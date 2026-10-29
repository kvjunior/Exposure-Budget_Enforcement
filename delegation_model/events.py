"""
Typed events. The history is an ordered list of events; all state (authorization,
key scopes, retained knowledge) is a deterministic fold over the prefix of events up to
the controller's observation cutoff.

Ordering model (brief sec 5): events carry a strictly increasing integer `t` (logical
time = position). Simultaneous events are disallowed at the model layer (the service
layer linearizes). Duplicate delivery is handled by idempotent application keyed on a
content hash; replay after restart re-folds from the persisted log.

Compromise events (CorruptProxy, Disclose*) are GROUND TRUTH used only by the exposure
model and evaluation. They are NEVER part of the controller's observations. The manager
sees admission requests, grants, revocations, rollovers, owner-availability, and its own
past decisions -- not the realized corruptions.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple, Union
from .types import (Grant, GrantId, ProxyId, RecipientId, Scope, Record, RecordRange,
                    ScopeKeyId, StreamId, Epoch, Seq)


@dataclass(frozen=True)
class StreamAuthorized:
    """Owner authorizes a producer device to append to a stream (device-to-stream auth)."""
    t: int
    owner: str
    stream: StreamId
    producer: str


@dataclass(frozen=True)
class ScopeActivated:
    """Owner activates a fresh key scope (new epoch) for a stream. Requires owner authority
    or an authentic preauthorization token (checked at the service/authorization layer)."""
    t: int
    owner: str
    scope: Scope
    scope_key_id: ScopeKeyId
    start_seq: Seq               # first record seq this scope covers


@dataclass(frozen=True)
class RecordProduced:
    """A producer emits a record on a stream; it falls in the currently active scope."""
    t: int
    record: Record
    weight: float = 1.0          # w(r) for exposure accounting


@dataclass(frozen=True)
class GrantIssued:
    """Owner issues an authentic grant (recipient may read a range of a scope)."""
    t: int
    grant: Grant


@dataclass(frozen=True)
class GrantRevoked:
    """Owner revokes a grant. Removes future authorization; does NOT erase retained material."""
    t: int
    grant_id: GrantId


@dataclass(frozen=True)
class KFragInstalled:
    """A proxy receives one raw key fragment of a grant (threshold PRE split)."""
    t: int
    grant_id: GrantId
    proxy: ProxyId
    index: int


@dataclass(frozen=True)
class CFragProduced:
    """A proxy transforms a specific capsule (record) with its kfrag, yielding a cfrag.
    Ground-truth record that this ciphertext-specific fragment now exists and could be
    retained by whoever received it."""
    t: int
    grant_id: GrantId
    record: Record
    index: int


@dataclass(frozen=True)
class OwnerAvailability:
    """Owner connectivity changes (online/offline). Observable by the controller."""
    t: int
    owner: str
    online: bool


# ---- compromise / disclosure events: GROUND TRUTH ONLY, never observed by controller ----
@dataclass(frozen=True)
class CorruptProxy:
    t: int
    proxy: ProxyId
    coalition: str               # label of the coalition that now holds this proxy's material


@dataclass(frozen=True)
class CorruptRecipient:
    t: int
    recipient: RecipientId
    coalition: str


@dataclass(frozen=True)
class DiscloseDataKey:
    t: int
    record: Record
    coalition: str


@dataclass(frozen=True)
class DiscloseScopeKey:
    t: int
    scope: Scope
    coalition: str


@dataclass(frozen=True)
class DisclosePlaintext:
    t: int
    record: Record
    coalition: str


Event = Union[
    StreamAuthorized, ScopeActivated, RecordProduced, GrantIssued, GrantRevoked,
    KFragInstalled, CFragProduced, OwnerAvailability,
    CorruptProxy, CorruptRecipient, DiscloseDataKey, DiscloseScopeKey, DisclosePlaintext,
]

# Events the online controller is allowed to observe. Compromise/disclosure excluded.
OBSERVABLE = (
    StreamAuthorized, ScopeActivated, RecordProduced, GrantIssued, GrantRevoked,
    KFragInstalled, CFragProduced, OwnerAvailability,
)
GROUND_TRUTH_ONLY = (
    CorruptProxy, CorruptRecipient, DiscloseDataKey, DiscloseScopeKey, DisclosePlaintext,
)


def event_time(e: Event) -> int:
    return e.t


def is_observable(e: Event) -> bool:
    return isinstance(e, OBSERVABLE)
