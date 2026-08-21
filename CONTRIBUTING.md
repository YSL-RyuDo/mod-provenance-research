<a id="contributing-en"></a>

# Contributing

[![English](https://img.shields.io/badge/EN-English-0969DA?style=for-the-badge)](#user-content-contributing-en) [![한국어](https://img.shields.io/badge/KO-%ED%95%9C%EA%B5%AD%EC%96%B4-6E7781?style=for-the-badge)](#user-content-contributing-ko) [![日本語](https://img.shields.io/badge/JA-%E6%97%A5%E6%9C%AC%E8%AA%9E-6E7781?style=for-the-badge)](#user-content-contributing-ja)

Contributions should preserve the research record, reproducibility boundaries, and third-party redistribution constraints documented in this repository.

## Before changing anything

1. Read the [reproduction guide](REPRODUCE.md#user-content-reproduce-en) and [Experiment Index](reproducibility/EXPERIMENT_INDEX.md#user-content-experiment-en).
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

기여 시에는 이 저장소에 기록된 연구 이력, 재현 조건과 제3자 자료의 재배포 제한을 유지해야 한다.

## 변경 전 확인

1. [재현 안내](REPRODUCE.md#user-content-reproduce-ko)와 [실험 인덱스](reproducibility/EXPERIMENT_INDEX.md#user-content-experiment-ko)를 확인한다.
2. 데이터나 생성 결과를 추가하기 전에 [추적 감사](reproducibility/TRACKING_AUDIT.md#user-content-tracking-ko)를 확인한다.
3. 범위가 명확한 브랜치에서 작업하고 관련 없는 로컬 파일은 커밋에서 제외한다.

## 보호되는 연구 산출물

일반적인 정리나 문서 작업으로 Phase 6의 분할·명세, Phase 7의 동결 매개변수·주요 TEST 예측, Phase 12/13의 동결 명세를 변경해서는 안 된다. 과학적 근거가 있는 후속 방법은 새 Phase 또는 명시적으로 버전을 부여한 절차로 기록하며, 기존의 동결 자료를 덮어쓰지 않는다.

원본 MOD/JAR 압축파일, 제3자 소스·도구 캐시, 외부 도구용 복원 데이터, 인증정보, 비공개 토큰, 가상환경, 컴파일 결과와 대용량 재생성 파일은 커밋하지 않는다.

## Pull request 점검표

- 변경의 연구 목적 또는 문서화 목적을 설명한다.
- 영향을 받는 스크립트, 입력, 출력과 요약 파일을 나열한다.
- 동결 자료의 변경 여부를 밝힌다. 변경되는 경우에는 이유와 새 해시를 기록하고 과거 기록을 덮어쓰지 않는다.
- 보고 수치가 추적 중인 공식 요약에서 옮겨졌으며 원래의 평가 범위를 유지하는지 확인한다.
- 인증정보, 재배포 제한 자료 또는 평가 전용 대응표가 실수로 포함되지 않았는지 확인한다.
- 관련 검사를 실행하고 Markdown 상대 경로가 모두 유효한지 확인한다.

## Issue 보고

재현 문제, 문서 누락과 범위가 명확한 연구 질문은 GitHub Issues로 접수한다. 공개 보고에는 제3자 원본 데이터나 평가 전용 정답을 첨부하지 않는다.

---

<a id="contributing-ja"></a>

# コントリビューションガイド

[![English](https://img.shields.io/badge/EN-English-6E7781?style=for-the-badge)](#user-content-contributing-en) [![한국어](https://img.shields.io/badge/KO-%ED%95%9C%EA%B5%AD%EC%96%B4-6E7781?style=for-the-badge)](#user-content-contributing-ko) [![日本語](https://img.shields.io/badge/JA-%E6%97%A5%E6%9C%AC%E8%AA%9E-0969DA?style=for-the-badge)](#user-content-contributing-ja)

コントリビューションでは、本リポジトリに記録された研究履歴、再現条件、第三者資料の再配布制限を維持する。

## 変更前の確認

1. [再現ガイド](REPRODUCE.md#user-content-reproduce-ja)と[実験インデックス](reproducibility/EXPERIMENT_INDEX.md#user-content-experiment-ja)を確認する。
2. データや生成結果を追加する前に[追跡監査](reproducibility/TRACKING_AUDIT.md#user-content-tracking-ja)を確認する。
3. 対象を明確にしたブランチで作業し、無関係なローカルファイルをコミットに含めない。

## 保護対象の研究成果物

通常の整理や文書作業によって、Phase 6のデータ分割・マニフェスト、Phase 7の凍結パラメータ・主要TEST予測、Phase 12/13の凍結マニフェストを変更してはならない。科学的根拠のある後継手法は、新しいPhaseまたは明示的に版を付けた手順として記録し、既存の凍結資料を上書きしない。

生のMOD/JARアーカイブ、第三者のソース・ツールキャッシュ、外部ツール用に復元したデータ、認証情報、非公開トークン、仮想環境、コンパイル結果、大容量の再生成可能ファイルはコミットしない。

## Pull requestチェックリスト

- 変更の研究上または文書上の目的を説明する。
- 影響を受けるスクリプト、入力、出力、要約ファイルを列挙する。
- 凍結資料の変更有無を明記する。変更する場合は理由と新しいハッシュを記録し、過去の記録を上書きしない。
- 報告値が追跡中の正式な要約から転記され、元の評価範囲を維持していることを確認する。
- 認証情報、再配布制限のある資料、評価専用対応表が誤って含まれていないことを確認する。
- 関連する検査を実行し、Markdownの相対パスがすべて有効であることを確認する。

## Issueの報告

再現上の問題、文書の不足、対象が明確な研究上の質問はGitHub Issuesで受け付ける。公開報告には第三者の原本データや評価専用の正解ラベルを添付しない。
