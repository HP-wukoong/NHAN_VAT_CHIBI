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
| Hiệu ứng gõ phím | Ở **mọi phần mềm**, chọn riêng mẫu khi gõ và khi xoá (hoặc ngẫu nhiên, hoặc **ngẫu nhiên hệ Lôi**) trong **24 mẫu**. **Hệ Lôi (11 mẫu)**: Lôi điện tỏa, Lôi đình giáng xuống, Lôi long sấm sét chạy trên chữ, **Lôi xích liên hoàn, Lôi cầu plasma, Lôi vân giáng thế, Lôi thương xuyên chữ, Lôi trảo xé chữ, Huyết lôi diệt thế, Thiên phạt lôi trụ, Lôi võng thu lưới**. Các mẫu khác: Thần quang vàng, Đầu lâu ma quái, **Lửa địa ngục (lam hoả)**, Hắc diễm, Băng tinh, Tinh tú, Sóng xung kích, Loạn đao chém, Búa sấm đập vỡ chữ, **Vạn kiếm đâm vỡ chữ**, Vỡ vụn, Hố đen nuốt chữ, Nổ tung. Gõ liên tục thì nhân vật nạp năng lượng; xoá liên tục thì nhân vật lao tới chỗ xoá. Cỡ hiệu ứng **tự theo cỡ chữ** của phần mềm đang gõ (có hệ số chỉnh thêm). Tắt được trong Cài đặt |
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

## Nhân vật Cổ Long (hắc long thái cổ)

Rồng đen chibi vẽ hoàn toàn bằng code theo khung xương (thân, cổ, đầu có hàm mở được, 4 chân, 2 cánh màng, đuôi 12 đốt có lưỡi đao). Mỗi khung hình là một tư thế tính từ đường cong mượt nên đi, bay, vỗ cánh, quật đuôi đều liền mạch (25 hình/giây). Có quầng hắc khí tím mờ quanh thân để nổi trên nền tối.

| Nhóm | Động tác |
|---|---|
| Di chuyển | Đứng thở, phì khói ngó nghiêng, đi 4 chân (bàn chân không trượt), phi nước đại, lướt sát đất, leo vách, bò trên trần |
| Long kỹ | **Long hống** (gầm sóng âm), **Hắc viêm long tức** (phun dòng lửa đen viền tím), **Long trảo liên hoàn** (đứng dậy cào 3 nhát), **Thần vĩ trảm** (quật đuôi qua đầu thành vệt trăng khuyết), **Phong dực cuồng phong** (vỗ cánh tạo gió xoáy), **Chấn địa** (dậm nứt đất, đá văng), **Lôi long giáng thế** (gầm gọi sét đánh quanh mình, sét đánh vào sừng) |
| Bá khí | **Tụ long khí** (lửa hắc khí bốc quanh thân, hạt khí hút vào), **Hắc nhật diệt thế** (tụ mặt trời đen trước miệng rồi bắn pháo hắc nhật), **Thái cổ long hoàng quyết** (full combo 6 chiêu) |
| Bay lượn | Cất cánh bay vút, bay theo chuột, **Thiên long trụy** (bay lên rồi bổ nhào kéo đuôi lửa, nện tạo hố) |
| Cảm xúc | Cười khẩy phì khói, cuồng nộ (mắt đỏ, lửa đỏ), ăn vạ nằm ngửa giãy, ngồi khóc, nằn nì mắt long lanh |
| Nghỉ | Cuộn mình nằm nghỉ, ngủ khò khò (chữ Z khói bay lên) |

Gán mặc định cho Cổ Long: trái 1 lần = Long trảo, trái 3 lần = full combo, giữ trái = Tụ long khí, phải 2 lần = Cuồng nộ, lăn lên = Bay vút; thả rơi = Thiên long trụy; đập tường = Ăn vạ. Trên màn hình: trái 2 lần = Hắc viêm, phải 2 lần = Hắc nhật, lăn lên = Lôi long giáng thế.

Muốn chỉnh hình rồng: sửa `tools/tao_co_long.py` rồi chạy `python tools/tao_co_long.py` (cần Pillow) để vẽ lại toàn bộ `NhanVat/CoLong/`. Xem nhanh vài động tác: `python tools/tao_co_long.py --xem roar,breath 8` (ảnh ra `/tmp/rong_xem.png`).

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
NhanVat/CoLong/        Nhân vật Cổ Long (ảnh do tools/tao_co_long.py vẽ) + conf/chibi.json (tên chiêu, gán mặc định)
tools/                 Công cụ vẽ nhân vật Cổ Long
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
