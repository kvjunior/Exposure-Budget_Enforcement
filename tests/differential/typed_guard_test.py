"""Guard contract checks for the separate ChatGPT correction branch (slice 1.2).

These are model checks, not a security proof or a service transaction test.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from delegation_model.types import Grant, Scope, Record, RecordRange
from delegation_model.events import (
    StreamAuthorized, ScopeActivated, RecordProduced, GrantIssued,
    KFragInstalled, OwnerAvailability, CorruptProxy,
)
from delegation_model.possible import CoalitionSpec
from delegation_manager.manager import (
    Action, ActionKind, PreAuth, project_observation, check_action,
)
from delegation_manager.exposure_check import ExposureBudget


class TypedGuardTests(unittest.TestCase):
    def setUp(self):
        self.events = [StreamAuthorized(0, "O", "g", "D"),
                       ScopeActivated(1, "O", Scope("g", 0), "g.k0", 0),
                       RecordProduced(2, Record("g", 0))]
        self.grant = Grant("G", "O", "R", Scope("g", 0), RecordRange("g", 0, 1),
                           2, 3, ("p0", "p1", "p2"), 3, None)
        self.action = Action(ActionKind.ADMIT_GRANT, grant=self.grant,
                             authorized_kfrag_indices=(0, 1))
        self.obs = project_observation(self.events, 2)

    def check_with(self, family, budget=None, observation=None):
        return check_action(self.action, observation or self.obs, PreAuth(),
                            budget or ExposureBudget(0, 0), family, {})

    def test_reach_changes_feasibility(self):
        # ONE allowed proxy is below t=2 despite two installations. The code
        # must not silently give that coalition every new grant party instead.
        narrow = CoalitionSpec("C", proxies={"p0"}, recipients={"R"})
        broad = CoalitionSpec("C", proxies={"p0", "p1"}, recipients={"R"})
        self.assertTrue(self.check_with([narrow]).ok)
        self.assertFalse(self.check_with([broad]).ok)

    def test_labels_and_empty_families_fail_closed(self):
        self.assertFalse(self.check_with(["C"]).ok)
        self.assertFalse(self.check_with([]).ok)

    def test_duplicate_labels_and_delivery_indices_fail_closed(self):
        spec = CoalitionSpec("C", proxies={"p0"}, recipients={"R"})
        self.assertFalse(self.check_with([spec, spec]).ok)
        action = Action(ActionKind.ADMIT_GRANT, grant=self.grant,
                        authorized_kfrag_indices=(0, 0))
        self.assertFalse(check_action(action, self.obs, PreAuth(),
                                      ExposureBudget(1, 1), [spec], {}).ok)

    def test_hidden_and_future_events_do_not_change_decision(self):
        spec = CoalitionSpec("C", proxies={"p0"}, recipients={"R"})
        hidden_and_future = self.events + [CorruptProxy(3, "p1", "C"),
                                           OwnerAvailability(100, "O", False)]
        alternative = project_observation(hidden_and_future, 2)
        self.assertEqual(self.check_with([spec]),
                         self.check_with([spec], observation=alternative))

    def test_historical_records_become_authorized_when_grant_lives(self):
        from delegation_model.events import CorruptRecipient, DiscloseDataKey
        from delegation_model.closure import accumulate, exposure
        events = self.events + [GrantIssued(3, self.grant),
                                 CorruptRecipient(4, "R", "C"),
                                 DiscloseDataKey(5, Record("g", 0), "C")]
        # Record produced at 2, grant starts at 3: delayed historical retrieval
        # is intentionally authorized. Do NOT require production >= valid_from.
        self.assertEqual(exposure(accumulate(events, "C", 5), events, 5, {}).past, 0)

    def test_coordinate_maxima_on_actual_action_path(self):
        old = Grant("OLD", "O", "R_old", Scope("b", 0), RecordRange("b", 0, 1),
                    2, 3, ("p0", "p1", "p2"), 6, None)
        new = Grant("NEW", "O", "R_new", Scope("a", 0), RecordRange("a", 0, 1),
                    2, 3, ("q0", "q1", "q2"), 11, None)
        events = [StreamAuthorized(0, "O", "a", "Da"),
                  StreamAuthorized(1, "O", "b", "Db"),
                  ScopeActivated(2, "O", Scope("a", 0), "a.k0", 0),
                  ScopeActivated(3, "O", Scope("b", 0), "b.k0", 0),
                  RecordProduced(4, Record("b", 0)),
                  RecordProduced(5, Record("b", 1)), GrantIssued(6, old),
                  KFragInstalled(7, "OLD", "p0", 0),
                  KFragInstalled(8, "OLD", "p1", 1),
                  ScopeActivated(9, "O", Scope("b", 1), "b.k1", 2),
                  RecordProduced(10, Record("a", 0))]
        family = [CoalitionSpec("future", proxies={"q0", "q1"}, recipients={"R_new"}),
                  CoalitionSpec("past", proxies={"p0", "p1"}, recipients={"R_old"})]
        action = Action(ActionKind.ADMIT_GRANT, grant=new,
                        authorized_kfrag_indices=(0, 1))
        obs = project_observation(events, 10)
        strict = check_action(action, obs, PreAuth(), ExposureBudget(1, 0), family, {})
        reversed_order = check_action(action, obs, PreAuth(), ExposureBudget(1, 0),
                                      list(reversed(family)), {})
        lenient = check_action(action, obs, PreAuth(), ExposureBudget(1, 1), family, {})
        self.assertFalse(strict.ok)
        self.assertIn("past=1.0", strict.exposure_reason)
        self.assertIn("past witness past", strict.exposure_reason)
        self.assertEqual(strict, reversed_order)
        self.assertTrue(lenient.ok)


if __name__ == "__main__":
    unittest.main()
