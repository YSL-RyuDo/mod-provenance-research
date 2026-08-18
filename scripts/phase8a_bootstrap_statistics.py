import json
from pathlib import Path

import numpy as np
import pandas as pd


# =========================================================
# Inputs
# =========================================================

FINAL_COMPONENT_CSV = Path(
    "results/phase7h_final_component_predictions.csv"
)

FINAL_QUERY_CSV = Path(
    "results/phase7h_final_query_predictions.csv"
)

BETA0_COMPONENT_CSV = Path(
    "results/phase7h_beta0_component_predictions.csv"
)

BETA0_QUERY_CSV = Path(
    "results/phase7h_beta0_query_predictions.csv"
)

PHASE7H_SUMMARY_JSON = Path(
    "results/phase7h_final_test_summary.json"
)


# =========================================================
# Outputs
# =========================================================

OUTPUT_REPLICATES_CSV = Path(
    "results/phase8a_bootstrap_replicates.csv"
)

OUTPUT_SUMMARY_JSON = Path(
    "results/phase8a_bootstrap_summary.json"
)


# =========================================================
# Frozen statistical protocol
# =========================================================

BOOTSTRAP_REPLICATES = 10000
RANDOM_SEED = 20260813

CI_LOW = 2.5
CI_HIGH = 97.5

UNKNOWN_LABEL = "UNKNOWN"

EXPECTED_QUERIES = 360
EXPECTED_COMPONENTS = 2520

EXPECTED_SCENARIOS = {
    "TEST_KNOWN_K1": 60,
    "TEST_KNOWN_K2": 60,
    "TEST_KNOWN_K3": 60,
    "TEST_MIXED_1K1U": 60,
    "TEST_MIXED_2K1U": 60,
    "TEST_UNKNOWN_K1": 60,
}


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


def binary_unknown_metrics(
    truth_labels,
    pred_labels,
):

    truth_unknown = np.asarray(
        [
            value == UNKNOWN_LABEL
            for value in truth_labels
        ],
        dtype=bool,
    )

    pred_unknown = np.asarray(
        [
            value == UNKNOWN_LABEL
            for value in pred_labels
        ],
        dtype=bool,
    )


    tp = int(
        np.logical_and(
            truth_unknown,
            pred_unknown,
        ).sum()
    )

    fp = int(
        np.logical_and(
            ~truth_unknown,
            pred_unknown,
        ).sum()
    )

    fn = int(
        np.logical_and(
            truth_unknown,
            ~pred_unknown,
        ).sum()
    )

    tn = int(
        np.logical_and(
            ~truth_unknown,
            ~pred_unknown,
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


def percentile_interval(values):

    values = np.asarray(
        values,
        dtype=np.float64,
    )

    return {
        "lower_95":
            float(
                np.percentile(
                    values,
                    CI_LOW,
                )
            ),

        "upper_95":
            float(
                np.percentile(
                    values,
                    CI_HIGH,
                )
            ),

        "bootstrap_mean":
            float(
                np.mean(
                    values
                )
            ),

        "bootstrap_std":
            float(
                np.std(
                    values,
                    ddof=1,
                )
            ),
    }


def delta_summary(values):

    values = np.asarray(
        values,
        dtype=np.float64,
    )

    result = percentile_interval(
        values
    )

    result.update({
        "probability_delta_gt_zero":
            float(
                np.mean(
                    values > 0.0
                )
            ),

        "probability_delta_ge_zero":
            float(
                np.mean(
                    values >= 0.0
                )
            ),

        "probability_delta_lt_zero":
            float(
                np.mean(
                    values < 0.0
                )
            ),

        "ci_excludes_zero":
            bool(
                (
                    result[
                        "lower_95"
                    ]
                    > 0.0
                )
                or
                (
                    result[
                        "upper_95"
                    ]
                    < 0.0
                )
            ),

        "direction_if_ci_excludes_zero":
            (
                "POSITIVE"
                if (
                    result[
                        "lower_95"
                    ]
                    > 0.0
                )
                else
                (
                    "NEGATIVE"
                    if (
                        result[
                            "upper_95"
                        ]
                        < 0.0
                    )
                    else
                    "INCONCLUSIVE"
                )
            ),
    })

    return result


# =========================================================
# Load
# =========================================================

for path in [
    FINAL_COMPONENT_CSV,
    FINAL_QUERY_CSV,
    BETA0_COMPONENT_CSV,
    BETA0_QUERY_CSV,
    PHASE7H_SUMMARY_JSON,
]:

    if not path.exists():

        raise FileNotFoundError(
            f"Missing: {path}"
        )


final_components = pd.read_csv(
    FINAL_COMPONENT_CSV
)

final_queries = pd.read_csv(
    FINAL_QUERY_CSV
)

beta0_components = pd.read_csv(
    BETA0_COMPONENT_CSV
)

beta0_queries = pd.read_csv(
    BETA0_QUERY_CSV
)


phase7h_summary = json.loads(
    PHASE7H_SUMMARY_JSON.read_text(
        encoding="utf-8"
    )
)


print(
    "======================================"
)

print(
    "Phase 8A - Frozen TEST Bootstrap"
)

print(
    "======================================"
)


# =========================================================
# Basic validation
# =========================================================

if len(
    final_components
) != EXPECTED_COMPONENTS:

    raise RuntimeError(
        "Final component count mismatch"
    )


if len(
    beta0_components
) != EXPECTED_COMPONENTS:

    raise RuntimeError(
        "Beta0 component count mismatch"
    )


if len(
    final_queries
) != EXPECTED_QUERIES:

    raise RuntimeError(
        "Final query count mismatch"
    )


if len(
    beta0_queries
) != EXPECTED_QUERIES:

    raise RuntimeError(
        "Beta0 query count mismatch"
    )


final_query_ids = set(
    final_queries[
        "query_id"
    ].astype(str)
)


beta0_query_ids = set(
    beta0_queries[
        "query_id"
    ].astype(str)
)


if (
    final_query_ids
    != beta0_query_ids
):

    raise RuntimeError(
        "Final and beta0 query identities differ"
    )


component_query_ids = set(
    final_components[
        "query_id"
    ].astype(str)
)


if (
    component_query_ids
    != final_query_ids
):

    raise RuntimeError(
        "Component/query identity mismatch"
    )


# =========================================================
# Scenario validation
# =========================================================

scenario_counts = (
    final_queries[
        "scenario"
    ]
    .astype(str)
    .value_counts()
    .to_dict()
)


if scenario_counts != EXPECTED_SCENARIOS:

    raise RuntimeError(
        "Unexpected TEST scenario distribution: "
        f"{scenario_counts}"
    )


# =========================================================
# Component pairing validation
# =========================================================

component_key_columns = [
    "query_id",
    "node_id",
]


final_component_keys = (
    final_components[
        component_key_columns
    ]
    .astype(str)
)


beta0_component_keys = (
    beta0_components[
        component_key_columns
    ]
    .astype(str)
)


final_key_set = set(
    map(
        tuple,
        final_component_keys.to_numpy()
    )
)


beta0_key_set = set(
    map(
        tuple,
        beta0_component_keys.to_numpy()
    )
)


if (
    final_key_set
    != beta0_key_set
):

    raise RuntimeError(
        "Final and beta0 component keys differ"
    )


# =========================================================
# Normalize IDs
# =========================================================

for dataframe in [
    final_components,
    beta0_components,
    final_queries,
    beta0_queries,
]:

    dataframe[
        "query_id"
    ] = (
        dataframe[
            "query_id"
        ].astype(str)
    )


# =========================================================
# Per-query sufficient statistics
#
# Bootstrap samples QUERY IDs.
#
# All seven components belonging to a query are carried
# together. This avoids treating 2520 components as
# independent observations.
# =========================================================

def build_query_records(
    query_df,
    component_df,
):

    records = {}


    query_df = (
        query_df
        .sort_values(
            "query_id",
            kind="stable",
        )
    )


    for query_row in query_df.itertuples(
        index=False
    ):

        query_id = clean_text(
            query_row.query_id
        )


        component_group = component_df[
            component_df[
                "query_id"
            ]
            == query_id
        ].copy()


        if len(
            component_group
        ) != 7:

            raise RuntimeError(
                f"{query_id}: expected 7 components"
            )


        component_truth = (
            component_group[
                "ground_truth_label"
            ]
            .astype(str)
            .tolist()
        )


        component_pred = (
            component_group[
                "predicted_label"
            ]
            .astype(str)
            .tolist()
        )


        component_correct = int(
            (
                component_group[
                    "ground_truth_label"
                ].astype(str)
                ==
                component_group[
                    "predicted_label"
                ].astype(str)
            ).sum()
        )


        unknown_metrics = (
            binary_unknown_metrics(
                component_truth,
                component_pred,
            )
        )


        records[
            query_id
        ] = {
            "query_id":
                query_id,

            "scenario":
                clean_text(
                    query_row.scenario
                ),

            "k_true":
                int(
                    query_row.k_true
                ),

            "k_pred":
                int(
                    query_row.k_pred
                ),

            "component_correct":
                component_correct,

            "component_total":
                7,

            "parent_set_f1":
                float(
                    query_row.parent_set_f1
                ),

            "parent_set_exact":
                int(
                    bool(
                        query_row.parent_set_exact
                    )
                ),

            "k_correct":
                int(
                    int(
                        query_row.k_true
                    )
                    ==
                    int(
                        query_row.k_pred
                    )
                ),

            "k_absolute_error":
                abs(
                    int(
                        query_row.k_true
                    )
                    -
                    int(
                        query_row.k_pred
                    )
                ),

            "unknown_tp":
                unknown_metrics[
                    "tp"
                ],

            "unknown_fp":
                unknown_metrics[
                    "fp"
                ],

            "unknown_fn":
                unknown_metrics[
                    "fn"
                ],

            "unknown_tn":
                unknown_metrics[
                    "tn"
                ],
        }


    return records


final_records = build_query_records(
    final_queries,
    final_components,
)


beta0_records = build_query_records(
    beta0_queries,
    beta0_components,
)


if set(
    final_records.keys()
) != set(
    beta0_records.keys()
):

    raise RuntimeError(
        "Final/beta0 record identities differ"
    )


# =========================================================
# Scenario buckets
#
# Stratified bootstrap:
# resample 60 queries WITH replacement inside each of
# the six frozen TEST scenarios.
#
# Thus every bootstrap replicate retains the original
# 60 x 6 scenario composition.
# =========================================================

scenario_query_ids = {}


for scenario in EXPECTED_SCENARIOS:

    ids = sorted(
        final_queries[
            final_queries[
                "scenario"
            ].astype(str)
            == scenario
        ][
            "query_id"
        ].astype(str)
        .tolist()
    )


    if len(ids) != 60:

        raise RuntimeError(
            f"{scenario}: expected 60 queries"
        )


    scenario_query_ids[
        scenario
    ] = np.array(
        ids,
        dtype=object,
    )


# =========================================================
# Aggregate sampled query records
# =========================================================

def aggregate_sample(
    sampled_ids,
    records,
):

    component_correct = 0
    component_total = 0

    parent_f1_sum = 0.0
    parent_exact_sum = 0

    k_correct_sum = 0
    k_absolute_error_sum = 0.0

    unknown_tp = 0
    unknown_fp = 0
    unknown_fn = 0
    unknown_tn = 0


    query_count = len(
        sampled_ids
    )


    for query_id in sampled_ids:

        record = records[
            str(
                query_id
            )
        ]


        component_correct += (
            record[
                "component_correct"
            ]
        )

        component_total += (
            record[
                "component_total"
            ]
        )


        parent_f1_sum += (
            record[
                "parent_set_f1"
            ]
        )

        parent_exact_sum += (
            record[
                "parent_set_exact"
            ]
        )


        k_correct_sum += (
            record[
                "k_correct"
            ]
        )

        k_absolute_error_sum += (
            record[
                "k_absolute_error"
            ]
        )


        unknown_tp += (
            record[
                "unknown_tp"
            ]
        )

        unknown_fp += (
            record[
                "unknown_fp"
            ]
        )

        unknown_fn += (
            record[
                "unknown_fn"
            ]
        )

        unknown_tn += (
            record[
                "unknown_tn"
            ]
        )


    component_accuracy = (
        safe_divide(
            component_correct,
            component_total,
        )
    )


    parent_set_f1 = (
        safe_divide(
            parent_f1_sum,
            query_count,
        )
    )


    parent_set_exact = (
        safe_divide(
            parent_exact_sum,
            query_count,
        )
    )


    k_accuracy = (
        safe_divide(
            k_correct_sum,
            query_count,
        )
    )


    k_mae = (
        safe_divide(
            k_absolute_error_sum,
            query_count,
        )
    )


    unknown_precision = safe_divide(
        unknown_tp,
        unknown_tp + unknown_fp,
    )


    unknown_recall = safe_divide(
        unknown_tp,
        unknown_tp + unknown_fn,
    )


    if (
        unknown_precision
        +
        unknown_recall
        == 0
    ):

        unknown_f1 = 0.0

    else:

        unknown_f1 = (
            2.0
            *
            unknown_precision
            *
            unknown_recall
            /
            (
                unknown_precision
                +
                unknown_recall
            )
        )


    return {
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
            unknown_precision,

        "unknown_recall":
            unknown_recall,

        "unknown_f1":
            unknown_f1,
    }


# =========================================================
# Point estimates from original TEST
# =========================================================

original_ids = sorted(
    final_records.keys()
)


final_point = aggregate_sample(
    original_ids,
    final_records,
)


beta0_point = aggregate_sample(
    original_ids,
    beta0_records,
)


point_delta = {
    metric:
        float(
            final_point[
                metric
            ]
            -
            beta0_point[
                metric
            ]
        )

    for metric in [
        "component_accuracy",
        "parent_set_f1",
        "parent_set_exact",
        "k_accuracy",
        "k_mae",
        "unknown_precision",
        "unknown_recall",
        "unknown_f1",
    ]
}


# =========================================================
# Cross-check against Phase 7H summary
# =========================================================

phase7h_final = (
    phase7h_summary[
        "final_method_beta_0_1"
    ]
)


cross_checks = {
    "component_accuracy":
        float(
            phase7h_final[
                "component_accuracy"
            ]
        ),

    "parent_set_f1":
        float(
            phase7h_final[
                "parent_set_f1"
            ]
        ),

    "parent_set_exact":
        float(
            phase7h_final[
                "parent_set_exact"
            ]
        ),

    "k_accuracy":
        float(
            phase7h_final[
                "k_accuracy"
            ]
        ),

    "k_mae":
        float(
            phase7h_final[
                "k_mae"
            ]
        ),

    "unknown_precision":
        float(
            phase7h_final[
                "unknown_precision"
            ]
        ),

    "unknown_recall":
        float(
            phase7h_final[
                "unknown_recall"
            ]
        ),

    "unknown_f1":
        float(
            phase7h_final[
                "unknown_f1"
            ]
        ),
}


for metric, expected_value in (
    cross_checks.items()
):

    actual_value = final_point[
        metric
    ]


    if not np.isclose(
        actual_value,
        expected_value,
        rtol=0.0,
        atol=1e-12,
    ):

        raise RuntimeError(
            f"Phase 7H cross-check failed "
            f"for {metric}: "
            f"{actual_value} vs "
            f"{expected_value}"
        )


print()

print(
    "Phase 7H point-estimate cross-check: PASS"
)


# =========================================================
# Bootstrap
# =========================================================

rng = np.random.default_rng(
    RANDOM_SEED
)


replicate_rows = []


FINAL_METRICS = [
    "component_accuracy",
    "parent_set_f1",
    "parent_set_exact",
    "k_accuracy",
    "k_mae",
    "unknown_precision",
    "unknown_recall",
    "unknown_f1",
]


DELTA_METRICS = [
    "component_accuracy",
    "parent_set_f1",
    "parent_set_exact",
    "k_accuracy",
    "k_mae",
    "unknown_f1",
]


for replicate_index in range(
    BOOTSTRAP_REPLICATES
):

    if (
        replicate_index == 0
        or
        (
            replicate_index + 1
        )
        % 1000
        == 0
    ):

        print(
            "bootstrap",
            replicate_index + 1,
            "/",
            BOOTSTRAP_REPLICATES,
        )


    sampled_ids = []


    for scenario in EXPECTED_SCENARIOS:

        ids = scenario_query_ids[
            scenario
        ]


        sampled = rng.choice(
            ids,
            size=len(ids),
            replace=True,
        )


        sampled_ids.extend(
            sampled.tolist()
        )


    final_metrics = aggregate_sample(
        sampled_ids,
        final_records,
    )


    beta0_metrics = aggregate_sample(
        sampled_ids,
        beta0_records,
    )


    row = {
        "replicate":
            int(
                replicate_index
            )
    }


    for metric in FINAL_METRICS:

        row[
            "final_"
            +
            metric
        ] = float(
            final_metrics[
                metric
            ]
        )


        row[
            "beta0_"
            +
            metric
        ] = float(
            beta0_metrics[
                metric
            ]
        )


    for metric in DELTA_METRICS:

        row[
            "delta_"
            +
            metric
        ] = float(
            final_metrics[
                metric
            ]
            -
            beta0_metrics[
                metric
            ]
        )


    replicate_rows.append(
        row
    )


replicates = pd.DataFrame(
    replicate_rows
)


# =========================================================
# Final-method CI
# =========================================================

final_ci = {}


for metric in FINAL_METRICS:

    column = (
        "final_"
        +
        metric
    )


    interval = percentile_interval(
        replicates[
            column
        ].to_numpy(
            dtype=float
        )
    )


    interval[
        "point_estimate"
    ] = float(
        final_point[
            metric
        ]
    )


    final_ci[
        metric
    ] = interval


# =========================================================
# Content-only CI
# =========================================================

beta0_ci = {}


for metric in FINAL_METRICS:

    column = (
        "beta0_"
        +
        metric
    )


    interval = percentile_interval(
        replicates[
            column
        ].to_numpy(
            dtype=float
        )
    )


    interval[
        "point_estimate"
    ] = float(
        beta0_point[
            metric
        ]
    )


    beta0_ci[
        metric
    ] = interval


# =========================================================
# Paired graph-contribution CI
# =========================================================

delta_ci = {}


for metric in DELTA_METRICS:

    column = (
        "delta_"
        +
        metric
    )


    result = delta_summary(
        replicates[
            column
        ].to_numpy(
            dtype=float
        )
    )


    result[
        "point_estimate"
    ] = float(
        point_delta[
            metric
        ]
    )


    delta_ci[
        metric
    ] = result


# =========================================================
# Graph interpretation
#
# Primary metric was frozen before TEST:
# parent_set_f1
# =========================================================

graph_primary = (
    delta_ci[
        "parent_set_f1"
    ]
)


if (
    graph_primary[
        "lower_95"
    ]
    > 0.0
):

    graph_statistical_interpretation = (
        "POSITIVE_CI_EXCLUDES_ZERO"
    )

elif (
    graph_primary[
        "upper_95"
    ]
    < 0.0
):

    graph_statistical_interpretation = (
        "NEGATIVE_CI_EXCLUDES_ZERO"
    )

else:

    graph_statistical_interpretation = (
        "CI_INCLUDES_ZERO"
    )


# =========================================================
# Save
# =========================================================

OUTPUT_REPLICATES_CSV.parent.mkdir(
    parents=True,
    exist_ok=True,
)


replicates.to_csv(
    OUTPUT_REPLICATES_CSV,
    index=False,
    encoding="utf-8-sig",
)


summary = {
    "bootstrap_statistics_complete":
        True,

    "performance_scope":
        "FROZEN_TEST_STATISTICAL_ANALYSIS",

    "method_parameters_changed":
        False,

    "test_rescored":
        False,

    "bootstrap_protocol": {
        "sampling_unit":
            "QUERY",

        "components_kept_with_query":
            True,

        "stratification":
            (
                "resample with replacement "
                "within each of the six frozen "
                "TEST scenarios"
            ),

        "scenario_size_per_replicate":
            60,

        "total_queries_per_replicate":
            360,

        "replicates":
            BOOTSTRAP_REPLICATES,

        "random_seed":
            RANDOM_SEED,

        "interval":
            "percentile_95",

        "paired_graph_comparison":
            True,
    },

    "final_method_beta_0_1":
        final_ci,

    "content_only_beta_0":
        beta0_ci,

    "paired_graph_minus_content_only":
        delta_ci,

    "primary_graph_metric":
        "parent_set_f1",

    "primary_graph_statistical_interpretation":
        graph_statistical_interpretation,

    "primary_graph_ci_excludes_zero":
        bool(
            graph_primary[
                "ci_excludes_zero"
            ]
        ),

    "interpretation_policy": {
        "if_ci_includes_zero":
            (
                "Do not claim statistically "
                "reliable graph improvement. "
                "Report the graph effect as small "
                "and statistically inconclusive."
            ),

        "if_positive_ci_excludes_zero":
            (
                "Graph refinement may be reported "
                "as a statistically supported "
                "positive effect on the frozen "
                "primary metric."
            ),

        "if_negative_ci_excludes_zero":
            (
                "Graph refinement should not be "
                "claimed as beneficial on the "
                "frozen primary metric."
            ),
    },

    "source_project_dependence_note":
        (
            "This phase uses query-level "
            "scenario-stratified bootstrap. "
            "It preserves dependence among the "
            "seven components within each query. "
            "Because source projects can recur "
            "across different queries and queries "
            "may contain multiple parents, a "
            "separate source-project clustered "
            "sensitivity analysis should be "
            "performed before final publication "
            "claims rather than treating 2520 "
            "components as independent."
        ),

    "goals_met":
        bool(
            len(
                replicates
            )
            == BOOTSTRAP_REPLICATES

            and

            set(
                final_ci.keys()
            )
            == set(
                FINAL_METRICS
            )

            and

            set(
                delta_ci.keys()
            )
            == set(
                DELTA_METRICS
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
# Print
# =========================================================

print()

print(
    "======================================"
)

print(
    "PHASE 8A RESULT"
)

print(
    "======================================"
)


print()

print(
    "FINAL METHOD 95% CI"
)


for metric in FINAL_METRICS:

    result = final_ci[
        metric
    ]


    print(
        metric,
        ":",
        result[
            "point_estimate"
        ],
        "[",
        result[
            "lower_95"
        ],
        ",",
        result[
            "upper_95"
        ],
        "]",
    )


print()

print(
    "PAIRED GRAPH DELTA 95% CI"
)


for metric in DELTA_METRICS:

    result = delta_ci[
        metric
    ]


    print(
        metric,
        ":",
        result[
            "point_estimate"
        ],
        "[",
        result[
            "lower_95"
        ],
        ",",
        result[
            "upper_95"
        ],
        "]",
        "P(delta>0)=",
        result[
            "probability_delta_gt_zero"
        ],
    )


print()

print(
    "Primary graph interpretation:",
    graph_statistical_interpretation
)


print()

print(
    "Replicates:",
    OUTPUT_REPLICATES_CSV
)

print(
    "Summary:",
    OUTPUT_SUMMARY_JSON
)