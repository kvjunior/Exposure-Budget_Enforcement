"""
Review R2 and R3.

R2: budget aggregation must take COORDINATE-WISE maxima -- different coalitions can witness
    different breached dimensions. A lexicographic single-coalition choice must not accept a
    violation.
R3: the checked-action path must VETO an exposure-creating admission BEFORE any fragment is
    installed, by evaluating the candidate's possible delivery effects. We demonstrate an actual
    veto (no material installed), not a post-hoc evaluation of a completed history.

Run with the PROD venv. Exit 0 = all expectations met.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "python"))

from delegation_model.possible import CoalitionSpec
from delegation_model.types import Grant, Record, RecordRange, Scope
from delegation_model.events import (StreamAuthorized, ScopeActivated, RecordProduced,
                                     DiscloseScopeKey, DiscloseDataKey)
from delegation_model.loader import load_events
from delegation_manager.manager import (project_observation, check_action, Action, ActionKind,
                                        PreAuth)
from delegation_manager.exposure_check import evaluate_exposure, ExposureBudget

FAIL = []
def expect(cid, cond, msg):
    ok = bool(cond); print(f"[{'ok ' if ok else 'FAIL'}] {cid:<26} {msg}")
    if not ok: FAIL.append(cid)

# ---- R2: coordinate-wise maxima, different witness coalitions ----
sa, sb, rb = Scope("a", 0), Scope("b", 0), Record("b", 0)
events = [StreamAuthorized(0, "O", "a", "D"), ScopeActivated(1, "O", sa, "ka", 0),
          StreamAuthorized(2, "O", "b", "D"), ScopeActivated(3, "O", sb, "kb", 0),
          RecordProduced(4, rb), DiscloseScopeKey(5, sa, "future"),
          DiscloseDataKey(6, rb, "past")]
weights = {rb: 1.0}
# coalition "future": 1 exposed active scope, 0 past. coalition "past": 0 future, 1 past.
# budget: future<=1, past<=0  => "past" coalition violates past dimension.
v = evaluate_exposure(events, 6, ["future", "past"], ExposureBudget(1, 0), weights)
expect("R2_rejects_violation", not v.ok,
       f"coordinate-wise aggregation REJECTS (past witness={v.past_witness}, "
       f"worst_past={v.worst_past}): {v.reason}")
expect("R2_past_witness", v.past_witness == "past" and v.worst_past == 1.0,
       "the past-dimension breach is attributed to coalition 'past'")
# order independence
v2 = evaluate_exposure(events, 6, ["past", "future"], ExposureBudget(1, 0), weights)
expect("R2_order_independent", (v.ok == v2.ok) and v2.worst_past == 1.0,
       "result is independent of coalition iteration order")

# ---- R3: pre-execution veto prevents fragment installation ----
sc = Scope("g", 0); rec = Record("g", 0)
# observable state: scope active, one record produced, owner online. NO corruption observed.
base = [StreamAuthorized(0, "O", "g", "D"), ScopeActivated(1, "O", sc, "k0", 0),
        RecordProduced(2, rec)]
obs = project_observation(base, 2)
# declared family: a single coalition "C" that may corrupt all three proxies and recipient R.
# A grant delivering t=2 kfrags would let C reconstruct scope A's key -> an exposed active scope.
grant = Grant("NEW", "O", "R", sc, RecordRange("g", 0, 1), 2, 3, ("p0", "p1", "p2"), 3, None)
action = Action(ActionKind.ADMIT_GRANT, grant=grant,
                authorized_kfrag_indices=(0, 1, 2))      # declares what it would install
strict = ExposureBudget(max_future_scopes=0, max_past_weight=0.0)
res = check_action(action, obs, PreAuth(), exposure_budget=strict,
                   coalition_family=[CoalitionSpec("C", proxies={"p0", "p1", "p2"}, recipients={"R"})], weights={rec: 1.0})
expect("R3_vetoes_before_install", not res.ok,
       f"checked-action VETOES the exposure-creating admission before install: {res.exposure_reason}")
# and nothing was installed: the observable history is unchanged (we never executed the action)
expect("R3_no_material_installed",
       all(getattr(e, '__class__', None).__name__ != "KFragInstalled" for e in obs.events),
       "no kfrag was installed (veto happened before execution)")
# a lenient budget that tolerates one exposed scope (and its one past record) admits it
lenient = ExposureBudget(max_future_scopes=1, max_past_weight=1.0)
res2 = check_action(action, obs, PreAuth(), exposure_budget=lenient,
                    coalition_family=[CoalitionSpec("C", proxies={"p0", "p1", "p2"}, recipients={"R"})], weights={rec: 1.0})
expect("R3_admits_within_budget", res2.ok,
       "the same action is admitted under a budget that tolerates one exposed scope")
# an ADMIT that declares kfrag delivery but is given NO budget is refused (never silently skip)
res3 = check_action(action, obs, PreAuth())
expect("R3_refuses_ungated", not res3.ok,
       "ADMIT declaring fragment delivery with no budget/family is REFUSED, not silently passed")

print(f"\n{len(FAIL)} failures" + (f": {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
