"""Finite timed model of retained material and declared-family exposure.

No legacy timestamp casts; no cryptography; PO1/family soundness remain assumptions.
The family expands exact recipient subsets because authorization is not monotone in reach.
"""
from dataclasses import dataclass
from itertools import combinations
from fractions import Fraction
import math
from .types import Record, Scope
from .service_clock import ServiceTime, require_time
from .demand_queue import validate_id, validate_record
from .timed_log import ScopeNotice, RecordNotice
from .timed_authorization import TimedGrant, validate_scopes


@dataclass(frozen=True)
class Reach:
    label: str
    proxies: frozenset[str]
    recipients: frozenset[str]

    def __post_init__(self):
        validate_id(self.label, 'reach label')
        for group in (self.proxies, self.recipients):
            if type(group) is not frozenset:
                raise TypeError('immutable reach required')
            for party in group:
                validate_id(party, 'party')
        if len(self.recipients) > 8:
            raise ValueError('P3B bounded family supports at most 8 candidate recipients per reach')


def family_cases(family):
    if type(family) is not tuple or not family or any(type(s) is not Reach for s in family):
        raise ValueError('nonempty immutable declared family required')
    if len({s.label for s in family}) != len(family):
        raise ValueError('unique family labels required')
    cases = []
    for s in family:
        rs = sorted(s.recipients)
        for n in range(len(rs)+1):
            for subset in combinations(rs, n):
                # Length-framed repr of a tuple is unambiguous even for punctuation in IDs.
                cases.append(Reach(repr((s.label, subset)), s.proxies, frozenset(subset)))
    return tuple(cases)


@dataclass(frozen=True)
class Budget:
    endpoint_weight: Fraction
    disclosed_weight: Fraction
    active_scopes: int

    def __post_init__(self):
        for v in (self.endpoint_weight, self.disclosed_weight):
            try:
                valid = type(v) in (int, float) and math.isfinite(v) and v >= 0
            except OverflowError:
                valid = False
            if not valid:
                raise ValueError('finite nonnegative weight budgets required')
        if type(self.active_scopes) is not int or self.active_scopes < 0:
            raise ValueError('nonnegative integer scope budget required')


@dataclass(frozen=True)
class IssuedGrant:
    grant: TimedGrant
    issued_at: ServiceTime
    revoked_at: ServiceTime | None = None

    def __post_init__(self):
        if type(self.grant) is not TimedGrant:
            raise TypeError('TimedGrant required')
        require_time(self.issued_at)
        if not self.grant.validity.contains(self.issued_at):
            raise ValueError('grant must be issued inside its service-time window')
        if self.revoked_at is not None:
            require_time(self.revoked_at)
            if self.revoked_at < self.issued_at:
                raise ValueError('revocation cannot precede issuance')

    def live(self, at):
        return self.issued_at <= at and self.grant.validity.contains(at) and (self.revoked_at is None or at < self.revoked_at)


@dataclass(frozen=True)
class Delivery:
    grant_id: str
    index: int
    record: Record | None = None  # None = raw kfrag installed at its named proxy

    def __post_init__(self):
        validate_id(self.grant_id, 'grant ID')
        if type(self.index) is not int or self.index < 0:
            raise ValueError('nonnegative integer share index required')
        if self.record is not None:
            validate_record(self.record)


@dataclass(frozen=True)
class CapabilityState:
    scopes: tuple[ScopeNotice, ...] = ()
    records: tuple[tuple[RecordNotice, ServiceTime], ...] = ()
    grants: tuple[IssuedGrant, ...] = ()
    deliveries: tuple[Delivery, ...] = ()

    def __post_init__(self):
        for values, kind in ((self.scopes, ScopeNotice), (self.grants, IssuedGrant),
                             (self.deliveries, Delivery)):
            if type(values) is not tuple or any(type(v) is not kind for v in values):
                raise TypeError('immutable typed capability components required')
        validate_scopes(self.scopes)
        if type(self.records) is not tuple:
            raise TypeError('immutable record catalogue required')
        for item in self.records:
            if type(item) is not tuple or len(item) != 2 or type(item[0]) is not RecordNotice:
                raise TypeError('typed record/time pair required')
            require_time(item[1])
        if len({n.record for n, _ in self.records}) != len(self.records):
            raise ValueError('duplicate produced record')
        grants = {g.grant.grant_id: g.grant for g in self.grants}
        if len(grants) != len(self.grants) or len(set(self.deliveries)) != len(self.deliveries):
            raise ValueError('duplicate grant or retained delivery')
        for d in self.deliveries:
            if d.grant_id not in grants or d.index >= len(grants[d.grant_id].proxies):
                raise ValueError('delivery without matching grant/share')
            if d.record is not None and Delivery(d.grant_id, d.index) not in self.deliveries:
                raise ValueError('transformed fragment requires an installed raw share')
            if d.record is not None:
                n = next((n for n, _ in self.records if n.record == d.record), None)
                if n is None or n.scope != grants[d.grant_id].scope or not grants[d.grant_id].rng.contains(d.record):
                    raise ValueError('transformed fragment must bind an authentic in-range record/scope')


@dataclass(frozen=True)
class CaseExposure:
    label: str
    endpoint_records: tuple[Record, ...]
    disclosed: tuple[tuple[Record, ServiceTime], ...]
    active_scopes: tuple[Scope, ...]
    endpoint_weight: float
    disclosed_weight: float

    def within(self, budget):
        return (self.endpoint_weight <= budget.endpoint_weight
                and self.disclosed_weight <= budget.disclosed_weight
                and len(self.active_scopes) <= budget.active_scopes)


def openability(state, recipients, proxies):
    exposed, opened = set(), set()
    for issued in state.grants:
        g = issued.grant
        if g.recipient not in recipients:
            continue
        raw = {d.index for d in state.deliveries if d.grant_id == g.grant_id and d.record is None
               and g.proxies[d.index] in proxies}
        if len(raw) >= g.threshold:
            exposed.add(g.scope)
        for notice, _ in state.records:
            if notice.scope != g.scope:
                continue
            received = {d.index for d in state.deliveries if d.grant_id == g.grant_id and d.record == notice.record}
            if len(raw | received) >= g.threshold:
                opened.add(notice.record)
    for notice, _ in state.records:
        if notice.scope in exposed:
            opened.add(notice.record)
    return exposed, opened


def authorized_ever(issued, notice, produced_at, now):
    g = issued.grant
    if g.scope != notice.scope or not g.rng.contains(notice.record):
        return False
    first = max(issued.issued_at, g.validity.start, produced_at)
    # External production precedes a manager revocation at the SAME tick. Such
    # records were intentionally authorized before that revocation committed.
    # Window expiry, in contrast, happens BEFORE production and stays exclusive.
    return (first <= now and (g.validity.end is None or first < g.validity.end)
            and (issued.revoked_at is None or first <= issued.revoked_at))


def assess(state, now, cases, previous=()):
    """Evaluate public or evaluator-only actual state. Never use actual metrics as policy input."""
    require_time(now)
    old = {p.label: dict(p.disclosed) for p in previous}
    # Exact arithmetic on the supplied int/IEEE-float values: a small positive
    # collateral weight must not disappear when added to a much larger weight.
    weights = {n.record: Fraction(n.weight) for n, _ in state.records}
    active = {s.scope for s in state.scopes if not any(t.scope.stream == s.scope.stream
              and t.scope.epoch > s.scope.epoch for t in state.scopes)}
    result = []
    for case in cases:
        exposed, opened = openability(state, case.recipients, case.proxies)
        authorized = {n.record for n, at in state.records for g in state.grants
                      if g.grant.recipient in case.recipients and authorized_ever(g, n, at, now)}
        collateral = opened - authorized
        ledger = old.get(case.label, {}).copy()
        for r in sorted(collateral):
            ledger.setdefault(r, now)
        result.append(CaseExposure(case.label, tuple(sorted(collateral)), tuple(sorted(ledger.items())),
                                   tuple(sorted(exposed & active)), sum((weights[r] for r in collateral), Fraction(0)),
                                   sum((weights[r] for r in ledger), Fraction(0))))
    return tuple(result)
