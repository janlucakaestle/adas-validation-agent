"""Immutable configuration values and canonical hashing.

Parsed configuration is frozen: mappings become read-only `MappingProxyType` views over
private dicts and lists become tuples, recursively. A caller can therefore not change a
cached configuration in memory and run a simulation that differs from the configuration
whose hash is recorded as provenance. To build a variant (sensitivity analysis), `thaw`
returns a mutable deep copy, and the variant is frozen again and hashed as its own release.

`canonical_json` is the single serialisation used for every content hash: sorted keys,
no whitespace, floats in their shortest round-trip form, and non-finite floats spelled out.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any


def freeze(obj: Any) -> Any:
    """Recursively immutable copy: dict -> MappingProxyType, list/tuple -> tuple."""
    if isinstance(obj, Mapping):
        return MappingProxyType({str(k): freeze(v) for k, v in obj.items()})
    if isinstance(obj, (list, tuple)):
        return tuple(freeze(v) for v in obj)
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    raise TypeError(f"cannot freeze a value of type {type(obj).__name__}")


def thaw(obj: Any) -> Any:
    """Recursively mutable deep copy of a frozen (or plain) value."""
    if isinstance(obj, Mapping):
        return {k: thaw(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [thaw(v) for v in obj]
    return obj


def _plain(obj: Any) -> Any:
    if isinstance(obj, Mapping):
        return {str(k): _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    if isinstance(obj, float) and not math.isfinite(obj):
        return {"__float__": repr(obj)}
    if hasattr(obj, "item") and not isinstance(obj, (str, bytes)):  # numpy scalar
        return _plain(obj.item())
    return obj


def canonical_json(obj: Any) -> str:
    """Deterministic JSON text of a (frozen or plain) value; the basis of every hash."""
    return json.dumps(_plain(obj), sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def content_hash(obj: Any) -> str:
    return sha256_text(canonical_json(obj))


def deep_merge(base: Any, patch: Any) -> Any:
    """`base` with `patch` applied recursively (mappings merged key by key, anything else
    replaced). Every key in `patch` must already exist in `base`, so a misspelt override
    fails instead of silently adding an unused value."""
    if not isinstance(patch, Mapping):
        return thaw(patch)
    if not isinstance(base, Mapping):
        raise KeyError("override patches a mapping onto a non-mapping value")
    out = thaw(base)
    for k, v in patch.items():
        if k not in out:
            raise KeyError(f"override key {k!r} does not exist in the configuration")
        out[k] = deep_merge(out[k], v) if isinstance(v, Mapping) else thaw(v)
    return out
