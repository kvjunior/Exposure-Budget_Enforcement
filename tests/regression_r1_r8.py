"""
Slice 1.1 regression reproducer: confirms each independent-review finding R1-R8 is CORRECTED,
using the corrected slice-1.1 interfaces. Writes machine-readable JSON and exits nonzero on any
regression. This complements (does not replace) the review package's reproduce_findings.py, which
exercises the slice-1 API against the slice-1 witness.

Env: R1 uses the LEGACY venv (umbral). R2-R8 use the PROD venv. This script is designed to run
under EITHER venv and will skip the umbral-dependent R1 body if umbral is unavailable, recording
that as "skipped" (not a pass). Run both:
  LEGACY: python tests/regression_r1_r8.py --only R1
  PROD:   python tests/regression_r1_r8.py --skip R1
or run the whole suite twice and merge; make check runs the dedicated per-finding tests anyway.
"""
import argparse, json, os, sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "python"))

RESULTS = []
def record(cid, corrected, detail):
    RESULTS.append({"id": cid, "corrected": bool(corrected), "detail": detail})
    print(f"[{'FIXED' if corrected else 'REGRESSED'}] {cid}: {json.dumps(detail, sort_keys=True)}")


def r1():
    import umbral
    from umbral import SecretKey, Signer, generate_kfrags, encrypt, reencrypt, decrypt_reencrypted
    from delegation_model.types import Grant, Record, RecordRange, Scope
    from delegation_model.events import (StreamAuthorized, ScopeActivated, RecordProduced,
                                         GrantIssued, KFragInstalled, CFragProduced,
                                         CorruptProxy, CorruptRecipient)
    from delegation_model.closure import accumulate, conservative_closure
    owner, recipient, signer = SecretKey.random(), SecretKey.random(), Signer(SecretKey.random())
    frags = generate_kfrags(owner, recipient.public_key(), signer, 2, 3, True, True)
    msg = b"regression mixed-fragment"
    capsule, ct = encrypt(owner.public_key(), msg)
    opened = decrypt_reencrypted(recipient, owner.public_key(), capsule,
                                 [reencrypt(capsule, frags[1]), reencrypt(capsule, frags[0])], ct)
    sc, rec = Scope("g", 0), Record("g", 0)
    g = Grant("G", "O", "R", sc, RecordRange("g", 0, 1), 2, 3, ("p0", "p1", "p2"), 0, None)
    ev = [StreamAuthorized(0, "O", "g", "D"), ScopeActivated(1, "O", sc, "k0", 0),
          RecordProduced(2, rec), GrantIssued(3, g), KFragInstalled(4, "G", "p0", 0),
          CFragProduced(5, "G", rec, 1), CorruptProxy(6, "p0", "C"), CorruptRecipient(7, "R", "C")]
    cl = conservative_closure(accumulate(ev, "C", 7), ev, 7)
    record("R1", opened == msg and rec in cl.records,
           {"real_umbral": opened == msg, "model_openable": rec in cl.records})


def r2_r8():
    from delegation_model.types import Grant, Record, RecordRange, Scope
    from delegation_model.events import (StreamAuthorized, ScopeActivated, RecordProduced,
                                         GrantIssued, DiscloseScopeKey, DiscloseDataKey)
    from delegation_model.loader import load_events
    from delegation_model.authorization import fold_authorization
    from delegation_model.closure import accumulate, conservative_closure, exposure
    from delegation_model.possible import CoalitionSpec, possible_exposure
    from delegation_manager.manager import (project_observation, check_action, Action, ActionKind,
                                            PreAuth)
    from delegation_manager.exposure_check import evaluate_exposure, ExposureBudget
    from reference.witness import (history_safe, history_exposed, NOW,
                                   history_lowobs, history_highobs, NOW_D)

    # R2: coordinate-wise rejection
    sa, sb, rb = Scope("a", 0), Scope("b", 0), Record("b", 0)
    ev = [StreamAuthorized(0, "O", "a", "D"), ScopeActivated(1, "O", sa, "ka", 0),
          StreamAuthorized(2, "O", "b", "D"), ScopeActivated(3, "O", sb, "kb", 0),
          RecordProduced(4, rb), DiscloseScopeKey(5, sa, "future"), DiscloseDataKey(6, rb, "past")]
    v = evaluate_exposure(ev, 6, ["future", "past"], ExposureBudget(1, 0), {rb: 1.0})
    record("R2", (not v.ok) and v.past_witness == "past",
           {"rejected": not v.ok, "past_witness": v.past_witness, "worst_past": v.worst_past})

    # R3: pre-execution veto, nothing installed
    sc, rec = Scope("g", 0), Record("g", 0)
    base = [StreamAuthorized(0, "O", "g", "D"), ScopeActivated(1, "O", sc, "k0", 0),
            RecordProduced(2, rec)]
    obs = project_observation(base, 2)
    g = Grant("NEW", "O", "R", sc, RecordRange("g", 0, 1), 2, 3, ("p0", "p1", "p2"), 3, None)
    act = Action(ActionKind.ADMIT_GRANT, grant=g, authorized_kfrag_indices=(0, 1, 2))
    res = check_action(act, obs, PreAuth(), exposure_budget=ExposureBudget(0, 0),
                       coalition_family=[CoalitionSpec("C", proxies={"p0", "p1", "p2"}, recipients={"R"})], weights={rec: 1.0})
    no_install = all(type(e).__name__ != "KFragInstalled" for e in obs.events)
    record("R3", (not res.ok) and no_install,
           {"vetoed": not res.ok, "no_material_installed": no_install})

    # R4: non-interference + distinguishable new witness
    obs_safe = project_observation(load_events(history_safe()), NOW)
    obs_exp = project_observation(load_events(history_exposed()), NOW)
    noninterf = obs_safe.events == obs_exp.events
    spec = CoalitionSpec("C", proxies={"p0", "p1", "p2"}, recipients={"R"})
    wl = {Record(e["record"][0], e["record"][1]): 1.0 for e in history_lowobs()
          if e["type"] == "RecordProduced"}
    wh = {Record(e["record"][0], e["record"][1]): 1.0 for e in history_highobs()
          if e["type"] == "RecordProduced"}
    xl = possible_exposure(load_events(history_lowobs()), spec, NOW_D, wl)
    xh = possible_exposure(load_events(history_highobs()), spec, NOW_D, wh)
    record("R4", noninterf and len(xl.future_scopes) != len(xh.future_scopes),
           {"noninterference": noninterf, "lowobs_scopes": len(xl.future_scopes),
            "highobs_scopes": len(xh.future_scopes)})

    # R5: foreign issuer rejected
    from delegation_model.events import OwnerAvailability
    base5 = base + [OwnerAvailability(3, "O", True)]
    obs5 = project_observation(base5, 3)
    foreign = Grant("F", "ATTACKER", "R", sc, RecordRange("g", 0, 1), 2, 3,
                    ("p0", "p1", "p2"), 4, None)
    r5 = check_action(Action(ActionKind.ADMIT_GRANT, grant=foreign), obs5, PreAuth())
    record("R5", not r5.ok, {"foreign_rejected": not r5.ok})

    # R6: already-active scope rejected; fresh accepted
    same = check_action(Action(ActionKind.ACTIVATE_SCOPE, scope=sc, new_scope_key_id="k1",
                               start_seq=1), obs5, PreAuth())
    fresh = check_action(Action(ActionKind.ACTIVATE_SCOPE, scope=Scope("g", 1),
                                new_scope_key_id="k1", start_seq=1), obs5, PreAuth())
    record("R6", (not same.ok) and fresh.ok,
           {"active_rejected": not same.ok, "fresh_accepted": fresh.ok})

    # R7: expiry at cutoff
    expiry = Grant("EXP", "O", "R", sc, RecordRange("g", 0, 1), 1, 1, ("p0",), 0, 5)
    ev7 = [StreamAuthorized(0, "O", "g", "D"), ScopeActivated(1, "O", sc, "k0", 0),
           RecordProduced(2, rec), GrantIssued(3, expiry)]
    st = fold_authorization(ev7, now=10)
    record("R7", not st.authorized("R", rec),
           {"still_authorized_at_10": st.authorized("R", rec), "state_now": st.now})

    # R8: post-revocation data is collateral
    broad = history_exposed()
    for e in broad:
        if e["type"] == "GrantIssued":
            e["grant"]["rng"] = ["g", 0, None]
    broad += [{"t": 12, "type": "RecordProduced", "record": ["g", 2], "weight": 1.0},
              {"t": 13, "type": "ScopeActivated", "owner": "O", "scope": ["g", 1],
               "scope_key_id": "g.e1.k0", "start_seq": 3}]
    ev8 = load_events(broad)
    r2rec = Record("g", 2)
    K = accumulate(ev8, "C", 13)
    cl = conservative_closure(K, ev8, 13)
    x = exposure(K, ev8, 13, {Record("g", 0): 1.0, Record("g", 1): 1.0, r2rec: 1.0})
    authorized_now = fold_authorization(ev8, 13).authorized("R", r2rec)
    record("R8", r2rec in cl.records and (not authorized_now) and x.past == 1.0,
           {"openable": r2rec in cl.records, "authorized_now": authorized_now,
            "past": x.past})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--skip")
    ap.add_argument("--output", default="results/manifests/regression_r1_r8.json")
    args = ap.parse_args()

    want = lambda cid: (args.only is None or args.only == cid) and (args.skip != cid)
    if want("R1"):
        try:
            r1()
        except ModuleNotFoundError:
            RESULTS.append({"id": "R1", "corrected": None, "detail": {"skipped": "umbral not in this venv"}})
            print("[SKIP ] R1: umbral not available in this venv")
    if args.only in (None, "R2", "R3", "R4", "R5", "R6", "R7", "R8"):
        if args.only is None or args.only != "R1":
            r2_r8() if args.only is None else _single(args.only)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    regressed = [r["id"] for r in RESULTS if r["corrected"] is False]
    out = {"results": RESULTS, "regressed": regressed}
    with open(args.output, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\n{len(regressed)} regressions" + (f": {regressed}" if regressed else ""))
    sys.exit(1 if regressed else 0)


def _single(cid):
    # run the full r2_r8 and let the harness filter by printing; simplest is to run all of r2_r8
    r2_r8()


if __name__ == "__main__":
    main()
