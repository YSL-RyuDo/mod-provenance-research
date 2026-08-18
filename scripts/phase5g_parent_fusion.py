import json
import statistics
from collections import defaultdict
from pathlib import Path

import pandas as pd

import phase5c2_strong_baseline as base


RESULT_ROOT = Path("results")
RESULT_ROOT.mkdir(exist_ok=True)

REPRESENTATIONS = [
    "OPCODE_3GRAM",
    "OPCODE_STRUCT",
    "OPCODE_CONTEXT",
]


# =========================================================
# Build evidence for one representation
# =========================================================

def build_rep_evidence(
    gt,
    representation
):

    evidence = {}

    for node_id in (
        gt[
            "ground_truth"
        ].keys()
    ):

        hidden = (
            gt[
                "hidden_nodes"
            ][node_id]
        )

        class_name = (
            base.p3d.path_to_class_name(
                hidden[
                    "source_path"
                ]
            )
        )

        key = (
            hidden[
                "source_mod"
            ],
            hidden[
                "historical_version_id"
            ],
            class_name,
        )

        distances = (
            base.distance_cache.get(
                (
                    key,
                    representation
                )
            )
        )

        if distances:

            evidence[
                node_id
            ] = dict(
                distances
            )

    return evidence


# =========================================================
# Normalized regret
#
# 0 = best candidate in representation
# 1 = worst candidate in representation
# =========================================================

def regret_vector(
    distances
):

    values = list(
        distances.values()
    )

    if not values:
        return {}

    minimum = min(
        values
    )

    maximum = max(
        values
    )

    scale = (
        maximum - minimum
    )

    if scale <= 0:

        return {
            mod: 0.0
            for mod
            in distances
        }

    return {
        mod:
            (
                distance
                - minimum
            )
            / scale

        for mod, distance
        in distances.items()
    }


# =========================================================
# Normalized rank
#
# Tie candidates receive identical rank.
# =========================================================

def rank_vector(
    distances
):

    if not distances:
        return {}

    grouped = defaultdict(
        list
    )

    for mod, distance in (
        distances.items()
    ):

        grouped[
            distance
        ].append(
            mod
        )


    sorted_distances = sorted(
        grouped.keys()
    )

    total_candidates = len(
        distances
    )

    result = {}

    position = 0


    for distance in (
        sorted_distances
    ):

        mods = sorted(
            grouped[
                distance
            ]
        )

        # same distance = same rank
        if total_candidates > 1:

            normalized_rank = (
                position
                / (
                    total_candidates
                    - 1
                )
            )

        else:

            normalized_rank = 0.0


        for mod in mods:

            result[
                mod
            ] = (
                normalized_rank
            )


        position += len(
            mods
        )


    return result


# =========================================================
# Fusion
# =========================================================

def fuse_evidence(
    evidence_by_rep,
    method
):

    fused = {}


    all_nodes = set()

    for rep_evidence in (
        evidence_by_rep.values()
    ):

        all_nodes.update(
            rep_evidence.keys()
        )


    for node_id in (
        all_nodes
    ):

        vectors = []


        for representation in (
            REPRESENTATIONS
        ):

            rep_evidence = (
                evidence_by_rep.get(
                    representation,
                    {}
                )
            )

            distances = (
                rep_evidence.get(
                    node_id
                )
            )

            if not distances:
                continue


            if method in {
                "MEAN_REGRET",
                "MEDIAN_REGRET",
            }:

                vector = (
                    regret_vector(
                        distances
                    )
                )


            elif (
                method
                == "MEAN_RANK"
            ):

                vector = (
                    rank_vector(
                        distances
                    )
                )


            else:

                raise ValueError(
                    method
                )


            vectors.append(
                vector
            )


        if not vectors:
            continue


        candidate_mods = set()

        for vector in vectors:

            candidate_mods.update(
                vector.keys()
            )


        fused_distances = {}


        for mod in (
            candidate_mods
        ):

            values = [
                vector[mod]

                for vector
                in vectors

                if mod in vector
            ]


            if not values:
                continue


            if (
                method
                == "MEDIAN_REGRET"
            ):

                score = (
                    statistics.median(
                        values
                    )
                )

            else:

                score = (
                    sum(values)
                    / len(values)
                )


            fused_distances[
                mod
            ] = score


        fused[
            node_id
        ] = (
            fused_distances
        )


    return fused


# =========================================================
# Evaluate
# =========================================================

gt_by_id = {
    row["query_id"]:
        row

    for row
    in base.ground_truth_rows
}


raw_rows = []


METHODS = [
    "SINGLE_3GRAM",
    "SINGLE_STRUCT",
    "SINGLE_CONTEXT",
    "MEAN_REGRET",
    "MEDIAN_REGRET",
    "MEAN_RANK",
]


for (
    query_index,
    public_query
) in enumerate(
    base.public_queries,
    start=1,
):

    query_id = (
        public_query[
            "query_id"
        ]
    )

    gt = (
        gt_by_id[
            query_id
        ]
    )

    true_labels = (
        gt[
            "ground_truth"
        ]
    )

    true_parents = (
        gt[
            "parents"
        ]
    )


    evidence_by_rep = {}


    valid = True


    for representation in (
        REPRESENTATIONS
    ):

        evidence = (
            build_rep_evidence(
                gt,
                representation,
            )
        )

        if (
            len(evidence)
            != len(
                true_labels
            )
        ):

            valid = False
            break


        evidence_by_rep[
            representation
        ] = evidence


    if not valid:
        continue


    # =====================================================
    # Single representation baselines
    # =====================================================

    single_mapping = {
        "SINGLE_3GRAM":
            "OPCODE_3GRAM",

        "SINGLE_STRUCT":
            "OPCODE_STRUCT",

        "SINGLE_CONTEXT":
            "OPCODE_CONTEXT",
    }


    for (
        method,
        representation
    ) in single_mapping.items():

        evidence = (
            evidence_by_rep[
                representation
            ]
        )


        (
            assignments,
            parents
        ) = (
            base.exact_global_parentset(
                evidence,
                public_query[
                    "parent_count"
                ],
            )
        )


        metrics = (
            base.evaluate_query(
                true_labels,
                true_parents,
                assignments,
                parents,
            )
        )


        raw_rows.append({
            "query_id":
                query_id,

            "parent_count":
                public_query[
                    "parent_count"
                ],

            "method":
                method,

            **metrics,
        })


    # =====================================================
    # Fixed fusion
    # =====================================================

    for method in [
        "MEAN_REGRET",
        "MEDIAN_REGRET",
        "MEAN_RANK",
    ]:

        fused = (
            fuse_evidence(
                evidence_by_rep,
                method,
            )
        )


        (
            assignments,
            parents
        ) = (
            base.exact_global_parentset(
                fused,
                public_query[
                    "parent_count"
                ],
            )
        )


        metrics = (
            base.evaluate_query(
                true_labels,
                true_parents,
                assignments,
                parents,
            )
        )


        raw_rows.append({
            "query_id":
                query_id,

            "parent_count":
                public_query[
                    "parent_count"
                ],

            "method":
                method,

            **metrics,
        })


    if (
        query_index % 25
        == 0
    ):

        print(
            "evaluated",
            query_index,
            "/",
            len(
                base.public_queries
            )
        )


# =========================================================
# Save raw
# =========================================================

raw = pd.DataFrame(
    raw_rows
)


raw.to_csv(
    RESULT_ROOT
    / "phase5g_parent_fusion_raw.csv",

    index=False,
    encoding="utf-8-sig",
)


# =========================================================
# Summary
# =========================================================

summary_rows = []


for (
    method,
    parent_count
), group in raw.groupby(
    [
        "method",
        "parent_count",
    ]
):

    summary_rows.append({
        "method":
            method,

        "parent_count":
            int(
                parent_count
            ),

        "queries":
            len(
                group
            ),

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
    })


for method, group in (
    raw.groupby(
        "method"
    )
):

    summary_rows.append({
        "method":
            method,

        "parent_count":
            "ALL",

        "queries":
            len(
                group
            ),

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
    })


summary_df = pd.DataFrame(
    summary_rows
)


summary_df.to_csv(
    RESULT_ROOT
    / "phase5g_parent_fusion_summary.csv",

    index=False,
    encoding="utf-8-sig",
)


# =========================================================
# Compact JSON
# =========================================================

compact = {
    "queries":
        len(
            base.public_queries
        ),

    "results":
        {},
}


all_rows = (
    summary_df[
        summary_df[
            "parent_count"
        ]
        == "ALL"
    ]
)


for _, row in (
    all_rows.iterrows()
):

    compact[
        "results"
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
    }


(
    RESULT_ROOT
    / "phase5g_summary.json"
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
    "PHASE 5G RESULT"
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
    "results\\phase5g_summary.json"
)