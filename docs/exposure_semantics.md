# Exposure semantics

K_t(C): accumulated retained material (monotone; revocation-invariant).

Conservative closure Cl_hat(K_t(C)) (over-approximates openable records; never under):
  R1 scope key held        -> every produced record of that scope openable (and future ones
                              while the scope stays active).
  R2 >=t matching kfrags of a grant + that grant's recipient key -> scope key (Umbral).
  R3 >=t cfrags for a record + recipient key -> that record (no scope key).
  R4 data key held         -> that record.
  R5 plaintext held        -> that record (never un-known by revocation).

Exposure X_t(C) = sum of w(r) over records r in Cl_hat outside ever-authorized-to-C, reported
as TWO quantities:
  - past (endpoint): produced records openable and never authorized to C by this cutoff;
  - future: scopes still ACTIVE whose key C holds -> future records will be exposed until the
    scope is rotated away.
Historical permission to read a record (even if later revoked) is NOT collateral exposure:
knowing that plaintext is not a new violation. Moving a reporting window never "erases"
knowledge. Owner-root compromise is excluded from small-bound claims.

w(r): a per-record weight (default 1.0); its meaning (record value, record count) is fixed per
experiment and frozen before the main comparison.

## Slice 1.1 corrections

### R3' mixed-fragment rule (replaces the slice-1 R3)
A coalition holding the recipient key can open a record under grant g if it can assemble >= t
cfrags for that record's capsule, where a share at index i is available if it holds EITHER a
received cfrag for (g, record, i) OR the raw kfrag for (g, i) (it locally transforms the public
capsule). The available-share set is the UNION of received-cfrag indices and held-kfrag indices;
each share counts once; cfrags from a different grant do not combine. Holding >= t kfrags of g
plus the recipient key therefore opens every produced record in g's range (and R2's scope-key
recovery additionally opens out-of-range and future records).

### R8 prospective-revocation contract (documented semantics)
authorized_records_of counts a record r as authorized to coalition C iff r is in a C-recipient
grant's range/scope AND r was produced on or before that grant's end of authorization (the
revocation time, or valid_to if earlier). Retained old plaintext stays authorized (a live-grant
recipient could read, including delayed retrieval of earlier records); a record first produced
AFTER revocation/expiry was never within the recipient's authorized reach and is counted as
collateral exposure. This is a semantic contract, chosen deliberately; the alternative weaker
contract (permanently authorizing all in-range future data) would require correspondingly
weaker revocation and exposure claims and is NOT adopted.

### Validity clock (R7)
Grant validity is evaluated at the REQUESTED observation time, which advances across idle
intervals even with no event at that exact time.

### Units
future-scope COUNT and weighted past-data exposure are DISTINCT dimensions with separate budget
caps and separate witness coalitions (coordinate-wise maxima). Do not conflate them.


## Correction branch 1.2: historical authorization and scope boundaries

A record is historically authorized by cutoff T iff there exists a reading time tau with
`max(record_production_time, grant_issue_time, valid_from) <= tau <= min(T, valid_to)` and
`tau < revoke_time`, with absent upper bounds omitted. Range and scope must match. This
permits delayed reading of old records after a later grant becomes live. A future grant that
has not started, or a grant revoked before it starts, grants no historical exemption.

The current past quantity is an ENDPOINT measure. A later grant may newly authorize an old
record and reduce this quantity. That is not cumulative irreversible leakage. Before using a
cumulative past-leakage budget, implement a separate ledger of first unauthorized disclosures;
subsequent grants must not erase that ledger.

This branch only admits immediate scope activation at the next produced sequence. Future
scheduled activation is unsupported; arbitrary history folds are not validated by this checker.
