# Server-Side Multi-Parent Provenance Reconstruction for Copyright-Related Source Attribution in Heterogeneous Game MOD Packages

[![Research status](https://img.shields.io/badge/status-Phase_1--13_complete-2ea44f)](reproducibility/EXPERIMENT_INDEX.md#user-content-experiment-en)
[![Benchmark](https://img.shields.io/badge/benchmark-frozen-6f42c1)](reproducibility/EXPERIMENT_INDEX.md#freeze-anchors)
[![Reproducibility](https://img.shields.io/badge/reproducibility-audited-0969da)](REPRODUCE.md#user-content-reproduce-en)

## Languages

[English](README.md) · [Korean](README.ko.md) · [Japanese](README.ja.md)

## Method and findings at a glance

The method combines Java opcode SimHash, image hashes and structured-resource features, retrieves registered parent candidates, and assigns components to multiple parents or UNKNOWN. The frozen Phase 6–7 baseline is preserved separately from later extensions. Dependency-graph refinement had a small, statistically inconclusive effect on the primary TEST metric. This is technical attribution evidence for human review, not a legal ownership determination.

## Reading guide

Start with the research question and method, then inspect measured results and failure cases. Use the reproduction guide to distinguish the public artifacts from required local data.

[Explore the case](https://ysl-ryudo.github.io/en/research/mod/) · [Portfolio](https://ysl-ryudo.github.io/en/)

## Portfolio context and continuing research

This is an independent MOD-package provenance research project. It is **separate from the WISA 2026 image-asset study and the GCTLAB collaboration**. The method combines content evidence, registered-parent retrieval, hierarchical multi-parent assignment and an explicit UNKNOWN option. Phase 6–7 defines the frozen baseline; later extensions should preserve it and report new results separately.

The public repository contains selected code and results, not the complete local corpus. Consult [REPRODUCE.md](REPRODUCE.md) for data requirements. Existing measured results below retain their original scope; this documentation update did not rerun the experiments.

<a id="readme-en"></a>

This repository implements and evaluates server-side multi-parent provenance reconstruction for copyright-related source attribution in recomposed MOD/JAR packages. The method attributes code/binary, structured-resource, and image components to registered reference projects or `UNKNOWN`, reconstructs package-level mixed-source relationships, and supplies technical evidence for human review. Phase 1-13 source code, frozen evaluation records, principal results, and reproduction material are preserved here.

> [!IMPORTANT]
> The output is technical provenance evidence, not a legal determination of copyright ownership, infringement, permission, or liability. It is intended to support expert review.

## Research question

Can a server reconstruct the component-level registered origins and package-level multi-parent set needed for copyright-related source review when a recomposed package mixes multiple registered projects with previously unseen sources?

Redistribution can remove or rewrite path names, package metadata, and project identifiers. The study therefore relies on content evidence, preserves unsupported attribution as `UNKNOWN`, and reports results at both component and package levels. The question is technical source attribution; it does not ask the system to determine legal ownership, copying, permission, or infringement.

## System overview

```mermaid
flowchart LR
    A[MOD / JAR package] --> B[Component extraction]
    B --> C1[Code and binary evidence]
    B --> C2[Structured-resource evidence]
    B --> C3[Image evidence]
    C1 --> D[Registered-parent retrieval]
    C2 --> D
    C3 --> D
    D --> E[Hierarchical package reconstruction]
    G[Optional dependency graph] -. weak refinement .-> E
    E --> F[Known parent set + UNKNOWN]
    F --> H[Copyright-related source-review report]
```

Content evidence is the primary signal. The dependency graph is an optional weak refinement; its TEST effect on the primary parent-set metric was small and statistically inconclusive.

## Method

1. Build public project and release registries, while retaining raw downloadable payloads locally.
2. Extract identity-neutral evidence from code/binary, structured-resource, and image components.
3. Retrieve a fixed candidate pool of registered parent projects for each query package.
4. Jointly select the package-level parent set and assign each component to a selected parent or `UNKNOWN`.
5. Freeze the benchmark, parameters, manifests, and hashes before opening the final TEST split.
6. Evaluate uncertainty, baselines, external clone detection, deployment behavior, robustness, retrieval scalability, and failure localization without retuning the frozen method.

## Contributions

- A copyright-related source-attribution formulation that combines heterogeneous components, registered-parent attribution, and open-set `UNKNOWN` rejection.
- A hierarchical reconstruction method that links component assignments to a coherent package-level parent set.
- A frozen 120-project benchmark with public/private manifest separation, hash verification, and leakage audits.
- Query-level bootstrap, ablation, source-cluster sensitivity, server correctness, and host-specific performance analyses.
- External NiCadCross comparison on a strictly source-resolvable code subset, plus compatibility preparation for StoneDetector.
- Post-freeze multi-unknown robustness, approximate-retrieval scalability, and hierarchical failure-localization studies.

## Research progress

All Phase 1-13 scripts and reportable outputs are preserved on `main`. “Complete” means the recorded phase artifacts exist; only Phase 6 onward forms the frozen confirmatory benchmark.

| Phase | Scope | Status |
|---:|---|:---:|
| 1 | Pilot collection and 30-project real-MOD corpus | Complete |
| 2 | Source/release registries and duplicate audits | Complete |
| 3 | Version-drift and bytecode/content baselines | Complete |
| 4 | Dependency and resource-reference graphs | Complete |
| 5 | Exploratory multi-parent hierarchical reconstruction | Complete |
| 6 | Fresh 120-project corpus, frozen splits, 540 queries, and materialization | **Frozen** |
| 7 | Calibration, method freeze, and final TEST evaluation | **Frozen** |
| 8 | Bootstrap statistics, ablations, and source-cluster sensitivity | Complete |
| 9 | Server correctness, concurrency, end-to-end, and gallery scaling | Complete |
| 10 | NiCadCross external comparison and StoneDetector compatibility | Complete |
| 11 | Controlled multiple-unknown-source robustness | Complete |
| 12 | Exact versus binary-LSH retrieval and scalability | Complete |
| 13 | Post-freeze automated failure analysis | Complete |

The detailed script → input → output → result → freeze map is in the [Experiment Index](reproducibility/EXPERIMENT_INDEX.md#user-content-experiment-en).

## Key results

### Frozen Phase 7 TEST

The final evaluation contains 360 queries and 2,520 components. The graph-refined result is the frozen final method; content-only is retained as the primary signal and ablation reference.

| Track | Component accuracy | `UNKNOWN` F1 | Parent-set F1 | Parent-set exact | K accuracy |
|---|---:|---:|---:|---:|---:|
| Frozen final, graph-refined | 0.805952 | 0.753786 | 0.844233 | 0.419444 | 0.486111 |
| Content-only | 0.807143 | 0.752386 | 0.843545 | 0.413889 | 0.480556 |

Candidate retrieval reached 0.974444 mean known-parent recall, with every known parent present for 0.943333 of known-parent queries. Hierarchical content improved parent-set F1 by 0.046133 over independent component decisions. The graph-minus-content parent-set F1 delta was +0.000688, and its 95% query-bootstrap confidence interval included zero.

### System and external validation

| Evaluation | Scope | Headline result |
|---|---|---|
| Server correctness | 360 queries / 2,520 components | Predictions matched the frozen reference for every query and component. |
| Precomputed-score server | Best measured concurrency | 86.21 requests/s. |
| Evidence → search → reconstruction | Concurrency 1 | Server p50 12.579 ms; search 11.493 ms; reconstruction 1.088 ms. |
| Local package → result | Concurrency 1 | Server p50 26.880 ms; extraction 14.440 ms; search 10.685 ms. |
| Gallery scaling | 20 → 100 real projects | Sequential search p50 4.353 → 21.457 ms. |
| NiCadCross paired subset | 1,169 source-resolvable code components | Proposed 0.841 vs NiCadCross 0.710 component accuracy; delta +0.131, paired 95% CI 0.096-0.167. |

Phase 11 adds a controlled 180-query / 1,260-component recomposition analysis: component accuracy 0.841, `UNKNOWN` F1 0.888, and collapsed parent-set F1 0.884. Because the frozen model emits one public `UNKNOWN` label, these numbers measure rejection of unregistered components—not recovery of distinct unknown identities or multiplicity.

Phase 12 found that BALANCED and HIGH_RECALL binary-LSH configurations preserved Exact predictions on all 360 frozen TEST queries. FAST changed 1/360 query prediction and 1/2,520 component prediction, while reducing the 60-project runtime-sample p50 from 10.315 ms to 8.848 ms (1.166×). The `200eq`/`500eq`/`1000eq` conditions are synthetic component-volume stresses over 100 real registered parents, not additional unique MOD projects.

Phase 13 localized 489 frozen TEST component errors: component assignment 325 (66.46%), `UNKNOWN` rejection 81 (16.56%), parent selection 47 (9.61%), and retrieval 36 (7.36%). It is diagnostic only and does not recompute predictions or change the method.

## Repository map

```text
scripts/             Phase 1-13 collection, calibration, evaluation, and audit scripts
server/              Phase 9 FastAPI research services
tools/               Tracked helper source and tool configuration
results/             Curated summaries, audits, predictions, and frozen manifests
reproducibility/     Environment records, hashes, freeze manifests, and experiment index
archive/             Historical generated, superseded, and known-bug artifacts retained for audit
data/                Registries and redistributable metadata; raw payload bytes remain ignored
```

Raw MOD/JAR payloads, reconstructed external-tool corpora, private held-out mappings not approved for release, caches, generated server data, compiled files, and virtual environments are intentionally excluded from Git. See [Tracking Audit](reproducibility/TRACKING_AUDIT.md#user-content-tracking-en) for the preservation policy and historical classification.

## Reproduction and freeze anchors

- [Reproduction guide](REPRODUCE.md#user-content-reproduce-en)
- [Experiment index](reproducibility/EXPERIMENT_INDEX.md#user-content-experiment-en)
- [Environment record](reproducibility/ENVIRONMENT.md#user-content-environment-en)
- [Tracking audit](reproducibility/TRACKING_AUDIT.md#user-content-tracking-en)
- [Contribution guide](CONTRIBUTING.md#user-content-contributing-en)
- [Archive notes](archive/README.md#user-content-archive-en)
- [Phase 12 freeze manifest](reproducibility/phase12_freeze_manifest.sha256)
- [Phase 13 freeze manifest](reproducibility/phase13_freeze_manifest.sha256)

Core Phase 6-7 anchors include the frozen split, query manifest and ground truth, payload-hash manifest, graph tracks, and `results/phase7g_final_method_parameters.json`. The frozen parameter SHA-256 is `caad17257304d0ab198e01ef327f5acf918e6b8aab3f00e5272be3d20d3f8325`.

## Interpretation limits

- Do not infer legal ownership, copying, license compliance, or infringement from a provenance score alone.
- Do not claim the graph refinement is a statistically established improvement on the primary TEST metric.
- Do not compare the Phase 9 latency scopes as if they measured the same pipeline.
- NiCadCross receives reconstructed Java source while the proposed system uses frozen binary-side evidence; the comparison is restricted to the same source-resolvable subset.
- StoneDetector artifacts document compatibility preparation, not a completed comparative effectiveness result.
- Do not use Phase 7 TEST, Phase 11 recompositions, Phase 12 operating points, or Phase 13 diagnostics to retune the frozen method.

## Data, citation, license, and contact

This repository is public. Redistribution scope is assessed per artifact; the complete local research corpus is not included in the public repository. “Private” benchmark files refer to model-private evaluation labels; they are not credentials and must still be handled as sensitive research data.

Until formal bibliographic metadata is finalized, cite this repository together with the exact commit hash used for reproduction. No repository-wide license has yet been declared; do not assume that source code, datasets, MOD/JAR payloads, or third-party materials are licensed for redistribution. Original third-party licenses remain controlling.

For research questions or reproducibility reports, use the repository's GitHub Issues. For private contact, use the [repository owner's GitHub profile](https://github.com/YSL-RyuDo).
