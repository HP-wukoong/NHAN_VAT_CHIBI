#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tạo bộ nhân vật CỔ LONG (Hắc long thái cổ) cho Chibi Nhắc Việc.

Rồng được vẽ hoàn toàn bằng code theo khung xương (thân, cổ, đầu, hàm, 4 chân, 2 cánh, đuôi 12 đốt),
mỗi khung hình là một tư thế tính từ hàm sin / đường cong mượt nên chuyển động liền mạch, tự nhiên.
Chạy:  python tools/tao_co_long.py            -> ghi đè NhanVat/CoLong/
       python tools/tao_co_long.py Stand Walk -> chỉ vẽ lại vài động tác (xem nhanh)
"""
import json
import math
import os
import random
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter

SS = 3                                   # vẽ to gấp 3 rồi thu nhỏ cho mịn
X0, Y0, CW, CH = -360, -330, 640, 380    # khung vẽ (đơn vị = điểm ảnh ở cỡ gốc), mặt đất y = 0
HS = 1.3                                 # đầu to kiểu chibi

OUT = (10, 7, 14)
PAL = {
    "scale": ((40, 35, 52), (19, 16, 27), (88, 80, 116)),
    "far": ((26, 22, 35), (12, 10, 18), (54, 48, 70)),
    "belly": ((104, 80, 66), (66, 50, 44), (156, 124, 98)),
    "fbelly": ((70, 54, 46), (44, 33, 30), (100, 80, 66)),
    "horn": ((216, 202, 174), (140, 122, 102), (252, 246, 230)),
    "fhorn": ((150, 136, 116), (96, 84, 72), (186, 172, 150)),
    "memb": ((78, 30, 62), (44, 14, 36), (124, 60, 100)),
    "fmemb": ((50, 20, 42), (28, 9, 24), (78, 36, 64)),
    "spike": ((92, 80, 86), (52, 44, 50), (140, 126, 130)),
    "mouth": ((100, 12, 32), (60, 6, 20), (150, 40, 60)),
}
GLOW = (170, 80, 255)
GLOWC = (236, 205, 255)
EYE = {"gold": ((255, 200, 64), (255, 140, 20)), "red": ((255, 70, 50), (255, 20, 30)),
       "violet": ((230, 170, 255), (170, 70, 255)), "blue": ((180, 230, 255), (90, 160, 255))}


# ───────────────────────── toán nhỏ ─────────────────────────
def lerp(a, b, t):
    return a + (b - a) * t


def clamp01(t):
    return max(0.0, min(1.0, t))


def ss(t):                                   # smoothstep
    t = clamp01(t)
    return t * t * (3 - 2 * t)


def seg(i, a, b):                            # tiến độ 0..1 trong đoạn khung [a, b]
    return clamp01((i - a) / float(max(1, b - a)))


def rot(p, a, c=(0.0, 0.0)):
    """Xoay (độ). a > 0 = ngẩng mũi lên với rồng quay mặt sang trái."""
    r = math.radians(a)
    x, y = p[0] - c[0], p[1] - c[1]
    return (c[0] + x * math.cos(r) - y * math.sin(r), c[1] + x * math.sin(r) + y * math.cos(r))


def add(p, q, k=1.0):
    return (p[0] + q[0] * k, p[1] + q[1] * k)


def dirv(a):
    r = math.radians(a)
    return (math.cos(r), math.sin(r))


def dist(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


def catmull(pts, closed=True, n=5):
    out = []
    m = len(pts)
    rng = range(m) if closed else range(m - 1)
    for i in rng:
        p0 = pts[(i - 1) % m] if closed else pts[max(0, i - 1)]
        p1, p2 = pts[i], pts[(i + 1) % m]
        p3 = pts[(i + 2) % m] if closed else pts[min(m - 1, i + 2)]
        for k in range(n):
            t = k / float(n)
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in (0, 1)))
    if not closed:
        out.append(pts[-1])
    return out


def tube(center, radii, cap0=True, cap1=True):
    """Đường ống thuôn (cổ, đuôi, sừng, chi) -> đa giác kín."""
    n = len(center)
    L, R = [], []
    for i in range(n):
        p = center[i]
        a = center[max(0, i - 1)]
        b = center[min(n - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        d = math.hypot(dx, dy) or 1
        nx, ny = -dy / d, dx / d
        r = radii[i]
        L.append((p[0] + nx * r, p[1] + ny * r))
        R.append((p[0] - nx * r, p[1] - ny * r))
    out = list(L)
    if cap1 and radii[-1] > 0.8:
        p, q = center[-1], center[-2]
        a0 = math.degrees(math.atan2(L[-1][1] - p[1], L[-1][0] - p[0]))
        for k in range(1, 6):
            out.append(add(p, dirv(a0 - 180 * k / 6.0), radii[-1]))
    out += R[::-1]
    if cap0 and radii[0] > 0.8:
        p = center[0]
        a0 = math.degrees(math.atan2(R[0][1] - p[1], R[0][0] - p[0]))
        for k in range(1, 6):
            out.append(add(p, dirv(a0 - 180 * k / 6.0), radii[0]))
    return out


def bez(p0, p1, p2, n=10):
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]) for t in [i / float(n) for i in range(n + 1)]]


def ik(hip, foot, l1, l2, bend):
    """Khớp gối 2 đoạn. bend = +1 gối hướng ra sau (+x), -1 hướng ra trước."""
    dx, dy = foot[0] - hip[0], foot[1] - hip[1]
    d = math.hypot(dx, dy) or 0.01
    d2 = min(d, l1 + l2 - 0.05)
    a = (l1 * l1 + d2 * d2 - l2 * l2) / (2 * l1 * d2)
    a = math.acos(max(-1, min(1, a)))
    base = math.atan2(dy, dx)
    k1 = (hip[0] + l1 * math.cos(base + a), hip[1] + l1 * math.sin(base + a))
    k2 = (hip[0] + l1 * math.cos(base - a), hip[1] + l1 * math.sin(base - a))
    k = k1 if (k1[0] - k2[0]) * bend > 0 else k2
    if d > l1 + l2:
        foot = (hip[0] + dx / d * (l1 + l2), hip[1] + dy / d * (l1 + l2))
    return k, foot


# ───────────────────────── khung vẽ một hình ─────────────────────────
def _shift(M, dx, dy):
    N = Image.new("L", M.size, 0)
    N.paste(M, (dx, dy))
    return N


class Frame:
    def __init__(self, G=None):
        self.G = G or (0.0, (0.0, 0.0), False)     # (góc xoay, tâm, lật dọc) toàn thân
        size = (CW * SS, CH * SS)
        self.img = Image.new("RGBA", size, (0, 0, 0, 0))
        self.shadow = Image.new("RGBA", size, (0, 0, 0, 0))
        self.L = {k: Image.new("RGBA", size, (0, 0, 0, 0)) for k in ("bg", "bgg", "fg", "fgg", "dg")}
        self.D = {k: ImageDraw.Draw(v) for k, v in self.L.items()}
        self.dimg = ImageDraw.Draw(self.img)

    def g(self, p):
        x, y = p
        ang, piv, fl = self.G
        if fl:
            y = 2 * piv[1] - y
        if ang:
            x, y = rot((x, y), ang, piv)
        return x, y

    def c(self, p):
        x, y = self.g(p)
        return ((x - X0) * SS, (y - Y0) * SS)

    def cs(self, pts):
        return [self.c(p) for p in pts]

    # vẽ một bộ phận: tô màu nền + dải tối phía dưới-phải + viền sáng phía trên-trái + nét viền
    def part(self, poly, pal, smooth=True, ol=1.0, sh=0.30, hi=0.12, alpha=255, layer=None):
        pts = self.cs(catmull(poly) if smooth else poly)
        if len(pts) < 3:
            return
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        x0, y0 = int(min(xs)) - 3, int(min(ys)) - 3
        x1, y1 = int(max(xs)) + 4, int(max(ys)) + 4
        w, h = x1 - x0, y1 - y0
        if w <= 1 or h <= 1:
            return
        loc = [(x - x0, y - y0) for x, y in pts]
        M = Image.new("L", (w, h), 0)
        ImageDraw.Draw(M).polygon(loc, fill=255)
        area = 0.0
        per = 0.0
        for i in range(len(loc)):
            a, b = loc[i], loc[(i + 1) % len(loc)]
            area += a[0] * b[1] - b[0] * a[1]
            per += math.hypot(b[0] - a[0], b[1] - a[1])
        thick = max(2.0, 2 * abs(area) / 2.0 / max(1.0, per) * 2)
        s = max(SS, int(thick * sh))
        hp = max(SS - 1, int(thick * hi))
        shm = ImageChops.subtract(M, _shift(M, -s, -s))
        him = ImageChops.subtract(ImageChops.subtract(M, _shift(M, hp, hp)), shm)
        patch = Image.new("RGBA", (w, h), pal[0] + (255,))
        patch.paste(pal[1] + (255,), mask=shm)
        patch.paste(pal[2] + (255,), mask=him)
        if alpha < 255:
            M = M.point(lambda v: v * alpha // 255)
        patch.putalpha(M)
        tgt = layer if layer is not None else self.img
        tgt.alpha_composite(patch, (x0, y0))
        if ol:
            ImageDraw.Draw(tgt).line(pts + [pts[0]], fill=OUT + (255,), width=max(1, int(ol * SS)), joint="curve")

    def line(self, pts, col, w=1.0, layer=None):
        d = self.D[layer] if layer else self.dimg
        d.line(self.cs(pts), fill=col, width=max(1, int(w * SS)), joint="curve")

    def poly(self, pts, col, layer=None, outline=None, ow=1.0):
        d = self.D[layer] if layer else self.dimg
        d.polygon(self.cs(pts), fill=col)
        if outline:
            q = self.cs(pts)
            d.line(q + [q[0]], fill=outline, width=max(1, int(ow * SS)), joint="curve")

    def ell(self, c, rx, ry, fill=None, layer=None, outline=None, w=1.0):
        d = self.D[layer] if layer else self.dimg
        x, y = self.c(c)
        d.ellipse((x - rx * SS, y - ry * SS, x + rx * SS, y + ry * SS), fill=fill, outline=outline,
                  width=max(1, int(w * SS)) if outline else 0)

    def finish(self, blur=2.6):
        A = self.img.getchannel("A")
        bb = A.getbbox()
        out = Image.new("RGBA", self.img.size, (0, 0, 0, 0))

        def blurred(layer, r):
            b = layer.getbbox()
            if not b:
                return None
            m = int(r * SS * 3) + 2
            b = (max(0, b[0] - m), max(0, b[1] - m), min(layer.width, b[2] + m), min(layer.height, b[3] + m))
            return layer.crop(b).filter(ImageFilter.GaussianBlur(r * SS)), b

        for k in ("bgg",):
            r = blurred(self.L[k], blur)
            if r:
                out.alpha_composite(r[0], r[1][:2])
        out.alpha_composite(self.L["bg"])
        out.alpha_composite(self.shadow)
        if bb:                                           # quầng hắc khí tím mờ + viền ngoài dày quanh con rồng
            m = SS * 8
            b = (max(0, bb[0] - m), max(0, bb[1] - m), min(A.width, bb[2] + m), min(A.height, bb[3] + m))
            au = A.crop(b).filter(ImageFilter.MaxFilter(2 * SS + 1)).filter(ImageFilter.GaussianBlur(SS * 2.2))
            au = au.point(lambda v: v * 95 // 255)
            aura = Image.new("RGBA", au.size, (120, 60, 200, 255))
            aura.putalpha(au)
            out.alpha_composite(aura, b[:2])
            m = SS * 3
            b = (max(0, bb[0] - m), max(0, bb[1] - m), min(A.width, bb[2] + m), min(A.height, bb[3] + m))
            dil = A.crop(b).filter(ImageFilter.MaxFilter(2 * SS + 1))
            ol = Image.new("RGBA", dil.size, OUT + (255,))
            ol.putalpha(dil)
            out.alpha_composite(ol, b[:2])
            out.alpha_composite(self.img)
        r = blurred(self.L["dg"], 1.6)
        if r:
            out.alpha_composite(r[0], r[1][:2])
            out.alpha_composite(r[0], r[1][:2])
        r = blurred(self.L["fgg"], blur)
        if r:
            out.alpha_composite(r[0], r[1][:2])
        out.alpha_composite(self.L["fg"])
        return out.resize((CW, CH), Image.LANCZOS)


# ───────────────────────── tư thế ─────────────────────────
DEF = dict(
    bx=0.0, by=-36.0, brot=0.0, bsx=1.0, bsy=1.0,
    hx=-20.0, hy=-34.0, hrot=0.0, jaw=0.0, eye=1.0, emo="angry", eyecol="gold", pupil=(0.0, 0.0), hflip=False,
    wing=0.05, flap=0.0, fwing=None, fflap=None,
    tail=30.0, tcurl=-7.5, twave=5.0, tph=0.0,
    fF=(-15.0, 0.0), fFf=(-15.0, 0.0), fH=(17.0, 0.0), fHf=(17.0, 0.0), feet_rel=False,
    glow=0.3, G=None, shadow=1.0, tears=0.0, blush=0.0, sparkle=0.0, smoke=0.0,
)
FO = (6.0, -3.0)          # chân / cánh phía xa lệch ra sau-lên một chút để có chiều sâu


def pose(**kw):
    P = dict(DEF)
    P.update(kw)
    return P


def geometry(P):
    J = {}
    a = P["brot"]
    bx, by = P["bx"], P["by"]

    def B(lx, ly):
        return add(rot((lx * P["bsx"], ly * P["bsy"]), a), (bx, by))
    J["B"] = B
    J["body_c"] = (bx, by)
    J["chest"] = B(-23, -8)
    J["shoulder"] = B(-4, -14)
    J["wing_back"] = B(20, -10)
    J["tail_root"] = B(24, -2)
    J["hipF"], J["hipH"] = B(-16, 9), B(16, 8)
    # đầu
    off = rot((P["hx"], P["hy"]), a * 0.5)
    hc = add(J["chest"], off)
    J["hc"] = hc
    hang = P["hrot"] + a * 0.5
    J["hang"] = hang

    def Hp(lx, ly, jaw=False):
        if jaw:
            lx, ly = rot((lx, ly), -P["jaw"] * 34, (9, 4))
        x, y = lx * HS, ly * HS
        if P["hflip"]:
            y = -y
        return add(rot((x, y), hang), hc)
    J["H"] = Hp
    J["mouth"] = Hp(-38, 3 + P["jaw"] * 4)
    J["mouth_in"] = Hp(-26, 5)
    J["nostril"] = Hp(-37, -3)
    J["eye"] = Hp(-12, -8)
    J["horn_tip"] = Hp(39, -44)
    J["neck_top"] = Hp(10, 6)
    J["scruff"] = Hp(16, -2)
    # đuôi
    n = 12
    pts = [J["tail_root"]]
    rads = []
    ang = P["tail"] + a
    for i in range(n):
        k = i / float(n)
        ai = ang + P["tcurl"] * i + P["twave"] * math.sin(P["tph"] - 0.55 * i) * (0.35 + k)
        p = add(pts[-1], dirv(ai), 7.6)
        pts.append(p)
    for i, p in enumerate(pts):
        k = i / float(n)
        r = 11.5 * (1 - k) ** 0.85 + 1.6
        rads.append(r)
        if P["G"] is None and p[1] > -r * 0.55:                      # đuôi nằm trên mặt đất
            pts[i] = (p[0], -r * 0.55)
    J["tail"], J["trad"] = pts, rads
    J["tail_tip"] = pts[-1]
    # chân
    legs = {}
    for key, hip, far, l1, l2, bend in (("fF", J["hipF"], False, 14, 14, 1), ("fFf", J["hipF"], True, 14, 14, 1),
                                        ("fH", J["hipH"], False, 15, 14, -1), ("fHf", J["hipH"], True, 15, 14, -1)):
        h = add(hip, FO) if far else hip
        f = P[key]
        if P["feet_rel"]:
            f = add(h, f)
        elif far:
            f = add(f, FO)
        k, f2 = ik(h, f, l1, l2, bend)
        legs[key] = (h, k, f2)
    J["legs"] = legs
    J["paw"] = legs["fF"][2]
    # cánh
    J["wings"] = {}
    for far in (True, False):
        s = P["fwing"] if (far and P["fwing"] is not None) else P["wing"]
        fl = P["fflap"] if (far and P["fflap"] is not None) else P["flap"]
        root = add(J["shoulder"], FO) if far else J["shoulder"]
        hum = lerp(-72, -100, s) + fl + a
        fore = lerp(-8, -58, s) + fl * 0.7 + a
        fing = [lerp(20, -92, s), lerp(32, -56, s), lerp(44, -22, s), lerp(56, 10, s)]
        lens = [lerp(26, 52, s), lerp(23, 48, s), lerp(20, 42, s), lerp(16, 32, s)]
        E = add(root, dirv(hum), lerp(13, 19, s))
        Wr = add(E, dirv(fore), lerp(14, 28, s))
        tips = [add(Wr, dirv(f + fl * 0.45 + a), L) for f, L in zip(fing, lens)]
        back = add(J["wing_back"], FO) if far else J["wing_back"]
        J["wings"][far] = (root, E, Wr, tips, back)
    return J


# ───────────────────────── vẽ rồng ─────────────────────────
def draw_wing(F, J, far):
    root, E, Wr, tips, back = J["wings"][far]
    pal = PAL["fmemb"] if far else PAL["memb"]
    mem = [root, E, Wr, tips[0]]
    seq = tips + [back]
    for i in range(len(seq) - 1):
        a, b = seq[i], seq[i + 1]
        m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        m = (lerp(m[0], Wr[0], 0.2), lerp(m[1], Wr[1], 0.2))
        mem.append(m)
        mem.append(b)
    F.part(mem, pal, smooth=False, sh=0.12, hi=0.05, ol=0.8)
    bone = PAL["far"][0] if far else PAL["scale"][0]
    for t in tips:                                               # xương ngón cánh
        F.line([Wr, t], OUT + (255,), 2.4)
        F.line([Wr, t], bone + (255,), 1.3)
    F.part(tube([root, E, Wr], [4.2, 3.2, 2.8]), PAL["far"] if far else PAL["scale"], smooth=False, ol=0.8)
    hc = PAL["fhorn"] if far else PAL["horn"]
    cl = add(Wr, dirv(J["hang"] - 120), 0.0)
    F.part([add(Wr, (-1.5, 0)), add(Wr, (1.5, 0)), add(Wr, (-3, -6))], hc, smooth=False, ol=0.6)
    for t in tips:
        F.part([add(t, (-1.2, 0)), add(t, (1.2, 0)), add(t, (0.5, 3.5))], hc, smooth=False, ol=0.5)


def draw_leg(F, J, key, far):
    h, k, f = J["legs"][key]
    hind = key.startswith("fH")
    pal = PAL["far"] if far else PAL["scale"]
    r0, r1, r2 = (12.0, 7.5, 5.2) if hind else (9.5, 6.5, 5.0)
    F.part(tube([h, k], [r0, r1]), pal, smooth=False, ol=0.9)
    F.part(tube([k, f], [r1 * 0.95, r2]), pal, smooth=False, ol=0.9)
    fx, fy = f
    foot = [(fx + 5, fy - 1), (fx + 4, fy - 6), (fx - 3, fy - 7.5), (fx - 9, fy - 4), (fx - 10, fy - 0.5), (fx + 5, fy - 0.2)]
    F.part(foot, pal, ol=0.9)
    hc = PAL["fhorn"] if far else PAL["horn"]
    for i, (cx, cy) in enumerate(((fx - 10, fy - 1.0), (fx - 8, fy - 4.2), (fx - 4.5, fy - 6.5))):
        F.part([(cx + 1.6, cy - 1.4), (cx + 1.6, cy + 1.2), (cx - 3.2, cy + 1.0)], hc, smooth=False, ol=0.5)


def draw_tail(F, J, P):
    pts, rads = J["tail"], J["trad"]
    pal = PAL["scale"]
    n = len(pts)
    for i in range(1, n - 1, 2):                                 # gai lưng đuôi
        a, b = pts[i - 1], pts[i + 1]
        d = math.hypot(b[0] - a[0], b[1] - a[1]) or 1
        tx, ty = (b[0] - a[0]) / d, (b[1] - a[1]) / d
        nx, ny = ty, -tx
        r = rads[i]
        hgt = 4 + 5.5 * (1 - i / float(n))
        base1 = (pts[i][0] + nx * r * 0.8 - tx * 3, pts[i][1] + ny * r * 0.8 - ty * 3)
        base2 = (pts[i][0] + nx * r * 0.8 + tx * 3, pts[i][1] + ny * r * 0.8 + ty * 3)
        tip = (pts[i][0] + nx * (r + hgt) + tx * 3.5, pts[i][1] + ny * (r + hgt) + ty * 3.5)
        F.part([base1, tip, base2], PAL["spike"], smooth=False, ol=0.6)
    F.part(tube(pts, rads, cap1=False), pal, smooth=False, ol=1.0, sh=0.32)
    a, b = pts[-2], pts[-1]                                      # lưỡi đao cuối đuôi
    d = dist(a, b) or 1
    tx, ty = (b[0] - a[0]) / d, (b[1] - a[1]) / d
    nx, ny = ty, -tx
    blade = [(b[0] + nx * 2, b[1] + ny * 2), (b[0] + nx * 7 + tx * 3, b[1] + ny * 7 + ty * 3),
             (b[0] + tx * 13, b[1] + ty * 13), (b[0] - nx * 7 + tx * 3, b[1] - ny * 7 + ty * 3), (b[0] - nx * 2, b[1] - ny * 2)]
    F.part(blade, PAL["spike"], smooth=False, ol=0.8)
    J["tail_tip"] = (b[0] + tx * 13, b[1] + ty * 13)


def draw_body(F, J, P):
    B = J["B"]
    for k in range(7):                                           # gai lưng
        th = math.radians(198 + k * 19)
        p = B(30 * math.cos(th), 21 * math.sin(th))
        nrm = rot((math.cos(th), math.sin(th) * 1.4), P["brot"])
        d = math.hypot(*nrm) or 1
        nx, ny = nrm[0] / d, nrm[1] / d
        tx, ty = -ny, nx
        hgt = 7.5 if 1 <= k <= 4 else 5.5
        F.part([(p[0] - tx * 3.8 - nx, p[1] - ty * 3.8 - ny), (p[0] + nx * hgt + 2.5, p[1] + ny * hgt),
                (p[0] + tx * 3.8 - nx, p[1] + ty * 3.8 - ny)], PAL["spike"], smooth=False, ol=0.6)
    body = []
    for k in range(28):
        th = 2 * math.pi * k / 28
        x, y = 30 * math.cos(th), 21 * math.sin(th)
        if x < 0:
            x *= 1.06
            y *= 1.05
        body.append(B(x, y))
    F.part(body, PAL["scale"], smooth=True, ol=1.0, sh=0.26)
    # bụng giáp vảy
    outer = [B(30 * 1.0 * math.cos(math.radians(t)), 21 * math.sin(math.radians(t))) for t in range(30, 172, 14)]
    inner = [B(25 * math.cos(math.radians(t)), 4 + 12 * math.sin(math.radians(t))) for t in range(170, 28, -14)]
    F.part(outer + inner, PAL["belly"], smooth=False, ol=0.7, sh=0.35)
    for t in range(44, 170, 18):
        F.line([B(29.5 * math.cos(math.radians(t)), 20.5 * math.sin(math.radians(t))),
                B(25.5 * math.cos(math.radians(t)), 4 + 12.5 * math.sin(math.radians(t)))], PAL["belly"][1] + (255,), 0.8)
    # vảy lớn trên lưng
    for (lx, ly) in ((-12, -12), (0, -15), (12, -12), (-4, -4), (8, -3)):
        F.line([B(lx - 4, ly + 1), B(lx, ly - 2), B(lx + 4, ly + 1)], PAL["scale"][1] + (255,), 0.8)
    runes(F, J, P)


def runes(F, J, P):
    g = P["glow"]
    if g <= 0.02:
        return
    B = J["B"]
    al = int(255 * min(1.0, g))
    glyphs = [[(-17, -3), (-12, -8), (-7, -4), (-9, 0)], [(-3, -9), (3, -6), (8, -10)], [(10, -4), (14, -8), (19, -5)],
              [(-2, 0), (3, -3)]]
    for gl in glyphs:
        pts = [B(*p) for p in gl]
        F.line(pts, GLOW + (al,), 2.6 + 2 * g, layer="dg")
        F.line(pts, GLOWC + (al,), 0.7)


def draw_neck(F, J, P):
    ch, top = J["chest"], J["neck_top"]
    mid = ((ch[0] + top[0]) / 2 - 5, (ch[1] + top[1]) / 2 + 1)
    c = bez(ch, mid, top, 8)
    rad = [lerp(13.5, 10.5, i / 8.0) for i in range(9)]
    F.part(tube(c, rad), PAL["scale"], smooth=False, ol=1.0, sh=0.3)
    th = []                                                       # họng giáp vảy
    for i, p in enumerate(c[1:-1], 1):
        a, b = c[i - 1], c[i + 1]
        d = dist(a, b) or 1
        nx, ny = -(b[1] - a[1]) / d, (b[0] - a[0]) / d
        if nx > 0:
            nx, ny = -nx, -ny
        th.append(add(p, (nx, ny), rad[i] * 0.5))
    F.part(tube(th, [rad[i] * 0.5 for i in range(1, len(th) + 1)]), PAL["belly"], smooth=False, ol=0.6, sh=0.35)
    for p in th[1::2]:
        F.line([add(p, (-3, -1)), add(p, (3, 1))], PAL["belly"][1] + (255,), 0.7)
    for i in (2, 5):                                              # gai cổ
        p = c[i]
        a, b = c[i - 1], c[i + 1]
        d = dist(a, b) or 1
        nx, ny = -(b[1] - a[1]) / d, (b[0] - a[0]) / d
        if nx < 0:
            nx, ny = -nx, -ny
        base = add(p, (nx, ny), rad[i] * 0.85)
        F.part([add(base, (-(b[0] - a[0]) / d * 3, -(b[1] - a[1]) / d * 3)), add(base, (nx + 0.6, ny), 6.5),
                add(base, ((b[0] - a[0]) / d * 3, (b[1] - a[1]) / d * 3))], PAL["spike"], smooth=False, ol=0.6)


def horn(F, Hp, pts, rads, pal):
    F.part(tube([Hp(*p) for p in pts], rads), pal, smooth=False, ol=0.8, sh=0.35)


def draw_head(F, J, P):
    Hp = J["H"]
    emo = P["emo"]
    # sừng phía xa (sau đầu)
    horn(F, lambda x, y: Hp(x + 3, y - 1), [(5, -15), (18, -24), (29, -33), (35, -44), (34, -55)],
         [4.6, 4.0, 3.0, 1.9, 0.5], PAL["fhorn"])
    # trong miệng
    if P["jaw"] > 0.04:
        up = [Hp(-38, 2), Hp(-22, 3.5), Hp(-8, 4), Hp(7, 4.5)]
        lo = [Hp(x, y, jaw=True) for x, y in ((7, 4.5), (-8, 4.6), (-22, 4.8), (-35, 5.2))]
        F.poly(up + lo, PAL["mouth"][1] + (255,))
        tg = [Hp(x, y, jaw=True) for x, y in ((4, 5), (-10, 4), (-22, 4.4), (-24, 6), (-10, 7), (4, 7))]
        F.part(tg, ((190, 60, 80), (130, 30, 50), (240, 120, 130)), ol=0.5)
        for x in (-34, -27, -20, -13, -6):                        # răng dưới
            b1, b2 = Hp(x - 1.5, 4.8, jaw=True), Hp(x + 1.5, 4.8, jaw=True)
            tip = Hp(x - 0.3, 1.8 if x != -27 else 0.2, jaw=True)
            F.part([b1, tip, b2], PAL["horn"], smooth=False, ol=0.45)
    # hàm dưới
    jaw = [(12, 3), (0, 4), (-14, 4.5), (-32, 4.5), (-37, 6), (-34, 9.5), (-20, 11), (-6, 11), (6, 9.5), (13, 6)]
    F.part([Hp(x, y, jaw=True) for x, y in jaw], PAL["scale"], ol=0.9, sh=0.3)
    F.part([Hp(x, y, jaw=True) for x, y in ((-30, 8.5), (-18, 10.2), (-4, 10.2), (6, 8.8), (-4, 8), (-18, 8))],
           PAL["belly"], ol=0.0, sh=0.3)
    # sọ + mõm
    skull = [(17, -4), (16, -11), (9, -17), (0, -19.5), (-10, -17.5), (-19, -14), (-29, -11), (-37, -7), (-41, -3),
             (-41, 1.2), (-35, 3), (-22, 3.5), (-8, 4), (4, 6), (13, 5)]
    F.part([Hp(*p) for p in skull], PAL["scale"], ol=1.0, sh=0.26, hi=0.1)
    for x, y in ((-6, -15), (2, -16.5), (-14, -13)):              # vảy đỉnh đầu
        F.line([Hp(x - 3, y + 1.5), Hp(x, y - 0.5), Hp(x + 3, y + 1.5)], PAL["scale"][1] + (255,), 0.8)
    # răng nanh trên
    for x, ln in ((-34, 4.2), (-28, 2.6), (-21, 4.8), (-14, 2.4), (-7, 2.2)):
        F.part([Hp(x - 1.6, 3.2), Hp(x + 1.6, 3.6), Hp(x - 0.2, 3.4 + ln)], PAL["horn"], smooth=False, ol=0.45)
    # sừng mũi, sừng nhỏ, gai má
    horn(F, Hp, [(-30, -10), (-30.5, -14), (-28, -18.5)], [2.5, 1.5, 0.4], PAL["horn"])
    horn(F, Hp, [(14, -8), (22, -10.5), (29, -12), (34, -16.5)], [3.2, 2.6, 1.7, 0.5], PAL["horn"])
    horn(F, Hp, [(12, 6.5), (19, 9.5), (25, 10)], [3.0, 1.9, 0.4], PAL["horn"])
    for p in ((17, -2), (18, 3)):
        F.part([Hp(p[0], p[1] - 2.2), Hp(p[0] + 7, p[1] + 0.5), Hp(p[0], p[1] + 2.2)], PAL["spike"], smooth=False, ol=0.5)
    # lỗ mũi
    F.ell(Hp(-37, -3), 1.6 * HS, 1.0 * HS, fill=(8, 4, 10, 255))
    draw_eye(F, J, P)
    # sừng chính phía gần
    horn(F, Hp, [(5, -15), (16, -21.5), (27, -27), (35, -35), (38.5, -45)], [5.0, 4.4, 3.4, 2.1, 0.5], PAL["horn"])
    for k, (x, y) in enumerate(((16, -21.5), (25, -26.5), (32, -33))):     # vân sừng
        F.line([Hp(x - 1.5, y - 3.4), Hp(x + 1.8, y + 3.2)], PAL["horn"][1] + (255,), 0.7)
    if P["blush"] > 0:
        F.ell(Hp(-20, -1), 4.5 * HS, 2 * HS, fill=(255, 90, 150, int(140 * P["blush"])), layer="dg")


def draw_eye(F, J, P):
    Hp = J["H"]
    emo = P["emo"]
    op = clamp01(P["eye"])
    col, gcol = EYE.get(P["eyecol"], EYE["gold"])
    px, py = P["pupil"]
    if emo in ("happy", "laugh") or op <= 0.06:
        if emo in ("happy", "laugh"):
            arc = [Hp(-19, -6.5), Hp(-15, -10), Hp(-10, -11), Hp(-5, -8.5)]
        else:
            arc = [Hp(-19, -7), Hp(-12, -6.2), Hp(-5, -7.6)]
        F.line(arc, OUT + (255,), 1.6)
        F.line(arc, col + (255,), 0.6)
    elif emo == "beg":
        c = Hp(-12, -8.5)
        r = 5.6 * HS
        F.ell(c, r, r * op, fill=OUT + (255,))
        F.ell(c, r - 0.8 * HS, (r - 0.8 * HS) * op, fill=col + (255,))
        F.ell(add(c, (px, py + 0.6)), 4.0 * HS, 4.2 * HS * op, fill=(40, 12, 24, 255))
        F.ell(add(c, (-1.8 * HS, -2.0 * HS)), 1.5 * HS, 1.5 * HS, fill=(255, 255, 255, 255))
        F.ell(add(c, (1.6 * HS, 1.4 * HS)), 0.8 * HS, 0.8 * HS, fill=(255, 255, 255, 255))
        F.ell(c, r * 1.3, r * 1.3 * op, fill=gcol + (110,), layer="dg")
    else:
        cy = -8.2
        top = [(-20, -6.3), (-15, -10.6), (-8, -11.4), (-3.8, -9.6)]
        bot = [(-5.6, -6.6), (-13, -5.0), (-20, -6.3)]
        if emo == "sad":
            top = [(-20, -8.0), (-15, -10.8), (-8, -10.6), (-4, -7.6)]
        if emo == "shock":
            top = [(-20, -6.8), (-15, -11.6), (-8, -12), (-4, -9.4)]
            bot = [(-5, -5.4), (-13, -4.2), (-20, -6.8)]
        pts = [(x, cy + (y - cy) * op) for x, y in top + bot]
        F.poly([Hp(*p) for p in catmull(pts)], col + (255,), outline=OUT + (255,), ow=0.9)
        if emo == "shock":
            F.ell(Hp(-12 + px, -8.4 + py), 1.0 * HS, 1.0 * HS * op, fill=(20, 6, 10, 255))
        elif emo != "dizzy":
            F.poly([Hp(-12 + px, -11.2 * op + cy * (1 - op) + 0.6 + py), Hp(-10.6 + px, -8.2 + py),
                    Hp(-12 + px, -5.2 * op + cy * (1 - op) - 0.2 + py), Hp(-13.4 + px, -8.2 + py)], (20, 6, 10, 255))
            F.ell(Hp(-14.5, -9.5), 0.8 * HS, 0.8 * HS * op, fill=(255, 250, 230, 255))
        else:
            for k in range(3):
                F.ell(Hp(-12, -8.3), (3.2 - k) * HS, (2.0 - k * 0.6) * HS * op, outline=(20, 6, 10, 255), w=0.5)
        F.ell(Hp(-12, -8.4), 9 * HS * 0.8, 5 * HS * 0.8 * max(0.3, op), fill=gcol + (150,), layer="dg")
    # mày gờ xương
    if emo in ("sad", "beg"):
        brow = [(-22, -15.5), (-12, -15), (-2, -12.8), (-2, -10.8), (-12, -12.4), (-21, -12.8)]
    elif emo in ("happy", "laugh"):
        brow = [(-22, -14.5), (-12, -16), (-2, -15), (-1.5, -13), (-12, -13.6), (-21, -12)]
    else:
        brow = [(-23, -10.8), (-14, -14.8), (-3, -16), (-0.5, -13), (-12, -11), (-21, -8.6)]
    F.part([Hp(*p) for p in brow], PAL["scale"], ol=0.8, sh=0.35)
    if P["tears"] > 0:
        t = P["tears"]
        c = Hp(-8, -5)
        F.ell(c, 1.6 * HS, 1.4 * HS, fill=(150, 220, 255, int(230 * t)))


def draw_shadow(F, J, P):
    if P["shadow"] <= 0 or P["G"] is not None:
        return
    lift = max(0.0, -36 - P["by"])
    k = P["shadow"] * max(0.35, 1 - lift / 120.0)
    x = P["bx"] + 4
    rx, ry = 46 * k, 5.5 * k
    d = ImageDraw.Draw(F.shadow)
    cx, cy = F.c((x, 0))
    d.ellipse((cx - rx * SS, cy - ry * SS, cx + rx * SS, cy + ry * SS), fill=(0, 0, 0, int(80 * k)))


def render(P, fx=None, t=0, extra=None):
    G = P["G"]
    F = Frame(G)
    J = geometry(P)
    F.J = J
    draw_shadow(F, J, P)
    if fx:
        fx(F, J, P, "back")
    draw_wing(F, J, True)
    draw_leg(F, J, "fHf", True)
    draw_leg(F, J, "fFf", True)
    draw_tail(F, J, P)
    draw_body(F, J, P)
    draw_leg(F, J, "fH", False)
    draw_neck(F, J, P)
    draw_wing(F, J, False)
    draw_leg(F, J, "fF", False)
    draw_head(F, J, P)
    if fx:
        fx(F, J, P, "front")
    return F.finish(), J




# ───────────────────────── khung khoá (keyframe) ─────────────────────────
def _lv(a, b, t):
    if isinstance(a, tuple):
        return tuple(lerp(x, y, t) for x, y in zip(a, b))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return lerp(a, b, t)
    return b if t >= 0.5 else a


def kf(i, keys):
    if i <= keys[0][0]:
        return keys[0][1]
    for (f0, v0), (f1, v1) in zip(keys, keys[1:]):
        if i <= f1:
            return _lv(v0, v1, ss((i - f0) / float(max(1e-6, f1 - f0))))
    return keys[-1][1]


def anim(i, spec, **extra):
    d = {k: kf(i, v) for k, v in spec.items()}
    d.update(extra)
    return d


def blink(i, at, ln=3):
    seq = (0.45, 0.0, 0.5) if ln == 3 else (0.6, 0.2, 0.0, 0.0, 0.3, 0.75)
    k = i - at
    return seq[k] if 0 <= k < len(seq) else 1.0


def gait(u, stance, S, lift):
    u %= 1.0
    if u < stance:
        return (S * (u / stance - 0.5), 0.0)
    s = (u - stance) / (1 - stance)
    return (S * (0.5 - ss(s)), -lift * math.sin(math.pi * s))


def shake(i, amp, seed=0):
    r = random.Random(i * 7919 + seed)
    return (r.uniform(-amp, amp), r.uniform(-amp, amp))


# ───────────────────────── hiệu ứng ─────────────────────────
def jag(p0, p1, n, amp, rnd):
    pts = [p0]
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy) or 1
    nx, ny = -dy / L, dx / L
    for k in range(1, n):
        t = k / float(n)
        j = rnd.uniform(-1, 1) * amp
        pts.append((p0[0] + dx * t + nx * j, p0[1] + dy * t + ny * j))
    pts.append(p1)
    return pts


def zap(F, pts, w, al=1.0, g=(90, 140, 255), m=(200, 225, 255), back=False):
    al = clamp01(al)
    L1, L2 = ("bgg", "bg") if back else ("fgg", "fg")
    F.line(pts, g + (int(210 * al),), w * 3.4, layer=L1)
    F.line(pts, m + (int(255 * al),), w, layer=L2)
    F.line(pts, (255, 255, 255, int(255 * al)), max(0.4, w * 0.4), layer=L2)


def puff(F, c, r, al, col=(110, 100, 128), back=False):
    F.ell(c, r, r * 0.85, fill=col + (int(210 * clamp01(al)),), layer="bgg" if back else "fgg")


def dust(F, c, r, al, back=False):
    al = clamp01(al)
    F.ell(c, r * 1.2, r * 0.6, fill=(150, 140, 132, int(150 * al)), layer="bgg" if back else "fgg")
    F.ell(c, r * 0.8, r * 0.4, fill=(170, 160, 150, int(120 * al)), layer="bg" if back else "fg")


def flame(F, c, r, al, hot=0.0, back=False, col=(150, 60, 255)):
    al = clamp01(al)
    G, C = ("bgg", "bg") if back else ("fgg", "fg")
    F.ell(c, r * 1.8, r * 1.8, fill=col + (int(170 * al),), layer=G)
    F.ell(c, r, r, fill=(col[0] - 20, col[1] - 20, col[2] - 30, int(235 * al)), layer=C)
    F.ell(c, r * 0.74, r * 0.74, fill=(14, 5, 24, int(240 * al)), layer=C)
    if hot > 0:
        F.ell(c, r * 0.4 * hot, r * 0.4 * hot, fill=(240, 215, 255, int(255 * al)), layer=C)


def tongue(F, base, r, h, al, back=False, col=(160, 70, 255), lean=0.0):
    """Lưỡi lửa hình giọt ngược: tròn ở gốc, nhọn bốc lên."""
    al = clamp01(al)
    G, C = ("bgg", "bg") if back else ("fgg", "fg")

    def shape(k):
        pts = [add(base, dirv(a), r * k) for a in range(-10, 200, 30)]
        tip = (base[0] + lean * h, base[1] - h * k - r * 0.3)
        mid_l = (base[0] - r * k * 0.9 + lean * h * 0.4, base[1] - h * 0.45 * k)
        mid_r = (base[0] + r * k * 0.9 + lean * h * 0.6, base[1] - h * 0.45 * k)
        return catmull([mid_r] + pts + [mid_l, tip], closed=True, n=3)
    F.poly(shape(1.25), col + (int(150 * al),), layer=G)
    F.poly(shape(1.0), (col[0] - 10, col[1] - 15, col[2], int(235 * al)), layer=C)
    F.poly(shape(0.5), (40, 10, 70, int(235 * al)), layer=C)
    F.poly(shape(0.22), (235, 205, 255, int(200 * al)), layer=C)


def arc_pts(c, rx, ry, a0, a1, n=16):
    return [(c[0] + rx * math.cos(math.radians(a0 + (a1 - a0) * k / n)),
             c[1] + ry * math.sin(math.radians(a0 + (a1 - a0) * k / n))) for k in range(n + 1)]


def sound_ring(F, c, ang, r, al, col=(200, 170, 255)):
    pts = arc_pts(c, r, r * 1.1, ang - 62, ang + 62)
    F.line(pts, col + (int(170 * al),), 3.2, layer="fgg")
    F.line(pts, (255, 245, 255, int(230 * al)), 1.0, layer="fg")


def crescent(F, path, w, al, col=GLOW, core=(255, 250, 255)):
    n = len(path)
    if n < 3:
        return
    rads = [w * math.sin(math.pi * k / (n - 1)) + 0.2 for k in range(n)]
    poly = tube(path, rads, False, False)
    F.poly(poly, col + (int(190 * al),), layer="fgg")
    F.poly(poly, (col[0], col[1], col[2], int(200 * al)), layer="fg")
    F.poly(tube(path, [r * 0.45 for r in rads], False, False), core + (int(255 * al),), layer="fg")


def rock(F, c, sz, ang, al=1.0):
    pts = [add(c, dirv(ang + k * 72 + (k % 2) * 18), sz * (0.75 + 0.3 * (k % 3) / 2.0)) for k in range(5)]
    F.poly(pts, (88, 78, 84, int(255 * al)), layer="fg", outline=OUT + (int(255 * al),), ow=0.6)


def crack(F, x0, dirn, ln, rnd, al):
    pts = [(x0, -0.6)]
    x = x0
    while abs(x - x0) < ln:
        x += dirn * rnd.uniform(5, 10)
        pts.append((x, -0.6 + rnd.uniform(-2.2, 1.0)))
    F.line(pts, (190, 90, 255, int(230 * al)), 5.0, layer="bgg")
    F.line(pts, (20, 8, 26, int(255 * al)), 2.2, layer="bg")
    F.line(pts, (235, 200, 255, int(255 * al)), 0.8, layer="bg")
    for k in range(2, len(pts) - 1, 3):                         # nhánh nứt
        q = pts[k]
        e = (q[0] + rnd.uniform(-6, 6), q[1] - rnd.uniform(2, 6))
        F.line([q, e], (20, 8, 26, int(255 * al)), 1.2, layer="bg")


def letter_z(F, c, s, al):
    pts = [(c[0] - s, c[1] - s), (c[0] + s, c[1] - s), (c[0] - s, c[1] + s), (c[0] + s, c[1] + s)]
    F.line(pts, (160, 120, 255, int(160 * al)), s * 0.9, layer="fgg")
    F.line(pts, (240, 230, 255, int(255 * al)), max(0.6, s * 0.3), layer="fg")


def sparkle(F, c, r, al, col=(255, 240, 180)):
    pts = []
    for k in range(8):
        rr = r if k % 2 == 0 else r * 0.3
        pts.append(add(c, dirv(k * 45 - 90), rr))
    F.poly(pts, col + (int(255 * al),), layer="fg")
    F.ell(c, r * 0.9, r * 0.9, fill=col + (int(120 * al),), layer="fgg")


def droplet(F, c, r, al):
    F.poly([add(c, (0, -r * 1.6)), add(c, (r, 0)), add(c, (0, r)), add(c, (-r, 0))], (150, 215, 255, int(240 * al)),
           layer="fg", outline=(40, 90, 160, int(200 * al)), ow=0.4)


# ───────────────────────── các bộ khung chuyển động ─────────────────────────
TAU = 2 * math.pi
SETS = {}


def defset(name, d=1, anchor=(0.0, 0.0)):
    def deco(fn):
        SETS[name] = dict(fn=fn, d=d, anchor=anchor)
        return fn
    return deco


def breath_base(i, T, k=1.0):
    w = TAU * i / T
    return dict(by=-36 + 0.9 * k * math.sin(w), bsy=1 + 0.015 * k * math.sin(w), bsx=1 - 0.01 * k * math.sin(w),
                hy=-34 + 1.3 * k * math.sin(w - 0.7), hrot=1.5 * k * math.sin(w - 1.0), tph=w, tail=30 + 2.5 * math.sin(w),
                flap=3 * math.sin(w - 0.5))


@defset("stand", d=2)
def S_stand():
    T = 32
    return [(pose(eye=blink(i, 22), **breath_base(i, T)), None) for i in range(T)]


@defset("standb", d=2)
def S_standb():
    T = 40
    out = []
    for i in range(T):
        b = breath_base(i, T)
        b["hrot"] += kf(i, [(0, 0), (7, 15), (14, 15), (18, -5), (27, -5), (34, 0)])
        px = kf(i, [(0, (0.0, 0.0)), (7, (-1.0, -1.2)), (14, (-0.5, -1.0)), (18, (1.2, 0.3)), (27, (1.2, 0.3)), (34, (0.0, 0.0))])
        jaw = kf(i, [(0, 0), (19, 0), (21, 0.14), (25, 0.0)])

        def fx(F, J, P, st, i=i):
            if st != "front":
                return
            for t0 in (20, 23):
                a = i - t0
                if 0 <= a < 16:
                    c = add(J["nostril"], (-2.4 * a - 2, -1.6 * a))
                    puff(F, c, 1.6 + 0.9 * a, 1 - a / 16.0)
        out.append((pose(pupil=px, jaw=jaw, eye=blink(i, 30), **b), fx))
    return out


@defset("walk")
def S_walk():
    T, vx, st = 24, 1.5, 0.62
    S = vx * st * T
    out = []
    for i in range(T):
        t = i / float(T)
        w = TAU * t
        feet = {}
        for key, base, ph in (("fF", -15, 0.0), ("fHf", 17, 0.08), ("fFf", -15, 0.5), ("fH", 17, 0.58)):
            gx, gy = gait(t + ph, st, S, 6)
            feet[key] = (base + gx, gy)
        P = pose(by=-36 + 1.0 * math.sin(2 * w + 0.6), brot=1.2 * math.sin(w), hx=-20 + 0.8 * math.sin(w),
                 hy=-34 + 1.2 * math.sin(2 * w + 1.4), hrot=2 * math.sin(w + 0.5), tail=30 + 4 * math.sin(w),
                 tph=w, twave=8, flap=3 * math.sin(2 * w), **feet)
        out.append((P, None))
    return out


@defset("run")
def S_run():
    T, vx, st = 14, 5.0, 0.42
    S = vx * st * T
    out = []
    for i in range(T):
        t = i / float(T)
        w = TAU * t
        feet = {}
        for key, base, ph in (("fF", -17, 0.0), ("fFf", -15, 0.07), ("fH", 15, 0.5), ("fHf", 17, 0.57)):
            gx, gy = gait(t + ph, st, S, 9)
            feet[key] = (base + gx, gy)
        P = pose(by=-38 + 2.6 * math.sin(w + 0.8), brot=7 * math.sin(w + 1.3), hx=-23, hy=-31 + 2 * math.sin(w + 2.0),
                 hrot=-4 + 3 * math.sin(w + 1.8), wing=0.32, flap=16 * math.sin(w), tail=12, tcurl=-3, twave=10, tph=w,
                 **feet)

        def fx(F, J, P, st_, i=i):
            if st_ == "back" and i % 7 in (0, 1, 2):
                a = i % 7
                dust(F, (30 + a * 5, -2 - a), 3 + a * 1.5, 0.8 - a * 0.22, back=True)
        out.append((P, fx))
    return out


def speed_lines(F, i, y0, y1, x0, x1, n=6, seed=0, col=(210, 200, 255)):
    r = random.Random(seed * 31 + i)
    for _ in range(n):
        y = r.uniform(y0, y1)
        a = r.uniform(x0, x1)
        L = r.uniform(18, 46)
        F.line([(a, y), (a + L, y)], col + (int(r.uniform(90, 190)),), r.uniform(0.6, 1.4), layer="bg")


@defset("dash")
def S_dash():
    T = 8
    out = []
    for i in range(T):
        w = TAU * i / T
        P = pose(by=-40 + 1.0 * math.sin(w), brot=-4, feet_rel=True, fF=(7, 12), fFf=(7, 12), fH=(9, 12), fHf=(9, 12),
                 wing=0.72, flap=50 + 6 * math.sin(w), tail=6, tcurl=-1.2, twave=4, tph=2 * w, hx=-25, hy=-30, hrot=-4)

        def fx(F, J, P, st, i=i):
            if st == "back":
                speed_lines(F, i, -60, -10, 30, 110, 7)
                for k in range(3):
                    a = (i + k * 3) % 8
                    dust(F, (34 + a * 9, -2 - a * 0.8), 3 + a, 0.7 - a * 0.08, back=True)
        out.append((P, fx))
    return out


def fly_pose(i, T=12, **kw):
    w = TAU * i / T
    d = dict(by=-46 + 3 * math.cos(w + 0.6), brot=10 + 2 * math.sin(w), wing=1.0, flap=30 * math.cos(w),
             feet_rel=True, fF=(3 + 1.5 * math.sin(w), 14), fFf=(4, 13), fH=(-1 + 2 * math.sin(w + 1), 15), fHf=(0, 14),
             tail=55, tcurl=-5, twave=7, tph=w, hx=-20, hy=-32, hrot=-2 + 3 * math.sin(w + 1), shadow=0.5)
    d.update(kw)
    return pose(**d)


@defset("fly")
def S_fly():
    return [(fly_pose(i), None) for i in range(12)]


@defset("flydash")
def S_flydash():
    out = []
    for i in range(6):
        w = TAU * i / 6
        P = pose(by=-42, brot=-10, wing=0.55, flap=58 + 4 * math.sin(w), feet_rel=True, fF=(8, 10), fFf=(8, 10),
                 fH=(10, 10), fHf=(10, 10), tail=4, tcurl=-0.6, twave=3, tph=w, hx=-25, hy=-29, hrot=-6, shadow=0.4,
                 glow=0.8, eyecol="gold")

        def fx(F, J, P, st, i=i):
            if st == "back":
                speed_lines(F, i, -80, -10, 40, 130, 9, seed=3, col=(200, 170, 255))
                for k in range(5):
                    flame(F, (40 + k * 16 + (i % 2) * 4, -42 + math.sin(i + k) * 3), 6 - k, 0.75 - k * 0.12, back=True)
        out.append((P, fx))
    return out


@defset("fall")
def S_fall():
    out = []
    for i in range(8):
        w = TAU * i / 8
        P = pose(by=-40, brot=8 * math.sin(w), wing=0.85, flap=-45 + 20 * math.sin(2 * w), feet_rel=True,
                 fF=(-4 + 5 * math.sin(2 * w), 12 + 3 * math.cos(2 * w)), fFf=(-2 + 5 * math.sin(2 * w + 2), 12),
                 fH=(4 + 5 * math.sin(2 * w + 1), 13), fHf=(5 + 5 * math.sin(2 * w + 3), 13), emo="shock", jaw=0.45,
                 tail=-12 + 15 * math.sin(w), tcurl=-4, tph=w, twave=9, hy=-36, hrot=10, shadow=0.3)
        out.append((P, None))
    return out


@defset("spin")
def S_spin():
    out = []
    for i in range(12):
        P = pose(G=(-360.0 * i / 12, (0.0, -36.0), False), feet_rel=True, fF=(2, 8), fFf=(2, 8), fH=(-2, 8),
                 fHf=(-2, 8), tail=80, tcurl=12, twave=3, emo="dizzy", jaw=0.2, wing=0.0, hx=-16, hy=-30)
        out.append((P, None))
    return out


_DRAG_PIV = None


def _drag_pose(i, T=32):
    w = TAU * i / T
    return pose(brot=50, hx=-16, hy=-30, hrot=-38 + 6 * math.sin(w), jaw=0.2 + 0.2 * math.sin(2 * w) ** 2,
                emo="angry", wing=0.55, flap=10 + 20 * math.sin(2 * w), feet_rel=True,
                fF=(2 + 3 * math.sin(w), 16), fFf=(3 + 3 * math.sin(w + 0.6), 15), fH=(0 + 3 * math.sin(w + 1.5), 16),
                fHf=(1 + 3 * math.sin(w + 2), 15), tail=40, tcurl=-3, twave=12, tph=w)


def drag_pivot():
    return geometry(_drag_pose(0))["scruff"]


@defset("drag", anchor=None)
def S_drag():
    piv = drag_pivot()
    out = []
    for i in range(32):
        P = _drag_pose(i)
        P["G"] = (7 * math.sin(TAU * i / 32), piv, False)
        out.append((P, None))
    return out


@defset("land")
def S_land():
    out = []
    for i in range(8):
        P = pose(**anim(i, dict(by=[(0, -29), (3, -31), (7, -36)], bsy=[(0, 0.86), (4, 1.05), (7, 1.0)],
                                bsx=[(0, 1.1), (4, 0.97), (7, 1.0)], wing=[(0, 0.6), (7, 0.05)], flap=[(0, -20), (7, 0)],
                                hy=[(0, -28), (4, -36), (7, -34)], tail=[(0, 10), (7, 30)])))

        def fx(F, J, P, st, i=i):
            if st == "front" and i < 7:
                for x in (-22, 26):
                    dust(F, (x - (i * 2 if x < 0 else -i * 2), -2), 3 + i * 1.5, 1 - i / 7.0)
        out.append((P, fx))
    return out


GWALL = (90.0, (0.0, -70.0), False)          # xoay đứng lên vách (bụng áp vào tường bên trái)
GCEIL = (0.0, (0.0, -65.0), True)            # lật ngửa bám trần


@defset("wallg", d=2, anchor="g")
def S_wallg():
    T = 24
    return [(pose(G=GWALL, eye=blink(i, 16), **breath_base(i, T)), None) for i in range(T)]


@defset("wallc", anchor="g")
def S_wallc():
    return [(dict(P, G=GWALL), None) for P, _ in S_walk()]


@defset("ceilg", d=2, anchor="g")
def S_ceilg():
    T = 24
    return [(pose(G=GCEIL, eye=blink(i, 16), **breath_base(i, T)), None) for i in range(T)]


@defset("ceilc", anchor="g")
def S_ceilc():
    return [(dict(P, G=GCEIL), None) for P, _ in S_walk()]


LIE = dict(by=-17.0, bsy=0.93, fF=(-33.0, 0.0), fFf=(-29.0, 0.0), fH=(6.0, 0.0), fHf=(9.0, 0.0), hx=-29.0, hy=6.0,
           hrot=-6.0, tail=14.0, tcurl=2.0, wing=0.0)
STAND = dict(by=-36.0, bsy=1.0, fF=(-15.0, 0.0), fFf=(-15.0, 0.0), fH=(17.0, 0.0), fHf=(17.0, 0.0), hx=-20.0, hy=-34.0,
             hrot=0.0, tail=30.0, tcurl=-7.5, wing=0.05)


@defset("lie")
def S_lie():
    out = []
    for i in range(14):
        t = ss(i / 13.0)
        d = {k: _lv(STAND[k], LIE[k], t) for k in STAND}
        out.append((pose(eye=lerp(1, 0.55, t), **d), None))
    return out


@defset("rest", d=2)
def S_rest():
    T = 32
    out = []
    for i in range(T):
        w = TAU * i / T
        d = dict(LIE)
        d.update(bsy=0.93 + 0.02 * math.sin(w), hy=6 + 0.8 * math.sin(w - 0.6), tph=w, twave=4,
                 tail=14 + 2 * math.sin(w), eye=0.55 * blink(i, 20))
        out.append((pose(**d), None))
    return out


@defset("sleep", d=2)
def S_sleep():
    T = 40
    out = []
    for i in range(T):
        w = TAU * i / T
        d = dict(LIE)
        d.update(bsy=0.93 + 0.03 * math.sin(w), bsx=1 - 0.012 * math.sin(w), hy=7 + 1.0 * math.sin(w - 0.6), tph=w * 0.5,
                 twave=2, eye=0.0, emo="normal", glow=0.15 + 0.1 * math.sin(w))

        def fx(F, J, P, st, i=i):
            if st != "front":
                return
            for k in range(3):
                a = ((i + k * 13) % T) / float(T)
                c = add(J["H"](-10, -18), (14 * a + 4 * math.sin(a * 9), -40 * a))
                letter_z(F, c, 2 + 3.2 * a, math.sin(math.pi * a))
            a = (i % 20) / 20.0
            puff(F, add(J["nostril"], (-5 * a, -2 * a)), 1 + 2 * a, 0.5 * (1 - a))
        out.append((pose(**d), fx))
    return out


# ── chiêu ──
@defset("roar")
def S_roar():
    T = 40
    spec = dict(brot=[(0, 0), (10, 8), (16, -6), (33, -6), (40, 0)], by=[(0, -36), (10, -38), (16, -34), (40, -36)],
                hx=[(0, -20), (10, -14), (16, -27), (33, -27), (40, -20)], hy=[(0, -34), (10, -39), (16, -30), (40, -34)],
                hrot=[(0, 0), (10, 22), (16, -6), (33, -6), (40, 0)], jaw=[(0, 0), (8, 0.2), (12, 0.1), (16, 1.0), (32, 1.0), (38, 0)],
                wing=[(0, 0.05), (10, 0.6), (16, 1.0), (32, 1.0), (40, 0.05)], flap=[(0, 0), (10, -15), (16, 25), (32, 25), (40, 0)],
                tail=[(0, 30), (16, 8), (34, 8), (40, 30)], glow=[(0, 0.3), (16, 1.0), (34, 1.0), (40, 0.3)])
    out = []
    for i in range(T):
        P = pose(**anim(i, spec))
        if 16 <= i <= 32:
            sx, sy = shake(i, 1.0)
            P["bx"] += sx
            P["hx"] += sx * 1.4
            P["hy"] += sy

        def fx(F, J, P, st, i=i):
            if st != "front":
                return
            ang = 180 + J["hang"]
            for t0 in range(16, 33, 3):
                a = i - t0
                if 0 <= a < 10:
                    sound_ring(F, J["mouth"], ang, 8 + a * 11, 1 - a / 10.0)
            if 16 <= i <= 34:
                r = random.Random(i)
                for _ in range(5):
                    aa = ang + r.uniform(-40, 40)
                    p0 = add(J["mouth"], dirv(aa), r.uniform(20, 50))
                    F.line([p0, add(p0, dirv(aa), r.uniform(10, 26))], (230, 210, 255, 170), 0.7, layer="fg")
                for x in range(3):
                    dust(F, (-40 - x * 22 - (i - 16) * 2, -2), 4 + (i - 16) * 0.4, 0.6 * (1 - (i - 16) / 19.0))
        out.append((P, fx))
    return out


@defset("breath")
def S_breath():
    T = 56
    spec = dict(hx=[(0, -20), (12, -13), (16, -27), (46, -27), (56, -20)], hy=[(0, -34), (12, -39), (16, -28), (46, -28), (56, -34)],
                hrot=[(0, 0), (12, 18), (16, -10), (30, -14), (46, -6), (56, 0)],
                jaw=[(0, 0), (10, 0.15), (14, 0.05), (17, 0.9), (45, 0.9), (50, 0.1), (56, 0)],
                brot=[(0, 0), (12, 6), (17, -4), (46, -4), (56, 0)], bsx=[(0, 1), (12, 1.06), (17, 0.97), (46, 0.97), (56, 1)],
                bsy=[(0, 1), (12, 1.06), (17, 0.98), (56, 1)], wing=[(0, 0.05), (14, 0.45), (46, 0.45), (56, 0.05)],
                flap=[(0, 0), (14, -10), (46, 15), (56, 0)], glow=[(0, 0.3), (13, 1.0), (46, 1.0), (56, 0.3)],
                tail=[(0, 30), (16, 14), (46, 14), (56, 30)])
    rnd0 = random.Random(5)
    embers = [(rnd0.uniform(0.2, 1), rnd0.uniform(-1, 1), rnd0.uniform(0, 1)) for _ in range(14)]
    out = []
    for i in range(T):
        P = pose(eyecol="gold", **anim(i, spec))

        def fx(F, J, P, st, i=i):
            if st != "front":
                return
            M = J["mouth"]
            if i < 14:                                           # hút khí: hạt sáng dồn vào miệng
                r = random.Random(i)
                for _ in range(7):
                    a = r.uniform(120, 240)
                    d = r.uniform(10, 50) * (1 - i / 14.0) + 6
                    F.ell(add(M, dirv(a), d), 1.0, 1.0, fill=(220, 180, 255, 230), layer="fg")
                for nn in (0, 1):
                    a = (i % 7) / 7.0
                    puff(F, add(J["nostril"], (-3 * a, -4 * a - nn)), 1 + 1.5 * a, 0.6 * (1 - a))
            if 16 <= i <= 47:
                Lc = min(1.0, (i - 15) / 6.0) * 230 * (1 if i < 44 else (47 - i) / 3.0)
                ang = 180 + J["hang"] + 4
                dv = dirv(ang)
                nv = (-dv[1], dv[0])
                r = random.Random(i * 13)
                N = 64
                blobs = []
                for k in range(N + 1):
                    s_ = (k / float(N)) * Lc
                    wob = math.sin(k * 0.8 - i * 1.4) * (1.5 + s_ * 0.05) + r.uniform(-1, 1) * s_ * 0.025
                    c = add(add(M, dv, s_ + 2), nv, wob)
                    rr = 3.4 + s_ * 0.1 + r.uniform(-0.4, 0.4)
                    blobs.append((c, rr, s_))
                fade = 1.0 if i < 44 else (47 - i) / 3.0
                for c, rr, s_ in blobs:
                    F.ell(c, rr * 1.7, rr * 1.7, fill=(140, 50, 255, int(120 * fade)), layer="fgg")
                for k in range(0, N, 5):                         # lưỡi lửa liếm ra hai bên
                    c, rr, s_ = blobs[k]
                    side = 1 if (k + i) % 2 else -1
                    tip = add(add(c, nv, side * (rr + 4 + s_ * 0.06)), dv, 6 + s_ * 0.05)
                    F.poly([add(c, dv, -rr * 0.6), tip, add(c, dv, rr * 0.9)], (170, 90, 255, int(230 * fade)), layer="fg")
                for c, rr, s_ in blobs:
                    F.ell(c, rr, rr, fill=(165, 85, 255, int(240 * fade)), layer="fg")
                for c, rr, s_ in blobs:
                    F.ell(c, rr * 0.68, rr * 0.68, fill=(16, 5, 28, int(250 * fade)), layer="fg")
                for c, rr, s_ in blobs:
                    if s_ < 40:
                        F.ell(c, rr * 0.35 * (1 - s_ / 40.0), rr * 0.35 * (1 - s_ / 40.0), fill=(245, 225, 255, int(255 * fade)), layer="fg")
                for fr, side, ph in embers:
                    s_ = ((fr + i * 0.07) % 1.0) * Lc
                    c = add(add(M, dv, s_), nv, side * (6 + s_ * 0.18))
                    F.ell(c, 1.1, 1.1, fill=(240, 200, 255, 255), layer="fg")
            if i >= 46:
                a = (i - 46) / 10.0
                puff(F, add(J["mouth"], (-4 - 8 * a, -6 * a)), 3 + 4 * a, 0.7 * (1 - a), col=(80, 60, 110))
        out.append((P, fx))
    return out


@defset("claw")
def S_claw():
    T = 36
    up = (-26.0, -48.0)
    dn = (-46.0, -14.0)
    swipes = [(9, "fF"), (17, "fFf"), (25, "fF")]
    spec = dict(brot=[(0, 0), (7, 30), (30, 30), (36, 0)], by=[(0, -36), (7, -44), (30, -44), (36, -36)],
                hx=[(0, -20), (7, -24), (30, -24), (36, -20)], hy=[(0, -34), (7, -26), (30, -26), (36, -34)],
                hrot=[(0, 0), (7, -26), (30, -26), (36, 0)], jaw=[(0, 0), (8, 0.55), (30, 0.55), (36, 0)],
                wing=[(0, 0.05), (7, 0.7), (30, 0.7), (36, 0.05)], flap=[(0, 0), (7, -20), (30, -20), (36, 0)],
                tail=[(0, 30), (7, 52), (30, 52), (36, 30)], fH=[(0, (17.0, 0.0)), (7, (8.0, 0.0)), (30, (8.0, 0.0)), (36, (17.0, 0.0))],
                fHf=[(0, (17.0, 0.0)), (7, (12.0, 0.0)), (30, (12.0, 0.0)), (36, (17.0, 0.0))], glow=[(0, 0.3), (8, 0.8), (36, 0.3)])
    out = []
    for i in range(T):
        P = pose(**anim(i, spec))
        rest_pos = {"fF": (-24.0, -30.0), "fFf": (-20.0, -32.0)}
        for key in ("fF", "fFf"):
            p = kf(i, [(0, (-15.0, 0.0)), (7, rest_pos[key]), (30, rest_pos[key]), (36, (-15.0, 0.0))])
            for t0, k2 in swipes:
                if k2 == key and t0 - 3 <= i <= t0 + 5:
                    if i < t0:
                        p = _lv(rest_pos[key], up, ss((i - t0 + 3) / 3.0))
                    else:
                        p = _lv(up, dn, ss((i - t0) / 3.0)) if i <= t0 + 3 else _lv(dn, rest_pos[key], (i - t0 - 3) / 2.0)
            P[key] = p

        def fx(F, J, P, st, i=i):
            if st != "front":
                return
            for t0, _ in swipes:
                a = i - t0
                if 0 <= a < 7:
                    al = 1 - a / 7.0
                    for k in range(3):
                        off = (k - 1) * 6
                        path = [add(add(up, (-6 + off * 0.4, off)), dirv(115), 0), add((-44 + off, -36 + off), (0, 0)),
                                add(add(dn, (-8 + off * 0.3, off * 0.6)), (0, 0))]
                        path = bez(path[0], path[1], path[2], 10)
                        crescent(F, path, 2.6 - k * 0.2, al)
        out.append((P, fx))
    return out


@defset("tailw")
def S_tailw():
    T = 32
    spec = dict(brot=[(0, 0), (8, -8), (14, -12), (22, -6), (32, 0)], by=[(0, -36), (8, -33), (14, -34), (32, -36)],
                hx=[(0, -20), (8, -18), (14, -26), (32, -20)], hy=[(0, -34), (8, -30), (14, -30), (32, -34)],
                hrot=[(0, 0), (8, 8), (14, -8), (32, 0)], jaw=[(0, 0), (10, 0.5), (18, 0.5), (26, 0)],
                tail=[(0, 30), (8, -60), (14, -205), (19, -215), (26, -40), (32, 30)],
                tcurl=[(0, -7.5), (8, -3.0), (14, 7.0), (19, 8.0), (26, -4), (32, -7.5)],
                wing=[(0, 0.05), (10, 0.5), (24, 0.5), (32, 0.05)], flap=[(0, 0), (12, 20), (32, 0)], glow=[(0, 0.3), (12, 0.9), (32, 0.3)])
    out = []
    path = []
    for i in range(T):
        P = pose(twave=2, **anim(i, spec))
        path.append(geometry(P)["tail"][-1])
    for i in range(T):
        P = pose(twave=2, **anim(i, spec))

        def fx(F, J, P, st, i=i):
            if st != "front":
                return
            if 9 <= i <= 22:
                lo = max(8, i - 6)
                pts = path[lo:i + 1]
                if len(pts) >= 3:
                    pts = catmull(pts, closed=False, n=4)
                    crescent(F, pts, 5.5, 1 - max(0, i - 17) / 6.0)
        out.append((P, fx))
    return out


@defset("gust")
def S_gust():
    T = 36
    spec = dict(wing=[(0, 0.05), (6, 1.0), (30, 1.0), (36, 0.05)],
                flap=[(0, 0), (6, -38), (12, 42), (18, -38), (24, 42), (30, 0), (36, 0)],
                by=[(0, -36), (6, -38), (12, -42), (18, -38), (24, -42), (30, -36)],
                brot=[(0, 0), (6, 8), (12, -4), (18, 8), (24, -4), (32, 0)],
                hx=[(0, -20), (12, -25), (26, -25), (34, -20)], hy=[(0, -34), (12, -31), (26, -31), (34, -34)],
                jaw=[(0, 0), (10, 0.35), (26, 0.35), (32, 0)], tail=[(0, 30), (12, 15), (28, 15), (36, 30)])
    out = []
    for i in range(T):
        P = pose(**anim(i, spec))

        def fx(F, J, P, st, i=i):
            if st != "front":
                return
            for t0 in (11, 23):
                a = i - t0
                if 0 <= a < 12:
                    al = 1 - a / 12.0
                    r = random.Random(t0)
                    for k in range(9):
                        y = -78 + k * 9.5 + r.uniform(-4, 4)
                        x = -26 - a * 15 - r.uniform(0, 24)
                        L = 34 + r.uniform(0, 30)
                        pts = bez((x, y), (x - L / 2, y - 7 * math.sin(k + a * 0.5)), (x - L, y + 3), 8)
                        F.line(pts, (150, 120, 255, int(170 * al)), 4.5, layer="fgg")
                        F.line(pts, (240, 240, 255, int(235 * al)), 1.4, layer="fg")
                    for cy in (-58, -24):
                        c = (-58 - a * 13, cy)
                        sw = [add(c, dirv(k * 38 + a * 40), 2 + k * 1.3) for k in range(14)]
                        F.line(sw, (160, 130, 255, int(160 * al)), 3.5, layer="fgg")
                        F.line(sw, (245, 245, 255, int(230 * al)), 1.1, layer="fg")
                    for x in (-30, -55, -80):
                        dust(F, (x - a * 12, -3), 5 + a * 1.2, al)
        out.append((P, fx))
    return out


@defset("stomp")
def S_stomp():
    T = 32
    spec = dict(brot=[(0, 0), (9, 28), (12, -6), (26, -4), (32, 0)], by=[(0, -36), (9, -42), (12, -31), (18, -34), (32, -36)],
                bsy=[(0, 1), (12, 0.9), (17, 1.02), (22, 1)], hx=[(0, -20), (9, -14), (12, -26), (30, -22)],
                hy=[(0, -34), (9, -40), (12, -27), (30, -34)], hrot=[(0, 0), (9, 18), (12, -10), (30, 0)],
                jaw=[(0, 0), (8, 0.4), (12, 0.9), (22, 0.6), (30, 0)], wing=[(0, 0.05), (9, 0.8), (14, 0.5), (32, 0.05)],
                flap=[(0, 0), (9, -30), (12, 30), (32, 0)], glow=[(0, 0.3), (12, 1.0), (32, 0.3)],
                fF=[(0, (-15.0, 0.0)), (9, (-28.0, -26.0)), (12, (-24.0, 0.0))],
                fFf=[(0, (-15.0, 0.0)), (9, (-24.0, -28.0)), (12, (-20.0, 0.0))])
    rnd0 = random.Random(9)
    rocks = [(rnd0.choice((-1, 1)) * rnd0.uniform(1.5, 4.5), rnd0.uniform(-7, -4), rnd0.uniform(1.5, 3.2), rnd0.uniform(0, 360))
             for _ in range(9)]
    out = []
    for i in range(T):
        P = pose(**anim(i, spec))
        if 12 <= i <= 20:
            sx, sy = shake(i, 1.4)
            P["bx"] += sx

        def fx(F, J, P, st, i=i):
            a = i - 12
            if a < 0:
                return
            hit = (-24.0, 0.0)
            if st == "back":
                r = random.Random(4)
                for dirn in (-1, 1):
                    for k in range(2):
                        crack(F, hit[0], dirn, min(1.0, a / 5.0) * (60 + 40 * k), r, 1 - max(0, a - 12) / 8.0)
                return
            if a < 5:
                F.ell(hit, 16 + a * 8, 8 + a * 3, fill=(200, 150, 255, int(230 * (1 - a / 5.0))), layer="fgg")
                if a < 2:
                    F.ell(hit, 9, 4, fill=(255, 245, 255, 255), layer="fg")
            if a < 12:
                al = 1 - a / 12.0
                F.ell(hit, 14 + a * 9, 3 + a * 1.4, outline=(220, 190, 255, int(220 * al)), w=1.2, layer="fg")
                F.ell(hit, 14 + a * 9, 3 + a * 1.4, outline=(160, 90, 255, int(160 * al)), w=3.5, layer="fgg")
            for vx, vy, sz, rot0 in rocks:
                x = hit[0] + vx * a
                y = vy * a + 0.45 * a * a
                if y < 0 and a < 18:
                    rock(F, (x, y), sz, rot0 + a * 25)
            for k in range(4):
                dust(F, (hit[0] + (k - 1.5) * 20 - (a * 2.2 if k < 2 else -a * 2.2), -4 - a * 0.6), 7 + a * 1.2,
                     0.8 * (1 - a / 20.0))
        out.append((P, fx))
    return out


@defset("thunder")
def S_thunder():
    T = 56
    spec = dict(brot=[(0, 0), (10, 15), (44, 15), (56, 0)], by=[(0, -36), (10, -40), (44, -40), (56, -36)],
                hx=[(0, -20), (10, -10), (44, -10), (56, -20)], hy=[(0, -34), (10, -40), (44, -40), (56, -34)],
                hrot=[(0, 0), (10, 28), (44, 28), (56, 0)], jaw=[(0, 0), (10, 0.3), (14, 1.0), (42, 1.0), (50, 0)],
                wing=[(0, 0.05), (10, 0.85), (44, 0.85), (56, 0.05)], flap=[(0, 0), (10, -25), (44, -25), (56, 0)],
                glow=[(0, 0.3), (14, 1.0), (50, 1.0), (56, 0.3)], tail=[(0, 30), (12, 10), (44, 10), (56, 30)])
    strikes = [(16, -150), (21, 95), (26, -95), (31, 150), (36, -60)]
    out = []
    for i in range(T):
        P = pose(eyecol="blue" if 14 <= i <= 50 else "gold", **anim(i, spec))
        if i in (40, 41, 42):
            P["glow"] = 1.0

        def fx(F, J, P, st, i=i):
            r = random.Random(i * 101)
            if st == "back":
                for t0, x in strikes:
                    a = i - t0
                    if 0 <= a < 5:
                        top = (x + r.uniform(-20, 20), Y0 + 5)
                        rb = random.Random(t0)
                        pts = jag(top, (x, -1), 12, 10, rb)
                        al = 1 - a / 5.0
                        zap(F, pts if a > 0 else pts[:7], 3.2, al, back=True)
                        for kk in (3, 6, 8):                     # nhánh sét
                            if a > 0:
                                q = pts[kk]
                                zap(F, jag(q, add(q, (rb.uniform(-40, 40), rb.uniform(20, 45))), 4, 4, rb), 1.4, al, back=True)
                        if a >= 1:
                            F.ell((x, -1), 26, 7, fill=(120, 170, 255, int(230 * al)), layer="bgg")
                            F.ell((x, -1), 10, 3, fill=(240, 248, 255, int(255 * al)), layer="bg")
                            for kk in range(5):
                                aa = rb.uniform(190, 350)
                                zap(F, jag((x, -1), add((x, -1), dirv(aa), rb.uniform(12, 26)), 3, 3, rb), 0.8, al, back=True)
                return
            if 14 <= i <= 44:                                   # điện quấn quanh thân, sừng
                for _ in range(3):
                    c = add(J["body_c"], (r.uniform(-30, 30), r.uniform(-20, 14)))
                    zap(F, jag(c, add(c, dirv(r.uniform(0, 360)), r.uniform(10, 18)), 3, 3, r), 0.7, 0.9)
                zap(F, jag(J["horn_tip"], add(J["horn_tip"], (r.uniform(-8, 8), -r.uniform(8, 16))), 3, 3, r), 0.7, 0.9)
            if 40 <= i <= 44:                                    # sét lớn đánh trúng sừng
                a = i - 40
                pts = jag((J["horn_tip"][0] + 30, Y0 + 5), J["horn_tip"], 9, 8, random.Random(77))
                zap(F, pts, 3, 1 - a / 5.0)
                F.ell(J["horn_tip"], 14 - a * 2, 14 - a * 2, fill=(190, 220, 255, int(230 * (1 - a / 5.0))), layer="fgg")
        out.append((P, fx))
    return out


@defset("charge")
def S_charge():
    T = 40
    spec = dict(by=[(0, -36), (8, -32), (34, -32), (40, -36)], bsy=[(0, 1), (8, 0.95), (34, 0.95), (36, 1.06), (40, 1)],
                hx=[(0, -20), (8, -22), (34, -22), (40, -20)], hy=[(0, -34), (8, -28), (34, -28), (36, -38), (40, -34)],
                hrot=[(0, 0), (8, -8), (34, -8), (36, 15), (40, 0)], jaw=[(0, 0), (34, 0.15), (36, 0.8), (40, 0)],
                glow=[(0, 0.3), (30, 1.0), (40, 0.5)], wing=[(0, 0.05), (8, 0.25), (34, 0.25), (36, 1.0), (40, 0.05)],
                flap=[(0, 0), (34, 0), (36, 25), (40, 0)], tail=[(0, 30), (8, 22), (40, 30)])
    out = []
    for i in range(T):
        P = pose(eyecol="violet", **anim(i, spec))
        if 8 <= i < 34:
            P["bx"] += shake(i, 0.5)[0]

        def fx(F, J, P, st, i=i):
            k = min(1.0, i / 24.0) * (1 if i < 34 else max(0, (40 - i) / 6.0))
            r = random.Random(i * 7)
            if st == "back":
                for n in range(int(16 * k) + 1):                # lửa hắc khí bốc lên quanh thân
                    x = -58 + n * 8.5 + r.uniform(-3, 3)
                    ph = (i * 0.07 + n * 0.37) % 1.0
                    hh = (22 + 34 * k) * (0.6 + 0.4 * math.sin(n * 1.7 + i * 0.5))
                    tongue(F, (x, -4 - ph * 10), 5 + 3 * k, hh, k * (1 - ph * 0.5), back=True,
                           lean=0.15 * math.sin(i * 0.4 + n))
                return
            for n in range(int(10 * k)):                        # hạt khí hút vào thân
                a = r.uniform(0, 360)
                ph = (i * 0.11 + r.random()) % 1.0
                c = add(J["body_c"], dirv(a), 70 * (1 - ph) + 8)
                F.ell(c, 1.0 + ph, 1.0 + ph, fill=(225, 190, 255, int(255 * ph)), layer="fg")
            if 34 <= i:
                a = i - 34
                c = J["body_c"]
                F.ell(c, 20 + a * 14, 14 + a * 9, outline=(230, 200, 255, int(255 * (1 - a / 6.0))), w=1.4, layer="fg")
                F.ell(c, 20 + a * 14, 14 + a * 9, outline=(170, 80, 255, int(200 * (1 - a / 6.0))), w=5, layer="fgg")
        out.append((P, fx))
    return out


@defset("ult")
def S_ult():
    T = 76
    spec = dict(brot=[(0, 0), (12, 18), (36, 18), (40, -4), (62, -4), (76, 0)], by=[(0, -36), (12, -42), (36, -42), (40, -35), (76, -36)],
                bx=[(0, 0), (40, 0), (44, 6), (62, 6), (76, 0)],
                hx=[(0, -20), (12, -12), (36, -12), (40, -27), (62, -27), (76, -20)],
                hy=[(0, -34), (12, -40), (36, -40), (40, -29), (62, -29), (76, -34)],
                hrot=[(0, 0), (12, 26), (36, 26), (40, -4), (62, -4), (76, 0)],
                jaw=[(0, 0), (10, 1.0), (62, 1.0), (70, 0)], wing=[(0, 0.05), (12, 1.0), (62, 1.0), (76, 0.05)],
                flap=[(0, 0), (12, -25), (36, -25), (40, 30), (62, 30), (76, 0)], glow=[(0, 0.3), (14, 1.0), (64, 1.0), (76, 0.3)],
                tail=[(0, 30), (12, 8), (62, 8), (76, 30)])
    out = []
    for i in range(T):
        P = pose(eyecol="violet", **anim(i, spec))
        if 40 <= i <= 62:
            P["bx"] += shake(i, 1.0)[0]

        def fx(F, J, P, st, i=i):
            M = J["mouth"]
            ang = 180 + J["hang"]
            orb = add(M, dirv(ang), 12)
            r = random.Random(i * 3)
            if st == "back":
                return
            if 10 <= i <= 40:                                   # hắc nhật thành hình
                k = ss((i - 10) / 24.0)
                R = 2 + 13 * k
                for n in range(14):
                    a = r.uniform(0, 360) + i * 12
                    d = R + 30 * ((n * 0.37 + i * 0.08) % 1.0)
                    c = add(orb, dirv(a), d)
                    F.line([c, add(c, dirv(a + 100), 4)], (220, 180, 255, 220), 0.8, layer="fg")
                F.ell(orb, R * 2.0, R * 2.0, fill=(150, 60, 255, 200), layer="fgg")
                F.ell(orb, R * 1.15, R * 1.15, fill=(220, 160, 255, 255), layer="fg")
                F.ell(orb, R, R, fill=(8, 2, 14, 255), layer="fg")
                F.ell(orb, R * 1.15, R * 1.15, outline=(255, 240, 255, 255), w=0.8, layer="fg")
            if 40 <= i <= 64:                                   # pháo hắc nhật
                a = i - 40
                k = min(1.0, a / 3.0) * (1 if i < 60 else (64 - i) / 4.0)
                R = 13 * k * (1 + 0.08 * math.sin(i * 2.3))
                end = (X0 + 4, orb[1] + (X0 + 4 - orb[0]) * math.tan(math.radians(ang - 180)) * -1)
                dv = dirv(ang)
                nv = (-dv[1], dv[0])
                L = dist(orb, end)

                def edge(sc, side, ph=0.0):
                    pts = []
                    for n in range(31):
                        s_ = L * n / 30.0
                        rr = R * sc * (1 + 0.1 * n / 30.0) * (1 + 0.18 * math.sin(s_ * 0.16 - i * 1.7 + ph))
                        pts.append(add(add(orb, dv, s_), nv, side * rr))
                    return pts
                F.poly(edge(2.2, 1) + edge(2.2, -1, 1.3)[::-1], (150, 60, 255, int(190 * k)), layer="fgg")
                F.poly(edge(1.0, 1) + edge(1.0, -1, 1.3)[::-1], (205, 150, 255, int(255 * k)), layer="fg")
                F.poly(edge(0.68, 1, 0.5) + edge(0.68, -1, 1.8)[::-1], (10, 3, 18, int(255 * k)), layer="fg")
                F.line(edge(0.7, 1, 0.5), (255, 255, 255, int(255 * k)), 0.6, layer="fg")
                F.line(edge(0.7, -1, 1.8), (255, 255, 255, int(255 * k)), 0.6, layer="fg")
                for side in (1, -1):                            # sét chạy dọc hai mép tia
                    p0 = add(orb, nv, side * R * 1.2)
                    zap(F, jag(p0, add(p0, dv, L), 16, R * 0.5, r), 0.9, k, g=(160, 90, 255), m=(230, 200, 255))
                for n in range(10):                             # hạt năng lượng phóng theo tia
                    s_ = ((n / 10.0) + a * 0.09) % 1.0 * L
                    c = add(add(orb, dv, s_), nv, R * r.uniform(-1.6, 1.6))
                    F.line([c, add(c, dv, 10)], (240, 220, 255, int(230 * k)), 0.8, layer="fg")
                F.ell(orb, R * 1.6, R * 1.6, fill=(240, 220, 255, int(255 * k)), layer="fg")
                F.ell(orb, R * 1.2, R * 1.2, fill=(10, 3, 18, int(255 * k)), layer="fg")
            if 62 <= i:
                a = i - 62
                puff(F, add(M, (-6 - a * 1.5, -a * 1.2)), 3 + a * 0.8, 0.7 * (1 - a / 14.0), col=(70, 50, 100))
        out.append((P, fx))
    return out


@defset("takeoff")
def S_takeoff():
    out = []
    for i in range(10):
        P = pose(**anim(i, dict(by=[(0, -36), (5, -30), (9, -46)], bsy=[(0, 1), (5, 0.9), (9, 1.05)], wing=[(0, 0.05), (5, 0.8), (9, 1.0)],
                                flap=[(0, 0), (5, -40), (9, 30)], hy=[(0, -34), (5, -28), (9, -32)], tail=[(0, 30), (9, 50)],
                                fF=[(0, (-15.0, 0.0)), (6, (-15.0, 0.0)), (9, (-10.0, -8.0))],
                                fFf=[(0, (-15.0, 0.0)), (6, (-15.0, 0.0)), (9, (-10.0, -8.0))])))

        def fx(F, J, P, st, i=i):
            if st == "front" and i >= 6:
                a = i - 6
                for x in (-30, 0, 30):
                    dust(F, (x + (x / 10.0) * a * 2, -2), 3 + a * 1.5, 1 - a / 4.0)
        out.append((P, fx))
    return out


@defset("dive")
def S_dive():
    out = []
    for i in range(6):
        w = TAU * i / 6
        P = pose(G=(-70.0, (0.0, -36.0), False), wing=0.35, flap=62 + 4 * math.sin(w), feet_rel=True, fF=(8, 10), fFf=(8, 10),
                 fH=(10, 10), fHf=(10, 10), tail=0, tcurl=-0.5, twave=4, tph=w, hx=-26, hy=-28, hrot=-4, jaw=0.6,
                 glow=1.0, eyecol="violet")

        def fx(F, J, P, st, i=i):
            if st != "back":
                return
            g0 = F.G
            F.G = (0.0, (0.0, 0.0), False)
            for k in range(7):                                 # đuôi lửa hắc viêm phía trên
                y = -92 - k * 15 + (i % 3) * 4
                flame(F, (14 + k * 3 + math.sin(k * 1.3 + i) * 4, y), 10 - k * 1.1, 0.85 - k * 0.1, back=True)
            r = random.Random(i)
            for _ in range(6):
                x = r.uniform(-40, 50)
                y = r.uniform(-200, -60)
                F.line([(x, y), (x, y - r.uniform(20, 40))], (210, 190, 255, 160), 0.8, layer="bg")
            F.G = g0
        out.append((P, fx))
    return out


@defset("impact")
def S_impact():
    T = 30
    spec = dict(by=[(0, -24), (6, -26), (16, -30), (24, -36), (30, -36)], bsy=[(0, 0.82), (6, 0.95), (16, 1.0)],
                bsx=[(0, 1.14), (6, 1.02), (16, 1.0)], hx=[(0, -26), (16, -24), (30, -20)], hy=[(0, -20), (12, -24), (22, -36), (30, -34)],
                hrot=[(0, -14), (14, -10), (22, 20), (28, 0)], jaw=[(0, 0.3), (16, 0.2), (20, 1.0), (26, 0.9), (30, 0)],
                wing=[(0, 0.8), (14, 0.6), (22, 1.0), (30, 0.05)], flap=[(0, 20), (14, 30), (22, -10), (30, 0)],
                glow=[(0, 1.0), (30, 0.4)], tail=[(0, 10), (30, 30)],
                fF=[(0, (-24.0, 0.0)), (16, (-20.0, 0.0)), (28, (-15.0, 0.0))], fFf=[(0, (-20.0, 0.0)), (28, (-15.0, 0.0))])
    rnd0 = random.Random(21)
    rocks = [(rnd0.uniform(-6, 6), rnd0.uniform(-9, -5), rnd0.uniform(1.6, 3.6), rnd0.uniform(0, 360)) for _ in range(14)]
    out = []
    for i in range(T):
        P = pose(eyecol="violet", **anim(i, spec))
        if i < 8:
            P["bx"] += shake(i, 1.5)[0]

        def fx(F, J, P, st, i=i):
            a = i
            if st == "back":                                    # hố sâu + vết nứt
                k = 1 - max(0, i - 22) / 8.0
                F.ell((0, 0), 62, 9, fill=(18, 8, 24, int(230 * k)), layer="bg")
                F.ell((0, 0), 62, 9, outline=(150, 80, 230, int(200 * k)), w=1.2, layer="bg")
                F.ell((0, 0), 66, 11, outline=(130, 60, 230, int(150 * k)), w=4, layer="bgg")
                r = random.Random(8)
                for dirn in (-1, 1):
                    for n in range(3):
                        crack(F, dirn * 50, dirn, min(1.0, a / 4.0) * (30 + n * 25), r, k)
                return
            if a < 5:
                F.ell((0, -10), 40 + a * 14, 16 + a * 6, fill=(200, 150, 255, int(220 * (1 - a / 5.0))), layer="fgg")
            if a < 14:
                al = 1 - a / 14.0
                F.ell((0, -2), 30 + a * 12, 4 + a * 2, outline=(235, 210, 255, int(255 * al)), w=1.4, layer="fg")
                F.ell((0, -2), 30 + a * 12, 4 + a * 2, outline=(160, 80, 255, int(200 * al)), w=5, layer="fgg")
                for n in range(8):                              # cột lửa hắc viêm bắn lên viền hố
                    x = -55 + n * 15
                    flame(F, (x, -4 - a * 3 - (n % 3) * 4), 5 * al + 1, al)
            for vx, vy, sz, r0 in rocks:
                x = vx * a * 1.6
                y = vy * a + 0.5 * a * a
                if y < 0 and a < 20:
                    rock(F, (x, y), sz, r0 + a * 30)
            for n in range(6):
                dust(F, ((n - 2.5) * 22 + (n - 2.5) * a * 1.2, -4 - a * 0.6), 6 + a * 0.8, 0.85 * (1 - a / 26.0))
        out.append((P, fx))
    return out


# ── cảm xúc ──
@defset("smug")
def S_smug():
    T = 40
    out = []
    for i in range(T):
        w = TAU * i / T
        P = pose(**anim(i, dict(hrot=[(0, 0), (6, 16), (34, 16), (40, 0)], hy=[(0, -34), (6, -37), (34, -37), (40, -34)],
                                hx=[(0, -20), (6, -16), (34, -16), (40, -20)])))
        lau = clamp01(seg(i, 6, 9)) * (1 - seg(i, 31, 34))
        P.update(emo="happy" if lau > 0.3 else "angry", jaw=lau * (0.25 + 0.15 * math.sin(i * 1.6)), by=-36 + lau * 0.8 * math.sin(i * 1.6),
                 tph=w * 2, twave=9, tail=34)
        P["hrot"] += lau * 2.5 * math.sin(i * 1.6)

        def fx(F, J, P, st, i=i):
            if st != "front":
                return
            for t0 in (8, 16, 24):
                a = i - t0
                if 0 <= a < 12:
                    for nn in (-1, 1):
                        c = add(J["nostril"], (-2 * a - 1 + nn, -1.8 * a - 1))
                        puff(F, c, 1.2 + 0.7 * a, 0.75 * (1 - a / 12.0), col=(120, 110, 140))
        out.append((P, fx))
    return out


@defset("rage")
def S_rage():
    T = 40
    out = []
    for i in range(T):
        k = seg(i, 0, 6) * (1 - seg(i, 34, 40))
        sx, sy = shake(i, 1.2 * k)
        P = pose(eyecol="red", emo="angry", jaw=0.5 * k + 0.12 * k * math.sin(i * 2.1), glow=0.3 + 0.7 * k,
                 bx=sx, hx=-22 + sx, hy=-31 + sy, hrot=-6 * k, by=-35, wing=0.05 + 0.4 * k, flap=-15 * k + 6 * math.sin(i * 2.3) * k,
                 tail=lerp(30, 12, k), twave=6 + 6 * k, tph=i * 0.9)

        def fx(F, J, P, st, i=i, k=k):
            r = random.Random(i * 11)
            if st == "back":
                for n in range(int(14 * k) + 1):
                    x = -56 + n * 8.5 + r.uniform(-3, 3)
                    ph = (i * 0.08 + n * 0.41) % 1.0
                    hh = (26 + 22 * k) * (0.6 + 0.4 * math.sin(n * 1.9 + i * 0.6))
                    tongue(F, (x, -4 - ph * 8), 4 + 3 * k, hh, k * (1 - ph * 0.5), back=True, col=(235, 40, 70),
                           lean=0.15 * math.sin(i * 0.5 + n))
                return
            for nn in (0, 1):
                a = (i * 1.0 + nn * 4) % 8 / 8.0
                puff(F, add(J["nostril"], (-3 - 6 * a, -2 - 5 * a)), 1.2 + 2.2 * a, k * (1 - a), col=(150, 140, 150))
            if k > 0.5:
                h = J["H"](-6, -22)
                for n in range(3):                              # gân giận chữ thập
                    a = n * 120 + i * 9
                    F.line([add(h, dirv(a), 1.5), add(h, dirv(a), 4)], (255, 60, 60, 255), 1.0, layer="fg")
        out.append((P, fx))
    return out


@defset("tantrum")
def S_tantrum():
    T = 48
    out = []
    for i in range(T):
        w = TAU * i / T
        P = pose(G=(0.0, (0.0, -21.0), True), hflip=True, by=-21, brot=3 * math.sin(4 * w), feet_rel=True,
                 fF=(-4 + 10 * math.sin(4 * w), 22 + 4 * math.cos(4 * w)), fFf=(-2 + 10 * math.sin(4 * w + 2), 22),
                 fH=(4 + 10 * math.sin(4 * w + 1), 23 + 4 * math.cos(4 * w + 1)), fHf=(6 + 10 * math.sin(4 * w + 3), 23),
                 wing=0.35, flap=95 + 18 * math.sin(4 * w), tail=25 + 25 * math.sin(2 * w), tcurl=-2, twave=8, tph=2 * w,
                 hx=-22, hy=2, hrot=6 * math.sin(4 * w + 1), jaw=0.6 + 0.25 * math.sin(6 * w), eye=0.0, emo="happy",
                 shadow=0)

        def fx(F, J, P, st, i=i):
            if st != "front":
                return
            e = F.g(J["eye"])
            for n in range(8):                                  # nước mắt phun hai bên
                a = ((i * 0.15 + n / 8.0) % 1.0)
                side = -1 if n % 2 else 1
                c = (e[0] + side * (6 + 30 * a), e[1] - 14 * math.sin(math.pi * a) * 1.5 + 10 * a * a)
                F.G, g0 = (0.0, (0.0, 0.0), False), F.G
                droplet(F, c, 1.6, 1 - a)
                F.G = g0
        out.append((P, fx))
    return out


@defset("cry")
def S_cry():
    T = 48
    out = []
    for i in range(T):
        w = TAU * i / T
        sn = 1.0 if (i % 16) < 3 else 0.0
        P = pose(brot=26, by=-29 + sn * 0.8, fH=(4, 0), fHf=(7, 0), fF=(-22, 0), fFf=(-20, 0), hx=-17, hy=-26,
                 hrot=-14 + 2 * math.sin(w), emo="sad", eye=0.55, jaw=0.15 + 0.08 * math.sin(i * 1.7), tail=20, tcurl=-2,
                 twave=3, tph=w, wing=0.0, tears=1.0)

        def fx(F, J, P, st, i=i):
            if st != "front":
                return
            e = J["H"](-8, -5)
            for n in range(4):                                  # suối nước mắt
                a = ((i / 12.0 + n / 4.0) % 1.0)
                droplet(F, add(e, (-2 - 3 * a, 26 * a * a + 2)), 1.5, 1 - a * 0.6)
            F.line([e, add(e, (-1, 6))], (150, 215, 255, 220), 1.6, layer="fg")
            if (i % 16) < 4:
                F.ell(add(J["nostril"], (-1, 2)), 1.6, 2.2, fill=(160, 220, 255, 200), layer="fg")
        out.append((P, fx))
    return out


@defset("beg")
def S_beg():
    T = 48
    out = []
    for i in range(T):
        w = TAU * i / T
        P = pose(brot=38, by=-37, fH=(4, 0), fHf=(7, 0), feet_rel=False, fF=(-24, -38), fFf=(-21, -36),
                 hx=-16, hy=-27, hrot=8 + 5 * math.sin(w), emo="beg", eye=1.0, blush=0.9, jaw=0.0,
                 tail=10, tcurl=-6, twave=16, tph=4 * w, wing=0.15, flap=8 * math.sin(4 * w))

        def fx(F, J, P, st, i=i):
            if st != "front":
                return
            for n in range(3):
                a = ((i / 24.0 + n / 3.0) % 1.0)
                c = add(J["hc"], dirv(-130 + n * 50), 30 + 4 * math.sin(a * 6))
                sparkle(F, c, 1.5 + 2.5 * math.sin(math.pi * a), math.sin(math.pi * a))
        out.append((P, fx))
    return out


# ───────────────────────── xuất ảnh ─────────────────────────
def render_set(name):
    spec = SETS[name]
    frames = spec["fn"]()
    ims = [render(P, fx, i)[0] for i, (P, fx) in enumerate(frames)]
    anchor = spec["anchor"]
    if anchor is None:
        anchor = drag_pivot()
    elif anchor == "g":
        anchor = Frame(frames[0][0]["G"]).g((0.0, 0.0))
    return ims, anchor


def sheet(ims, path, z=2, cols=None, bgc=(60, 64, 80, 255)):
    bb = None
    for im in ims:
        b = im.getbbox()
        if b:
            bb = b if bb is None else (min(bb[0], b[0]), min(bb[1], b[1]), max(bb[2], b[2]), max(bb[3], b[3]))
    bb = bb or (0, 0, 10, 10)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    cols = cols or len(ims)
    rows = (len(ims) + cols - 1) // cols
    out = Image.new("RGBA", (w * z * cols, h * z * rows), bgc)
    for k, im in enumerate(ims):
        c = im.crop(bb).resize((w * z, h * z), Image.LANCZOS)
        out.alpha_composite(c, ((k % cols) * w * z, (k // cols) * h * z))
    out.convert("RGB").save(path)
    return out.size


def preview(names, n=8, z=2, path="/tmp/rong_xem.png"):
    rows = []
    for nm in names:
        frames = SETS[nm]["fn"]()
        idx = sorted(set(int(k * (len(frames) - 1) / max(1, n - 1)) for k in range(n)))
        rows += [render(frames[i][0], frames[i][1], i)[0] for i in idx]
    return sheet(rows, path, z, cols=n)


# ───────────────────────── mô tả hành động (actions.xml) ─────────────────────────
FALL = "com.group_finity.mascot.action.Fall"
JUMP = "com.group_finity.mascot.action.Jump"
DRAG = "com.group_finity.mascot.action.Dragged"


def P_(st, vel=(0, 0), d=None, rev=False):
    return dict(set=st, vel=vel, d=d, rev=rev)


ACTIONS = [
    # cơ bản / hệ thống
    dict(name="Stand", type="Stay", border="Floor", poses=[P_("stand")]),
    dict(name="StandAlt", type="Stay", border="Floor", poses=[P_("standb")]),
    dict(name="Walk", type="Move", border="Floor", poses=[P_("walk", (-1.5, 0))]),
    dict(name="Run", type="Move", border="Floor", poses=[P_("run", (-5, 0))]),
    dict(name="Dash", type="Move", border="Floor", poses=[P_("dash", (-9, 0))]),
    dict(name="Fall", type="Embedded", cls=FALL, attrs=dict(RegistanceX="0.05", RegistanceY="0.1", Gravity="2"), poses=[P_("fall")]),
    dict(name="Thrown", type="Embedded", cls=FALL, attrs=dict(RegistanceX="0.02", RegistanceY="0.05", Gravity="2"), poses=[P_("spin")]),
    dict(name="Dragged", type="Embedded", cls=DRAG, poses=[P_("drag")]),
    dict(name="Land", type="Animate", border="Floor", poses=[P_("land")]),
    dict(name="GrabWall", type="Stay", border="Wall", poses=[P_("wallg")]),
    dict(name="ClimbWall", type="Move", border="Wall", poses=[P_("wallc", (0, -1.5))]),
    dict(name="GrabCeiling", type="Stay", border="Ceiling", poses=[P_("ceilg")]),
    dict(name="ClimbCeiling", type="Move", border="Ceiling", poses=[P_("ceilc", (-1.5, 0))]),
    dict(name="NhayLen", type="Embedded", cls=JUMP, attrs=dict(VelocityParam="22",
         TargetX="${mascot.anchor.x + (mascot.lookRight ? 240 : -240)}", TargetY="${mascot.anchor.y - 190}"), poses=[P_("fly")]),
    dict(name="ChayToiVach", type="Animate", border="Floor", poses=[P_("run", (-6, 0))]),
    dict(name="JumpToLeftWall", type="Embedded", cls=JUMP, attrs=dict(VelocityParam="22",
         TargetX="${mascot.environment.workArea.left}", TargetY="${mascot.environment.workArea.bottom - 260}"), poses=[P_("fly")]),
    dict(name="JumpToRightWall", type="Embedded", cls=JUMP, attrs=dict(VelocityParam="22",
         TargetX="${mascot.environment.workArea.right}", TargetY="${mascot.environment.workArea.bottom - 260}"), poses=[P_("fly")]),
    dict(name="LongDi_BamVachTrai", type="Sequence", refs=[("ChayToiVach", {}), ("JumpToLeftWall", {})]),
    dict(name="LongDi_BamVachPhai", type="Sequence", refs=[("ChayToiVach", {}), ("JumpToRightWall", {})]),
    # nghỉ
    dict(name="NamXuong", type="Animate", border="Floor", poses=[P_("lie")]),
    dict(name="DungDay", type="Animate", border="Floor", poses=[P_("lie", rev=True)]),
    dict(name="CuonMinh", type="Stay", border="Floor", poses=[P_("rest")]),
    dict(name="Ngu", type="Stay", border="Floor", poses=[P_("sleep")]),
    dict(name="LongNghi_CuonMinh", type="Sequence", refs=[("NamXuong", {}), ("CuonMinh", {"Duration": "420"}), ("DungDay", {})]),
    dict(name="LongNghi_Ngu", type="Sequence", refs=[("NamXuong", {}), ("Ngu", {"Duration": "1500"}), ("DungDay", {})]),
    # chiêu
    dict(name="Hong", type="Animate", border="Floor", poses=[P_("roar")]),
    dict(name="HacViem", type="Animate", border="Floor", poses=[P_("breath")]),
    dict(name="Trao", type="Animate", border="Floor", poses=[P_("claw")]),
    dict(name="VyTram", type="Animate", border="Floor", poses=[P_("tailw")]),
    dict(name="PhongDuc", type="Animate", border="Floor", poses=[P_("gust")]),
    dict(name="ChanDia", type="Animate", border="Floor", poses=[P_("stomp")]),
    dict(name="LoiGiang", type="Animate", border="Floor", poses=[P_("thunder")]),
    dict(name="TuKhi", type="Animate", border="Floor", poses=[P_("charge")]),
    dict(name="HacNhat", type="Animate", border="Floor", poses=[P_("ult")]),
    dict(name="LongKy_Hong", type="Sequence", refs=[("Hong", {})]),
    dict(name="LongKy_HacViem", type="Sequence", refs=[("HacViem", {})]),
    dict(name="LongKy_Trao", type="Sequence", refs=[("Trao", {})]),
    dict(name="LongKy_VyTram", type="Sequence", refs=[("VyTram", {})]),
    dict(name="LongKy_PhongDuc", type="Sequence", refs=[("PhongDuc", {})]),
    dict(name="LongKy_ChanDia", type="Sequence", refs=[("ChanDia", {})]),
    dict(name="LongKy_LoiGiang", type="Sequence", refs=[("LoiGiang", {})]),
    dict(name="LongBa_TuKhi", type="Sequence", refs=[("TuKhi", {})]),
    dict(name="LongBa_HacNhat", type="Sequence", refs=[("HacNhat", {})]),
    dict(name="LongBa_FullCombo", type="Sequence", refs=[("Hong", {}), ("Trao", {}), ("VyTram", {}), ("HacViem", {}),
                                                         ("LoiGiang", {}), ("HacNhat", {})]),
    # bay
    dict(name="CatCanh", type="Animate", border="Floor", poses=[P_("takeoff")]),
    dict(name="BayLen", type="Embedded", cls=JUMP, attrs=dict(VelocityParam="20",
         TargetX="${mascot.anchor.x + (mascot.lookRight ? 60 : -60)}", TargetY="${mascot.anchor.y - 300}"), poses=[P_("fly")]),
    dict(name="BayTheo", type="Embedded", cls=JUMP, attrs=dict(VelocityParam="16",
         TargetX="${mascot.environment.cursor.x}", TargetY="${mascot.environment.cursor.y - 60}"), poses=[P_("flydash")]),
    dict(name="LuonVong", type="Animate", poses=[P_("fly")], attrs=dict(Duration="48")),
    dict(name="HaCanh", type="Embedded", cls=FALL, attrs=dict(RegistanceX="0.08", RegistanceY="0.22", Gravity="1"), poses=[P_("fly")]),
    dict(name="BoNhao", type="Embedded", cls=FALL, attrs=dict(RegistanceX="0", RegistanceY="0", Gravity="5"), poses=[P_("dive")]),
    dict(name="VaDat", type="Animate", border="Floor", poses=[P_("impact")]),
    dict(name="LongPhi_BayVut", type="Sequence", refs=[("CatCanh", {}), ("BayLen", {}), ("LuonVong", {}), ("HaCanh", {}), ("Land", {})]),
    dict(name="LongPhi_BayTheoChuot", type="Sequence", refs=[("CatCanh", {}), ("BayLen", {}), ("BayTheo", {}), ("LuonVong", {}),
                                                             ("HaCanh", {}), ("Land", {})]),
    dict(name="LongPhi_ThienLongTruy", type="Sequence", refs=[("CatCanh", {}), ("BayLen", {}), ("BoNhao", {}), ("VaDat", {})]),
    # cảm xúc
    dict(name="CuoiKhay", type="Animate", border="Floor", poses=[P_("smug")]),
    dict(name="CuongNo", type="Animate", border="Floor", poses=[P_("rage")]),
    dict(name="AnVa", type="Stay", border="Floor", poses=[P_("tantrum")]),
    dict(name="Khoc", type="Stay", border="Floor", poses=[P_("cry")]),
    dict(name="NanNi", type="Stay", border="Floor", poses=[P_("beg")]),
    dict(name="LongTinh_CuoiKhay", type="Sequence", refs=[("CuoiKhay", {})]),
    dict(name="LongTinh_CuongNo", type="Sequence", refs=[("CuongNo", {})]),
    dict(name="LongTinh_AnVa", type="Sequence", refs=[("AnVa", {"Duration": "144"})]),
    dict(name="LongTinh_Khoc", type="Sequence", refs=[("Khoc", {"Duration": "144"})]),
    dict(name="LongTinh_NanNi", type="Sequence", refs=[("NanNi", {"Duration": "144"})]),
    # theo chuột
    dict(name="ChaseMouse", type="Move", border="Floor", attrs=dict(TargetX="${mascot.environment.cursor.x}",
         TargetY="${mascot.environment.floor.y}"), poses=[P_("run", (-8, 0))]),
    dict(name="LongTruy_DuoiChuot", type="Sequence", refs=[("ChaseMouse", {}), ("Trao", {})]),
]

FREQ = [("Stand", 80), ("StandAlt", 35), ("Walk", 100), ("Run", 35), ("Dash", 18),
        ("LongNghi_CuonMinh", 26), ("LongNghi_Ngu", 8),
        ("LongKy_Hong", 10), ("LongKy_HacViem", 9), ("LongKy_Trao", 12), ("LongKy_VyTram", 10), ("LongKy_PhongDuc", 9),
        ("LongKy_ChanDia", 9), ("LongKy_LoiGiang", 6), ("LongBa_TuKhi", 6), ("LongBa_HacNhat", 3), ("LongBa_FullCombo", 2),
        ("LongPhi_BayVut", 8), ("LongPhi_BayTheoChuot", 4), ("LongPhi_ThienLongTruy", 4),
        ("LongDi_BamVachTrai", 5), ("LongDi_BamVachPhai", 5),
        ("LongTinh_CuoiKhay", 8), ("LongTinh_CuongNo", 6), ("LongTinh_AnVa", 5), ("LongTinh_Khoc", 5), ("LongTinh_NanNi", 6),
        ("LongTruy_DuoiChuot", 4)]

META = {
    "name": "Cổ Long",
    "desc": "Hắc long thái cổ – rồng đen chibi, cánh màng, đuôi lưỡi đao, phun hắc viêm",
    "fly_prefix": "flydash",
    "drop_action": "LongPhi_ThienLongTruy",
    "wall_hit_action": "LongTinh_AnVa",
    "climb_behaviors": ["LongDi_BamVachTrai", "LongDi_BamVachPhai"],
    "groups": {"LongKy": "Long kỹ", "LongBa": "Bá khí", "LongPhi": "Bay lượn", "LongTinh": "Cảm xúc",
               "LongNghi": "Nghỉ ngơi", "LongDi": "Di chuyển", "LongTruy": "Theo chuột"},
    "labels": {
        "StandAlt": "Phì khói ngó nghiêng", "Run": "Phi nước đại", "Dash": "Lướt sát đất",
        "LongNghi_CuonMinh": "Cuộn mình nằm nghỉ", "LongNghi_Ngu": "Ngủ say (khò khò)",
        "LongKy_Hong": "Long hống (gầm sóng âm)", "LongKy_HacViem": "Hắc viêm long tức (phun lửa đen)",
        "LongKy_Trao": "Long trảo liên hoàn", "LongKy_VyTram": "Thần vĩ trảm (quật đuôi)",
        "LongKy_PhongDuc": "Phong dực cuồng phong (vỗ cánh)", "LongKy_ChanDia": "Chấn địa (dậm nứt đất)",
        "LongKy_LoiGiang": "Lôi long giáng thế (gọi sét)", "LongBa_TuKhi": "Tụ long khí (nạp năng lượng)",
        "LongBa_HacNhat": "Hắc nhật diệt thế (chiêu cuối)", "LongBa_FullCombo": "THÁI CỔ LONG HOÀNG QUYẾT (full combo)",
        "LongPhi_BayVut": "Cất cánh bay vút", "LongPhi_BayTheoChuot": "Bay theo chuột",
        "LongPhi_ThienLongTruy": "Thiên long trụy (bổ nhào tạo hố)", "LongDi_BamVachTrai": "Leo vách trái",
        "LongDi_BamVachPhai": "Leo vách phải", "LongTinh_CuoiKhay": "Cười khẩy phì khói", "LongTinh_CuongNo": "Cuồng nộ",
        "LongTinh_AnVa": "Ăn vạ lăn đùng", "LongTinh_Khoc": "Ngồi khóc", "LongTinh_NanNi": "Nằn nì mắt long lanh",
        "LongTruy_DuoiChuot": "Đuổi theo chuột",
    },
    "triggers": {
        "L1": {"act": "LongKy_Trao", "cmd": "upcoming"}, "L2": {"act": "", "cmd": "manager"},
        "L3": {"act": "LongBa_FullCombo", "cmd": ""}, "LH": {"act": "LongBa_TuKhi", "cmd": ""},
        "R1": {"act": "", "cmd": "menu"}, "R2": {"act": "LongTinh_CuongNo", "cmd": ""},
        "R3": {"act": "LongTinh_NanNi", "cmd": ""}, "RH": {"act": "LongPhi_BayTheoChuot", "cmd": ""},
        "WU": {"act": "LongPhi_BayVut", "cmd": ""}, "WD": {"act": "LongNghi_CuonMinh", "cmd": ""},
        "M1": {"act": "LongTruy_DuoiChuot", "cmd": ""},
        "E_REMIND": {"act": "LongKy_Hong"}, "E_DONE": {"act": "LongTinh_CuoiKhay"}, "E_SNOOZE": {"act": "LongTinh_AnVa"},
        "E_SKIP": {"act": "LongTinh_Khoc"}, "E_BREAK": {"act": "LongNghi_CuonMinh"}, "E_GREET": {"act": "LongKy_PhongDuc"},
        "E_SLEEP": {"act": "LongNghi_Ngu"}, "E_WAKE": {"act": "LongKy_Hong"},
        "E_TYPING": {"act": "LongBa_TuKhi"}, "E_DELETING": {"act": "LongKy_VyTram"},
        "S_L1": {"act": "LongKy_Trao"}, "S_L2": {"act": "LongKy_HacViem"}, "S_R1": {"act": "LongKy_VyTram"},
        "S_R2": {"act": "LongBa_HacNhat"}, "S_WU": {"act": "LongKy_LoiGiang"}, "S_WD": {"act": "LongKy_ChanDia"},
        "S_M1": {"act": "LongKy_Hong"}, "S_HK": {"act": "LongBa_FullCombo"},
    },
}

XMLNS = ('xmlns="http://www.group-finity.com/Mascot" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
         'xsi:schemaLocation="http://www.group-finity.com/Mascot Mascot.xsd"')


def _attr(d):
    return "".join(' %s="%s"' % (k, v.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))
                   for k, v in d.items())


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


def _num(v):
    return ("%d" % v) if float(v).is_integer() else ("%g" % v)


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
    ims, anchor = render_set(name)
    bb = None
    for im in ims:
        b = im.getbbox()
        if b:
            bb = b if bb is None else (min(bb[0], b[0]), min(bb[1], b[1]), max(bb[2], b[2]), max(bb[3], b[3]))
    bb = (max(0, bb[0] - 2), max(0, bb[1] - 2), min(CW, bb[2] + 2), min(CH, bb[3] + 2))
    files = []
    for k, im in enumerate(ims):
        fn = "%s%02d.png" % (name, k)
        q = im.crop(bb).quantize(256, method=Image.Quantize.FASTOCTREE)
        q.save(os.path.join(out_dir, fn), optimize=True)
        files.append(fn)
    ax = int(round(anchor[0] - X0 - bb[0]))
    ay = int(round(anchor[1] - Y0 - bb[1]))
    return name, dict(files=files, anchor=(ax, ay), d=SETS[name]["d"], size=(bb[2] - bb[0], bb[3] - bb[1]))


def main(argv):
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(base, "NhanVat", "CoLong")
    conf = os.path.join(out, "conf")
    os.makedirs(conf, exist_ok=True)
    names = [a for a in argv if a in SETS] or list(SETS)
    if names == list(SETS):
        for f in os.listdir(out):
            if f.endswith(".png"):
                os.remove(os.path.join(out, f))
    info_path = os.path.join(conf, "frames.json")
    info = {}
    if os.path.exists(info_path):
        info = json.load(open(info_path, encoding="utf-8"))
    jobs = [(n, out) for n in names]
    try:
        import multiprocessing as mp
        with mp.Pool(max(1, (os.cpu_count() or 2))) as pool:
            res = pool.map(export_set, jobs)
    except Exception:
        res = [export_set(j) for j in jobs]
    for n, inf in res:
        info[n] = inf
        print("%-9s %3d khung  %dx%d" % (n, len(inf["files"]), inf["size"][0], inf["size"][1]))
    json.dump(info, open(info_path, "w", encoding="utf-8"), indent=0)
    with open(os.path.join(conf, "actions.xml"), "w", encoding="utf-8") as f:
        f.write(build_actions_xml(info))
    with open(os.path.join(conf, "behaviors.xml"), "w", encoding="utf-8") as f:
        f.write(build_behaviors_xml())
    with open(os.path.join(conf, "chibi.json"), "w", encoding="utf-8") as f:
        json.dump(META, f, ensure_ascii=False, indent=1)
    print("Xong:", out)


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--xem":
        print(preview(sys.argv[2].split(","), n=int(sys.argv[3]) if len(sys.argv) > 3 else 8))
    else:
        main(sys.argv[1:])
