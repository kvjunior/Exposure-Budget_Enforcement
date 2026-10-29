"""
Delegation manager: observations -> proposed action -> conservative CHECKED-ACTION path.

Separation enforced here (brief sec 5 contracts; review R3/R4/R5/R6):
  - the POLICY proposes an action from OBSERVABLE history only (no compromise events, no
    future events, no honest secrets);
  - the CHECKED-ACTION path independently validates authority and authorization prerequisites
    AND conservatively evaluates the candidate action's possible capability-delivery effects
    against an exposure budget over a DECLARED coalition family, using OBSERVABLE history plus
    that public family only. Realized corruption stays in the evaluation channel; the checker
    never reads it. An optimizer can never override a cryptographic permission or fabricate
    owner authority.

This slice ships the checker and a fixed-epoch baseline. The proposed controller is NOT
implemented and must not be benchmarked; `policies.proposed_policy` returns UNSUPPORTED.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, FrozenSet
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from delegation_model.events import (Event, is_observable, GrantIssued, OwnerAvailability,
                                      ScopeActivated, StreamAuthorized, KFragInstalled,
                                      CFragProduced, RecordProduced)
from delegation_model.authorization import fold_authorization, AuthorizationState
from delegation_model.types import Grant, Scope, RecipientId, ProxyId, Record
from delegation_model.possible import CoalitionSpec


class ActionKind(Enum):
    ADMIT_GRANT = "admit_grant"       # install a requested grant now
    DEFER = "defer"                   # postpone (e.g. owner offline)
    REJECT = "reject"                 # decline with a reason
    ACTIVATE_SCOPE = "activate_scope" # roll a fresh key scope (needs owner authority/preauth)
    UNSUPPORTED = "unsupported"       # policy declined to decide (never benchmarked as done)


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    grant: Optional[Grant] = None
    scope: Optional[Scope] = None
    reason: str = ""
    # ACTIVATE_SCOPE freshness fields (review R6): a rollover must carry a NEW key id and a
    # start_seq that does not reassign already-produced records of the stream.
    new_scope_key_id: Optional[str] = None
    start_seq: Optional[int] = None
    # ADMIT_GRANT must declare the capability effects it authorizes (review R3): the share
    # indices that will be installed as kfrags (so the checker can evaluate possible delivery).
    authorized_kfrag_indices: Tuple[int, ...] = ()


@dataclass
class OwnerRegistry:
    """Authoritative owner<->stream binding (review R5). In this single-owner slice it is
    populated from StreamAuthorized events, which are treated as authentic at the model layer.
    The service boundary (not this slice) verifies the owner's signature on these records."""
    stream_owner: Dict[str, str] = field(default_factory=dict)
    def owner_of(self, stream: str) -> Optional[str]:
        return self.stream_owner.get(stream)


@dataclass
class Observation:
    """What the online controller is allowed to see: observable events up to the cutoff,
    the current authorization state, owner connectivity, and the owner<->stream registry.
    No compromise, no future."""
    cutoff: int
    events: List[Event]
    auth: AuthorizationState
    owner_online: bool
    registry: OwnerRegistry
    owner_online_by_id: Dict[str, bool] = field(default_factory=dict)

    def is_owner_online(self, owner: str) -> bool:
        return self.owner_online_by_id.get(owner, False)


def project_observation(events: List[Event], cutoff: int) -> Observation:
    obs_events = [e for e in events if is_observable(e) and e.t <= cutoff]
    auth = fold_authorization(obs_events, cutoff)
    reg = OwnerRegistry()
    for e in obs_events:
        if isinstance(e, StreamAuthorized):
            existing = reg.owner_of(e.stream)
            if existing is not None and existing != e.owner:
                raise ValueError("conflicting owners for stream " + e.stream)
            reg.stream_owner.setdefault(e.stream, e.owner)
    # Compatibility assumption of this model slice: a registered owner starts online
    # until an explicit availability event says otherwise. Keep one state PER owner.
    by_owner = {owner: True for owner in reg.stream_owner.values()}
    for e in obs_events:
        if isinstance(e, OwnerAvailability) and e.owner in by_owner:
            by_owner[e.owner] = e.online
    # Retained only for single-owner display compatibility. Decisions use the map.
    online = all(by_owner.values())
    return Observation(cutoff=cutoff, events=obs_events, auth=auth, owner_online=online,
                       registry=reg, owner_online_by_id=by_owner)


# ---------------- preauthorization: abstract vs verified ----------------
@dataclass(frozen=True)
class GrantToken:
    """An authentic preauthorization for ONE specific offline DELEGATION grant (item 3).

    A grant token is STRICTLY SCOPED and must name exactly what it authorizes: the owner, the
    recipient, the scope and record range, a validity window, and the permitted kfrag-delivery
    indices (the permitted effects). A scope-activation token (see PreAuth.scope_tokens) NEVER
    authorizes a delegation grant, and this token NEVER authorizes a scope activation. The two are
    separate so an offline owner who pre-authorized a rollover has not thereby authorized any new
    recipient's grant."""
    owner: str
    recipient: RecipientId
    stream: str
    epoch: int
    lo: int
    hi: Optional[int]                 # None = open-ended range
    # ISSUANCE window: when this token may be USED to issue a grant (the admission moment).
    issue_from: int
    issue_to: Optional[int]
    permitted_indices: Tuple[int, ...]
    # DELEGATED-ACCESS window (S2 obs): the grant's OWN validity must lie within this bound, so a
    # short issuance window cannot mint a grant valid for a much longer access window. None = any.
    access_from: Optional[int] = None
    access_to: Optional[int] = None

    def authorizes(self, g: Grant, indices: Tuple[int, ...], now: int) -> bool:
        if (self.owner, self.recipient, self.stream, self.epoch) != \
                (g.owner, g.recipient, g.scope.stream, g.scope.epoch):
            return False
        # the grant's range must be within the token's authorized range
        if g.rng.lo < self.lo:
            return False
        if self.hi is not None and (g.rng.hi is None or g.rng.hi > self.hi):
            return False
        # ISSUANCE window: the admission must happen within [issue_from, issue_to].
        if now < self.issue_from or (self.issue_to is not None and now > self.issue_to):
            return False
        # DELEGATED-ACCESS window: the grant's own validity must be within [access_from, access_to].
        if self.access_from is not None and g.valid_from < self.access_from:
            return False
        if self.access_to is not None and (g.valid_to is None or g.valid_to > self.access_to):
            return False
        # the delivered indices must be a subset of the permitted effects
        return set(indices) <= set(self.permitted_indices)


class PreAuth:
    """Preauthorization tokens. TWO DISJOINT kinds (item 3):
      - scope_tokens: permit specific offline SCOPE ACTIVATIONS, as (owner, stream, epoch).
      - grant_tokens: permit specific offline DELEGATION grants (GrantToken), fully scoped.
    A scope token can NEVER authorize a delegation grant and a grant token can NEVER authorize a
    scope activation; the checker consults only the matching kind.

    IMPORTANT (review R5): this is an ABSTRACT assumption object, NOT a signature-verification
    mechanism. `verified` records whether these tokens were produced by an actual authenticated
    check at the service boundary; the checker surfaces reliance on unverified tokens as an
    assumption. A real deployment sets verified=True only after Ed25519 verification of an
    owner-signed token (not implemented in this slice)."""
    def __init__(self, scope_tokens: Optional[set] = None, verified: bool = False,
                 grant_tokens: Optional[Tuple["GrantToken", ...]] = None):
        self.scope_tokens = scope_tokens or set()
        self.grant_tokens = tuple(grant_tokens or ())
        self.verified = verified

    # backward-compatible alias: old callers pass the scope-token set positionally.
    @property
    def tokens(self):
        return self.scope_tokens

    def permits_scope(self, owner: str, scope: Scope) -> bool:
        return (owner, scope.stream, scope.epoch) in self.scope_tokens

    def permits_grant(self, g: Grant, indices: Tuple[int, ...], now: int) -> bool:
        return any(t.authorizes(g, indices, now) for t in self.grant_tokens)


# ---------------- checked-action path ----------------
@dataclass
class CheckResult:
    ok: bool
    reason: str = ""
    assumptions: Tuple[str, ...] = ()
    exposure_reason: str = ""


def check_action(action: Action, obs: Observation, preauth: PreAuth,
                 exposure_budget=None, coalition_family: Optional[List[CoalitionSpec]] = None,
                 weights: Optional[Dict[Record, float]] = None) -> CheckResult:
    """Single checked-action path. Enforces authority + authorization prerequisites, then, for
    capability-delivering actions, conservatively evaluates the candidate's POSSIBLE exposure
    effects over the declared coalition family (review R3). Uses observable history + the public
    family only; never reads realized corruption.

    exposure_budget / coalition_family / weights are required to gate an ADMIT_GRANT that would
    deliver fragments; if omitted, an ADMIT that declares kfrag effects is REFUSED (we never
    silently skip the exposure gate)."""
    assumptions: Tuple[str, ...] = ()
    if not preauth.verified and (preauth.tokens or preauth.grant_tokens):
        assumptions = assumptions + ("preauth tokens are ASSUMED authentic (no signature "
                                     "verification in this slice)",)

    if action.kind == ActionKind.UNSUPPORTED:
        return CheckResult(False, "policy returned UNSUPPORTED (not a completed decision)")
    if action.kind in (ActionKind.DEFER, ActionKind.REJECT):
        return CheckResult(True, action.reason or action.kind.value, assumptions)

    if action.kind == ActionKind.ADMIT_GRANT:
        g = action.grant
        if g is None:
            return CheckResult(False, "admit_grant without a grant", assumptions)
        # R5: the grant issuer must be the registered owner of the stream.
        registered = obs.registry.owner_of(g.scope.stream)
        if registered is None:
            return CheckResult(False, "grant on an unregistered stream (no authorized owner)",
                               assumptions)
        if g.owner != registered:
            return CheckResult(False,
                               f"issuer {g.owner!r} does not own stream {g.scope.stream!r} "
                               f"(registered owner {registered!r})", assumptions)
        # owner must be online to create new grant authority, UNLESS an authentic grant token
        # (item 3) pre-authorizes THIS specific recipient/scope/range/validity/effects. A
        # scope-activation token does NOT suffice here; only a GrantToken does.
        if not obs.is_owner_online(registered):
            if not preauth.permits_grant(g, tuple(action.authorized_kfrag_indices), obs.cutoff):
                return CheckResult(False, "owner offline: cannot create new grant authorization "
                                   "(no grant preauthorization token matches this recipient/scope/"
                                   "range/validity/effects)", assumptions)
            assumptions = assumptions + ("offline grant authorized by a scoped grant token "
                                         "(recipient/scope/range/validity/effects matched)",)
        # the grant's scope must already be an activated scope
        spans = obs.auth.scope_spans.get(g.scope.stream, [])
        if not any(s.scope == g.scope for s in spans):
            return CheckResult(False, "grant references a scope not yet activated", assumptions)
        if g.grant_id in obs.auth.live_grants:
            return CheckResult(False, "new admission reuses an existing grant id", assumptions)
        indices = action.authorized_kfrag_indices
        if any(type(i) is not int or not 0 <= i < g.shares for i in indices):
            return CheckResult(False, "invalid share index in delivery plan", assumptions)
        if len(indices) != len(set(indices)):
            return CheckResult(False, "duplicate share index in delivery plan", assumptions)
        # R3: evaluate the candidate's possible capability-delivery effect on exposure.
        # The action authorizes installing kfrags at `authorized_kfrag_indices`; we check the
        # worst-case exposure AFTER that hypothetical installation, over the declared family.
        if action.authorized_kfrag_indices:
            if exposure_budget is None or coalition_family is None:
                return CheckResult(False, "ADMIT delivers kfrags but no exposure budget / "
                                   "coalition family supplied to gate it", assumptions)
            if not coalition_family or any(not isinstance(s, CoalitionSpec)
                                           for s in coalition_family):
                return CheckResult(False, "require a nonempty family of concrete CoalitionSpec "
                                   "objects; labels alone do not define adversary reach", assumptions)
            if len({s.label for s in coalition_family}) != len(coalition_family):
                return CheckResult(False, "coalition labels must be unique", assumptions)
            import math
            if any(not math.isfinite(w) or w < 0 for w in (weights or {}).values()):
                return CheckResult(False, "weights must be finite and nonnegative", assumptions)
            verdict = _exposure_after_admit(action, obs, exposure_budget, coalition_family,
                                            weights or {})
            if not verdict.ok:
                return CheckResult(False, "admission would breach exposure budget",
                                   assumptions, verdict.reason)
            return CheckResult(True, "admissible grant within exposure budget", assumptions,
                               verdict.reason)
        return CheckResult(True, "admissible grant (no fragment delivery declared)", assumptions)

    if action.kind == ActionKind.ACTIVATE_SCOPE:
        sc = action.scope
        if sc is None:
            return CheckResult(False, "activate_scope without a scope", assumptions)
        # R5: must be the registered owner's stream
        registered = obs.registry.owner_of(sc.stream)
        if registered is None:
            return CheckResult(False, "activation on an unregistered stream", assumptions)
        # R6: the scope must be FRESH -- not already activated -- and carry a new key id and a
        # start_seq that does not reassign already-produced records.
        spans = obs.auth.scope_spans.get(sc.stream, [])
        if any(s.scope == sc for s in spans):
            return CheckResult(False, "scope already activated: not a fresh rollover",
                               assumptions)
        if action.new_scope_key_id is None or action.start_seq is None:
            return CheckResult(False, "rollover missing fresh key id or start_seq", assumptions)
        if any(s.scope_key_id == action.new_scope_key_id for s in spans):
            return CheckResult(False, "scope key id reused: not fresh", assumptions)
        produced_next = obs.auth.produced.get(sc.stream, 0)
        if type(action.start_seq) is not int or action.start_seq != produced_next:
            return CheckResult(False,
                               f"immediate activation requires start_seq == next sequence "
                               f"{produced_next}; received {action.start_seq}", assumptions)
        if obs.is_owner_online(registered):
            return CheckResult(True, "fresh scope activation (owner online)", assumptions)
        if preauth.permits_scope(registered, sc):
            r = "fresh offline activation authorized by preauth token"
            return CheckResult(True, r, assumptions)
        return CheckResult(False, "owner offline and no preauth: cannot activate scope",
                           assumptions)

    return CheckResult(False, f"unknown action kind {action.kind}", assumptions)


def _exposure_after_admit(action: Action, obs: Observation, budget, coalition_family, weights):
    """Evaluate ALL historical material plus candidate effects for each public reach.

    No corruption events, real or invented, enter this path. The same CoalitionSpec
    is used for the complete observable history and the candidate's declared effects.
    This is a pure counterfactual checker, not an atomic executor or security proof.
    """
    from delegation_model.possible import possible_exposure
    from delegation_model.events import GrantIssued as GI, KFragInstalled as KI
    from delegation_manager.exposure_check import ExposureVerdict
    g = action.grant
    base = list(obs.events)                       # observable only
    t0 = obs.cutoff + 1
    hypo = base + [GI(t0, g)]
    tt = t0 + 1
    for i in action.authorized_kfrag_indices:
        proxy = g.proxies[i]             # indices were validated before this call
        hypo.append(KI(tt, g.grant_id, proxy, i)); tt += 1
    # S2-01 repair: a declared coalition's recipient SET is the set the adversary MAY corrupt;
    # collateral exposure is NOT monotone in recipient reach, so we must check each EXACT-recipient
    # subset (fixing R exactly, over-approximating only proxies). expand_family does this.
    from delegation_model.coverage import expand_family
    cases = expand_family(list(coalition_family),
                          recipients_are_exact=getattr(action, "recipients_are_exact", False))
    worst_future = 0; worst_past = 0.0
    future_witness = None; past_witness = None
    for spec in sorted(cases, key=lambda s: s.label):
        x = possible_exposure(hypo, spec, tt - 1, weights)
        if len(x.future_scopes) > worst_future:
            worst_future = len(x.future_scopes); future_witness = spec.label
        if x.past > worst_past:
            worst_past = x.past; past_witness = spec.label
    ok = (worst_future <= budget.max_future_scopes and worst_past <= budget.max_past_weight)
    reason = (f"worst-case over family: future_scopes={worst_future}, past={worst_past} "
              f"(future witness {future_witness}, past witness {past_witness}); "
              f"budget future<={budget.max_future_scopes}, "
              f"past<={budget.max_past_weight}")
    return ExposureVerdict(ok=ok, worst_coalition=future_witness or past_witness,
                           worst_future_scopes=worst_future, worst_past=worst_past,
                           owner_root_coalitions=[], reason=reason,
                           future_witness=future_witness, past_witness=past_witness)
