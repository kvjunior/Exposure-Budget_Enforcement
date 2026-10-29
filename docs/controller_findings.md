# Controller status and declared-objective finding

EARP is retired and raises NotImplementedError. Its historical rule was greedy under positive
rollover cost; no proposed controller is benchmarked or claimed novel in this release.

Current code supplies baseline infrastructure and an exact bounded canonical-plan oracle. Metadata
and partial admissions are explicit choices. Every comparison reports service counts as well as
cost, and rolling_horizon's perfect-information diagnostic receives only the remaining requests.
The legacy single-action baselines_vs_oracle experiment is a diagnostic, not a principal evaluation.

The corrected missing-metadata case has cost 24 serving one request; a valid alternative costs 25
serving two. A rotation already incurs an opportunity/miss cost, so completing that same request
can add fragment cost without removing the already-incurred penalty. This is reported under the
unchanged objective. P3 must define waiting versus terminal nonservice using actual release/deadline
semantics. No objective term is added to manufacture an algorithmic win.

risk_rotation_heuristic is our own reconstructibility heuristic. It is not a reproduction of the
published SACMAT method. No conclusion about that method follows from this heuristic's ranking.

No scalability claim is made: delivery enumeration uses 2^shares subsets and coverage 2^recipients
cases. The code explicitly refuses oversized delivery domains. Controller usefulness and a novel
management result remain open.
