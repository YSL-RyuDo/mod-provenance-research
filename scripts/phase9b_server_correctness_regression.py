import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd


# =========================================================
# Configuration
# =========================================================

SERVER_BASE_URL = "http://127.0.0.1:8000"

HEALTH_URL = (
    SERVER_BASE_URL
    + "/health"
)

REGRESSION_URL_PREFIX = (
    SERVER_BASE_URL
    + "/regression/"
)


# =========================================================
# Inputs
# =========================================================

FINAL_QUERY_CSV = Path(
    "results/phase7h_final_query_predictions.csv"
)

FINAL_COMPONENT_CSV = Path(
    "results/phase7h_final_component_predictions.csv"
)

PHASE7H_SUMMARY_JSON = Path(
    "results/phase7h_final_test_summary.json"
)

PHASE7G_PARAMETERS_JSON = Path(
    "results/phase7g_final_method_parameters.json"
)


# =========================================================
# Outputs
# =========================================================

OUTPUT_QUERY_AUDIT_CSV = Path(
    "results/phase9b_server_query_regression_audit.csv"
)

OUTPUT_COMPONENT_AUDIT_CSV = Path(
    "results/phase9b_server_component_regression_audit.csv"
)

OUTPUT_SUMMARY_JSON = Path(
    "results/phase9b_server_correctness_summary.json"
)


# =========================================================
# Expected frozen benchmark size
# =========================================================

EXPECTED_QUERIES = 360
EXPECTED_COMPONENTS = 2520
EXPECTED_COMPONENTS_PER_QUERY = 7

EXPECTED_ALPHA = 0.75
EXPECTED_LAMBDA = 0.5
EXPECTED_M = 10
EXPECTED_BETA = 0.1
EXPECTED_TOP_R = 3
EXPECTED_KMAX = 3

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


def parse_json_list(value):

    if isinstance(value, list):
        return value

    text = clean_text(
        value
    )

    if not text:
        return []

    parsed = json.loads(
        text
    )

    if not isinstance(
        parsed,
        list,
    ):
        raise ValueError(
            f"Expected JSON list, got: {value}"
        )

    return parsed


def http_get_json(
    url,
    timeout_seconds=30,
):

    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Accept":
                "application/json"
        },
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=timeout_seconds,
        ) as response:

            body = response.read()

            return (
                int(
                    response.status
                ),
                json.loads(
                    body.decode(
                        "utf-8"
                    )
                ),
            )

    except urllib.error.HTTPError as error:

        body = error.read().decode(
            "utf-8",
            errors="replace",
        )

        raise RuntimeError(
            f"HTTP {error.code}: "
            f"{body}"
        )

    except urllib.error.URLError as error:

        raise RuntimeError(
            "Cannot connect to Phase 9A server. "
            "Make sure uvicorn is still running. "
            f"Reason: {error}"
        )


def list_equal_exact(
    first,
    second,
):

    return list(
        first
    ) == list(
        second
    )


def sorted_set_equal(
    first,
    second,
):

    return sorted(
        set(
            first
        )
    ) == sorted(
        set(
            second
        )
    )


# =========================================================
# Validate local input files
# =========================================================

required_paths = [
    FINAL_QUERY_CSV,
    FINAL_COMPONENT_CSV,
    PHASE7H_SUMMARY_JSON,
    PHASE7G_PARAMETERS_JSON,
]


for path in required_paths:

    if not path.exists():

        raise FileNotFoundError(
            f"Missing required file: {path}"
        )


final_queries = pd.read_csv(
    FINAL_QUERY_CSV
)

final_components = pd.read_csv(
    FINAL_COMPONENT_CSV
)


phase7h_summary = json.loads(
    PHASE7H_SUMMARY_JSON.read_text(
        encoding="utf-8"
    )
)


phase7g_parameters = json.loads(
    PHASE7G_PARAMETERS_JSON.read_text(
        encoding="utf-8"
    )
)


if len(
    final_queries
) != EXPECTED_QUERIES:

    raise RuntimeError(
        f"Expected {EXPECTED_QUERIES} "
        f"queries, got {len(final_queries)}"
    )


if len(
    final_components
) != EXPECTED_COMPONENTS:

    raise RuntimeError(
        f"Expected {EXPECTED_COMPONENTS} "
        f"components, got "
        f"{len(final_components)}"
    )


final_queries[
    "query_id"
] = (
    final_queries[
        "query_id"
    ]
    .astype(str)
)


final_components[
    "query_id"
] = (
    final_components[
        "query_id"
    ]
    .astype(str)
)


final_components[
    "node_id"
] = (
    final_components[
        "node_id"
    ]
    .astype(str)
)


# =========================================================
# Local prediction maps
# =========================================================

query_ground_truth = {}


for row in final_queries.itertuples(
    index=False
):

    query_id = clean_text(
        row.query_id
    )


    query_ground_truth[
        query_id
    ] = {
        "predicted_parent_set":
            parse_json_list(
                row.predicted_parent_set
            ),

        "selected_known_subset":
            parse_json_list(
                row.selected_known_subset
            ),

        "candidate_pool":
            parse_json_list(
                row.candidate_pool
            ),

        "k_pred":
            int(
                row.k_pred
            ),

        "scenario":
            clean_text(
                row.scenario
            ),

        "k_true":
            int(
                row.k_true
            ),
    }


component_ground_truth = {}


for row in final_components.itertuples(
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


    if key in component_ground_truth:

        raise RuntimeError(
            f"Duplicate component key: {key}"
        )


    component_ground_truth[
        key
    ] = {
        "predicted_label":
            clean_text(
                row.predicted_label
            ),

        "modality":
            clean_text(
                row.modality
            ),
    }


if len(
    component_ground_truth
) != EXPECTED_COMPONENTS:

    raise RuntimeError(
        "Unexpected unique component count"
    )


# =========================================================
# Server health verification
# =========================================================

print(
    "======================================"
)

print(
    "Phase 9B - Server Correctness Regression"
)

print(
    "======================================"
)

print()

print(
    "Checking Phase 9A server..."
)


health_status, health = (
    http_get_json(
        HEALTH_URL
    )
)


if health_status != 200:

    raise RuntimeError(
        "Health endpoint did not return 200"
    )


if health.get(
    "status"
) != "ok":

    raise RuntimeError(
        "Server health status is not ok"
    )


if not health.get(
    "method_frozen",
    False,
):

    raise RuntimeError(
        "Server does not report frozen method"
    )


health_checks = {
    "alpha":
        np.isclose(
            float(
                health[
                    "alpha"
                ]
            ),
            EXPECTED_ALPHA,
            atol=EPSILON,
            rtol=0.0,
        ),

    "lambda":
        np.isclose(
            float(
                health[
                    "lambda"
                ]
            ),
            EXPECTED_LAMBDA,
            atol=EPSILON,
            rtol=0.0,
        ),

    "candidate_pool_M":
        int(
            health[
                "candidate_pool_M"
            ]
        )
        == EXPECTED_M,

    "graph_beta":
        np.isclose(
            float(
                health[
                    "graph_beta"
                ]
            ),
            EXPECTED_BETA,
            atol=EPSILON,
            rtol=0.0,
        ),

    "boundary_top_r":
        int(
            health[
                "boundary_top_r"
            ]
        )
        == EXPECTED_TOP_R,

    "Kmax":
        int(
            health[
                "Kmax"
            ]
        )
        == EXPECTED_KMAX,
}


if not all(
    health_checks.values()
):

    raise RuntimeError(
        "Server frozen parameter mismatch: "
        + json.dumps(
            health_checks,
            ensure_ascii=False,
        )
    )


print(
    "Server health/frozen parameters: PASS"
)


# =========================================================
# Full 360-query regression
# =========================================================

query_audit_rows = []
component_audit_rows = []


server_request_latencies = []

server_internal_latencies = []


query_ids = sorted(
    query_ground_truth.keys()
)


wall_start = time.perf_counter()


for query_index, query_id in enumerate(
    query_ids,
    start=1,
):

    if (
        query_index == 1
        or
        query_index % 30 == 0
    ):

        print(
            "query",
            query_index,
            "/",
            EXPECTED_QUERIES,
        )


    local_query = (
        query_ground_truth[
            query_id
        ]
    )


    request_start = (
        time.perf_counter()
    )


    status_code, server_result = (
        http_get_json(
            REGRESSION_URL_PREFIX
            + query_id,
            timeout_seconds=60,
        )
    )


    request_end = (
        time.perf_counter()
    )


    client_roundtrip_ms = (
        request_end
        -
        request_start
    ) * 1000.0


    server_request_latencies.append(
        client_roundtrip_ms
    )


    if status_code != 200:

        raise RuntimeError(
            f"{query_id}: server status "
            f"{status_code}"
        )


    returned_query_id = clean_text(
        server_result.get(
            "query_id"
        )
    )


    if returned_query_id != query_id:

        raise RuntimeError(
            f"{query_id}: response query_id "
            f"mismatch ({returned_query_id})"
        )


    server_parent_set = (
        server_result.get(
            "predicted_parent_set",
            [],
        )
    )


    server_selected_subset = (
        server_result.get(
            "selected_known_subset",
            [],
        )
    )


    server_candidate_pool = (
        server_result.get(
            "candidate_pool_top10",
            [],
        )
    )


    server_k = int(
        server_result.get(
            "predicted_k"
        )
    )


    local_parent_set = (
        local_query[
            "predicted_parent_set"
        ]
    )


    local_selected_subset = (
        local_query[
            "selected_known_subset"
        ]
    )


    local_candidate_pool = (
        local_query[
            "candidate_pool"
        ]
    )


    local_k = int(
        local_query[
            "k_pred"
        ]
    )


    parent_set_match = (
        sorted_set_equal(
            server_parent_set,
            local_parent_set,
        )
    )


    k_match = bool(
        server_k
        ==
        local_k
    )


    selected_subset_match = (
        list_equal_exact(
            server_selected_subset,
            local_selected_subset,
        )
    )


    candidate_pool_match = (
        list_equal_exact(
            server_candidate_pool,
            local_candidate_pool,
        )
    )


    latency_block = (
        server_result.get(
            "latency_ms",
            {}
        )
    )


    server_internal_total_ms = float(
        latency_block.get(
            "total",
            np.nan,
        )
    )


    if np.isfinite(
        server_internal_total_ms
    ):

        server_internal_latencies.append(
            server_internal_total_ms
        )


    # -----------------------------------------------------
    # Components
    # -----------------------------------------------------

    returned_components = (
        server_result.get(
            "components",
            []
        )
    )


    if len(
        returned_components
    ) != EXPECTED_COMPONENTS_PER_QUERY:

        raise RuntimeError(
            f"{query_id}: server returned "
            f"{len(returned_components)} "
            f"components instead of 7"
        )


    returned_component_map = {}


    for component in returned_components:

        node_id = clean_text(
            component.get(
                "node_id"
            )
        )


        if node_id in returned_component_map:

            raise RuntimeError(
                f"{query_id}: duplicate returned "
                f"node {node_id}"
            )


        returned_component_map[
            node_id
        ] = component


    local_component_group = (
        final_components[
            final_components[
                "query_id"
            ]
            == query_id
        ]
    )


    if len(
        local_component_group
    ) != EXPECTED_COMPONENTS_PER_QUERY:

        raise RuntimeError(
            f"{query_id}: local component "
            "count is not 7"
        )


    query_component_matches = 0


    for local_component in (
        local_component_group.itertuples(
            index=False
        )
    ):

        node_id = clean_text(
            local_component.node_id
        )


        key = (
            query_id,
            node_id,
        )


        if node_id not in returned_component_map:

            component_audit_rows.append({
                "query_id":
                    query_id,

                "node_id":
                    node_id,

                "modality":
                    clean_text(
                        local_component.modality
                    ),

                "phase7h_prediction":
                    clean_text(
                        local_component.predicted_label
                    ),

                "server_prediction":
                    "",

                "prediction_match":
                    False,

                "error":
                    "NODE_MISSING_FROM_SERVER_RESPONSE",
            })

            continue


        returned_component = (
            returned_component_map[
                node_id
            ]
        )


        local_prediction = clean_text(
            local_component.predicted_label
        )


        server_prediction = clean_text(
            returned_component.get(
                "predicted_parent"
            )
        )


        local_modality = clean_text(
            local_component.modality
        )


        server_modality = clean_text(
            returned_component.get(
                "modality"
            )
        )


        prediction_match = bool(
            local_prediction
            ==
            server_prediction
        )


        modality_match = bool(
            local_modality
            ==
            server_modality
        )


        full_component_match = bool(
            prediction_match
            and
            modality_match
        )


        query_component_matches += int(
            full_component_match
        )


        component_audit_rows.append({
            "query_id":
                query_id,

            "node_id":
                node_id,

            "modality":
                local_modality,

            "phase7h_prediction":
                local_prediction,

            "server_prediction":
                server_prediction,

            "prediction_match":
                prediction_match,

            "modality_match":
                modality_match,

            "full_component_match":
                full_component_match,

            "error":
                "",
        })


    all_components_match = bool(
        query_component_matches
        ==
        EXPECTED_COMPONENTS_PER_QUERY
    )


    full_query_match = bool(
        parent_set_match
        and
        k_match
        and
        selected_subset_match
        and
        candidate_pool_match
        and
        all_components_match
    )


    query_audit_rows.append({
        "query_id":
            query_id,

        "scenario":
            local_query[
                "scenario"
            ],

        "k_true":
            local_query[
                "k_true"
            ],

        "phase7h_k_pred":
            local_k,

        "server_k_pred":
            server_k,

        "parent_set_match":
            parent_set_match,

        "k_match":
            k_match,

        "selected_subset_match":
            selected_subset_match,

        "candidate_pool_match":
            candidate_pool_match,

        "component_matches":
            int(
                query_component_matches
            ),

        "component_expected":
            EXPECTED_COMPONENTS_PER_QUERY,

        "all_components_match":
            all_components_match,

        "full_query_match":
            full_query_match,

        "client_roundtrip_ms":
            float(
                client_roundtrip_ms
            ),

        "server_internal_total_ms":
            float(
                server_internal_total_ms
            ),
    })


wall_end = time.perf_counter()


# =========================================================
# Audit DataFrames
# =========================================================

query_audit = pd.DataFrame(
    query_audit_rows
)


component_audit = pd.DataFrame(
    component_audit_rows
)


if len(
    query_audit
) != EXPECTED_QUERIES:

    raise RuntimeError(
        "Query audit count mismatch"
    )


if len(
    component_audit
) != EXPECTED_COMPONENTS:

    raise RuntimeError(
        "Component audit count mismatch"
    )


# =========================================================
# Aggregate correctness
# =========================================================

parent_set_matches = int(
    query_audit[
        "parent_set_match"
    ].astype(bool).sum()
)


k_matches = int(
    query_audit[
        "k_match"
    ].astype(bool).sum()
)


subset_matches = int(
    query_audit[
        "selected_subset_match"
    ].astype(bool).sum()
)


candidate_pool_matches = int(
    query_audit[
        "candidate_pool_match"
    ].astype(bool).sum()
)


full_query_matches = int(
    query_audit[
        "full_query_match"
    ].astype(bool).sum()
)


component_matches = int(
    component_audit[
        "full_component_match"
    ].astype(bool).sum()
)


query_mismatches = (
    EXPECTED_QUERIES
    -
    full_query_matches
)


component_mismatches = (
    EXPECTED_COMPONENTS
    -
    component_matches
)


# =========================================================
# Latency diagnostic only
#
# NOT Phase 9C publication benchmark.
# =========================================================

roundtrip_array = np.asarray(
    server_request_latencies,
    dtype=np.float64,
)


internal_array = np.asarray(
    server_internal_latencies,
    dtype=np.float64,
)


latency_diagnostic = {
    "warning":
        (
            "Correctness-regression latency only. "
            "Do not use as final server performance "
            "result. Requests are sequential and "
            "/regression reads already-computed "
            "Phase 7H score matrices."
        ),

    "client_roundtrip_ms": {
        "mean":
            float(
                roundtrip_array.mean()
            ),

        "p50":
            float(
                np.percentile(
                    roundtrip_array,
                    50,
                )
            ),

        "p95":
            float(
                np.percentile(
                    roundtrip_array,
                    95,
                )
            ),

        "p99":
            float(
                np.percentile(
                    roundtrip_array,
                    99,
                )
            ),

        "max":
            float(
                roundtrip_array.max()
            ),
    },

    "server_internal_reconstruction_ms": {
        "count":
            int(
                len(
                    internal_array
                )
            ),

        "mean":
            (
                float(
                    internal_array.mean()
                )
                if len(
                    internal_array
                ) > 0
                else None
            ),

        "p50":
            (
                float(
                    np.percentile(
                        internal_array,
                        50,
                    )
                )
                if len(
                    internal_array
                ) > 0
                else None
            ),

        "p95":
            (
                float(
                    np.percentile(
                        internal_array,
                        95,
                    )
                )
                if len(
                    internal_array
                ) > 0
                else None
            ),
    },

    "full_regression_wall_seconds":
        float(
            wall_end
            -
            wall_start
        ),
}


# =========================================================
# Save
# =========================================================

OUTPUT_QUERY_AUDIT_CSV.parent.mkdir(
    parents=True,
    exist_ok=True,
)


query_audit.to_csv(
    OUTPUT_QUERY_AUDIT_CSV,
    index=False,
    encoding="utf-8-sig",
)


component_audit.to_csv(
    OUTPUT_COMPONENT_AUDIT_CSV,
    index=False,
    encoding="utf-8-sig",
)


correctness_passed = bool(
    parent_set_matches
    == EXPECTED_QUERIES

    and

    k_matches
    == EXPECTED_QUERIES

    and

    subset_matches
    == EXPECTED_QUERIES

    and

    candidate_pool_matches
    == EXPECTED_QUERIES

    and

    component_matches
    == EXPECTED_COMPONENTS

    and

    full_query_matches
    == EXPECTED_QUERIES
)


summary = {
    "server_correctness_regression_complete":
        True,

    "server_phase":
        "9A",

    "evaluation_phase":
        "9B",

    "performance_scope":
        "CORRECTNESS_REGRESSION_ONLY",

    "phase7h_predictions_modified":
        False,

    "server_method_frozen":
        True,

    "server_health": {
        "status":
            health[
                "status"
            ],

        "alpha":
            float(
                health[
                    "alpha"
                ]
            ),

        "lambda":
            float(
                health[
                    "lambda"
                ]
            ),

        "candidate_pool_M":
            int(
                health[
                    "candidate_pool_M"
                ]
            ),

        "graph_beta":
            float(
                health[
                    "graph_beta"
                ]
            ),

        "boundary_top_r":
            int(
                health[
                    "boundary_top_r"
                ]
            ),

        "Kmax":
            int(
                health[
                    "Kmax"
                ]
            ),

        "rss_bytes_at_health_check":
            int(
                health[
                    "rss_bytes"
                ]
            ),
    },

    "expected": {
        "queries":
            EXPECTED_QUERIES,

        "components":
            EXPECTED_COMPONENTS,
    },

    "matches": {
        "parent_set_queries":
            parent_set_matches,

        "k_queries":
            k_matches,

        "selected_subset_queries":
            subset_matches,

        "candidate_top10_queries":
            candidate_pool_matches,

        "component_assignments":
            component_matches,

        "fully_identical_queries":
            full_query_matches,
    },

    "mismatches": {
        "queries":
            int(
                query_mismatches
            ),

        "components":
            int(
                component_mismatches
            ),

        "parent_set_queries":
            int(
                EXPECTED_QUERIES
                -
                parent_set_matches
            ),

        "k_queries":
            int(
                EXPECTED_QUERIES
                -
                k_matches
            ),

        "selected_subset_queries":
            int(
                EXPECTED_QUERIES
                -
                subset_matches
            ),

        "candidate_top10_queries":
            int(
                EXPECTED_QUERIES
                -
                candidate_pool_matches
            ),
    },

    "latency_diagnostic_not_for_publication":
        latency_diagnostic,

    "correctness_passed":
        correctness_passed,

    "ready_for_phase9c_performance_benchmark":
        correctness_passed,

    "goals_met":
        correctness_passed,
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
    "PHASE 9B RESULT"
)

print(
    "======================================"
)

print(
    "Parent-set:",
    parent_set_matches,
    "/",
    EXPECTED_QUERIES,
)

print(
    "K:",
    k_matches,
    "/",
    EXPECTED_QUERIES,
)

print(
    "Selected subset:",
    subset_matches,
    "/",
    EXPECTED_QUERIES,
)

print(
    "Candidate Top-10:",
    candidate_pool_matches,
    "/",
    EXPECTED_QUERIES,
)

print(
    "Components:",
    component_matches,
    "/",
    EXPECTED_COMPONENTS,
)

print(
    "Fully identical queries:",
    full_query_matches,
    "/",
    EXPECTED_QUERIES,
)

print()

print(
    "Query mismatches:",
    query_mismatches
)

print(
    "Component mismatches:",
    component_mismatches
)

print()

print(
    "CORRECTNESS PASSED:",
    correctness_passed
)

print(
    "READY FOR 9C:",
    correctness_passed
)

print()

print(
    "Query audit:",
    OUTPUT_QUERY_AUDIT_CSV
)

print(
    "Component audit:",
    OUTPUT_COMPONENT_AUDIT_CSV
)

print(
    "Summary:",
    OUTPUT_SUMMARY_JSON
)