"""
Tests the exposure-constraint admission check against the two-history witness.
Exit 0 = all expectations met. Run with the PROD venv.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "python"))

from delegation_model.loader import load_events
from delegation_model.types import Record
from delegation_manager.exposure_check import (evaluate_exposure, ExposureBudget)
from reference.witness import history_safe, history_exposed, NOW

FAIL = []
def expect(cid, cond, msg):
    ok = bool(cond)
    print(f"[{'ok ' if ok else 'FAIL'}] {cid:<24} {msg}")
    if not ok: FAIL.append(cid)

def weights_of(hist, now):
    return {Record(e["record"][0], e["record"][1]): e.get("weight", 1.0)
            for e in hist if e["type"] == "RecordProduced" and e["t"] <= now}

# budget: allow 0 exposed active scopes, 0 past collateral weight
strict = ExposureBudget(max_future_scopes=0, max_past_weight=0.0)
lenient = ExposureBudget(max_future_scopes=1, max_past_weight=0.0)

# H_safe: no scope key exposed -> within strict budget
v_safe = evaluate_exposure(load_events(history_safe()), NOW, ["C"], strict,
                           weights_of(history_safe(), NOW))
expect("safe_within_strict", v_safe.ok,
       f"H_safe within strict budget (future_scopes={v_safe.worst_future_scopes})")

# H_exposed: one exposed active scope -> breaches strict, within lenient
v_exp_strict = evaluate_exposure(load_events(history_exposed()), NOW, ["C"], strict,
                                 weights_of(history_exposed(), NOW))
expect("exposed_breaches_strict", not v_exp_strict.ok,
       f"H_exposed BREACHES strict budget ({v_exp_strict.reason})")
v_exp_lenient = evaluate_exposure(load_events(history_exposed()), NOW, ["C"], lenient,
                                  weights_of(history_exposed(), NOW))
expect("exposed_within_lenient", v_exp_lenient.ok,
       f"H_exposed within lenient budget (future_scopes={v_exp_lenient.worst_future_scopes})")

# owner-root coalition is excluded from the bound (not counted toward breach)
v_root = evaluate_exposure(load_events(history_exposed()), NOW, ["C"], strict,
                           weights_of(history_exposed(), NOW), owner_root_labels=["C"])
expect("owner_root_excluded", "C" in v_root.owner_root_coalitions,
       f"owner-root coalition excluded from bound (hits={v_root.owner_root_coalitions})")

print(f"\n{len(FAIL)} failures" + (f": {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
