import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import pandas as pd


# =========================================================
# Project root
# =========================================================

ROOT = Path(__file__).resolve().parent.parent


# =========================================================
# Inputs
# =========================================================

PRIVATE_MANIFEST_CSV = (
    ROOT
    / "results"
    / "phase6l_materialized_private_manifest.csv"
)

QUERY_GT_CSV = (
    ROOT
    / "results"
    / "phase6k_query_ground_truth.csv"
)


# =========================================================
# Outputs
# =========================================================

PACKAGE_ROOT = (
    ROOT
    / "results"
    / "phase9e_packages"
)

OUTPUT_MANIFEST_CSV = (
    ROOT
    / "results"
    / "phase9e_package_manifest.csv"
)

OUTPUT_SUMMARY_JSON = (
    ROOT
    / "results"
    / "phase9e_package_materialization_summary.json"
)


# =========================================================
# Constants
# =========================================================

EXPECTED_TEST_QUERIES = 360
EXPECTED_COMPONENTS_PER_QUERY = 7
EXPECTED_TOTAL_COMPONENTS = 2520

EXPECTED_MODALITIES = {
    "CODE_BINARY": 5,
    "STRUCTURED": 1,
    "IMAGE": 1,
}


# =========================================================
# Helpers
# =========================================================

def clean_text(value):

    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    return str(value).strip()


def sha256_file(path):

    digest = hashlib.sha256()

    with Path(path).open("rb") as handle:

        while True:

            chunk = handle.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest()


def normalized_relative_path(value):

    text = clean_text(
        value
    )

    text = text.replace(
        "\\",
        "/",
    )

    while text.startswith(
        "./"
    ):
        text = text[2:]

    return Path(
        text
    )


# =========================================================
# Load files
# =========================================================

for path in [
    PRIVATE_MANIFEST_CSV,
    QUERY_GT_CSV,
]:

    if not path.exists():

        raise FileNotFoundError(
            f"Missing input: {path}"
        )


manifest = pd.read_csv(
    PRIVATE_MANIFEST_CSV
)

query_gt = pd.read_csv(
    QUERY_GT_CSV
)


# =========================================================
# Validate required columns
# =========================================================

required_manifest_columns = {
    "query_id",
    "node_id",
    "stage",
    "scenario",
    "k_true",
    "modality",
    "ground_truth_label",
    "source_fresh_id",
    "payload_relpath",
    "payload_sha256",
    "payload_size_bytes",
}


missing_columns = (
    required_manifest_columns
    -
    set(
        manifest.columns
    )
)


if missing_columns:

    raise RuntimeError(
        "Private manifest is missing columns: "
        + str(
            sorted(
                missing_columns
            )
        )
    )


required_query_columns = {
    "query_id",
    "stage",
    "scenario",
    "k_true",
}


missing_query_columns = (
    required_query_columns
    -
    set(
        query_gt.columns
    )
)


if missing_query_columns:

    raise RuntimeError(
        "Query GT is missing columns: "
        + str(
            sorted(
                missing_query_columns
            )
        )
    )


# =========================================================
# Select TEST queries
# =========================================================

test_gt = query_gt[
    query_gt[
        "stage"
    ].astype(str)
    ==
    "TEST"
].copy()


if len(
    test_gt
) != EXPECTED_TEST_QUERIES:

    raise RuntimeError(
        "Expected "
        f"{EXPECTED_TEST_QUERIES} TEST queries, "
        f"got {len(test_gt)}"
    )


test_query_ids = set(
    test_gt[
        "query_id"
    ].astype(str)
)


test_manifest = manifest[
    manifest[
        "query_id"
    ]
    .astype(str)
    .isin(
        test_query_ids
    )
].copy()


if len(
    test_manifest
) != EXPECTED_TOTAL_COMPONENTS:

    raise RuntimeError(
        "Expected "
        f"{EXPECTED_TOTAL_COMPONENTS} TEST components, "
        f"got {len(test_manifest)}"
    )


print(
    "======================================"
)

print(
    "Phase 9E-1 - Query Package Materialization"
)

print(
    "======================================"
)

print()

print(
    "TEST queries:",
    len(
        test_gt
    )
)

print(
    "TEST components:",
    len(
        test_manifest
    )
)

print(
    "Payload column: payload_relpath"
)


# =========================================================
# Validate query composition before touching files
# =========================================================

for query_id, group in (
    test_manifest.groupby(
        "query_id"
    )
):

    if len(
        group
    ) != EXPECTED_COMPONENTS_PER_QUERY:

        raise RuntimeError(
            f"{query_id}: expected 7 components, "
            f"got {len(group)}"
        )


    modality_counts = (
        group[
            "modality"
        ]
        .astype(str)
        .value_counts()
        .to_dict()
    )


    if modality_counts != EXPECTED_MODALITIES:

        raise RuntimeError(
            f"{query_id}: invalid modality composition "
            f"{modality_counts}"
        )


print(
    "Query composition validation: PASS"
)


# =========================================================
# Discover possible materialization roots
#
# Manifest says paths such as:
#
# queries/Q6K00181/Q6K00181_N01.bin
#
# but this path is not directly under project root.
#
# Instead of guessing the original Phase 6L root,
# locate directories in the project that actually contain
# a "queries" directory.
# =========================================================

candidate_roots = []


def add_candidate_root(path):

    path = Path(
        path
    ).resolve()

    if (
        path.exists()
        and
        path.is_dir()
        and
        path not in candidate_roots
    ):

        candidate_roots.append(
            path
        )


# Common deterministic candidates.
add_candidate_root(
    ROOT
)

add_candidate_root(
    ROOT
    / "results"
)

add_candidate_root(
    ROOT
    / "data"
)

add_candidate_root(
    ROOT
    / "dataset"
)

add_candidate_root(
    ROOT
    / "artifacts"
)

add_candidate_root(
    ROOT
    / "materialized"
)

add_candidate_root(
    ROOT
    / "results"
    / "materialized"
)

add_candidate_root(
    ROOT
    / "results"
    / "phase6l"
)

add_candidate_root(
    ROOT
    / "results"
    / "phase6l_materialized"
)

add_candidate_root(
    ROOT
    / "results"
    / "phase6l_materialized_queries"
)


# Discover every existing "queries" directory.
#
# If:
#
# X/queries/Q6K00181/...
#
# exists, then X is a possible base for payload_relpath.
#
print()

print(
    "Discovering materialized query roots..."
)


queries_directories = []


for queries_dir in ROOT.rglob(
    "queries"
):

    try:

        if not queries_dir.is_dir():
            continue

        # Never inspect packages generated by this phase.
        if PACKAGE_ROOT in queries_dir.parents:
            continue

        queries_directories.append(
            queries_dir.resolve()
        )

    except Exception:
        continue


for queries_dir in queries_directories:

    add_candidate_root(
        queries_dir.parent
    )


print(
    "Candidate roots discovered:",
    len(
        candidate_roots
    )
)


for root in candidate_roots:

    print(
        "  ",
        root
    )


# =========================================================
# Direct path resolver
# =========================================================

def direct_payload_candidates(
    payload_relpath,
):

    relative_path = normalized_relative_path(
        payload_relpath
    )


    candidates = []


    # Absolute path, just in case.
    if relative_path.is_absolute():

        candidates.append(
            relative_path
        )


    # Root / full manifest relative path.
    for root in candidate_roots:

        candidates.append(
            root
            /
            relative_path
        )


    # Manifest usually begins with queries/.
    #
    # If candidate root itself is .../queries,
    # support dropping first path component.
    parts = relative_path.parts


    if (
        len(parts) >= 2
        and
        parts[0].lower()
        ==
        "queries"
    ):

        without_queries = Path(
            *parts[1:]
        )


        for queries_dir in queries_directories:

            candidates.append(
                queries_dir
                /
                without_queries
            )


    # De-duplicate.
    unique = []

    seen = set()


    for candidate in candidates:

        try:

            candidate = (
                candidate.resolve()
            )

        except Exception:

            candidate = Path(
                candidate
            )


        key = str(
            candidate
        ).lower()


        if key in seen:
            continue


        seen.add(
            key
        )

        unique.append(
            candidate
        )


    return unique


# =========================================================
# Fallback filename index
#
# Used only if the relative-path resolution fails.
#
# It does NOT choose files blindly:
# payload SHA-256 must match manifest SHA.
# =========================================================

filename_index = None


def build_filename_index():

    global filename_index


    if filename_index is not None:

        return filename_index


    print()

    print(
        "Building fallback payload filename index..."
    )


    index = {}


    skipped_generated = 0
    scanned = 0


    for path in ROOT.rglob(
        "*"
    ):

        try:

            if not path.is_file():
                continue


            if PACKAGE_ROOT in path.parents:

                skipped_generated += 1
                continue


            scanned += 1


            index.setdefault(
                path.name,
                []
            ).append(
                path.resolve()
            )


        except Exception:
            continue


    filename_index = index


    print(
        "Fallback files scanned:",
        scanned
    )

    print(
        "Generated files skipped:",
        skipped_generated
    )


    return filename_index


# =========================================================
# Payload resolver with SHA verification
# =========================================================

resolution_cache = {}


def resolve_payload(
    payload_relpath,
    expected_sha256,
    expected_size,
):

    payload_relpath = clean_text(
        payload_relpath
    )


    expected_sha256 = (
        clean_text(
            expected_sha256
        )
        .lower()
    )


    expected_size = int(
        expected_size
    )


    cache_key = (
        payload_relpath,
        expected_sha256,
        expected_size,
    )


    if cache_key in resolution_cache:

        return resolution_cache[
            cache_key
        ]


    # -----------------------------------------------------
    # 1. Direct deterministic resolution
    # -----------------------------------------------------

    for candidate in direct_payload_candidates(
        payload_relpath
    ):

        if not candidate.exists():
            continue


        if not candidate.is_file():
            continue


        actual_size = int(
            candidate.stat().st_size
        )


        if (
            expected_size >= 0
            and
            actual_size
            !=
            expected_size
        ):

            continue


        actual_sha = sha256_file(
            candidate
        ).lower()


        if (
            expected_sha256
            and
            actual_sha
            !=
            expected_sha256
        ):

            continue


        resolution_cache[
            cache_key
        ] = (
            candidate,
            "DIRECT_RELATIVE_PATH",
        )


        return resolution_cache[
            cache_key
        ]


    # -----------------------------------------------------
    # 2. Fallback exact filename lookup + SHA
    # -----------------------------------------------------

    index = build_filename_index()


    filename = (
        normalized_relative_path(
            payload_relpath
        ).name
    )


    candidates = index.get(
        filename,
        []
    )


    valid_candidates = []


    for candidate in candidates:

        try:

            actual_size = int(
                candidate.stat().st_size
            )


            if (
                expected_size >= 0
                and
                actual_size
                !=
                expected_size
            ):

                continue


            actual_sha = sha256_file(
                candidate
            ).lower()


            if (
                expected_sha256
                and
                actual_sha
                !=
                expected_sha256
            ):

                continue


            valid_candidates.append(
                candidate
            )


        except Exception:
            continue


    if len(
        valid_candidates
    ) == 1:

        resolution_cache[
            cache_key
        ] = (
            valid_candidates[0],
            "FILENAME_PLUS_SHA256",
        )


        return resolution_cache[
            cache_key
        ]


    if len(
        valid_candidates
    ) > 1:

        # Identical bytes exist in multiple locations.
        #
        # Prefer the candidate whose path ends with the
        # manifest relative path.
        normalized_suffix = (
            payload_relpath
            .replace(
                "\\",
                "/",
            )
            .lower()
        )


        suffix_matches = [
            candidate

            for candidate
            in valid_candidates

            if (
                str(
                    candidate
                )
                .replace(
                    "\\",
                    "/",
                )
                .lower()
                .endswith(
                    normalized_suffix
                )
            )
        ]


        if len(
            suffix_matches
        ) == 1:

            resolution_cache[
                cache_key
            ] = (
                suffix_matches[0],
                "MULTIPLE_SHA_MATCH_SUFFIX_SELECTED",
            )


            return resolution_cache[
                cache_key
            ]


        # All valid candidates contain identical bytes
        # according to frozen SHA-256.
        #
        # Use deterministic lexical ordering.
        selected = sorted(
            valid_candidates,
            key=lambda value:
                str(
                    value
                ).lower(),
        )[0]


        resolution_cache[
            cache_key
        ] = (
            selected,
            "MULTIPLE_IDENTICAL_SHA_LEXICAL_SELECTED",
        )


        return resolution_cache[
            cache_key
        ]


    # -----------------------------------------------------
    # Failure diagnostic
    # -----------------------------------------------------

    checked = direct_payload_candidates(
        payload_relpath
    )


    diagnostic_paths = [
        str(
            value
        )
        for value
        in checked[:20]
    ]


    raise FileNotFoundError(
        "\n"
        "Unable to resolve frozen payload.\n"
        f"payload_relpath = {payload_relpath}\n"
        f"expected_sha256 = {expected_sha256}\n"
        f"expected_size = {expected_size}\n"
        f"filename matches found = {len(candidates)}\n"
        "direct candidates checked:\n"
        +
        "\n".join(
            diagnostic_paths
        )
    )


# =========================================================
# Resolve ALL 2520 payloads before creating any package
#
# This prevents a half-created Phase 9E corpus.
# =========================================================

print()

print(
    "Resolving all frozen TEST payloads..."
)


resolved_payloads = {}


resolution_method_counts = {}


for component_index, row in enumerate(
    test_manifest.itertuples(
        index=False
    ),
    start=1,
):

    if (
        component_index == 1
        or
        component_index % 200 == 0
    ):

        print(
            "resolve",
            component_index,
            "/",
            EXPECTED_TOTAL_COMPONENTS,
        )


    query_id = clean_text(
        row.query_id
    )

    node_id = clean_text(
        row.node_id
    )


    resolved_path, method = resolve_payload(
        row.payload_relpath,
        row.payload_sha256,
        row.payload_size_bytes,
    )


    key = (
        query_id,
        node_id,
    )


    if key in resolved_payloads:

        raise RuntimeError(
            f"Duplicate component key: {key}"
        )


    resolved_payloads[
        key
    ] = {
        "path":
            resolved_path,

        "method":
            method,
    }


    resolution_method_counts[
        method
    ] = (
        resolution_method_counts.get(
            method,
            0,
        )
        +
        1
    )


if len(
    resolved_payloads
) != EXPECTED_TOTAL_COMPONENTS:

    raise RuntimeError(
        "Resolved payload count mismatch"
    )


print()

print(
    "Payload resolution: PASS"
)

print(
    "Resolution methods:"
)

print(
    json.dumps(
        resolution_method_counts,
        ensure_ascii=False,
        indent=2,
    )
)


# =========================================================
# Recreate package output only AFTER all payloads resolved
# =========================================================

if PACKAGE_ROOT.exists():

    shutil.rmtree(
        PACKAGE_ROOT
    )


PACKAGE_ROOT.mkdir(
    parents=True,
    exist_ok=True,
)


# =========================================================
# Create deterministic packages
# =========================================================

package_rows = []


for query_index, (
    query_id,
    group
) in enumerate(
    test_manifest.groupby(
        "query_id",
        sort=True,
    ),
    start=1,
):

    query_id = str(
        query_id
    )


    if (
        query_index == 1
        or
        query_index % 30 == 0
    ):

        print(
            "package",
            query_index,
            "/",
            EXPECTED_TEST_QUERIES,
        )


    group = group.sort_values(
        "node_id",
        kind="stable",
    )


    package_path = (
        PACKAGE_ROOT
        /
        f"{query_id}.zip"
    )


    package_metadata = {
        "query_id":
            query_id,

        "format":
            "heterogeneous_provenance_query_package",

        "format_version":
            1,

        "component_count":
            EXPECTED_COMPONENTS_PER_QUERY,

        "components": [],
    }


    # ZIP_STORED deliberately avoids changing the payload
    # bytes and keeps archive processing deterministic.
    with zipfile.ZipFile(
        package_path,
        mode="w",
        compression=zipfile.ZIP_STORED,
    ) as archive:

        for component_number, row in enumerate(
            group.itertuples(
                index=False
            ),
            start=1,
        ):

            node_id = clean_text(
                row.node_id
            )

            modality = clean_text(
                row.modality
            )


            resolved = resolved_payloads[
                (
                    query_id,
                    node_id,
                )
            ]


            payload_path = resolved[
                "path"
            ]


            expected_sha = clean_text(
                row.payload_sha256
            ).lower()


            actual_sha = sha256_file(
                payload_path
            ).lower()


            if actual_sha != expected_sha:

                raise RuntimeError(
                    f"{query_id}/{node_id}: "
                    "payload SHA changed between "
                    "resolution and packaging"
                )


            original_suffix = (
                payload_path.suffix
                if payload_path.suffix
                else ".bin"
            )


            # Archive name contains no source identity.
            archive_name = (
                "components/"
                f"{component_number:02d}_"
                f"{node_id}"
                f"{original_suffix}"
            )


            archive.write(
                payload_path,
                arcname=archive_name,
            )


            package_metadata[
                "components"
            ].append({
                "node_id":
                    node_id,

                "modality":
                    modality,

                "archive_path":
                    archive_name,

                "payload_sha256":
                    expected_sha,

                "payload_size_bytes":
                    int(
                        row.payload_size_bytes
                    ),
            })


        archive.writestr(
            "manifest.json",
            json.dumps(
                package_metadata,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ).encode(
                "utf-8"
            ),
        )


    package_rows.append({
        "query_id":
            query_id,

        "package_path":
            str(
                package_path.relative_to(
                    ROOT
                )
            ),

        "package_size_bytes":
            int(
                package_path.stat().st_size
            ),

        "package_sha256":
            sha256_file(
                package_path
            ),

        "component_count":
            EXPECTED_COMPONENTS_PER_QUERY,
    })


package_df = pd.DataFrame(
    package_rows
)


if len(
    package_df
) != EXPECTED_TEST_QUERIES:

    raise RuntimeError(
        "Package count mismatch"
    )


# =========================================================
# Full archive integrity validation
# =========================================================

print()

print(
    "Validating generated archives..."
)


archive_validation_failures = []


validated_components = 0


for package_index, row in enumerate(
    package_df.itertuples(
        index=False
    ),
    start=1,
):

    if (
        package_index == 1
        or
        package_index % 50 == 0
    ):

        print(
            "validate",
            package_index,
            "/",
            EXPECTED_TEST_QUERIES,
        )


    package_path = (
        ROOT
        /
        row.package_path
    )


    try:

        with zipfile.ZipFile(
            package_path,
            mode="r",
        ) as archive:

            bad_member = (
                archive.testzip()
            )


            if bad_member is not None:

                archive_validation_failures.append({
                    "query_id":
                        row.query_id,

                    "reason":
                        "ZIP_CRC_FAILURE",

                    "member":
                        bad_member,
                })

                continue


            names = set(
                archive.namelist()
            )


            if (
                "manifest.json"
                not in names
            ):

                archive_validation_failures.append({
                    "query_id":
                        row.query_id,

                    "reason":
                        "MISSING_MANIFEST",
                })

                continue


            package_metadata = json.loads(
                archive.read(
                    "manifest.json"
                ).decode(
                    "utf-8"
                )
            )


            components_meta = (
                package_metadata[
                    "components"
                ]
            )


            if len(
                components_meta
            ) != EXPECTED_COMPONENTS_PER_QUERY:

                archive_validation_failures.append({
                    "query_id":
                        row.query_id,

                    "reason":
                        "BAD_COMPONENT_COUNT",
                })

                continue


            for component in components_meta:

                member_name = (
                    component[
                        "archive_path"
                    ]
                )


                if member_name not in names:

                    archive_validation_failures.append({
                        "query_id":
                            row.query_id,

                        "reason":
                            "MISSING_COMPONENT",

                        "member":
                            member_name,
                    })

                    continue


                payload_bytes = (
                    archive.read(
                        member_name
                    )
                )


                actual_sha = (
                    hashlib.sha256(
                        payload_bytes
                    )
                    .hexdigest()
                )


                expected_sha = (
                    component[
                        "payload_sha256"
                    ]
                    .lower()
                )


                if (
                    actual_sha
                    !=
                    expected_sha
                ):

                    archive_validation_failures.append({
                        "query_id":
                            row.query_id,

                        "reason":
                            "PAYLOAD_SHA_MISMATCH",

                        "member":
                            member_name,
                    })

                    continue


                if (
                    len(
                        payload_bytes
                    )
                    !=
                    int(
                        component[
                            "payload_size_bytes"
                        ]
                    )
                ):

                    archive_validation_failures.append({
                        "query_id":
                            row.query_id,

                        "reason":
                            "PAYLOAD_SIZE_MISMATCH",

                        "member":
                            member_name,
                    })

                    continue


                validated_components += 1


    except Exception as error:

        archive_validation_failures.append({
            "query_id":
                row.query_id,

            "reason":
                "ARCHIVE_EXCEPTION",

            "error":
                repr(
                    error
                ),
        })


# =========================================================
# Save package manifest
# =========================================================

OUTPUT_MANIFEST_CSV.parent.mkdir(
    parents=True,
    exist_ok=True,
)


package_df.to_csv(
    OUTPUT_MANIFEST_CSV,
    index=False,
    encoding="utf-8-sig",
)


# =========================================================
# Summary
# =========================================================

total_package_bytes = int(
    package_df[
        "package_size_bytes"
    ].sum()
)


summary = {
    "phase9e_package_materialization_complete":
        True,

    "scope":
        (
            "MATERIALIZED_HETEROGENEOUS_"
            "PROVENANCE_QUERY_PACKAGES"
        ),

    "queries":
        int(
            len(
                package_df
            )
        ),

    "components":
        EXPECTED_TOTAL_COMPONENTS,

    "components_per_query":
        EXPECTED_COMPONENTS_PER_QUERY,

    "modality_composition":
        EXPECTED_MODALITIES,

    "payload_path_column":
        "payload_relpath",

    "payload_resolution": {
        "resolved_components":
            int(
                len(
                    resolved_payloads
                )
            ),

        "resolution_method_counts":
            {
                key:
                    int(
                        value
                    )

                for key, value
                in resolution_method_counts.items()
            },
    },

    "archive_validation": {
        "validated_components":
            int(
                validated_components
            ),

        "validation_failures":
            int(
                len(
                    archive_validation_failures
                )
            ),
    },

    "package_storage": {
        "compression":
            "ZIP_STORED",

        "total_package_bytes":
            total_package_bytes,

        "median_package_bytes":
            float(
                package_df[
                    "package_size_bytes"
                ].median()
            ),

        "min_package_bytes":
            int(
                package_df[
                    "package_size_bytes"
                ].min()
            ),

        "max_package_bytes":
            int(
                package_df[
                    "package_size_bytes"
                ].max()
            ),
    },

    "runnable_mod_claim":
        False,

    "package_definition":
        (
            "A deterministic archive containing "
            "the seven frozen materialized benchmark "
            "components plus component-type metadata. "
            "It is a heterogeneous provenance-query "
            "package, not a runnable game MOD."
        ),

    "private_ground_truth_in_package":
        False,

    "source_identity_in_package_manifest":
        False,

    "goals_met":
        bool(
            len(
                package_df
            )
            == EXPECTED_TEST_QUERIES

            and
            len(
                resolved_payloads
            )
            == EXPECTED_TOTAL_COMPONENTS

            and
            validated_components
            == EXPECTED_TOTAL_COMPONENTS

            and
            len(
                archive_validation_failures
            )
            == 0
        ),
}


OUTPUT_SUMMARY_JSON.write_text(
    json.dumps(
        summary,
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)


# =========================================================
# Print
# =========================================================

print()

print(
    "======================================"
)

print(
    "PHASE 9E-1 FINAL RESULT"
)

print(
    "======================================"
)


print(
    "Packages:",
    len(
        package_df
    ),
    "/",
    EXPECTED_TEST_QUERIES,
)


print(
    "Resolved payloads:",
    len(
        resolved_payloads
    ),
    "/",
    EXPECTED_TOTAL_COMPONENTS,
)


print(
    "Validated archive components:",
    validated_components,
    "/",
    EXPECTED_TOTAL_COMPONENTS,
)


print(
    "Archive failures:",
    len(
        archive_validation_failures
    )
)


print(
    "Median package bytes:",
    summary[
        "package_storage"
    ][
        "median_package_bytes"
    ]
)


print(
    "GOALS MET:",
    summary[
        "goals_met"
    ]
)


print()

print(
    "Package manifest:",
    OUTPUT_MANIFEST_CSV
)

print(
    "Summary:",
    OUTPUT_SUMMARY_JSON
)