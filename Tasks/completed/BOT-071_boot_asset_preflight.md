# Hoàn thành: BOT-071 — Pre-flight kiểm tra asset UI lúc boot (fail-fast thay vì fallback im lặng)

**Trạng thái:** ✅ Hoàn thành
**Ngày hoàn thành:** 2026-08-17
**Loại tác vụ:** Engine Hardening / UI Asset Integrity (Lớp lỗi F)
**Độ phức tạp:** 🟢 S (Fast Agent)

---

## 1. Vấn đề giải quyết

Khi một file icon SVG bị xóa hoặc thất lạc (do `git reset`, conflict merge hay cấu trúc thư mục bị thay đổi), `IconLoader` fallback sang tạo icon trong suốt rỗng và chỉ ghi log warning. Điều này từng làm 7 icon (`sliders`, `chevron-down`, `briefcase`, `save`, `rotate-ccw`, `shield`, `zap`) biến mất và UI hiển thị icon trắng ở production mà không ai phát hiện cho tới khi user báo cáo (`BUG-002`).

Mục tiêu của `BOT-071` là đưa cơ chế kiểm tra **Pre-flight Asset Validation** vào quá trình boot app (`create_app`):
- Trong **Dev mode** (`dev.mode=True`): Fail-fast ngay lập tức bằng `CRITICAL FAULT` và thoát với mã lỗi `sys.exit(1)`, hiển thị rõ tên icon bị thiếu và đường dẫn kỳ vọng (ngăn chặn tình trạng app ship với icon trắng do `git reset` hoặc merge conflict).
- Trong **Production mode** (`dev.mode=False`): Ghi log `WARNING` và cho phép fallback an toàn để tránh làm gián đoạn trải nghiệm người dùng cuối.

---

## 2. Các thay đổi đã thực hiện

1. **`src/presentation/ui/assets/asset_validator_extension.py`**:
   - Định nghĩa `AssetValidatorExtension(IExtension[Any])` kế thừa lifecycle extension của Sagittarius Engine.
   - Khai báo danh sách `REQUIRED_UI_ICONS` gồm đầy đủ 29 SVG icon assets chuẩn hóa của ứng dụng.
   - Triển khai phương thức `boot()` kiểm tra tính tồn tại của từng file `.svg` trong thư mục `src/presentation/ui/assets/icons/`.
   - Phân nhánh hành vi dựa trên cờ `dev.mode` từ `IConfig`.

2. **`src/presentation/ui/assets/__init__.py`**:
   - Export `AssetValidatorExtension` và `REQUIRED_UI_ICONS`.

3. **`src/main.py`**:
   - Đăng ký `app.use(AssetValidatorExtension())` bên trong `create_app()`.

---

## 3. Bộ kiểm thử 4 tầng (Test Pyramid Verification)

Tuân thủ nghiêm ngặt tiêu chuẩn kim tự tháp kiểm thử 4 tầng theo `.agents/rules/code-rule.md` & `.agents/rules/ci-rule.md`:

1. **Tầng 1 — Static Quality (Lint & Format)**:
   - `ruff check src tests`: ✅ 0 lỗi.
   - `ruff format --check src tests`: ✅ 326 files formatted.

2. **Tầng 2 — Unit Tests (`tests/unit/`)**:
   - [`tests/unit/presentation/ui/test_asset_validator_extension.py`](file:///c:/Users/hoang/Documents/Sagittarius-Elite-Warrior/tests/unit/presentation/ui/test_asset_validator_extension.py):
     - `test_all_declared_required_ui_icons_exist_on_disk`: Guard test bảo đảm toàn bộ 29 icon trong `REQUIRED_UI_ICONS` thực sự tồn tại trên disk.
     - `test_preflight_passes_cleanly_when_all_assets_exist`: Xác thực preflight hoàn tất khi đủ assets.
     - `test_preflight_fails_fast_in_dev_mode_when_asset_is_missing`: Xác thực `CRITICAL FAULT` + `sys.exit(1)` trong dev mode.
     - `test_preflight_warns_and_continues_in_production_mode_when_asset_is_missing`: Xác thực log warning và không crash trong production mode.
     - `test_preflight_custom_subset_passes`: Xác thực custom icon subset và custom directory.

3. **Tầng 3 — Application & Integration Tests (`tests/integration/`)**:
   - [`tests/integration/presentation/test_asset_preflight_integration.py`](file:///c:/Users/hoang/Documents/Sagittarius-Elite-Warrior/tests/integration/presentation/test_asset_preflight_integration.py):
     - `test_asset_preflight_integration_passes_in_production_mode`: Tích hợp đa thành phần giữa `App`, `ConfigManager` và `AssetValidatorExtension`.
     - `test_asset_preflight_integration_fails_fast_in_dev_mode_with_broken_assets`: Kiểm tra vòng đời boot thực sự của App fail-fast khi thiếu asset ở dev mode.
     - `test_asset_preflight_integration_warns_and_continues_in_production_with_missing_assets`: Kiểm tra vòng đời boot thực sự của App cảnh báo và tiếp tục chạy ở production mode.

4. **Tầng 4 — Sanity Tests (`tests/sanity/`)**:
   - [`tests/sanity/test_asset_preflight_sanity.py`](file:///c:/Users/hoang/Documents/Sagittarius-Elite-Warrior/tests/sanity/test_asset_preflight_sanity.py):
     - `test_asset_validator_extension_is_wired_in_real_create_app`: Sanity DI wiring kiểm tra `create_app()` đăng ký đúng extension vào `app.modules`.
     - `test_asset_validator_boots_cleanly_in_real_app_boot`: Sanity Boot kiểm tra khởi động App thật hoàn tất sạch sẽ không ngoại lệ đối với assets thật trên ổ đĩa.

---

## 4. Kết quả xác thực CI (`.\scripts\ci-local.ps1 -Full`)

- **Ruff Lint & Format**: ✅ Passed (0 error, 326 files formatted).
- **Unit & Integration Tests**: ✅ 940 passed (100%).
- **Sanity Tests**: ✅ 27 passed (100%).
- **Coverage**: ✅ 94.02% (vượt ngưỡng 80%).
