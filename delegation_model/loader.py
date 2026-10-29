"""
Load JSON-ish event dicts (the portable scenario format, also used by the independent
Python reference) into typed model events. Keeping ONE on-disk format means the Rust/Python
model and the independent reference consume identical input, so a differential test is
meaningful. Unknown event types raise -- malformed scenarios must fail loudly.
"""
from __future__ import annotations
from typing import List
from .types import Record, Scope, RecordRange, Grant
from .events import (StreamAuthorized, ScopeActivated, RecordProduced, GrantIssued,
                     GrantRevoked, KFragInstalled, CFragProduced, OwnerAvailability,
                     CorruptProxy, CorruptRecipient, DiscloseDataKey, DiscloseScopeKey,
                     DisclosePlaintext, Event)


def _grant(d: dict) -> Grant:
    return Grant(
        grant_id=d["grant_id"], owner=d["owner"], recipient=d["recipient"],
        scope=Scope(d["scope"][0], d["scope"][1]),
        rng=RecordRange(d["rng"][0], d["rng"][1], d["rng"][2]),
        threshold=d["threshold"], shares=d["shares"], proxies=tuple(d["proxies"]),
        valid_from=d["valid_from"], valid_to=d["valid_to"])


def load_event(d: dict) -> Event:
    t = d["type"]
    if t == "StreamAuthorized":
        return StreamAuthorized(d["t"], d["owner"], d["stream"], d["producer"])
    if t == "ScopeActivated":
        return ScopeActivated(d["t"], d["owner"], Scope(d["scope"][0], d["scope"][1]),
                              d["scope_key_id"], d["start_seq"])
    if t == "RecordProduced":
        return RecordProduced(d["t"], Record(d["record"][0], d["record"][1]),
                              d.get("weight", 1.0))
    if t == "GrantIssued":
        return GrantIssued(d["t"], _grant(d["grant"]))
    if t == "GrantRevoked":
        return GrantRevoked(d["t"], d["grant_id"])
    if t == "KFragInstalled":
        return KFragInstalled(d["t"], d["grant_id"], d["proxy"], d["index"])
    if t == "CFragProduced":
        return CFragProduced(d["t"], d["grant_id"], Record(d["record"][0], d["record"][1]),
                             d["index"])
    if t == "OwnerAvailability":
        return OwnerAvailability(d["t"], d["owner"], d["online"])
    if t == "CorruptProxy":
        return CorruptProxy(d["t"], d["proxy"], d["coalition"])
    if t == "CorruptRecipient":
        return CorruptRecipient(d["t"], d["recipient"], d["coalition"])
    if t == "DiscloseDataKey":
        return DiscloseDataKey(d["t"], Record(d["record"][0], d["record"][1]), d["coalition"])
    if t == "DiscloseScopeKey":
        return DiscloseScopeKey(d["t"], Scope(d["scope"][0], d["scope"][1]), d["coalition"])
    if t == "DisclosePlaintext":
        return DisclosePlaintext(d["t"], Record(d["record"][0], d["record"][1]), d["coalition"])
    raise ValueError(f"unknown event type: {t!r}")


def load_events(ds: List[dict]) -> List[Event]:
    return [load_event(d) for d in ds]
