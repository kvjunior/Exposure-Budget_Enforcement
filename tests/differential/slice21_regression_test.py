"""
Slice 2.1 regression: the seven review findings under the CORRECTED contracts. PROD venv.
Exit 0 = all corrected properties hold. Preserves the original counterexamples' scenarios; the
assertions reflect the documented contract revisions (see docs/REVIEW_DISPOSITION_slice_2_1.md).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "python"))

from delegation_model.types import Grant, Record, RecordRange, Scope
from delegation_model.events import (StreamAuthorized, ScopeActivated, RecordProduced, GrantIssued,
                                     KFragInstalled, OwnerAvailability)
from delegation_model.possible import CoalitionSpec
from delegation_model.transitions import fold_state
from delegation_manager.manager import (Action, ActionKind, PreAuth, GrantToken,
                                        project_observation, check_action)
from delegation_manager.policies import Request
from delegation_manager.exposure_check import ExposureBudget
from delegation_manager.candidate_actions import enumerate_actions
from delegation_manager.offline_oracle import Instance, solve, replay_schedule, _apply_action_events
from delegation_manager.cost_model import action_cost, CostWeights
from delegation_manager.baselines.greedy_history import greedy_history_policy
from delegation_manager.baselines.rolling_horizon import rolling_horizon_policy
from delegation_manager.executor import approve, execute

FAIL = []
def expect(cid, cond, msg):
    ok = bool(cond); print(f"[{'ok ' if ok else 'FAIL'}] {cid:<34} {msg}")
    if not ok: FAIL.append(cid)

sc = Scope("g", 0); r0 = Record("g", 0)
base = [StreamAuthorized(0, "O", "g", "D"), ScopeActivated(1, "O", sc, "g.k0", 0),
        RecordProduced(2, r0), OwnerAvailability(3, "O", True)]
def grant(gid, rec, lo=0, hi=None, th=1):
    return Grant(gid, "O", rec, sc, RecordRange("g", lo, hi), th, 3, ("p0", "p1", "p2"), 0, None)

# ---- S2-01: coverage contract rejects the recipient-domination gap ----
obs = project_observation(base + [GrantIssued(4, grant("G0", "R0", 0, 1)),
                                  KFragInstalled(5, "G0", "p0", 0)], 5)
g1 = grant("G1", "R1", 1, 2, th=2)
a_admit = Action(ActionKind.ADMIT_GRANT, grant=g1, authorized_kfrag_indices=(0, 1))
fam_big = [CoalitionSpec("C", proxies={"p0", "p1"}, recipients={"R0", "R1"})]
r = check_action(a_admit, obs, PreAuth(), ExposureBudget(1, 0.0), fam_big, {r0: 1.0})
expect("S2-01_coverage_rejects", not r.ok,
       "coverage contract rejects the admit because the exact-recipient {R1} case breaches past")

# ---- S2-02: substituted recipient not committed under another action's receipt ----
from delegation_manager.manager import project_observation, PreAuth
from delegation_manager.exposure_check import ExposureBudget
obsx = project_observation(base, base[-1].t)
famx = [CoalitionSpec("C", proxies={"p0", "p1", "p2"}, recipients={"R_inside", "R_outside"})]
budx = ExposureBudget(1, 100.0); wx = {r0: 1.0}
g_in = grant("G", "R_inside")
a_in = Action(ActionKind.ADMIT_GRANT, grant=g_in, authorized_kfrag_indices=(0,))
receipt = approve(a_in, obsx, budx, famx, wx, PreAuth())
g_out = grant("G", "R_outside")
a_out = Action(ActionKind.ADMIT_GRANT, grant=g_out, authorized_kfrag_indices=(0,))
res_sub = execute(a_out, obsx, receipt, budx, famx, wx)
expect("S2-02_no_substitution", not res_sub.committed,
       "a substituted-recipient action does not commit under R_inside's receipt")
expect("S2-02_exact_commits", execute(a_in, obsx, receipt, budx, famx, wx).committed,
       "the exact approved action commits")

# ---- S2-03: oracle searches token-authorized offline admit ----
off = base + [OwnerAvailability(4, "O", False)]
obs_off = project_observation(off, 4)
tok = GrantToken("O", "R1", "g", 0, 0, None, 0, None, (0,))
pa = PreAuth(grant_tokens=(tok,), verified=True)
inst_tok = Instance(off, [Request(5, grant("GT", "R1"))], ExposureBudget(1, 100.0),
                    [CoalitionSpec("C", proxies={"p0", "p1", "p2"}, recipients={"R1"})],
                    {r0: 1.0}, preauth=pa)
opt_tok = solve(inst_tok)
expect("S2-03_oracle_admits_token", opt_tok.actions[0].kind == ActionKind.ADMIT_GRANT,
       "oracle chooses the token-authorized offline admit (cost 1), not defer (cost 10)")
expect("S2-03_oracle_cost", opt_tok.total_cost == 1.0,
       f"oracle optimum is the admit cost ({opt_tok.total_cost})")

# ---- S2-04: rolling horizon sees the beneficial rotation (14 vs plain defer 20) ----
fam = [CoalitionSpec("big", proxies={"p0", "p1", "p2"}, recipients={"R0", "R1"})]
bud0 = ExposureBudget(0, 0); w = {r0: 1.0}; cw = CostWeights()
qs = [Request(3, grant("G0", "R0")), Request(4, grant("G1", "R1"))]
hist = list(base)
first = rolling_horizon_policy(project_observation(hist, hist[-1].t), qs[0], bud0, fam, w,
                              forecast=[qs[1]], horizon=1, history=hist,
                              forecast_kind="perfect_information")
hist = hist + _apply_action_events(hist, first, hist[-1].t + 1)
second = greedy_history_policy(project_observation(hist, hist[-1].t), qs[1], bud0, fam, w, PreAuth(), cw)
rh_cost = action_cost(first, cw) + action_cost(second, cw)
from delegation_manager.offline_oracle import replay_plan
inst04 = Instance(base, qs, bud0, fam, w)
opt04 = solve(inst04); feas04, rc04, _ = replay_plan(inst04, opt04.plans)
# Legacy one-action diagnostic: the FIRST request rotates and remains unserved
# (13); the SECOND request is admitted (1). This totals 14 serving one request.
# The compound-plan oracle can serve both for 15, but minimizes the unchanged
# declared cost and therefore chooses 14. Service and cost are distinct.
expect("S2-04_rolling_sees_rotation", first.kind == ActionKind.ACTIVATE_SCOPE and rh_cost == 14,
       f"two-request trace: first unserved rotation, second admission (cost {rh_cost})")
# Under the single-charge plan contract, the 2-request zero-budget optimum is 14: rotate for R0
# (13, unserved) then admit R1 on the now-closed scope (1, served). The independent reference agrees.
expect("S2-04_oracle_14", opt04.total_cost == 14 and feas04 and rc04 == 14,
       "oracle optimum is 14 under the single-charge usable-completion plan contract")

# ---- S2-06: replay rejects empty and non-binding schedules ----
inst06 = Instance(base, [Request(3, grant("G0", "R0"))], ExposureBudget(1, 100.0),
                  [CoalitionSpec("C", proxies={"p0", "p1", "p2"}, recipients={"R0"})], {r0: 1.0})
ok_empty, _, _ = replay_schedule(inst06, [])
expect("S2-06_empty_rejected", not ok_empty, "empty schedule for a nonempty instance is rejected")
# a schedule that admits the WRONG request is rejected
wrong = Action(ActionKind.ADMIT_GRANT, grant=grant("OTHER", "RX"), authorized_kfrag_indices=(0,))
ok_wrong, _, why_wrong = replay_schedule(inst06, [wrong])
expect("S2-06_binding_enforced", not ok_wrong,
       "a schedule whose ADMIT does not serve the offered request is rejected")

# ---- GENUINELY independent reference (does NOT share enumerate_actions; F02/F06) ----
from independent_reference import ref_optimum

def make_instance_f04():
    from delegation_manager.offline_oracle import Instance as _I
    b=[StreamAuthorized(0,"O","g","D"),ScopeActivated(1,"O",sc,"gk.k0",0),RecordProduced(2,r0),OwnerAvailability(3,"O",True)]
    rq=[Request(4,Grant(f"Q{i}","O",f"RR{i}",sc,RecordRange("g",0,None),1,3,("p0","p1","p2"),0,None)) for i in range(2)]
    fm=[CoalitionSpec("C",proxies={"p0","p1","p2"},recipients={f"RR{i}" for i in range(2)})]
    return _I(b,rq,ExposureBudget(1,100.0),fm,{r0:1.0},max_branches=20)


expect("ref_matches_oracle_04", abs(ref_optimum(inst04) - opt04.total_cost) < 1e-9,
       f"independent reference optimum ({ref_optimum(inst04)}) matches the oracle ({opt04.total_cost})")
expect("ref_matches_oracle_tok", abs(ref_optimum(inst_tok) - opt_tok.total_cost) < 1e-9,
       f"independent reference optimum ({ref_optimum(inst_tok)}) matches the oracle (token admit)")

# ============================================================================================
# Slice 2.2 F01-F05 explicit contract checks (corrected contracts; old cases retained above).
# ============================================================================================
from delegation_manager.executor import approve as _approve, execute as _execute
from delegation_manager.offline_oracle import replay_plan as _replay_plan

# F01: a receipt from one history does not commit on a different history (same time/version)
baseA = [StreamAuthorized(0, "O", "g", "D"), ScopeActivated(1, "O", sc, "g.k0", 0),
         RecordProduced(2, r0), OwnerAvailability(3, "O", True)]
obsA = project_observation(baseA, 3)
gf = grant("GF", "R")
af = Action(ActionKind.ADMIT_GRANT, grant=gf, authorized_kfrag_indices=(0,))
famF = [CoalitionSpec("C", proxies={"p0", "p1", "p2"}, recipients={"R"})]
budF = ExposureBudget(1, 100.0); wF = {r0: 1.0}
rec = _approve(af, obsA, budF, famF, wF, PreAuth())
# a different history: an extra record changes the log digest
baseB = baseA + [RecordProduced(4, Record("g", 1))]
obsB = project_observation(baseB, 4)
expect("F01_cross_history_rejected", not _execute(af, obsB, rec, budF, famF, wF).committed,
       "a receipt does not commit on a different observable history")
# F01: a failing exposure check cannot be approved to commit
rec_bad = _approve(af, obsA, ExposureBudget(0, 0), famF, wF, PreAuth())
expect("F01_failed_check_not_approved",
       not _execute(af, obsA, rec_bad, ExposureBudget(0, 0), famF, wF).committed,
       "a receipt whose checker verdict was False never commits")

# F02: non-prefix usable delivery is enumerated and found by the oracle
base2 = [StreamAuthorized(0, "O", "g", "D"), ScopeActivated(1, "O", sc, "g.k0", 0),
         RecordProduced(2, r0), OwnerAvailability(3, "O", True)]
g2 = Grant("G", "O", "R", sc, RecordRange("g", 0, None), 1, 2, ("p0", "p1"), 0, None)
inst_f02 = Instance(base2, [Request(4, g2)], ExposureBudget(0, 100.0),
                    [CoalitionSpec("C", proxies={"p0"}, recipients={"R"})], {r0: 1.0}, max_branches=20)
opt_f02 = solve(inst_f02)
expect("F02_nonprefix_found", opt_f02.total_cost == 1.0,
       f"oracle finds the usable index-1 admit (cost {opt_f02.total_cost}), not defer (10)")

# F03: partial/zero/changed-threshold delivery is NOT served
g3 = Grant("G3", "O", "R", sc, RecordRange("g", 0, None), 2, 3, ("p0", "p1", "p2"), 0, None)
inst_f03 = Instance(base2, [Request(4, g3)], ExposureBudget(2, 100.0),
                    [CoalitionSpec("C", proxies={"p0", "p1", "p2"}, recipients={"R"})], {r0: 1.0})
zero = [[Action(ActionKind.ADMIT_GRANT, grant=g3, authorized_kfrag_indices=())]]
full = [[Action(ActionKind.ADMIT_GRANT, grant=g3, authorized_kfrag_indices=(0, 1))]]
g3_th1 = Grant("G3", "O", "R", sc, RecordRange("g", 0, None), 1, 3, ("p0", "p1", "p2"), 0, None)
changed = [[Action(ActionKind.ADMIT_GRANT, grant=g3_th1, authorized_kfrag_indices=(0,))]]
ok_z, c_z, why_z = _replay_plan(inst_f03, zero)
ok_f, c_f, why_f = _replay_plan(inst_f03, full)
ok_c, c_c, _ = _replay_plan(inst_f03, changed)
expect("F03_zero_unserved", ok_z and "served 0" in why_z and c_z == 10.0,
       "zero-fragment admit of a threshold-2 request is NOT served (miss charged)")
expect("F03_full_served", ok_f and "served 1" in why_f and c_f == 2.0,
       "full threshold-2 admit is served at fragment cost 2")
expect("F03_changed_threshold_rejected", not ok_c,
       "a changed-threshold grant is rejected (full offered grant must bind)")

# F04: every method trace replays feasibly under the common plan contract (checked in the
# controller_comparison experiment); here we assert the oracle/ref agree on a plan instance.
inst_f04 = make_instance_f04()
opt_f04 = solve(inst_f04); f4, rc4, _ = replay_plan(inst_f04, opt_f04.plans)
expect("F04_oracle_plan_replays", f4 and abs(rc4 - opt_f04.total_cost) < 1e-9,
       f"oracle plan replays feasibly under the common contract (cost {opt_f04.total_cost})")
expect("F04_ref_agrees", abs(ref_optimum(inst_f04) - opt_f04.total_cost) < 1e-9,
       "independent reference agrees with the plan-oracle")

print(f"\n{len(FAIL)} failures" + (f": {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
