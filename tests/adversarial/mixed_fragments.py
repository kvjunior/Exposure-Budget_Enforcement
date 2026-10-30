"""
R1 regression: the mixed-fragment capability must be in the closure, grounded in real Umbral.
Runs in the ISOLATED legacy venv (umbral 0.3.0). Exit 0 = all expectations met.

A 2-of-3 coalition holding ONE raw kfrag (index 0), ONE received cfrag at a DIFFERENT index
(index 1) for a specific record, and the recipient key, can locally transform the capsule with
its raw kfrag (yielding the index-0 cfrag), combine with the received index-1 cfrag, and
decrypt. The model must mark that record openable.

Guards:
  MIX-real   : real Umbral decrypts via [received cfrag(idx1), locally-made cfrag(idx0)].
  MIX-model  : conservative_closure includes the record (the R1 fix).
  MIX-ref    : the independent reference also includes it (both must be fixed, not just one).
  MIX-nodbl  : ONE raw kfrag + ONE received cfrag at the SAME index (both index 0) is ONE
               share, below threshold 2 -> record NOT openable (no double counting).
  MIX-incompat: a cfrag from a DIFFERENT grant does not combine to reach threshold.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "python"))
import umbral
from umbral import SecretKey, Signer, generate_kfrags, encrypt, reencrypt, decrypt_reencrypted
from delegation_model.types import Grant, Record, RecordRange, Scope
from delegation_model.events import (StreamAuthorized, ScopeActivated, RecordProduced,
                                     GrantIssued, KFragInstalled, CFragProduced,
                                     CorruptProxy, CorruptRecipient)
from delegation_model.closure import accumulate, conservative_closure
from reference import knowledge_closure as ref

FAIL = []
def expect(cid, cond, msg):
    ok = bool(cond); print(f"[{'ok ' if ok else 'FAIL'}] {cid:<12} {msg}")
    if not ok: FAIL.append(cid)

# --- real Umbral mixed-fragment decryption ---
owner = SecretKey.random(); recipient = SecretKey.random(); signer = Signer(SecretKey.random())
kfrags = generate_kfrags(owner, recipient.public_key(), signer, 2, 3, True, True)
msg = b"mixed-fragment witness"
capsule, ct = encrypt(owner.public_key(), msg)
received = reencrypt(capsule, kfrags[1])          # coalition RECEIVED this cfrag (index 1)
local = reencrypt(capsule, kfrags[0])             # coalition MAKES this one from raw kfrag 0
opened = decrypt_reencrypted(recipient, owner.public_key(), capsule, [received, local], ct)
expect("MIX-real", opened == msg, "real Umbral opens via received cfrag + locally-made cfrag")

# --- shared history: coalition holds raw kfrag idx0 + received cfrag idx1 + recipient key ---
sc = Scope("g", 0); rec = Record("g", 0)
g = Grant("G", "O", "R", sc, RecordRange("g", 0, 1), 2, 3, ("p0", "p1", "p2"), 0, None)
events = [StreamAuthorized(0, "O", "g", "D"), ScopeActivated(1, "O", sc, "k0", 0),
          RecordProduced(2, rec), GrantIssued(3, g),
          KFragInstalled(4, "G", "p0", 0), CFragProduced(5, "G", rec, 1),
          CorruptProxy(6, "p0", "C"), CorruptRecipient(7, "R", "C")]
cl = conservative_closure(accumulate(events, "C", 7), events, 7)
expect("MIX-model", rec in cl.records, "model closure includes the mixed-fragment record")

ev_json = [
    {"t": 0, "type": "StreamAuthorized", "owner": "O", "stream": "g", "producer": "D"},
    {"t": 1, "type": "ScopeActivated", "owner": "O", "scope": ["g", 0], "scope_key_id": "k0", "start_seq": 0},
    {"t": 2, "type": "RecordProduced", "record": ["g", 0], "weight": 1.0},
    {"t": 3, "type": "GrantIssued", "grant": {"grant_id": "G", "owner": "O", "recipient": "R",
        "scope": ["g", 0], "rng": ["g", 0, 1], "threshold": 2, "shares": 3,
        "proxies": ["p0", "p1", "p2"], "valid_from": 0, "valid_to": None}},
    {"t": 4, "type": "KFragInstalled", "grant_id": "G", "proxy": "p0", "index": 0},
    {"t": 5, "type": "CFragProduced", "grant_id": "G", "record": ["g", 0], "index": 1},
    {"t": 6, "type": "CorruptProxy", "proxy": "p0", "coalition": "C"},
    {"t": 7, "type": "CorruptRecipient", "recipient": "R", "coalition": "C"},
]
ref_out = ref.closure(ev_json, "C", 7)
expect("MIX-ref", ["g", 0] in [list(r) for r in ref_out["open_records"]],
       "independent reference also includes the mixed-fragment record")

# --- no double counting: raw kfrag idx0 + received cfrag idx0 = ONE share < threshold ---
events_same = [StreamAuthorized(0, "O", "g", "D"), ScopeActivated(1, "O", sc, "k0", 0),
               RecordProduced(2, rec), GrantIssued(3, g),
               KFragInstalled(4, "G", "p0", 0), CFragProduced(5, "G", rec, 0),  # SAME index 0
               CorruptProxy(6, "p0", "C"), CorruptRecipient(7, "R", "C")]
cl_same = conservative_closure(accumulate(events_same, "C", 7), events_same, 7)
expect("MIX-nodbl", rec not in cl_same.records,
       "same-index kfrag+cfrag counts as ONE share (below threshold) -> NOT openable")

# --- incompatible grant: a cfrag from grant H does not help open under grant G ---
h = Grant("H", "O", "R", sc, RecordRange("g", 0, 1), 2, 3, ("q0", "q1", "q2"), 0, None)
events_incompat = [StreamAuthorized(0, "O", "g", "D"), ScopeActivated(1, "O", sc, "k0", 0),
                   RecordProduced(2, rec), GrantIssued(3, g), GrantIssued(4, h),
                   KFragInstalled(5, "G", "p0", 0),         # one G kfrag (idx0)
                   CFragProduced(6, "H", rec, 1),           # cfrag from a DIFFERENT grant H
                   CorruptProxy(7, "p0", "C"), CorruptRecipient(8, "R", "C")]
cl_incompat = conservative_closure(accumulate(events_incompat, "C", 8), events_incompat, 8)
# Under G: only idx0 available (1 < 2). Under H: only the idx1 cfrag (1 < 2). Neither reaches t.
expect("MIX-incompat", rec not in cl_incompat.records,
       "cfrag from a different grant does not combine across grants to reach threshold")

print(f"\n{len(FAIL)} failures" + (f": {FAIL}" if FAIL else ""))
sys.exit(1 if FAIL else 0)
