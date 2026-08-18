#!/usr/bin/env python3

import csv
import json
import re
import xml.etree.ElementTree as ET
from collections import defaultdict, Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

QUERY_MAP = ROOT / "results" / "phase10a4_nicad_query_mapping.csv"
STONE_QUERY = ROOT / "results" / "phase10a5_query_private_mapping.csv"
GALLERY_MAP = ROOT / "results" / "phase10a4b_gallery_class_to_java_mapping.csv"
PARENT_MAP = ROOT / "results" / "phase10a5_parent_private_mapping.csv"

NICAD_XML = Path.home() / "Open-NiCad" / "nicadclones" / \
    "phase10a4_nicad_query_corpus" / \
    "phase10a4_nicad_query_corpus_functions-blind-crossclones" / \
    "phase10a4_nicad_query_corpus_functions-blind-crossclones-0.30.xml"

OUT_PAIRS = ROOT / "results" / "phase10a4d_nicad_clone_pairs.csv"
OUT_COMPONENT = ROOT / "results" / "phase10a4d_nicad_component_predictions.csv"
OUT_QUERY = ROOT / "results" / "phase10a4d_nicad_query_predictions.csv"
OUT_SUMMARY = ROOT / "results" / "phase10a4d_nicad_summary.json"


def load_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def truthy(x):
    return str(x).strip().lower() in {"true", "1", "yes"}


def f1(p, r):
    return 0.0 if p + r == 0 else 2 * p * r / (p + r)


def parse_qid_component(path):
    p = path.replace("\\", "/")

    # expected:
    # .../Q0001/Q0001_N01/Query.java
    m = re.search(r"/(Q\d{4})/(Q\d{4}_N\d+)/Query\.java$", p)
    if not m:
        return None, None

    return m.group(1), m.group(2)


def parse_parent(path):
    p = path.replace("\\", "/")

    # expected:
    # .../P0001/P0001_S000001.java
    m = re.search(r"/(P\d{4})/P\d{4}_S\d+\.java$", p)
    if not m:
        return None

    return m.group(1)


def extract_sources(elem):
    out = []

    for src in elem.iter("source"):
        file_attr = src.attrib.get("file", "")
        if file_attr:
            out.append({
                "file": file_attr,
                "startline": src.attrib.get("startline", ""),
                "endline": src.attrib.get("endline", "")
            })

    return out


def main():
    qmap = load_csv(QUERY_MAP)
    stone_q = load_csv(STONE_QUERY)
    gmap = load_csv(GALLERY_MAP)
    pmap = load_csv(PARENT_MAP)

    if not NICAD_XML.is_file():
        raise RuntimeError(f"Missing NiCad XML: {NICAD_XML}")

    # node_id -> query source metadata
    q_by_node = {r["node_id"]: r for r in qmap}

    # anonymous component stem -> node id
    anon_component_to_node = {}
    for r in qmap:
        stem = Path(r["nicad_source_relpath"]).parent.name
        anon_component_to_node[stem] = r["node_id"]

    stone_by_node = {r["node_id"]: r for r in stone_q}

    fresh_to_parent = {
        r["fresh_id"]: r["anonymous_parent_id"]
        for r in pmap
    }

    parent_to_fresh = {
        r["anonymous_parent_id"]: r["fresh_id"]
        for r in pmap
    }

    # source availability by parent
    parent_source_available = {
        r["anonymous_parent_id"]
        for r in gmap
        if truthy(r["source_resolvable"])
    }

    tree = ET.parse(NICAD_XML)
    root = tree.getroot()

    pair_rows = []
    support = defaultdict(lambda: Counter())

    pair_count = 0
    skipped_pair_shape = 0

    for clone in root.iter("clone"):
        sources = extract_sources(clone)

        if len(sources) < 2:
            skipped_pair_shape += 1
            continue

        # NiCad cross-clone pair should have source from query + gallery.
        qsrc = None
        gsrc = None

        for s in sources:
            qid, comp = parse_qid_component(s["file"])
            parent = parse_parent(s["file"])

            if qid and comp:
                qsrc = (s, qid, comp)

            if parent:
                gsrc = (s, parent)

        if not qsrc or not gsrc:
            # Fallback because NiCad may emit relative paths without leading slash.
            for s in sources:
                p = s["file"].replace("\\", "/")

                mq = re.search(r"(Q\d{4})/(Q\d{4}_N\d+)/Query\.java$", p)
                if mq:
                    qsrc = (s, mq.group(1), mq.group(2))

                mg = re.search(r"(P\d{4})/P\d{4}_S\d+\.java$", p)
                if mg:
                    gsrc = (s, mg.group(1))

        if not qsrc or not gsrc:
            skipped_pair_shape += 1
            continue

        qs, anon_qid, anon_comp = qsrc
        gs, parent_id = gsrc

        node_id = anon_component_to_node.get(anon_comp)

        if not node_id:
            skipped_pair_shape += 1
            continue

        pair_count += 1

        # DISTINCT QUERY METHOD support:
        # one query source-function should count at most once per parent.
        method_key = (
            qs["file"],
            qs["startline"],
            qs["endline"],
        )

        support[(node_id, parent_id)][method_key] += 1

        pair_rows.append({
            "node_id": node_id,
            "anonymous_query_id": anon_qid,
            "anonymous_component_id": anon_comp,
            "anonymous_parent_id": parent_id,
            "parent_fresh_id": parent_to_fresh.get(parent_id, ""),
            "query_file": qs["file"],
            "query_startline": qs["startline"],
            "query_endline": qs["endline"],
            "gallery_file": gs["file"],
            "gallery_startline": gs["startline"],
            "gallery_endline": gs["endline"],
        })

    # convert method support to distinct query method counts
    component_parent_support = defaultdict(dict)

    for (node_id, parent_id), methods in support.items():
        component_parent_support[node_id][parent_id] = len(methods)

    component_rows = []

    for r in qmap:
        node_id = r["node_id"]
        gt_fresh = r["source_fresh_id"]
        gt_parent = fresh_to_parent.get(gt_fresh, "")

        scores = component_parent_support.get(node_id, {})

        if not scores:
            pred_parent = "UNKNOWN"
            max_support = 0
            tied = []
        else:
            max_support = max(scores.values())
            tied = sorted([
                p for p, s in scores.items()
                if s == max_support
            ])

            if len(tied) == 1:
                pred_parent = tied[0]
            else:
                pred_parent = "UNKNOWN"

        pred_fresh = (
            parent_to_fresh.get(pred_parent, "")
            if pred_parent != "UNKNOWN"
            else "UNKNOWN"
        )

        gt_known = bool(gt_parent)
        gallery_available = gt_parent in parent_source_available if gt_parent else False

        correct = (
            pred_fresh == gt_fresh
            if gt_fresh != "UNKNOWN"
            else pred_fresh == "UNKNOWN"
        )

        component_rows.append({
            "anonymous_query_id": r["anonymous_query_id"],
            "query_id": r["query_id"],
            "node_id": node_id,
            "ground_truth_fresh_id": gt_fresh,
            "ground_truth_parent_id": gt_parent,
            "prediction_fresh_id": pred_fresh,
            "prediction_parent_id": pred_parent,
            "max_distinct_query_method_support": max_support,
            "tie_count": len(tied),
            "candidate_parent_count": len(scores),
            "correct": correct,
            "high_confidence_query_source": truthy(r["high_confidence_mapping"]),
            "ground_truth_gallery_source_available": gallery_available,
            "snapshot_resolution": r["snapshot_resolution"],
        })

    # query-level reconstruction
    by_q = defaultdict(list)
    for r in component_rows:
        by_q[r["anonymous_query_id"]].append(r)

    query_rows = []

    for aqid, rows in sorted(by_q.items()):
        meta = stone_by_node[rows[0]["node_id"]]

        gt_known = {
            r["ground_truth_fresh_id"]
            for r in rows
            if r["ground_truth_fresh_id"] != "UNKNOWN"
        }

        pred_known = {
            r["prediction_fresh_id"]
            for r in rows
            if r["prediction_fresh_id"] != "UNKNOWN"
        }

        inter = len(gt_known & pred_known)

        pp = (
            inter / len(pred_known)
            if pred_known else
            (1.0 if not gt_known else 0.0)
        )

        pr = (
            inter / len(gt_known)
            if gt_known else
            (1.0 if not pred_known else 0.0)
        )

        qf1 = f1(pp, pr)

        exact = gt_known == pred_known

        # NiCad CODE-only K = number of predicted known parents.
        k_pred = len(pred_known)

        query_rows.append({
            "anonymous_query_id": aqid,
            "query_id": meta["query_id"],
            "scenario": meta["scenario"],
            "k_true": int(meta["k_true"]),
            "k_pred": k_pred,
            "parent_precision": pp,
            "parent_recall": pr,
            "parent_f1": qf1,
            "parent_exact": exact,
            "k_correct": k_pred == int(meta["k_true"]),
            "component_count": len(rows),
            "all_query_sources_high_confidence": all(
                r["high_confidence_query_source"]
                for r in rows
            ),
            "all_gt_known_gallery_source_available": all(
                (
                    r["ground_truth_fresh_id"] == "UNKNOWN"
                    or r["ground_truth_gallery_source_available"]
                )
                for r in rows
            ),
        })

    def subset_component(rows, mode):
        if mode == "RESOLVABLE":
            return rows

        if mode == "AVAILABLE_GALLERY":
            return [
                r for r in rows
                if (
                    r["ground_truth_fresh_id"] == "UNKNOWN"
                    or r["ground_truth_gallery_source_available"]
                )
            ]

        if mode == "HIGH_CONFIDENCE":
            return [
                r for r in rows
                if r["high_confidence_query_source"]
            ]

        raise ValueError(mode)

    def metrics_for_components(rows):
        n = len(rows)
        if not n:
            return {}

        acc = sum(r["correct"] for r in rows) / n

        # UNKNOWN metrics
        tp = sum(
            r["ground_truth_fresh_id"] == "UNKNOWN"
            and r["prediction_fresh_id"] == "UNKNOWN"
            for r in rows
        )
        fp = sum(
            r["ground_truth_fresh_id"] != "UNKNOWN"
            and r["prediction_fresh_id"] == "UNKNOWN"
            for r in rows
        )
        fn = sum(
            r["ground_truth_fresh_id"] == "UNKNOWN"
            and r["prediction_fresh_id"] != "UNKNOWN"
            for r in rows
        )

        up = tp / (tp + fp) if tp + fp else 0.0
        ur = tp / (tp + fn) if tp + fn else 0.0
        uf = f1(up, ur)

        return {
            "n_components": n,
            "component_accuracy": acc,
            "unknown_precision": up,
            "unknown_recall": ur,
            "unknown_f1": uf,
            "predicted_unknown_rate": sum(
                r["prediction_fresh_id"] == "UNKNOWN"
                for r in rows
            ) / n,
            "gt_gallery_available_rate": sum(
                r["ground_truth_gallery_source_available"]
                for r in rows
                if r["ground_truth_fresh_id"] != "UNKNOWN"
            ) / max(
                1,
                sum(
                    r["ground_truth_fresh_id"] != "UNKNOWN"
                    for r in rows
                )
            ),
        }

    def metrics_for_queries(rows):
        n = len(rows)
        if not n:
            return {}

        return {
            "n_queries": n,
            "parent_precision": sum(r["parent_precision"] for r in rows) / n,
            "parent_recall": sum(r["parent_recall"] for r in rows) / n,
            "parent_f1": sum(r["parent_f1"] for r in rows) / n,
            "parent_exact": sum(r["parent_exact"] for r in rows) / n,
            "k_accuracy": sum(r["k_correct"] for r in rows) / n,
        }

    tracks = {}

    for mode in ["RESOLVABLE", "AVAILABLE_GALLERY", "HIGH_CONFIDENCE"]:
        cr = subset_component(component_rows, mode)

        qids = {r["anonymous_query_id"] for r in cr}

        if mode == "AVAILABLE_GALLERY":
            qr = [
                r for r in query_rows
                if r["all_gt_known_gallery_source_available"]
            ]
        elif mode == "HIGH_CONFIDENCE":
            qr = [
                r for r in query_rows
                if r["all_query_sources_high_confidence"]
            ]
        else:
            qr = query_rows

        tracks[mode] = {
            **metrics_for_components(cr),
            **metrics_for_queries(qr)
        }

    scenario = {}
    for sc in sorted({r["scenario"] for r in query_rows}):
        rr = [r for r in query_rows if r["scenario"] == sc]
        scenario[sc] = metrics_for_queries(rr)

    # write outputs
    with OUT_PAIRS.open("w", encoding="utf-8", newline="") as f:
        fields = list(pair_rows[0].keys()) if pair_rows else [
            "node_id",
            "anonymous_query_id",
            "anonymous_component_id",
            "anonymous_parent_id",
            "parent_fresh_id",
            "query_file",
            "query_startline",
            "query_endline",
            "gallery_file",
            "gallery_startline",
            "gallery_endline",
        ]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(pair_rows)

    with OUT_COMPONENT.open("w", encoding="utf-8", newline="") as f:
        fields = list(component_rows[0].keys())
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(component_rows)

    with OUT_QUERY.open("w", encoding="utf-8", newline="") as f:
        fields = list(query_rows[0].keys())
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(query_rows)

    summary = {
        "phase10a4d_complete": True,
        "baseline": "NiCadCross 7.0",
        "granularity": "functions",
        "language": "java",
        "configuration": "default/blindrename",
        "threshold": 0.30,
        "query_source_resolvable_components": len(qmap),
        "query_source_resolvable_queries": len({
            r["anonymous_query_id"] for r in qmap
        }),
        "gallery_source_available_parents": len(parent_source_available),
        "parsed_clone_pairs": pair_count,
        "skipped_pair_shapes": skipped_pair_shape,
        "tracks": tracks,
        "by_scenario": scenario,
        "protocol": {
            "component_parent_support":
                "number of distinct query methods with >=1 cross-clone into a parent",
            "decision":
                "highest support; no support -> UNKNOWN; exact tie -> UNKNOWN",
            "test_retuning": False,
            "manual_annotation": False,
        }
    }

    OUT_SUMMARY.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
