import os
import time
import json
from pathlib import Path
from collections import defaultdict

import requests
import pandas as pd


# =========================================================
# Config
# =========================================================

TARGET_COUNT = 10

ALLOWED_LICENSES = {
    "MIT",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "CC0-1.0",
    "MPL-2.0",
}

SEARCH_QUERIES = [
    "minecraft fabric mod language:Java fork:false archived:false stars:>5",
    "minecraft fabric mod language:Kotlin fork:false archived:false stars:>1",
]

RESULT_DIR = Path("results")
RESULT_DIR.mkdir(exist_ok=True)

TOKEN = os.environ.get("GITHUB_TOKEN")

HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"


# =========================================================
# Helpers
# =========================================================

def github_get(url, params=None):
    r = requests.get(
        url,
        headers=HEADERS,
        params=params,
        timeout=30,
    )

    remain = r.headers.get("X-RateLimit-Remaining")
    if remain is not None:
        print(f"[GitHub API] remaining = {remain}")

    if r.status_code == 403:
        print("GitHub API rate limit 또는 권한 문제 발생")
        print(r.text[:500])
        raise SystemExit(1)

    r.raise_for_status()
    return r.json()


def classify_tree(tree):
    counts = defaultdict(int)

    has_fabric_manifest = False

    for entry in tree:
        if entry.get("type") != "blob":
            continue

        path = entry["path"]
        lower = path.lower()

        # 빌드/생성 산출물 제외
        if (
            "/build/" in lower
            or lower.startswith("build/")
            or "/.gradle/" in lower
            or lower.startswith(".gradle/")
            or "/target/" in lower
            or lower.startswith("target/")
        ):
            continue

        if lower.endswith(".java"):
            counts["java"] += 1

        elif lower.endswith(".kt"):
            counts["kotlin"] += 1

        elif lower.endswith(".lua"):
            counts["lua"] += 1

        elif lower.endswith(".json"):
            counts["json"] += 1

        elif lower.endswith(".yaml") or lower.endswith(".yml"):
            counts["yaml"] += 1

        elif lower.endswith(".xml"):
            counts["xml"] += 1

        elif lower.endswith(".png"):
            counts["png"] += 1

        elif lower.endswith(".jpg") or lower.endswith(".jpeg"):
            counts["jpg"] += 1

        if lower.endswith("fabric.mod.json"):
            has_fabric_manifest = True

        if "mixin" in lower and lower.endswith(".json"):
            counts["mixin_json"] += 1

    counts["code"] = (
        counts["java"]
        + counts["kotlin"]
        + counts["lua"]
    )

    counts["structured"] = (
        counts["json"]
        + counts["yaml"]
        + counts["xml"]
    )

    counts["image"] = (
        counts["png"]
        + counts["jpg"]
    )

    return counts, has_fabric_manifest


# =========================================================
# Search
# =========================================================

print("======================================")
print("Phase 1 - Open Source MOD Inspection")
print("======================================")

candidates = {}

for query in SEARCH_QUERIES:
    print()
    print(f"[SEARCH] {query}")

    data = github_get(
        "https://api.github.com/search/repositories",
        params={
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": 30,
        },
    )

    for repo in data.get("items", []):
        candidates[repo["full_name"]] = repo

    time.sleep(1)


print()
print(f"검색 후보: {len(candidates)}개")
print()


# =========================================================
# Inspect repositories
# =========================================================

rows = []

for full_name, repo in candidates.items():

    if len(rows) >= TARGET_COUNT:
        break

    license_info = repo.get("license") or {}
    spdx = license_info.get("spdx_id")

    if spdx not in ALLOWED_LICENSES:
        continue

    default_branch = repo.get("default_branch")

    if not default_branch:
        continue

    print("--------------------------------------")
    print(f"검사: {full_name}")
    print(f"license: {spdx}")
    print(f"branch : {default_branch}")

    tree_url = (
        f"https://api.github.com/repos/"
        f"{full_name}/git/trees/{default_branch}"
    )

    try:
        tree_data = github_get(
            tree_url,
            params={"recursive": "1"},
        )
    except Exception as e:
        print(f"[SKIP] tree 조회 실패: {e}")
        continue

    tree = tree_data.get("tree", [])

    counts, has_fabric_manifest = classify_tree(tree)

    # 실제 Fabric MOD 형태가 아니면 제외
    if not has_fabric_manifest:
        print("[SKIP] fabric.mod.json 없음")
        continue

    if counts["code"] == 0:
        print("[SKIP] source code 없음")
        continue

    row = {
        "repo": full_name,
        "url": repo["html_url"],
        "license": spdx,
        "stars": repo.get("stargazers_count", 0),
        "default_branch": default_branch,

        "java": counts["java"],
        "kotlin": counts["kotlin"],
        "lua": counts["lua"],

        "json": counts["json"],
        "yaml": counts["yaml"],
        "xml": counts["xml"],

        "png": counts["png"],
        "jpg": counts["jpg"],

        "mixin_json": counts["mixin_json"],

        "code_total": counts["code"],
        "structured_total": counts["structured"],
        "image_total": counts["image"],

        "tree_truncated": tree_data.get("truncated", False),
    }

    rows.append(row)

    print(
        f"[ACCEPT] "
        f"code={counts['code']} "
        f"structured={counts['structured']} "
        f"image={counts['image']}"
    )

    time.sleep(0.5)


# =========================================================
# Save
# =========================================================

df = pd.DataFrame(rows)

csv_path = RESULT_DIR / "dataset_summary.csv"
df.to_csv(
    csv_path,
    index=False,
    encoding="utf-8-sig",
)

summary = {
    "accepted_repositories": len(df),
    "target": TARGET_COUNT,
}

if len(df) > 0:
    summary.update({
        "total_code_files": int(df["code_total"].sum()),
        "total_structured_files": int(df["structured_total"].sum()),
        "total_image_files": int(df["image_total"].sum()),

        "repos_with_images": int(
            (df["image_total"] > 0).sum()
        ),

        "repos_with_structured_data": int(
            (df["structured_total"] > 0).sum()
        ),

        "repos_with_java": int(
            (df["java"] > 0).sum()
        ),

        "repos_with_kotlin": int(
            (df["kotlin"] > 0).sum()
        ),
    })

json_path = RESULT_DIR / "phase1_summary.json"

with open(
    json_path,
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

print(json.dumps(
    summary,
    ensure_ascii=False,
    indent=2,
))

print()
print(f"CSV  : {csv_path}")
print(f"JSON : {json_path}")

if len(df) < TARGET_COUNT:
    print()
    print(
        f"[WARNING] 목표 {TARGET_COUNT}개 중 "
        f"{len(df)}개만 확보됨"
    )