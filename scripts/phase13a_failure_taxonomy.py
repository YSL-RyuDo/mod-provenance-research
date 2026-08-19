#!/usr/bin/env python3

import ast
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

COMP = ROOT / "results/phase7h_final_component_predictions.csv"
QUERY = ROOT / "results/phase7h_final_query_predictions.csv"
RETR = ROOT / "results/phase7h_test_candidate_retrieval_audit.csv"

OUT_COMP = ROOT / "results/phase13a_component_failures.csv"
OUT_QUERY = ROOT / "results/phase13a_query_failures.csv"
OUT_MODALITY = ROOT / "results/phase13a_modality_summary.csv"
OUT_SCENARIO = ROOT / "results/phase13a_scenario_summary.csv"
OUT_JSON = ROOT / "results/phase13a_failure_taxonomy_summary.json"


def parse_list(x):
    if isinstance(x, list):
        return x

    s = str(x).strip()

    if not s:
        return []

    try:
        return json.loads(s)
    except Exception:
        return ast.literal_eval(s)


comp = pd.read_csv(COMP)
query = pd.read_csv(QUERY)
retr = pd.read_csv(RETR)


# =========================================================
# Query metadata
# =========================================================

query_meta = {}

for r in query.itertuples(index=False):

    pool = set(parse_list(r.candidate_pool))
    true_set = set(parse_list(r.true_parent_set))
    pred_set = set(parse_list(r.predicted_parent_set))

    true_known = true_set - {"UNKNOWN"}
    pred_known = pred_set - {"UNKNOWN"}

    query_meta[str(r.query_id)] = {
        "pool": pool,
        "true_known": true_known,
        "pred_known": pred_known,
        "k_true": int(r.k_true),
        "k_pred": int(r.k_pred),
        "parent_exact": bool(r.parent_set_exact),
    }


# =========================================================
# Component-level taxonomy
# =========================================================

rows = []

for r in comp.itertuples(index=False):

    qid = str(r.query_id)
    gt = str(r.ground_truth_label)
    pred = str(r.predicted_label)

    correct = gt == pred
    meta = query_meta[qid]

    gt_unknown = gt == "UNKNOWN"
    pred_unknown = pred == "UNKNOWN"

    if correct:
        error_type = "CORRECT"
        failure_stage = "NONE"

    elif gt_unknown and not pred_unknown:
        error_type = "UNKNOWN_TO_KNOWN"
        failure_stage = "RECONSTRUCTION"

    elif not gt_unknown and pred_unknown:
        error_type = "KNOWN_TO_UNKNOWN"

        if gt not in meta["pool"]:
            failure_stage = "RETRIEVAL"
        else:
            failure_stage = "RECONSTRUCTION"

    elif not gt_unknown and not pred_unknown and gt != pred:
        error_type = "WRONG_KNOWN_PARENT"

        if gt not in meta["pool"]:
            failure_stage = "RETRIEVAL"
        else:
            failure_stage = "RECONSTRUCTION"

    else:
        error_type = "OTHER"
        failure_stage = "OTHER"

    rows.append({
        "query_id": qid,
        "scenario": str(r.scenario),
        "k_true": int(r.k_true),
        "node_id": str(r.node_id),
        "modality": str(r.modality),
        "ground_truth_label": gt,
        "predicted_label": pred,
        "correct": correct,
        "error_type": error_type,
        "failure_stage": failure_stage,
        "true_parent_in_candidate_pool":
            None if gt_unknown else gt in meta["pool"],
    })


comp_out = pd.DataFrame(rows)
comp_out.to_csv(OUT_COMP, index=False)


# =========================================================
# Query-level taxonomy
# =========================================================

qrows = []

for r in query.itertuples(index=False):

    qid = str(r.query_id)

    true_set = set(parse_list(r.true_parent_set))
    pred_set = set(parse_list(r.predicted_parent_set))
    pool = set(parse_list(r.candidate_pool))

    true_known = true_set - {"UNKNOWN"}
    pred_known = pred_set - {"UNKNOWN"}

    missing_true = sorted(true_known - pred_known)
    extra_pred = sorted(pred_known - true_known)
    missing_from_pool = sorted(true_known - pool)

    exact = true_set == pred_set

    if exact:
        query_failure = "CORRECT"

    elif missing_from_pool:
        query_failure = "RETRIEVAL_LIMITED"

    else:
        query_failure = "RECONSTRUCTION_LIMITED"

    qc = comp_out[
        comp_out["query_id"] == qid
    ]

    qrows.append({
        "query_id": qid,
        "scenario": str(r.scenario),
        "k_true": int(r.k_true),
        "k_pred": int(r.k_pred),
        "k_correct": int(r.k_true) == int(r.k_pred),
        "parent_set_exact": exact,
        "query_failure_type": query_failure,
        "true_known_parent_count": len(true_known),
        "pred_known_parent_count": len(pred_known),
        "missing_true_parents": json.dumps(missing_true),
        "extra_predicted_parents": json.dumps(extra_pred),
        "true_parents_missing_from_pool": json.dumps(missing_from_pool),
        "component_errors": int((~qc["correct"]).sum()),
        "retrieval_component_errors":
            int((qc["failure_stage"] == "RETRIEVAL").sum()),
        "reconstruction_component_errors":
            int((qc["failure_stage"] == "RECONSTRUCTION").sum()),
    })


query_out = pd.DataFrame(qrows)
query_out.to_csv(OUT_QUERY, index=False)


# =========================================================
# Modality summary
# =========================================================

modality = (
    comp_out
    .groupby("modality")
    .agg(
        components=("correct", "size"),
        correct=("correct", "sum"),
    )
    .reset_index()
)

modality["errors"] = (
    modality["components"]
    -
    modality["correct"]
)

modality["accuracy"] = (
    modality["correct"]
    /
    modality["components"]
)

for et in [
    "KNOWN_TO_UNKNOWN",
    "UNKNOWN_TO_KNOWN",
    "WRONG_KNOWN_PARENT",
]:
    counts = (
        comp_out[
            comp_out["error_type"] == et
        ]
        .groupby("modality")
        .size()
    )

    modality[et.lower()] = (
        modality["modality"]
        .map(counts)
        .fillna(0)
        .astype(int)
    )

modality.to_csv(OUT_MODALITY, index=False)


# =========================================================
# Scenario summary
# =========================================================

scenario = (
    comp_out
    .groupby("scenario")
    .agg(
        components=("correct", "size"),
        correct=("correct", "sum"),
    )
    .reset_index()
)

scenario["errors"] = (
    scenario["components"]
    -
    scenario["correct"]
)

scenario["accuracy"] = (
    scenario["correct"]
    /
    scenario["components"]
)

qagg = (
    query_out
    .groupby("scenario")
    .agg(
        queries=("query_id", "size"),
        parent_exact=("parent_set_exact", "sum"),
        k_correct=("k_correct", "sum"),
    )
    .reset_index()
)

qagg["parent_exact_rate"] = (
    qagg["parent_exact"]
    /
    qagg["queries"]
)

qagg["k_accuracy"] = (
    qagg["k_correct"]
    /
    qagg["queries"]
)

scenario = scenario.merge(
    qagg,
    on="scenario",
    how="left",
)

scenario.to_csv(OUT_SCENARIO, index=False)


# =========================================================
# Summary
# =========================================================

errors = comp_out[
    ~comp_out["correct"]
]

component_taxonomy = (
    errors["error_type"]
    .value_counts()
    .to_dict()
)

failure_stage = (
    errors["failure_stage"]
    .value_counts()
    .to_dict()
)

query_taxonomy = (
    query_out["query_failure_type"]
    .value_counts()
    .to_dict()
)

summary = {
    "phase13a_complete": True,
    "scope": "POST_FREEZE_AUTOMATED_FAILURE_ANALYSIS",
    "parameters_retuned": False,
    "predictions_recomputed": False,
    "primary_test_modified": False,

    "test": {
        "queries": int(query_out.shape[0]),
        "components": int(comp_out.shape[0]),
        "component_correct":
            int(comp_out["correct"].sum()),
        "component_errors":
            int((~comp_out["correct"]).sum()),
        "component_accuracy":
            float(comp_out["correct"].mean()),
        "query_parent_exact":
            int(query_out["parent_set_exact"].sum()),
        "query_parent_failures":
            int((~query_out["parent_set_exact"]).sum()),
    },

    "component_error_taxonomy": {
        str(k): int(v)
        for k, v in component_taxonomy.items()
    },

    "component_failure_stage": {
        str(k): int(v)
        for k, v in failure_stage.items()
    },

    "query_failure_taxonomy": {
        str(k): int(v)
        for k, v in query_taxonomy.items()
    },

    "interpretation_rule": (
        "RETRIEVAL denotes a registered ground-truth parent "
        "absent from the frozen candidate pool. "
        "RECONSTRUCTION denotes a failure despite the true "
        "registered parent being available to reconstruction, "
        "or an UNKNOWN false attribution."
    ),
}

OUT_JSON.write_text(
    json.dumps(
        summary,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)


print("========================================")
print("Phase 13A - Automated Failure Taxonomy")
print("========================================")

print()
print("TEST components:", len(comp_out))
print("Correct:", int(comp_out["correct"].sum()))
print("Errors:", int((~comp_out["correct"]).sum()))
print("Accuracy:", float(comp_out["correct"].mean()))

print()
print("COMPONENT ERROR TYPES")
print(
    errors["error_type"]
    .value_counts()
    .to_string()
)

print()
print("FAILURE STAGE")
print(
    errors["failure_stage"]
    .value_counts()
    .to_string()
)

print()
print("QUERY FAILURE TYPES")
print(
    query_out["query_failure_type"]
    .value_counts()
    .to_string()
)

print()
print("MODALITY")
print(
    modality.to_string(index=False)
)

print()
print("SCENARIO")
print(
    scenario.to_string(index=False)
)

print()
print("Wrote:", OUT_COMP)
print("Wrote:", OUT_QUERY)
print("Wrote:", OUT_MODALITY)
print("Wrote:", OUT_SCENARIO)
print("Wrote:", OUT_JSON)

print()
print("Phase13A COMPLETE")
