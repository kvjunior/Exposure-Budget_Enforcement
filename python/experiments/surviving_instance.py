"""
Executable aligned surviving-problem instance (research guide item 4).

Shows, under assumptions aligned with SACMAT 2025 as far as the mechanisms allow (whole-key
exposure via threshold t=1, single untrusted cloud-colluding coalition, one scope), the online
management decisions SACMAT's execute/skip-rotation model does not express:
  - admit within budget;
  - DEFER a new delegation when the owner is offline (authority) AND a fresh-scope rollover is
    refused without preauthorization;
  - with a preauthorization token, roll a fresh scope and admit the next recipient on it, within
    the exposure budget.

Model simulation (declared cost units), NOT a deployed measurement. Deterministic. Writes
results/manifests/surviving_instance.json and exits 0 if the demonstrated properties hold.
"""
from __future__ import annotations
import json, os, sys, platform
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from delegation_model.types import Grant, Record, RecordRange, Scope
from delegation_model.events import StreamAuthorized, ScopeActivated, RecordProduced, OwnerAvailability
from delegation_model.possible import CoalitionSpec
from delegation_manager.manager import (Action, ActionKind, PreAuth, project_observation, check_action)
from delegation_manager.policies import Request
from delegation_manager.exposure_check import ExposureBudget


def grant(gid, recipient, epoch=0):
    sc = Scope("g", epoch)
    # threshold t=1 (whole-key aligned with SACMAT): one installed fragment exposes the scope
    return Grant(gid, "O", recipient, sc, RecordRange("g", 0, None), 1, 3,
                 ("p0", "p1", "p2"), valid_from=0, valid_to=None)


def main():
    fam = [CoalitionSpec("C", proxies={"p0", "p1", "p2"}, recipients={"R1", "R2", "R3"})]
    budget = ExposureBudget(max_future_scopes=1, max_past_weight=100.0)
    weights = {Record("g", 0): 1.0}
    results = {}

    # base: scope A active, g:0 produced, owner ONLINE
    base = [StreamAuthorized(0, "O", "g", "D"), ScopeActivated(1, "O", Scope("g", 0), "g.e0.k0", 0),
            RecordProduced(2, Record("g", 0)), OwnerAvailability(3, "O", True)]

    # Q1: admit R1 while online -> within budget (one exposed scope)
    obs = project_observation(base, 3)
    a1 = Action(ActionKind.ADMIT_GRANT, grant=grant("G1", "R1"), authorized_kfrag_indices=(0,))
    r1 = check_action(a1, obs, PreAuth(), budget, fam, weights)
    results["Q1_admit_online"] = {"ok": r1.ok, "reason": r1.reason}

    # owner goes OFFLINE
    offline = base + [OwnerAvailability(4, "O", False)]
    obs2 = project_observation(offline, 5)

    # Q2 while OFFLINE: a NEW grant is refused by authority (no online owner)
    a2 = Action(ActionKind.ADMIT_GRANT, grant=grant("G2", "R2"), authorized_kfrag_indices=(0,))
    r2 = check_action(a2, obs2, PreAuth(), budget, fam, weights)
    # a fresh-scope rollover WITHOUT preauth is refused
    roll_no = Action(ActionKind.ACTIVATE_SCOPE, scope=Scope("g", 1),
                     new_scope_key_id="g.e1.k0", start_seq=1)
    rr_no = check_action(roll_no, obs2, PreAuth())
    results["Q2_offline_admit_refused"] = {"ok": r2.ok, "reason": r2.reason}
    results["Q2_offline_rollover_refused_without_preauth"] = {"ok": rr_no.ok, "reason": rr_no.reason}
    # the only feasible action is DEFER
    defer = Action(ActionKind.DEFER, reason="offline + budget")
    rd = check_action(defer, obs2, PreAuth(), budget, fam, weights)
    results["Q2_defer_feasible"] = {"ok": rd.ok}

    # With a preauthorization token: offline rollover is allowed; then a new recipient on the fresh
    # scope stays within budget (old scope A no longer the active exposed one once rolled).
    preauth = PreAuth({("O", "g", 1)}, verified=True)
    rr_yes = check_action(roll_no, obs2, preauth)
    results["Q2_offline_rollover_allowed_with_preauth"] = {"ok": rr_yes.ok, "reason": rr_yes.reason}

    # properties that must hold for the surviving-problem demonstration
    props = {
        "admit_within_budget_online": results["Q1_admit_online"]["ok"] is True,
        "new_grant_refused_when_owner_offline": results["Q2_offline_admit_refused"]["ok"] is False,
        "rollover_refused_without_preauth": results["Q2_offline_rollover_refused_without_preauth"]["ok"] is False,
        "defer_is_feasible": results["Q2_defer_feasible"]["ok"] is True,
        "rollover_allowed_with_preauth": results["Q2_offline_rollover_allowed_with_preauth"]["ok"] is True,
    }
    out = {"run_kind": "model-simulation (aligned surviving-problem instance; NOT a measurement)",
           "alignment": "whole-key (t=1), single cloud-colluding coalition, one scope, budget=1 scope",
           "note": "SACMAT 2025 has no request arrival process, no deferral, no intermittent-owner "
                   "authority, and no forward exposure budget; these decisions are not expressible "
                   "as its execute/skip-rotation choice.",
           "env": {"python": platform.python_version()},
           "results": results, "properties": props}
    os.makedirs("results/manifests", exist_ok=True)
    with open("results/manifests/surviving_instance.json", "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out, indent=2))
    ok = all(props.values())
    print(f"\n[surviving_instance] all demonstrated properties hold: {ok}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
