import os
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import psutil

from fastapi import FastAPI, HTTPException

from server.phase9a_server import (
    AnalyzeRequest,
    ComponentInput,
    GraphEdgeInput,
    ParentScore,
    analyze_internal,
)


# =========================================================
# Paths
# =========================================================

ROOT = Path(__file__).resolve().parent.parent

GALLERY_EVIDENCE_CSV = (
    ROOT
    / "results"
    / "phase7b_gallery_identity_neutral_evidence.csv"
)

QUERY_EVIDENCE_CSV = (
    ROOT
    / "results"
    / "phase7b_query_identity_neutral_evidence.csv"
)

FINAL_QUERY_CSV = (
    ROOT
    / "results"
    / "phase7h_final_query_predictions.csv"
)

STRESS_GRAPH_CSV = (
    ROOT
    / "results"
    / "phase6l_graph_connected_stress_public.csv"
)


# =========================================================
# Constants
# =========================================================

TEST_GALLERY_SPLITS = {
    "TEST_KNOWN",
    "TEST_BACKGROUND",
}

EXPECTED_TEST_GALLERY_PROJECTS = 60

MISSING_PARENT_DISTANCE = 1.0

POPCOUNT8 = np.array(
    [
        bin(value).count("1")
        for value in range(256)
    ],
    dtype=np.uint8,
)


# =========================================================
# Parsing helpers
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


def parse_hex128_optional(value):

    text = clean_text(value)

    if not text:
        return None

    if len(text) != 32:
        raise ValueError(
            f"Expected 128-bit hex, got {text!r}"
        )

    integer = int(
        text,
        16,
    )

    return (
        np.uint64(
            integer >> 64
        ),
        np.uint64(
            integer
            & ((1 << 64) - 1)
        ),
    )


def parse_hex64(value):

    text = clean_text(value)

    if len(text) != 16:
        raise ValueError(
            f"Expected 64-bit hex, got {text!r}"
        )

    return np.uint64(
        int(
            text,
            16,
        )
    )


def parse_hist16(value):

    text = clean_text(value)

    parts = [
        item.strip()
        for item in text.split(",")
    ]

    if len(parts) != 16:
        raise ValueError(
            f"Expected 16 histogram bins, "
            f"got {len(parts)}"
        )

    return np.array(
        [
            int(item)
            for item in parts
        ],
        dtype=np.float32,
    )


# =========================================================
# Distance helpers
# =========================================================

def hamming128_array(
    highs,
    lows,
    query_high,
    query_low,
):

    xor_high = np.bitwise_xor(
        highs,
        query_high,
    )

    xor_low = np.bitwise_xor(
        lows,
        query_low,
    )

    high_bytes = (
        xor_high
        .view(np.uint8)
        .reshape(-1, 8)
    )

    low_bytes = (
        xor_low
        .view(np.uint8)
        .reshape(-1, 8)
    )

    counts = (
        POPCOUNT8[
            high_bytes
        ].sum(axis=1)
        +
        POPCOUNT8[
            low_bytes
        ].sum(axis=1)
    )

    return (
        counts.astype(
            np.float32
        )
        / 128.0
    )


def hamming64_array(
    values,
    query_value,
):

    xor_values = np.bitwise_xor(
        values,
        query_value,
    )

    byte_values = (
        xor_values
        .view(np.uint8)
        .reshape(-1, 8)
    )

    counts = (
        POPCOUNT8[
            byte_values
        ].sum(axis=1)
    )

    return (
        counts.astype(
            np.float32
        )
        / 64.0
    )


def parent_minimum(
    component_distances,
    project_indices,
    project_count,
):

    result = np.full(
        project_count,
        np.inf,
        dtype=np.float32,
    )

    if len(
        component_distances
    ) > 0:

        np.minimum.at(
            result,
            project_indices,
            component_distances,
        )

    result[
        ~np.isfinite(
            result
        )
    ] = MISSING_PARENT_DISTANCE

    return result


def build_optional_128_gallery(
    dataframe,
    column,
):

    highs = []
    lows = []
    project_indices = []

    for row in dataframe.itertuples(
        index=False
    ):

        parsed = parse_hex128_optional(
            getattr(
                row,
                column,
                "",
            )
        )

        if parsed is None:
            continue

        high, low = parsed

        highs.append(
            high
        )

        lows.append(
            low
        )

        project_indices.append(
            int(
                row.project_index
            )
        )

    return {
        "high":
            np.array(
                highs,
                dtype=np.uint64,
            ),

        "low":
            np.array(
                lows,
                dtype=np.uint64,
            ),

        "project_indices":
            np.array(
                project_indices,
                dtype=np.int32,
            ),
    }


# =========================================================
# Load frozen evidence corpus
# =========================================================

for path in [
    GALLERY_EVIDENCE_CSV,
    QUERY_EVIDENCE_CSV,
    FINAL_QUERY_CSV,
    STRESS_GRAPH_CSV,
]:

    if not path.exists():
        raise FileNotFoundError(
            path
        )


print(
    "Loading Phase 9D evidence index..."
)


gallery = pd.read_csv(
    GALLERY_EVIDENCE_CSV
)

query_evidence = pd.read_csv(
    QUERY_EVIDENCE_CSV
)

final_queries = pd.read_csv(
    FINAL_QUERY_CSV
)

stress_graph = pd.read_csv(
    STRESS_GRAPH_CSV
)


test_query_ids = set(
    final_queries[
        "query_id"
    ].astype(str)
)


test_gallery = gallery[
    gallery[
        "frozen_split"
    ].isin(
        TEST_GALLERY_SPLITS
    )
].copy()


gallery_projects = sorted(
    test_gallery[
        "fresh_id"
    ]
    .astype(str)
    .unique()
)


if len(
    gallery_projects
) != EXPECTED_TEST_GALLERY_PROJECTS:

    raise RuntimeError(
        "Expected 60 TEST gallery projects, "
        f"got {len(gallery_projects)}"
    )


project_to_index = {
    project: index
    for index, project
    in enumerate(
        gallery_projects
    )
}


index_to_project = {
    index: project
    for project, index
    in project_to_index.items()
}


PROJECT_COUNT = len(
    gallery_projects
)


test_gallery[
    "project_index"
] = (
    test_gallery[
        "fresh_id"
    ]
    .astype(str)
    .map(
        project_to_index
    )
)


test_query_evidence = query_evidence[
    query_evidence[
        "query_id"
    ].astype(str).isin(
        test_query_ids
    )
].copy()


# =========================================================
# Build gallery index once at server startup
# =========================================================

# CODE
code_gallery = test_gallery[
    test_gallery[
        "modality"
    ]
    == "CODE_BINARY"
].copy()


code_op3 = build_optional_128_gallery(
    code_gallery,
    "code_op3_simhash128",
)

code_struct = build_optional_128_gallery(
    code_gallery,
    "code_struct_simhash128",
)

code_context = build_optional_128_gallery(
    code_gallery,
    "code_context_simhash128",
)


# STRUCTURED
structured_gallery = test_gallery[
    test_gallery[
        "modality"
    ]
    == "STRUCTURED"
].copy()


structured_rep = build_optional_128_gallery(
    structured_gallery,
    "structured_simhash128",
)


# IMAGE
image_gallery = test_gallery[
    test_gallery[
        "modality"
    ]
    == "IMAGE"
].copy()


image_project_indices = (
    image_gallery[
        "project_index"
    ]
    .astype(int)
    .to_numpy(
        dtype=np.int32
    )
)


image_ahash = []
image_dhash = []
image_phash = []
image_hist = []


for row in image_gallery.itertuples(
    index=False
):

    image_ahash.append(
        parse_hex64(
            row.image_ahash64
        )
    )

    image_dhash.append(
        parse_hex64(
            row.image_dhash64
        )
    )

    image_phash.append(
        parse_hex64(
            row.image_phash64
        )
    )

    image_hist.append(
        parse_hist16(
            row.image_hist16
        )
    )


image_arrays = {
    "project_indices":
        image_project_indices,

    "ahash":
        np.array(
            image_ahash,
            dtype=np.uint64,
        ),

    "dhash":
        np.array(
            image_dhash,
            dtype=np.uint64,
        ),

    "phash":
        np.array(
            image_phash,
            dtype=np.uint64,
        ),

    "hist":
        np.vstack(
            image_hist
        ).astype(
            np.float32
        ),
}


# =========================================================
# Pre-index query rows and graph edges
#
# Query EVIDENCE is precomputed.
# Parent distances are NOT precomputed.
# =========================================================

query_rows_by_id = {}


for query_id, group in (
    test_query_evidence.groupby(
        "query_id",
        sort=False,
    )
):

    query_rows_by_id[
        str(
            query_id
        )
    ] = (
        group
        .sort_values(
            "node_id",
            kind="stable",
        )
        .copy()
    )


edges_by_query = defaultdict(
    list
)


for row in stress_graph.itertuples(
    index=False
):

    query_id = clean_text(
        row.query_id
    )

    if query_id not in test_query_ids:
        continue

    edges_by_query[
        query_id
    ].append(
        (
            clean_text(
                row.node_a
            ),
            clean_text(
                row.node_b
            ),
        )
    )


# =========================================================
# Component → 60-parent distance vector
# =========================================================

def score_component(
    row,
):

    modality = clean_text(
        row.modality
    )


    representation_vectors = []


    # -----------------------------------------------------
    # CODE
    # -----------------------------------------------------

    if modality == "CODE_BINARY":

        parsed = parse_hex128_optional(
            row.code_op3_simhash128
        )

        if parsed is not None:

            q_high, q_low = parsed

            component_distances = (
                hamming128_array(
                    code_op3[
                        "high"
                    ],
                    code_op3[
                        "low"
                    ],
                    q_high,
                    q_low,
                )
            )

            representation_vectors.append(
                parent_minimum(
                    component_distances,
                    code_op3[
                        "project_indices"
                    ],
                    PROJECT_COUNT,
                )
            )


        parsed = parse_hex128_optional(
            row.code_struct_simhash128
        )

        if parsed is not None:

            q_high, q_low = parsed

            component_distances = (
                hamming128_array(
                    code_struct[
                        "high"
                    ],
                    code_struct[
                        "low"
                    ],
                    q_high,
                    q_low,
                )
            )

            representation_vectors.append(
                parent_minimum(
                    component_distances,
                    code_struct[
                        "project_indices"
                    ],
                    PROJECT_COUNT,
                )
            )


        parsed = parse_hex128_optional(
            row.code_context_simhash128
        )

        if parsed is not None:

            q_high, q_low = parsed

            component_distances = (
                hamming128_array(
                    code_context[
                        "high"
                    ],
                    code_context[
                        "low"
                    ],
                    q_high,
                    q_low,
                )
            )

            representation_vectors.append(
                parent_minimum(
                    component_distances,
                    code_context[
                        "project_indices"
                    ],
                    PROJECT_COUNT,
                )
            )


    # -----------------------------------------------------
    # STRUCTURED
    # -----------------------------------------------------

    elif modality == "STRUCTURED":

        parsed = parse_hex128_optional(
            row.structured_simhash128
        )

        if parsed is None:

            raise RuntimeError(
                "Missing STRUCTURED evidence"
            )

        q_high, q_low = parsed

        component_distances = (
            hamming128_array(
                structured_rep[
                    "high"
                ],
                structured_rep[
                    "low"
                ],
                q_high,
                q_low,
            )
        )

        representation_vectors.append(
            parent_minimum(
                component_distances,
                structured_rep[
                    "project_indices"
                ],
                PROJECT_COUNT,
            )
        )


    # -----------------------------------------------------
    # IMAGE
    # -----------------------------------------------------

    elif modality == "IMAGE":

        q_ahash = parse_hex64(
            row.image_ahash64
        )

        q_dhash = parse_hex64(
            row.image_dhash64
        )

        q_phash = parse_hex64(
            row.image_phash64
        )

        q_hist = parse_hist16(
            row.image_hist16
        )


        ahash_component = (
            hamming64_array(
                image_arrays[
                    "ahash"
                ],
                q_ahash,
            )
        )


        dhash_component = (
            hamming64_array(
                image_arrays[
                    "dhash"
                ],
                q_dhash,
            )
        )


        phash_component = (
            hamming64_array(
                image_arrays[
                    "phash"
                ],
                q_phash,
            )
        )


        hist_component = (
            np.abs(
                image_arrays[
                    "hist"
                ]
                -
                q_hist[
                    None,
                    :
                ]
            )
            .sum(
                axis=1
            )
            /
            20000.0
        ).astype(
            np.float32
        )


        hist_component = np.clip(
            hist_component,
            0.0,
            1.0,
        )


        representation_vectors.extend(
            [
                parent_minimum(
                    ahash_component,
                    image_arrays[
                        "project_indices"
                    ],
                    PROJECT_COUNT,
                ),

                parent_minimum(
                    dhash_component,
                    image_arrays[
                        "project_indices"
                    ],
                    PROJECT_COUNT,
                ),

                parent_minimum(
                    phash_component,
                    image_arrays[
                        "project_indices"
                    ],
                    PROJECT_COUNT,
                ),

                parent_minimum(
                    hist_component,
                    image_arrays[
                        "project_indices"
                    ],
                    PROJECT_COUNT,
                ),
            ]
        )


    else:

        raise RuntimeError(
            f"Unsupported modality: {modality}"
        )


    if not representation_vectors:

        raise RuntimeError(
            "No usable component evidence"
        )


    distance_matrix = np.vstack(
        representation_vectors
    )


    fused_parent_distance = (
        distance_matrix.mean(
            axis=0
        )
    )


    # Frozen Phase 7C/7H MEAN_REGRET rule.
    regret_matrix = np.zeros_like(
        distance_matrix,
        dtype=np.float32,
    )


    for representation_index in range(
        distance_matrix.shape[0]
    ):

        minimum = float(
            distance_matrix[
                representation_index
            ].min()
        )


        regret_matrix[
            representation_index
        ] = (
            distance_matrix[
                representation_index
            ]
            -
            minimum
        )


    mean_regret = (
        regret_matrix.mean(
            axis=0
        )
    )


    return (
        fused_parent_distance,
        mean_regret,
    )


# =========================================================
# Full evidence → reconstruction
# =========================================================

def analyze_query_evidence(
    query_id,
):

    if query_id not in query_rows_by_id:

        raise KeyError(
            query_id
        )


    process = psutil.Process(
        os.getpid()
    )


    rss_before = int(
        process
        .memory_info()
        .rss
    )


    total_start = (
        time.perf_counter_ns()
    )


    lookup_start = (
        time.perf_counter_ns()
    )


    query_rows = (
        query_rows_by_id[
            query_id
        ]
    )


    lookup_end = (
        time.perf_counter_ns()
    )


    search_start = (
        time.perf_counter_ns()
    )


    component_inputs = []


    for row in query_rows.itertuples(
        index=False
    ):

        (
            fused_parent_distance,
            mean_regret,
        ) = score_component(
            row
        )


        parent_scores = []


        for project_index in range(
            PROJECT_COUNT
        ):

            parent_scores.append(
                ParentScore(
                    parent_id=(
                        index_to_project[
                            project_index
                        ]
                    ),

                    fused_parent_distance=float(
                        fused_parent_distance[
                            project_index
                        ]
                    ),

                    mean_regret=float(
                        mean_regret[
                            project_index
                        ]
                    ),
                )
            )


        component_inputs.append(
            ComponentInput(
                node_id=clean_text(
                    row.node_id
                ),

                modality=clean_text(
                    row.modality
                ),

                parent_scores=parent_scores,
            )
        )


    search_end = (
        time.perf_counter_ns()
    )


    graph_edges = [
        GraphEdgeInput(
            node_a=node_a,
            node_b=node_b,
        )

        for node_a, node_b
        in edges_by_query.get(
            query_id,
            []
        )
    ]


    reconstruction_start = (
        time.perf_counter_ns()
    )


    result = analyze_internal(
        AnalyzeRequest(
            query_id=query_id,
            components=component_inputs,
            edges=graph_edges,
        )
    )


    reconstruction_end = (
        time.perf_counter_ns()
    )


    total_end = (
        time.perf_counter_ns()
    )


    rss_after = int(
        process
        .memory_info()
        .rss
    )


    result[
        "phase9d_latency_ms"
    ] = {
        "query_evidence_lookup":
            (
                lookup_end
                -
                lookup_start
            )
            / 1_000_000.0,

        "gallery_similarity_search":
            (
                search_end
                -
                search_start
            )
            / 1_000_000.0,

        "reconstruction":
            (
                reconstruction_end
                -
                reconstruction_start
            )
            / 1_000_000.0,

        "total_evidence_to_result":
            (
                total_end
                -
                total_start
            )
            / 1_000_000.0,
    }


    result[
        "phase9d_memory"
    ] = {
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


    result[
        "phase9d_scope"
    ] = (
        "IDENTITY_NEUTRAL_EVIDENCE_TO_PROVENANCE"
    )


    return result


# =========================================================
# API
# =========================================================

app = FastAPI(
    title=(
        "Game MOD Provenance "
        "Evidence Search Server"
    ),

    version="9D",
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
            "9D",

        "gallery_projects":
            PROJECT_COUNT,

        "test_queries_loaded":
            len(
                query_rows_by_id
            ),

        "gallery_code_components":
            len(
                code_gallery
            ),

        "gallery_structured_components":
            len(
                structured_gallery
            ),

        "gallery_image_components":
            len(
                image_gallery
            ),

        "rss_bytes":
            int(
                process
                .memory_info()
                .rss
            ),

        "scope":
            (
                "identity-neutral evidence "
                "to gallery search "
                "to provenance reconstruction"
            ),
    }


@app.get(
    "/analyze-evidence/{query_id}"
)
def analyze_evidence(
    query_id: str,
):

    try:

        return analyze_query_evidence(
            str(
                query_id
            )
        )

    except KeyError:

        raise HTTPException(
            status_code=404,
            detail=(
                "query_id not found "
                "in frozen TEST evidence"
            ),
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(
                error
            ),
        )


print(
    "Phase 9D evidence index ready."
)

print(
    "Gallery projects:",
    PROJECT_COUNT
)

print(
    "TEST queries:",
    len(
        query_rows_by_id
    )
)