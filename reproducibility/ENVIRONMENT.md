<a id="environment-en"></a>

# Reproducibility Environment

[![English](https://img.shields.io/badge/EN-English-0969DA?style=for-the-badge)](#user-content-environment-en) [![한국어](https://img.shields.io/badge/KO-%ED%95%9C%EA%B5%AD%EC%96%B4-6E7781?style=for-the-badge)](#user-content-environment-ko) [![日本語](https://img.shields.io/badge/JA-%E6%97%A5%E6%9C%AC%E8%AA%9E-6E7781?style=for-the-badge)](#user-content-environment-ja)

[← Reproduction guide](../REPRODUCE.md#user-content-reproduce-en)

Two environment snapshots exist because the research was run across WSL and Windows system-benchmark contexts. They must not be treated as one simultaneous environment.

## WSL/toolchain record

- OS/kernel: WSL2 Linux `6.6.87.2-microsoft-standard-WSL2`
- Python: 3.12.3
- Java: OpenJDK 11.0.31
- Git: 2.43.0

The exact captured strings are retained in `system.txt`, `python_version.txt`, `java_version.txt`, and `git_version.txt` in this directory.

`requirements_freeze.txt` is a compact later Python snapshot containing NumPy 2.5.2 and pandas 3.0.5. It is preserved as an environment record, but it is not claimed to be the full Phase 9 server environment.

## Phase 9 tested environment

Phase 9 performance summaries record:

- Windows Python 3.10.6
- Intel CPU, 20 physical / 28 logical cores
- 34,031,173,632 bytes total system memory

The full package freeze used for those server/system stages is `results/phase9_environment_freeze.txt`. Root `requirements.txt` mirrors that tested full environment for convenience. It includes NumPy 2.2.6, pandas 2.3.2, FastAPI 0.141.1, Uvicorn 0.52.1, SciPy 1.15.3, scikit-learn 1.7.2, Pillow 11.3.0, ImageHash 4.3.2, and the complete transitive environment.

Exact timing reproduction still depends on operating system, CPU, filesystem/cache state, and server process configuration. Treat performance summaries as results from the recorded host rather than universal constants.

## External tools

- Phase 3D requires Java to compile/run `tools/phase3d/JavapBatch.java`.
- Phase 10 uses a separate Open-NiCad/NiCadCross 7.0 installation configured for Java functions with the default/blindrename threshold 0.30.
- Git and network access are required only for restoring public repository snapshots/downloads; those caches are intentionally excluded.

## Recommended isolation

Use separate virtual environments for historical exact-server reproduction and any modern rerun. Do not silently upgrade the pinned Phase 9 environment and compare the resulting timing as though the environments were identical.

---

<a id="environment-ko"></a>

# 재현 환경

[![English](https://img.shields.io/badge/EN-English-6E7781?style=for-the-badge)](#user-content-environment-en) [![한국어](https://img.shields.io/badge/KO-%ED%95%9C%EA%B5%AD%EC%96%B4-0969DA?style=for-the-badge)](#user-content-environment-ko) [![日本語](https://img.shields.io/badge/JA-%E6%97%A5%E6%9C%AC%E8%AA%9E-6E7781?style=for-the-badge)](#user-content-environment-ja)

[← 재현 안내](../REPRODUCE.md#user-content-reproduce-ko)

연구가 WSL과 Windows system-benchmark 환경에서 진행되었으므로 두 개의 환경 snapshot이 존재합니다. 이를 하나의 동시 환경으로 취급하면 안 됩니다.

## WSL/toolchain 기록

- OS/kernel: WSL2 Linux `6.6.87.2-microsoft-standard-WSL2`
- Python: 3.12.3
- Java: OpenJDK 11.0.31
- Git: 2.43.0

정확히 capture한 문자열은 이 directory의 `system.txt`, `python_version.txt`, `java_version.txt`, `git_version.txt`에 보존되어 있습니다.

`requirements_freeze.txt`는 NumPy 2.5.2와 pandas 3.0.5를 포함한 간결한 후속 Python snapshot입니다. 환경 기록으로 보존하지만 완전한 Phase 9 server 환경이라고 주장하지 않습니다.

## 시험한 Phase 9 환경

Phase 9 성능 summary에는 다음이 기록되어 있습니다.

- Windows Python 3.10.6
- Intel CPU, physical core 20개 / logical core 28개
- 전체 system memory 34,031,173,632 bytes

해당 server/system 단계에서 사용한 전체 package freeze는 `results/phase9_environment_freeze.txt`입니다. 편의를 위해 루트의 `requirements.txt`가 시험한 전체 환경을 그대로 반영합니다. NumPy 2.2.6, pandas 2.3.2, FastAPI 0.141.1, Uvicorn 0.52.1, SciPy 1.15.3, scikit-learn 1.7.2, Pillow 11.3.0, ImageHash 4.3.2 및 전체 transitive 환경이 포함됩니다.

정확한 timing 재현은 여전히 운영체제, CPU, filesystem/cache 상태 및 server process 설정에 의존합니다. 성능 summary는 보편적 상수가 아니라 기록된 host의 결과로 취급하세요.

## 외부 도구

- Phase 3D에는 `tools/phase3d/JavapBatch.java`를 compile/run하기 위한 Java가 필요합니다.
- Phase 10은 Java function용으로 설정하고 default/blindrename threshold 0.30을 적용한 별도 Open-NiCad/NiCadCross 7.0 설치를 사용합니다.
- 공개 저장소 snapshot/download를 복원할 때만 Git과 network 접근이 필요하며, 해당 cache는 의도적으로 제외됩니다.

## 권장 격리

과거 exact-server 재현과 최신 재실행에는 서로 다른 가상환경을 사용하세요. 고정된 Phase 9 환경을 조용히 upgrade한 뒤 동일한 환경인 것처럼 timing을 비교하면 안 됩니다.

---

<a id="environment-ja"></a>

# 再現環境

[![English](https://img.shields.io/badge/EN-English-6E7781?style=for-the-badge)](#user-content-environment-en) [![한국어](https://img.shields.io/badge/KO-%ED%95%9C%EA%B5%AD%EC%96%B4-6E7781?style=for-the-badge)](#user-content-environment-ko) [![日本語](https://img.shields.io/badge/JA-%E6%97%A5%E6%9C%AC%E8%AA%9E-0969DA?style=for-the-badge)](#user-content-environment-ja)

[← 再現ガイド](../REPRODUCE.md#user-content-reproduce-ja)

研究はWSLとWindows system-benchmark環境にまたがって実行されたため、2つの環境snapshotがあります。これらを1つの同時環境として扱ってはいけません。

## WSL/toolchain記録

- OS/kernel：WSL2 Linux `6.6.87.2-microsoft-standard-WSL2`
- Python：3.12.3
- Java：OpenJDK 11.0.31
- Git：2.43.0

正確にcaptureした文字列は、このdirectoryの`system.txt`、`python_version.txt`、`java_version.txt`、`git_version.txt`に保存されています。

`requirements_freeze.txt`は、NumPy 2.5.2とpandas 3.0.5を含む簡潔な後期Python snapshotです。環境記録として保存されていますが、完全なPhase 9 server環境であるとは主張しません。

## 試験済みPhase 9環境

Phase 9性能summaryには次が記録されています。

- Windows Python 3.10.6
- Intel CPU、physical core 20 / logical core 28
- system memory合計34,031,173,632 bytes

これらのserver/system段階で使用した完全なpackage freezeは`results/phase9_environment_freeze.txt`です。便宜上、ルートの`requirements.txt`は試験済みの完全環境をそのまま反映します。NumPy 2.2.6、pandas 2.3.2、FastAPI 0.141.1、Uvicorn 0.52.1、SciPy 1.15.3、scikit-learn 1.7.2、Pillow 11.3.0、ImageHash 4.3.2、および完全なtransitive環境を含みます。

正確なtiming再現は、OS、CPU、filesystem/cache状態、server process設定にも依存します。性能summaryは普遍的な定数ではなく、記録されたhostでの結果として扱ってください。

## 外部tool

- Phase 3Dでは`tools/phase3d/JavapBatch.java`のcompile/runにJavaが必要です。
- Phase 10では、Java function用に設定し、default/blindrename threshold 0.30を適用した別のOpen-NiCad/NiCadCross 7.0 installを使用します。
- 公開リポジトリsnapshot/downloadの復元時にのみGitとnetwork accessが必要であり、そのcacheは意図的に除外されています。

## 推奨する分離

過去のexact-server再現と最新のrerunには別々の仮想環境を使用してください。固定済みPhase 9環境を黙ってupgradeし、同一環境であるかのようにtimingを比較してはいけません。
