import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
DATA = ROOT / "data"

SPLIT_CSV = RESULTS / "phase6c_project_split.csv"
QUERY_CSV = RESULTS / "phase6l_materialized_private_manifest.csv"

CURRENT_COMPONENT_CSV = (
    DATA
    / "fresh_registry"
    / "fresh_current_component_registry_filtered.csv"
)

CURRENT_PACKAGE_CSV = (
    DATA
    / "fresh_registry"
    / "fresh_current_package_registry.csv"
)

OUT_ROOT = DATA / "phase10a5_stonedetector_corpus"
QUERY_DIR = OUT_ROOT / "query"
GALLERY_DIR = OUT_ROOT / "gallery"

OUT_QUERY_MAP = RESULTS / "phase10a5_query_private_mapping.csv"
OUT_GALLERY_MAP = RESULTS / "phase10a5_gallery_private_mapping.csv"
OUT_PARENT_MAP = RESULTS / "phase10a5_parent_private_mapping.csv"
OUT_AUDIT = RESULTS / "phase10a5_payload_audit.csv"
OUT_SUMMARY = RESULTS / "phase10a5_stonedetector_corpus_summary.json"


def clean(v):
    if v is None:
        return ""
    return str(v).strip()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()

    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)

            if not chunk:
                break

            h.update(chunk)

    return h.hexdigest()


def modality_is_code(value):
    value = clean(value).upper()

    return value in {
        "CODE",
        "CODE_BINARY",
        "BYTECODE",
        "CLASS",
    }


def resolve_root_relative(path_text):
    path_text = clean(path_text)

    if not path_text:
        raise RuntimeError("Empty payload path")

    p = Path(path_text)

    if p.is_absolute():
        return p

    # Phase6L query payload paths are relative to data/final_benchmark.
    final_benchmark_candidate = ROOT / "data" / "final_benchmark" / p
    if final_benchmark_candidate.exists():
        return final_benchmark_candidate

    # Other registry paths such as current JAR local_path are project-root relative.
    root_candidate = ROOT / p
    if root_candidate.exists():
        return root_candidate

    # Preserve deterministic failure path if neither exists.
    return root_candidate


print("=" * 72)
print("PHASE 10A-5 — STONEDETECTOR FROZEN CORPUS")
print("=" * 72)


# --------------------------------------------------------------------
# Load frozen registries
# --------------------------------------------------------------------

split_df = pd.read_csv(
    SPLIT_CSV,
    dtype=str,
    keep_default_na=False,
)

query_df = pd.read_csv(
    QUERY_CSV,
    dtype=str,
    keep_default_na=False,
)

current_df = pd.read_csv(
    CURRENT_COMPONENT_CSV,
    dtype=str,
    keep_default_na=False,
)

package_df = pd.read_csv(
    CURRENT_PACKAGE_CSV,
    dtype=str,
    keep_default_na=False,
)


# --------------------------------------------------------------------
# Freeze TEST gallery = TEST_KNOWN + TEST_BACKGROUND
# --------------------------------------------------------------------

gallery_split_names = {
    "TEST_KNOWN",
    "TEST_BACKGROUND",
}

gallery_projects_df = split_df[
    split_df["frozen_split"].isin(
        gallery_split_names
    )
].copy()

gallery_fresh_ids = sorted(
    gallery_projects_df[
        "fresh_id"
    ].unique()
)

unknown_fresh_ids = set(
    split_df.loc[
        split_df["frozen_split"]
        ==
        "UNKNOWN_HELDOUT",
        "fresh_id",
    ]
)


if len(gallery_fresh_ids) != 60:
    raise RuntimeError(
        "Expected exactly 60 TEST gallery projects, "
        f"got {len(gallery_fresh_ids)}"
    )


gallery_unknown_overlap = (
    set(gallery_fresh_ids)
    &
    unknown_fresh_ids
)


if gallery_unknown_overlap:
    raise RuntimeError(
        "UNKNOWN leakage into gallery: "
        +
        repr(
            sorted(
                gallery_unknown_overlap
            )
        )
    )


print(
    "Frozen gallery projects:",
    len(gallery_fresh_ids)
)

print(
    "UNKNOWN held-out overlap:",
    len(gallery_unknown_overlap)
)


# --------------------------------------------------------------------
# Deterministic anonymous parent IDs
# --------------------------------------------------------------------

parent_rows = []

fresh_to_parent = {}


for idx, fresh_id in enumerate(
    gallery_fresh_ids,
    start=1,
):
    parent_id = f"P{idx:04d}"

    fresh_to_parent[
        fresh_id
    ] = parent_id

    row = gallery_projects_df[
        gallery_projects_df[
            "fresh_id"
        ]
        ==
        fresh_id
    ].iloc[0]

    parent_rows.append({
        "anonymous_parent_id":
            parent_id,

        "fresh_id":
            fresh_id,

        "project_id":
            clean(
                row.get(
                    "project_id",
                    ""
                )
            ),

        "slug":
            clean(
                row.get(
                    "slug",
                    ""
                )
            ),

        "title":
            clean(
                row.get(
                    "title",
                    ""
                )
            ),

        "frozen_split":
            clean(
                row.get(
                    "frozen_split",
                    ""
                )
            ),
    })


parent_df = pd.DataFrame(
    parent_rows
)


# --------------------------------------------------------------------
# TEST query CODE components
# --------------------------------------------------------------------

test_query_df = query_df[
    query_df["stage"].str.upper()
    ==
    "TEST"
].copy()

test_query_df = test_query_df[
    test_query_df[
        "modality"
    ].apply(
        modality_is_code
    )
].copy()


if len(test_query_df) != 1800:
    raise RuntimeError(
        "Expected 1800 frozen TEST CODE components, "
        f"got {len(test_query_df)}"
    )


query_ids = sorted(
    test_query_df[
        "query_id"
    ].unique()
)


if len(query_ids) != 360:
    raise RuntimeError(
        "Expected 360 TEST queries, "
        f"got {len(query_ids)}"
    )


query_to_anon = {
    query_id:
        f"Q{idx:04d}"

    for idx, query_id
    in enumerate(
        query_ids,
        start=1,
    )
}


query_sizes = (
    test_query_df
    .groupby(
        "query_id"
    )
    .size()
)


if not (
    query_sizes == 5
).all():
    raise RuntimeError(
        "Every TEST query must contain exactly "
        "5 CODE components.\n"
        +
        repr(
            query_sizes[
                query_sizes != 5
            ].to_dict()
        )
    )


print(
    "Frozen TEST queries:",
    len(query_ids)
)

print(
    "Frozen TEST CODE components:",
    len(test_query_df)
)


# --------------------------------------------------------------------
# Gallery current CODE components
# --------------------------------------------------------------------

gallery_code_df = current_df[
    current_df[
        "fresh_id"
    ].isin(
        gallery_fresh_ids
    )
].copy()

gallery_code_df = gallery_code_df[
    gallery_code_df[
        "modality"
    ].apply(
        modality_is_code
    )
].copy()


if len(gallery_code_df) == 0:
    raise RuntimeError(
        "No gallery CODE components found."
    )


current_package_lookup = {}


for row in package_df.itertuples(
    index=False
):
    if clean(
        row.release_kind
    ).upper() != "CURRENT":
        continue

    current_package_lookup[
        clean(
            row.fresh_id
        )
    ] = {
        "filename":
            clean(
                row.filename
            ),

        "local_path":
            clean(
                row.local_path
            ),

        "download_sha256":
            clean(
                row.download_sha256
            ),

        "download_status":
            clean(
                row.download_status
            ),
    }


missing_package_projects = sorted(
    set(
        gallery_code_df[
            "fresh_id"
        ]
    )
    -
    set(
        current_package_lookup
    )
)


if missing_package_projects:
    raise RuntimeError(
        "Missing current package registry for: "
        +
        repr(
            missing_package_projects
        )
    )


print(
    "Gallery CODE components:",
    len(gallery_code_df)
)


# --------------------------------------------------------------------
# Recreate output directory
# --------------------------------------------------------------------

if OUT_ROOT.exists():
    shutil.rmtree(
        OUT_ROOT
    )


QUERY_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

GALLERY_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# --------------------------------------------------------------------
# Materialize frozen query classes
# --------------------------------------------------------------------

query_mapping_rows = []
audit_rows = []


for query_id in query_ids:

    anon_query = query_to_anon[
        query_id
    ]

    qdir = QUERY_DIR / anon_query

    qdir.mkdir(
        parents=True,
        exist_ok=True,
    )

    group = (
        test_query_df[
            test_query_df[
                "query_id"
            ]
            ==
            query_id
        ]
        .sort_values(
            "node_id"
        )
        .reset_index(
            drop=True
        )
    )

    for local_index, row in group.iterrows():

        node_number = (
            local_index + 1
        )

        anonymous_filename = (
            f"{anon_query}_N{node_number:02d}.class"
        )

        source_payload = (
            resolve_root_relative(
                row[
                    "payload_relpath"
                ]
            )
        )

        if not source_payload.exists():
            raise FileNotFoundError(
                "Frozen query payload missing:\n"
                +
                str(
                    source_payload
                )
            )

        actual_sha = sha256_file(
            source_payload
        )

        expected_payload_sha = clean(
            row.get(
                "payload_sha256",
                ""
            )
        )

        if (
            expected_payload_sha
            and
            actual_sha.lower()
            !=
            expected_payload_sha.lower()
        ):
            raise RuntimeError(
                "Frozen query payload SHA mismatch:\n"
                f"{query_id} "
                f"{row['node_id']}\n"
                f"expected={expected_payload_sha}\n"
                f"actual={actual_sha}"
            )

        dest = (
            qdir
            /
            anonymous_filename
        )

        shutil.copyfile(
            source_payload,
            dest,
        )

        copied_sha = sha256_file(
            dest
        )

        if copied_sha != actual_sha:
            raise RuntimeError(
                "Query copy SHA mismatch."
            )

        query_mapping_rows.append({
            "anonymous_query_id":
                anon_query,

            "anonymous_filename":
                anonymous_filename,

            "query_id":
                clean(
                    row[
                        "query_id"
                    ]
                ),

            "node_id":
                clean(
                    row[
                        "node_id"
                    ]
                ),

            "scenario":
                clean(
                    row.get(
                        "scenario",
                        ""
                    )
                ),

            "k_true":
                clean(
                    row.get(
                        "k_true",
                        ""
                    )
                ),

            "ground_truth_label":
                clean(
                    row.get(
                        "ground_truth_label",
                        ""
                    )
                ),

            "source_fresh_id":
                clean(
                    row.get(
                        "source_fresh_id",
                        ""
                    )
                ),

            "source_version_id":
                clean(
                    row.get(
                        "source_version_id",
                        ""
                    )
                ),

            "source_relative_path":
                clean(
                    row.get(
                        "source_relative_path",
                        ""
                    )
                ),

            "payload_relpath":
                clean(
                    row[
                        "payload_relpath"
                    ]
                ),

            "payload_sha256":
                actual_sha,

            "stone_relpath":
                str(
                    dest.relative_to(
                        OUT_ROOT
                    )
                ).replace(
                    "\\",
                    "/"
                ),
        })

        audit_rows.append({
            "kind":
                "QUERY",

            "anonymous_group":
                anon_query,

            "anonymous_filename":
                anonymous_filename,

            "original_fresh_id":
                clean(
                    row.get(
                        "source_fresh_id",
                        ""
                    )
                ),

            "original_relative_path":
                clean(
                    row.get(
                        "source_relative_path",
                        ""
                    )
                ),

            "expected_sha256":
                expected_payload_sha,

            "actual_sha256":
                copied_sha,

            "sha_match":
                (
                    not expected_payload_sha
                    or
                    expected_payload_sha.lower()
                    ==
                    copied_sha.lower()
                ),
        })


# --------------------------------------------------------------------
# Materialize gallery classes from exact current JAR entries
# --------------------------------------------------------------------

gallery_mapping_rows = []

gallery_counter = 0

jar_cache = {}


for fresh_id in gallery_fresh_ids:

    parent_id = fresh_to_parent[
        fresh_id
    ]

    pdir = (
        GALLERY_DIR
        /
        parent_id
    )

    pdir.mkdir(
        parents=True,
        exist_ok=True,
    )

    package = current_package_lookup[
        fresh_id
    ]

    jar_path = resolve_root_relative(
        package[
            "local_path"
        ]
    )

    if not jar_path.exists():
        raise FileNotFoundError(
            f"Current gallery JAR missing: {jar_path}"
        )

    expected_jar_sha = clean(
        package[
            "download_sha256"
        ]
    )

    actual_jar_sha = sha256_file(
        jar_path
    )

    if (
        expected_jar_sha
        and
        actual_jar_sha.lower()
        !=
        expected_jar_sha.lower()
    ):
        raise RuntimeError(
            f"Current JAR SHA mismatch: {fresh_id}\n"
            f"expected={expected_jar_sha}\n"
            f"actual={actual_jar_sha}"
        )

    project_components = (
        gallery_code_df[
            gallery_code_df[
                "fresh_id"
            ]
            ==
            fresh_id
        ]
        .sort_values(
            [
                "relative_path",
                "component_sha256",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    with zipfile.ZipFile(
        jar_path,
        "r",
    ) as jar:

        zip_names = set(
            jar.namelist()
        )

        for local_index, row in project_components.iterrows():

            relative_path = clean(
                row[
                    "relative_path"
                ]
            ).replace(
                "\\",
                "/"
            )

            if relative_path not in zip_names:
                raise RuntimeError(
                    f"Registry entry missing from JAR:\n"
                    f"{fresh_id}\n"
                    f"{relative_path}\n"
                    f"{jar_path}"
                )

            payload = jar.read(
                relative_path
            )

            payload_sha = sha256_bytes(
                payload
            )

            expected_component_sha = clean(
                row[
                    "component_sha256"
                ]
            )

            if (
                payload_sha.lower()
                !=
                expected_component_sha.lower()
            ):
                raise RuntimeError(
                    "Gallery component SHA mismatch:\n"
                    f"{fresh_id}\n"
                    f"{relative_path}\n"
                    f"expected={expected_component_sha}\n"
                    f"actual={payload_sha}"
                )

            gallery_counter += 1

            anonymous_filename = (
                f"{parent_id}_G{local_index + 1:06d}.class"
            )

            dest = (
                pdir
                /
                anonymous_filename
            )

            dest.write_bytes(
                payload
            )

            copied_sha = sha256_file(
                dest
            )

            if copied_sha != payload_sha:
                raise RuntimeError(
                    "Gallery copy SHA mismatch."
                )

            gallery_mapping_rows.append({
                "anonymous_parent_id":
                    parent_id,

                "anonymous_filename":
                    anonymous_filename,

                "fresh_id":
                    fresh_id,

                "project_id":
                    clean(
                        row.get(
                            "project_id",
                            ""
                        )
                    ),

                "frozen_split":
                    clean(
                        gallery_projects_df.loc[
                            gallery_projects_df[
                                "fresh_id"
                            ]
                            ==
                            fresh_id,
                            "frozen_split",
                        ].iloc[0]
                    ),

                "version_id":
                    clean(
                        row.get(
                            "version_id",
                            ""
                        )
                    ),

                "version_number":
                    clean(
                        row.get(
                            "version_number",
                            ""
                        )
                    ),

                "jar_filename":
                    clean(
                        row.get(
                            "jar_filename",
                            ""
                        )
                    ),

                "relative_path":
                    relative_path,

                "component_sha256":
                    payload_sha,

                "stone_relpath":
                    str(
                        dest.relative_to(
                            OUT_ROOT
                        )
                    ).replace(
                        "\\",
                        "/"
                    ),
            })

            audit_rows.append({
                "kind":
                    "GALLERY",

                "anonymous_group":
                    parent_id,

                "anonymous_filename":
                    anonymous_filename,

                "original_fresh_id":
                    fresh_id,

                "original_relative_path":
                    relative_path,

                "expected_sha256":
                    expected_component_sha,

                "actual_sha256":
                    copied_sha,

                "sha_match":
                    (
                        expected_component_sha.lower()
                        ==
                        copied_sha.lower()
                    ),
            })


# --------------------------------------------------------------------
# Final audits
# --------------------------------------------------------------------

query_mapping_df = pd.DataFrame(
    query_mapping_rows
)

gallery_mapping_df = pd.DataFrame(
    gallery_mapping_rows
)

audit_df = pd.DataFrame(
    audit_rows
)


if not audit_df[
    "sha_match"
].astype(bool).all():
    raise RuntimeError(
        "At least one SHA audit failed."
    )


actual_query_files = list(
    QUERY_DIR.rglob(
        "*.class"
    )
)

actual_gallery_files = list(
    GALLERY_DIR.rglob(
        "*.class"
    )
)


if len(actual_query_files) != 1800:
    raise RuntimeError(
        "Materialized query file count mismatch: "
        f"{len(actual_query_files)}"
    )


if len(actual_gallery_files) != len(
    gallery_code_df
):
    raise RuntimeError(
        "Materialized gallery file count mismatch: "
        f"{len(actual_gallery_files)} "
        f"vs registry {len(gallery_code_df)}"
    )


unknown_gallery_leaks = sorted(
    set(
        gallery_mapping_df[
            "fresh_id"
        ]
    )
    &
    unknown_fresh_ids
)


if unknown_gallery_leaks:
    raise RuntimeError(
        "UNKNOWN project leaked into StoneDetector gallery."
    )


# Anonymous directories only in public StoneDetector corpus.
top_query_groups = sorted(
    p.name
    for p in QUERY_DIR.iterdir()
    if p.is_dir()
)

top_gallery_groups = sorted(
    p.name
    for p in GALLERY_DIR.iterdir()
    if p.is_dir()
)


if len(top_query_groups) != 360:
    raise RuntimeError(
        "Expected 360 anonymous query directories."
    )


if len(top_gallery_groups) != 60:
    raise RuntimeError(
        "Expected 60 anonymous gallery directories."
    )


# --------------------------------------------------------------------
# Write outputs
# --------------------------------------------------------------------

query_mapping_df.to_csv(
    OUT_QUERY_MAP,
    index=False,
    encoding="utf-8-sig",
)

gallery_mapping_df.to_csv(
    OUT_GALLERY_MAP,
    index=False,
    encoding="utf-8-sig",
)

parent_df.to_csv(
    OUT_PARENT_MAP,
    index=False,
    encoding="utf-8-sig",
)

audit_df.to_csv(
    OUT_AUDIT,
    index=False,
    encoding="utf-8-sig",
)


gallery_counts_by_parent = (
    gallery_mapping_df
    .groupby(
        "anonymous_parent_id"
    )
    .size()
)


summary = {
    "phase10a5_complete":
        True,

    "scope":
        "FROZEN_STONEDETECTOR_BYTECODE_CORPUS",

    "stone_detector_input_kind":
        "CLASS_FILES",

    "test_queries":
        int(
            len(query_ids)
        ),

    "query_code_components":
        int(
            len(query_mapping_df)
        ),

    "gallery_projects":
        int(
            len(parent_df)
        ),

    "gallery_code_components":
        int(
            len(gallery_mapping_df)
        ),

    "total_class_files":
        int(
            len(query_mapping_df)
            +
            len(gallery_mapping_df)
        ),

    "gallery_split_counts":
        {
            str(k):
                int(v)

            for k, v
            in parent_df[
                "frozen_split"
            ]
            .value_counts()
            .to_dict()
            .items()
        },

    "gallery_code_components_min_per_project":
        int(
            gallery_counts_by_parent.min()
        ),

    "gallery_code_components_median_per_project":
        float(
            gallery_counts_by_parent.median()
        ),

    "gallery_code_components_max_per_project":
        int(
            gallery_counts_by_parent.max()
        ),

    "query_sha_audit_passed":
        bool(
            audit_df[
                audit_df[
                    "kind"
                ]
                ==
                "QUERY"
            ][
                "sha_match"
            ]
            .astype(bool)
            .all()
        ),

    "gallery_sha_audit_passed":
        bool(
            audit_df[
                audit_df[
                    "kind"
                ]
                ==
                "GALLERY"
            ][
                "sha_match"
            ]
            .astype(bool)
            .all()
        ),

    "unknown_gallery_leak_count":
        int(
            len(
                unknown_gallery_leaks
            )
        ),

    "identity_bearing_input_paths_removed":
        True,

    "anonymous_query_directories":
        360,

    "anonymous_parent_directories":
        60,

    "stone_detector_config": {
        "METRIC":
            "LCS",

        "THRESHOLD":
            "0.3f",

        "MINFUNCTIONSIZE":
            15,

        "USEFUNCTIONNAMES":
            True,

        "BYTECODEBASEDCLONEDETECTION":
            True,

        "REGISTERCODE_STACKCODE":
            True,
    },

    "important_protocol_notes": {
        "test_not_retuned":
            True,

        "gallery_definition":
            "TEST_KNOWN + TEST_BACKGROUND frozen projects",

        "unknown_projects_excluded_from_gallery":
            True,

        "query_bytes":
            "Exact Phase6L frozen materialized TEST CODE payloads",

        "gallery_bytes":
            "Exact filtered current-release CLASS entries from frozen registry",

        "original_class_paths_not_exposed_to_stonedetector":
            True,
    },

    "corpus_path":
        str(
            OUT_ROOT
        ),

    "ready_for_phase10a6":
        True,
}


OUT_SUMMARY.write_text(
    json.dumps(
        summary,
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)


print()
print("=" * 72)
print("PHASE 10A-5 RESULT")
print("=" * 72)

print(
    "Queries:",
    summary[
        "test_queries"
    ]
)

print(
    "Query CODE:",
    summary[
        "query_code_components"
    ]
)

print(
    "Gallery projects:",
    summary[
        "gallery_projects"
    ]
)

print(
    "Gallery CODE:",
    summary[
        "gallery_code_components"
    ]
)

print(
    "Total .class:",
    summary[
        "total_class_files"
    ]
)

print(
    "Gallery splits:",
    summary[
        "gallery_split_counts"
    ]
)

print(
    "Gallery CODE/project min/median/max:",
    summary[
        "gallery_code_components_min_per_project"
    ],
    "/",
    summary[
        "gallery_code_components_median_per_project"
    ],
    "/",
    summary[
        "gallery_code_components_max_per_project"
    ]
)

print(
    "Query SHA audit:",
    summary[
        "query_sha_audit_passed"
    ]
)

print(
    "Gallery SHA audit:",
    summary[
        "gallery_sha_audit_passed"
    ]
)

print(
    "UNKNOWN gallery leaks:",
    summary[
        "unknown_gallery_leak_count"
    ]
)

print(
    "READY FOR 10A-6:",
    summary[
        "ready_for_phase10a6"
    ]
)

print()
print(
    "Summary:",
    OUT_SUMMARY
)