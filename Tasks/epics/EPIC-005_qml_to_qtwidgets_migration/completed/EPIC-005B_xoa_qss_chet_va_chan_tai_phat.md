# EPIC-005B — `style.qss` chết, không phải chép tay — xoá + chặn tái phát

**Thuộc Epic:** [`EPIC-005`](../README.md)
**Trạng thái:** ✅ Xong (2026-08-23)
**Phụ thuộc:** Không — có lợi kể cả khi toàn bộ EPIC-005 bị huỷ

---

## 0. Premise ban đầu sai — sửa lại trước khi làm

Task này lúc đầu định "sinh QSS từ `Palette`" vì docstring cũ của `palette.py` nói
`style.qss` "still hardcodes its own literal hex values... keeping it in sync... is a
manual step". **Kiểm tra thật trước khi code phát hiện premise đó sai:**

- `git log -- qss/style.qss` dừng ở `e6aef8e "BOT-030 — full QML migration"` — không ai sửa
  từ đó.
- Grep `\.qss` toàn bộ `src/` (kể cả 2 worktree khác đang tồn tại): **không có nơi nào load
  file này**. `app_bootstrapper.py:_apply_theme` dùng `qdarktheme.load_stylesheet("dark")`,
  chỉ thay đúng 1 màu accent bằng string-replace — không đụng `style.qss` bao giờ.
- Repo có sẵn `tests/unit/presentation/ui/test_qss_selectors_are_alive.py`, một guard test
  cho `style.qss` — nhưng nó chỉ kiểm tính nhất quán *nội bộ* của file (selector ↔
  objectName), không chứng minh file có được nạp hay không. Chính docstring của nó thừa
  nhận: ra đời để bắt rules chết dần *khi màn hình chuyển QML* — tức bản thân guard cũng là
  tàn dư từ giữa đợt BOT-030, không ai cập nhật khi cả file hoá chết hẳn.

**Kết luận: không có QSS thật để "sinh".** Việc đúng là xoá file chết + guard test của nó,
và sửa đúng 1 chỗ trùng lặp thật đang tồn tại.

## 1. Đã làm

1. Xoá `src/presentation/ui/qss/style.qss` (183 dòng, mồ côi) và
   `tests/unit/presentation/ui/test_qss_selectors_are_alive.py` (guard cho file đã chết).
2. `app_bootstrapper.py:_apply_theme` — fallback accent đổi từ literal `"#F3BA2F"` sang
   `Palette.ACCENT`. Đây là **chỗ trùng lặp thật duy nhất** trong pipeline theme đang chạy.
3. Viết `tests/unit/presentation/ui/test_palette_is_the_only_color_source.py`:
   - Test tĩnh quét `src/presentation/ui/` tìm hex literal trùng giá trị `Palette` — bắt
     đúng loại lỗi vừa sửa nếu tái phát.
   - Test hành vi: `_apply_theme` không config override phải hỏi `qdarktheme` đúng
     `Palette.ACCENT`, không phải literal độc lập.
4. Cập nhật docstring `palette.py` cho khớp thực tế (không còn nhắc `style.qss`).

## 2. Phạm vi guard — thu hẹp sau khi chạy thật lộ 2 lớp false positive

Bản đầu quét *toàn bộ* `src/`, cho ra 14 "offender" — nhưng phần lớn không phải bug:

- **`src/domain/indicator_scripts/*`, `strategies/*`** (9 hit): màu vẽ đường chỉ báo kỹ
  thuật trên chart (EMA, MACD...), chọn độc lập với UI theme — trùng giá trị hex với
  `Palette` là tình cờ, không phải quên import. Guard thu hẹp còn `presentation/ui/` only.
- **`components/chart_card/theme.py`** (1 hit, `TAKE_PROFIT_COLOR`): file tự ghi rõ trong
  docstring — *"this package doesn't import the app's global Palette (kept
  portable/standalone), so the value is duplicated here rather than imported"*. Trùng lặp
  **có chủ ý, có văn bản**, không phải bug. Loại trừ tường minh khỏi guard bằng
  `_EXEMPT_DIRS`, không phải bằng cách nới lỏng regex.

**3 chỗ còn lại là bug thật, đã sửa:**

| File | Trước | Sau |
| :--- | :--- | :--- |
| `main_window.py:76` | `"background-color: #0a0a0c; color: #e8e9ec;"` | `f"...{Palette.BG}...{Palette.TEXT_PRIMARY}..."` |
| `dashboard_presenter.py:81-82` | `"#848E9C"`, `"#F3BA2F"` trong `_WS_STATUS_BY_MODE` | `Palette.MUTED`, `Palette.ACCENT` |
| `dashboard_view_model.py:14` | `_IDLE_STATUS_COLOR = "#848E9C"` | `Palette.MUTED` |

Đáng chú ý: `dashboard_presenter.py` đã import `BULL_COLOR`/`BEAR_COLOR` từ
`chart_card.theme` cho 2 trạng thái kia trong cùng dict — tức tác giả **đã** trộn 2 nguồn
màu trong cùng một chỗ mà không nhận ra.

## 3. Xác minh

`pwsh -NoProfile -File scripts/ci-local.ps1 -Full` — `RESULT: PASS`, xác minh qua log file
(`FAILED`/`ResourceWarning`/`Traceback` — không có). `1790 passed / 54 sanity`.

## 4. Bài học cho các task con sau (D trở đi)

Guard "so hex với Palette" **chỉ đúng phạm vi trong `presentation/ui/`**. Nếu `EPIC-005D`
trở đi cần thêm exemption tương tự `chart_card/` (một package cố tình độc lập), thêm vào
`_EXEMPT_DIRS` kèm lý do bằng văn bản — đừng nới regex hay xoá test.
