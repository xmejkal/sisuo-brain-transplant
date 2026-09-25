"""
The whole firmware, running on a fake chip.

Everything else on the Mac stops at the strategies, because `hardware.py` imports `machine`.
With `fake_machine` installed, these run the real device construction, the real VL6180X register
conversation and the real tasks — so a test can press a button and watch the motor pins.

It is not a substitute for the bench (timing, electrical behaviour and the amplifier's real
command set are all outside it), but it catches the class of mistake that costs an evening:
a pin built with the wrong mode, a driver that talks to the wrong register, a task that never
fires the trigger it should.
"""

import asyncio
import unittest

import fakes  # noqa: F401 - puts the firmware on sys.path
import fake_machine

fake_machine.install()   # must precede any import that reaches the hardware

import config                                    # noqa: E402
from smartbin import assembly, states            # noqa: E402
from smartbin.hardware import Hardware           # noqa: E402


class Settings:
    """A copy of the real config, so a test can change one thing without touching the file."""

    def __init__(self, **overrides):
        for name in dir(config):
            if name.isupper():
                setattr(self, name, getattr(config, name))
        # Pin the configuration this file is about, rather than inheriting whatever config.py
        # currently says. These tests describe the rangefinder build; switching the shipped
        # default to the IR sensor should not make them fail — it should make them irrelevant.
        self.SENSOR_STRATEGY = "tof"
        self.CLOSE_DETECTOR = "timed"
        self.POWER_POLICY = "always_on"
        for name, value in overrides.items():
            setattr(self, name, value)
        # Scaled down so a full lid cycle takes a fraction of a second.
        self.LID_OPEN_RUN_MS = 30
        self.LID_CLOSE_RUN_MS = 30
        self.LID_OPEN_HOLD_MS = 40
        self.MOTOR_MAX_RUN_MS = 100
        self.SENSOR_POLL_MS = 5
        self.BUTTON_POLL_MS = 5
        self.IDLE_TICK_MS = 5
        self.WATCHDOG_MS = 0

    def save(self, values):
        return True


def build_bin(**overrides):
    fake_machine.reset()
    fake_machine.FakeI2C.devices[0x29] = fake_machine.FakeVL6180X(distance_mm=200)
    return assembly.build(Settings(**overrides))


#: Which level is a press on the OPEN button. Derived, because the board wires it to match
#: the deep-sleep trigger level and hard-coding either value here would silently stop testing a
#: press the moment that direction changed.
PRESSED = 1 if config.WAKE_ON_HIGH else 0
RELEASED = 1 - PRESSED


def pin(number):
    return fake_machine.FakePin.by_number[number]


class TestDeviceConstruction(unittest.TestCase):
    def test_every_device_exists_in_the_default_configuration(self):
        hardware = build_bin().hardware
        self.assertIsNotNone(hardware.motor)
        self.assertIsNotNone(hardware.player)
        self.assertIsNotNone(hardware.rangefinder)
        self.assertIsNotNone(hardware.sensor_bus)

    def test_each_button_is_pulled_AGAINST_its_pressed_level(self):
        """
        The invariant, rather than one wiring of it.

        This asserted that both buttons used the internal pull-up and idled at 1, which stopped
        being true when OPEN was rewired to 3V3: every armed deep-sleep pin shares one trigger
        level, so the wake sources have to assert HIGH and MODE — which cannot wake this chip —
        stayed on the cheaper arrangement. Two buttons, two directions, both correct.

        What must hold either way is that the pull OPPOSES the pressed level. A pull agreeing
        with it reads "pressed" forever; no pull at all leaves the pin floating, which during
        deep sleep wakes the bin at random.
        """
        binned = build_bin()
        for button, number in ((binned.hardware.button_open, config.PIN_BUTTON_OPEN),
                               (binned.hardware.button_mode, config.PIN_BUTTON_MODE)):
            with self.subTest(pin=number):
                expected_pull = (fake_machine.PULL_DOWN if button.pressed_level
                                 else fake_machine.PULL_UP)
                self.assertEqual(pin(number).pull, expected_pull)
                self.assertNotEqual(pin(number).value(), button.pressed_level,
                                    "idles at its pressed level, so it always reads pressed")

    def test_the_open_button_asserts_in_the_direction_deep_sleep_wakes_on(self):
        # If these two disagree the bin either never wakes or wakes constantly, and neither
        # shows up anywhere but on a battery.
        self.assertEqual(build_bin().hardware.button_open.pressed_level,
                         1 if config.WAKE_ON_HIGH else 0)

    def test_the_motor_is_left_stopped_after_construction(self):
        """Constructing the bin must never move the lid."""
        hardware = build_bin().hardware
        self.assertEqual(hardware.motor_pwm_a.duty, 0)
        self.assertEqual(hardware.motor_pwm_b.duty, 0)

    def test_the_ir_configuration_builds_no_i2c_bus(self):
        smart_bin = build_bin(SENSOR_STRATEGY="ir")
        self.assertIsNone(smart_bin.hardware.sensor_bus)
        self.assertIsNotNone(smart_bin.hardware.ir_emitter)


class TestRangefinderConversation(unittest.TestCase):
    def test_the_driver_reads_a_distance_through_the_real_registers(self):
        smart_bin = build_bin()
        self.assertEqual(smart_bin.sensor.read_distance_mm(), 200)

    def test_a_hand_inside_the_window_is_detected_and_one_outside_is_not(self):
        smart_bin = build_bin()
        device = fake_machine.FakeI2C.devices[0x29]

        device.distance_mm = 60          # a hand
        self.assertFalse(smart_bin.sensor.hand_detected())   # needs two readings in a row
        self.assertTrue(smart_bin.sensor.hand_detected())

        device.distance_mm = 200         # nothing there
        self.assertFalse(smart_bin.sensor.hand_detected())

    def test_a_measurement_error_is_not_a_hand_and_does_not_escape(self):
        """Status 7 is routine — it is what an empty field of view reports."""
        smart_bin = build_bin()
        fake_machine.FakeI2C.devices[0x29].status = 7
        self.assertFalse(smart_bin.sensor.hand_detected())
        self.assertIsNone(smart_bin.sensor.read_distance_mm())


class TestFullCycleOnFakeHardware(unittest.TestCase):
    def test_pressing_open_runs_the_motor_and_returns_to_idle(self):
        smart_bin = build_bin()

        async def scenario():
            tasks = smart_bin._start_tasks()
            try:
                pin(config.PIN_BUTTON_OPEN).value(PRESSED)      # press
                await asyncio.sleep(0.05)
                pin(config.PIN_BUTTON_OPEN).value(RELEASED)   # release
                opening_duty = smart_bin.hardware.motor_pwm_a.duty
                await asyncio.sleep(0.25)                 # open, hold, close
                return opening_duty
            finally:
                for task in tasks:
                    if task is not None:
                        task.cancel()

        opening_duty = asyncio.run(scenario())
        self.assertGreater(opening_duty, 0, "the motor should have been driven open")
        self.assertEqual(smart_bin.lid.state, states.IDLE)
        self.assertEqual(smart_bin.hardware.motor_pwm_a.duty, 0)
        self.assertEqual(smart_bin.hardware.motor_pwm_b.duty, 0)

    def test_a_wave_opens_the_lid(self):
        smart_bin = build_bin()
        fake_machine.FakeI2C.devices[0x29].distance_mm = 60

        async def scenario():
            tasks = smart_bin._start_tasks()
            try:
                await asyncio.sleep(0.05)
                return smart_bin.lid.state
            finally:
                for task in tasks:
                    if task is not None:
                        task.cancel()

        self.assertIn(asyncio.run(scenario()), (states.OPENING, states.OPEN))


class TestSafeState(unittest.TestCase):
    def test_enter_safe_state_stops_everything(self):
        smart_bin = build_bin()
        smart_bin.hardware.motor.drive(True, 200)
        smart_bin.hardware.enter_safe_state()
        self.assertEqual(smart_bin.hardware.motor_pwm_a.duty, 0)
        self.assertEqual(pin(config.PIN_LED_RED).value(), 0)
        self.assertEqual(pin(config.PIN_LED_GREEN).value(), 0)


class TestDeepSleep(unittest.TestCase):
    def test_sleeping_arms_the_wake_pins_and_stops_the_motor_first(self):
        smart_bin = build_bin(SENSOR_STRATEGY="tof_interrupt", POWER_POLICY="deep_sleep")
        smart_bin.hardware.motor.drive(True, 200)

        with self.assertRaises(fake_machine.DeepSleepRequested):
            smart_bin.sleep_now()

        self.assertEqual(smart_bin.hardware.motor_pwm_a.duty, 0)
        armed_pins, level = fake_machine.FakeMachineModule.armed_wake
        self.assertIn(config.PIN_BUTTON_OPEN, armed_pins)
        self.assertIn(config.PIN_TOF_INTERRUPT, armed_pins)

    def test_the_armed_wake_level_is_the_one_the_buttons_can_actually_assert(self):
        """
        The bug this exists to prevent: the board wires both buttons to ground, so they assert
        LOW, while the firmware armed wake for a HIGH. The bin would have slept and never woken.
        Two tests asserted the two halves of that contradiction and both passed.
        """
        smart_bin = build_bin(SENSOR_STRATEGY="tof_interrupt", POWER_POLICY="deep_sleep")

        with self.assertRaises(fake_machine.DeepSleepRequested):
            smart_bin.sleep_now()

        _, level = fake_machine.FakeMachineModule.armed_wake
        button_asserts_high = smart_bin.hardware.button_open.pressed_level == 1
        expected = (
            fake_machine.FakeEsp32Module.WAKEUP_ANY_HIGH
            if button_asserts_high
            else fake_machine.FakeEsp32Module.WAKEUP_ALL_LOW
        )
        self.assertEqual(level, expected)

    def test_the_pull_on_a_wake_pin_opposes_the_level_that_wakes(self):
        """A pin pulled the same way it is waiting to be driven can never change."""
        smart_bin = build_bin(SENSOR_STRATEGY="tof_interrupt", POWER_POLICY="deep_sleep")

        with self.assertRaises(fake_machine.DeepSleepRequested):
            smart_bin.sleep_now()

        waking_on_high = smart_bin.config.WAKE_ON_HIGH
        for gpio in fake_machine.FakeMachineModule.armed_wake[0]:
            pull = pin(gpio).pull
            self.assertEqual(
                pull,
                fake_machine.PULL_DOWN if waking_on_high else fake_machine.PULL_UP,
                "GPIO%d is pulled the same way it must be driven to wake" % gpio,
            )

    def test_it_refuses_to_sleep_when_nothing_could_wake_it(self):
        """
        A bin asleep with no way back is worse than a flat battery.

        The mismatch is DERIVED from how the button is actually wired, so this stays a real
        scenario whichever direction the board asserts in. It used to set WAKE_ON_HIGH twice —
        once derived, then unconditionally to True, which overwrote it — and the second line's
        comment said "buttons assert LOW". Both were true of the old wiring and neither was
        checked, so when OPEN moved to 3V3 the test stopped describing a mismatch at all and
        the bin slept.

        `tof` rather than `tof_interrupt`: a polled sensor cannot watch while the chip is off,
        so with the button also unable to assert, nothing is left.
        """
        smart_bin = build_bin(SENSOR_STRATEGY="tof", POWER_POLICY="deep_sleep")
        smart_bin.config.WAKE_ON_HIGH = not smart_bin.hardware.button_open.pressed_level

        self.assertFalse(smart_bin.sleep_now())  # returns rather than raising DeepSleepRequested

    def test_it_does_sleep_when_the_wiring_and_the_armed_level_agree(self):
        # The other half, without which the test above passes for a bin that never sleeps at all.
        smart_bin = build_bin(SENSOR_STRATEGY="tof_interrupt", POWER_POLICY="deep_sleep")
        with self.assertRaises(fake_machine.DeepSleepRequested):
            smart_bin.sleep_now()

    def test_waking_on_the_button_opens_the_lid_without_a_second_press(self):
        smart_bin = build_bin(SENSOR_STRATEGY="tof_interrupt", POWER_POLICY="deep_sleep")
        fake_machine.FakeMachineModule.wake_reason_value = fake_machine.FakeMachineModule.EXT1_WAKE
        fake_machine.FakeMachineModule.wake_pins_value = (config.PIN_BUTTON_OPEN,)

        trigger = smart_bin.power_policy.trigger_for_wake(smart_bin)
        self.assertEqual(trigger, states.OPEN_PRESSED)


if __name__ == "__main__":
    unittest.main()
