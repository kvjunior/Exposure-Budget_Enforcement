# 0002 Backend selection

Measured HPKE path: `hpke` 0.3.2 over `cryptography` 43 (RFC 9180, DHKEM-P256/HKDF-SHA256/
AES-256-GCM). Round-trip, owner-rewrap-preserving-payload, and tamper detection validated.

PRE witnesses: pyUmbral 0.3.0 (secp256k1). It requires cryptography ~=3.0, INCOMPATIBLE with
the HPKE stack, so it lives in a SEPARATE venv and runs as a separate process. We did not pick
a production stack because the legacy diagnostics run; the two environments are isolated by
design (requirements-prod.txt vs requirements-legacy.txt).

Rust Umbral + a Rust workspace are the planned end-state (brief sec 5). This sandbox has no
Rust toolchain and 1 vCPU; the slice is implemented in Python with the SAME typed contracts
(apply_event, retained_closure, exposure_bound, propose_action, check_action,
execute_authorized_action). Porting the model to Rust does not change the contracts or the
differential test, which already compares the model against an independently written reference.
No mock cryptosystem is used anywhere in the measured path.
