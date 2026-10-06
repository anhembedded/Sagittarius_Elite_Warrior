"""`BUG-052`/`BUG-067` regression: `PythonBinanceClient.close()` closes the
`requests` session underneath, which is what unblocks a worker still waiting
on a network read at shutdown.

Moved here from the Dev Board's stream tests when the Dev Board was deleted
(`EPIC-033P` stage 3): the client outlives the screen that first proved it.
"""

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance.client import (
    PythonBinanceClient,
)


def test_close_closes_the_sdk_clients_session():
    injected_client = Mock()
    client = PythonBinanceClient(client=injected_client)

    client.close()

    injected_client.session.close.assert_called_once()
