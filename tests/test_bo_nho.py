"""Quản lý bộ nhớ: đo RAM thật, chi tiết bộ đệm, nút xoá bộ nhớ đệm, tự dọn khi vượt ngưỡng, giao diện."""
import sys
import time
from common import load, make_app, check, RESULTS

C = load()
app = make_app(C)
mem = app.mem
rss, peak, priv = C.proc_mem()
check(rss > 20 and peak >= rss * 0.9, "đo được RAM thật của app: %.0f MB (đỉnh %.0f MB)" % (rss, peak))

# làm đầy bộ đệm
kf = app.keyfx
for k in list(C.FX_BY_KEY)[:3]:
    kf.bolt.variants(k, 216, block=True)
for _ in range(60):
    app.pet.tick(0.04)
    app.pet.render()
r = mem.report()
labels = [i[0] for i in r["items"]]
check(len(r["items"]) >= 6 and r["cache_mb"] > 1, "chi tiết %d bộ đệm, tổng %.0f MB: %s" % (len(labels), r["cache_mb"], labels))
check(any(i[2] for i in r["items"]), "bộ đệm có giới hạn hiển thị kèm ngưỡng")

b, a = mem.clear()
r2 = mem.report()
check(r2["cache_mb"] < 1, "Xóa bộ nhớ đệm: bộ đệm hình %.0f MB -> %.1f MB" % (r["cache_mb"], r2["cache_mb"]))
check(mem.last_clean and "bộ nhớ đệm" in " ".join(m for _, m in C.FX_EVENTS), "ghi nhật ký lần dọn")
# sau khi xoá vẫn chạy bình thường
for _ in range(20):
    app.pet.tick(0.04)
    app.pet.render()
vs = kf.bolt.variants(C.fx_resolve(app.store.s.get("key_fx_type", "bolt")), 152, block=True)
check(vs and vs[0], "xoá xong: nhân vật vẽ lại, hiệu ứng dựng lại bình thường")

# tự dọn khi vượt ngưỡng
real = C.proc_mem
C.proc_mem = lambda pid=None: (950.0, 990.0, 900.0)
app.store.s["mem_limit"] = 800
app.store.s["mem_auto"] = True
said = []
app.say = lambda t, x="", timeout=6, key=None: said.append(t)
mem.last_auto = 0
n0 = len(C.FX_EVENTS)
mem.watch()
check(said and "tự dọn" in said[0].lower(), "RAM 950 MB > ngưỡng 800 MB: tự dọn + báo (%s)" % said[:1])
r3 = mem.report()
check(r3["full"], "báo 'sắp đầy' khi vượt 85% ngưỡng")
said.clear()
mem.watch()
check(not said, "không dọn dồn dập (cách nhau ≥ 2 phút)")
app.store.s["mem_auto"] = False
mem.last_auto = 0
mem.watch()
check(not said, "tắt 'tự dọn' thì không tự dọn")
C.proc_mem = real

# giao diện
app.open_manager()
m = app.manager
for _ in range(30):
    app.root.update()
    time.sleep(0.02)
check("RAM đang dùng" in m.mem_lbl.cget("text") and "Khung nhân vật" in m.mem_detail.cget("text"),
      "tab Cài đặt hiển thị bảng bộ nhớ: " + m.mem_lbl.cget("text")[:70])
m._mem_clear()
check("Đã xoá" in m.mem_msg.cget("text") and "bộ nhớ đệm" in m.mem_msg.cget("text"), "nút 'Xóa bộ nhớ đệm' chạy: " + m.mem_msg.cget("text")[:60])

print("\n%d/%d đạt" % (sum(RESULTS), len(RESULTS)))
sys.exit(0 if all(RESULTS) else 1)
