"""The Parquet writer of an export, apart from the handler so that `pyarrow` is imported
only by an export that writes Parquet (`PRO-014`).

`pyarrow` (and the `numpy` it brings) cost about 0.1 s to import. The handler is imported by
every run, because the module binds its use cases at `register()`; the writer is reached by
`Deferred` from `_write_parquet` and imported on the first Parquet export.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

#: Rows buffered before one write: a 500k-row export holds this many at a time, not all.
_BATCH_SIZE = 20_000

_SCHEMA = pa.schema(
    [
        ("symbol", pa.string()),
        ("interval", pa.string()),
        ("market", pa.string()),
        ("open_time", pa.string()),
        ("open_price", pa.float64()),
        ("high_price", pa.float64()),
        ("low_price", pa.float64()),
        ("close_price", pa.float64()),
        ("volume", pa.float64()),
        ("close_time", pa.string()),
        ("quote_asset_volume", pa.float64()),
        ("number_of_trades", pa.int64()),
        ("taker_buy_base_asset_volume", pa.float64()),
        ("taker_buy_quote_asset_volume", pa.float64()),
    ]
)


def write_parquet(rows: Iterator[dict[str, Any]], path: str) -> int:
    """Streams `rows` to `path` in batches and returns how many were written."""
    count = 0
    batch: list[dict[str, Any]] = []
    with pq.ParquetWriter(path, _SCHEMA) as parquet_writer:
        for row in rows:
            batch.append(row)
            count += 1
            if len(batch) >= _BATCH_SIZE:
                parquet_writer.write_table(pa.Table.from_pylist(batch, schema=_SCHEMA))
                batch = []
        if batch:
            parquet_writer.write_table(pa.Table.from_pylist(batch, schema=_SCHEMA))
    return count
