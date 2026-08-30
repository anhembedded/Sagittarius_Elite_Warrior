# EPIC-018E — Rà soát Hard Design: `src/infrastructure/`

**Thuộc Epic:** [`EPIC-018`](../README.md)
**Trạng thái:** 🔴 Chưa bắt đầu
**Phụ thuộc:** Không.

---

## Phạm vi

Đúng 1 module — **chỉ** `src/infrastructure/`: `binance/`, `persistence/`,
`engine_adapters/`. Đợt khảo sát rộng chỉ đọc kỹ `sqlalchemy_repository.py`
và lướt `client.py` — `engine_adapters/` **chưa được đọc**.

## Đã biết trước (từ đợt khảo sát rộng)

- `sqlalchemy_repository.py` 478 dòng, trộn SQL/mapping/orchestration —
  ADR D5, đã lên kế hoạch tách ở `EPIC-018B` (đừng làm trùng ở đây).
- `_KLINE_STREAM_CHUNK_SIZE` định nghĩa 2 lần (`client.py` +
  `sqlalchemy_repository.py`) — ADR D6, **từ chối gộp**, chỉ sửa docstring
  gây hiểu lầm (gộp vào `EPIC-018B`).

## Việc cần làm

Đọc toàn bộ `binance/` (không chỉ `client.py`), `engine_adapters/` (chưa
ai động tới), và phần còn lại của `persistence/` ngoài
`sqlalchemy_repository.py`. Đặc biệt chú ý: adapter có leak chi tiết
implementation ra ngoài port không (`IExchangeClient`,
`IMarketDataRepository`), có chỗ nào bắt exception quá rộng nuốt lỗi
thật không.

## Tiêu chí xong

- Đọc hết mọi file `.py` trong `src/infrastructure/`.
- Mỗi finding: trích `file:line`, mức độ tin cậy, đối chiếu rule cụ thể.
- Cập nhật ADR trước khi sửa bất cứ gì.
