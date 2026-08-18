#!/usr/bin/env python3

import json
import math
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

GALLERY_FILE = ROOT / "results/phase7b_gallery_identity_neutral_evidence.csv"
QUERY_FILE = ROOT / "results/phase7b_query_identity_neutral_evidence.csv"
FINAL_QUERY_FILE = ROOT / "results/phase7h_final_query_predictions.csv"
FROZEN_AUDIT_FILE = ROOT / "results/phase7h_test_candidate_retrieval_audit.csv"

OUT_QUERY = ROOT / "results/phase12c_online_retrieval_queries.csv"
OUT_METRICS = ROOT / "results/phase12c_online_retrieval_metrics.csv"
OUT_SUMMARY = ROOT / "results/phase12c_online_retrieval_summary.json"


TEST_SPLITS = {
    "TEST_KNOWN",
    "TEST_BACKGROUND",
}

THRESHOLDS = {
    "CODE_BINARY": 0.1302083283662796,
    "STRUCTURED": 0.03125,
    "IMAGE": 0.0,
}

ALPHA = 0.75
REGRET_WEIGHT = 0.25
MISSING_PARENT_DISTANCE = 1.0
CANDIDATE_POOL_M = 10

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

POPCOUNT = np.asarray(
    [bin(i).count("1") for i in range(256)],
    dtype=np.uint8,
)


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

    return float(
        np.percentile(
            np.asarray(values, dtype=np.float64),
            q,
        )
    )


def parse_hex128_optional(value):
    text = clean(value)

    if not text:
        return None

    integer = int(text, 16)

    high = np.uint64(
        (integer >> 64)
        &
        ((1 << 64) - 1)
    )

    low = np.uint64(
        integer
        &
        ((1 << 64) - 1)
    )

    return high, low


def parse_hex64_optional(value):
    text = clean(value)

    if not text:
        return None

    return np.uint64(
        int(text, 16)
        &
        ((1 << 64) - 1)
    )


def parse_hist16(value):
    text = clean(value)

    parts = [
        x.strip()
        for x in text.split(",")
    ]

    if len(parts) != 16:
        raise ValueError(
            f"Expected 16 histogram bins, got {len(parts)}"
        )

    return np.asarray(
        [int(x) for x in parts],
        dtype=np.float32,
    )


def popcount64_array(values):
    x = np.ascontiguousarray(
        values,
        dtype=np.uint64,
    )

    byte_view = x.view(np.uint8).reshape(-1, 8)

    return (
        POPCOUNT[byte_view]
        .sum(axis=1)
        .astype(np.float32)
    )


def hamming64_array(values, query):
    xor = np.bitwise_xor(
        values,
        np.uint64(query),
    )

    return (
        popcount64_array(xor)
        /
        64.0
    ).astype(np.float32)


def hamming128_array(
    highs,
    lows,
    q_high,
    q_low,
):
    xor_high = np.bitwise_xor(
        highs,
        np.uint64(q_high),
    )

    xor_low = np.bitwise_xor(
        lows,
        np.uint64(q_low),
    )

    counts = (
        popcount64_array(xor_high)
        +
        popcount64_array(xor_low)
    )

    return (
        counts
        /
        128.0
    ).astype(np.float32)


def split_bands(
    value,
    bits,
    config,
):
    text = clean(value)

    if not text:
        return []

    integer = int(text, 16)

    band_count, band_width = config[bits]

    if band_count * band_width != bits:
        raise RuntimeError(
            "Invalid LSH configuration"
        )

    mask = (
        1 << band_width
    ) - 1

    output = []

    for band_id in range(band_count):
        output.append(
            (
                band_id,
                (
                    integer
                    >>
                    (band_id * band_width)
                )
                &
                mask,
            )
        )

    return output


def parent_minimum(
    component_distances,
    project_indices,
    project_count,
):
    result = np.full(
        project_count,
        np.inf,
        dtype=np.float32,
    )

    if len(component_distances):
        np.minimum.at(
            result,
            project_indices,
            component_distances,
        )

    result[
        ~np.isfinite(result)
    ] = MISSING_PARENT_DISTANCE

    return result


def normalized_component_cost(
    modality,
    distance,
    regret,
):
    threshold = THRESHOLDS[
        modality
    ]

    distance = float(distance)
    regret = float(regret)

    if threshold > 0:
        normalized_distance = min(
            distance / threshold,
            1.0,
        )
    else:
        normalized_distance = (
            0.0
            if abs(distance) <= 1e-12
            else 1.0
        )

    normalized_regret = min(
        max(regret, 0.0),
        1.0,
    )

    return float(
        ALPHA
        *
        normalized_distance
        +
        REGRET_WEIGHT
        *
        normalized_regret
    )


for path in [
    GALLERY_FILE,
    QUERY_FILE,
    FINAL_QUERY_FILE,
    FROZEN_AUDIT_FILE,
]:
    if not path.exists():
        raise FileNotFoundError(path)


print(
    "=========================================="
)
print(
    "Phase 12C - Online Exact vs LSH Retrieval"
)
print(
    "=========================================="
)


gallery = pd.read_csv(
    GALLERY_FILE,
)

query = pd.read_csv(
    QUERY_FILE,
)

final_query = pd.read_csv(
    FINAL_QUERY_FILE,
    dtype=str,
    keep_default_na=False,
)

frozen_audit = pd.read_csv(
    FROZEN_AUDIT_FILE,
    dtype=str,
    keep_default_na=False,
)


# =========================================================
# Exact frozen TEST universe
# =========================================================

gallery = gallery[
    gallery[
        "frozen_split"
    ].astype(str).isin(
        TEST_SPLITS
    )
].copy()


projects = sorted(
    gallery[
        "fresh_id"
    ]
    .astype(str)
    .unique()
    .tolist()
)


if len(projects) != 60:
    raise RuntimeError(
        f"Expected 60 TEST gallery projects, got {len(projects)}"
    )


project_to_index = {
    project: i
    for i, project
    in enumerate(projects)
}

index_to_project = {
    i: project
    for project, i
    in project_to_index.items()
}


test_query_ids = sorted(
    final_query[
        "query_id"
    ]
    .astype(str)
    .unique()
    .tolist()
)


if len(test_query_ids) != 360:
    raise RuntimeError(
        f"Expected 360 TEST queries, got {len(test_query_ids)}"
    )


query = query[
    query[
        "query_id"
    ]
    .astype(str)
    .isin(test_query_ids)
].copy()


if len(query) != 2520:
    raise RuntimeError(
        f"Expected 2520 TEST components, got {len(query)}"
    )


print(
    "Gallery projects:",
    len(projects),
)
print(
    "Gallery components:",
    len(gallery),
)
print(
    "TEST queries:",
    len(test_query_ids),
)
print(
    "TEST components:",
    len(query),
)


# =========================================================
# Ground-truth registered parent sets
# =========================================================

true_known = {}

scenario = {}

for row in final_query.itertuples(
    index=False
):
    qid = clean(
        row.query_id
    )

    parents = set(
        json.loads(
            clean(
                row.true_parent_set
            )
        )
    )

    parents.discard(
        "UNKNOWN"
    )

    true_known[
        qid
    ] = parents

    scenario[
        qid
    ] = clean(
        row.scenario
    )


# =========================================================
# Frozen Exact Top-10
# =========================================================

frozen_exact_pool = {}

for row in frozen_audit.itertuples(
    index=False
):
    frozen_exact_pool[
        clean(row.query_id)
    ] = json.loads(
        clean(
            row.candidate_pool
        )
    )


# =========================================================
# Build gallery arrays
# =========================================================

def build128(
    frame,
    column,
):
    highs = []
    lows = []
    parents = []

    for row in frame.itertuples(
        index=False
    ):
        parsed = (
            parse_hex128_optional(
                getattr(
                    row,
                    column,
                )
            )
        )

        if parsed is None:
            continue

        high, low = parsed

        highs.append(high)
        lows.append(low)

        parents.append(
            project_to_index[
                clean(
                    row.fresh_id
                )
            ]
        )

    return {
        "high":
            np.asarray(
                highs,
                dtype=np.uint64,
            ),

        "low":
            np.asarray(
                lows,
                dtype=np.uint64,
            ),

        "parent":
            np.asarray(
                parents,
                dtype=np.int32,
            ),
    }


def build64(
    frame,
    column,
):
    values = []
    parents = []

    for row in frame.itertuples(
        index=False
    ):
        parsed = (
            parse_hex64_optional(
                getattr(
                    row,
                    column,
                )
            )
        )

        if parsed is None:
            continue

        values.append(
            parsed
        )

        parents.append(
            project_to_index[
                clean(
                    row.fresh_id
                )
            ]
        )

    return {
        "value":
            np.asarray(
                values,
                dtype=np.uint64,
            ),

        "parent":
            np.asarray(
                parents,
                dtype=np.int32,
            ),
    }


code_gallery = gallery[
    gallery[
        "modality"
    ].astype(str)
    == "CODE_BINARY"
].copy()

struct_gallery = gallery[
    gallery[
        "modality"
    ].astype(str)
    == "STRUCTURED"
].copy()

image_gallery = gallery[
    gallery[
        "modality"
    ].astype(str)
    == "IMAGE"
].copy()


code_op3 = build128(
    code_gallery,
    "code_op3_simhash128",
)

code_struct = build128(
    code_gallery,
    "code_struct_simhash128",
)

code_context = build128(
    code_gallery,
    "code_context_simhash128",
)

structured_rep = build128(
    struct_gallery,
    "structured_simhash128",
)

image_ahash = build64(
    image_gallery,
    "image_ahash64",
)

image_dhash = build64(
    image_gallery,
    "image_dhash64",
)

image_phash = build64(
    image_gallery,
    "image_phash64",
)


image_hist_values = []
image_hist_parents = []

for row in image_gallery.itertuples(
    index=False
):
    text = clean(
        row.image_hist16
    )

    if not text:
        continue

    image_hist_values.append(
        parse_hist16(
            text
        )
    )

    image_hist_parents.append(
        project_to_index[
            clean(
                row.fresh_id
            )
        ]
    )


image_hist = {
    "value":
        np.asarray(
            image_hist_values,
            dtype=np.float32,
        ),

    "parent":
        np.asarray(
            image_hist_parents,
            dtype=np.int32,
        ),
}


# =========================================================
# Per-parent component index caches for ANN reranking
# =========================================================

def indices_by_parent(parent_array):
    result = {}

    for parent_index in range(
        len(projects)
    ):
        result[
            parent_index
        ] = np.where(
            parent_array
            ==
            parent_index
        )[0]

    return result


for rep in [
    code_op3,
    code_struct,
    code_context,
    structured_rep,
    image_ahash,
    image_dhash,
    image_phash,
    image_hist,
]:
    rep[
        "by_parent"
    ] = indices_by_parent(
        rep[
            "parent"
        ]
    )


# =========================================================
# Query groups
# =========================================================

query_groups = {
    str(qid):
        group.sort_values(
            "node_id"
        ).copy()

    for qid, group
    in query.groupby(
        "query_id"
    )
}


for qid in test_query_ids:
    if len(
        query_groups[qid]
    ) != 7:
        raise RuntimeError(
            f"{qid}: expected 7 query components"
        )


# =========================================================
# LSH parent indices
# =========================================================

lsh_indices = {}


for config_name, config in CONFIGS.items():

    build_start = time.perf_counter_ns()

    lsh = defaultdict(set)

    for row in gallery.itertuples(
        index=False
    ):

        modality = clean(
            row.modality
        )

        parent = clean(
            row.fresh_id
        )

        for column, bits in (
            REPRESENTATIONS[
                modality
            ]
        ):
            for band_id, band_value in split_bands(
                getattr(
                    row,
                    column,
                ),
                bits,
                config,
            ):
                lsh[
                    (
                        column,
                        band_id,
                        band_value,
                    )
                ].add(
                    parent
                )

    build_end = time.perf_counter_ns()

    lsh_indices[
        config_name
    ] = {
        "index":
            lsh,

        "build_ms":
            (
                build_end
                -
                build_start
            )
            /
            1_000_000.0,

        "keys":
            len(lsh),
    }


# =========================================================
# Select representation subarray
# =========================================================

def subset_indices(
    rep,
    allowed_parent_indices,
):
    if allowed_parent_indices is None:
        return None

    chunks = [
        rep[
            "by_parent"
        ][parent_index]

        for parent_index
        in allowed_parent_indices

        if len(
            rep[
                "by_parent"
            ][parent_index]
        )
    ]

    if not chunks:
        return np.empty(
            0,
            dtype=np.int64,
        )

    return np.concatenate(
        chunks
    )


def parent_min_for_128(
    rep,
    q_high,
    q_low,
    allowed_parent_indices=None,
):
    if allowed_parent_indices is None:
        high = rep["high"]
        low = rep["low"]
        parents = rep["parent"]

    else:
        idx = subset_indices(
            rep,
            allowed_parent_indices,
        )

        high = rep["high"][idx]
        low = rep["low"][idx]
        parents = rep["parent"][idx]

    distances = hamming128_array(
        high,
        low,
        q_high,
        q_low,
    )

    return parent_minimum(
        distances,
        parents,
        len(projects),
    )


def parent_min_for_64(
    rep,
    q_value,
    allowed_parent_indices=None,
):
    if allowed_parent_indices is None:
        values = rep["value"]
        parents = rep["parent"]

    else:
        idx = subset_indices(
            rep,
            allowed_parent_indices,
        )

        values = rep["value"][idx]
        parents = rep["parent"][idx]

    distances = hamming64_array(
        values,
        q_value,
    )

    return parent_minimum(
        distances,
        parents,
        len(projects),
    )


def parent_min_for_hist(
    q_hist,
    allowed_parent_indices=None,
):
    rep = image_hist

    if allowed_parent_indices is None:
        values = rep["value"]
        parents = rep["parent"]

    else:
        idx = subset_indices(
            rep,
            allowed_parent_indices,
        )

        values = rep["value"][idx]
        parents = rep["parent"][idx]

    if len(values) == 0:
        distances = np.empty(
            0,
            dtype=np.float32,
        )
    else:
        distances = (
            np.abs(
                values
                -
                q_hist[
                    None,
                    :
                ]
            )
            .sum(axis=1)
            /
            20000.0
        ).astype(
            np.float32
        )

        distances = np.clip(
            distances,
            0.0,
            1.0,
        )

    return parent_minimum(
        distances,
        parents,
        len(projects),
    )


# =========================================================
# Online scoring
# =========================================================

def component_parent_values(
    row,
    allowed_parents=None,
):
    modality = clean(
        row.modality
    )

    if allowed_parents is None:
        allowed_indices = None
        visible_indices = np.arange(
            len(projects),
            dtype=np.int32,
        )

    else:
        allowed_indices = sorted(
            project_to_index[p]
            for p in allowed_parents
        )

        visible_indices = np.asarray(
            allowed_indices,
            dtype=np.int32,
        )


    vectors = []


    if modality == "CODE_BINARY":

        parsed = parse_hex128_optional(
            row.code_op3_simhash128
        )

        if parsed is not None:
            vectors.append(
                parent_min_for_128(
                    code_op3,
                    parsed[0],
                    parsed[1],
                    allowed_indices,
                )
            )


        parsed = parse_hex128_optional(
            row.code_struct_simhash128
        )

        if parsed is not None:
            vectors.append(
                parent_min_for_128(
                    code_struct,
                    parsed[0],
                    parsed[1],
                    allowed_indices,
                )
            )


        parsed = parse_hex128_optional(
            row.code_context_simhash128
        )

        if parsed is not None:
            vectors.append(
                parent_min_for_128(
                    code_context,
                    parsed[0],
                    parsed[1],
                    allowed_indices,
                )
            )


    elif modality == "STRUCTURED":

        parsed = parse_hex128_optional(
            row.structured_simhash128
        )

        if parsed is None:
            raise RuntimeError(
                "Missing STRUCTURED signature"
            )

        vectors.append(
            parent_min_for_128(
                structured_rep,
                parsed[0],
                parsed[1],
                allowed_indices,
            )
        )


    elif modality == "IMAGE":

        q_ahash = parse_hex64_optional(
            row.image_ahash64
        )

        q_dhash = parse_hex64_optional(
            row.image_dhash64
        )

        q_phash = parse_hex64_optional(
            row.image_phash64
        )

        q_hist = parse_hist16(
            row.image_hist16
        )

        vectors.extend([
            parent_min_for_64(
                image_ahash,
                q_ahash,
                allowed_indices,
            ),
            parent_min_for_64(
                image_dhash,
                q_dhash,
                allowed_indices,
            ),
            parent_min_for_64(
                image_phash,
                q_phash,
                allowed_indices,
            ),
            parent_min_for_hist(
                q_hist,
                allowed_indices,
            ),
        ])

    else:
        raise RuntimeError(
            f"Unsupported modality: {modality}"
        )


    if not vectors:
        raise RuntimeError(
            "No representation vectors"
        )


    matrix = np.vstack(
        vectors
    )


    fused = matrix.mean(
        axis=0
    )


    regret_matrix = np.zeros_like(
        matrix,
        dtype=np.float32,
    )


    for rep_index in range(
        matrix.shape[0]
    ):

        visible_values = matrix[
            rep_index,
            visible_indices,
        ]

        if len(visible_values) == 0:
            reference_minimum = 1.0
        else:
            reference_minimum = float(
                visible_values.min()
            )

        regret_matrix[
            rep_index
        ] = (
            matrix[
                rep_index
            ]
            -
            reference_minimum
        )


    mean_regret = regret_matrix.mean(
        axis=0
    )


    output = {}

    for index in visible_indices:

        parent = index_to_project[
            int(index)
        ]

        output[
            parent
        ] = (
            float(
                fused[index]
            ),
            float(
                mean_regret[index]
            ),
            normalized_component_cost(
                modality,
                float(
                    fused[index]
                ),
                float(
                    mean_regret[index]
                ),
            ),
        )


    return output


def score_query_online(
    qid,
    allowed_parents=None,
):
    group = query_groups[
        qid
    ]

    parent_cost_lists = defaultdict(
        list
    )


    for row in group.itertuples(
        index=False
    ):

        values = component_parent_values(
            row,
            allowed_parents,
        )

        for parent, (
            _distance,
            _regret,
            cost,
        ) in values.items():

            parent_cost_lists[
                parent
            ].append(
                float(cost)
            )


    expected_component_count = len(
        group
    )


    result = {}


    candidate_parents = (
        projects
        if allowed_parents is None
        else sorted(
            allowed_parents
        )
    )


    for parent in candidate_parents:

        costs = parent_cost_lists[
            parent
        ]

        if len(costs) != expected_component_count:
            raise RuntimeError(
                f"{qid}/{parent}: "
                f"expected {expected_component_count} component costs, "
                f"got {len(costs)}"
            )

        costs = sorted(
            costs
        )

        result[
            parent
        ] = float(
            np.mean(
                costs[:3]
            )
        )


    ranked = sorted(
        candidate_parents,
        key=lambda parent: (
            result[parent],
            parent,
        ),
    )


    return (
        result,
        ranked[
            :CANDIDATE_POOL_M
        ],
    )


def lsh_shortlist(
    qid,
    config_name,
):
    config = CONFIGS[
        config_name
    ]

    lsh = lsh_indices[
        config_name
    ][
        "index"
    ]

    shortlist = set()


    for row in query_groups[
        qid
    ].itertuples(
        index=False
    ):

        modality = clean(
            row.modality
        )

        for column, bits in (
            REPRESENTATIONS[
                modality
            ]
        ):
            for band_id, band_value in split_bands(
                getattr(
                    row,
                    column,
                ),
                bits,
                config,
            ):
                shortlist.update(
                    lsh.get(
                        (
                            column,
                            band_id,
                            band_value,
                        ),
                        (),
                    )
                )


    return shortlist


# =========================================================
# Warm-up
# =========================================================

print()
print(
    "Warm-up..."
)

for qid in test_query_ids[
    :5
]:
    score_query_online(
        qid,
        None,
    )

    for config_name in CONFIGS:
        shortlist = lsh_shortlist(
            qid,
            config_name,
        )

        score_query_online(
            qid,
            shortlist,
        )

print(
    "Warm-up: PASS"
)


# =========================================================
# Exact runtime + frozen reproduction
# =========================================================

query_rows = []
backend_metrics = []


print()
print(
    "Running online EXACT..."
)


exact_latencies = []
exact_pools = {}


for q_index, qid in enumerate(
    test_query_ids,
    start=1,
):

    start = time.perf_counter_ns()

    _, pool = score_query_online(
        qid,
        None,
    )

    end = time.perf_counter_ns()

    latency_ms = (
        end - start
    ) / 1_000_000.0

    exact_latencies.append(
        latency_ms
    )

    exact_pools[
        qid
    ] = pool


    if pool != frozen_exact_pool[
        qid
    ]:
        raise RuntimeError(
            f"{qid}: online Exact Top-10 does not reproduce "
            f"frozen Phase7H candidate pool.\n"
            f"online={pool}\n"
            f"frozen={frozen_exact_pool[qid]}"
        )


    truth = true_known[
        qid
    ]

    if truth:
        recall = (
            len(
                truth
                &
                set(pool)
            )
            /
            len(truth)
        )

        all_present = bool(
            truth
            <=
            set(pool)
        )

    else:
        recall = None
        all_present = None


    query_rows.append({
        "backend":
            "EXACT",

        "query_id":
            qid,

        "scenario":
            scenario[qid],

        "shortlist_parent_count":
            60,

        "candidate_pool_count":
            len(pool),

        "known_true_parent_count":
            len(truth),

        "known_parent_recall":
            recall,

        "all_known_true_parents_present":
            all_present,

        "exact_top10_overlap":
            1.0,

        "exact_top10_identical":
            True,

        "search_ms":
            latency_ms,

        "candidate_pool":
            json.dumps(pool),
    })


    if q_index % 60 == 0:
        print(
            " exact query",
            q_index,
            "/",
            len(test_query_ids),
        )


print(
    "Online Exact frozen reproduction: PASS"
)


# =========================================================
# ANN online runtime
# =========================================================

for config_name in CONFIGS:

    print()
    print(
        "Running online",
        config_name,
        "..."
    )

    latencies = []
    shortlist_sizes = []

    recalls = []
    all_present_values = []

    overlaps = []
    identical_values = []

    under10 = 0
    empty = 0


    for q_index, qid in enumerate(
        test_query_ids,
        start=1,
    ):

        start = time.perf_counter_ns()

        shortlist = lsh_shortlist(
            qid,
            config_name,
        )


        if not shortlist:
            empty += 1

            # Deterministic safety fallback.
            #
            # This is not triggered in Phase12A but preserves
            # correctness of the implementation.
            shortlist = set(
                projects
            )


        _, pool = score_query_online(
            qid,
            shortlist,
        )

        end = time.perf_counter_ns()

        latency_ms = (
            end - start
        ) / 1_000_000.0


        latencies.append(
            latency_ms
        )

        shortlist_sizes.append(
            len(shortlist)
        )


        if len(pool) < CANDIDATE_POOL_M:
            under10 += 1


        exact_pool = exact_pools[
            qid
        ]


        overlap = (
            len(
                set(pool)
                &
                set(exact_pool)
            )
            /
            CANDIDATE_POOL_M
        )

        identical = bool(
            pool
            ==
            exact_pool
        )


        overlaps.append(
            overlap
        )

        identical_values.append(
            identical
        )


        truth = true_known[
            qid
        ]


        if truth:
            recall = (
                len(
                    truth
                    &
                    set(pool)
                )
                /
                len(truth)
            )

            all_present = bool(
                truth
                <=
                set(pool)
            )

            recalls.append(
                recall
            )

            all_present_values.append(
                all_present
            )

        else:
            recall = None
            all_present = None


        query_rows.append({
            "backend":
                config_name,

            "query_id":
                qid,

            "scenario":
                scenario[qid],

            "shortlist_parent_count":
                len(shortlist),

            "candidate_pool_count":
                len(pool),

            "known_true_parent_count":
                len(truth),

            "known_parent_recall":
                recall,

            "all_known_true_parents_present":
                all_present,

            "exact_top10_overlap":
                overlap,

            "exact_top10_identical":
                identical,

            "search_ms":
                latency_ms,

            "candidate_pool":
                json.dumps(pool),
        })


        if q_index % 60 == 0:
            print(
                " ",
                config_name,
                "query",
                q_index,
                "/",
                len(test_query_ids),
            )


    exact_p50 = percentile(
        exact_latencies,
        50,
    )

    exact_p95 = percentile(
        exact_latencies,
        95,
    )

    p50 = percentile(
        latencies,
        50,
    )

    p95 = percentile(
        latencies,
        95,
    )


    backend_metrics.append({
        "backend":
            config_name,

        "queries":
            360,

        "mean_shortlist_parents":
            float(
                np.mean(
                    shortlist_sizes
                )
            ),

        "median_shortlist_parents":
            float(
                np.median(
                    shortlist_sizes
                )
            ),

        "candidate_pool_under_10_queries":
            int(under10),

        "empty_shortlist_queries":
            int(empty),

        "mean_known_parent_recall":
            float(
                np.mean(
                    recalls
                )
            ),

        "all_known_true_parents_present_rate":
            float(
                np.mean(
                    all_present_values
                )
            ),

        "mean_exact_top10_overlap":
            float(
                np.mean(
                    overlaps
                )
            ),

        "exact_top10_identical_rate":
            float(
                np.mean(
                    identical_values
                )
            ),

        "search_mean_ms":
            float(
                np.mean(
                    latencies
                )
            ),

        "search_p50_ms":
            p50,

        "search_p95_ms":
            p95,

        "search_p99_ms":
            percentile(
                latencies,
                99,
            ),

        "speedup_p50_vs_exact":
            float(
                exact_p50 / p50
            ),

        "speedup_p95_vs_exact":
            float(
                exact_p95 / p95
            ),

        "index_build_ms":
            float(
                lsh_indices[
                    config_name
                ][
                    "build_ms"
                ]
            ),

        "index_keys":
            int(
                lsh_indices[
                    config_name
                ][
                    "keys"
                ]
            ),
    })


# Exact metric row

exact_known_recalls = []
exact_all_present = []

for qid in test_query_ids:
    truth = true_known[
        qid
    ]

    if not truth:
        continue

    pool = exact_pools[
        qid
    ]

    exact_known_recalls.append(
        len(
            truth
            &
            set(pool)
        )
        /
        len(truth)
    )

    exact_all_present.append(
        truth
        <=
        set(pool)
    )


exact_metric = {
    "backend":
        "EXACT",

    "queries":
        360,

    "mean_shortlist_parents":
        60.0,

    "median_shortlist_parents":
        60.0,

    "candidate_pool_under_10_queries":
        0,

    "empty_shortlist_queries":
        0,

    "mean_known_parent_recall":
        float(
            np.mean(
                exact_known_recalls
            )
        ),

    "all_known_true_parents_present_rate":
        float(
            np.mean(
                exact_all_present
            )
        ),

    "mean_exact_top10_overlap":
        1.0,

    "exact_top10_identical_rate":
        1.0,

    "search_mean_ms":
        float(
            np.mean(
                exact_latencies
            )
        ),

    "search_p50_ms":
        percentile(
            exact_latencies,
            50,
        ),

    "search_p95_ms":
        percentile(
            exact_latencies,
            95,
        ),

    "search_p99_ms":
        percentile(
            exact_latencies,
            99,
        ),

    "speedup_p50_vs_exact":
        1.0,

    "speedup_p95_vs_exact":
        1.0,

    "index_build_ms":
        0.0,

    "index_keys":
        0,
}


metrics_df = pd.DataFrame(
    [
        exact_metric,
        *backend_metrics,
    ]
)


query_df = pd.DataFrame(
    query_rows
)


metrics_df.to_csv(
    OUT_METRICS,
    index=False,
)

query_df.to_csv(
    OUT_QUERY,
    index=False,
)


summary = {
    "phase12c_complete":
        True,

    "scope":
        "ONLINE_DISTANCE_COMPUTATION_EXACT_VS_BINARY_LSH",

    "frozen_method_modified":
        False,

    "phase7_parameters_retuned":
        False,

    "test_used_for_ann_parameter_selection":
        False,

    "online_exact_reproduces_frozen_phase7h_top10":
        True,

    "benchmark": {
        "gallery_projects":
            60,

        "gallery_components":
            int(
                len(gallery)
            ),

        "test_queries":
            360,

        "test_components":
            2520,
    },

    "important_methodological_note": {
        "exact":
            "Computes frozen component-to-parent distances over the complete 60-project TEST gallery.",

        "ann":
            "LSH first generates a registered-parent shortlist; exact frozen hash/histogram distances are then recomputed only for gallery components belonging to shortlisted parents.",

        "ann_regret_reference":
            "MEAN_REGRET is recomputed within the ANN-visible parent shortlist. Therefore Phase12C is the deployable online approximation rather than the precomputed-score fidelity condition used in Phase12A/B.",

        "phase12a_b_distinction":
            "Phase12A/B isolated candidate-generation effects by reranking with previously frozen exact Phase7 scores. Phase12C includes the actual online distance computation and shortlist-local regret required by an ANN deployment.",
    },

    "metrics":
        {
            row[
                "backend"
            ]: row

            for row
            in [
                exact_metric,
                *backend_metrics,
            ]
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
print(
    "=========================================="
)
print(
    "Phase 12C COMPLETE"
)
print(
    "=========================================="
)
print()
print(
    metrics_df.to_string(
        index=False
    )
)
print()
print(
    "Wrote:",
    OUT_QUERY,
)
print(
    "Wrote:",
    OUT_METRICS,
)
print(
    "Wrote:",
    OUT_SUMMARY,
)
