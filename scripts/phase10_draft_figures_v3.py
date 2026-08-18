from pathlib import Path
import json
import math
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

ROOT = Path(r"C:\research\mod-provenance-research")
OUT = ROOT / "paper" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(OUT / f"{name}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] {name}.pdf / {name}.png")

def box(ax, x, y, w, h, text, fs=9):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02")
    ax.add_patch(p)
    ax.text(x + w/2, y + h/2, text, ha="center", va="center", fontsize=fs)
    return p

def arrow(ax, x1, y1, x2, y2):
    a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="->", mutation_scale=12)
    ax.add_patch(a)

def find_json(filename):
    matches = list(ROOT.rglob(filename))
    return matches[0] if matches else None

# ============================================================
# Fig. 1 Server-side provenance architecture
# ============================================================
fig, ax = plt.subplots(figsize=(11, 5.6))
ax.set_xlim(0, 12)
ax.set_ylim(0, 7)
ax.axis("off")

box(ax, 0.3, 5.3, 2.1, 0.8, "Registered MODs")
box(ax, 0.3, 3.8, 2.1, 0.8, "Component Registry")
box(ax, 0.3, 2.3, 2.1, 0.8, "Evidence Gallery /\nSearch Index")
arrow(ax, 1.35, 5.3, 1.35, 4.6)
arrow(ax, 1.35, 3.8, 1.35, 3.1)

box(ax, 3.2, 5.3, 2.0, 0.8, "MOD Upload")
box(ax, 3.2, 3.8, 2.0, 0.8, "FastAPI\nPackage Receiver")
box(ax, 3.2, 2.3, 2.0, 0.8, "Component\nExtractor")
arrow(ax, 4.2, 5.3, 4.2, 4.6)
arrow(ax, 4.2, 3.8, 4.2, 3.1)

box(ax, 6.0, 4.8, 2.1, 0.9, "Identity-Neutral\nEvidence Extraction")
box(ax, 6.0, 3.1, 2.1, 0.9, "Gallery Search")
box(ax, 6.0, 1.4, 2.1, 0.9, "Parent Candidate\nRetrieval")
arrow(ax, 5.2, 2.7, 6.0, 5.0)
arrow(ax, 7.05, 4.8, 7.05, 4.0)
arrow(ax, 7.05, 3.1, 7.05, 2.3)
arrow(ax, 2.4, 2.7, 6.0, 3.5)

box(ax, 8.9, 4.8, 2.5, 0.9, "Parent-Set / K\nReconstruction")
box(ax, 8.9, 3.1, 2.5, 0.9, "Component-Level\nAttribution")
box(ax, 8.9, 1.4, 2.5, 0.9, "Optional Dependency\nRefinement")
arrow(ax, 8.1, 1.85, 8.9, 5.0)
arrow(ax, 10.15, 4.8, 10.15, 4.0)
arrow(ax, 10.15, 3.1, 10.15, 2.3)

box(ax, 8.9, 0.15, 2.5, 0.7, "Provenance Result:\nParents + UNKNOWN", fs=8)
arrow(ax, 10.15, 1.4, 10.15, 0.85)

ax.text(1.35, 6.5, "Offline Registration", ha="center", fontsize=11)
ax.text(7.4, 6.5, "Online Query Processing", ha="center", fontsize=11)
save(fig, "fig01_server_architecture")

# ============================================================
# Fig. 2 Automated benchmark construction pipeline
# ============================================================
fig, ax = plt.subplots(figsize=(11, 4.6))
ax.set_xlim(0, 13)
ax.set_ylim(0, 5)
ax.axis("off")

labels = [
    "Real Public\nMOD Projects",
    "Current / Historical\nReleases",
    "Automatic Component\nExtraction",
    "Exact Source\nManifest",
    "Multi-Parent Query\nComposer",
    "Frozen Query +\nGround Truth",
]
xs = [0.2, 2.35, 4.5, 6.65, 8.8, 10.95]
for x, lab in zip(xs, labels):
    box(ax, x, 2.0, 1.75, 1.0, lab, fs=8.5)
for i in range(len(xs)-1):
    arrow(ax, xs[i]+1.75, 2.5, xs[i+1], 2.5)

ax.text(5.7, 4.1, "Automated Benchmark Construction", ha="center", fontsize=12)
ax.text(9.65, 0.85, "Scenarios: K1, K2, K3,\n1K1U, 2K1U, UNKNOWN", ha="center", fontsize=9)
arrow(ax, 9.65, 2.0, 9.65, 1.25)
save(fig, "fig02_benchmark_pipeline")

# ============================================================
# Fig. 3 Hierarchical reconstruction pipeline
# ============================================================
fig, ax = plt.subplots(figsize=(10.5, 5.0))
ax.set_xlim(0, 12)
ax.set_ylim(0, 6)
ax.axis("off")

box(ax, 0.4, 2.5, 1.8, 1.0, "Query\nComponents")
box(ax, 2.8, 4.3, 1.9, 0.9, "CODE\nEvidence")
box(ax, 2.8, 2.55, 1.9, 0.9, "STRUCTURED\nEvidence")
box(ax, 2.8, 0.8, 1.9, 0.9, "IMAGE\nEvidence")
arrow(ax, 2.2, 3.0, 2.8, 4.75)
arrow(ax, 2.2, 3.0, 2.8, 3.0)
arrow(ax, 2.2, 3.0, 2.8, 1.25)

box(ax, 5.4, 3.7, 2.1, 1.0, "Global Parent\nCandidate Retrieval")
box(ax, 5.4, 1.6, 2.1, 1.0, "UNKNOWN\nCalibration")
arrow(ax, 4.7, 4.75, 5.4, 4.2)
arrow(ax, 4.7, 3.0, 5.4, 4.2)
arrow(ax, 4.7, 1.25, 5.4, 4.2)
arrow(ax, 6.45, 1.6, 6.45, 3.7)

box(ax, 8.1, 3.7, 2.2, 1.0, "Parent-Set + K\nReconstruction")
box(ax, 8.1, 1.6, 2.2, 1.0, "Component-Level\nAssignment")
arrow(ax, 7.5, 4.2, 8.1, 4.2)
arrow(ax, 9.2, 3.7, 9.2, 2.6)

box(ax, 10.65, 1.6, 1.1, 1.0, "Graph\nRefine", fs=8)
arrow(ax, 10.3, 2.1, 10.65, 2.1)

ax.text(9.2, 0.5, "Final output: parent set, K, component labels, UNKNOWN",
        ha="center", fontsize=9)
arrow(ax, 9.2, 1.6, 9.2, 0.85)
save(fig, "fig03_reconstruction_pipeline")

# ============================================================
# Fig. 4 TEST scenario design (read frozen phase6k summary)
# ============================================================
summary_path = find_json("phase6k_query_summary.json")
scenario_names = []
scenario_counts = []

if summary_path:
    with summary_path.open("r", encoding="utf-8") as f:
        qsum = json.load(f)
    for key, value in qsum.get("scenario_summary", {}).items():
        if key.startswith("TEST_"):
            scenario_names.append(key.replace("TEST_", ""))
            scenario_counts.append(value["queries"])
    print(f"[SOURCE] {summary_path}")
else:
    raise FileNotFoundError(
        "phase6k_query_summary.json을 프로젝트에서 찾지 못했습니다. "
        "파일이 프로젝트 내부에 있는지 확인하세요."
    )

fig, ax = plt.subplots(figsize=(8.5, 4.8))
x = np.arange(len(scenario_names))
ax.bar(x, scenario_counts)
ax.set_ylabel("Queries")
ax.set_xticks(x)
ax.set_xticklabels(scenario_names, rotation=25, ha="right")
ax.set_ylim(0, max(scenario_counts) * 1.2)
ax.set_title("Frozen TEST Scenario Design")
save(fig, "fig04_test_scenarios")

# ============================================================
# Fig. 5 Main ablation — frozen TEST results
# Source: Phase 7H / Phase 8 verified results
# ============================================================
methods = ["Independent", "Hierarchical\nContent", "Final\n+Graph"]
component = [0.775794, 0.807143, 0.805952]
parent_f1 = [0.797412, 0.843545, 0.844233]
exact = [0.286111, 0.413889, 0.419444]
kacc = [0.325000, 0.480556, 0.486111]

fig, ax = plt.subplots(figsize=(8.7, 5.0))
x = np.arange(len(methods))
w = 0.19
ax.bar(x - 1.5*w, component, w, label="Component Acc.")
ax.bar(x - 0.5*w, parent_f1, w, label="Parent F1")
ax.bar(x + 0.5*w, exact, w, label="Exact Parent Set")
ax.bar(x + 1.5*w, kacc, w, label="K Accuracy")
ax.set_xticks(x)
ax.set_xticklabels(methods)
ax.set_ylabel("Score")
ax.set_ylim(0, 1.0)
ax.legend(ncol=2)
ax.set_title("Ablation on Frozen TEST")
save(fig, "fig05_method_ablation")

# ============================================================
# Fig. 6 Bootstrap CI — 10,000 resamples
# ============================================================
metrics = ["Component\nAccuracy", "Parent F1", "Exact\nParent Set", "K Accuracy", "UNKNOWN F1"]
means = np.array([0.805952, 0.844233, 0.419444, 0.486111, 0.753786])
lower = np.array([0.787698, 0.829101, 0.372222, 0.436111, 0.732551])
upper = np.array([0.823810, 0.859114, 0.466667, 0.533333, 0.774445])
errors = np.vstack([means-lower, upper-means])

fig, ax = plt.subplots(figsize=(8.5, 4.8))
ax.errorbar(np.arange(len(metrics)), means, yerr=errors, fmt="o", capsize=5)
ax.set_xticks(np.arange(len(metrics)))
ax.set_xticklabels(metrics)
ax.set_ylabel("Score")
ax.set_ylim(0.3, 0.9)
ax.set_title("95% Bootstrap Confidence Intervals (10,000 resamples)")
save(fig, "fig06_bootstrap_ci")

# ============================================================
# Fig. 7 Materialized package latency breakdown
# ============================================================
stages = ["Extraction", "Search", "Reconstruction"]
latency = [14.44, 10.69, 1.086]

fig, ax = plt.subplots(figsize=(7.0, 4.5))
ax.bar(stages, latency)
ax.set_ylabel("Median Latency (ms)")
ax.set_title("Materialized Package E2E Latency Breakdown")
save(fig, "fig07_server_latency")

# ============================================================
# Fig. 8 Gallery scalability
# ============================================================
gallery_projects = [20, 100]
search_latency = [4.35, 21.46]

fig, ax = plt.subplots(figsize=(7.0, 4.5))
ax.plot(gallery_projects, search_latency, marker="o")
ax.set_xlabel("Gallery Projects")
ax.set_ylabel("Median Search Latency (ms)")
ax.set_xticks(gallery_projects)
ax.set_title("Gallery Search Scalability")
save(fig, "fig08_gallery_scalability")

print("\nDONE")
print("Figures:", OUT)
