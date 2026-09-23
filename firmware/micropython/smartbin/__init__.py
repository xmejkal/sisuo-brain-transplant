"""
Smart Bin firmware — a Sisuo SS-01 sensor bin with a Seeed XIAO ESP32-C6 brain.

Two entry points, and the difference between them is the whole bench workflow:

    build()   constructs every object and starts NOTHING. Safe to call at the REPL.
    run()     builds, then runs the event loop. Only main.py calls this.

On the bench:

    >>> import smartbin
    >>> b = smartbin.build()
    >>> b.hardware.scan_i2c()          # ['0x29'] when the ToF sensor is wired
    >>> b.hardware.motor.drive(True, 150); b.hardware.motor.stop()
    >>> b.sensor.read_distance_mm()
    >>> b.lid.fire("open_pressed")     # drive the state machine with no sensor at all
    >>> b.lid.state, b.lid.history[-3:]

With `aiorepl` installed all of that also works while the bin is running, where it is `b`.

Which implementations get built is decided by config.py and wired in factory.py.
"""

import config as _default_config

from . import factory, log
from .app import SmartBin
from .events import EventBus

try:
    import asyncio
except ImportError:
    import uasyncio as asyncio

VERSION = "2.1.0-dev"


def build(config=_default_config, hardware=None):
    """
    Construct the whole bin: hardware, the chosen strategies, the lid and its listeners.

    `hardware` can be supplied to run the logic against fakes; otherwise the real peripherals are
    constructed from the pin numbers in config.
    """
    if hardware is None:
        from .hardware import Hardware

        hardware = Hardware(config)

    return SmartBin(
        hardware=hardware,
        config=config,
        bus=EventBus(),
        sensor=factory.build_sensor(config, hardware),
        close_detector=factory.build_close_detector(config, hardware),
        power_policy=factory.build_power_policy(config),
        listeners=factory.build_feedback_listeners(config, hardware),
        save_setting=config.save,
    )


def run(config=_default_config):
    """Production entry point. Everything is left in a safe state on every way out of here."""
    smart_bin = build(config)
    log.info("smartbin %s starting", VERSION)
    try:
        asyncio.run(smart_bin.main())
    except KeyboardInterrupt:
        log.info("interrupted")
    finally:
        smart_bin.hardware.enter_safe_state()
