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

연구를 WSL 환경과 Windows 시스템 성능 측정 환경에서 각각 수행했기 때문에 두 종류의 환경 기록이 남아 있다. 두 기록은 동일한 시점의 단일 환경을 나타내지 않는다.

## WSL 도구 환경 기록

- OS/kernel: WSL2 Linux `6.6.87.2-microsoft-standard-WSL2`
- Python: 3.12.3
- Java: OpenJDK 11.0.31
- Git: 2.43.0

당시 출력 문자열은 이 디렉터리의 `system.txt`, `python_version.txt`, `java_version.txt`, `git_version.txt`에 그대로 보존되어 있다.

`requirements_freeze.txt`는 NumPy 2.5.2와 pandas 3.0.5를 포함한 후속 Python 환경 요약이다. 환경 기록으로 보존하지만 Phase 9 서버의 전체 실행 환경을 나타내지는 않는다.

## 시험한 Phase 9 환경

Phase 9 성능 요약에는 다음 환경이 기록되어 있다.

- Windows Python 3.10.6
- Intel CPU, 물리 코어 20개 / 논리 코어 28개
- 전체 시스템 메모리 34,031,173,632바이트

서버·시스템 평가에 사용한 전체 패키지 목록은 `results/phase9_environment_freeze.txt`에 고정되어 있다. 저장소 루트의 `requirements.txt`도 같은 환경을 재현할 수 있도록 해당 목록을 반영한다. 주요 패키지는 NumPy 2.2.6, pandas 2.3.2, FastAPI 0.141.1, Uvicorn 0.52.1, SciPy 1.15.3, scikit-learn 1.7.2, Pillow 11.3.0, ImageHash 4.3.2이며, 이들이 의존하는 패키지도 함께 기록되어 있다.

정확한 실행 시간은 운영체제, CPU, 파일시스템·캐시 상태와 서버 프로세스 설정에 따라 달라진다. 따라서 성능 요약은 보편적인 수치가 아니라 기록된 실행 환경에서 얻은 결과로 해석해야 한다.

## 외부 도구

- Phase 3D에서 `tools/phase3d/JavapBatch.java`를 컴파일하고 실행하려면 Java가 필요하다.
- Phase 10은 Java 함수 단위 분석, `default`/`blindrename`, 임계값 0.30으로 설정한 별도의 Open-NiCad/NiCadCross 7.0 설치를 사용한다.
- 공개 저장소의 특정 시점 자료를 복원하거나 파일을 내려받을 때만 Git과 네트워크 접근이 필요하다. 내려받은 캐시는 Git 관리 대상에서 제외한다.

## 권장 격리

과거 서버 환경을 그대로 재현하는 경우와 최신 패키지로 다시 실행하는 경우에는 서로 다른 가상환경을 사용한다. 고정된 Phase 9 환경의 패키지를 바꾼 결과는 동일 조건의 실행 시간으로 비교할 수 없다.

---

<a id="environment-ja"></a>

# 再現環境

[![English](https://img.shields.io/badge/EN-English-6E7781?style=for-the-badge)](#user-content-environment-en) [![한국어](https://img.shields.io/badge/KO-%ED%95%9C%EA%B5%AD%EC%96%B4-6E7781?style=for-the-badge)](#user-content-environment-ko) [![日本語](https://img.shields.io/badge/JA-%E6%97%A5%E6%9C%AC%E8%AA%9E-0969DA?style=for-the-badge)](#user-content-environment-ja)

[← 再現ガイド](../REPRODUCE.md#user-content-reproduce-ja)

研究はWSL環境とWindows上のシステム性能測定環境で別々に実行したため、2種類の環境記録が残っている。両者は同一時点の単一環境を示すものではない。

## WSLツール環境の記録

- OS/kernel：WSL2 Linux `6.6.87.2-microsoft-standard-WSL2`
- Python：3.12.3
- Java：OpenJDK 11.0.31
- Git：2.43.0

当時の出力文字列は、このディレクトリの`system.txt`、`python_version.txt`、`java_version.txt`、`git_version.txt`にそのまま保存している。

`requirements_freeze.txt`は、NumPy 2.5.2とpandas 3.0.5を含む後期のPython環境要約である。環境記録として保存しているが、Phase 9サーバーの完全な実行環境を示すものではない。

## 試験済みPhase 9環境

Phase 9の性能要約には次の環境を記録している。

- Windows Python 3.10.6
- Intel CPU、物理コア20 / 論理コア28
- システムメモリ合計34,031,173,632バイト

サーバー・システム評価に用いた全パッケージ一覧は`results/phase9_environment_freeze.txt`に固定している。リポジトリルートの`requirements.txt`も、同じ環境を再現できるよう当該一覧を反映する。主要パッケージはNumPy 2.2.6、pandas 2.3.2、FastAPI 0.141.1、Uvicorn 0.52.1、SciPy 1.15.3、scikit-learn 1.7.2、Pillow 11.3.0、ImageHash 4.3.2であり、依存パッケージも併記している。

正確な処理時間は、OS、CPU、ファイルシステム・キャッシュの状態、サーバープロセスの設定によって変化する。性能要約は普遍的な値ではなく、記録された実行環境で得られた結果として解釈する必要がある。

## 外部ツール

- Phase 3Dで`tools/phase3d/JavapBatch.java`をコンパイル・実行するにはJavaが必要である。
- Phase 10では、Java関数単位、`default`/`blindrename`、しきい値0.30に設定した別途導入のOpen-NiCad/NiCadCross 7.0を使用する。
- 公開リポジトリの特定時点の資料を復元したり、ファイルをダウンロードしたりする場合にのみGitとネットワーク接続が必要となる。ダウンロード済みキャッシュはGit管理対象外である。

## 推奨する分離

過去のサーバー環境をそのまま再現する場合と、最新パッケージで再実行する場合には、別々の仮想環境を使用する。固定済みPhase 9環境のパッケージを変更した結果は、同一条件の処理時間として比較できない。
