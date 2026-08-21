# EPIC-003C — `PaperExchange` → Domain Policy (Margin/Matching/Fee)

**Thuộc Epic:** [`EPIC-003`](../README.md)
**Trạng thái:** 🔴 Chưa làm
**Phụ thuộc:** Không có — độc lập hoàn toàn, làm bất kỳ lúc nào, song song được với mọi task khác của epic này.

---

## 1. Vì Sao Rủi Ro Thấp Nhất Trong Cả 6 Task

Thuần Domain — không đụng PySide6/QML, không có rủi ro lệch binding UI như
mọi task Presentation khác trong epic này. Đã có **47+ test bảo vệ sẵn**
cho `PaperExchange` (xác nhận qua `BOT-114`/`BUG-025` phiên này — mọi lần
sửa file này trước giờ đều verify bằng cách chạy toàn bộ suite đó không đổi
assertion).

## 2. Thiết Kế (theo `PRO-002` §2.4)

3 Policy tách khỏi `paper_exchange.py` (662 dòng hiện tại):
- `MarginRiskPolicy`: ký quỹ, Maintenance Margin, Margin Call, Liquidation —
  đúng logic đòn bẩy vừa thêm ở `BOT-114`.
- `OrderMatchingPolicy`: khớp lệnh theo nến/tick, intrabar stop (`BOT-041`).
- `FeeCalculatorPolicy`: phí Maker/Taker, tính trên notional (đúng quyết
  định đã chốt ở `BOT-114`).

`PaperExchange` giữ vai trò điều phối, gọi vào 3 Policy — không tự tính
toán margin/khớp lệnh/phí trực tiếp nữa.

## 3. Kiểm Thử / Nghiệm Thu

- Toàn bộ test hiện có của `test_paper_exchange.py` phải pass **không đổi
  một assertion nào** — đây là bằng chứng bắt buộc rằng tách file không đổi
  hành vi tính toán tài chính (sai số ở đây là sai tiền thật nếu lên
  production).
- Mỗi Policy có test đơn vị riêng, cô lập khỏi `PaperExchange`.
