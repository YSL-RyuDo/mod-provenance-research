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
# Configuration
# =========================================================

BASE_URL = "http://127.0.0.1:8000"

HEALTH_URL = (
    BASE_URL
    + "/health"
)

ANALYZE_PREFIX = (
    BASE_URL
    + "/analyze-scale/"
)


GALLERY_SCALES = [
    20,
    40,
    60,
    80,
    100,
]


# Sequential latency + modest concurrent throughput.
CONCURRENCY_LEVELS = [
    1,
    4,
]


REQUESTS_PER_SETTING = 200

WARMUP_PER_SCALE = 20

RANDOM_SEED = 20260813

TIMEOUT_SECONDS = 180


# =========================================================
# Inputs
# =========================================================

FINAL_QUERY_CSV = Path(
    "results/phase7h_final_query_predictions.csv"
)

PHASE9D_SUMMARY_JSON = Path(
    "results/phase9d_evidence_pipeline_summary.json"
)

PHASE9E3_SUMMARY_JSON = Path(
    "results/phase9e3_end_to_end_summary.json"
)


# =========================================================
# Outputs
# =========================================================

OUTPUT_REQUESTS_CSV = Path(
    "results/phase9f_gallery_scalability_requests.csv"
)

OUTPUT_SETTINGS_CSV = Path(
    "results/phase9f_gallery_scalability_settings.csv"
)

OUTPUT_SCALE_CSV = Path(
    "results/phase9f_gallery_scalability_summary.csv"
)

OUTPUT_SUMMARY_JSON = Path(
    "results/phase9f_gallery_scalability_summary.json"
)


# =========================================================
# Helpers
# =========================================================

def percentile(
    values,
    q,
):

    values = np.asarray(
        values,
        dtype=np.float64,
    )


    if len(
        values
    ) == 0:

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
    }


# =========================================================
# Validate previous phases
# =========================================================

for path in [
    FINAL_QUERY_CSV,
    PHASE9D_SUMMARY_JSON,
    PHASE9E3_SUMMARY_JSON,
]:

    if not path.exists():

        raise FileNotFoundError(
            path
        )


phase9d = json.loads(
    PHASE9D_SUMMARY_JSON.read_text(
        encoding="utf-8"
    )
)


phase9e3 = json.loads(
    PHASE9E3_SUMMARY_JSON.read_text(
        encoding="utf-8"
    )
)


if not phase9d.get(
    "goals_met",
    False,
):

    raise RuntimeError(
        "Phase 9D did not pass"
    )


if not phase9e3.get(
    "goals_met",
    False,
):

    raise RuntimeError(
        "Phase 9E-3 did not pass"
    )


query_df = pd.read_csv(
    FINAL_QUERY_CSV,
    dtype=str,
    keep_default_na=False,
)


if len(
    query_df
) != 360:

    raise RuntimeError(
        "Expected 360 TEST queries"
    )


query_ids = sorted(
    query_df[
        "query_id"
    ].astype(str).tolist()
)


# =========================================================
# Server health
# =========================================================

print(
    "======================================"
)

print(
    "Phase 9F - Gallery Scalability Benchmark"
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
        "Phase 9F server unavailable"
    )


health = (
    health_response[
        "json"
    ]
)


if health.get(
    "phase"
) != "9F":

    raise RuntimeError(
        "Wrong server phase"
    )


if health.get(
    "gallery_scales"
) != GALLERY_SCALES:

    raise RuntimeError(
        "Gallery scale configuration mismatch"
    )


if not health.get(
    "scale60_matches_phase9d_project_set",
    False,
):

    raise RuntimeError(
        "Scale 60 is not Phase 9D TEST gallery"
    )


print(
    "Server health: PASS"
)

print(
    "Real projects:",
    health[
        "real_projects_available"
    ]
)


rss_initial = int(
    health[
        "rss_bytes"
    ]
)


# =========================================================
# Deterministic random generator
# =========================================================

rng = np.random.default_rng(
    RANDOM_SEED
)


# =========================================================
# Warm-up every gallery scale
# =========================================================

print()

print(
    "Warm-up"
)


for scale in GALLERY_SCALES:

    print(
        "scale",
        scale
    )


    warmup_ids = rng.choice(
        np.asarray(
            query_ids,
            dtype=object,
        ),
        size=WARMUP_PER_SCALE,
        replace=True,
    )


    for query_id in warmup_ids:

        response = get_json(
            (
                ANALYZE_PREFIX
                +
                str(
                    scale
                )
                +
                "/"
                +
                str(
                    query_id
                )
            )
        )


        if not response[
            "success"
        ]:

            raise RuntimeError(
                f"Warm-up failure at scale {scale}"
            )


print(
    "Warm-up: PASS"
)


# =========================================================
# Worker
# =========================================================

def benchmark_request(
    scale,
    concurrency,
    request_index,
    query_id,
):

    response = get_json(
        (
            ANALYZE_PREFIX
            +
            str(
                scale
            )
            +
            "/"
            +
            str(
                query_id
            )
        )
    )


    row = {
        "gallery_scale_projects":
            int(
                scale
            ),

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

        "gallery_components":
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

        phase9f = (
            response[
                "json"
            ][
                "phase9f"
            ]
        )


        latency = (
            phase9f[
                "latency_ms"
            ]
        )


        row[
            "gallery_components"
        ] = int(
            phase9f[
                "gallery_components"
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
                "total"
            ]
        )


    return row


# =========================================================
# Main benchmark
# =========================================================

all_request_rows = []
setting_rows = []


for scale in GALLERY_SCALES:

    for concurrency in CONCURRENCY_LEVELS:

        print()

        print(
            "--------------------------------------"
        )

        print(
            "Gallery scale:",
            scale
        )

        print(
            "Concurrency:",
            concurrency
        )

        print(
            "Requests:",
            REQUESTS_PER_SETTING
        )

        print(
            "--------------------------------------"
        )


        health_before_response = get_json(
            HEALTH_URL,
            timeout=30,
        )


        if not health_before_response[
            "success"
        ]:

            raise RuntimeError(
                "Health check failed before setting"
            )


        rss_before = int(
            health_before_response[
                "json"
            ][
                "rss_bytes"
            ]
        )


        selected_ids = rng.choice(
            np.asarray(
                query_ids,
                dtype=object,
            ),
            size=REQUESTS_PER_SETTING,
            replace=True,
        )


        wall_start = (
            time.perf_counter()
        )


        level_rows = []


        with ThreadPoolExecutor(
            max_workers=concurrency
        ) as executor:

            futures = [
                executor.submit(
                    benchmark_request,
                    scale,
                    concurrency,
                    request_index,
                    query_id,
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
                        REQUESTS_PER_SETTING,
                    )


        wall_end = (
            time.perf_counter()
        )


        health_after_response = get_json(
            HEALTH_URL,
            timeout=30,
        )


        if not health_after_response[
            "success"
        ]:

            raise RuntimeError(
                "Health check failed after setting"
            )


        rss_after = int(
            health_after_response[
                "json"
            ][
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


        search = stats(
            success_df,
            "search_ms",
        )


        reconstruction = stats(
            success_df,
            "reconstruction_ms",
        )


        total = stats(
            success_df,
            "server_total_ms",
        )


        gallery_component_values = (
            success_df[
                "gallery_components"
            ]
            .dropna()
            .astype(int)
            .unique()
        )


        if len(
            gallery_component_values
        ) != 1:

            raise RuntimeError(
                f"Scale {scale}: inconsistent "
                "gallery component count"
            )


        gallery_components = int(
            gallery_component_values[
                0
            ]
        )


        setting_rows.append({
            "gallery_scale_projects":
                int(
                    scale
                ),

            "gallery_components":
                gallery_components,

            "concurrency":
                int(
                    concurrency
                ),

            "requests":
                REQUESTS_PER_SETTING,

            "success_count":
                success_count,

            "failure_count":
                failure_count,

            "success_rate":
                float(
                    success_count
                    /
                    REQUESTS_PER_SETTING
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

            "reconstruction_p50_ms":
                reconstruction[
                    "p50"
                ],

            "reconstruction_p95_ms":
                reconstruction[
                    "p95"
                ],

            "server_total_mean_ms":
                total[
                    "mean"
                ],

            "server_total_p50_ms":
                total[
                    "p50"
                ],

            "server_total_p95_ms":
                total[
                    "p95"
                ],

            "server_total_p99_ms":
                total[
                    "p99"
                ],

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
        })


        all_request_rows.extend(
            level_rows
        )


        print(
            "Success:",
            success_count,
            "/",
            REQUESTS_PER_SETTING
        )


        print(
            "Gallery components:",
            gallery_components
        )


        print(
            "Throughput:",
            round(
                throughput,
                3,
            ),
            "req/s"
        )


        print(
            "Search p50/p95:",
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


        print(
            "Total p50/p95:",
            round(
                total[
                    "p50"
                ],
                3,
            ),
            "/",
            round(
                total[
                    "p95"
                ],
                3,
            ),
            "ms"
        )


# =========================================================
# DataFrames
# =========================================================

request_df = pd.DataFrame(
    all_request_rows
)


settings_df = pd.DataFrame(
    setting_rows
)


expected_requests = (
    len(
        GALLERY_SCALES
    )
    *
    len(
        CONCURRENCY_LEVELS
    )
    *
    REQUESTS_PER_SETTING
)


if len(
    request_df
) != expected_requests:

    raise RuntimeError(
        "Measured request count mismatch"
    )


# =========================================================
# Produce one publication-oriented row per gallery scale
#
# Latency:
#   concurrency 1
#
# Throughput:
#   concurrency 4
# =========================================================

scale_rows = []


for scale in GALLERY_SCALES:

    c1 = settings_df[
        (
            settings_df[
                "gallery_scale_projects"
            ]
            ==
            scale
        )
        &
        (
            settings_df[
                "concurrency"
            ]
            ==
            1
        )
    ].iloc[0]


    c4 = settings_df[
        (
            settings_df[
                "gallery_scale_projects"
            ]
            ==
            scale
        )
        &
        (
            settings_df[
                "concurrency"
            ]
            ==
            4
        )
    ].iloc[0]


    scale_rows.append({
        "gallery_projects":
            int(
                scale
            ),

        "gallery_components":
            int(
                c1[
                    "gallery_components"
                ]
            ),

        "sequential_search_p50_ms":
            float(
                c1[
                    "search_p50_ms"
                ]
            ),

        "sequential_search_p95_ms":
            float(
                c1[
                    "search_p95_ms"
                ]
            ),

        "sequential_total_p50_ms":
            float(
                c1[
                    "server_total_p50_ms"
                ]
            ),

        "sequential_total_p95_ms":
            float(
                c1[
                    "server_total_p95_ms"
                ]
            ),

        "sequential_reconstruction_p50_ms":
            float(
                c1[
                    "reconstruction_p50_ms"
                ]
            ),

        "concurrency4_throughput_req_s":
            float(
                c4[
                    "throughput_requests_per_second"
                ]
            ),

        "concurrency4_client_p50_ms":
            float(
                c4[
                    "client_p50_ms"
                ]
            ),

        "concurrency4_client_p95_ms":
            float(
                c4[
                    "client_p95_ms"
                ]
            ),

        "rss_after_scale_c4_bytes":
            int(
                c4[
                    "rss_after_bytes"
                ]
            ),
    })


scale_df = pd.DataFrame(
    scale_rows
)


# =========================================================
# Descriptive scale growth
# =========================================================

base20 = scale_df[
    scale_df[
        "gallery_projects"
    ]
    ==
    20
].iloc[0]


base_search = float(
    base20[
        "sequential_search_p50_ms"
    ]
)


base_total = float(
    base20[
        "sequential_total_p50_ms"
    ]
)


for index in scale_df.index:

    scale_df.loc[
        index,
        "search_p50_ratio_vs_20"
    ] = (
        float(
            scale_df.loc[
                index,
                "sequential_search_p50_ms"
            ]
        )
        /
        base_search
    )


    scale_df.loc[
        index,
        "total_p50_ratio_vs_20"
    ] = (
        float(
            scale_df.loc[
                index,
                "sequential_total_p50_ms"
            ]
        )
        /
        base_total
    )


# =========================================================
# Final health
# =========================================================

health_after = get_json(
    HEALTH_URL,
    timeout=30,
)


if not health_after[
    "success"
]:

    raise RuntimeError(
        "Final health check failed"
    )


rss_final = int(
    health_after[
        "json"
    ][
        "rss_bytes"
    ]
)


all_zero_failures = bool(
    (
        settings_df[
            "failure_count"
        ]
        ==
        0
    ).all()
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


settings_df.to_csv(
    OUTPUT_SETTINGS_CSV,
    index=False,
    encoding="utf-8-sig",
)


scale_df.to_csv(
    OUTPUT_SCALE_CSV,
    index=False,
    encoding="utf-8-sig",
)


summary = {
    "phase9f_complete":
        True,

    "performance_scope":
        "REAL_PROJECT_GALLERY_SIZE_SCALABILITY",

    "accuracy_re_evaluated":
        False,

    "parameters_retuned":
        False,

    "query_predictions_used_as_paper_accuracy":
        False,

    "gallery_design": {
        "scales_projects":
            GALLERY_SCALES,

        "real_projects_total":
            100,

        "test_projects":
            60,

        "calibration_projects":
            40,

        "ordering":
            (
                "sorted TEST projects first, "
                "followed by sorted CAL projects"
            ),

        "scale_60_matches_phase9d_test_gallery":
            True,

        "synthetic_gallery_duplication":
            False,
    },

    "benchmark_protocol": {
        "latency_concurrency":
            1,

        "throughput_concurrency":
            4,

        "requests_per_setting":
            REQUESTS_PER_SETTING,

        "warmup_per_scale":
            WARMUP_PER_SCALE,

        "total_measured_requests":
            expected_requests,

        "random_seed":
            RANDOM_SEED,

        "server":
            "FastAPI/Uvicorn single process",

        "input":
            (
                "pre-extracted identity-neutral "
                "TEST query evidence"
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

    "results_by_scale": {
        str(
            int(
                row[
                    "gallery_projects"
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
                        "gallery_projects",
                        "gallery_components",
                        "rss_after_scale_c4_bytes",
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
        in scale_rows
    },

    "aggregate": {
        "all_settings_zero_failures":
            all_zero_failures,

        "rss_initial_bytes":
            rss_initial,

        "rss_final_bytes":
            rss_final,

        "rss_change_bytes":
            int(
                rss_final
                -
                rss_initial
            ),

        "scale20_to_scale100": {
            "gallery_component_ratio":
                float(
                    scale_df.iloc[-1][
                        "gallery_components"
                    ]
                    /
                    scale_df.iloc[0][
                        "gallery_components"
                    ]
                ),

            "search_p50_ratio":
                float(
                    scale_df.iloc[-1][
                        "search_p50_ratio_vs_20"
                    ]
                ),

            "total_p50_ratio":
                float(
                    scale_df.iloc[-1][
                        "total_p50_ratio_vs_20"
                    ]
                ),
        },
    },

    "interpretation_warning":
        (
            "Phase 9F is a scalability-only system "
            "sensitivity analysis. Gallery size is "
            "changed using real TEST and calibration "
            "projects. Accuracy is neither evaluated "
            "nor retuned at these alternate gallery "
            "sizes. The input begins from already-"
            "extracted identity-neutral query evidence."
        ),

    "goals_met":
        bool(
            all_zero_failures
            and
            len(
                scale_df
            )
            ==
            len(
                GALLERY_SCALES
            )
            and
            len(
                request_df
            )
            ==
            expected_requests
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
    "PHASE 9F FINAL RESULT"
)

print(
    "======================================"
)


print(
    scale_df[
        [
            "gallery_projects",
            "gallery_components",
            "sequential_search_p50_ms",
            "sequential_search_p95_ms",
            "sequential_total_p50_ms",
            "sequential_total_p95_ms",
            "concurrency4_throughput_req_s",
            "rss_after_scale_c4_bytes",
            "search_p50_ratio_vs_20",
        ]
    ].to_string(
        index=False
    )
)


print()

print(
    "All settings zero failures:",
    all_zero_failures
)

print(
    "20→100 search p50 ratio:",
    summary[
        "aggregate"
    ][
        "scale20_to_scale100"
    ][
        "search_p50_ratio"
    ]
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