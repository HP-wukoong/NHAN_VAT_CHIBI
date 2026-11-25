# -*- coding: utf-8 -*-
"""Logic nhắc việc: lặp mỗi N phút, ẩn, khôi phục nhắc dở, việc quá hạn, toàn màn hình, sao lưu."""
import datetime as dt
from common import load, make_app, check, finish

C = load()
st = C.Store(C.DATA_FILE)
st.tasks.append(C.new_task("Việc quan trọng", "07:00", "daily"))
st.save()
st._bak_ts = 0
st.save()
open(C.DATA_FILE, "w").write("{hỏng")
check(any(t["title"] == "Việc quan trọng" for t in C.Store(C.DATA_FILE).tasks), "file hỏng -> khôi phục từ .bak")
app = make_app(C)
n = C.now()
nm = n.hour * 60 + n.minute


def run():
    t = C.new_task("Uống nước", C.m2hm(nm - 35), "interval", interval=60, end="23:59")
    app.store.tasks[:] = [t]
    app.check_tasks()
    check(t["id"] not in app.pending, "lặp mỗi N phút: lỡ mốc 35' -> chờ mốc sau")
    t["time"] = C.m2hm(nm - 62)
    app.check_tasks()
    check(t["id"] in app.pending, "lặp mỗi N phút: đúng mốc -> nhắc")
    app.hide(1)
    check(app.bubble.msg is not None or app.bubble.queue, "ẩn 15 phút không làm mất nhắc")
    app.unhide()
    app.task_done(t["id"])
    check(t["pending_sched"] == "" and t["id"] not in app.pending, "Xong -> xoá trạng thái đang nhắc")
    t2 = C.new_task("Họp", C.m2hm(nm - 5), "daily")
    app.store.tasks.append(t2)
    app.check_tasks()
    app.pending.clear()
    app.bubble.queue.clear()
    if app.bubble.msg:
        app.bubble.close()
    app.restore_pending()
    check(t2["id"] in app.pending, "mở lại app -> nhắc tiếp việc đang dở")
    t4 = C.new_task("Cũ", "08:00", "once", date=(dt.date.today() - dt.timedelta(days=2)).isoformat())
    app.store.tasks.append(t4)
    app.check_tasks()
    check(not t4["enabled"], "việc một lần quá ngày tự tắt")
    app.fs_hidden = True
    t5 = C.new_task("Lúc trình chiếu", C.m2hm(nm), "daily")
    app.store.tasks.append(t5)
    app.check_tasks()
    check(t5["id"] not in app.pending, "toàn màn hình -> dời nhắc")
    app.fs_hidden = False
    app.check_tasks()
    check(t5["id"] in app.pending, "hết toàn màn hình -> nhắc lại")
    finish(app, C)


app.root.after(2000, run)
app.root.mainloop()
