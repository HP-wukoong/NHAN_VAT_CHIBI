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

22 hiệu ứng (có Lôi tinh liên hoàn, Lôi thương xuyên chữ) dựng từ **ảnh hiệu ứng của bạn** (`HieuUng/`, cắt bằng `tools/cat_hieu_ung.py`). Ảnh không được dán nguyên mà được **bóc tách thành lớp** rồi dựng chuyển động.

**Các lớp được tách:**
- lõi sét trắng
- thân sợi điện có màu
- khói đen
- đá vụn (mảnh tối được nhấc riêng khỏi ảnh)

Kèm theo là trường "khoảng cách tới tâm năng lượng" và các rẻ quạt sợi sét.

**Tuỳ chỉnh** (Cài đặt → ⚡ Hiệu ứng gõ phím): Hệ số cỡ, **Độ đậm** (độ trong suốt 15–100%), **Tốc độ xuất hiện** (×0.4 chậm – ×2.0 nhanh).

Đầu lâu chỉ dùng phần đầu lâu bóc riêng từ ảnh. Lôi tinh liên hoàn và Lôi thương dựng từ hai ảnh riêng của bạn (`tools/hieu_ung_nguon/8_loi_lienhoan.png`, `9_loi_thuong.png`, cắt bằng `python tools/cat_hieu_ung.py --xoay`); bản vẽ bằng nét gấp khúc dùng khi thiếu numpy.

**Ổn định & khắc phục:** tab Cài đặt có bảng tình trạng (✅ ổn định / ⚠ đang lỗi gì) và nút **🛠 Khắc phục & làm mới** (cài lại hook bàn phím, khởi động lại bộ dò con trỏ, tạo lại cửa sổ hiệu ứng, dựng lại hình rồi phát thử). App tự canh gác mỗi 2 giây: Windows gỡ hook thì tự cài lại. Lỗi được ghi ở `ChibiData/hieu_ung_go.log`; nút **📋 Sao chép báo cáo lỗi** chép toàn bộ tình trạng + nhật ký để gửi người sửa.

**Thư viện:** hiệu ứng dựng từ ảnh cần `numpy`. `ChayChibi.bat` và app tự cài khi có mạng; nếu chưa cài được, hiệu ứng tự dùng bản vẽ dự phòng (vẫn chạy). Cài tay: `py -m pip install numpy`.

**Mỗi frame diễn ra:**
- Sét lan dần từ tâm theo mép răng cưa.
- Từng rẻ quạt chớp, tắt, loé theo nhịp riêng.
- Lõi bùng thành quầng sáng.
- Khói nở rồi tan theo nhiễu.
- Đá văng theo quán tính.
- Một lớp ảnh khác nháy ngược pha tạo hiệu ứng đan xen vàng và tím.
- Sợi sét rời (bóc từ bảng sét) chớp quanh tâm hoặc giáng dọc cột sét.

**Nhóm ma pháp:** có quỹ đạo riêng.
- Ma trảo vồ chéo qua chữ.
- Ma độc long trồi lên rồi lao đi, nhả độc khí.
- Bỉ ngạn hoa mọc lên, lay động, rơi cánh.
- Đầu lâu bay lên lắc lư, có hồn bay.
- Phi kiếm phóng ngang rồi kiếm lớn giáng xuống.

**Gõ và xoá khác nhau.** Khi xoá:
- Sét từ ngoài dồn sập vào chữ.
- Đá bị hút ngược về.
- Quỹ đạo chạy ngược.

**Quy tắc kích hoạt và hiển thị:**
- Chỉ kích hoạt khi nội dung thật sự đổi (con trỏ nhập dịch chuyển). Phím Delete vẫn được tính.
- Mỗi lần gõ có hiệu ứng riêng, chồng lớp tối đa 3 cái.
- Frame được dựng ở luồng phụ. Thiếu ảnh thì tự dùng bản vẽ bằng code.

**Thử thật:** `python tests/chay_thu_go_phim.py bolt slash /tmp/thu.gif`

## Nhân vật Cổ Long (rồng đen vảy vàng)

Dựng từ bảng sprite của bạn (`tools/co_long_nguon.png`, 14 nhóm động tác). Các khung bị khung kế bên che mất đuôi (đi bộ, đứng ngó, bay, biểu cảm, rồng mini) được ghép đuôi tự động theo độ dày mỏm cụt; mảnh rồng lạc ở khung bay được xoá. Đi / chạy / leo / bò trườn: 4 chân bước theo nhịp chéo (nhấc – đưa – đặt – đạp, khớp tốc độ nên không trượt), thân và đuôi uốn sóng trườn. Toàn bộ sấm sét dùng **Hệ Lôi** (tím): điện tập trung ở sừng, mắt, móng vuốt, khớp vảy, đầu đuôi, mỗi điểm sáng theo nhịp riêng. Công cụ `tools/dung_co_long.py`:

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
| Di chuyển | Đứng thở, ngó nghiêng, đi bộ (chân bước thật), chạy, **bò trườn sát đất**, lướt sát đất, leo vách, bò trên trần |
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

## Áo Đen bay lượn & phá icon (v3.13)
- Hành vi mới (nhóm **Bay lượn**): *Bay phá icon (tinh nghịch)*, *Bay lượn toàn màn hình*, *Bay chọc chuột* – tự xuất hiện khi rảnh, bật/tắt hoặc gán cho thao tác chuột ở tab Điều khiển.
- Phá icon chỉ là hiệu ứng vẽ đè lên màn hình; icon thật không bị di chuyển. Tắt ở Nhân vật → "Bay toàn màn hình & phá icon desktop".
- Khung vẽ thêm (bay, bổ nhào, cất cánh, quay người) dựng từ nét vẽ gốc bằng `python tools/dung_ao_den.py`; neo ghi ở `NhanVat/NhanVatAoDen/conf/x_khung.json`.
- Xem thử chuyến bay: `python tests/xem_bay_ao_den.py BayLuon_PhaIcon 3 bay.gif`.

## Phá phách v3.14
- Cổ Long khai báo bộ chiêu phá icon trong `NhanVat/CoLong/conf/chibi.json` (mục `freefly`: chiêu, kiểu icon trúng chiêu, điểm trúng đo từ khung hình). Kiểu icon: `hit`, `bite`, `shatter`, `burn`, `zap`, `squeeze`, `poke`.
- Áo Đen: `python tools/dung_ao_den.py` dựng khung bay, rồng hiện từ hư không (`x_hla_in*`, `x_hlb_in*`), đứng nộ sấm sét (`x_aura*`) và tự nối vào `conf/actions.xml` (khối `x:begin … x:end`).
- Xem thử: `python tests/xem_bay_ao_den.py BayLuon_PhaIcon 13 out.gif CoLong 0,0,700,480`.

## Bay lượn mượt (v3.15)
- Bay bằng lái liên tục: hướng uốn theo nhiễu mượt + trò nghịch (lộn vòng, bổ nhào, lạng lách, vụt); thân nghiêng theo hướng bay (xoay hình khi vẽ).
- Chỉ dừng khi đâm mép màn hình (bám tường / treo trần / nảy / đáp đất ra chiêu) hoặc chạm icon (phá).
- Đo độ mượt: `python tests/do_muot_bay.py BayLuon_TuDo NhanVatAoDen 4` (in gia tốc và các cú giật không do va chạm – phải rỗng).

## Hiệu năng (v3.16)
- Luồng chính (vẽ nhân vật, 40 ms/nhịp) không làm việc nặng: dò cửa sổ / icon, chụp màn hình, dựng hình hiệu ứng đều ở luồng phụ; gửi tin cho Explorer có giới hạn chờ.
- Bộ đệm: hiệu ứng gõ ≤ 100 MB/kênh, khung nhân vật ≤ 160 MB.
- Đo lag: `python tests/do_lag.py NhanVatAoDen` (hoặc `CoLong`) – in thời gian từng phần, số lần khựng > 100 ms và RAM.

