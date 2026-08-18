import json
import struct
import zipfile
from collections import defaultdict, deque
from pathlib import Path

import pandas as pd


# =========================================================
# Config
# =========================================================

HISTORICAL_COMPONENT_CSV = Path(
    "data/fresh_registry/"
    "fresh_historical_component_registry_filtered.csv"
)

HISTORICAL_PACKAGE_CSV = Path(
    "data/fresh_registry/"
    "fresh_historical_package_registry.csv"
)

HARD_CATALOG_CSV = Path(
    "results/"
    "phase6e_hard_candidate_catalog.csv"
)

SPLIT_CSV = Path(
    "results/"
    "phase6c_project_split.csv"
)

OUTPUT_EDGE_CSV = Path(
    "results/"
    "phase6f_historical_code_edges.csv"
)

OUTPUT_RELEASE_CSV = Path(
    "results/"
    "phase6f_historical_graph_release_stats.csv"
)

OUTPUT_FAILURE_JSON = Path(
    "results/"
    "phase6f_graph_failures.json"
)

OUTPUT_SUMMARY_JSON = Path(
    "results/"
    "phase6f_graph_summary.json"
)


QUERY_SPLITS = {
    "CALIBRATION_KNOWN",
    "TEST_KNOWN",
    "UNKNOWN_HELDOUT",
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


def normalize_path(value):

    return (
        clean_text(value)
        .replace("\\", "/")
    )


def as_bool(value):

    if isinstance(value, bool):
        return value

    if value is None:
        return False

    text = (
        str(value)
        .strip()
        .lower()
    )

    return text in {
        "1",
        "true",
        "yes",
        "y",
    }


# =========================================================
# Java class constant-pool parser
# =========================================================

def read_u1(
    data,
    offset,
):

    if offset + 1 > len(data):
        raise ValueError(
            "unexpected EOF: u1"
        )

    return (
        data[offset],
        offset + 1,
    )


def read_u2(
    data,
    offset,
):

    if offset + 2 > len(data):
        raise ValueError(
            "unexpected EOF: u2"
        )

    value = struct.unpack_from(
        ">H",
        data,
        offset,
    )[0]

    return (
        value,
        offset + 2,
    )


def read_u4(
    data,
    offset,
):

    if offset + 4 > len(data):
        raise ValueError(
            "unexpected EOF: u4"
        )

    value = struct.unpack_from(
        ">I",
        data,
        offset,
    )[0]

    return (
        value,
        offset + 4,
    )


def skip_bytes(
    data,
    offset,
    size,
):

    new_offset = (
        offset + size
    )

    if new_offset > len(data):

        raise ValueError(
            "unexpected EOF while skipping"
        )

    return new_offset


def normalize_class_ref(
    name
):

    if not name:
        return None


    # Array descriptors:
    #
    # [Lfoo/bar/Baz;
    # [[Lfoo/bar/Baz;
    #
    # Primitive arrays are ignored.
    if name.startswith("["):

        pos = name.find(
            "L"
        )

        end = name.rfind(
            ";"
        )


        if (
            pos >= 0
            and
            end > pos
        ):

            return name[
                pos + 1:
                end
            ]


        return None


    return name


def parse_constant_pool_class_refs(
    data
):

    offset = 0


    magic, offset = read_u4(
        data,
        offset,
    )


    if magic != 0xCAFEBABE:

        raise ValueError(
            "invalid class magic"
        )


    # minor / major
    _, offset = read_u2(
        data,
        offset,
    )

    _, offset = read_u2(
        data,
        offset,
    )


    cp_count, offset = read_u2(
        data,
        offset,
    )


    cp = [
        None
        for _ in range(
            cp_count
        )
    ]


    index = 1


    while index < cp_count:

        tag, offset = read_u1(
            data,
            offset,
        )


        # CONSTANT_Utf8
        if tag == 1:

            length, offset = read_u2(
                data,
                offset,
            )


            if (
                offset + length
                > len(data)
            ):

                raise ValueError(
                    "invalid UTF8 length"
                )


            raw = data[
                offset:
                offset + length
            ]

            offset += length


            # Modified UTF-8 is technically used by
            # class files. For internal class names,
            # ordinary UTF-8 decoding with replacement
            # is sufficient here.
            text = raw.decode(
                "utf-8",
                errors="replace",
            )


            cp[
                index
            ] = (
                "UTF8",
                text,
            )


        # CONSTANT_Integer
        elif tag == 3:

            offset = skip_bytes(
                data,
                offset,
                4,
            )


        # CONSTANT_Float
        elif tag == 4:

            offset = skip_bytes(
                data,
                offset,
                4,
            )


        # CONSTANT_Long
        elif tag == 5:

            offset = skip_bytes(
                data,
                offset,
                8,
            )

            # Takes two CP slots.
            index += 1


        # CONSTANT_Double
        elif tag == 6:

            offset = skip_bytes(
                data,
                offset,
                8,
            )

            index += 1


        # CONSTANT_Class
        elif tag == 7:

            name_index, offset = read_u2(
                data,
                offset,
            )


            cp[
                index
            ] = (
                "CLASS",
                name_index,
            )


        # CONSTANT_String
        elif tag == 8:

            offset = skip_bytes(
                data,
                offset,
                2,
            )


        # Fieldref / Methodref / InterfaceMethodref
        elif tag in {
            9,
            10,
            11,
        }:

            offset = skip_bytes(
                data,
                offset,
                4,
            )


        # NameAndType
        elif tag == 12:

            offset = skip_bytes(
                data,
                offset,
                4,
            )


        # MethodHandle
        elif tag == 15:

            offset = skip_bytes(
                data,
                offset,
                3,
            )


        # MethodType
        elif tag == 16:

            offset = skip_bytes(
                data,
                offset,
                2,
            )


        # Dynamic
        elif tag == 17:

            offset = skip_bytes(
                data,
                offset,
                4,
            )


        # InvokeDynamic
        elif tag == 18:

            offset = skip_bytes(
                data,
                offset,
                4,
            )


        # Module
        elif tag == 19:

            offset = skip_bytes(
                data,
                offset,
                2,
            )


        # Package
        elif tag == 20:

            offset = skip_bytes(
                data,
                offset,
                2,
            )


        else:

            raise ValueError(
                f"unknown constant-pool "
                f"tag: {tag}"
            )


        index += 1


    refs = set()


    for entry in cp:

        if (
            not entry
            or
            entry[
                0
            ] != "CLASS"
        ):

            continue


        name_index = (
            entry[
                1
            ]
        )


        if (
            name_index <= 0
            or
            name_index >= len(cp)
        ):

            continue


        utf_entry = (
            cp[
                name_index
            ]
        )


        if (
            not utf_entry
            or
            utf_entry[
                0
            ] != "UTF8"
        ):

            continue


        normalized = (
            normalize_class_ref(
                utf_entry[
                    1
                ]
            )
        )


        if normalized:

            refs.add(
                normalized
            )


    return refs


# =========================================================
# Connected components
# =========================================================

def connected_components(
    nodes,
    edges,
):

    adjacency = {
        node: set()
        for node in nodes
    }


    for source, target in edges:

        if (
            source not in adjacency
            or
            target not in adjacency
        ):

            continue


        adjacency[
            source
        ].add(
            target
        )

        adjacency[
            target
        ].add(
            source
        )


    visited = set()

    components = []


    for start in nodes:

        if start in visited:
            continue


        queue = deque(
            [
                start
            ]
        )

        visited.add(
            start
        )

        component = set()


        while queue:

            node = (
                queue.popleft()
            )

            component.add(
                node
            )


            for neighbor in (
                adjacency[
                    node
                ]
            ):

                if (
                    neighbor
                    not in visited
                ):

                    visited.add(
                        neighbor
                    )

                    queue.append(
                        neighbor
                    )


        components.append(
            component
        )


    return components


# =========================================================
# Load
# =========================================================

for path in [
    HISTORICAL_COMPONENT_CSV,
    HISTORICAL_PACKAGE_CSV,
    HARD_CATALOG_CSV,
    SPLIT_CSV,
]:

    if not path.exists():

        raise FileNotFoundError(
            f"Missing: {path}"
        )


components = pd.read_csv(
    HISTORICAL_COMPONENT_CSV
)

packages = pd.read_csv(
    HISTORICAL_PACKAGE_CSV
)

hard = pd.read_csv(
    HARD_CATALOG_CSV
)

splits = pd.read_csv(
    SPLIT_CSV
)


components[
    "fresh_id"
] = components[
    "fresh_id"
].astype(str)

components[
    "version_id"
] = components[
    "version_id"
].astype(str)


packages[
    "fresh_id"
] = packages[
    "fresh_id"
].astype(str)

packages[
    "version_id"
] = packages[
    "version_id"
].astype(str)


hard[
    "fresh_id"
] = hard[
    "fresh_id"
].astype(str)

hard[
    "version_id"
] = hard[
    "version_id"
].astype(str)


splits[
    "fresh_id"
] = splits[
    "fresh_id"
].astype(str)


split_map = dict(
    zip(
        splits[
            "fresh_id"
        ],

        splits[
            "frozen_split"
        ],
    )
)


print(
    "======================================"
)

print(
    "Phase 6F - Historical Graph Audit"
)

print(
    "======================================"
)


# =========================================================
# Code nodes by historical release
# =========================================================

code_components = components[
    components[
        "modality"
    ]
    == "CODE_BINARY"
].copy()


code_paths_by_release = {}


for (
    fresh_id,
    version_id
), group in code_components.groupby(
    [
        "fresh_id",
        "version_id",
    ],
    sort=False,
):

    code_paths_by_release[
        (
            str(
                fresh_id
            ),
            str(
                version_id
            ),
        )
    ] = set(
        normalize_path(
            value
        )

        for value in group[
            "relative_path"
        ]
    )


# =========================================================
# Hard code nodes
# =========================================================

hard_code = hard[
    hard[
        "modality"
    ]
    == "CODE_BINARY"
].copy()


hard_paths_by_release = (
    defaultdict(
        set
    )
)

strict_paths_by_release = (
    defaultdict(
        set
    )
)


for row in hard_code.itertuples(
    index=False
):

    key = (
        clean_text(
            row.fresh_id
        ),
        clean_text(
            row.version_id
        ),
    )

    path = normalize_path(
        row.relative_path
    )


    hard_paths_by_release[
        key
    ].add(
        path
    )


    if as_bool(
        row.strict_path_failed_candidate
    ):

        strict_paths_by_release[
            key
        ].add(
            path
        )


# =========================================================
# Package selection
# =========================================================

query_packages = packages[
    packages[
        "fresh_id"
    ].map(
        split_map
    ).isin(
        QUERY_SPLITS
    )
].copy()


expected_query_releases = (
    90 * 3
)


print(
    "Target historical releases:",
    len(
        query_packages
    )
)


if (
    len(
        query_packages
    )
    != expected_query_releases
):

    print(
        "WARNING: expected",
        expected_query_releases,
        "but got",
        len(
            query_packages
        ),
    )


# =========================================================
# Main graph extraction
# =========================================================

edge_rows = []

release_rows = []

failure_rows = []


class_parse_failures = 0

missing_class_entries = 0

fatal_release_failures = 0

processed_releases = 0


for release_number, row in enumerate(
    query_packages.itertuples(
        index=False
    ),
    start=1,
):

    fresh_id = clean_text(
        row.fresh_id
    )

    version_id = clean_text(
        row.version_id
    )

    version_number = clean_text(
        row.version_number
    )

    split_name = clean_text(
        split_map.get(
            fresh_id,
            "",
        )
    )


    key = (
        fresh_id,
        version_id,
    )


    jar_path = Path(
        clean_text(
            row.local_path
        )
    )


    nodes = set(
        code_paths_by_release.get(
            key,
            set(),
        )
    )


    hard_nodes = set(
        hard_paths_by_release.get(
            key,
            set(),
        )
    )


    strict_nodes = set(
        strict_paths_by_release.get(
            key,
            set(),
        )
    )


    print(
        f"[{release_number}/"
        f"{len(query_packages)}] "
        f"{fresh_id} "
        f"{version_number} "
        f"code={len(nodes)} "
        f"hard={len(hard_nodes)} "
        f"strict={len(strict_nodes)}"
    )


    if not jar_path.exists():

        fatal_release_failures += 1

        failure_rows.append({
            "fresh_id":
                fresh_id,

            "version_id":
                version_id,

            "relative_path":
                "",

            "reason":
                "JAR_NOT_FOUND",

            "detail":
                str(
                    jar_path
                ),
        })

        continue


    # -----------------------------------------------------
    # Internal name mapping
    # -----------------------------------------------------

    internal_to_path = {}


    for path in nodes:

        if not path.endswith(
            ".class"
        ):

            continue


        internal_name = (
            path[:-6]
        )


        internal_to_path[
            internal_name
        ] = path


    edges = set()


    # -----------------------------------------------------
    # Read class constant pools
    # -----------------------------------------------------

    try:

        with zipfile.ZipFile(
            jar_path,
            "r",
        ) as jar:

            zip_names = set(
                jar.namelist()
            )


            for class_index, path in enumerate(
                sorted(
                    nodes
                ),
                start=1,
            ):

                if path not in zip_names:

                    missing_class_entries += 1

                    failure_rows.append({
                        "fresh_id":
                            fresh_id,

                        "version_id":
                            version_id,

                        "relative_path":
                            path,

                        "reason":
                            "CLASS_ENTRY_NOT_FOUND",

                        "detail":
                            "",
                    })

                    continue


                try:

                    raw = jar.read(
                        path
                    )


                    refs = (
                        parse_constant_pool_class_refs(
                            raw
                        )
                    )


                except Exception as exc:

                    class_parse_failures += 1

                    failure_rows.append({
                        "fresh_id":
                            fresh_id,

                        "version_id":
                            version_id,

                        "relative_path":
                            path,

                        "reason":
                            "CLASS_PARSE_FAILED",

                        "detail":
                            repr(
                                exc
                            ),
                    })

                    continue


                for ref in refs:

                    target_path = (
                        internal_to_path.get(
                            ref
                        )
                    )


                    if not target_path:

                        continue


                    if target_path == path:

                        continue


                    edges.add(
                        (
                            path,
                            target_path,
                        )
                    )


    except Exception as exc:

        fatal_release_failures += 1

        failure_rows.append({
            "fresh_id":
                fresh_id,

            "version_id":
                version_id,

            "relative_path":
                "",

            "reason":
                "JAR_OPEN_FAILED",

            "detail":
                repr(
                    exc
                ),
        })

        continue


    # -----------------------------------------------------
    # Connected components
    # -----------------------------------------------------

    components_list = (
        connected_components(
            nodes,
            edges,
        )
    )


    largest_component_size = (
        max(
            (
                len(component)
                for component
                in components_list
            ),
            default=0,
        )
    )


    largest_component_rate = (
        largest_component_size
        / len(nodes)

        if nodes
        else 0.0
    )


    max_hard_in_component = 0

    max_strict_in_component = 0

    best_hard_component_size = 0

    best_hard_connector_count = 0


    for component in (
        components_list
    ):

        hard_count = len(
            component
            &
            hard_nodes
        )

        strict_count = len(
            component
            &
            strict_nodes
        )


        if (
            hard_count
            > max_hard_in_component
        ):

            max_hard_in_component = (
                hard_count
            )

            best_hard_component_size = (
                len(
                    component
                )
            )

            best_hard_connector_count = (
                len(
                    component
                )
                - hard_count
            )


        max_strict_in_component = max(
            max_strict_in_component,
            strict_count,
        )


    hard_coverage = (
        max_hard_in_component
        / len(
            hard_nodes
        )

        if hard_nodes
        else 0.0
    )


    strict_coverage = (
        max_strict_in_component
        / len(
            strict_nodes
        )

        if strict_nodes
        else 0.0
    )


    release_rows.append({
        "fresh_id":
            fresh_id,

        "frozen_split":
            split_name,

        "version_id":
            version_id,

        "version_number":
            version_number,

        "jar_filename":
            clean_text(
                row.filename
            ),

        "code_nodes":
            int(
                len(
                    nodes
                )
            ),

        "class_ref_edges":
            int(
                len(
                    edges
                )
            ),

        "connected_components":
            int(
                len(
                    components_list
                )
            ),

        "largest_component_size":
            int(
                largest_component_size
            ),

        "largest_component_rate":
            float(
                largest_component_rate
            ),

        "hard_code_nodes":
            int(
                len(
                    hard_nodes
                )
            ),

        "strict_code_nodes":
            int(
                len(
                    strict_nodes
                )
            ),

        "max_hard_in_one_component":
            int(
                max_hard_in_component
            ),

        "max_strict_in_one_component":
            int(
                max_strict_in_component
            ),

        "hard_coverage_by_best_component":
            float(
                hard_coverage
            ),

        "strict_coverage_by_best_component":
            float(
                strict_coverage
            ),

        "best_hard_component_size":
            int(
                best_hard_component_size
            ),

        "best_hard_connector_count":
            int(
                best_hard_connector_count
            ),

        "eligible_hard_h3":
            bool(
                max_hard_in_component
                >= 3
            ),

        "eligible_hard_h5":
            bool(
                max_hard_in_component
                >= 5
            ),

        "eligible_hard_h10":
            bool(
                max_hard_in_component
                >= 10
            ),

        "eligible_strict_h3":
            bool(
                max_strict_in_component
                >= 3
            ),

        "eligible_strict_h5":
            bool(
                max_strict_in_component
                >= 5
            ),
    })


    # -----------------------------------------------------
    # Save directed intra-JAR edges
    # -----------------------------------------------------

    for source, target in sorted(
        edges
    ):

        edge_rows.append({
            "fresh_id":
                fresh_id,

            "frozen_split":
                split_name,

            "version_id":
                version_id,

            "version_number":
                version_number,

            "source_path":
                source,

            "target_path":
                target,

            "edge_type":
                "CLASS_REF",
        })


    processed_releases += 1


# =========================================================
# Save CSV
# =========================================================

edge_columns = [
    "fresh_id",
    "frozen_split",
    "version_id",
    "version_number",
    "source_path",
    "target_path",
    "edge_type",
]


release_columns = [
    "fresh_id",
    "frozen_split",
    "version_id",
    "version_number",
    "jar_filename",
    "code_nodes",
    "class_ref_edges",
    "connected_components",
    "largest_component_size",
    "largest_component_rate",
    "hard_code_nodes",
    "strict_code_nodes",
    "max_hard_in_one_component",
    "max_strict_in_one_component",
    "hard_coverage_by_best_component",
    "strict_coverage_by_best_component",
    "best_hard_component_size",
    "best_hard_connector_count",
    "eligible_hard_h3",
    "eligible_hard_h5",
    "eligible_hard_h10",
    "eligible_strict_h3",
    "eligible_strict_h5",
]


edge_df = pd.DataFrame(
    edge_rows,
    columns=edge_columns,
)

release_df = pd.DataFrame(
    release_rows,
    columns=release_columns,
)


edge_df.to_csv(
    OUTPUT_EDGE_CSV,
    index=False,
    encoding="utf-8-sig",
)

release_df.to_csv(
    OUTPUT_RELEASE_CSV,
    index=False,
    encoding="utf-8-sig",
)


OUTPUT_FAILURE_JSON.write_text(
    json.dumps(
        failure_rows,
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)


# =========================================================
# Summary
# =========================================================

def split_summary(
    group
):

    return {
        "releases":
            int(
                len(
                    group
                )
            ),

        "projects":
            int(
                group[
                    "fresh_id"
                ].nunique()
            ),

        "code_nodes":
            int(
                group[
                    "code_nodes"
                ].sum()
            ),

        "class_ref_edges":
            int(
                group[
                    "class_ref_edges"
                ].sum()
            ),

        "hard_code_nodes":
            int(
                group[
                    "hard_code_nodes"
                ].sum()
            ),

        "strict_code_nodes":
            int(
                group[
                    "strict_code_nodes"
                ].sum()
            ),

        "releases_with_hard_code":
            int(
                (
                    group[
                        "hard_code_nodes"
                    ]
                    > 0
                ).sum()
            ),

        "projects_with_hard_code":
            int(
                group[
                    group[
                        "hard_code_nodes"
                    ]
                    > 0
                ][
                    "fresh_id"
                ].nunique()
            ),

        "hard_h3_releases":
            int(
                group[
                    "eligible_hard_h3"
                ].sum()
            ),

        "hard_h3_projects":
            int(
                group[
                    group[
                        "eligible_hard_h3"
                    ]
                ][
                    "fresh_id"
                ].nunique()
            ),

        "hard_h5_releases":
            int(
                group[
                    "eligible_hard_h5"
                ].sum()
            ),

        "hard_h5_projects":
            int(
                group[
                    group[
                        "eligible_hard_h5"
                    ]
                ][
                    "fresh_id"
                ].nunique()
            ),

        "hard_h10_releases":
            int(
                group[
                    "eligible_hard_h10"
                ].sum()
            ),

        "hard_h10_projects":
            int(
                group[
                    group[
                        "eligible_hard_h10"
                    ]
                ][
                    "fresh_id"
                ].nunique()
            ),

        "strict_h3_releases":
            int(
                group[
                    "eligible_strict_h3"
                ].sum()
            ),

        "strict_h3_projects":
            int(
                group[
                    group[
                        "eligible_strict_h3"
                    ]
                ][
                    "fresh_id"
                ].nunique()
            ),

        "strict_h5_releases":
            int(
                group[
                    "eligible_strict_h5"
                ].sum()
            ),

        "strict_h5_projects":
            int(
                group[
                    group[
                        "eligible_strict_h5"
                    ]
                ][
                    "fresh_id"
                ].nunique()
            ),

        "median_largest_component_rate":
            float(
                group[
                    "largest_component_rate"
                ].median()
            )
            if len(group)
            else 0.0,

        "median_hard_coverage_by_best_component":
            float(
                group[
                    group[
                        "hard_code_nodes"
                    ]
                    > 0
                ][
                    "hard_coverage_by_best_component"
                ].median()
            )
            if (
                group[
                    "hard_code_nodes"
                ]
                > 0
            ).any()
            else 0.0,

        "median_max_hard_in_one_component":
            float(
                group[
                    group[
                        "hard_code_nodes"
                    ]
                    > 0
                ][
                    "max_hard_in_one_component"
                ].median()
            )
            if (
                group[
                    "hard_code_nodes"
                ]
                > 0
            ).any()
            else 0.0,
    }


by_split = {}


for split_name, group in (
    release_df.groupby(
        "frozen_split"
    )
):

    by_split[
        str(
            split_name
        )
    ] = split_summary(
        group
    )


summary = {
    "graph_audit_frozen":
        True,

    "graph_definition":
        (
            "intra-JAR Java class dependency graph "
            "from CONSTANT_Class references; "
            "connectivity treated as undirected"
        ),

    "query_splits": sorted(
        QUERY_SPLITS
    ),

    "expected_target_historical_releases":
        int(
            expected_query_releases
        ),

    "processed_releases":
        int(
            processed_releases
        ),

    "release_rows":
        int(
            len(
                release_df
            )
        ),

    "total_code_nodes":
        int(
            release_df[
                "code_nodes"
            ].sum()
        )
        if len(
            release_df
        )
        else 0,

    "total_class_ref_edges":
        int(
            release_df[
                "class_ref_edges"
            ].sum()
        )
        if len(
            release_df
        )
        else 0,

    "total_hard_code_nodes":
        int(
            release_df[
                "hard_code_nodes"
            ].sum()
        )
        if len(
            release_df
        )
        else 0,

    "total_strict_code_nodes":
        int(
            release_df[
                "strict_code_nodes"
            ].sum()
        )
        if len(
            release_df
        )
        else 0,

    "class_parse_failures":
        int(
            class_parse_failures
        ),

    "missing_class_entries":
        int(
            missing_class_entries
        ),

    "fatal_release_failures":
        int(
            fatal_release_failures
        ),

    "failure_records":
        int(
            len(
                failure_rows
            )
        ),

    "by_split":
        by_split,

    "goals_met":
        bool(
            processed_releases
            == expected_query_releases

            and
            len(
                release_df
            )
            == expected_query_releases

            and
            fatal_release_failures
            == 0

            and
            missing_class_entries
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
# Result
# =========================================================

print()

print(
    "======================================"
)

print(
    "PHASE 6F RESULT"
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
    "Edges   :",
    OUTPUT_EDGE_CSV
)

print(
    "Releases:",
    OUTPUT_RELEASE_CSV
)

print(
    "Failures:",
    OUTPUT_FAILURE_JSON
)

print(
    "Summary :",
    OUTPUT_SUMMARY_JSON
)