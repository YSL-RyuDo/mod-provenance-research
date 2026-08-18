import hashlib
import io
import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path

import pandas as pd
from PIL import Image


CURRENT_COMPONENTS = Path(
    "data/registry/release_component_registry.csv"
)

CURRENT_PACKAGES = Path(
    "data/registry/release_package_registry.csv"
)

HISTORY_RESULTS = Path(
    "results/real_version_component_results.csv"
)

HISTORY_ROOT = Path(
    "data/historical_releases"
)

RELEASE_ROOT = Path(
    "data/release_packages"
)

RESULT_ROOT = Path("results")


# =========================================================
# Fingerprints
# =========================================================

TOKEN_RE = re.compile(
    rb"[A-Za-z_$][A-Za-z0-9_$/.$<>;():\[\]-]{2,}"
)


def simhash64(features):

    features = list(set(features))

    if not features:
        return 0

    weights = [0] * 64

    for feature in features:

        if isinstance(feature, str):
            feature = feature.encode(
                "utf-8",
                errors="ignore"
            )

        digest = hashlib.blake2b(
            feature,
            digest_size=8
        ).digest()

        value = int.from_bytes(
            digest,
            "big"
        )

        for bit in range(64):

            if value & (1 << bit):
                weights[bit] += 1

            else:
                weights[bit] -= 1

    result = 0

    for bit, weight in enumerate(weights):

        if weight >= 0:
            result |= (1 << bit)

    return result


def code_fingerprint(data):

    tokens = TOKEN_RE.findall(data)

    cleaned = []

    for token in tokens:

        if len(token) > 200:
            continue

        cleaned.append(token.lower())

    return simhash64(cleaned)


def flatten_json(obj, features):

    if isinstance(obj, dict):

        for key, value in obj.items():

            features.append(
                f"KEY:{str(key).lower()}"
            )

            flatten_json(
                value,
                features
            )

    elif isinstance(obj, list):

        features.append(
            "LIST"
        )

        for value in obj:

            flatten_json(
                value,
                features
            )

    elif isinstance(obj, str):

        for token in re.findall(
            r"[A-Za-z0-9_$./:-]+",
            obj.lower()
        ):
            features.append(
                "VAL:" + token
            )

    elif isinstance(
        obj,
        (int, float, bool)
    ):

        features.append(
            "TYPE:" +
            type(obj).__name__
        )


def structured_fingerprint(data):

    features = []

    try:

        text = data.decode(
            "utf-8",
            errors="strict"
        )

        obj = json.loads(text)

        flatten_json(
            obj,
            features
        )

    except Exception:

        text = data.decode(
            "utf-8",
            errors="ignore"
        ).lower()

        features.extend(
            re.findall(
                r"[A-Za-z0-9_$./:-]{2,}",
                text
            )
        )

    return simhash64(features)


def image_fingerprint(data):

    try:

        image = Image.open(
            io.BytesIO(data)
        )

        image = image.convert("L")

        image = image.resize(
            (9, 8)
        )

        pixels = list(
            image.getdata()
        )

        result = 0
        bit = 0

        for y in range(8):

            for x in range(8):

                left = pixels[
                    y * 9 + x
                ]

                right = pixels[
                    y * 9 + x + 1
                ]

                if left > right:
                    result |= (
                        1 << bit
                    )

                bit += 1

        return result

    except Exception:

        return None


def fingerprint(
    modality,
    data
):

    if modality == "CODE_BINARY":
        return code_fingerprint(data)

    if modality == "STRUCTURED":
        return structured_fingerprint(
            data
        )

    if modality == "IMAGE":
        return image_fingerprint(data)

    return None


def hamming(a, b):
    return (
        int(a) ^ int(b)
    ).bit_count()


# =========================================================
# JAR helpers
# =========================================================

def find_jar(directory):

    jars = list(
        directory.glob("*.jar")
    )

    if not jars:
        return None

    return jars[0]


def read_entry(
    jar_path,
    relative_path
):

    try:

        with zipfile.ZipFile(
            jar_path,
            "r"
        ) as jar:

            return jar.read(
                relative_path
            )

    except Exception:

        return None


# =========================================================
# Load metadata
# =========================================================

current = pd.read_csv(
    CURRENT_COMPONENTS
)

packages = pd.read_csv(
    CURRENT_PACKAGES
)

history = pd.read_csv(
    HISTORY_RESULTS
)


# =========================================================
# Determine path-failed real queries
# =========================================================

current_path_index = defaultdict(
    set
)

for _, row in current.iterrows():

    path = str(
        row["relative_path"]
    ).replace("\\", "/").lower()

    current_path_index[
        path
    ].add(
        row["mod_id"]
    )


hard_queries = []


for _, row in history.iterrows():

    path = str(
        row["relative_path"]
    ).replace("\\", "/").lower()

    candidates = (
        current_path_index.get(
            path,
            set()
        )
    )

    true_mod = row["mod_id"]

    # FULL_PATH가 unique correct면
    # 쉬운 query이므로 제외
    if (
        len(candidates) == 1
        and
        true_mod in candidates
    ):
        continue

    hard_queries.append(
        row.to_dict()
    )


hard = pd.DataFrame(
    hard_queries
)


print(
    "======================================"
)
print(
    "Phase 3C - Content-only Hard Subset"
)
print(
    "======================================"
)

print(
    f"Path-failed queries: {len(hard)}"
)

if len(hard):

    print(
        hard["modality"]
        .value_counts()
        .to_dict()
    )


# =========================================================
# Build CURRENT fingerprints
# =========================================================

package_filename = dict(
    zip(
        packages["mod_id"],
        packages["filename"]
    )
)


current_fp = defaultdict(list)


for mod_id, group in current.groupby(
    "mod_id"
):

    filename = package_filename.get(
        mod_id
    )

    if filename is None:
        continue

    jar_path = (
        RELEASE_ROOT
        / mod_id
        / filename
    )

    if not jar_path.exists():
        continue

    print(
        f"[INDEX] {mod_id}"
    )

    with zipfile.ZipFile(
        jar_path,
        "r"
    ) as jar:

        names = set(
            jar.namelist()
        )

        for _, row in group.iterrows():

            path = row[
                "relative_path"
            ]

            if path not in names:
                continue

            try:

                data = jar.read(path)

            except Exception:
                continue

            fp = fingerprint(
                row["modality"],
                data
            )

            if fp is None:
                continue

            current_fp[
                row["modality"]
            ].append({

                "mod_id":
                    mod_id,

                "path":
                    path,

                "fp":
                    fp,
            })


print()

for modality, items in (
    current_fp.items()
):

    print(
        f"{modality}: "
        f"{len(items)} indexed"
    )


# =========================================================
# Evaluate historical hard subset
# =========================================================

result_rows = []

jar_cache = {}


for index, row in hard.iterrows():

    mod_id = row["mod_id"]

    version_id = row[
        "historical_version_id"
    ]

    path = row[
        "relative_path"
    ]

    modality = row[
        "modality"
    ]

    key = (
        mod_id,
        version_id
    )

    if key not in jar_cache:

        directory = (
            HISTORY_ROOT
            / mod_id
            / version_id
        )

        jar_cache[key] = (
            find_jar(directory)
        )

    jar_path = jar_cache[key]

    if jar_path is None:
        continue

    data = read_entry(
        jar_path,
        path
    )

    if data is None:
        continue

    query_fp = fingerprint(
        modality,
        data
    )

    if query_fp is None:
        continue

    candidates = (
        current_fp.get(
            modality,
            []
        )
    )

    # ----------------------------------
    # 먼저 MOD별 최적 component 찾기
    # ----------------------------------

    best_by_mod = {}

    for candidate in candidates:

        distance = hamming(
            query_fp,
            candidate["fp"]
        )

        candidate_mod = (
            candidate["mod_id"]
        )

        previous = (
            best_by_mod.get(
                candidate_mod
            )
        )

        if (
            previous is None
            or
            distance
            < previous[0]
        ):

            best_by_mod[
                candidate_mod
            ] = (
                distance,
                candidate["path"]
            )


    if not best_by_mod:
        continue


    ranked = sorted(
        best_by_mod.items(),
        key=lambda x:
            x[1][0]
    )


    best_distance = (
        ranked[0][1][0]
    )

    best_mods = [
        candidate_mod
        for candidate_mod, info
        in ranked
        if info[0] == best_distance
    ]


    if len(ranked) >= 2:

        different_distances = sorted(
            set(
                info[0]
                for _, info
                in ranked
            )
        )

        if (
            len(
                different_distances
            ) >= 2
        ):

            second_distance = (
                different_distances[1]
            )

        else:

            second_distance = (
                best_distance
            )

    else:

        second_distance = 64


    margin = (
        second_distance
        - best_distance
    )


    if (
        len(best_mods) == 1
        and
        best_mods[0] == mod_id
    ):

        verdict = "CORRECT_UNIQUE"

    elif mod_id in best_mods:

        verdict = (
            "AMBIGUOUS_TRUE_INCLUDED"
        )

    elif len(best_mods) == 1:

        verdict = "WRONG_UNIQUE"

    else:

        verdict = "AMBIGUOUS_WRONG"


    result_rows.append({

        "mod_id":
            mod_id,

        "historical_version":
            row[
                "historical_version"
            ],

        "historical_version_id":
            version_id,

        "modality":
            modality,

        "relative_path":
            path,

        "best_distance":
            best_distance,

        "second_distance":
            second_distance,

        "margin":
            margin,

        "best_mods":
            "|".join(
                sorted(best_mods)
            ),

        "verdict":
            verdict,
    })


    if (
        len(result_rows)
        % 250 == 0
    ):

        print(
            f"evaluated "
            f"{len(result_rows)}"
        )


results = pd.DataFrame(
    result_rows
)


# =========================================================
# Summaries
# =========================================================

summary = {
    "path_failed_queries":
        len(hard),

    "content_queries_evaluated":
        len(results),
}


def summarize(group):

    total = len(group)

    counts = (
        group["verdict"]
        .value_counts()
        .to_dict()
    )

    return {

        "components":
            total,

        "unique_correct_rate":
            counts.get(
                "CORRECT_UNIQUE",
                0
            )
            / total,

        "true_in_best_tie_rate":
            (
                counts.get(
                    "CORRECT_UNIQUE",
                    0
                )
                +
                counts.get(
                    "AMBIGUOUS_TRUE_INCLUDED",
                    0
                )
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

        "mean_best_distance":
            float(
                group[
                    "best_distance"
                ].mean()
            ),

        "mean_margin":
            float(
                group[
                    "margin"
                ].mean()
            ),
    }


if len(results):

    summary["ALL"] = summarize(
        results
    )

    summary[
        "by_modality"
    ] = {}

    for modality, group in (
        results.groupby(
            "modality"
        )
    ):

        summary[
            "by_modality"
        ][modality] = (
            summarize(group)
        )


# =========================================================
# Save
# =========================================================

results.to_csv(
    RESULT_ROOT
    / "content_baseline_path_failed.csv",

    index=False,
    encoding="utf-8-sig",
)


with open(
    RESULT_ROOT
    / "phase3c_summary.json",

    "w",
    encoding="utf-8",
) as f:

    json.dump(
        summary,
        f,
        ensure_ascii=False,
        indent=2,
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
        summary,
        ensure_ascii=False,
        indent=2
    )
)