import logging

from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_live_stream_service import (
    ILiveStreamService,
)
from sagittarius_engine.interfaces.i_engine_context import IEngineContext
from sagittarius_engine.runtime.hosted.hosted_service import IHostedService

logger = logging.getLogger("App.LiveStreamAdapter")


class LiveStreamEngineAdapter(IHostedService):
    """
    @brief Object Adapter bridging the Engine's IHostedService lifecycle with the pure ILiveStreamService.
    @details Ensures the stream is cleanly shut down when the Engine stops, while keeping ILiveStreamService agnostic of the Engine.
    The service is looked up at `stop()`, and only if something built it (`PRO-014`): taking it in the
    constructor made every boot build the websocket service, and with it import the exchange SDK,
    for a run that never opened a stream. A service nobody built has nothing to stop.
    """

    def start(self, context: IEngineContext) -> None:
        """
        @brief Called by the Engine on boot.
        """
        logger.info("LiveStreamEngineAdapter started.")

    def stop(self, context: IEngineContext) -> None:
        """
        @brief Called by the Engine on shutdown. Stops the stream if running.
        """
        registration = context.container.registrations().get(ILiveStreamService)
        if registration is None or not registration.instantiated:
            logger.info("No live stream was built, nothing to stop.")
            return
        logger.info("Engine shutting down, ensuring stream is stopped...")
        context.container.resolve(ILiveStreamService).stop_all()
