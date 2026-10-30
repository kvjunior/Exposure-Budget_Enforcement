"""
Review R4: two properties.
  (A) NON-INTERFERENCE: the original safe/exposed pair has identical observations, so identical
      observable history + request + public family MUST yield identical online decisions.
      Changing only hidden corruption must not change what the controller sees or decides.
  (B) ONLINE-POLICY WITNESS: the new lowobs/highobs pair has the SAME current ACL but DIFFERENT
      observable installation history. Using possible-knowledge over the declared family (NO
      realized corruption), the controller CAN distinguish them: highobs could expose scope A,
      lowobs cannot.

Run with the PROD venv. Exit 0 = all expectations met.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "python"))

from delegation_model.loader import load_events
from delegation_model.types import Record, Scope
from delegation_model.possible import CoalitionSpec, possible_exposure
from delegation_manager.manager import project_observation
from reference.witness import (history_safe, history_exposed, NOW,
                               history_lowobs, history_highobs, NOW_D)

FAIL = []
def expect(cid, cond, msg):
    ok = bool(cond); print(f"[{'ok ' if ok else 'FAIL'}] {cid:<22} {msg}")
    if not ok: FAIL.append(cid)

# (A) non-interference: identical observations for safe vs exposed
obs_safe = project_observation(load_events(history_safe()), NOW)
obs_exp = project_observation(load_events(history_exposed()), NOW)
expect("noninterference_obs",
       obs_safe.events == obs_exp.events and obs_safe.owner_online == obs_exp.owner_online,
       "hidden corruption does NOT change observable history (same inputs => same decision)")

# (B) online-policy witness: same current ACL, different observable histories
def acl(histjson, now):
    ev = load_events(histjson)
    obs = project_observation(ev, now)
    produced = [Record(e["record"][0], e["record"][1]) for e in histjson
                if e["type"] == "RecordProduced" and e["t"] <= now]
    recips = {e["grant"]["recipient"] for e in histjson
              if e["type"] == "GrantIssued" and e["t"] <= now}
    return {(rc, r.stream, r.seq) for rc in recips for r in produced if obs.auth.authorized(rc, r)}

acl_low = acl(history_lowobs(), NOW_D)
acl_high = acl(history_highobs(), NOW_D)
expect("witness_same_acl", acl_low == acl_high == set(),
       f"lowobs and highobs have identical current ACL (both empty): {acl_low}, {acl_high}")

# possible exposure over the declared family C = {proxies p0,p1,p2; recipient R}
spec = CoalitionSpec("C", proxies={"p0", "p1", "p2"}, recipients={"R"})
wlow = {Record(e["record"][0], e["record"][1]): e.get("weight", 1.0)
        for e in history_lowobs() if e["type"] == "RecordProduced"}
whigh = {Record(e["record"][0], e["record"][1]): e.get("weight", 1.0)
         for e in history_highobs() if e["type"] == "RecordProduced"}
x_low = possible_exposure(load_events(history_lowobs()), spec, NOW_D, wlow)
x_high = possible_exposure(load_events(history_highobs()), spec, NOW_D, whigh)
expect("lowobs_no_possible_scope", len(x_low.future_scopes) == 0,
       "lowobs: only 1 kfrag observable installed -> scope A exposure NOT possible")
expect("highobs_possible_scope", len(x_high.future_scopes) == 1,
       "highobs: 2 kfrags observable installed -> scope A exposure IS possible (future-active)")
expect("witness_distinguishable", len(x_low.future_scopes) != len(x_high.future_scopes),
       "an online, observable-history-based controller CAN distinguish the two")

print(f"\n{len(FAIL)} failures" + (f": {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
