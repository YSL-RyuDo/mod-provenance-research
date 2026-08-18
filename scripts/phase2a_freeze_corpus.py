import json
import subprocess
import time
from pathlib import Path

import pandas as pd
import requests


INPUT = Path("results/dataset_summary_v2.csv")
OUTPUT = Path("results/dataset_corpus_v3.csv")
SUMMARY = Path("results/phase2a_summary.json")

MODRINTH_API = "https://api.modrinth.com/v2"

HEADERS = {
    "User-Agent": "mod-provenance-research/0.1"
}


def get_project(project_id):
    r = requests.get(
        f"{MODRINTH_API}/project/{project_id}",
        headers=HEADERS,
        timeout=30,
    )

    r.raise_for_status()
    return r.json()


def get_git_head(source_url):
    if not source_url:
        return None

    url = source_url.rstrip("/")

    if not url.endswith(".git"):
        url += ".git"

    try:
        result = subprocess.run(
            [
                "git",
                "ls-remote",
                url,
                "HEAD",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return None

        line = result.stdout.strip()

        if not line:
            return None

        return line.split()[0]

    except Exception:
        return None


df = pd.read_csv(INPUT)

rows = []

print("======================================")
print("Phase 2A - Corpus Freeze")
print("======================================")

for index, row in df.iterrows():

    project_id = row["modrinth_id"]

    print()
    print(
        f"[{index + 1}/{len(df)}] "
        f"{row['title']}"
    )

    try:
        project = get_project(project_id)
    except Exception as e:
        print(f"[ERROR] Modrinth metadata: {e}")
        continue

    categories = project.get("categories") or []
    additional = (
        project.get("additional_categories")
        or []
    )

    all_categories = sorted(
        set(categories + additional)
    )

    is_library = (
        "library" in all_categories
    )

    if is_library:
        role = "BACKGROUND_LIBRARY"
    else:
        role = "TARGET_MOD"

    source_url = project.get("source_url")

    print(f"role       = {role}")
    print(
        "categories = "
        + ", ".join(all_categories)
    )

    commit_sha = get_git_head(source_url)

    if commit_sha:
        print(
            f"commit     = "
            f"{commit_sha[:12]}"
        )
    else:
        print(
            "[WARNING] commit SHA "
            "조회 실패"
        )

    new_row = row.to_dict()

    new_row.update({
        "role": role,

        "modrinth_categories":
            json.dumps(
                all_categories,
                ensure_ascii=False,
            ),

        "client_side":
            project.get("client_side"),

        "server_side":
            project.get("server_side"),

        "project_status":
            project.get("status"),

        "description":
            project.get("description"),

        "frozen_commit_sha":
            commit_sha,
    })

    rows.append(new_row)

    time.sleep(0.2)


out = pd.DataFrame(rows)

out.to_csv(
    OUTPUT,
    index=False,
    encoding="utf-8-sig",
)

summary = {
    "total": len(out),

    "target_mods": int(
        (out["role"] == "TARGET_MOD").sum()
    ),

    "background_libraries": int(
        (
            out["role"]
            == "BACKGROUND_LIBRARY"
        ).sum()
    ),

    "commit_sha_success": int(
        out[
            "frozen_commit_sha"
        ].notna().sum()
    ),

    "commit_sha_failed": int(
        out[
            "frozen_commit_sha"
        ].isna().sum()
    ),
}


# Target MOD 쪽 통계
target = out[
    out["role"] == "TARGET_MOD"
]

if len(target):

    summary.update({

        "target_code_total":
            int(
                target[
                    "code_total"
                ].sum()
            ),

        "target_structured_total":
            int(
                target[
                    "structured_total"
                ].sum()
            ),

        "target_image_total":
            int(
                target[
                    "image_total"
                ].sum()
            ),

        "target_median_code":
            float(
                target[
                    "code_total"
                ].median()
            ),

        "target_median_structured":
            float(
                target[
                    "structured_total"
                ].median()
            ),

        "target_median_image":
            float(
                target[
                    "image_total"
                ].median()
            ),
    })


with open(
    SUMMARY,
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
print(f"CSV : {OUTPUT}")
print(f"JSON: {SUMMARY}")