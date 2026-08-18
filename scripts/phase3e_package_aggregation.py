import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd


INPUT = Path(
    "results/bytecode_baseline_raw.csv"
)

OUTPUT_RAW = Path(
    "results/package_aggregation_raw.csv"
)

OUTPUT_SUMMARY = Path(
    "results/package_aggregation_summary.csv"
)

OUTPUT_JSON = Path(
    "results/phase3e_summary.json"
)


# =========================================================
# Load
# =========================================================

df = pd.read_csv(INPUT)


required = {
    "mod_id",
    "historical_version_id",
    "representation",
    "best_mods",
    "best_distance",
    "true_distance",
    "optimistic_rank",
}

missing = required - set(df.columns)

if missing:
    raise RuntimeError(
        f"Missing columns: {missing}"
    )


print(
    "======================================"
)
print(
    "Phase 3E - Package Aggregation Baseline"
)
print(
    "======================================"
)

print(
    f"Component-result rows: {len(df)}"
)


# =========================================================
# Helpers
# =========================================================

def split_mods(text):

    if pd.isna(text):
        return []

    return [
        x
        for x in str(text).split("|")
        if x
    ]


def rank_scores(scores):

    return sorted(
        scores.items(),
        key=lambda x: (
            -x[1],
            x[0]
        )
    )


def rank_costs(costs):

    return sorted(
        costs.items(),
        key=lambda x: (
            x[1],
            x[0]
        )
    )


# =========================================================
# Per-package aggregation
# =========================================================

rows = []


group_columns = [
    "representation",
    "mod_id",
    "historical_version_id",
]


groups = df.groupby(
    group_columns,
    sort=False
)


for (
    representation,
    true_mod,
    version_id
), group in groups:

    component_count = len(group)

    # -----------------------------------------------------
    # Method A:
    # Top-1 fractional voting
    #
    # tie가 4개면 각 MOD에 1/4표
    # -----------------------------------------------------

    fractional_votes = defaultdict(
        float
    )


    # -----------------------------------------------------
    # Method B:
    # Reciprocal-rank evidence
    #
    # 현재 CSV에는 전체 ranking이 없으므로
    # true rank만 쓰면 leakage가 생김.
    # 따라서 여기서는 사용하지 않는다.
    # -----------------------------------------------------


    # -----------------------------------------------------
    # Method C:
    # Best-distance confidence-weighted vote
    #
    # 가까운 fingerprint일수록 더 큰 표.
    # best MOD tie에 균등 배분.
    # -----------------------------------------------------

    confidence_votes = defaultdict(
        float
    )


    for _, row in group.iterrows():

        best_mods = split_mods(
            row["best_mods"]
        )

        if not best_mods:
            continue

        tie_size = len(best_mods)

        fractional = (
            1.0 / tie_size
        )

        distance = float(
            row["best_distance"]
        )

        # 128-bit Hamming 기준
        # 단순하고 고정된 confidence.
        confidence = (
            1.0 / (1.0 + distance)
        )

        for candidate in best_mods:

            fractional_votes[
                candidate
            ] += fractional

            confidence_votes[
                candidate
            ] += (
                confidence
                / tie_size
            )


    # -----------------------------------------------------
    # Fractional voting result
    # -----------------------------------------------------

    frac_ranked = rank_scores(
        fractional_votes
    )

    if frac_ranked:

        frac_best_score = (
            frac_ranked[0][1]
        )

        frac_best_mods = [
            mod
            for mod, score
            in frac_ranked
            if math.isclose(
                score,
                frac_best_score,
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
        ]

        frac_true_rank = (
            1
            +
            sum(
                1
                for _, score
                in frac_ranked
                if score
                > fractional_votes.get(
                    true_mod,
                    0.0
                )
            )
        )

    else:

        frac_best_mods = []
        frac_true_rank = 999999


    # -----------------------------------------------------
    # Confidence voting result
    # -----------------------------------------------------

    conf_ranked = rank_scores(
        confidence_votes
    )

    if conf_ranked:

        conf_best_score = (
            conf_ranked[0][1]
        )

        conf_best_mods = [
            mod
            for mod, score
            in conf_ranked
            if math.isclose(
                score,
                conf_best_score,
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
        ]

        conf_true_rank = (
            1
            +
            sum(
                1
                for _, score
                in conf_ranked
                if score
                > confidence_votes.get(
                    true_mod,
                    0.0
                )
            )
        )

    else:

        conf_best_mods = []
        conf_true_rank = 999999


    # -----------------------------------------------------
    # Record
    # -----------------------------------------------------

    rows.append({

        "representation":
            representation,

        "true_mod":
            true_mod,

        "historical_version_id":
            version_id,

        "component_count":
            component_count,

        "fractional_best_mods":
            "|".join(
                sorted(
                    frac_best_mods
                )
            ),

        "fractional_true_rank":
            frac_true_rank,

        "fractional_top1_unique_correct":
            (
                len(frac_best_mods)
                == 1
                and
                frac_best_mods[0]
                == true_mod
            ),

        "fractional_top1_true_in_tie":
            (
                true_mod
                in frac_best_mods
            ),

        "fractional_top3":
            frac_true_rank <= 3,

        "fractional_top5":
            frac_true_rank <= 5,

        "confidence_best_mods":
            "|".join(
                sorted(
                    conf_best_mods
                )
            ),

        "confidence_true_rank":
            conf_true_rank,

        "confidence_top1_unique_correct":
            (
                len(conf_best_mods)
                == 1
                and
                conf_best_mods[0]
                == true_mod
            ),

        "confidence_top1_true_in_tie":
            (
                true_mod
                in conf_best_mods
            ),

        "confidence_top3":
            conf_true_rank <= 3,

        "confidence_top5":
            conf_true_rank <= 5,
    })


result = pd.DataFrame(rows)


# =========================================================
# Summary
# =========================================================

summary_rows = []


for representation, group in (
    result.groupby(
        "representation"
    )
):

    n = len(group)

    component_counts = (
        group["component_count"]
    )


    record = {

        "representation":
            representation,

        "historical_packages":
            n,

        "mean_hard_components":
            float(
                component_counts.mean()
            ),

        "median_hard_components":
            float(
                component_counts.median()
            ),

        # fractional
        "fractional_top1_unique":
            float(
                group[
                    "fractional_top1_unique_correct"
                ].mean()
            ),

        "fractional_top1_true_in_tie":
            float(
                group[
                    "fractional_top1_true_in_tie"
                ].mean()
            ),

        "fractional_top3":
            float(
                group[
                    "fractional_top3"
                ].mean()
            ),

        "fractional_top5":
            float(
                group[
                    "fractional_top5"
                ].mean()
            ),

        # confidence
        "confidence_top1_unique":
            float(
                group[
                    "confidence_top1_unique_correct"
                ].mean()
            ),

        "confidence_top1_true_in_tie":
            float(
                group[
                    "confidence_top1_true_in_tie"
                ].mean()
            ),

        "confidence_top3":
            float(
                group[
                    "confidence_top3"
                ].mean()
            ),

        "confidence_top5":
            float(
                group[
                    "confidence_top5"
                ].mean()
            ),
    }

    summary_rows.append(
        record
    )


summary_df = pd.DataFrame(
    summary_rows
)


# =========================================================
# By number of hard components
# =========================================================

def size_bucket(n):

    if n == 1:
        return "1"

    if n <= 3:
        return "2-3"

    if n <= 5:
        return "4-5"

    if n <= 10:
        return "6-10"

    if n <= 20:
        return "11-20"

    return "21+"


result[
    "component_bucket"
] = (
    result[
        "component_count"
    ].map(
        size_bucket
    )
)


bucket_rows = []


for (
    representation,
    bucket
), group in result.groupby(
    [
        "representation",
        "component_bucket",
    ]
):

    bucket_rows.append({

        "representation":
            representation,

        "component_bucket":
            bucket,

        "packages":
            len(group),

        "fractional_top1_unique":
            float(
                group[
                    "fractional_top1_unique_correct"
                ].mean()
            ),

        "confidence_top1_unique":
            float(
                group[
                    "confidence_top1_unique_correct"
                ].mean()
            ),
    })


bucket_df = pd.DataFrame(
    bucket_rows
)


# =========================================================
# Save
# =========================================================

result.to_csv(
    OUTPUT_RAW,
    index=False,
    encoding="utf-8-sig",
)

summary_df.to_csv(
    OUTPUT_SUMMARY,
    index=False,
    encoding="utf-8-sig",
)

bucket_df.to_csv(
    "results/package_aggregation_by_size.csv",
    index=False,
    encoding="utf-8-sig",
)


summary_json = {}


for _, row in (
    summary_df.iterrows()
):

    rep = row[
        "representation"
    ]

    summary_json[rep] = {

        "historical_packages":
            int(
                row[
                    "historical_packages"
                ]
            ),

        "mean_hard_components":
            float(
                row[
                    "mean_hard_components"
                ]
            ),

        "median_hard_components":
            float(
                row[
                    "median_hard_components"
                ]
            ),

        "fractional_voting": {

            "top1_unique":
                float(
                    row[
                        "fractional_top1_unique"
                    ]
                ),

            "top1_true_in_tie":
                float(
                    row[
                        "fractional_top1_true_in_tie"
                    ]
                ),

            "top3":
                float(
                    row[
                        "fractional_top3"
                    ]
                ),

            "top5":
                float(
                    row[
                        "fractional_top5"
                    ]
                ),
        },

        "confidence_voting": {

            "top1_unique":
                float(
                    row[
                        "confidence_top1_unique"
                    ]
                ),

            "top1_true_in_tie":
                float(
                    row[
                        "confidence_top1_true_in_tie"
                    ]
                ),

            "top3":
                float(
                    row[
                        "confidence_top3"
                    ]
                ),

            "top5":
                float(
                    row[
                        "confidence_top5"
                    ]
                ),
        },
    }


OUTPUT_JSON.write_text(
    json.dumps(
        summary_json,
        ensure_ascii=False,
        indent=2
    ),
    encoding="utf-8"
)


print()
print(
    "======================================"
)
print(
    "RESULT"
)
print(
    "======================================"
)

print(
    json.dumps(
        summary_json,
        ensure_ascii=False,
        indent=2
    )
)

print()
print(
    "Summary: "
    "results\\package_aggregation_summary.csv"
)

print(
    "Size analysis: "
    "results\\package_aggregation_by_size.csv"
)