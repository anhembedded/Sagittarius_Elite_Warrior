from abc import ABC, abstractmethod
from sagittarius_engine import App


class IMenuHandler(ABC):
    """
    @brief Interface for Terminal Menu Handlers.
    @details Ensures that menu logic is split into separate files avoiding God Object.
    """

    @abstractmethod
    def handle(self, app: App) -> None:
        """
        @brief Executes the interactive logic for a specific menu choice.
        @param app The Sagittarius App instance to resolve dependencies or dispatch commands.
        """
        pass
