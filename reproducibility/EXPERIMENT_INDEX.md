<a id="experiment-en"></a>

# Experiment Index: Phase 1-13

[![English](https://img.shields.io/badge/EN-English-0969DA?style=for-the-badge)](#user-content-experiment-en) [![한국어](https://img.shields.io/badge/KO-%ED%95%9C%EA%B5%AD%EC%96%B4-6E7781?style=for-the-badge)](#user-content-experiment-ko) [![日本語](https://img.shields.io/badge/JA-%E6%97%A5%E6%9C%AC%E8%AA%9E-6E7781?style=for-the-badge)](#user-content-experiment-ja)

[← Repository overview](../README.md#user-content-readme-en)

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


---

<a id="experiment-ko"></a>

# 실험 인덱스: Phase 1-13

[![English](https://img.shields.io/badge/EN-English-6E7781?style=for-the-badge)](#user-content-experiment-en) [![한국어](https://img.shields.io/badge/KO-%ED%95%9C%EA%B5%AD%EC%96%B4-0969DA?style=for-the-badge)](#user-content-experiment-ko) [![日本語](https://img.shields.io/badge/JA-%E6%97%A5%E6%9C%AC%E8%AA%9E-6E7781?style=for-the-badge)](#user-content-experiment-ja)

[← 한국어 저장소 소개](../README.md#user-content-readme-ko)

마지막 문서 감사일: 2026-08-19. 모든 경로는 저장소 루트를 기준으로 합니다.

이 인덱스는 보존된 연구 기록을 찾기 위한 안내도입니다. 탐색적 작업과 동결된 확인적 평가를 구분하고, 각 Phase를 script, input, 보고 가능한 output, 핵심 결과 및 동결 상태에 연결합니다.

`동결`은 후속 작업에서 해당 산출물의 split, label, parameter, protocol 또는 기록된 hash를 변경하지 않고 사용해야 한다는 뜻입니다. `완료`로 표시된 Phase도 탐색적, 사후적, 진단적 또는 특정 host에 종속된 작업일 수 있으며, 완료가 곧 확인적 평가라는 뜻은 아닙니다.

## Phase별 지도

| Phase | 목적과 script | 주요 input | 선별된 output | 핵심 결과 | 상태 |
|---:|---|---|---|---|---|
| 1 | 예비 및 실제 MOD 수집: `phase1_collect.py`, `phase1b_collect_real_mods.py` | 공개 저장소 및 Modrinth metadata | `results/dataset_*.csv`, `results/phase1*_summary.json` | 예비: 저장소 10개. 실제 MOD corpus: MOD 30개, 코드 5,732개, 구조화 파일 888개, 이미지 파일 357개. | 완료; 탐색적 snapshot |
| 2 | Corpus 및 release registry: `phase2a_freeze_corpus.py`, `phase2b_build_registry.py`, `phase2c_build_release_registry.py` | Phase 1 corpus, 저장소 commit, 공개 release metadata | Corpus/release registry, 중복 감사, `results/phase2*_summary.json` | 소스 snapshot 30/30개와 release download 30/30개를 확인했습니다. release 구성요소는 7,677개이며 해당 registry에서 MOD 간 중복 group은 없었습니다. | 과거 소스 snapshot 동결; raw download 제외 |
| 3 | Version drift 및 content/bytecode baseline: `phase3a_*`부터 `phase3e_*`; `tools/phase3d/JavapBatch.java` | Phase 2 release 및 과거 version | 경로/content/bytecode/package table과 `results/phase3*_summary.json` | OPCODE_CONTEXT confidence voting: 과거 package 45개에서 package top-1 unique 0.578, top-5 0.911. | Baseline 보존; 최종 TEST 아님 |
| 4 | Dependency 및 resource graph: `phase4a_*`부터 `phase4c_*` | Release registry와 추출 metadata | Graph 진단, unresolved-reference table, `results/phase4*_summary.json` | 보강된 edge 25,987개; 최대 연결요소 비율 중앙값 0.818. | Protocol 보존; 최종 TEST graph 아님 |
| 5 | 탐색적 다중 부모 재구성: `phase5a_*`부터 `phase5h_*`, `phase5c2_*` 포함 | Phase 3/4 증거 및 합성 다중 부모 query | 다중 부모 raw/summary table과 `results/phase5*_summary.json` | 합성 CLEAN TEST 부분: 질의 150개에서 fused hierarchical 구성요소 정확도 0.405, 부모 집합 F1 0.504. | 탐색적 방법 개발 |
| 6 | 신규 corpus, benchmark 생성 및 materialization: `phase6a_*`부터 `phase6l_*` | 신규 공개 metadata/releases, 과거 registry, 추출 payload | 동결 split; Phase 6K query manifest/ground truth; Phase 6L payload-hash manifest/graph; audit와 summary | 프로젝트 120개(대상 90개, background 30개), 질의 540개, materialized 구성요소 3,780개. 소스 hash를 검증했고 exact-stage gallery collision은 없었습니다. | **동결 benchmark** |
| 7 | Calibration, 동결 및 최종 TEST: `phase7a_*`부터 `phase7h_*`, `phase7c2_*`, `phase7f2_*` 포함 | 동결 Phase 6 benchmark, CALIBRATION split, 식별자 중립 증거 | Calibration grid, 동결 parameter, retrieval audit, prediction, `results/phase7h_final_test_summary.json` | 동결 TEST: 질의 360개 / 구성요소 2,520개. 구성요소 정확도 0.805952, 부모 집합 F1 0.844233, `UNKNOWN` F1 0.753786. | **7G에서 방법 동결; 이후 TEST 공개** |
| 8 | 통계 검증 및 ablation: `phase8a_bootstrap_statistics.py`, `phase8b_baseline_ablation.py`, `phase8c_source_cluster_sensitivity.py` | 동결 Phase 7 prediction과 score | Bootstrap, ablation, source-cluster table과 summary | Hierarchical content는 independent component보다 부모 집합 F1이 0.046133 높았습니다. Graph-minus-content는 +0.000688로 통계적으로 확정적이지 않았습니다. | 사후 분석; 재채점/재조정 없음 |
| 9 | 연구 service 및 system 평가: `server/phase9a_server.py`; `phase9b_*`부터 `phase9f_*` | 동결 Phase 7 방법/증거 및 Phase 6L package | Correctness audit, benchmark table/summary, 환경 동결 | 질의 360개 / 구성요소 2,520개에서 reference와 정확히 일치했습니다. 동시성 1에서 local-package p50 26.880 ms, 측정된 최적 end-to-end throughput 38.71 req/s. | Algorithm 동결; latency는 host별 값 |
| 10 | 외부 비교: `phase10a2_*`, `phase10a3_*`, `phase10a4*`, `phase10a5_*`; 논문용 script | 동결 TEST 코드 구성요소, 공개 소스 snapshot, 외부 NiCadCross output | Source mapping/audit, clone pair, paired prediction/summary, StoneDetector manifest | 동일한 구성요소 1,169개 부분집합에서 제안 방법 정확도 0.841, NiCadCross 0.710. 차이 +0.131, paired 95% CI 0.096-0.167. | 외부 비교; TEST 재조정 없음 |
| 11 | 통제된 다중 미등록 출처 강건성: `phase11a_build_multi_unknown_benchmark.py`, `phase11b_run_multi_unknown_robustness.py`, 보고 audit | 동결 TEST donor/payload/evidence, Phase 7 parameter와 gallery | 질의 180개 manifest, adapted evidence, prediction, audit, `results/phase11c_*`, `phase11d_*` | 질의 180개 / 구성요소 1,260개. 구성요소 정확도 0.841, `UNKNOWN` F1 0.888, collapsed 부모 집합 F1 0.884. | 동결 후 강건성; 1차 TEST 불변 |
| 12 | 근사 retrieval 확장성: `phase12a_*`부터 `phase12f_*` | 동결 Phase 7 gallery/evidence와 고정 Exact/LSH operating point | Candidate fidelity, online runtime, downstream 결과, crossover 분석, 보고 audit | BALANCED/HIGH_RECALL은 Exact와 같은 prediction을 냈습니다. FAST는 질의 1/360개와 구성요소 1/2,520개의 prediction을 바꿨고, 프로젝트 60개에서 p50은 10.315 → 8.848 ms였습니다. | 동결 후 system 분석; manifest 동결 |
| 13 | 자동 실패 분석: `phase13a_*`부터 `phase13c_*` | 동결 Phase 7H TEST prediction, retrieval audit, ground truth | Error taxonomy, hierarchical localization, 보고 audit | 오류 489개: 구성요소 할당 325개, `UNKNOWN` 거부 81개, 부모 선택 47개, retrieval 36개. | 진단 전용; manifest 동결 |

## 결과 찾기

특정 주장에 대한 권위 있는 산출물은 아래에서 찾을 수 있습니다. 대용량 raw/intermediate output은 재생성할 수 있거나 의도적으로 추적에서 제외될 수 있으며, 아래 summary와 audit는 Git으로 추적됩니다.

| 질문 | 권위 있는 추적 산출물 |
|---|---|
| 신규 corpus는 어떻게 분할했는가? | `results/phase6c_project_split.csv`, `results/phase6c_split_summary.json` |
| Benchmark를 구성하는 query와 label은 무엇인가? | `results/phase6k_query_manifest_public.csv`, `results/phase6k_query_manifest_private.csv`, `results/phase6k_query_ground_truth.csv`, `results/phase6k_query_summary.json` |
| Payload와 graph를 일관되게 materialize했는가? | `results/phase6l_materialized_public_manifest.csv`, `results/phase6l_materialized_private_manifest.csv`, Phase 6L graph CSV와 audit |
| 동결 방법을 정의하는 parameter는 무엇인가? | `results/phase7g_final_method_parameters.json`, `results/phase7g_final_method_freeze_summary.json` |
| 최종 TEST prediction과 metric은 무엇인가? | `results/phase7h_final_test_component_predictions.csv`, `results/phase7h_final_test_query_predictions.csv`, `results/phase7h_final_test_summary.json` |
| 결과를 뒷받침하는 uncertainty와 ablation은 무엇인가? | `results/phase8a_bootstrap_summary.json`, `results/phase8b_baseline_ablation_summary.json`, `results/phase8c_source_cluster_sensitivity_summary.json` |
| Service가 동결 prediction을 재현하는가? | `results/phase9b_server_correctness_summary.json` |
| 각 latency 결과는 어느 pipeline 범위에 해당하는가? | `results/phase9c_concurrency_benchmark_summary.json`, `phase9d_evidence_pipeline_summary.json`, `phase9e3_end_to_end_summary.json`, `phase9f_gallery_scalability_summary.json` |
| NiCadCross는 어떻게 비교했는가? | `results/phase10a4d_nicad_summary.json`, `phase10a4e_same_subset_summary.json`, `phase10a4f_nicad_paired_bootstrap_summary.json` |
| 다중 미등록 출처 강건성은 무엇을 보여 주는가? | `results/phase11c_multi_unknown_summary.json`, `results/phase11d_reporting_audit_summary.json` |
| Exact/LSH 절충은 어떠한가? | `results/phase12c_online_retrieval_summary.json`, `phase12d_online_pool_downstream_summary.json`, `phase12e_scalability_crossover_summary.json`, `phase12f_reporting_audit_summary.json` |
| 최종 TEST 오류는 어디에서 발생하는가? | `results/phase13a_failure_taxonomy_summary.json`, `phase13b_failure_localization_summary.json`, `phase13c_reporting_audit_summary.json` |

<a id="freeze-anchors-ko"></a>

## 동결 기준점

### Phase 6 benchmark

1. `results/phase6c_project_split.csv`는 프로젝트 split을 고정합니다: CALIBRATION known 25개, TEST known 45개, held-out unknown 20개, CALIBRATION background 15개, TEST background 15개.
2. `results/phase6k_query_manifest_private.csv`와 `results/phase6k_query_ground_truth.csv`는 query membership과 label을 고정합니다.
3. `results/phase6l_materialized_private_manifest.csv`는 local payload hash를 고정합니다. payload byte는 Git에서 계속 제외됩니다.
4. `results/phase6l_graph_natural_public.csv`와 `results/phase6l_graph_connected_stress_public.csv`는 두 graph track을 고정합니다.

### Phase 7 방법

1. `results/phase7g_final_method_parameters.json`은 threshold, `alpha`, `lambda`, candidate-pool 크기, graph beta, boundary Top-R 및 `Kmax`를 고정합니다.
2. 기록된 parameter SHA-256은 `caad17257304d0ab198e01ef327f5acf918e6b8aab3f00e5272be3d20d3f8325`입니다.
3. `results/phase7h_final_test_summary.json`은 동결 후 TEST를 채점했으며 parameter hash가 일치했음을 확인합니다.

### 동결 후 manifest

- `reproducibility/phase12_freeze_manifest.sha256`은 Phase 12 보고 집합을 기록합니다.
- `reproducibility/phase13_freeze_manifest.sha256`은 Phase 13 진단 집합을 기록합니다.
- Phase 8-13 output은 Phase 6 split, Phase 7 parameter 또는 1차 TEST prediction의 변경을 허용하지 않습니다.

## 실행 참고사항

- Script는 저장소 루트에서 실행하세요. 대부분 command-line interface 대신 고정 상대 경로를 사용합니다.
- 수집과 materialization에는 network 접근 및 무시되는 `data/` 경로 아래에 local로 보관한 raw archive가 필요합니다.
- `phase3d_bytecode_baseline.py`는 추적되는 `tools/phase3d/JavapBatch.java`를 사용하며, compile된 `.class` 파일은 무시됩니다.
- Phase 9 dependency는 `results/phase9_environment_freeze.txt`와 `reproducibility/requirements_freeze.txt`에 기록되어 있습니다.
- Phase 10 NiCadCross 작업에는 외부 Open-NiCad 설치와 복원된 source corpus가 필요합니다. 해당 도구와 corpus는 저장소에 포함하지 않습니다.
- `phase11b_run_multi_unknown_robustness.py`는 동결 Phase 7H 구현에서 임시 adapter를 결정론적으로 생성합니다. 활성 생성본은 무시되며 과거 생성본은 감사를 위해 `archive/`에 보존합니다.
- Phase 12의 합성 `200eq`/`500eq`/`1000eq` 규모는 실제 등록 부모 100개 위에서 component array를 복제합니다. 이는 구성요소 규모 stress test이지 고유 프로젝트 cohort가 아닙니다.

## 과거 및 제외된 산출물

- 대체된 script, 생성물, 알려진 bug script는 출처 기록과 함께 `archive/` 아래에 보존하며 활성 pipeline 진입점으로 사용하지 않습니다.
- 원본 MOD/JAR archive, 제3자 cache, 외부 도구용 복원 corpus, 가상환경, compiled output 및 대용량 재생성 가능 replica는 Git 밖에 둡니다.
- `reproducibility/TRACKING_AUDIT.md`에는 보존 정책과 원래 Phase 1-11 분류 감사가 기록되어 있습니다.
- `reproducibility/UNTRACKED_CLASSIFICATION.csv`는 상세 local 분류 ledger입니다. 여기의 경로는 GitHub에 없는 무시된 local 자료를 설명할 수 있습니다.

## 해석상 주의사항

- 이 방법은 기술적 출처 검토를 지원하지만 저작권 소유권, 침해, 허락 또는 법적 책임을 판단하지 않습니다.
- 동결 방법을 변경하는 데 Phase 7 TEST 결과를 사용하지 마세요.
- Phase 8 graph가 부모 집합 F1에 미친 영향은 작고 통계적으로 확정적이지 않습니다.
- Phase 9의 precomputed-score, evidence-to-result 및 local-package-to-result latency는 서로 다른 범위를 측정하므로 혼용하면 안 됩니다.
- Phase 10은 source-resolvable code만 비교합니다. NiCadCross는 복원된 Java source를 입력받지만 제안 방법은 동결 binary-side 증거를 사용합니다.
- Phase 11은 모든 미등록 출처를 하나의 `UNKNOWN` label로 합치므로 서로 다른 미등록 출처의 정체나 개수를 복원할 수 없습니다.
- Phase 12 FAST는 lossless가 아니며, fidelity를 보존하는 LSH가 평가한 모든 규모에서 vectorized exhaustive search보다 빠르지는 않았습니다.
- Phase 13은 기존 prediction의 기술적 실패 위치 분석이며 새로운 model 평가나 parameter 선택 단계가 아닙니다.

---

<a id="experiment-ja"></a>

# 実験インデックス：Phase 1-13

[![English](https://img.shields.io/badge/EN-English-6E7781?style=for-the-badge)](#user-content-experiment-en) [![한국어](https://img.shields.io/badge/KO-%ED%95%9C%EA%B5%AD%EC%96%B4-6E7781?style=for-the-badge)](#user-content-experiment-ko) [![日本語](https://img.shields.io/badge/JA-%E6%97%A5%E6%9C%AC%E8%AA%9E-0969DA?style=for-the-badge)](#user-content-experiment-ja)

[← 日本語のリポジトリ概要](../README.md#user-content-readme-ja)

最終文書監査日：2026-08-19。すべてのパスはリポジトリルートからの相対パスです。

本インデックスは、保存された研究記録の案内図です。探索的作業と凍結済みの確認的評価を区別し、各Phaseをscript、input、報告対象output、主要結果、凍結状況に対応付けます。

`凍結`とは、後続作業がsplit、label、parameter、protocol、記録済みhashを変更せずに当該成果物を使用しなければならないことを意味します。`完了`とされたPhaseも、探索的、事後的、診断的、または特定hostに依存する場合があり、完了は確認的評価であることを意味しません。

## Phase別マップ

| Phase | 目的とscript | 主なinput | 選別済みoutput | 主要結果 | 状況 |
|---:|---|---|---|---|---|
| 1 | 予備収集と実MOD収集：`phase1_collect.py`、`phase1b_collect_real_mods.py` | 公開リポジトリとModrinth metadata | `results/dataset_*.csv`、`results/phase1*_summary.json` | 予備：10リポジトリ。実MOD corpus：30 MOD、コード5,732件、構造化ファイル888件、画像ファイル357件。 | 完了；探索的snapshot |
| 2 | Corpusおよびrelease registry：`phase2a_freeze_corpus.py`、`phase2b_build_registry.py`、`phase2c_build_release_registry.py` | Phase 1 corpus、リポジトリcommit、公開release metadata | Corpus/release registry、重複監査、`results/phase2*_summary.json` | source snapshot 30/30件とrelease download 30/30件を解決しました。release componentは7,677件で、そのregistryにMOD間重複groupはありませんでした。 | 旧source snapshotを凍結；raw downloadを除外 |
| 3 | Version driftとcontent/bytecode baseline：`phase3a_*`から`phase3e_*`；`tools/phase3d/JavapBatch.java` | Phase 2 releaseと過去version | path/content/bytecode/package tableと`results/phase3*_summary.json` | OPCODE_CONTEXT confidence voting：過去45 packageでpackage top-1 unique 0.578、top-5 0.911。 | Baseline保存；最終TESTではない |
| 4 | Dependencyおよびresource graph：`phase4a_*`から`phase4c_*` | Release registryと抽出metadata | Graph診断、unresolved-reference table、`results/phase4*_summary.json` | 強化済みedge 25,987件；最大連結成分率の中央値0.818。 | Protocol保存；最終TEST graphではない |
| 5 | 探索的な複数親再構成：`phase5a_*`から`phase5h_*`、`phase5c2_*`を含む | Phase 3/4の証拠と合成複数親query | 複数親raw/summary tableと`results/phase5*_summary.json` | 合成CLEAN TEST部分：150 queryでfused hierarchical component accuracy 0.405、親集合F1 0.504。 | 探索的手法開発 |
| 6 | 新規corpus、benchmark生成、materialization：`phase6a_*`から`phase6l_*` | 新規公開metadata/releases、過去registry、抽出payload | 凍結split；Phase 6K query manifest/ground truth；Phase 6L payload-hash manifest/graph；auditとsummary | 120プロジェクト（対象90、background 30）、540 query、3,780 materialized component。source hashを検証し、exact-stage gallery collisionはありませんでした。 | **凍結benchmark** |
| 7 | Calibration、凍結、最終TEST：`phase7a_*`から`phase7h_*`、`phase7c2_*`、`phase7f2_*`を含む | 凍結Phase 6 benchmark、CALIBRATION split、識別子中立な証拠 | Calibration grid、凍結parameter、retrieval audit、prediction、`results/phase7h_final_test_summary.json` | 凍結TEST：360 query / 2,520 component。component accuracy 0.805952、親集合F1 0.844233、`UNKNOWN` F1 0.753786。 | **7Gで手法凍結；その後TESTを開封** |
| 8 | 統計検証とablation：`phase8a_bootstrap_statistics.py`、`phase8b_baseline_ablation.py`、`phase8c_source_cluster_sensitivity.py` | 凍結Phase 7 predictionとscore | Bootstrap、ablation、source-cluster tableとsummary | Hierarchical contentはindependent componentより親集合F1が0.046133高くなりました。Graph-minus-contentは+0.000688で統計的に確定的ではありませんでした。 | 事後分析；再採点・再調整なし |
| 9 | 研究serviceとsystem評価：`server/phase9a_server.py`；`phase9b_*`から`phase9f_*` | 凍結Phase 7手法/証拠とPhase 6L package | Correctness audit、benchmark table/summary、環境凍結 | 360 query / 2,520 componentでreferenceと完全一致。並行度1でlocal-package p50 26.880 ms、測定上の最良end-to-end throughput 38.71 req/s。 | Algorithm凍結；latencyはhost固有 |
| 10 | 外部比較：`phase10a2_*`、`phase10a3_*`、`phase10a4*`、`phase10a5_*`；論文用script | 凍結TESTコードcomponent、公開source snapshot、外部NiCadCross output | Source mapping/audit、clone pair、paired prediction/summary、StoneDetector manifest | 同じ1,169 componentのsubsetで提案手法0.841、NiCadCross 0.710。差+0.131、paired 95% CI 0.096-0.167。 | 外部比較；TEST再調整なし |
| 11 | 制御された複数未知由来への頑健性：`phase11a_build_multi_unknown_benchmark.py`、`phase11b_run_multi_unknown_robustness.py`、報告audit | 凍結TEST donor/payload/evidence、Phase 7 parameterとgallery | 180 query manifest、adapted evidence、prediction、audit、`results/phase11c_*`、`phase11d_*` | 180 query / 1,260 component。component accuracy 0.841、`UNKNOWN` F1 0.888、collapsed親集合F1 0.884。 | 凍結後頑健性；主要TESTは不変 |
| 12 | 近似retrievalのスケーラビリティ：`phase12a_*`から`phase12f_*` | 凍結Phase 7 gallery/evidenceと固定Exact/LSH operating point | Candidate fidelity、online runtime、downstream結果、crossover分析、報告audit | BALANCED/HIGH_RECALLはExactと同じpredictionでした。FASTはquery 1/360件とcomponent 1/2,520件のpredictionを変更し、60プロジェクトでp50は10.315 → 8.848 msでした。 | 凍結後system分析；manifest凍結 |
| 13 | 自動失敗分析：`phase13a_*`から`phase13c_*` | 凍結Phase 7H TEST prediction、retrieval audit、ground truth | Error taxonomy、hierarchical localization、報告audit | 489 error：component割当325、`UNKNOWN`棄却81、親選択47、retrieval 36。 | 診断専用；manifest凍結 |

## 結果の参照先

特定の主張に対する正本の成果物は、以下から確認できます。大容量のraw/intermediate outputは再生成可能または意図的に追跡対象外の場合がありますが、下記のsummaryとauditはGitで追跡されています。

| 質問 | 正本として追跡される成果物 |
|---|---|
| 新規corpusをどのように分割したか？ | `results/phase6c_project_split.csv`、`results/phase6c_split_summary.json` |
| Benchmarkを構成するqueryとlabelは何か？ | `results/phase6k_query_manifest_public.csv`、`results/phase6k_query_manifest_private.csv`、`results/phase6k_query_ground_truth.csv`、`results/phase6k_query_summary.json` |
| Payloadとgraphを一貫してmaterializeしたか？ | `results/phase6l_materialized_public_manifest.csv`、`results/phase6l_materialized_private_manifest.csv`、Phase 6L graph CSVとaudit |
| 凍結手法を定義するparameterは何か？ | `results/phase7g_final_method_parameters.json`、`results/phase7g_final_method_freeze_summary.json` |
| 最終TESTのpredictionとmetricは何か？ | `results/phase7h_final_test_component_predictions.csv`、`results/phase7h_final_test_query_predictions.csv`、`results/phase7h_final_test_summary.json` |
| 結果を裏付けるuncertaintyとablationは何か？ | `results/phase8a_bootstrap_summary.json`、`results/phase8b_baseline_ablation_summary.json`、`results/phase8c_source_cluster_sensitivity_summary.json` |
| Serviceは凍結predictionを再現するか？ | `results/phase9b_server_correctness_summary.json` |
| 各latency結果はどのpipeline範囲か？ | `results/phase9c_concurrency_benchmark_summary.json`、`phase9d_evidence_pipeline_summary.json`、`phase9e3_end_to_end_summary.json`、`phase9f_gallery_scalability_summary.json` |
| NiCadCrossをどのように比較したか？ | `results/phase10a4d_nicad_summary.json`、`phase10a4e_same_subset_summary.json`、`phase10a4f_nicad_paired_bootstrap_summary.json` |
| 複数未知由来への頑健性は何を示すか？ | `results/phase11c_multi_unknown_summary.json`、`results/phase11d_reporting_audit_summary.json` |
| Exact/LSHのトレードオフは何か？ | `results/phase12c_online_retrieval_summary.json`、`phase12d_online_pool_downstream_summary.json`、`phase12e_scalability_crossover_summary.json`、`phase12f_reporting_audit_summary.json` |
| 最終TESTのerrorはどこで発生するか？ | `results/phase13a_failure_taxonomy_summary.json`、`phase13b_failure_localization_summary.json`、`phase13c_reporting_audit_summary.json` |

<a id="freeze-anchors-ja"></a>

## 凍結アンカー

### Phase 6 benchmark

1. `results/phase6c_project_split.csv`はプロジェクトsplitを固定します：CALIBRATION known 25、TEST known 45、held-out unknown 20、CALIBRATION background 15、TEST background 15。
2. `results/phase6k_query_manifest_private.csv`と`results/phase6k_query_ground_truth.csv`はquery membershipとlabelを固定します。
3. `results/phase6l_materialized_private_manifest.csv`はlocal payload hashを固定します。payload byteは引き続きGitから除外します。
4. `results/phase6l_graph_natural_public.csv`と`results/phase6l_graph_connected_stress_public.csv`は2つのgraph trackを固定します。

### Phase 7手法

1. `results/phase7g_final_method_parameters.json`はthreshold、`alpha`、`lambda`、candidate-pool size、graph beta、boundary Top-R、`Kmax`を固定します。
2. 記録済みparameter SHA-256は`caad17257304d0ab198e01ef327f5acf918e6b8aab3f00e5272be3d20d3f8325`です。
3. `results/phase7h_final_test_summary.json`は、凍結後にTESTを採点し、parameter hashが一致したことを確認します。

### 凍結後manifest

- `reproducibility/phase12_freeze_manifest.sha256`はPhase 12の報告集合を記録します。
- `reproducibility/phase13_freeze_manifest.sha256`はPhase 13の診断集合を記録します。
- Phase 8-13のoutputは、Phase 6 split、Phase 7 parameter、主要TEST predictionの変更を許可しません。

## 実行上の注意

- Scriptはリポジトリルートから実行してください。多くはcommand-line interfaceではなく固定相対パスを使用します。
- 収集とmaterializationにはnetwork accessと、無視対象の`data/`パス配下にlocal保存したraw archiveが必要です。
- `phase3d_bytecode_baseline.py`は追跡対象の`tools/phase3d/JavapBatch.java`を使用し、compile済み`.class`ファイルは無視されます。
- Phase 9 dependencyは`results/phase9_environment_freeze.txt`と`reproducibility/requirements_freeze.txt`に記録されています。
- Phase 10 NiCadCross作業には外部Open-NiCadのインストールと再構成source corpusが必要です。これらのtoolとcorpusは同梱しません。
- `phase11b_run_multi_unknown_robustness.py`は凍結Phase 7H実装から一時adapterを決定論的に生成します。現在の生成copyは無視され、過去のcopyは監査用として`archive/`に保存されています。
- Phase 12の合成`200eq`/`500eq`/`1000eq`規模は、100件の実登録親に対してcomponent arrayを複製します。これはcomponent-volume stress testであり、一意なプロジェクトcohortではありません。

## 過去および除外対象の成果物

- 旧版、生成物、既知bugのscriptは由来メモとともに`archive/`配下に保存されますが、active pipelineのentry pointではありません。
- 生のMOD/JAR archive、第三者cache、外部tool用の再構成corpus、仮想環境、compiled output、大容量で再生成可能なreplicaはGit外に置きます。
- `reproducibility/TRACKING_AUDIT.md`には保存方針と当初のPhase 1-11分類監査を記録しています。
- `reproducibility/UNTRACKED_CLASSIFICATION.csv`は詳細なlocal分類ledgerです。ここに記載されたpathは、GitHubに存在しない無視対象のlocal資料を示す場合があります。

## 解釈上の注意事項

- 本手法は技術的な由来レビューを支援するものであり、著作権の帰属、侵害、許諾、法的責任を判断しません。
- 凍結手法の変更にPhase 7 TEST結果を使用しないでください。
- Phase 8 graphによる親集合F1への影響は小さく、統計的に確定的ではありません。
- Phase 9のprecomputed-score、evidence-to-result、local-package-to-result latencyは異なる範囲を測定するため、混同してはいけません。
- Phase 10はsource-resolvable codeのみを比較します。NiCadCrossには再構成Java sourceを入力しますが、提案手法は凍結binary-side evidenceを使用します。
- Phase 11はすべての未登録由来を1つの`UNKNOWN` labelにまとめるため、異なる未知由来の同定や個数を復元できません。
- Phase 12 FASTはlosslessではなく、fidelityを維持するLSHが評価したすべての規模でvectorized exhaustive searchより高速だったわけではありません。
- Phase 13は既存predictionに対する記述的な失敗局在化であり、新しいmodel評価やparameter選択段階ではありません。
