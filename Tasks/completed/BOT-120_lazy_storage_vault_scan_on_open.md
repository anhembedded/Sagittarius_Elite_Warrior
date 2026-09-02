# BOT-120: Không quét toàn bộ Storage Vault khi mở màn hình Data Management

- **ID**: `BOT-120`
- **Type**: Perf / Architecture (behavior change)
- **Module**: `presentation/ui/screens/data_management` (`ScanCoordinator`, `DataManagementPresenter`)
- **Status**: `🟡 Code + test xong, chờ user duyệt/commit`

---

## 1. Bối cảnh & vấn đề thật

User báo qua log dev-mode thật (`dev-20260902-101219.log`): mở màn hình **Data Management**
mất **~27 giây** ở nền trước khi bảng "Database Status" ổn định, dù thực tế chỉ có **9 shard
có dữ liệu thật**. Bằng chứng trực tiếp từ log:

```
17:12:25,134 - Handling ScanAllDatabasesQuery for 1350 symbols x 6 intervals.
17:12:52,315 - [storage-vault] Pruned 1348 empty shard(s) (0 klines in any interval): [...]
```

### Root cause

`DataManagementPresenter.__init__` tự động submit `run_auto_discover()` ra nền **mỗi lần màn
hình được mở lần đầu trong phiên** (`_run_auto_discover`,
`data_management_presenter.py:298`). Hàm đó:

1. dispatch `ScanAllDatabasesQuery(symbols=[], intervals=[])` — theo
   `ScanAllDatabasesQueryHandler`, `symbols` rỗng thì fallback sang
   `repository.list_available_shards()`, tức là **mọi file `.db` đang có trên đĩa**;
2. với mỗi symbol đó, mở **một session SQLAlchemy** và lặp 6 interval bên trong
   (`get_database_status_for_intervals`) — chi phí nằm ở việc **mở session**, không phải bản
   thân câu query (đã ghi rõ trong docstring của chính hàm đó, từ `BUG-078`);
3. rồi dispatch `PruneEmptyShardsCommand`, hàm này **lại liệt kê toàn bộ shard một lần nữa**
   và mở thêm một session mỗi shard để gọi `has_any_klines`.

Máy của user đang mang **1348 shard rỗng** tồn đọng từ trước khi `BUG-078` sửa root cause
(một lần đọc thuần tuý từng tạo ra file `.db` rỗng như tác dụng phụ của
`get_session()`'s create-on-first-use). Cơ chế tạo rác đó đã được vá, nhưng **mỗi lần mở
app**, `run_auto_discover` vẫn phải trả phí mở session cho toàn bộ 1350 ứng viên đó trước khi
dọn được 1348 cái rỗng — dọn xong thì gần như quay lại đúng 9 shard thật.

### Đây không chỉ là vấn đề tốc độ

Màn hình đã có sẵn nút **"Scan All Shards & Timeframes"** ở panel Actions — đúng cơ chế để
làm việc này **theo yêu cầu tường minh của user**. `run_auto_discover` lại âm thầm làm đúng
việc đó (mở session, quét, dọn rác) **tự động, không ai bấm gì**, mỗi lần mở màn hình — khiến
nút kia trở thành thừa và vi phạm nguyên tắc "data chỉ nên được fetch khi user chủ động thao
tác update/sync" (yêu cầu trực tiếp của user, và cũng là pattern phổ biến ở các công cụ lớn:
DBeaver/pgAdmin/VS Code Explorer hiển thị cây tức thì từ metadata rẻ, chỉ verify chi tiết khi
người dùng bấm Refresh/mở rộng node).

---

## 2. Thiết kế + lý do

**Quyết định theo `.agents/ONBOARDING.md` §7** ("Deciding for yourself is the default") — đây
là quyết định thiết kế bình thường trong phạm vi, không phải đánh đổi lớn/không đảo ngược
được, nên không dừng lại hỏi từng lựa chọn nhỏ.

1. **Mở màn hình vẫn rẻ, nhưng không còn mở session nào:**
   `run_auto_discover` chỉ còn dispatch `ListAvailableSymbolsQuery` (đã cache, nhanh, để đổ
   symbol picker) và gọi `market_data_repo.list_available_shards()` — xác nhận đây là một
   **liệt kê thư mục thuần tuý** (`SqliteShardManager.list_shards()` chỉ `Path.glob("*.db")`,
   không mở kết nối nào) — để log một dòng đúng sự thật: có bao nhiêu shard trên đĩa, **chưa
   quét trong phiên này**.
2. **Việc quét chi tiết + dọn rác chuyển hẳn sang hành động tường minh:** thân của
   `run_auto_discover` cũ (dispatch `ScanAllDatabasesQuery` rồi `PruneEmptyShardsCommand`)
   chuyển vào `run_scan_all` — đúng hàm đứng sau nút "Scan All Shards & Timeframes".
3. **Đổi nguồn symbol của `_on_check_all_status`:** hiện tại nút này quét theo
   `list(view_model.symbols)` — toàn bộ ~1358 symbol của sàn (hầu hết không có shard).
   Đổi sang truyền `[]`/`[]`, tái dùng đúng fallback đã có sẵn trong
   `ScanAllDatabasesQueryHandler` (rỗng → `list_available_shards()` +
   `_DEFAULT_SCAN_INTERVALS`) — không cần thêm handler mới, và "Scan All Shards" giờ đúng
   nghĩa đen là quét *shard đang có*, không phải toàn bộ sàn.
4. **UI trung thực:** khi chưa quét, log nói rõ "N shard cục bộ trên đĩa, chưa quét trong
   phiên này — nhấn 'Scan All Shards & Timeframes' để tải trạng thái", thay vì ngầm coi như
   đã "Auto-discovered" xong.

Không tối ưu thêm gì trong bản thân `ScanAllDatabasesQueryHandler` (ví dụ lọc theo kích thước
file trước khi mở session) — hành động giờ đã tường minh, có thể huỷ (`_on_cancel` đã nối dây
sẵn), nên việc nó chạy chậm một lần khi user chủ động bấm là chấp nhận được. Ghi lại như một
hướng tối ưu tương lai, không làm ngay để tránh phình phạm vi task này.

---

## 3. Thay đổi theo từng file

| File | Thay đổi |
| :--- | :--- |
| `src/presentation/ui/screens/data_management/coordinators/scan_coordinator.py` | `run_auto_discover` rút gọn (chỉ list symbol + log số shard trên đĩa); thân quét+dọn cũ chuyển vào `run_scan_all`, gọi `_prune_empty_shards` sau khi quét xong |
| `src/presentation/ui/screens/data_management/data_management_presenter.py` | `_on_check_all_status` đổi `list(view_model.symbols)`/`list(view_model.intervals)` thành `[]`/`[]` |
| `tests/unit/presentation/ui/screens/data_management/test_scan_coordinator.py` | Viết lại 3 test auto-discover cho hợp đồng rẻ mới; thêm test xác nhận `run_scan_all` dispatch prune |
| `tests/unit/presentation/ui/screens/test_data_management_presenter.py` | Cập nhật các test `test_startup_auto_discovery_*`, `test_auto_discover_empty_database_*`, `test_on_check_all_status_submits_background_task` cho hợp đồng mới |

## 4. Kiểm thử

Unit, tầng Presentation (đã có `qapp` fixture theo quy ước hiện tại của repo, không boot app
thật — vẫn là Unit theo `ci-rule.md` §4). Không cần Integration/Sanity mới vì không đổi cấu
trúc DI hay route.

## 5. Ghi chú triển khai (2026-09-02)

- **Đã code + test xong**, chưa commit (chờ user yêu cầu theo `commit-rule.md` §0).
- 4 file thay đổi đúng như thiết kế ở §3; không đổi thêm gì ngoài phạm vi.
- Bẫy thật gặp phải khi viết lại test: `_dispatch_by_query_type` (helper test có sẵn) trước
  đây chỉ phân biệt `ScanAllDatabasesQuery` vs "còn lại" — giờ `run_scan_all` dispatch **2**
  query (`ScanAllDatabasesQuery` rồi `PruneEmptyShardsCommand`), nên "còn lại" phải tách thêm
  nhánh cho `PruneEmptyShardsCommand` (trả `PruneEmptyShardsResult` thật), nếu không
  `result.removed_symbols` nổ `AttributeError` trên một `list` giả. Cùng lỗi ở fixture
  `mock_container` của presenter: `IMarketDataRepository` trước đây rơi vào nhánh
  `return Mock()` mặc định — `len(Mock())` nổ `TypeError`. Đã thêm fixture
  `mock_market_data_repo` riêng với `list_available_shards.return_value = []` mặc định.
- Verify: `ruff check` + `ruff format --check` sạch trên 4 file; mypy không áp dụng (tầng
  `presentation/` bị loại khỏi cổng theo baseline `EPIC-002A`, xem `ci-rule.md`). Test:
  10/10 (`test_scan_coordinator.py`) + 36/36 (`test_data_management_presenter.py`) +
  93/93 khi chạy cùng `test_database_user_flow.py`, `test_main_window_state.py`,
  `test_screen_layer_structure.py` — không có test nào khác trong repo bị ảnh hưởng.
- Không chạy full `ci-local.ps1 -Full` (không có PowerShell trong môi trường phiên này) —
  đã bù bằng lệnh bash tương đương theo `ONBOARDING.md` §5.
