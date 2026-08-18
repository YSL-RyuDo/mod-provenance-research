import json
from pathlib import Path

import pandas as pd

import phase5f_parentset_constrained_graph as graph
import phase5g_parent_fusion as fusion


RESULT_ROOT = Path("results")
RESULT_ROOT.mkdir(exist_ok=True)

FUSION_METHOD = "MEAN_REGRET"

THRESHOLD_GRID = [
    0.0,
    0.0025,
    0.005,
    0.01,
    0.02,
    0.05,
    0.10,
    0.20,
]


# =========================================================
# Fused evidence
# =========================================================

def build_fused_evidence(gt):

    evidence_by_rep = {}

    for representation in (
        fusion.REPRESENTATIONS
    ):

        evidence = (
            fusion.build_rep_evidence(
                gt,
                representation,
            )
        )

        if (
            len(evidence)
            != len(
                gt["ground_truth"]
            )
        ):

            return None

        evidence_by_rep[
            representation
        ] = evidence


    fused = (
        fusion.fuse_evidence(
            evidence_by_rep,
            FUSION_METHOD,
        )
    )


    # -----------------------------------------------------
    # phase5f graph code assumes Hamming-like
    # distance scale around 0..128.
    #
    # Fusion produces normalized 0..1 score,
    # so rescale without altering ranking.
    # -----------------------------------------------------

    scaled = {}

    for node_id, distances in (
        fused.items()
    ):

        scaled[
            node_id
        ] = {
            mod:
                score * 128.0

            for mod, score
            in distances.items()
        }

    return scaled


# =========================================================
# Same calibration/test split as Phase 5F
# =========================================================

calibration_queries = (
    graph.calibration_queries
)

test_queries = (
    graph.test_queries
)

gt_by_id = (
    graph.gt_by_id
)

base = (
    graph.base
)


print()
print(
    "======================================"
)
print(
    "Phase 5H - Fused Hierarchical Method"
)
print(
    "======================================"
)

print(
    "Fusion:",
    FUSION_METHOD
)

print(
    "Calibration:",
    len(calibration_queries)
)

print(
    "Test:",
    len(test_queries)
)


# =========================================================
# Tune graph boundary threshold
#
# NOTE:
# Fusion choice itself is already fixed.
# Only graph threshold is calibrated here.
# =========================================================

best_threshold = None
best_score = None


for threshold in (
    THRESHOLD_GRID
):

    accuracies = []


    for public_query in (
        calibration_queries
    ):

        gt = gt_by_id[
            public_query[
                "query_id"
            ]
        ]


        evidence = (
            build_fused_evidence(
                gt
            )
        )


        if evidence is None:
            continue


        true_labels = (
            gt[
                "ground_truth"
            ]
        )


        all_nodes = {
            node[
                "query_node_id"
            ]

            for node
            in public_query[
                "nodes"
            ]
        }


        # -----------------------------------------------
        # Stage 1:
        # fused exact-global parent set
        # -----------------------------------------------

        (
            _,
            predicted_parents
        ) = (
            base.exact_global_parentset(
                evidence,
                public_query[
                    "parent_count"
                ],
            )
        )


        if not predicted_parents:
            continue


        # -----------------------------------------------
        # Tune over all graph stress conditions
        # -----------------------------------------------

        for condition in (
            graph.CONDITIONS
        ):

            edges = (
                graph.corrupt_edges(
                    public_query,
                    gt,
                    condition,
                )
            )


            (
                predictions,
                _,
                _
            ) = (
                graph.hierarchical_assignment(
                    evidence,
                    all_nodes,
                    edges,
                    predicted_parents,
                    threshold,
                )
            )


            metrics = (
                base.evaluate_query(
                    true_labels,
                    gt["parents"],
                    predictions,
                    predicted_parents,
                )
            )


            accuracies.append(
                metrics[
                    "component_accuracy"
                ]
            )


    if not accuracies:
        continue


    score = (
        sum(accuracies)
        / len(accuracies)
    )


    print(
        "threshold=",
        threshold,
        "component_accuracy=",
        round(
            score,
            4
        )
    )


    if (
        best_score is None
        or
        score > best_score
    ):

        best_score = score
        best_threshold = (
            threshold
        )


print()
print(
    "BEST THRESHOLD:",
    best_threshold
)

print(
    "CALIBRATION ACC:",
    best_score
)


# =========================================================
# Test
# =========================================================

raw_rows = []


for (
    query_index,
    public_query
) in enumerate(
    test_queries,
    start=1,
):

    query_id = (
        public_query[
            "query_id"
        ]
    )


    gt = gt_by_id[
        query_id
    ]


    true_labels = (
        gt[
            "ground_truth"
        ]
    )


    evidence = (
        build_fused_evidence(
            gt
        )
    )


    if evidence is None:
        continue


    all_nodes = {
        node[
            "query_node_id"
        ]

        for node
        in public_query[
            "nodes"
        ]
    }


    # =====================================================
    # Stage 1 fused parent-set reconstruction
    # =====================================================

    (
        fused_global_assignments,
        fused_parent_set
    ) = (
        base.exact_global_parentset(
            evidence,
            public_query[
                "parent_count"
            ],
        )
    )


    for condition in (
        graph.CONDITIONS
    ):

        edges = (
            graph.corrupt_edges(
                public_query,
                gt,
                condition,
            )
        )


        # =================================================
        # F1:
        # Fused content-only exact global
        # =================================================

        metrics = (
            base.evaluate_query(
                true_labels,
                gt["parents"],
                fused_global_assignments,
                fused_parent_set,
            )
        )


        raw_rows.append({
            "query_id":
                query_id,

            "parent_count":
                public_query[
                    "parent_count"
                ],

            "condition":
                condition,

            "method":
                "F1_FUSED_GLOBAL",

            "cut_edges":
                0,

            **metrics,
        })


        # =================================================
        # F2:
        # Fused hierarchical method
        # =================================================

        (
            hierarchical_predictions,
            hierarchical_parents,
            cut_count
        ) = (
            graph.hierarchical_assignment(
                evidence,
                all_nodes,
                edges,
                fused_parent_set,
                best_threshold,
            )
        )


        metrics = (
            base.evaluate_query(
                true_labels,
                gt["parents"],
                hierarchical_predictions,
                hierarchical_parents,
            )
        )


        raw_rows.append({
            "query_id":
                query_id,

            "parent_count":
                public_query[
                    "parent_count"
                ],

            "condition":
                condition,

            "method":
                "F2_FUSED_HIERARCHICAL",

            "cut_edges":
                cut_count,

            **metrics,
        })


        # =================================================
        # Oracle diagnostic
        #
        # True parent set + same fused evidence
        # =================================================

        true_parent_set = list(
            gt[
                "parents"
            ]
        )


        (
            oracle_predictions,
            oracle_parents,
            oracle_cut_count
        ) = (
            graph.hierarchical_assignment(
                evidence,
                all_nodes,
                edges,
                true_parent_set,
                best_threshold,
            )
        )


        metrics = (
            base.evaluate_query(
                true_labels,
                gt["parents"],
                oracle_predictions,
                oracle_parents,
            )
        )


        raw_rows.append({
            "query_id":
                query_id,

            "parent_count":
                public_query[
                    "parent_count"
                ],

            "condition":
                condition,

            "method":
                "ORACLE_FUSED_PARENTSET",

            "cut_edges":
                oracle_cut_count,

            **metrics,
        })


    if (
        query_index % 25
        == 0
    ):

        print(
            "tested",
            query_index,
            "/",
            len(test_queries)
        )


# =========================================================
# Save raw
# =========================================================

raw = pd.DataFrame(
    raw_rows
)


raw.to_csv(
    RESULT_ROOT
    / "phase5h_fused_hierarchical_raw.csv",

    index=False,
    encoding="utf-8-sig",
)


# =========================================================
# Summary ALL
# =========================================================

summary_rows = []


for (
    condition,
    method
), group in raw.groupby(
    [
        "condition",
        "method",
    ]
):

    summary_rows.append({
        "condition":
            condition,

        "parent_count":
            "ALL",

        "method":
            method,

        "queries":
            len(group),

        "component_accuracy":
            float(
                group[
                    "component_accuracy"
                ].mean()
            ),

        "parent_precision":
            float(
                group[
                    "parent_precision"
                ].mean()
            ),

        "parent_recall":
            float(
                group[
                    "parent_recall"
                ].mean()
            ),

        "parent_f1":
            float(
                group[
                    "parent_f1"
                ].mean()
            ),

        "parent_set_exact":
            float(
                group[
                    "parent_set_exact"
                ].mean()
            ),

        "component_set_exact":
            float(
                group[
                    "component_set_exact"
                ].mean()
            ),

        "mean_cut_edges":
            float(
                group[
                    "cut_edges"
                ].mean()
            ),
    })


# =========================================================
# Summary 2-parent / 3-parent
# =========================================================

for (
    condition,
    method,
    parent_count
), group in raw.groupby(
    [
        "condition",
        "method",
        "parent_count",
    ]
):

    summary_rows.append({
        "condition":
            condition,

        "parent_count":
            int(
                parent_count
            ),

        "method":
            method,

        "queries":
            len(group),

        "component_accuracy":
            float(
                group[
                    "component_accuracy"
                ].mean()
            ),

        "parent_precision":
            float(
                group[
                    "parent_precision"
                ].mean()
            ),

        "parent_recall":
            float(
                group[
                    "parent_recall"
                ].mean()
            ),

        "parent_f1":
            float(
                group[
                    "parent_f1"
                ].mean()
            ),

        "parent_set_exact":
            float(
                group[
                    "parent_set_exact"
                ].mean()
            ),

        "component_set_exact":
            float(
                group[
                    "component_set_exact"
                ].mean()
            ),

        "mean_cut_edges":
            float(
                group[
                    "cut_edges"
                ].mean()
            ),
    })


summary_df = pd.DataFrame(
    summary_rows
)


summary_df.to_csv(
    RESULT_ROOT
    / "phase5h_fused_hierarchical_summary.csv",

    index=False,
    encoding="utf-8-sig",
)


# =========================================================
# Compact JSON
# =========================================================

compact = {
    "fusion_method":
        FUSION_METHOD,

    "calibration_queries":
        len(
            calibration_queries
        ),

    "test_queries":
        len(
            test_queries
        ),

    "best_threshold":
        best_threshold,

    "calibration_component_accuracy":
        best_score,

    "results":
        {},

    "by_parent_count":
        {},
}


all_summary = (
    summary_df[
        summary_df[
            "parent_count"
        ]
        == "ALL"
    ]
)


for condition in (
    graph.CONDITIONS
):

    compact[
        "results"
    ][condition] = {}


    subset = all_summary[
        all_summary[
            "condition"
        ]
        == condition
    ]


    for _, row in (
        subset.iterrows()
    ):

        compact[
            "results"
        ][
            condition
        ][
            row["method"]
        ] = {
            "component_accuracy":
                float(
                    row[
                        "component_accuracy"
                    ]
                ),

            "parent_f1":
                float(
                    row[
                        "parent_f1"
                    ]
                ),

            "parent_set_exact":
                float(
                    row[
                        "parent_set_exact"
                    ]
                ),

            "component_set_exact":
                float(
                    row[
                        "component_set_exact"
                    ]
                ),

            "mean_cut_edges":
                float(
                    row[
                        "mean_cut_edges"
                    ]
                ),
        }


for parent_count in [
    2,
    3,
]:

    compact[
        "by_parent_count"
    ][
        str(
            parent_count
        )
    ] = {}


    pc_rows = summary_df[
        summary_df[
            "parent_count"
        ]
        == parent_count
    ]


    for condition in (
        graph.CONDITIONS
    ):

        compact[
            "by_parent_count"
        ][
            str(
                parent_count
            )
        ][
            condition
        ] = {}


        subset = pc_rows[
            pc_rows[
                "condition"
            ]
            == condition
        ]


        for _, row in (
            subset.iterrows()
        ):

            compact[
                "by_parent_count"
            ][
                str(
                    parent_count
                )
            ][
                condition
            ][
                row["method"]
            ] = {
                "component_accuracy":
                    float(
                        row[
                            "component_accuracy"
                        ]
                    ),

                "parent_f1":
                    float(
                        row[
                            "parent_f1"
                        ]
                    ),

                "parent_set_exact":
                    float(
                        row[
                            "parent_set_exact"
                        ]
                    ),
            }


(
    RESULT_ROOT
    / "phase5h_summary.json"
).write_text(
    json.dumps(
        compact,
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
    "PHASE 5H RESULT"
)
print(
    "======================================"
)

print(
    json.dumps(
        compact,
        ensure_ascii=False,
        indent=2,
    )
)

print()
print(
    "JSON: "
    "results\\phase5h_summary.json"
)