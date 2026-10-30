# P3B timed-model integration, P3A inputs and preserved Slice 2.2.1 research checks.
# modelsim is a legacy model diagnostic; smoke is real HPKE, not a timed PRE evaluation.
# reproduce runs the full-horizon publication pipeline; pilot remains a legacy placeholder.
#
# Two isolated environments (see docs/decisions/0002_backend_selection.md):
#   PROD venv   : cryptography 43 + hpke 0.3.2  (measured HPKE path)   -> requirements-prod.txt
#   LEGACY venv : cryptography 3.4.8 + umbral 0.3.0 (PRE witnesses)    -> requirements-legacy.txt
# Set PROD and LEGACY to the two interpreters, or let the defaults point at the repo venvs.

PROD   ?= .venv-prod/bin/python
LEGACY ?= .venv-legacy/bin/python

.PHONY: check timed-check timed-pilot timed-oracle p3d p3e smoke modelsim pilot reproduce env

check:
	@echo "== slice-1.1 independent counterexamples + typed guard [PROD] =="
	$(PROD) tests/review_slice11.py --source . --family-api specs --output results/manifests/review_slice11.json
	$(PROD) tests/differential/typed_guard_test.py
	@echo "== differential + witness (model vs independent reference) [PROD] =="
	$(PROD) tests/differential/rust_python_closure.py
	@echo "== exposure-constraint admission check [PROD] =="
	$(PROD) tests/differential/exposure_check_test.py
	@echo "== checked-action: coordinate-wise budget (R2) + pre-execution veto (R3) [PROD] =="
	$(PROD) tests/differential/checked_action_test.py
	@echo "== online-policy witness + non-interference (R4) [PROD] =="
	$(PROD) tests/differential/online_witness_test.py
	@echo "== authority + fresh rollover (R5,R6) [PROD] =="
	$(PROD) tests/differential/authority_rollover_test.py
	@echo "== temporal authorization: expiry-at-cutoff (R7) + post-revocation (R8) [PROD] =="
	$(PROD) tests/differential/temporal_authorization_test.py
	@echo "== malformed/adversarial crypto negatives [PROD] =="
	$(PROD) tests/adversarial/malformed.py
	@echo "== retained-fragment PRE witnesses [LEGACY] =="
	$(LEGACY) tests/adversarial/retained_fragments.py
	@echo "== mixed-fragment capability (R1), grounded in real Umbral [LEGACY] =="
	$(LEGACY) tests/adversarial/mixed_fragments.py
	@echo "== R1-R8 regression reproducer [PROD: R2-R8] =="
	$(PROD) tests/regression_r1_r8.py --skip R1 --output results/manifests/regression_r2_r8.json
	@echo "== R1-R8 regression reproducer [LEGACY: R1] =="
	$(LEGACY) tests/regression_r1_r8.py --only R1 --output results/manifests/regression_r1.json
	@echo "== P2 model: transitions, executor, disclosure ledger [PROD] =="
	$(PROD) tests/differential/p2_model_test.py
	@echo "== P2 baselines + exact oracle, gap-to-optimum [PROD] =="
	$(PROD) tests/differential/p2_baselines_oracle_test.py
	@echo "== P2 nontriviality: state does not collapse to a flag [PROD] =="
	$(PROD) tests/differential/sufficient_state_test.py
	@echo "== foundation verification: ledger/transitions/executor/observation [PROD] =="
	$(PROD) tests/differential/foundation_verification_test.py
	@echo "== strengthened surviving instance: 2 choices / preauth split / threshold nontriviality [PROD] =="
	$(PROD) tests/differential/surviving_strengthened_test.py
	@echo "== slice 2.1 regression: S2-01..S2-07 corrected contracts [PROD] =="
	$(PROD) tests/differential/slice21_regression_test.py
	@echo "== Slice 2.2.1 exact-plan / full-domain oracle / reference authority [PROD] =="
	$(PROD) tests/differential/slice221_contract_test.py
	@echo "== P3A typed service time / immutable demand / causal public log [PROD] =="
	$(PROD) tests/differential/timed_inputs_test.py
	@echo "== P3B causal timed MODEL service / authority / retained effects [PROD] =="
	$(PROD) tests/differential/timed_service_test.py
	@echo "ALL CHECKS PASSED"

timed-check:
	$(PROD) tests/differential/timed_inputs_test.py
	$(PROD) tests/differential/timed_service_test.py

timed-pilot:
	$(PROD) python/experiments/timed_management_pilot.py

smoke:
	@echo "== end-to-end HPKE lifecycle smoke [PROD] (NOT a performance result) =="
	$(PROD) python/experiments/smoke_lifecycle.py

env:
	$(PROD) scripts/check_environment.py

modelsim:
	@echo "== P2 baselines vs exact oracle (model simulation, not a measurement) [PROD] =="
	$(PROD) python/experiments/baselines_vs_oracle.py
	@echo "== aligned surviving-problem instance [PROD] =="
	$(PROD) python/experiments/surviving_instance.py
	@echo "== controller vs baselines vs oracle [PROD] =="
	$(PROD) python/experiments/controller_comparison.py

pilot:
	@echo "publication pilot not implemented (use timed-pilot for scripted model traces)"; exit 2

reproduce:
	@echo "== FULL-HORIZON verified reproducible model simulation =="
	$(PROD) tests/differential/p3f_full_horizon_test.py
	$(PROD) tests/differential/timed_oracle_test.py
	$(PROD) tests/differential/p3d_counterexamples.py
	$(PROD) tests/differential/p3d_fencing_test.py
	$(PROD) tests/differential/p3e_enforcement_test.py
	$(PROD) tests/differential/p3e_multidemand_oracle_test.py
	$(PROD) python/experiments/timed_oracle_pilot.py
	$(PROD) python/experiments/p3d_fencing_pilot.py
	$(PROD) python/experiments/p3e_workload_eval.py
	$(PROD) scripts/verify_full_horizon_results.py
	$(PROD) python/experiments/p3e_make_figures.py
	$(PROD) python/experiments/p3f_make_paper_tables.py
	@echo "reproduce: complete-horizon pipeline passed; results in results/manifests, figures in results/figures"

timed-oracle:
	$(PROD) tests/differential/timed_oracle_test.py
	$(PROD) python/experiments/timed_oracle_pilot.py

p3d:
	$(PROD) tests/differential/p3d_counterexamples.py
	$(PROD) tests/differential/p3d_fencing_test.py
	$(PROD) python/experiments/p3d_fencing_pilot.py

p3e:
	$(PROD) tests/differential/p3e_enforcement_test.py
	$(PROD) tests/differential/p3e_multidemand_oracle_test.py
	$(PROD) python/experiments/p3e_workload_eval.py
	$(PROD) scripts/verify_full_horizon_results.py
	$(PROD) python/experiments/p3e_make_figures.py
