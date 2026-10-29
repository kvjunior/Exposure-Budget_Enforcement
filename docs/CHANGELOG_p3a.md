# P3A — typed timed-input foundation

Parent: Slice 2.2.1 source SHA256
`44a02f025f519b61ab1fad9f276b4d15f1ec6d6b9dd4af15e8c75dd2aeeb920a`.
Author: ChatGPT/Codex. Claude independent review pending.

Added three production modules: service_clock.py, demand_queue.py, timed_log.py;
one test module, timed_inputs_test.py; a precise timed-model contract; conditional
invariant arguments; and the P3B next-batch plan. No planned empty code stubs.

The new layer uses typed service ticks/append sequences, half-open deadlines,
immutable exact-record demands, at-most-once trusted completion bookkeeping,
waiting/terminal/pending metrics, delayed public reports and causal visible
prefixes. It does not import or reinterpret legacy grant/token time fields.
Existing crypto, checker, executor, decision-index oracle, reference and baseline
Python implementations are unchanged from the parent. P3A modules are not wired
into them yet. Full-regression compatibility and deterministic legacy-output
comparison accompany the release.

New tests cover 29 cases, 24 batch permutations and 1,296 tiny operation tapes /
5,184 transitions against a separate dictionary queue reference. These are the
implementer's tests, not independent laboratory verification or a crypto proof.

USABLE receipts remain an explicit trusted-backend assertion. Time/authority
migration, actual crypto completion, causal simulation, interrupted delivery,
production-driven exposure infeasibility and policy/oracle integration belong
to P3B. The literature/novelty gate and closure reduction remain open.
