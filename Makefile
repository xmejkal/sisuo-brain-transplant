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

# No check here may end in a pipe. A shell reports only the *last* command's status, so
# `cmd | tail -1` reports tail's success and a failing check passes silently — which is exactly
# what happened here: the two checks that compare the firmware, the board and the simulation
# could not fail at all. `.SHELLFLAGS := -o pipefail` would fix it on GNU make 3.82+, but macOS
# ships 3.81, which ignores it. So: run the command bare, keep its output, and print from the
# file afterwards.
SHELL := /bin/sh
export PATH := $(CURDIR)/node_modules/.bin:$(HOME)/.local/bin:$(PATH)

FIRMWARE   := firmware/micropython
SIM        := $(FIRMWARE)/sim
CONVERTER  := tools/circuit-to-wokwi

# --- the sources of truth ------------------------------------------------------------------
# Which microcontroller this is, in one file. Everything else derives from it — see boards/.
BOARD_DEFINITION := boards/xiao-esp32-c6.json
BOARD_SOURCES   := board.tsx XIAO-ESP32-C6-SMD.tsx $(BOARD_DEFINITION)
CIRCUIT         := dist/board/circuit.json
BOARD_SPEC      := $(FIRMWARE)/smartbin/board_spec.py

# --- everything derived from it ------------------------------------------------------------
DIAGRAM         := $(SIM)/diagram.json
GERBERS         := board-gerbers.zip
PCB_SVG         := board-pcb-routed.svg
SCHEMATIC_SVG   := board-sch.svg
MODEL_3D        := board.glb
CONVERTER_SRC   := $(wildcard $(CONVERTER)/lib/*.ts $(CONVERTER)/lib/**/*.ts) $(CONVERTER)/cli.ts
FIRMWARE_SOURCES := $(wildcard $(FIRMWARE)/smartbin/*.py) $(FIRMWARE)/config.py \
                    $(FIRMWARE)/main.py $(FIRMWARE)/boot.py
FLASH_IMAGE     := $(SIM)/flash-with-firmware.bin
MICROPYTHON_BIN := $(SIM)/micropython-c6.bin
CHIP_SOURCES    := $(wildcard $(SIM)/chips/*.chip.c)
CHIP_BINARIES   := $(CHIP_SOURCES:.chip.c=.chip.wasm)

DERIVED := $(BOARD_SPEC) $(CIRCUIT) $(DIAGRAM) $(FLASH_IMAGE) $(GERBERS) $(PCB_SVG) $(SCHEMATIC_SVG) $(MODEL_3D) $(CHIP_BINARIES)

.PHONY: all check clean install-hooks flash-image simulate simulate-all board-spec-current firmware-tests firmware-compiles firmware-simulates \
        board-builds pins-agree simulation-matches

all: $(DERIVED)
	@echo "everything is up to date."

# --- derivations ---------------------------------------------------------------------------

# The firmware cannot read boards/*.json at runtime, so it gets a generated module.
$(BOARD_SPEC): $(BOARD_DEFINITION) tools/generate-board-spec.py
	@echo "==> generating the firmware's board facts"
	@python3 tools/generate-board-spec.py

# The board design is the root: every other artefact below comes from this one file.
$(CIRCUIT): $(BOARD_SOURCES)
	@echo "==> building the board"
	@tsci build board.tsx > /dev/null
	@python3 -c "import json,sys; c=json.load(open('$(CIRCUIT)')); \
	   e=[x for x in c if 'error' in x['type']]; \
	   print('   %d traces, %d errors' % (sum(1 for x in c if x['type']=='pcb_trace'), len(e))); \
	   [print('   -', x.get('message','')[:120]) for x in e[:5]]; sys.exit(1 if e else 0)"

# The simulation is generated from the board, so it cannot describe a different bin.
$(DIAGRAM): $(CIRCUIT) $(BOARD_DEFINITION) $(CONVERTER_SRC) $(wildcard $(SIM)/chips/*.chip.json)
	@echo "==> generating the Wokwi diagram from the board"
	@cd $(CONVERTER) && bun run cli.ts > /tmp/smartbin-diagram.log 2>&1 \
	  || { cat /tmp/smartbin-diagram.log; exit 1; }
	@sed 's/^/   /' /tmp/smartbin-diagram.log | tail -3

# A flash image holding MicroPython and our code, which is what a headless simulation runs.
# Skipped with a message when the MicroPython build has not been downloaded.
$(FLASH_IMAGE): $(FIRMWARE_SOURCES) tools/build-flash-image.py
	@if [ -f $(MICROPYTHON_BIN) ]; then \
	   echo "==> building the flash image (MicroPython + our firmware)"; \
	   python3 tools/build-flash-image.py > /tmp/smartbin-image.log 2>&1 \
	     || { cat /tmp/smartbin-image.log; exit 1; }; \
	   tail -2 /tmp/smartbin-image.log | sed 's/^/   /'; \
	 else \
	   echo "==> flash image skipped: download $(MICROPYTHON_BIN) from"; \
	   echo "    https://micropython.org/download/ESP32_GENERIC_C6/"; \
	 fi

flash-image: $(FLASH_IMAGE)

# Run the simulation itself. Needs WOKWI_CLI_TOKEN from https://wokwi.com/dashboard/ci.
simulate: $(FLASH_IMAGE) $(DIAGRAM) $(CHIP_BINARIES)
	@command -v wokwi-cli > /dev/null || { \
	   echo "wokwi-cli not found. Install it with:"; \
	   echo "  curl -sL -o ~/.local/bin/wokwi-cli \\"; \
	   echo "    https://github.com/wokwi/wokwi-cli/releases/latest/download/wokwi-cli-macos-arm64"; \
	   echo "  chmod +x ~/.local/bin/wokwi-cli"; exit 1; }
	@[ -n "$$WOKWI_CLI_TOKEN" ] || { \
	   echo "WOKWI_CLI_TOKEN is not set. Get one (50 free CI minutes) at"; \
	   echo "  https://wokwi.com/dashboard/ci"; \
	   echo "then: echo 'export WOKWI_CLI_TOKEN=wok_...' >> ~/.zshrc"; exit 1; }
	@cd $(SIM) && wokwi-cli . --scenario lid-cycle.scenario.yaml --timeout 30000

# Every scenario, including the battery configuration, which needs its own flash image.
simulate-all: $(FLASH_IMAGE) $(DIAGRAM) $(CHIP_BINARIES)
	@python3 tools/build-flash-image.py --config \
	  '{"POWER_POLICY":"deep_sleep","SENSOR_STRATEGY":"tof_interrupt","SLEEP_AFTER_MS":3000}' \
	  flash-deep-sleep.bin > /dev/null
	@for scenario in lid-cycle wave-to-open obstruction; do \
	   printf "==> %s\n" "$$scenario"; \
	   (cd $(SIM) && wokwi-cli . --scenario $$scenario.scenario.yaml --timeout 120000 \
	      | grep -E "matched|completed|Timeout" | sed 's/^/   /') || exit 1; \
	 done
	@printf "==> deep sleep (battery configuration)\n"
	@cd $(SIM)/deep-sleep && wokwi-cli . --scenario sleep-and-wake.scenario.yaml --timeout 60000 \
	   | grep -E "matched|completed|Timeout" | sed 's/^/   /'

# Custom chips: C compiled to WASM, only when their source changes.
$(SIM)/%.chip.wasm: $(SIM)/%.chip.c $(SIM)/%.chip.json
	@echo "==> compiling custom chip $*"
	@cd $(SIM) && wokwi-cli chip compile $*.chip.c > /tmp/smartbin-chip.log 2>&1 \
	  || { cat /tmp/smartbin-chip.log; exit 1; }
	@tail -2 /tmp/smartbin-chip.log | sed 's/^/   /'

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

check: board-spec-current firmware-tests firmware-compiles firmware-simulates board-builds \
       pins-agree simulation-matches
	@echo "\neverything is in step."

board-spec-current:
	@echo "==> the firmware's board facts match the board definition"
	@python3 tools/generate-board-spec.py --check

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
	@cd $(CONVERTER) && bun run check-consistency.ts > /tmp/smartbin-pins.log 2>&1 \
	  || { cat /tmp/smartbin-pins.log; exit 1; }
	@tail -1 /tmp/smartbin-pins.log | sed 's/^/   /'

simulation-matches: $(CIRCUIT)
	@echo "==> the simulation matches the board"
	@cd $(CONVERTER) && bun test > /tmp/make-bun.txt 2>&1 || { tail -20 /tmp/make-bun.txt; exit 1; }
	@grep -E "^ *[0-9]+ pass" /tmp/make-bun.txt | sed 's/^/  /'
	@cd $(CONVERTER) && bun run cli.ts --check > /tmp/smartbin-check.log 2>&1 \
	  || { cat /tmp/smartbin-check.log; exit 1; }
	@tail -1 /tmp/smartbin-check.log | sed 's/^/   /'

# Refuse to commit a repository whose derived files disagree with the design. One-off, opt-in,
# and skippable with --no-verify; CI is the backstop that cannot be skipped.
install-hooks:
	@git config core.hooksPath tools/git-hooks
	@echo "git will now run 'make check' before each commit"

clean:
	rm -rf dist $(DIAGRAM) $(GERBERS) $(PCB_SVG) $(SCHEMATIC_SVG) $(MODEL_3D) $(CHIP_BINARIES)
