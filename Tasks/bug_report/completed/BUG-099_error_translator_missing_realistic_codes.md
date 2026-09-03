# BUG-099 — 5 mã lỗi Binance thực tế một lệnh live có thể gặp rơi vào `UNKNOWN` thay vì được phân loại

**Reported date:** 2026-09-03
**Severity:** 🟡 P2 — không mất an toàn (đường xử lý `UNKNOWN` vẫn hoạt động đúng, không crash),
nhưng người vận hành thấy lý do lệnh bị từ chối mơ hồ hơn cần thiết cho các trường hợp phổ biến.
**Status:** ✅ **Đã sửa (2026-09-03)**

---

## 1. Hiện tượng (Symptom)

`binance_error_translator.py::_UNAMBIGUOUS_CODE_TO_REASON` chỉ map 4 mã lỗi
(`-2019`, `-4164`, `-2022`, `-1003`). Đọc tài liệu mã lỗi Futures API của Binance, có ít nhất 5 mã
khác một lệnh live thực tế có xác suất gặp không nhỏ, hiện rơi hết vào `OrderRejectionReason.UNKNOWN`:
`-1015` (rate limit theo số lệnh mới), `-1111`/`-4003` (precision/quantity — cùng họ `LOT_SIZE`),
`-2027` (vượt vị thế tối đa theo đòn bẩy — `INSUFFICIENT_MARGIN`), `-4131` (percent-price filter).

## 2. Root cause

Bảng map ban đầu chỉ phủ các mã lỗi trong ví dụ minh hoạ của chính `EPIC-021F` (§5) lúc dựng
module — chưa được mở rộng theo tài liệu lỗi đầy đủ của Binance Futures.

## 3. Fix

Thêm 5 entry vào `_UNAMBIGUOUS_CODE_TO_REASON`: `-1015 → RATE_LIMIT`, `-1111 → LOT_SIZE`,
`-4003 → LOT_SIZE`, `-2027 → INSUFFICIENT_MARGIN`, `-4131 → PRICE_FILTER` — mỗi entry kèm comment
trích nguyên văn message Binance tài liệu hoá cho mã đó, giữ đúng convention đã có của file.

## 4. Regression test

`tests/unit/infrastructure/binance/test_binance_error_translator.py::
test_real_binance_codes_map_to_the_expected_reason` — thêm 5 case parametrize mới, mỗi case dùng
đúng message text tài liệu hoá của Binance cho mã đó.

Xác nhận đỏ trước fix (5 mã mới trả `UNKNOWN` thay vì reason kỳ vọng), xanh sau fix.
