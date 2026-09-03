# BUG-098 — `FuturesMetadataProvider.get_or_fetch()` không bao giờ coi cache là cũ — `is_stale()` viết ra nhưng chết, không ai gọi

**Reported date:** 2026-09-03
**Severity:** 🟡 P2 — symbol filter (`minNotional`, `lotSize`, `priceFilter`...) có thể lệch khỏi
thực tế sàn vô thời hạn một khi đã cache lần đầu trong phiên, dù entry đã hết hạn theo TTL của
chính nó.

**Status:** ✅ **Đã sửa (2026-09-03)**

---

## 1. Hiện tượng (Symptom)

`FuturesSymbolMetadata` có method `is_stale()` (kiểm tra tuổi entry so với TTL) — nhưng
`FuturesMetadataProvider.get_or_fetch()` chỉ kiểm tra `if cached is not None:` để quyết định dùng
cache hay gọi mạng lại. Một khi symbol đã được cache lần đầu, `get_or_fetch()` không bao giờ gọi
mạng lại cho symbol đó nữa trong suốt vòng đời tiến trình, bất kể `is_stale()` trả gì — cache
"sống mãi", TTL vô nghĩa trên thực tế.

## 2. Root cause

Điều kiện `if cached is not None:` thiếu vế `and not cached.is_stale()` — `is_stale()` đã được
viết đầy đủ logic đúng (dead code, không ai gọi tới), chỉ thiếu một chỗ dùng nó.

## 3. Fix

`get_or_fetch()`'s điều kiện đổi thành `if cached is not None and not cached.is_stale():` — cache
hit chỉ tính khi entry còn tồn tại **và** chưa hết hạn; cache miss (kể cả do stale) rơi vào nhánh
gọi mạng lại như bình thường.

## 4. Regression test

`tests/unit/infrastructure/binance/test_futures_metadata_provider.py::
test_a_stale_cache_hit_forces_a_real_refresh` — cache một `FuturesSymbolMetadata` với
`cached_at` đã quá hạn TTL, gọi `get_or_fetch()`, xác nhận session factory được gọi lại (network
refresh thật xảy ra) thay vì trả thẳng entry cũ.

Xác nhận đỏ trước fix (entry stale vẫn được trả về, không có lệnh gọi mạng nào xảy ra), xanh sau
fix.
