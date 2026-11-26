import sys
ARGV = list(sys.argv)
from common import load, make_app
import random, sys
from PIL import Image, ImageDraw, ImageOps
C = load(); app = make_app(C)
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
real_hit = app.icon_fx.hit
def hit(r, dirx=1, strong=False):
    icon = bg.crop(tuple(int(v) for v in r))
    fr, anc = C.icon_hit_frames(icon, dirx, strong, tick["t"])
    overlays.append((tick["t"], fr, anc, ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)))
app.icon_fx.hit = hit
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
        fr.alpha_composite(im, (int(eng.ax - ax), int(eng.ay - p.ay)))
        frames.append(fr.resize((W // 2, H // 2)).convert("RGB"))
    if eng.cur != mode and i > 10 and frames:
        for _ in range(12):
            frames.append(frames[-1])
        break
out = ARGV[3]
frames[0].save(out, save_all=True, append_images=frames[1:], duration=80, loop=0)
print(len(frames), "khung ->", out, "trúng", len(overlays))
