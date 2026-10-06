import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_live_stream_service import (
    ILiveStreamService,
)

from .command import StopLiveStreamCommand, StopLiveStreamResponse

logger = logging.getLogger("App.LiveStreamUseCase")


class StopLiveStreamCommandHandler(
    ICommandHandler[StopLiveStreamCommand, StopLiveStreamResponse]
):
    def __init__(self, stream_service: ILiveStreamService):
        self._stream_service = stream_service

    def execute(self, request: StopLiveStreamCommand) -> StopLiveStreamResponse:
        logger.info(f"Executing StopLiveStreamCommand for owner={request.owner}")
        success = self._stream_service.release_owner(request.owner)
        if success:
            logger.info("StopLiveStreamCommand executed successfully.")
            return StopLiveStreamResponse(
                success=True, message="Live stream stopped successfully."
            )
        else:
            # `BUG-160`: every chart restarts with an unconditional stop
            # (`LiveChartCoordinator.stop`), and an owner holding nothing is its
            # ordinary case, not a fault a WARNING (which fails the run-log
            # scan) should report.
            logger.info("Owner %s held no live stream; nothing to stop.", request.owner)
            return StopLiveStreamResponse(
                success=False,
                message="Failed to stop live stream. It might not be running.",
            )
