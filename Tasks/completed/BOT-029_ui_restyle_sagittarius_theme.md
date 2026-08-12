---
id: "BOT-029"
title: "Nhiệm vụ: UI Restyle — Theme "Sagittarius Elite Warrior""
status: "completed"
---

# Nhiệm vụ: UI Restyle — Theme "Sagittarius Elite Warrior"

## 1. Mục tiêu (Objective)
Đổi giao diện toàn app sang theme đen + gold (bám theo 4 ảnh mockup người dùng cung cấp — bản gốc ghi thương hiệu "AUREUM"), branding thật là **"Sagittarius Elite Warrior"** (không dùng tên "AUREUM" từ mock). Chỉ restyle — **không build tính năng backend mới** cho các phần tử mock có nhưng chưa có logic thật.

## 2. Mô tả (Description)
Xác nhận phạm vi qua 3 câu hỏi làm rõ trước khi lên plan:
- **Chỉ restyle giao diện** (màu/font/branding/layout) — giữ nguyên toàn bộ tính năng hiện có.
- ~~**API & Credentials → QML**, nối tiếp trực tiếp `BOT-028`~~ **[ĐẢO NGƯỢC ở Phase 4 — xem mục 4]**: sau khi dùng thử app thật, QML (`QQuickWidget`) có cảm giác chập/giật hơn rõ rệt so với phần còn lại (QtWidgets) — quyết định bỏ QML, chuyển API & Credentials về QtWidgets thuần, giữ nguyên thiết kế giao diện.
- **Branding**: đổi thật thành "Sagittarius Elite Warrior" (không phải "AUREUM") — đúng theo tên engine thật của dự án (`sagittarius_engine`), nên các label kiểu "ARCH: AUREUM Core" trong mock được đổi thành "ARCH: Sagittarius Core" — không chỉ là reskin, là label đúng sự thật.

**Danh sách cố tình để placeholder / KHÔNG build thật** (để không ai nhầm là bug sau này):
- Balance USDT trên top bar — không có concept ví/tài khoản trong bot. Hiển thị "—" hoặc bỏ hẳn, không hiện số giả.
- Database: nút "Seed 1,000 Records"/"Export JSON"/"Purge Vault" và tab "Bot Execution Orders" — chưa có logic seed/export/purge/order-tracking thật. Hiển thị nhưng **disabled** + tooltip, không giả vờ hoạt động.
- API & Credentials: field IP Whitelist và checkbox Enable Spot/Futures Trading — không map với key nào trong `user_config.json` hiện tại. **Bỏ hẳn khỏi lần này** (không hiển thị) vì phạm vi không thêm field config mới. Chỉ 5 field đã có từ `BOT-028` được restyle, cộng thêm nút eye/eye-off che/hiện API Secret (thuần UI, không đổi backend).
- Nav "Backtest Engine" — tính năng chưa tồn tại (`BOT-021`/`BOT-022` còn backlog). Thêm dạng **disabled** (khớp layout/nhóm của mock) thay vì dead-link.

**Lưu ý quan trọng phát hiện khi làm Phase 1, ảnh hưởng Phase 3:** Bảng trong mock (Database screen) hiển thị **từng dòng nến thô** (Timestamp/OHLCV/Trend, phân trang). Bảng hiện tại của `DatabaseStatusCard` hiển thị **trạng thái tổng hợp theo từng cặp symbol/interval** (Symbol/Interval/First/Last/Total/Status) — 2 khái niệm bảng khác nhau. Đúng phạm vi "chỉ restyle", Phase 3 restyle bảng trạng thái hiện có, **không dựng bảng browse-kline-thô mới** (cần query/pagination riêng, đó là tính năng mới nằm ngoài phạm vi đã chốt).

## 3. Các bước thực hiện (Action Items)
- [x] Phase 1: `qss/style.qss` (palette đen/gold), `chart_card/theme.py` (giữ nguyên, xem ghi chú), icon mới (`eye`, `eye-off`, `search`, `bar-chart-2`), `sidebar.py` (section grouping + brand cluster + disabled entry), `main_window.py` (title, nhãn "API & Credentials", route key giữ `"settings"`).
- [x] Phase 2: Top status bar cho Dev Board (symbol/giá thật từ dữ liệu chart có sẵn, badge WS từ FSM có sẵn, nút Reload — không có balance giả), restyle ChartCard/ControlCard/MonitorCard.
- [x] Phase 3 — **SUPERSEDED bởi `BOT-030`** (không phải abandoned): thiết kế stat tile/search/nút placeholder đã lên plan ở đây được gộp thẳng vào bản QML của `BOT-030` Phase 3 (`DatabaseScreen.qml`) thay vì làm bằng Widgets rồi làm lại lần 2 bằng QML. Xem `Tasks/completed/BOT-030_full_qml_migration.md`.
- [x] Phase 4 (đảo ngược, xem mục 4): **Bỏ QML**, viết lại `settings_view.py`/`settings_presenter.py` thành QtWidgets thuần (BaseCard + QFormLayout, giống hệt mô hình `DataManagementPresenter`/`View`) — vẫn giữ nguyên thiết kế đen/gold (áp tự động qua QSS toàn cục, không cần code riêng), giữ nút eye/eye-off toggle. Xoá `settings_view_model.py`, `settings_screen.qml`. **[Đảo ngược lần 2 ở `BOT-030`]**: Settings quay lại QML sau khi `BOT-030` chứng minh lag cảm nhận ở Phase 4 này là do chưa sửa 2 bug hiệu năng chart (bisect + windowed rendering), không phải do QML — xem `BOT-030` mục 4/Completion Notes.
- [x] Phase 5: đóng task tại đây — toàn bộ scope còn lại (branding/theme/restyle) đã hoàn tất qua Phase 1-2-4, phần UI framework (QML vs Widgets) do `BOT-030` quyết định lại và thực thi trọn vẹn. `ci-local.ps1 -Full` xanh xác nhận trong `BOT-030`.

## 4. Rủi ro / Lưu ý (Constraints & Risks)
- ~~QML (`settings_screen.qml`) hiện hardcode màu riêng, tách biệt khỏi `style.qss`~~ — không còn áp dụng, đã bỏ QML.
- **[Đảo ngược quyết định]** Sau khi Phase 1-2 xong, người dùng dùng thử app thật và thấy màn QML (`QQuickWidget`) chập/giật hơn rõ rệt so với phần còn lại — dù mọi test tự động đều pass (test chỉ xác nhận render đúng, không đo độ mượt tương tác thật). Quyết định bỏ hẳn QML cho bản thật; `BOT-028` được note lại là "kết luận kỹ thuật đúng (coexist được, không cần sửa `pyside_mvc`) nhưng trải nghiệm thực tế không đạt, không áp dụng". Xem ghi chú cập nhật trong `Tasks/completed/BOT-028_qml_hybrid_prototype_spike.md`.
- **[Phát hiện ngoài phạm vi, đã sửa]** Trong lúc test thủ công, phát hiện bug rendering candlestick có sẵn từ trước (không liên quan restyle): `FastCandlestickItem` tính `candle_width` chỉ từ khoảng cách 2 nến đầu tiên, nếu khoảng cách đó bất thường thì toàn bộ nến bị vẽ sai độ rộng (dính chồng lên nhau). Đã sửa sang dùng median toàn bộ khoảng cách + `abs()` phòng dữ liệu đảo ngược, có 2 test hồi quy trong `test_chart_card.py`.
- Mỗi phase có test gate riêng (sanity suite + screenshot thật qua script offscreen), chỉ sang phase sau khi phase trước xanh — theo đúng cách làm đã áp dụng ở `BOT-028`.

## 5. Ghi chú hoàn thành (Completion Notes)
Task này đóng lại với 2 lần "đảo ngược" đáng ghi nhớ, cả 2 đều đã verify bằng dữ liệu thật chứ không phải đoán:
1. **QML → Widgets** (Phase 4 ở đây): quyết định dựa trên cảm nhận lag thật khi dùng thử — đúng tại thời điểm đó vì root cause (2 bug hiệu năng chart) chưa được tìm ra.
2. **Widgets → QML lần 2** (`BOT-030`): sau khi 2 bug hiệu năng chart được sửa dứt điểm (thuần thuật toán, đo được bằng `cProfile`/benchmark, không liên quan framework), quyết định quay lại QML dựa trên lý do khác hẳn — AI dịch mockup sang code trực tiếp hơn ở QML, không phải hiệu năng.

Toàn bộ phạm vi branding/theme "Sagittarius Elite Warrior" của task này (palette đen/gold, icon, section grouping sidebar, đổi tên AUREUM→Sagittarius, ẩn field không map config) đã hoàn tất và được `BOT-030` kế thừa nguyên vẹn qua `ThemeBridge`/`Palette`. Chi tiết đầy đủ về giai đoạn QML cuối cùng: `Tasks/completed/BOT-030_full_qml_migration.md`.
