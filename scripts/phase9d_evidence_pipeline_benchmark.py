import json
import platform
import time
import urllib.error
import urllib.request

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
import psutil


# =========================================================
# Configuration
# =========================================================

BASE_URL = "http://127.0.0.1:8000"

HEALTH_URL = (
    BASE_URL
    + "/health"
)

ANALYZE_PREFIX = (
    BASE_URL
    + "/analyze-evidence/"
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

PHASE9B_SUMMARY_JSON = Path(
    "results/phase9b_server_correctness_summary.json"
)


# =========================================================
# Outputs
# =========================================================

OUTPUT_CORRECTNESS_CSV = Path(
    "results/phase9d_evidence_correctness_audit.csv"
)

OUTPUT_REQUESTS_CSV = Path(
    "results/phase9d_evidence_request_results.csv"
)

OUTPUT_CONCURRENCY_CSV = Path(
    "results/phase9d_evidence_concurrency_summary.csv"
)

OUTPUT_SUMMARY_JSON = Path(
    "results/phase9d_evidence_pipeline_summary.json"
)


# =========================================================
# Protocol
# =========================================================

EXPECTED_QUERIES = 360
EXPECTED_COMPONENTS = 2520

CONCURRENCY_LEVELS = [
    1,
    4,
    8,
    16,
    32,
]

REQUESTS_PER_LEVEL = 300

WARMUP_REQUESTS = 30

RANDOM_SEED = 20260813

TIMEOUT_SECONDS = 120


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

    if isinstance(
        value,
        list,
    ):
        return value

    return json.loads(
        clean_text(
            value
        )
    )


def percentile(
    values,
    q,
):

    return float(
        np.percentile(
            np.asarray(
                values,
                dtype=np.float64,
            ),
            q,
        )
    )


def get_json(
    url,
    timeout=TIMEOUT_SECONDS,
):

    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Accept":
                "application/json",

            "Connection":
                "keep-alive",
        },
    )


    start = time.perf_counter_ns()


    try:

        with urllib.request.urlopen(
            request,
            timeout=timeout,
        ) as response:

            data = json.loads(
                response.read().decode(
                    "utf-8"
                )
            )


            end = time.perf_counter_ns()


            return {
                "success":
                    True,

                "status":
                    int(
                        response.status
                    ),

                "client_ms":
                    (
                        end
                        -
                        start
                    )
                    / 1_000_000.0,

                "json":
                    data,

                "error":
                    "",
            }


    except Exception as error:

        end = time.perf_counter_ns()


        return {
            "success":
                False,

            "status":
                0,

            "client_ms":
                (
                    end
                    -
                    start
                )
                / 1_000_000.0,

            "json":
                None,

            "error":
                repr(
                    error
                ),
        }


# =========================================================
# Load frozen predictions
# =========================================================

for path in [
    FINAL_QUERY_CSV,
    FINAL_COMPONENT_CSV,
    PHASE9B_SUMMARY_JSON,
]:

    if not path.exists():

        raise FileNotFoundError(
            path
        )


queries = pd.read_csv(
    FINAL_QUERY_CSV
)

components = pd.read_csv(
    FINAL_COMPONENT_CSV
)


phase9b = json.loads(
    PHASE9B_SUMMARY_JSON.read_text(
        encoding="utf-8"
    )
)


if not phase9b[
    "correctness_passed"
]:

    raise RuntimeError(
        "Phase 9B correctness did not pass"
    )


if len(
    queries
) != EXPECTED_QUERIES:

    raise RuntimeError(
        "Expected 360 queries"
    )


if len(
    components
) != EXPECTED_COMPONENTS:

    raise RuntimeError(
        "Expected 2520 components"
    )


queries[
    "query_id"
] = (
    queries[
        "query_id"
    ].astype(str)
)


components[
    "query_id"
] = (
    components[
        "query_id"
    ].astype(str)
)


components[
    "node_id"
] = (
    components[
        "node_id"
    ].astype(str)
)


query_ids = sorted(
    queries[
        "query_id"
    ].tolist()
)


# =========================================================
# Health
# =========================================================

print(
    "======================================"
)

print(
    "Phase 9D - Evidence Pipeline Benchmark"
)

print(
    "======================================"
)


health_response = get_json(
    HEALTH_URL,
    timeout=30,
)


if not health_response[
    "success"
]:

    raise RuntimeError(
        "Phase 9D server unavailable"
    )


health = health_response[
    "json"
]


if health.get(
    "phase"
) != "9D":

    raise RuntimeError(
        "Wrong server phase"
    )


if int(
    health[
        "gallery_projects"
    ]
) != 60:

    raise RuntimeError(
        "Expected 60 gallery projects"
    )


rss_before_all = int(
    health[
        "rss_bytes"
    ]
)


print(
    "Phase 9D health: PASS"
)


# =========================================================
# Frozen local maps
# =========================================================

query_reference = {}


for row in queries.itertuples(
    index=False
):

    query_reference[
        clean_text(
            row.query_id
        )
    ] = {
        "parent_set":
            sorted(
                parse_json_list(
                    row.predicted_parent_set
                )
            ),

        "candidate_pool":
            parse_json_list(
                row.candidate_pool
            ),

        "selected_subset":
            parse_json_list(
                row.selected_known_subset
            ),

        "k":
            int(
                row.k_pred
            ),
    }


component_reference = {}


for row in components.itertuples(
    index=False
):

    component_reference[
        (
            clean_text(
                row.query_id
            ),
            clean_text(
                row.node_id
            ),
        )
    ] = clean_text(
        row.predicted_label
    )


# =========================================================
# A. 360-query correctness
# =========================================================

print()

print(
    "A. Evidence-to-result correctness regression"
)


correctness_rows = []


parent_set_matches = 0
candidate_matches = 0
subset_matches = 0
k_matches = 0
component_matches = 0


for index, query_id in enumerate(
    query_ids,
    start=1,
):

    if (
        index == 1
        or
        index % 30 == 0
    ):

        print(
            "correctness",
            index,
            "/",
            EXPECTED_QUERIES,
        )


    response = get_json(
        ANALYZE_PREFIX
        + query_id,
    )


    if not response[
        "success"
    ]:

        raise RuntimeError(
            f"{query_id}: "
            f"{response['error']}"
        )


    result = response[
        "json"
    ]


    reference = query_reference[
        query_id
    ]


    server_parent_set = sorted(
        result[
            "predicted_parent_set"
        ]
    )


    parent_match = bool(
        server_parent_set
        ==
        reference[
            "parent_set"
        ]
    )


    candidate_match = bool(
        result[
            "candidate_pool_top10"
        ]
        ==
        reference[
            "candidate_pool"
        ]
    )


    subset_match = bool(
        result[
            "selected_known_subset"
        ]
        ==
        reference[
            "selected_subset"
        ]
    )


    k_match = bool(
        int(
            result[
                "predicted_k"
            ]
        )
        ==
        reference[
            "k"
        ]
    )


    local_component_matches = 0


    for component in result[
        "components"
    ]:

        key = (
            query_id,
            clean_text(
                component[
                    "node_id"
                ]
            ),
        )


        server_prediction = (
            clean_text(
                component[
                    "predicted_parent"
                ]
            )
        )


        if (
            key
            in component_reference
            and
            server_prediction
            ==
            component_reference[
                key
            ]
        ):

            local_component_matches += 1


    parent_set_matches += int(
        parent_match
    )

    candidate_matches += int(
        candidate_match
    )

    subset_matches += int(
        subset_match
    )

    k_matches += int(
        k_match
    )

    component_matches += (
        local_component_matches
    )


    correctness_rows.append({
        "query_id":
            query_id,

        "parent_set_match":
            parent_match,

        "candidate_top10_match":
            candidate_match,

        "selected_subset_match":
            subset_match,

        "k_match":
            k_match,

        "component_matches":
            local_component_matches,

        "components_expected":
            7,

        "full_match":
            bool(
                parent_match
                and
                candidate_match
                and
                subset_match
                and
                k_match
                and
                local_component_matches
                == 7
            ),
    })


correctness_df = pd.DataFrame(
    correctness_rows
)


fully_identical_queries = int(
    correctness_df[
        "full_match"
    ].astype(bool).sum()
)


correctness_passed = bool(
    parent_set_matches
    == 360

    and

    candidate_matches
    == 360

    and

    subset_matches
    == 360

    and

    k_matches
    == 360

    and

    component_matches
    == 2520

    and

    fully_identical_queries
    == 360
)


print()

print(
    "Parent set:",
    parent_set_matches,
    "/ 360"
)

print(
    "Candidate Top-10:",
    candidate_matches,
    "/ 360"
)

print(
    "Subset:",
    subset_matches,
    "/ 360"
)

print(
    "K:",
    k_matches,
    "/ 360"
)

print(
    "Components:",
    component_matches,
    "/ 2520"
)

print(
    "Fully identical:",
    fully_identical_queries,
    "/ 360"
)


if not correctness_passed:

    correctness_df.to_csv(
        OUTPUT_CORRECTNESS_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    raise RuntimeError(
        "Phase 9D correctness mismatch. "
        "Performance benchmark aborted."
    )


print(
    "Evidence pipeline correctness: PASS"
)


# =========================================================
# Warm-up
# =========================================================

rng = np.random.default_rng(
    RANDOM_SEED
)


print()

print(
    "Warm-up:",
    WARMUP_REQUESTS
)


for query_id in rng.choice(
    np.array(
        query_ids,
        dtype=object,
    ),
    size=WARMUP_REQUESTS,
    replace=True,
):

    response = get_json(
        ANALYZE_PREFIX
        + str(
            query_id
        )
    )


    if not response[
        "success"
    ]:

        raise RuntimeError(
            "Warm-up failure"
        )


print(
    "Warm-up: PASS"
)


# =========================================================
# Request worker
# =========================================================

def benchmark_request(
    request_index,
    query_id,
    concurrency,
):

    response = get_json(
        ANALYZE_PREFIX
        + str(
            query_id
        )
    )


    row = {
        "concurrency":
            int(
                concurrency
            ),

        "request_index":
            int(
                request_index
            ),

        "query_id":
            str(
                query_id
            ),

        "success":
            bool(
                response[
                    "success"
                ]
            ),

        "client_latency_ms":
            float(
                response[
                    "client_ms"
                ]
            ),

        "search_ms":
            np.nan,

        "reconstruction_ms":
            np.nan,

        "server_total_ms":
            np.nan,

        "error":
            response[
                "error"
            ],
    }


    if response[
        "success"
    ]:

        result = response[
            "json"
        ]


        latency = result[
            "phase9d_latency_ms"
        ]


        row[
            "search_ms"
        ] = float(
            latency[
                "gallery_similarity_search"
            ]
        )


        row[
            "reconstruction_ms"
        ] = float(
            latency[
                "reconstruction"
            ]
        )


        row[
            "server_total_ms"
        ] = float(
            latency[
                "total_evidence_to_result"
            ]
        )


    return row


# =========================================================
# B. Concurrency benchmark
# =========================================================

print()

print(
    "B. Evidence pipeline concurrency benchmark"
)


all_request_rows = []
summary_rows = []


for concurrency in (
    CONCURRENCY_LEVELS
):

    print()

    print(
        "Concurrency:",
        concurrency
    )


    selected_ids = rng.choice(
        np.array(
            query_ids,
            dtype=object,
        ),
        size=REQUESTS_PER_LEVEL,
        replace=True,
    )


    wall_start = time.perf_counter()


    level_rows = []


    with ThreadPoolExecutor(
        max_workers=concurrency
    ) as executor:

        futures = [
            executor.submit(
                benchmark_request,
                index,
                query_id,
                concurrency,
            )

            for index, query_id
            in enumerate(
                selected_ids,
                start=1,
            )
        ]


        completed = 0


        for future in as_completed(
            futures
        ):

            level_rows.append(
                future.result()
            )

            completed += 1


            if (
                completed == 1
                or
                completed % 100 == 0
            ):

                print(
                    completed,
                    "/",
                    REQUESTS_PER_LEVEL,
                )


    wall_end = time.perf_counter()


    level_df = pd.DataFrame(
        level_rows
    )


    success_df = level_df[
        level_df[
            "success"
        ].astype(bool)
    ].copy()


    success_count = int(
        len(
            success_df
        )
    )


    failure_count = int(
        len(
            level_df
        )
        -
        success_count
    )


    wall_seconds = float(
        wall_end
        -
        wall_start
    )


    throughput = float(
        success_count
        /
        wall_seconds
    )


    def stats(column):

        values = (
            success_df[
                column
            ]
            .astype(float)
            .dropna()
            .to_numpy()
        )


        if len(
            values
        ) == 0:

            return {
                "mean": None,
                "p50": None,
                "p95": None,
                "p99": None,
            }


        return {
            "mean":
                float(
                    values.mean()
                ),

            "p50":
                percentile(
                    values,
                    50,
                ),

            "p95":
                percentile(
                    values,
                    95,
                ),

            "p99":
                percentile(
                    values,
                    99,
                ),
        }


    client = stats(
        "client_latency_ms"
    )

    search = stats(
        "search_ms"
    )

    reconstruction = stats(
        "reconstruction_ms"
    )

    server_total = stats(
        "server_total_ms"
    )


    summary_rows.append({
        "concurrency":
            concurrency,

        "requests":
            REQUESTS_PER_LEVEL,

        "success_count":
            success_count,

        "failure_count":
            failure_count,

        "success_rate":
            float(
                success_count
                /
                REQUESTS_PER_LEVEL
            ),

        "wall_seconds":
            wall_seconds,

        "throughput_requests_per_second":
            throughput,

        "client_mean_ms":
            client[
                "mean"
            ],

        "client_p50_ms":
            client[
                "p50"
            ],

        "client_p95_ms":
            client[
                "p95"
            ],

        "client_p99_ms":
            client[
                "p99"
            ],

        "search_mean_ms":
            search[
                "mean"
            ],

        "search_p50_ms":
            search[
                "p50"
            ],

        "search_p95_ms":
            search[
                "p95"
            ],

        "search_p99_ms":
            search[
                "p99"
            ],

        "reconstruction_mean_ms":
            reconstruction[
                "mean"
            ],

        "reconstruction_p50_ms":
            reconstruction[
                "p50"
            ],

        "reconstruction_p95_ms":
            reconstruction[
                "p95"
            ],

        "server_total_mean_ms":
            server_total[
                "mean"
            ],

        "server_total_p50_ms":
            server_total[
                "p50"
            ],

        "server_total_p95_ms":
            server_total[
                "p95"
            ],

        "server_total_p99_ms":
            server_total[
                "p99"
            ],
    })


    all_request_rows.extend(
        level_rows
    )


    print(
        "success:",
        success_count,
        "/",
        REQUESTS_PER_LEVEL
    )

    print(
        "throughput:",
        round(
            throughput,
            3,
        ),
        "req/s"
    )

    print(
        "server p50/p95:",
        round(
            server_total[
                "p50"
            ],
            3,
        ),
        "/",
        round(
            server_total[
                "p95"
            ],
            3,
        ),
        "ms"
    )

    print(
        "search p50/p95:",
        round(
            search[
                "p50"
            ],
            3,
        ),
        "/",
        round(
            search[
                "p95"
            ],
            3,
        ),
        "ms"
    )


request_df = pd.DataFrame(
    all_request_rows
)


concurrency_df = pd.DataFrame(
    summary_rows
)


# =========================================================
# Final health / memory
# =========================================================

health_after = get_json(
    HEALTH_URL
)[
    "json"
]


rss_after_all = int(
    health_after[
        "rss_bytes"
    ]
)


best_row = concurrency_df.loc[
    concurrency_df[
        "throughput_requests_per_second"
    ].idxmax()
]


all_zero_failures = bool(
    (
        concurrency_df[
            "failure_count"
        ]
        == 0
    ).all()
)


# =========================================================
# Save
# =========================================================

OUTPUT_CORRECTNESS_CSV.parent.mkdir(
    parents=True,
    exist_ok=True,
)


correctness_df.to_csv(
    OUTPUT_CORRECTNESS_CSV,
    index=False,
    encoding="utf-8-sig",
)


request_df.to_csv(
    OUTPUT_REQUESTS_CSV,
    index=False,
    encoding="utf-8-sig",
)


concurrency_df.to_csv(
    OUTPUT_CONCURRENCY_CSV,
    index=False,
    encoding="utf-8-sig",
)


summary = {
    "phase9d_complete":
        True,

    "performance_scope":
        (
            "IDENTITY_NEUTRAL_EVIDENCE_"
            "TO_GALLERY_SEARCH_"
            "TO_PROVENANCE_RECONSTRUCTION"
        ),

    "includes_gallery_similarity_search":
        True,

    "includes_reconstruction":
        True,

    "includes_archive_parsing":
        False,

    "includes_raw_evidence_extraction":
        False,

    "end_to_end_mod_package_analysis":
        False,

    "correctness": {
        "parent_set_queries":
            parent_set_matches,

        "candidate_top10_queries":
            candidate_matches,

        "selected_subset_queries":
            subset_matches,

        "k_queries":
            k_matches,

        "component_assignments":
            component_matches,

        "fully_identical_queries":
            fully_identical_queries,

        "mismatches":
            int(
                360
                -
                fully_identical_queries
            ),

        "passed":
            correctness_passed,
    },

    "benchmark_protocol": {
        "concurrency_levels":
            CONCURRENCY_LEVELS,

        "requests_per_level":
            REQUESTS_PER_LEVEL,

        "total_measured_requests":
            int(
                REQUESTS_PER_LEVEL
                *
                len(
                    CONCURRENCY_LEVELS
                )
            ),

        "warmup_requests":
            WARMUP_REQUESTS,

        "random_seed":
            RANDOM_SEED,

        "server":
            (
                "FastAPI/Uvicorn "
                "single process"
            ),
    },

    "host_system": {
        "platform":
            platform.platform(),

        "python_version":
            platform.python_version(),

        "physical_cpu_cores":
            psutil.cpu_count(
                logical=False
            ),

        "logical_cpu_cores":
            psutil.cpu_count(
                logical=True
            ),

        "total_memory_bytes":
            int(
                psutil.virtual_memory().total
            ),
    },

    "gallery": {
        "projects":
            int(
                health[
                    "gallery_projects"
                ]
            ),

        "code_components":
            int(
                health[
                    "gallery_code_components"
                ]
            ),

        "structured_components":
            int(
                health[
                    "gallery_structured_components"
                ]
            ),

        "image_components":
            int(
                health[
                    "gallery_image_components"
                ]
            ),
    },

    "results_by_concurrency": {
        str(
            int(
                row[
                    "concurrency"
                ]
            )
        ): {
            key:
                (
                    int(value)
                    if key
                    in {
                        "concurrency",
                        "requests",
                        "success_count",
                        "failure_count",
                    }
                    else
                    float(value)
                )

            for key, value
            in row.items()
        }

        for row
        in summary_rows
    },

    "aggregate": {
        "all_levels_zero_failures":
            all_zero_failures,

        "best_throughput_concurrency":
            int(
                best_row[
                    "concurrency"
                ]
            ),

        "best_throughput_requests_per_second":
            float(
                best_row[
                    "throughput_requests_per_second"
                ]
            ),

        "rss_before_bytes":
            rss_before_all,

        "rss_after_bytes":
            rss_after_all,

        "rss_change_bytes":
            int(
                rss_after_all
                -
                rss_before_all
            ),
    },

    "interpretation_warning":
        (
            "Phase 9D starts from already-extracted "
            "identity-neutral component evidence. "
            "It includes full TEST-gallery similarity "
            "computation and frozen provenance "
            "reconstruction, but excludes MOD archive "
            "parsing and raw bytecode/resource/image "
            "evidence extraction."
        ),

    "ready_for_phase9e":
        bool(
            correctness_passed
            and
            all_zero_failures
        ),

    "goals_met":
        bool(
            correctness_passed
            and
            len(
                concurrency_df
            )
            == 5
            and
            len(
                request_df
            )
            == 1500
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


# =========================================================
# Print
# =========================================================

print()

print(
    "======================================"
)

print(
    "PHASE 9D FINAL RESULT"
)

print(
    "======================================"
)


print(
    concurrency_df[
        [
            "concurrency",
            "success_rate",
            "throughput_requests_per_second",
            "client_p50_ms",
            "client_p95_ms",
            "search_p50_ms",
            "search_p95_ms",
            "reconstruction_p50_ms",
            "server_total_p50_ms",
            "server_total_p95_ms",
        ]
    ].to_string(
        index=False
    )
)


print()

print(
    "Correctness:",
    fully_identical_queries,
    "/ 360"
)

print(
    "Components:",
    component_matches,
    "/ 2520"
)

print(
    "Best throughput:",
    float(
        best_row[
            "throughput_requests_per_second"
        ]
    ),
    "req/s @",
    int(
        best_row[
            "concurrency"
        ]
    )
)

print(
    "Zero failures:",
    all_zero_failures
)

print(
    "Ready for 9E:",
    summary[
        "ready_for_phase9e"
    ]
)

print()

print(
    "Summary:",
    OUTPUT_SUMMARY_JSON
)