import pandas as pd
from pathlib import Path
p = Path(__file__).with_name('full_horizon_results.csv')
df = pd.read_csv(p)
assert len(df) == 900
assert df[['cell', 'seed', 'policy']].drop_duplicates().shape[0] == 900
assert ((df.simulation_end_tick == df.horizon) & (df.pending == 0)).all()
assert (df.served + df.rejected + df.expired == df.demands_total).all()
assert (df.productions_completed + df.fence_drops == df.productions_scheduled).all()
assert df.seed.nunique() == 30 and df.cell.nunique() == 6 and df.policy.nunique() == 5
base = df.query('cell == "heavy_B0"')
checks = {'unfenced':0.700,'production_only':0.200,'admission_only':0.633,'greedy_full':0.0}
for pol, val in checks.items():
    assert round(base.loc[base.policy == pol, 'violation'].mean(), 3) == val
assert df.loc[df.policy == 'greedy_full','violation'].sum() == 0
print('PASS: complete 900-run full-horizon dataset and headline outcomes')
