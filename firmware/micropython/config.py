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
SENSOR = "tof"              # "tof" (polled I2C) | "tof_interrupt" (sensor watches, can wake the
                            #   chip from deep sleep) | "ir" | "none" (buttons only)
POWER = "always_on"         # "always_on" (bench, USB) | "deep_sleep" (battery)
CLOSE_DETECT = "timed"      # "timed" | "limit" (microswitch) | "stall" (shunt + ADC)
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
LID_OPEN_HOLD_MS = 4000
MOTOR_MAX_RUN_MS = 1500     # hard safety cap; must exceed both run times with margin
MAX_CLOSE_RETRIES = 3       # obstructed this many times -> FAULT, rather than retrying forever
MOTION_POLL_MS = 10

# ----------------------------------------------------------------- sensing
SENSOR_POLL_MS = 60         # ~16 Hz; comfortably inside the VL6180X's measurement rate
BUTTON_POLL_MS = 20
BUTTON_DEBOUNCE_MS = 40
SENSOR_CONSECUTIVE = 2      # detections in a row before the lid reacts
SENSOR_COOLDOWN_MS = 1500   # ignore the sensor for this long after acting

TOF_INTERRUPT_PERIOD_MS = 500   # how often the sensor ranges by itself while the chip sleeps;
                                # ~340 uA at 500 ms, ~170 uA at 1000 ms, max 2550
TOF_INTERRUPT_ACTIVE_HIGH = True  # low-level wake has an open MicroPython bug on the C6
TOF_NEAR_MM = 30            # below this is the lid or a dirty window, not a hand
TOF_FAR_MM = 100            # the datasheet guarantees 100 mm; do not raise this hopefully
TOF_OFFSET_MM = None        # from the offset calibration, once mounted behind the window
TOF_CROSSTALK = None        # 9.7 fixed point, from the crosstalk calibration
TOF_RANGE_IGNORE = None     # >= 1.2x crosstalk; stops the window reading as a hand

IR_CARRIER_HZ = 38000
IR_BURST_US = 600

STALL_COUNTS = 12000        # raw ADC counts at stall; measure with bringup/07_stall.py
STALL_BLANKING_MS = 200     # ignore start-up inrush

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

# ----------------------------------------------------------------- housekeeping
I2C_FREQ_HZ = 400000
MP3_UART_ID = 1
MP3_BAUD = 9600
FAULT_BLINK_MS = 400
WATCHDOG_MS = 8000          # 0 disables. Started only by run(), never by build().
WATCHDOG_FEED_MS = 2000

OVERLAY_PATH = "/config.json"


def _apply_overlay():
    """Let /config.json override any constant above. Missing or broken file: keep the defaults."""
    try:
        with open(OVERLAY_PATH) as overlay_file:
            overlay = json.load(overlay_file)
    except (OSError, ValueError):
        return {}

    globals_dict = globals()
    for key, value in overlay.items():
        if key in globals_dict:
            globals_dict[key] = value
    return overlay


_OVERLAY = _apply_overlay()


def save(values):
    """
    Persist calibration or a setting choice to /config.json, merging with what is there.

    Used by the MODE button to remember the sound profile, and by the bench calibration helpers.
    """
    _OVERLAY.update(values)
    globals().update(values)
    try:
        with open(OVERLAY_PATH, "w") as overlay_file:
            json.dump(_OVERLAY, overlay_file)
        return True
    except OSError as exception:
        print("could not save config:", exception)
        return False
