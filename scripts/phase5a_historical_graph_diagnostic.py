import json
import struct
import zipfile
from collections import defaultdict, deque
from pathlib import Path

import pandas as pd


CURRENT_COMPONENTS = Path(
    "data/registry/release_component_registry.csv"
)

HISTORY_RESULTS = Path(
    "results/real_version_component_results.csv"
)

HISTORY_ROOT = Path(
    "data/historical_releases"
)

RESULT_ROOT = Path("results")
RESULT_ROOT.mkdir(exist_ok=True)


# =========================================================
# JVM constant pool
# =========================================================

def u1(data, pos):
    return data[pos], pos + 1


def u2(data, pos):
    return (
        struct.unpack_from(
            ">H",
            data,
            pos
        )[0],
        pos + 2
    )


def parse_class_refs(data):

    if len(data) < 10:
        return set()

    if data[:4] != b"\xca\xfe\xba\xbe":
        return set()

    pos = 4

    _, pos = u2(data, pos)
    _, pos = u2(data, pos)

    cp_count, pos = u2(
        data,
        pos
    )

    cp = [None] * cp_count

    i = 1

    try:

        while i < cp_count:

            tag, pos = u1(
                data,
                pos
            )

            if tag == 1:

                length, pos = u2(
                    data,
                    pos
                )

                raw = data[
                    pos:
                    pos + length
                ]

                pos += length

                cp[i] = (
                    "UTF8",
                    raw.decode(
                        "utf-8",
                        errors="replace"
                    )
                )

            elif tag in (3, 4):
                pos += 4

            elif tag in (5, 6):
                pos += 8
                i += 1

            elif tag == 7:

                name_index, pos = u2(
                    data,
                    pos
                )

                cp[i] = (
                    "CLASS",
                    name_index
                )

            elif tag in (
                8, 16, 19, 20
            ):
                pos += 2

            elif tag in (
                9, 10, 11,
                12, 17, 18
            ):
                pos += 4

            elif tag == 15:
                pos += 3

            else:
                return set()

            i += 1

    except Exception:
        return set()


    refs = set()

    for entry in cp:

        if not entry:
            continue

        if entry[0] != "CLASS":
            continue

        name_index = entry[1]

        if (
            name_index <= 0
            or
            name_index >= len(cp)
        ):
            continue

        value = cp[name_index]

        if (
            not value
            or
            value[0] != "UTF8"
        ):
            continue

        name = value[1]

        if name.startswith("["):
            continue

        refs.add(
            name + ".class"
        )

    return refs


# =========================================================
# Graph helpers
# =========================================================

def connected_components(
    nodes,
    edges
):

    adjacency = defaultdict(set)

    for a, b in edges:

        adjacency[a].add(b)
        adjacency[b].add(a)

    visited = set()
    components = []

    for node in nodes:

        if node in visited:
            continue

        queue = deque([node])

        visited.add(node)

        component = set()

        while queue:

            current = (
                queue.popleft()
            )

            component.add(
                current
            )

            for nxt in (
                adjacency.get(
                    current,
                    set()
                )
            ):

                if nxt in visited:
                    continue

                visited.add(nxt)
                queue.append(nxt)

        components.append(
            component
        )

    components.sort(
        key=len,
        reverse=True
    )

    return components


def find_jar(
    mod_id,
    version_id
):

    directory = (
        HISTORY_ROOT
        / str(mod_id)
        / str(version_id)
    )

    jars = list(
        directory.glob("*.jar")
    )

    if not jars:
        return None

    return jars[0]


# =========================================================
# Load
# =========================================================

current = pd.read_csv(
    CURRENT_COMPONENTS
)

history = pd.read_csv(
    HISTORY_RESULTS
)


# =========================================================
# Current full-path index
# Reconstruct Phase 3B hard criterion
# =========================================================

path_index = defaultdict(set)

for _, row in current.iterrows():

    path = str(
        row["relative_path"]
    ).replace(
        "\\",
        "/"
    ).lower()

    path_index[path].add(
        row["mod_id"]
    )


history_code = history[
    history["modality"]
    == "CODE_BINARY"
].copy()


history_code[
    "path_failed"
] = False


for idx, row in (
    history_code.iterrows()
):

    path = str(
        row["relative_path"]
    ).replace(
        "\\",
        "/"
    ).lower()

    candidates = (
        path_index.get(
            path,
            set()
        )
    )

    true_mod = row["mod_id"]

    unique_correct = (
        len(candidates) == 1
        and
        true_mod in candidates
    )

    history_code.at[
        idx,
        "path_failed"
    ] = not unique_correct


# =========================================================
# Process each historical release
# =========================================================

rows = []
failures = []


groups = history_code.groupby(
    [
        "mod_id",
        "historical_version_id",
    ],
    sort=False,
)


print(
    "======================================"
)
print(
    "Phase 5A - Historical Graph Diagnostic"
)
print(
    "======================================"
)

print(
    f"Historical release groups: "
    f"{len(groups)}"
)


for group_index, (
    (
        mod_id,
        version_id
    ),
    group
) in enumerate(
    groups,
    start=1
):

    version_number = (
        group[
            "historical_version"
        ].iloc[0]
    )

    jar_path = find_jar(
        mod_id,
        version_id
    )


    print()
    print(
        f"[{group_index}/"
        f"{len(groups)}] "
        f"{mod_id} "
        f"{version_number}"
    )


    if jar_path is None:

        failures.append({

            "mod_id":
                mod_id,

            "version_id":
                version_id,

            "reason":
                "jar_missing",
        })

        continue


    try:

        with zipfile.ZipFile(
            jar_path,
            "r"
        ) as jar:

            class_paths = {

                p.replace(
                    "\\",
                    "/"
                )

                for p in (
                    jar.namelist()
                )

                if (
                    p.lower()
                    .endswith(
                        ".class"
                    )
                    and
                    not p.lower()
                    .startswith(
                        "meta-inf/"
                    )
                )
            }


            edges = set()


            for class_path in (
                class_paths
            ):

                try:

                    refs = (
                        parse_class_refs(
                            jar.read(
                                class_path
                            )
                        )
                    )

                except Exception:
                    continue


                for target in refs:

                    if (
                        target
                        not in class_paths
                    ):
                        continue

                    if target == class_path:
                        continue


                    # undirected canonical edge
                    edge = tuple(
                        sorted(
                            (
                                class_path,
                                target
                            )
                        )
                    )

                    edges.add(edge)


    except Exception as e:

        failures.append({

            "mod_id":
                mod_id,

            "version_id":
                version_id,

            "reason":
                str(e),
        })

        continue


    # =====================================================
    # Hard nodes
    # =====================================================

    hard_nodes = set(

        str(x).replace(
            "\\",
            "/"
        )

        for x in group[
            group[
                "path_failed"
            ]
        ][
            "relative_path"
        ].tolist()

        if str(x).replace(
            "\\",
            "/"
        )
        in class_paths
    )


    all_components = (
        connected_components(
            class_paths,
            edges
        )
    )


    # -----------------------------------------------------
    # Largest full connected component
    # -----------------------------------------------------

    largest_full = (
        len(
            all_components[0]
        )
        if all_components
        else 0
    )


    # -----------------------------------------------------
    # How many hard nodes are contained
    # in one full connected component?
    # -----------------------------------------------------

    hard_counts_in_full = [

        len(
            component
            & hard_nodes
        )

        for component
        in all_components
    ]


    max_hard_in_full = (

        max(
            hard_counts_in_full
        )

        if hard_counts_in_full
        else 0
    )


    # -----------------------------------------------------
    # Induced hard graph
    # -----------------------------------------------------

    hard_edges = {

        edge

        for edge in edges

        if (
            edge[0]
            in hard_nodes
            and
            edge[1]
            in hard_nodes
        )
    }


    hard_components = (
        connected_components(
            hard_nodes,
            hard_edges
        )
        if hard_nodes
        else []
    )


    largest_hard_induced = (

        len(
            hard_components[0]
        )

        if hard_components
        else 0
    )


    hard_count = len(
        hard_nodes
    )


    rows.append({

        "mod_id":
            mod_id,

        "historical_version_id":
            version_id,

        "historical_version":
            version_number,

        "class_nodes":
            len(
                class_paths
            ),

        "class_edges":
            len(edges),

        "full_connected_components":
            len(
                all_components
            ),

        "largest_full_component":
            largest_full,

        "largest_full_component_rate":
            (
                largest_full
                / len(class_paths)

                if class_paths
                else 0
            ),

        "hard_path_failed_nodes":
            hard_count,

        "max_hard_nodes_in_one_full_component":
            max_hard_in_full,

        "hard_coverage_by_best_full_component":
            (
                max_hard_in_full
                / hard_count

                if hard_count
                else 0
            ),

        "hard_induced_edges":
            len(
                hard_edges
            ),

        "hard_induced_components":
            len(
                hard_components
            ),

        "largest_hard_induced_component":
            largest_hard_induced,

        "largest_hard_induced_rate":
            (
                largest_hard_induced
                / hard_count

                if hard_count
                else 0
            ),

        "eligible_5":
            (
                max_hard_in_full
                >= 5
            ),

        "eligible_10":
            (
                max_hard_in_full
                >= 10
            ),

        "eligible_20":
            (
                max_hard_in_full
                >= 20
            ),
    })


    print(
        f"classes={len(class_paths)} "
        f"edges={len(edges)} "
        f"hard={hard_count} "
        f"max-hard-connected="
        f"{max_hard_in_full}"
    )


# =========================================================
# Save
# =========================================================

results = pd.DataFrame(
    rows
)


results.to_csv(

    RESULT_ROOT
    / "historical_graph_diagnostic.csv",

    index=False,
    encoding="utf-8-sig",
)


# =========================================================
# Summary
# =========================================================

summary = {

    "historical_releases":
        len(results),

    "failures":
        len(failures),

    "releases_with_hard_nodes":
        int(
            (
                results[
                    "hard_path_failed_nodes"
                ]
                > 0
            ).sum()
        )
        if len(results)
        else 0,

    "total_hard_nodes":
        int(
            results[
                "hard_path_failed_nodes"
            ].sum()
        )
        if len(results)
        else 0,

    "eligible_connected_subgraph_5":
        int(
            results[
                "eligible_5"
            ].sum()
        )
        if len(results)
        else 0,

    "eligible_connected_subgraph_10":
        int(
            results[
                "eligible_10"
            ].sum()
        )
        if len(results)
        else 0,

    "eligible_connected_subgraph_20":
        int(
            results[
                "eligible_20"
            ].sum()
        )
        if len(results)
        else 0,

    "median_hard_nodes":
        float(
            results[
                results[
                    "hard_path_failed_nodes"
                ]
                > 0
            ][
                "hard_path_failed_nodes"
            ].median()
        )
        if (
            len(results)
            and
            (
                results[
                    "hard_path_failed_nodes"
                ]
                > 0
            ).any()
        )
        else 0,

    "median_max_hard_in_one_component":
        float(
            results[
                results[
                    "hard_path_failed_nodes"
                ]
                > 0
            ][
                "max_hard_nodes_in_one_full_component"
            ].median()
        )
        if (
            len(results)
            and
            (
                results[
                    "hard_path_failed_nodes"
                ]
                > 0
            ).any()
        )
        else 0,

    "median_hard_coverage_by_best_component":
        float(
            results[
                results[
                    "hard_path_failed_nodes"
                ]
                > 0
            ][
                "hard_coverage_by_best_full_component"
            ].median()
        )
        if (
            len(results)
            and
            (
                results[
                    "hard_path_failed_nodes"
                ]
                > 0
            ).any()
        )
        else 0,

    "median_largest_hard_induced_rate":
        float(
            results[
                results[
                    "hard_path_failed_nodes"
                ]
                > 0
            ][
                "largest_hard_induced_rate"
            ].median()
        )
        if (
            len(results)
            and
            (
                results[
                    "hard_path_failed_nodes"
                ]
                > 0
            ).any()
        )
        else 0,
}


(
    RESULT_ROOT
    / "phase5a_summary.json"
).write_text(

    json.dumps(
        summary,
        ensure_ascii=False,
        indent=2
    ),

    encoding="utf-8"
)


(
    RESULT_ROOT
    / "phase5a_failures.json"
).write_text(

    json.dumps(
        failures,
        ensure_ascii=False,
        indent=2
    ),

    encoding="utf-8"
)


print()
print(
    "======================================"
)
print("RESULT")
print(
    "======================================"
)

print(
    json.dumps(
        summary,
        ensure_ascii=False,
        indent=2
    )
)

print()
print(
    "Detailed: "
    "results\\historical_graph_diagnostic.csv"
)