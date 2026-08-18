import json
import struct
import zipfile
from collections import defaultdict, deque
from pathlib import Path

import pandas as pd


PACKAGE_REGISTRY = Path(
    "data/registry/release_package_registry.csv"
)

RELEASE_ROOT = Path(
    "data/release_packages"
)

REGISTRY_ROOT = Path(
    "data/registry"
)

RESULT_ROOT = Path("results")

REGISTRY_ROOT.mkdir(
    parents=True,
    exist_ok=True
)

RESULT_ROOT.mkdir(
    parents=True,
    exist_ok=True
)


# =========================================================
# JVM CLASS CONSTANT POOL PARSER
# =========================================================

def u1(data, pos):
    return data[pos], pos + 1


def u2(data, pos):
    return struct.unpack_from(
        ">H", data, pos
    )[0], pos + 2


def u4(data, pos):
    return struct.unpack_from(
        ">I", data, pos
    )[0], pos + 4


def parse_class_refs(data):

    if len(data) < 10:
        return set(), []

    if data[:4] != b"\xca\xfe\xba\xbe":
        return set(), []

    pos = 4

    # minor + major
    _, pos = u2(data, pos)
    _, pos = u2(data, pos)

    cp_count, pos = u2(
        data, pos
    )

    cp = [None] * cp_count

    utf8_values = []

    i = 1

    while i < cp_count:

        tag, pos = u1(
            data, pos
        )

        # UTF8
        if tag == 1:

            length, pos = u2(
                data, pos
            )

            raw = data[
                pos:pos + length
            ]

            pos += length

            text = raw.decode(
                "utf-8",
                errors="replace"
            )

            cp[i] = (
                "UTF8",
                text
            )

            utf8_values.append(
                text
            )

        # Integer / Float
        elif tag in (3, 4):

            pos += 4

        # Long / Double
        elif tag in (5, 6):

            pos += 8

            i += 1

        # Class
        elif tag == 7:

            name_index, pos = u2(
                data, pos
            )

            cp[i] = (
                "CLASS",
                name_index
            )

        # String
        elif tag == 8:

            pos += 2

        # Fieldref / Methodref /
        # InterfaceMethodref
        elif tag in (9, 10, 11):

            pos += 4

        # NameAndType
        elif tag == 12:

            pos += 4

        # MethodHandle
        elif tag == 15:

            pos += 3

        # MethodType
        elif tag == 16:

            pos += 2

        # Dynamic / InvokeDynamic
        elif tag in (17, 18):

            pos += 4

        # Module / Package
        elif tag in (19, 20):

            pos += 2

        else:

            raise ValueError(
                f"Unknown constant "
                f"pool tag: {tag}"
            )

        i += 1


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

        name_entry = cp[
            name_index
        ]

        if (
            not name_entry
            or
            name_entry[0]
            != "UTF8"
        ):
            continue

        name = name_entry[1]

        # array descriptor 제외/정규화
        if name.startswith("["):
            continue

        refs.add(
            name
        )

    return refs, utf8_values


# =========================================================
# Resource reference helpers
# =========================================================

def normalize_class_name(value):

    value = str(
        value
    ).strip()

    # fabric entrypoint:
    # com.foo.Bar::method

    if "::" in value:
        value = value.split(
            "::", 1
        )[0]

    value = value.replace(
        ".",
        "/"
    )

    return (
        value + ".class"
    )


def recursive_strings(obj):

    values = []

    if isinstance(obj, dict):

        for key, value in (
            obj.items()
        ):

            values.append(
                str(key)
            )

            values.extend(
                recursive_strings(
                    value
                )
            )

    elif isinstance(obj, list):

        for value in obj:

            values.extend(
                recursive_strings(
                    value
                )
            )

    elif isinstance(obj, str):

        values.append(obj)

    return values


def extract_entrypoints(
    fabric_json
):

    result = []

    entrypoints = (
        fabric_json.get(
            "entrypoints"
        )
        or {}
    )

    for kind, entries in (
        entrypoints.items()
    ):

        if not isinstance(
            entries,
            list
        ):
            entries = [entries]

        for entry in entries:

            if isinstance(
                entry,
                str
            ):

                value = entry

            elif isinstance(
                entry,
                dict
            ):

                value = (
                    entry.get(
                        "value"
                    )
                )

            else:
                continue

            if not value:
                continue

            result.append(
                (
                    kind,
                    normalize_class_name(
                        value
                    )
                )
            )

    return result


def extract_mixin_configs(
    fabric_json
):

    result = []

    mixins = (
        fabric_json.get(
            "mixins"
        )
        or []
    )

    for item in mixins:

        if isinstance(
            item,
            str
        ):

            result.append(
                item
            )

        elif isinstance(
            item,
            dict
        ):

            config = (
                item.get(
                    "config"
                )
            )

            if config:
                result.append(
                    config
                )

    return result


def parse_mixin_classes(
    obj
):

    package = str(
        obj.get(
            "package",
            ""
        )
    ).strip()

    classes = []

    for field in (
        "mixins",
        "client",
        "server",
    ):

        values = (
            obj.get(field)
            or []
        )

        if not isinstance(
            values,
            list
        ):
            continue

        for value in values:

            if not isinstance(
                value,
                str
            ):
                continue

            if package:

                full = (
                    package
                    + "."
                    + value
                )

            else:

                full = value

            classes.append(
                normalize_class_name(
                    full
                )
            )

    return classes


# =========================================================
# GRAPH STATS
# =========================================================

def component_stats(
    nodes,
    edges
):

    adjacency = defaultdict(
        set
    )

    for source, target, _ in (
        edges
    ):

        adjacency[source].add(
            target
        )

        adjacency[target].add(
            source
        )

    visited = set()

    component_sizes = []

    for node in nodes:

        if node in visited:
            continue

        q = deque([node])

        visited.add(node)

        size = 0

        while q:

            cur = q.popleft()

            size += 1

            for nxt in (
                adjacency.get(
                    cur,
                    []
                )
            ):

                if nxt in visited:
                    continue

                visited.add(nxt)

                q.append(nxt)

        component_sizes.append(
            size
        )

    component_sizes.sort(
        reverse=True
    )

    return {

        "connected_components":
            len(
                component_sizes
            ),

        "largest_component":
            (
                component_sizes[0]
                if component_sizes
                else 0
            ),

        "largest_component_rate":
            (
                component_sizes[0]
                / len(nodes)
                if nodes
                else 0
            ),
    }


# =========================================================
# MAIN
# =========================================================

packages = pd.read_csv(
    PACKAGE_REGISTRY
)

all_nodes = []
all_edges = []

stats_rows = []

failures = []


print(
    "======================================"
)

print(
    "Phase 4A - Dependency Graph Extraction"
)

print(
    "======================================"
)


for index, package in (
    packages.iterrows()
):

    mod_id = package[
        "mod_id"
    ]

    filename = package[
        "filename"
    ]

    title = package[
        "title"
    ]

    role = package[
        "role"
    ]

    jar_path = (
        RELEASE_ROOT
        / mod_id
        / filename
    )

    print()
    print(
        f"[{index + 1}/"
        f"{len(packages)}] "
        f"{mod_id} - {title}"
    )


    try:

        jar = zipfile.ZipFile(
            jar_path,
            "r"
        )

    except Exception as e:

        failures.append({
            "mod_id":
                mod_id,

            "reason":
                str(e),
        })

        continue


    with jar:

        names = set(
            x.replace(
                "\\",
                "/"
            )

            for x
            in jar.namelist()

            if not x.endswith("/")
        )


        class_names = {

            path
            for path in names
            if path.lower()
            .endswith(
                ".class"
            )

            and not path.lower()
            .startswith(
                "meta-inf/"
            )
        }


        structured_names = {

            path
            for path in names

            if (
                path.lower()
                .endswith(
                    ".json"
                )
                or
                path.lower()
                .endswith(
                    ".yaml"
                )
                or
                path.lower()
                .endswith(
                    ".yml"
                )
                or
                path.lower()
                .endswith(
                    ".xml"
                )
                or
                path.lower()
                .endswith(
                    ".mcmeta"
                )
            )
        }


        image_names = {

            path
            for path in names

            if (
                path.lower()
                .endswith(
                    ".png"
                )
                or
                path.lower()
                .endswith(
                    ".jpg"
                )
                or
                path.lower()
                .endswith(
                    ".jpeg"
                )
            )
        }


        component_names = (
            class_names
            |
            structured_names
            |
            image_names
        )


        node_ids = set()

        for path in sorted(
            component_names
        ):

            if path in class_names:
                node_type = "CLASS"

            elif (
                path
                in structured_names
            ):
                node_type = (
                    "STRUCTURED"
                )

            else:
                node_type = "IMAGE"


            node_id = (
                f"{mod_id}:{path}"
            )

            node_ids.add(
                node_id
            )


            all_nodes.append({

                "node_id":
                    node_id,

                "mod_id":
                    mod_id,

                "title":
                    title,

                "role":
                    role,

                "path":
                    path,

                "node_type":
                    node_type,
            })


        local_edges = set()


        # ================================================
        # 1. CLASS -> CLASS
        # ================================================

        class_edge_count = 0

        resource_literal_edges = 0


        for class_path in (
            class_names
        ):

            try:

                data = jar.read(
                    class_path
                )

                refs, utf8s = (
                    parse_class_refs(
                        data
                    )
                )

            except Exception:

                continue


            source = (
                f"{mod_id}:"
                f"{class_path}"
            )


            for ref in refs:

                target_path = (
                    ref + ".class"
                )

                if (
                    target_path
                    not in class_names
                ):
                    continue

                if (
                    target_path
                    == class_path
                ):
                    continue


                target = (
                    f"{mod_id}:"
                    f"{target_path}"
                )


                local_edges.add(
                    (
                        source,
                        target,
                        "CLASS_REF"
                    )
                )


            # UTF8 constant 안의
            # exact resource path 탐색

            for value in utf8s:

                normalized = (
                    value.replace(
                        "\\",
                        "/"
                    )
                )

                candidates = [
                    normalized,

                    normalized.lstrip(
                        "/"
                    ),
                ]


                for candidate in (
                    candidates
                ):

                    if (
                        candidate
                        not in component_names
                    ):
                        continue

                    if (
                        candidate
                        == class_path
                    ):
                        continue


                    target = (
                        f"{mod_id}:"
                        f"{candidate}"
                    )


                    local_edges.add(
                        (
                            source,
                            target,
                            "RESOURCE_LITERAL"
                        )
                    )


        # ================================================
        # 2. fabric.mod.json
        # ================================================

        fabric_path = (
            "fabric.mod.json"
        )


        if fabric_path in names:

            try:

                fabric_obj = json.loads(
                    jar.read(
                        fabric_path
                    ).decode(
                        "utf-8"
                    )
                )

            except Exception:

                fabric_obj = None


            if isinstance(
                fabric_obj,
                dict
            ):

                source = (
                    f"{mod_id}:"
                    f"{fabric_path}"
                )


                # entrypoints
                for (
                    kind,
                    target_path
                ) in extract_entrypoints(
                    fabric_obj
                ):

                    if (
                        target_path
                        not in class_names
                    ):
                        continue


                    target = (
                        f"{mod_id}:"
                        f"{target_path}"
                    )


                    local_edges.add(
                        (
                            source,
                            target,
                            "ENTRYPOINT"
                        )
                    )


                # mixin configs
                for config in (
                    extract_mixin_configs(
                        fabric_obj
                    )
                ):

                    if config not in names:
                        continue


                    target = (
                        f"{mod_id}:"
                        f"{config}"
                    )


                    local_edges.add(
                        (
                            source,
                            target,
                            "MIXIN_CONFIG"
                        )
                    )


        # ================================================
        # 3. MIXIN JSON -> CLASS
        # ================================================

        for path in (
            structured_names
        ):

            if not (
                "mixin"
                in path.lower()
                and
                path.lower()
                .endswith(
                    ".json"
                )
            ):
                continue


            try:

                obj = json.loads(
                    jar.read(
                        path
                    ).decode(
                        "utf-8"
                    )
                )

            except Exception:
                continue


            if not isinstance(
                obj,
                dict
            ):
                continue


            source = (
                f"{mod_id}:{path}"
            )


            for target_path in (
                parse_mixin_classes(
                    obj
                )
            ):

                if (
                    target_path
                    not in class_names
                ):
                    continue


                target = (
                    f"{mod_id}:"
                    f"{target_path}"
                )


                local_edges.add(
                    (
                        source,
                        target,
                        "MIXIN_CLASS"
                    )
                )


        # ================================================
        # 4. Generic JSON references
        # ================================================

        for path in (
            structured_names
        ):

            if not path.lower().endswith(
                ".json"
            ):
                continue


            try:

                obj = json.loads(
                    jar.read(
                        path
                    ).decode(
                        "utf-8"
                    )
                )

            except Exception:
                continue


            source = (
                f"{mod_id}:{path}"
            )


            for value in (
                recursive_strings(
                    obj
                )
            ):

                value = (
                    value.strip()
                    .replace(
                        "\\",
                        "/"
                    )
                )

                # exact path reference
                if (
                    value
                    in component_names
                    and
                    value != path
                ):

                    target = (
                        f"{mod_id}:"
                        f"{value}"
                    )

                    local_edges.add(
                        (
                            source,
                            target,
                            "STRUCTURED_REF"
                        )
                    )


                # dotted class reference
                if "." in value:

                    class_candidate = (
                        normalize_class_name(
                            value
                        )
                    )

                    if (
                        class_candidate
                        in class_names
                    ):

                        target = (
                            f"{mod_id}:"
                            f"{class_candidate}"
                        )

                        local_edges.add(
                            (
                                source,
                                target,
                                "STRUCTURED_CLASS_REF"
                            )
                        )


        # ================================================
        # Stats
        # ================================================

        edge_type_counts = (
            defaultdict(int)
        )


        for edge in local_edges:

            edge_type_counts[
                edge[2]
            ] += 1


            all_edges.append({

                "mod_id":
                    mod_id,

                "source":
                    edge[0],

                "target":
                    edge[1],

                "edge_type":
                    edge[2],
            })


        graph_stats = (
            component_stats(
                node_ids,
                local_edges
            )
        )


        stats_rows.append({

            "mod_id":
                mod_id,

            "title":
                title,

            "role":
                role,

            "nodes":
                len(node_ids),

            "class_nodes":
                len(
                    class_names
                ),

            "structured_nodes":
                len(
                    structured_names
                ),

            "image_nodes":
                len(
                    image_names
                ),

            "edges":
                len(
                    local_edges
                ),

            "class_ref_edges":
                edge_type_counts[
                    "CLASS_REF"
                ],

            "resource_literal_edges":
                edge_type_counts[
                    "RESOURCE_LITERAL"
                ],

            "entrypoint_edges":
                edge_type_counts[
                    "ENTRYPOINT"
                ],

            "mixin_config_edges":
                edge_type_counts[
                    "MIXIN_CONFIG"
                ],

            "mixin_class_edges":
                edge_type_counts[
                    "MIXIN_CLASS"
                ],

            "structured_ref_edges":
                edge_type_counts[
                    "STRUCTURED_REF"
                ],

            "structured_class_ref_edges":
                edge_type_counts[
                    "STRUCTURED_CLASS_REF"
                ],

            **graph_stats,
        })


        print(
            f"nodes={len(node_ids)} "
            f"edges={len(local_edges)} "
            f"class_edges="
            f"{edge_type_counts['CLASS_REF']} "
            f"largest="
            f"{graph_stats['largest_component_rate']:.3f}"
        )


# =========================================================
# SAVE
# =========================================================

nodes_df = pd.DataFrame(
    all_nodes
)

edges_df = pd.DataFrame(
    all_edges
)

stats_df = pd.DataFrame(
    stats_rows
)


nodes_df.to_csv(
    REGISTRY_ROOT
    / "dependency_nodes.csv",

    index=False,
    encoding="utf-8-sig",
)


edges_df.to_csv(
    REGISTRY_ROOT
    / "dependency_edges.csv",

    index=False,
    encoding="utf-8-sig",
)


stats_df.to_csv(
    RESULT_ROOT
    / "dependency_graph_stats.csv",

    index=False,
    encoding="utf-8-sig",
)


summary = {

    "projects":
        len(stats_df),

    "graph_failures":
        len(failures),

    "nodes":
        len(nodes_df),

    "edges":
        len(edges_df),

    "class_ref_edges":
        int(
            (
                edges_df[
                    "edge_type"
                ]
                == "CLASS_REF"
            ).sum()
        )
        if len(edges_df)
        else 0,

    "resource_literal_edges":
        int(
            (
                edges_df[
                    "edge_type"
                ]
                == "RESOURCE_LITERAL"
            ).sum()
        )
        if len(edges_df)
        else 0,

    "metadata_dependency_edges":
        int(
            (
                edges_df[
                    "edge_type"
                ]
                != "CLASS_REF"
            ).sum()
        )
        if len(edges_df)
        else 0,

    "mods_with_class_edges":
        int(
            (
                stats_df[
                    "class_ref_edges"
                ]
                > 0
            ).sum()
        )
        if len(stats_df)
        else 0,

    "median_edges_per_mod":
        float(
            stats_df[
                "edges"
            ].median()
        )
        if len(stats_df)
        else 0,

    "median_largest_component_rate":
        float(
            stats_df[
                "largest_component_rate"
            ].median()
        )
        if len(stats_df)
        else 0,

    "target_median_largest_component_rate":
        float(
            stats_df[
                stats_df[
                    "role"
                ]
                == "TARGET_MOD"
            ][
                "largest_component_rate"
            ].median()
        )
        if len(stats_df)
        else 0,
}


(
    RESULT_ROOT
    / "phase4a_summary.json"
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
    / "phase4a_failures.json"
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
    "Nodes : "
    "data\\registry\\dependency_nodes.csv"
)

print(
    "Edges : "
    "data\\registry\\dependency_edges.csv"
)

print(
    "Stats : "
    "results\\dependency_graph_stats.csv"
)