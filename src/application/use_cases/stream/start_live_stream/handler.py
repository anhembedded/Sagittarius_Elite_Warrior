import logging

from Sagittarius_Elite_Warrior.src.application.ports.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.application.ports.i_live_stream_service import ILiveStreamService

from .command import StartLiveStreamCommand, StartLiveStreamResponse

logger = logging.getLogger("App.LiveStreamUseCase")


class StartLiveStreamCommandHandler(
    ICommandHandler[StartLiveStreamCommand, StartLiveStreamResponse]
):
    def __init__(self, stream_service: ILiveStreamService):
        self._stream_service = stream_service

    def execute(self, request: StartLiveStreamCommand) -> StartLiveStreamResponse:
        logger.info(
            f"Executing StartLiveStreamCommand for {request.symbols} at {request.interval.value}"
        )
        success = self._stream_service.start_stream(
            request.symbols, request.interval.value
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
