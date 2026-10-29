# Threat model

Adversary = a coalition C from a declared admissible family, corrupting parties ADAPTIVELY
under a LIFETIME corruption budget (a concurrent-corruption bound is insufficient because old
shares accumulate). When a proxy/recipient joins C, ALL material ever routed to it (any time)
accumulates to C. A mobile adversary needs extra justified erasure/refresh assumptions; not
claimed here.

Honest-but-curious storage and proxies may also act maliciously (drop, reorder, replay,
return corrupt fragments); these are availability/soundness events, handled at the service
layer, distinct from confidentiality.

Owner root compromise is OUT of the small-bound regime: if O's root is in C, every scope key
is exposed and no small exposure bound is claimed (closure/exposure callers must special-case
this; see management_problem.md).

Controller: sees only observable history. It never observes realized corruption or future
events, and cannot mint owner authority. An offline controller may activate a fresh scope
ONLY with an authentic owner preauthorization token.

Confidentiality games MUST exclude authorized decryption: if C can legitimately open the
challenge capsule via available cfrags + recipient key, that capsule is not an admissible
challenge (witnessed by tests/adversarial ADV-R3b).
