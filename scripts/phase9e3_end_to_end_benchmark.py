import json
import platform
import time
import urllib.request

from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)

from pathlib import Path

import numpy as np
import pandas as pd
import psutil


# =========================================================
# URLs
# =========================================================

BASE_URL = "http://127.0.0.1:8000"

HEALTH_URL = (
    BASE_URL
    + "/health"
)

ANALYZE_PREFIX = (
    BASE_URL
    + "/analyze-package/"
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

PACKAGE_MANIFEST_CSV = Path(
    "results/phase9e_package_manifest.csv"
)

PHASE9E2_SUMMARY_JSON = Path(
    "results/phase9e2_evidence_regeneration_summary.json"
)


# =========================================================
# Outputs
# =========================================================

OUTPUT_CORRECTNESS_CSV = Path(
    "results/phase9e3_correctness_audit.csv"
)

OUTPUT_REQUESTS_CSV = Path(
    "results/phase9e3_request_results.csv"
)

OUTPUT_CONCURRENCY_CSV = Path(
    "results/phase9e3_concurrency_summary.csv"
)

OUTPUT_SUMMARY_JSON = Path(
    "results/phase9e3_end_to_end_summary.json"
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

REQUESTS_PER_LEVEL = 200

WARMUP_REQUESTS = 20

RANDOM_SEED = 20260813

TIMEOUT_SECONDS = 180


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

    text = clean_text(
        value
    )

    return json.loads(
        text
    )


def percentile(
    values,
    q,
):

    values = np.asarray(
        values,
        dtype=np.float64,
    )

    if len(values) == 0:
        return None

    return float(
        np.percentile(
            values,
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
        },
    )


    start = time.perf_counter_ns()


    try:

        with urllib.request.urlopen(
            request,
            timeout=timeout,
        ) as response:

            body = response.read()

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
                    json.loads(
                        body.decode(
                            "utf-8"
                        )
                    ),

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
# Load inputs
# =========================================================

for path in [
    FINAL_QUERY_CSV,
    FINAL_COMPONENT_CSV,
    PACKAGE_MANIFEST_CSV,
    PHASE9E2_SUMMARY_JSON,
]:

    if not path.exists():

        raise FileNotFoundError(
            path
        )


queries = pd.read_csv(
    FINAL_QUERY_CSV,
    dtype=str,
    keep_default_na=False,
)

components = pd.read_csv(
    FINAL_COMPONENT_CSV,
    dtype=str,
    keep_default_na=False,
)

packages = pd.read_csv(
    PACKAGE_MANIFEST_CSV,
    dtype=str,
    keep_default_na=False,
)


phase9e2 = json.loads(
    PHASE9E2_SUMMARY_JSON.read_text(
        encoding="utf-8"
    )
)


if not phase9e2.get(
    "correctness_passed",
    False,
):

    raise RuntimeError(
        "Phase 9E-2 did not pass"
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


if len(
    packages
) != EXPECTED_QUERIES:

    raise RuntimeError(
        "Expected 360 packages"
    )


query_ids = sorted(
    queries[
        "query_id"
    ].astype(str).tolist()
)


# =========================================================
# Reference maps
# =========================================================

query_reference = {}


for row in queries.itertuples(
    index=False
):

    query_id = clean_text(
        row.query_id
    )


    query_reference[
        query_id
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


package_size_by_query = {
    clean_text(
        row.query_id
    ):
        int(
            row.package_size_bytes
        )

    for row in packages.itertuples(
        index=False
    )
}


# =========================================================
# Health
# =========================================================

print(
    "======================================"
)

print(
    "Phase 9E-3 - Full Package Benchmark"
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
        "Phase 9E-3 server unavailable"
    )


health = health_response[
    "json"
]


if health.get(
    "phase"
) != "9E-3":

    raise RuntimeError(
        "Wrong server phase"
    )


if int(
    health[
        "packages"
    ]
) != 360:

    raise RuntimeError(
        "Expected 360 packages"
    )


if int(
    health[
        "gallery_projects"
    ]
) != 60:

    raise RuntimeError(
        "Expected 60 gallery projects"
    )


if not health.get(
    "phase7b_extractor_reused",
    False,
):

    raise RuntimeError(
        "Original Phase 7B extractor not reported"
    )


rss_before_all = int(
    health[
        "rss_bytes"
    ]
)


print(
    "Server health: PASS"
)


# =========================================================
# A. Full 360-query correctness regression
# =========================================================

print()

print(
    "A. Full package correctness regression"
)


correctness_rows = []


parent_matches = 0
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
        + query_id
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


    reference = (
        query_reference[
            query_id
        ]
    )


    parent_match = bool(
        sorted(
            result[
                "predicted_parent_set"
            ]
        )
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


        prediction = clean_text(
            component[
                "predicted_parent"
            ]
        )


        if (
            key
            in component_reference
            and
            prediction
            ==
            component_reference[
                key
            ]
        ):

            local_component_matches += 1


    full_match = bool(
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
    )


    parent_matches += int(
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

    component_matches += int(
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

        "full_match":
            full_match,

        "package_size_bytes":
            package_size_by_query[
                query_id
            ],
    })


correctness_df = pd.DataFrame(
    correctness_rows
)


fully_identical = int(
    correctness_df[
        "full_match"
    ].astype(bool).sum()
)


correctness_passed = bool(
    parent_matches
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

    fully_identical
    == 360
)


print()

print(
    "Parent set:",
    parent_matches,
    "/ 360"
)

print(
    "Candidate Top-10:",
    candidate_matches,
    "/ 360"
)

print(
    "Selected subset:",
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
    fully_identical,
    "/ 360"
)


OUTPUT_CORRECTNESS_CSV.parent.mkdir(
    parents=True,
    exist_ok=True,
)


correctness_df.to_csv(
    OUTPUT_CORRECTNESS_CSV,
    index=False,
    encoding="utf-8-sig",
)


if not correctness_passed:

    raise RuntimeError(
        "Phase 9E-3 correctness mismatch. "
        "Performance benchmark aborted."
    )


print(
    "Full package correctness: PASS"
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
# Worker
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

        "package_size_bytes":
            int(
                package_size_by_query[
                    str(
                        query_id
                    )
                ]
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

        "archive_manifest_ms":
            np.nan,

        "payload_read_ms":
            np.nan,

        "extraction_ms":
            np.nan,

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

        latency = (
            response[
                "json"
            ][
                "phase9e3_latency_ms"
            ]
        )


        row[
            "archive_manifest_ms"
        ] = float(
            latency[
                "archive_open_and_manifest"
            ]
        )


        row[
            "payload_read_ms"
        ] = float(
            latency[
                "payload_read"
            ]
        )


        row[
            "extraction_ms"
        ] = float(
            latency[
                "raw_evidence_extraction"
            ]
        )


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
                "total_server_processing"
            ]
        )


    return row


# =========================================================
# B. Concurrency benchmark
# =========================================================

print()

print(
    "B. Full package concurrency benchmark"
)


all_request_rows = []
summary_rows = []


def stats(
    dataframe,
    column,
):

    values = (
        dataframe[
            column
        ]
        .astype(float)
        .replace(
            [
                np.inf,
                -np.inf,
            ],
            np.nan,
        )
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
            "max": None,
        }


    return {
        "mean":
            float(
                np.mean(
                    values
                )
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

        "max":
            float(
                np.max(
                    values
                )
            ),
    }


for concurrency in CONCURRENCY_LEVELS:

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


    level_rows = []


    wall_start = (
        time.perf_counter()
    )


    with ThreadPoolExecutor(
        max_workers=concurrency
    ) as executor:

        futures = [
            executor.submit(
                benchmark_request,
                request_index,
                query_id,
                concurrency,
            )

            for request_index, query_id
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
                completed % 50 == 0
            ):

                print(
                    completed,
                    "/",
                    REQUESTS_PER_LEVEL,
                )


    wall_end = (
        time.perf_counter()
    )


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


    client = stats(
        success_df,
        "client_latency_ms",
    )

    archive = stats(
        success_df,
        "archive_manifest_ms",
    )

    payload = stats(
        success_df,
        "payload_read_ms",
    )

    extraction = stats(
        success_df,
        "extraction_ms",
    )

    search = stats(
        success_df,
        "search_ms",
    )

    reconstruction = stats(
        success_df,
        "reconstruction_ms",
    )

    server_total = stats(
        success_df,
        "server_total_ms",
    )


    summary_rows.append({
        "concurrency":
            int(
                concurrency
            ),

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

        "archive_p50_ms":
            archive[
                "p50"
            ],

        "archive_p95_ms":
            archive[
                "p95"
            ],

        "payload_read_p50_ms":
            payload[
                "p50"
            ],

        "payload_read_p95_ms":
            payload[
                "p95"
            ],

        "extraction_p50_ms":
            extraction[
                "p50"
            ],

        "extraction_p95_ms":
            extraction[
                "p95"
            ],

        "search_p50_ms":
            search[
                "p50"
            ],

        "search_p95_ms":
            search[
                "p95"
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

        "server_total_max_ms":
            server_total[
                "max"
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
        "server total p50/p95/p99:",
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
        "/",
        round(
            server_total[
                "p99"
            ],
            3,
        ),
        "ms"
    )

    print(
        "extraction p50:",
        round(
            extraction[
                "p50"
            ],
            3,
        ),
        "ms"
    )

    print(
        "search p50:",
        round(
            search[
                "p50"
            ],
            3,
        ),
        "ms"
    )


# =========================================================
# Final aggregates
# =========================================================

request_df = pd.DataFrame(
    all_request_rows
)


concurrency_df = pd.DataFrame(
    summary_rows
)


expected_measured_requests = (
    REQUESTS_PER_LEVEL
    *
    len(
        CONCURRENCY_LEVELS
    )
)


if len(
    request_df
) != expected_measured_requests:

    raise RuntimeError(
        "Measured request count mismatch"
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
        ==
        0
    ).all()
)


health_after_response = get_json(
    HEALTH_URL,
    timeout=30,
)


if not health_after_response[
    "success"
]:

    raise RuntimeError(
        "Final health request failed"
    )


health_after = (
    health_after_response[
        "json"
    ]
)


rss_after_all = int(
    health_after[
        "rss_bytes"
    ]
)


# =========================================================
# Single-concurrency stage breakdown
# =========================================================

c1 = concurrency_df[
    concurrency_df[
        "concurrency"
    ]
    ==
    1
].iloc[0]


c1_total = float(
    c1[
        "server_total_p50_ms"
    ]
)


stage_breakdown_c1_p50 = {
    "archive_open_and_manifest_ms":
        float(
            c1[
                "archive_p50_ms"
            ]
        ),

    "payload_read_ms":
        float(
            c1[
                "payload_read_p50_ms"
            ]
        ),

    "raw_evidence_extraction_ms":
        float(
            c1[
                "extraction_p50_ms"
            ]
        ),

    "gallery_similarity_search_ms":
        float(
            c1[
                "search_p50_ms"
            ]
        ),

    "reconstruction_ms":
        float(
            c1[
                "reconstruction_p50_ms"
            ]
        ),

    "total_server_processing_ms":
        c1_total,
}


# =========================================================
# Save
# =========================================================

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
    "phase9e3_complete":
        True,

    "performance_scope":
        (
            "SERVER_SIDE_MATERIALIZED_PACKAGE_"
            "TO_PROVENANCE_RESULT"
        ),

    "server_side_end_to_end_package_processing":
        True,

    "network_package_upload_included":
        False,

    "pipeline": [
        "archive_open_and_manifest_parse",
        "payload_read",
        "raw_identity_neutral_evidence_extraction",
        "60_project_gallery_similarity_search",
        "top10_parent_retrieval",
        "multi_parent_reconstruction",
        "dependency_graph_refinement",
        "json_result",
    ],

    "correctness": {
        "parent_set_queries":
            int(
                parent_matches
            ),

        "candidate_top10_queries":
            int(
                candidate_matches
            ),

        "selected_subset_queries":
            int(
                subset_matches
            ),

        "k_queries":
            int(
                k_matches
            ),

        "component_assignments":
            int(
                component_matches
            ),

        "fully_identical_queries":
            int(
                fully_identical
            ),

        "mismatches":
            int(
                EXPECTED_QUERIES
                -
                fully_identical
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
            expected_measured_requests,

        "warmup_requests":
            WARMUP_REQUESTS,

        "random_seed":
            RANDOM_SEED,

        "server":
            "FastAPI/Uvicorn single process",

        "package_source":
            "local server filesystem",

        "gallery_projects":
            60,
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
                    int(
                        value
                    )
                    if key
                    in {
                        "concurrency",
                        "requests",
                        "success_count",
                        "failure_count",
                    }
                    else
                    float(
                        value
                    )
                )

            for key, value
            in row.items()
        }

        for row
        in summary_rows
    },

    "single_request_stage_breakdown_p50":
        stage_breakdown_c1_p50,

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
            "The benchmark includes server-side "
            "processing from a local materialized "
            "provenance-query ZIP through raw evidence "
            "extraction, gallery similarity search and "
            "frozen provenance reconstruction. "
            "It does not include network transfer or "
            "client upload time and the archive is not "
            "claimed to be a runnable game MOD."
        ),

    "goals_met":
        bool(
            correctness_passed
            and
            all_zero_failures
            and
            len(
                request_df
            )
            ==
            expected_measured_requests
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
    "PHASE 9E-3 FINAL RESULT"
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
            "archive_p50_ms",
            "payload_read_p50_ms",
            "extraction_p50_ms",
            "search_p50_ms",
            "reconstruction_p50_ms",
            "server_total_p50_ms",
            "server_total_p95_ms",
            "server_total_p99_ms",
        ]
    ].to_string(
        index=False
    )
)


print()

print(
    "Correctness:",
    fully_identical,
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
    "req/s @ concurrency",
    int(
        best_row[
            "concurrency"
        ]
    )
)

print(
    "All zero failures:",
    all_zero_failures
)

print(
    "GOALS MET:",
    summary[
        "goals_met"
    ]
)

print()

print(
    "Summary:",
    OUTPUT_SUMMARY_JSON
)