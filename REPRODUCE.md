<a id="reproduce-en"></a>

# Reproducing the Research Workflow

[![English](https://img.shields.io/badge/EN-English-0969DA?style=for-the-badge)](#user-content-reproduce-en) [![한국어](https://img.shields.io/badge/KO-%ED%95%9C%EA%B5%AD%EC%96%B4-6E7781?style=for-the-badge)](#user-content-reproduce-ko) [![日本語](https://img.shields.io/badge/JA-%E6%97%A5%E6%9C%AC%E8%AA%9E-6E7781?style=for-the-badge)](#user-content-reproduce-ja)

[← Repository overview](README.md#user-content-readme-en)

This repository preserves the code and metadata needed to trace Phase 1 through Phase 13. It intentionally does not redistribute third-party MOD/JAR payloads, cloned repositories, generated query packages, or external tools.

## 1. Environment

The system benchmark's tested Python environment is pinned in `requirements.txt` and duplicated verbatim in `results/phase9_environment_freeze.txt`.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The recorded WSL toolchain used Python 3.12.3, OpenJDK 11.0.31, and Git 2.43.0. Phase 9 performance measurements used Windows Python 3.10.6; therefore exact latency values are host- and environment-specific. See the [environment record](reproducibility/ENVIRONMENT.md#user-content-environment-en) before comparing timings.

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
Phase 12 post-freeze Exact-vs-LSH retrieval/scalability evaluation
Phase 13 post-freeze automated failure analysis
```

The exact scripts, inputs, outputs, results, and freeze status for each phase are listed in the [Experiment Index](reproducibility/EXPERIMENT_INDEX.md#user-content-experiment-en).

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

## 8. Phase 12 approximate retrieval and scalability

Run in order:

- `scripts/phase12a_ann_candidate_benchmark.py`
- `scripts/phase12b_ann_downstream_evaluation.py`
- `scripts/phase12c_online_retrieval_runtime.py`
- `scripts/phase12d_online_pool_downstream_evaluation.py`
- `scripts/phase12e_scalability_crossover.py`
- `scripts/phase12f_reporting_audit.py`

Use Phase 12C/12D for full 360-query fidelity results. Phase 12E is a deterministic 120-query runtime/scalability sample.

`200eq`, `500eq`, and `1000eq` are synthetic component-volume stress conditions over 100 real registered parents, not unique-project counts.

Verify the frozen Phase 12 state with:

- `reproducibility/phase12_freeze_manifest.sha256`
- `results/phase12f_reporting_audit_summary.json`

## 9. Phase 13 failure analysis

Run in order:

- `scripts/phase13a_failure_taxonomy.py`
- `scripts/phase13b_hierarchical_failure_localization.py`
- `scripts/phase13c_reporting_audit.py`

This phase reads the existing frozen predictions and audits. It is diagnostic only: it must not recompute the primary predictions or be used to retune the frozen method.

Verify the frozen Phase 13 state with:

- `reproducibility/phase13_freeze_manifest.sha256`
- `results/phase13c_reporting_audit_summary.json`

## 10. Expected preserved endpoints

- Primary frozen TEST: `results/phase7h_final_test_summary.json`
- Statistical analysis: `results/phase8a_bootstrap_summary.json`, `phase8b_baseline_ablation_summary.json`, `phase8c_source_cluster_sensitivity_summary.json`
- System evaluation: `results/phase9b_server_correctness_summary.json` through `phase9f_gallery_scalability_summary.json`
- External baseline: `results/phase10a4f_nicad_paired_bootstrap_summary.json`
- Multi-UNKNOWN robustness: `results/phase11c_multi_unknown_summary.json`
- Approximate retrieval/scalability: `results/phase12f_reporting_audit_summary.json`
- Failure analysis: `results/phase13a_failure_taxonomy_summary.json`, `phase13b_failure_localization_summary.json`, `phase13c_reporting_audit_summary.json`

If regenerated endpoint metrics differ, stop and compare frozen input hashes, environment versions, and the relevant detailed audit tables before interpreting the discrepancy.

---

<a id="reproduce-ko"></a>

# 연구 워크플로 재현하기

[![English](https://img.shields.io/badge/EN-English-6E7781?style=for-the-badge)](#user-content-reproduce-en) [![한국어](https://img.shields.io/badge/KO-%ED%95%9C%EA%B5%AD%EC%96%B4-0969DA?style=for-the-badge)](#user-content-reproduce-ko) [![日本語](https://img.shields.io/badge/JA-%E6%97%A5%E6%9C%AC%E8%AA%9E-6E7781?style=for-the-badge)](#user-content-reproduce-ja)

[← 한국어 저장소 소개](README.md#user-content-readme-ko)

이 저장소는 Phase 1부터 Phase 13까지 추적하는 데 필요한 코드와 metadata를 보존합니다. 제3자 MOD/JAR payload, clone한 저장소, 생성된 query package 또는 외부 도구는 의도적으로 재배포하지 않습니다.

## 1. 환경

System benchmark에서 시험한 Python 환경은 `requirements.txt`에 고정되어 있으며 `results/phase9_environment_freeze.txt`에도 동일한 내용이 그대로 보존되어 있습니다.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

기록된 WSL toolchain은 Python 3.12.3, OpenJDK 11.0.31, Git 2.43.0을 사용했습니다. Phase 9 성능 측정은 Windows Python 3.10.6을 사용했으므로 정확한 latency 값은 host와 환경에 따라 달라집니다. 시간을 비교하기 전에 [환경 기록](reproducibility/ENVIRONMENT.md#user-content-environment-ko)을 확인하세요.

## 2. 제외된 input 복원

Raw archive는 Git에 없습니다. 추적되는 project/version identifier, download URL, content hash, snapshot commit 및 mapping audit를 사용하여 각 script가 기대하는 경로에 복원하세요. 중요한 복원 metadata는 다음과 같습니다.

- `results/phase6a_fresh_corpus.csv`
- `results/phase6c_project_split.csv`
- `results/phase10a3_repository_snapshot_audit.csv`
- `results/phase10a3_class_to_java_mapping.csv`
- `results/phase9e_package_manifest.csv`

후속 단계를 실행하기 전에 다운로드한 파일의 SHA-1/SHA-256/SHA-512 필드를 추적된 값과 대조하세요. 복원한 archive나 추출 payload를 commit하지 마세요.

## 3. 실행 순서

대부분의 script는 범용 command-line application이 아니라 경로 상수가 고정된 연구 protocol 프로그램입니다. 저장소 루트에서 실행하세요.

```text
Phase 1  수집
Phase 2  corpus/release 동결
Phase 3  과거 baseline
Phase 4  graph 추출
Phase 5  합성 방법 탐색
Phase 6  신규 benchmark 및 동결 query/graph 구축
Phase 7  calibration -> 방법 동결 -> 최종 TEST
Phase 8  사후 통계 및 ablation
Phase 9  server 정확성과 성능
Phase 10 source/외부 baseline 호환성
Phase 11 동결 후 다중 UNKNOWN 강건성
Phase 12 동결 후 Exact-vs-LSH retrieval/확장성 평가
Phase 13 동결 후 자동 실패 분석
```

각 Phase의 정확한 script, input, output, 결과 및 동결 상태는 [실험 인덱스](reproducibility/EXPERIMENT_INDEX.md#user-content-experiment-ko)에 정리되어 있습니다.

## 4. 평가 전 동결 확인

Phase 7H 또는 이후 분석을 재현하기 전에 다음을 확인하세요.

1. `results/phase7g_final_method_parameters.json`의 SHA-256이 `caad17257304d0ab198e01ef327f5acf918e6b8aab3f00e5272be3d20d3f8325`인지 확인합니다.
2. Phase 6C split과 Phase 6K/6L manifest가 `reproducibility/FROZEN_ARTIFACT_SHA256.txt`와 일치하는지 확인합니다.
3. TEST를 확인한 뒤에는 threshold, `alpha`, `lambda`, candidate-pool 크기, graph beta, boundary Top-R 또는 `Kmax`를 변경하지 않습니다.
4. 평가 전용 label은 scoring boundary 이외에서 model/pipeline이 접근하지 못하게 유지합니다.

## 5. Phase 9 service

보존된 service 구현은 다음과 같습니다.

- `server/phase9a_server.py`: 미리 계산한 score에서 동결 reconstruction 수행
- `server/phase9d_evidence_server.py`: 식별자 중립 evidence에서 gallery search와 reconstruction 수행
- `server/phase9e3_package_server.py`: local materialized package에서 extraction과 reconstruction 수행
- `server/phase9f_scalability_server.py`: gallery 크기 확장성 service

해당 server가 정상 상태를 보고한 뒤에 일치하는 Phase 9 benchmark script를 실행하세요. Latency를 보고할 때 benchmark 범위를 보존해야 합니다. Phase 9C, 9D, 9E3는 pipeline의 서로 다른 부분을 포함합니다.

## 6. Phase 10 외부 도구

Open-NiCad/NiCadCross는 저장소에 포함하지 않습니다. 별도로 설치하고 Phase 10 mapping에서 추적하는 query/gallery source corpus를 복원하세요. 보관된 `phase10a4d_score_nicad_v1_buggy.py`는 유효하지 않으므로 사용하면 안 됩니다. `scripts/phase10a4d_score_nicad.py`를 사용하세요.

## 7. Phase 11 생성 adapter

`scripts/phase11b_run_multi_unknown_robustness.py`를 실행하세요. 이 script는 정확한 Phase 7B donor evidence를 재사용하고 `scripts/_phase11b_phase7h_adapter_generated.py`에 임시 adapter를 생성합니다. 추적되는 driver가 이를 결정론적으로 재생성하므로 활성 생성 파일은 무시됩니다. 보존된 실행에서 사용한 과거 adapter는 감사를 위해 `archive/generated/` 아래에 있습니다.

## 8. Phase 12 근사 retrieval 및 확장성

다음 순서로 실행하세요.

- `scripts/phase12a_ann_candidate_benchmark.py`
- `scripts/phase12b_ann_downstream_evaluation.py`
- `scripts/phase12c_online_retrieval_runtime.py`
- `scripts/phase12d_online_pool_downstream_evaluation.py`
- `scripts/phase12e_scalability_crossover.py`
- `scripts/phase12f_reporting_audit.py`

360개 query 전체의 fidelity 결과에는 Phase 12C/12D를 사용하세요. Phase 12E는 결정론적으로 뽑은 120개 query runtime/확장성 sample입니다.

`200eq`, `500eq`, `1000eq`는 실제 등록 부모 100개에 대한 합성 component-volume stress 조건이며 고유 프로젝트 수가 아닙니다.

다음 파일로 동결 Phase 12 상태를 확인하세요.

- `reproducibility/phase12_freeze_manifest.sha256`
- `results/phase12f_reporting_audit_summary.json`

## 9. Phase 13 실패 분석

다음 순서로 실행하세요.

- `scripts/phase13a_failure_taxonomy.py`
- `scripts/phase13b_hierarchical_failure_localization.py`
- `scripts/phase13c_reporting_audit.py`

이 Phase는 기존 동결 prediction과 audit를 읽습니다. 진단 전용이므로 1차 prediction을 다시 계산하거나 동결 방법을 재조정하는 데 사용하면 안 됩니다.

다음 파일로 동결 Phase 13 상태를 확인하세요.

- `reproducibility/phase13_freeze_manifest.sha256`
- `results/phase13c_reporting_audit_summary.json`

## 10. 보존된 예상 endpoint

- 1차 동결 TEST: `results/phase7h_final_test_summary.json`
- 통계 분석: `results/phase8a_bootstrap_summary.json`, `phase8b_baseline_ablation_summary.json`, `phase8c_source_cluster_sensitivity_summary.json`
- System 평가: `results/phase9b_server_correctness_summary.json`부터 `phase9f_gallery_scalability_summary.json`
- 외부 baseline: `results/phase10a4f_nicad_paired_bootstrap_summary.json`
- 다중 UNKNOWN 강건성: `results/phase11c_multi_unknown_summary.json`
- 근사 retrieval/확장성: `results/phase12f_reporting_audit_summary.json`
- 실패 분석: `results/phase13a_failure_taxonomy_summary.json`, `phase13b_failure_localization_summary.json`, `phase13c_reporting_audit_summary.json`

재생성한 endpoint metric이 다르면 차이를 해석하기 전에 중단하고 동결 input hash, 환경 version 및 관련 상세 audit table을 비교하세요.

---

<a id="reproduce-ja"></a>

# 研究ワークフローの再現

[![English](https://img.shields.io/badge/EN-English-6E7781?style=for-the-badge)](#user-content-reproduce-en) [![한국어](https://img.shields.io/badge/KO-%ED%95%9C%EA%B5%AD%EC%96%B4-6E7781?style=for-the-badge)](#user-content-reproduce-ko) [![日本語](https://img.shields.io/badge/JA-%E6%97%A5%E6%9C%AC%E8%AA%9E-0969DA?style=for-the-badge)](#user-content-reproduce-ja)

[← 日本語のリポジトリ概要](README.md#user-content-readme-ja)

本リポジトリは、Phase 1からPhase 13までを追跡するために必要なコードとmetadataを保存しています。第三者のMOD/JAR payload、cloneしたリポジトリ、生成query package、外部toolは意図的に再配布しません。

## 1. 環境

System benchmarkで試験したPython環境は`requirements.txt`に固定され、`results/phase9_environment_freeze.txt`にも同じ内容がそのまま保存されています。

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

記録済みWSL toolchainはPython 3.12.3、OpenJDK 11.0.31、Git 2.43.0を使用しました。Phase 9性能測定はWindows Python 3.10.6を使用したため、正確なlatency値はhostと環境に依存します。時間を比較する前に[環境記録](reproducibility/ENVIRONMENT.md#user-content-environment-ja)を確認してください。

## 2. 除外inputの復元

Raw archiveはGitにありません。追跡対象のproject/version identifier、download URL、content hash、snapshot commit、mapping auditを用いて、各scriptが想定するpathへ復元してください。重要な復元metadataは次のとおりです。

- `results/phase6a_fresh_corpus.csv`
- `results/phase6c_project_split.csv`
- `results/phase10a3_repository_snapshot_audit.csv`
- `results/phase10a3_class_to_java_mapping.csv`
- `results/phase9e_package_manifest.csv`

後続段階を実行する前に、downloadしたファイルを追跡済みSHA-1/SHA-256/SHA-512 fieldと照合してください。復元archiveや抽出payloadをcommitしないでください。

## 3. 実行順序

多くのscriptは汎用command-line applicationではなく、path定数を固定した研究protocolプログラムです。リポジトリルートから実行してください。

```text
Phase 1  収集
Phase 2  corpus/release凍結
Phase 3  旧baseline
Phase 4  graph抽出
Phase 5  合成手法の探索
Phase 6  新規benchmarkと凍結query/graph構築
Phase 7  calibration -> 手法凍結 -> 最終TEST
Phase 8  事後統計とablation
Phase 9  server正確性と性能
Phase 10 source/外部baseline互換性
Phase 11 凍結後の複数UNKNOWN頑健性
Phase 12 凍結後のExact-vs-LSH retrieval/スケーラビリティ評価
Phase 13 凍結後の自動失敗分析
```

各Phaseの正確なscript、input、output、結果、凍結状況は[実験インデックス](reproducibility/EXPERIMENT_INDEX.md#user-content-experiment-ja)に記載しています。

## 4. 評価前の凍結確認

Phase 7Hまたはそれ以降の分析を再現する前に、次を確認してください。

1. `results/phase7g_final_method_parameters.json`のSHA-256が`caad17257304d0ab198e01ef327f5acf918e6b8aab3f00e5272be3d20d3f8325`であること。
2. Phase 6C splitおよびPhase 6K/6L manifestが`reproducibility/FROZEN_ARTIFACT_SHA256.txt`と一致すること。
3. TESTを確認した後はthreshold、`alpha`、`lambda`、candidate-pool size、graph beta、boundary Top-R、`Kmax`を変更しないこと。
4. 評価専用labelにはscoring boundary以外でmodel/pipelineからアクセスできないようにすること。

## 5. Phase 9 service

保存済みservice実装は次のとおりです。

- `server/phase9a_server.py`：事前計算scoreからの凍結reconstruction
- `server/phase9d_evidence_server.py`：識別子中立evidenceからgallery searchとreconstruction
- `server/phase9e3_package_server.py`：local materialized packageからextractionとreconstruction
- `server/phase9f_scalability_server.py`：gallery-sizeスケーラビリティservice

対応するserverが正常状態を報告してから、一致するPhase 9 benchmark scriptを実行してください。Latencyを報告するときはbenchmark範囲を維持してください。Phase 9C、9D、9E3はpipelineの異なる部分を含みます。

## 6. Phase 10外部tool

Open-NiCad/NiCadCrossは同梱しません。別途installし、Phase 10 mappingで追跡するquery/gallery source corpusを復元してください。保管された`phase10a4d_score_nicad_v1_buggy.py`は無効であり、使用してはいけません。`scripts/phase10a4d_score_nicad.py`を使用してください。

## 7. Phase 11生成adapter

`scripts/phase11b_run_multi_unknown_robustness.py`を実行してください。このscriptは正確なPhase 7B donor evidenceを再利用し、`scripts/_phase11b_phase7h_adapter_generated.py`に一時adapterを生成します。追跡済みdriverが決定論的に再生成するため、active生成ファイルは無視されます。保存runで使用した過去adapterは監査用として`archive/generated/`にあります。

## 8. Phase 12近似retrievalとスケーラビリティ

次の順序で実行してください。

- `scripts/phase12a_ann_candidate_benchmark.py`
- `scripts/phase12b_ann_downstream_evaluation.py`
- `scripts/phase12c_online_retrieval_runtime.py`
- `scripts/phase12d_online_pool_downstream_evaluation.py`
- `scripts/phase12e_scalability_crossover.py`
- `scripts/phase12f_reporting_audit.py`

360 query全体のfidelity結果にはPhase 12C/12Dを使用してください。Phase 12Eは決定論的に選んだ120 queryのruntime/スケーラビリティsampleです。

`200eq`、`500eq`、`1000eq`は実登録親100件に対する合成component-volume stress条件であり、一意なプロジェクト数ではありません。

次のファイルで凍結Phase 12状態を確認してください。

- `reproducibility/phase12_freeze_manifest.sha256`
- `results/phase12f_reporting_audit_summary.json`

## 9. Phase 13失敗分析

次の順序で実行してください。

- `scripts/phase13a_failure_taxonomy.py`
- `scripts/phase13b_hierarchical_failure_localization.py`
- `scripts/phase13c_reporting_audit.py`

このPhaseは既存の凍結predictionとauditを読み取ります。診断専用であり、主要predictionを再計算したり、凍結手法の再調整に使用したりしてはいけません。

次のファイルで凍結Phase 13状態を確認してください。

- `reproducibility/phase13_freeze_manifest.sha256`
- `results/phase13c_reporting_audit_summary.json`

## 10. 保存済みの期待endpoint

- 主要凍結TEST：`results/phase7h_final_test_summary.json`
- 統計分析：`results/phase8a_bootstrap_summary.json`、`phase8b_baseline_ablation_summary.json`、`phase8c_source_cluster_sensitivity_summary.json`
- System評価：`results/phase9b_server_correctness_summary.json`から`phase9f_gallery_scalability_summary.json`
- 外部baseline：`results/phase10a4f_nicad_paired_bootstrap_summary.json`
- 複数UNKNOWN頑健性：`results/phase11c_multi_unknown_summary.json`
- 近似retrieval/スケーラビリティ：`results/phase12f_reporting_audit_summary.json`
- 失敗分析：`results/phase13a_failure_taxonomy_summary.json`、`phase13b_failure_localization_summary.json`、`phase13c_reporting_audit_summary.json`

再生成したendpoint metricが異なる場合は、差を解釈する前に停止し、凍結input hash、環境version、関連する詳細audit tableを比較してください。
