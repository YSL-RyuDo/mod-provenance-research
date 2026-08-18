import json
import re
import struct
import zipfile
from collections import defaultdict, deque
from pathlib import Path

import pandas as pd


PACKAGE_REGISTRY = Path(
    "data/registry/release_package_registry.csv"
)

NODE_REGISTRY = Path(
    "data/registry/dependency_nodes.csv"
)

BASE_EDGE_REGISTRY = Path(
    "data/registry/dependency_edges.csv"
)

RELEASE_ROOT = Path(
    "data/release_packages"
)

REGISTRY_ROOT = Path(
    "data/registry"
)

RESULT_ROOT = Path("results")


# =========================================================
# Identifier
# =========================================================

IDENTIFIER_RE = re.compile(
    r"^[a-z0-9_.-]+:"
    r"[a-z0-9_./-]+$"
)

IDENTIFIER_FIND_RE = re.compile(
    r"(?<![A-Za-z0-9_.-])"
    r"([a-z0-9_.-]+:"
    r"[a-z0-9_./-]+)"
)


def normalize_identifier(value):

    value = str(value).strip()

    if value.startswith("#"):
        return None

    if not IDENTIFIER_RE.match(
        value
    ):
        return None

    return value.lower()


# =========================================================
# Constant Pool UTF8
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


def extract_utf8_constants(data):

    if len(data) < 10:
        return []

    if data[:4] != b"\xca\xfe\xba\xbe":
        return []

    pos = 4

    # minor / major
    _, pos = u2(data, pos)
    _, pos = u2(data, pos)

    cp_count, pos = u2(
        data,
        pos
    )

    result = []

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

                result.append(
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

            elif tag in (
                7, 8, 16,
                19, 20
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
                break

            i += 1

    except Exception:
        return result

    return result


# =========================================================
# Resource index
# =========================================================

def build_resource_indexes(
    paths
):

    generic = defaultdict(set)
    texture = defaultdict(set)
    model = defaultdict(set)

    for path in paths:

        p = path.replace(
            "\\",
            "/"
        )

        lower = p.lower()

        parts = lower.split("/")

        # ---------------------------------------------
        # assets/<namespace>/...
        # ---------------------------------------------

        if (
            len(parts) >= 4
            and
            parts[0] == "assets"
        ):

            namespace = parts[1]

            resource_type = parts[2]

            rest = "/".join(
                parts[3:]
            )

            # textures/foo.png
            if (
                resource_type
                == "textures"
                and
                rest.endswith(".png")
            ):

                logical = (
                    rest[:-4]
                )

                key = (
                    f"{namespace}:"
                    f"{logical}"
                )

                texture[key].add(p)
                generic[key].add(p)

            # models/foo.json
            elif (
                resource_type
                == "models"
                and
                rest.endswith(".json")
            ):

                logical = (
                    rest[:-5]
                )

                key = (
                    f"{namespace}:"
                    f"{logical}"
                )

                model[key].add(p)
                generic[key].add(p)

            # 다른 asset JSON/image도
            # category 포함 identifier 생성
            else:

                stem = rest

                for suffix in (
                    ".json",
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".mcmeta",
                ):

                    if stem.endswith(
                        suffix
                    ):
                        stem = stem[
                            :-len(suffix)
                        ]
                        break

                key = (
                    f"{namespace}:"
                    f"{stem}"
                )

                generic[key].add(p)

                category_key = (
                    f"{namespace}:"
                    f"{resource_type}/"
                    f"{stem}"
                )

                generic[
                    category_key
                ].add(p)


        # ---------------------------------------------
        # data/<namespace>/<category>/...
        # ---------------------------------------------

        elif (
            len(parts) >= 4
            and
            parts[0] == "data"
        ):

            namespace = parts[1]
            category = parts[2]

            rest = "/".join(
                parts[3:]
            )

            stem = rest

            for suffix in (
                ".json",
                ".mcmeta",
            ):

                if stem.endswith(
                    suffix
                ):
                    stem = stem[
                        :-len(suffix)
                    ]
                    break

            generic[
                f"{namespace}:"
                f"{stem}"
            ].add(p)

            generic[
                f"{namespace}:"
                f"{category}/"
                f"{stem}"
            ].add(p)


    return {
        "generic": generic,
        "texture": texture,
        "model": model,
    }


def unique_resolve(
    index,
    identifier
):

    paths = index.get(
        identifier,
        set()
    )

    if len(paths) != 1:
        return None

    return next(
        iter(paths)
    )


# =========================================================
# JSON traversal
# =========================================================

def walk_json(
    obj,
    parent_key=None
):

    if isinstance(obj, dict):

        for key, value in (
            obj.items()
        ):

            yield from walk_json(
                value,
                str(key)
            )

    elif isinstance(obj, list):

        for value in obj:

            yield from walk_json(
                value,
                parent_key
            )

    elif isinstance(obj, str):

        yield (
            parent_key,
            obj
        )


# =========================================================
# Connected component stats
# =========================================================

def graph_stats(
    node_ids,
    edges
):

    adjacency = defaultdict(set)

    for (
        source,
        target,
        _
    ) in edges:

        adjacency[source].add(
            target
        )

        adjacency[target].add(
            source
        )

    visited = set()
    sizes = []

    for node in node_ids:

        if node in visited:
            continue

        queue = deque([node])
        visited.add(node)

        size = 0

        while queue:

            current = (
                queue.popleft()
            )

            size += 1

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

        sizes.append(size)

    sizes.sort(
        reverse=True
    )

    if not sizes:
        return 0, 0.0

    return (
        sizes[0],
        sizes[0]
        / len(node_ids)
    )


# =========================================================
# Load
# =========================================================

packages = pd.read_csv(
    PACKAGE_REGISTRY
)

nodes = pd.read_csv(
    NODE_REGISTRY
)

base_edges = pd.read_csv(
    BASE_EDGE_REGISTRY
)


all_edges = set()

for _, row in (
    base_edges.iterrows()
):

    all_edges.add(
        (
            row["source"],
            row["target"],
            row["edge_type"],
        )
    )


base_edge_count = len(
    all_edges
)

added = set()

stats_rows = []


print(
    "======================================"
)
print(
    "Phase 4B - Resource Graph Enrichment"
)
print(
    "======================================"
)


# =========================================================
# Per MOD
# =========================================================

for index, pkg in (
    packages.iterrows()
):

    mod_id = pkg["mod_id"]
    title = pkg["title"]
    role = pkg["role"]

    jar_path = (
        RELEASE_ROOT
        / mod_id
        / pkg["filename"]
    )

    print()
    print(
        f"[{index + 1}/"
        f"{len(packages)}] "
        f"{mod_id} - {title}"
    )

    mod_nodes = nodes[
        nodes["mod_id"]
        == mod_id
    ]

    path_to_node = dict(
        zip(
            mod_nodes["path"],
            mod_nodes["node_id"]
        )
    )

    component_paths = set(
        path_to_node.keys()
    )

    indexes = (
        build_resource_indexes(
            component_paths
        )
    )

    local_added = set()


    with zipfile.ZipFile(
        jar_path,
        "r"
    ) as jar:

        names = set(
            jar.namelist()
        )


        # ================================================
        # JSON / structured resources
        # ================================================

        structured_paths = [

            path

            for path in component_paths

            if path.lower()
            .endswith(".json")
        ]


        for source_path in (
            structured_paths
        ):

            try:

                data = jar.read(
                    source_path
                )

                obj = json.loads(
                    data.decode(
                        "utf-8"
                    )
                )

            except Exception:
                continue


            source_node = (
                path_to_node[
                    source_path
                ]
            )


            for key, value in (
                walk_json(obj)
            ):

                stripped = (
                    value.strip()
                )


                # ----------------------------------------
                # Exact packaged path
                # ----------------------------------------

                direct = (
                    stripped
                    .replace(
                        "\\",
                        "/"
                    )
                    .lstrip("/")
                )

                if (
                    direct
                    in path_to_node
                    and
                    direct
                    != source_path
                ):

                    local_added.add(
                        (
                            source_node,
                            path_to_node[
                                direct
                            ],
                            "JSON_EXACT_PATH",
                        )
                    )


                identifier = (
                    normalize_identifier(
                        stripped
                    )
                )

                if identifier is None:
                    continue


                key_lower = (
                    str(key or "")
                    .lower()
                )


                # ----------------------------------------
                # Model parent
                # ----------------------------------------

                if key_lower == "parent":

                    target_path = (
                        unique_resolve(
                            indexes[
                                "model"
                            ],
                            identifier
                        )
                    )

                    if (
                        target_path
                        and
                        target_path
                        != source_path
                    ):

                        local_added.add(
                            (
                                source_node,
                                path_to_node[
                                    target_path
                                ],
                                "MODEL_PARENT",
                            )
                        )

                        continue


                # ----------------------------------------
                # Texture
                # ----------------------------------------

                if (
                    key_lower
                    in {
                        "texture",
                        "particle",
                        "layer0",
                        "layer1",
                        "layer2",
                        "layer3",
                    }
                    or
                    "texture"
                    in key_lower
                ):

                    target_path = (
                        unique_resolve(
                            indexes[
                                "texture"
                            ],
                            identifier
                        )
                    )

                    if (
                        target_path
                        and
                        target_path
                        != source_path
                    ):

                        local_added.add(
                            (
                                source_node,
                                path_to_node[
                                    target_path
                                ],
                                "TEXTURE_REF",
                            )
                        )

                        continue


                # ----------------------------------------
                # Generic unique resource identifier
                # ----------------------------------------

                target_path = (
                    unique_resolve(
                        indexes[
                            "generic"
                        ],
                        identifier
                    )
                )

                if (
                    target_path
                    and
                    target_path
                    != source_path
                ):

                    local_added.add(
                        (
                            source_node,
                            path_to_node[
                                target_path
                            ],
                            "JSON_IDENTIFIER_REF",
                        )
                    )


        # ================================================
        # fabric.mod.json icon
        # ================================================

        if (
            "fabric.mod.json"
            in names
            and
            "fabric.mod.json"
            in path_to_node
        ):

            try:

                fabric_obj = (
                    json.loads(
                        jar.read(
                            "fabric.mod.json"
                        ).decode(
                            "utf-8"
                        )
                    )
                )

            except Exception:
                fabric_obj = None


            if isinstance(
                fabric_obj,
                dict
            ):

                icon = (
                    fabric_obj.get(
                        "icon"
                    )
                )

                icon_paths = []

                if isinstance(
                    icon,
                    str
                ):

                    icon_paths = [icon]

                elif isinstance(
                    icon,
                    dict
                ):

                    icon_paths = [
                        x
                        for x in
                        icon.values()
                        if isinstance(
                            x,
                            str
                        )
                    ]


                for icon_path in (
                    icon_paths
                ):

                    clean = (
                        icon_path
                        .replace(
                            "\\",
                            "/"
                        )
                        .lstrip("/")
                    )

                    if clean not in (
                        path_to_node
                    ):
                        continue

                    local_added.add(
                        (
                            path_to_node[
                                "fabric.mod.json"
                            ],
                            path_to_node[
                                clean
                            ],
                            "FABRIC_ICON",
                        )
                    )


        # ================================================
        # Class UTF8 identifier references
        #
        # heuristic edge:
        # class constant에서 namespace:path 문자열을
        # 실제 packaged resource로 unique resolve
        # ================================================

        class_paths = [

            path

            for path in component_paths

            if path.lower()
            .endswith(".class")
        ]


        for source_path in (
            class_paths
        ):

            try:

                data = jar.read(
                    source_path
                )

            except Exception:
                continue


            strings = (
                extract_utf8_constants(
                    data
                )
            )

            identifiers = set()


            for text in strings:

                for match in (
                    IDENTIFIER_FIND_RE
                    .finditer(
                        text.lower()
                    )
                ):

                    identifiers.add(
                        match.group(1)
                    )


            source_node = (
                path_to_node[
                    source_path
                ]
            )


            for identifier in (
                identifiers
            ):

                target_path = (
                    unique_resolve(
                        indexes[
                            "generic"
                        ],
                        identifier
                    )
                )

                if not target_path:
                    continue

                if (
                    target_path
                    == source_path
                ):
                    continue


                local_added.add(
                    (
                        source_node,
                        path_to_node[
                            target_path
                        ],
                        "CLASS_IDENTIFIER_REF",
                    )
                )


    # ====================================================
    # Merge
    # ====================================================

    added.update(
        local_added
    )

    all_edges.update(
        local_added
    )


    local_all_edges = [

        edge

        for edge in all_edges

        if edge[0].startswith(
            mod_id + ":"
        )
    ]


    node_ids = set(
        mod_nodes[
            "node_id"
        ].tolist()
    )


    largest, largest_rate = (
        graph_stats(
            node_ids,
            local_all_edges
        )
    )


    hetero_count = sum(

        1

        for edge in (
            local_all_edges
        )

        if edge[2]
        != "CLASS_REF"
    )


    added_type_counts = (
        defaultdict(int)
    )


    for edge in local_added:

        added_type_counts[
            edge[2]
        ] += 1


    stats_rows.append({

        "mod_id":
            mod_id,

        "title":
            title,

        "role":
            role,

        "nodes":
            len(node_ids),

        "base_edges":
            len(
                base_edges[
                    base_edges[
                        "mod_id"
                    ]
                    == mod_id
                ]
            ),

        "added_edges":
            len(local_added),

        "total_edges_v2":
            len(
                local_all_edges
            ),

        "heterogeneous_edges_v2":
            hetero_count,

        "json_exact_path":
            added_type_counts[
                "JSON_EXACT_PATH"
            ],

        "json_identifier_ref":
            added_type_counts[
                "JSON_IDENTIFIER_REF"
            ],

        "model_parent":
            added_type_counts[
                "MODEL_PARENT"
            ],

        "texture_ref":
            added_type_counts[
                "TEXTURE_REF"
            ],

        "fabric_icon":
            added_type_counts[
                "FABRIC_ICON"
            ],

        "class_identifier_ref":
            added_type_counts[
                "CLASS_IDENTIFIER_REF"
            ],

        "largest_component":
            largest,

        "largest_component_rate_v2":
            largest_rate,
    })


    print(
        f"added={len(local_added)} "
        f"hetero={hetero_count} "
        f"largest="
        f"{largest_rate:.3f}"
    )


# =========================================================
# Save edge registry
# =========================================================

edge_rows = []

for (
    source,
    target,
    edge_type
) in sorted(all_edges):

    mod_id = (
        source.split(
            ":",
            1
        )[0]
    )

    edge_rows.append({

        "mod_id":
            mod_id,

        "source":
            source,

        "target":
            target,

        "edge_type":
            edge_type,
    })


edges_v2 = pd.DataFrame(
    edge_rows
)

stats = pd.DataFrame(
    stats_rows
)


edges_v2.to_csv(

    REGISTRY_ROOT
    / "dependency_edges_v2.csv",

    index=False,
    encoding="utf-8-sig",
)


stats.to_csv(

    RESULT_ROOT
    / "dependency_graph_stats_v2.csv",

    index=False,
    encoding="utf-8-sig",
)


# =========================================================
# Summary
# =========================================================

added_type_counts = (
    defaultdict(int)
)

for edge in added:

    added_type_counts[
        edge[2]
    ] += 1


non_class_v2 = int(

    (
        edges_v2[
            "edge_type"
        ]
        != "CLASS_REF"
    ).sum()
)


summary = {

    "projects":
        len(stats),

    "base_edges":
        base_edge_count,

    "added_edges":
        len(added),

    "total_edges_v2":
        len(edges_v2),

    "non_class_edges_v2":
        non_class_v2,

    "json_exact_path":
        added_type_counts[
            "JSON_EXACT_PATH"
        ],

    "json_identifier_ref":
        added_type_counts[
            "JSON_IDENTIFIER_REF"
        ],

    "model_parent":
        added_type_counts[
            "MODEL_PARENT"
        ],

    "texture_ref":
        added_type_counts[
            "TEXTURE_REF"
        ],

    "fabric_icon":
        added_type_counts[
            "FABRIC_ICON"
        ],

    "class_identifier_ref":
        added_type_counts[
            "CLASS_IDENTIFIER_REF"
        ],

    "mods_with_new_resource_edges":
        int(
            (
                stats[
                    "added_edges"
                ]
                > 0
            ).sum()
        ),

    "median_added_edges":
        float(
            stats[
                "added_edges"
            ].median()
        ),

    "median_non_class_edges_v2":
        float(
            stats[
                "heterogeneous_edges_v2"
            ].median()
        ),

    "median_largest_component_rate_v2":
        float(
            stats[
                "largest_component_rate_v2"
            ].median()
        ),

    "target_median_largest_component_rate_v2":
        float(
            stats[
                stats["role"]
                == "TARGET_MOD"
            ][
                "largest_component_rate_v2"
            ].median()
        ),
}


(
    RESULT_ROOT
    / "phase4b_summary.json"
).write_text(

    json.dumps(
        summary,
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
    "Edges V2 : "
    "data\\registry\\dependency_edges_v2.csv"
)

print(
    "Stats V2 : "
    "results\\dependency_graph_stats_v2.csv"
)