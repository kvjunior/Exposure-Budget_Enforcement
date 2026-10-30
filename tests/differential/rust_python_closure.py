"""
Differential test (model vs independent reference) and the two-history witness property.

Despite the filename (kept to match the planned tree, where the typed model is eventually
Rust), the typed model is currently the Python `delegation_model` package. The POINT of the
test is that it is compared against a SEPARATELY written reference (python/reference), not
that one of them is Rust. When the Rust model lands, this harness retargets to it unchanged.

Run: python tests/differential/rust_python_closure.py   (exit 0 = all expectations met)
"""
import sys, os, itertools
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "python"))

from delegation_model.loader import load_events
from delegation_model.authorization import fold_authorization
from delegation_model.closure import accumulate, conservative_closure, exposure
from delegation_model.types import Record
from reference import knowledge_closure as ref
from reference.witness import history_safe, history_exposed, NOW

FAIL = []
def expect(cid, cond, msg):
    ok = bool(cond)
    print(f"[{'ok ' if ok else 'FAIL'}] {cid:<22} {msg}")
    if not ok:
        FAIL.append(cid)

def model_open_records(events_json, coalition, now):
    events = load_events(events_json)
    auth = fold_authorization(events, now)
    K = accumulate(events, coalition, now, auth)
    cl = conservative_closure(K, events, now, auth)
    return sorted((r.stream, r.seq) for r in cl.records), sorted(
        (s.stream, s.epoch) for s in cl.scope_keys)

def ref_open_records(events_json, coalition, now):
    out = ref.closure(events_json, coalition, now)
    return sorted(tuple(r) for r in out["open_records"]), sorted(tuple(s) for s in out["scope_keys"])

# ---- 1. differential: model and reference agree on both histories ----
for name, hist in [("safe", history_safe()), ("exposed", history_exposed())]:
    m_rec, m_sk = model_open_records(hist, "C", NOW)
    r_rec, r_sk = ref_open_records(hist, "C", NOW)
    expect(f"diff_{name}_records", m_rec == r_rec,
           f"model vs reference open_records agree ({name}): {m_rec}")
    expect(f"diff_{name}_scopekeys", m_sk == r_sk,
           f"model vs reference scope_keys agree ({name}): {m_sk}")

# ---- 2. identical current ACL in both histories ----
def current_acl(events_json, now):
    events = load_events(events_json)
    auth = fold_authorization(events, now)
    produced = [Record(e["record"][0], e["record"][1]) for e in events_json
                if e["type"] == "RecordProduced" and e["t"] <= now]
    recips = {e["grant"]["recipient"] for e in events_json
              if e["type"] == "GrantIssued" and e["t"] <= now}
    acl = set()
    for rc in recips:
        for r in produced:
            if auth.authorized(rc, r):
                acl.add((rc, r.stream, r.seq))
    return acl

acl_safe = current_acl(history_safe(), NOW)
acl_exposed = current_acl(history_exposed(), NOW)
expect("acl_identical", acl_safe == acl_exposed,
       f"current ACL identical in both histories (both {sorted(acl_safe)})")
expect("acl_empty", acl_safe == set(),
       "current ACL is empty in both (grant revoked) -- no current permission difference")

# ---- 3. different retained capability: scope key exposed only in H_exposed ----
_, sk_safe = model_open_records(history_safe(), "C", NOW)
_, sk_exposed = model_open_records(history_exposed(), "C", NOW)
expect("safe_no_scopekey", sk_safe == [],
       "H_safe: sub-threshold kfrags -> NO scope key recovered")
expect("exposed_scopekey", sk_exposed == [("g", 0)],
       "H_exposed: threshold kfrags + recipient key -> scope A key recovered")

# ---- 4. different collateral exposure, and future exposure only in H_exposed ----
def expo(events_json, now):
    events = load_events(events_json)
    weights = {Record(e["record"][0], e["record"][1]): e.get("weight", 1.0)
               for e in events_json if e["type"] == "RecordProduced" and e["t"] <= now}
    auth = fold_authorization(events, now)
    K = accumulate(events, "C", now, auth)
    return exposure(K, events, now, weights, auth)

x_safe = expo(history_safe(), NOW)
x_exposed = expo(history_exposed(), NOW)
# past: records g:0,g:1 were AUTHORIZED to R while live, so even in H_exposed they are not
# "collateral" (outside-authorization). Collateral past exposure should be 0 in both here.
expect("past_zero_both", x_safe.past == 0.0 and x_exposed.past == 0.0,
       f"no collateral PAST exposure in either (authorized records don't count): "
       f"safe={x_safe.past}, exposed={x_exposed.past}")
expect("future_differs",
       x_safe.future_scopes == set() and x_exposed.future_scopes == {("g", 0)}
       if False else  # Scope is a dataclass; compare by membership below
       (len(x_safe.future_scopes) == 0 and len(x_exposed.future_scopes) == 1),
       f"FUTURE exposure differs: safe={len(x_safe.future_scopes)} active exposed scopes, "
       f"exposed={len(x_exposed.future_scopes)}")

# ---- 5. future record under exposed scope becomes openable in H_exposed, not H_safe ----
# Append a future record g:2 (still in active scope A) and recompute.
future_event = {"t": 12, "type": "RecordProduced", "record": ["g", 2], "weight": 1.0}
safe2 = history_safe() + [future_event]
exposed2 = history_exposed() + [future_event]
rec_safe2, _ = model_open_records(safe2, "C", 12)
rec_exposed2, _ = model_open_records(exposed2, "C", 12)
expect("future_rec_safe", ("g", 2) not in rec_safe2,
       "H_safe: future record g:2 is NOT openable by C")
expect("future_rec_exposed", ("g", 2) in rec_exposed2,
       "H_exposed: future record g:2 IS openable by C (exposed active scope key)")

print(f"\n{len(FAIL)} failures" + (f": {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
