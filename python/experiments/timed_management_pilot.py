"""Scripted deterministic P3B model traces. No controller, crypto timing or benchmark."""
import sys,json
from pathlib import Path
from dataclasses import asdict,is_dataclass
from enum import Enum
from fractions import Fraction
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from delegation_model.types import Record,Scope,RecordRange
from delegation_model.service_clock import ServiceTime as T,TimeWindow
from delegation_model.demand_queue import Demand
from delegation_model.timed_log import PublicEvent,OwnerNotice,ScopeNotice,DemandArrival
from delegation_model.timed_authorization import TimedGrant
from delegation_model.timed_capabilities import Reach,Budget
from delegation_manager.service_simulator import (ServiceSimulator,RecordProduction,InstallGrant,
    Transform,ActivateScope,Defer)

def encode(v):
    if isinstance(v,Fraction):
        return v.numerator if v.denominator==1 else {'numerator':v.numerator,'denominator':v.denominator}
    if is_dataclass(v):return encode(asdict(v))
    if isinstance(v,Enum):return v.value
    if isinstance(v,dict):return {str(k):encode(x) for k,x in v.items()}
    if isinstance(v,(tuple,list,set,frozenset)):return [encode(x) for x in v]
    return v

def notice(event_id,t,p,available=None):
    return PublicEvent(event_id,T(t),T(t if available is None else available),p)

def fixture(extra=(),deadline=30,budget=Budget(100,100,5)):
    r=Record('g',0);d=Demand('D','O','R',(r,),T(0),T(deadline))
    trace=(notice('up',0,OwnerNotice('O',True)),notice('scope',0,ScopeNotice('O',Scope('g',0),'key0',0)),
           RecordProduction('r0','O',r,T(0),T(0)),notice('arrival',0,DemandArrival(d)))+extra
    family=(Reach('declared',frozenset({'p0','p1','p2'}),frozenset({'R'})),)
    g=TimedGrant('G','O','R',Scope('g',0),RecordRange('g',0,1),2,('p0','p1','p2'),TimeWindow(T(0),T(30)))
    return ServiceSimulator(trace,family,budget),g

def scripted(sim,actions):
    records=[]
    for action in actions:
        v=sim.view();result=sim.execute(action,v)
        records.append({'public_time_before':v.observation.now,'public_sequence_before':v.observation.version,
                        'action_type':type(action).__name__,'action':action,'result':result,
                        'public_time_after':sim.now,'queue_after':sim.view().queue.metrics()})
    return {'actions':records,'evaluator_report':sim.report()}

def main():
    traces={}
    s,g=fixture((notice('down',4,OwnerNotice('O',False)),))
    traces['usable_existing_grant_owner_offline']=scripted(s,(InstallGrant('D',g,(0,1)),Transform('D','G',(0,1))))
    assert s.report()['queue'].served==1
    s,g=fixture((notice('down',3,OwnerNotice('O',False)),))
    traces['partial_install_interrupted']=scripted(s,(InstallGrant('D',g,(0,1)),Defer('D',T(5))))
    assert len(s.report()['deliveries'])==1 and s.report()['queue'].served==0
    s,g=fixture(deadline=6)
    traces['completion_exact_deadline']=scripted(s,(InstallGrant('D',g,(0,1)),Transform('D','G',(0,1))))
    assert s.report()['queue'].expired==1 and len(s.report()['deliveries'])==4
    s,g=fixture((RecordProduction('r1','O',Record('g',1),T(4),T(8)),),budget=Budget(0,0,1))
    traces['delayed_production_breach_then_mitigation']=scripted(s,(InstallGrant('D',g,(0,1)),Defer('D',T(8)),
        ActivateScope(ScopeNotice('O',Scope('g',1),'key1',2))))
    assert max(m.disclosed_weight for m in s.report()['actual_exposure'])==1
    assert max(len(m.active_scopes) for m in s.report()['actual_exposure'])==0
    s,g=fixture((RecordProduction('r1','O',Record('g',1),T(5),T(7)),),budget=Budget(0,0,1))
    traces['rotation_before_production_keeps_old_target_usable']=scripted(s,(InstallGrant('D',g,(0,1)),
        ActivateScope(ScopeNotice('O',Scope('g',1),'key1',1)),Transform('D','G',(0,1))))
    assert s.report()['queue'].served==1
    assert max(m.disclosed_weight for m in s.report()['actual_exposure'])==0
    assert s.report()['truth_records'][1][0].scope==Scope('g',1)
    payload={'batch':'P3B','kind':'scripted model traces; no policy comparison or measured crypto',
             'backend':'abstract-cfrag-usability-model','traces':traces}
    out=Path(__file__).resolve().parents[2]/'results/manifests/p3b_timed_management_pilot.json'
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(encode(payload),indent=2)+'\n')
    print(json.dumps({'traces':len(traces),'assertions':'passed','output':str(out.relative_to(out.parents[2])),
                      'publication_performance':False},indent=2))
if __name__=='__main__':main()
