# Firmware v2 plan — MicroPython, OO, testable

Status: **proposed, awaiting approval**. Supersedes the v1 port in `firmware/micropython/main.py`
(kept until v2 works). Reviewed by a MicroPython/ESP32 architecture pass and a digital-electronics
pass on 2026-09-23; their hardware findings are folded into `DESIGN_RULES.md` and `SHOPPING.md`.

## Design principles
1. **Strategy pattern where the hardware is genuinely undecided** — how we sense a hand, and how we
   know the lid is shut. Both are swappable objects behind a tiny interface, chosen in one place.
2. **Dependency injection**: nothing constructs its own pins. `Hardware` owns every peripheral and is
   passed in, so a `FakeHardware` runs the same logic on the Mac under CPython.
3. **Sync primitives, async motion, declarative transitions**: `motor.drive()`, `sensor.read()`,
   `led.set()`, `mp3.play()` are plain blocking calls you can type in the REPL; motion strokes are
   `async` tasks; and what may follow what lives in a transition table, not in `if` statements.
4. **Construct ≠ run**: `build()` makes objects and starts nothing; `run()` is the only thing that
   starts a loop; `main.py` is two lines. This is what makes bench debugging pleasant.
5. **The safety cap is structural, not a check**: every motor movement is inside `try/finally`, and
   the hard `MOTOR_MAX_RUN_MS` cap is the guarantee — not the sensor, not the timer.

## Strategies

### `ProximitySensor` — "is a hand there?"
```python
class ProximitySensor:          # protocol, not inheritance-enforced
    def read(self) -> int | None  # distance in mm, or None if unknown/not ranging
    def detected(self) -> bool    # the decision, with hysteresis + debounce inside
```
| Implementation | Hardware | Notes |
| --- | --- | --- |
| `TofSensor` | VL6180X on I2C | Primary. `30 mm < range < 100 mm` for N samples. Wraps `OSError`, re-inits after N failures. |
| `IrBurstSensor` | IR LED + CHQ1838 | Fallback that fits the lid holes. 38 kHz bursts (~10–20 cycles, gaps ≥4× burst — these receivers suppress a continuous carrier). `read()` returns `None`; it has no distance. |
| `ButtonOnlySensor` | none | Always `False`. Lets the whole bin run with no sensor at all during bring-up. |
| `FakeSensor` | none | Test double; you set what it returns. |

### `CloseDetector` — "is the lid shut?"
```python
class CloseDetector:
    def start(self) -> None           # called as the close stroke begins
    def closed(self, elapsed_ms) -> bool
```
| Implementation | Hardware | Notes |
| --- | --- | --- |
| `TimedCloseDetector` | none | v1 behaviour: `elapsed >= LID_CLOSE_RUN_MS`. Default. |
| `StallCloseDetector` | 1 Ω shunt → ADC on D1 | v2. Current above ~2× running for M samples, with a 150–200 ms blanking window for inrush. |
| `LimitSwitchCloseDetector` | one microswitch | Deterministic, zero calibration — the electronics reviewer's preferred option if you're willing to fit a switch. |

Both strategies are chosen in `config.py` (`SENSOR = "tof"`, `CLOSE_DETECT = "timed"`) and built in
one factory function, so swapping is a config edit plus a soft reset — no code change.

## The state machine — the spine of the firmware
The lid genuinely has states, so model them explicitly rather than inferring them from timers. The
machine owns three things: **which state we're in, which transitions are legal, and what is emitted
when one happens.** Motion coroutines no longer decide anything; they just drive the motor and
report back.

Why this over the plain async sequence: one authoritative `b.lid.state` to look at in the REPL;
illegal transitions are caught instead of silently doing something odd; **events can't be forgotten,
because the machine emits them, not the programmer**; and the whole table is testable on the Mac
with no hardware. It also gives the obstruction behaviour a place to live — the thing the original
bin got wrong (it retried forever, waiting for a signal that never came).

### States
| State | Meaning | Motor |
| --- | --- | --- |
| `IDLE` | shut, watching for a hand | off |
| `OPENING` | driving open | running |
| `OPEN` | held open, hold timer running | off |
| `CLOSING` | driving shut | running |
| `OBSTRUCTED` | something stopped the lid mid-close; re-opened to free it | off |
| `FAULT` | repeated obstruction or a dead sensor; needs a button press | off, latched |

### Triggers
`HAND_DETECTED` · `OPEN_PRESSED` · `MODE_PRESSED` · `STROKE_DONE` (motion finished normally) ·
`CAP_TRIPPED` (hard `MOTOR_MAX_RUN_MS` limit) · `CLOSED_CONFIRMED` (from the `CloseDetector`) ·
`HOLD_EXPIRED` · `SENSOR_FAILED` · `RESET`

### Transition table — data, not code
```python
TRANSITIONS = {
    IDLE:       {HAND_DETECTED: OPENING, OPEN_PRESSED: OPENING},
    OPENING:    {STROKE_DONE: OPEN, CAP_TRIPPED: OPEN},       # cap while opening = simply stop
    OPEN:       {HOLD_EXPIRED: CLOSING, OPEN_PRESSED: OPEN,   # re-press re-arms the hold
                 HAND_DETECTED: OPEN},                        # hand still there? keep it open
    CLOSING:    {CLOSED_CONFIRMED: IDLE, STROKE_DONE: IDLE,
                 CAP_TRIPPED: OBSTRUCTED, HAND_DETECTED: OBSTRUCTED},
    OBSTRUCTED: {STROKE_DONE: OPEN, RETRY_EXHAUSTED: FAULT},
    FAULT:      {OPEN_PRESSED: IDLE, RESET: IDLE},
}
```
Each entry is one line to read and one line to change. `on_enter` / `on_exit` hooks per state do the
work (start a motion task, cancel it, start the hold timer), and the machine emits a transition
event to the bus **around every hook**, so audio, LED and log listeners need no cooperation from the
lid code at all.

### The policies that matter
- **Nothing gets crushed.** `CAP_TRIPPED` or a hand seen while closing → `OBSTRUCTED`: reverse to
  open, announce, wait, then retry the close. After `MAX_CLOSE_RETRIES` → `FAULT`, red LED, and it
  stays there until a button is pressed. Never the original bin's infinite retry.
- **A hand in the way keeps the lid open** rather than fighting it (`HAND_DETECTED` in `OPEN`
  re-arms the hold timer).
- **`CAP_TRIPPED` while opening is benign** — the lid is simply at its stop. Same during closing it
  is not, which is why the two are different rows.
- **`FAULT` is latched and loud.** A sensor that fails repeatedly parks the bin in a safe, obvious
  state instead of quietly never opening.

### What this buys on the bench
`b.lid.state`, `b.lid.history[-5:]` (the last transitions with timestamps), and
`b.lid.fire(HAND_DETECTED)` to drive the machine by hand with no sensor connected. The table also
prints as a Mermaid diagram (`tools/fsm_diagram.py`) so the docs can't drift from the code.

## Events, sounds and feedback — configurable, not hard-coded
The lid must not know that sound exists. **The state machine emits one event per transition**;
whatever cares subscribes. Adding a
new reaction (a second LED, a log line, a future WiFi notification) means adding a listener, never
editing `Lid` — open/closed principle, and it keeps each class to one reason to change.

**The event vocabulary is the state machine's own**: entering a state *is* the event
(`entered:OPENING`, `entered:OBSTRUCTED`, `entered:FAULT`…), so there is exactly one list of names
and no second vocabulary to keep in sync. A handful of non-state events sit alongside it
(`MODE_CHANGED`, `LOW_BATTERY`, `SENSOR_RECOVERED`).

```python
class EventBus:
    def subscribe(self, listener): ...      # listener(event, **data)
    def emit(self, event, **data): ...      # never raises into the caller
```
Listeners: `AudioFeedback` (plays a track), `LedFeedback` (colour/blink), `LogFeedback` (console).
Each is independently disableable.

**Sounds live entirely in config**, as a *sound profile* — a mapping from event to track number:
```python
SOUND_PROFILES = {                       # state entered -> track number
    "default": {OPENING: 1, IDLE: 2, OBSTRUCTED: 3, FAULT: 8},
    "chatty":  {OPENING: 4, OPEN: 5, CLOSING: 6, IDLE: 7, OBSTRUCTED: 3, FAULT: 8},
    "silent":  {},
}
ACTIVE_PROFILE = "default"
VOLUME = 22
```
`AudioFeedback` just looks the event up and plays it; an unmapped event is silence, so a profile is
purely data — no code changes to re-voice the bin, and `/config.json` can override the profile and
volume per unit. **The MODE button cycles profiles** (default → chatty → silent) and persists the
choice to `config.json`, which finally gives that button the job v1 never gave it. LED feedback maps
the same way (`LED_COLOURS = {OPENING: "green", BLOCKED: "red", ...}`).

This is the SOLID payoff in practice: `Lid` depends on an `EventBus` interface, not on an MP3
module; `AudioFeedback` depends on a `Player` interface, not on the DFR0534; swapping in a buzzer,
or muting audio entirely, touches one line of config.

## File layout on the device
```
boot.py                  # no WiFi, no auto-start, nothing else
main.py                  # import smartbin; smartbin.run()
config.py                # tunables as constants; overlays /config.json if present
config.json              # per-unit bench calibration only (run times, thresholds, ToF offsets)
lib/                     # mip installs (aiorepl); never edited
smartbin/
  __init__.py            # build(), run(), VERSION
  compat.py              # ticks_ms/ticks_diff/sleep_ms shims so logic runs under CPython
  log.py                 # leveled logger, lazy % formatting, LEVEL flippable from the REPL
  hw.py                  # Hardware: owns every Pin/PWM/UART/I2C; the injection seam
  motor.py               # L9110Driver: drive(direction, speed), stop(), brake()
  lid.py                 # Lid: on_enter/on_exit hooks, motion tasks, the safety cap
  sensors.py             # ProximitySensor strategies
  closing.py             # CloseDetector strategies
  fsm.py                 # StateMachine: table, guards, history, event emission
  ui.py                  # Button (debounced), StatusLed (red/green/blink)
  audio.py               # Dfr0534: play(track), volume(v) — write-only UART frames
  vl6180x.py             # our port of Adafruit's driver (see below)
  app.py                 # SmartBin: wires tasks together
tests/                   # CPython unittest, runs on the Mac against FakeHardware
```

## Concurrency: asyncio + aiorepl
`asyncio` because the lid sequence reads top-to-bottom (`open(); await sleep(HOLD); close()`) instead
of a state enum with timestamp comparisons, and because task cancellation gives "abort mid-motion"
for free. The catch — the REPL is dead while `asyncio.run()` executes — is solved by
`mpremote mip install aiorepl`, which gives a live REPL *while the bin runs*, so you can type
`b.lid.state` or `b.sensor.read()` mid-operation. That library is the reason this choice wins.

## Bench workflow
```sh
mpremote mip install aiorepl          # once
mpremote cp -r smartbin/ :            # deploy
mpremote run tools/bringup_XX.py      # per-module tests, nothing persisted
mpremote repl                         # Ctrl-C stops main.py, then:
>>> import smartbin; b = smartbin.build()   # objects, no loop
>>> b.motor.drive(True, 200); b.motor.stop()
>>> b.sensor.read()
>>> import asyncio; asyncio.run(b.lid.cycle())
>>> smartbin.log.LEVEL = smartbin.log.DEBUG
```
Holding the MODE button at boot makes `main.py` skip `run()` — insurance against a board that
reboot-loops into lid motion.

## Safety decisions
- **`try/finally` around every drive**, plus a `finally` in `run()`. `CancelledError` and
  `KeyboardInterrupt` both unwind through it.
- **`MOTOR_MAX_RUN_MS` is the real guarantee** — a Ctrl-C landing between frames can still skip a
  `finally`, so the cap must be enforced by the motion loop itself, not only by the caller.
- **Watchdog (`machine.WDT`, ~8 s) started inside `run()` only, never in `build()`** — WDT can't be
  stopped once started, so a WDT at import would reset the board while you think in the REPL.
- **10 kΩ pulldowns on both L9110S inputs (hardware).** After a hard reset the XIAO's pins are
  high-Z for ~300 ms before code runs; MicroPython does not guarantee pin state across a soft reset
  either. The pulldowns are the only guarantee that survives a crash, brownout or reflash.
- Motor pins driven low on boot and before any sleep — a 3.3 V input against an unpowered 6 V rail
  injects current into the driver.
- `time.ticks_diff()` everywhere, never `now - start`. A wraparound bug in the cap check is exactly
  the one that burns the motor.

## VL6180X driver
Port Adafruit's maintained CircuitPython driver to `smartbin/vl6180x.py` (only four private I2C
helpers change, to `writeto_mem`/`readfrom_mem(..., addrsize=16)`), rather than using the only
existing MicroPython file, which is from 2017 and has real bugs: it raises on every soft reset
without a sensor power-cycle, and never checks `RESULT__RANGE_STATUS`, so an error is
indistinguishable from a genuine 255 mm. Then add the four registers no driver exposes — offset
`0x24`, crosstalk `0x1E`, range-ignore `0x26` + `0x2D` — which we need once it sits behind the lid
window. Full notes in `parts/SENSOR_OPTIONS.md`.

## Testing
- `tests/` runs under CPython on the Mac with `FakeHardware` + a fake clock: full open/hold/close
  cycle, the motor never runs past the cap, debounce, sensor hysteresis, both close strategies.
- `tools/bringup_*.py` stay as the on-hardware scripts (updated for the new pin map and L9110S).
- Honest scope note: for ~400 lines a full suite is over-engineering. The injection seam costs
  nothing and is what makes the strategies clean; the tests worth writing are the safety-cap one and
  the state-machine one.

## Pin map v2 (ESP32-C6 GPIO in brackets)
| Signal | ToF config | IR config |
| --- | --- | --- |
| Motor IA (PWM) | D3 [21] | D3 [21] |
| Motor IB | D8 [19] | D8 [19] |
| I2C SDA / IR emitter | D4 [22] | D4 [22] → BC337 base |
| I2C SCL / IR receiver | D5 [23] | D5 [23] ← CHQ1838 OUT |
| Open button | D6 [16] | D6 [16] |
| Mode button | D7 [17] | D7 [17] |
| MP3 RXD (XIAO TX) | D9 [20] | D9 [20] |
| Status LED red | D10 [18] | D10 [18] |
| Status LED green | D0 [0] | D0 [0] |
| **free, ADC-capable** | **D1 [1], D2 [2]** | same |

Changes from v1 and why:
- **MP3 RX dropped.** The DFR0534 is command-only, so we don't read it. This frees a pin — and it
  avoids a real hazard: powered from the LiPo its TXD idles at 3.7–4.2 V and C6 pins are not 5 V
  tolerant. Leave it unconnected (or divide 10k/20k if we ever want replies).
- **Only GPIO0/1/2 have an ADC** on this chip, so D1/D2 are reserved for stall sensing. The map must
  not creep onto them.
- **Nothing sits on a strapping pin.** ESP32-C6 straps are GPIO4/5/8/9/15, and the XIAO's D8/D9/D10
  are GPIO19/20/18 — the trap this board invites, avoided.
- **GPIO16 (D6) is the ROM console TX**: the bootloader prints there on every reset. A button is
  harmless; the MP3 module must never go there or boot-log bytes would read as commands.

## Hardware follow-ups (now in SHOPPING.md)
100 nF across the motor brushes (brush arcing, not inductive kickback, is what upsets I2C and IR) ·
220 µF at the driver VCC · 470–1000 µF at the DFR0534 (audio thump → brownout is a classic) ·
100 Ω + 4.7 µF supply filter at the IR receiver (its datasheet requires it) · 10 kΩ pulldowns ·
1 Ω 0.5 W shunt if we do stall sensing · star ground at the driver's GND pin.
**Measure the real motor current** — the 70/230 mA figures come from patent literature, not your
motor. If it stalls above ~500 mA the L9110S has almost no margin and the driver choice changes.
