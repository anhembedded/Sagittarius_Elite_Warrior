# EPIC-005B — Sinh `style.qss` từ `Palette` thay vì chép hex tay

**Thuộc Epic:** [`EPIC-005`](../README.md)
**Trạng thái:** 🔴 Chưa làm
**Phụ thuộc:** Không — **có lợi kể cả khi toàn bộ EPIC-005 bị huỷ**

---

## 0. Vì sao đây là bước duy nhất thắng vô điều kiện

Chính docstring của `src/presentation/ui/assets/palette.py:15-17` thừa nhận:

> `qss/style.qss` still hardcodes its own literal hex values (QSS is a static text file, not
> generated from Python) — keeping it in sync with this class when the palette changes is a
> manual step, same as today.

Hiện tại QML lấy màu qua Theme bridge (`Palette.as_ui_dict()` → `configure_app_qml()`), còn
QtWidgets lấy màu qua QSS **chép tay**. Một lần đổi palette là hai chỗ phải sửa, và chỗ thứ
hai không có gì nhắc.

**Càng migrate sang QtWidgets thì chỗ lệch này càng nhân rộng.** Nên phải sửa *trước*, không
phải sau. Và nếu EPIC-005 bị huỷ, việc này vẫn đáng làm — đó là lý do nó không phụ thuộc
`EPIC-005A`.

## 1. Yêu cầu

1. `style.qss` không còn literal hex nào trùng với hằng số trong `Palette`. Cách làm tuỳ chọn
   — template + sinh lúc build, hoặc đọc `.qss` rồi `str.replace` token lúc chạy — **nhưng
   phải chọn cách kiểm chứng được**, không phải "cẩn thận hơn khi sửa".
2. **Test tĩnh chặn tái phát**: quét `style.qss`, fail nếu tìm thấy hex nào trùng giá trị một
   hằng số `Palette`. Đây là bản QSS của guard `anti-literal-colour` mà engine đã có cho QML —
   cùng vấn đề, nên dùng cùng cách giải.
3. Đổi một giá trị trong `Palette`, xác nhận nó **thật sự** đổi ở cả QML và QtWidgets. Kiểm
   bằng cách chạy app/render thật, không phải bằng đọc code.
4. Không đổi bất kỳ màu nào. Task này phải **không có thay đổi thị giác** — nếu app trông
   khác đi thì tức là `style.qss` và `Palette` vốn đang lệch nhau, và **đó là một BUG cần ghi
   lại riêng**, không phải sửa lặng lẽ ở đây.

## 2. Cạm bẫy

QSS không có biến. Không được "giải quyết" bằng cách nhét `{color}` vào rồi `.format()` mù —
QSS dùng `{}` cho block selector, `str.format` sẽ vỡ. Chọn cú pháp placeholder không đụng
`{}` (ví dụ `@token-name`), hoặc dùng `string.Template` với `$token`.

## 3. Xác minh

`pwsh -NoProfile -File scripts/ci-local.ps1 -Full`, rồi grep LOG_FILE tìm
`FAILED`/`ERROR`/`Traceback` — không tin console. Lưu ý bước `Chart Benchmark Contract` từng
flaky (BUG-036); nếu fail thì chạy lại trước khi kết luận.
