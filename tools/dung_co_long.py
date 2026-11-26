#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dựng nhân vật CỔ LONG từ bảng sprite của người dùng (tools/co_long_nguon.png).

1. Tách nền caro giả, bỏ nhãn chữ / vạch kẻ, cắt từng khung theo BOXES.
2. Dựng hoạt cảnh: mỗi khung gốc được giữ vài nhịp kèm chuyển động liên tục (nhấp nhô, uốn, co giãn, chao),
   hoà chuyển nhanh sang khung sau; phủ hiệu ứng vẽ bằng code (lôi điện bò trên thân, chớp loá, sóng xung kích,
   lửa / sét phát ra từ miệng, đất nứt, tim, chữ Z...).
3. Xuất bộ Shimeji-ee: NhanVat/CoLong/*.png + conf/actions.xml + behaviors.xml + chibi.json.

Cần: Python 3.9+, Pillow, numpy.
Chạy:  python tools/dung_co_long.py                 -> dựng lại toàn bộ
       python tools/dung_co_long.py --khung         -> xem các khung đã cắt (/tmp/co_long_khung.png)
       python tools/dung_co_long.py --xem roar,fire  -> xem nhanh vài hoạt cảnh (/tmp/co_long_xem.png)
"""
import json
import math
import os
import random
import sys
from collections import deque

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
SHEET = os.path.join(HERE, "co_long_nguon.png")

# ───────────────────────── 1. cắt khung ─────────────────────────
LABELS = [(8, 3, 188, 28), (793, 3, 1003, 28), (8, 150, 128, 175), (793, 150, 897, 175), (8, 293, 135, 313),
          (793, 290, 970, 313), (8, 432, 190, 452), (823, 446, 950, 465), (8, 593, 272, 614), (803, 593, 990, 614),
          (8, 742, 218, 763), (742, 752, 965, 774), (0, 880, 152, 907), (958, 885, 1120, 906)]
MIRROR = {"st6", "st7"}
PINK = {"emo5"}
VIGNETTE = {"ult1", "ult2", "ult3", "ult4", "roar4", "aura3", "aura5"}
# khung có nền vân sét vàng nhạt dày đặc -> lọc bớt điểm nhạt màu (chỉ giữ thân tối + vàng đậm)
PALE = {"bolt1": 0.0, "bolt2": 0.0, "bolt3": 0.0, "bolt4": 0.0, "aura1": 0.3, "aura2": 0.3, "aura3": 0.3, "aura4": 0.3,
        "aura5": 0.3, "ult1": 0.3, "ult2": 0.3, "ult3": 0.3, "ult4": 0.3, "coil3": 0.5, "coil4": 0.5, "coil5": 0.5,
        "dive2": 0.6, "dive5": 0.6, "dive6": 0.6, "hover5": 0.5, "st5": 0.5}             # khung quay mặt sang phải -> lật lại cho cùng hướng

BOXES = {
    "walk0": (2, 22, 108, 138), "walk1": (100, 22, 197, 138), "walk2": (197, 22, 322, 138), "walk3": (322, 22, 447, 138),
    "walk4": (447, 22, 572, 138), "walk5": (572, 22, 792, 138),
    "fly1": (797, 25, 1000, 148), "fly3": (1155, 30, 1298, 148), "fly4": (1300, 10, 1536, 148),
    "coil1": (2, 160, 142, 290), "coil2": (138, 158, 292, 290), "coil3": (290, 155, 418, 290), "coil4": (418, 158, 556, 290),
    "coil5": (556, 158, 795, 290),
    "bolt1": (2, 300, 205, 432), "bolt2": (195, 300, 365, 432), "bolt3": (360, 300, 545, 432), "bolt4": (545, 300, 795, 432),
    "dive1": (826, 300, 948, 440), "dive2": (948, 295, 1042, 440), "dive3": (1040, 300, 1180, 440), "dive4": (1180, 300, 1268, 440),
    "dive5": (1268, 290, 1420, 440), "dive6": (1420, 290, 1536, 440),
    "aura1": (2, 452, 135, 590), "aura2": (132, 448, 290, 590), "aura3": (288, 448, 470, 590), "aura4": (475, 445, 625, 590),
    "aura5": (625, 448, 795, 590),
    "hover1": (818, 460, 920, 590), "hover2": (920, 465, 1040, 590), "hover3": (1040, 455, 1192, 590),
    "hover4": (1192, 460, 1360, 590), "hover5": (1370, 455, 1520, 590),
    "emo1": (2, 612, 135, 745), "emo2": (135, 615, 275, 745), "emo3": (272, 612, 430, 745), "emo4": (425, 610, 585, 745),
    "emo5": (585, 612, 752, 745),
    "roar1": (828, 615, 955, 740), "roar2": (955, 612, 1115, 740), "roar3": (1110, 612, 1260, 740), "roar4": (1260, 612, 1536, 740),
    "mini1": (2, 770, 105, 880), "mini2": (105, 762, 205, 880), "mini3": (205, 762, 305, 880), "mini4": (305, 765, 430, 880),
    "mini5": (430, 765, 548, 880), "mini6": (548, 785, 600, 880), "mini7": (600, 765, 738, 880),
    "ult1": (742, 772, 960, 885), "ult2": (960, 762, 1165, 885), "ult3": (1165, 762, 1355, 885), "ult4": (1355, 762, 1536, 885),
    "st1": (2, 900, 105, 1022), "st5": (405, 900, 545, 1022), "st6": (545, 900, 718, 1022), "st7": (718, 900, 935, 1022),
    "fx_orb": (955, 905, 1048, 1018), "fx_vorb": (1048, 905, 1135, 1018), "fx_star": (1192, 905, 1245, 1018),
    "fx_swirl": (1245, 905, 1338, 1018), "fx_ring": (1338, 905, 1405, 1018), "fx_bolts": (1405, 905, 1536, 1018),
}
# chỉnh tay điểm chạm đất (neo) / miệng khi tự tính chưa chuẩn: tên -> (x, y) theo toạ độ khung đã cắt
ANCHOR_FIX = {}
MOUTH_FIX = {}

_SRC = None
_ALPHA = None


def _load_sheet():
    global _SRC, _ALPHA
    if _SRC is not None:
        return
    im = np.asarray(Image.open(SHEET).convert("RGB")).astype(np.float32)
    mx, mn = im.max(2), im.min(2)
    sat, lum = mx - mn, im.mean(2)
    bg = np.clip((lum - 175) / 30.0, 0, 1) * np.clip((30 - sat) / 14.0, 0, 1)   # sáng + xám trung tính = nền caro
    a = 1 - bg
    for x0, y0, x1, y1 in LABELS:
        a[y0:y1, x0:x1] = 0
    # vạch kẻ ngang mảnh giữa các hàng: điểm có hình mà trên/dưới 3px đều trống, chạy dài theo chiều ngang
    on = a > 0.3
    thin = on.copy()
    thin[3:-3] &= ~on[:-6] & ~on[6:]
    thin[:3] = False
    thin[-3:] = False
    run = np.zeros(thin.shape, np.int32)
    k = np.ones(14, np.int32)
    for y in np.nonzero(thin.any(1))[0]:
        run[y] = np.convolve(thin[y].astype(np.int32), k, "same")
    line = thin & (run >= 10)
    for dy in (-1, 0, 1):
        a[np.roll(line, dy, 0)] = 0
    _SRC, _ALPHA = im, a


def _components(mask):
    h, w = mask.shape
    lab = np.zeros((h, w), np.int32)
    n = 0
    ys, xs = np.nonzero(mask)
    for y, x in zip(ys, xs):
        if lab[y, x]:
            continue
        n += 1
        q = deque([(y, x)])
        lab[y, x] = n
        while q:
            cy, cx = q.popleft()
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                yy, xx = cy + dy, cx + dx
                if 0 <= yy < h and 0 <= xx < w and mask[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = n
                    q.append((yy, xx))
    return lab, n


def cut(name):
    _load_sheet()
    x0, y0, x1, y1 = BOXES[name]
    a = _ALPHA[y0:y1, x0:x1].copy()
    rgb = _SRC[y0:y1, x0:x1]
    m = a > 0.3
    grown = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))) > 0
    lab, n = _components(grown)
    tot = max(1, m.sum())
    sizes = sorted((((lab == k) & m).sum(), k) for k in range(1, n + 1))[::-1]
    keep = np.zeros_like(m)
    for i, (sz, k) in enumerate(sizes):
        comp = lab == k
        ys, xs = np.nonzero(comp)
        hgt = ys.max() - ys.min() + 1
        touches = xs.min() == 0 or xs.max() == comp.shape[1] - 1
        if hgt <= 5 and xs.max() - xs.min() > 15:
            continue                                         # vạch kẻ ngang của bảng
        if i == 0 or (sz > tot * 0.004 and (not touches or sz > tot * 0.25)):
            keep |= comp
    a = np.where(keep, a, 0)
    if name in PALE:
        lum = rgb.mean(2)
        sat = rgb.max(2) - rgb.min(2)
        pale = np.clip((lum - 165) / 45.0, 0, 1) * np.clip((150 - sat) / 70.0, 0, 1)
        a = a * (1 - pale * (1 - PALE[name]))
        # điểm lẻ còn sót: giữ khi xung quanh đủ dày
        dens = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.BoxBlur(2))) / 255.0
        a = np.where(dens < 0.25, a * dens * 2, a)
    # mờ dần sát 4 cạnh khung cắt (hình tràn tới mép -> không còn viền thẳng như hộp)
    hh, ww = a.shape
    fx_ = np.minimum(np.arange(ww), np.arange(ww)[::-1])
    fy_ = np.minimum(np.arange(hh), np.arange(hh)[::-1])
    ramp = np.clip(np.minimum.outer(fy_, fx_) / 12.0, 0, 1)
    a = a * (0.25 + 0.75 * ramp) * np.where(ramp < 1, ramp ** 0.5, 1)
    if name in PINK:                                         # bụi hồng rắc quanh (khung biểu cảm) -> bỏ
        r_, g_, b_ = rgb[..., 0], rgb[..., 1], rgb[..., 2]
        pink = np.clip((r_ - g_ - 50) / 40.0, 0, 1) * np.clip((b_ - g_ + 10) / 40.0, 0, 1) * np.clip((r_ - 150) / 50.0, 0, 1)
        a = a * (1 - pink)
        dens = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.BoxBlur(3))) / 255.0
        a = np.where(dens < 0.3, a * np.clip((dens - 0.1) / 0.2, 0, 1), a)
    if name in VIGNETTE:                                     # vân năng lượng tràn khung -> bo thành hình elip mềm
        yy, xx = np.mgrid[0:hh, 0:ww]
        d = ((xx - ww / 2.0) / (ww / 2.0)) ** 2 + ((yy - hh * 0.55) / (hh * 0.55)) ** 2
        a = a * np.clip((1.0 - d) / 0.35, 0, 1)
    a = np.where(a < 0.12, 0, a)
    im = Image.fromarray(np.dstack([rgb, a * 255]).astype(np.uint8), "RGBA")
    bb = im.getchannel("A").getbbox()
    im = im.crop(bb)
    if name in ERASE:
        d = ImageDraw.Draw(im)
        for fx0, fy0, fx1, fy1 in ERASE[name]:
            d.rectangle((fx0 * im.width, fy0 * im.height, fx1 * im.width, fy1 * im.height), fill=(0, 0, 0, 0))
        im = im.crop(im.getchannel("A").getbbox())
    if name in MIRROR:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
    return im


# Khung đi bộ 1–4 trong ảnh gốc bị khung kế bên che mất đuôi -> ghép đoạn đuôi của walk5 (đủ đuôi, có chùm lửa đầu đuôi)
# tên -> (điểm cụt x, y tâm đuôi, hệ số độ dày)
TAIL_GRAFT = {"walk1": (84, 67, 0.85), "walk2": (113, 76, 0.9), "walk3": (113, 66, 0.9), "walk4": (113, 81, 0.9),
              "walk0": "auto", "fly3": "auto", "emo1": "auto", "emo2": "auto", "emo5": "auto", "mini1": "auto"}
TAIL_SRC = ("walk5", 148, 81)                 # khung có đuôi, cột bắt đầu cắt đoạn đuôi, tâm đuôi tại cột đó
# xoá mảnh hình của khung bên cạnh lọt vào ô cắt: tên -> [(x0, y0, x1, y1) theo tỉ lệ khung]
ERASE = {"fly3": [(0.0, 0.62, 0.34, 1.0)]}


def _body(im):
    a = np.asarray(im).astype(np.float32)
    return (a[..., 3] > 40) & (a[..., :3].mean(2) < 150)


def auto_stump(im):
    """Mỏm cụt ở mép phải: (x, y tâm, độ dày)."""
    b = _body(im)
    h, w = b.shape
    best = None
    for x in range(w - 1, max(0, w - 6), -1):
        col = b[:, x]
        y, run = 0, []
        while y < h:
            if col[y]:
                y0 = y
                while y < h and col[y]:
                    y += 1
                run.append((y - y0, y0, y))
            y += 1
        run = [r for r in run if r[0] >= 5]
        if run:
            r = max(run)
            if best is None or r[0] > best[2]:
                best = (x, (r[1] + r[2]) / 2.0, r[0])
    return best


def graft_tail(im, stump_x, stump_y, k, thick=None):
    src = cut(TAIL_SRC[0])
    sx0, sy0 = TAIL_SRC[1], TAIL_SRC[2]
    if thick is not None:                                           # chọn đoạn đuôi có độ dày khớp mỏm cụt
        b = _body(src)
        best = None
        for x in range(124, 176, 2):
            ys = np.nonzero(b[:97, x])[0]
            if len(ys) >= 4:
                t = ys.max() - ys.min() + 1
                if best is None or abs(t * 0.95 - thick) < best[0]:
                    best = (abs(t * 0.95 - thick), x, (ys.max() + ys.min()) / 2.0, t)
        if best:
            _, sx0, sy0, t = best
            k = max(0.6, min(1.15, thick / float(t)))
    piece = src.crop((sx0 - 6, 0, src.width, 97))                   # bỏ phần chân / bụi đất phía dưới
    if k != 1.0:
        piece = piece.resize((max(1, int(piece.width * k)), max(1, int(piece.height * k))), Image.LANCZOS)
    a = np.asarray(piece.getchannel("A")).astype(np.float32)
    ramp = np.clip(np.arange(a.shape[1]) / 8.0, 0, 1)                # mép nối mờ dần, giấu đường ghép
    piece.putalpha(Image.fromarray((a * ramp[None, :]).astype(np.uint8)))
    ox = int(round(stump_x - 6 * k - 6 * k))
    oy = int(round(stump_y - sy0 * k))
    W = max(im.width, ox + piece.width)
    top = min(0, oy)
    H = max(im.height, oy + piece.height) - top
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.alpha_composite(piece, (ox, oy - top))                       # đuôi nằm sau thân
    out.alpha_composite(im, (0, -top))
    tip = (ox + (src.width - 12 - sx0 + 6) * k, oy - top + 40 * k)
    return out, -top, tip


def hot_points(k):
    """Điểm tập trung điện năng trên khung rồng (toạ độ khung): sừng, mắt, móng vuốt, đầu đuôi, khớp vảy.
    Mỗi điểm có 1–2 tia sét gốc cố định toả ra ngoài thân (không đổi hình giữa các frame)."""
    try:
        body, gx, gy = k._hot_src
    except Exception:
        return None
    ys, xs = np.nonzero(body)
    if len(xs) < 50:
        return None
    dy = 0
    if k.tail_tip is not None:
        dy = int(round(k.anchor[1] - (gy + 1)))                       # đuôi ghép có thể dời khung xuống
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    w, h = x1 - x0 + 1, y1 - y0 + 1
    pts = []
    head = xs < x0 + w * 0.42
    if head.any():                                                    # sừng: 2 đỉnh cao nhất vùng đầu
        hy, hx = ys[head], xs[head]
        o = np.argsort(hy)
        a = (float(hx[o[0]]), float(hy[o[0]]))
        pts.append(("horn", a))
        far = np.abs(hx[o] - a[0]) > max(6, w * 0.06)
        if far.any():
            b = o[np.argmax(far)]
            pts.append(("horn", (float(hx[b]), float(hy[b]))))
    mx, my = k.mouth                                                  # mắt: phía trên – sau miệng
    pts.append(("eye", (mx + w * 0.12, my - h * 0.12)))
    low = ys > y1 - max(4, h * 0.06)                                  # móng vuốt: chỗ chạm đất
    if low.any():
        lx = np.sort(xs[low])
        groups, cur = [], [lx[0]]
        for v in lx[1:]:
            if v - cur[-1] > 6:
                groups.append(cur)
                cur = [v]
            else:
                cur.append(v)
        groups.append(cur)
        for g in sorted(groups, key=len, reverse=True)[:3]:
            pts.append(("claw", (float(np.mean(g)), float(y1))))
    if k.tail_tip is not None:
        pts.append(("tail", (k.tail_tip[0], k.tail_tip[1] - dy)))
    else:
        rx = xs > x1 - max(3, w * 0.03)
        pts.append(("tail", (float(x1), float(ys[rx].mean()))))
    rnd = random.Random(sum(map(ord, k.name)) * 13)
    for _ in range(4):                                                # khớp vảy trên thân
        q = rnd.randrange(len(xs))
        pts.append(("joint", (float(xs[q]), float(ys[q]))))
    pts = [(kind, (p[0], p[1] + dy)) for kind, p in pts]
    cx, cy = float(xs.mean()), float(ys.mean()) + dy
    bolts = []
    for kind, p in pts:
        out = math.degrees(math.atan2(p[1] - cy, p[0] - cx))           # toả ra phía ngoài thân
        ln = {"horn": 26, "eye": 14, "claw": 16, "tail": 24, "joint": 13}[kind]
        lst = []
        for d in ((-18, 18) if kind in ("horn", "tail") else (rnd.uniform(-25, 25),)):
            e = (p[0] + math.cos(math.radians(out + d)) * ln, p[1] + math.sin(math.radians(out + d)) * ln)
            lst.append(LoiBolt(p, e, 1.0, rnd, branches=2 if ln > 15 else 1, depth=1))
        bolts.append(lst)
    wrap = []
    joints = [p for kind, p in pts if kind in ("joint", "tail", "horn")]
    for a, b in zip(joints, joints[1:]):
        if math.hypot(a[0] - b[0], a[1] - b[1]) < w * 0.7:
            wrap.append(LoiBolt(a, b, 1.0, rnd, branches=1, depth=1))
    return dict(pts=[p for _, p in pts], kinds=[kd for kd, _ in pts], bolts=bolts, wrap=wrap[:2])


class Key:
    """Một khung gốc đã cắt + điểm neo (chạm đất), miệng, các điểm trên thân để vẽ điện bò."""

    def __init__(self, name):
        self.name = name
        self.im = cut(name)
        arr = np.asarray(self.im).astype(np.float32)
        al = arr[..., 3] / 255.0
        lum = arr[..., :3].mean(2)
        body = (al > 0.6) & (lum < 150)
        h, w = al.shape
        rows = body.sum(1)
        ys = np.nonzero(rows >= 4)[0]
        gy = int(ys.max()) if len(ys) else h - 1
        xs = np.nonzero(body)[1]
        gx = float(xs.mean()) if len(xs) else w / 2.0
        self.anchor = ANCHOR_FIX.get(name, (gx, gy + 1))
        band = body[int(h * 0.22):int(h * 0.62)]
        cols = np.nonzero(band.any(0))[0]
        if len(cols):
            mx_ = int(cols.min())
            yy = np.nonzero(band[:, mx_:mx_ + 4].any(1))[0]
            my = int(h * 0.22 + (yy.mean() if len(yy) else 0))
            self.mouth = MOUTH_FIX.get(name, (mx_ + 4, my + 3))
        else:
            self.mouth = MOUTH_FIX.get(name, (0, h * 0.4))
        pys, pxs = np.nonzero(body)
        rnd = random.Random(len(name) * 97 + w)
        idx = [rnd.randrange(len(pys)) for _ in range(300)] if len(pys) else []
        self.pts = [(float(pxs[i]), float(pys[i])) for i in idx]
        self.center = (float(pxs.mean()), float(pys.mean())) if len(pys) else (w / 2.0, h / 2.0)
        self._flash = {}
        self._halo = None
        self.tail_tip = None
        self._hot_src = (body, gx, gy)
        if name in TAIL_GRAFT:
            g = TAIL_GRAFT[name]
            if g == "auto":
                st = auto_stump(self.im)
                if st:
                    self.im, dy, self.tail_tip = graft_tail(self.im, st[0] - 1, st[1], 1.0, thick=st[2])
                else:
                    dy = 0
            else:
                sx_, sy_, k_ = g
                self.im, dy, self.tail_tip = graft_tail(self.im, sx_, sy_, k_)
            if dy:
                self.anchor = (self.anchor[0], self.anchor[1] + dy)
                self.mouth = (self.mouth[0], self.mouth[1] + dy)
                self.center = (self.center[0], self.center[1] + dy)
                self.pts = [(x, y + dy) for x, y in self.pts]
        self.hot = hot_points(self)

    def flash(self, k):
        k = round(k * 4) / 4.0
        if k not in self._flash:
            r, g, b, a = self.im.split()
            base = Image.merge("RGB", (r, g, b))
            hot = base.point(lambda v: min(255, int(v * 1.6 + 80)))          # chớp loá trắng tím (bảng màu hệ Lôi)
            hot = Image.blend(hot, Image.new("RGB", self.im.size, (226, 200, 255)), 0.45)
            rgb = Image.blend(base, hot, k)
            self._flash[k] = Image.merge("RGBA", (*rgb.split(), a))
        return self._flash[k]


KEYS = {}


def key(name):
    if name not in KEYS:
        if name == "fx_fire":
            KEYS[name] = flame_key()
        elif name.startswith("hu_"):
            KEYS[name] = file_key(name)
        else:
            KEYS[name] = Key(name)
    return KEYS[name]


TIP_KEYS = ("hu_loi_truc",)


def file_key(name):
    """Ảnh hiệu ứng của người dùng trong HieuUng/ (chạy tools/cat_hieu_ung.py trước). Neo = giữa đáy."""
    im = Image.open(os.path.join(os.path.dirname(HERE), "HieuUng", name[3:] + ".png")).convert("RGBA")
    k = Key.__new__(Key)
    k.name, k.im = name, im
    k.anchor = (im.width / 2.0, im.height * 0.96)
    if name in TIP_KEYS:                                     # tia sét giáng: neo = mũi nhọn thấp nhất (điểm chạm đất)
        A = np.asarray(im.getchannel("A"))
        ys, xs = np.nonzero(A > 120)
        y0 = ys.max()
        low = ys >= y0 - 6
        k.anchor = (float(xs[low].mean()), float(y0))
    k.center = (im.width / 2.0, im.height / 2.0)
    k.mouth = k.center
    k.pts = []
    k._flash = {}
    return k


FLAME_POLY = [(862, 214), (905, 200), (960, 214), (1040, 232), (1137, 252), (1137, 287), (1060, 287), (950, 262), (862, 240)]


def flame_key():
    """Lưỡi lửa gốc trong ảnh (hàng 4): tách theo độ 'nóng' của màu, lật cho lửa phun sang trái."""
    _load_sheet()
    x0, y0, x1, y1 = 860, 196, 1140, 289
    rgb = _SRC[y0:y1, x0:x1]
    warm = np.clip((rgb[..., 0] - rgb[..., 2] - 25) / 45.0, 0, 1)
    bright = np.clip((rgb.mean(2) - 120) / 60.0, 0, 1)
    a = np.maximum(warm, _ALPHA[y0:y1, x0:x1] * bright * warm)
    m = Image.new("L", (x1 - x0, y1 - y0), 0)
    ImageDraw.Draw(m).polygon([(x - x0, y - y0) for x, y in FLAME_POLY], fill=255)
    a = a * (np.asarray(m.filter(ImageFilter.GaussianBlur(2))) / 255.0)
    # lõi trắng nóng lẫn với nền caro -> đóng kín vùng lửa rồi tô lõi vàng trắng
    warm_m = Image.fromarray(((a > 0.35) * 255).astype(np.uint8))
    closed = np.asarray(warm_m.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.MinFilter(9))) > 0
    pale = rgb.mean(2) > 175
    hole = closed & (a < 0.6) & pale
    rgb = rgb.copy()
    lumv = rgb.mean(2)
    core = np.stack([np.full_like(lumv, 255), 205 + (lumv - 175) * 0.6, 90 + (lumv - 175) * 1.6], -1)
    rgb[hole] = np.clip(core[hole], 0, 255)
    a = np.where(hole, 0.97, a)
    im = Image.fromarray(np.dstack([rgb, a * 255]).astype(np.uint8), "RGBA").transpose(Image.FLIP_LEFT_RIGHT)
    im = im.crop(im.getchannel("A").getbbox())
    k = Key.__new__(Key)
    k.name, k.im = "fx_fire", im
    arr = np.asarray(im.getchannel("A")) > 100
    ys, xs = np.nonzero(arr)
    right = xs > im.width - 12                               # đầu lửa = cụm điểm sát mép phải
    k.anchor = (im.width - 2.0, float(ys[right].mean()) if right.any() else im.height * 0.5)
    k.axis = math.degrees(math.atan2(ys.mean() - k.anchor[1], xs.mean() - k.anchor[0]))
    k.center = k.anchor
    k.mouth = k.anchor
    k.pts = []
    k._flash = {}
    return k


# ───────────────────────── 2. khung vẽ ─────────────────────────
SS = 2
SCALE = 1.3                                   # phóng khung gốc
X0, Y0, CW, CH = -480, -400, 780, 470         # toạ độ: neo nhân vật = (0, 0), mặt đất y = 0


class Frame:
    def __init__(self):
        size = (CW * SS, CH * SS)
        self.L = {k: Image.new("RGBA", size, (0, 0, 0, 0)) for k in ("bgg", "bg", "halo", "spr", "fgg", "fg")}
        self.D = {k: ImageDraw.Draw(v) for k, v in self.L.items()}
        self.placed = []

    @staticmethod
    def c(p):
        return ((p[0] - X0) * SS, (p[1] - Y0) * SS)

    def line(self, pts, col, w=1.0, layer="fg"):
        self.D[layer].line([self.c(p) for p in pts], fill=col, width=max(1, int(w * SS)), joint="curve")

    def poly(self, pts, col, layer="fg"):
        self.D[layer].polygon([self.c(p) for p in pts], fill=col)

    def ell(self, c, rx, ry, fill=None, layer="fg", outline=None, w=1.0):
        x, y = self.c(c)
        self.D[layer].ellipse((x - rx * SS, y - ry * SS, x + rx * SS, y + ry * SS), fill=fill, outline=outline,
                              width=max(1, int(w * SS)) if outline else 0)

    # đặt một khung gốc: neo của khung tới điểm pos, co giãn / xoay quanh tâm thân
    def sprite(self, name, pos=(0.0, 0.0), sx=1.0, sy=1.0, rot=0.0, alpha=1.0, flash=0.0, glow=0.0,
               glow_col=(120, 55, 230), layer="spr", pivot="center", scale=1.0):
        k = key(name)
        im = k.flash(flash) if flash > 0.01 else k.im
        s = SCALE * SS * scale
        ax, ay = k.anchor
        pv = k.center if pivot == "center" else (k.anchor if pivot == "anchor" else pivot)
        tx, ty = self.c(pos)
        Tp = (tx + (pv[0] - ax) * s * sx, ty + (pv[1] - ay) * s * sy)
        th = math.radians(rot)
        co, si = math.cos(th), math.sin(th)

        def fwd(p):
            x, y = (p[0] - pv[0]) * s * sx, (p[1] - pv[1]) * s * sy
            return (Tp[0] + co * x - si * y, Tp[1] + si * x + co * y)
        corners = [fwd(p) for p in ((0, 0), (im.width, 0), (0, im.height), (im.width, im.height))]
        ox0, oy0 = int(min(p[0] for p in corners)) - 2, int(min(p[1] for p in corners)) - 2
        ox1, oy1 = int(max(p[0] for p in corners)) + 3, int(max(p[1] for p in corners)) + 3
        w, h = ox1 - ox0, oy1 - oy0
        # ánh xạ ngược: điểm ra (X, Y) -> điểm khung gốc
        m00, m01 = co / (s * sx), si / (s * sx)
        m10, m11 = -si / (s * sy), co / (s * sy)
        cx0, cy0 = Tp[0] - ox0, Tp[1] - oy0
        coef = (m00, m01, pv[0] - m00 * cx0 - m01 * cy0, m10, m11, pv[1] - m10 * cx0 - m11 * cy0)
        out = im.transform((w, h), Image.AFFINE, coef, resample=Image.BICUBIC)
        if alpha < 0.999:
            out.putalpha(out.getchannel("A").point(lambda v: int(v * alpha)))
        if glow > 0.01:
            pad = 8 * SS
            A_ = Image.new("L", (w + 2 * pad, h + 2 * pad), 0)
            A_.paste(out.getchannel("A"), (pad, pad))
            g = A_.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(4 * SS))
            g = g.point(lambda v: min(255, int(v * 1.5 * glow)))
            gi = Image.new("RGBA", g.size, glow_col + (255,))
            gi.putalpha(g)
            self._paste("halo", gi, ox0 - pad, oy0 - pad)
        self._paste(layer, out, ox0, oy0)
        info = dict(fwd=lambda p: ((fwd(p)[0] / SS) + X0, (fwd(p)[1] / SS) + Y0), key=k)
        info["mouth"] = info["fwd"](k.mouth)
        info["center"] = info["fwd"](k.center)
        self.placed.append(info)
        return info

    def _paste(self, layer, im, x, y):
        tgt = self.L[layer]
        if x < 0 or y < 0 or x + im.width > tgt.width or y + im.height > tgt.height:
            bx0, by0 = max(0, -x), max(0, -y)
            bx1, by1 = min(im.width, tgt.width - x), min(im.height, tgt.height - y)
            if bx1 <= bx0 or by1 <= by0:
                return
            im = im.crop((bx0, by0, bx1, by1))
            x, y = x + bx0, y + by0
        tgt.alpha_composite(im, (x, y))

    def fxsprite(self, name, pos, scale=1.0, rot=0.0, alpha=1.0, layer="fg", flash=0.0):
        k = key(name)
        old = k.anchor
        k.anchor = k.center
        self.sprite(name, pos, scale=scale, rot=rot, alpha=alpha, layer=layer, flash=flash)
        k.anchor = old
        self.placed.pop()

    def finish(self):
        out = Image.new("RGBA", self.L["bg"].size, (0, 0, 0, 0))
        for k, r in (("bgg", 3.0), ("bg", 0), ("halo", 0), ("spr", 0), ("fgg", 3.0), ("fg", 0)):
            lay = self.L[k]
            if r:
                b = lay.getbbox()
                if not b:
                    continue
                m = int(r * SS * 3)
                b = (max(0, b[0] - m), max(0, b[1] - m), min(lay.width, b[2] + m), min(lay.height, b[3] + m))
                out.alpha_composite(lay.crop(b).filter(ImageFilter.GaussianBlur(r * SS)), b[:2])
            else:
                out.alpha_composite(lay)
        return out.resize((CW, CH), Image.LANCZOS)


# ───────────────────────── 3. hiệu ứng ─────────────────────────
# ── HỆ LÔI THÁI CỔ HẮC LONG: dùng CHUNG lõi sấm sét với hiệu ứng bàn phím trong ChibiNhacViec.pyw ──
def _load_app():
    import importlib.machinery
    import importlib.util
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


APP = _load_app()
LoiBolt, loi_stroke, taper_poly = APP.LoiBolt, APP.loi_stroke, APP.taper_poly
LOI_CORE, LOI_MID, LOI_MID_B, LOI_EDGE, LOI_DARK, LOI_AURA = (APP.LOI_CORE, APP.LOI_MID, APP.LOI_MID_B, APP.LOI_EDGE,
                                                              APP.LOI_DARK, APP.LOI_AURA)
GOLD_G, GOLD_M = LOI_MID, LOI_CORE            # tên cũ: mọi tia sét giờ cùng bảng màu tím cố định
VIO_G, VIO_M = LOI_MID, LOI_CORE
HALO = (120, 55, 230)                          # quầng năng lượng quanh rồng (tím)


class Em:
    """Bộ vẽ cho lõi Lôi: đổ nét vào các lớp của khung rồng (quầng -> sau lưng, sáng / thân tia -> trước hoặc sau)."""

    def __init__(self, F, back=False):
        self.F, self.back = F, back

    def _lay(self, layer):
        if layer == "aura":
            return "bgg"
        if layer == "glow":
            return "bgg" if self.back else "fgg"
        return "bg" if self.back else "fg"

    def line(self, layer, pts, col, w):
        if len(pts) >= 2 and col[3] > 0:
            self.F.line(pts, col, w, layer=self._lay(layer))

    def poly(self, layer, pts, col):
        if len(pts) >= 3 and col[3] > 0:
            self.F.poly(pts, col, layer=self._lay(layer))

    def ell(self, layer, c, rx, ry, col):
        if col[3] > 0:
            self.F.ell(c, rx, ry, fill=col, layer=self._lay(layer))

    def ell_ring(self, layer, c, rx, ry, col, w):
        if col[3] > 0:
            self.F.ell(c, rx, ry, outline=col, w=w, layer=self._lay(layer))


def lerp(a, b, t):
    return a + (b - a) * t


def clamp01(t):
    return max(0.0, min(1.0, t))


def ss(t):
    t = clamp01(t)
    return t * t * (3 - 2 * t)


def dirv(a):
    r = math.radians(a)
    return (math.cos(r), math.sin(r))


def add(p, q, k=1.0):
    return (p[0] + q[0] * k, p[1] + q[1] * k)


_BOLTS = {}


def stable_bolt(p0, p1, w, branches=3, depth=2, tag=""):
    """Tia sét có thiết kế gốc cố định: cùng vị trí (làm tròn) -> cùng hình dáng ở mọi frame, chỉ đổi trạng thái."""
    q = (tag, round(p0[0] / 10), round(p0[1] / 10), round(p1[0] / 10), round(p1[1] / 10), round(w, 1), branches)
    b = _BOLTS.get(q)
    if b is None:
        L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        b = LoiBolt(p0, p1, w * 1.1, random.Random(hash(q) & 0xFFFFFF), branches=branches if L > 25 else 1,
                    depth=depth if L > 40 else 1)
        _BOLTS[q] = b
        if len(_BOLTS) > 4000:
            _BOLTS.clear()
    return b


def zap(F, pts, w=1.2, al=1.0, g=None, m=None, back=False):
    """Đường sét có sẵn toạ độ: vẽ bằng nét sét chuẩn (thuôn nhọn, quầng đen tím, lõi trắng tím)."""
    n = len(pts)
    if n < 2:
        return
    ws = [w * (1 - 0.5 * k / float(n - 1)) for k in range(n)]
    ws[-1] = 0
    loi_stroke(Em(F, back), pts, ws, clamp01(al))


def bolt(F, p0, p1, rnd=None, w=1.6, al=1.0, g=None, m=None, branches=3, back=False, seg=None, depth=0, grow=1.0, tail=0.0,
         tag=""):
    b = stable_bolt(p0, p1, w, branches, 2 if depth == 0 else 1, tag)
    jr = random.Random(int(al * 1000) + int(p0[0] * 7))
    b.draw(Em(F, back), grow, tail, clamp01(al), 0.6, jr)
    return b.pts


def body_arcs(F, info, rnd, n=2, al=1.0, g=None, m=None, ln=(8, 18)):
    """Điện bò quanh thân: tập trung ở sừng, mắt, móng vuốt, đầu đuôi, khớp vảy; mỗi điểm có nhịp riêng
    (bùng – giữ – co rút – tắt), nhánh đổi độ dài theo frame nhưng hình dáng gốc cố định."""
    k = info["key"]
    hot = getattr(k, "hot", None)
    if not hot:
        return
    i = getattr(F, "frame_no", 0)
    em = Em(F)
    off = hot.get("off", (0, 0))
    fw = info["fwd"]
    xf = (lambda p: fw((p[0] + off[0], p[1] + off[1]))) if off != (0, 0) else fw
    budget = max(1, int(n * 2))
    pts = hot["pts"]
    order = sorted(range(len(pts)), key=lambda j: ((i + j * 5) % 9))       # điểm nào đang tới nhịp thì sáng trước
    for j in order[:budget]:
        ph = (i + j * 5) % 9
        if ph > 4:
            continue
        grow = (0.45, 1.0, 1.0, 0.85, 0.6)[ph]
        tail = (0.0, 0.0, 0.15, 0.45, 0.75)[ph]
        pw = (0.8, 1.0, 0.6, 0.85, 0.4)[ph] * al
        for tb in hot["bolts"][j]:
            tb.draw(em, grow, tail, pw, 0.5, random.Random(i * 31 + j), xf=xf, wk=SCALE * 1.7)
    if n >= 3:                                                   # tia quấn ngang thân nối 2 điểm điện (mảnh, không che dáng)
        for wb in hot["wrap"]:
            ph = (i + int(wb.L)) % 7
            if ph < 3:
                wb.draw(em, (0.5, 1.0, 1.0)[ph], (0.0, 0.0, 0.4)[ph], 0.6 * al, 0.4, random.Random(i), xf=xf,
                        wk=SCALE * 1.0)


def flash_burst(F, c, r, al, col=None):
    APP.loi_flash(Em(F), c, r * 0.8, clamp01(al))


def ring(F, c, rx, ry, al, col=None, w=1.4):
    APP.loi_ring(Em(F), c, rx, ry, clamp01(al), w)


def sound_ring(F, c, ang, r, al):
    pts = [add(c, dirv(ang - 60 + 120 * k / 16.0), r) for k in range(17)]
    F.line(pts, LOI_MID + (int(180 * al),), 3.6, layer="fgg")
    F.line(pts, LOI_EDGE + (int(200 * al),), 1.8)
    F.line(pts, LOI_CORE + (int(240 * al),), 0.8)


def dust(F, c, r, al, back=False):
    al = clamp01(al)
    F.ell(c, r * 1.25, r * 0.6, fill=(160, 148, 130, int(150 * al)), layer="bgg" if back else "fgg")
    F.ell(c, r * 0.8, r * 0.4, fill=(185, 172, 155, int(120 * al)), layer="bg" if back else "fg")


def speed_lines(F, rnd, y0, y1, x0, x1, n=7, col=(205, 170, 255)):
    for _ in range(n):
        y = rnd.uniform(y0, y1)
        a = rnd.uniform(x0, x1)
        L = rnd.uniform(20, 50)
        F.line([(a, y), (a + L, y)], col + (int(rnd.uniform(90, 200)),), rnd.uniform(0.6, 1.4), layer="bg")


def crack(F, x0, dirn, ln, rnd, al):
    pts = [(x0, -0.5)]
    x = x0
    while abs(x - x0) < ln:
        x += dirn * rnd.uniform(5, 10)
        pts.append((x, -0.5 + rnd.uniform(-2.5, 1.0)))
    F.line(pts, (160, 80, 255, int(230 * al)), 5, layer="bgg")
    F.line(pts, (30, 16, 6, int(255 * al)), 2.0, layer="bg")
    F.line(pts, (240, 225, 255, int(255 * al)), 0.8, layer="bg")


def rock(F, c, sz, ang, al=1.0):
    pts = [add(c, dirv(ang + k * 72 + (k % 2) * 18), sz * (0.75 + 0.15 * (k % 3))) for k in range(5)]
    F.poly(pts, (70, 58, 50, int(255 * al)))
    F.line(pts + [pts[0]], (170, 100, 255, int(200 * al)), 0.5)


def fire_blob(F, c, r, al, hot):
    F.ell(c, r * 1.7, r * 1.7, fill=(255, 110, 20, int(130 * al)), layer="fgg")


def fire_stream(F, M, ang, Lc, i, al=1.0, col="fire"):
    """Dòng lửa phun từ miệng: nhiều lưỡi lửa bập bùng, mép rách, lõi trắng nóng gần miệng, tàn lửa + khói."""
    dv = dirv(ang)
    nv = (-dv[1], dv[0])
    r = random.Random(i * 13 + 5)
    pal = dict(fire=((255, 80, 0), (235, 60, 10), (255, 150, 20), (255, 225, 90), (255, 252, 225)),
               violet=((140, 50, 255), (120, 40, 230), (170, 100, 255), (215, 185, 255), (250, 245, 255)))[col]
    tongues = []
    n = 46
    for k in range(n):
        s_ = (k / float(n)) ** 0.9 * Lc
        spread = 3 + s_ * 0.16
        off = r.gauss(0, 0.45) * spread + math.sin(k * 0.9 - i * 1.7) * spread * 0.35
        c = add(add(M, dv, s_ + 3), nv, off)
        rr = (2.2 + s_ * 0.085) * r.uniform(0.75, 1.3)
        lick = (rr * r.uniform(1.6, 2.8))
        tongues.append((c, rr, lick, s_))
    for c, rr, lick, s_ in tongues:                          # quầng
        F.ell(c, rr * 2.0, rr * 1.8, fill=pal[0] + (int(95 * al),), layer="fgg")

    def tongue(c, rr, lick, color, k):
        tip = add(add(c, dv, lick * 0.5), (0, -1), lick * 0.7)          # lưỡi lửa uốn lên + theo hướng phun
        base = [add(c, dirv(a), rr * k) for a in range(0, 360, 40)]
        F.poly(base, color)
        F.poly([add(c, nv, rr * k * 0.9), tip, add(c, nv, -rr * k * 0.9)], color)
    for c, rr, lick, s_ in tongues:
        tongue(c, rr, lick, pal[1] + (int(235 * al),), 1.0)
    for c, rr, lick, s_ in tongues:
        tongue(c, rr, lick * 0.8, pal[2] + (int(240 * al),), 0.75)
    for c, rr, lick, s_ in tongues:
        if s_ < Lc * 0.8:
            tongue(c, rr, lick * 0.6, pal[3] + (int(245 * al),), 0.5)
    for c, rr, lick, s_ in tongues:
        if s_ < Lc * 0.45:
            F.ell(c, rr * 0.35, rr * 0.3, fill=pal[4] + (int(255 * al),))
    for k in range(14):                                      # tàn lửa bay
        s_ = r.uniform(0.2, 1.0) * Lc
        c = add(add(M, dv, s_), nv, r.uniform(-1, 1) * (8 + s_ * 0.25))
        c = add(c, (0, -r.uniform(0, 10)))
        F.ell(c, 1.0, 1.0, fill=(255, 240, 170, int(255 * al)))
    for k in range(5):                                       # khói ở đầu ngọn
        s_ = Lc * r.uniform(0.8, 1.05)
        c = add(add(M, dv, s_), (0, -6 - r.uniform(0, 12)), 1)
        F.ell(c, 6 + s_ * 0.04, 5 + s_ * 0.03, fill=(70, 50, 40, int(90 * al)), layer="fgg")


def letter_z(F, c, s, al):
    pts = [(c[0] - s, c[1] - s), (c[0] + s, c[1] - s), (c[0] - s, c[1] + s), (c[0] + s, c[1] + s)]
    F.line(pts, (255, 200, 80, int(150 * al)), s * 0.9, layer="fgg")
    F.line(pts, (255, 248, 220, int(255 * al)), max(0.6, s * 0.3))


def heart(F, c, s, al):
    pts = []
    for k in range(24):
        t = k / 24.0 * 2 * math.pi
        x = 16 * math.sin(t) ** 3
        y = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
        pts.append((c[0] + x * s / 16.0, c[1] + y * s / 16.0))
    F.poly(pts, (255, 110, 170, int(220 * al)), layer="fgg")
    F.poly(pts, (255, 120, 180, int(255 * al)))
    F.ell(add(c, (-s * 0.35, -s * 0.3)), s * 0.18, s * 0.14, fill=(255, 230, 240, int(255 * al)))


def droplet(F, c, r, al):
    F.poly([add(c, (0, -r * 1.6)), add(c, (r, 0)), add(c, (0, r)), add(c, (-r, 0))], (150, 215, 255, int(240 * al)))


def sparkle(F, c, r, al, col=(255, 240, 170)):
    pts = [add(c, dirv(k * 45 - 90), r if k % 2 == 0 else r * 0.3) for k in range(8)]
    F.poly(pts, col + (int(255 * al),))
    F.ell(c, r * 0.9, r * 0.9, fill=col + (int(120 * al),), layer="fgg")


# ───────────────────────── 3b. chân bước, thân trườn: biến dạng lưới khung gốc ─────────────────────────
# Vị trí bàn chân trong khung (toạ độ khung đã cắt): (x, y chạm đất, chiều cao chân, bề ngang vùng chân)
FEET = {"walk3": [(11, 101, 26, 10), (52, 108, 26, 11), (100, 110, 28, 12), (126, 107, 26, 10)],
        "st6": [(30, 103, 18, 10), (70, 106, 18, 10), (112, 106, 18, 10)]}
_WARP = {}


def mesh_warp(im, disp, step=5):
    """Biến dạng ảnh theo trường dịch chuyển disp(x, y) -> (dx, dy): điểm ra p hiển thị điểm vào p - d."""
    w, h = im.size
    pad = 14
    W, H = w + 2 * pad, h + 2 * pad
    src = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    src.paste(im, (pad, pad))
    mesh = []
    for y in range(0, H, step):
        for x in range(0, W, step):
            x1, y1 = min(x + step, W), min(y + step, H)
            q = []
            for (px, py) in ((x, y), (x, y1), (x1, y1), (x1, y)):
                dx, dy = disp(px - pad, py - pad)
                q += [px - dx, py - dy]
            mesh.append(((x, y, x1, y1), q))
    out = src.transform((W, H), Image.MESH, mesh, Image.BICUBIC)
    return out, pad


def gait_offset(u, stance, stride, lift):
    """Một bàn chân theo pha u (0..1): đạp lùi khi chạm đất, nhấc – đưa tới – đặt xuống khi bước."""
    u %= 1.0
    if u < stance:
        return (stride * (u / stance - 0.5), 0.0)                    # rồng hướng trái: chân chạm đất trôi về sau (+x)
    s_ = (u - stance) / (1 - stance)
    return (stride * (0.5 - ss(s_)), -lift * math.sin(math.pi * s_))


def gait_key(base, i, T, stride=7.0, lift=4.5, stance=0.62, wave=1.8, wl=70.0, phases=(0.0, 0.5, 0.25, 0.75),
             lean=0.0):
    """Khung gốc base biến dạng ở nhịp i/T: từng chân bước theo pha riêng (nhịp chéo), thân & đuôi uốn sóng trườn,
    đầu nhấp nhô ngược pha. Trả về Key ảo (giữ neo / miệng / điểm điện của khung gốc)."""
    ck = (base, i, T, stride, lift, stance, wave, wl, lean)
    if ck in _WARP:
        return _WARP[ck]
    k = key(base)
    feet = FEET.get(base, [])
    t = i / float(T)
    offs = [gait_offset(t + phases[n % len(phases)], stance, stride, lift) for n in range(len(feet))]
    w, h = k.im.size
    ph = 2 * math.pi * t

    def disp(x, y):
        dx = dy = 0.0
        legw = 0.0
        for (fx, fy, lh, lw), (ox, oy) in zip(feet, offs):
            wx = math.exp(-((x - fx) / float(lw)) ** 2)
            wy = ss((y - (fy - lh)) / float(lh))
            wgt = wx * wy
            if wgt > 0.001:
                dx += ox * wgt
                dy += oy * wgt
                legw = max(legw, wgt)
        body = 1.0 - legw
        u = max(0.0, min(1.0, x / float(w)))
        dy += wave * math.sin(2 * math.pi * x / wl - ph * 2) * (0.25 + 0.75 * u) * body      # sóng trườn dọc thân, mạnh về đuôi
        dx += lean * (1 - y / float(h)) * body
        dy += -0.9 * math.sin(ph * 2 + 1.2) * (1 - u) * (1 - y / float(h)) * body            # đầu nhấp nhô
        return dx, dy
    out, pad = mesh_warp(k.im, disp)
    v = Key.__new__(Key)
    v.name = "%s~%d" % (base, i)
    v.im = out
    v.anchor = (k.anchor[0] + pad, k.anchor[1] + pad)
    v.mouth = (k.mouth[0] + pad, k.mouth[1] + pad)
    v.center = (k.center[0] + pad, k.center[1] + pad)
    v.pts = [(x + pad, y + pad) for x, y in k.pts]
    v.tail_tip = None
    v._flash = {}
    v._halo = None
    v.hot = None
    if k.hot:
        v.hot = dict(k.hot)
        v.hot["pts"] = [(x + pad, y + pad) for x, y in k.hot["pts"]]
        v.hot["off"] = (pad, pad)
    KEYS[v.name] = v                                             # để Frame.sprite / body_arcs dùng như khung thường
    _WARP[ck] = v
    return v


# ───────────────────────── 4. hoạt cảnh ─────────────────────────
TAU = 2 * math.pi
SETS = {}


def defset(name, d=1, anchor=(0.0, 0.0), step=1):
    """step = 2: động tác chậm chỉ dựng 1/2 số khung (mỗi khung giữ 2 nhịp) cho nhẹ."""
    def deco(fn):
        SETS[name] = dict(fn=(lambda: fn()[::step]) if step > 1 else fn, d=d * step, anchor=anchor)
        return fn
    return deco


def tl(segs, blend=2, loop=False):
    """Dòng thời gian khung gốc: [(tên, số nhịp)] -> mỗi nhịp (khung A, khung B, mức hoà sang B)."""
    out = []
    n = len(segs)
    for si, (k, h) in enumerate(segs):
        nxt = segs[(si + 1) % n][0] if (loop or si < n - 1) else None
        for j in range(h):
            mix = 0.0
            if nxt and nxt != k and j >= h - blend:
                mix = (j - (h - blend) + 1) / float(blend + 1)
            out.append((k, nxt, mix))
    return out


def seg_index(segs, i):
    t = 0
    for si, (k, h) in enumerate(segs):
        if i < t + h:
            return si, i - t
        t += h
    return len(segs) - 1, i - t


def pair(F, a, b, mix, **tr):
    ia = F.sprite(a, alpha=1 - max(0.0, mix - 0.5) * 2, **tr)
    if b and mix > 0:
        ib = F.sprite(b, alpha=min(1.0, mix * 2), **tr)
        return ib if mix >= 0.5 else ia
    return ia


def build(T, fn):
    def run(F, i):
        F.frame_no = i
        return fn(F, i)
    return [(lambda F, i=i: run(F, i)) for i in range(T)]


def kfv(i, keys):
    if i <= keys[0][0]:
        return keys[0][1]
    for (f0, v0), (f1, v1) in zip(keys, keys[1:]):
        if i <= f1:
            return lerp(v0, v1, ss((i - f0) / float(max(1e-6, f1 - f0))))
    return keys[-1][1]


def shake(i, amp):
    r = random.Random(i * 7919 + 3)
    return (r.uniform(-amp, amp), r.uniform(-amp, amp))


# ── cơ bản ──
@defset("stand", d=2)
def S_stand():
    T = 30

    def f(F, i):
        w = TAU * i / T
        info = F.sprite("walk3", (0, 0), sx=1 - 0.008 * math.sin(w), sy=1 + 0.016 * math.sin(w), rot=0.7 * math.sin(w + 1),
                        pivot="anchor", glow=0.18 + 0.08 * math.sin(w), glow_col=(120, 55, 230))
        if i % 10 in (3, 4):
            body_arcs(F, info, random.Random(i), 1, 0.9)
    return build(T, f)


@defset("standb", d=2)
def S_standb():
    segs = [("walk3", 10), ("walk0", 14), ("walk3", 12)]
    T = 36
    seq = tl(segs, 2)

    def f(F, i):
        w = TAU * i / T
        a, b, m = seq[i]
        info = pair(F, a, b, m, sy=1 + 0.014 * math.sin(w), rot=1.6 * math.sin(w), pivot="anchor", glow=0.2, glow_col=(120, 55, 230))
        if 12 <= i <= 20:
            body_arcs(F, info, random.Random(i * 3), 2, 1.0 - (i - 12) / 9.0)
    return build(T, f)


WALK = [("walk2", 6), ("walk3", 6), ("walk4", 6), ("walk3", 6)]
WALK_T = 24
WALK_V = 1.2                                   # tốc độ đi (px / nhịp) – bước chân khớp tốc độ, không trượt


def walk_key(i, T=WALK_T, run=False):
    if run:
        return gait_key("walk3", i % T, T, stride=WALK_V * 3.6 * 0.42 * T / SCALE, lift=7.0, stance=0.42, wave=2.6, wl=60.0,
                        phases=(0.0, 0.1, 0.5, 0.6), lean=-2.0)
    return gait_key("walk3", i % T, T, stride=WALK_V * 0.62 * T / SCALE, lift=6.5, stance=0.62, wave=2.2)


@defset("walk")
def S_walk():
    T = WALK_T

    def f(F, i):
        k = walk_key(i)
        ph = TAU * i / 12.0
        info = F.sprite(k.name, (0, -0.8 * abs(math.sin(ph / 2))), rot=0.8 * math.sin(TAU * i / T), pivot="anchor", glow=0.15)
        if i % 12 == 2:
            dust(F, (28, -2), 4, 0.45, back=True)
        if i in (5, 17):
            body_arcs(F, info, random.Random(i), 1, 0.8)
    return build(T, f)


@defset("run")
def S_run():
    T = 12

    def f(F, i):
        k = walk_key(i, T, run=True)
        ph = TAU * i / 6.0
        info = F.sprite(k.name, (0, -3 * abs(math.sin(ph / 2))), sx=1.04, sy=0.98, rot=-3 + 1.5 * math.sin(ph), pivot="anchor",
                        glow=0.25)
        r = random.Random(i)
        for k2 in range(2):
            a_ = (i + k2 * 3) % 6
            dust(F, (30 + a_ * 7, -2 - a_), 3 + a_ * 1.4, 0.75 - a_ * 0.12, back=True)
        if i % 3 == 0:
            body_arcs(F, info, r, 1, 0.9)
    return build(T, f)


@defset("crawl")
def S_crawl():
    """Bò trườn: thân hạ sát đất, sóng trườn lớn chạy từ đầu tới đuôi, chân bơi theo nhịp chéo."""
    T = 32

    def f(F, i):
        k = gait_key("st6", i, T, stride=0.9 * 0.6 * T / SCALE, lift=3.0, stance=0.6, wave=3.2, wl=55.0,
                     phases=(0.0, 0.5, 0.25))
        info = F.sprite(k.name, (0, 0), rot=0.6 * math.sin(TAU * i / T), pivot="anchor", glow=0.15)
        if i % 8 == 0:
            dust(F, (40, -2), 4, 0.4, back=True)
        if i in (7, 23):
            body_arcs(F, info, random.Random(i), 1, 0.7)
    return build(T, f)


def trail(F, info, i, col="gold", n=6, ln=110):
    r = random.Random(i * 5)
    c = info["center"]
    g, m = (GOLD_G, GOLD_M) if col == "gold" else (VIO_G, VIO_M)
    for k in range(2):
        y = c[1] + r.uniform(-14, 14)
        bolt(F, (c[0] + 20, y), (c[0] + ln + r.uniform(0, 40), y + r.uniform(-12, 12)), r, 1.1, 0.85, g, m, 1, back=True)
    speed_lines(F, r, c[1] - 40, c[1] + 30, c[0] + 10, c[0] + 140, n)


@defset("dash")
def S_dash():
    T = 8

    def f(F, i):
        w = TAU * i / T
        info = F.sprite("fly1", (0, -4 + 1.5 * math.sin(w)), sx=1.08, sy=0.96, rot=-2 + 1.5 * math.sin(w), pivot="anchor", glow=0.45)
        trail(F, info, i)
        for k in range(3):
            a_ = (i + k * 3) % 8
            dust(F, (30 + a_ * 10, -2 - a_ * 0.8), 3 + a_, 0.7 - a_ * 0.08, back=True)
    return build(T, f)


FLY = [("fly1", 6), ("fly4", 6), ("fly3", 6)]


@defset("fly")
def S_fly():
    T = 18
    seq = tl(FLY, 2, loop=True)

    def f(F, i):
        a, b, m = seq[i]
        w = TAU * i / T
        info = pair(F, a, b, m, pos=(0, -6 + 4 * math.sin(w)), rot=3 * math.sin(w + 0.8), sy=1 + 0.02 * math.sin(2 * w), glow=0.3)
        if i % 6 == 2:
            body_arcs(F, info, random.Random(i), 2, 0.9)
    return build(T, f)


@defset("flydash")
def S_flydash():
    T = 6

    def f(F, i):
        k = "fly1" if i < 3 else "fly4"
        info = F.sprite(k, (0, -6), sx=1.14, sy=0.94, rot=-4, glow=0.7, flash=0.15 if i % 3 == 0 else 0)
        trail(F, info, i, n=10, ln=150)
    return build(T, f)


@defset("fall")
def S_fall():
    T = 8

    def f(F, i):
        w = TAU * i / T
        F.sprite("fly3", (0, -6), sx=1 + 0.04 * math.sin(2 * w), sy=1 - 0.04 * math.sin(2 * w), rot=10 * math.sin(w), glow=0.2)
    return build(T, f)


@defset("spin")
def S_spin():
    T = 12

    def f(F, i):
        F.sprite("coil1", (0, -10), rot=-(i - 1) * 30, alpha=0.35)
        info = F.sprite("coil1", (0, -10), rot=-i * 30, glow=0.3)
        if i % 4 == 0:
            body_arcs(F, info, random.Random(i), 2, 0.9)
    return build(T, f)


def _drag_pos():
    k = key("hover1")
    top = (k.center[0], 0.0)
    return top


HANG = -220.0                                 # điểm treo (con trỏ / trần) đặt cao trong khung vẽ để hình thõng xuống không bị cắt


@defset("drag", anchor=(0.0, HANG))
def S_drag():
    T = 24

    def f(F, i):
        k = key("hover1")
        w = TAU * i / T
        top = (k.center[0], 4.0)
        pos = (-(top[0] - k.anchor[0]) * SCALE, HANG + (k.anchor[1] - top[1]) * SCALE)
        info = F.sprite("hover1", pos, rot=8 * math.sin(w), sx=1 + 0.03 * math.sin(2 * w), sy=1 - 0.03 * math.sin(2 * w),
                        pivot=top, glow=0.2)
        if i % 8 == 4:
            body_arcs(F, info, random.Random(i), 1, 0.8)
    return build(T, f)


@defset("land")
def S_land():
    T = 8

    def f(F, i):
        sy = kfv(i, [(0, 0.82), (3, 1.06), (7, 1.0)])
        sx = kfv(i, [(0, 1.12), (3, 0.97), (7, 1.0)])
        F.sprite("walk3", (0, 0), sx=sx, sy=sy, pivot="anchor", glow=0.2)
        if i < 7:
            for x in (-40, 40):
                dust(F, (x * (0.6 + i * 0.1), -2), 4 + i * 1.6, 1 - i / 7.0)
    return build(T, f)


@defset("wallg", d=2)
def S_wallg():
    T = 16

    def f(F, i):
        w = TAU * i / T
        F.sprite("walk3", (0, 0), rot=90, sy=1 + 0.015 * math.sin(w), pivot="anchor", glow=0.15)
    return build(T, f)


@defset("wallc")
def S_wallc():
    T = 24

    def f(F, i):
        F.sprite(walk_key(i).name, (0.8 * abs(math.sin(TAU * i / 24)), 0), rot=90, pivot="anchor", glow=0.15)
    return build(T, f)


@defset("ceilg", d=2, anchor=(0.0, HANG))
def S_ceilg():
    T = 16

    def f(F, i):
        w = TAU * i / T
        F.sprite("walk3", (0, HANG), sy=-(1 + 0.015 * math.sin(w)), pivot="anchor", glow=0.15)
    return build(T, f)


@defset("ceilc", anchor=(0.0, HANG))
def S_ceilc():
    T = 24
    seq = tl(WALK, 2, loop=True)

    def f(F, i):
        F.sprite(walk_key(i).name, (0, HANG + 0.8 * abs(math.sin(TAU * i / 24))), sy=-1, pivot="anchor", glow=0.15)
    return build(T, f)


# ── nghỉ ──
@defset("lie")
def S_lie():
    T = 12
    seq = tl([("walk3", 6), ("st6", 6)], 4)

    def f(F, i):
        a, b, m = seq[i]
        pair(F, a, b, m, sy=kfv(i, [(0, 1), (5, 0.9), (11, 1)]), pivot="anchor", glow=0.15)
        if 5 <= i <= 11:
            dust(F, (-10 + (i - 5) * 3, -2), 5 + (i - 5), 0.6 - (i - 5) * 0.08)
    return build(T, f)


@defset("rest", d=2)
def S_rest():
    T = 32

    def f(F, i):
        w = TAU * i / T
        info = F.sprite("st6", (0, 0), sy=1 + 0.02 * math.sin(w), sx=1 - 0.006 * math.sin(w), pivot="anchor",
                        glow=0.12 + 0.06 * math.sin(w))
        if i in (9, 25):
            body_arcs(F, info, random.Random(i), 1, 0.7)
    return build(T, f)


@defset("sleep", d=2)
def S_sleep():
    T = 40

    def f(F, i):
        w = TAU * i / T
        info = F.sprite("st7", (0, 0), sy=1 + 0.025 * math.sin(w), sx=1 - 0.008 * math.sin(w), pivot="anchor", glow=0.1)
        head = info["fwd"]((key("st7").im.width * 0.2, key("st7").im.height * 0.15))
        for k in range(3):
            a = ((i + k * 13) % T) / float(T)
            letter_z(F, add(head, (-12 * a - 4 * math.sin(a * 9), -36 * a - 6)), 2 + 3.4 * a, math.sin(math.pi * a))
    return build(T, f)


# ── chiêu ──
@defset("coil")
def S_coil():
    segs = [("coil1", 7), ("coil2", 7), ("coil3", 7), ("coil4", 7), ("coil5", 10)]
    T = 38
    seq = tl(segs, 2)

    def f(F, i):
        a, b, m = seq[i]
        k = i / float(T)
        fl = 0.55 if i in (14, 21, 28) else (0.25 if i in (15, 22, 29) else 0)
        info = pair(F, a, b, m, sy=1 + 0.02 * math.sin(i * 0.9), rot=1.5 * math.sin(i * 0.6), pivot="anchor",
                    glow=0.25 + 0.6 * k, flash=fl)
        r = random.Random(i)
        if i == 20:
            HIT["coil"] = info["center"]                          # icon nằm giữa vòng cuộn (bị ôm siết)
        body_arcs(F, info, r, 1 + int(3 * k), 1.0)
        if i >= 30:
            a_ = (i - 30) / 8.0
            ring(F, info["center"], 30 + 70 * a_, 14 + 30 * a_, 1 - a_)
            if i < 33:
                flash_burst(F, info["center"], 26, 1 - (i - 30) / 3.0)
    return build(T, f)


def jitter_(i, k):
    return random.Random(i * 131 + k * 17).random()


@defset("fire")
def S_fire():
    segs = [("roar1", 9), ("roar3", 28), ("roar2", 7), ("walk3", 6)]
    T = 50
    seq = tl(segs, 2)

    def f(F, i):
        a, b, m = seq[i]
        sx_, sy_ = shake(i, 1.2) if 10 <= i <= 36 else (0, 0)
        info = pair(F, a, b, m, pos=(sx_ + kfv(i, [(0, 0), (9, 4), (12, 0)]), sy_), rot=kfv(i, [(0, 0), (8, -6), (11, 3), (36, 3), (44, 0)]),
                    pivot="anchor", glow=kfv(i, [(0, 0.2), (9, 0.7), (37, 0.7), (50, 0.2)]), glow_col=(255, 120, 30),
                    flash=0.4 if i == 10 else 0)
        M = info["mouth"]
        r = random.Random(i)
        if i < 9:                                             # hít lửa: tàn lửa dồn vào miệng
            for _ in range(8):
                p = add(M, dirv(r.uniform(140, 220)), r.uniform(10, 60) * (1 - i / 9.0) + 5)
                F.ell(p, 1.2, 1.2, fill=(255, 200, 80, 240))
        grow = min(1.0, (i - 9) / 5.0) * (1 if i < 37 else (40 - i) / 3.0)
        if 10 <= i <= 40 and grow > 0.05:
            Lc = grow * 250
            ang = 176 + 4 * math.sin(i * 0.35)
            dv = dirv(ang)
            for k in range(8):                               # quầng nóng + tàn lửa quanh dòng lửa
                c = add(M, dv, Lc * (k + 0.5) / 8.0)
                F.ell(c, 9 + k * 2.2, 7 + k * 1.6, fill=(255, 150, 40, 75), layer="fgg")
            for k in range(12):
                c = add(add(M, dv, Lc * jitter_(i, k)), (0, -14 * jitter_(i + 50, k)), 1)
                F.ell(c, 1.0, 1.0, fill=(255, 240, 170, 255))
            fk = key("fx_fire")
            jit = random.Random(i * 7)
            F.sprite("fx_fire", M, sx=Lc / fk.im.width * (1 + jit.uniform(-0.07, 0.07)) / SCALE,
                     sy=(1.2 + 0.45 * grow + jit.uniform(-0.15, 0.15)) / SCALE,
                     rot=ang - fk.axis + jit.uniform(-2.5, 2.5), pivot="anchor", layer="fg")
            F.placed.pop()
            if i % 4 == 0:
                body_arcs(F, info, r, 2, 0.9)
        if i == 10:
            flash_burst(F, M, 22, 1.0)
        if i == 20:
            HIT["fire"] = add(M, dirv(176), 165)                  # icon bị đốt ở giữa dòng lửa
    return build(T, f)


_rb = random.Random(4242)
BREATH = {
    "beam": [LoiBolt((0, 0), (-250, 0), 2.8, _rb, branches=4, depth=2),
             LoiBolt((0, -2), (-245, -16), 1.4, _rb, branches=2, depth=1),
             LoiBolt((0, 2), (-245, 16), 1.4, _rb, branches=2, depth=1)],
    "splash": [LoiBolt((0, 0), add((0, 0), dirv(a), _rb.uniform(16, 30)), 1.0, _rb, branches=1, depth=1)
               for a in (120, 160, 200, 235, 270)],
    "gather": [LoiBolt(add((0, 0), dirv(a), 45), add((0, 0), dirv(a), 12), 0.8, _rb, branches=1, depth=1)
               for a in (140, 170, 200, 230, 115, 250)],
}


@defset("boltb")
def S_boltb():
    segs = [("roar1", 7), ("roar2", 9), ("roar3", 12), ("roar2", 6), ("roar3", 8), ("walk3", 6)]
    T = 48
    seq = tl(segs, 2)

    def f(F, i):
        a, b, m = seq[i]
        vio = i >= 18
        sx_, sy_ = shake(i, 1.3) if 4 <= i <= 40 else (0, 0)
        fl = 0.6 if i in (4, 18, 29) else (0.3 if i in (5, 19, 30) else 0)
        info = pair(F, a, b, m, pos=(sx_, sy_), pivot="anchor", glow=0.6, glow_col=HALO, flash=fl)
        M = info["mouth"]
        r = random.Random(i * 3)
        em = Em(F)
        if i < 4:                                             # tụ điện: tia nhỏ hội tụ vào miệng
            for j, tb in enumerate(BREATH["gather"]):
                tb.draw(em, 1.0, i / 4.0, 0.8, 0.4, r, xf=lambda p: (M[0] + p[0] * (1 - i / 5.0), M[1] + p[1] * (1 - i / 5.0)))
        if 4 <= i <= 42:                                     # tia sét phun từ miệng: 3 sợi gốc cố định, vươn dài theo frame
            grow = min(1.0, (i - 3) / 3.0)
            tail = 0.0 if i < 40 else (i - 39) / 4.0
            ang = 3 * math.sin(i * 0.5)
            co, si = math.cos(math.radians(ang)), math.sin(math.radians(ang))
            xf = lambda p: (M[0] - 2 + p[0] * co - p[1] * si, M[1] + p[0] * si + p[1] * co)
            pw = (1.0, 0.75, 1.0, 0.55, 0.9, 0.7)[i % 6]
            for tb in BREATH["beam"]:
                tb.draw(em, grow, tail, pw, 1.2, r, xf=xf)
            end = xf((-250 * grow, 0))
            F.ell(M, 9, 9, fill=LOI_MID + (200,), layer="fgg")
            if grow >= 1 and tail <= 0:
                for k2, tb in enumerate(BREATH["splash"]):     # toé điện ở đầu tia, mỗi nhánh có nhịp riêng
                    if (i + k2) % 3:
                        tb.draw(em, 1.0, 0.0, 0.9, 0.6, r, xf=lambda p: (end[0] + p[0], end[1] + p[1]))
        if i in (4, 18, 29):
            flash_burst(F, M, 26, 1.0)
        if i == 20:
            HIT["zap"] = (M[0] - 175, M[1])                        # icon trúng tia sét gần đầu tia
        body_arcs(F, info, r, 2, 0.9)
    return build(T, f)


@defset("takeoff")
def S_takeoff():
    T = 10
    seq = tl([("walk3", 5), ("fly1", 5)], 3)

    def f(F, i):
        a, b, m = seq[i]
        pair(F, a, b, m, pos=(0, kfv(i, [(0, 0), (4, 2), (9, -14)])), sy=kfv(i, [(0, 1), (4, 0.88), (8, 1.05)]), pivot="anchor", glow=0.4)
        if i >= 4:
            a_ = i - 4
            for x in (-35, 0, 35):
                dust(F, (x * (1 + a_ * 0.15), -2), 4 + a_ * 1.6, 1 - a_ / 6.0)
    return build(T, f)


@defset("dive")
def S_dive():
    T = 6

    def f(F, i):
        info = F.sprite("dive2", (0, 0), sx=0.95 + 0.05 * (i % 2), sy=1.05, pivot="anchor", glow=0.8, flash=0.2 if i % 3 == 0 else 0)
        r = random.Random(i)
        c = info["center"]
        for k in range(3):
            x = c[0] + r.uniform(-18, 18)
            bolt(F, (x, c[1] - 30), (x + r.uniform(-10, 10), c[1] - 150), r, 1.0, 0.8, GOLD_G, GOLD_M, 1, back=True)
        for _ in range(6):
            x = c[0] + r.uniform(-40, 40)
            y = c[1] - r.uniform(40, 170)
            F.line([(x, y), (x, y - r.uniform(20, 40))], (205, 170, 255, 170), 0.8, layer="bg")
    return build(T, f)


@defset("impact")
def S_impact():
    segs = [("dive5", 5), ("dive6", 5), ("dive3", 7), ("dive4", 6), ("dive1", 7), ("walk3", 6)]
    T = 36
    seq = tl(segs, 2)
    rnd0 = random.Random(21)
    rocks = [(rnd0.uniform(-6, 6), rnd0.uniform(-9, -5), rnd0.uniform(2, 4), rnd0.uniform(0, 360)) for _ in range(14)]

    def f(F, i):
        a, b, m = seq[i]
        sx_, sy_ = shake(i, 3 * (1 - i / 14.0)) if i < 14 else (0, 0)
        # nổ tung một vùng (ảnh nổ của người dùng): nổ mặt đất vàng phía sau, nổ vàng tím bung ra, loé tròn
        grow = 1 - (1 - min(1.0, (i + 1) / 5.0)) ** 2
        fade = 1.0 if i < 12 else max(0.0, 1 - (i - 12) / 10.0)
        if fade > 0:
            dz = 420.0 / key("hu_no_dat").im.width / SCALE
            F.sprite("hu_no_dat", (0, 4), sx=dz * (0.5 + 0.55 * grow), sy=dz * (0.3 + 0.75 * grow), alpha=fade, pivot="anchor",
                     layer="bg", flash=0.5 if i < 2 else 0)
            F.placed.pop()
        if 1 <= i <= 14:
            k2 = (i - 1) / 13.0
            dz = 340.0 / key("hu_no_vang_tim").im.width / SCALE
            F.sprite("hu_no_vang_tim", (0, 2), sx=dz * (0.6 + 0.5 * k2), sy=dz * (0.6 + 0.5 * k2), alpha=1 - k2 ** 1.5,
                     pivot="anchor", layer="fg")
            F.placed.pop()
        if i < 7:
            dz = 300.0 / key("hu_no_vang").im.width / SCALE
            F.sprite("hu_no_vang", (0, -40), sx=dz * (0.4 + 0.15 * i), sy=dz * (0.4 + 0.15 * i), rot=i * 6, alpha=1 - i / 7.0,
                     pivot="center", layer="fg", flash=0.4 if i < 2 else 0)
            F.placed.pop()
        info = pair(F, a, b, m, pos=(sx_, sy_), pivot="anchor", glow=kfv(i, [(0, 1.0), (20, 0.4), (36, 0.2)]),
                    flash=kfv(i, [(0, 0.8), (3, 0.0)]))
        r = random.Random(8)
        k = 1 - max(0, i - 24) / 12.0
        F.ell((0, 0), 66, 9, fill=(26, 14, 6, int(220 * k)), layer="bg")
        F.ell((0, 0), 66, 9, outline=(170, 90, 255, int(200 * k)), w=1.2, layer="bg")
        for dirn in (-1, 1):
            for n in range(3):
                crack(F, dirn * 50, dirn, min(1.0, i / 4.0) * (30 + n * 28), r, k)
        if i < 5:
            flash_burst(F, (0, -30), 50 - i * 4, 1 - i / 5.0)
        if i < 14:
            al = 1 - i / 14.0
            ring(F, (0, -2), 30 + i * 13, 4 + i * 2.2, al)
        for vx, vy, sz, r0 in rocks:
            x, y = vx * i * 1.6, vy * i + 0.5 * i * i
            if y < 0 and i < 20:
                rock(F, (x, y), sz, r0 + i * 30)
        for n in range(6):
            dust(F, ((n - 2.5) * 22 + (n - 2.5) * i * 1.3, -4 - i * 0.6), 6 + i * 0.8, 0.85 * (1 - i / 30.0))
        if 6 <= i <= 22 and i % 3 == 0:
            body_arcs(F, info, random.Random(i), 3, 1.0)
    return build(T, f)


@defset("aura")
def S_aura():
    segs = [("aura1", 6), ("aura2", 6), ("aura3", 6), ("aura4", 6), ("aura5", 6), ("aura3", 6), ("walk3", 6)]
    T = 42
    seq = tl(segs, 2)

    def f(F, i):
        a, b, m = seq[i]
        fl = 0.45 if i % 6 == 3 and i < 36 else 0
        info = pair(F, a, b, m, rot=2.5 * math.sin(i * 0.5), sy=1 + 0.02 * math.sin(i * 0.9), pivot="anchor",
                    glow=0.4 + 0.4 * math.sin(math.pi * min(1, i / 36.0)), flash=fl)
        r = random.Random(i * 7)
        if i < 36:
            body_arcs(F, info, r, 3, 1.0, ln=(12, 26))
            c = info["center"]
            for _ in range(2):                               # tia điện vươn ra quanh thân
                a_ = r.uniform(0, 360)
                bolt(F, add(c, dirv(a_), 40), add(c, dirv(a_ + r.uniform(-30, 30)), 75), r, 1.0, 0.9, branches=1)
        if 34 <= i <= 38:
            a_ = (i - 34) / 4.0
            ring(F, info["center"], 40 + 60 * a_, 26 + 34 * a_, 1 - a_)
    return build(T, f)


@defset("hover")
def S_hover():
    segs = [("hover1", 7), ("hover2", 7), ("hover3", 9), ("hover4", 9), ("hover5", 12), ("hover4", 6), ("hover1", 6)]
    T = 56
    seq = tl(segs, 3)

    def f(F, i):
        a, b, m = seq[i]
        lift = kfv(i, [(0, 0), (12, -16), (44, -16), (56, 0)]) + 2.5 * math.sin(TAU * i / 18)
        info = pair(F, a, b, m, pos=(0, lift), rot=2 * math.sin(TAU * i / 28), pivot="anchor",
                    glow=0.5, glow_col=(120, 55, 230), flash=0.35 if i in (23, 41) else 0)
        r = random.Random(i)
        k = math.sin(math.pi * i / T)
        for n in range(3):                                   # xoáy tím dưới chân
            ph = ((i * 0.06 + n / 3.0) % 1.0)
            F.ell((0, -2), 18 + 50 * ph, 4 + 9 * ph, outline=(190, 140, 255, int(230 * k * (1 - ph))), w=1.2, layer="fg")
            F.ell((0, -2), 18 + 50 * ph, 4 + 9 * ph, outline=(140, 70, 255, int(180 * k * (1 - ph))), w=4, layer="fgg")
        if i % 4 == 0:
            body_arcs(F, info, r, 2, 0.9, VIO_G, VIO_M) if i > 20 else body_arcs(F, info, r, 2, 0.9)
    return build(T, f)


@defset("roar")
def S_roar():
    segs = [("roar1", 8), ("roar2", 8), ("roar3", 14), ("roar4", 14), ("walk3", 6)]
    T = 50
    seq = tl(segs, 2)

    def f(F, i):
        a, b, m = seq[i]
        sh = shake(i, 1.6) if 16 <= i <= 44 else (0, 0)
        info = pair(F, a, b, m, pos=sh, pivot="anchor", glow=kfv(i, [(0, 0.2), (16, 0.8), (44, 0.8), (50, 0.2)]),
                    flash=0.55 if i in (16, 30) else (0.25 if i in (17, 31) else 0))
        M = info["mouth"]
        if 16 <= i <= 44:
            for t0 in range(16, 44, 3):
                a_ = i - t0
                if 0 <= a_ < 9:
                    sound_ring(F, M, 180, 8 + a_ * 12, 1 - a_ / 9.0)
        r = random.Random(i * 11)
        if 30 <= i <= 44:                                    # sét bổ xuống quanh mình khi thét lớn
            if i % 3 == 0:
                x = r.choice((-1, 1)) * r.uniform(60, 150)
                bolt(F, (x + r.uniform(-20, 20), -230), (x, -1), r, 1.8, 1.0, branches=3, back=True)
                F.ell((x, -1), 20, 5, fill=(200, 160, 255, 220), layer="bgg")
            body_arcs(F, info, r, 3, 1.0)
        if i in (16, 30):
            flash_burst(F, M, 24, 1.0)
    return build(T, f)


@defset("mini")
def S_mini():
    segs = [("walk3", 5), ("mini1", 9), ("mini4", 9), ("mini5", 9), ("mini2", 12), ("mini3", 12), ("mini7", 10), ("walk3", 6)]
    T = 72
    seq = tl(segs, 2)

    def f(F, i):
        a, b, m = seq[i]
        mini = 5 <= i < 66
        sc = 0.7 if mini else 1.0
        hop = -9 * abs(math.sin(TAU * i / 18)) if mini and i < 32 else 0
        tr = dict(pos=(0, hop), pivot="anchor", glow=0.25, flash=0.8 if i in (5, 66) else (0.4 if i in (6, 67) else 0),
                  sy=1 + 0.03 * math.sin(i * 0.7))
        ia = F.sprite(a, scale=sc if a != "walk3" else 1.0, alpha=1 - max(0.0, m - 0.5) * 2, **tr)
        if b and m > 0:
            F.sprite(b, scale=0.7 if b != "walk3" else 1.0, alpha=min(1.0, m * 2), **tr)
        if i in (4, 5, 6, 65, 66, 67):                       # biến hình: chớp + khói
            k = 1 - abs(i - (5 if i < 30 else 66)) / 2.0
            flash_burst(F, (0, -45), 40, k)
            for n in range(6):
                dust(F, (math.cos(n) * 40, -30 + math.sin(n) * 25), 10, k)
    return build(T, f)


@defset("ult")
def S_ult():
    """Tuyệt kỹ Long tộc – LONG UY: mây sấm kéo tới, thiên lôi giáng thẳng xuống thân rồng, rồi lôi trận giáng dồn dập
    quanh rồng (trước – sau, trái – phải, nhanh dần), kết bằng VẠN LÔI TỀ GIÁNG 5 tia cùng lúc; sét dùng ảnh tia sét
    của người dùng (HieuUng/loi_truc.png): loá trắng – chớp tắt – tái giáng – tàn, chạm đất nổ + vòng chấn."""
    segs = [("aura3", 12), ("ult1", 8), ("ult2", 8), ("ult3", 8), ("ult4", 8), ("ult2", 8), ("ult3", 8), ("ult4", 10),
            ("roar4", 12), ("walk3", 10)]
    T = 92
    seq = tl(segs, 2)
    # lịch giáng: (khung, x, sau lưng?, hệ số cao, lật?)
    plan = [(16, -110, False, 0.95, 0), (21, 140, True, 0.85, 1), (26, -210, True, 0.9, 0), (30, 90, False, 1.0, 1),
            (34, -300, False, 0.95, 1), (37, 200, True, 0.8, 0), (40, -60, True, 0.9, 1), (43, -360, True, 0.85, 0),
            (46, 160, False, 1.0, 0), (48, -170, False, 0.95, 1), (50, 240, True, 0.8, 1), (52, -250, True, 0.9, 0),
            (54, 40, False, 1.0, 0), (56, -410, True, 0.8, 1), (58, 120, False, 0.95, 1)]
    FIN = 62
    final = [(-330, True, 0.95, 0), (-170, False, 1.05, 1), (10, False, 1.1, 0), (170, True, 0.9, 1), (-460, True, 0.8, 1)]
    LIFE = (1.0, 0.92, 0.3, 0.88, 0.5, 0.22, 0.08)                   # loá – giữ – tắt – tái giáng – tàn

    def strike(F, x, a, back, hk, flip, big=False):
        if a < 0 or a >= len(LIFE):
            return
        al = LIFE[a]
        gy = -10 if back else 6
        H = (360 if back else 400) * hk * (1.15 if big else 1.0)
        k = key("hu_loi_truc")
        sy = H / (k.im.height * SCALE)
        sx = sy * (0.85 if back else 1.0) * (-1 if flip else 1)
        lay, glay = ("bg", "bgg") if back else ("fg", "fgg")
        fl = 0.85 if a == 0 else (0.45 if a == 3 else 0.0)
        F.sprite("hu_loi_truc", (x, gy), sx=sx * 1.04, sy=sy * 1.02, alpha=al * 0.9, pivot="anchor", layer=glay, flash=0.6)
        F.placed.pop()                                               # quầng sáng (lớp mờ)
        F.sprite("hu_loi_truc", (x, gy), sx=sx, sy=sy, alpha=al, pivot="anchor", layer=lay, flash=fl)
        F.placed.pop()
        # chạm đất: loá tròn dẹt, nổ nhỏ, bụi đá, vòng chấn
        F.ell((x, gy), 34 * al + 10, 9 * al + 3, fill=(215, 175, 255, int(230 * al)), layer=glay)
        F.ell((x, gy), 12 * al + 3, 4 * al + 1, fill=(255, 245, 255, int(255 * al)), layer=lay)
        if a <= 4:
            kb = key("hu_no_vang_tim")
            dz = (150.0 if big else 105.0) / kb.im.width / SCALE * (0.6 + 0.12 * a)
            F.sprite("hu_no_vang_tim", (x, gy + 2), sx=dz, sy=dz * 0.8, alpha=(1 - a / 5.0) * 0.9, pivot="anchor", layer=lay)
            F.placed.pop()
        if 1 <= a <= 5:
            ring(F, (x, gy), 16 + a * (14 if big else 9), 4 + a * 2.5, 1 - a / 6.0)
            dust(F, (x + (a - 3) * 6, gy - 2), 6 + a * 2.5, 0.6 - a * 0.1, back)
        # loé trong mây ở gốc tia
        F.ell((x + (40 if not flip else -40) * hk, -380), 38, 12, fill=(160, 110, 255, int(85 * al)), layer="bgg")

    def f(F, i):
        a, b, m = seq[i]
        act = 12 <= i < 76
        spin = (i - 12) * 4 if act else 0
        pulse = 1 + 0.05 * math.sin(i * 1.1) if act else 1
        sh = shake(i, 3.2 if i in (12, 13, FIN, FIN + 1) else 2.0) if 12 <= i <= 78 else (0, 0)
        fl = 0.9 if i in (12, FIN) else (0.45 if i in (13, 30, 46, 54, FIN + 1) else 0)
        r = random.Random(i * 13)
        # mây sấm tím đen (sau lưng mọi thứ)
        cl = kfv(i, [(0, 0.0), (10, 0.9), (76, 0.9), (92, 0.0)])
        if cl > 0.01:
            rc = random.Random(5)
            for n in range(16):                                        # cụm mây bồng, mép mờ, không thành dải
                cx = -470 + n * 50 + rc.uniform(-25, 25) + math.sin(i * 0.08 + n) * 8
                cy = -392 + rc.uniform(-6, 14)
                rx, ry = 40 + rc.uniform(0, 45), 14 + rc.uniform(0, 16)
                F.ell((cx, cy), rx, ry, fill=(30, 16, 56, int(95 * cl)), layer="bgg")
                F.ell((cx + 6, cy - 3), rx * 0.6, ry * 0.55, fill=(58, 30, 104, int(70 * cl)), layer="bgg")
            if 4 <= i < 12 and i % 2 == 0:                              # chớp ngầm trong mây khi tụ khí
                F.ell((r.uniform(-400, 250), -384), 46, 13, fill=(170, 110, 255, 100), layer="bgg")
        info = pair(F, a, b, m, pos=sh, rot=math.sin(math.radians(spin)) * 4, sx=pulse, sy=pulse, pivot="anchor",
                    glow=kfv(i, [(0, 0.3), (12, 0.65), (76, 0.65), (92, 0.2)]), flash=fl)
        c = info["center"]
        if i < 12:                                           # tụ khí: hạt sáng hút vào, quả cầu hiện
            for _ in range(14):
                p = add(c, dirv(r.uniform(0, 360)), 100 * (1 - i / 12.0) + 10)
                F.line([p, add(p, dirv(r.uniform(0, 360)), 4)], (235, 220, 255, 230), 0.9)
            F.fxsprite("fx_orb", add(c, (0, -70)), scale=0.4 + 0.045 * i, rot=i * 20, alpha=0.6 + 0.035 * i)
        # THIÊN LÔI GIÁNG THÂN
        strike(F, 0, i - 12, False, 1.12, 0, big=True)
        strike(F, 0, i - 13, True, 1.05, 1, big=True)
        if 12 <= i <= 22:                                    # nổ mặt đất dưới chân rồng
            u = (i - 12) / 10.0
            kd = key("hu_no_dat")
            dz = 360.0 / kd.im.width / SCALE
            F.sprite("hu_no_dat", (0, 4), sx=dz * (0.5 + 0.6 * u), sy=dz * (0.3 + 0.7 * u), alpha=1 - u ** 1.6, pivot="anchor",
                     layer="bg", flash=0.5 if i < 14 else 0)
            F.placed.pop()
        for t0, x, back, hk, flip in plan:                     # LÔI TRẬN
            strike(F, x, i - t0, back, hk, flip)
        for n, (x, back, hk, flip) in enumerate(final):          # VẠN LÔI TỀ GIÁNG
            strike(F, x, i - FIN - (n % 2), back, hk, flip, big=True)
        if act:
            for t0 in list(range(12, 60, 6)) + [FIN]:
                a_ = i - t0
                if 0 <= a_ < 10:
                    big = t0 in (12, FIN)
                    ring(F, add(c, (0, 20)), 40 + a_ * (30 if big else 18), 10 + a_ * (6 if big else 4), 1 - a_ / 10.0)
            body_arcs(F, info, r, 5 if i >= FIN else 4, 1.0, ln=(14, 32))
        if 66 <= i < 86:                                     # dư chấn: điện bò mặt đất, khói tan
            k2 = 1 - (i - 66) / 20.0
            for _ in range(3):
                x0 = r.uniform(-420, 260)
                bolt(F, (x0, -2), (x0 + r.uniform(-60, 60), -2 - r.uniform(0, 14)), r, 1.0, 0.8 * k2, branches=1, back=True)
            for n in range(4):
                dust(F, (-330 + n * 160 + math.sin(i + n) * 10, -6 - (i - 66) * 0.8), 14 + (i - 66), 0.45 * k2, True)
        if i in (12, FIN):
            flash_burst(F, c, 62, 1.0)
        elif i in (13, FIN + 1):
            flash_burst(F, c, 40, 0.55)
    return build(T, f)


HIT = {}                                     # điểm trúng icon của các chiêu phá phách (toạ độ khung, neo = 0,0, quay trái)
BITE_CHOMPS = (8, 18, 28)


@defset("bite")
def S_bite():
    """Ôm icon cắn: vươn vuốt ôm lấy, ngửa đầu há miệng rồi đớp phập xuống 3 lần (mỗi lần gặm rung đầu), thở phì."""
    T = 36

    def f(F, i):
        c = min(BITE_CHOMPS, key=lambda x: abs(i - x))
        d_ = i - c
        if i < 5:
            k_, pos, rot, sx, sy = "roar1", (kfv(i, [(0, 0), (4, 8)]), 0), kfv(i, [(0, 0), (4, 6)]), 1, 1
        elif i >= 32:
            k_, pos, rot, sx, sy = "roar1", (kfv(i, [(32, -8), (35, 0)]), 0), kfv(i, [(32, -4), (35, 0)]), 1, 1
        elif d_ in (-3, -2, -1):                                     # ngửa đầu, há miệng
            k_, pos, rot, sx, sy = "roar2", (6 + 3 * d_ * -1, -4), 8, 1, 1
        elif d_ == 0:                                                # ĐỚP
            k_, pos, rot, sx, sy = "roar2", (-14, 4), -10, 1.06, 0.9
        elif 1 <= d_ <= 4:                                           # gặm: lắc đầu nhay nhay
            sh = shake(i, 2.5)
            k_, pos, rot, sx, sy = "roar1", (-10 + sh[0], 3 + sh[1]), -6 + 3 * math.sin(i * 2.1), 1.03, 0.95
        else:
            k_, pos, rot, sx, sy = "roar1", (0, 0), 2, 1, 1
        info = F.sprite(k_, pos, sx=sx, sy=sy, rot=rot, pivot="anchor", glow=0.45, glow_col=(255, 170, 60),
                        flash=0.35 if d_ == 0 else 0)
        M = info["mouth"]
        if i == BITE_CHOMPS[0]:
            HIT["bite"] = add(M, (-10, 6))
        r = random.Random(i * 5)
        if d_ == 0:                                                  # loé răng nanh
            flash_burst(F, M, 16, 0.9)
            for a in (150, 180, 210):
                F.line([add(M, dirv(a), 6), add(M, dirv(a), 20)], (255, 250, 230, 255), 1.4)
        if 1 <= d_ <= 4 and i % 2 == 0:                              # vụn bắn ra quanh miệng
            for _ in range(4):
                p = add(M, dirv(r.uniform(120, 240)), r.uniform(8, 24))
                F.ell(p, 1.4, 1.4, fill=(255, 220, 120, 230))
        if i % 6 == 3:
            body_arcs(F, info, r, 2, 0.9)
    return build(T, f)


def _tail_tip(name):
    """Chóp đuôi = điểm xa nhất bên phải (rồng quay trái) của khung gốc."""
    k = key(name)
    A = np.asarray(k.im.getchannel("A"))
    ys, xs = np.nonzero(A > 140)
    x1 = xs.max()
    sel = xs >= x1 - 4
    return (float(x1), float(ys[sel].mean()))


@defset("tail")
def S_tail():
    """Quật đuôi: thu người, vung đuôi lên cao run run lấy đà, rồi QUẬT vút xuống (vệt đuôi, loé chạm), dội lại."""
    T = 30
    HIT_F = 14
    K = "walk5"

    def f(F, i):
        rot = kfv(i, [(0, 0), (6, -26), (10, -30), (12, -28), (13, -8), (14, 8), (15, 18), (18, 10), (24, -3), (30, 0)])
        if 6 <= i <= 11:
            rot += 2.0 * math.sin(i * 2.7)                           # run run lấy đà
        k = key(K)
        info = F.sprite(K, (0, -20), rot=rot, pivot=k.mouth, glow=kfv(i, [(0, 0.3), (12, 0.8), (18, 0.5), (30, 0.3)]),
                        glow_col=(255, 170, 60), flash=0.4 if i == HIT_F else 0)
        tip = info["fwd"](_tail_tip(K))
        if i == HIT_F:
            HIT["tail"] = tip
            flash_burst(F, tip, 22, 1.0)
            ring(F, tip, 26, 10, 0.9)
        if 12 <= i <= 17:                                             # vệt quật: cung sáng theo đường chóp đuôi
            for j in range(1, 5):
                r0 = kfv(i - j * 0.5, [(0, 0), (6, -26), (10, -30), (12, -28), (13, -8), (14, 8), (15, 18), (18, 10)])
                pv = info["fwd"](k.mouth)
                tp = _tail_tip(K)
                dx, dy = (tp[0] - k.mouth[0]) * SCALE, (tp[1] - k.mouth[1]) * SCALE
                th = math.radians(r0)
                q = (pv[0] + dx * math.cos(th) - dy * math.sin(th), pv[1] + dx * math.sin(th) + dy * math.cos(th))
                F.ell(q, 7 - j, 7 - j, fill=(255, 210, 120, int(200 / j)), layer="fgg")
        if i % 5 == 2:
            body_arcs(F, info, random.Random(i), 2, 0.9)
    return build(T, f)


def compute_hits():
    """Dựng thử đúng khung ra đòn của các chiêu để biết điểm trúng icon (chạy trong tiến trình chính)."""
    for name, i in (("bite", BITE_CHOMPS[0]), ("tail", 14), ("fire", 20), ("boltb", 20), ("coil", 20)):
        fr = SETS[name]["fn"]()
        F = Frame()
        fr[i](F)
    return dict(HIT)


@defset("dark")
def S_dark():
    segs = [("walk3", 4), ("st1", 10), ("st5", 22), ("walk3", 6)]
    T = 42
    seq = tl(segs, 3)

    def f(F, i):
        a, b, m = seq[i]
        sh = shake(i, 1.2) if 14 <= i <= 36 else (0, 0)
        info = pair(F, a, b, m, pos=sh, pivot="anchor", glow=kfv(i, [(0, 0.2), (14, 0.9), (36, 0.9), (42, 0.2)]),
                    glow_col=(140, 60, 255), flash=0.5 if i == 14 else 0)
        r = random.Random(i * 17)
        c = info["center"]
        if 4 <= i <= 14:
            F.fxsprite("fx_vorb", add(c, (-36, -10)), scale=0.35 + 0.04 * (i - 4), rot=i * 25, alpha=0.9)
        if 14 <= i <= 36:
            body_arcs(F, info, r, 3, 1.0, VIO_G, VIO_M, ln=(14, 30))
            for _ in range(2):
                a_ = r.uniform(200, 340)
                bolt(F, add(c, dirv(a_), 30), add(c, dirv(a_), 90), r, 1.2, 0.9, VIO_G, VIO_M, 1)
        if i == 14:
            flash_burst(F, c, 50, 1.0, col=(200, 160, 255))
    return build(T, f)


# ── cảm xúc ──
@defset("doubt", step=2)
def S_doubt():
    segs = [("emo1", 12), ("emo2", 12), ("emo1", 12), ("emo2", 12)]
    T = 48
    seq = tl(segs, 2, loop=True)

    def f(F, i):
        a, b, m = seq[i]
        info = pair(F, a, b, m, rot=4 * math.sin(TAU * i / 24), sy=1 + 0.015 * math.sin(TAU * i / 12), pivot="anchor", glow=0.15)
        if a == "emo2" or b == "emo2":                       # dấu ? nhún nhảy cho khung không có sẵn
            c = info["fwd"]((key("emo2").im.width * 0.25, 4))
            y = -6 * abs(math.sin(TAU * i / 12))
            F.line([add(c, (-4, -14 + y)), add(c, (-1, -18 + y)), add(c, (3, -15 + y)), add(c, (0, -9 + y)), add(c, (0, -6 + y))],
                   (120, 190, 255, 255), 2.2)
            F.ell(add(c, (0, -2 + y)), 1.3, 1.3, fill=(120, 190, 255, 255))
    return build(T, f)


@defset("love", step=2)
def S_love():
    segs = [("emo4", 16), ("emo5", 16), ("emo4", 16)]
    T = 48
    seq = tl(segs, 3)

    def f(F, i):
        a, b, m = seq[i]
        hop = -4 * abs(math.sin(TAU * i / 16))
        info = pair(F, a, b, m, pos=(0, hop), rot=3 * math.sin(TAU * i / 24), pivot="anchor", glow=0.25, glow_col=(255, 120, 180))
        c = info["center"]
        for n in range(4):
            ph = ((i / 24.0 + n / 4.0) % 1.0)
            heart(F, add(c, (-40 + n * 22 + 6 * math.sin(ph * 6), -40 - ph * 60)), 4 + 3 * ph, math.sin(math.pi * ph))
    return build(T, f)


def anger_mark(F, c, s, al):
    """Dấu gân giận (4 nét cong đỏ) cạnh đầu."""
    for k in range(4):
        a = 45 + 90 * k
        p0 = add(c, dirv(a - 20), s * 0.35)
        p1 = add(c, dirv(a), s)
        p2 = add(c, dirv(a + 20), s * 0.35)
        F.line([p0, p1, p2], (255, 60, 60, int(255 * al)), 1.6)
        F.line([p0, p1, p2], (255, 40, 40, int(150 * al)), 4, layer="fgg")


@defset("angry")
def S_angry():
    segs = [("walk3", 4), ("emo5", 16), ("roar3", 14), ("emo5", 14), ("walk3", 4)]
    T = 52
    seq = tl(segs, 2)

    def f(F, i):
        a, b, m = seq[i]
        hop = -6 * abs(math.sin(TAU * i / 8)) if 4 <= i < 20 else 0              # dậm chân bực bội
        sh = shake(i, 1.6) if 4 <= i <= 48 else (0, 0)
        sq = kfv(i, [(0, 0.86), (3, 1.0)])
        info = pair(F, a, b, m, pos=(sh[0], hop + sh[1]), sy=sq, sx=2 - sq, pivot="anchor",
                    glow=kfv(i, [(0, 0.3), (8, 0.8), (46, 0.8), (52, 0.2)]), glow_col=(255, 50, 40),
                    flash=0.5 if i == 20 else 0)
        M = info["mouth"]
        r = random.Random(i * 19)
        kk = info["key"]
        head = info["fwd"]((kk.im.width * 0.32, kk.im.height * 0.02))
        anger_mark(F, add(head, (6, -10)), 8 + 2 * math.sin(i * 1.3), 1.0 if 4 <= i <= 48 else 0.0)
        for n in range(2):                                                    # phì khói nóng từ mũi
            ph = ((i * 0.12 + n * 0.5) % 1.0)
            F.ell(add(M, (6 - 10 * ph, -4 - 14 * ph)), 2 + 5 * ph, 2 + 4 * ph, fill=(170, 160, 160, int(170 * (1 - ph))), layer="fgg")
        if 20 <= i <= 33:                                                     # thét giận: sóng âm đỏ + sét đỏ tím
            for t0 in range(20, 34, 3):
                a_ = i - t0
                if 0 <= a_ < 8:
                    pts = [add(M, dirv(120 + 120 * k / 16.0), 8 + a_ * 11) for k in range(17)]
                    F.line(pts, (255, 60, 50, int(180 * (1 - a_ / 8.0))), 3.4, layer="fgg")
                    F.line(pts, (255, 220, 210, int(230 * (1 - a_ / 8.0))), 1.0)
            body_arcs(F, info, r, 3, 1.0, (255, 40, 60), (255, 190, 200))
        if i == 20:
            flash_burst(F, M, 24, 1.0, col=(255, 120, 100))
        if 4 <= i < 20 and i % 4 == 0:
            dust(F, (r.uniform(-20, 20), -2), 8, 0.7)
    return build(T, f)


@defset("tantrum")
def S_tantrum():
    T = 48

    def f(F, i):
        w = TAU * i / T
        k = "coil1" if (i // 12) % 2 == 0 else "emo5"
        rock_ = 16 * math.sin(2 * w) if k == "coil1" else 4 * math.sin(4 * w)
        info = F.sprite(k, (6 * math.sin(2 * w), -3 * abs(math.sin(4 * w))), rot=rock_, pivot="anchor", glow=0.2)
        M = info["mouth"]
        for n in range(6):                                   # nước mắt phun hai bên
            a = ((i * 0.12 + n / 6.0) % 1.0)
            side = -1 if n % 2 else 1
            droplet(F, (M[0] + 8 + side * (6 + 30 * a), M[1] - 14 - 18 * math.sin(math.pi * a) + 12 * a * a), 1.8, 1 - a)
        if i % 12 in (0, 1):
            dust(F, (0, -2), 10, 0.7)
    return build(T, f)


@defset("cry", step=2)
def S_cry():
    T = 40

    def f(F, i):
        sn = 1.0 if (i % 14) < 3 else 0.0
        info = F.sprite("emo3", (0, sn), sy=1 - 0.02 * sn, rot=-2 + math.sin(TAU * i / 40), pivot="anchor", glow=0.1,
                        glow_col=(120, 170, 255))
        M = info["mouth"]
        e = add(M, (10, -12))
        for n in range(4):
            a = ((i / 12.0 + n / 4.0) % 1.0)
            droplet(F, add(e, (-2 - 3 * a, 30 * a * a + 2)), 2.6, 1 - a * 0.6)
        F.line([e, add(e, (-1, 8))], (150, 215, 255, 230), 2.4)
    return build(T, f)


@defset("beg", step=2)
def S_beg():
    T = 40

    def f(F, i):
        info = F.sprite("emo4", (0, -2 * abs(math.sin(TAU * i / 10))), rot=5 * math.sin(TAU * i / 20), pivot="anchor",
                        glow=0.25, glow_col=(255, 140, 190))
        c = info["center"]
        for n in range(3):
            a = ((i / 20.0 + n / 3.0) % 1.0)
            sparkle(F, add(c, dirv(-140 + n * 50), 52 + 4 * math.sin(a * 6)), 1.5 + 3 * math.sin(math.pi * a), math.sin(math.pi * a))
    return build(T, f)


# ───────────────────────── 5. xem thử ─────────────────────────
def render_frame(draw):
    F = Frame()
    draw(F)
    return F.finish()


def sheet(ims, path, z=1, cols=None, bgc=(52, 58, 76, 255)):
    bb = None
    for im in ims:
        b = im.getbbox()
        if b:
            bb = b if bb is None else (min(bb[0], b[0]), min(bb[1], b[1]), max(bb[2], b[2]), max(bb[3], b[3]))
    bb = bb or (0, 0, 10, 10)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    cols = cols or len(ims)
    rows = (len(ims) + cols - 1) // cols
    out = Image.new("RGBA", (int(w * z) * cols, int(h * z) * rows), bgc)
    for k, im in enumerate(ims):
        c = im.crop(bb).resize((int(w * z), int(h * z)), Image.LANCZOS)
        out.alpha_composite(c, ((k % cols) * int(w * z), (k // cols) * int(h * z)))
    out.convert("RGB").save(path)
    return out.size


def preview(names, n=8, z=1.0, path="/tmp/co_long_xem.png"):
    ims = []
    for nm in names:
        fr = SETS[nm]["fn"]()
        idx = sorted(set(int(k * (len(fr) - 1) / max(1, n - 1)) for k in range(n)))
        ims += [render_frame(fr[i]) for i in idx]
        ims += [Image.new("RGBA", (CW, CH))] * (n - len(idx))
    return sheet(ims, path, z, cols=n)


# ───────────────────────── 6. xuất bộ Shimeji-ee ─────────────────────────
FALL = "com.group_finity.mascot.action.Fall"
JUMP = "com.group_finity.mascot.action.Jump"
DRAG = "com.group_finity.mascot.action.Dragged"


def P_(st, vel=(0, 0), d=None, rev=False):
    return dict(set=st, vel=vel, d=d, rev=rev)


def _anim(name, st, border="Floor", typ="Animate", vel=(0, 0), **attrs):
    a = dict(name=name, type=typ, poses=[P_(st, vel)], attrs=attrs)
    if border:
        a["border"] = border
    return a


def _seq(name, *refs):
    return dict(name=name, type="Sequence", refs=[r if isinstance(r, tuple) else (r, {}) for r in refs])


ACTIONS = [
    _anim("Stand", "stand", typ="Stay"), _anim("StandAlt", "standb", typ="Stay"),
    _anim("Walk", "walk", typ="Move", vel=(-WALK_V, 0)), _anim("Run", "run", typ="Move", vel=(-WALK_V * 3.6, 0)),
    _anim("BoTruon", "crawl", typ="Move", vel=(-0.9, 0)), _seq("LongDi_BoTruon", ("BoTruon", {"Duration": "200"})),
    _anim("Dash", "dash", typ="Move", vel=(-10, 0)),
    dict(name="Fall", type="Embedded", cls=FALL, attrs=dict(RegistanceX="0.05", RegistanceY="0.1", Gravity="2"), poses=[P_("fall")]),
    dict(name="Thrown", type="Embedded", cls=FALL, attrs=dict(RegistanceX="0.02", RegistanceY="0.05", Gravity="2"), poses=[P_("spin")]),
    dict(name="Dragged", type="Embedded", cls=DRAG, poses=[P_("drag")]),
    _anim("Land", "land"),
    _anim("GrabWall", "wallg", border="Wall", typ="Stay"), _anim("ClimbWall", "wallc", border="Wall", typ="Move", vel=(0, -WALK_V)),
    _anim("GrabCeiling", "ceilg", border="Ceiling", typ="Stay"),
    _anim("ClimbCeiling", "ceilc", border="Ceiling", typ="Move", vel=(-WALK_V, 0)),
    dict(name="NhayLen", type="Embedded", cls=JUMP, attrs=dict(VelocityParam="22",
         TargetX="${mascot.anchor.x + (mascot.lookRight ? 240 : -240)}", TargetY="${mascot.anchor.y - 190}"), poses=[P_("fly")]),
    _anim("ChayToiVach", "run", vel=(-6, 0)),
    dict(name="JumpToLeftWall", type="Embedded", cls=JUMP, attrs=dict(VelocityParam="22",
         TargetX="${mascot.environment.workArea.left}", TargetY="${mascot.environment.workArea.bottom - 260}"), poses=[P_("fly")]),
    dict(name="JumpToRightWall", type="Embedded", cls=JUMP, attrs=dict(VelocityParam="22",
         TargetX="${mascot.environment.workArea.right}", TargetY="${mascot.environment.workArea.bottom - 260}"), poses=[P_("fly")]),
    _seq("LongDi_BamVachTrai", "ChayToiVach", "JumpToLeftWall"), _seq("LongDi_BamVachPhai", "ChayToiVach", "JumpToRightWall"),
    # nghỉ
    _anim("NamXuong", "lie"), dict(name="DungDay", type="Animate", border="Floor", poses=[P_("lie", rev=True)]),
    _anim("CuonMinh", "rest", typ="Stay"), _anim("Ngu", "sleep", typ="Stay"),
    _seq("LongNghi_CuonMinh", "NamXuong", ("CuonMinh", {"Duration": "420"}), "DungDay"),
    _seq("LongNghi_Ngu", "NamXuong", ("Ngu", {"Duration": "1500"}), "DungDay"),
    # chiêu
    _anim("GamRu", "roar"), _anim("PhunLua", "fire"), _anim("PhunSamSet", "boltb"), _anim("CuonThan", "coil"),
    _anim("CanIcon", "bite"), _anim("QuatDuoi", "tail"),
    _seq("LongKy_OmCan", "CanIcon"), _seq("LongKy_QuatDuoi", "QuatDuoi"),
    _anim("LoiDien", "aura"), _anim("TreoLoLung", "hover"), _anim("LongUy", "ult"), _anim("HacHoa", "dark"), _anim("HoaMini", "mini"),
    _seq("LongKy_GamRu", "GamRu"), _seq("LongKy_PhunLua", "PhunLua"), _seq("LongKy_PhunSamSet", "PhunSamSet"),
    _seq("LongKy_CuonThan", "CuonThan"), _seq("LongKy_LoiDien", "LoiDien"), _seq("LongKy_TreoLoLung", "TreoLoLung"),
    _seq("LongBa_LongUy", "LongUy"), _seq("LongBa_HacHoa", "HacHoa"), _seq("LongBien_HoaMini", "HoaMini"),
    _seq("LongBa_FullCombo", "GamRu", "CuonThan", "PhunSamSet", "PhunLua", "LoiDien", "LongUy"),
    # bay
    _anim("CatCanh", "takeoff"),
    dict(name="BayLen", type="Embedded", cls=JUMP, attrs=dict(VelocityParam="20",
         TargetX="${mascot.anchor.x + (mascot.lookRight ? 60 : -60)}", TargetY="${mascot.anchor.y - 300}"), poses=[P_("fly")]),
    dict(name="BayTheo", type="Embedded", cls=JUMP, attrs=dict(VelocityParam="16",
         TargetX="${mascot.environment.cursor.x}", TargetY="${mascot.environment.cursor.y - 60}"), poses=[P_("flydash")]),
    dict(name="LuonVong", type="Animate", poses=[P_("fly")], attrs=dict(Duration="54")),
    dict(name="HaCanh", type="Embedded", cls=FALL, attrs=dict(RegistanceX="0.08", RegistanceY="0.22", Gravity="1"), poses=[P_("fly")]),
    dict(name="LaoXuong", type="Embedded", cls=FALL, attrs=dict(RegistanceX="0", RegistanceY="0", Gravity="5"), poses=[P_("dive")]),
    _anim("DapDat", "impact"),
    _seq("LongPhi_BayVut", "CatCanh", "BayLen", "LuonVong", "HaCanh", "Land"),
    _seq("LongPhi_BayTheoChuot", "CatCanh", "BayLen", "BayTheo", "LuonVong", "HaCanh", "Land"),
    _seq("LongPhi_LaoXuongDapDat", "CatCanh", "BayLen", "LaoXuong", "DapDat"),
    # cảm xúc
    _anim("TucGian", "angry"), _seq("LongTinh_TucGian", "TucGian"),
    _anim("HoaiNghi", "doubt"), _anim("YeuThich", "love"), _anim("AnVa", "tantrum", typ="Stay"), _anim("Khoc", "cry", typ="Stay"),
    _anim("NanNi", "beg", typ="Stay"),
    _seq("LongTinh_HoaiNghi", "HoaiNghi"), _seq("LongTinh_YeuThich", "YeuThich"), _seq("LongTinh_AnVa", ("AnVa", {"Duration": "144"})),
    _seq("LongTinh_Khoc", ("Khoc", {"Duration": "120"})), _seq("LongTinh_NanNi", ("NanNi", {"Duration": "120"})),
    dict(name="ChaseMouse", type="Move", border="Floor", attrs=dict(TargetX="${mascot.environment.cursor.x}",
         TargetY="${mascot.environment.floor.y}"), poses=[P_("run", (-8, 0))]),
    _seq("LongTruy_DuoiChuot", "ChaseMouse", "GamRu"),
]

FREQ = [("Stand", 80), ("StandAlt", 35), ("Walk", 100), ("Run", 30), ("Dash", 15), ("LongDi_BoTruon", 30),
        ("LongNghi_CuonMinh", 24), ("LongNghi_Ngu", 8),
        ("LongKy_GamRu", 9), ("LongKy_PhunLua", 8), ("LongKy_PhunSamSet", 8), ("LongKy_CuonThan", 9), ("LongKy_OmCan", 6), ("LongKy_QuatDuoi", 6), ("LongKy_LoiDien", 8),
        ("LongKy_TreoLoLung", 8), ("LongBa_LongUy", 3), ("LongBa_HacHoa", 4), ("LongBa_FullCombo", 2), ("LongBien_HoaMini", 5),
        ("LongPhi_BayVut", 8), ("LongPhi_BayTheoChuot", 4), ("LongPhi_LaoXuongDapDat", 4),
        ("LongDi_BamVachTrai", 5), ("LongDi_BamVachPhai", 5),
        ("LongTinh_HoaiNghi", 8), ("LongTinh_TucGian", 5), ("LongTinh_YeuThich", 7), ("LongTinh_AnVa", 4), ("LongTinh_Khoc", 4), ("LongTinh_NanNi", 6),
        ("LongTruy_DuoiChuot", 4)]

META = {
    "name": "Cổ Long",
    "desc": "Hắc long thái cổ (rồng đen vảy vàng) – bộ hình của người dùng, hiệu ứng lôi điện",
    "fly_prefix": "flydash",
    "drop_action": "LongPhi_LaoXuongDapDat",
    "wall_hit_action": "LongTinh_TucGian",
    "rev": 2,
    "climb_behaviors": ["LongDi_BamVachTrai", "LongDi_BamVachPhai"],
    "groups": {"LongKy": "Long kỹ", "LongBa": "Tuyệt kỹ", "LongPhi": "Bay lượn", "LongTinh": "Biểu cảm",
               "LongNghi": "Nghỉ ngơi", "LongDi": "Di chuyển", "LongTruy": "Theo chuột", "LongBien": "Biến hoá"},
    "labels": {
        "StandAlt": "Ngó nghiêng", "Run": "Chạy nhanh", "Dash": "Lướt sát đất",
        "LongNghi_CuonMinh": "Nằm nghỉ", "LongNghi_Ngu": "Ngủ say (khò khò)",
        "LongKy_GamRu": "Gầm rú & thét lớn", "LongKy_PhunLua": "Phun lửa", "LongKy_PhunSamSet": "Phun sấm sét",
        "LongKy_CuonThan": "Cuộn thân", "LongKy_OmCan": "Ôm cắn (đớp phập)", "LongKy_QuatDuoi": "Quật đuôi", "LongKy_LoiDien": "Lôi điện quanh thân", "LongKy_TreoLoLung": "Treo lơ lửng",
        "LongBa_LongUy": "Tuyệt kỹ Long tộc (Long uy)", "LongBa_HacHoa": "Hắc hoá (trạng thái tím)",
        "LongBa_FullCombo": "FULL COMBO Long tộc", "LongBien_HoaMini": "Hoá rồng mini",
        "LongPhi_BayVut": "Bay vút lên trời", "LongPhi_BayTheoChuot": "Bay theo chuột",
        "LongPhi_LaoXuongDapDat": "Lao xuống & đập đất", "LongDi_BamVachTrai": "Leo vách trái", "LongDi_BoTruon": "Bò trườn sát đất", "LongDi_BamVachPhai": "Leo vách phải",
        "LongTinh_HoaiNghi": "Hoài nghi (???)", "LongTinh_YeuThich": "Yêu thích (tim bay)", "LongTinh_AnVa": "Ăn vạ",
        "LongTinh_Khoc": "Khóc", "LongTinh_TucGian": "Tức giận (gân đỏ, thét)", "LongTinh_NanNi": "Nằn nì", "LongTruy_DuoiChuot": "Đuổi theo chuột",
    },
    "triggers": {
        "L1": {"act": "LongKy_PhunSamSet", "cmd": "upcoming"}, "L2": {"act": "", "cmd": "manager"},
        "L3": {"act": "LongBa_FullCombo", "cmd": ""}, "LH": {"act": "LongKy_LoiDien", "cmd": ""},
        "R1": {"act": "", "cmd": "menu"}, "R2": {"act": "LongBa_HacHoa", "cmd": ""},
        "R3": {"act": "LongTinh_YeuThich", "cmd": ""}, "RH": {"act": "LongPhi_BayTheoChuot", "cmd": ""},
        "WU": {"act": "LongPhi_BayVut", "cmd": ""}, "WD": {"act": "LongNghi_CuonMinh", "cmd": ""},
        "M1": {"act": "LongBien_HoaMini", "cmd": ""},
        "E_REMIND": {"act": "LongKy_GamRu"}, "E_DONE": {"act": "LongTinh_YeuThich"}, "E_SNOOZE": {"act": "LongTinh_AnVa"},
        "E_SKIP": {"act": "LongTinh_Khoc"}, "E_BREAK": {"act": "LongNghi_CuonMinh"}, "E_GREET": {"act": "LongKy_TreoLoLung"},
        "E_SLEEP": {"act": "LongNghi_Ngu"}, "E_WAKE": {"act": "LongKy_GamRu"},
        "E_TYPING": {"act": "LongKy_LoiDien"}, "E_DELETING": {"act": "LongKy_PhunSamSet"},
        "S_L1": {"act": "LongKy_PhunSamSet"}, "S_L2": {"act": "LongKy_PhunLua"}, "S_R1": {"act": "LongKy_CuonThan"},
        "S_R2": {"act": "LongBa_LongUy"}, "S_WU": {"act": "LongPhi_LaoXuongDapDat"}, "S_WD": {"act": "LongKy_GamRu"},
        "S_M1": {"act": "LongBa_HacHoa"}, "S_HK": {"act": "LongBa_FullCombo"},
    },
}

XMLNS = ('xmlns="http://www.group-finity.com/Mascot" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
         'xsi:schemaLocation="http://www.group-finity.com/Mascot Mascot.xsd"')


def _attr(d):
    return "".join(' %s="%s"' % (k, str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))
                   for k, v in d.items())


def _num(v):
    return ("%d" % v) if float(v).is_integer() else ("%g" % v)


def build_actions_xml(info):
    L = ['<?xml version="1.0" encoding="UTF-8"?>', "<Mascot %s>" % XMLNS, " <ActionList>"]
    for a in ACTIONS:
        at = {"Name": a["name"], "Type": a["type"]}
        if a.get("cls"):
            at["Class"] = a["cls"]
        if a.get("border"):
            at["BorderType"] = a["border"]
        if a["type"] == "Sequence":
            at["Loop"] = "false"
        at.update(a.get("attrs", {}))
        L.append("  <Action%s>" % _attr(at))
        if a["type"] == "Sequence":
            for rn, ra in a["refs"]:
                L.append("   <ActionReference%s/>" % _attr(dict({"Name": rn}, **ra)))
        else:
            L.append("   <Animation>")
            for ps in a["poses"]:
                inf = info[ps["set"]]
                d = ps["d"] or inf["d"]
                items = list(enumerate(inf["files"]))
                if ps["rev"]:
                    items = items[::-1]
                for k, fn in items:
                    ax, ay = inf["anchor"]
                    L.append('    <Pose Image="/%s" ImageAnchor="%d,%d" Velocity="%s,%s" Duration="%d"/>'
                             % (fn, ax, ay, _num(ps["vel"][0]), _num(ps["vel"][1]), d))
            L.append("   </Animation>")
        L.append("  </Action>")
    L += [" </ActionList>", "</Mascot>", ""]
    return "\n".join(L)


def build_behaviors_xml():
    def nexts(ind="    "):
        out = [ind + '<NextBehaviorList Add="false">']
        out += [ind + ' <BehaviorReference Name="%s" Frequency="%d"/>' % (n, f) for n, f in FREQ]
        out.append(ind + "</NextBehaviorList>")
        return out
    L = ['<?xml version="1.0" encoding="UTF-8"?>', "<Mascot %s>" % XMLNS, " <BehaviorList>"]
    for n, nx in (("Fall", "Land"), ("Dragged", "Fall"), ("Thrown", "Fall")):
        L += ['   <Behavior Name="%s" Frequency="0" Hidden="true">' % n, '    <NextBehaviorList Add="false">',
              '     <BehaviorReference Name="%s" Frequency="100"/>' % nx, "    </NextBehaviorList>", "   </Behavior>"]
    L.append('  <Condition Condition="#{mascot.environment.floor.isOn(mascot.anchor)}">')
    for n, f in FREQ:
        L.append('   <Behavior Name="%s" Frequency="%d">' % (n, f))
        L += nexts()
        L.append("   </Behavior>")
    L.append('   <Behavior Name="Land" Frequency="0" Hidden="true">')
    L += nexts()
    L += ["   </Behavior>", "  </Condition>",
          '  <Condition Condition="#{mascot.environment.wall.isOn(mascot.anchor)}">',
          '   <Behavior Name="GrabWall" Frequency="0" Hidden="true">', '    <NextBehaviorList Add="false">',
          '     <BehaviorReference Name="ClimbWall" Frequency="100"/>', '     <BehaviorReference Name="GrabWall" Frequency="30"/>',
          '     <BehaviorReference Name="Fall" Frequency="15"/>', "    </NextBehaviorList>", "   </Behavior>",
          '   <Behavior Name="ClimbWall" Frequency="0" Hidden="true">', '    <NextBehaviorList Add="false">',
          '     <Condition Condition="#{mascot.environment.ceiling.isOn(mascot.anchor)}"><BehaviorReference Name="GrabCeiling" Frequency="200"/></Condition>',
          '     <BehaviorReference Name="ClimbWall" Frequency="60"/>', '     <BehaviorReference Name="GrabWall" Frequency="30"/>',
          '     <BehaviorReference Name="Fall" Frequency="15"/>', "    </NextBehaviorList>", "   </Behavior>", "  </Condition>",
          '  <Condition Condition="#{mascot.environment.ceiling.isOn(mascot.anchor)}">',
          '   <Behavior Name="GrabCeiling" Frequency="0" Hidden="true">', '    <NextBehaviorList Add="false">',
          '     <BehaviorReference Name="ClimbCeiling" Frequency="100"/>', '     <BehaviorReference Name="GrabCeiling" Frequency="30"/>',
          '     <BehaviorReference Name="Fall" Frequency="15"/>', "    </NextBehaviorList>", "   </Behavior>",
          '   <Behavior Name="ClimbCeiling" Frequency="0" Hidden="true">', '    <NextBehaviorList Add="false">',
          '     <BehaviorReference Name="ClimbCeiling" Frequency="100"/>', '     <BehaviorReference Name="GrabCeiling" Frequency="30"/>',
          '     <BehaviorReference Name="Fall" Frequency="15"/>', "    </NextBehaviorList>", "   </Behavior>", "  </Condition>",
          " </BehaviorList>", "</Mascot>", ""]
    return "\n".join(L)


def export_set(args):
    name, out_dir = args
    spec = SETS[name]
    ims = [render_frame(dr) for dr in spec["fn"]()]
    bb = None
    for im in ims:
        b = im.getbbox()
        if b:
            bb = b if bb is None else (min(bb[0], b[0]), min(bb[1], b[1]), max(bb[2], b[2]), max(bb[3], b[3]))
    bb = (max(0, bb[0] - 2), max(0, bb[1] - 2), min(CW, bb[2] + 2), min(CH, bb[3] + 2))
    files = []
    for k, im in enumerate(ims):
        fn = "%s%02d.png" % (name, k)
        im.crop(bb).quantize(256, method=Image.Quantize.FASTOCTREE).save(os.path.join(out_dir, fn), optimize=True)
        files.append(fn)
    ax, ay = spec["anchor"]
    return name, dict(files=files, anchor=(int(round(ax - X0 - bb[0])), int(round(ay - Y0 - bb[1]))), d=spec["d"],
                      size=(bb[2] - bb[0], bb[3] - bb[1]))


def main(argv):
    base = os.path.dirname(HERE)
    out = os.path.join(base, "NhanVat", "CoLong")
    conf = os.path.join(out, "conf")
    os.makedirs(conf, exist_ok=True)
    names = [a for a in argv if a in SETS] or list(SETS)
    info_path = os.path.join(conf, "frames.json")
    info = {}
    if names == list(SETS):
        for f in os.listdir(out):
            if f.endswith(".png"):
                os.remove(os.path.join(out, f))
    elif os.path.exists(info_path):
        info = json.load(open(info_path, encoding="utf-8"))
    for n in names:                                          # xoá ảnh cũ của bộ sắp dựng lại (tránh sót khung thừa)
        for f in os.listdir(out):
            if f.startswith(n) and f[len(n):-4].isdigit():
                os.remove(os.path.join(out, f))
    jobs = [(n, out) for n in names]
    try:
        import multiprocessing as mp
        with mp.Pool(max(1, os.cpu_count() or 2)) as pool:
            res = pool.map(export_set, jobs)
    except Exception:
        res = [export_set(j) for j in jobs]
    for n, inf in res:
        info[n] = inf
        print("%-9s %3d khung  %dx%d" % (n, len(inf["files"]), inf["size"][0], inf["size"][1]))
    json.dump(info, open(info_path, "w", encoding="utf-8"), indent=0)
    hits = compute_hits()

    def at(k, ox=0.0, oy=0.0):
        return dict(dx=round(hits[k][0] + ox, 1), dy=round(hits[k][1] + oy, 1))
    META["freefly"] = {
        "bay": ["LuonVong"], "hov": ["LuonVong"], "takeoff": ["CatCanh"], "laugh": ["YeuThich"],
        "taunts": ["Grào! 🐉", "Rộp rộp~ ngon ghê!", "Cháy rồi kìa 🔥", "Quật cho một phát!", "Giật tê người chưa? ⚡",
                   "Của ta hết! Hehe", "Ôm chặt không cho chạy~"],
        "attacks": [dict(act="CanIcon", fx="bite", hit=[BITE_CHOMPS[0] / 36.0], w=1.3, **at("bite")),
                    dict(act="QuatDuoi", fx="shatter", hit=[14 / 30.0], w=1.2, **at("tail")),
                    dict(act="PhunLua", fx="burn", hit=[0.24], w=1.2, **at("fire")),
                    dict(act="PhunSamSet", fx="zap", hit=[0.38], w=1.0, **at("zap")),
                    dict(act="CuonThan", fx="squeeze", hit=[0.12], w=0.7, **at("coil"))],
    }
    print("điểm trúng icon:", {k: tuple(round(v) for v in p) for k, p in hits.items()})
    with open(os.path.join(conf, "actions.xml"), "w", encoding="utf-8") as f:
        f.write(build_actions_xml(info))
    with open(os.path.join(conf, "behaviors.xml"), "w", encoding="utf-8") as f:
        f.write(build_behaviors_xml())
    with open(os.path.join(conf, "chibi.json"), "w", encoding="utf-8") as f:
        json.dump(META, f, ensure_ascii=False, indent=1)
    print("Xong:", out)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--xem":
        print(preview(sys.argv[2].split(","), n=int(sys.argv[3]) if len(sys.argv) > 3 else 8))
    elif len(sys.argv) > 1 and sys.argv[1] == "--khung":
        sheet([key(n).im.resize((key(n).im.width * 2, key(n).im.height * 2)) for n in BOXES], "/tmp/co_long_khung.png", 1, cols=8)
    else:
        main(sys.argv[1:])
