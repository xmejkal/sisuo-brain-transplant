"""
Smart Bin firmware — a Sisuo SS-01 sensor bin with a Seeed XIAO ESP32-C6 brain.

Two entry points, and the difference between them is the whole bench workflow:

    build()   constructs every object and starts NOTHING. Safe to call at the REPL.
    run()     builds, then runs the event loop. Only main.py calls this.

So on the bench:

    >>> import smartbin
    >>> b = smartbin.build()
    >>> b.hw.scan_i2c()            # ['0x29'] if the ToF sensor is wired
    >>> b.hw.motor.drive(True, 150); b.hw.motor.stop()
    >>> b.sensor.read()            # distance in mm
    >>> b.lid.fire("open_pressed") # drive the state machine by hand
    >>> b.lid.state, b.lid.history[-3:]

and in production, main.py calls run() and `aiorepl` keeps all of the above available live.
"""

try:
    import asyncio
except ImportError:
    import uasyncio as asyncio

import config as _default_config

from . import app, closing, log, power, sensors

VERSION = "2.0.0-dev"


def build(config=_default_config, hardware=None):
    """
    Construct the whole bin: hardware, the chosen strategies, the lid and its listeners.

    `hardware` can be supplied to run the logic against fakes; otherwise the real peripherals are
    constructed from the pin numbers in config.
    """
    from .events import EventBus

    if hardware is None:
        from .hw import Hardware

        hardware = Hardware(config)

    bus = EventBus()
    sensor = _build_sensor(config, hardware)
    close_detector = _build_close_detector(config, hardware)
    return app.SmartBin(hardware, config, bus, sensor, close_detector, power.build(config))


def _build_sensor(config, hardware):
    """The strategy choice, in one place. Adding a sensor type means one branch here."""
    common = {
        "consecutive": config.SENSOR_CONSECUTIVE,
        "cooldown_ms": config.SENSOR_COOLDOWN_MS,
    }

    if config.SENSOR in ("tof", "tof_interrupt"):
        from .vl6180x import VL6180X

        driver = VL6180X(hardware.i2c, offset=config.TOF_OFFSET_MM)
        if config.TOF_CROSSTALK:
            driver.crosstalk = config.TOF_CROSSTALK
        if config.TOF_RANGE_IGNORE:
            driver.set_range_ignore(config.TOF_RANGE_IGNORE)
        if config.SENSOR == "tof_interrupt":
            return sensors.TofInterruptSensor(
                driver,
                hardware.tof_interrupt,
                period_ms=config.TOF_INTERRUPT_PERIOD_MS,
                active_high=config.TOF_INTERRUPT_ACTIVE_HIGH,
                near_mm=config.TOF_NEAR_MM,
                far_mm=config.TOF_FAR_MM,
                **common
            )
        return sensors.TofSensor(
            driver, near_mm=config.TOF_NEAR_MM, far_mm=config.TOF_FAR_MM, **common
        )

    if config.SENSOR == "ir":
        return sensors.IrBurstSensor(
            hardware.ir_emitter,
            hardware.ir_receiver,
            burst_us=config.IR_BURST_US,
            carrier_hz=config.IR_CARRIER_HZ,
            **common
        )

    log.warn("no proximity sensor configured; buttons only")
    return sensors.ButtonOnlySensor(**common)


def _build_close_detector(config, hardware):
    if config.CLOSE_DETECT == "limit":
        return closing.LimitSwitchCloseDetector(hardware.limit_switch)
    if config.CLOSE_DETECT == "stall":
        return closing.StallCloseDetector(
            hardware.shunt_adc, config.STALL_COUNTS, blanking_ms=config.STALL_BLANKING_MS
        )
    return closing.TimedCloseDetector(config.LID_CLOSE_RUN_MS)


def run(config=_default_config):
    """Production entry point. The motor is stopped on every way out of here."""
    bin_ = build(config)
    log.info("smartbin %s starting", VERSION)
    try:
        asyncio.run(bin_.main())
    except KeyboardInterrupt:
        log.info("interrupted")
    finally:
        bin_.hw.all_off()
