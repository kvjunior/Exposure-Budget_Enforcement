"""Single-threaded causal MODEL service, with no legacy timestamp conversion.

The default backend checks abstract cfrag usability, not encrypted bytes. Actual
owner state and production schedule are environment-only; policies receive PolicyView.
See docs/timed_authorization_contract.md for assumptions and observation limits.
"""
from dataclasses import dataclass, replace
from delegation_model.types import Record, Scope
from delegation_model.service_clock import ServiceTime, LogSequence, require_time
from delegation_model.demand_queue import (DemandQueue, DemandStatus, CompletionReceipt,
    CompletionKind, validate_id, validate_record)
from delegation_model.timed_log import (TimedLog, PublicEvent, PublicObservation, OwnerNotice,
    ScopeNotice, RecordNotice, DemandArrival)
from delegation_model.timed_authorization import (TimedGrant, GrantToken, ActivationToken,
    project, validate_scopes, indices, grant_authority, grant_token_covers,
    activation_authority, activation_token_covers, covers_demand)
from delegation_model.timed_capabilities import (Reach, Budget, IssuedGrant, Delivery,
    CapabilityState, family_cases, assess)


def duration(value):
    if type(value) is not int or value < 1:
        raise ValueError('action duration must be a positive integer number of service ticks')


@dataclass(frozen=True)
class RecordProduction:
    event_id: str
    owner: str
    record: Record
    occurred_at: ServiceTime
    available_at: ServiceTime
    weight: float = 1.0

    def __post_init__(self):
        validate_id(self.event_id, 'event ID')
        validate_id(self.owner, 'owner')
        validate_record(self.record)
        require_time(self.occurred_at)
        require_time(self.available_at)
        if self.available_at < self.occurred_at:
            raise ValueError('production report cannot arrive before production')
        RecordNotice(self.record, Scope(self.record.stream, 0), self.weight)


@dataclass(frozen=True)
class InstallGrant:
    demand_id: str
    grant: TimedGrant
    raw_indices: tuple[int, ...]
    metadata_ticks: int = 1
    step_ticks: int = 1

    def __post_init__(self):
        validate_id(self.demand_id, 'demand ID')
        if type(self.grant) is not TimedGrant:
            raise TypeError('TimedGrant required')
        indices(self.raw_indices, len(self.grant.proxies))
        duration(self.metadata_ticks)
        duration(self.step_ticks)


@dataclass(frozen=True)
class Transform:
    demand_id: str
    grant_id: str
    share_indices: tuple[int, ...]
    step_ticks: int = 1
    open_ticks: int = 1

    def __post_init__(self):
        validate_id(self.demand_id, 'demand ID')
        validate_id(self.grant_id, 'grant ID')
        # Share-count dependent bounds are checked against the actual issued grant.
        indices(self.share_indices)
        if not self.share_indices:
            raise ValueError('at least one transformation index required')
        duration(self.step_ticks)
        duration(self.open_ticks)


@dataclass(frozen=True)
class ActivateScope:
    activation: ScopeNotice
    ticks: int = 1

    def __post_init__(self):
        if type(self.activation) is not ScopeNotice:
            raise TypeError('ScopeNotice required')
        duration(self.ticks)


@dataclass(frozen=True)
class RevokeGrant:
    grant_id: str
    ticks: int = 1

    def __post_init__(self):
        validate_id(self.grant_id, 'grant ID')
        duration(self.ticks)


@dataclass(frozen=True)
class Defer:
    demand_id: str
    until: ServiceTime

    def __post_init__(self):
        validate_id(self.demand_id, 'demand ID')
        require_time(self.until)


@dataclass(frozen=True)
class Reject:
    demand_id: str

    def __post_init__(self):
        validate_id(self.demand_id, 'demand ID')


@dataclass(frozen=True)
class UsableResult:
    demand_id: str
    owner: str
    recipient: str
    targets: tuple[Record, ...]


class ModelBackend:
    """Trusted deterministic adapter for model experiments ONLY. No ciphertexts here."""
    name = 'abstract-cfrag-usability-model'

    def open(self, demand, grant, deliveries):
        if all(len({d.index for d in deliveries if d.grant_id == grant.grant_id
                    and d.record == r}) >= grant.threshold for r in demand.targets):
            return UsableResult(demand.demand_id, demand.owner, demand.recipient, demand.targets)
        return None


@dataclass(frozen=True)
class PolicyView:
    observation: PublicObservation
    queue: DemandQueue
    managed_scopes: tuple[ScopeNotice, ...]
    grants: tuple[IssuedGrant, ...]
    deliveries: tuple[Delivery, ...]
    tokens: tuple[GrantToken | ActivationToken, ...]
    family: tuple[Reach, ...]
    budget: Budget
    observable_exposure: tuple
    revision: int


@dataclass(frozen=True)
class ActionResult:
    status: str
    delivered: tuple[Delivery, ...] = ()
    reason: str = ''


class ServiceSimulator:
    """Environment-owned runner. Do not pass this object or report() to an online policy."""
    def __init__(self, trace, family, budget, tokens=(), backend=None,
                 production_fencing=False, fence_rejects_when_blocked=True,
                 admission_enforcement=True):
        if type(trace) is not tuple or any(type(e) not in (PublicEvent, RecordProduction) for e in trace):
            raise TypeError('immutable typed environment trace required')
        if any(type(e) is PublicEvent and type(e.payload) is RecordNotice for e in trace):
            raise ValueError('use RecordProduction: original scope is bound at actual production')
        if len({e.event_id for e in trace}) != len(trace):
            raise ValueError('duplicate environment event ID')
        facts = set()
        for e in trace:
            if type(e) is RecordProduction:
                fact = ('record', e.record)
            elif type(e.payload) is OwnerNotice:
                fact = ('owner', e.payload.owner, e.occurred_at)
            elif type(e.payload) is ScopeNotice:
                fact = ('scope', e.payload.scope)
            else:
                fact = ('demand', e.payload.demand.demand_id)
            if fact in facts:
                raise ValueError('duplicate/conflicting environment fact')
            facts.add(fact)
        if type(budget) is not Budget:
            raise TypeError('Budget required')
        if type(tokens) is not tuple or any(type(t) not in (GrantToken, ActivationToken) for t in tokens):
            raise TypeError('immutable typed provisioned tokens required')
        if len({t.token_id for t in tokens}) != len(tokens):
            raise ValueError('duplicate token ID')
        self._cases = family_cases(family)
        self._family, self._budget, self._tokens = family, budget, tokens
        self._backend = ModelBackend() if backend is None else backend
        self._trace = tuple(sorted(trace, key=lambda e: (e.occurred_at, e.event_id)))
        self._cursor = 0
        self._pending_reports = []
        self._owner_truth = {}
        self._truth_scopes = ()
        self._truth_records = ()
        self._managed = ()
        self._grants, self._deliveries = (), ()
        self._log, self._queue = TimedLog(), DemandQueue()
        self._revision = 0
        self._public_metrics, self._actual_metrics = (), ()
        self._breaches, self._outcomes = [], []
        # P3F: real production fencing in the execution path. When enabled, a record that would bind
        # to a scope ACTUALLY reconstructible by the declared family is bound to a freshly rotated
        # scope (if owner authority permits) or DROPPED. The rotation's truth scope + public report
        # are materialized. This genuinely invokes the production safety mechanism.
        self._production_fencing = production_fencing
        self._fence_rejects_when_blocked = fence_rejects_when_blocked
        self._fence_log, self._fence_rotations, self._fence_drops = [], 0, 0
        self._admission_enforcement = admission_enforcement
        self._drain_tick()

    @property
    def now(self):
        return self._log.clock.now

    def _catalogue(self):
        return project(self._log.observe(), self._managed)

    def _state(self, actual=False, grants=None, deliveries=None, scopes=None):
        cat = self._catalogue()
        return CapabilityState((self._truth_scopes if actual else cat.scopes) if scopes is None else scopes,
                               self._truth_records if actual else cat.records,
                               self._grants if grants is None else grants,
                               self._deliveries if deliveries is None else deliveries)

    def _measure(self, source):
        self._public_metrics = assess(self._state(), self.now, self._cases, self._public_metrics)
        self._actual_metrics = assess(self._state(True), self.now, self._cases, self._actual_metrics)
        for m in self._actual_metrics:
            if not m.within(self._budget):
                item = (self.now, source, m)
                if not self._breaches or self._breaches[-1] != item:
                    self._breaches.append(item)

    def _drain_tick(self):
        # Deadline expiry precedes all inputs and service completion at this tick.
        self._queue = self._queue.advance_to(self.now)
        occurred = []
        while self._cursor < len(self._trace) and self._trace[self._cursor].occurred_at == self.now:
            occurred.append(self._trace[self._cursor]); self._cursor += 1
        def phase(e):
            if type(e) is RecordProduction:
                return 2, e.record.stream, e.record.seq
            p = e.payload
            return ((0, p.owner, 0) if type(p) is OwnerNotice else
                    (1, p.scope.stream, p.scope.epoch) if type(p) is ScopeNotice else
                    (3, p.demand.demand_id, 0))
        for e in sorted(occurred, key=phase):
            if type(e) is RecordProduction:
                old = [n.record.seq for n, _ in self._truth_records if n.record.stream == e.record.stream]
                if old and e.record.seq <= max(old):
                    raise ValueError('source production sequences must strictly increase')
                possible = [s for s in self._truth_scopes if s.scope.stream == e.record.stream
                            and s.start_seq <= e.record.seq]
                if not possible:
                    raise ValueError('production has no authentic original scope')
                scope = max(possible, key=lambda s: s.start_seq)
                if scope.owner != e.owner:
                    raise ValueError('production owner does not own stream')
                # P3F PRODUCTION FENCE: if enabled and the target scope is actually reconstructible,
                # rotate to a fresh scope (owner authority) or drop the production.
                if self._production_fencing and self._scope_reconstructible_actual(scope.scope):
                    fresh = self._fence_rotate_or_drop(e, scope)
                    if fresh is None:
                        self._fence_drops += 1
                        self._fence_log.append((self.now, 'drop', e.record.stream,
                                                'reconstructible scope, no owner authority to rotate'))
                        continue                         # production REFUSED; record not bound
                    scope = fresh
                notice = RecordNotice(e.record, scope.scope, e.weight)
                self._truth_records += ((notice, self.now),)
                self._pending_reports.append(PublicEvent(e.event_id, e.occurred_at, e.available_at, notice))
                self._measure('external-production')
            else:
                if type(e.payload) is OwnerNotice:
                    self._owner_truth[e.payload.owner] = e.payload.online
                elif type(e.payload) is ScopeNotice:
                    candidate = self._truth_scopes + (e.payload,)
                    validate_scopes(candidate)
                    self._truth_scopes = tuple(sorted(candidate, key=lambda s: s.scope))
                    self._measure('external-scope')
                self._pending_reports.append(e)
        ready = tuple(e for e in self._pending_reports if e.available_at <= self.now)
        if ready:
            self._log = self._log.append_batch(ready)
            self._pending_reports = [e for e in self._pending_reports if e.available_at > self.now]
            for entry in self._log.entries[-len(ready):]:
                if type(entry.event.payload) is DemandArrival:
                    self._queue = self._queue.offer(entry.event.payload.demand)
        self._measure('public-observation')

    def _scope_reconstructible_actual(self, scope):
        """True iff the ACTUAL state has the given scope reconstructible by any declared case."""
        from delegation_manager.production_fence import scope_reconstructible
        return scope_reconstructible(self._state(True), self._family, scope)

    def _fence_rotate_or_drop(self, production, old_scope):
        """Fence action for an at-risk production. If the owner is online (or a valid activation
        preauth exists), materialize a FRESH truth scope (epoch+1) and its public report, bind the
        record there, and return the fresh ScopeNotice. Otherwise return None (drop). Records the
        rotation cost in the fence log."""
        from delegation_model.timed_authorization import activation_token_covers
        stream = production.record.stream
        owner = old_scope.owner
        new_epoch = max(s.scope.epoch for s in self._truth_scopes if s.scope.stream == stream) + 1
        fresh = ScopeNotice(owner, Scope(stream, new_epoch), f'{stream}.fence.e{new_epoch}',
                            production.record.seq)
        owner_online = self._owner_truth.get(owner, False)
        preauth_ok = activation_token_covers(fresh, self.now, self._tokens)
        if not (owner_online or preauth_ok):
            return None
        # materialize the fresh scope in truth and (as a public report) in the pending reports.
        candidate = self._truth_scopes + (fresh,)
        try:
            validate_scopes(candidate)
        except ValueError:
            return None
        self._truth_scopes = tuple(sorted(candidate, key=lambda s: s.scope))
        self._managed += (fresh,)
        self._pending_reports.append(PublicEvent(f'fence-rot-{stream}-{production.record.seq}-{self._revision}-{new_epoch}',
                                                 production.occurred_at, production.occurred_at, fresh))
        self._fence_rotations += 1
        self._fence_log.append((self.now, 'rotate', stream,
                                f'rotated to epoch {new_epoch} before binding {production.record.seq}'))
        self._measure('fence-rotation')
        return fresh

    def advance_to(self, until):
        require_time(until)
        if until < self.now:
            raise ValueError('cannot move service time backwards')
        while self.now < until:
            points = [until]
            if self._cursor < len(self._trace):
                points.append(self._trace[self._cursor].occurred_at)
            points.extend(e.available_at for e in self._pending_reports)
            points.extend(e.demand.deadline for e in self._queue.entries if e.status == DemandStatus.PENDING)
            at = min(p for p in points if p > self.now)
            self._log = self._log.advance_to(at)
            self._drain_tick()
        return self.view()

    def view(self):
        return PolicyView(self._log.observe(), self._queue, self._managed, self._grants,
                          self._deliveries, self._tokens, self._family, self._budget,
                          self._public_metrics, self._revision)

    def _pending(self, demand_id):
        try:
            entry = self._queue.get(demand_id)
        except KeyError:
            return None
        return entry.demand if entry.status == DemandStatus.PENDING else None

    def _issued(self, grant_id):
        return next((g for g in self._grants if g.grant.grant_id == grant_id), None)

    def _authority(self, grant, index=None):
        return (grant_authority(self._catalogue(), grant, self.now, self._tokens, index)
                and (self._owner_truth.get(grant.owner, False)
                     or grant_token_covers(grant, self.now, self._tokens, index)))

    def _gate(self, grants=None, deliveries=None):
        # PUBLIC gate: what the online controller can verify from the public view. May under-report
        # when production reports are delayed (that is the observability gap).
        candidate = assess(self._state(grants=grants, deliveries=deliveries), self.now,
                           self._cases, self._public_metrics)
        return all(m.within(self._budget) for m in candidate)

    def _enforce(self, grants=None, deliveries=None, scopes=None):
        """ENFORCEMENT boundary (P3E, Task 1): the authority co-located with production truth checks
        the whole-run IRREVERSIBLE disclosure budget on the ACTUAL state before committing a
        capability-changing operation. This closes the retroactive-disclosure hole (CE-RETRO): a
        grant delivery that would collaterally open older unauthorized records -- even ones not yet
        publicly reported -- is refused here, though the public gate cannot see them. We enforce the
        monotone disclosed_weight dimension (the whole-run bound); the active-scope and endpoint
        dimensions remain the public gate's responsibility, preserving the public/enforcement
        distinction the controller observes vs. what the boundary can verify."""
        candidate = assess(self._state(True, grants=grants, deliveries=deliveries, scopes=scopes),
                           self.now, self._cases, self._actual_metrics)
        return all(float(m.disclosed_weight) <= float(self._budget.disclosed_weight)
                   for m in candidate)

    def _commit(self, source, grants=None, deliveries=None):
        if grants is not None:
            self._grants = grants
        if deliveries is not None:
            self._deliveries = deliveries
        self._revision += 1
        self._measure(source)

    def execute(self, action, expected):
        if type(expected) is not PolicyView or expected != self.view():
            return ActionResult('refused', reason='stale or mismatched public context')
        if type(action) not in (InstallGrant, Transform, ActivateScope, RevokeGrant, Defer, Reject):
            raise TypeError('unknown action')
        before, before_grants = self._deliveries, self._grants
        result = self._execute(action)
        # Outcomes are public service feedback; evaluator breaches remain private.
        self._revision += 1
        added = tuple(d for d in self._deliveries if d not in before)
        if result.status == 'refused' and (added or self._grants != before_grants):
            result = replace(result, status='interrupted')
        self._outcomes.append((self.now, type(action).__name__, result.status, result.reason))
        return replace(result, delivered=added)

    def _execute(self, action):
        if type(action) is Defer:
            if self._pending(action.demand_id) is None or action.until <= self.now:
                return ActionResult('refused', reason='pending demand and later wake time required')
            self.advance_to(action.until)
            return ActionResult('deferred')
        if type(action) is Reject:
            if self._pending(action.demand_id) is None:
                return ActionResult('refused', reason='demand is not pending')
            self._queue = self._queue.reject(action.demand_id)
            return ActionResult('rejected')
        if type(action) is ActivateScope:
            return self._activate(action)
        if type(action) is RevokeGrant:
            old = self._issued(action.grant_id)
            if old is None or old.revoked_at is not None or not self._catalogue().online(old.grant.owner):
                return ActionResult('refused', reason='live owner authority required for revocation')
            self.advance_to(self.now.later_by(action.ticks))
            if not self._catalogue().online(old.grant.owner) or not self._owner_truth.get(old.grant.owner, False):
                return ActionResult('interrupted', reason='owner authority unavailable')
            grants = tuple(replace(g, revoked_at=self.now) if g == old else g for g in self._grants)
            self._commit('revoke', grants=grants)
            return ActionResult('revoked')
        if type(action) is InstallGrant:
            return self._install(action)
        return self._transform(action)

    def _activation_valid(self, activation):
        cat = self._catalogue()
        same = [s for s in cat.scopes if s.scope.stream == activation.scope.stream]
        produced = [n.record.seq for n, _ in cat.records if n.record.stream == activation.scope.stream]
        return (same and activation.owner == same[0].owner
                and activation.scope.epoch == max(s.scope.epoch for s in same)+1
                and activation.start_seq == max(produced, default=-1)+1
                and activation.start_seq > max(s.start_seq for s in same)
                and activation.key_id not in {s.key_id for s in cat.scopes}
                and activation_authority(cat, activation, self.now, self._tokens))

    def _activate(self, action):
        s = action.activation
        if not self._activation_valid(s):
            return ActionResult('refused', reason='invalid public activation/authority')
        self.advance_to(self.now.later_by(action.ticks))
        if not self._activation_valid(s):
            return ActionResult('interrupted', reason='activation context changed')
        truthseq = [n.record.seq for n, _ in self._truth_records if n.record.stream == s.scope.stream]
        if (s.start_seq != max(truthseq, default=-1)+1 or
                not (self._owner_truth.get(s.owner, False) or activation_token_covers(s, self.now, self._tokens))):
            return ActionResult('interrupted', reason='authoritative source/owner refused activation')
        candidate = self._truth_scopes + (s,)
        # Authoritative conflicts can arise from reports not yet visible.
        try:
            validate_scopes(candidate)
        except ValueError:
            return ActionResult('interrupted', reason='authoritative scope conflict')
        self._truth_scopes = tuple(sorted(candidate, key=lambda n: n.scope))
        self._managed += (s,)
        self._commit('activate')
        return ActionResult('activated')

    def _install(self, action):
        g = action.grant
        demand = self._pending(action.demand_id)
        old = self._issued(g.grant_id)
        if (demand is None or not covers_demand(self._catalogue(), g, demand, self.now)
                or not self._authority(g) or old is not None and (old.grant != g or not old.live(self.now))):
            return ActionResult('refused', reason='demand, grant or authority mismatch')
        if any(Delivery(g.grant_id, i) in self._deliveries for i in action.raw_indices):
            return ActionResult('refused', reason='raw fragment already installed')
        if old is None:
            self.advance_to(self.now.later_by(action.metadata_ticks))
            if (self._pending(action.demand_id) is None or not self._authority(g)
                    or not covers_demand(self._catalogue(), g, demand, self.now)):
                return ActionResult('interrupted', reason='metadata authority/window ended')
            grants = self._grants + (IssuedGrant(g, self.now),)
            if not self._gate(grants=grants):
                return ActionResult('refused', reason='observable exposure budget')
            if self._admission_enforcement and not self._enforce(grants=grants):
                return ActionResult('refused', reason='enforcement exposure budget (actual whole-run disclosure)')
            self._commit('grant-metadata', grants=grants)
        for i in action.raw_indices:
            self.advance_to(self.now.later_by(action.step_ticks))
            if (self._pending(action.demand_id) is None or not self._issued(g.grant_id).live(self.now)
                    or not self._authority(g, i) or not covers_demand(self._catalogue(), g, demand, self.now)):
                return ActionResult('interrupted', reason='raw-delivery authority/window ended')
            deliveries = self._deliveries + (Delivery(g.grant_id, i),)
            if not self._gate(deliveries=deliveries):
                return ActionResult('refused', reason='observable exposure budget')
            if self._admission_enforcement and not self._enforce(deliveries=deliveries):
                return ActionResult('refused', reason='enforcement exposure budget (actual whole-run disclosure)')
            self._commit('raw-delivery', deliveries=deliveries)
        return ActionResult('installed')

    def _transform(self, action):
        issued = self._issued(action.grant_id)
        demand = self._pending(action.demand_id)
        if issued is None or demand is None:
            return ActionResult('refused', reason='issued grant and pending demand required')
        g = issued.grant
        indices(action.share_indices, len(g.proxies))
        def valid():
            return (self._pending(action.demand_id) is not None and self._issued(g.grant_id).live(self.now)
                    and covers_demand(self._catalogue(), g, demand, self.now))
        if not valid() or any(Delivery(g.grant_id, i) not in self._deliveries for i in action.share_indices):
            return ActionResult('refused', reason='live grant/installed transformation shares required')
        for r in demand.targets:
            for i in action.share_indices:
                d = Delivery(g.grant_id, i, r)
                if d in self._deliveries:
                    continue
                self.advance_to(self.now.later_by(action.step_ticks))
                if not valid():
                    return ActionResult('interrupted', reason='transformation window ended')
                deliveries = self._deliveries + (d,)
                if not self._gate(deliveries=deliveries):
                    return ActionResult('refused', reason='observable exposure budget')
                if self._admission_enforcement and not self._enforce(deliveries=deliveries):
                    return ActionResult('refused', reason='enforcement exposure budget (actual whole-run disclosure)')
                self._commit('cfrag-delivery', deliveries=deliveries)
        enough = all(len({d.index for d in self._deliveries if d.grant_id == g.grant_id
                          and d.record == r}) >= g.threshold for r in demand.targets)
        if not enough:
            return ActionResult('partial', reason='fewer than threshold cfrags')
        self.advance_to(self.now.later_by(action.open_ticks))
        if not valid():
            return ActionResult('interrupted', reason='completion window ended; retained fragments remain')
        try:
            result = self._backend.open(demand, g, self._deliveries)
        except Exception:
            return ActionResult('partial', reason='backend failed; retained fragments remain')
        expected = UsableResult(demand.demand_id, demand.owner, demand.recipient, demand.targets)
        if type(result) is not UsableResult or result != expected:
            return ActionResult('partial', reason='backend did not attest exact usable service')
        receipt = CompletionReceipt('service-receipt-'+str(self._revision), demand.demand_id,
                                    demand.owner, demand.recipient, demand.targets, self.now, CompletionKind.USABLE)
        self._queue = self._queue.complete(demand.demand_id, receipt)
        self._commit('service-completion')
        return ActionResult('served')

    def report(self):
        """Evaluator-only result, including unobserved production. Never a policy input."""
        return {'backend': self._backend.name, 'now': self.now, 'queue': self._queue.metrics(),
                'exposure_interpretation': 'declared-family potential exposure over actual production; not observed corruption/decryption',
                'actual_exposure': self._actual_metrics, 'observable_exposure': self._public_metrics,
                'breaches': tuple(self._breaches), 'outcomes': tuple(self._outcomes),
                'truth_records': self._truth_records, 'deliveries': self._deliveries,
                'fence_log': tuple(self._fence_log), 'fence_rotations': self._fence_rotations,
                'fence_drops': self._fence_drops, 'production_fencing': self._production_fencing,
                'horizon': 'censored; pending demands remain pending'}
