<a id="archive-en"></a>

# Archived Research Artifacts

[![English](https://img.shields.io/badge/EN-English-0969DA?style=for-the-badge)](#user-content-archive-en) [![한국어](https://img.shields.io/badge/KO-%ED%95%9C%EA%B5%AD%EC%96%B4-6E7781?style=for-the-badge)](#user-content-archive-ko) [![日本語](https://img.shields.io/badge/JA-%E6%97%A5%E6%9C%AC%E8%AA%9E-6E7781?style=for-the-badge)](#user-content-archive-ja)

[← Repository overview](../README.md#user-content-readme-en)

This directory preserves generated or invalid historical implementations that are useful for auditability but are not current executable sources of truth.

## `generated/`

`_phase11b_phase7h_adapter_generated.py` was produced deterministically by `scripts/phase11b_run_multi_unknown_robustness.py` from the frozen Phase 7H implementation. It is retained as the exact historical adapter used for the recorded Phase 11 run. Future runs regenerate the active `scripts/_phase11b_phase7h_adapter_generated.py`, which is ignored.

## `failed_experiments/`

`phase10a4d_score_nicad_v1_buggy.py` is the superseded first NiCad scoring implementation. It used the internal source identity rather than the frozen benchmark `ground_truth_label` for held-out components and calculated K without the collapsed `UNKNOWN` group. It must not be used to reproduce reported Phase 10 results. The corrected implementation remains `scripts/phase10a4d_score_nicad.py`.

## `manuscript_v3/`

This directory preserves the superseded Korean v3 draft and its compiled PDF for manuscript history. It is not the current paper. The copyright-related English and Korean manuscript sources and 17-page PDFs are under [`paper/manuscript/`](../paper/manuscript/).

---

<a id="archive-ko"></a>

# 보관된 연구 산출물

[![English](https://img.shields.io/badge/EN-English-6E7781?style=for-the-badge)](#user-content-archive-en) [![한국어](https://img.shields.io/badge/KO-%ED%95%9C%EA%B5%AD%EC%96%B4-0969DA?style=for-the-badge)](#user-content-archive-ko) [![日本語](https://img.shields.io/badge/JA-%E6%97%A5%E6%9C%AC%E8%AA%9E-6E7781?style=for-the-badge)](#user-content-archive-ja)

[← 한국어 저장소 소개](../README.md#user-content-readme-ko)

이 디렉터리는 연구 이력을 검증하는 데 필요한 생성 파일과 폐기된 과거 구현을 보존한다. 현재 결과를 재현할 때 사용하는 실행 기준 파일은 아니다.

## `generated/`

`_phase11b_phase7h_adapter_generated.py`는 `scripts/phase11b_run_multi_unknown_robustness.py`가 동결된 Phase 7H 구현을 바탕으로 항상 같은 방식으로 생성한 파일이다. 기록된 Phase 11 실행에 사용한 버전을 남겨 두었으며, 이후 실행에서는 Git 관리 대상이 아닌 `scripts/_phase11b_phase7h_adapter_generated.py`를 다시 생성한다.

## `failed_experiments/`

`phase10a4d_score_nicad_v1_buggy.py`는 오류가 확인되어 교체된 초기 NiCad 채점 구현이다. 평가용으로 분리한 구성요소에 동결 벤치마크의 `ground_truth_label` 대신 내부 소스 식별자를 사용했고, 단일 `UNKNOWN` 집단을 제외한 채 K를 계산했다. 보고된 Phase 10 결과에는 사용할 수 없으며, 수정된 구현은 `scripts/phase10a4d_score_nicad.py`이다.

## `manuscript_v3/`

교체된 한글 v3 원고와 컴파일 PDF를 논문 변경 이력 확인용으로 보존한다. 이 파일은 현재 원고가 아니다. 저작권 관련 출처 판별 관점으로 개편한 최신 한·영 원고와 17쪽 PDF는 [`paper/manuscript/`](../paper/manuscript/)에 있다.

---

<a id="archive-ja"></a>

# 保存済み研究成果物

[![English](https://img.shields.io/badge/EN-English-6E7781?style=for-the-badge)](#user-content-archive-en) [![한국어](https://img.shields.io/badge/KO-%ED%95%9C%EA%B5%AD%EC%96%B4-6E7781?style=for-the-badge)](#user-content-archive-ko) [![日本語](https://img.shields.io/badge/JA-%E6%97%A5%E6%9C%AC%E8%AA%9E-0969DA?style=for-the-badge)](#user-content-archive-ja)

[← 日本語のリポジトリ概要](../README.md#user-content-readme-ja)

このディレクトリには、研究履歴の検証に必要な生成ファイルと、廃止された過去の実装を保存している。現在の結果を再現する際に使用する基準実装ではない。

## `generated/`

`_phase11b_phase7h_adapter_generated.py`は、`scripts/phase11b_run_multi_unknown_robustness.py`が凍結済みPhase 7H実装を基に常に同じ手順で生成したファイルである。記録済みPhase 11実行で使用した版を保存しており、今後の実行ではGit管理対象外の`scripts/_phase11b_phase7h_adapter_generated.py`を再生成する。

## `failed_experiments/`

`phase10a4d_score_nicad_v1_buggy.py`は、不具合が確認されて置き換えられた初期のNiCad採点実装である。評価用に分離したコンポーネントに、凍結ベンチマークの`ground_truth_label`ではなく内部ソース識別子を使用し、単一の`UNKNOWN`グループを除外してKを計算していた。報告済みPhase 10結果には使用できない。修正済み実装は`scripts/phase10a4d_score_nicad.py`である。

## `manuscript_v3/`

置き換え済みの韓国語v3原稿とコンパイル済みPDFを、論文の変更履歴を確認するために保存している。これは現行原稿ではない。著作権関連の由来判定として再構成した最新の英語・韓国語原稿と17ページPDFは、[`paper/manuscript/`](../paper/manuscript/)にある。
