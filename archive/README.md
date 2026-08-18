# Archived Research Artifacts

This directory preserves generated or invalid historical implementations that are useful for auditability but are not current executable sources of truth.

## `generated/`

`_phase11b_phase7h_adapter_generated.py` was produced deterministically by `scripts/phase11b_run_multi_unknown_robustness.py` from the frozen Phase 7H implementation. It is retained as the exact historical adapter used for the recorded Phase 11 run. Future runs regenerate the active `scripts/_phase11b_phase7h_adapter_generated.py`, which is ignored.

## `failed_experiments/`

`phase10a4d_score_nicad_v1_buggy.py` is the superseded first NiCad scoring implementation. It used the internal source identity rather than the frozen benchmark `ground_truth_label` for held-out components and calculated K without the collapsed `UNKNOWN` group. It must not be used to reproduce reported Phase 10 results. The corrected implementation remains `scripts/phase10a4d_score_nicad.py`.
