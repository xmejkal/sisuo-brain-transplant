"""
Listeners that turn state transitions into things a person notices.

Each subscribes to the bus and reacts to the event named after the state just entered. None can
influence the lid, and the bus contains any that misbehave, so feedback is strictly decoration on
a bin that works without it.

Sounds and colours are *data* — profiles in config, not code — so re-voicing the bin means
editing config.py or /config.json, never this file.
"""

from . import events, log, states, status_led


class AudioFeedback:
    """
    Plays a cue when a mapped state is entered.

    A profile maps state -> cue; an unmapped state is silence, so "silent" is simply an empty
    profile. `next_profile()` is what the MODE button calls.
    """

    def __init__(self, player, profiles, active="default", volume=22):
        self._player = player
        self._profiles = profiles or {"default": {}}
        self._volume = volume
        self.active = active if active in self._profiles else self._first_profile_name()

    @property
    def profile(self):
        return self._profiles.get(self.active, {})

    def _first_profile_name(self):
        """Falling back to *some* profile keeps a typo in config from killing the button task."""
        return list(self._profiles.keys())[0]

    def set_profile(self, name):
        if name not in self._profiles:
            log.warn("unknown sound profile %s", name)
            return False
        self.active = name
        log.info("sound profile: %s", name)
        return True

    def next_profile(self):
        """Cycle to the next profile in declaration order, and return the new name."""
        names = list(self._profiles.keys())
        if self.active not in names:
            self.active = names[0]
        else:
            self.active = names[(names.index(self.active) + 1) % len(names)]
        log.info("sound profile: %s", self.active)
        return self.active

    def set_volume(self, level):
        self._volume = level
        self._player.set_volume(level)

    def __call__(self, event, **event_data):
        """The bus calls this for every event; we answer only to the states we have a cue for."""
        for state, cue in self.profile.items():
            if event == events.state_entered(state):
                self._player.play(cue)
                return


class LedFeedback:
    """Sets the status LED colour on entering a state. Unmapped states leave the LED alone."""

    def __init__(self, led, colours):
        self._led = led
        self._colours = colours

    def __call__(self, event, **event_data):
        for state, colour in self._colours.items():
            if event == events.state_entered(state):
                self._led.set(colour)
                return


class LogFeedback:
    """Prints every event. The cheapest observability there is, and invaluable over USB."""

    def __call__(self, event, **event_data):
        log.info("event %s %s", event, event_data)


# Green while the lid is doing something wanted, amber while it is working through a problem, red
# when it needs a human. IDLE is dark so a bin at rest draws nothing.
DEFAULT_LED_COLOURS = {
    states.IDLE: status_led.OFF,
    states.OPENING: status_led.GREEN,
    states.OPEN: status_led.GREEN,
    states.CLOSING: status_led.AMBER,
    states.OBSTRUCTED: status_led.AMBER,
    states.FAULT: status_led.RED,
}
