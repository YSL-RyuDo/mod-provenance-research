<a id="archive-en"></a>

# Archived Research Artifacts

[![English](https://img.shields.io/badge/EN-English-0969DA?style=for-the-badge)](#user-content-archive-en) [![한국어](https://img.shields.io/badge/KO-%ED%95%9C%EA%B5%AD%EC%96%B4-6E7781?style=for-the-badge)](#user-content-archive-ko) [![日本語](https://img.shields.io/badge/JA-%E6%97%A5%E6%9C%AC%E8%AA%9E-6E7781?style=for-the-badge)](#user-content-archive-ja)

[← Repository overview](../README.md#user-content-readme-en)

This directory preserves generated or invalid historical implementations that are useful for auditability but are not current executable sources of truth.

## `generated/`

`_phase11b_phase7h_adapter_generated.py` was produced deterministically by `scripts/phase11b_run_multi_unknown_robustness.py` from the frozen Phase 7H implementation. It is retained as the exact historical adapter used for the recorded Phase 11 run. Future runs regenerate the active `scripts/_phase11b_phase7h_adapter_generated.py`, which is ignored.

## `failed_experiments/`

`phase10a4d_score_nicad_v1_buggy.py` is the superseded first NiCad scoring implementation. It used the internal source identity rather than the frozen benchmark `ground_truth_label` for held-out components and calculated K without the collapsed `UNKNOWN` group. It must not be used to reproduce reported Phase 10 results. The corrected implementation remains `scripts/phase10a4d_score_nicad.py`.

---

<a id="archive-ko"></a>

# 보관된 연구 산출물

[![English](https://img.shields.io/badge/EN-English-6E7781?style=for-the-badge)](#user-content-archive-en) [![한국어](https://img.shields.io/badge/KO-%ED%95%9C%EA%B5%AD%EC%96%B4-0969DA?style=for-the-badge)](#user-content-archive-ko) [![日本語](https://img.shields.io/badge/JA-%E6%97%A5%E6%9C%AC%E8%AA%9E-6E7781?style=for-the-badge)](#user-content-archive-ja)

[← 한국어 저장소 소개](../README.md#user-content-readme-ko)

이 directory는 감사 가능성에 유용하지만 현재 실행 가능한 source of truth가 아닌 생성물 또는 유효하지 않은 과거 구현을 보존합니다.

## `generated/`

`_phase11b_phase7h_adapter_generated.py`는 동결 Phase 7H 구현에서 `scripts/phase11b_run_multi_unknown_robustness.py`가 결정론적으로 생성했습니다. 기록된 Phase 11 실행에 사용한 정확한 과거 adapter로 보존합니다. 향후 실행은 무시되는 활성 파일 `scripts/_phase11b_phase7h_adapter_generated.py`를 다시 생성합니다.

## `failed_experiments/`

`phase10a4d_score_nicad_v1_buggy.py`는 대체된 최초 NiCad scoring 구현입니다. Held-out 구성요소에 동결 benchmark의 `ground_truth_label` 대신 internal source identity를 사용했고, collapsed `UNKNOWN` group을 제외한 채 K를 계산했습니다. 보고된 Phase 10 결과 재현에 사용하면 안 됩니다. 수정된 구현은 `scripts/phase10a4d_score_nicad.py`입니다.

---

<a id="archive-ja"></a>

# 保存済み研究成果物

[![English](https://img.shields.io/badge/EN-English-6E7781?style=for-the-badge)](#user-content-archive-en) [![한국어](https://img.shields.io/badge/KO-%ED%95%9C%EA%B5%AD%EC%96%B4-6E7781?style=for-the-badge)](#user-content-archive-ko) [![日本語](https://img.shields.io/badge/JA-%E6%97%A5%E6%9C%AC%E8%AA%9E-0969DA?style=for-the-badge)](#user-content-archive-ja)

[← 日本語のリポジトリ概要](../README.md#user-content-readme-ja)

このdirectoryは、監査可能性には有用ですが現在の実行可能なsource of truthではない、生成済みまたは無効な過去実装を保存します。

## `generated/`

`_phase11b_phase7h_adapter_generated.py`は、凍結Phase 7H実装から`scripts/phase11b_run_multi_unknown_robustness.py`によって決定論的に生成されました。記録済みPhase 11 runで使用した正確な過去adapterとして保存します。今後のrunでは、無視対象のactiveファイル`scripts/_phase11b_phase7h_adapter_generated.py`を再生成します。

## `failed_experiments/`

`phase10a4d_score_nicad_v1_buggy.py`は、置き換えられた最初のNiCad scoring実装です。Held-out componentに凍結benchmarkの`ground_truth_label`ではなくinternal source identityを使用し、collapsed `UNKNOWN` groupを除外してKを計算していました。報告済みPhase 10結果の再現に使用してはいけません。修正済み実装は`scripts/phase10a4d_score_nicad.py`です。
