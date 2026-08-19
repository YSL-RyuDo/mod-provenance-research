# Experiment Index: Phase 1-13

Last documentation audit: 2026-08-19. Paths are relative to the repository root.

This index is the routing map for the preserved research record. It distinguishes exploratory work from frozen confirmatory evaluation and maps each phase to its scripts, inputs, reportable outputs, headline result, and freeze status.

`Frozen` means that downstream work must consume the artifact without changing its split, labels, parameters, protocol, or recorded hash. A phase marked `Complete` can still be exploratory, post-hoc, diagnostic, or host-specific; completion is not a claim of confirmatory status.

## Phase-level map

| Phase | Purpose and scripts | Primary inputs | Curated outputs | Headline result | Status |
|---:|---|---|---|---|---|
| 1 | Pilot and real-MOD collection: `phase1_collect.py`, `phase1b_collect_real_mods.py` | Public repository and Modrinth metadata | `results/dataset_*.csv`, `results/phase1*_summary.json` | Pilot: 10 repositories. Real-MOD corpus: 30 MODs, 5,732 code, 888 structured, and 357 image files. | Complete; exploratory snapshot |
| 2 | Corpus and release registries: `phase2a_freeze_corpus.py`, `phase2b_build_registry.py`, `phase2c_build_release_registry.py` | Phase 1 corpus, repository commits, public release metadata | Corpus/release registries, duplicate audits, `results/phase2*_summary.json` | 30/30 source snapshots and 30/30 release downloads resolved; 7,677 release components; no cross-MOD duplicate group in that registry. | Legacy source snapshot frozen; raw downloads excluded |
| 3 | Version drift and content/bytecode baselines: `phase3a_*` through `phase3e_*`; `tools/phase3d/JavapBatch.java` | Phase 2 releases and historical versions | Path/content/bytecode/package tables and `results/phase3*_summary.json` | OPCODE_CONTEXT confidence voting: package top-1 unique 0.578 and top-5 0.911 across 45 historical packages. | Baselines preserved; not final TEST |
| 4 | Dependency and resource graphs: `phase4a_*` through `phase4c_*` | Release registries and extracted metadata | Graph diagnostics, unresolved-reference tables, `results/phase4*_summary.json` | 25,987 enriched edges; median largest-component rate 0.818. | Protocol preserved; not final TEST graph |
| 5 | Exploratory multi-parent reconstruction: `phase5a_*` through `phase5h_*`, including `phase5c2_*` | Phase 3/4 evidence and synthetic multi-parent queries | Multi-parent raw/summary tables and `results/phase5*_summary.json` | Synthetic CLEAN TEST portion: fused hierarchical component accuracy 0.405 and parent-set F1 0.504 over 150 queries. | Exploratory method development |
| 6 | Fresh corpus, benchmark generation, and materialization: `phase6a_*` through `phase6l_*` | Fresh public metadata/releases, historical registries, extracted payloads | Frozen split; Phase 6K query manifests/ground truth; Phase 6L payload-hash manifests/graphs; audits and summaries | 120 projects (90 target, 30 background); 540 queries; 3,780 materialized components; source hashes verified; no exact-stage gallery collisions. | **Frozen benchmark** |
| 7 | Calibration, freeze, and final TEST: `phase7a_*` through `phase7h_*`, including `phase7c2_*` and `phase7f2_*` | Frozen Phase 6 benchmark, CALIBRATION split, identity-neutral evidence | Calibration grids, frozen parameters, retrieval audits, predictions, `results/phase7h_final_test_summary.json` | Frozen TEST: 360 queries / 2,520 components; component accuracy 0.805952; parent-set F1 0.844233; `UNKNOWN` F1 0.753786. | **Method frozen at 7G; TEST opened afterward** |
| 8 | Statistical validation and ablation: `phase8a_bootstrap_statistics.py`, `phase8b_baseline_ablation.py`, `phase8c_source_cluster_sensitivity.py` | Frozen Phase 7 predictions and scores | Bootstrap, ablation, source-cluster tables and summaries | Hierarchical content improved parent-set F1 by 0.046133 over independent components. Graph-minus-content was +0.000688 and statistically inconclusive. | Post-hoc analysis; no rescoring/retuning |
| 9 | Research service and system evaluation: `server/phase9a_server.py`; `phase9b_*` through `phase9f_*` | Frozen Phase 7 method/evidence and Phase 6L packages | Correctness audits, benchmark tables/summaries, environment freeze | Exact reference agreement for 360 queries / 2,520 components; local-package p50 26.880 ms at concurrency 1; best measured end-to-end throughput 38.71 req/s. | Algorithm frozen; latency is host-specific |
| 10 | External comparison: `phase10a2_*`, `phase10a3_*`, `phase10a4*`, `phase10a5_*`; paper scripts | Frozen TEST code components, public source snapshots, external NiCadCross output | Source mappings/audits, clone pairs, paired predictions/summaries, StoneDetector manifests | On the same 1,169-component subset: proposed 0.841 vs NiCadCross 0.710 component accuracy; delta +0.131, paired 95% CI 0.096-0.167. | External comparison; no TEST retuning |
| 11 | Controlled multi-unknown robustness: `phase11a_build_multi_unknown_benchmark.py`, `phase11b_run_multi_unknown_robustness.py`, reporting audit | Frozen TEST donors/payloads/evidence, Phase 7 parameters and gallery | 180-query manifests, adapted evidence, predictions, audits, `results/phase11c_*`, `phase11d_*` | 180 queries / 1,260 components; component accuracy 0.841; `UNKNOWN` F1 0.888; collapsed parent-set F1 0.884. | Post-freeze robustness; primary TEST unchanged |
| 12 | Approximate retrieval scalability: `phase12a_*` through `phase12f_*` | Frozen Phase 7 gallery/evidence and fixed Exact/LSH operating points | Candidate fidelity, online runtime, downstream results, crossover analysis, reporting audit | BALANCED/HIGH_RECALL matched Exact predictions; FAST changed 1/360 queries and 1/2,520 components; 60-project p50 10.315 → 8.848 ms. | Post-freeze systems analysis; manifest frozen |
| 13 | Automated failure analysis: `phase13a_*` through `phase13c_*` | Frozen Phase 7H TEST predictions, retrieval audit, ground truth | Error taxonomy, hierarchical localization, reporting audit | 489 errors: assignment 325, `UNKNOWN` rejection 81, parent selection 47, retrieval 36. | Diagnostic only; manifest frozen |

## Result routing

Use this section to locate the authoritative artifact for a specific claim. Large raw/intermediate outputs may be regenerable or intentionally ignored; the listed summaries and audits are tracked.

| Question | Authoritative tracked artifacts |
|---|---|
| How was the fresh corpus split? | `results/phase6c_project_split.csv`, `results/phase6c_split_summary.json` |
| Which queries and labels form the benchmark? | `results/phase6k_query_manifest_public.csv`, `results/phase6k_query_manifest_private.csv`, `results/phase6k_query_ground_truth.csv`, `results/phase6k_query_summary.json` |
| Were payloads and graphs materialized consistently? | `results/phase6l_materialized_public_manifest.csv`, `results/phase6l_materialized_private_manifest.csv`, Phase 6L graph CSVs and audits |
| Which parameters define the frozen method? | `results/phase7g_final_method_parameters.json`, `results/phase7g_final_method_freeze_summary.json` |
| What are the final TEST predictions and metrics? | `results/phase7h_final_test_component_predictions.csv`, `results/phase7h_final_test_query_predictions.csv`, `results/phase7h_final_test_summary.json` |
| What uncertainty and ablations support the result? | `results/phase8a_bootstrap_summary.json`, `results/phase8b_baseline_ablation_summary.json`, `results/phase8c_source_cluster_sensitivity_summary.json` |
| Does the service reproduce the frozen predictions? | `results/phase9b_server_correctness_summary.json` |
| Which latency result belongs to which pipeline? | `results/phase9c_concurrency_benchmark_summary.json`, `phase9d_evidence_pipeline_summary.json`, `phase9e3_end_to_end_summary.json`, `phase9f_gallery_scalability_summary.json` |
| How was NiCadCross compared? | `results/phase10a4d_nicad_summary.json`, `phase10a4e_same_subset_summary.json`, `phase10a4f_nicad_paired_bootstrap_summary.json` |
| What does multi-unknown robustness show? | `results/phase11c_multi_unknown_summary.json`, `results/phase11d_reporting_audit_summary.json` |
| What is the Exact/LSH trade-off? | `results/phase12c_online_retrieval_summary.json`, `phase12d_online_pool_downstream_summary.json`, `phase12e_scalability_crossover_summary.json`, `phase12f_reporting_audit_summary.json` |
| Where do final TEST errors occur? | `results/phase13a_failure_taxonomy_summary.json`, `phase13b_failure_localization_summary.json`, `phase13c_reporting_audit_summary.json` |

## Freeze anchors

### Phase 6 benchmark

1. `results/phase6c_project_split.csv` fixes the project split: 25 CALIBRATION known, 45 TEST known, 20 held-out unknown, 15 CALIBRATION background, and 15 TEST background.
2. `results/phase6k_query_manifest_private.csv` and `results/phase6k_query_ground_truth.csv` fix query membership and labels.
3. `results/phase6l_materialized_private_manifest.csv` fixes local payload hashes; payload bytes remain excluded from Git.
4. `results/phase6l_graph_natural_public.csv` and `results/phase6l_graph_connected_stress_public.csv` fix the two graph tracks.

### Phase 7 method

1. `results/phase7g_final_method_parameters.json` fixes thresholds, `alpha`, `lambda`, candidate-pool size, graph beta, boundary Top-R, and `Kmax`.
2. The recorded parameter SHA-256 is `caad17257304d0ab198e01ef327f5acf918e6b8aab3f00e5272be3d20d3f8325`.
3. `results/phase7h_final_test_summary.json` confirms that TEST was scored after the freeze and that the parameter hash matched.

### Post-freeze manifests

- `reproducibility/phase12_freeze_manifest.sha256` records the Phase 12 reporting set.
- `reproducibility/phase13_freeze_manifest.sha256` records the Phase 13 diagnostic set.
- Phase 8-13 outputs do not authorize changes to Phase 6 splits, Phase 7 parameters, or the primary TEST predictions.

## Execution notes

- Run scripts from the repository root. Most use fixed relative paths rather than a command-line interface.
- Collection and materialization require network access and locally retained raw archives under ignored `data/` paths.
- `phase3d_bytecode_baseline.py` uses the tracked `tools/phase3d/JavapBatch.java`; compiled `.class` files are ignored.
- Phase 9 dependencies are recorded in `results/phase9_environment_freeze.txt` and `reproducibility/requirements_freeze.txt`.
- Phase 10 NiCadCross work requires an external Open-NiCad installation and reconstructed source corpora. Those tools and corpora are not vendored.
- `phase11b_run_multi_unknown_robustness.py` deterministically creates a temporary adapter from the frozen Phase 7H implementation. The active generated copy is ignored; the historical copy is preserved in `archive/` for audit.
- Phase 12 synthetic `200eq`/`500eq`/`1000eq` scales duplicate component arrays over 100 real registered parents. They are component-volume stress tests, not unique-project cohorts.

## Historical and excluded artifacts

- Superseded, generated, and known-bug scripts are retained under `archive/` with provenance notes; they are not active pipeline entry points.
- Raw MOD/JAR archives, third-party caches, reconstructed external-tool corpora, virtual environments, compiled output, and high-volume regenerable replicas remain outside Git.
- `reproducibility/TRACKING_AUDIT.md` records the preservation policy and the original Phase 1-11 classification audit.
- `reproducibility/UNTRACKED_CLASSIFICATION.csv` is the detailed local classification ledger; paths may describe ignored local material that is not present on GitHub.

## Interpretation guardrails

- The method supports technical provenance review; it does not decide copyright ownership, infringement, permission, or legal responsibility.
- Do not use Phase 7 TEST results to alter the frozen method.
- The Phase 8 graph effect on parent-set F1 is small and statistically inconclusive.
- Phase 9 precomputed-score, evidence-to-result, and local-package-to-result latencies measure different scopes and must not be mixed.
- Phase 10 compares source-resolvable code only; NiCadCross receives reconstructed Java source while the proposed method uses frozen binary-side evidence.
- Phase 11 collapses all unregistered sources to one `UNKNOWN` label and cannot recover distinct unknown identity or multiplicity.
- Phase 12 FAST is not lossless, and fidelity-preserving LSH was not universally faster than vectorized exhaustive search at the evaluated scales.
- Phase 13 is a descriptive failure localization of existing predictions, not a new model evaluation or parameter-selection stage.
