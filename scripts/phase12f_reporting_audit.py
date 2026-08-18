#!/usr/bin/env python3

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

A = ROOT / "results/phase12a_ann_candidate_summary.json"
B = ROOT / "results/phase12b_ann_downstream_summary.json"
C = ROOT / "results/phase12c_online_retrieval_summary.json"
D = ROOT / "results/phase12d_online_pool_downstream_summary.json"
E = ROOT / "results/phase12e_scalability_crossover_summary.json"

DM = ROOT / "results/phase12d_online_pool_downstream_metrics.csv"
EM = ROOT / "results/phase12e_scalability_crossover_metrics.csv"

OUT = ROOT / "results/phase12f_reporting_audit_summary.json"


for p in [A, B, C, D, E, DM, EM]:
    if not p.exists():
        raise FileNotFoundError(p)


a = json.loads(A.read_text(encoding="utf-8"))
b = json.loads(B.read_text(encoding="utf-8"))
c = json.loads(C.read_text(encoding="utf-8"))
d = json.loads(D.read_text(encoding="utf-8"))
e = json.loads(E.read_text(encoding="utf-8"))

dm = pd.read_csv(DM)
em = pd.read_csv(EM)


# ---------------------------------------------------------
# Completion / freeze integrity
# ---------------------------------------------------------

assert a["phase12a_complete"] is True
assert b["phase12b_complete"] is True
assert c["phase12c_complete"] is True
assert d["phase12d_complete"] is True
assert e["phase12e_complete"] is True

assert a["phase7_parameters_retuned"] is False
assert b["phase7_parameters_retuned"] is False
assert c["phase7_parameters_retuned"] is False
assert d["phase7_parameters_retuned"] is False
assert e["test_used_for_parameter_selection"] is False

assert c["online_exact_reproduces_frozen_phase7h_top10"] is True
assert d["frozen_beta0_reproduction"]["component_predictions_exact_match"] is True
assert d["frozen_beta0_reproduction"]["query_parent_sets_exact_match"] is True
assert e["scale60_integrity"]["exact_frozen_test_parent_universe"] is True
assert e["scale60_integrity"]["sampled_query_exact_top10_reproduction"] is True


# ---------------------------------------------------------
# Full-TEST downstream metrics from Phase12D
# ---------------------------------------------------------

def row(backend):
    r = dm[dm["backend"] == backend]

    if len(r) != 1:
        raise RuntimeError(
            f"Expected one Phase12D row for {backend}"
        )

    return r.iloc[0]


exact = row("EXACT")
fast = row("FAST")
balanced = row("BALANCED")
high = row("HIGH_RECALL")


# Verify frozen content-only baseline.
assert abs(
    exact["component_accuracy"]
    - 0.8071428571428572
) < 1e-12

assert abs(
    exact["unknown_f1"]
    - 0.7523862998315552
) < 1e-12

assert abs(
    exact["parent_set_f1"]
    - 0.8435449735449735
) < 1e-12

assert abs(
    exact["parent_set_exact"]
    - 0.41388888888888886
) < 1e-12

assert abs(
    exact["k_accuracy"]
    - 0.48055555555555557
) < 1e-12


# BALANCED/HIGH_RECALL must preserve aggregate downstream metrics.
for r in [balanced, high]:
    for metric in [
        "component_accuracy",
        "unknown_f1",
        "parent_set_f1",
        "parent_set_exact",
        "k_accuracy",
    ]:
        assert abs(
            float(r[metric])
            -
            float(exact[metric])
        ) < 1e-12


# FAST must only have the already-observed tiny degradation.
fast_delta = {
    "component_accuracy":
        float(
            fast["component_accuracy"]
            -
            exact["component_accuracy"]
        ),

    "unknown_f1":
        float(
            fast["unknown_f1"]
            -
            exact["unknown_f1"]
        ),

    "parent_set_f1":
        float(
            fast["parent_set_f1"]
            -
            exact["parent_set_f1"]
        ),

    "parent_set_exact":
        float(
            fast["parent_set_exact"]
            -
            exact["parent_set_exact"]
        ),

    "k_accuracy":
        float(
            fast["k_accuracy"]
            -
            exact["k_accuracy"]
        ),
}


# ---------------------------------------------------------
# Runtime / crossover
# ---------------------------------------------------------

def e_row(scale, backend):
    r = em[
        (em["scale"].astype(str) == str(scale))
        &
        (em["backend"] == backend)
    ]

    if len(r) != 1:
        raise RuntimeError(
            f"Expected one row for scale={scale}, backend={backend}"
        )

    return r.iloc[0]


runtime60 = {
    backend:
        {
            "p50_ms":
                float(
                    e_row("60", backend)["search_p50_ms"]
                ),
            "p95_ms":
                float(
                    e_row("60", backend)["search_p95_ms"]
                ),
            "speedup_p50_vs_exact":
                float(
                    e_row("60", backend)[
                        "speedup_p50_vs_exact"
                    ]
                ),
        }

    for backend in [
        "EXACT",
        "FAST",
        "BALANCED",
        "HIGH_RECALL",
    ]
}


runtime100 = {
    backend:
        {
            "p50_ms":
                float(
                    e_row("100", backend)["search_p50_ms"]
                ),
            "speedup_p50_vs_exact":
                float(
                    e_row("100", backend)[
                        "speedup_p50_vs_exact"
                    ]
                ),
        }

    for backend in [
        "EXACT",
        "FAST",
        "BALANCED",
        "HIGH_RECALL",
    ]
}


runtime1000 = {
    backend:
        {
            "p50_ms":
                float(
                    e_row("1000eq", backend)["search_p50_ms"]
                ),
            "speedup_p50_vs_exact":
                float(
                    e_row("1000eq", backend)[
                        "speedup_p50_vs_exact"
                    ]
                ),
        }

    for backend in [
        "EXACT",
        "FAST",
        "BALANCED",
        "HIGH_RECALL",
    ]
}


crossover = e["p50_crossover"]

assert (
    str(
        crossover["FAST"][
            "first_observed_p50_faster_scale"
        ]
    )
    ==
    "40"
)

assert (
    crossover["BALANCED"][
        "first_observed_p50_faster_scale"
    ]
    is None
)

assert (
    crossover["HIGH_RECALL"][
        "first_observed_p50_faster_scale"
    ]
    is None
)


summary = {
    "phase12f_complete": True,

    "scope":
        "REPORTING_ONLY_PHASE12_FREEZE_AUDIT",

    "predictions_recomputed": False,
    "parameters_retuned": False,
    "primary_test_modified": False,

    "phase12_interpretation": {
        "main_system_result":
            "Aggressive FAST LSH pruning provides a modest latency reduction with a very small downstream prediction change; conservative fidelity-preserving LSH configurations do not outperform vectorized exhaustive search at the evaluated scales.",

        "fast_real_crossover":
            "FAST first shows lower p50 latency than Exact at the 40-real-project scale.",

        "balanced_crossover":
            "No observed p50 crossover through 100 real projects and 1000-equivalent synthetic component-volume stress.",

        "high_recall_crossover":
            "No observed p50 crossover through 100 real projects and 1000-equivalent synthetic component-volume stress.",

        "accuracy_reporting_source":
            "Use full 360-query Phase12C/12D results for fidelity and downstream accuracy claims.",

        "scaling_reporting_source":
            "Use the deterministic stratified 120-query Phase12E sample only for runtime/scalability claims.",

        "synthetic_scope":
            "200eq/500eq/1000eq duplicate component arrays from 100 real registered parents and are computational component-volume stress tests, not 200/500/1000 unique real MOD projects.",
    },

    "full_test_downstream": {
        "EXACT": exact.to_dict(),
        "FAST": fast.to_dict(),
        "BALANCED": balanced.to_dict(),
        "HIGH_RECALL": high.to_dict(),
    },

    "fast_delta_from_exact": fast_delta,

    "scale60_runtime_sample": runtime60,
    "scale100_runtime_sample": runtime100,
    "scale1000eq_runtime_sample": runtime1000,

    "p50_crossover": crossover,

    "paper_safe_claims": [
        "The online exhaustive implementation exactly reproduced the frozen Phase7H Top-10 candidate pools.",
        "On the full frozen TEST set, BALANCED and HIGH_RECALL produced the same final content-only provenance predictions as Exact.",
        "FAST changed 1 of 360 query-level predictions and 1 of 2520 component predictions relative to Exact.",
        "FAST first achieved lower observed p50 search latency than Exact at the 40-project real-gallery scale.",
        "At 60 frozen TEST projects, FAST reduced p50 search latency while incurring only a very small downstream metric decrease.",
        "Fidelity-preserving BALANCED and HIGH_RECALL did not show a p50 speed advantage over Exact within the evaluated real and synthetic component-volume scales.",
    ],

    "claims_to_avoid": [
        "Do not claim ANN is universally faster than exhaustive search.",
        "Do not claim FAST is lossless.",
        "Do not report Phase12E sampled fidelity as the primary accuracy result.",
        "Do not call 200eq/500eq/1000eq evaluations on 200/500/1000 unique MOD projects.",
        "Do not claim a statistically significant ANN accuracy difference without a dedicated paired uncertainty analysis.",
    ],
}


OUT.write_text(
    json.dumps(
        summary,
        indent=2,
        ensure_ascii=False,
        default=lambda x:
            x.item()
            if hasattr(x, "item")
            else str(x),
    ),
    encoding="utf-8",
)


print("============================================")
print("Phase 12F - Reporting / Freeze Audit")
print("============================================")
print("All integrity assertions: PASS")
print()
print("FAST delta from Exact:")
print(
    json.dumps(
        fast_delta,
        indent=2,
    )
)
print()
print("P50 crossover:")
print(
    json.dumps(
        crossover,
        indent=2,
    )
)
print()
print("Wrote:", OUT)
