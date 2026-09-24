"""
Every tunable in one file.

Two layers, on purpose:
  * the constants below are the design — documented, versioned, and the same on every unit;
  * `/config.json` on the device holds what is true of *this* bin only (calibrated run times,
    sensor offsets, the chosen sound profile). It is applied on top at import.

So calibrating on the bench is "edit numbers, soft reset" and git never fills up with
calibration churn.

Pin numbers are ESP32-C6 GPIO numbers. The XIAO's D-labels are in the comments; they are not the
same numbers, which is the single easiest mistake to make on this board.
"""

import json

# ----------------------------------------------------------------- which parts are fitted
SENSOR_STRATEGY = "tof"     # "tof" (polled I2C) | "tof_interrupt" (the sensor watches by itself
                            #   and can wake the chip) | "ir" | "none" (buttons only)
POWER_POLICY = "always_on"  # "always_on" (bench, USB) | "deep_sleep" (battery)
CLOSE_DETECTOR = "timed"    # "timed" | "limit" (microswitch) | "stall" (shunt + ADC)
AUDIO_ENABLED = True
REPL_ENABLED = True         # live REPL via aiorepl while the bin runs
LOG_EVENTS = True

# ----------------------------------------------------------------- pins (GPIO, not D-numbers)
# Only GPIO0-7 can wake an ESP32-C6 from deep sleep, and on the XIAO that is D0, D1 and D2 and
# nothing else. Those three are therefore spent on the things that must wake the bin (the ToF
# interrupt and the OPEN button) plus the one analogue input we may want (stall sensing).
PIN_TOF_INTERRUPT = 0       # D0  <- VL6180X GPIO1   [wake-capable]
PIN_BUTTON_OPEN = 1         # D1  to GND             [wake-capable]
PIN_SHUNT_ADC = 2           # D2  stall sense, or PIN_LIMIT_SWITCH — ADC-capable
PIN_LIMIT_SWITCH = 2        # D2  (alternative use of the same pin)
PIN_MOTOR_IA = 21           # D3  -> L9110S A-IA
PIN_I2C_SDA = 22            # D4  (ToF config)
PIN_I2C_SCL = 23            # D5  (ToF config)
PIN_IR_EMITTER = 22         # D4  (IR config) -> BC337 base
PIN_IR_RECEIVER = 23        # D5  (IR config) <- receiver OUT
PIN_BUTTON_MODE = 16        # D6  (also the ROM console TX; fine for a button, never for the MP3)
PIN_LED_RED = 17            # D7
PIN_MOTOR_IB = 19           # D8  -> L9110S A-IB
PIN_MP3_TX = 20             # D9  -> module RXD. The module's TXD stays unwired.
PIN_LED_GREEN = 18          # D10

# ----------------------------------------------------------------- motion (CALIBRATE THESE)
MOTOR_OPEN_SPEED = 220      # 0-255
MOTOR_CLOSE_SPEED = 200
MOTOR_PWM_FREQ_HZ = 5000    # the L9110's bipolar output stage just heats up above ~10 kHz
LID_OPEN_RUN_MS = 900       # <- calibrate
LID_CLOSE_RUN_MS = 950      # <- calibrate
LID_OPEN_HOLD_MS = 4000     # how long the lid waits before closing
MAX_OPEN_MS = 30000         # ceiling on the total time held open, however much waving happens:
                            # without it, anything parked in front of the sensor keeps the lid
                            # open until the battery is flat
MOTOR_MAX_RUN_MS = 1500     # hard safety cap; must exceed both run times with margin
MAX_CLOSE_RETRIES = 3       # obstructed this many times -> FAULT, rather than retrying forever
MOTION_POLL_MS = 10

# ----------------------------------------------------------------- sensing
SENSOR_POLL_MS = 60         # ~16 Hz; comfortably inside the VL6180X's measurement rate
BUTTON_POLL_MS = 20
BUTTON_DEBOUNCE_MS = 40
SENSOR_CONSECUTIVE_HITS = 2  # detections in a row before the lid reacts
SENSOR_COOLDOWN_MS = 1500   # ignore the sensor for this long after acting

TOF_INTERRUPT_PERIOD_MS = 500   # how often the sensor ranges by itself while the chip sleeps;
                                # ~340 uA at 500 ms, ~170 uA at 1000 ms, max 2550
TOF_NEAR_MM = 30            # below this is the lid or a dirty window, not a hand
TOF_FAR_MM = 100            # the datasheet guarantees 100 mm; do not raise this hopefully
TOF_OFFSET_MM = None        # from the offset calibration, once mounted behind the window
TOF_CROSSTALK = None        # 9.7 fixed point, from the crosstalk calibration
TOF_RANGE_IGNORE = None     # >= 1.2x crosstalk; stops the window reading as a hand
TOF_MAX_FAILURES = 10       # unreadable this many times in a row -> the bin faults

IR_CARRIER_HZ = 38000
IR_BURST_US = 600

# Raw ADC counts at stall, across the board's 0.33 ohm shunt, read at 11 dB attenuation (~3.1 V
# full scale, 16-bit). The patent literature's ~230 mA stall is ~76 mV is ~1600 counts; running
# at ~70 mA is ~23 mV is ~490. The threshold sits between them.
#
# A starting point only: it MUST be measured on the real motor with tools/calibrate.py. If that
# motor's stall current is much higher than the literature's, this number changes and so might
# the driver — see STATUS.md.
STALL_COUNTS = 1000
STALL_BLANKING_MS = 200     # ignore start-up inrush
STALL_SAMPLES = 8           # ADC reads averaged per check (the C6's ADC is noisy)
STALL_CONSECUTIVE_HITS = 3  # checks above the threshold before believing it

# ----------------------------------------------------------------- audio
VOLUME = 22                 # 0-30
ACTIVE_PROFILE = "default"

# Sound profiles map "state entered" -> track number on the MP3 module. An unmapped state is
# silence, so "silent" is simply empty. The MODE button cycles through these in order.
SOUND_PROFILES = {
    "default": {"opening": 1, "idle": 2, "obstructed": 3, "fault": 8},
    "chatty": {"opening": 4, "open": 5, "closing": 6, "idle": 7, "obstructed": 3, "fault": 8},
    "silent": {},
}

# ----------------------------------------------------------------- power
IDLE_TICK_MS = 200          # how often the power policy gets a say
SLEEP_AFTER_MS = 30000      # idle this long -> deep sleep (deep_sleep policy only)
SLEEP_AFTER_FAULT_MS = 300000   # a faulted bin sleeps too, just later (5 min of visible red)

# All deep-sleep wake sources share one polarity, because the chip applies one level to all of
# them — so this follows the board, and the board wires both buttons to GND. A button that idles
# HIGH and goes LOW when pressed can only wake a chip that is waiting for a LOW, and the sensor's
# interrupt is configured to match.
#
# The cost is that low-level wake has an open MicroPython bug on this chip (#17334, "stuck pin"),
# which is a bench risk to check early. The alternative is rewiring both buttons to 3V3 with
# pull-downs and flipping this to True.
#
# Get this wrong in either direction and the bin never wakes, or wakes instantly forever. The
# firmware refuses to sleep when it detects the mismatch rather than bricking itself quietly —
# see power.DeepSleepPolicy.sleep_now.
WAKE_ON_HIGH = False
# This one setting decides the polarity for BOTH wake sources, because ext1 applies a single
# level to every pin in the mask. There used to be a second constant, TOF_INTERRUPT_ACTIVE_HIGH,
# which said True while this said False; nothing read it, so the contradiction sat here unnoticed.
# The sensor's interrupt polarity is not free to choose — it follows from this.

# ----------------------------------------------------------------- housekeeping
I2C_FREQ_HZ = 400000
MP3_UART_ID = 1
MP3_BAUD = 9600
FAULT_BLINK_MS = 400        # blink period while faulted
FAULT_IDLE_POLL_MS = 800    # how often the blinker checks whether a fault has appeared
# 0 disables. The watchdog cannot be stopped once started and survives Ctrl-C, so a board left
# at the REPL would reset every few seconds: keep it off by default and enable it in
# /config.json on the deployed bin.
WATCHDOG_MS = 0
WATCHDOG_FEED_MS = 2000

OVERLAY_PATH = "/config.json"
OVERLAY_TEMP_PATH = "/config.json.tmp"

# Only these may be overridden per unit, and only within these bounds. Everything else — pin
# numbers above all — is design, and a calibration file has no business repointing the motor.
#
# The bounds matter as much as the whitelist: a null or absurd value used to reach the lid's
# hold-timer arithmetic, raise inside a state-machine hook, and leave the lid open with nothing
# left to close it.
#
#   key: (type, minimum, maximum)   — strings and None-able keys use (type, None, None)
LIMITS = {
    "LID_OPEN_RUN_MS": (int, 50, 10000),
    "LID_CLOSE_RUN_MS": (int, 50, 10000),
    "LID_OPEN_HOLD_MS": (int, 500, 60000),
    "MAX_OPEN_MS": (int, 1000, 600000),
    "MOTOR_OPEN_SPEED": (int, 0, 255),
    "MOTOR_CLOSE_SPEED": (int, 0, 255),
    "TOF_NEAR_MM": (int, 0, 255),
    "TOF_FAR_MM": (int, 0, 255),
    "TOF_OFFSET_MM": (int, -128, 127),
    "TOF_CROSSTALK": (int, 0, 65535),
    "TOF_RANGE_IGNORE": (int, 0, 65535),
    "TOF_INTERRUPT_PERIOD_MS": (int, 10, 2550),
    "STALL_COUNTS": (int, 0, 65535),
    "STALL_BLANKING_MS": (int, 0, 5000),
    "SENSOR_CONSECUTIVE_HITS": (int, 1, 20),
    "SENSOR_COOLDOWN_MS": (int, 0, 60000),
    "VOLUME": (int, 0, 30),
    "SLEEP_AFTER_MS": (int, 1000, 3600000),
    "WATCHDOG_MS": (int, 0, 60000),
    "ACTIVE_PROFILE": (str, None, None),
    "SENSOR_STRATEGY": (str, None, None),
    "CLOSE_DETECTOR": (str, None, None),
    "POWER_POLICY": (str, None, None),
    "LOG_EVENTS": (bool, None, None),
}

CALIBRATABLE = (
    "LID_OPEN_RUN_MS", "LID_CLOSE_RUN_MS", "LID_OPEN_HOLD_MS", "MAX_OPEN_MS",
    "MOTOR_OPEN_SPEED", "MOTOR_CLOSE_SPEED",
    "TOF_NEAR_MM", "TOF_FAR_MM", "TOF_OFFSET_MM", "TOF_CROSSTALK", "TOF_RANGE_IGNORE",
    "TOF_INTERRUPT_PERIOD_MS",
    "STALL_COUNTS", "STALL_BLANKING_MS",
    "SENSOR_CONSECUTIVE_HITS", "SENSOR_COOLDOWN_MS",
    "ACTIVE_PROFILE", "VOLUME",
    "SENSOR_STRATEGY", "CLOSE_DETECTOR", "POWER_POLICY",
    "SLEEP_AFTER_MS", "WATCHDOG_MS", "LOG_EVENTS",
)


def _load_overlay():
    """
    Read /config.json and apply the keys it is allowed to change.

    A missing file is the normal case on a fresh board. A corrupt one is reported rather than
    silently ignored, because the alternative is a bin that quietly reverts to uncalibrated
    defaults and behaves oddly for reasons nobody can see.
    """
    try:
        with open(OVERLAY_PATH) as overlay_file:
            overlay = json.load(overlay_file)
    except OSError:
        return {}
    except ValueError as exception:
        print("W config: /config.json is corrupt, using defaults:", exception)
        return {}

    accepted = {}
    for key, value in overlay.items():
        if key not in CALIBRATABLE:
            print("W config: ignoring %s from /config.json (not calibratable)" % key)
            continue
        if not is_within_limits(key, value):
            print("W config: ignoring %s=%r from /config.json (out of range)" % (key, value))
            continue
        globals()[key] = value
        accepted[key] = value
    return accepted


def is_within_limits(key, value):
    """
    Would this value be safe to use?

    A calibration file is edited by hand and written by a bin that may lose power mid-write, so
    "the file said so" is not a good enough reason to drive a motor.
    """
    limit = LIMITS.get(key)
    if limit is None:
        return False
    expected_type, minimum, maximum = limit

    if expected_type is bool:
        return isinstance(value, bool)
    if expected_type is str:
        return isinstance(value, str) and len(value) > 0
    if isinstance(value, bool) or not isinstance(value, int):
        return False
    return minimum <= value <= maximum


_OVERLAY = _load_overlay()


def save(overrides):
    """
    Persist calibration or a setting choice to /config.json, merging with what is there.

    Written to a temporary file and renamed, so losing power mid-write cannot leave a *truncated*
    file. It can still lose the file entirely — see `_rename` — and the defaults in this file are
    the fallback when it does.
    """
    rejected = [key for key in overrides if not is_within_limits(key, overrides[key])]
    if rejected:
        print("W config: refusing to save (not calibratable, or out of range):", rejected)
        overrides = {k: v for k, v in overrides.items() if is_within_limits(k, v)}
    if not overrides:
        return False

    merged = dict(_OVERLAY)
    merged.update(overrides)
    try:
        with open(OVERLAY_TEMP_PATH, "w") as overlay_file:
            json.dump(merged, overlay_file)
        _rename(OVERLAY_TEMP_PATH, OVERLAY_PATH)
    except OSError as exception:
        print("E config: could not save:", exception)
        return False

    _OVERLAY.update(overrides)
    globals().update(overrides)
    return True


def forget(key):
    """Drop a calibrated value so the default in this file applies again after a restart."""
    if key not in _OVERLAY:
        return False
    merged = dict(_OVERLAY)
    del merged[key]
    try:
        with open(OVERLAY_TEMP_PATH, "w") as overlay_file:
            json.dump(merged, overlay_file)
        _rename(OVERLAY_TEMP_PATH, OVERLAY_PATH)
    except OSError as exception:
        print("E config: could not save:", exception)
        return False
    del _OVERLAY[key]
    print("I config: %s forgotten; restart to use the default" % key)
    return True


def calibration():
    """What this particular bin has been taught, as opposed to what the design says."""
    return dict(_OVERLAY)


def _rename(source, destination):
    """
    Replace `destination` with `source`.

    MicroPython's os.rename does not overwrite, so the old file has to go first — which leaves a
    window where a power loss takes the calibration with it. The window is one flash operation
    wide and the alternative needs a filesystem feature this port does not have, so it is
    accepted and stated rather than claimed away. The defaults in this file are always a safe
    fallback, which is what makes that acceptable.
    """
    import os

    try:
        os.remove(destination)
    except OSError:
        pass
    os.rename(source, destination)
