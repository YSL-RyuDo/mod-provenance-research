import os
import time
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

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

import server.phase9d_evidence_server as phase9d


# =========================================================
# Configuration
# =========================================================

ROOT = Path(__file__).resolve().parent.parent

GALLERY_SCALES = [
    20,
    40,
    60,
    80,
    100,
]

EXPECTED_TEST_PROJECTS = 60
EXPECTED_CAL_PROJECTS = 40

MISSING_PARENT_DISTANCE = 1.0


# =========================================================
# Frozen evidence table from Phase 7B
# =========================================================

gallery = phase9d.gallery.copy()


TEST_SPLITS = {
    "TEST_KNOWN",
    "TEST_BACKGROUND",
}

CAL_SPLITS = {
    "CALIBRATION_KNOWN",
    "CALIBRATION_BACKGROUND",
}


test_gallery = gallery[
    gallery[
        "frozen_split"
    ].isin(
        TEST_SPLITS
    )
].copy()


cal_gallery = gallery[
    gallery[
        "frozen_split"
    ].isin(
        CAL_SPLITS
    )
].copy()


test_projects = sorted(
    test_gallery[
        "fresh_id"
    ]
    .astype(str)
    .unique()
)


cal_projects = sorted(
    cal_gallery[
        "fresh_id"
    ]
    .astype(str)
    .unique()
)


if len(
    test_projects
) != EXPECTED_TEST_PROJECTS:

    raise RuntimeError(
        "Expected 60 TEST gallery projects, "
        f"got {len(test_projects)}"
    )


if len(
    cal_projects
) != EXPECTED_CAL_PROJECTS:

    raise RuntimeError(
        "Expected 40 CAL gallery projects, "
        f"got {len(cal_projects)}"
    )


# TEST projects first.
# Therefore scale=60 exactly reproduces the project set
# used by Phase 9D/9E.
ordered_projects = (
    test_projects
    +
    cal_projects
)


if len(
    ordered_projects
) != 100:

    raise RuntimeError(
        "Expected exactly 100 real gallery projects"
    )


if len(
    set(
        ordered_projects
    )
) != 100:

    raise RuntimeError(
        "Duplicate project IDs across TEST/CAL gallery"
    )


phase9d_project_set = set(
    phase9d.gallery_projects
)


if set(
    ordered_projects[:60]
) != phase9d_project_set:

    raise RuntimeError(
        "Scale 60 does not reproduce Phase 9D "
        "TEST gallery project set"
    )


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

        parsed = (
            phase9d.parse_hex128_optional(
                getattr(
                    row,
                    column,
                    "",
                )
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
            np.asarray(
                highs,
                dtype=np.uint64,
            ),

        "low":
            np.asarray(
                lows,
                dtype=np.uint64,
            ),

        "project_indices":
            np.asarray(
                project_indices,
                dtype=np.int32,
            ),
    }


# =========================================================
# Build a real gallery index for every scale
# =========================================================

def build_scale_index(
    scale,
):

    selected_projects = (
        ordered_projects[
            :scale
        ]
    )


    selected_project_set = set(
        selected_projects
    )


    scale_gallery = gallery[
        gallery[
            "fresh_id"
        ]
        .astype(str)
        .isin(
            selected_project_set
        )
    ].copy()


    project_to_index = {
        project:
            index

        for index, project
        in enumerate(
            selected_projects
        )
    }


    index_to_project = {
        index:
            project

        for project, index
        in project_to_index.items()
    }


    scale_gallery[
        "project_index"
    ] = (
        scale_gallery[
            "fresh_id"
        ]
        .astype(str)
        .map(
            project_to_index
        )
    )


    if scale_gallery[
        "project_index"
    ].isna().any():

        raise RuntimeError(
            f"Scale {scale}: project mapping failure"
        )


    # -----------------------------------------------------
    # CODE
    # -----------------------------------------------------

    code_gallery = scale_gallery[
        scale_gallery[
            "modality"
        ]
        ==
        "CODE_BINARY"
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


    # -----------------------------------------------------
    # STRUCTURED
    # -----------------------------------------------------

    structured_gallery = scale_gallery[
        scale_gallery[
            "modality"
        ]
        ==
        "STRUCTURED"
    ].copy()


    structured_rep = build_optional_128_gallery(
        structured_gallery,
        "structured_simhash128",
    )


    # -----------------------------------------------------
    # IMAGE
    # -----------------------------------------------------

    image_gallery = scale_gallery[
        scale_gallery[
            "modality"
        ]
        ==
        "IMAGE"
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
            phase9d.parse_hex64(
                row.image_ahash64
            )
        )

        image_dhash.append(
            phase9d.parse_hex64(
                row.image_dhash64
            )
        )

        image_phash.append(
            phase9d.parse_hex64(
                row.image_phash64
            )
        )

        image_hist.append(
            phase9d.parse_hist16(
                row.image_hist16
            )
        )


    image_arrays = {
        "project_indices":
            image_project_indices,

        "ahash":
            np.asarray(
                image_ahash,
                dtype=np.uint64,
            ),

        "dhash":
            np.asarray(
                image_dhash,
                dtype=np.uint64,
            ),

        "phash":
            np.asarray(
                image_phash,
                dtype=np.uint64,
            ),

        "hist":
            (
                np.vstack(
                    image_hist
                )
                .astype(
                    np.float32
                )
                if image_hist
                else
                np.empty(
                    (
                        0,
                        16,
                    ),
                    dtype=np.float32,
                )
            ),
    }


    by_modality = (
        scale_gallery[
            "modality"
        ]
        .value_counts()
        .to_dict()
    )


    return {
        "scale":
            int(
                scale
            ),

        "projects":
            selected_projects,

        "project_to_index":
            project_to_index,

        "index_to_project":
            index_to_project,

        "project_count":
            int(
                scale
            ),

        "gallery_component_count":
            int(
                len(
                    scale_gallery
                )
            ),

        "by_modality": {
            str(key):
                int(
                    value
                )

            for key, value
            in by_modality.items()
        },

        "code_op3":
            code_op3,

        "code_struct":
            code_struct,

        "code_context":
            code_context,

        "structured_rep":
            structured_rep,

        "image_arrays":
            image_arrays,
    }


print(
    "======================================"
)

print(
    "Phase 9F - Building Gallery Scale Indexes"
)

print(
    "======================================"
)


scale_indexes = {}


for scale in GALLERY_SCALES:

    print(
        "Building scale:",
        scale
    )


    scale_indexes[
        scale
    ] = build_scale_index(
        scale
    )


print(
    "All gallery scale indexes: READY"
)


# =========================================================
# Scale-aware minimum parent score
# =========================================================

def parent_minimum_scale(
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


# =========================================================
# Score one query component at arbitrary gallery scale
# =========================================================

def score_component_scale(
    row,
    index,
):

    modality = clean_text(
        row.modality
    )


    project_count = int(
        index[
            "project_count"
        ]
    )


    representation_vectors = []


    # -----------------------------------------------------
    # CODE
    # -----------------------------------------------------

    if modality == "CODE_BINARY":

        for column, gallery_key in [
            (
                "code_op3_simhash128",
                "code_op3",
            ),
            (
                "code_struct_simhash128",
                "code_struct",
            ),
            (
                "code_context_simhash128",
                "code_context",
            ),
        ]:

            parsed = (
                phase9d.parse_hex128_optional(
                    getattr(
                        row,
                        column,
                        "",
                    )
                )
            )


            if parsed is None:
                continue


            q_high, q_low = parsed

            representation = (
                index[
                    gallery_key
                ]
            )


            distances = (
                phase9d.hamming128_array(
                    representation[
                        "high"
                    ],
                    representation[
                        "low"
                    ],
                    q_high,
                    q_low,
                )
            )


            representation_vectors.append(
                parent_minimum_scale(
                    distances,
                    representation[
                        "project_indices"
                    ],
                    project_count,
                )
            )


    # -----------------------------------------------------
    # STRUCTURED
    # -----------------------------------------------------

    elif modality == "STRUCTURED":

        parsed = (
            phase9d.parse_hex128_optional(
                row.structured_simhash128
            )
        )


        if parsed is None:

            raise RuntimeError(
                "Missing STRUCTURED evidence"
            )


        q_high, q_low = parsed

        representation = (
            index[
                "structured_rep"
            ]
        )


        distances = (
            phase9d.hamming128_array(
                representation[
                    "high"
                ],
                representation[
                    "low"
                ],
                q_high,
                q_low,
            )
        )


        representation_vectors.append(
            parent_minimum_scale(
                distances,
                representation[
                    "project_indices"
                ],
                project_count,
            )
        )


    # -----------------------------------------------------
    # IMAGE
    # -----------------------------------------------------

    elif modality == "IMAGE":

        image_arrays = (
            index[
                "image_arrays"
            ]
        )


        if len(
            image_arrays[
                "project_indices"
            ]
        ) == 0:

            raise RuntimeError(
                "Image gallery is empty"
            )


        q_ahash = (
            phase9d.parse_hex64(
                row.image_ahash64
            )
        )

        q_dhash = (
            phase9d.parse_hex64(
                row.image_dhash64
            )
        )

        q_phash = (
            phase9d.parse_hex64(
                row.image_phash64
            )
        )

        q_hist = (
            phase9d.parse_hist16(
                row.image_hist16
            )
        )


        ahash_component = (
            phase9d.hamming64_array(
                image_arrays[
                    "ahash"
                ],
                q_ahash,
            )
        )


        dhash_component = (
            phase9d.hamming64_array(
                image_arrays[
                    "dhash"
                ],
                q_dhash,
            )
        )


        phash_component = (
            phase9d.hamming64_array(
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


        for distances in [
            ahash_component,
            dhash_component,
            phash_component,
            hist_component,
        ]:

            representation_vectors.append(
                parent_minimum_scale(
                    distances,
                    image_arrays[
                        "project_indices"
                    ],
                    project_count,
                )
            )


    else:

        raise RuntimeError(
            f"Unsupported modality: {modality}"
        )


    if not representation_vectors:

        raise RuntimeError(
            "No usable evidence representation"
        )


    distance_matrix = np.vstack(
        representation_vectors
    )


    fused_parent_distance = (
        distance_matrix.mean(
            axis=0
        )
    )


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
# Analyze query against scale
# =========================================================

def analyze_scale_internal(
    scale,
    query_id,
):

    scale = int(
        scale
    )

    query_id = str(
        query_id
    )


    if scale not in scale_indexes:

        raise KeyError(
            f"unsupported scale {scale}"
        )


    if query_id not in phase9d.query_rows_by_id:

        raise KeyError(
            query_id
        )


    index = (
        scale_indexes[
            scale
        ]
    )


    process = psutil.Process(
        os.getpid()
    )


    rss_before = int(
        process.memory_info().rss
    )


    total_start = (
        time.perf_counter_ns()
    )


    query_rows = (
        phase9d.query_rows_by_id[
            query_id
        ]
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
        ) = score_component_scale(
            row,
            index,
        )


        parent_scores = []


        for project_index in range(
            index[
                "project_count"
            ]
        ):

            parent_scores.append(
                ParentScore(
                    parent_id=(
                        index[
                            "index_to_project"
                        ][
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
        in phase9d.edges_by_query.get(
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
        process.memory_info().rss
    )


    result[
        "phase9f"
    ] = {
        "gallery_scale_projects":
            scale,

        "gallery_components":
            int(
                index[
                    "gallery_component_count"
                ]
            ),

        "gallery_components_by_modality":
            index[
                "by_modality"
            ],

        "latency_ms": {
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

            "total":
                (
                    total_end
                    -
                    total_start
                )
                / 1_000_000.0,
        },

        "memory": {
            "rss_before_bytes":
                rss_before,

            "rss_after_bytes":
                rss_after,
        },
    }


    return result


# =========================================================
# API
# =========================================================

app = FastAPI(
    title=(
        "Game MOD Provenance "
        "Gallery Scalability Server"
    ),

    version="9F",
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
            "9F",

        "gallery_scales":
            GALLERY_SCALES,

        "real_projects_available":
            100,

        "test_projects":
            len(
                test_projects
            ),

        "cal_projects":
            len(
                cal_projects
            ),

        "scale60_matches_phase9d_project_set":
            True,

        "test_queries_loaded":
            len(
                phase9d.query_rows_by_id
            ),

        "rss_bytes":
            int(
                process.memory_info().rss
            ),

        "scope":
            (
                "gallery-size scalability only; "
                "accuracy is not evaluated or retuned"
            ),
    }


@app.get(
    "/analyze-scale/{scale}/{query_id}"
)
def analyze_scale(
    scale: int,
    query_id: str,
):

    try:

        return analyze_scale_internal(
            scale,
            query_id,
        )

    except KeyError as error:

        raise HTTPException(
            status_code=404,
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


print()

print(
    "======================================"
)

print(
    "Phase 9F server ready"
)

print(
    "======================================"
)


for scale in GALLERY_SCALES:

    index = (
        scale_indexes[
            scale
        ]
    )

    print(
        "Scale",
        scale,
        ":",
        index[
            "gallery_component_count"
        ],
        "components",
    )