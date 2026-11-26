#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Vẽ thêm khung cho nhân vật Áo Đen từ chính nét vẽ gốc (NhanVat/NhanVatAoDen/*.png):
  x_bay0-7      bay ngang (tư thế lao) – khăn đỏ, vạt áo phần phật theo gió, vệt tốc độ
  x_baylen0-3   bay chúi lên        x_bayxuong0-3  bổ nhào xuống
  x_catcanh0-3  khuỵu gối lấy đà -> bật lên, vòng gió dưới chân
  x_quay0-1     quay người khi đổi hướng
Ảnh gốc hướng mặt sang TRÁI; app tự lật khi quay phải. Ghi neo (chân / tâm) vào conf/x_khung.json.
Chạy: python tools/dung_ao_den.py   (cần Pillow + numpy)"""
import json
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.join(os.path.dirname(HERE), "NhanVat", "NhanVatAoDen")
PAD = 40


def load(n):
    return Image.open(os.path.join(PACK, n + ".png")).convert("RGBA")


def padded(im, p=PAD):
    o = Image.new("RGBA", (im.width + 2 * p, im.height + 2 * p), (0, 0, 0, 0))
    o.alpha_composite(im, (p, p))
    return o


def flutter(im, phase, amp, side=1, k=0.09, start=0.45):
    """Gió thổi: điểm ảnh càng xa về phía sau (side=1: bên phải) càng lượn sóng mạnh (khăn, vạt áo, tóc)."""
    a = np.asarray(im).astype(np.float32)
    h, w = a.shape[:2]
    al = a[..., 3] > 20
    xs = np.where(al.any(0))[0]
    x0, x1 = xs.min(), xs.max()
    cx = x0 + (x1 - x0) * start
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    t = np.clip(((xx - cx) * side) / max(1.0, (x1 - cx if side > 0 else cx - x0)), 0, 1) ** 1.6
    dy = amp * t * np.sin(phase - xx * k * side)
    dx = amp * 0.35 * t * np.cos(phase * 1.3 - yy * 0.12)
    sy = np.clip(yy - dy, 0, h - 1)
    sx = np.clip(xx - dx, 0, w - 1)
    # nội suy song tuyến
    x0i, y0i = np.floor(sx).astype(int), np.floor(sy).astype(int)
    x1i, y1i = np.clip(x0i + 1, 0, w - 1), np.clip(y0i + 1, 0, h - 1)
    fx, fy = (sx - x0i)[..., None], (sy - y0i)[..., None]
    out = (a[y0i, x0i] * (1 - fx) * (1 - fy) + a[y0i, x1i] * fx * (1 - fy) + a[y1i, x0i] * (1 - fx) * fy +
           a[y1i, x1i] * fx * fy)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")


def streaks(im, f, n=6, side=1, col=(235, 235, 255)):
    """Vệt tốc độ phía sau lưng."""
    o = im.copy()
    a = np.asarray(o)[..., 3]
    ys, xs = np.nonzero(a > 40)
    if not len(xs):
        return o
    d = ImageDraw.Draw(o)
    rnd = np.random.RandomState(f * 7 + 3)
    y0, y1 = ys.min(), ys.max()
    for i in range(n):
        y = int(y0 + (y1 - y0) * (i + 0.5) / n + rnd.uniform(-4, 4))
        row = xs[np.abs(ys - y) < 3]
        if not len(row):
            continue
        xe = row.max() if side > 0 else row.min()
        L = rnd.uniform(18, 46)
        off = (f * 9 + i * 13) % 16
        xa, xb = xe + side * (6 + off), xe + side * (6 + off + L)
        al = int(rnd.uniform(90, 170))
        d.line([(xa, y), (xb, y)], fill=col + (al,), width=1)
    return o


def trim(im, extra=2):
    bb = im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    if not bb:
        return im, (0, 0)
    bb = (max(0, bb[0] - extra), max(0, bb[1] - extra), min(im.width, bb[2] + extra), min(im.height, bb[3] + extra))
    return im.crop(bb), bb[:2]


def foot_anchor(im):
    """Neo kiểu Shimeji: giữa thân theo chiều ngang, đáy hình."""
    a = np.asarray(im)[..., 3] > 60
    ys, xs = np.nonzero(a)
    return int(round(xs.mean())), int(ys.max())


def body_ref(im, ky=0.78):
    """Điểm tham chiếu cố định của THÂN (trọng tâm vùng đặc) – tính trên ảnh gốc đã xoay, trước khi thêm khăn bay /
    vệt tốc độ, để mọi khung cùng neo đúng một chỗ trên thân (không giật)."""
    a = np.asarray(im)[..., 3] > 120
    ys, xs = np.nonzero(a)
    return float(xs.mean()), float(ys.min() + (ys.max() - ys.min()) * ky)


def save(name, im, anchor, meta):
    im.save(os.path.join(PACK, name + ".png"), optimize=True)
    meta[name] = [int(anchor[0]), int(anchor[1])]


def ring(im, cx, cy, rx, ry, al, w=2, col=(225, 235, 255)):
    d = ImageDraw.Draw(im)
    d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), outline=col + (int(al),), width=w)


# ── RỒNG HIỆN TỪ HƯ KHÔNG (hl_a / hl_b) ──
# vùng thân nhân vật (đo tay trên ảnh gốc) – luôn hiện; phần còn lại là rồng, hiện dần dọc thân từ mõm
CHAR_POLY = {
    "hl_a0": [(58, 58), (78, 58), (80, 72), (97, 74), (108, 92), (116, 112), (114, 132), (110, 150), (122, 168),
              (124, 197), (104, 200), (96, 172), (82, 164), (64, 160), (55, 145), (58, 124), (66, 108), (62, 90),
              (56, 75)],
    "hl_b0": [(88, 38), (108, 38), (110, 62), (116, 62), (118, 38), (135, 38), (132, 70), (140, 100), (148, 130),
              (140, 150), (130, 152), (128, 186), (108, 188), (104, 152), (92, 148), (84, 128), (92, 100), (96, 70)],
}
SNOUT = {"hl_a0": (20, 64), "hl_b0": (14, 72)}           # mõm rồng = chỗ xé hư không
REVEAL_N = 16


def _geodesic(mask, seed):
    """Khoảng cách đi dọc trong vùng rồng (BFS 8 hướng) từ mõm -> thứ tự hiện của từng điểm trên thân."""
    from collections import deque
    h, w = mask.shape
    INF = 1e9
    dist = np.full((h, w), INF, np.float32)
    sx, sy = seed
    # điểm rồng gần mõm nhất làm gốc
    ys, xs = np.nonzero(mask)
    k = int(np.argmin((xs - sx) ** 2 + (ys - sy) ** 2))
    q = deque([(ys[k], xs[k])])
    dist[ys[k], xs[k]] = 0
    steps = [(-1, 0, 1), (1, 0, 1), (0, -1, 1), (0, 1, 1), (-1, -1, 1.414), (-1, 1, 1.414), (1, -1, 1.414), (1, 1, 1.414)]
    while q:
        y, x = q.popleft()
        d0 = dist[y, x]
        for dy, dx, c in steps:
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and dist[ny, nx] > d0 + c:
                dist[ny, nx] = d0 + c
                q.append((ny, nx))
    return dist


def dragon_reveal(base, meta):
    from PIL import ImageDraw as D_
    im = load(base)
    a = np.asarray(im).astype(np.float32)
    h, w = a.shape[:2]
    rgb, al = a[..., :3], a[..., 3] / 255.0
    poly = Image.new("L", (w, h), 0)
    D_.Draw(poly).polygon(CHAR_POLY[base], fill=255)
    poly = np.asarray(poly.filter(ImageFilter.GaussianBlur(1.2))).astype(np.float32) / 255.0
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    pink = ((r > g + 40) & (rgb.max(2) > 90)) | ((b > g + 25) & (r > g + 15))
    char = poly * (1 - 0.85 * pink)                              # vệt rồng đỏ hồng vắt ngang người vẫn để hiện dần
    dmask = (al > 0.04) & (char < 0.5)
    geo = _geodesic(dmask, SNOUT[base])
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    eu = np.hypot(xs - SNOUT[base][0], ys - SNOUT[base][1])
    fin = geo < 1e8
    D = float(geo[fin].max()) if fin.any() else float(eu.max())
    geo = np.where(fin, geo, eu * 1.15)                          # mảnh rời (tàn khí) hiện theo khoảng cách thẳng
    geo = np.minimum(geo, D * 1.02)
    soft = D * 0.08
    sx, sy = SNOUT[base]
    for k in range(REVEAL_N):
        t = k / float(REVEAL_N - 1)
        u_ = min(1.0, max(0.0, (t - 0.14) / 0.74))               # khe hư không mở trước, rồi đầu rồng chậm rãi chui ra
        R = (u_ ** 1.35) * (D * 1.12)
        vis = np.clip((R - geo) / soft, 0, 1)
        front = np.exp(-((R - geo) / (D * 0.05)) ** 2) * (1.0 if t < 0.92 else 0.0)
        A = np.maximum(char * al, vis * al)
        A = np.where(dmask, vis * al, A)
        col = rgb.copy()
        glow = (front * dmask)[..., None]
        col = col * (1 - 0.75 * glow) + np.array([255, 120, 205]) * 0.75 * glow     # mép đang hiện: loá hồng tím
        A = np.maximum(A, front * dmask * 0.9 * (al > 0.04))
        out = Image.fromarray(np.dstack([np.clip(col, 0, 255), np.clip(A * 255, 0, 255)]).astype(np.uint8), "RGBA")
        lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        dd = D_.Draw(lay)
        if k <= 10:                                               # khe hư không xé ra ở mõm rồng
            u = k / 10.0
            op = math.sin(min(1.0, u * 1.25) * math.pi) if u < 0.8 else max(0.0, 1 - (u - 0.8) / 0.2) * 0.5
            rx, ry = 6 + 10 * min(1.0, u * 2), 4 + 26 * min(1.0, u * 2)
            cx, cy = sx + 6, sy
            for kk, (col_, sc) in enumerate((((120, 20, 90), 1.5), ((40, 0, 40), 1.0), ((8, 0, 14), 0.7))):
                dd.ellipse((cx - rx * sc, cy - ry * sc, cx + rx * sc, cy + ry * sc), fill=col_ + (int(230 * op),))
            dd.ellipse((cx - rx * 1.5, cy - ry * 1.5, cx + rx * 1.5, cy + ry * 1.5), outline=(255, 120, 210, int(255 * op)),
                       width=2)
            for j in range(7):                                    # tia tím loé quanh khe
                aa = j * 0.9 + k * 0.5
                L1, L2 = ry * 1.2, ry * (1.8 + 0.4 * math.sin(k + j))
                dd.line((cx + math.cos(aa) * L1 * 0.6, cy + math.sin(aa) * L1, cx + math.cos(aa) * L2 * 0.6,
                         cy + math.sin(aa) * L2), fill=(255, 150, 230, int(200 * op)), width=1)
        glow_l = lay.filter(ImageFilter.GaussianBlur(2))
        fr = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        fr.alpha_composite(glow_l)
        fr.alpha_composite(lay)
        fr.alpha_composite(out)
        if k == REVEAL_N - 1:
            fr = im.copy()                                        # khung cuối = đúng ảnh gốc
        name = "x_%s_in%d" % (base.replace("0", "").replace("_", ""), k)
        fr.save(os.path.join(PACK, name + ".png"), optimize=True)
        meta[name] = None


# ── nối khung vẽ thêm vào conf/actions.xml (chạy lại nhiều lần vẫn đúng, không nhân đôi) ──
JUMP = "com.group_finity.mascot.action.Jump"
A_ANC = [(112, 222), (112, 217), (112, 212), (112, 217)]
B_ANC = [(95, 220), (95, 215), (95, 210), (95, 215)]


def _pose(img, anc, dur, right=True):
    r = ' ImageRight="/%sr.png"' % img if right else ""
    return '    <Pose Image="/%s.png"%s ImageAnchor="%d,%d" Velocity="0,0" Duration="%d"/>' % (img, r, anc[0], anc[1], dur)


def _action(name, poses, attrs='Type="Animate"'):
    return "\n".join(['  <Action Name="%s" %s>' % (name, attrs), "   <Animation>"] + poses + ["   </Animation>", "  </Action>"])


def _seq(name, refs):
    return "\n".join(['  <Action Name="%s" Type="Sequence" BorderType="Floor" Loop="false">' % name] +
                     ['   <ActionReference Name="%s"/>' % r for r in refs] + ["  </Action>"])


def gen_actions(extra=()):
    out = []
    for L, anc in (("a", A_ANC), ("b", B_ANC)):
        intro = [_pose("x_hl%s_in%d" % (L, k), anc[0], 2, right=False) for k in range(REVEAL_N)]
        loop = [_pose("hl_%s%d" % (L, k), anc[k], 3) for k in range(4)]
        out.append(_action("HL_RongHien" + L.upper(), intro + loop))
        out.append(_action("HL_Quanh" + L.upper(), loop * 3 + [_pose("hl_fade", (112, 199), 3)]))
    out.append(_action("HL_BayA", [_pose("hl_a%d" % k, A_ANC[k], 3) for k in range(4)],
                       'Type="Embedded" Class="%s" VelocityParam="20" TargetX="${mascot.environment.cursor.x}" '
                       'TargetY="${mascot.environment.cursor.y - 80}"' % JUMP))
    out += list(extra)
    return out


def patch_xml(extra=()):
    import re
    p = os.path.join(PACK, "conf", "actions.xml")
    s = open(p, encoding="utf-8").read()
    s = re.sub(r"\n  <!-- x:begin.*?<!-- x:end -->", "", s, flags=re.S)
    block = "\n  <!-- x:begin (tools/dung_ao_den.py – khung vẽ thêm) -->\n" + "\n".join(gen_actions(extra)) + "\n  <!-- x:end -->"
    s = s.replace("\n </ActionList>", block + "\n </ActionList>", 1)
    for name, refs in (("HacLong_NhayVut", ["HL_Chuan", "HL_NhayVut", "HL_RongHienB", "HL_QuanhB", "HL_Roi", "DapDat"]),
                       ("HacLong_BayTheoChuot", ["HL_Chuan", "HL_NhayVut", "HL_RongHienA", "HL_BayA", "HL_QuanhA", "HL_Roi",
                                                 "DapDat"])):
        s, n = re.subn(r'  <Action Name="%s" Type="Sequence".*?</Action>' % name, lambda m: _seq(name, refs), s, count=1,
                       flags=re.S)
        assert n == 1, name
    open(p, "w", encoding="utf-8").write(s)


# ── ĐỨNG NỘ (aura): bỏ 2 vòng cung đỏ, thay bằng sấm sét bao phủ toàn thân ──
AURA_ANC = {0: (111, 113), 1: (133, 136), 2: (155, 160), 3: (175, 172), 4: (156, 160), 5: (171, 169), 6: (159, 160),
            7: (172, 175), 8: (161, 160), 9: (144, 146)}
AURAFADE_ANC = {10: (160, 160), 11: (160, 160)}             # aurafade0, aurafade1 (neo gốc)
LOI_DO = ((255, 238, 244), (255, 48, 92), (120, 0, 34), (30, 0, 10))       # sét đỏ thẫm hợp áo khăn đỏ
XW, XH, XA = 300, 236, (150, 208)


def _app():
    import importlib.machinery
    import importlib.util
    import sys
    path = os.path.join(os.path.dirname(HERE), "ChibiNhacViec.pyw")
    argv = sys.argv
    sys.argv = [path]
    try:
        ld = importlib.machinery.SourceFileLoader("chibi_app_core", path)
        spec = importlib.util.spec_from_loader("chibi_app_core", ld)
        mod = importlib.util.module_from_spec(spec)
        ld.exec_module(mod)
    finally:
        sys.argv = argv
    return mod


def _xml_anchor(img):
    import re
    s = open(os.path.join(PACK, "conf", "actions.xml"), encoding="utf-8").read()
    m = re.search(r'Image="/%s\.png"[^>]*ImageAnchor="(\d+),(\d+)"' % re.escape(img), s)
    return (int(m.group(1)), int(m.group(2))) if m else None


def char_only(img, anc):
    """Giữ thân nhân vật, bỏ 2 vòng cung đỏ hai bên (ngoài khung thân, hoặc điểm đỏ hồng sát mép khung)."""
    im = load(img)
    a = np.asarray(im).astype(np.float32)
    h, w = a.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    ax, ay = anc
    rgb = a[..., :3]
    red = (rgb[..., 0] > rgb[..., 1] + 50) & (rgb[..., 0] > 110)
    inbox = (np.abs(xx - ax) <= 50) & (yy >= ay - 132) & (yy <= ay + 6)
    keep = inbox & ~(red & (np.abs(xx - ax) > 40))
    soft = np.clip((52 - np.abs(xx - ax)) / 4.0, 0, 1)
    a[..., 3] *= keep * soft
    return Image.fromarray(a.astype(np.uint8), "RGBA")


def aura_lightning():
    A = _app()
    rnd = __import__("random").Random(77)
    # khung sét cố định: vòm sét gấp khúc (đất -> vai -> đỉnh đầu), tia điện bò trên thân, sét chạy mặt đất
    bolts = []
    kw = dict(branches=3, depth=1, kink=(0.05, 0.13), seg=(0.07, 0.13), blen=(0.12, 0.26), spread=(30, 70))
    for sgn in (-1, 1):
        for g, sh, top, back in ((72, (58, 96), (18, 168), True), (56, (44, 118), (6, 160), False),
                                 (88, (70, 70), (34, 150), True)):
            p0 = (XA[0] + sgn * g, XA[1] - 2)
            p1 = (XA[0] + sgn * sh[0], XA[1] - sh[1])
            p2 = (XA[0] + sgn * top[0], XA[1] - top[1])
            w0 = rnd.uniform(1.7, 2.4)
            bolts.append((A.LoiBolt(p0, p1, w0, rnd, **kw).set_pal(LOI_DO), back))
            bolts.append((A.LoiBolt(p1, p2, w0 * 0.8, rnd, **kw).set_pal(LOI_DO), back))
    crawl = []                                                # điện bò quanh vai, tay, chân (trước người)
    for (x0, y0, x1, y1) in ((-30, 96, -48, 70), (30, 96, 50, 72), (-40, 66, -54, 40), (40, 66, 56, 44),
                             (-14, 34, -26, 6), (16, 34, 28, 6), (-8, 112, 10, 124)):
        crawl.append(A.LoiBolt((XA[0] + x0, XA[1] - y0), (XA[0] + x1, XA[1] - y1), 1.0, rnd, branches=1, depth=1,
                               kink=(0.1, 0.25)).set_pal(LOI_DO))
    ground = []
    for sgn in (-1, 1):
        for L in (80, 135):
            p0 = (XA[0] + sgn * 20, XA[1] - 1)
            ground.append(A.LoiBolt(p0, (XA[0] + sgn * L, XA[1] - rnd.uniform(0, 8)), 1.3, rnd, branches=2, depth=1,
                                    kink=(0.05, 0.12)).set_pal(LOI_DO))
    frames = []
    names = ["aura%d" % k for k in range(10)] + ["aurafade0", "aurafade1"]
    for k, img in enumerate(names):
        anc = AURA_ANC.get(k) or AURAFADE_ANC.get(k) or _xml_anchor(img)
        fade = 1.0 if k < 10 else (0.55, 0.22)[k - 10]
        ch = char_only(img, anc)
        jr = __import__("random").Random(k * 31 + 5)
        cvs = {}
        for lay in ("back", "front"):
            cv = A.VCanvas(XW, XH, ss=2)
            cvs[lay] = cv
        # quầng nộ khí đỏ đen sau lưng
        pul = 0.75 + 0.25 * math.sin(k * 1.3)
        cvs["back"].ell("aura", (XA[0], XA[1] - 70), 62 * pul, 86 * pul, LOI_DO[3] + (int(90 * fade),))
        cvs["back"].ell("glow", (XA[0], XA[1] - 70), 36, 60, LOI_DO[1] + (int(34 * fade * pul),))
        for j, (b, back) in enumerate(bolts):
            on = ((k + j * 3) % 5) != 0                      # mỗi sợi có nhịp chớp riêng
            pw = (1.0 if (k + j) % 3 == 0 else 0.72) * fade * (1.0 if on else 0.2)
            b.draw(cvs["back" if back else "front"], 1.0, 0.0, pw, 1.6, jr)
        for j, b in enumerate(crawl):
            if (k + j) % 3 != 1:
                b.draw(cvs["front"], 1.0, 0.0, 0.9 * fade, 1.2, jr)
        for j, b in enumerate(ground):
            if (k + j) % 2 == 0:
                b.draw(cvs["back"], 1.0, 0.0, 0.85 * fade, 1.0, jr)
        if k % 3 == 0 and fade > 0.5:                        # loé đỏ tại chân
            cvs["front"].ell("glow", (XA[0], XA[1] - 2), 26, 8, LOI_DO[1] + (200,))
            cvs["front"].ell("base", (XA[0], XA[1] - 2), 10, 3, LOI_DO[0] + (255,))
        out = Image.new("RGBA", (XW, XH), (0, 0, 0, 0))
        out.alpha_composite(cvs["back"].image())
        out.alpha_composite(ch, (XA[0] - anc[0], XA[1] - anc[1]))
        out.alpha_composite(cvs["front"].image())
        name = "x_" + img
        out.save(os.path.join(PACK, name + ".png"), optimize=True)
        frames.append(name)
    return names


def patch_aura_xml(names):
    import re
    p = os.path.join(PACK, "conf", "actions.xml")
    s = open(p, encoding="utf-8").read()
    for img in names:
        s = re.sub(r'Image="/%s\.png" ImageRight="/%sr\.png" ImageAnchor="\d+,\d+"' % (img, img),
                   'Image="/x_%s.png" ImageAnchor="%d,%d"' % (img, XA[0], XA[1]), s)
    open(p, "w", encoding="utf-8").write(s)


def main():
    meta = {}
    # ── bay ngang: tư thế lao (jumpup), xoay cho thân nằm ngang hơn ──
    bases = [load("jumpup0"), load("jumpup1")]
    for f in range(8):
        b = padded(bases[0], 60)
        b = b.rotate(18, Image.BICUBIC, expand=False)               # hạ đầu xuống: thân gần nằm ngang
        ref = body_ref(b)
        if f // 2 % 2:                                              # khung xen kẽ: thân thứ 2, căn trùng trọng tâm
            b2 = padded(bases[1], 60).rotate(18, Image.BICUBIC, expand=False)
            r2 = body_ref(b2)
            b = b2.transform(b2.size, Image.AFFINE, (1, 0, r2[0] - ref[0], 0, 1, r2[1] - ref[1]), Image.BICUBIC)
        b = flutter(b, f * math.pi / 4, 5.0, side=1)
        bob = 1.5 * math.sin(f * math.pi / 4)
        b = streaks(b, f)
        b, off = trim(b)
        save("x_bay%d" % f, b, (int(round(ref[0] - off[0])), int(round(ref[1] - off[1] - bob))), meta)
    for nm, ang in (("x_baylen", -16), ("x_bayxuong", 40)):
        for f in range(4):
            b = padded(bases[0], 70)
            b = b.rotate(18 + ang, Image.BICUBIC, expand=False)
            ref = body_ref(b)
            b = flutter(b, f * math.pi / 2, 5.0, side=1)
            b = streaks(b, f + 3, n=5)
            b, off = trim(b)
            save("%s%d" % (nm, f), b, (int(round(ref[0] - off[0])), int(round(ref[1] - off[1]))), meta)
    # ── cất cánh: khuỵu gối lấy đà -> bật lên ──
    cr = load("hl_crouch0")
    for f, (sx, sy) in enumerate(((1.06, 0.92), (1.1, 0.84))):
        b = cr.resize((int(cr.width * sx), int(cr.height * sy)), Image.LANCZOS)
        b = padded(b, 24)
        if f == 1:
            fx, fy = foot_anchor(b)
            for k in range(3):
                ring(b, fx + (k - 1) * 10, fy, 10 + k * 4, 3, 120 - k * 30)
        b, _ = trim(b)
        save("x_catcanh%d" % f, b, foot_anchor(b), meta)
    up = load("jumpup0")
    for f, (st, ral) in enumerate(((1.1, 200), (1.03, 110))):
        b = padded(up, 60).rotate(-28, Image.BICUBIC, expand=False)        # dựng người lên: vút thẳng
        b = b.resize((b.width, int(b.height * st)), Image.LANCZOS)
        b = flutter(b, f * 1.7, 4.0, side=1)
        fx, fy = foot_anchor(b)
        ring(b, fx, fy + 6 + f * 5, 18 + f * 10, 5 + f * 2, ral, 2)
        ring(b, fx, fy + 12 + f * 6, 26 + f * 12, 7 + f * 3, ral * 0.6, 1)
        b, _ = trim(b)
        ax, ay = foot_anchor(b)
        save("x_catcanh%d" % (f + 2), b, (ax, ay), meta)
    # ── quay người: thân xoay (ép bề ngang) ──
    st = load("stand0")
    for f, sx in enumerate((0.62, 0.26)):
        b = st.resize((max(4, int(st.width * sx)), st.height), Image.LANCZOS)
        b = padded(b, 4)
        b, _ = trim(b)
        save("x_quay%d" % f, b, foot_anchor(b), meta)
    for base in ("hl_a0", "hl_b0"):
        dragon_reveal(base, meta)
    patch_xml()
    patch_aura_xml(aura_lightning())
    meta = {k: v for k, v in meta.items() if v is not None}
    with open(os.path.join(PACK, "conf", "x_khung.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=0)
    print(len(meta), "khung ->", PACK)


if __name__ == "__main__":
    main()
