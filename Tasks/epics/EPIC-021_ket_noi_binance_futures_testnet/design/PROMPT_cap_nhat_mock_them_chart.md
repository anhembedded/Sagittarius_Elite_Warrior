# Prompt: cập nhật mockup màn "Giao dịch" — thêm chart

> **Đây là bản cập nhật cho mockup đã có, không phải thiết kế lại từ đầu.**
> Prompt gốc (palette, font, luật bố cục 4 dải, 3 trạng thái A/B/C):
> [`PROMPT_thiet_ke_man_giao_dich.md`](PROMPT_thiet_ke_man_giao_dich.md) — vẫn có hiệu lực, không
> lặp lại ở đây.
>
> **Về mức độ tự do:** phần dưới nói **cần gì và tại sao**, không nói **trông ra sao**. Bố cục,
> tỉ lệ, chỗ đặt chart, cách diễn đạt cảnh báo — anh quyết. Nếu khung 4 dải không chứa nổi chart
> một cách tử tế, **nói ra và đề xuất khác**, đừng ép cho vừa.

---

## Vì sao phải sửa

Review mockup hiện tại phát hiện thiếu hai thứ mà người vận hành cần nhìn liên tục: **chart giá
realtime kèm chiến lược**, và **chart vốn**. Bảng số thì biết *đang có gì*, nhưng không trả lời
được *tại sao bot vào lệnh ở đó* — mà đó chính là câu hỏi người ta nhìn màn này để hỏi.

---

## 1. Chart giá realtime + chiến lược — **làm ngay ở vòng này**

**Mục đích:** người vận hành phải phán đoán được một tín hiệu **mà không cần mở màn khác**.

Phải thấy được:

- Nến của symbol đang chọn, ở khung thời gian đang chạy.
- Đường chỉ báo **của chính chiến lược đang chạy** (ví dụ hiện tại là `ema_cross(9,21)` → hai
  đường EMA). Số lượng đường thay đổi theo chiến lược, không cố định.
- Mối liên hệ giữa chart và symbol/khung thời gian ở context bar — đổi symbol thì chart đổi theo.

### Hai ràng buộc hành vi, không phải ràng buộc thẩm mỹ

**1. Chart vẫn chạy khi giao dịch TẮT.** Nến là dữ liệu công khai, không cần API key. Ở trạng thái
A (Giao dịch TẮT), chart **không** được rỗng hay mờ đi như thể hỏng — nó vẫn chạy bình thường, chỉ
là không có lệnh nào được gửi. Trạng thái A hiện tại nói *"CHỈ XEM"* — chart chính là thứ đang
được xem.

**2. Giá trên chart KHÔNG phải giá khớp lệnh.** Đây là ràng buộc quan trọng nhất của mục này.

Nến đến từ **mainnet** (dữ liệu sạch, công khai). Lệnh khớp trên **testnet** (sổ lệnh riêng, giá
trôi lệch). Hai con số **khác nhau**, và người đọc mặc định sẽ tưởng chúng là một.

Thiết kế phải làm cho hiểu lầm đó **khó xảy ra**. Cách làm thế nào là quyền của anh — nhãn trên
chart, chú thích trục giá, gộp vào banner môi trường, hay cách khác. Chỉ cần đừng để một người mở
màn lần đầu nhìn giá trên chart rồi tưởng đó là giá mình vừa mua.

---

## 2. Chart vốn (equity) — **vòng sau, nhưng bố trí chỗ ngay bây giờ**

Đã tách thành task riêng (`EPIC-021M`) vì cần thêm hạ tầng dữ liệu. **Chưa cần vẽ chi tiết**, chỉ
cần bố cục dự trù được chỗ cho nó, để lần sau thêm vào không phải xếp lại cả màn.

Một đặc tính của dữ liệu sẽ định hình biểu đồ này — nói trước để anh không thiết kế nhầm:

> Điểm dữ liệu chỉ sinh ra **khi sàn báo có thay đổi**, không theo nhịp đồng hồ. Nên đường vốn có
> **khoảng cách không đều**, có thể phẳng lì rất lâu, và **có thể rỗng cả phiên** nếu không có lệnh
> nào. Đây là dữ liệu đúng, không phải lỗi — đừng thiết kế theo giả định "luôn có đường cong đẹp".

Trạng thái rỗng của nó cần đọc được là *"chưa có gì xảy ra"*, không phải *"hỏng"*.

---

## 3. Dữ liệu có thật — đừng vẽ cột không tồn tại

Phần này là ràng buộc cứng: mockup vẽ cột nào thì code phải lấy được dữ liệu cột đó.

| Vùng | Có thật | Ghi chú |
| :--- | :--- | :--- |
| Bảng vị thế | symbol, hướng, khối lượng, giá vào, giá đánh dấu, PnL chưa thực hiện, đòn bẩy, giá thanh lý | ✅ mockup hiện tại **khớp hết** |
| Bảng lệnh chờ | thời gian, symbol, loại, hướng, khối lượng, giá/trạng thái, ID lệnh | ✅ dữ liệu có thật. ⚠️ Cột `THỜI GIAN` **chưa chốt** lấy giờ của sàn hay giờ đóng dấu lúc nhận (`EPIC-021I` §3.1) — không ảnh hưởng bố cục, chỉ ảnh hưởng nhãn/chú thích nếu anh định ghi rõ nguồn giờ |
| Rail tài khoản | số dư USDT, margin đã dùng, PnL chưa thực hiện, số lệnh/hạn mức, chế độ vị thế, kiểu margin | ✅ khớp |
| Chart giá | nến + đường chỉ báo của chiến lược | ✅ có sẵn |
| Chart vốn | (thời điểm, vốn) | ⏳ `EPIC-021M` |
| **Marker lệnh trên chart** | — | ❌ **chưa** — thuộc `EPIC-021K`. Đừng vẽ mũi tên Buy/Sell trên chart ở vòng này |

Cần thêm cột nào ngoài bảng trên: **hỏi trước**, đừng vẽ rồi để người code phát hiện không có dữ
liệu.

---

## 4. Những điều phải giữ đúng (đã có trong prompt gốc, nhắc lại vì dễ vô tình phá khi thêm chart)

- Công tắc **Bật giao dịch luôn khởi đầu TẮT** mỗi lần mở app. Không có "nhớ trạng thái lần trước".
- **Không có lựa chọn mainnet.** Chỉ `TESTNET` hoặc tắt hẳn.
- Hạn mức là số thật: **20** lệnh/phiên · **500** USDT/lệnh · **1** vị thế/symbol · **60** giây
  giữa hai lệnh cùng symbol.
- **Dừng khẩn cấp** thuộc task sau (`EPIC-021K`). Giữ nút ở chỗ cũ, nhưng đừng đầu tư thêm vào nó
  ở vòng này.

---

## 5. Cần nhận lại gì

1. **Ba trạng thái cũ, cập nhật có chart**: A (TẮT) · B (đang chạy, có vị thế) · C (Dừng khẩn cấp
   thất bại một phần).
2. Riêng trạng thái B cho thấy chart lúc **thật sự có việc đang diễn ra** — đó là lúc màn này đáng
   nhìn nhất.
3. **Nói ngắn gọn** những gì anh đã đổi so với bản cũ và **vì sao** — nhất là chỗ nào phải hy sinh
   để nhét chart vào.
4. Nếu anh thấy một yêu cầu ở trên là sai hướng, **nói ra**. Bản mock là đầu vào để bàn, không phải
   hợp đồng phải tuân thủ từng chữ.
