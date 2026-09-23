"""
The event bus: how the lid tells the rest of the firmware what just happened.

The lid knows nothing about sound, LEDs or logging. It changes state; the state machine publishes
one event per transition; listeners react. Adding a reaction (a second LED, a network
notification, a spoken phrase) means writing a listener — never editing the lid.

A listener is any callable `listener(event, **event_data)`. Listeners must not raise, but a
listener that does is contained rather than allowed to break the lid: feedback is decoration on a
bin that has to keep working.

The event vocabulary is the state machine's own — entering a state *is* an event — so there is
one list of names rather than two that can drift apart.
"""

from . import log

# Events that are not state transitions.
MODE_CHANGED = "mode_changed"
SENSOR_FAILED = "sensor_failed"
SENSOR_RECOVERED = "sensor_recovered"
LOW_BATTERY = "low_battery"


def state_entered(state):
    """The event published when `state` is entered."""
    return "entered:" + state


class EventBus:
    """Synchronous publish/subscribe. Small enough that a list of callables is the whole design."""

    # A listener is dropped only after failing this many times: one transient UART error should
    # not silence the bin for the rest of the session, but a permanently broken listener should
    # not spam the log forever either.
    MAX_FAILURES = 3

    def __init__(self):
        self._listeners = []
        self._failures = {}

    def subscribe(self, listener):
        """Register `listener(event, **event_data)`. Returns it, so it can be used inline."""
        self._listeners.append(listener)
        return listener

    def unsubscribe(self, listener):
        if listener in self._listeners:
            self._listeners.remove(listener)

    def emit(self, event, **event_data):
        """Publish to every listener. Never raises into the caller."""
        for listener in list(self._listeners):
            try:
                listener(event, **event_data)
            except Exception as exception:  # noqa: BLE001 - deliberately broad, see module docs
                self._record_failure(listener, event, exception)

    def _record_failure(self, listener, event, exception):
        failures = self._failures.get(listener, 0) + 1
        self._failures[listener] = failures
        log.error("listener failed on %s (%d/%d): %s", event, failures, self.MAX_FAILURES,
                  exception)
        if failures >= self.MAX_FAILURES:
            log.error("listener dropped after repeated failures")
            self.unsubscribe(listener)
