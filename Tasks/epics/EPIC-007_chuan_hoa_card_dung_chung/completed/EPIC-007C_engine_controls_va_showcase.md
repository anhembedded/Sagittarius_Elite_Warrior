# EPIC-007C — Engine: control lá + showcase + coverage guard

**Thuộc:** [`EPIC-007`](../README.md) · **Repo:** `Sagittarius_Engine` · **Trạng thái:** ✅ Xong — 2026-08-25
**Phụ thuộc:** `007B` — đã xong

---

## Phạm vi

Ba control lá bị lặp nhiều nhất, cộng phần showcase mà `guards.py` **tự ghi nhận là còn
thiếu** (*"No coverage-guard counterpart yet ... no QtWidgets showcase/preview exists yet"*).

| Lớp mới | File | Kế thừa | Instance thật |
| :--- | :--- | :--- | ---: |
| `StyledLabel` (abstract) | `widgets/controls/styled_label.py` | `QLabel` | gốc của 2 lớp dưới |
| `SectionLabel` | `widgets/controls/section_label.py` | `StyledLabel` | 3 |
| `Badge` | `widgets/controls/badge.py` | `StyledLabel` | 4 |
| `StyledProgressBar` | `widgets/controls/styled_progress_bar.py` | `QProgressBar` | 2 |

## Bốn chỗ lệch khỏi đề bài

**1. `controls.py` phải thành package.** Task đặt lớp mới ở `widgets/controls/<tên>.py`, mà
`controls.py` là **module** — Python không cho tồn tại đồng thời `controls.py` và `controls/`.
Nên 4 lớp sẵn có cũng tách thành 4 file, đúng luật "1 file 1 lớp" §3.4. Đây là hệ quả bắt
buộc của chính đề bài, không phải mở rộng phạm vi.

**2. `StyledProgressBar` có 1 instance, không phải 2.** Grep toàn `src/`: đúng một
`QProgressBar` (`AppProgressBarWidget`). Và nó **wrap**, không kế thừa — một `QWidget` chứa
caption `QLabel` **phía trên** một bar. Cả 3 call site chỉ dùng `set_status_text`, **không ai
gọi `set_value`/`set_range`**. Nên lớp mới là *cái bar* (leaf control thật); phần composite
"caption trên bar" là một **surface**, 1 instance, ghi làm ứng viên.

**3. Tick của `SectionLabel` mặc định TẮT.** Đề bài ngầm hiểu mọi section label đều có tick.
Đo thật: **1/3**. Hai cái kia (`_section_label`, `TIMELINE COVERAGE`) là `QLabel` muted trơn.
Bật mặc định là cho chúng thêm một chi tiết thị giác chưa từng có. Nên tick là `tick=True`
opt-in, và có role riêng `SECTION_LABEL_TICKED`.

**4. `Badge` phủ 2 mô hình màu, không phải 1.** 7 instance thật chia hai nhóm: *chrome*
(count log, badge tab, badge interval — màu palette cố định, cặp idle/current) và *semantic*
(long/short, lãi/lỗ, delta — app truyền hex xanh/đỏ thô rồi tự chế nền bằng alpha). Nhóm hai
**không cần API nhận hex**: cả ba thực chất chỉ hỏi tích cực/tiêu cực/trung tính, nên
`set_tone(Tone)` trả lời bằng token. Nhận hex sẽ đẩy app quay lại tự `setStyleSheet` — đúng
thứ `find_inline_stylesheets` sinh ra để chặn.

## Ứng viên ghi lại, không làm ở đây

| Thứ | Vì sao hoãn |
| :--- | :--- |
| `ProgressPanel` (caption trên bar) | 1 instance, và hình dạng là một cột → surface, không phải leaf control |
| Badge có chấm trạng thái | Badge WS của dev board là `QFrame` chứa dot + label; cho `Badge` thêm con là biến label thành container |
| `_section_header` của backtest modals | Tick nằm **phía sau** (đường HLine), chữ màu accent — một hình dạng khác |
| Tick 3×14 + tiêu đề `TEXT_PRIMARY` 13px | Đó là header panel, không phải section label — 2 instance, ứng viên riêng |

## Yêu cầu

1. **Chuỗi kế thừa thứ 5 và thứ 6, vẫn đơn tuyến.** `QLabel → StyledLabel → {SectionLabel,
   Badge}` và `QProgressBar → StyledProgressBar`. Không đa kế thừa ở đâu — ràng buộc
   PySide6/Shiboken của ADR `EPIC-006` §3 giữ nguyên.
2. `StyledLabel` chỉ được tạo vì **có sẵn 2 lớp con thật ngay lập tức**. Nếu trong lúc làm phát
   hiện `Badge` và `SectionLabel` không dùng chung gì thật → bỏ `StyledLabel`, cho mỗi cái kế
   thừa thẳng `QLabel`. Đừng giữ một tầng trung gian rỗng.
   → **Đã cân nhắc, giữ lại.** Chúng dùng chung một hành vi thật, không chỉ chung constructor:
   cả hai phải **render lại sau khi dựng**, ở một state đổi lúc chạy (badge sang dạng nhấn khi
   tab của nó thành hiện hành; label mờ đi cùng nhóm). Đó là `set_state()`. Nếu sau này có lớp
   con chỉ cần constructor thì nó thuộc về `QLabel` thẳng, không phải tầng này.
3. **`SectionLabel` vẽ dấu tick accent bằng `border-left` trong QSS**, không tạo widget con —
   bản hiện tại của Elite (`dev_board_panel._SectionLabel`) là một `QHBoxLayout` chứa một
   `QFrame` 3×12px. Nếu QSS không cho kết quả thị giác tương đương thì ghi lại và giữ cách cũ;
   **không** im lặng chấp nhận khác biệt.
4. **Showcase**: một app QtWidgets nhỏ ở `tools/widget_showcase/` dựng mọi type trong
   `widgets/`. Đây là thứ thay `kit/gallery_coverage_guard.py` (nhắm QML, sẽ mất referent).
5. **Coverage guard**: test fail nếu có type nào trong `widgets/__all__` không xuất hiện trong
   showcase.

## Bằng chứng

### Gate (Engine, Python 3.12)

```text
ruff check sagittarius_engine tests examples tools        RC=0   All checks passed!
ruff format --check (toàn cây)                            RC=0   432 files
mypy ... --ignore-missing-imports --follow-imports=skip   RC=0
pytest tests/ examples/student_management/tests/ ...      RC=0   1139 passed, 8 skipped
                                                                 coverage 90.30%
pytest tests/test_architecture.py                         RC=0   8 passed
scripts/verify_wheel_importable.py                        RC=0
```

Log: `Sagittarius_Engine/logs/gate-007c-final-092157.log`, grep `FAILED|ERROR|Traceback|SyntaxError`
→ 0 mỗi loại. Trước `007C`: 1103 passed / cov 90.09%.

### Showcase

`python -m tools.widget_showcase` mở gallery; ảnh chụp đã gửi user trong phiên. Nền dùng token
`bg` — lần chụp đầu quên, cửa sổ ăn màu xám sáng mặc định của Qt và chữ muted không đọc nổi.

### Coverage guard chạy thật — đã xoá tạm `Badge` khỏi showcase

```text
E   AssertionError: these widget types are exported but never built by the showcase —
    add them to tools/widget_showcase, or record why they cannot be shown in
    _NOT_SHOWCASEABLE: ['Badge']
E   assert ['Badge'] == []
1 failed, 1 warning in 0.10s
```

Khôi phục xong → `3 passed`. Guard gồm 3 test: coverage thật, danh sách miễn trừ không được
chứa thứ đã hết tồn tại, và một test tự chứng minh guard đỏ khi thiếu type.
