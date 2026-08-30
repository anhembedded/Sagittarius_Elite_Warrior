# Epic EPIC-019 — Dashboard/Backtest: gộp logic Presenter trùng lặp thành Coordinator dùng chung

**Trạng thái:** 🟡 Đang làm — 1/3 task con (`019A` xong).
**Nguồn:** Báo cáo ngoài (Gemini) claim "màn hình có tính năng chung, không
có lớp cha chung" — verify độc lập, 2/7 claim đúng + 1 finding tự phát
hiện. Ratify ở
[`DECISION_2026-08-30_dashboard_backtest_shared_coordinators.md`](DECISION_2026-08-30_dashboard_backtest_shared_coordinators.md).

---

## 1. Bối cảnh

Sau khi hoàn thành `EPIC-018A`, user đưa một báo cáo audit từ Gemini nhận
định `presentation/ui/screens/` có nhiều tính năng chung nhưng thiếu lớp cha
chung. Báo cáo đó **không được tin theo lời** — verify độc lập từng claim
bằng cách đọc code thật, đúng phương pháp đã dùng cho `EPIC-017`/`EPIC-018`.
Kết quả: 4/7 claim sai hoặc bịa (file/tính năng không tồn tại trong code),
2/7 claim đúng và đáng làm, cộng 1 finding tự phát hiện độc lập với báo cáo.
Chi tiết bảng verify ở ADR.

**Quyết theo phương châm mới** (`architecture-rule.md`, callout đầu file,
user chốt 2026-08-30): best design/pattern đã kiểm chứng, không ngại
redesign, tham chiếu dự án lớn khi phân vân — áp dụng ở đây bằng cách chọn
**Coordinator pattern** (đã có tiền lệ 8+ lần trong chính repo, đúng hướng
`EPIC-003`/`EPIC-013` đã chốt) thay vì base-class Presenter dày mà báo cáo
Gemini đề xuất — hướng đó lặp lại đúng sai lầm `God Presenter` mà 2 epic
kia đã sửa.

## 2. Task con

| ID | Tên | Trạng thái |
| :--- | :--- | :---: |
| **[EPIC-019A](completed/EPIC-019A_symbol_options_coordinator.md)** | `SymbolOptionsCoordinator` dùng chung Dashboard + Backtest (D1) | ✅ Hoàn thành |
| **[EPIC-019B](incomplete/EPIC-019B_health_check_coordinator.md)** | `HealthCheckCoordinator` dùng chung Dashboard + Backtest (D2) | 🔴 Chưa bắt đầu |
| **[EPIC-019C](incomplete/EPIC-019C_qml_property_factory.md)** | Factory cho Qt `Property` boilerplate — thử nghiệm trên `DataManagementViewModel` (D3) | 🔴 Chưa bắt đầu |

## 3. Không nằm trong epic này

- `TradingScreenPresenter`/`TradingScreenViewModel` base class (đề xuất của
  Gemini) — **từ chối**, đi ngược hướng composition-qua-Coordinator đã chốt
  từ `EPIC-003`/`EPIC-013`.
- `SymbolCatalogService` ôm thẳng `ICommandDispatcher` (đề xuất của Gemini)
  — **từ chối**, phá ranh giới FSM/action-ownership phải ở Presenter.
- Nút "Refresh Symbol" / chuỗi 14 mắt xích / `DashboardSymbolPickerSource`
  — **không làm gì**, các claim này không có bằng chứng trong code thật
  (xem ADR §2, dòng 3-4).
- Timeframe picker dùng chung — **đã xong** ở `EPIC-014`/`EPIC-015`, claim
  của Gemini về thiếu dùng chung là sai.
