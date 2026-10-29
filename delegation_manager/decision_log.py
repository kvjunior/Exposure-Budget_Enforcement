"""Decision log record (P2): observation cutoff, selected action, safety witnesses, time, version."""
from __future__ import annotations
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any
import json


@dataclass
class DecisionRecord:
    cutoff: int
    policy: str
    action_kind: str
    checker_ok: bool
    reason: str
    exposure_reason: str = ""
    future_witness: Optional[str] = None
    past_witness: Optional[str] = None
    state_version: int = 0
    cost: float = 0.0
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)
