"""Pure, cryptography-free model of exposure-aware delegation."""
from .types import (StreamId, Epoch, Seq, Record, Scope, RecordRange, Material, Held, Grant)
from .events import Event, OBSERVABLE, GROUND_TRUTH_ONLY, is_observable
from .authorization import AuthorizationState, fold_authorization
from .closure import (CoalitionKnowledge, accumulate, conservative_closure, exposure,
                      Closure, Exposure)
