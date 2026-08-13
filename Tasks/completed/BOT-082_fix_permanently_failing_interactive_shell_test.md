# Nhiệm vụ: Sửa test đỏ vĩnh viễn — `test_interactive_shell_wait_for_exit_exception`

> Nguồn: 📄 [Rà soát định hướng App](../reports/app_direction_audit.md) §6.
>
> **Sửa mất ~1 phút. Nên làm ngay, không xếp hàng** — lý do ở §3, và nó không nằm ở chỗ
> cái test này quan trọng.

## 1. Triệu chứng

`pytest Sagittarius_Elite_Warrior/tests/unit/` **luôn** kết thúc bằng `1 failed`:

```
FAILED tests/unit/presentation/cli/test_interactive_shell.py::test_interactive_shell_wait_for_exit_exception
→ ModuleNotFoundError: No module named 'src'
```

## 2. Root cause (đã verify)

`tests/unit/presentation/cli/test_interactive_shell.py:169`:

```python
with patch('src.presentation.cli.interactive_shell.logger.exception') as mock_logger:
```

Thiếu tiền tố `Sagittarius_Elite_Warrior.`. **Mọi import khác trong chính file đó đều
có đủ** (dòng 3, 6, 9, 10) — nên đây là lỗi đánh máy cục bộ ở đúng một chuỗi, không phải
vấn đề cấu hình `pythonpath`.

Thêm vào bởi commit `9cd7ebf` *"Add tests for InteractiveShell start, wait_for_exit,
_run_loop, and do_help"* (12/08/2026) — mẫu commit của agent viết test tự động. Test này
**chưa từng pass một lần nào** kể từ khi merge.

## 3. Vì sao đáng ưu tiên dù bản thân nó vặt

Hệ quả nguy hiểm hơn nhiều so với cái test:

> Mỗi lần chạy suite đều thấy `1 failed`, nên **cả người lẫn agent đều học được thói quen
> bỏ qua màu đỏ.**

Trong chính phiên làm việc sinh ra báo cáo này, tôi đã xác nhận "không liên quan, có sẵn
từ trước" rồi đi tiếp **5 lần liên tiếp** — đúng cơ chế mà một regression thật sẽ lọt qua
mà không ai để ý.

Một suite đỏ thường trực làm hỏng **toàn bộ giá trị tín hiệu** của mọi test khác. Đó là
lý do task này ưu tiên cao, không phải vì `InteractiveShell` quan trọng.

## 4. Các bước thực hiện

- [x] Sửa chuỗi patch thành `Sagittarius_Elite_Warrior.src.presentation.cli.interactive_shell.logger.exception`.
- [x] Chạy lại → 13/13 test trong file xanh; **`test_interactive_shell_wait_for_exit_exception`
      biến mất khỏi danh sách đỏ của toàn suite.**
- [x] Quét nhanh các file test khác xem có `patch('src.` nào cùng lỗi không.
      `grep -rn "patch(['\"]src\." tests/ src/` → **đúng 1 chỗ duy nhất**, không có ca thứ hai.
- [x] Xác nhận test sau khi sửa **thật sự kiểm tra được điều nó nói**.

## 5. Kết quả triển khai thực tế

**Sửa**: 1 chuỗi, thêm tiền tố `Sagittarius_Elite_Warrior.` (ruff format tách thành 3 dòng).

**Verify bằng mutation test** — vì bước 4 cảnh báo "test chưa từng chạy thì assert bên
trong cũng chưa từng được kiểm chứng", không thể chỉ tin nó pass:

1. Đổi thông điệp log trong `interactive_shell.py` thành `"MUTATED — test phai bat duoc"`.
2. Chạy test → **FAILED** ✅ (đúng như phải thế).
3. Khôi phục nguyên bản → **PASSED**, `git diff` file nguồn sạch.

→ Chứng minh test thật sự đi tới nhánh `except`, gọi `logger.exception`, và assert đúng
nội dung — không phải pass vì may.

**Không có ca thứ hai**: `grep` toàn `tests/` + `src/` chỉ ra đúng 1 chỗ. Giả thuyết ban
đầu ("agent sinh 1 đợt thì có thể sai nhiều chỗ") **không đúng** — ghi lại để khỏi đi tìm
lại.

⚠️ **Suite chưa xanh hoàn toàn, nhưng vì lý do khác và mới hơn**: commit `d49c656`
(*"Refactor UI components in BackTestTradeLogs and DevBoardPanel"*) làm đỏ **3 test khác**
— không liên quan task này, đã tách sang
[`BOT-083`](BOT-083_qml_onclicked_moved_into_nested_mousearea.md).

## 5. Rủi ro / Lưu ý

- Sau khi sửa, test có thể **fail vì lý do khác** (phần assert chưa bao giờ chạy). Nếu vậy
  thì sửa cho đúng, **đừng** `skip` hay xoá — quay lại đúng vấn đề ban đầu.
- Cân nhắc (không bắt buộc trong task này): bật `--strict-markers`, hoặc thêm bước CI chặn
  merge khi suite đỏ. Nếu đã có mà vẫn lọt thì đáng tìm hiểu vì sao.

## 6. Phụ thuộc

- Không phụ thuộc gì. Sửa 1 dòng trong `Sagittarius_Elite_Warrior/tests/` → commit
  submodule + bump pointer.
