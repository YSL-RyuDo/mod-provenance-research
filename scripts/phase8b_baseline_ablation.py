import json
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd


# =========================================================
# Inputs
# =========================================================

SCORE_CSV = Path(
    "results/phase7h_test_component_parent_scores.csv"
)

PRIVATE_MANIFEST_CSV = Path(
    "results/phase6l_materialized_private_manifest.csv"
)

QUERY_GT_CSV = Path(
    "results/phase6k_query_ground_truth.csv"
)

FINAL_QUERY_CSV = Path(
    "results/phase7h_final_query_predictions.csv"
)

FINAL_COMPONENT_CSV = Path(
    "results/phase7h_final_component_predictions.csv"
)

BETA0_QUERY_CSV = Path(
    "results/phase7h_beta0_query_predictions.csv"
)

BETA0_COMPONENT_CSV = Path(
    "results/phase7h_beta0_component_predictions.csv"
)

FINAL_PARAMETERS_JSON = Path(
    "results/phase7g_final_method_parameters.json"
)

PHASE7H_SUMMARY_JSON = Path(
    "results/phase7h_final_test_summary.json"
)


# =========================================================
# Outputs
# =========================================================

OUTPUT_METHOD_TABLE_CSV = Path(
    "results/phase8b_baseline_ablation_table.csv"
)

OUTPUT_SCENARIO_TABLE_CSV = Path(
    "results/phase8b_baseline_by_scenario.csv"
)

OUTPUT_K_TABLE_CSV = Path(
    "results/phase8b_baseline_by_k.csv"
)

OUTPUT_INDEPENDENT_COMPONENT_CSV = Path(
    "results/phase8b_independent_component_predictions.csv"
)

OUTPUT_INDEPENDENT_QUERY_CSV = Path(
    "results/phase8b_independent_query_predictions.csv"
)

OUTPUT_ORACLE_COMPONENT_CSV = Path(
    "results/phase8b_oracle_k_component_predictions.csv"
)

OUTPUT_ORACLE_QUERY_CSV = Path(
    "results/phase8b_oracle_k_query_predictions.csv"
)

OUTPUT_SUMMARY_JSON = Path(
    "results/phase8b_baseline_ablation_summary.json"
)


# =========================================================
# Constants
# =========================================================

UNKNOWN_LABEL = "UNKNOWN"

EXPECTED_QUERIES = 360
EXPECTED_COMPONENTS = 2520
EXPECTED_GALLERY_PROJECTS = 60

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


def safe_divide(a, b):

    if b == 0:
        return 0.0

    return float(a / b)


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

    if precision + recall == 0:

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


def unknown_binary_metrics(
    truth_labels,
    pred_labels,
):

    truth = np.array(
        [
            value == UNKNOWN_LABEL
            for value in truth_labels
        ],
        dtype=bool,
    )

    pred = np.array(
        [
            value == UNKNOWN_LABEL
            for value in pred_labels
        ],
        dtype=bool,
    )

    tp = int(
        np.logical_and(
            truth,
            pred,
        ).sum()
    )

    fp = int(
        np.logical_and(
            ~truth,
            pred,
        ).sum()
    )

    fn = int(
        np.logical_and(
            truth,
            ~pred,
        ).sum()
    )

    tn = int(
        np.logical_and(
            ~truth,
            ~pred,
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

        "tp":
            tp,

        "fp":
            fp,

        "fn":
            fn,

        "tn":
            tn,
    }


# =========================================================
# Load
# =========================================================

required_paths = [
    SCORE_CSV,
    PRIVATE_MANIFEST_CSV,
    QUERY_GT_CSV,
    FINAL_QUERY_CSV,
    FINAL_COMPONENT_CSV,
    BETA0_QUERY_CSV,
    BETA0_COMPONENT_CSV,
    FINAL_PARAMETERS_JSON,
    PHASE7H_SUMMARY_JSON,
]


for path in required_paths:

    if not path.exists():

        raise FileNotFoundError(
            f"Missing: {path}"
        )


scores = pd.read_csv(
    SCORE_CSV
)

manifest = pd.read_csv(
    PRIVATE_MANIFEST_CSV
)

query_gt = pd.read_csv(
    QUERY_GT_CSV
)

final_query = pd.read_csv(
    FINAL_QUERY_CSV
)

final_component = pd.read_csv(
    FINAL_COMPONENT_CSV
)

beta0_query = pd.read_csv(
    BETA0_QUERY_CSV
)

beta0_component = pd.read_csv(
    BETA0_COMPONENT_CSV
)


parameters = json.loads(
    FINAL_PARAMETERS_JSON.read_text(
        encoding="utf-8"
    )
)


phase7h = json.loads(
    PHASE7H_SUMMARY_JSON.read_text(
        encoding="utf-8"
    )
)


print(
    "======================================"
)

print(
    "Phase 8B - Baseline / Ablation"
)

print(
    "======================================"
)


# =========================================================
# Frozen parameters
# =========================================================

stage1 = parameters[
    "stage1"
]


THRESHOLDS = {
    key:
        float(value)

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


if abs(
    ALPHA - 0.75
) > EPSILON:

    raise RuntimeError(
        "Frozen alpha mismatch"
    )


if abs(
    REGRET_WEIGHT - 0.25
) > EPSILON:

    raise RuntimeError(
        "Frozen regret weight mismatch"
    )


if abs(
    LAMBDA - 0.5
) > EPSILON:

    raise RuntimeError(
        "Frozen lambda mismatch"
    )


if CANDIDATE_POOL_SIZE != 10:

    raise RuntimeError(
        "Frozen candidate M mismatch"
    )


# =========================================================
# TEST identities
# =========================================================

test_gt = query_gt[
    query_gt[
        "stage"
    ]
    == "TEST"
].copy()


if len(
    test_gt
) != EXPECTED_QUERIES:

    raise RuntimeError(
        "Expected 360 TEST queries"
    )


test_query_ids = set(
    test_gt[
        "query_id"
    ].astype(str)
)


test_manifest = manifest[
    manifest[
        "query_id"
    ]
    .astype(str)
    .isin(
        test_query_ids
    )
].copy()


if len(
    test_manifest
) != EXPECTED_COMPONENTS:

    raise RuntimeError(
        "Expected 2520 TEST components"
    )


# =========================================================
# GT maps
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

        "source":
            clean_text(
                row.source_fresh_id
            ),

        "modality":
            clean_text(
                row.modality
            ),
    }


query_info = {}


for row in test_gt.itertuples(
    index=False
):

    query_info[
        clean_text(
            row.query_id
        )
    ] = {
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
# Frozen component cost
# =========================================================

def component_cost(
    modality,
    distance,
    regret,
):

    modality = clean_text(
        modality
    )

    distance = float(
        distance
    )

    regret = float(
        regret
    )


    threshold = THRESHOLDS[
        modality
    ]


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
            distance
            /
            threshold,
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
            else
            1.0
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
        float(
            cost
        ),
        eligible,
    )


# =========================================================
# Prepare all query score structures
# =========================================================

prepared = {}


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
            EXPECTED_QUERIES,
        )


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


    if len(
        node_ids
    ) != 7:

        raise RuntimeError(
            f"{query_id}: "
            "expected 7 components"
        )


    candidates = sorted(
        group[
            "candidate_parent"
        ].astype(str).unique()
    )


    if len(
        candidates
    ) != EXPECTED_GALLERY_PROJECTS:

        raise RuntimeError(
            f"{query_id}: "
            "expected 60 gallery projects"
        )


    modalities = {}

    costs = {}

    eligible = {}


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


        costs[
            node_id
        ] = {}


        eligible[
            node_id
        ] = {}


        for row in node_group.itertuples(
            index=False
        ):

            parent = clean_text(
                row.candidate_parent
            )


            cost, is_eligible = (
                component_cost(
                    modality,
                    row.fused_parent_distance,
                    row.mean_regret,
                )
            )


            costs[
                node_id
            ][
                parent
            ] = cost


            eligible[
                node_id
            ][
                parent
            ] = is_eligible


    # -----------------------------------------------------
    # Frozen Phase 7E retrieval score
    # -----------------------------------------------------

    retrieval_score = {}


    for parent in candidates:

        parent_costs = sorted(
            costs[
                node_id
            ][
                parent
            ]

            for node_id
            in node_ids
        )


        retrieval_score[
            parent
        ] = float(
            np.mean(
                parent_costs[
                    :3
                ]
            )
        )


    ranked = sorted(
        candidates,
        key=lambda parent: (
            retrieval_score[
                parent
            ],
            parent,
        ),
    )


    top10 = ranked[
        :CANDIDATE_POOL_SIZE
    ]


    prepared[
        query_id
    ] = {
        "query_id":
            query_id,

        "node_ids":
            node_ids,

        "candidates":
            candidates,

        "top10":
            list(
                top10
            ),

        "modalities":
            modalities,

        "costs":
            costs,

        "eligible":
            eligible,
    }


# =========================================================
# Baseline 1:
# Independent Component Matching
#
# Each component independently selects the lowest-cost
# eligible parent from the full 60-project TEST gallery.
#
# No query-level parent-set constraint.
# No lambda.
# No Top-10 restriction.
# No graph.
# =========================================================

independent_component_rows = []
independent_query_rows = []


for query_id in sorted(
    test_query_ids
):

    query = prepared[
        query_id
    ]


    predictions = []


    for node_id in query[
        "node_ids"
    ]:

        valid_parents = [
            parent

            for parent
            in query[
                "candidates"
            ]

            if query[
                "eligible"
            ][
                node_id
            ][
                parent
            ]
        ]


        if not valid_parents:

            prediction = (
                UNKNOWN_LABEL
            )

        else:

            prediction = min(
                valid_parents,
                key=lambda parent: (
                    query[
                        "costs"
                    ][
                        node_id
                    ][
                        parent
                    ],
                    parent,
                ),
            )


        truth = (
            component_gt[
                (
                    query_id,
                    node_id,
                )
            ][
                "label"
            ]
        )


        predictions.append(
            prediction
        )


        independent_component_rows.append({
            "query_id":
                query_id,

            "scenario":
                query_info[
                    query_id
                ][
                    "scenario"
                ],

            "k_true":
                query_info[
                    query_id
                ][
                    "k_true"
                ],

            "node_id":
                node_id,

            "modality":
                query[
                    "modalities"
                ][
                    node_id
                ],

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


    truth_labels = [
        component_gt[
            (
                query_id,
                node_id,
            )
        ][
            "label"
        ]

        for node_id
        in query[
            "node_ids"
        ]
    ]


    true_set = set(
        truth_labels
    )

    pred_set = set(
        predictions
    )


    metrics = set_metrics(
        true_set,
        pred_set,
    )


    independent_query_rows.append({
        "query_id":
            query_id,

        "scenario":
            query_info[
                query_id
            ][
                "scenario"
            ],

        "k_true":
            query_info[
                query_id
            ][
                "k_true"
            ],

        "k_pred":
            int(
                len(
                    pred_set
                )
            ),

        "true_parent_set":
            json.dumps(
                sorted(
                    true_set
                )
            ),

        "predicted_parent_set":
            json.dumps(
                sorted(
                    pred_set
                )
            ),

        "parent_set_precision":
            metrics[
                "precision"
            ],

        "parent_set_recall":
            metrics[
                "recall"
            ],

        "parent_set_f1":
            metrics[
                "f1"
            ],

        "parent_set_exact":
            metrics[
                "exact"
            ],
    })


independent_component_df = pd.DataFrame(
    independent_component_rows
)

independent_query_df = pd.DataFrame(
    independent_query_rows
)


# =========================================================
# Baseline 2:
# Oracle Known-Parent Cardinality
#
# Diagnostic upper bound only.
#
# We reveal ONLY the number of visible/known parents
# contributing to the query.
#
# We do NOT reveal their identities.
#
# UNKNOWN remains threshold-based.
#
# Search space remains frozen Top-10.
# Graph beta = 0.
# Lambda is unnecessary because subset size is fixed.
# =========================================================

oracle_component_rows = []
oracle_query_rows = []


for query_id in sorted(
    test_query_ids
):

    query = prepared[
        query_id
    ]


    truth_labels = [
        component_gt[
            (
                query_id,
                node_id,
            )
        ][
            "label"
        ]

        for node_id
        in query[
            "node_ids"
        ]
    ]


    known_true_parents = {
        label
        for label in truth_labels
        if label
        != UNKNOWN_LABEL
    }


    oracle_known_k = len(
        known_true_parents
    )


    best_solution = None
    best_key = None


    if oracle_known_k > len(
        query[
            "top10"
        ]
    ):

        raise RuntimeError(
            f"{query_id}: oracle K exceeds pool"
        )


    for subset in combinations(
        query[
            "top10"
        ],
        oracle_known_k,
    ):

        assignments = []

        total_cost = 0.0


        for node_id in query[
            "node_ids"
        ]:

            valid_parents = [
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


            if not valid_parents:

                assignments.append(
                    UNKNOWN_LABEL
                )

                total_cost += 1.0

                continue


            best_parent = min(
                valid_parents,
                key=lambda parent: (
                    query[
                        "costs"
                    ][
                        node_id
                    ][
                        parent
                    ],
                    parent,
                ),
            )


            best_cost = float(
                query[
                    "costs"
                ][
                    node_id
                ][
                    best_parent
                ]
            )


            assignments.append(
                best_parent
            )

            total_cost += (
                best_cost
            )


        key = (
            float(
                total_cost
            ),
            tuple(
                subset
            ),
        )


        if (
            best_key is None
            or
            key
            <
            best_key
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

                "cost":
                    float(
                        total_cost
                    ),
            }


    if best_solution is None:

        # This only occurs for Kknown=0.
        if oracle_known_k == 0:

            best_solution = {
                "subset":
                    tuple(),

                "assignments":
                    [
                        UNKNOWN_LABEL
                        for _ in query[
                            "node_ids"
                        ]
                    ],

                "cost":
                    float(
                        len(
                            query[
                                "node_ids"
                            ]
                        )
                    ),
            }

        else:

            raise RuntimeError(
                f"{query_id}: "
                "no oracle solution"
            )


    predictions = (
        best_solution[
            "assignments"
        ]
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

        oracle_component_rows.append({
            "query_id":
                query_id,

            "scenario":
                query_info[
                    query_id
                ][
                    "scenario"
                ],

            "k_true":
                query_info[
                    query_id
                ][
                    "k_true"
                ],

            "oracle_known_k":
                int(
                    oracle_known_k
                ),

            "node_id":
                node_id,

            "modality":
                query[
                    "modalities"
                ][
                    node_id
                ],

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


    true_set = set(
        truth_labels
    )

    pred_set = set(
        predictions
    )


    metrics = set_metrics(
        true_set,
        pred_set,
    )


    oracle_query_rows.append({
        "query_id":
            query_id,

        "scenario":
            query_info[
                query_id
            ][
                "scenario"
            ],

        "k_true":
            query_info[
                query_id
            ][
                "k_true"
            ],

        "oracle_known_k":
            int(
                oracle_known_k
            ),

        "k_pred":
            int(
                len(
                    pred_set
                )
            ),

        "selected_known_subset":
            json.dumps(
                list(
                    best_solution[
                        "subset"
                    ]
                )
            ),

        "true_parent_set":
            json.dumps(
                sorted(
                    true_set
                )
            ),

        "predicted_parent_set":
            json.dumps(
                sorted(
                    pred_set
                )
            ),

        "parent_set_precision":
            metrics[
                "precision"
            ],

        "parent_set_recall":
            metrics[
                "recall"
            ],

        "parent_set_f1":
            metrics[
                "f1"
            ],

        "parent_set_exact":
            metrics[
                "exact"
            ],
    })


oracle_component_df = pd.DataFrame(
    oracle_component_rows
)

oracle_query_df = pd.DataFrame(
    oracle_query_rows
)


# =========================================================
# Unified evaluator
# =========================================================

def evaluate_method(
    method_name,
    component_df,
    query_df,
):

    truth_labels = (
        component_df[
            "ground_truth_label"
        ]
        .astype(str)
        .tolist()
    )

    pred_labels = (
        component_df[
            "predicted_label"
        ]
        .astype(str)
        .tolist()
    )


    component_accuracy = float(
        (
            component_df[
                "ground_truth_label"
            ].astype(str)
            ==
            component_df[
                "predicted_label"
            ].astype(str)
        ).mean()
    )


    unknown = (
        unknown_binary_metrics(
            truth_labels,
            pred_labels,
        )
    )


    parent_set_f1 = float(
        query_df[
            "parent_set_f1"
        ].astype(float).mean()
    )


    parent_set_exact = float(
        query_df[
            "parent_set_exact"
        ]
        .map(
            as_bool
        )
        .mean()
    )


    k_accuracy = float(
        (
            query_df[
                "k_true"
            ].astype(int)
            ==
            query_df[
                "k_pred"
            ].astype(int)
        ).mean()
    )


    k_mae = float(
        np.abs(
            query_df[
                "k_true"
            ].astype(int)
            -
            query_df[
                "k_pred"
            ].astype(int)
        ).mean()
    )


    return {
        "method":
            method_name,

        "component_accuracy":
            component_accuracy,

        "parent_set_f1":
            parent_set_f1,

        "parent_set_exact":
            parent_set_exact,

        "k_accuracy":
            k_accuracy,

        "k_mae":
            k_mae,

        "unknown_precision":
            float(
                unknown[
                    "precision"
                ]
            ),

        "unknown_recall":
            float(
                unknown[
                    "recall"
                ]
            ),

        "unknown_f1":
            float(
                unknown[
                    "f1"
                ]
            ),
    }


# =========================================================
# Existing frozen methods
# =========================================================

# Normalize booleans if CSV loaded them as strings.
for dataframe in [
    final_query,
    beta0_query,
]:

    dataframe[
        "parent_set_exact"
    ] = (
        dataframe[
            "parent_set_exact"
        ].map(
            as_bool
        )
    )


methods = []


methods.append(
    evaluate_method(
        "Independent_Component",
        independent_component_df,
        independent_query_df,
    )
)


methods.append(
    evaluate_method(
        "Hierarchical_Content_Top10_Beta0",
        beta0_component,
        beta0_query,
    )
)


methods.append(
    evaluate_method(
        "Final_Graph_Beta0.1",
        final_component,
        final_query,
    )
)


methods.append(
    evaluate_method(
        "Oracle_KnownParentCount_Content",
        oracle_component_df,
        oracle_query_df,
    )
)


method_table = pd.DataFrame(
    methods
)


# =========================================================
# Cross-check frozen Phase 7H methods
# =========================================================

phase7h_content = phase7h[
    "content_only_same_top10_beta_0"
]

phase7h_final = phase7h[
    "final_method_beta_0_1"
]


content_row = method_table[
    method_table[
        "method"
    ]
    == "Hierarchical_Content_Top10_Beta0"
].iloc[0]


final_row = method_table[
    method_table[
        "method"
    ]
    == "Final_Graph_Beta0.1"
].iloc[0]


crosscheck_metrics = [
    "component_accuracy",
    "parent_set_f1",
    "parent_set_exact",
    "k_accuracy",
    "k_mae",
    "unknown_f1",
]


for metric in crosscheck_metrics:

    if not np.isclose(
        float(
            content_row[
                metric
            ]
        ),
        float(
            phase7h_content[
                metric
            ]
        ),
        atol=1e-12,
        rtol=0.0,
    ):

        raise RuntimeError(
            f"Content-only cross-check "
            f"failed: {metric}"
        )


    if not np.isclose(
        float(
            final_row[
                metric
            ]
        ),
        float(
            phase7h_final[
                metric
            ]
        ),
        atol=1e-12,
        rtol=0.0,
    ):

        raise RuntimeError(
            f"Final graph cross-check "
            f"failed: {metric}"
        )


print()

print(
    "Phase 7H frozen-method cross-check: PASS"
)


# =========================================================
# Scenario tables
# =========================================================

method_sources = {
    "Independent_Component":
        (
            independent_component_df,
            independent_query_df,
        ),

    "Hierarchical_Content_Top10_Beta0":
        (
            beta0_component,
            beta0_query,
        ),

    "Final_Graph_Beta0.1":
        (
            final_component,
            final_query,
        ),

    "Oracle_KnownParentCount_Content":
        (
            oracle_component_df,
            oracle_query_df,
        ),
}


scenario_rows = []


for method_name, (
    component_df,
    query_df
) in method_sources.items():

    scenarios = sorted(
        query_df[
            "scenario"
        ].astype(str).unique()
    )


    for scenario in scenarios:

        q = query_df[
            query_df[
                "scenario"
            ].astype(str)
            == scenario
        ]


        c = component_df[
            component_df[
                "scenario"
            ].astype(str)
            == scenario
        ]


        metrics = evaluate_method(
            method_name,
            c,
            q,
        )


        metrics[
            "scenario"
        ] = scenario


        metrics[
            "queries"
        ] = int(
            len(
                q
            )
        )


        scenario_rows.append(
            metrics
        )


scenario_table = pd.DataFrame(
    scenario_rows
)


# =========================================================
# K tables
# =========================================================

k_rows = []


for method_name, (
    component_df,
    query_df
) in method_sources.items():

    for k_true in [
        1,
        2,
        3,
    ]:

        q = query_df[
            query_df[
                "k_true"
            ].astype(int)
            == k_true
        ]


        query_ids = set(
            q[
                "query_id"
            ].astype(str)
        )


        c = component_df[
            component_df[
                "query_id"
            ].astype(str)
            .isin(
                query_ids
            )
        ]


        metrics = evaluate_method(
            method_name,
            c,
            q,
        )


        metrics[
            "k_true"
        ] = int(
            k_true
        )


        metrics[
            "queries"
        ] = int(
            len(
                q
            )
        )


        k_rows.append(
            metrics
        )


k_table = pd.DataFrame(
    k_rows
)


# =========================================================
# Key deltas
# =========================================================

method_index = (
    method_table
    .set_index(
        "method"
    )
)


independent = method_index.loc[
    "Independent_Component"
]


content = method_index.loc[
    "Hierarchical_Content_Top10_Beta0"
]


final = method_index.loc[
    "Final_Graph_Beta0.1"
]


oracle = method_index.loc[
    "Oracle_KnownParentCount_Content"
]


hierarchy_minus_independent = {
    metric:
        float(
            content[
                metric
            ]
            -
            independent[
                metric
            ]
        )

    for metric in crosscheck_metrics
}


graph_minus_content = {
    metric:
        float(
            final[
                metric
            ]
            -
            content[
                metric
            ]
        )

    for metric in crosscheck_metrics
}


oracle_minus_content = {
    metric:
        float(
            oracle[
                metric
            ]
            -
            content[
                metric
            ]
        )

    for metric in crosscheck_metrics
}


# =========================================================
# Save
# =========================================================

OUTPUT_METHOD_TABLE_CSV.parent.mkdir(
    parents=True,
    exist_ok=True,
)


method_table.to_csv(
    OUTPUT_METHOD_TABLE_CSV,
    index=False,
    encoding="utf-8-sig",
)


scenario_table.to_csv(
    OUTPUT_SCENARIO_TABLE_CSV,
    index=False,
    encoding="utf-8-sig",
)


k_table.to_csv(
    OUTPUT_K_TABLE_CSV,
    index=False,
    encoding="utf-8-sig",
)


independent_component_df.to_csv(
    OUTPUT_INDEPENDENT_COMPONENT_CSV,
    index=False,
    encoding="utf-8-sig",
)


independent_query_df.to_csv(
    OUTPUT_INDEPENDENT_QUERY_CSV,
    index=False,
    encoding="utf-8-sig",
)


oracle_component_df.to_csv(
    OUTPUT_ORACLE_COMPONENT_CSV,
    index=False,
    encoding="utf-8-sig",
)


oracle_query_df.to_csv(
    OUTPUT_ORACLE_QUERY_CSV,
    index=False,
    encoding="utf-8-sig",
)


# =========================================================
# Summary
# =========================================================

summary = {
    "baseline_ablation_complete":
        True,

    "performance_scope":
        "FROZEN_TEST_DIAGNOSTIC",

    "test_rescored_from_frozen_component_parent_scores":
        True,

    "method_parameters_changed":
        False,

    "methods": {
        row[
            "method"
        ]: {
            key:
                float(
                    value
                )

            for key, value
            in row.items()

            if key
            != "method"
        }

        for row
        in methods
    },

    "hierarchical_content_minus_independent":
        hierarchy_minus_independent,

    "graph_minus_hierarchical_content":
        graph_minus_content,

    "oracle_known_parent_count_minus_content":
        oracle_minus_content,

    "baseline_definitions": {
        "Independent_Component":
            (
                "Each component independently chooses "
                "the lowest-cost eligible parent from "
                "all 60 TEST gallery projects. "
                "No query-level parent-set constraint, "
                "no candidate-pool restriction, "
                "no proliferation penalty, and no graph."
            ),

        "Hierarchical_Content_Top10_Beta0":
            (
                "Frozen Top-10 retrieval followed by "
                "unknown-K parent-set optimization with "
                "the frozen lambda; graph beta=0."
            ),

        "Final_Graph_Beta0.1":
            (
                "Frozen final method using Top-10 "
                "retrieval, unknown-K parent-set "
                "optimization and boundary-aware "
                "graph beta=0.1."
            ),

        "Oracle_KnownParentCount_Content":
            (
                "Diagnostic upper bound. The method "
                "is given only the number of true "
                "registered/known parents in each query, "
                "not their identities. It searches the "
                "same frozen Top-10 candidate pool with "
                "content evidence only."
            ),
    },

    "oracle_is_deployable_method":
        False,

    "oracle_uses_ground_truth_cardinality":
        True,

    "phase7h_frozen_crosscheck_passed":
        True,

    "goals_met":
        bool(
            len(
                method_table
            )
            == 4

            and
            len(
                independent_component_df
            )
            == EXPECTED_COMPONENTS

            and
            len(
                oracle_component_df
            )
            == EXPECTED_COMPONENTS

            and
            len(
                independent_query_df
            )
            == EXPECTED_QUERIES

            and
            len(
                oracle_query_df
            )
            == EXPECTED_QUERIES
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
    "PHASE 8B RESULT"
)

print(
    "======================================"
)


print()

print(
    method_table.to_string(
        index=False
    )
)


print()

print(
    "Hierarchy - Independent:"
)

print(
    json.dumps(
        hierarchy_minus_independent,
        ensure_ascii=False,
        indent=2,
    )
)


print()

print(
    "Oracle-K - Content:"
)

print(
    json.dumps(
        oracle_minus_content,
        ensure_ascii=False,
        indent=2,
    )
)


print()

print(
    "Main table:",
    OUTPUT_METHOD_TABLE_CSV
)

print(
    "Scenario table:",
    OUTPUT_SCENARIO_TABLE_CSV
)

print(
    "K table:",
    OUTPUT_K_TABLE_CSV
)

print(
    "Summary:",
    OUTPUT_SUMMARY_JSON
)