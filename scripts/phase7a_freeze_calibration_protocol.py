import hashlib
import json
from pathlib import Path

import pandas as pd


# =========================================================
# Config
# =========================================================

SEED = 20260812

PRIVATE_MANIFEST = Path(
    "results/"
    "phase6l_materialized_private_manifest.csv"
)

QUERY_GT = Path(
    "results/"
    "phase6k_query_ground_truth.csv"
)

SPLIT_CSV = Path(
    "results/"
    "phase6c_project_split.csv"
)


OUTPUT_COMPONENT_CSV = Path(
    "results/"
    "phase7a_calibration_component_ground_truth.csv"
)

OUTPUT_QUERY_CSV = Path(
    "results/"
    "phase7a_calibration_query_protocol.csv"
)

OUTPUT_GALLERY_CSV = Path(
    "results/"
    "phase7a_calibration_gallery_protocol.csv"
)

OUTPUT_SUMMARY_JSON = Path(
    "results/"
    "phase7a_calibration_protocol_summary.json"
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


def stable_digest(text):

    return hashlib.sha256(
        (
            str(SEED)
            + "|"
            + text
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def choose_hidden_parent(
    query_id,
    parents,
):

    if not parents:

        raise RuntimeError(
            f"{query_id}: no parents"
        )

    ordered = sorted(
        parents,
        key=lambda parent: (
            stable_digest(
                f"{query_id}|"
                f"pseudo-unknown|"
                f"{parent}"
            ),
            parent,
        ),
    )

    return ordered[0]


# =========================================================
# Load
# =========================================================

for path in [
    PRIVATE_MANIFEST,
    QUERY_GT,
    SPLIT_CSV,
]:

    if not path.exists():

        raise FileNotFoundError(
            f"Missing: {path}"
        )


manifest = pd.read_csv(
    PRIVATE_MANIFEST
)

query_gt = pd.read_csv(
    QUERY_GT
)

splits = pd.read_csv(
    SPLIT_CSV
)


manifest[
    "source_fresh_id"
] = manifest[
    "source_fresh_id"
].astype(str)


splits[
    "fresh_id"
] = splits[
    "fresh_id"
].astype(str)


print(
    "======================================"
)

print(
    "Phase 7A - Calibration Protocol Freeze"
)

print(
    "======================================"
)


# =========================================================
# Calibration only
# =========================================================

cal_components = manifest[
    manifest[
        "stage"
    ]
    == "CALIBRATION"
].copy()


cal_queries = query_gt[
    query_gt[
        "stage"
    ]
    == "CALIBRATION"
].copy()


if (
    cal_queries[
        "query_id"
    ].nunique()
    != 180
):

    raise RuntimeError(
        "Expected 180 calibration queries"
    )


if len(
    cal_components
) != (
    180 * 7
):

    raise RuntimeError(
        "Expected 1260 calibration components"
    )


# =========================================================
# Frozen calibration-known gallery
# =========================================================

calibration_known_projects = sorted(
    splits[
        splits[
            "frozen_split"
        ]
        == "CALIBRATION_KNOWN"
    ][
        "fresh_id"
    ].astype(str)
    .unique()
)


calibration_background_projects = sorted(
    splits[
        splits[
            "frozen_split"
        ]
        == "CALIBRATION_BACKGROUND"
    ][
        "fresh_id"
    ].astype(str)
    .unique()
)


if len(
    calibration_known_projects
) != 25:

    raise RuntimeError(
        "Expected 25 CALIBRATION_KNOWN projects"
    )


if len(
    calibration_background_projects
) != 15:

    raise RuntimeError(
        "Expected 15 CALIBRATION_BACKGROUND projects"
    )


base_gallery = (
    calibration_known_projects
    +
    calibration_background_projects
)


# =========================================================
# Pseudo-UNKNOWN protocol
#
# One true known parent is hidden for every calibration
# query.
#
# This is used ONLY for open-set calibration.
#
# Original known-only calibration GT remains separately
# available for known-parent/K calibration.
# =========================================================

query_protocol_rows = []

component_protocol_rows = []

gallery_protocol_rows = []


hidden_parent_usage = {
    project:
        0
    for project
    in calibration_known_projects
}


for row in cal_queries.itertuples(
    index=False
):

    query_id = clean_text(
        row.query_id
    )


    query_components = cal_components[
        cal_components[
            "query_id"
        ].astype(str)
        == query_id
    ].copy()


    true_parents = sorted(
        query_components[
            "source_fresh_id"
        ].astype(str)
        .unique()
    )


    k_true = int(
        row.k_true
    )


    if len(
        true_parents
    ) != k_true:

        raise RuntimeError(
            f"{query_id}: parent count mismatch"
        )


    hidden_parent = (
        choose_hidden_parent(
            query_id,
            true_parents,
        )
    )


    hidden_parent_usage[
        hidden_parent
    ] += 1


    visible_true_parents = sorted(
        parent
        for parent
        in true_parents
        if parent
        != hidden_parent
    )


    pseudo_unknown_component_count = int(
        (
            query_components[
                "source_fresh_id"
            ].astype(str)
            == hidden_parent
        ).sum()
    )


    visible_known_component_count = int(
        len(
            query_components
        )
        -
        pseudo_unknown_component_count
    )


    query_protocol_rows.append({
        "query_id":
            query_id,

        "original_k_true":
            k_true,

        "hidden_parent":
            hidden_parent,

        "visible_true_parent_count":
            int(
                len(
                    visible_true_parents
                )
            ),

        "pseudo_unknown_parent_count":
            1,

        "visible_true_parents":
            json.dumps(
                visible_true_parents
            ),

        "pseudo_unknown_component_count":
            pseudo_unknown_component_count,

        "visible_known_component_count":
            visible_known_component_count,
    })


    # -----------------------------------------------------
    # Component-level pseudo-UNKNOWN labels
    # -----------------------------------------------------

    for component in (
        query_components.itertuples(
            index=False
        )
    ):

        source_parent = clean_text(
            component.source_fresh_id
        )


        pseudo_label = (
            "UNKNOWN"
            if source_parent
            == hidden_parent
            else source_parent
        )


        component_protocol_rows.append({
            "query_id":
                query_id,

            "node_id":
                clean_text(
                    component.node_id
                ),

            "modality":
                clean_text(
                    component.modality
                ),

            "original_source_parent":
                source_parent,

            "pseudo_ground_truth_label":
                pseudo_label,

            "is_pseudo_unknown":
                bool(
                    source_parent
                    == hidden_parent
                ),
        })


    # -----------------------------------------------------
    # Query-specific calibration gallery
    #
    # Hide exactly one parent.
    #
    # No TEST/UNKNOWN project can enter.
    # -----------------------------------------------------

    for project in (
        base_gallery
    ):

        included = (
            project
            != hidden_parent
        )


        role = (
            "KNOWN"
            if project
            in calibration_known_projects
            else
            "BACKGROUND"
        )


        gallery_protocol_rows.append({
            "query_id":
                query_id,

            "fresh_id":
                project,

            "gallery_role":
                role,

            "included":
                bool(
                    included
                ),

            "hidden_as_pseudo_unknown":
                bool(
                    project
                    == hidden_parent
                ),
        })


# =========================================================
# DataFrames
# =========================================================

query_protocol = pd.DataFrame(
    query_protocol_rows
)

component_protocol = pd.DataFrame(
    component_protocol_rows
)

gallery_protocol = pd.DataFrame(
    gallery_protocol_rows
)


# =========================================================
# Safety checks
# =========================================================

if len(
    query_protocol
) != 180:

    raise RuntimeError(
        "Wrong protocol query count"
    )


if len(
    component_protocol
) != (
    180 * 7
):

    raise RuntimeError(
        "Wrong protocol component count"
    )


if not (
    query_protocol[
        "pseudo_unknown_parent_count"
    ]
    == 1
).all():

    raise RuntimeError(
        "Every calibration query must hide "
        "exactly one parent"
    )


# Every query gallery:
#
# 25 calibration known
# + 15 calibration background
# - 1 hidden known
# = 39 visible projects.
visible_gallery_counts = (
    gallery_protocol[
        gallery_protocol[
            "included"
        ]
    ]
    .groupby(
        "query_id"
    )
    .size()
)


if not (
    visible_gallery_counts
    == 39
).all():

    raise RuntimeError(
        "Every pseudo-UNKNOWN calibration gallery "
        "must contain exactly 39 visible projects"
    )


# =========================================================
# Verify no forbidden split enters calibration gallery
# =========================================================

allowed_projects = set(
    calibration_known_projects
    +
    calibration_background_projects
)


gallery_projects_seen = set(
    gallery_protocol[
        "fresh_id"
    ].astype(str)
)


if not (
    gallery_projects_seen
    <= allowed_projects
):

    raise RuntimeError(
        "Forbidden project entered "
        "calibration gallery"
    )


# =========================================================
# Save
# =========================================================

component_protocol.to_csv(
    OUTPUT_COMPONENT_CSV,
    index=False,
    encoding="utf-8-sig",
)

query_protocol.to_csv(
    OUTPUT_QUERY_CSV,
    index=False,
    encoding="utf-8-sig",
)

gallery_protocol.to_csv(
    OUTPUT_GALLERY_CSV,
    index=False,
    encoding="utf-8-sig",
)


# =========================================================
# Summary
# =========================================================

usage_values = list(
    hidden_parent_usage.values()
)


parents_used_as_hidden = sum(
    1
    for value
    in usage_values
    if value > 0
)


summary = {
    "open_set_calibration_protocol_frozen":
        True,

    "performance_evaluated":
        False,

    "test_data_used":
        False,

    "unknown_heldout_used":
        False,

    "calibration_queries":
        int(
            len(
                query_protocol
            )
        ),

    "calibration_components":
        int(
            len(
                component_protocol
            )
        ),

    "base_calibration_known_projects":
        int(
            len(
                calibration_known_projects
            )
        ),

    "base_calibration_background_projects":
        int(
            len(
                calibration_background_projects
            )
        ),

    "visible_gallery_projects_per_pseudo_unknown_query":
        39,

    "hidden_parent_per_query":
        1,

    "parents_ever_used_as_pseudo_unknown":
        int(
            parents_used_as_hidden
        ),

    "minimum_hidden_uses_per_parent":
        int(
            min(
                usage_values
            )
        ),

    "maximum_hidden_uses_per_parent":
        int(
            max(
                usage_values
            )
        ),

    "pseudo_unknown_component_total":
        int(
            component_protocol[
                "is_pseudo_unknown"
            ].sum()
        ),

    "known_component_total":
        int(
            (
                ~component_protocol[
                    "is_pseudo_unknown"
                ]
            ).sum()
        ),

    "protocol_description":
        (
            "For each of the 180 calibration queries, "
            "one true CALIBRATION_KNOWN parent is "
            "deterministically removed from the "
            "40-project calibration gallery. Components "
            "from that hidden parent are relabeled "
            "UNKNOWN only for threshold calibration. "
            "TEST_KNOWN and UNKNOWN_HELDOUT are never "
            "used."
        ),

    "goals_met":
        bool(
            len(
                query_protocol
            )
            == 180

            and

            len(
                component_protocol
            )
            == 1260

            and

            parents_used_as_hidden
            >= 15

            and

            (
                gallery_projects_seen
                <= allowed_projects
            )
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
    "PHASE 7A RESULT"
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
    "Component GT:",
    OUTPUT_COMPONENT_CSV
)

print(
    "Query protocol:",
    OUTPUT_QUERY_CSV
)

print(
    "Gallery protocol:",
    OUTPUT_GALLERY_CSV
)

print(
    "Summary:",
    OUTPUT_SUMMARY_JSON
)