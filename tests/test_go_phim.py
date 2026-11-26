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
    cx = [400]

    def moving():                               # mỗi lần gõ con trỏ nhập dịch sang phải (nội dung thay đổi)
        cx[0] += 9
        return ((cx[0], 300), False)
    C.caret_info = moving
    n0 = fx.bolt.played
    for _ in range(10):
        fx.on_key("T")                          # 10 phím trong tích tắc (giữ phím lặp)
    check(fx.bolt.played - n0 == 1, "giữ phím lặp dồn dập -> gộp hiệu ứng, không làm chậm máy")
    fx.t_last["T"] = 0
    fx.on_key("T")
    check(fx.bolt.played - n0 == 2 and fx.last_pos == (cx[0], 300), "mỗi lần gõ có hiệu ứng riêng, đúng vị trí con trỏ nhập")
    C.caret_info = lambda: ((cx[0], 300), False)                # con trỏ đứng yên = nội dung không đổi
    fx.t_last["T"] = 0
    n1, sk = fx.bolt.played, fx.skipped
    fx.on_key("T")
    app.root.update()
    import time as _t
    _t.sleep(0.1)
    app.root.update()
    check(fx.bolt.played == n1 and fx.skipped == sk + 1, "nội dung không đổi (Backspace ở đầu ô...) -> không có hiệu ứng")
    fx.t_last["D"] = 0
    fx.on_key("D", 0x2E)
    check(fx.slash.played == 1, "phím Delete (xoá chữ bên phải, con trỏ đứng yên) vẫn có hiệu ứng xoá")
    C.caret_info = moving
    vs = fx.bolt.variants("bolt", fx.size())
    for _ in range(100):
        if len(vs) >= fx.bolt.VARIANTS:
            break
        _t.sleep(0.05)
    check(len(vs) == fx.bolt.VARIANTS, "dựng đủ %d biến thể ở luồng phụ" % fx.bolt.VARIANTS)
    for key, name, maker, anchor in C.FX_EFFECTS:
        ft, fd = maker(120, 7, "T"), maker(120, 7, "D")
        ok = all(len(fr) >= 6 and len({f.size for f in fr}) == 1 and sum(1 for f in fr if f.getbbox()) >= len(fr) * 0.6
                 for fr in (ft, fd))
        end_ok = all(not fr[-1].getbbox() or fr[-1].getchannel("A").getextrema()[1] < 200 for fr in (ft, fd))
        diff = any(a.tobytes() != b.tobytes() for a, b in zip(ft, fd))
        check(ok and end_ok and diff, "'%s': gõ %d / xoá %d khung, có diễn biến, tự tan, gõ ≠ xoá" % (name, len(ft), len(fd)))
    p = fx.bolt
    for _ in range(6):
        p.play(500, 300, 120, "bolt")
    check(len(p.live) <= p.MAX_LIVE + 1, "gõ chồng nhiều: giới hạn hiệu ứng cùng lúc (%d)" % len(p.live))
    for _ in range(80):
        app.root.update()
        _t.sleep(0.04)
        if not p.live:
            break
    check(not p.live and p.job is None, "hết hiệu ứng: tự dọn, không để lại hình")
    app.store.s["key_fx_type"], app.store.s["key_fx_del"] = "thunder", "skull"
    fx.t_last = {"T": 0, "D": 0}
    fx.on_key("T")
    fx.on_key("D")
    check(fx.bolt.last_key == "thunder" and fx.slash.last_key == "skull", "chọn mẫu riêng cho gõ / xoá")
    app.store.s["key_fx_type"] = "gai"                        # mã đã bỏ
    app.store.fix_triggers()
    check(app.store.s["key_fx_type"] == "sword", "mẫu cũ đã bỏ -> chuyển sang mẫu mới gần nhất")
    app.store.s["key_fx_type"] = "random"
    got = set()
    for _ in range(30):
        fx.t_last["T"] = 0
        fx.on_key("T")
        got.add(fx.bolt.last_key)
    check(len(got) >= 4, "ngẫu nhiên: đổi mẫu mỗi lần (%d mẫu khác nhau)" % len(got))
    app.store.s["key_fx_type"] = "random_thunder"
    got = set()
    for _ in range(40):
        fx.t_last["T"] = 0
        fx.on_key("T")
        got.add(fx.bolt.last_key)
    check(got <= set(C.FX_THUNDER) and len(got) >= 4, "ngẫu nhiên hệ Lôi: chỉ ra mẫu sấm sét (%d mẫu)" % len(got))
    check(all(k in C.FX_BY_KEY for k in C.FX_THUNDER) and len(C.FX_THUNDER) >= 11, "hệ Lôi có đủ 11 mẫu")
    check(any(c[0] == "random_thunder" for c in C.FX_CHOICES), "có lựa chọn Ngẫu nhiên hệ Lôi trong danh sách")
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
    fx.wait = (901, "T", C.time_now(), (11, 11), None)
    fx.finder.results.put((901, (640, 360), False, "UI Automation"))
    fx.poll()
    check(fx.bolt.played == n0 + 1 and fx.last_pos == (640, 360), "nhận vị trí từ UI Automation -> hiệu ứng đúng chỗ gõ")
    check("UI Automation" in fx.last_info, "ghi lại cách tìm được con trỏ nhập (%s)" % fx.last_info)
    fx.wait = (902, "D", C.time_now(), (11, 11), None)
    fx.finder.results.put((902, None, True, "UIA"))
    s0 = fx.slash.played
    fx.poll()
    check(fx.slash.played == s0, "ô mật khẩu trên trình duyệt -> không hiệu ứng")
    fx.wait = (903, "T", C.time_now() - 1.0, (77, 88), None)
    fx.poll()
    check(fx.last_pos == (77, 88), "phần mềm chậm trả lời quá 0,25 giây -> hiện cạnh chuột, không chờ")
    fx.wait = (904, "T", C.time_now(), (1, 1), None)
    fx.finder.results.put((900, (5, 5), False, "MSAA"))
    fx.poll()
    check(fx.wait is not None, "bỏ qua kết quả cũ không đúng yêu cầu")
    fx.wait = None
    # cỡ hiệu ứng theo cỡ chữ
    app.store.s["key_fx_autosize"], app.store.s["key_fx_size"] = True, 1.0
    small, big = fx.size(12), fx.size(40)
    check(small < big, "chữ nhỏ (12px) -> hiệu ứng nhỏ %d, chữ to (40px) -> to %d" % (small, big))
    check(fx.size(None) == fx.size(), "phần mềm không báo cỡ chữ -> dùng cỡ cố định")
    app.store.s["key_fx_size"] = 2.0
    check(fx.size(12) > small, "hệ số cỡ nhân thêm")
    app.store.s["key_fx_size"], app.store.s["key_fx_autosize"] = 1.0, False
    check(fx.size(12) == fx.size(40), "tắt tự động -> mọi cỡ chữ cùng cỡ hiệu ứng")
    app.store.s["key_fx_autosize"] = True
    fx.wait = (950, "T", C.time_now(), (1, 1), None)
    fx.finder.results.put((950, (300, 300), False, "UI Automation", 32))
    fx.poll()
    check(fx.last_size == fx.size(32), "cỡ chữ từ UI Automation được dùng để tính cỡ hiệu ứng")
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
