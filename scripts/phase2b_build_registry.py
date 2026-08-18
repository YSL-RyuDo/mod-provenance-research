import hashlib
import json
import re
import shutil
import time
import zipfile
from collections import defaultdict
from pathlib import Path, PurePosixPath

import pandas as pd
import requests


# =========================================================
# Config
# =========================================================

INPUT = Path("results/dataset_corpus_v3.csv")

DATA_ROOT = Path("data")
SOURCE_ROOT = DATA_ROOT / "source"
REGISTRY_ROOT = DATA_ROOT / "registry"

RESULT_ROOT = Path("results")

SOURCE_ROOT.mkdir(parents=True, exist_ok=True)
REGISTRY_ROOT.mkdir(parents=True, exist_ok=True)
RESULT_ROOT.mkdir(parents=True, exist_ok=True)

USER_AGENT = "mod-provenance-research/0.1"

HEADERS = {
    "User-Agent": USER_AGENT
}


# =========================================================
# Helpers
# =========================================================

def sha256_file(path: Path):
    h = hashlib.sha256()

    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)

            if not chunk:
                break

            h.update(chunk)

    return h.hexdigest()


def classify_file(relative_path):
    lower = relative_path.lower()

    filename = PurePosixPath(
        relative_path
    ).name.lower()

    # -------------------------
    # CODE
    # -------------------------

    if lower.endswith(".java"):
        return "CODE", "java"

    if lower.endswith(".kt"):
        return "CODE", "kotlin"

    if lower.endswith(".lua"):
        return "CODE", "lua"

    # -------------------------
    # STRUCTURED
    # -------------------------

    if lower.endswith(".json"):
        return "STRUCTURED", "json"

    if (
        lower.endswith(".yaml")
        or lower.endswith(".yml")
    ):
        return "STRUCTURED", "yaml"

    if lower.endswith(".xml"):
        return "STRUCTURED", "xml"

    # -------------------------
    # IMAGE
    # -------------------------

    if lower.endswith(".png"):
        return "IMAGE", "png"

    if (
        lower.endswith(".jpg")
        or lower.endswith(".jpeg")
    ):
        return "IMAGE", "jpg"

    return None, None


def production_path(repo_relative_path):
    p = repo_relative_path.replace(
        "\\",
        "/"
    )

    lower = p.lower()

    # 실제 production source tree만
    pattern = (
        r"(^|/)"
        r"src/main/"
        r"(java|kotlin|resources)/"
    )

    if not re.search(pattern, lower):
        return False

    # 안전 차원에서 제외
    bad = [
        "/test/",
        "/tests/",
        "/example/",
        "/examples/",
        "/fixture/",
        "/fixtures/",
        "/sample/",
        "/samples/",
        "/template/",
        "/templates/",
        "/build/",
        "/target/",
    ]

    wrapped = "/" + lower

    if any(x in wrapped for x in bad):
        return False

    return True


def download_zip(repo, sha, destination):
    url = (
        f"https://github.com/"
        f"{repo}/archive/{sha}.zip"
    )

    last_error = None

    for attempt in range(3):
        try:
            print(
                f"download attempt "
                f"{attempt + 1}/3"
            )

            with requests.get(
                url,
                headers=HEADERS,
                stream=True,
                timeout=120,
                allow_redirects=True,
            ) as r:

                r.raise_for_status()

                with open(
                    destination,
                    "wb"
                ) as f:

                    for chunk in r.iter_content(
                        chunk_size=1024 * 1024
                    ):
                        if chunk:
                            f.write(chunk)

            return True

        except Exception as e:
            last_error = e

            print(
                f"[WARNING] "
                f"download error: {e}"
            )

            time.sleep(
                2 * (attempt + 1)
            )

    print(
        f"[ERROR] download failed: "
        f"{last_error}"
    )

    return False


def safe_output_path(
    root: Path,
    relative_path: str
):
    parts = PurePosixPath(
        relative_path
    ).parts

    safe_parts = [
        p
        for p in parts
        if p not in ("", ".", "..")
    ]

    return root.joinpath(*safe_parts)


def extract_production_files(
    zip_path,
    target_root
):
    extracted = []

    with zipfile.ZipFile(
        zip_path,
        "r"
    ) as z:

        for info in z.infolist():

            if info.is_dir():
                continue

            archive_path = (
                info.filename
                .replace("\\", "/")
            )

            parts = PurePosixPath(
                archive_path
            ).parts

            # GitHub archive의
            # 최상위 repo-sha 폴더 제거
            if len(parts) < 2:
                continue

            repo_relative = "/".join(
                parts[1:]
            )

            if not production_path(
                repo_relative
            ):
                continue

            modality, subtype = (
                classify_file(
                    repo_relative
                )
            )

            # 현재 연구에서 사용하는
            # 3개 modality만 저장
            if modality is None:
                continue

            output_path = safe_output_path(
                target_root,
                repo_relative,
            )

            output_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            with z.open(
                info,
                "r"
            ) as src:

                with open(
                    output_path,
                    "wb"
                ) as dst:

                    shutil.copyfileobj(
                        src,
                        dst,
                    )

            extracted.append(
                (
                    repo_relative,
                    output_path,
                    modality,
                    subtype,
                )
            )

    return extracted


# =========================================================
# Load corpus
# =========================================================

df = pd.read_csv(INPUT)

print("======================================")
print("Phase 2B - Build Source Registry")
print("======================================")
print()

print(
    f"Frozen projects: {len(df)}"
)


# =========================================================
# Prepare registries
# =========================================================

mod_rows = []
component_rows = []

download_failed = []

temp_root = Path("temp_phase2b")
temp_root.mkdir(exist_ok=True)


# =========================================================
# Download / Extract
# =========================================================

for index, row in df.iterrows():

    mod_id = f"MOD{index + 1:04d}"

    repo = row["github_repo"]
    sha = row["frozen_commit_sha"]
    role = row["role"]

    print()
    print("======================================")
    print(
        f"[{index + 1}/{len(df)}] "
        f"{mod_id}"
    )
    print(f"title  : {row['title']}")
    print(f"repo   : {repo}")
    print(f"role   : {role}")
    print(f"commit : {sha}")
    print("======================================")

    mod_root = (
        SOURCE_ROOT
        / mod_id
    )

    # 이전 실패/재실행 시
    # 해당 MOD 폴더만 재생성
    if mod_root.exists():
        shutil.rmtree(mod_root)

    mod_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    zip_path = (
        temp_root
        / f"{mod_id}.zip"
    )

    ok = download_zip(
        repo,
        sha,
        zip_path,
    )

    if not ok:
        download_failed.append(
            {
                "mod_id": mod_id,
                "repo": repo,
            }
        )

        continue

    try:
        extracted = (
            extract_production_files(
                zip_path,
                mod_root,
            )
        )

    except Exception as e:

        print(
            f"[ERROR] extraction: {e}"
        )

        download_failed.append(
            {
                "mod_id": mod_id,
                "repo": repo,
            }
        )

        continue

    finally:

        if zip_path.exists():
            zip_path.unlink()

    print(
        f"extracted components: "
        f"{len(extracted)}"
    )

    counts = defaultdict(int)

    for (
        relative_path,
        local_path,
        modality,
        subtype,
    ) in extracted:

        digest = sha256_file(
            local_path
        )

        size = local_path.stat().st_size

        counts[modality] += 1
        counts[subtype] += 1

        lower = relative_path.lower()

        is_fabric_manifest = (
            lower.endswith(
                "fabric.mod.json"
            )
        )

        is_mixin_config = (
            "mixin" in lower
            and lower.endswith(".json")
        )

        component_id = (
            f"{mod_id}:"
            f"{relative_path}"
        )

        component_rows.append({
            "component_id":
                component_id,

            "mod_id":
                mod_id,

            "title":
                row["title"],

            "repo":
                repo,

            "role":
                role,

            "commit_sha":
                sha,

            "relative_path":
                relative_path,

            "modality":
                modality,

            "subtype":
                subtype,

            "size_bytes":
                size,

            "sha256":
                digest,

            "is_fabric_manifest":
                is_fabric_manifest,

            "is_mixin_config":
                is_mixin_config,
        })

    mod_rows.append({

        "mod_id":
            mod_id,

        "modrinth_id":
            row["modrinth_id"],

        "title":
            row["title"],

        "repo":
            repo,

        "role":
            role,

        "license":
            row["license"],

        "commit_sha":
            sha,

        "code_components":
            counts["CODE"],

        "structured_components":
            counts["STRUCTURED"],

        "image_components":
            counts["IMAGE"],

        "java_components":
            counts["java"],

        "kotlin_components":
            counts["kotlin"],

        "json_components":
            counts["json"],

        "yaml_components":
            counts["yaml"],

        "xml_components":
            counts["xml"],

        "png_components":
            counts["png"],

        "jpg_components":
            counts["jpg"],

        "total_components":
            len(extracted),
    })


# =========================================================
# Save registry
# =========================================================

mods = pd.DataFrame(mod_rows)

components = pd.DataFrame(
    component_rows
)

mod_registry_path = (
    REGISTRY_ROOT
    / "mod_registry.csv"
)

component_registry_csv = (
    REGISTRY_ROOT
    / "component_registry.csv"
)

component_registry_jsonl = (
    REGISTRY_ROOT
    / "component_registry.jsonl"
)

mods.to_csv(
    mod_registry_path,
    index=False,
    encoding="utf-8-sig",
)

components.to_csv(
    component_registry_csv,
    index=False,
    encoding="utf-8-sig",
)

with open(
    component_registry_jsonl,
    "w",
    encoding="utf-8",
) as f:

    for row in component_rows:

        f.write(
            json.dumps(
                row,
                ensure_ascii=False,
            )
            + "\n"
        )


# =========================================================
# Exact duplicate analysis
# =========================================================

duplicate_rows = []

cross_mod_duplicate_groups = 0
cross_mod_duplicate_components = 0

if len(components):

    for digest, group in (
        components.groupby("sha256")
    ):

        mods_in_group = sorted(
            group["mod_id"]
            .unique()
            .tolist()
        )

        # 동일 MOD 내부 중복 말고
        # 서로 다른 source MOD 간 동일 파일
        if len(mods_in_group) < 2:
            continue

        cross_mod_duplicate_groups += 1
        cross_mod_duplicate_components += (
            len(group)
        )

        duplicate_rows.append({

            "sha256":
                digest,

            "component_count":
                len(group),

            "mod_count":
                len(mods_in_group),

            "mods":
                "|".join(
                    mods_in_group
                ),

            "modalities":
                "|".join(
                    sorted(
                        group[
                            "modality"
                        ]
                        .unique()
                        .tolist()
                    )
                ),

            "paths":
                " | ".join(
                    group[
                        "relative_path"
                    ]
                    .tolist()
                )[:5000],
        })


duplicates = pd.DataFrame(
    duplicate_rows
)

duplicate_path = (
    RESULT_ROOT
    / "cross_mod_exact_duplicates.csv"
)

duplicates.to_csv(
    duplicate_path,
    index=False,
    encoding="utf-8-sig",
)


# =========================================================
# Summary
# =========================================================

summary = {

    "frozen_projects":
        len(df),

    "download_success":
        len(mods),

    "download_failed":
        len(download_failed),

    "total_components":
        len(components),

    "unique_sha256":
        int(
            components[
                "sha256"
            ].nunique()
        )
        if len(components)
        else 0,

    "code_components":
        int(
            (
                components[
                    "modality"
                ]
                == "CODE"
            ).sum()
        )
        if len(components)
        else 0,

    "structured_components":
        int(
            (
                components[
                    "modality"
                ]
                == "STRUCTURED"
            ).sum()
        )
        if len(components)
        else 0,

    "image_components":
        int(
            (
                components[
                    "modality"
                ]
                == "IMAGE"
            ).sum()
        )
        if len(components)
        else 0,

    "target_components":
        int(
            (
                components[
                    "role"
                ]
                == "TARGET_MOD"
            ).sum()
        )
        if len(components)
        else 0,

    "background_components":
        int(
            (
                components[
                    "role"
                ]
                == "BACKGROUND_LIBRARY"
            ).sum()
        )
        if len(components)
        else 0,

    "cross_mod_exact_duplicate_groups":
        cross_mod_duplicate_groups,

    "cross_mod_exact_duplicate_components":
        cross_mod_duplicate_components,
}

if len(components):

    summary[
        "cross_mod_duplicate_component_rate"
    ] = round(
        (
            cross_mod_duplicate_components
            / len(components)
        ),
        6,
    )

else:

    summary[
        "cross_mod_duplicate_component_rate"
    ] = 0.0


summary_path = (
    RESULT_ROOT
    / "phase2b_summary.json"
)

with open(
    summary_path,
    "w",
    encoding="utf-8",
) as f:

    json.dump(
        summary,
        f,
        ensure_ascii=False,
        indent=2,
    )


# 실패 목록
with open(
    RESULT_ROOT
    / "phase2b_failed.json",
    "w",
    encoding="utf-8",
) as f:

    json.dump(
        download_failed,
        f,
        ensure_ascii=False,
        indent=2,
    )


# temp 정리
shutil.rmtree(
    temp_root,
    ignore_errors=True,
)


print()
print("======================================")
print("RESULT")
print("======================================")
print(
    json.dumps(
        summary,
        ensure_ascii=False,
        indent=2,
    )
)

print()
print(
    f"MOD registry : "
    f"{mod_registry_path}"
)

print(
    f"Component registry : "
    f"{component_registry_csv}"
)

print(
    f"Exact duplicates : "
    f"{duplicate_path}"
)