# EPIC-007G — Elite: tách các file vượt ngưỡng ở tầng UI

**Thuộc:** [`EPIC-007`](../README.md) · **Repo:** `Sagittarius_Elite_Warrior` · **Trạng thái:** ✅ Xong 2026-08-26 — 3/5 file về dưới ngưỡng; 2 file còn lại có lý do ghi ở §Kết quả
**Phụ thuộc:** `007F`

---

## Phạm vi

Ngưỡng (`README.md` §3.4): **>400 dòng** hoặc **>15 phương thức công khai**.

Số dòng trong bảng gốc của task đo **trước** `007E`/`007F`; bảng dưới đo lại tại thời điểm làm.

## Kết quả — bảng dòng trước / dòng sau

| File | Trước | Sau | Ghi chú |
| :--- | ---: | ---: | :--- |
| `backtest_modals.py` | 1.238 | **package 15 file, lớn nhất 294** | 12 dialog công khai |
| `data_management_widgets.py` | 905 | **package 8 file, lớn nhất 375** | 5 widget công khai |
| `backtest_trade_logs_panel.py` | 644 | **389** | tách `_FilterTabButton`, `_TradeLogRowWidget`, spec cột |
| `data_management_view.py` | 851 | 699 ⚠️ | còn trên ngưỡng — xem dưới |
| `backtest_top_panel.py` | 682 | 682 ⚠️ | **không đổi** — xem dưới |

## Hai file được ở lại trên ngưỡng, và vì sao

Đây là câu trả lời thật, không phải phần bỏ sót.

- **`backtest_top_panel.py` (682)** — chứa **một** lớp `BackTestTopPanel` dài 627 dòng, cộng
  một helper 9 dòng mà chỉ lớp đó gọi. **Không có gì để *di chuyển*.** Cách duy nhất để xuống
  dưới ngưỡng là **chẻ chính lớp đó ra**, tức là đổi hành vi và API công khai — đúng thứ
  **yêu cầu 3 của task này cấm** (*"Không đổi hành vi, không đổi API công khai. Chỉ di
  chuyển."*).
- **`data_management_view.py` (699)** — cùng hình dạng: `DataManagementView` một mình đã 615
  dòng, mọi thứ di chuyển được đã chuyển đi hết (`_StatusRowWidget` → `_status_row.py`, spec
  cột → `_status_columns.py`).

**Chẻ một lớp cỡ đó là chủ đề của [`EPIC-003`](../EPIC-003_presenter_and_god_file_decomposition/),
không phải của task này.** Ghi lại làm ứng viên cho epic đó, không cố nhét vào đây.

Đo lại toàn cây UI sau khi xong: còn **15 file** trên ngưỡng, phần lớn là presenter/view-model
(`backtest_presenter.py` 2.803, `backtest_view_model.py` 1.368, `dashboard_presenter.py` 1.057)
— **ngoài phạm vi** task này, thuộc `EPIC-003`.

## Ranh giới module: theo luật cohesion, không theo số dòng

- `_layout.py`, `_kline_columns.py`, `_status_columns.py`, `_trade_log_columns.py` giữ thứ
  **nhiều module cùng đọc**. Chỉ số ô là `range(len(_COLUMNS))`, nên thêm một cột ở chỗ khác
  spec sẽ **âm thầm đánh số lại mọi ô** — chúng phải ở chung một chỗ hoặc không chỗ nào cả.
- `_bot_param_field.py` giữ `_NumericStepLineEdit` **cùng** `_BotParamFieldWidget`: cái trước
  chỉ được khởi tạo đúng một chỗ, bên trong cái sau. Một vòng đời — chẻ tiếp là **vi phạm**
  Single-Scope Cohesion chứ không phải tuân thủ (yêu cầu 2).
- `_kline_row.py` giữ `_kline_model_class` cùng `_KLineRowWidget`. Đặt resolver cạnh dialog tạo
  ra **import vòng thật** (dialog dựng row, row cần resolver). Giải bằng **đặt lại ranh giới
  module** — đúng thứ mục Rủi ro của task yêu cầu; import cục bộ trong hàm bị `code-rule.md`
  cấm tuyệt đối.
- `_CoverageSegmentWidget` ở lại `screens/` theo yêu cầu 5 của `007F`.

## Yêu cầu 3 — không đổi API công khai

Hai package re-export **đúng** những tên module cũ export (12 và 5). Không call-site nào phải
sửa: `backtest_view.py` và `data_management_view.py` không bị đụng tới. Ba file kia chỉ tách
lớp **private**, mỗi lớp có đúng một consumer trong chính file đó.

## Công cụ — và ba khuyết tật của chính nó bị bắt

Việc di chuyển do một công cụ AST làm, không chép tay: nó phát ra, cho mỗi module, **chỉ**
những import và hằng mà định nghĩa trong module đó thật sự tham chiếu; `ruff check --fix` cắt
phần dư chính xác (238 import thừa bị gỡ, không cái nào bằng mắt).

Ba khuyết tật của công cụ **bị các cổng bắt, không phải bằng mắt** — cả ba đều sẽ ship im lặng:

1. Hằng khai báo bằng **tuple unpacking** (`_A, _B = range(2)`) bị bỏ sót → `ruff` F821 gọi tên
   đủ 12 hằng thiếu.
2. Hằng dùng chung bị **chép** vào mọi module đọc nó (`_FIELD_STYLE`/`_ACCENT` vào 4 file).
   Công cụ giờ **từ chối đoán**: hằng có từ 2 consumer phải được khai chỗ ở, các module khác
   import. Kiểm lại sau đó: không hằng nào bị định nghĩa hai lần.
3. Module **chỉ chứa hằng** được phát ra **không có import nào**, vì import được suy từ các
   định nghĩa mà nó không có.

## Bằng chứng

- `git diff --stat`: phần lớn là **di chuyển** — 2.990 thêm / 2.564 xoá trên 32 file, gần đúng
  bằng nội dung được chuyển chỗ.
- `tests/unit/presentation/ui`: **1.282 passed**, **không đổi** qua cả ba lần commit tách.
- `ruff check` + `ruff format` sạch trên toàn `src`/`tests`/`tools`.
- Toàn suite: **2.305 passed, 4 skipped**, 0 dòng `FAILED|Traceback|ResourceWarning` trong log.

### Số test toàn suite đổi 2.283 → 2.309 (+26) — giải thích đủ, không phải đổi hành vi

Task yêu cầu *"số test không đổi"*. Nó **có đổi**, nên phải nói rõ vì sao — đo bằng worktree
trên `origin/master-warrior` (đặt đúng tên thư mục, vì repo import theo
`Sagittarius_Elite_Warrior.src...`; lần đo đầu đặt sai tên nên chỉ collect được 18 file, số đó
đã bỏ).

Chênh lệch nằm gọn ở **đúng một file**:

| Test file | Trước | Sau |
| :--- | ---: | ---: |
| `tests/unit/test_logging_namespace_guard.py` | 309 | **335** (+26) |
| *mọi file khác* | — | **không đổi** |

`test_logging_namespace_guard.py` là
`@pytest.mark.parametrize(..., _SRC_ROOT.rglob("*.py"))` — **một case cho mỗi file nguồn**.
`git diff --name-status` đếm được **28 file thêm, 2 file xoá = +26 file nguồn**. Khớp chính xác.

Nói cách khác: không test nào mới được viết, không test nào biến mất; một guard vốn chạy trên
từng file giờ có thêm 26 file để chạy. Đây là hệ quả cơ học của việc tách file, không phải thay
đổi hành vi.
- Export và đường import của cả hai package kiểm chứng bằng cách import thật lúc runtime.

> Ghi chú: `pwsh -NoProfile -File scripts/ci-local.ps1` không chạy được ở môi trường phiên này
> (không có `pwsh` trên Linux container). Đã thay bằng đúng các cổng CI của repo chạy trực
> tiếp: `ruff check`, `ruff format --check`, `pytest`.
