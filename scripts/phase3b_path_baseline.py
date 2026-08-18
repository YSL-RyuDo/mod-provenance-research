import json
from collections import defaultdict
from pathlib import Path, PurePosixPath

import pandas as pd


CURRENT = Path(
    "data/registry/release_component_registry.csv"
)

HISTORY = Path(
    "results/real_version_component_results.csv"
)

RESULT_ROOT = Path("results")
RESULT_ROOT.mkdir(exist_ok=True)


# =========================================================
# Normalization
# =========================================================

def norm_path(path):
    return str(path).replace("\\", "/").lower()


def basename(path):
    return PurePosixPath(
        norm_path(path)
    ).name


def outer_class_name(path):
    """
    Foo$Bar.class -> Foo.class

    CODE_BINARY가 아니면 basename 그대로.
    """

    name = basename(path)

    if not name.endswith(".class"):
        return name

    stem = name[:-6]

    if "$" in stem:
        stem = stem.split("$")[0]

    return stem + ".class"


# =========================================================
# Index
# =========================================================

current = pd.read_csv(CURRENT)
history = pd.read_csv(HISTORY)


path_index = defaultdict(set)
basename_index = defaultdict(set)
outer_class_index = defaultdict(set)
hash_index = defaultdict(set)


for _, row in current.iterrows():

    mod_id = row["mod_id"]
    path = row["relative_path"]
    digest = str(row["sha256"])

    path_index[
        norm_path(path)
    ].add(mod_id)

    basename_index[
        basename(path)
    ].add(mod_id)

    outer_class_index[
        outer_class_name(path)
    ].add(mod_id)

    hash_index[
        digest
    ].add(mod_id)


# =========================================================
# Verdict
# =========================================================

def verdict(candidates, true_mod):

    candidates = set(candidates)

    if not candidates:
        return "NO_MATCH"

    if len(candidates) == 1:

        if true_mod in candidates:
            return "CORRECT_UNIQUE"

        return "WRONG_UNIQUE"

    if true_mod in candidates:
        return "AMBIGUOUS_TRUE_INCLUDED"

    return "AMBIGUOUS_WRONG"


# =========================================================
# Evaluate
# =========================================================

rows = []


for _, row in history.iterrows():

    true_mod = row["mod_id"]

    path = row["relative_path"]
    digest = str(row["sha256"])
    modality = row["modality"]

    candidates = {

        "SHA256":
            hash_index.get(
                digest,
                set()
            ),

        "FULL_PATH":
            path_index.get(
                norm_path(path),
                set()
            ),

        "BASENAME":
            basename_index.get(
                basename(path),
                set()
            ),

        "OUTER_CLASS_NAME":
            outer_class_index.get(
                outer_class_name(path),
                set()
            ),
    }

    # 단순 diagnostic union
    candidates["SHA_OR_PATH"] = (
        set(candidates["SHA256"])
        |
        set(candidates["FULL_PATH"])
    )


    for method, candidate_set in (
        candidates.items()
    ):

        rows.append({

            "mod_id":
                true_mod,

            "historical_version":
                row[
                    "historical_version"
                ],

            "modality":
                modality,

            "relative_path":
                path,

            "method":
                method,

            "candidate_count":
                len(candidate_set),

            "candidate_mods":
                "|".join(
                    sorted(candidate_set)
                ),

            "verdict":
                verdict(
                    candidate_set,
                    true_mod
                ),
        })


results = pd.DataFrame(rows)


# =========================================================
# Summary
# =========================================================

summary_rows = []


def summarize(group, method, modality):

    total = len(group)

    if total == 0:
        return

    counts = (
        group["verdict"]
        .value_counts()
        .to_dict()
    )

    correct = counts.get(
        "CORRECT_UNIQUE",
        0
    )

    ambiguous_true = counts.get(
        "AMBIGUOUS_TRUE_INCLUDED",
        0
    )

    wrong = (
        counts.get(
            "WRONG_UNIQUE",
            0
        )
        +
        counts.get(
            "AMBIGUOUS_WRONG",
            0
        )
    )

    no_match = counts.get(
        "NO_MATCH",
        0
    )

    summary_rows.append({

        "method":
            method,

        "modality":
            modality,

        "components":
            total,

        "unique_correct_rate":
            correct / total,

        "true_in_candidate_rate":
            (
                correct
                + ambiguous_true
            )
            / total,

        "ambiguous_true_rate":
            ambiguous_true / total,

        "wrong_rate":
            wrong / total,

        "no_match_rate":
            no_match / total,

        "mean_candidate_count":
            group[
                "candidate_count"
            ].mean(),
    })


for method, method_group in (
    results.groupby("method")
):

    summarize(
        method_group,
        method,
        "ALL"
    )

    for modality, group in (
        method_group.groupby(
            "modality"
        )
    ):

        summarize(
            group,
            method,
            modality
        )


summary_df = pd.DataFrame(
    summary_rows
)


# =========================================================
# TARGET / BACKGROUND split
# =========================================================

current_mod_role = (
    current[
        ["mod_id", "role"]
    ]
    .drop_duplicates()
    .set_index("mod_id")["role"]
    .to_dict()
)

results["role"] = (
    results["mod_id"]
    .map(current_mod_role)
)


role_rows = []


for (
    method,
    role
), group in results.groupby(
    ["method", "role"]
):

    total = len(group)

    counts = (
        group["verdict"]
        .value_counts()
        .to_dict()
    )

    role_rows.append({

        "method":
            method,

        "role":
            role,

        "components":
            total,

        "unique_correct_rate":
            counts.get(
                "CORRECT_UNIQUE",
                0
            )
            / total,

        "ambiguous_true_rate":
            counts.get(
                "AMBIGUOUS_TRUE_INCLUDED",
                0
            )
            / total,

        "wrong_rate":
            (
                counts.get(
                    "WRONG_UNIQUE",
                    0
                )
                +
                counts.get(
                    "AMBIGUOUS_WRONG",
                    0
                )
            )
            / total,

        "no_match_rate":
            counts.get(
                "NO_MATCH",
                0
            )
            / total,
    })


role_df = pd.DataFrame(
    role_rows
)


# =========================================================
# Save
# =========================================================

results.to_csv(
    RESULT_ROOT
    / "path_baseline_raw.csv",

    index=False,
    encoding="utf-8-sig",
)

summary_df.to_csv(
    RESULT_ROOT
    / "path_baseline_summary.csv",

    index=False,
    encoding="utf-8-sig",
)

role_df.to_csv(
    RESULT_ROOT
    / "path_baseline_role_summary.csv",

    index=False,
    encoding="utf-8-sig",
)


overall = {}

for method in [
    "SHA256",
    "FULL_PATH",
    "BASENAME",
    "OUTER_CLASS_NAME",
    "SHA_OR_PATH",
]:

    match = summary_df[
        (
            summary_df["method"]
            == method
        )
        &
        (
            summary_df["modality"]
            == "ALL"
        )
    ]

    if len(match) == 0:
        continue

    row = match.iloc[0]

    overall[method] = {

        "unique_correct_rate":
            float(
                row[
                    "unique_correct_rate"
                ]
            ),

        "true_in_candidate_rate":
            float(
                row[
                    "true_in_candidate_rate"
                ]
            ),

        "ambiguous_true_rate":
            float(
                row[
                    "ambiguous_true_rate"
                ]
            ),

        "wrong_rate":
            float(
                row[
                    "wrong_rate"
                ]
            ),

        "no_match_rate":
            float(
                row[
                    "no_match_rate"
                ]
            ),
    }


with open(
    RESULT_ROOT
    / "phase3b_summary.json",

    "w",
    encoding="utf-8",
) as f:

    json.dump(
        overall,
        f,
        ensure_ascii=False,
        indent=2,
    )


print()
print(
    "======================================"
)
print(
    "Phase 3B RESULT"
)
print(
    "======================================"
)

print(
    json.dumps(
        overall,
        ensure_ascii=False,
        indent=2,
    )
)

print()
print(
    "Detailed summary : "
    "results\\path_baseline_summary.csv"
)

print(
    "Role summary     : "
    "results\\path_baseline_role_summary.csv"
)