"""
Thin adapter over a real threshold-PRE backend (pyUmbral 0.3.0, secp256k1).

IMPORTANT ENVIRONMENT NOTE. umbral 0.3.0 requires cryptography ~=3.0, which conflicts with
the HPKE baseline's cryptography 43. The two never run in the same process:
  - the measured HPKE service path uses the production venv (cryptography 43, no umbral);
  - this adapter and the adversarial PRE witnesses use the ISOLATED legacy venv
    (cryptography 3.4.8 + umbral 0.3.0), invoked as a separate process.
This mirrors the brief's instruction to keep the old diagnostic environment isolated and
not to choose a production stack merely because the diagnostics run.

The adapter exists to (a) perform real kfrag/cfrag operations so the abstract closure rules
in delegation_model.closure are grounded in the actual construction, and (b) expose exactly
the retained-capability facts the model reasons about:
  - reconstruct_scope_key_from_kfrags : t kfrags + recipient_sk -> delegating (scope) secret
  - open_with_cfrags                  : t cfrags + recipient_sk -> plaintext of ONE capsule
  - authorized_open                   : the normal t-cfrag path (used to state the game's
                                        authorized-decryption restriction explicitly)
"""
from __future__ import annotations
from typing import List, Tuple

# imported lazily so this file can be imported for docs without umbral present
def _umbral():
    import umbral
    from umbral import SecretKey, Signer, generate_kfrags, encrypt, decrypt_original, \
        decrypt_reencrypted, reencrypt
    from umbral.curve_scalar import CurveScalar
    from umbral.hashing import hash_to_shared_secret, hash_to_polynomial_arg
    return dict(umbral=umbral, SecretKey=SecretKey, Signer=Signer,
                generate_kfrags=generate_kfrags, encrypt=encrypt,
                decrypt_original=decrypt_original, decrypt_reencrypted=decrypt_reencrypted,
                reencrypt=reencrypt, CurveScalar=CurveScalar,
                hash_to_shared_secret=hash_to_shared_secret,
                hash_to_polynomial_arg=hash_to_polynomial_arg)

N_ORDER = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141


def new_scope_key(U):
    return U["SecretKey"].random()


def grant_kfrags(U, scope_sk, recipient_pk, signer, threshold, shares):
    return U["generate_kfrags"](delegating_sk=scope_sk, receiving_pk=recipient_pk,
                                signer=signer, threshold=threshold, shares=shares,
                                sign_delegating_key=True, sign_receiving_key=True)


def authorized_open(U, scope_sk, scope_pk, recipient_sk, recipient_pk, verified_kfrags,
                    threshold, plaintext: bytes) -> bytes:
    """The NORMAL authorized path: encrypt to scope, transform with t kfrags, recipient
    decrypts the re-encrypted capsule. This is legitimate decryption and is exactly what a
    confidentiality game must EXCLUDE from the challenge (brief sec 4.2)."""
    capsule, ct = U["encrypt"](scope_pk, plaintext)
    cfrags = [U["reencrypt"](capsule=capsule, kfrag=kf) for kf in verified_kfrags[:threshold]]
    pt = U["decrypt_reencrypted"](receiving_sk=recipient_sk, delegating_pk=scope_pk,
                                  capsule=capsule, verified_cfrags=cfrags, ciphertext=ct)
    return pt


def reconstruct_scope_key_from_kfrags(U, verified_kfrags, recipient_sk, recipient_pk,
                                      threshold) -> int:
    """Coalition capability behind closure rule R2: t raw kfrags + recipient_sk recover the
    scope (delegating) secret as an integer mod n, by Lagrange interpolation of the kfrag
    polynomial constant term (= delegating_sk * d^{-1}) times the reconstructible d."""
    kfrags = [vk.kfrag for vk in verified_kfrags[:threshold]]
    precursor = kfrags[0].precursor
    dh_point = precursor * recipient_sk.secret_scalar()
    d = U["hash_to_shared_secret"](precursor, recipient_pk.point(), dh_point)
    def s2i(s): return int.from_bytes(bytes(s), "big")
    xs, ys = [], []
    for kf in kfrags:
        x = U["hash_to_polynomial_arg"](precursor, recipient_pk.point(), dh_point, kf.id)
        xs.append(s2i(x)); ys.append(s2i(kf.key))
    acc = 0
    for i in range(len(xs)):
        num = den = 1
        for j in range(len(xs)):
            if j == i: continue
            num = (num * (-xs[j])) % N_ORDER
            den = (den * (xs[i] - xs[j])) % N_ORDER
        acc = (acc + ys[i] * num % N_ORDER * pow(den, -1, N_ORDER)) % N_ORDER
    return (acc * s2i(d)) % N_ORDER
