"""Independent invariants for complete-horizon P3F/P3E evaluation.

This test reads the input trace independently from the execution model and checks
that every planned production and every released demand has a terminal outcome.
It intentionally includes the original failing seeds 0, 1, and 4.
"""
import csv
import os
import subprocess
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)
from python.experiments.p3e_workload_eval import gen_workload, run_policy, POLICIES
from delegation_manager.service_simulator import RecordProduction
from delegation_model.timed_capabilities import Budget
from delegation_model.timed_log import DemandArrival, PublicEvent

CONFIGS = {
    'light': dict(n_streams=4, horizon=24, report_delay_max=2, offline_prob=.2),
    'heavy': dict(n_streams=4, horizon=30, report_delay_max=4, offline_prob=.3),
    'intermittent': dict(n_streams=4, horizon=28, report_delay_max=3, offline_prob=.55),
}

class FullHorizon(unittest.TestCase):
    def test_regression_seeds_and_complete_accounting(self):
        for seed in (0, 1, 4):
            cfg = CONFIGS['heavy']
            trace, dems, grants = gen_workload(seed, **cfg)
            for policy in POLICIES:
                with self.subTest(seed=seed, policy=policy):
                    m = run_policy(policy, trace, dems, grants, Budget(5, 0, 6), cfg['horizon'])
                    self.assertEqual(m['simulation_end_tick'], 30)
                    self.assertEqual(m['served']+m['rejected']+m['expired'], len(dems))
                    self.assertEqual(m['pending'], 0)
                    self.assertEqual(m['productions_completed']+m['fence_drops'],
                                     sum(isinstance(e, RecordProduction) for e in trace))
                    self.assertGreaterEqual(m['trace_tick_count'], 2)

    def test_all_configurations_and_budgets(self):
        for name, cfg in CONFIGS.items():
            for seed in (0, 1, 4, 9, 19, 29):
                events, demands, grants = gen_workload(seed, **cfg)
                arrivals = [e.payload.demand for e in events
                            if isinstance(e, PublicEvent) and isinstance(e.payload, DemandArrival)]
                self.assertEqual(set(d.demand_id for d in demands), set(d.demand_id for d in arrivals))
                self.assertTrue(all(d.released_at.ticks < cfg['horizon'] for d in demands))
                for b in (0, 1):
                    for p in POLICIES:
                        with self.subTest(config=name, seed=seed, b=b, policy=p):
                            m = run_policy(p, events, demands, grants, Budget(5,b,6),cfg['horizon'])
                            self.assertEqual(m['simulation_end_tick'],cfg['horizon'])
                            self.assertEqual(m['pending'],0)
                            self.assertEqual(m['demands_total'],cfg['n_streams'])
                            self.assertEqual(m['productions_scheduled'],2*cfg['n_streams'])
                            self.assertEqual(m['productions_completed']+m['fence_drops'],2*cfg['n_streams'])
                            if p in ('greedy_full','conservative'):
                                self.assertEqual(m['violation'],0)

    def test_same_trace_different_enforcement(self):
        cfg = CONFIGS['heavy']
        observed = {'unfenced':0, 'production_only':0, 'admission_only':0, 'greedy_full':0}
        for seed in range(30):
            ev, dems, gs = gen_workload(seed, **cfg)
            for p in observed:
                m = run_policy(p, ev, dems, gs, Budget(5,0,6),cfg['horizon'])
                observed[p] += m['violation']
        self.assertGreater(observed['unfenced'],0)
        self.assertGreater(observed['production_only'],0)
        self.assertGreater(observed['admission_only'],0)
        self.assertEqual(observed['greedy_full'],0)

if __name__ == '__main__':
    unittest.main(verbosity=2)
