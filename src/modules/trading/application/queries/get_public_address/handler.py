import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_public_address.query import (
    GetPublicAddressQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_public_address_reader import (
    IPublicAddressReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.public_address_lookup import (
    PublicAddressLookup,
)

logger = logging.getLogger("App.QueryHandler")


class GetPublicAddressQueryHandler(
    IQueryHandler[GetPublicAddressQuery, PublicAddressLookup]
):
    """@brief Handler for `GetPublicAddressQuery` (`BOT-224`): a thin CQRS wrapper,
    so the Options page asks through the dispatcher and never reaches the adapter."""

    def __init__(self, reader: IPublicAddressReader) -> None:
        self._reader = reader

    def execute(self, query: GetPublicAddressQuery) -> PublicAddressLookup:
        logger.debug("Handling GetPublicAddressQuery")
        return self._reader.read()
