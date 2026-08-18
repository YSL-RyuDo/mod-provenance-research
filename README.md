# Server-Side Multi-Parent Provenance Reconstruction for Heterogeneous Game MOD Packages

Research repository for hierarchical multi-parent provenance reconstruction of heterogeneous game MOD packages.

## Preservation status (2026-08-18)

The complete research workflow from Phase 1 through Phase 11 is preserved in Git. The repository contains the analysis source, server implementations, frozen experiment definitions, public and evaluation-private metadata, core intermediate tables, predictions, audits, summaries, and paper reproduction assets. Raw MOD/JAR payloads and replaceable caches are intentionally not versioned.

| Phase | Purpose | Status |
|---|---|---|
| 1 | Pilot and real-MOD corpus collection | Complete |
| 2 | Corpus/release registry freeze | Complete |
| 3 | Path, content, bytecode, and package baselines | Complete |
| 4 | Dependency/resource graph construction | Complete |
| 5 | Synthetic multi-parent method exploration | Complete |
| 6 | Fresh 100-project benchmark, frozen split, queries, payload manifest, and graphs | Complete and frozen |
| 7 | Calibration, method freeze, and final TEST evaluation | Complete and frozen |
| 8 | Bootstrap, ablation, and source-cluster sensitivity | Complete |
| 9 | Server correctness, concurrency, end-to-end, and scalability evaluation | Complete |
| 10 | Source compatibility, StoneDetector packaging, and NiCadCross comparison | Complete |
| 11 | Controlled multi-UNKNOWN robustness benchmark and evaluation | Complete |

The primary TEST benchmark and Phase 7 parameters must not be retuned. Phase 11 is a post-freeze robustness analysis and does not replace or modify the primary TEST benchmark.

## Workflow

The execution order is:

```text
Phase 1 -> Phase 2 -> Phase 3 -> Phase 4 -> Phase 5
        -> Phase 6 (freeze benchmark)
        -> Phase 7 (calibrate, freeze, open TEST once)
        -> Phase 8 (post-hoc statistics)
        -> Phase 9 (server/system evaluation)
        -> Phase 10 (external compatibility/baseline)
        -> Phase 11 (post-freeze robustness)
```

Scripts are named `scripts/phase<stage>_*.py`. Server entry points are in `server/`, and the Phase 3 bytecode helper source is in `tools/phase3d/`. Run scripts from the repository root so their relative `results/` and `data/` paths resolve consistently.

Start with [`REPRODUCE.md`](REPRODUCE.md). The detailed script-to-input-to-output map, headline results, and freeze status are in [`reproducibility/EXPERIMENT_INDEX.md`](reproducibility/EXPERIMENT_INDEX.md).

## Frozen artifacts

The primary freeze anchors are:

- `results/phase6c_project_split.csv`
- `results/phase6k_query_manifest_private.csv`
- `results/phase6k_query_manifest_public.csv`
- `results/phase6l_materialized_private_manifest.csv`
- `results/phase6l_materialized_public_manifest.csv`
- `results/phase6l_graph_natural_public.csv`
- `results/phase6l_graph_connected_stress_public.csv`
- `results/phase7g_final_method_parameters.json`
- `results/phase7g_final_method_freeze_summary.json`
- `reproducibility/phase7g_final_method_parameters.json`

The frozen Phase 7 parameter file SHA-256 recorded by the final evaluation is `caad17257304d0ab198e01ef327f5acf918e6b8aab3f00e5272be3d20d3f8325`.

## Reproducibility environment

Environment records are described in [`reproducibility/ENVIRONMENT.md`](reproducibility/ENVIRONMENT.md), with a tested full Python environment in `requirements.txt`/`results/phase9_environment_freeze.txt`. The workflow requires Python and Java; Phase 10's external source baseline additionally requires a separately installed Open-NiCad/NiCadCross environment. External tools and downloaded repositories are not vendored.

## Data and publication safety

This repository must remain **private** while it contains evaluation-private mappings and held-out ground-truth metadata. Here, `private` means hidden from the evaluated model, not credentials. Do not publish those mappings as part of a public benchmark release without a deliberate disclosure review.

The following are intentionally excluded from Git:

- raw MOD/JAR archives, extracted source/payload trees, and generated query ZIP packages;
- cloned third-party repositories and tool caches;
- virtual environments, bytecode/classes, logs, timings, bootstrap replicate tables, and build by-products;
- credentials, tokens, machine secrets, and accidental local command-output files.

The exact preservation audit and baseline untracked-file classification are in [`reproducibility/TRACKING_AUDIT.md`](reproducibility/TRACKING_AUDIT.md) and `reproducibility/UNTRACKED_CLASSIFICATION.csv`.

## Historical artifacts

Known generated or invalid implementations are retained under `archive/` with an explanation. They are evidence of the research process and must not be used as the current method.
