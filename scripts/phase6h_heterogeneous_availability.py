import json
from pathlib import Path

import pandas as pd


# =========================================================
# Config
# =========================================================

FRAGMENT_CSV = Path(
    "results/"
    "phase6g_h5_fragment_catalog.csv"
)

HARD_CSV = Path(
    "results/"
    "phase6e_hard_candidate_catalog.csv"
)

HISTORICAL_CSV = Path(
    "data/fresh_registry/"
    "fresh_historical_component_registry_filtered.csv"
)

CURRENT_CSV = Path(
    "data/fresh_registry/"
    "fresh_current_component_registry_filtered.csv"
)


OUTPUT_CSV = Path(
    "results/"
    "phase6h_heterogeneous_availability.csv"
)

OUTPUT_SUMMARY_JSON = Path(
    "results/"
    "phase6h_heterogeneous_availability_summary.json"
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


# =========================================================
# Load
# =========================================================

for path in [
    FRAGMENT_CSV,
    HARD_CSV,
    HISTORICAL_CSV,
    CURRENT_CSV,
]:

    if not path.exists():

        raise FileNotFoundError(
            f"Missing: {path}"
        )


fragments = pd.read_csv(
    FRAGMENT_CSV
)

hard = pd.read_csv(
    HARD_CSV
)

historical = pd.read_csv(
    HISTORICAL_CSV
)

current = pd.read_csv(
    CURRENT_CSV
)


for df in [
    fragments,
    hard,
    historical,
    current,
]:

    df["fresh_id"] = (
        df["fresh_id"]
        .astype(str)
    )


for df in [
    fragments,
    hard,
    historical,
]:

    df["version_id"] = (
        df["version_id"]
        .astype(str)
    )


print(
    "======================================"
)

print(
    "Phase 6H - Heterogeneous Availability"
)

print(
    "======================================"
)


# =========================================================
# One row per generated fragment
# =========================================================

fragment_meta = (
    fragments[
        [
            "fragment_id",
            "fresh_id",
            "frozen_split",
            "version_id",
            "version_number",
            "variant_index",
        ]
    ]
    .drop_duplicates(
        subset=[
            "fragment_id"
        ]
    )
    .copy()
)


print(
    "Generated fragments:",
    len(fragment_meta)
)


# =========================================================
# Historical HARD structured index
# =========================================================

hard_structured = hard[
    hard["modality"]
    == "STRUCTURED"
].copy()


hard_structured_counts = (
    hard_structured
    .groupby(
        [
            "fresh_id",
            "version_id",
        ]
    )
    .size()
    .to_dict()
)


# =========================================================
# Historical IMAGE index
# =========================================================

historical_images = historical[
    historical["modality"]
    == "IMAGE"
].copy()


image_counts = (
    historical_images
    .groupby(
        [
            "fresh_id",
            "version_id",
        ]
    )
    .size()
    .to_dict()
)


# =========================================================
# Own-current exact image hashes
#
# UNKNOWN current images are used ONLY for availability /
# drift characterization.
#
# They remain excluded from the TEST gallery.
# =========================================================

current_images = current[
    current["modality"]
    == "IMAGE"
].copy()


current_image_hashes = {}


for fresh_id, group in (
    current_images.groupby(
        "fresh_id"
    )
):

    current_image_hashes[
        str(fresh_id)
    ] = set(
        group[
            "component_sha256"
        ]
        .astype(str)
    )


# =========================================================
# Historical exact-surviving image counts
# =========================================================

surviving_image_counts = {}


for (
    fresh_id,
    version_id
), group in (
    historical_images.groupby(
        [
            "fresh_id",
            "version_id",
        ]
    )
):

    fresh_id = str(
        fresh_id
    )

    version_id = str(
        version_id
    )


    own_current_hashes = (
        current_image_hashes.get(
            fresh_id,
            set(),
        )
    )


    count = 0


    for digest in (
        group[
            "component_sha256"
        ].astype(str)
    ):

        if digest in own_current_hashes:

            count += 1


    surviving_image_counts[
        (
            fresh_id,
            version_id,
        )
    ] = count


# =========================================================
# Fragment-level audit
# =========================================================

rows = []


for index, row in enumerate(
    fragment_meta.itertuples(
        index=False
    ),
    start=1,
):

    fresh_id = clean_text(
        row.fresh_id
    )

    version_id = clean_text(
        row.version_id
    )


    key = (
        fresh_id,
        version_id,
    )


    structured_hard = int(
        hard_structured_counts.get(
            key,
            0,
        )
    )


    images = int(
        image_counts.get(
            key,
            0,
        )
    )


    surviving_images = int(
        surviving_image_counts.get(
            key,
            0,
        )
    )


    rows.append({
        "fragment_id":
            clean_text(
                row.fragment_id
            ),

        "fresh_id":
            fresh_id,

        "frozen_split":
            clean_text(
                row.frozen_split
            ),

        "version_id":
            version_id,

        "version_number":
            clean_text(
                row.version_number
            ),

        "variant_index":
            int(
                row.variant_index
            ),

        "hard_structured_components":
            structured_hard,

        "historical_image_components":
            images,

        "own_current_exact_surviving_images":
            surviving_images,

        "has_structured_hard_1":
            bool(
                structured_hard >= 1
            ),

        "has_structured_hard_2":
            bool(
                structured_hard >= 2
            ),

        "has_image_1":
            bool(
                images >= 1
            ),

        "has_exact_surviving_image_1":
            bool(
                surviving_images >= 1
            ),

        "eligible_code_structured":
            bool(
                structured_hard >= 1
            ),

        "eligible_full_heterogeneous":
            bool(
                structured_hard >= 1
                and
                surviving_images >= 1
            ),
    })


audit = pd.DataFrame(
    rows
)


audit.to_csv(
    OUTPUT_CSV,
    index=False,
    encoding="utf-8-sig",
)


# =========================================================
# Summary
# =========================================================

def summarize(
    group
):

    full_eligible = group[
        group[
            "eligible_full_heterogeneous"
        ]
    ]


    code_structured = group[
        group[
            "eligible_code_structured"
        ]
    ]


    return {
        "fragments":
            int(
                len(group)
            ),

        "projects":
            int(
                group[
                    "fresh_id"
                ].nunique()
            ),

        "fragments_with_structured_hard_1":
            int(
                group[
                    "has_structured_hard_1"
                ].sum()
            ),

        "fragments_with_structured_hard_2":
            int(
                group[
                    "has_structured_hard_2"
                ].sum()
            ),

        "fragments_with_image":
            int(
                group[
                    "has_image_1"
                ].sum()
            ),

        "fragments_with_exact_surviving_image":
            int(
                group[
                    "has_exact_surviving_image_1"
                ].sum()
            ),

        "code_structured_eligible_fragments":
            int(
                len(
                    code_structured
                )
            ),

        "code_structured_eligible_projects":
            int(
                code_structured[
                    "fresh_id"
                ].nunique()
            ),

        "full_heterogeneous_eligible_fragments":
            int(
                len(
                    full_eligible
                )
            ),

        "full_heterogeneous_eligible_projects":
            int(
                full_eligible[
                    "fresh_id"
                ].nunique()
            ),

        "structured_hard_median":
            float(
                group[
                    "hard_structured_components"
                ].median()
            )
            if len(group)
            else 0.0,

        "image_median":
            float(
                group[
                    "historical_image_components"
                ].median()
            )
            if len(group)
            else 0.0,

        "surviving_image_median":
            float(
                group[
                    "own_current_exact_surviving_images"
                ].median()
            )
            if len(group)
            else 0.0,
    }


by_split = {}


for split_name, group in (
    audit.groupby(
        "frozen_split"
    )
):

    by_split[
        str(split_name)
    ] = summarize(
        group
    )


# =========================================================
# Project coverage
# =========================================================

project_coverage = {}


for split_name, group in (
    audit.groupby(
        "frozen_split"
    )
):

    all_projects = set(
        group[
            "fresh_id"
        ].astype(str)
    )


    cs_projects = set(
        group[
            group[
                "eligible_code_structured"
            ]
        ][
            "fresh_id"
        ].astype(str)
    )


    full_projects = set(
        group[
            group[
                "eligible_full_heterogeneous"
            ]
        ][
            "fresh_id"
        ].astype(str)
    )


    project_coverage[
        str(split_name)
    ] = {
        "h5_code_projects":
            int(
                len(
                    all_projects
                )
            ),

        "code_structured_projects":
            int(
                len(
                    cs_projects
                )
            ),

        "full_heterogeneous_projects":
            int(
                len(
                    full_projects
                )
            ),

        "missing_code_structured_projects":
            sorted(
                all_projects
                -
                cs_projects
            ),

        "missing_full_heterogeneous_projects":
            sorted(
                all_projects
                -
                full_projects
            ),
    }


# =========================================================
# Goals
# =========================================================

def get_full_project_count(
    split_name
):

    return int(
        project_coverage
        .get(
            split_name,
            {},
        )
        .get(
            "full_heterogeneous_projects",
            0,
        )
    )


calibration_full = (
    get_full_project_count(
        "CALIBRATION_KNOWN"
    )
)

test_full = (
    get_full_project_count(
        "TEST_KNOWN"
    )
)

unknown_full = (
    get_full_project_count(
        "UNKNOWN_HELDOUT"
    )
)


summary = {
    "heterogeneous_availability_audit":
        True,

    "performance_evaluated":
        False,

    "thresholds_tuned":
        False,

    "code_requirement":
        (
            "existing Phase 6G H5 connected "
            "CODE_BINARY fragment"
        ),

    "structured_requirement":
        (
            "at least one HARD_MASKED STRUCTURED "
            "component from the same historical release"
        ),

    "image_requirement":
        (
            "at least one historical IMAGE component "
            "whose exact content also survives in its "
            "own current release; the image may later "
            "be automatically transformed before "
            "query construction"
        ),

    "generated_code_fragments_audited":
        int(
            len(
                audit
            )
        ),

    "by_split":
        by_split,

    "project_coverage":
        project_coverage,

    "minimum_full_heterogeneous_parent_goal":
        15,

    "goals_met":
        bool(
            calibration_full >= 15
            and
            test_full >= 15
            and
            unknown_full >= 15
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
    "PHASE 6H RESULT"
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
    "Audit  :",
    OUTPUT_CSV
)

print(
    "Summary:",
    OUTPUT_SUMMARY_JSON
)