# Prompt yêu cầu AI thiết kế màn "Giao dịch" (`EPIC-021I`)

Dán nguyên khối dưới đây cho một AI thiết kế (Claude, GPT, v0, Figma AI…). Nó tự chứa — người
nhận không cần biết repo này.

Mọi con số màu/font/bố cục trong prompt đều lấy từ code thật (`assets/palette.py`,
`kit/page_shell.py`, `app_config.json`), không phải bịa. Khi palette đổi, sửa ở đây trước khi
dùng lại.

---

```text
Bạn là một product designer làm giao diện desktop cho phần mềm tài chính chuyên nghiệp.
Hãy thiết kế MỘT màn hình cho một ứng dụng desktop giao dịch tiền mã hoá đã tồn tại. Đây là
màn hình mới thêm vào một app đã có 4 màn khác, nên nó PHẢI trông như cùng một sản phẩm —
không phải một concept độc lập.

## Deliverable

Một file HTML + CSS tĩnh, khung 1600×1000px, không JavaScript, không thư viện ngoài, không
ảnh ngoài (icon dùng ký tự Unicode hoặc SVG inline). Tôi sẽ chụp màn hình nó và đặt cạnh
ảnh chụp app thật để so sánh, nên hãy vẽ đúng tỉ lệ và mật độ thông tin của một app desktop
thật, đừng vẽ kiểu landing page.

Vẽ BA trạng thái, xếp dọc, mỗi trạng thái là một khung 1600×1000 riêng có nhãn:
  A. Giao dịch TẮT — chưa có vị thế, chưa có lệnh (trạng thái mặc định khi mở app)
  B. Giao dịch BẬT — 1 vị thế đang mở, 2 lệnh đang chờ
  C. Vừa bấm "Dừng khẩn cấp" và nó THẤT BẠI MỘT PHẦN — lệnh đã huỷ xong, vị thế đóng không được

## Bối cảnh sản phẩm

App là một trading bot chạy chiến lược tự động trên Binance USD-M Futures Testnet (tiền giả
lập). Màn hình này là nơi người vận hành NGỒI NHÌN LIÊN TỤC trong lúc bot chạy: nó trả lời
"bot đang giữ gì, đang chờ gì, tài khoản còn bao nhiêu, và làm sao để dừng ngay lập tức".
Nó KHÔNG phải màn cấu hình (cấu hình ở màn Settings) và KHÔNG phải màn phân tích (biểu đồ và
backtest ở màn khác).

Người dùng là một người: chủ sở hữu bot, có kiến thức kỹ thuật, tự viết chiến lược.

## Ngôn ngữ

Mọi chữ hiển thị bằng TIẾNG VIỆT, trừ các thuật ngữ giao dịch giữ nguyên tiếng Anh vì đó là
cách sàn gọi: LONG, SHORT, MARKET, LIMIT, BUY, SELL, FILLED, NEW, PARTIALLY_FILLED,
CANCELED, tên symbol (BTCUSDT), và USDT.

## Hệ thiết kế BẮT BUỘC tuân thủ (đây là app đã có, không phải thiết kế mới)

Theme tối, tông đen/vàng. Dùng ĐÚNG các mã màu này, không thêm màu mới:

  Nền trang            #0a0a0c
  Nền sidebar          #0d0e11
  Nền thẻ/card         #111318
  Nền đầu thẻ          #15171d
  Viền                 #23262e
  Chữ chính            #e8e9ec
  Chữ mờ / nhãn        #848E9C
  Nhấn (vàng Binance)  #F3BA2F   ← dùng cho "thông tin", trạng thái đang chọn, nút chính
  Tăng / thành công    #0ECB81
  Cảnh báo             #d97706   ← "cần chú ý nhưng chưa hỏng gì"
  Giảm / nguy hiểm     #F6465D
  Nền nút thường       #17181d      hover  #1f2127
  Nền mục nav đang chọn: vàng #F3BA2F ở alpha 12%

Quan trọng: vàng và cam là HAI vai trò khác nhau. Vàng = thông tin/đang chọn. Cam = cảnh báo.
Đừng gộp, vì cạnh nhau chúng phải phân biệt được.

Font: JetBrainsMono Nerd Font (monospace), cỡ nền 10–11px, fallback Consolas/monospace. Toàn
bộ app dùng monospace — kể cả nhãn và tiêu đề. Số liệu tài chính căn phải và canh cột thẳng
hàng theo chữ số.

Bo góc: 6px là mặc định (thẻ, nút, ô nhập); 4px cho phần tử nhỏ (badge, tab); 8px cho thẻ lớn.
Không dùng bóng đổ lớn, không gradient, không glassmorphism.

## Bố cục BẮT BUỘC — app có một khung 4 dải dùng chung, màn này phải theo

Bên trái toàn app là một sidebar dọc hẹp (~180px) chứa các mục điều hướng có icon + nhãn:
Dev Board, Giao dịch (mục MỚI này — đang được chọn), Backtest Engine, Database, và ghim ở
đáy là "API & Credentials". Vẽ sidebar để thấy ngữ cảnh, nhưng đừng thiết kế lại nó.

Vùng nội dung bên phải sidebar chia làm 4 dải, từ trên xuống:

  1. HEADER      — tiêu đề màn hình + banner môi trường (xem bên dưới)
  2. CONTEXT BAR — hàng điều khiển ngang: chọn symbol, công tắc "Bật giao dịch",
                   trạng thái kết nối rút gọn, nút "Dừng khẩn cấp"
  3. WORKSPACE   — vùng chính, chia trái/phải: nội dung chính bên trái,
                   RAIL bên PHẢI rộng ~300px (kéo giãn được)
  4. CONSOLE     — dải nhật ký thấp ở đáy, cuộn được

Luật cứng: RAIL LUÔN Ở BÊN PHẢI, không bao giờ bên trái. Dải nào không có gì thì ẩn hẳn,
không để dải trống.

## Nội dung từng vùng

### Header — banner môi trường (đây là chi tiết quan trọng nhất của màn này)

Một dải ngang luôn hiển thị, nói cho người dùng biết tiền của họ đang đi đâu. Ba trạng thái,
ba màu, ba câu khác nhau:

  • Giao dịch tắt (dùng cho khung A) — tông xám/mờ:
    "Giao dịch đang TẮT. Chỉ xem dữ liệu."
  • Dữ liệu và lệnh cùng một nơi — tông vàng:
    "FUTURES TESTNET — tiền giả lập."
  • Dữ liệu mainnet nhưng lệnh testnet (dùng cho khung B và C) — tông CAM cảnh báo:
    "Biểu đồ đang hiển thị giá MAINNET, lệnh khớp trên TESTNET. Giá thấy ≠ giá khớp."

Trạng thái thứ ba là cái bẫy thật của sản phẩm này — hãy thiết kế nó để không thể bỏ sót,
nhưng cũng đừng để nó nhấp nháy hay chiếm chỗ như một modal. Nó sống ở đó suốt phiên làm việc.

### Context bar

  - Ô chọn symbol (ví dụ BTCUSDT) — dạng nút mở picker, không phải dropdown dài
  - Công tắc "Bật giao dịch" — TẮT mặc định. Đây là hành động có hệ quả tiền bạc: hãy làm nó
    khác biệt rõ với một checkbox thông thường, và ở trạng thái BẬT phải nhìn ra ngay từ xa
  - Trạng thái kết nối rút gọn: "✔ FUTURES TESTNET" hoặc "✘ Mất kết nối"
  - Nút "Dừng khẩn cấp" — nút nguy hiểm nhất màn hình. Không được bấm nhầm, nhưng khi cần
    thì phải tìm thấy trong một giây

### Workspace — bên trái, hai bảng xếp dọc

Bảng 1 — VỊ THẾ ĐANG MỞ, các cột:
  Symbol · Hướng (LONG/SHORT) · Khối lượng · Giá vào · Giá đánh dấu · PnL chưa thực hiện
  · Đòn bẩy · Giá thanh lý
  Dữ liệu mẫu khung B: BTCUSDT · LONG · 0.002 · 64,105.35 · 64,090.10 · -0.03 USDT · 5x
  · 32,140.00
  PnL âm tô đỏ #F6465D, dương tô xanh #0ECB81. Giá thanh lý là con số đáng sợ nhất bảng —
  hãy để nó đọc được nhưng đừng tô đỏ như thể đang có sự cố.

Bảng 2 — LỆNH ĐANG CHỜ, các cột:
  Thời gian · Symbol · Loại (MARKET/LIMIT) · Hướng · Khối lượng · Giá · Trạng thái · ID lệnh
  Dữ liệu mẫu khung B: hai lệnh LIMIT, một BUY một SELL, trạng thái NEW.
  ID lệnh dạng "SEW-a91f4c72e0b8" — dài, phải cắt bằng ellipsis chứ không được tràn đè cột
  bên cạnh.

Cả hai bảng ở khung A đều rỗng: hãy thiết kế trạng thái rỗng cho tử tế (một câu giải thích
vì sao rỗng, không phải một ô trắng).

### Workspace — rail bên phải: thẻ TÀI KHOẢN

  Số dư USDT khả dụng     14,871.60
  Margin đang dùng           128.20
  PnL chưa thực hiện          -0.03
  Lệnh đã đặt phiên này      1 / 20      ← có hạn mức, hãy thể hiện được là "1 trên 20"
  Chế độ vị thế             ONE_WAY
  Kiểu margin               CROSSED

### Console dưới đáy

Nhật ký lệnh, mỗi dòng có giờ + nội dung, dòng mới nhất ở dưới cùng. Ví dụ:
  14:35:02  Đã gửi lệnh SEW-a91f4c72e0b8 · BTCUSDT MARKET BUY 0.002
  14:35:02  Khớp đủ 0.002 @ 64,105.35 · phí 0.0026 USDT

### Khung C — Dừng khẩn cấp thất bại một phần

Sau khi bấm, hiện kết quả TỪNG BƯỚC, không phải một thông báo "đã dừng" chung chung:
  1. Tắt giao dịch ........................ ✔
  2. Huỷ lệnh chờ (2 lệnh) ................ ✔
  3. Đóng vị thế (1 vị thế) ............... ✘  Margin is insufficient
  → "THẤT BẠI MỘT PHẦN — còn 1 vị thế đang mở. Giao dịch đã tắt, không có lệnh mới."

Đây là trạng thái quan trọng nhất phải thiết kế đúng: một nút báo "đã dừng" trong khi vị thế
còn mở là lời nói dối nguy hiểm nhất trong toàn bộ sản phẩm. Người dùng phải hiểu trong hai
giây rằng cái gì đã xong và cái gì CHƯA.

## Ràng buộc — vi phạm là thiết kế không dùng được

  - Không thêm màu nào ngoài bảng trên. Không đổi vàng #F3BA2F sang màu khác.
  - Rail luôn bên phải. Không bao giờ bên trái.
  - Không dùng chiều rộng cố định cho mọi thứ — app này đã bị phàn nàn "fix size nhiều quá".
    Bảng phải giãn theo cửa sổ; chỉ rail có bề rộng khởi điểm ~300px.
  - Mọi chuỗi dài (thời gian có microsecond, ID lệnh) phải cắt bằng ellipsis, không được
    tràn đè cột bên cạnh. Đây là một lỗi thật đã xảy ra ở màn khác của app này.
  - Không modal, không popup, không toast trong ba khung này.
  - Không biểu đồ nến trong màn này. Biểu đồ ở màn khác.
  - Mật độ thông tin cao là ĐÚNG với sản phẩm này. Đừng để khoảng trắng rộng kiểu web
    marketing. Nhưng cũng đừng nhồi tới mức không còn thứ bậc thị giác.

## Kèm theo bản thiết kế, trả lời ngắn gọn

  1. Anh/chị thể hiện "giao dịch đang BẬT" khác "đang TẮT" bằng cách nào, và vì sao cách đó
     nhìn ra được từ xa mà không cần đọc chữ?
  2. Nút "Dừng khẩn cấp" đặt ở đâu và vì sao chỗ đó vừa dễ tìm khi hoảng, vừa khó bấm nhầm?
  3. Ba trạng thái banner môi trường phân biệt bằng gì ngoài màu (phòng khi người dùng
     không phân biệt được màu)?
```

---

## Ghi chú khi dùng lại prompt này

- **Đổi deliverable nếu cần:** thay đoạn "Deliverable" thành "một ảnh mockup" cho AI sinh ảnh,
  hoặc "một file Figma" cho công cụ khác. Phần còn lại giữ nguyên.
- **Ba câu hỏi cuối là cố ý.** Chúng ép người thiết kế nói ra lý do, và câu trả lời cho câu 3
  (phân biệt không chỉ bằng màu) là thứ hay bị bỏ sót nhất.
- **Không đưa ảnh chụp app hiện tại vào prompt** trừ khi muốn AI bắt chước bố cục cũ. Nếu muốn
  đối chiếu, chụp app **sau** khi có bản thiết kế, rồi so — đó là cách `EPIC-020` đã làm và là
  cách phát hiện được 4 lỗi bố cục thật.
- **Kết quả trả về không phải hợp đồng.** `EPIC-021I` mới là nơi chốt: mọi widget phải lấy từ
  `kit/` và `qml/` đã có (`TableCard`, `Banner`, `Badge`, `StyledButton`, `TabBar`, `LogPanel`,
  `DataRow`, `StyledProgressBar`), không dựng widget mới chỉ vì mockup vẽ khác một chút.
