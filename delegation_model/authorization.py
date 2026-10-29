"""
Authorization state and key-scope state, as a deterministic fold over observable events.

Authorization state answers: at observation time `now`, which (recipient, record) pairs
are currently authorized, and which grants are live? Revocation and validity windows are
honoured here. This is the CURRENT ACL -- deliberately separate from retained capability.

Key-scope state answers: which scope (and scope key) covers a given record? Scopes are
half-open seq ranges per stream, created by ScopeActivated and closed by the next one.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from .types import Grant, GrantId, Record, Scope, ScopeKeyId, StreamId, Seq, RecipientId
from .events import (Event, StreamAuthorized, ScopeActivated, RecordProduced, GrantIssued,
                     GrantRevoked, is_observable)


@dataclass
class ScopeSpan:
    scope: Scope
    scope_key_id: ScopeKeyId
    start_seq: Seq
    end_seq: Optional[Seq] = None   # exclusive; None while this is the active scope


@dataclass
class AuthorizationState:
    live_grants: Dict[GrantId, Grant] = field(default_factory=dict)
    revoked: Dict[GrantId, int] = field(default_factory=dict)      # grant_id -> revoke time
    stream_producers: Dict[StreamId, set] = field(default_factory=dict)
    # per stream, ordered list of scope spans (by start_seq)
    scope_spans: Dict[StreamId, List[ScopeSpan]] = field(default_factory=dict)
    produced: Dict[StreamId, Seq] = field(default_factory=dict)   # stream -> next expected seq
    now: int = -1

    # ---- scope lookup ----
    def scope_of(self, r: Record) -> Optional[ScopeSpan]:
        for span in self.scope_spans.get(r.stream, []):
            if r.seq >= span.start_seq and (span.end_seq is None or r.seq < span.end_seq):
                return span
        return None

    # ---- current authorization (the ACL) ----
    def is_grant_live(self, g: Grant) -> bool:
        if g.grant_id in self.revoked:
            return False
        if self.now < g.valid_from:
            return False
        if g.valid_to is not None and self.now > g.valid_to:
            return False
        return True

    def authorized(self, recipient: RecipientId, r: Record) -> bool:
        """Is `recipient` currently authorized to read record `r`?"""
        for g in self.live_grants.values():
            if g.recipient != recipient:
                continue
            if not self.is_grant_live(g):
                continue
            if g.rng.contains(r) and self._record_in_scope(r, g.scope):
                return True
        return False

    def _record_in_scope(self, r: Record, scope: Scope) -> bool:
        span = self.scope_of(r)
        return span is not None and span.scope == scope


def fold_authorization(events: List[Event], now: Optional[int] = None) -> AuthorizationState:
    """Fold observable events up to and including logical time `now`.

    The observation time `now` is the authoritative clock for validity checks (review R7):
    it advances even across idle intervals with no event, so a grant expiring at t=5 is NOT
    live when queried at cutoff=10 even if the last event was at t=3. When `now` is None we
    use the last event time (whole-history view)."""
    st = AuthorizationState()
    last_t = -1
    for e in events:
        if not is_observable(e):
            continue                      # compromise events never touch authorization state
        if now is not None and e.t > now:
            break
        last_t = max(last_t, e.t)
        if isinstance(e, StreamAuthorized):
            st.stream_producers.setdefault(e.stream, set()).add(e.producer)
        elif isinstance(e, ScopeActivated):
            spans = st.scope_spans.setdefault(e.scope.stream, [])
            if spans and spans[-1].end_seq is None:
                spans[-1].end_seq = e.start_seq      # close the previous active scope
            spans.append(ScopeSpan(e.scope, e.scope_key_id, e.start_seq))
        elif isinstance(e, RecordProduced):
            st.produced[e.record.stream] = max(st.produced.get(e.record.stream, 0),
                                               e.record.seq + 1)
        elif isinstance(e, GrantIssued):
            st.live_grants[e.grant.grant_id] = e.grant
        elif isinstance(e, GrantRevoked):
            if e.grant_id in st.live_grants:
                st.revoked[e.grant_id] = e.t
    # The validity clock is the REQUESTED observation time, not the last event time.
    st.now = now if now is not None else last_t
    return st
