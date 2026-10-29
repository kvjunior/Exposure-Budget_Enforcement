"""Typed service ticks and append order. No conversion to legacy Event.t."""
from dataclasses import dataclass


def _nonnegative_integer(value, name):
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer, not bool/float or a different coordinate")
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")


def require_time(value):
    if type(value) is not ServiceTime:
        raise TypeError("expected ServiceTime")
    return value


@dataclass(frozen=True, order=True)
class ServiceTime:
    ticks: int

    def __post_init__(self):
        _nonnegative_integer(self.ticks, "service ticks")

    def later_by(self, ticks):
        _nonnegative_integer(ticks, "duration ticks")
        return ServiceTime(self.ticks + ticks)


@dataclass(frozen=True, order=True)
class LogSequence:
    value: int

    def __post_init__(self):
        _nonnegative_integer(self.value, "log sequence")


@dataclass(frozen=True)
class TimeWindow:
    start: ServiceTime
    end: ServiceTime | None = None

    def __post_init__(self):
        require_time(self.start)
        if self.end is not None:
            require_time(self.end)
            if self.end <= self.start:
                raise ValueError("time window must be nonempty: [start,end)")

    def contains(self, at):
        require_time(at)
        return at >= self.start and (self.end is None or at < self.end)


@dataclass(frozen=True)
class ServiceClock:
    now: ServiceTime = ServiceTime(0)
    last_sequence: LogSequence = LogSequence(0)

    def __post_init__(self):
        require_time(self.now)
        if type(self.last_sequence) is not LogSequence:
            raise TypeError("expected LogSequence")

    def advance_to(self, later):
        require_time(later)
        if later < self.now:
            raise ValueError("service clock cannot move backwards")
        return ServiceClock(later, self.last_sequence)

    def advance_by(self, ticks):
        return self.advance_to(self.now.later_by(ticks))

    def record(self):
        """Assign one append sequence at current time; do not manufacture time."""
        sequence = LogSequence(self.last_sequence.value + 1)
        return ServiceClock(self.now, sequence), sequence
