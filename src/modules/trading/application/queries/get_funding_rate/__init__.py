"""The use case, its input and its handler; the answer type lives in
`contracts/`."""

from .handler import GetFundingRateQueryHandler
from .query import GetFundingRateQuery

__all__ = [
    "GetFundingRateQuery",
    "GetFundingRateQueryHandler",
]
