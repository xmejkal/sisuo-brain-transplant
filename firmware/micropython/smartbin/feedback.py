"""
Listeners that turn state transitions into things a person notices.

Each one subscribes to the bus and reacts to the event named after the state just entered. None
of them can influence the lid, and the bus drops any that misbehave, so feedback is strictly
optional decoration on a bin that works without it.

Sounds and colours are *data* — a profile dict in config, not code — so re-voicing the bin means
editing config.py or config.json, never this file.
"""

from . import events, log, states, ui


class AudioFeedback:
    """
    Plays a clip when a mapped state is entered.

    A profile maps state -> track number; an unmapped state is silence, so "silent" is simply an
    empty profile. `set_profile` is what the MODE button calls.
    """

    def __init__(self, player, profiles, active="default", volume=22):
        self._player = player
        self._profiles = profiles
        self._volume = volume
        self.active = active if active in profiles else "default"

    @property
    def profile(self):
        return self._profiles.get(self.active, {})

    def set_profile(self, name):
        if name not in self._profiles:
            log.warn("unknown sound profile %s", name)
            return False
        self.active = name
        log.info("sound profile: %s", name)
        return True

    def next_profile(self):
        """Cycle to the next profile, in the order they are declared. Returns the new name."""
        names = list(self._profiles.keys())
        self.active = names[(names.index(self.active) + 1) % len(names)]
        log.info("sound profile: %s", self.active)
        return self.active

    def set_volume(self, volume):
        self._volume = volume
        self._player.set_volume(volume)

    def __call__(self, event, **data):
        for state, track in self.profile.items():
            if event == events.entered(state):
                self._player.play(track)
                return


class LedFeedback:
    """Sets the status LED colour on entering a state. Unmapped states leave the LED alone."""

    def __init__(self, led, colours):
        self._led = led
        self._colours = colours

    def __call__(self, event, **data):
        for state, colour in self._colours.items():
            if event == events.entered(state):
                self._led.set(colour)
                return


class LogFeedback:
    """Prints every event. The cheapest possible observability, and invaluable over USB."""

    def __call__(self, event, **data):
        log.info("event %s %s", event, data)


DEFAULT_LED_COLOURS = {
    states.IDLE: ui.OFF,
    states.OPENING: ui.GREEN,
    states.OPEN: ui.GREEN,
    states.CLOSING: ui.AMBER,
    states.OBSTRUCTED: ui.AMBER,
    states.FAULT: ui.RED,
}
