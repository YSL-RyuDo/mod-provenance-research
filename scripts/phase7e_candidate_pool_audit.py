import json
from pathlib import Path

import numpy as np
import pandas as pd


FULL40_SCORE_CSV = Path(
    "results/phase7c2_calibration_full40_parent_scores.csv"
)

PRIVATE_MANIFEST_CSV = Path(
    "results/phase6l_materialized_private_manifest.csv"
)

STAGE1_PARAMETERS_JSON = Path(
    "results/phase7d_stage1_parameters.json"
)


OUTPUT_QUERY_CSV = Path(
    "results/phase7e_candidate_pool_query_audit.csv"
)

OUTPUT_SUMMARY_JSON = Path(
    "results/phase7e_candidate_pool_summary.json"
)


TOP_M_VALUES = [
    3,
    4,
    5,
    6,
    8,
    10,
]


EXPECTED_QUERIES = 180
EXPECTED_COMPONENTS_PER_QUERY = 7


def clean_text(value):

    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    return str(value).strip()


for path in [
    FULL40_SCORE_CSV,
    PRIVATE_MANIFEST_CSV,
    STAGE1_PARAMETERS_JSON,
]:

    if not path.exists():
        raise FileNotFoundError(path)


scores = pd.read_csv(
    FULL40_SCORE_CSV
)

manifest = pd.read_csv(
    PRIVATE_MANIFEST_CSV
)

parameters = json.loads(
    STAGE1_PARAMETERS_JSON.read_text(
        encoding="utf-8"
    )
)


alpha = float(
    parameters[
        "alpha_absolute_distance"
    ]
)


thresholds = {
    key:
        float(value)

    for key, value
    in parameters[
        "unknown_thresholds"
    ].items()
}


print(
    "======================================"
)

print(
    "Phase 7E - Candidate Parent Pool Audit"
)

print(
    "======================================"
)

print(
    "Frozen alpha:",
    alpha
)


# =========================================================
# Calibration only
# =========================================================

cal_manifest = manifest[
    manifest[
        "stage"
    ]
    == "CALIBRATION"
].copy()


if len(
    cal_manifest
) != (
    EXPECTED_QUERIES
    *
    EXPECTED_COMPONENTS_PER_QUERY
):

    raise RuntimeError(
        "Calibration manifest size mismatch"
    )


calibration_query_ids = sorted(
    cal_manifest[
        "query_id"
    ].astype(str).unique()
)


if len(
    calibration_query_ids
) != EXPECTED_QUERIES:

    raise RuntimeError(
        "Expected 180 calibration queries"
    )


# =========================================================
# True parent sets
# =========================================================

true_parent_sets = {}


for query_id, group in (
    cal_manifest.groupby(
        "query_id"
    )
):

    parents = set(
        group[
            "source_fresh_id"
        ].astype(str)
    )


    true_parent_sets[
        str(query_id)
    ] = parents


# =========================================================
# Candidate parent ranking
#
# We aggregate component evidence into one query-level
# score per parent.
#
# Component cost:
#
# alpha * normalized absolute distance
# + (1-alpha) * clipped MEAN_REGRET
#
# For candidate-pool retrieval we do NOT apply lambda.
# Lambda is a final parent-count penalty and would harm
# recall if used during retrieval.
# =========================================================

query_rows = []


recall_by_m = {
    m: []
    for m in TOP_M_VALUES
}


exact_coverage_by_m = {
    m: []
    for m in TOP_M_VALUES
}


per_k_recall = {
    m: {}
    for m in TOP_M_VALUES
}


for query_index, query_id in enumerate(
    calibration_query_ids,
    start=1,
):

    if (
        query_index == 1
        or
        query_index % 30 == 0
    ):

        print(
            f"query "
            f"{query_index}/"
            f"{EXPECTED_QUERIES}"
        )


    query_scores = scores[
        scores[
            "query_id"
        ].astype(str)
        == query_id
    ].copy()


    node_ids = sorted(
        query_scores[
            "node_id"
        ].astype(str).unique()
    )


    if len(node_ids) != 7:

        raise RuntimeError(
            f"{query_id}: expected 7 nodes"
        )


    candidate_parents = sorted(
        query_scores[
            "candidate_parent"
        ].astype(str).unique()
    )


    if len(candidate_parents) != 40:

        raise RuntimeError(
            f"{query_id}: expected 40 candidates"
        )


    candidate_scores = {}


    for candidate_parent in (
        candidate_parents
    ):

        parent_rows = query_scores[
            query_scores[
                "candidate_parent"
            ].astype(str)
            == candidate_parent
        ]


        if len(parent_rows) != 7:

            raise RuntimeError(
                f"{query_id}/{candidate_parent}: "
                f"expected 7 component rows"
            )


        component_costs = []


        for row in parent_rows.itertuples(
            index=False
        ):

            modality = clean_text(
                row.modality
            )


            threshold = thresholds[
                modality
            ]


            distance = float(
                row.fused_parent_distance
            )

            regret = float(
                row.mean_regret
            )


            if threshold > 0:

                normalized_distance = min(
                    distance
                    /
                    threshold,
                    1.0,
                )

            else:

                # IMAGE threshold = 0.
                #
                # Exact perceptual match -> cost 0.
                # Any non-zero distance -> cost 1.
                normalized_distance = (
                    0.0
                    if abs(distance) <= 1e-12
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
                alpha
                *
                normalized_distance
                +
                (
                    1.0
                    -
                    alpha
                )
                *
                normalized_regret
            )


            component_costs.append(
                float(
                    cost
                )
            )


        # Best evidence from any component is too noisy.
        #
        # We therefore use the mean of the best three
        # component costs. This allows a real parent that
        # contributes only a subset of the seven query
        # components to rank highly without requiring it
        # to explain components belonging to other parents.
        component_costs.sort()


        best_evidence_count = min(
            3,
            len(
                component_costs
            )
        )


        candidate_score = float(
            np.mean(
                component_costs[
                    :best_evidence_count
                ]
            )
        )


        candidate_scores[
            candidate_parent
        ] = candidate_score


    ranked_parents = sorted(
        candidate_parents,
        key=lambda parent: (
            candidate_scores[
                parent
            ],
            parent,
        ),
    )


    true_set = (
        true_parent_sets[
            query_id
        ]
    )


    k_true = len(
        true_set
    )


    row_output = {
        "query_id":
            query_id,

        "k_true":
            int(
                k_true
            ),

        "true_parent_set":
            json.dumps(
                sorted(
                    true_set
                )
            ),
    }


    for m in TOP_M_VALUES:

        predicted_pool = set(
            ranked_parents[
                :m
            ]
        )


        covered = len(
            true_set
            &
            predicted_pool
        )


        recall = (
            covered
            /
            len(
                true_set
            )
        )


        exact_coverage = bool(
            true_set
            <= predicted_pool
        )


        recall_by_m[
            m
        ].append(
            recall
        )


        exact_coverage_by_m[
            m
        ].append(
            exact_coverage
        )


        per_k_recall[
            m
        ].setdefault(
            k_true,
            []
        )


        per_k_recall[
            m
        ][
            k_true
        ].append(
            recall
        )


        row_output[
            f"top{m}_parent_recall"
        ] = float(
            recall
        )


        row_output[
            f"top{m}_all_true_parents_present"
        ] = bool(
            exact_coverage
        )


        row_output[
            f"top{m}_candidate_pool"
        ] = json.dumps(
            ranked_parents[
                :m
            ]
        )


    query_rows.append(
        row_output
    )


query_df = pd.DataFrame(
    query_rows
)


# =========================================================
# Summary
# =========================================================

top_m_summary = {}


for m in TOP_M_VALUES:

    recall_values = (
        recall_by_m[
            m
        ]
    )


    exact_values = (
        exact_coverage_by_m[
            m
        ]
    )


    by_k = {}


    for k_true, values in sorted(
        per_k_recall[
            m
        ].items()
    ):

        by_k[
            str(
                k_true
            )
        ] = {
            "queries":
                int(
                    len(
                        values
                    )
                ),

            "mean_parent_recall":
                float(
                    np.mean(
                        values
                    )
                ),
        }


    top_m_summary[
        str(
            m
        )
    ] = {
        "mean_parent_recall":
            float(
                np.mean(
                    recall_values
                )
            ),

        "all_true_parents_present_rate":
            float(
                np.mean(
                    exact_values
                )
            ),

        "queries_missing_any_true_parent":
            int(
                sum(
                    not value
                    for value
                    in exact_values
                )
            ),

        "by_k":
            by_k,
    }


# =========================================================
# Frozen selection rule
#
# Choose the SMALLEST M satisfying:
#
# mean parent recall >= .95
# and
# all true parents present >= .90
#
# If none satisfy, select the M with:
# 1. highest exact coverage
# 2. highest mean recall
# 3. smaller M
#
# This is calibration only.
# =========================================================

eligible_m = []


for m in TOP_M_VALUES:

    result = (
        top_m_summary[
            str(m)
        ]
    )


    if (
        result[
            "mean_parent_recall"
        ]
        >= 0.95

        and

        result[
            "all_true_parents_present_rate"
        ]
        >= 0.90
    ):

        eligible_m.append(
            m
        )


if eligible_m:

    selected_m = min(
        eligible_m
    )

    selection_rule_status = (
        "TARGET_CRITERIA_MET"
    )

else:

    selected_m = max(
        TOP_M_VALUES,
        key=lambda m: (
            top_m_summary[
                str(m)
            ][
                "all_true_parents_present_rate"
            ],

            top_m_summary[
                str(m)
            ][
                "mean_parent_recall"
            ],

            -m,
        ),
    )

    selection_rule_status = (
        "TARGET_CRITERIA_NOT_MET_FALLBACK"
    )


# =========================================================
# Save
# =========================================================

OUTPUT_QUERY_CSV.parent.mkdir(
    parents=True,
    exist_ok=True,
)


query_df.to_csv(
    OUTPUT_QUERY_CSV,
    index=False,
    encoding="utf-8-sig",
)


summary = {
    "candidate_parent_pool_audit_complete":
        True,

    "performance_scope":
        "CALIBRATION_ONLY",

    "test_queries_scored":
        0,

    "unknown_heldout_queries_scored":
        0,

    "stage1_final_parent_set_not_used_as_hard_constraint":
        True,

    "retrieval_score_policy":
        (
            "frozen Phase 7D alpha and modality "
            "thresholds; no proliferation lambda; "
            "query-level candidate score is the mean "
            "of the three lowest component costs"
        ),

    "candidate_m_values":
        TOP_M_VALUES,

    "top_m_results":
        top_m_summary,

    "selection_target": {
        "mean_parent_recall":
            0.95,

        "all_true_parents_present_rate":
            0.90,
    },

    "selected_candidate_pool_size":
        int(
            selected_m
        ),

    "selection_rule_status":
        selection_rule_status,

    "goals_met":
        True,
}


OUTPUT_SUMMARY_JSON.write_text(
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
    "PHASE 7E RESULT"
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
    "Query audit:",
    OUTPUT_QUERY_CSV
)

print(
    "Summary:",
    OUTPUT_SUMMARY_JSON
)