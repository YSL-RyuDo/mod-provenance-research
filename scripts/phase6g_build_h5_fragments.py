import hashlib
import json
import statistics
from collections import defaultdict, deque
from pathlib import Path

import pandas as pd


# =========================================================
# Config
# =========================================================

SEED = 20260812

TARGETS_PER_FRAGMENT = 5

VARIANTS_PER_RELEASE = 3


HISTORICAL_COMPONENT_CSV = Path(
    "data/fresh_registry/"
    "fresh_historical_component_registry_filtered.csv"
)

HARD_CATALOG_CSV = Path(
    "results/"
    "phase6e_hard_candidate_catalog.csv"
)

EDGE_CSV = Path(
    "results/"
    "phase6f_historical_code_edges.csv"
)

RELEASE_STATS_CSV = Path(
    "results/"
    "phase6f_historical_graph_release_stats.csv"
)

SPLIT_CSV = Path(
    "results/"
    "phase6c_project_split.csv"
)


OUTPUT_NODE_CSV = Path(
    "results/"
    "phase6g_h5_fragment_catalog.csv"
)

OUTPUT_EDGE_CSV = Path(
    "results/"
    "phase6g_h5_fragment_edges.csv"
)

OUTPUT_FAILURE_JSON = Path(
    "results/"
    "phase6g_fragment_failures.json"
)

OUTPUT_SUMMARY_JSON = Path(
    "results/"
    "phase6g_fragment_summary.json"
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

    return (
        str(value)
        .strip()
        .lower()
        in {
            "1",
            "true",
            "yes",
            "y",
        }
    )


def stable_digest(text):

    return hashlib.sha256(
        text.encode(
            "utf-8"
        )
    ).hexdigest()


def stable_order(
    values,
    salt,
):

    return sorted(
        values,
        key=lambda value: (
            stable_digest(
                f"{SEED}|"
                f"{salt}|"
                f"{value}"
            ),
            value,
        ),
    )


# =========================================================
# Connected components
# =========================================================

def build_adjacency(
    nodes,
    directed_edges,
):

    adjacency = {
        node: set()
        for node in nodes
    }


    for source, target in (
        directed_edges
    ):

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


    return adjacency


def connected_components(
    adjacency
):

    visited = set()

    result = []


    for start in sorted(
        adjacency
    ):

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


            for neighbor in sorted(
                adjacency[
                    node
                ]
            ):

                if (
                    neighbor
                    in visited
                ):

                    continue


                visited.add(
                    neighbor
                )

                queue.append(
                    neighbor
                )


        result.append(
            component
        )


    return result


# =========================================================
# Compact fragment construction
# =========================================================

def nearest_hard_path(
    adjacency,
    fragment_nodes,
    remaining_targets,
    salt,
):

    # -----------------------------------------------------
    # A hard node may already have become a connector
    # while connecting previous targets.
    #
    # In that case promote it to TARGET at zero extra cost.
    # -----------------------------------------------------

    embedded = (
        set(
            remaining_targets
        )
        &
        set(
            fragment_nodes
        )
    )


    if embedded:

        chosen = stable_order(
            embedded,
            salt + "|embedded",
        )[0]


        return [
            chosen
        ]


    # -----------------------------------------------------
    # Multi-source BFS from current fragment.
    # -----------------------------------------------------

    queue = deque()

    previous = {}

    distance = {}


    for source in sorted(
        fragment_nodes
    ):

        queue.append(
            source
        )

        previous[
            source
        ] = None

        distance[
            source
        ] = 0


    found = []

    found_distance = None


    while queue:

        node = (
            queue.popleft()
        )

        node_distance = (
            distance[
                node
            ]
        )


        if (
            found_distance is not None
            and
            node_distance
            > found_distance
        ):

            break


        if (
            node in remaining_targets
            and
            node not in fragment_nodes
        ):

            found.append(
                node
            )

            found_distance = (
                node_distance
            )

            continue


        for neighbor in sorted(
            adjacency.get(
                node,
                set(),
            )
        ):

            if neighbor in distance:
                continue


            previous[
                neighbor
            ] = node

            distance[
                neighbor
            ] = (
                node_distance
                + 1
            )

            queue.append(
                neighbor
            )


    if not found:

        return None


    chosen = stable_order(
        found,
        salt + "|nearest",
    )[0]


    # -----------------------------------------------------
    # Reconstruct shortest path back to any existing
    # fragment node.
    # -----------------------------------------------------

    reverse_path = []

    cursor = chosen


    while cursor is not None:

        reverse_path.append(
            cursor
        )


        if (
            cursor
            in fragment_nodes
        ):

            break


        cursor = previous.get(
            cursor
        )


    reverse_path.reverse()


    if not reverse_path:

        return None


    return reverse_path


def build_fragment(
    fresh_id,
    version_id,
    nodes,
    directed_edges,
    hard_nodes,
    strict_nodes,
    variant_index,
):

    adjacency = (
        build_adjacency(
            nodes,
            directed_edges,
        )
    )


    components = (
        connected_components(
            adjacency
        )
    )


    if not components:

        return None


    # -----------------------------------------------------
    # Select component containing the largest number
    # of HARD_MASKED nodes.
    #
    # Tie:
    #   smaller component preferred,
    #   then deterministic lexical identity.
    # -----------------------------------------------------

    component_records = []


    for component in (
        components
    ):

        hard_count = len(
            component
            &
            hard_nodes
        )


        component_records.append(
            (
                hard_count,
                -len(component),
                min(component)
                if component
                else "",
                component,
            )
        )


    component_records.sort(
        key=lambda item: (
            -item[0],
            -item[1],
            item[2],
        )
    )


    best_component = (
        component_records[
            0
        ][
            3
        ]
    )


    candidates = (
        best_component
        &
        hard_nodes
    )


    if (
        len(candidates)
        < TARGETS_PER_FRAGMENT
    ):

        return None


    salt = (
        f"{fresh_id}|"
        f"{version_id}|"
        f"variant={variant_index}"
    )


    ordered_candidates = stable_order(
        candidates,
        salt + "|anchor",
    )


    anchor = (
        ordered_candidates[
            0
        ]
    )


    selected_targets = {
        anchor
    }

    fragment_nodes = {
        anchor
    }


    while (
        len(
            selected_targets
        )
        < TARGETS_PER_FRAGMENT
    ):

        remaining = (
            candidates
            -
            selected_targets
        )


        path = nearest_hard_path(
            adjacency,
            fragment_nodes,
            remaining,
            (
                salt
                +
                f"|step="
                f"{len(selected_targets)}"
            ),
        )


        if not path:

            return None


        target = (
            path[
                -1
            ]
        )


        fragment_nodes.update(
            path
        )

        selected_targets.add(
            target
        )


    # -----------------------------------------------------
    # Keep exactly five evaluation TARGET nodes.
    #
    # Other hard nodes encountered on shortest paths are
    # CONNECTOR nodes and are NOT evaluated.
    # -----------------------------------------------------

    if (
        len(
            selected_targets
        )
        != TARGETS_PER_FRAGMENT
    ):

        raise RuntimeError(
            "Target count invariant violated"
        )


    connector_nodes = (
        fragment_nodes
        -
        selected_targets
    )


    # -----------------------------------------------------
    # Preserve original directed CLASS_REF edges only
    # inside the selected fragment.
    # -----------------------------------------------------

    fragment_edges = set()


    for source, target in (
        directed_edges
    ):

        if (
            source in fragment_nodes
            and
            target in fragment_nodes
        ):

            fragment_edges.add(
                (
                    source,
                    target,
                )
            )


    strict_target_count = len(
        selected_targets
        &
        strict_nodes
    )


    return {
        "targets":
            set(
                selected_targets
            ),

        "connectors":
            set(
                connector_nodes
            ),

        "nodes":
            set(
                fragment_nodes
            ),

        "edges":
            set(
                fragment_edges
            ),

        "strict_target_count":
            int(
                strict_target_count
            ),

        "best_component_size":
            int(
                len(
                    best_component
                )
            ),

        "best_component_hard_nodes":
            int(
                len(
                    candidates
                )
            ),
    }


# =========================================================
# Load
# =========================================================

for path in [
    HISTORICAL_COMPONENT_CSV,
    HARD_CATALOG_CSV,
    EDGE_CSV,
    RELEASE_STATS_CSV,
    SPLIT_CSV,
]:

    if not path.exists():

        raise FileNotFoundError(
            f"Missing: {path}"
        )


historical = pd.read_csv(
    HISTORICAL_COMPONENT_CSV
)

hard = pd.read_csv(
    HARD_CATALOG_CSV
)

edges = pd.read_csv(
    EDGE_CSV
)

release_stats = pd.read_csv(
    RELEASE_STATS_CSV
)

splits = pd.read_csv(
    SPLIT_CSV
)


for df in [
    historical,
    hard,
    edges,
    release_stats,
    splits,
]:

    if "fresh_id" in df.columns:

        df[
            "fresh_id"
        ] = df[
            "fresh_id"
        ].astype(str)


for df in [
    historical,
    hard,
    edges,
    release_stats,
]:

    if "version_id" in df.columns:

        df[
            "version_id"
        ] = df[
            "version_id"
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
    "Phase 6G - H5 Fragment Catalog"
)

print(
    "======================================"
)


# =========================================================
# Eligible releases
# =========================================================

release_stats[
    "eligible_hard_h5_bool"
] = release_stats[
    "eligible_hard_h5"
].map(
    as_bool
)


eligible = release_stats[
    release_stats[
        "eligible_hard_h5_bool"
    ]
].copy()


eligible = eligible[
    eligible[
        "frozen_split"
    ].isin(
        QUERY_SPLITS
    )
].copy()


print(
    "Eligible H5 releases:",
    len(
        eligible
    )
)

print(
    "Eligible H5 projects:",
    eligible[
        "fresh_id"
    ].nunique()
)


# =========================================================
# Historical code node registry
# =========================================================

historical_code = historical[
    historical[
        "modality"
    ]
    == "CODE_BINARY"
].copy()


nodes_by_release = {}


for (
    fresh_id,
    version_id
), group in (
    historical_code.groupby(
        [
            "fresh_id",
            "version_id",
        ],
        sort=False,
    )
):

    key = (
        str(
            fresh_id
        ),
        str(
            version_id
        ),
    )


    nodes_by_release[
        key
    ] = set(
        normalize_path(
            value
        )

        for value in group[
            "relative_path"
        ]
    )


# =========================================================
# Hard node registry
# =========================================================

hard_code = hard[
    hard[
        "modality"
    ]
    == "CODE_BINARY"
].copy()


hard_by_release = (
    defaultdict(
        set
    )
)

strict_by_release = (
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


    hard_by_release[
        key
    ].add(
        path
    )


    if as_bool(
        row.strict_path_failed_candidate
    ):

        strict_by_release[
            key
        ].add(
            path
        )


# =========================================================
# Edge registry
# =========================================================

edges_by_release = (
    defaultdict(
        set
    )
)


for row in edges.itertuples(
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


    source = normalize_path(
        row.source_path
    )

    target = normalize_path(
        row.target_path
    )


    if (
        not source
        or
        not target
    ):

        continue


    edges_by_release[
        key
    ].add(
        (
            source,
            target,
        )
    )


# =========================================================
# Component SHA lookup
# =========================================================

component_sha = {}


for row in historical_code.itertuples(
    index=False
):

    key = (
        clean_text(
            row.fresh_id
        ),
        clean_text(
            row.version_id
        ),
        normalize_path(
            row.relative_path
        ),
    )


    component_sha[
        key
    ] = clean_text(
        row.component_sha256
    )


# =========================================================
# Generate fragment variants
# =========================================================

fragment_node_rows = []

fragment_edge_rows = []

fragment_records = []

failures = []


fragment_counter = 0


for release_number, row in enumerate(
    eligible.itertuples(
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
        row.frozen_split
    )


    key = (
        fresh_id,
        version_id,
    )


    nodes = set(
        nodes_by_release.get(
            key,
            set(),
        )
    )

    hard_nodes = set(
        hard_by_release.get(
            key,
            set(),
        )
    )

    strict_nodes = set(
        strict_by_release.get(
            key,
            set(),
        )
    )

    directed_edges = set(
        edges_by_release.get(
            key,
            set(),
        )
    )


    print(
        f"[{release_number}/"
        f"{len(eligible)}] "
        f"{fresh_id} "
        f"{version_number} "
        f"nodes={len(nodes)} "
        f"hard={len(hard_nodes)}"
    )


    if (
        len(
            hard_nodes
        )
        < TARGETS_PER_FRAGMENT
    ):

        failures.append({
            "fresh_id":
                fresh_id,

            "version_id":
                version_id,

            "reason":
                "INSUFFICIENT_HARD_NODES",

            "hard_nodes":
                len(
                    hard_nodes
                ),
        })

        continue


    # -----------------------------------------------------
    # Deduplicate variants which happen to select the
    # exact same node/target set.
    # -----------------------------------------------------

    signatures = set()


    for variant_index in range(
        VARIANTS_PER_RELEASE
    ):

        fragment = build_fragment(
            fresh_id,
            version_id,
            nodes,
            directed_edges,
            hard_nodes,
            strict_nodes,
            variant_index,
        )


        if fragment is None:

            failures.append({
                "fresh_id":
                    fresh_id,

                "version_id":
                    version_id,

                "variant_index":
                    variant_index,

                "reason":
                    "FRAGMENT_BUILD_FAILED",
            })

            continue


        signature_source = (
            "|".join(
                sorted(
                    fragment[
                        "targets"
                    ]
                )
            )
            +
            "||"
            +
            "|".join(
                sorted(
                    fragment[
                        "nodes"
                    ]
                )
            )
        )


        signature = stable_digest(
            signature_source
        )


        if signature in signatures:

            continue


        signatures.add(
            signature
        )


        fragment_counter += 1


        fragment_id = (
            f"F6G"
            f"{fragment_counter:06d}"
        )


        # -------------------------------------------------
        # Local anonymous node IDs.
        # -------------------------------------------------

        ordered_nodes = stable_order(
            fragment[
                "nodes"
            ],
            (
                f"{fresh_id}|"
                f"{version_id}|"
                f"{fragment_id}|"
                "node-order"
            ),
        )


        anon_map = {
            path:
                (
                    f"{fragment_id}_"
                    f"N{index:04d}"
                )

            for index, path
            in enumerate(
                ordered_nodes,
                start=1,
            )
        }


        for path in (
            ordered_nodes
        ):

            evaluation_role = (
                "TARGET"

                if path
                in fragment[
                    "targets"
                ]

                else
                "CONNECTOR"
            )


            is_strict = (
                path
                in strict_nodes
            )


            sha = component_sha.get(
                (
                    fresh_id,
                    version_id,
                    path,
                ),
                "",
            )


            fragment_node_rows.append({
                "fragment_id":
                    fragment_id,

                "fresh_id":
                    fresh_id,

                "frozen_split":
                    split_name,

                "version_id":
                    version_id,

                "version_number":
                    version_number,

                "variant_index":
                    int(
                        variant_index
                    ),

                "node_id":
                    anon_map[
                        path
                    ],

                "evaluation_role":
                    evaluation_role,

                "strict_path_failed":
                    bool(
                        is_strict
                    ),

                # PRIVATE SOURCE LOCATION.
                #
                # Do not expose this path to the final
                # attribution method.
                "source_relative_path":
                    path,

                "component_sha256":
                    sha,
            })


        for source, target in sorted(
            fragment[
                "edges"
            ]
        ):

            fragment_edge_rows.append({
                "fragment_id":
                    fragment_id,

                "fresh_id":
                    fresh_id,

                "frozen_split":
                    split_name,

                "version_id":
                    version_id,

                "version_number":
                    version_number,

                "source_node_id":
                    anon_map[
                        source
                    ],

                "target_node_id":
                    anon_map[
                        target
                    ],

                "edge_type":
                    "CLASS_REF",
            })


        record = {
            "fragment_id":
                fragment_id,

            "fresh_id":
                fresh_id,

            "frozen_split":
                split_name,

            "version_id":
                version_id,

            "version_number":
                version_number,

            "variant_index":
                int(
                    variant_index
                ),

            "target_nodes":
                int(
                    len(
                        fragment[
                            "targets"
                        ]
                    )
                ),

            "connector_nodes":
                int(
                    len(
                        fragment[
                            "connectors"
                        ]
                    )
                ),

            "total_nodes":
                int(
                    len(
                        fragment[
                            "nodes"
                        ]
                    )
                ),

            "fragment_edges":
                int(
                    len(
                        fragment[
                            "edges"
                        ]
                    )
                ),

            "strict_target_nodes":
                int(
                    fragment[
                        "strict_target_count"
                    ]
                ),

            "best_component_size":
                int(
                    fragment[
                        "best_component_size"
                    ]
                ),

            "best_component_hard_nodes":
                int(
                    fragment[
                        "best_component_hard_nodes"
                    ]
                ),
        }


        fragment_records.append(
            record
        )


# =========================================================
# DataFrames
# =========================================================

node_df = pd.DataFrame(
    fragment_node_rows
)

edge_df = pd.DataFrame(
    fragment_edge_rows
)

fragment_df = pd.DataFrame(
    fragment_records
)


node_df.to_csv(
    OUTPUT_NODE_CSV,
    index=False,
    encoding="utf-8-sig",
)

edge_df.to_csv(
    OUTPUT_EDGE_CSV,
    index=False,
    encoding="utf-8-sig",
)


OUTPUT_FAILURE_JSON.write_text(
    json.dumps(
        failures,
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)


# =========================================================
# Summary helpers
# =========================================================

def percentile(
    values,
    percent
):

    if not values:
        return 0.0


    ordered = sorted(
        values
    )


    if len(ordered) == 1:

        return float(
            ordered[
                0
            ]
        )


    position = (
        (
            len(ordered)
            - 1
        )
        *
        percent
    )


    lower = int(
        position
    )

    upper = min(
        lower + 1,
        len(ordered) - 1,
    )


    fraction = (
        position
        - lower
    )


    return float(
        ordered[
            lower
        ]
        *
        (
            1.0
            - fraction
        )
        +
        ordered[
            upper
        ]
        *
        fraction
    )


def summarize_fragments(
    group
):

    connector_counts = (
        group[
            "connector_nodes"
        ]
        .astype(int)
        .tolist()
    )

    total_counts = (
        group[
            "total_nodes"
        ]
        .astype(int)
        .tolist()
    )


    return {
        "fragments":
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

        "releases":
            int(
                group[
                    [
                        "fresh_id",
                        "version_id",
                    ]
                ]
                .drop_duplicates()
                .shape[
                    0
                ]
            ),

        "target_nodes":
            int(
                group[
                    "target_nodes"
                ].sum()
            ),

        "strict_target_nodes":
            int(
                group[
                    "strict_target_nodes"
                ].sum()
            ),

        "median_connectors":
            float(
                statistics.median(
                    connector_counts
                )
            )
            if connector_counts
            else 0.0,

        "p95_connectors":
            percentile(
                connector_counts,
                0.95,
            ),

        "max_connectors":
            int(
                max(
                    connector_counts
                )
            )
            if connector_counts
            else 0,

        "median_total_nodes":
            float(
                statistics.median(
                    total_counts
                )
            )
            if total_counts
            else 0.0,

        "p95_total_nodes":
            percentile(
                total_counts,
                0.95,
            ),

        "max_total_nodes":
            int(
                max(
                    total_counts
                )
            )
            if total_counts
            else 0,
    }


# =========================================================
# Split summary
# =========================================================

by_split = {}


if len(
    fragment_df
):

    for split_name, group in (
        fragment_df.groupby(
            "frozen_split"
        )
    ):

        by_split[
            str(
                split_name
            )
        ] = summarize_fragments(
            group
        )


# =========================================================
# Project coverage
# =========================================================

project_coverage = {}


for split_name in sorted(
    QUERY_SPLITS
):

    eligible_split = eligible[
        eligible[
            "frozen_split"
        ]
        == split_name
    ]


    generated_split = (
        fragment_df[
            fragment_df[
                "frozen_split"
            ]
            == split_name
        ]

        if len(
            fragment_df
        )

        else pd.DataFrame()
    )


    eligible_projects = set(
        eligible_split[
            "fresh_id"
        ].astype(str)
    )


    generated_projects = (
        set(
            generated_split[
                "fresh_id"
            ].astype(str)
        )

        if len(
            generated_split
        )

        else set()
    )


    project_coverage[
        split_name
    ] = {
        "eligible_h5_projects":
            int(
                len(
                    eligible_projects
                )
            ),

        "projects_with_generated_fragments":
            int(
                len(
                    generated_projects
                )
            ),

        "missing_projects":
            sorted(
                eligible_projects
                -
                generated_projects
            ),
    }


# =========================================================
# Summary
# =========================================================

calibration_projects = (
    project_coverage.get(
        "CALIBRATION_KNOWN",
        {},
    ).get(
        "projects_with_generated_fragments",
        0,
    )
)

test_projects = (
    project_coverage.get(
        "TEST_KNOWN",
        {},
    ).get(
        "projects_with_generated_fragments",
        0,
    )
)

unknown_projects = (
    project_coverage.get(
        "UNKNOWN_HELDOUT",
        {},
    ).get(
        "projects_with_generated_fragments",
        0,
    )
)


summary = {
    "fragment_catalog_frozen":
        True,

    "random_seed":
        SEED,

    "targets_per_fragment":
        TARGETS_PER_FRAGMENT,

    "variants_per_release_requested":
        VARIANTS_PER_RELEASE,

    "fragment_definition":
        (
            "five HARD_MASKED CODE_BINARY target "
            "components connected through the original "
            "historical intra-JAR CLASS_REF graph; "
            "additional shortest-path nodes are topology-"
            "only connectors and are excluded from "
            "attribution accuracy"
        ),

    "strict_path_failed_role":
        (
            "secondary diagnostic only; "
            "not the primary fragment eligibility rule"
        ),

    "eligible_h5_releases":
        int(
            len(
                eligible
            )
        ),

    "eligible_h5_projects":
        int(
            eligible[
                "fresh_id"
            ].nunique()
        ),

    "generated_fragments":
        int(
            len(
                fragment_df
            )
        ),

    "fragment_nodes":
        int(
            len(
                node_df
            )
        ),

    "fragment_edges":
        int(
            len(
                edge_df
            )
        ),

    "failure_records":
        int(
            len(
                failures
            )
        ),

    "by_split":
        by_split,

    "project_coverage":
        project_coverage,

    "minimum_parent_project_goal":
        15,

    "goals_met":
        bool(
            calibration_projects
            >= 15

            and
            test_projects
            >= 15

            and
            unknown_projects
            >= 15
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
    "PHASE 6G RESULT"
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
    "Node catalog:",
    OUTPUT_NODE_CSV
)

print(
    "Edge catalog:",
    OUTPUT_EDGE_CSV
)

print(
    "Failures    :",
    OUTPUT_FAILURE_JSON
)

print(
    "Summary     :",
    OUTPUT_SUMMARY_JSON
)