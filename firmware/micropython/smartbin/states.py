"""
The lid's states, the triggers that move between them, and the transition table.

This module is the behaviour of the product, written as data. It imports nothing from the
hardware, so the tests (and `tools/fsm_diagram.py`) can read it on a PC.

Read the table as: in state X, trigger T leads to state Y. A trigger not listed for the current
state is ignored — that is the point of the table, and it is why "hand waved while the lid is
already opening" needs no defensive `if` anywhere in the code.
"""

# --------------------------------------------------------------------------- states
IDLE = "idle"              # shut, watching for a hand
OPENING = "opening"        # driving open
OPEN = "open"              # held open, hold timer running
CLOSING = "closing"        # driving shut
OBSTRUCTED = "obstructed"  # something stopped the lid mid-close; reopening to free it
FAULT = "fault"            # repeated obstruction or a dead sensor; latched until a button press

ALL_STATES = (IDLE, OPENING, OPEN, CLOSING, OBSTRUCTED, FAULT)

# --------------------------------------------------------------------------- triggers
HAND_DETECTED = "hand_detected"
OPEN_PRESSED = "open_pressed"
STROKE_DONE = "stroke_done"              # a motion finished its calibrated run
CAP_TRIPPED = "cap_tripped"              # the hard MOTOR_MAX_RUN_MS limit fired
CLOSED_CONFIRMED = "closed_confirmed"    # the CloseDetector says the lid is shut
HOLD_EXPIRED = "hold_expired"
RETRY_EXHAUSTED = "retry_exhausted"
SENSOR_FAILED = "sensor_failed"
RESET = "reset"

# --------------------------------------------------------------------------- transitions
TRANSITIONS = {
    IDLE: {
        HAND_DETECTED: OPENING,
        OPEN_PRESSED: OPENING,
    },
    OPENING: {
        STROKE_DONE: OPEN,
        CAP_TRIPPED: OPEN,        # hitting the stop while opening is normal, not a fault
    },
    OPEN: {
        HOLD_EXPIRED: CLOSING,
        OPEN_PRESSED: OPEN,       # self-transition: re-arms the hold timer
        HAND_DETECTED: OPEN,      # a hand still in the way keeps the lid open
    },
    CLOSING: {
        CLOSED_CONFIRMED: IDLE,
        STROKE_DONE: IDLE,
        CAP_TRIPPED: OBSTRUCTED,  # the same trigger as above, and here it means trouble
        HAND_DETECTED: OBSTRUCTED,
    },
    OBSTRUCTED: {
        STROKE_DONE: OPEN,        # reopened successfully; the hold timer will retry the close
        RETRY_EXHAUSTED: FAULT,
        CAP_TRIPPED: OPEN,
    },
    FAULT: {
        OPEN_PRESSED: IDLE,
        RESET: IDLE,
    },
}

# A sensor that keeps failing parks the bin in FAULT from anywhere: better an obvious dead bin
# than one that silently stops noticing hands.
for _state in (IDLE, OPENING, OPEN, CLOSING, OBSTRUCTED):
    TRANSITIONS[_state][SENSOR_FAILED] = FAULT

MOVING_STATES = (OPENING, CLOSING, OBSTRUCTED)
