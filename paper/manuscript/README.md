<a id="manuscript-en"></a>

# Current Manuscript

[![English](https://img.shields.io/badge/EN-English-0969DA?style=for-the-badge)](#user-content-manuscript-en) [![한국어](https://img.shields.io/badge/KO-%ED%95%9C%EA%B5%AD%EC%96%B4-6E7781?style=for-the-badge)](#user-content-manuscript-ko) [![日本語](https://img.shields.io/badge/JA-%E6%97%A5%E6%9C%AC%E8%AA%9E-6E7781?style=for-the-badge)](#user-content-manuscript-ja)

[← Repository overview](../../README.md#user-content-readme-en)

This directory preserves the current anonymous 17-page manuscript:

> **Server-Side Multi-Parent Provenance Reconstruction for Copyright-Related Source Attribution in Heterogeneous Game MOD Packages**

| Version | LaTeX source | Compiled PDF |
|---|---|---|
| English | [`main_en.tex`](main_en.tex) | [`main_en.pdf`](main_en.pdf) |
| Korean review version | [`main_ko.tex`](main_ko.tex) | [`main_ko.pdf`](main_ko.pdf) |

Both versions use the same section structure, frozen Phase 7 method, experimental records, tables, and figure placement. The copyright-related framing treats system outputs as technical provenance evidence for expert source review; it does not claim automated legal determinations of authorship, ownership, permission, copying, or infringement.

## Build

Run the following sequence from this directory for either `main_en` or `main_ko`:

```text
pdflatex main_en.tex
bibtex main_en
pdflatex main_en.tex
pdflatex main_en.tex
```

The manuscript uses the included `llncs.cls`, `splncs04_unsrt.bst`, `references.bib`, and language-matched files under `figures/`.

---

<a id="manuscript-ko"></a>

# 현재 논문 원고

[![English](https://img.shields.io/badge/EN-English-6E7781?style=for-the-badge)](#user-content-manuscript-en) [![한국어](https://img.shields.io/badge/KO-%ED%95%9C%EA%B5%AD%EC%96%B4-0969DA?style=for-the-badge)](#user-content-manuscript-ko) [![日本語](https://img.shields.io/badge/JA-%E6%97%A5%E6%9C%AC%E8%AA%9E-6E7781?style=for-the-badge)](#user-content-manuscript-ja)

[← 한국어 저장소 소개](../../README.md#user-content-readme-ko)

이 디렉터리에는 현재 익명 17쪽 논문 원고가 보존되어 있다.

> **이종 게임 MOD 패키지의 저작권 출처 판별을 위한 서버 기반 다중 출처 Provenance 복원 기법**

영문판과 한글 검토판은 같은 장 구조, 동결된 Phase 7 방법, 실험 기록, 표와 그림 배치를 사용한다. 저작권기술 framing은 시스템 출력을 전문가의 출처 검토를 보조하는 기술적 provenance 증거로 한정하며, 저작권자·소유권·허락·복제·침해 여부를 자동 판정한다고 주장하지 않는다. 빌드 방법과 파일 연결은 위 영문 안내를 따른다.

---

<a id="manuscript-ja"></a>

# 現行の論文原稿

[![English](https://img.shields.io/badge/EN-English-6E7781?style=for-the-badge)](#user-content-manuscript-en) [![한국어](https://img.shields.io/badge/KO-%ED%95%9C%EA%B5%AD%EC%96%B4-6E7781?style=for-the-badge)](#user-content-manuscript-ko) [![日本語](https://img.shields.io/badge/JA-%E6%97%A5%E6%9C%AC%E8%AA%9E-0969DA?style=for-the-badge)](#user-content-manuscript-ja)

[← 日本語のリポジトリ概要](../../README.md#user-content-readme-ja)

このディレクトリには、現行の匿名17ページ論文原稿を保存している。英語版と韓国語確認版は、同一の章構成、凍結済みPhase 7手法、実験記録、表、図の配置を用いる。著作権関連の位置付けは、出力を専門家の由来確認を支援する技術的プロベナンス証拠に限定し、著作者、所有権、許諾、複製、侵害の法的判断を自動化するとは主張しない。
