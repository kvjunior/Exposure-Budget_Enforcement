# P3F changelog — manuscript-completion correction pass

Targeted fixes to the P3E submission-critical issues found by independent review, then the manuscript.

## A. Corrections
- A1: production fencing now GENUINELY EXECUTES in the simulator (ServiceSimulator(production_fencing=
  True)): a record binding to an actually-reconstructible scope is rotated to a fresh scope (owner
  authority) or DROPPED; rotations/drops recorded. decide_fence logic is invoked in the production path.
- A2: time-advancing workload with STAGGERED demand releases and POST-GRANT production; fence
  activation (rotate/drop) is exercised.
- A3: baselines follow DIFFERENT execution paths via two toggles -- production_fencing and
  admission_enforcement. unfenced=(off,off), production_only=(on,off), admission_only=(off,on),
  greedy_full=(on,on), conservative=(on,on,refuse-all).
- A4: two disclosed-weight budgets (0 and 1) x 3 report-delay/availability configs x 30 seeds.
- A5: FIVE policies in the main eval (oracle separate); docs/tables corrected.
- A6: theorem-to-implementation corrected -- enforcing disclosed_weight<=B is the BUDGET INVARIANT;
  zero-disclosure A-fence is the B=0 special case (proofs_p3e.md Thm 3 updated).

## B. Validated results (30 seeds; results/manifests/p3e_workload_eval.json + .csv; figures/)
Headline (heavy, B=0): unfenced viol 0.13 (both breaches); production_only viol 0.10 (fails on
B-retro); admission_only viol 0.07 (fails on B-prod); greedy_full viol 0.00 (safe on both);
conservative viol 0.00 but serves 0. Neither single mechanism suffices; the combination does, at a
measured service cost. Post-grant production occurs; the baselines take different paths; safe policies
respect their budgets; a positive budget absorbs one unit of collateral (Cor 1 M3).

## C. Literature (docs/novelty_p3e.md)
SDAC-BBPP (abstract), TOPS/SACMAT/FairShare (full text), plus US Patent 11,836,269 (resettable
query-count budget -> re-encryption; distinguished from our irreversible disclosure budget). No
verified source poses our problem. TNSM full ToC sweep still partial.

## D. Manuscript
paper/main.tex (IEEEtran journal), paper/refs.bib (verified DOIs), paper/main.pdf (4 pages, 2 figures).

## Verification
23 PROD suites + 2 Umbral crypto suites + HPKE smoke pass; make reproduce passes; manuscript compiles.
