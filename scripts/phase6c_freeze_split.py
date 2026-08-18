import hashlib
import json
import random
from pathlib import Path

import pandas as pd


# =========================================================
# Config
# =========================================================

SEED = 20260812

INPUT_CORPUS = Path(
    "results/phase6a_fresh_corpus.csv"
)

INPUT_PACKAGES = Path(
    "data/fresh_registry/"
    "fresh_current_package_registry.csv"
)

OUTPUT_CSV = Path(
    "results/phase6c_project_split.csv"
)

OUTPUT_JSON = Path(
    "results/phase6c_split_summary.json"
)


TARGET_SPLITS = {
    "CALIBRATION_KNOWN": 25,
    "TEST_KNOWN": 45,
    "UNKNOWN_HELDOUT": 20,
}

BACKGROUND_SPLITS = {
    "CALIBRATION_BACKGROUND": 15,
    "TEST_BACKGROUND": 15,
}


# =========================================================
# Hash helper
# =========================================================

def sha256_file(path):

    h = hashlib.sha256()

    with open(
        path,
        "rb"
    ) as f:

        while True:

            chunk = f.read(
                1024 * 1024
            )

            if not chunk:
                break

            h.update(
                chunk
            )

    return h.hexdigest()


# =========================================================
# Load
# =========================================================

if not INPUT_CORPUS.exists():

    raise FileNotFoundError(
        INPUT_CORPUS
    )


if not INPUT_PACKAGES.exists():

    raise FileNotFoundError(
        INPUT_PACKAGES
    )


corpus = pd.read_csv(
    INPUT_CORPUS
)

packages = pd.read_csv(
    INPUT_PACKAGES
)


# =========================================================
# Validation
# =========================================================

required_corpus = {
    "fresh_id",
    "project_id",
    "slug",
    "title",
    "role",
}

missing = (
    required_corpus
    - set(corpus.columns)
)

if missing:

    raise RuntimeError(
        "Missing corpus columns: "
        + str(sorted(missing))
    )


if len(corpus) != 120:

    raise RuntimeError(
        f"Expected 120 projects, "
        f"got {len(corpus)}"
    )


if corpus["fresh_id"].nunique() != 120:

    raise RuntimeError(
        "fresh_id is not unique"
    )


target = corpus[
    corpus["role"]
    == "TARGET_MOD"
].copy()

background = corpus[
    corpus["role"]
    == "BACKGROUND_LIBRARY"
].copy()


if len(target) != 90:

    raise RuntimeError(
        f"Expected 90 TARGET_MOD, "
        f"got {len(target)}"
    )


if len(background) != 30:

    raise RuntimeError(
        "Expected 30 "
        "BACKGROUND_LIBRARY, "
        f"got {len(background)}"
    )


# =========================================================
# Fixed random split
# =========================================================

rng = random.Random(
    SEED
)


target_ids = sorted(
    target[
        "fresh_id"
    ].astype(str).tolist()
)

background_ids = sorted(
    background[
        "fresh_id"
    ].astype(str).tolist()
)


rng.shuffle(
    target_ids
)

rng.shuffle(
    background_ids
)


split_map = {}


# ---------------------------------------------------------
# Target
# ---------------------------------------------------------

offset = 0

for split_name, count in (
    TARGET_SPLITS.items()
):

    selected = target_ids[
        offset:
        offset + count
    ]

    for fresh_id in selected:

        split_map[
            fresh_id
        ] = split_name

    offset += count


# ---------------------------------------------------------
# Background
# ---------------------------------------------------------

offset = 0

for split_name, count in (
    BACKGROUND_SPLITS.items()
):

    selected = background_ids[
        offset:
        offset + count
    ]

    for fresh_id in selected:

        split_map[
            fresh_id
        ] = split_name

    offset += count


if len(split_map) != 120:

    raise RuntimeError(
        "Split assignment incomplete"
    )


# =========================================================
# Create split table
# =========================================================

output = corpus.copy()

output[
    "frozen_split"
] = output[
    "fresh_id"
].map(
    split_map
)


if output[
    "frozen_split"
].isna().any():

    raise RuntimeError(
        "Some projects have no split"
    )


# =========================================================
# Add current package statistics
# =========================================================

package_columns = [
    "fresh_id",
    "code_binary_components",
    "structured_components",
    "image_components",
    "download_bytes",
]


available = [
    column
    for column
    in package_columns
    if column
    in packages.columns
]


package_stats = (
    packages[
        available
    ]
    .drop_duplicates(
        subset=[
            "fresh_id"
        ]
    )
)


output = output.merge(
    package_stats,
    on="fresh_id",
    how="left",
)


for column in [
    "code_binary_components",
    "structured_components",
    "image_components",
]:

    if column not in output.columns:

        output[column] = 0

    output[column] = (
        output[column]
        .fillna(0)
        .astype(int)
    )


output[
    "total_components"
] = (
    output[
        "code_binary_components"
    ]
    +
    output[
        "structured_components"
    ]
    +
    output[
        "image_components"
    ]
)


# =========================================================
# Sort only for readable output
# =========================================================

output = output.sort_values(
    by=[
        "frozen_split",
        "fresh_id",
    ]
).reset_index(
    drop=True
)


# =========================================================
# Save CSV
# =========================================================

OUTPUT_CSV.parent.mkdir(
    parents=True,
    exist_ok=True,
)


output.to_csv(
    OUTPUT_CSV,
    index=False,
    encoding="utf-8-sig",
)


# =========================================================
# Summary
# =========================================================

split_summary = {}


for split_name, group in (
    output.groupby(
        "frozen_split"
    )
):

    split_summary[
        split_name
    ] = {
        "projects":
            int(
                len(group)
            ),

        "target_mods":
            int(
                (
                    group[
                        "role"
                    ]
                    == "TARGET_MOD"
                ).sum()
            ),

        "background_libraries":
            int(
                (
                    group[
                        "role"
                    ]
                    == "BACKGROUND_LIBRARY"
                ).sum()
            ),

        "code_binary_components":
            int(
                group[
                    "code_binary_components"
                ].sum()
            ),

        "structured_components":
            int(
                group[
                    "structured_components"
                ].sum()
            ),

        "image_components":
            int(
                group[
                    "image_components"
                ].sum()
            ),

        "total_components":
            int(
                group[
                    "total_components"
                ].sum()
            ),

        "median_components":
            float(
                group[
                    "total_components"
                ].median()
            ),

        "projects_with_code":
            int(
                (
                    group[
                        "code_binary_components"
                    ]
                    > 0
                ).sum()
            ),

        "projects_with_structured":
            int(
                (
                    group[
                        "structured_components"
                    ]
                    > 0
                ).sum()
            ),

        "projects_with_image":
            int(
                (
                    group[
                        "image_components"
                    ]
                    > 0
                ).sum()
            ),
    }


summary = {
    "random_seed":
        SEED,

    "split_frozen":
        True,

    "pilot_development_corpus":
        "original 30-MOD corpus",

    "fresh_corpus_used_for_development":
        False,

    "fresh_projects":
        int(
            len(output)
        ),

    "target_projects":
        int(
            (
                output[
                    "role"
                ]
                == "TARGET_MOD"
            ).sum()
        ),

    "background_projects":
        int(
            (
                output[
                    "role"
                ]
                == "BACKGROUND_LIBRARY"
            ).sum()
        ),

    "target_split_definition":
        TARGET_SPLITS,

    "background_split_definition":
        BACKGROUND_SPLITS,

    "splits":
        split_summary,

    "input_corpus_sha256":
        sha256_file(
            INPUT_CORPUS
        ),

    "input_package_registry_sha256":
        sha256_file(
            INPUT_PACKAGES
        ),

    "output_split_sha256":
        sha256_file(
            OUTPUT_CSV
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


print(
    "======================================"
)

print(
    "PHASE 6C - FROZEN PROJECT SPLIT"
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
    "CSV :",
    OUTPUT_CSV
)

print(
    "JSON:",
    OUTPUT_JSON
)

print()

print(
    "IMPORTANT:"
)

print(
    "Do not change the seed or "
    "regenerate the split after "
    "looking at performance."
)