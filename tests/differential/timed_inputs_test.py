"""P3A input contracts: time/order, demand identity, service and causal views."""
from dataclasses import FrozenInstanceError, asdict, replace
from itertools import permutations, product
from pathlib import Path
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from delegation_model.types import Record, Scope
from delegation_model.events import OwnerAvailability, CorruptProxy, DiscloseDataKey
from delegation_model.service_clock import ServiceTime as T, LogSequence as S, ServiceClock, TimeWindow
from delegation_model.demand_queue import (Demand, DemandState, DemandStatus, DemandQueue,
                                           CompletionReceipt, CompletionKind)
from delegation_model.timed_log import (OwnerNotice, ScopeNotice, RecordNotice, DemandArrival,
                                       PublicEvent, TimedEntry, TimedLog, PublicObservation)

R0, R1 = Record("g", 0), Record("g", 1)
SC0, SC1 = Scope("g", 0), Scope("g", 1)


def demand(did="D", release=0, deadline=6, targets=(R0,), recipient="R"):
    return Demand(did, "O", recipient, targets, T(release), T(deadline))


def receipt(d, at, kind=CompletionKind.USABLE, rid=None):
    return CompletionReceipt(rid or "receipt-" + d.demand_id, d.demand_id,
                             d.owner, d.recipient, d.targets, T(at), kind)


def event(eid, payload, at=0, available=None):
    return PublicEvent(eid, T(at), T(at if available is None else available), payload)


class TimedInputs(unittest.TestCase):
    observations = {}

    def test_time_and_sequence_are_different_runtime_coordinates(self):
        for cls in (T, S):
            for value in (True, 1.0, "1", -1):
                with self.subTest(cls=cls, value=value):
                    with self.assertRaises((ValueError, TypeError)):
                        cls(value)
        with self.assertRaises(TypeError):
            _ = T(1) < S(1)
        with self.assertRaises(TypeError):
            int(T(1))
        with self.assertRaises(TypeError):
            ServiceClock().advance_to(4)
        with self.assertRaises(TypeError):
            ServiceClock().advance_to(S(4))

    def test_idle_advance_and_simultaneous_appends_are_independent(self):
        original = ServiceClock()
        idle = original.advance_to(T(7))
        a, first = idle.record()
        b, second = a.record()
        self.assertEqual((first, second), (S(1), S(2)))
        self.assertEqual((idle.now, idle.last_sequence), (T(7), S(0)))
        self.assertEqual((b.now, b.last_sequence), (T(7), S(2)))
        self.assertEqual(original, ServiceClock())
        with self.assertRaises(ValueError):
            b.advance_to(T(6))

    def test_half_open_windows_and_deadline_boundary(self):
        window = TimeWindow(T(2), T(5))
        self.assertTrue(window.contains(T(2)))
        self.assertFalse(window.contains(T(5)))
        self.assertTrue(TimeWindow(T(0)).contains(T(10**8)))
        with self.assertRaises(ValueError):
            TimeWindow(T(5), T(5))

    def test_target_set_is_immutable_and_canonical(self):
        d = demand(targets=(R1, R0))
        self.assertEqual(d.targets, (R0, R1))
        with self.assertRaises(FrozenInstanceError):
            d.targets = (Record("g", 2),)
        with self.assertRaises(TypeError):
            demand(targets=[R0])
        with self.assertRaises(ValueError):
            demand(targets=(R0, R0))
        with self.assertRaises(ValueError):
            demand(targets=(Record("g", True),))
        with self.assertRaises(ValueError):
            demand(deadline=0)

    def test_future_offer_is_refused_and_late_offer_expires(self):
        q = DemandQueue()
        with self.assertRaises(ValueError):
            q.offer(demand(release=1))
        late = q.advance_to(T(10)).offer(demand(deadline=3))
        self.assertEqual(late.get("D").status, DemandStatus.EXPIRED)
        self.assertEqual(late.metrics().waiting_ticks, 3)
        self.assertEqual(late.metrics().terminal_failures, 1)

    def test_deferral_retains_identity_and_accumulates_waiting(self):
        d = demand()
        original = DemandQueue().offer(d)
        delayed = original.defer("D", T(3))
        self.assertEqual(delayed.get("D").status, DemandStatus.PENDING)
        self.assertIs(delayed.get("D").demand, d)
        self.assertEqual(delayed.metrics().waiting_ticks, 3)
        self.assertEqual(original.now, T(0))
        self.assertEqual(original.metrics().waiting_ticks, 0)

    def test_deferral_across_deadline_expires_without_erasing(self):
        q = DemandQueue().offer(demand(deadline=2)).defer("D", T(5))
        self.assertEqual(q.get("D").ended_at, T(2))
        self.assertEqual(q.metrics().waiting_ticks, 2)
        self.assertEqual((q.metrics().pending, q.metrics().terminal_failures), (0, 1))

    def test_metadata_and_partial_receipts_do_not_serve(self):
        d = demand()
        q = DemandQueue().offer(d).advance_to(T(1))
        for kind in (CompletionKind.METADATA, CompletionKind.PARTIAL):
            with self.assertRaises(ValueError):
                q.complete("D", receipt(d, 1, kind))
        self.assertEqual((q.metrics().pending, q.metrics().served), (1, 0))
        self.assertEqual(q.metrics().waiting_ticks, 1)

    def test_completion_binds_all_demand_fields_and_current_time(self):
        d = demand()
        q = DemandQueue().offer(d).advance_to(T(2))
        good = receipt(d, 2)
        for bad in (replace(good, demand_id="OTHER"), replace(good, owner="OTHER"),
                    replace(good, recipient="OTHER"), replace(good, targets=(R1,)),
                    replace(good, completed_at=T(1)), replace(good, completed_at=T(3))):
            with self.subTest(receipt=bad):
                with self.assertRaises(ValueError):
                    q.complete("D", bad)
        self.assertEqual(q.complete("D", good).metrics().served, 1)

    def test_completion_at_deadline_is_late(self):
        d = demand(deadline=3)
        q = DemandQueue().offer(d).advance_to(T(3))
        with self.assertRaises(ValueError):
            q.complete("D", receipt(d, 3))
        self.assertEqual(q.get("D").status, DemandStatus.EXPIRED)
        self.assertEqual(q.metrics().served, 0)

    def test_served_at_zero_does_not_accrue_later_waiting(self):
        d = demand()
        q = DemandQueue().offer(d).complete("D", receipt(d, 0)).advance_to(T(100))
        self.assertEqual((q.metrics().served, q.metrics().waiting_ticks), (1, 0))

    def test_terminal_outcomes_are_absorbing_and_credited_once(self):
        d = demand()
        q = DemandQueue().offer(d).complete("D", receipt(d, 0))
        for operation in (lambda: q.complete("D", receipt(d, 0)), lambda: q.reject("D"),
                          lambda: q.defer("D", T(1)), lambda: q.offer(d)):
            with self.assertRaises(ValueError):
                operation()
        self.assertEqual(q.advance_to(T(20)).metrics().served, 1)

    def test_receipt_id_cannot_be_recredited_to_another_demand(self):
        a, b = demand("A"), demand("B")
        q = DemandQueue().offer(a).offer(b).complete("A", receipt(a, 0, rid="ONE"))
        with self.assertRaises(ValueError):
            q.complete("B", receipt(b, 0, rid="ONE"))
        self.assertEqual((q.metrics().served, q.metrics().pending), (1, 1))

    def test_rejection_and_expiry_are_terminal_failures(self):
        a, b = demand("A", deadline=3), demand("B", deadline=4)
        q = DemandQueue().offer(a).offer(b).advance_to(T(1)).reject("A").advance_to(T(10))
        self.assertEqual(asdict(q.metrics()), dict(pending=0, served=0, rejected=1, expired=1, waiting_ticks=5))

    def test_constructor_rejects_inconsistent_or_future_queue_state(self):
        d = demand()
        with self.assertRaises(ValueError):
            DemandQueue(T(6), (DemandState(d, T(0)),))
        with self.assertRaises(ValueError):
            DemandQueue(T(0), (DemandState(d, T(1)),))
        with self.assertRaises(ValueError):
            DemandQueue(T(0), (DemandState(d, T(0)), DemandState(d, T(0))))

    def test_public_payload_boundary_excludes_legacy_and_ground_truth(self):
        for payload in (OwnerAvailability(0, "O", False), CorruptProxy(0, "p0", "C"),
                        DiscloseDataKey(0, R0, "C"), {"future_secret": "x"}):
            with self.subTest(payload=payload):
                with self.assertRaises(TypeError):
                    event("BAD", payload)

    def test_event_causality_and_arrival_release_are_validated(self):
        with self.assertRaises(ValueError):
            event("EARLY", OwnerNotice("O", True), at=3, available=2)
        with self.assertRaises(ValueError):
            event("WRONG-RELEASE", DemandArrival(demand()), at=1)
        with self.assertRaises(ValueError):
            RecordNotice(R0, Scope("other", 0))
        with self.assertRaises(ValueError):
            RecordNotice(R0, SC0, float("nan"))

    def test_future_append_failure_is_atomic(self):
        original = TimedLog()
        ready = event("READY", OwnerNotice("O", True))
        future = event("FUTURE", RecordNotice(R0, SC0), at=2)
        with self.assertRaises(ValueError):
            original.append_batch((ready, future))
        self.assertEqual(original.entries, ())
        self.assertEqual(original.clock, ServiceClock())

    def test_delayed_report_has_no_retroactive_visibility(self):
        e = event("DELAYED", RecordNotice(R0, SC0), at=1, available=3)
        log = TimedLog().advance_to(T(5)).append_batch((e,))
        self.assertEqual(log.observe(T(4)).entries, ())
        self.assertEqual(log.observe(T(5)).entries[0].event.occurred_at, T(1))
        self.assertEqual(log.observe(T(5)).version, S(1))

    def test_simultaneous_batch_order_is_deterministic(self):
        events = (event("OWNER", OwnerNotice("O", False)),
                  event("SCOPE", ScopeNotice("O", SC0, "k0", 0)),
                  event("RECORD", RecordNotice(R0, SC0)),
                  event("DEMAND", DemandArrival(demand())))
        for permutation in permutations(events):
            log = TimedLog().append_batch(permutation)
            self.assertEqual([e.event.event_id for e in log.entries], ["OWNER", "SCOPE", "RECORD", "DEMAND"])
            self.assertEqual([e.sequence.value for e in log.entries], [1, 2, 3, 4])
            self.assertEqual(log.clock.now, T(0))
        self.observations["simultaneous_batch_permutations"] = 24

    def test_record_ties_use_sequence_not_event_name(self):
        log = TimedLog().append_batch((event("A", RecordNotice(R1, SC0)),
                                       event("Z", RecordNotice(R0, SC0))))
        self.assertEqual([e.event.payload.record for e in log.entries], [R0, R1])

    def test_committed_history_cannot_be_reordered_by_later_same_tick_batch(self):
        log = TimedLog().append_batch((event("S", ScopeNotice("O", SC0, "k0", 0)),))
        with self.assertRaises(ValueError):
            log.append_batch((event("O", OwnerNotice("O", False)),))
        self.assertEqual(len(log.entries), 1)

    def test_duplicate_and_conflicting_facts_are_rejected(self):
        owner = event("O1", OwnerNotice("O", True))
        log = TimedLog().append_batch((owner,))
        for duplicate in (owner, event("O2", OwnerNotice("O", False))):
            with self.assertRaises(ValueError):
                log.append_batch((duplicate,))
        record_log = TimedLog().append_batch((event("R", RecordNotice(R0, SC0)),))
        with self.assertRaises(ValueError):
            record_log.advance_to(T(1)).append_batch((event("RETCON", RecordNotice(R0, SC1), at=1),))

    def test_future_extensions_do_not_change_past_observation_or_version(self):
        log = TimedLog().append_batch((event("KNOWN", DemandArrival(demand())),))
        past = log.observe()
        later = log
        for i in range(1, 21):
            later = later.advance_to(T(i)).append_batch((event(f"F{i}", OwnerNotice(f"O{i}", True), at=i),))
        self.assertEqual(later.observe(T(0)), past)
        self.assertEqual(later.observe(T(0)).version, S(1))
        self.assertEqual(later.clock.last_sequence, S(21))
        self.observations["prefix_noninterference"] = {"visible_version": 1, "extended_full_version": 21}

    def test_same_tick_snapshot_can_be_reconstructed_by_sequence(self):
        first = TimedLog().append_batch((event("O", OwnerNotice("O", True)),))
        snapshot = first.observe()
        extended = first.append_batch((event("R", RecordNotice(R0, SC0)),))
        self.assertEqual(extended.observe(T(0), through_sequence=snapshot.version), snapshot)
        self.assertEqual(extended.observe().version, S(2))
        with self.assertRaises(ValueError):
            extended.observe(T(1))
        with self.assertRaises(ValueError):
            extended.observe(through_sequence=S(3))

    def test_manual_observation_cannot_contain_future_or_holes(self):
        e = TimedEntry(S(1), T(3), event("O", OwnerNotice("O", True), at=3))
        with self.assertRaises(ValueError):
            PublicObservation(T(2), S(1), (e,))
        with self.assertRaises(ValueError):
            PublicObservation(T(3), S(2), (e,))
        with self.assertRaises(ValueError):
            TimedLog(ServiceClock(T(3), S(2)), (replace(e, sequence=S(2)),))

    def test_rollover_notice_does_not_change_pending_target(self):
        d = demand()
        q = DemandQueue().offer(d).defer("D", T(2))
        log = TimedLog().advance_to(T(2)).append_batch((event("ROLL", ScopeNotice("O", SC1, "k1", 1), at=2),))
        self.assertEqual(log.observe().entries[0].event.payload.scope, SC1)
        self.assertEqual(q.get("D").demand.targets, (R0,))
        with self.assertRaises(ValueError):
            q.complete("D", replace(receipt(d, 2), targets=(R1,)))
        self.assertEqual(q.complete("D", receipt(d, 2)).metrics().served, 1)

    def test_contract_worked_trace(self):
        d = demand()
        q = DemandQueue().offer(d)
        log = TimedLog().append_batch((event("ARRIVAL", DemandArrival(d)),))
        log = log.advance_to(T(1)).append_batch((event("DOWN", OwnerNotice("O", False), at=1),))
        q = q.defer("D", T(3))
        log = log.advance_to(T(3))
        ids3 = [e.event.event_id for e in log.observe().entries]
        self.assertEqual(ids3, ["ARRIVAL", "DOWN"])
        log = log.advance_to(T(4)).append_batch((event("PRODUCED", RecordNotice(R1, SC0), at=2, available=4),
                                               event("UP", OwnerNotice("O", True), at=4)))
        served = q.advance_to(T(4)).complete("D", receipt(d, 4))
        expired = q.advance_to(T(6))
        self.assertEqual(asdict(served.metrics()), dict(pending=0, served=1, rejected=0, expired=0, waiting_ticks=4))
        self.assertEqual(expired.metrics().terminal_failures, 1)
        self.assertEqual(expired.metrics().waiting_ticks, 6)
        self.observations["worked_trace"] = {"view_at_3": ids3,
            "view_at_4": [e.event.event_id for e in log.observe().entries],
            "served_branch": asdict(served.metrics()), "no_completion_branch": asdict(expired.metrics())}

    def test_queue_against_independent_tiny_reference(self):
        # An independent dictionary transition model, not a second call to the
        # production queue. All release times are 0; A expires at 2, B at 3.
        actions = ("time1", "time2", "time3", "deferA2", "completeA", "rejectB")
        da, db = demand("A", deadline=2), demand("B", deadline=3)
        transitions = 0
        for tape in product(actions, repeat=4):
            q = DemandQueue().offer(da).offer(db)
            now = 0
            statuses = {"A": "pending", "B": "pending"}
            ends = {"A": None, "B": None}
            deadlines = {"A": 2, "B": 3}
            for action in tape:
                next_now, next_status, next_ends = now, dict(statuses), dict(ends)
                expected_error = False
                if action.startswith("time") or action == "deferA2":
                    target = 2 if action == "deferA2" else int(action[-1])
                    expected_error = target < now or (action == "deferA2" and statuses["A"] != "pending")
                    if not expected_error:
                        next_now = target
                        for key in ("A", "B"):
                            if statuses[key] == "pending" and target >= deadlines[key]:
                                next_status[key], next_ends[key] = "expired", deadlines[key]
                else:
                    key = "A" if action == "completeA" else "B"
                    expected_error = statuses[key] != "pending"
                    if not expected_error:
                        next_status[key] = "served" if action == "completeA" else "rejected"
                        next_ends[key] = now
                old = q
                old_snapshot = (q.now, q.entries)
                try:
                    if action.startswith("time"):
                        q = q.advance_to(T(int(action[-1])))
                    elif action == "deferA2":
                        q = q.defer("A", T(2))
                    elif action == "completeA":
                        q = q.complete("A", receipt(da, q.now.ticks))
                    else:
                        q = q.reject("B")
                except ValueError:
                    self.assertTrue(expected_error, (tape, action))
                else:
                    self.assertFalse(expected_error, (tape, action))
                if not expected_error:
                    now, statuses, ends = next_now, next_status, next_ends
                self.assertEqual(old_snapshot, (old.now, old.entries))
                self.assertEqual(q.now, T(now))
                for key in ("A", "B"):
                    self.assertEqual(q.get(key).status.value, statuses[key])
                    self.assertEqual(q.get(key).ended_at, None if ends[key] is None else T(ends[key]))
                m = q.metrics()
                self.assertEqual(m.waiting_ticks, sum(now if ends[k] is None else ends[k] for k in ("A", "B")))
                self.assertEqual(m.terminal_failures, sum(s in ("rejected", "expired") for s in statuses.values()))
                transitions += 1
        self.observations["independent_reference"] = {"tapes": 6**4, "transitions": transitions}


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(TimedInputs))
    report = {"batch": "P3A", "tests_run": result.testsRun, "failures": len(result.failures),
              "errors": len(result.errors), "observations": TimedInputs.observations,
              "scope": "typed-input/queue/log tests; not a timed PRE simulator or cryptographic proof"}
    target = ROOT / "results/manifests/p3a_timed_inputs.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + "\n")
    sys.exit(0 if result.wasSuccessful() else 1)
