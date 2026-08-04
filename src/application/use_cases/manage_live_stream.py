from dataclasses import dataclass
from pydantic import BaseModel, field_validator
from typing import List
from Binace_Bot.src.application.contracts.i_live_stream_service import (
    ILiveStreamService,
)
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame
from sagittarius_engine.extensions.cqrs import ICommand
import logging

logger = logging.getLogger("App.LiveStreamUseCase")


class StartLiveStreamCommand(BaseModel):
    """
    @brief Command to start the live market data stream.
    """

    symbols: List[str]
    interval: TimeFrame

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("Symbols list cannot be empty")
        for s in v:
            if len(s) < 3 or not s.isalnum():
                raise ValueError(f"'{s}' is not a valid trading pair symbol.")
        return [s.upper() for s in v]


@dataclass(frozen=True)
class StartLiveStreamResponse:
    success: bool
    message: str


class StartLiveStreamCommandHandler(
    ICommand[StartLiveStreamCommand, StartLiveStreamResponse]
):
    def __init__(self, stream_service: ILiveStreamService):
        self._stream_service = stream_service

    def execute(self, request: StartLiveStreamCommand) -> StartLiveStreamResponse:
        logger.info(
            f"Executing StartLiveStreamCommand for symbols: {request.symbols}, interval: {request.interval.value}"
        )
        success = self._stream_service.start_stream(
            request.symbols, request.interval.value
        )
        if success:
            logger.info("StartLiveStreamCommand executed successfully.")
            return StartLiveStreamResponse(
                success=True, message="Stream started successfully."
            )
        else:
            logger.warning(
                "StartLiveStreamCommand failed: Stream is already running or failed to start."
            )
            return StartLiveStreamResponse(
                success=False, message="Stream is already running or failed to start."
            )


class StopLiveStreamCommand(BaseModel):
    """
    @brief Command to stop the live market data stream.
    """

    pass


@dataclass(frozen=True)
class StopLiveStreamResponse:
    success: bool
    message: str


class StopLiveStreamCommandHandler(
    ICommand[StopLiveStreamCommand, StopLiveStreamResponse]
):
    def __init__(self, stream_service: ILiveStreamService):
        self._stream_service = stream_service

    def execute(self, request: StopLiveStreamCommand) -> StopLiveStreamResponse:
        logger.info("Executing StopLiveStreamCommand")
        success = self._stream_service.stop_stream()
        if success:
            logger.info("StopLiveStreamCommand executed successfully.")
            return StopLiveStreamResponse(
                success=True, message="Stream stopped successfully."
            )
        else:
            logger.warning("StopLiveStreamCommand failed: Stream is not running.")
            return StopLiveStreamResponse(
                success=False, message="Stream is not running."
            )
