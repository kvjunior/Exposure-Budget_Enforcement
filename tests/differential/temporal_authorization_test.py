"""Review R7 (expiry at cutoff) and R8 (post-revocation authorization). PROD venv. Exit 0 = ok."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "python"))
from delegation_model.types import Grant, Record, RecordRange, Scope
from delegation_model.events import StreamAuthorized, ScopeActivated, RecordProduced, GrantIssued
from delegation_model.authorization import fold_authorization
from delegation_model.loader import load_events
from delegation_model.closure import accumulate, conservative_closure, exposure
from reference.witness import history_exposed
FAIL=[]
def expect(cid,cond,msg):
    ok=bool(cond); print(f"[{'ok ' if ok else 'FAIL'}] {cid:<22} {msg}")
    if not ok: FAIL.append(cid)

# R7: grant expiring at t=5 is NOT live at cutoff 10 even if last event was t=3
sc=Scope("g",0); rec=Record("g",0)
expiry=Grant("EXP","O","R",sc,RecordRange("g",0,1),1,1,("p0",),0,5)
events=[StreamAuthorized(0,"O","g","D"),ScopeActivated(1,"O",sc,"k0",0),
        RecordProduced(2,rec),GrantIssued(3,expiry)]
st=fold_authorization(events, now=10)
expect("R7_expired_at_cutoff", not st.authorized("R",rec),
       f"grant expiring at 5 is not authorized at cutoff 10 (state.now={st.now})")
# still live within the window
st5=fold_authorization(events, now=5)
expect("R7_live_within_window", st5.authorized("R",rec),
       "grant is live at cutoff 5 (inclusive valid_to)")
# future valid_from not yet live
future=Grant("FUT","O","R",sc,RecordRange("g",0,1),1,1,("p0",),8,None)
ev2=events+[GrantIssued(4,future)]
st_early=fold_authorization(ev2, now=6)
expect("R7_future_valid_from", not st_early.authorized("R",rec),
       "a grant with valid_from=8 is not authorized at cutoff 6")

# R8: post-revocation newly produced record counts as collateral exposure, not exempt
broad=history_exposed()
for e in broad:
    if e["type"]=="GrantIssued": e["grant"]["rng"]=["g",0,None]
broad+=[{"t":12,"type":"RecordProduced","record":["g",2],"weight":1.0},
        {"t":13,"type":"ScopeActivated","owner":"O","scope":["g",1],"scope_key_id":"g.e1.k0","start_seq":3}]
events=load_events(broad); r2=Record("g",2)
K=accumulate(events,"C",13); cl=conservative_closure(K,events,13)
x=exposure(K,events,13,{Record('g',0):1.0,Record('g',1):1.0,r2:1.0})
authorized_now=fold_authorization(events,13).authorized("R",r2)
expect("R8_post_rev_openable", r2 in cl.records, "post-revocation record g:2 is openable by C")
expect("R8_not_authorized_now", not authorized_now, "g:2 not currently authorized")
expect("R8_counts_as_past", x.past==1.0,
       f"g:2 (produced AFTER revocation) counts as collateral past exposure (past={x.past})")

# R8 complement: a record produced WHILE the grant was live stays authorized (not collateral)
# g:0 and g:1 were produced at t=2,3; grant G1 valid_from=4 -> they were produced BEFORE the
# grant, so under prospective semantics they are NOT within its live window either. Use a record
# produced during the window: add one at t=5 (grant live until revocation t=8/11).
live_hist=history_exposed()
for e in live_hist:
    if e["type"]=="GrantIssued": e["grant"]["rng"]=["g",0,None]
# find revocation time
live_hist+=[{"t":5,"type":"RecordProduced","record":["g",2],"weight":1.0}]
ev3=load_events(live_hist)
K3=accumulate(ev3,'C',12); x3=exposure(K3,ev3,12,{Record('g',0):1.0,Record('g',1):1.0,Record('g',2):1.0})
# g:2 here produced at t=5; grant valid_from=4, revoked at t=8 -> within window -> authorized,
# so NOT collateral.
expect("R8_live_window_not_collateral", x3.past==0.0,
       f"a record produced WHILE the grant was live is authorized, not collateral (past={x3.past})")

print(f"\n{len(FAIL)} failures"+(f": {FAIL}" if FAIL else "")); sys.exit(1 if FAIL else 0)
