"""Áo Đen: khung vẽ thêm, bay tự do toàn màn hình (kể cả 2 màn hình), phá icon (chỉ hiệu ứng), chọc chuột,
quay người khi đổi hướng, nhảy parabol có lấy đà; Cổ Long không bị ảnh hưởng."""
import sys
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
app.icon_fx.hit = lambda r, d=1, strong=False: hits.append((r, d, strong))
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

# Cổ Long không bị bơm hành vi bay của Áo Đen
p2 = C.ShimejiPack(C.os.path.join(C.NHANVAT_DIR, "CoLong"))
check(not any(n.startswith("BayLuon") for n in p2.behaviors), "Cổ Long giữ nguyên bộ hành vi riêng")

print("\n%d/%d đạt" % (sum(RESULTS), len(RESULTS)))
sys.exit(0 if all(RESULTS) else 1)
