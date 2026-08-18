import hashlib
import json
import shutil
import zipfile
from pathlib import Path, PurePosixPath

import pandas as pd
import requests


INPUT = Path("results/dataset_corpus_v3.csv")

DATA_ROOT = Path("data")
PACKAGE_ROOT = DATA_ROOT / "release_packages"
REGISTRY_ROOT = DATA_ROOT / "registry"
RESULT_ROOT = Path("results")

PACKAGE_ROOT.mkdir(
    parents=True,
    exist_ok=True
)

REGISTRY_ROOT.mkdir(
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


def sha256_bytes(data):
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def sha256_file(path):
    h = hashlib.sha256()

    with open(path, "rb") as f:
        while True:
            chunk = f.read(
                1024 * 1024
            )

            if not chunk:
                break

            h.update(chunk)

    return h.hexdigest()


def api_get(path, params=None):
    r = requests.get(
        MODRINTH_API + path,
        headers=HEADERS,
        params=params,
        timeout=60,
    )

    r.raise_for_status()
    return r.json()


def classify_entry(path):
    lower = path.lower()

    # -------------------------
    # Executable code
    # -------------------------
    if lower.endswith(".class"):
        return "CODE_BINARY", "class"

    # -------------------------
    # Structured resources
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
    # Images
    # -------------------------
    if lower.endswith(".png"):
        return "IMAGE", "png"

    if (
        lower.endswith(".jpg")
        or lower.endswith(".jpeg")
    ):
        return "IMAGE", "jpg"

    # -------------------------
    # Other resources
    # -------------------------
    if lower.endswith(".mcmeta"):
        return "STRUCTURED", "mcmeta"

    return None, None


def should_ignore(path):
    lower = path.lower()

    # Signature / generic packaging metadata
    if lower.startswith("meta-inf/"):
        return True

    # Mac/OS noise
    if "__macosx/" in lower:
        return True

    if lower.endswith(".ds_store"):
        return True

    return False


def get_latest_fabric_version(project_id):
    versions = api_get(
        f"/project/{project_id}/version"
    )

    valid = []

    for version in versions:

        loaders = (
            version.get("loaders")
            or []
        )

        if "fabric" not in loaders:
            continue

        files = (
            version.get("files")
            or []
        )

        primary = None

        for f in files:
            if f.get("primary"):
                primary = f
                break

        if primary is None and files:
            primary = files[0]

        if primary is None:
            continue

        filename = (
            primary.get("filename", "")
            .lower()
        )

        if not filename.endswith(".jar"):
            continue

        valid.append(
            (
                version,
                primary
            )
        )

    if not valid:
        return None, None

    # Modrinth API 기본 반환은
    # 일반적으로 최신 버전 우선이므로
    # 첫 유효 Fabric release 사용
    return valid[0]


def download_file(url, path):
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


df = pd.read_csv(INPUT)

package_rows = []
component_rows = []
failed = []

print(
    "======================================"
)
print(
    "Phase 2C - Actual Release Registry"
)
print(
    "======================================"
)


for index, row in df.iterrows():

    mod_id = f"MOD{index + 1:04d}"

    project_id = row["modrinth_id"]

    print()
    print(
        f"[{index + 1}/{len(df)}] "
        f"{mod_id} - {row['title']}"
    )

    try:
        version, file_info = (
            get_latest_fabric_version(
                project_id
            )
        )

    except Exception as e:
        print(
            f"[FAILED] version API: {e}"
        )

        failed.append({
            "mod_id": mod_id,
            "reason":
                f"version_api:{e}",
        })

        continue

    if version is None:
        print(
            "[FAILED] Fabric JAR 없음"
        )

        failed.append({
            "mod_id": mod_id,
            "reason":
                "no_fabric_jar",
        })

        continue

    version_id = version["id"]
    version_number = (
        version.get("version_number")
    )

    filename = file_info["filename"]
    url = file_info["url"]

    expected_hashes = (
        file_info.get("hashes")
        or {}
    )

    expected_sha512 = (
        expected_hashes.get("sha512")
    )

    expected_sha1 = (
        expected_hashes.get("sha1")
    )

    print(
        f"version : {version_number}"
    )
    print(
        f"file    : {filename}"
    )

    mod_dir = (
        PACKAGE_ROOT / mod_id
    )

    if mod_dir.exists():
        shutil.rmtree(mod_dir)

    mod_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    jar_path = (
        mod_dir / filename
    )

    try:
        download_file(
            url,
            jar_path
        )

    except Exception as e:

        print(
            f"[FAILED] download: {e}"
        )

        failed.append({
            "mod_id": mod_id,
            "reason":
                f"download:{e}",
        })

        continue

    package_sha256 = (
        sha256_file(jar_path)
    )

    counts = {
        "CODE_BINARY": 0,
        "STRUCTURED": 0,
        "IMAGE": 0,
    }

    subtype_counts = {}

    component_count = 0

    try:

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

                modality, subtype = (
                    classify_entry(path)
                )

                if modality is None:
                    continue

                try:
                    data = jar.read(info)

                except Exception:
                    continue

                digest = (
                    sha256_bytes(data)
                )

                counts[modality] += 1

                subtype_counts[subtype] = (
                    subtype_counts.get(
                        subtype,
                        0
                    )
                    + 1
                )

                component_count += 1

                component_rows.append({

                    "component_id":
                        f"{mod_id}:{path}",

                    "mod_id":
                        mod_id,

                    "title":
                        row["title"],

                    "role":
                        row["role"],

                    "modrinth_id":
                        project_id,

                    "version_id":
                        version_id,

                    "version_number":
                        version_number,

                    "package_filename":
                        filename,

                    "relative_path":
                        path,

                    "modality":
                        modality,

                    "subtype":
                        subtype,

                    "size_bytes":
                        len(data),

                    "sha256":
                        digest,

                    "is_fabric_manifest":
                        (
                            path.lower()
                            .endswith(
                                "fabric.mod.json"
                            )
                        ),

                    "is_mixin_config":
                        (
                            "mixin"
                            in path.lower()
                            and
                            path.lower()
                            .endswith(
                                ".json"
                            )
                        ),
                })

    except zipfile.BadZipFile:

        print(
            "[FAILED] invalid JAR/ZIP"
        )

        failed.append({
            "mod_id": mod_id,
            "reason":
                "bad_zip",
        })

        continue

    package_rows.append({

        "mod_id":
            mod_id,

        "title":
            row["title"],

        "role":
            row["role"],

        "modrinth_id":
            project_id,

        "version_id":
            version_id,

        "version_number":
            version_number,

        "filename":
            filename,

        "package_sha256":
            package_sha256,

        "modrinth_sha512":
            expected_sha512,

        "modrinth_sha1":
            expected_sha1,

        "code_binary_components":
            counts["CODE_BINARY"],

        "structured_components":
            counts["STRUCTURED"],

        "image_components":
            counts["IMAGE"],

        "total_components":
            component_count,
    })

    print(
        "components: "
        f"class={counts['CODE_BINARY']} "
        f"structured={counts['STRUCTURED']} "
        f"image={counts['IMAGE']}"
    )


packages = pd.DataFrame(
    package_rows
)

components = pd.DataFrame(
    component_rows
)


package_registry_path = (
    REGISTRY_ROOT
    / "release_package_registry.csv"
)

component_registry_path = (
    REGISTRY_ROOT
    / "release_component_registry.csv"
)

packages.to_csv(
    package_registry_path,
    index=False,
    encoding="utf-8-sig",
)

components.to_csv(
    component_registry_path,
    index=False,
    encoding="utf-8-sig",
)


# ---------------------------------------
# Cross-package exact duplicate analysis
# ---------------------------------------

duplicate_rows = []

duplicate_groups = 0
duplicate_components = 0


if len(components):

    for digest, group in (
        components.groupby("sha256")
    ):

        mods = sorted(
            group["mod_id"]
            .unique()
            .tolist()
        )

        if len(mods) < 2:
            continue

        duplicate_groups += 1
        duplicate_components += (
            len(group)
        )

        duplicate_rows.append({

            "sha256":
                digest,

            "component_count":
                len(group),

            "mod_count":
                len(mods),

            "mods":
                "|".join(mods),

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


duplicate_df = pd.DataFrame(
    duplicate_rows
)

duplicate_path = (
    RESULT_ROOT
    / "release_cross_mod_duplicates.csv"
)

duplicate_df.to_csv(
    duplicate_path,
    index=False,
    encoding="utf-8-sig",
)


summary = {

    "requested_projects":
        len(df),

    "release_download_success":
        len(packages),

    "release_download_failed":
        len(failed),

    "total_release_components":
        len(components),

    "code_binary_components":
        int(
            (
                components["modality"]
                == "CODE_BINARY"
            ).sum()
        )
        if len(components)
        else 0,

    "structured_components":
        int(
            (
                components["modality"]
                == "STRUCTURED"
            ).sum()
        )
        if len(components)
        else 0,

    "image_components":
        int(
            (
                components["modality"]
                == "IMAGE"
            ).sum()
        )
        if len(components)
        else 0,

    "unique_component_sha256":
        int(
            components[
                "sha256"
            ].nunique()
        )
        if len(components)
        else 0,

    "cross_mod_duplicate_groups":
        duplicate_groups,

    "cross_mod_duplicate_components":
        duplicate_components,
}


if len(components):

    summary[
        "cross_mod_duplicate_rate"
    ] = (
        duplicate_components
        / len(components)
    )

else:

    summary[
        "cross_mod_duplicate_rate"
    ] = 0


with open(
    RESULT_ROOT
    / "phase2c_summary.json",
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
    / "phase2c_failed.json",
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
    f"Package registry: "
    f"{package_registry_path}"
)

print(
    f"Component registry: "
    f"{component_registry_path}"
)

print(
    f"Duplicates: "
    f"{duplicate_path}"
)