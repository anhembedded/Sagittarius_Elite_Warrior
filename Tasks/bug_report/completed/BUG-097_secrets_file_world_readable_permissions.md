# BUG-097 — `secrets.local.json` được ghi mà không khoá quyền file — key/secret sàn nằm world-readable trên hệ thống nhiều người dùng

**Reported date:** 2026-09-03
**Severity:** 🟡 P2 — không phải lỗ hổng khai thác từ xa, nhưng vi phạm nguyên tắc "secret ở đĩa
phải có quyền hạn chế" trên các hệ thống multi-user (server chia sẻ, máy CI dùng chung).
**Status:** ✅ **Đã sửa (2026-09-03)**

---

## 1. Hiện tượng (Symptom)

`SecretsFileSource.write()` (`src/infrastructure/credentials/secrets_file_source.py`) ghi API
key/secret Binance Testnet vào `secrets.local.json` bằng `json.dump()` thường — không có bước nào
đặt quyền file sau khi tạo. Trên Linux, file mới tạo qua `open()` thường thừa kế `umask` hệ thống
(thường `0o644` — world-readable), nghĩa là bất kỳ user nào khác trên cùng máy đọc được credential
sàn.

## 2. Root cause

`write()` chỉ gọi `json.dump(data, f)` rồi đóng file — thiếu bước `os.chmod()` để chủ động thu hẹp
quyền về chỉ chủ sở hữu, bất kể `umask` hệ thống là gì.

## 3. Fix

`write()` thêm `os.chmod(self._filepath, 0o600)` ngay sau `json.dump(...)`, bọc trong
try/except `OSError` — nếu hệ thống file không hỗ trợ chmod theo cách này (một số filesystem
mạng), log cảnh báo thay vì raise, không chặn việc secret đã ghi thành công.

## 4. Regression test

`tests/unit/infrastructure/credentials/test_secrets_file_source.py::
test_write_hardens_the_file_to_owner_only` — ghi một file thật, đọc lại `stat.S_IMODE(...)`,
xác nhận đúng `0o600`. Đánh dấu `@pytest.mark.skipif(sys.platform == "win32", ...)` — Unix
permission bits không áp dụng trên Windows.

Xác nhận đỏ trước fix (mode file sau `write()` giữ nguyên theo `umask` mặc định, không phải
`0o600`), xanh sau fix.
