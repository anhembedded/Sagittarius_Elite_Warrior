# Epic EPIC-003 — Phân rã Presenter/File quá tải (God Object/God File Decomposition)

**Trạng thái:** 🟡 Đang làm — 1/6 xong (21/08): `EPIC-003A`. Tiếp theo `EPIC-003B`/`EPIC-003C`/`EPIC-003D` làm được song song.
**Nguồn:** [`PRO-001`](../../proposal/PRO-001.md) (Coordinator Pattern cho Presenter),
[`PRO-002`](../../proposal/PRO-002.md) (khảo sát toàn bộ file quá tải trong `src/`) —
2 đề xuất do một phiên làm việc khác viết, được đối chiếu lại với quy tắc đã
có sẵn của dự án trước khi chấp nhận (xem §2).

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
| **[EPIC-003B](incomplete/EPIC-003B_data_management_coordinator_pilot.md)** | `DataManagementPresenter` → Coordinator Pattern (pilot) | 🟡 | 🔴 Chưa làm |
| **[EPIC-003C](incomplete/EPIC-003C_paper_exchange_policy_split.md)** | `PaperExchange` → Domain Policy (Margin/Matching/Fee) | 🟢 | 🔴 Chưa làm |
| **[EPIC-003D](incomplete/EPIC-003D_qml_component_split.md)** | Dọn 8 file misplaced trong `components/` (Phase 1) + tách 3 file QML lớn (Phase 2) | 🟢 | 🔴 Chưa làm |
| **[EPIC-003E](incomplete/EPIC-003E_backtest_presenter_coordinator.md)** | `BacktestPresenter` → Coordinator Pattern | 🔴 | 🔴 Chưa làm |
| **[EPIC-003F](incomplete/EPIC-003F_backtest_viewmodel_composite_design_review.md)** | `BacktestViewModel` → Composite ViewModel — **vòng thiết kế trước**, chưa code | 🔴 | 🔴 Chưa làm |

**Thứ tự phụ thuộc:** `A` chặn `B` và `E` (không Coordinator nào được cài
action-ownership riêng trước khi có tracker dùng chung). `C` và `D` độc lập
hoàn toàn, làm bất kỳ lúc nào, song song được với các task khác. `E` chặn
bởi `A` **và** `B` (pilot phải chứng minh pattern đúng trước khi áp dụng lên
file rủi ro cao nhất). `F` không phụ thuộc kỹ thuật vào task nào, nhưng cố
tình tách riêng khỏi `E` vì bản chất rủi ro khác hẳn (xem §3) — không tự
động làm sau `E` mà không có quyết định riêng.
