"""
Runs before main.py, and deliberately does nothing.

It would be natural to switch the radio off here for a battery-powered bin, but
`network.WLAN(...)` *initialises* the WiFi stack just by being constructed — tens of KB of heap
and real boot time — and the radio is not on by default anyway. On a bin that wakes from deep
sleep hundreds of times, that cost would be paid every wake for no benefit.

Anything that fails here leaves a board that is awkward to recover, so this file stays empty.
"""
