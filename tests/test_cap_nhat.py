# -*- coding: utf-8 -*-
"""Cập nhật: kiểm tra phiên bản, F5 tải + cài + sao lưu + khởi động lại, gói hỏng bị từ chối, quay về bản trước.
Dùng máy chủ HTTP giả trên máy, không cần mạng."""
import os
import io
import json
import zipfile
import threading
import http.server
from common import load, make_app, check, finish

C = load()
app = make_app(C)
up = app.updater
srv_dir = os.path.join(C.BASE_DIR, "_fake_github")
os.makedirs(srv_dir, exist_ok=True)
src = open(os.path.join(C.BASE_DIR, "chibi.py"), encoding="utf-8").read()
new_src = src.replace('APP_VER = "%s"' % C.APP_VER, 'APP_VER = "9.9"')
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w") as z:
    z.writestr("NHAN_VAT_CHIBI-main/ChibiNhacViec.pyw", new_src)
    z.writestr("NHAN_VAT_CHIBI-main/version.json", json.dumps({"version": "9.9"}))
    z.writestr("NHAN_VAT_CHIBI-main/NhanVat/NhanVatAoDen/test_moi.txt", "x")
open(os.path.join(srv_dir, "main.zip"), "wb").write(buf.getvalue())
json.dump({"version": "9.9", "notes": ["Thử nghiệm"]}, open(os.path.join(srv_dir, "version.json"), "w"))


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=srv_dir, **k)

    def log_message(self, *a):
        pass


httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
base = "http://127.0.0.1:%d/" % httpd.server_address[1]
C.URL_VERSION = base + "version.json"
C.URL_ZIP = base + "main.zip"
restarted = []
up.restart = lambda: restarted.append(1)
target = os.path.join(C.BASE_DIR, "ChibiNhacViec.pyw")
open(target, "w", encoding="utf-8").write(src)


def s1():
    up.check(manual=True)


def s2():
    check(app.bubble.msg and app.bubble.msg.get("key") == "update" or any(m.get("key") == "update" for m in app.bubble.queue),
          "có bản mới -> hiện thông báo hỏi cập nhật")
    check("9.9" in up.status, "trạng thái ghi rõ có bản mới v9.9")
    app.event_generate = None
    app.root.event_generate("<F5>")
    up.check(manual=True, install=True)


def s3():
    check(restarted, "F5: tải, cài xong và khởi động lại")
    check('APP_VER = "9.9"' in open(target, encoding="utf-8").read(), "file chương trình đã được thay bản mới")
    check(os.path.exists(os.path.join(C.BASE_DIR, "NhanVat", "NhanVatAoDen", "test_moi.txt")), "chép cả thư mục nhân vật")
    bk = os.listdir(C.BACKUP_DIR)
    check(len(bk) == 1 and os.path.exists(os.path.join(C.BACKUP_DIR, bk[0], "ChibiNhacViec.pyw")), "đã sao lưu bản cũ")
    check(app.store.s.get("just_updated") == "9.9", "ghi nhớ để chào sau khi khởi động lại")
    bad = os.path.join(srv_dir, "hong.zip")
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("x/ChibiNhacViec.pyw", "def hỏng(:\n")
    before = open(target, encoding="utf-8").read()
    try:
        up.install_zip(bad)
        ok = False
    except Exception:
        ok = True
    check(ok and open(target, encoding="utf-8").read() == before, "gói hỏng bị từ chối, không đụng bản đang chạy")
    C.messagebox.askyesno = lambda *a, **k: True
    restarted.clear()
    up.rollback()
    check(restarted and 'APP_VER = "%s"' % C.APP_VER in open(target, encoding="utf-8").read(), "quay về bản trước")
    httpd.shutdown()
    up.restart = lambda: None
    finish(app, C)


app.root.after(1500, s1)
app.root.after(4000, s2)
app.root.after(8000, s3)
app.root.mainloop()
