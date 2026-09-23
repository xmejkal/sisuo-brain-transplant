"""
Smart Bin — a Sisuo SS-01 sensor bin with a Seeed XIAO ESP32-C6 brain.

READ THIS FILE FIRST. It is the tour: what the parts are, how they are assembled, and what
happens when someone waves a hand at the bin. Every other module is one chapter of it.

===============================================================================================
FIVE LAYERS, AND THE RULE THAT DECIDES WHERE A THING LIVES
===============================================================================================

The distinction that matters, because the obvious question is "why is the motor `hardware` but
the sensor is not?": **a device is a thing you command; a strategy is a decision you make.**

  1. BOARD      board.py    facts about this chip: which pins can wake it, sleeping, the WDT
                config.py      every pin and tunable; /config.json holds per-unit calibration

  2. DEVICES    hardware.py    everything physical, constructed in one place and opinion-free:
                               the motor driver, the buttons, the LED, the MP3 module, the
                               rangefinder chip, the limit switch, the current sense.
                motor.py       MotorDriver  + L9110MotorDriver
                audio.py       Player       + Dfr0534Player / SilentPlayer
                buttons.py     Button
                status_led.py  StatusLed
                vl6180x.py     the rangefinder's registers

  3. STRATEGIES the decisions made *with* those devices — each one a config string:
                proximity.py     "is a hand there?"       ProximitySensor + four answers
                close_detection.py     "is the lid shut?"       CloseDetector   + three answers
                power.py       "what to do while idle?" PowerPolicy     + two answers
                assembly.py     picks which answer, from config

  4. BEHAVIOUR  states.py      the product as data: states, triggers, the transition table
                state_machine.py  walks that table, runs hooks, announces every move
                lid.py         the hooks, and the motor strokes they start
                events.py      the announcements; feedback.py turns them into light and sound

  5. APPLICATION
                smart_bin.py   three tasks, and the messages between them
                assembly.py    build() and run(): how one bin is put together
                __init__.py    this tour

So the rangefinder *chip* sits in layer 2 beside the motor, while "is that a hand?" sits in
layer 3 — because which judgement you want is a choice, and the chip is not. Each layer may use
the one below it and never the one above.

===============================================================================================
HOW THEY FIT TOGETHER
===============================================================================================

      buttons ─┐                                            ┌─► AudioFeedback ─► Player ─► 🔊
               ├─► SmartBin's tasks ─► trigger ─► StateMachine ─► LedFeedback   ─► LED
      sensor ──┘     (smart_bin.py)              (fsm.py)    └─► LogFeedback    ─► USB
                                                     │
                                                     │ enter/exit hooks
                                                     ▼
                                                  Lid (lid.py)
                                                     │ starts a stroke
                                                     ▼
                                             MotorDriver ─► the lid moves
                                                     │
                                            CloseDetector answers "shut yet?"

The arrows only ever point that way. The lid knows nothing about sound, LEDs or WiFi; feedback
cannot influence the lid; and what a trigger *means* is decided by the table in states.py rather
than by the code that fires it.

`SmartBin` holds one of each: the devices (`b.hardware`), the three strategies (`b.sensor`,
`b.close_detector`, `b.power_policy`), the behaviour (`b.lid`) and the listeners
(`b.listeners`). If you are unsure where something belongs, ask whether it *decides* anything.

===============================================================================================
WHAT HAPPENS WHEN SOMEONE WAVES
===============================================================================================

 1. `poll_sensor` (smart_bin.py) asks the sensor `hand_detected()`. The sensor debounces —
    several readings in a row, then a cooldown — so one wave is one answer.
 2. It fires HAND_DETECTED at the state machine.
 3. states.TRANSITIONS says IDLE + HAND_DETECTED -> OPENING, so the machine moves there and runs
    the lid's enter-hook for OPENING.
 4. The hook starts a stroke: drive the motor open, and watch three things — the hard safety cap
    (MOTOR_MAX_RUN_MS, checked first and always), the close detector, the calibrated run time.
 5. Entering OPENING also publishes "entered:opening", so the LED turns green and the MP3 module
    plays whatever the current sound profile maps that state to. The lid is not involved.
 6. The stroke ends and reports STROKE_FINISHED -> the machine moves to OPEN, which starts the
    hold timer. When it expires: CLOSING, and the same again in reverse.
 7. If something blocks the lid on the way down, the stroke reports SAFETY_CAP_TRIPPED, which in
    CLOSING means OBSTRUCTED: reopen, announce, retry. After MAX_CLOSE_RETRIES it latches FAULT
    and waits for a person — never the original bin's forever-retry.

===============================================================================================
BENCH
===============================================================================================

    >>> import smartbin
    >>> b = smartbin.build()            # constructs everything, starts NOTHING
    >>> b.hardware.scan_i2c()           # ['0x29'] when the ToF sensor is wired
    >>> b.hardware.motor.drive(True, 150); b.hardware.motor.stop()
    >>> b.sensor.read_distance_mm()
    >>> b.lid.fire("open_pressed")      # drive the machine by hand, with no sensor at all
    >>> b.lid.state, b.lid.history[-3:]

`build()` starts nothing and `run()` starts everything: that split is what makes the REPL useful.
With `aiorepl` installed it all works while the bin is running, where the bin is `b`.
"""

from .assembly import build, run

VERSION = "2.2.0-dev"

__all__ = ("build", "run", "VERSION")
