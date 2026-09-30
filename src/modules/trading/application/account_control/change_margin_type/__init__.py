"""The use case, its input and its handler; the answer type lives in
`contracts/`."""

from .command import ChangeMarginTypeCommand
from .handler import ChangeMarginTypeCommandHandler

__all__ = [
    "ChangeMarginTypeCommand",
    "ChangeMarginTypeCommandHandler",
]
