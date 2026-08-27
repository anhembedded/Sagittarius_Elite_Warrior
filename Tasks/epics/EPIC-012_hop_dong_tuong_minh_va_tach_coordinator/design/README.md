# EPIC-012 — Design

Bốn sơ đồ **đã áp dụng** (không phải đề xuất). Mọi con số trong đó đo bằng
`ast` trên mã thật ngày 2026-08-27 — cách đếm ghi ở `footer` của từng file.

Mỗi `.puml` có một `.svg` render sẵn nằm cạnh — cùng quy ước với
[`EPIC-007/design/`](../../EPIC-007_chuan_hoa_card_dung_chung/design/), để đọc
được mà không cần cài gì. **Sửa `.puml` thì phải render lại `.svg` trong cùng
commit**, không thì đúng bệnh bản-sao-trôi mà `CLAUDE.md` đã cảnh báo.

| File | Trả lời câu hỏi gì |
| :--- | :--- |
| [`01_as_is_class.puml`](01_as_is_class.puml) | **Trước:** hợp đồng ngầm ở đâu, và vì sao `getattr(view, "chart_mode", OHLC)` là dạng tệ nhất của `Any` |
| [`02_to_be_class.puml`](02_to_be_class.puml) | **Sau:** 5 port, lý do ABC-hay-Protocol từng cái, và cơ chế test thay cho `mypy` |
| [`03_to_be_component.puml`](03_to_be_component.puml) | 6 → 8 coordinator, ranh giới vẽ theo **vòng đời**, và vì sao tổng tham số chỉ 74 → 71 |
| [`04_bootstrap_sequence.puml`](04_bootstrap_sequence.puml) | `EPIC-012F` — View chọn **một lần** lúc bootstrap, và những bước **không** tồn tại |

## Render

Cần **cả** `plantuml.jar` **và** `graphviz` — thiếu `dot` thì class/component
diagram ném `IOException: Cannot run program ".../dot"`, còn sequence diagram
vẫn render bình thường, nên "04 chạy được" **không** phải bằng chứng ba file
kia đúng.

```bash
sudo apt-get install -y graphviz
java -jar plantuml.jar -graphvizdot /usr/bin/dot -tsvg *.puml   # ghi đè .svg cạnh .puml

# Chỉ kiểm cú pháp, không sinh ảnh:
java -jar plantuml.jar -graphvizdot /usr/bin/dot -checkonly *.puml
```

`-checkonly` trên **nhiều file** chỉ in một dòng `Some diagram description
contains errors` mà **không nói file nào** — chạy từng file khi cần tìm.

## Một cái bẫy cú pháp đã dính

`class Tên as Alias #Màu { ... }` **không parse** (PlantUML 1.2024.7). Phải
đặt tên trong ngoặc kép khi vừa có alias vừa có thân:

```plantuml
class "ExecutionCoordinator" as EX #FFF9C4 {   ' đúng
class ExecutionCoordinator as EX #FFF9C4 {     ' Syntax Error
```

Cả 4 file trong thư mục này đã qua `-checkonly` và đã render ra PNG thật.
