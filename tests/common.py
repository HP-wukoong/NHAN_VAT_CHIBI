# -*- coding: utf-8 -*-
"""Nạp app trong thư mục tạm (không đụng dữ liệu thật) để kiểm thử.
Chạy trên Windows: python tests\\test_xxx.py
Chạy trên Linux:  xvfb-run python3 tests/test_xxx.py"""
import os
import sys
import shutil
import socket
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load():
    tmp = tempfile.mkdtemp(prefix="chibi_test_")
    shutil.copy(os.path.join(ROOT, "ChibiNhacViec.pyw"), os.path.join(tmp, "chibi.py"))
    shutil.copytree(os.path.join(ROOT, "NhanVat"), os.path.join(tmp, "NhanVat"))
    sys.argv = [os.path.join(tmp, "chibi.py")]
    sys.path.insert(0, tmp)
    import chibi
    return chibi


def make_app(C):
    srv = socket.socket()
    srv.bind(("127.0.0.1", C.PORT))
    srv.listen(2)
    C.App.server = srv
    return C.App()


RESULTS = []


def check(cond, msg):
    RESULTS.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + msg)


def finish(app, C):
    if os.path.exists(C.ERR_FILE):
        print("errors.log:\n" + open(C.ERR_FILE, encoding="utf-8").read()[-1500:])
    print("\n%d/%d đạt" % (sum(RESULTS), len(RESULTS)))
    app.quit()
    sys.exit(0 if all(RESULTS) else 1)
