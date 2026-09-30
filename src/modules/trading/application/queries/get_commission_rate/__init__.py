"""The use case, its input and its handler; the answer type lives in
`contracts/`."""

from .handler import GetCommissionRateQueryHandler
from .query import GetCommissionRateQuery

__all__ = [
    "GetCommissionRateQuery",
    "GetCommissionRateQueryHandler",
]
