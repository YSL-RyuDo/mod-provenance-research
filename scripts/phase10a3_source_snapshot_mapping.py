import json
import os
import re
import shutil
import subprocess
import time
import urllib.request
from collections import Counter
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
CACHE = ROOT / "cache" / "phase10a3_repositories"

PROJECTS_CSV = RESULTS / "phase10a2_project_source_resolution.csv"
COMPONENTS_CSV = RESULTS / "phase10a2_code_source_resolution.csv"

OUTPUT_PROJECTS = RESULTS / "phase10a3_repository_snapshot_audit.csv"
OUTPUT_COMPONENTS = RESULTS / "phase10a3_class_to_java_mapping.csv"
OUTPUT_SUMMARY = RESULTS / "phase10a3_source_snapshot_mapping_summary.json"

MODRINTH_VERSION_API = "https://api.modrinth.com/v2/version/"

CACHE.mkdir(
    parents=True,
    exist_ok=True
)


def clean(value):
    if value is None:
        return ""

    return str(value).strip()


def run(
    args,
    cwd=None,
    check=True
):
    result = subprocess.run(
        args,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    if check and result.returncode != 0:
        raise RuntimeError(
            "Command failed:\n"
            + " ".join(map(str, args))
            + "\nSTDOUT:\n"
            + result.stdout
            + "\nSTDERR:\n"
            + result.stderr
        )

    return result


def fetch_json(
    url,
    timeout=30
):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent":
                "mod-provenance-research-phase10a3/1.0"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=timeout
    ) as response:

        return json.loads(
            response.read().decode("utf-8")
        )


def safe_repo_name(
    fresh_id,
    github_url
):
    tail = github_url.rstrip("/").split("/")[-1]

    tail = re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        tail
    )

    return f"{fresh_id}__{tail}"


def normalize_version(value):
    value = clean(value).lower()

    value = value.replace(
        "_",
        "-"
    )

    value = re.sub(
        r"^refs/tags/",
        "",
        value
    )

    value = re.sub(
        r"^v(?=\d)",
        "",
        value
    )

    value = re.sub(
        r"[^a-z0-9]+",
        "",
        value
    )

    return value


def list_tags(repo_dir):
    result = run(
        [
            "git",
            "tag",
            "--list"
        ],
        cwd=repo_dir
    )

    return [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
    ]


def choose_tag(
    version_number,
    tags
):
    target = normalize_version(
        version_number
    )

    if not target:
        return "", "NO_VERSION"

    exact = [
        tag
        for tag in tags
        if normalize_version(tag) == target
    ]

    if len(exact) == 1:
        return exact[0], "EXACT_NORMALIZED_TAG"

    if len(exact) > 1:
        exact_sorted = sorted(
            exact,
            key=lambda x: (
                len(x),
                x
            )
        )

        return (
            exact_sorted[0],
            "AMBIGUOUS_NORMALIZED_TAG"
        )

    # Weak suffix match, still explicitly marked.
    suffix = [
        tag
        for tag in tags
        if (
            target
            and
            normalize_version(tag).endswith(
                target
            )
        )
    ]

    if len(suffix) == 1:
        return (
            suffix[0],
            "UNIQUE_SUFFIX_TAG"
        )

    return "", "NO_TAG_MATCH"


def resolve_commit_before_date(
    repo_dir,
    date_published
):
    date_published = clean(
        date_published
    )

    if not date_published:
        return ""

    result = run(
        [
            "git",
            "rev-list",
            "-1",
            "--before=" + date_published,
            "--all"
        ],
        cwd=repo_dir,
        check=False
    )

    return result.stdout.strip()


def resolve_snapshot(
    repo_dir,
    version_number,
    date_published
):
    tags = list_tags(
        repo_dir
    )

    tag, tag_status = choose_tag(
        version_number,
        tags
    )

    if tag:
        result = run(
            [
                "git",
                "rev-list",
                "-n",
                "1",
                tag
            ],
            cwd=repo_dir,
            check=False
        )

        sha = result.stdout.strip()

        if sha:
            return {
                "snapshot_commit":
                    sha,

                "snapshot_ref":
                    tag,

                "snapshot_resolution":
                    tag_status,

                "snapshot_exact_release_claim":
                    bool(
                        tag_status
                        ==
                        "EXACT_NORMALIZED_TAG"
                    )
            }

    heuristic_sha = resolve_commit_before_date(
        repo_dir,
        date_published
    )

    if heuristic_sha:
        return {
            "snapshot_commit":
                heuristic_sha,

            "snapshot_ref":
                "",

            "snapshot_resolution":
                "DATE_HEURISTIC",

            "snapshot_exact_release_claim":
                False
        }

    return {
        "snapshot_commit":
            "",

        "snapshot_ref":
            "",

        "snapshot_resolution":
            "UNRESOLVED",

        "snapshot_exact_release_claim":
            False
    }


def git_ls_java_files(
    repo_dir,
    commit
):
    result = run(
        [
            "git",
            "ls-tree",
            "-r",
            "--name-only",
            commit
        ],
        cwd=repo_dir,
        check=False
    )

    if result.returncode != 0:
        return []

    return [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip().lower().endswith(
            ".java"
        )
    ]


def outer_java_filename(
    class_relative_path
):
    name = Path(
        clean(class_relative_path)
    ).name

    if name.lower().endswith(
        ".class"
    ):
        name = name[:-6]

    if "$" in name:
        name = name.split(
            "$",
            1
        )[0]

    if not name:
        return ""

    return name + ".java"


def expected_package_suffix(
    class_relative_path
):
    path = clean(
        class_relative_path
    ).replace("\\", "/")

    if path.lower().endswith(
        ".class"
    ):
        path = path[:-6]

    if "$" in path.rsplit("/", 1)[-1]:
        directory, filename = (
            path.rsplit("/", 1)
            if "/" in path
            else ("", path)
        )

        filename = filename.split(
            "$",
            1
        )[0]

        path = (
            directory + "/" + filename
            if directory
            else filename
        )

    return path + ".java"


def map_class_to_java(
    class_relative_path,
    java_files
):
    expected_name = outer_java_filename(
        class_relative_path
    )

    expected_suffix = expected_package_suffix(
        class_relative_path
    ).lower()

    if not expected_name:
        return {
            "java_path":
                "",

            "mapping_status":
                "NO_EXPECTED_NAME",

            "candidate_count":
                0
        }

    basename_matches = [
        path
        for path in java_files
        if Path(path).name == expected_name
    ]

    if not basename_matches:
        return {
            "java_path":
                "",

            "mapping_status":
                "NO_BASENAME_MATCH",

            "candidate_count":
                0
        }

    suffix_matches = [
        path
        for path in basename_matches
        if path.lower().endswith(
            expected_suffix
        )
    ]

    if len(suffix_matches) == 1:
        return {
            "java_path":
                suffix_matches[0],

            "mapping_status":
                "EXACT_PACKAGE_SUFFIX",

            "candidate_count":
                len(basename_matches)
        }

    if len(basename_matches) == 1:
        return {
            "java_path":
                basename_matches[0],

            "mapping_status":
                "UNIQUE_BASENAME",

            "candidate_count":
                1
        }

    return {
        "java_path":
            "",

        "mapping_status":
            "AMBIGUOUS_BASENAME",

        "candidate_count":
            len(basename_matches)
    }


project_df = pd.read_csv(
    PROJECTS_CSV,
    dtype=str,
    keep_default_na=False
)

component_df = pd.read_csv(
    COMPONENTS_CSV,
    dtype=str,
    keep_default_na=False
)


github_projects = project_df[
    project_df[
        "resolution_status"
    ]
    ==
    "GITHUB_SOURCE"
].copy()


print("=" * 65)
print("PHASE 10A-3 SOURCE SNAPSHOT + CLASS→JAVA AUDIT")
print("=" * 65)

print(
    "GitHub source projects:",
    len(github_projects)
)

print(
    "CODE components:",
    len(component_df)
)


# ---------------------------------------------------------
# Clone/update repositories
# ---------------------------------------------------------

repo_dirs = {}
repo_errors = {}


for index, row in enumerate(
    github_projects.itertuples(
        index=False
    ),
    start=1
):

    fresh_id = clean(
        row.fresh_id
    )

    github_repo = clean(
        row.github_repo
    )

    local_name = safe_repo_name(
        fresh_id,
        github_repo
    )

    local_dir = CACHE / local_name

    print()
    print(
        f"[Repository {index}/{len(github_projects)}]",
        fresh_id,
        github_repo
    )

    try:

        if (
            local_dir.exists()
            and
            (local_dir / ".git").exists()
        ):

            print(
                "Updating cached repository..."
            )

            run(
                [
                    "git",
                    "fetch",
                    "--all",
                    "--tags",
                    "--prune"
                ],
                cwd=local_dir
            )

        else:

            if local_dir.exists():
                shutil.rmtree(
                    local_dir
                )

            print(
                "Cloning..."
            )

            run(
                [
                    "git",
                    "clone",
                    "--mirror",
                    github_repo + ".git",
                    str(local_dir)
                ]
            )

            # mirror repo still supports ls-tree/rev-list/tag.
            run(
                [
                    "git",
                    "fetch",
                    "--all",
                    "--tags",
                    "--prune"
                ],
                cwd=local_dir
            )

        repo_dirs[
            fresh_id
        ] = local_dir

    except Exception as exc:

        repo_errors[
            fresh_id
        ] = repr(
            exc
        )

        print(
            "REPOSITORY ERROR:",
            repr(exc)
        )


# ---------------------------------------------------------
# Resolve Modrinth versions
# ---------------------------------------------------------

unique_versions = (
    component_df[
        [
            "source_fresh_id",
            "source_version_id",
            "source_version_number"
        ]
    ]
    .drop_duplicates()
    .reset_index(
        drop=True
    )
)


version_metadata = {}


print()
print(
    "Resolving Modrinth version metadata:",
    len(unique_versions)
)


for index, row in enumerate(
    unique_versions.itertuples(
        index=False
    ),
    start=1
):

    version_id = clean(
        row.source_version_id
    )

    if version_id in version_metadata:
        continue

    try:

        data = fetch_json(
            MODRINTH_VERSION_API
            +
            version_id
        )

        version_metadata[
            version_id
        ] = {
            "version_number":
                clean(
                    data.get(
                        "version_number"
                    )
                ),

            "date_published":
                clean(
                    data.get(
                        "date_published"
                    )
                ),

            "version_type":
                clean(
                    data.get(
                        "version_type"
                    )
                )
        }

    except Exception as exc:

        version_metadata[
            version_id
        ] = {
            "version_number":
                clean(
                    row.source_version_number
                ),

            "date_published":
                "",

            "version_type":
                "",

            "error":
                repr(exc)
        }

    if (
        index == 1
        or
        index % 25 == 0
        or
        index == len(unique_versions)
    ):
        print(
            index,
            "/",
            len(unique_versions)
        )

    time.sleep(
        0.06
    )


# ---------------------------------------------------------
# Resolve one snapshot per project/version
# ---------------------------------------------------------

snapshot_cache = {}
project_snapshot_rows = []


for row in unique_versions.itertuples(
    index=False
):

    fresh_id = clean(
        row.source_fresh_id
    )

    version_id = clean(
        row.source_version_id
    )

    original_version_number = clean(
        row.source_version_number
    )

    metadata = version_metadata.get(
        version_id,
        {}
    )

    version_number = (
        clean(
            metadata.get(
                "version_number"
            )
        )
        or
        original_version_number
    )

    date_published = clean(
        metadata.get(
            "date_published"
        )
    )

    key = (
        fresh_id,
        version_id
    )

    if fresh_id in repo_errors:

        resolution = {
            "snapshot_commit":
                "",

            "snapshot_ref":
                "",

            "snapshot_resolution":
                "REPOSITORY_ERROR",

            "snapshot_exact_release_claim":
                False
        }

    elif fresh_id not in repo_dirs:

        resolution = {
            "snapshot_commit":
                "",

            "snapshot_ref":
                "",

            "snapshot_resolution":
                "NO_GITHUB_REPOSITORY",

            "snapshot_exact_release_claim":
                False
        }

    else:

        try:

            resolution = resolve_snapshot(
                repo_dirs[
                    fresh_id
                ],
                version_number,
                date_published
            )

        except Exception as exc:

            resolution = {
                "snapshot_commit":
                    "",

                "snapshot_ref":
                    "",

                "snapshot_resolution":
                    "SNAPSHOT_ERROR",

                "snapshot_exact_release_claim":
                    False,

                "error":
                    repr(exc)
            }

    snapshot_cache[
        key
    ] = resolution

    project_snapshot_rows.append({
        "source_fresh_id":
            fresh_id,

        "source_version_id":
            version_id,

        "source_version_number":
            original_version_number,

        "api_version_number":
            version_number,

        "date_published":
            date_published,

        "snapshot_commit":
            clean(
                resolution.get(
                    "snapshot_commit"
                )
            ),

        "snapshot_ref":
            clean(
                resolution.get(
                    "snapshot_ref"
                )
            ),

        "snapshot_resolution":
            clean(
                resolution.get(
                    "snapshot_resolution"
                )
            ),

        "snapshot_exact_release_claim":
            bool(
                resolution.get(
                    "snapshot_exact_release_claim",
                    False
                )
            ),

        "error":
            clean(
                resolution.get(
                    "error"
                )
            )
    })


snapshot_df = pd.DataFrame(
    project_snapshot_rows
)


# ---------------------------------------------------------
# Build Java file lists per resolved snapshot
# ---------------------------------------------------------

java_file_cache = {}


for key, resolution in snapshot_cache.items():

    fresh_id, version_id = key

    commit = clean(
        resolution.get(
            "snapshot_commit"
        )
    )

    if (
        not commit
        or
        fresh_id not in repo_dirs
    ):
        java_file_cache[
            key
        ] = []

        continue

    try:

        java_file_cache[
            key
        ] = git_ls_java_files(
            repo_dirs[
                fresh_id
            ],
            commit
        )

    except Exception:

        java_file_cache[
            key
        ] = []


# ---------------------------------------------------------
# Component mapping
# ---------------------------------------------------------

mapping_rows = []


for index, row in enumerate(
    component_df.itertuples(
        index=False
    ),
    start=1
):

    fresh_id = clean(
        row.source_fresh_id
    )

    version_id = clean(
        row.source_version_id
    )

    class_path = clean(
        row.source_relative_path
    )

    key = (
        fresh_id,
        version_id
    )

    resolution = snapshot_cache.get(
        key,
        {}
    )

    java_files = java_file_cache.get(
        key,
        []
    )

    mapping = map_class_to_java(
        class_path,
        java_files
    )

    github_repo = clean(
        row.github_repo
    )

    snapshot_resolution = clean(
        resolution.get(
            "snapshot_resolution"
        )
    )

    mapping_status = clean(
        mapping.get(
            "mapping_status"
        )
    )

    high_confidence = bool(
        snapshot_resolution
        ==
        "EXACT_NORMALIZED_TAG"
        and
        mapping_status
        in {
            "EXACT_PACKAGE_SUFFIX",
            "UNIQUE_BASENAME"
        }
    )

    source_resolvable = bool(
        clean(
            resolution.get(
                "snapshot_commit"
            )
        )
        and
        clean(
            mapping.get(
                "java_path"
            )
        )
    )

    mapping_rows.append({
        "query_id":
            clean(
                row.query_id
            ),

        "node_id":
            clean(
                row.node_id
            ),

        "source_fresh_id":
            fresh_id,

        "source_version_id":
            version_id,

        "source_version_number":
            clean(
                row.source_version_number
            ),

        "source_relative_class_path":
            class_path,

        "github_repo":
            github_repo,

        "snapshot_commit":
            clean(
                resolution.get(
                    "snapshot_commit"
                )
            ),

        "snapshot_ref":
            clean(
                resolution.get(
                    "snapshot_ref"
                )
            ),

        "snapshot_resolution":
            snapshot_resolution,

        "snapshot_exact_release_claim":
            bool(
                resolution.get(
                    "snapshot_exact_release_claim",
                    False
                )
            ),

        "java_path":
            clean(
                mapping.get(
                    "java_path"
                )
            ),

        "java_mapping_status":
            mapping_status,

        "java_candidate_count":
            int(
                mapping.get(
                    "candidate_count",
                    0
                )
            ),

        "source_resolvable":
            source_resolvable,

        "high_confidence_mapping":
            high_confidence
    })

    if (
        index == 1
        or
        index % 200 == 0
        or
        index == len(component_df)
    ):
        print(
            "Mapped",
            index,
            "/",
            len(component_df)
        )


mapping_df = pd.DataFrame(
    mapping_rows
)


# ---------------------------------------------------------
# Query-level coverage
# ---------------------------------------------------------

query_total = int(
    mapping_df[
        "query_id"
    ].nunique()
)


queries_all_resolvable = 0
queries_all_high_confidence = 0
queries_any_resolvable = 0


for query_id, group in mapping_df.groupby(
    "query_id"
):

    flags = group[
        "source_resolvable"
    ].astype(bool)

    high_flags = group[
        "high_confidence_mapping"
    ].astype(bool)

    if flags.any():
        queries_any_resolvable += 1

    if flags.all():
        queries_all_resolvable += 1

    if high_flags.all():
        queries_all_high_confidence += 1


snapshot_counts = (
    snapshot_df[
        "snapshot_resolution"
    ]
    .value_counts()
    .to_dict()
)


mapping_counts = (
    mapping_df[
        "java_mapping_status"
    ]
    .value_counts()
    .to_dict()
)


resolved_components = int(
    mapping_df[
        "source_resolvable"
    ].astype(bool).sum()
)


high_components = int(
    mapping_df[
        "high_confidence_mapping"
    ].astype(bool).sum()
)


summary = {
    "phase10a3_complete":
        True,

    "scope":
        "SOURCE_SNAPSHOT_AND_CLASS_TO_JAVA_MAPPING_AUDIT",

    "input_code_components":
        int(
            len(mapping_df)
        ),

    "input_queries":
        query_total,

    "repository_errors":
        int(
            len(repo_errors)
        ),

    "unique_project_versions":
        int(
            len(snapshot_df)
        ),

    "snapshot_resolution_counts": {
        str(k):
            int(v)

        for k, v
        in snapshot_counts.items()
    },

    "java_mapping_status_counts": {
        str(k):
            int(v)

        for k, v
        in mapping_counts.items()
    },

    "source_resolvable_components":
        resolved_components,

    "source_resolvable_component_rate":
        (
            resolved_components
            /
            len(mapping_df)
            if len(mapping_df)
            else 0.0
        ),

    "high_confidence_components":
        high_components,

    "high_confidence_component_rate":
        (
            high_components
            /
            len(mapping_df)
            if len(mapping_df)
            else 0.0
        ),

    "queries_with_any_resolvable_code":
        int(
            queries_any_resolvable
        ),

    "queries_with_all_code_resolvable":
        int(
            queries_all_resolvable
        ),

    "queries_with_all_code_high_confidence":
        int(
            queries_all_high_confidence
        ),

    "manual_annotation_used":
        False,

    "important_interpretation": {
        "exact_normalized_tag":
            (
                "Version number matched a Git tag "
                "after normalization."
            ),

        "date_heuristic":
            (
                "Nearest repository commit before "
                "Modrinth release date; this is NOT "
                "claimed to be the exact build source."
            ),

        "high_confidence_definition":
            (
                "EXACT_NORMALIZED_TAG plus an "
                "unambiguous Java source mapping."
            )
    },

    "ready_for_phase10a4":
        bool(
            resolved_components
            > 0
        )
}


snapshot_df.to_csv(
    OUTPUT_PROJECTS,
    index=False,
    encoding="utf-8-sig"
)


mapping_df.to_csv(
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
print("=" * 65)
print("PHASE 10A-3 FINAL RESULT")
print("=" * 65)

print(
    "Project/version snapshots:",
    len(snapshot_df)
)

print(
    "Snapshot status:",
    summary[
        "snapshot_resolution_counts"
    ]
)

print(
    "Resolvable CODE components:",
    resolved_components,
    "/",
    len(mapping_df),
    "(",
    round(
        summary[
            "source_resolvable_component_rate"
        ]
        * 100,
        2
    ),
    "%)"
)

print(
    "High-confidence components:",
    high_components,
    "/",
    len(mapping_df),
    "(",
    round(
        summary[
            "high_confidence_component_rate"
        ]
        * 100,
        2
    ),
    "%)"
)

print(
    "Queries all 5 CODE resolvable:",
    queries_all_resolvable,
    "/",
    query_total
)

print(
    "Queries all 5 CODE high-confidence:",
    queries_all_high_confidence,
    "/",
    query_total
)

print(
    "Java mapping statuses:",
    summary[
        "java_mapping_status_counts"
    ]
)

print(
    "READY FOR 10A-4:",
    summary[
        "ready_for_phase10a4"
    ]
)

print()
print(
    "Summary:",
    OUTPUT_SUMMARY
)