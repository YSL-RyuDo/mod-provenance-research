# Reproducing the Research Workflow

This repository preserves the code and metadata needed to trace Phase 1 through Phase 11. It intentionally does not redistribute third-party MOD/JAR payloads, cloned repositories, generated query packages, or external tools.

## 1. Environment

The system benchmark's tested Python environment is pinned in `requirements.txt` and duplicated verbatim in `results/phase9_environment_freeze.txt`.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The recorded WSL toolchain used Python 3.12.3, OpenJDK 11.0.31, and Git 2.43.0. Phase 9 performance measurements used Windows Python 3.10.6; therefore exact latency values are host- and environment-specific. See `reproducibility/ENVIRONMENT.md` before comparing timings.

## 2. Restore excluded inputs

Raw archives are not in Git. Use the tracked project/version identifiers, download URLs, content hashes, snapshot commits, and mapping audits to reconstruct them under the paths expected by each script. Important restoration metadata includes:

- `results/phase6a_fresh_corpus.csv`
- `results/phase6c_project_split.csv`
- `results/phase10a3_repository_snapshot_audit.csv`
- `results/phase10a3_class_to_java_mapping.csv`
- `results/phase9e_package_manifest.csv`

Verify downloaded files against their tracked SHA-1/SHA-256/SHA-512 fields before running downstream stages. Do not commit restored archives or extracted payloads.

## 3. Execution order

Most scripts are fixed-protocol research programs with path constants rather than general command-line applications. Run them from the repository root.

```text
Phase 1  collection
Phase 2  corpus/release freeze
Phase 3  legacy baselines
Phase 4  graph extraction
Phase 5  synthetic method exploration
Phase 6  fresh benchmark and frozen query/graph construction
Phase 7  calibration -> method freeze -> final TEST
Phase 8  post-hoc statistics and ablations
Phase 9  server correctness and performance
Phase 10 source/external-baseline compatibility
Phase 11 post-freeze multi-UNKNOWN robustness
```

The exact scripts, inputs, outputs, results, and freeze status for each phase are listed in `reproducibility/EXPERIMENT_INDEX.md`.

## 4. Freeze checks before evaluation

Before reproducing Phase 7H or any later analysis:

1. Confirm `results/phase7g_final_method_parameters.json` has SHA-256 `caad17257304d0ab198e01ef327f5acf918e6b8aab3f00e5272be3d20d3f8325`.
2. Confirm the Phase 6C split and Phase 6K/6L manifests match `reproducibility/FROZEN_ARTIFACT_SHA256.txt`.
3. Do not change thresholds, `alpha`, `lambda`, candidate-pool size, graph beta, boundary Top-R, or `Kmax` after examining TEST.
4. Keep evaluation-private labels inaccessible to the model/pipeline except at the scoring boundary.

## 5. Phase 9 services

The preserved service implementations are:

- `server/phase9a_server.py`: frozen reconstruction from precomputed scores;
- `server/phase9d_evidence_server.py`: identity-neutral evidence through gallery search and reconstruction;
- `server/phase9e3_package_server.py`: local materialized package through extraction and reconstruction;
- `server/phase9f_scalability_server.py`: gallery-size scalability service.

Run the matching Phase 9 benchmark script only after its server reports healthy. Preserve the benchmark scope when reporting latency: Phase 9C, 9D, and 9E3 include different portions of the pipeline.

## 6. Phase 10 external tools

Open-NiCad/NiCadCross is not vendored. Install it separately and reconstruct the tracked query/gallery source corpora from the Phase 10 mappings. The archived `phase10a4d_score_nicad_v1_buggy.py` is invalid and must not be used; use `scripts/phase10a4d_score_nicad.py`.

## 7. Phase 11 generated adapter

Run `scripts/phase11b_run_multi_unknown_robustness.py`. It reuses exact Phase 7B donor evidence and generates a temporary adapter in `scripts/_phase11b_phase7h_adapter_generated.py`. That active generated file is ignored because the tracked driver recreates it deterministically. The historical adapter used for the preserved run is under `archive/generated/` for audit.

## 8. Expected preserved endpoints

- Primary frozen TEST: `results/phase7h_final_test_summary.json`
- Statistical analysis: `results/phase8a_bootstrap_summary.json`, `phase8b_baseline_ablation_summary.json`, `phase8c_source_cluster_sensitivity_summary.json`
- System evaluation: `results/phase9b_server_correctness_summary.json` through `phase9f_gallery_scalability_summary.json`
- External baseline: `results/phase10a4f_nicad_paired_bootstrap_summary.json`
- Multi-UNKNOWN robustness: `results/phase11c_multi_unknown_summary.json`

If regenerated endpoint metrics differ, stop and compare frozen input hashes, environment versions, and the relevant detailed audit tables before interpreting the discrepancy.
