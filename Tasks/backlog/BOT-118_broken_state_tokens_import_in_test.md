# BOT-118: Import `QmlShared.state_tokens` đã chết trong test UI foundation

## 1. Bối cảnh & vấn đề thật

Phát hiện 2026-08-23 khi audit chéo toàn bộ bề mặt API mà app này dùng từ
`Sagittarius_Engine` (sau khi engine hoàn tất `EPIC-002`). Cùng quy trình đã
dùng cho [BOT-117](BOT-117_stale_pyside_mvc_paths_in_palette_docstring.md):
kiểm tra chéo, lập task, không sửa tại phiên phát hiện.

Cách audit: quét mọi `from sagittarius_engine... import ...` trong repo này
rồi thử import thật từng module và từng symbol với engine ở trạng thái hiện
tại.

**Kết quả tổng thể rất tốt:** 31 module engine được dùng, **281 symbol** —
chỉ **1** chỗ hỏng. App này bám API engine gần như sạch tuyệt đối.

Chỗ hỏng duy nhất:

```
tests/unit/presentation/ui/test_shared_ui_state_foundation.py
    from sagittarius_engine.extensions.pyside_mvc.QmlShared.state_tokens import ...
    ModuleNotFoundError: No module named
    'sagittarius_engine.extensions.pyside_mvc.QmlShared.state_tokens'
```

`state_tokens.py` đã được engine chuyển sang `pyside_mvc/tokens/` trong đợt
tái cấu trúc `EPIC-001B` (cùng đợt sinh ra BOT-117). Đường dẫn `QmlShared`
vẫn còn tồn tại nên các import khác của app không gãy — riêng `state_tokens`
thì đã đi.

## 2. Vì sao chưa ai thấy

Đây là file test. Nếu suite của app này đang chạy được thì hoặc test đó bị
skip, hoặc chưa được collect, hoặc suite đang chạy với engine bản cũ. Cần xác
minh — **khả năng test này im lặng không chạy còn đáng lo hơn bản thân cái
import hỏng.**

## 3. Yêu cầu

1. Đổi import sang đường dẫn thật. Kiểm tra trong engine xem nên dùng
   `pyside_mvc.tokens.state_tokens` hay re-export ở `pyside_mvc.tokens`
   (engine có `tokens/__init__.py` re-export sẵn — ưu tiên đường public).
2. **Xác minh test này thực sự chạy và pass**, không chỉ import được. Nếu nó
   đang bị skip/không collect thì xử lý luôn nguyên nhân đó.
3. Rà cả repo xem còn chỗ nào import qua `QmlShared` không, đối chiếu với
   rule no-deep-import của engine (`.agents/rules/ui-architecture.md`) — có
   thể gộp chung với BOT-117 vì cùng gốc là đợt tái cấu trúc đó.

## 4. Ưu tiên

P2 — không ảnh hưởng runtime production (chỉ nằm trong test), nhưng một test
không chạy là vùng mù, và nó cùng gốc với BOT-117 nên làm một thể thì rẻ.

## 5. Phân loại

Tests / Engine integration
