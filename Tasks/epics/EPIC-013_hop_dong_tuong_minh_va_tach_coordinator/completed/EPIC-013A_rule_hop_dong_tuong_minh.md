# EPIC-013A — Luật "hợp đồng phải tường minh, cấm duck-typing ngầm"

**Trạng thái:** ✅ Xong 2026-08-27
**Repo:** Elite
**Phụ thuộc:** không

## Yêu cầu gốc

User, 2026-08-27: *"updat rule code strickly no duck-typed. use abstract or
interface class"* — kèm câu hỏi *"ban thay sao, co mau thuan gi ko?"*.

## Mâu thuẫn đã nêu trước khi viết luật

Câu chữ *"strictly no duck-typed"* đọc theo nghĩa đen là **cấm
`typing.Protocol`** (structural typing chính là duck typing được hình thức
hoá). Đo trước khi viết:

- **18 `Protocol` đang dùng thật** — 9 ở `src/` repo này, 9 ở Engine.
- `LogModel`, `ITab`, `IStateContributor`, `IBacktestChartHost`: implementer đều
  là subclass `QObject`. `ABCMeta` xung đột metaclass với metaclass của Shiboken
  → biến chúng thành ABC là **không chạy được**, không phải "xấu hơn".
- `kit/style.py` module docstring đã ghi ràng buộc này: *"PySide6/Shiboken
  forbids a class inheriting two QObject-derived bases"* — chính là lý do
  `apply_role()` là composition thay vì mixin.
- `architecture-rule.md` §2 đã cấm sẵn multiple inheritance, nên implementer nào
  cũng đã có base class riêng.
- Engine dựng cả hệ extension trên narrow context Protocol
  (`IExtension[ILoggerContext]`).

Cái user thật sự muốn cấm — và cũng là lỗi đo được trong repo — là **hợp đồng
ngầm**, không phải `Protocol`:

- Presenter + 6 Coordinator + `signal_wiring` gọi **14 thành viên** của
  `view`, **0 khai báo** (`EPIC-013B` đo lại chính xác; quét cả thư mục ra 15,
  cái thứ 15 là `resize` của `preview.py` — một harness dev, không thuộc ranh
  giới Presenter↔View).
- `BasePresenter.__init__(self, view, container)`: `view` **không annotation**.
- `IView` khai đúng 1 method `bind()` mà **không View nào implement**; `src/`
  tham chiếu `IView` **0 lần**.

## Đã làm

1. `.agents/rules/architecture-rule.md` — thêm **§2.1 "Hợp đồng phải tường
   minh — cấm duck-typing ngầm"**, gồm:
   - phân biệt *duck-typing ngầm* (cấm) với `typing.Protocol` (một interface
     class tường minh, được phép);
   - **thứ tự chọn không được đảo**: ABC mặc định → `Protocol` chỉ khi rơi vào
     đúng 1 trong 3 lý do (QObject/Shiboken, §2 cấm multiple inheritance, class
     bên thứ ba), và **docstring phải ghi lý do thuộc nhóm nào**;
   - cảnh báo *"Protocol không phải lối thoát khỏi tính đầy đủ"* — bỏ sót ở ABC
     nổ `TypeError` ngay, bỏ sót ở Protocol thì **không gì nổ** cho tới khi
     `mypy` chạy;
   - số đo 2026-08-27 làm bằng chứng, kèm lệnh `grep` tự kiểm hợp đồng có đang
     trôi không;
   - **quyết định "View chọn lúc bootstrap, không thay runtime"** và hệ quả cấm
     cache widget con (`BUG-013`).
2. `.agents/rules/architecture-rule.md` frontmatter `description` — thêm mục
   mới, để công cụ nào đọc frontmatter cũng thấy.
3. `CLAUDE.md` — thêm **đúng một dòng trỏ** vào hàng "Kiến trúc" của bảng điều
   hướng. Không chép nội dung luật: `CLAUDE.md` tự ghi rằng repo đã dính bệnh
   bản-sao-trôi hai lần.

## Vì sao luật nằm ở `architecture-rule.md` chứ không phải `code-quality-rule.md`

Đây là quyết định **ranh giới giữa các thành phần** (ai được biết gì về ai), đo
bằng kiểu và bằng `mypy` — cùng abstraction level với §2 "Full Abstraction &
Decoupling" ngay trên nó và với §7 "Code phải tự nói lên chính nó".
`code-quality-rule.md` là luật *trong lòng một file* (typing, magic number,
nested loop, lazy import). Đặt sai chỗ là lặp lại đúng lỗi đã buộc
`code-rule.md` phải tách làm 6 file.
