# -*- coding: utf-8 -*-
"""CHẠY THỬ THẬT: mở app + một ô soạn thảo, gõ / xoá ký tự thật vào ô. Mỗi phím đi đúng đường của hook bàn phím
(hàng đợi -> on_key -> kiểm tra nội dung đổi -> dựng / phát hiệu ứng), ghi lại màn hình kèm các cửa sổ hiệu ứng
thành ảnh động. Dùng: python chay_thu_go_phim.py <mẫu gõ> <mẫu xoá> <file.gif>"""
import os
import sys

from common import load, make_app, check, finish

ARGS = sys.argv[1:] or ["bolt", "slash", "/tmp/chay_thu.gif"]
C = load()
app = make_app(C)
s = app.store.s
s["key_fx_type"], s["key_fx_del"] = ARGS[0], ARGS[1]
s["key_fx_pet"] = False
s["key_fx_autosize"] = True

tk = C.tk
ed = tk.Toplevel(app.root)
ed.geometry("620x150+40+120")
ed.configure(bg="#ffffff")
txt = tk.Text(ed, font=("DejaVu Sans", 18), bg="#ffffff", fg="#111111", insertwidth=2, relief="flat", padx=14, pady=40)
txt.pack(fill="both", expand=True)
txt.focus_force()


def caret():
    """Vị trí con trỏ nhập thật của ô soạn thảo (thay cho GetGUIThreadInfo trên Windows)."""
    b = txt.bbox("insert")
    if not b:
        return (None, False, None)
    return ((txt.winfo_rootx() + b[0], txt.winfo_rooty() + b[1] + b[3]), False, b[3])


C.caret_info = caret
shown = []                                        # (frame_no, kênh, x, y, ảnh) – mọi frame đã phát
current = {}                                      # cửa sổ hiệu ứng đang hiển thị: id -> (kênh, x, y, ảnh)
tick = [0]


def spy(player):
    orig = player._step

    def step():
        for e in player.live:
            if e["i"] < len(e["seq"]):
                data, w, h = e["seq"][e["i"]]
                ax, ay = e["anchor"]
                im = C.Image.frombytes("RGBa", (w, h), data, "raw", "BGRa").convert("RGBA")
                rec = (tick[0], player.mode, e["pos"][0] - int(w * ax), e["pos"][1] - int(h * ay), im)
                shown.append(rec)
                current[id(e)] = rec[1:]
        orig()
        ids = {id(e) for e in player.live}
        for k in [k for k, v in current.items() if v[0] == player.mode and k not in ids]:
            del current[k]
    player._step = step


spy(app.keyfx.bolt)
spy(app.keyfx.slash)
frames = []
plan = list("Họp giao ban") + ["BS"] * 4 + list("8h!") + ["HOME", "BS", "BS"]     # 2 Backspace cuối ở đầu dòng: không xoá gì
ev = {"played_T": 0, "played_D": 0}


def press(k):
    if k == "BS":
        before = txt.get("1.0", "end-1c")
        txt.delete("insert-1c", "insert")
        changed = txt.get("1.0", "end-1c") != before
        app.gmouse.q.put(("K", "D", 0x08))
        ev.setdefault("bs", []).append(changed)
    elif k == "HOME":
        txt.mark_set("insert", "1.0")
    else:
        txt.insert("insert", k)
        app.gmouse.q.put(("K", "T", 0x41))


def grab():
    from PIL import ImageGrab
    x, y = ed.winfo_rootx(), ed.winfo_rooty()
    W, H = ed.winfo_width(), ed.winfo_height()
    shot = ImageGrab.grab(bbox=(x - 30, y - 230, x + W + 30, y + H + 40), xdisplay=os.environ.get("DISPLAY")).convert("RGBA")
    for mode, ex, ey, im in list(current.values()):
        shot.alpha_composite(im, (ex - (x - 30), ey - (y - 230))) if ex - (x - 30) >= 0 and ey - (y - 230) >= 0 else \
            shot.paste(im, (ex - (x - 30), ey - (y - 230)), im)
    frames.append(shot.convert("RGB"))


step_i = [0]


def loop():
    tick[0] += 1
    if tick[0] > 8 and step_i[0] < len(plan) and tick[0] % 4 == 0:
        press(plan[step_i[0]])
        step_i[0] += 1
    app.root.update_idletasks()
    grab()
    if step_i[0] >= len(plan) and not app.keyfx.bolt.live and not app.keyfx.slash.live and tick[0] > 30:
        done()
        return
    app.root.after(40, loop)


def done():
    kf = app.keyfx
    typed = sum(1 for k in plan if len(k) == 1)
    check(kf.bolt.played >= typed - 1, "gõ %d ký tự -> %d hiệu ứng gõ (%s)" % (typed, kf.bolt.played, ARGS[0]))
    real_bs = sum(1 for c in ev["bs"] if c)
    check(kf.slash.played == real_bs, "Backspace %d lần, xoá thật %d ký tự -> %d hiệu ứng xoá (%s)"
          % (len(ev["bs"]), real_bs, kf.slash.played, ARGS[1]))
    check(kf.skipped >= 2, "Backspace ở đầu dòng (không xoá gì) -> bỏ qua %d lần" % kf.skipped)
    check(txt.get("1.0", "end-1c") == "Họp giao8h!", "ô soạn thảo nhận đủ ký tự, không mất chữ: %r" % txt.get("1.0", "end-1c"))
    check(any(z[1] == "T" for z in shown) and any(z[1] == "D" for z in shown), "cửa sổ hiệu ứng thực sự hiển thị frame (gõ & xoá)")
    frames[0].save(ARGS[2], save_all=True, append_images=frames[1:], duration=40, loop=0, optimize=True)
    print("ảnh động:", ARGS[2], len(frames), "frame")
    finish(app, C)


app.root.after(1500, loop)
app.root.mainloop()
