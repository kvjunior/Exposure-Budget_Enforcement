# IEEE TNSM research artifact — independent full-horizon repair (2026-10-28)

## Change summary

1. `p3e_workload_eval.run_policy`: replaced one-pass, truncated scheduling with a public-view,
   earliest-deadline-first driver that advances to the declared horizon, retries incomplete
   demands at subsequent opportunities and accounts for all productions and all demands.
2. `service_simulator._fence_rotate_or_drop`: made auto-rotation public-event IDs unique across
   streams, sequence numbers and revisions; previously simultaneous rotations could collide.
3. Added a regression suite `tests/differential/p3f_full_horizon_test.py`, covering the original
   failing heavy seeds (0/1/4), 3 regimes x 2 budgets x multiple seeds x 5 policies, and baseline
   differentiation. Added to `make reproduce`.
4. Regenerated 900 run-level results (30 seeds x 3 regimes x 2 budgets x 5 policies) and all
   reported tables and figures. Generated tables are `paper/results_generated.tex`, never hand-edited.
5. Replaced the misleading four-page claims with a qualified eight-page IEEE manuscript. Its
   model-level theorems are conditional and its empirical statements are limited to observed data.

## Reproduction

With Python 3.11+ and Matplotlib installed (model simulations do not depend on HPKE/Umbral):

```bash
make reproduce PROD=python
cd paper && pdflatex -interaction=nonstopmode -halt-on-error main.tex && pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

The model-side result can also be regenerated in separate stages:

```bash
python tests/differential/p3f_full_horizon_test.py
python python/experiments/p3e_workload_eval.py
python python/experiments/p3e_make_figures.py
python python/experiments/p3f_make_paper_tables.py
```

The CSV contains one row per policy, seed, budget and config and includes the `horizon`,
`simulation_end_tick`, `demands_total`, `pending`, `productions_scheduled`, `productions_completed`,
and `fence_drops` fields. Assert the complete-run invariants:

```
end_tick == horizon
served + expired + rejected == demands_total
pending == 0
productions_completed + fence_drops == productions_scheduled
```

### Independently performed here

- Complete-horizon differential tests: 3 tests PASS, including the original failing seeds.
- Corrected evaluator: returns exit 0; run-level data inspected to verify all 900 complete-run
  invariants and no budget violations under the combined policy in the tested configurations.
- Matplotlib figures regenerated from JSON and LaTeX tables regenerated from the same JSON.
- Numerous model tests passed in the available Python environment; historical crypto evidence is
  retained but independently executing HPKE and Umbral tests needs the respective pinned venvs.
- IEEE LaTeX compiles to an eight-page PDF, with no unresolved references or overfull warnings.

### Not independently verified here

The current working environment did not provide the pinned `hpke==0.3.2` and `umbral==0.3.0`
interpreters. Earlier P3F crypto-suite pass claims and logs are historical, not new independent
reruns. The evaluation runs the abstract backend, NOT HPKE/Umbral ciphertext operations.

## Scientifically important results and qualifications

- Heavy, B=0 (30 paired traces): public-log violation 0.700; production-only 0.200;
  admission-only 0.633; combined 0.000. No generalization beyond this generated model.
- Heavy, B=0 mean served requests out of FOUR: public-log 0.500; production-only 0.500;
  admission-only 0.467; combined 0.567. Therefore the earlier statement that protected operation
  necessarily reduces request completion was incorrect.
- Heavy B=1: combined may allow mean actual disclosure 0.833 units while staying <= B=1.
- The combined policy is NOT proven optimal, and production fencing is NOT logically necessary
  for every architecture. All proofs require actual-state/atomic commit mediation and closure.
- The simulation contains a single owner shared across four streams. Costs are illustrative
  integers, not measured latency, bandwidth, monetary cost or PRE microbenchmarks.

## Submission verdict: conditional / not yet externally validated

A real TNSM submission still benefits from (i) access to the complete SDAC-BBPP paper and expert
prior-art assessment, (ii) operationally calibrated arrivals/outages and measured crypto/service
costs, (iii) independent review of the assumptions and empirical claims, and (iv) final authorship,
ethical and format checks. These are disclosed rather than hidden; no universal deployment
confidentiality or camera-ready status is claimed.
