# Custom chips

Wokwi has no model of three of our parts, so each needs a custom chip — a small C program
compiled to WASM that acts as the peripheral. The API supports I2C and UART devices, which is
what makes this possible: https://docs.wokwi.com/chips-api/getting-started

| Part | Why a custom chip | What it must do |
| --- | --- | --- |
| VL6180X | no ToF sensor exists in Wokwi | answer I2C at 0x29: model ID 0xB4, a range value a control slider sets, status "sample ready" |
| L9110S + motor | no H-bridge or DC motor part | read two pins and report direction and duty; a pair of LEDs is enough to *see* it, which is what `diagram.json` does today |
| DFR0534 | no MP3 module | accept UART frames and log them, so the sound profile can be asserted |

Only the VL6180X is genuinely needed: without it the firmware falls back to `SENSOR_STRATEGY =
"none"` and the buttons still drive a full cycle, which is enough to test the state machine.

Build with `wokwi-cli chip compile vl6180x.chip.c`, then uncomment the `[[chip]]` block in
`../wokwi.toml`.

**Status: not written yet.** `tests/test_on_fake_hardware.py` already covers the driver's
register conversation offline, so this is only worth writing when we want the sensor *in* the
simulation — see `../README.md` for what each layer of testing is for.
