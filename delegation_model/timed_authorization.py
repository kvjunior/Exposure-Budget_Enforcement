"""Service-time authority; no conversion to legacy Event.t or Grant validity.

Notices/tokens are authentic provisioning assertions in this model, not signatures.
Only public observations are projected here. Actual owner availability is a backend duty.
"""
from dataclasses import dataclass
from .types import RecordRange, Scope
from .service_clock import ServiceTime, TimeWindow, require_time
from .demand_queue import Demand, validate_id
from .timed_log import PublicObservation, OwnerNotice, ScopeNotice, RecordNotice


@dataclass(frozen=True)
class TimedGrant:
    grant_id: str
    owner: str
    recipient: str
    scope: Scope
    rng: RecordRange
    threshold: int
    proxies: tuple[str, ...]
    validity: TimeWindow

    def __post_init__(self):
        for n in ('grant_id', 'owner', 'recipient'):
            validate_id(getattr(self, n), n)
        if type(self.scope) is not Scope or type(self.rng) is not RecordRange:
            raise TypeError('typed scope and range required')
        # ScopeNotice supplies the strict checks absent in historical Scope.
        ScopeNotice(self.owner, self.scope, 'validation-key', 0)
        if self.rng.stream != self.scope.stream:
            raise ValueError('range stream differs from scope')
        if type(self.rng.lo) is not int or self.rng.lo < 0:
            raise ValueError('range lower bound must be a nonnegative integer')
        if self.rng.hi is not None and (type(self.rng.hi) is not int or self.rng.hi <= self.rng.lo):
            raise ValueError('bounded range must be nonempty')
        if type(self.proxies) is not tuple or not self.proxies:
            raise TypeError('nonempty immutable proxy tuple required')
        for p in self.proxies:
            validate_id(p, 'proxy')
        if len(set(self.proxies)) != len(self.proxies):
            raise ValueError('distinct proxies required')
        if type(self.threshold) is not int or not 1 <= self.threshold <= len(self.proxies):
            raise ValueError('invalid threshold')
        if type(self.validity) is not TimeWindow:
            raise TypeError('service-time window required')


def indices(value, shares=None):
    if type(value) is not tuple or any(type(i) is not int or i < 0 or
                                     (shares is not None and i >= shares) for i in value):
        raise ValueError('indices must be an immutable tuple of in-range integers')
    if value != tuple(sorted(set(value))):
        raise ValueError('indices must be unique and sorted')
    return value


@dataclass(frozen=True)
class GrantToken:
    token_id: str
    grant: TimedGrant
    validity: TimeWindow
    allowed_indices: tuple[int, ...]

    def __post_init__(self):
        validate_id(self.token_id, 'token ID')
        if type(self.grant) is not TimedGrant or type(self.validity) is not TimeWindow:
            raise TypeError('typed grant/window required')
        indices(self.allowed_indices, len(self.grant.proxies))


@dataclass(frozen=True)
class ActivationToken:
    token_id: str
    activation: ScopeNotice
    validity: TimeWindow

    def __post_init__(self):
        validate_id(self.token_id, 'token ID')
        if type(self.activation) is not ScopeNotice or type(self.validity) is not TimeWindow:
            raise TypeError('typed scope activation/window required')


@dataclass(frozen=True)
class PublicCatalogue:
    owners: tuple[tuple[str, ServiceTime, bool], ...]
    scopes: tuple[ScopeNotice, ...]
    records: tuple[tuple[RecordNotice, ServiceTime], ...]

    def online(self, owner):
        return any(o == owner and up for o, _, up in self.owners)

    def scope(self, scope):
        return next((s for s in self.scopes if s.scope == scope), None)

    def record(self, record):
        return next((r for r, _ in self.records if r.record == record), None)


def validate_scopes(scopes):
    """One owner per stream; monotonic epoch/start; no key-ID aliasing. Freshness is assumed."""
    if len({s.scope for s in scopes}) != len(scopes) or len({s.key_id for s in scopes}) != len(scopes):
        raise ValueError('duplicate scope or reused scope-key ID')
    for stream in {s.scope.stream for s in scopes}:
        ss = sorted((s for s in scopes if s.scope.stream == stream), key=lambda s: s.scope.epoch)
        if len({s.owner for s in ss}) != 1:
            raise ValueError('stream ownership conflict')
        if any(a.start_seq >= b.start_seq for a, b in zip(ss, ss[1:])):
            raise ValueError('scope starts must increase with epoch')


def project(observation, managed_scopes=()):
    if type(observation) is not PublicObservation or type(managed_scopes) is not tuple:
        raise TypeError('public observation and immutable managed scopes required')
    owners, scopes, records = {}, {}, {}
    for entry in observation.entries:
        p, at = entry.event.payload, entry.event.occurred_at
        if type(p) is OwnerNotice:
            if p.owner not in owners or at > owners[p.owner][0]:
                owners[p.owner] = (at, p.online)
        elif type(p) is ScopeNotice:
            scopes[p.scope] = p
        elif type(p) is RecordNotice:
            records[p.record] = (p, at)
    for s in managed_scopes:
        if type(s) is not ScopeNotice:
            raise TypeError('typed managed scope required')
        if s.scope in scopes and scopes[s.scope] != s:
            raise ValueError('conflicting scope report')
        scopes[s.scope] = s
    ss = tuple(sorted(scopes.values(), key=lambda s: s.scope))
    validate_scopes(ss)
    return PublicCatalogue(tuple((o, *owners[o]) for o in sorted(owners)), ss,
                           tuple(records[r] for r in sorted(records)))


def grant_authority(catalogue, grant, now, tokens, index=None):
    """Public authority predicate; backend additionally checks actual owner state."""
    require_time(now)
    scope = catalogue.scope(grant.scope)
    if scope is None or scope.owner != grant.owner or not grant.validity.contains(now):
        return False
    if catalogue.online(grant.owner):
        return True
    return any(type(t) is GrantToken and t.grant == grant and t.validity.contains(now)
               and (index is None or index in t.allowed_indices) for t in tokens)


def grant_token_covers(grant, now, tokens, index=None):
    return any(type(t) is GrantToken and t.grant == grant and t.validity.contains(now)
               and (index is None or index in t.allowed_indices) for t in tokens)


def activation_authority(catalogue, activation, now, tokens):
    if catalogue.online(activation.owner):
        return True
    return activation_token_covers(activation, now, tokens)


def activation_token_covers(activation, now, tokens):
    return any(type(t) is ActivationToken and t.activation == activation and t.validity.contains(now)
               for t in tokens)


def covers_demand(catalogue, grant, demand, now):
    if type(demand) is not Demand or not demand.released_at <= now < demand.deadline:
        return False
    if (demand.owner, demand.recipient) != (grant.owner, grant.recipient):
        return False
    return all((r := catalogue.record(target)) is not None and r.scope == grant.scope
               and grant.rng.contains(target) for target in demand.targets)
