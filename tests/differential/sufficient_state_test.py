"""
Nontriviality check (research guide): does the conservative threat model collapse history to a
simple per-scope "delegated?" flag? If it did, the management problem would be trivial. PROD venv.
Exit 0 = the state is substantive (NOT collapsible to a flag).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from delegation_model.types import Grant, Record, RecordRange, Scope
from delegation_model.events import StreamAuthorized, ScopeActivated, RecordProduced, GrantIssued, KFragInstalled
from delegation_model.possible import CoalitionSpec, possible_exposure

FAIL = []
def expect(cid, cond, msg):
    ok = bool(cond); print(f"[{'ok ' if ok else 'FAIL'}] {cid:<28} {msg}")
    if not ok: FAIL.append(cid)

def hist(indices, threshold=2):
    sc = Scope("g", 0)
    ev = [StreamAuthorized(0, "O", "g", "D"), ScopeActivated(1, "O", sc, "g.k0", 0),
          RecordProduced(2, Record("g", 0)),
          GrantIssued(3, Grant("G", "O", "R", sc, RecordRange("g", 0, None), threshold, 3,
                               ("p0", "p1", "p2"), 0, None))]
    t = 4
    for i in indices:
        ev.append(KFragInstalled(t, "G", f"p{i}", i)); t += 1
    return ev

full = CoalitionSpec("C", proxies={"p0", "p1", "p2"}, recipients={"R"})
narrow = CoalitionSpec("C", proxies={"p0"}, recipients={"R"})
norec = CoalitionSpec("C", proxies={"p0", "p1", "p2"}, recipients=set())

exposed_full = len(possible_exposure(hist([0, 1]), full, 99, {}).future_scopes)
exposed_narrow = len(possible_exposure(hist([0, 1]), narrow, 99, {}).future_scopes)
exposed_subthresh = len(possible_exposure(hist([0]), full, 99, {}).future_scopes)
exposed_norec = len(possible_exposure(hist([0, 1]), norec, 99, {}).future_scopes)

expect("completed_full_exposes", exposed_full == 1,
       "a completed grant with full reach + recipient exposes the scope")
expect("reach_below_threshold_safe", exposed_narrow == 0,
       "SAME completed grant, coalition reaches < t of the installed proxies -> NOT exposed")
expect("subthreshold_install_safe", exposed_subthresh == 0,
       "sub-threshold installation -> NOT exposed even with full reach")
expect("no_recipient_safe", exposed_norec == 0,
       "no recipient key in reach -> NOT exposed even with full install + proxy reach")
# the decisive nontriviality conclusion: exposure is NOT a function of 'a completed grant exists'
expect("not_collapsible_to_flag",
       not (exposed_full == exposed_narrow == exposed_subthresh == exposed_norec),
       "exposure depends on install/threshold/reach/recipient, NOT a single delegated flag "
       "-> history does not collapse; the management problem is substantive")

print(f"\n{len(FAIL)} failures" + (f": {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
