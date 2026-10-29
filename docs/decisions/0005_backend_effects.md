# 0005 Backend effects: separate logical authority from capability delivery

Decision: model capability DELIVERY with typed, backend-specific Effects
(delegation_model/effects.py), distinct per mechanism:
  - THRESHOLD_PRE grant -> raw KFRAG effects to proxies (t + recipient key => scope key);
  - OWNER_HPKE_REWRAP   -> one DATA_KEY effect to one recipient for one record;
  - SCOPE_KEY_HANDOVER  -> one SCOPE_KEY effect to a recipient (whole scope).

Rationale (research guide): "every mechanism needs a matching effect contract; do not attach HPKE
timing to a PRE capability model and call it one measured protocol." The reference executor
(delegation_manager/executor.py) enforces that the effects a checked action DECLARED equal the
effects delivered; a mismatch refuses commitment with no delivered outbox. The HPKE smoke measures OWNER_HPKE_REWRAP; the Umbral
witnesses exercise THRESHOLD_PRE; they are never conflated.

Consequence: the current checked-action exposure gate reasons about THRESHOLD_PRE kfrag delivery.
HPKE-rewrap and handover effects are modeled but their admission gating is P3 (service stage).
