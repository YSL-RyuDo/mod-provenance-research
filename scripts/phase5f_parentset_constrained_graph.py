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
    0.0025,
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
# Deterministic RNG
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
    # DROP 30%
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
    # Cross-parent bridge
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
            ] = distances

    return evidence


# =========================================================
# Graph
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

        visited.add(
            node
        )

        timer[0] += 1

        tin[node] = (
            timer[0]
        )

        low[node] = (
            timer[0]
        )


        for nxt in (
            adjacency.get(
                node,
                set()
            )
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

            dfs(
                node
            )


    return bridges


# =========================================================
# BFS side after bridge removal
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


        for nxt in (
            adjacency.get(
                cur,
                set()
            )
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
# Restricted side preference
# =========================================================

def side_preference(
    target_nodes,
    evidence,
    candidate_parents
):

    target_nodes = [
        node

        for node
        in target_nodes

        if node in evidence
    ]


    if not target_nodes:
        return None


    scores = {}


    for parent in (
        candidate_parents
    ):

        total = 0.0
        valid = True


        for node in (
            target_nodes
        ):

            distances = (
                evidence[node]
            )


            if parent not in (
                distances
            ):

                valid = False
                break


            best = min(
                distances[p]
                for p
                in candidate_parents
                if p in distances
            )


            total += (
                distances[parent]
                - best
            ) / 128.0


        if valid:

            scores[parent] = (
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


    best_parent = (
        ranked[0][0]
    )

    best_cost = (
        ranked[0][1]
    )


    if len(ranked) >= 2:

        confidence = (
            ranked[1][1]
            - best_cost
        )

    else:

        confidence = 1.0


    return {
        "best_parent":
            best_parent,

        "confidence":
            confidence,

        "target_count":
            len(
                target_nodes
            ),
    }


# =========================================================
# Boundary pruning
# =========================================================

def boundary_prune(
    evidence,
    all_nodes,
    edges,
    candidate_parents,
    threshold,
):

    current_edges = {
        edge_key(
            edge["source"],
            edge["target"]
        )
        for edge
        in edges
    }

    removed_count = 0


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


        bridges = (
            find_bridges(
                all_nodes,
                edge_rows
            )
        )


        if not bridges:
            break


        adjacency = (
            adjacency_from_edges(
                all_nodes,
                edge_rows
            )
        )


        remove_now = []


        for bridge in (
            sorted(
                bridges
            )
        ):

            a, b = bridge


            side_a = bfs_side(
                a,
                adjacency,
                bridge,
            )

            side_b = bfs_side(
                b,
                adjacency,
                bridge,
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
                    evidence,
                    candidate_parents,
                )
            )

            pref_b = (
                side_preference(
                    target_b,
                    evidence,
                    candidate_parents,
                )
            )


            if (
                pref_a is None
                or
                pref_b is None
            ):
                continue


            if (
                pref_a[
                    "best_parent"
                ]
                == pref_b[
                    "best_parent"
                ]
            ):
                continue


            confidence = min(
                pref_a[
                    "confidence"
                ],
                pref_b[
                    "confidence"
                ],
            )


            if (
                confidence
                >= threshold
            ):

                remove_now.append(
                    bridge
                )


        if not remove_now:
            break


        for bridge in (
            remove_now
        ):

            if (
                bridge
                in current_edges
            ):

                current_edges.remove(
                    bridge
                )

                removed_count += 1


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
        removed_count,
    )


# =========================================================
# Assign graph components
# =========================================================

def constrained_component_assignment(
    evidence,
    all_nodes,
    edges,
    candidate_parents,
):

    components = (
        base.connected_components(
            all_nodes,
            edges,
        )
    )

    predictions = {}


    for component in (
        components
    ):

        target_nodes = [
            node

            for node
            in component

            if node in evidence
        ]


        if not target_nodes:
            continue


        costs = {}


        for parent in (
            candidate_parents
        ):

            total = 0.0
            valid = True


            for node in (
                target_nodes
            ):

                distances = (
                    evidence[node]
                )


                if parent not in (
                    distances
                ):

                    valid = False
                    break


                best = min(
                    distances[p]
                    for p
                    in candidate_parents
                    if p in distances
                )


                total += (
                    distances[parent]
                    - best
                )


            if valid:

                costs[parent] = (
                    total
                )


        if not costs:
            continue


        chosen = sorted(
            costs.items(),
            key=lambda x: (
                x[1],
                x[0]
            ),
        )[0][0]


        for node in (
            target_nodes
        ):

            predictions[node] = (
                chosen
            )


    return predictions


# =========================================================
# Full hierarchical method
# =========================================================

def hierarchical_assignment(
    evidence,
    all_nodes,
    edges,
    candidate_parents,
    threshold,
):

    (
        pruned_edges,
        cut_count
    ) = (
        boundary_prune(
            evidence,
            all_nodes,
            edges,
            candidate_parents,
            threshold,
        )
    )


    predictions = (
        constrained_component_assignment(
            evidence,
            all_nodes,
            pruned_edges,
            candidate_parents,
        )
    )


    # Parent-set retrieval is handled
    # by Stage 1.
    predicted_parents = list(
        candidate_parents
    )


    return (
        predictions,
        predicted_parents,
        cut_count,
    )


# =========================================================
# Calibration/test split
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
    rows
) in queries_by_k.items():

    local = list(
        rows
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
# Tune threshold using predicted parent set
#
# Parent retrieval itself is fixed;
# calibration optimizes component attribution only.
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
                build_evidence(
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
                    _,
                    _
                ) = (
                    hierarchical_assignment(
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
                        gt[
                            "parents"
                        ],
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
            sum(
                accuracies
            )
            / len(
                accuracies
            )
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

        "calibration_component_accuracy":
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


        # -------------------------------------------------
        # Stage 1 predicted parent set
        # -------------------------------------------------

        (
            exact_assignments,
            predicted_parent_set
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


            # =============================================
            # B2
            # =============================================

            metrics = (
                base.evaluate_query(
                    true_labels,
                    gt[
                        "parents"
                    ],
                    exact_assignments,
                    predicted_parent_set,
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
                    "B2_EXACT_GLOBAL",

                "cut_edges":
                    0,

                **metrics,
            })


            # =============================================
            # B3 original graph
            # =============================================

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


            metrics = (
                base.evaluate_query(
                    true_labels,
                    gt[
                        "parents"
                    ],
                    hard_predictions,
                    hard_parents,
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
                    "B3_HARD_COMPONENT",

                "cut_edges":
                    0,

                **metrics,
            })


            # =============================================
            # B6 predicted-parent constrained
            # =============================================

            (
                hybrid_predictions,
                hybrid_parents,
                hybrid_cut_count
            ) = (
                hierarchical_assignment(
                    evidence,
                    all_nodes,
                    edges,
                    predicted_parent_set,
                    threshold,
                )
            )


            metrics = (
                base.evaluate_query(
                    true_labels,
                    gt[
                        "parents"
                    ],
                    hybrid_predictions,
                    hybrid_parents,
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
                    "B6_PARENTSET_GRAPH",

                "cut_edges":
                    hybrid_cut_count,

                **metrics,
            })


            # =============================================
            # Oracle diagnostic
            #
            # NOT a baseline.
            # Shows headroom if Stage-1 parent
            # retrieval were perfect.
            # =============================================

            true_parent_set = list(
                gt["parents"]
            )


            (
                oracle_predictions,
                oracle_parents,
                oracle_cut_count
            ) = (
                hierarchical_assignment(
                    evidence,
                    all_nodes,
                    edges,
                    true_parent_set,
                    threshold,
                )
            )


            metrics = (
                base.evaluate_query(
                    true_labels,
                    gt[
                        "parents"
                    ],
                    oracle_predictions,
                    oracle_parents,
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
                    "ORACLE_PARENTSET_GRAPH",

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
    / "phase5f_parentset_graph_raw.csv",

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
    / "phase5f_parentset_graph_summary.csv",

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

    "results":
        {},
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
    / "phase5f_summary.json"
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
    "PHASE 5F RESULT"
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
    "results\\phase5f_summary.json"
)