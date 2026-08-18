import hashlib
import json
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd


# =========================================================
# Project root
# =========================================================

ROOT = Path(__file__).resolve().parent.parent


# =========================================================
# Inputs
# =========================================================

PHASE7B_EXTRACTOR = (
    ROOT
    / "scripts"
    / "phase7b_extract_identity_neutral_evidence.py"
)

PHASE7B_QUERY_EVIDENCE_CSV = (
    ROOT
    / "results"
    / "phase7b_query_identity_neutral_evidence.csv"
)

PHASE7H_QUERY_PREDICTIONS_CSV = (
    ROOT
    / "results"
    / "phase7h_final_query_predictions.csv"
)

PHASE9E_PACKAGE_MANIFEST_CSV = (
    ROOT
    / "results"
    / "phase9e_package_manifest.csv"
)

PHASE9E_MATERIALIZATION_SUMMARY_JSON = (
    ROOT
    / "results"
    / "phase9e_package_materialization_summary.json"
)


# =========================================================
# Outputs
# =========================================================

OUTPUT_COMPONENT_AUDIT_CSV = (
    ROOT
    / "results"
    / "phase9e2_evidence_regeneration_audit.csv"
)

OUTPUT_TIMING_CSV = (
    ROOT
    / "results"
    / "phase9e2_evidence_extraction_timing.csv"
)

OUTPUT_SUMMARY_JSON = (
    ROOT
    / "results"
    / "phase9e2_evidence_regeneration_summary.json"
)


# =========================================================
# Expected frozen benchmark
# =========================================================

EXPECTED_QUERIES = 360
EXPECTED_COMPONENTS = 2520

EXPECTED_MODALITY_COUNTS = {
    "CODE_BINARY": 1800,
    "STRUCTURED": 360,
    "IMAGE": 360,
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


def sha256_bytes(data):

    return hashlib.sha256(
        data
    ).hexdigest()


def percentile(values, q):

    values = np.asarray(
        values,
        dtype=np.float64,
    )

    if len(values) == 0:
        return None

    return float(
        np.percentile(
            values,
            q,
        )
    )


# =========================================================
# Validate required files
# =========================================================

for path in [
    PHASE7B_EXTRACTOR,
    PHASE7B_QUERY_EVIDENCE_CSV,
    PHASE7H_QUERY_PREDICTIONS_CSV,
    PHASE9E_PACKAGE_MANIFEST_CSV,
    PHASE9E_MATERIALIZATION_SUMMARY_JSON,
]:

    if not path.exists():

        raise FileNotFoundError(
            f"Missing required file: {path}"
        )


# =========================================================
# Validate Phase 9E-1
# =========================================================

phase9e1_summary = json.loads(
    PHASE9E_MATERIALIZATION_SUMMARY_JSON.read_text(
        encoding="utf-8"
    )
)


if not phase9e1_summary.get(
    "goals_met",
    False,
):

    raise RuntimeError(
        "Phase 9E-1 package materialization did not pass"
    )


if int(
    phase9e1_summary[
        "queries"
    ]
) != EXPECTED_QUERIES:

    raise RuntimeError(
        "Phase 9E-1 query count mismatch"
    )


if int(
    phase9e1_summary[
        "components"
    ]
) != EXPECTED_COMPONENTS:

    raise RuntimeError(
        "Phase 9E-1 component count mismatch"
    )


# =========================================================
# Load EXACT Phase 7B extractor definitions
#
# We deliberately DO NOT import the module because the
# original Phase 7B script executes the full extraction
# pipeline at module import time.
#
# Instead, we execute the original source only through
# the extractor-definition section immediately before:
#
#     # Load registries
#
# No Phase 7B extractor logic is reimplemented here.
# =========================================================

print(
    "======================================"
)

print(
    "Phase 9E-2 - Raw Evidence Regeneration"
)

print(
    "======================================"
)

print()

print(
    "Loading frozen Phase 7B extractor definitions..."
)


phase7b_source = PHASE7B_EXTRACTOR.read_text(
    encoding="utf-8"
)


split_marker = (
    "# =========================================================\n"
    "# Load registries\n"
    "# ========================================================="
)


if split_marker not in phase7b_source:

    raise RuntimeError(
        "Could not locate '# Load registries' marker "
        "in Phase 7B extractor"
    )


extractor_source = phase7b_source.split(
    split_marker,
    1,
)[0]


extractor_namespace = {
    "__name__":
        "phase7b_extractor_definition_only",

    "__file__":
        str(
            PHASE7B_EXTRACTOR
        ),
}


exec(
    compile(
        extractor_source,
        str(
            PHASE7B_EXTRACTOR
        ),
        "exec",
    ),
    extractor_namespace,
)


if (
    "extract_features"
    not in extractor_namespace
):

    raise RuntimeError(
        "Phase 7B extract_features() was not loaded"
    )


if (
    "SIGNATURE_COLUMNS"
    not in extractor_namespace
):

    raise RuntimeError(
        "Phase 7B SIGNATURE_COLUMNS was not loaded"
    )


extract_features = (
    extractor_namespace[
        "extract_features"
    ]
)

SIGNATURE_COLUMNS = list(
    extractor_namespace[
        "SIGNATURE_COLUMNS"
    ]
)


print(
    "Frozen Phase 7B extractor loaded: PASS"
)

print(
    "Signature fields:",
    len(
        SIGNATURE_COLUMNS
    )
)


# =========================================================
# Load Phase 7B reference evidence
# =========================================================

reference_evidence = pd.read_csv(
    PHASE7B_QUERY_EVIDENCE_CSV,
    dtype=str,
    keep_default_na=False,
)


final_queries = pd.read_csv(
    PHASE7H_QUERY_PREDICTIONS_CSV,
    dtype=str,
    keep_default_na=False,
)


package_manifest = pd.read_csv(
    PHASE9E_PACKAGE_MANIFEST_CSV,
    dtype=str,
    keep_default_na=False,
)


test_query_ids = set(
    final_queries[
        "query_id"
    ].astype(str)
)


if len(
    test_query_ids
) != EXPECTED_QUERIES:

    raise RuntimeError(
        "Expected 360 Phase 7H TEST query IDs"
    )


reference_test = reference_evidence[
    reference_evidence[
        "query_id"
    ].astype(str).isin(
        test_query_ids
    )
].copy()


if len(
    reference_test
) != EXPECTED_COMPONENTS:

    raise RuntimeError(
        "Expected 2520 TEST reference evidence rows, "
        f"got {len(reference_test)}"
    )


if len(
    package_manifest
) != EXPECTED_QUERIES:

    raise RuntimeError(
        "Expected 360 Phase 9E packages"
    )


# =========================================================
# Build exact Phase 7B reference map
# =========================================================

reference_map = {}


for row in reference_test.itertuples(
    index=False
):

    query_id = clean_text(
        row.query_id
    )

    node_id = clean_text(
        row.node_id
    )

    key = (
        query_id,
        node_id,
    )


    if key in reference_map:

        raise RuntimeError(
            f"Duplicate reference evidence: {key}"
        )


    record = {
        "modality":
            clean_text(
                row.modality
            )
    }


    for column in SIGNATURE_COLUMNS:

        record[
            column
        ] = clean_text(
            getattr(
                row,
                column
            )
        )


    reference_map[
        key
    ] = record


if len(
    reference_map
) != EXPECTED_COMPONENTS:

    raise RuntimeError(
        "Reference evidence map count mismatch"
    )


# =========================================================
# Comparison rules
#
# Phase 7B CSV contains numeric values as strings after
# pandas serialization. Regenerated extractor values are
# Python ints/strings.
#
# Compare numeric signature columns numerically and all
# hash/parse-kind/histogram fields exactly as text.
# =========================================================

INTEGER_COLUMNS = {
    "code_method_count",
    "code_instruction_count",
    "code_major_version",
    "structured_token_count",
    "image_width",
    "image_height",
    "image_frames",
}


TEXT_COLUMNS = set(
    SIGNATURE_COLUMNS
) - INTEGER_COLUMNS


def compare_signature_value(
    column,
    reference_value,
    regenerated_value,
):

    reference_value = clean_text(
        reference_value
    )


    regenerated_value = clean_text(
        regenerated_value
    )


    # Empty field must remain empty.
    if (
        reference_value == ""
        or
        regenerated_value == ""
    ):

        return bool(
            reference_value
            ==
            regenerated_value
        )


    if column in INTEGER_COLUMNS:

        try:

            return bool(
                int(
                    float(
                        reference_value
                    )
                )
                ==
                int(
                    float(
                        regenerated_value
                    )
                )
            )

        except Exception:

            return False


    return bool(
        reference_value
        ==
        regenerated_value
    )


# =========================================================
# Regenerate all 2520 TEST components directly from
# Phase 9E archive payload bytes
# =========================================================

audit_rows = []
timing_rows = []


query_count = 0
component_count = 0

payload_sha_matches = 0
signature_matches = 0

field_comparisons = 0
field_matches = 0


modality_counts = {
    "CODE_BINARY": 0,
    "STRUCTURED": 0,
    "IMAGE": 0,
}


modality_signature_matches = {
    "CODE_BINARY": 0,
    "STRUCTURED": 0,
    "IMAGE": 0,
}


field_mismatch_counts = {
    column: 0
    for column in SIGNATURE_COLUMNS
}


archive_parse_times = []
extraction_times = []
total_component_times = []


for package_index, package_row in enumerate(
    package_manifest.sort_values(
        "query_id",
        kind="stable",
    ).itertuples(
        index=False
    ),
    start=1,
):

    if (
        package_index == 1
        or
        package_index % 30 == 0
    ):

        print(
            "package",
            package_index,
            "/",
            EXPECTED_QUERIES,
        )


    query_id = clean_text(
        package_row.query_id
    )


    package_path = Path(
        clean_text(
            package_row.package_path
        )
    )


    if not package_path.is_absolute():

        package_path = (
            ROOT
            /
            package_path
        )


    if not package_path.exists():

        raise FileNotFoundError(
            f"Package not found: {package_path}"
        )


    package_start = (
        time.perf_counter_ns()
    )


    with zipfile.ZipFile(
        package_path,
        mode="r",
    ) as archive:

        manifest_start = (
            time.perf_counter_ns()
        )


        package_metadata = json.loads(
            archive.read(
                "manifest.json"
            ).decode(
                "utf-8"
            )
        )


        manifest_end = (
            time.perf_counter_ns()
        )


        if clean_text(
            package_metadata.get(
                "query_id"
            )
        ) != query_id:

            raise RuntimeError(
                f"{query_id}: package manifest query mismatch"
            )


        components_meta = package_metadata.get(
            "components",
            []
        )


        if len(
            components_meta
        ) != 7:

            raise RuntimeError(
                f"{query_id}: expected 7 archive components"
            )


        query_count += 1


        for component in components_meta:

            component_start = (
                time.perf_counter_ns()
            )


            node_id = clean_text(
                component[
                    "node_id"
                ]
            )


            modality = clean_text(
                component[
                    "modality"
                ]
            )


            archive_path = clean_text(
                component[
                    "archive_path"
                ]
            )


            expected_payload_sha = clean_text(
                component[
                    "payload_sha256"
                ]
            ).lower()


            key = (
                query_id,
                node_id,
            )


            if key not in reference_map:

                raise RuntimeError(
                    f"Reference evidence missing: {key}"
                )


            reference = reference_map[
                key
            ]


            if (
                reference[
                    "modality"
                ]
                !=
                modality
            ):

                raise RuntimeError(
                    f"{query_id}/{node_id}: "
                    "modality mismatch between package "
                    "and Phase 7B reference"
                )


            # ---------------------------------------------
            # Archive payload read
            # ---------------------------------------------

            read_start = (
                time.perf_counter_ns()
            )


            raw = archive.read(
                archive_path
            )


            read_end = (
                time.perf_counter_ns()
            )


            actual_payload_sha = (
                sha256_bytes(
                    raw
                )
            )


            payload_sha_match = bool(
                actual_payload_sha
                ==
                expected_payload_sha
            )


            payload_sha_matches += int(
                payload_sha_match
            )


            if not payload_sha_match:

                raise RuntimeError(
                    f"{query_id}/{node_id}: "
                    "archive payload SHA mismatch"
                )


            # ---------------------------------------------
            # EXACT Phase 7B extraction
            # ---------------------------------------------

            extraction_start = (
                time.perf_counter_ns()
            )


            regenerated = extract_features(
                modality,
                raw,
            )


            extraction_end = (
                time.perf_counter_ns()
            )


            component_field_matches = {}
            mismatched_fields = []


            for column in SIGNATURE_COLUMNS:

                is_match = (
                    compare_signature_value(
                        column,
                        reference[
                            column
                        ],
                        regenerated.get(
                            column,
                            "",
                        ),
                    )
                )


                component_field_matches[
                    column
                ] = is_match


                field_comparisons += 1
                field_matches += int(
                    is_match
                )


                if not is_match:

                    mismatched_fields.append(
                        column
                    )

                    field_mismatch_counts[
                        column
                    ] += 1


            full_signature_match = bool(
                len(
                    mismatched_fields
                )
                ==
                0
            )


            signature_matches += int(
                full_signature_match
            )


            modality_counts[
                modality
            ] += 1


            modality_signature_matches[
                modality
            ] += int(
                full_signature_match
            )


            component_end = (
                time.perf_counter_ns()
            )


            archive_read_ms = (
                read_end
                -
                read_start
            ) / 1_000_000.0


            extraction_ms = (
                extraction_end
                -
                extraction_start
            ) / 1_000_000.0


            component_total_ms = (
                component_end
                -
                component_start
            ) / 1_000_000.0


            archive_parse_times.append(
                archive_read_ms
            )


            extraction_times.append(
                extraction_ms
            )


            total_component_times.append(
                component_total_ms
            )


            timing_rows.append({
                "query_id":
                    query_id,

                "node_id":
                    node_id,

                "modality":
                    modality,

                "payload_size_bytes":
                    int(
                        len(
                            raw
                        )
                    ),

                "archive_read_ms":
                    float(
                        archive_read_ms
                    ),

                "evidence_extraction_ms":
                    float(
                        extraction_ms
                    ),

                "component_total_ms":
                    float(
                        component_total_ms
                    ),
            })


            audit_rows.append({
                "query_id":
                    query_id,

                "node_id":
                    node_id,

                "modality":
                    modality,

                "payload_sha_match":
                    payload_sha_match,

                "full_signature_match":
                    full_signature_match,

                "mismatched_fields":
                    "|".join(
                        mismatched_fields
                    ),
            })


            component_count += 1


    package_end = (
        time.perf_counter_ns()
    )


# =========================================================
# DataFrames
# =========================================================

audit_df = pd.DataFrame(
    audit_rows
)


timing_df = pd.DataFrame(
    timing_rows
)


if query_count != EXPECTED_QUERIES:

    raise RuntimeError(
        f"Expected 360 packages, got {query_count}"
    )


if component_count != EXPECTED_COMPONENTS:

    raise RuntimeError(
        f"Expected 2520 components, got {component_count}"
    )


if modality_counts != EXPECTED_MODALITY_COUNTS:

    raise RuntimeError(
        "Unexpected modality counts: "
        + json.dumps(
            modality_counts
        )
    )


# =========================================================
# Aggregate correctness
# =========================================================

mismatch_components = (
    EXPECTED_COMPONENTS
    -
    signature_matches
)


payload_sha_mismatches = (
    EXPECTED_COMPONENTS
    -
    payload_sha_matches
)


correctness_passed = bool(
    query_count
    == EXPECTED_QUERIES

    and

    component_count
    == EXPECTED_COMPONENTS

    and

    payload_sha_matches
    == EXPECTED_COMPONENTS

    and

    signature_matches
    == EXPECTED_COMPONENTS

    and

    field_matches
    == field_comparisons
)


# =========================================================
# Timing stats
#
# Diagnostic only.
# Phase 9E-3 will perform the actual end-to-end server
# benchmark.
# =========================================================

timing_summary = {}


for modality in [
    "CODE_BINARY",
    "STRUCTURED",
    "IMAGE",
]:

    subset = timing_df[
        timing_df[
            "modality"
        ]
        ==
        modality
    ]


    values = (
        subset[
            "evidence_extraction_ms"
        ]
        .astype(float)
        .to_numpy()
    )


    timing_summary[
        modality
    ] = {
        "components":
            int(
                len(
                    subset
                )
            ),

        "mean_ms":
            float(
                np.mean(
                    values
                )
            ),

        "p50_ms":
            percentile(
                values,
                50,
            ),

        "p95_ms":
            percentile(
                values,
                95,
            ),

        "p99_ms":
            percentile(
                values,
                99,
            ),

        "max_ms":
            float(
                np.max(
                    values
                )
            ),
    }


overall_extraction = timing_df[
    "evidence_extraction_ms"
].astype(float).to_numpy()


overall_archive_read = timing_df[
    "archive_read_ms"
].astype(float).to_numpy()


# =========================================================
# Save
# =========================================================

OUTPUT_COMPONENT_AUDIT_CSV.parent.mkdir(
    parents=True,
    exist_ok=True,
)


audit_df.to_csv(
    OUTPUT_COMPONENT_AUDIT_CSV,
    index=False,
    encoding="utf-8-sig",
)


timing_df.to_csv(
    OUTPUT_TIMING_CSV,
    index=False,
    encoding="utf-8-sig",
)


summary = {
    "phase9e2_complete":
        True,

    "scope":
        (
            "RAW_ARCHIVE_PAYLOAD_TO_"
            "IDENTITY_NEUTRAL_EVIDENCE_"
            "REGENERATION_CORRECTNESS"
        ),

    "extractor_reuse": {
        "source":
            (
                "scripts/"
                "phase7b_extract_identity_neutral_evidence.py"
            ),

        "reimplemented":
            False,

        "definition_loading_method":
            (
                "execute original Phase 7B source "
                "through the '# Load registries' marker"
            ),

        "same_extract_features_function":
            True,
    },

    "expected": {
        "queries":
            EXPECTED_QUERIES,

        "components":
            EXPECTED_COMPONENTS,

        "modality_counts":
            EXPECTED_MODALITY_COUNTS,
    },

    "observed": {
        "queries":
            int(
                query_count
            ),

        "components":
            int(
                component_count
            ),

        "modality_counts":
            {
                key:
                    int(
                        value
                    )

                for key, value
                in modality_counts.items()
            },
    },

    "payload_integrity": {
        "sha256_matches":
            int(
                payload_sha_matches
            ),

        "sha256_mismatches":
            int(
                payload_sha_mismatches
            ),
    },

    "signature_correctness": {
        "fully_identical_components":
            int(
                signature_matches
            ),

        "mismatched_components":
            int(
                mismatch_components
            ),

        "field_comparisons":
            int(
                field_comparisons
            ),

        "field_matches":
            int(
                field_matches
            ),

        "field_mismatch_counts":
            {
                key:
                    int(
                        value
                    )

                for key, value
                in field_mismatch_counts.items()
            },

        "by_modality": {
            modality: {
                "components":
                    int(
                        modality_counts[
                            modality
                        ]
                    ),

                "fully_identical":
                    int(
                        modality_signature_matches[
                            modality
                        ]
                    ),

                "mismatches":
                    int(
                        modality_counts[
                            modality
                        ]
                        -
                        modality_signature_matches[
                            modality
                        ]
                    ),
            }

            for modality
            in EXPECTED_MODALITY_COUNTS
        },
    },

    "timing_diagnostic_not_final_benchmark": {
        "warning":
            (
                "These are sequential offline extraction "
                "diagnostics only. Publication-ready "
                "end-to-end latency is measured in "
                "Phase 9E-3."
            ),

        "archive_payload_read_ms": {
            "mean":
                float(
                    np.mean(
                        overall_archive_read
                    )
                ),

            "p50":
                percentile(
                    overall_archive_read,
                    50,
                ),

            "p95":
                percentile(
                    overall_archive_read,
                    95,
                ),

            "p99":
                percentile(
                    overall_archive_read,
                    99,
                ),
        },

        "evidence_extraction_ms": {
            "mean":
                float(
                    np.mean(
                        overall_extraction
                    )
                ),

            "p50":
                percentile(
                    overall_extraction,
                    50,
                ),

            "p95":
                percentile(
                    overall_extraction,
                    95,
                ),

            "p99":
                percentile(
                    overall_extraction,
                    99,
                ),

            "by_modality":
                timing_summary,
        },
    },

    "correctness_passed":
        correctness_passed,

    "ready_for_phase9e3":
        correctness_passed,

    "goals_met":
        correctness_passed,
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
    "PHASE 9E-2 FINAL RESULT"
)

print(
    "======================================"
)

print(
    "Packages:",
    query_count,
    "/",
    EXPECTED_QUERIES,
)

print(
    "Components:",
    component_count,
    "/",
    EXPECTED_COMPONENTS,
)

print(
    "Payload SHA:",
    payload_sha_matches,
    "/",
    EXPECTED_COMPONENTS,
)

print(
    "Evidence identical:",
    signature_matches,
    "/",
    EXPECTED_COMPONENTS,
)

print()

print(
    "By modality:"
)

for modality in [
    "CODE_BINARY",
    "STRUCTURED",
    "IMAGE",
]:

    print(
        modality,
        modality_signature_matches[
            modality
        ],
        "/",
        modality_counts[
            modality
        ],
    )


print()

print(
    "Mismatched components:",
    mismatch_components
)

print(
    "CORRECTNESS PASSED:",
    correctness_passed
)

print(
    "READY FOR 9E-3:",
    correctness_passed
)

print()

print(
    "Audit:",
    OUTPUT_COMPONENT_AUDIT_CSV
)

print(
    "Timing:",
    OUTPUT_TIMING_CSV
)

print(
    "Summary:",
    OUTPUT_SUMMARY_JSON
)