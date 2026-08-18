from itertools import combinations
import json
import math
import sys
from collections import defaultdict, deque
from pathlib import Path

import pandas as pd


# =========================================================
# Import Phase 3D bytecode utilities
# =========================================================

SCRIPT_DIR = Path(__file__).resolve().parent

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import phase3d_bytecode_baseline as p3d


# =========================================================
# Config
# =========================================================

QUERY_FILE = Path(
    "data/benchmark/multiparent_queries_h3.jsonl"
)

CURRENT_COMPONENTS = Path(
    "data/registry/release_component_registry.csv"
)

CURRENT_PACKAGES = Path(
    "data/registry/release_package_registry.csv"
)

HISTORY_ROOT = Path(
    "data/historical_releases"
)

RELEASE_ROOT = Path(
    "data/release_packages"
)

RESULT_ROOT = Path("results")

PUBLIC_QUERY_FILE = Path(
    "data/benchmark/multiparent_queries_h3_public.jsonl"
)

GT_FILE = Path(
    "data/benchmark/multiparent_queries_h3_ground_truth.jsonl"
)

RESULT_ROOT.mkdir(exist_ok=True)

REPRESENTATIONS = [
    "OPCODE_3GRAM",
    "OPCODE_STRUCT",
    "OPCODE_CONTEXT",
]


# =========================================================
# Load JSONL
# =========================================================

def load_jsonl(path):
    rows = []

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:

        for line in f:
            line = line.strip()

            if not line:
                continue

            rows.append(
                json.loads(line)
            )

    return rows


queries = load_jsonl(
    QUERY_FILE
)


# =========================================================
# Leakage-safe benchmark split
# =========================================================

public_queries = []
ground_truth_rows = []


for query in queries:

    public_nodes = []
    hidden_nodes = {}

    for node in query["nodes"]:

        public_nodes.append({
            "query_node_id":
                node["query_node_id"],

            "evaluation_role":
                node["evaluation_role"],
        })

        hidden_nodes[
            node["query_node_id"]
        ] = {
            "source_mod":
                node["source_mod"],

            "historical_version_id":
                node[
                    "historical_version_id"
                ],

            "source_path":
                node["source_path"],

            "evaluation_role":
                node["evaluation_role"],
        }

    public_queries.append({
        "query_id":
            query["query_id"],

        "parent_count":
            query["parent_count"],

        "nodes":
            public_nodes,

        "edges":
            query["edges"],
    })

    ground_truth_rows.append({
        "query_id":
            query["query_id"],

        "parents":
            query["parents"],

        "ground_truth":
            query["ground_truth"],

        "hidden_nodes":
            hidden_nodes,
    })


with open(
    PUBLIC_QUERY_FILE,
    "w",
    encoding="utf-8"
) as f:

    for row in public_queries:
        f.write(
            json.dumps(
                row,
                ensure_ascii=False
            )
            + "\n"
        )


with open(
    GT_FILE,
    "w",
    encoding="utf-8"
) as f:

    for row in ground_truth_rows:
        f.write(
            json.dumps(
                row,
                ensure_ascii=False
            )
            + "\n"
        )


print(
    "Leakage-safe benchmark files created."
)


# =========================================================
# Metadata
# =========================================================

current = pd.read_csv(
    CURRENT_COMPONENTS
)

packages = pd.read_csv(
    CURRENT_PACKAGES
)

current_code = current[
    current["modality"]
    == "CODE_BINARY"
].copy()

package_filename = dict(
    zip(
        packages["mod_id"],
        packages["filename"]
    )
)


# =========================================================
# Build current gallery
# =========================================================

print()
print(
    "======================================"
)
print(
    "[1/4] Building current gallery"
)
print(
    "======================================"
)


gallery = {
    rep: defaultdict(list)
    for rep in REPRESENTATIONS
}


for index, (
    mod_id,
    group
) in enumerate(
    current_code.groupby(
        "mod_id"
    ),
    start=1
):

    filename = package_filename.get(
        mod_id
    )

    if not filename:
        continue

    jar_path = (
        RELEASE_ROOT
        / mod_id
        / filename
    )

    if not jar_path.exists():
        continue

    class_names = []

    for _, row in group.iterrows():

        class_name = (
            p3d.path_to_class_name(
                row["relative_path"]
            )
        )

        if class_name:
            class_names.append(
                class_name
            )

    class_names = list(
        dict.fromkeys(
            class_names
        )
    )

    print(
        f"[{index}] "
        f"{mod_id}: "
        f"{len(class_names)} classes"
    )

    outputs = (
        p3d.run_javap_for_classes(
            jar_path,
            class_names
        )
    )

    for class_name in class_names:

        block = outputs.get(
            class_name
        )

        if (
            not block
            or
            block["rc"] != 0
        ):
            continue

        signatures = (
            p3d.signatures_from_javap(
                block["text"]
            )
        )

        for rep in REPRESENTATIONS:

            gallery[
                rep
            ][mod_id].append(
                signatures[rep]
            )


for rep in REPRESENTATIONS:

    total = sum(
        len(x)
        for x
        in gallery[rep].values()
    )

    print(
        f"{rep}: {total}"
    )


# =========================================================
# Historical signature cache
# =========================================================

print()
print(
    "======================================"
)
print(
    "[2/4] Building query signature cache"
)
print(
    "======================================"
)


signature_cache = {}


def historical_jar(
    mod_id,
    version_id
):

    directory = (
        HISTORY_ROOT
        / str(mod_id)
        / str(version_id)
    )

    jars = list(
        directory.glob(
            "*.jar"
        )
    )

    if not jars:
        return None

    return jars[0]


requests_by_jar = defaultdict(
    set
)


for gt in ground_truth_rows:

    for node_id, hidden in (
        gt["hidden_nodes"].items()
    ):

        # Connector의 content는
        # attribution evidence로 사용 금지.
        if (
            hidden["evaluation_role"]
            != "TARGET"
        ):
            continue

        class_name = (
            p3d.path_to_class_name(
                hidden["source_path"]
            )
        )

        if not class_name:
            continue

        key = (
            hidden["source_mod"],
            hidden[
                "historical_version_id"
            ]
        )

        requests_by_jar[
            key
        ].add(
            class_name
        )


for index, (
    key,
    class_names
) in enumerate(
    requests_by_jar.items(),
    start=1
):

    mod_id, version_id = key

    jar_path = historical_jar(
        mod_id,
        version_id
    )

    if jar_path is None:
        continue

    class_names = sorted(
        class_names
    )

    print(
        f"[{index}/"
        f"{len(requests_by_jar)}] "
        f"{mod_id}: "
        f"{len(class_names)}"
    )

    outputs = (
        p3d.run_javap_for_classes(
            jar_path,
            class_names
        )
    )

    for class_name in class_names:

        block = outputs.get(
            class_name
        )

        if (
            not block
            or
            block["rc"] != 0
        ):
            continue

        signature_cache[
            (
                mod_id,
                version_id,
                class_name,
            )
        ] = (
            p3d.signatures_from_javap(
                block["text"]
            )
        )


print(
    "Cached query classes:",
    len(signature_cache)
)


# =========================================================
# Candidate distance vectors
# =========================================================

print()
print(
    "======================================"
)
print(
    "[3/4] Computing candidate evidence"
)
print(
    "======================================"
)


def mod_distances(
    signature,
    representation
):

    result = {}

    for mod_id, signatures in (
        gallery[
            representation
        ].items()
    ):

        if not signatures:
            continue

        result[mod_id] = min(
            p3d.hamming128(
                signature,
                candidate
            )
            for candidate
            in signatures
        )

    return result


distance_cache = {}


for gt in ground_truth_rows:

    for node_id, hidden in (
        gt["hidden_nodes"].items()
    ):

        if (
            hidden["evaluation_role"]
            != "TARGET"
        ):
            continue

        class_name = (
            p3d.path_to_class_name(
                hidden["source_path"]
            )
        )

        key = (
            hidden["source_mod"],
            hidden[
                "historical_version_id"
            ],
            class_name,
        )

        signatures = (
            signature_cache.get(
                key
            )
        )

        if signatures is None:
            continue

        for rep in REPRESENTATIONS:

            cache_key = (
                key,
                rep
            )

            if (
                cache_key
                not in distance_cache
            ):

                distance_cache[
                    cache_key
                ] = mod_distances(
                    signatures[rep],
                    rep
                )


print(
    "Candidate vectors:",
    len(distance_cache)
)


# =========================================================
# Graph helpers
# =========================================================

def connected_components(
    node_ids,
    edges
):

    adjacency = defaultdict(
        set
    )

    for edge in edges:

        a = edge["source"]
        b = edge["target"]

        adjacency[a].add(b)
        adjacency[b].add(a)

    visited = set()
    components = []

    for node in node_ids:

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

    return components


# =========================================================
# B1 Independent
# =========================================================

def independent_assignment(
    evidence
):

    assignments = {}

    for node_id, distances in (
        evidence.items()
    ):

        if not distances:
            continue

        best = min(
            distances.values()
        )

        best_mods = sorted(
            mod
            for mod, distance
            in distances.items()
            if distance == best
        )

        assignments[
            node_id
        ] = best_mods[0]

    return assignments


# =========================================================
# B2 Original package aggregation
# =========================================================

def package_parent_restricted(
    evidence,
    parent_count
):

    package_scores = defaultdict(
        float
    )

    for node_id, distances in (
        evidence.items()
    ):

        ranked = sorted(
            distances.items(),
            key=lambda x: (
                x[1],
                x[0]
            )
        )

        groups = defaultdict(
            list
        )

        for mod, distance in ranked:
            groups[
                distance
            ].append(mod)

        rank = 1

        for distance in sorted(
            groups.keys()
        ):

            mods = groups[
                distance
            ]

            contribution = (
                1.0 / rank
            )

            for mod in mods:

                package_scores[
                    mod
                ] += contribution

            rank += len(mods)

    selected_parents = [
        mod
        for mod, _
        in sorted(
            package_scores.items(),
            key=lambda x: (
                -x[1],
                x[0]
            )
        )[:parent_count]
    ]

    assignments = {}

    for node_id, distances in (
        evidence.items()
    ):

        candidates = {
            mod:
                distances[mod]
            for mod
            in selected_parents
            if mod in distances
        }

        if not candidates:
            continue

        best = min(
            candidates.values()
        )

        best_mods = sorted(
            mod
            for mod, distance
            in candidates.items()
            if distance == best
        )

        assignments[
            node_id
        ] = best_mods[0]

    return (
        assignments,
        selected_parents
    )


# =========================================================
# B2S Strong graph-agnostic exact baseline
# =========================================================

def exact_global_parentset(
    evidence,
    parent_count
):

    # -----------------------------------------------------
    # Strong graph-agnostic baseline.
    #
    # 가능한 모든 K-parent set 완전탐색.
    #
    # Objective:
    #
    # sum_v min_{p in S} distance(v,p)
    #
    # Query graph / dependency edge는
    # 전혀 사용하지 않는다.
    # -----------------------------------------------------

    candidate_mods = sorted(
        {
            mod
            for distances
            in evidence.values()
            for mod
            in distances.keys()
        }
    )

    if (
        len(candidate_mods)
        < parent_count
    ):
        return {}, []

    best_parent_set = None
    best_cost = None

    for parent_tuple in combinations(
        candidate_mods,
        parent_count
    ):

        total_cost = 0.0
        valid = True

        for node_id, distances in (
            evidence.items()
        ):

            available = [
                distances[parent]
                for parent
                in parent_tuple
                if parent in distances
            ]

            if not available:
                valid = False
                break

            total_cost += min(
                available
            )

        if not valid:
            continue

        if best_cost is None:

            best_cost = total_cost
            best_parent_set = (
                parent_tuple
            )

            continue

        if total_cost < best_cost:

            best_cost = total_cost
            best_parent_set = (
                parent_tuple
            )

            continue

        if (
            math.isclose(
                total_cost,
                best_cost,
                abs_tol=1e-12
            )
            and
            parent_tuple
            < best_parent_set
        ):

            best_cost = total_cost
            best_parent_set = (
                parent_tuple
            )

    if best_parent_set is None:
        return {}, []

    selected_parents = list(
        best_parent_set
    )

    assignments = {}

    for node_id, distances in (
        evidence.items()
    ):

        available = {
            parent:
                distances[parent]
            for parent
            in selected_parents
            if parent in distances
        }

        if not available:
            continue

        best_distance = min(
            available.values()
        )

        best_mods = sorted(
            parent
            for parent, distance
            in available.items()
            if distance
            == best_distance
        )

        assignments[
            node_id
        ] = best_mods[0]

    return (
        assignments,
        selected_parents
    )


# =========================================================
# B3 Dependency
# =========================================================

def dependency_assignment(
    evidence,
    all_node_ids,
    edges
):

    # CONNECTOR에는 content score가 없음.
    # 오직 topology 연결용.

    components = (
        connected_components(
            all_node_ids,
            edges
        )
    )

    assignments = {}
    component_parents = []

    for component in components:

        target_nodes = [
            node
            for node in component
            if node in evidence
        ]

        if not target_nodes:
            continue

        aggregate = defaultdict(
            float
        )

        for node_id in target_nodes:

            distances = evidence[
                node_id
            ]

            best = min(
                distances.values()
            )

            for mod, distance in (
                distances.items()
            ):

                aggregate[mod] += (
                    distance - best
                )

        min_cost = min(
            aggregate.values()
        )

        best_mods = sorted(
            mod
            for mod, cost
            in aggregate.items()
            if math.isclose(
                cost,
                min_cost,
                abs_tol=1e-12
            )
        )

        chosen = best_mods[0]

        component_parents.append(
            chosen
        )

        for node_id in target_nodes:

            assignments[
                node_id
            ] = chosen

    return (
        assignments,
        sorted(
            set(
                component_parents
            )
        )
    )


# =========================================================
# Metrics
# =========================================================

def evaluate_query(
    true_labels,
    true_parents,
    predicted,
    predicted_parents,
):

    target_nodes = list(
        true_labels.keys()
    )

    correct = sum(
        1
        for node in target_nodes
        if predicted.get(node)
        == true_labels[node]
    )

    component_accuracy = (
        correct
        / len(target_nodes)
        if target_nodes
        else 0
    )

    true_set = set(
        true_parents
    )

    pred_set = set(
        predicted_parents
    )

    tp = len(
        true_set
        & pred_set
    )

    precision = (
        tp / len(pred_set)
        if pred_set
        else 0
    )

    recall = (
        tp / len(true_set)
        if true_set
        else 0
    )

    f1 = (
        2
        * precision
        * recall
        / (
            precision
            + recall
        )
        if (
            precision
            + recall
        ) > 0
        else 0
    )

    parent_exact = (
        true_set
        == pred_set
    )

    component_exact = (
        component_accuracy
        == 1.0
    )

    return {
        "component_accuracy":
            component_accuracy,

        "parent_precision":
            precision,

        "parent_recall":
            recall,

        "parent_f1":
            f1,

        "parent_set_exact":
            parent_exact,

        "component_set_exact":
            component_exact,
    }


# =========================================================
# Evaluate all queries
# =========================================================

print()
print(
    "======================================"
)
print(
    "[4/4] Evaluating multi-parent methods"
)
print(
    "======================================"
)


gt_by_id = {
    row["query_id"]:
        row
    for row
    in ground_truth_rows
}


raw_rows = []


for query_index, public_query in (
    enumerate(
        public_queries,
        start=1
    )
):

    query_id = (
        public_query[
            "query_id"
        ]
    )

    gt = (
        gt_by_id[
            query_id
        ]
    )

    true_labels = (
        gt["ground_truth"]
    )

    true_parents = (
        gt["parents"]
    )

    target_node_ids = set(
        true_labels.keys()
    )

    all_node_ids = {
        node["query_node_id"]
        for node
        in public_query["nodes"]
    }

    for rep in REPRESENTATIONS:

        evidence = {}

        for node_id in (
            target_node_ids
        ):

            hidden = (
                gt[
                    "hidden_nodes"
                ][node_id]
            )

            class_name = (
                p3d.path_to_class_name(
                    hidden[
                        "source_path"
                    ]
                )
            )

            key = (
                hidden[
                    "source_mod"
                ],

                hidden[
                    "historical_version_id"
                ],

                class_name,
            )

            distances = (
                distance_cache.get(
                    (
                        key,
                        rep
                    )
                )
            )

            if distances:

                evidence[
                    node_id
                ] = distances

        if (
            len(evidence)
            != len(
                target_node_ids
            )
        ):
            continue


        # ===============================================
        # B1 Independent
        # ===============================================

        independent = (
            independent_assignment(
                evidence
            )
        )

        independent_parents = sorted(
            set(
                independent.values()
            )
        )

        metrics = evaluate_query(
            true_labels,
            true_parents,
            independent,
            independent_parents,
        )

        raw_rows.append({
            "query_id":
                query_id,

            "parent_count":
                public_query[
                    "parent_count"
                ],

            "representation":
                rep,

            "method":
                "B1_INDEPENDENT",

            **metrics,
        })


        # ===============================================
        # B2 Original package aggregation
        # ===============================================

        (
            package_assignments,
            package_parents
        ) = (
            package_parent_restricted(
                evidence,
                public_query[
                    "parent_count"
                ],
            )
        )

        metrics = evaluate_query(
            true_labels,
            true_parents,
            package_assignments,
            package_parents,
        )

        raw_rows.append({
            "query_id":
                query_id,

            "parent_count":
                public_query[
                    "parent_count"
                ],

            "representation":
                rep,

            "method":
                "B2_PACKAGE_AGGREGATION",

            **metrics,
        })


        # ===============================================
        # B2S Strong exact global parent-set search
        # ===============================================

        (
            exact_assignments,
            exact_parents
        ) = (
            exact_global_parentset(
                evidence,
                public_query[
                    "parent_count"
                ],
            )
        )

        metrics = evaluate_query(
            true_labels,
            true_parents,
            exact_assignments,
            exact_parents,
        )

        raw_rows.append({
            "query_id":
                query_id,

            "parent_count":
                public_query[
                    "parent_count"
                ],

            "representation":
                rep,

            "method":
                "B2_EXACT_GLOBAL",

            **metrics,
        })


        # ===============================================
        # B3 Dependency
        # ===============================================

        (
            dependency_predictions,
            dependency_parents
        ) = (
            dependency_assignment(
                evidence,
                all_node_ids,
                public_query[
                    "edges"
                ],
            )
        )

        metrics = evaluate_query(
            true_labels,
            true_parents,
            dependency_predictions,
            dependency_parents,
        )

        raw_rows.append({
            "query_id":
                query_id,

            "parent_count":
                public_query[
                    "parent_count"
                ],

            "representation":
                rep,

            "method":
                "B3_DEPENDENCY",

            **metrics,
        })


    if query_index % 25 == 0:

        print(
            f"evaluated "
            f"{query_index}/"
            f"{len(public_queries)}"
        )


raw = pd.DataFrame(
    raw_rows
)


# =========================================================
# Summary
# =========================================================

summary_rows = []


for (
    representation,
    method,
    parent_count
), group in raw.groupby(
    [
        "representation",
        "method",
        "parent_count",
    ]
):

    summary_rows.append({
        "representation":
            representation,

        "method":
            method,

        "parent_count":
            int(parent_count),

        "queries":
            len(group),

        "component_accuracy":
            float(
                group[
                    "component_accuracy"
                ].mean()
            ),

        "parent_precision":
            float(
                group[
                    "parent_precision"
                ].mean()
            ),

        "parent_recall":
            float(
                group[
                    "parent_recall"
                ].mean()
            ),

        "parent_f1":
            float(
                group[
                    "parent_f1"
                ].mean()
            ),

        "parent_set_exact":
            float(
                group[
                    "parent_set_exact"
                ].mean()
            ),

        "component_set_exact":
            float(
                group[
                    "component_set_exact"
                ].mean()
            ),
    })


# ALL parent counts

for (
    representation,
    method
), group in raw.groupby(
    [
        "representation",
        "method",
    ]
):

    summary_rows.append({
        "representation":
            representation,

        "method":
            method,

        "parent_count":
            "ALL",

        "queries":
            len(group),

        "component_accuracy":
            float(
                group[
                    "component_accuracy"
                ].mean()
            ),

        "parent_precision":
            float(
                group[
                    "parent_precision"
                ].mean()
            ),

        "parent_recall":
            float(
                group[
                    "parent_recall"
                ].mean()
            ),

        "parent_f1":
            float(
                group[
                    "parent_f1"
                ].mean()
            ),

        "parent_set_exact":
            float(
                group[
                    "parent_set_exact"
                ].mean()
            ),

        "component_set_exact":
            float(
                group[
                    "component_set_exact"
                ].mean()
            ),
    })


summary_df = pd.DataFrame(
    summary_rows
)


# =========================================================
# Save strong-baseline results
# =========================================================

raw.to_csv(
    RESULT_ROOT
    / "multiparent_evaluation_strong_raw.csv",

    index=False,
    encoding="utf-8-sig",
)


summary_df.to_csv(
    RESULT_ROOT
    / "multiparent_evaluation_strong_summary.csv",

    index=False,
    encoding="utf-8-sig",
)


# =========================================================
# Compact JSON
# =========================================================

compact = {}


all_rows = summary_df[
    summary_df["parent_count"]
    == "ALL"
]


for representation in (
    REPRESENTATIONS
):

    compact[
        representation
    ] = {}

    rep_rows = all_rows[
        all_rows[
            "representation"
        ]
        == representation
    ]

    for _, row in (
        rep_rows.iterrows()
    ):

        compact[
            representation
        ][
            row["method"]
        ] = {
            "queries":
                int(
                    row[
                        "queries"
                    ]
                ),

            "component_accuracy":
                float(
                    row[
                        "component_accuracy"
                    ]
                ),

            "parent_precision":
                float(
                    row[
                        "parent_precision"
                    ]
                ),

            "parent_recall":
                float(
                    row[
                        "parent_recall"
                    ]
                ),

            "parent_f1":
                float(
                    row[
                        "parent_f1"
                    ]
                ),

            "parent_set_exact":
                float(
                    row[
                        "parent_set_exact"
                    ]
                ),

            "component_set_exact":
                float(
                    row[
                        "component_set_exact"
                    ]
                ),
        }


(
    RESULT_ROOT
    / "phase5c2_summary.json"
).write_text(
    json.dumps(
        compact,
        ensure_ascii=False,
        indent=2
    ),
    encoding="utf-8"
)


# =========================================================
# Console result
# =========================================================

print()
print(
    "======================================"
)
print(
    "RESULT"
)
print(
    "======================================"
)

print(
    json.dumps(
        compact,
        ensure_ascii=False,
        indent=2
    )
)

print()
print(
    "Raw     : "
    "results\\multiparent_evaluation_strong_raw.csv"
)

print(
    "Summary : "
    "results\\multiparent_evaluation_strong_summary.csv"
)

print(
    "JSON    : "
    "results\\phase5c2_summary.json"
)

print()
print(
    "Public benchmark : "
    "data\\benchmark\\multiparent_queries_h3_public.jsonl"
)

print(
    "Ground truth     : "
    "data\\benchmark\\multiparent_queries_h3_ground_truth.jsonl"
)