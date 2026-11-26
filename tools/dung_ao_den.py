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


def save(name, im, anchor, meta):
    im.save(os.path.join(PACK, name + ".png"), optimize=True)
    meta[name] = [int(anchor[0]), int(anchor[1])]


def ring(im, cx, cy, rx, ry, al, w=2, col=(225, 235, 255)):
    d = ImageDraw.Draw(im)
    d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), outline=col + (int(al),), width=w)


def main():
    meta = {}
    # ── bay ngang: tư thế lao (jumpup), xoay cho thân nằm ngang hơn ──
    bases = [load("jumpup0"), load("jumpup1")]
    for f in range(8):
        b = padded(bases[f // 2 % 2], 60)
        b = b.rotate(18, Image.BICUBIC, expand=False)               # hạ đầu xuống: thân gần nằm ngang
        b = flutter(b, f * math.pi / 4, 5.0, side=1)
        bob = int(round(2 * math.sin(f * math.pi / 4)))
        b = b.transform(b.size, Image.AFFINE, (1, 0, 0, 0, 1, -bob), Image.BICUBIC)
        b = streaks(b, f)
        b, _ = trim(b)
        save("x_bay%d" % f, b, (b.width // 2, int(b.height * 0.78)), meta)
    for nm, ang in (("x_baylen", -16), ("x_bayxuong", 40)):
        for f in range(4):
            b = padded(bases[f // 2 % 2], 70)
            b = b.rotate(18 + ang, Image.BICUBIC, expand=False)
            b = flutter(b, f * math.pi / 2, 5.0, side=1)
            b = streaks(b, f + 3, n=5)
            b, _ = trim(b)
            save("%s%d" % (nm, f), b, (b.width // 2, int(b.height * 0.78)), meta)
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
    with open(os.path.join(PACK, "conf", "x_khung.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=0)
    print(len(meta), "khung ->", PACK)


if __name__ == "__main__":
    main()
