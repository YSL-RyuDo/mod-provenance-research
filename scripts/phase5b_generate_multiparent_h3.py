import json
import random
import struct
import zipfile
from collections import defaultdict, deque
from itertools import combinations
from pathlib import Path

import pandas as pd


SEED = 20260812
random.seed(SEED)

HARD_PER_PARENT = 3
MAX_FRAGMENTS_PER_RELEASE = 3

TARGET_TWO_PARENT_QUERIES = 100
TARGET_THREE_PARENT_QUERIES = 100


CURRENT_COMPONENTS = Path(
    "data/registry/release_component_registry.csv"
)

CURRENT_PACKAGES = Path(
    "data/registry/release_package_registry.csv"
)

HISTORY_RESULTS = Path(
    "results/real_version_component_results.csv"
)

HISTORY_ROOT = Path(
    "data/historical_releases"
)

OUT_ROOT = Path(
    "data/benchmark"
)

RESULT_ROOT = Path("results")

OUT_ROOT.mkdir(
    parents=True,
    exist_ok=True
)

RESULT_ROOT.mkdir(
    exist_ok=True
)


# =========================================================
# JVM class reference parser
# =========================================================

def u1(data, pos):
    return data[pos], pos + 1


def u2(data, pos):
    return (
        struct.unpack_from(
            ">H", data, pos
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
        data, pos
    )

    cp = [None] * cp_count

    i = 1

    try:

        while i < cp_count:

            tag, pos = u1(
                data, pos
            )

            if tag == 1:

                length, pos = u2(
                    data, pos
                )

                raw = data[
                    pos:pos + length
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
                    data, pos
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

        idx = entry[1]

        if (
            idx <= 0
            or
            idx >= len(cp)
        ):
            continue

        value = cp[idx]

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
# Graph
# =========================================================

def build_graph(jar_path):

    with zipfile.ZipFile(
        jar_path,
        "r"
    ) as jar:

        nodes = {

            path.replace(
                "\\", "/"
            )

            for path in jar.namelist()

            if (
                path.lower()
                .endswith(".class")
                and
                not path.lower()
                .startswith(
                    "meta-inf/"
                )
            )
        }

        adjacency = defaultdict(
            set
        )

        edges = set()

        for source in nodes:

            try:

                refs = parse_class_refs(
                    jar.read(source)
                )

            except Exception:
                continue

            for target in refs:

                if target not in nodes:
                    continue

                if target == source:
                    continue

                adjacency[
                    source
                ].add(target)

                adjacency[
                    target
                ].add(source)

                edges.add(
                    tuple(
                        sorted(
                            (
                                source,
                                target
                            )
                        )
                    )
                )

    return nodes, edges, adjacency


def connected_components(
    nodes,
    adjacency
):

    visited = set()
    components = []

    for node in nodes:

        if node in visited:
            continue

        q = deque([node])
        visited.add(node)

        component = set()

        while q:

            cur = q.popleft()

            component.add(cur)

            for nxt in (
                adjacency.get(
                    cur,
                    set()
                )
            ):

                if nxt in visited:
                    continue

                visited.add(nxt)
                q.append(nxt)

        components.append(
            component
        )

    components.sort(
        key=len,
        reverse=True
    )

    return components


# =========================================================
# Compact fragment
# =========================================================

def shortest_paths_from(
    start,
    adjacency
):

    distance = {
        start: 0
    }

    parent = {
        start: None
    }

    q = deque([start])

    while q:

        cur = q.popleft()

        for nxt in (
            adjacency.get(
                cur,
                set()
            )
        ):

            if nxt in distance:
                continue

            distance[nxt] = (
                distance[cur] + 1
            )

            parent[nxt] = cur

            q.append(nxt)

    return distance, parent


def restore_path(
    target,
    parent
):

    if target not in parent:
        return []

    path = []

    cur = target

    while cur is not None:

        path.append(cur)
        cur = parent[cur]

    path.reverse()

    return path


def make_fragment(
    hard_nodes,
    component,
    adjacency,
    seed_node,
    hard_count
):

    distance, parent = (
        shortest_paths_from(
            seed_node,
            adjacency
        )
    )

    reachable_hard = [

        node

        for node in hard_nodes

        if (
            node in component
            and
            node in distance
        )
    ]

    reachable_hard.sort(
        key=lambda x: (
            distance[x],
            x
        )
    )

    selected_hard = (
        reachable_hard[
            :hard_count
        ]
    )

    if (
        len(selected_hard)
        < hard_count
    ):
        return None


    fragment_nodes = set()

    for hard in selected_hard:

        path = restore_path(
            hard,
            parent
        )

        fragment_nodes.update(
            path
        )


    connector_nodes = (
        fragment_nodes
        - set(selected_hard)
    )


    fragment_edges = set()

    for source in fragment_nodes:

        for target in (
            adjacency.get(
                source,
                set()
            )
        ):

            if target not in (
                fragment_nodes
            ):
                continue

            fragment_edges.add(
                tuple(
                    sorted(
                        (
                            source,
                            target
                        )
                    )
                )
            )


    return {

        "hard_nodes":
            sorted(selected_hard),

        "connector_nodes":
            sorted(
                connector_nodes
            ),

        "all_nodes":
            sorted(
                fragment_nodes
            ),

        "edges":
            sorted(
                fragment_edges
            ),
    }


# =========================================================
# Locate historical JAR
# =========================================================

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

packages = pd.read_csv(
    CURRENT_PACKAGES
)

history = pd.read_csv(
    HISTORY_RESULTS
)


roles = dict(
    zip(
        packages["mod_id"],
        packages["role"]
    )
)


# =========================================================
# Hard criterion
# Same as Phase 3B
# =========================================================

path_index = defaultdict(set)

for _, row in current.iterrows():

    path = str(
        row["relative_path"]
    ).replace(
        "\\", "/"
    ).lower()

    path_index[path].add(
        row["mod_id"]
    )


history_code = history[
    history["modality"]
    == "CODE_BINARY"
].copy()


hard_groups = defaultdict(set)

version_numbers = {}


for _, row in (
    history_code.iterrows()
):

    mod_id = row["mod_id"]

    # Parent source는 TARGET only
    if roles.get(
        mod_id
    ) != "TARGET_MOD":
        continue

    path = str(
        row["relative_path"]
    ).replace(
        "\\", "/"
    )

    candidates = (
        path_index.get(
            path.lower(),
            set()
        )
    )

    unique_correct = (
        len(candidates) == 1
        and
        mod_id in candidates
    )

    if unique_correct:
        continue

    key = (
        mod_id,
        row[
            "historical_version_id"
        ]
    )

    hard_groups[key].add(
        path
    )

    version_numbers[key] = (
        row[
            "historical_version"
        ]
    )


# =========================================================
# Build fragment catalog
# =========================================================

fragment_catalog = []

fragment_id = 1


print(
    "======================================"
)
print(
    "Phase 5B - Multi-Parent Benchmark"
)
print(
    "======================================"
)

print(
    f"TARGET hard release groups: "
    f"{len(hard_groups)}"
)


for group_index, (
    key,
    hard_nodes
) in enumerate(
    hard_groups.items(),
    start=1
):

    mod_id, version_id = key

    if len(hard_nodes) < (
        HARD_PER_PARENT
    ):
        continue

    jar_path = find_jar(
        mod_id,
        version_id
    )

    if jar_path is None:
        continue


    nodes, edges, adjacency = (
        build_graph(
            jar_path
        )
    )


    hard_nodes = (
        set(hard_nodes)
        & nodes
    )

    if len(hard_nodes) < (
        HARD_PER_PARENT
    ):
        continue


    components = (
        connected_components(
            nodes,
            adjacency
        )
    )


    eligible_components = [

        component

        for component
        in components

        if len(
            component
            & hard_nodes
        ) >= HARD_PER_PARENT
    ]


    if not eligible_components:
        continue


    created = 0


    for component in (
        eligible_components
    ):

        component_hard = sorted(
            component
            & hard_nodes
        )


        # 다양한 seed 후보
        seeds = (
            component_hard.copy()
        )

        random.shuffle(seeds)


        for seed in seeds:

            fragment = (
                make_fragment(
                    hard_nodes,
                    component,
                    adjacency,
                    seed,
                    HARD_PER_PARENT,
                )
            )

            if fragment is None:
                continue


            # 지나치게 큰 connector chain은
            # preliminary benchmark에서 제외
            if (
                len(
                    fragment[
                        "connector_nodes"
                    ]
                )
                > 25
            ):
                continue


            catalog_entry = {

                "fragment_id":
                    f"F{fragment_id:04d}",

                "source_mod":
                    mod_id,

                "source_role":
                    roles.get(
                        mod_id
                    ),

                "historical_version_id":
                    version_id,

                "historical_version":
                    version_numbers.get(
                        key
                    ),

                "hard_node_count":
                    len(
                        fragment[
                            "hard_nodes"
                        ]
                    ),

                "connector_node_count":
                    len(
                        fragment[
                            "connector_nodes"
                        ]
                    ),

                "node_count":
                    len(
                        fragment[
                            "all_nodes"
                        ]
                    ),

                "edge_count":
                    len(
                        fragment[
                            "edges"
                        ]
                    ),

                **fragment,
            }


            # 동일 release에서 완전히
            # 같은 target set 중복 방지
            signature = tuple(
                fragment[
                    "hard_nodes"
                ]
            )


            duplicate = any(
                (
                    existing["source_mod"] == mod_id
                    and
                    existing["historical_version_id"] == version_id
                    and
                    tuple(existing["hard_nodes"]) == signature
                )
                for existing in fragment_catalog
            )


            if duplicate:
                continue


            fragment_catalog.append(
                catalog_entry
            )

            fragment_id += 1
            created += 1


            if (
                created
                >= MAX_FRAGMENTS_PER_RELEASE
            ):
                break


        if (
            created
            >= MAX_FRAGMENTS_PER_RELEASE
        ):
            break


    print(
        f"[{group_index}/"
        f"{len(hard_groups)}] "
        f"{mod_id} "
        f"hard={len(hard_nodes)} "
        f"fragments={created}"
    )


# =========================================================
# Parent coverage
# =========================================================

fragments_by_mod = defaultdict(
    list
)

for fragment in fragment_catalog:

    fragments_by_mod[
        fragment[
            "source_mod"
        ]
    ].append(
        fragment
    )


eligible_parent_mods = sorted(
    fragments_by_mod.keys()
)


print()
print(
    f"Fragments: "
    f"{len(fragment_catalog)}"
)

print(
    f"Distinct TARGET parent MODs: "
    f"{len(eligible_parent_mods)}"
)


# =========================================================
# Build query combinations
# =========================================================

def sample_combinations(
    parent_count,
    target_count
):

    possible = list(
        combinations(
            eligible_parent_mods,
            parent_count
        )
    )

    random.shuffle(
        possible
    )

    queries = []

    # 조합이 적으면 여러 fragment
    # 선택으로 추가 query 생성
    attempts = 0
    max_attempts = (
        target_count * 50
    )


    while (
        len(queries)
        < target_count
        and
        attempts
        < max_attempts
        and
        possible
    ):

        attempts += 1

        parents = random.choice(
            possible
        )


        selected = [

            random.choice(
                fragments_by_mod[
                    parent
                ]
            )

            for parent
            in parents
        ]


        signature = tuple(
            sorted(
                fragment[
                    "fragment_id"
                ]

                for fragment
                in selected
            )
        )


        if any(
            q[
                "_signature"
            ]
            == signature

            for q in queries
        ):
            continue


        queries.append({

            "_signature":
                signature,

            "fragments":
                selected,
        })


    return queries


two_parent = (
    sample_combinations(
        2,
        TARGET_TWO_PARENT_QUERIES
    )
)

three_parent = (
    sample_combinations(
        3,
        TARGET_THREE_PARENT_QUERIES
    )
)


# =========================================================
# Anonymized query representation
# =========================================================

query_rows = []

query_id_counter = 1


def materialize_query(
    query,
    parent_count,
    query_id
):

    nodes = []
    edges = []

    ground_truth = {}

    parent_mods = []


    local_counter = 1


    for fragment in (
        query["fragments"]
    ):

        parent = fragment[
            "source_mod"
        ]

        parent_mods.append(
            parent
        )


        mapping = {}


        for original in (
            fragment[
                "all_nodes"
            ]
        ):

            anonymous = (
                f"{query_id}:"
                f"N{local_counter:04d}"
            )

            local_counter += 1

            mapping[
                original
            ] = anonymous


        hard_set = set(
            fragment[
                "hard_nodes"
            ]
        )


        for original in (
            fragment[
                "all_nodes"
            ]
        ):

            role = (
                "TARGET"
                if original
                in hard_set
                else
                "CONNECTOR"
            )


            node = {

                "query_node_id":
                    mapping[
                        original
                    ],

                # 이 값은 evaluator가
                # payload를 historical JAR에서
                # 찾기 위한 내부 metadata.
                # retrieval algorithm input으로
                # 사용하면 안 됨.
                "source_mod":
                    parent,

                "historical_version_id":
                    fragment[
                        "historical_version_id"
                    ],

                "source_path":
                    original,

                "evaluation_role":
                    role,
            }


            nodes.append(node)


            if role == "TARGET":

                ground_truth[
                    mapping[
                        original
                    ]
                ] = parent


        for a, b in (
            fragment[
                "edges"
            ]
        ):

            edges.append({

                "source":
                    mapping[a],

                "target":
                    mapping[b],

                "edge_type":
                    "CLASS_REF",
            })


    return {

        "query_id":
            query_id,

        "parent_count":
            parent_count,

        "parents":
            sorted(
                parent_mods
            ),

        "nodes":
            nodes,

        "edges":
            edges,

        "ground_truth":
            ground_truth,

        "target_node_count":
            len(
                ground_truth
            ),

        "connector_node_count":
            sum(
                1
                for node in nodes
                if node[
                    "evaluation_role"
                ]
                == "CONNECTOR"
            ),
    }


queries = []


for query in two_parent:

    query_id = (
        f"Q{query_id_counter:04d}"
    )

    query_id_counter += 1

    queries.append(
        materialize_query(
            query,
            2,
            query_id
        )
    )


for query in three_parent:

    query_id = (
        f"Q{query_id_counter:04d}"
    )

    query_id_counter += 1

    queries.append(
        materialize_query(
            query,
            3,
            query_id
        )
    )


# =========================================================
# Save
# =========================================================

fragment_path = (
    OUT_ROOT
    / "fragment_catalog_h3.jsonl"
)

query_path = (
    OUT_ROOT
    / "multiparent_queries_h3.jsonl"
)


with open(
    fragment_path,
    "w",
    encoding="utf-8"
) as f:

    for row in fragment_catalog:

        f.write(
            json.dumps(
                row,
                ensure_ascii=False
            )
            + "\n"
        )


with open(
    query_path,
    "w",
    encoding="utf-8"
) as f:

    for row in queries:

        f.write(
            json.dumps(
                row,
                ensure_ascii=False
            )
            + "\n"
        )


# =========================================================
# Summary
# =========================================================

summary = {

    "random_seed":
        SEED,

    "hard_nodes_per_parent":
        HARD_PER_PARENT,

    "fragment_catalog_size":
        len(
            fragment_catalog
        ),

    "distinct_parent_mods":
        len(
            eligible_parent_mods
        ),

    "parent_mods":
        eligible_parent_mods,

    "two_parent_queries":
        len(
            two_parent
        ),

    "three_parent_queries":
        len(
            three_parent
        ),

    "total_queries":
        len(
            queries
        ),

    "total_target_nodes":
        sum(
            q[
                "target_node_count"
            ]
            for q in queries
        ),

    "total_connector_nodes":
        sum(
            q[
                "connector_node_count"
            ]
            for q in queries
        ),

    "mean_target_nodes_per_query":
        (
            sum(
                q[
                    "target_node_count"
                ]
                for q in queries
            )
            / len(queries)
            if queries
            else 0
        ),

    "mean_connector_nodes_per_query":
        (
            sum(
                q[
                    "connector_node_count"
                ]
                for q in queries
            )
            / len(queries)
            if queries
            else 0
        ),
}


(
    RESULT_ROOT
    / "phase5b_h3_summary.json"
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
    "Fragment catalog : "
    "data\\benchmark\\fragment_catalog.jsonl"
)

print(
    "Queries          : "
    "data\\benchmark\\multiparent_queries.jsonl"
)