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
## 2025-02-20 - ThreadPoolExecutor Rate Limiting

**Learning:** When using `concurrent.futures.ThreadPoolExecutor` to speed up blocking tasks (like market data syncs) that also need to abide by rate limits, simple sequential `sleep` delays in the submission loop are inadequate if task processing is slow. If worker threads are occupied, tasks queue up. When multiple threads become available simultaneously, queued tasks burst into execution, violating the rate limit spacing.
**Action:** Enforce rate limit spacing using a global thread-safe lock and track the `last_dispatch_time` *inside* the submitted worker functions. This ensures the rate limit delay dictates the execution start times, regardless of queue bursts.
## 2024-10-18 - Optimized PySide6 QPainter Operations

**Learning:** Batching drawing operations using `QPainter.drawLines` and `QPainter.drawRects` with an accumulated list of `QLineF` and `QRectF` avoids the heavy overhead of repeatedly calling `QPainter.drawLine` and `QPainter.drawRect` coupled with setting the brush/pen on each iteration. Doing so cuts rendering time by approximately 8-10x for tens of thousands of items (e.g. 4.2s to 0.4s on 50,000 candles).

**Action:** Whenever drawing multiple lines or rects with the same colors, pre-accumulate `QLineF` and `QRectF` collections and use `drawLines()` / `drawRects()` to batch the draw operations instead of setting up and drawing elements individually in a loop.
## 2024-11-20 - [Optimize pyqtgraph BarGraphItem rendering]
**Learning:** Calling `pg.mkBrush(color)` inside a list comprehension on high-frequency UI rendering callbacks (like `refresh_window()` called on every pan/zoom frame for volume bars) is surprisingly slow and causes severe stutter. It rebuilds `QBrush` objects on every frame.
**Action:** Pre-instantiate and track the `QBrush` objects instead of string colors, and slice the brush list directly to pass to `setOpts()`. This cuts rendering time by ~20x.

## 2024-11-28 - Concurrent Database Scanning
**Learning:** Nested loops querying database status sequentially scale extremely poorly as the number of symbols and intervals increases.
**Action:** Always utilize `concurrent.futures.ThreadPoolExecutor` to concurrently map independent database readout queries (like status/gap checking) instead of sequential iterations.
