# Capital

Pilot #2 của `EPIC-015` bậc 1. Chọn vì nó là **đúng hình dạng `BUG-064`**: một ô nhập mà giá
trị phải tới được màn hình, và một kết quả validate phải tới được trạng thái `enabled` của nút.

Bản widget cần: nối `textChanged`, nối `capitalValidationMessageChanged`, và một hàm
`_sync_validation()` để giữ hai thứ đó khớp nhau — ba chỗ có thể lệch.

Bản QML: `text: vm.text`, `visible: vm.validationMessage !== ""`, `enabled: vm.canApply`.
Ba dòng khai báo, không có chỗ nào để lệch.

**Nhưng `apply()` vẫn tự kiểm `canApply` trong VM**, không tin vào `enabled:` của QML. Một luật
chỉ được giữ bởi một binding trong `.qml` là luật biến mất ngay khi ai đó sửa file `.qml` đó.
