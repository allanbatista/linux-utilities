"""Helper functions for serialization and data manipulation."""

import base64
import dataclasses
import datetime as dt
import decimal
import enum
import json
import pathlib
import uuid
from collections.abc import Mapping, Sequence, Set
from typing import Any, Optional

import yaml

# Optional deps (handled gracefully if missing)
try:
    import numpy as np  # type: ignore
except Exception:
    np = None

try:
    import pandas as pd  # type: ignore
except Exception:
    pd = None

try:
    from pydantic import BaseModel  # type: ignore
except Exception:
    BaseModel = None  # type: ignore


_JSON_PRIMITIVES = (str, int, float, bool, type(None))


def to_serializable(obj, _seen: Optional[set[int]] = None):
    """
    Convert `obj` into a structure that `json.dumps` can handle.
    Returns only JSON-safe types: dict, list, str, int, float, bool, None.
    """
    if isinstance(obj, _JSON_PRIMITIVES):
        return obj

    if _seen is None:
        _seen = set()

    oid = id(obj)
    if oid in _seen:
        # Circular reference detected
        return f"<CircularRef type={type(obj).__name__} id={oid}>"

    # Mark only potentially-recursive containers/objects
    might_recurse = isinstance(obj, (Mapping, Sequence, Set)) or hasattr(obj, "__dict__")
    if might_recurse:
        _seen.add(oid)

    # --- Common rich types ---
    if isinstance(obj, (dt.datetime, dt.date, dt.time)):
        # ISO 8601 for interop
        return obj.isoformat()

    if isinstance(obj, dt.timedelta):
        # Represent duration in seconds (float); easy to consume
        return obj.total_seconds()

    if isinstance(obj, decimal.Decimal):
        # Use string to preserve precision
        return str(obj)

    if isinstance(obj, (uuid.UUID, pathlib.Path)):
        return str(obj)

    if isinstance(obj, enum.Enum):
        # Prefer the enum value (commonly str/int)
        return to_serializable(obj.value, _seen)

    if isinstance(obj, complex):
        # JSON doesn't support complex; store structured
        return {"$complex": [obj.real, obj.imag]}

    if isinstance(obj, (bytes, bytearray, memoryview)):
        # Base64 for binary
        return {"$base64": base64.b64encode(bytes(obj)).decode("ascii")}

    # --- Optional ecosystems ---
    if np is not None:
        if isinstance(obj, (np.generic,)):  # numpy scalar
            return obj.item()
        if isinstance(obj, np.ndarray):
            return obj.tolist()

    if pd is not None:
        if isinstance(obj, (pd.Series, pd.Index)):
            return obj.tolist()
        if isinstance(obj, pd.DataFrame):
            # Compact "records" format is widely compatible
            return {"$dataframe": obj.to_dict(orient="records")}

    if dataclasses.is_dataclass(obj):
        # asdict already recurses into fields
        return to_serializable(dataclasses.asdict(obj), _seen)

    if BaseModel is not None and isinstance(obj, BaseModel):  # type: ignore
        # Pydantic v2
        return to_serializable(obj.model_dump(), _seen)

    # Namedtuple → object by field names
    if isinstance(obj, tuple) and hasattr(obj, "_fields"):
        return {name: to_serializable(getattr(obj, name), _seen) for name in obj._fields}

    # --- Containers ---
    if isinstance(obj, Mapping):
        # Keys must be strings in JSON; we stringify anything else
        return {
            str(to_serializable(k, _seen)): to_serializable(v, _seen)
            for k, v in obj.items()
        }

    if isinstance(obj, Set) and not isinstance(obj, (str, bytes, bytearray, memoryview)):
        return [to_serializable(x, _seen) for x in obj]

    if isinstance(obj, Sequence) and not isinstance(obj, (str, bytes, bytearray, memoryview)):
        return [to_serializable(x, _seen) for x in obj]

    # Objects with a custom JSON hook
    if hasattr(obj, "__json__") and callable(getattr(obj, "__json__")):
        try:
            return to_serializable(obj.__json__(), _seen)
        except Exception:
            pass

    # Generic Python objects: use their public attributes
    if hasattr(obj, "__dict__"):
        return {
            k: to_serializable(v, _seen)
            for k, v in vars(obj).items()
            if not callable(v) and not k.startswith("_")
        }

    # Fallback: string representation
    return str(obj)


class AnyJSONEncoder(json.JSONEncoder):
    """json.dumps(..., cls=AnyJSONEncoder) convenience encoder."""
    def default(self, obj):  # type: ignore[override]
        return to_serializable(obj)


def dumps(obj, *, indent: Optional[int] = None, ensure_ascii: bool = False, sort_keys: bool = False) -> str:
    """
    Serialize any Python object to JSON string.
    """
    return json.dumps(
        to_serializable(obj),
        indent=indent,
        ensure_ascii=ensure_ascii,
        sort_keys=sort_keys,
        separators=None if indent else (",", ":"),
    )


def load_yaml(file_path: str) -> Any:
    """Load YAML file and return parsed content."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def save_yaml(data: Any, file_path: str, *, indent: int = 2) -> None:
    """Save data to YAML file."""
    with open(file_path, 'w', encoding='utf-8') as f:
        yaml.dump(
            to_serializable(data),
            f,
            default_flow_style=False,
            allow_unicode=True,
            indent=indent,
            sort_keys=False
        )


def ensure_dir(path: str) -> None:
    """Ensure directory exists, create if necessary."""
    import os
    os.makedirs(path, exist_ok=True)


def get_timestamp() -> str:
    """Get current timestamp in ISO-8601 format."""
    return dt.datetime.now().isoformat()


def truncate_text(text: str, max_length: int = 80, suffix: str = "...") -> str:
    """Truncate text to max_length with suffix if needed."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix
