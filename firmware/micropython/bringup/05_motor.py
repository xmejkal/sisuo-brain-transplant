"""
Bring-up step 5 — L9110S + lid motor.

Wiring: A-IA <- the pin named below, A-IB <- the pin named below, module VCC <- 6V pack, module GND, the board GND and
the pack's negative all meeting at ONE point (the module's GND pin). Motor on MOTOR A.
Add the 10k pulldowns on A-IA and A-IB: they are what keeps the motor still while the module boots.

Short, slow pulses only, with the motor OUT of the bin or the lid free to move.
If "open" actually closes, swap the two motor wires in the terminal block.
"""

import time

from machine import PWM, Pin

PIN_MOTOR_IA = 14         # D10
PIN_MOTOR_IB = 18         # D6
PWM_FREQ_HZ = 5000
TEST_SPEED = 120       # 0-255, gentle
PULSE_MS = 300         # well under MOTOR_MAX_RUN_MS
PAUSE_MS = 1000

pwm_a = PWM(Pin(PIN_MOTOR_IA), freq=PWM_FREQ_HZ, duty_u16=0)
pwm_b = PWM(Pin(PIN_MOTOR_IB), freq=PWM_FREQ_HZ, duty_u16=0)


def stop():
    pwm_a.duty_u16(0)
    pwm_b.duty_u16(0)


def pulse(open_direction, label):
    print("Pulse:", label)
    duty = TEST_SPEED * 65535 // 255
    if open_direction:
        pwm_b.duty_u16(0)
        pwm_a.duty_u16(duty)
    else:
        pwm_a.duty_u16(0)
        pwm_b.duty_u16(duty)
    time.sleep_ms(PULSE_MS)
    stop()
    time.sleep_ms(PAUSE_MS)


try:
    pulse(True, "OPEN direction")
    pulse(False, "CLOSE direction")
finally:
    stop()

print("PASS if the motor turned briefly one way, then the other.")
print("Then measure the current: multimeter in series with the motor, running and stalled by hand.")
