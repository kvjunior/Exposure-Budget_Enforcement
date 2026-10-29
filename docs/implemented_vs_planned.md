# Implementation status — P3B

Implemented: P3A typed time/order, immutable queue, public prefix log; P3B typed timed grants and
effect-specific tokens, effective-time projection, causal scheduler with action-dependent original
record scope binding, per-delivery checks, abstract usability backend, retained interrupted effects,
three separate exposure coordinates, actual-vs-observable ledgers and production-breach reporting.
44 integration tests and five scripted deterministic model traces are supplied.

Preserved byte-for-byte: all P3A Python files, including legacy Slice 2.2.1 authorization/closure,
process-local executor, bounded old oracle/reference, baseline diagnostics, isolated Umbral witnesses
and HPKE smoke. They keep their decision-index semantics and original proof limitations.

Not implemented: real timed PRE backend/receipt verification, cryptographic token signatures,
timed exact oracle/reference, new controller, multi-grant completion, networked deployment,
production-scale workloads, publication figures or a whole-run hard cumulative budget guarantee.
ModelBackend is an abstract trusted usability assertion. The observable gate cannot see unreported
actual production; an explicit implemented counterexample demonstrates the resulting limitation.

Next: P3C contract/candidates/timed oracle/separate replay reference. Real timed backend integration
is a later step. PO1, full-run/adaptive/cumulative guarantees, family justification, TOPS extension
full text and systematic TNSM novelty comparison remain open. EARP stays retired.
