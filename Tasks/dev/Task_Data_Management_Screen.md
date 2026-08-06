# Nhiệm vụ: Tích hợp Giao diện Data Management (Quản lý Dữ liệu)

## 1. Mục tiêu (Objective)
Cung cấp cho người dùng một giao diện trực quan để kiểm soát, theo dõi và đồng bộ dữ liệu lịch sử nến (klines) của từng đồng tiền (Symbol), hỗ trợ quá trình Backtest sau này.

## 2. Mô tả (Description)
Hệ thống Database (SQLite) đã hỗ trợ API kiểm tra khoảng hổng dữ liệu (`get_database_status`) cực kỳ nhanh bằng Window Functions.
Nhiệm vụ này sẽ kết nối hàm này với `DataManagementPresenter` để render ra một bảng điều khiển (Table) trên UI.

## 3. Các bước thực hiện (Action Items)
- [ ] Thiết kế lại giao diện bảng `DataManagementView` với các cột: Symbol, Khoảng thời gian, Nến đầu tiên, Nến cuối cùng, Tổng số nến, Số khoảng hổng (Gaps).
- [ ] Tại `DataManagementPresenter`, lắng nghe sự kiện khi view yêu cầu tải dữ liệu, và thực thi Query lấy thông tin status từ Repository.
- [ ] Đẩy kết quả vào bảng trên View để hiển thị.
- [ ] Bổ sung nút "Sync All" hoặc "Sync" từng hàng để người dùng tự do lấp đầy các khoảng dữ liệu bị thiếu.

## 4. Rủi ro / Lưu ý (Constraints & Risks)
- Đảm bảo các truy vấn lấy status không block Main UI Thread. Có thể sử dụng Background Task hoặc Signal/Slot.
