"""
P3D production-fencing tests (Task 3). Exit 0 = all expectations met.

Drives the REAL simulator with the concrete fence (production_fence.py) and checks the ACTUAL
disclosure ledger (report()['actual_exposure']), not just the public ledger.

Cases:
  FENCE-SAFE     : when the active scope is reconstructible, the fence ROTATES before the production,
                   binding the record to a fresh scope -> actual disclosed weight stays 0
                   (the Theorem-1 breach is PREVENTED by production-time fencing).
  FENCE-DEFER    : when the active scope is reconstructible AND the owner is offline with no preauth,
                   the fence REJECTS/DEFERS the production -> no record is bound under the exposed
                   scope -> actual disclosed weight stays 0 (explicit safe fallback).
  FENCE-SAFE-NOOP: when the active scope is NOT reconstructible, the fence produces on the current
                   scope (no needless rotation).
  RETRO-CHECK    : the admission-side check `admission_would_retroactively_disclose` flags the
                   records a grant would collaterally disclose (the CE-RETRO records), so the manager
                   can refuse. Positive and negative.
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
                                                  Transform, ActivateScope)
from delegation_manager.production_fence import (decide_fence, scope_reconstructible,
                                                 active_scope_on, admission_would_retroactively_disclose,
                                                 FenceOutcome, FenceLog)

FAIL = []
def expect(cid, cond, msg):
    ok = bool(cond); print(f"[{'ok ' if ok else 'FAIL'}] {cid:<16} {msg}")
    if not ok: FAIL.append(cid)

def _n(eid, t, payload, avail=None):
    return PublicEvent(eid, T(t), T(t if avail is None else avail), payload)

def max_disclosed(sim):
    return max((float(m.disclosed_weight) for m in sim.report()['actual_exposure']), default=0.0)

family = (Reach('declared', frozenset({'p0', 'p1', 'p2'}), frozenset({'R'})),)


def build_breach_trace(owner_online_at_prod=True, fenced=False):
    """Scope (g,0) active; demand for g:0; a later production of g:1 under the exposed scope at tick 4.
    If `fenced`, a rotation scope-notice is interposed at tick 3 (before the tick-4 production), so
    g:1 binds to a fresh scope (g,1). If owner goes offline, fencing cannot rotate -> the fenced
    variant OMITS the production (reject/defer)."""
    r0, r1 = Record('g', 0), Record('g', 1)
    dem = Demand('D', 'O', 'R', (r0,), T(0), T(40))
    base = [_n('up', 0, OwnerNotice('O', True)),
            _n('scope', 0, ScopeNotice('O', Scope('g', 0), 'key0', 0)),
            RecordProduction('r0', 'O', r0, T(0), T(0)),
            _n('arrival', 0, DemandArrival(dem))]
    if not owner_online_at_prod:
        # owner drops at tick 4, AFTER a 2-share install completes (raw deliveries at ticks 2 and 3)
        # so the scope IS reconstructible, but before a later production -> fencing cannot rotate.
        base.append(_n('down', 4, OwnerNotice('O', False)))
    if fenced:
        if owner_online_at_prod:
            # fence rotates to (g,1) at tick 3, then g:1 is produced under (g,1) at tick 4 (SAFE)
            base.append(_n('rotate', 3, ScopeNotice('O', Scope('g', 1), 'key1', 1)))
            base.append(RecordProduction('r1', 'O', r1, T(4), T(8)))
        else:
            # cannot rotate (owner offline) -> fence REJECTS the production: g:1 is NOT emitted
            pass
    else:
        # unfenced: g:1 is produced under the exposed (g,0) at tick 4 (BREACH)
        base.append(RecordProduction('r1', 'O', r1, T(4), T(8)))
    g = TimedGrant('G', 'O', 'R', Scope('g', 0), RecordRange('g', 0, 1), 2, ('p0', 'p1', 'p2'),
                   TimeWindow(T(0), T(40)))
    return tuple(base), g


# ---- FENCE-SAFE: fenced run prevents the breach ----
# First confirm the fence DECISION is ROTATE when the scope is reconstructible.
tr_u, g = build_breach_trace(fenced=False)
sim = ServiceSimulator(tr_u, family, Budget(0, 0, 2))
sim.execute(InstallGrant('D', g, (0, 1)), sim.view())          # make (g,0) reconstructible
state = sim._state(True)                                        # evaluator/actual state
dec = decide_fence(state, family, 'g', owner_online=True, preauth_ok=False)
expect("FENCE-DECIDE", dec.outcome == FenceOutcome.ROTATE_THEN_PRODUCE and dec.rotated,
       f"fence decides ROTATE_THEN_PRODUCE when the active scope is reconstructible ({dec.reason})")

# unfenced run -> breach (actual disclosed weight reaches 1)
sim_u = ServiceSimulator(tr_u, family, Budget(5, 5, 2))        # budget large so install proceeds
sim_u.execute(InstallGrant('D', g, (0, 1)), sim_u.view())
sim_u.execute(Transform('D', 'G', (0, 1)), sim_u.view())
expect("FENCE-UNFENCED-BREACH", max_disclosed(sim_u) >= 1.0,
       f"UNFENCED: actual disclosed weight reaches {max_disclosed(sim_u)} (breach)")

# fenced run -> the realized trace binds g:1 to (g,1); actual disclosed weight stays 0
tr_f, gf = build_breach_trace(fenced=True)
sim_f = ServiceSimulator(tr_f, family, Budget(5, 5, 2))
sim_f.execute(InstallGrant('D', gf, (0, 1)), sim_f.view())
sim_f.execute(Transform('D', 'G', (0, 1)), sim_f.view())
# confirm g:1 bound to (g,1) and no collateral
g1_scope = [n.scope for n, _ in sim_f.report()['truth_records'] if n.record == Record('g', 1)]
expect("FENCE-SAFE-BIND", g1_scope and g1_scope[0] == Scope('g', 1),
       "FENCED: g:1 is bound to the fresh scope (g,1), not the exposed (g,0)")
expect("FENCE-SAFE-LEDGER", max_disclosed(sim_f) == 0.0,
       f"FENCED: actual disclosed weight stays {max_disclosed(sim_f)} -> breach prevented")

# ---- FENCE-DEFER/REJECT: owner offline at production -> no production under exposed scope ----
tr_off, goff = build_breach_trace(owner_online_at_prod=False, fenced=True)   # g:1 omitted (rejected)
sim_off = ServiceSimulator(tr_off, family, Budget(5, 5, 2))
sim_off.execute(InstallGrant('D', goff, (0, 1)), sim_off.view())            # installs fully while online
# confirm the scope IS reconstructible now (owner was online through install)
st_off = sim_off._state(True)
expect("FENCE-REJECT-SETUP", scope_reconstructible(st_off, family, Scope('g', 0)),
       "setup: (g,0) is reconstructible after the full install (owner online through install)")
# owner is offline at production time -> fence cannot rotate
dec_off = decide_fence(st_off, family, 'g', owner_online=False, preauth_ok=False)
produced_records = {(n.record.stream, n.record.seq) for n, _ in sim_off.report()['truth_records']}
expect("FENCE-REJECT-DECIDE", dec_off.outcome in (FenceOutcome.REJECT, FenceOutcome.DEFER),
       f"fence decides {dec_off.outcome.value} when scope reconstructible and owner offline ({dec_off.reason})")
expect("FENCE-REJECT-LEDGER", max_disclosed(sim_off) == 0.0 and ('g', 1) not in produced_records,
       "FENCED+offline: g:1 is NOT produced under the exposed scope -> actual disclosed weight 0")

# ---- FENCE-SAFE-NOOP: scope not reconstructible -> produce on current scope, no rotation ----
tr_noop, _ = build_breach_trace(fenced=False)
sim_noop = ServiceSimulator(tr_noop, family, Budget(5, 5, 2))   # NO grant installed -> not reconstructible
st_noop = sim_noop._state(True)
dec_noop = decide_fence(st_noop, family, 'g', owner_online=True, preauth_ok=False)
expect("FENCE-NOOP", dec_noop.outcome == FenceOutcome.PRODUCE_CURRENT and not dec_noop.rotated,
       f"fence produces on current scope when not reconstructible ({dec_noop.reason})")

# ---- RETRO-CHECK: admission-side retroactive-disclosure detector ----
# scope (g,0) has g:0 and g:1; a grant on (g,0) range [1,2) would collaterally disclose g:0.
r0b, r1b = Record('g', 0), Record('g', 1)
tr_r = (_n('up', 0, OwnerNotice('O', True)),
        _n('scope', 0, ScopeNotice('O', Scope('g', 0), 'key0', 0)),
        RecordProduction('r0', 'O', r0b, T(0), T(0)),
        RecordProduction('r1', 'O', r1b, T(0), T(0)))
sim_r = ServiceSimulator(tr_r, family, Budget(5, 5, 2))
state_r = sim_r._state(True)
grant_narrow = TimedGrant('G', 'O', 'R', Scope('g', 0), RecordRange('g', 1, 2), 2,
                          ('p0', 'p1', 'p2'), TimeWindow(T(0), T(40)))
collateral = admission_would_retroactively_disclose(state_r, family, grant_narrow, (0, 1))
expect("RETRO-POS", Record('g', 0) in collateral,
       f"admission check flags g:0 as collateral for a grant on (g,0) range [1,2): {[(r.stream,r.seq) for r in collateral]}")
# a grant covering the whole scope ([0,2)) discloses nothing extra (all authorized)
grant_wide = TimedGrant('G2', 'O', 'R', Scope('g', 0), RecordRange('g', 0, 2), 2,
                        ('p0', 'p1', 'p2'), TimeWindow(T(0), T(40)))
collateral2 = admission_would_retroactively_disclose(state_r, family, grant_wide, (0, 1))
expect("RETRO-NEG", collateral2 == [],
       "admission check flags NOTHING for a grant whose range covers all scope records (no collateral)")
# below threshold -> no exposure -> nothing flagged
collateral3 = admission_would_retroactively_disclose(state_r, family, grant_narrow, (0,))
expect("RETRO-SUBTHRESH", collateral3 == [],
       "below threshold delivery exposes nothing -> no collateral flagged")

print(f"\n{len(FAIL)} failures" + (f": {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
