"""
P3D theoretical counterexamples (executable, against the REAL ServiceSimulator).

These justify the corrections to the dichotomy spine. Each inspects the ACTUAL disclosure ledger
(report()['actual_exposure'], the evaluator-only truth), not merely the public observable ledger.

CE-RETRO : a record produced under a scope and "fenced-safe" (scope not yet reconstructible) is
           RETROACTIVELY disclosed by a LATER grant on that scope whose range does NOT contain it.
           This refutes Theorem 2's claim that a fresh-scope record contributes 0 to L forever, and
           shows fencing must be an ONGOING whole-run invariant, not a one-time barrier.
CE-NEC   : with a disclosure budget B >= producible unauthorized weight, the delayed-production
           breach stays WITHIN budget without any fencing. This refutes the "iff": fencing is
           SUFFICIENT but NOT NECESSARY.
CE-REFUSE: a controller that never delivers a threshold of raw shares keeps L = 0 with no fencing
           and no rotation. A second witness that fencing is not necessary (admission refusal).

Exit 0 iff all counterexample properties hold (i.e., the old theorems are indeed refuted as claimed).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from fractions import Fraction
from delegation_model.types import Record, Scope, RecordRange
from delegation_model.service_clock import ServiceTime as T, TimeWindow
from delegation_model.demand_queue import Demand
from delegation_model.timed_log import PublicEvent, OwnerNotice, ScopeNotice, DemandArrival
from delegation_model.timed_authorization import TimedGrant
from delegation_model.timed_capabilities import Reach, Budget
from delegation_manager.service_simulator import (ServiceSimulator, RecordProduction, InstallGrant,
                                                  Transform, ActivateScope, Reject)

FAIL = []
def expect(cid, cond, msg):
    ok = bool(cond); print(f"[{'ok ' if ok else 'FAIL'}] {cid:<12} {msg}")
    if not ok: FAIL.append(cid)

def _n(eid, t, payload, avail=None):
    return PublicEvent(eid, T(t), T(t if avail is None else avail), payload)

def max_disclosed(sim):
    return max((float(m.disclosed_weight) for m in sim.report()['actual_exposure']), default=0.0)


# ============================================================================================
# CE-RETRO: retroactive disclosure of a fenced-safe record by a later grant on its scope.
# Setup: scope (g,0) active; records g:0 and g:1 produced under (g,0). A demand D wants ONLY g:1
# (range [1,2)). The manager installs a grant on (g,0) with range [1,2) and delivers 2 raw shares.
# openability then marks the WHOLE scope (g,0) exposed -> g:0 (range [0,1), NOT in the grant range)
# is opened and is COLLATERAL. g:0 was never authorized to the coalition; it is retroactively
# disclosed by a grant that did not even request it.
# ============================================================================================
r0, r1 = Record('g', 0), Record('g', 1)
demand = Demand('D', 'O', 'R', (r1,), T(0), T(40))      # wants only g:1
# g:0 is produced under (g,0) but its PUBLIC REPORT is DELAYED (available only at tick 20), so the
# online gate -- acting on the public view -- does NOT see g:0 when it admits the grant for g:1.
trace = (_n('up', 0, OwnerNotice('O', True)),
         _n('scope', 0, ScopeNotice('O', Scope('g', 0), 'key0', 0)),
         RecordProduction('r0', 'O', r0, T(0), T(20)),   # g:0 under (g,0); report DELAYED to tick 20
         RecordProduction('r1', 'O', r1, T(0), T(0)),    # g:1 under (g,0); reported immediately
         _n('arrival', 0, DemandArrival(demand)))
family = (Reach('declared', frozenset({'p0', 'p1', 'p2'}), frozenset({'R'})),)
budget = Budget(0, 0, 2)             # zero disclosed-weight budget: the gate WILL block visible collateral
grant_on_old = TimedGrant('G', 'O', 'R', Scope('g', 0), RecordRange('g', 1, 2), 2,  # range covers ONLY g:1
                          ('p0', 'p1', 'p2'), TimeWindow(T(0), T(40)))
sim = ServiceSimulator(trace, family, budget)
before = max_disclosed(sim)
# install the grant on (g,0) for g:1 and deliver two raw shares
r = sim.execute(InstallGrant('D', grant_on_old, (0, 1)), sim.view())
after = max_disclosed(sim)
# g:0 is outside the grant's range but under the exposed scope -> collateral disclosure
ledger_records = set()
for m in sim.report()['actual_exposure']:
    for rec, _t in m.disclosed:
        ledger_records.add((rec.stream, rec.seq))
# P3E UPDATE: the ENFORCEMENT boundary (actual-state whole-run gate) now BLOCKS this retroactive
# disclosure. The PUBLIC gate still could not see the delayed g:0 (observability gap preserved), but
# the enforcement boundary -- co-located with production truth -- refuses the delivery. So the
# historical hole is now CLOSED by execution, not merely detected. The counterexample is retained to
# document the hole and to prove the fix governs execution.
expect("CE-RETRO-1", before == 0.0,
       "before the delivery, actual disclosed weight is 0")
expect("CE-RETRO-2", r.status in ('refused', 'interrupted') and
       'enforcement' in (r.reason or ''),
       f"P3E: the ENFORCEMENT boundary REFUSES the retroactive-disclosing delivery ({r.status}: "
       f"{r.reason}) -- the public gate could not see the delayed g:0, but the authority boundary can")
expect("CE-RETRO-3", after == 0.0 and ('g', 0) not in ledger_records,
       f"P3E: actual disclosed weight stays {after}; g:0 is NOT in the ledger -> the retroactive "
       f"collateral disclosure is PREVENTED. (In the public-gate-only P3D design it reached 1; the "
       f"enforcement boundary closes the hole while preserving the public/enforcement distinction.)")

# ============================================================================================
# CE-NEC: fencing is NOT necessary when the budget can absorb the disclosure.
# The delayed-production breach with a disclosed-weight budget of 1 stays within budget WITHOUT
# any rotation/fencing: L reaches 1, and 1 <= B. So fencing is sufficient but not necessary.
# ============================================================================================
rr0, rr1 = Record('g', 0), Record('g', 1)
dem2 = Demand('D', 'O', 'R', (rr0,), T(0), T(40))
trace2 = (_n('up', 0, OwnerNotice('O', True)),
          _n('scope', 0, ScopeNotice('O', Scope('g', 0), 'key0', 0)),
          RecordProduction('r0', 'O', rr0, T(0), T(0)),
          _n('arrival', 0, DemandArrival(dem2)),
          RecordProduction('r1', 'O', rr1, T(4), T(8)))   # delayed-report production under (g,0)
g2 = TimedGrant('G', 'O', 'R', Scope('g', 0), RecordRange('g', 0, 1), 2, ('p0', 'p1', 'p2'),
                TimeWindow(T(0), T(40)))
budget_absorb = Budget(2, 2, 2)        # budget >= 1 absorbs the breach
sim2 = ServiceSimulator(trace2, family, budget_absorb)
sim2.execute(InstallGrant('D', g2, (0, 1)), sim2.view())      # install, no rotation/fencing
sim2.execute(Transform('D', 'G', (0, 1)), sim2.view())
disc2 = max_disclosed(sim2)
within = all(m.within(budget_absorb) if hasattr(m, 'within') else float(m.disclosed_weight) <= 2
             for m in sim2.report()['actual_exposure'])
expect("CE-NEC-1", disc2 >= 1.0,
       f"without fencing, a delayed-production breach discloses weight {disc2}")
expect("CE-NEC-2", disc2 <= 2.0,
       "...but it stays WITHIN a budget of 2 -> fencing is NOT necessary (the 'iff' is refuted); "
       "fencing is one SUFFICIENT mechanism among others (here: a large enough budget).")

# ============================================================================================
# CE-REFUSE: admission refusal keeps L = 0 with no fencing and no rotation.
# The manager simply rejects the demand; no shares are ever delivered; no scope becomes
# reconstructible; actual disclosure stays 0 across the delayed-production trace.
# ============================================================================================
sim3 = ServiceSimulator(trace2, family, Budget(0, 0, 2))
sim3.execute(Reject('D'), sim3.view())
# advance through the delayed production by a no-op defer-free run: just read the final report
disc3 = max_disclosed(sim3)
expect("CE-REFUSE", disc3 == 0.0,
       "admission refusal: no threshold delivery -> no scope reconstructible -> actual disclosure "
       "stays 0 with NO fencing. A second witness that fencing is not necessary.")

print(f"\n{len(FAIL)} failures" + (f": {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
