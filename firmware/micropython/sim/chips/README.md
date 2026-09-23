# Custom chips

Wokwi has no model of three of our parts, so each needs a custom chip — a small C program
compiled to WASM that acts as the peripheral. The API supports I2C and UART devices, which is
what makes this possible: https://docs.wokwi.com/chips-api/getting-started

| Part | Why a custom chip | What it must do |
| --- | --- | --- |
| VL6180X | no ToF sensor exists in Wokwi | answer I2C at 0x29: model ID 0xB4, a range value a control slider sets, status "sample ready" |
| L9110S + motor | no H-bridge or DC motor part | read two pins and report direction and duty; a pair of LEDs is enough to *see* it, which is what `diagram.json` does today |
| DFR0534 | no MP3 module | accept UART frames and log them, so the sound profile can be asserted |

The VL6180X chip is the one that earns its keep: it is what makes "wave a hand at the bin"
testable, through the real I2C driver. Its distance is a slider you can drag mid-simulation.

`make` rebuilds them when their C changes; by hand it is `wokwi-cli chip compile <file>.chip.c`.

**Known divergences from the real parts** — a firmware that passes against these could still
fail on a bench, so they are worth knowing: the VL6180X chip always reports a good range status
(so `RangeError` and the failure-escalation path never occur in simulation), always says a
sample is ready (so the driver's poll timeout is never exercised), does not latch its interrupt
(so `clear_interrupt()` is untestable), and ignores the polarity and mode registers. The L9110S
chip models no current, so stall detection cannot be simulated at all.

**Status: both written, compiled and in use.** `vl6180x.chip.c` and `l9110s.chip.c` are
referenced from `../wokwi.toml` and rebuilt by `make`. The DFR0534 still has none, deliberately:
the firmware's log says which cue it played, which is all the simulation needs.
