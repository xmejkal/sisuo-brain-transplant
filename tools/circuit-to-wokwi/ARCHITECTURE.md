# circuit-to-wokwi

Turns the board design into a Wokwi simulator project, so the simulation cannot drift from the
board it is meant to simulate.

`board.tsx` → `tsci build` → **`circuit.json`** → *this* → `diagram.json`.

## Why this exists

Nothing converts any EDA format to Wokwi's `diagram.json` — checked across npm and GitHub. The
alternative is hand-maintaining a wiring diagram beside a board design and hoping they agree,
which they will not after the third pin change.

## The pipeline

Each stage is a pure function in its own file, and the stage boundaries are where the extension
points are.

```
circuit.json
     │  lib/netlist.ts          extract what is logically true
     ▼
  Netlist  ◄── the intermediate representation: every future emitter reads this, and only this
     │
     │  lib/mapping.ts          project data: which Wokwi part stands in for which component
     │  lib/geometry.ts         part sizes and pin names, from Wokwi's own registry
     │  lib/placement.ts        where parts sit (deterministic, grid-snapped)
     ▼
  lib/emitters/wokwi.ts         Netlist + those three → diagram.json
     │
     │  lib/merge.ts            keep the positions a human tuned in the editor
     │  lib/validate.ts         lint offline, and prove every net made it
     ▼
 diagram.json
```

### The intermediate representation is the whole design

```ts
interface Netlist {
  components: Component[];   // { id, name, type, pins: [{ name, portId }] }
  nets: Net[];               // { id, name?, members: [{ componentId, pinName }] }
}
```

Deliberately thin — no geometry, no vendor concepts, nothing Wokwi-specific. A second emitter
(a docs table, a wiring list for the breadboard, a test-point list) reads the same `Netlist` and
knows nothing about the first. That is the only abstraction this tool asks anyone to learn.

**Connectivity is read exactly one way**: `getSourcePortConnectivityMapFromCircuitJson` from
`circuit-json-to-connectivity-map`. Every `source_port` already carries a precomputed net id, so
re-deriving nets from traces by hand would be a second implementation that can disagree with the
first. It is never done here.

## What we reuse, and what we must write

Reused, because someone maintains it better than we would:

| Package | For |
| --- | --- |
| `circuit-json-to-connectivity-map` | nets — the one source of connectivity |
| `@tscircuit/circuit-json-util` | element lookup (`cju`) and readable names |
| `@wokwi/diagram-lint` | **twice**: as the offline pin-name oracle (`PartRegistry`, 137 parts with real pin lists) and as the validator of what we emit |

Written here, because nothing upstream can know it:

* **the mapping table** — a VL6180X has no Wokwi part; a bicolour LED is two Wokwi LEDs; a
  pushbutton's pins are `1.l`/`2.l`, not `1`/`2`. No tool can guess this, so it is curated data;
* **net → wires** — Wokwi has no concept of a net, only pin-to-pin wires, so each net is expanded
  (star from the board pin where there is one, otherwise a chain);
* **placement** — Wokwi wants absolute pixels.

## Placement, and why it is deliberately dumb

The temptation is a real layout engine (`elkjs` can do it, with fixed port positions). We are not
doing that yet, because **generated files must be diffable**: a deterministic, grid-snapped
heuristic gives a diff you can read when a pin changes, and a force-directed layout gives a
diff where everything moved.

So: the board sits at the origin, other parts are stacked either side of it depending on which
edge their board pin is on, and everything snaps to Wokwi's 9.6 px grid (0.1 inch; `MM_TO_PX` is
96/25.4). `Placer` is an interface, so a better one can be dropped in later without touching the
emitter.

Better still, `lib/merge.ts` means the machine does not have the last word: positions already in
the target file are preserved, so you drag the parts around once in the Wokwi editor and
regeneration keeps your layout. The generator owns *what is connected*; you own *what it looks
like*.

## How it proves itself

Three checks, all offline, all in the test suite:

1. **Lint** — `@wokwi/diagram-lint` catches unknown part types, invalid pin names and duplicate
   ids, using Wokwi's own registry.
2. **Coverage** — every net in the `Netlist` must appear in the diagram. This is the guarantee
   the tool exists for: if a net is missing, the simulation is not simulating the board.
3. **Snapshot** — the emitted diagram for a fixture board, so an upstream `0.0.x` bump cannot
   quietly change the output.

Plus `--check` mode: regenerate and compare against the committed file, non-zero on difference.
That is the CI gate that keeps a stale diagram from surviving a pin change.

## Errors

A missing mapping or an unknown pin is a **collected** error, not a thrown one: one run tells you
every component it cannot place, with the component name and the pins involved, rather than
making you fix them one at a time.

## Adding things later

| To add | Do this | Touches |
| --- | --- | --- |
| a new part | one entry in `lib/mapping.ts` | data only |
| a new output (docs, wiring list, KiCad hand-off) | `lib/emitters/<name>.ts` reading `Netlist` | nothing else |
| better layout | implement `Placer` | `lib/placement.ts` |
| another source (a KiCad netlist, say) | a reader producing `Netlist` | nothing else |

## Deliberate non-goals

* **Not an npm package.** It is a tool in this repo. tscircuit publishes one package per target;
  we have one target and one consumer, and a package would be ceremony.
* **No pretty wire routing.** Wokwi's route mini-language is hand-tuning territory; the merge
  step preserves what a human wrote.
* **Not a schematic renderer.** `circuit-to-svg` already does that, and `tsci export` calls it.

## Status

Built and working against the real board:

```
$ bun run cli.ts
board: 19 components, 18 nets
diagram: 8 parts, 17 wires, 9/18 nets wired

not simulated, on purpose:
  Mp3Player: no Wokwi part; cues are visible in the serial log
  BinConnector: a connector is wiring, not a part to simulate
  ...
```

23 tests (`bun test`), typechecked (`bun run typecheck`), and the output passes **Wokwi's own**
`wokwi-cli lint` as well as the in-process linter.

The nine unwired nets are the skip rules working: they connect capacitors, the connector and the
MP3 module, none of which the simulation has parts for.

### What it caught while being written

* `board-ssd1306` uses pins `SDA`/`SCL`, not `DATA`/`CLK` — the pin oracle rejected the wrong
  names before anything ran.
* A wire to `motordriver:PWMA`, which passes `wokwi-cli lint` because it cannot resolve custom
  chips. The L9110S standing in for the board's TB6612 has no PWM pin, and now `mapping.ts` says
  so explicitly and the oracle reads our own `chip.json` files.

### Using it

```sh
cd tools/circuit-to-wokwi
bun install
bun run generate    # write the diagram
bun run check       # fail if the committed diagram is out of date  <- the CI gate
bun test
```

The output goes to `firmware/micropython/sim/diagram.generated.json`, beside the hand-written
`diagram.json`. They differ on purpose right now: the hand-written one describes the **v2** design
(L9110S, rangefinder, no OLED) while `board.tsx` is still **v1**. When the board is redone for v2,
the generated file becomes the only one, and `bun run check` becomes the thing that keeps it true.
