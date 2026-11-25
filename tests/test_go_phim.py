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
    check(len(fx.bolt.variants("bolt", fx.size())) == fx.bolt.VARIANTS, "lôi điện: 5 biến thể")
    for key, name, maker, anchor in C.FX_EFFECTS:
        fr = maker(120, 7)
        ok = len(fr) >= 6 and len({f.size for f in fr}) == 1 and any(f.getbbox() for f in fr)
        check(ok, "mẫu hiệu ứng '%s': %d khung, cùng cỡ, có hình" % (name, len(fr)))
    app.store.s["key_fx_type"], app.store.s["key_fx_del"] = "thunder", "hammer"
    fx.t_last = {"T": 0, "D": 0}
    fx.on_key("T")
    fx.on_key("D")
    check(fx.bolt.last_key == "thunder" and fx.slash.last_key == "hammer", "chọn mẫu riêng cho gõ / xoá")
    app.store.s["key_fx_type"] = "random"
    got = set()
    for _ in range(30):
        fx.t_last["T"] = 0
        fx.on_key("T")
        got.add(fx.bolt.last_key)
    check(len(got) >= 4, "ngẫu nhiên: đổi mẫu mỗi lần (%d mẫu khác nhau)" % len(got))
    app.store.s["key_fx_type"], app.store.s["key_fx_del"] = "bolt", "slash"
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
    fx.hist = {"T": [], "D": []}
    fx.cool = {"T": 0.0, "D": 0.0}
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
    # đường tìm con trỏ nhập ở luồng riêng (UI Automation / MSAA cho Chrome, Zalo...)
    import ctypes
    check(ctypes.sizeof(C._VARIANT) == (24 if ctypes.sizeof(ctypes.c_void_p) == 8 else 16), "cấu trúc VARIANT đúng kích thước COM")
    n0 = fx.bolt.played
    fx.wait = (901, "T", C.time_now(), (11, 11))
    fx.finder.results.put((901, (640, 360), False, "UI Automation"))
    fx.poll()
    check(fx.bolt.played == n0 + 1 and fx.last_pos == (640, 360), "nhận vị trí từ UI Automation -> hiệu ứng đúng chỗ gõ")
    check("UI Automation" in fx.last_info, "ghi lại cách tìm được con trỏ nhập (%s)" % fx.last_info)
    fx.wait = (902, "D", C.time_now(), (11, 11))
    fx.finder.results.put((902, None, True, "UIA"))
    s0 = fx.slash.played
    fx.poll()
    check(fx.slash.played == s0, "ô mật khẩu trên trình duyệt -> không hiệu ứng")
    fx.wait = (903, "T", C.time_now() - 1.0, (77, 88))
    fx.poll()
    check(fx.last_pos == (77, 88), "phần mềm chậm trả lời quá 0,25 giây -> hiện cạnh chuột, không chờ")
    fx.wait = (904, "T", C.time_now(), (1, 1))
    fx.finder.results.put((900, (5, 5), False, "MSAA"))
    fx.poll()
    check(fx.wait is not None, "bỏ qua kết quả cũ không đúng yêu cầu")
    fx.wait = None
    # tiến trình phụ: hỏi - đáp qua ống, sập thì chibi vẫn sống, tự mở lại, quá 3 lần thì thôi
    import time as _t
    fd = C.CaretFinder()
    fd.available = lambda: fd.crashes < 3
    fd.request(1)
    got = None
    for _ in range(100):
        try:
            got = fd.results.get(timeout=0.1)
            break
        except Exception:
            pass
    check(got is not None and got[0] == 1, "tiến trình phụ trả lời yêu cầu (%s)" % (got,))
    for k in range(3):
        fd.proc.kill()
        fd.proc.wait()
        for _ in range(50):
            if fd.crashes > k:
                break
            _t.sleep(0.1)
        if fd.crashes < 3:
            fd.request(2 + k)
            _t.sleep(1.0)
    check(fd.crashes >= 3 and app.root.winfo_exists(), "tiến trình phụ sập 3 lần: chibi vẫn chạy, tắt cách tìm này")
    fd.request(99)
    check(fd.proc is None, "đã tắt thì không mở lại tiến trình phụ nữa")
    fd.stop()
    q = app.gmouse.q
    q.put(("K", "D"))
    s0 = fx.slash.played
    fx.t_last["D"] = 0
    app.gmouse.poll()
    check(fx.slash.played == s0 + 1, "sự kiện từ hook bàn phím đi qua hàng đợi tới hiệu ứng")
    finish(app, C)


app.root.after(1500, run)
app.root.mainloop()
