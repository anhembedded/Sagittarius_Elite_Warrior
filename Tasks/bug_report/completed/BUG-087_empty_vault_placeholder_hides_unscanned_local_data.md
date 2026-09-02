# BUG-087: Placeholder nói "Storage Vault trống" dù đĩa có 2 shard chưa quét

- **Reported**: 2026-09-03
- **Severity**: Trung bình (không mất dữ liệu, nhưng UI nói sai sự thật về Storage Vault)
- **Status**: ✅ Fixed 2026-09-03 (root-caused / reproduced qua test / regression-tested / verified)

---

## Symptom

Bằng chứng thật từ log dev-mode + ảnh chụp màn hình user gửi:

```
2026-09-03 05:29:28,196 - App.DataManagement - INFO - [storage-vault] 2 local shard(s) on disk, not yet scanned this session.
```

Nhưng UI tại đúng thời điểm đó hiện:
- Badge header bảng: **"0 shards"**
- Placeholder giữa bảng: **"Storage Vault trống. Hãy chọn Symbol & Timeframe và nhấn 'Sync' để tải dữ liệu."**
- "Est. Database Size": **2172.54 MB** (khác 0, đúng)

Log xác nhận có **2 shard cục bộ thật trên đĩa**, nhưng UI nói "trống" — trực tiếp mâu thuẫn,
đúng loại lỗi `domain-truth-rule.md` cấm: UI nói dối về thứ hệ thống thật sự biết.

## Root cause

Đây là tác dụng phụ của `BOT-120` (vừa merge PR #159): trước đó, mở màn hình Data Management
tự động quét toàn bộ vault (`ScanAllDatabasesQuery`) và đổ kết quả thật vào bảng, nên
`vm.rowCount` (số dòng đã quét) và "có bao nhiêu shard trên đĩa" luôn trùng nhau một cách tình
cờ. `BOT-120` dừng việc tự quét đó (đúng ý định — quét chỉ nên chạy khi user chủ động), nhưng
**không cập nhật lại 2 chỗ UI vẫn đang đọc `rowCount` như thể nó là "số shard trên đĩa"**:

- `DatabaseStatusTable.qml:28`: `badgeText: (vm ? vm.rowCount : 0) + " shards"`
- `DatabaseStatusTable.qml:134-135`: placeholder hiện khi `vm.rowCount === 0`, với nội dung giả
  định "rowCount === 0" nghĩa là "vault không có gì" — đúng trước `BOT-120`, sai sau đó.

Sau `BOT-120`, `rowCount` ở lại `0` **vĩnh viễn cho tới khi user chủ động quét**, kể cả khi
vault có dữ liệu thật — nên placeholder cũ luôn hiện sai trong đúng trường hợp phổ biến nhất
(vừa mở app, có dữ liệu cũ, chưa bấm gì).

## Fix

Thêm một sự thật độc lập với `rowCount`: **`knownShardCount`** — số shard `list_available_shards()`
tìm thấy trên đĩa (glob thư mục thuần tuý, không mở session nào) tại lần auto-discover/scan-all
gần nhất. Xuyên suốt 5 file:

- `ScanCoordinator`: `run_auto_discover` và `run_scan_all` (sau khi prune) đều báo số này qua
  một callback mới `ui_known_shard_count_signal`.
- `DataManagementPresenter`: signal `ui_known_shard_count_signal = Signal(int)` nối
  `view_model.set_known_shard_count`.
- `DataManagementViewModel`: property `knownShardCount` mới, độc lập với `status_model.rowCount()`.
- `DatabaseStatusPanel`/`DatabaseStatusVM`: forward xuống widget con — theo đúng pattern
  `set_search_text`/`set_actions_enabled` đã có.
- `DatabaseStatusTable.qml`: placeholder giờ rẽ nhánh theo `knownShardCount` — `> 0` thì nói rõ
  "có N tệp dữ liệu cục bộ, chưa quét trong phiên này", `== 0` mới giữ nguyên câu "Storage Vault
  trống" cũ.

Badge header ("N shards") **giữ nguyên** — nó đang đúng nghĩa "số dòng đang hiện trong bảng",
không đổi.

## Regression test

- `tests/unit/presentation/ui/qml/test_database_status_vm.py` (mới) — khoá `knownShardCount`
  độc lập với `rowCount`, có notify đúng, không notify khi giá trị không đổi.
- `tests/unit/presentation/ui/screens/data_management/test_scan_coordinator.py` —
  `test_scan_coordinator_auto_discover_never_opens_a_shard_session` và
  `..._reports_an_empty_vault_truthfully` giờ khoá luôn giá trị `ui_known_shard_count` gửi đi;
  test mới `test_scan_coordinator_scan_all_refreshes_known_shard_count_after_prune` khoá việc
  `run_scan_all` báo lại số **sau khi** prune, không phải số cũ trước khi dọn rác.
- `tests/unit/presentation/ui/screens/test_data_management_presenter.py` —
  `test_startup_auto_discovery_reports_known_shard_count_truthfully` (mới) khoá đường dây đầy đủ
  presenter → view model, xác nhận trước khi sửa: `rowCount == 0` nhưng `knownShardCount == 2`.

Toàn bộ 113 test liên quan (coordinator + presenter + widget VM + integration) chạy xanh sau
khi sửa; `ruff check`/`ruff format --check` sạch trên 9 file thay đổi.
