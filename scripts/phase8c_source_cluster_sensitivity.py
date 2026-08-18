import hashlib
import json
from collections import defaultdict
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

PRIVATE_MANIFEST_CSV = Path(
    "results/phase6l_materialized_private_manifest.csv"
)

QUERY_GT_CSV = Path(
    "results/phase6k_query_ground_truth.csv"
)

PHASE8A_SUMMARY_JSON = Path(
    "results/phase8a_bootstrap_summary.json"
)


# =========================================================
# Outputs
# =========================================================

OUTPUT_CLUSTER_REPLICATES_CSV = Path(
    "results/phase8c_source_cluster_bootstrap_replicates.csv"
)

OUTPUT_LOSO_CSV = Path(
    "results/phase8c_leave_one_source_out.csv"
)

OUTPUT_QUERY_CLUSTER_CSV = Path(
    "results/phase8c_query_source_clusters.csv"
)

OUTPUT_SUMMARY_JSON = Path(
    "results/phase8c_source_cluster_sensitivity_summary.json"
)


# =========================================================
# Protocol
# =========================================================

BOOTSTRAP_REPLICATES = 10000
RANDOM_SEED = 20260813

UNKNOWN_LABEL = "UNKNOWN"

EXPECTED_QUERIES = 360
EXPECTED_COMPONENTS = 2520

CI_LOW = 2.5
CI_HIGH = 97.5


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


def safe_divide(a, b):

    if b == 0:
        return 0.0

    return float(a / b)


def binary_unknown_metrics(
    truth_labels,
    pred_labels,
):

    truth = np.asarray(
        [
            value == UNKNOWN_LABEL
            for value in truth_labels
        ],
        dtype=bool,
    )

    pred = np.asarray(
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
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }


def deterministic_anchor(
    query_id,
    source_projects,
):

    source_projects = sorted(
        set(
            source_projects
        )
    )


    if not source_projects:

        raise RuntimeError(
            f"{query_id}: no source projects"
        )


    digest = hashlib.sha256(
        query_id.encode(
            "utf-8"
        )
    ).digest()


    integer = int.from_bytes(
        digest[:8],
        byteorder="big",
        signed=False,
    )


    index = (
        integer
        %
        len(
            source_projects
        )
    )


    return source_projects[
        index
    ]


def percentile_summary(values):

    values = np.asarray(
        values,
        dtype=np.float64,
    )


    return {
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
    }


# =========================================================
# Load
# =========================================================

required = [
    FINAL_COMPONENT_CSV,
    FINAL_QUERY_CSV,
    PRIVATE_MANIFEST_CSV,
    QUERY_GT_CSV,
    PHASE8A_SUMMARY_JSON,
]


for path in required:

    if not path.exists():

        raise FileNotFoundError(
            f"Missing: {path}"
        )


components = pd.read_csv(
    FINAL_COMPONENT_CSV
)

queries = pd.read_csv(
    FINAL_QUERY_CSV
)

manifest = pd.read_csv(
    PRIVATE_MANIFEST_CSV
)

query_gt = pd.read_csv(
    QUERY_GT_CSV
)


phase8a = json.loads(
    PHASE8A_SUMMARY_JSON.read_text(
        encoding="utf-8"
    )
)


print(
    "======================================"
)

print(
    "Phase 8C - Source Project Sensitivity"
)

print(
    "======================================"
)


# =========================================================
# Validate
# =========================================================

if len(
    components
) != EXPECTED_COMPONENTS:

    raise RuntimeError(
        "Expected 2520 final components"
    )


if len(
    queries
) != EXPECTED_QUERIES:

    raise RuntimeError(
        "Expected 360 final queries"
    )


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
        "Expected 360 TEST query GT rows"
    )


test_query_ids = set(
    queries[
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
        "TEST manifest size mismatch"
    )


for dataframe in [
    components,
    queries,
    test_manifest,
]:

    dataframe[
        "query_id"
    ] = (
        dataframe[
            "query_id"
        ].astype(str)
    )


# =========================================================
# Source memberships per query
#
# Uses PRIVATE GT only for statistical clustering.
# It is NOT part of the inference method.
# =========================================================

sources_by_query = {}


for query_id, group in (
    test_manifest.groupby(
        "query_id"
    )
):

    source_projects = sorted(
        set(
            group[
                "source_fresh_id"
            ]
            .astype(str)
            .tolist()
        )
    )


    if not source_projects:

        raise RuntimeError(
            f"{query_id}: no source membership"
        )


    sources_by_query[
        str(query_id)
    ] = source_projects


all_source_projects = sorted(
    {
        source

        for sources
        in sources_by_query.values()

        for source
        in sources
    }
)


print(
    "Distinct TEST source projects:",
    len(
        all_source_projects
    )
)


# =========================================================
# Deterministic anchor cluster assignment
# =========================================================

query_cluster_rows = []

anchor_by_query = {}

queries_by_anchor = defaultdict(
    list
)


for query_id in sorted(
    test_query_ids
):

    sources = (
        sources_by_query[
            query_id
        ]
    )


    anchor = deterministic_anchor(
        query_id,
        sources,
    )


    anchor_by_query[
        query_id
    ] = anchor


    queries_by_anchor[
        anchor
    ].append(
        query_id
    )


    query_cluster_rows.append({
        "query_id":
            query_id,

        "source_projects":
            json.dumps(
                sources
            ),

        "source_project_count":
            int(
                len(
                    sources
                )
            ),

        "anchor_source_project":
            anchor,
    })


query_cluster_df = pd.DataFrame(
    query_cluster_rows
)


anchor_projects = sorted(
    queries_by_anchor.keys()
)


anchor_sizes = [
    len(
        queries_by_anchor[
            project
        ]
    )
    for project
    in anchor_projects
]


print(
    "Anchor clusters:",
    len(
        anchor_projects
    )
)

print(
    "Anchor cluster median queries:",
    float(
        np.median(
            anchor_sizes
        )
    )
)

print(
    "Anchor cluster max queries:",
    int(
        max(
            anchor_sizes
        )
    )
)


# =========================================================
# Query-level sufficient statistics
# =========================================================

query_records = {}


for query_row in queries.itertuples(
    index=False
):

    query_id = clean_text(
        query_row.query_id
    )


    component_group = components[
        components[
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


    truth_labels = (
        component_group[
            "ground_truth_label"
        ]
        .astype(str)
        .tolist()
    )


    pred_labels = (
        component_group[
            "predicted_label"
        ]
        .astype(str)
        .tolist()
    )


    unknown = (
        binary_unknown_metrics(
            truth_labels,
            pred_labels,
        )
    )


    query_records[
        query_id
    ] = {
        "component_correct":
            int(
                (
                    component_group[
                        "ground_truth_label"
                    ].astype(str)
                    ==
                    component_group[
                        "predicted_label"
                    ].astype(str)
                ).sum()
            ),

        "component_total":
            7,

        "parent_set_f1":
            float(
                query_row.parent_set_f1
            ),

        "parent_set_exact":
            int(
                as_bool(
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
            int(
                unknown[
                    "tp"
                ]
            ),

        "unknown_fp":
            int(
                unknown[
                    "fp"
                ]
            ),

        "unknown_fn":
            int(
                unknown[
                    "fn"
                ]
            ),

        "unknown_tn":
            int(
                unknown[
                    "tn"
                ]
            ),
    }


# =========================================================
# Aggregation
# =========================================================

def aggregate_query_ids(
    sampled_query_ids,
):

    component_correct = 0
    component_total = 0

    parent_f1_sum = 0.0
    parent_exact_sum = 0

    k_correct_sum = 0
    k_error_sum = 0.0

    unknown_tp = 0
    unknown_fp = 0
    unknown_fn = 0
    unknown_tn = 0


    query_count = len(
        sampled_query_ids
    )


    if query_count == 0:

        raise RuntimeError(
            "Cannot aggregate zero queries"
        )


    for query_id in (
        sampled_query_ids
    ):

        record = query_records[
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

        k_error_sum += (
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
            safe_divide(
                component_correct,
                component_total,
            ),

        "parent_set_f1":
            safe_divide(
                parent_f1_sum,
                query_count,
            ),

        "parent_set_exact":
            safe_divide(
                parent_exact_sum,
                query_count,
            ),

        "k_accuracy":
            safe_divide(
                k_correct_sum,
                query_count,
            ),

        "k_mae":
            safe_divide(
                k_error_sum,
                query_count,
            ),

        "unknown_precision":
            unknown_precision,

        "unknown_recall":
            unknown_recall,

        "unknown_f1":
            unknown_f1,

        "queries":
            int(
                query_count
            ),
    }


# =========================================================
# Original point estimates
# =========================================================

all_query_ids = sorted(
    test_query_ids
)


point_estimate = (
    aggregate_query_ids(
        all_query_ids
    )
)


phase8a_final = (
    phase8a[
        "final_method_beta_0_1"
    ]
)


crosscheck_metrics = [
    "component_accuracy",
    "parent_set_f1",
    "parent_set_exact",
    "k_accuracy",
    "k_mae",
    "unknown_precision",
    "unknown_recall",
    "unknown_f1",
]


for metric in crosscheck_metrics:

    expected = float(
        phase8a_final[
            metric
        ][
            "point_estimate"
        ]
    )

    actual = float(
        point_estimate[
            metric
        ]
    )


    if not np.isclose(
        actual,
        expected,
        atol=1e-12,
        rtol=0.0,
    ):

        raise RuntimeError(
            f"Phase 8A cross-check failed "
            f"for {metric}: "
            f"{actual} != {expected}"
        )


print(
    "Phase 8A point-estimate cross-check: PASS"
)


# =========================================================
# A. Anchor source-project cluster bootstrap
#
# Resample source clusters WITH replacement.
# Each selected cluster brings all queries assigned
# deterministically to that anchor.
#
# Cluster sizes are therefore preserved.
# =========================================================

rng = np.random.default_rng(
    RANDOM_SEED
)


replicate_rows = []


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
            "cluster bootstrap",
            replicate_index + 1,
            "/",
            BOOTSTRAP_REPLICATES,
        )


    sampled_clusters = rng.choice(
        np.array(
            anchor_projects,
            dtype=object,
        ),
        size=len(
            anchor_projects
        ),
        replace=True,
    )


    sampled_query_ids = []


    for cluster in (
        sampled_clusters
    ):

        sampled_query_ids.extend(
            queries_by_anchor[
                str(
                    cluster
                )
            ]
        )


    metrics = aggregate_query_ids(
        sampled_query_ids
    )


    output = {
        "replicate":
            int(
                replicate_index
            ),

        "sampled_clusters":
            int(
                len(
                    sampled_clusters
                )
            ),

        "sampled_queries":
            int(
                len(
                    sampled_query_ids
                )
            ),
    }


    for metric in (
        crosscheck_metrics
    ):

        output[
            metric
        ] = float(
            metrics[
                metric
            ]
        )


    replicate_rows.append(
        output
    )


replicates = pd.DataFrame(
    replicate_rows
)


cluster_ci = {}


for metric in crosscheck_metrics:

    result = percentile_summary(
        replicates[
            metric
        ]
        .to_numpy(
            dtype=float
        )
    )


    result[
        "point_estimate"
    ] = float(
        point_estimate[
            metric
        ]
    )


    cluster_ci[
        metric
    ] = result


# =========================================================
# Compare width with Phase 8A query bootstrap
# =========================================================

ci_width_comparison = {}


for metric in crosscheck_metrics:

    query_lower = float(
        phase8a_final[
            metric
        ][
            "lower_95"
        ]
    )

    query_upper = float(
        phase8a_final[
            metric
        ][
            "upper_95"
        ]
    )


    cluster_lower = float(
        cluster_ci[
            metric
        ][
            "lower_95"
        ]
    )

    cluster_upper = float(
        cluster_ci[
            metric
        ][
            "upper_95"
        ]
    )


    query_width = (
        query_upper
        -
        query_lower
    )


    cluster_width = (
        cluster_upper
        -
        cluster_lower
    )


    ci_width_comparison[
        metric
    ] = {
        "query_bootstrap_width":
            float(
                query_width
            ),

        "source_cluster_bootstrap_width":
            float(
                cluster_width
            ),

        "cluster_over_query_width_ratio":
            float(
                safe_divide(
                    cluster_width,
                    query_width,
                )
            ),
    }


# =========================================================
# B. Leave-One-Source-Project-Out sensitivity
#
# Remove ALL queries containing each source project,
# regardless of whether that project was the anchor.
#
# This directly captures multi-parent memberships.
# =========================================================

loso_rows = []


for index, source_project in enumerate(
    all_source_projects,
    start=1,
):

    if (
        index == 1
        or
        index % 10 == 0
    ):

        print(
            "LOSO",
            index,
            "/",
            len(
                all_source_projects
            ),
        )


    removed_query_ids = {
        query_id

        for query_id, sources
        in sources_by_query.items()

        if source_project
        in sources
    }


    retained_query_ids = [
        query_id

        for query_id
        in all_query_ids

        if query_id
        not in removed_query_ids
    ]


    if not retained_query_ids:

        raise RuntimeError(
            "LOSO removed all queries"
        )


    metrics = aggregate_query_ids(
        retained_query_ids
    )


    output = {
        "source_project":
            source_project,

        "removed_queries":
            int(
                len(
                    removed_query_ids
                )
            ),

        "retained_queries":
            int(
                len(
                    retained_query_ids
                )
            ),
    }


    for metric in crosscheck_metrics:

        value = float(
            metrics[
                metric
            ]
        )


        point = float(
            point_estimate[
                metric
            ]
        )


        output[
            metric
        ] = value


        output[
            "delta_"
            +
            metric
        ] = (
            value
            -
            point
        )


    loso_rows.append(
        output
    )


loso = pd.DataFrame(
    loso_rows
)


# =========================================================
# LOSO influence summary
# =========================================================

loso_summary = {}


for metric in crosscheck_metrics:

    delta_column = (
        "delta_"
        +
        metric
    )


    deltas = (
        loso[
            delta_column
        ]
        .astype(float)
    )


    absolute = (
        deltas.abs()
    )


    maximum_index = (
        absolute.idxmax()
    )


    maximum_row = (
        loso.loc[
            maximum_index
        ]
    )


    loso_summary[
        metric
    ] = {
        "mean_delta":
            float(
                deltas.mean()
            ),

        "mean_absolute_delta":
            float(
                absolute.mean()
            ),

        "max_absolute_delta":
            float(
                absolute.max()
            ),

        "most_influential_source_project":
            clean_text(
                maximum_row[
                    "source_project"
                ]
            ),

        "most_influential_removed_queries":
            int(
                maximum_row[
                    "removed_queries"
                ]
            ),

        "most_influential_signed_delta":
            float(
                maximum_row[
                    delta_column
                ]
            ),
    }


# =========================================================
# Stability heuristic
#
# This is descriptive, NOT a statistical significance test.
#
# "Stable" if:
# - cluster CI overlaps the point estimate from query CI
#   naturally by construction, and
# - no single source removal shifts parent F1 by >= 0.03
# - no single source removal shifts component accuracy >= .03
# - no single source removal shifts UNKNOWN F1 >= .05
# =========================================================

stable_parent_f1 = bool(
    loso_summary[
        "parent_set_f1"
    ][
        "max_absolute_delta"
    ]
    < 0.03
)


stable_component_accuracy = bool(
    loso_summary[
        "component_accuracy"
    ][
        "max_absolute_delta"
    ]
    < 0.03
)


stable_unknown_f1 = bool(
    loso_summary[
        "unknown_f1"
    ][
        "max_absolute_delta"
    ]
    < 0.05
)


overall_sensitivity_stable = bool(
    stable_parent_f1
    and
    stable_component_accuracy
    and
    stable_unknown_f1
)


# =========================================================
# Save
# =========================================================

OUTPUT_CLUSTER_REPLICATES_CSV.parent.mkdir(
    parents=True,
    exist_ok=True,
)


replicates.to_csv(
    OUTPUT_CLUSTER_REPLICATES_CSV,
    index=False,
    encoding="utf-8-sig",
)


loso.to_csv(
    OUTPUT_LOSO_CSV,
    index=False,
    encoding="utf-8-sig",
)


query_cluster_df.to_csv(
    OUTPUT_QUERY_CLUSTER_CSV,
    index=False,
    encoding="utf-8-sig",
)


summary = {
    "source_project_sensitivity_complete":
        True,

    "performance_scope":
        "FROZEN_TEST_SENSITIVITY",

    "method_parameters_changed":
        False,

    "test_rescored":
        False,

    "point_estimates":
        {
            metric:
                float(
                    point_estimate[
                        metric
                    ]
                )

            for metric
            in crosscheck_metrics
        },

    "source_anchor_cluster_bootstrap": {
        "anchor_assignment":
            (
                "Each query is assigned to one of "
                "its true contributing source projects "
                "using SHA-256(query_id) modulo the "
                "number of contributing projects. "
                "Assignment is deterministic and "
                "independent of performance."
            ),

        "clusters":
            int(
                len(
                    anchor_projects
                )
            ),

        "median_queries_per_cluster":
            float(
                np.median(
                    anchor_sizes
                )
            ),

        "max_queries_per_cluster":
            int(
                max(
                    anchor_sizes
                )
            ),

        "replicates":
            BOOTSTRAP_REPLICATES,

        "random_seed":
            RANDOM_SEED,

        "interval":
            "percentile_95",

        "metrics":
            cluster_ci,
    },

    "query_vs_source_cluster_ci_width":
        ci_width_comparison,

    "leave_one_source_project_out": {
        "distinct_source_projects":
            int(
                len(
                    all_source_projects
                )
            ),

        "membership_policy":
            (
                "For each source project, all TEST "
                "queries containing that project are "
                "removed, including queries where the "
                "project is a secondary parent."
            ),

        "metric_influence":
            loso_summary,
    },

    "sensitivity_stability": {
        "parent_set_f1_max_loso_delta_below_0.03":
            stable_parent_f1,

        "component_accuracy_max_loso_delta_below_0.03":
            stable_component_accuracy,

        "unknown_f1_max_loso_delta_below_0.05":
            stable_unknown_f1,

        "overall_descriptive_stability":
            overall_sensitivity_stable,
    },

    "methodological_note":
        (
            "Multi-parent queries belong to multiple "
            "source projects, so there is no unique "
            "ordinary one-way cluster assignment. "
            "The anchor-source bootstrap is therefore "
            "reported as a sensitivity analysis rather "
            "than as a replacement for the primary "
            "scenario-stratified query bootstrap. "
            "The leave-one-source-project-out analysis "
            "uses all parent memberships and directly "
            "tests whether any individual MOD project "
            "dominates the reported performance."
        ),

    "phase8a_point_estimate_crosscheck_passed":
        True,

    "goals_met":
        bool(
            len(
                replicates
            )
            == BOOTSTRAP_REPLICATES

            and

            len(
                loso
            )
            == len(
                all_source_projects
            )

            and

            len(
                query_cluster_df
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
    "PHASE 8C RESULT"
)

print(
    "======================================"
)


for metric in [
    "component_accuracy",
    "parent_set_f1",
    "parent_set_exact",
    "k_accuracy",
    "unknown_f1",
]:

    result = cluster_ci[
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
        "width ratio=",
        ci_width_comparison[
            metric
        ][
            "cluster_over_query_width_ratio"
        ],
    )


print()

print(
    "Max LOSO shifts:"
)


for metric in [
    "component_accuracy",
    "parent_set_f1",
    "unknown_f1",
]:

    result = loso_summary[
        metric
    ]


    print(
        metric,
        "max |delta| =",
        result[
            "max_absolute_delta"
        ],
        "project =",
        result[
            "most_influential_source_project"
        ],
        "removed queries =",
        result[
            "most_influential_removed_queries"
        ],
    )


print()

print(
    "Overall descriptive stability:",
    overall_sensitivity_stable
)

print()

print(
    "Cluster replicates:",
    OUTPUT_CLUSTER_REPLICATES_CSV
)

print(
    "LOSO:",
    OUTPUT_LOSO_CSV
)

print(
    "Query clusters:",
    OUTPUT_QUERY_CLUSTER_CSV
)

print(
    "Summary:",
    OUTPUT_SUMMARY_JSON
)