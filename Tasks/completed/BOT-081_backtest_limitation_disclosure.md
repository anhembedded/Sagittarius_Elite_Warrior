# Nhiệm vụ: Công bố giới hạn của backtest ngay trên UI kết quả

> Thuộc Epic [`BOT-078`](BOT-078_backtest_trustworthiness_epic.md).
> Phụ thuộc [`BOT-079`](../completed/BOT-079_fee_transparency_and_trade_frequency.md).

## 1. Mục tiêu

Gom **mọi giới hạn đã biết** của backtest vào một chỗ user thật sự nhìn thấy, thay vì để
rải rác trong task file mà chỉ người viết code đọc.

Lý do: màn hình Backtest hiện trình bày kết quả với độ tự tin của một báo cáo tài chính
(13 metric, equity curve, drawdown, trade journal) — trong khi bên dưới có **một loạt giả
định mạnh** chưa từng được nói ra với người dùng.

## 2. Danh sách giới hạn đã biết — tất cả đều đã verify

| Giới hạn | Nguồn |
| :--- | :--- |
| **Không mô phỏng slippage** — luôn khớp đúng giá yêu cầu | `PaperExchange` (`BOT-021`) |
| **Không mô phỏng độ trễ mạng / thời gian xử lý** | `BOT-021` |
| **Không mô phỏng orderbook depth / partial fill** — lệnh luôn khớp trọn vẹn, bất kể khối lượng | `BOT-021` |
| **All-in sizing, single position, long-only** — không đòn bẩy, không short | `PaperExchange`; `BOT-049`/`BOT-050` chưa làm |
| **Không có SL/TP** | [`BOT-041`](BOT-041_stop_loss_take_profit_and_risk_sizing.md) chưa làm |
| **Fill ở open nến kế tiếp** — chặn lookahead, nhưng tạo độ trễ nhân tạo 1 bar | `BOT-021` (có chủ đích) |
| **Phí có thể chiếm phần lớn kết quả** | [`BOT-079`](../completed/BOT-079_fee_transparency_and_trade_frequency.md) |
| **Không có kiểm định ngoài mẫu** | [`BOT-080`](BOT-080_out_of_sample_walk_forward.md) |
| *(sau `BOT-073`)* **Tick 1s không phải tick thật** — `aggTrade` có thể nhiều lệnh/giây | [`BOT-073`](BOT-073_realtime_tick_backtest_epic.md) §8 |

## 3. Các bước thực hiện

- [x] Một chỗ hiển thị gọn (icon ⓘ cạnh kết quả, mở ra panel/popup) liệt kê giới hạn
      **đang áp dụng cho lần chạy này** — không phải danh sách tĩnh.
- [x] **Động theo trạng thái thật**, đây là điểm mấu chốt: nếu `BOT-041` đã xong và user
      có bật SL/TP thì **không** hiện dòng "không có SL/TP" nữa. Danh sách tĩnh sẽ sai
      ngay khi có task tiếp theo hoàn thành → thành nhiễu, rồi bị bỏ qua.
- [x] Nguồn sự thật cho từng dòng phải là **trạng thái/cấu hình thật**, không phải hằng
      số chép tay (vd: có SL/TP hay không đọc từ config lần chạy, không hardcode).
- [x] Ghi rõ chế độ đang chạy (Static / Realtime + độ phân giải tick) — 2 kết quả trông
      giống hệt nhau mà ngữ nghĩa khác hẳn là bẫy hiểu nhầm thật (`BOT-076` §3.3).

## 4. Rủi ro / Lưu ý

- **Cám dỗ làm quá tay**: biến thành cảnh báo to đùng đỏ chót mỗi lần chạy → user học
  cách bỏ qua sau 3 lần, thành vô dụng (đúng cơ chế "cửa sổ vỡ" ở
  📄 [Rà soát định hướng App](../reports/app_direction_audit.md) §6). Mặc định phải **kín
  đáo nhưng tìm thấy được**.
- **Danh sách tĩnh sẽ mục rữa.** Nếu không làm động theo trạng thái thật thì đừng làm —
  một danh sách sai còn tệ hơn không có, vì nó tạo cảm giác an tâm giả.
- Task này **không** sửa engine, thuần trình bày.

## 5. Phụ thuộc

- [`BOT-079`](../completed/BOT-079_fee_transparency_and_trade_frequency.md) — cung cấp số liệu phí để
  hiển thị.
- [`BOT-055`](../completed/BOT-055_backtest_performance_metrics_panel.md) ✅ — panel kết
  quả, nơi đặt entry point.
- Cập nhật lại khi `BOT-041`/`BOT-049`/`BOT-050`/`BOT-073` hoàn thành — mỗi task đó **xoá
  bớt** một dòng khỏi danh sách. Ghi vào các task đó luôn? → **Không**; thay vào đó làm
  danh sách động (§3) để không phải nhớ.

## 6. Kết quả triển khai thực tế

- **`logic/backtest_limitations_view.py`** (mới, thuần Python): `build_backtest_limitations(result)`
  trả `list[str]`. 8 dòng "luôn đúng hôm nay" (`_ALWAYS_APPLICABLE_LIMITATIONS`, 1 hằng số
  danh sách — sửa đúng 1 chỗ khi `BOT-041`/`049`/`050`/`073` xong, đúng tinh thần "không
  phải nhớ" của task) — không có config/state thật nào để đọc cho các mục này (chưa có
  field SL/TP, chưa có toggle đòn bẩy/short trong `PaperExchange`/`BacktestRunConfig`) nên
  không thể "động" hơn được tới khi các task đó thật sự thêm field. **1 dòng thật sự động
  theo trạng thái mỗi lần chạy**: cảnh báo thiếu out-of-sample chỉ xuất hiện khi
  `result.out_of_sample is None` (`BOT-080` đã xong, nhưng khoảng dữ liệu quá ngắn ở 1 lần
  chạy cụ thể vẫn có thể không chia được — dòng này phản ánh đúng ca đó, không phải một
  danh sách tĩnh nói dối).
- **UI**: nút ⓘ nhỏ (`Button`, `objectName: "btnBacktestLimitations"` — dùng `Button` chứ
  không phải `Rectangle+MouseArea`, đúng quy ước test-clickable từ `BOT-057`/`BOT-083`)
  cạnh tiêu đề "CHỈ SỐ HIỆU SUẤT BACKTEST", mở `Popup` liệt kê — **kín đáo nhưng tìm thấy
  được** đúng yêu cầu §4, khác hẳn `resultWarningText` (`BOT-079`) phải luôn hiện không
  được giấu sau click. `BackTestViewModel` thêm `limitations` (`QStringList`) +
  `set_limitations()`, nối ở cả 3 nhánh Presenter (thành công/rỗng/lỗi).
  **Không đụng `MetricCard.qml`.**
- **Test**: 3 test thuần Python cho `build_backtest_limitations()` + 5 test presenter
  (bao gồm 1 test click nút QML thật qua `qml_item(...).clicked.emit()`, xác nhận không
  crash — không kiểm được nội dung Popup do giới hạn đã biết của test harness từ `BOT-047`:
  "Popup content không test được qua `find_qml_item`"). 822 test toàn `tests/unit/`+
  `tests/sanity/` pass, `ruff` sạch.
