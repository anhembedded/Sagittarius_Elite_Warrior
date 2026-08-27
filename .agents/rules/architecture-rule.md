---
name: Architecture Rule
description: SOLID, Clean Architecture layer boundaries, Ports/Adapters and ABC completeness, hợp đồng phải tường minh (cấm duck-typing ngầm — ABC mặc định, Protocol chỉ khi kế thừa bất khả thi), CQRS use-case structure, và Abstraction-Level Separation (khác abstraction level thì không chung file, không chung thư mục).
trigger: always_on
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

### 2.1 Hợp đồng phải tường minh — cấm duck-typing ngầm (user chốt 2026-08-27)

> **Mọi hợp đồng vượt ranh giới (Presenter ↔ View, consumer ↔ port, module ↔
> module) PHẢI là một kiểu có tên. Không được để hợp đồng chỉ tồn tại dưới
> dạng "gọi thử xem có method đó không".**

**Chữ "duck-typing" bị cấm ở đây là *duck-typing ngầm*, KHÔNG phải
`typing.Protocol`.** Phân biệt này là bắt buộc, vì đọc nhầm sẽ đi phá 18 chỗ
đang đúng (9 Protocol ở `src/` của repo này, 9 ở Engine):

| | Cấm | Bắt buộc |
| :--- | :--- | :--- |
| **Hợp đồng ngầm** | `def __init__(self, view)` không annotation, rồi consumer gọi 15 thành viên của nó; `hasattr()`/`getattr()` để dò khả năng | — |
| **Hợp đồng tường minh** | — | Một kiểu có tên: `abc.ABC` **hoặc** `typing.Protocol` |

`typing.Protocol` **là** một interface class tường minh: nó có tên, có
`grep` ra được, `mypy` kiểm được, `@runtime_checkable` thì `isinstance()`
được. Thứ nó bỏ đi chỉ là **bắt buộc kế thừa** — chứ không phải bỏ hợp đồng.

#### Thứ tự chọn — không được đảo

1. **`abc.ABC` là mặc định.** Implementer `class X(IPort)`, và luật "ABC
   completeness" ở §2 ngay trên áp dụng đầy đủ.
2. **`typing.Protocol` (kèm `@runtime_checkable`) chỉ khi kế thừa bất khả thi
   hoặc bị chính repo này cấm** — và **docstring của Protocol đó PHẢI ghi lý do
   thuộc nhóm nào dưới đây.** Đúng 3 lý do hợp lệ, cả 3 đều đã có tiền lệ thật:
   - **(a) Implementer là subclass `QObject`.** PySide6/Shiboken cấm một class
     kế thừa hai base dẫn xuất từ `QObject`, và `ABCMeta` xung đột metaclass
     với metaclass của Shiboken — biến nó thành ABC là **không chạy được**,
     không phải "xấu hơn". Tiền lệ: `kit/style.py` module docstring (lý do
     `apply_role()` là composition thay vì mixin), `LogModel`, `ITab`,
     `IStateContributor`, `IBacktestChartHost`.
   - **(b) §2 "NO Multiple Inheritance" chặn.** Implementer đã có base class
     riêng của nó (`BasePresenter`, `QMainWindow`, ...) và thêm một base nữa
     là đúng thứ §2 cấm.
   - **(c) Implementer là class của bên thứ ba** mà repo này không sửa được.
3. **Không rơi vào (a)/(b)/(c) → phải là ABC.** "Protocol tiện hơn" không phải
   lý do.

#### Protocol không phải lối thoát khỏi tính đầy đủ

Một `Protocol` phải mô tả **đúng và đủ** những gì consumer thật sự dùng. Thêm
một lời gọi mới lên hợp đồng mà không khai báo nó vào Protocol là **quay lại
đúng duck-typing ngầm mà mục này cấm**, chỉ khác là có một file trông giống
interface đứng cạnh để trấn an. Khác biệt so với ABC: bỏ sót ở ABC thì
`TypeError: Can't instantiate abstract class` nổ ngay; bỏ sót ở Protocol thì
**không có gì nổ cả** cho tới khi `mypy` chạy — nên với Protocol, `mypy`
(`EPIC-002`) không phải "backstop cơ học" mà là **cơ chế duy nhất**.

#### Bằng chứng thật, đo 2026-08-27

`backtest_presenter.py` + 6 coordinator + `signal_wiring.py` gọi **14 thành
viên** của `view`: `chart_cards`, `chart_controls`, `render_symbol_cards`,
`set_view_model`, `set_chart_mode`, `set_chart_host_factory`,
`set_chart_dev_mode`, `set_chart_opengl_enabled`,
`set_chart_cached_interaction_enabled`, `set_display_timezone`,
`set_volume_visible`, `set_trade_flags_visible`, `on_preview_data_ready`,
`on_backtest_data_ready` — **không kiểu nào khai báo chúng.** Engine's
`BasePresenter.__init__(self, view, container)` để `view` **không có
annotation**.

(Quét cả thư mục ra **15**; cái thứ 15 là `resize`, và nó đến từ `preview.py` —
một harness dev tự dựng `BackTestView()`, không phải ranh giới Presenter↔View.
Đây là lý do bước "xem từng hit đến từ đâu" ở dưới không được bỏ.)

Engine *có* `IView`, nhưng nó khai đúng 1 method `bind()` mà **không View nào
trong cả hai repo implement**, và `src/` của repo này tham chiếu `IView`
**0 lần**. Hợp đồng thật (15 thành viên) và hợp đồng khai báo (1 method chết)
là hai thứ khác nhau — đó chính xác là cái giá của duck-typing ngầm: hợp đồng
trôi mà không có gì vỡ ra.

Lệnh kiểm khi nghi một hợp đồng đang ngầm:

```bash
# Consumer đang dùng những gì của `x`? (bỏ -h để thấy hit nào ở file nào)
grep -rnoE "(self\.)?_?<tên_thuộc_tính>\.[a-zA-Z_]+" src/<thư_mục>/
```

Số thành viên còn lại **sau khi loại các hit không thuộc ranh giới đang xét**
phải khớp với kiểu đã khai báo. Lệch là hợp đồng đã trôi.

**Tốt hơn `grep` một lần: một test khoá hai chiều.** `grep` là thứ phải nhớ
chạy; test thì tự chạy. `tests/unit/presentation/ui/screens/backtest/test_backtest_view_contract.py`
(`EPIC-013B`) duyệt source bằng `ast` và đỏ ở **cả hai chiều** — thành viên được
dùng mà chưa khai (hợp đồng lại thành ngầm), **và** thành viên đã khai mà không
ai dùng (đúng tình trạng của `IView`). Nó còn khoá **số đếm**, vì hai chiều kia
so *tập hợp* nên xoá 1 thêm 1 sẽ triệt tiêu nhau và vẫn xanh.

Điều này đặc biệt quan trọng ở `presentation/`: tầng đó bị **loại khỏi cổng
`mypy`** (`pyproject.toml`, `EPIC-002A`), nên một `Protocol` sống ở đây **không
có bất kỳ cơ chế tĩnh nào** kiểm. Không có test kiểu trên thì nó chỉ là tài
liệu.

#### View được chọn lúc bootstrap, không thay lúc runtime (user chốt 2026-08-27)

Hệ quả trực tiếp của mục này, ghi ra để lần sau không ai thiết kế thừa: một
Presenter **không** phải chịu được việc bị tráo View giữa chừng. Việc chọn
View cụ thể nào là **quyết định lúc bootstrap, đọc từ config**, rồi inject
vào `__init__` — đúng hình dạng `BasePresenter` đang có.

Điều đó **không** làm hợp đồng bớt cần tường minh: lý do khai `IBacktestView`
là để consumer lập trình vào được và `mypy` kiểm được, chứ không phải để tráo
runtime. Nhưng nó **cấm** một thứ: coordinator/presenter **không được cache
`self._view` rồi giả định nó bất biến để tối ưu** — vì `BUG-013` đã cho thấy
một widget con cached có thể trở thành C++ object đã `deleteLater()` sau khi
host dựng lại. Bất biến ở đây là *danh tính View*, không phải *các widget bên
trong nó*.
---

## 3. Clean Architecture Layer Enforcement

5. **Clean Architecture Layer Enforcement:**
   - Always strictly respect the 4 Layers: **Domain** (Pure) $\rightarrow$ **Application** (Use Cases/Ports) $\rightarrow$ **Interface Adapters** (CLI/UI Presenters) $\rightarrow$ **Infrastructure** (DB/API/Frameworks).
   - Never leak Infrastructure concerns (like `sagittarius_engine` base classes, SQLAlchemy, or API clients) into the Domain or Application layers.
   - Prioritize building reusable abstraction base layers (base cards, base dialogs, base presenters/view models) over concrete duplication.
   - **Shared Kernel — đúng 2 ký hiệu, không hơn (user chốt 2026-08-24, `EPIC-008`'s ADR §4.1):** `src/domain/` và `src/application/` được phép import **duy nhất** hai ký hiệu này của engine:
     - `sagittarius_engine.domain.i_domain_event.IDomainEvent`
     - `sagittarius_engine.domain.base_event.BaseEvent`

     **Lý do có ngoại lệ:** user chốt mọi domain event phải kế thừa `BaseEvent` để engine dựng được registry/catalog và tool audit về sau (event nào tồn tại, ai nghe, chạy bao lâu). Một marker type dùng chung là điều kiện cần — copy `BaseEvent` sang Elite sẽ tạo hai cây kế thừa không nhận ra nhau, đúng thứ registry sinh ra để tránh. Đây là **Shared Kernel** theo nghĩa DDD: một vùng nhỏ, **có tên, được ghi thành luật**, hai bên cùng sở hữu — không phải "ngoại lệ cho tiện".

     **Mọi thứ khác của engine PHẢI qua port** trong `src/application/ports/`, và adapter bọc nó sống ở `src/infrastructure/engine_adapters/` — nơi được phép biết engine. `EPIC-008F` đã dựng 3 port cho đúng mục đích này: `IEventPublisher` (thay `IEventBus`), `IConfigReader` (thay `IConfig`), `ICommandDispatcher` (thay `IDispatcher`).

     **Tầng Presentation không bị ràng buộc này** — nó được phép biết engine trực tiếp (`BasePresenter`, `QtEventBridge`, `IEventBus.on/off`). Chiều **nghe** event chỉ xảy ra ở đó; `IEventPublisher` cố ý chỉ có chiều **phát**.

     **Có test khoá, không phải luật suông:** `tests/unit/domain/test_indicator_script_conventions.py` giữ allow-list đúng 2 đường dẫn module trên, cộng 1 test riêng chặn việc nới allow-list thành prefix (nới thành prefix là cả engine lọt lại vào domain mà không test nào biết). Kiểm tay bằng lệnh thật:
     ```bash
     grep -rn "sagittarius_engine" src/domain src/application --include=*.py
     ```
     Thêm bất kỳ import engine nào khác vào 2 tầng đó là **sai**, kể cả khi "chỉ dùng 1 method" — đó chính là lý do `IConfigReader`/`ICommandDispatcher` tồn tại thay vì import thẳng `IConfig`/`IDispatcher`.

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

---

## 6. Event Placement — Qt signal hay Event Bus? (user chốt 2026-08-25)

Câu hỏi **không phải** "signal hay bus", cũng không phải "signal cầu nối là nợ kỹ thuật".
Câu hỏi đúng là: **ai sở hữu sự thật này?**

> **Sự thật riêng của MỘT màn** → Qt signal nội bộ.
> **Sự thật của HỆ THỐNG, hoặc ≥2 màn cần** → Event Bus + đúng **một** Feed chuẩn hoá.

### 6.1 Tách hai vấn đề đang hay bị gộp

| | Vấn đề | Cơ chế đúng |
| :-: | :--- | :--- |
| **A** | Đưa dữ liệu từ thread nền về main thread **an toàn** | Qt queued signal **hoặc** `QtEventBridge` — cả hai đều đúng |
| **B** | **Ai được biết về ai**; một sự thật bị xử lý lặp ở mấy nơi | Bus + đúng 1 subscriber chuẩn hoá (Feed), nhiều nơi *hiển thị* |

**Qt queued signal chính là cơ chế Qt thiết kế ra cho (A).** Nó **không** phải nợ kỹ thuật,
không phải workaround, và **không** phải thứ cần xoá. Thấy một signal bắc cầu worker → main
thread thì đó là code **đúng**, đừng "dọn" nó.

`QtEventBridge` chỉ thay thế được signal nào phát ra **từ handler của event bus**. Worker chạy
nền mà không đi qua bus thì bridge không giúp gì — xoá signal của nó là đẩy cập nhật UI sang
worker thread, đúng lớp lỗi [`BUG-031`](../../Tasks/bug_report/completed/BUG-031_cross_thread_timer_start_hangs_ui_during_backtest.md).

### 6.2 Phân loại — hỏi đúng một câu

*"Nếu màn khác cũng muốn biết chuyện này, nó có vô lý không?"*

- **Vô lý** → sự thật riêng tư (`history load xong`, `stream của tôi start được`,
  `indicator của tôi tính xong`). Dùng Qt signal nội bộ trong presenter/controller.
  Đẩy lên bus là **rò rỉ**: mọi màn đều có thể nghe, bề mặt coupling phình ra, và nhìn code
  không còn biết ai phụ thuộc ai.
- **Hợp lý** → sự thật hệ thống (`health đổi`, `task nền chết`, `sync tiến độ`, `log`).
  Lên bus, **đúng một** Feed nghe và chuẩn hoá, nhiều màn *hiển thị*.

### 6.3 Thăng cấp khi consumer thứ hai xuất hiện THẬT — không thăng trước

Đây là quy tắc về **định tuyến** (sự thật này đi đường nào), không phải về việc có tạo
abstraction hay không — xem §7 cho luật abstraction. Lý do bất đối xứng:

- **Thăng cấp muộn thì rẻ:** worker vốn đã emit *một cái gì đó*; đổi chỗ nó emit tới là sửa cục bộ.
- **Đẩy hết lên bus trước thì đắt và gần như không lùi được** — sau đó không ai dám xoá
  subscriber nào vì không biết còn ai đang nghe.

### 6.4 Bằng chứng thật, đo 2026-08-25 (`EPIC-008G`)

Đếm trên 3 presenter: **48 signal, 46 cái có đúng 1 nơi nghe.** Cái duy nhất fan-out là
`ui_log_signal` (2 nơi) — và nó đúng là sự thật hệ thống, tức đúng thứ *nên* thành Feed.

Nói cách khác: **code đã tự phân loại đúng từ trước, chỉ là chưa ai đặt tên cho quy tắc.**
`EPIC-008G` §2 ban đầu đặt chỉ tiêu "xoá 48 signal cầu nối" vì gộp nhầm (A) vào (B); đo thật thì
**47/48 tồn tại vì (A)**, xoá được ≈1. Đã dừng theo đúng điều kiện dừng của chính task đó.

**Đừng đặt chỉ tiêu theo số đếm signal.** Sai ranh giới thì con số chỉ dẫn tới việc phá code đúng.

---

## 7. Code phải tự nói lên chính nó — cái gì hoãn lại hoặc đánh đổi thì phải có Interface (user chốt 2026-08-25)

> **Nếu một thứ sẽ được phát triển sau, hoặc là một cái giá đã chấp nhận trả, thì trong code
> phải có một Interface / kiểu dữ liệu / test đại diện cho nó. Không được để nó chỉ nằm trong
> tài liệu.**

Lý do: tài liệu là thứ agent phải **đi tìm mới thấy**; kiểu dữ liệu là thứ **đập vào mắt khi đọc
code**. Một quyết định chỉ ghi trong `.agents/` hoặc trong task file thì lần sau người khác sẽ
làm sai — không phải vì họ ẩu, mà vì code không hề gợi ý gì cả.

Bằng chứng thật: `EPIC-008G` §2 đặt chỉ tiêu "xoá 48 signal cầu nối". Người viết nó **có đủ**
rule trong tay. Vẫn đặt sai, vì chỗ khai báo signal trong code **không nói một chữ nào** về việc
chúng là cầu nối thread và xoá đi thì hỏng gì. Luật đúng mà code câm thì luật vô dụng.

### 7.1 Hai dạng, hai cách thể hiện

| Dạng | Bắt buộc phải có trong code |
| :--- | :--- |
| **Sẽ phát triển sau** (điểm mở rộng đã biết, giai đoạn sau đã chốt) | Một **type/ABC/base class** đóng vai điểm hạ cánh, kèm docstring ghi công thức mở rộng. Agent sau `grep` ra được, và bắt chước được. |
| **Cái giá đã chấp nhận trả** (đánh đổi có chủ đích) | Một **test khoá hành vi hiện tại** + docstring nói rõ mất gì, vì sao chấp nhận. Không phải chỉ một dòng ghi chú. |

Ví dụ thật trong repo này:

- **Đánh đổi:** `EPIC-008F` bỏ `frozen=True` của 4 domain event để kế thừa được `BaseEvent`.
  Không xoá test bất biến — **đổi nó thành test khoá hành vi mới**
  (`test_signal_generated_event_is_no_longer_frozen`) kèm lý do và điều kiện khôi phục. Mất mát
  nằm trong test suite, không nằm trong một dòng ghi chú ai cũng lướt qua.
- **Điểm mở rộng:** `SystemErrorFeed` là Feed đầu tiên; `HealthFeed`/`SyncProgressFeed` đã chốt
  là sẽ có. Vậy phải có `BaseFeed` làm hợp đồng, để "thăng cấp một sự thật riêng tư lên bus"
  (§6.3) có **chỗ hạ cánh có tên**, thay vì mỗi người tự chế một kiểu.

### 7.2 Luôn khuyến khích abstraction — class là một **hợp đồng**, không phải một cục code

> **Luật hiện hành (user chốt 2026-08-25).** Khi viết một class, **đánh giá khả năng mở rộng và
> API của nó trước**, rồi mới viết thân. Mặc định là **có abstraction**: class phải là một
> **hợp đồng** với các class khác, không phải một khối implementation mà nơi khác phải biết ruột
> gan mới dùng được.

Cụ thể, khi thêm một class mới, hỏi theo thứ tự:

1. **Ai sẽ gọi nó, và họ cần thấy gì?** Đó chính là API — thiết kế nó trước, không phải rút ra
   sau khi đã viết xong thân hàm.
2. **Chỗ nào có khả năng mở rộng?** (đổi backend, đổi nguồn dữ liệu, thêm biến thể). Chỗ đó
   phải là một `abc.ABC` / Port, để người sau thay được mà không phải sửa consumer.
3. **Consumer có buộc phải biết chi tiết bên trong không?** Nếu có → hợp đồng chưa đủ, siết lại.

Abstraction ở đây **không** có nghĩa "đẻ thêm lớp trung gian cho có". Nó có nghĩa: **bề mặt công
khai của class phải là thứ người khác lập trình vào được**, và điểm nào biết trước là sẽ thay đổi
thì điểm đó có kiểu trừu tượng đại diện.

> #### ⚠️ Đảo ngược `EPIC-006`'s ADR §4 — ghi rõ, không xoá lặng lẽ
>
> Luật cũ: *"chỉ tạo abstraction khi có ≥2 nhu cầu thật"* (lý do: nó đã chặn được 4 stub card
> `ActionCard`/`FormCard`/`StreamCard`/`TableCard` suy đoán từ docstring, 0 instance thật).
> **User bỏ luật này ngày 2026-08-25.** Từ nay **luôn khuyến khích abstraction**; ngưỡng "≥2 nhu
> cầu" **không còn là điều kiện chặn**.
>
> Ghi lại vì hai lý do: (a) `EPIC-006`'s ADR và `EPIC-007`'s design (`03_to_be_class.puml`,
> `README` §3.3) vẫn viện dẫn luật cũ như tiêu chí đang hiệu lực — đọc chúng phải biết là đã bị
> thay; (b) bài học chống lại vẫn còn giá trị: 4 stub kia sai **không** phải vì thiếu abstraction,
> mà vì chúng **đoán sai hình dạng** của thứ chưa tồn tại. Khuyến khích abstraction là khuyến
> khích **thiết kế API cho cái đang viết**, không phải khuyến khích đoán trước cái chưa ai cần.

### 7.3 Không được lách bằng docstring

Docstring/comment là **bổ sung**, không phải thay thế. Comment giải thích *vì sao*; type và test
mới là thứ **buộc** người sau đi đúng đường, và là thứ **vỡ ra** khi thực tế đổi. Một quyết định
chỉ sống trong prose thì không có gì phát hiện khi nó hết đúng — đúng cơ chế đã khiến
`.agents/context/` mục ruỗng suốt 3 tuần (`EPIC-002`).
