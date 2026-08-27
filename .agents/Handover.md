# Handover — phiên gần nhất, và việc phải làm tiếp

**Chốt lúc:** 2026-08-25 · **Elite** `f0e63ca` (`master-warrior`) · **Engine** `2d9154b` (`main`)
Cả hai repo: cây sạch, đã push, không còn commit chờ.

> **File này bị THAY THẾ mỗi phiên, không được nối thêm.** Bản trước dài 585 dòng gồm 3 mục
> "session handover" chồng lên nhau từ 19–20/08, và tới cuối đời nó phải mang một khối cảnh báo
> ở đầu để nói rằng phần lớn nội dung bên dưới **đã sai** (chart native đã bị xoá, hai repo
> không còn là submodule). Một file handover mà người đọc phải tự lọc đúng-sai thì tệ hơn không
> có. Bối cảnh lịch sử đã nằm trong `git log`, trong task file đã đóng và trong `Tasks/reports/` —
> đó mới là nơi giữ nó. Bản cũ: `git show f0e63ca:.agents/Handover.md`.
>
> **Phân vai để không có 2 nguồn sự thật:** file này giữ thứ **thay đổi mỗi phiên** (đang ở đâu,
> làm gì tiếp, vừa quyết định gì). [`ONBOARDING.md`](ONBOARDING.md) giữ thứ **ổn định** (quy
> trình, lệnh gate, bẫy cố hữu, quyền hạn). Đừng chép qua lại.

---

## 1. Việc tiếp theo: `EPIC-007A`, ở repo **Engine**

[`EPIC-007`](../Tasks/epics/EPIC-007_chuan_hoa_card_dung_chung/README.md) — chuẩn hoá card dùng
chung, 0/7. Bảng thứ tự trong README của nó có cột **Repo**; ba task đầu (`007A`–`007C`) nằm ở
`Sagittarius_Engine`, bốn task sau ở đây. Không nhảy cóc — bảng xếp theo rủi ro tăng dần.

```bash
cd ../Sagittarius_Engine && git pull
```

`007A` làm hai việc: mở rộng guard `find_bare_qt_base_widgets` để bắt cả `QWidget` (regex hiện
chỉ khớp `QFrame|QDialog`, nên 7 widget của Elite lọt), và hiện thực `ConfirmOverlay` /
`PickerOverlay` — hai lớp mà `widgets/overlay.py` đang **nhắc tên trong thông báo lỗi nhưng
chưa từng tồn tại**. Việc thứ hai phải mở `BUG` bên Engine trước khi sửa (phát biểu sai sự thật
về code = BUG theo luật repo đó), file task đã ghi rõ.

**Bắt buộc đọc trước khi gõ dòng đầu:** [`EPIC-007/README.md`](../Tasks/epics/EPIC-007_chuan_hoa_card_dung_chung/README.md)
và 4 sơ đồ PlantUML ở `EPIC-007/design/` (2 as-is, 2 to-be). ADR ghi lại những quyết định đã
tranh luận xong — tự suy luận lại tốn một phiên và thường ra kết quả khác.

> ### ⚠️ Một câu trong `EPIC-007A` đã bị luật mới phủ định
>
> `007A` §2 viết *"cả hai đều thoả kỷ luật ≥2 instance thật"*, và `EPIC-007` §3.3 dựng trên
> cùng ngưỡng đó. **Ngưỡng "≥2 nhu cầu thật mới được tạo abstraction" đã bị user xoá khỏi
> `architecture-rule.md` ngày 2026-08-25** (commit `ca45e0f`). Luật hiện hành ngược lại:
> abstraction **luôn được khuyến khích**; viết một class thì phải cân nhắc khả năng mở rộng và
> API của nó, vì class là một **contract** với các class khác.
>
> Không có nghĩa là đẻ bừa lớp trung gian — `EPIC-006`'s ADR §2 có bài học thật: 4 stub
> `ActionCard`/`FormCard`/`StreamCard`/`TableCard` của kit QML cũ tự biến mất khi phát hiện
> `setEnabled()` của Qt đã làm sẵn việc đó. Nhưng lý do loại chúng là **"Qt đã có rồi"**, không
> phải **"mới có 1 consumer"**. Khi làm `007A`, đừng dùng câu ≥2 đó để biện minh cho bất cứ
> quyết định nào; sửa luôn câu chữ trong file task nếu nó chặn đường.

### Việc khác đang mở, nếu `EPIC-007` bị chặn

| | |
| :--- | :--- |
| `EPIC-001` 1/2 · `EPIC-002` 4/5 · `EPIC-003` 3/6 (1 huỷ) · `EPIC-004` 3/4 | Elite — đều dở dang, mở README từng epic |
| `BUG-030`, `BUG-034` | 2 bug Elite đang mở, chưa ai nhận |
| Tháo kit QML của Engine | **Chưa có file task.** Bị chặn bởi một quyết định chưa hỏi user: lật default của sample app sang `qfluentwidgets`, hay tách kit thành extension tuỳ chọn. Elite đã hết `.qml` nên nó không chặn gì bên này |
| 66 link hỏng trong `Tasks/` | Có từ trước, cố ý hoãn sang một commit `docs:` riêng |

---

## 2. Phiên vừa rồi đã làm gì

**`EPIC-008` đóng 8/8** (`bf88b51`…`9af4ea5`) — chuẩn hoá luồng event. Elite giờ có 3 Feed
(`SystemErrorFeed`, `HealthFeed`, `SyncProgressFeed`) ở `presentation/ui/common/`, 3 port
(`IEventPublisher`, `IConfigReader`, `ICommandDispatcher`) + adapter tương ứng, và 4 guard chạy
trong CI. Bên Engine: `BaseEvent` equality, `EventRegistry` cảnh báo trùng tên, bus không nuốt
lỗi, `QtEventBridge`.

**`EPIC-006` đóng 6/6** (`0112839`) — Elite **hết sạch `.qml`** (xoá 22 file + 2 test phụ thuộc,
4.978 dòng). Kit QML bên Engine **ở lại** vì sample app cần nó.

**Bookkeeping** (`8b049b5`, `f0e63ca`) — `EPIC-005F` đóng (do `006D/E` làm), `EPIC-003D` huỷ,
và thêm quy ước `cancelled/` cho bố cục epic.

## 3. Quyết định đắt tiền — đừng suy luận lại từ đầu

**`EPIC-008G` §2 dừng theo chính kill criterion của nó, không phải bỏ dở.** Nó định xoá các
signal "cầu nối" của presenter để worker bắn thẳng lên UI. Đo thật: **47/48 signal đang bắc cầu
*thread*, không phải bắc cầu *bus handler*** — hai chuyện hoàn toàn khác nhau mà task file gộp
làm một. Qt queued signal là cơ chế **đúng** cho thread affinity. Xoá chúng là tự tay tạo ra
lỗi cross-thread. Bằng chứng quyết định nằm trong chính docstring hợp đồng của
`stream_lifecycle_controller.py`. Ba presenter giờ có banner tiếng Việt ngay trên chỗ khai báo
signal — **đọc trước khi xoá bất kỳ signal nào**.

**Guard thứ 5 bị bỏ, cố ý.** Nó sẽ báo đỏ đúng cái pattern Feed mà epic vừa dựng. Một guard
false-positive tệ hơn không có guard, vì người ta sẽ học cách bỏ qua nó.

**4 domain event mất `frozen=True`.** Python cấm dataclass `frozen` kế thừa dataclass không
`frozen`, và `BaseEvent` không thể `frozen` vì có subclass tự viết `__init__`. Đây là đánh đổi
đã ghi rõ trong docstring của cả 4 và trong test đã viết lại — không phải sơ suất. Nếu định
"sửa lại cho đúng", đọc docstring trước.

**Đặt chỗ event = ai sở hữu nó, không phải nó tiện cho ai.** Riêng một màn → Qt signal. Toàn hệ
thống / ≥2 màn → bus + đúng **một** Feed. Luật đầy đủ: `architecture-rule.md` §6, và guard 3
ép được nó.

**Shared Kernel: đúng 2 symbol của Engine** (`IDomainEvent`, `BaseEvent`) được phép xuất hiện
trong `domain/`+`application/` của Elite. Mọi thứ khác đi qua port.

**Luật mới, áp cho mọi task từ đây:** thứ gì đã quyết làm sau, hoặc đánh đổi đã chấp nhận, thì
**trong code phải có Interface/type/test nói lên điều đó** — code tự nói lên chính nó, không
để luật nằm mồ côi trong file rule. (`architecture-rule.md` §7)

## 4. Bẫy phát hiện trong phiên này, chưa nằm ở file rule nào

- **`Mock(spec=...)` chặn được tên method, không chặn được kiểu trả về.** Method chưa cấu hình
  trả về một `Mock` trần, và nó đi thẳng vào handler thật. Đây là nguồn của 2 lỗi mà `EPIC-008`
  §4 làm lộ ra — §4 **phơi bày** chứ không **gây ra** chúng (đã A/B bằng `git stash` để chứng
  minh, trước khi kết luận).
- **`StdLogger.__init__` xoá sạch handler** của `logging.getLogger("App")`. Hai instance cùng
  bọc một logger stdlib — tạo instance thứ hai là giết log của instance thứ nhất.
- **`__init_subclass__` đăng ký lúc class được thực thi.** Muốn test va chạm tên thì phải
  **định nghĩa** class thứ hai, gọi hàm đăng ký bằng tay không tái hiện được.
- **`\bevent_bus\b` không khớp `self._event_bus`** — `_` là word character. Đã trượt một lượt
  vì bẫy này; luôn kiểm lại bằng lượt grep thứ hai sau mỗi lần rename bằng regex.
- **`trigger: always_on` trong frontmatter `.agents/rules/*.md` không phải Claude Code đọc** —
  đó là quy ước của 7 file `.agents/Skills/*.prompt.md` (dời từ `.jules/`,
  `EPIC-012`, 27/08). Claude Code chỉ tự nạp
  [`CLAUDE.md`](../CLAUDE.md) (thêm 2026-08-25, `0de5403`), và file đó **chỉ điều hướng**.

## 5. Đã bỏ khỏi file này, và tại sao

Bản cũ có mục "Test-writing gotchas" ~8 gạch đầu dòng về `Repeater`/`findChild`,
`mapToItem`, `ensurePolished`, `SizeRootObjectToView`, `ScrollBar.qml`, `OverlayHost`. **Toàn
bộ là bẫy của QML, và Elite giờ có 0 file `.qml`** — giữ lại chỉ khiến người đọc tưởng repo này
còn chạy QML. Chúng vẫn có thể còn giá trị cho kit QML bên **Engine**; nếu cần, lấy ở
`git show f0e63ca:.agents/Handover.md`.

Cũng bỏ: mục "What this project is" và "Where the actual rules live" — trùng
[`ONBOARDING.md`](ONBOARDING.md) §1/§2/§9 và [`CLAUDE.md`](../CLAUDE.md), mà bản trùng thì đã
kịp trôi sai (nó vẫn mô tả hai repo là superproject/submodule suốt 4 ngày sau khi tách). Mục
"How to verify a change" bỏ vì `ci-rule.md` §7 + `ONBOARDING.md` §5 mới là chủ sở hữu — bản
trong Handover từng khẳng định có `.github/workflows/ci.yml` "chạy đúng lệnh này", trong khi
repo **không có thư mục `.github/` nào cả**.
