# BOT-119: Thứ tự boot phụ thuộc hoàn toàn vào thứ tự gọi `app.use()`

## 1. Bối cảnh & vấn đề thật

Phát hiện 2026-08-23, cùng đợt audit chéo với
[BOT-118](BOT-118_broken_state_tokens_import_in_test.md).

`src/main.py` đăng ký 6 extension/module, và thứ tự đúng đang được giữ **chỉ
bằng thứ tự dòng code**, có chỗ ghi hẳn thành comment:

```python
app.use(DependencyValidatorExtension([...]))
app.use(AssetValidatorExtension())
app.use(LoggerExtension())
app.use(ThreadManagerExtension())

# Load Domain Module (Registers Repositories & UseCases)
app.use(BinanceBotModule())

# Load Health Check Diagnostic Extension after domain modules
app.use(HealthExtension())
```

Dòng comment `# ... after domain modules` chính là vấn đề: **một ràng buộc
thứ tự thật đang được mã hoá bằng tiếng Anh trong comment, chứ không phải
bằng code.** Đổi chỗ hai dòng `app.use()` là hỏng, và không có gì báo.

Quét cả repo: **không có extension nào của app này khai báo `dependencies`.**

## 2. Engine hỗ trợ khai báo — chỉ là chưa dùng

`ExtensionManager._build_and_sort()` của engine làm **topological sort thật**
trên thuộc tính `dependencies`, khớp theo `descriptor.name`. Khai báo rồi thì
thứ tự `app.use()` không còn quan trọng.

Engine đã xác minh điều này bằng thực nghiệm và ghi lại trong
`examples/student_management/docs/module_registration.md`: đảo ngược thứ tự
hai lời gọi `app.use()` mà vẫn boot sạch, miễn là có khai báo. App mẫu
(`StudentManagementExtension`) hiện dùng đúng cách này:

```python
dependencies: ClassVar[list[str]] = ["DatabaseExtension"]
```

Đây đúng là loại "practice đã chốt ở app mẫu" mà quy trình cross-check này
sinh ra để phát hiện.

## 3. Yêu cầu

1. Xác định ràng buộc thứ tự **thật** giữa 6 thành phần trong `src/main.py` —
   dựa trên cái gì bind vào container và cái gì resolve ra, không dựa vào thứ
   tự hiện tại. Thứ tự hiện tại chạy được không có nghĩa nó phản ánh đúng
   ràng buộc; nó chỉ là một thứ tự thoả mãn.
2. Khai báo `dependencies: ClassVar[list[str]]` trên các extension của app,
   dùng tên class như engine yêu cầu (khớp `descriptor.name`).
3. **Viết test đảo thứ tự `app.use()` rồi assert vẫn boot được.** Đó mới là
   thứ chứng minh ràng buộc đã thành khai báo chứ không còn ngầm định — không
   có nó thì khai báo `dependencies` cũng chỉ là comment loại khác.
4. Xoá các comment mô tả thứ tự (`# ... after domain modules`) sau khi ràng
   buộc đã nằm trong code.
5. `BinanceBotModule` đang kế thừa `BaseModule` (đường `IModule` legacy —
   engine gọi thẳng trong code của nó là *"a legacy IModule"*). Cân nhắc
   chuyển sang `IExtension` luôn trong lúc làm, vì `dependencies` là cơ chế
   của `IExtension`. Nếu quyết định giữ legacy thì ghi lý do lại.

## 4. Ưu tiên

P3 — hiện đang chạy đúng, không có bug. Đây là giảm nợ về độ giòn: sửa trước
khi có người đổi thứ tự và mất nửa ngày dò.

## 5. Phân loại

Bootstrap / Engine integration
