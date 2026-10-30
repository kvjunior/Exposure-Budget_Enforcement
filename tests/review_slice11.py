#!/usr/bin/env python3
"""Independent slice-1.1 contract checks. Exit 1 = violated contract; 2 = cannot run.

This is a reviewer harness, not a replacement model, security proof, or benchmark.
Run against an extracted source directory; no third-party packages are required.
The uploaded code is imported without alteration. JSON records counterexamples.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
import sys
import traceback


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--family-api", choices=["labels", "specs"], default="labels",
                        help="slice 1.1 uses labels; corrected branch uses typed reach specs")
    args = parser.parse_args()
    source = args.source.resolve()
    sys.path.insert(0, str(source))
    from delegation_model.types import Grant, Record, RecordRange, Scope
    from delegation_model.events import (
        StreamAuthorized, ScopeActivated, RecordProduced, GrantIssued,
        GrantRevoked, KFragInstalled, CorruptRecipient, DiscloseDataKey,
        OwnerAvailability,
    )
    from delegation_model.authorization import fold_authorization
    from delegation_model.closure import accumulate, conservative_closure, exposure
    from delegation_model.possible import CoalitionSpec, possible_exposure
    from delegation_manager.manager import (
        Action, ActionKind, PreAuth, project_observation, check_action,
    )
    from delegation_manager.exposure_check import ExposureBudget

    results = []

    def family(spec):
        return [spec] if args.family_api == "specs" else [spec.label]

    def record(cid, satisfied, details, category="contract"):
        results.append({"id": cid, "category": category,
                        "property_satisfied": bool(satisfied), "details": details})
        print(f"[{'PASS' if satisfied else 'FAIL'}] {cid}: "
              + json.dumps(details, sort_keys=True))

    def grant(gid, stream, recipient, proxies, *, valid_from=0, valid_to=None):
        return Grant(gid, "O", recipient, Scope(stream, 0),
                     RecordRange(stream, 0, 1), 2, 3, tuple(proxies),
                     valid_from, valid_to)

    # S11-01: Two streams, one concrete public coalition. Before: 1 exposed
    # active scope (within budget 1). A new grant adds a second exposed scope.
    # The guard instead hypothesizes corruption of only the NEW grant's parties,
    # forgetting the OLD recipient/proxies in that same allowed coalition.
    old = grant("OLD", "b", "R_old", ("p0", "p1", "p2"))
    candidate = grant("NEW", "a", "R_new", ("q0", "q1", "q2"))
    history = [
        StreamAuthorized(0, "O", "a", "Da"),
        StreamAuthorized(1, "O", "b", "Db"),
        ScopeActivated(2, "O", Scope("a", 0), "a.k0", 0),
        ScopeActivated(3, "O", Scope("b", 0), "b.k0", 0),
        RecordProduced(4, Record("a", 0)),
        RecordProduced(5, Record("b", 0)),
        GrantIssued(6, old), KFragInstalled(7, "OLD", "p0", 0),
        KFragInstalled(8, "OLD", "p1", 1),
    ]
    spec = CoalitionSpec("C", proxies={"p0", "p1", "q0", "q1"},
                         recipients={"R_old", "R_new"})
    before = possible_exposure(history, spec, 8, {})
    action = Action(ActionKind.ADMIT_GRANT, grant=candidate,
                    authorized_kfrag_indices=(0, 1))
    verdict = check_action(action, project_observation(history, 8), PreAuth(),
                           ExposureBudget(1, 0), family(spec), {})
    post = history + [GrantIssued(9, candidate),
                      KFragInstalled(10, "NEW", "q0", 0),
                      KFragInstalled(11, "NEW", "q1", 1)]
    after = possible_exposure(post, spec, 11, {})
    assert len(before.future_scopes) == 1 and len(after.future_scopes) == 2
    record("S11-01_history_and_family", not verdict.ok, {
        "allowed_coalition": {"proxies": sorted(spec.proxies),
                              "recipients": sorted(spec.recipients)},
        "budget_future_scopes": 1,
        "pre_future_scopes": len(before.future_scopes),
        "post_future_scopes": len(after.future_scopes),
        "pre_past_weight": before.past, "post_past_weight": after.past,
        "guard_accepts": verdict.ok, "guard_exposure": verdict.exposure_reason,
        "family_api": args.family_api,
    })

    # S11-02: A recipient has an unambiguous data-key disclosure. A grant is
    # issued for a future valid_from, then revoked BEFORE it ever becomes live.
    # It must not exempt the disclosed record from collateral exposure.
    future = grant("NEVER_LIVE", "g", "R", ("p0", "p1", "p2"), valid_from=20)
    r = Record("g", 0)
    temporal = [StreamAuthorized(0, "O", "g", "D"),
                ScopeActivated(1, "O", Scope("g", 0), "g.k0", 0),
                RecordProduced(2, r), GrantIssued(3, future),
                CorruptRecipient(4, "R", "C"), DiscloseDataKey(5, r, "C"),
                GrantRevoked(6, "NEVER_LIVE")]
    auth = fold_authorization(temporal, 10)
    k = accumulate(temporal, "C", 10, auth)
    x = exposure(k, temporal, 10, {r: 1.0}, auth)
    assert not any(fold_authorization(temporal, t).authorized("R", r)
                   for t in range(11))
    record("S11-02_never_live_authorization", x.past == 1.0, {
        "issue_time": 3, "valid_from": 20, "revoke_time": 6, "cutoff": 10,
        "ever_live_by_cutoff": False, "data_key_known": True,
        "expected_past_weight": 1.0, "observed_past_weight": x.past,
    })

    # S11-03: A future start_seq does not make the old key stop covering the
    # intervening UNPRODUCED records. The code marks only the last span future-
    # exposed, so a scheduled activation can make the risk disappear on paper.
    g = grant("G", "g", "R", ("p0", "p1", "p2"))
    roll_history = [StreamAuthorized(0, "O", "g", "D"),
                    ScopeActivated(1, "O", Scope("g", 0), "g.k0", 0),
                    RecordProduced(2, r), GrantIssued(3, g),
                    KFragInstalled(4, "G", "p0", 0),
                    KFragInstalled(5, "G", "p1", 1), GrantRevoked(6, "G")]
    reach = CoalitionSpec("C", proxies={"p0", "p1"}, recipients={"R"})
    roll = Action(ActionKind.ACTIVATE_SCOPE, scope=Scope("g", 1),
                  new_scope_key_id="g.k1", start_seq=100)
    roll_check = check_action(roll, project_observation(roll_history, 6), PreAuth())
    rolled = roll_history + [ScopeActivated(7, "O", Scope("g", 1), "g.k1", 100)]
    x_roll = possible_exposure(rolled, reach, 7, {})
    next_r = Record("g", 1)
    old_span = fold_authorization(rolled, 7).scope_of(next_r)
    with_record = rolled + [RecordProduced(8, next_r)]
    x_record = possible_exposure(with_record, reach, 8, {})
    record("S11-03_future_start_rollover", not roll_check.ok or
           Scope("g", 0) in x_roll.future_scopes, {
        "produced_next_seq": 1, "activation_start_seq": 100,
        "guard_accepts": roll_check.ok,
        "future_exposed_scopes_reported": len(x_roll.future_scopes),
        "next_record_scope": [old_span.scope.stream, old_span.scope.epoch],
        "next_record_is_collateral_when_produced": next_r in x_record.past_records,
        "correct_options": "reject immediate activation at seq 100, or account for the finite old-key future span",
    })

    # S11-04: Owner availability is stored in one boolean, even when the
    # registry accepts two distinct owners. Owner P going online incorrectly
    # enables a new grant for offline owner O. A single-owner slice may reject
    # the second owner instead; silently accepting the history is not enough.
    owners = [StreamAuthorized(0, "O", "g", "Dg"),
              ScopeActivated(1, "O", Scope("g", 0), "g.k0", 0),
              StreamAuthorized(2, "P", "h", "Dh"),
              ScopeActivated(3, "P", Scope("h", 0), "h.k0", 0),
              OwnerAvailability(4, "O", False), OwnerAvailability(5, "P", True)]
    try:
        obs = project_observation(owners, 5)
        owner_result = check_action(Action(ActionKind.ADMIT_GRANT, grant=g), obs, PreAuth())
        owner_satisfied = not owner_result.ok
        detail = {"O_online": False, "P_online": True,
                  "observation_owner_online": obs.owner_online,
                  "grant_for_O_accepted": owner_result.ok,
                  "guard_reason": owner_result.reason}
    except ValueError as exc:
        owner_satisfied = True
        detail = {"second_owner_rejected_by_validation": str(exc)}
    record("S11-04_owner_connectivity", owner_satisfied, detail, "scope-boundary")

    # S11-05: An admitted material-delivery plan must have valid share indices.
    # Current code invents proxy p3 for index 3 in a three-share (0..2) grant,
    # and accepts negative indices through Python tuple indexing.
    simple = [StreamAuthorized(0, "O", "g", "D"),
              ScopeActivated(1, "O", Scope("g", 0), "g.k0", 0),
              RecordProduced(2, r)]
    invalid = []
    for indices in [(0, 3), (0, -1)]:
        invalid_action = Action(ActionKind.ADMIT_GRANT, grant=g,
                                authorized_kfrag_indices=indices)
        try:
            checked = check_action(invalid_action, project_observation(simple, 2),
                                   PreAuth(), ExposureBudget(1, 1), family(reach), {r: 1})
            accepted = checked.ok
            reason = checked.reason
        except ValueError as exc:
            accepted = False
            reason = str(exc)
        invalid.append({"indices": list(indices), "accepted": accepted, "reason": reason})
    record("S11-05_invalid_share_indices", not any(c["accepted"] for c in invalid),
           {"shares": 3, "valid_indices": [0, 1, 2], "cases": invalid})

    # Positive controls: do not confuse a remaining defect with wholesale
    # rejection of the repairs in 1.1. These are the previously observed cases.
    expiry = grant("EXP", "g", "R", ("p0", "p1", "p2"), valid_to=5)
    expired = simple + [GrantIssued(3, expiry)]
    record("CONTROL_expiry_at_cutoff", not fold_authorization(expired, 10).authorized("R", r),
           {"cutoff": 10, "valid_to": 5}, "positive-control")
    strict_action = Action(ActionKind.ADMIT_GRANT, grant=g,
                           authorized_kfrag_indices=(0, 1))
    strict_result = check_action(strict_action, project_observation(simple, 2), PreAuth(),
                                 ExposureBudget(0, 0), family(reach), {r: 1})
    record("CONTROL_new_grant_veto", not strict_result.ok,
           {"guard_rejects": not strict_result.ok}, "positive-control")
    lenient_result = check_action(strict_action, project_observation(simple, 2), PreAuth(),
                                  ExposureBudget(1, 0), family(reach), {r: 1})
    record("CONTROL_lenient_grant_admitted", lenient_result.ok,
           {"guard_accepts": lenient_result.ok}, "positive-control")

    hashes = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
              for folder in ["delegation_model", "delegation_manager"]
              for p in sorted((source / folder).glob("*.py"))}
    report = {"review_kind": "independent contract counterexamples, not a security proof",
              "python": platform.python_version(), "source_hashes": hashes,
              "results": results,
              "violations": sum(not item["property_satisfied"] for item in results)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    return 1 if report["violations"] else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
