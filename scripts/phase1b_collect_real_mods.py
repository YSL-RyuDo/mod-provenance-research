import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests


TARGET_COUNT = 30

ALLOWED_LICENSES = {
    "MIT",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "CC0-1.0",
    "MPL-2.0",
}

MODRINTH_API = "https://api.modrinth.com/v2"

HEADERS = {
    "User-Agent": "mod-provenance-research/0.1",
}

RESULTS = Path("results")
RESULTS.mkdir(exist_ok=True)


def modrinth_get(path, params=None):
    r = requests.get(
        MODRINTH_API + path,
        headers=HEADERS,
        params=params,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def parse_github_url(url):
    if not url:
        return None

    try:
        p = urlparse(url)

        if p.netloc.lower() != "github.com":
            return None

        parts = [
            x for x in p.path.strip("/").split("/")
            if x
        ]

        if len(parts) < 2:
            return None

        owner = parts[0]
        repo = parts[1]

        if repo.endswith(".git"):
            repo = repo[:-4]

        return owner, repo

    except Exception:
        return None


def clone_tree_only(owner, repo, dst):
    url = f"https://github.com/{owner}/{repo}.git"

    cmd = [
        "git",
        "clone",
        "--depth", "1",
        "--filter=blob:none",
        "--no-checkout",
        url,
        str(dst),
    ]

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:
        return False, result.stderr[-500:]

    return True, ""


def get_paths(repo_dir):
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_dir),
            "ls-tree",
            "-r",
            "--name-only",
            "HEAD",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=60,
    )

    if result.returncode != 0:
        return []

    return [
        x.strip()
        for x in result.stdout.splitlines()
        if x.strip()
    ]


def is_production_path(path):
    p = path.lower()

    bad_parts = [
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

    wrapped = "/" + p

    if any(x in wrapped for x in bad_parts):
        return False

    # 실제 Gradle/Maven production source tree 위주
    if re.search(
        r"(^|/)src/main/(java|kotlin|resources)/",
        p
    ):
        return True

    return False


def inspect_paths(paths):
    prod = [
        p for p in paths
        if is_production_path(p)
    ]

    lower_prod = [
        p.lower()
        for p in prod
    ]

    manifests = [
        p for p in prod
        if p.lower().endswith(
            "src/main/resources/fabric.mod.json"
        )
    ]

    java = sum(
        p.endswith(".java")
        for p in lower_prod
    )

    kotlin = sum(
        p.endswith(".kt")
        for p in lower_prod
    )

    json_count = sum(
        p.endswith(".json")
        for p in lower_prod
    )

    yaml = sum(
        p.endswith(".yaml")
        or p.endswith(".yml")
        for p in lower_prod
    )

    xml = sum(
        p.endswith(".xml")
        for p in lower_prod
    )

    png = sum(
        p.endswith(".png")
        for p in lower_prod
    )

    jpg = sum(
        p.endswith(".jpg")
        or p.endswith(".jpeg")
        for p in lower_prod
    )

    code = java + kotlin
    structured = json_count + yaml + xml
    image = png + jpg

    return {
        "manifest_count": len(manifests),
        "java": java,
        "kotlin": kotlin,
        "json": json_count,
        "yaml": yaml,
        "xml": xml,
        "png": png,
        "jpg": jpg,
        "code_total": code,
        "structured_total": structured,
        "image_total": image,
    }


print("======================================")
print("Phase 1B - Real Modrinth MOD Corpus")
print("======================================")

facets = json.dumps([
    ["project_type:mod"],
    ["categories:fabric"],
    ["open_source:true"],
])

search = modrinth_get(
    "/search",
    params={
        "facets": facets,
        "index": "downloads",
        "limit": 100,
    },
)

hits = search.get("hits", [])

print(f"Modrinth 후보: {len(hits)}")

rows = []

tmp_root = Path(
    tempfile.mkdtemp(
        prefix="modprov_"
    )
)

try:
    for hit in hits:

        if len(rows) >= TARGET_COUNT:
            break

        project_id = hit.get("project_id")

        if not project_id:
            continue

        try:
            project = modrinth_get(
                f"/project/{project_id}"
            )
        except Exception as e:
            print(
                f"[SKIP] project 조회 실패: {e}"
            )
            continue

        if project.get("project_type") != "mod":
            continue

        license_obj = (
            project.get("license") or {}
        )

        spdx = license_obj.get("id")

        if spdx not in ALLOWED_LICENSES:
            continue

        source_url = project.get("source_url")

        github = parse_github_url(source_url)

        if not github:
            continue

        owner, repo = github

        full_name = f"{owner}/{repo}"

        print()
        print("--------------------------------------")
        print(
            f"[CHECK] "
            f"{project.get('title')} "
            f"→ {full_name}"
        )
        print(f"license={spdx}")

        local_dir = (
            tmp_root
            / f"{owner}_{repo}"
        )

        ok, error = clone_tree_only(
            owner,
            repo,
            local_dir,
        )

        if not ok:
            print(
                f"[SKIP] clone 실패: "
                f"{error}"
            )
            continue

        paths = get_paths(local_dir)

        stats = inspect_paths(paths)

        # production source tree에
        # 실제 fabric.mod.json이 있어야 함
        if stats["manifest_count"] == 0:
            print(
                "[SKIP] production "
                "fabric.mod.json 없음"
            )
            shutil.rmtree(
                local_dir,
                ignore_errors=True,
            )
            continue

        if stats["code_total"] == 0:
            print(
                "[SKIP] production "
                "code 없음"
            )
            shutil.rmtree(
                local_dir,
                ignore_errors=True,
            )
            continue

        row = {
            "modrinth_id": project_id,
            "title": project.get("title"),
            "slug": project.get("slug"),
            "github_repo": full_name,
            "source_url": source_url,
            "license": spdx,
            "downloads": project.get(
                "downloads", 0
            ),
            **stats,
        }

        rows.append(row)

        print(
            "[ACCEPT] "
            f"code={stats['code_total']} "
            f"structured="
            f"{stats['structured_total']} "
            f"image={stats['image_total']}"
        )

        shutil.rmtree(
            local_dir,
            ignore_errors=True,
        )

finally:
    shutil.rmtree(
        tmp_root,
        ignore_errors=True,
    )


df = pd.DataFrame(rows)

csv_path = (
    RESULTS
    / "dataset_summary_v2.csv"
)

df.to_csv(
    csv_path,
    index=False,
    encoding="utf-8-sig",
)

summary = {
    "accepted_real_mods": len(df),
    "target": TARGET_COUNT,
}

if len(df):
    summary.update({
        "total_code": int(
            df["code_total"].sum()
        ),
        "total_structured": int(
            df["structured_total"].sum()
        ),
        "total_image": int(
            df["image_total"].sum()
        ),

        "median_code": float(
            df["code_total"].median()
        ),
        "median_structured": float(
            df[
                "structured_total"
            ].median()
        ),
        "median_image": float(
            df["image_total"].median()
        ),

        "mods_with_images": int(
            (
                df["image_total"] > 0
            ).sum()
        ),

        "mods_with_structured": int(
            (
                df[
                    "structured_total"
                ] > 0
            ).sum()
        ),

        "java_mods": int(
            (df["java"] > 0).sum()
        ),

        "kotlin_mods": int(
            (df["kotlin"] > 0).sum()
        ),
    })

with open(
    RESULTS / "phase1b_summary.json",
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
print(f"CSV: {csv_path}")