"""
INDEPENDENT reference implementation of retained-knowledge closure.

Deliberately written in a different style from delegation_model.closure: here we reduce
everything to a flat set of string "facts" and iterate a fixpoint until nothing new is
derived. This exists so a differential test can catch bugs that a shared implementation
would hide. It must NOT import delegation_model.

Fact vocabulary (strings):
  corrupt_proxy:<proxy>
  corrupt_recipient:<recipient>
  recipient_sk:<recipient>
  kfrag:<grant>:<index>
  cfrag:<grant>:<stream>:<seq>:<index>
  data_key:<stream>:<seq>
  scope_key:<stream>:<epoch>
  plaintext:<stream>:<seq>
  open_record:<stream>:<seq>          (derived)

Rules (fixpoint):
  F2  >=t distinct kfrag:<g>:* AND recipient_sk:<recip(g)>  -> scope_key:<scope(g)>
  F3  >=t distinct cfrag:<g>:<r>:*  AND recipient_sk:<recip(g)> -> open_record:<r>
  F4  data_key:<r>  -> open_record:<r>
  F5  plaintext:<r> -> open_record:<r>
  F1  scope_key:<scope> -> open_record:<r> for every produced r in that scope
"""
from __future__ import annotations
from typing import Dict, List, Set, Tuple


def grant_facts(grants: List[dict]) -> Dict[str, dict]:
    return {g["grant_id"]: g for g in grants}


def accumulate_facts(events: List[dict], coalition: str, now: int) -> Set[str]:
    """Build the base fact set for a coalition from a JSON-ish event list."""
    facts: Set[str] = set()
    corrupt_proxies: Set[str] = set()
    corrupt_recipients: Set[str] = set()
    grants = grant_facts([e["grant"] for e in events
                          if e["type"] == "GrantIssued" and e["t"] <= now])

    for e in events:
        if e["t"] > now:
            continue
        et = e["type"]
        if et == "CorruptProxy" and e["coalition"] == coalition:
            corrupt_proxies.add(e["proxy"]); facts.add(f"corrupt_proxy:{e['proxy']}")
        elif et == "CorruptRecipient" and e["coalition"] == coalition:
            corrupt_recipients.add(e["recipient"]); facts.add(f"corrupt_recipient:{e['recipient']}")
        elif et == "DiscloseScopeKey" and e["coalition"] == coalition:
            facts.add(f"scope_key:{e['scope'][0]}:{e['scope'][1]}")
        elif et == "DiscloseDataKey" and e["coalition"] == coalition:
            facts.add(f"data_key:{e['record'][0]}:{e['record'][1]}")
        elif et == "DisclosePlaintext" and e["coalition"] == coalition:
            facts.add(f"plaintext:{e['record'][0]}:{e['record'][1]}")

    for rcpt in corrupt_recipients:
        facts.add(f"recipient_sk:{rcpt}")

    for e in events:
        if e["t"] > now:
            continue
        et = e["type"]
        if et == "KFragInstalled" and e["proxy"] in corrupt_proxies:
            facts.add(f"kfrag:{e['grant_id']}:{e['index']}")
        elif et == "CFragProduced":
            g = grants.get(e["grant_id"])
            if g and g["recipient"] in corrupt_recipients:
                r = e["record"]
                facts.add(f"cfrag:{e['grant_id']}:{r[0]}:{r[1]}:{e['index']}")
    return facts


def produced_records(events: List[dict], now: int) -> List[Tuple[str, int]]:
    return [tuple(e["record"]) for e in events
            if e["type"] == "RecordProduced" and e["t"] <= now]


def scope_of(events: List[dict], now: int, record: Tuple[str, int]):
    """Reconstruct which (stream,epoch) scope covers a record, from ScopeActivated events."""
    stream, seq = record
    spans = []  # (start_seq, scope_tuple)
    for e in events:
        if e["t"] > now:
            continue
        if e["type"] == "ScopeActivated" and e["scope"][0] == stream:
            spans.append((e["start_seq"], tuple(e["scope"])))
    spans.sort()
    cur = None
    for start, sc in spans:
        if seq >= start:
            cur = sc
        else:
            break
    return cur


def closure(events: List[dict], coalition: str, now: int) -> Dict[str, object]:
    facts = accumulate_facts(events, coalition, now)
    grants = grant_facts([e["grant"] for e in events
                          if e["type"] == "GrantIssued" and e["t"] <= now])
    produced = produced_records(events, now)

    changed = True
    while changed:
        changed = False
        new: Set[str] = set()

        # F2: threshold kfrags + recipient key -> scope key
        for gid, g in grants.items():
            idxs = {f.split(":")[2] for f in facts if f.startswith(f"kfrag:{gid}:")}
            if len(idxs) >= g["threshold"] and f"recipient_sk:{g['recipient']}" in facts:
                sc = tuple(g["scope"])
                fact = f"scope_key:{sc[0]}:{sc[1]}"
                if fact not in facts:
                    new.add(fact)

        # F3' (corrected per review R1): mixed-fragment local transformation.
        # Available share indices for (grant g, record r) = received-cfrag indices for (g,r)
        # UNION raw-kfrag indices for g (the coalition locally transforms r's public capsule
        # with each held kfrag). A kfrag index and a cfrag index coincide iff they are the
        # same share, so the UNION counts each share once. >= t available + recipient key
        # opens r.
        # received cfrags per (grant, record)
        cfrag_idx: Dict[Tuple[str, Tuple[str, int]], Set[str]] = {}
        for f in facts:
            if f.startswith("cfrag:"):
                _, gid, st, sq, ix = f.split(":")
                cfrag_idx.setdefault((gid, (st, int(sq))), set()).add(ix)
        # held kfrags per grant
        kfrag_idx: Dict[str, Set[str]] = {}
        for f in facts:
            if f.startswith("kfrag:"):
                _, gid, ix = f.split(":")
                kfrag_idx.setdefault(gid, set()).add(ix)
        # candidate records: any with a received cfrag, plus any produced record in a grant's
        # range/scope for which the coalition holds a kfrag.
        candidates: Set[Tuple[str, Tuple[str, int]]] = set(cfrag_idx.keys())
        for gid, g in grants.items():
            if gid not in kfrag_idx:
                continue
            rng = g["rng"]  # [stream, lo, hi]
            for (rs, rq) in produced:
                in_range = (rs == rng[0] and rq >= rng[1] and (rng[2] is None or rq < rng[2]))
                if in_range and scope_of(events, now, (rs, rq)) == tuple(g["scope"]):
                    candidates.add((gid, (rs, rq)))
        for (gid, (rs, rq)) in candidates:
            g = grants.get(gid)
            if not g or f"recipient_sk:{g['recipient']}" not in facts:
                continue
            avail = set(cfrag_idx.get((gid, (rs, rq)), set())) | kfrag_idx.get(gid, set())
            if len(avail) >= g["threshold"]:
                fact = f"open_record:{rs}:{rq}"
                if fact not in facts:
                    new.add(fact)

        # F4, F5
        for f in list(facts):
            if f.startswith("data_key:"):
                _, st, sq = f.split(":"); new.add(f"open_record:{st}:{sq}")
            elif f.startswith("plaintext:"):
                _, st, sq = f.split(":"); new.add(f"open_record:{st}:{sq}")

        # F1: scope key -> every produced record in that scope
        scope_keys = {f for f in facts if f.startswith("scope_key:")}
        for sk in scope_keys:
            _, st, ep = sk.split(":")
            for (rs, rq) in produced:
                if rs == st and scope_of(events, now, (rs, rq)) == (st, int(ep)):
                    new.add(f"open_record:{rs}:{rq}")

        additions = new - facts
        if additions:
            facts |= additions
            changed = True

    open_records = sorted(tuple(f.split(":")[1:]) for f in facts if f.startswith("open_record:"))
    open_records = [(s, int(q)) for s, q in open_records]
    scope_keys = sorted(tuple(f.split(":")[1:]) for f in facts if f.startswith("scope_key:"))
    scope_keys = [(s, int(e)) for s, e in scope_keys]
    return {"open_records": open_records, "scope_keys": scope_keys, "facts": sorted(facts)}
