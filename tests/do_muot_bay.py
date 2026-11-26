"""Đo độ mượt khi bay: python tests/do_muot_bay.py <hành vi> <bộ nhân vật> <seed>  – in gia tốc, các cú giật không do va chạm."""
import sys
ARGV = list(sys.argv)
from common import load, make_app
import random, math
C = load(); app = make_app(C)
if len(ARGV) > 2:
    app.switch_pack(C.os.path.join(C.NHANVAT_DIR, ARGV[2]))
pet, eng, env = app.pet, app.pet.engine, app.pet.env
app.areas = [(0, 0, 1600, 960)]
ICONS = [C.Platform(40, 88, 40 + k * 90, "icon") for k in range(5)]
ev = []
app.icon_fx.play = lambda kind, r, d=1, strong=False: ev.append(("icon", len(path)))
for _ in range(500):
    env.refresh(); env.icon_plats = ICONS; eng.tick()
    if env.on_floor(eng.ax, eng.ay) is not None and eng.cur in ("Stand", "StandAlt", "Walk", "Land", "Run"): break
random.seed(int(ARGV[3]) if len(ARGV) > 3 else 4)
mode = ARGV[1]
bumps = []
_rb = eng._react_bump
def rb(side, st):
    bumps.append((len(path), side))
    return _rb(side, st)
eng._react_bump = rb
_sm = eng._smash
def sm(rect, st, atk=None):
    bumps.append((len(path), "icon"))
    return _sm(rect, st, atk)
eng._smash = sm
_cs = eng._fly_clamp_soft
def cs(p, k=1.0, cap=14.0):
    x0, y0 = eng.ax, eng.ay
    _cs(p, k, cap)
    if abs(eng.ax - x0) + abs(eng.ay - y0) > 0.5:
        bumps.append((len(path), "mép"))
eng._fly_clamp_soft = cs
eng.force(mode, wait=False)
path, poses, tilts = [], [], []
pitch = []
for i in range(3000):
    env.refresh(); env.icon_plats = ICONS; eng.tick()
    path.append((eng.ax, eng.ay)); poses.append(eng.pose.img if eng.pose else ""); tilts.append(eng.tilt if not eng.look_right else -eng.tilt)
    if eng.cur != mode: break
fly = set(k for k, p in enumerate(poses) if p.startswith(("x_bay", "fly")))
acc, where = [], []
for k in range(1, len(path) - 1):
    if k - 1 in fly and k in fly and k + 1 in fly:
        a1 = (path[k][0] - path[k - 1][0], path[k][1] - path[k - 1][1])
        a2 = (path[k + 1][0] - path[k][0], path[k + 1][1] - path[k][1])
        acc.append(math.hypot(a2[0] - a1[0], a2[1] - a1[1])); where.append(k)
sp = [math.hypot(path[k][0] - path[k - 1][0], path[k][1] - path[k - 1][1]) for k in sorted(fly) if k > 0 and k - 1 in fly]
slow = sum(1 for x in sp if x < 2.0)
dt = [abs(tilts[k] - tilts[k - 1]) for k in range(1, len(tilts)) if k in fly and k - 1 in fly]
acc_s = sorted(acc)
print("%s: %d nhịp (%.1fs), bay %d nhịp, tốc độ TB %.1f px/nhịp" % (mode, len(path), len(path) * 0.04, len(fly), sum(sp) / max(1, len(sp))))
print("gia tốc: trung vị %.2f, 99%% %.2f, max %.1f px/nhịp²; nhịp bay chậm (<2px) %d; đổi nghiêng max %.1f°/nhịp"
      % (acc_s[len(acc_s) // 2], acc_s[int(len(acc_s) * 0.99)], acc_s[-1], slow, max(dt or [0])))
big = [(round(acc[i], 1), where[i], poses[where[i] - 1], poses[where[i] + 1]) for i in range(len(acc)) if acc[i] > 4]
print("cú giật >4:", big[:8])
print("sự kiện (nhịp, loại):", [b for b in bumps if b[1] != "mép"][:12], "chạm mép %d nhịp" % sum(1 for b in bumps if b[1] == "mép"))
evk = [b[0] for b in bumps]
free = [(a_, k) for a_, k, _, _ in big if not any(-4 <= k - e <= 6 for e in evk)]
print("GIẬT KHÔNG DO VA CHẠM:", free)
print("trúng icon", sum(1 for e in ev if e[0] == "icon"), "| khung dùng:", sorted(set(p.split(".")[0].rstrip("0123456789") for p in poses))[:14])
