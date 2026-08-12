## 2026-08-09 - UI Rendering Optimization: Candlestick Bounds Caching
**Learning:** O(N) operations inside high-frequency UI rendering callbacks like PyQtGraph's `dataBounds()` (called on every panning frame) can introduce severe stutter. Pre-computing min/max list comprehensions based on visible slices was slow.
**Action:** Next time, cache the computed bounds keyed by the window slicing bounds (like binary search index bounds `lo` and `hi`). Combine this with using cached full bounding boxes (e.g. `self._full_bounds_rect.top()`) instead of doing a full history scan for global bounds fallback. Use generator expressions to save memory overhead if cache re-population is required. Always measure with a benchmark script.
## 2024-11-13 - [Optimize get_klines using SQLAlchemy Core]
**Learning:** For extremely high-throughput database inserts and upserts in SQLAlchemy, `session.execute` and multiple inner loop commits incur a massive performance penalty. Switching to `connection.execute` completely bypasses the ORM's processing pipeline, and doing dictionary construction internally without method calls speeds up mappings. Committing only once reduces SQLite file lock handling and transaction management.
**Action:** Always prefer Core connection `conn.execute()` for data migration, batch inserts, and upserts. Ensure transactions encapsulate the entire operation rather than every chunk.

## 2026-08-12 - [Optimize datetime difference calculations using unixepoch()]
**Learning:** For SQLite database queries computing integer seconds for time deltas, using the native `unixepoch()` function is more performant than `strftime('%s', ...)`. Since the project runs on SQLite 3.45.1+, `unixepoch()` is fully supported and natively computes the UNIX timestamp more directly than formatting the datetime string.
**Action:** Prefer `unixepoch()` over `strftime('%s', ...)` in all SQLite queries computing timestamps or time deltas to maximize database query performance.

## 2024-02-12 - Batch Database Queries via ThreadPoolExecutor
**Learning:** Sequential database queries within a loop inside the application use cases caused high latency. By utilizing a ThreadPoolExecutor inside the handler to fetch independent data sources (symbols) concurrently, we achieve significant performance improvements.
**Action:** Next time when designing handlers that fetch multiple independent pieces of data from the database, consider accepting a batch/list of inputs and dispatching them concurrently within the handler, ensuring thread safety and minimizing roundtrips through the CQRS dispatcher.
