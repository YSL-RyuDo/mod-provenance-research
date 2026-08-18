#!/usr/bin/env python3

import csv
import json
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]

NICAD_COMP = ROOT / "results" / "phase10a4d_nicad_component_predictions.csv"
NICAD_QUERY = ROOT / "results" / "phase10a4d_nicad_query_predictions.csv"
NICAD_MAP = ROOT / "results" / "phase10a4_nicad_query_mapping.csv"

PROPOSED = ROOT / "results" / "phase7h_final_component_predictions.csv"
STONE_QUERY = ROOT / "results" / "phase10a5_query_private_mapping.csv"

OUT_COMP = ROOT / "results" / "phase10a4e_same_subset_component_comparison.csv"
OUT_QUERY = ROOT / "results" / "phase10a4e_same_subset_query_comparison.csv"
OUT_SUMMARY = ROOT / "results" / "phase10a4e_same_subset_summary.json"


def load(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def truthy(x):
    return str(x).strip().lower() in {"1", "true", "yes"}


def find_col(headers, candidates, label):
    lower = {h.lower(): h for h in headers}

    for c in candidates:
        if c.lower() in lower:
            return lower[c.lower()]

    raise RuntimeError(
        f"Could not identify {label} column.\n"
        f"Available columns: {headers}"
    )


def f1(p, r):
    return 0.0 if p + r == 0 else 2 * p * r / (p + r)


def component_metrics(rows, pred_key):
    n = len(rows)

    correct = sum(
        r[pred_key] == r["gt"]
        for r in rows
    )

    tp = sum(
        r["gt"] == "UNKNOWN" and r[pred_key] == "UNKNOWN"
        for r in rows
    )
    fp = sum(
        r["gt"] != "UNKNOWN" and r[pred_key] == "UNKNOWN"
        for r in rows
    )
    fn = sum(
        r["gt"] == "UNKNOWN" and r[pred_key] != "UNKNOWN"
        for r in rows
    )

    p = tp / (tp + fp) if tp + fp else 0.0
    rr = tp / (tp + fn) if tp + fn else 0.0

    return {
        "n_components": n,
        "component_accuracy": correct / n if n else 0.0,
        "unknown_precision": p,
        "unknown_recall": rr,
        "unknown_f1": f1(p, rr),
        "predicted_unknown_rate": (
            sum(r[pred_key] == "UNKNOWN" for r in rows) / n
            if n else 0.0
        ),
    }


def query_metrics(component_rows, pred_key):
    by_q = defaultdict(list)

    for r in component_rows:
        by_q[r["anonymous_query_id"]].append(r)

    qrows = []

    for qid, rows in sorted(by_q.items()):
        gt_known = {
            r["gt"]
            for r in rows
            if r["gt"] != "UNKNOWN"
        }

        pred_known = {
            r[pred_key]
            for r in rows
            if r[pred_key] != "UNKNOWN"
        }

        gt_unknown = any(r["gt"] == "UNKNOWN" for r in rows)
        pred_unknown = any(r[pred_key] == "UNKNOWN" for r in rows)

        inter = len(gt_known & pred_known)

        pp = (
            inter / len(pred_known)
            if pred_known
            else (1.0 if not gt_known else 0.0)
        )

        pr = (
            inter / len(gt_known)
            if gt_known
            else (1.0 if not pred_known else 0.0)
        )

        pf1 = f1(pp, pr)

        parent_exact = gt_known == pred_known

        k_true_subset = len(gt_known) + (1 if gt_unknown else 0)
        k_pred_subset = len(pred_known) + (1 if pred_unknown else 0)

        qrows.append({
            "anonymous_query_id": qid,
            "parent_precision": pp,
            "parent_recall": pr,
            "parent_f1": pf1,
            "parent_exact": parent_exact,
            "k_true_subset": k_true_subset,
            "k_pred_subset": k_pred_subset,
            "k_correct": k_true_subset == k_pred_subset,
        })

    n = len(qrows)

    return {
        "n_queries": n,
        "parent_precision": sum(r["parent_precision"] for r in qrows) / n,
        "parent_recall": sum(r["parent_recall"] for r in qrows) / n,
        "parent_f1": sum(r["parent_f1"] for r in qrows) / n,
        "parent_exact": sum(r["parent_exact"] for r in qrows) / n,
        "k_accuracy": sum(r["k_correct"] for r in qrows) / n,
    }, qrows


def main():
    nicad = load(NICAD_COMP)
    nmap = load(NICAD_MAP)
    proposed = load(PROPOSED)
    stone = load(STONE_QUERY)

    if len(nicad) != 1169:
        raise RuntimeError(f"Expected 1169 NiCad components, got {len(nicad)}")

    headers = list(proposed[0].keys())

    node_col = find_col(
        headers,
        ["node_id", "component_id"],
        "node/component id"
    )

    pred_col = find_col(
        headers,
        [
            "prediction",
            "predicted_label",
            "prediction_label",
            "pred_label",
            "predicted_parent",
            "predicted_fresh_id",
            "y_pred",
        ],
        "proposed prediction"
    )

    stone_by_node = {r["node_id"]: r for r in stone}
    proposed_by_node = {r[node_col]: r for r in proposed}
    map_by_node = {r["node_id"]: r for r in nmap}

    rows = []
    missing = []

    for nr in nicad:
        node = nr["node_id"]

        if node not in proposed_by_node:
            missing.append(node)
            continue

        sm = stone_by_node[node]
        pm = proposed_by_node[node]
        nm = map_by_node[node]

        gt = sm["ground_truth_label"]

        proposed_pred = str(pm[pred_col]).strip()

        # Normalize common UNKNOWN spellings.
        if proposed_pred.upper() in {
            "UNKNOWN", "UNK", "NONE", "OPEN_SET"
        }:
            proposed_pred = "UNKNOWN"

        rows.append({
            "anonymous_query_id": sm["anonymous_query_id"],
            "query_id": sm["query_id"],
            "node_id": node,
            "scenario": sm["scenario"],
            "gt": gt,
            "nicad_pred": nr["prediction_fresh_id"],
            "proposed_pred": proposed_pred,
            "high_confidence_source_mapping":
                truthy(nm["high_confidence_mapping"]),
        })

    if missing:
        raise RuntimeError(
            f"{len(missing)} NiCad nodes missing from proposed predictions. "
            f"Examples: {missing[:10]}"
        )

    print("Detected proposed columns:")
    print(" node =", node_col)
    print(" pred =", pred_col)

    tracks = {}

    definitions = {
        "NICAD_RESOLVABLE": rows,
        "HIGH_CONF_COMPONENTS": [
            r for r in rows
            if r["high_confidence_source_mapping"]
        ],
    }

    all_query_nodes = defaultdict(list)
    for r in nmap:
        all_query_nodes[r["anonymous_query_id"]].append(r)

    # Strict query-level high-confidence = all five CODE components from the
    # original query are high-confidence.  Phase10A3 established 17 such
    # queries, so determine them from the full frozen mapping if possible.
    strict_high_qids = set()

    phase10a3 = load(
        ROOT / "results" / "phase10a3_class_to_java_mapping.csv"
    )

    tmp = defaultdict(list)
    for r in phase10a3:
        # Only TEST CODE nodes represented in the frozen NiCad query universe.
        if r["node_id"] in stone_by_node:
            tmp[stone_by_node[r["node_id"]]["anonymous_query_id"]].append(r)

    for qid, rr in tmp.items():
        if (
            len(rr) == 5
            and all(truthy(x["high_confidence_mapping"]) for x in rr)
        ):
            strict_high_qids.add(qid)

    for track_name, subset in definitions.items():
        pm = component_metrics(subset, "proposed_pred")
        nm = component_metrics(subset, "nicad_pred")

        pq, _ = query_metrics(subset, "proposed_pred")
        nq, _ = query_metrics(subset, "nicad_pred")

        tracks[track_name] = {
            "n_components": len(subset),
            "proposed": {**pm, **pq},
            "nicad": {**nm, **nq},
            "delta_proposed_minus_nicad": {
                "component_accuracy":
                    pm["component_accuracy"] - nm["component_accuracy"],
                "unknown_f1":
                    pm["unknown_f1"] - nm["unknown_f1"],
                "parent_f1":
                    pq["parent_f1"] - nq["parent_f1"],
                "parent_exact":
                    pq["parent_exact"] - nq["parent_exact"],
                "k_accuracy":
                    pq["k_accuracy"] - nq["k_accuracy"],
            }
        }

    strict_rows = [
        r for r in rows
        if r["anonymous_query_id"] in strict_high_qids
    ]

    if strict_rows:
        pm = component_metrics(strict_rows, "proposed_pred")
        nm = component_metrics(strict_rows, "nicad_pred")

        pq, _ = query_metrics(strict_rows, "proposed_pred")
        nq, _ = query_metrics(strict_rows, "nicad_pred")

        tracks["STRICT_HIGH_CONFIDENCE_QUERIES"] = {
            "n_components": len(strict_rows),
            "n_queries_expected": 17,
            "n_queries_actual": len(strict_high_qids),
            "proposed": {**pm, **pq},
            "nicad": {**nm, **nq},
            "delta_proposed_minus_nicad": {
                "component_accuracy":
                    pm["component_accuracy"] - nm["component_accuracy"],
                "unknown_f1":
                    pm["unknown_f1"] - nm["unknown_f1"],
                "parent_f1":
                    pq["parent_f1"] - nq["parent_f1"],
                "parent_exact":
                    pq["parent_exact"] - nq["parent_exact"],
                "k_accuracy":
                    pq["k_accuracy"] - nq["k_accuracy"],
            }
        }

    # Scenario comparison on same 1169 components.
    scenario = {}

    for sc in sorted({r["scenario"] for r in rows}):
        sr = [r for r in rows if r["scenario"] == sc]

        pcomp = component_metrics(sr, "proposed_pred")
        ncomp = component_metrics(sr, "nicad_pred")

        pq, _ = query_metrics(sr, "proposed_pred")
        nq, _ = query_metrics(sr, "nicad_pred")

        scenario[sc] = {
            "n_components": len(sr),
            "proposed": {**pcomp, **pq},
            "nicad": {**ncomp, **nq},
        }

    with OUT_COMP.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    summary = {
        "phase10a4e_complete": True,
        "comparison":
            "Proposed identity-neutral binary method vs NiCadCross "
            "on the exact same source-resolvable CODE component subset",
        "proposed_prediction_file":
            str(PROPOSED.relative_to(ROOT)),
        "detected_proposed_prediction_column": pred_col,
        "same_subset_components": len(rows),
        "same_subset_queries": len({
            r["anonymous_query_id"] for r in rows
        }),
        "strict_high_confidence_query_count": len(strict_high_qids),
        "tracks": tracks,
        "by_scenario": scenario,
        "interpretation": {
            "nicad_advantage":
                "NiCad receives reconstructed Java source corresponding to "
                "binary query components; the proposed method operates on "
                "the frozen binary-side evidence directly.",
            "no_test_retuning": True,
            "comparison_unit":
                "exact same NiCad-source-resolvable CODE nodes",
        }
    }

    OUT_SUMMARY.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print()
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
