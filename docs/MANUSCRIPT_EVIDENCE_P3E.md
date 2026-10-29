# Manuscript evidence package (P3E)

Everything needed to write the IEEE TNSM paper directly. Authoritative docs only; obsolete marked.

## Contribution statement
A characterization of the feasibility/limits of enforcing an irreversible whole-run DISCLOSURE BUDGET
for threshold-PRE delegated encrypted data under INTERMITTENT owners and DELAYED public reporting,
with a MANAGEMENT-PLANE / DATA-PLANE CO-DESIGN result (admission-side enforcement + production fence).
See docs/novelty_p3e.md for the "beyond standard admission/AC/rotation/budget" statement.

## Formal content
docs/proofs_p3e.md (authoritative): model, assumptions A1-A5, Thm 1 (restricted impossibility),
Cor 1 (sufficiency; fencing not necessary), Thm 2 (ongoing-invariant feasibility), Thm 3 (enforcement
realizes A-fence), Prop 4 (trade-off, experimental). Obsolete: OBSOLETE_dichotomy_spine_p3b.md;
superseded intermediate: dichotomy_spine_p3d.md (kept for the correction narrative).

## Experimental protocol + results
- Workload: python/experiments/p3e_workload_eval.py (30 seeds x 3 configs; 6 policies).
- Results: results/manifests/p3e_workload_eval.json (+ .csv); figures: results/figures/fig_*.png.
- Oracle: delegation_manager/timed_oracle.py; tests timed_oracle_test, p3e_multidemand_oracle_test.
- Counterexamples: tests/differential/p3d_counterexamples.py; enforcement tests p3e_enforcement_test.
- Fencing pilot: python/experiments/p3d_fencing_pilot.py.

## Baselines + fair-comparison justification
unfenced_publog (unsafe), production_only (fence, no admission enforcement), greedy_full (proposed),
blind_rotation, conservative, exact oracle (tractable instances). Policy notes and the same
enforcement/budget assumptions are recorded in the eval JSON "policy_notes".

## Prior-art comparisons (verified)
docs/novelty_p3e.md with reading levels; SACMAT 2025 / TOPS 2022 / FairShare full text, SDAC-BBPP
abstract+kw.

## Reproducibility + limitations
make reproduce; SHA256SUMS.txt; requirements-prod/legacy; docs/GO_NOGO_P3E.md blockers B1-B4;
limitations: t=0 demand release, abstract backend, model-level proofs, single/2-demand oracle.
