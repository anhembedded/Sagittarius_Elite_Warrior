# EPIC-002A — Đo baseline: `mypy` bắt bao nhiêu lỗi thật trên codebase hiện tại

**Thuộc Epic:** [`EPIC-002`](../README.md)
**Trạng thái:** ✅ **Hoàn thành (2026-08-21)**
**Phụ thuộc:** Không có — làm trước tiên, kết quả quyết định thiết kế của `EPIC-002B`.

**Báo cáo đầy đủ:** [`Tasks/reports/EPIC-002A_mypy_baseline_audit.md`](../../../reports/EPIC-002A_mypy_baseline_audit.md).

**Tóm tắt kết quả:** `src/` 183 lỗi (241 file) — 73% ở `presentation/`, trong đó 52% toàn bộ (`96/183`) là nhiễu hệ thống PySide6 `@Property`, không phải bug thật. `scripts/` 29 lỗi, `tests/` 9 lỗi. Phát hiện kỹ thuật quan trọng: `mypy` chỉ bắt được lỗi lớp `BUG-026` khi chạy `src`+`scripts` **cùng 1 lệnh**, chạy riêng lẻ từng thư mục sẽ báo "Success" giả. Phát hiện 1 defect sống cùng lớp `BUG-026`, chưa từng báo cáo: `scripts/backtest_timeframe_toolbar_e2e.py`'s `_SeededMarketDataRepository` thiếu 7 method — 2 trong số đó do chính `BUG-025` (phiên này) thêm vào mà phạm vi grep audit khi đó bỏ sót `scripts/`. **Đã sửa ngay sau khi `EPIC-002B` xong** — xem [`BUG-027`](../../../bug_report/completed/BUG-027_seeded_market_data_repository_missing_seven_port_methods.md).

---

## 1. Mục tiêu

Trước khi nối `mypy` vào CI, cần biết **thật sự** nó sẽ báo bao nhiêu lỗi
trên codebase hiện tại (chưa từng type-check ngày nào). Không suy đoán —
chạy thật, đếm thật, phân loại thật.

## 2. Việc cần làm

1. Cài `mypy` vào `.venv` của submodule (thêm vào `requirements-dev.txt` nếu
   chưa đúng phiên bản, hoặc xác nhận `mypy==2.1.0` đã khai báo là đủ).
2. Chạy `mypy` ở cấu hình **mặc định, không `--strict`** trên toàn bộ `src/`
   (không chạy trên `tests/`/`scripts/` ở bước đo này — domain/application/
   infrastructure trước, UI/test sau, vì đây là nơi lỗi kiểu dữ liệu có giá
   trị phát hiện cao nhất).
3. Ghi lại kết quả vào `Tasks/reports/` (theo đúng tiền lệ `engine_defect_class_analysis.md`,
   `BUG-009_logging_and_test_gap_case_study.md` đã có sẵn trong repo):
   - Tổng số lỗi, phân theo mã lỗi mypy (`[abstract]`, `[assignment]`,
     `[arg-type]`, `[return-value]`, `[attr-defined]`, ...).
   - Phân theo layer (Domain / Application / Infrastructure / Presentation)
     — layer nào sạch nhất, layer nào bẩn nhất.
   - Liệt kê riêng mọi lỗi thuộc nhóm `[abstract]`/`[override]` (đúng lớp lỗi
     của `BUG-026`) — đây là bằng chứng trực tiếp cho việc "nếu đã có gate từ
     trước, còn bao nhiêu `BUG-026` tương tự đang ẩn trong repo ngay bây giờ".
4. **Không sửa bất kỳ lỗi nào tìm thấy trong task này** — phạm vi chỉ là đo
   và báo cáo. Sửa (nếu cần) thuộc `EPIC-002B`/`EPIC-002D`.

## 3. Kết quả mong đợi

Một con số cụ thể + báo cáo phân loại, để `EPIC-002B` quyết định được:
config `mypy` khởi điểm nên bật/tắt gì, có cần cơ chế baseline-suppression
(ví dụ `mypy-baseline`, hoặc allowlist module) hay không, và phạm vi ban đầu
nên là toàn `src/` hay chỉ một vài module ít lỗi nhất trước.
