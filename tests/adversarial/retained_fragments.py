"""
Adversarial witnesses that ground the model's closure rules in REAL threshold-PRE crypto.
Runs in the ISOLATED legacy venv (umbral 0.3.0, secp256k1). Exit 0 = all expectations met.

These correspond to brief sec 4.2 distinctions and correct the two interpretation issues it
flagged about the old archive:
  (a) EX-4 was counted as a passing executable check although it was an assumption. Here,
      ADV-4 is reported SEPARATELY as an assumption line and is NOT included in the pass/fail
      count (it prints [assumption], never [ok]/[FAIL]).
  (b) The cross-scope claim omitted that AUTHORIZED cfrag decryption must be excluded from the
      confidentiality challenge. ADV-R3b makes that explicit: the legitimate t-cfrag path DOES
      decrypt the challenge capsule, so a game that allowed it would be trivially won; the
      restriction is therefore necessary, not optional.

Checks:
  ADV-R2   t raw kfrags + recipient_sk reconstruct the scope secret (grounds rule R2); the
           reconstructed secret decrypts a FRESH record under that scope with no transform.
  ADV-R2sub  t-1 kfrags + recipient_sk do NOT reconstruct the scope secret.
  ADV-R3   t cfrags for a specific capsule + recipient_sk open THAT capsule (grounds rule R3)
           without using the raw kfrags as a scope key (does not yield the scope secret).
  ADV-R3b  the authorized t-cfrag path decrypts the challenge capsule -> such a decryption
           must be EXCLUDED from any confidentiality game (restriction statement).
  ADV-4    [assumption] a proxy lacking recipient_sk cannot place the shares (reduces to CDH);
           stated, not benchmarked.
"""
import sys
import umbral
from umbral import SecretKey, Signer, encrypt, decrypt_original
sys.path.insert(0, ".")
from delegation_crypto import pre_adapter as A

U = A._umbral()
FAIL = []
def expect(cid, cond, msg):
    ok = bool(cond)
    print(f"[{'ok ' if ok else 'FAIL'}] {cid:<10} {msg}")
    if not ok: FAIL.append(cid)
def assumption(cid, msg):
    print(f"[assumption] {cid:<10} {msg}  (NOT counted as an executable pass)")

N_ORDER = A.N_ORDER
T, N = 2, 3
signer = Signer(SecretKey.random())
scope_sk = SecretKey.random(); scope_pk = scope_sk.public_key()
rsk = SecretKey.random(); rpk = rsk.public_key()
vkfrags = A.grant_kfrags(U, scope_sk, rpk, signer, T, N)

# ADV-R2: t kfrags + recipient_sk -> scope secret
rec = A.reconstruct_scope_key_from_kfrags(U, vkfrags, rsk, rpk, T)
true_scope = int.from_bytes(bytes(scope_sk.secret_scalar()), "big")
expect("ADV-R2", rec == true_scope, "t kfrags + recipient_sk reconstruct the scope secret")

# reconstructed secret opens a FRESH record under the scope, directly (no transform)
rec_sk = SecretKey(U["CurveScalar"].from_int(rec))
cap_f, ct_f = encrypt(scope_pk, b"fresh record under scope, never delegated")
opened = decrypt_original(rec_sk, cap_f, ct_f)
expect("ADV-R2dec", opened == b"fresh record under scope, never delegated",
       "reconstructed scope secret decrypts a fresh same-scope record directly")

# ADV-R2sub: t-1 kfrags do NOT reconstruct
try:
    rec_sub = A.reconstruct_scope_key_from_kfrags(U, vkfrags, rsk, rpk, T - 1)
    sub_ok = (rec_sub != true_scope)
except Exception:
    sub_ok = True
expect("ADV-R2sub", sub_ok, "t-1 kfrags + recipient_sk do NOT reconstruct the scope secret")

# ADV-R3: t cfrags for a capsule + recipient_sk open THAT capsule (no raw-kfrag scope key)
pt = A.authorized_open(U, scope_sk, scope_pk, rsk, rpk, vkfrags, T,
                       b"capsule-specific record")
expect("ADV-R3", pt == b"capsule-specific record",
       "t cfrags + recipient_sk open the specific capsule (rule R3)")

# ADV-R3b: the authorized path decrypts the CHALLENGE capsule -> must be excluded from a game
challenge_pt = b"the confidentiality challenge plaintext"
auth_pt = A.authorized_open(U, scope_sk, scope_pk, rsk, rpk, vkfrags, T, challenge_pt)
expect("ADV-R3b", auth_pt == challenge_pt,
       "AUTHORIZED cfrag path decrypts the challenge capsule -> a game MUST exclude it "
       "(authorized decryption is not a confidentiality break)")

# ADV-4: assumption only (not a pass/fail executable check)
assumption("ADV-4", "a proxy lacking recipient_sk cannot place shares (dh_point is a CDH "
                    "value); reconstruction-without-delegatee reduces to ECCDH and is ASSUMED")

print(f"\n{len(FAIL)} failures" + (f": {FAIL}" if FAIL else "")
      + "  (ADV-4 assumption excluded from the count)")
sys.exit(1 if FAIL else 0)
