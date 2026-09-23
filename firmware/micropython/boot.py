"""
Runs before main.py.

Kept almost empty on purpose: anything failing here leaves a board that is awkward to recover.
WiFi is disabled because the bin does not use it, and a radio left on costs battery.
"""

import network

network.WLAN(network.STA_IF).active(False)
