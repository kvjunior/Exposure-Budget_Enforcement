# P3C changelog — bounded timed oracle + independent replay reference

Built on the verified p3b head. Adds the timed evaluation the paper's spine requires, and closes
the first of the spine's open items (a bounded timed oracle + a separate replay reference).

## New
- delegation_manager/timed_oracle.py: a bounded EXACT timed oracle. Exhaustive deepcopy-based search
  over the REAL ServiceSimulator (driven only through its public execute(action, view) API on
  independent copies; no private mutation, A3-respecting). Returns the minimum-cost schedule for a
  tiny timed instance; explicit branching/depth bounds; refuses rather than omitting legal actions.
  Enumerates all size-threshold delivery choices (the timed analogue of the untimed F02 repair).
  Deterministic cost = fragment*(committed deliveries) + rollover*(activations) + miss*(unserved).
- tests/differential/timed_independent_reference.py: a GENUINELY INDEPENDENT reference that does NOT
  import ServiceSimulator or the oracle's action generator. It re-derives, from the trace and demand
  alone, owner-availability, deadline feasibility, a serve cost lower bound, and a budget/fencing
  note, and returns an exact optimum for single-demand instances. This is the F06 independence
  requirement in the timed setting.
- tests/differential/timed_oracle_test.py: oracle optima replay feasibly in a fresh simulator; the
  independent reference agrees across servable / tight-deadline-unservable / owner-offline-unservable
  regimes; no online policy beats the optimum; INSIDE the feasible regime greedy ACHIEVES the optimum
  (gap 0) while blind rotate-first is sub-optimal (over-rolls).
- python/experiments/timed_oracle_pilot.py: timed gap-to-optimum across the three regimes; writes
  results/manifests/p3c_timed_oracle.json. Model simulation, not a performance measurement.
- Makefile: `make timed-oracle` runs the test and the pilot.

## Evidence produced (results/manifests/p3c_timed_oracle.json)
- generous_servable:          oracle 4, ref 4, greedy gap 0, blind gap 3.
- tight_deadline_unservable:  oracle 10 (miss), ref 10, greedy gap 4 (greedy wastes fragments on a
                              doomed demand; the oracle does not), blind gap 6.
- owner_offline_during_install: oracle 10, ref 10, greedy gap 0 (both can only miss).
No online policy beats the optimum; every oracle optimum replays feasibly and matches the reference.

## What this establishes (and does NOT)
- ESTABLISHES, in the TIMED model: an exact offline optimum exists and is independently checkable;
  greedy attains it inside the feasible regime; blind rotation and fragment-wasting are sub-optimal.
  This is the timed instance of the spine's "inside the feasible regime, a simple greedy policy
  attains the optimum" claim -- now with numbers, not just the untimed model.
- Does NOT establish: real cryptographic security (backend still abstract), a scalable regime
  characterization (instances are tiny by construction), or closed novelty. These remain open.

## Still open after P3C (unchanged from the spine)
- A concrete arrival/reservation model making "fencing" a measurable mechanism (not a scripted barrier).
- Whether greedy's optimality generalizes beyond tiny instances (a proof, not examples).
- Real timed PRE backend + verified receipts.
- Full-text SDAC-BBPP read and adjacent online-admission/privacy-budget literature.
- Submission-grade proofs of the dichotomy theorems.
