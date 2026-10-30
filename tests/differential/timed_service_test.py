"""P3B causal integration and retained-effect tests; implementer-authored."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import itertools,json,unittest
from dataclasses import replace
from delegation_model.types import Scope,Record,RecordRange
from delegation_model.service_clock import ServiceTime as T,TimeWindow as W
from delegation_model.demand_queue import Demand,DemandStatus
from delegation_model.timed_log import PublicEvent as E,OwnerNotice,ScopeNotice,DemandArrival,RecordNotice
from delegation_model.timed_authorization import TimedGrant,GrantToken,ActivationToken,project
from delegation_model.timed_capabilities import Reach,Budget,family_cases,Delivery,CapabilityState,IssuedGrant,openability,assess
from delegation_manager.service_simulator import (ServiceSimulator,RecordProduction,InstallGrant,
    Transform,ActivateScope,RevokeGrant,Defer,Reject,ModelBackend,UsableResult)
R=Record('g',0);S=Scope('g',0);SEED=ScopeNotice('O',S,'key0',0)
FAMILY=(Reach('C',frozenset({'p0','p1','p2'}),frozenset({'R'})),)
LIMIT=Budget(100,100,5);OBSERVATIONS={}
def owner(event_id,at,up,available=None):
    return E(event_id,T(at),T(at if available is None else available),OwnerNotice('O',up))
def demand(deadline=30,demand_id='D',targets=(R,),recipient='R',release=0):
    return Demand(demand_id,'O',recipient,targets,T(release),T(deadline))
def grant(valid_to=30,threshold=2,recipient='R',scope=S,rng=None,grant_id='G'):
    return TimedGrant(grant_id,'O',recipient,scope,RecordRange('g',0,1) if rng is None else rng,
                      threshold,('p0','p1','p2'),W(T(0),T(valid_to)))
def base(extra=(),*,d=None,family=FAMILY,budget=LIMIT,tokens=(),online=True,backend=None):
    d=demand() if d is None else d
    trace=(owner('up',0,online),E('scope0',T(0),T(0),SEED),
           RecordProduction('record0','O',R,T(0),T(0)),
           E('arrival',d.released_at,d.released_at,DemandArrival(d)))+extra
    return ServiceSimulator(trace,family,budget,tokens,backend)
def run(s,a):return s.execute(a,s.view())
def metrics(s):return s.report()['queue']
class TimedServiceTests(unittest.TestCase):
    def test_durations_and_typed_inputs(self):
        for x in (0,-1,True,1.2):
            with self.assertRaises((TypeError,ValueError)):InstallGrant('D',grant(),(0,),step_ticks=x)
        for idx in ((True,),(-1,),(3,),(1,0),(0,0)):
            with self.assertRaises((TypeError,ValueError)):InstallGrant('D',grant(),idx)
        with self.assertRaises(TypeError):ServiceSimulator([],FAMILY,LIMIT)
        with self.assertRaises(ValueError):grant(threshold=True)
        with self.assertRaises(ValueError):replace(grant(),proxies=('p0','p0'))
    def test_metadata_never_serves(self):
        s=base();r=run(s,InstallGrant('D',grant(),()))
        self.assertEqual(r.status,'installed');self.assertEqual(r.delivered,())
        self.assertEqual(metrics(s).served,0);self.assertEqual(metrics(s).pending,1);self.assertEqual(s.now,T(1))
    def test_raw_installs_do_not_credit_service(self):
        s=base();self.assertEqual(run(s,InstallGrant('D',grant(),(0,1))).status,'installed')
        self.assertEqual(metrics(s).served,0);self.assertEqual(len(s.view().deliveries),2)
    def test_usable_completion_exact_targets_and_waiting(self):
        s=base();run(s,InstallGrant('D',grant(),(0,1)))
        self.assertEqual(run(s,Transform('D','G',(0,1))).status,'served')
        self.assertEqual(s.now,T(6));self.assertEqual(metrics(s).waiting_ticks,6)
        receipt=s.view().queue.get('D').receipt
        self.assertEqual(receipt.targets,(R,));self.assertEqual(receipt.completed_at,T(6))
        self.assertEqual(run(s,Transform('D','G',(0,1))).status,'refused')
        s.advance_to(T(40));self.assertEqual(metrics(s).waiting_ticks,6)
    def test_partial_then_resume(self):
        s=base();run(s,InstallGrant('D',grant(),(0,1)))
        self.assertEqual(run(s,Transform('D','G',(0,))).status,'partial');self.assertEqual(metrics(s).served,0)
        self.assertEqual(run(s,Transform('D','G',(1,))).status,'served');self.assertEqual(len(s.view().deliveries),4)
    def test_missing_installed_share_refused_without_delivery(self):
        s=base();run(s,InstallGrant('D',grant(),(0,)));before=s.view().deliveries
        self.assertEqual(run(s,Transform('D','G',(1,))).status,'refused');self.assertEqual(before,s.view().deliveries)
    def test_outage_mid_raw_delivery_keeps_prefix(self):
        s=base((owner('down',3,False),));r=run(s,InstallGrant('D',grant(),(0,1)))
        self.assertEqual(r.status,'interrupted');self.assertEqual(r.delivered,(Delivery('G',0),))
        self.assertEqual(s.view().deliveries,(Delivery('G',0),));self.assertEqual(metrics(s).pending,1)
    def test_down_notice_same_tick_precedes_delivery(self):
        s=base((owner('down',2,False),));r=run(s,InstallGrant('D',grant(),(0,1)))
        self.assertEqual(r.status,'interrupted');self.assertEqual(r.delivered,());self.assertEqual(s.now,T(2))
    def test_actual_outage_blocks_even_if_notice_delayed(self):
        s=base((owner('down',2,False,8),));r=run(s,InstallGrant('D',grant(),(0,1)))
        self.assertEqual(r.status,'interrupted');self.assertEqual(r.delivered,())
        self.assertTrue(project(s.view().observation).online('O'))
        s.advance_to(T(8));self.assertFalse(project(s.view().observation).online('O'))
    def test_old_delayed_owner_report_cannot_overwrite_new_state(self):
        s=base((owner('down',1,False,8),owner('up-new',4,True)))
        s.advance_to(T(8));self.assertTrue(project(s.view().observation).online('O'))
    def test_existing_grant_transforms_while_owner_offline(self):
        s=base((owner('down',4,False),));run(s,InstallGrant('D',grant(),(0,1)))
        self.assertEqual(run(s,Transform('D','G',(0,1))).status,'served')
        self.assertFalse(project(s.view().observation).online('O'))
    def test_grant_token_exact_offline_effects(self):
        g=grant();token=GrantToken('gt',g,W(T(0),T(30)),(0,));s=base(tokens=(token,),online=False)
        r=run(s,InstallGrant('D',g,(0,1)));self.assertEqual(r.status,'interrupted')
        self.assertEqual(r.delivered,(Delivery('G',0),));s=base(tokens=(token,),online=False)
        self.assertEqual(run(s,InstallGrant('D',replace(g,recipient='other'),())).status,'refused')
    def test_grant_token_expiry_at_delivery(self):
        g=grant();token=GrantToken('gt',g,W(T(0),T(2)),(0,1));s=base(tokens=(token,),online=False)
        self.assertEqual(run(s,InstallGrant('D',g,(0,1))).status,'interrupted');self.assertEqual(s.view().deliveries,())
    def test_activation_token_does_not_grant(self):
        ns=ScopeNotice('O',Scope('g',1),'key1',1);token=ActivationToken('at',ns,W(T(0),T(30)))
        s=base(tokens=(token,),online=False)
        self.assertEqual(run(s,ActivateScope(ns)).status,'activated')
        self.assertEqual(run(s,InstallGrant('D',grant(),(0,))).status,'refused')
    def test_grant_token_does_not_activate(self):
        g=grant();s=base(tokens=(GrantToken('gt',g,W(T(0),T(30)),(0,)),),online=False)
        self.assertEqual(run(s,ActivateScope(ScopeNotice('O',Scope('g',1),'key1',1))).status,'refused')
    def test_outage_between_rotation_and_new_grant(self):
        s=base((owner('down',2,False),))
        self.assertEqual(run(s,ActivateScope(ScopeNotice('O',Scope('g',1),'key1',1))).status,'activated')
        r=run(s,InstallGrant('D',grant(),(0,)));self.assertEqual(r.status,'interrupted');self.assertEqual(r.delivered,())
        self.assertEqual(s.view().managed_scopes[0].scope,Scope('g',1))
    def test_original_scope_not_rebound_by_rotation(self):
        s=base();run(s,ActivateScope(ScopeNotice('O',Scope('g',1),'key1',1)))
        self.assertEqual(run(s,InstallGrant('D',grant(scope=Scope('g',1)),(0,1))).status,'refused')
        self.assertEqual(project(s.view().observation,s.view().managed_scopes).record(R).scope,S)
    def test_future_production_binds_new_active_scope(self):
        s=base((RecordProduction('r1','O',Record('g',1),T(2),T(4)),))
        run(s,ActivateScope(ScopeNotice('O',Scope('g',1),'key1',1)));s.advance_to(T(3))
        self.assertIsNone(project(s.view().observation,s.view().managed_scopes).record(Record('g',1)))
        s.advance_to(T(4));self.assertEqual(project(s.view().observation,s.view().managed_scopes).record(Record('g',1)).scope,Scope('g',1))
    def test_intervening_production_invalidates_stale_activation_start(self):
        s=base((RecordProduction('r1','O',Record('g',1),T(1),T(5)),))
        self.assertEqual(run(s,ActivateScope(ScopeNotice('O',Scope('g',1),'key1',1))).status,'interrupted')
        self.assertEqual(s.view().managed_scopes,())
    def test_defer_processes_all_intervening_reports(self):
        d2=demand(deadline=10,demand_id='E',release=2)
        s=base((owner('down',1,False),owner('up2',4,True),E('arrival2',T(2),T(2),DemandArrival(d2))))
        original=s.view().queue.get('D').demand;self.assertEqual(run(s,Defer('D',T(5))).status,'deferred')
        self.assertEqual(s.view().queue.get('D').demand,original);self.assertEqual(s.view().queue.get('E').demand,d2)
        self.assertEqual(s.view().observation.version.value,7);self.assertEqual(metrics(s).waiting_ticks,8)
    def test_defer_crosses_deadline_and_keeps_expired(self):
        s=base(d=demand(deadline=3));run(s,Defer('D',T(7)))
        self.assertEqual(s.view().queue.get('D').status,DemandStatus.EXPIRED)
        self.assertEqual(metrics(s).waiting_ticks,3);self.assertEqual(metrics(s).terminal_failures,1)
        self.assertEqual(run(s,InstallGrant('D',grant(),())).status,'refused')
    def test_deadline_exact_completion_retains_cfrags_without_credit(self):
        s=base(d=demand(deadline=6));run(s,InstallGrant('D',grant(),(0,1)));r=run(s,Transform('D','G',(0,1)))
        self.assertEqual(r.status,'interrupted');self.assertEqual(len(r.delivered),2)
        self.assertEqual(metrics(s).served,0);self.assertEqual(metrics(s).expired,1);self.assertEqual(len(s.view().deliveries),4)
    def test_grant_expiry_mid_transform(self):
        s=base();run(s,InstallGrant('D',grant(valid_to=5),(0,1)));r=run(s,Transform('D','G',(0,1)))
        self.assertEqual(r.status,'interrupted');self.assertEqual(r.delivered,(Delivery('G',0,R),));self.assertEqual(metrics(s).served,0)
    def test_stale_time_and_revision_deliver_nothing(self):
        s=base();old=s.view();s.advance_to(T(1))
        self.assertEqual(s.execute(InstallGrant('D',grant(),(0,)),old).status,'refused');self.assertEqual(s.view().deliveries,())
        old=s.view();run(s,InstallGrant('D',grant(),()))
        self.assertEqual(s.execute(Transform('D','G',(0,)),old).status,'refused')
    def test_context_bound_to_history_not_just_time_sequence(self):
        a=base();b=base(d=demand(recipient='other'));self.assertEqual(a.now,b.now)
        self.assertEqual(a.view().observation.version,b.view().observation.version)
        self.assertEqual(a.execute(InstallGrant('D',grant(),(0,)),b.view()).status,'refused');self.assertEqual(a.view().deliveries,())
    def test_backend_wrong_binding_never_serves(self):
        class Broken(ModelBackend):
            def open(self,d,g,ds):return UsableResult(d.demand_id,d.owner,'wrong',d.targets)
        s=base(backend=Broken());run(s,InstallGrant('D',grant(),(0,1)))
        self.assertEqual(run(s,Transform('D','G',(0,1))).status,'partial')
        self.assertEqual(metrics(s).served,0);self.assertEqual(len(s.view().deliveries),4)
    def test_coordinate_budget_denies_scope_key_threshold(self):
        s=base(budget=Budget(0,0,0));r=run(s,InstallGrant('D',grant(),(0,1)))
        self.assertEqual(r.status,'interrupted');self.assertEqual(r.delivered,(Delivery('G',0),))
        self.assertEqual(len(s.view().deliveries),1)
    def test_external_production_breach_is_not_erased(self):
        s=base((RecordProduction('collateral','O',Record('g',1),T(4),T(8)),),budget=Budget(0,0,1))
        run(s,InstallGrant('D',grant(),(0,1)));s.advance_to(T(4))
        actual=max(s.report()['actual_exposure'],key=lambda m:m.disclosed_weight)
        self.assertEqual(actual.disclosed_weight,1);self.assertEqual(actual.disclosed[0][1],T(4))
        self.assertEqual(max(m.disclosed_weight for m in s.view().observable_exposure),0)
        self.assertTrue(any(source=='external-production' for _,source,_ in s.report()['breaches']))
        s.advance_to(T(8));self.assertEqual(max(m.disclosed_weight for m in s.view().observable_exposure),1)
        self.assertEqual(run(s,ActivateScope(ScopeNotice('O',Scope('g',1),'key1',2))).status,'activated')
        self.assertEqual(max(m.disclosed_weight for m in s.report()['actual_exposure']),1)
        OBSERVATIONS['production_breach']={'actual_first_tick':4,'public_detection_tick':8,'retained_after_rotation':True}
    def test_later_authorization_does_not_erase_disclosure(self):
        d2=demand(demand_id='D2',targets=(Record('g',1),),release=4)
        s=base((RecordProduction('r1','O',Record('g',1),T(4),T(4)),E('a2',T(4),T(4),DemandArrival(d2))))
        run(s,InstallGrant('D',grant(),(0,1)));s.advance_to(T(4))
        self.assertEqual(max(m.endpoint_weight for m in s.report()['actual_exposure']),1)
        run(s,InstallGrant('D2',grant(grant_id='G2',rng=RecordRange('g',1,2)),()))
        self.assertEqual(max(m.endpoint_weight for m in s.report()['actual_exposure']),0)
        self.assertEqual(max(m.disclosed_weight for m in s.report()['actual_exposure']),1)
    def test_revocation_keeps_retained_and_prevents_delivery(self):
        s=base();run(s,InstallGrant('D',grant(),(0,1)));old=s.view().deliveries
        self.assertEqual(run(s,RevokeGrant('G')).status,'revoked');self.assertEqual(s.view().deliveries,old)
        self.assertEqual(run(s,Transform('D','G',(0,1))).status,'refused')
        self.assertEqual(max(len(m.active_scopes) for m in s.report()['actual_exposure']),1)
    def test_recipient_subsets_and_index_union(self):
        f=(Reach('all',frozenset({'p0'}),frozenset({'R','other'})),);s=base(family=f)
        run(s,InstallGrant('D',grant(),(0,1)));run(s,Transform('D','G',(0,)))
        self.assertEqual(max(len(m.active_scopes) for m in s.report()['actual_exposure']),0)
        self.assertEqual(len(family_cases(f)),4)
        s.advance_to(T(5));self.assertEqual(max(m.endpoint_weight for m in s.report()['actual_exposure']),0)
    def test_future_trace_not_in_view_or_initial_decision(self):
        a=base();b=base((owner('future-down',10,False),RecordProduction('r1','O',Record('g',1),T(12),T(14))))
        self.assertEqual(a.view(),b.view())
        for action in (InstallGrant('D',grant(),(0,1)),Transform('D','G',(0,1))):
            self.assertEqual(run(a,action),run(b,action));self.assertEqual(a.view(),b.view())
    def test_simultaneous_input_permutations_identical(self):
        d=demand();trace=(owner('up',0,True),E('s',T(0),T(0),SEED),RecordProduction('r','O',R,T(0),T(0)),E('a',T(0),T(0),DemandArrival(d)))
        views=[ServiceSimulator(order,FAMILY,LIMIT).view() for order in itertools.permutations(trace)]
        self.assertTrue(all(v==views[0] for v in views));OBSERVATIONS['initial_event_permutations']=24
    def test_arrival_report_after_deadline_is_expired(self):
        d=demand(deadline=2,demand_id='late',release=1);s=base((E('late-a',T(1),T(4),DemandArrival(d)),))
        s.advance_to(T(4));self.assertEqual(s.view().queue.get('late').status,DemandStatus.EXPIRED)
        self.assertEqual(s.view().queue.get('late').ended_at,T(2))
    def test_horizon_censoring_no_silent_rejection(self):
        s=base();s.advance_to(T(5));self.assertEqual(metrics(s).pending,1);self.assertEqual(metrics(s).terminal_failures,0)
        self.assertIn('censored',s.report()['horizon']);self.assertEqual(run(s,Reject('D')).status,'rejected')
        self.assertEqual(metrics(s).terminal_failures,1)
    def test_production_before_same_tick_revocation_keeps_authorization(self):
        s=base((RecordProduction('r1','O',Record('g',1),T(4),T(8)),))
        run(s,InstallGrant('D',grant(rng=RecordRange('g',0,None)),(0,1)))
        self.assertEqual(run(s,RevokeGrant('G')).status,'revoked')
        self.assertEqual(max(m.disclosed_weight for m in s.report()['actual_exposure']),0)
        s.advance_to(T(8))
        self.assertEqual(max(m.disclosed_weight for m in s.view().observable_exposure),0)
    def test_production_exact_window_expiry_is_not_authorized(self):
        s=base((RecordProduction('r1','O',Record('g',1),T(4),T(8)),))
        run(s,InstallGrant('D',grant(valid_to=4,rng=RecordRange('g',0,None)),(0,1)))
        s.advance_to(T(4));self.assertEqual(max(m.disclosed_weight for m in s.report()['actual_exposure']),1)
        s.advance_to(T(8));self.assertEqual(max(m.disclosed_weight for m in s.view().observable_exposure),1)
    def test_backend_exception_retains_effects(self):
        class Broken(ModelBackend):
            def open(self,d,g,ds):raise RuntimeError('untrusted backend details')
        s=base(backend=Broken());run(s,InstallGrant('D',grant(),(0,1)))
        result=run(s,Transform('D','G',(0,1)))
        self.assertEqual(result.status,'partial');self.assertNotIn('untrusted',result.reason)
        self.assertEqual(len(s.view().deliveries),4);self.assertEqual(metrics(s).served,0)
    def test_conflicting_environment_facts_rejected_upfront(self):
        with self.assertRaises(ValueError):base((owner('conflict',0,False,5),))
        with self.assertRaises(ValueError):base((RecordProduction('same-record','O',R,T(2),T(2)),))
    def test_no_delivery_before_future_target_is_observable(self):
        r=Record('g',1);d=demand(targets=(r,))
        s=base((RecordProduction('later','O',r,T(1),T(4)),),d=d)
        g=grant(rng=RecordRange('g',1,2))
        self.assertEqual(run(s,InstallGrant('D',g,(0,1))).status,'refused')
        s.advance_to(T(3));self.assertEqual(run(s,InstallGrant('D',g,(0,1))).status,'refused')
        s.advance_to(T(4));self.assertEqual(run(s,InstallGrant('D',g,(0,1))).status,'installed')
    def test_full_recipient_reach_cannot_replace_subset_checks(self):
        r1=Record('g',1);g1=grant();g2=grant(grant_id='G2',recipient='other',rng=RecordRange('g',1,2))
        state=CapabilityState((SEED,),((RecordNotice(R,S),T(0)),
                              (RecordNotice(r1,S),T(0))),
                              (IssuedGrant(g1,T(0)),IssuedGrant(g2,T(0))), (Delivery('G',0),Delivery('G',1)))
        f=(Reach('both',frozenset({'p0','p1'}),frozenset({'R','other'})),)
        out=assess(state,T(0),family_cases(f))
        full=next(m for m in out if "('R', 'other')" in m.label)
        self.assertEqual(full.endpoint_weight,0);self.assertEqual(max(m.endpoint_weight for m in out),1)
    def test_finite_mixed_capability_reference(self):
        from delegation_model.timed_log import RecordNotice
        r1=Record('g',1);count=0
        for threshold,rawmask,cfragmask,has_recipient in itertools.product((1,2,3),range(8),range(8),(False,True)):
            g=grant(threshold=threshold)
            # All proxy shares are installed; the coalition reaches only rawmask proxies.
            raw=tuple(Delivery('G',i) for i in range(3))
            cfs=tuple(Delivery('G',i,R) for i in range(3) if cfragmask & (1<<i))
            st=CapabilityState((SEED,),((RecordNotice(R,S),T(0)),(RecordNotice(r1,S),T(0))),
                               (IssuedGrant(g,T(0)),),raw+cfs)
            proxies=frozenset('p'+str(i) for i in range(3) if rawmask & (1<<i))
            exposed,opened=openability(st,frozenset({'R'}) if has_recipient else frozenset(),proxies)
            # Separate bit-count arithmetic does not call closure or family helpers.
            scope_expected=has_recipient and rawmask.bit_count()>=threshold
            rec_expected=set()
            if scope_expected:rec_expected={R,r1}
            elif has_recipient and (rawmask|cfragmask).bit_count()>=threshold:rec_expected={R}
            self.assertEqual(exposed,{S} if scope_expected else set());self.assertEqual(opened,rec_expected);count+=1
        OBSERVATIONS['separate_capability_reference']={'cases':count}
    def test_small_positive_weight_cannot_round_away_at_gate(self):
        s=base((RecordProduction('r1','O',Record('g',1),T(0),T(0),1.0),
                RecordProduction('r2','O',Record('g',2),T(0),T(0),2**-54)),budget=Budget(1,1,5))
        result=run(s,InstallGrant('D',grant(),(0,1)))
        self.assertEqual(result.status,'interrupted');self.assertEqual(result.delivered,(Delivery('G',0),))
    def test_finite_deferral_reference(self):
        count=0
        for deadline in (3,5):
            for steps in itertools.product((1,2,4),repeat=3):
                extra=demand(deadline=7,demand_id='E',release=2)
                s=base((E('extra',T(2),T(2),DemandArrival(extra)),),d=demand(deadline=deadline));now=0
                for step in steps:
                    now+=step
                    if s.view().queue.get('D').status==DemandStatus.PENDING:run(s,Defer('D',T(now)))
                    else:s.advance_to(T(now))
                    m=metrics(s);expected_wait=min(now,deadline)+(min(now,7)-2 if now>=2 else 0)
                    self.assertEqual(m.waiting_ticks,expected_wait)
                    self.assertEqual(m.pending,int(now<deadline)+int(2<=now<7))
                    self.assertEqual(m.expired,int(now>=deadline)+int(now>=7));count+=1
        OBSERVATIONS['separate_deferral_reference']={'tapes':54,'checkpoints':count}
if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(TimedServiceTests))
    out=Path(__file__).resolve().parents[2]/'results/manifests/p3b_timed_service.json';out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({'batch':'P3B','tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
        'observations':OBSERVATIONS,'scope':'Abstract service integration; no timed crypto backend/performance/security proof.'},indent=2)+'\n')
    sys.exit(not result.wasSuccessful())
