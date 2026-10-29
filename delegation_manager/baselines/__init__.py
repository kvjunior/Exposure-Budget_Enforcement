"""Baseline policies (P2). policies.py remains as a compatibility facade for the fixed-epoch demo.
Each baseline is deterministic and causal: it sees only observable history up to the cutoff."""
from .fixed_period import fixed_period_policy
from .greedy_history import greedy_history_policy
from .rolling_horizon import rolling_horizon_policy
