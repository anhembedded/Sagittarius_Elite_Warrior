# BOT-120: Màn Backtest phụ thuộc màn Dashboard cho 3 thứ phi-UI

**Trạng thái:** ✅ Xong 2026-08-25

## 1. Bối cảnh & vấn đề thật

Phát hiện 2026-08-25 khi `EPIC-007E` dựng guard chặn import chéo giữa các gói
`screens/*`. Guard tìm được **6** vi phạm; 3 cái là widget và đã bị cắt trong
chính epic đó. **Ba cái còn lại không phải widget**, nên nằm ngoài phạm vi một
epic về chuẩn hoá card — chúng được cho vào danh sách miễn trừ của guard, trỏ
tới file này:

| Nơi | Lấy gì từ `dashboard` |
| :--- | :--- |
| `screens/backtest/backtest_presenter.py:98` | `IndicatorScriptRunner`, `qualified_line_name` |
| `screens/backtest/backtest_presenter.py:102` | `map_klines`, `map_volume` |
| `screens/backtest/backtest_view_model.py:29` | `IndicatorScriptListModel` |

Không có cái nào thuộc về màn Dashboard. Chúng ở đó vì Dashboard là nơi chúng
được viết ra trước.

## 2. Vì sao đáng sửa

Ba import này nói rằng **Backtest không chạy được nếu không có Dashboard**.
Điều đó không đúng về mặt nghiệp vụ: chạy chỉ báo trên một chuỗi nến và ánh xạ
nến sang dạng vẽ được là việc của cả hai màn, không của riêng màn nào.

Hệ quả cụ thể, không phải lý thuyết:

- Xoá hoặc đổi tên màn Dashboard sẽ làm hỏng màn Backtest, và không có gì
  trong tên file nói lên điều đó.
- Guard mới của `EPIC-007E` phải mang một danh sách miễn trừ 3 dòng. Miễn trừ
  không có hạn dùng thì thành vĩnh viễn.
- `qualified_line_name` và `map_klines` là hàm thuần — chúng không có lý do gì
  để sống trong một gói màn hình.

## 3. Đề xuất

Chuyển cả ba lên tầng dùng chung. Chỗ tự nhiên là `presentation/ui/components/`
(nếu còn dính Qt) hoặc `application/` (nếu thuần logic) — cần đọc mới quyết
được, đừng chốt trước:

- `map_klines`/`map_volume` gần như chắc chắn là hàm thuần chuyển đổi dữ liệu.
- `IndicatorScriptRunner`/`IndicatorScriptListModel` cần kiểm xem có phụ thuộc
  Qt không (`ListModel` thì gần như chắc là có).

Xong thì **xoá 3 dòng miễn trừ** khỏi
`tests/unit/presentation/ui/test_no_cross_screen_imports.py` — đó là tín hiệu
task này hoàn tất.

## 4. Ngoài phạm vi

Ba import widget mà `EPIC-007E` đã cắt. Chúng đã xong.

## 5. Kết quả — 2026-08-25

Cả ba chuyển lên `presentation/ui/components/`, đúng tiêu chí đã đọc trước khi
chốt (§3 của task này):

| Từ (`screens/dashboard/`) | Đến | Vì sao |
| :--- | :--- | :--- |
| `kline_mapping.py` (`map_klines`/`map_volume`) | `components/chart_card/kline_mapping.py` | Hàm thuần, nhưng docstring của chính nó ghi rõ đích là `FastCandlestickItem`/`VolumeItem` — cả hai sống trong `chart_card/`. Không phải business logic trung lập, mà là bước chuyển đổi cho đúng widget chart này. |
| `indicator_script_runner.py` → `runner.py`, `script_region_tracker.py` → `region_tracker.py` | `components/indicator_scripts/` (gói mới) | Không import Qt trực tiếp, nhưng thao tác thẳng lên một `card` (gọi `card.add_overlay_indicator(...)` v.v.) — từ vựng đó là của tầng trình bày, không phải nghiệp vụ thuần. Tên/hành vi mang nghiệp vụ (chỉ báo, kịch bản) + ≥2 màn dùng → đúng tier `components/` theo khung 3 tầng của `EPIC-007`. |
| `indicator_script_list_model.py` → `list_model.py` | `components/indicator_scripts/` | `QAbstractListModel` — chắc chắn phụ thuộc Qt như dự đoán trong §3. |

**Không gộp chung một gói** `chart_card`/`indicator_scripts` dù cả hai đều
"vẽ lên chart": `indicator_script_runner.py` tự định nghĩa `MarkerPoint` với
đúng shape `chart_card/marker_lod.py` đã có sẵn — nhét runner vào thẳng gói
`chart_card` sẽ tạo hai `MarkerPoint` cùng tên khác nghĩa trong cùng một gói.
Trùng lặp kiểu này đã tồn tại từ trước (không phải BOT-120 sinh ra), ghi lại
đây làm ứng viên dọn dẹp sau, **không sửa trong task này** — ngoài phạm vi.

**Phát hiện phụ, sửa luôn vì đang sửa đúng file đó:** docstring của
`IndicatorScriptListModel` nói sai — nhắc tới `DevBoardPanel.qml` và một
`Repeater` delegate mà `EPIC-006` đã xoá từ lâu. Cùng lớp BUG với
`BUG-004`/`BUG-001` bên Engine (docstring nhắc tới thứ không tồn tại) nhưng
không đáng file riêng vì sửa 1 dòng, cùng chỗ đang đổi import.

**Guard đã đóng đúng như thiết kế:** `_ALLOWED` trong
`test_no_cross_screen_imports.py` rỗng — không xoá biến, giữ khung để một
miễn trừ tương lai có chỗ ghi lại (comment giải thích vì sao giữ).

**Kiểm tra:** `ruff check`/`ruff format --check` sạch trên toàn bộ file đổi,
`mypy` không tăng lỗi (giữ nguyên baseline 247 lỗi có sẵn, không liên quan —
đã xác nhận bằng `git stash` chạy lại trên commit gốc). Suite đầy đủ:
`1807 passed, 4 skipped` (một lần chạy dính 1 test đỏ không liên quan,
`test_macd_produces_no_series_with_too_little_history`, xanh khi chạy riêng
và xanh lại ở lần chạy toàn bộ tiếp theo — flake phụ thuộc thứ tự suite,
cùng loại với `BUG-006`, không phải regression của task này).

**Tác dụng phụ tìm thấy khi chạy full suite — sửa luôn:** 4 test đỏ **có sẵn
từ trước** task này (`git stash` xác nhận đỏ y hệt trên commit gốc):
`test_shutdown_database_sync_process.py` (3 case) và
`test_shutdown_sync_process.py`. Nguyên nhân: hai probe script
(`scripts/shutdown_sync_probe.py`, `scripts/shutdown_database_sync_probe.py`)
tự dựng bootstrap riêng thay vì dùng `app_bootstrapper.py`, và vẫn gọi
`configure_app_qml(...)` — cách nạp `get_theme_bridge()` từ thời còn QML.
`EPIC-006F` đã bỏ QML hoàn toàn và đổi `app_bootstrapper.py` sang gọi thẳng
`get_theme_bridge(Palette.as_ui_dict())`, nhưng hai probe này không được cập
nhật theo. Sửa cả hai theo đúng mẫu `app_bootstrapper.py` đang dùng — cả 4
test giờ xanh.
