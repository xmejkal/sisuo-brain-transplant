# Everything derived from the board design, regenerated when the design changes.
#
#   make            regenerate whatever is out of date
#   make check      verify everything agrees, changing nothing   <- what CI runs
#   make -n         show what would be regenerated, and why
#   make clean      delete the derived files
#
# The rule of the project: `board.tsx` and the firmware are written by hand; everything below is
# derived. If a derived file is edited by hand, the next `make` throws that edit away — which is
# the point, because a diagram that disagrees with the board is worse than no diagram.
#
# Make is used rather than a script because the dependencies are real files: change `board.tsx`
# and only the things downstream of it are rebuilt, in order, and `make -n` explains the plan.

SHELL := /bin/sh
export PATH := $(CURDIR)/node_modules/.bin:$(PATH)

FIRMWARE   := firmware/micropython
SIM        := $(FIRMWARE)/sim
CONVERTER  := tools/circuit-to-wokwi

# --- the source of truth -------------------------------------------------------------------
BOARD_SOURCES   := board.tsx XIAO-ESP32-C6-SMD.tsx
CIRCUIT         := dist/board/circuit.json

# --- everything derived from it ------------------------------------------------------------
DIAGRAM         := $(SIM)/diagram.json
GERBERS         := board-gerbers.zip
PCB_SVG         := board-pcb-routed.svg
SCHEMATIC_SVG   := board-sch.svg
MODEL_3D        := board.glb
CONVERTER_SRC   := $(wildcard $(CONVERTER)/lib/*.ts $(CONVERTER)/lib/**/*.ts) $(CONVERTER)/cli.ts
CHIP_SOURCES    := $(wildcard $(SIM)/chips/*.chip.c)
CHIP_BINARIES   := $(CHIP_SOURCES:.chip.c=.chip.wasm)

DERIVED := $(CIRCUIT) $(DIAGRAM) $(GERBERS) $(PCB_SVG) $(SCHEMATIC_SVG) $(MODEL_3D) $(CHIP_BINARIES)

.PHONY: all check clean install-hooks firmware-tests firmware-compiles firmware-simulates \
        board-builds pins-agree simulation-matches

all: $(DERIVED)
	@echo "everything is up to date."

# --- derivations ---------------------------------------------------------------------------

# The board design is the root: every other artefact below comes from this one file.
$(CIRCUIT): $(BOARD_SOURCES)
	@echo "==> building the board"
	@tsci build board.tsx > /dev/null
	@python3 -c "import json,sys; c=json.load(open('$(CIRCUIT)')); \
	   e=[x for x in c if 'error' in x['type']]; \
	   print('   %d traces, %d errors' % (sum(1 for x in c if x['type']=='pcb_trace'), len(e))); \
	   [print('   -', x.get('message','')[:120]) for x in e[:5]]; sys.exit(1 if e else 0)"

# The simulation is generated from the board, so it cannot describe a different bin.
$(DIAGRAM): $(CIRCUIT) $(CONVERTER_SRC) $(wildcard $(SIM)/chips/*.chip.json)
	@echo "==> generating the Wokwi diagram from the board"
	@cd $(CONVERTER) && bun run cli.ts | sed 's/^/   /'

# Custom chips: C compiled to WASM, only when their source changes.
$(SIM)/%.chip.wasm: $(SIM)/%.chip.c $(SIM)/%.chip.json
	@echo "==> compiling custom chip $*"
	@cd $(SIM) && wokwi-cli chip compile $*.chip.c | tail -2 | sed 's/^/   /'

$(GERBERS): $(CIRCUIT)
	@echo "==> exporting fab package"
	@tsci export -f gerbers board.tsx -o $@ > /dev/null

$(PCB_SVG): $(CIRCUIT)
	@echo "==> exporting PCB view"
	@tsci export -f pcb-svg board.tsx -o $@ > /dev/null

$(SCHEMATIC_SVG): $(CIRCUIT)
	@echo "==> exporting schematic"
	@tsci export -f schematic-svg board.tsx -o $@ > /dev/null

$(MODEL_3D): $(CIRCUIT)
	@echo "==> exporting 3D model"
	@tsci export -f glb board.tsx -o $@ > /dev/null

# --- verification: changes nothing, fails if anything disagrees -----------------------------

check: firmware-tests firmware-compiles firmware-simulates board-builds pins-agree \
       simulation-matches
	@echo "\neverything is in step."

firmware-tests:
	@echo "==> firmware logic (CPython)"
	@cd $(FIRMWARE) && python3 -m unittest discover -s tests -t tests 2>&1 | grep -E "^(OK|FAILED|Ran)" | sed 's/^/   /'
	@cd $(FIRMWARE) && python3 -m unittest discover -s tests -t tests > /dev/null 2>&1

firmware-compiles:
	@echo "==> firmware compiles under MicroPython's own compiler"
	@for source in $(FIRMWARE)/smartbin/*.py $(FIRMWARE)/config.py $(FIRMWARE)/main.py $(FIRMWARE)/boot.py; do \
	   mpy-cross -o /tmp/make-check.mpy $$source || exit 1; \
	 done
	@echo "   all modules compile"

firmware-simulates:
	@echo "==> firmware behaves, on a real MicroPython runtime"
	@if command -v micropython > /dev/null; then \
	   cd $(FIRMWARE) && micropython sim/run_on_micropython.py > /tmp/make-sim.txt 2>&1 \
	     || { tail -20 /tmp/make-sim.txt; exit 1; }; \
	   grep -c PASS /tmp/make-sim.txt | sed 's/^/   /;s/$$/ checks passed/'; \
	 else echo "   skipped: brew install micropython"; fi

board-builds: $(CIRCUIT)

pins-agree: $(CIRCUIT)
	@echo "==> firmware and board agree on every pin"
	@cd $(CONVERTER) && bun run check-consistency.ts | tail -1 | sed 's/^/   /'

simulation-matches: $(CIRCUIT)
	@echo "==> the simulation matches the board"
	@cd $(CONVERTER) && bun test > /tmp/make-bun.txt 2>&1 || { tail -20 /tmp/make-bun.txt; exit 1; }
	@grep -E "^ *[0-9]+ pass" /tmp/make-bun.txt | sed 's/^/  /'
	@cd $(CONVERTER) && bun run cli.ts --check | tail -1 | sed 's/^/   /'

# Refuse to commit a repository whose derived files disagree with the design. One-off, opt-in,
# and skippable with --no-verify; CI is the backstop that cannot be skipped.
install-hooks:
	@git config core.hooksPath tools/git-hooks
	@echo "git will now run 'make check' before each commit"

clean:
	rm -rf dist $(DIAGRAM) $(GERBERS) $(PCB_SVG) $(SCHEMATIC_SVG) $(MODEL_3D) $(CHIP_BINARIES)
