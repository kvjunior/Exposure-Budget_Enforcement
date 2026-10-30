"""
Foundation verification (research guide item 5), consolidated. PROD venv. Exit 0 = all hold.

Four properties the controller safety argument (docs/c11_po2_argument.md) depends on:
  F1 later grants cannot erase earlier unauthorized disclosures (ledger irreversibility);
  F2 every relevant delivery and production transition is represented (transition coverage);
  F3 stale or refused actions deliver nothing (executor fidelity);
  F4 online decisions consume no hidden corruption or future ground truth (observation purity).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "python"))

from delegation_model.types import Grant, Record, RecordRange, Scope
from delegation_model.events import (StreamAuthorized, ScopeActivated, RecordProduced, GrantIssued,
                                     GrantRevoked, KFragInstalled, CFragProduced, OwnerAvailability,
                                     CorruptProxy, CorruptRecipient, DiscloseDataKey,
                                     DiscloseScopeKey, DisclosePlaintext, OBSERVABLE,
                                     GROUND_TRUTH_ONLY)
from delegation_model.disclosure_ledger import build_ledger
from delegation_model.transitions import apply_event, ManagementState, TransitionError
from delegation_manager.manager import project_observation, Action, ActionKind
from delegation_manager.executor import execute
from delegation_model.effects import threshold_pre_grant_effects

FAIL = []
def expect(cid, cond, msg):
    ok = bool(cond); print(f"[{'ok ' if ok else 'FAIL'}] {cid:<22} {msg}")
    if not ok: FAIL.append(cid)

sc = Scope("g", 0)

# F1: later authorizing grant cannot erase an earlier disclosure
g_late = Grant("LATE", "O", "R", sc, RecordRange("g", 0, None), 1, 1, ("p0",), 8, None)
hist = [StreamAuthorized(0, "O", "g", "D"), ScopeActivated(1, "O", sc, "g.k0", 0),
        RecordProduced(2, Record("g", 0)), CorruptRecipient(3, "R", "C"),
        DiscloseDataKey(5, Record("g", 0), "C"), GrantIssued(8, g_late),
        KFragInstalled(9, "LATE", "p0", 0)]
disclosed_before = build_ledger(hist, "C", 7).disclosed()      # before the authorizing grant
disclosed_after = build_ledger(hist, "C", 10).disclosed()      # after it
expect("F1_disclosed_before", Record("g", 0) in disclosed_before,
       "g:0 disclosed at t=5 (before the later grant)")
expect("F1_not_erased", disclosed_before <= disclosed_after,
       "later authorizing grant does NOT erase the earlier disclosure (monotone)")
expect("F1_still_present", Record("g", 0) in disclosed_after,
       "g:0 remains in the ledger at t=10 despite the authorizing grant")

# F2: transition coverage -- delivery (kfrag), production, revocation all fold without error;
# and an unrepresented/duplicate transition is rejected.
s = ManagementState()
events = [StreamAuthorized(0, "O", "g", "D"), ScopeActivated(1, "O", sc, "g.k0", 0),
          RecordProduced(2, Record("g", 0)),
          GrantIssued(3, Grant("G", "O", "R", sc, RecordRange("g", 0, None), 2, 3,
                               ("p0", "p1", "p2"), 0, None)),
          KFragInstalled(4, "G", "p0", 0), KFragInstalled(5, "G", "p1", 1),
          RecordProduced(6, Record("g", 1)), GrantRevoked(7, "G")]
try:
    for e in events:
        s = apply_event(s, e)
    covered = (s.produced == {Record("g", 0), Record("g", 1)} and
               "G" in s.revoked and s.installed.get("G") == {0, 1})
    expect("F2_coverage", covered,
           "delivery (kfrag), production, and revocation transitions are all represented")
except TransitionError as ex:
    expect("F2_coverage", False, f"unexpected rejection: {ex}")
# an out-of-seq production is rejected (transition is total over valid inputs, rejects invalid)
try:
    apply_event(s, RecordProduced(8, Record("g", 9)))
    expect("F2_rejects_invalid", False, "should reject out-of-seq production")
except TransitionError:
    expect("F2_rejects_invalid", True, "invalid production transition is rejected, not folded")

# F3: stale or refused actions deliver nothing
from delegation_manager.manager import project_observation, PreAuth
from delegation_model.possible import CoalitionSpec
from delegation_manager.exposure_check import ExposureBudget
base = [StreamAuthorized(0, "O", "g", "D"), ScopeActivated(1, "O", sc, "g.k0", 0),
        RecordProduced(2, Record("g", 0)), OwnerAvailability(3, "O", True)]
st = ManagementState()
for e in base:
    st = apply_event(st, e)
g = Grant("G", "O", "R", sc, RecordRange("g", 0, None), 2, 3, ("p0", "p1", "p2"), 4, None)
action = Action(ActionKind.ADMIT_GRANT, grant=g, authorized_kfrag_indices=(0, 1))
checked = threshold_pre_grant_effects("G", sc, ("p0", "p1", "p2"), (0, 1))
from delegation_manager.executor import approve
obs_f3 = project_observation(base, 3)
fam_f3 = [CoalitionSpec("C", proxies={"p0", "p1", "p2"}, recipients={"R"})]
bud_f3 = ExposureBudget(1, 100.0); w_f3 = {Record("g", 0): 1.0}
receipt = approve(action, obs_f3, bud_f3, fam_f3, w_f3, PreAuth())
# advanced history (a new record produced) -> cross-history mismatch
adv_hist = base + [RecordProduced(4, Record("g", 1))]
obs_adv = project_observation(adv_hist, 4)
stale = execute(action, obs_adv, receipt, bud_f3, fam_f3, w_f3)
# checker verdict False under a zero budget
refused = execute(action, obs_f3, approve(action, obs_f3, ExposureBudget(0, 0), fam_f3, w_f3, PreAuth()),
                  ExposureBudget(0, 0), fam_f3, w_f3)
committed = execute(action, obs_f3, receipt, bud_f3, fam_f3, w_f3)
expect("F3_stale_nothing", (not stale.committed) and stale.outbox == (),
       "a stale action delivers nothing")
expect("F3_refused_nothing", (not refused.committed) and refused.outbox == (),
       "a refused action delivers nothing")
expect("F3_commit_delivers", committed.committed and committed.outbox == checked,
       "a committed action delivers exactly the checked effects")

# F4: observation purity -- project_observation drops ground-truth and future events
full = base + [CorruptProxy(3, "p0", "C"), CorruptRecipient(4, "R", "C"),
               DiscloseDataKey(5, Record("g", 0), "C"), DiscloseScopeKey(6, sc, "C"),
               DisclosePlaintext(7, Record("g", 0), "C"),
               RecordProduced(8, Record("g", 1))]  # future relative to cutoff 5
obs = project_observation(full, cutoff=5)
has_ground_truth = any(isinstance(e, GROUND_TRUTH_ONLY) for e in obs.events)
has_future = any(e.t > 5 for e in obs.events)
expect("F4_no_ground_truth", not has_ground_truth,
       "observation contains NO corruption/disclosure ground-truth events")
expect("F4_no_future", not has_future,
       "observation contains NO events after the cutoff")
expect("F4_only_observable", all(isinstance(e, OBSERVABLE) for e in obs.events),
       "observation contains only observable event types")

print(f"\n{len(FAIL)} failures" + (f": {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
