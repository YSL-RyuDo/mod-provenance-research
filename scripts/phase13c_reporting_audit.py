import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

A = json.loads(
    (ROOT / "results/phase13a_failure_taxonomy_summary.json")
    .read_text(encoding="utf-8")
)

B = json.loads(
    (ROOT / "results/phase13b_failure_localization_summary.json")
    .read_text(encoding="utf-8")
)

assert A["phase13a_complete"] is True
assert B["phase13b_complete"] is True

assert A["parameters_retuned"] is False
assert A["predictions_recomputed"] is False
assert A["primary_test_modified"] is False

assert B["parameters_retuned"] is False
assert B["predictions_recomputed"] is False
assert B["primary_test_modified"] is False

assert A["test"]["queries"] == 360
assert A["test"]["components"] == 2520
assert A["test"]["component_errors"] == 489

assert sum(
    A["component_error_taxonomy"].values()
) == 489

assert sum(
    B["failure_localization"].values()
) == 489

assert B["failure_localization"]["COMPONENT_ASSIGNMENT_MISS"] == 325
assert B["failure_localization"]["UNKNOWN_REJECTION_FAILURE"] == 81
assert B["failure_localization"]["PARENT_SELECTION_MISS"] == 47
assert B["failure_localization"]["RETRIEVAL_MISS"] == 36

out = {
    "phase13c_complete": True,
    "scope": "REPORTING_ONLY_FAILURE_ANALYSIS_FREEZE",
    "parameters_retuned": False,
    "predictions_recomputed": False,
    "primary_test_modified": False,
    "component_errors": 489,
    "main_failure_localization": {
        "COMPONENT_ASSIGNMENT_MISS": 325,
        "UNKNOWN_REJECTION_FAILURE": 81,
        "PARENT_SELECTION_MISS": 47,
        "RETRIEVAL_MISS": 36
    },
    "paper_safe_interpretation": [
        "Most component-level errors arise after retrieval, during component assignment.",
        "Retrieval misses account for only a small fraction of total component errors.",
        "Known K=1 failures are entirely localized to component assignment in this taxonomy.",
        "Higher-parent-count scenarios show additional retrieval and parent-selection failures.",
        "UNKNOWN-only errors are false attribution of UNKNOWN components to registered parents.",
        "The analysis is diagnostic only and does not modify or retune the frozen method."
    ]
}

p = ROOT / "results/phase13c_reporting_audit_summary.json"
p.write_text(
    json.dumps(out, indent=2, ensure_ascii=False),
    encoding="utf-8"
)

print("Phase13C reporting audit: PASS")
print("Phase13 COMPLETE")
