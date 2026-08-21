# Epic EPIC-002 — Kiểm tra kiểu tĩnh (`mypy`) trong CI cục bộ

**Trạng thái:** 🟡 Đang làm — `EPIC-002A` xong (21/08), tiếp theo `EPIC-002B`.
**Nguồn:** [`BUG-026`](../../bug_report/completed/BUG-026_shutdown_probe_missing_stream_historical_klines_implementation.md).

---

## 1. Bối cảnh & Bằng chứng

`BUG-026`: một class implement `IExchangeClient` thiếu 1 method abstract
(`stream_historical_klines()`) — Python ném `TypeError: Can't instantiate
abstract class` ngay lúc khởi tạo. Lỗi này **có sẵn từ trước**, chỉ lộ ra khi
chạy đúng bài test process-level chạm tới nó, và `ruff` (công cụ tĩnh duy
nhất đang chạy trong CI cục bộ) không có cách nào bắt được — kiểm tra "class
con có implement đủ mọi method abstract của interface" đòi hỏi phân tích
kiểu dữ liệu xuyên suốt cây kế thừa, là việc của **type checker**
(`mypy`/`pyright`), nằm ngoài kiến trúc của `ruff` (linter) hoàn toàn — không
phải do thiếu bật 1 rule nào đó.

Đáng nói hơn: `mypy==2.1.0` **đã được khai báo sẵn** trong
`requirements-dev.txt` — ý định dùng nó đã có từ trước, chỉ chưa từng được
nối vào bất kỳ bước kiểm tra thật nào (`ci-local.ps1` không nhắc tới `mypy`
một lần nào).

**Đã verify thật, không suy đoán:** cài `mypy` vào venv tạm, tái hiện đúng
hình dạng lỗi của `BUG-026` (class chỉ implement 1/2 method abstract) trong
1 file cô lập, chạy `mypy` — bắt được ngay:

```
error: Cannot instantiate abstract class "_BlockingExchangeClient" with
abstract attribute "stream_historical_klines"  [abstract]
```

Không cần chạy test nào, không cần chạy app — bắt tại thời điểm code, tức
khắc.

## 2. Mục tiêu Epic

Nối `mypy` vào `ci-local.ps1 -Full` như một cổng bắt buộc, cạnh `ruff check`/
`ruff format --check` — để lớp lỗi của `BUG-026` không thể tái diễn mà phải
chờ tới lúc chạy đúng test mới lộ ra.

**Không** bật chế độ nghiêm ngặt (`--strict`) ngay từ đầu: đây là codebase
chưa từng type-check ngày nào, bật `--strict` tức khắc gần như chắc chắn xì
ra hàng loạt lỗi kiểu dữ liệu cũ không liên quan, chặn đứng mọi commit khác.
Đi theo đúng cách dự án này đã làm với native chart (`BOT-098F` A→B→C→D→E):
rollout từng bước, mỗi bước có tiêu chí nghiệm thu riêng, siết dần theo thời
gian chứ không "bật hết 1 lần".

## 3. Task con

| ID | Tên | Trạng thái |
| :--- | :--- | :---: |
| **[EPIC-002A](completed/EPIC-002A_mypy_baseline_audit.md)** | Đo baseline: `mypy` bắt bao nhiêu lỗi thật trên codebase hiện tại | ✅ Xong (21/08) — [báo cáo đầy đủ](../../reports/EPIC-002A_mypy_baseline_audit.md), phát hiện thêm 1 defect sống cùng lớp `BUG-026` |
| **[EPIC-002B](incomplete/EPIC-002B_wire_mypy_into_ci_local.md)** | Nối `mypy` (chế độ tối thiểu) vào `ci-local.ps1 -Full` | 🔴 Chưa làm |
| **[EPIC-002C](incomplete/EPIC-002C_document_mypy_gate_in_rules.md)** | Ghi nhận cổng `mypy` vào `ci-rule.md`/`ONBOARDING.md` | 🔴 Chưa làm |
| **[EPIC-002D](incomplete/EPIC-002D_incremental_strictness_rollout.md)** | Lộ trình siết `--strict` dần theo module (giai đoạn sau, không chặn 3 task trên) | 🔴 Chưa làm |

Thứ tự bắt buộc: `A` → `B` → `C`. `D` là backlog dài hạn, không phụ thuộc
tuyến tính, có thể làm bất kỳ lúc nào sau `B`.
