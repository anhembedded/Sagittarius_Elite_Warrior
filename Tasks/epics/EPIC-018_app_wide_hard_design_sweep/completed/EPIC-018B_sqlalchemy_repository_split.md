# EPIC-018B — `sqlalchemy_repository.py`: tách mapping/query-building

**Thuộc Epic:** [`EPIC-018`](../README.md)
**Trạng thái:** ✅ Hoàn thành — 2026-08-30
**Phụ thuộc:** Không.
**Nguồn:** ADR D5 (tách file) + D6 (sửa docstring gây hiểu lầm, gộp vào task này vì cùng file).

---

## Hiện trạng

`src/infrastructure/persistence/sqlalchemy_repository.py` — 478 dòng,
vượt ngưỡng cứng `architecture-rule.md` §5.4 (>400 dòng). Trộn 3 tầng
trách nhiệm: build câu SQL thô (`_build_upsert_stmt`, `_build_status_query`),
mapping ORM-row ↔ domain entity (`_to_market_data_entity`,
`_map_status_result`, `_parse_db_datetime`), và logic nghiệp vụ repository
(`get_gaps`, `get_range_coverage`).

`_KLINE_STREAM_CHUNK_SIZE:31` có docstring viết "matching the
`_KLINE_STREAM_CHUNK_SIZE` convention already established" (ở
`client.py:30`) — gây hiểu lầm là cố ý dùng chung 1 giá trị, trong khi
ADR D6 đã xác định đây là **2 tunable độc lập** (page size Binance REST vs
batch size `yield_per()` của SQLAlchemy) tình cờ cùng giá trị 1000.

## Việc cần làm

1. Tách `_to_market_data_entity`, `_build_status_query`,
   `_map_status_result`, `_parse_db_datetime`, `_build_upsert_stmt` sang
   `kline_row_mapper.py` cùng thư mục `persistence/` — đúng tiền lệ
   `EPIC-003C` (tách Policy khỏi `paper_exchange.py`).
2. Class repository chỉ còn orchestration — gọi mapper, không tự build SQL
   thô hay tự parse datetime.
3. Sửa docstring ở `_KLINE_STREAM_CHUNK_SIZE` — nói rõ đây là 2 tunable độc
   lập, không phải dùng chung 1 nguồn — **không đổi giá trị, không gộp
   constant** (ADR D6 đã từ chối gộp).

## Tiêu chí xong

- `sqlalchemy_repository.py` xuống dưới 400 dòng.
- `kline_row_mapper.py` mới có test riêng (hoặc test hiện có của repository
  vẫn phủ được qua orchestration, ghi rõ hướng nào được chọn).
- Toàn bộ test `tests/.../test_sqlalchemy_repository*.py` xanh không đổi
  assertion.
- Docstring `_KLINE_STREAM_CHUNK_SIZE` không còn gợi ý sai về việc dùng
  chung constant.

## Kết quả

- `src/infrastructure/persistence/kline_row_mapper.py` (mới, 174 dòng) —
  7 hàm module-level thuần (không class, đúng tiền lệ `backtest_range_coverage.py`
  đã được chính file này import sẵn): `to_market_data_entity`,
  `parse_db_datetime`, `build_upsert_stmt`, `build_status_query`,
  `map_status_result`, `build_range_coverage_query`, `build_gaps_query`.
- **Lan rộng hơn kế hoạch ban đầu (ghi nhận trung thực):** task chỉ liệt kê
  5 hàm; tách thêm 2 hàm build-query nữa
  (`build_range_coverage_query`/`build_gaps_query`, trước đây là SQL thô
  viết thẳng trong `get_range_coverage`/`get_gaps`) vì để lại sẽ vi phạm
  đúng tiêu chí "class repository chỉ còn orchestration, không tự build
  SQL thô" mà task này đặt ra — không có lý do giữ 2/4 raw-SQL query trong
  class trong khi 2 cái kia đã chuyển đi.
- `sqlalchemy_repository.py`: 478 → **355 dòng** (dưới ngưỡng 400).
  `get_database_status`/`get_range_coverage`/`get_gaps` giờ chỉ gọi
  `build_*_query()` + `map_status_result()`/`parse_db_datetime()`, không
  tự build SQL hay tự parse datetime.
- `_KLINE_STREAM_CHUNK_SIZE` docstring viết lại rõ: 2 tunable độc lập
  (Binance REST page size ở `client.py` vs SQLAlchemy `yield_per()` batch
  size ở đây), trỏ thẳng tới ADR D6 — không đổi giá trị, không gộp hằng số.
- Test cập nhật: `test_sqlalchemy_repository_helpers.py` — 3 test đọc
  `SQLAlchemyMarketDataRepository._to_market_data_entity`/`_parse_db_datetime`
  đổi sang import thẳng `to_market_data_entity`/`parse_db_datetime` từ
  `kline_row_mapper`. `_group_by_symbol` giữ nguyên trên class (không thuộc
  nhóm mapping/query-building — nó gom domain entity cho vòng lặp upsert).
- `32 test xanh` (unit + integration persistence), 0 fail, cùng 6 warning
  SQLAlchemy `DeprecationWarning` pre-existing (không liên quan thay đổi
  này). `mypy` sạch trên cả 2 file.
