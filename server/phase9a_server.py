import json
import math
import os
import time
from itertools import combinations
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import psutil

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


# =========================================================
# Paths
# =========================================================

ROOT = Path(__file__).resolve().parent.parent


FINAL_PARAMETERS_JSON = (
    ROOT
    / "results"
    / "phase7g_final_method_parameters.json"
)

PHASE7H_SCORE_CSV = (
    ROOT
    / "results"
    / "phase7h_test_component_parent_scores.csv"
)

STRESS_GRAPH_CSV = (
    ROOT
    / "results"
    / "phase6l_graph_connected_stress_public.csv"
)


# =========================================================
# Constants
# =========================================================

UNKNOWN_LABEL = "UNKNOWN"

EPSILON = 1e-12

EXPECTED_COMPONENTS = 7

EXPECTED_CODE = 5
EXPECTED_STRUCTURED = 1
EXPECTED_IMAGE = 1


# =========================================================
# Load frozen parameters
# =========================================================

if not FINAL_PARAMETERS_JSON.exists():

    raise FileNotFoundError(
        FINAL_PARAMETERS_JSON
    )


PARAMETERS = json.loads(
    FINAL_PARAMETERS_JSON.read_text(
        encoding="utf-8"
    )
)


STAGE1 = PARAMETERS[
    "stage1"
]

STAGE2 = PARAMETERS[
    "stage2"
]


THRESHOLDS = {
    key:
        float(value)

    for key, value
    in STAGE1[
        "unknown_thresholds"
    ].items()
}


ALPHA = float(
    STAGE1[
        "alpha_absolute_distance"
    ]
)


REGRET_WEIGHT = float(
    STAGE1[
        "alpha_mean_regret"
    ]
)


LAMBDA = float(
    STAGE1[
        "parent_proliferation_lambda"
    ]
)


CANDIDATE_POOL_SIZE = int(
    STAGE1[
        "candidate_pool_size"
    ]
)


MAX_KNOWN_PARENTS = int(
    PARAMETERS[
        "query_definition"
    ][
        "maximum_known_parents"
    ]
)


GRAPH_BETA = float(
    STAGE2[
        "graph_beta"
    ]
)


BOUNDARY_TOP_R = int(
    STAGE2[
        "boundary_candidate_top_r"
    ]
)


# =========================================================
# Frozen-value guard
# =========================================================

if not math.isclose(
    ALPHA,
    0.75,
    abs_tol=EPSILON,
):

    raise RuntimeError(
        "Frozen alpha mismatch"
    )


if not math.isclose(
    REGRET_WEIGHT,
    0.25,
    abs_tol=EPSILON,
):

    raise RuntimeError(
        "Frozen MEAN_REGRET weight mismatch"
    )


if not math.isclose(
    LAMBDA,
    0.5,
    abs_tol=EPSILON,
):

    raise RuntimeError(
        "Frozen lambda mismatch"
    )


if CANDIDATE_POOL_SIZE != 10:

    raise RuntimeError(
        "Frozen candidate pool M mismatch"
    )


if MAX_KNOWN_PARENTS != 3:

    raise RuntimeError(
        "Frozen Kmax mismatch"
    )


if not math.isclose(
    GRAPH_BETA,
    0.1,
    abs_tol=EPSILON,
):

    raise RuntimeError(
        "Frozen graph beta mismatch"
    )


if BOUNDARY_TOP_R != 3:

    raise RuntimeError(
        "Frozen boundary Top-R mismatch"
    )


# =========================================================
# Request schemas
# =========================================================

class ParentScore(BaseModel):

    parent_id: str

    fused_parent_distance: float

    mean_regret: float


class ComponentInput(BaseModel):

    node_id: str

    modality: str

    parent_scores: List[
        ParentScore
    ]


class GraphEdgeInput(BaseModel):

    node_a: str

    node_b: str


class AnalyzeRequest(BaseModel):

    query_id: str

    components: List[
        ComponentInput
    ]

    edges: List[
        GraphEdgeInput
    ]


# =========================================================
# Internal helpers
# =========================================================

def normalized_component_cost(
    modality,
    distance,
    regret,
):

    if modality not in THRESHOLDS:

        raise ValueError(
            f"Unsupported modality: "
            f"{modality}"
        )


    threshold = THRESHOLDS[
        modality
    ]


    distance = float(
        distance
    )

    regret = float(
        regret
    )


    if threshold > 0:

        eligible = bool(
            distance
            <= (
                threshold
                +
                EPSILON
            )
        )


        normalized_distance = min(
            distance
            /
            threshold,
            1.0,
        )


    else:

        eligible = bool(
            abs(
                distance
            )
            <= EPSILON
        )


        normalized_distance = (
            0.0
            if eligible
            else
            1.0
        )


    normalized_regret = min(
        max(
            regret,
            0.0,
        ),
        1.0,
    )


    cost = (
        ALPHA
        *
        normalized_distance
        +
        REGRET_WEIGHT
        *
        normalized_regret
    )


    return (
        float(cost),
        eligible,
    )


# =========================================================
# Prepare request
# =========================================================

def prepare_request(
    request: AnalyzeRequest,
):

    if len(
        request.components
    ) != EXPECTED_COMPONENTS:

        raise ValueError(
            "Exactly 7 components are required"
        )


    modalities = [
        component.modality

        for component
        in request.components
    ]


    modality_counts = {
        modality:
            modalities.count(
                modality
            )

        for modality
        in set(
            modalities
        )
    }


    expected = {
        "CODE_BINARY":
            EXPECTED_CODE,

        "STRUCTURED":
            EXPECTED_STRUCTURED,

        "IMAGE":
            EXPECTED_IMAGE,
    }


    if modality_counts != expected:

        raise ValueError(
            "Expected modality composition "
            f"{expected}, got "
            f"{modality_counts}"
        )


    node_ids = [
        component.node_id

        for component
        in request.components
    ]


    if len(
        set(
            node_ids
        )
    ) != EXPECTED_COMPONENTS:

        raise ValueError(
            "Duplicate node_id detected"
        )


    # -----------------------------------------------------
    # Candidate universe
    # -----------------------------------------------------

    candidate_sets = []


    for component in (
        request.components
    ):

        candidate_sets.append(
            {
                score.parent_id

                for score
                in component.parent_scores
            }
        )


    candidate_universe = set.intersection(
        *candidate_sets
    )


    if not candidate_universe:

        raise ValueError(
            "No common candidate parents "
            "across components"
        )


    # -----------------------------------------------------
    # Base costs
    # -----------------------------------------------------

    base_costs = {}

    eligible = {}

    modalities_by_node = {}


    for component in (
        request.components
    ):

        node_id = (
            component.node_id
        )

        modality = (
            component.modality
        )


        modalities_by_node[
            node_id
        ] = modality


        base_costs[
            node_id
        ] = {}


        eligible[
            node_id
        ] = {}


        score_map = {
            score.parent_id:
                score

            for score
            in component.parent_scores
        }


        for parent in (
            candidate_universe
        ):

            score = score_map[
                parent
            ]


            cost, is_eligible = (
                normalized_component_cost(
                    modality,
                    score.fused_parent_distance,
                    score.mean_regret,
                )
            )


            base_costs[
                node_id
            ][
                parent
            ] = cost


            eligible[
                node_id
            ][
                parent
            ] = is_eligible


    # -----------------------------------------------------
    # Frozen Top-10 retrieval
    #
    # Same Phase 7E/7H rule:
    # mean of three lowest component costs.
    # -----------------------------------------------------

    retrieval_scores = {}


    for parent in (
        candidate_universe
    ):

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
        candidate_universe,
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

        if modalities_by_node[
            node_id
        ]
        == "CODE_BINARY"
    ]


    return {
        "query_id":
            request.query_id,

        "node_ids":
            node_ids,

        "code_nodes":
            code_nodes,

        "modalities":
            modalities_by_node,

        "candidate_pool":
            list(
                candidate_pool
            ),

        "retrieval_scores":
            retrieval_scores,

        "base_costs":
            base_costs,

        "eligible":
            eligible,

        "edges":
            [
                (
                    edge.node_a,
                    edge.node_b,
                )

                for edge
                in request.edges
            ],
    }


# =========================================================
# Boundary signal
# =========================================================

def top_parent_set(
    query,
    node_id,
):

    ranked = sorted(
        query[
            "candidate_pool"
        ],
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
            :BOUNDARY_TOP_R
        ]
    )


def build_edge_weights(
    query,
):

    code_nodes = set(
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


    edge_results = []


    for node_a, node_b in (
        query[
            "edges"
        ]
    ):

        if (
            node_a not in code_nodes
            or
            node_b not in code_nodes
        ):

            continue


        first = top_sets[
            node_a
        ]

        second = top_sets[
            node_b
        ]


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


        edge_results.append({
            "node_a":
                node_a,

            "node_b":
                node_b,

            "weight":
                float(
                    weight
                ),
        })


    return edge_results


# =========================================================
# Graph refinement
# =========================================================

def refined_costs(
    query,
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

        weight = float(
            edge[
                "weight"
            ]
        )


        if weight <= 0:

            continue


        node_a = edge[
            "node_a"
        ]

        node_b = edge[
            "node_b"
        ]


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


    for node_id in (
        query[
            "code_nodes"
        ]
    ):

        neighbors = adjacency[
            node_id
        ]


        total_weight = sum(
            weight

            for _, weight
            in neighbors
        )


        if total_weight <= 0:

            continue


        for parent in (
            query[
                "candidate_pool"
            ]
        ):

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
                total_weight
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
                    GRAPH_BETA
                )
                *
                own_cost

                +

                GRAPH_BETA
                *
                neighbor_cost
            )


    return (
        refined,
        edges,
    )


# =========================================================
# Frozen parent-set solver
# =========================================================

def solve_query(
    query,
):

    refined, edges = (
        refined_costs(
            query
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


    combinations_evaluated = 0


    for subset_size in range(
        MAX_KNOWN_PARENTS + 1
    ):

        for subset in combinations(
            pool,
            subset_size,
        ):

            combinations_evaluated += 1


            assignments = []

            assignment_cost = 0.0


            for node_id in node_ids:

                valid_parents = [
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


                if not valid_parents:

                    assignments.append(
                        UNKNOWN_LABEL
                    )

                    assignment_cost += 1.0

                    continue


                best_parent = min(
                    valid_parents,
                    key=lambda parent: (
                        refined[
                            node_id
                        ][
                            parent
                        ],
                        parent,
                    ),
                )


                best_cost = float(
                    refined[
                        node_id
                    ][
                        best_parent
                    ]
                )


                if best_cost > 1.0:

                    assignments.append(
                        UNKNOWN_LABEL
                    )

                    assignment_cost += 1.0

                else:

                    assignments.append(
                        best_parent
                    )

                    assignment_cost += (
                        best_cost
                    )


            objective = (
                assignment_cost
                +
                LAMBDA
                *
                subset_size
            )


            key = (
                float(
                    objective
                ),
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
                }


    if best_solution is None:

        raise RuntimeError(
            "No provenance solution"
        )


    best_solution[
        "combinations_evaluated"
    ] = combinations_evaluated


    best_solution[
        "edges"
    ] = edges


    return best_solution


# =========================================================
# Service analysis function
# =========================================================

def analyze_internal(
    request: AnalyzeRequest,
):

    process = psutil.Process(
        os.getpid()
    )


    memory_before = (
        process
        .memory_info()
        .rss
    )


    t0 = time.perf_counter_ns()


    query = prepare_request(
        request
    )


    t1 = time.perf_counter_ns()


    solution = solve_query(
        query
    )


    t2 = time.perf_counter_ns()


    memory_after = (
        process
        .memory_info()
        .rss
    )


    component_results = []


    for (
        node_id,
        prediction
    ) in zip(
        query[
            "node_ids"
        ],
        solution[
            "assignments"
        ],
    ):

        component_results.append({
            "node_id":
                node_id,

            "modality":
                query[
                    "modalities"
                ][
                    node_id
                ],

            "predicted_parent":
                prediction,
        })


    predicted_parent_set = sorted(
        set(
            solution[
                "assignments"
            ]
        )
    )


    known_parent_set = sorted(
        parent

        for parent
        in predicted_parent_set

        if parent
        != UNKNOWN_LABEL
    )


    result = {
        "query_id":
            request.query_id,

        "predicted_parent_set":
            predicted_parent_set,

        "predicted_known_parent_set":
            known_parent_set,

        "predicted_k":
            int(
                len(
                    predicted_parent_set
                )
            ),

        "predicted_known_k":
            int(
                len(
                    known_parent_set
                )
            ),

        "unknown_present":
            bool(
                UNKNOWN_LABEL
                in predicted_parent_set
            ),

        "selected_known_subset":
            list(
                solution[
                    "subset"
                ]
            ),

        "candidate_pool_top10":
            query[
                "candidate_pool"
            ],

        "components":
            component_results,

        "graph_edges":
            solution[
                "edges"
            ],

        "objective":
            float(
                solution[
                    "objective"
                ]
            ),

        "combinations_evaluated":
            int(
                solution[
                    "combinations_evaluated"
                ]
            ),

        "latency_ms": {
            "request_preparation":
                (
                    t1 - t0
                )
                / 1_000_000.0,

            "reconstruction":
                (
                    t2 - t1
                )
                / 1_000_000.0,

            "total":
                (
                    t2 - t0
                )
                / 1_000_000.0,
        },

        "process_memory": {
            "rss_before_bytes":
                int(
                    memory_before
                ),

            "rss_after_bytes":
                int(
                    memory_after
                ),

            "rss_delta_bytes":
                int(
                    memory_after
                    -
                    memory_before
                ),
        },

        "frozen_method": {
            "alpha":
                ALPHA,

            "regret_weight":
                REGRET_WEIGHT,

            "lambda":
                LAMBDA,

            "candidate_pool_M":
                CANDIDATE_POOL_SIZE,

            "graph_beta":
                GRAPH_BETA,

            "boundary_top_r":
                BOUNDARY_TOP_R,

            "maximum_known_parents":
                MAX_KNOWN_PARENTS,
        },
    }


    return result


# =========================================================
# FastAPI
# =========================================================

app = FastAPI(
    title=(
        "Game MOD Multi-Parent "
        "Provenance Server"
    ),

    version="9A",

    description=(
        "Frozen server-side inference engine "
        "for heterogeneous multi-parent "
        "game MOD provenance reconstruction."
    ),
)


@app.get(
    "/health"
)
def health():

    process = psutil.Process(
        os.getpid()
    )


    return {
        "status":
            "ok",

        "phase":
            "9A",

        "method_frozen":
            True,

        "alpha":
            ALPHA,

        "lambda":
            LAMBDA,

        "candidate_pool_M":
            CANDIDATE_POOL_SIZE,

        "graph_beta":
            GRAPH_BETA,

        "boundary_top_r":
            BOUNDARY_TOP_R,

        "Kmax":
            MAX_KNOWN_PARENTS,

        "rss_bytes":
            int(
                process
                .memory_info()
                .rss
            ),
    }


@app.post(
    "/analyze"
)
def analyze(
    request: AnalyzeRequest,
):

    try:

        return analyze_internal(
            request
        )

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(
                error
            ),
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(
                error
            ),
        )


# =========================================================
# Regression request generator
#
# This is only a helper endpoint for Phase 9B.
#
# It creates an API request from the already-frozen
# Phase 7H TEST score matrix.
# No private GT is included in the request.
# =========================================================

_score_cache = None
_graph_cache = None


def load_regression_cache():

    global _score_cache
    global _graph_cache


    if _score_cache is None:

        if not PHASE7H_SCORE_CSV.exists():

            raise FileNotFoundError(
                PHASE7H_SCORE_CSV
            )


        _score_cache = pd.read_csv(
            PHASE7H_SCORE_CSV
        )


    if _graph_cache is None:

        if not STRESS_GRAPH_CSV.exists():

            raise FileNotFoundError(
                STRESS_GRAPH_CSV
            )


        _graph_cache = pd.read_csv(
            STRESS_GRAPH_CSV
        )


@app.get(
    "/regression/{query_id}"
)
def regression(
    query_id: str,
):

    try:

        load_regression_cache()


        group = _score_cache[
            _score_cache[
                "query_id"
            ].astype(str)
            ==
            str(
                query_id
            )
        ]


        if len(group) == 0:

            raise HTTPException(
                status_code=404,
                detail=(
                    "query_id not found "
                    "in frozen TEST scores"
                ),
            )


        components = []


        for node_id, node_group in (
            group.groupby(
                "node_id",
                sort=True,
            )
        ):

            modality_values = set(
                node_group[
                    "modality"
                ].astype(str)
            )


            if len(
                modality_values
            ) != 1:

                raise RuntimeError(
                    "Mixed modality in score rows"
                )


            modality = next(
                iter(
                    modality_values
                )
            )


            parent_scores = []


            for row in (
                node_group.itertuples(
                    index=False
                )
            ):

                parent_scores.append({
                    "parent_id":
                        str(
                            row.candidate_parent
                        ),

                    "fused_parent_distance":
                        float(
                            row.fused_parent_distance
                        ),

                    "mean_regret":
                        float(
                            row.mean_regret
                        ),
                })


            components.append({
                "node_id":
                    str(
                        node_id
                    ),

                "modality":
                    modality,

                "parent_scores":
                    parent_scores,
            })


        graph_group = _graph_cache[
            _graph_cache[
                "query_id"
            ].astype(str)
            ==
            str(
                query_id
            )
        ]


        edges = []


        for row in (
            graph_group.itertuples(
                index=False
            )
        ):

            edges.append({
                "node_a":
                    str(
                        row.node_a
                    ),

                "node_b":
                    str(
                        row.node_b
                    ),
            })


        request = AnalyzeRequest(
            query_id=str(
                query_id
            ),
            components=components,
            edges=edges,
        )


        return analyze_internal(
            request
        )


    except HTTPException:

        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(
                error
            ),
        )