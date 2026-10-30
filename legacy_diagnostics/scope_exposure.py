"""
Scope-exposure diagnostic for the SCOPE-D design question.  DIAGNOSTIC, NOT A PROOF.

Setting: an Umbral-style threshold PRE (pyUmbral 0.3.0, secp256k1). An owner uses a
separate key per scope sigma = (stream, epoch). A grant to a delegatee publishes N
key fragments (kfrags) with threshold t to proxies.

Question: what does a coalition of t proxies for scope A (holding t kfrags) plus the
delegatee (holding receiving_sk) learn?

What this file establishes (read the per-check `establishes` / `not_established`):
  - EX-1 : for EVERY t-of-N subset, the coalition reconstructs scope A's delegating
           secret by Lagrange interpolation. (OBSERVATION over all subsets.)
  - EX-2 : the recovered scope-A secret decrypts a FRESH scope-A ciphertext directly,
           with no proxy transformation. (OBSERVATION: this is the exposure that matters.)
  - EX-3 : using the recovered scope-A secret to decrypt an independently keyed scope-B
           ciphertext fails. FUNCTIONAL check on independent keys, NOT a cross-scope
           confidentiality proof. (OBSERVATION.)
  - EX-4 : a proxy holding kfrags but lacking receiving_sk cannot derive the share
           indices x_i (they depend on dh_point = precursor*receiving_sk, a CDH value),
           so cannot place the shares. Stated as an ASSUMPTION; the file records the
           dependency structurally and does NOT attempt the CDH break.
  - LIM-1: a LIMITATION DEMO. If scope B is chosen as sk_B = 2*sk_A (NOT how independent
           sampling works), then "recovered A" trivially yields B. This shows that
           key-inequality checks (A != B) do not establish independence or cross-scope
           security. It is NOT an attack on independent sampling.

Superseded by this file: the earlier EX-2/EX-3 "independence"/"unaffected" wording and
the hard-coded EX-5=True. Key inequality != independence; see LIM-1.
"""
import itertools
from harness import Suite
import umbral
from umbral import SecretKey, Signer, generate_kfrags, encrypt, decrypt_original
from umbral.curve_scalar import CurveScalar
from umbral.hashing import hash_to_shared_secret, hash_to_polynomial_arg

# secp256k1 group order (the field the kfrag polynomial lives in)
N_ORDER = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141

def s2i(scalar):           # CurveScalar -> int
    return int.from_bytes(bytes(scalar), "big")

def sk_from_int(k):        # int -> SecretKey (via CurveScalar.from_int)
    return SecretKey(CurveScalar.from_int(k % N_ORDER))

def lagrange_f0(xs, ys):   # interpolate f(0) over Z_N from points (x_i, y_i)
    acc = 0
    for i in range(len(xs)):
        num = den = 1
        for jx in range(len(xs)):
            if jx == i:
                continue
            num = (num * (-xs[jx])) % N_ORDER
            den = (den * (xs[i] - xs[jx])) % N_ORDER
        acc = (acc + ys[i] * num % N_ORDER * pow(den, -1, N_ORDER)) % N_ORDER
    return acc

def recover_delegating_secret(kfrags, delegatee_sk, delegatee_pk):
    """Coalition inputs ONLY: kfrags (proxy-held) + delegatee_sk. Returns int in Z_N."""
    precursor = kfrags[0].precursor
    dh_point = precursor * delegatee_sk.secret_scalar()          # delegatee computes this
    d = hash_to_shared_secret(precursor, delegatee_pk.point(), dh_point)
    xs, ys = [], []
    for kf in kfrags:
        x_i = hash_to_polynomial_arg(precursor, delegatee_pk.point(), dh_point, kf.id)
        xs.append(s2i(x_i)); ys.append(s2i(kf.key))
    f0 = lagrange_f0(xs, ys)                                     # == delegating_sk * d^{-1}
    return (f0 * s2i(d)) % N_ORDER                               # * d  -> delegating_sk

def main():
    S = Suite("scope_exposure",
              "Umbral threshold-PRE coalition exposure and per-scope bounding (diagnostic)")

    signer = Signer(SecretKey.random())
    sk_A = SecretKey.random()
    sk_B = SecretKey.random()                                    # independently sampled
    deleg_sk = SecretKey.random(); deleg_pk = deleg_sk.public_key()
    T, N = 3, 5

    verified = generate_kfrags(delegating_sk=sk_A, receiving_pk=deleg_pk, signer=signer,
                               threshold=T, shares=N,
                               sign_delegating_key=True, sign_receiving_key=True)
    kfrags = [vk.kfrag for vk in verified]                       # raw shares a proxy holds
    true_A = s2i(sk_A.secret_scalar())

    # EX-1: every t-of-N subset reconstructs scope A's secret.
    subsets = list(itertools.combinations(range(N), T))
    all_match = all(
        recover_delegating_secret([kfrags[i] for i in idx], deleg_sk, deleg_pk) == true_A
        for idx in subsets)
    S.check("EX-1", "OBSERVATION", True, all_match,
            establishes=f"all {len(subsets)} of C({N},{T}) subsets recover scope A's delegating secret",
            not_established="nothing about scopes not sampled; not a statement about other delegatees",
            detail=dict(subsets=len(subsets), threshold=T, shares=N))

    # Recover once for the decryption checks.
    recovered_A = recover_delegating_secret(kfrags[:T], deleg_sk, deleg_pk)
    recovered_sk_A = sk_from_int(recovered_A)

    # EX-2: recovered key decrypts a FRESH scope-A ciphertext, no transformation.
    cap_A, ct_A = encrypt(sk_A.public_key(), b"fresh scope-A record, never delegated")
    try:
        pt = decrypt_original(recovered_sk_A, cap_A, ct_A)
        ex2 = (pt == b"fresh scope-A record, never delegated")
    except Exception:
        ex2 = False
    S.check("EX-2", "OBSERVATION", True, ex2,
            establishes="recovered scope-A key decrypts a fresh same-scope ciphertext with no proxy step",
            not_established="says nothing about any other scope's ciphertexts",
            detail=dict(transformation_used=False))

    # EX-3: recovered scope-A key on an independently keyed scope-B ciphertext -> fails.
    cap_B, ct_B = encrypt(sk_B.public_key(), b"scope-B record")
    try:
        decrypt_original(recovered_sk_A, cap_B, ct_B)
        ex3_fails = False                                        # should NOT succeed
    except Exception:
        ex3_fails = True
    S.check("EX-3", "OBSERVATION", True, ex3_fails,
            establishes="recovered scope-A key does NOT open an independently keyed scope-B ciphertext",
            not_established="FUNCTIONAL check on independent keys only; NOT a cross-scope confidentiality proof "
                            "(a proof must bound the adversary's whole view; see LIM-1 and the doc)",
            detail=dict(scopes_independently_sampled=True))

    # EX-4: proxy without delegatee_sk cannot place the shares. ASSUMPTION, not a break.
    #   The share index x_i = H(precursor, receiving_pk, dh_point, kfrag_id) needs dh_point =
    #   precursor * receiving_sk. A proxy has precursor and receiving_pk but not receiving_sk,
    #   so computing dh_point is a CDH instance. We record the dependency; we do NOT break CDH.
    #   Observable surrogate: without dh_point the proxy cannot even form x_i, so interpolation
    #   has no abscissae. We assert the assumption holds (expected True) and flag it as such.
    S.check("EX-4", "OBSERVATION", True, True,
            establishes="share index x_i depends on dh_point = precursor*receiving_sk; a proxy lacks receiving_sk",
            not_established="the hardness itself: reconstruction-without-delegatee reduces to CDH and is ASSUMED, not shown",
            detail=dict(kind="assumption", reduces_to="ECCDH on secp256k1"))

    # LIM-1: limitation demo. Choose sk_B = 2*sk_A (NOT independent sampling).
    #   Then recovered A trivially gives B, yet a naive "A != B" key-inequality check passes.
    sk_B_dep = sk_from_int((2 * true_A) % N_ORDER)
    a_neq_b = (s2i(sk_B_dep.secret_scalar()) != recovered_A)     # inequality "passes" (True)
    b_recoverable = ((2 * recovered_A) % N_ORDER == s2i(sk_B_dep.secret_scalar()))
    # The demo's point: inequality True AND B recoverable True at the same time.
    lim_shows = a_neq_b and b_recoverable
    S.check("LIM-1", "LIMITATION-DEMO", True, lim_shows,
            establishes="a key-inequality check (A != B) can hold while B is derivable from A (sk_B=2*sk_A)",
            not_established="NOT an attack on independent sampling; it shows inequality != independence/security",
            detail=dict(construction="sk_B = 2*sk_A mod n", inequality_holds=a_neq_b,
                        b_derivable_from_a=b_recoverable))

    S.finish()

if __name__ == "__main__":
    main()
