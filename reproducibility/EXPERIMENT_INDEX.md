<a id="experiment-en"></a>

# Experiment Index: Phase 1-13

[![English](https://img.shields.io/badge/EN-English-0969DA?style=for-the-badge)](#user-content-experiment-en) [![한국어](https://img.shields.io/badge/KO-%ED%95%9C%EA%B5%AD%EC%96%B4-6E7781?style=for-the-badge)](#user-content-experiment-ko) [![日本語](https://img.shields.io/badge/JA-%E6%97%A5%E6%9C%AC%E8%AA%9E-6E7781?style=for-the-badge)](#user-content-experiment-ja)

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

마지막 문서 감사일: 2026-08-19. 모든 경로는 저장소 루트를 기준으로 한다.

이 문서는 보존된 연구 기록을 단계별로 연결한 인덱스다. 탐색 단계와 동결된 확인 평가를 구분하고, 각 Phase의 스크립트, 입력, 보고 대상 출력, 주요 결과와 동결 상태를 함께 제시한다.

`동결`은 이후 작업에서 데이터 분할, 정답, 매개변수, 평가 절차와 기록된 해시를 변경하지 않은 채 해당 자료를 사용해야 한다는 뜻이다. `완료`로 표시된 Phase라도 탐색·사후 분석·진단 또는 특정 실행 환경에 한정된 작업일 수 있으며, 완료가 곧 확인 평가를 뜻하지는 않는다.

## Phase별 지도

| Phase | 목적과 스크립트 | 주요 입력 | 보고 대상 출력 | 주요 결과 | 상태 |
|---:|---|---|---|---|---|
| 1 | 예비 조사 및 실제 MOD 수집: `phase1_collect.py`, `phase1b_collect_real_mods.py` | 공개 저장소와 Modrinth 메타데이터 | `results/dataset_*.csv`, `results/phase1*_summary.json` | 예비 저장소 10개. 실제 MOD 데이터셋은 MOD 30개, 코드 5,732개, 구조화 파일 888개, 이미지 파일 357개로 구성된다. | 완료; 탐색적 시점 자료 |
| 2 | 데이터셋 및 릴리스 목록 구축: `phase2a_freeze_corpus.py`, `phase2b_build_registry.py`, `phase2c_build_release_registry.py` | Phase 1 데이터셋, 저장소 커밋, 공개 릴리스 메타데이터 | 데이터셋·릴리스 목록, 중복 감사, `results/phase2*_summary.json` | 소스 시점 자료 30/30개와 릴리스 파일 30/30개를 확인했다. 릴리스 구성요소는 7,677개이며 MOD 사이에 중복 집단은 없었다. | 과거 소스 시점 자료 동결; 원본 파일 제외 |
| 3 | 버전 변화와 내용·바이트코드 기준선: `phase3a_*`부터 `phase3e_*`; `tools/phase3d/JavapBatch.java` | Phase 2 릴리스와 과거 버전 | 경로·내용·바이트코드·패키지 표와 `results/phase3*_summary.json` | OPCODE_CONTEXT 신뢰도 투표는 과거 패키지 45개에서 패키지 top-1 고유 정확도 0.578, top-5 0.911을 기록했다. | 기준선 보존; 최종 TEST 아님 |
| 4 | 의존성과 리소스 참조 그래프: `phase4a_*`부터 `phase4c_*` | 릴리스 목록과 추출 메타데이터 | 그래프 진단, 미해결 참조 표, `results/phase4*_summary.json` | 보강된 간선 25,987개; 최대 연결요소 비율의 중앙값은 0.818이다. | 절차 보존; 최종 TEST 그래프 아님 |
| 5 | 탐색적 다중 부모 재구성: `phase5a_*`부터 `phase5h_*`, `phase5c2_*` 포함 | Phase 3/4 증거와 합성 다중 부모 질의 | 다중 부모 원자료·요약표와 `results/phase5*_summary.json` | 합성 CLEAN TEST 부분의 질의 150개에서 결합 계층 방법의 구성요소 정확도는 0.405, 부모 집합 F1은 0.504였다. | 탐색적 방법 개발 |
| 6 | 신규 데이터셋·벤치마크 생성과 질의 구성: `phase6a_*`부터 `phase6l_*` | 신규 공개 메타데이터·릴리스, 과거 목록, 추출 원본 데이터 | 동결 분할; Phase 6K 질의 목록·정답; Phase 6L 원본 해시 목록·그래프; 감사와 요약 | 프로젝트 120개(대상 90개, 배경 30개), 질의 540개, 구성된 구성요소 3,780개. 소스 해시를 검증했으며 정확 일치 단계의 후보군 충돌은 없었다. | **동결 벤치마크** |
| 7 | 보정, 방법 동결과 최종 TEST: `phase7a_*`부터 `phase7h_*`, `phase7c2_*`, `phase7f2_*` 포함 | 동결 Phase 6 벤치마크, CALIBRATION 분할, 식별자 중립 증거 | 보정 격자, 동결 매개변수, 검색 감사, 예측, `results/phase7h_final_test_summary.json` | 동결 TEST는 질의 360개와 구성요소 2,520개로 이루어진다. 구성요소 정확도 0.805952, 부모 집합 F1 0.844233, `UNKNOWN` F1 0.753786이다. | **7G에서 방법 동결; 이후 TEST 개봉** |
| 8 | 통계 검증과 제거 실험: `phase8a_bootstrap_statistics.py`, `phase8b_baseline_ablation.py`, `phase8c_source_cluster_sensitivity.py` | 동결 Phase 7 예측과 점수 | 부트스트랩, 제거 실험, 출처 군집 표와 요약 | 계층적 내용 방법은 독립 구성요소 기준선보다 부모 집합 F1이 0.046133 높았다. 그래프 보정과 내용 방법의 차이는 +0.000688로 통계적으로 확정할 수 없었다. | 사후 분석; 재채점·재조정 없음 |
| 9 | 연구 서버와 시스템 평가: `server/phase9a_server.py`; `phase9b_*`부터 `phase9f_*` | 동결 Phase 7 방법·증거와 Phase 6L 패키지 | 정확성 감사, 성능 평가표·요약, 환경 고정 목록 | 질의 360개와 구성요소 2,520개에서 기준 예측과 완전히 일치했다. 동시성 1의 로컬 패키지 p50은 26.880 ms이며, 측정 범위 내 최고 전체 처리량은 38.71 req/s였다. | 알고리즘 동결; 지연 시간은 실행 환경별 결과 |
| 10 | 외부 비교: `phase10a2_*`, `phase10a3_*`, `phase10a4*`, `phase10a5_*` | 동결 TEST 코드 구성요소, 공개 소스 시점 자료, 외부 NiCadCross 출력 | 소스 대응표·감사, 복제 쌍, 대응 예측·요약, StoneDetector 명세 | 동일한 구성요소 1,169개 부분집합에서 제안 방법의 정확도는 0.841, NiCadCross는 0.710이었다. 차이는 +0.131, 대응표본 95% CI는 0.096-0.167이었다. | 외부 비교; TEST 재조정 없음 |
| 11 | 통제된 다중 미등록 출처 강건성: `phase11a_build_multi_unknown_benchmark.py`, `phase11b_run_multi_unknown_robustness.py`, 보고 감사 | 동결 TEST 제공 자료·증거, Phase 7 매개변수와 후보군 | 질의 180개 목록, 변환된 증거, 예측, 감사, `results/phase11c_*`, `phase11d_*` | 질의 180개와 구성요소 1,260개. 구성요소 정확도 0.841, `UNKNOWN` F1 0.888, 단일 `UNKNOWN`으로 합산한 부모 집합 F1 0.884이다. | 동결 후 강건성; 주요 TEST 불변 |
| 12 | 근사 검색 확장성: `phase12a_*`부터 `phase12f_*` | 동결 Phase 7 후보군·증거와 고정된 정확 검색·LSH 설정 | 후보 일치도, 온라인 실행 시간, 최종 예측, 교차점 분석, 보고 감사 | BALANCED와 HIGH_RECALL은 정확 검색과 같은 예측을 냈다. FAST는 질의 1/360개와 구성요소 1/2,520개의 예측을 바꾸었고, 프로젝트 60개에서 p50은 10.315 ms에서 8.848 ms로 줄었다. | 동결 후 시스템 분석; 명세 동결 |
| 13 | 자동 오류 분석: `phase13a_*`부터 `phase13c_*` | 동결 Phase 7H TEST 예측, 검색 감사, 정답 자료 | 오류 유형, 계층적 오류 위치, 보고 감사 | 오류 489개는 구성요소 귀속 325개, `UNKNOWN` 판정 81개, 부모 선택 47개, 검색 36개로 구분된다. | 진단 전용; 명세 동결 |

## 결과 찾기

각 주장에 대응하는 공식 결과 파일은 아래 표에서 확인할 수 있다. 대용량 원본·중간 결과는 재생성할 수 있거나 의도적으로 추적 대상에서 제외하지만, 아래의 요약과 감사 자료는 Git으로 관리한다.

| 질문 | 공식 추적 자료 |
|---|---|
| 신규 데이터셋은 어떻게 분할했는가? | `results/phase6c_project_split.csv`, `results/phase6c_split_summary.json` |
| 벤치마크를 구성하는 질의와 정답은 무엇인가? | `results/phase6k_query_manifest_public.csv`, `results/phase6k_query_manifest_private.csv`, `results/phase6k_query_ground_truth.csv`, `results/phase6k_query_summary.json` |
| 원본 데이터와 그래프를 일관되게 구성했는가? | `results/phase6l_materialized_public_manifest.csv`, `results/phase6l_materialized_private_manifest.csv`, Phase 6L 그래프 CSV와 감사 자료 |
| 동결 방법을 정의하는 매개변수는 무엇인가? | `results/phase7g_final_method_parameters.json`, `results/phase7g_final_method_freeze_summary.json` |
| 최종 TEST 예측과 평가지표는 무엇인가? | `results/phase7h_final_test_component_predictions.csv`, `results/phase7h_final_test_query_predictions.csv`, `results/phase7h_final_test_summary.json` |
| 결과의 불확실성과 제거 실험은 무엇인가? | `results/phase8a_bootstrap_summary.json`, `results/phase8b_baseline_ablation_summary.json`, `results/phase8c_source_cluster_sensitivity_summary.json` |
| 서버가 동결 예측을 재현하는가? | `results/phase9b_server_correctness_summary.json` |
| 각 지연 시간은 처리 과정의 어느 범위를 측정하는가? | `results/phase9c_concurrency_benchmark_summary.json`, `phase9d_evidence_pipeline_summary.json`, `phase9e3_end_to_end_summary.json`, `phase9f_gallery_scalability_summary.json` |
| NiCadCross는 어떻게 비교했는가? | `results/phase10a4d_nicad_summary.json`, `phase10a4e_same_subset_summary.json`, `phase10a4f_nicad_paired_bootstrap_summary.json` |
| 다중 미등록 출처 강건성은 무엇을 보여 주는가? | `results/phase11c_multi_unknown_summary.json`, `results/phase11d_reporting_audit_summary.json` |
| 정확 검색과 LSH 검색의 절충은 어떠한가? | `results/phase12c_online_retrieval_summary.json`, `phase12d_online_pool_downstream_summary.json`, `phase12e_scalability_crossover_summary.json`, `phase12f_reporting_audit_summary.json` |
| 최종 TEST 오류는 어디에서 발생하는가? | `results/phase13a_failure_taxonomy_summary.json`, `phase13b_failure_localization_summary.json`, `phase13c_reporting_audit_summary.json` |

<a id="freeze-anchors-ko"></a>

## 동결 기준점

### Phase 6 벤치마크

1. `results/phase6c_project_split.csv`는 프로젝트 분할을 고정한다: CALIBRATION known 25개, TEST known 45개, held-out unknown 20개, CALIBRATION background 15개, TEST background 15개.
2. `results/phase6k_query_manifest_private.csv`와 `results/phase6k_query_ground_truth.csv`는 질의 구성과 정답을 고정한다.
3. `results/phase6l_materialized_private_manifest.csv`는 로컬 원본 데이터의 해시를 고정한다. 원본 바이트는 계속 Git에서 제외한다.
4. `results/phase6l_graph_natural_public.csv`와 `results/phase6l_graph_connected_stress_public.csv`는 두 그래프 조건을 고정한다.

### Phase 7 방법

1. `results/phase7g_final_method_parameters.json`은 임계값, `alpha`, `lambda`, 후보군 크기, 그래프 beta, 경계 Top-R과 `Kmax`를 고정한다.
2. 기록된 매개변수 SHA-256은 `caad17257304d0ab198e01ef327f5acf918e6b8aab3f00e5272be3d20d3f8325`이다.
3. `results/phase7h_final_test_summary.json`은 동결 이후 TEST를 채점했고 매개변수 해시가 일치했음을 확인한다.

### 동결 후 명세

- `reproducibility/phase12_freeze_manifest.sha256`은 Phase 12 보고 집합을 기록한다.
- `reproducibility/phase13_freeze_manifest.sha256`은 Phase 13 진단 집합을 기록한다.
- Phase 8-13의 출력은 Phase 6 분할, Phase 7 매개변수와 주요 TEST 예측을 변경하지 않는다.

## 실행 참고사항

- 스크립트는 저장소 루트에서 실행한다. 대부분 명령행 선택지 대신 고정 상대 경로를 사용한다.
- 수집과 데이터 구성에는 네트워크 접근과 Git 관리 대상이 아닌 `data/` 경로에 로컬로 보관한 원본 압축파일이 필요하다.
- `phase3d_bytecode_baseline.py`는 추적 중인 `tools/phase3d/JavapBatch.java`를 사용하며, 컴파일된 `.class` 파일은 제외한다.
- Phase 9 의존성은 `results/phase9_environment_freeze.txt`와 `reproducibility/requirements_freeze.txt`에 기록되어 있다.
- Phase 10 NiCadCross 작업에는 외부 Open-NiCad 설치와 복원한 소스 데이터가 필요하다. 도구와 데이터는 저장소에 포함하지 않는다.
- `phase11b_run_multi_unknown_robustness.py`는 동결된 Phase 7H 구현에서 임시 어댑터를 항상 같은 방식으로 생성한다. 현재 생성본은 제외하고 과거 생성본은 감사를 위해 `archive/`에 보존한다.
- Phase 12의 합성 `200eq`/`500eq`/`1000eq` 조건은 실제 등록 부모 100개를 바탕으로 구성요소 배열을 복제한다. 이는 구성요소 수에 대한 부하 시험이며 고유 프로젝트 집단이 아니다.

## 과거 및 제외된 산출물

- 교체된 스크립트, 생성 파일과 오류가 확인된 스크립트는 이력 설명과 함께 `archive/` 아래에 보존하되 현재 처리 과정의 진입점으로 사용하지 않는다.
- 원본 MOD/JAR 압축파일, 제3자 캐시, 외부 도구용 복원 데이터, 가상환경, 컴파일 결과와 대용량 재생성 자료는 Git 밖에 둔다.
- `reproducibility/TRACKING_AUDIT.md`에는 보존 정책과 원래 Phase 1-11 파일 분류 감사가 기록되어 있다.
- `reproducibility/UNTRACKED_CLASSIFICATION.csv`는 로컬 파일의 상세 분류대장이다. 여기에 기록된 경로는 GitHub에 없는 로컬 제외 자료를 가리킬 수 있다.

## 해석상 주의사항

- 이 방법은 기술적 출처 검토를 지원하지만 저작권의 귀속, 침해, 이용 허락 또는 법적 책임을 판단하지 않는다.
- Phase 7 TEST 결과는 동결 방법을 변경하는 데 사용하지 않았다.
- Phase 8에서 그래프가 부모 집합 F1에 미친 영향은 작고 통계적으로 확정할 수 없었다.
- Phase 9의 사전 계산 점수, 증거부터 결과까지, 로컬 패키지부터 결과까지의 지연 시간은 서로 다른 범위를 측정하므로 혼용할 수 없다.
- Phase 10은 소스 코드를 확인할 수 있는 코드만 비교한다. NiCadCross는 복원된 Java 소스를 입력받지만 제안 방법은 동결된 바이너리 측 증거를 사용한다.
- Phase 11은 모든 미등록 출처를 하나의 `UNKNOWN`으로 합치므로 서로 다른 미등록 출처의 정체나 개수를 복원하지 않는다.
- Phase 12 FAST는 완전 무손실이 아니다. 예측을 보존하는 LSH도 평가한 모든 규모에서 벡터화된 전수 검색보다 빠르지는 않았다.
- Phase 13은 기존 예측의 기술적 오류 위치를 분석하는 단계이며 새로운 모델 평가나 매개변수 선택 단계가 아니다.

---

<a id="experiment-ja"></a>

# 実験インデックス：Phase 1-13

[![English](https://img.shields.io/badge/EN-English-6E7781?style=for-the-badge)](#user-content-experiment-en) [![한국어](https://img.shields.io/badge/KO-%ED%95%9C%EA%B5%AD%EC%96%B4-6E7781?style=for-the-badge)](#user-content-experiment-ko) [![日本語](https://img.shields.io/badge/JA-%E6%97%A5%E6%9C%AC%E8%AA%9E-0969DA?style=for-the-badge)](#user-content-experiment-ja)

最終文書監査日：2026-08-19。すべてのパスはリポジトリルートからの相対パスである。

本書は、保存済みの研究記録をPhaseごとに結び付けた索引である。探索段階と凍結済みの確認評価を区別し、各Phaseのスクリプト、入力、報告対象の出力、主要結果、凍結状況を併記する。

`凍結`は、後続作業においてデータ分割、正解ラベル、パラメータ、評価手順、記録済みハッシュを変更せずに当該資料を使用することを示す。`完了`と表示したPhaseでも、探索、事後分析、診断、または特定の実行環境に限定した作業の場合があり、完了が確認評価を意味するとは限らない。

## Phase別マップ

| Phase | 目的とスクリプト | 主な入力 | 報告対象の出力 | 主要結果 | 状況 |
|---:|---|---|---|---|---|
| 1 | 予備調査と実在MODの収集：`phase1_collect.py`、`phase1b_collect_real_mods.py` | 公開リポジトリとModrinthメタデータ | `results/dataset_*.csv`、`results/phase1*_summary.json` | 予備リポジトリ10件。実在MODデータセットはMOD 30件、コード5,732件、構造化ファイル888件、画像ファイル357件で構成される。 | 完了；探索段階の時点資料 |
| 2 | データセット・リリース一覧の構築：`phase2a_freeze_corpus.py`、`phase2b_build_registry.py`、`phase2c_build_release_registry.py` | Phase 1データセット、リポジトリのコミット、公開リリースメタデータ | データセット・リリース一覧、重複監査、`results/phase2*_summary.json` | ソース時点資料30/30件とリリースファイル30/30件を確認した。リリースのコンポーネントは7,677件で、MOD間の重複グループはなかった。 | 過去ソースの時点資料を凍結；原本ファイルは除外 |
| 3 | バージョン差分と内容・バイトコードのベースライン：`phase3a_*`から`phase3e_*`；`tools/phase3d/JavapBatch.java` | Phase 2リリースと過去バージョン | パス・内容・バイトコード・パッケージ表と`results/phase3*_summary.json` | OPCODE_CONTEXT信頼度投票は過去45パッケージで、パッケージtop-1一意正解率0.578、top-5 0.911を記録した。 | ベースライン保存；最終TESTではない |
| 4 | 依存関係とリソース参照グラフ：`phase4a_*`から`phase4c_*` | リリース一覧と抽出メタデータ | グラフ診断、未解決参照表、`results/phase4*_summary.json` | 補強済みの辺25,987件。最大連結成分率の中央値は0.818であった。 | 手順保存；最終TESTグラフではない |
| 5 | 探索的な複数親再構成：`phase5a_*`から`phase5h_*`、`phase5c2_*`を含む | Phase 3/4の証拠と合成複数親クエリ | 複数親の原資料・要約表と`results/phase5*_summary.json` | 合成CLEAN TEST部分の150クエリで、統合階層手法のコンポーネント正解率は0.405、親集合F1は0.504であった。 | 探索的手法開発 |
| 6 | 新規データセット・ベンチマーク生成とクエリ構成：`phase6a_*`から`phase6l_*` | 新規公開メタデータ・リリース、過去一覧、抽出済み原本データ | 凍結済み分割；Phase 6Kクエリ一覧・正解；Phase 6L原本ハッシュ一覧・グラフ；監査と要約 | 120プロジェクト（対象90、背景30）、540クエリ、構成済みコンポーネント3,780件。ソースハッシュを検証し、完全一致段階の候補群衝突はなかった。 | **凍結ベンチマーク** |
| 7 | 較正、手法凍結、最終TEST：`phase7a_*`から`phase7h_*`、`phase7c2_*`、`phase7f2_*`を含む | 凍結済みPhase 6ベンチマーク、CALIBRATION分割、識別子に依存しない証拠 | 較正グリッド、凍結パラメータ、検索監査、予測、`results/phase7h_final_test_summary.json` | 凍結TESTは360クエリ、2,520コンポーネントで構成される。コンポーネント正解率0.805952、親集合F1 0.844233、`UNKNOWN` F1 0.753786である。 | **7Gで手法凍結；その後TESTを開封** |
| 8 | 統計検証とアブレーション：`phase8a_bootstrap_statistics.py`、`phase8b_baseline_ablation.py`、`phase8c_source_cluster_sensitivity.py` | 凍結済みPhase 7予測とスコア | ブートストラップ、アブレーション、由来クラスタ表と要約 | 階層的な内容ベース手法は、独立コンポーネントのベースラインより親集合F1が0.046133高かった。グラフ補正と内容ベース手法の差は+0.000688で、統計的に確定できなかった。 | 事後分析；再採点・再調整なし |
| 9 | 研究サーバーとシステム評価：`server/phase9a_server.py`；`phase9b_*`から`phase9f_*` | 凍結済みPhase 7手法・証拠とPhase 6Lパッケージ | 正確性監査、性能評価表・要約、環境固定一覧 | 360クエリ、2,520コンポーネントで参照予測と完全に一致した。並行数1のローカルパッケージp50は26.880 ms、測定範囲内の最高エンドツーエンド処理量は38.71 req/sであった。 | アルゴリズム凍結；処理時間は実行環境固有 |
| 10 | 外部比較：`phase10a2_*`、`phase10a3_*`、`phase10a4*`、`phase10a5_*`；論文用スクリプト | 凍結TESTコードコンポーネント、公開ソースの時点資料、外部NiCadCross出力 | ソース対応表・監査、クローン対、対応予測・要約、StoneDetectorマニフェスト | 同じ1,169コンポーネントの部分集合で、提案手法の正解率は0.841、NiCadCrossは0.710であった。差は+0.131、対応あり95% CIは0.096-0.167であった。 | 外部比較；TEST再調整なし |
| 11 | 制御条件下の複数未登録由来に対する頑健性：`phase11a_build_multi_unknown_benchmark.py`、`phase11b_run_multi_unknown_robustness.py`、報告監査 | 凍結TESTの提供資料・証拠、Phase 7パラメータと候補群 | 180クエリの一覧、変換済み証拠、予測、監査、`results/phase11c_*`、`phase11d_*` | 180クエリ、1,260コンポーネント。コンポーネント正解率0.841、`UNKNOWN` F1 0.888、単一の`UNKNOWN`にまとめた親集合F1 0.884である。 | 凍結後の頑健性；主要TESTは不変 |
| 12 | 近似検索のスケーラビリティ：`phase12a_*`から`phase12f_*` | 凍結済みPhase 7候補群・証拠と固定済みの厳密検索・LSH設定 | 候補一致度、オンライン実行時間、最終予測、交差点分析、報告監査 | BALANCEDとHIGH_RECALLは厳密検索と同一の予測を出力した。FASTはクエリ1/360件とコンポーネント1/2,520件の予測を変更し、60プロジェクトでp50は10.315 msから8.848 msへ短縮した。 | 凍結後のシステム分析；マニフェスト凍結 |
| 13 | 自動誤り分析：`phase13a_*`から`phase13c_*` | 凍結済みPhase 7H TEST予測、検索監査、正解資料 | 誤り分類、階層的な誤り位置、報告監査 | 誤り489件は、コンポーネント帰属325件、`UNKNOWN`判定81件、親選択47件、検索36件に分かれる。 | 診断専用；マニフェスト凍結 |

## 結果の参照先

各主張に対応する正式な結果ファイルを以下に示す。大容量の原本・中間結果は、再生成可能または意図的に追跡対象外としている場合がある。一方、下記の要約と監査資料はGitで管理している。

| 質問 | 正式な追跡資料 |
|---|---|
| 新規データセットをどのように分割したか？ | `results/phase6c_project_split.csv`、`results/phase6c_split_summary.json` |
| ベンチマークを構成するクエリと正解ラベルは何か？ | `results/phase6k_query_manifest_public.csv`、`results/phase6k_query_manifest_private.csv`、`results/phase6k_query_ground_truth.csv`、`results/phase6k_query_summary.json` |
| 原本データとグラフを一貫した手順で構成したか？ | `results/phase6l_materialized_public_manifest.csv`、`results/phase6l_materialized_private_manifest.csv`、Phase 6LグラフCSVと監査資料 |
| 凍結手法を定義するパラメータは何か？ | `results/phase7g_final_method_parameters.json`、`results/phase7g_final_method_freeze_summary.json` |
| 最終TESTの予測と評価指標は何か？ | `results/phase7h_final_test_component_predictions.csv`、`results/phase7h_final_test_query_predictions.csv`、`results/phase7h_final_test_summary.json` |
| 結果の不確実性とアブレーションは何か？ | `results/phase8a_bootstrap_summary.json`、`results/phase8b_baseline_ablation_summary.json`、`results/phase8c_source_cluster_sensitivity_summary.json` |
| サーバーは凍結済み予測を再現するか？ | `results/phase9b_server_correctness_summary.json` |
| 各処理時間は処理系のどの範囲を測定するか？ | `results/phase9c_concurrency_benchmark_summary.json`、`phase9d_evidence_pipeline_summary.json`、`phase9e3_end_to_end_summary.json`、`phase9f_gallery_scalability_summary.json` |
| NiCadCrossをどのように比較したか？ | `results/phase10a4d_nicad_summary.json`、`phase10a4e_same_subset_summary.json`、`phase10a4f_nicad_paired_bootstrap_summary.json` |
| 複数未知由来への頑健性は何を示すか？ | `results/phase11c_multi_unknown_summary.json`、`results/phase11d_reporting_audit_summary.json` |
| 厳密検索とLSH検索のトレードオフは何か？ | `results/phase12c_online_retrieval_summary.json`、`phase12d_online_pool_downstream_summary.json`、`phase12e_scalability_crossover_summary.json`、`phase12f_reporting_audit_summary.json` |
| 最終TESTの誤りはどこで発生するか？ | `results/phase13a_failure_taxonomy_summary.json`、`phase13b_failure_localization_summary.json`、`phase13c_reporting_audit_summary.json` |

<a id="freeze-anchors-ja"></a>

## 凍結の基準資料

### Phase 6ベンチマーク

1. `results/phase6c_project_split.csv`はプロジェクト分割を固定する：CALIBRATION known 25、TEST known 45、held-out unknown 20、CALIBRATION background 15、TEST background 15。
2. `results/phase6k_query_manifest_private.csv`と`results/phase6k_query_ground_truth.csv`は、クエリ構成と正解ラベルを固定する。
3. `results/phase6l_materialized_private_manifest.csv`は、ローカル原本データのハッシュを固定する。原本バイト列は引き続きGitから除外する。
4. `results/phase6l_graph_natural_public.csv`と`results/phase6l_graph_connected_stress_public.csv`は、2つのグラフ条件を固定する。

### Phase 7手法

1. `results/phase7g_final_method_parameters.json`は、しきい値、`alpha`、`lambda`、候補群サイズ、グラフbeta、境界Top-R、`Kmax`を固定する。
2. 記録済みパラメータのSHA-256は`caad17257304d0ab198e01ef327f5acf918e6b8aab3f00e5272be3d20d3f8325`である。
3. `results/phase7h_final_test_summary.json`は、凍結後にTESTを採点し、パラメータのハッシュが一致したことを確認する。

### 凍結後のマニフェスト

- `reproducibility/phase12_freeze_manifest.sha256`はPhase 12の報告集合を記録する。
- `reproducibility/phase13_freeze_manifest.sha256`はPhase 13の診断集合を記録する。
- Phase 8-13の出力は、Phase 6の分割、Phase 7のパラメータ、主要TEST予測を変更しない。

## 実行上の注意

- スクリプトはリポジトリルートから実行する。多くはコマンドライン引数ではなく、固定の相対パスを使用する。
- 収集とデータ構成には、ネットワーク接続と、Git管理対象外の`data/`パスにローカル保存した原本アーカイブが必要である。
- `phase3d_bytecode_baseline.py`は追跡中の`tools/phase3d/JavapBatch.java`を使用し、コンパイル済み`.class`ファイルは除外する。
- Phase 9の依存関係は`results/phase9_environment_freeze.txt`と`reproducibility/requirements_freeze.txt`に記録している。
- Phase 10のNiCadCross作業には、外部Open-NiCadの導入と復元済みソースデータが必要である。ツールとデータは同梱しない。
- `phase11b_run_multi_unknown_robustness.py`は、凍結済みPhase 7H実装から一時アダプターを常に同じ手順で生成する。現在の生成物は除外し、過去の生成物は監査用として`archive/`に保存する。
- Phase 12の合成`200eq`/`500eq`/`1000eq`条件は、100件の実在する登録済み親を基にコンポーネント配列を複製する。これはコンポーネント数に対する負荷試験であり、固有プロジェクトの集団ではない。

## 過去および除外対象の成果物

- 旧版、生成物、不具合が確認されたスクリプトは、履歴説明とともに`archive/`配下に保存するが、現在の処理系の実行開始点には使用しない。
- 生のMOD/JARアーカイブ、第三者キャッシュ、外部ツール用の復元データ、仮想環境、コンパイル結果、大容量の再生成可能資料はGit外に置く。
- `reproducibility/TRACKING_AUDIT.md`には、保存方針と当初のPhase 1-11ファイル分類監査を記録している。
- `reproducibility/UNTRACKED_CLASSIFICATION.csv`は、ローカルファイルの詳細な分類台帳である。記載パスがGitHubに存在しないローカル除外資料を示す場合がある。

## 解釈上の注意事項

- 本手法は技術的な由来確認を支援するものであり、著作権の帰属、侵害、利用許諾、法的責任を判断しない。
- Phase 7 TEST結果は、凍結済み手法の変更に用いていない。
- Phase 8でグラフが親集合F1に与えた影響は小さく、統計的に確定できなかった。
- Phase 9の事前計算スコア、証拠から結果まで、ローカルパッケージから結果までの処理時間は、それぞれ測定範囲が異なるため混同できない。
- Phase 10では、ソースコードを対応付けられたコードのみを比較する。NiCadCrossには復元済みJavaソースを入力する一方、提案手法は凍結済みのバイナリ側証拠を用いる。
- Phase 11では、すべての未登録由来を1つの`UNKNOWN`にまとめるため、異なる未登録由来の同定や個数の復元は行わない。
- Phase 12のFASTは完全な無損失ではない。予測を維持するLSHも、評価したすべての規模でベクトル化全数検索より高速だったわけではない。
- Phase 13は既存予測の技術的な誤り位置を分析する段階であり、新しいモデル評価やパラメータ選択の段階ではない。
