# Epic EPIC-003 — Phân rã Presenter/File quá tải (God Object/God File Decomposition)

**Trạng thái:** 🟡 Đang làm — 15/17 xong, **1 huỷ** (`003D`). `003F` (vòng thiết kế) đã chốt hướng C;
**cả 5 lát cắt của nó đã xong** (`003F1`…`003F5`, 2026-09-02 → 2026-09-07) và nhóm cuối ("UI lặt
vặt") đã kết luận **không tách** — xem [`EPIC-003F5`](completed/EPIC-003F5_run_progress_and_result_sub_view_models_facade.md) §4.
`003F` **đã xong hoàn toàn**: bước cuối ở §4.3 của nó — **gỡ facade** —
[`EPIC-003F6`](completed/EPIC-003F6_go_facade_backtest_view_model.md) đóng 2026-09-07 sau 7 phase.
`backtest_view_model.py` **1.435 → 689 dòng**, 0 thuộc tính chuyển tiếp. Số điểm đọc đo lại là
**524**, không phải 344 — con số cũ đã trôi qua 5 lát cắt. Cập nhật 2026-09-07.
**Nguồn:** [`PRO-001`](../../proposal/PRO-001.md) (Coordinator Pattern cho Presenter),
[`PRO-002`](../../proposal/PRO-002.md) (khảo sát toàn bộ file quá tải trong `src/`) —
2 đề xuất do một phiên làm việc khác viết, được đối chiếu lại với quy tắc đã
có sẵn của dự án trước khi chấp nhận (xem §2).

> **Ghi chú 2026-09-22 (review độc lập PR #256):** `backtest_presenter.py` (1.833→1.913 dòng,
> +80 từ 2 slot `_ask_report_export_path`/`_on_report_export_requested` của `BOT-115B`) và
> `backtest_top_panel.py` (726→746 dòng, +20 cho nút "Save report") tiếp tục phình sau khi
> `003E`/`003F` đã xong — không có guard test nào chặn, gate vẫn xanh, nhưng mỗi tính năng mới
> trên màn Backtest lại trả thêm dòng cho đúng 2 file epic này đang tìm cách rút gọn. Chưa mở
> task con mới cho việc này — chỉ ghi lại để `003` không lặng lẽ mất đất đã lấy lại được trong
> lúc tạm dừng.

---

## 1. Bối Cảnh

`PRO-002` khảo sát 8 file vượt ngưỡng review trong `src/`. Đo lại tại thời
điểm lập epic này (21/08) — **số dòng còn lớn hơn báo cáo gốc**, do code mới
thêm vào từ lúc `PRO-002` được viết:

| File | `PRO-002` ghi | Thực tế 21/08 | Lớp kiến trúc |
| :--- | ---: | ---: | :--- |
| `backtest_presenter.py` | 2,523 | **2,722** | Presentation |
| `backtest_view_model.py` | 1,113 | **1,350** | Presentation |
| `DatabaseScreen.qml` | 893 | **993** | QML View |
| `data_management_presenter.py` | 732 | **919** | Presentation |
| `BackTestTopPanel.qml` | 724 | **823** | QML View |
| `StrategyPropertiesModal.qml` | 696 | **766** | QML View |
| `paper_exchange.py` | 603 | **662** | Domain |
| `cached_frame_interaction.py` | 574 | **631** | Presentation |

Vấn đề gốc là thật, không phải số liệu bịa.

---

## 2. Đối Chiếu Với Quy Tắc Đã Có — 2 Mâu Thuẫn Đã Xử Lý Trước Khi Lập Epic

Trước khi chấp nhận Coordinator Pattern, đã tìm ra 2 chỗ đề xuất gốc mâu
thuẫn với quy tắc **có sẵn từ trước** của dự án — cả hai đã được giải quyết
bằng cách **cập nhật `.agents/rules/code-rule.md`** (không lặng lẽ bỏ qua,
không tự ý làm theo đề xuất gốc mà không đối chiếu):

### 2a. "MVP Trio Screen Directory Layout" chỉ cho phép "helper module"

Rule cũ: `<name>_presenter.py` nằm phẳng, chỉ được tách **helper module**
(hàm thuần, không giữ state) vào `<name>/logic/`. `coordinators/` mà
`PRO-001` đề xuất là loại khác hẳn — mỗi Coordinator tự giữ
`thread_manager`/`dispatcher` và tự submit background job, không phải hàm
thuần.

**Giải quyết:** `code-rule.md` §3 giờ sanction rõ ràng `coordinators/` là
1 danh mục riêng, tách biệt `logic/`/`helpers/` — được phép giữ state và tự
submit việc nền, với 1 ràng buộc bắt buộc (xem 2b).

### 2b. Cơ chế "Async UI Action Ownership & Cancellation" đang sống tập trung

Đọc thật `backtest_presenter.py` xác nhận: `_next_action_id`,
`_active_action`, `_is_current_action`, `_finish_action`,
`_invalidate_active_action`, `BacktestActionKind`/`BacktestActionOutcome` —
toàn bộ cơ chế action-id/generation fencing (≈150 dòng) là **tự viết riêng
cho presenter này**, không phải primitive dùng chung. Tách thành 5-6
Coordinator độc lập mà mỗi cái tự cài lại cơ chế này là đúng lớp lỗi
`BUG-018` đã gặp: nhiều nguồn sự thật có thể lệch nhau âm thầm.

**Giải quyết:** `code-rule.md` §3 giờ bắt buộc: Coordinator **không được**
tự giữ FSM hay tự cài action-ownership riêng — cơ chế đó có đúng 1 chủ sở
hữu (Presenter, hoặc 1 tracker dùng chung do Presenter cấp phát). `EPIC-003A`
dưới đây là bước bắt buộc làm **trước tiên**, đúng vì lý do này.

---

## 3. Đánh Giá Rủi Ro Từng Phần Đề Xuất (khác nhau nhiều, không nên gộp 1 mức độ)

| Phần | Rủi ro | Lý do |
| :--- | :---: | :--- |
| `PaperExchange` → Policy (Domain) | 🟢 Thấp | Thuần Domain, không đụng QML/PySide6, có sẵn 47+ test bảo vệ. |
| Dọn vị trí sai chỗ + tách QML lớn thành component | 🟢 Thấp | Đúng tiền lệ đã có (`ModalDialogCard.qml`), không đổi kiểu dữ liệu binding. 8/17 file trong `components/` thực ra chỉ dùng bởi Backtest — vi phạm rule "Component File Structure" đã có sẵn trong `qml-rule.md`. |
| `DataManagementPresenter` → Coordinator | 🟡 Trung bình | File nhỏ hơn, chưa có cơ chế action-ownership riêng phức tạp — pilot hợp lý. |
| `BacktestPresenter` → Coordinator | 🔴 Cao | File lớn nhất, đã có cơ chế action-ownership bespoke phức tạp nhất — chỉ làm sau khi pilot ở trên chứng minh được pattern. |
| `BacktestViewModel` → Composite ViewModel | 🔴 Cao nhất | Mọi `.qml` đang bind `viewModel.xxx` trực tiếp phải đổi cách bind — blast radius lớn hơn hẳn 4 việc trên, đúng lớp lỗi binding đã gặp (`BUG-018`, `BUG-019`). **Chưa greenlight** — cần 1 vòng thiết kế riêng trước khi bắt đầu, xem `EPIC-003F`. |

`qml-rule.md` cũng lưu ý rõ: 300 dòng là **ngưỡng review, không phải lỗi vi
phạm cứng** — *"không tách layout mạch lạc chỉ để đạt con số"*. Mọi task
tách QML dưới đây phải nêu **rõ N trách nhiệm bị trộn**, không chỉ dẫn số
dòng.

---

## 4. Task Con

| ID | Tên | Rủi ro | Trạng thái |
| :--- | :--- | :---: | :---: |
| **[EPIC-003A](completed/EPIC-003A_shared_action_ownership_tracker.md)** | Trích xuất cơ chế Action-Ownership dùng chung | 🟡 | ✅ Xong (21/08) — 172 test pass, `mypy`/`ruff` sạch |
| **[EPIC-003B](completed/EPIC-003B_data_management_coordinator_pilot.md)** | `DataManagementPresenter` → Coordinator Pattern (pilot) | 🟡 | ✅ Xong (21/08) — 57 test pass, `mypy`/`ruff` sạch |
| **[EPIC-003B2](completed/EPIC-003B2_data_management_ui_mode_transitions.md)** | 12 `add_transition` trong `__init__` → bảng `logic/ui_mode_transitions.py` | 🟢 | ✅ Xong (07/09) — 874→857 dòng, **`tests/` diff rỗng**, +6 test |
| **[EPIC-003C](completed/EPIC-003C_paper_exchange_policy_split.md)** | `PaperExchange` → Domain Policy (Margin/Matching/Fee) | 🟢 | ✅ Xong (22/08) — 119 test pass, `mypy`/`ruff` sạch |
| **[EPIC-003D](cancelled/EPIC-003D_qml_component_split.md)** | Dọn 9 file misplaced (Phase 1) + tách 3 file QML lớn (Phase 2) + danh mục `components/README.md` có test enforce (Phase 3) | 🟢 | ❌ **HUỶ 2026-08-25** — Phase 1+2 hết đối tượng (`EPIC-006F` xoá sạch `.qml`); Phase 3 gộp vào `EPIC-007G` |
| **[EPIC-003E](completed/EPIC-003E_backtest_presenter_coordinator.md)** | `BacktestPresenter` → Coordinator Pattern | 🔴 | ✅ Xong 2026-08-26 — 6 coordinator, 2.803 → 2.135 dòng |
| **[EPIC-003E2](completed/EPIC-003E2_run_config_builder_logic.md)** | `_build_run_config` (107 dòng) + `_get_current_config` (36) → `logic/run_config_builder.py`, hàm thuần trả về `RunConfigOutcome` | 🟡 | ✅ Xong (07/09) — 1.966→1.828 dòng, **`tests/` diff rỗng**, +15 test |
| **[EPIC-003E3](completed/EPIC-003E3_backtest_screen_config.md)** | 5 lần đọc `IConfig` rải rác trong `__init__` → `logic/backtest_screen_config.py`; tìm ra lỗ `int(True)==1` ở fetch-limit | 🟢 | ✅ Xong (07/09) — 1.828→1.776 dòng, `__init__` 272→237, **`tests/` diff rỗng**, +10 test |
| **[EPIC-003F](completed/EPIC-003F_backtest_viewmodel_composite_design_review.md)** | `BackTestViewModel` → Composite ViewModel — **vòng thiết kế trước**, chưa code | 🔴 | ✅ Xong (07/09) — 6 task con `F1`…`F6`, kể cả bước gỡ facade ở §4.3. Xem [`DOCTOR-002`](../../completed/DOCTOR-002_epic_003f_blocker_is_dead.md) |
| **[EPIC-003F1](completed/EPIC-003F1_trade_log_sub_view_model_facade.md)** | Lát cắt đầu tiên của `003F`: `TradeLogViewModel` + facade chuyển tiếp (6 property / 6 signal) | 🟡 | ✅ Xong (02/09) — `backtest_view_model.py` 1.435→1.426 dòng, `tests/` diff rỗng tuyệt đối, mutation-verify đã làm thật |
| **[EPIC-003F2](completed/EPIC-003F2_strategy_params_sub_view_model_facade.md)** | Lát cắt 2 của `003F`: `StrategyParamsViewModel` + facade (6 property / 5 signal / `step_bot_param_value`) | 🟡 | ✅ Xong (07/09) — 1.426→1.417 dòng, **`tests/` diff rỗng tuyệt đối**, CI 3.639 passed. Phạm vi thu hẹp có lý do: 2 signal `open*Requested` ở lại khối 10 signal "mở modal" |
| **[EPIC-003F3](completed/EPIC-003F3_time_range_sub_view_model_facade.md)** | Lát cắt 3: `TimeRangeViewModel` + facade (8 property / 4 signal / 1 slot, kèm 2 bảng option) | 🟡 | ✅ Xong (07/09) — 1.417→1.405 dòng, **`tests/` diff rỗng**, +12 test mới |
| **[EPIC-003F4](completed/EPIC-003F4_broker_sim_sub_view_model_facade.md)** | Lát cắt 4: `BrokerSimViewModel` + facade (12 property / 12 signal / 10 slot); clamp và mặc định thành hằng số có tên | 🟡 | ✅ Xong (07/09) — 1.405→1.379 dòng, **`tests/` diff rỗng**, +10 test mới |
| **[EPIC-003F5](completed/EPIC-003F5_run_progress_and_result_sub_view_models_facade.md)** | Lát cắt 5: `RunProgressViewModel` + `RunResultViewModel` + facade. Kết luận nhóm cuối: **không tách** | 🟡 | ✅ Xong (07/09) — 1.379→1.351 dòng, **`tests/` diff rỗng**, +15 test mới |
| **[EPIC-003F6](completed/EPIC-003F6_go_facade_backtest_view_model.md)** | **Gỡ facade** — bước cuối của `003F`. Task duy nhất được phép sửa test (524 điểm đọc), nên có luật riêng: chỉ đổi đường dẫn thuộc tính, không đổi assert; 4 ngoại lệ có ghi rõ | 🔴 | ✅ Xong (07/09) — 7 phase, **1.351→689 dòng**, 0 thuộc tính chuyển tiếp, 3 file test facade xoá vì hết đối tượng |
| **[EPIC-003G](completed/EPIC-003G_dashboard_presenter_coordinator.md)** | `DashboardPresenter` → trích `IndicatorCoordinator` (fetch-limit + script dispatch) | 🟢 | ✅ Xong 2026-08-30 — 1.158→1.134 dòng, 13 test coordinator riêng, 787 test tổng xanh |
| **[EPIC-003G2](completed/EPIC-003G2_dashboard_chart_zoom_limits.md)** | `DashboardPresenter` → `logic/chart_zoom_limits.py`; xoá 2 bản sao của giới hạn zoom + 2 import trong thân hàm | 🟢 | ✅ Xong (07/09) — 1.222→1.207 dòng, **`tests/` diff rỗng**, +3 test |

> ### ❌ `EPIC-003D` đã huỷ (2026-08-25, user duyệt)
>
> Phase 1+2 của nó thao tác trên file `.qml`; `EPIC-006F` đã xoá sạch 22 file `.qml` cuối cùng
> nên **không còn gì để dời hay tách**. Phase 3 (danh mục `components/README.md` có test enforce)
> vẫn còn giá trị — `components/README.md` chưa tồn tại — nhưng phải áp cho file `.py`, và
> `EPIC-007G` cũng đụng `components/` nên gộp vào đó thay vì mở task riêng.

**Thứ tự phụ thuộc:** `A` chặn `B` và `E` (không Coordinator nào được cài
action-ownership riêng trước khi có tracker dùng chung). `C` và `D` độc lập
hoàn toàn, làm bất kỳ lúc nào, song song được với các task khác. `E` chặn
bởi `A` **và** `B` (pilot phải chứng minh pattern đúng trước khi áp dụng lên
file rủi ro cao nhất). `F` không phụ thuộc kỹ thuật vào task nào, nhưng cố
tình tách riêng khỏi `E` vì bản chất rủi ro khác hẳn (xem §3) — không tự
động làm sau `E` mà không có quyết định riêng. `G` chặn bởi `A` (cùng lý do
với `B`/`E` — tracker dùng chung phải có trước), nhưng độc lập với `B`/`E`/`F`
— màn hình khác nhau, làm song song được.
