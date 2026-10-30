"""P3F figure generation from p3e_workload_eval.json. Model-simulation units. Exit 0 on success."""
import json, os, sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
HERE = os.path.dirname(__file__); ROOT = os.path.join(HERE, "..", "..")
d = json.load(open(os.path.join(ROOT, "results/manifests/p3e_workload_eval.json")))
OUT = os.path.join(ROOT, "results/figures"); os.makedirs(OUT, exist_ok=True)
policies = ["unfenced", "production_only", "admission_only", "greedy_full", "conservative"]
labels = ["unfenced", "prod-only", "adm-only", "greedy+full", "conservative"]
colors = ["#c0392b", "#e67e22", "#8e44ad", "#27ae60", "#7f8c8d"]
cells = [c for c in d["cells"] if c.endswith("B0")]   # tight-budget cells for the headline figures

def bar(metric, ylabel, fname, title):
    fig, ax = plt.subplots(figsize=(8.5, 4.2)); n = len(cells); w = 0.16
    for i, p in enumerate(policies):
        xs = [j + i * w for j in range(n)]
        ys = [d["cells"][c]["policies"][p][metric]["mean"] for c in cells]
        es = [d["cells"][c]["policies"][p][metric]["stdev"] for c in cells]
        ax.bar(xs, ys, w, yerr=es, capsize=3, label=labels[i], color=colors[i])
    ax.set_xticks([j + 2 * w for j in range(n)]); ax.set_xticklabels([c[:-3] for c in cells])
    ax.set_ylabel(ylabel); ax.set_title(title + "  (B=0; 30 seeds; mean±stdev; model units)")
    ax.legend(fontsize=8, ncol=5, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    fig.tight_layout(); fig.savefig(os.path.join(OUT, fname), dpi=150, bbox_inches="tight"); plt.close(fig)

bar("violation", "budget-violation rate", "fig_violations.png", "Budget violations: single mechanisms are insufficient")
bar("actual_disclosed", "mean actual disclosed weight", "fig_disclosure.png", "Actual cumulative disclosure")
bar("served", "mean demands served", "fig_served.png", "Service completion (cost of safety)")
bar("total_cost", "mean total management cost", "fig_cost.png", "Total management cost")
print("wrote figures:", sorted(os.listdir(OUT))); sys.exit(0)
