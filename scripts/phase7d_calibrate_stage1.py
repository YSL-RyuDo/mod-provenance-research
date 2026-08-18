import json
import math
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd


# =========================================================
# Config
# =========================================================

OPEN39_SCORE_CSV = Path(
    "results/"
    "phase7c_calibration_component_parent_scores.csv"
)

OPENSET_FEATURE_CSV = Path(
    "results/"
    "phase7c_calibration_component_openset_features.csv"
)

FULL40_SCORE_CSV = Path(
    "results/"
    "phase7c2_calibration_full40_parent_scores.csv"
)

PSEUDO_GT_CSV = Path(
    "results/"
    "phase7a_calibration_component_ground_truth.csv"
)

PRIVATE_MANIFEST_CSV = Path(
    "results/"
    "phase6l_materialized_private_manifest.csv"
)


OUTPUT_THRESHOLD_GRID_CSV = Path(
    "results/"
    "phase7d_openset_threshold_grid.csv"
)

OUTPUT_PARAMETER_GRID_CSV = Path(
    "results/"
    "phase7d_stage1_parameter_grid.csv"
)

OUTPUT_COMPONENT_PREDICTIONS_CSV = Path(
    "results/"
    "phase7d_selected_component_predictions.csv"
)

OUTPUT_QUERY_PREDICTIONS_CSV = Path(
    "results/"
    "phase7d_selected_query_predictions.csv"
)

OUTPUT_PARAMETERS_JSON = Path(
    "results/"
    "phase7d_stage1_parameters.json"
)

OUTPUT_SUMMARY_JSON = Path(
    "results/"
    "phase7d_stage1_calibration_summary.json"
)


EXPECTED_QUERIES = 180
EXPECTED_COMPONENTS = 1260

EXPECTED_OPEN_CANDIDATES = 39
EXPECTED_FULL_CANDIDATES = 40

MAX_KNOWN_PARENTS = 3


# Coarse frozen grid to reduce calibration overfitting.
ALPHAS = [
    0.00,
    0.25,
    0.50,
    0.75,
    1.00,
]


LAMBDAS = sorted(
    set(
        [
            round(
                index * 0.05,
                2,
            )
            for index
            in range(
                0,
                41,
            )
        ]
        +
        [
            2.50,
            3.00,
            4.00,
            5.00,
            7.00,
        ]
    )
)


MODALITIES = [
    "CODE_BINARY",
    "STRUCTURED",
    "IMAGE",
]


UNKNOWN_LABEL = "UNKNOWN"

EPSILON = 1e-12


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

    return (
        clean_text(value).lower()
        in {
            "1",
            "true",
            "yes",
            "y",
        }
    )


def safe_divide(
    numerator,
    denominator,
):

    if denominator == 0:
        return 0.0

    return float(
        numerator
        /
        denominator
    )


# =========================================================
# Binary metrics
# =========================================================

def binary_metrics(
    truth,
    prediction,
):

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


    precision_positive = safe_divide(
        tp,
        tp + fp,
    )

    recall_positive = safe_divide(
        tp,
        tp + fn,
    )


    if (
        precision_positive
        +
        recall_positive
        == 0
    ):

        f1_positive = 0.0

    else:

        f1_positive = (
            2.0
            *
            precision_positive
            *
            recall_positive
            /
            (
                precision_positive
                +
                recall_positive
            )
        )


    # Negative class treated as positive.
    tn_as_tp = tn
    fn_as_fp = fn
    fp_as_fn = fp


    precision_negative = safe_divide(
        tn_as_tp,
        tn_as_tp + fn_as_fp,
    )

    recall_negative = safe_divide(
        tn_as_tp,
        tn_as_tp + fp_as_fn,
    )


    if (
        precision_negative
        +
        recall_negative
        == 0
    ):

        f1_negative = 0.0

    else:

        f1_negative = (
            2.0
            *
            precision_negative
            *
            recall_negative
            /
            (
                precision_negative
                +
                recall_negative
            )
        )


    macro_f1 = (
        f1_positive
        +
        f1_negative
    ) / 2.0


    accuracy = safe_divide(
        tp + tn,
        len(truth),
    )


    return {
        "tp":
            tp,

        "fp":
            fp,

        "fn":
            fn,

        "tn":
            tn,

        "precision_positive":
            precision_positive,

        "recall_positive":
            recall_positive,

        "f1_positive":
            f1_positive,

        "f1_negative":
            f1_negative,

        "macro_f1":
            macro_f1,

        "accuracy":
            accuracy,
    }


# =========================================================
# Parent-set metrics
# =========================================================

def set_metrics(
    true_set,
    pred_set,
):

    true_set = set(
        true_set
    )

    pred_set = set(
        pred_set
    )


    intersection = len(
        true_set
        &
        pred_set
    )


    precision = safe_divide(
        intersection,
        len(
            pred_set
        ),
    )


    recall = safe_divide(
        intersection,
        len(
            true_set
        ),
    )


    if (
        precision
        +
        recall
        == 0
    ):

        f1 = 0.0

    else:

        f1 = (
            2.0
            *
            precision
            *
            recall
            /
            (
                precision
                +
                recall
            )
        )


    return {
        "precision":
            precision,

        "recall":
            recall,

        "f1":
            f1,

        "exact":
            bool(
                true_set
                ==
                pred_set
            ),
    }


# =========================================================
# Load
# =========================================================

for path in [
    OPEN39_SCORE_CSV,
    OPENSET_FEATURE_CSV,
    FULL40_SCORE_CSV,
    PSEUDO_GT_CSV,
    PRIVATE_MANIFEST_CSV,
]:

    if not path.exists():

        raise FileNotFoundError(
            f"Missing: {path}"
        )


open39_scores = pd.read_csv(
    OPEN39_SCORE_CSV
)

openset_features = pd.read_csv(
    OPENSET_FEATURE_CSV
)

full40_scores = pd.read_csv(
    FULL40_SCORE_CSV
)

pseudo_gt = pd.read_csv(
    PSEUDO_GT_CSV
)

private_manifest = pd.read_csv(
    PRIVATE_MANIFEST_CSV
)


print(
    "======================================"
)

print(
    "Phase 7D - Stage-1 Calibration"
)

print(
    "======================================"
)


# =========================================================
# Basic validation
# =========================================================

open_components = (
    open39_scores[
        [
            "query_id",
            "node_id",
        ]
    ]
    .drop_duplicates()
)


full_components = (
    full40_scores[
        [
            "query_id",
            "node_id",
        ]
    ]
    .drop_duplicates()
)


if len(
    open_components
) != EXPECTED_COMPONENTS:

    raise RuntimeError(
        "OPEN39 component count mismatch"
    )


if len(
    full_components
) != EXPECTED_COMPONENTS:

    raise RuntimeError(
        "FULL40 component count mismatch"
    )


open_counts = (
    open39_scores
    .groupby(
        [
            "query_id",
            "node_id",
        ]
    )
    .size()
)


if not (
    open_counts
    == EXPECTED_OPEN_CANDIDATES
).all():

    raise RuntimeError(
        "OPEN39 does not contain "
        "39 candidates per component"
    )


full_counts = (
    full40_scores
    .groupby(
        [
            "query_id",
            "node_id",
        ]
    )
    .size()
)


if not (
    full_counts
    == EXPECTED_FULL_CANDIDATES
).all():

    raise RuntimeError(
        "FULL40 does not contain "
        "40 candidates per component"
    )


# =========================================================
# Known-only original calibration GT
# =========================================================

known_manifest = private_manifest[
    private_manifest[
        "stage"
    ]
    == "CALIBRATION"
].copy()


if len(
    known_manifest
) != EXPECTED_COMPONENTS:

    raise RuntimeError(
        "Expected 1260 calibration manifest rows"
    )


known_gt_map = {}


for row in known_manifest.itertuples(
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


    label = clean_text(
        row.ground_truth_label
    )


    if label == UNKNOWN_LABEL:

        raise RuntimeError(
            "Calibration known-only manifest "
            "unexpectedly contains UNKNOWN"
        )


    known_gt_map[
        key
    ] = label


# =========================================================
# Pseudo-open GT
# =========================================================

pseudo_gt_map = {}


for row in pseudo_gt.itertuples(
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


    pseudo_gt_map[
        key
    ] = clean_text(
        row.pseudo_ground_truth_label
    )


if len(
    pseudo_gt_map
) != EXPECTED_COMPONENTS:

    raise RuntimeError(
        "Pseudo GT component count mismatch"
    )


# =========================================================
# Phase 1:
# Modality-specific UNKNOWN thresholds
#
# Prediction:
# UNKNOWN iff best visible absolute distance > threshold.
#
# Selection:
# 1. binary macro-F1
# 2. UNKNOWN F1
# 3. UNKNOWN recall
# 4. lower threshold
# =========================================================

threshold_grid_rows = []

selected_thresholds = {}

selected_threshold_metrics = {}


for modality in MODALITIES:

    group = openset_features[
        openset_features[
            "modality"
        ]
        == modality
    ].copy()


    if len(group) == 0:

        raise RuntimeError(
            f"No open-set calibration rows "
            f"for {modality}"
        )


    distances = (
        group[
            "best_fused_parent_distance"
        ]
        .astype(float)
        .to_numpy()
    )


    truth_unknown = (
        group[
            "is_pseudo_unknown"
        ]
        .map(
            as_bool
        )
        .to_numpy(
            dtype=bool
        )
    )


    unique_values = sorted(
        set(
            float(value)
            for value in distances
        )
    )


    candidate_thresholds = {
        0.0,
        1.0,
    }


    candidate_thresholds.update(
        unique_values
    )


    for left, right in zip(
        unique_values[:-1],
        unique_values[1:],
    ):

        candidate_thresholds.add(
            (
                left
                +
                right
            )
            /
            2.0
        )


    candidate_thresholds = sorted(
        value
        for value in candidate_thresholds
        if (
            0.0
            <= value
            <= 1.0
        )
    )


    best_record = None
    best_key = None


    for threshold in (
        candidate_thresholds
    ):

        predicted_unknown = (
            distances
            >
            threshold
        )


        metrics = binary_metrics(
            truth_unknown,
            predicted_unknown,
        )


        record = {
            "modality":
                modality,

            "threshold":
                float(
                    threshold
                ),

            "components":
                int(
                    len(group)
                ),

            "true_unknown":
                int(
                    truth_unknown.sum()
                ),

            "true_known":
                int(
                    (
                        ~truth_unknown
                    ).sum()
                ),

            "macro_f1":
                float(
                    metrics[
                        "macro_f1"
                    ]
                ),

            "unknown_precision":
                float(
                    metrics[
                        "precision_positive"
                    ]
                ),

            "unknown_recall":
                float(
                    metrics[
                        "recall_positive"
                    ]
                ),

            "unknown_f1":
                float(
                    metrics[
                        "f1_positive"
                    ]
                ),

            "known_f1":
                float(
                    metrics[
                        "f1_negative"
                    ]
                ),

            "accuracy":
                float(
                    metrics[
                        "accuracy"
                    ]
                ),
        }


        threshold_grid_rows.append(
            record
        )


        selection_key = (
            record[
                "macro_f1"
            ],

            record[
                "unknown_f1"
            ],

            record[
                "unknown_recall"
            ],

            -record[
                "threshold"
            ],
        )


        if (
            best_key is None
            or
            selection_key
            >
            best_key
        ):

            best_key = (
                selection_key
            )

            best_record = (
                record
            )


    if best_record is None:

        raise RuntimeError(
            f"Threshold calibration failed: "
            f"{modality}"
        )


    selected_thresholds[
        modality
    ] = float(
        best_record[
            "threshold"
        ]
    )


    selected_threshold_metrics[
        modality
    ] = {
        key:
            value

        for key, value
        in best_record.items()

        if key
        != "modality"
    }


threshold_grid = pd.DataFrame(
    threshold_grid_rows
)


print()

print(
    "UNKNOWN thresholds:"
)


for modality in MODALITIES:

    print(
        " ",
        modality,
        "=",
        selected_thresholds[
            modality
        ],
        "macro-F1=",
        selected_threshold_metrics[
            modality
        ][
            "macro_f1"
        ],
    )


# =========================================================
# Prepare score matrices per query
# =========================================================

def prepare_view(
    score_df,
    gt_map,
    expected_candidates,
    view_name,
):

    prepared_queries = []


    query_ids = sorted(
        score_df[
            "query_id"
        ].astype(str).unique()
    )


    if len(
        query_ids
    ) != EXPECTED_QUERIES:

        raise RuntimeError(
            f"{view_name}: expected "
            f"{EXPECTED_QUERIES} queries, "
            f"got {len(query_ids)}"
        )


    for query_number, query_id in enumerate(
        query_ids,
        start=1,
    ):

        group = score_df[
            score_df[
                "query_id"
            ].astype(str)
            == query_id
        ]


        node_ids = sorted(
            group[
                "node_id"
            ].astype(str).unique()
        )


        if len(node_ids) != 7:

            raise RuntimeError(
                f"{view_name}/{query_id}: "
                f"expected 7 components"
            )


        candidates = sorted(
            group[
                "candidate_parent"
            ].astype(str).unique()
        )


        if len(
            candidates
        ) != expected_candidates:

            raise RuntimeError(
                f"{view_name}/{query_id}: "
                f"expected {expected_candidates} "
                f"candidate projects"
            )


        candidate_to_index = {
            candidate:
                index

            for index, candidate
            in enumerate(
                candidates
            )
        }


        component_count = len(
            node_ids
        )

        candidate_count = len(
            candidates
        )


        distances = np.zeros(
            (
                component_count,
                candidate_count,
            ),
            dtype=np.float64,
        )


        regrets = np.zeros(
            (
                component_count,
                candidate_count,
            ),
            dtype=np.float64,
        )


        modalities = []

        ground_truth = []


        for component_index, node_id in enumerate(
            node_ids
        ):

            component_group = group[
                group[
                    "node_id"
                ].astype(str)
                == node_id
            ]


            if len(
                component_group
            ) != expected_candidates:

                raise RuntimeError(
                    f"{view_name}/{query_id}/{node_id}: "
                    f"candidate row count mismatch"
                )


            modality_values = set(
                component_group[
                    "modality"
                ].astype(str)
            )


            if len(
                modality_values
            ) != 1:

                raise RuntimeError(
                    "Mixed modality in one component"
                )


            modality = next(
                iter(
                    modality_values
                )
            )


            modalities.append(
                modality
            )


            gt_key = (
                query_id,
                node_id,
            )


            if gt_key not in gt_map:

                raise RuntimeError(
                    f"{view_name}: missing GT "
                    f"{query_id}/{node_id}"
                )


            ground_truth.append(
                gt_map[
                    gt_key
                ]
            )


            for row in (
                component_group.itertuples(
                    index=False
                )
            ):

                candidate = clean_text(
                    row.candidate_parent
                )


                candidate_index = (
                    candidate_to_index[
                        candidate
                    ]
                )


                distances[
                    component_index,
                    candidate_index
                ] = float(
                    row.fused_parent_distance
                )


                regrets[
                    component_index,
                    candidate_index
                ] = float(
                    row.mean_regret
                )


        true_parent_set = set(
            ground_truth
        )


        prepared_queries.append({
            "query_id":
                query_id,

            "node_ids":
                node_ids,

            "candidates":
                candidates,

            "modalities":
                modalities,

            "distances":
                distances,

            "regrets":
                regrets,

            "ground_truth":
                ground_truth,

            "true_parent_set":
                true_parent_set,

            "k_true":
                int(
                    len(
                        true_parent_set
                    )
                ),
        })


    return prepared_queries


known_queries = prepare_view(
    full40_scores,
    known_gt_map,
    EXPECTED_FULL_CANDIDATES,
    "KNOWN_ONLY_40",
)


pseudo_queries = prepare_view(
    open39_scores,
    pseudo_gt_map,
    EXPECTED_OPEN_CANDIDATES,
    "PSEUDO_UNKNOWN_39",
)


# =========================================================
# Combination cache
# =========================================================

combination_cache = {}


def get_combinations(
    candidate_count,
    k,
):

    key = (
        candidate_count,
        k,
    )


    if key in combination_cache:

        return combination_cache[
            key
        ]


    if k == 0:

        result = np.empty(
            (
                1,
                0,
            ),
            dtype=np.int16,
        )


    else:

        result = np.array(
            list(
                combinations(
                    range(
                        candidate_count
                    ),
                    k,
                )
            ),
            dtype=np.int16,
        )


    combination_cache[
        key
    ] = result


    return result


# =========================================================
# Recover component assignments
# =========================================================

def recover_assignments(
    query,
    combined_cost,
    eligible,
    subset_indices,
):

    candidates = query[
        "candidates"
    ]


    assignments = []


    for component_index in range(
        len(
            query[
                "node_ids"
            ]
        )
    ):

        valid = [
            int(
                parent_index
            )

            for parent_index
            in subset_indices

            if eligible[
                component_index,
                int(
                    parent_index
                )
            ]
        ]


        if not valid:

            assignments.append(
                UNKNOWN_LABEL
            )

            continue


        best_parent_index = min(
            valid,
            key=lambda parent_index: (
                float(
                    combined_cost[
                        component_index,
                        parent_index
                    ]
                ),
                candidates[
                    parent_index
                ],
            ),
        )


        assignments.append(
            candidates[
                best_parent_index
            ]
        )


    return assignments


# =========================================================
# Best subset for each K
# =========================================================

def build_query_solutions(
    query,
    alpha,
):

    distances = query[
        "distances"
    ]

    regrets = query[
        "regrets"
    ]


    component_count = (
        distances.shape[
            0
        ]
    )

    candidate_count = (
        distances.shape[
            1
        ]
    )


    thresholds = np.array(
        [
            selected_thresholds[
                modality
            ]
            for modality
            in query[
                "modalities"
            ]
        ],
        dtype=np.float64,
    )


    eligible = (
        distances
        <= (
            thresholds[
                :,
                None
            ]
            +
            EPSILON
        )
    )


    denominator = np.maximum(
        thresholds,
        1e-9,
    )


    normalized_distance = (
        distances
        /
        denominator[
            :,
            None
        ]
    )


    normalized_distance = np.clip(
        normalized_distance,
        0.0,
        1.0,
    )


    normalized_regret = np.clip(
        regrets,
        0.0,
        1.0,
    )


    combined_cost = (
        float(
            alpha
        )
        *
        normalized_distance
        +
        (
            1.0
            -
            float(
                alpha
            )
        )
        *
        normalized_regret
    )


    # Parent is unavailable for this component:
    # UNKNOWN cost = 1.
    assignment_cost = np.where(
        eligible,
        combined_cost,
        1.0,
    )


    solutions = {}


    # -----------------------------------------------------
    # Kknown = 0
    # -----------------------------------------------------

    solutions[
        0
    ] = {
        "subset_size":
            0,

        "subset_indices":
            tuple(),

        "subset_parents":
            tuple(),

        "base_cost":
            float(
                component_count
            ),

        "assignments":
            [
                UNKNOWN_LABEL
                for _ in range(
                    component_count
                )
            ],
    }


    # -----------------------------------------------------
    # Kknown = 1
    # -----------------------------------------------------

    costs_k1 = (
        assignment_cost.sum(
            axis=0
        )
    )


    best_index = int(
        np.argmin(
            costs_k1
        )
    )


    subset_indices = (
        best_index,
    )


    solutions[
        1
    ] = {
        "subset_size":
            1,

        "subset_indices":
            subset_indices,

        "subset_parents":
            tuple(
                query[
                    "candidates"
                ][
                    index
                ]
                for index
                in subset_indices
            ),

        "base_cost":
            float(
                costs_k1[
                    best_index
                ]
            ),

        "assignments":
            recover_assignments(
                query,
                combined_cost,
                eligible,
                subset_indices,
            ),
    }


    # -----------------------------------------------------
    # Kknown = 2
    # -----------------------------------------------------

    combos2 = get_combinations(
        candidate_count,
        2,
    )


    first_cost = (
        assignment_cost[
            :,
            combos2[
                :,
                0
            ]
        ]
        .T
    )


    second_cost = (
        assignment_cost[
            :,
            combos2[
                :,
                1
            ]
        ]
        .T
    )


    costs_k2 = np.minimum(
        first_cost,
        second_cost,
    ).sum(
        axis=1
    )


    best_combo_index = int(
        np.argmin(
            costs_k2
        )
    )


    subset_indices = tuple(
        int(value)
        for value
        in combos2[
            best_combo_index
        ]
    )


    solutions[
        2
    ] = {
        "subset_size":
            2,

        "subset_indices":
            subset_indices,

        "subset_parents":
            tuple(
                query[
                    "candidates"
                ][
                    index
                ]
                for index
                in subset_indices
            ),

        "base_cost":
            float(
                costs_k2[
                    best_combo_index
                ]
            ),

        "assignments":
            recover_assignments(
                query,
                combined_cost,
                eligible,
                subset_indices,
            ),
    }


    # -----------------------------------------------------
    # Kknown = 3
    # -----------------------------------------------------

    combos3 = get_combinations(
        candidate_count,
        3,
    )


    cost_a = (
        assignment_cost[
            :,
            combos3[
                :,
                0
            ]
        ]
        .T
    )


    cost_b = (
        assignment_cost[
            :,
            combos3[
                :,
                1
            ]
        ]
        .T
    )


    cost_c = (
        assignment_cost[
            :,
            combos3[
                :,
                2
            ]
        ]
        .T
    )


    costs_k3 = np.minimum(
        np.minimum(
            cost_a,
            cost_b,
        ),
        cost_c,
    ).sum(
        axis=1
    )


    best_combo_index = int(
        np.argmin(
            costs_k3
        )
    )


    subset_indices = tuple(
        int(value)
        for value
        in combos3[
            best_combo_index
        ]
    )


    solutions[
        3
    ] = {
        "subset_size":
            3,

        "subset_indices":
            subset_indices,

        "subset_parents":
            tuple(
                query[
                    "candidates"
                ][
                    index
                ]
                for index
                in subset_indices
            ),

        "base_cost":
            float(
                costs_k3[
                    best_combo_index
                ]
            ),

        "assignments":
            recover_assignments(
                query,
                combined_cost,
                eligible,
                subset_indices,
            ),
    }


    return solutions


# =========================================================
# Precompute solutions for each alpha
#
# Lambda does not alter the best subset inside a fixed
# subset size; it only chooses between 0/1/2/3.
# =========================================================

print()

print(
    "Precomputing exhaustive parent subsets..."
)


precomputed_known = {}

precomputed_pseudo = {}


for alpha in ALPHAS:

    print(
        " alpha =",
        alpha,
    )


    known_alpha = []


    for index, query_record in enumerate(
        known_queries,
        start=1,
    ):

        if (
            index == 1
            or
            index % 60 == 0
        ):

            print(
                "   known",
                index,
                "/",
                len(
                    known_queries
                ),
            )


        known_alpha.append({
            "query":
                query_record,

            "solutions":
                build_query_solutions(
                    query_record,
                    alpha,
                ),
        })


    pseudo_alpha = []


    for index, query_record in enumerate(
        pseudo_queries,
        start=1,
    ):

        if (
            index == 1
            or
            index % 60 == 0
        ):

            print(
                "   pseudo",
                index,
                "/",
                len(
                    pseudo_queries
                ),
            )


        pseudo_alpha.append({
            "query":
                query_record,

            "solutions":
                build_query_solutions(
                    query_record,
                    alpha,
                ),
        })


    precomputed_known[
        alpha
    ] = known_alpha


    precomputed_pseudo[
        alpha
    ] = pseudo_alpha


# =========================================================
# Choose solution for lambda
# =========================================================

def choose_lambda_solution(
    record,
    lambda_value,
):

    candidates = []


    for subset_size in range(
        0,
        MAX_KNOWN_PARENTS + 1,
    ):

        solution = (
            record[
                "solutions"
            ][
                subset_size
            ]
        )


        objective = (
            float(
                solution[
                    "base_cost"
                ]
            )
            +
            float(
                lambda_value
            )
            *
            subset_size
        )


        candidates.append(
            (
                objective,
                subset_size,
                tuple(
                    solution[
                        "subset_parents"
                    ]
                ),
                solution,
            )
        )


    # Lower objective.
    # Exact ties -> smaller subset.
    # Then lexical subset identity.
    best = min(
        candidates,
        key=lambda item: (
            item[0],
            item[1],
            item[2],
        ),
    )


    return (
        best[
            3
        ],
        float(
            best[
                0
            ]
        ),
    )


# =========================================================
# Evaluate one view
# =========================================================

def evaluate_view(
    records,
    lambda_value,
    pseudo_open,
    collect_predictions=False,
):

    total_components = 0
    correct_components = 0


    parent_precision_values = []
    parent_recall_values = []
    parent_f1_values = []

    parent_exact_count = 0

    k_correct_count = 0

    k_absolute_errors = []


    unknown_truth = []
    unknown_prediction = []


    false_unknown_known_components = 0
    known_component_total = 0


    component_prediction_rows = []

    query_prediction_rows = []


    for record in records:

        query = record[
            "query"
        ]


        (
            solution,
            objective,
        ) = choose_lambda_solution(
            record,
            lambda_value,
        )


        predictions = solution[
            "assignments"
        ]


        ground_truth = query[
            "ground_truth"
        ]


        if (
            len(
                predictions
            )
            != len(
                ground_truth
            )
        ):

            raise RuntimeError(
                "Prediction component count mismatch"
            )


        for (
            node_id,
            modality,
            truth,
            prediction
        ) in zip(
            query[
                "node_ids"
            ],
            query[
                "modalities"
            ],
            ground_truth,
            predictions,
        ):

            total_components += 1


            if truth == prediction:

                correct_components += 1


            if pseudo_open:

                unknown_truth.append(
                    truth
                    == UNKNOWN_LABEL
                )

                unknown_prediction.append(
                    prediction
                    == UNKNOWN_LABEL
                )


            else:

                known_component_total += 1


                if (
                    prediction
                    == UNKNOWN_LABEL
                ):

                    false_unknown_known_components += 1


            if collect_predictions:

                component_prediction_rows.append({
                    "view":
                        (
                            "PSEUDO_UNKNOWN_39"
                            if pseudo_open
                            else
                            "KNOWN_ONLY_40"
                        ),

                    "query_id":
                        query[
                            "query_id"
                        ],

                    "node_id":
                        node_id,

                    "modality":
                        modality,

                    "ground_truth_label":
                        truth,

                    "predicted_label":
                        prediction,

                    "correct":
                        bool(
                            truth
                            ==
                            prediction
                        ),
                })


        true_parent_set = set(
            ground_truth
        )

        pred_parent_set = set(
            predictions
        )


        metrics = set_metrics(
            true_parent_set,
            pred_parent_set,
        )


        parent_precision_values.append(
            metrics[
                "precision"
            ]
        )

        parent_recall_values.append(
            metrics[
                "recall"
            ]
        )

        parent_f1_values.append(
            metrics[
                "f1"
            ]
        )


        if metrics[
            "exact"
        ]:

            parent_exact_count += 1


        k_true = len(
            true_parent_set
        )

        k_pred = len(
            pred_parent_set
        )


        if k_true == k_pred:

            k_correct_count += 1


        k_absolute_errors.append(
            abs(
                k_true
                -
                k_pred
            )
        )


        if collect_predictions:

            query_prediction_rows.append({
                "view":
                    (
                        "PSEUDO_UNKNOWN_39"
                        if pseudo_open
                        else
                        "KNOWN_ONLY_40"
                    ),

                "query_id":
                    query[
                        "query_id"
                    ],

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

                "k_true":
                    int(
                        k_true
                    ),

                "k_pred":
                    int(
                        k_pred
                    ),

                "selected_known_subset_size":
                    int(
                        solution[
                            "subset_size"
                        ]
                    ),

                "selected_known_subset":
                    json.dumps(
                        list(
                            solution[
                                "subset_parents"
                            ]
                        )
                    ),

                "objective":
                    float(
                        objective
                    ),

                "parent_set_precision":
                    float(
                        metrics[
                            "precision"
                        ]
                    ),

                "parent_set_recall":
                    float(
                        metrics[
                            "recall"
                        ]
                    ),

                "parent_set_f1":
                    float(
                        metrics[
                            "f1"
                        ]
                    ),

                "parent_set_exact":
                    bool(
                        metrics[
                            "exact"
                        ]
                    ),
            })


    query_count = len(
        records
    )


    result = {
        "component_accuracy":
            safe_divide(
                correct_components,
                total_components,
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
                query_count,
            ),

        "k_accuracy":
            safe_divide(
                k_correct_count,
                query_count,
            ),

        "k_mae":
            float(
                np.mean(
                    k_absolute_errors
                )
            ),
    }


    if pseudo_open:

        unknown_metrics = binary_metrics(
            unknown_truth,
            unknown_prediction,
        )


        result.update({
            "unknown_precision":
                float(
                    unknown_metrics[
                        "precision_positive"
                    ]
                ),

            "unknown_recall":
                float(
                    unknown_metrics[
                        "recall_positive"
                    ]
                ),

            "unknown_f1":
                float(
                    unknown_metrics[
                        "f1_positive"
                    ]
                ),

            "unknown_known_macro_f1":
                float(
                    unknown_metrics[
                        "macro_f1"
                    ]
                ),
        })


    else:

        result[
            "false_unknown_rate"
        ] = safe_divide(
            false_unknown_known_components,
            known_component_total,
        )


    return (
        result,
        component_prediction_rows,
        query_prediction_rows,
    )


# =========================================================
# Parameter grid
#
# Selection priority:
#
# 1. mean parent-set F1 across both calibration views
# 2. mean K accuracy
# 3. pseudo-UNKNOWN F1
# 4. mean component accuracy
# 5. larger lambda (parsimony)
# 6. alpha nearest 0.5
#
# No TEST data is involved.
# =========================================================

print()

print(
    "Evaluating calibration parameter grid..."
)


parameter_grid_rows = []


best_record = None
best_selection_key = None


for alpha in ALPHAS:

    known_records = (
        precomputed_known[
            alpha
        ]
    )

    pseudo_records = (
        precomputed_pseudo[
            alpha
        ]
    )


    for lambda_value in LAMBDAS:

        known_metrics, _, _ = evaluate_view(
            known_records,
            lambda_value,
            pseudo_open=False,
            collect_predictions=False,
        )


        pseudo_metrics, _, _ = evaluate_view(
            pseudo_records,
            lambda_value,
            pseudo_open=True,
            collect_predictions=False,
        )


        mean_parent_set_f1 = (
            known_metrics[
                "parent_set_f1"
            ]
            +
            pseudo_metrics[
                "parent_set_f1"
            ]
        ) / 2.0


        mean_k_accuracy = (
            known_metrics[
                "k_accuracy"
            ]
            +
            pseudo_metrics[
                "k_accuracy"
            ]
        ) / 2.0


        mean_component_accuracy = (
            known_metrics[
                "component_accuracy"
            ]
            +
            pseudo_metrics[
                "component_accuracy"
            ]
        ) / 2.0


        row = {
            "alpha":
                float(
                    alpha
                ),

            "lambda":
                float(
                    lambda_value
                ),

            "mean_parent_set_f1":
                float(
                    mean_parent_set_f1
                ),

            "mean_k_accuracy":
                float(
                    mean_k_accuracy
                ),

            "mean_component_accuracy":
                float(
                    mean_component_accuracy
                ),

            "known_component_accuracy":
                float(
                    known_metrics[
                        "component_accuracy"
                    ]
                ),

            "known_parent_set_f1":
                float(
                    known_metrics[
                        "parent_set_f1"
                    ]
                ),

            "known_parent_set_exact":
                float(
                    known_metrics[
                        "parent_set_exact"
                    ]
                ),

            "known_k_accuracy":
                float(
                    known_metrics[
                        "k_accuracy"
                    ]
                ),

            "known_k_mae":
                float(
                    known_metrics[
                        "k_mae"
                    ]
                ),

            "known_false_unknown_rate":
                float(
                    known_metrics[
                        "false_unknown_rate"
                    ]
                ),

            "pseudo_component_accuracy":
                float(
                    pseudo_metrics[
                        "component_accuracy"
                    ]
                ),

            "pseudo_parent_set_f1":
                float(
                    pseudo_metrics[
                        "parent_set_f1"
                    ]
                ),

            "pseudo_parent_set_exact":
                float(
                    pseudo_metrics[
                        "parent_set_exact"
                    ]
                ),

            "pseudo_k_accuracy":
                float(
                    pseudo_metrics[
                        "k_accuracy"
                    ]
                ),

            "pseudo_k_mae":
                float(
                    pseudo_metrics[
                        "k_mae"
                    ]
                ),

            "pseudo_unknown_precision":
                float(
                    pseudo_metrics[
                        "unknown_precision"
                    ]
                ),

            "pseudo_unknown_recall":
                float(
                    pseudo_metrics[
                        "unknown_recall"
                    ]
                ),

            "pseudo_unknown_f1":
                float(
                    pseudo_metrics[
                        "unknown_f1"
                    ]
                ),

            "pseudo_unknown_known_macro_f1":
                float(
                    pseudo_metrics[
                        "unknown_known_macro_f1"
                    ]
                ),
        }


        parameter_grid_rows.append(
            row
        )


        selection_key = (
            row[
                "mean_parent_set_f1"
            ],

            row[
                "mean_k_accuracy"
            ],

            row[
                "pseudo_unknown_f1"
            ],

            row[
                "mean_component_accuracy"
            ],

            row[
                "lambda"
            ],

            -abs(
                row[
                    "alpha"
                ]
                -
                0.5
            ),
        )


        if (
            best_selection_key is None
            or
            selection_key
            >
            best_selection_key
        ):

            best_selection_key = (
                selection_key
            )

            best_record = (
                row
            )


parameter_grid = pd.DataFrame(
    parameter_grid_rows
)


if best_record is None:

    raise RuntimeError(
        "No Stage-1 parameter set selected"
    )


selected_alpha = float(
    best_record[
        "alpha"
    ]
)


selected_lambda = float(
    best_record[
        "lambda"
    ]
)


print()

print(
    "Selected alpha :",
    selected_alpha
)

print(
    "Selected lambda:",
    selected_lambda
)

print(
    "Mean parent F1 :",
    best_record[
        "mean_parent_set_f1"
    ]
)

print(
    "Mean K acc     :",
    best_record[
        "mean_k_accuracy"
    ]
)


# =========================================================
# Selected calibration predictions
# =========================================================

selected_known_metrics, known_component_rows, known_query_rows = (
    evaluate_view(
        precomputed_known[
            selected_alpha
        ],
        selected_lambda,
        pseudo_open=False,
        collect_predictions=True,
    )
)


selected_pseudo_metrics, pseudo_component_rows, pseudo_query_rows = (
    evaluate_view(
        precomputed_pseudo[
            selected_alpha
        ],
        selected_lambda,
        pseudo_open=True,
        collect_predictions=True,
    )
)


component_predictions = pd.DataFrame(
    known_component_rows
    +
    pseudo_component_rows
)


query_predictions = pd.DataFrame(
    known_query_rows
    +
    pseudo_query_rows
)


# =========================================================
# Safety
# =========================================================

if len(
    component_predictions
) != (
    EXPECTED_COMPONENTS
    *
    2
):

    raise RuntimeError(
        "Selected component-prediction "
        "row count mismatch"
    )


if len(
    query_predictions
) != (
    EXPECTED_QUERIES
    *
    2
):

    raise RuntimeError(
        "Selected query-prediction "
        "row count mismatch"
    )


if not set(
    parameter_grid[
        "alpha"
    ].unique()
) <= set(
    ALPHAS
):

    raise RuntimeError(
        "Unexpected alpha in grid"
    )


# =========================================================
# Boundary diagnostics
# =========================================================

lambda_is_grid_maximum = bool(
    math.isclose(
        selected_lambda,
        max(
            LAMBDAS
        ),
        abs_tol=1e-12,
    )
)


lambda_is_grid_minimum = bool(
    math.isclose(
        selected_lambda,
        min(
            LAMBDAS
        ),
        abs_tol=1e-12,
    )
)


# =========================================================
# Save
# =========================================================

OUTPUT_THRESHOLD_GRID_CSV.parent.mkdir(
    parents=True,
    exist_ok=True,
)


threshold_grid.to_csv(
    OUTPUT_THRESHOLD_GRID_CSV,
    index=False,
    encoding="utf-8-sig",
)


parameter_grid.to_csv(
    OUTPUT_PARAMETER_GRID_CSV,
    index=False,
    encoding="utf-8-sig",
)


component_predictions.to_csv(
    OUTPUT_COMPONENT_PREDICTIONS_CSV,
    index=False,
    encoding="utf-8-sig",
)


query_predictions.to_csv(
    OUTPUT_QUERY_PREDICTIONS_CSV,
    index=False,
    encoding="utf-8-sig",
)


# =========================================================
# Frozen parameter file
# =========================================================

parameter_file = {
    "stage1_parameters_frozen":
        True,

    "calibration_only":
        True,

    "test_used":
        False,

    "unknown_thresholds":
        {
            modality:
                float(
                    selected_thresholds[
                        modality
                    ]
                )

            for modality
            in MODALITIES
        },

    "alpha_absolute_distance":
        selected_alpha,

    "alpha_mean_regret":
        float(
            1.0
            -
            selected_alpha
        ),

    "parent_proliferation_lambda":
        selected_lambda,

    "maximum_known_parent_candidates":
        MAX_KNOWN_PARENTS,

    "unknown_rule":
        (
            "A candidate known parent is eligible "
            "for a component only when its absolute "
            "fused distance is <= the frozen "
            "modality-specific threshold. If no "
            "selected known parent is eligible, "
            "the component is assigned UNKNOWN."
        ),

    "known_assignment_cost":
        (
            "alpha * min(distance / threshold, 1) "
            "+ (1-alpha) * clipped MEAN_REGRET"
        ),

    "query_objective":
        (
            "sum(component assignment costs) "
            "+ lambda * number_of_selected_known_parents"
        ),

    "search_space":
        (
            "exhaustive known-parent subsets of size "
            "0 through 3; exact K is never supplied"
        ),
}


OUTPUT_PARAMETERS_JSON.write_text(
    json.dumps(
        parameter_file,
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)


# =========================================================
# Summary
# =========================================================

summary = {
    "stage1_calibration_complete":
        True,

    "stage1_parameters_frozen":
        True,

    "performance_evaluated":
        True,

    "performance_scope":
        "CALIBRATION_ONLY",

    "test_queries_scored":
        0,

    "unknown_heldout_queries_scored":
        0,

    "calibration_views": [
        "KNOWN_ONLY_40",
        "PSEUDO_UNKNOWN_39",
    ],

    "unknown_threshold_selection":
        (
            "modality-specific threshold maximizing "
            "binary macro-F1 for pseudo-UNKNOWN vs "
            "known components; ties use UNKNOWN F1, "
            "UNKNOWN recall, then lower threshold"
        ),

    "selected_unknown_thresholds":
        {
            modality:
                float(
                    selected_thresholds[
                        modality
                    ]
                )

            for modality
            in MODALITIES
        },

    "threshold_calibration_metrics":
        selected_threshold_metrics,

    "alpha_grid":
        ALPHAS,

    "lambda_grid":
        LAMBDAS,

    "parameter_grid_rows":
        int(
            len(
                parameter_grid
            )
        ),

    "selected_alpha":
        selected_alpha,

    "selected_lambda":
        selected_lambda,

    "lambda_selected_at_grid_minimum":
        lambda_is_grid_minimum,

    "lambda_selected_at_grid_maximum":
        lambda_is_grid_maximum,

    "selection_priority": [
        "mean parent-set F1 across KNOWN_ONLY_40 and PSEUDO_UNKNOWN_39",
        "mean K accuracy across both views",
        "pseudo-UNKNOWN component F1",
        "mean component accuracy",
        "larger lambda for parsimony under exact metric ties",
        "alpha nearest 0.5 under remaining ties",
    ],

    "selected_known_only_metrics":
        {
            key:
                float(
                    value
                )

            for key, value
            in selected_known_metrics.items()
        },

    "selected_pseudo_unknown_metrics":
        {
            key:
                float(
                    value
                )

            for key, value
            in selected_pseudo_metrics.items()
        },

    "primary_selection_metrics": {
        "mean_parent_set_f1":
            float(
                best_record[
                    "mean_parent_set_f1"
                ]
            ),

        "mean_k_accuracy":
            float(
                best_record[
                    "mean_k_accuracy"
                ]
            ),

        "mean_component_accuracy":
            float(
                best_record[
                    "mean_component_accuracy"
                ]
            ),

        "pseudo_unknown_f1":
            float(
                best_record[
                    "pseudo_unknown_f1"
                ]
            ),
    },

    "maximum_known_parents":
        MAX_KNOWN_PARENTS,

    "exact_k_exposed":
        False,

    "test_data_used_for_parameter_selection":
        False,

    "goals_met":
        bool(
            len(
                parameter_grid
            )
            > 0

            and

            selected_alpha
            in ALPHAS

            and

            selected_lambda
            in LAMBDAS

            and

            len(
                selected_thresholds
            )
            == 3

            and

            len(
                component_predictions
            )
            == (
                EXPECTED_COMPONENTS
                *
                2
            )

            and

            len(
                query_predictions
            )
            == (
                EXPECTED_QUERIES
                *
                2
            )
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
# Result
# =========================================================

print()

print(
    "======================================"
)

print(
    "PHASE 7D RESULT"
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
    "Threshold grid:",
    OUTPUT_THRESHOLD_GRID_CSV
)

print(
    "Parameter grid:",
    OUTPUT_PARAMETER_GRID_CSV
)

print(
    "Component predictions:",
    OUTPUT_COMPONENT_PREDICTIONS_CSV
)

print(
    "Query predictions:",
    OUTPUT_QUERY_PREDICTIONS_CSV
)

print(
    "Frozen parameters:",
    OUTPUT_PARAMETERS_JSON
)

print(
    "Summary:",
    OUTPUT_SUMMARY_JSON
)