# Project charter

**Title (working).** Exposure-Aware Delegation Management for Encrypted Data Services with Intermittent Owners.

**Venue.** IEEE TNSM, traditional subscription route. 10 pages without mandatory charges, then US$220/page to 16 (2026 IEEE APC list, verified). Recheck at submission.

**Central question.** How should an encrypted data service admit or defer delegation requests and roll key scopes, using only information available at decision time, when owners are intermittently available and previously issued cryptographic capabilities may be retained by colluding parties?

**Hypothesis under test (falsifiable).** History-dependent management of *retained capabilities* — accounting for collateral exposure and feasible owner-authorized actions — yields better feasible management decisions than exposure-blind baselines under matched constraints. This is a hypothesis, not a result. If every policy turns out equivalent, the exposure bound vacuous, or one static policy always optimal, we revise the question rather than manufacture a win.

**What is contributed (intended).** (1) a management model separating authorization state, key-scope state, retained knowledge, and operational state; (2) a conservative retained-capability closure and an exposure measure with a stated conditional soundness argument; (3) a justified online controller; (4) a reproducible evaluation against real baselines with matched security. Cryptography is used, not invented: PRE (Umbral), HPKE (RFC 9180), Ed25519. We do **not** claim a new signcryption/PRE primitive, nor a new aggregate-authentication theorem.

**Non-goals.** Fault-localising aggregate authentication as a second research project; a theorem-only paper; retargeting to TDSC silently.

**Scope boundaries.** Single owner per stream initially; threshold and proxy placement fixed initially; owner-root compromise handled separately (it gives every scope key — no small bound is claimed there).
