# Simulating the bin

Three layers of testing, cheapest first. Each catches things the one below cannot.

**The middle layer runs today, locally, with no account:** `sim/run_on_micropython.py` runs the
real firmware on a real MicroPython runtime with a fake chip underneath it.

```sh
brew install micropython          # once
micropython sim/run_on_micropython.py     # 12 checks; exit code says pass or fail
python3     sim/run_on_micropython.py     # the same script under CPython, as a control
```

It presses the buttons, waves a hand at the rangefinder, holds something in the lid's way, and
checks what the bin does — on the runtime whose asyncio actually differs from CPython's. It
found a real bug the first time it ran: see below.

| Layer | Runs | Catches | Cost |
| --- | --- | --- | --- |
| `tests/` on the Mac | `python3 -m unittest discover -s tests -t tests` | the state machine, timings, strategies, and — via `tests/fake_machine.py` — device construction and the VL6180X register conversation | free, ~1 s |
| **`sim/run_on_micropython.py`** | the whole firmware on the MicroPython unix runtime | MicroPython's own semantics: its asyncio, its compiler, its ticks | free, ~8 s |
| **Wokwi** (this folder) | a real MicroPython build on a simulated XIAO ESP32-C6 | anything that depends on the real `machine` module, asyncio on-device, boot behaviour, real pin toggling | free in the editor; CI needs a token |
| the bench | the actual bin | timing, electrical behaviour, the DFR0534's real command set, the lid's mechanics | the only thing that proves it works |

## What Wokwi does and does not have

Verified 2026-09-23 against [docs.wokwi.com](https://docs.wokwi.com/getting-started/supported-hardware):

* **ESP32-C6 is supported, and the XIAO ESP32-C6 is a stock board** — no porting, the pin map stays.
* **MicroPython runs**: point `wokwi.toml` at a MicroPython `.bin` and push code with `mpremote`
  over RFC2217, exactly as over USB.
* **Buttons and LEDs exist**; the motor is shown as two LEDs on the driver's input pins, which is
  enough to see and assert direction and duty.
* **No VL6180X and no H-bridge — so we wrote them.** `chips/vl6180x.chip.c` answers I2C at 0x29
  with the registers the driver reads and a draggable distance slider; `chips/l9110s.chip.c`
  watches the driver's two inputs and prints `MOTOR: opening` / `closing` / `stopped`, which is
  what the scenario asserts on. Both compile with `wokwi-cli chip compile <file>.chip.c`.
* **No MP3 module.** Not worth a chip: the firmware's own log says which cue it played.
* **Deep sleep under MicroPython is unverified here.** It works in Wokwi for Arduino/ESP-IDF
  projects, but nobody has confirmed `machine.deepsleep()` + `esp32.wake_on_ext1` in MicroPython.
  Treat a failure as "unsupported in the simulator" until the bench says otherwise.

## Running it

Everything is in place except a token: the diagram lints clean, both custom chips compile, and
`micropython-c6.bin` (v1.29.0, the same version as the `mpy-cross` we compile with) is
downloaded. What remains is one environment variable.

```sh
export WOKWI_CLI_TOKEN=wok_...        # from https://wokwi.com/dashboard/ci (50 free CI minutes)
wokwi-cli . --scenario lid-cycle.scenario.yaml --timeout 20000
```

The CLI itself is a binary, not an npm package:

```sh
curl -sL -o ~/.local/bin/wokwi-cli \
  https://github.com/wokwi/wokwi-cli/releases/latest/download/wokwi-cli-macos-arm64
chmod +x ~/.local/bin/wokwi-cli
```

An agent can drive the simulator directly through Wokwi's MCP server, which is the same binary:

```json
{"mcpServers": {"wokwi": {"command": "wokwi-cli", "args": ["mcp"],
  "env": {"WOKWI_CLI_TOKEN": "wok_..."}}}}
```

## The older notes

**`diagram.json` is generated from `board.tsx`** — do not edit it by hand except to move parts
around, which `make` preserves. Everything else is overwritten on the next regeneration, on
purpose: a wiring diagram that disagrees with the board is worse than none.

In the browser, quickest: start from <https://wokwi.com/projects/new/micropython-esp32-c6>, paste
`diagram.json`, then paste the firmware files.

Locally, with the [Wokwi VS Code extension](https://docs.wokwi.com/vscode/getting-started):

```sh
# once: a MicroPython ESP32-C6 build, next to wokwi.toml
curl -L -o sim/micropython-c6.bin https://micropython.org/resources/firmware/ESP32_GENERIC_C6-<version>.bin

# start the simulation from VS Code, then push the firmware into it:
mpremote connect port:rfc2217://localhost:4000 fs cp -r smartbin :
mpremote connect port:rfc2217://localhost:4000 fs cp config.py main.py boot.py :
```

Headless, for CI ([wokwi-cli](https://docs.wokwi.com/wokwi-ci/cli-usage)):

```sh
export WOKWI_CLI_TOKEN=wok_...      # from https://wokwi.com/dashboard/ci
wokwi-cli sim --scenario sim/lid-cycle.scenario.yaml --timeout 20000
```

`lid-cycle.scenario.yaml` presses OPEN and then waits for each state transition in the serial log
— the firmware logs every one, so the state machine is directly observable with no extra harness.

## Honest limits

Nothing here has been run yet: the scenario file and diagram are written from the documented
formats, not from a passing run. The first run will need fixing up, most likely the part IDs in
`diagram.json` and the exact control name for a pushbutton. CI minutes may also need a paid plan
— the free allowance is not documented.


## What this layer has already caught

**A hand that never leaves held the lid open forever.** Every detection re-armed the hold timer,
by design — "a hand in the way keeps the lid open" — but nothing capped the total. Anything
parked in front of the sensor (a bin bag, a wall, a sticker on the window) would hold the lid
open until the battery was flat. The transition log made it obvious at a glance:

    open --hand_detected--> open
    open --hand_detected--> open
    open --hand_detected--> open        ... forever

Fixed with `config.MAX_OPEN_MS`: past that ceiling the lid closes regardless, and if something
really is in the way the closing stroke discovers it and the OBSTRUCTED path takes over — which
is where that decision belongs. Two regression tests in `tests/test_lid.py` hold it in place.

None of the Mac unit tests would have found this: they fire triggers deliberately, and nobody
writes the test for the case they did not think of. A scenario that just *holds a hand there* did.

## Compiling with MicroPython's own compiler

`mpy-cross` catches anything the on-device compiler would reject, in a second and with no runtime:

```sh
for f in smartbin/*.py config.py main.py boot.py; do mpy-cross -o /tmp/out.mpy "$f" || echo "FAIL $f"; done
```
