import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_venues import (
    IMarketDataVenues,
)

from .command import StartLiveStreamCommand, StartLiveStreamResponse

logger = logging.getLogger("App.LiveStreamUseCase")


class StartLiveStreamCommandHandler(
    ICommandHandler[StartLiveStreamCommand, StartLiveStreamResponse]
):
    def __init__(self, venues: IMarketDataVenues):
        self._venues = venues

    def execute(self, request: StartLiveStreamCommand) -> StartLiveStreamResponse:
        logger.info(
            f"Executing StartLiveStreamCommand for owner={request.owner} "
            f"{request.market_type.value} {request.symbols} at "
            f"{request.interval.value}"
        )
        stream = self._venues.live_stream(request.venue or self._venues.default_venue)
        success = stream.subscribe(
            request.owner, request.market_type, request.symbols, request.interval
        )
        if success:
            logger.info("StartLiveStreamCommand executed successfully.")
            return StartLiveStreamResponse(
                success=True, message="Live stream started successfully."
            )
        else:
            logger.warning("Failed to start live stream.")
            return StartLiveStreamResponse(
                success=False, message="Failed to start live stream."
            )
