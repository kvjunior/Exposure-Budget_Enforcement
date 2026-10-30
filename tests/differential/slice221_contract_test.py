"""Meaningful regressions for R22-01..03 and their shared plan contracts."""
from dataclasses import asdict, replace
from itertools import product
from pathlib import Path
import json
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))
from delegation_model.types import Grant, Record, RecordRange, Scope
from delegation_model.events import (StreamAuthorized, ScopeActivated, RecordProduced,
                                     OwnerAvailability)
from delegation_model.possible import CoalitionSpec, possible_exposure
from delegation_model.transitions import fold_state
from delegation_manager.manager import (Action, ActionKind, GrantToken, PreAuth,
                                        project_observation, check_action)
from delegation_manager.executor import approve, execute
from delegation_manager.exposure_check import ExposureBudget
from delegation_manager.candidate_actions import enumerate_actions
from delegation_manager.cost_model import CostWeights
from delegation_manager.offline_oracle import (Instance, solve, replay_plan,
                                               _apply_action_events)
from independent_reference import (ref_solve, reference_actions,
                                   reference_evaluate_plan)
from python.experiments import controller_comparison as comparison

SC = Scope("g", 0)
R0, R1, R2 = (Record("g", i) for i in range(3))
FAMILY = [CoalitionSpec("C", {"p0"}, {"R"})]


def base(records=1, offline=False):
    h = [StreamAuthorized(0, "O", "g", "D"), ScopeActivated(1, "O", SC, "g.k0", 0)]
    h.extend(RecordProduced(2+i, Record("g", i)) for i in range(records))
    if offline:
        h.append(OwnerAvailability(h[-1].t+1, "O", False))
    return h


def grant(gid="G", lo=0, hi=1, shares=1, threshold=1, valid_to=None):
    return Grant(gid, "O", "R", SC, RecordRange("g", lo, hi), threshold, shares,
                 tuple(f"p{i}" for i in range(shares)), 0, valid_to)


def admit(g, indices=(0,)):
    return Action(ActionKind.ADMIT_GRANT, grant=g, authorized_kfrag_indices=indices)


def rotate(seq):
    return Action(ActionKind.ACTIVATE_SCOPE, scope=Scope("g", 1),
                  new_scope_key_id="g.e1.k0", start_seq=seq)


def token(lo=0, hi=1, indices=(0,), issue_to=None):
    return GrantToken("O", "R", "g", 0, lo, hi, 0, issue_to, indices)


def metadata_instance():
    gs = [grant("BROAD", 0, 3), grant("N1", 1, 2), grant("N2", 2, 3)]
    pa = PreAuth(scope_tokens={("O", "g", 1)}, verified=True,
                 grant_tokens=(token(0, 3, ()), token(1, 2), token(2, 3)))
    return _instance(base(3, True), gs, pa, weights={R0: 1, R1: 1, R2: 1})


def _instance(history, grants, preauth=None, maximum=2, weights=None, budget=None):
    from delegation_manager.policies import Request
    return Instance(history, [Request(history[-1].t+1+i, g) for i, g in enumerate(grants)],
                    budget or ExposureBudget(0, 0), FAMILY, weights or {R0: 1, R1: 1},
                    preauth=preauth or PreAuth(), max_plan_actions=maximum)


def authority_instance():
    pa = PreAuth(scope_tokens={("O", "g", 1)}, grant_tokens=(token(1, 2),), verified=True)
    return _instance(base(2, True), [grant("BROAD", 0, 2), grant("N", 1, 2)], pa)


def bound_instance():
    return _instance(base(2), [grant("BROAD", 0, 2), grant("N", 1, 2)], maximum=1)


def plan_json(plans):
    return [[dict(asdict(a), kind=a.kind.value) for a in p] for p in plans]


class Contracts(unittest.TestCase):
    observations = {}

    def test_noncanonical_timestamp_refused_before_delivery(self):
        h = base()
        o = project_observation(h, 2)
        with self.assertRaisesRegex(ValueError, "cutoff"):
            approve(admit(grant(valid_to=4)), o, ExposureBudget(1, 0), FAMILY, {R0: 1}, t0=100)
        self.assertEqual(len(h), 3)
        self.observations["R22-01_noncanonical_approval"] = "ValueError before delivery"

    def test_exact_default_plan_keeps_endpoint_budget(self):
        h = base()
        o = project_observation(h, 2)
        a = admit(grant(valid_to=4))
        b = ExposureBudget(1, 0)
        receipt = approve(a, o, b, FAMILY, {R0: 1})
        ex = execute(a, o, receipt, b, FAMILY, {R0: 1})
        self.assertTrue(ex.committed)
        self.assertEqual([e.t for e in ex.log_appended], [3, 4])
        self.assertEqual(tuple(ex.log_appended), receipt.planned_events)
        x = possible_exposure(h + list(ex.log_appended), FAMILY[0], ex.state.t, {R0: 1})
        self.assertEqual(x.past, 0)
        self.observations["R22-01_default"] = {"times": [e.t for e in ex.log_appended], "past": x.past}

    def test_timestamp_override_at_commit_delivers_nothing(self):
        o = project_observation(base(), 2)
        a = admit(grant(valid_to=4))
        b = ExposureBudget(1, 0)
        r = approve(a, o, b, FAMILY, {R0: 1})
        ex = execute(a, o, r, b, FAMILY, {R0: 1}, t0=100)
        self.assertFalse(ex.committed)
        self.assertEqual(ex.outbox, ())
        self.assertEqual(ex.log_appended, ())

    def test_changed_cutoff_and_expired_token_refused(self):
        h = base(1, True)
        old, now = project_observation(h, 3), project_observation(h, 10)
        pa = PreAuth(grant_tokens=(token(issue_to=3),), verified=True)
        a = admit(grant())
        b = ExposureBudget(1, 0)
        r = approve(a, old, b, FAMILY, {R0: 1}, pa)
        self.assertTrue(r.checked_ok)
        self.assertFalse(check_action(a, now, pa, b, FAMILY, {R0: 1}).ok)
        ex = execute(a, now, r, b, FAMILY, {R0: 1}, preauth=pa)
        self.assertFalse(ex.committed)
        self.assertEqual(ex.outbox, ())

    def test_offline_context_required_at_commit(self):
        o = project_observation(base(1, True), 3)
        pa = PreAuth(grant_tokens=(token(),), verified=True)
        a = admit(grant())
        b = ExposureBudget(1, 0)
        r = approve(a, o, b, FAMILY, {R0: 1}, pa)
        self.assertTrue(execute(a, o, r, b, FAMILY, {R0: 1}, preauth=pa).committed)
        self.assertFalse(execute(a, o, r, b, FAMILY, {R0: 1}).committed)

    def test_idle_logical_cutoff_uses_cutoff_not_last_event(self):
        h = base()
        o = project_observation(h, 10)
        a = admit(grant())
        b = ExposureBudget(1, 0)
        r = approve(a, o, b, FAMILY, {R0: 1})
        ex = execute(a, o, r, b, FAMILY, {R0: 1})
        self.assertTrue(ex.committed)
        self.assertEqual([e.t for e in ex.log_appended], [11, 12])

    def test_invalid_indices_refuse_without_planner_index_error(self):
        o = project_observation(base(), 2)
        a = admit(grant(), (7,))
        r = approve(a, o, ExposureBudget(1, 0), FAMILY, {R0: 1})
        self.assertFalse(r.checked_ok)
        self.assertEqual(r.planned_events, ())
        self.assertFalse(execute(a, o, r, ExposureBudget(1, 0), FAMILY, {R0: 1}).committed)

    def _compare(self, name, inst, expected):
        opt, reference = solve(inst), ref_solve(inst)
        rp = reference_actions(reference)
        ro, rr = replay_plan(inst, opt.plans), replay_plan(inst, rp)
        self.assertEqual(opt.total_cost, expected)
        self.assertEqual(reference.total_cost, expected)
        self.assertTrue(ro[0] and rr[0])
        self.assertEqual(ro[1], opt.total_cost)
        self.assertEqual(rr[1], reference.total_cost)
        self.observations[name] = {
            "oracle": {"cost": opt.total_cost, "replay": ro, "plans": plan_json(opt.plans)},
            "reference": {"cost": reference.total_cost, "served": reference.served,
                          "replay": rr, "plans": plan_json(rp)}}
        return opt, reference

    def test_metadata_state_is_included_in_optimum(self):
        inst = metadata_instance()
        opt, _ = self._compare("R22-02_metadata", inst, 24)
        self.assertTrue(any(a.kind == ActionKind.ADMIT_GRANT and not a.authorized_kfrag_indices
                            for a in opt.actions))
        # The review established 25 as a FEASIBLE witness, not the optimum.
        # The full search finds 24 by foregoing the first narrow completion.
        witness = [[admit(inst.requests[0].grant, ())],
                   [rotate(3), admit(inst.requests[1].grant)],
                   [admit(inst.requests[2].grant)]]
        replay = replay_plan(inst, witness)
        self.assertEqual(replay, (True, 25.0, "ok (served 2, unserved 1)"))
        self.observations["R22-02_metadata"]["original_25_witness"] = {
            "plans": plan_json(witness), "replay": replay}

    def test_scope_token_does_not_create_grant_authority(self):
        inst = authority_instance()
        self._compare("R22-03_scope_vs_grant", inst, 20)
        illegal = [[rotate(2), admit(inst.requests[0].grant)], [admit(inst.requests[1].grant)]]
        self.assertFalse(replay_plan(inst, illegal)[0])
        ref_plan = [("activate", (Scope("g", 1), "g.e1.k0", 2)),
                    ("admit", (inst.requests[0].grant, (0,)))]
        self.assertIsNone(reference_evaluate_plan(inst, inst.base_history, inst.requests[0], ref_plan))

    def test_reference_and_oracle_respect_k_one(self):
        inst = bound_instance()
        opt, ref = self._compare("R22-03_K1", inst, 20)
        self.assertTrue(all(len(p) == 1 for p in opt.plans + ref.plans))

    def test_token_expiry_between_rotate_and_admit(self):
        h = base(1, True)
        g = grant()
        pa = PreAuth(scope_tokens={("O", "g", 1)},
                     grant_tokens=(token(issue_to=3),), verified=True)
        inst = _instance(h, [g], pa, weights={R0: 1})
        proposed = [[rotate(1), admit(g)]]
        self.assertFalse(replay_plan(inst, proposed)[0])
        ref_plan = [("activate", (Scope("g", 1), "g.e1.k0", 1)), ("admit", (g, (0,)))]
        self.assertIsNone(reference_evaluate_plan(inst, h, inst.requests[0], ref_plan))

    def test_all_subset_sizes_are_real_candidates(self):
        from delegation_manager.policies import Request
        g = grant(shares=2)
        candidates = enumerate_actions(project_observation(base(), 2), Request(3, g))
        self.assertEqual({a.authorized_kfrag_indices for a in candidates if a.kind == ActionKind.ADMIT_GRANT},
                         {(), (0,), (1,), (0, 1)})

    def test_large_delivery_domain_refused_before_materialization(self):
        from delegation_manager.policies import Request
        g = grant(shares=60, threshold=30)
        with patch("itertools.combinations", side_effect=AssertionError("allocated before bound")):
            with self.assertRaisesRegex(ValueError, "branching"):
                enumerate_actions(project_observation(base(), 2), Request(3, g))

    def test_plan_grammar_and_demand_are_enforced(self):
        inst = _instance(base(), [grant()], budget=ExposureBudget(1, 0), weights={R0: 1})
        a, r = admit(inst.requests[0].grant), rotate(1)
        for plan in ([], [a, r], [Action(ActionKind.DEFER), a], [r, r],
                     [admit(replace(inst.requests[0].grant, valid_to=20))]):
            with self.subTest(plan=plan):
                self.assertFalse(replay_plan(inst, [plan])[0])
        self.assertTrue(replay_plan(inst, [[r, a]])[0])

    def test_nonnegative_cost_prerequisite(self):
        for bad in (-1, float("nan"), float("inf")):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    CostWeights(per_fragment_cost=bad)

    def test_canonical_service_domain_is_enforced_by_both_models(self):
        inst = _instance(base(), [grant(shares=2)], budget=ExposureBudget(1, 0), weights={R0: 1})
        g = inst.requests[0].grant
        # Sets use a single sorted representation; other epoch/key identities
        # belong to the lower-level checker, not this bounded service domain.
        for a in (admit(g, (1, 0)), replace(rotate(1), scope=Scope("g", 3)),
                  replace(rotate(1), new_scope_key_id="arbitrary-key")):
            self.assertFalse(replay_plan(inst, [[a]])[0])
        ref_plan = [("admit", (g, (1, 0)))]
        self.assertIsNone(reference_evaluate_plan(inst, inst.base_history, inst.requests[0], ref_plan))
        self.assertTrue(replay_plan(inst, [[admit(g, (0, 1))]])[0])

    def test_reference_agrees_on_small_authority_budget_matrix(self):
        rows = []
        for k, threshold, future, authority in product((1, 2), (1, 2), (0, 1),
                                                       ("online", "offline_valid", "scope_only")):
            h = base(2, authority != "online")
            gs = [grant("A", 0, 2, shares=2, threshold=threshold),
                  grant("B", 0, 2, shares=2, threshold=threshold)]
            pa = PreAuth(scope_tokens={("O", "g", 1)}, verified=True,
                         grant_tokens=(token(0, 2, (0, 1)),) if authority == "offline_valid" else ())
            inst = _instance(h, gs, pa, maximum=k, budget=ExposureBudget(future, 0))
            opt, ref = solve(inst), ref_solve(inst)
            rr = replay_plan(inst, reference_actions(ref))
            with self.subTest(k=k, threshold=threshold, future=future, authority=authority):
                self.assertEqual(opt.total_cost, ref.total_cost)
                self.assertTrue(rr[0])
                self.assertEqual(rr[1], ref.total_cost)
                self.assertIn(f"served {ref.served},", rr[2])
            rows.append({"K": k, "threshold": threshold, "future_budget": future,
                         "authority": authority, "oracle_cost": opt.total_cost,
                         "reference_cost": ref.total_cost})
        self.observations["matrix"] = rows

    def test_comparison_receives_only_remaining_forecast(self):
        inst = comparison.make_instance(3, 1)
        forecasts = []
        def capture(obs, req, *args, **kwargs):
            forecasts.append([r.grant.grant_id for r in kwargs["forecast"]])
            return Action(ActionKind.DEFER)
        with patch.object(comparison, "rolling_horizon_policy", side_effect=capture):
            self.assertTrue(comparison.run_method("rolling_horizon", inst)["feasible"])
        self.assertEqual(forecasts, [["G1", "G2"], ["G2"], []])


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts))
    report = {"batch": "2.2.1", "tests_run": result.testsRun,
              "failures": len(result.failures), "errors": len(result.errors),
              "observations": Contracts.observations,
              "scope": "bounded model/code regression evidence; no cryptographic or novelty proof"}
    target = ROOT / "results/manifests/slice221_contracts.json"
    target.write_text(json.dumps(report, indent=2) + "\n")
    sys.exit(0 if result.wasSuccessful() else 1)
