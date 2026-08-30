# EPIC-018C — Rà soát Hard Design: `src/domain/`

**Thuộc Epic:** [`EPIC-018`](../README.md)
**Trạng thái:** 🔴 Chưa bắt đầu
**Phụ thuộc:** Không.

---

## Phạm vi

Đúng 1 module — **chỉ** `src/domain/`: `entities/`, `events/`,
`value_objects/`, `models/`, `indicators/`, `indicator_scripts/`,
`scripting/`, `strategies/`, `backtesting/`. Không lan sang
`application/`/`infrastructure`/`presentation` — mỗi module có task riêng
(xem `EPIC-018` README).

## Đã biết trước (từ đợt khảo sát rộng, cần xác nhận lại kỹ hơn trong task này)

- `base_indicator_script.py` (515 dòng/~28 method) — ADR D7 đã **từ chối**
  tách, đánh giá là DSL cohesive hợp lệ, nhưng chính agent khảo sát tự nhận
  "độ tin cậy thấp". Task này nên xác nhận lại kỹ hơn (đọc toàn bộ 9 script
  con kế thừa nó, xem có thực sự dùng hết ~28 method hay một phần đã chết).

## Việc cần làm

Đọc toàn bộ `src/domain/` tìm Hard Design thật (concrete-phụ-concrete
không qua port, God File chưa theo dõi, magic number/string không có
SSOT, duck-typing ngầm). Đối chiếu `.agents/rules/architecture-rule.md`
trước khi kết luận — domain layer đặc biệt nhạy với "Single-Scope
Cohesion" (§5.5): nhiều class trông dài nhưng là DSL/aggregate hợp lệ, đừng
pattern-match bề mặt.

## Tiêu chí xong

- Đọc hết mọi file `.py` trong `src/domain/` (không chỉ file lớn).
- Mỗi finding: trích `file:line`, mức độ tin cậy, đối chiếu rule cụ thể.
- Cập nhật ADR `EPIC-018` (hoặc ADR riêng nếu finding đủ lớn) với quyết định
  từng điểm trước khi sửa bất cứ gì.
