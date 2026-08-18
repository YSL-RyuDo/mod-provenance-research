#!/usr/bin/env python3

import csv
import json
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

SCORES_FILE = ROOT / "results/phase7h_test_component_parent_scores.csv"
POOLS_FILE = ROOT / "results/phase12c_online_retrieval_queries.csv"
BASE_COMPONENT_FILE = ROOT / "results/phase7h_beta0_component_predictions.csv"
BASE_QUERY_FILE = ROOT / "results/phase7h_beta0_query_predictions.csv"

GT_CANDIDATES = [
    ROOT / "results/phase6k_query_manifest_private.csv",
    ROOT / "results/phase6l_materialized_private_manifest.csv",
]

OUT_METRICS = ROOT / "results/phase12d_online_pool_downstream_metrics.csv"
OUT_QUERY = ROOT / "results/phase12d_online_pool_query_predictions.csv"
OUT_COMPONENT = ROOT / "results/phase12d_online_pool_component_predictions.csv"
OUT_SUMMARY = ROOT / "results/phase12d_online_pool_downstream_summary.json"


THRESHOLDS = {
    "CODE_BINARY": 0.1302083283662796,
    "STRUCTURED": 0.03125,
    "IMAGE": 0.0,
}

ALPHA = 0.75
REGRET_WEIGHT = 0.25
LAMBDA = 0.5
MAX_KNOWN_PARENTS = 3
UNKNOWN = "UNKNOWN"
EPSILON = 1e-12

BACKENDS = [
    "EXACT",
    "FAST",
    "BALANCED",
    "HIGH_RECALL",
]


def clean(value):
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    return str(value).strip()


def find_col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c

    raise RuntimeError(
        "None of columns exist: "
        + repr(candidates)
        + "\nAvailable: "
        + repr(list(df.columns))
    )


def normalized_component_cost(
    modality,
    distance,
    regret,
):
    threshold = THRESHOLDS[modality]

    distance = float(distance)
    regret = float(regret)

    if threshold > 0:
        eligible = bool(
            distance <= threshold + EPSILON
        )

        normalized_distance = min(
            distance / threshold,
            1.0,
        )

    else:
        eligible = bool(
            abs(distance) <= EPSILON
        )

        normalized_distance = (
            0.0
            if eligible
            else 1.0
        )

    normalized_regret = min(
        max(regret, 0.0),
        1.0,
    )

    cost = (
        ALPHA * normalized_distance
        +
        REGRET_WEIGHT * normalized_regret
    )

    return float(cost), eligible


def set_metrics(true_set, pred_set):
    true_set = set(true_set)
    pred_set = set(pred_set)

    inter = len(true_set & pred_set)

    precision = (
        inter / len(pred_set)
        if pred_set
        else (
            1.0
            if not true_set
            else 0.0
        )
    )

    recall = (
        inter / len(true_set)
        if true_set
        else (
            1.0
            if not pred_set
            else 0.0
        )
    )

    f1 = (
        2.0 * precision * recall
        / (precision + recall)
        if precision + recall
        else 0.0
    )

    return {
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "exact": bool(true_set == pred_set),
    }


for path in [
    SCORES_FILE,
    POOLS_FILE,
    BASE_COMPONENT_FILE,
    BASE_QUERY_FILE,
]:
    if not path.exists():
        raise FileNotFoundError(path)


gt_file = None

for path in GT_CANDIDATES:
    if path.exists():
        gt_file = path
        break

if gt_file is None:
    raise FileNotFoundError(
        "Could not locate frozen private query manifest"
    )


print("==========================================")
print("Phase 12D - Online Pool Downstream Evaluation")
print("==========================================")
print("Ground truth:", gt_file)


scores = pd.read_csv(
    SCORES_FILE,
    dtype=str,
    keep_default_na=False,
)

pools = pd.read_csv(
    POOLS_FILE,
    dtype=str,
    keep_default_na=False,
)

base_component = pd.read_csv(
    BASE_COMPONENT_FILE,
    dtype=str,
    keep_default_na=False,
)

base_query = pd.read_csv(
    BASE_QUERY_FILE,
    dtype=str,
    keep_default_na=False,
)

gt = pd.read_csv(
    gt_file,
    dtype=str,
    keep_default_na=False,
)


test_query_ids = sorted(
    base_query["query_id"]
    .astype(str)
    .unique()
    .tolist()
)

if len(test_query_ids) != 360:
    raise RuntimeError(
        f"Expected 360 TEST queries, got {len(test_query_ids)}"
    )


gt = gt[
    gt["query_id"]
    .astype(str)
    .isin(test_query_ids)
].copy()


if len(gt) != 2520:
    raise RuntimeError(
        f"Expected 2520 TEST components in GT, got {len(gt)}"
    )


GT_LABEL_COL = find_col(
    gt,
    [
        "ground_truth_label",
        "true_label",
        "truth_label",
    ],
)

GT_MODALITY_COL = find_col(
    gt,
    [
        "modality",
    ],
)

BASE_PRED_COL = find_col(
    base_component,
    [
        "predicted_label",
        "prediction",
        "pred_label",
    ],
)


# =========================================================
# Frozen component truth
# =========================================================

truth_label = {}
truth_modality = {}

for row in gt.itertuples(index=False):
    qid = clean(getattr(row, "query_id"))
    node = clean(getattr(row, "node_id"))

    truth_label[(qid, node)] = clean(
        getattr(row, GT_LABEL_COL)
    )

    truth_modality[(qid, node)] = clean(
        getattr(row, GT_MODALITY_COL)
    )


# =========================================================
# Frozen query truth
# =========================================================

true_parent_set = {}
true_k = {}
scenario_by_query = {}

for row in base_query.itertuples(index=False):
    qid = clean(row.query_id)

    true_parent_set[qid] = set(
        json.loads(
            clean(row.true_parent_set)
        )
    )

    true_k[qid] = int(
        float(row.k_true)
    )

    scenario_by_query[qid] = clean(
        getattr(row, "scenario")
    )


# =========================================================
# Base costs and eligibility from frozen Phase7H scores
# =========================================================

base_costs = {}
eligible = {}
nodes_by_query = {}


scores["query_id"] = scores["query_id"].astype(str)
scores["node_id"] = scores["node_id"].astype(str)
scores["candidate_parent"] = (
    scores["candidate_parent"].astype(str)
)


for qid, qgroup in scores.groupby("query_id"):

    node_ids = sorted(
        qgroup["node_id"]
        .astype(str)
        .unique()
        .tolist()
    )

    if len(node_ids) != 7:
        raise RuntimeError(
            f"{qid}: expected 7 nodes"
        )

    nodes_by_query[qid] = node_ids
    base_costs[qid] = {}
    eligible[qid] = {}

    for node_id in node_ids:

        ng = qgroup[
            qgroup["node_id"].astype(str)
            == node_id
        ]

        modalities = set(
            ng["modality"].astype(str)
        )

        if len(modalities) != 1:
            raise RuntimeError(
                f"{qid}/{node_id}: mixed modality"
            )

        modality = next(iter(modalities))

        base_costs[qid][node_id] = {}
        eligible[qid][node_id] = {}

        for row in ng.itertuples(index=False):

            parent = clean(
                row.candidate_parent
            )

            cost, is_eligible = (
                normalized_component_cost(
                    modality,
                    float(row.fused_parent_distance),
                    float(row.mean_regret),
                )
            )

            base_costs[qid][node_id][parent] = cost
            eligible[qid][node_id][parent] = is_eligible


# =========================================================
# Candidate pools from Phase12C online retrieval
#
# These pools were obtained by actual online distance
# computation rather than frozen-score reranking.
#
# Reconstruction below remains frozen and unchanged,
# isolating retrieval-backend effects.
# =========================================================

pools_by_backend = {
    backend: {}
    for backend in BACKENDS
}

if "backend" not in pools.columns:
    raise RuntimeError(
        "Phase12C pool file does not contain backend column"
    )

if "candidate_pool" not in pools.columns:
    raise RuntimeError(
        "Phase12C pool file does not contain candidate_pool column"
    )

for backend in BACKENDS:

    bg = pools[
        pools["backend"].astype(str)
        == backend
    ].copy()

    if len(bg) != 360:
        raise RuntimeError(
            f"{backend}: expected 360 Phase12C rows, got {len(bg)}"
        )

    if (
        bg["query_id"].astype(str).nunique()
        != 360
    ):
        raise RuntimeError(
            f"{backend}: duplicate/missing query IDs"
        )

    for row in bg.itertuples(index=False):

        qid = clean(
            row.query_id
        )

        pool = json.loads(
            clean(
                row.candidate_pool
            )
        )

        pools_by_backend[
            backend
        ][
            qid
        ] = pool


# =========================================================
# Frozen content-only hierarchical solver
#
# beta = 0 deliberately.
#
# This isolates candidate-retrieval backend impact from the
# optional weak graph-refinement term.
# =========================================================

def solve_query(qid, pool):

    node_ids = nodes_by_query[qid]

    best_solution = None
    best_key = None

    maximum_subset = min(
        MAX_KNOWN_PARENTS,
        len(pool),
    )

    for subset_size in range(
        maximum_subset + 1
    ):

        for subset in combinations(
            pool,
            subset_size,
        ):

            assignments = []
            total_assignment_cost = 0.0

            for node_id in node_ids:

                possible = [
                    parent
                    for parent in subset
                    if eligible[qid][node_id][parent]
                ]

                if not possible:
                    assignments.append(UNKNOWN)
                    total_assignment_cost += 1.0
                    continue

                best_parent = min(
                    possible,
                    key=lambda parent: (
                        base_costs[qid][node_id][parent],
                        parent,
                    ),
                )

                best_cost = float(
                    base_costs[qid][node_id][best_parent]
                )

                if best_cost > 1.0:
                    assignments.append(UNKNOWN)
                    total_assignment_cost += 1.0

                else:
                    assignments.append(best_parent)
                    total_assignment_cost += best_cost

            objective = (
                total_assignment_cost
                +
                LAMBDA * subset_size
            )

            key = (
                float(objective),
                subset_size,
                tuple(subset),
            )

            if (
                best_key is None
                or key < best_key
            ):
                best_key = key

                best_solution = {
                    "selected_known_subset":
                        list(subset),
                    "assignments":
                        list(assignments),
                    "objective":
                        float(objective),
                }

    if best_solution is None:
        raise RuntimeError(
            f"{qid}: no solution"
        )

    return best_solution


# =========================================================
# Verify standalone EXACT solver against frozen Phase7H
# beta=0 predictions BEFORE evaluating ANN.
# =========================================================

print()
print("Reproducing frozen Phase7H beta=0 baseline...")


base_component_map = {}

for row in base_component.itertuples(index=False):
    key = (
        clean(row.query_id),
        clean(row.node_id),
    )

    base_component_map[key] = clean(
        getattr(row, BASE_PRED_COL)
    )


base_query_parent_map = {}

for row in base_query.itertuples(index=False):
    qid = clean(row.query_id)

    base_query_parent_map[qid] = set(
        json.loads(
            clean(row.predicted_parent_set)
        )
    )


exact_component_mismatches = []
exact_query_mismatches = []


for q_index, qid in enumerate(
    test_query_ids,
    start=1,
):

    solution = solve_query(
        qid,
        pools_by_backend["EXACT"][qid],
    )

    assignments = solution["assignments"]

    for node_id, prediction in zip(
        nodes_by_query[qid],
        assignments,
    ):

        expected = base_component_map[
            (qid, node_id)
        ]

        if prediction != expected:
            exact_component_mismatches.append(
                (
                    qid,
                    node_id,
                    expected,
                    prediction,
                )
            )

    predicted_parent_set = set(assignments)

    if (
        predicted_parent_set
        !=
        base_query_parent_map[qid]
    ):
        exact_query_mismatches.append(
            (
                qid,
                sorted(base_query_parent_map[qid]),
                sorted(predicted_parent_set),
            )
        )

    if q_index % 60 == 0:
        print(
            " exact reproduction",
            q_index,
            "/",
            len(test_query_ids),
        )


if exact_component_mismatches:
    raise RuntimeError(
        "Frozen beta0 component reproduction mismatch: "
        + repr(exact_component_mismatches[:5])
    )

if exact_query_mismatches:
    raise RuntimeError(
        "Frozen beta0 query reproduction mismatch: "
        + repr(exact_query_mismatches[:5])
    )


print("Frozen Phase7H beta=0 reproduction: PASS")


# =========================================================
# Evaluate all retrieval backends
# =========================================================

metrics_rows = []
query_output = []
component_output = []

summary_backends = {}


for backend in BACKENDS:

    print()
    print("------------------------------------------")
    print("Backend:", backend)
    print("------------------------------------------")

    component_truth = []
    component_pred = []

    parent_precision = []
    parent_recall = []
    parent_f1 = []
    parent_exact = []

    k_correct = []
    k_abs_error = []

    for q_index, qid in enumerate(
        test_query_ids,
        start=1,
    ):

        pool = pools_by_backend[
            backend
        ][qid]

        solution = solve_query(
            qid,
            pool,
        )

        assignments = solution[
            "assignments"
        ]

        pred_parent_set = set(
            assignments
        )

        parent_metric = set_metrics(
            true_parent_set[qid],
            pred_parent_set,
        )

        parent_precision.append(
            parent_metric["precision"]
        )

        parent_recall.append(
            parent_metric["recall"]
        )

        parent_f1.append(
            parent_metric["f1"]
        )

        parent_exact.append(
            parent_metric["exact"]
        )

        k_pred = len(
            pred_parent_set
        )

        k_correct.append(
            k_pred == true_k[qid]
        )

        k_abs_error.append(
            abs(
                k_pred
                -
                true_k[qid]
            )
        )

        query_output.append({
            "backend": backend,
            "query_id": qid,
            "scenario": scenario_by_query[qid],
            "k_true": true_k[qid],
            "k_pred": k_pred,
            "true_parent_set":
                json.dumps(
                    sorted(true_parent_set[qid])
                ),
            "predicted_parent_set":
                json.dumps(
                    sorted(pred_parent_set)
                ),
            "selected_known_subset":
                json.dumps(
                    solution[
                        "selected_known_subset"
                    ]
                ),
            "candidate_pool":
                json.dumps(pool),
            "candidate_pool_size":
                len(pool),
            "parent_set_precision":
                parent_metric["precision"],
            "parent_set_recall":
                parent_metric["recall"],
            "parent_set_f1":
                parent_metric["f1"],
            "parent_set_exact":
                parent_metric["exact"],
            "objective":
                solution["objective"],
        })


        for node_id, prediction in zip(
            nodes_by_query[qid],
            assignments,
        ):

            truth = truth_label[
                (qid, node_id)
            ]

            modality = truth_modality[
                (qid, node_id)
            ]

            component_truth.append(truth)
            component_pred.append(prediction)

            component_output.append({
                "backend": backend,
                "query_id": qid,
                "node_id": node_id,
                "scenario": scenario_by_query[qid],
                "modality": modality,
                "ground_truth_label": truth,
                "predicted_label": prediction,
                "correct": bool(
                    truth == prediction
                ),
            })

        if q_index % 60 == 0:
            print(
                " query",
                q_index,
                "/",
                len(test_query_ids),
            )


    component_truth = np.asarray(
        component_truth,
        dtype=object,
    )

    component_pred = np.asarray(
        component_pred,
        dtype=object,
    )

    component_accuracy = float(
        np.mean(
            component_truth
            ==
            component_pred
        )
    )


    true_unknown = (
        component_truth
        ==
        UNKNOWN
    )

    pred_unknown = (
        component_pred
        ==
        UNKNOWN
    )

    tp = int(
        np.sum(
            true_unknown
            &
            pred_unknown
        )
    )

    fp = int(
        np.sum(
            ~true_unknown
            &
            pred_unknown
        )
    )

    fn = int(
        np.sum(
            true_unknown
            &
            ~pred_unknown
        )
    )

    unknown_precision = (
        tp / (tp + fp)
        if tp + fp
        else 0.0
    )

    unknown_recall = (
        tp / (tp + fn)
        if tp + fn
        else 0.0
    )

    unknown_f1 = (
        2
        * unknown_precision
        * unknown_recall
        /
        (
            unknown_precision
            +
            unknown_recall
        )
        if (
            unknown_precision
            +
            unknown_recall
        )
        else 0.0
    )


    result = {
        "backend": backend,
        "queries": 360,
        "components": 2520,
        "component_accuracy":
            component_accuracy,
        "unknown_precision":
            float(unknown_precision),
        "unknown_recall":
            float(unknown_recall),
        "unknown_f1":
            float(unknown_f1),
        "parent_set_precision":
            float(np.mean(parent_precision)),
        "parent_set_recall":
            float(np.mean(parent_recall)),
        "parent_set_f1":
            float(np.mean(parent_f1)),
        "parent_set_exact":
            float(np.mean(parent_exact)),
        "k_accuracy":
            float(np.mean(k_correct)),
        "k_mae":
            float(np.mean(k_abs_error)),
    }

    metrics_rows.append(result)
    summary_backends[backend] = result


metrics_df = pd.DataFrame(
    metrics_rows
)

query_df = pd.DataFrame(
    query_output
)

component_df = pd.DataFrame(
    component_output
)


metrics_df.to_csv(
    OUT_METRICS,
    index=False,
)

query_df.to_csv(
    OUT_QUERY,
    index=False,
)

component_df.to_csv(
    OUT_COMPONENT,
    index=False,
)


# =========================================================
# Deltas from exact content-only baseline
# =========================================================

exact_result = summary_backends[
    "EXACT"
]

deltas = {}

for backend in [
    "FAST",
    "BALANCED",
    "HIGH_RECALL",
]:

    deltas[backend] = {
        metric:
            float(
                summary_backends[backend][metric]
                -
                exact_result[metric]
            )

        for metric in [
            "component_accuracy",
            "unknown_f1",
            "parent_set_f1",
            "parent_set_exact",
            "k_accuracy",
        ]
    }


summary = {
    "phase12d_complete": True,
    "scope":
        "ONLINE_ANN_POOL_DOWNSTREAM_FROZEN_RECONSTRUCTION",
    "frozen_method_modified": False,
    "phase7_parameters_retuned": False,
    "test_used_for_ann_parameter_selection": False,
    "graph_refinement_applied": False,
    "reason_graph_excluded":
        "Phase12B isolates retrieval-backend effects. "
        "The frozen dependency-graph term is an optional weak "
        "refinement whose Phase7 TEST contribution was small "
        "and statistically inconclusive.",
    "frozen_beta0_reproduction": {
        "component_predictions_exact_match": True,
        "query_parent_sets_exact_match": True,
    },
    "backends": summary_backends,
    "delta_from_exact": deltas,
    "interpretation_rule": {
        "operating_points_all_reported": True,
        "no_test_selection": True,
        "balanced_not_promoted_based_on_test":
            "FAST, BALANCED, and HIGH_RECALL remain fixed operating points. Phase12D evaluates online Phase12C candidate pools without TEST-based selection.",
    },
}


OUT_SUMMARY.write_text(
    json.dumps(
        summary,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)


print()
print("==========================================")
print("Phase 12D COMPLETE")
print("==========================================")
print()
print(metrics_df.to_string(index=False))

print()
print("Wrote:", OUT_METRICS)
print("Wrote:", OUT_QUERY)
print("Wrote:", OUT_COMPONENT)
print("Wrote:", OUT_SUMMARY)
