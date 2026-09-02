from Sagittarius_Elite_Warrior.src.domain.trading.client_order_id import (
    MAX_CLIENT_ORDER_ID_LENGTH,
    generate_client_order_id,
)


def test_generated_id_carries_the_app_prefix() -> None:
    client_order_id = generate_client_order_id()
    assert client_order_id.startswith("SEW-")


def test_generated_id_is_within_binances_length_limit() -> None:
    client_order_id = generate_client_order_id()
    assert len(client_order_id) <= MAX_CLIENT_ORDER_ID_LENGTH


def test_generated_ids_are_unique() -> None:
    ids = {generate_client_order_id() for _ in range(1000)}
    assert len(ids) == 1000
