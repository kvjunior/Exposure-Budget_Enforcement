# Related-work reading log

Versioned, section-level evidence. "full" = relevant sections read in the actual full text this
session; "partial"/"abstract" noted. An abstract or keyword hit never establishes an affirmative
gap; only full-text reading of the decision problem does.

## JNCA 2025 — Berlato, Morelli, Carbone, Ranise, "A Secure and Quality of Service-Aware Solution for the End-to-End Protection of IoT Applications," *Internet of Things* (Elsevier), preprint dated June 6, 2025.
Reading: **full** (PDF supplied; Sections 1, 2, 5.2, 6.1, 6.3, 7.1–7.4 read directly).
- Problem: cryptographic access control (CAC) for MQTT publish/subscribe, end-to-end
  confidentiality/integrity, honest-but-curious Edge/Cloud. RBAC mapped to topics (§6.1).
- Revocation and cached keys (§6.3): on revocation, "any resource's symmetric key and role's
  private key that the revoked user could access … need to be renewed and re-distributed," because
  "the revoked user could still access the resource using a cached key." Keys carry **version
  numbers** incremented on rotation; metadata signed and held by a Metadata Manager. This is the
  closest prior treatment of the cached-key problem — and it handles it by **renew-and-redistribute
  with versioning**, not by a quantitative retained-capability exposure measure or an online
  admission decision.
- Optimization problem (§5.2, §7): the decision variable is an **architecture** = an assignment of
  entities {proxy, RM, MM, DM} to **domains** {client, on-premise, Edge, Cloud}. §7.1 enumerates
  ARC_ext = P(D_ext × E) = 2^(4·4) = **65,536 architectures**; the optimizer picks Pareto-optimal
  or weighted-sum-ranked architectures that minimize risk and maximize QoS. This is a **design-time
  deployment-placement** optimization, evaluated once per scenario.
- What is absent (searched full text): no online admit/defer decision over an evolving request
  history; no deferral; no exposure budget over declared coalitions; no intermittent-owner
  availability reasoning; no immediate key-scope rollover chosen from observable retained-capability
  state. "admi/defer/schedul/queue/budget/coalition" return only unrelated hits.

**Affirmative difference (grounded in full text):** JNCA optimizes *where to deploy* the CAC
mechanism; this work decides *whether to admit/defer a delegation and whether to roll a key scope
now*, online, from observable retained-capability history under an exposure budget and intermittent
owner authority. Different decision variable, different information (design-time placement vs online
history), different objective (risk/QoS of a static architecture vs served-demand/cost under an
exposure constraint). The cached-key renewal in §6.3 is prior art we must cite and NOT claim as new.

## NuCypher KMS — arXiv:1707.06140.
Reading: **full** (prior session; re-confirmed scope). Scoped/time-based policies, split-key
m-of-n proxies, per-field/per-channel keys, rotation, revocation by kfrag deletion; names
proxy–reader collusion informally. No online history-dependent admission controller, no exposure
measure, no intermittent-owner reasoning. Cite; do not claim collusion/rotation as new.

## ASIA CCS 2020 (10.1145/3320269.3384767) — Berlato, Carbone, Lee, Ranise.
Reading: **full** (read this session via the NSF PAR copy, purl 10298471). CORRECTION to the prior
session wrap: ASIA CCS 2020 and the TOPS 2022 journal article (10.1145/3474056) are SEPARATE
versions; reading the conference paper does NOT constitute a full-text read of the TOPS extension.
The two are treated separately here.
Decisive detail (conference version): the optimization decision variable is an **architecture** = a
subset of (Entities × Domains): which software entities (proxy, reference monitor, data storage,
metadata storage) are deployed in which domains (client / on-premise / CSP). Section 4 formalizes the
set ARC (81 architectures) in set theory; Section 5 reduces architecture selection to a **design-time
Multi-Objective Optimization Problem** solved once per scenario via Pareto optimality or a constrained
weighted sum over static security/usability goals (redundancy, scalability, reliability, maintenance,
DoS resilience, vendor lock-in, monetary savings), feeding a TOSCA/Cloudify blueprint. No temporal
request history, no online admit/defer, no retained-capability exposure budget, no intermittent-owner
availability. Revocation appears only in related-work discussion of other schemes.
**Difference (this version):** ASIA CCS 2020 optimizes WHERE to deploy CAC entities at design time;
this work decides, online, WHETHER to admit/defer a delegation and WHETHER to roll a key scope now.
Different decision variable, information, and objective.

## TOPS 2022 (10.1145/3474056) — Berlato, Carbone, Lee, Ranise, "Formal Modelling and Automated Trade-off Analysis of Enforcement Architectures for CAC in the Cloud," ACM TOPS 25(1).
Reading: **UNRESOLVED / not read in full this session.** It is the journal extension of ASIA CCS
2020 and, per its abstract and the authors' records, extends the same architecture-selection MOOP
(adding a formal model and automated trade-off analysis). I did NOT retrieve its full text this
session, so I do not claim a full-text comparison with TOPS 2022. The comparison with the TOPS
extension is marked open; the ASIA CCS 2020 full text covers the core model it extends.

## SACMAT 2025 — Brunello, Berlato, Carbone, Lee, Ranise, "Relying on Trust to Balance Protection and Performance in Cryptographic Access Control," Proc. 30th ACM SACMAT, Stony Brook, 8-10 Jul 2025 (10.1145/3734436.3734452).
Reading: **full** (PDF supplied; Sections 1, 4-6, evaluation read directly). This is the CLOSEST
prior work and it is materially closer than the prior session wrap credited; my earlier
title-level dismissal was wrong and is corrected here.
What it actually does:
- It models CACHED decrypting keys after revocation explicitly. A revoked-but-untrusted user "may
  have cached such decrypting keys and still access the data without authorization (possibly even
  colluding with cloud providers)" (Sec 1). This is the same retained-capability risk this work
  studies.
- It gives a FOUR-STATUS state model of keys (Sec 4.2): incomplete inc, operational ope, revoked
  **hide** ("for tracking keys that MAY HAVE BEEN CACHED"), and deleted del. User-role and
  role-permission assignment sets are partitioned into these four statuses, so cached-but-not-yet-
  rotated capabilities are tracked as state. This is a cached-capability state model, not a flag.
- It adds a query `canUserBeCache_C(u,r)` ("whether u can assume role r POSSIBLY USING CACHED KEYS")
  and 10 queries Q_C capturing what a malicious user could do with cached keys (Sec 5.3, Table 8).
- The DECISION it makes: whether role-key rotation, resource-key rotation, and resource
  re-encryption are NEEDED NOW vs superfluous, per a tunable security model (trust predicates like
  `untrusted(u)`, `eager(f)`). The state-change rules no longer rotate automatically; rotation runs
  only "when required by the underlying security model" (Sec 4.2, 5.4). The decision variable is
  essentially: on this revocation/policy change, execute or skip the (expensive) rotation/
  re-encryption, with eager vs lazy timing.
- A Prolog CONSISTENCY CHECK (Sec 6) proves correctness and safety invariants, e.g.
  `isRoleKeyRotationNeeded_E(u,r) => canUserBe_C(u,r) \/ ~canUserBeCache_C(u,r)` — rotate iff the
  user is still authorized OR could still assume the role with cached keys. Evaluation is a
  preliminary Prolog proof-of-concept timing 100 state-change rules (Sec, Table 6).

Honest reassessment of our claimed differences:
1. Cached-key state: NOT a difference. SACMAT 2025 tracks cached-key status (hide) and reasons about
   collusion with the cloud. We must stop claiming "names collusion only informally" for this work.
2. Cryptographic-operation decision: SACMAT decides WHICH expensive crypto ops (rotation,
   re-encryption) to execute or skip on a policy change, and eager-vs-lazy timing. That is a
   genuine management-of-cryptographic-work decision — overlapping in spirit with our admit/defer/
   roll, but with DIFFERENT decision variables (execute/skip a rotation vs admit/defer a delegation
   and roll a scope) and a DIFFERENT objective (minimize superfluous crypto while preserving RBAC
   correctness vs serve delegation demand under an exposure budget with intermittent owners).
3. Consistency checking: SACMAT's consistency check verifies RBAC correctness/safety invariants
   after each state change. Our checked-action path verifies authority + an exposure-budget
   constraint over a declared coalition family before admitting. Related in role (a per-transition
   soundness check) but different property (RBAC correctness vs forward exposure budget).

Surviving differences (candidate, to be made precise — see docs/surviving_problem.md):
- ONLINE SEQUENTIAL admission/deferral of delegation REQUESTS over time, vs SACMAT's reactive
  decision triggered by an administrator's revocation/policy change. SACMAT has no request queue,
  no deferral, no arrival process.
- INTERMITTENT OWNER AUTHORITY: SACMAT assumes an always-available administrator; it has no notion
  of the authority being offline and no preauthorization mechanism.
- A QUANTITATIVE forward EXPOSURE BUDGET over a declared coalition family and a cumulative
  irreversible disclosure ledger, vs SACMAT's boolean correctness/safety invariants.
- THRESHOLD/fragment structure: SACMAT's cached keys are whole role/resource keys; our exposure
  depends on installed share indices vs threshold and coalition reach (the nontriviality result).
  Under SACMAT's whole-key model, "a completed grant" is closer to a flag; under threshold PRE it is
  not. This difference must be stated carefully and may narrow the claim (see below).
Mechanism mismatch to state honestly: SACMAT is RBAC role/resource keys with rotation+re-encryption;
our backend is threshold PRE + HPKE rewrap. Comparisons must align assumptions, not equate
mechanisms.

## JEDI (USENIX Security 2019).
Reading: **partial** (design read previously). Hierarchical URI+time delegation via WKD-IBE;
expiry built into keys; decentralized delegation. It decides **key structure / scope**, not an
online admit/defer/roll controller under retained-capability exposure. Complementary; cite as the
scoped-delegation baseline.

## Umbral / pyUmbral (threshold PRE backend).
Reading: **full** (code). Supplies the retained-material capabilities the closure reasons over
(t kfrags + recipient key → scope key; mixed fragments). A mechanism we use, not a competitor.

## Gate status after this session
Full-text read and confirmed NOT to pose online history-dependent delegation admission under a
retained-capability exposure budget with intermittent owners: **JNCA 2025**, **ASIA CCS 2020 (=TOPS
2022 journal extension)**, **NuCypher KMS**. These are the three closest works and all optimize
either deployment architecture (Berlato line) or provide scoped/rotating PRE primitives (NuCypher).
The affirmative novelty gap is now grounded in the full texts of the three closest works.
Remaining (do not block slice-2 findings, but required before freezing the principal comparison and
submitting): SACMAT 2025 full text (trust/performance tuning — expected same family); a targeted
recent-TNSM scan for any online cryptographic-delegation management paper. The gate is therefore
**affirmative on the closest prior art, pending two confirmatory reads** — a materially stronger
position than the provisional status at the start of this session.

## Recent-TNSM / adjacent scan (25 Oct 2026)

Searched (dates = this session): IEEE TNSM + "proxy re-encryption / delegation / access control /
key management / cloud data sharing" (2024-2025); TNSM + "cryptographic access control / key
rotation / revocation / scheduling / IIoT data sharing management" (2024-2025). Reading level:
abstract/snippet (not full text) except where noted. Findings:
- The field around this problem is dominated by cryptographic-PRIMITIVE papers: collusion-resistant
  and revocable PRE/ABE (e.g., ciphertext-dependent PRE "full-authority data sharing" / cdPRE,
  ePrint; attribute-based PRE with direct revocation, IEEE TDSC 2024; revocable IB broadcast PRE,
  TDSC; conditional PRE with ciphertext evolution, IEEE Access 2021), and KEY-ROTATION MECHANISMS
  (epoch-based CK rotation for blockchain-IoT, arXiv 2026; time-bound ABE revocation, SECRYPT 2024 /
  ePrint 2021/140; key-rotation management systems with scheduling dashboards, ICCWS 2024).
- These are either (a) new PRE/ABE primitives with revocation, or (b) rotation scheduling/lifecycle
  tooling. None is an ONLINE, arrival-driven, exposure-budget-constrained, intermittent-owner
  DELEGATION-ADMISSION controller; none models deferral against a forward exposure budget over a
  declared adversary coalition; none was found in TNSM matching this exact management problem.
- Limitations of this scan: abstract-level only; search-engine coverage, not a systematic TNSM
  table-of-contents sweep; a full systematic TNSM 2023-2025 ToC review is still owed before freezing
  the principal evaluation. cdPRE "full-authority data sharing" (collusion-resistant,
  ciphertext-dependent, O(1) sequential delegation) is the most relevant primitive lead and should
  be read in full as a candidate BACKEND (it would change the exposure rules), not as a management
  competitor.

## Overall gate status after this session
PROVISIONAL AND NARROWED. SACMAT 2025 (closest, full text) already has cached-key accounting and a
per-transition consistency check, so those are not our novelty. The surviving candidate contribution
is the ONLINE management problem (arrival-driven admit/defer + intermittent-owner authority +
forward exposure budget + preauth-gated rollover), demonstrated on one aligned instance
(docs/surviving_problem.md), not yet a general claim. Owed before freezing: TOPS 2022 full text; a
systematic TNSM ToC sweep; a full read of cdPRE as a candidate backend.
