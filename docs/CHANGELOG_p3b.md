# P3B change record

Parent: P3A source archive SHA-256
`1609491d78a96f8493ed756e1da65cd4fec426765133becbd7081b3382f2ea24`.
Author: ChatGPT/Codex. Independent Claude review pending.

Added service-time grants, typed effect-specific tokens, occurrence-time public projection,
a declared-family retained-capability evaluator and a causal single-threaded model simulator.
Added 44 integration tests and five scripted traces. Added explicit conditional arguments and
a counterexample to whole-run disclosure guarantees under delayed/unbounded production.
The model includes an abstract backend; no timed PRE decryption or measured latency is claimed.

All Python files present in P3A remain unchanged. The Makefile adds timed service checks and
`timed-pilot`; source status/claims/docs are updated without changing the legacy objective,
oracle, reference, crypto code or decision-index PO2 statement. Generated clean-run evidence is
provided alongside, not prepopulated into the source archive.
