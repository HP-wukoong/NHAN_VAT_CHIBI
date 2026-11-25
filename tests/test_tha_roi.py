# -*- coding: utf-8 -*-
"""Kéo xách nhân vật rồi thả: lao cắm đầu xuống, chạm đất nện tạo hố."""
from common import load, make_app, check, finish

C = load()
app = make_app(C)
pet, eng = app.pet, app.pet.engine
app.store.s["free_master"] = False


def drag_to(x, y, steps=5):
    eng.start_drag()
    for i in range(steps):
        pet.env.cursor = (x + i * 3, y)
        eng.tick()
    eng.end_drag()


def run():
    for _ in range(200):
        eng.tick()
    a = pet.env.area_at(eng.ax, eng.ay)
    check("VaCham_RoiHoDat" in eng.drop_choices(), "Rơi tạo hố có trong danh sách chọn khi thả")
    drag_to((a[0] + a[2]) / 2, a[1] + 120)
    eng.tick()
    check(eng.cur == "VaCham_RoiHoDat", "thả trên cao -> chạy Rơi tạo hố")
    imgs, landed_at = [], None
    for i in range(400):
        eng.tick()
        imgs.append(eng.pose.img)
        if landed_at is None and pet.env.on_floor(eng.ax, eng.ay):
            landed_at = i
        if eng.cur != "VaCham_RoiHoDat":
            break
    falling = imgs[:landed_at] if landed_at else imgs
    check(falling and all(x.startswith("fh") for x in falling[:-1]), "đang rơi: tư thế lao cắm đầu (fh*)")
    check(any(x.startswith("crater") for x in imgs), "chạm đất: nện tạo hố (crater*)")
    check(abs(eng.ay - a[3]) < 2, "kết thúc nằm trên mặt đất")
    for _ in range(100):
        eng.tick()
    eng.gen = None
    eng.ax, eng.ay = (a[0] + a[2]) / 2, a[3]
    eng.tick()
    drag_to((a[0] + a[2]) / 2, a[3] - 15)
    eng.tick()
    check(eng.cur != "VaCham_RoiHoDat", "thả sát đất -> tiếp đất bình thường, không nện hố")
    for _ in range(100):
        eng.tick()
    app.store.s["drop_action"] = ""
    drag_to((a[0] + a[2]) / 2, a[1] + 120)
    eng.tick()
    check(eng.cur in ("Fall", "Thrown"), "chọn 'Rơi thường' -> rơi kiểu cũ")
    app.store.s["drop_action"] = "VaCham_RoiHoDat"
    for _ in range(200):
        eng.tick()
    # quăng mạnh sang trái vào tường
    eng.start_drag()
    x0 = a[0] + 260
    for i in range(5):
        pet.env.cursor = (x0 - i * 45, a[1] + 200)
        eng.tick()
    eng.end_drag()
    seen = set()
    for _ in range(600):
        eng.tick()
        seen.add(eng.cur)
        if eng.cur == "TrangThai_AnVa":
            break
    check(eng.cur == "TrangThai_AnVa", "quăng đập vào tường rồi rơi xuống -> ăn vạ")
    check("VaCham_RoiHoDat" in seen and abs(eng.ay - a[3]) < 2, "đập tường thì bỏ nện hố, nằm ăn vạ trên mặt đất")
    for _ in range(400):
        eng.tick()
    app.store.s["wall_hit_action"] = ""
    eng.start_drag()
    for i in range(5):
        pet.env.cursor = (x0 - i * 45, a[1] + 200)
        eng.tick()
    eng.end_drag()
    grabbed = False
    for _ in range(300):
        eng.tick()
        if eng.cur in ("GrabWall", "ClimbWall"):
            grabbed = True
            break
    check(grabbed, "chọn 'Bám luôn vào tường' -> bám tường như cũ")
    app.store.s["wall_hit_action"] = "TrangThai_AnVa"
    # không lấn ra ngoài màn hình
    m = app.monitors[0]
    worst = 0
    for edge in (a[0], a[2]):
        for n in ("GrabWall", "ChienDau_KiemKhi", "BaKhi_FullCombo", "Stand"):
            eng.gen = None
            eng.ax, eng.ay = edge, a[3]
            eng.start(n)
            for _ in range(40):
                eng.tick()
                pet.render()
                worst = max(worst, m[0] - pet.x, pet.x + pet.W - m[2], m[1] - pet.y, pet.y + pet.H - m[3])
    check(worst <= 0, "sát mép trái/phải: khung hình nhân vật luôn nằm trong màn hình (lấn %dpx)" % max(0, worst))
    finish(app, C)


app.root.after(1500, run)
app.root.mainloop()
