"""Chống lag / đơ: luồng vẽ nhân vật không bao giờ phải chờ Explorer, cửa sổ bị treo, chụp màn hình hay dựng hình;
bộ đệm hình có giới hạn dung lượng (không ngốn RAM)."""
import sys
import time
from common import load, make_app, check, RESULTS

C = load()
app = make_app(C)
env = app.pet.env

# 1) Explorer / cửa sổ bị treo: dò ở luồng phụ, luồng chính vẫn mượt
calls = {"win": 0, "icon": 0}


def slow_win():
    calls["win"] += 1
    time.sleep(2.0)                                   # giả lập cửa sổ bị treo
    return [C.Platform(100, 600, 300, "win", 1)]


def slow_icons():
    calls["icon"] += 1
    time.sleep(2.0)                                   # giả lập Explorer bận
    return [C.Platform(40, 88, 40, "icon")]


C.window_platforms, C.desktop_icon_platforms = slow_win, slow_icons
C.IS_WIN = True
worst = 0.0
for _ in range(55):
    t = time.perf_counter()
    env.refresh()
    worst = max(worst, time.perf_counter() - t)
    time.sleep(0.1)
C.IS_WIN = False
check(worst < 0.02, "Explorer / cửa sổ bị treo 2 giây: luồng chính vẫn chỉ mất %.1f ms mỗi lần dò" % (worst * 1000))
check(calls["win"] >= 1 and calls["icon"] >= 1 and env.win_plats and env.all_icons,
      "dò ở luồng phụ vẫn ra kết quả (%d cửa sổ, %d icon)" % (len(env.win_plats), len(env.all_icons)))
src = open(C.__file__, encoding="utf-8").read()
check("SendMessageTimeoutW" in src and "u32.SendMessageW(lv" not in src, "gửi tin cho Explorer có giới hạn chờ (không đơ khi Explorer treo)")

# 2) icon trúng chiêu: dựng hình ở luồng phụ, luồng chính không chờ
fx = app.icon_fx
played = []
fx.player.play_frames = lambda x, y, fr, anc=(0.5, 0.5): played.append(len(fr))
rect = (300, 300, 348, 348)
t = time.perf_counter()
fx.play("burn", rect, 1, True)
dt = time.perf_counter() - t
check(dt < 0.02, "phát hiệu ứng icon cháy: luồng chính mất %.1f ms (dựng ở luồng phụ)" % (dt * 1000))
for _ in range(100):
    fx.poll()
    if played:
        break
    time.sleep(0.05)
check(played and played[0] > 20, "dựng xong là tự phát (%s khung)" % (played[:1]))
fx.prebake("shatter", rect, -1, False)
time.sleep(1.5)
fx.poll()
played.clear()
t = time.perf_counter()
fx.play("shatter", rect, -1, False)
check(played and time.perf_counter() - t < 0.01, "dựng sẵn lúc bắt đầu tung chiêu -> tới nhịp trúng phát ngay")

# 4) phím đầu tiên khi chưa có hình: không chặn luồng chính, hình xong thì phát
pl = app.keyfx.bolt
pl.cache.clear()
pl.played = 0
t = time.perf_counter()
pl.play(500, 400, 156, "lientinh")
dt = time.perf_counter() - t
check(dt < 0.02, "phím đầu (chưa có hình): luồng chính mất %.1f ms" % (dt * 1000))
for _ in range(120):
    app.root.update()
    if pl.played:
        break
    time.sleep(0.05)
check(pl.played == 1, "hình dựng xong -> hiệu ứng của phím đó vẫn được phát")

# 3) bộ đệm hiệu ứng gõ có giới hạn dung lượng
pl = app.keyfx.bolt
keys = list(C.FX_BY_KEY)[:4]
for k in keys:
    for sz in (152, 340, 536):
        pl.variants(k, sz, block=True)
check(pl.cache_mb() <= C.FX_CACHE_MB, "đệm hiệu ứng gõ %.0f MB ≤ %d MB (trước đây có thể > 1 GB)" % (pl.cache_mb(), C.FX_CACHE_MB))
sizes = sorted(set(app.keyfx.size(h) for h in range(6, 120)))
check(len(sizes) <= 26, "cỡ hiệu ứng gom theo bậc: %d cỡ cho mọi cỡ chữ" % len(sizes))

# 5) đệm khung nhân vật có giới hạn
pet = app.pet
for z in (0.8, 1.0, 1.3, 1.7, 2.2, 2.8):
    pet.zoom = z
    for fn in list(pet.pack.images)[:40] or ["stand0.png"]:
        pet.frame(fn, False, False)
check(getattr(pet, "cache_bytes", 0) <= C.PET_CACHE_MB * 1e6, "đệm khung nhân vật %.0f MB ≤ %d MB" % (
    getattr(pet, "cache_bytes", 0) / 1e6, C.PET_CACHE_MB))

print("\n%d/%d đạt" % (sum(RESULTS), len(RESULTS)))
sys.exit(0 if all(RESULTS) else 1)
