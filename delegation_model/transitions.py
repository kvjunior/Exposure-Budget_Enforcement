"""
One pure validated state transition (P2, review step 1).

A single function `apply_event` advances a typed immutable-ish ManagementState by exactly one
event, validating that event against the current state. The SAME transition is used by the model
executor (committing checked actions) and by planners/oracles (exploring futures), so the
executor and planner can never diverge on what an event does. Production, expiry, revocation and
partial delivery are all expressed as events and handled here.

The state tracks only what transitions need: stream owners, active scope + key id + start seq per
stream, next seq per stream, produced records, live/revoked grants, installed kfrag indices per
grant, and owner connectivity. It deliberately does NOT track realized corruption (evaluation
channel) — retained-capability accounting is computed from the event log by closure/ledger.
"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from .types import Scope, Record, Grant, GrantId
from .events import (Event, StreamAuthorized, ScopeActivated, RecordProduced, GrantIssued,
                     GrantRevoked, KFragInstalled, CFragProduced, OwnerAvailability)


class TransitionError(ValueError):
    pass


@dataclass
class ManagementState:
    t: int = -1
    stream_owner: Dict[str, str] = field(default_factory=dict)
    active_scope: Dict[str, Scope] = field(default_factory=dict)
    scope_key_id: Dict[Tuple[str, int], str] = field(default_factory=dict)
    scope_start: Dict[Tuple[str, int], int] = field(default_factory=dict)
    next_seq: Dict[str, int] = field(default_factory=dict)
    produced: Set[Record] = field(default_factory=set)
    live_grants: Dict[GrantId, Grant] = field(default_factory=dict)
    revoked: Dict[GrantId, int] = field(default_factory=dict)
    installed: Dict[GrantId, Set[int]] = field(default_factory=dict)   # grant -> share indices
    owner_online: Dict[str, bool] = field(default_factory=dict)
    version: int = 0

    def copy(self) -> "ManagementState":
        return deepcopy(self)


def apply_event(state: ManagementState, e: Event) -> ManagementState:
    """Return a NEW state advanced by `e`, or raise TransitionError. Pure: input unchanged."""
    s = state.copy()
    if e.t <= s.t:
        raise TransitionError(f"event time {e.t} not after state time {s.t}")
    s.t = e.t
    s.version += 1

    if isinstance(e, StreamAuthorized):
        if e.stream in s.stream_owner and s.stream_owner[e.stream] != e.owner:
            raise TransitionError(f"conflicting owner for stream {e.stream!r}")
        s.stream_owner.setdefault(e.stream, e.owner)
        s.owner_online.setdefault(e.owner, True)

    elif isinstance(e, ScopeActivated):
        if e.scope.stream not in s.stream_owner:
            raise TransitionError("scope on unregistered stream")
        if (e.scope.stream, e.scope.epoch) in s.scope_start:
            raise TransitionError("scope already activated")
        if e.scope_key_id in s.scope_key_id.values():
            raise TransitionError("reused scope key id")
        want = s.next_seq.get(e.scope.stream, 0)
        if e.start_seq != want:
            raise TransitionError(f"start_seq {e.start_seq} != next seq {want}")
        s.active_scope[e.scope.stream] = e.scope
        s.scope_key_id[(e.scope.stream, e.scope.epoch)] = e.scope_key_id
        s.scope_start[(e.scope.stream, e.scope.epoch)] = e.start_seq

    elif isinstance(e, RecordProduced):
        st = e.record.stream
        if st not in s.active_scope:
            raise TransitionError("record with no active scope")
        want = s.next_seq.get(st, 0)
        if e.record.seq != want:
            raise TransitionError(f"record seq {e.record.seq} != next seq {want}")
        s.produced.add(e.record)
        s.next_seq[st] = want + 1

    elif isinstance(e, GrantIssued):
        g = e.grant
        if g.scope.stream not in s.stream_owner:
            raise TransitionError("grant on unregistered stream")
        if g.owner != s.stream_owner[g.scope.stream]:
            raise TransitionError("grant issuer is not the stream owner")
        if (g.scope.stream, g.scope.epoch) not in s.scope_start:
            raise TransitionError("grant references non-activated scope")
        if g.grant_id in s.live_grants or g.grant_id in s.revoked:
            raise TransitionError("duplicate grant id")
        s.live_grants[g.grant_id] = g
        s.installed.setdefault(g.grant_id, set())

    elif isinstance(e, KFragInstalled):
        if e.grant_id not in s.live_grants:
            raise TransitionError("kfrag for non-live grant")
        g = s.live_grants[e.grant_id]
        if not (type(e.index) is int and 0 <= e.index < g.shares):
            raise TransitionError("kfrag index out of range")
        if e.proxy not in g.proxies:
            raise TransitionError("kfrag proxy not in grant")
        s.installed[e.grant_id].add(e.index)

    elif isinstance(e, CFragProduced):
        if e.grant_id not in s.live_grants and e.grant_id not in s.revoked:
            raise TransitionError("cfrag for unknown grant")

    elif isinstance(e, GrantRevoked):
        if e.grant_id not in s.live_grants:
            raise TransitionError("revoke of non-live grant")
        s.revoked[e.grant_id] = e.t
        del s.live_grants[e.grant_id]

    elif isinstance(e, OwnerAvailability):
        s.owner_online[e.owner] = e.online

    else:
        raise TransitionError(f"unknown event type {type(e).__name__}")

    return s


def fold_state(events: List[Event]) -> ManagementState:
    s = ManagementState()
    for e in events:
        s = apply_event(s, e)
    return s
