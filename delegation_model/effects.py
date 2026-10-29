"""
Typed capability effects (P2).

A capability EFFECT is the retained-material consequence of executing an action, expressed in
the SAME vocabulary the closure reasons over (delegation_model.types.Material). Effects are
BACKEND-SPECIFIC: a threshold-PRE grant delivers raw kfrags; an owner-HPKE rewrap delivers a
per-record key envelope to one recipient; a scope-key handover delivers a whole scope key. The
point of this module (research guide: "every mechanism needs a matching effect contract; do not
attach HPKE timing to a PRE capability model") is to make the mechanism explicit and to let the
checker verify that the effects it checked are exactly the effects the executor delivered.

An Effect is a declaration of WHAT retained material reaches WHICH party under WHICH backend. It
does not perform cryptography. The executor (delegation_manager.executor) turns committed effects
into Held material for the evaluation channel; the crypto layer performs the real operation.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple
from .types import Material, Scope, Record, GrantId, ProxyId, RecipientId


class Backend(Enum):
    """The cryptographic mechanism a delegation uses. Each exposes DIFFERENT retained material."""
    THRESHOLD_PRE = "threshold_pre"     # proxies hold raw kfrags; t + recipient key -> scope key
    OWNER_HPKE_REWRAP = "owner_hpke_rewrap"  # owner reseals one record's DEK to a recipient
    SCOPE_KEY_HANDOVER = "scope_key_handover"  # recipient is handed a whole scope key directly


@dataclass(frozen=True)
class Effect:
    """One retained-material delivery. `to_proxy`/`to_recipient` name the holder; `material`
    says what kind; the remaining fields qualify it exactly so the executor and closure agree."""
    backend: Backend
    material: Material
    grant: Optional[GrantId] = None
    scope: Optional[Scope] = None
    index: Optional[int] = None          # share index for KFRAG/CFRAG
    record: Optional[Record] = None      # for per-record DEK / data key
    to_proxy: Optional[ProxyId] = None
    to_recipient: Optional[RecipientId] = None

    def holder(self) -> str:
        return self.to_proxy if self.to_proxy is not None else (self.to_recipient or "?")


def threshold_pre_grant_effects(grant_id: GrantId, scope: Scope,
                                proxies: Tuple[ProxyId, ...], indices: Tuple[int, ...]
                                ) -> Tuple[Effect, ...]:
    """Effects of installing a threshold-PRE grant's kfrags at the given share indices.
    Each index i delivers a raw KFRAG to proxies[i]. Indices MUST be validated (0<=i<shares,
    distinct) by the caller/checker before this is used; we assert to catch contract breaches."""
    out = []
    for i in indices:
        assert 0 <= i < len(proxies), f"share index {i} out of range for {len(proxies)} proxies"
        out.append(Effect(Backend.THRESHOLD_PRE, Material.KFRAG, grant=grant_id, scope=scope,
                          index=i, to_proxy=proxies[i]))
    return tuple(out)


def owner_hpke_rewrap_effect(record: Record, to_recipient: RecipientId) -> Effect:
    """Effect of an owner rewrapping ONE record's data key to a recipient: a DATA_KEY for that
    one record reaches that recipient. No scope key, no fragments. This is the HPKE baseline's
    delivery, and it is deliberately a DIFFERENT effect type from a PRE grant."""
    return Effect(Backend.OWNER_HPKE_REWRAP, Material.DATA_KEY, record=record,
                  to_recipient=to_recipient)


def scope_key_handover_effect(scope: Scope, to_recipient: RecipientId) -> Effect:
    """Effect of handing a whole scope key to a recipient: a SCOPE_KEY reaches that recipient,
    opening every record of the scope present and future until rotation. The broadest effect."""
    return Effect(Backend.SCOPE_KEY_HANDOVER, Material.SCOPE_KEY, scope=scope,
                  to_recipient=to_recipient)
