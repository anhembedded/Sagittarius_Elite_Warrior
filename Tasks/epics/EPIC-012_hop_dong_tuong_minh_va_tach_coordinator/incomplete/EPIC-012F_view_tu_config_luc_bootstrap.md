# EPIC-012F — Chọn View từ config lúc bootstrap, có kiểu đại diện

**Trạng thái:** ⬜ Chưa làm
**Repo:** Elite
**Phụ thuộc:** `B` (`IBacktestView` là kiểu mà factory phải trả về)

## Yêu cầu gốc

User, 2026-08-27: *"ko thay view runtime, cho load view tu config luc
bootstrap"*.

## Hiện trạng

`main_window.py::_setup_router()` đăng ký 4 màn bằng lambda ghi cứng class:

```python
self._router.register("backtest", BackTestPresenter, lambda: BackTestView())
```

Nghĩa là: View **đã** được chọn lúc bootstrap (đúng ý user), nhưng lựa chọn đó
**ghi cứng trong code**, không đọc từ config, và **không có kiểu nào** nói lambda
đó phải trả về cái gì.

## Việc

1. Một **kiểu factory tường minh** cho mỗi route — `Callable[[], IBacktestView]`
   thay cho `lambda: BackTestView()` không kiểu. Đây chính là §2.1: thứ đi qua
   ranh giới phải có kiểu.
2. Đọc lựa chọn View từ **config** (`config_keys.py` / `user_config.json`), với
   default là hành vi hiện tại. Không được ghi cứng chuỗi tên class rải rác —
   theo `code-quality-rule.md` "No Magic Numbers & Named Constants".
3. **Ghi vào docstring của điểm đăng ký**: lựa chọn này là *bootstrap-time*, và
   Presenter **không** phải chịu được việc bị tráo View giữa chừng. Theo §7 của
   `architecture-rule.md` ("code phải tự nói lên chính nó"), quyết định này phải
   nằm trong **kiểu + test**, không chỉ trong prose.

## Cẩn thận: đây là điểm rất dễ overengineer

Hôm nay mỗi route có **đúng 1** View. Task này **không** phải là dựng một hệ
plugin. Phạm vi đúng là: *lựa chọn có tên, đọc từ config, trả về một kiểu đã
khai báo*. Repo này đã có tiền lệ thật về việc đoán sai hình dạng của thứ chưa
tồn tại — 4 stub card `ActionCard`/`FormCard`/`StreamCard`/`TableCard` suy ra từ
docstring, 0 instance thật (`EPIC-006` ADR §4). Luật "luôn khuyến khích
abstraction" (§7.2) khuyến khích **thiết kế API cho cái đang viết**, không
khuyến khích đoán trước cái chưa ai cần.

## Nghiệm thu

- `pwsh -NoProfile -File scripts/ci-local.ps1 -Full` → `RESULT: PASS`.
- Có test: config trỏ tới một View khác → bootstrap dựng đúng View đó;
  config thiếu/sai → fallback về mặc định **và** ghi log, không nổ.
- `mypy` đỏ khi factory trả về kiểu không thoả `IBacktestView`.
