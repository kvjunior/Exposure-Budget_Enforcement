# 0003 Controller information boundary

The online controller consumes `project_observation(events, cutoff)`, which keeps only
OBSERVABLE events (StreamAuthorized, ScopeActivated, RecordProduced, GrantIssued, GrantRevoked,
KFragInstalled, CFragProduced, OwnerAvailability) with t <= cutoff. Ground-truth compromise
(CorruptProxy, CorruptRecipient, Disclose*) and any event with t > cutoff are excluded by
construction. The exposure model consumes the FULL stream (it is an evaluation/soundness tool,
not a controller input). A planned test (python/tests/test_no_future_information.py) asserts no
ground-truth/future event ever reaches a policy.
