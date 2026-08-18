#!/usr/bin/env python3

import json
import math
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

GALLERY = ROOT / "results/phase7b_gallery_identity_neutral_evidence.csv"
QUERY = ROOT / "results/phase7b_query_identity_neutral_evidence.csv"
SCORES = ROOT / "results/phase7h_test_component_parent_scores.csv"
EXACT_AUDIT = ROOT / "results/phase7h_test_candidate_retrieval_audit.csv"
FINAL_QUERY = ROOT / "results/phase7h_final_query_predictions.csv"

OUT_POOLS = ROOT / "results/phase12a_ann_candidate_pools.csv"
OUT_CONFIG = ROOT / "results/phase12a_ann_config_summary.csv"
OUT_SUMMARY = ROOT / "results/phase12a_ann_candidate_summary.json"


THRESHOLDS = {
    "CODE_BINARY": 0.1302083283662796,
    "STRUCTURED": 0.03125,
    "IMAGE": 0.0,
}

ALPHA = 0.75
REGRET_WEIGHT = 0.25
CANDIDATE_POOL_M = 10


# ---------------------------------------------------------
# ANN operating points.
#
# These are fixed a priori and ALL are reported.
# TEST results are NOT used to select/tune one configuration.
#
# 128-bit signatures:
# FAST       = 4 x 32-bit bands
# BALANCED   = 8 x 16-bit bands
# HIGH       = 16 x 8-bit bands
#
# 64-bit signatures use proportional banding.
# ---------------------------------------------------------

CONFIGS = {
    "FAST": {
        128: (4, 32),
        64: (2, 32),
    },
    "BALANCED": {
        128: (8, 16),
        64: (4, 16),
    },
    "HIGH_RECALL": {
        128: (16, 8),
        64: (8, 8),
    },
}


REPRESENTATIONS = {
    "CODE_BINARY": [
        ("code_op3_simhash128", 128),
        ("code_struct_simhash128", 128),
        ("code_context_simhash128", 128),
    ],
    "STRUCTURED": [
        ("structured_simhash128", 128),
    ],
    "IMAGE": [
        ("image_ahash64", 64),
        ("image_dhash64", 64),
        ("image_phash64", 64),
    ],
}


def clean(value):
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def percentile(values, q):
    if not values:
        return None
    return float(np.percentile(np.asarray(values, dtype=np.float64), q))


def normalized_component_cost(modality, distance, regret):
    threshold = THRESHOLDS[modality]

    distance = float(distance)
    regret = float(regret)

    if threshold > 0:
        normalized_distance = min(distance / threshold, 1.0)
    else:
        normalized_distance = 0.0 if abs(distance) <= 1e-12 else 1.0

    normalized_regret = min(max(regret, 0.0), 1.0)

    return (
        ALPHA * normalized_distance
        + REGRET_WEIGHT * normalized_regret
    )


def split_bands(hex_text, bits, config):
    text = clean(hex_text)
    if not text:
        return []

    try:
        value = int(text, 16)
    except ValueError:
        return []

    band_count, band_width = config[bits]

    if band_count * band_width != bits:
        raise RuntimeError("Invalid LSH band configuration")

    mask = (1 << band_width) - 1

    result = []

    for band_id in range(band_count):
        shift = band_id * band_width
        band_value = (value >> shift) & mask
        result.append((band_id, band_value))

    return result


for path in [GALLERY, QUERY, SCORES, EXACT_AUDIT, FINAL_QUERY]:
    if not path.exists():
        raise FileNotFoundError(path)


print("==========================================")
print("Phase 12A - ANN Candidate Fidelity Audit")
print("==========================================")


gallery = pd.read_csv(GALLERY)
query = pd.read_csv(QUERY)
scores = pd.read_csv(SCORES)
exact_audit = pd.read_csv(EXACT_AUDIT)
final_query = pd.read_csv(FINAL_QUERY)

# =========================================================
# Frozen Phase7H TEST gallery only
#
# phase7b gallery contains components from multiple frozen
# splits.  Phase7H TEST inference used exactly:
#   TEST_KNOWN: 45 projects
#   TEST_BG:    15 projects
# for a total of 60 registered gallery projects.
#
# Phase12 must preserve that exact gallery universe.
# =========================================================

gallery = gallery[
    gallery["frozen_split"].astype(str).isin(
        ["TEST_KNOWN", "TEST_BACKGROUND"]
    )
].copy()


test_query_ids = sorted(
    final_query["query_id"].astype(str).unique().tolist()
)

if len(test_query_ids) != 360:
    raise RuntimeError(
        f"Expected 360 TEST queries, got {len(test_query_ids)}"
    )


query = query[
    query["query_id"].astype(str).isin(test_query_ids)
].copy()

if len(query) != 360 * 7:
    raise RuntimeError(
        f"Expected 2520 TEST query components, got {len(query)}"
    )


gallery_parents = sorted(
    gallery["fresh_id"].astype(str).unique().tolist()
)

if len(gallery_parents) != 60:
    raise RuntimeError(
        f"Expected frozen 60-project gallery, got {len(gallery_parents)}"
    )


print("Gallery components:", len(gallery))
print("Gallery parents:", len(gallery_parents))
print("TEST queries:", len(test_query_ids))
print("TEST components:", len(query))


# =========================================================
# Frozen exact query -> parent retrieval scores
#
# Reconstruct exact Phase7E retrieval score:
# normalized component cost, then mean of best 3 components.
# =========================================================

print()
print("Building frozen exact retrieval score table...")


scores["query_id"] = scores["query_id"].astype(str)
scores["node_id"] = scores["node_id"].astype(str)
scores["candidate_parent"] = scores["candidate_parent"].astype(str)
scores["modality"] = scores["modality"].astype(str)


exact_retrieval_scores = {}
exact_rankings = {}


for q_index, query_id in enumerate(test_query_ids, start=1):

    group = scores[scores["query_id"] == query_id]

    node_ids = sorted(group["node_id"].unique().tolist())

    if len(node_ids) != 7:
        raise RuntimeError(f"{query_id}: expected 7 nodes")

    candidate_parents = sorted(
        group["candidate_parent"].unique().tolist()
    )

    if len(candidate_parents) != 60:
        raise RuntimeError(
            f"{query_id}: expected 60 candidate parents"
        )

    per_parent = {}

    for parent in candidate_parents:

        pg = group[group["candidate_parent"] == parent]

        costs = []

        for row in pg.itertuples(index=False):

            costs.append(
                normalized_component_cost(
                    clean(row.modality),
                    float(row.fused_parent_distance),
                    float(row.mean_regret),
                )
            )

        if len(costs) != 7:
            raise RuntimeError(
                f"{query_id}/{parent}: expected 7 costs"
            )

        costs.sort()

        per_parent[parent] = float(
            np.mean(costs[:3])
        )

    ranking = sorted(
        candidate_parents,
        key=lambda parent: (
            per_parent[parent],
            parent,
        ),
    )

    exact_retrieval_scores[query_id] = per_parent
    exact_rankings[query_id] = ranking

    if q_index % 60 == 0:
        print(" exact score query", q_index, "/", len(test_query_ids))


# Verify against frozen Phase7H audit.

audit_pool = {}

for row in exact_audit.itertuples(index=False):
    qid = clean(row.query_id)
    audit_pool[qid] = json.loads(clean(row.candidate_pool))


mismatch = []

for qid in test_query_ids:
    expected = audit_pool[qid]
    rebuilt = exact_rankings[qid][:CANDIDATE_POOL_M]

    if expected != rebuilt:
        mismatch.append(qid)


if mismatch:
    raise RuntimeError(
        "Frozen exact retrieval reconstruction mismatch: "
        + repr(mismatch[:10])
    )


print("Frozen Exact Top-10 reconstruction: PASS")


# =========================================================
# Ground truth known parent sets
# =========================================================

true_known = {}

for row in final_query.itertuples(index=False):

    qid = clean(row.query_id)

    parents = set(json.loads(clean(row.true_parent_set)))

    parents.discard("UNKNOWN")

    true_known[qid] = parents


# =========================================================
# Build LSH index per configuration
# =========================================================

gallery_rows = list(gallery.itertuples(index=False))
query_groups = {
    qid: group.copy()
    for qid, group in query.groupby("query_id")
}


pool_rows = []
config_rows = []
summary_configs = {}


for config_name, config in CONFIGS.items():

    print()
    print("------------------------------------------")
    print("Configuration:", config_name)
    print("------------------------------------------")

    build_start = time.perf_counter_ns()

    # index[(column, band_id, band_value)] -> set(parent IDs)
    index = defaultdict(set)

    posting_count = 0

    for row in gallery_rows:

        modality = clean(row.modality)
        parent = clean(row.fresh_id)

        for column, bits in REPRESENTATIONS[modality]:

            value = getattr(row, column)

            for band_id, band_value in split_bands(
                value,
                bits,
                config,
            ):
                index[
                    (
                        column,
                        band_id,
                        band_value,
                    )
                ].add(parent)

                posting_count += 1

    build_end = time.perf_counter_ns()

    build_ms = (
        build_end - build_start
    ) / 1_000_000.0

    print("LSH keys:", len(index))
    print("Postings:", posting_count)
    print("Build ms:", round(build_ms, 3))


    query_latencies_ms = []
    shortlist_sizes = []
    pool_sizes = []
    recalls = []
    all_present = []
    top10_overlap = []
    top10_exact_match = []
    under10_count = 0
    empty_shortlist_count = 0


    for q_index, qid in enumerate(test_query_ids, start=1):

        q_start = time.perf_counter_ns()

        shortlist = set()

        group = query_groups[qid]

        for row in group.itertuples(index=False):

            modality = clean(row.modality)

            for column, bits in REPRESENTATIONS[modality]:

                value = getattr(row, column)

                for band_id, band_value in split_bands(
                    value,
                    bits,
                    config,
                ):

                    shortlist.update(
                        index.get(
                            (
                                column,
                                band_id,
                                band_value,
                            ),
                            (),
                        )
                    )

        # ANN only generates a parent shortlist.
        #
        # Within this shortlist, use EXACT frozen Phase7
        # query-parent retrieval scores for reranking.
        #
        # No approximate score is used for provenance decisions.

        ranked_shortlist = sorted(
            shortlist,
            key=lambda parent: (
                exact_retrieval_scores[qid][parent],
                parent,
            ),
        )

        candidate_pool = ranked_shortlist[:CANDIDATE_POOL_M]

        q_end = time.perf_counter_ns()

        latency_ms = (
            q_end - q_start
        ) / 1_000_000.0

        query_latencies_ms.append(latency_ms)

        shortlist_sizes.append(len(shortlist))
        pool_sizes.append(len(candidate_pool))

        if len(shortlist) == 0:
            empty_shortlist_count += 1

        if len(candidate_pool) < CANDIDATE_POOL_M:
            under10_count += 1


        truth = true_known[qid]

        if truth:
            covered = len(
                truth & set(candidate_pool)
            )

            recall = covered / len(truth)

            recalls.append(recall)
            all_present.append(
                truth <= set(candidate_pool)
            )
        else:
            recall = math.nan


        exact_top10 = exact_rankings[qid][:CANDIDATE_POOL_M]

        overlap = len(
            set(candidate_pool)
            &
            set(exact_top10)
        ) / CANDIDATE_POOL_M

        top10_overlap.append(overlap)

        exact_same = bool(
            candidate_pool == exact_top10
        )

        top10_exact_match.append(exact_same)


        pool_rows.append({
            "config": config_name,
            "query_id": qid,
            "shortlist_parent_count": len(shortlist),
            "candidate_pool_count": len(candidate_pool),
            "known_true_parent_count": len(truth),
            "known_parent_recall":
                None if not truth else float(recall),
            "all_known_true_parents_present":
                None if not truth
                else bool(truth <= set(candidate_pool)),
            "exact_top10_overlap": float(overlap),
            "exact_top10_identical": exact_same,
            "ann_candidate_generation_and_rerank_ms":
                float(latency_ms),
            "candidate_pool": json.dumps(candidate_pool),
            "exact_candidate_pool": json.dumps(exact_top10),
        })


        if q_index % 60 == 0:
            print(
                " query",
                q_index,
                "/",
                len(test_query_ids),
            )


    known_query_count = len(recalls)

    row = {
        "config": config_name,
        "queries": len(test_query_ids),
        "known_parent_queries": known_query_count,
        "mean_shortlist_parents": float(
            np.mean(shortlist_sizes)
        ),
        "median_shortlist_parents": float(
            np.median(shortlist_sizes)
        ),
        "mean_candidate_pool_size": float(
            np.mean(pool_sizes)
        ),
        "candidate_pool_under_10_queries":
            int(under10_count),
        "empty_shortlist_queries":
            int(empty_shortlist_count),
        "mean_known_parent_recall":
            float(np.mean(recalls)),
        "all_known_true_parents_present_rate":
            float(np.mean(all_present)),
        "mean_exact_top10_overlap":
            float(np.mean(top10_overlap)),
        "exact_top10_identical_rate":
            float(np.mean(top10_exact_match)),
        "latency_mean_ms":
            float(np.mean(query_latencies_ms)),
        "latency_p50_ms":
            percentile(query_latencies_ms, 50),
        "latency_p95_ms":
            percentile(query_latencies_ms, 95),
        "latency_p99_ms":
            percentile(query_latencies_ms, 99),
        "index_build_ms":
            float(build_ms),
        "index_unique_bucket_keys":
            int(len(index)),
        "index_postings":
            int(posting_count),
    }

    config_rows.append(row)

    summary_configs[config_name] = row


pool_df = pd.DataFrame(pool_rows)
config_df = pd.DataFrame(config_rows)

pool_df.to_csv(
    OUT_POOLS,
    index=False,
)

config_df.to_csv(
    OUT_CONFIG,
    index=False,
)


summary = {
    "phase12a_complete": True,
    "scope": "ANN_CANDIDATE_GENERATION_FIDELITY_AUDIT",
    "frozen_method_modified": False,
    "phase7_parameters_retuned": False,
    "test_used_for_ann_parameter_selection": False,
    "benchmark": {
        "gallery_projects": len(gallery_parents),
        "gallery_components": len(gallery),
        "test_queries": len(test_query_ids),
        "test_components": len(query),
        "candidate_pool_M": CANDIDATE_POOL_M,
    },
    "method": {
        "ann_family": "MULTI_TABLE_BINARY_LSH",
        "candidate_generation_only": True,
        "exact_frozen_distance_reranking": True,
        "histogram_used_for_lsh": False,
        "histogram_still_used_in_frozen_exact_reranking": True,
        "configurations_reported_without_test_selection":
            list(CONFIGS.keys()),
    },
    "configs": summary_configs,
    "interpretation_rule": {
        "ann_score_is_not_final_provenance_score": True,
        "candidate_generation":
            "LSH retrieves candidate registered parents from frozen binary signatures.",
        "reranking":
            "Retrieved parents are reranked using the exact frozen Phase7 query-parent retrieval score.",
        "downstream_solver":
            "Evaluated separately in Phase12B.",
    },
}


OUT_SUMMARY.write_text(
    json.dumps(
        summary,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)


print()
print("==========================================")
print("Phase 12A COMPLETE")
print("==========================================")

print()
print(config_df.to_string(index=False))

print()
print("Wrote:", OUT_POOLS)
print("Wrote:", OUT_CONFIG)
print("Wrote:", OUT_SUMMARY)
