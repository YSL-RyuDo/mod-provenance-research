# Experiment Index: Phase 1-11

This index records the preserved research flow as of 2026-08-18. Paths are relative to the repository root. `Frozen` means that downstream evaluation must consume the artifact without changing the split, labels, parameters, or protocol.

## Phase-level map

| Phase | Scripts / service | Primary input | Primary output | Headline result | Freeze status |
|---|---|---|---|---|---|
| 1 | `phase1_collect.py`, `phase1b_collect_real_mods.py` | Public repository and Modrinth project metadata | `dataset_*.csv`, `phase1*_summary.json` | Pilot: 10 repositories. Real-MOD corpus: 30 mods, 5,732 code, 888 structured, and 357 image files. | Exploratory snapshot; inputs later formalized in Phase 2. |
| 2 | `phase2a_freeze_corpus.py`, `phase2b_build_registry.py`, `phase2c_build_release_registry.py` | Phase 1 corpus, repository commits, public release metadata | corpus and release registries, duplicate audits, `phase2*_summary.json` | 30/30 commit snapshots resolved; 30/30 release downloads registered; 7,677 release components and no cross-MOD duplicate group in that registry. | Phase 2A source snapshots frozen for the legacy corpus. Raw downloads excluded. |
| 3 | `phase3a_real_version_drift.py` through `phase3e_package_aggregation.py`; `tools/phase3d/JavapBatch.java` | Phase 2 releases and historical versions | path/content/bytecode/package raw and summary CSVs, `phase3*_summary.json` | OPCODE_CONTEXT confidence voting reached package top-1 unique 0.578 and top-5 0.911 across 45 historical packages. | Baseline definitions preserved; exploratory rather than final TEST. |
| 4 | `phase4a_extract_dependency_graph.py`, `phase4b_enrich_resource_graph.py`, `phase4c_resource_reference_diagnostic.py` | Release registries and extracted component metadata | graph diagnostics, unresolved-reference tables, `phase4*_summary.json` | 25,987 total enriched edges; median largest-component rate 0.818. | Graph extraction protocol preserved; not final TEST graph. |
| 5 | `phase5a_historical_graph_diagnostic.py` through `phase5h_fused_hierarchical.py` (including `phase5c2_*`) | Phase 3/4 evidence and synthetic multi-parent queries | multi-parent raw/summary tables and `phase5*_summary.json` | On the synthetic CLEAN track, fused hierarchical component accuracy was 0.405 and parent-set F1 was 0.504 over the 150-query test portion. | Method exploration only; final decisions are not frozen here. |
| 6 | `phase6a_collect_fresh_corpus.py` through `phase6l_materialize_and_freeze_graph.py` | Fresh public metadata/releases, historical registries, extracted payloads | `phase6c_project_split.csv`, Phase 6K manifests/ground truth, Phase 6L payload manifests/graphs, audits and summaries | 540 frozen queries, 3,780 materialized components, all source hashes verified, no exact-stage gallery collisions, and all connected-stress graphs connected. | **Frozen benchmark.** Split, queries, payload hashes, public/private manifests, and graph tracks must not change. Payload bytes remain local. |
| 7 | `phase7a_freeze_calibration_protocol.py` through `phase7h_final_test_evaluation.py` (including `phase7c2_*`, `phase7f2_*`) | Frozen Phase 6 benchmark, calibration split, identity-neutral evidence | calibration grids, frozen parameters, candidate audits, component/query predictions, `phase7h_final_test_summary.json` | Frozen TEST (360 queries/2,520 components): component accuracy 0.806, parent-set F1 0.844, unknown F1 0.754. | **Final method frozen at 7G.** TEST opened after freeze; parameter SHA-256 verified; no retuning permitted. |
| 8 | `phase8a_bootstrap_statistics.py`, `phase8b_baseline_ablation.py`, `phase8c_source_cluster_sensitivity.py` | Frozen Phase 7 predictions and scores | bootstrap/ablation/source-cluster tables and summaries | Hierarchical content improved parent-set F1 by 0.046 versus independent components. Graph-minus-content parent-set F1 was +0.00069 and its 95% query-bootstrap CI included zero; source-cluster sensitivity remained descriptively stable. | Post-hoc analysis only; test not rescored and parameters unchanged. Replicate-level tables are regenerable and excluded. |
| 9 | `server/phase9a_server.py`; `phase9b_server_correctness_regression.py` through `phase9f_gallery_scalability_benchmark.py`; Phase 9D/9E/9F servers | Frozen Phase 7 method/evidence, Phase 6L packages, server environment | correctness audits, request/summary tables, environment freeze | Server output matched all 360 queries and 2,520 components. End-to-end local-package p50 server time was 26.88 ms at concurrency 1; best measured end-to-end throughput was 38.71 req/s. At 100 gallery projects search p50 was 21.46 ms. | Server algorithm frozen to Phase 7. System/environment recorded; performance is host-specific. |
| 10 | `phase10a2_source_resolution_audit.py`, `phase10a3_source_snapshot_mapping.py`, `phase10a4_*`, `phase10a4b_*`, `phase10a4d_*`, `phase10a4e_*`, `phase10a4f_*`, `phase10a5_*`; paper figure scripts | Frozen TEST binary components, public source snapshots, external NiCadCross output | source mappings/audits, NiCad corpus mappings, clone pairs, comparison predictions/summaries, StoneDetector manifests | Same 1,169-component subset: proposed component accuracy 0.841 vs NiCadCross 0.710 (delta +0.131; paired 95% CI 0.096-0.167). Parent-set F1 delta +0.052 (95% CI approximately 0.0001-0.104). | External comparison only; no TEST retuning. External source/tool caches excluded. |
| 11 | `phase11a_build_multi_unknown_benchmark.py`, `phase11b_run_multi_unknown_robustness.py` | Frozen Phase 6K TEST donor components, Phase 6L payloads, exact Phase 7B donor evidence, frozen Phase 7 parameters/gallery | 180-query robustness manifest/ground truth, adapted evidence, predictions/audits, `phase11c_*` tables and summary | 180 queries/1,260 components: component accuracy 0.841, unknown F1 0.888, collapsed parent-set F1 0.884, collapsed-K accuracy 0.633. Distinct unknown-source identity recovery remains unsupported because the model emits one `UNKNOWN` label. | **Complete post-freeze robustness analysis.** Primary TEST unchanged; donor evidence reused; no feature recomputation or parameter retuning. |

## Phase 6-7 freeze anchors

1. `results/phase6c_project_split.csv` fixes the project split.
2. `results/phase6k_query_manifest_private.csv` and `results/phase6k_query_ground_truth.csv` fix query membership and labels.
3. `results/phase6l_materialized_private_manifest.csv` fixes local payload hashes; the corresponding payload files remain excluded.
4. `results/phase6l_graph_natural_public.csv` and `results/phase6l_graph_connected_stress_public.csv` fix the two graph tracks.
5. `results/phase7g_final_method_parameters.json` fixes thresholds and optimizer settings. Its recorded SHA-256 is `caad17257304d0ab198e01ef327f5acf918e6b8aab3f00e5272be3d20d3f8325`.
6. `results/phase7h_final_test_summary.json` confirms that TEST was scored after the freeze and the parameter hash matched.

## Execution notes

- Run scripts from the repository root. Most scripts use fixed relative inputs and outputs rather than a command-line interface.
- Collection/materialization stages require network access and locally retained raw archives under ignored `data/` paths.
- `phase3d_bytecode_baseline.py` uses the tracked `tools/phase3d/JavapBatch.java` source; compiled `.class` files are intentionally ignored.
- Phase 9 services require the dependencies captured in `results/phase9_environment_freeze.txt` and `reproducibility/requirements_freeze.txt`.
- Phase 10 NiCadCross requires an external Open-NiCad installation and reconstructed source corpora. Those tools/corpora are not vendored.
- `phase11b_run_multi_unknown_robustness.py` deterministically generates a temporary adapter from the frozen Phase 7H implementation. The generated active copy is ignored; the historical generated copy is archived for audit only.

## Interpretation guardrails

- Do not use Phase 7 TEST results to alter thresholds, `alpha`, `lambda`, candidate-pool size, graph beta, boundary Top-R, or `Kmax`.
- Phase 8 graph effects are small and statistically inconclusive on the primary parent-set F1 metric.
- Phase 9 latency scopes differ: precomputed-score, evidence-to-result, and local-package-to-result numbers must not be mixed.
- Phase 10 compares only source-resolvable code components and gives NiCadCross reconstructed Java source while the proposed method uses frozen binary-side evidence.
- Phase 11 measures rejection of components from multiple unregistered sources after collapsing them to one public `UNKNOWN` label; it does not identify distinct unknown parents.


## Phase 12 — Approximate Retrieval Scalability

Phase 12 evaluates whether the frozen Phase 7 provenance reconstruction pipeline can replace exhaustive registered-parent retrieval with binary multi-table LSH candidate generation without retuning the frozen method.

- Phase 12A: candidate-generation fidelity audit using fixed FAST, BALANCED, and HIGH_RECALL LSH operating points.
- Phase 12B: downstream content-only reconstruction using LSH candidate pools with frozen Phase 7 scores.
- Phase 12C: deployable online Exact-vs-LSH retrieval with actual Hamming/histogram distance recomputation.
- Phase 12D: downstream reconstruction from the online Phase 12C candidate pools.
- Phase 12E: retrieval scalability benchmark at 20/40/60/80/100 real projects and 200eq/500eq/1000eq synthetic component-volume stress.
- Phase 12F: reporting-only integrity and freeze audit.

Key findings:

- Online Exact reproduces the frozen Phase 7H Top-10 candidate pools.
- Full TEST content-only Exact performance remains component accuracy 0.807143, UNKNOWN F1 0.752386, parent-set F1 0.843545, parent-set exact 0.413889, and K accuracy 0.480556.
- BALANCED and HIGH_RECALL preserve the final Exact predictions on all 360 frozen TEST queries.
- FAST changes 1/360 query prediction and 1/2520 component prediction; its component-accuracy delta is -0.000397 and parent-F1 delta is -0.000741.
- FAST first shows lower observed p50 search latency than Exact at 40 real gallery projects.
- At the 60-project frozen TEST scale, the Phase 12E runtime sample reports Exact p50 10.315 ms and FAST p50 8.848 ms (1.166x).
- Fidelity-preserving BALANCED and HIGH_RECALL do not show an observed p50 crossover through 100 real projects or the 1000eq synthetic component-volume stress.
- 200eq/500eq/1000eq are computational component-volume stress conditions over 100 real registered parents, not additional unique real MOD projects.

Primary fidelity/downstream claims must use the full 360-query Phase 12C/12D results. Phase 12E uses a deterministic stratified 120-query sample and is used for runtime/scalability reporting.
