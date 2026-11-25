# -*- coding: utf-8 -*-
"""Nhân vật Cổ Long: bộ hình đầy đủ, đổi nhân vật giữ riêng bộ gán chuột, mọi chiêu chạy được."""
import os

from common import load, make_app, check, finish

C = load()
app = make_app(C)


def run():
    packs = dict(C.available_packs())
    check(packs.get("builtin:CoLong") == "Cổ Long", "danh sách nhân vật có Cổ Long")
    pk = C.ShimejiPack(os.path.join(C.NHANVAT_DIR, "CoLong"))
    check(pk.ok and pk.name == "Cổ Long", "đọc được bộ Cổ Long (%d hành động)" % len(pk.actions))
    missing = [p.img for a in pk.actions.values() for p in a.poses if not os.path.isfile(os.path.join(pk.img_dir, p.img))]
    check(not missing, "mọi khung hình đều có file ảnh (%d thiếu)" % len(missing))
    bad_ref = [r for a in pk.actions.values() for r, _ in a.refs if r not in pk.actions]
    check(not bad_ref, "chuỗi chiêu chỉ gọi hành động có thật")
    for n in ("Stand", "Walk", "Fall", "Dragged", "Thrown", "Land", "GrabWall", "ClimbWall", "GrabCeiling", "ClimbCeiling"):
        check(n in pk.actions, "có hành động hệ thống " + n)
    acts = [v["act"] for v in pk.meta["triggers"].values() if v.get("act")]
    check(all(a in pk.behaviors for a in acts), "gán chuột / sự kiện mặc định đều trỏ tới chiêu có thật")

    aoden_tr = dict(app.store.s["triggers"])
    tr = dict(aoden_tr)
    tr["L3"] = {"act": "TrangThai_NanNi", "cmd": ""}
    app.set_setting("triggers", tr)
    app.set_setting("pet_name", "Đen Đủi")
    app.switch_pack("builtin:CoLong")
    s = app.store.s
    check(app.pet.pack.name == "Cổ Long" and s["pet_name"] == "Cổ Long", "đổi sang Cổ Long, tên gọi đổi theo")
    check(s["triggers"]["L3"]["act"] == "LongBa_FullCombo" and s["drop_action"] == "LongPhi_LaoXuongDapDat",
          "Cổ Long dùng bộ gán chuột riêng")
    check(C.beh_label("LongKy_PhunLua") == "Phun lửa" and C.beh_group("LongKy_PhunSamSet") == "Long kỹ",
          "tên chiêu / nhóm hiện tiếng Việt")
    eng = app.pet.engine
    check(len(eng.fly_poses()) == 6 and eng.fly_poses()[0].img.startswith("flydash"), "lao tới chỗ bấm dùng tư thế bay lướt")
    check(eng.drop_parts("LongPhi_LaoXuongDapDat") == ("LaoXuong", ["DapDat"]), "thả rơi = Lao xuống & đập đất")
    tr = dict(s["triggers"])
    tr["R2"] = {"act": "LongKy_CuonThan", "cmd": ""}
    app.set_setting("triggers", tr)
    app.switch_pack("")
    s = app.store.s
    check(app.pet.pack.name == "Áo Đen" and s["triggers"]["L3"]["act"] == "TrangThai_NanNi" and s["pet_name"] == "Đen Đủi",
          "quay về Áo Đen: lấy lại đúng bộ gán và tên cũ")
    app.switch_pack("builtin:CoLong")
    check(app.store.s["triggers"]["R2"]["act"] == "LongKy_CuonThan", "sang lại Cổ Long: giữ chỉnh sửa trước đó")

    pet, eng = app.pet, app.pet.engine
    a = pet.env.area_at(eng.ax, eng.ay)
    for _ in range(150):
        eng.tick()
    n0 = os.path.getsize(C.ERR_FILE) if os.path.exists(C.ERR_FILE) else 0
    for n in pet.pack.user_behaviors():
        eng.gen = None
        eng.ax, eng.ay, eng.vx, eng.vy = (a[0] + a[2]) / 2, a[3], 0, 0
        if not eng.can_now(n):
            continue
        eng.force(n)
        ticks, inside = 0, True
        while eng.cur == n and ticks < 4000:
            eng.tick()
            if ticks % 5 == 0:
                pet.render()
            ticks += 1
            inside &= a[0] - 1 <= eng.ax <= a[2] + 1 and a[1] - 1 <= eng.ay <= a[3] + 1
        check(ticks < 4000 and inside, "%-36s chạy %4d nhịp, tự kết thúc" % (C.beh_label(n), ticks))
        for _ in range(200):
            eng.tick()
    eng.start_drag()
    for _ in range(10):
        eng.tick()
    eng.end_drag()
    for _ in range(400):
        eng.tick()
    check(pet.env.on_floor(eng.ax, eng.ay) is not None, "xách lên thả ra -> lao xuống đập đất")
    n1 = os.path.getsize(C.ERR_FILE) if os.path.exists(C.ERR_FILE) else 0
    check(n1 == n0, "không phát sinh lỗi khi chạy")
    finish(app, C)


app.root.after(1500, run)
app.root.mainloop()
