"""Read the header of `state/host-facts.json` (`EPIC-047B`)."""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_facts_document import (
    HostFactsHeader,
    HostFactsUnreadableError,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_facts_codec import (
    IHostFactsCodec,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_facts_source import (
    IHostFactsSource,
)


class FileHostFactsSource(IHostFactsSource):
    def __init__(self, path: Path, codec: IHostFactsCodec) -> None:
        self._path = path
        self._codec = codec

    def read_header(self) -> HostFactsHeader | None:
        try:
            raw = self._path.read_bytes()
        except FileNotFoundError:
            return None
        except OSError as failure:
            raise HostFactsUnreadableError(
                f"the file cannot be read ({type(failure).__name__})"
            ) from failure
        return self._codec.decode_header(raw)
