#!/usr/bin/env python3

import csv
import json
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

INPUT = ROOT / "results" / "phase10a4e_same_subset_component_comparison.csv"
OUT_REPS = ROOT / "results" / "phase10a4f_nicad_paired_bootstrap_replicates.csv"
OUT_SUMMARY = ROOT / "results" / "phase10a4f_nicad_paired_bootstrap_summary.json"

N_BOOT = 10000
SEED = 20260813


def load(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def f1(p, r):
    return 0.0 if p + r == 0 else 2 * p * r / (p + r)


def component_metrics(rows, pred):
    n = len(rows)

    acc = sum(r[pred] == r["gt"] for r in rows) / n

    tp = sum(
        r["gt"] == "UNKNOWN" and r[pred] == "UNKNOWN"
        for r in rows
    )
    fp = sum(
        r["gt"] != "UNKNOWN" and r[pred] == "UNKNOWN"
        for r in rows
    )
    fn = sum(
        r["gt"] == "UNKNOWN" and r[pred] != "UNKNOWN"
        for r in rows
    )

    p = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0

    return acc, f1(p, rec)


def query_metrics(rows, pred):
    byq = defaultdict(list)

    for r in rows:
        byq[r["anonymous_query_id"]].append(r)

    f1s = []
    exacts = []
    ks = []

    for qrows in byq.values():
        gt = {
            r["gt"]
            for r in qrows
            if r["gt"] != "UNKNOWN"
        }

        pr = {
            r[pred]
            for r in qrows
            if r[pred] != "UNKNOWN"
        }

        gt_u = any(r["gt"] == "UNKNOWN" for r in qrows)
        pr_u = any(r[pred] == "UNKNOWN" for r in qrows)

        inter = len(gt & pr)

        pp = (
            inter / len(pr)
            if pr else
            (1.0 if not gt else 0.0)
        )

        rr = (
            inter / len(gt)
            if gt else
            (1.0 if not pr else 0.0)
        )

        f1s.append(f1(pp, rr))
        exacts.append(gt == pr)

        k_gt = len(gt) + int(gt_u)
        k_pr = len(pr) + int(pr_u)

        ks.append(k_gt == k_pr)

    n = len(f1s)

    return (
        sum(f1s) / n,
        sum(exacts) / n,
        sum(ks) / n,
    )


def metrics(rows, pred):
    ca, uf = component_metrics(rows, pred)
    pf, pe, ka = query_metrics(rows, pred)

    return {
        "component_accuracy": ca,
        "unknown_f1": uf,
        "parent_f1": pf,
        "parent_exact": pe,
        "k_subset_accuracy": ka,
    }


def percentile(vals, q):
    vals = sorted(vals)

    x = (len(vals) - 1) * q
    lo = int(x)
    hi = min(lo + 1, len(vals) - 1)
    frac = x - lo

    return vals[lo] * (1 - frac) + vals[hi] * frac


def main():
    rows = load(INPUT)

    byq = defaultdict(list)
    for r in rows:
        byq[r["anonymous_query_id"]].append(r)

    qids = sorted(byq)

    if len(qids) != 306:
        raise RuntimeError(f"Expected 306 queries, got {len(qids)}")

    observed_p = metrics(rows, "proposed_pred")
    observed_n = metrics(rows, "nicad_pred")

    observed_delta = {
        k: observed_p[k] - observed_n[k]
        for k in observed_p
    }

    rng = random.Random(SEED)

    reps = []

    for b in range(N_BOOT):
        sampled_qids = [
            rng.choice(qids)
            for _ in range(len(qids))
        ]

        # Preserve duplicate sampled query clusters.
        boot_rows = []

        for instance, qid in enumerate(sampled_qids):
            for r in byq[qid]:
                nr = dict(r)
                nr["anonymous_query_id"] = (
                    f"{qid}__BOOT{instance:04d}"
                )
                boot_rows.append(nr)

        pm = metrics(boot_rows, "proposed_pred")
        nm = metrics(boot_rows, "nicad_pred")

        rep = {"replicate": b}

        for k in pm:
            rep[f"proposed_{k}"] = pm[k]
            rep[f"nicad_{k}"] = nm[k]
            rep[f"delta_{k}"] = pm[k] - nm[k]

        reps.append(rep)

        if (b + 1) % 1000 == 0:
            print(f"[{b+1}/{N_BOOT}]")

    fields = list(reps[0].keys())

    with OUT_REPS.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(reps)

    ci = {}

    for metric in observed_delta:
        vals = [
            r[f"delta_{metric}"]
            for r in reps
        ]

        ci[metric] = {
            "observed_delta": observed_delta[metric],
            "ci95_lower": percentile(vals, 0.025),
            "ci95_upper": percentile(vals, 0.975),
            "bootstrap_probability_delta_gt_0":
                sum(v > 0 for v in vals) / len(vals),
        }

    summary = {
        "phase10a4f_complete": True,
        "method": "paired query-cluster bootstrap",
        "bootstrap_replicates": N_BOOT,
        "seed": SEED,
        "clusters": len(qids),
        "components": len(rows),
        "observed": {
            "proposed": observed_p,
            "nicad": observed_n,
            "delta_proposed_minus_nicad": observed_delta,
        },
        "delta_ci95": ci,
        "interpretation": {
            "resampling_unit":
                "query cluster; all source-resolvable CODE components "
                "for a sampled query are resampled together",
            "test_retuning": False,
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
