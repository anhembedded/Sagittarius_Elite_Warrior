---
name: Architecture Rule
description: SOLID, Clean Architecture layer boundaries, Ports/Adapters and ABC completeness, CQRS use-case structure, and Abstraction-Level Separation (khác abstraction level thì không chung file, không chung thư mục).
trigger: on_demand
---

# ARCHITECTURE RULES

> **Nguồn (2026-08-25):** nội dung dưới đây được **chuyển nguyên văn** từ
> `code-rule.md` khi file đó được tách theo abstraction level. Không có quy tắc
> nào bị đổi nghĩa, thêm hay bớt trong lần tách này — chỉ đổi chỗ ở.

Đọc file này khi: thiết kế/tái cấu trúc kiến trúc, thêm hoặc đổi một Port
(`abc.ABC` / `Protocol`), thêm một Use Case, quyết định một thứ nên nằm ở
file/thư mục nào, hoặc khi tách một file/lớp đã quá ngưỡng.

Quy tắc chất lượng code thuần tuý (magic number, nested loop, lazy import,
typing, immutability) **không** nằm ở đây — xem
[`code-quality-rule.md`](code-quality-rule.md).

---

## 1. SOLID Principles
Follow SOLID wherever it's practical — apply it to improve clarity/testability, don't force an abstraction onto a small, unlikely-to-change piece of code just to tick a box.
- **S — Single Responsibility:** One class/module has one reason to change. (See "No God Objects" below.) Split by responsibility into separate files/modules instead of piling unrelated logic into one file or one function.
- **O — Open/Closed:** Prefer extending behavior via a new class/strategy over editing existing, already-tested logic; put extension points behind an interface/ABC.
- **L — Liskov Substitution:** A subclass must work anywhere its base/interface is expected — no raising `NotImplementedError` on inherited methods, no narrowing accepted inputs or weakening guarantees the base type promised.
- **I — Interface Segregation:** Keep ports/interfaces narrow and role-specific; don't make an implementer satisfy methods it has no use for.
- **D — Dependency Inversion:** High-level modules depend on abstractions, not concrete implementations. (See "Full Abstraction & Decoupling" below.)

---

## 2. Full Abstraction & Decoupling

2. **Full Abstraction & Decoupling:**
   - Define explicit abstractions using `abc.ABC` or `typing.Protocol` for repositories, services, and external clients.
   - Adhere strictly to the Dependency Inversion Principle (DIP). High-level business logic must depend on abstractions, not concrete implementations.
   - Prefer Dependency Injection (DI) over hardcoded class instantiations inside domain logic.
   - **NO Multiple Inheritance:** Strictly avoid multiple inheritance. Use composition over inheritance, and flatten interfaces where necessary to avoid complex method resolution orders (MRO).
   - **Every `abc.ABC` implementer must stay complete, everywhere.** When a
     Port (`IExchangeClient`, `IMarketDataRepository`, ...) gains a new
     `@abstractmethod`, every concrete class implementing it must be updated
     in the same change — not just the real production implementation. Search
     `src/`, `scripts/`, **and** `tests/` for every implementer; a hand-rolled
     test double or probe script left behind an interface change instantiates
     fine until the exact moment something runs it, then fails with
     `TypeError: Can't instantiate abstract class`
     (`BUG-026`: a shutdown-probe script's fake exchange client silently fell
     behind a Port change; a second, still-unfixed instance
     (`scripts/backtest_timeframe_toolbar_e2e.py`) was only found later by
     `EPIC-002A`'s static audit — not by anyone running that script). `ruff`
     cannot catch this — verifying ABC completeness across files is a type
     checker's job, not a linter's; `mypy` (`EPIC-002`) is the mechanical
     backstop, but do not rely on the tool alone — grep for implementers
     as part of the change itself.

---

## 3. Clean Architecture Layer Enforcement

5. **Clean Architecture Layer Enforcement:**
   - Always strictly respect the 4 Layers: **Domain** (Pure) $\rightarrow$ **Application** (Use Cases/Ports) $\rightarrow$ **Interface Adapters** (CLI/UI Presenters) $\rightarrow$ **Infrastructure** (DB/API/Frameworks).
   - Never leak Infrastructure concerns (like `sagittarius_engine` base classes, SQLAlchemy, or API clients) into the Domain or Application layers.
   - Prioritize building reusable abstraction base layers (base cards, base dialogs, base presenters/view models) over concrete duplication.

---

## 4. Use Case Structure (CQRS)

6. **Use Case Structure (CQRS):**
   - Every Application Use Case must reside in its own dedicated directory (e.g., `src/application/use_cases/<my_use_case>/`).
   - The Command/Response definition must be separated from the Handler logic into multiple files (e.g., `command.py` and `handler.py`), and then exported cleanly via `__init__.py`.
   - Never import engine-specific interfaces (like `sagittarius_engine.extensions.cqrs.ICommand`) into the Application layer. Use the layer's own pure Python `ICommandHandler` / `IQueryHandler` interfaces.

---

## 5. Abstraction-Level Separation

   - **Abstraction-Level Separation (Khác abstract level thì không chung file, không chung thư mục) — user chốt 2026-08-25:** Chia nhỏ là mặc định. **Càng nhiều file càng tốt**; gộp phải có lý do, tách thì không cần xin phép.
     1. **Không chung file:** hai thứ **khác abstraction level** MUST NOT nằm cùng một file. Một interface/Port và một implementation cụ thể của nó; một base class và các subclass; một policy trừu tượng và cách nó đọc đĩa — mỗi thứ một file riêng.
     2. **Không chung thư mục:** các file **khác abstraction level** MUST NOT nằm chung một `dir`. Thư mục là một tầng, không phải một cái sọt: `interfaces/` không chứa implementation, `widgets/` (nguyên thuỷ dùng chung) không chứa màn hình cụ thể, `domain/` không chứa adapter hạ tầng. Nếu một thư mục đang trộn hai tầng, tách thư mục con theo tầng chứ đừng đổi tên file cho gọn.
     3. **Đối trọng duy nhất là Single-Scope Cohesion ngay bên trên** — và nó chỉ thắng khi các định nghĩa mô tả **cùng một vòng đời** (enum + ma trận của cùng 1 FSM; `StyleRole` + `_build_qss()`). "Cùng feature", "cùng màn hình", "hay dùng chung lúc" **không phải** cùng abstraction level và **không** đủ để gộp.
     4. **Ngưỡng buộc phải tách** (`EPIC-007` §3.4, áp cho mọi code mới): một file **>400 dòng** hoặc một lớp **>15 phương thức công khai**. Chạm ngưỡng là tách, không thương lượng.
     5. Cách phân xử nhanh khi lưỡng lự: *"Đổi thứ A có bắt buộc phải đọc/sửa thứ B không?"* Có → cùng vòng đời, được chung file. Không → khác tầng, tách ra. Chứng cứ thật cho luật này: `data_management_widgets.py` (1.156 dòng) vô tình thành thư viện widget chung của cả app vì trộn nguyên thuỷ dùng chung với widget riêng của 1 màn — 3 file ở 2 màn khác phải import chéo vào nó (`EPIC-007` §1).

> Đối trọng của quy tắc này là **Single-Scope Cohesion**, sống ở
> [`code-quality-rule.md`](code-quality-rule.md) — đọc cả hai trước khi
> quyết định gộp hay tách.
