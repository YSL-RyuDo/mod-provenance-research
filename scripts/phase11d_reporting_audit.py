#!/usr/bin/env python3

import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

COMPONENT_FILE = ROOT / "results/phase11b_component_predictions.csv"
GT_FILE = ROOT / "results/phase11a_multi_unknown_ground_truth.csv"

OUT_SUMMARY = ROOT / "results/phase11d_reporting_audit_summary.json"
OUT_SCENARIO = ROOT / "results/phase11d_reporting_by_scenario.csv"


def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def div(a, b):
    return a / b if b else 0.0


def f1(p, r):
    return 2 * p * r / (p + r) if (p + r) else 0.0


def parent_metrics(true_set, pred_set):
    true_set = set(true_set)
    pred_set = set(pred_set)

    inter = len(true_set & pred_set)

    p = div(inter, len(pred_set))
    r = div(inter, len(true_set))
    score = f1(p, r)

    return {
        "precision": p,
        "recall": r,
        "f1": score,
        "exact": true_set == pred_set,
    }


components = read_csv(COMPONENT_FILE)
gt_rows = read_csv(GT_FILE)

gt_by_q = {
    r["query_id"]: r
    for r in gt_rows
}

by_query = defaultdict(list)

for r in components:
    by_query[r["query_id"]].append(r)

if len(gt_rows) != 180:
    raise RuntimeError(f"Expected 180 GT queries, got {len(gt_rows)}")

if len(components) != 1260:
    raise RuntimeError(f"Expected 1260 components, got {len(components)}")

if len(by_query) != 180:
    raise RuntimeError(f"Expected 180 predicted queries, got {len(by_query)}")


# ============================================================
# Overall component / UNKNOWN metrics
# ============================================================

component_correct = 0

tp = fp = fn = 0

for r in components:
    truth = r["ground_truth_label"]
    pred = r["predicted_label"]

    component_correct += int(truth == pred)

    truth_u = truth == "UNKNOWN"
    pred_u = pred == "UNKNOWN"

    tp += int(truth_u and pred_u)
    fp += int((not truth_u) and pred_u)
    fn += int(truth_u and (not pred_u))

unknown_precision = div(tp, tp + fp)
unknown_recall = div(tp, tp + fn)
unknown_f1 = f1(unknown_precision, unknown_recall)


# ============================================================
# Query metrics
# ============================================================

collapsed_f1_values = []
collapsed_exact = 0

k_collapsed_correct = 0
k_collapsed_abs_error = []

actual_k_abs_error = []

registered_p = []
registered_r = []
registered_f1 = []
registered_exact = 0
registered_query_count = 0

scenario_rows = []

scenario_data = defaultdict(
    lambda: {
        "queries": 0,
        "component_total": 0,
        "component_correct": 0,

        "unknown_tp": 0,
        "unknown_fp": 0,
        "unknown_fn": 0,

        "collapsed_f1": [],
        "collapsed_exact": 0,

        "k_collapsed_correct": 0,
        "k_collapsed_errors": [],
        "actual_k_errors": [],

        "known_parent_queries": 0,
        "known_parent_precision": [],
        "known_parent_recall": [],
        "known_parent_f1": [],
        "known_parent_exact": 0,
    }
)


for qid, rr in sorted(by_query.items()):

    g = gt_by_q[qid]
    scenario = g["scenario"]

    truth_labels = [r["ground_truth_label"] for r in rr]
    pred_labels = [r["predicted_label"] for r in rr]

    truth_set = set(truth_labels)
    pred_set = set(pred_labels)

    # --------------------------------------------------------
    # Collapsed parent set:
    # known IDs + at most one UNKNOWN label
    # --------------------------------------------------------

    cm = parent_metrics(truth_set, pred_set)

    collapsed_f1_values.append(cm["f1"])
    collapsed_exact += int(cm["exact"])

    k_collapsed_true = int(g["k_target_collapsed_unknown"])
    k_actual_true = int(g["k_true_actual_sources"])
    k_pred = len(pred_set)

    k_collapsed_correct += int(k_pred == k_collapsed_true)
    k_collapsed_abs_error.append(abs(k_pred - k_collapsed_true))
    actual_k_abs_error.append(abs(k_pred - k_actual_true))

    # --------------------------------------------------------
    # Registered-parent metrics:
    # IMPORTANT: evaluate ONLY queries that actually contain
    # >= 1 registered/known parent.
    # --------------------------------------------------------

    true_known = {
        x for x in truth_set
        if x != "UNKNOWN"
    }

    pred_known = {
        x for x in pred_set
        if x != "UNKNOWN"
    }

    known_parent_count = int(g["known_parent_count"])

    if known_parent_count > 0:
        km = parent_metrics(true_known, pred_known)

        registered_query_count += 1

        registered_p.append(km["precision"])
        registered_r.append(km["recall"])
        registered_f1.append(km["f1"])
        registered_exact += int(km["exact"])

    # --------------------------------------------------------
    # Scenario accumulation
    # --------------------------------------------------------

    s = scenario_data[scenario]
    s["queries"] += 1

    for truth, pred in zip(truth_labels, pred_labels):
        s["component_total"] += 1
        s["component_correct"] += int(truth == pred)

        truth_u = truth == "UNKNOWN"
        pred_u = pred == "UNKNOWN"

        s["unknown_tp"] += int(truth_u and pred_u)
        s["unknown_fp"] += int((not truth_u) and pred_u)
        s["unknown_fn"] += int(truth_u and (not pred_u))

    s["collapsed_f1"].append(cm["f1"])
    s["collapsed_exact"] += int(cm["exact"])

    s["k_collapsed_correct"] += int(
        k_pred == k_collapsed_true
    )

    s["k_collapsed_errors"].append(
        abs(k_pred - k_collapsed_true)
    )

    s["actual_k_errors"].append(
        abs(k_pred - k_actual_true)
    )

    if known_parent_count > 0:
        km = parent_metrics(true_known, pred_known)

        s["known_parent_queries"] += 1
        s["known_parent_precision"].append(km["precision"])
        s["known_parent_recall"].append(km["recall"])
        s["known_parent_f1"].append(km["f1"])
        s["known_parent_exact"] += int(km["exact"])


# ============================================================
# Scenario table
# ============================================================

for scenario, s in sorted(scenario_data.items()):

    up = div(
        s["unknown_tp"],
        s["unknown_tp"] + s["unknown_fp"]
    )

    ur = div(
        s["unknown_tp"],
        s["unknown_tp"] + s["unknown_fn"]
    )

    uf = f1(up, ur)

    n_known_q = s["known_parent_queries"]

    row = {
        "scenario": scenario,
        "queries": s["queries"],

        "component_accuracy":
            div(
                s["component_correct"],
                s["component_total"]
            ),

        "unknown_precision": up,
        "unknown_recall": ur,
        "unknown_f1": uf,

        "collapsed_parent_set_f1":
            sum(s["collapsed_f1"])
            / len(s["collapsed_f1"]),

        "collapsed_parent_set_exact":
            div(
                s["collapsed_exact"],
                s["queries"]
            ),

        "k_collapsed_accuracy":
            div(
                s["k_collapsed_correct"],
                s["queries"]
            ),

        "k_collapsed_mae":
            sum(s["k_collapsed_errors"])
            / len(s["k_collapsed_errors"]),

        "k_actual_source_count_mae":
            sum(s["actual_k_errors"])
            / len(s["actual_k_errors"]),

        "registered_parent_query_count":
            n_known_q,

        "registered_parent_precision":
            (
                sum(s["known_parent_precision"])
                / n_known_q
                if n_known_q else None
            ),

        "registered_parent_recall":
            (
                sum(s["known_parent_recall"])
                / n_known_q
                if n_known_q else None
            ),

        "registered_parent_f1":
            (
                sum(s["known_parent_f1"])
                / n_known_q
                if n_known_q else None
            ),

        "registered_parent_exact":
            (
                div(
                    s["known_parent_exact"],
                    n_known_q
                )
                if n_known_q else None
            ),
    }

    scenario_rows.append(row)


with OUT_SCENARIO.open(
    "w",
    encoding="utf-8",
    newline=""
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=list(scenario_rows[0].keys())
    )

    writer.writeheader()
    writer.writerows(scenario_rows)


# ============================================================
# Final report-safe summary
# ============================================================

summary = {
    "phase11d_complete": True,

    "scope":
        "REPORTING_ONLY_METRIC_AUDIT",

    "inputs_unchanged": True,
    "predictions_recomputed": False,
    "parameters_retuned": False,
    "primary_test_modified": False,

    "benchmark": {
        "queries": 180,
        "components": 1260,
        "registered_parent_queries": registered_query_count,
        "unknown_only_queries": 180 - registered_query_count,
    },

    "overall_reporting_metrics": {
        "component_accuracy":
            div(component_correct, len(components)),

        "unknown_precision":
            unknown_precision,

        "unknown_recall":
            unknown_recall,

        "unknown_f1":
            unknown_f1,

        "collapsed_parent_set_f1":
            sum(collapsed_f1_values)
            / len(collapsed_f1_values),

        "collapsed_parent_set_exact":
            div(collapsed_exact, 180),

        "k_collapsed_accuracy":
            div(k_collapsed_correct, 180),

        "k_collapsed_mae":
            sum(k_collapsed_abs_error)
            / len(k_collapsed_abs_error),

        "k_actual_source_count_mae":
            sum(actual_k_abs_error)
            / len(actual_k_abs_error),
    },

    "registered_parent_metrics_known_queries_only": {
        "queries":
            registered_query_count,

        "precision":
            sum(registered_p)
            / registered_query_count,

        "recall":
            sum(registered_r)
            / registered_query_count,

        "f1":
            sum(registered_f1)
            / registered_query_count,

        "exact":
            div(
                registered_exact,
                registered_query_count
            ),
    },

    "reporting_rule": {
        "registered_parent_metrics":
            "Computed only on queries containing at least one registered known parent.",

        "unknown_only_scenarios":
            "Registered-parent precision/recall/F1/exact are N/A, not zero and not empty-set correctness.",

        "unknown_metric":
            "UNKNOWN F1 evaluates rejection of unregistered components, not discrimination among distinct unknown source projects.",

        "actual_unknown_multiplicity":
            "Not representable by the frozen single-UNKNOWN model.",
    },

    "by_scenario":
        scenario_rows,
}

OUT_SUMMARY.write_text(
    json.dumps(
        summary,
        indent=2,
        ensure_ascii=False
    ),
    encoding="utf-8"
)

print(json.dumps(
    summary,
    indent=2,
    ensure_ascii=False
))
