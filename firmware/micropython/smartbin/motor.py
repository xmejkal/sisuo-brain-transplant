"""
The lid motor.

`MotorDriver` is what the lid depends on — a thing that can drive in two directions and stop.
`L9110MotorDriver` is the one driver chip we happen to use. Anything satisfying the same three
methods can replace it without the lid noticing.

Safety note: the hard run-time cap is NOT here. `Lid` owns it, because the cap must cover the
whole stroke including the code that decides when to stop.
"""

DUTY_MAX = 65535        # MicroPython's 16-bit PWM duty
SPEED_MAX = 255         # the 0-255 scale used throughout config.py


def duty_for_speed(speed):
    """Map the 0-255 speed used in config onto MicroPython's 16-bit duty, clamping the ends."""
    if speed < 0:
        speed = 0
    elif speed > SPEED_MAX:
        speed = SPEED_MAX
    return speed * DUTY_MAX // SPEED_MAX


class MotorDriver:
    """
    What the lid needs from a motor:

        drive(opening, speed)  run, `opening` True to open and False to close, speed 0-255
        stop()                 let the motor coast to a halt; the resting state
        brake()                short the motor for a faster stop
    """

    def drive(self, opening, speed):
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError

    def brake(self):
        """Optional: a driver without a braking mode may simply stop."""
        self.stop()


class L9110MotorDriver(MotorDriver):
    """
    One channel of an L9110S module.

    The chip has no enable or standby pin: direction and speed both come from its two inputs.
        IA high, IB low  -> one direction        IA low, IB high -> the other
        both low         -> coast                both high       -> brake
    Speed is the duty cycle on whichever input is high ("drive/coast", slow decay). Never PWM
    both inputs in opposition: the chip has no dead time, so that means shoot-through and heat.

    Both inputs are PWM objects because either can be the driven one, depending on direction.
    """

    def __init__(self, pwm_a, pwm_b):
        self._pwm_a = pwm_a
        self._pwm_b = pwm_b
        self.stop()

    def drive(self, opening, speed):
        duty = duty_for_speed(speed)
        if opening:
            self._pwm_b.duty_u16(0)
            self._pwm_a.duty_u16(duty)
        else:
            self._pwm_a.duty_u16(0)
            self._pwm_b.duty_u16(duty)

    def stop(self):
        """Coast: both inputs low."""
        self._pwm_a.duty_u16(0)
        self._pwm_b.duty_u16(0)

    def brake(self):
        """Both inputs high shorts the motor, which stops the lid faster than coasting."""
        self._pwm_a.duty_u16(DUTY_MAX)
        self._pwm_b.duty_u16(DUTY_MAX)
