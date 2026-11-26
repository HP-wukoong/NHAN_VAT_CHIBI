"""Hiệu ứng gõ phím chạy ổn định: tự khôi phục khi Windows gỡ hook, luồng bắt phím chết, cửa sổ hiệu ứng kẹt/hỏng,
bộ dò con trỏ sập, phần mềm không báo vị trí con trỏ; nút Khắc phục; báo cáo; cỡ nhỏ tối đa."""
import sys
import time
from common import load, make_app, check, RESULTS

C = load()
app = make_app(C)
kf = app.keyfx


class FakeThread:
    def __init__(self, alive):
        self.a = alive

    def is_alive(self):
        return self.a


class FakeGM:
    def __init__(self):
        self.thread = FakeThread(True)
        self.tid = 1
        self.cb_tick = 1000
        self.key_tick = 1000
        self.khook_ok = True
        self.reinstalls = 0
        self.last_fix = 0.0
        self.started = 0
        self.re = 0

    def alive(self):
        return self.thread.is_alive()

    def start(self):
        self.started += 1
        self.thread = FakeThread(True)

    def reinstall(self):
        self.re += 1
        self.reinstalls += 1


real_gm = app.gmouse
gm = FakeGM()
app.gmouse = gm
C.IS_WIN = True
tick = {"v": 1200}
C.last_input_tick = lambda: tick["v"]
kf.started = 0

# 1) hook còn sống (thao tác mới nhất hook đều thấy) -> không đụng tới
kf._watch()
check(gm.re == 0, "hook còn sống: không cài lại vô cớ")
# 2) Windows có thao tác mới (5 giây sau) mà hook không thấy -> cài lại
tick["v"] = 6000
kf._watch()
check(gm.re == 1, "Windows gỡ hook (có thao tác mà hook không thấy) -> tự cài lại")
check(kf.auto_fixes >= 1 and any("hook" in m for _, m in C.FX_EVENTS), "ghi nhật ký lần tự khôi phục")
kf._watch()
check(gm.re == 1, "không cài lại dồn dập (chờ ≥ 8 giây giữa 2 lần)")
# 3) tràn số GetTickCount (máy chạy > 49 ngày) không bị hiểu nhầm
gm.last_fix = 0
gm.cb_tick = gm.key_tick = 0xFFFFFF00
tick["v"] = 0x50
kf._watch()
check(gm.re == 1, "GetTickCount tràn vòng: không báo nhầm")
# 4) luồng bắt phím chết -> chạy lại
gm.thread = FakeThread(False)
kf._watch()
check(gm.started == 1, "luồng bắt phím chết -> tự chạy lại")
# 5) hook bàn phím chưa cài được -> cài lại
gm.khook_ok = False
gm.last_fix = 0
gm.cb_tick = gm.key_tick = tick["v"]
kf._watch()
check(gm.re == 2, "hook bàn phím chưa cài được -> cài lại")
lv, title, lines, probs = kf.health()
check(lv == "warn" and "hook" in title.lower(), "bảng tình trạng báo lỗi hook: " + title)
gm.khook_ok = True
C.IS_WIN = False
app.gmouse = real_gm

# 6) cửa sổ hiệu ứng: kẹt / vẽ lỗi -> làm mới
pl = kf.bolt
pl.live = [dict(seq=[(b"", 1, 1)] * 5, i=0, pos=(0, 0), anchor=(0.5, 0.5), slot=0)]
pl.job = None
kf._watch()
check(pl.job is not None, "hàng phát mất nhịp -> chạy lại")
pl.last_step = C.time_now() - 10
kf._watch()
check(not pl.live and pl.job is None, "hiệu ứng kẹt > 3 giây -> gỡ, làm mới cửa sổ")
pl.fails = 3
kf._watch()
check(pl.fails == 0, "cửa sổ vẽ lỗi liên tục -> tạo lại")

# 7) bộ dò con trỏ sập 3 lần: nghỉ 1 phút rồi tự thử lại (trước đây tắt vĩnh viễn)
C.IS_WIN = True
kf.finder.crashes = 3
kf.finder.crash_t = C.time_now()
check(not kf.finder.available(), "sập 3 lần: tạm nghỉ")
kf.finder.crash_t = C.time_now() - 61
check(kf.finder.available() and kf.finder.crashes == 0, "sau 1 phút: tự thử lại")
C.IS_WIN = False

# 8) phần mềm không báo vị trí con trỏ mới -> sau 4 cú gõ chuyển sang tin cú gõ (không bỏ qua mãi)
kf.trust.clear()
kf.skip_run.clear()
kf.bolt.variants(C.fx_resolve(app.store.s.get("key_fx_type", "bolt")), 152, block=True)   # như app dựng sẵn lúc mở
kf.last_size = 152
n0 = kf.bolt.played
kf.prev_caret = ((300, 300), C.time_now())
for _ in range(3):
    kf._skip("T", (300, 300), None)
check(kf.bolt.played == n0, "3 lần đầu: vẫn coi là gõ không đổi nội dung")
kf._skip("T", (300, 300), None)
check(kf.bolt.played == n0 + 1 and kf.trust, "lần 4: phát hiệu ứng + ghi nhận phần mềm này")
check(kf._changed((300, 300)), "từ đó cú gõ ở phần mềm này luôn có hiệu ứng")
kf._skip("D", (300, 300), None)
kf.trust.clear()
kf.skip_run.clear()
for _ in range(6):
    kf._skip("D", (300, 300), None)
check(not kf.trust, "Backspace ở đầu dòng nhiều lần KHÔNG làm tắt kiểm tra (chỉ tính gõ ký tự)")

# 9) cỡ: giảm tối đa
app.store.s["key_fx_size"] = 0.05
check(kf.size() <= 20 and kf.size(8) <= 20, "hệ số cỡ nhỏ nhất -> hiệu ứng ~16 px (trước: kẹt ở 60 px)")
fr = C.FX_BY_KEY[C.fx_resolve(app.store.s.get("key_fx_type", "bolt"))][2](kf.size(), 0, "T")
check(sum(1 for f in fr if f.getbbox()) > 3, "cỡ rất nhỏ vẫn dựng được hình")
app.store.s["key_fx_size"] = 1.0

# 10) dựng hình không khựng: đổi cỡ gần giống -> dùng tạm cỡ có sẵn, dựng cỡ đúng ở luồng phụ
key = C.fx_resolve(app.store.s.get("key_fx_type", "bolt"))
pl.variants(key, 152)
t = time.time()
vs = pl.variants(key, 168)
check(vs and time.time() - t < 0.2, "cỡ mới gần giống: trả về ngay (%.0f ms), không chặn luồng chính" % ((time.time() - t) * 1000))
for _ in range(100):
    if pl.cache.get((key, 168, "T")):
        break
    time.sleep(0.1)
check(bool(pl.cache.get((key, 168, "T"))), "cỡ đúng được dựng xong ở luồng phụ")

# 11) nút Khắc phục & làm mới + báo cáo
ok, msg = kf.fix()
check(ok, "Khắc phục & làm mới: " + msg)
rep = kf.report()
check("BÁO CÁO HIỆU ỨNG GÕ PHÍM" in rep and "Khắc phục" in rep, "báo cáo có tình trạng + nhật ký")
lv, title, _, _ = kf.health()
check(lv == "ok", "sau khắc phục: " + title)
app.store.s["key_fx"] = False
check(kf.health()[0] == "off", "tắt hiệu ứng: báo đang tắt")
app.store.s["key_fx"] = True

# 12) phím vẫn tới hiệu ứng khi nhân vật đang ẩn
app.hidden = True
n0 = kf.keys_seen
app.gmouse.q.put(("K", "T", 0x41))
app.gmouse.poll()
check(kf.keys_seen == n0 + 1, "ẩn nhân vật: hiệu ứng gõ vẫn nhận phím")
app.hidden = False

print("\n%d/%d đạt" % (sum(RESULTS), len(RESULTS)))
sys.exit(0 if all(RESULTS) else 1)
