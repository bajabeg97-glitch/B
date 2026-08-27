# BAJA MAX Autonomous Premium R5 Checkpoint

## Implemented in R5
- Selective event/dimension rollback for mutation-budget violations.
  - Velocity rolls back at individual note-on level.
  - Timing/gate roll back through absolute-event maps followed by safe SMF delta rebuild.
  - Full pre-performance rollback remains a fail-safe only if selective recovery cannot prove safety or the Factory evidence metric regresses materially.
- Musical Decision Brain register OOD signal using the resolved Factory Sound key envelope.
- Confidence bands remain explicitly non-probabilistic until a labeled calibration corpus exists.
- Resumable/sharded complete-stress runner.
- Removed circular stress dependency: runtime stress produces COMPLETE_STRESS_RESULT first; meta release/integrity tests consume it afterwards.
- Direct `python tools/run_complete_stress.py` entry point now resolves the project root without manual PYTHONPATH.
- Structural A-Z process certification no longer requires final release evidence when explicitly run with `run_regression=False`; production mode still requires release audit.

## Verified in this checkpoint
- Selective rollback / Brain / authority focus: 22 PASS.
- Brain + optimizer safety focus after register OOD: 21 PASS.
- Process/stress architecture regression: 19 PASS.
- Earlier R4 broad regression baseline: 376 functional/regression PASS before these R5 changes.

A later broad optimizer/verifier trace run exceeded the execution window before producing a final summary; it is not claimed as PASS or FAIL here.

## Fresh stress status
`PUBLIC_API_STRESS_MANIFEST.json` was regenerated for R5:
- modules: 114
- public functions: 365
- unclassified: 0

The original one-process complete stress runner exceeded the execution window. R5 replaces it with resumable sharding. Initial runtime stress shards completed successfully before the current checkpoint, but all shards have not yet been finalized into a fresh `COMPLETE_STRESS_RESULT.json`.

Therefore:
- SOFTWARE CHECKPOINT: VALIDATED FOR CHANGED R5 LAYERS
- FINAL PREMIUM RELEASE GATE: PENDING FRESH COMPLETE SHARDED STRESS
- PHYSICAL PA800 HARDWARE EVIDENCE: EXTERNAL / PENDING
