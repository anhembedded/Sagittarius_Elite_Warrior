# EPIC-012F — Chọn View từ config lúc bootstrap, có kiểu đại diện

**Trạng thái:** ✅ Xong 2026-08-27
**Repo:** Elite
**Phụ thuộc:** `B`

## Yêu cầu gốc

User, 2026-08-27: *"ko thay view runtime, cho load view tu config luc
bootstrap"*.

## Trước / sau

```python
# trước — main_window.py
self._router.register("backtest", BackTestPresenter, lambda: BackTestView())

# sau
config = self._app.context.container.resolve(IConfig)
self._router.register("backtest", BackTestPresenter,
                      lambda: build_backtest_view(config))
```

Hai thứ ngầm đã được đặt tên:

1. **Lựa chọn View** — trước là sửa code, giờ là `ConfigKeys.BACKTEST_VIEW`
   (`"backtest.view"`), giá trị là thành viên của `BacktestViewKey`.
2. **Kiểu trả về** — lambda cũ **không có kiểu**, nên không gì nói router được
   phép làm gì với thứ nó nhận. `build_backtest_view()` khai trả về
   `IBacktestView` (`012B`).

## File mới `screens/backtest/view_factory.py`

| Ký hiệu | Vai trò |
| :--- | :--- |
| `BacktestViewKey` | Enum các View app biết dựng. Hôm nay đúng **1** member: `QT_WIDGETS` |
| `DEFAULT_BACKTEST_VIEW_KEY` | Hằng có tên cho trường hợp config im lặng |
| `_BUILDERS: dict[BacktestViewKey, Callable[[], IBacktestView]]` | Bảng, không phải chuỗi `if` — thêm View là **một dòng**, và `resolve` validate ngay trên bảng đó nên không có danh sách thứ hai để lệch |
| `resolve_backtest_view_key(config)` | Key đã cấu hình, hoặc default **kèm `warning`** |
| `build_backtest_view(config)` | Dựng, và **log một dòng** View nào đã dựng |

Dòng log đó là bằng chứng **duy nhất** có được khi một bug report mô tả màn
hình mà máy dev không tái hiện được — `logging-rule.md` §3.

Giá trị sai (`"qml"` chẳng hạn) **không** làm chết boot: một cái typo trong
`user_config.json` không được lấy mất cả app. Nhưng cũng **không im lặng** —
§2 yêu cầu nhánh degrade phải nói nó chọn gì và vì sao.

## Đã cố ý KHÔNG làm

**Không** dựng hệ plugin. Hôm nay mỗi route có đúng 1 View; phạm vi đúng là
*một lựa chọn có tên, đọc từ config, trả về một kiểu đã khai*. Repo này có tiền
lệ thật cho việc làm quá: 4 stub card `ActionCard`/`FormCard`/`StreamCard`/
`TableCard` suy ra từ docstring, **0 instance thật** (`EPIC-006` ADR §4). Thêm
key thứ hai là vài dòng, **khi** có View thứ hai thật.

**Không** đụng 3 route còn lại (`dashboard`, `data_management`, `settings`).
Chúng có cùng hình dạng, nhưng task này của màn Backtest; sửa hàng loạt là mở
rộng phạm vi không ai yêu cầu.

## Verify — bơm lỗi

Đổi `_BUILDERS[QT_WIDGETS]` từ `BackTestView` sang `object` →
**`test_every_buildable_view_satisfies_the_declared_contract` đỏ**, 4 test còn
lại xanh. Khôi phục → 5/5 xanh.

Test đó lặp trên **cả enum**, không gọi tên một member: một View được thêm vào
`BacktestViewKey` mà không thoả `IBacktestView` sẽ đỏ ở đây — và đây là **cơ
chế duy nhất** bắt được, vì `presentation/` nằm ngoài cổng `mypy`.

`_Config` trong test là class thật chứ **không** phải `MagicMock`: mock trả
`Mock` cho mọi key, nên một factory đọc **sai key config** vẫn trông như chạy
đúng.

## Nghiệm thu

- `pwsh -NoProfile -File scripts/ci-local.ps1 -Full` → `RESULT: PASS`, log quét
  sạch `FAILED|ERROR|Traceback|ResourceWarning`.
