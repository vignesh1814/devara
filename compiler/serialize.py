"""Generic dataclass <-> JSON serialization and tree printing.

Used for tokens, AST, typed tree and IR so that every stage output can be
inspected, stored and fed to the next stage.

Encoding:
* dataclass instance -> ``{"_node": "<ClassName>", <field>: ...}``
* ``StrEnum``/``Enum`` member -> its value string (decoded using the field's
  type annotation)
* list/tuple -> JSON array (decoded to ``list``; tuples are decoded to tuples
  when the annotation says ``tuple``)
* ``dict`` with string keys -> JSON object
* int/float/bool/str/None -> themselves. Non-finite floats are encoded as
  ``{"_float": "nan"|"inf"|"-inf"}``.
"""

from __future__ import annotations

import dataclasses
import enum
import json
import math
import types
import typing
from typing import Any

_CLASSES: dict[str, type] = {}
_HINTS: dict[type, dict[str, Any]] = {}


def register(*modules: types.ModuleType) -> None:
    """Register every dataclass defined in the given modules for decoding."""
    for mod in modules:
        for name, obj in vars(mod).items():
            if (
                isinstance(obj, type)
                and dataclasses.is_dataclass(obj)
                and obj.__module__ == mod.__name__
            ):
                _CLASSES[obj.__name__] = obj


def to_data(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        out: dict[str, Any] = {"_node": type(obj).__name__}
        for f in dataclasses.fields(obj):
            out[f.name] = to_data(getattr(obj, f.name))
        return out
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, (list, tuple)):
        return [to_data(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): to_data(v) for k, v in obj.items()}
    if isinstance(obj, float) and not math.isfinite(obj):
        return {"_float": "nan" if math.isnan(obj) else ("inf" if obj > 0 else "-inf")}
    if isinstance(obj, bytes):
        return {"_bytes": obj.hex()}
    return obj


def _hints(cls: type) -> dict[str, Any]:
    h = _HINTS.get(cls)
    if h is None:
        h = typing.get_type_hints(cls)
        _HINTS[cls] = h
    return h


def _decode(value: Any, hint: Any) -> Any:
    if isinstance(value, dict):
        if "_node" in value:
            cls = _CLASSES[value["_node"]]
            hints = _hints(cls)
            kwargs = {}
            for f in dataclasses.fields(cls):
                if f.name in value:
                    kwargs[f.name] = _decode(value[f.name], hints.get(f.name))
            return cls(**kwargs)
        if "_float" in value:
            return float(value["_float"])
        if "_bytes" in value:
            return bytes.fromhex(value["_bytes"])
    origin = typing.get_origin(hint)
    args = typing.get_args(hint)
    if origin in (typing.Union, types.UnionType):
        if value is None:
            return None
        for a in args:
            if a is type(None):
                continue
            if isinstance(a, type) and issubclass(a, enum.Enum) and isinstance(value, str):
                return a(value)
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return _decode(value, non_none[0])
        return _decode(value, None)
    if isinstance(hint, type) and issubclass(hint, enum.Enum) and isinstance(value, str):
        return hint(value)
    if isinstance(value, list):
        if origin is tuple:
            if len(args) == 2 and args[1] is Ellipsis:
                return tuple(_decode(v, args[0]) for v in value)
            return tuple(_decode(v, a) for v, a in zip(value, args))
        elem = args[0] if origin is list and args else None
        return [_decode(v, elem) for v in value]
    if isinstance(value, dict):
        vt = args[1] if origin is dict and len(args) == 2 else None
        kt = args[0] if origin is dict and len(args) == 2 else None
        return {(int(k) if kt is int else k): _decode(v, vt) for k, v in value.items()}
    return value


def from_data(data: Any) -> Any:
    return _decode(data, None)


def dumps(obj: Any, indent: int | None = 2) -> str:
    return json.dumps(to_data(obj), indent=indent)


def loads(text: str) -> Any:
    return from_data(json.loads(text))


# ── Human-readable indented tree ──

_SKIP_FIELDS = {"span"}


def _scalar(v: Any) -> str:
    if isinstance(v, enum.Enum):
        return str(v.value)
    if isinstance(v, str):
        return repr(v)
    return repr(v)


def format_tree(obj: Any, *, spans: bool = True, indent: str = "  ") -> str:
    """Render a dataclass tree as an indented outline (stable, diff-friendly)."""
    lines: list[str] = []

    def head(node: Any) -> str:
        name = type(node).__name__
        sp = getattr(node, "span", None)
        if spans and sp is not None:
            return f"{name} [{sp.start_line}:{sp.start_column}-{sp.end_line}:{sp.end_column}]"
        return name

    def emit(label: str | None, v: Any, depth: int) -> None:
        pad = indent * depth
        prefix = f"{label}: " if label else ""
        if hasattr(v, "compact") and dataclasses.is_dataclass(v):
            lines.append(f"{pad}{prefix}{v.compact()}")
        elif dataclasses.is_dataclass(v) and not isinstance(v, type):
            lines.append(f"{pad}{prefix}{head(v)}")
            for f in dataclasses.fields(v):
                if f.name in _SKIP_FIELDS:
                    continue
                emit(f.name, getattr(v, f.name), depth + 1)
        elif isinstance(v, (list, tuple)):
            if not v:
                lines.append(f"{pad}{prefix}[]")
            elif all(not (dataclasses.is_dataclass(x) or isinstance(x, (list, tuple, dict))) for x in v):
                lines.append(f"{pad}{prefix}[{', '.join(_scalar(x) for x in v)}]")
            else:
                lines.append(f"{pad}{prefix}[")
                for x in v:
                    emit(None, x, depth + 1)
                lines.append(f"{pad}]")
        elif isinstance(v, dict):
            if not v:
                lines.append(f"{pad}{prefix}{{}}")
            else:
                lines.append(f"{pad}{prefix}{{")
                for k, x in v.items():
                    emit(str(k), x, depth + 1)
                lines.append(f"{pad}}}")
        else:
            lines.append(f"{pad}{prefix}{_scalar(v)}")

    emit(None, obj, 0)
    return "\n".join(lines)


def _register_builtin_modules() -> None:
    from compiler import diagnostics

    register(diagnostics)


_register_builtin_modules()
