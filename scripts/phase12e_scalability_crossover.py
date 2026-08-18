#!/usr/bin/env python3

import gc
import json
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

OUT_METRICS = ROOT / "results/phase12e_scalability_crossover_metrics.csv"
OUT_QUERIES = ROOT / "results/phase12e_scalability_crossover_queries.csv"
OUT_SAMPLE = ROOT / "results/phase12e_scalability_query_sample.csv"
OUT_SUMMARY = ROOT / "results/phase12e_scalability_crossover_summary.json"

SEED = 20260818
QUERIES_PER_SCENARIO = 20
M = 10

THRESHOLDS = {
    "CODE_BINARY": 0.1302083283662796,
    "STRUCTURED": 0.03125,
    "IMAGE": 0.0,
}

ALPHA = 0.75
REGRET_WEIGHT = 0.25
MISSING_PARENT_DISTANCE = 1.0

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


def pct(values, q):
    values = np.asarray(values, dtype=np.float64)

    if not len(values):
        return None

    return float(
        np.percentile(values, q)
    )


def parse128(value):
    text = clean(value)

    if not text:
        return None

    integer = int(text, 16)

    return (
        np.uint64(
            (integer >> 64)
            &
            ((1 << 64) - 1)
        ),
        np.uint64(
            integer
            &
            ((1 << 64) - 1)
        ),
    )


def parse64(value):
    text = clean(value)

    if not text:
        return None

    return np.uint64(
        int(text, 16)
        &
        ((1 << 64) - 1)
    )


def parse_hist(value):
    parts = [
        x.strip()
        for x in clean(value).split(",")
    ]

    if len(parts) != 16:
        raise RuntimeError(
            f"Expected 16 histogram bins, got {len(parts)}"
        )

    return np.asarray(
        [int(x) for x in parts],
        dtype=np.float32,
    )


def popcount64(values):
    values = np.ascontiguousarray(
        values,
        dtype=np.uint64,
    )

    raw = values.view(
        np.uint8
    ).reshape(-1, 8)

    return (
        POPCOUNT[raw]
        .sum(axis=1)
        .astype(np.float32)
    )


def hamming64(values, query_value):
    return (
        popcount64(
            np.bitwise_xor(
                values,
                np.uint64(query_value),
            )
        )
        /
        64.0
    ).astype(np.float32)


def hamming128(
    highs,
    lows,
    q_high,
    q_low,
):
    return (
        (
            popcount64(
                np.bitwise_xor(
                    highs,
                    np.uint64(q_high),
                )
            )
            +
            popcount64(
                np.bitwise_xor(
                    lows,
                    np.uint64(q_low),
                )
            )
        )
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

    return [
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
        for band_id
        in range(band_count)
    ]


def normalized_cost(
    modality,
    distance,
    regret,
):
    threshold = THRESHOLDS[
        modality
    ]

    if threshold > 0:
        normalized_distance = min(
            float(distance)
            /
            threshold,
            1.0,
        )
    else:
        normalized_distance = (
            0.0
            if abs(float(distance)) <= 1e-12
            else 1.0
        )

    normalized_regret = min(
        max(
            float(regret),
            0.0,
        ),
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


def parent_minimum(
    distances,
    parent_indices,
    parent_count,
):
    output = np.full(
        parent_count,
        np.inf,
        dtype=np.float32,
    )

    if len(distances):
        np.minimum.at(
            output,
            parent_indices,
            distances,
        )

    output[
        ~np.isfinite(output)
    ] = MISSING_PARENT_DISTANCE

    return output


def build128(
    frame,
    column,
    p2i,
):
    highs = []
    lows = []
    parents = []

    for row in frame.itertuples(
        index=False
    ):
        parsed = parse128(
            getattr(row, column)
        )

        if parsed is None:
            continue

        highs.append(parsed[0])
        lows.append(parsed[1])
        parents.append(
            p2i[
                clean(row.fresh_id)
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
    p2i,
):
    values = []
    parents = []

    for row in frame.itertuples(
        index=False
    ):
        parsed = parse64(
            getattr(row, column)
        )

        if parsed is None:
            continue

        values.append(parsed)
        parents.append(
            p2i[
                clean(row.fresh_id)
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


def apply_multiplier(
    rep,
    multiplier,
):
    if multiplier == 1:
        return

    for key in list(rep.keys()):
        if key == "by_parent":
            continue

        array = rep[key]

        if array.ndim == 1:
            rep[key] = np.tile(
                array,
                multiplier,
            )
        else:
            rep[key] = np.tile(
                array,
                (multiplier, 1),
            )


def add_parent_lookup(
    rep,
    parent_count,
):
    rep["by_parent"] = {
        parent_index:
            np.where(
                rep["parent"]
                ==
                parent_index
            )[0]

        for parent_index
        in range(parent_count)
    }


def build_state(
    base_frame,
    multiplier,
):
    projects = sorted(
        base_frame[
            "fresh_id"
        ]
        .astype(str)
        .unique()
        .tolist()
    )

    p2i = {
        parent: index
        for index, parent
        in enumerate(projects)
    }

    i2p = {
        index: parent
        for parent, index
        in p2i.items()
    }

    code = base_frame[
        base_frame["modality"].astype(str)
        == "CODE_BINARY"
    ]

    struct = base_frame[
        base_frame["modality"].astype(str)
        == "STRUCTURED"
    ]

    image = base_frame[
        base_frame["modality"].astype(str)
        == "IMAGE"
    ]

    state = {
        "projects": projects,
        "p2i": p2i,
        "i2p": i2p,
        "code_op3":
            build128(
                code,
                "code_op3_simhash128",
                p2i,
            ),
        "code_struct":
            build128(
                code,
                "code_struct_simhash128",
                p2i,
            ),
        "code_context":
            build128(
                code,
                "code_context_simhash128",
                p2i,
            ),
        "structured":
            build128(
                struct,
                "structured_simhash128",
                p2i,
            ),
        "image_ahash":
            build64(
                image,
                "image_ahash64",
                p2i,
            ),
        "image_dhash":
            build64(
                image,
                "image_dhash64",
                p2i,
            ),
        "image_phash":
            build64(
                image,
                "image_phash64",
                p2i,
            ),
    }

    hist_values = []
    hist_parents = []

    for row in image.itertuples(
        index=False
    ):
        text = clean(
            row.image_hist16
        )

        if not text:
            continue

        hist_values.append(
            parse_hist(text)
        )

        hist_parents.append(
            p2i[
                clean(row.fresh_id)
            ]
        )

    state["image_hist"] = {
        "value":
            np.asarray(
                hist_values,
                dtype=np.float32,
            ),
        "parent":
            np.asarray(
                hist_parents,
                dtype=np.int32,
            ),
    }

    rep_names = [
        "code_op3",
        "code_struct",
        "code_context",
        "structured",
        "image_ahash",
        "image_dhash",
        "image_phash",
        "image_hist",
    ]

    for name in rep_names:
        apply_multiplier(
            state[name],
            multiplier,
        )

        add_parent_lookup(
            state[name],
            len(projects),
        )

    numeric_bytes = 0

    for name in rep_names:
        for key, value in state[name].items():
            if (
                key != "by_parent"
                and
                isinstance(
                    value,
                    np.ndarray,
                )
            ):
                numeric_bytes += int(
                    value.nbytes
                )

    state[
        "numeric_array_bytes"
    ] = numeric_bytes

    return state


def subset_indices(
    rep,
    allowed_indices,
):
    chunks = [
        rep["by_parent"][index]
        for index in allowed_indices
        if len(
            rep["by_parent"][index]
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


def pmin128(
    rep,
    query_sig,
    state,
    allowed_indices,
):
    if allowed_indices is None:
        highs = rep["high"]
        lows = rep["low"]
        parents = rep["parent"]

    else:
        indices = subset_indices(
            rep,
            allowed_indices,
        )

        highs = rep["high"][indices]
        lows = rep["low"][indices]
        parents = rep["parent"][indices]

    distances = hamming128(
        highs,
        lows,
        query_sig[0],
        query_sig[1],
    )

    return parent_minimum(
        distances,
        parents,
        len(state["projects"]),
    )


def pmin64(
    rep,
    query_sig,
    state,
    allowed_indices,
):
    if allowed_indices is None:
        values = rep["value"]
        parents = rep["parent"]

    else:
        indices = subset_indices(
            rep,
            allowed_indices,
        )

        values = rep["value"][indices]
        parents = rep["parent"][indices]

    distances = hamming64(
        values,
        query_sig,
    )

    return parent_minimum(
        distances,
        parents,
        len(state["projects"]),
    )


def pmin_hist(
    rep,
    q_hist,
    state,
    allowed_indices,
):
    if allowed_indices is None:
        values = rep["value"]
        parents = rep["parent"]

    else:
        indices = subset_indices(
            rep,
            allowed_indices,
        )

        values = rep["value"][indices]
        parents = rep["parent"][indices]

    if len(values):
        distances = (
            np.abs(
                values
                -
                q_hist[None, :]
            )
            .sum(axis=1)
            /
            20000.0
        ).astype(np.float32)

        distances = np.clip(
            distances,
            0.0,
            1.0,
        )
    else:
        distances = np.empty(
            0,
            dtype=np.float32,
        )

    return parent_minimum(
        distances,
        parents,
        len(state["projects"]),
    )


def component_costs(
    row,
    state,
    allowed_parents=None,
):
    modality = clean(
        row.modality
    )

    if allowed_parents is None:
        visible_indices = np.arange(
            len(state["projects"]),
            dtype=np.int32,
        )

        allowed_indices = None

    else:
        allowed_indices = sorted(
            state["p2i"][parent]
            for parent
            in allowed_parents
        )

        visible_indices = np.asarray(
            allowed_indices,
            dtype=np.int32,
        )

    vectors = []

    if modality == "CODE_BINARY":

        parsed = parse128(
            row.code_op3_simhash128
        )

        if parsed is not None:
            vectors.append(
                pmin128(
                    state["code_op3"],
                    parsed,
                    state,
                    allowed_indices,
                )
            )

        parsed = parse128(
            row.code_struct_simhash128
        )

        if parsed is not None:
            vectors.append(
                pmin128(
                    state["code_struct"],
                    parsed,
                    state,
                    allowed_indices,
                )
            )

        parsed = parse128(
            row.code_context_simhash128
        )

        if parsed is not None:
            vectors.append(
                pmin128(
                    state["code_context"],
                    parsed,
                    state,
                    allowed_indices,
                )
            )

    elif modality == "STRUCTURED":

        parsed = parse128(
            row.structured_simhash128
        )

        if parsed is None:
            raise RuntimeError(
                "Missing structured signature"
            )

        vectors.append(
            pmin128(
                state["structured"],
                parsed,
                state,
                allowed_indices,
            )
        )

    elif modality == "IMAGE":

        vectors.extend([
            pmin64(
                state["image_ahash"],
                parse64(
                    row.image_ahash64
                ),
                state,
                allowed_indices,
            ),
            pmin64(
                state["image_dhash"],
                parse64(
                    row.image_dhash64
                ),
                state,
                allowed_indices,
            ),
            pmin64(
                state["image_phash"],
                parse64(
                    row.image_phash64
                ),
                state,
                allowed_indices,
            ),
            pmin_hist(
                state["image_hist"],
                parse_hist(
                    row.image_hist16
                ),
                state,
                allowed_indices,
            ),
        ])

    else:
        raise RuntimeError(
            f"Unsupported modality: {modality}"
        )

    matrix = np.vstack(
        vectors
    )

    fused = matrix.mean(
        axis=0
    )

    regret = np.zeros_like(
        matrix,
        dtype=np.float32,
    )

    for rep_index in range(
        matrix.shape[0]
    ):
        minimum = float(
            matrix[
                rep_index,
                visible_indices,
            ].min()
        )

        regret[
            rep_index
        ] = (
            matrix[
                rep_index
            ]
            -
            minimum
        )

    mean_regret = regret.mean(
        axis=0
    )

    output = {}

    for index in visible_indices:

        parent = state["i2p"][
            int(index)
        ]

        output[parent] = normalized_cost(
            modality,
            fused[index],
            mean_regret[index],
        )

    return output


def score_query(
    group,
    state,
    allowed_parents=None,
):
    costs_by_parent = defaultdict(
        list
    )

    for row in group.itertuples(
        index=False
    ):
        values = component_costs(
            row,
            state,
            allowed_parents,
        )

        for parent, cost in values.items():
            costs_by_parent[parent].append(
                float(cost)
            )

    if allowed_parents is None:
        parents = state["projects"]
    else:
        parents = sorted(
            allowed_parents
        )

    scores = {}

    for parent in parents:
        values = sorted(
            costs_by_parent[parent]
        )

        if len(values) != 7:
            raise RuntimeError(
                f"{parent}: expected 7 component costs, "
                f"got {len(values)}"
            )

        scores[parent] = float(
            np.mean(
                values[:3]
            )
        )

    ranked = sorted(
        parents,
        key=lambda parent: (
            scores[parent],
            parent,
        ),
    )

    return ranked[:M]


def build_lsh_indices(
    base_frame,
):
    output = {}

    for config_name, config in CONFIGS.items():

        start = time.perf_counter_ns()

        index = defaultdict(set)

        raw_insertions = 0

        for row in base_frame.itertuples(
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
                    index[
                        (
                            column,
                            band_id,
                            band_value,
                        )
                    ].add(
                        parent
                    )

                    raw_insertions += 1

        end = time.perf_counter_ns()

        unique_parent_postings = sum(
            len(value)
            for value
            in index.values()
        )

        output[config_name] = {
            "index":
                index,
            "build_ms":
                (
                    end - start
                )
                /
                1_000_000.0,
            "keys":
                len(index),
            "raw_insertions":
                raw_insertions,
            "unique_parent_postings":
                unique_parent_postings,
        }

    return output


def lsh_shortlist(
    group,
    config_name,
    lsh_indices,
):
    config = CONFIGS[
        config_name
    ]

    index = lsh_indices[
        config_name
    ]["index"]

    shortlist = set()

    for row in group.itertuples(
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
                    index.get(
                        (
                            column,
                            band_id,
                            band_value,
                        ),
                        (),
                    )
                )

    return shortlist


for path in [
    GALLERY_FILE,
    QUERY_FILE,
    FINAL_QUERY_FILE,
    FROZEN_AUDIT_FILE,
]:
    if not path.exists():
        raise FileNotFoundError(path)


print(
    "============================================"
)
print(
    "Phase 12E - Scalability Crossover Benchmark"
)
print(
    "============================================"
)


gallery_all = pd.read_csv(
    GALLERY_FILE
)

query_all = pd.read_csv(
    QUERY_FILE
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


if gallery_all["fresh_id"].nunique() != 100:
    raise RuntimeError(
        "Expected 100 real frozen gallery projects"
    )


test_frame = gallery_all[
    gallery_all[
        "frozen_split"
    ].astype(str).isin(
        [
            "TEST_KNOWN",
            "TEST_BACKGROUND",
        ]
    )
].copy()


test_projects = sorted(
    test_frame[
        "fresh_id"
    ].astype(str).unique()
)


cal_frame = gallery_all[
    gallery_all[
        "frozen_split"
    ].astype(str).isin(
        [
            "CALIBRATION_KNOWN",
            "CALIBRATION_BACKGROUND",
        ]
    )
].copy()


cal_projects = sorted(
    cal_frame[
        "fresh_id"
    ].astype(str).unique()
)


if len(test_projects) != 60:
    raise RuntimeError(
        "Expected exact 60-project TEST gallery"
    )

if len(cal_projects) != 40:
    raise RuntimeError(
        "Expected 40 calibration projects"
    )


# =========================================================
# Deterministic nested real-gallery project sets
# =========================================================

rng_projects = np.random.default_rng(
    SEED
)

test_order = list(
    rng_projects.permutation(
        np.asarray(
            test_projects,
            dtype=object,
        )
    )
)

cal_order = list(
    rng_projects.permutation(
        np.asarray(
            cal_projects,
            dtype=object,
        )
    )
)


real_sets = {
    20:
        set(test_order[:20]),

    40:
        set(test_order[:40]),

    # Critical: exact frozen Phase7H universe.
    60:
        set(test_projects),

    80:
        set(test_projects)
        |
        set(cal_order[:20]),

    100:
        set(
            gallery_all[
                "fresh_id"
            ].astype(str).unique()
        ),
}


# =========================================================
# Stratified fixed 120-query runtime sample
# =========================================================

scenario_values = sorted(
    final_query[
        "scenario"
    ].astype(str).unique()
)


if len(scenario_values) != 6:
    raise RuntimeError(
        f"Expected 6 TEST scenarios, got {scenario_values}"
    )


rng_queries = np.random.default_rng(
    SEED
)

sample_ids = []

sample_rows = []


for scenario in scenario_values:

    ids = sorted(
        final_query[
            final_query[
                "scenario"
            ].astype(str)
            ==
            scenario
        ][
            "query_id"
        ]
        .astype(str)
        .tolist()
    )

    if len(ids) != 60:
        raise RuntimeError(
            f"{scenario}: expected 60 queries"
        )

    chosen = sorted(
        rng_queries.choice(
            np.asarray(
                ids,
                dtype=object,
            ),
            size=QUERIES_PER_SCENARIO,
            replace=False,
        ).tolist()
    )

    sample_ids.extend(
        chosen
    )

    for qid in chosen:
        sample_rows.append({
            "scenario":
                scenario,
            "query_id":
                qid,
        })


sample_ids = sorted(
    sample_ids
)


if len(sample_ids) != 120:
    raise RuntimeError(
        "Expected 120 sampled queries"
    )


pd.DataFrame(
    sample_rows
).to_csv(
    OUT_SAMPLE,
    index=False,
)


query_sample = query_all[
    query_all[
        "query_id"
    ].astype(str).isin(
        sample_ids
    )
].copy()


if len(query_sample) != 120 * 7:
    raise RuntimeError(
        "Expected 840 sampled query components"
    )


query_groups = {
    str(qid):
        group.sort_values(
            "node_id"
        ).copy()

    for qid, group
    in query_sample.groupby(
        "query_id"
    )
}


# Frozen Phase7H pools for scale-60 assertion.
frozen_pools = {
    clean(row.query_id):
        json.loads(
            clean(row.candidate_pool)
        )

    for row
    in frozen_audit.itertuples(
        index=False
    )
}


# =========================================================
# Scales
#
# 20-100 = real unique projects.
#
# 200/500/1000 = same 100 real registered parents;
# component arrays duplicated 2x/5x/10x.
#
# They are NOT additional unique projects.
# =========================================================

scale_specs = [
    {
        "label": "20",
        "type": "REAL",
        "real_project_count": 20,
        "multiplier": 1,
    },
    {
        "label": "40",
        "type": "REAL",
        "real_project_count": 40,
        "multiplier": 1,
    },
    {
        "label": "60",
        "type": "REAL_FROZEN_TEST",
        "real_project_count": 60,
        "multiplier": 1,
    },
    {
        "label": "80",
        "type": "REAL",
        "real_project_count": 80,
        "multiplier": 1,
    },
    {
        "label": "100",
        "type": "REAL",
        "real_project_count": 100,
        "multiplier": 1,
    },
    {
        "label": "200eq",
        "type": "SYNTHETIC_COMPONENT_VOLUME",
        "real_project_count": 100,
        "multiplier": 2,
    },
    {
        "label": "500eq",
        "type": "SYNTHETIC_COMPONENT_VOLUME",
        "real_project_count": 100,
        "multiplier": 5,
    },
    {
        "label": "1000eq",
        "type": "SYNTHETIC_COMPONENT_VOLUME",
        "real_project_count": 100,
        "multiplier": 10,
    },
]


metric_rows = []
query_rows = []


for scale_index, spec in enumerate(
    scale_specs,
    start=1,
):

    print()
    print(
        "============================================"
    )
    print(
        f"Scale {spec['label']} "
        f"({spec['type']}) "
        f"[{scale_index}/{len(scale_specs)}]"
    )
    print(
        "============================================"
    )


    if spec[
        "real_project_count"
    ] <= 100:

        project_set = (
            real_sets[
                spec[
                    "real_project_count"
                ]
            ]
            if spec[
                "real_project_count"
            ]
            in real_sets
            else real_sets[100]
        )


    base_frame = gallery_all[
        gallery_all[
            "fresh_id"
        ]
        .astype(str)
        .isin(
            project_set
        )
    ].copy()


    if (
        base_frame[
            "fresh_id"
        ].nunique()
        !=
        spec[
            "real_project_count"
        ]
    ):
        raise RuntimeError(
            f"Scale {spec['label']}: parent count mismatch"
        )


    # Critical frozen-TEST integrity check.
    if spec["label"] == "60":

        actual = set(
            base_frame[
                "fresh_id"
            ].astype(str).unique()
        )

        if actual != set(
            test_projects
        ):
            raise RuntimeError(
                "Scale 60 is not exact frozen TEST gallery"
            )


    gc.collect()

    state_start = time.perf_counter_ns()

    state = build_state(
        base_frame,
        spec[
            "multiplier"
        ],
    )

    state_end = time.perf_counter_ns()


    lsh_indices = build_lsh_indices(
        base_frame
    )


    effective_components = (
        len(base_frame)
        *
        spec[
            "multiplier"
        ]
    )


    print(
        "unique registered parents =",
        len(
            state[
                "projects"
            ]
        ),
    )

    print(
        "base real components       =",
        len(base_frame),
    )

    print(
        "component multiplier       =",
        spec[
            "multiplier"
        ],
    )

    print(
        "effective components       =",
        effective_components,
    )

    print(
        "numeric arrays MB          =",
        round(
            state[
                "numeric_array_bytes"
            ]
            /
            (1024 ** 2),
            3,
        ),
    )


    # -----------------------------------------------------
    # Warmup
    # -----------------------------------------------------

    warmup_ids = sample_ids[:3]

    for qid in warmup_ids:

        score_query(
            query_groups[qid],
            state,
            None,
        )

        for config_name in CONFIGS:

            shortlist = lsh_shortlist(
                query_groups[qid],
                config_name,
                lsh_indices,
            )

            if not shortlist:
                shortlist = set(
                    state[
                        "projects"
                    ]
                )

            score_query(
                query_groups[qid],
                state,
                shortlist,
            )


    # -----------------------------------------------------
    # Exact benchmark first
    # -----------------------------------------------------

    print(
        "Running EXACT..."
    )


    exact_times = []
    exact_pools = {}


    exact_wall_start = time.perf_counter_ns()


    for index, qid in enumerate(
        sample_ids,
        start=1,
    ):

        begin = time.perf_counter_ns()

        pool = score_query(
            query_groups[qid],
            state,
            None,
        )

        finish = time.perf_counter_ns()

        latency = (
            finish - begin
        ) / 1_000_000.0

        exact_times.append(
            latency
        )

        exact_pools[
            qid
        ] = pool


        if spec["label"] == "60":

            if (
                pool
                !=
                frozen_pools[qid]
            ):
                raise RuntimeError(
                    f"Scale60 Exact reproduction failed for {qid}"
                )


        query_rows.append({
            "scale":
                spec["label"],
            "scale_type":
                spec["type"],
            "backend":
                "EXACT",
            "query_id":
                qid,
            "unique_registered_parents":
                len(
                    state[
                        "projects"
                    ]
                ),
            "effective_gallery_components":
                effective_components,
            "shortlist_parent_count":
                len(
                    state[
                        "projects"
                    ]
                ),
            "search_ms":
                latency,
            "candidate_pool":
                json.dumps(pool),
            "exact_top10_overlap":
                1.0,
            "exact_top10_identical":
                True,
        })


        if index % 40 == 0:
            print(
                " exact",
                index,
                "/",
                len(sample_ids),
            )


    exact_wall_end = time.perf_counter_ns()

    exact_wall_seconds = (
        exact_wall_end
        -
        exact_wall_start
    ) / 1_000_000_000.0


    exact_p50 = pct(
        exact_times,
        50,
    )

    exact_p95 = pct(
        exact_times,
        95,
    )


    metric_rows.append({
        "scale":
            spec["label"],
        "scale_type":
            spec["type"],
        "backend":
            "EXACT",
        "queries":
            len(sample_ids),
        "unique_registered_parents":
            len(
                state[
                    "projects"
                ]
            ),
        "base_real_components":
            len(base_frame),
        "component_multiplier":
            spec["multiplier"],
        "effective_gallery_components":
            effective_components,
        "mean_shortlist_parents":
            float(
                len(
                    state[
                        "projects"
                    ]
                )
            ),
        "shortlist_fraction":
            1.0,
        "mean_exact_top10_overlap":
            1.0,
        "exact_top10_identical_rate":
            1.0,
        "search_mean_ms":
            float(
                np.mean(
                    exact_times
                )
            ),
        "search_p50_ms":
            exact_p50,
        "search_p95_ms":
            exact_p95,
        "search_p99_ms":
            pct(
                exact_times,
                99,
            ),
        "throughput_qps":
            float(
                len(sample_ids)
                /
                exact_wall_seconds
            ),
        "speedup_p50_vs_exact":
            1.0,
        "speedup_p95_vs_exact":
            1.0,
        "state_build_ms":
            (
                state_end
                -
                state_start
            )
            /
            1_000_000.0,
        "lsh_index_build_ms":
            0.0,
        "lsh_index_keys":
            0,
        "lsh_unique_parent_postings":
            0,
        "numeric_array_mb":
            state[
                "numeric_array_bytes"
            ]
            /
            (1024 ** 2),
    })


    if spec["label"] == "60":
        print(
            "Scale60 Exact frozen reproduction: PASS"
        )


    # -----------------------------------------------------
    # ANN backends
    # -----------------------------------------------------

    for config_name in CONFIGS:

        print(
            f"Running {config_name}..."
        )


        times = []
        shortlist_sizes = []
        overlaps = []
        identical = []

        empty_before_fallback = 0
        under10 = 0


        wall_start = time.perf_counter_ns()


        for index, qid in enumerate(
            sample_ids,
            start=1,
        ):

            begin = time.perf_counter_ns()

            shortlist = lsh_shortlist(
                query_groups[qid],
                config_name,
                lsh_indices,
            )

            original_shortlist_size = len(
                shortlist
            )

            if not shortlist:

                empty_before_fallback += 1

                shortlist = set(
                    state[
                        "projects"
                    ]
                )


            pool = score_query(
                query_groups[qid],
                state,
                shortlist,
            )


            finish = time.perf_counter_ns()

            latency = (
                finish - begin
            ) / 1_000_000.0


            times.append(
                latency
            )

            shortlist_sizes.append(
                len(shortlist)
            )


            if len(pool) < M:
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
                M
            )

            is_identical = bool(
                pool
                ==
                exact_pool
            )

            overlaps.append(
                overlap
            )

            identical.append(
                is_identical
            )


            query_rows.append({
                "scale":
                    spec["label"],
                "scale_type":
                    spec["type"],
                "backend":
                    config_name,
                "query_id":
                    qid,
                "unique_registered_parents":
                    len(
                        state[
                            "projects"
                        ]
                    ),
                "effective_gallery_components":
                    effective_components,
                "shortlist_parent_count":
                    len(shortlist),
                "shortlist_parent_count_before_fallback":
                    original_shortlist_size,
                "search_ms":
                    latency,
                "candidate_pool":
                    json.dumps(pool),
                "exact_top10_overlap":
                    overlap,
                "exact_top10_identical":
                    is_identical,
            })


            if index % 40 == 0:
                print(
                    " ",
                    config_name,
                    index,
                    "/",
                    len(sample_ids),
                )


        wall_end = time.perf_counter_ns()

        wall_seconds = (
            wall_end
            -
            wall_start
        ) / 1_000_000_000.0


        p50 = pct(
            times,
            50,
        )

        p95 = pct(
            times,
            95,
        )


        lsh_meta = lsh_indices[
            config_name
        ]


        metric_rows.append({
            "scale":
                spec["label"],
            "scale_type":
                spec["type"],
            "backend":
                config_name,
            "queries":
                len(sample_ids),
            "unique_registered_parents":
                len(
                    state[
                        "projects"
                    ]
                ),
            "base_real_components":
                len(base_frame),
            "component_multiplier":
                spec[
                    "multiplier"
                ],
            "effective_gallery_components":
                effective_components,
            "mean_shortlist_parents":
                float(
                    np.mean(
                        shortlist_sizes
                    )
                ),
            "shortlist_fraction":
                float(
                    np.mean(
                        shortlist_sizes
                    )
                    /
                    len(
                        state[
                            "projects"
                        ]
                    )
                ),
            "candidate_pool_under_10_queries":
                int(
                    under10
                ),
            "empty_shortlist_before_fallback":
                int(
                    empty_before_fallback
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
                        identical
                    )
                ),
            "search_mean_ms":
                float(
                    np.mean(
                        times
                    )
                ),
            "search_p50_ms":
                p50,
            "search_p95_ms":
                p95,
            "search_p99_ms":
                pct(
                    times,
                    99,
                ),
            "throughput_qps":
                float(
                    len(sample_ids)
                    /
                    wall_seconds
                ),
            "speedup_p50_vs_exact":
                float(
                    exact_p50
                    /
                    p50
                ),
            "speedup_p95_vs_exact":
                float(
                    exact_p95
                    /
                    p95
                ),
            "state_build_ms":
                (
                    state_end
                    -
                    state_start
                )
                /
                1_000_000.0,
            "lsh_index_build_ms":
                lsh_meta[
                    "build_ms"
                ],
            "lsh_index_keys":
                lsh_meta[
                    "keys"
                ],
            "lsh_unique_parent_postings":
                lsh_meta[
                    "unique_parent_postings"
                ],
            "numeric_array_mb":
                state[
                    "numeric_array_bytes"
                ]
                /
                (1024 ** 2),
        })


    del state
    del lsh_indices
    gc.collect()


metrics_df = pd.DataFrame(
    metric_rows
)

queries_df = pd.DataFrame(
    query_rows
)


metrics_df.to_csv(
    OUT_METRICS,
    index=False,
)

queries_df.to_csv(
    OUT_QUERIES,
    index=False,
)


# =========================================================
# Automatic crossover reporting
# =========================================================

crossover = {}


for backend in [
    "FAST",
    "BALANCED",
    "HIGH_RECALL",
]:

    rows = metrics_df[
        metrics_df[
            "backend"
        ]
        ==
        backend
    ].copy()

    faster = rows[
        rows[
            "speedup_p50_vs_exact"
        ].astype(float)
        >
        1.0
    ]

    if len(faster):

        first = faster.iloc[0]

        crossover[
            backend
        ] = {
            "first_observed_p50_faster_scale":
                clean(
                    first[
                        "scale"
                    ]
                ),
            "scale_type":
                clean(
                    first[
                        "scale_type"
                    ]
                ),
            "speedup_p50":
                float(
                    first[
                        "speedup_p50_vs_exact"
                    ]
                ),
        }

    else:

        crossover[
            backend
        ] = {
            "first_observed_p50_faster_scale":
                None,
            "scale_type":
                None,
            "speedup_p50":
                None,
        }


summary = {
    "phase12e_complete":
        True,

    "scope":
        "RETRIEVAL_SCALABILITY_CROSSOVER",

    "phase7_parameters_retuned":
        False,

    "test_used_for_parameter_selection":
        False,

    "query_sampling": {
        "seed":
            SEED,
        "strategy":
            "20 deterministic random TEST queries from each of six frozen scenarios",
        "queries_total":
            len(sample_ids),
    },

    "real_scales": [
        20,
        40,
        60,
        80,
        100,
    ],

    "synthetic_component_volume_scales": {
        "200eq":
            "100 real registered parents with exact gallery component arrays duplicated 2x",
        "500eq":
            "100 real registered parents with exact gallery component arrays duplicated 5x",
        "1000eq":
            "100 real registered parents with exact gallery component arrays duplicated 10x",
    },

    "synthetic_scope_warning":
        "200eq/500eq/1000eq are computational component-volume stress tests, not evaluations on 200/500/1000 unique real MOD projects.",

    "synthetic_lsh_note":
        "Exact duplicate components do not create new parent-band memberships, so the LSH bucket directory is built from the 100 real-project gallery while exact reranking arrays are duplicated by the stated multiplier.",

    "scale60_integrity": {
        "exact_frozen_test_parent_universe":
            True,
        "sampled_query_exact_top10_reproduction":
            True,
    },

    "p50_crossover":
        crossover,

    "metrics":
        metrics_df.to_dict(
            orient="records"
        ),
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
    "============================================"
)
print(
    "Phase 12E COMPLETE"
)
print(
    "============================================"
)

display_cols = [
    "scale",
    "scale_type",
    "backend",
    "unique_registered_parents",
    "effective_gallery_components",
    "mean_shortlist_parents",
    "search_p50_ms",
    "search_p95_ms",
    "throughput_qps",
    "speedup_p50_vs_exact",
    "mean_exact_top10_overlap",
    "exact_top10_identical_rate",
]

print()
print(
    metrics_df[
        display_cols
    ].to_string(
        index=False
    )
)

print()
print(
    "P50 crossover:"
)
print(
    json.dumps(
        crossover,
        indent=2,
        ensure_ascii=False,
    )
)

print()
print(
    "Wrote:",
    OUT_METRICS,
)
print(
    "Wrote:",
    OUT_QUERIES,
)
print(
    "Wrote:",
    OUT_SAMPLE,
)
print(
    "Wrote:",
    OUT_SUMMARY,
)
