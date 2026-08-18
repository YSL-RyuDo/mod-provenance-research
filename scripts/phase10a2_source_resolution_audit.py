import csv
import json
import re
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"

SPLIT_CSV = RESULTS / "phase6c_project_split.csv"
QUERY_MANIFEST_CSV = RESULTS / "phase6k_query_manifest_private.csv"

OUTPUT_PROJECTS = RESULTS / "phase10a2_project_source_resolution.csv"
OUTPUT_COMPONENTS = RESULTS / "phase10a2_code_source_resolution.csv"
OUTPUT_SUMMARY = RESULTS / "phase10a2_source_resolution_summary.json"

MODRINTH_BASE = "https://api.modrinth.com/v2/project/"


def clean(value):
    if value is None:
        return ""
    return str(value).strip()


def fetch_json(url, timeout=30):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent":
                "mod-provenance-research-phase10a2/1.0"
        }
    )

    with urllib.request.urlopen(
        req,
        timeout=timeout
    ) as response:

        return json.loads(
            response.read().decode("utf-8")
        )


def normalize_github_url(url):
    url = clean(url)

    if not url:
        return ""

    url = url.rstrip("/")

    if url.endswith(".git"):
        url = url[:-4]

    parsed = urlparse(url)

    host = parsed.netloc.lower()

    if host not in {
        "github.com",
        "www.github.com"
    }:
        return ""

    parts = [
        p for p in parsed.path.split("/")
        if p
    ]

    if len(parts) < 2:
        return ""

    owner = parts[0]
    repo = parts[1]

    return f"https://github.com/{owner}/{repo}"


def outer_class_from_relative_path(path):
    path = clean(path)

    name = Path(path).name

    if name.endswith(".class"):
        name = name[:-6]

    # Inner classes map back to outer source class.
    if "$" in name:
        name = name.split("$", 1)[0]

    return name


def expected_java_filename(relative_path):
    outer = outer_class_from_relative_path(
        relative_path
    )

    if not outer:
        return ""

    return outer + ".java"


split_df = pd.read_csv(
    SPLIT_CSV,
    dtype=str,
    keep_default_na=False
)

query_df = pd.read_csv(
    QUERY_MANIFEST_CSV,
    dtype=str,
    keep_default_na=False
)

test_query_df = query_df[
    (query_df["stage"] == "TEST")
    &
    (query_df["modality"] == "CODE_BINARY")
].copy()


if len(test_query_df) != 1800:
    raise RuntimeError(
        f"Expected 1800 TEST CODE components, "
        f"got {len(test_query_df)}"
    )


fresh_to_project = {
    clean(row.fresh_id):
        clean(row.project_id)

    for row in split_df.itertuples(
        index=False
    )
}


required_fresh_ids = sorted(
    set(
        test_query_df[
            "source_fresh_id"
        ].astype(str)
    )
)


print(
    "TEST CODE components:",
    len(test_query_df)
)

print(
    "Unique source fresh IDs:",
    len(required_fresh_ids)
)


project_rows = []


for i, fresh_id in enumerate(
    required_fresh_ids,
    start=1
):

    project_id = fresh_to_project.get(
        fresh_id,
        ""
    )

    status = ""
    source_url = ""
    github_repo = ""
    error = ""
    slug = ""
    title = ""

    if not project_id:

        status = "NO_PROJECT_ID"

    else:

        try:

            data = fetch_json(
                MODRINTH_BASE
                +
                project_id
            )

            source_url = clean(
                data.get(
                    "source_url"
                )
            )

            github_repo = normalize_github_url(
                source_url
            )

            slug = clean(
                data.get(
                    "slug"
                )
            )

            title = clean(
                data.get(
                    "title"
                )
            )

            if github_repo:
                status = "GITHUB_SOURCE"
            elif source_url:
                status = "NON_GITHUB_SOURCE"
            else:
                status = "NO_SOURCE_URL"

        except Exception as exc:

            status = "API_ERROR"
            error = repr(exc)

    project_rows.append({
        "fresh_id":
            fresh_id,

        "project_id":
            project_id,

        "slug":
            slug,

        "title":
            title,

        "source_url":
            source_url,

        "github_repo":
            github_repo,

        "resolution_status":
            status,

        "error":
            error,
    })

    print(
        f"[{i}/{len(required_fresh_ids)}]",
        fresh_id,
        status,
        github_repo
    )

    time.sleep(0.08)


project_df = pd.DataFrame(
    project_rows
)


project_lookup = {
    row["fresh_id"]:
        row

    for row in project_rows
}


component_rows = []


for row in test_query_df.itertuples(
    index=False
):

    fresh_id = clean(
        row.source_fresh_id
    )

    project = project_lookup.get(
        fresh_id,
        {}
    )

    relative_path = clean(
        row.source_relative_path
    )

    expected_java = expected_java_filename(
        relative_path
    )

    component_rows.append({
        "query_id":
            clean(row.query_id),

        "node_id":
            clean(row.node_id),

        "source_fresh_id":
            fresh_id,

        "source_version_id":
            clean(row.source_version_id),

        "source_version_number":
            clean(row.source_version_number),

        "source_relative_path":
            relative_path,

        "source_component_sha256":
            clean(row.source_component_sha256),

        "expected_outer_class":
            outer_class_from_relative_path(
                relative_path
            ),

        "expected_java_filename":
            expected_java,

        "project_id":
            clean(
                project.get(
                    "project_id"
                )
            ),

        "github_repo":
            clean(
                project.get(
                    "github_repo"
                )
            ),

        "project_resolution_status":
            clean(
                project.get(
                    "resolution_status"
                )
            ),

        "github_source_available":
            bool(
                clean(
                    project.get(
                        "github_repo"
                    )
                )
            ),
    })


component_df = pd.DataFrame(
    component_rows
)


project_status_counts = (
    project_df[
        "resolution_status"
    ]
    .value_counts()
    .to_dict()
)


github_projects = int(
    (
        project_df[
            "resolution_status"
        ]
        ==
        "GITHUB_SOURCE"
    ).sum()
)


github_components = int(
    component_df[
        "github_source_available"
    ].astype(bool).sum()
)


github_queries = int(
    component_df[
        component_df[
            "github_source_available"
        ].astype(bool)
    ][
        "query_id"
    ].nunique()
)


fully_github_query_count = 0


for query_id, group in component_df.groupby(
    "query_id"
):

    if (
        group[
            "github_source_available"
        ]
        .astype(bool)
        .all()
    ):
        fully_github_query_count += 1


summary = {
    "phase10a2_complete":
        True,

    "scope":
        "TEST_CODE_SOURCE_REPOSITORY_RESOLUTION",

    "test_code_components":
        int(
            len(component_df)
        ),

    "test_queries":
        int(
            component_df[
                "query_id"
            ].nunique()
        ),

    "unique_source_projects":
        int(
            len(project_df)
        ),

    "github_source_projects":
        github_projects,

    "github_source_project_rate":
        (
            github_projects
            /
            len(project_df)
            if len(project_df)
            else 0.0
        ),

    "github_source_components":
        github_components,

    "github_source_component_rate":
        (
            github_components
            /
            len(component_df)
            if len(component_df)
            else 0.0
        ),

    "queries_with_at_least_one_github_code_source":
        github_queries,

    "queries_with_all_code_sources_on_github":
        int(
            fully_github_query_count
        ),

    "project_resolution_status_counts":
        {
            str(k):
                int(v)

            for k, v
            in project_status_counts.items()
        },

    "notes": {
        "java_mapping_not_yet_claimed":
            True,

        "current_stage_only_resolves_project_source_repository":
            True,

        "class_to_java_mapping_next_phase":
            True,

        "manual_annotation_used":
            False,
    },

    "ready_for_phase10a3":
        bool(
            github_projects > 0
        ),
}


project_df.to_csv(
    OUTPUT_PROJECTS,
    index=False,
    encoding="utf-8-sig"
)


component_df.to_csv(
    OUTPUT_COMPONENTS,
    index=False,
    encoding="utf-8-sig"
)


OUTPUT_SUMMARY.write_text(
    json.dumps(
        summary,
        ensure_ascii=False,
        indent=2
    ),
    encoding="utf-8"
)


print()
print("=" * 60)
print("PHASE 10A-2 RESULT")
print("=" * 60)

print(
    "Unique source projects:",
    summary[
        "unique_source_projects"
    ]
)

print(
    "GitHub source projects:",
    summary[
        "github_source_projects"
    ],
    "/",
    summary[
        "unique_source_projects"
    ]
)

print(
    "GitHub CODE components:",
    summary[
        "github_source_components"
    ],
    "/",
    summary[
        "test_code_components"
    ]
)

print(
    "Queries with all CODE sources on GitHub:",
    summary[
        "queries_with_all_code_sources_on_github"
    ],
    "/",
    summary[
        "test_queries"
    ]
)

print(
    "Status counts:",
    summary[
        "project_resolution_status_counts"
    ]
)

print(
    "READY FOR 10A-3:",
    summary[
        "ready_for_phase10a3"
    ]
)

print()
print(
    "Summary:",
    OUTPUT_SUMMARY
)