import json
import random
import statistics
import time
from pathlib import Path

import pandas as pd
import requests


# =========================================================
# Config
# =========================================================

SEED = 20260812

TARGET_MOD_COUNT = 90
BACKGROUND_LIBRARY_COUNT = 30

MIN_VALID_FABRIC_VERSIONS = 4

SEARCH_LIMIT = 100
MAX_OFFSETS_PER_INDEX = 15

SEARCH_INDEXES = [
    "downloads",
    "updated",
    "newest",
]

LICENSE_ALLOWLIST = {
    "MIT",
    "Apache-2.0",
    "MPL-2.0",
    "BSD-3-Clause",
}

API_BASE = (
    "https://api.modrinth.com/v2"
)

RESULT_ROOT = Path("results")
RESULT_ROOT.mkdir(exist_ok=True)

EXISTING_FILES = [
    Path(
        "results/dataset_corpus_v3.csv"
    ),
    Path(
        "data/registry/release_package_registry.csv"
    ),
]

OUTPUT_CSV = (
    RESULT_ROOT
    / "phase6a_fresh_corpus.csv"
)

OUTPUT_JSON = (
    RESULT_ROOT
    / "phase6a_summary.json"
)

FAILURE_JSON = (
    RESULT_ROOT
    / "phase6a_failures.json"
)


random.seed(SEED)


session = requests.Session()

session.headers.update({
    "User-Agent":
        "mod-provenance-research/"
        "phase6a academic research"
})


# =========================================================
# Existing pilot corpus
# =========================================================

existing_project_ids = set()
existing_slugs = set()
existing_titles = set()


PROJECT_ID_COLUMNS = {
    "project_id",
    "modrinth_project_id",
    "modrinth_id",
}

SLUG_COLUMNS = {
    "slug",
    "project_slug",
    "modrinth_slug",
}

TITLE_COLUMNS = {
    "title",
    "project_title",
    "name",
}


for path in EXISTING_FILES:

    if not path.exists():
        continue

    try:

        df = pd.read_csv(
            path
        )

    except Exception:
        continue


    for column in df.columns:

        normalized = (
            str(column)
            .strip()
            .lower()
        )


        if (
            normalized
            in PROJECT_ID_COLUMNS
        ):

            for value in (
                df[column]
                .dropna()
                .astype(str)
            ):

                value = (
                    value.strip()
                )

                if value:

                    existing_project_ids.add(
                        value
                    )


        elif (
            normalized
            in SLUG_COLUMNS
        ):

            for value in (
                df[column]
                .dropna()
                .astype(str)
            ):

                value = (
                    value.strip()
                    .lower()
                )

                if value:

                    existing_slugs.add(
                        value
                    )


        elif (
            normalized
            in TITLE_COLUMNS
        ):

            for value in (
                df[column]
                .dropna()
                .astype(str)
            ):

                value = (
                    value.strip()
                    .lower()
                )

                if value:

                    existing_titles.add(
                        value
                    )


print(
    "======================================"
)
print(
    "Phase 6A - Fresh Corpus Collection"
)
print(
    "======================================"
)

print(
    "Existing project IDs:",
    len(existing_project_ids)
)

print(
    "Existing slugs:",
    len(existing_slugs)
)

print(
    "Existing titles:",
    len(existing_titles)
)


# =========================================================
# HTTP helper
# =========================================================

def get_json(
    endpoint,
    params=None,
    retries=4,
):

    url = (
        API_BASE
        + endpoint
    )


    for attempt in range(
        retries
    ):

        try:

            response = (
                session.get(
                    url,
                    params=params,
                    timeout=30,
                )
            )


            if (
                response.status_code
                == 429
            ):

                wait = (
                    2.0
                    * (
                        attempt + 1
                    )
                )

                print(
                    "Rate limited; "
                    f"sleep {wait}s"
                )

                time.sleep(wait)

                continue


            response.raise_for_status()

            return (
                response.json()
            )


        except Exception as exc:

            if (
                attempt
                == retries - 1
            ):

                raise


            wait = (
                1.5
                * (
                    attempt + 1
                )
            )

            print(
                "Retry:",
                endpoint,
                repr(exc),
            )

            time.sleep(wait)


# =========================================================
# Search pool
# =========================================================

facets = json.dumps([
    [
        "project_type:mod"
    ],
    [
        "categories:fabric"
    ],
    [
        "open_source:true"
    ],
])


candidate_by_id = {}


for search_index in (
    SEARCH_INDEXES
):

    print()
    print(
        "Search index:",
        search_index
    )


    for page in range(
        MAX_OFFSETS_PER_INDEX
    ):

        offset = (
            page
            * SEARCH_LIMIT
        )


        try:

            data = get_json(
                "/search",
                params={
                    "facets":
                        facets,

                    "index":
                        search_index,

                    "offset":
                        offset,

                    "limit":
                        SEARCH_LIMIT,
                },
            )


        except Exception as exc:

            print(
                "Search failed:",
                search_index,
                offset,
                repr(exc),
            )

            break


        hits = (
            data.get(
                "hits",
                []
            )
        )


        if not hits:
            break


        for hit in hits:

            project_id = str(
                hit.get(
                    "project_id",
                    ""
                )
            ).strip()

            slug = str(
                hit.get(
                    "slug",
                    ""
                )
            ).strip()

            title = str(
                hit.get(
                    "title",
                    ""
                )
            ).strip()

            license_id = str(
                hit.get(
                    "license",
                    ""
                )
            ).strip()


            if not project_id:
                continue


            # ---------------------------------------------
            # Exclude development corpus
            # ---------------------------------------------

            if (
                project_id
                in existing_project_ids
            ):

                continue


            if (
                slug.lower()
                in existing_slugs
            ):

                continue


            if (
                title.lower()
                in existing_titles
            ):

                continue


            # ---------------------------------------------
            # Explicit license allowlist
            # ---------------------------------------------

            if (
                license_id
                not in
                LICENSE_ALLOWLIST
            ):

                continue


            if (
                project_id
                not in
                candidate_by_id
            ):

                candidate_by_id[
                    project_id
                ] = hit


        print(
            "offset=",
            offset,
            "pool=",
            len(
                candidate_by_id
            ),
        )


        total_hits = int(
            data.get(
                "total_hits",
                0
            )
        )


        if (
            offset
            + len(hits)
            >= total_hits
        ):
            break


        time.sleep(
            0.05
        )


candidate_pool = list(
    candidate_by_id.values()
)


# deterministic shuffle so final corpus
# is not simply "most downloaded"
random.Random(
    SEED
).shuffle(
    candidate_pool
)


print()
print(
    "Raw fresh candidate pool:",
    len(candidate_pool)
)


# =========================================================
# Version file helper
# =========================================================

def select_jar_file(
    version
):

    files = (
        version.get(
            "files",
            []
        )
        or []
    )


    usable = []


    for file in files:

        filename = str(
            file.get(
                "filename",
                ""
            )
        )


        if (
            not filename.lower()
            .endswith(".jar")
        ):
            continue


        file_type = (
            file.get(
                "file_type"
            )
        )


        # Do not select source/dev/doc JARs.
        if file_type in {
            "sources-jar",
            "dev-jar",
            "javadoc-jar",
        }:

            continue


        usable.append(
            file
        )


    if not usable:
        return None


    primary = [
        file
        for file
        in usable
        if file.get(
            "primary"
        )
    ]


    if primary:
        return (
            primary[0]
        )


    return (
        usable[0]
    )


# =========================================================
# Validate Fabric release history
# =========================================================

def valid_fabric_versions(
    project_id
):

    versions = get_json(
        f"/project/"
        f"{project_id}"
        f"/version",
        params={
            "loaders":
                json.dumps(
                    [
                        "fabric"
                    ]
                ),

            "include_changelog":
                "false",
        },
    )


    result = []


    for version in versions:

        status = (
            version.get(
                "status"
            )
        )


        # Final corpus uses publicly listed releases.
        if (
            status
            != "listed"
        ):

            continue


        jar_file = (
            select_jar_file(
                version
            )
        )


        if jar_file is None:
            continue


        date_published = str(
            version.get(
                "date_published",
                ""
            )
        )


        result.append({
            "version_id":
                str(
                    version.get(
                        "id",
                        ""
                    )
                ),

            "version_number":
                str(
                    version.get(
                        "version_number",
                        ""
                    )
                ),

            "date_published":
                date_published,

            "version_type":
                str(
                    version.get(
                        "version_type",
                        ""
                    )
                ),

            "filename":
                str(
                    jar_file.get(
                        "filename",
                        ""
                    )
                ),

            "url":
                str(
                    jar_file.get(
                        "url",
                        ""
                    )
                ),

            "sha1":
                str(
                    (
                        jar_file.get(
                            "hashes",
                            {}
                        )
                        or {}
                    ).get(
                        "sha1",
                        ""
                    )
                ),

            "sha512":
                str(
                    (
                        jar_file.get(
                            "hashes",
                            {}
                        )
                        or {}
                    ).get(
                        "sha512",
                        ""
                    )
                ),
        })


    result.sort(
        key=lambda x:
            x[
                "date_published"
            ],
        reverse=True,
    )


    return result


# =========================================================
# Collect accepted projects
# =========================================================

accepted = []
failures = []

target_count = 0
background_count = 0


for candidate_index, hit in (
    enumerate(
        candidate_pool,
        start=1,
    )
):

    if (
        target_count
        >= TARGET_MOD_COUNT
        and
        background_count
        >= BACKGROUND_LIBRARY_COUNT
    ):
        break


    project_id = str(
        hit[
            "project_id"
        ]
    )

    slug = str(
        hit.get(
            "slug",
            ""
        )
    )

    title = str(
        hit.get(
            "title",
            ""
        )
    )


    categories = sorted(
        set(
            hit.get(
                "categories",
                []
            )
            or []
        )
    )


    display_categories = sorted(
        set(
            hit.get(
                "display_categories",
                []
            )
            or []
        )
    )


    all_categories = {
        str(x).lower()
        for x in (
            categories
            + display_categories
        )
    }


    if (
        "library"
        in all_categories
    ):

        role = (
            "BACKGROUND_LIBRARY"
        )

    else:

        role = (
            "TARGET_MOD"
        )


    # Already filled this bucket.
    if (
        role
        == "TARGET_MOD"
        and
        target_count
        >= TARGET_MOD_COUNT
    ):
        continue


    if (
        role
        == "BACKGROUND_LIBRARY"
        and
        background_count
        >= BACKGROUND_LIBRARY_COUNT
    ):
        continue


    print()
    print(
        f"[{candidate_index}/"
        f"{len(candidate_pool)}] "
        f"{project_id} "
        f"{title} "
        f"[{role}]"
    )


    try:

        versions = (
            valid_fabric_versions(
                project_id
            )
        )


    except Exception as exc:

        print(
            "VERSION ERROR:",
            repr(exc)
        )

        failures.append({
            "project_id":
                project_id,

            "slug":
                slug,

            "title":
                title,

            "reason":
                "version_api_error",

            "detail":
                repr(exc),
        })

        continue


    if (
        len(versions)
        < MIN_VALID_FABRIC_VERSIONS
    ):

        print(
            "SKIP: valid versions =",
            len(versions)
        )

        failures.append({
            "project_id":
                project_id,

            "slug":
                slug,

            "title":
                title,

            "reason":
                "insufficient_fabric_versions",

            "valid_versions":
                len(versions),
        })

        continue


    current = (
        versions[0]
    )

    historical = (
        versions[1:4]
    )


    fresh_id = (
        f"FMOD"
        f"{len(accepted) + 1:04d}"
    )


    accepted.append({
        "fresh_id":
            fresh_id,

        "project_id":
            project_id,

        "slug":
            slug,

        "title":
            title,

        "author":
            str(
                hit.get(
                    "author",
                    ""
                )
            ),

        "role":
            role,

        "license":
            str(
                hit.get(
                    "license",
                    ""
                )
            ),

        "categories":
            json.dumps(
                categories,
                ensure_ascii=False,
            ),

        "display_categories":
            json.dumps(
                display_categories,
                ensure_ascii=False,
            ),

        "downloads":
            int(
                hit.get(
                    "downloads",
                    0
                )
                or 0
            ),

        "date_created":
            str(
                hit.get(
                    "date_created",
                    ""
                )
            ),

        "date_modified":
            str(
                hit.get(
                    "date_modified",
                    ""
                )
            ),

        "valid_fabric_version_count":
            len(
                versions
            ),

        "current_version_id":
            current[
                "version_id"
            ],

        "current_version_number":
            current[
                "version_number"
            ],

        "current_date_published":
            current[
                "date_published"
            ],

        "current_filename":
            current[
                "filename"
            ],

        "current_url":
            current[
                "url"
            ],

        "current_sha1":
            current[
                "sha1"
            ],

        "current_sha512":
            current[
                "sha512"
            ],

        "historical_version_ids":
            json.dumps(
                [
                    x[
                        "version_id"
                    ]
                    for x
                    in historical
                ]
            ),

        "historical_version_numbers":
            json.dumps(
                [
                    x[
                        "version_number"
                    ]
                    for x
                    in historical
                ],
                ensure_ascii=False,
            ),

        "historical_dates":
            json.dumps(
                [
                    x[
                        "date_published"
                    ]
                    for x
                    in historical
                ]
            ),

        "historical_filenames":
            json.dumps(
                [
                    x[
                        "filename"
                    ]
                    for x
                    in historical
                ],
                ensure_ascii=False,
            ),

        "historical_urls":
            json.dumps(
                [
                    x[
                        "url"
                    ]
                    for x
                    in historical
                ]
            ),

        "historical_sha1":
            json.dumps(
                [
                    x[
                        "sha1"
                    ]
                    for x
                    in historical
                ]
            ),

        "historical_sha512":
            json.dumps(
                [
                    x[
                        "sha512"
                    ]
                    for x
                    in historical
                ]
            ),
    })


    if (
        role
        == "TARGET_MOD"
    ):

        target_count += 1

    else:

        background_count += 1


    print(
        "ACCEPTED:",
        "target=",
        target_count,
        "background=",
        background_count,
    )


    time.sleep(
        0.05
    )


# =========================================================
# Save
# =========================================================

accepted_df = pd.DataFrame(
    accepted
)


accepted_df.to_csv(
    OUTPUT_CSV,
    index=False,
    encoding="utf-8-sig",
)


FAILURE_JSON.write_text(
    json.dumps(
        failures,
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)


# =========================================================
# Summary
# =========================================================

if len(accepted_df):

    version_counts = (
        accepted_df[
            "valid_fabric_version_count"
        ]
        .astype(int)
        .tolist()
    )

else:

    version_counts = []


license_counts = {}

if len(accepted_df):

    license_counts = (
        accepted_df[
            "license"
        ]
        .value_counts()
        .to_dict()
    )


summary = {
    "random_seed":
        SEED,

    "development_corpus_excluded":
        True,

    "fresh_projects":
        len(
            accepted_df
        ),

    "target_mods":
        int(
            (
                accepted_df[
                    "role"
                ]
                == "TARGET_MOD"
            ).sum()
        )
        if len(
            accepted_df
        )
        else 0,

    "background_libraries":
        int(
            (
                accepted_df[
                    "role"
                ]
                == "BACKGROUND_LIBRARY"
            ).sum()
        )
        if len(
            accepted_df
        )
        else 0,

    "minimum_required_fabric_versions":
        MIN_VALID_FABRIC_VERSIONS,

    "median_valid_fabric_versions":
        float(
            statistics.median(
                version_counts
            )
        )
        if version_counts
        else 0.0,

    "min_valid_fabric_versions":
        int(
            min(
                version_counts
            )
        )
        if version_counts
        else 0,

    "max_valid_fabric_versions":
        int(
            max(
                version_counts
            )
        )
        if version_counts
        else 0,

    "license_counts":
        {
            str(k):
                int(v)

            for k, v
            in license_counts.items()
        },

    "candidate_pool":
        len(
            candidate_pool
        ),

    "rejected_or_failed":
        len(
            failures
        ),

    "target_goal":
        TARGET_MOD_COUNT,

    "background_goal":
        BACKGROUND_LIBRARY_COUNT,

    "goals_met":
        bool(
            target_count
            >= TARGET_MOD_COUNT
            and
            background_count
            >= BACKGROUND_LIBRARY_COUNT
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


print()
print(
    "======================================"
)
print(
    "PHASE 6A RESULT"
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
    "CSV  :",
    OUTPUT_CSV
)

print(
    "JSON :",
    OUTPUT_JSON
)

print(
    "FAIL :",
    FAILURE_JSON
)