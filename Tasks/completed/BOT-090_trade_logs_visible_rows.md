# Nhiệm vụ: Trade Logs hiển thị được dòng — hiện đang trống hoàn toàn

> Thuộc Epic [`BOT-086`](BOT-086_ui_layout_and_overlay_architecture_epic.md), **Track B**,
> task 2/2. Phụ thuộc [`BOT-089`](BOT-089_content_driven_panel_sizing.md).
> Nguồn: 📄 [`BUG-004`](../bug_report/BUG-004.md).

## 1. Vấn đề — mất tính năng hoàn toàn, không phải xấu

Ảnh `BUG-004` cho thấy bảng Trade Logs hiện đủ header (`STT / THỜI GIAN`, `LOẠI`,
`GIÁ VÀO / THOÁT`, …), đủ tab lọc, đủ phân trang **"75 Lệnh · Trang 1 / 4"** — nhưng
**không một dòng lệnh nào** được vẽ.

Tính từ code:

- [`trade_log_pagination.py`](../../src/presentation/ui/screens/backtest/logic/trade_log_pagination.py): `PAGE_SIZE = 20`
- [`BackTestTradeLogs.qml`](../../src/presentation/ui/screens/backtest/BackTestTradeLogs.qml): mỗi dòng `implicitHeight: 44`
- → riêng phần rows cần **20 × 44 = 880px**, chưa kể header + tab lọc + phân trang
- [`backtest_view.py`](../../src/presentation/ui/screens/backtest/backtest_view.py): `main_splitter.setSizes([600, 200])` → pane này được **200px**

→ 880px nội dung nhồi vào 200px. Toàn bộ 20 dòng bị đẩy ra ngoài vùng nhìn thấy.
`BOT-057` (bảng Trade Logs) và `BOT-045` (dòng chi tiết mở rộng) **đang không dùng được**
ở kích thước cửa sổ mặc định, dù code của chúng đúng.

## 2. Các bước thực hiện

- [x] **Viết test tái hiện trước khi sửa** (đúng quy trình bug-fix của repo,
      [`.agents/rules/code-rule.md`](../../.agents/rules/code-rule.md)): dựng màn với 75
      trade thật ở kích thước cửa sổ mặc định, assert **có ít nhất N dòng thật sự nhìn
      thấy được** (nằm trong vùng hiển thị của pane, không chỉ tồn tại trong cây QML) —
      hiện tại phải **fail**.
- [x] Sửa `setSizes([600, 200])`: pane Trade Logs phải nhận đủ chỗ cho một số dòng tối
      thiểu dùng được. Chốt lúc code — ưu tiên **tỉ lệ/`minimumHeight` theo nội dung**
      hơn là một cặp số pixel mới (cặp số mới sẽ sai lại ở độ phân giải khác).
- [x] Cân nhắc `PAGE_SIZE` động theo chiều cao khả dụng thay vì cố định 20 (20 dòng ×
      44px sẽ **không bao giờ** vừa ở cửa sổ thấp). Nếu chọn cố định thì phải có scroll
      hoạt động thật trong pane. → **Chốt: giữ `PAGE_SIZE=20` cố định** — xem §5.
- [x] Xác nhận `ListView` trong pane cuộn được khi vẫn thiếu chỗ — fallback bắt buộc,
      không được để lặp lại tình trạng "nội dung tồn tại nhưng không ai thấy".

## 3. Rủi ro / Lưu ý

- **Không sửa bằng cách giảm `PAGE_SIZE` xuống 3-4 dòng cho vừa 200px.** Bảng 4 dòng cho
  75 lệnh là làm hỏng tính năng theo cách khác. Vấn đề là *pane quá nhỏ*, không phải
  *trang quá nhiều dòng*.
- Splitter cho user kéo tay được — nhưng **mặc định phải dùng được ngay**, không thể yêu
  cầu user kéo mới thấy dữ liệu.
- Task này **không** sửa modal bị cắt (Track A) và **không** sửa panel trên
  (`BOT-089`) — chỉ pane dưới.

## 4. Phụ thuộc

- [`BOT-089`](BOT-089_content_driven_panel_sizing.md) — nên xong trước: panel trên hết ép
  `setFixedHeight` thì chỗ còn lại cho splitter mới tính đúng được.
- Liên quan: [`BOT-057`](../completed/BOT-057_backtest_trade_logs_table.md) (bảng),
  [`BOT-045`](../completed/BOT-045_trade_journal_detail_and_metadata.md) (dòng chi tiết) —
  2 task này **không sai**, chỉ đang bị layout che mất.
- Chỉ sửa `Sagittarius_Elite_Warrior/src/` → commit submodule + bump pointer.

## 5. Kết quả triển khai thực tế

- **`BackTestTradeLogs.qml`**: bỏ `implicitHeight: 300` khai cứng ở root (không dùng tới
  — resizeMode của widget luôn là `SizeRootObjectToView`, giá trị này chưa từng có tác
  dụng thật). Thêm 3 property mới ở root, theo đúng nguyên tắc "1 nguồn sự thật" của
  `BOT-089`:
  - `rowHeight: 44` — dùng chung bởi delegate thật (`implicitHeight: root.rowHeight`
    thay vì literal `44`) và công thức tính minimum, không thể lệch nhau.
  - `minVisibleRows: 5` — **quyết định UX có chủ đích**, không phải "đo lại nội dung
    thật" như card của `BOT-089`: 1 trang có thể tới `PAGE_SIZE=20` dòng, `ListView` vốn
    là `Flickable` không có 1 "chiều cao tự nhiên" duy nhất để đo — 5 dòng là ngưỡng
    "dùng được ngay", phần còn lại cuộn.
  - `minimumUsableHeight` — tổng `panelMargin*2 + toolbarRow.implicitHeight +
    outerColumn.spacing + tableHeaderRow.Layout.preferredHeight + minVisibleRows*rowHeight
    + paginationRow.Layout.preferredHeight`. Luôn cộng cả hàng phân trang dù có thể đang
    ẩn (`tradeLogTotalPages <= 1`) — tránh minimum nhảy số tuỳ kết quả backtest.
- **`backtest_view.py`**: `_bind_trade_log_minimum_height()` mới (mirror
  `_bind_top_panel_height()` từ `BOT-089`) — đọc `minimumUsableHeight`, gọi
  `bottom_widget.setMinimumHeight()`, nối `minimumUsableHeightChanged` để tự cập nhật.
  **Khác `_bind_top_panel_height()` ở điểm cốt lõi**: dùng `setMinimumHeight()` (sàn, user
  vẫn kéo to hơn được qua splitter) chứ không phải `setFixedHeight()` (panel trên không
  có gì tranh chỗ nên cố định được; panel dưới nằm trong `QSplitter` chia sẻ chỗ với
  chart). `setSizes([600, 200])` → `[500, 350]` — chỉ là gợi ý khởi tạo cho đỡ giật hình
  lúc mở app, `setMinimumHeight()` mới là cơ chế thật sự chặn splitter kéo pane xuống
  dưới mức dùng được (đo thật: splitter tự nâng 200→352px ngay khi có minimum, không cần
  đổi `setSizes` tí nào — vẫn đổi cho nhất quán, tránh cú nhảy hình nhìn thấy được).
- **Quyết định `PAGE_SIZE`**: giữ nguyên **cố định 20**, không làm động theo chiều cao —
  `ListView` vốn đã là `Flickable`, cuộn được ngay khi có đủ nội dung + chiều cao khả
  dụng dương; làm `PAGE_SIZE` động sẽ phải tính lại số trang mỗi khi resize cửa sổ, rủi ro
  cao hơn nhiều so với lợi ích, và ngoài phạm vi thật của bug (bug là "pane quá nhỏ", không
  phải "trang quá nhiều dòng" — task tự cảnh báo đúng điều này ở §3).
- **Verify bằng ảnh chụp UI thật** (không chỉ test offscreen): dựng `BackTestView` với 20
  dòng/75 lệnh, chụp `view.grab()` — xác nhận **5 dòng hiện đầy đủ** cùng header/tab lọc/
  phân trang, đúng ý đồ `minVisibleRows: 5`.
- **Test**: 2 test mới trong `test_backtest_view_layout.py` (dùng chung file với
  `BOT-089`, cùng phạm vi "BackTestView layout"): minimum được tôn trọng, và dòng thứ 5
  nằm trong vùng nhìn thấy được — đo toạ độ **tuyệt đối** qua `mapToItem()`, đúng cạm bẫy
  `card.y` cục bộ mà `BOT-089` đã gặp. Cả 2 verify bằng mutation test (bỏ
  `_bind_trade_log_minimum_height()` → cả 2 đỏ → khôi phục → xanh lại). 827 test toàn
  `tests/unit/`+`tests/sanity/` pass, `ruff` sạch, ổn định qua nhiều lần chạy lặp lại kể
  cả kết hợp với suite Backtest presenter đầy đủ.
