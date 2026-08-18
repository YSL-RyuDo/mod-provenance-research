import hashlib
import json
from collections import defaultdict
from pathlib import Path

import pandas as pd


# =========================================================
# Config
# =========================================================

SEED = 20260812

QUERIES_PER_SCENARIO = 60


FRAGMENT_CSV = Path(
    "results/"
    "phase6g_h5_fragment_catalog.csv"
)

AVAILABILITY_CSV = Path(
    "results/"
    "phase6h_heterogeneous_availability.csv"
)

HARD_CSV = Path(
    "results/"
    "phase6e_hard_candidate_catalog.csv"
)

HISTORICAL_CSV = Path(
    "data/fresh_registry/"
    "fresh_historical_component_registry_filtered.csv"
)

CURRENT_CSV = Path(
    "data/fresh_registry/"
    "fresh_current_component_registry_filtered.csv"
)


OUTPUT_PRIVATE_CSV = Path(
    "results/"
    "phase6k_query_manifest_private.csv"
)

OUTPUT_PUBLIC_CSV = Path(
    "results/"
    "phase6k_query_manifest_public.csv"
)

OUTPUT_QUERY_CSV = Path(
    "results/"
    "phase6k_query_ground_truth.csv"
)

OUTPUT_SUMMARY_JSON = Path(
    "results/"
    "phase6k_query_summary.json"
)


# =========================================================
# Frozen modality composition
# =========================================================

CODE_PER_QUERY = 5
STRUCTURED_PER_QUERY = 1
IMAGE_PER_QUERY = 1

TOTAL_COMPONENTS = 7


# =========================================================
# Frozen scenarios
# =========================================================

CALIBRATION_SCENARIOS = [
    {
        "name": "CAL_KNOWN_K1",
        "k_true": 1,
        "known_parents": 1,
        "unknown_parents": 0,
        "count": QUERIES_PER_SCENARIO,
    },
    {
        "name": "CAL_KNOWN_K2",
        "k_true": 2,
        "known_parents": 2,
        "unknown_parents": 0,
        "count": QUERIES_PER_SCENARIO,
    },
    {
        "name": "CAL_KNOWN_K3",
        "k_true": 3,
        "known_parents": 3,
        "unknown_parents": 0,
        "count": QUERIES_PER_SCENARIO,
    },
]


TEST_SCENARIOS = [
    {
        "name": "TEST_KNOWN_K1",
        "k_true": 1,
        "known_parents": 1,
        "unknown_parents": 0,
        "count": QUERIES_PER_SCENARIO,
    },
    {
        "name": "TEST_KNOWN_K2",
        "k_true": 2,
        "known_parents": 2,
        "unknown_parents": 0,
        "count": QUERIES_PER_SCENARIO,
    },
    {
        "name": "TEST_KNOWN_K3",
        "k_true": 3,
        "known_parents": 3,
        "unknown_parents": 0,
        "count": QUERIES_PER_SCENARIO,
    },
    {
        "name": "TEST_MIXED_1K1U",
        "k_true": 2,
        "known_parents": 1,
        "unknown_parents": 1,
        "count": QUERIES_PER_SCENARIO,
    },
    {
        "name": "TEST_MIXED_2K1U",
        "k_true": 3,
        "known_parents": 2,
        "unknown_parents": 1,
        "count": QUERIES_PER_SCENARIO,
    },
    {
        "name": "TEST_UNKNOWN_K1",
        "k_true": 1,
        "known_parents": 0,
        "unknown_parents": 1,
        "count": QUERIES_PER_SCENARIO,
    },
]


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


def as_bool(value):

    if isinstance(value, bool):
        return value

    return (
        clean_text(value).lower()
        in {
            "1",
            "true",
            "yes",
            "y",
        }
    )


def stable_digest(text):

    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def stable_order(
    values,
    salt,
):

    return sorted(
        values,
        key=lambda value: (
            stable_digest(
                f"{SEED}|{salt}|{value}"
            ),
            str(value),
        ),
    )


def choose_distinct(
    values,
    count,
    salt,
):

    ordered = stable_order(
        list(values),
        salt,
    )

    if len(ordered) < count:

        raise RuntimeError(
            f"Need {count} distinct values, "
            f"but only {len(ordered)} available "
            f"for {salt}"
        )

    return ordered[:count]


# =========================================================
# Load
# =========================================================

for path in [
    FRAGMENT_CSV,
    AVAILABILITY_CSV,
    HARD_CSV,
    HISTORICAL_CSV,
    CURRENT_CSV,
]:

    if not path.exists():

        raise FileNotFoundError(
            f"Missing: {path}"
        )


fragments = pd.read_csv(
    FRAGMENT_CSV
)

availability = pd.read_csv(
    AVAILABILITY_CSV
)

hard = pd.read_csv(
    HARD_CSV
)

historical = pd.read_csv(
    HISTORICAL_CSV
)

current = pd.read_csv(
    CURRENT_CSV
)


for df in [
    fragments,
    availability,
    hard,
    historical,
    current,
]:

    df["fresh_id"] = (
        df["fresh_id"]
        .astype(str)
    )


for df in [
    fragments,
    availability,
    hard,
    historical,
]:

    df["version_id"] = (
        df["version_id"]
        .astype(str)
    )


print(
    "======================================"
)

print(
    "Phase 6K - Final Component Query Freeze"
)

print(
    "======================================"
)


# =========================================================
# Full heterogeneous eligible fragments
# =========================================================

availability[
    "eligible_full_bool"
] = availability[
    "eligible_full_heterogeneous"
].map(
    as_bool
)


eligible_meta = availability[
    availability[
        "eligible_full_bool"
    ]
].copy()


eligible_fragment_ids = set(
    eligible_meta[
        "fragment_id"
    ].astype(str)
)


fragment_targets = fragments[
    (
        fragments[
            "fragment_id"
        ].astype(str)
        .isin(
            eligible_fragment_ids
        )
    )
    &
    (
        fragments[
            "evaluation_role"
        ]
        == "TARGET"
    )
].copy()


# =========================================================
# Validate each fragment has exactly five code TARGETs
# =========================================================

target_counts = (
    fragment_targets
    .groupby(
        "fragment_id"
    )
    .size()
)


bad_fragments = (
    target_counts[
        target_counts
        != 5
    ]
)


if len(bad_fragments):

    raise RuntimeError(
        "Some eligible fragments do not "
        "contain exactly five TARGET nodes: "
        + str(
            bad_fragments.to_dict()
        )
    )


# =========================================================
# Fragment metadata
# =========================================================

fragment_info = (
    eligible_meta[
        [
            "fragment_id",
            "fresh_id",
            "frozen_split",
            "version_id",
            "version_number",
            "variant_index",
        ]
    ]
    .drop_duplicates(
        subset=[
            "fragment_id"
        ]
    )
    .copy()
)


# =========================================================
# Hard STRUCTURED lookup
# =========================================================

hard_structured = hard[
    hard[
        "modality"
    ]
    == "STRUCTURED"
].copy()


structured_by_release = defaultdict(
    list
)


for row in hard_structured.itertuples(
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


    structured_by_release[
        key
    ].append({
        "relative_path":
            clean_text(
                row.relative_path
            ),

        "component_sha256":
            clean_text(
                row.component_sha256
            ),
    })


# =========================================================
# Exact-surviving IMAGE lookup
# =========================================================

current_images = current[
    current[
        "modality"
    ]
    == "IMAGE"
].copy()


current_image_hashes = defaultdict(
    set
)


for row in current_images.itertuples(
    index=False
):

    current_image_hashes[
        clean_text(
            row.fresh_id
        )
    ].add(
        clean_text(
            row.component_sha256
        )
    )


historical_images = historical[
    historical[
        "modality"
    ]
    == "IMAGE"
].copy()


images_by_release = defaultdict(
    list
)


for row in historical_images.itertuples(
    index=False
):

    fresh_id = clean_text(
        row.fresh_id
    )

    digest = clean_text(
        row.component_sha256
    )


    if (
        digest
        not in current_image_hashes[
            fresh_id
        ]
    ):

        continue


    key = (
        fresh_id,
        clean_text(
            row.version_id
        ),
    )


    images_by_release[
        key
    ].append({
        "relative_path":
            clean_text(
                row.relative_path
            ),

        "component_sha256":
            digest,
    })


# =========================================================
# Fragment record pool
# =========================================================

records_by_parent = defaultdict(
    list
)


for row in fragment_info.itertuples(
    index=False
):

    fragment_id = clean_text(
        row.fragment_id
    )

    fresh_id = clean_text(
        row.fresh_id
    )

    version_id = clean_text(
        row.version_id
    )

    split_name = clean_text(
        row.frozen_split
    )


    code_rows = (
        fragment_targets[
            fragment_targets[
                "fragment_id"
            ].astype(str)
            == fragment_id
        ]
        .copy()
    )


    if len(code_rows) != 5:
        continue


    release_key = (
        fresh_id,
        version_id,
    )


    structured_options = (
        structured_by_release.get(
            release_key,
            []
        )
    )


    image_options = (
        images_by_release.get(
            release_key,
            []
        )
    )


    if (
        len(structured_options) < 1
        or
        len(image_options) < 1
    ):

        continue


    code_options = []


    for code_row in (
        code_rows.itertuples(
            index=False
        )
    ):

        code_options.append({
            "relative_path":
                clean_text(
                    code_row.source_relative_path
                ),

            "component_sha256":
                clean_text(
                    code_row.component_sha256
                ),

            "fragment_node_id":
                clean_text(
                    code_row.node_id
                ),
        })


    records_by_parent[
        fresh_id
    ].append({
        "fragment_id":
            fragment_id,

        "fresh_id":
            fresh_id,

        "frozen_split":
            split_name,

        "version_id":
            version_id,

        "version_number":
            clean_text(
                row.version_number
            ),

        "variant_index":
            int(
                row.variant_index
            ),

        "code_options":
            code_options,

        "structured_options":
            structured_options,

        "image_options":
            image_options,
    })


# =========================================================
# Parent pools
# =========================================================

def parents_for_split(
    split_name
):

    return sorted(
        fresh_id

        for fresh_id, records
        in records_by_parent.items()

        if any(
            record[
                "frozen_split"
            ]
            == split_name

            for record
            in records
        )
    )


calibration_known_parents = (
    parents_for_split(
        "CALIBRATION_KNOWN"
    )
)

test_known_parents = (
    parents_for_split(
        "TEST_KNOWN"
    )
)

unknown_parents = (
    parents_for_split(
        "UNKNOWN_HELDOUT"
    )
)


print(
    "Calibration known parents:",
    len(
        calibration_known_parents
    )
)

print(
    "Test known parents:",
    len(
        test_known_parents
    )
)

print(
    "Unknown parents:",
    len(
        unknown_parents
    )
)


if len(calibration_known_parents) < 15:

    raise RuntimeError(
        "Calibration parent pool < 15"
    )


if len(test_known_parents) < 15:

    raise RuntimeError(
        "Test known parent pool < 15"
    )


if len(unknown_parents) < 15:

    raise RuntimeError(
        "Unknown parent pool < 15"
    )


# =========================================================
# Record selection
# =========================================================

def choose_record(
    fresh_id,
    query_id,
):

    records = records_by_parent[
        fresh_id
    ]


    ordered = sorted(
        records,
        key=lambda record: stable_digest(
            f"{SEED}|"
            f"{query_id}|"
            f"{fresh_id}|"
            f"{record['fragment_id']}"
        ),
    )


    return ordered[
        0
    ]


# =========================================================
# Code allocation
# =========================================================

def code_allocation(
    k_true
):

    if k_true == 1:
        return [5]

    if k_true == 2:
        return [3, 2]

    if k_true == 3:
        return [2, 2, 1]

    raise ValueError(
        f"Unsupported K: {k_true}"
    )


# =========================================================
# Query generation
# =========================================================

private_rows = []

public_rows = []

query_rows = []


query_counter = 0


def generate_query(
    stage,
    scenario,
    query_index,
):

    global query_counter


    query_counter += 1


    query_id = (
        f"Q6K{query_counter:05d}"
    )


    scenario_name = (
        scenario[
            "name"
        ]
    )

    k_true = int(
        scenario[
            "k_true"
        ]
    )

    known_needed = int(
        scenario[
            "known_parents"
        ]
    )

    unknown_needed = int(
        scenario[
            "unknown_parents"
        ]
    )


    # -----------------------------------------------------
    # Parent pools
    # -----------------------------------------------------

    if stage == "CALIBRATION":

        known_pool = (
            calibration_known_parents
        )

    else:

        known_pool = (
            test_known_parents
        )


    selected_known = (
        choose_distinct(
            known_pool,
            known_needed,
            (
                f"{scenario_name}|"
                f"{query_index}|"
                "known"
            ),
        )

        if known_needed

        else []
    )


    selected_unknown = (
        choose_distinct(
            unknown_parents,
            unknown_needed,
            (
                f"{scenario_name}|"
                f"{query_index}|"
                "unknown"
            ),
        )

        if unknown_needed

        else []
    )


    selected_parents = (
        selected_known
        +
        selected_unknown
    )


    if (
        len(
            set(
                selected_parents
            )
        )
        != k_true
    ):

        raise RuntimeError(
            "Parent-count invariant failed"
        )


    # -----------------------------------------------------
    # Randomized deterministic parent order.
    #
    # This determines which parent receives 3/2/1 code
    # components. It prevents KNOWN/UNKNOWN type from
    # systematically receiving a larger contribution.
    # -----------------------------------------------------

    parent_order = stable_order(
        selected_parents,
        (
            f"{query_id}|"
            "parent-order"
        ),
    )


    allocations = (
        code_allocation(
            k_true
        )
    )


    parent_code_counts = dict(
        zip(
            parent_order,
            allocations,
        )
    )


    # -----------------------------------------------------
    # Choose one eligible historical fragment per parent
    # -----------------------------------------------------

    selected_records = {}


    for fresh_id in (
        selected_parents
    ):

        selected_records[
            fresh_id
        ] = choose_record(
            fresh_id,
            query_id,
        )


    # -----------------------------------------------------
    # Choose which parent supplies STRUCTURED / IMAGE.
    #
    # This is deterministic but independent of K class.
    # -----------------------------------------------------

    structured_parent = (
        stable_order(
            selected_parents,
            (
                f"{query_id}|"
                "structured-parent"
            ),
        )[0]
    )


    image_parent = (
        stable_order(
            selected_parents,
            (
                f"{query_id}|"
                "image-parent"
            ),
        )[0]
    )


    components = []


    # -----------------------------------------------------
    # CODE_BINARY
    # -----------------------------------------------------

    for fresh_id in (
        parent_order
    ):

        record = (
            selected_records[
                fresh_id
            ]
        )


        count = (
            parent_code_counts[
                fresh_id
            ]
        )


        ordered_code = stable_order(
            range(
                len(
                    record[
                        "code_options"
                    ]
                )
            ),
            (
                f"{query_id}|"
                f"{fresh_id}|"
                "code"
            ),
        )


        chosen_indices = (
            ordered_code[
                :count
            ]
        )


        for option_index in (
            chosen_indices
        ):

            option = (
                record[
                    "code_options"
                ][
                    option_index
                ]
            )


            components.append({
                "modality":
                    "CODE_BINARY",

                "source_fresh_id":
                    fresh_id,

                "source_version_id":
                    record[
                        "version_id"
                    ],

                "source_version_number":
                    record[
                        "version_number"
                    ],

                "source_fragment_id":
                    record[
                        "fragment_id"
                    ],

                "source_fragment_node_id":
                    option[
                        "fragment_node_id"
                    ],

                "source_relative_path":
                    option[
                        "relative_path"
                    ],

                "source_component_sha256":
                    option[
                        "component_sha256"
                    ],

                "transform_recipe":
                    "NONE",
            })


    # -----------------------------------------------------
    # STRUCTURED
    # -----------------------------------------------------

    record = (
        selected_records[
            structured_parent
        ]
    )


    structured_indices = stable_order(
        range(
            len(
                record[
                    "structured_options"
                ]
            )
        ),
        (
            f"{query_id}|"
            f"{structured_parent}|"
            "structured"
        ),
    )


    structured_option = (
        record[
            "structured_options"
        ][
            structured_indices[
                0
            ]
        ]
    )


    components.append({
        "modality":
            "STRUCTURED",

        "source_fresh_id":
            structured_parent,

        "source_version_id":
            record[
                "version_id"
            ],

        "source_version_number":
            record[
                "version_number"
            ],

        "source_fragment_id":
            record[
                "fragment_id"
            ],

        "source_fragment_node_id":
            "",

        "source_relative_path":
            structured_option[
                "relative_path"
            ],

        "source_component_sha256":
            structured_option[
                "component_sha256"
            ],

        "transform_recipe":
            "NONE",
    })


    # -----------------------------------------------------
    # IMAGE
    #
    # The actual image transformation is materialized
    # in Phase 6L.
    # -----------------------------------------------------

    record = (
        selected_records[
            image_parent
        ]
    )


    image_indices = stable_order(
        range(
            len(
                record[
                    "image_options"
                ]
            )
        ),
        (
            f"{query_id}|"
            f"{image_parent}|"
            "image"
        ),
    )


    image_option = (
        record[
            "image_options"
        ][
            image_indices[
                0
            ]
        ]
    )


    components.append({
        "modality":
            "IMAGE",

        "source_fresh_id":
            image_parent,

        "source_version_id":
            record[
                "version_id"
            ],

        "source_version_number":
            record[
                "version_number"
            ],

        "source_fragment_id":
            record[
                "fragment_id"
            ],

        "source_fragment_node_id":
            "",

        "source_relative_path":
            image_option[
                "relative_path"
            ],

        "source_component_sha256":
            image_option[
                "component_sha256"
            ],

        "transform_recipe":
            "LOSSLESS_REENCODE_PNG_V1",
    })


    # -----------------------------------------------------
    # Invariants
    # -----------------------------------------------------

    if len(components) != TOTAL_COMPONENTS:

        raise RuntimeError(
            "Query does not contain "
            "exactly 7 components"
        )


    modality_counts = (
        pd.Series(
            [
                component[
                    "modality"
                ]
                for component
                in components
            ]
        )
        .value_counts()
        .to_dict()
    )


    expected_counts = {
        "CODE_BINARY":
            CODE_PER_QUERY,

        "STRUCTURED":
            STRUCTURED_PER_QUERY,

        "IMAGE":
            IMAGE_PER_QUERY,
    }


    if modality_counts != expected_counts:

        raise RuntimeError(
            f"Bad modality composition: "
            f"{query_id} "
            f"{modality_counts}"
        )


    component_parent_set = set(
        component[
            "source_fresh_id"
        ]
        for component
        in components
    )


    if len(component_parent_set) != k_true:

        raise RuntimeError(
            f"Component parent count != K "
            f"for {query_id}"
        )


    # -----------------------------------------------------
    # Query-level private GT
    # -----------------------------------------------------

    unknown_parent_set = set(
        selected_unknown
    )


    query_rows.append({
        "query_id":
            query_id,

        "stage":
            stage,

        "scenario":
            scenario_name,

        "k_true":
            k_true,

        "known_parent_count":
            known_needed,

        "unknown_parent_count":
            unknown_needed,

        "known_parent_ids":
            json.dumps(
                sorted(
                    selected_known
                )
            ),

        "unknown_parent_ids":
            json.dumps(
                sorted(
                    selected_unknown
                )
            ),

        "all_parent_ids":
            json.dumps(
                sorted(
                    selected_parents
                )
            ),

        "component_count":
            TOTAL_COMPONENTS,

        "code_count":
            CODE_PER_QUERY,

        "structured_count":
            STRUCTURED_PER_QUERY,

        "image_count":
            IMAGE_PER_QUERY,
    })


    # -----------------------------------------------------
    # Component manifests
    # -----------------------------------------------------

    component_order = stable_order(
        range(
            len(
                components
            )
        ),
        (
            f"{query_id}|"
            "public-node-order"
        ),
    )


    for public_index, source_index in enumerate(
        component_order,
        start=1,
    ):

        component = (
            components[
                source_index
            ]
        )


        node_id = (
            f"{query_id}_"
            f"N{public_index:02d}"
        )


        fresh_id = (
            component[
                "source_fresh_id"
            ]
        )


        ground_truth_label = (
            "UNKNOWN"

            if fresh_id
            in unknown_parent_set

            else fresh_id
        )


        private_rows.append({
            "query_id":
                query_id,

            "node_id":
                node_id,

            "stage":
                stage,

            "scenario":
                scenario_name,

            "k_true":
                k_true,

            "modality":
                component[
                    "modality"
                ],

            "ground_truth_label":
                ground_truth_label,

            "source_fresh_id":
                fresh_id,

            "source_version_id":
                component[
                    "source_version_id"
                ],

            "source_version_number":
                component[
                    "source_version_number"
                ],

            "source_fragment_id":
                component[
                    "source_fragment_id"
                ],

            "source_fragment_node_id":
                component[
                    "source_fragment_node_id"
                ],

            "source_relative_path":
                component[
                    "source_relative_path"
                ],

            "source_component_sha256":
                component[
                    "source_component_sha256"
                ],

            "transform_recipe":
                component[
                    "transform_recipe"
                ],
        })


        # PUBLIC VIEW:
        #
        # No K
        # No scenario
        # No source identity
        # No source path
        # No source hash
        # No version identity
        public_rows.append({
            "query_id":
                query_id,

            "node_id":
                node_id,

            "modality":
                component[
                    "modality"
                ],

            "payload_key":
                node_id,

            "transform_applied":
                bool(
                    component[
                        "transform_recipe"
                    ]
                    != "NONE"
                ),
        })


# =========================================================
# Generate calibration queries
# =========================================================

for scenario in (
    CALIBRATION_SCENARIOS
):

    for query_index in range(
        scenario[
            "count"
        ]
    ):

        generate_query(
            "CALIBRATION",
            scenario,
            query_index,
        )


# =========================================================
# Generate final test queries
# =========================================================

for scenario in (
    TEST_SCENARIOS
):

    for query_index in range(
        scenario[
            "count"
        ]
    ):

        generate_query(
            "TEST",
            scenario,
            query_index,
        )


# =========================================================
# DataFrames
# =========================================================

private_df = pd.DataFrame(
    private_rows
)

public_df = pd.DataFrame(
    public_rows
)

query_df = pd.DataFrame(
    query_rows
)


# =========================================================
# Global safety checks
# =========================================================

expected_calibration_queries = (
    sum(
        scenario[
            "count"
        ]
        for scenario
        in CALIBRATION_SCENARIOS
    )
)


expected_test_queries = (
    sum(
        scenario[
            "count"
        ]
        for scenario
        in TEST_SCENARIOS
    )
)


if (
    len(
        query_df[
            query_df[
                "stage"
            ]
            == "CALIBRATION"
        ]
    )
    != expected_calibration_queries
):

    raise RuntimeError(
        "Wrong calibration query count"
    )


if (
    len(
        query_df[
            query_df[
                "stage"
            ]
            == "TEST"
        ]
    )
    != expected_test_queries
):

    raise RuntimeError(
        "Wrong test query count"
    )


counts_per_query = (
    public_df
    .groupby(
        "query_id"
    )
    .size()
)


if not (
    counts_per_query
    == TOTAL_COMPONENTS
).all():

    raise RuntimeError(
        "Public query-size leakage check failed"
    )


# =========================================================
# Public-column leakage check
# =========================================================

forbidden_public_tokens = [
    "source",
    "path",
    "sha",
    "version",
    "parent",
    "k_true",
    "scenario",
    "ground_truth",
]


for column in (
    public_df.columns
):

    lower = (
        column.lower()
    )


    for token in (
        forbidden_public_tokens
    ):

        if token in lower:

            raise RuntimeError(
                "Forbidden information in "
                f"public manifest column: "
                f"{column}"
            )


# =========================================================
# Save
# =========================================================

OUTPUT_PRIVATE_CSV.parent.mkdir(
    parents=True,
    exist_ok=True,
)


private_df.to_csv(
    OUTPUT_PRIVATE_CSV,
    index=False,
    encoding="utf-8-sig",
)


public_df.to_csv(
    OUTPUT_PUBLIC_CSV,
    index=False,
    encoding="utf-8-sig",
)


query_df.to_csv(
    OUTPUT_QUERY_CSV,
    index=False,
    encoding="utf-8-sig",
)


# =========================================================
# Summary
# =========================================================

scenario_summary = {}


for scenario_name, group in (
    query_df.groupby(
        "scenario"
    )
):

    scenario_summary[
        str(
            scenario_name
        )
    ] = {
        "queries":
            int(
                len(
                    group
                )
            ),

        "k_true":
            sorted(
                set(
                    int(v)
                    for v
                    in group[
                        "k_true"
                    ]
                )
            ),

        "known_parent_count":
            sorted(
                set(
                    int(v)
                    for v
                    in group[
                        "known_parent_count"
                    ]
                )
            ),

        "unknown_parent_count":
            sorted(
                set(
                    int(v)
                    for v
                    in group[
                        "unknown_parent_count"
                    ]
                )
            ),
    }


test_k_counts = (
    query_df[
        query_df[
            "stage"
        ]
        == "TEST"
    ][
        "k_true"
    ]
    .value_counts()
    .sort_index()
    .to_dict()
)


summary = {
    "component_query_manifest_frozen":
        True,

    "random_seed":
        SEED,

    "performance_evaluated":
        False,

    "thresholds_tuned":
        False,

    "fixed_query_component_count":
        TOTAL_COMPONENTS,

    "fixed_modality_composition": {
        "CODE_BINARY":
            CODE_PER_QUERY,

        "STRUCTURED":
            STRUCTURED_PER_QUERY,

        "IMAGE":
            IMAGE_PER_QUERY,
    },

    "calibration_queries":
        int(
            expected_calibration_queries
        ),

    "test_queries":
        int(
            expected_test_queries
        ),

    "total_queries":
        int(
            len(
                query_df
            )
        ),

    "test_k_distribution": {
        str(k):
            int(v)
        for k, v
        in test_k_counts.items()
    },

    "scenario_summary":
        scenario_summary,

    "eligible_parent_pools": {
        "CALIBRATION_KNOWN":
            int(
                len(
                    calibration_known_parents
                )
            ),

        "TEST_KNOWN":
            int(
                len(
                    test_known_parents
                )
            ),

        "UNKNOWN_HELDOUT":
            int(
                len(
                    unknown_parents
                )
            ),
    },

    "unknown_design": (
        "at most one held-out UNKNOWN source per query; "
        "multiple unseen-source clustering is outside "
        "the primary benchmark"
    ),

    "image_transform_recipe":
        "LOSSLESS_REENCODE_PNG_V1",

    "public_manifest_exposes_K":
        False,

    "public_manifest_exposes_scenario":
        False,

    "public_manifest_exposes_source_identity":
        False,

    "public_manifest_exposes_path":
        False,

    "public_manifest_exposes_source_hash":
        False,

    "graph_frozen":
        False,

    "payloads_materialized":
        False,

    "goals_met":
        bool(
            expected_calibration_queries
            == 180

            and
            expected_test_queries
            == 360

            and
            test_k_counts.get(
                1,
                0
            )
            == 120

            and
            test_k_counts.get(
                2,
                0
            )
            == 120

            and
            test_k_counts.get(
                3,
                0
            )
            == 120

            and
            len(
                unknown_parents
            )
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
# Print
# =========================================================

print()

print(
    "======================================"
)

print(
    "PHASE 6K RESULT"
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
    OUTPUT_PRIVATE_CSV
)

print(
    "Public manifest :",
    OUTPUT_PUBLIC_CSV
)

print(
    "Query GT        :",
    OUTPUT_QUERY_CSV
)

print(
    "Summary         :",
    OUTPUT_SUMMARY_JSON
)