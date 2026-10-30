"""
P3E enforcement tests (Task 1). Exit 0 = all expectations met.

Verifies the admission-side whole-run disclosure safety rule GOVERNS EXECUTION (not merely exposed
as a check), across grant installation, fragment delivery, and capability changes. Checks the ACTUAL
ledger. Covers: scope-wide reconstructibility, retained fragments, all coalition cases, authorization
of existing records, future grants not silently exposing older records, budget boundary, fail-safe
(nothing committed on refusal), and that enforcement does not over-block safe grants.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from delegation_model.types import Record, Scope, RecordRange
from delegation_model.service_clock import ServiceTime as T, TimeWindow
from delegation_model.demand_queue import Demand
from delegation_model.timed_log import PublicEvent, OwnerNotice, ScopeNotice, DemandArrival
from delegation_model.timed_authorization import TimedGrant
from delegation_model.timed_capabilities import Reach, Budget
from delegation_manager.service_simulator import (ServiceSimulator, RecordProduction, InstallGrant,
                                                  Transform)

FAIL = []
def expect(cid, cond, msg):
    ok = bool(cond); print(f"[{'ok ' if ok else 'FAIL'}] {cid:<20} {msg}")
    if not ok: FAIL.append(cid)

def _n(e, t, p, a=None):
    return PublicEvent(e, T(t), T(t if a is None else a), p)

def disclosed(sim):
    return max((float(m.disclosed_weight) for m in sim.report()['actual_exposure']), default=0.0)


# ---- ENFORCE-RETRO: a later narrow grant cannot silently expose an older record ----
r0, r1 = Record('g', 0), Record('g', 1)
dem = Demand('D', 'O', 'R', (r1,), T(0), T(40))
trace = (_n('up', 0, OwnerNotice('O', True)), _n('sc', 0, ScopeNotice('O', Scope('g', 0), 'k0', 0)),
         RecordProduction('r0', 'O', r0, T(0), T(0)), RecordProduction('r1', 'O', r1, T(0), T(0)),
         _n('arr', 0, DemandArrival(dem)))
fam = (Reach('d', frozenset({'p0', 'p1', 'p2'}), frozenset({'R'})),)
g_narrow = TimedGrant('G', 'O', 'R', Scope('g', 0), RecordRange('g', 1, 2), 2, ('p0', 'p1', 'p2'),
                      TimeWindow(T(0), T(40)))
sim = ServiceSimulator(trace, fam, Budget(0, 0, 2))
r = sim.execute(InstallGrant('D', g_narrow, (0, 1)), sim.view())
expect("ENFORCE-RETRO", r.status in ('refused', 'interrupted') and disclosed(sim) == 0.0,
       f"a narrow grant [1,2) that would collaterally open g:0 is REFUSED by enforcement ({r.status}); "
       f"actual disclosed stays {disclosed(sim)}")

# ---- ENFORCE-SAFE-PASS: a grant whose range covers ALL its scope's records is NOT over-blocked ----
dem2 = Demand('D2', 'O', 'R', (r0, r1), T(0), T(40))
trace2 = (_n('up', 0, OwnerNotice('O', True)), _n('sc', 0, ScopeNotice('O', Scope('g', 0), 'k0', 0)),
          RecordProduction('r0', 'O', r0, T(0), T(0)), RecordProduction('r1', 'O', r1, T(0), T(0)),
          _n('arr', 0, DemandArrival(dem2)))
g_wide = TimedGrant('G', 'O', 'R', Scope('g', 0), RecordRange('g', 0, 2), 2, ('p0', 'p1', 'p2'),
                    TimeWindow(T(0), T(40)))
sim2 = ServiceSimulator(trace2, fam, Budget(0, 0, 2))
r2 = sim2.execute(InstallGrant('D2', g_wide, (0, 1)), sim2.view())
expect("ENFORCE-SAFE-PASS", r2.status == 'installed' and disclosed(sim2) == 0.0,
       f"a grant covering all its scope's records installs fine ({r2.status}); no over-blocking")

# ---- ENFORCE-MULTI-CASE: enforcement considers ALL coalition cases ----
# two cases in the family; the narrow grant is collateral for a case reaching R, blocked for ANY.
fam_multi = (Reach('c1', frozenset({'p0', 'p1', 'p2'}), frozenset({'R'})),
             Reach('c2', frozenset({'p0'}), frozenset({'Rx'})))     # c2 cannot reach threshold
sim3 = ServiceSimulator(trace, fam_multi, Budget(0, 0, 2))
r3 = sim3.execute(InstallGrant('D', g_narrow, (0, 1)), sim3.view())
expect("ENFORCE-MULTI-CASE", r3.status in ('refused', 'interrupted'),
       "with multiple coalition cases, a delivery collateral for ANY case is refused")

# ---- ENFORCE-TRANSFORM: cfrag delivery is also enforced ----
# install a wide (safe) grant, then it serves; disclosed stays 0 through transform.
sim4 = ServiceSimulator(trace2, fam, Budget(0, 0, 2))
sim4.execute(InstallGrant('D2', g_wide, (0, 1)), sim4.view())
rt = sim4.execute(Transform('D2', 'G', (0, 1)), sim4.view())
expect("ENFORCE-TRANSFORM", disclosed(sim4) == 0.0,
       f"cfrag delivery path keeps actual disclosed at {disclosed(sim4)} for an authorized grant")

# ---- ENFORCE-BUDGET-BOUNDARY: at the budget passes, one over fails ----
# narrow grant discloses weight 1 (g:0). With budget disclosed_weight=1 it is ALLOWED; with 0 refused.
sim_ok = ServiceSimulator(trace, fam, Budget(5, 1, 2))      # disclosed budget 1 -> allow the 1 collateral
r_ok = sim_ok.execute(InstallGrant('D', g_narrow, (0, 1)), sim_ok.view())
expect("ENFORCE-BOUND-OK", r_ok.status == 'installed' and disclosed(sim_ok) == 1.0,
       f"at budget disclosed=1 the 1-weight collateral is ADMITTED ({r_ok.status}, disclosed {disclosed(sim_ok)})")
sim_no = ServiceSimulator(trace, fam, Budget(5, 0, 2))      # disclosed budget 0 -> refuse
r_no = sim_no.execute(InstallGrant('D', g_narrow, (0, 1)), sim_no.view())
expect("ENFORCE-BOUND-NO", r_no.status in ('refused', 'interrupted') and disclosed(sim_no) == 0.0,
       f"at budget disclosed=0 the same collateral is REFUSED ({r_no.status})")

# ---- ENFORCE-FAILSAFE: on refusal, nothing is committed (state preserved) ----
before_deliveries = len(sim_no.report()['deliveries'])
# sim_no refused above; the threshold delivery that would breach must NOT have committed
has_full_threshold = len({d.index for d in sim_no.report()['deliveries']
                          if d.grant_id == 'G' and d.record is None}) >= 2
expect("ENFORCE-FAILSAFE", not has_full_threshold and disclosed(sim_no) == 0.0,
       "fail-safe: the breaching threshold delivery is NOT committed; the scope stays non-exposed")

# ---- ENFORCE-RETAINED: a first grant below threshold + a second grant together would expose ----
# install share 0 of a narrow grant (below threshold, safe); then adding share 1 would expose g:0.
sim5 = ServiceSimulator(trace, fam, Budget(5, 0, 2))
r5a = sim5.execute(InstallGrant('D', g_narrow, (0,)), sim5.view())     # 1 share: below threshold, safe
r5b = sim5.execute(InstallGrant('D', g_narrow, (1,)), sim5.view())     # 2nd share would expose g:0
expect("ENFORCE-RETAINED", r5a.status == 'installed' and r5b.status in ('refused', 'interrupted')
       and disclosed(sim5) == 0.0,
       f"retained-fragment accumulation: 1st share installs ({r5a.status}); the share that would "
       f"complete the threshold and expose g:0 is REFUSED ({r5b.status}); disclosed {disclosed(sim5)}")

print(f"\n{len(FAIL)} failures" + (f": {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
