"""
ADS-PRE diagnostic (self-contained).  DIAGNOSTIC, NOT security proofs, NOT performance code.

Self-contained: all curve arithmetic and the ADS-PRE algorithms are defined HERE, so running
this file prints only these checks and never re-prints obsolete tests or withdrawn conclusions
from any other module.

Versions of the manuscript analysed:
  V1  = T-IFS-21434-2025 (Mar 2025): Omega scalar; omega declared in {0,1}^kappa, read here as
        an integer mod q (the only reading under which Omega = omega*x is defined).
  V2  = T-IFS-24929-2025 (Dec 2025): Omega = omega*x*P (a point); k = H4(omega); C = k xor Z.

Attack discipline: every coalition check recovers a target using ONLY that coalition's stated
inputs. Original secrets are read afterwards SOLELY to verify the recovered value. This is noted
per check in `inputs_used`.

Categories (see harness): OBSERVATION, TYPE-CHECK, IDENTITY, LIMITATION-DEMO.
Note: several correct outcomes are False (e.g. V2 computability); expected values encode that.
"""
import hashlib, secrets
from harness import Suite

# ---------- NIST P-256 ----------
p  = 0xffffffff00000001000000000000000000000000ffffffffffffffffffffffff
q  = 0xffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551
aa = -3
Gx = 0x6b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296
Gy = 0x4fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5
O  = None

def add(P, Q):
    if P is O: return Q
    if Q is O: return P
    x1, y1 = P; x2, y2 = Q
    if x1 == x2 and (y1 + y2) % p == 0: return O
    if P == Q: l = (3*x1*x1 + aa) * pow(2*y1, -1, p) % p
    else:      l = (y2 - y1) * pow(x2 - x1, -1, p) % p
    x3 = (l*l - x1 - x2) % p
    return (x3, (l*(x1 - x3) - y1) % p)

def mul(k, P):
    k %= q; R = O
    while k:
        if k & 1: R = add(R, P)
        P = add(P, P); k >>= 1
    return R

def neg(P): return O if P is O else (P[0], (-P[1]) % p)
def sub(P, Q): return add(P, neg(Q))
def div(P, s): return mul(pow(s, -1, q), P)          # "P / s" = s^{-1} * P
P0 = (Gx, Gy)

def enc(x):
    if x is O: return b"O"
    if isinstance(x, tuple): return x[0].to_bytes(32, "big") + x[1].to_bytes(32, "big")
    if isinstance(x, int): return x.to_bytes(32, "big")
    if isinstance(x, str): return x.encode()
    return x
def Hz(tag, *a): return int.from_bytes(hashlib.sha256(tag + b"".join(enc(v) for v in a)).digest(), "big") % (q-1) + 1
def Hb(tag, *a): return hashlib.sha256(tag + b"".join(enc(v) for v in a)).digest()
H1 = lambda *v: Hz(b"H1", *v); H2 = lambda *v: Hz(b"H2", *v)
H3 = lambda *v: Hb(b"H3", *v); H4 = lambda *v: Hz(b"H4", *v); H5 = lambda *v: Hz(b"H5", *v)
xor = lambda x, y: bytes(i ^ j for i, j in zip(x, y))
rnd = lambda: secrets.randbelow(q-1) + 1

alpha = rnd(); Ppub = mul(alpha, P0)

def keygen(ID):
    Phi = rnd(); PID = mul(Phi, P0)
    r = rnd(); RID = mul(r, P0)
    psi = H1(ID, RID, PID); d = (r + alpha*psi) % q; VID = mul(d, P0)
    return dict(ID=ID, Phi=Phi, d=d, PID=PID, RID=RID, VID=VID, psi=psi)

full_pk_point = lambda u: add(add(u['PID'], u['RID']), mul(u['psi'], Ppub))      # (Phi+d)P
dec_secret    = lambda u: (u['d'] + u['Phi']*H2(u['ID'], Ppub)) % q               # x_j
dec_point     = lambda u: add(add(u['RID'], mul(u['psi'], Ppub)), mul(H2(u['ID'], Ppub), u['PID']))

def SC(s, r, m):
    lam, mu = rnd(), rnd(); Lam, Del = mul(lam, P0), mul(mu, P0)
    D = mul(lam, dec_point(r))
    E = xor(m, H3(s['ID'], Lam))
    h = H4(m, s['ID'], E, D, Lam, s['RID'], s['PID'])
    theta = (lam + h*(s['Phi'] + s['d'])) % q
    Psi = H5(D, E, Del, theta)
    f = (mu + Psi*(s['Phi'] + s['d'])) % q
    return dict(D=D, E=E, Del=Del, f=f, theta=theta), lam

def cloud_verify(s, c):
    Psi = H5(c['D'], c['E'], c['Del'], c['theta'])
    return mul(c['f'], P0) == add(c['Del'], mul(Psi, full_pk_point(s)))

def USC1(s, r, c):
    Lam = div(c['D'], dec_secret(r))
    m = xor(c['E'], H3(s['ID'], Lam))
    h = H4(m, s['ID'], c['E'], c['D'], Lam, s['RID'], s['PID'])
    ok = mul(c['theta'], P0) == add(Lam, mul(h, full_pk_point(s)))
    return m, ok, Lam, h

def RKG_V1(jj, ll):          # scalar Omega (V1')
    om, t = rnd(), rnd(); T = mul(t, P0); Z = H3(jj['ID'], T)
    Om = om * dec_secret(jj) % q
    gam = mul(t, dec_point(ll)); C = xor(om.to_bytes(32, "big"), Z)
    return dict(C=C, Om=Om, gam=gam), om

def RKG_V2(jj, ll):          # Omega point, C = H4(omega) xor Z  (as published in V2)
    om, t = rnd(), rnd(); T = mul(t, P0); Z = H3(jj['ID'], T)
    Om = mul(om * dec_secret(jj) % q, P0)
    k = H4(om)
    gam = mul(t, dec_point(ll)); C = xor(k.to_bytes(32, "big"), Z)
    return dict(C=C, Om=Om, gam=gam), om


def main():
    S = Suite("adspre_diag", "ADS-PRE correctness and coalition exposure (self-contained, diagnostic)")
    j = keygen("j"); l = keygen("l")

    # ---- V2 published re-encryption is not computable -------------------------------------
    rk2, om2 = RKG_V2(j, l)
    c, _ = SC(keygen("s0"), j, b"x"*32)
    try:
        div(c['D'], rk2['Om'])                       # point / point: no scalar inverse of a point
        v2a = True
    except TypeError:
        v2a = False
    S.check("V2-a", "TYPE-CHECK", False, v2a,
            establishes="published V2 Alg.8 'D/Omega' with Omega a POINT is undefined (expected False)",
            not_established="nothing about V1; this is the V2 typing error only")

    T = div(rk2['gam'], dec_secret(l))
    rec = int.from_bytes(xor(rk2['C'], H3(j['ID'], T)), "big")
    S.check("V2-b", "OBSERVATION", False, (rec == om2),
            establishes="V2 Dec2 does NOT recover omega (expected False): it recovers H4(omega)",
            not_established="—")
    S.check("V2-c", "OBSERVATION", True, (rec == H4(om2)),
            establishes="V2 Dec2 recovers H4(omega), a hash that cannot be inverted to omega",
            not_established="—")

    # ---- V1' coalition: proxy (Omega) + delegatee (omega) recover x_j ----------------------
    rk, om = RKG_V1(j, l)
    # Coalition inputs ONLY: Omega (proxy) and omega (delegatee). Recover x_j.
    x_recovered = (rk['Om'] * pow(om, -1, q)) % q    # uses rk['Om'], om only
    x_true = dec_secret(j)                            # read AFTER, to verify only
    S.check("C1-a", "OBSERVATION", True, (x_recovered == x_true),
            establishes="proxy(Omega)+delegatee(omega) recover x_j = d_j + Phi_j*H2(ID_j,Ppub)",
            not_established="recovery of Phi_j, d_j, or the signing secret s_j individually (see C1-c)",
            detail=dict(inputs_used=["rk.Omega (proxy)", "omega (delegatee)"]))

    # x_j opens a fresh first-level ciphertext to j (never delegated).
    fresh, _ = SC(keygen("s1"), j, b"N"*32)
    Lam = div(fresh['D'], x_recovered)
    opened = (xor(fresh['E'], H3("s1", Lam)) == b"N"*32)
    S.check("C1-b", "OBSERVATION", True, opened,
            establishes="recovered x_j decrypts a fresh, never-delegated first-level ciphertext addressed to j",
            not_established="any effect on ciphertexts addressed to other receivers",
            detail=dict(inputs_used=["x_j (recovered)"]))

    # ---- C1-c narrowed: the exact identity checked, with its stated conditions -------------
    # Identity: s_j = x_j + Phi_j*(1 - H2(ID_j,Ppub))  (mod q), where s_j = Phi_j + d_j, x_j = d_j + Phi_j*H2.
    h2 = H2(j['ID'], Ppub)
    s_j = (j['Phi'] + j['d']) % q
    identity_holds = (s_j == (x_recovered + j['Phi']*(1 - h2)) % q)
    S.check("C1-c", "IDENTITY", True, identity_holds,
            establishes="the algebraic identity s_j = x_j + Phi_j*(1 - H2) holds (verified on this instance)",
            not_established="it does NOT by itself prove s_j is hard to recover. Rearranged, Phi_j = (s_j - x_j)/(1 - H2) "
                            "requires H2 != 1 (else undefined) and knowledge of s_j; from the coalition view "
                            "(x_j and the public (Phi_j+d_j)P) obtaining Phi_j is an ECDL instance. Whether the FULL "
                            "adversary view yields s_j is a separate claim needing a proof, not shown here.",
            detail=dict(h2_equals_1=(h2 == 1), condition="H2 != 1 for the rearrangement to be defined"))

    # With the KGC additionally (knows d_j): Phi_j = (x_j - d_j)/H2, full key.
    if h2 != 1:
        phi_rec = ((x_recovered - j['d']) * pow(h2, -1, q)) % q
        S.check("C1-d", "OBSERVATION", True, (phi_rec == j['Phi']),
                establishes="proxy+delegatee+KGC (adds d_j) recover Phi_j, hence the full private key (Phi_j,d_j)",
                not_established="this needs the KGC in the coalition; without d_j it is the ECDL of C1-c",
                detail=dict(inputs_used=["x_j (recovered)", "d_j (KGC)"]))
    else:
        S.check("C1-d", "OBSERVATION", True, True,
                establishes="H2 happened to be 1 on this instance; skipped (astronomically unlikely)",
                not_established="—")

    # ---- Aggregate cancellation: two invalid thetas that cancel are accepted --------------
    mal = keygen("mal")
    c1, _ = SC(mal, j, b"A"*32); c2, _ = SC(mal, j, b"B"*32)
    delta = rnd(); c1 = dict(c1); c2 = dict(c2)
    c1['theta'] = (c1['theta'] + delta) % q; c2['theta'] = (c2['theta'] - delta) % q
    for cc in (c1, c2):                                # recompute f so the public check still passes
        mu = rnd(); cc['Del'] = mul(mu, P0)
        Psi = H5(cc['D'], cc['E'], cc['Del'], cc['theta'])
        cc['f'] = (mu + Psi*(mal['Phi'] + mal['d'])) % q
    _, ok1, L1, h1 = USC1(mal, j, c1)
    _, ok2, L2, h2b = USC1(mal, j, c2)
    Theta = (c1['theta'] + c2['theta']) % q
    agg_ok = mul(Theta, P0) == add(add(L1, mul(h1, full_pk_point(mal))),
                                   add(L2, mul(h2b, full_pk_point(mal))))
    S.check("AG-pass", "OBSERVATION", True, cloud_verify(mal, c1) and cloud_verify(mal, c2),
            establishes="both tampered records still pass the per-item cloud f-check",
            not_established="—")
    S.check("AG-accept", "OBSERVATION", True, agg_ok,
            establishes="the aggregate theta-check ACCEPTS the batch though neither theta is individually valid",
            not_established="—")
    S.check("AG-invalid", "OBSERVATION", True, (not ok1) and (not ok2),
            establishes="neither individual theta verifies: the sum cancelled the tampering",
            not_established="—")

    # ---- Replay / omission: the verified statement carries no freshness or completeness ----
    old, _ = SC(keygen("s2"), j, b"OLD".ljust(32, b"0"))
    new, _ = SC(keygen("s3"), j, b"NEW".ljust(32, b"0"))
    def agg_accept(items):
        Th = sum(c['theta'] for _, c in items) % q; rhs = O
        for s, c in items:
            _, _, Lam, h = USC1(s, j, c); rhs = add(rhs, add(Lam, mul(h, full_pk_point(s))))
        return mul(Th, P0) == rhs
    s2u, s3u = keygen("s2b"), keygen("s3b")
    o2, _ = SC(s2u, j, b"R".ljust(32, b"0")); o3, _ = SC(s3u, j, b"S".ljust(32, b"0"))
    S.check("RP-replay", "OBSERVATION", True, agg_accept([(s2u, o2), (s2u, o2), (s3u, o3)]),
            establishes="a replayed record is accepted again inside a later aggregate (no freshness bound)",
            not_established="—")
    S.check("OM-omit", "OBSERVATION", True, agg_accept([(s3u, o3)]),
            establishes="dropping a record and its theta still verifies (no completeness bound)",
            not_established="—")

    S.finish()

if __name__ == "__main__":
    main()
