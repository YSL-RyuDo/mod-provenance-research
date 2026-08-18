from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(r"C:\research\mod-provenance-research")
OUT = ROOT / "paper" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------
# Figure 1. Main method comparison
# ---------------------------------------------------------

methods = [
    "Independent",
    "Hierarchical\nContent",
    "Final\n+Graph"
]

component = [0.775794, 0.807143, 0.805952]
parent_f1 = [0.797412, 0.843545, 0.844233]
exact = [0.286111, 0.413889, 0.419444]
kacc = [0.325000, 0.480556, 0.486111]

x = np.arange(len(methods))
w = 0.19

plt.figure(figsize=(8, 4.8))
plt.bar(x - 1.5*w, component, w, label="Component Acc.")
plt.bar(x - 0.5*w, parent_f1, w, label="Parent F1")
plt.bar(x + 0.5*w, exact, w, label="Exact Parent Set")
plt.bar(x + 1.5*w, kacc, w, label="K Accuracy")

plt.xticks(x, methods)
plt.ylabel("Score")
plt.ylim(0, 1.0)
plt.legend(ncol=2)
plt.tight_layout()

plt.savefig(
    OUT / "method_comparison.pdf",
    bbox_inches="tight"
)
plt.savefig(
    OUT / "method_comparison.png",
    dpi=300,
    bbox_inches="tight"
)
plt.close()


# ---------------------------------------------------------
# Figure 2. Bootstrap confidence intervals
# ---------------------------------------------------------

metrics = [
    "Component\nAccuracy",
    "Parent F1",
    "Exact\nParent Set",
    "K Accuracy",
    "UNKNOWN F1"
]

means = np.array([
    0.805952,
    0.844233,
    0.419444,
    0.486111,
    0.753786
])

lower = np.array([
    0.787698,
    0.829101,
    0.372222,
    0.436111,
    0.732551
])

upper = np.array([
    0.823810,
    0.859114,
    0.466667,
    0.533333,
    0.774445
])

errors = np.vstack([
    means - lower,
    upper - means
])

plt.figure(figsize=(8, 4.8))
plt.errorbar(
    np.arange(len(metrics)),
    means,
    yerr=errors,
    fmt="o",
    capsize=5
)

plt.xticks(np.arange(len(metrics)), metrics)
plt.ylabel("Score")
plt.ylim(0.3, 0.9)
plt.tight_layout()

plt.savefig(
    OUT / "bootstrap_ci.pdf",
    bbox_inches="tight"
)
plt.savefig(
    OUT / "bootstrap_ci.png",
    dpi=300,
    bbox_inches="tight"
)
plt.close()


# ---------------------------------------------------------
# Figure 3. Server latency breakdown
# ---------------------------------------------------------

stages = [
    "Extraction",
    "Search",
    "Reconstruction"
]

latency = [
    14.44,
    10.69,
    1.086
]

plt.figure(figsize=(6.5, 4.5))
plt.bar(stages, latency)
plt.ylabel("Median Latency (ms)")
plt.tight_layout()

plt.savefig(
    OUT / "server_latency.pdf",
    bbox_inches="tight"
)
plt.savefig(
    OUT / "server_latency.png",
    dpi=300,
    bbox_inches="tight"
)
plt.close()


# ---------------------------------------------------------
# Figure 4. Gallery scalability
# ---------------------------------------------------------

gallery_projects = [20, 100]
search_latency = [4.35, 21.46]

plt.figure(figsize=(6.5, 4.5))
plt.plot(
    gallery_projects,
    search_latency,
    marker="o"
)

plt.xlabel("Number of Gallery Projects")
plt.ylabel("Median Search Latency (ms)")
plt.xticks(gallery_projects)
plt.tight_layout()

plt.savefig(
    OUT / "gallery_scalability.pdf",
    bbox_inches="tight"
)
plt.savefig(
    OUT / "gallery_scalability.png",
    dpi=300,
    bbox_inches="tight"
)
plt.close()

print("DONE")
print(OUT)