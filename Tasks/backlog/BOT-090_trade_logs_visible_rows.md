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

- [ ] **Viết test tái hiện trước khi sửa** (đúng quy trình bug-fix của repo,
      [`.agents/rules/code-rule.md`](../../.agents/rules/code-rule.md)): dựng màn với 75
      trade thật ở kích thước cửa sổ mặc định, assert **có ít nhất N dòng thật sự nhìn
      thấy được** (nằm trong vùng hiển thị của pane, không chỉ tồn tại trong cây QML) —
      hiện tại phải **fail**.
- [ ] Sửa `setSizes([600, 200])`: pane Trade Logs phải nhận đủ chỗ cho một số dòng tối
      thiểu dùng được. Chốt lúc code — ưu tiên **tỉ lệ/`minimumHeight` theo nội dung**
      hơn là một cặp số pixel mới (cặp số mới sẽ sai lại ở độ phân giải khác).
- [ ] Cân nhắc `PAGE_SIZE` động theo chiều cao khả dụng thay vì cố định 20 (20 dòng ×
      44px sẽ **không bao giờ** vừa ở cửa sổ thấp). Nếu chọn cố định thì phải có scroll
      hoạt động thật trong pane.
- [ ] Xác nhận `ListView` trong pane cuộn được khi vẫn thiếu chỗ — fallback bắt buộc,
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
