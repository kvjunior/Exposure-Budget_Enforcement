"""
Strengthened surviving-problem evidence (research-guide items 2, 3, 4). PROD venv. Exit 0 = all hold.

Item 2: a small instance with AT LEAST TWO feasible management choices under the SAME observations,
        authority, coalition family, and resource limits, with DIFFERENT consequences for useful
        service / irreversible exposure / cost. All admissible actions are listed; rejection is
        treated explicitly; the service objective is stated so "refuse everything" cannot look good.
Item 3: a scope-activation token does NOT authorize a delegation grant; a scoped grant token does,
        only for its named recipient/scope/range/validity/effects.
Item 4: threshold nontriviality examined under USABLE grants, with cfrag/mixed-fragment cases, and
        the whole-key collapse reported honestly.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "python"))

from delegation_model.types import Grant, Record, RecordRange, Scope
from delegation_model.events import (StreamAuthorized, ScopeActivated, RecordProduced, GrantIssued,
                                     KFragInstalled, CFragProduced, OwnerAvailability,
                                     CorruptProxy, CorruptRecipient)
from delegation_model.possible import CoalitionSpec, possible_exposure
from delegation_model.disclosure_ledger import build_ledger
from delegation_manager.manager import (Action, ActionKind, PreAuth, GrantToken,
                                        project_observation, check_action)
from delegation_manager.policies import Request
from delegation_manager.exposure_check import ExposureBudget
from delegation_manager.candidate_actions import enumerate_actions
from delegation_manager.cost_model import action_cost, CostWeights

FAIL = []
def expect(cid, cond, msg):
    ok = bool(cond); print(f"[{'ok ' if ok else 'FAIL'}] {cid:<30} {msg}")
    if not ok: FAIL.append(cid)

# ============================================================================================
# ITEM 2: two feasible choices, same inputs, different consequences.
# Service objective (stated): serve the pending delegation request at minimum cost
#   cost = miss_penalty * [request not served this step] + rollover_cost * [rolled] + per_fragment.
# A pending request that is admitted is "served"; defer/reject leave it UNSERVED (miss). So
# refusing all work incurs the miss penalty and cannot masquerade as optimal.
# Setup: scope A active with record g:0, a prior grant G0 already delegated R0 on scope A (one
# exposed scope under coalition C). Owner ONLINE. Budget allows at most ONE exposed active scope.
# A NEW request Q to delegate R1. Admitting Q on scope A would make TWO recipients exposed on the
# same un-rotated scope A -> still ONE exposed *scope* (same key), so admit is within the scope
# budget while closing A first removes its future active-scope risk.
# The SAME old-scope grant is then admitted; both branches preserve g:0.
# ============================================================================================
sc = Scope("g", 0)
fam = [CoalitionSpec("C", proxies={"p0", "p1", "p2"}, recipients={"R0", "R1"})]
weights = {Record("g", 0): 1.0}
cw = CostWeights(miss_penalty=10.0, rollover_cost=3.0, per_fragment_cost=1.0)
budget = ExposureBudget(max_future_scopes=1, max_past_weight=100.0)

def g0():
    return Grant("G0", "O", "R0", sc, RecordRange("g", 0, None), 1, 3, ("p0", "p1", "p2"), 0, None)

base = [StreamAuthorized(0, "O", "g", "D"), ScopeActivated(1, "O", sc, "g.e0.k0", 0),
        RecordProduced(2, Record("g", 0)), OwnerAvailability(3, "O", True),
        GrantIssued(4, g0()), KFragInstalled(5, "G0", "p0", 0)]   # R0 already delegated
obs = project_observation(base, 5)
reqQ = Request(6, Grant("G1", "O", "R1", sc, RecordRange("g", 0, None), 1, 3,
                        ("p0", "p1", "p2"), 6, None))

# list ALL admissible actions (authority-feasible), then their budget feasibility
cands = enumerate_actions(obs, reqQ, PreAuth())
admissible = []
for a in cands:
    r = check_action(a, obs, PreAuth(), budget, fam, weights)
    admissible.append((a.kind.value, r.ok, r.reason))
print("  [item2] admissible actions:", [(k, ok) for (k, ok, _) in admissible])

# the two interesting feasible choices:
admit_on_A = Action(ActionKind.ADMIT_GRANT, grant=reqQ.grant, authorized_kfrag_indices=(0,))
roll_B = Action(ActionKind.ACTIVATE_SCOPE, scope=Scope("g", 1),
                new_scope_key_id="g.e1.k0", start_seq=1)
r_admit = check_action(admit_on_A, obs, PreAuth(), budget, fam, weights)
r_roll = check_action(roll_B, obs, PreAuth(), budget, fam, weights)
expect("item2_two_feasible", r_admit.ok and r_roll.ok,
       "BOTH admit-on-A and roll-fresh-scope are feasible under identical inputs")
# rejection is allowed and is explicitly NOT free: it leaves Q unserved (miss penalty)
reject = Action(ActionKind.REJECT, reason="explicit reject")
r_reject = check_action(reject, obs, PreAuth(), budget, fam, weights)
expect("item2_reject_allowed_but_costly",
       r_reject.ok and action_cost(reject, cw, request_present=True) == cw.miss_penalty,
       "reject is admissible but incurs the miss penalty (refusing work is not free)")
# different consequences: admit serves Q now (cost = 1 fragment) but widens exposure breadth on A;
# roll defers Q this step (miss) + rollover cost, but isolates R1 on a clean scope.
cost_admit = action_cost(admit_on_A, cw, request_present=True)     # served -> no miss
cost_roll = action_cost(roll_B, cw, request_present=True)          # not served -> miss + rollover
expect("item2_different_cost", cost_admit != cost_roll,
       f"the two feasible choices have different cost (admit={cost_admit}, roll={cost_roll})")
# F05 repair: BOTH branches serve the IDENTICAL offered grant reqQ.grant (G1 to R1 on scope (g,0),
# range [0,inf)). The admit branch admits it directly on the active scope; the roll branch rotates
# the stream and then admits the SAME grant on its now-CLOSED old scope (g,0). g:0 authorization is
# preserved in both branches (the grant's range covers g:0 either way). The exposure DIFFERS in
# MAGNITUDE now: admit exposes active scope (g,0) -> future count 1; roll-then-admit puts the grant
# on the closed scope -> future count 0. Costs: admit 1, roll-then-admit 14 (rollover 13 + admit 1).
from delegation_model.possible import possible_exposure as _pe
from delegation_model.authorization import fold_authorization as _fa
spec_future = CoalitionSpec("C", proxies={"p0", "p1", "p2"}, recipients={"R1"})
# admit branch: admit the offered grant directly
hist_admit = base + [GrantIssued(6, reqQ.grant), KFragInstalled(7, "G1", "p0", 0)]
x_admit = _pe(hist_admit, spec_future, 7, weights)
# roll branch: rotate the stream, THEN admit the SAME offered grant on the now-closed old scope
hist_roll = base + [ScopeActivated(6, "O", Scope("g", 1), "g.e1.k0", 1),
                    GrantIssued(7, reqQ.grant),              # SAME grant: scope (g,0), range [0,inf)
                    KFragInstalled(8, "G1", "p0", 0)]
x_roll = _pe(hist_roll, spec_future, 8, weights)
# both branches authorize the originally-produced requested record g:0 (grant range covers it)
admit_auth = _fa(hist_admit, 7).authorized("R1", Record("g", 0))
roll_auth = _fa(hist_roll, 8).authorized("R1", Record("g", 0))
expect("item2_same_demand_served", admit_auth and roll_auth,
       "BOTH branches serve the same offered grant: g:0 is authorized to R1 in both")
future_admit = len(x_admit.future_scopes); future_roll = len(x_roll.future_scopes)
expect("item2_roll_reduces_future_exposure", future_admit == 1 and future_roll == 0,
       f"with identical served demand, roll-then-admit-on-closed-scope gives future count "
       f"{future_roll} vs admit-on-active {future_admit}: a real exposure reduction, at higher cost "
       f"(14 vs 1). A model TRADEOFF, not a controller or novelty.")

# ============================================================================================
# ITEM 3: scope token != grant token.
# ============================================================================================
offline = base + [OwnerAvailability(6, "O", False)]
obs_off = project_observation(offline, 7)
reqG = Grant("G2", "O", "R1", sc, RecordRange("g", 0, None), 1, 3, ("p0", "p1", "p2"), 7, None)
admit_off = Action(ActionKind.ADMIT_GRANT, grant=reqG, authorized_kfrag_indices=(0,))
roll_off = Action(ActionKind.ACTIVATE_SCOPE, scope=Scope("g", 1),
                  new_scope_key_id="g.e1.k0", start_seq=1)

# a SCOPE token authorizes rollover but NOT the grant
scope_only = PreAuth(scope_tokens={("O", "g", 1)}, verified=True)
r_roll_scope = check_action(roll_off, obs_off, scope_only)
r_admit_scope = check_action(admit_off, obs_off, scope_only, budget, fam, weights)
expect("item3_scope_token_rolls", r_roll_scope.ok,
       "a scope-activation token permits the offline rollover")
expect("item3_scope_token_not_grant", not r_admit_scope.ok,
       "the SAME scope token does NOT authorize the offline delegation grant (still refused)")

# a scoped GRANT token authorizes exactly its named grant
grant_tok = GrantToken(owner="O", recipient="R1", stream="g", epoch=0, lo=0, hi=None,
                       issue_from=0, issue_to=None, permitted_indices=(0,))
grant_pa = PreAuth(grant_tokens=(grant_tok,), verified=True)
r_admit_grant = check_action(admit_off, obs_off, grant_pa, budget, fam, weights)
expect("item3_grant_token_admits", r_admit_grant.ok,
       "a scoped grant token (matching recipient/scope/range/validity/effects) authorizes the grant")
# but NOT a different recipient
reqG_other = Grant("G3", "O", "R2", sc, RecordRange("g", 0, None), 1, 3, ("p0", "p1", "p2"), 7, None)
admit_other = Action(ActionKind.ADMIT_GRANT, grant=reqG_other, authorized_kfrag_indices=(0,))
r_other = check_action(admit_other, obs_off, grant_pa, budget, fam + [CoalitionSpec("C2", proxies={"p0","p1","p2"}, recipients={"R2"})], weights)
expect("item3_grant_token_scoped", not r_other.ok,
       "the grant token does NOT authorize a different recipient's grant")
# and NOT indices beyond the permitted effects
admit_wide = Action(ActionKind.ADMIT_GRANT, grant=Grant("G4","O","R1",sc,RecordRange("g",0,None),2,3,("p0","p1","p2"),7,None),
                    authorized_kfrag_indices=(0,1))
r_wide = check_action(admit_wide, obs_off, grant_pa, budget, fam, weights)
expect("item3_grant_token_effects", not r_wide.ok,
       "the grant token does NOT authorize kfrag indices beyond its permitted effects")

# ============================================================================================
# ITEM 4: threshold nontriviality under USABLE grants, with cfrag/mixed cases, honest collapse.
# A 2-of-3 grant G on scope A, record g:0 produced.
# ============================================================================================
def mk(indices_installed, cfrags=(), threshold=2):
    scA = Scope("g", 0); rec = Record("g", 0)
    ev = [StreamAuthorized(0, "O", "g", "D"), ScopeActivated(1, "O", scA, "g.k0", 0),
          RecordProduced(2, rec),
          GrantIssued(3, Grant("G", "O", "R", scA, RecordRange("g", 0, None), threshold, 3,
                               ("p0", "p1", "p2"), 0, None))]
    t = 4
    for i in indices_installed:
        ev.append(KFragInstalled(t, "G", f"p{i}", i)); t += 1
    for i in cfrags:
        ev.append(CFragProduced(t, "G", rec, i)); t += 1
    return ev

full = CoalitionSpec("C", proxies={"p0", "p1", "p2"}, recipients={"R"})
cannot = CoalitionSpec("C", proxies={"p0"}, recipients={"R"})       # reaches < threshold proxies
norec = CoalitionSpec("C", proxies={"p0", "p1", "p2"}, recipients=set())

# (a) family that CAN obtain a compatible threshold + recipient secret -> scope exposed
exp_can = len(possible_exposure(mk([0, 1]), full, 99, {}).future_scopes)
# (b) family that CANNOT obtain a compatible threshold (reaches 1 < 2) -> not exposed
exp_cannot = len(possible_exposure(mk([0, 1]), cannot, 99, {}).future_scopes)
# (c) no recipient secret -> not exposed
exp_norec = len(possible_exposure(mk([0, 1]), norec, 99, {}).future_scopes)
# (d) MIXED: 1 raw kfrag (idx0) + 1 cfrag (idx1) + recipient -> record openable (R3' mixed)
from delegation_model.closure import accumulate, conservative_closure
mixed_hist = mk([0], cfrags=(1,)) + [CorruptProxy(10, "p0", "C"), CorruptRecipient(11, "R", "C")]
cl_mixed = conservative_closure(accumulate(mixed_hist, "C", 11), mixed_hist, 11)
mixed_openable = Record("g", 0) in cl_mixed.records
expect("item4_threshold_family_exposed", exp_can == 1,
       "family with threshold proxies + recipient secret: scope exposed (usable grant)")
expect("item4_subthreshold_family_safe", exp_cannot == 0,
       "family that cannot reach a compatible threshold: NOT exposed")
expect("item4_no_recipient_safe", exp_norec == 0,
       "family without the recipient secret: NOT exposed")
expect("item4_mixed_fragments_openable", mixed_openable,
       "mixed raw-kfrag + cfrag + recipient opens the record (R3' capability captured)")
# nontriviality: a COMPLETED usable grant does NOT make exposure collapse to a flag in the
# threshold regime (same completed grant, different families -> different exposure).
expect("item4_no_collapse_threshold", not (exp_can == exp_cannot == exp_norec),
       "completed usable grant: exposure depends on family reach/recipient, NOT a per-scope flag")
# honest whole-key simplification: with threshold=1, a single installed fragment to a reached
# proxy + recipient exposes the scope; "a completed grant exists" is then closer to a flag.
exp_wholekey = len(possible_exposure(mk([0], threshold=1), full, 99, {}).future_scopes)
expect("item4_wholekey_collapses", exp_wholekey == 1,
       "HONEST: with threshold=1 (whole-key), one installed fragment exposes the scope -> closer "
       "to a per-scope flag; the nontriviality result holds only in the threshold>1 regime")

print(f"\n{len(FAIL)} failures" + (f": {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
