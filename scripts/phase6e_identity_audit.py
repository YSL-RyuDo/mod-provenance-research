import hashlib
import json
from collections import defaultdict
from pathlib import Path

import pandas as pd


# =========================================================
# Config
# =========================================================

CURRENT_CSV = Path(
    "data/fresh_registry/"
    "fresh_current_component_registry_filtered.csv"
)

HISTORICAL_CSV = Path(
    "data/fresh_registry/"
    "fresh_historical_component_registry_filtered.csv"
)

SPLIT_CSV = Path(
    "results/phase6c_project_split.csv"
)

OUTPUT_AUDIT_CSV = Path(
    "results/"
    "phase6e_historical_identity_audit.csv"
)

OUTPUT_HARD_CSV = Path(
    "results/"
    "phase6e_hard_candidate_catalog.csv"
)

OUTPUT_SUMMARY_JSON = Path(
    "results/"
    "phase6e_identity_summary.json"
)


CALIBRATION_GALLERY_SPLITS = {
    "CALIBRATION_KNOWN",
    "CALIBRATION_BACKGROUND",
}

TEST_GALLERY_SPLITS = {
    "TEST_KNOWN",
    "TEST_BACKGROUND",
}

QUERY_SPLITS = {
    "CALIBRATION_KNOWN",
    "TEST_KNOWN",
    "UNKNOWN_HELDOUT",
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


def normalize_path(value):

    return (
        clean_text(value)
        .replace("\\", "/")
    )


def basename_key(
    relative_path
):

    path = normalize_path(
        relative_path
    )

    if not path:
        return ""

    return path.rsplit(
        "/",
        1,
    )[-1]


def outer_class_key(
    relative_path,
    modality,
):

    if modality != "CODE_BINARY":
        return ""

    base = basename_key(
        relative_path
    )

    if not base.lower().endswith(
        ".class"
    ):
        return ""

    name = base[:-6]

    # Foo$Inner.class -> Foo
    return name.split(
        "$",
        1,
    )[0]


def sha256_file(
    path
):

    digest = hashlib.sha256()

    with open(
        path,
        "rb",
    ) as f:

        while True:

            chunk = f.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest()


def stage_for_split(
    split_name
):

    if split_name == "CALIBRATION_KNOWN":
        return "CALIBRATION"

    if split_name in {
        "TEST_KNOWN",
        "UNKNOWN_HELDOUT",
    }:
        return "TEST"

    return None


# =========================================================
# Load
# =========================================================

for path in [
    CURRENT_CSV,
    HISTORICAL_CSV,
    SPLIT_CSV,
]:

    if not path.exists():

        raise FileNotFoundError(
            f"Missing: {path}"
        )


current = pd.read_csv(
    CURRENT_CSV
)

historical = pd.read_csv(
    HISTORICAL_CSV
)

splits = pd.read_csv(
    SPLIT_CSV
)


print(
    "======================================"
)

print(
    "Phase 6E - Historical Identity Audit"
)

print(
    "======================================"
)


# =========================================================
# Split map
# =========================================================

split_table = (
    splits[
        [
            "fresh_id",
            "frozen_split",
            "role",
        ]
    ]
    .drop_duplicates(
        subset=[
            "fresh_id"
        ]
    )
)


if split_table[
    "fresh_id"
].nunique() != 120:

    raise RuntimeError(
        "Expected 120 frozen projects"
    )


split_map = dict(
    zip(
        split_table[
            "fresh_id"
        ].astype(str),

        split_table[
            "frozen_split"
        ].astype(str),
    )
)


current[
    "fresh_id"
] = current[
    "fresh_id"
].astype(str)

historical[
    "fresh_id"
] = historical[
    "fresh_id"
].astype(str)


current[
    "frozen_split"
] = current[
    "fresh_id"
].map(
    split_map
)

historical[
    "frozen_split"
] = historical[
    "fresh_id"
].map(
    split_map
)


if current[
    "frozen_split"
].isna().any():

    raise RuntimeError(
        "Current registry contains "
        "unassigned project"
    )


if historical[
    "frozen_split"
].isna().any():

    raise RuntimeError(
        "Historical registry contains "
        "unassigned project"
    )


# =========================================================
# Normalize identity fields
#
# IMPORTANT:
# Do NOT use column names beginning with "_".
# pandas.itertuples() renames them internally.
# =========================================================

for df in [
    current,
    historical,
]:

    df[
        "norm_path"
    ] = df[
        "relative_path"
    ].map(
        normalize_path
    )

    df[
        "norm_basename"
    ] = df[
        "relative_path"
    ].map(
        basename_key
    )

    df[
        "norm_outer_class"
    ] = [
        outer_class_key(
            path,
            modality,
        )

        for path, modality in zip(
            df[
                "relative_path"
            ],

            df[
                "modality"
            ],
        )
    ]


# =========================================================
# Own-current indexes
#
# UNKNOWN current releases are used ONLY to characterize
# their own historical drift.
#
# They are NOT inserted into the TEST gallery.
# =========================================================

own_sha = set()

own_path = set()

own_basename = set()

own_outer = set()


for row in current.itertuples(
    index=False
):

    fresh_id = clean_text(
        row.fresh_id
    )

    modality = clean_text(
        row.modality
    )

    digest = clean_text(
        row.component_sha256
    )

    path = clean_text(
        row.norm_path
    )

    basename = clean_text(
        row.norm_basename
    )

    outer = clean_text(
        row.norm_outer_class
    )


    own_sha.add(
        (
            fresh_id,
            modality,
            digest,
        )
    )


    own_path.add(
        (
            fresh_id,
            modality,
            path,
        )
    )


    own_basename.add(
        (
            fresh_id,
            modality,
            basename,
        )
    )


    if (
        modality == "CODE_BINARY"
        and
        outer
    ):

        own_outer.add(
            (
                fresh_id,
                modality,
                outer,
            )
        )


# =========================================================
# Stage-specific gallery indexes
# =========================================================

def new_indexes():

    return {
        "sha":
            defaultdict(set),

        "path":
            defaultdict(set),

        "basename":
            defaultdict(set),

        "outer":
            defaultdict(set),
    }


gallery_indexes = {
    "CALIBRATION":
        new_indexes(),

    "TEST":
        new_indexes(),
}


gallery_projects = {
    "CALIBRATION":
        set(),

    "TEST":
        set(),
}


for row in current.itertuples(
    index=False
):

    fresh_id = clean_text(
        row.fresh_id
    )

    split_name = clean_text(
        row.frozen_split
    )

    modality = clean_text(
        row.modality
    )

    digest = clean_text(
        row.component_sha256
    )

    path = clean_text(
        row.norm_path
    )

    basename = clean_text(
        row.norm_basename
    )

    outer = clean_text(
        row.norm_outer_class
    )


    stages = []


    if (
        split_name
        in CALIBRATION_GALLERY_SPLITS
    ):

        stages.append(
            "CALIBRATION"
        )


    if (
        split_name
        in TEST_GALLERY_SPLITS
    ):

        stages.append(
            "TEST"
        )


    for stage in stages:

        gallery_projects[
            stage
        ].add(
            fresh_id
        )


        indexes = (
            gallery_indexes[
                stage
            ]
        )


        indexes[
            "sha"
        ][
            (
                modality,
                digest,
            )
        ].add(
            fresh_id
        )


        indexes[
            "path"
        ][
            (
                modality,
                path,
            )
        ].add(
            fresh_id
        )


        indexes[
            "basename"
        ][
            (
                modality,
                basename,
            )
        ].add(
            fresh_id
        )


        if (
            modality == "CODE_BINARY"
            and
            outer
        ):

            indexes[
                "outer"
            ][
                (
                    modality,
                    outer,
                )
            ].add(
                fresh_id
            )


# =========================================================
# Gallery safety checks
# =========================================================

unknown_projects = set(
    split_table[
        split_table[
            "frozen_split"
        ]
        == "UNKNOWN_HELDOUT"
    ][
        "fresh_id"
    ].astype(str)
)


if (
    unknown_projects
    &
    gallery_projects[
        "TEST"
    ]
):

    raise RuntimeError(
        "UNKNOWN leakage into TEST gallery"
    )


print(
    "Calibration gallery projects:",
    len(
        gallery_projects[
            "CALIBRATION"
        ]
    )
)

print(
    "Test gallery projects:",
    len(
        gallery_projects[
            "TEST"
        ]
    )
)

print(
    "Held-out unknown projects:",
    len(
        unknown_projects
    )
)


# =========================================================
# Historical TARGET queries only
# =========================================================

queries = historical[
    historical[
        "frozen_split"
    ].isin(
        QUERY_SPLITS
    )
].copy()


print(
    "Historical TARGET components:",
    len(
        queries
    )
)


# =========================================================
# Audit
# =========================================================

audit_rows = []


for query_index, row in enumerate(
    queries.itertuples(
        index=False
    ),
    start=1,
):

    if (
        query_index % 10000
        == 0
    ):

        print(
            "processed:",
            query_index,
            "/",
            len(
                queries
            ),
        )


    fresh_id = clean_text(
        row.fresh_id
    )

    split_name = clean_text(
        row.frozen_split
    )

    stage = stage_for_split(
        split_name
    )


    if stage is None:
        continue


    modality = clean_text(
        row.modality
    )

    digest = clean_text(
        row.component_sha256
    )

    path = clean_text(
        row.norm_path
    )

    basename = clean_text(
        row.norm_basename
    )

    outer = clean_text(
        row.norm_outer_class
    )


    # -----------------------------------------------------
    # Own-current drift
    # -----------------------------------------------------

    own_exact_sha = (
        (
            fresh_id,
            modality,
            digest,
        )
        in own_sha
    )


    own_same_path = (
        (
            fresh_id,
            modality,
            path,
        )
        in own_path
    )


    own_same_basename = (
        (
            fresh_id,
            modality,
            basename,
        )
        in own_basename
    )


    own_same_outer = False


    if (
        modality == "CODE_BINARY"
        and
        outer
    ):

        own_same_outer = (
            (
                fresh_id,
                modality,
                outer,
            )
            in own_outer
        )


    # -----------------------------------------------------
    # Stage gallery candidates
    # -----------------------------------------------------

    indexes = (
        gallery_indexes[
            stage
        ]
    )


    sha_candidates = set(
        indexes[
            "sha"
        ].get(
            (
                modality,
                digest,
            ),
            set(),
        )
    )


    path_candidates = set(
        indexes[
            "path"
        ].get(
            (
                modality,
                path,
            ),
            set(),
        )
    )


    basename_candidates = set(
        indexes[
            "basename"
        ].get(
            (
                modality,
                basename,
            ),
            set(),
        )
    )


    outer_candidates = set()


    if (
        modality == "CODE_BINARY"
        and
        outer
    ):

        outer_candidates = set(
            indexes[
                "outer"
            ].get(
                (
                    modality,
                    outer,
                ),
                set(),
            )
        )


    is_unknown = (
        split_name
        == "UNKNOWN_HELDOUT"
    )


    is_known = (
        not is_unknown
    )


    # -----------------------------------------------------
    # Hard-track definitions
    # -----------------------------------------------------

    changed_from_own_current = (
        not own_exact_sha
    )


    hard_masked = (
        changed_from_own_current
    )


    strict_path_failed = (
        changed_from_own_current
        and
        not own_same_path
    )


    audit_rows.append({
        "fresh_id":
            fresh_id,

        "project_id":
            clean_text(
                row.project_id
            ),

        "slug":
            clean_text(
                row.slug
            ),

        "title":
            clean_text(
                row.title
            ),

        "frozen_split":
            split_name,

        "evaluation_stage":
            stage,

        "known_source":
            bool(
                is_known
            ),

        "version_id":
            clean_text(
                row.version_id
            ),

        "version_number":
            clean_text(
                row.version_number
            ),

        "jar_filename":
            clean_text(
                row.jar_filename
            ),

        "modality":
            modality,

        "relative_path":
            path,

        "basename":
            basename,

        "outer_class_name":
            outer,

        "size_bytes":
            int(
                row.size_bytes
            ),

        "component_sha256":
            digest,

        # Own-current drift
        "own_current_exact_sha":
            bool(
                own_exact_sha
            ),

        "own_current_same_path":
            bool(
                own_same_path
            ),

        "own_current_same_basename":
            bool(
                own_same_basename
            ),

        "own_current_same_outer_class":
            bool(
                own_same_outer
            ),

        "changed_from_own_current":
            bool(
                changed_from_own_current
            ),

        # Gallery candidate counts
        "gallery_sha_candidate_count":
            int(
                len(
                    sha_candidates
                )
            ),

        "gallery_path_candidate_count":
            int(
                len(
                    path_candidates
                )
            ),

        "gallery_basename_candidate_count":
            int(
                len(
                    basename_candidates
                )
            ),

        "gallery_outer_candidate_count":
            int(
                len(
                    outer_candidates
                )
            ),

        # Known source hits
        "gallery_sha_true_parent_hit":
            bool(
                is_known
                and
                fresh_id
                in sha_candidates
            ),

        "gallery_path_true_parent_hit":
            bool(
                is_known
                and
                fresh_id
                in path_candidates
            ),

        "gallery_basename_true_parent_hit":
            bool(
                is_known
                and
                fresh_id
                in basename_candidates
            ),

        "gallery_outer_true_parent_hit":
            bool(
                is_known
                and
                fresh_id
                in outer_candidates
            ),

        # UNKNOWN collisions
        "unknown_sha_collision":
            bool(
                is_unknown
                and
                len(
                    sha_candidates
                ) > 0
            ),

        "unknown_path_collision":
            bool(
                is_unknown
                and
                len(
                    path_candidates
                ) > 0
            ),

        "unknown_basename_collision":
            bool(
                is_unknown
                and
                len(
                    basename_candidates
                ) > 0
            ),

        "unknown_outer_collision":
            bool(
                is_unknown
                and
                len(
                    outer_candidates
                ) > 0
            ),

        "hard_masked_candidate":
            bool(
                hard_masked
            ),

        "strict_path_failed_candidate":
            bool(
                strict_path_failed
            ),
    })


audit = pd.DataFrame(
    audit_rows
)


# =========================================================
# Save audit
# =========================================================

audit.to_csv(
    OUTPUT_AUDIT_CSV,
    index=False,
    encoding="utf-8-sig",
)


# =========================================================
# Hard candidate catalog
# =========================================================

hard = audit[
    audit[
        "hard_masked_candidate"
    ]
].copy()


hard.to_csv(
    OUTPUT_HARD_CSV,
    index=False,
    encoding="utf-8-sig",
)


# =========================================================
# Summary helpers
# =========================================================

def safe_rate(
    series
):

    if len(series) == 0:
        return None

    return float(
        series.astype(
            bool
        ).mean()
    )


def group_summary(
    group
):

    result = {
        "components":
            int(
                len(group)
            ),

        "own_exact_sha_rate":
            safe_rate(
                group[
                    "own_current_exact_sha"
                ]
            ),

        "own_same_path_rate":
            safe_rate(
                group[
                    "own_current_same_path"
                ]
            ),

        "hard_masked_candidates":
            int(
                group[
                    "hard_masked_candidate"
                ].sum()
            ),

        "hard_masked_rate":
            safe_rate(
                group[
                    "hard_masked_candidate"
                ]
            ),

        "strict_path_failed_candidates":
            int(
                group[
                    "strict_path_failed_candidate"
                ].sum()
            ),

        "strict_path_failed_rate":
            safe_rate(
                group[
                    "strict_path_failed_candidate"
                ]
            ),
    }


    known = group[
        group[
            "known_source"
        ]
    ]


    if len(known):

        result[
            "known_sha_true_parent_rate"
        ] = safe_rate(
            known[
                "gallery_sha_true_parent_hit"
            ]
        )

        result[
            "known_path_true_parent_rate"
        ] = safe_rate(
            known[
                "gallery_path_true_parent_hit"
            ]
        )

        result[
            "known_basename_true_parent_rate"
        ] = safe_rate(
            known[
                "gallery_basename_true_parent_hit"
            ]
        )


        code_known = known[
            known[
                "modality"
            ]
            == "CODE_BINARY"
        ]


        result[
            "known_outer_class_true_parent_rate_code"
        ] = (
            safe_rate(
                code_known[
                    "gallery_outer_true_parent_hit"
                ]
            )
            if len(code_known)
            else None
        )


    unknown = group[
        ~group[
            "known_source"
        ]
    ]


    if len(unknown):

        result[
            "unknown_sha_collision_rate"
        ] = safe_rate(
            unknown[
                "unknown_sha_collision"
            ]
        )

        result[
            "unknown_path_collision_rate"
        ] = safe_rate(
            unknown[
                "unknown_path_collision"
            ]
        )

        result[
            "unknown_basename_collision_rate"
        ] = safe_rate(
            unknown[
                "unknown_basename_collision"
            ]
        )


        code_unknown = unknown[
            unknown[
                "modality"
            ]
            == "CODE_BINARY"
        ]


        result[
            "unknown_outer_collision_rate_code"
        ] = (
            safe_rate(
                code_unknown[
                    "unknown_outer_collision"
                ]
            )
            if len(code_unknown)
            else None
        )


    return result


# =========================================================
# Summary by split
# =========================================================

by_split = {}


for split_name, group in (
    audit.groupby(
        "frozen_split"
    )
):

    by_split[
        str(
            split_name
        )
    ] = group_summary(
        group
    )


# =========================================================
# Summary by split + modality
# =========================================================

by_split_modality = {}


for (
    split_name,
    modality
), group in (
    audit.groupby(
        [
            "frozen_split",
            "modality",
        ]
    )
):

    by_split_modality.setdefault(
        str(
            split_name
        ),
        {},
    )


    by_split_modality[
        str(
            split_name
        )
    ][
        str(
            modality
        )
    ] = group_summary(
        group
    )


# =========================================================
# Distinct source availability
# =========================================================

hard_parent_counts = {}


for split_name, group in (
    hard.groupby(
        "frozen_split"
    )
):

    hard_parent_counts[
        str(
            split_name
        )
    ] = {
        "distinct_parent_projects":
            int(
                group[
                    "fresh_id"
                ].nunique()
            ),

        "hard_components":
            int(
                len(group)
            ),

        "strict_path_failed_components":
            int(
                group[
                    "strict_path_failed_candidate"
                ].sum()
            ),

        "parents_with_code_hard_components":
            int(
                group[
                    group[
                        "modality"
                    ]
                    == "CODE_BINARY"
                ][
                    "fresh_id"
                ].nunique()
            ),

        "parents_with_structured_hard_components":
            int(
                group[
                    group[
                        "modality"
                    ]
                    == "STRUCTURED"
                ][
                    "fresh_id"
                ].nunique()
            ),

        "parents_with_image_hard_components":
            int(
                group[
                    group[
                        "modality"
                    ]
                    == "IMAGE"
                ][
                    "fresh_id"
                ].nunique()
            ),
    }


# =========================================================
# Final summary
# =========================================================

summary = {
    "identity_audit_frozen":
        True,

    "path_identity_allowed_in_final_method":
        False,

    "hard_masked_definition":
        (
            "historical component whose exact SHA-256 "
            "does not occur in its own current release; "
            "path/name identity is not exposed to the "
            "final attribution method"
        ),

    "strict_path_failed_definition":
        (
            "HARD_MASKED component whose same full "
            "relative path also does not occur in its "
            "own current release"
        ),

    "current_filtered_components":
        int(
            len(current)
        ),

    "historical_filtered_components":
        int(
            len(historical)
        ),

    "historical_target_components_audited":
        int(
            len(audit)
        ),

    "hard_masked_components":
        int(
            len(hard)
        ),

    "strict_path_failed_components":
        int(
            hard[
                "strict_path_failed_candidate"
            ].sum()
        ),

    "calibration_gallery_projects":
        int(
            len(
                gallery_projects[
                    "CALIBRATION"
                ]
            )
        ),

    "test_gallery_projects":
        int(
            len(
                gallery_projects[
                    "TEST"
                ]
            )
        ),

    "unknown_heldout_projects":
        int(
            len(
                unknown_projects
            )
        ),

    "unknown_projects_in_test_gallery":
        int(
            len(
                unknown_projects
                &
                gallery_projects[
                    "TEST"
                ]
            )
        ),

    "by_split":
        by_split,

    "by_split_modality":
        by_split_modality,

    "hard_parent_availability":
        hard_parent_counts,

    "input_current_sha256":
        sha256_file(
            CURRENT_CSV
        ),

    "input_historical_sha256":
        sha256_file(
            HISTORICAL_CSV
        ),

    "input_split_sha256":
        sha256_file(
            SPLIT_CSV
        ),

    "audit_csv_sha256":
        sha256_file(
            OUTPUT_AUDIT_CSV
        ),

    "hard_catalog_sha256":
        sha256_file(
            OUTPUT_HARD_CSV
        ),

    "goals_met":
        bool(
            len(audit) > 0
            and
            len(hard) > 0
            and
            len(
                unknown_projects
                &
                gallery_projects[
                    "TEST"
                ]
            ) == 0
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
    "PHASE 6E RESULT"
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
    "Audit :",
    OUTPUT_AUDIT_CSV
)

print(
    "Hard  :",
    OUTPUT_HARD_CSV
)

print(
    "JSON  :",
    OUTPUT_SUMMARY_JSON
)