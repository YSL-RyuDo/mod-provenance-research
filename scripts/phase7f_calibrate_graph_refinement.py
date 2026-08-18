import json
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd


# =========================================================
# Config
# =========================================================

FULL40_SCORE_CSV = Path(
    "results/phase7c2_calibration_full40_parent_scores.csv"
)

OPEN39_SCORE_CSV = Path(
    "results/phase7c_calibration_component_parent_scores.csv"
)

PSEUDO_GT_CSV = Path(
    "results/phase7a_calibration_component_ground_truth.csv"
)

PRIVATE_MANIFEST_CSV = Path(
    "results/phase6l_materialized_private_manifest.csv"
)

STRESS_GRAPH_CSV = Path(
    "results/phase6l_graph_connected_stress_public.csv"
)

NATURAL_GRAPH_CSV = Path(
    "results/phase6l_graph_natural_public.csv"
)

STAGE1_PARAMETERS_JSON = Path(
    "results/phase7d_stage1_parameters.json"
)

CANDIDATE_AUDIT_JSON = Path(
    "results/phase7e_candidate_pool_summary.json"
)


OUTPUT_GRID_CSV = Path(
    "results/phase7f_graph_beta_grid.csv"
)

OUTPUT_QUERY_CSV = Path(
    "results/phase7f_selected_query_predictions.csv"
)

OUTPUT_COMPONENT_CSV = Path(
    "results/phase7f_selected_component_predictions.csv"
)

OUTPUT_EDGE_AUDIT_CSV = Path(
    "results/phase7f_edge_weight_audit.csv"
)

OUTPUT_PARAMETERS_JSON = Path(
    "results/phase7f_graph_parameters.json"
)

OUTPUT_SUMMARY_JSON = Path(
    "results/phase7f_graph_calibration_summary.json"
)


EXPECTED_QUERIES = 180
EXPECTED_COMPONENTS_PER_QUERY = 7
EXPECTED_CODE_COMPONENTS_PER_QUERY = 5

UNKNOWN_LABEL = "UNKNOWN"

MAX_KNOWN_PARENTS = 3

TOP_R_FOR_EDGE_WEIGHT = 3

BETAS = [
    0.0,
    0.1,
    0.2,
    0.3,
    0.4,
    0.5,
    0.6,
    0.7,
    0.8,
    0.9,
    1.0,
]

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


def set_metrics(true_set, pred_set):

    true_set = set(true_set)
    pred_set = set(pred_set)

    intersection = len(
        true_set & pred_set
    )

    precision = safe_divide(
        intersection,
        len(pred_set),
    )

    recall = safe_divide(
        intersection,
        len(true_set),
    )

    if precision + recall == 0:

        f1 = 0.0

    else:

        f1 = (
            2.0
            * precision
            * recall
            / (precision + recall)
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
                true_set == pred_set
            ),
    }


def binary_metrics(truth, prediction):

    truth = np.asarray(
        truth,
        dtype=bool,
    )

    prediction = np.asarray(
        prediction,
        dtype=bool,
    )

    tp = int(
        np.logical_and(
            truth,
            prediction,
        ).sum()
    )

    fp = int(
        np.logical_and(
            ~truth,
            prediction,
        ).sum()
    )

    fn = int(
        np.logical_and(
            truth,
            ~prediction,
        ).sum()
    )

    tn = int(
        np.logical_and(
            ~truth,
            ~prediction,
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
            * precision
            * recall
            / (precision + recall)
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

for path in [
    FULL40_SCORE_CSV,
    OPEN39_SCORE_CSV,
    PSEUDO_GT_CSV,
    PRIVATE_MANIFEST_CSV,
    STRESS_GRAPH_CSV,
    NATURAL_GRAPH_CSV,
    STAGE1_PARAMETERS_JSON,
    CANDIDATE_AUDIT_JSON,
]:

    if not path.exists():

        raise FileNotFoundError(
            f"Missing: {path}"
        )


full40 = pd.read_csv(
    FULL40_SCORE_CSV
)

open39 = pd.read_csv(
    OPEN39_SCORE_CSV
)

pseudo_gt = pd.read_csv(
    PSEUDO_GT_CSV
)

manifest = pd.read_csv(
    PRIVATE_MANIFEST_CSV
)

stress_graph = pd.read_csv(
    STRESS_GRAPH_CSV
)

natural_graph = pd.read_csv(
    NATURAL_GRAPH_CSV
)


stage1_parameters = json.loads(
    STAGE1_PARAMETERS_JSON.read_text(
        encoding="utf-8"
    )
)


candidate_audit = json.loads(
    CANDIDATE_AUDIT_JSON.read_text(
        encoding="utf-8"
    )
)


ALPHA = float(
    stage1_parameters[
        "alpha_absolute_distance"
    ]
)


LAMBDA = float(
    stage1_parameters[
        "parent_proliferation_lambda"
    ]
)


THRESHOLDS = {
    key:
        float(value)

    for key, value
    in stage1_parameters[
        "unknown_thresholds"
    ].items()
}


CANDIDATE_POOL_SIZE = int(
    candidate_audit[
        "selected_candidate_pool_size"
    ]
)


if CANDIDATE_POOL_SIZE != 10:

    raise RuntimeError(
        "Expected frozen candidate pool size M=10, "
        f"got {CANDIDATE_POOL_SIZE}"
    )


print(
    "======================================"
)

print(
    "Phase 7F - Graph Refinement Calibration"
)

print(
    "======================================"
)

print(
    "Frozen alpha :",
    ALPHA
)

print(
    "Frozen lambda:",
    LAMBDA
)

print(
    "Frozen M     :",
    CANDIDATE_POOL_SIZE
)


# =========================================================
# Calibration GT
# =========================================================

cal_manifest = manifest[
    manifest[
        "stage"
    ]
    == "CALIBRATION"
].copy()


if len(cal_manifest) != (
    EXPECTED_QUERIES
    *
    EXPECTED_COMPONENTS_PER_QUERY
):

    raise RuntimeError(
        "Calibration manifest size mismatch"
    )


known_gt = {}


for row in cal_manifest.itertuples(
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

    known_gt[
        key
    ] = clean_text(
        row.source_fresh_id
    )


pseudo_gt_map = {}


for row in pseudo_gt.itertuples(
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

    pseudo_gt_map[
        key
    ] = clean_text(
        row.pseudo_ground_truth_label
    )


# =========================================================
# Graph lookup
# =========================================================

stress_edges_by_query = {}


for query_id, group in stress_graph.groupby(
    "query_id"
):

    edges = []

    for row in group.itertuples(
        index=False
    ):

        edges.append(
            (
                clean_text(
                    row.node_a
                ),
                clean_text(
                    row.node_b
                ),
            )
        )

    stress_edges_by_query[
        str(query_id)
    ] = edges


natural_edge_set = set()


for row in natural_graph.itertuples(
    index=False
):

    a = clean_text(
        row.node_a
    )

    b = clean_text(
        row.node_b
    )

    edge = tuple(
        sorted(
            [
                a,
                b,
            ]
        )
    )

    natural_edge_set.add(
        (
            clean_text(
                row.query_id
            ),
            edge[0],
            edge[1],
        )
    )


# =========================================================
# Score preparation
# =========================================================

def normalized_component_cost(
    modality,
    distance,
    regret,
):

    threshold = THRESHOLDS[
        modality
    ]


    if threshold > 0:

        normalized_distance = min(
            float(distance)
            /
            threshold,
            1.0,
        )

        eligible = bool(
            float(distance)
            <= (
                threshold
                +
                EPSILON
            )
        )


    else:

        eligible = bool(
            abs(
                float(distance)
            )
            <= EPSILON
        )

        normalized_distance = (
            0.0
            if eligible
            else 1.0
        )


    normalized_regret = min(
        max(
            float(regret),
            0.0,
        ),
        1.0,
    )


    cost = (
        ALPHA
        *
        normalized_distance
        +
        (
            1.0
            -
            ALPHA
        )
        *
        normalized_regret
    )


    return (
        float(cost),
        eligible,
    )


def prepare_query(
    score_df,
    query_id,
    gt_map,
):

    group = score_df[
        score_df[
            "query_id"
        ].astype(str)
        == query_id
    ].copy()


    node_ids = sorted(
        group[
            "node_id"
        ].astype(str).unique()
    )


    if len(node_ids) != 7:

        raise RuntimeError(
            f"{query_id}: expected 7 nodes"
        )


    modalities = {}


    all_candidates = sorted(
        group[
            "candidate_parent"
        ].astype(str).unique()
    )


    # -----------------------------------------------------
    # Build base cost for all candidate parents.
    # -----------------------------------------------------

    base_costs = {}

    eligible_map = {}


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
                f"{query_id}/{node_id}: "
                "mixed modalities"
            )


        modality = next(
            iter(
                modality_values
            )
        )


        modalities[
            node_id
        ] = modality


        base_costs[
            node_id
        ] = {}


        eligible_map[
            node_id
        ] = {}


        for row in node_group.itertuples(
            index=False
        ):

            parent = clean_text(
                row.candidate_parent
            )


            cost, eligible = (
                normalized_component_cost(
                    modality,
                    float(
                        row.fused_parent_distance
                    ),
                    float(
                        row.mean_regret
                    ),
                )
            )


            base_costs[
                node_id
            ][
                parent
            ] = cost


            eligible_map[
                node_id
            ][
                parent
            ] = eligible


    # -----------------------------------------------------
    # Query-level retrieval score:
    # mean of best three component costs.
    # Same frozen policy as Phase 7E.
    # -----------------------------------------------------

    retrieval_scores = {}


    for parent in all_candidates:

        costs = sorted(
            base_costs[
                node_id
            ][
                parent
            ]

            for node_id
            in node_ids
        )


        retrieval_scores[
            parent
        ] = float(
            np.mean(
                costs[
                    :3
                ]
            )
        )


    ranked_candidates = sorted(
        all_candidates,
        key=lambda parent: (
            retrieval_scores[
                parent
            ],
            parent,
        ),
    )


    candidate_pool = (
        ranked_candidates[
            :CANDIDATE_POOL_SIZE
        ]
    )


    code_nodes = [
        node_id

        for node_id
        in node_ids

        if modalities[
            node_id
        ]
        == "CODE_BINARY"
    ]


    if len(
        code_nodes
    ) != EXPECTED_CODE_COMPONENTS_PER_QUERY:

        raise RuntimeError(
            f"{query_id}: expected 5 CODE nodes, "
            f"got {len(code_nodes)}"
        )


    ground_truth = {
        node_id:
            gt_map[
                (
                    query_id,
                    node_id,
                )
            ]

        for node_id
        in node_ids
    }


    return {
        "query_id":
            query_id,

        "node_ids":
            node_ids,

        "code_nodes":
            code_nodes,

        "modalities":
            modalities,

        "candidate_pool":
            candidate_pool,

        "base_costs":
            base_costs,

        "eligible":
            eligible_map,

        "ground_truth":
            ground_truth,
    }


# =========================================================
# Prepare both calibration views
# =========================================================

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


known_queries = []

pseudo_queries = []


for index, query_id in enumerate(
    calibration_query_ids,
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


    known_queries.append(
        prepare_query(
            full40,
            query_id,
            known_gt,
        )
    )


    pseudo_queries.append(
        prepare_query(
            open39,
            query_id,
            pseudo_gt_map,
        )
    )


# =========================================================
# Boundary-aware edge weights
#
# For each CODE node:
# rank its top-R candidate parents according to
# content cost inside the frozen Top-10 pool.
#
# Edge weight:
# Jaccard(top-R(u), top-R(v))
#
# No ground truth and no synthetic-edge flag are used.
# =========================================================

def top_parent_set(
    query,
    node_id,
):

    pool = query[
        "candidate_pool"
    ]


    ranked = sorted(
        pool,
        key=lambda parent: (
            query[
                "base_costs"
            ][
                node_id
            ][
                parent
            ],
            parent,
        ),
    )


    return set(
        ranked[
            :TOP_R_FOR_EDGE_WEIGHT
        ]
    )


def build_edge_weights(
    query,
):

    query_id = query[
        "query_id"
    ]


    code_node_set = set(
        query[
            "code_nodes"
        ]
    )


    top_sets = {
        node_id:
            top_parent_set(
                query,
                node_id,
            )

        for node_id
        in query[
            "code_nodes"
        ]
    }


    edge_weights = []


    for node_a, node_b in (
        stress_edges_by_query.get(
            query_id,
            []
        )
    ):

        if (
            node_a
            not in code_node_set
            or
            node_b
            not in code_node_set
        ):

            continue


        first = (
            top_sets[
                node_a
            ]
        )

        second = (
            top_sets[
                node_b
            ]
        )


        union = (
            first
            |
            second
        )


        if not union:

            weight = 0.0

        else:

            weight = (
                len(
                    first
                    &
                    second
                )
                /
                len(
                    union
                )
            )


        edge_key = tuple(
            sorted(
                [
                    node_a,
                    node_b,
                ]
            )
        )


        is_natural = (
            (
                query_id,
                edge_key[0],
                edge_key[1],
            )
            in natural_edge_set
        )


        edge_weights.append({
            "node_a":
                node_a,

            "node_b":
                node_b,

            "weight":
                float(
                    weight
                ),

            # Private calibration diagnostic only.
            "is_natural_edge":
                bool(
                    is_natural
                ),
        })


    return edge_weights


# =========================================================
# Refine code unary costs
# =========================================================

def refined_costs(
    query,
    beta,
):

    refined = {
        node_id: {
            parent:
                float(
                    query[
                        "base_costs"
                    ][
                        node_id
                    ][
                        parent
                    ]
                )

            for parent
            in query[
                "candidate_pool"
            ]
        }

        for node_id
        in query[
            "node_ids"
        ]
    }


    if beta <= 0:

        return (
            refined,
            build_edge_weights(
                query
            ),
        )


    edges = build_edge_weights(
        query
    )


    adjacency = {
        node_id: []

        for node_id
        in query[
            "code_nodes"
        ]
    }


    for edge in edges:

        node_a = edge[
            "node_a"
        ]

        node_b = edge[
            "node_b"
        ]

        weight = float(
            edge[
                "weight"
            ]
        )


        if weight <= 0:
            continue


        adjacency[
            node_a
        ].append(
            (
                node_b,
                weight,
            )
        )


        adjacency[
            node_b
        ].append(
            (
                node_a,
                weight,
            )
        )


    for node_id in query[
        "code_nodes"
    ]:

        neighbors = adjacency[
            node_id
        ]


        weight_sum = sum(
            weight
            for _, weight
            in neighbors
        )


        if weight_sum <= 0:
            continue


        for parent in query[
            "candidate_pool"
        ]:

            neighbor_cost = (
                sum(
                    weight
                    *
                    query[
                        "base_costs"
                    ][
                        neighbor
                    ][
                        parent
                    ]

                    for neighbor, weight
                    in neighbors
                )
                /
                weight_sum
            )


            own_cost = (
                query[
                    "base_costs"
                ][
                    node_id
                ][
                    parent
                ]
            )


            refined[
                node_id
            ][
                parent
            ] = float(
                (
                    1.0
                    -
                    beta
                )
                *
                own_cost
                +
                beta
                *
                neighbor_cost
            )


    return (
        refined,
        edges,
    )


# =========================================================
# Parent subset optimization
#
# Eligibility is NEVER changed by graph refinement.
# =========================================================

def solve_query(
    query,
    beta,
):

    refined, edges = (
        refined_costs(
            query,
            beta,
        )
    )


    pool = query[
        "candidate_pool"
    ]


    node_ids = query[
        "node_ids"
    ]


    best_solution = None
    best_key = None


    for subset_size in range(
        0,
        MAX_KNOWN_PARENTS + 1,
    ):

        for subset in combinations(
            pool,
            subset_size,
        ):

            assignments = []

            assignment_cost_sum = 0.0


            for node_id in node_ids:

                eligible_parents = [
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


                if not eligible_parents:

                    assignments.append(
                        UNKNOWN_LABEL
                    )

                    assignment_cost_sum += 1.0

                    continue


                best_parent = min(
                    eligible_parents,
                    key=lambda parent: (
                        refined[
                            node_id
                        ][
                            parent
                        ],
                        parent,
                    ),
                )


                best_parent_cost = float(
                    refined[
                        node_id
                    ][
                        best_parent
                    ]
                )


                # UNKNOWN remains an available alternative
                # with unit cost.
                if (
                    best_parent_cost
                    >
                    1.0
                ):

                    assignments.append(
                        UNKNOWN_LABEL
                    )

                    assignment_cost_sum += 1.0

                else:

                    assignments.append(
                        best_parent
                    )

                    assignment_cost_sum += (
                        best_parent_cost
                    )


            objective = (
                assignment_cost_sum
                +
                LAMBDA
                *
                subset_size
            )


            key = (
                objective,
                subset_size,
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

                    "objective":
                        float(
                            objective
                        ),

                    "edges":
                        edges,
                }


    if best_solution is None:

        raise RuntimeError(
            f"{query['query_id']}: "
            "no graph solution"
        )


    return best_solution


# =========================================================
# Evaluate view
# =========================================================

def evaluate_view(
    queries,
    beta,
    pseudo_open,
    collect=False,
):

    component_total = 0
    component_correct = 0

    parent_f1_values = []
    parent_exact = 0

    k_correct = 0
    k_errors = []


    unknown_truth = []
    unknown_pred = []


    query_rows = []
    component_rows = []
    edge_rows = []


    for query in queries:

        solution = solve_query(
            query,
            beta,
        )


        truth_labels = [
            query[
                "ground_truth"
            ][
                node_id
            ]

            for node_id
            in query[
                "node_ids"
            ]
        ]


        predictions = (
            solution[
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

            component_total += 1


            if truth == prediction:

                component_correct += 1


            if pseudo_open:

                unknown_truth.append(
                    truth
                    == UNKNOWN_LABEL
                )

                unknown_pred.append(
                    prediction
                    == UNKNOWN_LABEL
                )


            if collect:

                component_rows.append({
                    "view":
                        (
                            "PSEUDO_UNKNOWN_39"
                            if pseudo_open
                            else
                            "KNOWN_ONLY_40"
                        ),

                    "query_id":
                        query[
                            "query_id"
                        ],

                    "node_id":
                        node_id,

                    "modality":
                        query[
                            "modalities"
                        ][
                            node_id
                        ],

                    "ground_truth":
                        truth,

                    "prediction":
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


        parent_f1_values.append(
            metrics[
                "f1"
            ]
        )


        if metrics[
            "exact"
        ]:

            parent_exact += 1


        k_true = len(
            true_set
        )

        k_pred = len(
            pred_set
        )


        if k_true == k_pred:

            k_correct += 1


        k_errors.append(
            abs(
                k_true
                -
                k_pred
            )
        )


        if collect:

            query_rows.append({
                "view":
                    (
                        "PSEUDO_UNKNOWN_39"
                        if pseudo_open
                        else
                        "KNOWN_ONLY_40"
                    ),

                "query_id":
                    query[
                        "query_id"
                    ],

                "beta":
                    float(
                        beta
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

                "k_true":
                    int(
                        k_true
                    ),

                "k_pred":
                    int(
                        k_pred
                    ),

                "selected_known_subset":
                    json.dumps(
                        list(
                            solution[
                                "subset"
                            ]
                        )
                    ),

                "parent_set_f1":
                    float(
                        metrics[
                            "f1"
                        ]
                    ),

                "parent_set_exact":
                    bool(
                        metrics[
                            "exact"
                        ]
                    ),

                "objective":
                    float(
                        solution[
                            "objective"
                        ]
                    ),
            })


            # Private audit only.
            code_gt = {
                node_id:
                    query[
                        "ground_truth"
                    ][
                        node_id
                    ]

                for node_id
                in query[
                    "code_nodes"
                ]
            }


            for edge in solution[
                "edges"
            ]:

                node_a = edge[
                    "node_a"
                ]

                node_b = edge[
                    "node_b"
                ]


                edge_rows.append({
                    "view":
                        (
                            "PSEUDO_UNKNOWN_39"
                            if pseudo_open
                            else
                            "KNOWN_ONLY_40"
                        ),

                    "query_id":
                        query[
                            "query_id"
                        ],

                    "node_a":
                        node_a,

                    "node_b":
                        node_b,

                    "edge_weight":
                        float(
                            edge[
                                "weight"
                            ]
                        ),

                    "same_ground_truth_parent":
                        bool(
                            code_gt[
                                node_a
                            ]
                            ==
                            code_gt[
                                node_b
                            ]
                        ),

                    "is_natural_edge_private_audit":
                        bool(
                            edge[
                                "is_natural_edge"
                            ]
                        ),
                })


    query_count = len(
        queries
    )


    result = {
        "component_accuracy":
            safe_divide(
                component_correct,
                component_total,
            ),

        "parent_set_f1":
            float(
                np.mean(
                    parent_f1_values
                )
            ),

        "parent_set_exact":
            safe_divide(
                parent_exact,
                query_count,
            ),

        "k_accuracy":
            safe_divide(
                k_correct,
                query_count,
            ),

        "k_mae":
            float(
                np.mean(
                    k_errors
                )
            ),
    }


    if pseudo_open:

        metrics = binary_metrics(
            unknown_truth,
            unknown_pred,
        )


        result[
            "unknown_precision"
        ] = float(
            metrics[
                "precision"
            ]
        )


        result[
            "unknown_recall"
        ] = float(
            metrics[
                "recall"
            ]
        )


        result[
            "unknown_f1"
        ] = float(
            metrics[
                "f1"
            ]
        )


    return (
        result,
        query_rows,
        component_rows,
        edge_rows,
    )


# =========================================================
# Beta grid
#
# Primary selection:
# mean parent-set F1 across both calibration views.
#
# Ties:
# mean component accuracy
# mean K accuracy
# pseudo UNKNOWN F1
# smaller beta (less graph intervention)
# =========================================================

grid_rows = []

best_row = None
best_key = None


for beta in BETAS:

    print()

    print(
        "beta =",
        beta
    )


    known_metrics, _, _, _ = (
        evaluate_view(
            known_queries,
            beta,
            pseudo_open=False,
            collect=False,
        )
    )


    pseudo_metrics, _, _, _ = (
        evaluate_view(
            pseudo_queries,
            beta,
            pseudo_open=True,
            collect=False,
        )
    )


    mean_parent_f1 = (
        known_metrics[
            "parent_set_f1"
        ]
        +
        pseudo_metrics[
            "parent_set_f1"
        ]
    ) / 2.0


    mean_component_accuracy = (
        known_metrics[
            "component_accuracy"
        ]
        +
        pseudo_metrics[
            "component_accuracy"
        ]
    ) / 2.0


    mean_k_accuracy = (
        known_metrics[
            "k_accuracy"
        ]
        +
        pseudo_metrics[
            "k_accuracy"
        ]
    ) / 2.0


    row = {
        "beta":
            float(
                beta
            ),

        "mean_parent_set_f1":
            float(
                mean_parent_f1
            ),

        "mean_component_accuracy":
            float(
                mean_component_accuracy
            ),

        "mean_k_accuracy":
            float(
                mean_k_accuracy
            ),

        "known_component_accuracy":
            float(
                known_metrics[
                    "component_accuracy"
                ]
            ),

        "known_parent_set_f1":
            float(
                known_metrics[
                    "parent_set_f1"
                ]
            ),

        "known_parent_set_exact":
            float(
                known_metrics[
                    "parent_set_exact"
                ]
            ),

        "known_k_accuracy":
            float(
                known_metrics[
                    "k_accuracy"
                ]
            ),

        "known_k_mae":
            float(
                known_metrics[
                    "k_mae"
                ]
            ),

        "pseudo_component_accuracy":
            float(
                pseudo_metrics[
                    "component_accuracy"
                ]
            ),

        "pseudo_parent_set_f1":
            float(
                pseudo_metrics[
                    "parent_set_f1"
                ]
            ),

        "pseudo_parent_set_exact":
            float(
                pseudo_metrics[
                    "parent_set_exact"
                ]
            ),

        "pseudo_k_accuracy":
            float(
                pseudo_metrics[
                    "k_accuracy"
                ]
            ),

        "pseudo_k_mae":
            float(
                pseudo_metrics[
                    "k_mae"
                ]
            ),

        "pseudo_unknown_precision":
            float(
                pseudo_metrics[
                    "unknown_precision"
                ]
            ),

        "pseudo_unknown_recall":
            float(
                pseudo_metrics[
                    "unknown_recall"
                ]
            ),

        "pseudo_unknown_f1":
            float(
                pseudo_metrics[
                    "unknown_f1"
                ]
            ),
    }


    grid_rows.append(
        row
    )


    selection_key = (
        row[
            "mean_parent_set_f1"
        ],

        row[
            "mean_component_accuracy"
        ],

        row[
            "mean_k_accuracy"
        ],

        row[
            "pseudo_unknown_f1"
        ],

        -row[
            "beta"
        ],
    )


    if (
        best_key is None
        or
        selection_key
        >
        best_key
    ):

        best_key = (
            selection_key
        )

        best_row = (
            row
        )


grid_df = pd.DataFrame(
    grid_rows
)


if best_row is None:

    raise RuntimeError(
        "No beta selected"
    )


selected_beta = float(
    best_row[
        "beta"
    ]
)


print()

print(
    "Selected beta:",
    selected_beta
)


# =========================================================
# Selected predictions + edge diagnostics
# =========================================================

(
    selected_known_metrics,
    known_query_rows,
    known_component_rows,
    known_edge_rows,
) = evaluate_view(
    known_queries,
    selected_beta,
    pseudo_open=False,
    collect=True,
)


(
    selected_pseudo_metrics,
    pseudo_query_rows,
    pseudo_component_rows,
    pseudo_edge_rows,
) = evaluate_view(
    pseudo_queries,
    selected_beta,
    pseudo_open=True,
    collect=True,
)


query_df = pd.DataFrame(
    known_query_rows
    +
    pseudo_query_rows
)


component_df = pd.DataFrame(
    known_component_rows
    +
    pseudo_component_rows
)


edge_df = pd.DataFrame(
    known_edge_rows
    +
    pseudo_edge_rows
)


# =========================================================
# Edge-weight diagnostic
# =========================================================

edge_weight_summary = {}


if len(
    edge_df
):

    for same_parent_value, group in (
        edge_df.groupby(
            "same_ground_truth_parent"
        )
    ):

        key = (
            "SAME_PARENT"
            if bool(
                same_parent_value
            )
            else
            "CROSS_PARENT"
        )


        edge_weight_summary[
            key
        ] = {
            "edges":
                int(
                    len(
                        group
                    )
                ),

            "mean_weight":
                float(
                    group[
                        "edge_weight"
                    ].mean()
                ),

            "median_weight":
                float(
                    group[
                        "edge_weight"
                    ].median()
                ),
        }


# =========================================================
# Save
# =========================================================

OUTPUT_GRID_CSV.parent.mkdir(
    parents=True,
    exist_ok=True,
)


grid_df.to_csv(
    OUTPUT_GRID_CSV,
    index=False,
    encoding="utf-8-sig",
)


query_df.to_csv(
    OUTPUT_QUERY_CSV,
    index=False,
    encoding="utf-8-sig",
)


component_df.to_csv(
    OUTPUT_COMPONENT_CSV,
    index=False,
    encoding="utf-8-sig",
)


edge_df.to_csv(
    OUTPUT_EDGE_AUDIT_CSV,
    index=False,
    encoding="utf-8-sig",
)


graph_parameters = {
    "graph_parameters_frozen":
        True,

    "calibration_only":
        True,

    "test_used":
        False,

    "primary_graph_track":
        "CONNECTED_STRESS",

    "candidate_pool_size":
        CANDIDATE_POOL_SIZE,

    "top_r_for_boundary_weight":
        TOP_R_FOR_EDGE_WEIGHT,

    "edge_weight":
        (
            "Jaccard overlap between each edge "
            "endpoint's top-3 content candidate sets"
        ),

    "graph_refinement":
        (
            "(1-beta) * own content unary cost "
            "+ beta * edge-weighted neighboring "
            "content unary cost"
        ),

    "eligibility_policy":
        (
            "Graph refinement does not change "
            "Phase 7D absolute-distance eligibility; "
            "an ineligible candidate cannot become "
            "eligible through graph propagation."
        ),

    "selected_beta":
        selected_beta,

    "alpha":
        ALPHA,

    "lambda":
        LAMBDA,

    "maximum_known_parents":
        MAX_KNOWN_PARENTS,
}


OUTPUT_PARAMETERS_JSON.write_text(
    json.dumps(
        graph_parameters,
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)


summary = {
    "graph_refinement_calibration_complete":
        True,

    "performance_scope":
        "CALIBRATION_ONLY",

    "test_queries_scored":
        0,

    "unknown_heldout_queries_scored":
        0,

    "candidate_pool_size":
        CANDIDATE_POOL_SIZE,

    "top_r_for_edge_weight":
        TOP_R_FOR_EDGE_WEIGHT,

    "beta_grid":
        BETAS,

    "selected_beta":
        selected_beta,

    "beta_selected_at_zero":
        bool(
            abs(
                selected_beta
            )
            <= EPSILON
        ),

    "beta_selected_at_grid_maximum":
        bool(
            abs(
                selected_beta
                -
                max(
                    BETAS
                )
            )
            <= EPSILON
        ),

    "selection_priority": [
        "mean parent-set F1 across KNOWN_ONLY_40 and PSEUDO_UNKNOWN_39",
        "mean component accuracy",
        "mean K accuracy",
        "pseudo-UNKNOWN F1",
        "smaller beta under remaining ties",
    ],

    "stage1_reference_from_phase7d": {
        "known_component_accuracy":
            0.7388888888888889,

        "known_parent_set_f1":
            0.7574338624338626,

        "known_k_accuracy":
            0.34444444444444444,

        "pseudo_component_accuracy":
            0.834920634920635,

        "pseudo_parent_set_f1":
            0.8762962962962964,

        "pseudo_k_accuracy":
            0.6,

        "pseudo_unknown_f1":
            0.8783868935097668,
    },

    "selected_known_metrics":
        {
            key:
                float(value)

            for key, value
            in selected_known_metrics.items()
        },

    "selected_pseudo_metrics":
        {
            key:
                float(value)

            for key, value
            in selected_pseudo_metrics.items()
        },

    "selected_grid_metrics":
        {
            key:
                float(value)

            for key, value
            in best_row.items()
        },

    "private_edge_weight_diagnostic":
        edge_weight_summary,

    "edge_origin_used_by_method":
        False,

    "ground_truth_used_to_compute_edge_weight":
        False,

    "graph_changes_candidate_eligibility":
        False,

    "test_data_used_for_selection":
        False,

    "goals_met":
        bool(
            len(
                grid_df
            )
            == len(
                BETAS
            )

            and

            len(
                query_df
            )
            == (
                EXPECTED_QUERIES
                *
                2
            )

            and

            len(
                component_df
            )
            == (
                EXPECTED_QUERIES
                *
                EXPECTED_COMPONENTS_PER_QUERY
                *
                2
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


print()

print(
    "======================================"
)

print(
    "PHASE 7F RESULT"
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
    "Beta grid:",
    OUTPUT_GRID_CSV
)

print(
    "Query predictions:",
    OUTPUT_QUERY_CSV
)

print(
    "Component predictions:",
    OUTPUT_COMPONENT_CSV
)

print(
    "Edge audit:",
    OUTPUT_EDGE_AUDIT_CSV
)

print(
    "Frozen graph parameters:",
    OUTPUT_PARAMETERS_JSON
)

print(
    "Summary:",
    OUTPUT_SUMMARY_JSON
)