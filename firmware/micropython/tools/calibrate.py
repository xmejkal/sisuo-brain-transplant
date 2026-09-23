"""
Bench calibration, run on the device.

Deploy the firmware first, then:

    mpremote repl
    >>> import tools.calibrate as cal     # or paste this file's functions
    >>> cal.stroke_times(cal.bin())
    >>> cal.tof_offset(cal.bin())
    >>> cal.tof_crosstalk(cal.bin())

Every procedure prints what it measured and offers to store it in /config.json, so the numbers
survive a re-deploy. Nothing is saved without you saying yes.

The ToF procedures come from ST's datasheet and AN4545 and must be run **through the lid's
window, in the final assembly** — that is what they are measuring. Re-gluing the window
invalidates them. Background: parts/SENSOR_OPTIONS.md.
"""

import time

import config
import smartbin

WHITE_TARGET_DISTANCE_MM = 50    # ST's offset procedure: 88% reflectance target at 50 mm
BLACK_TARGET_DISTANCE_MM = 100   # ST's crosstalk procedure: 3% reflectance target at 100 mm
OFFSET_TOLERANCE_MM = 3          # within this, ST says no offset calibration is needed
CROSSTALK_FIXED_POINT_SCALE = 128    # the registers use 9.7 fixed point
RANGE_IGNORE_MARGIN = 1.2        # ST recommends at least 1.2x the measured crosstalk
SAMPLES = 10


def bin_():
    """A constructed bin that has started nothing. Kept short because you type it a lot."""
    return smartbin.build()


bin = bin_  # noqa: A001 - convenience at the REPL, where shadowing the builtin costs nothing


def _confirm_and_save(values):
    print("Save to /config.json?", values)
    answer = input("[y/N] ")
    if answer.strip().lower() not in ("y", "yes"):
        print("Not saved.")
        return False
    return config.save(values)


def _average_range(driver, samples=SAMPLES):
    readings = []
    for _ in range(samples):
        distance_mm = driver.range_or_none()
        if distance_mm is not None:
            readings.append(distance_mm)
        time.sleep_ms(50)
    if not readings:
        raise RuntimeError("no usable readings — is anything in front of the sensor?")
    return sum(readings) / len(readings)


# --------------------------------------------------------------------------- motion
def stroke_times(smart_bin, speed=None, step_ms=100, limit_ms=None):
    """
    Find how long the lid takes to open and to close.

    Drives in one direction in short bursts until you say it has finished travelling, then the
    other. Do this with the lid installed, and keep a hand clear of it.
    """
    motor = smart_bin.hardware.motor
    speed = speed or config.MOTOR_OPEN_SPEED
    limit_ms = limit_ms or config.MOTOR_MAX_RUN_MS

    measured = {}
    for opening, key in ((True, "LID_OPEN_RUN_MS"), (False, "LID_CLOSE_RUN_MS")):
        direction = "OPEN" if opening else "CLOSE"
        print("\n%s: pressing Enter runs the motor %d ms at a time." % (direction, step_ms))
        print("Type 'done' when the lid has finished travelling.")
        elapsed_ms = 0
        while elapsed_ms < limit_ms:
            if input("[Enter]/done> ").strip().lower() == "done":
                break
            motor.drive(opening, speed)
            time.sleep_ms(step_ms)
            motor.stop()
            elapsed_ms += step_ms
            print("  %d ms" % elapsed_ms)
        measured[key] = elapsed_ms
        print("%s took %d ms" % (direction, elapsed_ms))

    longest = max(measured.values())
    if longest >= config.MOTOR_MAX_RUN_MS:
        print("WARNING: a stroke reached the safety cap (%d ms). Raise MOTOR_MAX_RUN_MS above"
              % config.MOTOR_MAX_RUN_MS, longest, "or the lid will never complete a stroke.")
    return _confirm_and_save(measured)


def stall_counts(smart_bin, samples=20):
    """
    Read the shunt while the motor runs free and while you hold the lid, so `STALL_COUNTS` can
    sit between the two. Needs CLOSE_DETECTOR = "stall" so the ADC exists.
    """
    detector = smart_bin.close_detector
    if not hasattr(detector, "read_counts"):
        print("Set CLOSE_DETECTOR = 'stall' in config.py first.")
        return False

    motor = smart_bin.hardware.motor
    readings = {}
    for label in ("free-running", "stalled (hold the lid)"):
        input("Press Enter to measure %s> " % label)
        motor.drive(True, config.MOTOR_OPEN_SPEED)
        time.sleep_ms(config.STALL_BLANKING_MS)
        counts = [detector.read_counts() for _ in range(samples)]
        motor.stop()
        readings[label] = sum(counts) // len(counts)
        print("  %s: %d counts" % (label, readings[label]))

    midpoint = (readings["free-running"] + readings["stalled (hold the lid)"]) // 2
    print("Suggested STALL_COUNTS (midway):", midpoint)
    return _confirm_and_save({"STALL_COUNTS": midpoint})


# --------------------------------------------------------------------------- ToF sensor
def tof_offset(smart_bin):
    """
    ST's offset procedure: a white (88% reflectance) target at 50 mm from the *outside* of the
    window. Plain white paper is close enough.
    """
    driver = _driver_of(smart_bin)
    driver.offset = 0
    input("Place a white target %d mm from the window, then press Enter> "
          % WHITE_TARGET_DISTANCE_MM)

    average_mm = _average_range(driver)
    error_mm = WHITE_TARGET_DISTANCE_MM - average_mm
    print("Measured %.1f mm, error %.1f mm" % (average_mm, error_mm))

    if abs(error_mm) <= OFFSET_TOLERANCE_MM:
        print("Within +/-%d mm: no offset needed." % OFFSET_TOLERANCE_MM)
        return False
    return _confirm_and_save({"TOF_OFFSET_MM": int(round(error_mm))})


def tof_crosstalk(smart_bin):
    """
    ST's crosstalk procedure: a black (3% reflectance) target at 100 mm. Measures how much light
    the window itself reflects back — the thing that otherwise reads as a permanent hand.

    Also computes the range-ignore threshold, which is what actually suppresses that reflection.
    """
    driver = _driver_of(smart_bin)
    driver.crosstalk = 0
    input("Place a black target %d mm from the window, then press Enter> "
          % BLACK_TARGET_DISTANCE_MM)

    rates, ranges = [], []
    for _ in range(SAMPLES):
        distance_mm = driver.range_or_none()
        if distance_mm is None:
            continue
        ranges.append(distance_mm)
        rates.append(driver.return_rate)
        time.sleep_ms(50)

    if not ranges:
        print("No usable readings; check the target and the window.")
        return False

    average_range = sum(ranges) / len(ranges)
    average_rate = sum(rates) / len(rates)
    crosstalk = average_rate * (1 - average_range / BLACK_TARGET_DISTANCE_MM)
    crosstalk_fixed = int(round(crosstalk * CROSSTALK_FIXED_POINT_SCALE))
    range_ignore = int(round(crosstalk_fixed * RANGE_IGNORE_MARGIN))

    print("Average range %.1f mm, return rate %.1f -> crosstalk %.2f (%d fixed point)"
          % (average_range, average_rate, crosstalk, crosstalk_fixed))
    print("Range-ignore threshold (%.1fx):" % RANGE_IGNORE_MARGIN, range_ignore)
    return _confirm_and_save(
        {"TOF_CROSSTALK": crosstalk_fixed, "TOF_RANGE_IGNORE": range_ignore}
    )


def tof_window(smart_bin, seconds=20):
    """
    Watch live distances so you can choose TOF_NEAR_MM and TOF_FAR_MM by waving at the bin the
    way you actually would.
    """
    driver = _driver_of(smart_bin)
    print("Wave at the sensor. Note the range at a comfortable distance.")
    deadline = time.ticks_add(time.ticks_ms(), seconds * 1000)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        print("range:", driver.range_or_none())
        time.sleep_ms(200)


def _driver_of(smart_bin):
    driver = getattr(smart_bin.sensor, "_driver", None)
    if driver is None:
        raise RuntimeError("no ToF sensor in this configuration (SENSOR_STRATEGY = %r)"
                           % config.SENSOR_STRATEGY)
    return driver
