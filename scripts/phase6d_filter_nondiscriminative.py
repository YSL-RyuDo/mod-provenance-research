import json
import re
import zipfile
from collections import Counter
from pathlib import Path

import pandas as pd


# =========================================================
# Config
# =========================================================

CURRENT_COMPONENT_CSV = Path(
    "data/fresh_registry/"
    "fresh_current_component_registry.csv"
)

HISTORICAL_COMPONENT_CSV = Path(
    "data/fresh_registry/"
    "fresh_historical_component_registry.csv"
)

CURRENT_PACKAGE_CSV = Path(
    "data/fresh_registry/"
    "fresh_current_package_registry.csv"
)

HISTORICAL_PACKAGE_CSV = Path(
    "data/fresh_registry/"
    "fresh_historical_package_registry.csv"
)

SPLIT_CSV = Path(
    "results/phase6c_project_split.csv"
)


OUTPUT_CURRENT_CSV = Path(
    "data/fresh_registry/"
    "fresh_current_component_registry_filtered.csv"
)

OUTPUT_HISTORICAL_CSV = Path(
    "data/fresh_registry/"
    "fresh_historical_component_registry_filtered.csv"
)

REMOVED_CSV = Path(
    "results/"
    "phase6d_removed_nondiscriminative.csv"
)

DUPLICATE_CSV = Path(
    "results/"
    "phase6d_current_cross_project_duplicates_filtered.csv"
)

SUMMARY_JSON = Path(
    "results/"
    "phase6d_filter_summary.json"
)

FAILURE_JSON = Path(
    "results/"
    "phase6d_failures.json"
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


def nondiscriminative_reason(
    raw_bytes
):

    # -----------------------------------------------------
    # Zero-byte file
    # -----------------------------------------------------

    if len(raw_bytes) == 0:

        return "EMPTY_BYTES"


    # -----------------------------------------------------
    # Decode textual structured payload
    # -----------------------------------------------------

    try:

        text = raw_bytes.decode(
            "utf-8-sig"
        )

    except UnicodeDecodeError:

        # A structured-looking extension containing
        # non-UTF8 data is NOT automatically removed.
        return None


    stripped = text.strip()


    # -----------------------------------------------------
    # Whitespace-only file
    # -----------------------------------------------------

    if not stripped:

        return "WHITESPACE_ONLY"


    # -----------------------------------------------------
    # Empty JSON container
    #
    # Only whitespace is removed here.
    #
    # Examples:
    #
    # {}
    # { }
    # {
    # }
    #
    # []
    # [ ]
    #
    # are equivalent.
    # -----------------------------------------------------

    compact = re.sub(
        r"\s+",
        "",
        stripped,
    )


    if compact == "{}":

        return "EMPTY_JSON_OBJECT"


    if compact == "[]":

        return "EMPTY_JSON_ARRAY"


    return None


# =========================================================
# Load input
# =========================================================

required_files = [
    CURRENT_COMPONENT_CSV,
    HISTORICAL_COMPONENT_CSV,
    CURRENT_PACKAGE_CSV,
    HISTORICAL_PACKAGE_CSV,
    SPLIT_CSV,
]


for path in required_files:

    if not path.exists():

        raise FileNotFoundError(
            f"Missing: {path}"
        )


current_components = pd.read_csv(
    CURRENT_COMPONENT_CSV
)

historical_components = pd.read_csv(
    HISTORICAL_COMPONENT_CSV
)

current_packages = pd.read_csv(
    CURRENT_PACKAGE_CSV
)

historical_packages = pd.read_csv(
    HISTORICAL_PACKAGE_CSV
)

splits = pd.read_csv(
    SPLIT_CSV
)


print(
    "======================================"
)

print(
    "Phase 6D - Non-discriminative Filter"
)

print(
    "======================================"
)

print(
    "Current components:",
    len(current_components)
)

print(
    "Historical components:",
    len(historical_components)
)


# =========================================================
# Validate required columns
# =========================================================

component_required = {
    "fresh_id",
    "project_id",
    "release_kind",
    "version_id",
    "jar_filename",
    "relative_path",
    "modality",
    "component_sha256",
}


for name, df in [
    (
        "current_components",
        current_components,
    ),
    (
        "historical_components",
        historical_components,
    ),
]:

    missing = (
        component_required
        - set(df.columns)
    )

    if missing:

        raise RuntimeError(
            f"{name} missing columns: "
            f"{sorted(missing)}"
        )


package_required = {
    "fresh_id",
    "version_id",
    "local_path",
}


for name, df in [
    (
        "current_packages",
        current_packages,
    ),
    (
        "historical_packages",
        historical_packages,
    ),
]:

    missing = (
        package_required
        - set(df.columns)
    )

    if missing:

        raise RuntimeError(
            f"{name} missing columns: "
            f"{sorted(missing)}"
        )


# =========================================================
# Package path maps
# =========================================================

def make_package_map(
    packages
):

    result = {}


    for _, row in (
        packages.iterrows()
    ):

        key = (
            clean_text(
                row["fresh_id"]
            ),
            clean_text(
                row["version_id"]
            ),
        )

        path = Path(
            clean_text(
                row["local_path"]
            )
        )


        if key in result:

            if result[key] != path:

                raise RuntimeError(
                    "Conflicting package path: "
                    f"{key}"
                )


        result[key] = path


    return result


current_package_map = (
    make_package_map(
        current_packages
    )
)

historical_package_map = (
    make_package_map(
        historical_packages
    )
)


# =========================================================
# Filter registry
# =========================================================

failures = []

removed_rows = []


def filter_registry(
    components,
    package_map,
    release_label,
):

    keep_indices = []


    groups = components.groupby(
        [
            "fresh_id",
            "version_id",
        ],
        sort=False,
    )


    total_groups = (
        groups.ngroups
    )


    for group_number, (
        key,
        group
    ) in enumerate(
        groups,
        start=1,
    ):

        fresh_id = clean_text(
            key[0]
        )

        version_id = clean_text(
            key[1]
        )

        map_key = (
            fresh_id,
            version_id,
        )


        print(
            f"[{release_label} "
            f"{group_number}/"
            f"{total_groups}] "
            f"{fresh_id} "
            f"{version_id}"
        )


        if map_key not in package_map:

            failures.append({
                "release":
                    release_label,

                "fresh_id":
                    fresh_id,

                "version_id":
                    version_id,

                "reason":
                    "PACKAGE_PATH_NOT_FOUND",
            })

            continue


        jar_path = (
            package_map[
                map_key
            ]
        )


        if not jar_path.exists():

            failures.append({
                "release":
                    release_label,

                "fresh_id":
                    fresh_id,

                "version_id":
                    version_id,

                "reason":
                    "JAR_NOT_FOUND",

                "path":
                    str(
                        jar_path
                    ),
            })

            continue


        try:

            with zipfile.ZipFile(
                jar_path,
                "r",
            ) as jar:

                zip_names = set(
                    jar.namelist()
                )


                for row_index, row in (
                    group.iterrows()
                ):

                    modality = (
                        clean_text(
                            row[
                                "modality"
                            ]
                        )
                    )


                    # -------------------------------------
                    # Only STRUCTURED can be filtered.
                    # Code and images are always kept.
                    # -------------------------------------

                    if (
                        modality
                        != "STRUCTURED"
                    ):

                        keep_indices.append(
                            row_index
                        )

                        continue


                    relative_path = (
                        clean_text(
                            row[
                                "relative_path"
                            ]
                        )
                        .replace(
                            "\\",
                            "/"
                        )
                    )


                    if (
                        relative_path
                        not in zip_names
                    ):

                        failures.append({
                            "release":
                                release_label,

                            "fresh_id":
                                fresh_id,

                            "version_id":
                                version_id,

                            "relative_path":
                                relative_path,

                            "reason":
                                "ZIP_ENTRY_NOT_FOUND",
                        })

                        continue


                    try:

                        raw = jar.read(
                            relative_path
                        )

                    except Exception as exc:

                        failures.append({
                            "release":
                                release_label,

                            "fresh_id":
                                fresh_id,

                            "version_id":
                                version_id,

                            "relative_path":
                                relative_path,

                            "reason":
                                "ZIP_READ_FAILED",

                            "detail":
                                repr(exc),
                        })

                        continue


                    reason = (
                        nondiscriminative_reason(
                            raw
                        )
                    )


                    if reason is None:

                        keep_indices.append(
                            row_index
                        )

                    else:

                        removed = (
                            row.to_dict()
                        )

                        removed[
                            "filter_reason"
                        ] = reason

                        removed[
                            "payload_bytes"
                        ] = len(raw)

                        removed_rows.append(
                            removed
                        )


        except Exception as exc:

            failures.append({
                "release":
                    release_label,

                "fresh_id":
                    fresh_id,

                "version_id":
                    version_id,

                "reason":
                    "JAR_OPEN_FAILED",

                "detail":
                    repr(exc),

                "path":
                    str(
                        jar_path
                    ),
            })


    filtered = (
        components
        .loc[
            keep_indices
        ]
        .copy()
    )


    filtered = (
        filtered.reset_index(
            drop=True
        )
    )


    return filtered


# =========================================================
# Current
# =========================================================

print()

print(
    "Filtering CURRENT..."
)

filtered_current = (
    filter_registry(
        current_components,
        current_package_map,
        "CURRENT",
    )
)


# =========================================================
# Historical
# =========================================================

print()

print(
    "Filtering HISTORICAL..."
)

filtered_historical = (
    filter_registry(
        historical_components,
        historical_package_map,
        "HISTORICAL",
    )
)


# =========================================================
# Safety validation
# =========================================================

removed_df = pd.DataFrame(
    removed_rows
)


if len(removed_df):

    removed_modalities = set(
        removed_df[
            "modality"
        ].astype(str)
    )


    if removed_modalities != {
        "STRUCTURED"
    }:

        raise RuntimeError(
            "Safety violation: "
            "non-structured component "
            "was removed."
        )


# =========================================================
# Save filtered registries
# =========================================================

OUTPUT_CURRENT_CSV.parent.mkdir(
    parents=True,
    exist_ok=True,
)


filtered_current.to_csv(
    OUTPUT_CURRENT_CSV,
    index=False,
    encoding="utf-8-sig",
)

filtered_historical.to_csv(
    OUTPUT_HISTORICAL_CSV,
    index=False,
    encoding="utf-8-sig",
)


if len(removed_df):

    removed_df.to_csv(
        REMOVED_CSV,
        index=False,
        encoding="utf-8-sig",
    )

else:

    pd.DataFrame(
        columns=[
            "fresh_id",
            "project_id",
            "release_kind",
            "version_id",
            "relative_path",
            "modality",
            "component_sha256",
            "filter_reason",
            "payload_bytes",
        ]
    ).to_csv(
        REMOVED_CSV,
        index=False,
        encoding="utf-8-sig",
    )


# =========================================================
# Cross-project exact duplicate audit AFTER filter
# =========================================================

duplicate_rows = []

duplicate_group_count = 0

duplicate_component_count = 0

duplicate_groups_by_modality = Counter()

duplicate_components_by_modality = Counter()


grouped = (
    filtered_current
    .groupby(
        [
            "modality",
            "component_sha256",
        ],
        sort=False,
    )
)


for (
    modality,
    digest
), group in grouped:

    projects = sorted(
        set(
            group[
                "fresh_id"
            ].astype(str)
        )
    )


    if len(projects) <= 1:

        continue


    duplicate_group_count += 1

    duplicate_component_count += (
        len(group)
    )


    duplicate_groups_by_modality[
        modality
    ] += 1

    duplicate_components_by_modality[
        modality
    ] += len(group)


    for _, row in (
        group.iterrows()
    ):

        duplicate_rows.append({
            "modality":
                modality,

            "component_sha256":
                digest,

            "project_count":
                len(projects),

            "projects":
                json.dumps(
                    projects
                ),

            "fresh_id":
                row[
                    "fresh_id"
                ],

            "role":
                row[
                    "role"
                ],

            "relative_path":
                row[
                    "relative_path"
                ],
        })


duplicate_columns = [
    "modality",
    "component_sha256",
    "project_count",
    "projects",
    "fresh_id",
    "role",
    "relative_path",
]


duplicate_df = pd.DataFrame(
    duplicate_rows,
    columns=duplicate_columns,
)


duplicate_df.to_csv(
    DUPLICATE_CSV,
    index=False,
    encoding="utf-8-sig",
)


# =========================================================
# Split statistics
# =========================================================

split_map = (
    splits[
        [
            "fresh_id",
            "frozen_split",
        ]
    ]
    .drop_duplicates(
        subset=[
            "fresh_id"
        ]
    )
)


current_with_split = (
    filtered_current.merge(
        split_map,
        on="fresh_id",
        how="left",
    )
)


removed_with_split = (
    removed_df.merge(
        split_map,
        on="fresh_id",
        how="left",
    )

    if len(removed_df)

    else pd.DataFrame()
)


split_stats = {}


for split_name, group in (
    current_with_split.groupby(
        "frozen_split"
    )
):

    split_stats[
        str(split_name)
    ] = {
        "components_after_filter":
            int(
                len(group)
            ),

        "code_binary":
            int(
                (
                    group[
                        "modality"
                    ]
                    == "CODE_BINARY"
                ).sum()
            ),

        "structured":
            int(
                (
                    group[
                        "modality"
                    ]
                    == "STRUCTURED"
                ).sum()
            ),

        "image":
            int(
                (
                    group[
                        "modality"
                    ]
                    == "IMAGE"
                ).sum()
            ),
    }


if len(
    removed_with_split
):

    removed_split_counts = (
        removed_with_split[
            "frozen_split"
        ]
        .value_counts()
        .to_dict()
    )

else:

    removed_split_counts = {}


# =========================================================
# Filter reason statistics
# =========================================================

reason_counts = {}

current_reason_counts = {}

historical_reason_counts = {}


if len(removed_df):

    reason_counts = {
        str(k):
            int(v)

        for k, v in (
            removed_df[
                "filter_reason"
            ]
            .value_counts()
            .to_dict()
            .items()
        )
    }


    current_removed = (
        removed_df[
            removed_df[
                "release_kind"
            ]
            == "CURRENT"
        ]
    )


    historical_removed = (
        removed_df[
            removed_df[
                "release_kind"
            ]
            == "HISTORICAL"
        ]
    )


    current_reason_counts = {
        str(k):
            int(v)

        for k, v in (
            current_removed[
                "filter_reason"
            ]
            .value_counts()
            .to_dict()
            .items()
        )
    }


    historical_reason_counts = {
        str(k):
            int(v)

        for k, v in (
            historical_removed[
                "filter_reason"
            ]
            .value_counts()
            .to_dict()
            .items()
        )
    }


# =========================================================
# Summary
# =========================================================

current_removed_count = (
    len(current_components)
    - len(filtered_current)
)

historical_removed_count = (
    len(historical_components)
    - len(filtered_historical)
)


duplicate_rate_after = (
    duplicate_component_count
    / len(filtered_current)

    if len(filtered_current)

    else 0.0
)


summary = {
    "filter_definition_frozen":
        True,

    "filter_rules": [
        "EMPTY_BYTES",
        "WHITESPACE_ONLY",
        "EMPTY_JSON_OBJECT",
        "EMPTY_JSON_ARRAY",
    ],

    "filter_scope":
        "STRUCTURED_ONLY",

    "current_before":
        int(
            len(current_components)
        ),

    "current_after":
        int(
            len(filtered_current)
        ),

    "current_removed":
        int(
            current_removed_count
        ),

    "current_removed_rate":
        float(
            current_removed_count
            / len(current_components)
        )
        if len(current_components)
        else 0.0,

    "historical_before":
        int(
            len(historical_components)
        ),

    "historical_after":
        int(
            len(filtered_historical)
        ),

    "historical_removed":
        int(
            historical_removed_count
        ),

    "historical_removed_rate":
        float(
            historical_removed_count
            / len(historical_components)
        )
        if len(historical_components)
        else 0.0,

    "removed_reason_counts":
        reason_counts,

    "current_removed_reason_counts":
        current_reason_counts,

    "historical_removed_reason_counts":
        historical_reason_counts,

    "current_cross_project_duplicate_groups_after_filter":
        int(
            duplicate_group_count
        ),

    "current_cross_project_duplicate_components_after_filter":
        int(
            duplicate_component_count
        ),

    "current_cross_project_duplicate_rate_after_filter":
        float(
            duplicate_rate_after
        ),

    "duplicate_groups_by_modality_after_filter":
        {
            str(k):
                int(v)

            for k, v in (
                duplicate_groups_by_modality
                .items()
            )
        },

    "duplicate_components_by_modality_after_filter":
        {
            str(k):
                int(v)

            for k, v in (
                duplicate_components_by_modality
                .items()
            )
        },

    "current_split_stats_after_filter":
        split_stats,

    "current_removed_by_split":
        {
            str(k):
                int(v)

            for k, v in (
                removed_split_counts
                .items()
            )
        },

    "failures":
        int(
            len(failures)
        ),

    "goals_met":
        bool(
            len(failures) == 0

            and
            len(filtered_current)
            + current_removed_count
            == len(current_components)

            and
            len(filtered_historical)
            + historical_removed_count
            == len(historical_components)
        ),
}


# =========================================================
# Save failures / summary
# =========================================================

FAILURE_JSON.write_text(
    json.dumps(
        failures,
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)


SUMMARY_JSON.write_text(
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
    "PHASE 6D RESULT"
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
    "Filtered current   :",
    OUTPUT_CURRENT_CSV
)

print(
    "Filtered historical:",
    OUTPUT_HISTORICAL_CSV
)

print(
    "Removed audit      :",
    REMOVED_CSV
)

print(
    "Duplicate audit    :",
    DUPLICATE_CSV
)

print(
    "Failures           :",
    FAILURE_JSON
)

print(
    "Summary            :",
    SUMMARY_JSON
)