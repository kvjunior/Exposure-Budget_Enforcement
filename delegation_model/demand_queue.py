"""Immutable finite-record demands, service completion and explicit waiting metrics.

CompletionReceipt is a trusted-adapter assertion, not a cryptographic proof.
This layer never grants authority or delivers PRE material.
"""
from dataclasses import dataclass, replace
from enum import Enum
from .types import Record
from .service_clock import ServiceTime, TimeWindow, require_time


def validate_id(value, name):
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")


def validate_record(record):
    if type(record) is not Record:
        raise TypeError("expected an immutable Record identity")
    validate_id(record.stream, "stream")
    if type(record.seq) is not int or record.seq < 0:
        raise ValueError("record sequence must be a nonnegative integer")


def _targets(records):
    if type(records) is not tuple:
        raise TypeError("record targets must be an immutable tuple")
    if not records:
        raise ValueError("at least one record target is required")
    for record in records:
        validate_record(record)
    if len(set(records)) != len(records):
        raise ValueError("duplicate record target")
    return tuple(sorted(records))


@dataclass(frozen=True)
class Demand:
    demand_id: str
    owner: str
    recipient: str
    targets: tuple[Record, ...]
    released_at: ServiceTime
    deadline: ServiceTime

    def __post_init__(self):
        for name in ("demand_id", "owner", "recipient"):
            validate_id(getattr(self, name), name)
        object.__setattr__(self, "targets", _targets(self.targets))
        require_time(self.deadline)
        TimeWindow(self.released_at, self.deadline)


class CompletionKind(Enum):
    METADATA = "metadata"
    PARTIAL = "partial"
    USABLE = "usable"


@dataclass(frozen=True)
class CompletionReceipt:
    receipt_id: str
    demand_id: str
    owner: str
    recipient: str
    targets: tuple[Record, ...]
    completed_at: ServiceTime
    kind: CompletionKind

    def __post_init__(self):
        for name in ("receipt_id", "demand_id", "owner", "recipient"):
            validate_id(getattr(self, name), name)
        object.__setattr__(self, "targets", _targets(self.targets))
        require_time(self.completed_at)
        if type(self.kind) is not CompletionKind:
            raise TypeError("expected CompletionKind")


class DemandStatus(Enum):
    PENDING = "pending"
    SERVED = "served"
    REJECTED = "rejected"
    EXPIRED = "expired"


def _matches(demand, receipt):
    return ((receipt.demand_id, receipt.owner, receipt.recipient, receipt.targets) ==
            (demand.demand_id, demand.owner, demand.recipient, demand.targets))


@dataclass(frozen=True)
class DemandState:
    demand: Demand
    offered_at: ServiceTime
    status: DemandStatus = DemandStatus.PENDING
    ended_at: ServiceTime | None = None
    receipt: CompletionReceipt | None = None

    def __post_init__(self):
        if type(self.demand) is not Demand or type(self.status) is not DemandStatus:
            raise TypeError("expected Demand and DemandStatus")
        require_time(self.offered_at)
        if self.offered_at < self.demand.released_at:
            raise ValueError("future demand cannot be offered early")
        if self.status == DemandStatus.PENDING:
            if self.ended_at is not None or self.receipt is not None:
                raise ValueError("pending demand has no terminal result")
            if self.offered_at >= self.demand.deadline:
                raise ValueError("a late offer must be expired")
        else:
            require_time(self.ended_at)
            if self.status == DemandStatus.EXPIRED:
                if self.ended_at != self.demand.deadline or self.receipt is not None:
                    raise ValueError("expiry ends at the deadline without a completion receipt")
            else:
                if not self.offered_at <= self.ended_at < self.demand.deadline:
                    raise ValueError("terminal service/rejection must precede the deadline")
                if self.status == DemandStatus.SERVED:
                    if (type(self.receipt) is not CompletionReceipt or
                            self.receipt.kind != CompletionKind.USABLE or
                            self.receipt.completed_at != self.ended_at or
                            not _matches(self.demand, self.receipt)):
                        raise ValueError("served demand requires matching usable evidence")
                elif self.receipt is not None:
                    raise ValueError("rejection cannot carry a completion receipt")


class DemandStateError(ValueError):
    pass


@dataclass(frozen=True)
class QueueMetrics:
    pending: int
    served: int
    rejected: int
    expired: int
    waiting_ticks: int

    @property
    def terminal_failures(self):
        return self.rejected + self.expired


@dataclass(frozen=True)
class DemandQueue:
    now: ServiceTime = ServiceTime(0)
    entries: tuple[DemandState, ...] = ()

    def __post_init__(self):
        require_time(self.now)
        if type(self.entries) is not tuple or any(type(e) is not DemandState for e in self.entries):
            raise TypeError("queue entries must be an immutable tuple of DemandState")
        if len({e.demand.demand_id for e in self.entries}) != len(self.entries):
            raise ValueError("duplicate demand ID")
        receipts = [e.receipt.receipt_id for e in self.entries if e.receipt is not None]
        if len(set(receipts)) != len(receipts):
            raise ValueError("completion receipt credited more than once")
        for entry in self.entries:
            if entry.offered_at > self.now or (entry.ended_at is not None and entry.ended_at > self.now):
                raise ValueError("queue cannot contain future state")
            if entry.status == DemandStatus.PENDING and self.now >= entry.demand.deadline:
                raise ValueError("overdue demand must be expired")

    def get(self, demand_id):
        for entry in self.entries:
            if entry.demand.demand_id == demand_id:
                return entry
        raise KeyError(demand_id)

    def _pending(self, demand_id):
        entry = self.get(demand_id)
        if entry.status != DemandStatus.PENDING:
            raise DemandStateError(f"{demand_id} is already {entry.status.value}")
        return entry

    def _replace(self, updated):
        return DemandQueue(self.now, tuple(updated if e.demand.demand_id == updated.demand.demand_id
                                           else e for e in self.entries))

    def advance_to(self, later):
        require_time(later)
        if later < self.now:
            raise ValueError("queue time cannot move backwards")
        entries = tuple(replace(e, status=DemandStatus.EXPIRED, ended_at=e.demand.deadline)
                        if e.status == DemandStatus.PENDING and later >= e.demand.deadline else e
                        for e in self.entries)
        return DemandQueue(later, entries)

    def offer(self, demand):
        if type(demand) is not Demand:
            raise TypeError("expected Demand")
        if any(e.demand.demand_id == demand.demand_id for e in self.entries):
            raise ValueError("demand ID cannot be offered twice")
        if demand.released_at > self.now:
            raise ValueError("future demand is not yet observable")
        late = self.now >= demand.deadline
        entry = DemandState(demand, self.now, DemandStatus.EXPIRED if late else DemandStatus.PENDING,
                            demand.deadline if late else None)
        return DemandQueue(self.now, self.entries + (entry,))

    def defer(self, demand_id, until):
        self._pending(demand_id)
        return self.advance_to(until)

    def reject(self, demand_id):
        entry = self._pending(demand_id)
        return self._replace(replace(entry, status=DemandStatus.REJECTED, ended_at=self.now))

    def complete(self, demand_id, receipt):
        entry = self._pending(demand_id)
        if type(receipt) is not CompletionReceipt:
            raise TypeError("expected CompletionReceipt from the trusted backend")
        if (receipt.completed_at != self.now or receipt.kind != CompletionKind.USABLE or
                not _matches(entry.demand, receipt)):
            raise ValueError("completion must match current time, exact demand and usable service")
        return self._replace(replace(entry, status=DemandStatus.SERVED, ended_at=self.now, receipt=receipt))

    def metrics(self):
        counts = {status: sum(e.status == status for e in self.entries) for status in DemandStatus}
        waiting = sum((e.ended_at if e.ended_at is not None else self.now).ticks
                      - e.demand.released_at.ticks for e in self.entries)
        return QueueMetrics(counts[DemandStatus.PENDING], counts[DemandStatus.SERVED],
                            counts[DemandStatus.REJECTED], counts[DemandStatus.EXPIRED], waiting)
