import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_venues import (
    IMarketDataVenues,
)

from .command import StopLiveStreamCommand, StopLiveStreamResponse

logger = logging.getLogger("App.LiveStreamUseCase")


class StopLiveStreamCommandHandler(
    ICommandHandler[StopLiveStreamCommand, StopLiveStreamResponse]
):
    def __init__(self, venues: IMarketDataVenues):
        self._venues = venues

    def execute(self, request: StopLiveStreamCommand) -> StopLiveStreamResponse:
        logger.info(f"Executing StopLiveStreamCommand for owner={request.owner}")
        stream = self._venues.live_stream(request.venue or self._venues.default_venue)
        success = stream.release_owner(request.owner)
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
