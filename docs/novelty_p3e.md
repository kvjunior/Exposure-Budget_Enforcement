# Focused novelty check (P3E, Task 5)

Reading levels recorded per source. "Full text" = substantial sections read; "abstract+kw" =
abstract and keyword/metadata; "metadata" = citation only.

| Source | DOI | Reading | What it does | Relation to our problem |
|---|---|---|---|---|
| SDAC-BBPP (TNSM 2024) | 10.1109/TNSM.2024.3371521 | abstract+kw (IEEE paywall) | CP-ABE with verifiable OUTSOURCED decryption; multi-chain policy hiding; a supervisory policy with DYNAMIC TRUST ASSESSMENT + smart contracts that DETECT and PUNISH malicious behavior. "Dynamic" = dynamic regulation/trust, reactive. | NOT our problem. No request arrival process, no forward EXPOSURE BUDGET, no intermittent-owner authority, no threshold-fragment reconstructibility/disclosure ledger. Its trust assessment punishes AFTER detection; we PREVENT disclosure before it (admission + production enforcement). The last-closest TNSM paper; now read at abstract level, it does not subsume us. |
| TOPS 2022 | 10.1145/3474056 | full (prior session) | Design-time architecture SELECTION (which CAC entities in which domains) as a MOCOP. | Different decision (placement, design-time) vs our online admit/defer/roll under a budget. Complementary. |
| SACMAT 2025 | 10.1145/3734436.3734452 | full (prior session) | Trust-driven reduction of cryptographic work; cached-key status tracking; decide when rotation/re-encryption is needed. | Closest on cached keys, but no arrival process, no online admission, no forward budget, no intermittent owners. Cached-key tracking is prior art; our ONLINE management + the impossibility/feasibility characterization is not. |
| FairShare (TNSM 2023) | 10.1109/TNSM.2023.3239832 | full (prior session) | Fair/accountable PRE exchange on blockchain; single-proxy; always-online delegator. | A fixed protocol, not an online management problem; soundness later disputed (FairShare+ 2026). A mechanism-layer citation/baseline, not a competitor. |
| Online admission control / budgeted resource mgmt / privacy-budget | (area) | abstract-level survey | Admission control with resource/regret budgets; DP privacy-budget accounting. | Our "budget" is an IRREVERSIBLE disclosure budget whose growth is caused by CRYPTOGRAPHIC scope-key reconstruction under delayed public reports -- not a renewable resource or a composition budget. The impossibility is information-structural (delayed reports + irreversibility), specific to this setting. Related in spirit, distinct in mechanism. |
| Threshold-PRE / NuCypher-Umbral, JEDI | (various) | prior sessions | Threshold PRE primitives; hierarchical time-scoped delegation. | Mechanisms we build on, not management-layer competitors. |

## Honest contribution statement (beyond standard online admission / AC enforcement / key rotation / budget mgmt)

What is NEW is NOT a primitive, nor generic admission control, nor key rotation. It is a
CHARACTERIZATION of the feasibility/limits of enforcing an IRREVERSIBLE whole-run disclosure budget
for threshold-PRE delegated data under INTERMITTENT owners and DELAYED public reporting, with a
MANAGEMENT-PLANE / DATA-PLANE CO-DESIGN result: (i) an online public-log controller is PROVABLY
INSUFFICIENT in a precise regime (Thm 1); (ii) feasibility requires an ONGOING invariant enforced
across BOTH the production fence (data plane) and an admission-side enforcement boundary (management
plane) that has truth access the public controller lacks; (iii) the retroactive-disclosure
phenomenon (a later grant discloses earlier records via scope-key-opens-everything + observability
gap) shows the invariant must be ONGOING, and is enforced, not just detected; (iv) fencing is
SUFFICIENT but NOT NECESSARY (admission refusal / budget absorption are alternatives); (v) an
evaluation quantifying the COST OF SAFETY (service loss) and showing production-fencing ALONE is
INSUFFICIENT. We found no prior work, in TNSM 2022-2026 or the Berlato line, posing or resolving
this exact problem.

## Caveat
This is a narrow, defensible contribution, model-level and conditional on closure soundness. It is
NOT a universal impossibility and NOT a new cryptographic guarantee. SDAC-BBPP and several 2024-2026
sources were read at abstract level only (paywalls); a full systematic TNSM ToC sweep is still owed.

## P3F focused re-check (additional)
- US Patent 11,836,269 ("Protection of data of database clients from persistent adversaries"):
  a database proxy maintains a "security budget" (max query threshold) and RE-ENCRYPTS when the
  budget falls below a threshold; the budget is RESET on re-encryption. Reading: claims+abstract.
  Closest "budget-triggered re-encryption" prior art. DIFFERENT from ours: a RESET-ABLE query-count
  budget (renewable) vs our IRREVERSIBLE cumulative DISCLOSURE ledger; database-query proxy vs
  delegated encrypted-data service with threshold-PRE reconstructibility and intermittent owners;
  no online admission/deferral, no production fencing, no management/data-plane co-design. Cite as
  related budget-driven re-encryption, clearly distinguished.
- Additional PRE/AB-PRE/threshold-PRE items (time-based AB-PRE 2024; KeRePRE 2025; TDSC 2025
  sanitizable cross-domain AC) are mechanism-level schemes, not the online management problem.
- Conclusion unchanged: no verified source poses the online whole-run exposure-budget enforcement
  problem with intermittent owners and management/data-plane co-design. TNSM full ToC sweep still
  partial (abstract-level); SDAC-BBPP full text still paywalled.
