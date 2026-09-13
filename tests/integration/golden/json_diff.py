"""A readable list of differences between two JSON-shaped values, by path."""

from __future__ import annotations

from typing import Any


def diff(expected: Any, actual: Any, path: str = "$") -> list[str]:
    if isinstance(expected, dict) and isinstance(actual, dict):
        out: list[str] = []
        for key in sorted(set(expected) | set(actual)):
            if key not in expected:
                out.append(f"  {path}.{key}: added")
            elif key not in actual:
                out.append(f"  {path}.{key}: removed")
            else:
                out.extend(diff(expected[key], actual[key], f"{path}.{key}"))
        return out
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return [f"  {path}: length {len(expected)} -> {len(actual)}"]
        out = []
        for index, (e, a) in enumerate(zip(expected, actual, strict=True)):
            out.extend(diff(e, a, f"{path}[{index}]"))
        return out
    if expected != actual:
        return [f"  {path}: {expected!r} -> {actual!r}"]
    return []
