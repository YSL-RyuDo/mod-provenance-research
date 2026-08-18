import hashlib
import io
import json
import shutil
import zipfile
from collections import defaultdict, deque
from pathlib import Path

import pandas as pd

try:
    from PIL import Image
    from PIL.PngImagePlugin import PngInfo
except ImportError:
    raise RuntimeError(
        "Pillow is required. Run:\n"
        "python -m pip install pillow"
    )


# =========================================================
# Config
# =========================================================

PRIVATE_MANIFEST_CSV = Path(
    "results/"
    "phase6k_query_manifest_private.csv"
)

PUBLIC_MANIFEST_CSV = Path(
    "results/"
    "phase6k_query_manifest_public.csv"
)

QUERY_GT_CSV = Path(
    "results/"
    "phase6k_query_ground_truth.csv"
)

HISTORICAL_PACKAGE_CSV = Path(
    "data/fresh_registry/"
    "fresh_historical_package_registry.csv"
)

CURRENT_COMPONENT_CSV = Path(
    "data/fresh_registry/"
    "fresh_current_component_registry_filtered.csv"
)

SPLIT_CSV = Path(
    "results/"
    "phase6c_project_split.csv"
)

FRAGMENT_EDGE_CSV = Path(
    "results/"
    "phase6g_h5_fragment_edges.csv"
)


OUTPUT_ROOT = Path(
    "data/"
    "final_benchmark/"
    "queries"
)

OUTPUT_PRIVATE_MANIFEST = Path(
    "results/"
    "phase6l_materialized_private_manifest.csv"
)

OUTPUT_PUBLIC_MANIFEST = Path(
    "results/"
    "phase6l_materialized_public_manifest.csv"
)

OUTPUT_NATURAL_GRAPH = Path(
    "results/"
    "phase6l_graph_natural_public.csv"
)

OUTPUT_STRESS_GRAPH = Path(
    "results/"
    "phase6l_graph_connected_stress_public.csv"
)

OUTPUT_GRAPH_PRIVATE = Path(
    "results/"
    "phase6l_graph_private_audit.csv"
)

OUTPUT_FAILURE_JSON = Path(
    "results/"
    "phase6l_failures.json"
)

OUTPUT_SUMMARY_JSON = Path(
    "results/"
    "phase6l_summary.json"
)


EXPECTED_QUERIES = 540
EXPECTED_COMPONENTS_PER_QUERY = 7

EXPECTED_MODALITY_COUNTS = {
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


def normalize_path(value):

    return (
        clean_text(value)
        .replace("\\", "/")
    )


def sha256_bytes(data):

    return hashlib.sha256(
        data
    ).hexdigest()


def sha256_file(path):

    digest = hashlib.sha256()

    with open(
        path,
        "rb",
    ) as f:

        while True:

            chunk = f.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest()


def stable_digest(text):

    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def stable_order(values, salt):

    return sorted(
        values,
        key=lambda value: (
            stable_digest(
                f"20260812|{salt}|{value}"
            ),
            str(value),
        ),
    )


def canonical_edge(a, b):

    if a == b:
        return None

    if a < b:
        return (a, b)

    return (b, a)


# =========================================================
# PNG pixel-preserving transformation
# =========================================================

def transform_image_to_png(raw_bytes):

    source = Image.open(
        io.BytesIO(
            raw_bytes
        )
    )


    n_frames = getattr(
        source,
        "n_frames",
        1,
    )


    if n_frames != 1:

        raise RuntimeError(
            f"Animated image is not supported: "
            f"frames={n_frames}"
        )


    # Canonical decoded pixel representation.
    rgba = source.convert(
        "RGBA"
    )

    width, height = rgba.size

    source_pixels = (
        rgba.tobytes()
    )


    metadata = PngInfo()

    metadata.add_text(
        "benchmark_transform",
        "LOSSLESS_REENCODE_PNG_V1",
    )


    output = io.BytesIO()


    rgba.save(
        output,
        format="PNG",
        compress_level=6,
        optimize=False,
        pnginfo=metadata,
    )


    transformed = (
        output.getvalue()
    )


    # -----------------------------------------------------
    # Validate decoded pixels.
    # -----------------------------------------------------

    check = Image.open(
        io.BytesIO(
            transformed
        )
    ).convert(
        "RGBA"
    )


    if check.size != (
        width,
        height,
    ):

        raise RuntimeError(
            "Image dimensions changed"
        )


    if (
        check.tobytes()
        != source_pixels
    ):

        raise RuntimeError(
            "Image pixel content changed"
        )


    return (
        transformed,
        width,
        height,
    )


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


    for a, b in edges:

        if (
            a not in adjacency
            or
            b not in adjacency
        ):
            continue

        adjacency[a].add(b)
        adjacency[b].add(a)


    visited = set()
    components = []


    for start in sorted(nodes):

        if start in visited:
            continue

        queue = deque([start])

        visited.add(start)

        component = set()


        while queue:

            node = queue.popleft()

            component.add(node)


            for neighbor in sorted(
                adjacency[node]
            ):

                if neighbor in visited:
                    continue

                visited.add(neighbor)

                queue.append(neighbor)


        components.append(
            component
        )


    return components


def connect_graph_deterministically(
    query_id,
    nodes,
    natural_edges,
):

    stress_edges = set(
        natural_edges
    )

    added_edges = set()


    while True:

        components = (
            connected_components(
                nodes,
                stress_edges,
            )
        )


        if len(components) <= 1:
            break


        # -------------------------------------------------
        # Stable component ordering independent of source
        # labels / K / ground truth.
        # -------------------------------------------------

        component_records = []


        for component in components:

            ordered_nodes = stable_order(
                component,
                (
                    f"{query_id}|"
                    "component-node-order"
                ),
            )

            representative = (
                ordered_nodes[0]
            )


            signature = (
                "|".join(
                    sorted(component)
                )
            )


            component_records.append(
                (
                    stable_digest(
                        f"{query_id}|{signature}"
                    ),
                    representative,
                    component,
                )
            )


        component_records.sort(
            key=lambda item: item[0]
        )


        first = (
            component_records[0]
        )

        second = (
            component_records[1]
        )


        node_a = first[1]
        node_b = second[1]


        edge = canonical_edge(
            node_a,
            node_b,
        )


        if edge is None:

            raise RuntimeError(
                "Invalid stress bridge"
            )


        if edge in stress_edges:

            raise RuntimeError(
                "Bridge unexpectedly already exists"
            )


        stress_edges.add(
            edge
        )

        added_edges.add(
            edge
        )


    return (
        stress_edges,
        added_edges,
    )


# =========================================================
# Load files
# =========================================================

required_files = [
    PRIVATE_MANIFEST_CSV,
    PUBLIC_MANIFEST_CSV,
    QUERY_GT_CSV,
    HISTORICAL_PACKAGE_CSV,
    CURRENT_COMPONENT_CSV,
    SPLIT_CSV,
    FRAGMENT_EDGE_CSV,
]


for path in required_files:

    if not path.exists():

        raise FileNotFoundError(
            f"Missing: {path}"
        )


private_df = pd.read_csv(
    PRIVATE_MANIFEST_CSV
)

public_df = pd.read_csv(
    PUBLIC_MANIFEST_CSV
)

query_gt = pd.read_csv(
    QUERY_GT_CSV
)

packages = pd.read_csv(
    HISTORICAL_PACKAGE_CSV
)

current = pd.read_csv(
    CURRENT_COMPONENT_CSV
)

splits = pd.read_csv(
    SPLIT_CSV
)

fragment_edges = pd.read_csv(
    FRAGMENT_EDGE_CSV
)


for df in [
    private_df,
    packages,
    current,
    splits,
    fragment_edges,
]:

    if "fresh_id" in df.columns:

        df["fresh_id"] = (
            df["fresh_id"]
            .astype(str)
        )


for df in [
    private_df,
    packages,
    fragment_edges,
]:

    if "version_id" in df.columns:

        df["version_id"] = (
            df["version_id"]
            .astype(str)
        )


print(
    "======================================"
)

print(
    "Phase 6L - Materialize + Freeze Graph"
)

print(
    "======================================"
)


# =========================================================
# Validate Phase 6K query structure
# =========================================================

query_ids = sorted(
    private_df[
        "query_id"
    ].astype(str).unique()
)


if len(query_ids) != EXPECTED_QUERIES:

    raise RuntimeError(
        f"Expected {EXPECTED_QUERIES} queries, "
        f"got {len(query_ids)}"
    )


for query_id, group in (
    private_df.groupby(
        "query_id"
    )
):

    if len(group) != EXPECTED_COMPONENTS_PER_QUERY:

        raise RuntimeError(
            f"{query_id}: expected 7 components, "
            f"got {len(group)}"
        )


    counts = (
        group[
            "modality"
        ]
        .value_counts()
        .to_dict()
    )


    if counts != EXPECTED_MODALITY_COUNTS:

        raise RuntimeError(
            f"{query_id}: bad modality counts "
            f"{counts}"
        )


# =========================================================
# Historical package map
# =========================================================

package_map = {}


for row in packages.itertuples(
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


    path = Path(
        clean_text(
            row.local_path
        )
    )


    if key in package_map:

        if package_map[key] != path:

            raise RuntimeError(
                f"Conflicting package path: {key}"
            )


    package_map[key] = path


# =========================================================
# Frozen split map
# =========================================================

split_map = dict(
    zip(
        splits[
            "fresh_id"
        ].astype(str),

        splits[
            "frozen_split"
        ].astype(str),
    )
)


# =========================================================
# Stage gallery exact-hash indexes
# =========================================================

CALIBRATION_GALLERY_SPLITS = {
    "CALIBRATION_KNOWN",
    "CALIBRATION_BACKGROUND",
}

TEST_GALLERY_SPLITS = {
    "TEST_KNOWN",
    "TEST_BACKGROUND",
}


current = current.copy()

current[
    "frozen_split"
] = current[
    "fresh_id"
].map(
    split_map
)


gallery_hashes = {
    "CALIBRATION":
        defaultdict(set),

    "TEST":
        defaultdict(set),
}


for row in current.itertuples(
    index=False
):

    split_name = clean_text(
        row.frozen_split
    )

    modality = clean_text(
        row.modality
    )

    digest = clean_text(
        row.component_sha256
    )

    fresh_id = clean_text(
        row.fresh_id
    )


    stages = []


    if split_name in (
        CALIBRATION_GALLERY_SPLITS
    ):

        stages.append(
            "CALIBRATION"
        )


    if split_name in (
        TEST_GALLERY_SPLITS
    ):

        stages.append(
            "TEST"
        )


    for stage in stages:

        gallery_hashes[
            stage
        ][
            (
                modality,
                digest,
            )
        ].add(
            fresh_id
        )


# =========================================================
# Clean materialized output
# =========================================================

if OUTPUT_ROOT.exists():

    shutil.rmtree(
        OUTPUT_ROOT
    )


OUTPUT_ROOT.mkdir(
    parents=True,
    exist_ok=True,
)


# =========================================================
# Materialize payloads
# =========================================================

materialized_private_rows = []

materialized_public_rows = []

failure_rows = []


source_hash_verified = 0

image_transformed = 0

image_pixel_equal = 0

image_output_hash_changed = 0

exact_gallery_collision_count = 0

collision_by_modality = defaultdict(
    int
)

collision_by_stage = defaultdict(
    int
)


# Cache JAR contents by path to avoid repeatedly opening
# the same JAR for every component.
jar_cache = {}


def read_jar_entry(
    jar_path,
    relative_path,
):

    jar_path_str = str(
        jar_path
    )


    if jar_path_str not in jar_cache:

        jar_cache[
            jar_path_str
        ] = zipfile.ZipFile(
            jar_path,
            "r",
        )


    jar = jar_cache[
        jar_path_str
    ]


    return jar.read(
        relative_path
    )


try:

    total_components = len(
        private_df
    )


    for index, row in enumerate(
        private_df.itertuples(
            index=False
        ),
        start=1,
    ):

        if (
            index == 1
            or
            index % 250 == 0
        ):

            print(
                f"payload "
                f"{index}/"
                f"{total_components}"
            )


        query_id = clean_text(
            row.query_id
        )

        node_id = clean_text(
            row.node_id
        )

        stage = clean_text(
            row.stage
        )

        modality = clean_text(
            row.modality
        )

        fresh_id = clean_text(
            row.source_fresh_id
        )

        version_id = clean_text(
            row.source_version_id
        )

        source_path = normalize_path(
            row.source_relative_path
        )

        expected_source_sha = clean_text(
            row.source_component_sha256
        )

        transform_recipe = clean_text(
            row.transform_recipe
        )


        package_key = (
            fresh_id,
            version_id,
        )


        if package_key not in package_map:

            raise RuntimeError(
                f"Package not found: "
                f"{package_key}"
            )


        jar_path = (
            package_map[
                package_key
            ]
        )


        if not jar_path.exists():

            raise RuntimeError(
                f"JAR missing: "
                f"{jar_path}"
            )


        raw = read_jar_entry(
            jar_path,
            source_path,
        )


        actual_source_sha = (
            sha256_bytes(
                raw
            )
        )


        if (
            actual_source_sha
            != expected_source_sha
        ):

            raise RuntimeError(
                f"Source SHA mismatch: "
                f"{query_id} {node_id}"
            )


        source_hash_verified += 1


        # -------------------------------------------------
        # Materialize transformed/public payload
        # -------------------------------------------------

        width = None
        height = None


        if modality == "IMAGE":

            transformed, width, height = (
                transform_image_to_png(
                    raw
                )
            )


            output_bytes = (
                transformed
            )


            image_transformed += 1


            # Pixel equality is validated inside the
            # transformation function.
            image_pixel_equal += 1


            output_sha = (
                sha256_bytes(
                    output_bytes
                )
            )


            if (
                output_sha
                == actual_source_sha
            ):

                raise RuntimeError(
                    f"Image SHA did not change: "
                    f"{query_id} {node_id}"
                )


            image_output_hash_changed += 1


            filename = (
                f"{node_id}.png"
            )


        else:

            output_bytes = raw

            output_sha = (
                actual_source_sha
            )

            filename = (
                f"{node_id}.bin"
            )


        query_dir = (
            OUTPUT_ROOT
            /
            query_id
        )


        query_dir.mkdir(
            parents=True,
            exist_ok=True,
        )


        output_path = (
            query_dir
            /
            filename
        )


        output_path.write_bytes(
            output_bytes
        )


        # -------------------------------------------------
        # Exact collision against stage gallery
        # -------------------------------------------------

        collision_projects = (
            gallery_hashes[
                stage
            ].get(
                (
                    modality,
                    output_sha,
                ),
                set(),
            )
        )


        exact_collision = bool(
            collision_projects
        )


        if exact_collision:

            exact_gallery_collision_count += 1

            collision_by_modality[
                modality
            ] += 1

            collision_by_stage[
                stage
            ] += 1


        payload_relpath = (
            output_path
            .relative_to(
                OUTPUT_ROOT.parent
            )
            .as_posix()
        )


        materialized_private_rows.append({
            "query_id":
                query_id,

            "node_id":
                node_id,

            "stage":
                stage,

            "scenario":
                clean_text(
                    row.scenario
                ),

            "k_true":
                int(
                    row.k_true
                ),

            "modality":
                modality,

            "ground_truth_label":
                clean_text(
                    row.ground_truth_label
                ),

            "source_fresh_id":
                fresh_id,

            "source_version_id":
                version_id,

            "source_version_number":
                clean_text(
                    row.source_version_number
                ),

            "source_fragment_id":
                clean_text(
                    row.source_fragment_id
                ),

            "source_fragment_node_id":
                clean_text(
                    row.source_fragment_node_id
                ),

            "source_relative_path":
                source_path,

            "source_sha256":
                actual_source_sha,

            "transform_recipe":
                transform_recipe,

            "payload_relpath":
                payload_relpath,

            "payload_sha256":
                output_sha,

            "payload_size_bytes":
                int(
                    len(
                        output_bytes
                    )
                ),

            "image_width":
                width,

            "image_height":
                height,

            "exact_gallery_collision":
                exact_collision,

            "exact_gallery_collision_projects":
                json.dumps(
                    sorted(
                        collision_projects
                    )
                ),
        })


        # PUBLIC view intentionally omits:
        #
        # source project
        # source path
        # source/version hash
        # K
        # scenario
        # ground truth
        # exact collision information
        materialized_public_rows.append({
            "query_id":
                query_id,

            "node_id":
                node_id,

            "modality":
                modality,

            "payload_relpath":
                payload_relpath,

            "transform_applied":
                bool(
                    transform_recipe
                    != "NONE"
                ),
        })


finally:

    for jar in jar_cache.values():

        try:
            jar.close()
        except Exception:
            pass


materialized_private_df = pd.DataFrame(
    materialized_private_rows
)

materialized_public_df = pd.DataFrame(
    materialized_public_rows
)


# =========================================================
# Payload post-validation
# =========================================================

if len(
    materialized_private_df
) != (
    EXPECTED_QUERIES
    *
    EXPECTED_COMPONENTS_PER_QUERY
):

    raise RuntimeError(
        "Wrong number of materialized payloads"
    )


for row in (
    materialized_private_df.itertuples(
        index=False
    )
):

    payload_path = (
        OUTPUT_ROOT.parent
        /
        clean_text(
            row.payload_relpath
        )
    )


    if not payload_path.exists():

        raise RuntimeError(
            f"Materialized payload missing: "
            f"{payload_path}"
        )


    if (
        sha256_file(
            payload_path
        )
        != clean_text(
            row.payload_sha256
        )
    ):

        raise RuntimeError(
            "Materialized payload hash mismatch"
        )


# =========================================================
# Build query CODE node maps
# =========================================================

code_private = materialized_private_df[
    materialized_private_df[
        "modality"
    ]
    == "CODE_BINARY"
].copy()


# source fragment node -> public query node
query_fragment_node_map = defaultdict(
    dict
)


for row in code_private.itertuples(
    index=False
):

    query_id = clean_text(
        row.query_id
    )

    fragment_id = clean_text(
        row.source_fragment_id
    )

    fragment_node_id = clean_text(
        row.source_fragment_node_id
    )

    query_node_id = clean_text(
        row.node_id
    )


    if not fragment_node_id:

        raise RuntimeError(
            f"Missing fragment node ID: "
            f"{query_id}"
        )


    query_fragment_node_map[
        query_id
    ][
        (
            fragment_id,
            fragment_node_id,
        )
    ] = query_node_id


# =========================================================
# Fragment-edge lookup
# =========================================================

fragment_edge_lookup = defaultdict(
    list
)


for row in fragment_edges.itertuples(
    index=False
):

    fragment_id = clean_text(
        row.fragment_id
    )


    fragment_edge_lookup[
        fragment_id
    ].append(
        (
            clean_text(
                row.source_node_id
            ),
            clean_text(
                row.target_node_id
            ),
        )
    )


# =========================================================
# Freeze NATURAL + CONNECTED_STRESS graph
# =========================================================

natural_public_rows = []

stress_public_rows = []

graph_private_rows = []


natural_cc_counts = defaultdict(
    int
)

stress_cc_counts = defaultdict(
    int
)

stress_added_edge_counts = []

queries_with_stress_bridges = 0


query_gt_map = (
    query_gt
    .set_index(
        "query_id"
    )
    .to_dict(
        orient="index"
    )
)


for query_index, query_id in enumerate(
    query_ids,
    start=1,
):

    if (
        query_index == 1
        or
        query_index % 100 == 0
    ):

        print(
            f"graph "
            f"{query_index}/"
            f"{len(query_ids)}"
        )


    query_code = code_private[
        code_private[
            "query_id"
        ].astype(str)
        == query_id
    ]


    code_nodes = set(
        query_code[
            "node_id"
        ].astype(str)
    )


    if len(code_nodes) != 5:

        raise RuntimeError(
            f"{query_id}: expected 5 code nodes"
        )


    mapping = (
        query_fragment_node_map[
            query_id
        ]
    )


    # -----------------------------------------------------
    # NATURAL graph:
    # original CLASS_REF only when both selected query
    # nodes were endpoints in the same source fragment.
    # -----------------------------------------------------

    natural_edges = set()


    fragment_ids = set(
        fragment_id
        for (
            fragment_id,
            fragment_node_id
        )
        in mapping.keys()
    )


    for fragment_id in (
        fragment_ids
    ):

        for (
            source_fragment_node,
            target_fragment_node
        ) in fragment_edge_lookup.get(
            fragment_id,
            []
        ):

            source_query_node = (
                mapping.get(
                    (
                        fragment_id,
                        source_fragment_node,
                    )
                )
            )

            target_query_node = (
                mapping.get(
                    (
                        fragment_id,
                        target_fragment_node,
                    )
                )
            )


            if (
                not source_query_node
                or
                not target_query_node
            ):

                continue


            edge = canonical_edge(
                source_query_node,
                target_query_node,
            )


            if edge is not None:

                natural_edges.add(
                    edge
                )


    natural_components = (
        connected_components(
            code_nodes,
            natural_edges,
        )
    )


    natural_cc = len(
        natural_components
    )


    # -----------------------------------------------------
    # CONNECTED_STRESS
    #
    # Add the minimum number of deterministic bridges
    # required to make the 5-code-node graph connected.
    #
    # IMPORTANT:
    # This function uses public graph structure + query ID,
    # NOT source labels or true K.
    # -----------------------------------------------------

    (
        stress_edges,
        added_edges,
    ) = connect_graph_deterministically(
        query_id,
        code_nodes,
        natural_edges,
    )


    stress_components = (
        connected_components(
            code_nodes,
            stress_edges,
        )
    )


    stress_cc = len(
        stress_components
    )


    if stress_cc != 1:

        raise RuntimeError(
            f"{query_id}: stress graph "
            f"is not connected"
        )


    if added_edges:

        queries_with_stress_bridges += 1


    stress_added_edge_counts.append(
        len(
            added_edges
        )
    )


    query_info = (
        query_gt_map[
            query_id
        ]
    )


    k_true = int(
        query_info[
            "k_true"
        ]
    )


    natural_cc_counts[
        (
            k_true,
            natural_cc,
        )
    ] += 1


    stress_cc_counts[
        (
            k_true,
            stress_cc,
        )
    ] += 1


    # -----------------------------------------------------
    # Public NATURAL graph
    # -----------------------------------------------------

    for node_a, node_b in sorted(
        natural_edges
    ):

        natural_public_rows.append({
            "query_id":
                query_id,

            "node_a":
                node_a,

            "node_b":
                node_b,
        })


    # -----------------------------------------------------
    # Public CONNECTED_STRESS graph
    #
    # edge origin is intentionally hidden.
    # -----------------------------------------------------

    for node_a, node_b in sorted(
        stress_edges
    ):

        stress_public_rows.append({
            "query_id":
                query_id,

            "node_a":
                node_a,

            "node_b":
                node_b,
        })


    # -----------------------------------------------------
    # Private audit keeps origin only for analysis.
    # -----------------------------------------------------

    for node_a, node_b in sorted(
        stress_edges
    ):

        origin = (
            "NATURAL_CLASS_REF"
            if (
                node_a,
                node_b,
            )
            in natural_edges

            else
            "SYNTHETIC_CONNECTIVITY_BRIDGE"
        )


        graph_private_rows.append({
            "query_id":
                query_id,

            "k_true":
                k_true,

            "node_a":
                node_a,

            "node_b":
                node_b,

            "edge_origin":
                origin,
        })


natural_df = pd.DataFrame(
    natural_public_rows,
    columns=[
        "query_id",
        "node_a",
        "node_b",
    ],
)

stress_df = pd.DataFrame(
    stress_public_rows,
    columns=[
        "query_id",
        "node_a",
        "node_b",
    ],
)

graph_private_df = pd.DataFrame(
    graph_private_rows
)


# =========================================================
# Public leakage validation
# =========================================================

for df_name, df in [
    (
        "materialized_public",
        materialized_public_df,
    ),
    (
        "natural_graph",
        natural_df,
    ),
    (
        "stress_graph",
        stress_df,
    ),
]:

    forbidden_tokens = [
        "source",
        "parent",
        "ground_truth",
        "scenario",
        "k_true",
        "version",
        "sha",
    ]


    for column in df.columns:

        lower = (
            column.lower()
        )


        for token in forbidden_tokens:

            if token in lower:

                raise RuntimeError(
                    f"{df_name}: forbidden "
                    f"public column {column}"
                )


# =========================================================
# Save outputs
# =========================================================

OUTPUT_PRIVATE_MANIFEST.parent.mkdir(
    parents=True,
    exist_ok=True,
)


materialized_private_df.to_csv(
    OUTPUT_PRIVATE_MANIFEST,
    index=False,
    encoding="utf-8-sig",
)

materialized_public_df.to_csv(
    OUTPUT_PUBLIC_MANIFEST,
    index=False,
    encoding="utf-8-sig",
)

natural_df.to_csv(
    OUTPUT_NATURAL_GRAPH,
    index=False,
    encoding="utf-8-sig",
)

stress_df.to_csv(
    OUTPUT_STRESS_GRAPH,
    index=False,
    encoding="utf-8-sig",
)

graph_private_df.to_csv(
    OUTPUT_GRAPH_PRIVATE,
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
# Summary helpers
# =========================================================

def cc_dict(
    counter
):

    result = {}


    for (
        k_true,
        cc
    ), count in sorted(
        counter.items()
    ):

        k_key = str(
            k_true
        )

        cc_key = str(
            cc
        )


        result.setdefault(
            k_key,
            {}
        )


        result[
            k_key
        ][
            cc_key
        ] = int(
            count
        )


    return result


# =========================================================
# Summary
# =========================================================

query_payload_files = list(
    OUTPUT_ROOT.rglob("*")
)


query_payload_files = [
    path
    for path
    in query_payload_files
    if path.is_file()
]


summary = {
    "phase6l_complete":
        True,

    "component_query_manifest_remains_frozen":
        True,

    "performance_evaluated":
        False,

    "thresholds_tuned":
        False,

    "queries":
        int(
            len(
                query_ids
            )
        ),

    "materialized_payloads":
        int(
            len(
                materialized_private_df
            )
        ),

    "payload_files_on_disk":
        int(
            len(
                query_payload_files
            )
        ),

    "source_hash_verified":
        int(
            source_hash_verified
        ),

    "image_payloads":
        int(
            image_transformed
        ),

    "image_pixel_equality_verified":
        int(
            image_pixel_equal
        ),

    "image_output_hash_changed":
        int(
            image_output_hash_changed
        ),

    "exact_stage_gallery_collisions":
        int(
            exact_gallery_collision_count
        ),

    "exact_gallery_collisions_by_modality": {
        str(k):
            int(v)
        for k, v
        in collision_by_modality.items()
    },

    "exact_gallery_collisions_by_stage": {
        str(k):
            int(v)
        for k, v
        in collision_by_stage.items()
    },

    "graph_tracks": {
        "NATURAL": (
            "undirected dependency adjacency among "
            "selected CODE_BINARY query components "
            "using original historical CLASS_REF edges"
        ),

        "CONNECTED_STRESS": (
            "NATURAL graph plus minimum deterministic "
            "bridges required to make all five CODE "
            "query nodes connected; bridge construction "
            "does not use parent labels or K and edge "
            "origin is hidden from the public method"
        ),
    },

    "primary_graph_track":
        "CONNECTED_STRESS",

    "natural_graph_edges":
        int(
            len(
                natural_df
            )
        ),

    "connected_stress_graph_edges":
        int(
            len(
                stress_df
            )
        ),

    "queries_with_stress_bridges":
        int(
            queries_with_stress_bridges
        ),

    "mean_stress_bridges_per_query":
        float(
            sum(
                stress_added_edge_counts
            )
            /
            len(
                stress_added_edge_counts
            )
        )
        if stress_added_edge_counts
        else 0.0,

    "max_stress_bridges_per_query":
        int(
            max(
                stress_added_edge_counts
            )
        )
        if stress_added_edge_counts
        else 0,

    "natural_connected_components_by_k":
        cc_dict(
            natural_cc_counts
        ),

    "stress_connected_components_by_k":
        cc_dict(
            stress_cc_counts
        ),

    "stress_all_queries_connected":
        bool(
            all(
                cc == 1
                for (
                    k,
                    cc
                )
                in stress_cc_counts.keys()
            )
        ),

    "public_payload_manifest_exposes_source_identity":
        False,

    "public_graph_exposes_edge_origin":
        False,

    "public_graph_exposes_K":
        False,

    "payloads_materialized":
        True,

    "graph_frozen":
        True,

    "goals_met":
        bool(
            len(
                query_ids
            )
            == EXPECTED_QUERIES

            and

            len(
                materialized_private_df
            )
            == (
                EXPECTED_QUERIES
                *
                EXPECTED_COMPONENTS_PER_QUERY
            )

            and

            source_hash_verified
            == (
                EXPECTED_QUERIES
                *
                EXPECTED_COMPONENTS_PER_QUERY
            )

            and

            image_transformed
            == EXPECTED_QUERIES

            and

            image_pixel_equal
            == EXPECTED_QUERIES

            and

            image_output_hash_changed
            == EXPECTED_QUERIES

            and

            all(
                cc == 1
                for (
                    k,
                    cc
                )
                in stress_cc_counts.keys()
            )

            and

            len(
                failure_rows
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
# Result
# =========================================================

print()

print(
    "======================================"
)

print(
    "PHASE 6L RESULT"
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
    "Private manifest:",
    OUTPUT_PRIVATE_MANIFEST
)

print(
    "Public manifest :",
    OUTPUT_PUBLIC_MANIFEST
)

print(
    "Natural graph   :",
    OUTPUT_NATURAL_GRAPH
)

print(
    "Stress graph    :",
    OUTPUT_STRESS_GRAPH
)

print(
    "Private graph   :",
    OUTPUT_GRAPH_PRIVATE
)

print(
    "Failures        :",
    OUTPUT_FAILURE_JSON
)

print(
    "Summary         :",
    OUTPUT_SUMMARY_JSON
)