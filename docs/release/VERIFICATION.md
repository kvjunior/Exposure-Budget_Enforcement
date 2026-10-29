# Release verification record — 2026-10-30

## Completed in this packaging pass

- New-title IEEE manuscript compiled with two `pdflatex` passes to 10 pages, with the bibliography and graphics included.
- Verified the PDF's first page displays the new title.
- Cross-checked the raw 900-row dataset against the aggregate JSON using `python3 scripts/verify_full_horizon_results.py` (PASS).
- Independently checked 900-run terminal-accounting invariants and headline values with `python3 data/verify_results.py` (PASS).
- Executed `python3 tests/differential/p3f_full_horizon_test.py`: 3 tests PASSED, including regression seeds 0, 1 and 4.
- Confirmed `data/full_horizon_results.csv` and `results/manifests/p3e_workload_eval.csv` are byte-identical in the released snapshot.
- Confirmed paper caption and cross-reference labels are present for Figs. 1–4 and all three tables.

## Limitations of this packaging pass

- A fresh `make reproduce PROD=python3` was attempted. The tests and timed pilot stages completed, but the full 900-run evaluation exceeded the container's execution window. Its previously generated, internally validated results remain included; this attempt is **not** recorded as an end-to-end pass.
- The separately pinned HPKE and Umbral functional suites were **not** rerun because their libraries are unavailable in this packaging environment. Their test source and dependency files are included.
- The supplied anonymous repository URL is an external publication destination. This file package has **not** been uploaded to that destination by the assistant.

The evaluation is an abstract timed simulation. Costs are declared model units; no deployment-level latency or live cryptographic timing is reported.
