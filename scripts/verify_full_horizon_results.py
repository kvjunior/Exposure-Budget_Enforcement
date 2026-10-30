"""Independent consistency check of full-horizon CSV and published aggregate JSON."""
from collections import defaultdict
from pathlib import Path
import csv, json, statistics
root = Path(__file__).resolve().parents[1]
rows = list(csv.DictReader((root/'results/manifests/p3e_workload_eval.csv').open()))
report = json.loads((root/'results/manifests/p3e_workload_eval.json').read_text())
expected = set(report['cells'])
policies = set(report['policies'])
assert len(rows) == 3*2*30*5, f'wrong row count: {len(rows)}'
seen=set(); grouped=defaultdict(list)
for r in rows:
    ident=(r['cell'],r['seed'],r['policy'])
    assert ident not in seen, f'duplicate run: {ident}'
    seen.add(ident)
    assert r['cell'] in expected and r['policy'] in policies
    assert int(r['simulation_end_tick'])==int(r['horizon'])
    assert int(r['pending'])==0
    assert sum(int(r[k]) for k in ('served','rejected','expired'))==int(r['demands_total'])
    assert int(r['productions_completed'])+int(r['fence_drops'])==int(r['productions_scheduled'])
    assert int(r['violation'])==int(float(r['actual_disclosed'])>float(report['cells'][r['cell']]['budget_disclosed']))
    grouped[(r['cell'],r['policy'])].append(r)
for (cell,policy), recs in grouped.items():
    assert len(recs)==30 and set(int(r['seed']) for r in recs)==set(range(30))
    summary=report['cells'][cell]['policies'][policy]
    for field in ('served','violation','expired','actual_disclosed','fence_rotations','fence_drops','total_cost'):
        observed=round(statistics.mean(float(r[field]) for r in recs),3)
        assert abs(observed-summary[field]['mean'])<1e-7, (cell,policy,field,observed,summary[field]['mean'])
    if policy in ('greedy_full','conservative'):
        assert all(int(r['violation'])==0 for r in recs)
print(f'PASS: {len(rows)} complete runs; {len(grouped)} policy/cells; no skipped production or demands; aggregates match CSV')
