import logging
from sagittarius_engine.interfaces.i_engine_context import IEngineContext
from sagittarius_engine.runtime.hosted.hosted_service import IHostedService

from Binace_Bot.src.application.contracts.i_live_stream_service import (
    ILiveStreamService,
)

logger = logging.getLogger("App.LiveStreamAdapter")


class LiveStreamEngineAdapter(IHostedService):
    """
    @brief Object Adapter bridging the Engine's IHostedService lifecycle with the pure ILiveStreamService.
    @details Ensures the stream is cleanly shut down when the Engine stops, while keeping ILiveStreamService agnostic of the Engine.
    """

    def __init__(self, stream_service: ILiveStreamService) -> None:
        self._stream_service = stream_service

    def start(self, context: IEngineContext) -> None:
        """
        @brief Called by the Engine on boot.
        """
        logger.info("LiveStreamEngineAdapter started.")

    def stop(self, context: IEngineContext) -> None:
        """
        @brief Called by the Engine on shutdown. Stops the stream if running.
        """
        logger.info("Engine shutting down, ensuring stream is stopped...")
        self._stream_service.stop_stream()
