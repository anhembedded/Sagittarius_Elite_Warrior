from pydantic import BaseModel
from dataclasses import dataclass

class StopLiveStreamCommand(BaseModel):
    """
    @brief Command to stop the live market data stream.
    """
    pass

@dataclass(frozen=True)
class StopLiveStreamResponse:
    success: bool
    message: str
