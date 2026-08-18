import hashlib
import json
import random
from collections import defaultdict, deque
from pathlib import Path

import pandas as pd

import phase5c2_strong_baseline as base


SEED = 20260812
CALIBRATION_PER_K = 25

THRESHOLD_GRID = [
    0.0,
    0.005,
    0.01,
    0.02,
    0.05,
    0.10,
    0.20,
]

CONDITIONS = [
    "CLEAN",
    "DROP30",
    "BRIDGE",
    "DROP30_BRIDGE",
]

RESULT_ROOT = Path("results")
RESULT_ROOT.mkdir(exist_ok=True)


# =========================================================
# Stable RNG
# =========================================================

def stable_rng(*parts):

    text = "|".join(
        str(x)
        for x in parts
    )

    digest = hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()

    return random.Random(
        int(
            digest[:16],
            16
        )
    )


# =========================================================
# Graph corruption
# =========================================================

def edge_key(a, b):

    return tuple(
        sorted(
            (a, b)
        )
    )


def corrupt_edges(
    public_query,
    gt,
    condition
):

    edges = {
        edge_key(
            edge["source"],
            edge["target"]
        )
        for edge
        in public_query["edges"]
    }

    rng = stable_rng(
        SEED,
        public_query["query_id"],
        condition,
    )


    # -----------------------------------------------------
    # Drop 30%
    # -----------------------------------------------------

    if condition in {
        "DROP30",
        "DROP30_BRIDGE",
    }:

        edge_list = sorted(
            edges
        )

        delete_count = int(
            round(
                len(edge_list)
                * 0.30
            )
        )

        if (
            edge_list
            and
            delete_count == 0
        ):
            delete_count = 1

        if delete_count > 0:

            delete_set = set(
                rng.sample(
                    edge_list,
                    min(
                        delete_count,
                        len(edge_list)
                    )
                )
            )

            edges -= delete_set


    # -----------------------------------------------------
    # Cross-parent bridges
    # -----------------------------------------------------

    if condition in {
        "BRIDGE",
        "DROP30_BRIDGE",
    }:

        nodes_by_parent = (
            defaultdict(list)
        )

        for (
            node_id,
            hidden
        ) in gt[
            "hidden_nodes"
        ].items():

            nodes_by_parent[
                hidden[
                    "source_mod"
                ]
            ].append(
                node_id
            )


        parents = sorted(
            gt["parents"]
        )


        for index in range(
            len(parents) - 1
        ):

            parent_a = (
                parents[index]
            )

            parent_b = (
                parents[index + 1]
            )

            nodes_a = (
                nodes_by_parent[
                    parent_a
                ]
            )

            nodes_b = (
                nodes_by_parent[
                    parent_b
                ]
            )

            if (
                not nodes_a
                or
                not nodes_b
            ):
                continue

            a = rng.choice(
                nodes_a
            )

            b = rng.choice(
                nodes_b
            )

            edges.add(
                edge_key(
                    a,
                    b
                )
            )


    return [
        {
            "source": a,
            "target": b,
            "edge_type":
                "CLASS_REF",
        }
        for a, b
        in sorted(edges)
    ]


# =========================================================
# Evidence
# =========================================================

def build_evidence(
    public_query,
    gt,
    representation
):

    evidence = {}


    for node_id in gt[
        "ground_truth"
    ].keys():

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
            hidden["source_mod"],
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
            ] = distances


    return evidence


# =========================================================
# Graph helpers
# =========================================================

def adjacency_from_edges(
    all_nodes,
    edges
):

    adjacency = {
        node: set()
        for node
        in all_nodes
    }


    for edge in edges:

        a = edge["source"]
        b = edge["target"]

        adjacency.setdefault(
            a,
            set()
        ).add(b)

        adjacency.setdefault(
            b,
            set()
        ).add(a)


    return adjacency


# =========================================================
# Tarjan bridge detection
# =========================================================

def find_bridges(
    all_nodes,
    edges
):

    adjacency = (
        adjacency_from_edges(
            all_nodes,
            edges
        )
    )

    timer = [0]

    tin = {}
    low = {}

    visited = set()

    bridges = set()


    def dfs(
        node,
        parent=None
    ):

        visited.add(node)

        timer[0] += 1

        tin[node] = (
            timer[0]
        )

        low[node] = (
            timer[0]
        )


        for nxt in adjacency.get(
            node,
            set()
        ):

            if nxt == parent:
                continue


            if nxt in visited:

                low[node] = min(
                    low[node],
                    tin[nxt]
                )

                continue


            dfs(
                nxt,
                node
            )

            low[node] = min(
                low[node],
                low[nxt]
            )


            if (
                low[nxt]
                > tin[node]
            ):

                bridges.add(
                    edge_key(
                        node,
                        nxt
                    )
                )


    for node in all_nodes:

        if node not in visited:

            dfs(node)


    return bridges


# =========================================================
# BFS after removing bridge
# =========================================================

def bfs_side(
    start,
    adjacency,
    blocked_edge
):

    visited = {
        start
    }

    queue = deque([
        start
    ])


    while queue:

        cur = (
            queue.popleft()
        )


        for nxt in adjacency.get(
            cur,
            set()
        ):

            if (
                edge_key(
                    cur,
                    nxt
                )
                == blocked_edge
            ):
                continue


            if nxt in visited:
                continue


            visited.add(
                nxt
            )

            queue.append(
                nxt
            )


    return visited


# =========================================================
# Parent preference of one graph side
# =========================================================

def side_preference(
    target_nodes,
    evidence
):

    target_nodes = [
        node

        for node
        in target_nodes

        if node in evidence
    ]


    if not target_nodes:
        return None


    candidate_mods = sorted(
        {
            mod

            for node
            in target_nodes

            for mod
            in evidence[
                node
            ].keys()
        }
    )


    scores = {}


    for mod in candidate_mods:

        total = 0.0
        valid = True


        for node in target_nodes:

            distances = (
                evidence[node]
            )


            if mod not in distances:

                valid = False
                break


            best = min(
                distances.values()
            )


            total += (
                distances[mod]
                - best
            ) / 128.0


        if valid:

            scores[mod] = (
                total
                / len(
                    target_nodes
                )
            )


    if not scores:
        return None


    ranked = sorted(
        scores.items(),
        key=lambda x: (
            x[1],
            x[0]
        ),
    )


    best_mod, (
        best_cost
    ) = ranked[0]


    if len(ranked) >= 2:

        confidence = (
            ranked[1][1]
            - best_cost
        )

    else:

        confidence = 1.0


    return {
        "best_mod":
            best_mod,

        "best_cost":
            best_cost,

        "confidence":
            confidence,

        "target_count":
            len(
                target_nodes
            ),
    }


# =========================================================
# Provenance boundary pruning
# =========================================================

def boundary_prune(
    evidence,
    all_nodes,
    edges,
    threshold
):

    current_edges = {
        edge_key(
            edge["source"],
            edge["target"]
        )
        for edge
        in edges
    }

    removed = []


    for _ in range(20):

        edge_rows = [
            {
                "source": a,
                "target": b,
                "edge_type":
                    "CLASS_REF",
            }
            for a, b
            in sorted(
                current_edges
            )
        ]


        bridges = find_bridges(
            all_nodes,
            edge_rows
        )


        if not bridges:
            break


        adjacency = (
            adjacency_from_edges(
                all_nodes,
                edge_rows
            )
        )


        to_remove = []


        for bridge in sorted(
            bridges
        ):

            a, b = bridge


            side_a = bfs_side(
                a,
                adjacency,
                bridge
            )

            side_b = bfs_side(
                b,
                adjacency,
                bridge
            )


            target_a = (
                set(side_a)
                & set(
                    evidence.keys()
                )
            )

            target_b = (
                set(side_b)
                & set(
                    evidence.keys()
                )
            )


            if (
                not target_a
                or
                not target_b
            ):
                continue


            pref_a = (
                side_preference(
                    target_a,
                    evidence
                )
            )

            pref_b = (
                side_preference(
                    target_b,
                    evidence
                )
            )


            if (
                pref_a is None
                or
                pref_b is None
            ):
                continue


            # Same provenance preference:
            # retain dependency.
            if (
                pref_a[
                    "best_mod"
                ]
                == pref_b[
                    "best_mod"
                ]
            ):
                continue


            boundary_confidence = min(
                pref_a[
                    "confidence"
                ],
                pref_b[
                    "confidence"
                ],
            )


            if (
                boundary_confidence
                >= threshold
            ):

                to_remove.append(
                    (
                        bridge,
                        {
                            "left_parent":
                                pref_a[
                                    "best_mod"
                                ],

                            "right_parent":
                                pref_b[
                                    "best_mod"
                                ],

                            "left_confidence":
                                pref_a[
                                    "confidence"
                                ],

                            "right_confidence":
                                pref_b[
                                    "confidence"
                                ],
                        },
                    )
                )


        if not to_remove:
            break


        for (
            bridge,
            info
        ) in to_remove:

            if bridge not in (
                current_edges
            ):
                continue


            current_edges.remove(
                bridge
            )


            removed.append({
                "edge":
                    bridge,

                **info,
            })


    pruned_edges = [
        {
            "source": a,
            "target": b,
            "edge_type":
                "CLASS_REF",
        }
        for a, b
        in sorted(
            current_edges
        )
    ]


    return (
        pruned_edges,
        removed,
    )


# =========================================================
# B5 assignment
# =========================================================

def boundary_assignment(
    evidence,
    all_nodes,
    edges,
    threshold
):

    (
        pruned_edges,
        removed
    ) = (
        boundary_prune(
            evidence,
            all_nodes,
            edges,
            threshold,
        )
    )


    (
        predictions,
        parents
    ) = (
        base.dependency_assignment(
            evidence,
            all_nodes,
            pruned_edges,
        )
    )


    return (
        predictions,
        parents,
        len(removed),
    )


# =========================================================
# Same calibration/test split as Phase 5D
# =========================================================

gt_by_id = {
    row["query_id"]:
        row

    for row
    in base.ground_truth_rows
}


queries_by_k = (
    defaultdict(list)
)


for query in (
    base.public_queries
):

    queries_by_k[
        query[
            "parent_count"
        ]
    ].append(
        query
    )


calibration_queries = []
test_queries = []


for (
    k,
    queries
) in queries_by_k.items():

    local = list(
        queries
    )

    rng = stable_rng(
        SEED,
        "split",
        k,
    )

    rng.shuffle(
        local
    )


    calibration_queries.extend(
        local[
            :CALIBRATION_PER_K
        ]
    )


    test_queries.extend(
        local[
            CALIBRATION_PER_K:
        ]
    )


print()

print(
    "Calibration queries:",
    len(
        calibration_queries
    )
)

print(
    "Test queries:",
    len(
        test_queries
    )
)


# =========================================================
# Tune boundary threshold
#
# Calibration includes stress conditions.
# Test queries remain disjoint.
# =========================================================

best_thresholds = {}


for representation in (
    base.REPRESENTATIONS
):

    print()

    print(
        "======================================"
    )

    print(
        "Tuning",
        representation
    )

    print(
        "======================================"
    )


    best_score = None
    best_threshold = None


    for threshold in (
        THRESHOLD_GRID
    ):

        metrics_all = []


        for public_query in (
            calibration_queries
        ):

            gt = gt_by_id[
                public_query[
                    "query_id"
                ]
            ]


            evidence = (
                build_evidence(
                    public_query,
                    gt,
                    representation,
                )
            )


            true_labels = (
                gt[
                    "ground_truth"
                ]
            )


            if (
                len(evidence)
                != len(
                    true_labels
                )
            ):
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


            for condition in (
                CONDITIONS
            ):

                edges = (
                    corrupt_edges(
                        public_query,
                        gt,
                        condition,
                    )
                )


                (
                    predictions,
                    predicted_parents,
                    _
                ) = (
                    boundary_assignment(
                        evidence,
                        all_nodes,
                        edges,
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


                metrics_all.append(
                    metrics
                )


        if not metrics_all:
            continue


        component = sum(
            row[
                "component_accuracy"
            ]

            for row
            in metrics_all
        ) / len(
            metrics_all
        )


        parent_f1 = sum(
            row[
                "parent_f1"
            ]

            for row
            in metrics_all
        ) / len(
            metrics_all
        )


        score = (
            component
            + parent_f1
        ) / 2.0


        print(
            "threshold=",
            threshold,
            "component=",
            round(
                component,
                4
            ),
            "parent_f1=",
            round(
                parent_f1,
                4
            ),
            "score=",
            round(
                score,
                4
            ),
        )


        if (
            best_score is None
            or
            score > best_score
        ):

            best_score = (
                score
            )

            best_threshold = (
                threshold
            )


    best_thresholds[
        representation
    ] = {
        "threshold":
            best_threshold,

        "calibration_score":
            best_score,
    }


print()

print(
    "BEST THRESHOLDS"
)

print(
    json.dumps(
        best_thresholds,
        ensure_ascii=False,
        indent=2,
    )
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

    gt = gt_by_id[
        public_query[
            "query_id"
        ]
    ]


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


    for representation in (
        base.REPRESENTATIONS
    ):

        evidence = (
            build_evidence(
                public_query,
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
            continue


        # B1
        independent = (
            base.independent_assignment(
                evidence
            )
        )

        independent_parents = (
            sorted(
                set(
                    independent.values()
                )
            )
        )


        # B2 strong
        (
            exact_assignments,
            exact_parents
        ) = (
            base.exact_global_parentset(
                evidence,
                public_query[
                    "parent_count"
                ],
            )
        )


        threshold = (
            best_thresholds[
                representation
            ][
                "threshold"
            ]
        )


        for condition in (
            CONDITIONS
        ):

            edges = (
                corrupt_edges(
                    public_query,
                    gt,
                    condition,
                )
            )


            # B3
            (
                hard_predictions,
                hard_parents
            ) = (
                base.dependency_assignment(
                    evidence,
                    all_nodes,
                    edges,
                )
            )


            # B5
            (
                boundary_predictions,
                boundary_parents,
                removed_count
            ) = (
                boundary_assignment(
                    evidence,
                    all_nodes,
                    edges,
                    threshold,
                )
            )


            methods = [
                (
                    "B1_INDEPENDENT",
                    independent,
                    independent_parents,
                    0,
                ),
                (
                    "B2_EXACT_GLOBAL",
                    exact_assignments,
                    exact_parents,
                    0,
                ),
                (
                    "B3_HARD_COMPONENT",
                    hard_predictions,
                    hard_parents,
                    0,
                ),
                (
                    "B5_BOUNDARY_CUT",
                    boundary_predictions,
                    boundary_parents,
                    removed_count,
                ),
            ]


            for (
                method,
                predictions,
                predicted_parents,
                cut_edges
            ) in methods:

                metrics = (
                    base.evaluate_query(
                        true_labels,
                        gt["parents"],
                        predictions,
                        predicted_parents,
                    )
                )


                raw_rows.append({
                    "query_id":
                        public_query[
                            "query_id"
                        ],

                    "parent_count":
                        public_query[
                            "parent_count"
                        ],

                    "representation":
                        representation,

                    "condition":
                        condition,

                    "method":
                        method,

                    "cut_edges":
                        cut_edges,

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
            len(
                test_queries
            )
        )


# =========================================================
# Save
# =========================================================

raw = pd.DataFrame(
    raw_rows
)


raw.to_csv(
    RESULT_ROOT
    / "phase5e_boundary_cut_raw.csv",

    index=False,
    encoding="utf-8-sig",
)


summary_rows = []


for (
    representation,
    condition,
    method
), group in raw.groupby(
    [
        "representation",
        "condition",
        "method",
    ]
):

    summary_rows.append({
        "representation":
            representation,

        "condition":
            condition,

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
    / "phase5e_boundary_cut_summary.csv",

    index=False,
    encoding="utf-8-sig",
)


compact = {
    "calibration_queries":
        len(
            calibration_queries
        ),

    "test_queries":
        len(
            test_queries
        ),

    "best_thresholds":
        best_thresholds,

    "results": {},
}


for representation in (
    base.REPRESENTATIONS
):

    compact[
        "results"
    ][representation] = {}


    for condition in (
        CONDITIONS
    ):

        compact[
            "results"
        ][
            representation
        ][condition] = {}


        subset = summary_df[
            (
                summary_df[
                    "representation"
                ]
                == representation
            )
            &
            (
                summary_df[
                    "condition"
                ]
                == condition
            )
        ]


        for _, row in (
            subset.iterrows()
        ):

            compact[
                "results"
            ][
                representation
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


(
    RESULT_ROOT
    / "phase5e_summary.json"
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
    "PHASE 5E RESULT"
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
    "results\\phase5e_summary.json"
)