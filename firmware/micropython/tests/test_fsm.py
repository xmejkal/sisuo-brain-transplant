"""State machine and event bus: the parts everything else is built on."""

import unittest

import fakes  # noqa: F401 - puts the firmware on sys.path

from smartbin import events, states
from smartbin.events import EventBus
from smartbin.fsm import StateMachine


def build_machine():
    bus = EventBus()
    seen = []
    bus.subscribe(lambda event, **data: seen.append((event, data)))
    return StateMachine(states.TRANSITIONS, states.IDLE, bus=bus), seen


class TestTransitions(unittest.TestCase):
    def test_legal_transition_moves_and_publishes(self):
        machine, seen = build_machine()
        self.assertTrue(machine.fire(states.HAND_DETECTED))
        self.assertEqual(machine.state, states.OPENING)
        self.assertEqual(seen[0][0], events.entered(states.OPENING))
        self.assertEqual(seen[0][1]["previous"], states.IDLE)

    def test_trigger_not_in_the_table_is_ignored_not_an_error(self):
        machine, seen = build_machine()
        self.assertFalse(machine.fire(states.HOLD_EXPIRED))
        self.assertEqual(machine.state, states.IDLE)
        self.assertEqual(seen, [])

    def test_hooks_run_in_order_around_the_transition(self):
        machine, _ = build_machine()
        order = []
        machine.on_exit(states.IDLE, lambda: order.append("exit idle"))
        machine.on_enter(states.OPENING, lambda: order.append("enter opening"))
        machine.fire(states.OPEN_PRESSED)
        self.assertEqual(order, ["exit idle", "enter opening"])

    def test_a_hook_may_fire_another_trigger(self):
        """The obstruction retry counter does exactly this; it must not re-enter."""
        machine, _ = build_machine()
        machine.on_enter(states.OPENING, lambda: machine.fire(states.CAP_TRIPPED))
        machine.fire(states.HAND_DETECTED)
        self.assertEqual(machine.state, states.OPEN)

    def test_history_records_transitions(self):
        machine, _ = build_machine()
        machine.fire(states.HAND_DETECTED)
        machine.fire(states.STROKE_DONE)
        self.assertEqual(
            [(entry[1], entry[2], entry[3]) for entry in machine.history],
            [
                (states.IDLE, states.HAND_DETECTED, states.OPENING),
                (states.OPENING, states.STROKE_DONE, states.OPEN),
            ],
        )

    def test_every_state_is_reachable_and_has_a_way_out(self):
        """A state you cannot leave is a bricked bin; catch that in the table, not on the bench."""
        destinations = set()
        for transitions in states.TRANSITIONS.values():
            destinations.update(transitions.values())

        for state in states.ALL_STATES:
            self.assertIn(state, states.TRANSITIONS, "%s has no transitions out" % state)
            self.assertTrue(states.TRANSITIONS[state], "%s is a dead end" % state)
            if state != states.IDLE:
                self.assertIn(state, destinations, "%s is unreachable" % state)


class TestEventBus(unittest.TestCase):
    def test_a_broken_listener_is_dropped_not_propagated(self):
        bus = EventBus()
        survived = []

        def broken(event, **data):
            raise ValueError("boom")

        bus.subscribe(broken)
        bus.subscribe(lambda event, **data: survived.append(event))

        bus.emit("first")   # must not raise
        bus.emit("second")

        self.assertEqual(survived, ["first", "second"])


if __name__ == "__main__":
    unittest.main()
