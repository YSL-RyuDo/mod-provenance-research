<a id="contributing-en"></a>

# Contributing

[![English](https://img.shields.io/badge/EN-English-0969DA?style=for-the-badge)](#user-content-contributing-en) [![한국어](https://img.shields.io/badge/KO-%ED%95%9C%EA%B5%AD%EC%96%B4-6E7781?style=for-the-badge)](#user-content-contributing-ko) [![日本語](https://img.shields.io/badge/JA-%E6%97%A5%E6%9C%AC%E8%AA%9E-6E7781?style=for-the-badge)](#user-content-contributing-ja)

[← Repository overview](README.md#user-content-readme-en)

Contributions should preserve the research record, reproducibility boundaries, and third-party redistribution constraints documented in this repository.

## Before changing anything

1. Read the [repository overview](README.md#user-content-readme-en), [reproduction guide](REPRODUCE.md#user-content-reproduce-en), and [Experiment Index](reproducibility/EXPERIMENT_INDEX.md#user-content-experiment-en).
2. Check the [Tracking Audit](reproducibility/TRACKING_AUDIT.md#user-content-tracking-en) before adding data or generated outputs.
3. Work on a focused branch and keep unrelated local files out of the commit.

## Protected research artifacts

Do not modify Phase 6 splits/manifests, Phase 7 frozen parameters or primary TEST predictions, or the Phase 12/13 freeze manifests as part of routine cleanup or documentation work. A scientifically justified successor method must be recorded as a new phase or explicitly versioned protocol; it must not silently replace frozen evidence.

Never commit raw MOD/JAR archives, third-party source/tool caches, reconstructed external-tool corpora, credentials, private tokens, virtual environments, compiled output, or high-volume regenerable files.

## Pull-request checklist

- Explain the research or documentation purpose of the change.
- List the scripts, inputs, outputs, and summaries affected.
- State whether any frozen artifact changes; if yes, explain why and provide new hashes without overwriting historical records.
- Confirm that reported metrics were copied from tracked summaries and retain their original scope.
- Confirm that no secret, redistribution-sensitive payload, or held-out mapping was added unintentionally.
- Run the relevant script checks and verify all relative Markdown links.

## Reporting issues

Use GitHub Issues for reproducibility problems, documentation gaps, and narrowly scoped research questions. Do not attach third-party payloads or evaluation-private labels to a public report.

---

<a id="contributing-ko"></a>

# 기여 안내

[![English](https://img.shields.io/badge/EN-English-6E7781?style=for-the-badge)](#user-content-contributing-en) [![한국어](https://img.shields.io/badge/KO-%ED%95%9C%EA%B5%AD%EC%96%B4-0969DA?style=for-the-badge)](#user-content-contributing-ko) [![日本語](https://img.shields.io/badge/JA-%E6%97%A5%E6%9C%AC%E8%AA%9E-6E7781?style=for-the-badge)](#user-content-contributing-ja)

[← 한국어 저장소 소개](README.md#user-content-readme-ko)

기여 내용은 이 저장소에 문서화된 연구 기록, 재현성 경계 및 제3자 재배포 제약을 보존해야 합니다.

## 변경 전 확인

1. [한국어 저장소 소개](README.md#user-content-readme-ko), [재현 안내](REPRODUCE.md#user-content-reproduce-ko), [실험 인덱스](reproducibility/EXPERIMENT_INDEX.md#user-content-experiment-ko)를 읽으세요.
2. Data나 생성 output을 추가하기 전에 [추적 감사](reproducibility/TRACKING_AUDIT.md#user-content-tracking-ko)를 확인하세요.
3. 범위가 명확한 branch에서 작업하고 관련 없는 local 파일은 commit에서 제외하세요.

## 보호되는 연구 산출물

일상적인 정리나 문서 작업의 일부로 Phase 6 split/manifest, Phase 7 동결 parameter나 1차 TEST prediction 또는 Phase 12/13 freeze manifest를 변경하지 마세요. 과학적으로 정당한 후속 방법은 새 Phase 또는 명시적으로 version을 부여한 protocol로 기록해야 하며, 동결 evidence를 조용히 대체하면 안 됩니다.

원본 MOD/JAR archive, 제3자 source/tool cache, 외부 도구용 복원 corpus, credential, private token, 가상환경, compiled output 또는 대용량 재생성 가능 파일을 절대 commit하지 마세요.

## Pull request 점검표

- 변경의 연구 또는 문서 목적을 설명합니다.
- 영향받는 script, input, output 및 summary를 나열합니다.
- 동결 artifact가 변경되는지 밝힙니다. 변경된다면 이유를 설명하고 과거 기록을 덮어쓰지 않은 새 hash를 제공합니다.
- 보고한 metric이 추적되는 summary에서 복사되었고 원래 범위를 유지하는지 확인합니다.
- Secret, 재배포 민감 payload 또는 held-out mapping을 실수로 추가하지 않았는지 확인합니다.
- 관련 script 점검을 실행하고 모든 상대 Markdown link를 확인합니다.

## Issue 보고

재현 문제, 문서 누락 및 범위가 좁은 연구 질문에는 GitHub Issues를 사용하세요. 공개 보고서에 제3자 payload 또는 평가 전용 label을 첨부하지 마세요.

---

<a id="contributing-ja"></a>

# コントリビューションガイド

[![English](https://img.shields.io/badge/EN-English-6E7781?style=for-the-badge)](#user-content-contributing-en) [![한국어](https://img.shields.io/badge/KO-%ED%95%9C%EA%B5%AD%EC%96%B4-6E7781?style=for-the-badge)](#user-content-contributing-ko) [![日本語](https://img.shields.io/badge/JA-%E6%97%A5%E6%9C%AC%E8%AA%9E-0969DA?style=for-the-badge)](#user-content-contributing-ja)

[← 日本語のリポジトリ概要](README.md#user-content-readme-ja)

コントリビューションでは、本リポジトリに記録された研究記録、再現性の境界、第三者再配布の制約を維持する必要があります。

## 変更前の確認

1. [日本語のリポジトリ概要](README.md#user-content-readme-ja)、[再現ガイド](REPRODUCE.md#user-content-reproduce-ja)、[実験インデックス](reproducibility/EXPERIMENT_INDEX.md#user-content-experiment-ja)を読んでください。
2. Dataや生成outputを追加する前に[追跡監査](reproducibility/TRACKING_AUDIT.md#user-content-tracking-ja)を確認してください。
3. 対象を絞ったbranchで作業し、無関係なlocalファイルをcommitに含めないでください。

## 保護対象の研究成果物

通常の整理や文書作業の一部として、Phase 6 split/manifest、Phase 7凍結parameterや主要TEST prediction、Phase 12/13 freeze manifestを変更しないでください。科学的に正当な後継手法は、新しいPhaseまたは明示的にversionを付けたprotocolとして記録し、凍結evidenceを黙って置き換えてはいけません。

生のMOD/JAR archive、第三者source/tool cache、外部tool用の再構成corpus、credential、private token、仮想環境、compiled output、大容量で再生成可能なファイルを決してcommitしないでください。

## Pull requestチェックリスト

- 変更の研究上または文書上の目的を説明します。
- 影響を受けるscript、input、output、summaryを列挙します。
- 凍結artifactが変更されるかを明記します。変更する場合は理由を説明し、過去記録を上書きせずに新しいhashを提示します。
- 報告metricが追跡済みsummaryから転記され、元の範囲を維持していることを確認します。
- Secret、再配布に配慮が必要なpayload、held-out mappingを誤って追加していないことを確認します。
- 関連scriptのcheckを実行し、すべての相対Markdown linkを確認します。

## Issueの報告

再現上の問題、文書の不足、範囲を絞った研究質問にはGitHub Issuesを使用してください。公開報告に第三者payloadや評価専用labelを添付しないでください。
