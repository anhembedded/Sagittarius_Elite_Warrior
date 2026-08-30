# Epic EPIC-017 — Presentation Hard-Design Round 2

**Trạng thái:** 🟡 Đang làm — 1/2 task con xong (`017B`). Cập nhật 2026-08-30.
**Nguồn:** Report "6 Hard Design" từ 1 phiên làm việc khác (Windows), verify
độc lập và ratify ở [`DECISION_2026-08-30_hard_design_round2.md`](DECISION_2026-08-30_hard_design_round2.md).

---

## 1. Bối cảnh

Report liệt kê 6 vấn đề "Hard Design". Sau khi verify độc lập bằng code
thật (không tin theo lời report), 6 điểm chia làm 4 nhóm quyết định — xem
ADR để biết chi tiết verify từng điểm:

- **2 điểm mở task ở đây:** D1 (Settings hard-code field 3 màn khác), D3
  (magic string `"1m"` — sửa lại: `TimeFrame` Enum **đã tồn tại**, việc là
  dùng nó chứ không phải tạo mới).
- **1 điểm route sang epic khác, không trùng lặp:** D5 (God Presenters) —
  phần chưa có ai làm (`dashboard_presenter.py`) mở task mới ở
  [`EPIC-003`](../EPIC-003_presenter_and_god_file_decomposition/README.md)
  (`EPIC-003G`), không mở epic mới cho vấn đề `EPIC-003` đã sở hữu.
- **1 điểm scope-corrected, không mở task:** D4 (boilerplate "cả 4
  presenter") — chỉ đúng cho 3/4, phần lõi đã DRY sẵn.
- **2 điểm bị từ chối:** D2 (auto-discovery cho strategy/indicator), D6
  (bỏ Junction hack trong `run-ui.ps1`) — cả 2 đề xuất gốc đi ngược
  convention có chủ đích của repo.

## 2. Task con

| ID | Tên | Rủi ro | Trạng thái |
| :--- | :--- | :---: | :---: |
| **[EPIC-017A](incomplete/EPIC-017A_settings_state_key_ownership_inversion.md)** | Đảo ngược sở hữu state-key — mỗi màn tự khai `bound_config_keys`, bỏ dict cứng trong `SettingsPresenter` | 🟡 | 🔴 Chưa bắt đầu |
| **[EPIC-017B](completed/EPIC-017B_adopt_timeframe_enum.md)** | Dùng `TimeFrame` Enum có sẵn thay literal `"1m"` ở 5 file presentation | 🟢 | ✅ Xong 2026-08-30 — 487 test xanh |

`A` và `B` độc lập, làm song song được.

## 3. Không nằm trong epic này

- God Presenters (`dashboard_presenter.py`, v.v.) — theo dõi ở `EPIC-003`
  (`EPIC-003G`), không lặp lại ở đây.
- Auto-discovery cho strategy/indicator — bị từ chối (ADR D2), không có task.
- Bỏ Junction hack trong `run-ui.ps1` — bị từ chối (ADR D6), không có task.
- Đồng bộ thuật ngữ `"timeframe"` vs `"interval"` giữa các màn — hệ quả phụ
  của `017A`/`017B` nhưng không phải mục tiêu chính; nếu phát sinh, mở task
  riêng sau khi 2 task trên xong, không gộp vào giữa chừng.
