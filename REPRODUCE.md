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

이 저장소에는 Phase 1부터 Phase 13까지의 연구 과정을 재현하는 데 필요한 코드와 메타데이터가 보존되어 있다. 제3자 MOD/JAR 원본, 복제한 외부 저장소, 생성된 질의 패키지와 외부 도구는 재배포하지 않는다.

## 1. 환경

시스템 성능 평가에 사용한 Python 환경은 `requirements.txt`와 `results/phase9_environment_freeze.txt`에 동일하게 고정되어 있다.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

WSL 실행 기록은 Python 3.12.3, OpenJDK 11.0.31과 Git 2.43.0을 사용한다. Phase 9의 성능 측정은 Windows Python 3.10.6에서 수행했으므로 정확한 지연 시간은 실행 컴퓨터와 환경에 따라 달라진다. 성능 수치를 비교할 때에는 [환경 기록](reproducibility/ENVIRONMENT.md#user-content-environment-ko)을 함께 확인해야 한다.

## 2. 제외된 입력 자료 복원

원본 압축파일은 Git에 포함하지 않는다. 추적 중인 프로젝트·버전 식별자, 내려받기 주소, 내용 해시, 특정 시점의 커밋과 대응표 감사를 이용하여 각 스크립트가 요구하는 경로에 자료를 복원한다. 주요 복원 자료는 다음과 같다.

- `results/phase6a_fresh_corpus.csv`
- `results/phase6c_project_split.csv`
- `results/phase10a3_repository_snapshot_audit.csv`
- `results/phase10a3_class_to_java_mapping.csv`
- `results/phase9e_package_manifest.csv`

후속 단계를 실행하기 전에 내려받은 파일의 SHA-1/SHA-256/SHA-512를 추적된 값과 대조한다. 복원한 압축파일과 추출한 원본 데이터는 커밋하지 않는다.

## 3. 실행 순서

대부분의 스크립트는 범용 명령행 프로그램이 아니라 경로와 절차가 고정된 연구용 프로그램이다. 저장소 루트에서 실행한다.

```text
Phase 1  수집
Phase 2  데이터셋·릴리스 동결
Phase 3  과거 기준선
Phase 4  그래프 추출
Phase 5  합성 방법 탐색
Phase 6  신규 벤치마크 및 동결 질의·그래프 구축
Phase 7  보정 -> 방법 동결 -> 최종 TEST
Phase 8  사후 통계 및 제거 실험
Phase 9  서버 정확성과 성능
Phase 10 소스·외부 기준선 호환성
Phase 11 동결 후 다중 UNKNOWN 강건성
Phase 12 동결 후 정확 검색·LSH 검색의 성능과 확장성 평가
Phase 13 동결 후 자동 실패 분석
```

각 Phase의 스크립트, 입력, 출력, 결과와 동결 상태는 [실험 인덱스](reproducibility/EXPERIMENT_INDEX.md#user-content-experiment-ko)에 정리되어 있다.

## 4. 평가 전 동결 확인

Phase 7H 또는 이후 분석을 재현하기 전에 다음 사항을 확인한다.

1. `results/phase7g_final_method_parameters.json`의 SHA-256이 `caad17257304d0ab198e01ef327f5acf918e6b8aab3f00e5272be3d20d3f8325`인지 확인한다.
2. Phase 6C 분할과 Phase 6K/6L 명세가 `reproducibility/FROZEN_ARTIFACT_SHA256.txt`와 일치하는지 확인한다.
3. TEST를 확인한 뒤에는 임계값, `alpha`, `lambda`, 후보군 크기, 그래프 beta, 경계 Top-R과 `Kmax`를 변경하지 않는다.
4. 평가 전용 정답은 채점 단계 이외에서 모델과 처리 과정이 접근할 수 없도록 분리한다.

## 5. Phase 9 서버

보존된 서버 구현은 다음과 같다.

- `server/phase9a_server.py`: 미리 계산한 점수로 동결된 재구성 수행
- `server/phase9d_evidence_server.py`: 식별자 중립 증거를 이용한 후보 검색과 재구성 수행
- `server/phase9e3_package_server.py`: 로컬에 구성한 패키지의 추출과 재구성 수행
- `server/phase9f_scalability_server.py`: 후보 프로젝트 수에 따른 확장성 평가

해당 서버의 정상 동작을 확인한 뒤 대응하는 Phase 9 성능 평가 스크립트를 실행한다. Phase 9C, 9D, 9E3는 처리 과정의 서로 다른 구간을 측정하므로, 지연 시간을 보고할 때 각 평가 범위를 구분해야 한다.

## 6. Phase 10 외부 도구

Open-NiCad/NiCadCross는 저장소에 포함하지 않는다. 별도로 설치한 뒤 Phase 10 대응표에 기록된 질의·후보 소스 데이터를 복원한다. 보관된 `phase10a4d_score_nicad_v1_buggy.py`에는 오류가 있으므로 보고 결과 재현에 사용할 수 없다. 수정된 `scripts/phase10a4d_score_nicad.py`를 사용한다.

## 7. Phase 11 생성 어댑터

`scripts/phase11b_run_multi_unknown_robustness.py`는 Phase 7B의 기증자 증거를 그대로 재사용하고 `scripts/_phase11b_phase7h_adapter_generated.py`에 임시 어댑터를 생성한다. 추적 중인 실행 파일이 항상 같은 방식으로 다시 만들 수 있으므로 현재 생성본은 Git 관리 대상에서 제외한다. 보존된 실행에 사용한 과거 어댑터는 감사를 위해 `archive/generated/`에 남겨 두었다.

## 8. Phase 12 근사 검색 및 확장성

다음 순서로 실행한다.

- `scripts/phase12a_ann_candidate_benchmark.py`
- `scripts/phase12b_ann_downstream_evaluation.py`
- `scripts/phase12c_online_retrieval_runtime.py`
- `scripts/phase12d_online_pool_downstream_evaluation.py`
- `scripts/phase12e_scalability_crossover.py`
- `scripts/phase12f_reporting_audit.py`

360개 질의 전체의 예측 일치도는 Phase 12C/12D에서 확인한다. Phase 12E는 항상 같은 방식으로 선택한 120개 질의의 실행 시간·확장성 표본이다.

`200eq`, `500eq`, `1000eq`는 실제 등록 부모 100개를 바탕으로 구성요소 수만 늘린 합성 부하 조건이며 고유 프로젝트 수가 아니다.

다음 파일로 동결 Phase 12 상태를 확인한다.

- `reproducibility/phase12_freeze_manifest.sha256`
- `results/phase12f_reporting_audit_summary.json`

## 9. Phase 13 실패 분석

다음 순서로 실행한다.

- `scripts/phase13a_failure_taxonomy.py`
- `scripts/phase13b_hierarchical_failure_localization.py`
- `scripts/phase13c_reporting_audit.py`

이 Phase는 기존의 동결 예측과 감사 자료를 읽는다. 진단 전용 단계이며 주요 예측을 다시 계산하거나 동결 방법을 재조정하지 않는다.

다음 파일로 동결 Phase 13 상태를 확인한다.

- `reproducibility/phase13_freeze_manifest.sha256`
- `results/phase13c_reporting_audit_summary.json`

## 10. 보존된 주요 결과 파일

- 1차 동결 TEST: `results/phase7h_final_test_summary.json`
- 통계 분석: `results/phase8a_bootstrap_summary.json`, `phase8b_baseline_ablation_summary.json`, `phase8c_source_cluster_sensitivity_summary.json`
- 시스템 평가: `results/phase9b_server_correctness_summary.json`부터 `phase9f_gallery_scalability_summary.json`
- 외부 기준선: `results/phase10a4f_nicad_paired_bootstrap_summary.json`
- 다중 UNKNOWN 강건성: `results/phase11c_multi_unknown_summary.json`
- 근사 검색·확장성: `results/phase12f_reporting_audit_summary.json`
- 실패 분석: `results/phase13a_failure_taxonomy_summary.json`, `phase13b_failure_localization_summary.json`, `phase13c_reporting_audit_summary.json`

다시 생성한 주요 수치가 다를 경우에는 해석을 중단하고 동결 입력 해시, 환경 버전과 관련 상세 감사표를 먼저 비교한다.

---

<a id="reproduce-ja"></a>

# 研究ワークフローの再現

[![English](https://img.shields.io/badge/EN-English-6E7781?style=for-the-badge)](#user-content-reproduce-en) [![한국어](https://img.shields.io/badge/KO-%ED%95%9C%EA%B5%AD%EC%96%B4-6E7781?style=for-the-badge)](#user-content-reproduce-ko) [![日本語](https://img.shields.io/badge/JA-%E6%97%A5%E6%9C%AC%E8%AA%9E-0969DA?style=for-the-badge)](#user-content-reproduce-ja)

[← 日本語のリポジトリ概要](README.md#user-content-readme-ja)

本リポジトリには、Phase 1からPhase 13までの研究手順を再現するために必要なコードとメタデータを保存している。第三者のMOD/JAR原本、複製した外部リポジトリ、生成済みクエリパッケージ、外部ツールは再配布しない。

## 1. 環境

システム性能評価に使用したPython環境は、`requirements.txt`と`results/phase9_environment_freeze.txt`に同一内容で固定している。

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

WSLの実行記録ではPython 3.12.3、OpenJDK 11.0.31、Git 2.43.0を使用している。Phase 9の性能測定はWindows Python 3.10.6で実施したため、正確な処理時間は実行コンピューターと環境によって変化する。性能値を比較する際は[環境記録](reproducibility/ENVIRONMENT.md#user-content-environment-ja)を併せて確認する必要がある。

## 2. Gitに含まれない入力資料の復元

原本アーカイブはGitに含めていない。追跡済みのプロジェクト・バージョン識別子、ダウンロードURL、内容ハッシュ、特定時点のコミット、対応表監査を用いて、各スクリプトが想定するパスへ資料を復元する。主な復元資料は次のとおりである。

- `results/phase6a_fresh_corpus.csv`
- `results/phase6c_project_split.csv`
- `results/phase10a3_repository_snapshot_audit.csv`
- `results/phase10a3_class_to_java_mapping.csv`
- `results/phase9e_package_manifest.csv`

後続段階を実行する前に、ダウンロードしたファイルのSHA-1/SHA-256/SHA-512を追跡済みの値と照合する。復元したアーカイブと抽出済み原本データはコミットしない。

## 3. 実行順序

多くのスクリプトは汎用のコマンドラインアプリケーションではなく、パスと手順を固定した研究用プログラムである。リポジトリルートから実行する。

```text
Phase 1  収集
Phase 2  データセット・リリースの凍結
Phase 3  旧ベースライン
Phase 4  グラフ抽出
Phase 5  合成手法の探索
Phase 6  新規ベンチマークと凍結済みクエリ・グラフ構築
Phase 7  較正 -> 手法凍結 -> 最終TEST
Phase 8  事後統計とアブレーション
Phase 9  サーバー正確性と性能
Phase 10 ソース・外部ベースライン互換性
Phase 11 凍結後の複数UNKNOWN頑健性
Phase 12 凍結後の厳密検索・LSH検索の性能とスケーラビリティ評価
Phase 13 凍結後の自動失敗分析
```

各Phaseのスクリプト、入力、出力、結果、凍結状況は[実験インデックス](reproducibility/EXPERIMENT_INDEX.md#user-content-experiment-ja)に記載している。

## 4. 評価前の凍結確認

Phase 7Hまたはそれ以降の分析を再現する前に、次の事項を確認する。

1. `results/phase7g_final_method_parameters.json`のSHA-256が`caad17257304d0ab198e01ef327f5acf918e6b8aab3f00e5272be3d20d3f8325`であること。
2. Phase 6Cの分割とPhase 6K/6Lのマニフェストが`reproducibility/FROZEN_ARTIFACT_SHA256.txt`と一致すること。
3. TESTを確認した後は、しきい値、`alpha`、`lambda`、候補群サイズ、グラフbeta、境界Top-R、`Kmax`を変更しないこと。
4. 評価専用の正解ラベルを、採点段階以外からモデルや処理系が参照できないよう分離すること。

## 5. Phase 9サーバー

保存済みのサーバー実装は次のとおりである。

- `server/phase9a_server.py`：事前計算済みスコアによる凍結済み再構成
- `server/phase9d_evidence_server.py`：識別子に依存しない証拠による候補検索と再構成
- `server/phase9e3_package_server.py`：ローカルに構成したパッケージの抽出と再構成
- `server/phase9f_scalability_server.py`：候補プロジェクト数に対するスケーラビリティ評価

対応するサーバーの正常動作を確認してから、該当するPhase 9性能評価スクリプトを実行する。Phase 9C、9D、9E3は処理系の異なる区間を測定するため、処理時間を報告する際は各評価範囲を区別する。

## 6. Phase 10外部ツール

Open-NiCad/NiCadCrossは同梱していない。別途導入したうえで、Phase 10対応表に記録されたクエリ・候補ソースデータを復元する。保存済みの`phase10a4d_score_nicad_v1_buggy.py`には不具合があり、報告結果の再現には使用できない。修正版の`scripts/phase10a4d_score_nicad.py`を使用する。

## 7. Phase 11生成アダプター

`scripts/phase11b_run_multi_unknown_robustness.py`は、Phase 7Bの提供元証拠をそのまま再利用し、`scripts/_phase11b_phase7h_adapter_generated.py`に一時アダプターを生成する。追跡済みの実行ファイルが常に同じ手順で再生成できるため、現在の生成物はGit管理対象外である。保存済み実行で使用した過去のアダプターは、監査用として`archive/generated/`に残している。

## 8. Phase 12近似検索とスケーラビリティ

次の順序で実行する。

- `scripts/phase12a_ann_candidate_benchmark.py`
- `scripts/phase12b_ann_downstream_evaluation.py`
- `scripts/phase12c_online_retrieval_runtime.py`
- `scripts/phase12d_online_pool_downstream_evaluation.py`
- `scripts/phase12e_scalability_crossover.py`
- `scripts/phase12f_reporting_audit.py`

360クエリ全体の予測一致度はPhase 12C/12Dで確認する。Phase 12Eは、常に同じ手順で選択した120クエリの処理時間・スケーラビリティ標本である。

`200eq`、`500eq`、`1000eq`は、100件の実在する登録済み親を基にコンポーネント数のみを増やした合成負荷条件であり、固有プロジェクト数ではない。

次のファイルで凍結済みPhase 12の状態を確認する。

- `reproducibility/phase12_freeze_manifest.sha256`
- `results/phase12f_reporting_audit_summary.json`

## 9. Phase 13失敗分析

次の順序で実行する。

- `scripts/phase13a_failure_taxonomy.py`
- `scripts/phase13b_hierarchical_failure_localization.py`
- `scripts/phase13c_reporting_audit.py`

このPhaseは既存の凍結済み予測と監査資料を読み込む。診断専用の段階であり、主要予測の再計算や凍結済み手法の再調整は行わない。

次のファイルで凍結済みPhase 13の状態を確認する。

- `reproducibility/phase13_freeze_manifest.sha256`
- `results/phase13c_reporting_audit_summary.json`

## 10. 保存済みの主要結果ファイル

- 主要凍結TEST：`results/phase7h_final_test_summary.json`
- 統計分析：`results/phase8a_bootstrap_summary.json`、`phase8b_baseline_ablation_summary.json`、`phase8c_source_cluster_sensitivity_summary.json`
- システム評価：`results/phase9b_server_correctness_summary.json`から`phase9f_gallery_scalability_summary.json`
- 外部ベースライン：`results/phase10a4f_nicad_paired_bootstrap_summary.json`
- 複数UNKNOWN頑健性：`results/phase11c_multi_unknown_summary.json`
- 近似検索・スケーラビリティ：`results/phase12f_reporting_audit_summary.json`
- 失敗分析：`results/phase13a_failure_taxonomy_summary.json`、`phase13b_failure_localization_summary.json`、`phase13c_reporting_audit_summary.json`

再生成した主要指標が異なる場合は解釈を中断し、凍結済み入力ハッシュ、環境のバージョン、関連する詳細監査表を比較する。
