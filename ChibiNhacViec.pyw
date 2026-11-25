# -*- coding: utf-8 -*-
"""
CHIBI NHẮC VIỆC  v2.6
Robot chibi nhắc việc chạy trên màn hình Windows 10/11.
- Đi lại tự do toàn màn hình (hỗ trợ nhiều màn hình), kéo thả, đổi kích thước, đổi nhân vật
- Nhắc việc: một lần / hằng ngày / T2-T6 / chọn thứ / lặp mỗi N phút, hoãn, báo trước
- Tự học: phát hiện việc bạn hay làm cùng giờ, gợi ý dời giờ nhắc, gợi ý bỏ ngày hay bỏ qua,
  học thói quen mở ứng dụng, nhắc nghỉ mắt theo thời gian làm việc thực tế
Chỉ cần Python 3.8+ (tkinter có sẵn). Pillow là tuỳ chọn (dùng ảnh PNG/GIF riêng đẹp hơn).
Mọi dữ liệu lưu cục bộ trong thư mục ChibiData cạnh file này.
"""
import os
import sys
import json
import math
import random
import re
import socket
import threading
import statistics
import unicodedata
import uuid
import traceback
import datetime as dt
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, colorchooser

IS_WIN = sys.platform.startswith("win")
if IS_WIN:
    import ctypes
    from ctypes import wintypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    # Khai báo kiểu trả về để handle 64-bit không bị cắt cụt (lỗi ngẫu nhiên trên Win x64)
    try:
        _u32, _k32 = ctypes.windll.user32, ctypes.windll.kernel32
        _u32.GetForegroundWindow.restype = wintypes.HWND
        _u32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        _u32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        _u32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        _u32.MonitorFromWindow.restype = wintypes.HMONITOR
        _u32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        _k32.OpenProcess.restype = wintypes.HANDLE
        _k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        _k32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                    ctypes.POINTER(wintypes.DWORD)]
        _k32.CloseHandle.argtypes = [wintypes.HANDLE]
        _k32.GetTickCount.restype = wintypes.DWORD
    except Exception:
        pass

    class _RECT(ctypes.Structure):
        _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long), ("r", ctypes.c_long), ("b", ctypes.c_long)]

    class _MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", _RECT), ("rcWork", _RECT), ("dwFlags", ctypes.c_ulong)]

try:
    from PIL import Image, ImageTk, ImageOps, ImageSequence
    HAS_PIL = True
except Exception:
    HAS_PIL = False

APP_NAME = "Chibi Nhắc Việc"
APP_VER = "2.6"
KEY = "#ff00ff"          # màu nền trong suốt
PORT = 47613             # chống chạy 2 lần
FONT = "Segoe UI" if IS_WIN else "DejaVu Sans"
GRACE_MIN = 180
# ── bảng màu "bá khí": đen tím, đỏ thẫm, tím ma, vàng kim ──
C_BG, C_PANEL, C_PANEL2, C_LINE = "#0d0b14", "#15111f", "#1f1830", "#3a2d52"
C_FG, C_MUTED, C_ACC, C_ACC2, C_GOLD = "#ece6f5", "#9a90b0", "#e3263f", "#8b3dff", "#f5c542"          # bật máy trễ tối đa 3 giờ vẫn nhắc
BASE_DIR = os.path.dirname(os.path.abspath(sys.argv[0] if sys.argv and sys.argv[0] else __file__))


def data_dir():
    d = os.path.join(BASE_DIR, "ChibiData")
    try:
        os.makedirs(d, exist_ok=True)
        test = os.path.join(d, ".w")
        with open(test, "w") as f:
            f.write("1")
        os.remove(test)
        return d
    except Exception:
        d = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "ChibiNhacViec")
        os.makedirs(d, exist_ok=True)
        return d


DATA_DIR = data_dir()
DATA_FILE = os.path.join(DATA_DIR, "chibi_data.json")
ERR_FILE = os.path.join(DATA_DIR, "errors.log")


def log_error():
    try:
        with open(ERR_FILE, "a", encoding="utf-8") as f:
            f.write("\n[%s]\n%s" % (dt.datetime.now().isoformat(timespec="seconds"), traceback.format_exc()))
    except Exception:
        pass


# ───────────────────────── tiện ích ─────────────────────────
def norm(s):
    s = (s or "").strip().lower().replace("đ", "d")
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def hm2m(s):
    try:
        h, m = str(s).split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return 0


def m2hm(m):
    m = int(round(m)) % 1440
    return "%02d:%02d" % (m // 60, m % 60)


def round5(m):
    return int(5 * round(m / 5.0))


def now():
    return dt.datetime.now()


def iso(t):
    return t.isoformat(timespec="seconds")


def parse_iso(s):
    try:
        return dt.datetime.fromisoformat(s)
    except Exception:
        return None


def shade(hexc, f):
    hexc = hexc.lstrip("#")
    r, g, b = (int(hexc[i:i + 2], 16) for i in (0, 2, 4))
    if f < 1:
        r, g, b = (int(c * f) for c in (r, g, b))
    else:
        r, g, b = (int(c + (255 - c) * (f - 1)) for c in (r, g, b))
    return "#%02x%02x%02x" % (min(255, r), min(255, g), min(255, b))


def fmt_dur(mins):
    mins = int(mins)
    if mins < 60:
        return "%d phút" % mins
    return "%d giờ %02d phút" % (mins // 60, mins % 60)


WD = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
REPEAT_LABELS = [
    ("once", "Một lần"),
    ("daily", "Hằng ngày"),
    ("weekdays", "Ngày làm việc (T2–T6)"),
    ("weekly", "Chọn thứ trong tuần"),
    ("interval", "Lặp mỗi N phút"),
]
REPEAT_TEXT = dict(REPEAT_LABELS)


def repeat_desc(t):
    r = t.get("repeat")
    if r == "once":
        try:
            return "Một lần " + dt.date.fromisoformat(t.get("date")).strftime("%d/%m/%Y")
        except Exception:
            return "Một lần"
    if r == "weekly":
        return "Thứ: " + ", ".join(WD[d] for d in sorted(t.get("days") or []))
    if r == "interval":
        days = t.get("days") or list(range(7))
        dd = "mọi ngày" if len(days) == 7 else ", ".join(WD[d] for d in sorted(days))
        return "Mỗi %s phút đến %s (%s)" % (t.get("interval", 60), t.get("end", "17:00"), dd)
    return REPEAT_TEXT.get(r, r)


# ───────────────────────── Windows API ─────────────────────────
MONITORS = []      # khung toàn màn hình (kể cả taskbar) của từng màn hình, cập nhật cùng get_work_areas()


def get_work_areas():
    """Danh sách vùng làm việc (trừ taskbar) của mọi màn hình: (l, t, r, b)."""
    if IS_WIN:
        try:
            areas = []
            mons = []
            Proc = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(_RECT), ctypes.c_ssize_t)

            def cb(hmon, hdc, lprc, lp):
                mi = _MONITORINFO()
                mi.cbSize = ctypes.sizeof(_MONITORINFO)
                if ctypes.windll.user32.GetMonitorInfoW(ctypes.c_void_p(hmon), ctypes.byref(mi)):
                    w = mi.rcWork
                    m = mi.rcMonitor
                    areas.append((w.l, w.t, w.r, w.b))
                    mons.append((m.l, m.t, m.r, m.b))
                return 1

            ctypes.windll.user32.EnumDisplayMonitors(None, None, Proc(cb), 0)
            if areas:
                MONITORS[:] = mons
                return areas
        except Exception:
            log_error()
    return None


def get_idle_seconds():
    if IS_WIN:
        try:
            class LASTINPUTINFO(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
            li = LASTINPUTINFO()
            li.cbSize = ctypes.sizeof(LASTINPUTINFO)
            if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li)):
                tick = ctypes.windll.kernel32.GetTickCount() & 0xFFFFFFFF
                return ((tick - li.dwTime) & 0xFFFFFFFF) / 1000.0
        except Exception:
            pass
    return 0.0


def get_foreground_exe():
    if not IS_WIN:
        return None
    try:
        u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
        hwnd = u32.GetForegroundWindow()
        if not hwnd:
            return None
        pid = wintypes.DWORD()
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        h = k32.OpenProcess(0x1000, False, pid.value)
        if not h:
            return None
        try:
            buf = ctypes.create_unicode_buffer(520)
            size = wintypes.DWORD(520)
            if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                return os.path.basename(buf.value).lower()
        finally:
            k32.CloseHandle(h)
    except Exception:
        pass
    return None


def foreground_fullscreen():
    """True nếu cửa sổ đang dùng phủ kín cả màn hình (trình chiếu, xem video, game)."""
    if not IS_WIN:
        return False
    try:
        u32 = ctypes.windll.user32
        hwnd = u32.GetForegroundWindow()
        if not hwnd:
            return False
        cls = ctypes.create_unicode_buffer(64)
        u32.GetClassNameW(hwnd, cls, 64)
        if cls.value in ("Progman", "WorkerW", "Shell_TrayWnd", "TkTopLevel", "Tk", "#32768"):
            return False
        r = wintypes.RECT()
        if not u32.GetWindowRect(hwnd, ctypes.byref(r)):
            return False
        hmon = u32.MonitorFromWindow(hwnd, 2)
        mi = _MONITORINFO()
        mi.cbSize = ctypes.sizeof(_MONITORINFO)
        if not u32.GetMonitorInfoW(ctypes.c_void_p(hmon), ctypes.byref(mi)):
            return False
        m = mi.rcMonitor
        return r.left <= m.l and r.top <= m.t and r.right >= m.r and r.bottom >= m.b
    except Exception:
        return False


APP_IGNORE = {"explorer.exe", "python.exe", "pythonw.exe", "py.exe", "pyw.exe", "searchhost.exe",
              "searchapp.exe", "shellexperiencehost.exe", "startmenuexperiencehost.exe", "lockapp.exe",
              "applicationframehost.exe", "textinputhost.exe", "systemsettings.exe", "taskmgr.exe",
              "searchui.exe", "dwm.exe", "rundll32.exe", "consent.exe", "cmd.exe", "conhost.exe"}
APP_NAMES = {"excel.exe": "Excel", "winword.exe": "Word", "powerpnt.exe": "PowerPoint", "outlook.exe": "Outlook",
             "chrome.exe": "Chrome", "msedge.exe": "Edge", "firefox.exe": "Firefox", "zalo.exe": "Zalo",
             "acrord32.exe": "Acrobat Reader", "acrobat.exe": "Acrobat", "foxitpdfreader.exe": "Foxit PDF",
             "teams.exe": "Teams", "ms-teams.exe": "Teams", "telegram.exe": "Telegram", "code.exe": "VS Code",
             "notepad.exe": "Notepad", "wps.exe": "WPS Writer", "et.exe": "WPS Spreadsheets", "ultraviewer.exe": "UltraViewer",
             "teamviewer.exe": "TeamViewer", "anydesk.exe": "AnyDesk", "photoshop.exe": "Photoshop"}


def app_name(exe):
    return APP_NAMES.get(exe, os.path.splitext(exe)[0].replace("_", " ").title())


def beep():
    if IS_WIN:
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
            return
        except Exception:
            pass


# ───────────────────────── Lưu trữ ─────────────────────────
DEFAULT_SETTINGS = {
    "pet_name": "Áo Đen", "scale": 1.0,
    "sound": True, "talk": True, "break_minutes": 60, "pre_notice": 5,
    "quiet_start": "22:00", "quiet_end": "06:00", "track_apps": True, "auto_adjust": False,
    "autostart": False, "pos": None, "last_greet_date": "", "hide_fullscreen": True,
    "pack": "", "free_master": True, "free": {}, "assigned_no_free": True, "walk_windows": True, "jump_icons": True,
    "auto_jump": True, "climb": True, "smooth": True, "triggers": None, "screen_mode": "desktop",
    "update_mode": "notify", "last_update_check": "", "just_updated": "",
    "key_fx": True, "key_fx_pet": True, "key_fx_size": 1.0, "key_fx_type": "bolt", "key_fx_del": "slash",
    "drop_action": "VaCham_RoiHoDat", "wall_hit_action": "TrangThai_AnVa",
}


class Store:
    def __init__(self, path):
        self.path = path
        self.data = {"settings": dict(DEFAULT_SETTINGS), "tasks": [], "log": [], "app_usage": {},
                     "day_start": {}, "ignored": {}}
        self.load()

    def _read(self, path):
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        if not isinstance(d.get("tasks"), list):
            raise ValueError("thiếu danh sách việc")
        for k in self.data:
            if k in d:
                self.data[k] = d[k]
        s = dict(DEFAULT_SETTINGS)
        s.update(self.data.get("settings") or {})
        for old in ("character", "main_color", "accent_color", "accessory", "custom_image", "walk", "speed", "gravity"):
            s.pop(old, None)
        self.data["settings"] = s
        self.fix_triggers()

    def fix_triggers(self):
        import copy
        s = self.data["settings"]
        tr = s.get("triggers") or {}
        for k, v in DEFAULT_TRIGGERS.items():
            if k not in tr:
                tr[k] = copy.deepcopy(v)
        s["triggers"] = tr

    def load(self):
        self._bak_ts = 0
        if not os.path.exists(self.path):
            if os.path.exists(self.path + ".bak"):
                try:
                    self._read(self.path + ".bak")
                    return
                except Exception:
                    log_error()
            self.seed()
            return
        try:
            self._read(self.path)
        except Exception:
            # file hỏng (mất điện khi đang ghi...) -> giữ lại bản hỏng, khôi phục từ bản sao lưu hằng ngày
            log_error()
            try:
                os.replace(self.path, self.path + ".hong_%d" % int(dt.datetime.now().timestamp()))
            except Exception:
                pass
            try:
                self._read(self.path + ".bak")
                self.save()
            except Exception:
                self.seed()

    def seed(self):
        self.fix_triggers()
        self.data["tasks"] = [
            new_task("Kiểm tra email / Zalo công việc", "08:00", "weekdays"),
            new_task("Uống nước", "08:30", "interval", interval=90, end="17:00"),
        ]
        self.save()

    def save(self):
        try:
            self.trim()
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, separators=(",", ":"))
                f.flush()
                os.fsync(f.fileno())
            ts = dt.datetime.now().timestamp()
            if ts - self._bak_ts > 3600 and os.path.exists(self.path):
                try:
                    import shutil
                    shutil.copy2(self.path, self.path + ".bak")   # sao lưu cuốn chiếu, tối đa mất 1 giờ dữ liệu
                except Exception:
                    pass
                self._bak_ts = ts
            os.replace(tmp, self.path)
        except Exception:
            log_error()

    def trim(self):
        cut = (now() - dt.timedelta(days=120)).isoformat()
        self.data["log"] = [e for e in self.data["log"] if e.get("t", "") >= cut][-5000:]
        cutd = (dt.date.today() - dt.timedelta(days=60)).isoformat()
        self.data["app_usage"] = {d: v for d, v in self.data["app_usage"].items() if d >= cutd}
        self.data["day_start"] = {d: v for d, v in self.data["day_start"].items() if d >= cutd}

    @property
    def s(self):
        return self.data["settings"]

    @property
    def tasks(self):
        return self.data["tasks"]

    def task(self, tid):
        for t in self.tasks:
            if t["id"] == tid:
                return t
        return None

    def add_log(self, kind, task=None, title=None, sched=None, extra=None):
        t = now()
        e = {"t": iso(t), "date": t.date().isoformat(), "kind": kind,
             "task": task["id"] if task else None,
             "title": title or (task["title"] if task else ""), "sched": sched}
        if extra:
            e.update(extra)
        self.data["log"].append(e)
        self.save()
        return e


def new_task(title, time="08:00", repeat="daily", **kw):
    t = {"id": uuid.uuid4().hex[:10], "title": title, "note": "", "time": time, "repeat": repeat,
         "days": [], "date": dt.date.today().isoformat(), "interval": 60, "end": "17:00",
         "enabled": True, "source": "user", "created": iso(now()),
         "last_occ": "", "done_date": "", "snooze_until": "", "snooze_sched": "", "pre_occ": "", "last_fired_ts": "", "pending_sched": ""}
    t.update(kw)
    return t


def occurs_on(t, d):
    r = t.get("repeat")
    if r == "once":
        return t.get("date") == d.isoformat()
    if r == "daily":
        return True
    if r == "weekdays":
        return d.weekday() < 5
    days = t.get("days") or list(range(7))
    return d.weekday() in days


# ───────────────────────── Nhân vật Shimeji (engine chạy actions.xml / behaviors.xml) ─────────────────────────
BUILTIN_PACK = os.path.join(BASE_DIR, "NhanVat", "NhanVatAoDen")
PACKS_DIR = os.path.join(DATA_DIR, "packs")


def pack_ref(path):
    """Lưu đường dẫn tương đối nếu nằm trong ChibiData (đổi ký tự ổ USB vẫn chạy)."""
    try:
        ap = os.path.abspath(path)
        if os.path.commonpath([ap, DATA_DIR]) == DATA_DIR:
            return os.path.relpath(ap, DATA_DIR)
    except Exception:
        pass
    return path


def pack_resolve(ref):
    if not ref:
        return ""
    return ref if os.path.isabs(ref) else os.path.join(DATA_DIR, ref)


def safe_name(s):
    s = norm(s).replace(" ", "_") or "nhan_vat"
    base, i = s, 2
    while os.path.exists(os.path.join(PACKS_DIR, s)):
        s = "%s_%d" % (base, i)
        i += 1
    return s
TICK_MS = 40                      # 1 nhịp Shimeji = 40ms (25 khung/giây)

BEHAVIOR_LABELS = {
    "Stand": "Đứng thủ thế", "StandAlt": "Đứng (kiểu 2)", "Walk": "Đi bộ", "Run": "Chạy", "Dash": "Lướt nhanh",
    "Fall": "Rơi", "Land": "Tiếp đất", "Dragged": "Bị túm", "Thrown": "Bị ném",
    "GrabWall": "Bám tường", "ClimbWall": "Leo tường", "GrabCeiling": "Bám trần", "ClimbCeiling": "Leo trần",
    "NghiNgoi_Ngoi": "Ngồi nghỉ", "NghiNgoi_Ngu": "Nằm ngủ",
    "ChienDau_DamLien": "Đấm liên tiếp", "ChienDau_KiemKhi": "Kiếm khí", "ChienDau_LaoChem": "Lao chém",
    "ChienDau_NhayChem": "Nhảy chém", "ChienDau_DamThep": "Đấm thép", "ChienDau_DamLienHoan": "Đấm liên hoàn",
    "ChienDau_DamSongAm": "Đấm sóng âm", "HacLong_NhayVut": "Hắc Long nhảy vút",
    "HacLong_BayTheoChuot": "Hắc Long bay theo chuột", "DiChuyen_LuotTrai": "Lướt trái", "DiChuyen_LuotPhai": "Lướt phải",
    "DiChuyen_LaoNhanh": "Lao nhanh", "DiChuyen_BamVachTrai": "Leo vách trái", "DiChuyen_BamVachPhai": "Leo vách phải",
    "VaCham_RoiHoDat": "Rơi tạo hố", "TrangThai_NgoiKhoc": "Ngồi khóc", "TrangThai_AnVa": "Ăn vạ",
    "TrangThai_NanNi": "Nằn nì", "TrangThai_BiTreo": "Bị treo (trên trần)", "BieuCam_CuoiMaQuai": "Cười ma quái",
    "BieuCam_HoaCuong": "Hóa cuồng", "BaKhi_NapNang": "Nạp năng lượng", "BaKhi_NoKhi": "Nổ khí",
    "BaKhi_FullCombo": "FULL COMBO", "TapLuyen_DanhBong": "Đánh bóng (tập)", "TapLuyen_ChayBo": "Chạy bộ (tập)",
    "TapLuyen_LaoTapLuyen": "Lao tập luyện", "ChuotThu_ChayTheoChuot": "Đuổi theo chuột",
}
GROUP_LABELS = {"ChienDau": "Chiến đấu", "HacLong": "Hắc Long", "DiChuyen": "Di chuyển", "VaCham": "Va chạm",
                "TrangThai": "Trạng thái", "BieuCam": "Biểu cảm", "BaKhi": "Bá khí", "TapLuyen": "Tập luyện",
                "NghiNgoi": "Nghỉ ngơi", "ChuotThu": "Theo chuột"}
CORE_BEHAVIORS = ("Stand", "StandAlt", "Walk", "Run", "Dash")
SYSTEM_BEHAVIORS = ("Fall", "Land", "Dragged", "Thrown", "GrabWall", "ClimbWall", "GrabCeiling", "ClimbCeiling")


def beh_label(n):
    if n in BEHAVIOR_LABELS:
        return BEHAVIOR_LABELS[n]
    s = n.split("_", 1)[-1]
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s)


def beh_group(n):
    if n in CORE_BEHAVIORS:
        return "Cơ bản"
    if n in SYSTEM_BEHAVIORS:
        return "Hệ thống"
    p = n.split("_", 1)[0]
    return GROUP_LABELS.get(p, p if "_" in n else "Khác")


# ── biểu thức kiểu JavaScript trong file Shimeji -> Python ──
class _Obj(dict):
    def __getattr__(self, k):
        return self.get(k, 0)


class _Math:
    random = staticmethod(random.random)
    abs = staticmethod(abs)
    min = staticmethod(min)
    max = staticmethod(max)
    floor = staticmethod(math.floor)
    ceil = staticmethod(math.ceil)
    round = staticmethod(round)
    sqrt = staticmethod(math.sqrt)
    sin = staticmethod(math.sin)
    cos = staticmethod(math.cos)
    PI = math.pi


_TERN = re.compile(r"\(([^()?:]+)\?([^()?:]+):([^()?:]+)\)")


def js_compile(expr):
    e = (expr or "").strip()
    if e[:2] in ("${", "#{") and e.endswith("}"):
        e = e[2:-1]
    e = e.replace("&&", " and ").replace("||", " or ")
    e = re.sub(r"\btrue\b", "True", re.sub(r"\bfalse\b", "False", e))
    e = re.sub(r"!(?!=)", " not ", e)
    while True:
        n = _TERN.sub(lambda m: "((%s) if (%s) else (%s))" % (m.group(2), m.group(1), m.group(3)), e)
        if n == e:
            break
        e = n
    m = re.fullmatch(r"([^?:]+)\?([^?:]+):([^?:]+)", e)
    if m:
        e = "((%s) if (%s) else (%s))" % (m.group(2), m.group(1), m.group(3))
    try:
        return compile(e.strip(), "<shimeji>", "eval")
    except Exception:
        return None


class Pose:
    __slots__ = ("img", "imgr", "ax", "ay", "vx", "vy", "dur")


class ActionSpec:
    def __init__(self):
        self.name, self.type, self.cls, self.border, self.loop = "", "", "", None, False
        self.attrs, self.poses, self.refs = {}, [], []


class BehaviorSpec:
    def __init__(self):
        self.name, self.freq, self.hidden, self.cond, self.add = "", 0, False, None, False
        self.nexts = []            # (tên, tần suất, điều kiện)
        self.action = ""


def _local(tag):
    return tag.split("}")[-1]


def _cond_kind(text):
    t = (text or "").replace(" ", "")
    for k in ("floor", "wall", "ceiling"):
        if "%s.isOn" % k in t:
            return ("not_" + k) if ("!" + "mascot.environment.%s" % k) in t else k
    return None


class ShimejiPack:
    """Đọc bộ Shimeji-ee (conf/actions.xml + conf/behaviors.xml + ảnh)."""

    def __init__(self, root_dir):
        import xml.etree.ElementTree as ET
        self.ok = False
        self.actions, self.behaviors, self.order = {}, {}, []
        self.images = {}
        conf = None
        for r, ds, fs in os.walk(root_dir):
            if "actions.xml" in [f.lower() for f in fs] and "behaviors.xml" in [f.lower() for f in fs]:
                conf = r
                break
        if not conf:
            raise ValueError("Không thấy conf/actions.xml và behaviors.xml")
        self.conf_dir = conf
        self.img_dir = os.path.dirname(conf) if os.path.basename(conf).lower() == "conf" else conf
        self.name = os.path.basename(self.img_dir)
        if self.name.lower() == "nhanvataoden":
            self.name = "Áo Đen"
        files = {f.lower(): f for f in os.listdir(conf)}
        A = ET.parse(os.path.join(conf, files["actions.xml"])).getroot()
        B = ET.parse(os.path.join(conf, files["behaviors.xml"])).getroot()
        for al in A:
            if _local(al.tag) != "ActionList":
                continue
            for a in al:
                if _local(a.tag) == "Action":
                    self._parse_action(a)
        for bl in B:
            if _local(bl.tag) == "BehaviorList":
                self._parse_behaviors(bl, None)
        self.ok = bool(self.actions) and bool(self.behaviors)

    def _parse_action(self, a):
        s = ActionSpec()
        s.name = a.get("Name")
        s.type = a.get("Type", "Stay")
        s.cls = (a.get("Class") or "").split(".")[-1]
        s.border = a.get("BorderType")
        s.loop = (a.get("Loop") or "").lower() == "true"
        for k, v in a.attrib.items():
            if k not in ("Name", "Type", "Class", "BorderType", "Loop"):
                s.attrs[k] = v
        for c in a:
            t = _local(c.tag)
            if t == "Animation" and not s.poses:
                for p in c:
                    if _local(p.tag) != "Pose":
                        continue
                    o = Pose()
                    o.img = (p.get("Image") or "").lstrip("/\\")
                    o.imgr = (p.get("ImageRight") or "").lstrip("/\\")
                    ax, ay = (p.get("ImageAnchor") or "0,0").split(",")
                    vx, vy = (p.get("Velocity") or "0,0").split(",")
                    o.ax, o.ay, o.vx, o.vy = float(ax), float(ay), float(vx), float(vy)
                    o.dur = max(1, int(float(p.get("Duration") or 1)))
                    s.poses.append(o)
            elif t in ("ActionReference", "Action"):
                if t == "Action":
                    self._parse_action(c)
                ref = dict(c.attrib)
                s.refs.append((ref.pop("Name", ""), ref))
        self.actions[s.name] = s

    def _parse_behaviors(self, node, cond):
        for c in node:
            t = _local(c.tag)
            if t == "Condition":
                self._parse_behaviors(c, _cond_kind(c.get("Condition")) or cond)
            elif t == "Behavior":
                b = BehaviorSpec()
                b.name = c.get("Name")
                b.action = c.get("Action") or b.name
                b.freq = int(float(c.get("Frequency") or 0))
                b.hidden = (c.get("Hidden") or "").lower() == "true"
                b.cond = cond
                nl = None
                for x in c:
                    if _local(x.tag) == "NextBehaviorList":
                        nl = x
                if nl is not None:
                    b.add = (nl.get("Add") or "true").lower() == "true"
                    self._parse_nexts(nl, None, b.nexts)
                else:
                    b.add = True
                self.behaviors[b.name] = b
                self.order.append(b.name)

    def _parse_nexts(self, node, cond, out):
        for c in node:
            t = _local(c.tag)
            if t == "BehaviorReference":
                out.append((c.get("Name"), int(float(c.get("Frequency") or 0)), cond))
            elif t == "Condition":
                self._parse_nexts(c, _cond_kind(c.get("Condition")) or cond, out)

    def image(self, fn):
        im = self.images.get(fn)
        if im is None:
            p = os.path.join(self.img_dir, fn)
            try:
                im = Image.open(p).convert("RGBA")
            except Exception:
                im = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
            self.images[fn] = im
            while len(self.images) > 260:       # giữ RAM gọn: ảnh gốc ít dùng sẽ đọc lại từ đĩa
                self.images.pop(next(iter(self.images)))
        return im

    def user_behaviors(self):
        """Hành vi người dùng có thể gán / bật tắt (bỏ các hành vi hệ thống ẩn)."""
        out = []
        for n in self.order:
            b = self.behaviors[n]
            if n in SYSTEM_BEHAVIORS or (b.hidden and n not in self.actions):
                continue
            if b.hidden and b.freq == 0 and n in ("Land",):
                continue
            out.append(n)
        return out


# ── môi trường: vùng làm việc, mặt đất, cửa sổ, biểu tượng desktop ──
class Platform:
    __slots__ = ("x1", "x2", "y", "kind", "hwnd")

    def __init__(self, x1, x2, y, kind, hwnd=None):
        self.x1, self.x2, self.y, self.kind, self.hwnd = x1, x2, y, kind, hwnd


def _win_api_setup():
    if not IS_WIN or getattr(_win_api_setup, "done", False):
        return
    _win_api_setup.done = True
    u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
    u32.WindowFromPoint.argtypes = [wintypes.POINT]
    u32.WindowFromPoint.restype = wintypes.HWND
    u32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    u32.GetAncestor.restype = wintypes.HWND
    u32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    u32.FindWindowW.restype = wintypes.HWND
    u32.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
    u32.FindWindowExW.restype = wintypes.HWND
    u32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    u32.SendMessageW.restype = ctypes.c_ssize_t
    u32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    u32.IsWindowVisible.argtypes = [wintypes.HWND]
    u32.IsIconic.argtypes = [wintypes.HWND]
    u32.IsZoomed.argtypes = [wintypes.HWND]
    u32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    u32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    k32.VirtualAllocEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
    k32.VirtualAllocEx.restype = ctypes.c_void_p
    k32.VirtualFreeEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD]
    k32.WriteProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p]
    k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p]
    try:
        ctypes.windll.dwmapi.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    except Exception:
        pass


def _root_of_point(x, y):
    u32 = ctypes.windll.user32
    h = u32.WindowFromPoint(wintypes.POINT(int(x), int(y)))
    return u32.GetAncestor(h, 2) if h else None


def _class_name(h):
    b = ctypes.create_unicode_buffer(64)
    ctypes.windll.user32.GetClassNameW(h, b, 64)
    return b.value


def window_platforms():
    """Mép trên các cửa sổ đang mở (không thu nhỏ, không phóng to) -> chỗ đứng cho nhân vật."""
    out = []
    if not IS_WIN:
        return out
    _win_api_setup()
    u32 = ctypes.windll.user32
    own = os.getpid()
    Proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(h, lp):
        try:
            if not u32.IsWindowVisible(h) or u32.IsIconic(h) or u32.IsZoomed(h):
                return True
            if u32.GetWindowLongW(h, -20) & 0x80 or u32.GetWindowTextLengthW(h) == 0:
                return True
            pid = wintypes.DWORD()
            u32.GetWindowThreadProcessId(h, ctypes.byref(pid))
            if pid.value == own:
                return True
            if _class_name(h) in ("Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Windows.UI.Core.CoreWindow"):
                return True
            cl = ctypes.c_int(0)
            try:
                ctypes.windll.dwmapi.DwmGetWindowAttribute(h, 14, ctypes.byref(cl), 4)
            except Exception:
                pass
            if cl.value:
                return True
            r = wintypes.RECT()
            ok = False
            try:
                ok = ctypes.windll.dwmapi.DwmGetWindowAttribute(h, 9, ctypes.byref(r), ctypes.sizeof(r)) == 0
            except Exception:
                pass
            if not ok:
                u32.GetWindowRect(h, ctypes.byref(r))
            if r.right - r.left < 160 or r.bottom - r.top < 90:
                return True
            # chỉ lấy cửa sổ mà mép trên đang thấy được (không bị cửa sổ khác che)
            vis = False
            for px in (r.left + 30, (r.left + r.right) // 2, r.right - 30):
                rt = _root_of_point(px, r.top + 4)
                if rt == h:
                    vis = True
                    break
            if vis:
                out.append(Platform(r.left, r.right, r.top, "win", h))
        except Exception:
            pass
        return True

    u32.EnumWindows(Proc(cb), 0)
    return out


def desktop_icon_platforms():
    """Đỉnh các biểu tượng thư mục/file trên desktop đang thấy được."""
    out = []
    if not IS_WIN:
        return out
    _win_api_setup()
    u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
    try:
        prog = u32.FindWindowW("Progman", None)
        dv = u32.FindWindowExW(prog, None, "SHELLDLL_DefView", None)
        w = None
        while not dv:
            w = u32.FindWindowExW(None, w, "WorkerW", None)
            if not w:
                break
            dv = u32.FindWindowExW(w, None, "SHELLDLL_DefView", None)
        lv = u32.FindWindowExW(dv, None, "SysListView32", None) if dv else None
        if not lv or not u32.IsWindowVisible(lv):
            return out
        n = int(u32.SendMessageW(lv, 0x1004, 0, 0))     # LVM_GETITEMCOUNT
        if n <= 0:
            return out
        pid = wintypes.DWORD()
        u32.GetWindowThreadProcessId(lv, ctypes.byref(pid))
        hp = k32.OpenProcess(0x0008 | 0x0010 | 0x0020 | 0x0400, False, pid.value)
        if not hp:
            return out
        mem = k32.VirtualAllocEx(hp, None, 16, 0x3000, 0x04)
        try:
            for i in range(min(n, 400)):
                rc = wintypes.RECT(1, 0, 0, 0)            # LVIR_ICON
                k32.WriteProcessMemory(hp, mem, ctypes.byref(rc), 16, None)
                if not u32.SendMessageW(lv, 0x100E, i, mem):   # LVM_GETITEMRECT
                    continue
                k32.ReadProcessMemory(hp, mem, ctypes.byref(rc), 16, None)
                p1 = wintypes.POINT(rc.left, rc.top)
                p2 = wintypes.POINT(rc.right, rc.bottom)
                u32.ClientToScreen(lv, ctypes.byref(p1))
                u32.ClientToScreen(lv, ctypes.byref(p2))
                if p2.x - p1.x < 8:
                    continue
                rt = _root_of_point((p1.x + p2.x) // 2, (p1.y + p2.y) // 2)
                if rt and _class_name(rt) in ("Progman", "WorkerW"):
                    out.append(Platform(p1.x, p2.x, p1.y, "icon", None))
        finally:
            k32.VirtualFreeEx(hp, mem, 0, 0x8000)
            k32.CloseHandle(hp)
    except Exception:
        log_error()
    return out


class Env:
    """Toạ độ 'thế giới' = toạ độ màn hình / zoom, để mọi con số trong file Shimeji co giãn theo kích thước."""

    def __init__(self, app):
        self.app = app
        self.zoom = 1.0
        self.areas = []
        self.platforms = []
        self.win_plats = []
        self.icon_plats = []
        self._last_win = 0
        self._last_icon = 0
        self.cursor = (0, 0)
        self.temp = None             # nền tạm giữa không trung khi bay tới tung chiêu

    def refresh(self, force=False):
        z = self.zoom
        self.areas = [(a[0] / z, a[1] / z, a[2] / z, a[3] / z) for a in self.app.areas]
        t = time_now()
        s = self.app.store.s
        if force or t - self._last_win > 0.5:
            self._last_win = t
            self.win_plats = window_platforms() if s.get("walk_windows", True) else []
        if force or t - self._last_icon > 3.0:
            self._last_icon = t
            self.icon_plats = desktop_icon_platforms() if s.get("jump_icons", True) else []
        pl = [Platform(a[0], a[2], a[3], "base") for a in self.areas]
        for p in self.win_plats + self.icon_plats:
            pl.append(Platform(p.x1 / z, p.x2 / z, p.y / z, p.kind, p.hwnd))
        if self.temp is not None:
            pl.append(self.temp)
        self.platforms = pl
        try:
            px, py = self.app.root.winfo_pointerxy()
            self.cursor = (px / z, py / z)
        except Exception:
            pass

    def area_at(self, x, y=None):
        best = None
        for a in self.areas:
            if a[0] <= x <= a[2] and (y is None or a[1] - 2 <= y <= a[3] + 2):
                return a
            d = min(abs(x - a[0]), abs(x - a[2]))
            if best is None or d < best[0]:
                best = (d, a)
        return best[1] if best else (0, 0, 1920, 1040)

    def on_floor(self, x, y):
        for p in self.platforms:
            if p.x1 <= x <= p.x2 and abs(p.y - y) <= 1.5:
                return p
        return None

    def on_wall(self, x, y):
        a = self.area_at(x, y)
        return (abs(x - a[0]) <= 1.5 or abs(x - a[2]) <= 1.5) and y > a[1] + 1.5

    def on_ceiling(self, x, y):
        a = self.area_at(x, y)
        return abs(y - a[1]) <= 1.5

    def landing(self, x, y0, y1):
        """Mặt đất đầu tiên cắt qua khi rơi từ y0 xuống y1 tại x."""
        best = None
        for p in self.platforms:
            if p.x1 <= x <= p.x2 and y0 - 0.5 <= p.y <= y1 + 0.5:
                if best is None or p.y < best.y:
                    best = p
        return best

    def step_up_target(self, x, y, dirn):
        """Vật cản / chỗ cao phía trước (cửa sổ, biểu tượng) trong tầm nhảy."""
        best = None
        for p in self.platforms:
            if p.kind == "base" or not (y - 330 < p.y < y - 25):
                continue
            edge = p.x1 if dirn > 0 else p.x2
            dist = (edge - x) * dirn
            if 8 < dist < 220:
                inset = min(28, (p.x2 - p.x1) / 2.0)
                tx = edge + dirn * inset
                if best is None or dist < best[0]:
                    best = (dist, tx, p.y)
        return best


def time_now():
    return dt.datetime.now().timestamp()


class Engine:
    def __init__(self, pet, pack):
        self.pet, self.app, self.pack = pet, pet.app, pack
        self.env = pet.env
        self.ax, self.ay = 0.0, 0.0
        self.look_right = False
        self.vx = self.vy = 0.0
        self.cur = None
        self.gen = None
        self.pose = None
        self.forced = None
        self.dragging = False
        self.drag_hist = []
        self.calm = False
        self.sleep_beh = None
        self.on_hwnd = None
        self.last_plat = None
        self.pending = None          # (tên chiêu, hạn chót) chờ đứng vững rồi ra chiêu
        self.wall_hit = False        # vừa bị quăng đập vào tường

    # ── tiện ích ──
    def ctx(self):
        a = self.env.area_at(self.ax, self.ay)
        cx, cy = self.env.cursor
        fl = self.env.on_floor(self.ax, self.ay)
        wa = _Obj(left=a[0], top=a[1], right=a[2], bottom=a[3], width=a[2] - a[0], height=a[3] - a[1])
        env = _Obj(workArea=wa, screen=wa, cursor=_Obj(x=cx, y=cy),
                   floor=_Obj(y=fl.y if fl else a[3]), ceiling=_Obj(y=a[1]))
        m = _Obj(anchor=_Obj(x=self.ax, y=self.ay), lookRight=self.look_right, environment=env)
        return {"mascot": m, "Math": _Math, "__builtins__": {}}

    def ev(self, attrs, key, default=None):
        v = attrs.get(key)
        if v is None:
            return default
        try:
            code = js_compile(v)
            return float(eval(code, self.ctx())) if code else default
        except Exception:
            return default

    def cond_ok(self, c):
        if c is None:
            return True
        neg = c.startswith("not_")
        k = c[4:] if neg else c
        f = {"floor": self.env.on_floor(self.ax, self.ay) is not None,
             "wall": self.env.on_wall(self.ax, self.ay),
             "ceiling": self.env.on_ceiling(self.ax, self.ay)}.get(k, True)
        return (not f) if neg else bool(f)

    def clamp(self):
        a = self.env.area_at(self.ax, self.ay)
        self.ax = max(a[0], min(a[2], self.ax))
        self.ay = max(a[1], min(a[3], self.ay))

    @staticmethod
    def cycle(poses):
        while True:
            for p in poses:
                for _ in range(p.dur):
                    yield p

    def dir(self):
        return 1 if self.look_right else -1

    # ── các kiểu hành động ──
    def run_action(self, name, attrs=None, depth=0):
        spec = self.pack.actions.get(name)
        if not spec or depth > 12:
            return
        a = dict(spec.attrs)
        a.update(attrs or {})
        t = spec.type
        if t == "Sequence":
            n = 0
            while True:
                for rn, ra in spec.refs:
                    yield from self.run_action(rn, ra, depth + 1)
                n += 1
                if not spec.loop or n > 50:
                    break
        elif t == "Select":
            for rn, ra in spec.refs:
                yield from self.run_action(rn, ra, depth + 1)
                break
        elif t == "Embedded":
            if spec.cls == "Fall":
                yield from self.act_fall(spec, a)
            elif spec.cls == "Jump":
                yield from self.act_jump(spec, a)
            elif spec.cls == "Dragged":
                yield from self.act_dragged(spec, a)
            else:
                yield from self.act_animate(spec, a)
        elif t == "Move":
            yield from self.act_move(spec, a)
        else:
            yield from self.act_animate(spec, a)

    def _floor_follow(self, spec):
        if spec.border == "Floor":
            p = self.env.on_floor(self.ax, self.ay)
            if p is None:
                return False
            self.ay = p.y
            self.on_hwnd = p.hwnd
        return True

    def act_animate(self, spec, a):
        if not spec.poses or not self._floor_follow(spec):
            return
        total = sum(p.dur for p in spec.poses)
        dur = self.ev(a, "Duration", None)
        n = int(dur) if dur else total
        it = self.cycle(spec.poses)
        for _ in range(max(1, n)):
            p = next(it)
            if p.vx or p.vy:
                old = self.ax
                self.ax += p.vx * (-1 if self.look_right else 1)
                self.ay += p.vy
                self.clamp()
                if spec.border == "Floor" and self.env.on_floor(self.ax, self.ay) is None:
                    p2 = self.env.on_floor(old, self.ay)
                    if p2 is None:
                        yield p
                        return
            if not self._floor_follow(spec):
                return
            yield p

    def act_move(self, spec, a):
        if not spec.poses:
            return
        if not self._floor_follow(spec):
            return
        tx = self.ev(a, "TargetX", None)
        ty = self.ev(a, "TargetY", None)
        area = self.env.area_at(self.ax, self.ay)
        if tx is not None:
            tx = max(area[0], min(area[2], tx))
            if abs(tx - self.ax) < 1 and (ty is None or spec.border == "Floor"):
                return
            self.look_right = tx > self.ax
        elif spec.border in ("Floor", "Ceiling"):
            if random.random() < 0.5:
                self.look_right = not self.look_right
            if self.ax - area[0] < 60:
                self.look_right = True
            elif area[2] - self.ax < 60:
                self.look_right = False
        total = sum(p.dur for p in spec.poses)
        limit = total * random.randint(2, 5) if tx is None and spec.border != "Wall" else 2000
        it = self.cycle(spec.poses)
        jump_checked = 0
        for i in range(limit):
            p = next(it)
            sp = abs(p.vx)
            if tx is not None:
                d = tx - self.ax
                step = min(sp, abs(d))
                self.ax += step * (1 if d > 0 else -1)
                self.look_right = d > 0 if abs(d) > 0.5 else self.look_right
            else:
                self.ax += p.vx * (-1 if self.look_right else 1)
            if spec.border != "Floor":
                if ty is not None and p.vy:
                    d = ty - self.ay
                    self.ay += min(abs(p.vy), abs(d)) * (1 if d > 0 else -1)
                else:
                    self.ay += p.vy
            area = self.env.area_at(self.ax, self.ay)
            hit_edge = self.ax <= area[0] or self.ax >= area[2]
            self.clamp()
            if spec.border == "Floor":
                pl = self.env.on_floor(self.ax, self.ay)
                if pl is None:
                    yield p                    # bước hụt khỏi mép cửa sổ -> rơi
                    return
                self.ay = pl.y
                self.on_hwnd = pl.hwnd
                # thấy vật cản / chỗ cao phía trước -> nhảy lên
                jump_checked -= 1
                if jump_checked <= 0 and self.app.store.s.get("auto_jump", True):
                    jump_checked = 12
                    tgt = self.env.step_up_target(self.ax, self.ay, 1 if self.look_right else -1)
                    if tgt and random.random() < 0.7:
                        yield from self.jump_to(tgt[1], tgt[2])
                        return
            elif spec.border == "Wall":
                if self.ay <= area[1] + 0.5:
                    self.ay = area[1]
                    yield p
                    return
            if tx is not None and abs(self.ax - tx) < 0.5:
                yield p
                return
            if hit_edge and tx is None:
                yield p
                return
            yield p

    def act_fall(self, spec, a):
        g = float(a.get("Gravity", 2) or 2)
        rx = float(a.get("RegistanceX", a.get("ResistanceX", 0.05)) or 0)
        ry = float(a.get("RegistanceY", a.get("ResistanceY", 0.1)) or 0)
        vx, vy = self.vx, self.vy
        self.vx = self.vy = 0.0
        poses = spec.poses or (self.pack.actions.get("Fall").poses if self.pack.actions.get("Fall") else [])
        if not poses:
            return
        it = self.cycle(poses)
        for _ in range(3000):
            p = next(it)
            vx -= vx * rx
            vy += g - vy * ry
            if abs(vx) > 0.6:
                self.look_right = vx > 0
            n = int(max(abs(vx), abs(vy)) / 6) + 1
            for _ in range(n):
                nx, ny = self.ax + vx / n, self.ay + vy / n
                area = self.env.area_at(self.ax, self.ay)
                if nx <= area[0] or nx >= area[2]:
                    nx = max(area[0], min(area[2], nx))
                    hard = abs(vx) > 6 and ny < area[3] - 40
                    if hard and self.app.store.s.get("wall_hit_action", "TrangThai_AnVa"):
                        self.wall_hit = True            # đập vào tường: bật ra, rơi xuống rồi ăn vạ
                        vx = -vx * 0.35
                        vy = min(vy, 0.0) + 2.0
                    elif hard and self.app.store.s.get("climb", True):
                        self.ax, self.ay = nx, ny       # bị ném vào tường -> bám tường (kiểu cũ)
                        self.look_right = nx >= area[2]
                        yield p
                        return
                    else:
                        vx = -vx * 0.3
                if ny < area[1]:
                    ny, vy = area[1], 0.0
                if vy >= 0:
                    pl = self.env.landing(nx, self.ay, ny)
                    if pl is not None:
                        self.ax, self.ay = nx, pl.y
                        self.on_hwnd = pl.hwnd
                        yield p
                        return
                self.ax, self.ay = nx, ny
            yield p
        a2 = self.env.area_at(self.ax, self.ay)
        self.ay = a2[3]

    def jump_to(self, tx, ty, speed=None, poses=None):
        if poses is None:
            for nm in ("NhayLen", "Jumping", "Jump", "JumpToLeftWall", "Fall"):
                sp = self.pack.actions.get(nm)
                if sp and sp.poses:
                    poses = sp.poses
                    if speed is None:
                        speed = float(sp.attrs.get("VelocityParam", 18) or 18)
                    break
        if not poses:
            return
        speed = speed or 18
        it = self.cycle(poses)
        for _ in range(400):
            p = next(it)
            dx = tx - self.ax
            dy = ty - self.ay - abs(dx) / 2.0
            d = math.hypot(dx, dy)
            if abs(dx) > 0.5:
                self.look_right = dx > 0
            if d <= speed:
                self.ax, self.ay = tx, ty
                yield p
                break
            self.ax += speed * dx / d
            self.ay += speed * dy / d
            yield p
        if self.env.on_floor(self.ax, self.ay) is not None and "Land" in self.pack.actions:
            yield from self.run_action("Land")

    def act_jump(self, spec, a):
        tx = self.ev(a, "TargetX", self.ax)
        ty = self.ev(a, "TargetY", self.ay)
        area = self.env.area_at(self.ax, self.ay)
        tx = max(area[0], min(area[2], tx))
        ty = max(area[1], min(area[3], ty))
        sp = float(a.get("VelocityParam", 20) or 20)
        it = self.cycle(spec.poses or self.pack.actions["Fall"].poses)
        for _ in range(500):
            p = next(it)
            dx = tx - self.ax
            dy = ty - self.ay - abs(dx) / 2.0
            d = math.hypot(dx, dy)
            if abs(dx) > 0.5:
                self.look_right = dx > 0
            if d <= sp:
                self.ax, self.ay = tx, ty
                yield p
                return
            self.ax += sp * dx / d
            self.ay += sp * dy / d
            yield p

    def act_dragged(self, spec, a):
        it = self.cycle(spec.poses)
        self.drag_hist = []
        while self.dragging:
            cx, cy = self.env.cursor
            self.drag_hist.append((cx, cy))
            self.drag_hist = self.drag_hist[-4:]
            if len(self.drag_hist) >= 2 and abs(self.drag_hist[-1][0] - self.drag_hist[-2][0]) > 1:
                self.look_right = self.drag_hist[-1][0] < self.drag_hist[-2][0]
            self.ax, self.ay = cx, cy
            yield next(it)
        h = self.drag_hist
        if len(h) >= 2:
            k = len(h) - 1
            self.vx = (h[-1][0] - h[0][0]) / k
            self.vy = (h[-1][1] - h[0][1]) / k

    # ── chọn hành vi ──
    def allowed(self, n):
        if n in SYSTEM_BEHAVIORS:
            return True
        s = self.app.store.s
        if self.calm:
            return n in ("Stand", "StandAlt")
        if not s.get("free_master", True):
            return n in ("Stand", "StandAlt")
        if n in ("DiChuyen_BamVachTrai", "DiChuyen_BamVachPhai", "TrangThai_BiTreo") and not s.get("climb", True):
            return False
        if s.get("assigned_no_free", True) and n in self.pet.assigned():
            return False
        return bool((s.get("free") or {}).get(n, True))

    def pick(self):
        pk = self.pack
        if self.forced:
            n, self.forced = self.forced, None
            return n
        if self.sleep_beh and self.sleep_beh in pk.behaviors and self.cond_ok(pk.behaviors[self.sleep_beh].cond):
            return self.sleep_beh
        b = pk.behaviors.get(self.cur)
        cands = []

        def add(n, f, c=None):
            bb = pk.behaviors.get(n)
            if not bb or f <= 0 or not self.cond_ok(c) or not self.cond_ok(bb.cond) or not self.allowed(n):
                return
            cands.append((n, f))

        if b is not None and b.nexts:
            for n, f, c in b.nexts:
                add(n, f, c)
        if b is None or b.add or not b.nexts:
            for n in pk.order:
                add(n, pk.behaviors[n].freq)
        if cands:
            tot = sum(f for _, f in cands)
            r = random.uniform(0, tot)
            for n, f in cands:
                r -= f
                if r <= 0:
                    return n
            return cands[-1][0]
        if self.env.on_floor(self.ax, self.ay):
            return "Stand" if "Stand" in pk.actions else pk.order[0]
        if self.env.on_ceiling(self.ax, self.ay) and "GrabCeiling" in pk.actions:
            return "GrabCeiling"
        if self.env.on_wall(self.ax, self.ay) and "GrabWall" in pk.actions:
            return "GrabWall"
        return "Fall"

    def start(self, name):
        b = self.pack.behaviors.get(name)
        self.cur = name
        self.gen = self.run_action(b.action if b else name)

    def can_now(self, name):
        b = self.pack.behaviors.get(name)
        if b and b.cond and not self.cond_ok(b.cond):
            return False
        if b is None and self.env.on_floor(self.ax, self.ay) is None:
            return False
        return True

    def force(self, name, wait=True):
        """Gọi chiêu theo thao tác chuột / sự kiện.
        Đang rơi / leo tường thì giữ lệnh tối đa 4 giây, chạm đất là ra chiêu ngay."""
        if not name or self.dragging or name not in self.pack.actions:
            return False
        if not self.can_now(name):
            if wait:
                self.pending = (name, time_now() + 4.0)
            return False
        self.pending = None
        self.start(name)
        return True

    def fly_poses(self):
        # ưu tiên tư thế "lao vút" hl_hover (người thẳng, vệt lửa dưới chân)
        hov = []
        seen = set()
        for sp in self.pack.actions.values():
            for p in sp.poses:
                if p.img.lower().startswith("hl_hover") and p.img not in seen:
                    seen.add(p.img)
                    q = Pose()
                    q.img, q.imgr, q.ax, q.ay, q.vx, q.vy, q.dur = p.img, p.imgr, p.ax, p.ay, 0.0, 0.0, 1
                    hov.append(q)
        if hov:
            return sorted(hov, key=lambda q: q.img)
        for nm in ("HL_Bay", "Fly", "Flying"):
            sp = self.pack.actions.get(nm)
            if sp and sp.poses:
                return sp.poses
        for sp in self.pack.actions.values():
            if sp.type == "Embedded" and sp.cls == "Jump" and sp.poses:
                return sp.poses
        sp = self.pack.actions.get("Fall")
        return sp.poses if sp else []

    def fly_and_act(self, sx, sy, name, hold=0.0):
        """Lao thẳng tới điểm (toạ độ màn hình) rồi tung chiêu; giữa không trung thì đứng trên nền tạm.
        hold > 0: chỉ lao tới và đứng chờ (giây) – dùng khi vừa nhấn chuột, chưa biết bấm 1 hay 2 lần."""
        if self.dragging:
            return False
        if self.gen is not None:
            self.gen.close()         # đóng chiêu cũ trước (khối finally của nó sẽ dọn nền tạm cũ)
            self.gen = None
        z = self.env.zoom
        a = self.env.area_at(sx / z, sy / z)
        tx = max(a[0] + 10, min(a[2] - 10, sx / z))
        ty = max(a[1] + 60, min(a[3], sy / z))
        land = None
        for p in self.env.platforms:
            if p.kind != "temp" and p.x1 <= tx <= p.x2 and -10 <= p.y - ty <= 70:
                if land is None or p.y < land.y:
                    land = p
        self.env.temp = None
        if land is not None:
            ty = land.y
        else:
            self.env.temp = Platform(tx - 260, tx + 260, ty, "temp")
        self.env.refresh(force=False)
        if name and name not in self.pack.actions:
            name = ""
        self.pending = None
        self.cur = name or "Stand"
        self.gen = self._fly_gen(tx, ty, name, hold)
        return True

    def _fly_gen(self, tx, ty, name, hold=0.0):
        try:
            poses = self.fly_poses()
            d0 = math.hypot(tx - self.ax, ty - self.ay)
            if poses and d0 > 1:
                it = self.cycle(poses)
                # tốc độ theo quãng đường: xa cỡ nào cũng tới trong ~4 nhịp (~0,16 giây)
                sp = max(45.0, d0 / 4.0)
                for _ in range(60):
                    p = next(it)
                    dx, dy = tx - self.ax, ty - self.ay
                    d = math.hypot(dx, dy)
                    if abs(dx) > 1:
                        self.look_right = dx > 0
                    if d <= sp:
                        self.ax, self.ay = tx, ty
                        yield p
                        break
                    self.ax += sp * dx / d
                    self.ay += sp * dy / d
                    yield p
            self.ax, self.ay = tx, ty
            if hold > 0:
                st = self.pack.actions.get("Stand")
                poses = st.poses if st and st.poses else self.fly_poses()
                it = self.cycle(poses)
                for _ in range(int(hold * 1000 / TICK_MS)):
                    yield next(it)
            elif name:
                yield from self.run_action(self.pack.behaviors[name].action if name in self.pack.behaviors else name)
            else:
                st = self.pack.actions.get("Stand")
                if st:
                    yield from self.act_animate(st, {})
        finally:
            self.env.temp = None
            self.env.platforms = [p for p in self.env.platforms if p.kind != "temp"]

    def drop_parts(self, name):
        """Tách một động tác dạng chuỗi thành (đoạn rơi, các đoạn sau khi chạm đất).
        Ví dụ Rơi tạo hố = [nhảy vút] + RoiDauXuong (rơi) + HoDat (nện hố) -> (RoiDauXuong, [HoDat])."""
        b = self.pack.behaviors.get(name)
        spec = self.pack.actions.get(b.action if b else name)
        if not spec or spec.type != "Sequence":
            return None
        for i, (rn, ra) in enumerate(spec.refs):
            rs = self.pack.actions.get(rn)
            if rs and rs.type == "Embedded" and rs.cls == "Fall":
                return rn, [x for x, _ in spec.refs[i + 1:]]
        return None

    def drop_choices(self):
        """Các động tác dùng được khi thả nhân vật: chuỗi có đoạn rơi."""
        return [n for n in self.pack.user_behaviors() if self.drop_parts(n)]

    def after_drop(self):
        """Thả nhân vật đang bị xách: lao cắm đầu xuống theo đà tay rồi nện tạo hố."""
        name = self.app.store.s.get("drop_action", "VaCham_RoiHoDat")
        parts = self.drop_parts(name) if name else None
        if not parts:
            return False
        a = self.env.area_at(self.ax, self.ay)
        floor = self.env.landing(self.ax, self.ay, a[3] + 1)
        if floor is None or floor.y - self.ay < 40:             # thả sát đất: tiếp đất bình thường
            return False
        fall_name, after = parts
        self.cur = name
        self.gen = self._drop_gen(fall_name, after)
        return True

    def _drop_gen(self, fall_name, after):
        spec = self.pack.actions[fall_name]
        yield from self.act_fall(spec, dict(spec.attrs))
        if self.wall_hit:
            return                                            # đã đập tường -> ăn vạ thay vì nện hố
        if self.env.on_floor(self.ax, self.ay) is None:
            return                                            # va vào tường -> để engine chuyển sang bám tường
        for nm in after:
            yield from self.run_action(nm)

    def start_drag(self):
        if "Dragged" not in self.pack.actions:
            return
        self.env.temp = None
        self.env.platforms = [p for p in self.env.platforms if p.kind != "temp"]
        self.pending = None
        self.wall_hit = False
        self.dragging = True
        self.start("Dragged")

    def end_drag(self):
        self.dragging = False

    def tick(self):
        if self.pending and not self.dragging:
            n, until = self.pending
            if time_now() > until:
                self.pending = None
            elif self.can_now(n) and self.cur not in ("Dragged", "Thrown"):
                self.pending = None
                self.start(n)
        for _ in range(6):
            if self.gen is None:
                self.start(self.pick())
            try:
                self.pose = next(self.gen)
                break
            except StopIteration:
                self.gen = None
                if self.wall_hit and self.cur != "Dragged" and self.env.on_floor(self.ax, self.ay) is not None:
                    self.wall_hit = False
                    act = self.app.store.s.get("wall_hit_action", "TrangThai_AnVa")
                    if act in self.pack.actions:
                        self.forced = act             # rơi xuống đất sau cú đập tường -> ăn vạ
                        continue
                if self.cur == "Dragged":
                    if not self.after_drop():
                        sp = math.hypot(self.vx, self.vy)
                        self.forced = "Thrown" if sp > 5 and "Thrown" in self.pack.actions else "Fall"
            except Exception:
                log_error()
                self.gen = None
                self.cur = None
        # bám theo cửa sổ khi nó di chuyển
        if self.on_hwnd and not self.dragging:
            for p in self.env.platforms:
                if p.hwnd == self.on_hwnd:
                    if self.last_plat and (p.x1, p.y) != self.last_plat:
                        self.ax += p.x1 - self.last_plat[0]
                        self.ay += p.y - self.last_plat[1]
                    self.last_plat = (p.x1, p.y)
                    break
            else:
                self.last_plat = None
        else:
            self.last_plat = None


# ───────────────────────── Bong bóng thoại ─────────────────────────
class Bubble:
    PAD = 12
    TAIL = 14

    def __init__(self, app):
        self.app = app
        self.win = None
        self.msg = None
        self.queue = []
        self.hide_job = None
        self.above = True

    @property
    def visible(self):
        return self.win is not None

    def push(self, msg, front=False):
        # msg: dict(kind, title, text, buttons=[(label, fn, color)], timeout)
        if msg.get("key") and (self.msg and self.msg.get("key") == msg["key"] or any(m.get("key") == msg["key"] for m in self.queue)):
            return
        urgent = msg.get("kind") in ("reminder", "break")
        cur = self.msg.get("kind") if self.msg else None
        if urgent:
            # việc cần nhắc chen lên trước mọi lời chào / gợi ý / thông tin
            pos = 0
            while pos < len(self.queue) and self.queue[pos].get("kind") in ("reminder", "break"):
                pos += 1
            self.queue.insert(pos, msg)
            if cur in ("info", "greet", "suggest"):
                if cur != "info":
                    self.queue.insert(pos + 1, self.msg)
                self.close()
                return
        elif front:
            self.queue.insert(0, msg)
        else:
            self.queue.append(msg)
        if not self.visible:
            self.next()

    def next(self):
        if self.visible or not self.queue:
            return
        self.show(self.queue.pop(0))

    def show(self, msg):
        app = self.app
        urgent = msg.get("kind") in ("reminder", "break")
        if (app.hidden or app.fs_hidden) and not urgent:
            app.root.after(400, self.next)     # đang ẩn: bỏ lời nói chuyện, không bật chibi lên
            return
        self.msg = msg
        if app.hidden:
            app.unhide()
        wrap = int(300 * app.dpi)
        waiting = sum(1 for m in self.queue if m.get("kind") == "reminder")
        w = tk.Toplevel(app.root)
        w.withdraw()
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        if IS_WIN:
            try:
                w.attributes("-transparentcolor", KEY)
            except Exception:
                pass
        self.win = w
        cream = msg.get("bg", "#17121f")
        cv = tk.Canvas(w, bg=KEY, highlightthickness=0, bd=0)
        cv.pack()
        self.cv = cv
        fr = tk.Frame(cv, bg=cream)
        if msg.get("title"):
            tk.Label(fr, text=msg["title"], bg=cream, fg=msg.get("title_fg", "#ff5d6c"),
                     font=(FONT, 11, "bold"), justify="left", wraplength=wrap).pack(anchor="w")
        if msg.get("text"):
            tk.Label(fr, text=msg["text"], bg=cream, fg="#e8e3f0", font=(FONT, 10),
                     justify="left", wraplength=wrap).pack(anchor="w", pady=(2, 0))
        if msg.get("kind") == "reminder" and waiting:
            tk.Label(fr, text="(còn %d việc khác đang chờ nhắc)" % waiting, bg=cream, fg=C_MUTED,
                     font=(FONT, 9, "italic")).pack(anchor="w")
        btns = msg.get("buttons") or []
        if btns:
            row = tk.Frame(fr, bg=cream)
            row.pack(anchor="e", pady=(8, 0))
            for label, fn, color in btns:
                b = tk.Button(row, text=label, bg=color, fg="white", activebackground=shade(color, 0.85),
                              activeforeground="white", relief="flat", bd=0, padx=9, pady=3,
                              font=(FONT, 9, "bold"), cursor="hand2",
                              command=lambda f=fn: self._click(f))
                b.pack(side="left", padx=3)
        else:
            fr.bind("<Button-1>", lambda e: self.close())
            for c in fr.winfo_children():
                c.bind("<Button-1>", lambda e: self.close())
        self.frame_id = cv.create_window(self.PAD, self.PAD + self.TAIL, window=fr, anchor="nw")
        self.fr = fr
        fr.update_idletasks()
        self.fw, self.fh = fr.winfo_reqwidth(), fr.winfo_reqheight()
        self.W = self.fw + 2 * self.PAD
        self.H = self.fh + 2 * self.PAD + self.TAIL
        cv.config(width=self.W, height=self.H)
        self.above = None
        self.reposition(force=True)
        if not (app.hidden or app.fs_hidden):
            w.deiconify()
            w.attributes("-topmost", True)
        if msg.get("sound") and app.store.s.get("sound"):
            beep()
        if msg.get("timeout"):
            self.hide_job = app.root.after(int(msg["timeout"] * 1000), self.close)
        app.pet.on_bubble(msg)

    def drop(self, key):
        self.queue = [m for m in self.queue if m.get("key") != key]
        if self.msg and self.msg.get("key") == key:
            self.close()

    def _click(self, fn):
        try:
            self.close()
            if fn:
                fn()
        except Exception:
            log_error()

    def _shape(self, above, tail_x):
        cv = self.cv
        cv.delete("shape")
        P, T = self.PAD, self.TAIL
        x1, x2 = 2, self.W - 2
        if above:
            y1, y2 = 2, self.H - T - 2
        else:
            y1, y2 = T + 2, self.H - 2
        r = 12
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
               x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        bg = self.msg.get("bg", "#17121f")
        edge = self.msg.get("edge", C_ACC)
        cv.create_polygon(pts, smooth=True, fill=bg, outline=edge, width=2, tags="shape")
        tx = max(x1 + 18, min(x2 - 18, tail_x))
        if above:
            cv.create_polygon(tx - 9, y2 - 1, tx + 9, y2 - 1, tx, self.H - 1, fill=bg, outline=edge, width=2, tags="shape")
            cv.create_line(tx - 8, y2 - 1, tx + 8, y2 - 1, fill=bg, width=3, tags="shape")
            cv.coords(self.frame_id, P, P)
        else:
            cv.create_polygon(tx - 9, y1 + 1, tx + 9, y1 + 1, tx, 1, fill=bg, outline=edge, width=2, tags="shape")
            cv.create_line(tx - 8, y1 + 1, tx + 8, y1 + 1, fill=bg, width=3, tags="shape")
            cv.coords(self.frame_id, P, P + T)
        cv.tag_lower("shape")

    def reposition(self, force=False):
        if not self.visible:
            return
        pet = self.app.pet
        px, py, pw, ph = pet.x, pet.y, pet.W, pet.H
        head_top = int(pet.head_top())
        b = self.app.bounds
        above = head_top - self.H >= b[1]
        x = int(px + pw / 2 - self.W / 2)
        x = max(b[0], min(b[2] - self.W, x))
        y = head_top - self.H + 4 if above else py + ph - 6
        tail_x = int(px + pw / 2 - x)
        if force or above != self.above or getattr(self, "_tx", None) != tail_x:
            self._shape(above, tail_x)
            self.above, self._tx = above, tail_x
        self.win.geometry("+%d+%d" % (x, y))

    def close(self):
        if self.hide_job:
            try:
                self.app.root.after_cancel(self.hide_job)
            except Exception:
                pass
            self.hide_job = None
        if self.win:
            try:
                self.win.destroy()
            except Exception:
                pass
        self.win = None
        old = self.msg
        self.msg = None
        self.app.pet.on_bubble_closed(old)
        self.app.root.after(400, self.next)

    def set_shown(self, shown):
        if self.win:
            try:
                if shown:
                    self.win.deiconify()
                    self.win.attributes("-topmost", True)
                    self.reposition(force=True)
                else:
                    self.win.withdraw()
            except Exception:
                pass

    def raise_(self):
        if self.win:
            try:
                self.win.attributes("-topmost", True)
                self.win.lift()
            except Exception:
                pass


# ───────────────────────── Cửa sổ trong suốt mịn (per-pixel alpha) ─────────────────────────
class LayeredWin:
    """Vẽ ảnh RGBA thẳng lên màn hình bằng UpdateLayeredWindow: giữ nguyên hào quang, viền mờ, bóng."""

    def __init__(self, root, extra_ex=0):
        u32, g32 = ctypes.windll.user32, ctypes.windll.gdi32
        _win_api_setup()
        u32.GetDC.restype = wintypes.HDC
        u32.GetDC.argtypes = [wintypes.HWND]
        g32.CreateCompatibleDC.restype = wintypes.HDC
        g32.CreateCompatibleDC.argtypes = [wintypes.HDC]
        g32.CreateDIBSection.restype = wintypes.HBITMAP
        g32.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.c_void_p, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p),
                                         wintypes.HANDLE, wintypes.DWORD]
        g32.SelectObject.restype = wintypes.HGDIOBJ
        g32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
        g32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
        u32.UpdateLayeredWindow.argtypes = [wintypes.HWND, wintypes.HDC, ctypes.POINTER(wintypes.POINT),
                                            ctypes.POINTER(wintypes.SIZE), wintypes.HDC, ctypes.POINTER(wintypes.POINT),
                                            wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        u32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
        self.u32, self.g32 = u32, g32
        root.update_idletasks()
        self.hwnd = u32.GetAncestor(root.winfo_id(), 2) or root.winfo_id()
        ex = u32.GetWindowLongW(self.hwnd, -20)
        u32.SetWindowLongW(self.hwnd, -20, ex | 0x80000 | 0x80 | extra_ex)      # WS_EX_LAYERED | WS_EX_TOOLWINDOW
        self.hdc_screen = u32.GetDC(None)
        self.hdc_mem = g32.CreateCompatibleDC(self.hdc_screen)

        class BIH(ctypes.Structure):
            _fields_ = [("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                        ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_long),
                        ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]

        class BLEND(ctypes.Structure):
            _fields_ = [("op", ctypes.c_ubyte), ("flags", ctypes.c_ubyte), ("alpha", ctypes.c_ubyte), ("fmt", ctypes.c_ubyte)]
        self.BIH = BIH
        self.blend = BLEND(0, 0, 255, 1)

    def update(self, x, y, w, h, bgra):
        bih = self.BIH(ctypes.sizeof(self.BIH), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        bits = ctypes.c_void_p()
        hbmp = self.g32.CreateDIBSection(self.hdc_mem, ctypes.byref(bih), 0, ctypes.byref(bits), None, 0)
        if not hbmp:
            return False
        try:
            ctypes.memmove(bits, bgra, w * h * 4)
            old = self.g32.SelectObject(self.hdc_mem, hbmp)
            ok = self.u32.UpdateLayeredWindow(self.hwnd, self.hdc_screen, ctypes.byref(wintypes.POINT(x, y)),
                                              ctypes.byref(wintypes.SIZE(w, h)), self.hdc_mem,
                                              ctypes.byref(wintypes.POINT(0, 0)), 0, ctypes.byref(self.blend), 2)
            self.g32.SelectObject(self.hdc_mem, old)
            return bool(ok)
        finally:
            self.g32.DeleteObject(hbmp)


# ───────────────────────── Thao tác chuột ─────────────────────────
TRIGGERS = [
    ("L1", "Chuột trái – bấm 1 lần"), ("L2", "Chuột trái – bấm 2 lần"), ("L3", "Chuột trái – bấm liên tục (≥3)"),
    ("LH", "Chuột trái – bấm giữ"),
    ("R1", "Chuột phải – bấm 1 lần"), ("R2", "Chuột phải – bấm 2 lần"), ("R3", "Chuột phải – bấm liên tục (≥3)"),
    ("RH", "Chuột phải – bấm giữ"),
    ("WU", "Lăn chuột lên"), ("WD", "Lăn chuột xuống"), ("M1", "Nhấn con lăn"),
]
EVENTS = [
    ("E_REMIND", "Khi báo nhắc việc"), ("E_DONE", "Khi bấm Xong việc"), ("E_SNOOZE", "Khi bấm Hoãn"),
    ("E_SKIP", "Khi bấm Bỏ qua"), ("E_BREAK", "Khi nhắc nghỉ mắt"), ("E_GREET", "Khi chào buổi sáng"),
    ("E_SLEEP", "Khi bạn rời máy / giờ yên lặng (lặp lại)"), ("E_WAKE", "Khi bạn quay lại máy"),
    ("E_TYPING", "Khi gõ phím liên tục (~25 phím / 8 giây)"),
    ("E_DELETING", "Khi xoá liên tục (~8 lần / 3 giây) – lao tới chỗ xoá"),
]
SCREEN_TRIGGERS = [
    ("S_L1", "Màn hình – chuột trái 1 lần"), ("S_L2", "Màn hình – chuột trái 2 lần"),
    ("S_R1", "Màn hình – chuột phải 1 lần"), ("S_R2", "Màn hình – chuột phải 2 lần"),
    ("S_WU", "Màn hình – lăn chuột lên"), ("S_WD", "Màn hình – lăn chuột xuống"),
    ("S_M1", "Màn hình – nhấn con lăn"), ("S_HK", "Phím Ctrl + Alt + X (gọi tới chỗ chuột)"),
]
SCREEN_MODES = [("desktop", "Chỉ trên vùng trống desktop (an toàn)"),
                ("all", "Mọi nơi, kể cả vùng an toàn (không cần giữ phím)"), ("alt", "Giữ Alt + thao tác (mọi nơi)"),
                ("ctrlalt", "Giữ Ctrl + Alt + thao tác (mọi nơi)"), ("off", "Tắt")]
COMMANDS = [
    ("", "— Không —"), ("upcoming", "Xem việc sắp tới"), ("manager", "Mở bảng quản lý"), ("menu", "Mở menu nhanh"),
    ("add_task", "Thêm việc nhắc"), ("note", "Ghi nhận việc vừa làm"), ("chat", "Nói 1 câu ngẫu nhiên"),
    ("bigger", "Phóng to"), ("smaller", "Thu nhỏ"), ("toggle_free", "Bật/tắt tự hoạt động"),
    ("mute", "Im lặng 30 phút"), ("hide", "Ẩn 15 phút"),
]
DEFAULT_TRIGGERS = {
    "L1": {"act": "ChienDau_DamThep", "cmd": "upcoming"}, "L2": {"act": "", "cmd": "manager"},
    "L3": {"act": "BaKhi_FullCombo", "cmd": ""}, "LH": {"act": "BaKhi_NapNang", "cmd": ""},
    "R1": {"act": "", "cmd": "menu"}, "R2": {"act": "BieuCam_HoaCuong", "cmd": ""},
    "R3": {"act": "TrangThai_NanNi", "cmd": ""}, "RH": {"act": "HacLong_BayTheoChuot", "cmd": ""},
    "WU": {"act": "HacLong_NhayVut", "cmd": ""}, "WD": {"act": "NghiNgoi_Ngoi", "cmd": ""},
    "M1": {"act": "ChuotThu_ChayTheoChuot", "cmd": ""},
    "E_REMIND": {"act": "BaKhi_NoKhi"}, "E_DONE": {"act": "BieuCam_CuoiMaQuai"}, "E_SNOOZE": {"act": "TrangThai_AnVa"},
    "E_SKIP": {"act": "TrangThai_NgoiKhoc"}, "E_BREAK": {"act": "NghiNgoi_Ngoi"}, "E_GREET": {"act": "BieuCam_HoaCuong"},
    "E_SLEEP": {"act": "NghiNgoi_Ngu"}, "E_WAKE": {"act": "BaKhi_NoKhi"},
    "E_TYPING": {"act": "BaKhi_NapNang"}, "E_DELETING": {"act": "ChienDau_LaoChem"},
    "S_L1": {"act": "ChienDau_DamThep"}, "S_L2": {"act": "ChienDau_KiemKhi"},
    "S_R1": {"act": "ChienDau_LaoChem"}, "S_R2": {"act": "BaKhi_FullCombo"},
    "S_WU": {"act": "ChienDau_DamSongAm"}, "S_WD": {"act": "NghiNgoi_Ngoi"},
    "S_M1": {"act": "BaKhi_NoKhi"}, "S_HK": {"act": "BieuCam_CuoiMaQuai"},
}


class Mouse:
    HOLD_MS = 550
    MULTI_MS = 300

    def __init__(self, pet):
        self.pet = pet
        r = pet.root
        self.down, self.hold_job, self.hold_fired = {}, {}, {}
        self.count, self.timer, self.rapid = {}, {}, {}
        self.dragging = False
        self.last_wheel = 0
        self.last_event = None
        r.bind("<ButtonPress-1>", lambda e: self.press(e, "L"))
        r.bind("<ButtonRelease-1>", lambda e: self.release(e, "L"))
        r.bind("<B1-Motion>", self.motion)
        r.bind("<ButtonPress-3>", lambda e: self.press(e, "R"))
        r.bind("<ButtonRelease-3>", lambda e: self.release(e, "R"))
        r.bind("<ButtonRelease-2>", lambda e: self.fire("M1", e))
        r.bind("<MouseWheel>", self.wheel)
        r.bind("<Button-4>", lambda e: self.wheel(e, 120))
        r.bind("<Button-5>", lambda e: self.wheel(e, -120))
        r.bind("<Enter>", lambda e: setattr(pet, "hover", True))
        r.bind("<Leave>", lambda e: setattr(pet, "hover", False))

    def press(self, e, b):
        self.last_event = e
        self.down[b] = (e.x_root, e.y_root)
        self.hold_fired[b] = False
        if self.hold_job.get(b):
            self.pet.root.after_cancel(self.hold_job[b])
        self.hold_job[b] = self.pet.root.after(self.HOLD_MS, lambda: self.hold(b))

    def motion(self, e):
        d = self.down.get("L")
        if not d:
            return
        if not self.dragging and abs(e.x_root - d[0]) + abs(e.y_root - d[1]) > 6 and not self.hold_fired.get("L"):
            self.dragging = True
            self._cancel_hold("L")
            self.pet.engine.start_drag()

    def _cancel_hold(self, b):
        if self.hold_job.get(b):
            try:
                self.pet.root.after_cancel(self.hold_job[b])
            except Exception:
                pass
            self.hold_job[b] = None

    def hold(self, b):
        self.hold_job[b] = None
        if b in self.down and not self.dragging:
            self.hold_fired[b] = True
            self.fire(b + "H", self.last_event)

    def release(self, e, b):
        self.last_event = e
        self._cancel_hold(b)
        self.down.pop(b, None)
        if b == "L" and self.dragging:
            self.dragging = False
            self.pet.engine.end_drag()
            return
        if self.hold_fired.get(b):
            self.hold_fired[b] = False
            return
        self.count[b] = self.count.get(b, 0) + 1
        if self.count[b] == 3:
            self.rapid[b] = True
            self.fire(b + "3", e)
        if self.timer.get(b):
            self.pet.root.after_cancel(self.timer[b])
        self.timer[b] = self.pet.root.after(self.MULTI_MS, lambda: self.finish(b))

    def finish(self, b):
        self.timer[b] = None
        n = self.count.get(b, 0)
        if not self.rapid.get(b) and n:
            self.fire(b + ("1" if n == 1 else "2"), self.last_event)
        self.count[b] = 0
        self.rapid[b] = False

    def wheel(self, e, delta=None):
        delta = delta if delta is not None else e.delta
        if e.state & 0x0004:                    # Ctrl + lăn: đổi kích thước
            self.pet.app.set_scale(self.pet.s_user + (0.1 if delta > 0 else -0.1))
            return
        t = time_now()
        if t - self.last_wheel < 0.35:
            return
        self.last_wheel = t
        self.fire("WU" if delta > 0 else "WD", e)

    def fire(self, key, e=None):
        self.pet.trigger(key, e)


class GlobalMouse:
    """Bắt thao tác chuột trên toàn màn hình bằng hook cấp thấp (luồng riêng, chỉ xếp hàng sự kiện rồi trả về ngay)."""

    def __init__(self, app):
        import queue
        self.app = app
        self.q = queue.Queue()
        self.mode = "off"
        self.swallow = set()
        self.tid = None
        self.down = {}
        self.count, self.timer = {}, {}
        self.last_wheel = 0
        self.ok = False

    def start(self):
        if not IS_WIN:
            return
        threading.Thread(target=self._run, daemon=True).start()

    def set_keyboard(self, on):
        if self.tid:
            try:
                ctypes.windll.user32.PostThreadMessageW(self.tid, 0x8001 if on else 0x8002, 0, 0)
            except Exception:
                log_error()

    def stop(self):
        if self.tid:
            try:
                ctypes.windll.user32.PostThreadMessageW(self.tid, 0x0012, 0, 0)   # WM_QUIT
            except Exception:
                pass

    def _run(self):
        try:
            _win_api_setup()
            u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
            self.tid = k32.GetCurrentThreadId()

            class MSLL(ctypes.Structure):
                _fields_ = [("pt", wintypes.POINT), ("mouseData", wintypes.DWORD), ("flags", wintypes.DWORD),
                            ("time", wintypes.DWORD), ("extra", ctypes.c_size_t)]
            Proc = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
            u32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
            u32.CallNextHookEx.restype = ctypes.c_ssize_t
            u32.SetWindowsHookExW.argtypes = [ctypes.c_int, Proc, wintypes.HINSTANCE, wintypes.DWORD]
            u32.SetWindowsHookExW.restype = wintypes.HHOOK
            k32.GetModuleHandleW.restype = wintypes.HMODULE
            u32.GetAsyncKeyState.restype = ctypes.c_short

            def proc(code, wp, lp):
                if code == 0:
                    try:
                        if self._handle(int(wp), ctypes.cast(lp, ctypes.POINTER(MSLL)).contents):
                            return 1
                    except Exception:
                        pass
                return u32.CallNextHookEx(None, code, wp, lp)

            self._proc = Proc(proc)
            hook = u32.SetWindowsHookExW(14, self._proc, k32.GetModuleHandleW(None), 0)
            hot = u32.RegisterHotKey(None, 1, 0x0002 | 0x0001 | 0x4000, ord("X"))   # Ctrl+Alt+X
            self.ok = bool(hook)

            class KBLL(ctypes.Structure):
                _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD), ("flags", wintypes.DWORD),
                            ("time", wintypes.DWORD), ("extra", ctypes.c_size_t)]

            def kproc(code, wp, lp):
                # chỉ phân loại GÕ / XOÁ rồi bỏ vào hàng đợi – không lưu, không chặn phím nào
                if code == 0 and wp in (0x100, 0x104):
                    try:
                        k = ctypes.cast(lp, ctypes.POINTER(KBLL)).contents
                        kind = classify_key(k.vkCode, bool(k.flags & 0x10),
                                            bool(u32.GetAsyncKeyState(0x11) & 0x8000),
                                            bool(k.flags & 0x20) or bool(u32.GetAsyncKeyState(0x12) & 0x8000),
                                            bool((u32.GetAsyncKeyState(0x5B) | u32.GetAsyncKeyState(0x5C)) & 0x8000))
                        if kind:
                            self.q.put(("K", kind))
                    except Exception:
                        pass
                return u32.CallNextHookEx(None, code, wp, lp)

            self._kproc = Proc(kproc)
            khook = None
            if self.app.store.s.get("key_fx", True):
                khook = u32.SetWindowsHookExW(13, self._kproc, k32.GetModuleHandleW(None), 0)
            msg = wintypes.MSG()
            while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == 0x0312:
                    self.q.put(("HK",))
                elif msg.message == 0x8001 and not khook:            # bật hiệu ứng gõ phím -> cài hook bàn phím
                    khook = u32.SetWindowsHookExW(13, self._kproc, k32.GetModuleHandleW(None), 0)
                elif msg.message == 0x8002 and khook:                # tắt -> gỡ hẳn hook
                    u32.UnhookWindowsHookEx(khook)
                    khook = None
            if khook:
                u32.UnhookWindowsHookEx(khook)
            if hook:
                u32.UnhookWindowsHookEx(hook)
            if hot:
                u32.UnregisterHotKey(None, 1)
        except Exception:
            log_error()

    def _handle(self, wp, m):
        btn = {0x201: "L", 0x202: "L", 0x204: "R", 0x205: "R", 0x207: "M", 0x208: "M", 0x20A: "W"}.get(wp)
        if not btn:
            return False
        up = wp in (0x202, 0x205, 0x208)
        if up and btn in self.swallow:          # đã chặn cú nhấn xuống thì chặn luôn cú nhả
            self.swallow.discard(btn)
            self.q.put((btn, "up", m.pt.x, m.pt.y))
            return True
        mode = self.mode
        if mode == "off" or (m.flags & 1):      # bỏ qua chuột giả lập
            return False
        u32 = ctypes.windll.user32
        root = _root_of_point(m.pt.x, m.pt.y)
        if root:
            pid = wintypes.DWORD()
            u32.GetWindowThreadProcessId(root, ctypes.byref(pid))
            if pid.value == os.getpid():
                return False                    # trên cửa sổ của chính app -> để app tự xử lý
        if mode == "desktop":
            ok = bool(root) and _class_name(root) in ("Progman", "WorkerW")
        elif mode == "all":
            ok = True
        else:
            alt = u32.GetAsyncKeyState(0x12) & 0x8000
            ctrl = u32.GetAsyncKeyState(0x11) & 0x8000
            ok = bool(alt) and (bool(ctrl) if mode == "ctrlalt" else not ctrl)
        if not ok:
            return False
        if btn == "W":
            self.q.put(("W", ctypes.c_short((m.mouseData >> 16) & 0xFFFF).value, m.pt.x, m.pt.y))
        else:
            self.q.put((btn, "up" if up else "down", m.pt.x, m.pt.y))
        if mode in ("desktop", "all"):
            return False                        # không chặn: chuột vẫn chạy bình thường
        if not up and btn != "W":
            self.swallow.add(btn)
        return True                             # chế độ phím: chặn để phần mềm bên dưới không nhận cú bấm

    # ── luồng chính: gom cú bấm thành 1 lần / 2 lần ──
    def poll(self):
        self.mode = self.app.store.s.get("screen_mode", "desktop")
        while True:
            try:
                ev = self.q.get_nowait()
            except Exception:
                break
            if self.app.hidden or self.app.fs_hidden:
                continue
            k = ev[0]
            if k == "K":
                self.app.keyfx.on_key(ev[1])
                continue
            if k == "HK":
                x, y = self.app.root.winfo_pointerxy()
                self.fire("S_HK", x, y)
            elif k == "W":
                t = time_now()
                if t - self.last_wheel >= 0.35:
                    self.last_wheel = t
                    self.fire("S_WU" if ev[1] > 0 else "S_WD", ev[2], ev[3])
            elif ev[1] == "down":
                self.down[k] = (ev[2], ev[3], time_now())
                if self.has_act(k):
                    # lao tới ngay khi vừa nhấn xuống -> tới nơi cùng lúc với cú bấm
                    self.app.pet.engine.fly_and_act(ev[2], ev[3], "", hold=1.2)
            else:
                d = self.down.pop(k, None)
                if not d or abs(ev[2] - d[0]) + abs(ev[3] - d[1]) > 10 or time_now() - d[2] > 0.6:
                    continue                    # kéo chọn vùng / giữ lâu -> không tính
                if k == "M":
                    self.fire("S_M1", ev[2], ev[3])
                    continue
                self.count[k] = self.count.get(k, 0) + 1
                if self.timer.get(k):
                    self.app.root.after_cancel(self.timer[k])
                self.timer[k] = self.app.root.after(300, lambda k=k, x=ev[2], y=ev[3]: self.finish(k, x, y))

    def has_act(self, k):
        tr = self.app.store.s.get("triggers") or {}
        keys = {"L": ("S_L1", "S_L2"), "R": ("S_R1", "S_R2"), "M": ("S_M1",)}.get(k, ())
        return any((tr.get(x) or {}).get("act") for x in keys)

    def finish(self, k, x, y):
        n = self.count.get(k, 0)
        self.count[k], self.timer[k] = 0, None
        if n:
            self.fire("S_%s%d" % (k, 1 if n == 1 else 2), x, y)

    def fire(self, key, x, y):
        m = (self.app.store.s.get("triggers") or {}).get(key) or {}
        if key != "S_HK" and not m.get("act"):
            return
        self.app.pet.engine.fly_and_act(x, y, m.get("act") or "")


# ───────────────────────── Hiệu ứng gõ phím: lôi điện khi gõ, loạn đao khi xoá ─────────────────────────
def classify_key(vk, injected, ctrl, alt, win):
    """'T' = gõ ký tự, 'D' = xoá, None = bỏ qua. Không lưu lại phím nào."""
    if injected:
        return "T" if vk == 0xE7 else None      # phím giả lập (Unikey/EVKey bỏ dấu): chỉ tính ký tự Unicode
    if vk in (0x08, 0x2E):                      # Backspace, Delete (kể cả Ctrl+Backspace)
        return "D"
    if ctrl or alt or win:
        return None                             # phím tắt Ctrl+C, Alt+Tab... không tính
    if (vk in (0x20, 0x0D, 0xE2, 0xE5) or 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A or 0x60 <= vk <= 0x6F
            or 0xBA <= vk <= 0xC0 or 0xDB <= vk <= 0xDF):
        return "T"
    return None


def caret_info():
    """(vị trí con trỏ nhập trên màn hình hoặc None, đang ở ô mật khẩu?)"""
    if not IS_WIN:
        return None, False
    try:
        u32 = ctypes.windll.user32

        class GTI(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD), ("hwndActive", wintypes.HWND),
                        ("hwndFocus", wintypes.HWND), ("hwndCapture", wintypes.HWND), ("hwndMenuOwner", wintypes.HWND),
                        ("hwndMoveSize", wintypes.HWND), ("hwndCaret", wintypes.HWND), ("rcCaret", wintypes.RECT)]
        fg = u32.GetForegroundWindow()
        if not fg:
            return None, False
        tid = u32.GetWindowThreadProcessId(fg, None)
        gi = GTI()
        gi.cbSize = ctypes.sizeof(GTI)
        if not u32.GetGUIThreadInfo(tid, ctypes.byref(gi)):
            return None, False
        pw = False
        if gi.hwndFocus:
            cls = _class_name(gi.hwndFocus).lower()
            if "edit" in cls and u32.GetWindowLongW(gi.hwndFocus, -16) & 0x20:     # ES_PASSWORD
                pw = True
        if gi.hwndCaret:
            r = gi.rcCaret
            pt = wintypes.POINT(r.left, (r.top + r.bottom) // 2)
            u32.ClientToScreen(gi.hwndCaret, ctypes.byref(pt))
            return (pt.x, pt.y), pw
        return None, pw
    except Exception:
        return None, False


def _bezier(p0, p1, p2, n=18):
    out = []
    for i in range(n + 1):
        t = i / float(n)
        a, b, c = (1 - t) ** 2, 2 * (1 - t) * t, t * t
        out.append((a * p0[0] + b * p1[0] + c * p2[0], a * p0[1] + b * p1[1] + c * p2[1]))
    return out


def make_bolt_frames(size, seed):
    """Lôi điện tím xanh toả ra từ con trỏ nhập: 6 khung (~0,24 giây)."""
    from PIL import ImageDraw, ImageFilter
    rnd = random.Random(seed)
    W = H = size
    c = (W / 2.0, H / 2.0)
    bolts = []
    for _ in range(rnd.randint(2, 3)):
        ang = rnd.uniform(0, 2 * math.pi)
        bolts.append((ang, rnd.uniform(0.32, 0.47) * W))
    frames = []
    for f in range(6):
        fade = (1.0, 1.0, 0.9, 0.65, 0.4, 0.18)[f]
        grow = min(1.0, (f + 1) / 2.0)
        core = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dc, dg = ImageDraw.Draw(core), ImageDraw.Draw(glow)
        for ang, L in bolts:
            pts = [c]
            seg = 7
            for i in range(1, seg + 1):
                t = i / float(seg) * grow
                j = rnd.uniform(-1, 1) * W * 0.07
                pts.append((c[0] + math.cos(ang) * L * t - math.sin(ang) * j,
                            c[1] + math.sin(ang) * L * t + math.cos(ang) * j))
            lines = [pts]
            if len(pts) > 4 and rnd.random() < 0.75:          # nhánh rẽ
                k = rnd.randint(2, len(pts) - 2)
                a2 = ang + rnd.choice((-1, 1)) * rnd.uniform(0.5, 1.0)
                bx, by = pts[k]
                br = [(bx, by)]
                for i in range(1, 4):
                    t = i / 3.0 * L * 0.35
                    br.append((bx + math.cos(a2) * t + rnd.uniform(-1, 1) * W * 0.03,
                               by + math.sin(a2) * t + rnd.uniform(-1, 1) * W * 0.03))
                lines.append(br)
            for n_, ln in enumerate(lines):
                k_ = 1.0 if n_ == 0 else 0.6
                dg.line(ln, fill=(120, 60, 255, int(210 * fade)), width=max(3, int(W * 0.07 * k_)))
                dc.line(ln, fill=(185, 165, 255, int(255 * fade)), width=max(2, int(W * 0.024 * k_)))
                dc.line(ln, fill=(255, 255, 255, int(255 * fade)), width=max(1, int(W * 0.01 * k_)))
        if f < 3:                                            # chớp sáng tại tâm
            r = W * (0.09 - f * 0.02)
            dg.ellipse((c[0] - r * 2, c[1] - r * 2, c[0] + r * 2, c[1] + r * 2), fill=(140, 90, 255, int(160 * fade)))
            dc.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), fill=(255, 255, 255, int(240 * fade)))
        for _ in range(rnd.randint(3, 6)):                   # tia lửa
            a = rnd.uniform(0, 2 * math.pi)
            rr = rnd.uniform(0.08, 0.42) * W * grow
            x, y = c[0] + math.cos(a) * rr, c[1] + math.sin(a) * rr
            q = max(1, W * 0.012)
            dc.ellipse((x - q, y - q, x + q, y + q), fill=(225, 215, 255, int(255 * fade)))
        glow = glow.filter(ImageFilter.GaussianBlur(max(1, W * 0.03)))
        glow.alpha_composite(core)
        frames.append(glow)
    return frames


def make_slash_frames(size, seed):
    """Loạn đao chém: 3–5 nhát lưỡi liềm đỏ trắng xuất hiện liên tiếp rồi tan, 8 khung (~0,32 giây)."""
    from PIL import ImageDraw, ImageFilter
    rnd = random.Random(seed + 1000)
    W = H = size
    c = (W / 2.0, H / 2.0)
    cuts = []
    for _ in range(rnd.randint(3, 5)):
        ang = rnd.uniform(0, math.pi)
        off = (rnd.uniform(-0.12, 0.12) * W, rnd.uniform(-0.12, 0.12) * H)
        cuts.append((ang, off, rnd.uniform(0.6, 0.85) * W, rnd.choice((-1, 1)) * rnd.uniform(0.08, 0.16) * W))
    frames = []
    for f in range(8):
        core = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dc, dg = ImageDraw.Draw(core), ImageDraw.Draw(glow)
        for idx, (ang, off, L, bulge) in enumerate(cuts):
            age = f - idx
            if age < 0:
                continue
            al = max(0.0, 1.0 - age * 0.24)
            if al <= 0:
                continue
            reach = min(1.0, 0.45 + age * 0.55)              # nhát chém vươn dài ra
            cx, cy = c[0] + off[0], c[1] + off[1]
            dx, dy = math.cos(ang) * L / 2 * reach, math.sin(ang) * L / 2 * reach
            nx, ny = -math.sin(ang), math.cos(ang)
            p0, p2 = (cx - dx, cy - dy), (cx + dx, cy + dy)
            outer = _bezier(p0, (cx + nx * bulge, cy + ny * bulge), p2)
            inner = _bezier(p0, (cx + nx * bulge * 0.45, cy + ny * bulge * 0.45), p2)
            blade = outer + inner[::-1]
            dg.polygon(blade, fill=(255, 10, 40, int(235 * al)))
            dg.line(outer, fill=(255, 20, 50, int(220 * al)), width=max(3, int(W * 0.07)))
            dc.polygon(blade, fill=(255, 55, 80, int(255 * al)))
            dc.line(outer, fill=(255, 255, 255, int(255 * al)), width=max(1, int(W * 0.014)))
            if age == 0:                                     # tia lửa văng ra ở mũi đao
                for _ in range(3):
                    q = max(1, W * 0.012)
                    x = p2[0] + rnd.uniform(-1, 1) * W * 0.08
                    y = p2[1] + rnd.uniform(-1, 1) * W * 0.08
                    dc.ellipse((x - q, y - q, x + q, y + q), fill=(255, 220, 120, 255))
        glow = glow.filter(ImageFilter.GaussianBlur(max(1, W * 0.035)))
        glow.alpha_composite(core)
        frames.append(glow)
    return frames


def _fx_new(W, H):
    from PIL import ImageDraw
    core = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    return core, glow, ImageDraw.Draw(core), ImageDraw.Draw(glow)


def _fx_merge(core, glow, blur):
    from PIL import ImageFilter
    if blur > 0:
        glow = glow.filter(ImageFilter.GaussianBlur(blur))
    glow.alpha_composite(core)
    return glow


def _jagged(p0, p1, segs, amp, rnd):
    pts = [p0]
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy) or 1
    nx, ny = -dy / L, dx / L
    for i in range(1, segs):
        t = i / float(segs)
        j = rnd.uniform(-1, 1) * amp
        pts.append((p0[0] + dx * t + nx * j, p0[1] + dy * t + ny * j))
    pts.append(p1)
    return pts


def make_thunder_frames(size, seed):
    """Lôi đình giáng xuống: sét đánh từ trên xuống chữ, chớp sáng chỗ chạm."""
    rnd = random.Random(seed + 2000)
    W, H = size, int(size * 1.8)
    hit = (W / 2.0, H * 0.9)
    top = (W / 2.0 + rnd.uniform(-0.25, 0.25) * W, 0)
    main = _jagged(top, hit, 10, W * 0.09, rnd)
    branches = []
    for _ in range(rnd.randint(2, 3)):
        k = rnd.randint(2, 7)
        bx, by = main[k]
        branches.append(_jagged((bx, by), (bx + rnd.uniform(-0.4, 0.4) * W, by + rnd.uniform(0.12, 0.28) * H), 4, W * 0.04, rnd))
    frames = []
    for f in range(7):
        core, glow, dc, dg = _fx_new(W, H)
        if f == 0:                                           # tia dẫn mờ
            dc.line(main[:6], fill=(200, 200, 255, 150), width=max(1, int(W * 0.01)))
        else:
            fade = (1, 1, 1, 0.8, 0.55, 0.3, 0.12)[f]
            if f <= 3:
                for b in branches:
                    dg.line(b, fill=(110, 130, 255, int(170 * fade)), width=max(2, int(W * 0.04)))
                    dc.line(b, fill=(230, 235, 255, int(230 * fade)), width=max(1, int(W * 0.012)))
                dg.line(main, fill=(90, 120, 255, int(230 * fade)), width=max(4, int(W * 0.11)))
                dc.line(main, fill=(200, 215, 255, int(255 * fade)), width=max(2, int(W * 0.035)))
                dc.line(main, fill=(255, 255, 255, int(255 * fade)), width=max(1, int(W * 0.014)))
            r = min(W * (0.10 + 0.05 * f), W * 0.28)
            dg.ellipse((hit[0] - r * 1.6, hit[1] - r * 0.6, hit[0] + r * 1.6, hit[1] + r * 0.4),
                       fill=(120, 150, 255, int(200 * fade)))
            if f <= 2:
                rr = W * 0.08
                dc.ellipse((hit[0] - rr, hit[1] - rr * 0.6, hit[0] + rr, hit[1] + rr * 0.6), fill=(255, 255, 255, 255))
            for _ in range(6):                                # tia lửa bắn ngang
                a = rnd.uniform(math.pi * 1.05, math.pi * 1.95)
                d = W * rnd.uniform(0.1, 0.45) * min(1, f / 2.0)
                x, y = hit[0] + math.cos(a) * d, hit[1] + math.sin(a) * d * 0.5
                q = max(1, W * 0.012)
                dc.ellipse((x - q, y - q, x + q, y + q), fill=(220, 230, 255, int(255 * fade)))
        frames.append(_fx_merge(core, glow, max(1, W * 0.035)))
    return frames


def make_holy_frames(size, seed):
    """Thần quang vàng: hào quang toả tia, vòng sáng lan ra."""
    rnd = random.Random(seed + 3000)
    W = H = size
    c = (W / 2.0, H / 2.0)
    n = rnd.randint(10, 14)
    rot = rnd.uniform(0, math.pi)
    lens = [rnd.uniform(0.32, 0.5) for _ in range(n)]
    frames = []
    for f in range(8):
        core, glow, dc, dg = _fx_new(W, H)
        fade = (0.7, 1, 1, 0.9, 0.7, 0.5, 0.3, 0.12)[f]
        grow = min(1.0, (f + 1) / 3.0)
        for i in range(n):
            a = rot + i * 2 * math.pi / n + f * 0.04
            L = lens[i] * W * grow
            wdt = W * 0.035
            tip = (c[0] + math.cos(a) * L, c[1] + math.sin(a) * L)
            s1 = (c[0] + math.cos(a + math.pi / 2) * wdt, c[1] + math.sin(a + math.pi / 2) * wdt)
            s2 = (c[0] + math.cos(a - math.pi / 2) * wdt, c[1] + math.sin(a - math.pi / 2) * wdt)
            dg.polygon([s1, tip, s2], fill=(255, 200, 40, int(190 * fade)))
            dc.line([c, tip], fill=(255, 245, 190, int(230 * fade)), width=max(1, int(W * 0.01)))
        r = W * (0.12 + 0.36 * f / 7.0)
        dc.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), outline=(255, 220, 90, int(220 * fade)),
                   width=max(1, int(W * 0.015)))
        rc = W * (0.12 if f < 3 else 0.08)
        dg.ellipse((c[0] - rc * 2, c[1] - rc * 2, c[0] + rc * 2, c[1] + rc * 2), fill=(255, 210, 60, int(200 * fade)))
        dc.ellipse((c[0] - rc, c[1] - rc, c[0] + rc, c[1] + rc), fill=(255, 252, 230, int(255 * fade)))
        for _ in range(4):                                    # lấp lánh hình chữ thập
            a = rnd.uniform(0, 2 * math.pi)
            d = rnd.uniform(0.2, 0.45) * W * grow
            x, y = c[0] + math.cos(a) * d, c[1] + math.sin(a) * d
            q = W * 0.03
            dc.line([(x - q, y), (x + q, y)], fill=(255, 250, 200, int(255 * fade)), width=1)
            dc.line([(x, y - q), (x, y + q)], fill=(255, 250, 200, int(255 * fade)), width=1)
        frames.append(_fx_merge(core, glow, max(1, W * 0.03)))
    return frames


def _draw_skull(dc, dg, cx, cy, r, al, glowc):
    dg.ellipse((cx - r * 1.7, cy - r * 1.6, cx + r * 1.7, cy + r * 1.9), fill=glowc + (int(170 * al),))
    bone = (232, 236, 222, int(255 * al))
    dc.ellipse((cx - r, cy - r, cx + r, cy + r * 0.85), fill=bone)
    dc.rounded_rectangle((cx - r * 0.55, cy + r * 0.45, cx + r * 0.55, cy + r * 1.15), radius=max(1, r * 0.2), fill=bone)
    e = r * 0.33
    for sx in (-1, 1):
        ex = cx + sx * r * 0.4
        dc.ellipse((ex - e, cy - e * 0.6, ex + e, cy + e * 1.2), fill=(25, 0, 35, int(255 * al)))
        dc.ellipse((ex - e * 0.35, cy + e * 0.05, ex + e * 0.35, cy + e * 0.6), fill=glowc + (int(255 * al),))
    dc.polygon([(cx, cy + r * 0.4), (cx - r * 0.12, cy + r * 0.62), (cx + r * 0.12, cy + r * 0.62)],
               fill=(25, 0, 35, int(255 * al)))
    for i in (-1, 0, 1):
        x = cx + i * r * 0.2
        dc.line([(x, cy + r * 0.8), (x, cy + r * 1.1)], fill=(60, 50, 70, int(255 * al)), width=1)


def make_skull_frames(size, seed):
    """Đầu lâu ma quái li ti bay lên, mắt xanh ma trơi."""
    rnd = random.Random(seed + 4000)
    W, H = size, int(size * 1.4)
    sk = []
    for _ in range(rnd.randint(2, 3)):
        sk.append((W / 2.0 + rnd.uniform(-0.25, 0.25) * W, rnd.uniform(0.07, 0.11) * W, rnd.uniform(0, 6.3),
                   rnd.choice(((90, 255, 160), (180, 100, 255), (120, 230, 255)))))
    frames = []
    for f in range(10):
        core, glow, dc, dg = _fx_new(W, H)
        t = f / 9.0
        al = min(1.0, (f + 1) / 2.0) * (1 - max(0, t - 0.55) / 0.45)
        for x0, r, ph, col in sk:
            cy = H * 0.85 - t * H * 0.7
            cx = x0 + math.sin(ph + f * 0.8) * W * 0.06
            for k in range(1, 4):                              # vệt khói ma phía dưới
                ty = cy + r * (1.2 + k * 0.9)
                tx = x0 + math.sin(ph + (f - k * 0.6) * 0.8) * W * 0.06
                q = r * (0.7 - k * 0.15)
                dg.ellipse((tx - q, ty - q, tx + q, ty + q), fill=col + (int(110 * al / k),))
            _draw_skull(dc, dg, cx, cy, r * (0.8 + 0.2 * min(1, f / 2.0)), max(0, al), col)
        frames.append(_fx_merge(core, glow, max(1, W * 0.025)))
    return frames


def make_darkflame_frames(size, seed):
    """Hắc diễm: lưỡi lửa đen viền tím đỏ bùng lên."""
    rnd = random.Random(seed + 5000)
    W, H = size, int(size * 1.3)
    tongues = [(W / 2.0 + rnd.uniform(-0.22, 0.22) * W, rnd.uniform(0.35, 0.65) * H, rnd.uniform(0.06, 0.1) * W,
                rnd.uniform(0, 6)) for _ in range(rnd.randint(4, 6))]
    frames = []
    for f in range(8):
        core, glow, dc, dg = _fx_new(W, H)
        fade = (0.6, 1, 1, 1, 0.85, 0.6, 0.35, 0.15)[f]
        grow = min(1.0, (f + 1) / 3.0)
        base = H * 0.85
        for x0, L, w, ph in tongues:
            L2 = L * grow * (0.85 + 0.15 * math.sin(ph + f * 1.7))
            sway = math.sin(ph + f * 1.3) * w * 0.8
            tip = (x0 + sway, base - L2)
            pts = [(x0 - w, base)]
            for k in range(1, 6):
                t = k / 6.0
                pts.append((x0 - w * (1 - t) + sway * t + math.sin(ph + k + f) * w * 0.2, base - L2 * t))
            pts.append(tip)
            for k in range(5, 0, -1):
                t = k / 6.0
                pts.append((x0 + w * (1 - t) + sway * t + math.sin(ph - k + f) * w * 0.2, base - L2 * t))
            pts.append((x0 + w, base))
            dg.polygon(pts, fill=(150, 40, 255, int(210 * fade)))
            dc.polygon(pts, fill=(25, 5, 35, int(235 * fade)), outline=(255, 60, 110, int(255 * fade)))
        dg.ellipse((W * 0.2, base - W * 0.06, W * 0.8, base + W * 0.06), fill=(255, 40, 90, int(200 * fade)))
        frames.append(_fx_merge(core, glow, max(1, W * 0.04)))
    return frames


def make_ice_frames(size, seed):
    """Băng tinh: mảnh băng sắc bắn ra, tuyết lấp lánh."""
    rnd = random.Random(seed + 6000)
    W = H = size
    c = (W / 2.0, H / 2.0)
    shards = [(rnd.uniform(0, 2 * math.pi), rnd.uniform(0.18, 0.3) * W, rnd.uniform(0.03, 0.05) * W)
              for _ in range(rnd.randint(6, 9))]
    frames = []
    for f in range(7):
        core, glow, dc, dg = _fx_new(W, H)
        fade = (1, 1, 1, 0.8, 0.6, 0.35, 0.15)[f]
        d0 = W * (0.05 + 0.06 * f)
        for a, L, w in shards:
            ca, sa = math.cos(a), math.sin(a)
            p0 = (c[0] + ca * d0, c[1] + sa * d0)
            p1 = (c[0] + ca * (d0 + L), c[1] + sa * (d0 + L))
            m = ((p0[0] + p1[0]) / 2 - sa * w, (p0[1] + p1[1]) / 2 + ca * w)
            n = ((p0[0] + p1[0]) / 2 + sa * w, (p0[1] + p1[1]) / 2 - ca * w)
            dg.polygon([p0, m, p1, n], fill=(80, 200, 255, int(180 * fade)))
            dc.polygon([p0, m, p1, n], fill=(200, 240, 255, int(235 * fade)), outline=(255, 255, 255, int(255 * fade)))
        if f < 3:
            r = W * 0.1
            dg.ellipse((c[0] - r * 2, c[1] - r * 2, c[0] + r * 2, c[1] + r * 2), fill=(120, 220, 255, 200))
        for _ in range(6):
            x, y = c[0] + rnd.uniform(-0.45, 0.45) * W, c[1] + rnd.uniform(-0.45, 0.45) * H
            q = W * 0.018
            dc.line([(x - q, y), (x + q, y)], fill=(255, 255, 255, int(255 * fade)))
            dc.line([(x, y - q), (x, y + q)], fill=(255, 255, 255, int(255 * fade)))
        frames.append(_fx_merge(core, glow, max(1, W * 0.025)))
    return frames


def _star(cx, cy, r, rot=0.0):
    pts = []
    for i in range(8):
        a = rot + i * math.pi / 4
        rr = r if i % 2 == 0 else r * 0.28
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    return pts


def make_star_frames(size, seed):
    """Tinh tú lấp lánh: sao bốn cánh nhấp nháy."""
    rnd = random.Random(seed + 7000)
    W = H = size
    stars = [(W / 2.0 + rnd.uniform(-0.38, 0.38) * W, H / 2.0 + rnd.uniform(-0.38, 0.38) * H, rnd.uniform(0.07, 0.13) * W,
              rnd.uniform(0, 3), rnd.choice(((255, 230, 120), (255, 180, 230), (180, 220, 255), (255, 255, 255))))
             for _ in range(rnd.randint(7, 10))]
    frames = []
    for f in range(8):
        core, glow, dc, dg = _fx_new(W, H)
        for x, y, r, ph, col in stars:
            k = 0.35 + 0.65 * abs(math.sin(ph + f * 0.9))      # luôn sáng, nhấp nháy so le
            al = k * (1 - f / 9.0) * min(1.0, (f + 1) / 2.0)
            rr = r * (0.5 + 0.5 * k)
            dg.ellipse((x - rr, y - rr, x + rr, y + rr), fill=col + (int(150 * al),))
            dc.polygon(_star(x, y, rr, math.pi / 4 * (f % 2)), fill=col + (int(255 * al),))
        frames.append(_fx_merge(core, glow, max(1, W * 0.03)))
    return frames


def make_shock_frames(size, seed):
    """Sóng xung kích: vòng sóng kép lan ra."""
    rnd = random.Random(seed + 8000)
    W = H = size
    c = (W / 2.0, H / 2.0)
    col = rnd.choice(((90, 220, 255), (200, 120, 255), (255, 120, 90)))
    frames = []
    for f in range(7):
        core, glow, dc, dg = _fx_new(W, H)
        fade = 1 - f / 7.0
        for k, lag in ((1.0, 0), (0.7, 1.5)):
            r = W * 0.48 * max(0.05, (f - lag) / 6.0)
            if r <= 2:
                continue
            dg.ellipse((c[0] - r, c[1] - r * 0.75, c[0] + r, c[1] + r * 0.75), outline=col + (int(255 * fade),),
                       width=max(3, int(W * 0.08 * k)))
            dc.ellipse((c[0] - r, c[1] - r * 0.75, c[0] + r, c[1] + r * 0.75), outline=col + (int(255 * fade),),
                       width=max(2, int(W * 0.03 * k)))
            dc.ellipse((c[0] - r, c[1] - r * 0.75, c[0] + r, c[1] + r * 0.75), outline=(255, 255, 255, int(255 * fade)),
                       width=max(1, int(W * 0.012)))
        if f < 2:
            q = W * 0.08
            dg.ellipse((c[0] - q * 2, c[1] - q * 1.5, c[0] + q * 2, c[1] + q * 1.5), fill=col + (230,))
        frames.append(_fx_merge(core, glow, max(1, W * 0.03)))
    return frames


def _hammer_img(L):
    """Búa chiến khắc rune (búa sấm chung, không theo thiết kế của hãng nào)."""
    from PIL import ImageDraw
    im = Image.new("RGBA", (int(L), int(L)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx = L / 2.0
    hw, hh = L * 0.44, L * 0.24
    d.rectangle((cx - L * 0.045, L * 0.24, cx + L * 0.045, L * 0.95), fill=(95, 60, 40, 255), outline=(40, 25, 15, 255))
    for i in range(6):                                        # quấn da tay cầm
        y = L * (0.45 + i * 0.07)
        d.line([(cx - L * 0.045, y), (cx + L * 0.045, y + L * 0.03)], fill=(60, 35, 20, 255), width=max(1, int(L * 0.012)))
    d.ellipse((cx - L * 0.06, L * 0.91, cx + L * 0.06, L * 0.99), fill=(150, 155, 165, 255), outline=(60, 60, 70, 255))
    d.rounded_rectangle((cx - hw / 2, L * 0.04, cx + hw / 2, L * 0.04 + hh), radius=L * 0.03,
                        fill=(165, 172, 185, 255), outline=(55, 58, 70, 255), width=max(1, int(L * 0.015)))
    d.rectangle((cx - hw / 2, L * 0.04 + hh * 0.42, cx + hw / 2, L * 0.04 + hh * 0.58), fill=(120, 126, 140, 255))
    for i in (-1, 1):                                         # rune phát sáng
        x = cx + i * hw * 0.22
        d.line([(x, L * 0.08), (x - L * 0.02, L * 0.14), (x + L * 0.02, L * 0.18), (x, L * 0.24)],
               fill=(120, 200, 255, 255), width=max(1, int(L * 0.012)))
    return im


def make_hammer_frames(size, seed):
    """Búa sấm lao tới đập vỡ chữ: búa bay vào, nện xuống, nứt toác, mảnh vỡ văng ra."""
    rnd = random.Random(seed + 9000)
    W, H = int(size * 1.5), int(size * 1.3)
    hit = (W / 2.0, H * 0.65)
    side = rnd.choice((-1, 1))
    hl = size * 0.55
    hammer = _hammer_img(hl).rotate(180)                     # đầu búa xuống dưới để nện vào chữ
    head_off = hl * 0.34                                       # tâm đầu búa cách tâm ảnh
    cracks = []
    for _ in range(rnd.randint(5, 7)):
        a = rnd.uniform(0, 2 * math.pi)
        cracks.append(_jagged(hit, (hit[0] + math.cos(a) * size * rnd.uniform(0.25, 0.45),
                                    hit[1] + math.sin(a) * size * rnd.uniform(0.15, 0.3)), 5, size * 0.03, rnd))
    debris = [(rnd.uniform(0, 2 * math.pi), rnd.uniform(4, 9), rnd.uniform(0.015, 0.035) * size) for _ in range(10)]
    frames = []
    # vị trí TÂM ĐẦU BÚA theo từng khung; góc âm/dương để cán nghiêng về phía búa bay tới
    hy = hit[1] - hl * 0.1
    path = [(hit[0] + side * W * 0.40, hy - H * 0.55, -side * 70), (hit[0] + side * W * 0.24, hy - H * 0.33, -side * 48),
            (hit[0] + side * W * 0.09, hy - H * 0.12, -side * 20), (hit[0], hy, -side * 4)]
    for f in range(10):
        core, glow, dc, dg = _fx_new(W, H)
        if f >= 3:                                            # va chạm
            k = f - 3
            fade = max(0, 1 - k / 6.5)
            if k <= 1:
                r = size * (0.18 + 0.1 * k)
                dg.ellipse((hit[0] - r * 1.5, hit[1] - r, hit[0] + r * 1.5, hit[1] + r), fill=(170, 210, 255, 230))
                dc.ellipse((hit[0] - r * 0.6, hit[1] - r * 0.4, hit[0] + r * 0.6, hit[1] + r * 0.4), fill=(255, 255, 255, 255))
            for cr in cracks:
                dc.line(cr, fill=(255, 255, 255, int(255 * fade)), width=max(1, int(size * 0.012)))
                dg.line(cr, fill=(120, 190, 255, int(200 * fade)), width=max(2, int(size * 0.035)))
            for a, sp, q in debris:
                x = hit[0] + math.cos(a) * sp * k * size / 60.0
                y = hit[1] + math.sin(a) * sp * k * size / 60.0 + 0.6 * k * k * size / 60.0
                dc.polygon([(x - q, y), (x, y - q), (x + q * 0.8, y + q * 0.6)], fill=(150, 160, 180, int(255 * fade)))
            if k <= 2:
                for _ in range(4):                            # tia sét nhỏ quanh búa
                    a = rnd.uniform(0, 2 * math.pi)
                    p1 = (hit[0] + math.cos(a) * size * 0.35, hit[1] + math.sin(a) * size * 0.25)
                    dc.line(_jagged(hit, p1, 4, size * 0.03, rnd), fill=(210, 230, 255, 255), width=1)
        if f <= 5:                                            # búa bay vào rồi nằm tại chỗ va chạm
            px, py, ang = path[min(f, 3)]
            if f > 3:
                py -= (f - 3) * size * 0.05                    # nảy nhẹ lên sau cú nện
            al = 1.0 if f <= 4 else 0.5
            hm = hammer.rotate(ang, resample=Image.BICUBIC, expand=True)
            if al < 1:
                hm.putalpha(hm.split()[3].point(lambda v: int(v * al)))
            if 0 < f <= 3:                                    # vệt bay
                qx, qy, _ = path[f - 1]
                dg.line([(qx, qy), (px, py)], fill=(150, 200, 255, 170), width=max(3, int(hl * 0.35)))
            th = math.radians(ang)
            ox, oy = head_off * math.sin(th), head_off * math.cos(th)
            x0 = int(px - hm.width / 2.0 - ox)
            y0 = int(py - hm.height / 2.0 - oy)
            if x0 + hm.width > 0 and y0 + hm.height > 0:
                tmp = Image.new("RGBA", core.size, (0, 0, 0, 0))
                tmp.paste(hm, (x0, y0), hm)
                core.alpha_composite(tmp)
        frames.append(_fx_merge(core, glow, max(1, size * 0.03)))
    return frames


def make_shatter_frames(size, seed):
    """Vỡ vụn: nứt rồi vỡ tung thành mảnh kính."""
    rnd = random.Random(seed + 10000)
    W = H = size
    c = (W / 2.0, H / 2.0)
    n = rnd.randint(7, 10)
    angs = sorted(rnd.uniform(0, 2 * math.pi) for _ in range(n))
    R = W * 0.22
    frames = []
    for f in range(8):
        core, glow, dc, dg = _fx_new(W, H)
        fade = 1 - max(0, f - 2) / 6.0
        for i in range(n):
            a0, a1 = angs[i], angs[(i + 1) % n] + (2 * math.pi if i == n - 1 else 0)
            am = (a0 + a1) / 2
            push = 0 if f < 2 else (f - 1) * W * 0.05
            dx, dy = math.cos(am) * push, math.sin(am) * push + (0 if f < 2 else (f - 1) ** 2 * W * 0.008)
            tri = [(c[0] + dx, c[1] + dy), (c[0] + math.cos(a0) * R + dx, c[1] + math.sin(a0) * R + dy),
                   (c[0] + math.cos(a1) * R + dx, c[1] + math.sin(a1) * R + dy)]
            if f >= 2:
                dc.polygon(tri, fill=(200, 215, 235, int(120 * fade)), outline=(255, 255, 255, int(255 * fade)))
            else:
                dc.line([tri[0], tri[1]], fill=(255, 255, 255, 255), width=max(1, int(W * 0.012)))
                dg.line([tri[0], tri[1]], fill=(150, 200, 255, 200), width=max(2, int(W * 0.03)))
        frames.append(_fx_merge(core, glow, max(1, W * 0.02)))
    return frames


def make_blackhole_frames(size, seed):
    """Hố đen nuốt chữ: xoáy tím cam, hạt sáng bị hút vào tâm."""
    rnd = random.Random(seed + 11000)
    W = H = size
    c = (W / 2.0, H / 2.0)
    parts = [(rnd.uniform(0, 2 * math.pi), rnd.uniform(0.25, 0.48) * W) for _ in range(14)]
    frames = []
    for f in range(9):
        core, glow, dc, dg = _fx_new(W, H)
        t = f / 8.0
        size_k = math.sin(t * math.pi)                       # nở ra rồi sụp lại
        R = W * 0.3 * size_k
        if R > 2:
            for k in range(3):
                rr = R * (1 - k * 0.22)
                st = (f * 50 + k * 70) % 360
                dg.arc((c[0] - rr, c[1] - rr * 0.55, c[0] + rr, c[1] + rr * 0.55), st, st + 250,
                       fill=(255, 130, 40, 220) if k == 0 else (170, 70, 255, 220), width=max(2, int(W * 0.05)))
                dc.arc((c[0] - rr, c[1] - rr * 0.55, c[0] + rr, c[1] + rr * 0.55), st, st + 200,
                       fill=(255, 220, 160, 230) if k == 0 else (220, 180, 255, 230), width=max(1, int(W * 0.012)))
            hr = R * 0.38
            dc.ellipse((c[0] - hr, c[1] - hr, c[0] + hr, c[1] + hr), fill=(5, 0, 10, 255), outline=(255, 160, 80, 255))
        for a, d in parts:
            aa = a + t * 4
            dd = d * (1 - t)
            x, y = c[0] + math.cos(aa) * dd, c[1] + math.sin(aa) * dd * 0.6
            q = max(1, W * 0.012)
            dc.ellipse((x - q, y - q, x + q, y + q), fill=(255, 230, 200, int(255 * (1 - t * 0.7))))
        frames.append(_fx_merge(core, glow, max(1, W * 0.03)))
    return frames


def make_explode_frames(size, seed):
    """Nổ tung: cầu lửa, khói, tia lửa."""
    rnd = random.Random(seed + 12000)
    W = H = size
    c = (W / 2.0, H / 2.0)
    puffs = [(rnd.uniform(0, 2 * math.pi), rnd.uniform(0.05, 0.22) * W, rnd.uniform(0.09, 0.16) * W) for _ in range(7)]
    sparks = [(rnd.uniform(0, 2 * math.pi), rnd.uniform(0.3, 0.5) * W) for _ in range(10)]
    frames = []
    for f in range(8):
        core, glow, dc, dg = _fx_new(W, H)
        t = f / 7.0
        fade = 1 - max(0, t - 0.3) / 0.7
        for a, d, r in puffs:
            dd = d * (0.4 + t)
            x, y = c[0] + math.cos(a) * dd, c[1] + math.sin(a) * dd - t * W * 0.08
            rr = r * (0.6 + t * 0.8)
            colr = (255, int(200 - 150 * t), int(60 - 50 * t)) if t < 0.5 else (90, 80, 85)
            dg.ellipse((x - rr * 1.2, y - rr * 1.2, x + rr * 1.2, y + rr * 1.2), fill=(255, 120, 30, int(180 * fade)))
            dc.ellipse((x - rr, y - rr, x + rr, y + rr), fill=colr + (int(235 * fade),))
        if f < 3:
            r = W * (0.1 + f * 0.05)
            dc.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), fill=(255, 255, 220, 255))
        for a, L in sparks:
            d0, d1 = L * t * 0.7, L * min(1, t + 0.15)
            dc.line([(c[0] + math.cos(a) * d0, c[1] + math.sin(a) * d0), (c[0] + math.cos(a) * d1, c[1] + math.sin(a) * d1)],
                    fill=(255, 230, 140, int(255 * fade)), width=max(1, int(W * 0.012)))
        frames.append(_fx_merge(core, glow, max(1, W * 0.035)))
    return frames


# (khoá, tên hiển thị, hàm tạo, điểm neo trong khung: tỉ lệ x, y)
FX_EFFECTS = [
    ("bolt", "Lôi điện tỏa", make_bolt_frames, (0.5, 0.5)),
    ("thunder", "Lôi đình giáng xuống", make_thunder_frames, (0.5, 0.9)),
    ("holy", "Thần quang vàng", make_holy_frames, (0.5, 0.5)),
    ("skull", "Đầu lâu ma quái bay lên", make_skull_frames, (0.5, 0.85)),
    ("darkflame", "Hắc diễm bùng cháy", make_darkflame_frames, (0.5, 0.85)),
    ("ice", "Băng tinh nổ", make_ice_frames, (0.5, 0.5)),
    ("star", "Tinh tú lấp lánh", make_star_frames, (0.5, 0.5)),
    ("shock", "Sóng xung kích", make_shock_frames, (0.5, 0.5)),
    ("slash", "Loạn đao chém", make_slash_frames, (0.5, 0.5)),
    ("hammer", "Búa sấm đập vỡ chữ", make_hammer_frames, (0.5, 0.65)),
    ("shatter", "Vỡ vụn", make_shatter_frames, (0.5, 0.5)),
    ("blackhole", "Hố đen nuốt chữ", make_blackhole_frames, (0.5, 0.5)),
    ("explode", "Nổ tung", make_explode_frames, (0.5, 0.5)),
]
FX_BY_KEY = {e[0]: e for e in FX_EFFECTS}
FX_CHOICES = [("random", "★ Ngẫu nhiên (đổi mỗi lần)")] + [(e[0], e[1]) for e in FX_EFFECTS]


class FxPlayer:
    """Cửa sổ hiệu ứng trong suốt, chuột bấm xuyên qua, không bao giờ lấy focus của ô đang gõ."""
    VARIANTS = 5

    def __init__(self, app, default_key):
        self.app = app
        self.default_key = default_key
        self.cache = {}                          # (mẫu, cỡ) -> danh sách biến thể
        self.seq, self.i, self.pos, self.job = [], 0, (0, 0), None
        self.last_key = None
        self.played = 0
        self.lw = None
        if IS_WIN:
            try:
                self.win = tk.Toplevel(app.root)
                self.win.overrideredirect(True)
                self.win.attributes("-topmost", True)
                self.win.geometry("1x1+-50+-50")
                # WS_EX_TRANSPARENT (bấm xuyên) | WS_EX_NOACTIVATE (không giành focus)
                self.lw = LayeredWin(self.win, extra_ex=0x20 | 0x08000000)
                self.lw.update(-50, -50, 1, 1, b"\0\0\0\0")
            except Exception:
                log_error()
                self.lw = None

    def variants(self, key, size):
        k = (key, size)
        if k not in self.cache:
            maker = FX_BY_KEY[key][2]
            vs = []
            for seed in range(self.VARIANTS):
                vs.append([(im.convert("RGBa").tobytes("raw", "BGRa"), im.width, im.height) for im in maker(size, seed)])
            self.cache[k] = vs
            while len(self.cache) > 8:
                self.cache.pop(next(iter(self.cache)))
        return self.cache[k]

    def play(self, x, y, size, key=None):
        key = key or self.default_key
        if key == "random" or key not in FX_BY_KEY:
            key = random.choice([e[0] for e in FX_EFFECTS])
        self.last_key = key
        self.seq = random.choice(self.variants(key, size))
        self.anchor = FX_BY_KEY[key][3]
        self.i = 0
        self.pos = (int(x), int(y))
        self.played += 1
        if self.job is None:
            self._step()

    def _step(self):
        if self.i >= len(self.seq):
            self.job = None
            if self.lw:
                self.lw.update(-50, -50, 1, 1, b"\0\0\0\0")
            return
        data, w, h = self.seq[self.i]
        if self.lw:
            try:
                ax, ay = self.anchor
                self.lw.update(self.pos[0] - int(w * ax), self.pos[1] - int(h * ay), w, h, data)
            except Exception:
                log_error()
        self.i += 1
        self.job = self.app.root.after(40, self._step)


class KeyFx:
    def __init__(self, app):
        self.app = app
        self.bolt = FxPlayer(app, "bolt")         # kênh hiệu ứng khi gõ
        self.slash = FxPlayer(app, "slash")       # kênh hiệu ứng khi xoá
        self.t_last = {"T": 0.0, "D": 0.0}
        self.hist = {"T": [], "D": []}
        self.cool = {"T": 0.0, "D": 0.0}
        self.last_pos = None

    def size(self):
        return int(150 * float(self.app.store.s.get("key_fx_size", 1.0)) * self.app.dpi)

    def on_key(self, kind):
        s = self.app.store.s
        if not s.get("key_fx", True) or self.app.fs_hidden:
            return
        t = time_now()
        pos, pw = caret_info()
        if pw:
            return                                   # ô mật khẩu: không hiệu ứng
        if pos is None:
            px, py = self.app.root.winfo_pointerxy()
            pos = (px + 14, py + 18)                 # phần mềm không báo vị trí con trỏ nhập -> cạnh chuột
        self.last_pos = pos
        if t - self.t_last[kind] >= (0.07 if kind == "T" else 0.09):     # gõ nhanh / giữ phím: gộp bớt
            self.t_last[kind] = t
            if kind == "T":
                self.bolt.play(pos[0], pos[1], self.size(), s.get("key_fx_type", "bolt"))
            else:
                self.slash.play(pos[0], pos[1], self.size(), s.get("key_fx_del", "slash"))
        if not s.get("key_fx_pet", True) or self.app.hidden:
            return
        h = self.hist[kind]
        h.append(t)
        span, need = (8.0, 25) if kind == "T" else (3.0, 8)
        while h and t - h[0] > span:
            h.pop(0)
        if len(h) >= need and t > self.cool[kind]:
            self.cool[kind] = t + (30 if kind == "T" else 20)
            h.clear()
            key = "E_TYPING" if kind == "T" else "E_DELETING"
            act = ((s.get("triggers") or {}).get(key) or {}).get("act")
            if act:
                eng = self.app.pet.engine
                if kind == "D":
                    eng.fly_and_act(pos[0], pos[1] + 40, act)
                else:
                    eng.force(act)


# ───────────────────────── Nhân vật trên màn hình ─────────────────────────
class Pet:
    def __init__(self, app):
        self.app = app
        self.root = app.root
        self.t = 0.0
        self.alert = False
        self.hover = False
        self.happy_until = 0
        self.x = self.y = 0
        self.W = self.H = 10
        self.top_off = 0
        self.acc = 0.0
        self.sleeping = False
        self.cache = {}
        self.layered = None
        self.pack = None
        self.engine = None
        self.env = Env(app)
        self.cv = tk.Canvas(self.root, bg=KEY, highlightthickness=0, bd=0, cursor="hand2", width=10, height=10)
        self.cv.pack()
        self.mode = "key"
        if IS_WIN and app.store.s.get("smooth", True):
            try:
                self.layered = LayeredWin(self.root)
                self.mode = "layered"
            except Exception:
                log_error()
                self.layered = None
        if self.mode == "key" and IS_WIN:
            try:
                self.root.attributes("-transparentcolor", KEY)
            except Exception:
                pass
        self.apply_look(reset_size=True)
        self.mouse = Mouse(self)

    # ── tải nhân vật / kích thước ──
    def pack_path(self):
        p = pack_resolve(self.app.store.s.get("pack") or "")
        return p if p and os.path.isdir(p) else BUILTIN_PACK

    def apply_look(self, reset_size=False):
        s = self.app.store.s
        self.s_user = max(0.4, min(3.0, float(s.get("scale", 1.0))))
        old_screen = None
        if self.engine is not None:
            old_screen = (self.engine.ax * self.env.zoom, self.engine.ay * self.env.zoom)
        path = self.pack_path()
        if self.pack is None or getattr(self, "_pack_dir", None) != path:
            try:
                pk = ShimejiPack(path)
            except Exception:
                log_error()
                pk = ShimejiPack(BUILTIN_PACK)
                path = BUILTIN_PACK
            self.pack = pk
            self._pack_dir = path
            self.engine = None
        self.zoom = self.s_user * self.app.dpi
        self.env.zoom = self.zoom
        self.cache = {}
        self.env.refresh(force=True)
        if self.engine is None:
            self.engine = Engine(self, self.pack)
            pos = s.get("pos")
            if old_screen:
                pos = old_screen
            a = self.app.areas[0]
            if not pos:
                pos = (a[2] - 260, a[1] + 40)
            self.engine.ax, self.engine.ay = pos[0] / self.zoom, pos[1] / self.zoom
            self.engine.clamp()
        elif old_screen:
            self.engine.ax, self.engine.ay = old_screen[0] / self.zoom, old_screen[1] / self.zoom
            self.engine.clamp()
            self.engine.gen = None
            self.engine.forced = "Fall"

    def assigned(self):
        """Chiêu gán cho thao tác chuột trên nhân vật (những chiêu này mặc định không tự làm)."""
        tr = self.app.store.s.get("triggers") or {}
        keys = {k for k, _ in TRIGGERS}
        return {v.get("act") for k, v in tr.items() if k in keys and v.get("act")}

    # ── thao tác & sự kiện ──
    def trigger(self, key, e=None):
        m = (self.app.store.s.get("triggers") or {}).get(key) or {}
        act, cmd = m.get("act"), m.get("cmd")
        if act:
            self.engine.force(act)
        if cmd:
            self.app.run_cmd(cmd, e)

    def event(self, key):
        self.trigger(key)

    def happy(self, secs=1.5):
        self.happy_until = self.t + secs

    def on_bubble(self, msg):
        k = msg.get("kind")
        self.alert = k in ("reminder", "break")
        self.engine.calm = self.alert
        if k == "reminder":
            self.event("E_REMIND")
        elif k == "break":
            self.event("E_BREAK")
        elif k == "greet":
            self.event("E_GREET")

    def on_bubble_closed(self, msg):
        self.alert = False
        self.engine.calm = False

    def head_top(self):
        return self.y + self.top_off

    def move_to(self, x, y):
        """Gọi sau khi đổi độ phân giải / rút màn hình phụ: kéo nhân vật về vùng còn thấy được."""
        if self.engine is not None:
            self.env.refresh(force=True)
            self.engine.clamp()

    def clamp_to_screen(self, x, y, w, h, sx, sy):
        """Giữ trọn khung hình nhân vật trong màn hình đang đứng, không lấn ra ngoài mép."""
        mons = getattr(self.app, "monitors", None) or [self.app.bounds]
        m = None
        for r in mons:
            if r[0] <= sx < r[2] and r[1] <= sy <= r[3]:
                m = r
                break
        if m is None:
            m = min(mons, key=lambda r: abs(sx - (r[0] + r[2]) / 2.0) + abs(sy - (r[1] + r[3]) / 2.0))
        if w <= m[2] - m[0]:
            x = max(m[0], min(m[2] - w, x))
        if h <= m[3] - m[1]:
            y = max(m[1], min(m[3] - h, y))
        return x, y

    def anchor_screen(self):
        return [int(self.engine.ax * self.zoom), int(self.engine.ay * self.zoom)]

    def frame_delay(self):
        return TICK_MS

    # ── vòng lặp ──
    def tick(self, dtt):
        self.t += dtt
        self.acc += dtt * 1000
        sleepy = self.app.is_sleepy() and not self.alert
        eng = self.engine
        if sleepy != self.sleeping:
            self.sleeping = sleepy
            sb = ((self.app.store.s.get("triggers") or {}).get("E_SLEEP") or {}).get("act")
            eng.sleep_beh = sb if sleepy else None
            if sleepy:
                eng.calm = False
            else:
                self.event("E_WAKE")
        self.env.refresh()
        n = 0
        while self.acc >= TICK_MS and n < 4:
            self.acc -= TICK_MS
            eng.tick()
            n += 1
        if self.acc > TICK_MS * 4:
            self.acc = 0
        if n:
            self.render()

    def frame(self, fn, alert, mirror=False):
        key = (fn, alert, mirror)
        f = self.cache.pop(key, None)
        if f:
            self.cache[key] = f                  # đưa lên cuối = mới dùng
            return f
        base = self.pack.image(fn)
        if mirror:
            base = ImageOps.mirror(base)
        z = self.zoom
        w, h = max(1, int(round(base.width * z))), max(1, int(round(base.height * z)))
        rs = Image.NEAREST if (z >= 2 and abs(z - round(z)) < 0.01) else Image.LANCZOS
        im = base.resize((w, h), rs) if (w, h) != base.size else base.copy()
        off = 0
        if alert:
            from PIL import ImageDraw
            off = int(34 * z)
            big = Image.new("RGBA", (w, h + off), (0, 0, 0, 0))
            big.paste(im, (0, off))
            bb = im.getbbox() or (0, 0, w, h)
            cx = min(w - int(6 * z), bb[2] - int(4 * z))
            top = bb[1] + off - int(30 * z)
            d = ImageDraw.Draw(big)
            bw = max(3, int(6 * z))
            d.rounded_rectangle((cx - bw, top, cx + bw, top + int(18 * z)), radius=bw, fill=(255, 60, 60, 255),
                                outline=(255, 255, 255, 255), width=max(1, int(z)))
            d.ellipse((cx - bw, top + int(21 * z), cx + bw, top + int(21 * z) + 2 * bw), fill=(255, 60, 60, 255),
                      outline=(255, 255, 255, 255), width=max(1, int(z)))
            im = big
            h += off
        bb = im.split()[3].getbbox()
        top = bb[1] if bb else 0
        if self.mode == "layered":
            data = im.convert("RGBa").tobytes("raw", "BGRa")
        else:
            a = im.split()[3].point(lambda v: 255 if v >= 100 else 0)
            bg = Image.new("RGB", im.size, (255, 0, 255))
            solid = Image.new("RGBA", im.size, (40, 30, 45, 255))
            solid.alpha_composite(im)
            bg.paste(solid.convert("RGB"), (0, 0), a)
            data = ImageTk.PhotoImage(bg)
        f = (data, w, h, off, top, base.width)
        self.cache[key] = f
        while len(self.cache) > 360:             # bỏ khung cũ nhất thay vì xoá sạch (đỡ giật)
            self.cache.pop(next(iter(self.cache)))
        return f

    def render(self):
        eng = self.engine
        p = eng.pose
        if p is None:
            return
        right = eng.look_right
        fn = (p.imgr or p.img) if right else p.img
        blink = self.alert and int(self.t * 2.5) % 2 == 0
        mirror = right and not p.imgr
        data, w, h, off, top, base_w = self.frame(fn, blink, mirror)
        ax = (base_w - p.ax) if right else p.ax
        z = self.zoom
        x = int(round(eng.ax * z - ax * z))
        y = int(round(eng.ay * z - p.ay * z - off))
        x, y = self.clamp_to_screen(x, y, w, h, eng.ax * z, eng.ay * z)
        size_changed = (w, h) != (self.W, self.H)
        if self.mode == "layered":
            if size_changed or (x, y) != (self.x, self.y):
                self.root.geometry("%dx%d+%d+%d" % (w, h, x, y))
            if not self.layered.update(x, y, w, h, data):
                log_error()
                self.mode = "key"           # dự phòng: chuyển sang chế độ màu khoá
                self.cache = {}
                try:
                    self.root.attributes("-transparentcolor", KEY)
                except Exception:
                    pass
        else:
            if size_changed:
                self.cv.config(width=w, height=h)
                self.root.geometry("%dx%d+%d+%d" % (w, h, x, y))
            elif (x, y) != (self.x, self.y):
                self.root.geometry("+%d+%d" % (x, y))
            self.cv.delete("pet")
            self.cv.create_image(0, 0, image=data, anchor="nw", tags="pet")
        self.x, self.y, self.W, self.H, self.top_off = x, y, w, h, top
        self.app.bubble.reposition()


# ───────────────────────── Bộ não tự học ─────────────────────────
class Learner:
    def __init__(self, app):
        self.app = app
        self.suggestions = []

    def ignored(self, key):
        d = self.app.store.data["ignored"].get(key)
        if not d:
            return False
        try:
            return (dt.date.today() - dt.date.fromisoformat(d)).days < 30
        except Exception:
            return False

    def analyze(self):
        st = self.app.store
        log = st.data["log"]
        today = dt.date.today()
        out = []
        recurring_norms = {norm(t["title"]) for t in st.tasks if t.get("enabled") and t.get("repeat") != "once"}

        # A) Việc bạn tự ghi nhận / việc một lần lặp đi lặp lại -> đề xuất tạo nhắc
        cut = (today - dt.timedelta(days=30)).isoformat()
        groups = {}
        for e in log:
            if e.get("date", "") < cut or e["kind"] not in ("note", "done"):
                continue
            if e["kind"] == "done":
                tk_ = st.task(e.get("task")) if e.get("task") else None
                if tk_ and tk_.get("repeat") != "once":
                    continue
            n = norm(e.get("title"))
            if not n:
                continue
            tm = parse_iso(e["t"])
            g = groups.setdefault(n, {"title": e.get("title"), "days": {}})
            g["title"] = e.get("title")
            m = tm.hour * 60 + tm.minute
            if e["date"] not in g["days"] or m < g["days"][e["date"]]:
                g["days"][e["date"]] = m
        for n, g in groups.items():
            if n in recurring_norms or len(g["days"]) < 3:
                continue
            mins = list(g["days"].values())
            med = statistics.median(mins)
            keep = [(d, m) for d, m in g["days"].items() if abs(m - med) <= 60]
            if len(keep) < 3:
                continue
            ms = [m for _, m in keep]
            if statistics.pstdev(ms) > 35:
                continue
            wds = sorted({dt.date.fromisoformat(d).weekday() for d, _ in keep})
            if len(wds) >= 4:
                rep, days = ("weekdays", []) if max(wds) < 5 else ("daily", [])
            else:
                rep, days = "weekly", wds
            tme = m2hm(round5(statistics.median(ms)))
            key = "new:%s" % n
            if self.ignored(key):
                continue
            dd = REPEAT_TEXT[rep] if rep != "weekly" else ", ".join(WD[d] for d in days)
            out.append({"key": key, "kind": "new_task",
                        "text": "Tạo nhắc \"%s\" lúc %s (%s)" % (g["title"], tme, dd),
                        "reason": "Bạn đã làm việc này %d ngày, thường quanh %s" % (len(keep), tme),
                        "payload": {"title": g["title"], "time": tme, "repeat": rep, "days": days}})

        # B) dời giờ nhắc theo giờ bạn thật sự làm, C) bỏ ngày hay bỏ qua / tắt việc
        cut21 = (today - dt.timedelta(days=21)).isoformat()
        by_task = {}
        for e in log:                       # gom nhật ký theo việc 1 lần (thay vì quét lại cho từng việc)
            if e.get("task") and e.get("date", "") >= cut21:
                by_task.setdefault(e["task"], []).append(e)
        for t in st.tasks:
            if not t.get("enabled") or t.get("repeat") in ("once", "interval"):
                continue
            ev = by_task.get(t["id"], [])
            delays = []
            for e in ev:
                if e["kind"] == "done" and e.get("sched") == t["time"]:
                    tm = parse_iso(e["t"])
                    dly = tm.hour * 60 + tm.minute - hm2m(e["sched"])
                    if -180 <= dly <= 240:
                        delays.append(dly)
            if len(delays) >= 4:
                med = statistics.median(delays)
                if abs(med) >= 15:
                    newt = m2hm(round5(hm2m(t["time"]) + med))
                    key = "shift:%s:%s" % (t["id"], newt)
                    if not self.ignored(key):
                        out.append({"key": key, "kind": "shift_time",
                                    "text": "Dời giờ nhắc \"%s\": %s → %s" % (t["title"], t["time"], newt),
                                    "reason": "Bạn thường làm %s %d phút so với giờ nhắc" % ("trễ" if med > 0 else "sớm", abs(int(med))),
                                    "payload": {"id": t["id"], "time": newt}})
            outcomes = [e for e in ev if e["kind"] in ("done", "skip")]
            last5 = outcomes[-5:]
            if len(last5) >= 4 and sum(1 for e in last5 if e["kind"] == "skip") >= 4:
                key = "off:%s" % t["id"]
                if not self.ignored(key):
                    out.append({"key": key, "kind": "disable", "text": "Tạm tắt nhắc \"%s\"" % t["title"],
                                "reason": "Bạn đã bỏ qua %d/%d lần gần nhất" % (sum(1 for e in last5 if e["kind"] == "skip"), len(last5)),
                                "payload": {"id": t["id"]}})
                continue
            by_wd = {}
            for e in outcomes:
                wd = dt.date.fromisoformat(e["date"]).weekday()
                by_wd.setdefault(wd, []).append(e["kind"])
            for wd, ks in by_wd.items():
                if ks.count("skip") >= 3 and "done" not in ks:
                    cur = [d for d in range(7) if occurs_on(t, today + dt.timedelta(days=(d - today.weekday())))]
                    if wd in cur and len(cur) > 1:
                        newdays = [d for d in cur if d != wd]
                        key = "dropday:%s:%d" % (t["id"], wd)
                        if not self.ignored(key):
                            out.append({"key": key, "kind": "drop_day",
                                        "text": "Bỏ %s khỏi lịch nhắc \"%s\"" % (WD[wd], t["title"]),
                                        "reason": "Bạn luôn bỏ qua việc này vào %s (%d lần)" % (WD[wd], ks.count("skip")),
                                        "payload": {"id": t["id"], "days": newdays}})

        # D) thói quen mở ứng dụng giữa ngày
        usage = st.data["app_usage"]
        days = sorted(d for d in usage if d >= (today - dt.timedelta(days=14)).isoformat())
        if len(days) >= 4:
            per = {}
            for d in days:
                ds = hm2m(st.data["day_start"].get(d, "00:00"))
                for exe, v in usage[d].items():
                    fm = hm2m(v.get("first", "00:00"))
                    if fm - ds >= 20 and v.get("minutes", 0) >= 3:
                        per.setdefault(exe, []).append(fm)
            for exe, ms in per.items():
                if len(ms) < 4 or len(ms) / len(days) < 0.6:
                    continue
                med = statistics.median(ms)
                keep = [m for m in ms if abs(m - med) <= 45]
                if len(keep) < 4 or statistics.pstdev(keep) > 25:
                    continue
                name = app_name(exe)
                title = "Mở %s" % name
                if norm(title) in recurring_norms:
                    continue
                key = "app:%s" % exe
                if self.ignored(key):
                    continue
                tme = m2hm(round5(statistics.median(keep)))
                out.append({"key": key, "kind": "new_task", "text": "Tạo nhắc \"%s\" lúc %s (T2–T6)" % (title, tme),
                            "reason": "%d/%d ngày gần đây bạn mở %s quanh %s" % (len(keep), len(days), name, tme),
                            "payload": {"title": title, "time": tme, "repeat": "weekdays", "days": []}})
        self.suggestions = out
        return out

    def apply(self, sg):
        st = self.app.store
        p = sg["payload"]
        k = sg["kind"]
        if k == "new_task":
            t = new_task(p["title"], p["time"], p["repeat"], days=p.get("days") or [], source="learned")
            st.tasks.append(t)
        elif k == "shift_time":
            t = st.task(p["id"])
            if t:
                t["time"] = p["time"]
        elif k == "disable":
            t = st.task(p["id"])
            if t:
                t["enabled"] = False
        elif k == "drop_day":
            t = st.task(p["id"])
            if t:
                t["repeat"] = "weekly"
                t["days"] = p["days"]
        st.data["ignored"][sg["key"]] = "2000-01-01"
        st.save()
        self.suggestions = [s for s in self.suggestions if s["key"] != sg["key"]]
        self.app.refresh_ui()

    def ignore(self, sg):
        self.app.store.data["ignored"][sg["key"]] = dt.date.today().isoformat()
        self.app.store.save()
        self.suggestions = [s for s in self.suggestions if s["key"] != sg["key"]]
        self.app.refresh_ui()


PHRASES = [
    "Nhớ uống nước nhé!", "Ngồi thẳng lưng lên nào ~", "Bạn đang làm rất tốt đó!",
    "Thả lỏng vai một chút đi.", "Nhìn ra xa 20 giây cho mắt nghỉ nhé.", "Mình vẫn đang canh giờ cho bạn đây!",
    "Có việc gì cần nhớ thì bấm chuột phải vào mình nha.", "Hít thở sâu 3 lần nào.",
    "Nhấp đúp vào mình để mở bảng quản lý.", "Giữ Ctrl + lăn chuột trên mình để đổi kích thước!",
    "Làm xong việc nhớ bấm 'Xong' để mình học thói quen của bạn nhé.",
]


# ───────────────────────── Ứng dụng ─────────────────────────
class App:
    def __init__(self):
        self.store = Store(DATA_FILE)
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.config(bg=KEY)
        try:
            self.dpi = max(1.0, self.root.winfo_fpixels("1i") / 96.0) if IS_WIN else 1.0
        except Exception:
            self.dpi = 1.0
        self.refresh_areas()
        self.hidden = False
        self.fs_hidden = False
        self.save_job = None
        self.ticks = 0
        self.muted_until = None
        self.pending = {}         # task_id -> sched
        self.active_secs = 0
        self.idle = 0.0
        self.was_idle_long = False
        self.break_pending = False
        self.next_chat = now() + dt.timedelta(minutes=random.uniform(8, 20))
        self.manager = None
        self.style()
        self.bubble = Bubble(self)
        self.pet = Pet(self)
        self.learner = Learner(self)
        self.gmouse = GlobalMouse(self)
        self.gmouse.start()
        self.keyfx = KeyFx(self)
        self.updater = Updater(self)
        self.root.bind_all("<F5>", lambda e: self.updater.check(manual=True, install=True))
        self._last = now().timestamp()
        self.root.after(50, self.anim_loop)
        self.root.after(2500, self.schedule_loop)
        self.root.after(5000, self.track_loop)
        self.root.after(4000, self.topmost_loop)
        self.root.after(8000, self.learn_loop)
        self.root.after(1500, self.greet_if_new_day)
        self.root.after(3000, self.fullscreen_loop)
        self.root.after(3500, self.restore_pending)
        self.root.after(20000, self.update_loop)
        self.root.after(2500, self.after_update_hello)
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.start_server()
        if self.store.s.get("autostart") and IS_WIN:
            set_autostart(True)

    # ── chung ──
    def style(self):
        st = ttk.Style(self.root)
        try:
            st.theme_use("clam")
        except Exception:
            pass
        f10 = (FONT, 10)
        st.configure(".", background=C_BG, foreground=C_FG, fieldbackground=C_PANEL2, bordercolor=C_LINE,
                     lightcolor=C_PANEL2, darkcolor=C_BG, troughcolor=C_PANEL, selectbackground=C_ACC2,
                     selectforeground="#ffffff", insertcolor=C_FG, font=f10, arrowcolor=C_GOLD)
        st.configure("TFrame", background=C_BG)
        st.configure("Card.TFrame", background=C_PANEL)
        st.configure("TLabel", background=C_BG, foreground=C_FG, font=f10)
        st.configure("Muted.TLabel", background=C_BG, foreground=C_MUTED, font=(FONT, 9))
        st.configure("H.TLabel", background=C_BG, foreground=C_GOLD, font=(FONT, 12, "bold"))
        st.configure("TButton", background=C_PANEL2, foreground=C_FG, bordercolor=C_ACC2, focusthickness=0,
                     padding=(10, 5), font=(FONT, 10, "bold"))
        st.map("TButton", background=[("pressed", "#5a1020"), ("active", C_ACC)], foreground=[("active", "#ffffff")],
               bordercolor=[("active", C_GOLD)])
        st.configure("Accent.TButton", background=C_ACC, foreground="#ffffff", bordercolor=C_GOLD)
        st.map("Accent.TButton", background=[("active", "#ff3d57")])
        for w in ("TCheckbutton", "TRadiobutton"):
            st.configure(w, background=C_BG, foreground=C_FG, indicatorbackground=C_PANEL2, indicatorforeground=C_GOLD,
                         font=f10)
            st.map(w, background=[("active", C_BG)], foreground=[("active", C_GOLD)],
                   indicatorbackground=[("selected", C_ACC), ("active", C_PANEL2)])
        for w in ("TEntry", "TSpinbox", "TCombobox"):
            st.configure(w, fieldbackground=C_PANEL2, foreground=C_FG, background=C_PANEL2, bordercolor=C_LINE,
                         arrowcolor=C_GOLD, insertcolor=C_FG)
            st.map(w, fieldbackground=[("readonly", C_PANEL2)], foreground=[("readonly", C_FG)],
                   bordercolor=[("focus", C_ACC)])
        st.configure("TNotebook", background=C_BG, bordercolor=C_LINE, tabmargins=(4, 6, 4, 0))
        st.configure("TNotebook.Tab", background=C_PANEL, foreground=C_MUTED, bordercolor=C_LINE,
                     font=(FONT, 10, "bold"), padding=(14, 6))
        st.map("TNotebook.Tab", background=[("selected", C_PANEL2), ("active", "#24183a")],
               foreground=[("selected", C_GOLD), ("active", C_FG)], expand=[("selected", (2, 2, 2, 0))])
        st.configure("Treeview", background=C_PANEL, fieldbackground=C_PANEL, foreground=C_FG,
                     rowheight=int(24 * self.dpi), font=f10, bordercolor=C_LINE)
        st.map("Treeview", background=[("selected", C_ACC2)], foreground=[("selected", "#ffffff")])
        st.configure("Treeview.Heading", background=C_PANEL2, foreground=C_GOLD, font=(FONT, 10, "bold"),
                     bordercolor=C_LINE, relief="flat")
        st.map("Treeview.Heading", background=[("active", "#2a1f42")])
        for sbn in ("TScrollbar", "Vertical.TScrollbar", "Horizontal.TScrollbar"):
            st.configure(sbn, background=C_PANEL2, troughcolor=C_BG, bordercolor=C_BG, arrowcolor=C_MUTED,
                         lightcolor=C_PANEL2, darkcolor=C_PANEL2, gripcount=0)
            st.map(sbn, background=[("active", C_ACC2)])
        st.configure("Small.TButton", padding=(4, 1), font=(FONT, 9, "bold"))
        st.configure("Horizontal.TScale", background=C_ACC, troughcolor=C_PANEL2, bordercolor=C_LINE)
        st.configure("TSeparator", background=C_LINE)
        r = self.root
        r.option_add("*TCombobox*Listbox.background", C_PANEL2)
        r.option_add("*TCombobox*Listbox.foreground", C_FG)
        r.option_add("*TCombobox*Listbox.selectBackground", C_ACC2)
        r.option_add("*TCombobox*Listbox.font", f10)
        r.option_add("*Menu.background", C_PANEL)
        r.option_add("*Menu.foreground", C_FG)
        r.option_add("*Menu.activeBackground", C_ACC)
        r.option_add("*Menu.activeForeground", "#ffffff")
        r.option_add("*Menu.selectColor", C_GOLD)
        r.option_add("*Menu.relief", "flat")
        r.option_add("*Toplevel.background", C_BG)

    def refresh_areas(self):
        areas = get_work_areas()
        if not areas:
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            areas = [(0, 0, sw, sh - (40 if IS_WIN else 0))]
        self.areas = areas
        self.monitors = list(MONITORS) if len(MONITORS) == len(areas) else \
            [(0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())] if len(areas) == 1 else list(areas)
        self.bounds = (min(a[0] for a in areas), min(a[1] for a in areas),
                       max(a[2] for a in areas), max(a[3] for a in areas))

    def in_quiet(self):
        s = self.store.s
        n = now().hour * 60 + now().minute
        a, b = hm2m(s.get("quiet_start", "22:00")), hm2m(s.get("quiet_end", "06:00"))
        if a == b:
            return False
        return a <= n < b if a < b else (n >= a or n < b)

    def is_sleepy(self):
        return self.idle >= 600 or (self.in_quiet() and self.idle >= 60)

    def is_muted(self):
        """Đang im lặng hoặc đang trình chiếu/toàn màn hình -> dời nhắc lại."""
        return (self.muted_until is not None and now() < self.muted_until) or self.fs_hidden

    def update_loop(self):
        """Tự kiểm tra bản mới khi mở app và mỗi 6 giờ."""
        try:
            if self.store.s.get("update_mode", "notify") != "off":
                last = parse_iso(self.store.s.get("last_update_check") or "")
                if not last or (now() - last).total_seconds() > 6 * 3600:
                    self.updater.check()
        except Exception:
            log_error()
        self.root.after(30 * 60 * 1000, self.update_loop)

    def after_update_hello(self):
        v = self.store.s.get("just_updated")
        if v:
            self.store.s["just_updated"] = ""
            self.save_soon()
            self.say("Đã lên v%s! ⚔" % APP_VER, "Cập nhật thành công. Xem có gì mới ở Bảng quản lý → Cài đặt.", timeout=10)
            self.pet.event("E_GREET")

    def save_soon(self, ms=1500):
        """Gộp nhiều lần ghi (kéo thanh trượt, gõ tên...) thành 1 lần ghi đĩa."""
        if self.save_job:
            try:
                self.root.after_cancel(self.save_job)
            except Exception:
                pass
        self.save_job = self.root.after(ms, self._do_save)

    def _do_save(self):
        self.save_job = None
        self.store.save()

    def fullscreen_loop(self):
        try:
            fs = bool(self.store.s.get("hide_fullscreen", True)) and foreground_fullscreen()
            if fs != self.fs_hidden:
                self.fs_hidden = fs
                if not self.hidden:
                    if fs:
                        self.root.withdraw()
                        self.bubble.set_shown(False)
                    else:
                        self.root.deiconify()
                        self.root.overrideredirect(True)
                        self.root.attributes("-topmost", True)
                        self.bubble.set_shown(True)
        except Exception:
            log_error()
        self.root.after(3000, self.fullscreen_loop)

    def restore_pending(self):
        """Nhắc đang hiện mà tắt máy/thoát app -> mở lại sẽ nhắc tiếp, không mất việc."""
        tiso = dt.date.today().isoformat()
        for t in self.store.tasks:
            ps = t.get("pending_sched")
            if not ps:
                continue
            same_day = (t.get("last_occ", "").startswith(tiso) or (t.get("last_fired_ts") or "").startswith(tiso))
            if t.get("enabled") and same_day and t.get("done_date") != tiso:
                self.fire(t, ps)
            else:
                t["pending_sched"] = ""
        self.store.save()

    def name(self):
        return self.store.s.get("pet_name") or "Bi"

    # ── vòng lặp ──
    def anim_loop(self):
        try:
            t = now().timestamp()
            dtt = min(0.2, max(0.01, t - self._last))
            self._last = t
            self.gmouse.poll()
            if not self.hidden and not self.fs_hidden:
                self.pet.tick(dtt)
        except Exception:
            log_error()
        delay = 500 if (self.hidden or self.fs_hidden) else self.pet.frame_delay()
        self.root.after(delay, self.anim_loop)

    def topmost_loop(self):
        try:
            if not self.hidden and not self.fs_hidden:
                self.root.attributes("-topmost", True)
                self.root.lift()
                self.bubble.raise_()
        except Exception:
            pass
        self.root.after(4000, self.topmost_loop)

    def learn_loop(self):
        try:
            before = {s["key"] for s in self.learner.suggestions}
            sgs = self.learner.analyze()
            if self.store.s.get("auto_adjust"):
                for sg in [x for x in sgs if x["kind"] == "shift_time"]:
                    self.learner.apply(sg)
                    self.say("Mình đã tự " + sg["text"][0].lower() + sg["text"][1:], sg["reason"], timeout=12)
            for sg in self.learner.suggestions:
                if sg["key"] not in before and not self.in_quiet():
                    self.bubble.push({
                        "kind": "suggest", "key": "sg:" + sg["key"], "title": "★ %s để ý thấy..." % self.name(),
                        "title_fg": "#c79bff", "text": sg["reason"] + ".\n→ " + sg["text"] + "?", "bg": "#1a1426", "edge": C_ACC2,
                        "buttons": [("Đồng ý", lambda s=sg: (self.learner.apply(s), self.pet.happy(2)), "#7b4fd6"),
                                    ("Không", lambda s=sg: self.learner.ignore(s), "#4a4060")]})
                    break   # mỗi lần chỉ gợi ý 1 cái
        except Exception:
            log_error()
        self.root.after(20 * 60 * 1000, self.learn_loop)

    def track_loop(self):
        try:
            self.idle = get_idle_seconds()
            n = now()
            d = n.date().isoformat()
            if self.idle < 60:
                if d not in self.store.data["day_start"]:
                    self.store.data["day_start"][d] = n.strftime("%H:%M")
                if self.was_idle_long:
                    self.was_idle_long = False
                    self.greet_if_new_day(back=True)
            if self.idle >= 1800:
                self.was_idle_long = True
            # thời gian làm việc liên tục
            if self.idle < 120:
                self.active_secs += 30
            elif self.idle >= 300:
                self.active_secs = 0
            bm = int(self.store.s.get("break_minutes", 0) or 0)
            if bm > 0 and self.active_secs >= bm * 60 and not self.break_pending and not self.in_quiet() and not self.is_muted():
                self.break_pending = True
                self.bubble.push({
                    "kind": "break", "key": "break", "sound": True, "title": "☕ Nghỉ một chút nhé!",
                    "title_fg": "#5ee38b", "bg": "#0f1a14", "edge": "#2fbf6b",
                    "text": "Bạn đã làm liên tục %s rồi.\nĐứng dậy vươn vai, nhìn xa 20 giây cho mắt nghỉ." % fmt_dur(self.active_secs / 60),
                    "buttons": [("Đã nghỉ ✓", self.break_done, "#27ae60"), ("10 phút nữa", self.break_later, "#e67e22")]})
            # theo dõi ứng dụng
            if self.store.s.get("track_apps") and self.idle < 120:
                exe = get_foreground_exe()
                if exe and exe not in APP_IGNORE:
                    day = self.store.data["app_usage"].setdefault(d, {})
                    rec = day.setdefault(exe, {"first": n.strftime("%H:%M"), "minutes": 0.0})
                    rec["minutes"] = round(rec.get("minutes", 0) + 0.5, 1)
            self.ticks += 1
            if self.ticks % 10 == 0:            # mỗi 5 phút
                self.store.s["pos"] = self.pet.anchor_screen()
                self.store.save()
                self.refresh_areas()
                self.pet.move_to(self.pet.x, self.pet.y)   # đổi độ phân giải / rút màn hình phụ -> kéo chibi về
                self.refresh_ui()
        except Exception:
            log_error()
        self.root.after(30000, self.track_loop)

    def break_done(self):
        self.active_secs = 0
        self.break_pending = False
        self.store.add_log("break")
        self.pet.happy(2)

    def break_later(self):
        bm = int(self.store.s.get("break_minutes", 60) or 60)
        self.active_secs = max(0, (bm - 10) * 60)
        self.break_pending = False

    def schedule_loop(self):
        try:
            self.check_tasks()
            self.maybe_chat()
            # máy chạy qua đêm: sang ngày mới vẫn chào và đọc lịch hôm nay
            if (self.store.s.get("last_greet_date") != dt.date.today().isoformat()
                    and now().hour >= 5 and self.idle < 60 and not self.fs_hidden):
                self.greet_if_new_day()
        except Exception:
            log_error()
        self.root.after(15000, self.schedule_loop)

    def check_tasks(self):
        n = now()
        today = n.date()
        tiso = today.isoformat()
        nm = n.hour * 60 + n.minute
        pre = int(self.store.s.get("pre_notice", 0) or 0)
        muted = self.is_muted()
        changed = False
        for t in self.store.tasks:
            if not t.get("enabled") or t["id"] in self.pending:
                continue
            if t.get("repeat") == "once" and t.get("date", tiso) < tiso and not t.get("snooze_until"):
                t["enabled"] = False         # việc một lần đã qua ngày -> tự tắt
                changed = True
                continue
            if t.get("snooze_until"):
                su = parse_iso(t["snooze_until"])
                if su and n >= su and not muted:
                    t["snooze_until"] = ""
                    self.fire(t, t.get("snooze_sched") or t["time"], snoozed=True)
                    changed = True
                continue
            if not occurs_on(t, today):
                continue
            if t.get("repeat") == "interval":
                st_, en = hm2m(t["time"]), hm2m(t.get("end", "17:00"))
                if not (st_ <= nm <= en) or muted:
                    continue
                # bám theo mốc cố định: bắt đầu 08:30, mỗi 90' -> 08:30, 10:00, 11:30...
                # (trước đây mở máy lúc nào là nhắc ngay lúc đó, lệch hết lịch)
                iv = max(5, int(t.get("interval", 60)))
                slot = st_ + ((nm - st_) // iv) * iv
                if nm - slot > 10:
                    continue                 # đã lỡ mốc này quá 10 phút -> chờ mốc sau
                last = parse_iso(t.get("last_fired_ts") or "")
                if last and last.date() == today and last.hour * 60 + last.minute >= slot:
                    continue
                t["last_fired_ts"] = iso(n)
                self.fire(t, n.strftime("%H:%M"))
                changed = True
                continue
            tm = hm2m(t["time"])
            occ = "%s %s" % (tiso, t["time"])
            if t.get("last_occ") == occ or t.get("done_date") == tiso:
                continue
            if 0 <= nm - tm <= GRACE_MIN:
                if muted:
                    continue
                t["last_occ"] = occ
                self.fire(t, t["time"], late=nm - tm > 10)
                changed = True
            elif pre > 0 and 0 < tm - nm <= pre and t.get("pre_occ") != occ and not muted:
                t["pre_occ"] = occ
                changed = True
                self.say("%d phút nữa: %s" % (tm - nm, t["title"]), "Lúc %s — mình sẽ nhắc lại đúng giờ." % t["time"],
                         timeout=10, key="pre:" + t["id"])
        if changed:
            self.store.save()

    def fire(self, t, sched, late=False, snoozed=False, test=False):
        title = "⏰ %s  —  %s" % (sched, t["title"])
        text = t.get("note") or ""
        if test:
            # nhắc thử: không ghi nhật ký, không làm sai dữ liệu tự học
            self.bubble.push({"kind": "reminder", "key": "test:" + t["id"], "sound": True, "title": title,
                              "text": (text + "\n(Đây là nhắc thử)").strip(),
                              "buttons": [("Đã thấy ✓", None, "#27ae60")]})
            return
        self.pending[t["id"]] = sched
        t["pending_sched"] = sched
        self.save_soon(300)
        self.root.after(200, self.refresh_ui)
        if late:
            text = ("(Đã quá giờ — máy vừa bật/hết im lặng)\n" + text).strip()
        if snoozed:
            text = ("(Nhắc lại sau khi hoãn)\n" + text).strip()
        self.bubble.push({
            "kind": "reminder", "key": "rem:" + t["id"], "sound": True, "title": title, "text": text,
            "buttons": [("Xong ✓", lambda: self.task_done(t["id"]), "#27ae60"),
                        ("Hoãn 10'", lambda: self.task_snooze(t["id"], 10), "#e67e22"),
                        ("Hoãn 30'", lambda: self.task_snooze(t["id"], 30), "#d35400"),
                        ("Bỏ qua", lambda: self.task_skip(t["id"]), "#95a5a6")]})
        self.root.after(60000, lambda: self.reping(t["id"], 1))

    def reping(self, tid, n):
        if tid in self.pending and self.bubble.msg and self.bubble.msg.get("key") == "rem:" + tid and n <= 3:
            if self.store.s.get("sound"):
                beep()
            self.pet.happy_until = 0
            self.root.after(120000, lambda: self.reping(tid, n + 1))

    def task_done(self, tid, early=False):
        t = self.store.task(tid)
        if not t:
            return
        self.bubble.drop("rem:" + tid)
        t["pending_sched"] = ""
        sched = self.pending.pop(tid, None) or (t["time"] if early else None)
        t["snooze_until"] = ""
        if t.get("repeat") != "interval":
            t["done_date"] = dt.date.today().isoformat()
            t["last_occ"] = "%s %s" % (t["done_date"], t["time"])
        if t.get("repeat") == "once":
            t["enabled"] = False
        self.store.add_log("done", t, sched=sched)
        self.pet.event("E_DONE")
        self.say(random.choice(["Giỏi quá! ♥", "Tuyệt vời!", "Xong một việc rồi nè!", "Làm tốt lắm!"]), timeout=3)
        self.refresh_ui()

    def task_snooze(self, tid, mins):
        t = self.store.task(tid)
        if not t:
            return
        self.bubble.drop("rem:" + tid)
        t["pending_sched"] = ""
        sched = self.pending.pop(tid, None) or t["time"]
        t["snooze_until"] = iso(now() + dt.timedelta(minutes=mins))
        t["snooze_sched"] = sched
        self.store.add_log("snooze", t, sched=sched, extra={"mins": mins})
        self.pet.event("E_SNOOZE")
        self.refresh_ui()

    def task_skip(self, tid):
        t = self.store.task(tid)
        if not t:
            return
        self.bubble.drop("rem:" + tid)
        t["pending_sched"] = ""
        sched = self.pending.pop(tid, None)
        t["snooze_until"] = ""
        if t.get("repeat") == "once":
            t["enabled"] = False
        self.store.add_log("skip", t, sched=sched)
        self.pet.event("E_SKIP")
        self.refresh_ui()

    def upcoming(self, limit=5):
        n = now()
        nm = n.hour * 60 + n.minute
        out = []
        tiso = n.date().isoformat()
        for t in self.store.tasks:
            if not t.get("enabled") or not occurs_on(t, n.date()):
                continue
            if t.get("repeat") == "interval":
                continue
            tm = hm2m(t["time"])
            if tm >= nm and t.get("done_date") != tiso:
                out.append((tm, t))
        out.sort(key=lambda x: x[0])
        return out[:limit]

    def maybe_chat(self):
        if not self.store.s.get("talk") or self.bubble.visible or self.in_quiet() or self.is_muted() or self.hidden:
            return
        if now() < self.next_chat or self.idle > 120:
            return
        self.next_chat = now() + dt.timedelta(minutes=random.uniform(20, 45))
        up = self.upcoming(1)
        if up and random.random() < 0.5:
            tm, t = up[0]
            left = tm - (now().hour * 60 + now().minute)
            self.say("Việc tiếp theo: %s" % t["title"], "Lúc %s (còn %s)" % (t["time"], fmt_dur(left)), timeout=8)
        else:
            self.say(random.choice(PHRASES), timeout=6)

    def say(self, title, text="", timeout=6, key=None):
        self.bubble.push({"kind": "info", "title": title, "title_fg": "#7cc4ff", "edge": C_ACC2, "text": text,
                          "timeout": timeout, "key": key})

    def greet_if_new_day(self, back=False):
        s = self.store.s
        d = dt.date.today().isoformat()
        h = now().hour
        if s.get("last_greet_date") != d:
            s["last_greet_date"] = d
            self.store.save()
            part = "buổi sáng" if h < 11 else ("buổi trưa" if h < 13 else ("buổi chiều" if h < 18 else "buổi tối"))
            ups = [(t["time"], t["title"]) for t in self.store.tasks
                   if t.get("enabled") and occurs_on(t, dt.date.today()) and t.get("repeat") != "interval"]
            ups.sort()
            if ups:
                lines = "\n".join("• %s  %s" % x for x in ups[:6])
                more = "\n… và %d việc khác" % (len(ups) - 6) if len(ups) > 6 else ""
                text = "Hôm nay có %d việc cần nhớ:\n%s%s" % (len(ups), lines, more)
            else:
                text = "Hôm nay chưa có việc nào. Bấm chuột phải vào mình để thêm nhé!"
            self.bubble.push({"kind": "greet", "title": "Chào %s! Mình là %s ☀" % (part, self.name()),
                              "title_fg": C_GOLD, "edge": C_GOLD, "text": text, "timeout": 25})
            self.pet.happy(2)
        elif back:
            self.say("Chào mừng bạn quay lại!", "Mình vẫn canh lịch giúp bạn đây.", timeout=6)
            self.pet.happy(2)

    def on_pet_click(self):
        up = self.upcoming(3)
        if self.bubble.visible:
            return
        if up:
            n = now().hour * 60 + now().minute
            lines = "\n".join("• %s  %s (còn %s)" % (t["time"], t["title"], fmt_dur(tm - n)) for tm, t in up)
            self.say("Sắp tới:", lines, timeout=8)
        else:
            self.say(random.choice(PHRASES), "Hôm nay không còn việc nào nữa ✓", timeout=6)

    # ── menu chuột phải ──
    def show_menu(self, e=None):
        s = self.store.s
        m = tk.Menu(self.root, tearoff=0, font=(FONT, 10), bg=C_PANEL, fg=C_FG, activebackground=C_ACC, activeforeground="#ffffff", bd=1)
        m.add_command(label="✚  Thêm việc nhắc...", command=lambda: TaskEditor(self, None))
        m.add_command(label="✎  Ghi nhận việc vừa làm...", command=self.quick_note)
        m.add_command(label="☰  Mở bảng quản lý", command=self.open_manager)
        m.add_separator()
        am = tk.Menu(m, tearoff=0, font=(FONT, 10))
        groups = {}
        for n in self.pet.pack.user_behaviors():
            groups.setdefault(beh_group(n), []).append(n)
        for g, names in groups.items():
            gm = tk.Menu(am, tearoff=0, font=(FONT, 10))
            for n in names:
                gm.add_command(label=beh_label(n), command=lambda n=n: self.pet.engine.force(n))
            am.add_cascade(label=g, menu=gm)
        m.add_cascade(label="★  Ra chiêu", menu=am)
        self._free_var = tk.BooleanVar(value=s.get("free_master", True))
        m.add_checkbutton(label="Tự hoạt động tự do", variable=self._free_var,
                          command=lambda: self.set_setting("free_master", self._free_var.get()))
        sm = tk.Menu(m, tearoff=0, font=(FONT, 10))
        for lab, v in (("Nhỏ", 0.6), ("Vừa", 1.0), ("Lớn", 1.5), ("Rất lớn", 2.2), ("Khổng lồ", 3.0)):
            sm.add_command(label="%s (%.1fx)" % (lab, v), command=lambda v=v: self.set_scale(v))
        m.add_cascade(label="Kích thước", menu=sm)
        qm = tk.Menu(m, tearoff=0, font=(FONT, 10))
        for lab, mins in (("30 phút", 30), ("1 giờ", 60), ("2 giờ", 120), ("4 giờ", 240)):
            qm.add_command(label=lab, command=lambda mm=mins: self.mute(mm))
        qm.add_command(label="Bật lại ngay", command=lambda: self.mute(0))
        m.add_cascade(label="Im lặng (dời nhắc)", menu=qm)
        m.add_command(label="Ẩn 15 phút", command=lambda: self.hide(15))
        m.add_command(label="⟳  Kiểm tra cập nhật (F5)", command=lambda: self.updater.check(manual=True))
        m.add_separator()
        m.add_command(label="Thoát", command=self.quit)
        x, y = (e.x_root, e.y_root) if e is not None else self.root.winfo_pointerxy()
        try:
            m.tk_popup(x, y)
        finally:
            m.grab_release()

    def run_cmd(self, cmd, e=None):
        try:
            if cmd == "upcoming":
                self.on_pet_click()
            elif cmd == "manager":
                self.open_manager()
            elif cmd == "menu":
                self.show_menu(e)
            elif cmd == "add_task":
                TaskEditor(self, None)
            elif cmd == "note":
                self.quick_note()
            elif cmd == "chat":
                self.say(random.choice(PHRASES), timeout=5)
            elif cmd == "bigger":
                self.set_scale(self.pet.s_user + 0.2)
            elif cmd == "smaller":
                self.set_scale(self.pet.s_user - 0.2)
            elif cmd == "toggle_free":
                v = not self.store.s.get("free_master", True)
                self.set_setting("free_master", v)
                self.say("Tự hoạt động: " + ("BẬT" if v else "TẮT"), timeout=3)
            elif cmd == "mute":
                self.mute(30)
            elif cmd == "hide":
                self.hide(15)
        except Exception:
            log_error()

    def set_setting(self, k, v):
        self.store.s[k] = v
        self.save_soon()

    def set_scale(self, v):
        v = round(max(0.4, min(3.0, v)), 2)
        self.store.s["scale"] = v
        self.store.save()
        self.pet.apply_look()
        self.refresh_ui(look=True)

    def mute(self, mins):
        if mins <= 0:
            self.muted_until = None
            self.say("Đã bật nhắc lại!", timeout=3)
        else:
            self.muted_until = now() + dt.timedelta(minutes=mins)
            self.say("Im lặng %s" % fmt_dur(mins), "Việc đến giờ sẽ được nhắc sau khi hết im lặng (tối đa trễ 3 giờ).", timeout=5)

    def hide(self, mins):
        # không đóng bong bóng nhắc (trước đây đóng -> việc bị kẹt "đang nhắc" cả ngày)
        self.hidden = True
        if self.bubble.msg and self.bubble.msg.get("kind") not in ("reminder", "break"):
            self.bubble.close()
        self.bubble.set_shown(False)
        self.root.withdraw()
        self.root.after(mins * 60000, self.unhide)

    def unhide(self):
        if self.hidden:
            self.hidden = False
            if not self.fs_hidden:
                self.root.deiconify()
                self.root.overrideredirect(True)
                self.root.attributes("-topmost", True)
                self.bubble.set_shown(True)

    def quick_note(self):
        QuickNote(self)

    def open_manager(self):
        self.unhide()
        if self.manager and self.manager.alive():
            self.manager.win.deiconify()
            self.manager.win.lift()
            self.manager.win.focus_force()
            return
        self.manager = Manager(self)

    def refresh_ui(self, look=False):
        if self.manager and self.manager.alive():
            try:
                self.manager.refresh(look)
            except Exception:
                log_error()

    def start_server(self):
        def run(sock):
            while True:
                try:
                    c, _ = sock.accept()
                    c.close()
                    self.root.after(0, self.open_manager)
                except Exception:
                    break
        threading.Thread(target=run, args=(self.server,), daemon=True).start()

    def quit(self):
        try:
            self.gmouse.stop()
            if self.save_job:
                self.root.after_cancel(self.save_job)
            self.store.s["pos"] = self.pet.anchor_screen()
            self.store.save()
        finally:
            self.root.destroy()


# ───────────────────────── Hộp thoại ─────────────────────────
class TaskEditor:
    def __init__(self, app, task, parent=None):
        self.app = app
        self.task = task
        w = tk.Toplevel(parent or app.root)
        self.win = w
        w.title("Sửa việc nhắc" if task else "Thêm việc nhắc")
        w.attributes("-topmost", True)
        w.resizable(False, False)
        t = task
        if not t:
            m = round5(now().hour * 60 + now().minute + 30)
            t = new_task("", m2hm(m), "once")
            if m >= 1440:      # 23:40 + 30' -> sang ngày mai
                t["date"] = (dt.date.today() + dt.timedelta(days=1)).isoformat()
        f = ttk.Frame(w, padding=14)
        f.pack(fill="both")
        r = 0
        ttk.Label(f, text="Tên việc:").grid(row=r, column=0, sticky="w")
        self.title = ttk.Entry(f, width=42, font=(FONT, 10))
        self.title.insert(0, t["title"])
        self.title.grid(row=r, column=1, columnspan=3, sticky="we", pady=3)
        r += 1
        ttk.Label(f, text="Ghi chú:").grid(row=r, column=0, sticky="w")
        self.note = ttk.Entry(f, width=42, font=(FONT, 10))
        self.note.insert(0, t.get("note", ""))
        self.note.grid(row=r, column=1, columnspan=3, sticky="we", pady=3)
        r += 1
        ttk.Label(f, text="Giờ (HH:MM):").grid(row=r, column=0, sticky="w")
        self.time = ttk.Entry(f, width=8, font=(FONT, 10))
        self.time.insert(0, t["time"])
        self.time.grid(row=r, column=1, sticky="w", pady=3)
        r += 1
        ttk.Label(f, text="Lặp lại:").grid(row=r, column=0, sticky="w")
        self.rep = ttk.Combobox(f, state="readonly", width=26, values=[b for _, b in REPEAT_LABELS], font=(FONT, 10))
        self.rep.set(REPEAT_TEXT.get(t["repeat"], "Một lần"))
        self.rep.grid(row=r, column=1, columnspan=3, sticky="w", pady=3)
        self.rep.bind("<<ComboboxSelected>>", lambda e: self.update_vis())
        r += 1
        self.date_lbl = ttk.Label(f, text="Ngày (dd/mm/yyyy):")
        self.date_lbl.grid(row=r, column=0, sticky="w")
        self.date = ttk.Entry(f, width=12, font=(FONT, 10))
        try:
            self.date.insert(0, dt.date.fromisoformat(t.get("date")).strftime("%d/%m/%Y"))
        except Exception:
            self.date.insert(0, dt.date.today().strftime("%d/%m/%Y"))
        self.date.grid(row=r, column=1, sticky="w", pady=3)
        r += 1
        self.days_fr = ttk.Frame(f)
        self.days_fr.grid(row=r, column=0, columnspan=4, sticky="w", pady=3)
        ttk.Label(self.days_fr, text="Các thứ:   ").pack(side="left")
        self.dvars = []
        for i, n in enumerate(WD):
            v = tk.BooleanVar(value=i in (t.get("days") or []))
            ttk.Checkbutton(self.days_fr, text=n, variable=v).pack(side="left")
            self.dvars.append(v)
        r += 1
        self.iv_fr = ttk.Frame(f)
        self.iv_fr.grid(row=r, column=0, columnspan=4, sticky="w", pady=3)
        ttk.Label(self.iv_fr, text="Mỗi").pack(side="left")
        self.iv = ttk.Spinbox(self.iv_fr, from_=5, to=480, increment=5, width=5)
        self.iv.set(t.get("interval", 60))
        self.iv.pack(side="left", padx=4)
        ttk.Label(self.iv_fr, text="phút, từ giờ trên đến").pack(side="left")
        self.end = ttk.Entry(self.iv_fr, width=7)
        self.end.insert(0, t.get("end", "17:00"))
        self.end.pack(side="left", padx=4)
        r += 1
        bf = ttk.Frame(f)
        bf.grid(row=r, column=0, columnspan=4, sticky="e", pady=(10, 0))
        ttk.Button(bf, text="Lưu", style="Accent.TButton", command=self.save).pack(side="left", padx=4)
        ttk.Button(bf, text="Huỷ", command=w.destroy).pack(side="left")
        self.update_vis()
        self.title.focus_set()
        w.bind("<Return>", lambda e: self.save())
        w.bind("<Escape>", lambda e: w.destroy())
        w.update_idletasks()
        w.geometry("+%d+%d" % (w.winfo_screenwidth() // 2 - w.winfo_width() // 2, w.winfo_screenheight() // 3))

    def rep_key(self):
        v = self.rep.get()
        for k, b in REPEAT_LABELS:
            if b == v:
                return k
        return "once"

    def update_vis(self):
        k = self.rep_key()
        for wdg in (self.date_lbl, self.date):
            wdg.grid() if k == "once" else wdg.grid_remove()
        self.days_fr.grid() if k in ("weekly", "interval") else self.days_fr.grid_remove()
        self.iv_fr.grid() if k == "interval" else self.iv_fr.grid_remove()

    def save(self):
        title = self.title.get().strip()
        if not title:
            messagebox.showwarning(APP_NAME, "Vui lòng nhập tên việc.", parent=self.win)
            return
        tm = self.time.get().strip().replace("h", ":").replace(".", ":")
        if re.fullmatch(r"\d{1,2}", tm):
            tm += ":00"
        mt = re.fullmatch(r"(\d{1,2}):(\d{1,2})", tm)
        if not mt or int(mt.group(1)) > 23 or int(mt.group(2)) > 59:
            messagebox.showwarning(APP_NAME, "Giờ không hợp lệ (ví dụ 08:30).", parent=self.win)
            return
        tm = "%02d:%02d" % (int(mt.group(1)), int(mt.group(2)))
        k = self.rep_key()
        days = [i for i, v in enumerate(self.dvars) if v.get()]
        if k == "weekly" and not days:
            messagebox.showwarning(APP_NAME, "Hãy chọn ít nhất một thứ.", parent=self.win)
            return
        date = dt.date.today().isoformat()
        if k == "once":
            try:
                date = dt.datetime.strptime(self.date.get().strip(), "%d/%m/%Y").date().isoformat()
            except Exception:
                messagebox.showwarning(APP_NAME, "Ngày không hợp lệ (dd/mm/yyyy).", parent=self.win)
                return
        if k == "once" and (date < dt.date.today().isoformat() or
                            (date == dt.date.today().isoformat() and hm2m(tm) < now().hour * 60 + now().minute - GRACE_MIN)):
            messagebox.showwarning(APP_NAME, "Thời điểm này đã qua, chọn ngày/giờ khác.", parent=self.win)
            return
        end = self.end.get().strip()
        if k == "interval" and not re.fullmatch(r"\d{1,2}:\d{2}", end):
            messagebox.showwarning(APP_NAME, "Giờ kết thúc không hợp lệ.", parent=self.win)
            return
        try:
            iv = max(5, int(self.iv.get()))
        except Exception:
            iv = 60
        st = self.app.store
        if self.task:
            t = self.task
            if t["time"] != tm or t.get("date") != date or t["repeat"] != k:
                t["last_occ"] = t["done_date"] = t["pre_occ"] = ""
                t["snooze_until"] = t["pending_sched"] = ""
                self.app.pending.pop(t["id"], None)
                self.app.bubble.drop("rem:" + t["id"])
        else:
            t = new_task(title)
            st.tasks.append(t)
        t.update({"title": title, "note": self.note.get().strip(), "time": tm, "repeat": k, "days": days,
                  "date": date, "interval": iv, "end": end, "enabled": True})
        st.save()
        self.win.destroy()
        self.app.pet.happy(1.5)
        self.app.say("Đã lưu: %s" % title, "%s — %s" % (tm, repeat_desc(t)), timeout=4)
        self.app.refresh_ui()


class QuickNote:
    """Ghi nhận việc vừa làm: dữ liệu để bộ tự học phát hiện thói quen."""

    def __init__(self, app, parent=None):
        self.app = app
        w = tk.Toplevel(parent or app.root)
        self.win = w
        w.title("Ghi nhận việc vừa làm")
        w.attributes("-topmost", True)
        w.resizable(False, False)
        f = ttk.Frame(w, padding=14)
        f.pack()
        ttk.Label(f, text="Bạn vừa làm xong việc gì?").pack(anchor="w")
        seen, opts = set(), []
        for e in reversed(app.store.data["log"]):
            if e["kind"] in ("note", "done") and norm(e.get("title")) not in seen and e.get("title"):
                seen.add(norm(e["title"]))
                opts.append(e["title"])
            if len(opts) >= 30:
                break
        self.cb = ttk.Combobox(f, values=opts, width=40, font=(FONT, 10))
        self.cb.pack(pady=6)
        self.cb.focus_set()
        ttk.Label(f, text="Ghi nhận đều đặn vài ngày, %s sẽ tự đề xuất tạo lịch nhắc." % app.name(),
                  foreground=C_MUTED).pack(anchor="w")
        bf = ttk.Frame(f)
        bf.pack(anchor="e", pady=(8, 0))
        ttk.Button(bf, text="Ghi nhận", style="Accent.TButton", command=self.ok).pack(side="left", padx=4)
        ttk.Button(bf, text="Huỷ", command=w.destroy).pack(side="left")
        w.bind("<Return>", lambda e: self.ok())
        w.bind("<Escape>", lambda e: w.destroy())
        w.update_idletasks()
        w.geometry("+%d+%d" % (w.winfo_screenwidth() // 2 - w.winfo_width() // 2, w.winfo_screenheight() // 3))

    def ok(self):
        txt = self.cb.get().strip()
        if not txt:
            return
        self.app.store.add_log("note", title=txt)
        self.win.destroy()
        self.app.pet.happy(2)
        self.app.say("Đã ghi nhận ✓", txt, timeout=3)
        self.app.learner.analyze()
        self.app.refresh_ui()


# ───────────────────────── Bảng quản lý ─────────────────────────
class Manager:
    def __init__(self, app):
        self.app = app
        w = tk.Toplevel(app.root)
        self.win = w
        w.title("%s v%s — Bảng quản lý" % (APP_NAME, APP_VER))
        w.configure(bg=C_BG)
        w.geometry("%dx%d" % (int(980 * app.dpi), int(680 * app.dpi)))
        w.minsize(820, 560)
        self.banner = tk.Canvas(w, height=int(92 * app.dpi), bg=C_BG, highlightthickness=0)
        self.banner.pack(fill="x")
        self.banner.bind("<Configure>", lambda e: self.draw_banner())
        nb = ttk.Notebook(w)
        nb.pack(fill="both", expand=True, padx=10, pady=(4, 10))
        self.nb = nb
        self.build_tasks(nb)
        self.build_today(nb)
        self.build_learn(nb)
        self.build_char(nb)
        self.build_controls(nb)
        self.build_settings(nb)
        self._tlog = {}
        self.refresh(True)
        w.lift()
        w.focus_force()
        self.auto_refresh()
        w.after(50, self.draw_banner)

    def draw_banner(self):
        """Dải tiêu đề: nền chuyển đỏ thẫm -> tím đêm, chữ vàng kim, chân dung nhân vật, tóm tắt hôm nay."""
        cv = self.banner
        cv.delete("all")
        W, H = max(200, cv.winfo_width()), int(cv["height"])
        a, b = (0x3a, 0x07, 0x14), (0x12, 0x09, 0x26)
        step = 4
        for x in range(0, W, step):
            k = x / float(W)
            col = "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))
            cv.create_rectangle(x, 0, x + step, H, fill=col, outline=col)
        for i in range(6):                                     # vệt chém chéo
            x0 = W * 0.42 + i * 46
            cv.create_line(x0, H, x0 + 70, 0, fill="#2a0d2e" if i % 2 else "#3b0d1f", width=10)
        cv.create_line(0, H - 2, W, H - 2, fill=C_ACC, width=2)
        cv.create_line(0, H - 4, W * 0.6, H - 4, fill=C_GOLD, width=1)
        try:
            pk = self.app.pet.pack
            p = pk.actions["Stand"].poses[0]
            im = pk.image(p.img)
            z = (H - 8) / float(im.height)
            t = im.resize((max(1, int(im.width * z)), H - 8), Image.LANCZOS)
            self._ban = ImageTk.PhotoImage(ImageOps.mirror(t))
            cv.create_image(12, H - 4, image=self._ban, anchor="sw")
            x0 = 12 + t.width + 14
        except Exception:
            x0 = 18
        fs = max(16, int(H * 0.26))
        title = "CHIBI NHẮC VIỆC"
        cv.create_text(x0 + 2, H * 0.40 + 2, text=title, anchor="w", fill="#5a1020", font=(FONT, fs, "bold"))
        cv.create_text(x0, H * 0.40, text=title, anchor="w", fill=C_GOLD, font=(FONT, fs, "bold"))
        nm = self.app.name()
        cv.create_text(x0, H * 0.74, anchor="w", fill="#ff8a9a", font=(FONT, 10, "bold"),
                       text="⚔  %s  •  v%s" % (nm.upper(), APP_VER))
        try:
            today = dt.date.today()
            st = self.app.store
            cnt = sum(1 for t_ in st.tasks if t_.get("enabled") and occurs_on(t_, today))
            done = sum(1 for t_ in st.tasks if t_.get("done_date") == today.isoformat())
            up = self.app.upcoming(1)
            nxt = ("Tiếp theo: %s  %s" % (up[0][1]["time"], up[0][1]["title"])) if up else "Hôm nay hết việc ✓"
            cv.create_text(W - 16, H * 0.36, anchor="e", fill=C_FG, font=(FONT, 11, "bold"),
                           text="Hôm nay: %d/%d việc" % (done, cnt))
            cv.create_text(W - 16, H * 0.66, anchor="e", fill=C_MUTED, font=(FONT, 9), text=nxt[:60])
        except Exception:
            pass
        bx = W * 0.58
        cv.create_rectangle(bx, H * 0.30, bx + 150, H * 0.70, fill="#2a0d1c", outline=C_GOLD, width=1, tags="upd")
        cv.create_text(bx + 75, H * 0.50, text="⟳  CẬP NHẬT  (F5)", fill=C_GOLD, font=(FONT, 9, "bold"), tags="upd")
        cv.tag_bind("upd", "<Button-1>", lambda e: self.app.updater.check(manual=True, install=True))
        cv.tag_bind("upd", "<Enter>", lambda e: cv.config(cursor="hand2"))
        cv.tag_bind("upd", "<Leave>", lambda e: cv.config(cursor=""))

    def auto_refresh(self):
        if not self.alive():
            return
        try:
            self.refresh()
        except Exception:
            log_error()
        self.win.after(30000, self.auto_refresh)

    def alive(self):
        try:
            return bool(self.win.winfo_exists())
        except Exception:
            return False

    # ── tab việc ──
    def build_tasks(self, nb):
        f = ttk.Frame(nb, padding=8)
        nb.add(f, text="  Việc nhắc  ")
        cols = ("time", "title", "repeat", "status", "src")
        tv = ttk.Treeview(f, columns=cols, show="headings", selectmode="browse")
        for c, h, wd in (("time", "Giờ", 70), ("title", "Tên việc", 300), ("repeat", "Lặp lại", 230),
                         ("status", "Hôm nay", 110), ("src", "Nguồn", 80)):
            tv.heading(c, text=h)
            tv.column(c, width=wd, anchor="w" if c in ("title", "repeat") else "center")
        tv.tag_configure("off", foreground="#6d6480")
        tv.tag_configure("learned", foreground="#c79bff")
        sb = ttk.Scrollbar(f, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        tv.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        f.rowconfigure(0, weight=1)
        f.columnconfigure(0, weight=1)
        tv.bind("<Double-1>", lambda e: self.edit())
        self.tv = tv
        bf = ttk.Frame(f)
        bf.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))
        for txt, fn in (("✚ Thêm", lambda: TaskEditor(self.app, None, self.win)), ("✎ Sửa", self.edit),
                        ("✕ Xoá", self.delete), ("Bật / Tắt", self.toggle), ("✓ Xong hôm nay", self.done_now),
                        ("▶ Thử nhắc", self.test_fire)):
            ttk.Button(bf, text=txt, command=fn).pack(side="left", padx=3)

    def sel(self):
        s = self.tv.selection()
        return self.app.store.task(s[0]) if s else None

    def edit(self):
        t = self.sel()
        if t:
            TaskEditor(self.app, t, self.win)

    def delete(self):
        t = self.sel()
        if t and messagebox.askyesno(APP_NAME, "Xoá việc \"%s\"?" % t["title"], parent=self.win):
            self.app.store.tasks.remove(t)
            self.app.pending.pop(t["id"], None)
            self.app.bubble.drop("rem:" + t["id"])
            self.app.store.save()
            self.refresh()

    def toggle(self):
        t = self.sel()
        if t:
            t["enabled"] = not t.get("enabled")
            if t["enabled"] and t["repeat"] == "once":
                t["last_occ"] = t["done_date"] = ""
            self.app.store.save()
            self.refresh()

    def done_now(self):
        t = self.sel()
        if t:
            self.app.task_done(t["id"], early=True)

    def test_fire(self):
        t = self.sel()
        if t:
            self.app.fire(t, t["time"], test=True)

    def status(self, t):
        today = dt.date.today()
        tiso = today.isoformat()
        if not t.get("enabled"):
            if t.get("repeat") == "once" and t.get("date", tiso) < tiso:
                return "Đã qua ngày"
            return "Đã tắt"
        if not occurs_on(t, today):
            return "—"
        if t.get("snooze_until"):
            return "Hoãn đến " + t["snooze_until"][11:16]
        if t["id"] in self.app.pending:
            return "Đang nhắc!"
        if t.get("repeat") == "interval":
            n = sum(1 for e in self._tlog.get(t["id"], []) if e["kind"] == "done")
            return "Đã làm %d lần" % n
        if t.get("done_date") == tiso:
            return "✓ Xong"
        last = self._tlog.get(t["id"], [])
        if last and last[-1]["kind"] == "skip":
            return "Bỏ qua"
        nm = now().hour * 60 + now().minute
        return "Chờ" if hm2m(t["time"]) > nm else "Đã nhắc"

    # ── tab hôm nay ──
    def build_today(self, nb):
        f = ttk.Frame(nb, padding=8)
        nb.add(f, text="  Hôm nay  ")
        top = ttk.Frame(f)
        top.pack(fill="x")
        self.today_lbl = ttk.Label(top, text="", style="H.TLabel")
        self.today_lbl.pack(side="left")
        ttk.Button(top, text="✎ Ghi nhận việc vừa làm...", command=lambda: QuickNote(self.app, self.win)).pack(side="right")
        ttk.Label(f, text="Nhật ký hôm nay (dữ liệu để tự học):").pack(anchor="w", pady=(8, 2))
        tv = ttk.Treeview(f, columns=("t", "k", "title"), show="headings", height=12)
        for c, h, wd in (("t", "Lúc", 80), ("k", "Hành động", 130), ("title", "Việc", 520)):
            tv.heading(c, text=h)
            tv.column(c, width=wd, anchor="w")
        tv.pack(fill="both", expand=True)
        self.log_tv = tv

    # ── tab tự học ──
    def build_learn(self, nb):
        f = ttk.Frame(nb, padding=8)
        nb.add(f, text="  Tự học  ")
        ttk.Label(f, text="Gợi ý từ thói quen của bạn", style="H.TLabel").pack(anchor="w")
        tv = ttk.Treeview(f, columns=("sg", "why"), show="headings", height=7, selectmode="browse")
        tv.heading("sg", text="Gợi ý")
        tv.heading("why", text="Lý do")
        tv.column("sg", width=380)
        tv.column("why", width=380)
        tv.pack(fill="x", pady=4)
        self.sg_tv = tv
        bf = ttk.Frame(f)
        bf.pack(anchor="w")
        ttk.Button(bf, text="✓ Áp dụng", command=self.sg_apply).pack(side="left", padx=3)
        ttk.Button(bf, text="✕ Bỏ qua", command=self.sg_ignore).pack(side="left", padx=3)
        ttk.Button(bf, text="⟳ Phân tích lại", command=lambda: (self.app.learner.analyze(), self.refresh())).pack(side="left", padx=3)
        ttk.Label(f, text="Thống kê", style="H.TLabel").pack(anchor="w", pady=(12, 0))
        self.stats = tk.Text(f, height=12, font=(FONT, 10), relief="flat", bg=C_PANEL, fg=C_FG, insertbackground=C_FG, wrap="word", padx=10, pady=8)
        self.stats.pack(fill="both", expand=True, pady=4)

    def sg_get(self):
        s = self.sg_tv.selection()
        if not s:
            return None
        for sg in self.app.learner.suggestions:
            if sg["key"] == s[0]:
                return sg

    def sg_apply(self):
        sg = self.sg_get()
        if sg:
            self.app.learner.apply(sg)

    def sg_ignore(self):
        sg = self.sg_get()
        if sg:
            self.app.learner.ignore(sg)

    # ── tab nhân vật ──
    def build_char(self, nb):
        f = ttk.Frame(nb, padding=10)
        nb.add(f, text="  Nhân vật  ")
        s = self.app.store.s
        left = ttk.Frame(f)
        left.pack(side="left", fill="y")
        self.pk_name = ttk.Label(left, text="", style="H.TLabel")
        self.pk_name.pack(anchor="w")
        self.prev = tk.Canvas(left, width=230, height=170, bg="#120d1c", highlightthickness=1, highlightbackground=C_ACC)
        self.prev.pack(pady=4)
        self._pv_i = 0
        ttk.Label(left, text="Tên gọi:").pack(anchor="w", pady=(6, 0))
        self.name_e = ttk.Entry(left, width=24)
        self.name_e.pack(anchor="w")
        self.name_e.bind("<KeyRelease>", lambda e: self.app.set_setting("pet_name", self.name_e.get().strip() or "Bi"))
        ttk.Label(left, text="Kích thước:").pack(anchor="w", pady=(8, 0))
        self.scale_var = tk.DoubleVar(value=s.get("scale", 1.0))
        self.scale_lbl = ttk.Label(left, text="")
        sc = ttk.Scale(left, from_=0.4, to=3.0, variable=self.scale_var, length=230,
                       command=lambda v: self.scale_lbl.config(text="%.1fx" % float(v)))
        sc.pack(anchor="w")
        sc.bind("<ButtonRelease-1>", lambda e: self.app.set_scale(self.scale_var.get()))
        self.scale_lbl.pack(anchor="w")
        self.cvars = {}
        for key, txt, dflt in (("free_master", "Tự hoạt động tự do", True),
                               ("walk_windows", "Đi / đứng trên cửa sổ đang mở", True),
                               ("jump_icons", "Nhảy lên biểu tượng thư mục, file desktop", True),
                               ("auto_jump", "Thấy vật cản phía trước thì nhảy lên", True),
                               ("climb", "Leo tường, leo trần", True),
                               ("smooth", "Hiển thị mịn (giữ hào quang) – mở lại app", True)):
            v = tk.BooleanVar(value=s.get(key, dflt))
            self.cvars[key] = v
            ttk.Checkbutton(left, text=txt, variable=v,
                            command=lambda k=key, v=v: (self.app.set_setting(k, v.get()), self.app.pet.env.refresh(True))
                            ).pack(anchor="w")
        bf = ttk.Frame(left)
        bf.pack(anchor="w", pady=(8, 0))
        ttk.Button(bf, text="Nạp Shimeji khác", style="Small.TButton", command=self.load_pack).pack(side="left")
        ttk.Button(bf, text="Về Áo Đen", style="Small.TButton", command=self.reset_pack).pack(side="left", padx=4)

        right = ttk.Frame(f)
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))
        ttk.Label(right, text="Động tác của nhân vật", style="H.TLabel").pack(anchor="w")
        ttk.Label(right, text="Nhấp đúp hoặc nhấn Space để bật/tắt 'Tự làm'. Động tác tắt tự làm vẫn dùng được khi gán chuột.",
                  foreground=C_MUTED, wraplength=520).pack(anchor="w")
        cols = ("name", "group", "assign", "free")
        tv = ttk.Treeview(right, columns=cols, show="headings", selectmode="browse")
        for c, h, w in (("name", "Động tác", 170), ("group", "Nhóm", 90), ("assign", "Đang gán cho", 190), ("free", "Tự làm", 60)):
            tv.heading(c, text=h)
            tv.column(c, width=w, anchor="center" if c == "free" else "w")
        tv.tag_configure("off", foreground="#6d6480")
        tv.tag_configure("asg", foreground="#c79bff")
        sb = ttk.Scrollbar(right, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        tv.pack(side="top", fill="both", expand=True, pady=4)
        tv.bind("<Double-1>", lambda e: self.toggle_free())
        tv.bind("<space>", lambda e: self.toggle_free())
        self.beh_tv = tv
        b2 = ttk.Frame(right)
        b2.pack(anchor="w")
        ttk.Button(b2, text="▶ Diễn thử", style="Accent.TButton", command=self.try_beh).pack(side="left")
        ttk.Button(b2, text="Bật/tắt", command=self.toggle_free).pack(side="left", padx=4)
        ttk.Button(b2, text="Bật hết", command=lambda: self.set_all_free(True)).pack(side="left")
        ttk.Button(b2, text="Tắt hết", command=lambda: self.set_all_free(False)).pack(side="left", padx=4)
        self.anf_v = tk.BooleanVar(value=s.get("assigned_no_free", True))
        ttk.Checkbutton(right, text="Chiêu gán cho chuột trên nhân vật thì không tự làm (chỉ chạy khi bạn bấm)",
                        variable=self.anf_v, command=lambda: (self.app.set_setting("assigned_no_free", self.anf_v.get()),
                                                              self.refresh_beh())).pack(anchor="w", pady=(6, 0))
        self.preview_loop()

    def beh_names(self):
        pk = self.app.pet.pack
        return pk.user_behaviors() if pk else []

    def refresh_beh(self):
        tv = self.beh_tv
        sel = tv.selection()
        tv.delete(*tv.get_children())
        s = self.app.store.s
        free = s.get("free") or {}
        tr = s.get("triggers") or {}
        lab = dict(TRIGGERS + EVENTS + SCREEN_TRIGGERS)
        excl = self.app.pet.assigned()
        asg = {}
        for k, v in tr.items():
            if v.get("act"):
                asg.setdefault(v["act"], []).append(lab.get(k, k).replace("Chuột ", "").replace("Màn hình – ", "MH ").replace(" – ", " "))
        for n in self.beh_names():
            a = asg.get(n, [])
            on = free.get(n, True)
            eff = on and not (n in excl and s.get("assigned_no_free", True))
            tags = ("asg",) if n in excl else (() if on else ("off",))
            tv.insert("", "end", iid=n, tags=tags, values=(beh_label(n), beh_group(n), ", ".join(a),
                                                          "☑" if eff else ("(gán)" if n in excl and on else "☐")))
        if sel and tv.exists(sel[0]):
            tv.selection_set(sel[0])
            tv.see(sel[0])

    def toggle_free(self):
        sel = self.beh_tv.selection()
        if not sel:
            return
        s = self.app.store.s
        free = dict(s.get("free") or {})
        free[sel[0]] = not free.get(sel[0], True)
        self.app.set_setting("free", free)
        self.refresh_beh()

    def set_all_free(self, on):
        s = self.app.store.s
        asg = self.app.pet.assigned()
        free = dict(s.get("free") or {})
        for n in self.beh_names():
            if on or n not in asg:
                if n in CORE_BEHAVIORS and not on:
                    continue          # giữ đứng/đi cơ bản để nhân vật không đơ
                free[n] = on
        self.app.set_setting("free", free)
        self.refresh_beh()

    def try_beh(self):
        sel = self.beh_tv.selection()
        if sel and not self.app.pet.engine.force(sel[0]):
            messagebox.showinfo(APP_NAME, "Nhân vật đang không đứng trên mặt đất, thử lại sau chút nhé.", parent=self.win)

    def load_pack(self):
        d = filedialog.askdirectory(parent=self.win, title="Chọn thư mục bộ Shimeji-ee (có conf/actions.xml)")
        if not d:
            return
        try:
            pk = ShimejiPack(d)
            assert pk.ok
        except Exception:
            messagebox.showerror(APP_NAME, "Không đọc được. Cần bộ Shimeji-ee có conf/actions.xml và conf/behaviors.xml.",
                                 parent=self.win)
            return
        import shutil
        os.makedirs(PACKS_DIR, exist_ok=True)
        dst = os.path.join(PACKS_DIR, safe_name(pk.name))
        shutil.copytree(pk.img_dir, dst)
        self.app.set_setting("pack", pack_ref(dst))
        self.app.pet.apply_look()
        self.refresh(True)

    def reset_pack(self):
        self.app.set_setting("pack", "")
        self.app.pet.apply_look()
        self.refresh(True)

    def preview_loop(self):
        if not self.alive():
            return
        try:
            pk = self.app.pet.pack
            sp = pk.actions.get("Stand") or next(iter(pk.actions.values()))
            poses = [p for p in sp.poses]
            p = poses[self._pv_i % len(poses)]
            self._pv_i += 1
            im = pk.image(p.img)
            z = min(200.0 / im.width, 150.0 / im.height, 1.3)
            t = im.resize((max(1, int(im.width * z)), max(1, int(im.height * z))), Image.LANCZOS)
            bg = Image.new("RGBA", (230, 170), (18, 13, 28, 255))
            bg.alpha_composite(t, (int(115 - p.ax * z), int(160 - p.ay * z)) if 0 <= 115 - p.ax * z and 160 - p.ay * z >= 0 else (0, 0))
            self._pv = ImageTk.PhotoImage(bg)
            self.prev.delete("all")
            self.prev.create_image(0, 0, image=self._pv, anchor="nw")
            delay = max(60, p.dur * TICK_MS)
        except Exception:
            log_error()
            delay = 500
        self.win.after(delay, self.preview_loop)

    # ── tab điều khiển ──
    def build_controls(self, nb):
        outer = ttk.Frame(nb, padding=8)
        nb.add(outer, text="  Điều khiển  ")
        cv = tk.Canvas(outer, highlightthickness=0, bg=C_BG)
        sb = ttk.Scrollbar(outer, orient="vertical", command=cv.yview)
        cv.bind_all("<MouseWheel>", lambda e: cv.yview_scroll(int(-e.delta / 120), "units")
                    if str(e.widget).startswith(str(cv)) else None, add="+")
        f = ttk.Frame(cv)
        f.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.create_window((0, 0), window=f, anchor="nw")
        cv.configure(yscrollcommand=sb.set)
        cv.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        self.ctrl_rows = {}
        r = 0
        ttk.Label(f, text="Thao tác chuột trên nhân vật", style="H.TLabel").grid(row=r, column=0, sticky="w", columnspan=3)
        r += 1
        ttk.Label(f, text="Thao tác", foreground=C_MUTED).grid(row=r, column=0, sticky="w")
        ttk.Label(f, text="Chiêu / biểu cảm", foreground=C_MUTED).grid(row=r, column=1, sticky="w", padx=6)
        ttk.Label(f, text="Lệnh của app", foreground=C_MUTED).grid(row=r, column=2, sticky="w", padx=6)
        r += 1
        for k, lab in TRIGGERS:
            self._ctrl_row(f, r, k, lab, with_cmd=True)
            r += 1
        ttk.Label(f, text="Kéo xách nhân vật rồi thả ra").grid(row=r, column=0, sticky="w", pady=2)
        self.dropcb = ttk.Combobox(f, state="readonly", width=28)
        self.dropcb.grid(row=r, column=1, sticky="w", padx=6)
        self.dropcb.bind("<<ComboboxSelected>>", lambda e: self.app.set_setting(
            "drop_action", self._drop_map.get(self.dropcb.get(), "")))
        r += 1
        ttk.Label(f, text="Quăng đập vào tường rồi rơi xuống").grid(row=r, column=0, sticky="w", pady=2)
        self.wallcb = ttk.Combobox(f, state="readonly", width=28)
        self.wallcb.grid(row=r, column=1, sticky="w", padx=6)
        self.wallcb.bind("<<ComboboxSelected>>", lambda e: self.app.set_setting(
            "wall_hit_action", self._wall_map.get(self.wallcb.get(), "")))
        r += 1
        ttk.Label(f, text="(Kéo giữ chuột trái + di chuyển = túm nhân vật; thả ra = rơi theo đà tay.  Ctrl + lăn chuột = đổi kích thước.)",
                  foreground=C_MUTED).grid(row=r, column=0, columnspan=3, sticky="w", pady=(2, 8))
        r += 1
        ttk.Label(f, text="Thao tác chuột trên màn hình  →  nhân vật bay tới chỗ bấm và tung chiêu", style="H.TLabel"
                  ).grid(row=r, column=0, sticky="w", columnspan=4, pady=(6, 0))
        r += 1
        ttk.Label(f, text="Chế độ:").grid(row=r, column=0, sticky="w")
        self.smode = ttk.Combobox(f, state="readonly", width=34, values=[b for _, b in SCREEN_MODES])
        self.smode.grid(row=r, column=1, columnspan=2, sticky="w", padx=6)
        self.smode.bind("<<ComboboxSelected>>", lambda e: self.app.set_setting(
            "screen_mode", {b: k for k, b in SCREEN_MODES}.get(self.smode.get(), "desktop")))
        r += 1
        for k, lab in SCREEN_TRIGGERS:
            self._ctrl_row(f, r, k, lab, with_cmd=False, screen=True)
            r += 1
        ttk.Label(f, text="Desktop: bấm lên vùng trống / biểu tượng ngoài desktop, chuột vẫn hoạt động bình thường.\n"
                          "Mọi nơi: bấm ở bất kỳ đâu nhân vật cũng lao tới (chuột vẫn hoạt động bình thường với phần mềm).\n"
                          "Chế độ phím: giữ phím rồi bấm ở bất kỳ đâu; cú bấm đó bị giữ lại, không lọt xuống phần mềm bên dưới.",
                  style="Muted.TLabel", justify="left").grid(row=r, column=0, columnspan=4, sticky="w", pady=(2, 8))
        r += 1
        ttk.Label(f, text="Trạng thái theo sự kiện nhắc việc", style="H.TLabel").grid(row=r, column=0, sticky="w", columnspan=3)
        r += 1
        for k, lab in EVENTS:
            self._ctrl_row(f, r, k, lab, with_cmd=False)
            r += 1
        bf = ttk.Frame(f)
        bf.grid(row=r, column=0, columnspan=3, sticky="w", pady=10)
        ttk.Button(bf, text="Khôi phục mặc định", command=self.reset_triggers).pack(side="left")
        ttk.Label(bf, text="  Thay đổi có hiệu lực ngay.", foreground=C_MUTED).pack(side="left")

    def _act_values(self):
        return ["— Không —"] + [beh_label(n) for n in self.beh_names()]

    def _ctrl_row(self, f, r, key, lab, with_cmd, screen=False):
        ttk.Label(f, text=lab).grid(row=r, column=0, sticky="w", pady=2)
        a = ttk.Combobox(f, state="readonly", width=28, values=self._act_values())
        a.grid(row=r, column=1, sticky="w", padx=6)
        a.bind("<<ComboboxSelected>>", lambda e, k=key: self.on_ctrl(k))
        c = None
        if with_cmd:
            c = ttk.Combobox(f, state="readonly", width=24, values=[b for _, b in COMMANDS])
            c.grid(row=r, column=2, sticky="w", padx=6)
            c.bind("<<ComboboxSelected>>", lambda e, k=key: self.on_ctrl(k))
        if screen:
            def test(k=key):
                a = self.app.areas[0]
                self.app.gmouse.fire(k, random.randint(a[0] + 200, a[2] - 200), random.randint(a[1] + 200, a[3] - 150))
            ttk.Button(f, text="▶", width=3, style="Small.TButton", command=test).grid(row=r, column=3, padx=2)
        else:
            ttk.Button(f, text="▶", width=3, style="Small.TButton", command=lambda k=key: self.app.pet.trigger(k)).grid(row=r, column=3, padx=2)
        self.ctrl_rows[key] = (a, c)

    def fill_controls(self):
        tr = self.app.store.s.get("triggers") or {}
        self._drop_map = {"Rơi thường (bị ném xoay tròn)": ""}
        for n in self.app.pet.engine.drop_choices():
            self._drop_map[beh_label(n)] = n
        self.dropcb.config(values=list(self._drop_map))
        cur = self.app.store.s.get("drop_action", "VaCham_RoiHoDat")
        self.dropcb.set(next((k for k, v in self._drop_map.items() if v == cur), "Rơi thường (bị ném xoay tròn)"))
        self._wall_map = {"Bám luôn vào tường (kiểu cũ)": ""}
        for n in self.beh_names():
            self._wall_map[beh_label(n)] = n
        self.wallcb.config(values=list(self._wall_map))
        cw_ = self.app.store.s.get("wall_hit_action", "TrangThai_AnVa")
        self.wallcb.set(next((k for k, v in self._wall_map.items() if v == cw_), "Bám luôn vào tường (kiểu cũ)"))
        self.smode.set(dict(SCREEN_MODES).get(self.app.store.s.get("screen_mode", "desktop"), SCREEN_MODES[0][1]))
        names = self.beh_names()
        cmdl = dict(COMMANDS)
        for key, (a, c) in self.ctrl_rows.items():
            a.config(values=self._act_values())
            m = tr.get(key) or {}
            a.set(beh_label(m["act"]) if m.get("act") in names else "— Không —")
            if c is not None:
                c.set(cmdl.get(m.get("cmd", ""), "— Không —"))

    def on_ctrl(self, key):
        a, c = self.ctrl_rows[key]
        names = self.beh_names()
        lab2n = {beh_label(n): n for n in names}
        tr = dict(self.app.store.s.get("triggers") or {})
        m = dict(tr.get(key) or {})
        m["act"] = lab2n.get(a.get(), "")
        if c is not None:
            m["cmd"] = {b: k for k, b in COMMANDS}.get(c.get(), "")
        tr[key] = m
        self.app.set_setting("triggers", tr)
        self.refresh_beh()

    def reset_triggers(self):
        import copy
        self.app.set_setting("triggers", copy.deepcopy(DEFAULT_TRIGGERS))
        self.fill_controls()
        self.refresh_beh()

    # ── tab cài đặt ──
    def build_settings(self, nb):
        outer = ttk.Frame(nb)
        nb.add(outer, text="  Cài đặt  ")
        cv = tk.Canvas(outer, highlightthickness=0, bg=C_BG)
        sb = ttk.Scrollbar(outer, orient="vertical", command=cv.yview)
        f = ttk.Frame(cv, padding=12)
        f.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.create_window((0, 0), window=f, anchor="nw")
        cv.configure(yscrollcommand=sb.set)
        cv.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        cv.bind_all("<MouseWheel>", lambda e: cv.yview_scroll(int(-e.delta / 120), "units")
                    if str(e.widget).startswith(str(cv)) else None, add="+")
        cv.bind_all("<Button-4>", lambda e: cv.yview_scroll(-3, "units") if str(e.widget).startswith(str(cv)) else None, add="+")
        cv.bind_all("<Button-5>", lambda e: cv.yview_scroll(3, "units") if str(e.widget).startswith(str(cv)) else None, add="+")
        s = self.app.store.s
        self.svars = {}

        def chk(key, text, row, cmd=None):
            v = tk.BooleanVar(value=bool(s.get(key)))
            self.svars[key] = v
            ttk.Checkbutton(f, text=text, variable=v,
                            command=lambda: (self.app.set_setting(key, v.get()), cmd and cmd(v.get()))).grid(
                row=row, column=0, columnspan=3, sticky="w", pady=2)

        def num(key, text, row, lo, hi, inc=5):
            ttk.Label(f, text=text).grid(row=row, column=0, sticky="w", pady=2)
            sp = ttk.Spinbox(f, from_=lo, to=hi, increment=inc, width=6)
            sp.set(s.get(key))
            sp.grid(row=row, column=1, sticky="w")

            def upd(*_):
                try:
                    self.app.set_setting(key, int(sp.get()))
                except Exception:
                    pass
            sp.bind("<KeyRelease>", upd)
            sp.config(command=upd)

        num("break_minutes", "Nhắc nghỉ mắt sau mỗi (phút làm liên tục, 0 = tắt):", 0, 0, 240)
        num("pre_notice", "Báo trước khi đến giờ (phút, 0 = tắt):", 1, 0, 60, 1)
        ttk.Label(f, text="Giờ yên lặng (ngủ, không nói chuyện):").grid(row=2, column=0, sticky="w", pady=2)
        qf = ttk.Frame(f)
        qf.grid(row=2, column=1, columnspan=2, sticky="w")
        self.qs = ttk.Entry(qf, width=6)
        self.qs.insert(0, s.get("quiet_start"))
        self.qs.pack(side="left")
        ttk.Label(qf, text=" đến ").pack(side="left")
        self.qe = ttk.Entry(qf, width=6)
        self.qe.insert(0, s.get("quiet_end"))
        self.qe.pack(side="left")
        for e, k in ((self.qs, "quiet_start"), (self.qe, "quiet_end")):
            e.bind("<FocusOut>", lambda ev, e=e, k=k: re.fullmatch(r"\d{1,2}:\d{2}", e.get().strip()) and self.app.set_setting(k, e.get().strip()))
        chk("sound", "Phát âm thanh khi nhắc", 3)
        chk("talk", "Thỉnh thoảng nói chuyện / nhắc việc sắp tới", 4)
        chk("track_apps", "Tự học thói quen dùng ứng dụng (chỉ ghi tên chương trình + phút dùng, lưu trên máy này)", 5)
        chk("auto_adjust", "Tự động dời giờ nhắc theo giờ bạn thường làm (không cần hỏi)", 6)
        chk("autostart", "Khởi động cùng Windows", 7, cmd=lambda v: set_autostart(v))
        chk("hide_fullscreen", "Tự ẩn và dời nhắc khi trình chiếu / xem video / ứng dụng toàn màn hình", 8)
        bf = ttk.Frame(f)
        bf.grid(row=9, column=0, columnspan=3, sticky="w", pady=(12, 0))
        ttk.Button(bf, text="Mở thư mục dữ liệu", command=lambda: open_path(DATA_DIR)).pack(side="left", padx=3)
        ttk.Button(bf, text="Sao lưu...", command=self.backup).pack(side="left", padx=3)
        ttk.Button(bf, text="Khôi phục...", command=self.restore).pack(side="left", padx=3)
        ttk.Button(bf, text="Xoá dữ liệu tự học", command=self.clear_learn).pack(side="left", padx=3)
        help_ = ("Mặc định: Nhấp 1 lần = ra chiêu + xem việc sắp tới • Nhấp đúp = mở bảng này • Chuột phải = menu nhanh\n"
                 "(đổi tất cả ở tab Điều khiển) • Kéo thả để túm/ném • Ctrl + lăn chuột trên nhân vật = phóng to/thu nhỏ\n"
                 "Bấm 'Xong' / 'Bỏ qua' khi được nhắc và dùng 'Ghi nhận việc vừa làm' để chibi học thói quen của bạn.\n"
                 "Dữ liệu: " + DATA_FILE)
        ttk.Label(f, text=help_, foreground=C_MUTED, justify="left").grid(row=12, column=0, columnspan=3, sticky="w", pady=(16, 0))
        # ── hiệu ứng gõ phím ──
        kf = ttk.Frame(f)
        kf.grid(row=11, column=0, columnspan=3, sticky="we", pady=(14, 0))
        ttk.Label(kf, text="⚡  Hiệu ứng gõ phím (mọi phần mềm)", style="H.TLabel").grid(row=0, column=0, columnspan=4, sticky="w")
        self.kfx_v = tk.BooleanVar(value=s.get("key_fx", True))
        self.kpet_v = tk.BooleanVar(value=s.get("key_fx_pet", True))

        def kfx_toggle():
            self.app.set_setting("key_fx", self.kfx_v.get())
            self.app.gmouse.set_keyboard(self.kfx_v.get())
        ttk.Checkbutton(kf, text="Bật hiệu ứng khi gõ ký tự và khi xoá", variable=self.kfx_v,
                        command=kfx_toggle).grid(row=1, column=0, columnspan=2, sticky="w")
        ttk.Checkbutton(kf, text="Nhân vật phản ứng khi gõ / xoá liên tục (gán chiêu ở tab Điều khiển)",
                        variable=self.kpet_v, command=lambda: self.app.set_setting("key_fx_pet", self.kpet_v.get())
                        ).grid(row=2, column=0, columnspan=2, sticky="w")
        ttk.Label(kf, text="Cỡ hiệu ứng:").grid(row=3, column=0, sticky="w", pady=4)
        self.kfs_v = tk.DoubleVar(value=s.get("key_fx_size", 1.0))
        ksc = ttk.Scale(kf, from_=0.5, to=2.0, variable=self.kfs_v, length=200)
        ksc.grid(row=3, column=1, sticky="w", padx=6)
        ksc.bind("<ButtonRelease-1>", lambda e: self.app.set_setting("key_fx_size", round(self.kfs_v.get(), 2)))
        fxl = [b for _, b in FX_CHOICES]
        lab2k = {b: k for k, b in FX_CHOICES}
        ttk.Label(kf, text="Khi gõ ký tự:").grid(row=4, column=0, sticky="w", pady=3)
        self.fxt = ttk.Combobox(kf, state="readonly", width=30, values=fxl)
        self.fxt.set(dict(FX_CHOICES).get(s.get("key_fx_type", "bolt")))
        self.fxt.grid(row=4, column=1, sticky="w", padx=6)
        ttk.Label(kf, text="Khi xoá:").grid(row=5, column=0, sticky="w", pady=3)
        self.fxd = ttk.Combobox(kf, state="readonly", width=30, values=fxl)
        self.fxd.set(dict(FX_CHOICES).get(s.get("key_fx_del", "slash")))
        self.fxd.grid(row=5, column=1, sticky="w", padx=6)
        self.fxt.bind("<<ComboboxSelected>>", lambda e: (self.app.set_setting("key_fx_type", lab2k[self.fxt.get()]),
                                                         self.fx_preview_set(lab2k[self.fxt.get()])))
        self.fxd.bind("<<ComboboxSelected>>", lambda e: (self.app.set_setting("key_fx_del", lab2k[self.fxd.get()]),
                                                         self.fx_preview_set(lab2k[self.fxd.get()])))
        tb = ttk.Frame(kf)
        tb.grid(row=6, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Button(tb, text="⚡ Thử gõ trên màn hình", style="Small.TButton",
                   command=lambda: self._kfx_demo("T")).pack(side="left")
        ttk.Button(tb, text="✕ Thử xoá trên màn hình", style="Small.TButton",
                   command=lambda: self._kfx_demo("D")).pack(side="left", padx=6)
        ttk.Label(kf, text="App chỉ nhận biết 'vừa gõ' hay 'vừa xoá', không ghi lại phím nào. Tự tắt ở ô mật khẩu và khi "
                           "trình chiếu. Tắt mục này là gỡ hẳn chức năng bắt phím.", style="Muted.TLabel", wraplength=470,
                  justify="left").grid(row=7, column=0, columnspan=2, sticky="w")
        self.fxprev = tk.Canvas(kf, width=260, height=220, bg="#120d1c", highlightthickness=1, highlightbackground=C_ACC2)
        self.fxprev.grid(row=1, column=2, rowspan=7, padx=(18, 0), sticky="n")
        self._fxp = {"key": s.get("key_fx_type", "bolt"), "frames": [], "i": 0, "n": 0}
        self.fx_preview_set(self._fxp["key"])
        self.fx_preview_loop()

        # ── cập nhật ──
        uf = ttk.Frame(f)
        uf.grid(row=10, column=0, columnspan=3, sticky="we", pady=(16, 0))
        ttk.Label(uf, text="⟳  Cập nhật phần mềm", style="H.TLabel").grid(row=0, column=0, columnspan=4, sticky="w")
        ttk.Label(uf, text="Chế độ:").grid(row=1, column=0, sticky="w", pady=4)
        self.umode = ttk.Combobox(uf, state="readonly", width=40, values=[b for _, b in UPDATE_MODES])
        self.umode.set(dict(UPDATE_MODES).get(s.get("update_mode", "notify")))
        self.umode.grid(row=1, column=1, columnspan=3, sticky="w", padx=6)
        self.umode.bind("<<ComboboxSelected>>", lambda e: self.app.set_setting(
            "update_mode", {b: k for k, b in UPDATE_MODES}.get(self.umode.get(), "notify")))
        ub = ttk.Frame(uf)
        ub.grid(row=2, column=0, columnspan=4, sticky="w", pady=2)
        ttk.Button(ub, text="⟳ Cập nhật ngay (F5)", style="Accent.TButton",
                   command=lambda: self.app.updater.check(manual=True, install=True)).pack(side="left")
        ttk.Button(ub, text="Chỉ kiểm tra", command=lambda: self.app.updater.check(manual=True)).pack(side="left", padx=4)
        ttk.Button(ub, text="Cập nhật từ file .zip...", command=lambda: self.app.updater.from_file(self.win)).pack(side="left")
        ttk.Button(ub, text="Quay về bản trước", command=lambda: self.app.updater.rollback(self.win)).pack(side="left", padx=4)
        ttk.Button(ub, text="Trang GitHub", command=lambda: __import__("webbrowser").open(URL_PAGE)).pack(side="left")
        self.ustat = ttk.Label(uf, text=self.app.updater.status, style="Muted.TLabel")
        self.ustat.grid(row=3, column=0, columnspan=4, sticky="w")
        self.app.updater.on_status = lambda t: self.alive() and self.ustat.config(text=t)

    def fx_preview_set(self, key):
        self._fxp.update(key=key, frames=[], i=0)

    def fx_preview_loop(self):
        """Ô xem trước: phát lặp mẫu đang chọn trên nền tối, có dòng chữ giả làm chỗ gõ."""
        if not self.alive():
            return
        try:
            p = self._fxp
            if not p["frames"] or p["i"] >= len(p["frames"]) + 6:
                key = p["key"]
                if key == "random" or key not in FX_BY_KEY:
                    key = random.choice([e[0] for e in FX_EFFECTS])
                e = FX_BY_KEY[key]
                frames = e[2](150, random.randint(0, 99))
                p.update(frames=frames, i=0, anchor=e[3], name=e[1])
            cv = self.fxprev
            cv.delete("all")
            cv.create_text(130, 150, text="Nhắc việc|", fill="#cfc6e6", font=(FONT, 13))
            cv.create_text(130, 14, text=p.get("name", ""), fill=C_GOLD, font=(FONT, 9, "bold"))
            if p["i"] < len(p["frames"]):
                im = p["frames"][p["i"]]
                ax, ay = p["anchor"]
                self._fxp_img = ImageTk.PhotoImage(im)
                cv.create_image(178 - im.width * ax, 150 - im.height * ay, image=self._fxp_img, anchor="nw")
            p["i"] += 1
        except Exception:
            log_error()
        self.win.after(45, self.fx_preview_loop)

    def _kfx_demo(self, kind):
        x, y = self.win.winfo_pointerxy()
        s = self.app.store.s
        player = self.app.keyfx.bolt if kind == "T" else self.app.keyfx.slash
        key = s.get("key_fx_type", "bolt") if kind == "T" else s.get("key_fx_del", "slash")
        for i in range(4 if kind == "T" else 2):
            self.win.after(i * 220, lambda i=i: player.play(x - 60 + i * 40, y - 80, self.app.keyfx.size(), key))

    def backup(self):
        p = filedialog.asksaveasfilename(parent=self.win, defaultextension=".json",
                                         initialfile="chibi_backup_%s.json" % dt.date.today().strftime("%Y%m%d"),
                                         filetypes=[("JSON", "*.json")])
        if p:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(self.app.store.data, f, ensure_ascii=False, indent=1)
            messagebox.showinfo(APP_NAME, "Đã sao lưu.", parent=self.win)

    def restore(self):
        p = filedialog.askopenfilename(parent=self.win, filetypes=[("JSON", "*.json")])
        if not p:
            return
        try:
            with open(p, "r", encoding="utf-8") as f:
                d = json.load(f)
            assert isinstance(d.get("tasks"), list)
        except Exception:
            messagebox.showerror(APP_NAME, "File sao lưu không hợp lệ.", parent=self.win)
            return
        if messagebox.askyesno(APP_NAME, "Thay toàn bộ dữ liệu hiện tại bằng bản sao lưu?", parent=self.win):
            self.app.store.save()
            for k in self.app.store.data:
                if k in d:
                    self.app.store.data[k] = d[k]
            ss = dict(DEFAULT_SETTINGS)
            ss.update(self.app.store.data["settings"])
            self.app.store.data["settings"] = ss
            self.app.store.save()
            self.app.pet.apply_look()
            self.refresh(True)

    def clear_learn(self):
        if messagebox.askyesno(APP_NAME, "Xoá nhật ký, thống kê ứng dụng và các gợi ý đã bỏ qua?\n(Danh sách việc nhắc được giữ nguyên.)", parent=self.win):
            d = self.app.store.data
            d["log"], d["app_usage"], d["day_start"], d["ignored"] = [], {}, {}, {}
            self.app.store.save()
            self.app.learner.analyze()
            self.refresh()

    # ── làm mới ──
    def refresh(self, look=False):
        app = self.app
        st = app.store
        tiso = dt.date.today().isoformat()
        self._tlog = {}
        if self.banner.winfo_width() > 10:
            self.draw_banner()
        for e in st.data["log"]:           # chỉ mục nhật ký hôm nay, quét 1 lần cho mọi dòng
            if e.get("date") == tiso and e.get("task"):
                self._tlog.setdefault(e["task"], []).append(e)
        # việc
        sel = self.tv.selection()
        self.tv.delete(*self.tv.get_children())
        order = sorted(st.tasks, key=lambda t: (not t.get("enabled"), t["time"]))
        for t in order:
            tags = ("off",) if not t.get("enabled") else (("learned",) if t.get("source") == "learned" else ())
            self.tv.insert("", "end", iid=t["id"], tags=tags,
                           values=(t["time"], t["title"], repeat_desc(t), self.status(t),
                                   "Tự học" if t.get("source") == "learned" else "Bạn"))
        if sel and self.tv.exists(sel[0]):
            self.tv.selection_set(sel[0])
        # hôm nay
        today = dt.date.today()
        cnt = sum(1 for t in st.tasks if t.get("enabled") and occurs_on(t, today))
        done = sum(1 for t in st.tasks if t.get("done_date") == today.isoformat())
        self.today_lbl.config(text="%s, %s — %d việc, đã xong %d" % (
            ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"][today.weekday()],
            today.strftime("%d/%m/%Y"), cnt, done))
        self.log_tv.delete(*self.log_tv.get_children())
        kinds = {"done": "✓ Xong", "skip": "✕ Bỏ qua", "snooze": "⏰ Hoãn", "note": "✎ Tự ghi nhận", "break": "☕ Nghỉ mắt"}
        for e in reversed([e for e in st.data["log"] if e.get("date") == today.isoformat()]):
            k = kinds.get(e["kind"], e["kind"])
            if e["kind"] == "snooze":
                k += " %s'" % e.get("mins", "")
            self.log_tv.insert("", "end", values=(e["t"][11:16], k, e.get("title", "")))
        # tự học
        self.sg_tv.delete(*self.sg_tv.get_children())
        for sg in app.learner.suggestions:
            self.sg_tv.insert("", "end", iid=sg["key"], values=(sg["text"], sg["reason"]))
        self.stats.config(state="normal")
        self.stats.delete("1.0", "end")
        self.stats.insert("end", self.stats_text())
        self.stats.config(state="disabled")
        if look:
            st_ = self.app.store.s
            pk = self.app.pet.pack
            self.pk_name.config(text="Nhân vật: %s  (%d động tác)" % (pk.name, len(pk.user_behaviors())) if pk else "")
            self.scale_var.set(st_.get("scale", 1.0))
            self.scale_lbl.config(text="%.1fx" % float(st_.get("scale", 1.0)))
            self.name_e.delete(0, "end")
            self.name_e.insert(0, st_.get("pet_name", "Bi"))
            self.refresh_beh()
            self.fill_controls()

    def stats_text(self):
        st = self.app.store
        lines = []
        d = dt.date.today().isoformat()
        u = st.data["app_usage"].get(d, {})
        if u:
            top = sorted(u.items(), key=lambda x: -x[1].get("minutes", 0))[:8]
            lines.append("Ứng dụng dùng nhiều hôm nay:")
            for exe, v in top:
                lines.append("   • %-18s %s (mở lúc %s)" % (app_name(exe), fmt_dur(v.get("minutes", 0)), v.get("first")))
        elif st.s.get("track_apps") and IS_WIN:
            lines.append("Đang thu thập thói quen dùng ứng dụng...")
        starts = [hm2m(v) for k, v in st.data["day_start"].items() if k >= (dt.date.today() - dt.timedelta(days=14)).isoformat()]
        if starts:
            lines.append("\nGiờ bắt đầu làm việc trung bình (14 ngày): %s" % m2hm(statistics.median(starts)))
        lines.append("Đang làm liên tục: %s" % fmt_dur(self.app.active_secs / 60))
        cut = (dt.date.today() - dt.timedelta(days=7)).isoformat()
        week = [e for e in st.data["log"] if e.get("date", "") >= cut]
        dn = sum(1 for e in week if e["kind"] == "done")
        sk = sum(1 for e in week if e["kind"] == "skip")
        sz = sum(1 for e in week if e["kind"] == "snooze")
        lines.append("\n7 ngày qua: %d việc xong • %d bỏ qua • %d lần hoãn • %d lần nghỉ mắt" % (
            dn, sk, sz, sum(1 for e in week if e["kind"] == "break")))
        if dn + sk:
            lines.append("Tỉ lệ hoàn thành: %d%%" % (100 * dn // (dn + sk)))
        lines.append("\nCách %s học: ghi lại lúc bạn bấm Xong/Bỏ qua/Hoãn và các việc bạn tự ghi nhận;"
                     " khi thấy lặp lại đủ nhiều (≥3–4 lần, giờ giấc ổn định) sẽ đưa ra gợi ý ở trên." % self.app.name())
        return "\n".join(lines)


# ───────────────────────── Hệ thống ─────────────────────────
def open_path(p):
    try:
        if IS_WIN:
            os.startfile(p)
        else:
            import subprocess
            subprocess.Popen(["xdg-open", p])
    except Exception:
        log_error()


def startup_file():
    return os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup", "ChibiNhacViec.vbs")


def set_autostart(on):
    if not IS_WIN:
        return
    p = startup_file()
    try:
        if on:
            exe = sys.executable
            cand = os.path.join(os.path.dirname(exe), "pythonw.exe")
            if os.path.exists(cand):
                exe = cand
            script = os.path.abspath(sys.argv[0])
            vbs = ('Set sh = CreateObject("WScript.Shell")\r\n'
                   'sh.CurrentDirectory = "%s"\r\n'
                   'sh.Run """%s"" ""%s""", 0, False\r\n') % (os.path.dirname(script), exe, script)
            with open(p, "w", encoding="utf-16") as f:
                f.write(vbs)
        elif os.path.exists(p):
            os.remove(p)
    except Exception:
        log_error()



# ───────────────────────── Cập nhật phiên bản từ GitHub ─────────────────────────
UPDATE_REPO = "HP-wukoong/NHAN_VAT_CHIBI"
UPDATE_BRANCH = "main"
URL_VERSION = "https://raw.githubusercontent.com/%s/%s/version.json" % (UPDATE_REPO, UPDATE_BRANCH)
URL_ZIP = "https://github.com/%s/archive/refs/heads/%s.zip" % (UPDATE_REPO, UPDATE_BRANCH)
URL_PAGE = "https://github.com/%s" % UPDATE_REPO
INSTALL_ITEMS = ["ChibiNhacViec.pyw", "ChayChibi.bat", "README.md", "version.json", "NhanVat", "tests"]
UPDATE_MODES = [("notify", "Báo khi có bản mới (hỏi trước khi cập nhật)"), ("auto", "Tự động cập nhật"),
                ("off", "Tắt kiểm tra tự động")]
BACKUP_DIR = os.path.join(DATA_DIR, "backup")


def ver_tuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", str(v))[:4]) or (0,)


class Updater:
    def __init__(self, app):
        self.app = app
        self.busy = False
        self.status = "Phiên bản hiện tại: v%s" % APP_VER
        self.on_status = None

    def set_status(self, txt):
        self.status = txt
        if self.on_status:
            try:
                self.on_status(txt)
            except Exception:
                pass

    def _ui(self, fn, *a):
        self.app.root.after(0, lambda: fn(*a))

    # ── kiểm tra ──
    def check(self, manual=False, install=False):
        """manual: người dùng bấm (báo cả khi đã mới nhất). install: có bản mới thì cài luôn (F5)."""
        if self.busy:
            return
        self.busy = True
        self.set_status("Đang kiểm tra bản mới trên GitHub...")
        threading.Thread(target=self._check, args=(manual, install), daemon=True).start()

    def _fetch(self, url, timeout=20):
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "ChibiNhacViec/" + APP_VER, "Cache-Control": "no-cache"})
        return urllib.request.urlopen(req, timeout=timeout)

    def _check(self, manual, install):
        try:
            with self._fetch(URL_VERSION + "?t=%d" % int(time_now())) as r:
                info = json.loads(r.read().decode("utf-8-sig"))
            self._ui(self._checked, info, manual, install)
        except Exception as e:
            self._ui(self._fail, "Không kết nối được GitHub (%s). Thử lại sau hoặc cập nhật từ file .zip." % e.__class__.__name__, manual)

    def _fail(self, msg, manual):
        self.busy = False
        self.set_status(msg)
        if manual:
            self.app.say("Chưa cập nhật được", msg, timeout=8)

    def _checked(self, info, manual, install):
        self.busy = False
        self.app.store.s["last_update_check"] = iso(now())
        latest = str(info.get("version", "0"))
        if ver_tuple(latest) <= ver_tuple(APP_VER):
            self.set_status("Đang dùng bản mới nhất v%s ✓" % APP_VER)
            if manual:
                self.app.say("Đang dùng bản mới nhất ✓", "v%s" % APP_VER, timeout=5)
            return
        notes = info.get("notes") or []
        if isinstance(notes, str):
            notes = [notes]
        self.set_status("Có bản mới v%s (đang dùng v%s)" % (latest, APP_VER))
        if install or self.app.store.s.get("update_mode", "notify") == "auto":
            self.download_install(info)
            return
        txt = "\n".join("• " + n for n in notes[:6]) or "Có cải tiến và sửa lỗi."
        self.app.bubble.push({
            "kind": "suggest", "key": "update", "title": "⟳ Có bản mới v%s!" % latest, "title_fg": C_GOLD,
            "edge": C_GOLD, "text": txt,
            "buttons": [("Cập nhật ngay", lambda: self.download_install(info), C_ACC), ("Để sau", None, "#4a4060")]})

    # ── tải và cài ──
    def download_install(self, info=None):
        if self.busy:
            return
        self.busy = True
        self.set_status("Đang tải bản mới...")
        threading.Thread(target=self._download, daemon=True).start()

    def _download(self):
        import tempfile
        try:
            path = os.path.join(tempfile.gettempdir(), "ChibiNhacViec_update.zip")
            with self._fetch(URL_ZIP, timeout=60) as r, open(path, "wb") as f:
                total = int(r.headers.get("Content-Length") or 0)
                got = 0
                while True:
                    b = r.read(256 * 1024)
                    if not b:
                        break
                    f.write(b)
                    got += len(b)
                    self._ui(self.set_status, "Đang tải... %.1f MB%s" % (got / 1048576.0,
                                                                          (" / %.1f MB" % (total / 1048576.0)) if total else ""))
            ver = self.install_zip(path)
            self._ui(self._installed, ver)
        except Exception as e:
            log_error()
            self._ui(self._fail, "Cập nhật thất bại: %s" % e, True)

    def install_zip(self, path):
        """Kiểm tra gói, sao lưu bản đang dùng rồi chép đè. Trả về số phiên bản mới. Chạy được trong luồng phụ."""
        import zipfile
        import shutil
        import tempfile
        with zipfile.ZipFile(path) as z:
            cands = [n for n in z.namelist() if n.replace("\\", "/").endswith("ChibiNhacViec.pyw")]
            if not cands:
                raise ValueError("file .zip không có ChibiNhacViec.pyw")
            main_name = min(cands, key=len)
            src = z.read(main_name).decode("utf-8")
            compile(src, "ChibiNhacViec.pyw", "exec")          # file hỏng / tải dở thì dừng, không đụng bản đang chạy
            m = re.search(r'^APP_VER\s*=\s*"([^"]+)"', src, re.M)
            new_ver = m.group(1) if m else "?"
            tmp = tempfile.mkdtemp(prefix="chibi_upd_")
            z.extractall(tmp)
        root = os.path.join(tmp, os.path.dirname(main_name))
        # sao lưu bản đang dùng (giữ 3 bản gần nhất)
        bdir = os.path.join(BACKUP_DIR, "v%s_%s" % (APP_VER, now().strftime("%Y%m%d_%H%M%S")))
        os.makedirs(bdir, exist_ok=True)
        for it in ("ChibiNhacViec.pyw", "ChayChibi.bat", "version.json"):
            p = os.path.join(BASE_DIR, it)
            if os.path.exists(p):
                shutil.copy2(p, os.path.join(bdir, it))
        olds = sorted(d for d in os.listdir(BACKUP_DIR) if os.path.isdir(os.path.join(BACKUP_DIR, d)))
        for d in olds[:-3]:
            shutil.rmtree(os.path.join(BACKUP_DIR, d), ignore_errors=True)
        for it in INSTALL_ITEMS:
            sp = os.path.join(root, it)
            dp = os.path.join(BASE_DIR, it)
            if os.path.isdir(sp):
                shutil.copytree(sp, dp, dirs_exist_ok=True)
            elif os.path.isfile(sp):
                shutil.copy2(sp, dp + ".new")
                os.replace(dp + ".new", dp)                      # thay nguyên khối, không để file dở dang
        shutil.rmtree(tmp, ignore_errors=True)
        return new_ver

    def _installed(self, ver):
        self.busy = False
        self.set_status("Đã cài v%s – đang khởi động lại..." % ver)
        self.app.store.s["just_updated"] = ver
        self.app.say("Đã cập nhật lên v%s!" % ver, "Mình khởi động lại chút nhé...", timeout=3)
        self.app.root.after(1800, self.restart)

    def from_file(self, parent=None):
        p = filedialog.askopenfilename(parent=parent, title="Chọn gói cập nhật (.zip)",
                                       filetypes=[("Gói cập nhật", "*.zip")])
        if not p:
            return
        try:
            ver = self.install_zip(p)
        except Exception as e:
            log_error()
            messagebox.showerror(APP_NAME, "Không cài được gói này:\n%s" % e, parent=parent)
            return
        self._installed(ver)

    def rollback(self, parent=None):
        import shutil
        bk = sorted(d for d in os.listdir(BACKUP_DIR)) if os.path.isdir(BACKUP_DIR) else []
        if not bk:
            messagebox.showinfo(APP_NAME, "Chưa có bản sao lưu nào.", parent=parent)
            return
        last = bk[-1]
        if not messagebox.askyesno(APP_NAME, "Quay về bản trước (%s)?" % last.split("_")[0], parent=parent):
            return
        for it in os.listdir(os.path.join(BACKUP_DIR, last)):
            shutil.copy2(os.path.join(BACKUP_DIR, last, it), os.path.join(BASE_DIR, it))
        shutil.rmtree(os.path.join(BACKUP_DIR, last), ignore_errors=True)
        self.app.store.s["update_mode"] = "notify" if self.app.store.s.get("update_mode") == "auto" else \
            self.app.store.s.get("update_mode")
        self.restart()

    def restart(self):
        import subprocess
        app = self.app
        try:
            app.store.s["pos"] = app.pet.anchor_screen()
            app.store.save()
            app.gmouse.stop()
            App.server.close()
        except Exception:
            log_error()
        exe = sys.executable
        if IS_WIN:
            w = os.path.join(os.path.dirname(exe), "pythonw.exe")
            if os.path.exists(w):
                exe = w
        try:
            subprocess.Popen([exe, os.path.abspath(sys.argv[0]), "--restart"], cwd=BASE_DIR,
                             close_fds=True, creationflags=0x00000008 if IS_WIN else 0)   # DETACHED_PROCESS
        except Exception:
            log_error()
        app.root.destroy()


def main():
    # chống chạy 2 lần: nếu đã chạy thì gọi bản cũ mở bảng quản lý
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    bound = False
    if "--restart" in sys.argv:              # khởi động lại sau cập nhật: chờ bản cũ nhả cổng (tối đa 15 giây)
        import time as _t
        for _ in range(60):
            try:
                srv.bind(("127.0.0.1", PORT))
                bound = True
                break
            except OSError:
                _t.sleep(0.25)
    try:
        if not bound:
            srv.bind(("127.0.0.1", PORT))
        srv.listen(2)
    except OSError:
        try:
            c = socket.create_connection(("127.0.0.1", PORT), timeout=2)
            c.close()
        except Exception:
            pass
        return
    App.server = srv
    app = App()
    if "--test" in sys.argv:
        app.root.after(int(sys.argv[sys.argv.index("--test") + 1]) * 1000, app.quit)
    app.root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log_error()
        try:
            r = tk.Tk()
            r.withdraw()
            messagebox.showerror(APP_NAME, "Có lỗi khi khởi động. Xem file:\n" + ERR_FILE)
        except Exception:
            pass
