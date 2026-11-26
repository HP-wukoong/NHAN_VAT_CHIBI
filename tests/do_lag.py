"""Đo độ trễ vòng lặp chính (lag / đơ): python tests/do_lag.py [bộ nhân vật]"""
import sys
ARGV = list(sys.argv)
from common import load, make_app
import time, random, collections
C = load(); app = make_app(C)
if len(ARGV) > 1:
    app.switch_pack(C.os.path.join(C.NHANVAT_DIR, ARGV[1]))
T = collections.defaultdict(list)


def wrap(obj, name, label):
    f = getattr(obj, name)
    def g(*a, **k):
        t = time.perf_counter()
        try:
            return f(*a, **k)
        finally:
            T[label].append((time.perf_counter() - t) * 1000)
    setattr(obj, name, g)


wrap(app, "anim_loop", "vòng lặp chính (1 nhịp)")
wrap(app.pet, "render", "vẽ nhân vật")
wrap(app.pet, "frame_rot", "xoay nghiêng 1 khung")
wrap(app.pet.engine if app.pet.engine else app.pet, "tick", "engine 1 nhịp")
wrap(app.pet.env, "refresh", "dò cửa sổ / icon")
wrap(app.icon_fx, "play", "dựng hiệu ứng icon")
wrap(app.icon_fx, "prepare", "chụp icon")
wrap(app.keyfx, "on_key", "xử lý 1 phím")
wrap(app.keyfx.bolt, "_step", "phát hiệu ứng gõ")
ICONS = [C.Platform(40, 88, 40 + k * 90, "icon") for k in range(5)]
_r = app.pet.env.refresh
def rf(force=False):
    _r(force)
    app.pet.env.icon_plats = ICONS
app.pet.env.refresh = rf
random.seed(3)
t0 = time.time()
def driver():
    el = time.time() - t0
    if 3 < el and app.pet.engine.cur not in ("BayLuon_PhaIcon",) and el < 30 and int(el) % 9 == 3:
        app.pet.engine.force("BayLuon_PhaIcon", wait=False)
    if 2 < el < 38:
        app.keyfx.on_key("T", 0x41)                  # gõ ~ 12 phím / giây
    if el > 40:
        app.root.quit()
        return
    app.root.after(80, driver)
app.root.after(500, driver)
gaps = []
last = [time.perf_counter()]
def gap():
    t = time.perf_counter(); gaps.append((t - last[0]) * 1000); last[0] = t
    app.root.after(10, gap)
app.root.after(10, gap)
app.root.mainloop()
def stat(v):
    v = sorted(v)
    return "n=%4d  TB %6.1f  95%% %6.1f  max %7.1f ms" % (len(v), sum(v) / len(v), v[int(len(v) * 0.95)], v[-1])
for k, v in T.items():
    if v:
        print("%-28s %s" % (k, stat(v)))
g = sorted(gaps)
print("%-28s %s   (khựng >100ms: %d lần, >250ms: %d lần)" % ("giao diện bị chặn (nhịp 10ms)", stat(g), sum(1 for x in g if x > 100), sum(1 for x in g if x > 250)))
import resource
def cache_mb(c):
    tot = 0
    for v in list(c.values()):
        for item in (v if isinstance(v, list) else [v]):
            for fr in (item if isinstance(item, list) else [item]):
                d = fr[0] if isinstance(fr, tuple) else fr
                tot += len(d) if isinstance(d, (bytes, bytearray)) else 0
    return tot / 1e6
print("RAM đỉnh: %.0f MB | đệm khung nhân vật: %d khung, %.0f MB | đệm hiệu ứng gõ: %.0f + %.0f MB" % (
    resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, len(app.pet.cache), cache_mb(app.pet.cache),
    cache_mb(app.keyfx.bolt.cache), cache_mb(app.keyfx.slash.cache)))
