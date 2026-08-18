import json
import os
import time
import zipfile

from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import psutil

from fastapi import FastAPI, HTTPException

from server.phase9a_server import (
    AnalyzeRequest,
    ComponentInput,
    GraphEdgeInput,
    ParentScore,
    analyze_internal,
)

import server.phase9d_evidence_server as phase9d


# =========================================================
# Root / paths
# =========================================================

ROOT = Path(__file__).resolve().parent.parent

PHASE7B_EXTRACTOR = (
    ROOT
    / "scripts"
    / "phase7b_extract_identity_neutral_evidence.py"
)

PACKAGE_MANIFEST_CSV = (
    ROOT
    / "results"
    / "phase9e_package_manifest.csv"
)

PHASE9E2_SUMMARY_JSON = (
    ROOT
    / "results"
    / "phase9e2_evidence_regeneration_summary.json"
)


# =========================================================
# Constants
# =========================================================

EXPECTED_QUERIES = 360
EXPECTED_COMPONENTS_PER_QUERY = 7

EXPECTED_COMPOSITION = {
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


# =========================================================
# Validate Phase 9E-2
# =========================================================

for path in [
    PHASE7B_EXTRACTOR,
    PACKAGE_MANIFEST_CSV,
    PHASE9E2_SUMMARY_JSON,
]:

    if not path.exists():

        raise FileNotFoundError(
            path
        )


phase9e2 = json.loads(
    PHASE9E2_SUMMARY_JSON.read_text(
        encoding="utf-8"
    )
)


if not phase9e2.get(
    "correctness_passed",
    False,
):

    raise RuntimeError(
        "Phase 9E-2 correctness did not pass"
    )


if not phase9e2.get(
    "ready_for_phase9e3",
    False,
):

    raise RuntimeError(
        "Phase 9E-2 did not approve Phase 9E-3"
    )


# =========================================================
# Load EXACT Phase 7B extractor definitions
# =========================================================

print(
    "Loading frozen Phase 7B extractor..."
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
        "Could not locate Phase 7B "
        "'# Load registries' marker"
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


if "extract_features" not in extractor_namespace:

    raise RuntimeError(
        "Phase 7B extract_features() not loaded"
    )


extract_features = (
    extractor_namespace[
        "extract_features"
    ]
)


print(
    "Frozen Phase 7B extractor: READY"
)


# =========================================================
# Package registry
# =========================================================

package_manifest = pd.read_csv(
    PACKAGE_MANIFEST_CSV,
    dtype=str,
    keep_default_na=False,
)


if len(
    package_manifest
) != EXPECTED_QUERIES:

    raise RuntimeError(
        "Expected 360 Phase 9E packages"
    )


package_by_query = {}


for row in package_manifest.itertuples(
    index=False
):

    query_id = clean_text(
        row.query_id
    )


    package_path = Path(
        clean_text(
            row.package_path
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
            package_path
        )


    if query_id in package_by_query:

        raise RuntimeError(
            f"Duplicate package query: {query_id}"
        )


    package_by_query[
        query_id
    ] = {
        "path":
            package_path,

        "size_bytes":
            int(
                row.package_size_bytes
            ),
    }


if len(
    package_by_query
) != EXPECTED_QUERIES:

    raise RuntimeError(
        "Package map count mismatch"
    )


# =========================================================
# Score regenerated evidence against Phase 9D gallery
# =========================================================

def score_regenerated_component(
    node_id,
    modality,
    features,
):

    evidence_row = SimpleNamespace(
        modality=modality,
        **features,
    )


    (
        fused_parent_distance,
        mean_regret,
    ) = phase9d.score_component(
        evidence_row
    )


    parent_scores = []


    for project_index in range(
        phase9d.PROJECT_COUNT
    ):

        parent_scores.append(
            ParentScore(
                parent_id=(
                    phase9d.index_to_project[
                        project_index
                    ]
                ),

                fused_parent_distance=float(
                    fused_parent_distance[
                        project_index
                    ]
                ),

                mean_regret=float(
                    mean_regret[
                        project_index
                    ]
                ),
            )
        )


    return ComponentInput(
        node_id=node_id,
        modality=modality,
        parent_scores=parent_scores,
    )


# =========================================================
# Full package pipeline
# =========================================================

def analyze_package_internal(
    query_id,
):

    query_id = str(
        query_id
    )


    if query_id not in package_by_query:

        raise KeyError(
            query_id
        )


    process = psutil.Process(
        os.getpid()
    )


    package_record = (
        package_by_query[
            query_id
        ]
    )


    package_path = (
        package_record[
            "path"
        ]
    )


    rss_before = int(
        process.memory_info().rss
    )


    total_start = (
        time.perf_counter_ns()
    )


    # =====================================================
    # Archive open + manifest parse
    # =====================================================

    archive_start = (
        time.perf_counter_ns()
    )


    archive = zipfile.ZipFile(
        package_path,
        mode="r",
    )


    package_metadata = json.loads(
        archive.read(
            "manifest.json"
        ).decode(
            "utf-8"
        )
    )


    archive_manifest_end = (
        time.perf_counter_ns()
    )


    if clean_text(
        package_metadata.get(
            "query_id"
        )
    ) != query_id:

        archive.close()

        raise RuntimeError(
            "Package query_id mismatch"
        )


    components_meta = (
        package_metadata.get(
            "components",
            []
        )
    )


    if len(
        components_meta
    ) != EXPECTED_COMPONENTS_PER_QUERY:

        archive.close()

        raise RuntimeError(
            f"{query_id}: expected 7 components"
        )


    modality_counts = {}


    for component in components_meta:

        modality = clean_text(
            component[
                "modality"
            ]
        )

        modality_counts[
            modality
        ] = (
            modality_counts.get(
                modality,
                0,
            )
            +
            1
        )


    if modality_counts != EXPECTED_COMPOSITION:

        archive.close()

        raise RuntimeError(
            f"{query_id}: invalid composition "
            f"{modality_counts}"
        )


    # Keep same deterministic node ordering as Phase 7H.
    components_meta = sorted(
        components_meta,
        key=lambda value:
            clean_text(
                value[
                    "node_id"
                ]
            ),
    )


    # =====================================================
    # Raw payload read + Phase 7B feature extraction
    # =====================================================

    payload_read_ns = 0
    extraction_ns = 0


    extracted_components = []


    try:

        for component in components_meta:

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


            read_start = (
                time.perf_counter_ns()
            )


            raw = archive.read(
                archive_path
            )


            read_end = (
                time.perf_counter_ns()
            )


            payload_read_ns += (
                read_end
                -
                read_start
            )


            extraction_start = (
                time.perf_counter_ns()
            )


            features = extract_features(
                modality,
                raw,
            )


            extraction_end = (
                time.perf_counter_ns()
            )


            extraction_ns += (
                extraction_end
                -
                extraction_start
            )


            extracted_components.append(
                (
                    node_id,
                    modality,
                    features,
                )
            )


    finally:

        archive.close()


    # =====================================================
    # Gallery similarity
    # =====================================================

    search_start = (
        time.perf_counter_ns()
    )


    component_inputs = []


    for (
        node_id,
        modality,
        features,
    ) in extracted_components:

        component_inputs.append(
            score_regenerated_component(
                node_id,
                modality,
                features,
            )
        )


    search_end = (
        time.perf_counter_ns()
    )


    # =====================================================
    # Graph
    # =====================================================

    graph_edges = [
        GraphEdgeInput(
            node_a=node_a,
            node_b=node_b,
        )

        for node_a, node_b
        in phase9d.edges_by_query.get(
            query_id,
            []
        )
    ]


    # =====================================================
    # Frozen reconstruction
    # =====================================================

    reconstruction_start = (
        time.perf_counter_ns()
    )


    result = analyze_internal(
        AnalyzeRequest(
            query_id=query_id,
            components=component_inputs,
            edges=graph_edges,
        )
    )


    reconstruction_end = (
        time.perf_counter_ns()
    )


    total_end = (
        time.perf_counter_ns()
    )


    rss_after = int(
        process.memory_info().rss
    )


    result[
        "phase9e3_latency_ms"
    ] = {
        "archive_open_and_manifest":
            (
                archive_manifest_end
                -
                archive_start
            )
            / 1_000_000.0,

        "payload_read":
            payload_read_ns
            / 1_000_000.0,

        "raw_evidence_extraction":
            extraction_ns
            / 1_000_000.0,

        "gallery_similarity_search":
            (
                search_end
                -
                search_start
            )
            / 1_000_000.0,

        "reconstruction":
            (
                reconstruction_end
                -
                reconstruction_start
            )
            / 1_000_000.0,

        "total_server_processing":
            (
                total_end
                -
                total_start
            )
            / 1_000_000.0,
    }


    result[
        "phase9e3_package"
    ] = {
        "package_size_bytes":
            int(
                package_record[
                    "size_bytes"
                ]
            ),

        "components":
            EXPECTED_COMPONENTS_PER_QUERY,

        "composition":
            EXPECTED_COMPOSITION,
    }


    result[
        "phase9e3_memory"
    ] = {
        "rss_before_bytes":
            rss_before,

        "rss_after_bytes":
            rss_after,

        "rss_delta_bytes":
            int(
                rss_after
                -
                rss_before
            ),
    }


    result[
        "phase9e3_scope"
    ] = (
        "SERVER_SIDE_MATERIALIZED_PACKAGE_"
        "TO_PROVENANCE_RESULT"
    )


    return result


# =========================================================
# API
# =========================================================

app = FastAPI(
    title=(
        "Game MOD Provenance "
        "Full Package Processing Server"
    ),

    version="9E-3",
)


@app.get(
    "/health"
)
def health():

    process = psutil.Process(
        os.getpid()
    )


    return {
        "status":
            "ok",

        "phase":
            "9E-3",

        "packages":
            len(
                package_by_query
            ),

        "gallery_projects":
            int(
                phase9d.PROJECT_COUNT
            ),

        "rss_bytes":
            int(
                process.memory_info().rss
            ),

        "phase7b_extractor_reused":
            True,

        "phase9e2_correctness":
            True,

        "network_file_upload_included":
            False,

        "scope":
            (
                "local package archive parsing "
                "+ raw evidence extraction "
                "+ gallery similarity search "
                "+ frozen provenance reconstruction"
            ),
    }


@app.get(
    "/analyze-package/{query_id}"
)
def analyze_package(
    query_id: str,
):

    try:

        return analyze_package_internal(
            str(
                query_id
            )
        )

    except KeyError:

        raise HTTPException(
            status_code=404,
            detail="query package not found",
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(
                error
            ),
        )


print(
    "======================================"
)

print(
    "Phase 9E-3 package server ready"
)

print(
    "======================================"
)

print(
    "Packages:",
    len(
        package_by_query
    )
)

print(
    "Gallery projects:",
    phase9d.PROJECT_COUNT
)