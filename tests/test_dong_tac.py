# -*- coding: utf-8 -*-
"""Mọi động tác của nhân vật đều chạy được, tự kết thúc và không văng khỏi màn hình."""
from common import load, make_app, check, finish

C = load()
app = make_app(C)
pet, eng = app.pet, app.pet.engine


def run():
    a = pet.env.area_at(eng.ax, eng.ay)
    for _ in range(200):
        eng.tick()
    check(pet.env.on_floor(eng.ax, eng.ay) is not None, "thả ra từ trên cao -> rơi xuống đất")
    for n in pet.pack.user_behaviors():
        eng.gen = None
        eng.ax, eng.ay, eng.vx, eng.vy = (a[0] + a[2]) / 2, a[3], 0, 0
        if not eng.can_now(n):
            continue                                   # ví dụ "Bị treo" chỉ diễn khi đang ở trên trần
        eng.force(n)
        ticks, inside = 0, True
        while eng.cur == n and ticks < 3000:
            eng.tick()
            ticks += 1
            inside &= a[0] - 1 <= eng.ax <= a[2] + 1 and a[1] - 1 <= eng.ay <= a[3] + 1
        check(ticks < 3000 and inside, "%-26s tự kết thúc sau %d nhịp, trong màn hình" % (C.beh_label(n), ticks))
        for _ in range(300):
            eng.tick()
    finish(app, C)


app.root.after(1500, run)
app.root.mainloop()
