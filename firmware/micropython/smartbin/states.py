"""
The lid's states, the triggers that move between them, and the transition table.

This module is the behaviour of the product, written as data. It imports nothing from the
hardware, so the tests (and `tools/fsm_diagram.py`) can read it on a PC.

Vocabulary: a **stroke** is one run of the motor in one direction — opening or closing — which
ends either by finishing its calibrated time, by the safety cap, or by the close detector.

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

# States in which the motor may be running. Leaving one of them cancels the stroke.
STATES_WITH_MOTION = (OPENING, CLOSING, OBSTRUCTED)

# --------------------------------------------------------------------------- triggers
HAND_DETECTED = "hand_detected"
OPEN_PRESSED = "open_pressed"
STROKE_FINISHED = "stroke_finished"          # the stroke ran its calibrated time
SAFETY_CAP_TRIPPED = "safety_cap_tripped"    # MOTOR_MAX_RUN_MS stopped it first
CLOSE_CONFIRMED = "close_confirmed"          # the CloseDetector says the lid is shut
HOLD_EXPIRED = "hold_expired"
RETRY_LIMIT_REACHED = "retry_limit_reached"
SENSOR_FAILED = "sensor_failed"
RESET_REQUESTED = "reset_requested"

# --------------------------------------------------------------------------- transitions
TRANSITIONS = {
    IDLE: {
        HAND_DETECTED: OPENING,
        OPEN_PRESSED: OPENING,
    },
    OPENING: {
        STROKE_FINISHED: OPEN,
        SAFETY_CAP_TRIPPED: OPEN,   # hitting the stop while opening is normal, not a fault
    },
    OPEN: {
        HOLD_EXPIRED: CLOSING,
        OPEN_PRESSED: OPEN,         # self-transition: re-arms the hold timer
        HAND_DETECTED: OPEN,        # a hand still in the way keeps the lid open
    },
    CLOSING: {
        CLOSE_CONFIRMED: IDLE,
        STROKE_FINISHED: IDLE,
        SAFETY_CAP_TRIPPED: OBSTRUCTED,  # the same trigger as above, and here it means trouble
        HAND_DETECTED: OBSTRUCTED,
    },
    OBSTRUCTED: {
        STROKE_FINISHED: OPEN,      # reopened successfully; the hold timer will retry the close
        SAFETY_CAP_TRIPPED: OPEN,
        RETRY_LIMIT_REACHED: FAULT,
    },
    FAULT: {
        OPEN_PRESSED: IDLE,
        RESET_REQUESTED: IDLE,
    },
}

# A sensor that keeps failing parks the bin in FAULT from anywhere: better an obvious dead bin
# than one that silently stops noticing hands.
for _state in (IDLE, OPENING, OPEN, CLOSING, OBSTRUCTED):
    TRANSITIONS[_state][SENSOR_FAILED] = FAULT
