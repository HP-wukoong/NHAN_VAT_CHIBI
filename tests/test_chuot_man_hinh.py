# -*- coding: utf-8 -*-
"""Thao tác chuột trên màn hình: phân loại cú bấm, bay tới điểm bấm, nền tạm, chiêu chờ."""
from common import load, make_app, check, finish

C = load()
app = make_app(C)
pet, eng, gm = app.pet, app.pet.engine, app.gmouse
app.store.s["free_master"] = False
fired = []
real_fire = gm.fire


def step1():
    for _ in range(300):
        eng.tick()
    gm.fire = lambda k, x, y: fired.append(k)
    gm.q.put(("L", "down", 600, 300))
    gm.q.put(("L", "up", 602, 301))
    gm.poll()


def step2():
    check(fired == ["S_L1"], "trái 1 lần -> S_L1")
    fired.clear()
    for _ in range(2):
        gm.q.put(("L", "down", 600, 300))
        gm.q.put(("L", "up", 600, 300))
    gm.poll()


def step3():
    check(fired == ["S_L2"], "trái 2 lần -> S_L2")
    fired.clear()
    gm.q.put(("L", "down", 100, 100))
    gm.q.put(("L", "up", 400, 300))
    gm.poll()


def step4():
    check(fired == [], "kéo chọn vùng không bị tính là bấm")
    gm.q.put(("W", 120, 500, 400))
    gm.q.put(("W", 120, 500, 400))
    gm.q.put(("HK",))
    gm.poll()
    check(fired == ["S_WU", "S_HK"], "lăn lên (chống dội) + phím Ctrl+Alt+X")
    gm.fire = real_fire
    gm.fire("S_L1", 700, 300)
    z = pet.zoom
    for _ in range(150):
        eng.tick()
        if abs(eng.ax - 700 / z) < 1 and abs(eng.ay - 300 / z) < 1:
            break
    check(abs(eng.ax - 700 / z) < 1 and abs(eng.ay - 300 / z) < 1, "bay tới đúng điểm bấm")
    check(pet.env.temp is not None, "giữa không trung có nền tạm để đứng tung chiêu")
    for _ in range(10):
        eng.tick()
    check(eng.cur == app.store.s["triggers"]["S_L1"]["act"], "đang tung đúng chiêu đã gán")
    for _ in range(300):
        eng.tick()
        if pet.env.temp is None:
            break
    check(pet.env.temp is None, "diễn xong thì bỏ nền tạm")
    for _ in range(200):
        eng.tick()
    a = pet.env.area_at(eng.ax, eng.ay)
    check(abs(eng.ay - a[3]) < 2, "rơi xuống đất sau khi diễn")
    eng.gen, eng.ay, eng.forced = None, a[1] + 50, "Fall"
    eng.tick()
    eng.force("BieuCam_HoaCuong")
    check(eng.pending is not None, "đang rơi: giữ lệnh chờ")
    for _ in range(200):
        eng.tick()
        if eng.cur == "BieuCam_HoaCuong":
            break
    check(eng.cur == "BieuCam_HoaCuong", "chạm đất là ra chiêu đã chờ")
    finish(app, C)


for i, f in enumerate([step1, step2, step3, step4]):
    app.root.after(1500 + i * 600, f)
app.root.mainloop()
