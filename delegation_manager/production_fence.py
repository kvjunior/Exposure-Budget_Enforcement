"""
Concrete production fencing (P3D, Task 2).

Replaces the scripted P3B rotation barrier with an ENFORCED reservation mechanism. Production is
modeled as a REQUEST that must pass the fence; the data plane cannot bind a record to a scope the
fence has not cleared. The fence has production-time access to actual state (it is co-located with
production), which is exactly what lets it succeed where the delayed-public-report online gate
cannot (see docs/dichotomy_spine.md, corrected Theorem 1/2).

Ordering per production request (atomic from the fence's view; no time-of-check/time-of-use gap
because the fence holds the reservation and performs the rotation itself before binding):
    reserve -> actual-reconstructibility check of the target scope
            -> if safe: bind to current scope, produce, report
            -> if unsafe: rotate to a fresh scope (owner online or valid preauth), then bind/produce
            -> if rotation cannot complete: DEFER (retry later) or REJECT (drop) -- no production
               under a reconstructible scope ever occurs.

SCOPE OF THE GUARANTEE (stated honestly):
  - This fence prevents PRODUCTION-TIME disclosure: a record is never bound to a scope that is
    actually reconstructible at its production tick. It directly blocks the Theorem-1 delayed-
    production breach.
  - It does NOT by itself prevent RETROACTIVE disclosure by a FUTURE grant on the record's scope
    (counterexample CE-RETRO): that requires the complementary admission-side rule
    `admission_would_retroactively_disclose` below, which the manager must also honor. The fence
    exposes that check; enforcing it on every grant is the ongoing whole-run invariant.
  - Confidentiality that a reconstructible scope's key opens its records is the ASSUMED closure
    soundness (PO1), a computational assumption; the fence logic itself is model-level.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

from delegation_model.types import Record, Scope
from delegation_model.service_clock import ServiceTime
from delegation_model.timed_log import ScopeNotice
from delegation_model.timed_capabilities import openability, family_cases


class FenceOutcome(Enum):
    PRODUCE_CURRENT = "produce_current"       # scope safe; bound to current scope
    ROTATE_THEN_PRODUCE = "rotate_then_produce"
    DEFER = "defer"                           # unsafe + cannot rotate now; retry later
    REJECT = "reject"                         # unsafe + cannot rotate at all; drop the record


@dataclass
class FenceDecision:
    outcome: FenceOutcome
    target_scope: Optional[Scope]             # the scope the record WOULD bind to (after any rotation)
    rotated: bool
    reason: str
    rotation_ticks: int = 0


def scope_reconstructible(state, family, scope: Scope) -> bool:
    """Actual reconstructibility of `scope` by ANY declared coalition, from the given CapabilityState
    (use the simulator's ACTUAL/truth state). True iff some family case holds >= threshold raw shares
    of a grant on `scope` to proxies it reaches."""
    for case in family_cases(family):
        exposed, _ = openability(state, case.recipients, case.proxies)
        if scope in exposed:
            return True
    return False


def active_scope_on(state, stream: str) -> Optional[Scope]:
    """The current (highest-epoch) scope on `stream` in the given state."""
    scopes = [s.scope for s in state.scopes if s.scope.stream == stream]
    return max(scopes, key=lambda sc: sc.epoch) if scopes else None


def admission_would_retroactively_disclose(state, family, grant, delivered_indices) -> List[Record]:
    """Admission-side counterpart of the fence (CE-RETRO). Returns the records that WOULD become
    collateral (opened but not authorized by `grant`) if `grant`'s scope were made reconstructible
    by delivering `delivered_indices`. The manager must refuse/withhold such a delivery to maintain
    the whole-run invariant. This uses ACTUAL state (closing the observability gap that let CE-RETRO
    through the public-view gate)."""
    scope = grant.scope
    under_scope = [n.record for n, _ in state.records if n.scope == scope]
    in_range = [r for r in under_scope if grant.rng.contains(r)]
    # if the delivered indices reach threshold, the whole scope opens
    if len(set(delivered_indices)) < grant.threshold:
        return []
    collateral = [r for r in under_scope if r not in in_range]
    return sorted(collateral)


@dataclass
class FenceLog:
    decisions: List[FenceDecision] = field(default_factory=list)
    rotations: int = 0
    deferred: int = 0
    rejected: int = 0
    total_rotation_ticks: int = 0

    def record(self, d: FenceDecision):
        self.decisions.append(d)
        if d.rotated:
            self.rotations += 1
            self.total_rotation_ticks += d.rotation_ticks
        if d.outcome == FenceOutcome.DEFER:
            self.deferred += 1
        if d.outcome == FenceOutcome.REJECT:
            self.rejected += 1


def decide_fence(state, family, stream: str, owner_online: bool, preauth_ok: bool,
                 rotation_ticks: int = 1, next_epoch: Optional[int] = None,
                 next_key_id: Optional[str] = None, next_start_seq: Optional[int] = None,
                 can_reject: bool = True) -> FenceDecision:
    """Pure fence decision for producing a record on `stream`, given the actual state.
    Does not mutate anything; returns what the driver should do."""
    cur = active_scope_on(state, stream)
    if cur is None:
        return FenceDecision(FenceOutcome.REJECT, None, False, "no active scope on stream")
    if not scope_reconstructible(state, family, cur):
        return FenceDecision(FenceOutcome.PRODUCE_CURRENT, cur, False, "active scope not reconstructible")
    # unsafe: must rotate to a fresh scope first
    if owner_online or preauth_ok:
        fresh = Scope(stream, (next_epoch if next_epoch is not None else cur.epoch + 1))
        return FenceDecision(FenceOutcome.ROTATE_THEN_PRODUCE, fresh, True,
                             "active scope reconstructible; rotating to a fresh scope before binding",
                             rotation_ticks=rotation_ticks)
    # cannot rotate now
    if can_reject:
        return FenceDecision(FenceOutcome.REJECT, None, False,
                             "active scope reconstructible and owner offline/no preauth: REJECT production")
    return FenceDecision(FenceOutcome.DEFER, None, False,
                         "active scope reconstructible and owner offline/no preauth: DEFER production")
