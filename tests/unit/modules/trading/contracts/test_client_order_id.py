import re

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    MAX_CLIENT_ORDER_ID_LENGTH,
    InvalidClientOrderTagError,
    generate_client_order_id,
    tag_of,
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


# --- EPIC-029A (ADR D5): the bot tag -----------------------------------------

_UNTAGGED = re.compile(r"^SEW-[0-9a-f]{12}$")
_TAGGED = re.compile(r"^SEW-a3f9c1-[0-9a-f]{10}$")


def test_an_untagged_id_keeps_its_original_shape() -> None:
    assert all(_UNTAGGED.fullmatch(generate_client_order_id()) for _ in range(200))


def test_a_tagged_id_carries_the_tag() -> None:
    ids = [generate_client_order_id("a3f9c1") for _ in range(200)]
    assert all(_TAGGED.fullmatch(client_order_id) for client_order_id in ids)
    assert len(set(ids)) == 200
    assert max(map(len, ids)) <= MAX_CLIENT_ORDER_ID_LENGTH


@pytest.mark.parametrize(
    "tag", ["", "a3f9c", "a3f9c12", "A3F9C1", "a3f9c-", "a3f9c ", "a3f9cé"]
)
def test_a_malformed_tag_is_refused_by_name(tag: str) -> None:
    with pytest.raises(InvalidClientOrderTagError) as caught:
        generate_client_order_id(tag)
    assert caught.value.tag == tag


def test_tag_of_reads_the_tag_back() -> None:
    assert tag_of(generate_client_order_id("zz0099")) == "zz0099"
    assert tag_of(generate_client_order_id()) is None
    assert tag_of("SEW-a3f9c1-0123456789") == "a3f9c1"
    assert tag_of("SEW-a3f9c1-012345678") is None  # suffix one short
    assert tag_of("SEW-A3F9C1-0123456789") is None
    assert tag_of("web_xyz") is None
