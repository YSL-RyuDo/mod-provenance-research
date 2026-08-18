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
    "phase6i_query_capacity_audit.csv"
)

OUTPUT_JSON = Path(
    "results/"
    "phase6i_query_capacity_summary.json"
)


BUDGETS = [
    7,
    8,
    9,
    10,
    11,
    12,
]


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


df["fresh_id"] = (
    df["fresh_id"]
    .astype(str)
)


# =========================================================
# Boolean helper
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


df[
    "eligible_full_heterogeneous_bool"
] = df[
    "eligible_full_heterogeneous"
].map(
    as_bool
)


# =========================================================
# Only fully heterogeneous fragments
# =========================================================

full = df[
    df[
        "eligible_full_heterogeneous_bool"
    ]
].copy()


# =========================================================
# Capacity
#
# Five CODE targets already exist in Phase 6G.
#
# STRUCTURED:
#   HARD_MASKED only.
#
# IMAGE:
#   Historical image whose exact original survives in the
#   current release. The query version will later be
#   transformed, so exact SHA matching will not be usable.
# =========================================================

full[
    "code_capacity"
] = 5


full[
    "structured_capacity"
] = (
    full[
        "hard_structured_components"
    ]
    .fillna(0)
    .astype(int)
)


full[
    "image_capacity"
] = (
    full[
        "own_current_exact_surviving_images"
    ]
    .fillna(0)
    .astype(int)
)


full[
    "total_heterogeneous_capacity"
] = (
    full[
        "code_capacity"
    ]
    +
    full[
        "structured_capacity"
    ]
    +
    full[
        "image_capacity"
    ]
)


# =========================================================
# Budget flags
# =========================================================

for budget in BUDGETS:

    full[
        f"supports_budget_{budget}"
    ] = (
        full[
            "total_heterogeneous_capacity"
        ]
        >= budget
    )


# =========================================================
# Save detailed audit
# =========================================================

full.to_csv(
    OUTPUT_CSV,
    index=False,
    encoding="utf-8-sig",
)


# =========================================================
# Helpers
# =========================================================

def percentile_nearest_rank(
    values,
    percent,
):

    values = sorted(
        int(v)
        for v in values
    )


    if not values:

        return 0


    rank = int(
        (percent * len(values))
        + 0.999999999
    )


    rank = max(
        1,
        min(
            rank,
            len(values),
        ),
    )


    return int(
        values[
            rank - 1
        ]
    )


def summarize_split(
    group
):

    capacities = (
        group[
            "total_heterogeneous_capacity"
        ]
        .astype(int)
        .tolist()
    )


    result = {
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

        "min_capacity":
            int(
                min(capacities)
            )
            if capacities
            else 0,

        "median_capacity":
            float(
                group[
                    "total_heterogeneous_capacity"
                ].median()
            )
            if len(group)
            else 0.0,

        "p25_capacity":
            percentile_nearest_rank(
                capacities,
                0.25,
            ),

        "p75_capacity":
            percentile_nearest_rank(
                capacities,
                0.75,
            ),

        "max_capacity":
            int(
                max(capacities)
            )
            if capacities
            else 0,

        "budgets":
            {},
    }


    for budget in BUDGETS:

        eligible = group[
            group[
                f"supports_budget_{budget}"
            ]
        ]


        eligible_projects = set(
            eligible[
                "fresh_id"
            ].astype(str)
        )


        all_projects = set(
            group[
                "fresh_id"
            ].astype(str)
        )


        result[
            "budgets"
        ][
            str(budget)
        ] = {
            "fragments":
                int(
                    len(
                        eligible
                    )
                ),

            "projects":
                int(
                    len(
                        eligible_projects
                    )
                ),

            "missing_projects":
                sorted(
                    all_projects
                    -
                    eligible_projects
                ),
        }


    return result


# =========================================================
# By split
# =========================================================

by_split = {}


for split_name, group in (
    full.groupby(
        "frozen_split"
    )
):

    by_split[
        str(
            split_name
        )
    ] = summarize_split(
        group
    )


# =========================================================
# Common-budget check
#
# We want at least 15 distinct parent projects in:
#
#   CALIBRATION_KNOWN
#   TEST_KNOWN
#   UNKNOWN_HELDOUT
#
# after imposing the query budget.
# =========================================================

budget_viability = {}


for budget in BUDGETS:

    counts = {}


    for split_name in [
        "CALIBRATION_KNOWN",
        "TEST_KNOWN",
        "UNKNOWN_HELDOUT",
    ]:

        group = full[
            full[
                "frozen_split"
            ]
            == split_name
        ]


        eligible = group[
            group[
                f"supports_budget_{budget}"
            ]
        ]


        counts[
            split_name
        ] = int(
            eligible[
                "fresh_id"
            ].nunique()
        )


    viable = (
        counts[
            "CALIBRATION_KNOWN"
        ]
        >= 15

        and

        counts[
            "TEST_KNOWN"
        ]
        >= 15

        and

        counts[
            "UNKNOWN_HELDOUT"
        ]
        >= 15
    )


    budget_viability[
        str(
            budget
        )
    ] = {
        "projects":
            counts,

        "minimum_15_parent_goal_met":
            bool(
                viable
            ),
    }


# =========================================================
# Highest safe budget
# =========================================================

safe_budgets = [
    budget
    for budget in BUDGETS
    if budget_viability[
        str(
            budget
        )
    ][
        "minimum_15_parent_goal_met"
    ]
]


highest_safe_budget = (
    max(
        safe_budgets
    )
    if safe_budgets
    else None
)


# =========================================================
# Summary
# =========================================================

summary = {
    "query_capacity_audit":
        True,

    "performance_evaluated":
        False,

    "thresholds_tuned":
        False,

    "input_full_heterogeneous_fragments":
        int(
            len(
                full
            )
        ),

    "capacity_definition":
        (
            "5 HARD_MASKED CODE_BINARY components + "
            "all same-release HARD_MASKED STRUCTURED "
            "components + all same-release historical "
            "IMAGE components whose exact original "
            "survives in the source current release"
        ),

    "candidate_query_budgets":
        BUDGETS,

    "minimum_parent_project_goal":
        15,

    "by_split":
        by_split,

    "budget_viability":
        budget_viability,

    "highest_safe_common_budget":
        highest_safe_budget,

    "goals_met":
        bool(
            highest_safe_budget
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

print(
    "======================================"
)

print(
    "PHASE 6I - QUERY CAPACITY AUDIT"
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