"""
Smart Bin — a Sisuo SS-01 sensor bin with a Seeed XIAO ESP32-C6 brain.

READ THIS FILE FIRST. It is the tour: what the parts are, how they are assembled, and what
happens when someone waves a hand at the bin. Every other module is one chapter of it.

===============================================================================================
WHAT THE PARTS ARE
===============================================================================================

    hardware.py    the peripherals: motor pins, buttons, LED, I2C bus, MP3 UART
    platform.py    facts about this chip: which pins can wake it, how to sleep, the watchdog

    sensors.py     "is a hand there?"          ProximitySensor  + four implementations
    closing.py     "is the lid shut?"          CloseDetector    + three implementations
    power.py       "what to do while idle?"    PowerPolicy      + stay awake / deep sleep
    motor.py       "drive the lid"             MotorDriver      + the L9110S we use
    audio.py       "make a noise"              Player           + the DFR0534 we use

    states.py      the behaviour, as data: states, triggers, and the transition table
    fsm.py         the machine that walks that table and announces every move
    lid.py         the hooks it calls, and the motor strokes they start
    events.py      the announcements; feedback.py listens and lights LEDs / plays cues

    factory.py     turns config strings into the objects above
    smart_bin.py   the running application: three tasks, and the wiring between them
    config.py      every tunable and every pin, with /config.json holding per-unit calibration

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

import config as _default_config

from . import factory, log
from .events import EventBus
from .smart_bin import SmartBin

try:
    import asyncio
except ImportError:
    import uasyncio as asyncio

VERSION = "2.1.0-dev"


def build(config=_default_config, hardware=None):
    """
    Assemble the bin from the configuration, and start nothing.

    Read top to bottom, this is the whole product: peripherals, then the three decisions that
    depend on which parts are fitted, then the things that react, then the object that runs it.

    `hardware` can be supplied to run the logic against fakes; otherwise the real peripherals
    are constructed from the pin numbers in config.py.
    """
    if hardware is None:
        from .hardware import Hardware

        hardware = Hardware(config)

    # The three swappable decisions. Each is one config string; factory.py holds the choices.
    sensor = factory.build_sensor(config, hardware)              # how a hand is noticed
    close_detector = factory.build_close_detector(config, hardware)  # how "shut" is known
    power_policy = factory.build_power_policy(config)            # what idling costs

    # Everything that reacts to the lid without being able to affect it.
    listeners = factory.build_feedback_listeners(config, hardware)

    return SmartBin(
        hardware=hardware,
        config=config,
        bus=EventBus(),
        sensor=sensor,
        close_detector=close_detector,
        power_policy=power_policy,
        listeners=listeners,
        save_setting=config.save,   # how the MODE button remembers its choice
    )


def run(config=_default_config):
    """
    Build the bin and run it. The only caller is main.py.

    Whatever happens — a crash, Ctrl-C, a cancelled task — the hardware is left safe on the way
    out. That `finally` is the last line of defence behind the safety cap inside every stroke.
    """
    smart_bin = build(config)
    log.info("smartbin %s starting", VERSION)
    try:
        asyncio.run(smart_bin.main())
    except KeyboardInterrupt:
        log.info("interrupted")
    finally:
        smart_bin.hardware.enter_safe_state()
