# EPIC-013G — `TimeFrame.M1` không tồn tại: nhánh fallback tự nó ném `AttributeError`

**Trạng thái:** ✅ Xong 2026-08-27
**Repo:** Elite
**Phụ thuộc:** không

## Lỗi (nguyên trạng trước khi sửa)

`backtest_presenter.py`:

```python
try:
    tf = TimeFrame(timeframe_str)
except ValueError:
    tf = TimeFrame.M1        # TimeFrame không có thành viên M1
```

`TimeFrame` khai `ONE_MINUTE = "1m"`. **Không có `M1`.** Nhánh cứu lỗi **thay
một lỗi xử lý được bằng một lỗi không xử lý được**.

Có từ `e071c8d` (2026-08-22) — **trước** toàn bộ `EPIC-003E`/`EPIC-013`. Không
test nào phủ, `ruff` không thấy (thành viên `Enum` là attribute động dưới mắt
linter), `mypy` không chạy ở `presentation/`.

## Đã sửa

File mới `logic/timeframe_parsing.py`:

- `FALLBACK_TIMEFRAME = TimeFrame.ONE_MINUTE` — hằng **có tên**, chọn
  `ONE_MINUTE` vì `BackTestViewModel` vốn đã khởi động ở đó
  (`DEFAULT_TIMEFRAMES[0]`), nên giá trị cứu được **khớp với thứ toolbar đang
  hiển thị**.
- `timeframe_or_fallback(raw)` — parse, hoặc trả fallback **kèm
  `logger.warning`**. Theo `logging-rule.md` §2: một giá trị tới được đây mà
  không parse nghĩa là ViewModel đang giữ thứ **không picker nào tạo ra được**
  (`user_config.json` sửa tay, hoặc `ui_state` khôi phục từ bản build có danh
  sách timeframe khác). Đó là tín hiệu state hỏng, không được nuốt im lặng.

**Tách thành file riêng mới là thứ làm nó test được.** Nằm trong
`BackTestPresenter` thì muốn chạm vào nhánh này phải dựng cả presenter.

## Hai call site còn lại KHÔNG dùng hàm này — cố ý

`_build_run_config` gọi `TimeFrame(view_model.selectedTimeframe)` **không có
try** ở 2 chỗ. Giữ nguyên: dựng config cho một run thật là **đường validate**,
timeframe không dùng được thì phải **ném**, không được lặng lẽ hoá thành thứ
khác. Hai chính sách khác nhau, có chủ đích — không phải chỗ bỏ sót.

## Verify — bơm lại đúng lỗi cũ

Đổi `FALLBACK_TIMEFRAME` về `TimeFrame.M1` → **lỗi ngay ở bước collect** của
pytest (`AttributeError` lúc import module).

Đây là một cải thiện cấu trúc, không chỉ một bản vá: hằng ở **module level**
nghĩa là cùng lớp lỗi đó **không còn nấp được trong một nhánh hiếm khi chạy**
nữa — nó nổ lúc import, mỗi lần, cho mọi người. Đó chính là §7 của
`architecture-rule.md`: đưa quyết định ra chỗ code **tự nói lên chính nó**.

Khôi phục → 14/14 xanh.

## 14 test mới

- 6 giá trị hợp lệ đi qua nguyên vẹn — trong đó có **cả `"1M"` (tháng) và
  `"1m"` (phút)**: chúng chỉ khác nhau ở chữ hoa/thường và **cả hai đều tồn
  tại**, nên một fallback lỡ `lower()` sẽ âm thầm biến backtest theo tháng
  thành theo phút.
- 5 giá trị hỏng đều rơi về fallback thay vì ném — gồm `"M1"`, đúng chuỗi mà
  code hỏng đã đặt tên.
- 1 test khoá `FALLBACK_TIMEFRAME` phải là thành viên thật của enum.
- 2 test khoá log: hỏng thì **có** WARNING, hợp lệ thì **không** — nếu thiếu
  vế sau, dòng warning mất giá trị làm bằng chứng.

## Nghiệm thu

- `pwsh -NoProfile -File scripts/ci-local.ps1 -Full` → `RESULT: PASS`, log quét
  sạch `FAILED|ERROR|Traceback|ResourceWarning`.
