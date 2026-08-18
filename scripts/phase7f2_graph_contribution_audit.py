import json
from pathlib import Path

import pandas as pd


GRID_CSV = Path(
    "results/phase7f_graph_beta_grid.csv"
)

GRAPH_SUMMARY_JSON = Path(
    "results/phase7f_graph_calibration_summary.json"
)

OUTPUT_JSON = Path(
    "results/phase7f2_graph_contribution_summary.json"
)


if not GRID_CSV.exists():
    raise FileNotFoundError(
        GRID_CSV
    )

if not GRAPH_SUMMARY_JSON.exists():
    raise FileNotFoundError(
        GRAPH_SUMMARY_JSON
    )


grid = pd.read_csv(
    GRID_CSV
)

graph_summary = json.loads(
    GRAPH_SUMMARY_JSON.read_text(
        encoding="utf-8"
    )
)


selected_beta = float(
    graph_summary[
        "selected_beta"
    ]
)


print(
    "======================================"
)

print(
    "Phase 7F2 - Graph Contribution Audit"
)

print(
    "======================================"
)


def get_beta_row(beta):

    matched = grid[
        (
            grid[
                "beta"
            ].astype(float)
            -
            float(beta)
        ).abs()
        < 1e-12
    ]


    if len(matched) != 1:

        raise RuntimeError(
            f"Expected exactly one row "
            f"for beta={beta}, "
            f"got {len(matched)}"
        )


    return matched.iloc[0]


baseline = get_beta_row(
    0.0
)

selected = get_beta_row(
    selected_beta
)


METRICS = [
    "mean_parent_set_f1",
    "mean_component_accuracy",
    "mean_k_accuracy",

    "known_component_accuracy",
    "known_parent_set_f1",
    "known_parent_set_exact",
    "known_k_accuracy",
    "known_k_mae",

    "pseudo_component_accuracy",
    "pseudo_parent_set_f1",
    "pseudo_parent_set_exact",
    "pseudo_k_accuracy",
    "pseudo_k_mae",

    "pseudo_unknown_precision",
    "pseudo_unknown_recall",
    "pseudo_unknown_f1",
]


baseline_metrics = {}

selected_metrics = {}

deltas = {}


for metric in METRICS:

    if metric not in grid.columns:

        continue


    baseline_value = float(
        baseline[
            metric
        ]
    )

    selected_value = float(
        selected[
            metric
        ]
    )


    baseline_metrics[
        metric
    ] = baseline_value

    selected_metrics[
        metric
    ] = selected_value

    deltas[
        metric
    ] = (
        selected_value
        -
        baseline_value
    )


# =========================================================
# Frozen contribution decision
#
# We do NOT choose another beta.
#
# Graph is considered a useful performance refinement only
# if selected beta improves the PRIMARY calibration metric
# over beta=0 in the SAME Top-10 pipeline.
#
# Otherwise beta=0 becomes the final performance method,
# while edge-weight separation is retained only as a
# structural diagnostic/analysis result.
# =========================================================

primary_delta = deltas[
    "mean_parent_set_f1"
]


if primary_delta > 1e-12:

    graph_performance_contribution = True

    final_beta_for_performance = (
        selected_beta
    )

    decision = (
        "KEEP_GRAPH_REFINEMENT"
    )

else:

    graph_performance_contribution = False

    final_beta_for_performance = 0.0

    decision = (
        "REJECT_GRAPH_REFINEMENT_FOR_FINAL_PERFORMANCE"
    )


# =========================================================
# Also compare against original 7D reference.
#
# This is NOT used to accept/reject graph contribution
# because candidate search spaces differ.
# =========================================================

stage1_reference = graph_summary[
    "stage1_reference_from_phase7d"
]


phase7d_known_parent_f1 = float(
    stage1_reference[
        "known_parent_set_f1"
    ]
)

phase7d_pseudo_parent_f1 = float(
    stage1_reference[
        "pseudo_parent_set_f1"
    ]
)


phase7d_mean_parent_f1 = (
    phase7d_known_parent_f1
    +
    phase7d_pseudo_parent_f1
) / 2.0


selected_mean_parent_f1 = float(
    selected[
        "mean_parent_set_f1"
    ]
)


delta_vs_phase7d = (
    selected_mean_parent_f1
    -
    phase7d_mean_parent_f1
)


summary = {
    "graph_contribution_audit_complete":
        True,

    "performance_scope":
        "CALIBRATION_ONLY",

    "test_queries_scored":
        0,

    "unknown_heldout_queries_scored":
        0,

    "comparison_is_same_candidate_pool":
        True,

    "candidate_pool_size":
        int(
            graph_summary[
                "candidate_pool_size"
            ]
        ),

    "baseline_beta":
        0.0,

    "selected_beta_from_phase7f":
        selected_beta,

    "baseline_beta0_metrics":
        baseline_metrics,

    "selected_beta_metrics":
        selected_metrics,

    "selected_minus_beta0":
        deltas,

    "primary_metric":
        "mean_parent_set_f1",

    "primary_metric_delta":
        float(
            primary_delta
        ),

    "graph_performance_contribution":
        bool(
            graph_performance_contribution
        ),

    "decision":
        decision,

    "final_beta_for_performance":
        float(
            final_beta_for_performance
        ),

    "phase7d_reference_note":
        (
            "Phase 7D searches all 40 calibration "
            "candidate projects, whereas Phase 7F "
            "uses the frozen Top-10 retrieval pool. "
            "Therefore the Phase 7D comparison is "
            "reported only as context and is not "
            "the causal graph-contribution test."
        ),

    "phase7d_mean_parent_set_f1":
        float(
            phase7d_mean_parent_f1
        ),

    "selected_graph_mean_parent_set_f1":
        float(
            selected_mean_parent_f1
        ),

    "selected_graph_minus_phase7d":
        float(
            delta_vs_phase7d
        ),

    "edge_weight_signal": {
        "same_parent_mean":
            float(
                graph_summary[
                    "private_edge_weight_diagnostic"
                ][
                    "SAME_PARENT"
                ][
                    "mean_weight"
                ]
            ),

        "cross_parent_mean":
            float(
                graph_summary[
                    "private_edge_weight_diagnostic"
                ][
                    "CROSS_PARENT"
                ][
                    "mean_weight"
                ]
            ),

        "same_parent_median":
            float(
                graph_summary[
                    "private_edge_weight_diagnostic"
                ][
                    "SAME_PARENT"
                ][
                    "median_weight"
                ]
            ),

        "cross_parent_median":
            float(
                graph_summary[
                    "private_edge_weight_diagnostic"
                ][
                    "CROSS_PARENT"
                ][
                    "median_weight"
                ]
            ),
    },

    "test_data_used_for_decision":
        False,

    "goals_met":
        True,
}


OUTPUT_JSON.write_text(
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
    "PHASE 7F2 RESULT"
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
    "Summary:",
    OUTPUT_JSON
)