"""
Close-detection strategies — "is the lid actually shut?"

This is the question the original Sisuo board got wrong: it drove the lid closed and waited
forever for a confirmation that never came. Three answers, from crudest to best, all behind one
interface so the choice is a config line:

    start()             -> called as the closing stroke begins
    closed(elapsed_ms)  -> True when the lid should be considered shut

None of them is the safety net. `Lid` stops the motor at MOTOR_MAX_RUN_MS regardless of what a
detector says, so a broken detector can never burn the motor.
"""

from . import log


class TimedCloseDetector:
    """
    Run the motor for a calibrated time and call it shut. No extra hardware, no feedback.

    Good enough to get the bin working, and the reason `LID_CLOSE_RUN_MS` needs calibrating on
    the bench. It cannot tell "shut" from "jammed on a bin bag" — that is what the safety cap and
    the OBSTRUCTED state are for.
    """

    def __init__(self, run_ms):
        self._run_ms = run_ms

    def start(self):
        pass

    def closed(self, elapsed_ms):
        return elapsed_ms >= self._run_ms


class LimitSwitchCloseDetector:
    """
    A microswitch at the end of travel. Deterministic, needs no calibration, and is the option
    the electronics review preferred: one part, and "shut" means shut.

    The switch is wired to ground with a pull-up, so closed == 0.
    """

    def __init__(self, pin):
        self._pin = pin

    def start(self):
        pass

    def closed(self, elapsed_ms):
        return self._pin.value() == 0


class StallCloseDetector:
    """
    Watch the motor current and call the lid shut when it stalls against its stop — the method
    the original board appears to have used.

    Needs the 1 ohm shunt in the motor's ground return and an ADC pin (only GPIO0/1/2 have one on
    this chip). Readings are averaged because the ESP32-C6 ADC is noisy, and the first
    `blanking_ms` of a stroke are ignored so the motor's inrush current is not mistaken for a
    stall.
    """

    def __init__(self, adc, stall_counts, blanking_ms=200, samples=8, consecutive=3, clock=None):
        self._adc = adc
        self._stall_counts = stall_counts
        self._blanking_ms = blanking_ms
        self._samples = samples
        self._consecutive = consecutive
        self._hits = 0

    def start(self):
        self._hits = 0

    def read_counts(self):
        """Averaged raw ADC counts. Exposed for calibration from the REPL."""
        total = 0
        for _ in range(self._samples):
            total += self._adc.read_u16()
        return total // self._samples

    def closed(self, elapsed_ms):
        if elapsed_ms < self._blanking_ms:
            return False

        counts = self.read_counts()
        if counts < self._stall_counts:
            self._hits = 0
            return False

        self._hits += 1
        if self._hits < self._consecutive:
            return False

        log.info("stall detected at %d counts after %d ms", counts, elapsed_ms)
        return True


class FakeCloseDetector:
    """Test double: set `.is_closed` to choose the answer."""

    def __init__(self, is_closed=False):
        self.is_closed = is_closed
        self.started = 0

    def start(self):
        self.started += 1

    def closed(self, elapsed_ms):
        return self.is_closed
