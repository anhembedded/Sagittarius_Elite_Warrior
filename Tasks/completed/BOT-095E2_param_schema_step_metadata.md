# Nhiệm vụ: BOT-095E2 — Step Metadata cho Strategy Parameter Schema

> Phụ thuộc được phát hiện khi triển khai BOT-095E.

## Vấn đề

`ScriptInput` chỉ mô tả `minval`/`maxval`; UI không có nguồn sự thật để biết
bước nhảy hợp lệ của một tham số số. Tự suy đoán theo tên strategy sẽ làm sai
contract schema.

## Mục tiêu

- Bổ sung `step` tùy chọn cho `input_int` và `input_float` trên cả Strategy và
  Indicator Script API.
- Schema QML chuyển tiếp metadata này nguyên vẹn.
- Khi không được khai báo, UI dùng mặc định minh bạch: `1` cho int, `0.1` cho
  float.
- Reject step không dương hoặc step cho input không phải số.

## Hoàn thành khi

- Stepper BOT-095E tôn trọng `min`/`max`/`step` từ schema.
- Unit test bảo vệ API và QML schema.

## Hoàn thành (2026-08-17)

- `step` đã được thêm và validate cho Strategy/Indicator schema.
- QML nhận metadata nguyên vẹn nhưng phép tính step/clamp chạy trong Python để
  không có hai nguồn sự thật.
- Covered bởi unit schema/normalisation test và Qt interaction test; Full CI
  xanh cùng BOT-095E.
