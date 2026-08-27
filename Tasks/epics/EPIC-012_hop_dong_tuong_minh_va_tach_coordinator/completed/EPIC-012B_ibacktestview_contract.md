# EPIC-012B — Khai `IBacktestView`: hết hợp đồng ngầm ở màn Backtest

**Trạng thái:** ✅ Xong 2026-08-27
**Repo:** Elite
**Phụ thuộc:** `A` (luật §2.1 định nghĩa ABC-hay-Protocol)

## Đã khai — 4 port, không phải 1

Đo lại bằng `ast` (chính xác hơn `grep` của lần đo đầu): Presenter +
6 Coordinator + `signal_wiring` dùng **14 thành viên** của `view`.

> Lần đo đầu ghi **15**. Cái thứ 15 là `resize`, và nó đến từ `preview.py` —
> một harness dev tự dựng `BackTestView()` rồi gọi `resize(1400, 850)`. Đó là
> thao tác `QWidget`, không phải thứ Presenter yêu cầu ở View. Đưa nó vào port
> là bắt mọi View tương lai nợ một method không Presenter nào gọi. Số đúng là
> **14**; con số cũ đã sửa ở `architecture-rule.md` §2.1 và ở README của epic.

Hai thành viên trong số đó **không thể** khai bằng kiểu có sẵn mà không kéo một
widget cụ thể vào thư mục `ports/`, nên chúng sinh ra port riêng — nếu không,
chúng sẽ phải mang kiểu `object`, tức là **đúng hợp đồng ngầm đội lốt
annotation**:

| File | Nội dung | Số thành viên |
| :--- | :--- | ---: |
| `ports/i_backtest_view.py` | `IBacktestView` — hợp đồng Presenter↔View | 14 |
| `ports/i_backtest_chart_controls.py` | `IBacktestChartControls` — 4 signal + 3 method của toolbar | 7 |
| `ports/i_backtest_chart_host_factory.py` | `IBacktestChartHostFactory` — `create()` | 1 |
| `ports/i_backtest_chart_host.py` | `IBacktestChartHost` — **chuyển từ** `logic/backtest_chart_host.py` | (giữ nguyên) |

`is_trade_flags_checked()` có trên widget thật nhưng **không** khai ở
`IBacktestChartControls`: không consumer nào bên phía Presenter dùng nó. §1 "I"
— port nói cái consumer cần, không nói cái implementation tình cờ có.

## Tại sao có thư mục `ports/`

`logic/backtest_chart_host.py` đang giữ **port + implementation + factory**
trong một file 224 dòng — đúng hình dạng `architecture-rule.md` §5.1 cấm. Đã
chuyển port ra `ports/`, `logic/` giữ lại phần cụ thể. Tiền lệ bố cục:
`presentation/ui/state/ports/`.

## `Protocol`, không phải ABC — và ghi lý do vào docstring

Cả 4 port đều là `@runtime_checkable Protocol` theo §2.1 lý do **(a)/(b)**:
implementer là subclass `QWidget`/`QObject`, `ABCMeta` xung đột metaclass với
Shiboken, và thêm base thứ hai là đúng thứ §2 "NO Multiple Inheritance" cấm.
Docstring mỗi port ghi rõ đang dùng lý do nào — §2.1 bắt buộc.

**Không** kế thừa `IView` của Engine: `IView` khai `bind()`, không View nào
trong cả hai repo implement. Kế thừa nó là bắt mọi Backtest View mọc thêm một
method chỉ để thoả một interface chưa ai dùng. Việc `IView` nên được định nghĩa
lại hay gỡ đi là **task của repo Engine** — ghi ở đây để lần sau không ai coi
là đã xử lý.

## Phát hiện quan trọng: `mypy` KHÔNG kiểm tầng này

Nghiệm thu ban đầu của task này viết *"bơm lỗi → `mypy` phải đỏ"*. **Sai.**
`pyproject.toml` loại **toàn bộ `presentation/`** khỏi cổng `mypy`
(`EPIC-002A`: 24 file / 133 lỗi, 52% là false positive do mypy đọc
`@Property` của PySide6). Nghĩa là một `Protocol` sống ở tầng này **không có
cơ chế tĩnh nào** kiểm — đúng thứ §2.1 cảnh báo: bỏ sót ở ABC nổ `TypeError`
ngay, bỏ sót ở Protocol thì không gì nổ cả.

Nên cơ chế thật là **test**, không phải type checker:
`tests/unit/presentation/ui/screens/backtest/test_backtest_view_contract.py`
duyệt source bên phía Presenter bằng `ast` và đỏ ở **cả hai chiều**:

1. thành viên được dùng mà port chưa khai → hợp đồng lại thành ngầm;
2. thành viên port khai mà không ai dùng → đúng tình trạng `IView` đang mắc;
3. **cộng một test khoá số đếm (14)**, vì (1) và (2) so *tập hợp* nên xoá 1
   thêm 1 sẽ triệt tiêu nhau mà vẫn xanh;
4. cộng 3 `isinstance` khoá `BackTestView`/`BacktestChartControls`/
   `BacktestChartHostFactory` thật sự thoả port của chúng.

`preview.py` **cố ý** không nằm trong danh sách module được quét, và lý do nằm
ngay trong comment của test — nếu không, `resize` sẽ bị kéo vào port.

## Verify — bơm lỗi 3 lần, mỗi lần đúng test đỏ

| Bơm | Kết quả |
| :--- | :--- |
| Xoá `set_volume_visible` khỏi port | `test_every_member_..._is_declared` + `test_..._fourteen_members` đỏ |
| Thêm `self._view.totally_undeclared_member()` vào coordinator | `test_every_member_..._is_declared` đỏ |
| Thêm `nobody_calls_this()` vào port | `test_every_declared_member_is_actually_used` + `test_..._fourteen_members` + `test_backtest_view_satisfies_the_port` đỏ |

Khôi phục → 5/5 xanh.

## Nghiệm thu

- `pwsh -NoProfile -File scripts/ci-local.ps1 -Full` → `RESULT: PASS`, log quét
  sạch `FAILED|ERROR|Traceback|ResourceWarning`.
- 3 lần bơm lỗi ở bảng trên.
