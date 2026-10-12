"""`EPIC-038C` - "is a host running, and what does it hold?"."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GetHostStatusQuery:
    """No parameters: the host is the one on this data root."""
