# ⚔ CHIBI NHẮC VIỆC — Áo Đen

Robot nhắc việc dạng nhân vật chibi chạy trên màn hình Windows 10/11.
Nhân vật **Áo Đen** đi lại, leo tường, nhảy lên cửa sổ, tung combo. Nó nhắc việc, tự học thói quen của bạn, và phản ứng theo từng thao tác chuột bạn gán.

## Cài đặt

1. Cài **Python 3.9+** từ [python.org](https://www.python.org/downloads/). Khi cài nhớ tick **Add python.exe to PATH**.
2. Tải repo này về (nút **Code → Download ZIP**), giải nén ra một thư mục bất kỳ (USB cũng được).
3. Chạy **`ChayChibi.bat`**.
   - Lần đầu, file này tự cài **Pillow** (thư viện ảnh, bắt buộc).
   - Máy không có mạng: chép bộ cài Pillow `.whl` (Windows 64-bit, đúng phiên bản Python) vào thư mục `ThuVien/` rồi chạy lại.

Dữ liệu (việc nhắc, nhật ký tự học, cài đặt) lưu trong thư mục `ChibiData/` cạnh file chương trình. Chép cả thư mục này sang máy khác là giữ được nguyên.

## Tính năng

| Nhóm | Chi tiết |
|---|---|
| Nhắc việc | Một lần, hằng ngày, T2–T6, chọn thứ, lặp mỗi N phút. Có Hoãn 10'/30', báo trước, máy bật trễ tối đa 3 giờ vẫn nhắc. Nhắc dở dang được nhắc tiếp khi mở lại app |
| Tự học | Phát hiện việc bạn hay làm cùng giờ, gợi ý dời giờ nhắc, bỏ ngày hay bị bỏ qua, học thói quen mở ứng dụng |
| Sức khoẻ | Nhắc nghỉ mắt theo thời gian làm việc liên tục thật, có giờ yên lặng, tự ngủ khi bạn rời máy |
| Nhân vật | Engine Shimeji-ee chạy thẳng `actions.xml` / `behaviors.xml`. Có sẵn 2 nhân vật: **Áo Đen** (35 động tác) và **Cổ Long** (28 động tác, xem bên dưới). Chọn ở tab **Nhân vật**; mỗi nhân vật nhớ bộ gán chuột, tên gọi riêng |
| Môi trường | Đi và đứng trên mép cửa sổ đang mở. Thấy cửa sổ hay biểu tượng thư mục/file cao hơn phía trước thì nhảy lên. Bước hụt mép thì rơi |
| Chuột trên nhân vật | Trái/phải × (1 lần, 2 lần, liên tục, giữ), lăn lên, lăn xuống, nhấn con lăn. Mỗi thao tác gán 1 chiêu và/hoặc 1 lệnh. Kéo để xách; thả ra thì nhân vật **lao cắm đầu xuống và nện tạo hố**; quăng **đập vào tường** thì rơi xuống **ăn vạ** (đổi được cả hai) |
| Chuột trên màn hình | Bấm 1 lần, 2 lần, chuột phải, lăn, nhấn con lăn tại bất kỳ điểm nào: nhân vật **lao tới ngay khi vừa nhấn chuột** (~0,16 giây, dù xa cỡ nào) rồi tung chiêu. Phím **Ctrl + Alt + X** gọi nhân vật tới chỗ con trỏ |
| Hiệu ứng gõ phím | Ở **mọi phần mềm**, 16 hiệu ứng VFX động (xem mục *Hệ VFX bàn phím*). Chọn riêng mẫu khi gõ và khi xoá, hoặc ngẫu nhiên / ngẫu nhiên hệ Lôi. Cỡ tự theo cỡ chữ. Gõ liên tục thì nhân vật nạp năng lượng; xoá liên tục thì nhân vật lao tới chỗ xoá |
| Cập nhật | Tự kiểm tra bản mới trên GitHub khi mở app và mỗi 6 giờ. Có thể chọn tự cài hoặc hỏi trước. **F5** trong bảng quản lý để cập nhật ngay. Cập nhật từ file `.zip` cho máy không mạng. Quay về bản trước |
| Sự kiện | Gán chiêu khi báo nhắc, Xong, Hoãn, Bỏ qua, nghỉ mắt, chào buổi sáng, rời máy, quay lại |
| Tự hoạt động | Bật/tắt từng động tác. Chiêu đã gán cho chuột trên nhân vật thì mặc định chỉ chạy khi bạn bấm |
| Hiển thị | Luôn nằm gọn trong màn hình đang đứng, không lấn ra mép. Trong suốt từng điểm ảnh (giữ hào quang, viền mờ). Tự ẩn khi trình chiếu hoặc xem phim toàn màn hình |

### Chế độ thao tác chuột trên màn hình (tab **Điều khiển**)

| Chế độ | Cách dùng | Ảnh hưởng tới phần mềm khác |
|---|---|---|
| Chỉ trên vùng trống desktop *(mặc định)* | Bấm lên desktop hoặc biểu tượng ngoài desktop | Không, chuột vẫn chạy bình thường |
| **Mọi nơi** (kể cả vùng an toàn) | Bấm ở bất kỳ đâu, không cần giữ phím | Không, chuột vẫn chạy bình thường với phần mềm |
| Giữ **Alt** + thao tác | Bấm ở bất kỳ đâu khi đang giữ Alt | Cú bấm đó được giữ lại, không lọt xuống phần mềm bên dưới |
| Giữ **Ctrl + Alt** + thao tác | Như trên, dùng khi Alt + bấm trùng phím tắt khác | Như trên |
| Tắt | — | — |

### Thao tác mặc định trên nhân vật

| Thao tác | Mặc định |
|---|---|
| Trái 1 lần | Đấm thép + xem việc sắp tới |
| Trái 2 lần | Mở bảng quản lý |
| Trái liên tục (≥3) | FULL COMBO |
| Trái giữ | Nạp năng lượng |
| Phải 1 lần | Menu nhanh (có mục ★ Ra chiêu) |
| Lăn lên / xuống | Hắc Long nhảy vút / Ngồi nghỉ |
| Nhấn con lăn | Đuổi theo chuột |
| Ctrl + lăn | Đổi kích thước |

Đổi tất cả trong **Bảng quản lý → Điều khiển**. Mở bảng quản lý bằng cách nhấp đúp vào nhân vật.

## Hệ VFX bàn phím

Mỗi hiệu ứng là một lớp `Vfx` trong `ChibiNhacViec.pyw`. Vòng đời của nó:
1. `__init__` nhận thông số: cỡ, chế độ, cường độ, tốc độ, hạt giống.
2. `init()` dựng thiết kế gốc cố định.
3. Lặp `update()` và `draw()` theo từng frame.
4. `finish()` giải phóng.

`bake()` chạy vòng đời đó thành dãy frame 25 hình/giây. Có thêm pha phân rã chung để hiệu ứng luôn kết thúc sạch.

Mỗi hiệu ứng đi qua 5 giai đoạn: khởi phát, tăng năng lượng, cao trào, phản ứng, phân rã. Các lớp hình phối hợp gồm: hình chính, tia phụ, hạt, quầng sáng, tan biến.

- **Gõ và xoá khác nhau:** gõ thì bùng ra, giáng xuống, phóng đi. Xoá thì diễn biến ngược: hút vào, rút về, tan rã, lôi đi.
- **Chỉ kích hoạt khi nội dung thật sự đổi.** App ghi lại vị trí con trỏ nhập lúc yên, vì hook nhận phím trước phần mềm đích. Nếu con trỏ không dịch chuyển thì bỏ qua (ví dụ Backspace ở đầu ô). Riêng phím Delete được tính dù con trỏ đứng yên.
- **Gõ dồn:** mỗi lần gõ một hiệu ứng riêng, mỗi hiệu ứng một cửa sổ trong suốt riêng. Tối đa 3 hiệu ứng mỗi kênh; cái cũ nhất được đẩy nhanh sang pha tan biến.
- **Không làm chậm máy:** frame được dựng sẵn ở luồng phụ (4 biến thể mỗi mẫu).

| Nhóm | Hiệu ứng |
|---|---|
| ⚡ Hệ Lôi | Lôi tinh bạo phát, Thiên lôi giáng, Sấm sét liên hồi, Lôi hoàn, Lôi xoáy, Lôi phạt trụ, Địa chấn lôi, Lôi xích liên hoàn, Lôi long, Lôi thương, Tử lôi bùng nổ |
| Ma pháp | Ma trảo, Ma độc long, Bỉ ngạn hoa nở, Đầu lâu quỷ bay lên, Song phi kiếm bay vút |

**Hệ Lôi Thái Cổ Hắc Long**

Đây là ngôn ngữ thiết kế sấm sét dùng chung cho cả bàn phím và chiêu của Cổ Long.
- **Hình dạng:** tia chính gấp khúc răng cưa có chủ đích. Nhánh phụ đầu nhọn, phân nhánh tự nhiên, không rối thành lưới.
- **Bảng màu cố định:** lõi trắng tím, trắng xanh; trung gian tím điện, xanh tím; viền tím đậm; quầng đen tím.
- **Thiết kế gốc cố định:** mỗi tia được dựng một lần từ hạt giống. Các frame chỉ đổi trạng thái: vươn, giật, nhịp sáng, co rút.

Thử thật: `python tests/chay_thu_go_phim.py bolt slash /tmp/thu.gif` sẽ mở ô soạn thảo, gõ và xoá thật, rồi ghi lại hình hiệu ứng.

## Nhân vật Cổ Long (rồng đen vảy vàng)

Dựng từ bảng sprite của bạn (`tools/co_long_nguon.png`, 14 nhóm động tác). 4 khung đi bộ vốn bị khung kế bên che mất đuôi được ghép đuôi từ khung có đủ đuôi. Toàn bộ sấm sét dùng **Hệ Lôi** (tím): điện tập trung ở sừng, mắt, móng vuốt, khớp vảy, đầu đuôi, mỗi điểm sáng theo nhịp riêng. Công cụ `tools/dung_co_long.py`:

1. **Cắt khung:** tách nền caro giả, bỏ nhãn chữ và vạch kẻ, cắt 70 khung gốc. Những khung quay mặt sang phải thì lật lại cho cùng hướng.
2. **Dựng hoạt cảnh 25 hình/giây:**
   - Mỗi khung gốc được giữ vài nhịp kèm chuyển động liên tục (thở, nhấp nhô, chao, co giãn, rung), rồi hoà nhanh sang khung kế.
   - Đòn nhanh thì đổi khung 2–3 nhịp; động tác chậm (nghỉ, ngủ, biểu cảm) thì giữ lâu.
3. **Phủ hiệu ứng vẽ bằng code:**
   - Lôi điện bò trên thân, chớp loá vàng rực lúc ra đòn, sét trời giáng xuống.
   - Sóng âm, vòng xung kích, đất nứt, đá văng.
   - Lửa phun từ miệng (dùng chính lưỡi lửa trong ảnh của bạn), tia sét phân nhánh tự nhiên.

| Nhóm | Động tác |
|---|---|
| Di chuyển | Đứng thở, ngó nghiêng, đi bộ, chạy, lướt sát đất, leo vách, bò trên trần |
| Long kỹ | Gầm rú & thét lớn, Phun lửa, Phun sấm sét (vàng → tím), Cuộn thân, Lôi điện quanh thân, Treo lơ lửng (xoáy tím dưới chân) |
| Tuyệt kỹ | Long uy (lốc vàng + sét trời), Hắc hoá (quả cầu tím → cột hắc khí), FULL COMBO (gầm → cuộn thân → sấm sét → lửa → lôi điện → Long uy) |
| Bay | Bay vút, bay theo chuột, Lao xuống & đập đất (nổ tung, hố, đá văng) |
| Biến hoá | Hoá rồng mini (chớp + khói, nhảy tưng tưng rồi biến lại) |
| Biểu cảm | Tức giận (gân đỏ, dậm chân, thét), Hoài nghi (???), Yêu thích (tim bay), Ăn vạ, Khóc, Nằn nì |
| Nghỉ | Nằm nghỉ, Ngủ khò khò (chữ Z) |

Gán mặc định:
- **Trên nhân vật:** trái 1 lần = Phun sấm sét, trái 3 lần = Full combo, giữ trái = Lôi điện, phải 2 lần = Hắc hoá, nhấn con lăn = Hoá rồng mini.
- **Rơi / va chạm:** thả rơi từ trên cao = lao xuống, chạm đất **nổ tung một vùng** (ảnh nổ của bạn); quăng đập tường = rơi xuống rồi **tức giận**.
- **Trên màn hình:** trái 2 lần = Phun lửa, phải 2 lần = Long uy.

Muốn chỉnh:
- Sửa `tools/dung_co_long.py` (toạ độ cắt `BOXES`, dòng thời gian từng chiêu), rồi chạy `python tools/dung_co_long.py` để dựng lại. Cần Pillow và numpy.
- Xem các khung đã cắt: `--khung`.
- Xem nhanh vài chiêu: `--xem roar,fire`.

## Hiệu ứng gõ phím & quyền riêng tư

- App chỉ nhận biết **"vừa gõ ký tự"** hay **"vừa xoá"**. Không ghi lại, không lưu, không gửi đi phím nào (xem hàm `classify_key` trong mã nguồn).
- Tắt trong **Cài đặt → Hiệu ứng gõ phím** là app gỡ hẳn chức năng bắt phím của Windows.
- Tự tắt ở ô mật khẩu (cả phần mềm Windows lẫn trình duyệt web) và khi trình chiếu / toàn màn hình.
- Bỏ qua phím do Unikey/EVKey tự gửi khi bỏ dấu, nên không hiện hiệu ứng chém nhầm.
- Vị trí hiệu ứng được tìm lần lượt bằng: con trỏ hệ thống → **UI Automation** (Chrome, Edge, Word, app Windows 11) → **MSAA** (Zalo, app Electron). Không cách nào được thì hiện cạnh con trỏ chuột. Mục Cài đặt cho biết từng phần mềm đang dùng cách nào.
- Phần tìm con trỏ nhập chạy ở **tiến trình phụ riêng** (`--caret-helper`), có hạn chờ 0,25 giây. Phần mềm kia treo hay lỗi thì chibi vẫn chạy; lỗi 3 lần thì tự chuyển sang hiện cạnh chuột.
- Phần mềm diệt virus có thể cảnh báo vì app dùng kỹ thuật bắt phím toàn hệ thống. Mã nguồn công khai ở repo này để kiểm chứng.

## Cập nhật phiên bản

| Cách | Làm thế nào |
|---|---|
| Tự động | **Bảng quản lý → Cài đặt → Cập nhật phần mềm**, chọn *Tự động cập nhật* hoặc *Báo khi có bản mới* (mặc định) |
| Phím F5 | Đang mở bảng quản lý thì bấm **F5**: có bản mới là tải, cài và khởi động lại ngay |
| Nút | Nút **⟳ CẬP NHẬT (F5)** trên banner bảng quản lý, hoặc mục *Kiểm tra cập nhật* trong menu chuột phải |
| Thủ công | Tải [ZIP từ GitHub](https://github.com/HP-wukoong/NHAN_VAT_CHIBI/archive/refs/heads/main.zip), rồi vào **Cài đặt → Cập nhật từ file .zip...** |
| Quay lại | **Cài đặt → Quay về bản trước** (app giữ 3 bản sao lưu trong `ChibiData/backup/`) |

Trước khi chép đè, app kiểm tra file tải về có hợp lệ không. File hỏng hoặc tải dở thì app không đụng tới bản đang chạy. Dữ liệu trong `ChibiData/` luôn được giữ nguyên.

Người phát hành bản mới: sửa số `APP_VER` trong `ChibiNhacViec.pyw`, sửa `version.json` (số phiên bản + ghi chú), rồi đẩy lên nhánh `main`.

## Cấu trúc thư mục

```
ChibiNhacViec.pyw      Chương trình (1 file, Python + tkinter + Pillow)
ChayChibi.bat          Trình khởi động: tìm Python, cài Pillow, chạy không hiện cửa sổ đen
version.json           Số phiên bản mới nhất + ghi chú (app đọc file này để biết có bản mới)
NhanVat/NhanVatAoDen/  Nhân vật gốc: ảnh + conf/actions.xml + conf/behaviors.xml (định dạng Shimeji-ee)
NhanVat/CoLong/        Nhân vật Cổ Long (dựng từ bảng sprite của bạn) + conf/chibi.json (tên chiêu, gán mặc định)
HieuUng/               Ảnh hiệu ứng gõ phím / tiếp đất (cắt từ ảnh của bạn bằng tools/cat_hieu_ung.py)
tools/                 Ảnh gốc + công cụ dựng Cổ Long (dung_co_long.py) và cắt hiệu ứng (cat_hieu_ung.py)
ThuVien/               Để bộ cài Pillow .whl cho máy không có mạng
tests/                 Kiểm thử tự động
ChibiData/             (tự tạo khi chạy) dữ liệu người dùng – không đưa lên git
```

Muốn dùng nhân vật Shimeji-ee khác: vào **Bảng quản lý → Nhân vật → Nạp Shimeji khác**, chọn thư mục có `conf/actions.xml`.

## Kiểm thử

```bat
cd tests
python test_nhac_viec.py
python test_chuot_man_hinh.py
python test_dong_tac.py
python test_cap_nhat.py
python test_go_phim.py
python test_tha_roi.py
python test_co_long.py
```

Trên Linux chạy bằng `xvfb-run python3 tests/<tên file>`. Mỗi bộ test chạy trong thư mục tạm, không đụng dữ liệu thật, và in `PASS`/`FAIL` cho từng mục.

## Gỡ lỗi

- Lỗi được ghi vào `ChibiData/errors.log`.
- Nhân vật không hiện, hoặc hào quang có viền hồng: vào **Nhân vật**, bỏ tick **Hiển thị mịn**, rồi mở lại app.
- Lăn chuột không ăn: bật *Settings → Bluetooth & devices → Mouse → Scroll inactive windows when I hover over them*.
- Phím Ctrl + Alt + X không chạy: có phần mềm khác đã chiếm tổ hợp phím này.
