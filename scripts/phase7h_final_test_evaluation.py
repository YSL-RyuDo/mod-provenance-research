import hashlib
import json
import math
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd


# =========================================================
# Inputs
# =========================================================

GALLERY_EVIDENCE_CSV = Path(
    "results/phase7b_gallery_identity_neutral_evidence.csv"
)

QUERY_EVIDENCE_CSV = Path(
    "results/phase7b_query_identity_neutral_evidence.csv"
)

PRIVATE_MANIFEST_CSV = Path(
    "results/phase6l_materialized_private_manifest.csv"
)

QUERY_GT_CSV = Path(
    "results/phase6k_query_ground_truth.csv"
)

STRESS_GRAPH_CSV = Path(
    "results/phase6l_graph_connected_stress_public.csv"
)

FINAL_PARAMETERS_JSON = Path(
    "results/phase7g_final_method_parameters.json"
)

FINAL_FREEZE_SUMMARY_JSON = Path(
    "results/phase7g_final_method_freeze_summary.json"
)


# =========================================================
# Outputs
# =========================================================

OUTPUT_SCORE_CSV = Path(
    "results/phase7h_test_component_parent_scores.csv"
)

OUTPUT_FINAL_COMPONENT_CSV = Path(
    "results/phase7h_final_component_predictions.csv"
)

OUTPUT_FINAL_QUERY_CSV = Path(
    "results/phase7h_final_query_predictions.csv"
)

OUTPUT_BETA0_COMPONENT_CSV = Path(
    "results/phase7h_beta0_component_predictions.csv"
)

OUTPUT_BETA0_QUERY_CSV = Path(
    "results/phase7h_beta0_query_predictions.csv"
)

OUTPUT_RETRIEVAL_CSV = Path(
    "results/phase7h_test_candidate_retrieval_audit.csv"
)

OUTPUT_SUMMARY_JSON = Path(
    "results/phase7h_final_test_summary.json"
)


# =========================================================
# Frozen constants
# =========================================================

EXPECTED_TEST_QUERIES = 360
EXPECTED_TEST_COMPONENTS = 2520
EXPECTED_COMPONENTS_PER_QUERY = 7

EXPECTED_CODE_PER_QUERY = 5
EXPECTED_STRUCTURED_PER_QUERY = 1
EXPECTED_IMAGE_PER_QUERY = 1

EXPECTED_TEST_GALLERY_PROJECTS = 60

UNKNOWN_LABEL = "UNKNOWN"

EPSILON = 1e-12

MISSING_PARENT_DISTANCE = 1.0


# =========================================================
# Helpers
# =========================================================

def clean_text(value):
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    return str(value).strip()


def as_bool(value):
    if isinstance(value, bool):
        return value

    return clean_text(value).lower() in {
        "1",
        "true",
        "yes",
        "y",
    }


def safe_divide(a, b):
    if b == 0:
        return 0.0

    return float(a / b)


def sha256_file(path):
    digest = hashlib.sha256()

    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def set_metrics(true_set, pred_set):
    true_set = set(true_set)
    pred_set = set(pred_set)

    intersection = len(
        true_set & pred_set
    )

    precision = safe_divide(
        intersection,
        len(pred_set),
    )

    recall = safe_divide(
        intersection,
        len(true_set),
    )

    if precision + recall == 0:
        f1 = 0.0
    else:
        f1 = (
            2.0
            * precision
            * recall
            / (precision + recall)
        )

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "exact": bool(
            true_set == pred_set
        ),
    }


def binary_metrics(truth, prediction):
    truth = np.asarray(
        truth,
        dtype=bool,
    )

    prediction = np.asarray(
        prediction,
        dtype=bool,
    )

    tp = int(
        np.logical_and(
            truth,
            prediction,
        ).sum()
    )

    fp = int(
        np.logical_and(
            ~truth,
            prediction,
        ).sum()
    )

    fn = int(
        np.logical_and(
            truth,
            ~prediction,
        ).sum()
    )

    tn = int(
        np.logical_and(
            ~truth,
            ~prediction,
        ).sum()
    )

    precision = safe_divide(
        tp,
        tp + fp,
    )

    recall = safe_divide(
        tp,
        tp + fn,
    )

    if precision + recall == 0:
        f1 = 0.0
    else:
        f1 = (
            2.0
            * precision
            * recall
            / (precision + recall)
        )

    # Known class F1
    known_precision = safe_divide(
        tn,
        tn + fn,
    )

    known_recall = safe_divide(
        tn,
        tn + fp,
    )

    if known_precision + known_recall == 0:
        known_f1 = 0.0
    else:
        known_f1 = (
            2.0
            * known_precision
            * known_recall
            / (
                known_precision
                + known_recall
            )
        )

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "known_f1": known_f1,
        "macro_f1": (
            f1 + known_f1
        ) / 2.0,
    }


# =========================================================
# Hex parsing
# =========================================================

def parse_hex128_optional(value):
    text = clean_text(value)

    if not text:
        return None

    if len(text) != 32:
        raise ValueError(
            f"Expected 128-bit hex, got {text!r}"
        )

    integer = int(
        text,
        16,
    )

    return (
        np.uint64(
            integer >> 64
        ),
        np.uint64(
            integer
            & ((1 << 64) - 1)
        ),
    )


def parse_hex64(value):
    text = clean_text(value)

    if len(text) != 16:
        raise ValueError(
            f"Expected 64-bit hex, got {text!r}"
        )

    return np.uint64(
        int(
            text,
            16,
        )
    )


def parse_hist16(value):
    text = clean_text(value)

    parts = [
        item.strip()
        for item in text.split(",")
    ]

    if len(parts) != 16:
        raise ValueError(
            f"Expected 16 histogram bins, "
            f"got {len(parts)}"
        )

    return np.array(
        [
            int(item)
            for item in parts
        ],
        dtype=np.float32,
    )


# =========================================================
# Popcount / Hamming
# =========================================================

POPCOUNT8 = np.array(
    [
        bin(value).count("1")
        for value in range(256)
    ],
    dtype=np.uint8,
)


def hamming128_array(
    highs,
    lows,
    query_high,
    query_low,
):
    xor_high = np.bitwise_xor(
        highs,
        query_high,
    )

    xor_low = np.bitwise_xor(
        lows,
        query_low,
    )

    high_bytes = (
        xor_high
        .view(np.uint8)
        .reshape(-1, 8)
    )

    low_bytes = (
        xor_low
        .view(np.uint8)
        .reshape(-1, 8)
    )

    counts = (
        POPCOUNT8[
            high_bytes
        ].sum(axis=1)
        +
        POPCOUNT8[
            low_bytes
        ].sum(axis=1)
    )

    return (
        counts.astype(
            np.float32
        )
        / 128.0
    )


def hamming64_array(
    values,
    query_value,
):
    xor_values = np.bitwise_xor(
        values,
        query_value,
    )

    byte_values = (
        xor_values
        .view(np.uint8)
        .reshape(-1, 8)
    )

    counts = (
        POPCOUNT8[
            byte_values
        ].sum(axis=1)
    )

    return (
        counts.astype(
            np.float32
        )
        / 64.0
    )


# =========================================================
# Parent minimum
# =========================================================

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

    if len(component_distances) > 0:
        np.minimum.at(
            result,
            project_indices,
            component_distances,
        )

    result[
        ~np.isfinite(result)
    ] = MISSING_PARENT_DISTANCE

    return result


# =========================================================
# Optional 128-bit gallery builder
# =========================================================

def build_optional_128_gallery(
    dataframe,
    column,
):
    highs = []
    lows = []
    projects = []

    for row in dataframe.itertuples(
        index=False
    ):
        parsed = parse_hex128_optional(
            getattr(
                row,
                column,
                "",
            )
        )

        if parsed is None:
            continue

        high, low = parsed

        highs.append(high)
        lows.append(low)

        projects.append(
            int(
                row.project_index
            )
        )

    return {
        "high": np.array(
            highs,
            dtype=np.uint64,
        ),
        "low": np.array(
            lows,
            dtype=np.uint64,
        ),
        "project_indices": np.array(
            projects,
            dtype=np.int32,
        ),
    }


# =========================================================
# Load files
# =========================================================

required_paths = [
    GALLERY_EVIDENCE_CSV,
    QUERY_EVIDENCE_CSV,
    PRIVATE_MANIFEST_CSV,
    QUERY_GT_CSV,
    STRESS_GRAPH_CSV,
    FINAL_PARAMETERS_JSON,
    FINAL_FREEZE_SUMMARY_JSON,
]

for path in required_paths:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing: {path}"
        )


gallery = pd.read_csv(
    GALLERY_EVIDENCE_CSV
)

query_evidence = pd.read_csv(
    QUERY_EVIDENCE_CSV
)

private_manifest = pd.read_csv(
    PRIVATE_MANIFEST_CSV
)

query_gt = pd.read_csv(
    QUERY_GT_CSV
)

stress_graph = pd.read_csv(
    STRESS_GRAPH_CSV
)


final_parameters = json.loads(
    FINAL_PARAMETERS_JSON.read_text(
        encoding="utf-8"
    )
)

freeze_summary = json.loads(
    FINAL_FREEZE_SUMMARY_JSON.read_text(
        encoding="utf-8"
    )
)


print(
    "======================================"
)

print(
    "Phase 7H - Frozen Final TEST Evaluation"
)

print(
    "======================================"
)


# =========================================================
# Verify freeze integrity
# =========================================================

expected_parameter_sha = clean_text(
    freeze_summary[
        "final_parameter_file_sha256"
    ]
)

actual_parameter_sha = sha256_file(
    FINAL_PARAMETERS_JSON
)


if (
    actual_parameter_sha
    != expected_parameter_sha
):
    raise RuntimeError(
        "Final parameter file SHA changed "
        "after Phase 7G freeze"
    )


stage1 = final_parameters[
    "stage1"
]

stage2 = final_parameters[
    "stage2"
]


THRESHOLDS = {
    key: float(value)
    for key, value
    in stage1[
        "unknown_thresholds"
    ].items()
}


ALPHA = float(
    stage1[
        "alpha_absolute_distance"
    ]
)

REGRET_WEIGHT = float(
    stage1[
        "alpha_mean_regret"
    ]
)

LAMBDA = float(
    stage1[
        "parent_proliferation_lambda"
    ]
)

CANDIDATE_POOL_SIZE = int(
    stage1[
        "candidate_pool_size"
    ]
)

MAX_KNOWN_PARENTS = int(
    final_parameters[
        "query_definition"
    ][
        "maximum_known_parents"
    ]
)

FINAL_BETA = float(
    stage2[
        "graph_beta"
    ]
)

TOP_R = int(
    stage2[
        "boundary_candidate_top_r"
    ]
)


print(
    "Frozen alpha :",
    ALPHA
)

print(
    "Frozen lambda:",
    LAMBDA
)

print(
    "Frozen M     :",
    CANDIDATE_POOL_SIZE
)

print(
    "Frozen beta  :",
    FINAL_BETA
)

print(
    "Frozen Top-R :",
    TOP_R
)


# =========================================================
# Hard frozen-value checks
# =========================================================

if abs(
    ALPHA - 0.75
) > EPSILON:
    raise RuntimeError(
        "Unexpected alpha"
    )

if abs(
    REGRET_WEIGHT - 0.25
) > EPSILON:
    raise RuntimeError(
        "Unexpected regret weight"
    )

if abs(
    LAMBDA - 0.5
) > EPSILON:
    raise RuntimeError(
        "Unexpected lambda"
    )

if CANDIDATE_POOL_SIZE != 10:
    raise RuntimeError(
        "Unexpected candidate M"
    )

if MAX_KNOWN_PARENTS != 3:
    raise RuntimeError(
        "Unexpected Kmax"
    )

if abs(
    FINAL_BETA - 0.1
) > EPSILON:
    raise RuntimeError(
        "Unexpected beta"
    )

if TOP_R != 3:
    raise RuntimeError(
        "Unexpected boundary Top-R"
    )


# =========================================================
# TEST query identities
# =========================================================

test_gt = query_gt[
    query_gt[
        "stage"
    ]
    == "TEST"
].copy()


if len(test_gt) != EXPECTED_TEST_QUERIES:
    raise RuntimeError(
        "Expected 360 TEST queries"
    )


test_query_ids = set(
    test_gt[
        "query_id"
    ].astype(str)
)


test_manifest = private_manifest[
    private_manifest[
        "query_id"
    ].astype(str).isin(
        test_query_ids
    )
].copy()


test_query_evidence = query_evidence[
    query_evidence[
        "query_id"
    ].astype(str).isin(
        test_query_ids
    )
].copy()


if len(test_manifest) != EXPECTED_TEST_COMPONENTS:
    raise RuntimeError(
        "Expected 2520 TEST private components"
    )


if len(test_query_evidence) != EXPECTED_TEST_COMPONENTS:
    raise RuntimeError(
        "Expected 2520 TEST evidence components"
    )


# =========================================================
# Verify test query composition
# =========================================================

for query_id, group in (
    test_manifest.groupby(
        "query_id"
    )
):
    if len(group) != 7:
        raise RuntimeError(
            f"{query_id}: query size != 7"
        )

    counts = (
        group[
            "modality"
        ]
        .value_counts()
        .to_dict()
    )

    expected = {
        "CODE_BINARY": 5,
        "STRUCTURED": 1,
        "IMAGE": 1,
    }

    if counts != expected:
        raise RuntimeError(
            f"{query_id}: bad modalities "
            f"{counts}"
        )


# =========================================================
# TEST gallery ONLY
# =========================================================

TEST_GALLERY_SPLITS = {
    "TEST_KNOWN",
    "TEST_BACKGROUND",
}


test_gallery = gallery[
    gallery[
        "frozen_split"
    ].isin(
        TEST_GALLERY_SPLITS
    )
].copy()


gallery_projects = sorted(
    test_gallery[
        "fresh_id"
    ].astype(str).unique()
)


if len(
    gallery_projects
) != EXPECTED_TEST_GALLERY_PROJECTS:
    raise RuntimeError(
        "Expected 60 TEST gallery projects, "
        f"got {len(gallery_projects)}"
    )


# Held-out UNKNOWN must not appear.
unknown_source_projects = set(
    test_manifest[
        test_manifest[
            "ground_truth_label"
        ]
        == UNKNOWN_LABEL
    ][
        "source_fresh_id"
    ].astype(str)
)


gallery_project_set = set(
    gallery_projects
)


unknown_gallery_leakage = (
    unknown_source_projects
    & gallery_project_set
)


if unknown_gallery_leakage:
    raise RuntimeError(
        "UNKNOWN source leaked into TEST gallery: "
        + str(
            sorted(
                unknown_gallery_leakage
            )
        )
    )


project_to_index = {
    project: index
    for index, project
    in enumerate(
        gallery_projects
    )
}


index_to_project = {
    index: project
    for project, index
    in project_to_index.items()
}


project_count = len(
    gallery_projects
)


test_gallery[
    "project_index"
] = (
    test_gallery[
        "fresh_id"
    ]
    .astype(str)
    .map(
        project_to_index
    )
)


# =========================================================
# Gallery arrays
# =========================================================

# CODE
code_gallery = test_gallery[
    test_gallery[
        "modality"
    ]
    == "CODE_BINARY"
].copy()


code_op3 = build_optional_128_gallery(
    code_gallery,
    "code_op3_simhash128",
)

code_struct = build_optional_128_gallery(
    code_gallery,
    "code_struct_simhash128",
)

code_context = build_optional_128_gallery(
    code_gallery,
    "code_context_simhash128",
)


# STRUCTURED
structured_gallery = test_gallery[
    test_gallery[
        "modality"
    ]
    == "STRUCTURED"
].copy()


structured_rep = build_optional_128_gallery(
    structured_gallery,
    "structured_simhash128",
)


# IMAGE
image_gallery = test_gallery[
    test_gallery[
        "modality"
    ]
    == "IMAGE"
].copy()


image_project_indices = (
    image_gallery[
        "project_index"
    ]
    .astype(int)
    .to_numpy(
        dtype=np.int32
    )
)


image_ahash = []
image_dhash = []
image_phash = []
image_hist = []


for row in image_gallery.itertuples(
    index=False
):
    image_ahash.append(
        parse_hex64(
            row.image_ahash64
        )
    )

    image_dhash.append(
        parse_hex64(
            row.image_dhash64
        )
    )

    image_phash.append(
        parse_hex64(
            row.image_phash64
        )
    )

    image_hist.append(
        parse_hist16(
            row.image_hist16
        )
    )


image_arrays = {
    "project_indices":
        image_project_indices,

    "ahash":
        np.array(
            image_ahash,
            dtype=np.uint64,
        ),

    "dhash":
        np.array(
            image_dhash,
            dtype=np.uint64,
        ),

    "phash":
        np.array(
            image_phash,
            dtype=np.uint64,
        ),

    "hist":
        np.vstack(
            image_hist
        ).astype(
            np.float32
        ),
}


print(
    "TEST gallery projects:",
    len(
        gallery_projects
    )
)

print(
    "TEST gallery CODE:",
    len(
        code_gallery
    )
)

print(
    "TEST gallery STRUCTURED:",
    len(
        structured_gallery
    )
)

print(
    "TEST gallery IMAGE:",
    len(
        image_gallery
    )
)


# =========================================================
# Component GT map
# =========================================================

component_gt = {}


for row in test_manifest.itertuples(
    index=False
):
    key = (
        clean_text(
            row.query_id
        ),
        clean_text(
            row.node_id
        ),
    )

    component_gt[
        key
    ] = {
        "label":
            clean_text(
                row.ground_truth_label
            ),

        "source_fresh_id":
            clean_text(
                row.source_fresh_id
            ),

        "modality":
            clean_text(
                row.modality
            ),

        "scenario":
            clean_text(
                row.scenario
            ),

        "k_true":
            int(
                row.k_true
            ),
    }


# =========================================================
# Compute TEST component-parent scores
# =========================================================

score_rows = []


test_query_evidence = (
    test_query_evidence
    .sort_values(
        [
            "query_id",
            "node_id",
        ],
        kind="stable",
    )
    .reset_index(
        drop=True
    )
)


for component_index, row in enumerate(
    test_query_evidence.itertuples(
        index=False
    ),
    start=1,
):
    if (
        component_index == 1
        or
        component_index % 100 == 0
    ):
        print(
            "score",
            component_index,
            "/",
            EXPECTED_TEST_COMPONENTS,
        )

    query_id = clean_text(
        row.query_id
    )

    node_id = clean_text(
        row.node_id
    )

    modality = clean_text(
        row.modality
    )

    representation_names = []
    parent_distance_vectors = []


    # -----------------------------------------------------
    # CODE
    # -----------------------------------------------------

    if modality == "CODE_BINARY":
        parsed = parse_hex128_optional(
            row.code_op3_simhash128
        )

        if parsed is not None:
            q_high, q_low = parsed

            component_distances = (
                hamming128_array(
                    code_op3["high"],
                    code_op3["low"],
                    q_high,
                    q_low,
                )
            )

            parent_distances = (
                parent_minimum(
                    component_distances,
                    code_op3[
                        "project_indices"
                    ],
                    project_count,
                )
            )

            representation_names.append(
                "CODE_OP3"
            )

            parent_distance_vectors.append(
                parent_distances
            )


        parsed = parse_hex128_optional(
            row.code_struct_simhash128
        )

        if parsed is not None:
            q_high, q_low = parsed

            component_distances = (
                hamming128_array(
                    code_struct["high"],
                    code_struct["low"],
                    q_high,
                    q_low,
                )
            )

            parent_distances = (
                parent_minimum(
                    component_distances,
                    code_struct[
                        "project_indices"
                    ],
                    project_count,
                )
            )

            representation_names.append(
                "CODE_STRUCT"
            )

            parent_distance_vectors.append(
                parent_distances
            )


        parsed = parse_hex128_optional(
            row.code_context_simhash128
        )

        if parsed is not None:
            q_high, q_low = parsed

            component_distances = (
                hamming128_array(
                    code_context["high"],
                    code_context["low"],
                    q_high,
                    q_low,
                )
            )

            parent_distances = (
                parent_minimum(
                    component_distances,
                    code_context[
                        "project_indices"
                    ],
                    project_count,
                )
            )

            representation_names.append(
                "CODE_CONTEXT"
            )

            parent_distance_vectors.append(
                parent_distances
            )


    # -----------------------------------------------------
    # STRUCTURED
    # -----------------------------------------------------

    elif modality == "STRUCTURED":
        parsed = parse_hex128_optional(
            row.structured_simhash128
        )

        if parsed is None:
            raise RuntimeError(
                f"{query_id}/{node_id}: "
                "missing structured signature"
            )

        q_high, q_low = parsed

        component_distances = (
            hamming128_array(
                structured_rep["high"],
                structured_rep["low"],
                q_high,
                q_low,
            )
        )

        parent_distances = (
            parent_minimum(
                component_distances,
                structured_rep[
                    "project_indices"
                ],
                project_count,
            )
        )

        representation_names.append(
            "STRUCTURED_SIMHASH"
        )

        parent_distance_vectors.append(
            parent_distances
        )


    # -----------------------------------------------------
    # IMAGE
    # -----------------------------------------------------

    elif modality == "IMAGE":
        q_ahash = parse_hex64(
            row.image_ahash64
        )

        q_dhash = parse_hex64(
            row.image_dhash64
        )

        q_phash = parse_hex64(
            row.image_phash64
        )

        q_hist = parse_hist16(
            row.image_hist16
        )


        ahash_component = (
            hamming64_array(
                image_arrays[
                    "ahash"
                ],
                q_ahash,
            )
        )

        dhash_component = (
            hamming64_array(
                image_arrays[
                    "dhash"
                ],
                q_dhash,
            )
        )

        phash_component = (
            hamming64_array(
                image_arrays[
                    "phash"
                ],
                q_phash,
            )
        )

        hist_component = (
            np.abs(
                image_arrays[
                    "hist"
                ]
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

        hist_component = np.clip(
            hist_component,
            0.0,
            1.0,
        )


        ahash_parent = parent_minimum(
            ahash_component,
            image_arrays[
                "project_indices"
            ],
            project_count,
        )

        dhash_parent = parent_minimum(
            dhash_component,
            image_arrays[
                "project_indices"
            ],
            project_count,
        )

        phash_parent = parent_minimum(
            phash_component,
            image_arrays[
                "project_indices"
            ],
            project_count,
        )

        hist_parent = parent_minimum(
            hist_component,
            image_arrays[
                "project_indices"
            ],
            project_count,
        )


        representation_names.extend(
            [
                "IMAGE_AHASH",
                "IMAGE_DHASH",
                "IMAGE_PHASH",
                "IMAGE_HIST16",
            ]
        )

        parent_distance_vectors.extend(
            [
                ahash_parent,
                dhash_parent,
                phash_parent,
                hist_parent,
            ]
        )


    else:
        raise RuntimeError(
            f"Unsupported modality: "
            f"{modality}"
        )


    if not parent_distance_vectors:
        raise RuntimeError(
            f"{query_id}/{node_id}: "
            "no usable representation"
        )


    distance_matrix = np.vstack(
        parent_distance_vectors
    )


    fused_parent_distance = (
        distance_matrix.mean(
            axis=0
        )
    )


    # MEAN_REGRET over all 60 visible TEST gallery projects.
    regret_matrix = np.zeros_like(
        distance_matrix,
        dtype=np.float32,
    )


    for rep_index in range(
        distance_matrix.shape[0]
    ):
        reference_minimum = float(
            distance_matrix[
                rep_index
            ].min()
        )

        regret_matrix[
            rep_index
        ] = (
            distance_matrix[
                rep_index
            ]
            -
            reference_minimum
        )


    mean_regret = (
        regret_matrix.mean(
            axis=0
        )
    )


    for project_index in range(
        project_count
    ):
        project = index_to_project[
            project_index
        ]

        output = {
            "query_id":
                query_id,

            "node_id":
                node_id,

            "modality":
                modality,

            "candidate_parent":
                project,

            "fused_parent_distance":
                float(
                    fused_parent_distance[
                        project_index
                    ]
                ),

            "mean_regret":
                float(
                    mean_regret[
                        project_index
                    ]
                ),

            "representation_count":
                int(
                    distance_matrix.shape[0]
                ),
        }


        for (
            rep_name,
            rep_values
        ) in zip(
            representation_names,
            parent_distance_vectors,
        ):
            output[
                "distance_"
                + rep_name.lower()
            ] = float(
                rep_values[
                    project_index
                ]
            )


        score_rows.append(
            output
        )


scores = pd.DataFrame(
    score_rows
)


expected_score_rows = (
    EXPECTED_TEST_COMPONENTS
    *
    EXPECTED_TEST_GALLERY_PROJECTS
)


if len(scores) != expected_score_rows:
    raise RuntimeError(
        f"Expected {expected_score_rows} "
        f"score rows, got {len(scores)}"
    )


score_counts = (
    scores
    .groupby(
        [
            "query_id",
            "node_id",
        ]
    )
    .size()
)


if not (
    score_counts
    == EXPECTED_TEST_GALLERY_PROJECTS
).all():
    raise RuntimeError(
        "Some TEST component does not "
        "have exactly 60 candidate parents"
    )


# =========================================================
# Frozen normalized cost
# =========================================================

def normalized_component_cost(
    modality,
    distance,
    regret,
):
    threshold = THRESHOLDS[
        modality
    ]

    distance = float(
        distance
    )

    regret = float(
        regret
    )


    if threshold > 0:
        eligible = bool(
            distance
            <= (
                threshold
                +
                EPSILON
            )
        )

        normalized_distance = min(
            distance / threshold,
            1.0,
        )

    else:
        eligible = bool(
            abs(
                distance
            )
            <= EPSILON
        )

        normalized_distance = (
            0.0
            if eligible
            else 1.0
        )


    normalized_regret = min(
        max(
            regret,
            0.0,
        ),
        1.0,
    )


    cost = (
        ALPHA
        *
        normalized_distance
        +
        REGRET_WEIGHT
        *
        normalized_regret
    )


    return (
        float(cost),
        eligible,
    )


# =========================================================
# Stress graph lookup
# =========================================================

stress_edges_by_query = defaultdict(
    list
)


for row in stress_graph.itertuples(
    index=False
):
    query_id = clean_text(
        row.query_id
    )

    if query_id not in test_query_ids:
        continue

    stress_edges_by_query[
        query_id
    ].append(
        (
            clean_text(
                row.node_a
            ),
            clean_text(
                row.node_b
            ),
        )
    )


# =========================================================
# Prepare query objects
# =========================================================

def prepare_query(query_id):
    group = scores[
        scores[
            "query_id"
        ].astype(str)
        == query_id
    ].copy()

    node_ids = sorted(
        group[
            "node_id"
        ].astype(str).unique()
    )

    if len(node_ids) != 7:
        raise RuntimeError(
            f"{query_id}: expected 7 nodes"
        )


    modalities = {}

    base_costs = {}

    eligible_map = {}


    for node_id in node_ids:
        node_group = group[
            group[
                "node_id"
            ].astype(str)
            == node_id
        ]

        modality_values = set(
            node_group[
                "modality"
            ].astype(str)
        )

        if len(
            modality_values
        ) != 1:
            raise RuntimeError(
                "Mixed modality"
            )

        modality = next(
            iter(
                modality_values
            )
        )

        modalities[
            node_id
        ] = modality

        base_costs[
            node_id
        ] = {}

        eligible_map[
            node_id
        ] = {}


        for row in node_group.itertuples(
            index=False
        ):
            parent = clean_text(
                row.candidate_parent
            )

            cost, eligible = (
                normalized_component_cost(
                    modality,
                    row.fused_parent_distance,
                    row.mean_regret,
                )
            )

            base_costs[
                node_id
            ][
                parent
            ] = cost

            eligible_map[
                node_id
            ][
                parent
            ] = eligible


    all_candidates = sorted(
        group[
            "candidate_parent"
        ].astype(str).unique()
    )


    if len(all_candidates) != 60:
        raise RuntimeError(
            f"{query_id}: expected 60 candidates"
        )


    # Frozen Phase 7E retrieval:
    # mean of best three component costs.
    retrieval_scores = {}


    for parent in all_candidates:
        costs = sorted(
            base_costs[
                node_id
            ][
                parent
            ]
            for node_id
            in node_ids
        )

        retrieval_scores[
            parent
        ] = float(
            np.mean(
                costs[:3]
            )
        )


    ranked_candidates = sorted(
        all_candidates,
        key=lambda parent: (
            retrieval_scores[
                parent
            ],
            parent,
        ),
    )


    candidate_pool = ranked_candidates[
        :CANDIDATE_POOL_SIZE
    ]


    code_nodes = [
        node_id
        for node_id
        in node_ids
        if modalities[
            node_id
        ]
        == "CODE_BINARY"
    ]


    if len(code_nodes) != 5:
        raise RuntimeError(
            f"{query_id}: expected 5 code nodes"
        )


    gt_labels = {
        node_id:
            component_gt[
                (
                    query_id,
                    node_id,
                )
            ][
                "label"
            ]
        for node_id
        in node_ids
    }


    source_projects = {
        node_id:
            component_gt[
                (
                    query_id,
                    node_id,
                )
            ][
                "source_fresh_id"
            ]
        for node_id
        in node_ids
    }


    return {
        "query_id":
            query_id,

        "node_ids":
            node_ids,

        "modalities":
            modalities,

        "code_nodes":
            code_nodes,

        "candidate_pool":
            list(
                candidate_pool
            ),

        "base_costs":
            base_costs,

        "eligible":
            eligible_map,

        "ground_truth":
            gt_labels,

        "source_projects":
            source_projects,

        "retrieval_scores":
            retrieval_scores,
    }


prepared_queries = []


for index, query_id in enumerate(
    sorted(
        test_query_ids
    ),
    start=1,
):
    if (
        index == 1
        or
        index % 30 == 0
    ):
        print(
            "prepare",
            index,
            "/",
            EXPECTED_TEST_QUERIES,
        )

    prepared_queries.append(
        prepare_query(
            query_id
        )
    )


# =========================================================
# Retrieval ceiling audit
# =========================================================

retrieval_rows = []


for query in prepared_queries:
    known_true_projects = set()

    for node_id in query[
        "node_ids"
    ]:
        truth_label = query[
            "ground_truth"
        ][
            node_id
        ]

        if truth_label == UNKNOWN_LABEL:
            continue

        known_true_projects.add(
            query[
                "source_projects"
            ][
                node_id
            ]
        )


    pool_set = set(
        query[
            "candidate_pool"
        ]
    )


    if known_true_projects:
        covered = len(
            known_true_projects
            & pool_set
        )

        known_parent_recall = (
            covered
            /
            len(
                known_true_projects
            )
        )

        all_known_present = bool(
            known_true_projects
            <= pool_set
        )

    else:
        covered = 0
        known_parent_recall = np.nan
        all_known_present = np.nan


    gt_row = test_gt[
        test_gt[
            "query_id"
        ].astype(str)
        == query[
            "query_id"
        ]
    ].iloc[0]


    retrieval_rows.append({
        "query_id":
            query[
                "query_id"
            ],

        "scenario":
            clean_text(
                gt_row[
                    "scenario"
                ]
            ),

        "k_true":
            int(
                gt_row[
                    "k_true"
                ]
            ),

        "known_true_parent_count":
            int(
                len(
                    known_true_projects
                )
            ),

        "known_true_parents_covered":
            int(
                covered
            ),

        "known_parent_recall":
            known_parent_recall,

        "all_known_true_parents_present":
            all_known_present,

        "candidate_pool":
            json.dumps(
                query[
                    "candidate_pool"
                ]
            ),
    })


retrieval_df = pd.DataFrame(
    retrieval_rows
)


# =========================================================
# Boundary-aware graph
# =========================================================

def top_parent_set(
    query,
    node_id,
):
    ranked = sorted(
        query[
            "candidate_pool"
        ],
        key=lambda parent: (
            query[
                "base_costs"
            ][
                node_id
            ][
                parent
            ],
            parent,
        ),
    )

    return set(
        ranked[:TOP_R]
    )


def build_edge_weights(query):
    query_id = query[
        "query_id"
    ]

    code_nodes = set(
        query[
            "code_nodes"
        ]
    )

    top_sets = {
        node_id:
            top_parent_set(
                query,
                node_id,
            )
        for node_id
        in query[
            "code_nodes"
        ]
    }


    edges = []


    for node_a, node_b in (
        stress_edges_by_query.get(
            query_id,
            []
        )
    ):
        if (
            node_a not in code_nodes
            or
            node_b not in code_nodes
        ):
            continue

        first = top_sets[
            node_a
        ]

        second = top_sets[
            node_b
        ]

        union = (
            first | second
        )

        if not union:
            weight = 0.0
        else:
            weight = (
                len(
                    first & second
                )
                /
                len(
                    union
                )
            )

        edges.append({
            "node_a":
                node_a,

            "node_b":
                node_b,

            "weight":
                float(
                    weight
                ),
        })


    return edges


def refined_costs(
    query,
    beta,
):
    refined = {
        node_id: {
            parent:
                float(
                    query[
                        "base_costs"
                    ][
                        node_id
                    ][
                        parent
                    ]
                )
            for parent
            in query[
                "candidate_pool"
            ]
        }
        for node_id
        in query[
            "node_ids"
        ]
    }


    edges = build_edge_weights(
        query
    )


    if beta <= EPSILON:
        return refined


    adjacency = {
        node_id: []
        for node_id
        in query[
            "code_nodes"
        ]
    }


    for edge in edges:
        weight = float(
            edge[
                "weight"
            ]
        )

        if weight <= 0:
            continue

        node_a = edge[
            "node_a"
        ]

        node_b = edge[
            "node_b"
        ]

        adjacency[
            node_a
        ].append(
            (
                node_b,
                weight,
            )
        )

        adjacency[
            node_b
        ].append(
            (
                node_a,
                weight,
            )
        )


    for node_id in query[
        "code_nodes"
    ]:
        neighbors = adjacency[
            node_id
        ]

        weight_sum = sum(
            weight
            for _, weight
            in neighbors
        )

        if weight_sum <= 0:
            continue


        for parent in query[
            "candidate_pool"
        ]:
            neighbor_cost = (
                sum(
                    weight
                    *
                    query[
                        "base_costs"
                    ][
                        neighbor
                    ][
                        parent
                    ]
                    for neighbor, weight
                    in neighbors
                )
                /
                weight_sum
            )

            own_cost = (
                query[
                    "base_costs"
                ][
                    node_id
                ][
                    parent
                ]
            )

            refined[
                node_id
            ][
                parent
            ] = float(
                (
                    1.0 - beta
                )
                *
                own_cost
                +
                beta
                *
                neighbor_cost
            )


    return refined


# =========================================================
# Frozen subset optimizer
# =========================================================

def solve_query(
    query,
    beta,
):
    refined = refined_costs(
        query,
        beta,
    )

    pool = query[
        "candidate_pool"
    ]

    node_ids = query[
        "node_ids"
    ]


    best_solution = None
    best_key = None


    for subset_size in range(
        MAX_KNOWN_PARENTS + 1
    ):
        for subset in combinations(
            pool,
            subset_size,
        ):
            assignments = []

            total_assignment_cost = 0.0


            for node_id in node_ids:
                eligible_parents = [
                    parent
                    for parent
                    in subset
                    if query[
                        "eligible"
                    ][
                        node_id
                    ][
                        parent
                    ]
                ]


                if not eligible_parents:
                    assignments.append(
                        UNKNOWN_LABEL
                    )

                    total_assignment_cost += 1.0
                    continue


                best_parent = min(
                    eligible_parents,
                    key=lambda parent: (
                        refined[
                            node_id
                        ][
                            parent
                        ],
                        parent,
                    ),
                )


                best_parent_cost = float(
                    refined[
                        node_id
                    ][
                        best_parent
                    ]
                )


                if best_parent_cost > 1.0:
                    assignments.append(
                        UNKNOWN_LABEL
                    )

                    total_assignment_cost += 1.0
                else:
                    assignments.append(
                        best_parent
                    )

                    total_assignment_cost += (
                        best_parent_cost
                    )


            objective = (
                total_assignment_cost
                +
                LAMBDA
                *
                subset_size
            )


            key = (
                float(
                    objective
                ),
                subset_size,
                tuple(
                    subset
                ),
            )


            if (
                best_key is None
                or
                key < best_key
            ):
                best_key = key

                best_solution = {
                    "subset":
                        tuple(
                            subset
                        ),

                    "assignments":
                        list(
                            assignments
                        ),

                    "objective":
                        float(
                            objective
                        ),
                }


    if best_solution is None:
        raise RuntimeError(
            f"{query['query_id']}: "
            "no solution"
        )


    return best_solution


# =========================================================
# Evaluate fixed beta
# =========================================================

def evaluate(
    beta,
    collect_predictions,
):
    component_rows = []
    query_rows = []


    component_truth = []
    component_prediction = []


    unknown_truth = []
    unknown_prediction = []


    known_component_total = 0
    known_component_correct = 0


    parent_precision_values = []
    parent_recall_values = []
    parent_f1_values = []

    parent_exact_count = 0

    k_correct_count = 0
    k_errors = []


    scenario_accumulator = defaultdict(
        lambda: {
            "queries": 0,
            "component_total": 0,
            "component_correct": 0,
            "parent_f1": [],
            "parent_exact": 0,
            "k_correct": 0,
            "k_errors": [],
            "unknown_truth": [],
            "unknown_pred": [],
        }
    )


    k_accumulator = defaultdict(
        lambda: {
            "queries": 0,
            "component_total": 0,
            "component_correct": 0,
            "parent_f1": [],
            "parent_exact": 0,
            "k_correct": 0,
            "k_errors": [],
        }
    )


    modality_accumulator = defaultdict(
        lambda: {
            "total": 0,
            "correct": 0,
            "unknown_truth": [],
            "unknown_pred": [],
        }
    )


    for index, query in enumerate(
        prepared_queries,
        start=1,
    ):
        if (
            index == 1
            or
            index % 30 == 0
        ):
            print(
                "evaluate beta=",
                beta,
                index,
                "/",
                EXPECTED_TEST_QUERIES,
            )


        solution = solve_query(
            query,
            beta,
        )


        gt_row = test_gt[
            test_gt[
                "query_id"
            ].astype(str)
            == query[
                "query_id"
            ]
        ].iloc[0]


        scenario = clean_text(
            gt_row[
                "scenario"
            ]
        )

        k_true_manifest = int(
            gt_row[
                "k_true"
            ]
        )


        truth_labels = [
            query[
                "ground_truth"
            ][
                node_id
            ]
            for node_id
            in query[
                "node_ids"
            ]
        ]


        predictions = solution[
            "assignments"
        ]


        true_parent_set = set(
            truth_labels
        )

        pred_parent_set = set(
            predictions
        )


        if len(
            true_parent_set
        ) != k_true_manifest:
            raise RuntimeError(
                f"{query['query_id']}: "
                "GT K mismatch"
            )


        parent_metrics = set_metrics(
            true_parent_set,
            pred_parent_set,
        )


        parent_precision_values.append(
            parent_metrics[
                "precision"
            ]
        )

        parent_recall_values.append(
            parent_metrics[
                "recall"
            ]
        )

        parent_f1_values.append(
            parent_metrics[
                "f1"
            ]
        )


        if parent_metrics[
            "exact"
        ]:
            parent_exact_count += 1


        k_pred = len(
            pred_parent_set
        )


        if k_pred == k_true_manifest:
            k_correct_count += 1


        k_errors.append(
            abs(
                k_pred
                -
                k_true_manifest
            )
        )


        s = scenario_accumulator[
            scenario
        ]

        s[
            "queries"
        ] += 1

        s[
            "parent_f1"
        ].append(
            parent_metrics[
                "f1"
            ]
        )

        s[
            "parent_exact"
        ] += int(
            parent_metrics[
                "exact"
            ]
        )

        s[
            "k_correct"
        ] += int(
            k_pred
            ==
            k_true_manifest
        )

        s[
            "k_errors"
        ].append(
            abs(
                k_pred
                -
                k_true_manifest
            )
        )


        k_bucket = k_accumulator[
            k_true_manifest
        ]

        k_bucket[
            "queries"
        ] += 1

        k_bucket[
            "parent_f1"
        ].append(
            parent_metrics[
                "f1"
            ]
        )

        k_bucket[
            "parent_exact"
        ] += int(
            parent_metrics[
                "exact"
            ]
        )

        k_bucket[
            "k_correct"
        ] += int(
            k_pred
            ==
            k_true_manifest
        )

        k_bucket[
            "k_errors"
        ].append(
            abs(
                k_pred
                -
                k_true_manifest
            )
        )


        for (
            node_id,
            truth,
            prediction
        ) in zip(
            query[
                "node_ids"
            ],
            truth_labels,
            predictions,
        ):
            modality = query[
                "modalities"
            ][
                node_id
            ]


            component_truth.append(
                truth
            )

            component_prediction.append(
                prediction
            )


            correct = bool(
                truth == prediction
            )


            s[
                "component_total"
            ] += 1

            s[
                "component_correct"
            ] += int(
                correct
            )


            k_bucket[
                "component_total"
            ] += 1

            k_bucket[
                "component_correct"
            ] += int(
                correct
            )


            m = modality_accumulator[
                modality
            ]

            m[
                "total"
            ] += 1

            m[
                "correct"
            ] += int(
                correct
            )


            is_unknown_truth = bool(
                truth == UNKNOWN_LABEL
            )

            is_unknown_pred = bool(
                prediction == UNKNOWN_LABEL
            )


            unknown_truth.append(
                is_unknown_truth
            )

            unknown_prediction.append(
                is_unknown_pred
            )


            s[
                "unknown_truth"
            ].append(
                is_unknown_truth
            )

            s[
                "unknown_pred"
            ].append(
                is_unknown_pred
            )


            m[
                "unknown_truth"
            ].append(
                is_unknown_truth
            )

            m[
                "unknown_pred"
            ].append(
                is_unknown_pred
            )


            if not is_unknown_truth:
                known_component_total += 1

                if correct:
                    known_component_correct += 1


            if collect_predictions:
                component_rows.append({
                    "query_id":
                        query[
                            "query_id"
                        ],

                    "scenario":
                        scenario,

                    "k_true":
                        k_true_manifest,

                    "node_id":
                        node_id,

                    "modality":
                        modality,

                    "ground_truth_label":
                        truth,

                    "predicted_label":
                        prediction,

                    "correct":
                        correct,
                })


        if collect_predictions:
            query_rows.append({
                "query_id":
                    query[
                        "query_id"
                    ],

                "scenario":
                    scenario,

                "k_true":
                    k_true_manifest,

                "k_pred":
                    int(
                        k_pred
                    ),

                "true_parent_set":
                    json.dumps(
                        sorted(
                            true_parent_set
                        )
                    ),

                "predicted_parent_set":
                    json.dumps(
                        sorted(
                            pred_parent_set
                        )
                    ),

                "selected_known_subset":
                    json.dumps(
                        list(
                            solution[
                                "subset"
                            ]
                        )
                    ),

                "candidate_pool":
                    json.dumps(
                        query[
                            "candidate_pool"
                        ]
                    ),

                "parent_set_precision":
                    float(
                        parent_metrics[
                            "precision"
                        ]
                    ),

                "parent_set_recall":
                    float(
                        parent_metrics[
                            "recall"
                        ]
                    ),

                "parent_set_f1":
                    float(
                        parent_metrics[
                            "f1"
                        ]
                    ),

                "parent_set_exact":
                    bool(
                        parent_metrics[
                            "exact"
                        ]
                    ),

                "objective":
                    float(
                        solution[
                            "objective"
                        ]
                    ),
            })


    total_components = len(
        component_truth
    )

    total_correct = sum(
        truth == prediction
        for truth, prediction
        in zip(
            component_truth,
            component_prediction,
        )
    )


    unknown_metrics = binary_metrics(
        unknown_truth,
        unknown_prediction,
    )


    scenario_metrics = {}


    for scenario, data in sorted(
        scenario_accumulator.items()
    ):
        scenario_unknown = binary_metrics(
            data[
                "unknown_truth"
            ],
            data[
                "unknown_pred"
            ],
        )


        scenario_metrics[
            scenario
        ] = {
            "queries":
                int(
                    data[
                        "queries"
                    ]
                ),

            "component_accuracy":
                safe_divide(
                    data[
                        "component_correct"
                    ],
                    data[
                        "component_total"
                    ],
                ),

            "parent_set_f1":
                float(
                    np.mean(
                        data[
                            "parent_f1"
                        ]
                    )
                ),

            "parent_set_exact":
                safe_divide(
                    data[
                        "parent_exact"
                    ],
                    data[
                        "queries"
                    ],
                ),

            "k_accuracy":
                safe_divide(
                    data[
                        "k_correct"
                    ],
                    data[
                        "queries"
                    ],
                ),

            "k_mae":
                float(
                    np.mean(
                        data[
                            "k_errors"
                        ]
                    )
                ),

            "unknown_precision":
                float(
                    scenario_unknown[
                        "precision"
                    ]
                ),

            "unknown_recall":
                float(
                    scenario_unknown[
                        "recall"
                    ]
                ),

            "unknown_f1":
                float(
                    scenario_unknown[
                        "f1"
                    ]
                ),
        }


    by_k = {}


    for k_true, data in sorted(
        k_accumulator.items()
    ):
        by_k[
            str(
                k_true
            )
        ] = {
            "queries":
                int(
                    data[
                        "queries"
                    ]
                ),

            "component_accuracy":
                safe_divide(
                    data[
                        "component_correct"
                    ],
                    data[
                        "component_total"
                    ],
                ),

            "parent_set_f1":
                float(
                    np.mean(
                        data[
                            "parent_f1"
                        ]
                    )
                ),

            "parent_set_exact":
                safe_divide(
                    data[
                        "parent_exact"
                    ],
                    data[
                        "queries"
                    ],
                ),

            "k_accuracy":
                safe_divide(
                    data[
                        "k_correct"
                    ],
                    data[
                        "queries"
                    ],
                ),

            "k_mae":
                float(
                    np.mean(
                        data[
                            "k_errors"
                        ]
                    )
                ),
        }


    by_modality = {}


    for modality, data in sorted(
        modality_accumulator.items()
    ):
        modality_unknown = binary_metrics(
            data[
                "unknown_truth"
            ],
            data[
                "unknown_pred"
            ],
        )


        by_modality[
            modality
        ] = {
            "components":
                int(
                    data[
                        "total"
                    ]
                ),

            "component_accuracy":
                safe_divide(
                    data[
                        "correct"
                    ],
                    data[
                        "total"
                    ],
                ),

            "unknown_precision":
                float(
                    modality_unknown[
                        "precision"
                    ]
                ),

            "unknown_recall":
                float(
                    modality_unknown[
                        "recall"
                    ]
                ),

            "unknown_f1":
                float(
                    modality_unknown[
                        "f1"
                    ]
                ),
        }


    metrics = {
        "component_accuracy":
            safe_divide(
                total_correct,
                total_components,
            ),

        "known_component_accuracy":
            safe_divide(
                known_component_correct,
                known_component_total,
            ),

        "unknown_precision":
            float(
                unknown_metrics[
                    "precision"
                ]
            ),

        "unknown_recall":
            float(
                unknown_metrics[
                    "recall"
                ]
            ),

        "unknown_f1":
            float(
                unknown_metrics[
                    "f1"
                ]
            ),

        "unknown_known_macro_f1":
            float(
                unknown_metrics[
                    "macro_f1"
                ]
            ),

        "parent_set_precision":
            float(
                np.mean(
                    parent_precision_values
                )
            ),

        "parent_set_recall":
            float(
                np.mean(
                    parent_recall_values
                )
            ),

        "parent_set_f1":
            float(
                np.mean(
                    parent_f1_values
                )
            ),

        "parent_set_exact":
            safe_divide(
                parent_exact_count,
                EXPECTED_TEST_QUERIES,
            ),

        "k_accuracy":
            safe_divide(
                k_correct_count,
                EXPECTED_TEST_QUERIES,
            ),

        "k_mae":
            float(
                np.mean(
                    k_errors
                )
            ),

        "by_scenario":
            scenario_metrics,

        "by_k":
            by_k,

        "by_modality":
            by_modality,
    }


    return (
        metrics,
        pd.DataFrame(
            component_rows
        ),
        pd.DataFrame(
            query_rows
        ),
    )


# =========================================================
# FINAL frozen method
# =========================================================

print()

print(
    "======================================"
)

print(
    "FINAL beta =",
    FINAL_BETA
)

print(
    "======================================"
)


(
    final_metrics,
    final_component_df,
    final_query_df,
) = evaluate(
    FINAL_BETA,
    collect_predictions=True,
)


# =========================================================
# Frozen ablation: beta=0
# =========================================================

print()

print(
    "======================================"
)

print(
    "ABLATION beta = 0"
)

print(
    "======================================"
)


(
    beta0_metrics,
    beta0_component_df,
    beta0_query_df,
) = evaluate(
    0.0,
    collect_predictions=True,
)


# =========================================================
# Graph contribution on unseen TEST
# =========================================================

test_graph_delta = {
    "component_accuracy":
        float(
            final_metrics[
                "component_accuracy"
            ]
            -
            beta0_metrics[
                "component_accuracy"
            ]
        ),

    "parent_set_f1":
        float(
            final_metrics[
                "parent_set_f1"
            ]
            -
            beta0_metrics[
                "parent_set_f1"
            ]
        ),

    "parent_set_exact":
        float(
            final_metrics[
                "parent_set_exact"
            ]
            -
            beta0_metrics[
                "parent_set_exact"
            ]
        ),

    "k_accuracy":
        float(
            final_metrics[
                "k_accuracy"
            ]
            -
            beta0_metrics[
                "k_accuracy"
            ]
        ),

    "unknown_f1":
        float(
            final_metrics[
                "unknown_f1"
            ]
            -
            beta0_metrics[
                "unknown_f1"
            ]
        ),
}


# =========================================================
# Retrieval audit summary
# =========================================================

retrieval_known = retrieval_df[
    retrieval_df[
        "known_true_parent_count"
    ]
    > 0
].copy()


retrieval_summary = {
    "queries_with_known_parent":
        int(
            len(
                retrieval_known
            )
        ),

    "mean_known_parent_recall":
        float(
            retrieval_known[
                "known_parent_recall"
            ].mean()
        ),

    "all_known_true_parents_present_rate":
        float(
            retrieval_known[
                "all_known_true_parents_present"
            ]
            .astype(bool)
            .mean()
        ),

    "queries_missing_any_known_true_parent":
        int(
            (
                ~retrieval_known[
                    "all_known_true_parents_present"
                ].astype(bool)
            ).sum()
        ),
}


retrieval_by_scenario = {}


for scenario, group in (
    retrieval_df.groupby(
        "scenario"
    )
):
    with_known = group[
        group[
            "known_true_parent_count"
        ]
        > 0
    ]


    if len(with_known) == 0:
        retrieval_by_scenario[
            str(
                scenario
            )
        ] = {
            "queries_with_known_parent":
                0,

            "mean_known_parent_recall":
                None,

            "all_known_true_parents_present_rate":
                None,
        }

    else:
        retrieval_by_scenario[
            str(
                scenario
            )
        ] = {
            "queries_with_known_parent":
                int(
                    len(
                        with_known
                    )
                ),

            "mean_known_parent_recall":
                float(
                    with_known[
                        "known_parent_recall"
                    ].mean()
                ),

            "all_known_true_parents_present_rate":
                float(
                    with_known[
                        "all_known_true_parents_present"
                    ]
                    .astype(bool)
                    .mean()
                ),
        }


retrieval_summary[
    "by_scenario"
] = retrieval_by_scenario


# =========================================================
# Save
# =========================================================

OUTPUT_SCORE_CSV.parent.mkdir(
    parents=True,
    exist_ok=True,
)


scores.to_csv(
    OUTPUT_SCORE_CSV,
    index=False,
    encoding="utf-8-sig",
)


final_component_df.to_csv(
    OUTPUT_FINAL_COMPONENT_CSV,
    index=False,
    encoding="utf-8-sig",
)


final_query_df.to_csv(
    OUTPUT_FINAL_QUERY_CSV,
    index=False,
    encoding="utf-8-sig",
)


beta0_component_df.to_csv(
    OUTPUT_BETA0_COMPONENT_CSV,
    index=False,
    encoding="utf-8-sig",
)


beta0_query_df.to_csv(
    OUTPUT_BETA0_QUERY_CSV,
    index=False,
    encoding="utf-8-sig",
)


retrieval_df.to_csv(
    OUTPUT_RETRIEVAL_CSV,
    index=False,
    encoding="utf-8-sig",
)


# =========================================================
# Final summary
# =========================================================

summary = {
    "final_test_evaluation_complete":
        True,

    "performance_scope":
        "FROZEN_TEST",

    "test_opened_after_method_freeze":
        True,

    "method_parameters_changed_after_freeze":
        False,

    "final_parameter_file_sha256_verified":
        True,

    "final_parameter_file_sha256":
        actual_parameter_sha,

    "test_queries":
        EXPECTED_TEST_QUERIES,

    "test_components":
        EXPECTED_TEST_COMPONENTS,

    "test_gallery_projects":
        EXPECTED_TEST_GALLERY_PROJECTS,

    "unknown_source_projects_in_gallery":
        int(
            len(
                unknown_gallery_leakage
            )
        ),

    "frozen_parameters": {
        "CODE_UNKNOWN_threshold":
            THRESHOLDS[
                "CODE_BINARY"
            ],

        "STRUCTURED_UNKNOWN_threshold":
            THRESHOLDS[
                "STRUCTURED"
            ],

        "IMAGE_UNKNOWN_threshold":
            THRESHOLDS[
                "IMAGE"
            ],

        "alpha":
            ALPHA,

        "mean_regret_weight":
            REGRET_WEIGHT,

        "lambda":
            LAMBDA,

        "candidate_pool_M":
            CANDIDATE_POOL_SIZE,

        "graph_beta":
            FINAL_BETA,

        "boundary_top_r":
            TOP_R,

        "Kmax":
            MAX_KNOWN_PARENTS,
    },

    "candidate_retrieval_ceiling":
        retrieval_summary,

    "final_method_beta_0_1":
        final_metrics,

    "content_only_same_top10_beta_0":
        beta0_metrics,

    "graph_minus_content_only":
        test_graph_delta,

    "interpretation_policy": (
        "All final TEST metrics are reported as-is. "
        "No threshold, alpha, lambda, candidate-pool "
        "size, graph beta, Top-R or Kmax may be "
        "changed based on these TEST results."
    ),

    "goals_met":
        bool(
            len(
                final_component_df
            )
            == EXPECTED_TEST_COMPONENTS

            and
            len(
                final_query_df
            )
            == EXPECTED_TEST_QUERIES

            and
            len(
                scores
            )
            == expected_score_rows

            and
            len(
                unknown_gallery_leakage
            )
            == 0
        ),
}


OUTPUT_SUMMARY_JSON.write_text(
    json.dumps(
        summary,
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)


# =========================================================
# Print
# =========================================================

print()

print(
    "======================================"
)

print(
    "PHASE 7H FINAL TEST RESULT"
)

print(
    "======================================"
)

print(
    json.dumps(
        summary,
        ensure_ascii=False,
        indent=2,
    )
)

print()

print(
    "Scores:",
    OUTPUT_SCORE_CSV
)

print(
    "Final component predictions:",
    OUTPUT_FINAL_COMPONENT_CSV
)

print(
    "Final query predictions:",
    OUTPUT_FINAL_QUERY_CSV
)

print(
    "Beta0 component predictions:",
    OUTPUT_BETA0_COMPONENT_CSV
)

print(
    "Beta0 query predictions:",
    OUTPUT_BETA0_QUERY_CSV
)

print(
    "Retrieval audit:",
    OUTPUT_RETRIEVAL_CSV
)

print(
    "Summary:",
    OUTPUT_SUMMARY_JSON
)