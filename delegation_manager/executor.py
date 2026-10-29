"""Process-local checked reference executor — Slice 2.2.1.

Approval and execution use exactly cutoff+1 event times. A noncanonical t0 is
refused; a changed cutoff, history, action or preauth/config context cannot
commit. Execution reconstructs observation state and reruns the complete
checker before comparing/committing the exact event/effect plan.

This returns a pure reference state/outbox. It is not durable atomic I/O, a
concurrent distributed transaction, a signature, or a deployed service.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib, json
from typing import List, Optional, Tuple
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from delegation_model.events import Event, GrantIssued, KFragInstalled, ScopeActivated
from delegation_model.transitions import ManagementState, apply_event, TransitionError
from delegation_model.effects import Effect, Backend, threshold_pre_grant_effects
from delegation_model.types import Grant, Scope
from .manager import Action, ActionKind


def _action_digest(action: Action) -> str:
    g = action.grant
    payload = {
        "kind": action.kind.value,
        "grant": None if g is None else {
            "grant_id": g.grant_id, "owner": g.owner, "recipient": g.recipient,
            "scope": [g.scope.stream, g.scope.epoch],
            "rng": [g.rng.stream, g.rng.lo, g.rng.hi],
            "threshold": g.threshold, "shares": g.shares, "proxies": list(g.proxies),
            "valid_from": g.valid_from, "valid_to": g.valid_to},
        "scope": None if action.scope is None else [action.scope.stream, action.scope.epoch],
        "new_scope_key_id": action.new_scope_key_id, "start_seq": action.start_seq,
        "indices": list(action.authorized_kfrag_indices),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def config_digest(budget, family, weights, preauth=None) -> str:
    def spec_key(s):
        return [s.label, sorted(s.proxies), sorted(s.recipients)]
    payload = {
        "budget": [getattr(budget, "max_future_scopes", None),
                   getattr(budget, "max_past_weight", None)] if budget else None,
        "family": sorted([spec_key(s) for s in (family or [])]),
        "weights": sorted([[r.stream, r.seq, w] for r, w in (weights or {}).items()]),
        "preauth": {
            "scope_tokens": sorted([list(t) for t in getattr(preauth, "scope_tokens", ())]),
            "grant_tokens": [_canon(t) for t in getattr(preauth, "grant_tokens", ())],
            "verified": bool(getattr(preauth, "verified", False)),
        },
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class ApprovalReceipt:
    """A checker-issued approval boundary (F01 repair). Minted ONLY by approve(), which runs the
    full checker; it binds the CHECKED OBSERVABLE-LOG digest (not just a version number), the full
    action, the config (budget/family/weights), the cutoff, and the planned events/effects. A
    receipt cannot be forged by passing authority_ok=True, and it does not match a different
    history (the log digest differs) even at the same time/version."""
    action_digest: str
    log_digest: str            # hash of the CHECKED observable event log (history identity)
    at_version: int
    cutoff: int
    config_digest: str
    planned_events: Tuple[Event, ...]
    planned_effects: Tuple[Effect, ...]
    checked_ok: bool           # the checker's OWN verdict (authority + exposure), not a caller flag
    check_reason: str = ""


def _planned_events_and_effects(action: Action, state: ManagementState, t0: int):
    if action.kind == ActionKind.ADMIT_GRANT:
        g: Grant = action.grant
        idx = tuple(action.authorized_kfrag_indices)
        events: List[Event] = [GrantIssued(t0, g)]
        tt = t0 + 1
        for i in idx:
            events.append(KFragInstalled(tt, g.grant_id, g.proxies[i], i)); tt += 1
        effects = list(threshold_pre_grant_effects(g.grant_id, g.scope, g.proxies, idx))
        return events, effects
    if action.kind == ActionKind.ACTIVATE_SCOPE:
        ev = ScopeActivated(t0, state.stream_owner.get(action.scope.stream, "O"),
                            action.scope, action.new_scope_key_id, action.start_seq)
        return [ev], []
    return [], []


def _log_digest(obs_events) -> str:
    """Stable digest of the observable event log (history identity). Uses each event's type and a
    canonical field snapshot so two histories that differ anywhere produce different digests."""
    import dataclasses
    parts = []
    for e in obs_events:
        d = {"_t": type(e).__name__}
        for f in dataclasses.fields(e):
            v = getattr(e, f.name)
            d[f.name] = _canon(v)
        parts.append(d)
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()


def _canon(v):
    # canonicalise nested dataclasses (Record, Scope, RecordRange, Grant) to tuples/lists
    import dataclasses
    if dataclasses.is_dataclass(v) and not isinstance(v, type):
        return [type(v).__name__] + [_canon(getattr(v, f.name)) for f in dataclasses.fields(v)]
    if isinstance(v, (list, tuple)):
        return [_canon(x) for x in v]
    return v


def _current_observation(obs):
    """Rebuild derived state from a valid observable prefix at an explicit logical cutoff.

    Idle logical cutoffs are allowed, but events may not be hidden or later than
    that cutoff. No wall-clock arrival/queue semantics are implied.
    """
    from delegation_model.events import is_observable
    from delegation_model.validation import validate_history
    from .manager import project_observation
    if type(obs.cutoff) is not int or obs.cutoff < -1:
        raise ValueError("observation cutoff must be an integer >= -1")
    events = list(obs.events)
    if any(not is_observable(e) or e.t > obs.cutoff for e in events):
        raise ValueError("executor requires an observable prefix at the cutoff")
    validate_history(events)
    return project_observation(events, obs.cutoff)


def _canonical_time(obs, t0):
    wanted = obs.cutoff + 1
    if t0 is not None and (type(t0) is not int or t0 != wanted):
        raise ValueError(f"action must begin at cutoff + 1 = {wanted}")
    return wanted


def approve(action: Action, obs, budget=None, family=None, weights=None,
            preauth=None, t0: Optional[int] = None) -> ApprovalReceipt:
    """Mint an approval by RUNNING the checker (F01). `obs` is the Observation the action was
    checked against (it carries the observable event log and cutoff). The receipt's checked_ok is
    the checker's own verdict; there is no caller-supplied authority flag. The receipt binds the
    observable-log digest, so a receipt from one history will not match a different history."""
    from delegation_manager.manager import check_action, PreAuth
    from delegation_model.transitions import fold_state
    obs = _current_observation(obs)
    preauth = preauth or PreAuth()
    t0 = _canonical_time(obs, t0)
    res = check_action(action, obs, preauth, budget, family, weights)
    # derive the state the events are planned against from the observable log
    state = fold_state(list(obs.events))
    # Do not attempt to build an invalid/absent grant or out-of-range effects
    # after a checker refusal. In particular, malformed indices cannot crash
    # approval while indexing g.proxies.
    events, effects = _planned_events_and_effects(action, state, t0) if res.ok else ([], [])
    return ApprovalReceipt(action_digest=_action_digest(action),
                           log_digest=_log_digest(obs.events),
                           at_version=state.version, cutoff=obs.cutoff,
                           config_digest=config_digest(budget, family, weights, preauth),
                           planned_events=tuple(events), planned_effects=tuple(effects),
                           checked_ok=res.ok, check_reason=res.reason)


@dataclass
class ExecutionResult:
    committed: bool
    reason: str
    state: ManagementState
    outbox: Tuple[Effect, ...] = ()
    log_appended: Tuple[Event, ...] = ()


def execute(action: Action, obs, receipt: ApprovalReceipt,
            budget=None, family=None, weights=None, t0: Optional[int] = None,
            preauth=None) -> ExecutionResult:
    """Execute under a checker-issued receipt bound to THIS observable log (F01). `obs` is the
    CURRENT observation; if its log digest differs from the receipt's (a different history, even at
    the same time/version), execution is refused. A receipt whose checker verdict was False never
    commits."""
    from delegation_model.transitions import fold_state
    from .manager import check_action, PreAuth
    obs = _current_observation(obs)
    preauth = preauth or PreAuth()
    state = fold_state(list(obs.events))
    if receipt.cutoff != obs.cutoff:
        return ExecutionResult(False, "observation cutoff changed since approval", state)
    try:
        t0 = _canonical_time(obs, t0)
    except ValueError as ex:
        return ExecutionResult(False, str(ex), state)
    if not receipt.checked_ok:
        return ExecutionResult(False, "receipt's checker verdict was NOT ok (authority or exposure "
                               "failed at approval)", state)
    if receipt.log_digest != _log_digest(obs.events):
        return ExecutionResult(False, "receipt bound to a DIFFERENT observable history "
                               "(cross-history replay rejected)", state)
    if receipt.action_digest != _action_digest(action):
        return ExecutionResult(False, "receipt does not bind this exact action "
                               "(substitution rejected)", state)
    if receipt.at_version != state.version:
        return ExecutionResult(False, f"stale: receipt at v{receipt.at_version}, "
                               f"state at v{state.version}", state)
    if receipt.config_digest != config_digest(budget, family, weights, preauth):
        return ExecutionResult(False, "budget/family/weights/preauth context changed since approval", state)
    current_check = check_action(action, obs, preauth, budget, family, weights)
    if not current_check.ok:
        return ExecutionResult(False, "commit-time check refused: " + current_check.reason, state)
    if action.kind in (ActionKind.DEFER, ActionKind.REJECT, ActionKind.UNSUPPORTED):
        return ExecutionResult(False, f"{action.kind.value}: nothing to deliver", state)
    events, delivered = _planned_events_and_effects(action, state, t0)
    if tuple(events) != receipt.planned_events or tuple(delivered) != receipt.planned_effects:
        return ExecutionResult(False, "planned events/effects differ from the approved plan", state)
    s = state
    try:
        for e in events:
            s = apply_event(s, e)
    except TransitionError as ex:
        return ExecutionResult(False, f"transition rejected: {ex}", state)
    return ExecutionResult(True, "committed", s, outbox=tuple(delivered),
                           log_appended=tuple(events))
