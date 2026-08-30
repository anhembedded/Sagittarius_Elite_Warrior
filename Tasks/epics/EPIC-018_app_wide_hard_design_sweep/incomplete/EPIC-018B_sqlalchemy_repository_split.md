# EPIC-018B — `sqlalchemy_repository.py`: tách mapping/query-building

**Thuộc Epic:** [`EPIC-018`](../README.md)
**Trạng thái:** 🔴 Chưa bắt đầu
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
