#!/usr/bin/env python3

import csv
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

# ============================================================
# Inputs
# ============================================================

P11_MANIFEST = ROOT / "results/phase11a_multi_unknown_manifest_private.csv"
P11_GT = ROOT / "results/phase11a_multi_unknown_ground_truth.csv"

P7_EVIDENCE = ROOT / "results/phase7b_query_identity_neutral_evidence.csv"
P7H_SOURCE = ROOT / "scripts/phase7h_final_test_evaluation.py"

# ============================================================
# Adapter files
# ============================================================

ADAPT_EVIDENCE = ROOT / "results/phase11b_query_identity_neutral_evidence.csv"
ADAPT_PRIVATE = ROOT / "results/phase11b_compat_private_manifest.csv"
ADAPT_GT = ROOT / "results/phase11b_compat_ground_truth.csv"
ADAPT_GRAPH = ROOT / "results/phase11b_empty_graph.csv"

GENERATED_RUNNER = ROOT / "scripts/_phase11b_phase7h_adapter_generated.py"

# ============================================================
# Phase7H adapted outputs
# ============================================================

OUT_SCORES = ROOT / "results/phase11b_component_parent_scores.csv"
OUT_COMPONENTS = ROOT / "results/phase11b_component_predictions.csv"
OUT_QUERIES = ROOT / "results/phase11b_query_predictions.csv"

OUT_BETA0_COMPONENTS = ROOT / "results/phase11b_beta0_component_predictions.csv"
OUT_BETA0_QUERIES = ROOT / "results/phase11b_beta0_query_predictions.csv"

OUT_RETRIEVAL = ROOT / "results/phase11b_candidate_retrieval_audit.csv"
OUT_RAW_SUMMARY = ROOT / "results/phase11b_raw_phase7h_summary.json"

# ============================================================
# Final Phase11C outputs
# ============================================================

OUT_SCENARIO = ROOT / "results/phase11c_by_scenario.csv"
OUT_UNKNOWN_COUNT = ROOT / "results/phase11c_by_unknown_multiplicity.csv"
OUT_SUMMARY = ROOT / "results/phase11c_multi_unknown_summary.json"

EXPECTED_QUERIES = 180
EXPECTED_COMPONENTS = 1260
EXPECTED_GALLERY = 60
UNKNOWN = "UNKNOWN"


def read_csv(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def safe_div(a, b):
    return a / b if b else 0.0


def binary_unknown_metrics(truth, pred):
    tp = sum(t == UNKNOWN and p == UNKNOWN for t, p in zip(truth, pred))
    fp = sum(t != UNKNOWN and p == UNKNOWN for t, p in zip(truth, pred))
    fn = sum(t == UNKNOWN and p != UNKNOWN for t, p in zip(truth, pred))

    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def set_metrics(a, b):
    a = set(a)
    b = set(b)

    if not a and not b:
        return 1.0, 1.0, 1.0, True

    inter = len(a & b)

    precision = inter / len(b) if b else 0.0
    recall = inter / len(a) if a else 0.0

    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )

    return precision, recall, f1, a == b


# ============================================================
# 1. Reuse exact frozen Phase7B donor evidence
# ============================================================

print("=== Phase11B: build frozen evidence adapter ===")

manifest = read_csv(P11_MANIFEST)
gt = read_csv(P11_GT)
evidence = read_csv(P7_EVIDENCE)

if len(manifest) != EXPECTED_COMPONENTS:
    raise RuntimeError(
        f"Expected {EXPECTED_COMPONENTS} Phase11 components, got {len(manifest)}"
    )

if manifest["query_id"].nunique() != EXPECTED_QUERIES:
    raise RuntimeError(
        f"Expected {EXPECTED_QUERIES} Phase11 queries, "
        f"got {manifest['query_id'].nunique()}"
    )

evidence_key = {}

for _, row in evidence.iterrows():
    key = (str(row["query_id"]), str(row["node_id"]))

    if key in evidence_key:
        raise RuntimeError(f"Duplicate Phase7 evidence key: {key}")

    evidence_key[key] = row.copy()


adapt_rows = []
missing = []

for _, row in manifest.iterrows():

    donor_key = (
        str(row["donor_query_id"]),
        str(row["donor_node_id"]),
    )

    if donor_key not in evidence_key:
        missing.append(donor_key)
        continue

    e = evidence_key[donor_key].copy()

    e["query_id"] = str(row["query_id"])
    e["node_id"] = str(row["node_id"])

    # Phase7 uses CODE_BINARY.
    modality = str(row["modality"]).strip().upper()

    if modality == "CODE":
        modality = "CODE_BINARY"

    e["modality"] = modality

    # Make it look like the frozen TEST input expected by Phase7H.
    if "stage" in e.index:
        e["stage"] = "TEST"

    if "scenario" in e.index:
        e["scenario"] = str(row["scenario"])

    adapt_rows.append(e)


if missing:
    raise RuntimeError(
        f"{len(missing)} donor evidence rows missing. Examples={missing[:10]}"
    )

adapt_evidence = pd.DataFrame(adapt_rows)

if len(adapt_evidence) != EXPECTED_COMPONENTS:
    raise RuntimeError(
        f"Expected {EXPECTED_COMPONENTS} adapted evidence rows, "
        f"got {len(adapt_evidence)}"
    )

if adapt_evidence[["query_id", "node_id"]].duplicated().any():
    raise RuntimeError("Duplicate Phase11 adapted evidence node IDs.")

adapt_evidence.to_csv(ADAPT_EVIDENCE, index=False)

print("adapted evidence:", len(adapt_evidence))


# ============================================================
# 2. Compatibility private manifest
# ============================================================

compat_private = manifest.copy()

compat_private["stage"] = "TEST"

compat_private["modality"] = compat_private["modality"].replace({
    "CODE": "CODE_BINARY"
})

# Phase7H expects k_true on every component.
compat_private["k_true"] = compat_private["k_target_collapsed_unknown"]

compat_private.to_csv(ADAPT_PRIVATE, index=False)

print("compat private manifest:", len(compat_private))


# ============================================================
# 3. Compatibility query GT
# ============================================================

compat_gt = gt.copy()

compat_gt["stage"] = "TEST"
compat_gt["k_true"] = compat_gt["k_target_collapsed_unknown"]

# Phase7H only needs a compatible parent-set definition.
compat_gt["known_parent_ids"] = compat_gt["known_parent_ids"]

compat_gt["unknown_parent_ids"] = compat_gt[
    "unknown_parent_ids_private"
].apply(
    lambda x: json.dumps(["UNKNOWN"])
    if len(json.loads(x)) > 0
    else json.dumps([])
)

def make_all_parent_ids(row):
    known = json.loads(row["known_parent_ids"])
    unknowns = json.loads(row["unknown_parent_ids_private"])

    result = list(known)

    if unknowns:
        result.append("UNKNOWN")

    return json.dumps(result)

compat_gt["all_parent_ids"] = compat_gt.apply(
    make_all_parent_ids,
    axis=1
)

compat_gt["component_count"] = "7"
compat_gt["code_count"] = "5"
compat_gt["structured_count"] = "1"
compat_gt["image_count"] = "1"

compat_gt.to_csv(ADAPT_GT, index=False)

print("compat query GT:", len(compat_gt))


# ============================================================
# 4. Empty graph
#
# No dependency graph exists for recomposed Phase11 queries.
# With no edges, beta=0.1 produces identical refined/base costs.
# ============================================================

with ADAPT_GRAPH.open("w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["query_id", "node_a", "node_b"])

print("Phase11 graph: 0 edges (content-only robustness)")


# ============================================================
# 5. Generate adapted Phase7H runner
# ============================================================

print()
print("=== Generate Phase7H adapter ===")

src = P7H_SOURCE.read_text(encoding="utf-8")

replacements = {
    "results/phase7b_query_identity_neutral_evidence.csv":
        "results/phase11b_query_identity_neutral_evidence.csv",

    "results/phase6l_materialized_private_manifest.csv":
        "results/phase11b_compat_private_manifest.csv",

    "results/phase6k_query_ground_truth.csv":
        "results/phase11b_compat_ground_truth.csv",

    "results/phase6l_graph_connected_stress_public.csv":
        "results/phase11b_empty_graph.csv",

    "results/phase7h_test_component_parent_scores.csv":
        "results/phase11b_component_parent_scores.csv",

    "results/phase7h_final_component_predictions.csv":
        "results/phase11b_component_predictions.csv",

    "results/phase7h_final_query_predictions.csv":
        "results/phase11b_query_predictions.csv",

    "results/phase7h_beta0_component_predictions.csv":
        "results/phase11b_beta0_component_predictions.csv",

    "results/phase7h_beta0_query_predictions.csv":
        "results/phase11b_beta0_query_predictions.csv",

    "results/phase7h_test_candidate_retrieval_audit.csv":
        "results/phase11b_candidate_retrieval_audit.csv",

    "results/phase7h_final_test_summary.json":
        "results/phase11b_raw_phase7h_summary.json",
}

for old, new in replacements.items():

    if old not in src:
        raise RuntimeError(
            f"Expected Phase7H path not found: {old}"
        )

    src = src.replace(old, new)


# Patch expected counts robustly.
patterns = [
    (
        r"(EXPECTED_TEST_QUERIES\s*=\s*)360\b",
        rf"\g<1>{EXPECTED_QUERIES}",
        "EXPECTED_TEST_QUERIES"
    ),
    (
        r"(EXPECTED_TEST_COMPONENTS\s*=\s*)2520\b",
        rf"\g<1>{EXPECTED_COMPONENTS}",
        "EXPECTED_TEST_COMPONENTS"
    ),
]

for pattern, replacement, name in patterns:
    new_src, count = re.subn(pattern, replacement, src)

    if count != 1:
        raise RuntimeError(
            f"Could not uniquely patch {name}; replacements={count}"
        )

    src = new_src


# Keep the frozen gallery exactly 60.
if not re.search(
    r"EXPECTED_TEST_GALLERY_PROJECTS\s*=\s*60\b",
    src
):
    raise RuntimeError(
        "Could not verify frozen TEST gallery project count = 60."
    )


# Add an unmistakable generated-header note.
src = (
    "# AUTO-GENERATED PHASE11 ADAPTER.\n"
    "# Original algorithm: phase7h_final_test_evaluation.py\n"
    "# Frozen parameters are NOT modified.\n"
    "# Phase11 graph intentionally contains zero edges because queries are recomposed.\n\n"
    + src
)

GENERATED_RUNNER.write_text(
    src,
    encoding="utf-8"
)

print("generated:", GENERATED_RUNNER.relative_to(ROOT))


# ============================================================
# 6. Execute exact adapted Phase7H reconstruction
# ============================================================

print()
print("=== Execute frozen Phase7H logic on Phase11 ===")

proc = subprocess.run(
    [sys.executable, str(GENERATED_RUNNER)],
    cwd=str(ROOT),
)

if proc.returncode != 0:
    raise SystemExit(proc.returncode)


# ============================================================
# 7. Phase11C independent scoring
# ============================================================

print()
print("=== Phase11C scoring ===")

pred = read_csv(OUT_COMPONENTS)
qpred = read_csv(OUT_QUERIES)

if len(pred) != EXPECTED_COMPONENTS:
    raise RuntimeError(
        f"Expected {EXPECTED_COMPONENTS} predictions, got {len(pred)}"
    )

if qpred["query_id"].nunique() != EXPECTED_QUERIES:
    raise RuntimeError(
        f"Expected {EXPECTED_QUERIES} query predictions, "
        f"got {qpred['query_id'].nunique()}"
    )

private_by_node = {
    (r["query_id"], r["node_id"]): r
    for _, r in manifest.iterrows()
}

gt_by_q = {
    r["query_id"]: r
    for _, r in gt.iterrows()
}


def score_rows(component_df, query_df):
    truths = component_df["ground_truth_label"].tolist()
    predictions = component_df["predicted_label"].tolist()

    component_accuracy = safe_div(
        sum(t == p for t, p in zip(truths, predictions)),
        len(truths)
    )

    um = binary_unknown_metrics(truths, predictions)

    known_mask = [t != UNKNOWN for t in truths]

    known_total = sum(known_mask)

    known_correct = sum(
        t == p
        for t, p, known in zip(
            truths, predictions, known_mask
        )
        if known
    )

    known_component_accuracy = safe_div(
        known_correct,
        known_total
    )

    collapsed_f1s = []
    collapsed_exacts = []

    known_parent_f1s = []
    known_parent_exacts = []

    k_collapsed_correct = 0
    k_collapsed_errors = []

    actual_k_errors = []

    query_output = []

    by_query_components = {
        q: rr
        for q, rr in component_df.groupby("query_id")
    }

    for _, qr in query_df.iterrows():

        qid = qr["query_id"]
        gr = gt_by_q[qid]
        rr = by_query_components[qid]

        truth_set = set(rr["ground_truth_label"])
        pred_set = set(rr["predicted_label"])

        _, _, collapsed_f1, collapsed_exact = set_metrics(
            truth_set,
            pred_set
        )

        collapsed_f1s.append(collapsed_f1)
        collapsed_exacts.append(int(collapsed_exact))

        true_known = {
            x for x in truth_set
            if x != UNKNOWN
        }

        pred_known = {
            x for x in pred_set
            if x != UNKNOWN
        }

        _, _, known_f1, known_exact = set_metrics(
            true_known,
            pred_known
        )

        known_parent_f1s.append(known_f1)
        known_parent_exacts.append(int(known_exact))

        k_pred = len(pred_set)

        k_collapsed = int(
            gr["k_target_collapsed_unknown"]
        )

        k_actual = int(
            gr["k_true_actual_sources"]
        )

        k_collapsed_correct += int(
            k_pred == k_collapsed
        )

        k_collapsed_errors.append(
            abs(k_pred - k_collapsed)
        )

        # This is deliberately measured despite representational limitation.
        actual_k_errors.append(
            abs(k_pred - k_actual)
        )

        query_output.append({
            "query_id": qid,
            "scenario": gr["scenario"],
            "unknown_parent_count":
                int(gr["unknown_parent_count"]),
            "known_parent_count":
                int(gr["known_parent_count"]),
            "k_actual_sources":
                k_actual,
            "k_collapsed_target":
                k_collapsed,
            "k_pred_collapsed_labels":
                k_pred,
            "collapsed_parent_f1":
                collapsed_f1,
            "collapsed_parent_exact":
                bool(collapsed_exact),
            "known_parent_f1":
                known_f1,
            "known_parent_exact":
                bool(known_exact),
            "k_collapsed_correct":
                bool(k_pred == k_collapsed),
            "k_actual_absolute_error":
                abs(k_pred - k_actual),
        })

    return {
        "queries":
            len(query_output),

        "components":
            len(component_df),

        "component_accuracy":
            component_accuracy,

        "known_component_accuracy":
            known_component_accuracy,

        "unknown_precision":
            um["precision"],

        "unknown_recall":
            um["recall"],

        "unknown_f1":
            um["f1"],

        "collapsed_parent_set_f1":
            sum(collapsed_f1s) / len(collapsed_f1s),

        "collapsed_parent_set_exact":
            sum(collapsed_exacts) / len(collapsed_exacts),

        "registered_known_parent_f1":
            sum(known_parent_f1s) / len(known_parent_f1s),

        "registered_known_parent_exact":
            sum(known_parent_exacts) / len(known_parent_exacts),

        "k_collapsed_accuracy":
            safe_div(
                k_collapsed_correct,
                len(query_output)
            ),

        "k_collapsed_mae":
            sum(k_collapsed_errors)
            / len(k_collapsed_errors),

        "k_actual_source_count_mae":
            sum(actual_k_errors)
            / len(actual_k_errors),

        "query_rows":
            query_output,
    }


overall = score_rows(pred, qpred)


# ============================================================
# Scenario scoring
# ============================================================

scenario_rows = []

for scenario in sorted(gt["scenario"].unique()):

    qids = set(
        gt.loc[
            gt["scenario"] == scenario,
            "query_id"
        ]
    )

    cp = pred[
        pred["query_id"].isin(qids)
    ].copy()

    qp = qpred[
        qpred["query_id"].isin(qids)
    ].copy()

    m = score_rows(cp, qp)

    sample_gt = gt[
        gt["scenario"] == scenario
    ].iloc[0]

    scenario_rows.append({
        "scenario":
            scenario,

        "queries":
            m["queries"],

        "unknown_parent_count":
            int(sample_gt["unknown_parent_count"]),

        "known_parent_count":
            int(sample_gt["known_parent_count"]),

        "component_accuracy":
            m["component_accuracy"],

        "known_component_accuracy":
            m["known_component_accuracy"],

        "unknown_precision":
            m["unknown_precision"],

        "unknown_recall":
            m["unknown_recall"],

        "unknown_f1":
            m["unknown_f1"],

        "registered_known_parent_f1":
            m["registered_known_parent_f1"],

        "registered_known_parent_exact":
            m["registered_known_parent_exact"],

        "collapsed_parent_set_f1":
            m["collapsed_parent_set_f1"],

        "collapsed_parent_set_exact":
            m["collapsed_parent_set_exact"],

        "k_collapsed_accuracy":
            m["k_collapsed_accuracy"],

        "k_collapsed_mae":
            m["k_collapsed_mae"],

        "k_actual_source_count_mae":
            m["k_actual_source_count_mae"],
    })


scenario_df = pd.DataFrame(scenario_rows)
scenario_df.to_csv(OUT_SCENARIO, index=False)


# ============================================================
# By UNKNOWN multiplicity: 2 vs 3
# ============================================================

unknown_count_rows = []

for unknown_count in [2, 3]:

    qids = set(
        gt.loc[
            gt["unknown_parent_count"].astype(int)
            == unknown_count,
            "query_id"
        ]
    )

    cp = pred[
        pred["query_id"].isin(qids)
    ].copy()

    qp = qpred[
        qpred["query_id"].isin(qids)
    ].copy()

    m = score_rows(cp, qp)

    unknown_count_rows.append({
        "unknown_parent_count":
            unknown_count,

        "queries":
            m["queries"],

        "components":
            m["components"],

        "component_accuracy":
            m["component_accuracy"],

        "known_component_accuracy":
            m["known_component_accuracy"],

        "unknown_precision":
            m["unknown_precision"],

        "unknown_recall":
            m["unknown_recall"],

        "unknown_f1":
            m["unknown_f1"],

        "registered_known_parent_f1":
            m["registered_known_parent_f1"],

        "registered_known_parent_exact":
            m["registered_known_parent_exact"],

        "collapsed_parent_set_f1":
            m["collapsed_parent_set_f1"],

        "collapsed_parent_set_exact":
            m["collapsed_parent_set_exact"],

        "k_collapsed_accuracy":
            m["k_collapsed_accuracy"],

        "k_collapsed_mae":
            m["k_collapsed_mae"],

        "k_actual_source_count_mae":
            m["k_actual_source_count_mae"],
    })


unknown_count_df = pd.DataFrame(unknown_count_rows)
unknown_count_df.to_csv(
    OUT_UNKNOWN_COUNT,
    index=False
)


# ============================================================
# Modality metrics
# ============================================================

modality_metrics = {}

for modality, rr in pred.groupby("modality"):

    truth = rr["ground_truth_label"].tolist()
    prediction = rr["predicted_label"].tolist()

    um = binary_unknown_metrics(
        truth,
        prediction
    )

    modality_metrics[modality] = {
        "components":
            len(rr),

        "component_accuracy":
            safe_div(
                sum(t == p for t, p in zip(truth, prediction)),
                len(rr)
            ),

        "unknown_precision":
            um["precision"],

        "unknown_recall":
            um["recall"],

        "unknown_f1":
            um["f1"],
    }


# ============================================================
# Retrieval ceiling
# ============================================================

retrieval = read_csv(OUT_RETRIEVAL)

known_recall_values = []

all_present_values = []

for _, r in retrieval.iterrows():

    if int(r["known_true_parent_count"]) <= 0:
        continue

    if r["known_parent_recall"] != "":
        known_recall_values.append(
            float(r["known_parent_recall"])
        )

    v = str(
        r["all_known_true_parents_present"]
    ).strip().lower()

    if v in {"true", "1"}:
        all_present_values.append(1)
    elif v in {"false", "0"}:
        all_present_values.append(0)


retrieval_summary = {
    "queries_with_known_parent":
        len(known_recall_values),

    "mean_known_parent_recall":
        (
            sum(known_recall_values)
            / len(known_recall_values)
            if known_recall_values
            else None
        ),

    "all_known_true_parents_present_rate":
        (
            sum(all_present_values)
            / len(all_present_values)
            if all_present_values
            else None
        ),
}


# ============================================================
# Frozen parameter audit
# ============================================================

with open(
    ROOT / "results/phase7g_final_method_parameters.json",
    encoding="utf-8"
) as f:
    frozen = json.load(f)

with open(
    ROOT / "results/phase7g_final_method_freeze_summary.json",
    encoding="utf-8"
) as f:
    freeze_summary = json.load(f)


# ============================================================
# Final summary
# ============================================================

summary = {
    "phase11c_complete": True,

    "scope":
        "CONTROLLED_MULTI_UNKNOWN_ROBUSTNESS",

    "benchmark": {
        "queries":
            EXPECTED_QUERIES,

        "components":
            EXPECTED_COMPONENTS,

        "scenarios":
            {
                r["scenario"]: int(r["queries"])
                for _, r in scenario_df.iterrows()
            },

        "unknown_source_multiplicity":
            [2, 3],

        "independent_test_set":
            False,

        "construction":
            "Post-freeze recomposition of frozen TEST donor components.",

        "primary_frozen_test_modified":
            False,

        "manual_annotation_used":
            False,
    },

    "inference_protocol": {
        "phase7b_evidence":
            "Exact frozen donor evidence reused; no feature recomputation.",

        "gallery":
            "Original frozen 60-project TEST gallery.",

        "candidate_retrieval":
            "Frozen Phase7E mean-of-best-three component costs, M=10.",

        "solver":
            "Frozen Phase7H subset optimizer.",

        "graph_refinement":
            "Not applied because recomposed robustness queries have no empirical dependency graph.",

        "effective_track":
            "CONTENT_ONLY_HIERARCHICAL_RECONSTRUCTION",

        "parameter_retuning":
            False,

        "unknown_output_labels_per_query":
            1,

        "actual_unknown_source_identity_available_to_model":
            False,
    },

    "frozen_parameters": {
        "CODE_UNKNOWN_threshold":
            frozen["stage1"]["unknown_thresholds"]["CODE_BINARY"],

        "STRUCTURED_UNKNOWN_threshold":
            frozen["stage1"]["unknown_thresholds"]["STRUCTURED"],

        "IMAGE_UNKNOWN_threshold":
            frozen["stage1"]["unknown_thresholds"]["IMAGE"],

        "alpha":
            frozen["stage1"]["alpha_absolute_distance"],

        "mean_regret_weight":
            frozen["stage1"]["alpha_mean_regret"],

        "lambda":
            frozen["stage1"]["parent_proliferation_lambda"],

        "candidate_pool_M":
            frozen["stage1"]["candidate_pool_size"],

        "maximum_known_parents":
            frozen["query_definition"]["maximum_known_parents"],

        "maximum_unregistered_parent_labels":
            frozen["unknown_model"][
                "maximum_unregistered_parent_labels_per_query"
            ],
    },

    "overall": {
        k: v
        for k, v in overall.items()
        if k != "query_rows"
    },

    "retrieval_ceiling":
        retrieval_summary,

    "by_scenario":
        scenario_df.to_dict(orient="records"),

    "by_unknown_multiplicity":
        unknown_count_df.to_dict(orient="records"),

    "by_modality":
        modality_metrics,

    "structural_limitation": {
        "actual_multi_unknown_parent_identity_recovery":
            "UNSUPPORTED",

        "reason":
            "The frozen model exposes only one UNKNOWN label per query.",

        "interpretation":
            "UNKNOWN precision/recall/F1 measures rejection of unregistered components. "
            "It does not measure discrimination among multiple distinct held-out source projects.",

        "k_collapsed_definition":
            "number of registered known labels plus one if any UNKNOWN component is present",

        "k_actual_definition":
            "number of registered known parents plus the number of distinct held-out source projects",

        "k_actual_source_count_mae":
            overall["k_actual_source_count_mae"],
    },

    "freeze_integrity": {
        "phase7_final_method_frozen":
            frozen["final_method_frozen"],

        "phase7_test_used_for_selection":
            frozen["selection_history"]["test_used_for_selection"],

        "phase11_parameter_retuning":
            False,
    },
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
print("============================================================")
print("PHASE11C COMPLETE")
print("============================================================")
print(json.dumps(summary, indent=2, ensure_ascii=False))
print()
print("Outputs:")
print(" ", OUT_COMPONENTS.relative_to(ROOT))
print(" ", OUT_QUERIES.relative_to(ROOT))
print(" ", OUT_SCENARIO.relative_to(ROOT))
print(" ", OUT_UNKNOWN_COUNT.relative_to(ROOT))
print(" ", OUT_SUMMARY.relative_to(ROOT))
