"""
The event bus: how the lid tells the rest of the firmware what just happened.

The lid knows nothing about sound, LEDs or logging. It changes state; the state machine publishes
one event per transition; listeners react. Adding a reaction (a second LED, a network
notification, a spoken phrase) means writing a listener — never editing the lid.

A listener is any callable `listener(event, **data)`. A listener that raises is logged and
disabled-in-place rather than allowed to break the lid: feedback must never take the bin down.
"""

from . import log

# Events that are not state transitions. Transition events are named by the state entered,
# via `entered()` below, so states and events share one vocabulary.
MODE_CHANGED = "mode_changed"
SENSOR_FAILED = "sensor_failed"
SENSOR_RECOVERED = "sensor_recovered"
LOW_BATTERY = "low_battery"


def entered(state):
    """The event published when `state` is entered. Keeps one vocabulary for states and events."""
    return "entered:" + state


class EventBus:
    """Synchronous publish/subscribe. Small enough that a dict of lists is the whole design."""

    def __init__(self):
        self._listeners = []

    def subscribe(self, listener):
        """Register `listener(event, **data)`. Returns the listener, so it can be used inline."""
        self._listeners.append(listener)
        return listener

    def unsubscribe(self, listener):
        if listener in self._listeners:
            self._listeners.remove(listener)

    def emit(self, event, **data):
        """
        Publish to every listener. Never raises into the caller: a broken listener must not be
        able to stop the lid from moving, so it is logged and dropped from the bus.
        """
        for listener in list(self._listeners):
            try:
                listener(event, **data)
            except Exception as exception:  # noqa: BLE001 - deliberately broad, see docstring
                log.error("listener %s failed on %s: %s", listener, event, exception)
                self.unsubscribe(listener)
