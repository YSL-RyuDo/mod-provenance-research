import json
from pathlib import Path

import pandas as pd


# =========================================================
# Config
# =========================================================

INPUT_CSV = Path(
    "results/"
    "phase6h_heterogeneous_availability.csv"
)

OUTPUT_CSV = Path(
    "results/"
    "phase6j_modality_composition_audit.csv"
)

OUTPUT_JSON = Path(
    "results/"
    "phase6j_modality_composition_summary.json"
)


MIN_PARENT_PROJECTS = 15


# =========================================================
# Candidate fixed query compositions
#
# Every final query will have exactly 8 evaluated
# components regardless of K.
#
# This prevents query size and modality counts from
# trivially revealing K.
# =========================================================

TEMPLATES = {
    "A_5C_2S_1I": {
        "code": 5,
        "structured": 2,
        "image": 1,
    },

    "B_5C_1S_2I": {
        "code": 5,
        "structured": 1,
        "image": 2,
    },

    "C_4C_2S_2I": {
        "code": 4,
        "structured": 2,
        "image": 2,
    },
}


# Methodological preference:
#
# A first:
#   preserves all five H5 code targets while still
#   evaluating STRUCTURED and IMAGE evidence.
#
# B second:
#   preserves H5 but requires more image availability.
#
# C third:
#   more modality-balanced but uses only four code targets.
#
TEMPLATE_PRIORITY = [
    "A_5C_2S_1I",
    "B_5C_1S_2I",
    "C_4C_2S_2I",
]


EXPECTED_SPLITS = [
    "CALIBRATION_KNOWN",
    "TEST_KNOWN",
    "UNKNOWN_HELDOUT",
]


# =========================================================
# Helpers
# =========================================================

def as_bool(value):

    if isinstance(value, bool):
        return value

    return (
        str(value)
        .strip()
        .lower()
        in {
            "1",
            "true",
            "yes",
            "y",
        }
    )


# =========================================================
# Load
# =========================================================

if not INPUT_CSV.exists():

    raise FileNotFoundError(
        INPUT_CSV
    )


df = pd.read_csv(
    INPUT_CSV
)


required_columns = {
    "fragment_id",
    "fresh_id",
    "frozen_split",
    "version_id",
    "hard_structured_components",
    "own_current_exact_surviving_images",
    "eligible_full_heterogeneous",
}


missing = (
    required_columns
    - set(df.columns)
)


if missing:

    raise RuntimeError(
        "Missing columns: "
        + str(
            sorted(
                missing
            )
        )
    )


df[
    "fresh_id"
] = df[
    "fresh_id"
].astype(str)


df[
    "version_id"
] = df[
    "version_id"
].astype(str)


df[
    "eligible_full_heterogeneous_bool"
] = df[
    "eligible_full_heterogeneous"
].map(
    as_bool
)


# =========================================================
# Full heterogeneous fragment pool
# =========================================================

full = df[
    df[
        "eligible_full_heterogeneous_bool"
    ]
].copy()


full[
    "hard_structured_components"
] = (
    full[
        "hard_structured_components"
    ]
    .fillna(0)
    .astype(int)
)


full[
    "own_current_exact_surviving_images"
] = (
    full[
        "own_current_exact_surviving_images"
    ]
    .fillna(0)
    .astype(int)
)


print(
    "======================================"
)

print(
    "Phase 6J - Modality Composition Audit"
)

print(
    "======================================"
)

print(
    "Input full heterogeneous fragments:",
    len(
        full
    )
)


# =========================================================
# Template support
#
# CODE availability is guaranteed by Phase 6G H5:
# every fragment has five HARD_MASKED CODE_BINARY targets.
# =========================================================

for template_name, spec in (
    TEMPLATES.items()
):

    structured_needed = int(
        spec[
            "structured"
        ]
    )

    image_needed = int(
        spec[
            "image"
        ]
    )


    full[
        f"supports_{template_name}"
    ] = (
        (
            full[
                "hard_structured_components"
            ]
            >= structured_needed
        )
        &
        (
            full[
                "own_current_exact_surviving_images"
            ]
            >= image_needed
        )
    )


# =========================================================
# Detailed output
# =========================================================

output_columns = [
    "fragment_id",
    "fresh_id",
    "frozen_split",
    "version_id",
    "version_number",
    "variant_index",
    "hard_structured_components",
    "own_current_exact_surviving_images",
]


for template_name in TEMPLATES:

    output_columns.append(
        f"supports_{template_name}"
    )


available_columns = [
    column
    for column in output_columns
    if column in full.columns
]


full[
    available_columns
].to_csv(
    OUTPUT_CSV,
    index=False,
    encoding="utf-8-sig",
)


# =========================================================
# Summary per template / split
# =========================================================

template_summary = {}


for template_name, spec in (
    TEMPLATES.items()
):

    support_column = (
        f"supports_{template_name}"
    )


    split_results = {}

    all_splits_viable = True


    for split_name in (
        EXPECTED_SPLITS
    ):

        split_group = full[
            full[
                "frozen_split"
            ]
            == split_name
        ]


        eligible = split_group[
            split_group[
                support_column
            ]
        ]


        all_projects = set(
            split_group[
                "fresh_id"
            ].astype(str)
        )


        eligible_projects = set(
            eligible[
                "fresh_id"
            ].astype(str)
        )


        project_count = len(
            eligible_projects
        )


        split_viable = (
            project_count
            >= MIN_PARENT_PROJECTS
        )


        if not split_viable:

            all_splits_viable = False


        split_results[
            split_name
        ] = {
            "fragments":
                int(
                    len(
                        eligible
                    )
                ),

            "projects":
                int(
                    project_count
                ),

            "minimum_parent_goal_met":
                bool(
                    split_viable
                ),

            "missing_projects":
                sorted(
                    all_projects
                    -
                    eligible_projects
                ),
        }


    template_summary[
        template_name
    ] = {
        "composition": {
            "CODE_BINARY":
                int(
                    spec[
                        "code"
                    ]
                ),

            "STRUCTURED":
                int(
                    spec[
                        "structured"
                    ]
                ),

            "IMAGE":
                int(
                    spec[
                        "image"
                    ]
                ),

            "total":
                int(
                    spec[
                        "code"
                    ]
                    +
                    spec[
                        "structured"
                    ]
                    +
                    spec[
                        "image"
                    ]
                ),
        },

        "splits":
            split_results,

        "all_splits_minimum_15_met":
            bool(
                all_splits_viable
            ),
    }


# =========================================================
# Select fixed composition
#
# This is NOT selected using provenance performance.
#
# Selection criterion:
#
# 1. Must retain >= 15 parent projects in every split.
# 2. Use frozen methodological priority.
# =========================================================

viable_templates = [
    template_name

    for template_name
    in TEMPLATE_PRIORITY

    if template_summary[
        template_name
    ][
        "all_splits_minimum_15_met"
    ]
]


selected_template = (
    viable_templates[
        0
    ]

    if viable_templates

    else None
)


# =========================================================
# Leakage policy
# =========================================================

leakage_policy = {
    "fixed_evaluated_components_per_query":
        8,

    "query_size_varies_with_K":
        False,

    "modality_composition_varies_with_K":
        False,

    "K_exposed_to_method":
        False,

    "path_identity_exposed_to_method":
        False,

    "source_project_identity_exposed_to_method":
        False,
}


# =========================================================
# Final summary
# =========================================================

summary = {
    "modality_composition_audit":
        True,

    "performance_evaluated":
        False,

    "thresholds_tuned":
        False,

    "query_budget":
        8,

    "minimum_parent_project_goal":
        MIN_PARENT_PROJECTS,

    "candidate_templates":
        TEMPLATES,

    "template_priority":
        TEMPLATE_PRIORITY,

    "template_results":
        template_summary,

    "selected_template":
        selected_template,

    "selection_rule":
        (
            "first template in the frozen methodological "
            "priority order that retains at least 15 "
            "distinct parent projects in CALIBRATION_KNOWN, "
            "TEST_KNOWN, and UNKNOWN_HELDOUT; no provenance "
            "performance result is used"
        ),

    "leakage_policy":
        leakage_policy,

    "goals_met":
        bool(
            selected_template
            is not None
        ),
}


OUTPUT_JSON.write_text(
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
    "PHASE 6J RESULT"
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
    OUTPUT_JSON
)