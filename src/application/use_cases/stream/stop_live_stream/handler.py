import logging

from Binace_Bot.src.application.ports.i_cqrs import ICommandHandler
from Binace_Bot.src.application.ports.i_live_stream_service import ILiveStreamService

from .command import StopLiveStreamCommand, StopLiveStreamResponse

logger = logging.getLogger("App.LiveStreamUseCase")


class StopLiveStreamCommandHandler(
    ICommandHandler[StopLiveStreamCommand, StopLiveStreamResponse]
):
    def __init__(self, stream_service: ILiveStreamService):
        self._stream_service = stream_service

    def execute(self, request: StopLiveStreamCommand) -> StopLiveStreamResponse:
        logger.info("Executing StopLiveStreamCommand")
        success = self._stream_service.stop_stream()
        if success:
            logger.info("StopLiveStreamCommand executed successfully.")
            return StopLiveStreamResponse(
                success=True, message="Live stream stopped successfully."
            )
        else:
            logger.warning("Failed to stop live stream. It might not be running.")
            return StopLiveStreamResponse(
                success=False,
                message="Failed to stop live stream. It might not be running.",
            )
