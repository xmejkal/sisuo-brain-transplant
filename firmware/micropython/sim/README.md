# Simulating the bin

Three layers of testing, cheapest first. Each catches things the one below cannot.

| Layer | Runs | Catches | Cost |
| --- | --- | --- | --- |
| `tests/` on the Mac | `python3 -m unittest discover -s tests -t tests` | the state machine, timings, strategies, and — via `tests/fake_machine.py` — device construction and the VL6180X register conversation | free, ~1 s |
| **Wokwi** (this folder) | a real MicroPython build on a simulated XIAO ESP32-C6 | anything that depends on the real `machine` module, asyncio on-device, boot behaviour, real pin toggling | free in the editor; CI needs a token |
| the bench | the actual bin | timing, electrical behaviour, the DFR0534's real command set, the lid's mechanics | the only thing that proves it works |

## What Wokwi does and does not have

Verified 2026-09-23 against [docs.wokwi.com](https://docs.wokwi.com/getting-started/supported-hardware):

* **ESP32-C6 is supported, and the XIAO ESP32-C6 is a stock board** — no porting, the pin map stays.
* **MicroPython runs**: point `wokwi.toml` at a MicroPython `.bin` and push code with `mpremote`
  over RFC2217, exactly as over USB.
* **Buttons and LEDs exist**; the motor is shown as two LEDs on the driver's input pins, which is
  enough to see and assert direction and duty.
* **No VL6180X, no H-bridge or DC motor, no MP3 module.** Each would need a custom chip
  (`chips/README.md`). Without the sensor, run with `SENSOR_STRATEGY = "none"` and drive the lid
  from the buttons — the state machine is what this layer is really testing.
* **Deep sleep under MicroPython is unverified here.** It works in Wokwi for Arduino/ESP-IDF
  projects, but nobody has confirmed `machine.deepsleep()` + `esp32.wake_on_ext1` in MicroPython.
  Treat a failure as "unsupported in the simulator" until the bench says otherwise.

## Running it

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
