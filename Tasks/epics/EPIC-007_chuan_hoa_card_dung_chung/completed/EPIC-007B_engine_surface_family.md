# EPIC-007B — Engine: 6 hình dạng surface dùng chung, mỗi lớp một file

**Thuộc:** [`EPIC-007`](../README.md) · **Repo:** `Sagittarius_Engine` · **Trạng thái:** ✅ Xong — 2026-08-25
**Phụ thuộc:** `007A` (guard phải bắt đúng trước) — đã xong

> Code + commit ở repo **Engine**. Riêng task này có **một thay đổi bắt buộc bên Elite**
> (`Palette.WARNING`), lý do ở §"Token `warning`" bên dưới — hai commit này phải đi cùng nhau.

---

## Phạm vi

Sáu hình dạng đang bị Elite viết lại 2–5 lần. Mỗi cái đều thoả kỷ luật ADR `EPIC-006` §4:
**≥2 instance thật đang tồn tại**, không suy đoán.

| Lớp mới | File | Kế thừa | Instance thật hiện có |
| :--- | :--- | :--- | ---: |
| `LogPanel` | `widgets/surfaces/log_panel.py` | `Card` | 3 |
| `StatCard` | `widgets/surfaces/stat_card.py` | `Card` | 2 |
| `TableCard` | `widgets/surfaces/table_card.py` | `Card` | 3 |
| `DataRow` | `widgets/surfaces/data_row.py` | `Panel` | 4 |
| `Banner` | `widgets/surfaces/banner.py` | `Panel` | 5 |
| `TabBar` | `widgets/surfaces/tab_bar.py` | `Panel` | 2 |

Instance thật tương ứng, để người review đối chiếu:

- **LogPanel** — `data_management_widgets.LogPanelWidget`, dùng bởi DataMgmt + DevBoard +
  BackTestTradeLogsPanel.
- **StatCard** — `backtest_widgets.MetricCardWidget` + `data_management_view._build_stat_tile()`.
- **TableCard** — header cột + hàng + phân trang: `BackTestTradeLogsPanel`,
  `KLineInspectorDialog`, `GapInspectorDialog`.
- **DataRow** — `_TradeLogRowWidget`, `_StatusRowWidget`, `_KLineRowWidget`, `_GapRowWidget`.
- **Banner** — 4 banner của `backtest_top_panel` (`progress`/`preview`/`stale`/`coverage`) +
  `_build_audit_banner` của DataMgmt.
- **TabBar** — `DynamicTabBarWidget` + hàng `_FilterTabButton`.

## Yêu cầu

1. **1 file 1 lớp.** Không dồn vào `surface.py`. `surface.py` giữ nguyên `Surface`/`Panel`/
   `Card`/`SelectableCard` — chúng là gốc phân loại, đã ở đúng chỗ.
2. **`StyleRole` mới đặt trong `style.py`**, không tách file: `BADGE`, `BANNER_INFO`,
   `BANNER_WARN`, `BANNER_DANGER`, `SECTION_LABEL`, `TABLE_HEADER`, `PROGRESS`. Đây là ngoại lệ
   có chủ đích của luật "1 file 1 lớp" — `StyleRole` và `_build_qss()` là **cùng một vòng đời**,
   tách ra vi phạm Single-Scope Cohesion (`code-rule.md`).
3. **Không lớp nào biết Elite tồn tại.** Không có tên nghiệp vụ (`Trade`, `Kline`, `Symbol`,
   `Backtest`) trong bất kỳ file nào của `widgets/`.
4. **`TableCard` — trả lời trước câu hỏi chắc chắn bị hỏi:** tên này trùng 1 trong 4 stub QML
   đã bị xoá ở `EPIC-006`. Khác biệt phải ghi ngay trong docstring: 4 stub đó suy đoán từ một
   docstring và có **0 instance**; cái này có **3 instance thật** cùng contract. Nếu review
   thấy vẫn gợn, đổi tên thành `ListCard` — không đổi thiết kế.
5. **Không hex literal ngoài `style.py`** — guard `find_inline_stylesheets` phải xanh.
6. Test cho từng lớp, đặt gương với cấu trúc package (`tests/extensions/pyside_mvc/widgets/surfaces/`).

## Bằng chứng

Gate (Engine, Python 3.12) — `pwsh` không có trên môi trường Linux này, nên chạy đúng 5 bước
`ci-local.ps1` truyền, cộng bước wheel guard mà `49c941b` thêm:

```text
ruff check sagittarius_engine tests examples tools        RC=0   All checks passed!
ruff format --check (toàn cây)                            RC=0   418 files
mypy ... --ignore-missing-imports --follow-imports=skip   RC=0
pytest tests/ examples/student_management/tests/ ...      RC=0   1103 passed, 8 skipped
                                                                 coverage 90.09%
pytest tests/test_architecture.py                         RC=0   8 passed
scripts/verify_wheel_importable.py                        RC=0   190 shipped modules
```

Log: `Sagittarius_Engine/logs/gate-007b-final-085242.log`, grep `FAILED|ERROR|Traceback|SyntaxError`
→ 0 mỗi loại. Trước `007B`: 1004 passed / 183 module. Test tăng 99, module tăng 7.

Elite: `1694 passed` (`tests/unit/`), sau khi sửa nốt 4 hex `#d97706` — xem §Token bên dưới.

### Instance thật cho từng lớp

| Lớp | Instance thật |
| :--- | :--- |
| `LogPanel` | `data_management_widgets.py:156` (`LogPanelWidget`), dùng ở `data_management_view.py:776`, `dev_board_panel.py:119`, `backtest_trade_logs_panel.py:311` |
| `StatCard` | `backtest_widgets.py:46` (`MetricCardWidget`, gọi ở `backtest_top_panel.py:646` + `backtest_modals.py:242`); `data_management_view.py:579` (`_build_stat_tile`, gọi 2 lần ở `:557`) |
| `TableCard` | `backtest_trade_logs_panel.py:289`, `data_management_widgets.py:547`, `:934`, và `data_management_view.py:707` (card DATABASE STATUS — cái thứ tư task chưa đếm) |
| `DataRow` | `data_management_view.py:85`, `data_management_widgets.py:465`, `:848` |
| `Banner` | `backtest_top_panel.py:320`, `:346`, `:377`, `data_management_widgets.py:633` |
| `TabBar` | `backtest_widgets.py:213` (`DynamicTabBarWidget`), `backtest_trade_logs_panel.py:61` (`_FilterTabButton` + hàng ở `:344`) |

## Bốn chỗ đã lệch khỏi đề bài, đều có chủ ý

**1. `TableCard` — phân trang có tham số, theo quyết định của user.** Đo thật thì 3 bảng làm
3 kiểu: trade log có prev/next + nhãn; candle inspector có `«‹›»` + 4 nút cỡ trang + nhãn
đếm; gap inspector **không phân trang**. Ba cách lưu hàng cũng khác nhau (layout + stretch,
`setIndexWidget`, layout + list Python). Giải: `Pagination.NONE/SIMPLE/FULL`, và `TableCard`
**không sở hữu số trang** — nó phát `page_requested`/`page_size_requested`, consumer quyết
rồi đẩy lại bằng `set_page()`. Phần lưu hàng để nguyên cho consumer; card chỉ nhận widget.

**2. `DataRow` bỏ `_TradeLogRowWidget`, theo quyết định của user** — và đây đúng chỗ §Rủi ro
của task bảo phải dừng. Nó không phải bản rộng hơn của 3 cái kia: nó **là** một `QPushButton`,
3/6 cột xếp 2 dòng chữ khác kiểu, 2 ô là badge đổi màu, nó có pane chi tiết bung ra 3 cột nữa,
và nó phát `Signal(int)`. Nhét vừa sẽ cần factory widget cho từng ô + hook pane + signal click
— lúc đó base chẳng còn gì mà subclass không override.

**3. Banner bỏ cái progress.** Thân nó là một progress bar, không có ô icon, không có text
riêng, nút của nó đổi nhãn giữa "Hủy" và "Đang hủy...". Chung với 4 cái kia đúng mỗi "panel bo
góc ẩn cho đến khi cần". Ghi làm ứng viên `ProgressBanner`.

**4. Marker `base-exempt` dùng lần thứ hai.** `_TabButton(QPushButton)` mang
`# base-exempt: a tab is a button, not a surface`. Đây là ca thật đầu tiên ngoài `BaseView`
mà cơ chế của `007A` phục vụ.

## Token `warning` — thay đổi phá vỡ, lan sang Elite

`BANNER_WARN` mà §2 yêu cầu **không có màu nào để dùng**: engine chỉ có 10 colour token bắt
buộc, không có warning; và 2 banner thật đang hardcode `#2a1c07`/`#d97706`/`#fbbf24`. Màu hổ
phách đó không phải `accent` (vàng Binance) cũng không phải `danger` (đỏ) — banner `preview`
ngay cạnh dùng `accent`, gộp lại thì "cảnh báo" và "thông tin" trông y hệt nhau.

User chốt: **thêm `warning` vào `REQUIRED_COLOUR_TOKENS`**. Hệ quả bắt buộc:

- Engine: `vocabulary.py` + 3 palette (conftest test, sample app, gallery snapshot).
- **Elite: `Palette.WARNING = "#d97706"` + `as_ui_dict()`.** Thiếu là **app chết lúc bootstrap**
  vì engine validate token bắt buộc.
- Elite: 4 hex `#d97706` trong `backtest_top_panel.py` phải trỏ về `Palette.WARNING` — không
  phải dọn dẹp tuỳ hứng: guard `test_palette_is_the_only_color_source` của Elite **báo đỏ ngay**,
  vì promote một hex lên palette thì mọi bản chép tay của nó thành "bản sao thứ hai". Pixel
  không đổi.

⚠️ **Hai commit phải đi cùng nhau khi push.** Push Engine mà bỏ Elite → Elite chết. Ngược lại
thì an toàn (Elite thừa 1 token, engine cũ không quan tâm).

## Ứng viên ghi lại, không làm ở đây

| Thứ | Vì sao hoãn |
| :--- | :--- |
| `ProgressBanner` | Xem §3 trên |
| `LogPanel` auto-scroll | Kit QML cũ có (`autoScroll` + chốt "chỉ bám nếu đang ở đáy"), bản QtWidgets làm mất. Khôi phục là **đổi thứ user nhìn thấy**, thuộc task migrate có thể review/revert, không lén qua base class |
| `StatCard` co chữ 18→16px khi giá trị dài >10 ký tự | Sửa usability thật, nhưng cần token cỡ chữ mới biểu diễn được mà không dùng literal |
| `_TradeLogRowWidget` | Xem §2 trên |
| Cột stretch trùng lặp bên Elite | `[22,10,28,28,18,22,26]` chép ở cả `_StatusRowWidget.__init__` lẫn header `data_management_view.py:748`; `Column` đã có sẵn để gộp — việc của `007F` |
| `_make_label(_weight)` bên Elite | Tham số float không ai đọc, sót từ thời port QML — việc của `007G` |

## Rủi ro (bản gốc, đã kiểm)

`DataRow` là cái dễ vượt phạm vi nhất — 4 instance thật có số cột và kiểu ô khác nhau. Giữ nó
ở mức "hàng có ô + hàng nút hành động", đừng cố mô hình hoá cột. Nếu phải thêm tham số thứ 4
để chiều một instance thì dừng lại: đó là dấu hiệu cái này chưa phải một hình dạng chung.

→ **Đã xảy ra đúng như dự đoán, và đã dừng.** Xem §2.
