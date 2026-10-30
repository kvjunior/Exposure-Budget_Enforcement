"""Review R5 (stream-ownership authority) and R6 (fresh-scope rollover). PROD venv. Exit 0 = ok."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from delegation_model.types import Grant, Record, RecordRange, Scope
from delegation_model.events import StreamAuthorized, ScopeActivated, RecordProduced, OwnerAvailability
from delegation_manager.manager import project_observation, check_action, Action, ActionKind, PreAuth
FAIL=[]
def expect(cid,cond,msg):
    ok=bool(cond); print(f"[{'ok ' if ok else 'FAIL'}] {cid:<26} {msg}")
    if not ok: FAIL.append(cid)
sc=Scope("g",0)
base=[StreamAuthorized(0,"O","g","D"),ScopeActivated(1,"O",sc,"k0",0),
      RecordProduced(2,Record("g",0)),OwnerAvailability(3,"O",True)]
obs=project_observation(base,3)

# R5: foreign issuer rejected
foreign=Grant("F","ATTACKER","R",sc,RecordRange("g",0,1),2,3,("p0","p1","p2"),4,None)
r=check_action(Action(ActionKind.ADMIT_GRANT,grant=foreign),obs,PreAuth())
expect("R5_foreign_rejected", not r.ok, f"foreign issuer rejected: {r.reason}")
# legit issuer accepted (no fragment delivery declared -> no exposure gate needed)
legit=Grant("G","O","R",sc,RecordRange("g",0,1),2,3,("p0","p1","p2"),4,None)
r2=check_action(Action(ActionKind.ADMIT_GRANT,grant=legit),obs,PreAuth())
expect("R5_owner_accepted", r2.ok, f"registered owner accepted: {r2.reason}")
# unregistered stream rejected
other=Grant("X","O","R",Scope("z",0),RecordRange("z",0,1),2,3,("p0","p1","p2"),4,None)
r3=check_action(Action(ActionKind.ADMIT_GRANT,grant=other),obs,PreAuth())
expect("R5_unregistered_rejected", not r3.ok, f"unregistered stream rejected: {r3.reason}")

# R6: re-activating an already-active scope is rejected
same=Action(ActionKind.ACTIVATE_SCOPE,scope=sc,new_scope_key_id="k1",start_seq=1)
r4=check_action(same,obs,PreAuth())
expect("R6_reactivate_rejected", not r4.ok, f"already-active scope rejected: {r4.reason}")
# a genuinely fresh scope with new key id and valid start_seq is accepted
fresh=Action(ActionKind.ACTIVATE_SCOPE,scope=Scope("g",1),new_scope_key_id="k1",start_seq=1)
r5=check_action(fresh,obs,PreAuth())
expect("R6_fresh_accepted", r5.ok, f"fresh scope accepted: {r5.reason}")
# fresh scope reusing an old key id rejected
reuse=Action(ActionKind.ACTIVATE_SCOPE,scope=Scope("g",1),new_scope_key_id="k0",start_seq=1)
r6=check_action(reuse,obs,PreAuth())
expect("R6_reused_keyid_rejected", not r6.ok, f"reused key id rejected: {r6.reason}")
# start_seq that reassigns already-produced records rejected (next seq is 1; start 0 reassigns)
reassign=Action(ActionKind.ACTIVATE_SCOPE,scope=Scope("g",1),new_scope_key_id="k1",start_seq=0)
r7=check_action(reassign,obs,PreAuth())
expect("R6_reassign_rejected", not r7.ok, f"start_seq reassigning old records rejected: {r7.reason}")
# missing freshness fields rejected
nofresh=Action(ActionKind.ACTIVATE_SCOPE,scope=Scope("g",1))
r8=check_action(nofresh,obs,PreAuth())
expect("R6_missing_fields_rejected", not r8.ok, f"missing key id/start_seq rejected: {r8.reason}")

print(f"\n{len(FAIL)} failures"+(f": {FAIL}" if FAIL else "")); sys.exit(1 if FAIL else 0)
