import json
from pathlib import Path

import numpy as np
import pandas as pd


# =========================================================
# Config
# =========================================================

GALLERY_EVIDENCE_CSV = Path(
    "results/phase7b_gallery_identity_neutral_evidence.csv"
)

QUERY_EVIDENCE_CSV = Path(
    "results/phase7b_query_identity_neutral_evidence.csv"
)

CAL_COMPONENT_GT_CSV = Path(
    "results/phase7a_calibration_component_ground_truth.csv"
)

CAL_QUERY_PROTOCOL_CSV = Path(
    "results/phase7a_calibration_query_protocol.csv"
)

CAL_GALLERY_PROTOCOL_CSV = Path(
    "results/phase7a_calibration_gallery_protocol.csv"
)


OUTPUT_SCORE_CSV = Path(
    "results/phase7c_calibration_component_parent_scores.csv"
)

OUTPUT_OPENSET_CSV = Path(
    "results/phase7c_calibration_component_openset_features.csv"
)

OUTPUT_FAILURE_JSON = Path(
    "results/phase7c_score_failures.json"
)

OUTPUT_SUMMARY_JSON = Path(
    "results/phase7c_score_summary.json"
)


EXPECTED_QUERIES = 180
EXPECTED_COMPONENTS = 1260
EXPECTED_VISIBLE_PROJECTS = 39
EXPECTED_SCORE_ROWS = (
    EXPECTED_COMPONENTS
    * EXPECTED_VISIBLE_PROJECTS
)

MISSING_PARENT_DISTANCE = 1.0


CALIBRATION_SPLITS = {
    "CALIBRATION_KNOWN",
    "CALIBRATION_BACKGROUND",
}


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


# =========================================================
# Hex
# =========================================================

def parse_hex128(value):

    text = clean_text(value)

    if len(text) != 32:

        raise ValueError(
            f"Expected 128-bit hex, got: {text!r}"
        )

    integer = int(
        text,
        16,
    )

    high = integer >> 64

    low = (
        integer
        & ((1 << 64) - 1)
    )

    return (
        np.uint64(high),
        np.uint64(low),
    )


def parse_hex128_optional(value):

    text = clean_text(value)

    if not text:
        return None

    return parse_hex128(
        text
    )


def parse_hex64(value):

    text = clean_text(value)

    if len(text) != 16:

        raise ValueError(
            f"Expected 64-bit hex, got: {text!r}"
        )

    return np.uint64(
        int(
            text,
            16,
        )
    )


# =========================================================
# Popcount
# =========================================================

POPCOUNT8 = np.array(
    [
        bin(value).count("1")
        for value in range(256)
    ],
    dtype=np.uint8,
)


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
        counts.astype(np.float32)
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
        counts.astype(np.float32)
        / 64.0
    )


# =========================================================
# Histogram
# =========================================================

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
# Parent minimum
# =========================================================

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


    if len(component_distances) > 0:

        np.minimum.at(
            result,
            project_indices,
            component_distances,
        )


    result[
        ~np.isfinite(result)
    ] = MISSING_PARENT_DISTANCE


    return result


# =========================================================
# Build optional 128-bit gallery representation
# =========================================================

def build_optional_128_gallery(
    dataframe,
    column,
):

    highs = []
    lows = []
    projects = []

    missing = 0


    for row in dataframe.itertuples(
        index=False
    ):

        value = clean_text(
            getattr(
                row,
                column,
            )
        )


        if not value:

            missing += 1
            continue


        high, low = parse_hex128(
            value
        )


        highs.append(
            high
        )

        lows.append(
            low
        )

        projects.append(
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
                projects,
                dtype=np.int32,
            ),

        "available":
            int(
                len(highs)
            ),

        "missing":
            int(
                missing
            ),
    }


# =========================================================
# Load
# =========================================================

for path in [
    GALLERY_EVIDENCE_CSV,
    QUERY_EVIDENCE_CSV,
    CAL_COMPONENT_GT_CSV,
    CAL_QUERY_PROTOCOL_CSV,
    CAL_GALLERY_PROTOCOL_CSV,
]:

    if not path.exists():

        raise FileNotFoundError(
            f"Missing: {path}"
        )


gallery = pd.read_csv(
    GALLERY_EVIDENCE_CSV
)

query = pd.read_csv(
    QUERY_EVIDENCE_CSV
)

component_gt = pd.read_csv(
    CAL_COMPONENT_GT_CSV
)

query_protocol = pd.read_csv(
    CAL_QUERY_PROTOCOL_CSV
)

gallery_protocol = pd.read_csv(
    CAL_GALLERY_PROTOCOL_CSV
)


print(
    "======================================"
)

print(
    "Phase 7C - Calibration Parent Scores"
)

print(
    "======================================"
)


# =========================================================
# Calibration queries
# =========================================================

calibration_query_ids = set(
    component_gt[
        "query_id"
    ].astype(str)
)


if len(
    calibration_query_ids
) != EXPECTED_QUERIES:

    raise RuntimeError(
        "Expected 180 calibration queries"
    )


cal_query = query[
    query[
        "query_id"
    ].astype(str).isin(
        calibration_query_ids
    )
].copy()


if len(
    cal_query
) != EXPECTED_COMPONENTS:

    raise RuntimeError(
        f"Expected {EXPECTED_COMPONENTS} "
        f"calibration components, "
        f"got {len(cal_query)}"
    )


# =========================================================
# Calibration gallery ONLY
# =========================================================

cal_gallery = gallery[
    gallery[
        "frozen_split"
    ].isin(
        CALIBRATION_SPLITS
    )
].copy()


gallery_projects = sorted(
    cal_gallery[
        "fresh_id"
    ].astype(str).unique()
)


if len(
    gallery_projects
) != 40:

    raise RuntimeError(
        f"Expected 40 calibration projects, "
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


project_count = len(
    gallery_projects
)


cal_gallery[
    "project_index"
] = (
    cal_gallery[
        "fresh_id"
    ]
    .astype(str)
    .map(
        project_to_index
    )
)


# =========================================================
# Project roles
# =========================================================

project_roles = {}


for row in gallery_protocol.itertuples(
    index=False
):

    fresh_id = clean_text(
        row.fresh_id
    )

    role = clean_text(
        row.gallery_role
    )


    if fresh_id in project_roles:

        if (
            project_roles[
                fresh_id
            ]
            != role
        ):

            raise RuntimeError(
                "Conflicting project role"
            )

    else:

        project_roles[
            fresh_id
        ] = role


# =========================================================
# Hidden parent
# =========================================================

hidden_parent_by_query = dict(
    zip(
        query_protocol[
            "query_id"
        ].astype(str),

        query_protocol[
            "hidden_parent"
        ].astype(str),
    )
)


# =========================================================
# GT
# =========================================================

component_gt_map = {}


for row in component_gt.itertuples(
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


    component_gt_map[
        key
    ] = {
        "pseudo_ground_truth_label":
            clean_text(
                row.pseudo_ground_truth_label
            ),

        "is_pseudo_unknown":
            as_bool(
                row.is_pseudo_unknown
            ),

        "original_source_parent":
            clean_text(
                row.original_source_parent
            ),
    }


# =========================================================
# Gallery: CODE
# =========================================================

code_gallery = cal_gallery[
    cal_gallery[
        "modality"
    ]
    == "CODE_BINARY"
].copy()


code_op3 = (
    build_optional_128_gallery(
        code_gallery,
        "code_op3_simhash128",
    )
)


code_struct = (
    build_optional_128_gallery(
        code_gallery,
        "code_struct_simhash128",
    )
)


code_context = (
    build_optional_128_gallery(
        code_gallery,
        "code_context_simhash128",
    )
)


print(
    "Calibration gallery CODE:",
    len(code_gallery)
)

print(
    "  OP3 available/missing:",
    code_op3["available"],
    "/",
    code_op3["missing"],
)

print(
    "  STRUCT available/missing:",
    code_struct["available"],
    "/",
    code_struct["missing"],
)

print(
    "  CONTEXT available/missing:",
    code_context["available"],
    "/",
    code_context["missing"],
)


if (
    code_struct[
        "available"
    ]
    == 0
):

    raise RuntimeError(
        "No CODE STRUCT representations available"
    )


# =========================================================
# Gallery: STRUCTURED
# =========================================================

structured_gallery = cal_gallery[
    cal_gallery[
        "modality"
    ]
    == "STRUCTURED"
].copy()


structured_rep = (
    build_optional_128_gallery(
        structured_gallery,
        "structured_simhash128",
    )
)


if (
    structured_rep[
        "available"
    ]
    == 0
):

    raise RuntimeError(
        "No structured representations"
    )


print(
    "Calibration gallery STRUCTURED:",
    len(structured_gallery)
)

print(
    "  available/missing:",
    structured_rep["available"],
    "/",
    structured_rep["missing"],
)


# =========================================================
# Gallery: IMAGE
# =========================================================

image_gallery = cal_gallery[
    cal_gallery[
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


print(
    "Calibration gallery IMAGE:",
    len(image_gallery)
)


# =========================================================
# Query missing-signature diagnostics
# =========================================================

cal_code_query = cal_query[
    cal_query[
        "modality"
    ]
    == "CODE_BINARY"
]


query_code_missing = {
    "OP3":
        int(
            cal_code_query[
                "code_op3_simhash128"
            ].isna().sum()
            +
            (
                cal_code_query[
                    "code_op3_simhash128"
                ]
                .fillna("")
                .astype(str)
                .str.strip()
                == ""
            ).sum()
            -
            cal_code_query[
                "code_op3_simhash128"
            ].isna().sum()
        ),

    "STRUCT":
        int(
            (
                cal_code_query[
                    "code_struct_simhash128"
                ]
                .fillna("")
                .astype(str)
                .str.strip()
                == ""
            ).sum()
        ),

    "CONTEXT":
        int(
            (
                cal_code_query[
                    "code_context_simhash128"
                ]
                .fillna("")
                .astype(str)
                .str.strip()
                == ""
            ).sum()
        ),
}


# =========================================================
# Scoring
# =========================================================

score_rows = []

openset_rows = []

failure_rows = []


modality_counts = {
    "CODE_BINARY": 0,
    "STRUCTURED": 0,
    "IMAGE": 0,
}


code_query_rep_usage = {
    "OP3":
        0,

    "STRUCT":
        0,

    "CONTEXT":
        0,
}


code_query_rep_count_distribution = {
    "1":
        0,

    "2":
        0,

    "3":
        0,
}


hidden_parent_rows_emitted = 0


cal_query = (
    cal_query
    .sort_values(
        [
            "query_id",
            "node_id",
        ],
        kind="stable",
    )
    .reset_index(
        drop=True
    )
)


for component_index, row in enumerate(
    cal_query.itertuples(
        index=False
    ),
    start=1,
):

    if (
        component_index == 1
        or
        component_index % 100 == 0
    ):

        print(
            f"component "
            f"{component_index}/"
            f"{len(cal_query)}"
        )


    query_id = clean_text(
        row.query_id
    )

    node_id = clean_text(
        row.node_id
    )

    modality = clean_text(
        row.modality
    )


    gt_key = (
        query_id,
        node_id,
    )


    if gt_key not in component_gt_map:

        raise RuntimeError(
            f"Missing GT: "
            f"{query_id}/{node_id}"
        )


    gt_record = component_gt_map[
        gt_key
    ]


    hidden_parent = (
        hidden_parent_by_query.get(
            query_id
        )
    )


    if not hidden_parent:

        raise RuntimeError(
            f"Missing hidden parent: "
            f"{query_id}"
        )


    hidden_index = (
        project_to_index[
            hidden_parent
        ]
    )


    visible_indices = [
        index
        for index
        in range(
            project_count
        )
        if index
        != hidden_index
    ]


    if (
        len(
            visible_indices
        )
        != EXPECTED_VISIBLE_PROJECTS
    ):

        raise RuntimeError(
            "Visible gallery count mismatch"
        )


    modality_counts[
        modality
    ] += 1


    representation_names = []

    representation_parent_distances = []


    # =====================================================
    # CODE
    # =====================================================

    if modality == "CODE_BINARY":

        # -------------------------------------------------
        # OP3 - optional
        # -------------------------------------------------

        parsed = (
            parse_hex128_optional(
                row.code_op3_simhash128
            )
        )


        if parsed is not None:

            q_high, q_low = parsed


            component_distances = (
                hamming128_array(
                    code_op3["high"],
                    code_op3["low"],
                    q_high,
                    q_low,
                )
            )


            parent_distances = (
                parent_minimum(
                    component_distances,
                    code_op3[
                        "project_indices"
                    ],
                    project_count,
                )
            )


            representation_names.append(
                "CODE_OP3"
            )

            representation_parent_distances.append(
                parent_distances
            )


            code_query_rep_usage[
                "OP3"
            ] += 1


        # -------------------------------------------------
        # STRUCT - expected to exist
        # -------------------------------------------------

        parsed = (
            parse_hex128_optional(
                row.code_struct_simhash128
            )
        )


        if parsed is not None:

            q_high, q_low = parsed


            component_distances = (
                hamming128_array(
                    code_struct["high"],
                    code_struct["low"],
                    q_high,
                    q_low,
                )
            )


            parent_distances = (
                parent_minimum(
                    component_distances,
                    code_struct[
                        "project_indices"
                    ],
                    project_count,
                )
            )


            representation_names.append(
                "CODE_STRUCT"
            )

            representation_parent_distances.append(
                parent_distances
            )


            code_query_rep_usage[
                "STRUCT"
            ] += 1


        # -------------------------------------------------
        # CONTEXT - optional
        # -------------------------------------------------

        parsed = (
            parse_hex128_optional(
                row.code_context_simhash128
            )
        )


        if parsed is not None:

            q_high, q_low = parsed


            component_distances = (
                hamming128_array(
                    code_context["high"],
                    code_context["low"],
                    q_high,
                    q_low,
                )
            )


            parent_distances = (
                parent_minimum(
                    component_distances,
                    code_context[
                        "project_indices"
                    ],
                    project_count,
                )
            )


            representation_names.append(
                "CODE_CONTEXT"
            )

            representation_parent_distances.append(
                parent_distances
            )


            code_query_rep_usage[
                "CONTEXT"
            ] += 1


        rep_count = len(
            representation_parent_distances
        )


        if rep_count == 0:

            raise RuntimeError(
                f"{query_id}/{node_id}: "
                f"no usable CODE representation"
            )


        code_query_rep_count_distribution[
            str(rep_count)
        ] += 1


    # =====================================================
    # STRUCTURED
    # =====================================================

    elif modality == "STRUCTURED":

        parsed = (
            parse_hex128_optional(
                row.structured_simhash128
            )
        )


        if parsed is None:

            raise RuntimeError(
                f"{query_id}/{node_id}: "
                f"missing structured signature"
            )


        q_high, q_low = parsed


        component_distances = (
            hamming128_array(
                structured_rep["high"],
                structured_rep["low"],
                q_high,
                q_low,
            )
        )


        parent_distances = (
            parent_minimum(
                component_distances,
                structured_rep[
                    "project_indices"
                ],
                project_count,
            )
        )


        representation_names = [
            "STRUCTURED_SIMHASH",
        ]

        representation_parent_distances = [
            parent_distances,
        ]


    # =====================================================
    # IMAGE
    # =====================================================

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
            .sum(axis=1)
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


        ahash_parent = parent_minimum(
            ahash_component,
            image_arrays[
                "project_indices"
            ],
            project_count,
        )


        dhash_parent = parent_minimum(
            dhash_component,
            image_arrays[
                "project_indices"
            ],
            project_count,
        )


        phash_parent = parent_minimum(
            phash_component,
            image_arrays[
                "project_indices"
            ],
            project_count,
        )


        hist_parent = parent_minimum(
            hist_component,
            image_arrays[
                "project_indices"
            ],
            project_count,
        )


        representation_names = [
            "IMAGE_AHASH",
            "IMAGE_DHASH",
            "IMAGE_PHASH",
            "IMAGE_HIST16",
        ]


        representation_parent_distances = [
            ahash_parent,
            dhash_parent,
            phash_parent,
            hist_parent,
        ]


    else:

        raise RuntimeError(
            f"Unsupported modality: "
            f"{modality}"
        )


    # =====================================================
    # Fusion
    #
    # IMPORTANT:
    #
    # Only AVAILABLE representations for this query
    # component are included.
    # =====================================================

    distance_matrix = np.vstack(
        representation_parent_distances
    )


    fused_parent_distance = (
        distance_matrix.mean(
            axis=0
        )
    )


    # =====================================================
    # MEAN_REGRET
    # =====================================================

    regret_matrix = np.zeros_like(
        distance_matrix,
        dtype=np.float32,
    )


    for rep_index in range(
        distance_matrix.shape[0]
    ):

        visible_values = (
            distance_matrix[
                rep_index,
                visible_indices
            ]
        )


        reference_minimum = float(
            visible_values.min()
        )


        regret_matrix[
            rep_index
        ] = (
            distance_matrix[
                rep_index
            ]
            -
            reference_minimum
        )


    mean_regret = (
        regret_matrix.mean(
            axis=0
        )
    )


    # =====================================================
    # Visible ranking
    # =====================================================

    visible_records = []


    for project_index in visible_indices:

        project = index_to_project[
            project_index
        ]


        visible_records.append({
            "project_index":
                project_index,

            "project":
                project,

            "fused_distance":
                float(
                    fused_parent_distance[
                        project_index
                    ]
                ),

            "mean_regret":
                float(
                    mean_regret[
                        project_index
                    ]
                ),
        })


    visible_records.sort(
        key=lambda item: (
            item["fused_distance"],
            item["mean_regret"],
            item["project"],
        )
    )


    rank_by_project = {
        record["project"]:
            rank

        for rank, record
        in enumerate(
            visible_records,
            start=1,
        )
    }


    best_record = visible_records[0]

    second_record = visible_records[1]


    best_distance = float(
        best_record[
            "fused_distance"
        ]
    )


    second_distance = float(
        second_record[
            "fused_distance"
        ]
    )


    # =====================================================
    # Open-set features
    # =====================================================

    openset_rows.append({
        "query_id":
            query_id,

        "node_id":
            node_id,

        "modality":
            modality,

        "pseudo_ground_truth_label":
            gt_record[
                "pseudo_ground_truth_label"
            ],

        "is_pseudo_unknown":
            bool(
                gt_record[
                    "is_pseudo_unknown"
                ]
            ),

        "hidden_parent":
            hidden_parent,

        "best_visible_parent":
            best_record[
                "project"
            ],

        "best_fused_parent_distance":
            best_distance,

        "second_fused_parent_distance":
            second_distance,

        "distance_margin":
            float(
                second_distance
                -
                best_distance
            ),

        "best_mean_regret":
            float(
                mean_regret[
                    best_record[
                        "project_index"
                    ]
                ]
            ),

        "representation_count":
            int(
                distance_matrix.shape[0]
            ),

        "visible_project_count":
            EXPECTED_VISIBLE_PROJECTS,
    })


    # =====================================================
    # Candidate score rows
    # =====================================================

    for project_index in visible_indices:

        project = index_to_project[
            project_index
        ]


        if project == hidden_parent:

            hidden_parent_rows_emitted += 1


        output = {
            "query_id":
                query_id,

            "node_id":
                node_id,

            "modality":
                modality,

            "candidate_parent":
                project,

            "candidate_role":
                project_roles.get(
                    project,
                    "",
                ),

            "candidate_rank":
                int(
                    rank_by_project[
                        project
                    ]
                ),

            "fused_parent_distance":
                float(
                    fused_parent_distance[
                        project_index
                    ]
                ),

            "mean_regret":
                float(
                    mean_regret[
                        project_index
                    ]
                ),

            "representation_count":
                int(
                    distance_matrix.shape[0]
                ),

            "is_pseudo_unknown_component":
                bool(
                    gt_record[
                        "is_pseudo_unknown"
                    ]
                ),
        }


        for (
            rep_name,
            rep_values,
        ) in zip(
            representation_names,
            representation_parent_distances,
        ):

            output[
                "distance_"
                + rep_name.lower()
            ] = float(
                rep_values[
                    project_index
                ]
            )


        score_rows.append(
            output
        )


# =========================================================
# DataFrames
# =========================================================

scores = pd.DataFrame(
    score_rows
)

openset = pd.DataFrame(
    openset_rows
)


# =========================================================
# Validation
# =========================================================

if len(scores) != EXPECTED_SCORE_ROWS:

    raise RuntimeError(
        f"Expected {EXPECTED_SCORE_ROWS} "
        f"score rows, got {len(scores)}"
    )


if len(openset) != EXPECTED_COMPONENTS:

    raise RuntimeError(
        f"Expected {EXPECTED_COMPONENTS} "
        f"open-set rows, got {len(openset)}"
    )


rows_per_component = (
    scores
    .groupby(
        [
            "query_id",
            "node_id",
        ]
    )
    .size()
)


if not (
    rows_per_component
    == EXPECTED_VISIBLE_PROJECTS
).all():

    raise RuntimeError(
        "Not every component has 39 parents"
    )


if hidden_parent_rows_emitted != 0:

    raise RuntimeError(
        "Hidden parent was emitted"
    )


if not np.isfinite(
    scores[
        "fused_parent_distance"
    ].to_numpy(
        dtype=float
    )
).all():

    raise RuntimeError(
        "Non-finite fused distances"
    )


if not np.isfinite(
    scores[
        "mean_regret"
    ].to_numpy(
        dtype=float
    )
).all():

    raise RuntimeError(
        "Non-finite regrets"
    )


# =========================================================
# Save
# =========================================================

OUTPUT_SCORE_CSV.parent.mkdir(
    parents=True,
    exist_ok=True,
)


scores.to_csv(
    OUTPUT_SCORE_CSV,
    index=False,
    encoding="utf-8-sig",
)


openset.to_csv(
    OUTPUT_OPENSET_CSV,
    index=False,
    encoding="utf-8-sig",
)


OUTPUT_FAILURE_JSON.write_text(
    json.dumps(
        failure_rows,
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)


# =========================================================
# Summary
# =========================================================

summary = {
    "calibration_score_matrix_complete":
        True,

    "missing_representation_policy":
        (
            "A missing component representation is "
            "excluded from that query component's fusion. "
            "Available representations are averaged. "
            "A parent with no gallery component for an "
            "available representation receives normalized "
            "distance 1.0."
        ),

    "performance_evaluated":
        False,

    "test_queries_scored":
        0,

    "unknown_heldout_queries_scored":
        0,

    "calibration_queries":
        int(
            len(
                calibration_query_ids
            )
        ),

    "calibration_components":
        int(
            len(
                cal_query
            )
        ),

    "calibration_gallery_projects":
        int(
            len(
                gallery_projects
            )
        ),

    "visible_gallery_projects_per_query":
        EXPECTED_VISIBLE_PROJECTS,

    "score_rows":
        int(
            len(
                scores
            )
        ),

    "openset_feature_rows":
        int(
            len(
                openset
            )
        ),

    "component_modality_counts": {
        key:
            int(value)

        for key, value
        in modality_counts.items()
    },

    "code_gallery_representation_availability": {
        "OP3": {
            "available":
                code_op3["available"],

            "missing":
                code_op3["missing"],
        },

        "STRUCT": {
            "available":
                code_struct["available"],

            "missing":
                code_struct["missing"],
        },

        "CONTEXT": {
            "available":
                code_context["available"],

            "missing":
                code_context["missing"],
        },
    },

    "code_query_missing_representations":
        query_code_missing,

    "code_query_representation_usage": {
        key:
            int(value)

        for key, value
        in code_query_rep_usage.items()
    },

    "code_query_representation_count_distribution": {
        key:
            int(value)

        for key, value
        in code_query_rep_count_distribution.items()
    },

    "distance_policy": {
        "CODE_BINARY": (
            "minimum gallery-component normalized "
            "Hamming distance per parent for each "
            "available OP3, STRUCT and CONTEXT "
            "representation; missing query "
            "representations are omitted from fusion"
        ),

        "STRUCTURED": (
            "minimum normalized structural SimHash "
            "Hamming distance per parent"
        ),

        "IMAGE": (
            "minimum normalized aHash/dHash/pHash "
            "Hamming and normalized 16-bin luminance "
            "histogram L1 distance per parent"
        ),
    },

    "missing_modality_parent_distance":
        MISSING_PARENT_DISTANCE,

    "hidden_parent_rows_emitted":
        int(
            hidden_parent_rows_emitted
        ),

    "expected_score_rows":
        EXPECTED_SCORE_ROWS,

    "failure_records":
        int(
            len(
                failure_rows
            )
        ),

    "goals_met":
        bool(
            len(scores)
            == EXPECTED_SCORE_ROWS

            and

            len(openset)
            == EXPECTED_COMPONENTS

            and

            hidden_parent_rows_emitted
            == 0

            and

            (
                rows_per_component
                == EXPECTED_VISIBLE_PROJECTS
            ).all()

            and

            len(failure_rows)
            == 0
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
# Result
# =========================================================

print()

print(
    "======================================"
)

print(
    "PHASE 7C RESULT"
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
    "Parent scores:",
    OUTPUT_SCORE_CSV
)

print(
    "Open-set features:",
    OUTPUT_OPENSET_CSV
)

print(
    "Failures:",
    OUTPUT_FAILURE_JSON
)

print(
    "Summary:",
    OUTPUT_SUMMARY_JSON
)