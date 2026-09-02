# Prompt vòng 3: mock màn "Giao dịch" — thiếu chỗ **cấu hình**, và thiếu lúc hệ thống **từ chối**

> **Cập nhật cho mock A/B/C đã có, không thiết kế lại.** Hai prompt trước vẫn có hiệu lực, không
> lặp lại ở đây:
> [`PROMPT_thiet_ke_man_giao_dich.md`](PROMPT_thiet_ke_man_giao_dich.md) (palette, font, 4 dải,
> 3 trạng thái) · [`PROMPT_cap_nhat_mock_them_chart.md`](PROMPT_cap_nhat_mock_them_chart.md)
> (chart giá, chart vốn, tách giá mainnet/testnet).
>
> **Mức độ tự do:** dưới đây nói **cần gì và tại sao**, không nói **trông ra sao**. Bố cục, chỗ
> đặt, cách diễn đạt — anh quyết. Nếu một yêu cầu ở đây làm hỏng bố cục 4 dải, **nói ra và đề
> xuất khác**, đừng ép cho vừa.

---

## Vì sao phải sửa

Bản A/B/C là ảnh **rất tốt** của một hệ thống **đang chạy đúng**. Nó thiếu hai nửa còn lại:

1. **Không có chỗ nào để cấu hình bot.** Chiến lược, tham số, khung thời gian, khối lượng vào
   lệnh — mock hiển thị cả bốn dưới dạng *chữ đã cố định*, không phải control.
2. **Không có ảnh nào của hệ thống đang từ chối.** Mock chỉ vẽ lúc mọi thứ trôi chảy, cộng đúng
   một thất bại (Dừng khẩn cấp). Nhưng phần lớn giá trị của app này nằm ở chỗ nó **chặn** —
   và chặn thì đang vô hình.

Giữ nguyên phần đã tốt: tách giá MAINNET/TESTNET (4 chỗ độc lập), 4 hạn mức trên rail, trạng
thái rỗng đọc ra *"chưa có gì xảy ra"* chứ không giống hỏng.

---

## 1. Bốn control còn thiếu

Mock đang **giả định** chúng tồn tại ở đâu đó. Không có chỗ nào cả.

### 1.1 Khối lượng vào lệnh — cái này không phải thiếu tính năng, là **bug đang chặn cả bot**

Đây là điểm quan trọng nhất của prompt này.

Code hiện hard-code *"20% vốn, đòn bẩy 1x"*. Đặt cạnh hạn mức **500 USDT/lệnh**, kết quả là:

| Số dư tài khoản | Lệnh sinh ra | Kết quả |
| ---: | ---: | :--- |
| **14 871.60** *(đúng con số mock đang vẽ)* | 2 948.85 USDT | ❌ **bị chặn** |
| 15 000 *(mặc định của testnet)* | 2 948.85 USDT | ❌ **bị chặn** |
| 2 500 | 448.74 USDT | ✅ qua |

Nói cách khác: **với chính con số mock vẽ trên rail, bot không đặt nổi một lệnh nào.** Mock vẽ
0.002 BTC ≈ 0.86% vốn — tức nó đã ngầm giả định có control này rồi.

Control phải chọn được **một trong bốn kiểu** (đây là bốn kiểu code thật đã hỗ trợ, không phải
đề xuất — đừng bịa thêm kiểu thứ năm):

| Kiểu | Nhập gì |
| :--- | :--- |
| Phần trăm vốn | một số % |
| Số tiền cố định | một số USDT |
| Số lượng cố định | một số coin/contract |
| Rủi ro theo % | một số % + khoảng cắt lỗ |

**Ràng buộc hành vi, không phải thẩm mỹ:** người dùng phải thấy được **notional mà lựa chọn của
họ sinh ra** và **nó có vượt hạn mức 500 hay không**, *trước khi* bật giao dịch. Nếu phải bật
lên, chờ tín hiệu, rồi mới biết mình cấu hình sai — thì cái control này không giải quyết được gì.

Đòn bẩy cũng vậy: mock trạng thái B ghi `5x` ở bảng vị thế, nhưng không có chỗ nào đặt nó.

### 1.2 Chọn chiến lược

Có **6** chiến lược đã đăng ký. Mặc định hiện tại là **rỗng** ⇒ bot không chạy gì.

`ema_crossover` · `multi_ema_trend_follower` · `support_resistance` ·
`ema_trend_confirm_pullback` · `long_term_trend_zone` · `volume_spike_flow`

*(Mock đang ghi `ema_cross(9,21)`; tên khoá thật là `ema_crossover`.)*

### 1.3 Tham số của chiến lược — **số lượng thay đổi theo chiến lược**

Ràng buộc quan trọng nhất của mục này: **không thiết kế một khung 2 ô cố định.**

| Chiến lược | Số tham số |
| :--- | :-: |
| `long_term_trend_zone` | **1** |
| `ema_crossover` | 2 |
| `multi_ema_trend_follower` | 4 |
| `support_resistance` | 5 |
| `volume_spike_flow` | 7 |
| `ema_trend_confirm_pullback` | **10** |

Đổi chiến lược thì cả danh sách tham số đổi theo. Một panel vẽ vừa cho `ema_crossover` sẽ vỡ khi
chọn `ema_trend_confirm_pullback`.

*(Mock ghi `(9,21)`; mặc định thật của `ema_crossover` là `12/26` — số trong mock là một cấu hình
tuỳ chỉnh, càng chứng tỏ control này phải có.)*

### 1.4 Khung thời gian

Header ghi `1m` nhưng không có control. Đây cũng là một lỗi thật đang mở: đường xử lý live hiện
**không lọc theo khung**, nên hai khung cùng một symbol sẽ trộn vào nhau và làm hỏng chỉ báo.

**Widget chọn khung thời gian đã có sẵn trong app** (đang dùng ở Backtest, Data Management,
Dev Board) — dùng lại, đừng vẽ kiểu mới.

### Một câu hỏi thiết kế thật, không phải chuyện bố cục

Bốn control này **đổi được khi bot đang chạy không?** Đổi chiến lược giữa phiên khi đang có vị
thế mở là chuyện nguy hiểm. Anh đề xuất đi — khoá lại khi đang BẬT, hay cho đổi kèm cảnh báo, hay
cách khác. Cần một lập trường, không cần một câu trả lời "đúng".

---

## 2. Năm trạng thái còn thiếu

> **Đừng tự viết câu chữ lỗi.** Hệ thống **đã có 14 lý do có tên** cho việc từ chối. Việc của
> thiết kế là cho chúng một chỗ đứng, không phải nghĩ ra chúng.
>
> **3 rào an toàn:** venue chưa bật · công tắc đang tắt · kết nối chưa sẵn sàng
> **4 hạn mức:** số lệnh/phiên · notional/lệnh · vị thế/symbol · giãn cách 2 lệnh
> **7 lý do sàn từ chối:** thiếu margin · sai bước khối lượng · dưới notional tối thiểu ·
> sai bước giá · từ chối lệnh đóng · quá tần suất · không rõ

### 2.1 Đang đối soát, và **từ chối bật**

Bật công tắc **không** phải lật một cái switch. Nó chạy đối soát với sàn trước: đọc vị thế và
lệnh đang có thật. Nếu sàn có vị thế mà app không biết (ai đó vào web Binance đặt tay, hoặc một
phiên app khác) → **từ chối bật**, hiện ra cho người dùng quyết định, **không tự đóng**.

Cần: trạng thái *đang đối soát* (mất vài giây, có thể lỗi mạng), và trạng thái *từ chối bật kèm
lý do*. Công tắc trong mock hiện chỉ có 2 vị trí.

### 2.2 Lệnh bị hạn mức chặn — trạng thái quan trọng nhất còn thiếu

Bốn hạn mức đang hiện đẹp trên rail nhưng **chưa bao giờ được vẽ lúc chúng thực sự chặn**.

Vấn đề thật, và nó nghiêm trọng hơn vẻ ngoài: hiện tại *"chiến lược không phát tín hiệu"* và
*"phát tín hiệu nhưng bị chặn"* **trông giống hệt nhau** — màn hình đứng im. Người vận hành không
phân biệt được bot đang chờ đúng lúc với bot đang bị chính hạn mức của mình khoá.

Cần thấy: tín hiệu **nào** bị chặn, bởi hạn mức **nào**, và (nếu là hạn mức giãn cách) **còn bao
lâu nữa thì hết chặn**.

### 2.3 Kết nối chưa sẵn sàng — **6 lý do khác nhau**

Rào an toàn thứ 3. Dải banner hiện có 3 trạng thái, không cái nào cho việc này. Sáu lý do đã có
tên trong code, và chúng đòi hành động **khác nhau** — nên gộp hết thành *"mất kết nối"* là làm
mất thông tin:

chưa cấu hình key · chữ ký sai · lệch đồng hồ · key hết hạn · lỗi mạng ·
**tài khoản đang ở chế độ Hedge** *(app chỉ hỗ trợ One-way — người dùng phải tự đổi trên web
Binance, app không đổi hộ)*

### 2.4 Chưa cấu hình API key

Sidebar có mục *"API & Credentials"* nhưng màn Giao dịch không có trạng thái tương ứng. Đây là
tình trạng của **lần mở app đầu tiên** — đáng lẽ phải là trạng thái được thiết kế kỹ nhất, không
phải trạng thái bị bỏ quên.

### 2.5 Lệnh bị **sàn** từ chối

Khác hẳn bị hạn mức chặn: lệnh đã rời khỏi máy, sàn nhận và trả lỗi. Bảy lý do ở trên. Mock hiện
chỉ có một ảnh lỗi duy nhất, và nó thuộc về Dừng khẩn cấp.

---

## 3. Ba hành động còn thiếu — cơ chế đã có sẵn trong code

| Hành động | Vì sao cần |
| :--- | :--- |
| **Huỷ một lệnh chờ** | Bảng lệnh chờ không có nút nào. Muốn bỏ một lệnh phải giật Dừng khẩn cấp — huỷ sạch mọi thứ |
| **Đóng một vị thế bằng tay** | Cùng vấn đề. Người vận hành nhìn thấy một vị thế xấu **không làm gì được** ngoài cầu dao tổng |
| **Lệnh khớp một phần** | Cột `GIÁ TRẠNG THÁI` gộp giá và trạng thái. Trạng thái *khớp một phần* cần **đã khớp / tổng** — chân bảng B có ghi "0 khớp một phần" nên mock có biết, nhưng bảng chưa có chỗ đặt |

---

## 4. Sửa số liệu — ràng buộc cứng, không phải góp ý

Đối chiếu từng ô với dữ liệu app thật lấy được:

| Ô trong mock | Vấn đề |
| :--- | :--- |
| *"Số dư USDT **khả dụng** 14 871.60"* | App lấy được **số dư ví**, không phải số khả dụng. Hai số khác nhau ngay khi có vị thế — mà trạng thái B đang hiện cùng lúc cả hai. **Đổi nhãn** hoặc bỏ chữ "khả dụng" |
| *"Margin đang dùng 128.20"* | **Không lấy được** ở cấp tài khoản. Và mock tự mâu thuẫn: rail ghi `128.20`, thẻ vị thế ngay dưới ghi `Margin 25.64` — `128.20` là **giá trị vị thế**, không phải margin |
| *"PnL chưa thực hiện"* trên rail | Chỉ là **tổng của các vị thế đang mở**. Gọi đúng tên nó |
| *"Mở lúc 14:35:02"* | Sàn **không trả về** thời điểm mở vị thế. Chỉ có "lần cập nhật gần nhất" |
| `THỜI GIAN` = `14:35:03.412881` | 6 chữ số thập phân = micro-giây. Sàn trả **mili-giây** (3 chữ số). Số 6 chữ số là đồng hồ máy người dùng, không phải giờ sàn — mà cột này **đã chốt dùng giờ sàn** |
| Trạng thái C: số dư `12.40` | Rơi từ `14 871.60` xuống `12.40` không giải thích được. Câu *"không đủ để đóng vị thế 128.21 USDT"* cũng sai cơ chế — lệnh đóng vị thế không cần thêm vốn bằng giá trị vị thế |

**Cần thêm ô nào ngoài bảng này: hỏi trước.** Đừng vẽ rồi để người code phát hiện không có dữ liệu.

---

## 5. Những điều phải giữ đúng

- Công tắc **luôn khởi đầu TẮT** mỗi lần mở app. Không nhớ trạng thái lần trước.
- **Không có lựa chọn mainnet.** Chỉ testnet hoặc tắt hẳn.
- Hạn mức là số thật: **20** lệnh/phiên · **500** USDT/lệnh · **1** vị thế/symbol · **60** giây.
- Giá trên chart là giá **mainnet**, không phải giá khớp. Bốn chỗ đang nói điều này — giữ cả bốn.
- Marker Buy/Sell của lệnh thật trên chart vẫn **chưa** thuộc vòng này.

---

## 6. Cần nhận lại gì

1. **Ba trạng thái cũ**, cập nhật có đủ 4 control và số liệu đã sửa theo §4.
2. **Trạng thái mới** cho §2 — không cần 5 khung riêng nếu anh gộp được hợp lý, nhưng phải thấy
   được: *đang đối soát*, *từ chối bật*, *lệnh bị hạn mức chặn*, *kết nối chưa sẵn sàng*,
   *chưa có API key*.
3. **Lập trường về câu hỏi ở §1**: đổi cấu hình khi bot đang chạy — cho hay khoá.
4. **Nói ngắn gọn** đã đổi gì và **vì sao**, nhất là chỗ nào phải hy sinh để nhét 4 control vào.
5. Thấy yêu cầu nào sai hướng thì **nói ra**. Bản mock là đầu vào để bàn, không phải hợp đồng.
