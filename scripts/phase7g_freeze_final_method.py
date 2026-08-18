import hashlib
import json
from pathlib import Path

import pandas as pd


# =========================================================
# Inputs
# =========================================================

STAGE1_PARAMETERS = Path(
    "results/phase7d_stage1_parameters.json"
)

CANDIDATE_SUMMARY = Path(
    "results/phase7e_candidate_pool_summary.json"
)

GRAPH_PARAMETERS = Path(
    "results/phase7f_graph_parameters.json"
)

GRAPH_CONTRIBUTION = Path(
    "results/phase7f2_graph_contribution_summary.json"
)

QUERY_GT = Path(
    "results/phase6k_query_ground_truth.csv"
)

PRIVATE_MANIFEST = Path(
    "results/phase6l_materialized_private_manifest.csv"
)

PUBLIC_MANIFEST = Path(
    "results/phase6l_materialized_public_manifest.csv"
)

STRESS_GRAPH = Path(
    "results/phase6l_graph_connected_stress_public.csv"
)


# =========================================================
# Outputs
# =========================================================

OUTPUT_PARAMETERS = Path(
    "results/phase7g_final_method_parameters.json"
)

OUTPUT_SUMMARY = Path(
    "results/phase7g_final_method_freeze_summary.json"
)


# =========================================================
# Helpers
# =========================================================

def sha256_file(path):

    digest = hashlib.sha256()

    with path.open("rb") as f:

        while True:

            chunk = f.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest()


def load_json(path):

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


# =========================================================
# Validate files
# =========================================================

required = [
    STAGE1_PARAMETERS,
    CANDIDATE_SUMMARY,
    GRAPH_PARAMETERS,
    GRAPH_CONTRIBUTION,
    QUERY_GT,
    PRIVATE_MANIFEST,
    PUBLIC_MANIFEST,
    STRESS_GRAPH,
]


for path in required:

    if not path.exists():

        raise FileNotFoundError(
            f"Missing: {path}"
        )


# =========================================================
# Load
# =========================================================

stage1 = load_json(
    STAGE1_PARAMETERS
)

candidate = load_json(
    CANDIDATE_SUMMARY
)

graph = load_json(
    GRAPH_PARAMETERS
)

contribution = load_json(
    GRAPH_CONTRIBUTION
)


query_gt = pd.read_csv(
    QUERY_GT
)

private_manifest = pd.read_csv(
    PRIVATE_MANIFEST
)

public_manifest = pd.read_csv(
    PUBLIC_MANIFEST
)

stress_graph = pd.read_csv(
    STRESS_GRAPH
)


print(
    "======================================"
)

print(
    "Phase 7G - Final Method Freeze"
)

print(
    "======================================"
)


# =========================================================
# Freeze checks
# =========================================================

alpha = float(
    stage1[
        "alpha_absolute_distance"
    ]
)

regret_weight = float(
    stage1[
        "alpha_mean_regret"
    ]
)

lambda_value = float(
    stage1[
        "parent_proliferation_lambda"
    ]
)

thresholds = {
    key:
        float(value)

    for key, value
    in stage1[
        "unknown_thresholds"
    ].items()
}

max_known_parents = int(
    stage1[
        "maximum_known_parent_candidates"
    ]
)


candidate_pool_size = int(
    candidate[
        "selected_candidate_pool_size"
    ]
)


selected_beta = float(
    contribution[
        "final_beta_for_performance"
    ]
)


top_r = int(
    graph[
        "top_r_for_boundary_weight"
    ]
)


# =========================================================
# Expected frozen values
# =========================================================

if abs(
    alpha - 0.75
) > 1e-12:

    raise RuntimeError(
        f"Unexpected alpha: {alpha}"
    )


if abs(
    regret_weight - 0.25
) > 1e-12:

    raise RuntimeError(
        f"Unexpected regret weight: "
        f"{regret_weight}"
    )


if abs(
    lambda_value - 0.50
) > 1e-12:

    raise RuntimeError(
        f"Unexpected lambda: "
        f"{lambda_value}"
    )


if candidate_pool_size != 10:

    raise RuntimeError(
        "Candidate pool M must be 10"
    )


if max_known_parents != 3:

    raise RuntimeError(
        "Kmax must be 3"
    )


if abs(
    selected_beta - 0.1
) > 1e-12:

    raise RuntimeError(
        f"Final beta must be 0.1, "
        f"got {selected_beta}"
    )


if top_r != 3:

    raise RuntimeError(
        "Boundary Top-R must be 3"
    )


if (
    contribution[
        "decision"
    ]
    != "KEEP_GRAPH_REFINEMENT"
):

    raise RuntimeError(
        "Graph contribution decision mismatch"
    )


# =========================================================
# Query benchmark checks
# =========================================================

if len(
    query_gt
) != 540:

    raise RuntimeError(
        "Expected 540 total queries"
    )


test_gt = query_gt[
    query_gt[
        "stage"
    ]
    == "TEST"
].copy()


cal_gt = query_gt[
    query_gt[
        "stage"
    ]
    == "CALIBRATION"
].copy()


if len(
    test_gt
) != 360:

    raise RuntimeError(
        "Expected 360 TEST queries"
    )


if len(
    cal_gt
) != 180:

    raise RuntimeError(
        "Expected 180 calibration queries"
    )


# =========================================================
# TEST K balance
# =========================================================

test_k_counts = (
    test_gt[
        "k_true"
    ]
    .astype(int)
    .value_counts()
    .sort_index()
    .to_dict()
)


expected_k_counts = {
    1: 120,
    2: 120,
    3: 120,
}


if test_k_counts != expected_k_counts:

    raise RuntimeError(
        f"Unexpected TEST K balance: "
        f"{test_k_counts}"
    )


# =========================================================
# Component counts
# =========================================================

test_query_ids = set(
    test_gt[
        "query_id"
    ].astype(str)
)


test_private = private_manifest[
    private_manifest[
        "query_id"
    ].astype(str).isin(
        test_query_ids
    )
]


test_public = public_manifest[
    public_manifest[
        "query_id"
    ].astype(str).isin(
        test_query_ids
    )
]


if len(
    test_private
) != (
    360 * 7
):

    raise RuntimeError(
        "Expected 2520 TEST private components"
    )


if len(
    test_public
) != (
    360 * 7
):

    raise RuntimeError(
        "Expected 2520 TEST public components"
    )


counts_per_query = (
    test_public
    .groupby(
        "query_id"
    )
    .size()
)


if not (
    counts_per_query
    == 7
).all():

    raise RuntimeError(
        "TEST query size is not fixed at 7"
    )


# =========================================================
# Modality composition
# =========================================================

for query_id, group in (
    test_public.groupby(
        "query_id"
    )
):

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
            f"{query_id}: "
            f"bad modality composition "
            f"{counts}"
        )


# =========================================================
# Public leakage check
# =========================================================

forbidden_tokens = [
    "source",
    "parent",
    "ground_truth",
    "scenario",
    "k_true",
    "version",
    "sha",
]


for column in public_manifest.columns:

    lower = column.lower()


    for token in forbidden_tokens:

        if token in lower:

            raise RuntimeError(
                "Public manifest leakage: "
                f"{column}"
            )


for column in stress_graph.columns:

    lower = column.lower()


    for token in forbidden_tokens:

        if token in lower:

            raise RuntimeError(
                "Public graph leakage: "
                f"{column}"
            )


# =========================================================
# Test graph presence
# =========================================================

graph_query_ids = set(
    stress_graph[
        "query_id"
    ].astype(str)
)


missing_graph_queries = (
    test_query_ids
    -
    graph_query_ids
)


if missing_graph_queries:

    raise RuntimeError(
        "Some TEST queries have no "
        "CONNECTED_STRESS graph"
    )


# =========================================================
# Final immutable method
# =========================================================

final_parameters = {
    "final_method_frozen":
        True,

    "freeze_phase":
        "7G",

    "test_performance_seen_before_freeze":
        False,

    "query_definition": {
        "components_per_query":
            7,

        "modality_composition": {
            "CODE_BINARY":
                5,

            "STRUCTURED":
                1,

            "IMAGE":
                1,
        },

        "K_exposed":
            False,

        "maximum_known_parents":
            3,
    },

    "stage1": {
        "unknown_thresholds":
            thresholds,

        "alpha_absolute_distance":
            alpha,

        "alpha_mean_regret":
            regret_weight,

        "parent_proliferation_lambda":
            lambda_value,

        "candidate_pool_size":
            candidate_pool_size,
    },

    "stage2": {
        "graph_track":
            "CONNECTED_STRESS",

        "boundary_candidate_top_r":
            top_r,

        "edge_weight":
            (
                "Jaccard overlap between "
                "Top-3 content candidate sets"
            ),

        "graph_beta":
            selected_beta,

        "graph_changes_candidate_eligibility":
            False,
    },

    "unknown_model": {
        "maximum_unregistered_parent_labels_per_query":
            1,

        "unknown_output_label":
            "UNKNOWN",
    },

    "selection_history": {
        "stage1_selected_on":
            "CALIBRATION_ONLY",

        "candidate_pool_selected_on":
            "CALIBRATION_ONLY",

        "graph_beta_selected_on":
            "CALIBRATION_ONLY",

        "test_used_for_selection":
            False,
    },
}


# =========================================================
# Input hashes
# =========================================================

input_hashes = {
    str(path):
        sha256_file(
            path
        )

    for path in required
}


final_parameters[
    "freeze_input_sha256"
] = input_hashes


OUTPUT_PARAMETERS.parent.mkdir(
    parents=True,
    exist_ok=True,
)


OUTPUT_PARAMETERS.write_text(
    json.dumps(
        final_parameters,
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)


# =========================================================
# Freeze file hash
# =========================================================

final_parameter_sha = sha256_file(
    OUTPUT_PARAMETERS
)


# =========================================================
# Summary
# =========================================================

summary = {
    "final_method_freeze_complete":
        True,

    "performance_evaluated":
        False,

    "performance_scope":
        "NONE",

    "test_queries_scored":
        0,

    "unknown_heldout_queries_scored":
        0,

    "final_parameters": {
        "CODE_UNKNOWN_threshold":
            thresholds[
                "CODE_BINARY"
            ],

        "STRUCTURED_UNKNOWN_threshold":
            thresholds[
                "STRUCTURED"
            ],

        "IMAGE_UNKNOWN_threshold":
            thresholds[
                "IMAGE"
            ],

        "alpha":
            alpha,

        "mean_regret_weight":
            regret_weight,

        "lambda":
            lambda_value,

        "candidate_pool_M":
            candidate_pool_size,

        "graph_beta":
            selected_beta,

        "boundary_top_r":
            top_r,

        "Kmax":
            max_known_parents,
    },

    "test_queries":
        int(
            len(
                test_gt
            )
        ),

    "test_components":
        int(
            len(
                test_private
            )
        ),

    "test_k_distribution": {
        str(key):
            int(value)

        for key, value
        in test_k_counts.items()
    },

    "query_size_constant":
        True,

    "modality_composition_constant":
        True,

    "public_identity_leakage_detected":
        False,

    "final_parameter_file_sha256":
        final_parameter_sha,

    "parameters_may_change_after_this_phase":
        False,

    "goals_met":
        True,
}


OUTPUT_SUMMARY.write_text(
    json.dumps(
        summary,
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)


print()

print(
    "======================================"
)

print(
    "PHASE 7G RESULT"
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
    "Frozen method:",
    OUTPUT_PARAMETERS
)

print(
    "Summary:",
    OUTPUT_SUMMARY
)