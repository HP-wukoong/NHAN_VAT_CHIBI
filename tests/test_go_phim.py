# -*- coding: utf-8 -*-
"""Hiệu ứng gõ phím: phân loại phím (kể cả bộ gõ tiếng Việt), gộp khi gõ nhanh, bỏ qua ô mật khẩu, nhân vật phản ứng."""
from common import load, make_app, check, finish

C = load()
k = C.classify_key
check(k(0x41, False, False, False, False) == "T", "chữ cái -> gõ")
check(k(0x20, False, False, False, False) == "T", "phím cách -> gõ")
check(k(0x08, False, False, False, False) == "D", "Backspace -> xoá")
check(k(0x2E, False, False, False, False) == "D", "Delete -> xoá")
check(k(0x08, False, True, False, False) == "D", "Ctrl+Backspace -> xoá")
check(k(0x43, False, True, False, False) is None, "Ctrl+C không tính")
check(k(0x09, False, False, True, False) is None, "Alt+Tab không tính")
check(k(0x25, False, False, False, False) is None, "phím mũi tên không tính")
check(k(0x08, True, False, False, False) is None, "Backspace giả lập của Unikey/EVKey (bỏ dấu) không bị chém nhầm")
check(k(0xE7, True, False, False, False) == "T", "ký tự Unicode do bộ gõ tiếng Việt gửi -> gõ")

app = make_app(C)
fx = app.keyfx
calls = []
app.pet.engine.force = lambda n, wait=True: calls.append(("force", n)) or True
app.pet.engine.fly_and_act = lambda x, y, n, hold=0.0: calls.append(("fly", n)) or True


def run():
    C.caret_info = lambda: ((400, 300), False)
    n0 = fx.bolt.played
    for _ in range(10):
        fx.on_key("T")                          # 10 phím trong tích tắc
    check(fx.bolt.played - n0 == 1, "gõ dồn dập -> gộp hiệu ứng, không làm chậm máy")
    fx.t_last["T"] = 0
    fx.on_key("T")
    check(fx.bolt.played - n0 == 2 and fx.last_pos == (400, 300), "hiệu ứng đặt đúng vị trí con trỏ nhập")
    fx.on_key("D")
    check(fx.slash.played == 1, "xoá -> loạn đao chém")
    check(len(fx.bolt.variants) == fx.bolt.VARIANTS and len(fx.bolt.variants[0]) == 6, "lôi điện: 5 biến thể x 6 khung")
    C.caret_info = lambda: ((400, 300), True)
    p = fx.bolt.played
    fx.t_last["T"] = 0
    fx.on_key("T")
    check(fx.bolt.played == p, "ô mật khẩu: không hiệu ứng")
    C.caret_info = lambda: (None, False)
    fx.t_last["T"] = 0
    fx.on_key("T")
    check(fx.bolt.played == p + 1, "phần mềm không báo con trỏ nhập -> hiệu ứng cạnh chuột")
    app.store.s["key_fx"] = False
    fx.t_last["T"] = 0
    fx.on_key("T")
    check(fx.bolt.played == p + 1, "tắt trong Cài đặt -> không còn hiệu ứng")
    app.store.s["key_fx"] = True
    C.caret_info = lambda: ((500, 300), False)
    calls.clear()
    fx.hist["T"].clear()
    for _ in range(25):
        fx.on_key("T")
    check(("force", app.store.s["triggers"]["E_TYPING"]["act"]) in calls, "gõ liên tục -> nhân vật nạp năng lượng")
    calls.clear()
    for _ in range(25):
        fx.on_key("T")
    check(not calls, "có thời gian nghỉ giữa 2 lần phản ứng")
    for _ in range(8):
        fx.on_key("D")
    check(("fly", app.store.s["triggers"]["E_DELETING"]["act"]) in calls, "xoá liên tục -> nhân vật lao tới chỗ xoá")
    q = app.gmouse.q
    q.put(("K", "D"))
    s0 = fx.slash.played
    fx.t_last["D"] = 0
    app.gmouse.poll()
    check(fx.slash.played == s0 + 1, "sự kiện từ hook bàn phím đi qua hàng đợi tới hiệu ứng")
    finish(app, C)


app.root.after(1500, run)
app.root.mainloop()
