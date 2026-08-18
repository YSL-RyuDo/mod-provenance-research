import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


# =========================================================
# Config
# =========================================================

VISIBLE_SCORE_CSV = Path(
    "results/"
    "phase7c_calibration_component_parent_scores.csv"
)

GALLERY_EVIDENCE_CSV = Path(
    "results/"
    "phase7b_gallery_identity_neutral_evidence.csv"
)

QUERY_EVIDENCE_CSV = Path(
    "results/"
    "phase7b_query_identity_neutral_evidence.csv"
)

QUERY_PROTOCOL_CSV = Path(
    "results/"
    "phase7a_calibration_query_protocol.csv"
)

COMPONENT_GT_CSV = Path(
    "results/"
    "phase7a_calibration_component_ground_truth.csv"
)


OUTPUT_FULL_SCORE_CSV = Path(
    "results/"
    "phase7c2_calibration_full40_parent_scores.csv"
)

OUTPUT_HIDDEN_SCORE_CSV = Path(
    "results/"
    "phase7c2_hidden_parent_absolute_scores.csv"
)

OUTPUT_FAILURE_JSON = Path(
    "results/"
    "phase7c2_failures.json"
)

OUTPUT_SUMMARY_JSON = Path(
    "results/"
    "phase7c2_full_calibration_summary.json"
)


EXPECTED_COMPONENTS = 1260
EXPECTED_VISIBLE_PROJECTS = 39
EXPECTED_FULL_PROJECTS = 40

EXPECTED_VISIBLE_ROWS = (
    EXPECTED_COMPONENTS
    *
    EXPECTED_VISIBLE_PROJECTS
)

EXPECTED_FULL_ROWS = (
    EXPECTED_COMPONENTS
    *
    EXPECTED_FULL_PROJECTS
)

MISSING_PARENT_DISTANCE = 1.0


CALIBRATION_SPLITS = {
    "CALIBRATION_KNOWN",
    "CALIBRATION_BACKGROUND",
}


# =========================================================
# Distance-column definitions
# =========================================================

CODE_COLUMNS = [
    "distance_code_op3",
    "distance_code_struct",
    "distance_code_context",
]

STRUCTURED_COLUMNS = [
    "distance_structured_simhash",
]

IMAGE_COLUMNS = [
    "distance_image_ahash",
    "distance_image_dhash",
    "distance_image_phash",
    "distance_image_hist16",
]


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


def hamming_hex(
    first,
    second,
    bits,
):

    a = clean_text(first)
    b = clean_text(second)

    if not a or not b:
        return None

    return (
        (
            int(a, 16)
            ^
            int(b, 16)
        ).bit_count()
        /
        float(bits)
    )


def parse_hist16(value):

    text = clean_text(value)

    if not text:
        return None

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
            float(item)
            for item in parts
        ],
        dtype=np.float32,
    )


def histogram_distance(
    first,
    second,
):

    a = parse_hist16(
        first
    )

    b = parse_hist16(
        second
    )

    if (
        a is None
        or
        b is None
    ):

        return None

    distance = float(
        np.abs(
            a - b
        ).sum()
        /
        20000.0
    )

    return min(
        1.0,
        max(
            0.0,
            distance,
        ),
    )


def minimum_or_missing(
    values,
):

    finite = [
        float(value)
        for value in values
        if (
            value is not None
            and
            math.isfinite(
                float(value)
            )
        )
    ]

    if not finite:

        return float(
            MISSING_PARENT_DISTANCE
        )

    return float(
        min(
            finite
        )
    )


def relevant_distance_columns(
    modality,
):

    if modality == "CODE_BINARY":
        return CODE_COLUMNS

    if modality == "STRUCTURED":
        return STRUCTURED_COLUMNS

    if modality == "IMAGE":
        return IMAGE_COLUMNS

    raise RuntimeError(
        f"Unsupported modality: "
        f"{modality}"
    )


# =========================================================
# Load
# =========================================================

for path in [
    VISIBLE_SCORE_CSV,
    GALLERY_EVIDENCE_CSV,
    QUERY_EVIDENCE_CSV,
    QUERY_PROTOCOL_CSV,
    COMPONENT_GT_CSV,
]:

    if not path.exists():

        raise FileNotFoundError(
            f"Missing: {path}"
        )


visible_scores = pd.read_csv(
    VISIBLE_SCORE_CSV
)

gallery = pd.read_csv(
    GALLERY_EVIDENCE_CSV
)

query = pd.read_csv(
    QUERY_EVIDENCE_CSV
)

query_protocol = pd.read_csv(
    QUERY_PROTOCOL_CSV
)

component_gt = pd.read_csv(
    COMPONENT_GT_CSV
)


print(
    "======================================"
)

print(
    "Phase 7C2 - Full 40-Parent Calibration"
)

print(
    "======================================"
)


# =========================================================
# Validate visible 39-parent score matrix
# =========================================================

if len(
    visible_scores
) != EXPECTED_VISIBLE_ROWS:

    raise RuntimeError(
        f"Expected {EXPECTED_VISIBLE_ROWS} "
        f"visible score rows, "
        f"got {len(visible_scores)}"
    )


visible_counts = (
    visible_scores
    .groupby(
        [
            "query_id",
            "node_id",
        ]
    )
    .size()
)


if not (
    visible_counts
    == EXPECTED_VISIBLE_PROJECTS
).all():

    raise RuntimeError(
        "Existing Phase 7C matrix is not "
        "39 candidates per component"
    )


# =========================================================
# Calibration-only gallery
# =========================================================

cal_gallery = gallery[
    gallery[
        "frozen_split"
    ].isin(
        CALIBRATION_SPLITS
    )
].copy()


calibration_projects = sorted(
    cal_gallery[
        "fresh_id"
    ].astype(str)
    .unique()
)


if len(
    calibration_projects
) != EXPECTED_FULL_PROJECTS:

    raise RuntimeError(
        f"Expected 40 calibration projects, "
        f"got {len(calibration_projects)}"
    )


project_roles = {}


for project, group in (
    cal_gallery.groupby(
        "fresh_id"
    )
):

    split_values = set(
        group[
            "frozen_split"
        ].astype(str)
    )


    if split_values == {
        "CALIBRATION_KNOWN"
    }:

        project_roles[
            str(project)
        ] = "KNOWN"


    elif split_values == {
        "CALIBRATION_BACKGROUND"
    }:

        project_roles[
            str(project)
        ] = "BACKGROUND"


    else:

        raise RuntimeError(
            f"Unexpected project split values: "
            f"{project} {split_values}"
        )


# =========================================================
# Hidden parent per query
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


if len(
    hidden_parent_by_query
) != 180:

    raise RuntimeError(
        "Expected 180 hidden-parent assignments"
    )


# =========================================================
# Original component GT
# =========================================================

original_parent_by_component = {}


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


    original_parent_by_component[
        key
    ] = clean_text(
        row.original_source_parent
    )


if len(
    original_parent_by_component
) != EXPECTED_COMPONENTS:

    raise RuntimeError(
        "Expected 1260 component GT rows"
    )


# =========================================================
# Calibration query evidence only
# =========================================================

calibration_query_ids = set(
    hidden_parent_by_query.keys()
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
        f"calibration query components, "
        f"got {len(cal_query)}"
    )


query_map = {}


for row in cal_query.itertuples(
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

    query_map[
        key
    ] = row


# =========================================================
# Parent/modality gallery cache
# =========================================================

gallery_cache = {}


for (
    fresh_id,
    modality
), group in cal_gallery.groupby(
    [
        "fresh_id",
        "modality",
    ],
    sort=False,
):

    gallery_cache[
        (
            str(fresh_id),
            str(modality),
        )
    ] = group.copy()


# =========================================================
# Hidden-parent absolute distance functions
# =========================================================

def hidden_code_distances(
    query_row,
    parent_gallery,
):

    result = {
        column: np.nan
        for column in CODE_COLUMNS
    }


    query_representations = [
        (
            "distance_code_op3",
            "code_op3_simhash128",
        ),
        (
            "distance_code_struct",
            "code_struct_simhash128",
        ),
        (
            "distance_code_context",
            "code_context_simhash128",
        ),
    ]


    for output_column, source_column in (
        query_representations
    ):

        query_value = clean_text(
            getattr(
                query_row,
                source_column,
                "",
            )
        )


        # Missing QUERY representation:
        # omit this representation from fusion.
        if not query_value:

            result[
                output_column
            ] = np.nan

            continue


        distances = []


        if parent_gallery is not None:

            for gallery_row in (
                parent_gallery.itertuples(
                    index=False
                )
            ):

                gallery_value = clean_text(
                    getattr(
                        gallery_row,
                        source_column,
                        "",
                    )
                )


                distance = hamming_hex(
                    query_value,
                    gallery_value,
                    128,
                )


                if distance is not None:

                    distances.append(
                        distance
                    )


        result[
            output_column
        ] = minimum_or_missing(
            distances
        )


    return result


def hidden_structured_distances(
    query_row,
    parent_gallery,
):

    query_value = clean_text(
        getattr(
            query_row,
            "structured_simhash128",
            "",
        )
    )


    if not query_value:

        raise RuntimeError(
            "Missing structured query signature"
        )


    distances = []


    if parent_gallery is not None:

        for gallery_row in (
            parent_gallery.itertuples(
                index=False
            )
        ):

            distance = hamming_hex(
                query_value,
                getattr(
                    gallery_row,
                    "structured_simhash128",
                    "",
                ),
                128,
            )


            if distance is not None:

                distances.append(
                    distance
                )


    return {
        "distance_structured_simhash":
            minimum_or_missing(
                distances
            )
    }


def hidden_image_distances(
    query_row,
    parent_gallery,
):

    hash_specs = [
        (
            "distance_image_ahash",
            "image_ahash64",
        ),
        (
            "distance_image_dhash",
            "image_dhash64",
        ),
        (
            "distance_image_phash",
            "image_phash64",
        ),
    ]


    result = {}


    for output_column, source_column in (
        hash_specs
    ):

        query_value = clean_text(
            getattr(
                query_row,
                source_column,
                "",
            )
        )


        if not query_value:

            raise RuntimeError(
                f"Missing image query signature: "
                f"{source_column}"
            )


        distances = []


        if parent_gallery is not None:

            for gallery_row in (
                parent_gallery.itertuples(
                    index=False
                )
            ):

                distance = hamming_hex(
                    query_value,
                    getattr(
                        gallery_row,
                        source_column,
                        "",
                    ),
                    64,
                )


                if distance is not None:

                    distances.append(
                        distance
                    )


        result[
            output_column
        ] = minimum_or_missing(
            distances
        )


    histogram_distances = []


    if parent_gallery is not None:

        for gallery_row in (
            parent_gallery.itertuples(
                index=False
            )
        ):

            distance = histogram_distance(
                getattr(
                    query_row,
                    "image_hist16",
                    "",
                ),
                getattr(
                    gallery_row,
                    "image_hist16",
                    "",
                ),
            )


            if distance is not None:

                histogram_distances.append(
                    distance
                )


    result[
        "distance_image_hist16"
    ] = minimum_or_missing(
        histogram_distances
    )


    return result


# =========================================================
# Compute one hidden candidate per component
# =========================================================

hidden_rows = []

failure_rows = []


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


for index, row in enumerate(
    cal_query.itertuples(
        index=False
    ),
    start=1,
):

    if (
        index == 1
        or
        index % 100 == 0
    ):

        print(
            f"hidden score "
            f"{index}/"
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


    parent_gallery = (
        gallery_cache.get(
            (
                hidden_parent,
                modality,
            )
        )
    )


    if modality == "CODE_BINARY":

        distances = hidden_code_distances(
            row,
            parent_gallery,
        )


    elif modality == "STRUCTURED":

        distances = (
            hidden_structured_distances(
                row,
                parent_gallery,
            )
        )


    elif modality == "IMAGE":

        distances = hidden_image_distances(
            row,
            parent_gallery,
        )


    else:

        raise RuntimeError(
            f"Unsupported modality: "
            f"{modality}"
        )


    relevant_columns = (
        relevant_distance_columns(
            modality
        )
    )


    available_values = [
        float(
            distances[
                column
            ]
        )

        for column in relevant_columns

        if (
            column in distances

            and

            pd.notna(
                distances[
                    column
                ]
            )
        )
    ]


    if not available_values:

        raise RuntimeError(
            f"{query_id}/{node_id}: "
            f"no usable representation"
        )


    fused_distance = float(
        np.mean(
            available_values
        )
    )


    component_key = (
        query_id,
        node_id,
    )


    original_parent = (
        original_parent_by_component[
            component_key
        ]
    )


    output = {
        "query_id":
            query_id,

        "node_id":
            node_id,

        "modality":
            modality,

        "candidate_parent":
            hidden_parent,

        "candidate_role":
            project_roles.get(
                hidden_parent,
                "",
            ),

        "candidate_rank":
            0,

        "fused_parent_distance":
            fused_distance,

        "mean_regret":
            0.0,

        "representation_count":
            int(
                len(
                    available_values
                )
            ),

        "is_pseudo_unknown_component":
            bool(
                original_parent
                == hidden_parent
            ),

        "candidate_was_hidden_in_pseudo_protocol":
            True,

        "original_source_parent":
            original_parent,

        "is_original_true_parent_candidate":
            bool(
                hidden_parent
                == original_parent
            ),
    }


    for column in (
        CODE_COLUMNS
        +
        STRUCTURED_COLUMNS
        +
        IMAGE_COLUMNS
    ):

        output[
            column
        ] = distances.get(
            column,
            np.nan,
        )


    hidden_rows.append(
        output
    )


hidden_df = pd.DataFrame(
    hidden_rows
)


if len(
    hidden_df
) != EXPECTED_COMPONENTS:

    raise RuntimeError(
        "Expected 1260 hidden-parent rows"
    )


# =========================================================
# Prepare visible rows
# =========================================================

visible = visible_scores.copy()


visible[
    "candidate_was_hidden_in_pseudo_protocol"
] = False


original_parent_values = []

true_candidate_values = []


for row in visible.itertuples(
    index=False
):

    component_key = (
        clean_text(
            row.query_id
        ),
        clean_text(
            row.node_id
        ),
    )


    original_parent = (
        original_parent_by_component[
            component_key
        ]
    )


    candidate_parent = clean_text(
        row.candidate_parent
    )


    original_parent_values.append(
        original_parent
    )

    true_candidate_values.append(
        bool(
            candidate_parent
            == original_parent
        )
    )


visible[
    "original_source_parent"
] = (
    original_parent_values
)


visible[
    "is_original_true_parent_candidate"
] = (
    true_candidate_values
)


# =========================================================
# Ensure all representation columns exist
# =========================================================

all_distance_columns = (
    CODE_COLUMNS
    +
    STRUCTURED_COLUMNS
    +
    IMAGE_COLUMNS
)


for column in all_distance_columns:

    if column not in visible.columns:

        visible[
            column
        ] = np.nan


    if column not in hidden_df.columns:

        hidden_df[
            column
        ] = np.nan


# =========================================================
# Combine 39 visible + 1 hidden
# =========================================================

full = pd.concat(
    [
        visible,
        hidden_df,
    ],
    ignore_index=True,
    sort=False,
)


if len(full) != EXPECTED_FULL_ROWS:

    raise RuntimeError(
        f"Expected {EXPECTED_FULL_ROWS} "
        f"combined rows, "
        f"got {len(full)}"
    )


# =========================================================
# Recompute fused distance / MEAN_REGRET / rank
#
# IMPORTANT:
# Phase 7C regret used only 39 visible parents.
#
# Here we recompute regret against all 40 calibration
# projects for known-only K calibration.
# =========================================================

recomputed_groups = []


for group_index, (
    component_key,
    group
) in enumerate(
    full.groupby(
        [
            "query_id",
            "node_id",
        ],
        sort=False,
    ),
    start=1,
):

    if (
        group_index == 1
        or
        group_index % 100 == 0
    ):

        print(
            f"recompute "
            f"{group_index}/"
            f"{EXPECTED_COMPONENTS}"
        )


    group = group.copy()


    if len(group) != EXPECTED_FULL_PROJECTS:

        raise RuntimeError(
            f"{component_key}: "
            f"expected 40 candidates, "
            f"got {len(group)}"
        )


    candidate_set = set(
        group[
            "candidate_parent"
        ].astype(str)
    )


    if len(
        candidate_set
    ) != EXPECTED_FULL_PROJECTS:

        raise RuntimeError(
            f"{component_key}: duplicate "
            f"candidate parent"
        )


    modality_values = set(
        group[
            "modality"
        ].astype(str)
    )


    if len(
        modality_values
    ) != 1:

        raise RuntimeError(
            "Mixed modality inside component"
        )


    modality = next(
        iter(
            modality_values
        )
    )


    possible_columns = (
        relevant_distance_columns(
            modality
        )
    )


    # A query-side missing representation creates
    # NaN for every candidate in that column.
    available_columns = [
        column
        for column in possible_columns
        if (
            column in group.columns

            and

            group[
                column
            ].notna().any()
        )
    ]


    if not available_columns:

        raise RuntimeError(
            f"{component_key}: no available "
            f"distance representation"
        )


    # -----------------------------------------------------
    # Absolute fused distance
    # -----------------------------------------------------

    group[
        "fused_parent_distance"
    ] = (
        group[
            available_columns
        ]
        .astype(float)
        .mean(
            axis=1
        )
    )


    # -----------------------------------------------------
    # Full-40 MEAN_REGRET
    # -----------------------------------------------------

    regret_columns = []


    for column in available_columns:

        minimum_value = float(
            group[
                column
            ]
            .astype(float)
            .min()
        )


        regret_column = (
            "__regret_"
            + column
        )


        group[
            regret_column
        ] = (
            group[
                column
            ].astype(float)
            -
            minimum_value
        )


        regret_columns.append(
            regret_column
        )


    group[
        "mean_regret"
    ] = (
        group[
            regret_columns
        ]
        .mean(
            axis=1
        )
    )


    group[
        "representation_count"
    ] = int(
        len(
            available_columns
        )
    )


    # -----------------------------------------------------
    # Full-40 candidate rank
    # -----------------------------------------------------

    order = (
        group[
            [
                "candidate_parent",
                "fused_parent_distance",
                "mean_regret",
            ]
        ]
        .sort_values(
            [
                "fused_parent_distance",
                "mean_regret",
                "candidate_parent",
            ],
            kind="stable",
        )
        .index
        .tolist()
    )


    rank_map = {
        row_index:
            rank

        for rank, row_index
        in enumerate(
            order,
            start=1,
        )
    }


    group[
        "candidate_rank"
    ] = [
        rank_map[
            row_index
        ]

        for row_index in (
            group.index
        )
    ]


    group = group.drop(
        columns=regret_columns
    )


    recomputed_groups.append(
        group
    )


full40 = pd.concat(
    recomputed_groups,
    ignore_index=True,
)


# =========================================================
# Final safety checks
# =========================================================

rows_per_component = (
    full40
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
    == EXPECTED_FULL_PROJECTS
).all():

    raise RuntimeError(
        "Not every component has "
        "40 candidate parents"
    )


projects_per_component = (
    full40
    .groupby(
        [
            "query_id",
            "node_id",
        ]
    )[
        "candidate_parent"
    ]
    .nunique()
)


if not (
    projects_per_component
    == EXPECTED_FULL_PROJECTS
).all():

    raise RuntimeError(
        "Not every component has "
        "40 distinct candidate projects"
    )


hidden_rows_per_component = (
    full40[
        full40[
            "candidate_was_hidden_in_pseudo_protocol"
        ].map(
            as_bool
        )
    ]
    .groupby(
        [
            "query_id",
            "node_id",
        ]
    )
    .size()
)


if not (
    hidden_rows_per_component
    == 1
).all():

    raise RuntimeError(
        "Every component must recover "
        "exactly one hidden-parent row"
    )


true_rows_per_component = (
    full40[
        full40[
            "is_original_true_parent_candidate"
        ].map(
            as_bool
        )
    ]
    .groupby(
        [
            "query_id",
            "node_id",
        ]
    )
    .size()
)


if not (
    true_rows_per_component
    == 1
).all():

    raise RuntimeError(
        "Every component must have "
        "exactly one true-parent candidate"
    )


if not np.isfinite(
    full40[
        "fused_parent_distance"
    ].to_numpy(
        dtype=float
    )
).all():

    raise RuntimeError(
        "Non-finite fused distance"
    )


if not np.isfinite(
    full40[
        "mean_regret"
    ].to_numpy(
        dtype=float
    )
).all():

    raise RuntimeError(
        "Non-finite MEAN_REGRET"
    )


# =========================================================
# Save
# =========================================================

OUTPUT_FULL_SCORE_CSV.parent.mkdir(
    parents=True,
    exist_ok=True,
)


hidden_df.to_csv(
    OUTPUT_HIDDEN_SCORE_CSV,
    index=False,
    encoding="utf-8-sig",
)


full40.to_csv(
    OUTPUT_FULL_SCORE_CSV,
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
    "full40_calibration_matrix_complete":
        True,

    "performance_evaluated":
        False,

    "test_queries_scored":
        0,

    "unknown_heldout_queries_scored":
        0,

    "calibration_components":
        int(
            EXPECTED_COMPONENTS
        ),

    "pseudo_unknown_visible_candidates_per_component":
        int(
            EXPECTED_VISIBLE_PROJECTS
        ),

    "full_known_candidates_per_component":
        int(
            EXPECTED_FULL_PROJECTS
        ),

    "existing_visible_score_rows":
        int(
            len(
                visible_scores
            )
        ),

    "recovered_hidden_parent_rows":
        int(
            len(
                hidden_df
            )
        ),

    "full40_score_rows":
        int(
            len(
                full40
            )
        ),

    "expected_full40_score_rows":
        int(
            EXPECTED_FULL_ROWS
        ),

    "full40_regret_recomputed":
        True,

    "calibration_views": {
        "PSEUDO_UNKNOWN_39": (
            "Phase 7C matrix. One true known parent "
            "is absent and acts as UNKNOWN. Used for "
            "open-set threshold calibration."
        ),

        "KNOWN_ONLY_40": (
            "Phase 7C2 matrix. The hidden parent is "
            "restored and MEAN_REGRET/rank are "
            "recomputed over all 40 calibration "
            "projects. Used for known-only K=1/2/3 "
            "parent-set and proliferation-penalty "
            "calibration."
        ),
    },

    "true_parent_candidate_rows":
        int(
            full40[
                "is_original_true_parent_candidate"
            ].map(
                as_bool
            ).sum()
        ),

    "hidden_candidate_rows":
        int(
            full40[
                "candidate_was_hidden_in_pseudo_protocol"
            ].map(
                as_bool
            ).sum()
        ),

    "failure_records":
        int(
            len(
                failure_rows
            )
        ),

    "goals_met":
        bool(
            len(
                full40
            )
            == EXPECTED_FULL_ROWS

            and

            len(
                hidden_df
            )
            == EXPECTED_COMPONENTS

            and

            (
                rows_per_component
                == EXPECTED_FULL_PROJECTS
            ).all()

            and

            (
                projects_per_component
                == EXPECTED_FULL_PROJECTS
            ).all()

            and

            (
                true_rows_per_component
                == 1
            ).all()

            and

            len(
                failure_rows
            )
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
# Print
# =========================================================

print()

print(
    "======================================"
)

print(
    "PHASE 7C2 RESULT"
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
    "Full 40 scores:",
    OUTPUT_FULL_SCORE_CSV
)

print(
    "Hidden rows:",
    OUTPUT_HIDDEN_SCORE_CSV
)

print(
    "Failures:",
    OUTPUT_FAILURE_JSON
)

print(
    "Summary:",
    OUTPUT_SUMMARY_JSON
)