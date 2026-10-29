# 0006 History summary: is sufficient state substantive or a flag?

Question: does the conservative threat model make every completed t-of-n grant expose the whole
scope, collapsing the relevant history to a per-scope "delegated?" boolean?

Finding (tests/differential/sufficient_state_test.py): NO. Possible-exposure of a scope depends
jointly on (i) how many distinct share indices were installed vs the threshold, (ii) whether the
declared coalition's reach covers >= t of those proxies, and (iii) whether the coalition holds the
grant's recipient key. The same completed grant is exposing under full reach + recipient, and
NON-exposing under reach < t, sub-threshold install, or no recipient key. Therefore the sufficient
state is NOT a single flag, and the online management problem is substantive.

Consequence: a history_summary.py (minimal sufficient state) may still be built, but only AFTER a
correctness argument; it will summarize (per scope: installed-index set per grant, and the
family-relative reach), not a boolean. No presumed novelty is attached to it yet.
