"""
Irreversible disclosure ledger (P2, review step 2).

The endpoint exposure measure X_t(C) in closure.py answers "what is collateral RIGHT NOW": it is
an ENDPOINT measure, and a later grant can make a previously-leaked record authorized, reducing
it. That is the wrong quantity for a CUMULATIVE leakage claim: once a coalition could open an
unauthorized record, that disclosure happened and cannot be undone by a subsequent grant.

This ledger records, for each (coalition, record), the FIRST logical time the record was both
(a) openable by the coalition's conservative closure and (b) NOT authorized to the coalition at
that time. Later authorization never erases a recorded first-disclosure. The endpoint measure is
preserved separately as a diagnostic.

Subtlety the review calls out: legitimate DELAYED reading of older records must stay authorized.
A record produced before a grant becomes live is authorized once the grant is live (closure's
authorized_records_of already models this). The ledger uses that same authorization notion at
EACH step, so a record that becomes openable only at a time when it is ALREADY authorized (e.g.,
the coalition legitimately holds a live grant covering it) is never recorded as a disclosure.

This module scans the observable+evaluation history step by step. It is an evaluation/soundness
tool (it reads realized corruption to compute what actually leaked), NOT a controller input.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from .types import Record, RecipientId
from .events import Event, RecordProduced, GrantIssued, GrantRevoked
from .authorization import fold_authorization
from .closure import accumulate, conservative_closure, authorized_records_of


@dataclass
class DisclosureEntry:
    record: Record
    first_time: int            # logical time of first unauthorized openability
    coalition: str


@dataclass
class DisclosureLedger:
    coalition: str
    entries: Dict[Record, DisclosureEntry] = field(default_factory=dict)

    def record_weight(self, weights: Dict[Record, float]) -> float:
        return sum(weights.get(r, 1.0) for r in self.entries)

    def disclosed(self) -> Set[Record]:
        return set(self.entries)


def _event_times(events: List[Event], now: Optional[int]) -> List[int]:
    ts = sorted({e.t for e in events if (now is None or e.t <= now)})
    return ts


def build_ledger(events: List[Event], coalition: str, now: Optional[int],
                 weights: Optional[Dict[Record, float]] = None) -> DisclosureLedger:
    """Scan history; at each distinct event time t, compute the coalition's openable-but-
    unauthorized records and record any not already in the ledger. Monotone: entries are never
    removed. The first_time is the earliest t at which the record was openable AND unauthorized.
    """
    ledger = DisclosureLedger(coalition)
    for t in _event_times(events, now):
        auth = fold_authorization(events, t)
        K = accumulate(events, coalition, t, auth)
        cl = conservative_closure(K, events, t, auth)
        authed = authorized_records_of(K, events, t, auth)
        for r in cl.records:
            if r in authed:
                continue                       # authorized at this step -> not a disclosure
            if r not in ledger.entries:
                ledger.entries[r] = DisclosureEntry(record=r, first_time=t, coalition=coalition)
    return ledger


def ledger_never_decreases(events: List[Event], coalition: str,
                           checkpoints: List[int]) -> bool:
    """Property check: the cumulative disclosed set is monotone non-decreasing across time."""
    prev: Set[Record] = set()
    for t in sorted(checkpoints):
        cur = build_ledger(events, coalition, t).disclosed()
        if not prev <= cur:
            return False
        prev = cur
    return True
