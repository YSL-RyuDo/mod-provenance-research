#!/usr/bin/env python3

import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MANIFEST = ROOT / "results" / "phase6k_query_manifest_private.csv"
GT_FILE = ROOT / "results" / "phase6k_query_ground_truth.csv"
MATERIALIZED = ROOT / "results" / "phase6l_materialized_private_manifest.csv"

OUT_MANIFEST = ROOT / "results" / "phase11a_multi_unknown_manifest_private.csv"
OUT_GT = ROOT / "results" / "phase11a_multi_unknown_ground_truth.csv"
OUT_AUDIT = ROOT / "results" / "phase11a_multi_unknown_component_audit.csv"
OUT_SUMMARY = ROOT / "results" / "phase11a_multi_unknown_summary.json"

SEED = 20260818
QUERIES_PER_SCENARIO = 30

SCENARIOS = {
    # slot assignment:
    # five CODE slots + STRUCTURED + IMAGE
    #
    # K0/K1 = known parent indices
    # U0/U1/U2 = distinct held-out source parents

    "MU_1K2U": {
        "known": 1,
        "unknown": 2,
        "slots": [
            ("CODE", "K0"),
            ("CODE", "K0"),
            ("CODE", "U0"),
            ("CODE", "U0"),
            ("CODE", "U1"),
            ("STRUCTURED", "U1"),
            ("IMAGE", "K0"),
        ],
    },

    "MU_2K2U": {
        "known": 2,
        "unknown": 2,
        "slots": [
            ("CODE", "K0"),
            ("CODE", "K1"),
            ("CODE", "U0"),
            ("CODE", "U1"),
            ("CODE", "K0"),
            ("STRUCTURED", "K1"),
            ("IMAGE", "U0"),
        ],
    },

    "MU_1K3U": {
        "known": 1,
        "unknown": 3,
        "slots": [
            ("CODE", "K0"),
            ("CODE", "U0"),
            ("CODE", "U1"),
            ("CODE", "U2"),
            ("CODE", "K0"),
            ("STRUCTURED", "U0"),
            ("IMAGE", "U1"),
        ],
    },

    "MU_2K3U": {
        "known": 2,
        "unknown": 3,
        "slots": [
            ("CODE", "K0"),
            ("CODE", "K1"),
            ("CODE", "U0"),
            ("CODE", "U1"),
            ("CODE", "U2"),
            ("STRUCTURED", "K0"),
            ("IMAGE", "K1"),
        ],
    },

    "MU_U2": {
        "known": 0,
        "unknown": 2,
        "slots": [
            ("CODE", "U0"),
            ("CODE", "U1"),
            ("CODE", "U0"),
            ("CODE", "U1"),
            ("CODE", "U0"),
            ("STRUCTURED", "U1"),
            ("IMAGE", "U0"),
        ],
    },

    "MU_U3": {
        "known": 0,
        "unknown": 3,
        "slots": [
            ("CODE", "U0"),
            ("CODE", "U1"),
            ("CODE", "U2"),
            ("CODE", "U0"),
            ("CODE", "U1"),
            ("STRUCTURED", "U2"),
            ("IMAGE", "U0"),
        ],
    },
}


def load_csv(path):
    with path.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:
        return list(csv.DictReader(f))


def norm_modality(v):
    v = str(v).strip().upper()

    if v in {"CODE", "CODE_BINARY", "CLASS", "BYTECODE"}:
        return "CODE"

    if v in {"STRUCT", "STRUCTURED", "JSON"}:
        return "STRUCTURED"

    if v in {"IMAGE", "IMG", "PNG"}:
        return "IMAGE"

    return v


def find_payload_column(headers):
    candidates = [
        "payload_relpath",
        "materialized_relpath",
        "payload_path",
        "materialized_path",
        "query_payload_relpath",
    ]

    lower = {x.lower(): x for x in headers}

    for c in candidates:
        if c.lower() in lower:
            return lower[c.lower()]

    return None


def main():
    rng = random.Random(SEED)

    manifest = load_csv(MANIFEST)
    gt_rows = load_csv(GT_FILE)
    materialized = load_csv(MATERIALIZED)

    # ------------------------------------------------------------------
    # Only frozen TEST components are permitted as robustness donors.
    # ------------------------------------------------------------------

    test_rows = [
        dict(r)
        for r in manifest
        if r["stage"].strip().upper() == "TEST"
    ]

    if not test_rows:
        raise RuntimeError(
            "No TEST rows found in phase6k manifest."
        )

    for r in test_rows:
        r["modality"] = norm_modality(r["modality"])

    # ------------------------------------------------------------------
    # Locate frozen materialized payload for every existing node.
    # ------------------------------------------------------------------

    mat_headers = list(materialized[0].keys())

    node_col = None
    for c in ["node_id", "query_node_id"]:
        if c in mat_headers:
            node_col = c
            break

    if not node_col:
        raise RuntimeError(
            "Could not locate node_id column in "
            f"{MATERIALIZED}. Columns={mat_headers}"
        )

    payload_col = find_payload_column(mat_headers)

    if payload_col is None:
        raise RuntimeError(
            "Could not locate materialized payload path column.\n"
            f"Columns={mat_headers}"
        )

    mat_by_node = {
        r[node_col]: r
        for r in materialized
    }

    missing_materialized = [
        r["node_id"]
        for r in test_rows
        if r["node_id"] not in mat_by_node
    ]

    if missing_materialized:
        raise RuntimeError(
            f"{len(missing_materialized)} TEST nodes have no "
            f"Phase6L materialized entry. "
            f"Examples={missing_materialized[:10]}"
        )

    # ------------------------------------------------------------------
    # Build donor pool.
    #
    # KNOWN:
    #     ground_truth_label == source_fresh_id != UNKNOWN
    #
    # UNKNOWN:
    #     ground_truth_label == UNKNOWN,
    #     but source_fresh_id privately identifies the held-out source.
    # ------------------------------------------------------------------

    known_pool = defaultdict(
        lambda: defaultdict(list)
    )
    unknown_pool = defaultdict(
        lambda: defaultdict(list)
    )

    for r in test_rows:
        label = r["ground_truth_label"].strip()
        source = r["source_fresh_id"].strip()
        modality = r["modality"]

        if not source:
            continue

        if label == "UNKNOWN":
            unknown_pool[source][modality].append(r)
        else:
            known_pool[source][modality].append(r)

    known_sources = sorted(known_pool)
    unknown_sources = sorted(unknown_pool)

    # ------------------------------------------------------------------
    # Availability report.
    # ------------------------------------------------------------------

    def source_availability(pool):
        result = {}

        for src, mods in pool.items():
            result[src] = {
                m: len(mods.get(m, []))
                for m in ["CODE", "STRUCTURED", "IMAGE"]
            }

        return result

    known_avail = source_availability(known_pool)
    unknown_avail = source_availability(unknown_pool)

    print("=== DONOR POOL ===")
    print("TEST components:", len(test_rows))
    print("known sources:", len(known_sources))
    print("unknown held-out sources:", len(unknown_sources))

    print()
    print("KNOWN modality totals:")
    print(
        Counter(
            r["modality"]
            for r in test_rows
            if r["ground_truth_label"] != "UNKNOWN"
        )
    )

    print()
    print("UNKNOWN modality totals:")
    print(
        Counter(
            r["modality"]
            for r in test_rows
            if r["ground_truth_label"] == "UNKNOWN"
        )
    )

    # ------------------------------------------------------------------
    # We permit donor reuse across different robustness queries because
    # this is a stress benchmark assembled from a fixed frozen TEST pool.
    #
    # Within one generated query, however:
    # - no component node can appear twice
    # - each parent token maps to a distinct real source
    #
    # This benchmark is NOT used to fit/tune any parameter.
    # ------------------------------------------------------------------

    def can_supply(pool, source, requirements):
        mods = pool[source]

        need = Counter(requirements)

        for modality, n in need.items():
            if len(mods.get(modality, [])) < n:
                return False

        return True

    def requirements_for_token(slots, token):
        return [
            modality
            for modality, t in slots
            if t == token
        ]

    def viable_sources(pool, slots, tokens):
        result = {}

        for token in tokens:
            req = requirements_for_token(slots, token)

            result[token] = [
                src
                for src in pool
                if can_supply(pool, src, req)
            ]

        return result

    new_manifest = []
    new_gt = []
    audit_rows = []

    generated = 0
    failed_attempts = Counter()

    for scenario, spec in SCENARIOS.items():

        slots = spec["slots"]

        k_tokens = [
            f"K{i}"
            for i in range(spec["known"])
        ]

        u_tokens = [
            f"U{i}"
            for i in range(spec["unknown"])
        ]

        viable_k = viable_sources(
            known_pool,
            slots,
            k_tokens
        )

        viable_u = viable_sources(
            unknown_pool,
            slots,
            u_tokens
        )

        for token, srcs in viable_k.items():
            if not srcs:
                raise RuntimeError(
                    f"{scenario}: no viable KNOWN donor "
                    f"for token {token}; "
                    f"requirements="
                    f"{requirements_for_token(slots, token)}"
                )

        for token, srcs in viable_u.items():
            if not srcs:
                raise RuntimeError(
                    f"{scenario}: no viable UNKNOWN donor "
                    f"for token {token}; "
                    f"requirements="
                    f"{requirements_for_token(slots, token)}"
                )

        scenario_generated = 0

        while scenario_generated < QUERIES_PER_SCENARIO:

            success = False

            for attempt in range(10000):

                token_to_source = {}

                # Choose distinct known parents.
                chosen_known = set()

                okay = True

                for token in k_tokens:
                    candidates = [
                        s
                        for s in viable_k[token]
                        if s not in chosen_known
                    ]

                    if not candidates:
                        okay = False
                        break

                    src = rng.choice(candidates)
                    chosen_known.add(src)
                    token_to_source[token] = src

                if not okay:
                    continue

                # Choose distinct unknown parents.
                chosen_unknown = set()

                for token in u_tokens:
                    candidates = [
                        s
                        for s in viable_u[token]
                        if s not in chosen_unknown
                    ]

                    if not candidates:
                        okay = False
                        break

                    src = rng.choice(candidates)
                    chosen_unknown.add(src)
                    token_to_source[token] = src

                if not okay:
                    continue

                # Select components without duplicates within query.
                selected = []
                used_node_ids = set()

                for modality, token in slots:
                    source = token_to_source[token]

                    pool = (
                        known_pool
                        if token.startswith("K")
                        else unknown_pool
                    )

                    candidates = [
                        r
                        for r in pool[source][modality]
                        if r["node_id"] not in used_node_ids
                    ]

                    if not candidates:
                        okay = False
                        break

                    donor = rng.choice(candidates)

                    used_node_ids.add(donor["node_id"])
                    selected.append(
                        (
                            modality,
                            token,
                            source,
                            donor
                        )
                    )

                if not okay:
                    continue

                success = True
                break

            if not success:
                failed_attempts[scenario] += 1
                raise RuntimeError(
                    f"Failed to construct {scenario} "
                    f"query {scenario_generated+1} "
                    f"after 10000 attempts."
                )

            generated += 1
            scenario_generated += 1

            qid = f"Q11A{generated:04d}"

            known_parent_ids = sorted(
                token_to_source[t]
                for t in k_tokens
            )

            unknown_parent_ids = sorted(
                token_to_source[t]
                for t in u_tokens
            )

            # Actual provenance-source multiplicity.
            k_true = (
                len(known_parent_ids)
                + len(unknown_parent_ids)
            )

            # Existing inference model can only emit one UNKNOWN label.
            collapsed_k_target = (
                len(known_parent_ids)
                + (1 if unknown_parent_ids else 0)
            )

            new_gt.append({
                "query_id": qid,
                "stage": "ROBUSTNESS_MULTI_UNKNOWN",
                "scenario": scenario,
                "k_true_actual_sources": k_true,
                "k_target_collapsed_unknown":
                    collapsed_k_target,
                "known_parent_count":
                    len(known_parent_ids),
                "unknown_parent_count":
                    len(unknown_parent_ids),
                "known_parent_ids":
                    json.dumps(
                        known_parent_ids,
                        ensure_ascii=False
                    ),
                "unknown_parent_ids_private":
                    json.dumps(
                        unknown_parent_ids,
                        ensure_ascii=False
                    ),
                "evaluation_parent_labels":
                    json.dumps(
                        known_parent_ids
                        + (
                            ["UNKNOWN"]
                            if unknown_parent_ids
                            else []
                        ),
                        ensure_ascii=False
                    ),
                "component_count": 7,
                "code_count": 5,
                "structured_count": 1,
                "image_count": 1,
            })

            # Stable node ordering:
            # N01-N05 CODE, N06 STRUCTURED, N07 IMAGE
            for idx, (
                modality,
                token,
                source,
                donor
            ) in enumerate(selected, 1):

                new_node = f"{qid}_N{idx:02d}"

                evaluation_label = (
                    source
                    if token.startswith("K")
                    else "UNKNOWN"
                )

                mat = mat_by_node[donor["node_id"]]

                payload_relpath = mat[payload_col]

                row = {
                    "query_id": qid,
                    "node_id": new_node,
                    "stage": "ROBUSTNESS_MULTI_UNKNOWN",
                    "scenario": scenario,
                    "k_true_actual_sources": k_true,
                    "k_target_collapsed_unknown":
                        collapsed_k_target,
                    "modality": modality,
                    "ground_truth_label":
                        evaluation_label,
                    "source_fresh_id": source,
                    "source_version_id":
                        donor["source_version_id"],
                    "source_version_number":
                        donor["source_version_number"],
                    "source_fragment_id":
                        donor["source_fragment_id"],
                    "source_fragment_node_id":
                        donor["source_fragment_node_id"],
                    "source_relative_path":
                        donor["source_relative_path"],
                    "source_component_sha256":
                        donor["source_component_sha256"],
                    "transform_recipe":
                        donor["transform_recipe"],
                    "donor_query_id":
                        donor["query_id"],
                    "donor_node_id":
                        donor["node_id"],
                    "parent_token": token,
                    "payload_relpath":
                        payload_relpath,
                }

                new_manifest.append(row)

                audit_rows.append({
                    "query_id": qid,
                    "node_id": new_node,
                    "scenario": scenario,
                    "modality": modality,
                    "parent_token": token,
                    "evaluation_label":
                        evaluation_label,
                    "private_source_fresh_id":
                        source,
                    "donor_query_id":
                        donor["query_id"],
                    "donor_node_id":
                        donor["node_id"],
                    "source_component_sha256":
                        donor["source_component_sha256"],
                    "payload_relpath":
                        payload_relpath,
                })

    # ------------------------------------------------------------------
    # Audits
    # ------------------------------------------------------------------

    if len(new_gt) != (
        QUERIES_PER_SCENARIO * len(SCENARIOS)
    ):
        raise RuntimeError(
            "Unexpected generated query count."
        )

    if len(new_manifest) != len(new_gt) * 7:
        raise RuntimeError(
            "Every robustness query must have 7 components."
        )

    scenario_counts = Counter(
        r["scenario"]
        for r in new_gt
    )

    modality_counts = Counter(
        r["modality"]
        for r in new_manifest
    )

    # Ensure each query is exactly 5/1/1.
    by_query = defaultdict(list)

    for r in new_manifest:
        by_query[r["query_id"]].append(r)

    bad_composition = []

    for qid, rr in by_query.items():
        c = Counter(x["modality"] for x in rr)

        if (
            len(rr) != 7
            or c["CODE"] != 5
            or c["STRUCTURED"] != 1
            or c["IMAGE"] != 1
        ):
            bad_composition.append(
                (qid, dict(c))
            )

    if bad_composition:
        raise RuntimeError(
            f"Bad modality composition: "
            f"{bad_composition[:10]}"
        )

    # Actual unknown multiplicity audit.
    bad_unknown_counts = []

    gt_by_q = {
        r["query_id"]: r
        for r in new_gt
    }

    for qid, rr in by_query.items():
        sources = {
            r["source_fresh_id"]
            for r in rr
            if r["ground_truth_label"] == "UNKNOWN"
        }

        expected = int(
            gt_by_q[qid]["unknown_parent_count"]
        )

        if len(sources) != expected:
            bad_unknown_counts.append(
                (
                    qid,
                    expected,
                    len(sources),
                    sorted(sources)
                )
            )

    if bad_unknown_counts:
        raise RuntimeError(
            "Unknown multiplicity audit failed: "
            f"{bad_unknown_counts[:10]}"
        )

    # ------------------------------------------------------------------
    # Write files.
    # ------------------------------------------------------------------

    manifest_fields = [
        "query_id",
        "node_id",
        "stage",
        "scenario",
        "k_true_actual_sources",
        "k_target_collapsed_unknown",
        "modality",
        "ground_truth_label",
        "source_fresh_id",
        "source_version_id",
        "source_version_number",
        "source_fragment_id",
        "source_fragment_node_id",
        "source_relative_path",
        "source_component_sha256",
        "transform_recipe",
        "donor_query_id",
        "donor_node_id",
        "parent_token",
        "payload_relpath",
    ]

    with OUT_MANIFEST.open(
        "w",
        encoding="utf-8",
        newline=""
    ) as f:
        w = csv.DictWriter(
            f,
            fieldnames=manifest_fields
        )
        w.writeheader()
        w.writerows(new_manifest)

    gt_fields = list(new_gt[0].keys())

    with OUT_GT.open(
        "w",
        encoding="utf-8",
        newline=""
    ) as f:
        w = csv.DictWriter(
            f,
            fieldnames=gt_fields
        )
        w.writeheader()
        w.writerows(new_gt)

    audit_fields = list(audit_rows[0].keys())

    with OUT_AUDIT.open(
        "w",
        encoding="utf-8",
        newline=""
    ) as f:
        w = csv.DictWriter(
            f,
            fieldnames=audit_fields
        )
        w.writeheader()
        w.writerows(audit_rows)

    summary = {
        "phase11a_complete": True,
        "scope":
            "MULTI_UNKNOWN_ROBUSTNESS_BENCHMARK",
        "seed": SEED,
        "queries_per_scenario":
            QUERIES_PER_SCENARIO,
        "total_queries": len(new_gt),
        "total_components":
            len(new_manifest),
        "scenario_counts":
            dict(scenario_counts),
        "modality_counts":
            dict(modality_counts),
        "frozen_test_donor_components":
            len(test_rows),
        "known_donor_sources":
            len(known_sources),
        "unknown_heldout_donor_sources":
            len(unknown_sources),
        "known_donor_availability":
            known_avail,
        "unknown_donor_availability":
            unknown_avail,
        "bad_composition_count":
            len(bad_composition),
        "bad_unknown_multiplicity_count":
            len(bad_unknown_counts),
        "manual_annotation_used":
            False,
        "test_retuning":
            False,
        "primary_test_modified":
            False,
        "important_protocol_notes": {
            "donor_pool":
                "Only frozen Phase6K TEST components "
                "and their Phase6L materialized payloads.",
            "multi_unknown_ground_truth":
                "Distinct held-out source_fresh_id values "
                "are retained privately to measure actual "
                "unknown-source multiplicity.",
            "evaluation_label":
                "All held-out sources remain collapsed to "
                "the single public label UNKNOWN.",
            "k_true_actual_sources":
                "Known parents plus distinct held-out "
                "source parents.",
            "k_target_collapsed_unknown":
                "Known parents plus one UNKNOWN group; "
                "this is the only K notion the existing "
                "classifier can currently represent.",
            "purpose":
                "Post-freeze robustness evaluation only; "
                "not used for calibration or parameter tuning."
        }
    }

    OUT_SUMMARY.write_text(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print()
    print("=== PHASE11A SUMMARY ===")
    print(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
