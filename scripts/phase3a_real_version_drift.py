import hashlib
import json
import shutil
import time
import zipfile
from collections import defaultdict
from pathlib import Path

import pandas as pd
import requests


# =========================================================
# Config
# =========================================================

CURRENT_PACKAGE_REGISTRY = Path(
    "data/registry/release_package_registry.csv"
)

CURRENT_COMPONENT_REGISTRY = Path(
    "data/registry/release_component_registry.csv"
)

HISTORY_ROOT = Path(
    "data/historical_releases"
)

RESULT_ROOT = Path("results")

HISTORY_ROOT.mkdir(
    parents=True,
    exist_ok=True
)

RESULT_ROOT.mkdir(
    parents=True,
    exist_ok=True
)

MODRINTH_API = "https://api.modrinth.com/v2"

HEADERS = {
    "User-Agent":
        "mod-provenance-research/0.1"
}

OLDER_VERSIONS_PER_MOD = 3


# =========================================================
# Helpers
# =========================================================

def api_get(path, params=None):
    r = requests.get(
        MODRINTH_API + path,
        headers=HEADERS,
        params=params,
        timeout=60,
    )

    r.raise_for_status()

    return r.json()


def sha256_bytes(data):
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def classify_entry(path):
    lower = path.lower()

    if lower.endswith(".class"):
        return "CODE_BINARY"

    if (
        lower.endswith(".json")
        or lower.endswith(".yaml")
        or lower.endswith(".yml")
        or lower.endswith(".xml")
        or lower.endswith(".mcmeta")
    ):
        return "STRUCTURED"

    if (
        lower.endswith(".png")
        or lower.endswith(".jpg")
        or lower.endswith(".jpeg")
    ):
        return "IMAGE"

    return None


def should_ignore(path):
    lower = path.lower()

    if lower.startswith("meta-inf/"):
        return True

    if "__macosx/" in lower:
        return True

    if lower.endswith(".ds_store"):
        return True

    return False


def primary_jar(version):
    files = version.get("files") or []

    jar_files = [
        f for f in files
        if (
            f.get("filename", "")
            .lower()
            .endswith(".jar")
            and
            f.get("file_type")
            not in {
                "sources-jar",
                "dev-jar",
                "javadoc-jar",
            }
        )
    ]

    if not jar_files:
        return None

    for f in jar_files:
        if f.get("primary"):
            return f

    return jar_files[0]


def download(url, path):
    if path.exists():
        return

    with requests.get(
        url,
        headers=HEADERS,
        stream=True,
        timeout=180,
    ) as r:

        r.raise_for_status()

        with open(path, "wb") as f:

            for chunk in r.iter_content(
                chunk_size=1024 * 1024
            ):
                if chunk:
                    f.write(chunk)


def extract_components(jar_path):
    components = []

    with zipfile.ZipFile(
        jar_path,
        "r"
    ) as jar:

        for info in jar.infolist():

            if info.is_dir():
                continue

            path = (
                info.filename
                .replace("\\", "/")
            )

            if should_ignore(path):
                continue

            modality = classify_entry(path)

            if modality is None:
                continue

            try:
                data = jar.read(info)
            except Exception:
                continue

            components.append({
                "relative_path": path,
                "modality": modality,
                "sha256":
                    sha256_bytes(data),
                "size_bytes":
                    len(data),
            })

    return components


# =========================================================
# Load current registry
# =========================================================

packages = pd.read_csv(
    CURRENT_PACKAGE_REGISTRY
)

current = pd.read_csv(
    CURRENT_COMPONENT_REGISTRY
)


# ---------------------------------------------------------
# Current indexes
# ---------------------------------------------------------

# MOD -> SHA set
current_mod_hashes = {}

# MOD -> path -> SHA
current_mod_paths = {}

for mod_id, group in current.groupby(
    "mod_id"
):

    current_mod_hashes[mod_id] = set(
        group["sha256"]
        .astype(str)
        .tolist()
    )

    current_mod_paths[mod_id] = dict(
        zip(
            group[
                "relative_path"
            ].astype(str),

            group[
                "sha256"
            ].astype(str),
        )
    )


# hash -> current MOD IDs
hash_to_current_mods = defaultdict(set)

for _, row in current.iterrows():

    hash_to_current_mods[
        str(row["sha256"])
    ].add(
        row["mod_id"]
    )


# =========================================================
# Evaluation
# =========================================================

raw_rows = []
version_rows = []
failed = []


print(
    "======================================"
)

print(
    "Phase 3A - Real Version Drift"
)

print(
    "======================================"
)


for package_index, pkg in packages.iterrows():

    mod_id = pkg["mod_id"]
    title = pkg["title"]

    project_id = pkg["modrinth_id"]
    current_version_id = pkg["version_id"]

    print()
    print(
        f"[{package_index + 1}/"
        f"{len(packages)}] "
        f"{mod_id} - {title}"
    )

    try:

        versions = api_get(
            f"/project/{project_id}/version",
            params={
                "loaders":
                    json.dumps(
                        ["fabric"]
                    ),

                "include_changelog":
                    "false",
            },
        )

    except Exception as e:

        print(
            f"[FAILED] version list: {e}"
        )

        failed.append({
            "mod_id": mod_id,
            "reason": str(e),
        })

        continue


    # 날짜 명시적으로 정렬
    versions = sorted(
        versions,
        key=lambda x:
            x.get(
                "date_published",
                ""
            ),
        reverse=True,
    )


    # 현재 Phase 2C에서 사용한
    # 정확한 version 위치 찾기
    current_position = None

    for i, version in enumerate(
        versions
    ):

        if (
            version.get("id")
            == current_version_id
        ):

            current_position = i
            break


    if current_position is None:

        print(
            "[WARNING] current version "
            "not found"
        )

        continue


    older = versions[
        current_position + 1:
    ]


    # JAR 있는 버전만 최대 3개
    selected = []

    for version in older:

        file_info = primary_jar(
            version
        )

        if file_info is None:
            continue

        selected.append(
            (version, file_info)
        )

        if (
            len(selected)
            >= OLDER_VERSIONS_PER_MOD
        ):
            break


    print(
        f"historical versions selected: "
        f"{len(selected)}"
    )


    for history_index, (
        version,
        file_info,
    ) in enumerate(
        selected,
        start=1,
    ):

        version_id = version["id"]

        version_number = (
            version.get(
                "version_number"
            )
        )

        date_published = (
            version.get(
                "date_published"
            )
        )

        filename = (
            file_info["filename"]
        )

        print(
            f"  [{history_index}] "
            f"{version_number}"
        )


        version_dir = (
            HISTORY_ROOT
            / mod_id
            / version_id
        )

        version_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        jar_path = (
            version_dir
            / filename
        )


        try:

            download(
                file_info["url"],
                jar_path,
            )

            history_components = (
                extract_components(
                    jar_path
                )
            )

        except Exception as e:

            print(
                f"  [FAILED] {e}"
            )

            failed.append({
                "mod_id":
                    mod_id,

                "version_id":
                    version_id,

                "reason":
                    str(e),
            })

            continue


        same_mod_hashes = (
            current_mod_hashes.get(
                mod_id,
                set(),
            )
        )

        same_mod_paths = (
            current_mod_paths.get(
                mod_id,
                {},
            )
        )


        counts = defaultdict(int)

        modality_counts = defaultdict(
            lambda: defaultdict(int)
        )


        for component in (
            history_components
        ):

            path = (
                component[
                    "relative_path"
                ]
            )

            digest = (
                component["sha256"]
            )

            modality = (
                component["modality"]
            )


            # --------------------------------
            # Real version survival
            # --------------------------------

            path_current_hash = (
                same_mod_paths.get(path)
            )


            if (
                path_current_hash
                == digest
            ):

                survival = (
                    "UNCHANGED_SAME_PATH"
                )

            elif (
                digest
                in same_mod_hashes
            ):

                survival = (
                    "UNCHANGED_MOVED_PATH"
                )

            else:

                survival = (
                    "CHANGED_OR_REMOVED"
                )


            # --------------------------------
            # Exact provenance attribution
            # --------------------------------

            candidate_mods = sorted(
                hash_to_current_mods.get(
                    digest,
                    set(),
                )
            )


            if not candidate_mods:

                attribution = (
                    "NO_EXACT_MATCH"
                )

            elif (
                len(candidate_mods) == 1
                and
                candidate_mods[0]
                == mod_id
            ):

                attribution = (
                    "CORRECT_PARENT"
                )

            elif (
                mod_id
                in candidate_mods
                and
                len(candidate_mods) > 1
            ):

                attribution = (
                    "AMBIGUOUS"
                )

            else:

                attribution = (
                    "WRONG_PARENT"
                )


            counts[survival] += 1
            counts[attribution] += 1

            modality_counts[
                modality
            ][survival] += 1

            modality_counts[
                modality
            ][attribution] += 1


            raw_rows.append({

                "mod_id":
                    mod_id,

                "title":
                    title,

                "historical_version_id":
                    version_id,

                "historical_version":
                    version_number,

                "date_published":
                    date_published,

                "relative_path":
                    path,

                "modality":
                    modality,

                "sha256":
                    digest,

                "survival_status":
                    survival,

                "exact_attribution":
                    attribution,

                "candidate_mods":
                    "|".join(
                        candidate_mods
                    ),
            })


        total = len(
            history_components
        )


        if total == 0:
            continue


        version_rows.append({

            "mod_id":
                mod_id,

            "title":
                title,

            "role":
                pkg["role"],

            "historical_version_id":
                version_id,

            "historical_version":
                version_number,

            "date_published":
                date_published,

            "component_count":
                total,

            "unchanged_same_path":
                counts[
                    "UNCHANGED_SAME_PATH"
                ],

            "unchanged_moved_path":
                counts[
                    "UNCHANGED_MOVED_PATH"
                ],

            "changed_or_removed":
                counts[
                    "CHANGED_OR_REMOVED"
                ],

            "exact_correct_parent":
                counts[
                    "CORRECT_PARENT"
                ],

            "exact_no_match":
                counts[
                    "NO_EXACT_MATCH"
                ],

            "exact_ambiguous":
                counts[
                    "AMBIGUOUS"
                ],

            "exact_wrong_parent":
                counts[
                    "WRONG_PARENT"
                ],

            "exact_parent_recall":
                (
                    counts[
                        "CORRECT_PARENT"
                    ]
                    / total
                ),
        })


        print(
            "    total="
            f"{total} "
            "exact-parent="
            f"{counts['CORRECT_PARENT'] / total:.3f}"
        )


# =========================================================
# Save raw
# =========================================================

raw = pd.DataFrame(
    raw_rows
)

versions_df = pd.DataFrame(
    version_rows
)


raw_path = (
    RESULT_ROOT
    / "real_version_component_results.csv"
)

version_path = (
    RESULT_ROOT
    / "real_version_summary.csv"
)


raw.to_csv(
    raw_path,
    index=False,
    encoding="utf-8-sig",
)

versions_df.to_csv(
    version_path,
    index=False,
    encoding="utf-8-sig",
)


# =========================================================
# Overall summary
# =========================================================

summary = {

    "projects":
        len(packages),

    "historical_versions_tested":
        len(versions_df),

    "historical_components_tested":
        len(raw),

    "failed_operations":
        len(failed),
}


if len(raw):

    total = len(raw)

    summary.update({

        "unchanged_same_path_rate":
            float(
                (
                    raw[
                        "survival_status"
                    ]
                    ==
                    "UNCHANGED_SAME_PATH"
                ).mean()
            ),

        "unchanged_moved_path_rate":
            float(
                (
                    raw[
                        "survival_status"
                    ]
                    ==
                    "UNCHANGED_MOVED_PATH"
                ).mean()
            ),

        "changed_or_removed_rate":
            float(
                (
                    raw[
                        "survival_status"
                    ]
                    ==
                    "CHANGED_OR_REMOVED"
                ).mean()
            ),

        "exact_parent_recall":
            float(
                (
                    raw[
                        "exact_attribution"
                    ]
                    ==
                    "CORRECT_PARENT"
                ).mean()
            ),

        "exact_no_match_rate":
            float(
                (
                    raw[
                        "exact_attribution"
                    ]
                    ==
                    "NO_EXACT_MATCH"
                ).mean()
            ),

        "exact_ambiguous_rate":
            float(
                (
                    raw[
                        "exact_attribution"
                    ]
                    ==
                    "AMBIGUOUS"
                ).mean()
            ),

        "exact_wrong_parent_rate":
            float(
                (
                    raw[
                        "exact_attribution"
                    ]
                    ==
                    "WRONG_PARENT"
                ).mean()
            ),
    })


    # modality breakdown
    modality_summary = {}

    for modality, group in (
        raw.groupby("modality")
    ):

        modality_summary[
            modality
        ] = {

            "components":
                len(group),

            "exact_parent_recall":
                float(
                    (
                        group[
                            "exact_attribution"
                        ]
                        ==
                        "CORRECT_PARENT"
                    ).mean()
                ),

            "changed_or_removed_rate":
                float(
                    (
                        group[
                            "survival_status"
                        ]
                        ==
                        "CHANGED_OR_REMOVED"
                    ).mean()
                ),
        }

    summary[
        "by_modality"
    ] = modality_summary


with open(
    RESULT_ROOT
    / "phase3a_summary.json",
    "w",
    encoding="utf-8",
) as f:

    json.dump(
        summary,
        f,
        ensure_ascii=False,
        indent=2,
    )


with open(
    RESULT_ROOT
    / "phase3a_failed.json",
    "w",
    encoding="utf-8",
) as f:

    json.dump(
        failed,
        f,
        ensure_ascii=False,
        indent=2,
    )


print()
print(
    "======================================"
)

print("RESULT")

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
    f"Raw results : {raw_path}"
)

print(
    f"Version summary : "
    f"{version_path}"
)