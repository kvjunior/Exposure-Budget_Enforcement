# Checked action and executable plan boundary — Slice 2.2.1

check_action is pure. For a delivering ADMIT it checks registered owner/availability or a matching
grant token, activated scope, new grant identifier and distinct valid share indices. A nonempty
public coalition family and finite nonnegative weights are required. It evaluates the entire
observable prefix plus candidate grant/kfrags, expands exact recipient subsets, and checks
coordinate-wise endpoint past-weight and exposed active-scope maxima.

An empty-delivery ADMIT is an authentic logical authorization, not usable service. It can change
later exemptions and is therefore retained in oracle enumeration. Scope tokens and grant tokens
are separate; issuance and access validity are separate. PreAuth is an assumed authentic context,
not signature verification. Root compromise and arbitrary disclosures are outside the small bound.

approve/execute rebuild derived observation state, enforce one canonical event time at cutoff+1,
bind complete observable history/cutoff/action/context/config/plan, recheck at commit and return an
empty outbox on a stale/substituted/context-changed/refused commit. An unsupported timestamp at
approval raises ValueError before effects exist. The executor is a pure process-local reference,
not persistent or concurrent network I/O.

The canonical SERVICE plan grammar and cost domain are separately specified in
decision_index_contract.md. Replay and oracle enforce that smaller domain consistently. Scope/key
identifiers remain abstract fresh labels rather than a signed catalogue of actual fresh bytes.
HPKE smoke and threshold-PRE retained-capability witnesses are separate mechanisms; no HPKE timing
is presented as a measurement of PRE admission.
