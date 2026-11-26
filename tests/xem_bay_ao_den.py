import sys
ARGV = list(sys.argv)
from common import load, make_app
import random, sys
from PIL import Image, ImageDraw, ImageOps
C = load(); app = make_app(C)
if len(ARGV) > 4:                                   # tham số 4: tên bộ nhân vật (vd CoLong)
    app.switch_pack(C.os.path.join(C.NHANVAT_DIR, ARGV[4]))
random.seed(int(ARGV[2]) if len(ARGV) > 2 else 3)
pet = app.pet; eng = pet.engine; env = pet.env; pk = pet.pack
W, H = 1600, 1000
icons = [C.Platform(x, x + 48, y, "icon") for x, y in ((60, 60), (60, 150), (60, 240), (60, 330), (160, 60), (160, 150), (1450, 80), (1450, 170))]
bg = Image.new("RGBA", (W, H))
d = ImageDraw.Draw(bg)
for y in range(H):
    d.line([(0, y), (W, y)], fill=(20 + y // 25, 50 + y // 30, 90 + y // 20, 255))
cols = [(250, 200, 70), (90, 160, 250), (240, 90, 90), (110, 210, 120), (200, 120, 240), (250, 150, 60), (80, 200, 220), (230, 230, 230)]
for k, ic in enumerate(icons):
    d.rounded_rectangle((ic.x1, ic.y, ic.x2, ic.y + 48), radius=8, fill=cols[k] + (255,))
    d.text((ic.x1 - 2, ic.y + 52), "Icon %d" % (k + 1), fill=(255, 255, 255, 255))
d.rectangle((0, H - 40, W, H), fill=(25, 25, 35, 255))
app.areas = [(0, 0, W, H - 40)]
overlays = []
tick = {"t": 0}
def play(kind, r, dirx=1, strong=False):
    m = C.IconFx.margin(r)
    patch = bg.crop((int(r[0]) - m, int(r[1]) - m, int(r[2]) + m, int(r[3]) + m))
    fr, anc = C.icon_fx_frames(kind, patch, m, dirx, strong, tick["t"])
    overlays.append((tick["t"], fr, anc, ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)))
    kinds.append(kind)
kinds = []
app.icon_fx.play = play
app.icon_fx.prepare = lambda rects: None
for i in range(400):
    env.refresh(); env.icon_plats = icons
    eng.tick()
    if env.on_floor(eng.ax, eng.ay) is not None and eng.cur in ("Stand", "StandAlt", "Walk", "Land"):
        break
mode = ARGV[1]
print("đất", round(eng.ax), round(eng.ay), eng.cur, "force", eng.force(mode, wait=False))
frames = []
for i in range(1200):
    tick["t"] = i
    env.refresh(); env.icon_plats = icons
    eng.tick()
    p = eng.pose
    if i % 2 == 0 and p is not None:
        fn = (p.imgr or p.img) if eng.look_right else p.img
        im = pk.image(fn)
        ax = p.ax
        if eng.look_right and not p.imgr:
            im = ImageOps.mirror(im); ax = im.width - p.ax
        elif eng.look_right:
            ax = im.width - p.ax if False else p.ax
        fr = bg.copy()
        for t0, seq, anc, (cx, cy) in overlays:
            k = i - t0
            if 0 <= k < len(seq):
                o = seq[k]
                fr.alpha_composite(o, (int(cx - o.width * anc[0]), int(cy - o.height * anc[1])))
        ay_ = p.ay
        tl = getattr(eng, "tilt", 0.0) or 0.0
        if abs(tl) >= 1.5:                                   # nghiêng thân như trong app (xoay quanh neo)
            import math as _m
            R = int(_m.ceil(max(_m.hypot(ax - cx, ay_ - cy) for cx in (0, im.width) for cy in (0, im.height)))) + 2
            cv = Image.new("RGBA", (2 * R, 2 * R))
            cv.paste(im, (int(round(R - ax)), int(round(R - ay_))))
            im = cv.rotate(int(round(tl / 3.0)) * 3, Image.BICUBIC, center=(R, R))
            ax, ay_ = R, R
        fr.alpha_composite(im, (int(eng.ax - ax), int(eng.ay - ay_)))
        frames.append((fr if len(ARGV) > 5 else fr.resize((W // 2, H // 2))).convert("RGB"))
    if eng.cur != mode and i > 10 and frames:
        for _ in range(12):
            frames.append(frames[-1])
        break
out = ARGV[3]
if len(ARGV) > 5:                                   # tham số 5: vùng cắt cận cảnh x1,y1,x2,y2 (toạ độ thật)
    x1, y1, x2, y2 = (int(v) for v in ARGV[5].split(","))
    frames = [f.crop((x1, y1, x2, y2)) for f in frames]
frames[0].save(out, save_all=True, append_images=frames[1:], duration=80, loop=0)
print(len(frames), "khung ->", out, "trúng", len(overlays), kinds)
