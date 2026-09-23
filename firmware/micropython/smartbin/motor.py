"""
The lid motor, driven by one channel of an L9110S module.

The L9110S has no enable or standby pin: direction and speed both come from its two inputs.
  IA high, IB low  -> one direction        IA low, IB high -> the other
  both low         -> coast                both high       -> brake
Speed is the duty cycle applied to whichever input is high ("drive/coast", slow decay). Never
PWM both inputs in opposition: the chip has no dead time, so that means shoot-through and heat.

Both inputs are PWM objects because either can be the driven one, depending on direction.

Safety note: the hard run-time cap does NOT live here. `Lid` owns it, because the cap must apply
to the whole stroke including the code that decides when to stop.
"""

DUTY_MAX = 65535
SPEED_MAX = 255


def _duty(speed):
    """Map the 0-255 speed used throughout the config onto MicroPython's 16-bit duty."""
    if speed < 0:
        speed = 0
    elif speed > SPEED_MAX:
        speed = SPEED_MAX
    return speed * DUTY_MAX // SPEED_MAX


class L9110Driver:
    """One L9110S channel. `pwm_a`/`pwm_b` are machine.PWM objects on the IA/IB inputs."""

    def __init__(self, pwm_a, pwm_b):
        self._pwm_a = pwm_a
        self._pwm_b = pwm_b
        self.stop()

    def drive(self, open_direction, speed):
        """Run the motor. `open_direction` True opens the lid, False closes it."""
        duty = _duty(speed)
        if open_direction:
            self._pwm_b.duty_u16(0)
            self._pwm_a.duty_u16(duty)
        else:
            self._pwm_a.duty_u16(0)
            self._pwm_b.duty_u16(duty)

    def stop(self):
        """Coast: both inputs low. The default resting state."""
        self._pwm_a.duty_u16(0)
        self._pwm_b.duty_u16(0)

    def brake(self):
        """Short the motor (both inputs high) for a faster stop than coasting."""
        self._pwm_a.duty_u16(DUTY_MAX)
        self._pwm_b.duty_u16(DUTY_MAX)
