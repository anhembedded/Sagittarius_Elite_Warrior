---
name: Code Quality Rule
description: Typing, readability, immutability/pure function, và các quy tắc chất lượng cứng — no magic number, no nested loop, no God object, no lazy import, Single-Scope Cohesion.
trigger: on_file_change
patterns:
  - <SRC_DIR>/**
  - scripts/**
---

# CODE QUALITY RULES

Áp cho mọi file mã nguồn trong `<SRC_DIR>` và `scripts/`.

Quyết định **kiến trúc** (interface nằm đâu, file nào thuộc tầng nào, tách file
theo abstraction level) không nằm ở đây — xem
[`architecture-rule.md`](architecture-rule.md).

---

## 1. Typing chặt

- Annotation tường minh cho **mọi** chữ ký hàm: tham số, giá trị trả về, thuộc
  tính của class.
- **Tránh tuyệt đối kiểu "bất kỳ"** (`Any`, `object`, `any`, `interface{}`).
  Cần linh hoạt thì dùng union, optional, generic, type variable.
- Dùng **kiểu có cấu trúc** (dataclass/struct/record, ưu tiên bất biến; hoặc
  model có validate) thay cho dict/map thô và tuple vô danh. Mô hình hoá dữ
  liệu bằng value object và enum thay vì primitive rời rạc.

## 2. Readability hơn brevity

- Theo style guide của ngôn ngữ. Ưu tiên code tường minh, tự giải thích, hơn
  one-liner ngắn.
- **Không** dùng comprehension lồng nhau phức tạp hay lambda nhiều dòng khi một
  vòng lặp rõ ràng hoặc một hàm phụ có tên dễ đọc hơn. Không dùng lambda cho
  callback không tầm thường.
- Hàm nhỏ, tập trung, một mục đích. Tên biến tường minh, mô tả được.

## 3. Immutability & pure function

- Hướng tới hàm thuần: chỉ phụ thuộc tham số truyền vào, trả về giá trị xác
  định.
- **Không bao giờ mutate tham số truyền vào tại chỗ.** Trả về instance mới
  hoặc bản copy đã sửa.
- **Tuyệt đối tránh mutable default argument** (kinh điển:
  `def f(items=[]):`).
- Cô lập side effect (I/O, DB, network) vào đúng class adapter/boundary.

## 4. Bốn luật cứng

- **No magic number & named constant.** Không dùng số hay chuỗi thô trong
  code. Khai báo tập trung thành hằng số có tên hoặc key cấu hình. Tham số của
  thuật toán/chiến lược phải khai báo qua schema tham số, không rải rác.
- **No nested loop.** Tránh lồng sâu vòng lặp. Rút logic bên trong thành hàm
  phụ để giảm độ phức tạp chu trình và tăng khả năng test.
- **No God object.** Không tạo class/module khổng lồ biết quá nhiều hoặc làm
  quá nhiều. Uỷ quyền (parse CLI, bootstrap, xử lý event) sang module riêng.
- **Abstract low-level logic.** Không viết thao tác hệ điều hành / hệ file
  chi tiết thẳng trong tầng application hay composition root. Rút ra utility.

## 5. No function-local / lazy import

**Mọi** import phải khai ở đầu file. Không đặt import bên trong hàm, method,
callback, test case, hay scope lồng nhau. (Ngoại lệ duy nhất: guard chỉ dành
cho type checker, vẫn đặt ở top level.)

Lazy import che giấu phụ thuộc vòng thay vì sửa nó, và làm chi phí import
xuất hiện ngẫu nhiên giữa runtime.

## 6. Single-Scope Cohesion & colocation

Các thành phần **gắn chặt** cùng mô tả **một** vòng đời, một state machine,
hay một cấu hình feature PHẢI ở cùng một file/scope — ví dụ điển hình: enum
State + enum Event + ma trận chuyển trạng thái + ánh xạ UI mode của **cùng
một** FSM.

**Không** rải các định nghĩa gắn chặt ra nhiều file, khiến việc hiểu hay sửa
một vòng đời phải nhảy qua 4-5 module rời rạc. Enum, schema, bảng chuyển
trạng thái, hằng số thuộc **một** khái niệm phải sống cùng nhau như một
single source of truth.

> **Đối trọng trực tiếp: Abstraction-Level Separation**
> ([`architecture-rule.md`](architecture-rule.md) §5) — "khác abstraction
> level thì không chung file, không chung thư mục", cộng ngưỡng buộc tách
> **>400 dòng/file** và **>15 method công khai/lớp**. Đọc **cả hai** khi lưỡng
> lự. Phân xử nhanh: *đổi A có bắt buộc phải sửa B không?* Có → chung file;
> không → tách.

---

## Phụ lục — ví dụ theo stack *(thay theo ngôn ngữ của bạn)*

| Luật | Python | TypeScript |
| :--- | :--- | :--- |
| Kiểu có cấu trúc | `@dataclass(frozen=True)`, Pydantic model | `interface` / `type`, `readonly`, zod schema |
| Tránh kiểu "bất kỳ" | cấm `Any`; dùng `Union`/`Optional`/`TypeVar` | `noImplicitAny`, cấm `any`; dùng generic, union |
| Bất biến | `frozen=True`, `tuple`, `MappingProxyType` | `readonly`, `as const`, `Object.freeze` |
| Guard cho type checker | `if TYPE_CHECKING:` | `import type { ... }` |
| Lint/format read-only | `ruff check` / `ruff format --check` | `eslint` / `prettier --check` |
