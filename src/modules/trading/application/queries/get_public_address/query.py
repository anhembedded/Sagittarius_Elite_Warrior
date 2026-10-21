from dataclasses import dataclass


@dataclass(frozen=True)
class GetPublicAddressQuery:
    """
    @brief Query for the public IPv4 address outside servers see for this
    machine (`BOT-224`).
    @details No fields: the address is the machine's, not a venue's. It is
    dispatched only when the user asks, because answering it calls a third party.
    """
