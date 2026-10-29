"""
Retained-knowledge state K_t(C), conservative closure Cl_hat, and exposure X_t(C).

This is the formal heart of the management model. It is PURE reasoning over *what a
coalition could decrypt*, derived from accumulated retained material and the documented
capabilities of the chosen PRE primitive (Umbral threshold PRE). It performs no
cryptography; delegation_crypto's executable witnesses confirm the rules are faithful to
the real construction (see tests/adversarial and the reference cross-check).

Accumulation (brief sec 4.2): K_t(C) is monotone non-decreasing in t. Revocation does NOT
remove anything from K_t(C). Corruption is adaptive under a lifetime budget; a kfrag/cfrag
installed before or after corruption still accumulates to C once the holding party is in C.

Closure rules (each conservative = may over-approximate what C can open, never under):
  R1 SCOPE_KEY held            -> every record of that scope, present AND future, is openable.
  R2 t matching KFRAGs of a grant + the grant's recipient key held
                               -> the grant's scope key is recoverable (Umbral: t shares +
                                  receiving_sk reconstruct delegating_sk). Promotes to R1.
  R3 t CFRAGs for a specific record + recipient key held
                               -> THAT record is openable (capsule opens) WITHOUT the raw
                                  kfrags. Does NOT give the scope key.
  R4 DATA_KEY held             -> that one record is openable.
  R5 PLAINTEXT held            -> that record's content is known (and stays known forever).

Openable(C) = union of records produced by closure. Authorized(C) = records ever
intentionally authorized to any recipient in C by time t. Exposure counts openable records
OUTSIDE authorized -- split into past (already produced) and future (not yet produced, but
openable because an exposed scope key covers the whole scope range).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set, Tuple
from .types import (Material, Held, Scope, Record, Grant, GrantId, ProxyId, RecipientId,
                    Seq, StreamId)
from .events import (Event, GrantIssued, KFragInstalled, CFragProduced, CorruptProxy,
                     CorruptRecipient, DiscloseDataKey, DiscloseScopeKey, DisclosePlaintext,
                     RecordProduced, GrantRevoked, is_observable)
from .authorization import AuthorizationState, fold_authorization


@dataclass
class CoalitionKnowledge:
    """K_t(C): everything coalition C has retained by time t. Monotone in t."""
    label: str
    held: Set[Held] = field(default_factory=set)
    corrupt_proxies: Set[ProxyId] = field(default_factory=set)
    corrupt_recipients: Set[RecipientId] = field(default_factory=set)
    # record of grants this coalition was ever intentionally authorized for (its recipients)
    authorized_grants: Set[GrantId] = field(default_factory=set)


def accumulate(events: List[Event], coalition: str, now: Optional[int] = None,
               auth: Optional[AuthorizationState] = None) -> CoalitionKnowledge:
    """Fold the FULL event stream (including ground-truth compromise) into K_t(C).

    Corruption is adaptive: when a proxy/recipient joins C, ALL of its material installed at
    ANY time (before or after) accumulates. We therefore do two passes: first discover who
    is in C by `now`, then gather every fragment/key ever routed to those parties by `now`.
    """
    if auth is None:
        auth = fold_authorization(events, now)
    K = CoalitionKnowledge(coalition)

    # pass 1: coalition membership and direct disclosures
    kfrag_holder: Dict[Tuple[GrantId, int], ProxyId] = {}
    for e in events:
        if now is not None and e.t > now:
            break
        if isinstance(e, CorruptProxy) and e.coalition == coalition:
            K.corrupt_proxies.add(e.proxy)
        elif isinstance(e, CorruptRecipient) and e.coalition == coalition:
            K.corrupt_recipients.add(e.recipient)
        elif isinstance(e, DiscloseScopeKey) and e.coalition == coalition:
            K.held.add(Held(Material.SCOPE_KEY, scope=e.scope))
        elif isinstance(e, DiscloseDataKey) and e.coalition == coalition:
            K.held.add(Held(Material.DATA_KEY, record=e.record))
        elif isinstance(e, DisclosePlaintext) and e.coalition == coalition:
            K.held.add(Held(Material.PLAINTEXT, record=e.record))

    # recipient secret keys of corrupted recipients
    for rcpt in K.corrupt_recipients:
        K.held.add(Held(Material.RECIPIENT_SK, recipient=rcpt))

    # pass 2: fragments routed to corrupted parties (adaptive: any time up to now)
    for e in events:
        if now is not None and e.t > now:
            break
        if isinstance(e, KFragInstalled) and e.proxy in K.corrupt_proxies:
            g = auth.live_grants.get(e.grant_id) or _find_grant(events, e.grant_id)
            K.held.add(Held(Material.KFRAG, grant=e.grant_id,
                            scope=(g.scope if g else None), index=e.index))
        elif isinstance(e, CFragProduced):
            # a cfrag is retained by C if the grant's recipient is corrupt (it was produced
            # for that recipient) -- conservative: also if any corrupt proxy produced it.
            g = auth.live_grants.get(e.grant_id) or _find_grant(events, e.grant_id)
            recip_corrupt = g is not None and g.recipient in K.corrupt_recipients
            if recip_corrupt:
                K.held.add(Held(Material.CFRAG, grant=e.grant_id,
                                scope=(g.scope if g else None), index=e.index, record=e.record))
        elif isinstance(e, GrantIssued):
            if e.grant.recipient in K.corrupt_recipients:
                K.authorized_grants.add(e.grant.grant_id)

    return K


def _find_grant(events: List[Event], gid: GrantId) -> Optional[Grant]:
    for e in events:
        if isinstance(e, GrantIssued) and e.grant.grant_id == gid:
            return e.grant
    return None


@dataclass
class Closure:
    """Result of Cl_hat(K_t(C)): which records C can open, and via which rule."""
    scope_keys: Set[Scope]                 # scopes whose owner key C holds/derived (R1,R2)
    records: Set[Record]                   # concrete already-produced records C can open
    reasons: Dict[Record, str]             # record -> rule id that opened it


def conservative_closure(K: CoalitionKnowledge, events: List[Event],
                         now: Optional[int] = None,
                         auth: Optional[AuthorizationState] = None) -> Closure:
    """Compute Cl_hat. Conservative: over-approximates openable records, never under."""
    if auth is None:
        auth = fold_authorization(events, now)
    scope_keys: Set[Scope] = set()

    # R1: directly held scope keys
    for h in K.held:
        if h.kind == Material.SCOPE_KEY and h.scope is not None:
            scope_keys.add(h.scope)

    # R2: t matching kfrags of a grant + that grant's recipient key -> scope key
    kfrags_by_grant: Dict[GrantId, Set[int]] = {}
    for h in K.held:
        if h.kind == Material.KFRAG and h.grant is not None and h.index is not None:
            kfrags_by_grant.setdefault(h.grant, set()).add(h.index)
    for gid, idxs in kfrags_by_grant.items():
        g = _find_grant(events, gid)
        if g is None:
            continue
        has_recip_key = Held(Material.RECIPIENT_SK, recipient=g.recipient) in K.held
        if has_recip_key and len(idxs) >= g.threshold:
            scope_keys.add(g.scope)        # Umbral: t shares + receiving_sk -> delegating_sk

    # records openable so far
    records: Set[Record] = set()
    reasons: Dict[Record, str] = {}

    # R4: disclosed data keys
    for h in K.held:
        if h.kind == Material.DATA_KEY and h.record is not None:
            records.add(h.record); reasons[h.record] = "R4:data_key"
    # R5: known plaintext
    for h in K.held:
        if h.kind == Material.PLAINTEXT and h.record is not None:
            records.add(h.record); reasons.setdefault(h.record, "R5:plaintext")
    # R3' (corrected per review R1): mixed-fragment local-transformation capability.
    # For a given grant g and a specific produced record (whose capsule is public), the
    # coalition can OPEN that record if it holds the recipient key AND can assemble >= t
    # cfrags for that capsule, where a cfrag is available at share index i if EITHER
    #   (a) it already holds a received cfrag for (g, record, i), OR
    #   (b) it holds the raw kfrag for (g, i): it locally transforms the public capsule with
    #       that kfrag to produce the cfrag at index i.
    # A raw kfrag at index i and a received cfrag at index i for the SAME record are the SAME
    # share and must count ONCE. So the available-share set is the UNION of received-cfrag
    # indices and held-kfrag indices for that grant.
    #
    # Because any produced record of the grant's scope within the grant's range has a public
    # capsule the coalition can transform, holding >= t kfrags of a grant (plus the recipient
    # key) already opens every such record. R3' therefore subsumes the old R3 and also the
    # pure-kfrag-per-record capability; the scope-key recovery (R2) remains the stronger rule
    # that additionally opens records NOT in the grant's range and FUTURE records.
    kfrag_idxs_by_grant: Dict[GrantId, Set[int]] = {}
    for h in K.held:
        if h.kind == Material.KFRAG and h.grant is not None and h.index is not None:
            kfrag_idxs_by_grant.setdefault(h.grant, set()).add(h.index)
    cfrag_idxs_by_rec: Dict[Tuple[GrantId, Record], Set[int]] = {}
    for h in K.held:
        if h.kind == Material.CFRAG and h.grant is not None and h.record is not None \
                and h.index is not None:
            cfrag_idxs_by_rec.setdefault((h.grant, h.record), set()).add(h.index)

    # candidate (grant, record) pairs: any record for which the coalition has a cfrag, OR any
    # produced record within a grant's range for which the coalition holds >= 1 kfrag.
    produced_all = _produced_records(events, now)
    candidates: Set[Tuple[GrantId, Record]] = set(cfrag_idxs_by_rec.keys())
    for gid, kidxs in kfrag_idxs_by_grant.items():
        g = _find_grant(events, gid)
        if g is None:
            continue
        for r in produced_all:
            if g.rng.contains(r):
                span = auth.scope_of(r)
                if span is not None and span.scope == g.scope:
                    candidates.add((gid, r))

    for (gid, rec) in candidates:
        g = _find_grant(events, gid)
        if g is None:
            continue
        if Held(Material.RECIPIENT_SK, recipient=g.recipient) not in K.held:
            continue
        available = set(cfrag_idxs_by_rec.get((gid, rec), set()))   # received cfrags (index i)
        available |= kfrag_idxs_by_grant.get(gid, set())            # locally-derivable (same i's merge)
        if len(available) >= g.threshold:
            records.add(rec); reasons.setdefault(rec, "R3':mixed_fragments")

    # R1/R2 consequence: every PRODUCED record of an exposed scope is openable
    produced_records = _produced_records(events, now)
    for r in produced_records:
        span = auth.scope_of(r)
        if span is not None and span.scope in scope_keys:
            records.add(r); reasons.setdefault(r, "R1/R2:scope_key")

    return Closure(scope_keys=scope_keys, records=records, reasons=reasons)


def _produced_records(events: List[Event], now: Optional[int]) -> List[Record]:
    out = []
    for e in events:
        if now is not None and e.t > now:
            break
        if isinstance(e, RecordProduced):
            out.append(e.record)
    return out


@dataclass
class Exposure:
    past: float            # weight of openable PRODUCED records outside authorization
    future_scopes: Set[Scope]   # exposed scopes still active (future records will be exposed)
    past_records: Set[Record]
    detail: Dict[str, float] = field(default_factory=dict)


def _production_times(events: List[Event], now: Optional[int]) -> Dict[Record, int]:
    """Map each produced record to the logical time it was first produced."""
    out: Dict[Record, int] = {}
    for e in events:
        if now is not None and e.t > now:
            break
        if isinstance(e, RecordProduced) and e.record not in out:
            out[e.record] = e.t
    return out


def authorized_records_of(K: CoalitionKnowledge, events: List[Event],
                          now: Optional[int], auth: AuthorizationState) -> Set[Record]:
    """Endpoint historical authorization: a valid reading time must exist by the cutoff.

    A record may predate grant issuance; delayed retrieval becomes authorized once the
    grant actually becomes live. Never-live future/revoked grants confer no exemption.
    This is not an irreversible disclosure ledger: later grants can reduce endpoint exposure.
    """
    prod_t = _production_times(events, now)
    cutoff = now if now is not None else max((e.t for e in events), default=-1)
    authed: Set[Record] = set()
    for e in events:
        if now is not None and e.t > now:
            break
        if isinstance(e, GrantIssued) and e.grant.recipient in K.corrupt_recipients:
            g = e.grant
            # A historical read must have been possible at SOME time by this cutoff.
            # Earlier records may be read once a later grant goes live; a never-live
            # future or preemptively revoked grant grants no historical exemption.
            start_t = max(e.t, g.valid_from)
            end_t = cutoff if g.valid_to is None else min(cutoff, g.valid_to)
            rev_t = auth.revoked.get(g.grant_id)
            if rev_t is not None:
                # Logical event times are integers and strictly ordered. Revocation
                # removes authority at its event; valid_to is inclusive.
                end_t = min(end_t, rev_t - 1)
            for r, t_prod in prod_t.items():
                if not g.rng.contains(r):
                    continue
                span = auth.scope_of(r)
                if span is None or span.scope != g.scope:
                    continue
                if max(start_t, t_prod) <= end_t:
                    authed.add(r)
    return authed


def exposure(K: CoalitionKnowledge, events: List[Event], now: Optional[int],
             weights: Dict[Record, float], auth: Optional[AuthorizationState] = None) -> Exposure:
    """X_t(C): collateral exposure = openable records outside ever-authorized, split into
    cumulative-past (produced) and future (exposed active scopes).

    Owner-root compromise is handled by the caller: if the owner root is in C, every scope
    key is exposed and this bound is not small -- do not call this to claim a small bound
    in that case (see management_problem.md)."""
    if auth is None:
        auth = fold_authorization(events, now)
    cl = conservative_closure(K, events, now, auth)
    authed = authorized_records_of(K, events, now, auth)

    past_records = {r for r in cl.records if r not in authed}
    past = sum(weights.get(r, 1.0) for r in past_records)

    # future: an exposed scope that is still ACTIVE (end_seq is None) will cover records not
    # yet produced; those are future collateral exposure iff they would not be authorized.
    future_scopes: Set[Scope] = set()
    for scope in cl.scope_keys:
        spans = auth.scope_spans.get(scope.stream, [])
        for span in spans:
            if span.scope == scope and span.end_seq is None:
                future_scopes.add(scope)
    return Exposure(past=past, future_scopes=future_scopes, past_records=past_records,
                    detail={"n_past_records": float(len(past_records)),
                            "n_exposed_scopes": float(len(cl.scope_keys)),
                            "n_future_active_scopes": float(len(future_scopes))})
