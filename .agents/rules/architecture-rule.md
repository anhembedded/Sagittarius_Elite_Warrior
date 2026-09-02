---
name: Architecture Rule
description: SOLID, Clean Architecture layer boundaries, Ports/Adapters and ABC completeness, hợp đồng phải tường minh (cấm duck-typing ngầm — ABC mặc định, Protocol chỉ khi kế thừa bất khả thi), CQRS use-case structure, và Abstraction-Level Separation (khác abstraction level thì không chung file, không chung thư mục).
trigger: always_on
---

# ARCHITECTURE RULES

Đọc khi: thiết kế/tái cấu trúc kiến trúc, thêm/đổi một Port (`abc.ABC` / `Protocol`), thêm Use Case, quyết định một thứ nằm ở file/thư mục nào, hoặc tách một file/lớp đã quá ngưỡng. Chất lượng code thuần tuý (magic number, nested loop, lazy import, typing, immutability) ở [`code-quality-rule.md`](code-quality-rule.md) — đối trọng của §5 là **Single-Scope Cohesion** trong file đó.

> [!IMPORTANT]
> **Phương châm quyết định khi kiến trúc khó/mơ hồ đã chuyển sang
> [`../ONBOARDING.md`](../ONBOARDING.md) §7** ("Tự quyết là mặc định") —
> 2026-09-02. Lý do: nó là luật về **quyền tự quyết**, áp cho mọi quyết định
> kỹ thuật chứ không riêng kiến trúc, và nằm ở đây thì **không file điều hướng
> nào trỏ tới nó** nên trên thực tế không ai đọc. Tóm tắt: quyết theo pattern
> đã được kiểm chứng, tham chiếu dự án lớn, không ngại redesign *hard design*,
> tự quyết mà không hỏi từng lựa chọn nhỏ — trừ 3 nhóm nêu ở đó.

---

## 1. SOLID Principles

Follow SOLID wherever it's practical — apply it to improve clarity/testability, don't force an abstraction onto a small, unlikely-to-change piece of code just to tick a box.

- **S — Single Responsibility:** One class/module has one reason to change (see "No God Objects"). Split by responsibility into separate files/modules instead of piling unrelated logic into one file or one function.
- **O — Open/Closed:** Prefer extending behavior via a new class/strategy over editing existing, already-tested logic; put extension points behind an interface/ABC.
- **L — Liskov Substitution:** A subclass must work anywhere its base/interface is expected — no raising `NotImplementedError` on inherited methods, no narrowing accepted inputs or weakening guarantees the base type promised.
- **I — Interface Segregation:** Keep ports/interfaces narrow and role-specific; don't make an implementer satisfy methods it has no use for.
- **D — Dependency Inversion:** High-level modules depend on abstractions, not concrete implementations.

---

## 2. Full Abstraction & Decoupling

- Define explicit abstractions using `abc.ABC` or `typing.Protocol` for repositories, services, and external clients.
- Adhere strictly to the Dependency Inversion Principle (DIP). High-level business logic must depend on abstractions, not concrete implementations.
- Prefer Dependency Injection (DI) over hardcoded class instantiations inside domain logic.
- **NO Multiple Inheritance:** Strictly avoid multiple inheritance. Use composition over inheritance, and flatten interfaces where necessary to avoid complex method resolution orders (MRO).
- **Every `abc.ABC` implementer must stay complete, everywhere.** Port (`IExchangeClient`, `IMarketDataRepository`, ...) thêm `@abstractmethod` thì **mọi** implementer phải sửa trong cùng thay đổi — grep `src/`, `scripts/` **và** `tests/`. Test double / probe script bị bỏ lại vẫn import được, chỉ nổ đúng lúc ai đó chạy nó: `TypeError: Can't instantiate abstract class` (`BUG-026`: fake exchange client của một shutdown-probe script tụt lại sau một Port change; instance thứ hai, `scripts/backtest_timeframe_toolbar_e2e.py`, chỉ bị bắt bởi static audit của `EPIC-002A`). `ruff` không bắt được — việc này là của type checker; `mypy` (`EPIC-002`) là backstop cơ học, nhưng **vẫn phải tự grep implementer**, đừng phó mặc tool.

### 2.1 Hợp đồng phải tường minh — cấm duck-typing ngầm

> **Mọi hợp đồng vượt ranh giới (Presenter ↔ View, consumer ↔ port, module ↔ module) PHẢI là một
> kiểu có tên. Không được để hợp đồng chỉ tồn tại dưới dạng "gọi thử xem có method đó không".**

**Cấm:** hợp đồng ngầm — `def __init__(self, view)` không annotation rồi consumer gọi 15 thành viên của nó; `hasattr()`/`getattr()` để dò khả năng. **Bắt buộc:** một kiểu có tên (`abc.ABC` **hoặc** `typing.Protocol`).

Thứ bị cấm là *duck-typing ngầm*, **KHÔNG phải `typing.Protocol`** (đọc nhầm là đi phá 18 Protocol đang đúng: 9 ở `src/`, 9 ở Engine). `Protocol` **là** interface tường minh: có tên, `grep` ra được, `mypy` kiểm được, `@runtime_checkable` thì `isinstance()` được — nó chỉ bỏ **bắt buộc kế thừa**, không bỏ hợp đồng.

**Thứ tự chọn — không được đảo:**

1. **`abc.ABC` là mặc định.** Implementer `class X(IPort)`; luật ABC completeness ở §2 áp dụng đầy đủ.
2. **`typing.Protocol` (kèm `@runtime_checkable`) chỉ khi kế thừa bất khả thi hoặc bị chính repo này cấm** — và **docstring PHẢI ghi nó thuộc lý do nào**. Đúng 3 lý do hợp lệ, cả 3 đều có tiền lệ thật:
   - **(a) Implementer là subclass `QObject`.** PySide6/Shiboken cấm kế thừa 2 base dẫn xuất từ `QObject`, `ABCMeta` lại xung đột metaclass với Shiboken — ABC là **không chạy được**, không phải "xấu hơn". Tiền lệ: `kit/style.py`, `LogModel`, `ITab`, `IStateContributor`, `IBacktestChartHost`.
   - **(b) §2 "NO Multiple Inheritance" chặn** — implementer đã có base riêng (`BasePresenter`, `QMainWindow`, ...).
   - **(c) Implementer là class bên thứ ba** repo này không sửa được.
3. **Không rơi vào (a)/(b)/(c) → phải là ABC.** "Protocol tiện hơn" không phải lý do.

**Protocol không phải lối thoát khỏi tính đầy đủ.** Protocol phải mô tả đúng và đủ những gì consumer thật sự dùng; thêm lời gọi mới mà không khai vào Protocol là quay lại đúng duck-typing ngầm. Bỏ sót ở ABC thì `TypeError` nổ ngay; bỏ sót ở Protocol thì **không gì nổ** cho tới khi `mypy` chạy — nên với Protocol, `mypy` (`EPIC-002`) không phải backstop mà là **cơ chế duy nhất**.

**Bằng chứng thật (đo 2026-08-27):** `backtest_presenter.py` + 6 coordinator + `signal_wiring.py` gọi **14 thành viên** của `view` mà **không kiểu nào khai** (`BasePresenter.__init__(self, view, container)` của Engine để `view` không annotation). Quét cả thư mục ra 15 — cái thứ 15 đến từ harness dev `preview.py`, không thuộc ranh giới Presenter↔View, nên bước "xem từng hit đến từ đâu" không được bỏ. Engine *có* `IView` nhưng nó khai đúng 1 method `bind()` không View nào implement, và `src/` tham chiếu `IView` **0 lần**: hợp đồng thật ≠ hợp đồng khai.

```bash
# Consumer đang dùng những gì của `x`? (bỏ -h để thấy hit nào ở file nào)
grep -rnoE "(self\.)?_?<tên_thuộc_tính>\.[a-zA-Z_]+" src/<thư_mục>/
```

Số thành viên còn lại **sau khi loại các hit không thuộc ranh giới đang xét** phải khớp kiểu đã khai; lệch là hợp đồng đã trôi. **Tốt hơn `grep` một lần: một test khoá hai chiều** — `tests/unit/presentation/ui/screens/backtest/test_backtest_view_contract.py` (`EPIC-013B`) duyệt source bằng `ast`, đỏ khi dùng mà chưa khai **và** khi khai mà không ai dùng (tình trạng `IView`), đồng thời khoá **số đếm** (so tập hợp thì xoá 1 thêm 1 triệt tiêu nhau mà vẫn xanh). Bắt buộc ở `presentation/`: tầng đó bị **loại khỏi cổng `mypy`** (`pyproject.toml`, `EPIC-002A`), nên Protocol ở đây không có cơ chế tĩnh nào kiểm — không test thì chỉ là tài liệu.

**View chọn lúc bootstrap, không thay lúc runtime.** Presenter **không** phải chịu được việc bị tráo View giữa chừng: chọn View nào là quyết định lúc bootstrap, đọc từ config, inject vào `__init__`. Hợp đồng vẫn phải tường minh (khai `IBacktestView` để consumer lập trình vào được và `mypy` kiểm được), nhưng **cấm** coordinator/presenter cache `self._view` rồi giả định bất biến để tối ưu — `BUG-013`: một widget con cached có thể là C++ object đã `deleteLater()` sau khi host dựng lại. Bất biến ở đây là *danh tính View*, không phải *các widget bên trong nó*.

---

## 3. Clean Architecture Layer Enforcement

- Always strictly respect the 4 Layers: **Domain** (Pure) $\rightarrow$ **Application** (Use Cases/Ports) $\rightarrow$ **Interface Adapters** (CLI/UI Presenters) $\rightarrow$ **Infrastructure** (DB/API/Frameworks).
- Never leak Infrastructure concerns (like `sagittarius_engine` base classes, SQLAlchemy, or API clients) into the Domain or Application layers.
- Prioritize building reusable abstraction base layers (base cards, base dialogs, base presenters/view models) over concrete duplication.
- **Shared Kernel — đúng 2 ký hiệu, không hơn** (`EPIC-008`'s ADR §4.1): `src/domain/` và `src/application/` chỉ được import **duy nhất** `sagittarius_engine.domain.i_domain_event.IDomainEvent` và `sagittarius_engine.domain.base_event.BaseEvent`.

  **Lý do:** mọi domain event phải kế thừa `BaseEvent` để engine dựng được registry/catalog và tool audit (event nào tồn tại, ai nghe, chạy bao lâu); copy `BaseEvent` sang Elite sẽ tạo hai cây kế thừa không nhận ra nhau — đúng thứ registry sinh ra để tránh. Đây là **Shared Kernel** theo nghĩa DDD: vùng nhỏ, có tên, ghi thành luật, hai bên cùng sở hữu.

  **Mọi thứ khác của engine PHẢI qua port** trong `src/application/ports/`, adapter bọc nó ở `src/infrastructure/engine_adapters/`. `EPIC-008F` đã dựng 3 port: `IEventPublisher` (thay `IEventBus`), `IConfigReader` (thay `IConfig`), `ICommandDispatcher` (thay `IDispatcher`). **Tầng Presentation không bị ràng buộc này** — được biết engine trực tiếp (`BasePresenter`, `QtEventBridge`, `IEventBus.on/off`); chiều **nghe** event chỉ xảy ra ở đó, `IEventPublisher` cố ý chỉ có chiều **phát**.

  **Có test khoá:** `tests/unit/domain/test_indicator_script_conventions.py` giữ allow-list đúng 2 đường dẫn module trên, cộng 1 test chặn việc nới allow-list thành prefix (nới thành prefix là cả engine lọt lại vào domain mà không test nào biết). Kiểm tay:
  ```bash
  grep -rn "sagittarius_engine" src/domain src/application --include=*.py
  ```
  Thêm import engine nào khác vào 2 tầng đó là **sai**, kể cả "chỉ dùng 1 method" — đúng lý do `IConfigReader`/`ICommandDispatcher` tồn tại.

---

## 4. Use Case Structure (CQRS)

- Every Application Use Case must reside in its own dedicated directory (e.g., `src/application/use_cases/<my_use_case>/`).
- The Command/Response definition must be separated from the Handler logic into multiple files (e.g., `command.py` and `handler.py`), and then exported cleanly via `__init__.py`.
- Never import engine-specific interfaces (like `sagittarius_engine.extensions.cqrs.ICommand`) into the Application layer. Use the layer's own pure Python `ICommandHandler` / `IQueryHandler` interfaces.

---

## 5. Abstraction-Level Separation

Chia nhỏ là mặc định: **càng nhiều file càng tốt**; gộp phải có lý do, tách thì không cần xin phép.

1. **Không chung file:** hai thứ **khác abstraction level** MUST NOT nằm cùng một file. Một interface/Port và implementation của nó; một base class và các subclass; một policy trừu tượng và cách nó đọc đĩa — mỗi thứ một file.
2. **Không chung thư mục:** các file **khác abstraction level** MUST NOT chung một `dir`. Thư mục là một tầng, không phải cái sọt: `interfaces/` không chứa implementation, `widgets/` (nguyên thuỷ dùng chung) không chứa màn hình cụ thể, `domain/` không chứa adapter hạ tầng. Thư mục đang trộn hai tầng thì tách thư mục con theo tầng, đừng đổi tên file cho gọn.
3. **Đối trọng duy nhất là Single-Scope Cohesion** ([`code-quality-rule.md`](code-quality-rule.md)), và nó chỉ thắng khi các định nghĩa mô tả **cùng một vòng đời** (enum + ma trận của cùng 1 FSM; `StyleRole` + `_build_qss()`). "Cùng feature", "cùng màn hình", "hay dùng chung lúc" **không** đủ để gộp.
4. **Ngưỡng buộc phải tách** (`EPIC-007` §3.4, áp cho mọi code mới): file **>400 dòng** hoặc lớp **>15 phương thức công khai**. Chạm ngưỡng là tách, không thương lượng.
5. **Phân xử nhanh:** *"Đổi thứ A có bắt buộc phải đọc/sửa thứ B không?"* Có → cùng vòng đời, chung file được. Không → khác tầng, tách. Chứng cứ: `data_management_widgets.py` (**1.156 dòng**) vô tình thành thư viện widget chung của cả app vì trộn nguyên thuỷ dùng chung với widget riêng của 1 màn — 3 file ở 2 màn khác phải import chéo vào nó (`EPIC-007` §1).

---

## 6. Event Placement — Qt signal hay Event Bus?

Câu hỏi không phải "signal hay bus", cũng không phải "signal cầu nối là nợ kỹ thuật", mà là: **ai sở hữu sự thật này?**

> **Sự thật riêng của MỘT màn** → Qt signal nội bộ.
> **Sự thật của HỆ THỐNG, hoặc ≥2 màn cần** → Event Bus + đúng **một** Feed chuẩn hoá.

### 6.1 Tách hai vấn đề đang hay bị gộp

| | Vấn đề | Cơ chế đúng |
| :-: | :--- | :--- |
| **A** | Đưa dữ liệu từ thread nền về main thread **an toàn** | Qt queued signal **hoặc** `QtEventBridge` — cả hai đều đúng |
| **B** | **Ai được biết về ai**; một sự thật bị xử lý lặp ở mấy nơi | Bus + đúng 1 subscriber chuẩn hoá (Feed), nhiều nơi *hiển thị* |

**Qt queued signal chính là cơ chế Qt thiết kế ra cho (A)** — không phải nợ kỹ thuật, không phải workaround. Signal bắc cầu worker → main thread là code **đúng**, đừng "dọn" nó. `QtEventBridge` chỉ thay được signal phát ra **từ handler của event bus**; worker nền không đi qua bus thì bridge không giúp gì — xoá signal của nó là đẩy cập nhật UI sang worker thread, đúng lớp lỗi [`BUG-031`](../../Tasks/bug_report/completed/BUG-031_cross_thread_timer_start_hangs_ui_during_backtest.md).

### 6.2 Phân loại — hỏi đúng một câu

*"Nếu màn khác cũng muốn biết chuyện này, nó có vô lý không?"*

- **Vô lý** → sự thật riêng tư (`history load xong`, `stream của tôi start được`, `indicator của tôi tính xong`): Qt signal nội bộ trong presenter/controller. Đẩy lên bus là **rò rỉ** — mọi màn đều nghe được, bề mặt coupling phình ra.
- **Hợp lý** → sự thật hệ thống (`health đổi`, `task nền chết`, `sync tiến độ`, `log`): lên bus, **đúng một** Feed nghe và chuẩn hoá, nhiều màn *hiển thị*.

### 6.3 Thăng cấp khi consumer thứ hai xuất hiện THẬT — không thăng trước

Luật về **định tuyến**, không phải về việc có tạo abstraction hay không (xem §7). Thăng cấp muộn thì rẻ (worker vốn đã emit *một cái gì đó*; đổi chỗ nó emit tới là sửa cục bộ); đẩy hết lên bus trước thì đắt và gần như không lùi được — sau đó không ai dám xoá subscriber nào vì không biết còn ai đang nghe.

### 6.4 Bằng chứng thật (đo 2026-08-25, `EPIC-008G`)

Đếm trên 3 presenter: **48 signal, 46 cái có đúng 1 nơi nghe.** Cái duy nhất fan-out là `ui_log_signal` (2 nơi) — đúng là sự thật hệ thống, tức đúng thứ *nên* thành Feed; code đã tự phân loại đúng từ trước. `EPIC-008G` §2 đặt chỉ tiêu "xoá 48 signal cầu nối" vì gộp nhầm (A) vào (B); đo thật thì **47/48 tồn tại vì (A)**, xoá được ≈1. **Đừng đặt chỉ tiêu theo số đếm signal** — sai ranh giới thì con số chỉ dẫn tới việc phá code đúng.

---

## 7. Code phải tự nói lên chính nó — cái gì hoãn lại hoặc đánh đổi thì phải có Interface

> **Nếu một thứ sẽ được phát triển sau, hoặc là một cái giá đã chấp nhận trả, thì trong code
> phải có một Interface / kiểu dữ liệu / test đại diện cho nó. Không được để nó chỉ nằm trong
> tài liệu.**

Tài liệu là thứ agent phải đi tìm mới thấy; kiểu dữ liệu đập vào mắt khi đọc code. Bằng chứng: `EPIC-008G` §2 đặt sai chỉ tiêu "xoá 48 signal cầu nối" dù người viết **có đủ** rule trong tay — vì chỗ khai báo signal không nói gì về việc chúng là cầu nối thread. Luật đúng mà code câm thì luật vô dụng.

### 7.1 Hai dạng, hai cách thể hiện

| Dạng | Bắt buộc phải có trong code |
| :--- | :--- |
| **Sẽ phát triển sau** (điểm mở rộng đã biết, giai đoạn sau đã chốt) | Một **type/ABC/base class** đóng vai điểm hạ cánh, kèm docstring ghi công thức mở rộng. Agent sau `grep` ra được, và bắt chước được. |
| **Cái giá đã chấp nhận trả** (đánh đổi có chủ đích) | Một **test khoá hành vi hiện tại** + docstring nói rõ mất gì, vì sao chấp nhận. Không phải chỉ một dòng ghi chú. |

- **Đánh đổi:** `EPIC-008F` bỏ `frozen=True` của 4 domain event để kế thừa được `BaseEvent` — không xoá test bất biến mà **đổi nó thành test khoá hành vi mới** (`test_signal_generated_event_is_no_longer_frozen`) kèm lý do và điều kiện khôi phục.
- **Điểm mở rộng:** `SystemErrorFeed` là Feed đầu tiên, `HealthFeed`/`SyncProgressFeed` đã chốt là sẽ có → phải có `BaseFeed` làm hợp đồng, để việc thăng cấp một sự thật riêng tư lên bus (§6.3) có **chỗ hạ cánh có tên**.

### 7.2 Luôn khuyến khích abstraction — class là một **hợp đồng**, không phải một cục code

> Khi viết một class, **đánh giá khả năng mở rộng và API của nó trước**, rồi mới viết thân.
> Mặc định là **có abstraction**: class phải là một **hợp đồng** với các class khác, không phải
> một khối implementation mà nơi khác phải biết ruột gan mới dùng được.

Khi thêm class mới, hỏi theo thứ tự: (1) **ai sẽ gọi nó, họ cần thấy gì?** — đó là API, thiết kế trước chứ không rút ra sau; (2) **chỗ nào có khả năng mở rộng?** (đổi backend, đổi nguồn dữ liệu, thêm biến thể) — chỗ đó phải là `abc.ABC` / Port để người sau thay được mà không phải sửa consumer; (3) **consumer có buộc phải biết chi tiết bên trong không?** — có thì hợp đồng chưa đủ, siết lại.

Abstraction ở đây **không** phải "đẻ thêm lớp trung gian cho có": nó là **bề mặt công khai của class phải lập trình vào được**, và điểm nào biết trước sẽ thay đổi thì có kiểu trừu tượng đại diện.

> ⚠️ Ngưỡng cũ *"chỉ tạo abstraction khi có ≥2 nhu cầu thật"* (`EPIC-006`'s ADR §4) **đã bị bỏ 2026-08-25**; `EPIC-006`'s ADR và `EPIC-007`'s design vẫn viện dẫn nó, đọc chúng phải biết là đã hết hiệu lực. Bài học còn giá trị: 4 stub card (`ActionCard`/`FormCard`/`StreamCard`/`TableCard`) sai không phải vì thiếu abstraction mà vì **đoán sai hình dạng** của thứ chưa tồn tại — khuyến khích abstraction là thiết kế API cho cái đang viết, không phải đoán trước cái chưa ai cần.

### 7.3 Không được lách bằng docstring

Docstring/comment là **bổ sung**, không phải thay thế. Comment giải thích *vì sao*; type và test mới là thứ **buộc** người sau đi đúng đường, và là thứ **vỡ ra** khi thực tế đổi. Quyết định chỉ sống trong prose thì không có gì phát hiện khi nó hết đúng — đúng cơ chế đã khiến `.agents/context/` mục ruỗng suốt 3 tuần (`EPIC-002`).
