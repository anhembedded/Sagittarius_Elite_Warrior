from dataclasses import dataclass

from pydantic import BaseModel


class StopLiveStreamCommand(BaseModel):
    """
    @brief Command to stop the live market data stream.
    """


@dataclass(frozen=True)
class StopLiveStreamResponse:
    success: bool
    message: str
