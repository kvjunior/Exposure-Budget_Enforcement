"""Append-only public input log with typed observation time and sequence.

Only PublicObservation is intended for a policy. Environment traces/full logs
are not policy inputs. This layer does not verify signatures or authorize PRE.
"""
from dataclasses import dataclass
import math
from .types import Scope, Record
from .service_clock import ServiceTime, LogSequence, ServiceClock, require_time
from .demand_queue import Demand, validate_id, validate_record


def _scope(scope):
    if type(scope) is not Scope:
        raise TypeError("expected Scope")
    validate_id(scope.stream, "scope stream")
    if type(scope.epoch) is not int or scope.epoch < 0:
        raise ValueError("scope epoch must be a nonnegative integer")


@dataclass(frozen=True)
class OwnerNotice:
    owner: str
    online: bool

    def __post_init__(self):
        validate_id(self.owner, "owner")
        if type(self.online) is not bool:
            raise TypeError("availability must be bool")


@dataclass(frozen=True)
class ScopeNotice:
    owner: str
    scope: Scope
    key_id: str
    start_seq: int

    def __post_init__(self):
        validate_id(self.owner, "owner")
        _scope(self.scope)
        validate_id(self.key_id, "key ID")
        if type(self.start_seq) is not int or self.start_seq < 0:
            raise ValueError("scope start must be a nonnegative integer")


@dataclass(frozen=True)
class RecordNotice:
    record: Record
    scope: Scope
    weight: float = 1.0

    def __post_init__(self):
        validate_record(self.record)
        _scope(self.scope)
        if self.record.stream != self.scope.stream:
            raise ValueError("record must name its original stream's scope")
        if type(self.weight) not in (int, float):
            raise TypeError("record weight must be numeric, not bool")
        try:
            valid = math.isfinite(self.weight) and self.weight >= 0
        except OverflowError:
            valid = False
        if not valid:
            raise ValueError("record weight must be finite and nonnegative")


@dataclass(frozen=True)
class DemandArrival:
    demand: Demand

    def __post_init__(self):
        if type(self.demand) is not Demand:
            raise TypeError("expected immutable Demand")


_PUBLIC_TYPES = (OwnerNotice, ScopeNotice, RecordNotice, DemandArrival)


@dataclass(frozen=True)
class PublicEvent:
    event_id: str
    occurred_at: ServiceTime
    available_at: ServiceTime
    payload: OwnerNotice | ScopeNotice | RecordNotice | DemandArrival

    def __post_init__(self):
        validate_id(self.event_id, "event ID")
        require_time(self.occurred_at)
        require_time(self.available_at)
        if self.available_at < self.occurred_at:
            raise ValueError("a report cannot be available before occurrence")
        # Exact whitelist prevents legacy or ground-truth event subclasses
        # carrying hidden fields from entering policy observations.
        if type(self.payload) not in _PUBLIC_TYPES:
            raise TypeError("unknown/legacy/ground-truth payload is not a public timed input")
        if type(self.payload) is DemandArrival and self.occurred_at != self.payload.demand.released_at:
            raise ValueError("arrival occurrence must equal demand release")


def _event_key(event):
    p = event.payload
    if type(p) is OwnerNotice:
        phase, domain = 0, (p.owner,)
    elif type(p) is ScopeNotice:
        phase, domain = 1, (p.scope.stream, p.scope.epoch, p.start_seq, p.key_id, p.owner)
    elif type(p) is RecordNotice:
        phase, domain = 2, (p.record.stream, p.record.seq, p.scope.epoch)
    else:
        phase, domain = 3, (p.demand.demand_id,)
    return event.available_at.ticks, phase, event.occurred_at.ticks, domain, event.event_id


def _fact_key(event):
    p = event.payload
    if type(p) is OwnerNotice:
        return "owner", p.owner, event.occurred_at.ticks
    if type(p) is ScopeNotice:
        return "scope", p.scope.stream, p.scope.epoch
    if type(p) is RecordNotice:
        return "record", p.record.stream, p.record.seq
    return "demand", p.demand.demand_id


@dataclass(frozen=True)
class TimedEntry:
    sequence: LogSequence
    logged_at: ServiceTime
    event: PublicEvent

    def __post_init__(self):
        if type(self.sequence) is not LogSequence or self.sequence.value == 0:
            raise ValueError("entry sequence starts at one")
        require_time(self.logged_at)
        if type(self.event) is not PublicEvent:
            raise TypeError("expected PublicEvent")
        if self.event.available_at > self.logged_at:
            raise ValueError("future report cannot be logged")


def _validate_entries(entries, now):
    if type(entries) is not tuple or any(type(e) is not TimedEntry for e in entries):
        raise TypeError("entries must be an immutable tuple of TimedEntry")
    ids, facts = set(), set()
    previous = None
    for index, entry in enumerate(entries, 1):
        if entry.sequence.value != index or entry.logged_at > now:
            raise ValueError("noncontiguous sequence or future entry")
        if previous is not None:
            if entry.logged_at < previous.logged_at:
                raise ValueError("logging time cannot move backwards")
            if entry.logged_at == previous.logged_at and _event_key(entry.event) < _event_key(previous.event):
                raise ValueError("same-time reports must follow canonical order")
        fact = _fact_key(entry.event)
        if entry.event.event_id in ids or fact in facts:
            raise ValueError("duplicate event ID, duplicate fact or conflicting same-time owner notice")
        ids.add(entry.event.event_id)
        facts.add(fact)
        previous = entry


@dataclass(frozen=True)
class PublicObservation:
    now: ServiceTime
    version: LogSequence
    entries: tuple[TimedEntry, ...] = ()

    def __post_init__(self):
        require_time(self.now)
        _validate_entries(self.entries, self.now)
        if type(self.version) is not LogSequence or self.version.value != len(self.entries):
            raise ValueError("observation version must describe only its visible prefix")


@dataclass(frozen=True)
class TimedLog:
    clock: ServiceClock = ServiceClock()
    entries: tuple[TimedEntry, ...] = ()

    def __post_init__(self):
        if type(self.clock) is not ServiceClock:
            raise TypeError("expected ServiceClock")
        _validate_entries(self.entries, self.clock.now)
        if self.clock.last_sequence.value != len(self.entries):
            raise ValueError("clock append counter must match the full log")

    def advance_to(self, later):
        return TimedLog(self.clock.advance_to(later), self.entries)

    def append_batch(self, events):
        if type(events) is not tuple or any(type(e) is not PublicEvent for e in events):
            raise TypeError("batch must be an immutable tuple of PublicEvent")
        clock = self.clock
        added = []
        for event in sorted(events, key=_event_key):
            clock, sequence = clock.record()
            added.append(TimedEntry(sequence, clock.now, event))
        return TimedLog(clock, self.entries + tuple(added))

    def observe(self, cutoff=None, through_sequence=None):
        at = self.clock.now if cutoff is None else require_time(cutoff)
        if at > self.clock.now:
            raise ValueError("cannot observe a future service cutoff")
        maximum = self.clock.last_sequence
        if through_sequence is not None:
            if type(through_sequence) is not LogSequence:
                raise TypeError("expected LogSequence frontier")
            if through_sequence > maximum:
                raise ValueError("cannot observe an uncommitted sequence")
            maximum = through_sequence
        prefix = tuple(e for e in self.entries if e.logged_at <= at and e.sequence <= maximum)
        version = prefix[-1].sequence if prefix else LogSequence(0)
        return PublicObservation(at, version, prefix)
