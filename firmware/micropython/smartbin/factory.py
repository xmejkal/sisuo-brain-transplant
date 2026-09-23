"""
Wiring: config strings in, constructed objects out.

All the "which implementation" decisions live here, so adding a strategy means one entry in one
table in this file, and `smartbin/__init__.py` stays the two-entry-point module it advertises.

Every choice fails loudly on an unknown name rather than silently degrading, because a typo in
config that quietly disables the sensor is a bin that looks broken for no visible reason.
"""

from . import closing, feedback, log, power, sensors


def build_sensor(config, hardware):
    """The proximity sensor named by `config.SENSOR_STRATEGY`."""
    debounce = {
        "consecutive_hits": config.SENSOR_CONSECUTIVE_HITS,
        "cooldown_ms": config.SENSOR_COOLDOWN_MS,
    }
    strategy = config.SENSOR_STRATEGY

    if strategy in ("tof", "tof_interrupt"):
        driver = _build_tof_driver(config, hardware)
        if strategy == "tof_interrupt":
            return sensors.SelfRangingTimeOfFlightSensor(
                driver,
                hardware.tof_interrupt,
                period_ms=config.TOF_INTERRUPT_PERIOD_MS,
                interrupt_active_high=config.WAKE_ON_HIGH,
                near_mm=config.TOF_NEAR_MM,
                far_mm=config.TOF_FAR_MM,
                max_failures=config.TOF_MAX_FAILURES,
                **debounce
            )
        return sensors.TimeOfFlightSensor(
            driver,
            near_mm=config.TOF_NEAR_MM,
            far_mm=config.TOF_FAR_MM,
            max_failures=config.TOF_MAX_FAILURES,
            **debounce
        )

    if strategy == "ir":
        return sensors.InfraredBurstSensor(
            hardware.ir_emitter,
            hardware.ir_receiver,
            burst_us=config.IR_BURST_US,
            carrier_hz=config.IR_CARRIER_HZ,
            **debounce
        )

    if strategy != "none":
        log.error("unknown SENSOR_STRATEGY %r; falling back to buttons only", strategy)
    else:
        log.info("no proximity sensor fitted; buttons only")
    return sensors.ButtonOnlySensor(**debounce)


def _build_tof_driver(config, hardware):
    """The VL6180X itself, with any calibration this particular bin has been given."""
    from .vl6180x import VL6180X

    driver = VL6180X(hardware.sensor_bus, offset=config.TOF_OFFSET_MM)
    if config.TOF_CROSSTALK:
        driver.crosstalk = config.TOF_CROSSTALK
    if config.TOF_RANGE_IGNORE:
        driver.set_range_ignore(config.TOF_RANGE_IGNORE)
    return driver


def build_close_detector(config, hardware):
    """The close detector named by `config.CLOSE_DETECTOR`."""
    choice = config.CLOSE_DETECTOR

    if choice == "limit":
        return closing.LimitSwitchCloseDetector(hardware.limit_switch)

    if choice == "stall":
        return closing.MotorStallCloseDetector(
            hardware.shunt_adc,
            config.STALL_COUNTS,
            blanking_ms=config.STALL_BLANKING_MS,
            samples=config.STALL_SAMPLES,
            consecutive_hits=config.STALL_CONSECUTIVE_HITS,
        )

    if choice != "timed":
        log.error("unknown CLOSE_DETECTOR %r; falling back to timed", choice)
    return closing.TimedCloseDetector(config.LID_CLOSE_RUN_MS)


def build_power_policy(config):
    """The power policy named by `config.POWER_POLICY`."""
    return power.build_policy(config)


def build_feedback_listeners(config, hardware):
    """
    Everything that reacts to a state change for a person's benefit.

    Built here rather than inside the application so that adding one — a notifier, a counter, a
    different kind of player — is a line in this list and nothing else.
    """
    listeners = [
        feedback.AudioFeedback(
            hardware.player, config.SOUND_PROFILES, config.ACTIVE_PROFILE, config.VOLUME
        ),
        feedback.LedFeedback(hardware.led, feedback.DEFAULT_LED_COLOURS),
    ]
    if config.LOG_EVENTS:
        listeners.append(feedback.LogFeedback())
    return listeners
