#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cắt các hiệu ứng (sấm sét, nổ, ma pháp...) từ ảnh của người dùng -> HieuUng/*.png cho hiệu ứng gõ phím
và hiệu ứng tiếp đất của Cổ Long.

Ảnh gốc ở tools/hieu_ung_nguon/. Ảnh 2–7 đã có nền trong suốt thật; ảnh 1 là nền caro giả -> tách nền.
Chạy: python tools/cat_hieu_ung.py   (cần Pillow + numpy)
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "hieu_ung_nguon")
OUT = os.path.join(os.path.dirname(HERE), "HieuUng")
MAXD = 360                                   # cạnh dài nhất của ảnh hiệu ứng lưu ra

S7 = "7_bang_tim_vang.png"
S2 = "2_bang_vang.png"
CUTS = {
    # ảnh đơn
    "tim_no": ("1_tim_no.png", None), "no_vang": ("3_no_vang.png", None), "no_vang_tim": ("4_no_vang_tim.png", None),
    "no_dat": ("5_no_dat.png", None), "tia_chop": ("6_tia_chop.png", None),
    # bảng tím vàng
    "loidien1": (S7, (7, 42, 120, 300)), "loidien2": (S7, (120, 42, 220, 300)), "loidien3": (S7, (220, 42, 352, 300)),
    "loiphat1": (S7, (360, 42, 460, 300)), "loiphat2": (S7, (460, 42, 550, 300)), "loiphat3": (S7, (553, 42, 675, 300)),
    "loilong": (S7, (683, 42, 950, 305)), "loikiep": (S7, (950, 42, 1170, 305)), "loiquang": (S7, (1178, 42, 1362, 305)),
    "loian": (S7, (1365, 42, 1530, 305)),
    "settim1": (S7, (7, 338, 95, 513)), "settim2": (S7, (95, 338, 187, 513)), "settim3": (S7, (187, 330, 275, 513)),
    "settim4": (S7, (275, 330, 335, 513)), "settim5": (S7, (335, 330, 400, 513)),
    "xoantim1": (S7, (400, 330, 605, 513)), "xoantim2": (S7, (607, 322, 770, 513)), "xoantim3": (S7, (773, 315, 988, 513)),
    "xoantim4": (S7, (988, 315, 1180, 513)), "cottim": (S7, (1180, 315, 1287, 513)), "gaitim": (S7, (1287, 315, 1362, 513)),
    "matrao1": (S7, (7, 542, 210, 722)), "matrao2": (S7, (207, 542, 335, 722)), "matrao3": (S7, (327, 542, 515, 722)),
    "madoc1": (S7, (520, 545, 662, 722)), "madoc2": (S7, (660, 545, 805, 722)), "madoc3": (S7, (805, 540, 1008, 722)),
    "bingan1": (S7, (1013, 548, 1135, 722)), "bingan2": (S7, (1133, 560, 1200, 722)), "bingan3": (S7, (1198, 530, 1362, 722)),
    "bingan4": (S7, (1365, 530, 1530, 722)),
    "daulau1": (S7, (7, 760, 97, 1000)), "daulau2": (S7, (95, 740, 295, 1000)), "daulau3": (S7, (293, 735, 475, 1000)),
    "phikiem1": (S7, (475, 760, 622, 1000)), "phikiem2": (S7, (607, 760, 855, 1000)), "phikiem3": (S7, (833, 750, 1030, 1000)),
    "phikiem4": (S7, (1013, 745, 1310, 1000)), "phikiem5": (S7, (1310, 730, 1533, 1000)),
    # bảng vàng
    "kimtinh1": (S2, (27, 10, 330, 305)), "kimtinh2": (S2, (340, 7, 668, 305)), "vongvang": (S2, (673, 13, 880, 300)),
    "cotvang1": (S2, (887, 7, 1088, 313)), "cotvang2": (S2, (1088, 7, 1295, 313)), "nhanhvang": (S2, (1313, 7, 1522, 353)),
    "setvang1": (S2, (13, 313, 115, 480)), "setvang2": (S2, (125, 313, 195, 480)), "setvang3": (S2, (195, 313, 268, 480)),
    "setvang4": (S2, (272, 313, 388, 480)), "setvang5": (S2, (392, 313, 482, 480)), "setvang6": (S2, (482, 313, 562, 480)),
    "setvang7": (S2, (562, 313, 662, 480)), "setvang8": (S2, (662, 313, 768, 480)), "setvang9": (S2, (768, 313, 868, 480)),
    "tinhvang": (S2, (1053, 313, 1347, 480)), "diavang": (S2, (1353, 313, 1522, 482)),
    "xoanvang1": (S2, (18, 483, 222, 627)), "xoanvang2": (S2, (225, 483, 550, 627)), "hoanvang1": (S2, (553, 483, 768, 627)),
    "hoanvang2": (S2, (773, 483, 1060, 627)), "vomvang": (S2, (1060, 483, 1342, 627)), "bungvang": (S2, (1345, 483, 1515, 627)),
    "datvang1": (S2, (13, 627, 230, 747)), "datvang2": (S2, (265, 627, 550, 747)), "datvang3": (S2, (553, 627, 895, 747)),
    "datvang4": (S2, (898, 627, 1162, 747)), "datvang5": (S2, (1165, 627, 1328, 747)), "truvong": (S2, (1313, 627, 1533, 990)),
    "longvang1": (S2, (7, 760, 182, 1013)), "longvang2": (S2, (180, 760, 408, 1013)), "longvang3": (S2, (405, 760, 630, 1013)),
    "chau": (S2, (640, 760, 835, 1013)), "vongran": (S2, (840, 760, 1055, 1013)), "luatru": (S2, (1058, 760, 1302, 1013)),
}
# nhãn chữ trong bảng tím vàng (xoá khỏi ảnh)
LABELS7 = [(20, 8, 180, 40), (385, 8, 545, 40), (700, 8, 850, 40), (970, 8, 1115, 40), (1195, 8, 1345, 40), (1375, 8, 1520, 40),
           (8, 308, 220, 340), (8, 512, 155, 542), (510, 508, 675, 542), (978, 515, 1142, 548), (8, 725, 232, 758),
           (512, 722, 735, 758)]


def load(fn):
    im = Image.open(os.path.join(SRC, fn)).convert("RGBA")
    if fn.startswith("1_"):                                  # nền caro giả -> trong suốt
        a = np.asarray(im).astype(np.float32)
        lum = a[..., :3].mean(2)
        sat = a[..., :3].max(2) - a[..., :3].min(2)
        bg = np.clip((lum - 150) / 35.0, 0, 1) * np.clip((40 - sat) / 18.0, 0, 1)
        al = 1 - bg
        # điểm lẻ mờ (vân caro sót) -> bỏ; lõi trắng nằm giữa vùng tím -> giữ
        from PIL import ImageFilter
        dens = np.asarray(Image.fromarray((al * 255).astype(np.uint8)).filter(ImageFilter.BoxBlur(3))) / 255.0
        al = np.where(dens < 0.35, al * np.clip((dens - 0.15) / 0.2, 0, 1), al)
        # lõi trắng của tia sét: điểm sáng mà xung quanh (bán kính ~6px) có nhiều điểm tím đậm
        vio = ((a[..., 2] - a[..., 1]) > 40).astype(np.uint8) * 255
        near = np.asarray(Image.fromarray(vio).filter(ImageFilter.BoxBlur(6))) / 255.0
        core = (lum > 195) & (near > 0.22)
        al = np.where(core, np.maximum(al, np.clip((near - 0.22) / 0.15, 0, 1)), al)
        a[..., 3] = 255 * al
        im = Image.fromarray(a.astype(np.uint8), "RGBA")
    if fn == S7:
        d = ImageDraw.Draw(im)
        for b in LABELS7:
            d.rectangle(b, fill=(0, 0, 0, 0))
    return im


def main():
    os.makedirs(OUT, exist_ok=True)
    cache = {}
    for name, (fn, box) in CUTS.items():
        if fn not in cache:
            cache[fn] = load(fn)
        im = cache[fn] if box is None else cache[fn].crop(box)
        a = np.asarray(im.getchannel("A")).astype(np.float32)
        if box is not None:                                  # mờ dần sát mép khung cắt (không bị đứt thẳng)
            hh, ww = a.shape
            fx_ = np.minimum(np.arange(ww), np.arange(ww)[::-1])
            fy_ = np.minimum(np.arange(hh), np.arange(hh)[::-1])
            a = a * np.clip(np.minimum.outer(fy_, fx_) / 10.0, 0, 1)
        a = Image.fromarray(a.astype(np.uint8)).point(lambda v: 0 if v < 10 else v)
        im.putalpha(a)
        bb = a.getbbox()
        im = im.crop(bb)
        z = min(1.0, MAXD / float(max(im.size)))
        if z < 1:
            im = im.resize((max(1, int(im.width * z)), max(1, int(im.height * z))), Image.LANCZOS)
        im.save(os.path.join(OUT, name + ".png"), optimize=True)          # giữ đủ màu + độ trong (để tách lớp)
    print(len(CUTS), "hiệu ứng ->", OUT)


# ảnh riêng cho Lôi tinh liên hoàn / Lôi thương: xoay cho trục chính nằm ngang (đầu tia, mũi thương quay về bên phải)
XOAY = {
    "loi_lienhoan": ("8_loi_lienhoan.png", -70.0, 480, 0.62),  # tia sét dọc chéo -> nằm ngang (ép dẹt để chạy sát dòng chữ)
    "loi_thuong": ("9_loi_thuong.png", -28.3, 480, 1.0),       # thương chéo -> nằm ngang, mũi bên phải
}


def xoay():
    os.makedirs(OUT, exist_ok=True)
    for name, (fn, ang, md, sy) in XOAY.items():
        im = Image.open(os.path.join(SRC, fn)).convert("RGBA")
        im = im.rotate(ang, Image.BICUBIC, expand=True)
        a = im.getchannel("A").point(lambda v: 0 if v < 10 else v)
        im.putalpha(a)
        im = im.crop(a.getbbox())
        z = min(1.0, md / float(max(im.size)))
        im = im.resize((max(1, int(im.width * z)), max(1, int(im.height * z * sy))), Image.LANCZOS)
        im.save(os.path.join(OUT, name + ".png"), optimize=True)
        print(name, im.size)


if __name__ == "__main__":
    if "--xoay" not in sys.argv:
        main()
    xoay()
