# EPIC-018E — Rà soát Hard Design: `src/infrastructure/`

**Thuộc Epic:** [`EPIC-018`](../README.md)
**Trạng thái:** ✅ Hoàn thành — 2026-08-30
**Phụ thuộc:** Không.
**Nguồn:** [`DECISION_2026-08-30_module_scoped_audits_round2.md`](../DECISION_2026-08-30_module_scoped_audits_round2.md) §2 mục `018E`.

---

## Kết quả rà soát

Đọc hết 12 file `.py` trong `src/infrastructure/` (1.498 dòng). 5 finding:

- **E1** — `kline_row_mapper.py:64` (`build_upsert_stmt()`) có
  `from sqlalchemy.dialects.sqlite import insert` bên trong hàm — file
  mới toanh do `EPIC-018B` tạo, không lý do circular-import.
- **E2** — `client.py:193` — magic number `1000` cho progress-callback
  cadence, cùng file đã có `_KLINE_STREAM_CHUNK_SIZE = 1000` đúng khái
  niệm này.
- **E3** — `binance_websocket_service.py:126` — `asyncio.sleep(5)`
  reconnect delay không tên.
- **E4** — `binance_websocket_service.py:139,147` — `bsm`/`tscm` không
  type annotation (mypy không bắt được do thiếu stub `python-binance`,
  vẫn đáng sửa cho người đọc).
- **E5** — `sqlalchemy_repository.py:90` untyped `session`/`stmt` —
  **từ chối sửa**, nợ kỹ thuật cũ đã nằm trong `mypy` exclude baseline từ
  trước `EPIC-018B`, không phải regression mới.

## Việc cần làm

1. `kline_row_mapper.py`: chuyển `from sqlalchemy.dialects.sqlite import insert`
   lên đầu file (cùng chỗ `import sqlalchemy as sa`).
2. `client.py:193`: đổi `if (i + 1) % 1000 == 0:` → dùng
   `_KLINE_STREAM_CHUNK_SIZE` thay vì literal `1000`.
3. `binance_websocket_service.py`: thêm hằng module-level
   `_RECONNECT_DELAY_SECONDS = 5`, dùng thay `asyncio.sleep(5)` tại dòng
   126.
4. `binance_websocket_service.py:139,147`: thêm type annotation cho
   `bsm`/`tscm` (kiểu cụ thể từ `python-binance` nếu import được không vỡ
   gì, `Any` có ghi chú lý do nếu thư viện không export type — không để
   trống hoàn toàn).

## Tiêu chí xong

- 4 việc trên hoàn thành, `mypy`/test không có lỗi mới so với trước khi
  sửa (so sánh trước/sau như đã làm ở `018A`/`018B`).
- Không đụng `sqlalchemy_repository.py:90` (quyết định từ chối đã ghi ở
  ADR).
- Test `tests/unit/infrastructure/` + `tests/integration/infrastructure/`
  xanh không đổi assertion.

## Kết quả

- `kline_row_mapper.py`: `from sqlalchemy.dialects.sqlite import insert`
  chuyển lên top-level, cùng chỗ `import sqlalchemy as sa`.
- `client.py:193`: `if (i + 1) % 1000 == 0:` → dùng
  `_KLINE_STREAM_CHUNK_SIZE` (constant đã có sẵn cùng file, đúng khái niệm
  "trang request Binance").
- `binance_websocket_service.py`: thêm `_RECONNECT_DELAY_SECONDS = 5`,
  dùng thay `asyncio.sleep(5)` + log message. Thêm type annotation cho
  `bsm: BinanceSocketManager` (đã import top-level từ trước, chỉ thiếu
  annotation) và `tscm: ReconnectingWebsocket` (đọc source `python-binance`
  để xác nhận `BinanceSocketManager._get_socket()` — nơi cả
  `kline_socket()`/`multiplex_socket()` đều gọi tới — trả về đúng type
  này; `ReconnectingWebsocket.__aenter__` trả `self` nên `tscm` cùng type
  với biến `socket`). `_create_socket()` cũng thêm return type
  `-> ReconnectingWebsocket`.
- `sqlalchemy_repository.py:90` **không đụng** (quyết định từ chối đã ghi
  ở ADR — nợ `mypy` exclude cũ, không phải regression).
- `63 test xanh` (`tests/unit/infrastructure/` +
  `tests/integration/infrastructure/`), 0 fail. `mypy` sạch trên cả 3 file
  sửa (`kline_row_mapper.py`, `binance_websocket_service.py`); `client.py`
  giữ nguyên đúng 2 lỗi pre-existing không liên quan (xác nhận qua `git
  stash` trước/sau, chỉ lệch số dòng).
