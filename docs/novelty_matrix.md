**Gate status (slice 2, corrected after SACMAT 2025 full-text read): PROVISIONAL AND NARROWED — NOT affirmative.**
Correction: SACMAT 2025 (Brunello et al., read in full) is the CLOSEST prior work and is materially
closer than previously credited. It tracks cached-key state (a four-status model incl. "hide" for
possibly-cached keys), reasons about user-cloud collusion, and decides whether expensive rotation/
re-encryption is needed now vs superfluous under a tunable trust model, with a Prolog consistency
check for RBAC correctness/safety. So "cached-key risk" and "per-transition consistency check" are
NOT our novelty. ALSO corrected: ASIA CCS 2020 and TOPS 2022 are separate versions; only ASIA CCS
2020 was read in full (TOPS 2022 comparison UNRESOLVED). The surviving candidate differences
(online sequential admit/defer over a request arrival process; intermittent owner authority +
preauthorization; a quantitative forward exposure budget over a declared coalition family + an
irreversible disclosure ledger; threshold/fragment-structured exposure) are stated in
docs/surviving_problem.md with an aligned small instance, and must be hardened before any novelty
claim. Keep novelty PROVISIONAL. Remaining reads: TOPS 2022 full text; a targeted recent-TNSM scan.
An online controller cannot beat the matched-model offline optimum; usefulness is a gap-to-optimum
claim.

---

# Novelty comparison — OPEN, correction branch 1.2

This records evidence status, not a certificate that the proposed work is novel. Full-text
absence claims require the actual identified version and relevant sections, not an abstract.

| Work | Verified relationship / current task | Evidence status |
|---|---|---|
| NuCypher KMS, arXiv:1707.06140 | Scoped/time-dependent delegation, collusion and rotation are existing ideas. Compare the exact management decisions and retained-material assumptions. | Primary PDF identified; prior relevant reading; final formal comparison still required. |
| Umbral implementation | The chosen capability rules must match this actual primitive and version, including mixed fragments and generation matching. | Real witnesses run in the isolated supplied environment; this is not a primitive security proof. |
| Berlato TOPS, 10.1145/3474056 | Closest architecture/trust/performance optimization framing; do not infer absence of dynamic concerns from metadata. | Publisher fetch blocked. Primary companion and author thesis located; full comparison unresolved. |
| Berlato JNCA 2025, 10.1016/j.jnca.2025.104246 | Cached-key revocation and architecture optimization are already treated. Compare our precise online decision variables and information constraints. | Actual author PDF reachable; relevant Sections 6.3, 7 and limitations inspected in independent review; complete comparison still open. |
| Berlato and collaborators, SACMAT 2025 trust/protection/performance | Additional close work to compare rather than assuming no prior runtime/trust trade-off exists. | Author PDF identified; substantive comparison pending. |
| JEDI, USENIX Security 2019 | Scoped/time-bounded delegation is not a new contribution here. | Primary full text identified; exact model comparison pending. |
| Recent relevant TNSM work including FairShare | Establish management readership relevance and distinguish the actual objective/baselines. | Search/read/verify before final manuscript; no gap is asserted from an abstract. |

## Remaining gate

A candidate difference is online management over retained-capability history, public coalition
reach, intermittent owner authority and explicit service/exposure constraints. Establish that
this is a substantive problem: does a completed threshold grant always expose its scope under
the declared family, does sufficient historical state reduce to one flag, and do ordinary
rotation/per-record keys/greedy or rolling-horizon methods suffice? Negative results should
change the contribution, not be hidden.

A generic solver call or renamed heuristic is insufficient. Compare online methods against
strong causal baselines and the GAP TO a matched-model exact offline optimum; do not claim an
online method beats that optimum. C10 is empirical usefulness; C11 needs a conditional argument
over every allowed transition. A backend with different collusion guarantees needs different
capability rules even when the management API is reused.

Primary leads:
- https://arxiv.org/pdf/1707.06140
- https://dl.acm.org/doi/10.1145/3474056
- https://st.fbk.eu/complementary/TOPS2020_2/
- https://iris.unige.it/retrieve/65b859f0-d1ba-4a3d-96c2-80802eb89416/phdunige_4770592.pdf
- https://stefano.berlato.it/publications/JNCA2025.pdf
- https://stefano.berlato.it/publications/SACMAT2025.pdf
- https://www.usenix.org/system/files/sec19-kumar-sam.pdf
