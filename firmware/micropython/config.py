"""
Every tunable in one file.

Two layers, on purpose:
  * the constants below are the design — documented, versioned, and the same on every unit;
  * `/config.json` on the device holds what is true of *this* bin only (calibrated run times,
    sensor offsets, the chosen sound profile). It is applied on top at import.

So calibrating on the bench is "edit numbers, soft reset" and git never fills up with
calibration churn.

Pin numbers are ESP32-S3 GPIO numbers. The FireBeetle's D-labels are in the comments; they are
not the same numbers — D9 is GPIO0 and D13 is GPIO21 — which is the single easiest mistake to
make on this board. The authority for that map is `boards/firebeetle2-esp32s3.json`, reaching
the firmware through the generated `smartbin/board_spec.py`.
"""

import json

# ----------------------------------------------------------------- which parts are fitted
# The bin runs on a battery, so it sleeps. Deep sleep only works with "tof_interrupt": the
# sensor has to keep ranging and assert its interrupt pin while the chip is off, because a
# sleeping chip cannot poll an I2C bus. The two settings therefore move together.
#
# Both are calibratable, so bench work over USB is a /config.json away and needs no edit here:
#   {"POWER_POLICY": "always_on", "SENSOR_STRATEGY": "tof"}
SENSOR_STRATEGY = "tof_interrupt"   # "tof" (polled I2C) | "tof_interrupt" (the sensor watches by
                            #   itself and can wake the chip) | "ir" | "none" (buttons only)
POWER_POLICY = "deep_sleep"  # "always_on" (bench, USB) | "deep_sleep" (battery)
CLOSE_DETECTOR = "timed"    # "timed" | "limit" (microswitch) | "stall" (shunt + ADC)

# Which audio hardware is fitted. THIS IS A CHOICE OF BOARD, not a preference:
#   "i2s"      DFR0954 MAX98357A amplifier, the ESP32 synthesises the tones. Needs the v4
#              board (board.tsx): three I2S pins on SCK/MO/MI and shutdown on D3.
#   "dfr0534"  DFRobot DFR0534, clips in the module's own flash, one UART line. Needs the v3
#              board (board-v3-dfr0534.tsx): a 6-way header and D3 carrying serial.
# Selecting one the board does not have gets you silence and no error, which is why
# `assembly.build_player` checks the pins exist rather than trusting this line.
AUDIO_STRATEGY = "i2s"
AUDIO_ENABLED = True
REPL_ENABLED = True         # live REPL via aiorepl while the bin runs
LOG_EVENTS = True

# ----------------------------------------------------------------- pins (GPIO, not D-numbers)
# On the ESP32-S3 almost every header pin can wake the chip (GPIO0-21 are RTC pins), so unlike
# the C6 — where three usable wake pins dictated the whole map — the pins here are spent on
# purpose. Three scarcities remain, and each one is honoured below:
#
#   * ADC1 is GPIO1-10 and nothing else. ADC2 exists but cannot be read while WiFi is on, so
#     A5 (GPIO11) is an analogue pin we may not use. Only the shunt needs an ADC, so it takes
#     A0 and the other analogue pins stay free.
#   * D3 (GPIO38), D14 (GPIO47), TX and RX are outside the RTC domain and cannot wake the chip.
#     They are therefore given to things that never need to: the amplifier's shutdown line and
#     the MODE button.
#   * D9 (GPIO0) is the BOOT strap and D2 (GPIO3) the JTAG strap. Nothing is put on either —
#     a button on GPIO0 would drop the board into the bootloader if held during a reset.
#
# The two that must wake the bin — the ToF interrupt and the OPEN button — take D12 and D11,
# which are RTC-capable but NOT on ADC1, so they cost us no analogue headroom.
PIN_TOF_INTERRUPT = 12      # D12 <- VL6180X GPIO1   [wake-capable]
PIN_BUTTON_OPEN = 13        # D11 to GND             [wake-capable]
PIN_SHUNT_ADC = 4           # A0  stall sense, or PIN_LIMIT_SWITCH — the one ADC1 pin we spend
PIN_LIMIT_SWITCH = 4        # A0  (alternative use of the same pin)
PIN_MOTOR_IA = 14           # D10 -> L9110S A-IA
PIN_MOTOR_IB = 18           # D6  -> L9110S A-IB
PIN_I2C_SDA = 1             # SDA (ToF config) — the board's dedicated I2C pins
PIN_I2C_SCL = 2             # SCL (ToF config)
PIN_IR_EMITTER = 1          # SDA (IR config) -> BC337 base
PIN_IR_RECEIVER = 2         # SCL (IR config) <- receiver OUT
PIN_BUTTON_MODE = 47        # D14 — cannot wake, and does not need to. This is also the on-board
                            #   user button, so the board's own button works as MODE on the bench.
# I2S to the MAX98357A amplifier. The three SPI pads, spent here because this design has no
# SPI and they are the cheapest pins left — which frees A1/GPIO5, an ADC1 pin.
PIN_I2S_BCLK = 17           # SCK -> bit clock
PIN_I2S_LRC = 15            # MO  -> word select (left/right). The pad reads MO; the vendor's
                            #   header calls the same GPIO MOSI.
PIN_I2S_DIN = 16            # MI  -> serial data into the amplifier
PIN_AUDIO_SD = 38           # D3  -> shutdown. LOW shuts the amplifier down to 0.6 uA; merely
                            #   stopping the clock leaves it in standby at 340 uA, five hundred
                            #   times more. Must be DRIVEN — the module pulls it up, and
                            #   floating selects a channel rather than turning anything off.
PIN_LED_RED = 9             # D7
PIN_LED_GREEN = 7           # D5

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

# Raw ADC counts at stall, across the board's 0.1 ohm shunt, read at 0 dB attenuation
# (~0.95 V full scale, 16-bit). The conversion, so the number can be derived from any
# measurement rather than guessed:
#
#     counts = amps * SHUNT_OHMS * 65535 / ADC_FULL_SCALE_V   ->   about 6900 counts per amp
#
# so 0.25 A is ~1700 counts, 1 A is ~6900, and 2 A is ~13800 — the whole plausible range fits
# inside the ADC's span with room to spare, which is the reason for the 0 dB setting. At the
# previous 0.33 ohm and 11 dB, a 2 A stall would have put 660 mV of lift on the driver's ground
# reference; at 0.1 ohm it is 200 mV.
#
# UNCALIBRATED. This value is a placeholder chosen to sit above a plausible running current and
# below a plausible stall, and it is the reason CLOSE_DETECTOR defaults to "timed" rather than
# "stall". Measure the real motor with tools/calibrate.py before switching the detector over.
SHUNT_OHMS = 0.1
ADC_FULL_SCALE_V = 0.95
STALL_COUNTS = 4000
STALL_BLANKING_MS = 200     # ignore start-up inrush
STALL_SAMPLES = 8           # ADC reads averaged per check
STALL_CONSECUTIVE_HITS = 3  # checks above the threshold before believing it

# ----------------------------------------------------------------- audio
VOLUME = 22                 # 0-30
ACTIVE_PROFILE = "default"

# Sound profiles map "state entered" -> a cue NAME from `audio.ALL_CUES`. An unmapped state is
# silence, so "silent" is simply empty. The MODE button cycles through these in order.
#
# These were bare integers until 2026-09-25, and the integer meant whatever the player in use
# happened to think it meant — a track in a module's flash, or an entry in a tone table. The
# same profile produced unrelated sounds depending on which player was built, and nothing could
# detect it. A name says what the bin is EXPRESSING; translating that into a track number or a
# frequency is the player's business and nobody else's.
SOUND_PROFILES = {
    "default": {
        "opening": "open-start", "idle": "settled",
        "obstructed": "blocked", "fault": "fault",
    },
    "chatty": {
        "opening": "open-start-bright", "open": "open-reached", "closing": "close-start",
        "idle": "settled", "obstructed": "blocked", "fault": "fault",
    },
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
I2S_ID = 0                  # which I2S peripheral. The S3 has two; nothing else uses either.
I2S_BUFFER_BYTES = 4096     # the driver's ring buffer. Must exceed the longest cue's samples
                            #   (cue 8 is 400 ms at 16 kHz mono 16-bit = 12.8 KB, so a cue
                            #   larger than this buffer simply takes more than one drain —
                            #   which is fine, because rendering happens in its own task).
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

# Keys whose value must be one of a fixed set, not merely a non-empty string.
#
# Without this a single typo in /config.json is a silent product change. `{"SENSOR_STRATEGY":
# "tof-interrupt"}` — a hyphen where the code has an underscore — passes the (str, None, None)
# check, reaches `build_sensor`, does not match, logs one line and falls back to buttons only.
# The bin then deep-sleeps happily and opens only when pressed. On a deployed unit with nothing
# attached to the serial port, the product has quietly become a different product and the only
# evidence is a log line nobody will ever read.
#
# `tests/test_assembly.py` proves these agree with the implementations that dispatch on them, so
# adding a strategy without listing it here fails the build rather than the bin.
ALLOWED_VALUES = {
    "SENSOR_STRATEGY": ("tof", "tof_interrupt", "ir", "none"),
    "CLOSE_DETECTOR": ("timed", "limit", "stall"),
    "POWER_POLICY": ("always_on", "deep_sleep"),
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
        if not isinstance(value, str) or not value:
            return False
        allowed = ALLOWED_VALUES.get(key)
        return allowed is None or value in allowed
    if isinstance(value, bool) or not isinstance(value, int):
        return False
    return minimum <= value <= maximum


def relation_problems(settings=None):
    """
    Settings that are each individually legal but wrong together.

    Per-key bounds cannot see these. `TOF_FAR_MM = 0` is a legal distance and passes (int, 0,
    255); it also makes `near < d < far` unsatisfiable, so the bin never sees a hand again and
    reports nothing. Same silent-different-product failure as an unknown strategy, through a
    different door.
    """
    source = settings if settings is not None else globals()
    get = source.get if hasattr(source, "get") else lambda key, default=None: source[key]

    problems = []
    near, far = get("TOF_NEAR_MM"), get("TOF_FAR_MM")
    if isinstance(near, int) and isinstance(far, int) and near >= far:
        problems.append(
            "TOF_NEAR_MM (%d) must be below TOF_FAR_MM (%d), or no distance is ever a hand"
            % (near, far))

    profile = get("ACTIVE_PROFILE")
    profiles = get("SOUND_PROFILES") or {}
    if profile is not None and profiles and profile not in profiles:
        problems.append(
            "ACTIVE_PROFILE %r is not one of %s, so the bin would be silent"
            % (profile, ", ".join(sorted(profiles))))
    return problems


_OVERLAY = _load_overlay()

for _problem in relation_problems():
    print("W config: %s" % _problem)


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
