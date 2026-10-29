"""
Strict history validation (P2, review step 1).

A valid history is a precondition for every model claim. This rejects malformed input rather than
silently folding it (slice 1.1's loader did minimal checks). Checks:
  - events strictly ordered by t, no duplicate t (the model assumes a linearised log);
  - no conflicting stream owners;
  - scope activations are fresh (new scope, unused key id) and start at the running next-seq
    (immediate activation; future-start scheduling is out of model, consistent with S11-03);
  - records produced on a stream are produced under an active scope, in nondecreasing seq, no
    duplicate (stream, seq);
  - grants reference an activated scope and a registered owner; share indices are well-formed;
  - kfrag installs reference a known grant and a valid share index and proxy;
  - revocation references a known grant.
Raises ValueError with a precise message on the first violation.
"""
from __future__ import annotations
from typing import Dict, List, Optional, Set, Tuple
from .types import Scope, Record
from .events import (Event, StreamAuthorized, ScopeActivated, RecordProduced, GrantIssued,
                     GrantRevoked, KFragInstalled, CFragProduced, OwnerAvailability,
                     is_observable)


def validate_history(events: List[Event]) -> None:
    last_t: Optional[int] = None
    stream_owner: Dict[str, str] = {}
    scope_keys: Set[str] = set()
    active_scope: Dict[str, Scope] = {}
    scope_start: Dict[Tuple[str, int], int] = {}
    next_seq: Dict[str, int] = {}
    produced: Set[Record] = set()
    grants: Dict[str, GrantIssued] = {}
    revoked: Set[str] = set()

    for e in events:
        # ordering
        if last_t is not None and e.t <= last_t:
            raise ValueError(f"events must be strictly increasing in t; {e.t} after {last_t}")
        last_t = e.t

        if isinstance(e, StreamAuthorized):
            if e.stream in stream_owner and stream_owner[e.stream] != e.owner:
                raise ValueError(f"conflicting owners for stream {e.stream!r}")
            stream_owner[e.stream] = e.owner

        elif isinstance(e, ScopeActivated):
            if e.scope.stream not in stream_owner:
                raise ValueError(f"scope on unregistered stream {e.scope.stream!r}")
            if e.scope_key_id in scope_keys:
                raise ValueError(f"reused scope key id {e.scope_key_id!r}")
            cur = active_scope.get(e.scope.stream)
            if cur is not None and e.scope == cur:
                raise ValueError(f"scope {e.scope} already active")
            want = next_seq.get(e.scope.stream, 0)
            if e.start_seq != want:
                raise ValueError(f"scope start_seq {e.start_seq} must equal next seq {want} "
                                 f"(immediate activation only)")
            scope_keys.add(e.scope_key_id)
            active_scope[e.scope.stream] = e.scope
            scope_start[(e.scope.stream, e.scope.epoch)] = e.start_seq

        elif isinstance(e, RecordProduced):
            st = e.record.stream
            if st not in active_scope:
                raise ValueError(f"record on stream {st!r} with no active scope")
            want = next_seq.get(st, 0)
            if e.record.seq != want:
                raise ValueError(f"record seq {e.record.seq} must equal next seq {want}")
            if e.record in produced:
                raise ValueError(f"duplicate record {e.record}")
            produced.add(e.record)
            next_seq[st] = want + 1

        elif isinstance(e, GrantIssued):
            g = e.grant
            if g.scope.stream not in stream_owner:
                raise ValueError(f"grant on unregistered stream {g.scope.stream!r}")
            if g.owner != stream_owner[g.scope.stream]:
                raise ValueError(f"grant issuer {g.owner!r} is not the stream owner")
            if active_scope.get(g.scope.stream) != g.scope and \
                    (g.scope.stream, g.scope.epoch) not in scope_start:
                raise ValueError(f"grant references non-activated scope {g.scope}")
            if g.grant_id in grants:
                raise ValueError(f"duplicate grant id {g.grant_id!r}")
            if not (1 <= g.threshold <= g.shares) or len(g.proxies) != g.shares:
                raise ValueError(f"grant {g.grant_id!r} has malformed threshold/shares/proxies")
            grants[g.grant_id] = e

        elif isinstance(e, KFragInstalled):
            if e.grant_id not in grants:
                raise ValueError(f"kfrag for unknown grant {e.grant_id!r}")
            g = grants[e.grant_id].grant
            if not (type(e.index) is int and 0 <= e.index < g.shares):
                raise ValueError(f"kfrag index {e.index} out of range for grant {e.grant_id!r}")
            if e.proxy not in g.proxies:
                raise ValueError(f"kfrag proxy {e.proxy!r} not in grant {e.grant_id!r}")

        elif isinstance(e, CFragProduced):
            if e.grant_id not in grants:
                raise ValueError(f"cfrag for unknown grant {e.grant_id!r}")
            g = grants[e.grant_id].grant
            if not (type(e.index) is int and 0 <= e.index < g.shares):
                raise ValueError(f"cfrag index {e.index} out of range for grant {e.grant_id!r}")

        elif isinstance(e, GrantRevoked):
            if e.grant_id not in grants:
                raise ValueError(f"revoke of unknown grant {e.grant_id!r}")
            revoked.add(e.grant_id)


def is_valid_history(events: List[Event]) -> bool:
    try:
        validate_history(events)
        return True
    except ValueError:
        return False
