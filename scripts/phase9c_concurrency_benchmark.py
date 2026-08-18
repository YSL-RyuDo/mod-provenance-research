import json
import math
import os
import platform
import statistics
import threading
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

PHASE9B_SUMMARY_JSON = Path(
    "results/phase9b_server_correctness_summary.json"
)


# =========================================================
# Outputs
# =========================================================

OUTPUT_REQUESTS_CSV = Path(
    "results/phase9c_concurrency_request_results.csv"
)

OUTPUT_CONCURRENCY_CSV = Path(
    "results/phase9c_concurrency_summary.csv"
)

OUTPUT_SUMMARY_JSON = Path(
    "results/phase9c_concurrency_benchmark_summary.json"
)


# =========================================================
# Benchmark protocol
# =========================================================

CONCURRENCY_LEVELS = [
    1,
    4,
    8,
    16,
    32,
]

REQUESTS_PER_LEVEL = 1000

WARMUP_REQUESTS = 100

REQUEST_TIMEOUT_SECONDS = 60

RANDOM_SEED = 20260813

EXPECTED_QUERY_COUNT = 360

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


def percentile(values, q):

    values = np.asarray(
        values,
        dtype=np.float64,
    )

    return float(
        np.percentile(
            values,
            q,
        )
    )


def http_get_json(
    url,
    timeout_seconds=60,
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
            timeout=timeout_seconds,
        ) as response:

            body = response.read()

            end = time.perf_counter_ns()

            return {
                "success":
                    True,

                "status_code":
                    int(
                        response.status
                    ),

                "client_latency_ms":
                    (
                        end - start
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

    except urllib.error.HTTPError as error:

        end = time.perf_counter_ns()

        body = error.read().decode(
            "utf-8",
            errors="replace",
        )

        return {
            "success":
                False,

            "status_code":
                int(
                    error.code
                ),

            "client_latency_ms":
                (
                    end - start
                )
                / 1_000_000.0,

            "json":
                None,

            "error":
                body,
        }

    except Exception as error:

        end = time.perf_counter_ns()

        return {
            "success":
                False,

            "status_code":
                0,

            "client_latency_ms":
                (
                    end - start
                )
                / 1_000_000.0,

            "json":
                None,

            "error":
                repr(
                    error
                ),
        }


def get_health():

    result = http_get_json(
        HEALTH_URL,
        timeout_seconds=10,
    )

    if not result[
        "success"
    ]:

        raise RuntimeError(
            "Server health request failed: "
            + result[
                "error"
            ]
        )

    return result[
        "json"
    ]


# =========================================================
# Load benchmark inputs
# =========================================================

if not FINAL_QUERY_CSV.exists():

    raise FileNotFoundError(
        FINAL_QUERY_CSV
    )


if not PHASE9B_SUMMARY_JSON.exists():

    raise FileNotFoundError(
        PHASE9B_SUMMARY_JSON
    )


query_df = pd.read_csv(
    FINAL_QUERY_CSV
)


phase9b = json.loads(
    PHASE9B_SUMMARY_JSON.read_text(
        encoding="utf-8"
    )
)


if len(
    query_df
) != EXPECTED_QUERY_COUNT:

    raise RuntimeError(
        f"Expected {EXPECTED_QUERY_COUNT} queries, "
        f"got {len(query_df)}"
    )


if not phase9b.get(
    "correctness_passed",
    False,
):

    raise RuntimeError(
        "Phase 9B correctness did not pass"
    )


if not phase9b.get(
    "ready_for_phase9c_performance_benchmark",
    False,
):

    raise RuntimeError(
        "Phase 9B did not approve Phase 9C"
    )


query_ids = (
    query_df[
        "query_id"
    ]
    .astype(str)
    .tolist()
)


# =========================================================
# Health check
# =========================================================

print(
    "======================================"
)

print(
    "Phase 9C - Concurrent Server Benchmark"
)

print(
    "======================================"
)

print()


health_before_all = get_health()


if health_before_all.get(
    "status"
) != "ok":

    raise RuntimeError(
        "Server status is not ok"
    )


if not health_before_all.get(
    "method_frozen",
    False,
):

    raise RuntimeError(
        "Server method is not frozen"
    )


print(
    "Server health: PASS"
)

print(
    "Initial RSS:",
    health_before_all[
        "rss_bytes"
    ],
    "bytes",
)


# =========================================================
# Host system information
# =========================================================

logical_cpus = psutil.cpu_count(
    logical=True
)

physical_cpus = psutil.cpu_count(
    logical=False
)

memory_info = psutil.virtual_memory()


host_info = {
    "platform":
        platform.platform(),

    "python_version":
        platform.python_version(),

    "processor":
        platform.processor(),

    "physical_cpu_cores":
        physical_cpus,

    "logical_cpu_cores":
        logical_cpus,

    "total_system_memory_bytes":
        int(
            memory_info.total
        ),
}


# =========================================================
# Warm-up
# =========================================================

print()

print(
    "Warm-up:",
    WARMUP_REQUESTS,
    "requests"
)


rng = np.random.default_rng(
    RANDOM_SEED
)


warmup_ids = rng.choice(
    np.array(
        query_ids,
        dtype=object,
    ),
    size=WARMUP_REQUESTS,
    replace=True,
)


warmup_failures = 0


for index, query_id in enumerate(
    warmup_ids,
    start=1,
):

    result = http_get_json(
        REGRESSION_URL_PREFIX
        + str(
            query_id
        ),
        timeout_seconds=REQUEST_TIMEOUT_SECONDS,
    )

    if not result[
        "success"
    ]:

        warmup_failures += 1


if warmup_failures != 0:

    raise RuntimeError(
        f"Warm-up had {warmup_failures} failures"
    )


print(
    "Warm-up: PASS"
)


# =========================================================
# Request worker
# =========================================================

def execute_request(
    request_index,
    query_id,
    concurrency,
):

    result = http_get_json(
        REGRESSION_URL_PREFIX
        + str(
            query_id
        ),
        timeout_seconds=REQUEST_TIMEOUT_SECONDS,
    )


    server_internal_ms = np.nan

    predicted_k = None


    if (
        result[
            "success"
        ]
        and
        result[
            "json"
        ]
        is not None
    ):

        response_json = result[
            "json"
        ]


        latency_block = (
            response_json.get(
                "latency_ms",
                {}
            )
        )


        try:

            server_internal_ms = float(
                latency_block.get(
                    "total",
                    np.nan,
                )
            )

        except Exception:

            server_internal_ms = np.nan


        try:

            predicted_k = int(
                response_json.get(
                    "predicted_k"
                )
            )

        except Exception:

            predicted_k = None


    return {
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
                result[
                    "success"
                ]
            ),

        "status_code":
            int(
                result[
                    "status_code"
                ]
            ),

        "client_latency_ms":
            float(
                result[
                    "client_latency_ms"
                ]
            ),

        "server_internal_total_ms":
            float(
                server_internal_ms
            ),

        "predicted_k":
            predicted_k,

        "error":
            result[
                "error"
            ],
    }


# =========================================================
# Benchmark loop
# =========================================================

all_request_rows = []

concurrency_rows = []


for concurrency in (
    CONCURRENCY_LEVELS
):

    print()

    print(
        "--------------------------------------"
    )

    print(
        "Concurrency:",
        concurrency
    )

    print(
        "Requests:",
        REQUESTS_PER_LEVEL
    )

    print(
        "--------------------------------------"
    )


    health_before = get_health()


    rss_before = int(
        health_before[
            "rss_bytes"
        ]
    )


    request_query_ids = rng.choice(
        np.array(
            query_ids,
            dtype=object,
        ),
        size=REQUESTS_PER_LEVEL,
        replace=True,
    )


    level_rows = []


    wall_start = time.perf_counter()


    with ThreadPoolExecutor(
        max_workers=concurrency
    ) as executor:

        futures = [
            executor.submit(
                execute_request,
                request_index,
                query_id,
                concurrency,
            )

            for (
                request_index,
                query_id
            )
            in enumerate(
                request_query_ids,
                start=1,
            )
        ]


        completed = 0


        for future in as_completed(
            futures
        ):

            row = future.result()

            level_rows.append(
                row
            )

            completed += 1


            if (
                completed == 1
                or
                completed % 200 == 0
            ):

                print(
                    "completed",
                    completed,
                    "/",
                    REQUESTS_PER_LEVEL,
                )


    wall_end = time.perf_counter()


    wall_seconds = float(
        wall_end
        -
        wall_start
    )


    health_after = get_health()


    rss_after = int(
        health_after[
            "rss_bytes"
        ]
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


    success_rate = float(
        success_count
        /
        REQUESTS_PER_LEVEL
    )


    throughput = float(
        success_count
        /
        wall_seconds
    )


    if success_count > 0:

        client_latencies = (
            success_df[
                "client_latency_ms"
            ]
            .astype(float)
            .to_numpy()
        )


        internal_latencies = (
            success_df[
                "server_internal_total_ms"
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


        client_mean = float(
            np.mean(
                client_latencies
            )
        )


        client_p50 = percentile(
            client_latencies,
            50,
        )


        client_p95 = percentile(
            client_latencies,
            95,
        )


        client_p99 = percentile(
            client_latencies,
            99,
        )


        client_max = float(
            np.max(
                client_latencies
            )
        )


        if len(
            internal_latencies
        ) > 0:

            internal_mean = float(
                np.mean(
                    internal_latencies
                )
            )


            internal_p50 = percentile(
                internal_latencies,
                50,
            )


            internal_p95 = percentile(
                internal_latencies,
                95,
            )


            internal_p99 = percentile(
                internal_latencies,
                99,
            )

        else:

            internal_mean = None
            internal_p50 = None
            internal_p95 = None
            internal_p99 = None


    else:

        client_mean = None
        client_p50 = None
        client_p95 = None
        client_p99 = None
        client_max = None

        internal_mean = None
        internal_p50 = None
        internal_p95 = None
        internal_p99 = None


    summary_row = {
        "concurrency":
            int(
                concurrency
            ),

        "requests":
            int(
                REQUESTS_PER_LEVEL
            ),

        "success_count":
            success_count,

        "failure_count":
            failure_count,

        "success_rate":
            success_rate,

        "wall_seconds":
            wall_seconds,

        "throughput_requests_per_second":
            throughput,

        "client_latency_mean_ms":
            client_mean,

        "client_latency_p50_ms":
            client_p50,

        "client_latency_p95_ms":
            client_p95,

        "client_latency_p99_ms":
            client_p99,

        "client_latency_max_ms":
            client_max,

        "server_internal_mean_ms":
            internal_mean,

        "server_internal_p50_ms":
            internal_p50,

        "server_internal_p95_ms":
            internal_p95,

        "server_internal_p99_ms":
            internal_p99,

        "rss_before_bytes":
            rss_before,

        "rss_after_bytes":
            rss_after,

        "rss_delta_bytes":
            int(
                rss_after
                -
                rss_before
            ),
    }


    concurrency_rows.append(
        summary_row
    )


    all_request_rows.extend(
        level_rows
    )


    print()

    print(
        "success:",
        success_count,
        "/",
        REQUESTS_PER_LEVEL,
    )

    print(
        "throughput:",
        round(
            throughput,
            3,
        ),
        "req/s",
    )

    print(
        "client p50/p95/p99:",
        round(
            client_p50,
            3,
        )
        if client_p50 is not None
        else None,
        "/",
        round(
            client_p95,
            3,
        )
        if client_p95 is not None
        else None,
        "/",
        round(
            client_p99,
            3,
        )
        if client_p99 is not None
        else None,
        "ms",
    )

    print(
        "server internal p50/p95:",
        round(
            internal_p50,
            3,
        )
        if internal_p50 is not None
        else None,
        "/",
        round(
            internal_p95,
            3,
        )
        if internal_p95 is not None
        else None,
        "ms",
    )

    print(
        "RSS delta:",
        rss_after - rss_before,
        "bytes",
    )


# =========================================================
# Final DataFrames
# =========================================================

request_df = pd.DataFrame(
    all_request_rows
)


concurrency_df = pd.DataFrame(
    concurrency_rows
)


expected_total_requests = (
    REQUESTS_PER_LEVEL
    *
    len(
        CONCURRENCY_LEVELS
    )
)


if len(
    request_df
) != expected_total_requests:

    raise RuntimeError(
        "Unexpected total request count"
    )


# =========================================================
# Stability / saturation diagnostics
# =========================================================

best_throughput_row = (
    concurrency_df.loc[
        concurrency_df[
            "throughput_requests_per_second"
        ].idxmax()
    ]
)


best_throughput_concurrency = int(
    best_throughput_row[
        "concurrency"
    ]
)


best_throughput = float(
    best_throughput_row[
        "throughput_requests_per_second"
    ]
)


all_successful = bool(
    (
        concurrency_df[
            "failure_count"
        ]
        ==
        0
    ).all()
)


highest_concurrency_row = (
    concurrency_df[
        concurrency_df[
            "concurrency"
        ]
        ==
        max(
            CONCURRENCY_LEVELS
        )
    ].iloc[0]
)


highest_concurrency_success_rate = float(
    highest_concurrency_row[
        "success_rate"
    ]
)


# =========================================================
# Save
# =========================================================

OUTPUT_REQUESTS_CSV.parent.mkdir(
    parents=True,
    exist_ok=True,
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


health_after_all = get_health()


summary = {
    "concurrency_benchmark_complete":
        True,

    "performance_scope":
        (
            "ONLINE_RECONSTRUCTION_FROM_"
            "PRECOMPUTED_PARENT_SCORES"
        ),

    "end_to_end_mod_analysis":
        False,

    "phase9b_correctness_required":
        True,

    "phase9b_correctness_passed":
        True,

    "server_method_frozen":
        True,

    "benchmark_protocol": {
        "concurrency_levels":
            CONCURRENCY_LEVELS,

        "requests_per_level":
            REQUESTS_PER_LEVEL,

        "total_measured_requests":
            expected_total_requests,

        "warmup_requests":
            WARMUP_REQUESTS,

        "request_timeout_seconds":
            REQUEST_TIMEOUT_SECONDS,

        "random_seed":
            RANDOM_SEED,

        "client":
            (
                "Python urllib + "
                "ThreadPoolExecutor"
            ),

        "server":
            (
                "FastAPI / Uvicorn "
                "single process"
            ),
    },

    "host_system":
        host_info,

    "server_health_before": {
        "rss_bytes":
            int(
                health_before_all[
                    "rss_bytes"
                ]
            ),

        "alpha":
            float(
                health_before_all[
                    "alpha"
                ]
            ),

        "lambda":
            float(
                health_before_all[
                    "lambda"
                ]
            ),

        "candidate_pool_M":
            int(
                health_before_all[
                    "candidate_pool_M"
                ]
            ),

        "graph_beta":
            float(
                health_before_all[
                    "graph_beta"
                ]
            ),

        "boundary_top_r":
            int(
                health_before_all[
                    "boundary_top_r"
                ]
            ),

        "Kmax":
            int(
                health_before_all[
                    "Kmax"
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
                    None
                    if pd.isna(
                        value
                    )
                    else
                    (
                        int(value)
                        if key in {
                            "concurrency",
                            "requests",
                            "success_count",
                            "failure_count",
                            "rss_before_bytes",
                            "rss_after_bytes",
                            "rss_delta_bytes",
                        }
                        else float(
                            value
                        )
                    )
                )

            for key, value
            in row.items()
        }

        for row
        in concurrency_rows
    },

    "aggregate": {
        "all_levels_zero_failures":
            all_successful,

        "best_throughput_concurrency":
            best_throughput_concurrency,

        "best_throughput_requests_per_second":
            best_throughput,

        "highest_tested_concurrency":
            max(
                CONCURRENCY_LEVELS
            ),

        "highest_concurrency_success_rate":
            highest_concurrency_success_rate,

        "server_rss_after_all_bytes":
            int(
                health_after_all[
                    "rss_bytes"
                ]
            ),

        "server_rss_change_whole_benchmark_bytes":
            int(
                health_after_all[
                    "rss_bytes"
                ]
                -
                health_before_all[
                    "rss_bytes"
                ]
            ),
    },

    "interpretation_warning":
        (
            "This benchmark measures online "
            "parent retrieval/reconstruction from "
            "already-computed component-parent "
            "scores through the HTTP service. "
            "It excludes archive parsing, bytecode/"
            "resource/image evidence extraction, "
            "and gallery similarity computation. "
            "Do not label these numbers as "
            "end-to-end MOD analysis latency."
        ),

    "ready_for_end_to_end_phase":
        bool(
            all_successful
            and
            highest_concurrency_success_rate
            == 1.0
        ),

    "goals_met":
        bool(
            len(
                concurrency_df
            )
            ==
            len(
                CONCURRENCY_LEVELS
            )

            and

            len(
                request_df
            )
            ==
            expected_total_requests
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
    "PHASE 9C FINAL RESULT"
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
            "client_latency_p50_ms",
            "client_latency_p95_ms",
            "client_latency_p99_ms",
            "server_internal_p50_ms",
            "server_internal_p95_ms",
            "rss_after_bytes",
        ]
    ].to_string(
        index=False
    )
)


print()

print(
    "Best throughput:",
    best_throughput,
    "req/s @ concurrency",
    best_throughput_concurrency,
)


print(
    "All levels zero failures:",
    all_successful
)


print(
    "Ready for end-to-end phase:",
    summary[
        "ready_for_end_to_end_phase"
    ]
)


print()

print(
    "Requests:",
    OUTPUT_REQUESTS_CSV
)

print(
    "Concurrency summary:",
    OUTPUT_CONCURRENCY_CSV
)

print(
    "JSON summary:",
    OUTPUT_SUMMARY_JSON
)