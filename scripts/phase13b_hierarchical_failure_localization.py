#!/usr/bin/env python3

import ast
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

COMP = ROOT / "results/phase13a_component_failures.csv"
QUERY = ROOT / "results/phase7h_final_query_predictions.csv"

OUT = ROOT / "results/phase13b_failure_localization.csv"
OUT_SUM = ROOT / "results/phase13b_failure_localization_summary.json"


def parse_set(x):
    if isinstance(x, list):
        return set(x)

    s = str(x).strip()

    if not s:
        return set()

    try:
        return set(json.loads(s))
    except Exception:
        return set(ast.literal_eval(s))


comp = pd.read_csv(COMP)
query = pd.read_csv(QUERY)

qmeta = {}

for r in query.itertuples(index=False):
    qmeta[str(r.query_id)] = {
        "candidate_pool": parse_set(r.candidate_pool),
        "selected_subset": parse_set(r.selected_known_subset),
        "true_parent_set": parse_set(r.true_parent_set),
        "predicted_parent_set": parse_set(r.predicted_parent_set),
    }


rows = []

for r in comp.itertuples(index=False):

    qid = str(r.query_id)
    gt = str(r.ground_truth_label)
    pred = str(r.predicted_label)

    meta = qmeta[qid]

    if bool(r.correct):
        localization = "CORRECT"

    elif gt == "UNKNOWN" and pred != "UNKNOWN":
        localization = "UNKNOWN_REJECTION_FAILURE"

    elif gt != "UNKNOWN":

        if gt not in meta["candidate_pool"]:
            localization = "RETRIEVAL_MISS"

        elif gt not in meta["selected_subset"]:
            localization = "PARENT_SELECTION_MISS"

        else:
            localization = "COMPONENT_ASSIGNMENT_MISS"

    else:
        localization = "OTHER"

    rows.append({
        "query_id": qid,
        "scenario": r.scenario,
        "k_true": r.k_true,
        "node_id": r.node_id,
        "modality": r.modality,
        "ground_truth_label": gt,
        "predicted_label": pred,
        "error_type": r.error_type,
        "localization": localization,
    })


out = pd.DataFrame(rows)
out.to_csv(OUT, index=False)

errors = out[out["localization"] != "CORRECT"]

counts = (
    errors["localization"]
    .value_counts()
)

by_modality = pd.crosstab(
    errors["modality"],
    errors["localization"],
)

by_scenario = pd.crosstab(
    errors["scenario"],
    errors["localization"],
)

summary = {
    "phase13b_complete": True,
    "scope": "POST_FREEZE_HIERARCHICAL_FAILURE_LOCALIZATION",
    "parameters_retuned": False,
    "predictions_recomputed": False,
    "primary_test_modified": False,

    "component_errors": int(len(errors)),

    "failure_localization": {
        str(k): int(v)
        for k, v in counts.items()
    },

    "failure_localization_fraction": {
        str(k): float(v / len(errors))
        for k, v in counts.items()
    },

    "interpretation": {
        "RETRIEVAL_MISS":
            "The registered ground-truth parent is absent from the frozen candidate pool.",

        "PARENT_SELECTION_MISS":
            "The true parent is retrieved but excluded by package-level known-parent subset reconstruction.",

        "COMPONENT_ASSIGNMENT_MISS":
            "The true parent survives both retrieval and package-level parent selection, but the component is assigned to UNKNOWN or another parent.",

        "UNKNOWN_REJECTION_FAILURE":
            "A true UNKNOWN component is falsely attributed to a registered parent.",
    },

    "by_modality":
        by_modality.to_dict(),

    "by_scenario":
        by_scenario.to_dict(),
}

OUT_SUM.write_text(
    json.dumps(
        summary,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)

print("==========================================")
print("Phase 13B - Failure Localization")
print("==========================================")
print()
print(counts.to_string())

print()
print("FRACTIONS")
for k, v in counts.items():
    print(
        k,
        f"{v / len(errors):.4f}"
    )

print()
print("BY MODALITY")
print(by_modality.to_string())

print()
print("BY SCENARIO")
print(by_scenario.to_string())

print()
print("Wrote:", OUT)
print("Wrote:", OUT_SUM)
print()
print("Phase13B COMPLETE")
