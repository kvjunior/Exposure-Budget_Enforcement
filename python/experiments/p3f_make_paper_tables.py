"""Generate LaTeX evidence tables from the reproduced full-horizon JSON, never hand-edit results."""
from pathlib import Path
import json, csv
root = Path(__file__).resolve().parents[2]
data = json.loads((root/'results/manifests/p3e_workload_eval.json').read_text())
policies = ['unfenced','production_only','admission_only','greedy_full','conservative']
tex = root/'paper/results_generated.tex'
heavy = data['cells']['heavy_B0']['policies']
lines=[r'''\begin{table}[t]
\caption{Full-horizon heavy-load results at $B=0$ (30 traces; mean per run). Each run schedules four demands and eight productions. Costs are model units, not measured execution time.}\label{tab:heavy}\centering\footnotesize
\begin{tabular}{lrrrr}\toprule
Policy & Viol. & Served & Rot. & Cost \\
\midrule''']
for p in policies:
 m=heavy[p]; name={'unfenced':'Public log','production_only':'Production only','admission_only':'Admission only','greedy_full':r'\textbf{Combined}','conservative':'Reject all'}[p]
 lines.append(f"{name} & {m['violation']['mean']:.3f} & {m['served']['mean']:.3f} & {m['fence_rotations']['mean']:.3f} & {m['total_cost']['mean']:.2f} \\\\")
lines.append(r'''\bottomrule\end{tabular}\end{table}''')
lines.append(r'''\begin{table}[t]
\caption{Violation proportions by regime and disclosure budget, 30 full-horizon traces per cell. Values are observed proportions, not confidence bounds on general deployment risk.}\label{tab:sweep}\centering\footnotesize
\begin{tabular}{llrrrr}\toprule
Regime & $B$ & Public & Prod. & Admit & Both \\
\midrule''')
for regime in ('light','heavy','intermittent'):
 for b in ('B0','B1'):
  pol=data['cells'][f'{regime}_{b}']['policies']
  lines.append(f'{regime.title()} & {b[-1]} & ' + ' & '.join(f"{pol[p]['violation']['mean']:.3f}" for p in policies[:4]) + r' \\' )
lines.append(r'''\bottomrule\end{tabular}\end{table}''')
tex.write_text('\n'.join(lines)+'\n')
print('generated',tex)
