# Coordinated Exposure-Budget Enforcement for Encrypted Data Services with Intermittent Owners

**Anonymous research artifact for IEEE Transactions on Network and Service Management (IEEE TNSM).**  
Repository: <https://anonymous.4open.science/r/Exposure-Budget_Enforcement-7A03/>

This repository accompanies the manuscript *Coordinated Exposure-Budget Enforcement for Encrypted Data Services with Intermittent Owners*. It provides the model, policy/enforcement implementation, tests, synthetic event-driven workloads, raw per-run results, aggregate results, manuscript figures, and the anonymous paper source.

## What the artifact evaluates

The system separates (1) an online public-observation controller and (2) a privileged actual-state enforcement boundary. It models retained delegation capabilities, scope reconstructibility, delayed reporting, first disclosure, record production, owner availability and budget-constrained capability commits.

The evaluation isolates two ways a cumulative disclosure budget can be exceeded:

- **Production-side exposure:** a later unauthorized record is produced while its scope is reconstructible by a declared coalition.
- **Admission-side exposure:** a later grant makes an existing, previously unreported record openable to a coalition outside the grant's authorized record range.

Five policies are evaluated: `unfenced`, `production_only`, `admission_only`, `greedy_full` (combined checks), and `conservative` (reject all grants). The combined mechanism performs actual-state admission checks and production fencing. Security conclusions are conditional on the declared coalition family, capability-closure assumptions, fresh independent scopes, and complete atomic mediation of the modeled transitions.

## Quick start — reproduce the article's synthetic experiment

**Requirements:** Python 3.11 or later, `make` (on systems where available), and the Python libraries in `requirements-reproduce.txt`. The full-horizon simulation uses an abstract timed capability backend and **does not require** the separate HPKE or Umbral environments.

```bash
python3 -m venv .venv-repro
. .venv-repro/bin/activate
python -m pip install -r requirements-reproduce.txt
make reproduce PROD=python
python scripts/verify_full_horizon_results.py
python data/verify_results.py
```

To run without Make:

```bash
python tests/differential/p3f_full_horizon_test.py
python python/experiments/p3e_workload_eval.py
python scripts/verify_full_horizon_results.py
python python/experiments/p3e_make_figures.py
python python/experiments/p3f_make_paper_tables.py
```

The driver overwrites the evaluation JSON/CSV and generated figure/table assets with outputs for the fixed experiment configuration. Run from the **repository root**. The shipped 900-run CSV is also available as `data/full_horizon_results.csv`.

### Expected workload and validation

| Property | Value |
|---|---|
| Workload regimes | `light`, `heavy`, `intermittent` |
| Disclosure budget | `B=0`, `B=1` model units |
| Paired random seeds | 0–29 in each regime/budget cell |
| Compared policies | 5 |
| Policy–trace run records | 3 × 2 × 30 × 5 = **900** |
| Demands per run | 4 |
| Scheduled productions per run | 8 |
| Total policy-run demand opportunities | 3,600 |
| Total policy-run production opportunities | 7,200 |

The independently checked whole-run invariants are:

```text
simulation_end_tick == horizon
pending == 0
served + rejected + expired == demands_total
productions_completed + fence_drops == productions_scheduled
violation == (actual_disclosed > budget_disclosed)
```

The verification scripts also reject duplicate policy/seed/cell records and recheck the aggregate means in JSON against the 900 CSV rows.

### Example reproduced outcome

For the `heavy_B0` cell (30 paired traces per policy), observed budget-violation proportions are:

| Policy | Violating runs | Proportion |
|---|---:|---:|
| `unfenced` | 21 / 30 | 0.700 |
| `production_only` | 6 / 30 | 0.200 |
| `admission_only` | 19 / 30 | 0.633 |
| `greedy_full` | 0 / 30 | 0.000 |
| `conservative` | 0 / 30 | 0.000 |

The reported outcomes are **simulation observations within the specified model**, not empirical estimates of real deployment compromise probability or measured cryptographic latency.

## File map

| Directory / file | Purpose |
|---|---|
| `delegation_model/` | State, capabilities, event, authorization, and time semantics |
| `delegation_manager/` | Policies, management logic, guarded commits, production fencing, and bounded oracles |
| `delegation_crypto/` | Separate cryptographic adapters and functional integration layer |
| `python/experiments/p3e_workload_eval.py` | Authoritative full-horizon synthetic workload and policy evaluation |
| `python/experiments/p3e_make_figures.py` | Generates additional research plots from the JSON results |
| `python/experiments/p3f_make_paper_tables.py` | Generates paper-table values from the JSON results |
| `tests/differential/p3f_full_horizon_test.py` | Regression tests for staggered demand arrivals, complete horizons, and baselines |
| `tests/differential/` | Model, safety, adversarial and timed-oracle tests |
| `tests/adversarial/` | Cryptographic functional checks, in separately provisioned environments |
| `scripts/verify_full_horizon_results.py` | Checks all 900 completed runs and exact JSON aggregates |
| `data/full_horizon_results.csv` | Immutable snapshot of the 900-run per-trace results |
| `data/verify_results.py` | Additional independent data consistency assertions |
| `results/manifests/p3e_workload_eval.csv` | Reproducible run-level results (900 rows) |
| `results/manifests/p3e_workload_eval.json` | Aggregates, per-policy metrics and workload configuration |
| `results/figures/` | Generated research plots; the approved manuscript dashboard is in `paper/figures_vector/` |
| `paper/main.tex`, `paper/main.pdf` | Anonymous article with the latest title, four selected figures, and three tables |
| `paper/full_text.txt` | Searchable plain-text version extracted from the compiled manuscript |
| `paper/refs.bib`, `paper/figures_vector/` | Bibliography and final manuscript figure assets |
| `docs/FINAL_VERIFICATION_AND_READINESS.md` | Current full-horizon repair and test-status assessment |
| `docs/PROOFS_FULL_HORIZON.md` | Formal model, assumptions, and bounded claim statements |
| `docs/release/` | Release scope, environment, and integrity information |
| `frozen_slice_*/`, `legacy_diagnostics/` | Historical source snapshots and independent diagnostic code, retained for provenance |

**Version note:** some historical `docs/` and frozen slices describe earlier research branches, incomplete gates, or former paper drafts. The current manuscript is `paper/main.tex`; the current evaluation is `python/experiments/p3e_workload_eval.py` with `results/manifests/p3e_workload_eval.*`. Historical documents are provided for provenance and do not supersede these files.

## Functional cryptographic tests (separate from simulation)

The timed simulation models capability usability and abstract reconstructibility. The project also retains functional tests involving HPKE and Umbral, which require **separate, potentially incompatible Python environments**:

```bash
python3 -m venv .venv-prod
.venv-prod/bin/python -m pip install -r requirements-prod.txt
python3 -m venv .venv-legacy
.venv-legacy/bin/python -m pip install -r requirements-legacy.txt
make check PROD=.venv-prod/bin/python LEGACY=.venv-legacy/bin/python
make smoke PROD=.venv-prod/bin/python
```

See `docs/decisions/0002_backend_selection.md` for backend choices. These functional checks support selected crypto implementation paths; **the article's 900-run evaluation does not call HPKE/Umbral for encryption/decryption timing**. Installability can vary across Python versions and binary wheels. The code supplied here does not contain operational deployment traces or empirical cloud-latency benchmarks.

## Build the paper

```bash
cd paper
pdflatex -halt-on-error -interaction=nonstopmode main.tex
pdflatex -halt-on-error -interaction=nonstopmode main.tex
```

The compiled reference list (`paper/main.bbl`) is included. To rebuild it after editing the bibliography, run `bibtex main` between LaTeX passes if needed. The author's name and affiliation are deliberately replaced by an anonymous review placeholder; the figure and table references use native LaTeX labels.

## Availability and reproducibility limits

The service controller observes delayed public reports; the trusted boundary sees the actual records and retained capabilities at a commit point. Results concern an abstract finite coalition/capability model with synthetic demand, outages, report delays, and **declared model-unit costs**. The security characterization relies on complete and atomic mediation of the specified events. A distributed deployment would need to implement the corresponding transaction and data-source integrity contracts. Greedy optimality is **not** claimed for unrestricted multi-demand workloads.

Raw data, scripts, fixed seed configuration and validation tests are supplied to reproduce numerical claims. The 30 paired seeds are deterministic simulation inputs, not field observations. The paper's original Fig. 4 is retained in `paper/figures_vector/experimental_dashboard.pdf`; other generated plots in `results/figures/` are supporting evidence.

## Integrity and version details

`SHA256SUMS.txt` contains checksums for all released files (except itself). Check with:

```bash
sha256sum -c SHA256SUMS.txt
```

For exact data identity, `data/full_horizon_results.csv` and `results/manifests/p3e_workload_eval.csv` have matching bytes in this release. Source and research logs document the status of functional tests; this repository does not claim newly completed HPKE/Umbral reruns.

## Citation / contact

For an anonymous review, cite the manuscript title and the anonymous repository URL above. Author attribution, affiliations and public release metadata can be added after the review process, subject to the venue's double-blind requirements. No new license is granted by this README; publication and redistribution permissions remain with their respective rights holders.
