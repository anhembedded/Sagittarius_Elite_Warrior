---
name: Local CI Execution Rule
description: Lệnh verification bắt buộc, các tầng test, và cách xử lý khi gate đỏ.
trigger: always_on
---

# CI Rule & Run Guide

**Phải có đúng MỘT lệnh là nguồn chân lý cho verification cục bộ.** Nếu repo
chưa có, tạo nó trước khi làm gì khác — một script tự tìm môi trường ảo, dựng
đúng biến môi trường, và chạy đủ các bước dưới.

```bash
<CI_CMD>
```

**Đừng thay một lần chạy gate bắt buộc bằng lệnh test thô.** Lệnh thô có thể
không boot dự án trong đúng môi trường import/runtime mà script dựng, và
thường bỏ mất bước quét log ở cuối.

---

## 1. Cổng bắt buộc — trước khi handoff, commit, merge, hay tuyên bố "xong"

`<CI_CMD>` phải chạy **tất cả**:

- **lint + format ở chế độ chỉ đọc** (`<LINT_CMD>`);
- **type check tĩnh** (`<TYPECHECK_CMD>`) trên `<SRC_DIR>` **và** `scripts/`
  **trong cùng một lần gọi** — chạy riêng lẻ có thể để lọt lỗi "implementer
  không đầy đủ" vì type checker khi đó không phân giải module định nghĩa
  interface trong cùng một pass;
- **toàn bộ test chính** (`<TEST_DIR>`);
- **tier boot/sanity chạy tuần tự** trong một job riêng;
- **coverage** với ngưỡng đã chốt;
- **guard test cho chính tài liệu agent**, nếu repo có agent chạy tự động —
  mọi đường dẫn mà prompt của chúng nhắc tới phải còn resolve được. Agent chạy
  không người trông thì một link gãy **fail lặng lẽ**: run vẫn kết thúc và vẫn
  báo thành công.

Gate phải exit `0`. **Test pass nhưng lint/format/coverage/sanity đỏ là một
lần verify THẤT BẠI**, không phải một lần handoff thành công.

Nếu type checker được gate ở một **baseline** thay vì ở zero (danh sách file
nợ cũ), thì: file **không** nằm trong danh sách phải sạch tuyệt đối, và danh
sách chỉ được **ngắn đi**, không bao giờ dài ra.

### Ngoại lệ — commit không đụng file code nào

Một commit mà diff **không** chạm file nào trong `<SRC_DIR>`, `<TEST_DIR>`,
`scripts/`, và không chạm file nào ảnh hưởng build/dependency/runtime
(manifest, lockfile, file cấu hình build) thì **không cần** chạy gate — không
có thay đổi code nào để test verify. Ví dụ: commit chỉ đụng tài liệu, task
file, `.agents/`.

Chạm **một** file có khả năng ảnh hưởng build/runtime/lint/type/test là vẫn
phải chạy đủ gate. Ngoại lệ này **không** áp dụng vì "phần lớn diff là docs";
nó chỉ áp dụng khi **không phần nào** của diff là code.

---

## 2. Chế độ chẩn đoán — không bao giờ đủ để thay gate

| Mục đích | Ví dụ | Thay được gate? |
| :--- | :--- | :---: |
| Feedback nhanh | chỉ chạy unit | **Không** |
| Chẩn đoán boot/DI | chỉ chạy sanity | **Không** |
| Tái hiện lỗi do song song | gate với 1 worker | **Không** |
| Chẩn đoán riêng test | gate, bỏ lint | **Không** |
| Chẩn đoán riêng static | gate, bỏ test | **Không** |

Mọi cờ "skip" là **công cụ chẩn đoán**. Chúng MUST NOT được dùng để né một
gate đang đỏ, để biện minh cho một commit, hay để đánh dấu task hoàn thành.

**Đừng tăng số worker để chạy nhanh hơn khi chưa đo.** Đo thật trên một máy 4
nhân: 6 worker → ~147s; 12 worker → ~150s. Gấp đôi worker **không đổi gì** —
worker vượt số nhân chỉ thêm tranh chấp. Kiểm `nproc` trước, và coi mọi con số
thời gian là của riêng từng máy.

---

## 3. Xử lý khi đỏ

1. **Đọc bước fail ĐẦU TIÊN và giữ lại output của nó.**
2. **Sửa root cause.** Không làm yếu assertion, không skip test, không hạ
   ngưỡng coverage, không thêm ignore rộng chỉ để gate xanh.
3. **Format là hành động tường minh của người phát triển, không phải của CI.**
   CI phải **read-only**: dùng chế độ `--check`, không bao giờ để CI tự sửa
   file. Một test runner làm đổi file không liên quan không phải một cổng chất
   lượng chấp nhận được. Chạy lệnh fix bằng tay, **review từng diff** (nhất là
   ở file không liên quan), rồi chạy lại gate.
4. **Không commit khi gate đỏ.** Nếu là một blocker ngoại cảnh đã xác định,
   báo cáo bằng chứng và **giữ nguyên** coverage bắt buộc, thay vì tuyên bố
   một thành công chưa verify.
5. **Định kỳ verify lại mọi ngoại lệ kiểu "known flaky/crashy".** Ở repo gốc,
   một thư mục test bị loại khỏi CI hơn một năm vì "flaky đã biết"; khi cuối
   cùng có người đo lại (7 lần chạy, cả tuần tự lẫn song song) thì **không tái
   hiện được lần nào** — nguyên nhân gốc đã bị xoá khỏi codebase từ lâu. Một
   ngoại lệ đứng mãi là chỗ một regression thật ẩn mình.

---

## 4. Bốn tầng test

Mỗi tính năng được verify qua đúng bốn tầng. **Mỗi tầng chỉ chứng minh hợp
đồng của chính nó**; tầng cao hơn không bao giờ thay thế coverage xác định của
tầng thấp hơn.

1. **Unit** — hàm thuần, hợp đồng dữ liệu, invariant, hành vi xác định của một
   component. Không boot app/DI container thật, không network, không chờ theo
   thời gian. *(Dựng trực tiếp một widget/component rời vẫn tính là Unit,
   miễn là không boot app thật.)*
2. **Integration** — hành trình người dùng/ứng dụng **xác định**, qua các
   collaborator **thật**, với ranh giới ngoài được seed/fake **cục bộ**. Nó
   chứng minh **luồng**, không phải một lời gọi private hay một kỳ vọng trên
   mock. Không bao giờ phụ thuộc dịch vụ ngoài thật.
3. **Sanity** — boot **thật**, nối dây DI thật, dựng view/controller thật.
   Không thao tác người dùng, không dispatch nền. Nó chứng minh **sức khoẻ
   composition**: app lắp ráp, resolve, và tắt **trong im lặng**.
4. **E2E** — một hành trình nhìn thấy được, qua **ứng dụng thật đang chạy**,
   khởi động từ entry point thật, với input thật của người dùng và output thật.
   Opt-in / chạy nightly, nhưng là **bằng chứng bắt buộc** cho thay đổi ở code
   render/tương tác và cho mọi defect GUI/runtime được báo.

**Component probe — không phải một tầng test, và không phải E2E.** Một script
dựng trực tiếp một mảnh rời (render thật, input thật) **không** đi qua entry
point hay wiring production — ví dụ chứng minh một widget chưa được tích hợp
đã chạy được. Nó là bằng chứng cục bộ hợp lệ cho **một mảnh chưa ai với tới
được từ app thật**. Nó **không** thay thế E2E: **ngay khi** tính năng đó trở
nên với tới được từ app thật, E2E trở thành bằng chứng bắt buộc. Probe xanh
chứng minh mảnh đó chạy trong cô lập; nó **không** chứng minh app chạy.

Một smoke check với dịch vụ ngoài là kiểm tra vận hành opt-in, **không** phải
tầng test thứ năm và không bao giờ là yêu cầu CI thường.

### 4.1 Vì sao đúng bốn tầng này — đọc theo V-model

Mỗi tier verify đúng cái artifact mà giai đoạn phát triển tương ứng sinh ra —
cùng ý tưởng ánh xạ tầng-với-tầng của V-model, **nhưng không** lấy phần tuần
tự kiểu thác nước của nó. Dự án ship tăng dần, nên bản đồ này đọc **theo từng
feature, tại thời điểm thật**, đối chiếu với việc feature đó đã được dựng tới
đâu — không phải lập kế hoạch trước cho cả hệ thống:

| Giai đoạn phát triển | Tầng test |
| :--- | :--- |
| Implement một module/hàm | **Unit** |
| Nối dây các collaborator trong một feature | **Integration** |
| Boot/composition toàn app | **Sanity** |
| Một mảnh đã dựng nhưng app thật chưa với tới | **Component probe** |
| Feature đã nối vào app thật đang chạy | **E2E** |

Luật thực dụng rút ra: **test đúng tới mức feature đã thật sự được tích hợp,
không bao giờ đi trước nó.**

### 4.2 Sanity phải scale bằng 0

- **Thêm một feature/màn hình thì thêm ZERO test vào tier sanity.** Mọi
  assertion ở đây phải **quét một nguồn sự thật thật** (mọi use case đã đăng
  ký, mọi route điều hướng được, mọi package màn hình trên đĩa) — không bao
  giờ là một test viết tay cho từng feature. Nếu một màn hình mới cần một test
  sanity mới thì các test sanity hiện có đã được viết sai.
- **Một lần boot thật cho cả session**, không phải mỗi test một lần.
- **Im lặng chính là assertion:** một guard autouse phải fail khi có bất kỳ
  message nào của framework, bất kỳ log record nào từ WARNING trở lên, hay bất
  kỳ `warning` nào phát ra trong boot/construct/shutdown. Exit code xanh
  **không** đủ.
- **Thay thế duy nhất được phép là ranh giới network, vẽ ở tầng CẤU HÌNH,
  không bao giờ ở một code path** — trỏ client thật vào một fake server cục
  bộ; **không bao giờ** tự viết một class thay thế cho một port. Chính hình
  dạng đó đã sinh ra hai bug thật (implementer giả bị bỏ quên sau khi
  interface đổi).
- **Không assertion nào ở tier này được nhắc tới một sự thật nghiệp vụ** —
  cái đó thuộc Integration.
- Có một lớp **chạy ngoài tiến trình** (khởi động entry point thật như một
  subprocess thật) — đó là tier duy nhất chứng minh được process **thật sự
  thoát**, chứ không chỉ chứng minh hàm teardown trả về.

---

## 5. Bắt buộc: ghi log ra file rồi QUÉT nó

**Exit code xanh không phải bằng chứng đủ rằng một lần chạy là sạch.**

Script gate phải **ghi lại toàn bộ mỗi lần chạy ra file log**, rồi tự quét file
đó tìm các mức có vấn đề (`WARNING`, `ERROR`, `CRITICAL` — xem
[`logging-rule.md`](logging-rule.md)) bằng đúng matcher mà file đó công bố, và
**fail run nếu tìm thấy**. Làm việc này **trong script**, không phải bằng tay
mỗi lần.

```bash
<CI_CMD> > /tmp/ci.log 2>&1
grep -nE '\- (WARNING|ERROR|CRITICAL) \-' /tmp/ci.log
```

**Mọi hit đều PHẢI được điều tra và báo cáo** — không bao giờ được lặng lẽ
chấp nhận vì "test vẫn pass", và không bao giờ được bỏ qua bằng cờ
"cho-phép-warning" chỉ để có build xanh. Báo cáo từng hit là một trong hai:

- **(a) một defect thật** — khi đó đi theo
  [`bug-fix-rule.md`](bug-fix-rule.md) đầy đủ; hoặc
- **(b) một điều kiện kỳ vọng đã hiểu và biện minh được**, nêu rõ lý do.

*"Nó có sẵn từ trước khi tôi sửa"* là lý do để **kiểm xem đó có phải một bug
đang mở đã biết hay không**, không phải lý do để bỏ qua.

> **Vì sao có luật này:** một lần chạy có thể exit `0` trong khi ghi log một
> đường chạy đã **suy giảm lặng lẽ** — ví dụ thật: một vòng lặp ghi WARNING ở
> **mỗi bước của mỗi lần chạy** vì một điều kiện so sánh không bao giờ khớp
> giá trị thật (mỗi bước bị xử lý hai lần), và một truy vấn trả về `rows=0`
> tạo ra một biểu đồ trắng — **không chỗ nào fail cả**.

---

## 6. Tier benchmark

Benchmark là **chẩn đoán, không phải gate**. Báo cáo của nó là bằng chứng cục
bộ để ước lượng, phát hiện regression, và ra quyết định release — **không phải**
ngưỡng dùng chung trong CI.

---

## 7. Gate cục bộ và CI trên máy chủ không phải bản sao của nhau

Nếu repo có **cả hai**, hãy biết trước khác biệt trước khi coi một trong hai
là đủ:

| | Gate cục bộ | CI trên máy chủ |
| :--- | :--- | :--- |
| Test chính | thường song song | thường tuần tự |
| Sanity | job riêng, tuần tự | có thể trộn chung |
| Coverage / lint / type check | ? | ? |

**Điền bảng này bằng cách đọc cả hai file cấu hình, không phải bằng trí nhớ.**
Ở repo gốc, một dòng trong chính file rule này từng khẳng định "dự án không có
CI trên máy chủ" — sai, workflow tồn tại và đang chạy. Xác nhận bằng
`ls .github/workflows/` (hoặc tương đương), đừng tin tài liệu. Và **đừng giả
định một bên bao trùm bên kia.**
