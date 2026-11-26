"""Áo Đen: khung vẽ thêm, bay tự do toàn màn hình (kể cả 2 màn hình), phá icon (chỉ hiệu ứng), chọc chuột,
quay người khi đổi hướng, nhảy parabol có lấy đà; Cổ Long không bị ảnh hưởng."""
import sys
import math
import random
from common import load, make_app, check, RESULTS

C = load()
app = make_app(C)
pet, eng, env = app.pet, app.pet.engine, app.pet.env
pk = pet.pack
check(pk.name == "Áo Đen", "đang dùng nhân vật Áo Đen")
check(len(pk.xk) >= 22, "có %d khung vẽ thêm (bay, bổ nhào, cất cánh, quay người)" % len(pk.xk))
for n in ("BayLuon_PhaIcon", "BayLuon_TuDo", "BayLuon_ChocChuot"):
    check(n in pk.behaviors and n in pk.user_behaviors(), "có hành vi %s (%s), bật/tắt & gán chuột được" % (n, C.beh_label(n)))
check(any(n == "BayLuon_PhaIcon" for n, _, _ in pk.behaviors["Stand"].nexts), "đang đứng có thể tự chuyển sang bay phá icon")

hits = []
app.icon_fx.play = lambda kind, r, d=1, strong=False: hits.append((r, d, strong, kind))
app.icon_fx.prepare = lambda rects: None


def land():
    for _ in range(500):
        env.refresh()
        env.icon_plats = ICONS
        eng.tick()
        if env.on_floor(eng.ax, eng.ay) is not None and eng.cur in ("Stand", "StandAlt", "Walk", "Land", "Run"):
            return True
    return False


def fly(mode, n=3000):
    land()
    ok = eng.force(mode, wait=False)
    path, imgs = [], set()
    for i in range(n):
        env.refresh()
        env.icon_plats = ICONS
        eng.tick()
        path.append((eng.ax, eng.ay))
        if eng.pose:
            imgs.add(eng.pose.img)
        if eng.cur != mode:
            break
    return ok, path, imgs, i


def inside(path):
    for x, y in path:
        if not any(a[0] - 1 <= x <= a[2] + 1 and a[1] - 1 <= y <= a[3] + 1 for a in app.areas):
            return False
    return True


app.areas = [(0, 0, 1600, 960)]
ICONS = [C.Platform(40, 88, 40 + k * 90, "icon") for k in range(5)] + [C.Platform(1500, 1548, 60, "icon")]
random.seed(7)
ok, path, imgs, n = fly("BayLuon_PhaIcon")
check(ok, "ra lệnh bay phá icon")
check(len(hits) >= 2, "trúng %d cú vào icon" % len(hits))
check(any(i.startswith("x_bay") for i in imgs) and any(i.startswith("x_catcanh") for i in imgs),
      "dùng khung bay ngang + cất cánh")
check(min(y for _, y in path) < 300 and max(x for x, _ in path) - min(x for x, _ in path) > 600,
      "bay rộng khắp màn hình (lên cao, sang ngang)")
check(inside(path), "không bay ra ngoài màn hình")
step = max(abs(path[k][0] - path[k - 1][0]) + abs(path[k][1] - path[k - 1][1]) for k in range(1, len(path)))
check(step < 60, "chuyển động liền mạch, không giật cục (bước lớn nhất %d px/nhịp)" % step)
check(env.on_floor(eng.ax, eng.ay) is not None, "bay xong hạ cánh an toàn xuống đất")
check(n < 1600, "chuyến bay kết thúc (%.1f giây)" % (n * 0.04))

# 2 màn hình: bay sang được màn hình kia
app.areas = [(0, 0, 1600, 960), (1600, 0, 3200, 960)]
random.seed(11)
xs = []
for _ in range(3):
    ok, path, imgs, n = fly("BayLuon_TuDo")
    xs += [x for x, _ in path]
check(min(xs) < 1600 < max(xs), "2 màn hình: bay qua lại giữa hai màn hình")
check(inside(path), "2 màn hình: vẫn trong vùng màn hình")
app.areas = [(0, 0, 1600, 960)]

# chọc chuột: lượn vòng quanh con trỏ
env.refresh()
random.seed(5)
land()
eng.force("BayLuon_ChocChuot", wait=False)
near = 0
for i in range(2500):
    env.refresh()
    env.cursor = (800, 400)
    eng.tick()
    if abs(eng.ax - 800) < 160 and abs(eng.ay - 440) < 120:
        near += 1
    if eng.cur != "BayLuon_ChocChuot":
        break
check(near > 20, "chọc chuột: lượn vòng sát con trỏ (%d nhịp)" % near)

# tắt phá icon -> không đụng icon
app.store.s["pha_icon"] = False
hits.clear()
random.seed(3)
fly("BayLuon_PhaIcon")
check(not hits, "tắt 'phá icon': chỉ bay lượn, không đánh icon")
app.store.s["pha_icon"] = True

# hiệu ứng icon: kết thúc trong suốt (icon thật lộ lại nguyên vẹn)
from PIL import Image
icon = Image.new("RGBA", (48, 48), (250, 200, 70, 255))
fr, anc = C.icon_hit_frames(icon, 1, True, 1)
check(len(fr) >= 15 and fr[-1].getbbox() is None, "icon trúng đòn: %d khung, khung cuối trong suốt" % len(fr))
W, H = fr[0].size
ox, oy = int(W * anc[0] - 24), int(H * anc[1] - 24)
check(fr[6].crop((ox, oy, ox + 48, oy + 48)).getbbox() is not None, "bản sao icon đè đúng chỗ icon thật")

# quay người khi đổi hướng
land()
q = list(eng.turn(not eng.look_right))
check(len(q) == 8 and all(p.img.startswith("x_quay") for p in q), "đổi hướng: xoay người 8 nhịp")

# nhảy parabol: có lấy đà, có đỉnh cao hơn cả 2 đầu
land()
y0 = eng.ay
ys, imgs = [], []
for p in eng.jump_to(eng.ax + 200, y0 - 120):
    ys.append(eng.ay)
    imgs.append(p.img)
check(imgs[0].startswith("x_catcanh"), "nhảy: khuỵu gối lấy đà trước")
check(min(ys) < y0 - 120 - 10, "nhảy: bay theo đường parabol (đỉnh cao hơn chỗ đáp)")

# ── Áo Đen: rồng hiện từ hư không + đứng nộ sấm sét ──
acts = pk.actions
check([r for r, _ in acts["HacLong_NhayVut"].refs][2] == "HL_RongHienB" and
      [r for r, _ in acts["HacLong_BayTheoChuot"].refs][2] == "HL_RongHienA", "2 chiêu rồng: có đoạn rồng hiện ra trước")
for L, base in (("A", "hl_a0"), ("B", "hl_b0")):
    ps = acts["HL_RongHien" + L].poses
    first, last = pk.image(ps[0].img), pk.image(ps[15].img)
    orig = pk.image(base + ".png")
    import numpy as np
    a0 = np.asarray(first)[..., 3].astype(int).sum()
    a1 = np.asarray(orig)[..., 3].astype(int).sum()
    check(a0 < a1 * 0.5, "rồng %s: khung đầu chỉ có người + khe hư không (%.0f%% điểm ảnh)" % (L, 100.0 * a0 / a1))
    check(last.tobytes() == orig.tobytes(), "rồng %s: khung cuối đúng y ảnh gốc" % L)
nk = [p.img for p in acts["NoKhi"].poses]
check(all(i.startswith("x_aura") for i in nk if "aura" in i and "aurafade2" not in i) and any(i.startswith("x_aura") for i in nk),
      "đứng nộ: dùng khung sấm sét bao phủ (bỏ 2 vòng cung)")
im = pk.image("x_aura3.png")
arr = np.asarray(im)
red = ((arr[..., 0] > 200) & (arr[..., 1] < 140) & (arr[..., 3] > 150)).sum()
check(red > 400, "khung nộ khí có tia sét đỏ (%d điểm)" % red)

# ── Cổ Long: phá phách riêng ──
app.switch_pack(C.os.path.join(C.NHANVAT_DIR, "CoLong"))
pet, eng, env = app.pet, app.pet.engine, app.pet.env
kit = eng.fly_kit()
fx = sorted(a["fx"] for a in kit["attacks"])
check(fx == ["bite", "burn", "shatter", "squeeze", "zap"], "Cổ Long: ôm cắn, quật đuôi vỡ, phun lửa cháy, phun sét, cuộn siết (%s)" % fx)
check(all(n in pet.pack.behaviors for n in ("BayLuon_PhaIcon", "BayLuon_DuoiBatChuot", "LongKy_OmCan", "LongKy_QuatDuoi")),
      "Cổ Long có hành vi bay phá icon, đuổi bắt chuột, ôm cắn, quật đuôi")
hits.clear()
app.icon_fx.play = lambda kind, r, d=1, strong=False: hits.append((r, d, strong, kind))
seen = set()
for sd in (2, 5, 9, 13):
    random.seed(sd)
    ok, path, imgs, n = fly("BayLuon_PhaIcon")
    seen |= {h[3] for h in hits}
check(len(seen) >= 3, "Cổ Long phá icon bằng nhiều chiêu khác nhau: %s" % sorted(seen))
check(inside(path) and env.on_floor(eng.ax, eng.ay) is not None, "Cổ Long bay trong màn hình, xong hạ cánh")

# đứng đúng chỗ ra đòn: điểm trúng (miệng / chóp đuôi) trùng tâm icon
eng.ax, eng.ay = 900.0, 500.0
st = dict(vx=0.0, vy=0.0, t=0, bay=kit["bay"], up=[], dn=[], hov=kit["hov"], kit=kit)
rect = (600, 300, 648, 348)
for atk in kit["attacks"]:
    got = []
    app.icon_fx.play = lambda kind, r, d=1, strong=False: got.append((eng.ax, eng.ay, eng.look_right))
    eng.ax, eng.ay = 900.0, 500.0
    list(eng._smash(rect, st, atk))
    ax, ay, right = got[0]
    hx = ax + (-atk["dx"] if right else atk["dx"])
    hy = ay + atk["dy"]
    check(abs(hx - 624) < 14 and abs(hy - 324) < 14, "%s: điểm trúng cách tâm icon %d px" % (atk["act"], math.hypot(hx - 624, hy - 324)))

# ── hiệu ứng icon: mọi kiểu kết thúc trong suốt (icon thật lộ lại nguyên vẹn) ──
patch = Image.new("RGBA", (64, 64), (40, 70, 110, 255))
for kind in ("hit", "bite", "shatter", "burn", "zap", "squeeze", "poke"):
    fr, anc = C.icon_fx_frames(kind, patch, 8, 1, True, 1)
    check(len(fr) >= 10 and fr[-1].getbbox() is None, "icon %s: %d khung, khung cuối trong suốt" % (kind, len(fr)))

print("\n%d/%d đạt" % (sum(RESULTS), len(RESULTS)))
sys.exit(0 if all(RESULTS) else 1)
