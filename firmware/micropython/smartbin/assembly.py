"""
How a bin is put together: the composition root.

`build()` assembles one and starts nothing; `run()` starts it. Everything they decide is in this
file, so "how is this bin assembled?" has exactly one answer.

A strategy is a decision the bin makes with the devices `hardware.py` provides — "is that a
hand?", "is the lid shut?", "should we sleep?". The devices themselves are not built here; this
file only chooses which judgement to apply to them.

All the "which implementation" choices live here, so adding one means editing one function in
one file, and `smartbin/__init__.py` stays the tour it advertises.

Every choice fails loudly on an unknown name rather than silently degrading, because a typo in
config that quietly disables the sensor is a bin that looks broken for no visible reason.
"""

import config as _default_config

from . import close_detection, feedback, log, power, proximity
from .events import EventBus
from .smart_bin import SmartBin

try:
    import asyncio
except ImportError:
    import uasyncio as asyncio


def build(config=_default_config, hardware=None):
    """
    Assemble the bin from the configuration, and start nothing.

    Read top to bottom, this is the whole product: devices, then the three decisions that depend
    on which parts are fitted, then the things that react, then the object that runs it.

    `hardware` can be supplied to run the logic against fakes; otherwise the real devices are
    constructed from the pin numbers in config.py.
    """
    if hardware is None:
        from .hardware import Hardware

        hardware = Hardware(config)

    return SmartBin(
        hardware=hardware,
        config=config,
        bus=EventBus(),
        sensor=build_sensor(config, hardware),                  # how a hand is noticed
        close_detector=build_close_detector(config, hardware),  # how "shut" is known
        power_policy=build_power_policy(config),                # what idling costs
        listeners=build_feedback_listeners(config, hardware),   # what reacts, without deciding
        save_setting=config.save,  # how the MODE button remembers its choice
    )


def run(config=_default_config):
    """
    Build the bin and run it. The only caller is main.py.

    Whatever happens — a crash, Ctrl-C, a cancelled task — the hardware is left safe on the way
    out. That `finally` is the last line of defence behind the safety cap inside every stroke.
    """
    smart_bin = build(config)
    log.info("smartbin starting")
    try:
        asyncio.run(smart_bin.main())
    except KeyboardInterrupt:
        log.info("interrupted")
    finally:
        smart_bin.hardware.enter_safe_state()


def build_sensor(config, hardware):
    """The proximity sensor named by `config.SENSOR_STRATEGY`."""
    debounce = {
        "consecutive_hits": config.SENSOR_CONSECUTIVE_HITS,
        "cooldown_ms": config.SENSOR_COOLDOWN_MS,
    }
    strategy = config.SENSOR_STRATEGY

    if strategy in ("tof", "tof_interrupt"):
        if strategy == "tof_interrupt":
            return proximity.SelfRangingTimeOfFlightSensor(
                hardware.rangefinder,
                hardware.rangefinder_interrupt,
                period_ms=config.TOF_INTERRUPT_PERIOD_MS,
                interrupt_active_high=config.WAKE_ON_HIGH,
                near_mm=config.TOF_NEAR_MM,
                far_mm=config.TOF_FAR_MM,
                max_failures=config.TOF_MAX_FAILURES,
                **debounce
            )
        return proximity.TimeOfFlightSensor(
            hardware.rangefinder,
            near_mm=config.TOF_NEAR_MM,
            far_mm=config.TOF_FAR_MM,
            max_failures=config.TOF_MAX_FAILURES,
            **debounce
        )

    if strategy == "ir":
        return proximity.InfraredBurstSensor(
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
    return proximity.ButtonOnlySensor(**debounce)


def build_close_detector(config, hardware):
    """The close detector named by `config.CLOSE_DETECTOR`."""
    choice = config.CLOSE_DETECTOR

    if choice == "limit":
        return close_detection.LimitSwitchCloseDetector(hardware.limit_switch)

    if choice == "stall":
        return close_detection.MotorStallCloseDetector(
            hardware.current_sense,
            config.STALL_COUNTS,
            blanking_ms=config.STALL_BLANKING_MS,
            samples=config.STALL_SAMPLES,
            consecutive_hits=config.STALL_CONSECUTIVE_HITS,
        )

    if choice != "timed":
        log.error("unknown CLOSE_DETECTOR %r; falling back to timed", choice)
    return close_detection.TimedCloseDetector(config.LID_CLOSE_RUN_MS)


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
