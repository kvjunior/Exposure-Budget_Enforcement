"""
Actual cryptography for the measured path: RFC 9180 HPKE (via `hpke` 0.3.2, backed by
`cryptography` 43) for key-envelope wrapping, Ed25519 for origin signatures, AES-256-GCM
for the record payload. No hand-rolled curve math. No PRE here -- PRE lives in pre_adapter.

Record format (immutable signed origin envelope + separable key envelope):
  hdr    = canonical(version, suite, producer, stream, seq, scope_key_id, nonce)
  ct     = AES-256-GCM(dek, payload, aad=H(hdr))           # payload ciphertext
  edek   = HPKE.seal(recipient_or_owner_pk, info, aad=H(hdr), dek)  # key envelope
  sig    = Ed25519(producer_sk, "rec-sig-v1" || H(hdr) || H(ct))
Rewrapping (owner-mediated baseline) replaces ONLY edek for a new recipient key; hdr, ct,
sig are preserved byte-for-byte. AEAD nonce is derived per record (deterministic from dek
and H(hdr)) so a fresh dek gives a fresh nonce with no sender state.
"""
from __future__ import annotations
import hashlib, json, os
from dataclasses import dataclass
from typing import Optional, Tuple
from cryptography.hazmat.primitives.asymmetric import ed25519, ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import serialization
from hpke import Suite__DHKEM_P256_HKDF_SHA256__HKDF_SHA256__AES_256_GCM as HPKE_SUITE

VERSION = 1
SUITE = "HPKE-P256-SHA256-AES256GCM/Ed25519/AES256GCM"


def h(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def canonical_hdr(producer: str, stream: str, seq: int, scope_key_id: str, nonce: bytes) -> bytes:
    obj = {"v": VERSION, "suite": SUITE, "producer": producer, "stream": stream,
           "seq": seq, "scope_key_id": scope_key_id, "nonce": nonce.hex()}
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def derive_nonce(dek: bytes, hdr_hash: bytes) -> bytes:
    # 96-bit AEAD nonce, deterministic in (dek, hdr). Fresh dek => fresh nonce.
    return hashlib.sha256(b"nonce-v1" + dek + hdr_hash).digest()[:12]


@dataclass
class Envelope:
    hdr: bytes          # canonical header bytes
    ct: bytes           # payload ciphertext (AES-GCM)
    edek: bytes         # HPKE-sealed data key (the ONLY part rewrapping changes)
    enc: bytes          # HPKE encapsulated key
    sig: bytes          # Ed25519 origin signature
    recipient_fp: str   # fingerprint of the pk edek is sealed to (bookkeeping)

    def hdr_hash(self) -> bytes:
        return h(self.hdr)


def pk_fingerprint(pk) -> str:
    raw = pk.public_bytes(serialization.Encoding.X962,
                          serialization.PublicFormat.UncompressedPoint)
    return h(raw).hex()[:16]


def produce_record(producer_sk: ed25519.Ed25519PrivateKey, producer_id: str,
                   stream: str, seq: int, scope_key_id: str,
                   recipient_pk: ec.EllipticCurvePublicKey, payload: bytes) -> Envelope:
    dek = os.urandom(32)
    nonce_seed = os.urandom(16)
    hdr = canonical_hdr(producer_id, stream, seq, scope_key_id, nonce_seed)
    hh = h(hdr)
    aead_nonce = derive_nonce(dek, hh)
    ct = AESGCM(dek).encrypt(aead_nonce, payload, hh)
    info = b"dek-wrap-v1/" + scope_key_id.encode()
    enc, edek = HPKE_SUITE.seal(recipient_pk, info=info, aad=hh, message=dek)
    sig = producer_sk.sign(b"rec-sig-v1" + hh + h(ct))
    return Envelope(hdr=hdr, ct=ct, edek=edek, enc=enc, sig=sig,
                    recipient_fp=pk_fingerprint(recipient_pk))


def open_record(env: Envelope, recipient_sk: ec.EllipticCurvePrivateKey,
                producer_pk: ed25519.Ed25519PublicKey, scope_key_id: str) -> bytes:
    hh = env.hdr_hash()
    producer_pk.verify(env.sig, b"rec-sig-v1" + hh + h(env.ct))   # origin auth first
    info = b"dek-wrap-v1/" + scope_key_id.encode()
    dek = HPKE_SUITE.open(env.enc, recipient_sk, info=info, aad=hh, ciphertext=env.edek)
    aead_nonce = derive_nonce(dek, hh)
    return AESGCM(dek).decrypt(aead_nonce, env.ct, hh)


def rewrap_edek(env: Envelope, owner_sk: ec.EllipticCurvePrivateKey,
                new_recipient_pk: ec.EllipticCurvePublicKey, scope_key_id: str,
                owner_is_original_recipient: bool = True) -> Envelope:
    """Owner-mediated rewrap: recover dek with the owner's key, reseal to a new recipient.
    Preserves hdr, ct, sig byte-for-byte; replaces ONLY edek/enc. This is the non-PRE
    baseline: payload ciphertext is NOT re-encrypted or re-uploaded."""
    hh = env.hdr_hash()
    info = b"dek-wrap-v1/" + scope_key_id.encode()
    dek = HPKE_SUITE.open(env.enc, owner_sk, info=info, aad=hh, ciphertext=env.edek)
    enc2, edek2 = HPKE_SUITE.seal(new_recipient_pk, info=info, aad=hh, message=dek)
    return Envelope(hdr=env.hdr, ct=env.ct, edek=edek2, enc=enc2, sig=env.sig,
                    recipient_fp=pk_fingerprint(new_recipient_pk))


def gen_recipient_key() -> Tuple[ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey]:
    sk = ec.generate_private_key(ec.SECP256R1())
    return sk, sk.public_key()


def gen_signing_key() -> Tuple[ed25519.Ed25519PrivateKey, ed25519.Ed25519PublicKey]:
    sk = ed25519.Ed25519PrivateKey.generate()
    return sk, sk.public_key()
