---
name: Architecture Rule
description: SOLID, ranh giới tầng, Port/interface và tính đầy đủ của implementer, hợp đồng phải tường minh (cấm duck-typing ngầm), use case, Abstraction-Level Separation, đặt chỗ event, và luật "cái gì hoãn lại thì phải có type đại diện".
trigger: always_on
---

# ARCHITECTURE RULES

Đọc file này khi: thiết kế/tái cấu trúc, thêm hoặc đổi một interface, thêm một
use case, quyết định một thứ nên nằm ở file/thư mục nào, hoặc khi tách một
file/lớp đã quá ngưỡng.

Quy tắc chất lượng code thuần tuý (magic number, nested loop, typing,
immutability) **không** nằm ở đây — xem
[`code-quality-rule.md`](code-quality-rule.md).

> [!IMPORTANT]
> **Phương châm quyết định khi kiến trúc khó hoặc mơ hồ.**
> Nhiều hướng đều có lý, không có "đúng tuyệt đối" → quyết theo **design
> pattern đã được kiểm chứng**. **Không ngại redesign** một phần đã có nếu
> thiết kế hiện tại là *hard design* (cứng, chắp vá, khó mở rộng) — "đang chạy
> được" không phải lý do giữ nguyên. Khi phân vân: **tham chiếu cách các dự án
> lớn, đã được cộng đồng kiểm chứng, đang làm** — ưu tiên pattern có tên, có
> tiền lệ rộng, hơn tự sáng chế một hình dạng mới không ai kiểm chứng.
>
> Agent **tự quyết** theo phương châm này cho các quyết định thiết kế — không
> hỏi lại user cho từng lựa chọn nhỏ. Chỉ hỏi khi đánh đổi thật sự lớn, không
> đảo ngược được, hoặc vượt khỏi phạm vi thuần thiết kế (`push`, xoá, ghi đè —
> xem `../ONBOARDING.md` §6; phương châm này **không** nới nhóm đó).
>
> Nó quyết **hướng nào đúng**, không đổi **quy trình làm sao**: vẫn task +
> design/ADR trước khi code, vẫn qua đúng cổng CI và commit như cũ.

---

## 1. SOLID

Áp dụng ở nơi nó làm code rõ hơn / dễ test hơn; đừng ép abstraction lên một
mẩu code nhỏ, gần như chắc chắn không đổi, chỉ để tick vào ô.

- **S — Single Responsibility:** một class/module có **một** lý do để thay đổi.
  Tách theo trách nhiệm thành file riêng thay vì chất logic không liên quan
  vào cùng một chỗ.
- **O — Open/Closed:** ưu tiên mở rộng bằng class/strategy mới hơn là sửa
  logic đã được test; đặt điểm mở rộng sau một interface.
- **L — Liskov:** subclass phải chạy được ở mọi nơi base type của nó được kỳ
  vọng — không ném "chưa implement" ở method kế thừa, không thu hẹp input,
  không làm yếu bảo đảm mà base type đã hứa.
- **I — Interface Segregation:** interface hẹp và đúng vai; đừng bắt
  implementer thoả mãn method nó không dùng.
- **D — Dependency Inversion:** module cấp cao phụ thuộc abstraction, không
  phụ thuộc implementation cụ thể.

---

## 2. Abstraction & decoupling

- Định nghĩa abstraction tường minh cho repository, service, và mọi client ra
  ngoài hệ thống.
- Ưu tiên **Dependency Injection** hơn là khởi tạo cứng bên trong logic
  nghiệp vụ.
- **Không đa kế thừa.** Dùng composition; làm phẳng interface khi cần, để
  tránh thứ tự phân giải method phức tạp.
- **Mọi implementer của một interface phải luôn đầy đủ, ở mọi nơi.** Khi một
  interface có thêm method, **mọi** class implement nó phải được cập nhật
  trong **cùng một thay đổi** — không chỉ implementation chính ở production.
  `grep` implementer ở `<SRC_DIR>`, `scripts/`, **và** `<TEST_DIR>`.

  > **Bằng chứng thật:** một test double / script probe bị bỏ quên sau khi
  > interface đổi vẫn khởi tạo được cho tới đúng lúc có ai chạy nó, rồi nổ
  > `TypeError: Can't instantiate abstract class`. Lần thứ hai lọt là vì phạm
  > vi `grep` bỏ sót `scripts/`. **Linter không bắt được lớp lỗi này** —
  > verify tính đầy đủ của implementer xuyên file là việc của type checker.
  > Nhưng đừng chỉ dựa vào tool: `grep` vẫn phải làm như một phần của chính
  > thay đổi đó.

### 2.1 Hợp đồng phải tường minh — cấm duck-typing ngầm

> **Mọi hợp đồng vượt ranh giới (module ↔ module, consumer ↔ port, view ↔
> controller) PHẢI là một kiểu có tên. Không được để hợp đồng chỉ tồn tại
> dưới dạng "gọi thử xem có method đó không".**

| | Cấm | Bắt buộc |
| :--- | :--- | :--- |
| **Hợp đồng ngầm** | Tham số không annotation rồi consumer gọi 15 thành viên của nó; dò khả năng bằng `hasattr`/`getattr`/`in` | — |
| **Hợp đồng tường minh** | — | Một kiểu có tên: interface class **hoặc** structural type (Protocol / `interface` / trait) |

**Structural type có tên KHÔNG phải là duck-typing ngầm.** Nó có tên, `grep`
ra được, type checker kiểm được. Thứ nó bỏ đi chỉ là **bắt buộc kế thừa** —
không phải bỏ hợp đồng.

#### Thứ tự chọn — không được đảo

1. **Interface class kế thừa (ABC / `implements`) là mặc định**, và luật "tính
   đầy đủ của implementer" ở §2 áp dụng đầy đủ.
2. **Structural type chỉ khi kế thừa bất khả thi hoặc bị chính repo này cấm**
   — và docstring của nó **PHẢI ghi rõ lý do** thuộc nhóm nào:
   - **(a)** Kế thừa gây xung đột metaclass / framework cấm (nhiều framework
     UI không cho một class kế thừa hai base của framework).
   - **(b)** §2 "không đa kế thừa" chặn: implementer đã có base class riêng.
   - **(c)** Implementer là class của bên thứ ba mà repo này không sửa được.
3. **Không rơi vào (a)/(b)/(c) → phải là interface class.** "Tiện hơn" không
   phải lý do.

#### Structural type không phải lối thoát khỏi tính đầy đủ

Nó phải mô tả **đúng và đủ** những gì consumer thật sự dùng. Thêm một lời gọi
mới lên hợp đồng mà không khai báo vào type là **quay lại đúng duck-typing
ngầm**, chỉ khác là có một file trông giống interface đứng cạnh để trấn an.

Khác biệt về cách vỡ: bỏ sót ở interface kế thừa thì **nổ ngay lúc khởi tạo**;
bỏ sót ở structural type thì **không có gì nổ cả** cho tới khi type checker
chạy — nên với structural type, type checker không phải "lưới an toàn" mà là
**cơ chế duy nhất**. Ở tầng nào bị **loại khỏi phạm vi type check** (rất hay
gặp với tầng UI), một structural type sống ở đó **không có bất kỳ cơ chế tĩnh
nào** kiểm — nó chỉ là tài liệu.

#### Lệnh kiểm khi nghi một hợp đồng đang ngầm

```bash
# Consumer đang dùng những gì của `x`? (bỏ -h để thấy hit nào ở file nào)
grep -rnoE "(self\.)?_?<ten_thuoc_tinh>\.[a-zA-Z_]+" <SRC_DIR>/<thu_muc>/
```

Số thành viên còn lại **sau khi loại các hit không thuộc ranh giới đang xét**
phải khớp với kiểu đã khai báo. Lệch là hợp đồng đã trôi. (Bước "xem từng hit
đến từ đâu" không được bỏ: ở một lần đo thật, hit thứ 15 đến từ một harness
dev tự dựng object, không thuộc ranh giới đang xét.)

**Tốt hơn `grep` một lần: một test khoá hai chiều.** `grep` là thứ phải nhớ
chạy; test thì tự chạy. Test đó duyệt source và đỏ ở **cả hai chiều**: thành
viên được dùng mà chưa khai (hợp đồng lại thành ngầm), **và** thành viên đã
khai mà không ai dùng (hợp đồng chết). Nó còn phải khoá **số đếm** — hai chiều
kia so *tập hợp*, nên xoá 1 thêm 1 sẽ triệt tiêu nhau và vẫn xanh.

> **Bằng chứng thật:** một hợp đồng giữa hai lớp có **14 thành viên** được gọi
> thật, **không kiểu nào khai báo chúng**. Trong khi đó interface *chính thức*
> tồn tại trong codebase khai đúng 1 method mà **không implementer nào**
> implement và **không ai** tham chiếu. Hợp đồng thật và hợp đồng khai báo là
> hai thứ khác nhau — đó chính xác là cái giá của duck-typing ngầm: hợp đồng
> trôi mà không có gì vỡ ra.

---

## 3. Ranh giới tầng

- Tôn trọng nghiêm ngặt hướng phụ thuộc: **Domain** (thuần) → **Application**
  (use case / port) → **Interface Adapters** (CLI/UI, presenter) →
  **Infrastructure** (DB/API/framework). Phụ thuộc chỉ đi **vào trong**.
- Không bao giờ để mối bận tâm hạ tầng (ORM, HTTP client, base class của
  framework) rò vào Domain hoặc Application.
- Ưu tiên dựng base layer dùng lại được hơn là nhân bản implementation.

### 3.1 Shared Kernel — nếu có, phải đúng vài ký hiệu, được ghi thành luật, và có test khoá

Khi hai repo/module phải dùng chung vài kiểu (một marker type, một base
event), đó là **Shared Kernel** theo nghĩa DDD: một vùng nhỏ, **có tên, được
ghi thành luật, hai bên cùng sở hữu** — không phải "ngoại lệ cho tiện".

- Liệt kê **đúng và đủ** các ký hiệu được phép, bằng danh sách, không bằng
  prefix.
- **Mọi thứ khác phải đi qua port**, adapter bọc nó sống ở tầng hạ tầng.
- **Phải có test khoá allow-list đó**, cộng một test riêng chặn việc nới
  allow-list thành prefix (nới thành prefix là cả thư viện lọt lại vào domain
  mà không test nào biết). Kiểm tay:
  ```bash
  grep -rn "<ten_thu_vien>" <SRC_DIR>/domain <SRC_DIR>/application
  ```
- Thêm bất kỳ import nào khác vào 2 tầng đó là **sai**, kể cả khi "chỉ dùng 1
  method" — đó chính là lý do các port kia tồn tại.

---

## 4. Cấu trúc Use Case

- Mỗi use case ở thư mục riêng của nó.
- Định nghĩa Command/Response tách khỏi logic Handler (`command.py` +
  `handler.py` hoặc tương đương), export sạch qua entry point của package.
- Không import interface đặc thù của framework vào tầng Application — dùng
  interface thuần của chính tầng đó.

---

## 5. Abstraction-Level Separation

**Chia nhỏ là mặc định. Càng nhiều file càng tốt; gộp phải có lý do, tách thì
không cần xin phép.**

1. **Không chung file:** hai thứ **khác abstraction level** MUST NOT nằm cùng
   một file. Một interface và một implementation của nó; một base class và các
   subclass; một policy trừu tượng và cách nó đọc đĩa — mỗi thứ một file.
2. **Không chung thư mục:** các file **khác abstraction level** MUST NOT nằm
   chung một `dir`. Thư mục là một **tầng**, không phải một cái sọt:
   `interfaces/` không chứa implementation, thư mục nguyên thuỷ dùng chung
   không chứa widget riêng của một màn hình, `domain/` không chứa adapter hạ
   tầng. Thư mục đang trộn hai tầng thì **tách thư mục con theo tầng**, đừng
   đổi tên file cho gọn.
3. **Đối trọng duy nhất là Single-Scope Cohesion**
   ([`code-quality-rule.md`](code-quality-rule.md)), và nó **chỉ** thắng khi
   các định nghĩa mô tả **cùng một vòng đời**. "Cùng feature", "cùng màn
   hình", "hay dùng chung lúc" **không phải** cùng abstraction level và
   **không** đủ để gộp.
4. **Ngưỡng buộc phải tách:** một file **>400 dòng** hoặc một lớp **>15
   phương thức công khai**. Chạm ngưỡng là tách, không thương lượng.
5. **Phân xử nhanh khi lưỡng lự:** *"Đổi thứ A có bắt buộc phải đọc/sửa thứ B
   không?"* Có → cùng vòng đời, được chung file. Không → khác tầng, tách ra.

> **Bằng chứng thật:** một file 1.156 dòng vô tình trở thành thư viện widget
> chung của cả app vì trộn nguyên thuỷ dùng chung với widget riêng của một màn
> hình — 3 file ở 2 màn khác phải import chéo vào nó.

---

---

## 6. Hai chủ đề đã tách ra file riêng

Chúng khác abstraction level với phần trên (đây là luật về **cấu trúc tĩnh**;
hai file kia là luật về **luồng thông tin** và về **cách mã hoá ý định**) — nên
theo đúng §5 của chính file này, chúng không ở chung file:

| Câu hỏi | Đọc ở |
| :--- | :--- |
| Sự thật này đi bằng signal nội bộ hay Event Bus? | [`event-rule.md`](event-rule.md) |
| Thứ tôi hoãn lại / cái giá tôi chấp nhận trả phải xuất hiện trong code thế nào? | [`design-intent-rule.md`](design-intent-rule.md) |
