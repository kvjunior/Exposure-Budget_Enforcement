"""
Typed core objects for the exposure-aware delegation model.

This module is PURE: no network, no timing, no secret bytes of honest actors, no
cryptographic operations. It models *who could know what* and *what that implies*,
not the cryptography itself. The cryptography lives in delegation_crypto.

Terminology (fixed here, used everywhere):
  stream g        : an append-only source of records (e.g. one device's sensor feed)
  record r        : one datum on a stream, identified by (stream, seq)
  scope sigma     : (stream, epoch) -- the unit a single owner key covers. Rolling the
                    epoch starts a NEW scope with a fresh owner key; past records keep
                    their old scope. A scope therefore covers a half-open seq range.
  owner O         : the authorization authority for its streams. Only O (or an authentic
                    preauthorization it signed) creates grants / rolls scopes.
  grant           : an authentic authorization: recipient R may read a record range of a
                    scope, within a validity window, deliverable by named proxies.
  coalition C     : a set of corrupted parties whose retained material we accumulate.

Exposure is history-dependent: revoking a grant removes future *authorization* but never
removes material already retained by a coalition (kfrags, cfrags, data keys, scope keys,
or plaintext). That asymmetry is the object of study.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import FrozenSet, Optional, Tuple

# ---- identifiers (newtypes over str/int for clarity; validated at construction) ----
StreamId = str
Epoch = int
Seq = int
OwnerId = str
RecipientId = str
ProxyId = str
GrantId = str
ScopeKeyId = str          # concrete key version for a scope; rolling epoch => new ScopeKeyId


@dataclass(frozen=True, order=True)
class Record:
    """A single record identity. Immutable."""
    stream: StreamId
    seq: Seq
    def __post_init__(self):
        if self.seq < 0:
            raise ValueError("seq must be >= 0")


@dataclass(frozen=True, order=True)
class Scope:
    """A (stream, epoch) key scope. One owner key per scope."""
    stream: StreamId
    epoch: Epoch
    def __post_init__(self):
        if self.epoch < 0:
            raise ValueError("epoch must be >= 0")


@dataclass(frozen=True)
class RecordRange:
    """Half-open [lo, hi) seq range on a single stream. hi=None means open-ended
    (covers all current and FUTURE records of the stream from lo)."""
    stream: StreamId
    lo: Seq
    hi: Optional[Seq] = None     # None => unbounded (future records included)
    def __post_init__(self):
        if self.lo < 0:
            raise ValueError("lo >= 0 required")
        if self.hi is not None and self.hi < self.lo:
            raise ValueError("hi >= lo required")

    def contains(self, r: Record) -> bool:
        if r.stream != self.stream or r.seq < self.lo:
            return False
        return self.hi is None or r.seq < self.hi

    def bounded(self) -> bool:
        return self.hi is not None


class Material(Enum):
    """Kinds of retained cryptographic material a coalition can hold.

    These mirror the distinctions the brief demands be kept separate (sec 4.2):
      KFRAG       : one raw key fragment of a grant's re-encryption key (proxy-held).
      CFRAG       : one ciphertext-specific capsule fragment (output of transforming a
                    specific capsule with a kfrag). Enough cfrags + recipient key open
                    THAT capsule without the raw kfrags.
      RECIPIENT_SK: a recipient's secret key.
      DATA_KEY    : a disclosed per-record data-encryption key (opens exactly one record).
      SCOPE_KEY   : a disclosed scope owner secret (opens every record under that scope,
                    present AND future, until the scope is rotated away).
      PLAINTEXT   : record content already known. Never un-known by revocation.
    """
    KFRAG = "kfrag"
    CFRAG = "cfrag"
    RECIPIENT_SK = "recipient_sk"
    DATA_KEY = "data_key"
    SCOPE_KEY = "scope_key"
    PLAINTEXT = "plaintext"


@dataclass(frozen=True)
class Held:
    """One piece of retained material, fully qualified so accumulation is exact.

    Fields used depend on `kind`:
      KFRAG/CFRAG : grant, scope, index (which share), capsule (for CFRAG: which record)
      RECIPIENT_SK: recipient
      DATA_KEY    : record
      SCOPE_KEY   : scope
      PLAINTEXT   : record
    Unused fields stay None so two Held objects compare equal iff they are the same thing.
    """
    kind: Material
    grant: Optional[GrantId] = None
    scope: Optional[Scope] = None
    index: Optional[int] = None          # share index for KFRAG/CFRAG
    record: Optional[Record] = None      # for CFRAG (the capsule's record), DATA_KEY, PLAINTEXT
    recipient: Optional[RecipientId] = None


@dataclass(frozen=True)
class Grant:
    """An authentic authorization. Created only by the owner (or authentic preauth)."""
    grant_id: GrantId
    owner: OwnerId
    recipient: RecipientId
    scope: Scope
    rng: RecordRange
    threshold: int                       # t: cfrags/kfrags needed to transform
    shares: int                          # N: proxies the grant is split across
    proxies: Tuple[ProxyId, ...]
    valid_from: int                      # logical time (event index); inclusive
    valid_to: Optional[int]              # inclusive; None => open until revoked
    def __post_init__(self):
        if not (1 <= self.threshold <= self.shares):
            raise ValueError("require 1 <= threshold <= shares")
        if len(self.proxies) != self.shares:
            raise ValueError("proxies must list exactly `shares` ids")
        if self.rng.stream != self.scope.stream:
            raise ValueError("grant range stream must match scope stream")
