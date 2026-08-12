---
id: "BOT-015"
title: "📋 BOT-015: Đánh giá & Chuẩn hóa Quy trình Quản lý Chất lượng (QA & Testing Strategy Audit)"
status: "completed"
---

# 📋 BOT-015: Đánh giá & Chuẩn hóa Quy trình Quản lý Chất lượng (QA & Testing Strategy Audit)

> [!IMPORTANT]
> **Độ ưu tiên:** 🟡 P1.5  
> **Trạng thái:** ✅ Completed (một phần — xem Ghi chú hoàn thành)  
> **Lớp liên quan:** Toàn bộ dự án (`Binace_Bot/tests/`, CI/CD Script `ci-local.ps1`)  

---

## 1. 🎯 Mục tiêu (Objective)

Đánh giá toàn diện quy trình kiểm thử hiện tại của dự án, loại bỏ các test case lỗi thời/thừa thãi, bổ sung các tầng kiểm thử còn thiếu (Sanity Tests, Smoke Tests, Dynamic Import Tests) và chuẩn hóa cấu hình CI/CD local script (`ci-local.ps1`).

---

## 2. 📝 Báo cáo Phân tích Chi tiết (Audit Report)

Báo cáo phân tích chuyên sâu:  
📄 **[Báo cáo Audit QA & Testing Strategy](../reports/qa_testing_strategy_report.md)**

---

## 3. 🛠️ Các bước Thực hiện (Action Items)

### Phase 1: Rà soát & Dọn dẹp Test Suite Hiện tại (Audit & Cleanup)
- [x] Rà soát lại toàn bộ 92+ test cases trong `Binace_Bot/tests/` — theo báo cáo đã có, không phát hiện test case lỗi thời cần loại bỏ.
- [x] Tách biệt rõ ràng cấu trúc thư mục test: `tests/unit/`, `tests/integration/` đã có sẵn; bổ sung `tests/sanity/` mới.

### Phase 2: Bổ sung các Loại Test Case Cần thiết (New Test Suites)
- [x] **Sanity / Smoke Tests (`tests/sanity/`):**
  - Di chuyển `test_circular_imports.py` từ `tests/unit/presentation/ui/` sang `tests/sanity/`.
  - Thêm `test_bootstrapper_di_sanity.py`: boot `create_app()` thật (không mock dispatch) và verify `IDispatcher`, `IEventBus`, `IThreadManager`, `IConfig`, `ITaskManager` đều resolve.
- [ ] **Concurrency & Thread Safety Tests** — *chưa làm*, xem Ghi chú hoàn thành.

### Phase 3: Tối ưu hóa CI/CD Local Script (`ci-local.ps1`)
- [x] Bổ sung cờ `-SanityOnly` (chỉ `tests/sanity`, bỏ qua lint, không coverage), `-UnitOnly` (chỉ `tests/unit`, bỏ qua lint, không ép ngưỡng coverage), `-Full` (alias tường minh cho hành vi mặc định: lint + toàn bộ test + coverage gate).
- [x] Cấu hình `--cov-fail-under=80` cho lần chạy mặc định/`-Full` (coverage hiện tại 87.91% — an toàn, không phá CI hiện có).
- [x] Đặt bộ **Testing Standards & Guidelines** vào `.agents/rules/testing.md` — mở rộng rule đã có sẵn (từ phiên trước, về "khi nào cần thêm test") với 4 quy tắc Qt/UI cụ thể: No Silent Swallowing, Strict Qt Cleanup (`qtbot.addWidget`), Explicit Assertions cho async/signal, No `time.sleep()`.

---

## 4. Ghi chú hoàn thành (Completion Notes)

- **Phát hiện thật khi viết `test_bootstrapper_di_sanity.py`:** bản nháp đầu tự dựng `App(container, event_bus)` + `BinanceBotModule()` thủ công (thiếu `ThreadManagerExtension`) — fail ngay ở `IThreadManager` vì extension đó chỉ được đăng ký trong `main.py::create_app()`, không phải trong `BinanceBotModule`. Sửa lại test dùng đúng `create_app()` thật thay vì tự dựng App rút gọn — đúng tinh thần một sanity test: nó tự bắt lỗi thiết kế test của chính nó trước khi bắt được lỗi thật.
- **Chưa làm — hoãn có chủ đích:** *Concurrency & Thread Safety Tests* (đảm bảo `IThreadManager` giải phóng thread sạch khi đóng app). Cần cách đo thread leak (vd so sánh `threading.enumerate()` trước/sau `app.stop()`) mà chưa có pattern sẵn nào trong test suite để tái dùng — cần thiết kế riêng, không phải việc "thêm nhanh" trong lượt này.
- Verify: `scripts/ci-local.ps1` — mặc định (128 test, coverage 87.91%), `-SanityOnly` (6 test, ~6s), `-UnitOnly` (103 test, coverage không ép ngưỡng) đều đã chạy thử thành công.
