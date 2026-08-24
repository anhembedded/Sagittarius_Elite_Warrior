# EPIC-005A — Ghi lại vì sao đảo chiều, và điều kiện dừng

**Thuộc Epic:** [`EPIC-005`](../README.md)
**Trạng thái:** 🟡 ADR đã viết, chờ user duyệt trước khi `EPIC-005C` bắt đầu
**Phụ thuộc:** Không — đây là cổng chặn cho toàn bộ epic

---

## Kết quả

Xem toàn văn: [`DECISION_2026-08-23.md`](../DECISION_2026-08-23.md).

**Tóm tắt — kết luận thay đổi hướng đi so với `EPIC-005` README ban đầu:**

Lý do gốc chọn QML (`BOT-030`, nguyên văn: *"AI dịch mockup sang code trực tiếp hơn ở QML,
không phải hiệu năng"*) được kiểm chứng lại bằng git log, **không phải suy đoán**: workflow
"mockup → QML" **vẫn đang diễn ra liên tục** — 15+ task (`BOT-040` đến `BOT-112C`) sau
`BOT-030` đều tự ghi "theo mockup user cung cấp". Không có màn hình nào "ổn định, ít thay
đổi" — mọi màn hình bị sửa tính năng trong 10 ngày gần nhất.

**Không huỷ epic**, nhưng:

1. Thu hẹp còn màn hình form/bảng tra cứu (`EPIC-005D`/`E`, đúng như đã chọn).
2. **`EPIC-005F` (backtest + dashboard) nên hoãn vô thời hạn** — đây chính xác là nơi lý do
   gốc của QML đang phát huy tác dụng thật, không phải nơi để migrate.
3. Điều kiện dừng cụ thể đã chốt trong ADR §5.

## Việc còn lại trước khi coi task này xong

Mục 6 của ADR đề xuất sửa `README.md` epic (bỏ `F` khỏi lộ trình chủ động) và `qml-rule.md`
(QML vẫn mặc định cho màn hình nhận mockup trực tiếp). **Chưa làm** — đây là thay đổi chiến
lược, cần user đọc ADR và xác nhận trước khi áp dụng, đúng tinh thần "cổng chặn" của task này.
