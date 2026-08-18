import hashlib
import json
import math
import random
from collections import Counter, defaultdict, deque
from pathlib import Path

import phase5c2_strong_baseline as base


SEED = 20260812

CALIBRATION_PER_K = 25
TOP_M = 10

LAMBDA_GRID = [
    0.0,
    0.05,
    0.10,
    0.20,
    0.40,
]

GAMMA_GRID = [
    0.0,
    0.10,
    0.25,
    0.50,
    1.00,
]

RESULT_ROOT = Path("results")


# =========================================================
# Utilities
# =========================================================

def stable_rng(*parts):

    text = "|".join(
        str(x)
        for x in parts
    )

    digest = hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()

    seed = int(
        digest[:16],
        16
    )

    return random.Random(seed)


def build_evidence(
    public_query,
    gt,
    representation
):

    evidence = {}

    for node_id in (
        gt["ground_truth"].keys()
    ):

        hidden = (
            gt[
                "hidden_nodes"
            ][node_id]
        )

        class_name = (
            base.p3d.path_to_class_name(
                hidden["source_path"]
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
            evidence[node_id] = (
                distances
            )

    return evidence


# =========================================================
# Graph manipulation
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

    original_edges = {
        edge_key(
            edge["source"],
            edge["target"]
        )
        for edge
        in public_query["edges"]
    }

    edges = set(
        original_edges
    )

    rng = stable_rng(
        SEED,
        public_query["query_id"],
        condition
    )

    # -----------------------------------------------------
    # 30% edge deletion
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
            len(edge_list) > 0
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
    #
    # K parents -> K-1 bridges
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
        ) in (
            gt[
                "hidden_nodes"
            ].items()
        ):

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

        # chain:
        # A-B, B-C, ...
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
# Candidate parents
# =========================================================

def candidate_labels(
    evidence,
    top_m
):

    aggregate = defaultdict(
        float
    )

    for node_id, distances in (
        evidence.items()
    ):

        if not distances:
            continue

        ordered = sorted(
            distances.items(),
            key=lambda x: (
                x[1],
                x[0]
            )
        )

        if len(ordered) <= 1:

            for mod, _ in ordered:
                aggregate[mod] += 0.0

            continue

        # rank-normalized unary
        for rank, (
            mod,
            distance
        ) in enumerate(
            ordered
        ):

            aggregate[mod] += (
                rank
                / (
                    len(ordered)
                    - 1
                )
            )

    ranked = sorted(
        aggregate.items(),
        key=lambda x: (
            x[1],
            x[0]
        )
    )

    return [
        mod
        for mod, _
        in ranked[:top_m]
    ]


# =========================================================
# Unary cost
# =========================================================

def unary_costs(
    evidence,
    labels
):

    result = {}

    for node_id, distances in (
        evidence.items()
    ):

        best_distance = min(
            distances.values()
        )

        costs = {}

        for label in labels:

            if label not in distances:

                costs[label] = 1.0
                continue

            # Hamming is 0..128
            costs[label] = (
                distances[label]
                - best_distance
            ) / 128.0

        result[node_id] = costs

    return result


# =========================================================
# Graph
# =========================================================

def adjacency_from_edges(
    all_node_ids,
    edges
):

    adjacency = {
        node: set()
        for node
        in all_node_ids
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
# Objective
# =========================================================

def objective(
    labels_by_node,
    target_nodes,
    unary,
    edges,
    lambda_value,
    gamma_value
):

    cost = 0.0

    # unary
    for node in target_nodes:

        label = (
            labels_by_node[
                node
            ]
        )

        cost += unary[
            node
        ][label]

    # graph disagreement
    for edge in edges:

        a = edge["source"]
        b = edge["target"]

        if (
            labels_by_node[a]
            != labels_by_node[b]
        ):

            cost += (
                lambda_value
            )

    # parent proliferation
    used = {
        labels_by_node[node]
        for node
        in target_nodes
    }

    cost += (
        gamma_value
        * len(used)
    )

    return cost


# =========================================================
# Initializations
# =========================================================

def initialize_nearest(
    all_node_ids,
    target_nodes,
    unary,
    adjacency,
    labels
):

    assignment = {}

    # TARGET = best unary
    for node in target_nodes:

        assignment[node] = min(
            labels,
            key=lambda label: (
                unary[
                    node
                ][label],
                label
            )
        )

    # connectors
    unresolved = [
        node
        for node
        in all_node_ids
        if node
        not in assignment
    ]

    for _ in range(
        len(all_node_ids) + 1
    ):

        changed = False

        for node in list(
            unresolved
        ):

            neighboring_labels = [
                assignment[n]
                for n
                in adjacency.get(
                    node,
                    set()
                )
                if n in assignment
            ]

            if not neighboring_labels:
                continue

            counts = Counter(
                neighboring_labels
            )

            assignment[node] = sorted(
                counts.items(),
                key=lambda x: (
                    -x[1],
                    x[0]
                )
            )[0][0]

            unresolved.remove(
                node
            )

            changed = True

        if not changed:
            break

    # isolated connector fallback
    fallback = labels[0]

    for node in unresolved:
        assignment[node] = (
            fallback
        )

    return assignment


def initialize_single_label(
    all_node_ids,
    label
):

    return {
        node: label
        for node
        in all_node_ids
    }


# =========================================================
# ICM
# =========================================================

def icm_optimize(
    initial,
    all_node_ids,
    target_nodes,
    unary,
    edges,
    labels,
    lambda_value,
    gamma_value,
):

    assignment = dict(
        initial
    )

    best_cost = objective(
        assignment,
        target_nodes,
        unary,
        edges,
        lambda_value,
        gamma_value,
    )

    ordered_nodes = sorted(
        all_node_ids
    )

    for _ in range(50):

        changed = False

        for node in ordered_nodes:

            current = (
                assignment[node]
            )

            local_best_label = (
                current
            )

            local_best_cost = (
                best_cost
            )

            for label in labels:

                if label == current:
                    continue

                assignment[node] = (
                    label
                )

                cost = objective(
                    assignment,
                    target_nodes,
                    unary,
                    edges,
                    lambda_value,
                    gamma_value,
                )

                if (
                    cost
                    < local_best_cost
                    - 1e-12
                ):

                    local_best_cost = (
                        cost
                    )

                    local_best_label = (
                        label
                    )

                elif (
                    math.isclose(
                        cost,
                        local_best_cost,
                        abs_tol=1e-12
                    )
                    and
                    label
                    < local_best_label
                ):

                    local_best_label = (
                        label
                    )

            assignment[node] = (
                local_best_label
            )

            if (
                local_best_label
                != current
            ):

                changed = True

                best_cost = (
                    local_best_cost
                )

        if not changed:
            break

    final_cost = objective(
        assignment,
        target_nodes,
        unary,
        edges,
        lambda_value,
        gamma_value,
    )

    return (
        assignment,
        final_cost
    )


# =========================================================
# Soft graph inference
# =========================================================

def soft_graph_assignment(
    evidence,
    all_node_ids,
    edges,
    lambda_value,
    gamma_value,
):

    target_nodes = set(
        evidence.keys()
    )

    labels = candidate_labels(
        evidence,
        TOP_M
    )

    if not labels:
        return {}, []

    unary = unary_costs(
        evidence,
        labels
    )

    adjacency = (
        adjacency_from_edges(
            all_node_ids,
            edges
        )
    )

    starts = []

    starts.append(
        initialize_nearest(
            all_node_ids,
            target_nodes,
            unary,
            adjacency,
            labels,
        )
    )

    # additional single-label starts
    for label in labels[:3]:

        starts.append(
            initialize_single_label(
                all_node_ids,
                label
            )
        )

    best_assignment = None
    best_cost = None

    for start in starts:

        assignment, cost = (
            icm_optimize(
                start,
                all_node_ids,
                target_nodes,
                unary,
                edges,
                labels,
                lambda_value,
                gamma_value,
            )
        )

        if (
            best_cost is None
            or
            cost < best_cost
        ):

            best_cost = cost
            best_assignment = (
                assignment
            )

    predictions = {
        node:
            best_assignment[node]
        for node
        in target_nodes
    }

    predicted_parents = sorted(
        set(
            predictions.values()
        )
    )

    return (
        predictions,
        predicted_parents
    )


# =========================================================
# Split calibration/test
# =========================================================

gt_by_id = {
    row["query_id"]:
        row
    for row
    in base.ground_truth_rows
}


queries_by_k = defaultdict(
    list
)

for query in (
    base.public_queries
):

    queries_by_k[
        query["parent_count"]
    ].append(
        query
    )


calibration_queries = []
test_queries = []


for k, queries in (
    queries_by_k.items()
):

    local = list(
        queries
    )

    rng = stable_rng(
        SEED,
        "split",
        k
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
    len(calibration_queries)
)

print(
    "Test queries:",
    len(test_queries)
)


# =========================================================
# Tune lambda/gamma on CLEAN calibration only
# =========================================================

best_params = {}


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
    best_pair = None


    for lambda_value in (
        LAMBDA_GRID
    ):

        for gamma_value in (
            GAMMA_GRID
        ):

            metric_rows = []

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

                predictions, (
                    predicted_parents
                ) = (
                    soft_graph_assignment(
                        evidence,
                        all_nodes,
                        public_query[
                            "edges"
                        ],
                        lambda_value,
                        gamma_value,
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

                metric_rows.append(
                    metrics
                )

            if not metric_rows:
                continue

            mean_component = sum(
                x[
                    "component_accuracy"
                ]
                for x
                in metric_rows
            ) / len(metric_rows)

            mean_parent_f1 = sum(
                x[
                    "parent_f1"
                ]
                for x
                in metric_rows
            ) / len(metric_rows)

            # equal weight
            score = (
                mean_component
                + mean_parent_f1
            ) / 2.0

            print(
                representation,
                "lambda=",
                lambda_value,
                "gamma=",
                gamma_value,
                "score=",
                round(score, 4)
            )

            if (
                best_score is None
                or
                score > best_score
            ):

                best_score = score

                best_pair = (
                    lambda_value,
                    gamma_value
                )


    best_params[
        representation
    ] = {
        "lambda":
            best_pair[0],

        "gamma":
            best_pair[1],

        "calibration_score":
            best_score,
    }


print()
print(
    "BEST PARAMETERS"
)
print(
    json.dumps(
        best_params,
        ensure_ascii=False,
        indent=2
    )
)


# =========================================================
# Test
# =========================================================

CONDITIONS = [
    "CLEAN",
    "DROP30",
    "BRIDGE",
    "DROP30_BRIDGE",
]


raw_rows = []


for query_index, public_query in (
    enumerate(
        test_queries,
        start=1
    )
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


        # -------------------------------------------------
        # Graph-independent baselines
        # same under all conditions
        # -------------------------------------------------

        independent = (
            base.independent_assignment(
                evidence
            )
        )

        independent_parents = sorted(
            set(
                independent.values()
            )
        )


        exact_assignments, (
            exact_parents
        ) = (
            base.exact_global_parentset(
                evidence,
                public_query[
                    "parent_count"
                ],
            )
        )


        for condition in (
            CONDITIONS
        ):

            corrupted_edges = (
                corrupt_edges(
                    public_query,
                    gt,
                    condition,
                )
            )


            # =============================================
            # B1
            # =============================================

            metrics = (
                base.evaluate_query(
                    true_labels,
                    gt["parents"],
                    independent,
                    independent_parents,
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
                    "B1_INDEPENDENT",

                **metrics,
            })


            # =============================================
            # B2 Exact Global
            # =============================================

            metrics = (
                base.evaluate_query(
                    true_labels,
                    gt["parents"],
                    exact_assignments,
                    exact_parents,
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

                **metrics,
            })


            # =============================================
            # B3 Hard connected-component dependency
            # =============================================

            hard_predictions, (
                hard_parents
            ) = (
                base.dependency_assignment(
                    evidence,
                    all_nodes,
                    corrupted_edges,
                )
            )

            metrics = (
                base.evaluate_query(
                    true_labels,
                    gt["parents"],
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

                **metrics,
            })


            # =============================================
            # B4 Soft graph
            # =============================================

            lambda_value = (
                best_params[
                    representation
                ][
                    "lambda"
                ]
            )

            gamma_value = (
                best_params[
                    representation
                ][
                    "gamma"
                ]
            )


            soft_predictions, (
                soft_parents
            ) = (
                soft_graph_assignment(
                    evidence,
                    all_nodes,
                    corrupted_edges,
                    lambda_value,
                    gamma_value,
                )
            )

            metrics = (
                base.evaluate_query(
                    true_labels,
                    gt["parents"],
                    soft_predictions,
                    soft_parents,
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
                    "B4_SOFT_GRAPH",

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
# Save
# =========================================================

import pandas as pd


raw = pd.DataFrame(
    raw_rows
)


raw.to_csv(
    RESULT_ROOT
    / "phase5d_soft_graph_raw.csv",

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
    / "phase5d_soft_graph_summary.csv",

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

    "best_params":
        best_params,

    "results":
        {},
}


for representation in (
    base.REPRESENTATIONS
):

    compact[
        "results"
    ][
        representation
    ] = {}

    for condition in (
        CONDITIONS
    ):

        compact[
            "results"
        ][
            representation
        ][
            condition
        ] = {}

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
            }


(
    RESULT_ROOT
    / "phase5d_summary.json"
).write_text(
    json.dumps(
        compact,
        ensure_ascii=False,
        indent=2
    ),
    encoding="utf-8"
)


print()
print(
    "======================================"
)
print(
    "PHASE 5D RESULT"
)
print(
    "======================================"
)

print(
    json.dumps(
        compact,
        ensure_ascii=False,
        indent=2
    )
)

print()
print(
    "JSON: "
    "results\\phase5d_summary.json"
)