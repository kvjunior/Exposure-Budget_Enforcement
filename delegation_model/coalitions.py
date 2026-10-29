"""
Canonical immutable public coalition specifications and budget enumeration (P2).

A coalition specification is PUBLIC adversary reach: the proxies and recipients a declared
coalition is permitted to corrupt. It is NOT realized corruption (that lives only in the
evaluation channel). This module canonicalises specs so equal reach compares equal regardless
of construction order, and enumerates a declared family with unique labels.

CoalitionSpec itself is defined in delegation_model.possible (imported here) to avoid a circular
import; this module adds canonicalisation, validation and family helpers on top.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import FrozenSet, Iterable, List, Tuple
from .possible import CoalitionSpec


def canonical(spec: CoalitionSpec) -> Tuple[str, FrozenSet[str], FrozenSet[str]]:
    """A hashable canonical key for a coalition's reach (label + frozen reach sets)."""
    return (spec.label, frozenset(spec.proxies), frozenset(spec.recipients))


def validate_family(family: Iterable[CoalitionSpec]) -> List[CoalitionSpec]:
    """Return the family as a list, raising on malformed input:
      - not a CoalitionSpec,
      - empty family,
      - duplicate labels (labels must identify a coalition uniquely).
    Two specs with the same label MUST have identical reach, else the label is ambiguous."""
    fam = list(family)
    if not fam:
        raise ValueError("coalition family must be nonempty")
    by_label = {}
    for s in fam:
        if not isinstance(s, CoalitionSpec):
            raise ValueError(f"family element is not a CoalitionSpec: {s!r}")
        key = canonical(s)
        if s.label in by_label and by_label[s.label] != key:
            raise ValueError(f"coalition label {s.label!r} used for two different reaches")
        by_label[s.label] = key
    if len(by_label) != len({s.label for s in fam}):
        raise ValueError("duplicate coalition labels")
    return fam


def unique_reaches(family: Iterable[CoalitionSpec]) -> List[CoalitionSpec]:
    """Deduplicate a family by canonical reach (collapse identical reaches)."""
    seen = {}
    for s in validate_family(family):
        seen.setdefault(canonical(s), s)
    return list(seen.values())
