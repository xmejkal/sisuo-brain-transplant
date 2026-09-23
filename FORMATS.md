# One design, many formats

How the board in `board.tsx` becomes a simulator project, a KiCad design, a SPICE netlist and
something Fusion 360 can use — and how to add the next target without it becoming a mess.

## The honest answer to "what is the standard format?"

There isn't one. The candidates and what they actually carry:

| Format | Carries | Verdict for us |
| --- | --- | --- |
| **Circuit JSON** (tscircuit) | logical netlist + schematic geometry + PCB geometry + 3D refs, all in one file | **Our pivot.** It is what `tsci build` already emits, and the only format carrying everything at once |
| KiCad `.kicad_sch` / `.kicad_pcb` | full schematic and board, open s-expression | **Our secondary pivot** — the ticket to a mature toolchain (`kicad-cli`) |
| KiCad `.net` netlist | refdes, footprints, nets — no geometry | Fine to read, but KiCad cannot import one into a blank schematic |
| SPICE netlist | topology and device models only | A *target*, for analog simulation. Loses packaging |
| EDIF | netlist only, 1988 vintage | Effectively dead |
| IPC-2581 / ODB++ | complete fab and assembly data | Only if a fab asks. ODB++ is Siemens-owned |
| Fritzing `.fzz`, Eagle, Altium | full designs, vendor-shaped | Lock-in; not worth converting into |
| **Wokwi `diagram.json`** | parts and pin-to-pin wires, no net concept | A *target*, and the one nobody has written a converter for |

Caveat worth knowing: every tscircuit package is still `0.0.x`. The shape is de-facto stable and
Zod-validated, but it is not a frozen standard — so pin exact versions.

## The map

```
                      board.tsx
                          │  tsci build
                          ▼
                   circuit.json  ← the pivot: everything downstream reads this
                          │
     ┌────────────────────┼─────────────────────────────┐
     │                    │                             │
  tsci export      our converter                 circuit-json-to-kicad
  (native)         (the only new code)                  │
     │                    │                             ▼
     ▼                    ▼                      .kicad_sch / .kicad_pcb
 gerbers, BOM,     sim/diagram.json                     │  kicad-cli
 SVG, GLB, STEP,   (Wokwi)                    ┌─────────┼──────────┬─────────┐
 specctra DSN                                 ▼         ▼          ▼         ▼
                                            STEP      DXF        SPICE    ERC/DRC
                                          (Fusion)  (outline)  (analog)   (checks)
```

**The rule: delegate anything mature to KiCad.** `kicad-cli` already exports STEP, DXF, SPICE,
BOM and runs ERC/DRC headless. Emitting KiCad files and letting it do that work means maintaining
two converters instead of six.

## The one converter we have to write

Nothing anywhere converts an EDA format to Wokwi's `diagram.json` — I looked. It is also the
smallest of the targets, because the format is small.

### Shape

```
circuit.json ──► logical netlist ──► emitter ──► diagram.json
                 (components,        + mapping
                  nets, pins)          table
```

**Logical netlist** — the one shared abstraction, and deliberately thin: components with a
reference, a type and pins; nets with their member pins. Everything else each emitter derives
for itself.

Connectivity is read **one way only**: every `source_port` and `source_trace` in Circuit JSON
carries a `subcircuit_connectivity_map_key`, which is a precomputed net id, so grouping ports by
that key *is* the netlist. No graph traversal, and no second implementation to keep correct.
(`circuit-json-to-connectivity-map` wraps the same thing if we would rather not hand-roll it.)

**Mapping table** — the genuinely new work, and it is *data*, not code:

| Our part | Wokwi | Notes |
| --- | --- | --- |
| XIAO ESP32-C6 | `board-xiao-esp32-c6` | pins are `D0`–`D10`, `3V3`, `5V`, `GND` — **not** GPIO numbers |
| Button | `wokwi-pushbutton` | |
| Bicolour LED | two `wokwi-led` + resistors | Wokwi has no bicolour part |
| VL6180X | `chip-vl6180x` | our custom chip |
| L9110S | `chip-l9110s` | our custom chip |
| DFR0534 | — | no chip; the firmware's log says what it played |

A part with no mapping is an error the converter reports, not something it silently drops.

### What is generated and what stays hand-written

Generated, because it comes from the design and must never drift:
* the part list, from the components,
* the connections, by expanding each net into pin-to-pin wires.

Hand-written, because the design does not know it and a generator would do it badly:
* `top`/`left` positions and wire `route`s — no anchor geometry is published, so auto-placement
  looks terrible,
* which modules become custom chips, and those chips' pins and controls,
* the scenario files: the assertions are the test, and tests are written, not derived.

So the converter **merges**: it rewrites parts and connections while preserving the positions
already in the file. Layout is edited once, in the Wokwi editor, and kept.

### How we know it is right

1. `@wokwi/diagram-lint` runs **in-process and offline** (it bundles the part definitions), so
   every generated diagram is checked for unknown parts, invalid pins and duplicate ids before
   it is written.
2. A **coverage check**: every net in the netlist must appear in the diagram, or the converter
   fails. This is the guarantee that the simulation matches the board.
3. A snapshot test per emitter, so an upstream `0.0.x` bump cannot quietly change the output.

### Where it lives

```
tools/circuit-to-wokwi/
  netlist.ts     circuit.json  -> logical netlist          (shared by every future emitter)
  mapping.ts     the part/pin table above                  (data)
  emit.ts        logical netlist -> diagram.json           (~100 lines)
  merge.ts       keep hand-tuned positions                 
  cli.ts         tsci build && convert && lint
```

TypeScript rather than Python, because the tscircuit and Wokwi tooling is all npm and we get
their types and their linter for free.

**Adding a target later is then one file**: a new emitter consuming the same logical netlist.
A wiring/breadboard diagram, a documentation table, a test-point list — each is about a hundred
lines and none of them touch the others.

## Headless KiCad, for checking rather than converting

`kicad-cli` is worth having in CI for what it *checks*, not only what it exports:

```sh
kicad-cli sch erc board.kicad_sch      # electrical rules: unconnected pins, conflicting outputs
kicad-cli pcb drc board.kicad_pcb      # clearances, track widths, unrouted nets
```

That is real verification the tscircuit autorouter cannot give us, and it is the answer to
"can we test the board itself?" — yes, headlessly, once we emit KiCad files.

## Fusion 360

Fusion imports **STEP** as solids; meshes (GLB/OBJ) come in as decoration you cannot model
against. In order of reliability:

1. **`kicad-cli pcb export dxf`** of the board outline → sketch-import into Fusion. Most robust,
   and usually all an enclosure needs.
2. **`kicad-cli pcb export step`** → a real board solid, synthesized from outline and drills even
   where parts lack 3D models.
3. **`tsci export -f step`** exists, but our parts' 3D models come from JLCPCB as OBJ meshes, so
   expect meshes rather than solids.

The gap to be blunt about: nothing in this chain produces proper solid models of the *modules*
(XIAO, DFR0534, the rangefinder). Use the vendors' own STEP files — `parts/PARTS.md` tracks
where they are — or draw blocks by hand.

## Order of work

1. The Wokwi converter, once the simulation runs with the hand-written diagram (so there is a
   known-good target to reproduce).
2. `circuit-json-to-kicad` + `kicad-cli` ERC/DRC in CI, when the v2 board exists.
3. DXF outline for the enclosure, when the v2 board exists.
4. SPICE, only if the stall-sense divider needs proving on paper before it is built.

## Known blocker

`tsci` will not currently run here: `node_modules/.bin/bun` fails with "cannot execute binary
file", so the toolchain needs reinstalling (`npm ci`) before any of this can be wired up.

---

## Built: `tools/circuit-to-wokwi`

The Wokwi converter described above now exists — see `tools/circuit-to-wokwi/ARCHITECTURE.md`.
Design as planned: `circuit.json` → a thin `Netlist` → emitter, with the mapping table as data,
connectivity read only through `circuit-json-to-connectivity-map`, and `@wokwi/diagram-lint` used
twice (as the offline pin-name oracle and as the validator). 23 tests; `--check` is the CI gate.

The research changed three things from the plan:

1. **`@wokwi/diagram-lint` bundles Wokwi's part registry** — 137 parts with real pin lists — so
   pin names are validated offline instead of guessed. It caught two wrong pin names immediately.
2. **Custom chips are not in that registry**, and `wokwi-cli lint` cannot resolve them either, so
   the oracle also reads our own `chip.json` files. That hole had already let a bad wire through.
3. **A stand-in part can lack a pin the real one has** (the L9110S has no PWM input where the
   TB6612 does). The mapping table can now say so with `null`, which records a decision instead of
   emitting an invalid wire.


## Keeping it all in step

Four layers, each cheap, each covering the one before it:

| Layer | Catches | Misses |
| --- | --- | --- |
| **`make`** | anything out of date, on demand; `make -n` shows the plan | anyone who does not run it |
| **Claude Code hook** (the `spark` plugin's `hooks/hooks.json`) | drift the moment an AI session edits `board.tsx`, `config.py` or the mapping table | edits made in another editor |
| **git pre-commit** (`make install-hooks`) | drift before it reaches history | `git commit --no-verify` |
| **GitHub Actions** (`make check` on push) | everything, permanently | nothing, but it is the slowest to tell you |

`make` regenerates; `make check` changes nothing and fails if anything disagrees. That second
mode is what stops a stale diagram from being committed, and it is why every generator here has
a `--check` flag.

The check people forget is the third one: **firmware against hardware**. Nothing else would
notice that `config.py` drives D3 while the board wired the motor to D0 — and nothing would,
until the lid did not move. `tools/circuit-to-wokwi/check-consistency.ts` reads the pin numbers
out of the firmware and the labels out of the design and compares them: currently 14 pins, all
in agreement.
