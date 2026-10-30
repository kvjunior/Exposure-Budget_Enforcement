"""
Motivation witness (brief sec 4.3 / step 3): a minimal pair of histories H_safe and
H_exposed that are INDISTINGUISHABLE by current permissions (the ACL at `now` is identical)
yet differ in retained cryptographic capability and therefore in which future actions are
safe. This is a motivation artifact, not a claim that cached-key risk was unknown.

Both histories:
  - stream "g", epoch 0 scope A active from seq 0; records g:0 and g:1 produced.
  - a grant G1 to recipient "R" for range [0,2) of scope A, threshold t=2 of N=3,
    proxies p0,p1,p2; grant is later REVOKED at the same time in both.
  So at `now`, in BOTH histories, R is NOT currently authorized for anything (grant revoked)
  and no one else is authorized -> identical current ACL (empty).

They differ only in retained material held by coalition "C" (cloud + R):
  H_safe   : C corrupted ONE proxy (p0) and R. One kfrag < threshold -> C holds a sub-threshold
             fragment set. C cannot reconstruct the scope key. Past authorized records were
             g:0,g:1 (while the grant was live) -> knowing those is NOT collateral exposure.
             No future records are exposed.
  H_exposed: C corrupted TWO proxies (p0,p1) and R. Two kfrags == threshold + recipient key
             -> C reconstructs scope A's key (closure rule R2). Because scope A is STILL the
             active scope, every FUTURE record on g is exposed too. Revoking G1 did not help.

Consequence for management: in H_exposed, activating a fresh scope (epoch roll) BEFORE
producing more records on g is necessary to stop future exposure; in H_safe it is not.
Same ACL, different safe action set. That gap is the thing the controller must act on.
"""
from __future__ import annotations
from typing import Dict, List


def _base_events() -> List[dict]:
    """Events common to both histories, as JSON-ish dicts (reference representation)."""
    return [
        {"t": 0, "type": "StreamAuthorized", "owner": "O", "stream": "g", "producer": "D"},
        {"t": 1, "type": "ScopeActivated", "owner": "O", "scope": ["g", 0],
         "scope_key_id": "g.e0.k0", "start_seq": 0},
        {"t": 2, "type": "RecordProduced", "record": ["g", 0], "weight": 1.0},
        {"t": 3, "type": "RecordProduced", "record": ["g", 1], "weight": 1.0},
        {"t": 4, "type": "GrantIssued", "grant": {
            "grant_id": "G1", "owner": "O", "recipient": "R", "scope": ["g", 0],
            "rng": ["g", 0, 2], "threshold": 2, "shares": 3,
            "proxies": ["p0", "p1", "p2"], "valid_from": 4, "valid_to": None}},
        {"t": 5, "type": "KFragInstalled", "grant_id": "G1", "proxy": "p0", "index": 0},
        {"t": 6, "type": "KFragInstalled", "grant_id": "G1", "proxy": "p1", "index": 1},
        {"t": 7, "type": "KFragInstalled", "grant_id": "G1", "proxy": "p2", "index": 2},
        {"t": 8, "type": "GrantRevoked", "grant_id": "G1"},   # revoked in BOTH
    ]


def history_safe() -> List[dict]:
    ev = _base_events()
    ev += [
        {"t": 9, "type": "CorruptRecipient", "recipient": "R", "coalition": "C"},
        {"t": 10, "type": "CorruptProxy", "proxy": "p0", "coalition": "C"},  # ONE proxy only
    ]
    return ev


def history_exposed() -> List[dict]:
    ev = _base_events()
    ev += [
        {"t": 9, "type": "CorruptRecipient", "recipient": "R", "coalition": "C"},
        {"t": 10, "type": "CorruptProxy", "proxy": "p0", "coalition": "C"},
        {"t": 11, "type": "CorruptProxy", "proxy": "p1", "coalition": "C"},  # TWO proxies == t
    ]
    return ev


NOW = 11   # observation cutoff for both (the extra corrupt event in safe has no t=11)


# ============================================================================================
# Review R4: an ONLINE-POLICY decision witness. The original safe/exposed pair differs only in
# hidden corruption, so it is kept as a NON-INTERFERENCE test (identical observations => identical
# decisions). A policy cannot act on it. Here we add a pair with the SAME current ACL but
# DIFFERENT OBSERVABLE histories, under the SAME declared coalition family, so a history-aware
# online policy CAN safely distinguish them from observable information alone.
#
# Both histories H_lowobs and H_highobs:
#   - stream g, scope A active from seq 0; records g:0, g:1 produced.
#   - a grant G1 to recipient R over [0,2) of scope A, t=2 of N=3, later REVOKED.
#   => identical current ACL at NOW_D (empty; grant revoked).
# They differ in OBSERVABLE installation history:
#   H_lowobs : only ONE kfrag of G1 was ever installed (to p0). From observable history + the
#              public family {C = cloud+R}, the worst-case POSSIBLE retained share set is 1 < t,
#              so no scope-key exposure is POSSIBLE. Admitting more work on scope A is safe.
#   H_highobs: TWO kfrags of G1 were installed (to p0, p1). From observable history + the same
#              family, the worst-case POSSIBLE retained set reaches t, so scope A COULD be
#              exposed. A history-aware controller should roll a fresh scope before producing
#              more records on g.
# No corruption events appear in either history: the distinction is computed CONSERVATIVELY from
# what the declared family COULD retain given the observable installations, not from realized
# compromise.

def _base_events_D():
    return [
        {"t": 0, "type": "StreamAuthorized", "owner": "O", "stream": "g", "producer": "D"},
        {"t": 1, "type": "ScopeActivated", "owner": "O", "scope": ["g", 0],
         "scope_key_id": "g.e0.k0", "start_seq": 0},
        {"t": 2, "type": "RecordProduced", "record": ["g", 0], "weight": 1.0},
        {"t": 3, "type": "RecordProduced", "record": ["g", 1], "weight": 1.0},
        {"t": 4, "type": "GrantIssued", "grant": {
            "grant_id": "G1", "owner": "O", "recipient": "R", "scope": ["g", 0],
            "rng": ["g", 0, 2], "threshold": 2, "shares": 3,
            "proxies": ["p0", "p1", "p2"], "valid_from": 4, "valid_to": None}},
    ]

def history_lowobs():
    ev = _base_events_D()
    ev += [
        {"t": 5, "type": "KFragInstalled", "grant_id": "G1", "proxy": "p0", "index": 0},
        {"t": 6, "type": "GrantRevoked", "grant_id": "G1"},
    ]
    return ev

def history_highobs():
    ev = _base_events_D()
    ev += [
        {"t": 5, "type": "KFragInstalled", "grant_id": "G1", "proxy": "p0", "index": 0},
        {"t": 6, "type": "KFragInstalled", "grant_id": "G1", "proxy": "p1", "index": 1},
        {"t": 7, "type": "GrantRevoked", "grant_id": "G1"},
    ]
    return ev

NOW_D = 7
