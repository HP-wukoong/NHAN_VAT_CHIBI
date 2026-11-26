# -*- coding: utf-8 -*-
"""
CHIBI NHẮC VIỆC  v3.0
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
import ctypes                      # dùng cả cho cấu trúc COM khai báo ở cấp module
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
APP_VER = "3.10"
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


def log_error_msg(msg):
    try:
        with open(ERR_FILE, "a", encoding="utf-8") as f:
            f.write("\n[%s] %s\n" % (dt.datetime.now().isoformat(timespec="seconds"), msg))
    except Exception:
        pass


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
    "key_fx": True, "key_fx_pet": True, "key_fx_size": 1.0, "key_fx_alpha": 1.0, "key_fx_speed": 1.0, "key_fx_type": "bolt", "key_fx_del": "slash", "key_fx_autosize": True,
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
        # mẫu hiệu ứng gõ phím đã bỏ ở bản mới -> về mặc định
        for k, dflt in (("key_fx_type", "bolt"), ("key_fx_del", "slash")):
            v = FX_ALIAS.get(s.get(k), s.get(k))
            s[k] = v if (v in FX_BY_KEY or v in ("random", "random_thunder")) else dflt

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
NHANVAT_DIR = os.path.join(BASE_DIR, "NhanVat")
BUILTIN_PACK = os.path.join(NHANVAT_DIR, "NhanVatAoDen")
PACKS_DIR = os.path.join(DATA_DIR, "packs")
PACK_META = {}                    # thông tin riêng của nhân vật đang dùng (conf/chibi.json): nhãn, nhóm, gán mặc định
PROFILE_KEYS = ("triggers", "drop_action", "wall_hit_action", "free", "pet_name")


def pack_meta(path):
    """Đọc conf/chibi.json của bộ nhân vật (nếu có)."""
    for sub in ("conf", ""):
        f = os.path.join(path or BUILTIN_PACK, sub, "chibi.json")
        if os.path.isfile(f):
            try:
                with open(f, encoding="utf-8") as fh:
                    m = json.load(fh)
                return m if isinstance(m, dict) else {}
            except Exception:
                log_error()
    return {}


def pack_key(ref):
    return ref or "builtin:NhanVatAoDen"


def pack_defaults(meta, name=""):
    """Bộ gán chuột / sự kiện / thả rơi mặc định của một nhân vật."""
    import copy
    tr = copy.deepcopy(DEFAULT_TRIGGERS)
    if meta.get("triggers"):
        tr = {k: dict(v) for k, v in DEFAULT_TRIGGERS.items()}
        for k in tr:
            tr[k]["act"] = ""
        for k, v in meta["triggers"].items():
            tr[k] = dict(v)
    return {"triggers": tr, "drop_action": meta.get("drop_action", "VaCham_RoiHoDat"),
            "wall_hit_action": meta.get("wall_hit_action", "TrangThai_AnVa"), "free": {},
            "pet_name": meta.get("name") or name or "Áo Đen"}


def available_packs():
    """[(mã lưu trong cài đặt, tên hiển thị)]: nhân vật có sẵn trong NhanVat/ + bộ Shimeji đã nạp thêm."""
    out = [("", "Áo Đen")]
    try:
        for d in sorted(os.listdir(NHANVAT_DIR)):
            full = os.path.join(NHANVAT_DIR, d)
            if d == "NhanVatAoDen" or not os.path.isdir(os.path.join(full, "conf")):
                continue
            out.append(("builtin:" + d, pack_meta(full).get("name") or d))
    except Exception:
        pass
    try:
        for d in sorted(os.listdir(PACKS_DIR)):
            full = os.path.join(PACKS_DIR, d)
            if os.path.isdir(full):
                out.append((pack_ref(full), (pack_meta(full).get("name") or d) + " (đã nạp)"))
    except Exception:
        pass
    return out


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
    if ref.startswith("builtin:"):
        return os.path.join(NHANVAT_DIR, ref[8:])
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
    lab = PACK_META.get("labels") or {}
    if n in lab:
        return lab[n]
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
    g = PACK_META.get("groups") or {}
    if p in g:
        return g[p]
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
        self.meta = pack_meta(self.img_dir)
        if self.meta.get("name"):
            self.name = self.meta["name"]
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
        if (n in ("DiChuyen_BamVachTrai", "DiChuyen_BamVachPhai", "TrangThai_BiTreo")
                or n in (self.pack.meta.get("climb_behaviors") or ())) and not s.get("climb", True):
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
        # ưu tiên tư thế "lao vút" (Áo Đen: hl_hover; nhân vật khác khai báo fly_prefix trong chibi.json)
        pre = (self.pack.meta.get("fly_prefix") or "hl_hover").lower()
        hov = []
        seen = set()
        for sp in self.pack.actions.values():
            for p in sp.poses:
                if p.img.lower().startswith(pre) and p.img not in seen:
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

    def update(self, x, y, w, h, bgra, alpha=255):
        self.blend.alpha = max(0, min(255, int(alpha)))              # độ trong suốt chung của cả cửa sổ
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
                            self.q.put(("K", kind, k.vkCode))
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
        try:
            self.app.keyfx.poll(self.q.empty())
        except Exception:
            log_error()
        while True:
            try:
                ev = self.q.get_nowait()
            except Exception:
                break
            if self.app.hidden or self.app.fs_hidden:
                continue
            k = ev[0]
            if k == "K":
                self.app.keyfx.on_key(ev[1], ev[2] if len(ev) > 2 else None)
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
    """(vị trí con trỏ nhập trên màn hình hoặc None, đang ở ô mật khẩu?, chiều cao con trỏ = cỡ chữ hoặc None)"""
    if not IS_WIN:
        return None, False, None
    try:
        u32 = ctypes.windll.user32

        class GTI(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD), ("hwndActive", wintypes.HWND),
                        ("hwndFocus", wintypes.HWND), ("hwndCapture", wintypes.HWND), ("hwndMenuOwner", wintypes.HWND),
                        ("hwndMoveSize", wintypes.HWND), ("hwndCaret", wintypes.HWND), ("rcCaret", wintypes.RECT)]
        fg = u32.GetForegroundWindow()
        if not fg:
            return None, False, None
        tid = u32.GetWindowThreadProcessId(fg, None)
        gi = GTI()
        gi.cbSize = ctypes.sizeof(GTI)
        if not u32.GetGUIThreadInfo(tid, ctypes.byref(gi)):
            return None, False, None
        pw = False
        if gi.hwndFocus:
            cls = _class_name(gi.hwndFocus).lower()
            if "edit" in cls and u32.GetWindowLongW(gi.hwndFocus, -16) & 0x20:     # ES_PASSWORD
                pw = True
        if gi.hwndCaret:
            r = gi.rcCaret
            pt = wintypes.POINT(r.left, (r.top + r.bottom) // 2)
            u32.ClientToScreen(gi.hwndCaret, ctypes.byref(pt))
            return (pt.x, pt.y), pw, max(0, r.bottom - r.top)
        return None, pw, None
    except Exception:
        return None, False, None


# ── Tìm vị trí con trỏ nhập ở MỌI phần mềm: UI Automation (Chrome, Edge, Word, app mới), MSAA (Electron/Zalo) ──
def _release(p):
    if p:
        try:
            vtbl = ctypes.cast(p, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
            ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtbl[2])(p)
        except Exception:
            pass


def _guid(s):
    class GUID(ctypes.Structure):
        _fields_ = [("a", ctypes.c_ulong), ("b", ctypes.c_ushort), ("c", ctypes.c_ushort), ("d", ctypes.c_ubyte * 8)]
    h = s.strip("{}").replace("-", "")
    g = GUID(int(h[0:8], 16), int(h[8:12], 16), int(h[12:16], 16))
    for i in range(8):
        g.d[i] = int(h[16 + i * 2:18 + i * 2], 16)
    return g


class _VARIANT(ctypes.Structure):
    _fields_ = [("vt", ctypes.c_ushort), ("r1", ctypes.c_ushort), ("r2", ctypes.c_ushort), ("r3", ctypes.c_ushort),
                ("v1", ctypes.c_void_p), ("v2", ctypes.c_void_p)]


def _vcall(ptr, index, argtypes, args, restype=ctypes.c_long):
    vtbl = ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    fn = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)(vtbl[index])
    return fn(ptr, *args)


def _rects_from_safearray(psa):
    oa = ctypes.windll.oleaut32
    out = []
    if not psa:
        return out
    try:
        ub = ctypes.c_long()
        oa.SafeArrayGetUBound(psa, 1, ctypes.byref(ub))
        n = ub.value + 1
        data = ctypes.c_void_p()
        if n >= 4 and oa.SafeArrayAccessData(psa, ctypes.byref(data)) == 0:
            arr = ctypes.cast(data, ctypes.POINTER(ctypes.c_double))
            vals = [arr[i] for i in range(n)]
            oa.SafeArrayUnaccessData(psa)
            for i in range(0, n - 3, 4):
                out.append(tuple(vals[i:i + 4]))
    finally:
        oa.SafeArrayDestroy(psa)
    return out


class _CaretCore:
    """Phần gọi UI Automation / MSAA. Chỉ chạy trong TIẾN TRÌNH PHỤ (--caret-helper):
    lỡ lệnh COM làm sập thì chỉ tiến trình phụ chết, chibi vẫn chạy."""
    IID_IAccessible = "{618736E0-3C3D-11CF-810C-00AA00389B71}"
    CLSID_UIA = "{FF48DBA4-60EF-4201-AA87-54103EEF594E}"
    IID_UIA = "{30CBE57D-D9D0-452A-AB13-7AC5AC4825EE}"
    IID_TP2 = "{506A921A-FCC9-409F-B23B-37EB74106872}"
    IID_TP = "{32EBA289-3583-42C9-9C59-3B6D9A1E9B6A}"

    def __init__(self):
        self.uia = None
        try:
            ctypes.windll.ole32.CoInitializeEx(None, 0)       # COINIT_MULTITHREADED
            p = ctypes.c_void_p()
            if ctypes.windll.ole32.CoCreateInstance(ctypes.byref(_guid(self.CLSID_UIA)), None, 1,
                                                    ctypes.byref(_guid(self.IID_UIA)), ctypes.byref(p)) == 0:
                self.uia = p
        except Exception:
            pass

    def find(self):
        pw = False
        if self.uia:
            pos, pw = self._uia()
            if pw:
                return None, True, "UIA"
            if pos:
                return pos, False, "UI Automation"
        pos = self._msaa()
        if pos:
            return pos, pw, "MSAA"
        return None, pw, ""

    def _uia(self):
        el = ctypes.c_void_p()
        if _vcall(self.uia, 8, [ctypes.POINTER(ctypes.c_void_p)], [ctypes.byref(el)]) != 0 or not el:
            return None, False
        try:
            v = _VARIANT()
            pw = False
            if _vcall(el, 10, [ctypes.c_int, ctypes.POINTER(_VARIANT)], [30019, ctypes.byref(v)]) == 0:   # IsPassword
                pw = v.vt == 11 and (ctypes.c_short(v.v1 or 0).value != 0)
            if pw:
                return None, True
            for pid, iid in ((10024, self.IID_TP2), (10014, self.IID_TP)):
                unk = ctypes.c_void_p()
                if _vcall(el, 16, [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)], [pid, ctypes.byref(unk)]) != 0 or not unk:
                    continue
                tp = ctypes.c_void_p()
                try:
                    _vcall(unk, 0, [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)],
                           [ctypes.byref(_guid(iid)), ctypes.byref(tp)])
                finally:
                    _release(unk)
                if not tp:
                    continue
                try:
                    rng = ctypes.c_void_p()
                    if pid == 10024:
                        active = ctypes.c_int()
                        _vcall(tp, 10, [ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_void_p)],
                               [ctypes.byref(active), ctypes.byref(rng)])
                    else:
                        arr = ctypes.c_void_p()
                        if _vcall(tp, 5, [ctypes.POINTER(ctypes.c_void_p)], [ctypes.byref(arr)]) == 0 and arr:
                            n = ctypes.c_int()
                            _vcall(arr, 3, [ctypes.POINTER(ctypes.c_int)], [ctypes.byref(n)])
                            if n.value > 0:
                                _vcall(arr, 4, [ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)], [0, ctypes.byref(rng)])
                            _release(arr)
                    if rng:
                        try:
                            pos = self._range_pos(rng)
                        finally:
                            _release(rng)
                        if pos:
                            return pos, False
                finally:
                    _release(tp)
            return None, False
        finally:
            _release(el)

    def _range_pos(self, rng):
        psa = ctypes.c_void_p()
        _vcall(rng, 10, [ctypes.POINTER(ctypes.c_void_p)], [ctypes.byref(psa)])
        rects = _rects_from_safearray(psa)
        if not rects:                                      # con trỏ = khoảng rỗng -> nới ra 1 ký tự để lấy toạ độ
            _vcall(rng, 6, [ctypes.c_int], [0])
            psa = ctypes.c_void_p()
            _vcall(rng, 10, [ctypes.POINTER(ctypes.c_void_p)], [ctypes.byref(psa)])
            rects = _rects_from_safearray(psa)
        rects = [r for r in rects if r[3] > 0]
        if not rects:
            return None
        l, t, w, h = rects[-1]
        return int(l + w), int(t + h / 2), int(h)

    def _msaa(self):
        u32 = ctypes.windll.user32
        fg = u32.GetForegroundWindow()
        if not fg:
            return None
        tid = u32.GetWindowThreadProcessId(fg, None)

        class GTI(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD), ("hwndActive", wintypes.HWND),
                        ("hwndFocus", wintypes.HWND), ("hwndCapture", wintypes.HWND), ("hwndMenuOwner", wintypes.HWND),
                        ("hwndMoveSize", wintypes.HWND), ("hwndCaret", wintypes.HWND), ("rcCaret", wintypes.RECT)]
        gi = GTI()
        gi.cbSize = ctypes.sizeof(GTI)
        hwnd = fg
        if u32.GetGUIThreadInfo(tid, ctypes.byref(gi)) and gi.hwndFocus:
            hwnd = gi.hwndFocus
        acc = ctypes.c_void_p()
        oacc = ctypes.windll.oleacc
        oacc.AccessibleObjectFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p,
                                                    ctypes.POINTER(ctypes.c_void_p)]
        if oacc.AccessibleObjectFromWindow(hwnd, 0xFFFFFFF8, ctypes.byref(_guid(self.IID_IAccessible)),
                                           ctypes.byref(acc)) != 0 or not acc:          # OBJID_CARET
            return None
        try:
            l, t, w, h = ctypes.c_long(), ctypes.c_long(), ctypes.c_long(), ctypes.c_long()
            child = _VARIANT()
            child.vt = 3                                    # VT_I4, CHILDID_SELF = 0
            hr = _vcall(acc, 22, [ctypes.POINTER(ctypes.c_long)] * 4 + [_VARIANT],
                        [ctypes.byref(l), ctypes.byref(t), ctypes.byref(w), ctypes.byref(h), child])
            if hr == 0 and (l.value or t.value) and h.value > 0:
                return l.value + w.value, t.value + h.value // 2, h.value
        finally:
            _release(acc)
        return None




def caret_helper_main():
    """Tiến trình phụ: đọc mã yêu cầu từ stdin, trả 'mã x y mậtkhẩu cách' ra stdout. Thoát khi app chính đóng."""
    core = _CaretCore()
    out = sys.stdout
    for line in sys.stdin:
        rid = line.strip()
        if not rid:
            continue
        try:
            pos, pw, how = core.find()
        except Exception:
            pos, pw, how = None, False, ""
        x, y, ch = pos if pos else (-99999, -99999, 0)
        out.write("%s %d %d %d %s %d\n" % (rid, x, y, 1 if pw else 0, how.replace(" ", "_") or "-", ch))
        out.flush()


class CaretFinder:
    """Hỏi tiến trình phụ vị trí con trỏ nhập. Tiến trình phụ chỉ khởi động khi cần, sập thì tự mở lại (tối đa 3 lần)."""

    def __init__(self):
        import queue
        self.results = queue.Queue()
        self.proc = None
        self.crashes = 0
        self.uia = None
        self.lock = threading.Lock()

    def available(self):
        return IS_WIN and self.crashes < 3

    def _spawn(self):
        import subprocess
        exe = sys.executable
        con = os.path.join(os.path.dirname(exe), "python.exe")
        if os.path.exists(con):
            exe = con                       # python.exe + CREATE_NO_WINDOW: có ống stdin/stdout, không hiện cửa sổ
        self.proc = subprocess.Popen([exe, os.path.abspath(sys.argv[0]), "--caret-helper"],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                     creationflags=0x08000000 if IS_WIN else 0, cwd=BASE_DIR)
        threading.Thread(target=self._reader, args=(self.proc,), daemon=True).start()

    def _reader(self, proc):
        try:
            for raw in proc.stdout:
                parts = raw.decode("utf-8", "replace").split()
                if len(parts) >= 5:
                    x, y = int(parts[1]), int(parts[2])
                    pos = None if x == -99999 else (x, y)
                    how = parts[4].replace("_", " ")
                    ch = int(parts[5]) if len(parts) > 5 and int(parts[5]) > 0 else None
                    self.results.put((int(parts[0]), pos, parts[3] == "1", "" if how == "-" else how, ch))
        except Exception:
            pass
        with self.lock:
            if self.proc is proc:
                self.proc = None
                self.crashes += 1           # tiến trình phụ chết bất thường
                if self.crashes >= 3:
                    log_error_msg("Tìm con trỏ nhập (UI Automation/MSAA) lỗi 3 lần – chuyển sang hiện hiệu ứng cạnh chuột.")

    def request(self, rid):
        if not self.available():
            return
        try:
            with self.lock:
                if self.proc is None or self.proc.poll() is not None:
                    self._spawn()
                p = self.proc
            p.stdin.write(("%d\n" % rid).encode())
            p.stdin.flush()
        except Exception:
            log_error()

    def stop(self):
        with self.lock:
            p, self.proc = self.proc, None
        if p:
            try:
                p.kill()
            except Exception:
                pass


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


def _horror_skull(r, jaw, al, seed=0):
    """Đầu lâu kim loại bạc kinh dị: hốc mắt sâu, nứt sọ, nanh dài. Vẽ phóng 4 lần rồi thu nhỏ cho mịn."""
    from PIL import ImageDraw, ImageFilter
    rnd = random.Random(seed)
    k = 4
    R = r * k
    W, H = int(R * 2.3), int(R * 3.1)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx, cy = W / 2.0, R * 1.05
    silver, mid, dark = (205, 210, 220), (130, 135, 148), (35, 35, 42)
    # sọ + gò má
    d.ellipse((cx - R, cy - R * 1.0, cx + R, cy + R * 0.85), fill=mid + (255,))
    d.polygon([(cx - R * 0.95, cy + R * 0.1), (cx - R * 0.75, cy + R * 0.95), (cx + R * 0.75, cy + R * 0.95),
               (cx + R * 0.95, cy + R * 0.1)], fill=mid + (255,))
    d.ellipse((cx - R * 0.85, cy - R * 0.95, cx + R * 0.7, cy + R * 0.55), fill=silver + (255,))   # mảng sáng kim loại
    # hàm dưới (há theo jaw 0..1)
    jy = cy + R * 0.95 + jaw * R * 0.55
    d.polygon([(cx - R * 0.72, cy + R * 0.7), (cx - R * 0.6, jy + R * 0.45), (cx, jy + R * 0.62),
               (cx + R * 0.6, jy + R * 0.45), (cx + R * 0.72, cy + R * 0.7)], fill=mid + (255,))
    # khoang miệng tối
    d.polygon([(cx - R * 0.62, cy + R * 0.78), (cx + R * 0.62, cy + R * 0.78), (cx + R * 0.5, jy + R * 0.3),
               (cx - R * 0.5, jy + R * 0.3)], fill=(8, 6, 10, 255))
    # nanh trên (dài, chĩa xuống) và nanh dưới (chĩa lên)
    n = 7
    for i in range(n):
        x = cx - R * 0.55 + i * R * 1.1 / (n - 1)
        L = R * (0.42 if i in (1, 5) else 0.28) * (1.15 if i in (0, 6) else 1)
        d.polygon([(x - R * 0.075, cy + R * 0.76), (x + R * 0.075, cy + R * 0.76), (x + R * 0.01, cy + R * 0.76 + L)],
                  fill=(235, 238, 245, 255), outline=(70, 72, 80, 255))
        L2 = R * (0.36 if i in (2, 4) else 0.24)
        d.polygon([(x - R * 0.07, jy + R * 0.32), (x + R * 0.07, jy + R * 0.32), (x - R * 0.01, jy + R * 0.32 - L2)],
                  fill=(225, 228, 236, 255), outline=(70, 72, 80, 255))
    # hốc mắt sâu
    for sx in (-1, 1):
        ex = cx + sx * R * 0.42
        d.polygon([(ex - R * 0.32, cy - R * 0.05), (ex - sx * R * 0.05, cy - R * 0.38), (ex + R * 0.3, cy - R * 0.12),
                   (ex + R * 0.22, cy + R * 0.25), (ex - R * 0.2, cy + R * 0.3)], fill=(5, 4, 8, 255),
                  outline=(60, 62, 70, 255))
        d.ellipse((ex - R * 0.05, cy - R * 0.02, ex + R * 0.05, cy + R * 0.08), fill=(255, 40, 30, 230))
    # hốc mũi
    d.polygon([(cx, cy + R * 0.22), (cx - R * 0.16, cy + R * 0.58), (cx, cy + R * 0.5), (cx + R * 0.16, cy + R * 0.58)],
              fill=(5, 4, 8, 255))
    # vệt sáng kim loại + nứt
    for _ in range(9):
        x = cx + rnd.uniform(-0.75, 0.75) * R
        y = cy + rnd.uniform(-0.85, 0.1) * R
        d.line([(x, y), (x + rnd.uniform(-0.05, 0.05) * R, y + rnd.uniform(0.15, 0.35) * R)],
               fill=(255, 255, 255, 200), width=max(1, int(R * 0.03)))
    for _ in range(3):
        x, y = cx + rnd.uniform(-0.5, 0.5) * R, cy - R * 0.9
        pts = [(x, y)]
        for _ in range(4):
            x += rnd.uniform(-0.12, 0.12) * R
            y += rnd.uniform(0.1, 0.2) * R
            pts.append((x, y))
        d.line(pts, fill=dark + (255,), width=max(1, int(R * 0.025)))
    im = im.filter(ImageFilter.SMOOTH)
    im = im.resize((max(1, W // k), max(1, H // k)), Image.LANCZOS)
    if al < 1:
        im.putalpha(im.split()[3].point(lambda v: int(v * al)))
    return im


def make_hellfire_frames(size, seed):
    """Lửa địa ngục (lam hoả): sợi lửa xanh trong suốt, lõi trắng xanh, đầu lửa cuộn, tàn lửa cam bay lên."""
    rnd = random.Random(seed + 14000)
    W, H = size, int(size * 1.35)
    base = H * 0.86
    strands = [(W / 2.0 + rnd.uniform(-0.36, 0.36) * W, rnd.uniform(0.3, 0.8) * H, rnd.uniform(0, 6.3),
                rnd.uniform(0.06, 0.12) * W, rnd.choice((-1, 1))) for _ in range(rnd.randint(11, 15))]
    embers = [(W / 2.0 + rnd.uniform(-0.4, 0.4) * W, rnd.uniform(0.3, 0.9), rnd.uniform(0, 6.3)) for _ in range(14)]
    frames = []
    for f in range(10):
        core, glow, dc, dg = _fx_new(W, H)
        grow = min(1.0, (f + 1) / 3.5)
        fade = 1.0 if f < 6 else (10 - f) / 4.0
        for x0, L, ph, amp, cur in strands:
            L2 = L * grow * (0.85 + 0.15 * math.sin(ph + f * 1.4))
            pts = []
            n = 14
            for i in range(n + 1):
                t = i / float(n)
                y = base - L2 * t
                x = x0 + math.sin(ph + t * 5 + f * 0.9) * amp * t + math.sin(ph * 2 + t * 11 + f * 1.7) * amp * 0.25 * t
                pts.append((x, y))
            tx, ty = pts[-1]                                # đầu lửa cuộn
            for i in range(1, 6):
                a = ph + cur * i * 0.9
                rr = amp * 0.5 * (1 - i / 6.0)
                pts.append((tx + math.cos(a) * rr * cur, ty - i * amp * 0.12 + math.sin(a) * rr))
            for i in range(len(pts) - 1):                   # thuôn dần lên ngọn
                t = i / float(len(pts))
                wg = max(3, int(W * 0.14 * (1 - t * 0.8)))
                dg.line([pts[i], pts[i + 1]], fill=(25, 80, 255, int(190 * fade)), width=wg)
                dc.line([pts[i], pts[i + 1]], fill=(40, 130, 255, int(120 * fade * (1 - t * 0.4))),
                        width=max(2, int(W * 0.07 * (1 - t * 0.8))))
                dc.line([pts[i], pts[i + 1]], fill=(90, 195, 255, int(220 * fade * (1 - t * 0.4))),
                        width=max(1, int(W * 0.03 * (1 - t * 0.7))))
                if t < 0.6:
                    dc.line([pts[i], pts[i + 1]], fill=(220, 248, 255, int(235 * fade * (1 - t))),
                            width=max(1, int(W * 0.01)))
        dg.ellipse((W * 0.08, base - W * 0.08, W * 0.92, base + W * 0.08), fill=(40, 120, 255, int(200 * fade)))
        for x0, sp, ph in embers:                           # tàn lửa cam
            y = base - (f + ph) * H * 0.07 * sp
            if y < 0:
                continue
            x = x0 + math.sin(ph + f) * W * 0.03
            q = max(1, W * 0.01)
            dc.ellipse((x - q, y - q, x + q, y + q), fill=(255, 150, 50, int(255 * fade)))
        frames.append(_fx_merge(core, glow, max(1, W * 0.045)))
    return frames


def _sword_img(L):
    """Phi kiếm: lưỡi bạc, rãnh máu, chắn vàng, chuôi quấn, tua đỏ. Mũi kiếm hướng LÊN."""
    from PIL import ImageDraw
    w = int(L * 0.36)
    im = Image.new("RGBA", (w, int(L)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx = w / 2.0
    tip, guard = L * 0.02, L * 0.68
    bw = L * 0.045
    d.polygon([(cx, tip), (cx + bw, tip + L * 0.08), (cx + bw, guard), (cx - bw, guard), (cx - bw, tip + L * 0.08)],
              fill=(215, 222, 235, 255), outline=(90, 100, 120, 255))
    d.line([(cx, tip + L * 0.1), (cx, guard - L * 0.02)], fill=(150, 160, 180, 255), width=max(1, int(L * 0.012)))
    d.line([(cx - bw * 0.6, tip + L * 0.09), (cx - bw * 0.6, guard)], fill=(255, 255, 255, 255), width=1)
    d.rounded_rectangle((cx - L * 0.13, guard, cx + L * 0.13, guard + L * 0.035), radius=L * 0.015,
                        fill=(230, 180, 60, 255), outline=(120, 80, 20, 255))
    d.rectangle((cx - L * 0.028, guard + L * 0.035, cx + L * 0.028, L * 0.93), fill=(70, 35, 30, 255))
    for i in range(5):
        y = guard + L * (0.05 + i * 0.045)
        d.line([(cx - L * 0.028, y), (cx + L * 0.028, y + L * 0.02)], fill=(40, 20, 15, 255), width=1)
    d.ellipse((cx - L * 0.04, L * 0.92, cx + L * 0.04, L * 0.99), fill=(230, 180, 60, 255))
    d.line([(cx, L * 0.97), (cx + L * 0.05, L * 0.995)], fill=(220, 30, 40, 255), width=max(1, int(L * 0.02)))
    return im


def make_skull_frames(size, seed):
    """Đầu lâu ma quái: 4–6 cái nối nhau bay lên, cái sau to hơn cái trước, mỗi cái nhỏ rồi to dần khi bay."""
    rnd = random.Random(seed + 4000)
    W, H = int(size * 1.3), int(size * 2.0)
    n = rnd.randint(4, 6)
    sk = []
    for i in range(n):
        final = W * (0.06 + 0.11 * i / max(1, n - 1))          # thứ tự: nhỏ -> to
        side = (1 if i % 2 else -1) * rnd.uniform(0.05, 0.22)
        sk.append((i * 2.0, final, side, rnd.uniform(0, 6.3)))
    F = int(2 * n + 11)
    base_cache = {}

    def skull(rq, jq):
        k = (rq, jq)
        if k not in base_cache:
            base_cache[k] = _horror_skull(max(3, rq), jq / 3.0, 1.0, seed + rq)
        return base_cache[k]

    frames = []
    for f in range(F):
        core, glow, dc, dg = _fx_new(W, H)
        for i, (start, final, side, ph) in enumerate(sk):
            age = f - start
            if age < 0:
                continue
            life = 11.0
            t = age / life
            if t > 1:
                continue
            al = min(1.0, age / 1.5) * (1 - max(0.0, t - 0.65) / 0.35)
            rr = final * (0.3 + 0.7 * min(1.0, t * 1.6))             # nhỏ rồi to dần
            cy = H * 0.86 - t * H * 0.7
            cx = W / 2.0 + side * W * min(1.0, t * 2) + math.sin(ph + age * 0.8) * W * 0.02
            for k2 in range(1, 4):                                   # khói ma
                q = rr * (0.9 - k2 * 0.15)
                ty = cy + rr * (1.1 + k2 * 0.8)
                dg.ellipse((cx - q, ty - q, cx + q, ty + q), fill=(90, 30, 140, int(150 * al / k2)))
            dg.ellipse((cx - rr * 1.5, cy - rr * 1.5, cx + rr * 1.5, cy + rr * 1.7), fill=(60, 0, 90, int(190 * al)))
            img = skull(int(rr / 2) * 2, int(abs(math.sin(age * 1.6 + i)) * 3 + 0.5))
            if al < 0.99:
                img = img.copy()
                img.putalpha(img.split()[3].point(lambda v: int(v * al)))
            core.alpha_composite(img, (int(cx - img.width / 2), max(0, int(cy - rr * 1.05))))
        frames.append(_fx_merge(core, glow, max(1, W * 0.035)))
    return frames


def make_dragon_frames(size, seed):
    """Lôi long: rồng sấm sét xanh trắng chạy dọc phía trên dòng chữ về chỗ gõ, sét con đánh xuống chữ, cuối cùng nổ chớp."""
    rnd = random.Random(seed + 13000)
    W, H = int(size * 2.2), int(size * 0.9)
    base = H * 0.62                                          # đường chân chữ
    x0, x1 = W * 0.04, W * 0.88
    blen = W * 0.5
    F = 13
    frames = []

    def ypath(x, f):
        return base - H * 0.2 + math.sin(x / (W * 0.09) + f * 0.9) * H * 0.07

    for f in range(F):
        core, glow, dc, dg = _fx_new(W, H)
        tr = min(1.0, f / 9.0)
        hx = x0 + (x1 - x0) * tr
        hy = ypath(hx, f)
        fade = 1.0 if f < F - 2 else 0.5
        if f <= 10:
            tail = max(x0, hx - blen)
            for s_ in range(3):                              # 3 dải sét xoắn làm thân
                pts = []
                x = tail
                while x <= hx:
                    t = (x - tail) / max(1.0, hx - tail)
                    off = math.sin(x / (W * 0.035) + s_ * 2.1 + f * 1.3) * H * 0.045 * (0.4 + 0.6 * t)
                    pts.append((x, ypath(x, f) + off + rnd.uniform(-1, 1) * H * 0.02))
                    x += max(3, W * 0.018)
                pts.append((hx, hy))
                for i in range(len(pts) - 1):
                    t = i / float(len(pts))
                    dg.line([pts[i], pts[i + 1]], fill=(70, 120, 255, int(190 * fade)), width=max(2, int(H * 0.07 * (0.3 + t))))
                    dc.line([pts[i], pts[i + 1]], fill=(170, 205, 255, int(230 * fade)), width=max(1, int(H * 0.025 * (0.3 + t))))
                    dc.line([pts[i], pts[i + 1]], fill=(255, 255, 255, int(255 * fade)), width=1)
            for _ in range(2 if f % 2 else 1):               # sét con đánh xuống chữ
                bx = rnd.uniform(max(x0, hx - blen), hx)
                by = ypath(bx, f)
                bolt = _jagged((bx, by), (bx + rnd.uniform(-0.03, 0.03) * W, base + H * 0.06), 4, H * 0.03, rnd)
                dg.line(bolt, fill=(100, 150, 255, 200), width=max(2, int(H * 0.04)))
                dc.line(bolt, fill=(235, 245, 255, 255), width=1)
            hs = H * 0.17                                     # đầu rồng bằng nét sét, nhìn về phía con trỏ

            def J(a, b):
                ln = _jagged(a, b, 3, hs * 0.08, rnd)
                dg.line(ln, fill=(90, 140, 255, 220), width=max(2, int(hs * 0.35)))
                dc.line(ln, fill=(235, 245, 255, 255), width=max(1, int(hs * 0.1)))
            gape = hs * (0.35 + 0.2 * math.sin(f * 1.7))
            snout = (hx + hs * 1.7, hy - hs * 0.15)
            J((hx - hs * 0.3, hy - hs * 0.55), snout)                         # hàm trên
            J((hx - hs * 0.2, hy + hs * 0.2), (hx + hs * 1.4, hy + gape))     # hàm dưới
            J((hx - hs * 0.3, hy - hs * 0.55), (hx - hs * 1.3, hy - hs * 1.3))  # sừng
            J((hx + hs * 0.2, hy - hs * 0.6), (hx - hs * 0.6, hy - hs * 1.5))
            for k in range(3):                                                # bờm
                J((hx - hs * 0.2 * k, hy - hs * 0.3), (hx - hs * (0.9 + 0.3 * k), hy + hs * (0.2 + 0.35 * k)))
            for s2 in (-1, 1):                                                # râu điện
                J((hx + hs * 1.2, hy + s2 * hs * 0.05), (hx + hs * 0.4, hy + s2 * hs * 1.1 + hs * 0.3))
            ex, ey = hx + hs * 0.55, hy - hs * 0.3
            q = max(1, hs * 0.16)
            dg.ellipse((ex - q * 3, ey - q * 3, ex + q * 3, ey + q * 3), fill=(150, 200, 255, 230))
            dc.ellipse((ex - q, ey - q, ex + q, ey + q), fill=(255, 255, 255, 255))
        if f >= 9:                                           # nổ chớp tại chỗ gõ
            k = f - 9
            r = min(H * (0.1 + 0.05 * k), H * 0.22)
            a_ = max(0.0, 1 - k / 4.0)
            cx_, cy_ = x1, base - H * 0.12
            dg.ellipse((cx_ - r * 1.6, cy_ - r, cx_ + r * 1.6, cy_ + r), fill=(110, 160, 255, int(230 * a_)))
            if k < 2:
                dc.ellipse((cx_ - r * 0.5, cy_ - r * 0.35, cx_ + r * 0.5, cy_ + r * 0.35), fill=(255, 255, 255, 255))
            for _ in range(5):
                a = rnd.uniform(0, 2 * math.pi)
                ln = _jagged((cx_, cy_), (cx_ + math.cos(a) * r * 1.6, cy_ + math.sin(a) * r), 4, H * 0.025, rnd)
                dc.line(ln, fill=(230, 240, 255, int(255 * a_)), width=1)
        frames.append(_fx_merge(core, glow, max(1, H * 0.035)))
    return frames


def make_sword_frames(size, seed):
    """Vạn kiếm: 5–7 phi kiếm nhỏ lần lượt bay xoáy rồi đâm chùm quanh chữ, nứt vỡ, cùng tan."""
    rnd = random.Random(seed + 15000)
    W = H = int(size * 1.5)
    hit = (W / 2.0, H * 0.55)
    L = size * 0.32
    sword = _sword_img(L)
    n = rnd.randint(5, 7)
    sw = []
    for i in range(n):
        a0 = rnd.uniform(0, 2 * math.pi)
        tg = (hit[0] + rnd.uniform(-0.12, 0.12) * size, hit[1] + rnd.uniform(-0.07, 0.07) * size)
        cr = [_jagged(tg, (tg[0] + math.cos(a) * size * rnd.uniform(0.1, 0.2), tg[1] + math.sin(a) * size * rnd.uniform(0.06, 0.13)),
                      3, size * 0.015, rnd) for a in [rnd.uniform(0, 6.3) for _ in range(3)]]
        sw.append(dict(a0=a0, sgn=rnd.choice((-1, 1)), R=W * rnd.uniform(0.28, 0.42), start=i * 0.8, tg=tg, cracks=cr))
    FLY = 6

    def orbit(s_, t):
        a = s_["a0"] + s_["sgn"] * t * 2.2 * math.pi
        rr = s_["R"] * (1 - 0.5 * t)
        return hit[0] + math.cos(a) * rr, hit[1] + math.sin(a) * rr * 0.75

    def put(layer, cx_, cy_, tipdir, al=1.0):
        dx, dy = tipdir
        deg = math.degrees(math.atan2(-dy, dx)) - 90
        img = sword.rotate(deg, resample=Image.BICUBIC, expand=True)
        if al < 1:
            img.putalpha(img.split()[3].point(lambda v: int(v * al)))
        tmp = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        tmp.paste(img, (int(cx_ - img.width / 2), int(cy_ - img.height / 2)), img)
        layer.alpha_composite(tmp)

    F = int(n * 0.8 + FLY + 7)
    frames = []
    for f in range(F):
        core, glow, dc, dg = _fx_new(W, H)
        end_fade = 1.0 if f < F - 4 else (F - f) / 4.0
        for s_ in sw:
            age = f - s_["start"]
            if age < 0:
                continue
            tg = s_["tg"]
            if age < FLY:                                       # bay xoáy, mũi kiếm theo hướng bay
                t = age / float(FLY)
                p, q = orbit(s_, t), orbit(s_, t + 0.04)
                tip = (q[0] - p[0], q[1] - p[1])
                trail = [orbit(s_, max(0.0, t - k * 0.04)) for k in range(6)]
                dg.line(trail, fill=(90, 210, 255, 160), width=max(2, int(L * 0.15)))
                put(core, p[0], p[1], tip)
                s_["last"] = p
            else:
                p = s_.get("last", orbit(s_, 1.0))
                d_ = (tg[0] - p[0], tg[1] - p[1])
                dl = math.hypot(*d_) or 1
                u = (d_[0] / dl, d_[1] / dl)
                a_tip = L * 0.48
                k = age - FLY
                if k < 1:                                       # lao thẳng tới
                    cxx, cyy = tg[0] - u[0] * (a_tip + L * 0.3), tg[1] - u[1] * (a_tip + L * 0.3)
                    dg.line([p, (cxx, cyy)], fill=(130, 225, 255, 200), width=max(2, int(L * 0.2)))
                    put(core, cxx, cyy, u)
                else:                                           # cắm vào chữ
                    shake = (1.5 if k < 2.5 else 0) * (1 if int(f) % 2 else -1)
                    put(core, tg[0] - u[0] * a_tip * 0.9 + shake, tg[1] - u[1] * a_tip * 0.9, u, max(0.15, end_fade))
                    if k < 2:
                        r = size * 0.07
                        dg.ellipse((tg[0] - r * 1.5, tg[1] - r, tg[0] + r * 1.5, tg[1] + r), fill=(150, 225, 255, 220))
                        dc.ellipse((tg[0] - r * 0.4, tg[1] - r * 0.3, tg[0] + r * 0.4, tg[1] + r * 0.3), fill=(255, 255, 255, 255))
                    for cr in s_["cracks"]:
                        dc.line(cr, fill=(255, 255, 255, int(255 * end_fade)), width=1)
                        dg.line(cr, fill=(100, 200, 255, int(180 * end_fade)), width=max(2, int(size * 0.02)))
        frames.append(_fx_merge(core, glow, max(1, size * 0.025)))
    return frames


# (khoá, tên hiển thị, hàm tạo, điểm neo trong khung: tỉ lệ x, y)
def _zap(dc, dg, pts, w, glow, mid, al=1.0, white=True):
    """Vẽ một tia sét: quầng màu + lõi sáng + chỉ trắng."""
    a = max(0.0, min(1.0, al))
    dg.line(pts, fill=glow[:3] + (int(glow[3] * a),), width=max(2, int(w * 3.2)))
    dc.line(pts, fill=mid[:3] + (int(mid[3] * a),), width=max(1, int(w)))
    if white:
        dc.line(pts, fill=(255, 255, 255, int(255 * a)), width=max(1, int(w * 0.4)))


def _sparks(dc, rnd, c, rmin, rmax, n, q, col, al=1.0, sy=1.0):
    for _ in range(n):
        a = rnd.uniform(0, 2 * math.pi)
        d = rnd.uniform(rmin, rmax)
        x, y = c[0] + math.cos(a) * d, c[1] + math.sin(a) * d * sy
        dc.ellipse((x - q, y - q, x + q, y + q), fill=col[:3] + (int(col[3] * al),))


def make_chain_frames(size, seed):
    """Lôi xích liên hoàn: tia sét nhảy từ chữ này sang chữ kia dọc dòng, dồn về chỗ gõ rồi nổ."""
    rnd = random.Random(seed + 17000)
    W, H = int(size * 2.2), int(size * 0.8)
    base = H * 0.62
    n = rnd.randint(4, 6)
    nodes = []
    for i in range(n):
        t = i / float(n - 1)
        nodes.append((W * (0.06 + 0.84 * t) + rnd.uniform(-1, 1) * W * 0.02, base - H * rnd.uniform(0.08, 0.3)))
    nodes[-1] = (W * 0.9, base - H * 0.12)
    G, M = (80, 140, 255, 210), (180, 215, 255, 255)
    F = n + 6
    frames = []
    for f in range(F):
        core, glow, dc, dg = _fx_new(W, H)
        for i in range(n - 1):
            age = f - i
            if age < 0:
                continue
            al = 1.0 if age < 3 else max(0.0, 1 - (age - 2) * 0.3)
            if al <= 0:
                continue
            a, b = nodes[i], nodes[i + 1]
            for k in range(2 if age < 2 else 1):             # cung sét vồng lên giữa 2 chữ
                mx, my = (a[0] + b[0]) / 2, min(a[1], b[1]) - H * rnd.uniform(0.1, 0.25)
                arc = _jagged(a, (mx, my), 4, H * 0.04, rnd)[:-1] + _jagged((mx, my), b, 4, H * 0.04, rnd)
                _zap(dc, dg, arc, H * 0.03 * (1 if k == 0 else 0.6), G, M, al)
            if age < 2:                                      # chớp tại chữ bị trúng
                r = H * 0.07
                dg.ellipse((b[0] - r * 2, b[1] - r * 2, b[0] + r * 2, b[1] + r * 2), fill=(120, 170, 255, int(200 * al)))
                dc.ellipse((b[0] - r * 0.6, b[1] - r * 0.6, b[0] + r * 0.6, b[1] + r * 0.6), fill=(255, 255, 255, 255))
                _sparks(dc, rnd, b, H * 0.05, H * 0.22, 4, max(1, H * 0.012), (210, 230, 255, 255))
        if f >= n - 1:                                       # nổ tại chỗ gõ
            k = f - (n - 1)
            c = nodes[-1]
            al = max(0.0, 1 - k / 6.0)
            r = min(H * (0.12 + 0.06 * k), H * 0.3)
            dg.ellipse((c[0] - r * 1.5, c[1] - r, c[0] + r * 1.5, c[1] + r), fill=(90, 150, 255, int(220 * al)))
            for _ in range(5):
                a = rnd.uniform(0, 2 * math.pi)
                _zap(dc, dg, _jagged(c, (c[0] + math.cos(a) * r * 1.8, c[1] + math.sin(a) * r * 1.1), 4, H * 0.03, rnd),
                     H * 0.015, G, M, al, white=False)
            if k < 2:
                rr = H * 0.06
                dc.ellipse((c[0] - rr, c[1] - rr, c[0] + rr, c[1] + rr), fill=(255, 255, 255, 255))
        frames.append(_fx_merge(core, glow, max(1, H * 0.03)))
    return frames


def make_plasma_frames(size, seed):
    """Lôi cầu plasma: quả cầu điện tụ lại, tua sét quằn quại, rồi nổ bung."""
    rnd = random.Random(seed + 18000)
    W = H = size
    c = (W / 2.0, H / 2.0)
    G, M = (150, 80, 255, 210), (210, 180, 255, 255)
    frames = []
    for f in range(9):
        core, glow, dc, dg = _fx_new(W, H)
        if f < 6:
            grow = min(1.0, (f + 1) / 3.0)
            R = W * 0.13 * grow
            dg.ellipse((c[0] - R * 2.2, c[1] - R * 2.2, c[0] + R * 2.2, c[1] + R * 2.2), fill=(120, 70, 255, 170))
            dc.ellipse((c[0] - R, c[1] - R, c[0] + R, c[1] + R), fill=(170, 140, 255, 150), outline=(230, 220, 255, 255),
                       width=max(1, int(W * 0.012)))
            r2 = R * 0.45
            dc.ellipse((c[0] - r2, c[1] - r2, c[0] + r2, c[1] + r2), fill=(255, 255, 255, 255))
            for _ in range(rnd.randint(5, 8)):               # tua sét bám ra ngoài
                a = rnd.uniform(0, 2 * math.pi)
                L = W * rnd.uniform(0.25, 0.44) * grow
                p1 = (c[0] + math.cos(a) * L, c[1] + math.sin(a) * L)
                _zap(dc, dg, _jagged(c, p1, 6, W * 0.035, rnd), W * 0.012, G, M, 1.0)
                q = max(1, W * 0.014)
                dc.ellipse((p1[0] - q, p1[1] - q, p1[0] + q, p1[1] + q), fill=(240, 230, 255, 255))
        else:                                                # nổ bung
            k = f - 5
            al = 1 - k / 4.0
            r = W * (0.18 + 0.1 * k)
            dg.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), outline=(160, 100, 255, int(230 * al)), width=max(3, int(W * 0.06)))
            dc.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), outline=(240, 230, 255, int(255 * al)), width=max(1, int(W * 0.012)))
            if k == 1:
                rr = W * 0.12
                dc.ellipse((c[0] - rr, c[1] - rr, c[0] + rr, c[1] + rr), fill=(255, 255, 255, 230))
            for _ in range(6):
                a = rnd.uniform(0, 2 * math.pi)
                p1 = (c[0] + math.cos(a) * r * 1.1, c[1] + math.sin(a) * r * 1.1)
                _zap(dc, dg, _jagged((c[0] + math.cos(a) * r * 0.5, c[1] + math.sin(a) * r * 0.5), p1, 3, W * 0.02, rnd),
                     W * 0.01, G, M, al, white=False)
        frames.append(_fx_merge(core, glow, max(1, W * 0.035)))
    return frames


def make_storm_frames(size, seed):
    """Lôi vân giáng thế: mây giông đen kéo tới trên chữ, chớp loé trong mây, sét đánh xuống liên hồi."""
    rnd = random.Random(seed + 19000)
    W, H = int(size * 1.6), int(size * 1.6)
    ground = H * 0.9
    puffs = [(W * rnd.uniform(0.12, 0.88), H * rnd.uniform(0.1, 0.22), W * rnd.uniform(0.12, 0.2)) for _ in range(9)]
    strikes = []
    for i in range(rnd.randint(3, 4)):
        x = W * 0.5 if i == 0 else W * rnd.uniform(0.18, 0.82)
        strikes.append((2 + i * 2, _jagged((x + rnd.uniform(-1, 1) * W * 0.1, H * 0.2), (x, ground), 9, W * 0.05, rnd)))
    F = 13
    frames = []
    for f in range(F):
        core, glow, dc, dg = _fx_new(W, H)
        cl = min(1.0, (f + 1) / 2.5) * (1.0 if f < F - 3 else max(0.0, (F - f) / 3.0))
        flash = any(0 <= f - t0 < 2 for t0, _ in strikes)
        for (px, py, pr) in puffs:                           # mây giông
            col = (70, 60, 110, int(200 * cl)) if flash else (30, 26, 52, int(210 * cl))
            dc.ellipse((px - pr, py - pr * 0.6, px + pr, py + pr * 0.6), fill=col)
        if flash:
            dg.ellipse((W * 0.15, H * 0.05, W * 0.85, H * 0.3), fill=(140, 150, 255, int(160 * cl)))
        for t0, pts in strikes:
            age = f - t0
            if age < 0 or age > 3:
                continue
            al = (1, 1, 0.6, 0.3)[age]
            if age == 0:
                pts_ = pts[:len(pts) // 2 + 1]
            else:
                pts_ = pts
            _zap(dc, dg, pts_, W * 0.022, (90, 120, 255, 220), (200, 215, 255, 255), al)
            if age >= 1:
                hx, hy = pts[-1]
                r = W * 0.1
                dg.ellipse((hx - r * 1.6, hy - r * 0.6, hx + r * 1.6, hy + r * 0.4), fill=(130, 160, 255, int(220 * al)))
                _sparks(dc, rnd, (hx, hy), W * 0.03, W * 0.18, 5, max(1, W * 0.01), (220, 230, 255, 255), al, sy=0.4)
        frames.append(_fx_merge(core, glow, max(1, W * 0.03)))
    return frames


def make_spear_frames(size, seed):
    """Lôi thương xuyên chữ: ngọn giáo sét lao vút ngang tới chỗ gõ, cắm xuyên, nổ toé điện."""
    rnd = random.Random(seed + 20000)
    W, H = int(size * 2.0), int(size * 0.8)
    hit = (W * 0.85, H * 0.5)
    G, M = (70, 150, 255, 220), (190, 225, 255, 255)
    frames = []
    for f in range(10):
        core, glow, dc, dg = _fx_new(W, H)
        tx = W * 0.05 + (hit[0] + W * 0.06 - W * 0.05) * min(1.0, (f + 1) / 4.0)
        y = hit[1]
        if f < 7:
            al = 1.0 if f < 5 else 0.5
            tail = max(0.0, tx - W * 0.55)
            Ls = H * 0.13
            for k in range(3):                               # thân giáo = bó sét
                _zap(dc, dg, _jagged((tail, y), (tx - Ls, y), 8, H * (0.03 + 0.02 * k), rnd),
                     H * (0.03 if k == 0 else 0.015), G, M, al)
            tip = [(tx + Ls * 0.4, y), (tx - Ls, y - Ls * 0.45), (tx - Ls * 0.7, y), (tx - Ls, y + Ls * 0.45)]
            dg.polygon(tip, fill=(110, 180, 255, int(230 * al)))
            dc.polygon(tip, fill=(220, 240, 255, int(255 * al)), outline=(255, 255, 255, int(255 * al)))
            for _ in range(3):                               # tua điện kéo đuôi
                x = rnd.uniform(tail, tx)
                _zap(dc, dg, _jagged((x, y), (x - W * 0.06, y + rnd.choice((-1, 1)) * H * rnd.uniform(0.1, 0.25)), 3, H * 0.02, rnd),
                     H * 0.01, G, M, al * 0.8, white=False)
        if f >= 3:                                           # cắm trúng: nổ toé
            k = f - 3
            al = max(0.0, 1 - k / 6.5)
            r = min(H * (0.12 + 0.06 * k), H * 0.32)
            dg.ellipse((hit[0] - r * 0.7, hit[1] - r * 0.7, hit[0] + r * 0.7, hit[1] + r * 0.7), fill=(90, 160, 255, int(170 * al)))
            if k < 2:
                rr = H * 0.1
                dc.ellipse((hit[0] - rr, hit[1] - rr, hit[0] + rr, hit[1] + rr), fill=(255, 255, 255, 255))
            for _ in range(6):
                a = rnd.uniform(-math.pi * 0.6, math.pi * 0.6) + (0 if rnd.random() < 0.7 else math.pi)
                _zap(dc, dg, _jagged(hit, (hit[0] + math.cos(a) * r * 1.6, hit[1] + math.sin(a) * r * 1.2), 4, H * 0.03, rnd),
                     H * 0.012, G, M, al, white=False)
        frames.append(_fx_merge(core, glow, max(1, H * 0.035)))
    return frames


def make_claw_frames(size, seed):
    """Lôi trảo xé chữ: ba vuốt sét chéo cào qua liên tiếp, để lại vệt điện rồi tan."""
    rnd = random.Random(seed + 21000)
    W = H = size
    ang = math.radians(rnd.uniform(50, 70)) * rnd.choice((-1, 1))
    dx, dy = math.cos(ang), math.sin(ang)
    nx, ny = -dy, dx
    c = (W / 2.0, H / 2.0)
    G, M = (60, 170, 255, 220), (200, 235, 255, 255)
    claws = []
    for i in range(3):
        o = (i - 1) * W * 0.16
        L = W * (0.36 if i == 1 else 0.3)
        cx, cy = c[0] + nx * o, c[1] + ny * o
        claws.append(((cx - dx * L, cy - dy * L), (cx + dx * L, cy + dy * L)))
    frames = []
    for f in range(8):
        core, glow, dc, dg = _fx_new(W, H)
        for i, (a, b) in enumerate(claws):
            age = f - i * 0.6
            if age < 0:
                continue
            reach = min(1.0, (age + 1) / 2.0)
            al = 1.0 if age < 3 else max(0.0, 1 - (age - 2.5) * 0.35)
            if al <= 0:
                continue
            e = (a[0] + (b[0] - a[0]) * reach, a[1] + (b[1] - a[1]) * reach)
            pts = _jagged(a, e, 7, W * 0.022, rnd)
            w = W * 0.03 * (1.3 if i == 1 else 1.0)
            _zap(dc, dg, pts, w, G, M, al)
            if age < 2:
                _sparks(dc, rnd, e, W * 0.02, W * 0.12, 4, max(1, W * 0.012), (220, 240, 255, 255), al)
        frames.append(_fx_merge(core, glow, max(1, W * 0.03)))
    return frames


def make_bloodbolt_frames(size, seed):
    """Huyết lôi diệt thế: sét đỏ máu quầng đen nổ xé từ chỗ gõ, vòng hắc khí lan ra."""
    rnd = random.Random(seed + 22000)
    W = H = int(size * 1.15)
    c = (W / 2.0, H / 2.0)
    bolts = [(rnd.uniform(0, 2 * math.pi), rnd.uniform(0.32, 0.48) * W) for _ in range(rnd.randint(4, 5))]
    G, M = (230, 10, 30, 230), (255, 90, 90, 255)
    frames = []
    for f in range(8):
        core, glow, dc, dg = _fx_new(W, H)
        fade = (1, 1, 1, 0.85, 0.6, 0.4, 0.22, 0.1)[f]
        grow = min(1.0, (f + 1) / 2.0)
        r = W * (0.12 + 0.05 * f)                            # vòng hắc khí
        dg.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), outline=(40, 0, 10, int(220 * fade)), width=max(3, int(W * 0.07)))
        dc.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), outline=(200, 0, 30, int(200 * fade)), width=max(1, int(W * 0.01)))
        for ang, L in bolts:
            end = (c[0] + math.cos(ang) * L * grow, c[1] + math.sin(ang) * L * grow)
            pts = _jagged(c, end, 7, W * 0.05, rnd)
            dg.line(pts, fill=(20, 0, 0, int(200 * fade)), width=max(4, int(W * 0.08)))   # quầng đen
            _zap(dc, dg, pts, W * 0.022, G, M, fade)
            if rnd.random() < 0.7:
                k = rnd.randint(2, len(pts) - 2)
                a2 = ang + rnd.choice((-1, 1)) * rnd.uniform(0.5, 1.0)
                br = _jagged(pts[k], (pts[k][0] + math.cos(a2) * L * 0.3, pts[k][1] + math.sin(a2) * L * 0.3), 3, W * 0.02, rnd)
                _zap(dc, dg, br, W * 0.012, G, M, fade, white=False)
        if f < 3:
            rr = W * (0.08 - f * 0.015)
            dg.ellipse((c[0] - rr * 2, c[1] - rr * 2, c[0] + rr * 2, c[1] + rr * 2), fill=(255, 20, 40, int(200 * fade)))
            dc.ellipse((c[0] - rr, c[1] - rr, c[0] + rr, c[1] + rr), fill=(255, 235, 235, 255))
        frames.append(_fx_merge(core, glow, max(1, W * 0.03)))
    return frames


def make_pillar_frames(size, seed):
    """Thiên phạt lôi trụ: cột sáng vàng kim giáng thẳng xuống chữ, sét xoắn quanh cột, vòng chấn động dưới chân."""
    rnd = random.Random(seed + 23000)
    W, H = int(size * 1.1), int(size * 2.0)
    cx, gy = W / 2.0, H * 0.9
    G, M = (255, 170, 30, 220), (255, 230, 150, 255)
    from PIL import ImageChops
    fade_mask = Image.linear_gradient("L").resize((W, H))
    fade_mask = fade_mask.point(lambda v: min(255, int(v * 2.6)))
    frames = []
    for f in range(10):
        core, glow, dc, dg = _fx_new(W, H)
        if f == 0:
            dc.line([(cx, 0), (cx, gy)], fill=(255, 240, 180, 160), width=max(1, int(W * 0.01)))
        else:
            al = 1.0 if f < 6 else max(0.0, 1 - (f - 5) / 4.5)
            bw = W * (0.09 if f < 3 else 0.07) * (1 if f < 6 else al)
            dg.rectangle((cx - bw * 2.2, 0, cx + bw * 2.2, gy), fill=(255, 170, 40, int(170 * al)))
            dc.rectangle((cx - bw * 0.7, 0, cx + bw * 0.7, gy), fill=(255, 235, 160, int(240 * al)))
            dc.rectangle((cx - bw * 0.25, 0, cx + bw * 0.25, gy), fill=(255, 255, 255, int(255 * al)))
            for s_ in (-1, 1):                               # sét xoắn quanh cột
                pts = []
                for i in range(21):
                    y = gy * i / 20.0
                    pts.append((cx + s_ * math.sin(y / (H * 0.07) + f * 1.2) * W * 0.16 + rnd.uniform(-1, 1) * W * 0.015, y))
                _zap(dc, dg, pts, W * 0.016, G, M, al)
            k = f - 1                                        # vòng chấn động dưới chân
            r = W * (0.12 + 0.07 * k)
            dg.ellipse((cx - r, gy - r * 0.28, cx + r, gy + r * 0.28), outline=(255, 190, 60, int(230 * al)), width=max(3, int(W * 0.05)))
            dc.ellipse((cx - r, gy - r * 0.28, cx + r, gy + r * 0.28), outline=(255, 245, 200, int(255 * al)), width=max(1, int(W * 0.012)))
            _sparks(dc, rnd, (cx, gy), W * 0.05, W * 0.4, 6, max(1, W * 0.012), (255, 240, 190, 255), al, sy=0.35)
        im = _fx_merge(core, glow, max(1, W * 0.035))
        a_ = im.getchannel("A")                              # đỉnh cột mờ dần như từ trời cao giáng xuống
        im.putalpha(ImageChops.multiply(a_, fade_mask))
        frames.append(im)
    return frames


def make_net_frames(size, seed):
    """Lôi võng thu lưới: lưới điện giăng quanh chữ rồi siết lại vào chỗ gõ, nổ chớp."""
    rnd = random.Random(seed + 24000)
    W = H = size
    c = (W / 2.0, H / 2.0)
    n = rnd.randint(6, 8)
    angs = [2 * math.pi * i / n + rnd.uniform(-0.2, 0.2) for i in range(n)]
    G, M = (170, 90, 255, 210), (220, 190, 255, 255)
    frames = []
    for f in range(9):
        core, glow, dc, dg = _fx_new(W, H)
        if f < 7:
            R = W * (0.44 - max(0, f - 2) * 0.08) * min(1.0, (f + 1) / 2.0)
            pts = [(c[0] + math.cos(a) * R, c[1] + math.sin(a) * R) for a in angs]
            for i in range(n):                               # vòng lưới + nan lưới
                _zap(dc, dg, _jagged(pts[i], pts[(i + 1) % n], 4, W * 0.02, rnd), W * 0.01, G, M, 1.0, white=False)
                _zap(dc, dg, _jagged(pts[i], pts[(i + n // 2) % n], 6, W * 0.025, rnd), W * 0.008, G, M, 0.75, white=False)
            for p in pts:
                q = max(1, W * 0.018)
                dc.ellipse((p[0] - q, p[1] - q, p[0] + q, p[1] + q), fill=(255, 255, 255, 255))
        if f >= 6:
            k = f - 6
            al = 1 - k / 3.0
            r = W * (0.1 + 0.08 * k)
            dg.ellipse((c[0] - r * 1.5, c[1] - r * 1.5, c[0] + r * 1.5, c[1] + r * 1.5), fill=(170, 110, 255, int(220 * al)))
            dc.ellipse((c[0] - r * 0.5, c[1] - r * 0.5, c[0] + r * 0.5, c[1] + r * 0.5), fill=(255, 255, 255, int(255 * al)))
        frames.append(_fx_merge(core, glow, max(1, W * 0.03)))
    return frames


# ══════════════ HỆ LÔI THÁI CỔ HẮC LONG – ngôn ngữ thiết kế sấm sét dùng chung ══════════════
# Dùng cho hiệu ứng bàn phím VÀ chiêu thức của Cổ Long (tools/dung_co_long.py nạp lại phần này).
# Bảng màu cố định, không đổi giữa các frame / chiêu:
LOI_CORE = (246, 238, 255)       # lõi: trắng tím cực sáng
LOI_CORE_B = (228, 242, 255)     # lõi phụ: trắng xanh
LOI_MID = (172, 94, 255)         # lớp điện trung gian: tím điện
LOI_MID_B = (118, 108, 255)      # xanh tím
LOI_EDGE = (84, 26, 152)         # viền ngoài: tím đậm
LOI_DARK = (44, 9, 72)           # hắc tím
LOI_AURA = (22, 4, 38)           # quầng năng lượng: đen tím (vẽ bán trong suốt)


def _c01(t):
    return 0.0 if t < 0 else (1.0 if t > 1 else t)


def _ph(t, a, b):
    """Tiến độ 0..1 của giai đoạn [a, b] trên trục thời gian 0..1."""
    return _c01((t - a) / float(max(1e-6, b - a)))


def _eo(t):
    t = _c01(t)
    return 1 - (1 - t) ** 3


def _ei(t):
    t = _c01(t)
    return t * t


def _dv(a):
    r = math.radians(a)
    return (math.cos(r), math.sin(r))


def _ad(p, q, k=1.0):
    return (p[0] + q[0] * k, p[1] + q[1] * k)


def _lp(p, q, t):
    return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)


def loi_path(p0, p1, rnd, kink=(0.025, 0.07), seg=(0.05, 0.12), lift=0.0):
    """Đường sét chính: gấp khúc răng cưa sắc, luân phiên đổi hướng có chủ đích, hội tụ vào điểm đích.
    lift > 0: cả đường vồng lên (dùng cho tia nhảy giữa 2 chữ)."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / L, dx / L
    pts = [p0]
    t = 0.0
    side = rnd.choice((-1, 1))
    drift = 0.0
    while True:
        t += rnd.uniform(*seg) * (0.55 if rnd.random() < 0.3 else 1.0)
        if t >= 0.94:
            break
        if rnd.random() < 0.72:
            side = -side                                     # luân phiên -> răng cưa
        jag = rnd.uniform(*kink) * (2.1 if rnd.random() < 0.18 else 1.0)    # thỉnh thoảng gập mạnh có chủ đích
        drift = drift * 0.5 + side * jag
        off = drift * L * (1 - 0.5 * t)
        if lift:
            off -= lift * L * 4 * t * (1 - t)
        pts.append((p0[0] + dx * t + nx * off, p0[1] + dy * t + ny * off))
    pts.append(p1)
    return pts


class LoiBolt:
    """Một tia sét có THIẾT KẾ GỐC CỐ ĐỊNH (khung xương + cây nhánh tạo một lần từ hạt giống).
    Mỗi frame chỉ đổi trạng thái: grow (vươn tới đâu), tail (co rút từ gốc), power (nhịp sáng), jit (giật nhẹ)."""

    def __init__(self, p0, p1, w, rnd, branches=3, depth=2, kink=(0.025, 0.07), seg=(0.05, 0.12),
                 blen=(0.2, 0.38), spread=(24, 52), lift=0.0, pts=None, hue=0.0):
        self.pts = pts if pts is not None else loi_path(p0, p1, rnd, kink, seg, lift)
        self.w = w
        self.hue = hue                                        # 0 = tím điện, 1 = xanh tím
        cum = [0.0]
        for a, b in zip(self.pts, self.pts[1:]):
            cum.append(cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
        self.cum, self.L = cum, (cum[-1] or 1.0)
        self.kids = []
        n = len(self.pts)
        if depth > 0 and branches > 0 and n > 3:
            idx = list(range(1, n - 2))
            rnd.shuffle(idx)
            idx = sorted(idx[:branches])
            side = rnd.choice((-1, 1))
            for i in idx:
                q = self.pts[i]
                a, b = self.pts[i - 1], self.pts[i + 1]
                d0 = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
                side = -side
                ang = d0 + side * rnd.uniform(*spread)
                ln = self.L * rnd.uniform(*blen) * (1 - 0.35 * cum[i] / self.L)
                kid = LoiBolt(q, _ad(q, _dv(ang), ln), w * 0.52, rnd, branches=max(0, branches - 2), depth=depth - 1,
                              kink=(kink[0] * 1.15, kink[1] * 1.15), seg=(0.14, 0.26), blen=blen, spread=spread, hue=hue)
                self.kids.append((cum[i] / self.L, kid))

    def set_pal(self, pal):
        self.pal = pal
        for _, kid in self.kids:
            kid.set_pal(pal)
        return self

    def _cut(self, s0, s1):
        """Đoạn đường từ tỉ lệ s0 tới s1 của chiều dài."""
        a, b = s0 * self.L, s1 * self.L
        out = []
        for i in range(len(self.pts) - 1):
            c0, c1 = self.cum[i], self.cum[i + 1]
            if c1 < a or c0 > b:
                continue
            p, q = self.pts[i], self.pts[i + 1]
            seg = (c1 - c0) or 1.0
            if not out:
                out.append(_lp(p, q, max(0.0, (a - c0) / seg)))
            out.append(_lp(p, q, min(1.0, (b - c0) / seg)))
        return out

    def draw(self, em, grow=1.0, tail=0.0, power=1.0, jit=0.0, jr=None, xf=None, wk=1.0, kid_power=0.9):
        """em: bộ vẽ (VCanvas hoặc adapter khung rồng). xf: hàm biến đổi toạ độ (xoay / co giãn theo frame)."""
        grow, tail = _c01(grow), _c01(tail)
        if grow - tail > 0.02 and power > 0.02:
            pts = self._cut(tail, grow)
            if len(pts) >= 2:
                if jit and jr is not None:
                    pts = [pts[0]] + [(x + jr.uniform(-jit, jit), y + jr.uniform(-jit, jit)) for x, y in pts[1:-1]] + [pts[-1]]
                if xf:
                    pts = [xf(p) for p in pts]
                vis = (grow - tail)
                n = len(pts)
                ws = []
                for k in range(n):
                    u = k / float(n - 1)
                    w = self.w * wk * (1 - 0.5 * (tail + u * vis))
                    tip = _c01((1 - u) / 0.18) if vis > 0.05 else 0.0     # đầu tia nhọn
                    root = _c01(u / 0.12) if tail > 0.02 else 1.0          # đang co rút: gốc cũng nhọn
                    ws.append(w * min(tip, max(0.35, root)) if k not in (0, n - 1) else (0.0 if k == n - 1 else w * (1.0 if tail <= 0.02 else 0.3)))
                loi_stroke(em, pts, ws, power, self.hue, getattr(self, "pal", None))
        for tk, kid in self.kids:
            if grow > tk:
                g = (grow - tk) / 0.28
                tl = (tail - tk) / 0.28 if tail > tk else 0.0
                kid.draw(em, g, tl, power * kid_power, jit * 0.8, jr, xf, wk, kid_power)


def _norms(pts):
    n = len(pts)
    out = []
    for i in range(n):
        a = pts[max(0, i - 1)]
        b = pts[min(n - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1.0
        out.append((-dy / L, dx / L))
    return out


def taper_poly(pts, ws, k=1.0):
    """Đa giác thuôn nhọn bao quanh đường gấp khúc (độ dày ws[i] * k)."""
    nm = _norms(pts)
    L = [(p[0] + n[0] * w * k, p[1] + n[1] * w * k) for p, n, w in zip(pts, nm, ws)]
    R = [(p[0] - n[0] * w * k, p[1] - n[1] * w * k) for p, n, w in zip(pts, nm, ws)]
    return L + R[::-1]


LOI_XANH = ((232, 248, 255), (70, 170, 255), (16, 70, 175), (20, 70, 150))     # lôi xanh: lõi, thân, viền, quầng


def loi_stroke(em, pts, ws, power=1.0, hue=0.0, pal=None):
    """Vẽ một đường sét theo bảng màu cố định: quầng đen tím – quầng tím – viền tím đậm – thân tím điện – lõi trắng tím.
    pal = (lõi, thân, viền, quầng) để dùng bảng màu khác (vd LOI_XANH)."""
    p = _c01(power)
    wmax = max(ws) if ws else 1.0
    if pal:
        core, mid, edge, aura = pal
    else:
        mid = tuple(int(LOI_MID[i] + (LOI_MID_B[i] - LOI_MID[i]) * hue) for i in range(3))
        core = tuple(int(LOI_CORE[i] + (LOI_CORE_B[i] - LOI_CORE[i]) * hue) for i in range(3))
        edge, aura = LOI_EDGE, LOI_AURA
    em.line("aura", pts, aura + (int(120 * (0.4 + 0.6 * p)),), wmax * 7.0)
    em.line("glow", pts, mid + (int(215 * p),), wmax * 2.8)
    em.poly("base", taper_poly(pts, ws, 1.7), edge + (int(255 * min(1.0, 0.35 + p)),))
    em.poly("base", taper_poly(pts, ws, 1.0), mid + (int(255 * min(1.0, 0.2 + p)),))
    if p > 0.25:
        em.poly("base", taper_poly(pts, ws, 0.42), core + (int(255 * _c01((p - 0.25) / 0.5)),))


def loi_arc_pts(r, a0, a1, rnd, kink=(0.05, 0.12), step=(7, 13)):
    """Đường sét chạy theo cung tròn bán kính r (toạ độ quanh tâm 0,0), gấp khúc theo bán kính."""
    pts = []
    a = a0
    side = rnd.choice((-1, 1))
    while a < a1:
        if rnd.random() < 0.8:
            side = -side
        rr = r * (1 + side * rnd.uniform(*kink)) if pts else r
        pts.append((math.cos(math.radians(a)) * rr, math.sin(math.radians(a)) * rr))
        a += rnd.uniform(*step)
    pts.append((math.cos(math.radians(a1)) * r, math.sin(math.radians(a1)) * r))
    return pts


def loi_flash(em, c, r, power=1.0):
    """Chớp loá: quầng đen tím rộng, quầng tím, tâm trắng, 8 tia sáng nhọn."""
    p = _c01(power)
    em.ell("aura", c, r * 2.2, r * 2.2, LOI_AURA + (int(130 * p),))
    em.ell("glow", c, r * 1.3, r * 1.3, LOI_MID + (int(220 * p),))
    em.ell("base", c, r * 0.45, r * 0.45, LOI_CORE + (int(255 * p),))
    for k in range(8):
        a = k * 45 + 22.5
        ln = r * (1.9 if k % 2 else 1.25)
        em.poly("base", [_ad(c, _dv(a - 7), r * 0.3), _ad(c, _dv(a), ln), _ad(c, _dv(a + 7), r * 0.3)],
                LOI_CORE + (int(230 * p),))


def loi_ring(em, c, rx, ry, power=1.0, w=2.0):
    p = _c01(power)
    em.ell_ring("glow", c, rx, ry, LOI_MID + (int(200 * p),), w * 2.6)
    em.ell_ring("base", c, rx, ry, LOI_EDGE + (int(230 * p),), w * 1.5)
    em.ell_ring("base", c, rx, ry, LOI_CORE + (int(240 * p),), max(1.0, w * 0.5))


# ══════════════ VFX bàn phím: khung vẽ, hạt, lớp hiệu ứng ══════════════
class VCanvas:
    """Khung vẽ một frame: lớp quầng (làm mờ rộng), lớp sáng (mờ vừa), lớp chính (vẽ phóng ss lần cho sắc nét)."""

    def __init__(self, W, H, ss=2, blur=1.0):
        from PIL import ImageDraw
        self.W, self.H, self.ss, self.blur = int(W), int(H), ss, blur
        self.L = {"aura": Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0)),
                  "glow": Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0)),
                  "base": Image.new("RGBA", (self.W * ss, self.H * ss), (0, 0, 0, 0))}
        self.D = {k: ImageDraw.Draw(v) for k, v in self.L.items()}

    def _p(self, layer, pts):
        if layer == "base":
            s = self.ss
            return [(x * s, y * s) for x, y in pts]
        return list(pts)

    def _k(self, layer):
        return self.ss if layer == "base" else 1

    def line(self, layer, pts, col, w):
        if len(pts) >= 2 and col[3] > 0:
            self.D[layer].line(self._p(layer, pts), fill=col, width=max(1, int(w * self._k(layer))), joint="curve")

    def poly(self, layer, pts, col):
        if len(pts) >= 3 and col[3] > 0:
            self.D[layer].polygon(self._p(layer, pts), fill=col)

    def ell(self, layer, c, rx, ry, col):
        if col[3] > 0 and rx > 0 and ry > 0:
            k = self._k(layer)
            x, y = c[0] * k, c[1] * k
            self.D[layer].ellipse((x - rx * k, y - ry * k, x + rx * k, y + ry * k), fill=col)

    def ell_ring(self, layer, c, rx, ry, col, w):
        if col[3] > 0 and rx > 1 and ry > 0.5:
            k = self._k(layer)
            x, y = c[0] * k, c[1] * k
            self.D[layer].ellipse((x - rx * k, y - ry * k, x + rx * k, y + ry * k), outline=col, width=max(1, int(w * k)))

    def stamp(self, im, c, scale=1.0, rot=0.0, alpha=1.0, layer="base"):
        """Đặt một hình (đầu lâu, kiếm...) tâm tại c, phóng / xoay / độ mờ."""
        if alpha <= 0.01 or im is None:
            return
        k = self._k(layer) * scale
        w, h = max(1, int(im.width * k)), max(1, int(im.height * k))
        t = im.resize((w, h), Image.BICUBIC)
        if rot:
            t = t.rotate(rot, resample=Image.BICUBIC, expand=True)
        if alpha < 0.999:
            t.putalpha(t.getchannel("A").point(lambda v: int(v * alpha)))
        x = int(c[0] * self._k(layer) - t.width / 2)
        y = int(c[1] * self._k(layer) - t.height / 2)
        tgt = self.L[layer]
        bx0, by0 = max(0, -x), max(0, -y)
        bx1, by1 = min(t.width, tgt.width - x), min(t.height, tgt.height - y)
        if bx1 > bx0 and by1 > by0:
            tgt.alpha_composite(t.crop((bx0, by0, bx1, by1)), (x + bx0, y + by0))

    def image(self):
        from PIL import ImageFilter
        out = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        base = min(self.W, self.H)
        for k, r in (("aura", max(3.0, base * 0.03)), ("glow", max(1.5, base * 0.011))):
            lay = self.L[k]
            b = lay.getbbox()
            if not b:
                continue
            r *= self.blur
            m = int(r * 3) + 2
            b = (max(0, b[0] - m), max(0, b[1] - m), min(self.W, b[2] + m), min(self.H, b[3] + m))
            g = lay.crop(b).filter(ImageFilter.GaussianBlur(r))
            out.alpha_composite(g, b[:2])
            if k == "glow":
                out.alpha_composite(g, b[:2])                   # cộng 2 lần: sáng rực kiểu cộng màu
        bs = self.L["base"]
        if bs.getbbox():
            out.alpha_composite(bs.resize((self.W, self.H), Image.LANCZOS) if self.ss > 1 else bs)
        return out


class Part:
    """Hạt: tia lửa điện, bụi năng lượng, khói, đá vụn, cánh hoa, mảnh vỡ..."""
    __slots__ = ("x", "y", "vx", "vy", "life", "age", "size", "kind", "drag", "grav", "rot", "vr", "col", "ax", "ay", "img")

    def __init__(self, x, y, vx, vy, life, size, kind="spark", drag=0.92, grav=0.0, col=None, rot=0.0, vr=0.0):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.life, self.age, self.size, self.kind = life, 0, size, kind
        self.drag, self.grav, self.col, self.rot, self.vr = drag, grav, col, rot, vr
        self.ax = self.ay = 0.0
        self.img = None

    def step(self):
        self.age += 1
        self.vx = self.vx * self.drag + self.ax
        self.vy = self.vy * self.drag + self.grav + self.ay
        self.x += self.vx
        self.y += self.vy
        self.rot += self.vr

    def alive(self):
        return self.age < self.life

    def draw(self, cv):
        k = 1 - self.age / float(self.life)
        x, y, s = self.x, self.y, self.size
        if self.kind == "sprite":                             # mảnh bóc từ ảnh (đá vụn...) bay theo quán tính
            cv.stamp(self.img, (x, y), 1.0, self.rot, min(1.0, k * 1.6))
            return
        if self.kind == "spark_b":                            # tia lửa lôi xanh, mảnh
            tail = (x - self.vx * 1.6, y - self.vy * 1.6)
            cv.line("glow", [tail, (x, y)], LOI_XANH[1] + (int(200 * k),), 2.2)
            cv.line("base", [tail, (x, y)], LOI_XANH[0] + (int(255 * k),), 0.8)
            return
        if self.kind == "spark":                              # vệt tia lửa điện: lõi trắng, viền tím
            s = max(s, 1.2)
            tail = (x - self.vx * 1.6, y - self.vy * 1.6)
            cv.line("glow", [tail, (x, y)], LOI_MID + (int(220 * k),), s * 2.5)
            cv.line("base", [tail, (x, y)], LOI_MID + (int(255 * k),), s)
            cv.line("base", [_lp(tail, (x, y), 0.5), (x, y)], LOI_CORE + (int(255 * k),), max(0.6, s * 0.45))
        elif self.kind == "mote":                             # bụi năng lượng hình thoi
            col = self.col or LOI_MID
            s = max(s, 1.6)
            cv.ell("glow", (x, y), s * 2.2, s * 2.2, col + (int(160 * k),))
            cv.poly("base", [(x, y - s * 1.6), (x + s * 0.7, y), (x, y + s * 1.6), (x - s * 0.7, y)], LOI_CORE + (int(240 * k),))
        elif self.kind == "smoke":                            # khói / quầng hắc tím, nở to dần
            col = self.col or LOI_AURA
            r = s * (1 + 1.4 * (1 - k))
            cv.ell("aura", (x, y), r, r * 0.85, col + (int(150 * k),))
        elif self.kind == "gas":                              # độc khí xanh tím
            col = self.col or (90, 210, 80)
            r = s * (1 + 1.2 * (1 - k))
            cv.ell("aura", (x, y), r, r * 0.8, col + (int(110 * k),))
            cv.ell("glow", (x, y), r * 0.5, r * 0.4, col + (int(70 * k),))
        elif self.kind == "rock":                             # đá vụn tối, mép ánh tím
            pts = [_ad((x, y), _dv(self.rot + i * 72 + (i % 2) * 20), s * (0.7 + 0.2 * (i % 3))) for i in range(5)]
            cv.poly("base", pts, (34, 22, 40, int(255 * min(1, k * 1.5))))
            cv.line("base", pts + [pts[0]], LOI_MID + (int(220 * k),), 0.8)
        elif self.kind == "shard":                            # mảnh sáng (kiếm vỡ, sọ vỡ)
            col = self.col or LOI_CORE
            pts = [_ad((x, y), _dv(self.rot), s * 1.6), _ad((x, y), _dv(self.rot + 150), s * 0.6),
                   _ad((x, y), _dv(self.rot + 210), s * 0.6)]
            cv.poly("base", pts, col + (int(255 * k),))
            cv.ell("glow", (x, y), s * 1.5, s * 1.5, LOI_MID + (int(150 * k),))
        elif self.kind == "petal":                            # cánh bỉ ngạn rơi xoay
            col = self.col or (210, 22, 44)
            a = self.rot
            pts = [_ad((x, y), _dv(a), s * 1.8), _ad((x, y), _dv(a + 90), s * 0.45), _ad((x, y), _dv(a + 180), s * 0.8),
                   _ad((x, y), _dv(a + 270), s * 0.45)]
            cv.poly("base", pts, col + (int(255 * k),))
            cv.ell("glow", (x, y), s * 1.2, s * 1.2, (255, 60, 90, int(90 * k)))
        elif self.kind == "soul":                             # linh hồn: đốm sáng kéo đuôi
            tail = (x - self.vx * 3, y - self.vy * 3)
            cv.line("glow", [tail, (x, y)], (150, 110, 255, int(170 * k)), s * 2.2)
            cv.ell("base", (x, y), s * 0.6, s * 0.6, LOI_CORE + (int(230 * k),))
        elif self.kind == "drop":                             # giọt độc
            col = self.col or (120, 255, 90)
            cv.poly("base", [(x, y - s * 1.8), (x + s * 0.8, y), (x, y + s * 0.8), (x - s * 0.8, y)], col + (int(240 * k),))


def dissolve(im, thr, noise, edge=(186, 110, 255), width=0.09):
    """Tan rã theo nhiễu (không phải chỉ làm mờ): điểm có nhiễu < thr biến mất, mép đang cháy sáng tím."""
    import numpy as np
    a = np.asarray(im).astype(np.float32)
    nz = noise[:a.shape[0], :a.shape[1]]
    keep = np.clip((nz - thr) / 0.03, 0, 1)
    burn = np.clip(1 - (nz - thr) / width, 0, 1) * keep
    for c in range(3):
        a[..., c] = a[..., c] * (1 - burn) + edge[c] * burn
    a[..., 3] *= keep
    return Image.fromarray(a.astype(np.uint8), "RGBA")


def make_noise(w, h, seed, cell=6):
    import numpy as np
    rr = np.random.RandomState(seed)
    small = (rr.rand(max(2, h // cell + 2), max(2, w // cell + 2)) * 255).astype(np.uint8)
    big = Image.fromarray(small).resize((w + cell, h + cell), Image.BICUBIC)
    return np.asarray(big).astype(np.float32) / 255.0


class Vfx:
    """Một hiệu ứng bàn phím. Vòng đời: __init__ (nhận thông số) -> init() -> [update(f, t) -> draw(cv, f, t)] * n
    -> finish() giải phóng. bake() chạy vòng đời đó để tạo dãy frame; FxPlayer phát dãy frame tại con trỏ nhập.
    Thông số: size (cỡ, theo cỡ chữ), mode 'T' (gõ) / 'D' (xoá), power (cường độ), speed (tốc độ), seed (biến thiên)."""
    name = ""
    frames = 16                    # số frame ở tốc độ 1 (25 frame/giây)
    anchor = (0.5, 0.5)            # điểm trong khung ứng với vị trí con trỏ nhập
    box = (1.3, 1.3)               # khung = box * size

    def __init__(self, size, seed=0, mode="T", power=1.0, speed=1.0):
        self.S = float(size)
        self.mode, self.D = mode, (mode == "D")
        self.power, self.speed = power, speed
        self.seed = seed
        self.rnd = random.Random(seed * 7919 + sum(map(ord, self.name)) * 31 + (17 if self.D else 0))
        self.n = max(6, int(round(self.frames / max(0.3, speed))))
        self.W, self.H = int(self.box[0] * size) + 4, int(self.box[1] * size) + 4
        self.c = (self.W * self.anchor[0], self.H * self.anchor[1])
        self.parts = []
        self.init()

    # các bước con ghi đè
    def init(self):
        pass

    def update(self, f, t):
        pass

    def draw(self, cv, f, t):
        pass

    def finish(self):
        self.parts = []

    # tiện ích
    def emit(self, n, c, speed, life, size, kind="spark", spread=(0, 360), drag=0.9, grav=0.0, col=None, inward=False,
             radius=0.0):
        r = self.rnd
        for _ in range(n):
            a = r.uniform(*spread)
            v = speed * r.uniform(0.5, 1.15)
            if inward:                                       # sinh ở vòng ngoài, bay vào tâm (hiệu ứng hút ngược)
                rad = radius * r.uniform(0.7, 1.1)
                p = _ad(c, _dv(a), rad)
                d = _dv(a + 180)
                self.parts.append(Part(p[0], p[1], d[0] * v, d[1] * v, life, size * r.uniform(0.7, 1.2), kind, drag, grav, col,
                                       r.uniform(0, 360), r.uniform(-15, 15)))
            else:
                p = _ad(c, _dv(a), radius * r.random())
                d = _dv(a)
                self.parts.append(Part(p[0], p[1], d[0] * v, d[1] * v, life, size * r.uniform(0.7, 1.2), kind, drag, grav, col,
                                       r.uniform(0, 360), r.uniform(-15, 15)))

    def pulse(self, f, pattern=(1.0, 0.55, 1.0, 0.35, 0.85, 0.3, 0.7, 0.22, 0.5, 0.15)):
        """Nhịp sáng: sét bùng – tắt – bùng lại, không sáng liên tục."""
        return pattern[f % len(pattern)]

    def bake(self):
        ss = getattr(self, "ss", None) or (2 if self.S <= 320 else 1)
        out = []
        jr = random.Random(self.seed * 131 + 7)
        for f in range(self.n):
            t = f / float(self.n - 1)
            self.jr = jr
            self.update(f, t)
            for p in self.parts:
                p.step()
            self.parts = [p for p in self.parts if p.alive()]
            cv = VCanvas(self.W, self.H, ss)
            self.draw(cv, f, t)
            for p in self.parts:
                p.draw(cv)
            im = cv.image()
            left = self.n - 1 - f
            if left < 3:                                         # pha phân rã chung: 3 frame cuối mờ dần, kết thúc sạch
                k = (left + 1) / 4.0
                im.putalpha(im.getchannel("A").point(lambda v, k=k: int(v * k)))
            out.append(im)
        self.finish()
        return out


# ══════════════ 16 hiệu ứng bàn phím ══════════════
# Mỗi lớp: init() dựng thiết kế gốc cố định (khung sét, quỹ đạo...), update() sinh/di chuyển hạt theo giai đoạn,
# draw() vẽ trạng thái frame. 5 giai đoạn: khởi phát – tăng năng lượng – cao trào – phản ứng – phân rã.
# Chế độ 'D' (xoá): hướng ngược lại – hút vào / rút về / tan rã, không dùng lại nguyên hiệu ứng gõ.

class LoiTinhBaoPhat(Vfx):
    """Lôi tinh bạo phát – gõ: tia sét bung toả từ con trỏ; xoá: tia sét từ ngoài hút sập vào con trỏ."""
    name, frames, anchor, box = "bolt", 15, (0.5, 0.5), (1.35, 1.35)

    def init(self):
        r = self.rnd
        n = 7
        self.rays = []
        for k in range(n):
            a = k * 360.0 / n + r.uniform(-14, 14)
            L = self.S * r.uniform(0.4, 0.6)
            out = _ad(self.c, _dv(a), L)
            p0, p1 = (out, self.c) if self.D else (self.c, out)
            self.rays.append(LoiBolt(p0, p1, self.S * 0.018, r, branches=3, depth=2))

    def update(self, f, t):
        if not self.D and f == 1:
            self.emit(16, self.c, self.S * 0.045, 9, self.S * 0.012, "spark", drag=0.86)
        if not self.D and f == 5:
            self.emit(8, self.c, self.S * 0.02, 10, self.S * 0.01, "mote", drag=0.9, grav=-0.15)
        if self.D and f in (0, 3):
            self.emit(12, self.c, self.S * 0.05, 9, self.S * 0.011, "spark", inward=True, radius=self.S * 0.55, drag=0.97)

    def draw(self, cv, f, t):
        pw = self.pulse(f) * self.power
        c = self.c
        if not self.D:
            g = _eo(_ph(t, 0.0, 0.22))
            tail = _ph(t, 0.58, 0.95)
            if f <= 1:
                loi_flash(cv, c, self.S * (0.08 + 0.06 * f), 1.0)
            if 0.05 < t < 0.5:
                k = _ph(t, 0.05, 0.5)
                loi_ring(cv, c, self.S * (0.12 + 0.45 * k), self.S * (0.12 + 0.45 * k), 1 - k, self.S * 0.012)
            for b in self.rays:
                b.draw(cv, g, tail, pw * (1 - 0.6 * tail), self.S * 0.006, self.jr)
            if t < 0.6:
                cv.ell("base", c, self.S * 0.03, self.S * 0.03, LOI_CORE + (int(255 * pw),))
        else:
            g = _ei(_ph(t, 0.0, 0.3)) * 0.98 + 0.02
            tail = _ph(t, 0.35, 0.7)                             # tia rút dần vào tâm
            for b in self.rays:
                b.draw(cv, g, tail, pw, self.S * 0.006, self.jr)
            k = _ph(t, 0.0, 0.7)
            loi_ring(cv, c, self.S * 0.55 * (1 - k), self.S * 0.55 * (1 - k), 0.8 * (1 - k), self.S * 0.01)
            core = self.S * 0.07 * (1 - _ph(t, 0.55, 0.8))
            cv.ell("aura", c, core * 3, core * 3, LOI_AURA + (180,))
            cv.ell("base", c, core, core, LOI_DARK + (255,))
            cv.ell_ring("base", c, core, core, LOI_MID + (255,), 1.2)
            if 0.72 < t < 0.9:
                loi_flash(cv, c, self.S * 0.07, 1 - _ph(t, 0.72, 0.9))


class ThienLoiGiang(Vfx):
    """Thiên lôi giáng – gõ: sét dẫn bậc thang giáng xuống chữ, chớp hồi kích, toé điện sát chân chữ;
    xoá: sét bắn ngược từ chữ lên trời, hạt năng lượng bị hút lên theo."""
    name, frames, anchor, box = "thunder", 16, (0.5, 0.9), (0.95, 1.6)

    def init(self):
        r = self.rnd
        self.g = self.c
        top = (self.W * 0.5 + r.uniform(-0.15, 0.15) * self.W, self.H * 0.03)
        p0, p1 = (self.g, top) if self.D else (top, self.g)
        self.main = LoiBolt(p0, p1, self.S * 0.024, r, branches=5, depth=2)
        self.side = []
        for sgn in (-1, 1):
            e = (self.g[0] + sgn * self.S * r.uniform(0.3, 0.42), self.g[1] - self.S * r.uniform(0.0, 0.06))
            a, b = (e, self.g) if self.D else (self.g, e)
            self.side.append(LoiBolt(a, b, self.S * 0.012, r, branches=1, depth=1))

    def update(self, f, t):
        g = self.g
        if not self.D and f == 4:
            self.emit(14, g, self.S * 0.05, 12, self.S * 0.011, "spark", spread=(190, 350), drag=0.9, grav=self.S * 0.004)
            self.emit(6, g, self.S * 0.015, 14, self.S * 0.05, "smoke", spread=(200, 340), drag=0.9)
        if self.D and f < 8 and f % 2 == 0:
            for _ in range(4):
                x = g[0] + self.rnd.uniform(-0.3, 0.3) * self.S
                self.parts.append(Part(x, g[1], (g[0] - x) * 0.05, -self.S * 0.05, 12, self.S * 0.012, "mote", 0.98, -0.2))

    def cloud(self, cv, k, lit):
        """Mây giông hắc tím: cụm bông xếp chồng, loé sáng từ bên trong khi sét đánh."""
        if k <= 0.02:
            return
        cx, cy, S = self.W / 2, self.H * 0.05, self.S
        for dx, dy, r in ((-0.22, 0.02, 0.13), (0.0, -0.01, 0.17), (0.22, 0.02, 0.13), (-0.1, 0.05, 0.12), (0.12, 0.05, 0.12)):
            p = (cx + dx * S, cy + dy * S)
            cv.ell("aura", p, r * S * 1.15, r * S * 0.7, LOI_AURA + (int(150 * k),))
            cv.ell("base", p, r * S, r * S * 0.55, (52, 26, 78, int(235 * k)))
            cv.ell("base", (p[0] - r * S * 0.25, p[1] - r * S * 0.2), r * S * 0.55, r * S * 0.3, (84, 52, 120, int(220 * k)))
        if lit > 0:
            cv.ell("glow", (cx, cy + S * 0.03), S * 0.3, S * 0.09, LOI_MID + (int(230 * lit * k),))

    def draw(self, cv, f, t):
        g = self.g
        cloud = _ph(t, 0, 0.15) * (1 - _ph(t, 0.7, 1.0))
        if not self.D:
            self.cloud(cv, cloud, 1.0 if f in (4, 5, 7) else 0.0)
            lead = (0.2, 0.38, 0.55, 0.72)
            if f < 4:                                            # tia dẫn: nhảy bậc từng đoạn, mảnh và mờ
                self.main.draw(cv, lead[f], 0, 0.45, self.S * 0.004, self.jr, wk=0.55)
                return
            pw = (1.0, 0.95, 0.3, 1.0, 0.55, 0.85, 0.25, 0.6, 0.18, 0.4, 0.12, 0.2)[min(11, f - 4)] * self.power
            tail = _ph(t, 0.62, 0.97)
            self.main.draw(cv, 1.0, tail, pw, self.S * 0.006, self.jr)
            if f in (4, 5, 7):
                loi_flash(cv, g, self.S * (0.11 if f == 4 else 0.07), 1.0)
            sg = _eo(_ph(t, 0.27, 0.42))
            for b in self.side:
                b.draw(cv, sg, _ph(t, 0.55, 0.8), pw)
            k = _ph(t, 0.26, 0.6)
            loi_ring(cv, g, self.S * (0.08 + 0.42 * k), self.S * (0.03 + 0.09 * k), 1 - k, self.S * 0.01)
        else:
            sg = _eo(_ph(t, 0.0, 0.2))
            for b in self.side:
                b.draw(cv, sg, _ph(t, 0.2, 0.42), 0.9)
            if f < 2:
                loi_flash(cv, g, self.S * 0.08, 0.9)
            g2 = _eo(_ph(t, 0.12, 0.38))
            tail = _ei(_ph(t, 0.45, 0.92))                       # gốc rời khỏi chữ, bị kéo lên trời
            pw = self.pulse(f, (1, 0.6, 1, 0.4, 0.9, 0.5)) * self.power
            self.main.draw(cv, g2, tail, pw, self.S * 0.006, self.jr)
            self.cloud(cv, cloud, 0.8 if f in (3, 4, 6) else 0.0)


class LoiLienHoi(Vfx):
    """Sấm sét liên hồi – gõ: 4 tia đánh xuống nối tiếp quanh chữ; xoá: 4 tia bắn ngược lên, lùi dần sang trái."""
    name, frames, anchor, box = "settia", 22, (0.5, 0.9), (1.7, 1.5)

    def init(self):
        r = self.rnd
        offs = [0.32, 0.1, -0.12, -0.34] if self.D else [0.0, -0.3, 0.26, -0.08]
        self.st = []
        for i, o in enumerate(offs):
            g = (self.c[0] + o * self.S, self.c[1] - (0 if i == 0 else r.uniform(0, 0.04) * self.S))
            top = (g[0] + r.uniform(-0.2, 0.2) * self.S, self.H * 0.04)
            a, b = (g, top) if self.D else (top, g)
            self.st.append((i * 4, g, LoiBolt(a, b, self.S * (0.02 if i == 0 else 0.015), r, branches=3, depth=2)))

    def update(self, f, t):
        for t0, g, _ in self.st:
            if f == t0 + 1 and not self.D:
                self.emit(6, g, self.S * 0.04, 9, self.S * 0.01, "spark", spread=(200, 340), grav=self.S * 0.003)
            if f == t0 and self.D:
                self.emit(5, g, self.S * 0.03, 10, self.S * 0.01, "mote", spread=(250, 290), grav=-0.3)

    def draw(self, cv, f, t):
        for t0, g, b in self.st:
            a = f - t0
            if a < 0 or a > 7:
                continue
            if self.D:
                grow, tail = (0.45, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)[a], (0, 0, 0, 0.2, 0.45, 0.65, 0.85, 1)[a]
            else:
                grow, tail = (0.5, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)[a], (0, 0, 0, 0.15, 0.4, 0.6, 0.8, 1)[a]
            pw = (0.5, 1.0, 0.4, 0.9, 0.5, 0.35, 0.2, 0.1)[a] * self.power
            b.draw(cv, grow, tail, pw, self.S * 0.005, self.jr, wk=0.6 if a == 0 else 1.0)
            if a in (1, 3):
                loi_flash(cv, g, self.S * 0.06, 0.9)


class LoiHoan(Vfx):
    """Lôi hoàn – gõ: vòng sét xoay nở rộng, tia nan hoa nối tâm; xoá: vòng sét xoay ngược, siết vào tâm rồi vỡ."""
    name, frames, anchor, box = "hoan", 16, (0.5, 0.5), (1.4, 1.4)

    def init(self):
        r = self.rnd
        self.arcs = []
        for k in range(6):
            a0 = k * 60 + r.uniform(0, 8)
            pts = loi_arc_pts(1.0, a0, a0 + 46, r, kink=(0.04, 0.1), step=(6, 11))
            self.arcs.append(LoiBolt(None, None, 1.0, r, branches=2, depth=1, pts=pts, blen=(0.25, 0.45)))
        self.spokes = [LoiBolt((0, 0), _dv(k * 120 + 30), 1.0, r, branches=1, depth=1) for k in range(3)]

    def _xf(self, rad, rot):
        c, co, si = self.c, math.cos(math.radians(rot)), math.sin(math.radians(rot))
        return lambda p: (c[0] + (p[0] * co - p[1] * si) * rad, c[1] + (p[0] * si + p[1] * co) * rad)

    def update(self, f, t):
        if f == 4 and not self.D:
            self.emit(14, self.c, self.S * 0.04, 10, self.S * 0.011, "spark", radius=self.S * 0.3)
        if self.D and f == 2:
            self.emit(14, self.c, self.S * 0.04, 10, self.S * 0.01, "mote", inward=True, radius=self.S * 0.6, drag=0.97)

    def draw(self, cv, f, t):
        if not self.D:
            rad = self.S * (0.1 + 0.45 * _eo(_ph(t, 0, 0.6)))
            rot = 70 * t
            g = _eo(_ph(t, 0.0, 0.25))
            tail = _ph(t, 0.6, 0.95)
        else:
            rad = self.S * (0.58 - 0.53 * _ei(_ph(t, 0, 0.75)))
            rot = -90 * t
            g = _eo(_ph(t, 0.0, 0.2))
            tail = _ph(t, 0.7, 0.9)
        pw = self.pulse(f) * self.power
        xf = self._xf(rad, rot)
        for a in self.arcs:
            a.draw(cv, g, tail, pw, 0.01, self.jr, xf=xf, wk=self.S * 0.017)
        if not self.D and 0.1 < t < 0.45:
            for sp in self.spokes:
                sp.draw(cv, 1.0, _ph(t, 0.3, 0.45), pw * 0.9, 0, None, xf=xf, wk=self.S * 0.011)
            loi_flash(cv, self.c, self.S * 0.05, 1 - _ph(t, 0.1, 0.45))
        if self.D and 0.72 < t < 0.95:
            loi_flash(cv, self.c, self.S * 0.08, 1 - _ph(t, 0.72, 0.95))


class LoiXoay(Vfx):
    """Lôi xoáy – gõ: 3 nhánh sét xoắn ốc xoay toả ra; xoá: xoắn ốc xoáy ngược hút vào lõi."""
    name, frames, anchor, box = "xoan", 16, (0.5, 0.5), (1.35, 1.35)

    def init(self):
        r = self.rnd
        self.arms = []
        for k in range(3):
            pts = []
            n = 22
            side = 1
            for i in range(n + 1):
                u = i / float(n)
                a = k * 120 + u * 260
                side = -side if r.random() < 0.75 else side
                rr = (0.08 + 0.92 * u) * (1 + side * r.uniform(0.0, 0.09))
                pts.append((math.cos(math.radians(a)) * rr, math.sin(math.radians(a)) * rr))
            if self.D:
                pts = pts[::-1]
            self.arms.append(LoiBolt(None, None, 1.0, r, branches=3, depth=1, pts=pts, blen=(0.15, 0.3)))

    def update(self, f, t):
        if not self.D and f in (3, 6):
            self.emit(8, self.c, self.S * 0.035, 10, self.S * 0.01, "spark", radius=self.S * 0.25)
        if self.D and f in (0, 4):
            self.emit(10, self.c, self.S * 0.045, 9, self.S * 0.01, "spark", inward=True, radius=self.S * 0.55, drag=0.97)

    def draw(self, cv, f, t):
        if not self.D:
            rad, rot = self.S * (0.2 + 0.4 * _eo(_ph(t, 0, 0.7))), 160 * t
            g, tail = _eo(_ph(t, 0, 0.35)), _ph(t, 0.6, 0.95)
        else:
            rad, rot = self.S * (0.6 - 0.45 * _ei(_ph(t, 0.1, 0.8))), -200 * t
            g, tail = _eo(_ph(t, 0, 0.3)), _ph(t, 0.45, 0.85)
        c = self.c
        co, si = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        xf = lambda p: (c[0] + (p[0] * co - p[1] * si) * rad, c[1] + (p[0] * si + p[1] * co) * rad)
        pw = self.pulse(f) * self.power
        for a in self.arms:
            a.draw(cv, g, tail, pw, 0.008, self.jr, xf=xf, wk=self.S * 0.017)
        core = self.S * (0.05 + 0.02 * math.sin(f * 1.3)) * (1 - _ph(t, 0.75, 1.0))
        cv.ell("aura", c, core * 3, core * 3, LOI_AURA + (150,))
        cv.ell("glow", c, core * 1.6, core * 1.6, LOI_MID + (int(200 * pw),))
        cv.ell("base", c, core * 0.5, core * 0.5, LOI_CORE + (int(255 * pw),))


class LoiPhatTru(Vfx):
    """Lôi phạt trụ – gõ: cột thiên phạt giáng xuống, sét xoắn quấn cột, ấn tròn dưới chân, cột co hẹp rồi tắt;
    xoá: cột bắn lên từ chữ rồi bị nhấc khỏi mặt đất hút lên trời."""
    name, frames, anchor, box = "loiphat", 18, (0.5, 0.92), (0.95, 1.7)

    def init(self):
        r = self.rnd
        self.g = self.c
        top = (self.g[0], 0.0)
        self.strands = []
        for k in range(3):
            o = (k - 1) * self.S * 0.03
            a, b = ((self.g[0] + o, self.g[1]), (top[0] + o, top[1])) if self.D else ((top[0] + o, top[1]), (self.g[0] + o, self.g[1]))
            self.strands.append(LoiBolt(a, b, self.S * (0.03 if k == 1 else 0.016), r, branches=2, depth=1, kink=(0.01, 0.03)))
        self.zz = [r.uniform(-1, 1) for _ in range(40)]

    def update(self, f, t):
        if f == 3 and not self.D:
            self.emit(16, self.g, self.S * 0.05, 12, self.S * 0.011, "spark", spread=(190, 350), grav=self.S * 0.004)
        if 2 < f < 12 and f % 3 == 0:
            self.emit(3, (self.g[0], self.g[1] - self.S * 0.1), self.S * 0.02, 14, self.S * 0.01, "mote",
                      spread=(250, 290), grav=-0.25, radius=self.S * 0.1)

    def draw(self, cv, f, t):
        g = self.g
        pw = self.pulse(f, (1, 0.7, 1, 0.55, 0.95, 0.6)) * self.power
        if not self.D:
            grow = _eo(_ph(t, 0, 0.16))
            narrow = 1 - 0.75 * _ph(t, 0.62, 0.95)
            tail = _ph(t, 0.8, 1.0)
        else:
            grow = _eo(_ph(t, 0, 0.16))
            narrow = 1 - 0.5 * _ph(t, 0.6, 0.95)
            tail = _ei(_ph(t, 0.45, 0.95))
        for b in self.strands:
            b.draw(cv, grow, tail, pw, self.S * 0.004, self.jr, wk=narrow)
        if grow > 0.95 and t < 0.85:                            # sét xoắn quấn quanh cột
            for s_ in (0, 1):
                pts, ws = [], []
                y0 = 0 if not self.D else self.H * tail * 0.9
                for i in range(40):
                    y = y0 + (g[1] - y0) * i / 39.0
                    ph = y / (self.S * 0.12) + f * 0.9 + s_ * math.pi
                    pts.append((g[0] + math.sin(ph) * self.S * 0.11 * narrow + self.zz[i] * self.S * 0.012, y))
                    ws.append(self.S * 0.008 * (0.4 + 0.6 * (math.cos(ph) > 0)))
                ws[-1] = 0
                loi_stroke(cv, pts, ws, pw * 0.85, 1.0)
        rk = _eo(_ph(t, 0.1, 0.4)) * (1 - _ph(t, 0.7, 1.0))      # ấn tròn dưới chân, xoay
        if rk > 0.02:
            loi_ring(cv, g, self.S * 0.32 * rk, self.S * 0.08 * rk, rk, self.S * 0.008)
            for k in range(8):
                a = k * 45 + f * 9
                p = (g[0] + math.cos(math.radians(a)) * self.S * 0.32 * rk, g[1] + math.sin(math.radians(a)) * self.S * 0.08 * rk)
                cv.poly("base", [_ad(p, (0, -self.S * 0.03)), _ad(p, (self.S * 0.01, 0)), _ad(p, (0, self.S * 0.012)),
                                 _ad(p, (-self.S * 0.01, 0))], LOI_CORE + (int(230 * rk),))
        if f in (2, 3) and not self.D:
            loi_flash(cv, g, self.S * 0.12, 1.0)


class DiaChanLoi(Vfx):
    """Địa chấn lôi – gõ: sét chạy dọc mặt chữ sang hai bên, đất nứt, đá văng; xoá: sét từ hai đầu chạy dồn vào con trỏ,
    đá bị hút ngược về."""
    name, frames, anchor, box = "diachan", 16, (0.5, 0.78), (2.0, 0.95)

    def init(self):
        r = self.rnd
        self.g = self.c
        self.runs = []
        for sgn in (-1, 1):
            e = (self.g[0] + sgn * self.W * 0.47, self.g[1] + r.uniform(-0.03, 0.03) * self.S)
            a, b = (e, self.g) if self.D else (self.g, e)
            self.runs.append(LoiBolt(a, b, self.S * 0.016, r, branches=4, depth=1, kink=(0.02, 0.05), spread=(40, 75)))
        self.cracks = []
        for sgn in (-1, 1):
            pts, x = [self.g], self.g[0]
            while abs(x - self.g[0]) < self.W * 0.4:
                x += sgn * r.uniform(0.04, 0.08) * self.S
                pts.append((x, self.g[1] + r.uniform(-0.01, 0.025) * self.S))
            self.cracks.append(pts)

    def update(self, f, t):
        g = self.g
        if not self.D and f in (2, 5):
            for _ in range(7):
                x = g[0] + self.rnd.uniform(-0.6, 0.6) * self.S
                self.parts.append(Part(x, g[1], self.rnd.uniform(-1, 1) * self.S * 0.012, -self.S * self.rnd.uniform(0.03, 0.06),
                                       14, self.S * 0.018, "rock", 0.97, self.S * 0.006, rot=self.rnd.uniform(0, 360), vr=20))
        if self.D and f in (1, 4):
            for _ in range(6):
                sx = self.rnd.choice((-1, 1)) * self.rnd.uniform(0.4, 0.8) * self.S
                self.parts.append(Part(g[0] + sx, g[1] - self.S * 0.12, -sx * 0.09, self.S * 0.01, 11, self.S * 0.016,
                                       "rock", 0.95, 0.0, rot=20, vr=-25))

    def draw(self, cv, f, t):
        pw = self.pulse(f) * self.power
        if not self.D:
            g, tail = _eo(_ph(t, 0, 0.3)), _ph(t, 0.55, 0.92)
        else:
            g, tail = _ei(_ph(t, 0, 0.45)), _ph(t, 0.5, 0.85)
        ck = _ph(t, 0.05, 0.3) * (1 - _ph(t, 0.75, 1.0))
        for pts in self.cracks:
            n = max(2, int(len(pts) * (g if not self.D else 1)))
            cv.line("base", pts[:n], LOI_DARK + (int(255 * ck),), self.S * 0.012)
            cv.line("glow", pts[:n], LOI_MID + (int(180 * ck),), self.S * 0.02)
        for b in self.runs:
            b.draw(cv, g, tail, pw, self.S * 0.004, self.jr)
        if (not self.D and f < 2) or (self.D and 0.42 < t < 0.65):
            loi_flash(cv, self.g, self.S * 0.08, 1.0)
        k = _ph(t, 0, 0.5) if not self.D else 1 - _ph(t, 0, 0.5)
        if 0 < k < 1:
            loi_ring(cv, self.g, self.S * (0.1 + 0.8 * k), self.S * (0.02 + 0.06 * k), 1 - abs(2 * k - 1), self.S * 0.008)


class LoiXich(Vfx):
    """Lôi xích liên hoàn – gõ: sét nhảy cung qua các chữ phía trước rồi dồn vào chữ vừa gõ;
    xoá: sét bật khỏi chữ vừa xoá, nhảy lùi sang trái, chữ bị đi qua cháy sém."""
    name, frames, anchor, box = "chain", 18, (0.9, 0.62), (2.2, 0.8)

    def init(self):
        r = self.rnd
        n = 5
        self.nodes = [(self.c[0] - k * self.S * 0.36 + r.uniform(-0.04, 0.04) * self.S,
                       self.c[1] - r.uniform(0.0, 0.1) * self.S) for k in range(n)]
        self.nodes[0] = self.c
        order = self.nodes[::-1] if not self.D else self.nodes
        self.hops = [LoiBolt(a, b, self.S * 0.015, r, branches=2, depth=1, lift=0.35) for a, b in zip(order, order[1:])]
        self.order = order

    def update(self, f, t):
        i = f // 3
        if f % 3 == 1 and i < len(self.hops):
            p = self.order[i + 1]
            self.emit(5, p, self.S * 0.03, 8, self.S * 0.009, "spark")

    def draw(self, cv, f, t):
        for i, h in enumerate(self.hops):
            a = f - i * 3
            if a < 0:
                continue
            grow = _eo(a / 2.0)
            tail = _c01((a - 3) / 4.0)
            pw = (0.7, 1.0, 1.0, 0.6, 0.8, 0.4, 0.25)[min(6, a)] * self.power
            h.draw(cv, grow, tail, pw, self.S * 0.004, self.jr)
            if a in (2, 3):
                loi_flash(cv, self.order[i + 1], self.S * 0.05, 0.9)
        if self.D:                                               # chữ bị sét đi qua: vết cháy hắc tím
            for i, p in enumerate(self.order[1:]):
                a = f - i * 3 - 2
                if a >= 0:
                    k = 1 - _c01(a / 9.0)
                    cv.ell("aura", p, self.S * 0.08, self.S * 0.05, LOI_AURA + (int(200 * k),))
                    cv.ell("base", p, self.S * 0.018, self.S * 0.018, LOI_MID + (int(200 * k),))
        last = len(self.hops) * 3
        if not self.D and last - 1 <= f <= last + 2:
            loi_flash(cv, self.c, self.S * 0.09, 1 - (f - last + 1) / 4.0)


def dragon_head(cv, h, behind, L, f, pw, al, style, S):
    """Đầu rồng dùng chung (Lôi long / Ma độc long): sọ đặc mõm dài, hàm dưới há theo nhịp, nanh, sừng răng cưa,
    bờm, râu, mắt xếch. style 'loi' = viền sét tím; 'doc' = viền độc xanh, mắt xanh."""
    d = math.degrees(math.atan2(h[1] - behind[1], h[0] - behind[0]))
    up = 1 if math.cos(math.radians(d)) >= 0 else -1                 # bay sang trái: lật để đầu không lộn ngược
    ux, uy = _dv(d)
    vx, vy = -uy * up, ux * up
    X = lambda x, y: (h[0] + (ux * x + vx * y) * L, h[1] + (uy * x + vy * y) * L)
    ja = math.radians(14 + 18 * abs(math.sin(f * 0.8)))
    J = lambda x, y: X(0.12 + (x - 0.12) * math.cos(ja) - (y - 0.1) * math.sin(ja),
                       0.1 + (x - 0.12) * math.sin(ja) + (y - 0.1) * math.cos(ja))
    head = [(-0.35, 0.05), (-0.32, -0.22), (-0.05, -0.33), (0.18, -0.24), (0.55, -0.17), (0.92, -0.11), (1.06, -0.03),
            (0.98, 0.05), (0.55, 0.07), (0.15, 0.12), (-0.2, 0.16)]
    jaw = [(0.12, 0.1), (0.92, 0.12), (0.88, 0.2), (0.42, 0.25), (0.08, 0.22)]
    a8 = int(255 * al)
    doc = style == "doc"
    fill = (46, 12, 60) if doc else LOI_DARK
    rim = (100, 235, 80)
    if doc:
        cv.poly("base", [J(*q) for q in [(0.3, 0.12), (0.8, 0.13), (0.75, 0.18), (0.35, 0.2)]], (150, 20, 40, a8))   # họng đỏ
    for poly_ in ([J(*q) for q in jaw], [X(*q) for q in head]):
        cv.poly("aura", poly_, ((18, 50, 12) if doc else LOI_AURA) + (int(170 * al),))
        if doc:
            cv.poly("base", poly_, rim + (a8,))
            cv.poly("base", [_lp(_lp(poly_[0], poly_[len(poly_) // 2], 0.5), q, 0.9) for q in poly_], fill + (a8,))
        else:
            cv.poly("base", poly_, fill + (a8,))
            loi_stroke(cv, poly_ + [poly_[0]], [S * 0.008] * (len(poly_) + 1), pw)
    if doc:                                                           # vảy đầu
        for x in (0.25, 0.45, 0.65):
            cv.line("base", [X(x - 0.06, -0.2), X(x, -0.13), X(x + 0.06, -0.18)], (110, 60, 140, a8), max(1, S * 0.004))
    for x in (0.3, 0.5, 0.7, 0.86):                                   # răng nanh
        cv.poly("base", [X(x - 0.04, 0.07), X(x + 0.03, 0.07), X(x - 0.01, 0.17)], (235, 240, 225, a8) if doc else LOI_CORE + (a8,))
        cv.poly("base", [J(x - 0.04, 0.12), J(x + 0.03, 0.12), J(x, 0.03)], (235, 240, 225, a8) if doc else LOI_CORE + (a8,))
    for (bx, by), (tx, ty) in (((-0.05, -0.3), (-1.0, -0.75)), ((-0.25, -0.2), (-0.95, -0.35))):   # sừng răng cưa
        pts = [X(bx, by), X(bx + (tx - bx) * 0.35, by + (ty - by) * 0.35 - 0.08), X(bx + (tx - bx) * 0.7, by + (ty - by) * 0.7 + 0.05),
               X(tx, ty)]
        ws = [S * 0.017, S * 0.012, S * 0.007, 0]
        if doc:
            cv.poly("base", taper_poly(pts, ws, 1.25), rim + (a8,))
            cv.poly("base", taper_poly(pts, ws, 1.0), (70, 22, 92, a8))
        else:
            loi_stroke(cv, pts, ws, pw)
    for k in range(4):                                                # bờm sau gáy
        a = X(-0.3, -0.1 + k * 0.08)
        tip = X(-0.85 - 0.1 * math.sin(f + k), 0.1 + k * 0.18)
        if doc:
            cv.poly("base", taper_poly([a, _lp(a, tip, 0.5), tip], [S * 0.012, S * 0.008, 0]), (60, 18, 80, a8))
        else:
            loi_stroke(cv, [a, _lp(a, tip, 0.5), tip], [S * 0.007, S * 0.005, 0], pw * 0.8)
    for x in (0.72, 0.9):                                             # râu
        a = X(x, 0.0)
        pts = [a, X(x - 0.2, 0.35), X(x - 0.45, 0.55)]
        if doc:
            cv.line("base", pts, rim + (int(200 * al),), max(1, S * 0.005))
        else:
            loi_stroke(cv, pts, [S * 0.005, S * 0.004, 0], pw * 0.8)
    eye_g = (120, 255, 80) if doc else LOI_MID
    cv.poly("glow", [X(0.02, -0.24), X(0.34, -0.15), X(0.02, -0.08)], eye_g + (int(240 * max(pw, 0.6) * al),))
    cv.poly("base", [X(0.1, -0.2), X(0.26, -0.15), X(0.1, -0.12)], ((230, 255, 200) if doc else LOI_CORE) + (a8,))


class LoiLong(Vfx):
    """Lôi long – gõ: rồng sét (thân 3 dải sét bện) bay lượn trên dòng chữ tới con trỏ rồi giáng đầu xuống, nổ;
    xoá: rồng sét trồi lên từ chỗ xoá, kéo thân bay lùi sang trái rồi tan rã."""
    name, frames, anchor, box = "dragon", 22, (0.86, 0.74), (2.3, 1.25)

    def init(self):
        r = self.rnd
        self.zz = [[r.uniform(-1, 1) for _ in range(80)] for _ in range(3)]
        self.x0, self.x1 = self.W * 0.04, self.c[0]
        self.amp = self.S * 0.16
        self.base = self.c[1] - self.S * 0.42
        self.burst = [LoiBolt(self.c, _ad(self.c, _dv(a), self.S * r.uniform(0.22, 0.32)), self.S * 0.013, r, 2, 1)
                      for a in (200, 240, 270, 300, 340)]

    def C(self, s):
        x = self.x0 + (self.x1 - self.x0) * s
        y = self.base - self.amp * math.sin(s * 2.4 * math.pi) * (1 - 0.6 * s)
        if s > 0.9:
            y += (self.c[1] - y) * _ei((s - 0.9) / 0.1)
        return (x, y)

    def update(self, f, t):
        if not self.D and f == 15:
            self.emit(16, self.c, self.S * 0.05, 10, self.S * 0.011, "spark", spread=(180, 360))
        if self.D and f == 0:
            self.emit(10, self.c, self.S * 0.04, 10, self.S * 0.01, "spark", spread=(180, 360))
        if f % 3 == 0 and f < 16:
            s = self._head_s(t)
            self.parts.append(Part(*self.C(max(0, s - 0.08)), self.rnd.uniform(-0.5, 0.5), self.rnd.uniform(0.2, 0.8), 10,
                                   self.S * 0.01, "mote", 0.95, 0.05))

    def _head_s(self, t):
        return (_eo(_ph(t, 0.0, 0.68))) if not self.D else 1 - _eo(_ph(t, 0.05, 0.75))

    def draw(self, cv, f, t):
        hs = self._head_s(t)
        blen = 0.55
        dis = _ph(t, 0.72, 1.0) if not self.D else _ph(t, 0.68, 1.0)
        pw = self.pulse(f, (1, 0.75, 1, 0.5, 0.9, 0.65)) * self.power * (1 - 0.7 * dis)
        n = 34
        sp = []
        for i in range(n):
            s = hs - blen * i / (n - 1) if not self.D else hs + blen * i / (n - 1)
            if 0 <= s <= 1:
                sp.append(self.C(s))
        if len(sp) >= 3:
            keep = int(len(sp) * (1 - dis))                    # phân rã từ đuôi lên đầu
            body = sp[:max(2, keep)]
            nm = _norms(body)
            core_w = [self.S * 0.05 * (1 - 0.8 * i / float(max(1, len(body) - 1))) for i in range(len(body))]
            core_w[-1] = 0
            cv.poly("aura", taper_poly(body, core_w, 1.6), LOI_AURA + (int(140 * (1 - dis)),))
            cv.poly("base", taper_poly(body, core_w, 0.75), LOI_DARK + (int(200 * (1 - dis)),))   # khối thân hắc tím
            for k in range(3):                                  # 3 dải sét bện xoắn quanh xương sống
                pts, ws = [], []
                for i, (p, q) in enumerate(zip(body, nm)):
                    u = i / float(max(1, len(body) - 1))
                    off = math.sin(i * 0.7 + k * 2.1 + f * 0.6) * self.S * 0.04 * (1 - 0.6 * u) + self.zz[k][i] * self.S * 0.006
                    pts.append((p[0] + q[0] * off, p[1] + q[1] * off))
                    ws.append(self.S * 0.014 * (1 - 0.75 * u) * (1.25 if k == 0 else 0.75))
                ws[-1] = 0
                loi_stroke(cv, pts, ws, pw, 0.0 if k == 0 else 1.0)
            for i in range(3, len(body) - 3, 3):                # vây gai sét dọc lưng (răng cưa, nhọn)
                p, q = body[i], nm[i]
                u = i / float(len(body))
                h = self.S * 0.09 * (1 - 0.6 * u)
                tip = (p[0] - q[0] * h, p[1] - q[1] * h)
                bk = _ad(p, (q[1], -q[0]), -self.S * 0.02)
                loi_stroke(cv, [bk, _lp(bk, tip, 0.5), tip], [self.S * 0.008, self.S * 0.006, 0], pw * 0.85)
            if dis < 0.6:
                dragon_head(cv, body[0], body[3], self.S * 0.24, f, pw, 1 - dis, "loi", self.S)
        if not self.D and 14 <= f <= 19:
            a = f - 14
            for b in self.burst:
                b.draw(cv, _eo(a / 2.0), _c01((a - 2) / 3.0), 1.0)
            if a < 3:
                loi_flash(cv, self.c, self.S * 0.1, 1.0)


class LoiThuong(Vfx):
    """Lôi thương – gõ: giáo sét lao chéo từ trên xuống cắm xuyên chữ, nổ chấn, giáo rung điện rồi tan;
    xoá: giáo đang cắm bị rút phăng ra, bay ngược lên kéo theo tia lửa."""
    name, frames, anchor, box = "gai", 16, (0.36, 0.72), (1.55, 1.25)

    def init(self):
        r = self.rnd
        self.start = (self.W * 1.02, self.H * 0.0)
        d = math.atan2(self.c[1] - self.start[1], self.c[0] - self.start[0])
        self.dir = (math.cos(d), math.sin(d))
        self.ang = math.degrees(d)
        self.len = self.S * 0.62
        self.shaft = LoiBolt((-self.len, 0), (0, 0), self.S * 0.02, r, branches=3, depth=1, kink=(0.015, 0.04),
                             spread=(150, 170), blen=(0.15, 0.28))
        self.burst = [LoiBolt(self.c, _ad(self.c, _dv(a), self.S * r.uniform(0.18, 0.3)), self.S * 0.012, r, 1, 1)
                      for a in (r.uniform(100, 140), r.uniform(150, 200), r.uniform(-30, 20), r.uniform(30, 70))]

    def _tip(self, t):
        if not self.D:
            k = _ei(_ph(t, 0, 0.28))
            return _lp(self.start, _ad(self.c, self.dir, self.S * 0.05), k)
        k = _ei(_ph(t, 0.25, 0.7))
        return _lp(_ad(self.c, self.dir, self.S * 0.05), self.start, k)

    def update(self, f, t):
        if not self.D and f == 4:
            self.emit(18, self.c, self.S * 0.05, 11, self.S * 0.011, "spark", drag=0.88)
            self.emit(5, self.c, self.S * 0.01, 12, self.S * 0.05, "smoke")
        if self.D and 4 <= f <= 9:
            tip = self._tip(f / float(self.n - 1))
            self.emit(3, tip, self.S * 0.02, 8, self.S * 0.009, "spark", spread=(self.ang + 160, self.ang + 200))

    def draw(self, cv, f, t):
        tip = self._tip(t)
        a = math.radians(self.ang)
        co, si = math.cos(a), math.sin(a)
        xf = lambda p: (tip[0] + p[0] * co - p[1] * si, tip[1] + p[0] * si + p[1] * co)
        moving = (t < 0.28) if not self.D else (0.25 < t < 0.7)
        stuck = (not self.D and 0.28 <= t) or (self.D and t <= 0.25)
        fade = _ph(t, 0.65, 0.95) if not self.D else _ph(t, 0.6, 0.85)
        pw = (self.pulse(f) if stuck else 1.0) * self.power * (1 - fade)
        if moving:                                               # bóng mờ phía sau khi lao nhanh
            for g_ in (2, 1):
                back = _ad(tip, self.dir, -self.S * 0.12 * g_)
                xb = lambda p, back=back: (back[0] + p[0] * co - p[1] * si, back[1] + p[0] * si + p[1] * co)
                self.shaft.draw(cv, 1, 0, 0.25 / g_, 0, None, xf=xb)
        self.shaft.draw(cv, 1.0, fade, pw, self.S * 0.003, self.jr, xf=xf)
        if pw > 0.05:                                            # mũi giáo hình thoi, lõi trắng
            L, w = self.S * 0.1, self.S * 0.035
            head = [xf((L * 0.9, 0)), xf((0, w)), xf((-L * 0.35, 0)), xf((0, -w))]
            cv.poly("glow", head, LOI_MID + (int(220 * pw),))
            cv.poly("base", head, LOI_EDGE + (int(255 * pw),))
            cv.poly("base", [xf((L * 0.75, 0)), xf((0, w * 0.5)), xf((-L * 0.2, 0)), xf((0, -w * 0.5))], LOI_CORE + (int(255 * pw),))
        if not self.D and 4 <= f <= 9:
            k = f - 4
            for b in self.burst:
                b.draw(cv, _eo(k / 1.5), _c01((k - 2) / 3.0), 1.0)
            loi_ring(cv, self.c, self.S * (0.06 + 0.07 * k), self.S * (0.03 + 0.03 * k), 1 - k / 6.0, self.S * 0.008)
            if k < 2:
                loi_flash(cv, self.c, self.S * 0.1, 1.0)
        if self.D and 3 <= f <= 7:
            loi_flash(cv, self.c, self.S * 0.06, 1 - (f - 3) / 5.0)


class TuLoiBungNo(Vfx):
    """Tử lôi bùng nổ – gõ: chớp trắng, vòm xung kích, 10 tia sét toả lên, đá văng, khói hắc tím bốc;
    xoá: khói và đá bị hút ngược vào điểm kỳ dị đen, tia sét sập vào, nổ bật nhỏ rồi tắt."""
    name, frames, anchor, box = "tuno", 18, (0.5, 0.78), (1.7, 1.35)

    def init(self):
        r = self.rnd
        self.rays = []
        for k in range(10):
            a = 185 + k * 17 + r.uniform(-6, 6)
            L = self.S * r.uniform(0.38, 0.62)
            out = _ad(self.c, _dv(a), L)
            p0, p1 = (out, self.c) if self.D else (self.c, out)
            self.rays.append(LoiBolt(p0, p1, self.S * 0.02, r, branches=3, depth=2))

    def update(self, f, t):
        c = self.c
        if not self.D:
            if f == 1:
                self.emit(14, c, self.S * 0.05, 18, self.S * 0.022, "rock", spread=(200, 340), drag=0.97, grav=self.S * 0.005)
                self.emit(20, c, self.S * 0.06, 10, self.S * 0.012, "spark", spread=(180, 360), drag=0.86)
            if f in (2, 4, 6, 8):
                self.emit(4, c, self.S * 0.012, 16, self.S * 0.08, "smoke", spread=(220, 320), drag=0.95, grav=-0.12,
                          radius=self.S * 0.15)
        else:
            if f in (0, 2, 4, 6):
                self.emit(4, c, self.S * 0.045, 11, self.S * 0.07, "smoke", spread=(180, 360), inward=True,
                          radius=self.S * 0.55, drag=0.97)
            if f in (1, 5):
                self.emit(6, c, self.S * 0.05, 10, self.S * 0.02, "rock", spread=(180, 360), inward=True, radius=self.S * 0.55,
                          drag=0.97)

    def draw(self, cv, f, t):
        c = self.c
        pw = self.pulse(f) * self.power
        if not self.D:
            if f <= 1:
                cv.ell("glow", c, self.S * 0.5, self.S * 0.35, LOI_CORE + (200,))
                loi_flash(cv, c, self.S * 0.16, 1.0)
            k = _eo(_ph(t, 0.02, 0.5))
            if k < 1:
                loi_ring(cv, c, self.S * (0.1 + 0.6 * k), self.S * (0.06 + 0.42 * k), 1 - k, self.S * 0.014)
            g, tail = _eo(_ph(t, 0.03, 0.22)), _ph(t, 0.5, 0.88)
            for b in self.rays:
                b.draw(cv, g, tail, pw, self.S * 0.006, self.jr)
        else:
            g, tail = _ei(_ph(t, 0.05, 0.4)), _ph(t, 0.4, 0.72)
            for b in self.rays:
                b.draw(cv, g, tail, pw, self.S * 0.006, self.jr)
            core = self.S * (0.04 + 0.06 * _ph(t, 0, 0.5)) * (1 - _ph(t, 0.7, 0.85))
            cv.ell("aura", c, core * 3.2, core * 3.2, LOI_AURA + (210,))
            cv.ell("base", c, core, core, (6, 0, 12, 255))
            cv.ell_ring("base", c, core, core, LOI_MID + (255,), 1.5)
            if 0.82 < t < 0.98:
                loi_flash(cv, c, self.S * 0.1, 1 - _ph(t, 0.82, 0.98))


class MaTrao(Vfx):
    """Ma trảo – gõ: cổng hắc khí mở, 4 móng vuốt vươn ra rồi cào xé chéo qua chữ, để lại vết cào điện,
    móng tan thành khói; xoá: móng vuốt chụp lấy chữ, siết lại rồi lôi tuột vào cổng hắc khí bên trái."""
    name, frames, anchor, box = "slash", 18, (0.5, 0.55), (1.35, 1.25)

    def init(self):
        r = self.rnd
        S, c = self.S, self.c
        if not self.D:
            self.p0 = (c[0] + S * 0.42, c[1] - S * 0.4)            # cổng mở phía trên phải
            self.p1 = (c[0] - S * 0.35, c[1] + S * 0.3)            # cào chéo xuống trái
        else:
            self.p0 = (c[0] + S * 0.05, c[1])
            self.p1 = (c[0] - S * 0.55, c[1] - S * 0.05)           # lôi về cổng bên trái
        self.marks = []
        for k in range(4):
            o = (k - 1.5) * S * 0.07
            a = (c[0] + S * 0.32 + o, c[1] - S * 0.32 + o)
            b = (c[0] - S * 0.28 + o, c[1] + S * 0.26 + o)
            m = (c[0] + o * 1.5 + S * 0.06, c[1] + o * 1.5 - S * 0.06)
            self.marks.append([_lp(_lp(a, m, u), _lp(m, b, u), u) for u in [i / 14.0 for i in range(15)]])
        self.noise = make_noise(int(self.W) + 8, int(self.H) + 8, self.seed + 3)

    def _claws(self, cv, base, ang, ext, curl, al):
        """4 móng: thân tối, mép tím điện, lõi sáng. ext = độ vươn, curl = độ quặp."""
        S = self.S
        for k in range(4):
            spread = (k - 1.5) * 15
            d = ang + spread
            root = _ad(base, _dv(d + 90), (k - 1.5) * S * 0.035)
            L = S * (0.26 if k in (1, 2) else 0.2) * ext
            pts = [root]
            for i in range(1, 7):
                u = i / 6.0
                pts.append(_ad(root, _dv(d + curl * 70 * u * u), L * u))
            ws = [S * 0.028 * (1 - i / 6.0) + 0.3 for i in range(7)]
            ws[-1] = 0
            cv.poly("aura", taper_poly(pts, ws, 2.2), LOI_AURA + (int(150 * al),))
            cv.poly("base", taper_poly(pts, ws, 1.35), LOI_MID + (int(255 * al),))
            cv.poly("base", taper_poly(pts, ws, 1.0), (18, 6, 26, int(255 * al)))
            cv.line("base", pts[1:-1], LOI_CORE + (int(220 * al),), max(0.8, S * 0.004))

    def update(self, f, t):
        if 0.3 < t < 0.6 and f % 2 == 0:
            for m in self.marks:
                p = m[min(14, int(_ph(t, 0.3, 0.55) * 14))]
                self.parts.append(Part(p[0], p[1], self.rnd.uniform(-1, 1) * self.S * 0.01, self.rnd.uniform(0, 1) * self.S * 0.01,
                                       10, self.S * 0.009, "spark", 0.9))
        if f in (12, 14, 16):
            pos = _lp(self.p0, self.p1, _ph(t, 0.3, 0.6))
            self.emit(5, pos, self.S * 0.012, 12, self.S * 0.06, "smoke", radius=self.S * 0.1, grav=-0.1)

    def draw(self, cv, f, t):
        S = self.S
        port_k = _eo(_ph(t, 0, 0.2)) * (1 - _ph(t, 0.7, 1.0))
        portal = self.p0 if not self.D else self.p1
        if port_k > 0.02:                                        # cổng hắc khí xoáy
            cv.ell("aura", portal, S * 0.2 * port_k, S * 0.16 * port_k, LOI_AURA + (220,))
            for k in range(3):
                a = f * 25 + k * 120
                arc = [_ad(portal, _dv(a + i * 20), S * 0.12 * port_k * (1 - i * 0.08)) for i in range(8)]
                cv.line("base", arc, LOI_MID + (int(200 * port_k),), S * 0.008)
        if not self.D:
            ext = _eo(_ph(t, 0.12, 0.32))
            sw = _ei(_ph(t, 0.3, 0.52))
            base = _lp(self.p0, self.p1, sw)
            ang = 135 - 30 * sw
            al = 1 - _ph(t, 0.55, 0.85)
            curl = 0.2 + 0.6 * sw
            mark_k = _ph(t, 0.32, 0.52)
        else:
            ext = _eo(_ph(t, 0.0, 0.18))
            curl = 0.1 + 0.9 * _eo(_ph(t, 0.18, 0.36))           # chụp & siết
            pull = _ei(_ph(t, 0.38, 0.78))
            base = _lp(self.p0, self.p1, pull)
            ang = -20 - 20 * pull
            al = 1 - _ph(t, 0.72, 0.95)
            mark_k = 0
        if al > 0.02 and ext > 0.02:
            self._claws(cv, base, ang, ext, curl, al)
        if mark_k > 0 or (not self.D and t > 0.52):              # vết cào: lõi trắng tím, viền tím, tan từ hai đầu
            fade = _ph(t, 0.62, 0.98)
            for m in self.marks:
                n = max(2, int(15 * mark_k)) if t <= 0.52 else 15
                seg = m[:n]
                a0 = int(len(seg) * fade * 0.5)
                seg = seg[a0:len(seg) - a0] if len(seg) - 2 * a0 >= 2 else []
                if len(seg) >= 2:
                    ws = [S * 0.014 * math.sin(math.pi * (i + 0.5) / len(seg)) for i in range(len(seg))]
                    loi_stroke(cv, seg, ws, 1 - fade * 0.6)
        if self.D and 0.18 < t < 0.5:
            loi_flash(cv, self.c, S * 0.05, 1 - _ph(t, 0.18, 0.5))


class MaDocLong(Vfx):
    """Ma độc long – gõ: độc khí bốc từ chữ, rồng độc trồi lên trườn uốn bay đi, nhả độc khí, thân rã thành sương độc;
    xoá: rồng độc từ xa lao bổ vào chữ, thân bị nuốt dần vào điểm xoá, độc khí xoáy hút vào."""
    name, frames, anchor, box = "madoc", 22, (0.25, 0.75), (1.9, 1.35)
    TOX = (110, 235, 80)

    def init(self):
        self.far = (self.W * 0.82, self.H * 0.3)

    def C(self, s):
        """Quỹ đạo uốn lượn: từ chữ (s=0) vòng lên phải (s=1)."""
        c, e = self.c, self.far
        x = c[0] + (e[0] - c[0]) * s
        y = c[1] + (e[1] - c[1]) * (s ** 0.8) - math.sin(s * math.pi * 2.0) * self.S * 0.2
        return (x, y)

    def _hs(self, t):
        return _eo(_ph(t, 0.05, 0.7)) if not self.D else 1 - _ei(_ph(t, 0.0, 0.62))

    def update(self, f, t):
        hs = self._hs(t)
        head = self.C(hs)
        if f % 2 == 0 and t < 0.8:
            tail = self.C(max(0, hs - 0.25)) if not self.D else self.C(min(1, hs + 0.25))
            self.parts.append(Part(tail[0], tail[1], self.rnd.uniform(-0.6, 0.6), -0.4, 16, self.S * 0.05, "gas", 0.96,
                                   col=self.TOX))
            self.parts.append(Part(head[0], head[1], self.rnd.uniform(-1, 1), 0.5, 12, self.S * 0.01, "drop", 0.97,
                                   self.S * 0.004, col=(130, 255, 90)))
        if not self.D and f < 4:
            self.emit(3, self.c, self.S * 0.01, 14, self.S * 0.05, "gas", spread=(240, 300), col=self.TOX, grav=-0.15)
        if not self.D and t > 0.72 and f % 2 == 0:
            for s in (hs - 0.1, hs - 0.2, hs - 0.3):
                p = self.C(max(0, s))
                self.parts.append(Part(p[0], p[1], self.rnd.uniform(-1, 1), -0.3, 14, self.S * 0.06, "gas", 0.95, col=self.TOX))
        if self.D and f in (8, 11, 14):
            self.emit(5, self.c, self.S * 0.03, 10, self.S * 0.05, "gas", inward=True, radius=self.S * 0.4, col=self.TOX,
                      drag=0.97)

    def draw(self, cv, f, t):
        S = self.S
        hs = self._hs(t)
        n = 20
        blen = 0.42
        dis = _ph(t, 0.72, 1.0) if not self.D else _ph(t, 0.7, 0.9)
        segs = []
        for i in range(n):
            s = hs - blen * i / (n - 1) if not self.D else hs + blen * i / (n - 1)
            if self.D and s > 1:
                break
            if not self.D and s < 0:
                break
            if self.D and hs <= 0.001 and i > 0:
                break
            segs.append((self.C(max(0.0, min(1.0, s))), i))
        if self.D:                                               # bị nuốt vào chữ: các đốt chạm điểm xoá biến mất
            segs = [(p, i) for p, i in segs if math.hypot(p[0] - self.c[0], p[1] - self.c[1]) > S * 0.04 or i == 0]
        keep = int(len(segs) * (1 - dis))
        segs = segs[:keep] if not self.D else (segs if dis < 0.5 else [])
        if len(segs) >= 2:                                       # thân liền khối: tím đen, viền độc xanh, vảy, gai lưng
            pts = [p for p, i in segs]
            ws = [S * (0.065 * (1 - 0.75 * i / float(n)) + 0.01) for p, i in segs]
            ws[-1] = S * 0.006
            cv.poly("aura", taper_poly(pts, ws, 2.0), (20, 55, 14, 110))
            cv.poly("base", taper_poly(pts, ws, 1.18), (96, 228, 72, 240))
            cv.poly("base", taper_poly(pts, ws, 1.0), (46, 12, 60, 255))
            nm = _norms(pts)
            if sum(q[1] for q in nm) > 0:                          # pháp tuyến phía lưng = phía hướng lên màn hình
                nm = [(-q[0], -q[1]) for q in nm]
            belly = [(p[0] - q[0] * w * 0.45, p[1] - q[1] * w * 0.45) for p, q, w in zip(pts, nm, ws)]
            cv.line("base", belly, (110, 70, 130, 200), max(1, S * 0.008))
            for k in range(1, len(pts) - 1):
                p, q, w = pts[k], nm[k], ws[k]
                a, b = (p[0] + q[0] * w * 0.8, p[1] + q[1] * w * 0.8), (p[0] - q[0] * w * 0.3, p[1] - q[1] * w * 0.3)
                cv.line("base", [a, _lp(a, b, 0.5), b], (90, 40, 115, 220), max(1, S * 0.004))    # vân vảy
                if k % 2 == 0:
                    tip = (p[0] + q[0] * w * 2.1, p[1] + q[1] * w * 2.1)
                    sd = (q[1] * w * 0.5, -q[0] * w * 0.5)
                    base1 = (p[0] + q[0] * w * 0.9 + sd[0], p[1] + q[1] * w * 0.9 + sd[1])
                    base2 = (p[0] + q[0] * w * 0.9 - sd[0], p[1] + q[1] * w * 0.9 - sd[1])
                    cv.poly("base", [base1, tip, base2], (66, 20, 86, 255))
                    cv.line("base", [base1, tip], (100, 230, 80, 200), 1)
        if segs and segs[0][1] == 0 and dis < 0.7:               # đầu rồng (dùng chung kiểu đầu với Lôi long)
            behind = segs[min(3, len(segs) - 1)][0] if len(segs) > 1 else _ad(segs[0][0], (-1, 1))
            dragon_head(cv, segs[0][0], behind, S * 0.22, f, 1.0, 1 - dis, "doc", S)
        if self.D and 0.62 < t < 0.85:
            k = _ph(t, 0.62, 0.85)
            cv.ell("glow", self.c, S * 0.1 * (1 - k), S * 0.1 * (1 - k), (130, 255, 90, int(220 * (1 - k))))
            loi_flash(cv, self.c, S * 0.06, 1 - k)


class BiNganHoa(Vfx):
    """Bỉ ngạn hoa – gõ: thân mọc từ chữ, nụ hình thành, 6 cánh cong ngược mở lần lượt, nhuỵ dài vươn ra,
    cánh rơi, hoa héo rồi tan thành bụi đỏ; xoá: hoa đang nở bị giật ngược – cánh xé bay hút vào chữ, thân rút xuống."""
    name, frames, anchor, box = "bingan", 24, (0.5, 0.94), (1.15, 1.55)
    RED, DARK, LIGHT = (214, 20, 44), (110, 0, 22), (255, 120, 140)

    def init(self):
        r = self.rnd
        self.top = (self.c[0] + r.uniform(-0.06, 0.06) * self.S, self.c[1] - self.S * 0.78)
        self.ctrl = (self.c[0] + r.uniform(-0.15, 0.15) * self.S, self.c[1] - self.S * 0.4)
        self.petals = [(k * 60 + r.uniform(-10, 10) - 90, r.uniform(0.9, 1.1)) for k in range(6)]
        self.F = self.top
        self.stam = [(-90 + (k - 2.5) * 26 + r.uniform(-6, 6), r.uniform(0.95, 1.2)) for k in range(6)]

    def stem(self, k):
        pts = []
        for i in range(13):
            u = i / 12.0 * k
            pts.append(_lp(_lp(self.c, self.ctrl, u), _lp(self.ctrl, self.top, u), u))
        return pts

    def petal(self, a, open_, droop, scale):
        """Cánh bỉ ngạn: dải hẹp vươn ra rồi cong ngược ra sau."""
        F, S = self.F, self.S
        L = S * 0.3 * scale
        pts = []
        for i in range(9):
            u = i / 8.0
            ang = a + (1 - open_) * (-90 - a) * 0.85 + (u * u * 110 * open_) * (1 if math.cos(math.radians(a)) >= 0 else -1) + droop * 60 * u
            pts.append(_ad(pts[-1] if pts else F, _dv(ang), L / 8.0 if pts else 0))
        ws = [S * 0.024 * math.sin(math.pi * min(0.95, (i + 0.6) / 9.0)) for i in range(9)]
        ws[-1] = 0
        return pts, ws

    def update(self, f, t):
        if 0.4 < t < 0.8 and f % 2 == 0:
            self.emit(2, self.F, self.S * 0.012, 16, self.S * 0.011, "mote", spread=(200, 340), grav=-0.12, col=(255, 60, 90),
                      radius=self.S * 0.2)
        if not self.D and t > 0.55 and f % 2 == 1:
            a, sc = self.petals[(f // 2) % 6]
            p = _ad(self.F, _dv(a), self.S * 0.18)
            self.parts.append(Part(p[0], p[1], self.rnd.uniform(-0.8, 0.8), 0.4, 18, self.S * 0.025, "petal", 0.97, self.S * 0.002,
                                   rot=self.rnd.uniform(0, 360), vr=self.rnd.uniform(-20, 20)))
        if not self.D and f == self.n - 6:
            self.emit(16, self.F, self.S * 0.03, 10, self.S * 0.01, "mote", col=(255, 50, 80), radius=self.S * 0.2, grav=-0.1)
        if self.D and f in (6, 8, 10):
            for a, sc in self.petals[(f - 6):(f - 6) + 2]:
                p = _ad(self.F, _dv(a), self.S * 0.2)
                dx, dy = self.c[0] - p[0], self.c[1] - p[1]
                self.parts.append(Part(p[0], p[1], dx * 0.12, dy * 0.12, 8, self.S * 0.03, "petal", 1.0, rot=a, vr=40))

    def draw(self, cv, f, t):
        S = self.S
        if not self.D:
            sk = _eo(_ph(t, 0.0, 0.25))
            bud = _ph(t, 0.18, 0.3)
            wither = _ph(t, 0.72, 0.95)
            stem_al = 1 - _ph(t, 0.85, 1.0)
        else:
            sk = 1 - _ei(_ph(t, 0.45, 0.85))
            bud = 1.0
            wither = 0.0
            stem_al = 1 - _ph(t, 0.8, 1.0)
        st = self.stem(sk)
        if len(st) >= 2 and stem_al > 0.02:
            col = tuple(int(c * (1 - 0.5 * wither)) for c in (40, 120, 50))
            cv.line("base", st, col + (int(255 * stem_al),), S * 0.014)
            cv.line("glow", st, (200, 30, 60, int(90 * stem_al)), S * 0.02)
        F = st[-1] if st else self.c
        self.F = F
        if bud <= 0 or (sk < 0.9 and not self.D) or (self.D and t > 0.6):
            return
        col = tuple(int(self.RED[i] * (1 - wither) + self.DARK[i] * wither) for i in range(3))
        gk = (1 - wither) * (1 if not self.D else 1 - _ph(t, 0.2, 0.5))
        if gk > 0.02:
            cv.ell("glow", F, S * 0.07, S * 0.07, (230, 30, 70, int(150 * gk)))
            cv.ell("aura", F, S * 0.16, S * 0.16, (60, 0, 20, int(70 * gk)))
        for k, (a, sc) in enumerate(self.petals):
            if not self.D:
                op = _eo(_ph(t, 0.28 + k * 0.04, 0.5 + k * 0.04))
                al = 1 - _ph(t, 0.8 + k * 0.02, 0.98)
            else:
                torn = _ph(t, 0.22 + k * 0.05, 0.3 + k * 0.05)   # cánh bị xé lần lượt
                op = 1 - 0.5 * torn
                al = 1 - torn
            if al <= 0.02:
                continue
            pts, ws = self.petal(a, max(0.15, op) * bud, wither, sc)
            cv.poly("base", taper_poly(pts, ws, 1.3), self.DARK + (int(255 * al),))
            cv.poly("base", taper_poly(pts, ws, 1.0), col + (int(255 * al),))
            cv.line("base", pts[:-2], self.LIGHT + (int(200 * al * (1 - wither)),), max(0.7, S * 0.005))
        for a, sc in self.stam:                                  # nhuỵ dài cong, đầu nhuỵ sáng
            ok = _eo(_ph(t, 0.42, 0.62)) * (1 - _ph(t, 0.75, 0.9)) if not self.D else 1 - _ph(t, 0.15, 0.4)
            if ok <= 0.02:
                continue
            L = S * 0.36 * sc * ok
            pts = [F]
            for i in range(1, 7):
                u = i / 6.0
                pts.append(_ad(pts[-1], _dv(a + u * u * 55 * (1 if a > -90 else -1) + wither * 40 * u), L / 6.0))
            cv.line("base", pts, (230, 40, 60, int(255 * ok)), max(0.8, S * 0.005))
            cv.ell("glow", pts[-1], S * 0.02, S * 0.02, (255, 90, 120, int(200 * ok)))
            cv.ell("base", pts[-1], S * 0.008, S * 0.008, (255, 230, 200, int(255 * ok)))


class DauLauQuy(Vfx):
    """Đầu lâu quỷ – gõ: khói tụ lại, đầu lâu hiện ra từ khói (tan-hiện theo nhiễu), bay lên lắc lư, mắt rực tím,
    kéo đuôi linh hồn, cuối cùng rã thành bụi hồn; xoá: đầu lâu hiện trên cao, há miệng lao bổ xuống chữ rồi vỡ vụn."""
    name, frames, anchor, box = "skull", 22, (0.5, 0.92), (1.0, 1.75)

    def init(self):
        r = self.rnd
        rad = max(6, int(self.S * 0.12))
        self.sk = [self._tint(_horror_skull(rad, j, 1.0, self.seed)) for j in (0.0, 1.0)]
        w = max(i.width for i in self.sk)
        h = max(i.height for i in self.sk)
        self.noise = make_noise(w + 8, h + 8, self.seed + 11, cell=max(3, w // 10))
        self.sway = r.uniform(0.6, 1.0) * r.choice((-1, 1))
        self.y0, self.y1 = self.c[1] - self.S * 0.12, self.S * 0.22

    @staticmethod
    def _tint(im):
        r, g, b, a = im.split()
        gray = Image.merge("RGB", (r, g, b)).convert("L")
        tinted = Image.merge("RGB", (gray.point(lambda v: int(v * 0.72)), gray.point(lambda v: int(v * 0.55)), gray))
        return Image.merge("RGBA", (*tinted.split(), a))

    def pos(self, t):
        if not self.D:
            k = _ph(t, 0.18, 0.92)
            y = self.y0 + (self.y1 - self.y0) * _eo(k)
            x = self.c[0] + math.sin(k * 5.0) * self.S * 0.12 * self.sway
            return (x, y), math.sin(k * 6.0) * 12 * self.sway, 0.75 + 0.35 * k
        k = _ei(_ph(t, 0.28, 0.68))
        y = self.y1 + (self.y0 - self.y1) * k
        return (self.c[0] + math.sin(t * 9) * self.S * 0.03, y), math.sin(t * 20) * 6, 1.0 - 0.2 * k

    def update(self, f, t):
        p, rot, sc = self.pos(t)
        if not self.D:
            if f < 5:
                self.emit(3, (self.c[0], self.y0), self.S * 0.03, 8, self.S * 0.07, "smoke", inward=True, radius=self.S * 0.3,
                          drag=0.95)
            if 4 < f < self.n - 5 and f % 2 == 0:
                self.parts.append(Part(p[0] + self.rnd.uniform(-0.05, 0.05) * self.S, p[1] + self.S * 0.12,
                                       self.rnd.uniform(-0.5, 0.5), self.S * 0.012, 12, self.S * 0.012, "soul", 0.93))
            if f == self.n - 6:
                self.emit(14, p, self.S * 0.025, 12, self.S * 0.01, "soul", spread=(200, 340), grav=-0.2, radius=self.S * 0.1)
        else:
            if 6 < f < 14:
                self.parts.append(Part(p[0], p[1] - self.S * 0.1, 0, -self.S * 0.01, 8, self.S * 0.012, "soul", 0.9))
            if f == int(0.68 * (self.n - 1)) + 1:
                self.emit(14, self.c, self.S * 0.05, 12, self.S * 0.02, "shard", spread=(180, 360), grav=self.S * 0.004,
                          col=(205, 195, 230))
                self.emit(5, self.c, self.S * 0.02, 12, self.S * 0.06, "smoke", spread=(180, 360))

    def draw(self, cv, f, t):
        S = self.S
        p, rot, sc = self.pos(t)
        if not self.D:
            appear = _ph(t, 0.05, 0.3)
            gone = _ph(t, 0.74, 0.97)
            jaw = 1 if (f // 2) % 2 and 0.3 < t < 0.75 else 0
        else:
            appear = _ph(t, 0.0, 0.2)
            gone = 1.0 if t > 0.7 else 0.0
            jaw = 1 if t > 0.25 else 0
        if gone >= 1 or appear <= 0:
            return
        thr = (1 - appear) * 0.9 + gone * 0.95                  # hiện ra / tan rã theo nhiễu, mép cháy tím
        im = dissolve(self.sk[jaw], thr, self.noise)
        cv.ell("aura", p, S * 0.16 * sc, S * 0.2 * sc, LOI_AURA + (int(120 * appear * (1 - gone)),))
        cv.stamp(im, p, sc, rot)
        eg = (0.6 + 0.4 * abs(math.sin(f * 1.1))) * appear * (1 - gone)
        sw, sh = self.sk[0].size
        for sx in (-1, 1):                                       # mắt rực tím (hốc mắt ~ 38% chiều cao sọ)
            e = (p[0] + sx * sw * 0.2 * sc, p[1] - sh * 0.1 * sc)
            cv.ell("glow", e, S * 0.05 * sc, S * 0.04 * sc, LOI_MID + (int(240 * eg),))
            cv.ell("base", e, S * 0.013 * sc, S * 0.011 * sc, LOI_CORE + (int(255 * eg),))
        if self.D and 0.6 < t < 0.75:
            loi_flash(cv, self.c, S * 0.08, 1.0)


class SongPhiKiem(Vfx):
    """Song phi kiếm – gõ: 2 kiếm loé hiện tại chữ, xoay ngắm, phóng vút giao nhau ra hai phía, kiếm quang kéo vệt,
    loé sao khi đạt tốc độ; xoá: 2 kiếm từ ngoài lao vào đâm trúng chữ cùng lúc, vỡ thành mảnh sáng."""
    name, frames, anchor, box = "sword", 18, (0.5, 0.62), (1.9, 1.45)

    def init(self):
        r = self.rnd
        L = max(24, int(self.S * 0.5))
        self.img = self._glow(_sword_img(L))
        c = self.c
        if not self.D:                                           # bay giao nhau: kiếm trái bay sang phải-trên và ngược lại
            self.paths = [((c[0] - self.S * 0.12, c[1]), (self.W * 1.15, -self.H * 0.15), 60),
                          ((c[0] + self.S * 0.12, c[1]), (-self.W * 0.15, -self.H * 0.15), 120)]
        else:
            self.paths = [((-self.W * 0.1, -self.H * 0.05), (c[0] - self.S * 0.03, c[1] - self.S * 0.02), 0),
                          ((self.W * 1.1, -self.H * 0.05), (c[0] + self.S * 0.03, c[1] - self.S * 0.02), 0)]
        self.lag = [0, 1]                                        # lệch nhịp rất ngắn

    @staticmethod
    def _glow(im):
        from PIL import ImageFilter
        g = im.getchannel("A").filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(3))
        out = Image.new("RGBA", (im.width, im.height), LOI_MID + (0,))
        out.putalpha(g.point(lambda v: int(v * 0.8)))
        out.alpha_composite(im)
        return out

    def state(self, k, f):
        a, b, _ = self.paths[k]
        t = (f - self.lag[k]) / float(self.n - 1)
        dx, dy = b[0] - a[0], b[1] - a[1]
        ang = math.degrees(math.atan2(dy, dx))
        if not self.D:
            aim = _eo(_ph(t, 0.05, 0.28))
            fly = _ei(_ph(t, 0.3, 0.78))
            pos = _lp(a, b, fly)
            rot_dir = -90 + (ang + 90) * aim if aim < 1 else ang
            return pos, rot_dir, fly, _ph(t, 0, 0.08)
        fly = _ei(_ph(t, 0.0, 0.42))
        return _lp(a, b, fly), ang, fly, 1.0

    def update(self, f, t):
        for k in range(2):
            pos, rot, fly, ap = self.state(k, f)
            if not self.D and 0.3 < fly < 0.95:
                self.parts.append(Part(pos[0], pos[1], self.rnd.uniform(-1, 1), self.rnd.uniform(-1, 1), 8, self.S * 0.009,
                                       "spark", 0.85))
        if self.D and f == int(0.42 * (self.n - 1)) + 2:
            self.emit(22, self.c, self.S * 0.05, 13, self.S * 0.018, "shard", grav=self.S * 0.003, col=(225, 225, 245))
            self.emit(10, self.c, self.S * 0.05, 9, self.S * 0.01, "spark")
        if not self.D and f == 1:
            self.emit(10, self.c, self.S * 0.03, 8, self.S * 0.009, "spark")

    def draw(self, cv, f, t):
        S = self.S
        if not self.D and f <= 2:
            loi_flash(cv, self.c, S * 0.1, 1 - f / 3.0)
        for k in range(2):
            pos, rot, fly, ap = self.state(k, f)
            if self.D and fly >= 1 and t > 0.55:
                continue
            a, b, _ = self.paths[k]
            dv = _dv(rot)
            if fly > 0.05:                                       # kiếm quang: vệt sáng thuôn phía sau
                ln = S * (0.25 + 0.9 * min(1.0, fly * 1.6)) * (1 if not self.D else 0.7)
                pos_t = pos
                pos = _ad(pos, dv, -S * 0.2)                      # vệt bắt đầu từ chuôi kiếm
                back = _ad(pos, dv, -ln)
                nx, ny = -dv[1], dv[0]
                w = S * 0.018
                trail = [_ad(pos, (nx, ny), w), _ad(pos, (nx, ny), -w), back]
                cv.poly("aura", trail, LOI_AURA + (110,))
                cv.poly("glow", trail, LOI_MID + (190,))
                cv.poly("base", [_ad(pos, (nx, ny), w * 0.35), _ad(pos, (nx, ny), -w * 0.35), _lp(pos, back, 0.7)],
                        LOI_CORE + (220,))
                pos = pos_t
                for g_ in (1, 2):                                # bóng ảnh kiếm
                    cv.stamp(self.img, _ad(pos, dv, -S * 0.16 * g_), 1.0, -(rot + 90), 0.3 / g_)
            cv.stamp(self.img, pos, 1.0, -(rot + 90), max(0.0, min(1.0, ap * 1.5)))
            if not self.D and 0.45 < fly < 0.62:                 # loé sao khi đạt tốc độ cao
                tip = _ad(pos, dv, S * 0.2)
                loi_flash(cv, tip, S * 0.05, 1.0)
        if self.D and 0.42 <= t < 0.62:
            loi_flash(cv, self.c, S * 0.12, 1 - _ph(t, 0.42, 0.62))
            k = _ph(t, 0.42, 0.75)
            loi_ring(cv, self.c, S * (0.05 + 0.4 * k), S * (0.04 + 0.25 * k), 1 - k, S * 0.01)


# ══════════════ VFX TỪ ẢNH CỦA NGƯỜI DÙNG: bóc tách lớp rồi dựng chuyển động ══════════════
# Ảnh trong HieuUng/ (cắt bằng tools/cat_hieu_ung.py) KHÔNG được dán nguyên: mỗi ảnh được tách thành
#   lõi sét (điểm trắng sáng) – thân sợi điện (có màu) – khói đen – đá vụn (mảnh tối tách rời, nhấc khỏi ảnh)
# cùng trường "khoảng cách tới tâm năng lượng" và các rẻ quạt sợi sét. Mỗi frame: sét lan theo trường khoảng cách
# với mép răng cưa, từng rẻ quạt chớp – tắt – loé theo nhịp riêng, lõi bùng sáng thành quầng, khói nở rồi tan theo
# nhiễu, đá văng theo quán tính; sợi sét rời (bóc từ bảng sét) đan xen vàng / tím quanh tâm.
FX_DIR = os.path.join(BASE_DIR, "HieuUng")
_FX_SRC = {}
_FX_LAY = {}


def fx_src(name):
    im = _FX_SRC.get(name)
    if im is None:
        try:
            im = Image.open(os.path.join(FX_DIR, name + ".png")).convert("RGBA")
            _FX_SRC[name] = im
        except Exception:
            im = None                                   # không nhớ lỗi: có ảnh lại là dùng được ngay
    return im


def _components_np(mask, max_px=60000):
    """Gán nhãn thành phần liên thông 4 hướng (thuần python, chỉ duyệt điểm thuộc mặt nạ)."""
    import numpy as np
    from collections import deque
    h, w = mask.shape
    lab = np.zeros((h, w), np.int32)
    out = []
    ys, xs = np.nonzero(mask)
    if len(ys) > max_px:
        return lab, out
    n = 0
    for y, x in zip(ys.tolist(), xs.tolist()):
        if lab[y, x]:
            continue
        n += 1
        q = deque([(y, x)])
        lab[y, x] = n
        pts = []
        while q:
            cy, cx = q.popleft()
            pts.append((cy, cx))
            for yy, xx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                if 0 <= yy < h and 0 <= xx < w and mask[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = n
                    q.append((yy, xx))
        out.append((n, pts))
    return lab, out


class FxLayers:
    """Một ảnh hiệu ứng đã bóc tách ở đúng cỡ hiển thị (px = cạnh dài)."""

    def __init__(self, name, px, origin=(0.5, 0.5), reveal="radial", nsec=9, wipe=0.0, rocks=False, vig=False):
        import numpy as np
        src = fx_src(name)
        self.ok = src is not None
        if not self.ok:
            return
        k = px / float(max(src.size))
        im = src.resize((max(2, int(src.width * k)), max(2, int(src.height * k))), Image.LANCZOS)
        a = np.asarray(im).astype(np.float32) / 255.0
        h, w = a.shape[:2]
        self.w, self.h = w, h
        rgb, al = a[..., :3].copy(), a[..., 3].copy()
        if vig:                                                                      # bo mép elip: xoá dấu ô cắt hình chữ nhật
            yy0, xx0 = np.mgrid[0:h, 0:w].astype(np.float32)
            d = ((xx0 - w / 2.0) / (w / 2.0)) ** 2 + ((yy0 - h / 2.0) / (h / 2.0)) ** 2
            al *= np.clip((1.0 - d) / 0.45, 0, 1)
        lum = rgb.mean(2)
        sat = rgb.max(2) - rgb.min(2)
        self.core = np.clip((lum - 0.7) / 0.2, 0, 1) * al                          # lõi sét trắng
        self.dark = np.clip((0.34 - lum) / 0.22, 0, 1) * (1 - np.clip((sat - 0.22) / 0.2, 0, 1))   # khói / đá: tối, ít màu
        m = al > 0.25
        self.tint = tuple(int(v) for v in (rgb[m & (lum > 0.45)].mean(0) * 255)) if (m & (lum > 0.45)).any() else (200, 160, 255)
        self.rocks = []
        if rocks:                                                                    # bóc đá vụn: mảnh tối, đặc, nhỏ, tách rời
            rm = (lum < 0.2) & (al > 0.8)
            lab, comps = _components_np(rm)
            ox, oy = origin[0] * w, origin[1] * h
            for nlab, pts in comps:
                if not (8 <= len(pts) <= max(40, w * h // 120)):
                    continue
                yy = [p[0] for p in pts]
                xx = [p[1] for p in pts]
                y0, y1, x0, x1 = min(yy), max(yy) + 1, min(xx), max(xx) + 1
                if len(pts) < 0.35 * (y1 - y0) * (x1 - x0):
                    continue                                                         # không đặc = vệt khói, bỏ
                piece = np.zeros((y1 - y0 + 2, x1 - x0 + 2, 4), np.float32)
                for py, px_ in pts:
                    piece[py - y0 + 1, px_ - x0 + 1, :3] = rgb[py, px_]
                    piece[py - y0 + 1, px_ - x0 + 1, 3] = 1.0
                    al[py, px_] *= 0.35                                             # nhấc khỏi ảnh gốc, chỗ cũ còn vệt khói mờ
                cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
                self.rocks.append((Image.fromarray((piece * 255).astype(np.uint8), "RGBA"), cx, cy,
                                   math.atan2(cy - oy, cx - ox)))
            self.rocks = sorted(self.rocks, key=lambda r: -r[0].width * r[0].height)[:14]
        self.rgb, self.al = rgb, al
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        ox, oy = origin[0] * w, origin[1] * h
        if reveal == "radial":
            f = np.hypot(xx - ox, yy - oy)
        elif reveal == "down":
            f = yy - oy
        elif reveal == "up":
            f = oy - yy
        elif reveal == "spin":
            f = (np.arctan2(yy - oy, xx - ox) + math.pi) % (2 * math.pi)
        else:                                                                        # wipe theo hướng (độ)
            dx, dy = math.cos(math.radians(wipe)), math.sin(math.radians(wipe))
            f = (xx - ox) * dx + (yy - oy) * dy
        mm = al > 0.05
        if mm.any():
            lo, hi = float(f[mm].min()), float(f[mm].max())
            f = (f - lo) / max(1e-6, hi - lo)
        self.field = np.clip(f, 0, 1)
        self.noise = make_noise(w, h, len(name) * 7 + w)[:h, :w]
        ang = np.arctan2(yy - oy, xx - ox)
        if reveal in ("down", "up"):
            sec = (xx / w * nsec + (self.noise - 0.5) * 1.2).astype(np.int32)
        else:
            sec = ((ang + math.pi) / (2 * math.pi) * nsec + (self.noise - 0.5) * 0.9).astype(np.int32)
        self.sec = np.clip(sec, 0, nsec - 1) % nsec
        self.nsec = nsec
        self.pin_px = (ox, oy)

    def frame(self, lo, hi, gains, core_k=1.0, smoke_k=1.0, smoke_thr=0.0, inv=False, soft=0.05, jitter=0, noise_fade=False):
        """Ảnh RGBA của trạng thái hiện tại + ảnh lõi (để làm quầng sáng)."""
        import numpy as np
        f = self.field + (self.noise - 0.5) * 0.12                                    # mép lan răng cưa
        if inv:
            f = 1.0 - f
        if noise_fade:                                                               # tan theo nhiễu (kiểu xoay: không có mép thẳng)
            vis = np.clip((hi - f) / soft, 0, 1) * np.clip((self.noise - lo * 0.95) / 0.06, 0, 1)
        else:
            vis = np.clip((hi - f) / soft, 0, 1) * np.clip((f - lo) / soft, 0, 1)
        g = np.asarray(gains, np.float32)[self.sec]
        light = self.al * (1 - self.dark)
        smoke = self.al * self.dark
        svis = np.clip((hi + 0.08 - f) / soft, 0, 1)                                 # khói đi sau, đọng lại lâu hơn
        sd = np.clip((self.noise - smoke_thr) / 0.08, 0, 1)                          # khói tan theo nhiễu
        a_l = light * vis * np.clip(0.08 + 0.92 * g, 0, 1) ** 1.3                 # nhánh tắt: mờ đi, không xỉn màu
        a_s = smoke * svis * smoke_k * sd * np.clip(0.45 + 0.4 * g, 0, 1)
        bright = np.clip(0.88 + 0.22 * g, 0, 1.5)[..., None]
        rgb = np.clip(self.rgb * bright + (self.core * np.clip(g * core_k - 0.9, 0, 2) * 0.55)[..., None], 0, 1)
        A = np.clip(a_l + a_s, 0, 1)
        out = np.dstack([rgb, A])
        if jitter:                                                                   # giật điện: lệch 1px theo hàng nhiễu
            out = np.roll(out, jitter, axis=1 if jitter % 2 else 0)
        core = np.clip(self.core * vis * np.clip(g * core_k, 0, 2) * 0.8, 0, 1)
        im = Image.fromarray((out * 255).astype(np.uint8), "RGBA")
        cm = Image.fromarray((core * 255).astype(np.uint8), "L")
        return im, cm


def fx_layers(name, px, **kw):
    key = (name, int(px)) + tuple(sorted(kw.items()))
    L = _FX_LAY.get(key)
    if L is None:
        L = FxLayers(name, px, **kw)
        _FX_LAY[key] = L
        if len(_FX_LAY) > 120:
            _FX_LAY.pop(next(iter(_FX_LAY)))
    return L


def _place(cv, im, pin, c, scale=1.0, rot=0.0, alpha=1.0, layer="base"):
    """Đặt ảnh sao cho điểm pin (toạ độ trong ảnh) rơi đúng vị trí c, sau khi phóng / xoay quanh pin."""
    if im is None or alpha <= 0.01:
        return
    w, h = im.size
    dx, dy = (w / 2.0 - pin[0]) * scale, (h / 2.0 - pin[1]) * scale
    r = math.radians(-rot)
    cx = c[0] + dx * math.cos(r) - dy * math.sin(r)
    cy = c[1] + dx * math.sin(r) + dy * math.cos(r)
    cv.stamp(im, (cx, cy), scale, rot, alpha, layer)


def _tinted(mask, tint, k=1.0):
    t = Image.new("RGBA", mask.size, tint + (255,))
    t.putalpha(mask.point(lambda v: min(255, int(v * k))))
    return t


class ImgVfx(Vfx):
    """Hiệu ứng dựng từ lớp đã bóc tách. SPEC (ghi đè ở lớp con):
      layers: [dict(src, size, origin, pin, reveal, wipe, t0, t1, rot, rotv, rise, nsec, role)]
              size = cạnh dài theo đơn vị S; t0..t1 = khoảng thời gian lớp tồn tại; rotv = độ xoay / cả hiệu ứng;
              rise = dịch lên (đơn vị S) suốt hiệu ứng; role 'main' / 'weave' (lớp đan xen, nháy ngược pha)
      strands: (danh sách sợi sét rời, số sợi, độ dài theo S) – bóc từ bảng sét, đan xen quanh tâm
      parts: 'petal' | 'toxic' | 'soul' | None – hạt riêng của hiệu ứng"""
    ss = 1
    layers = []
    strands = None
    parts = None
    grow_end = 0.28                     # lúc sét lan hết
    fade_start = 0.55                   # lúc bắt đầu rút / tan

    def init(self):
        r = self.rnd
        self.L = []
        for spec in self.layers:
            px = spec.get("size", 1.0) * self.S
            L = fx_layers(spec["src"], px, origin=spec.get("origin", (0.5, 0.5)), reveal=spec.get("reveal", "radial"),
                          nsec=spec.get("nsec", 9), wipe=spec.get("wipe", 0.0), rocks=spec.get("rocks", False),
                          vig=spec.get("vig", False))
            if not L.ok:
                continue
            pin = spec.get("pin", spec.get("origin", (0.5, 0.5)))
            self.L.append((spec, L, (pin[0] * L.w, pin[1] * L.h)))
        self.ok = bool(self.L)
        if not self.ok:
            return
        n = self.n
        self.gains = []                                                     # nhịp chớp riêng từng rẻ quạt
        strikes = {1, 2} | ({int(n * 0.42)} if n > 10 else set())
        for spec, L, pin in self.L:
            tab = []
            for f in range(n):
                row = []
                for s in range(L.nsec):
                    v = r.random()
                    g = 0.25 if v < 0.22 else (0.6 if v < 0.4 else (1.45 if v > 0.85 else 1.0))
                    if f in strikes:
                        g = 1.6
                    row.append(g)
                if spec.get("steady"):                                      # ma pháp: sáng ổn định, nhấp nháy nhẹ
                    row = [1.0 + 0.12 * math.sin(f * 1.7 + s_) + (0.45 if f in (1, 2) else 0) for s_ in range(L.nsec)]
                if spec.get("role") == "weave":                             # lớp đan xen: sáng khi lớp chính tối
                    row = [1.7 - g if f not in strikes else 1.4 for g in row]
                tab.append(row)
            self.gains.append(tab)
        self.rock_parts = False
        self.strand_set = []
        if self.strands:
            names, cnt, ln = self.strands
            for k in range(cnt):
                nm = names[k % len(names)]
                Ls = fx_layers(nm, ln * self.S * r.uniform(0.75, 1.1), origin=(0.5, 0.0), reveal="down", nsec=1, rocks=False)
                if not self.strand_ring:                                   # kiểu cột: sợi giáng dọc hai bên cột xuống chữ
                    Ls = fx_layers(nm, self.S * r.uniform(0.9, 1.25), origin=(0.5, 0.0), reveal="down", nsec=1, rocks=False)
                if Ls.ok:
                    ang = r.uniform(0, 360) if self.strand_ring else r.choice((-1, 1)) * r.uniform(10, 35)
                    t0 = r.randint(0, max(1, int(n * 0.55)))
                    self.strand_set.append((Ls, ang, t0, r.randint(3, 5)))

    strand_ring = True                  # sợi đan xen toả tròn quanh tâm (False: rủ xuống quanh cột)

    def _main_state(self, t, spec):
        """lo / hi của dải hiển thị trên trường khoảng cách, theo giai đoạn của lớp."""
        t0, t1 = spec.get("t0", 0.0), spec.get("t1", 1.0)
        if t < t0 or t > t1:
            return None
        u = (t - t0) / max(1e-6, t1 - t0)
        ge = self.grow_end / max(0.2, t1 - t0) if t1 - t0 < 1 else self.grow_end
        hi = _eo(_ph(u, 0, min(0.9, ge))) * 1.15
        lo = _ph(u, self.fade_start, 0.97) * 1.15
        return lo, hi, u

    def update(self, f, t):
        if not self.ok:
            return
        r = self.rnd
        spec, L, pin = self.L[0]
        k = spec.get("size", 1.0)
        if f == 1 and not self.rock_parts:                                  # đá vụn đã bóc: văng ra / bị hút vào
            self.rock_parts = True
            for img, cx, cy, ang in L.rocks:
                px, py = self.c[0] + (cx - pin[0]), self.c[1] + (cy - pin[1])
                sp = self.S * r.uniform(0.012, 0.03)
                if not self.D:
                    p = Part(px, py, math.cos(ang) * sp, math.sin(ang) * sp - self.S * 0.01, self.n, 1.0, "sprite", 0.97,
                             self.S * 0.0025, rot=0, vr=r.uniform(-18, 18))
                else:
                    far = self.S * 0.35
                    p = Part(px + math.cos(ang) * far, py + math.sin(ang) * far, -math.cos(ang) * far / 9.0,
                             -math.sin(ang) * far / 9.0, 9, 1.0, "sprite", 1.0, 0, rot=0, vr=r.uniform(-25, 25))
                p.img = img
                self.parts.append(p)
        if self.parts_kind == "petal" and f % 2 == 0 and t > 0.35:
            p = _ad(self.c, (r.uniform(-0.25, 0.25) * self.S, -self.S * r.uniform(0.4, 0.8)))
            self.parts.append(Part(p[0], p[1], r.uniform(-0.6, 0.6), 0.5, 18, self.S * 0.02, "petal", 0.97, self.S * 0.002,
                                   rot=r.uniform(0, 360), vr=r.uniform(-20, 20)))
        if self.parts_kind == "toxic" and f % 2 == 0:
            p = _ad(self.c, (r.uniform(-0.4, 0.4) * self.S, -self.S * r.uniform(0.0, 0.5)))
            self.parts.append(Part(p[0], p[1], r.uniform(-0.6, 0.6), -0.3, 14, self.S * 0.05, "gas", 0.96, col=(110, 235, 80)))
        if self.parts_kind == "soul" and f % 2 == 1:
            p = _ad(self.c, (r.uniform(-0.2, 0.2) * self.S, -self.S * r.uniform(0.1, 0.6)))
            self.parts.append(Part(p[0], p[1], r.uniform(-0.4, 0.4), -self.S * 0.012, 12, self.S * 0.012, "soul", 0.95))
        if self.parts_kind == "spark" and not self.D and f in (1, 2, 5):
            self.emit(10, self.c, self.S * 0.05, 9, self.S * 0.01, "spark")

    parts_kind = None

    def draw(self, cv, f, t):
        if not self.ok:
            return
        for li, (spec, L, pin) in enumerate(self.L):
            st = self._main_state(t, spec)
            if st is None:
                continue
            lo, hi, u = st
            inv = self.D
            if self.D:                                                      # xoá: sét từ ngoài dồn vào tâm rồi tắt
                hi = _ei(_ph(u, 0, 0.35)) * 1.15
                lo = _ph(u, 0.45, 0.92) * 1.15
            smoke_thr = _ph(u, 0.35, 0.8) * 1.1
            g = self.gains[li][min(f, self.n - 1)]
            core_k = 1.6 if f in (1, 2) else 1.0
            jit = (f % 3) - 1 if spec.get("role") != "still" else 0
            im, cm = L.frame(lo, hi, g, core_k, 1.0, smoke_thr, inv=inv, jitter=jit,
                             noise_fade=spec.get("reveal") == "spin" or spec.get("nf", False))
            if self.D:
                scale = 1.05 - 0.25 * _ei(_ph(u, 0.3, 1.0))
            else:
                scale = 0.86 + 0.18 * _eo(_ph(u, 0, 0.5))
            rot = spec.get("rot", 0.0) + spec.get("rotv", 0.0) * (u if not self.D else -u)
            rot += spec.get("sway", 0.0) * math.sin(u * math.pi * 3)                 # lắc lư
            c = _ad(self.c, (0, -spec.get("rise", 0.0) * self.S * _eo(u)))
            mv = spec.get("move")
            if mv:                                                                     # quỹ đạo: (từ x, y) -> (tới x, y), đơn vị S
                (x0, y0), (x1, y1) = mv if not self.D else (mv[1], mv[0])
                k = spec.get("ease", _eo)(u)
                c = _ad(c, (self.S * (x0 + (x1 - x0) * k), self.S * (y0 + (y1 - y0) * k)))
            if spec.get("lunge"):                                                      # vồ tới: co lại lấy đà rồi bung ra
                scale *= 0.7 + 0.45 * _eo(_ph(u, 0.12, 0.35)) - 0.15 * _ph(u, 0.6, 1.0)
            _place(cv, im, pin, c, scale, rot, 1.0, "base")
            _place(cv, _tinted(cm, L.tint, 1.4), pin, c, scale, rot, 1.0, "glow")      # quầng loé của lõi sét
        for Ls, ang, t0, life in self.strand_set:                           # sợi sét rời đan xen, chớp theo nhịp riêng
            a = f - t0
            if a < 0 or a >= life:
                continue
            hi = (0.55, 1.15, 1.15, 1.15, 1.15)[a]
            lo = (0.0, 0.0, 0.25, 0.6, 0.9)[a] if a < 5 else 1.2
            gpow = (1.2, 1.6, 0.6, 1.2, 0.4)[a]
            im, cm = Ls.frame(lo, hi, [gpow], 1.3, 0.6, 0.3, inv=self.D)
            pin = (Ls.w * 0.5, 0.0)
            spec0, L0, pin0 = self.L[0]
            if self.strand_ring:
                base = _ad(self.c, _dv(ang - 90), self.S * 0.06)
                _place(cv, im, pin, base, 1.0, -(ang + 180), 0.95)
                _place(cv, _tinted(cm, Ls.tint, 1.2), pin, base, 1.0, -(ang + 180), 0.9, "glow")
            else:
                top = (self.c[0] + ang / 35.0 * self.S * 0.3, self.c[1] - Ls.h * 0.98)
                _place(cv, im, pin, top, 1.0, 0, 0.95)
                _place(cv, _tinted(cm, Ls.tint, 1.2), pin, top, 1.0, 0, 0.9, "glow")
        spec0, L0, pin0 = self.L[0]
        if not self.D and f in (0, 1, 2):                                   # chớp khởi phát theo màu ảnh
            img_flash(cv, self.c, self.S * (0.1 + 0.03 * f), (1.0, 0.85, 0.5)[f], L0.tint)
        if self.D and abs(t - 0.86) < 0.08:                                 # sập về tâm
            img_flash(cv, self.c, self.S * 0.08, 1 - abs(t - 0.86) / 0.08, L0.tint)


def img_flash(cv, c, r, k, tint):
    cv.ell("aura", c, r * 2.0, r * 2.0, (20, 8, 30, int(90 * k)))
    cv.ell("glow", c, r * 1.4, r * 1.4, tint + (int(230 * k),))
    cv.ell("base", c, r * 0.45, r * 0.45, (255, 252, 240, int(255 * k)))
    for i in range(8):
        a = i * 45 + 22.5
        ln = r * (2.0 if i % 2 else 1.3)
        cv.poly("base", [_ad(c, _dv(a - 6), r * 0.28), _ad(c, _dv(a), ln), _ad(c, _dv(a + 6), r * 0.28)], (255, 250, 230, int(220 * k)))


class LoiTinhLienHoan(Vfx):
    """Lôi tinh liên hoàn – MỘT tia sét lôi xanh mảnh chạy dọc trên dòng chữ: đầu tia là tinh điểm sáng lao từ đầu dòng tới
    con trỏ, thân tia bám sát mặt chữ, tới nơi thì chớp loá, cả dòng giật sáng 2-3 nhịp rồi rút dần vào con trỏ.
    Xoá: tia phóng ngược từ con trỏ về đầu dòng, nhạt dần."""
    name, frames, anchor, box = "lientinh", 20, (0.93, 0.6), (3.0, 0.9)

    def init(self):
        r, S = self.rnd, self.S
        a = (self.c[0] - S * 2.7, self.c[1] - S * r.uniform(0.0, 0.08))
        b = (self.c[0], self.c[1])
        if self.D:
            a, b = b, a
        self.bolt = LoiBolt(a, b, S * 0.0075, r, branches=6, depth=1, kink=(0.004, 0.011), seg=(0.018, 0.035),
                            blen=(0.02, 0.045), spread=(35, 75)).set_pal(LOI_XANH)
        self.ok = True

    def at(self, s):
        return self.bolt._cut(max(0.0, s - 0.002), max(0.002, s))[-1]

    def state(self, f, t):
        """(đầu tia, đuôi tia, độ sáng)"""
        if t < 0.46:                                              # tia chạy: đầu lao, thân dài ~40% dòng bám theo
            g = _eo(_ph(t, 0.0, 0.46))
            return g, max(0.0, g - 0.4), 1.0
        if t < 0.76:                                              # tới nơi: cả dòng giật sáng theo nhịp, lúc đứt lúc liền
            p = self.pulse(f)
            return 1.0, (0.0 if p > 0.6 else 0.45), 0.55 + 0.45 * p
        u = _ph(t, 0.76, 1.0)                                     # rút dần về phía con trỏ
        return 1.0, u, 0.9 - 0.5 * u

    def update(self, f, t):
        g, tl, pw = self.state(f, t)
        if t < 0.46:
            self.emit(2, self.at(g), self.S * 0.02, 6, self.S * 0.005, "spark_b")
        hit = int(0.46 * (self.n - 1)) + 1
        if f == hit:
            self.emit(10, self.at(1.0), self.S * 0.04, 8, self.S * 0.006, "spark_b")

    def draw(self, cv, f, t):
        g, tl, pw = self.state(f, t)
        self.bolt.draw(cv, g, tl, pw, self.S * 0.005, self.jr, kid_power=0.75)
        S = self.S
        if t < 0.5:                                               # tinh điểm ở đầu tia
            h = self.at(g)
            cv.ell("aura", h, S * 0.09, S * 0.09, LOI_XANH[3] + (110,))
            cv.ell("glow", h, S * 0.05, S * 0.05, LOI_XANH[1] + (230,))
            cv.ell("base", h, S * 0.016, S * 0.016, LOI_XANH[0] + (255,))
            for k in range(4):
                a = k * 90 + f * 25
                cv.poly("base", [_ad(h, _dv(a - 10), S * 0.008), _ad(h, _dv(a), S * 0.05), _ad(h, _dv(a + 10), S * 0.008)],
                        LOI_XANH[0] + (220,))
        hit = int(0.46 * (self.n - 1)) + 1
        a = f - hit
        if 0 <= a < 3:                                            # chớp loá tại đích
            e = self.at(1.0)
            k = 1.0 - a * 0.35
            cv.ell("aura", e, S * 0.22, S * 0.22, LOI_XANH[3] + (int(110 * k),))
            cv.ell("glow", e, S * 0.12, S * 0.12, LOI_XANH[1] + (int(230 * k),))
            cv.ell("base", e, S * 0.03, S * 0.03, LOI_XANH[0] + (int(255 * k),))
            for i in range(6):
                d = i * 60 + 15
                cv.poly("base", [_ad(e, _dv(d - 6), S * 0.012), _ad(e, _dv(d), S * (0.12 if i % 2 else 0.07)),
                                 _ad(e, _dv(d + 6), S * 0.012)], LOI_XANH[0] + (int(220 * k),))


class LoiThuongTu(Vfx):
    """Lôi thương – cây thương sấm sét: mũi lá có ngạnh răng cưa hình tia chớp, sống giữa trắng loá, đai chắn với hai cánh
    sét vuốt ngược, cán dài có sét quấn xoắn, chuôi kim cương. Gõ: thương phóng chéo xuống, kéo bóng mờ, cắm xuyên chữ –
    chớp loá, sóng chấn, nổ (bóc từ ảnh nổ nếu có), đá văng; thương rung bần bật, sét quấn cán giật liên hồi rồi tan thành
    tia lửa. Xoá: thương đang cắm bị rút phăng ngược lên."""
    name, frames, anchor, box = "loithuong", 20, (0.30, 0.8), (1.9, 1.75)

    def init(self):
        r, S = self.rnd, self.S
        self.start = (self.W * 1.12, -self.H * 0.2)
        d = math.atan2(self.c[1] - self.start[1], self.c[0] - self.start[0])
        self.ang = math.degrees(d)
        self.dir = (math.cos(d), math.sin(d))
        self.nv = (-self.dir[1], self.dir[0])
        self.L = S * 1.25
        self.hit = _ad(self.c, self.dir, S * 0.05)                     # mũi cắm sâu vào chữ
        self.ph = r.uniform(0, 6.28)
        self.arcs = [LoiBolt((0, 0), (r.uniform(-1, 1) * S * 0.25, -S * r.uniform(0.05, 0.22)), S * 0.006, r, 1, 1)
                     for _ in range(5)]
        self.boom = None
        try:
            bm = fx_layers("no_vang_tim", S * 0.85, origin=(0.5, 0.82), nsec=8, rocks=True)
            self.boom = bm if bm.ok else None
        except Exception:
            self.boom = None
        self.ok = True
        self.hit_f = int(0.2 * (self.n - 1)) + 1

    def tip(self, t):
        if not self.D:
            return _lp(self.start, self.hit, _ei(_ph(t, 0, 0.2)))
        return _lp(self.hit, self.start, _ei(_ph(t, 0.3, 0.62)))

    def spear(self, cv, tp, k, f, shake=0.0, coil=1.0):
        S, L, dv, nv = self.S, self.L, self.dir, self.nv
        if k <= 0.02:
            return

        def P(x, y):
            y = y + shake * (-x / L)                                   # rung: mũi đứng yên, chuôi quẫy
            return (tp[0] + dv[0] * x + nv[0] * y, tp[1] + dv[1] * x + nv[1] * y)

        A = lambda v: int(v * k)
        B = 0.42                                                     # chiều dài mũi thương (theo S)
        cv.line("aura", [P(0, 0), P(-L, 0)], LOI_AURA + (A(110),), S * 0.12)
        cv.line("glow", [P(-0.05 * S, 0), P(-L, 0)], LOI_MID + (A(140),), S * 0.045)
        # cán
        for hw, col in ((0.018, LOI_EDGE), (0.011, LOI_MID), (0.004, LOI_CORE)):
            cv.poly("base", [P(-(B + 0.05) * S, hw * S), P(-L, hw * S * 0.8), P(-L, -hw * S * 0.8), P(-(B + 0.05) * S, -hw * S)],
                    col + (A(255),))
        # chuôi: khâu tròn nhỏ + 2 sợi điện tua
        cv.ell("base", P(-L, 0), S * 0.024, S * 0.024, LOI_EDGE + (A(255),))
        cv.ell("base", P(-L, 0), S * 0.012, S * 0.012, LOI_CORE + (A(230),))
        # đai chắn + 2 cánh sét vuốt ngược (gấp khúc như tia chớp)
        x0 = -B * S
        for sg in (1, -1):
            wing = [P(x0, sg * 0.025 * S), P(x0 - 0.04 * S, sg * 0.09 * S), P(x0 - 0.065 * S, sg * 0.07 * S),
                    P(x0 - 0.13 * S, sg * 0.15 * S), P(x0 - 0.10 * S, sg * 0.06 * S), P(x0 - 0.075 * S, sg * 0.045 * S),
                    P(x0 - 0.05 * S, sg * 0.025 * S)]
            cv.poly("base", wing, LOI_EDGE + (A(255),))
            cv.line("base", [P(x0 - 0.01 * S, sg * 0.035 * S), P(x0 - 0.04 * S, sg * 0.085 * S), P(x0 - 0.065 * S, sg * 0.068 * S),
                             P(x0 - 0.12 * S, sg * 0.14 * S)], LOI_CORE + (A(230),), max(1.0, S * 0.007))
        cv.poly("base", [P(x0 + 0.01 * S, 0.05 * S), P(x0 - 0.06 * S, 0.05 * S), P(x0 - 0.06 * S, -0.05 * S),
                         P(x0 + 0.01 * S, -0.05 * S)], LOI_EDGE + (A(255),))
        cv.poly("base", [P(x0, 0.033 * S), P(x0 - 0.05 * S, 0.033 * S), P(x0 - 0.05 * S, -0.033 * S), P(x0, -0.033 * S)],
                LOI_MID + (A(255),))
        # mũi thương: lá dài to bản, mép có ngạnh răng cưa hình tia chớp
        up = [(0, 0), (-0.08, 0.05), (-0.15, 0.085), (-0.18, 0.055), (-0.26, 0.105), (-0.29, 0.07), (-0.37, 0.06), (-B, 0.03)]
        blade = [P(x * S, y * S) for x, y in up] + [P(x * S, -y * S) for x, y in reversed(up[1:])]
        cv.poly("glow", blade, LOI_MID + (A(240),))
        cv.poly("base", blade, LOI_EDGE + (A(255),))
        inner = [P(x * S * 0.96 - 0.012 * S, y * S * 0.55) for x, y in up] + \
                [P(x * S * 0.96 - 0.012 * S, -y * S * 0.55) for x, y in reversed(up[1:])]
        cv.poly("base", inner, LOI_MID + (A(255),))
        cv.poly("base", [P(0, 0), P(-0.15 * S, 0.014 * S), P(-(B - 0.01) * S, 0.008 * S), P(-(B - 0.01) * S, -0.008 * S),
                         P(-0.15 * S, -0.014 * S)], LOI_CORE + (A(255),))           # sống giữa trắng loá
        # sét quấn xoắn quanh cán
        if coil > 0.05:
            n = 26
            pts = []
            for i in range(n + 1):
                x = -0.52 * S - (L - 0.58 * S) * i / float(n)
                y = 0.04 * S * math.sin(i * 1.15 + self.ph + f * 1.7) + self.jr.uniform(-1, 1) * S * 0.006
                pts.append(P(x, y))
            loi_stroke(cv, pts, [S * 0.0055] * len(pts), coil * k)

    def update(self, f, t):
        S = self.S
        if not self.D and f == self.hit_f:
            self.emit(20, self.c, S * 0.05, 11, S * 0.01, "spark", spread=(180, 360))
            if self.boom:
                for img, cx, cy, a in self.boom.rocks:
                    pp = Part(self.c[0] + (cx - self.boom.w / 2) * 0.6, self.c[1], math.cos(a) * S * 0.03,
                              -abs(math.sin(a)) * S * 0.04, 14, 1.0, "sprite", 0.97, S * 0.004, vr=self.rnd.uniform(-20, 20))
                    pp.img = img
                    self.parts.append(pp)
        if not self.D and f == int(0.7 * (self.n - 1)):                     # thương tan thành tia lửa dọc cán
            for i in range(8):
                p = _ad(self.hit, self.dir, -self.L * i / 8.0)
                self.emit(2, p, S * 0.02, 9, S * 0.007, "spark", grav=S * 0.002)
        if self.D and 0.3 * (self.n - 1) <= f <= 0.55 * (self.n - 1):
            self.emit(4, self.c, S * 0.03, 8, S * 0.008, "spark", spread=(200, 340))

    def draw(self, cv, f, t):
        S = self.S
        tp = self.tip(t)
        if not self.D:
            moving = t < 0.2
            fade = _ph(t, 0.7, 0.95)
            a = f - self.hit_f
            shake = (S * 0.06 * math.exp(-a * 0.35) * math.sin(a * 2.6)) if a >= 0 else 0.0
        else:
            moving = 0.3 <= t <= 0.62
            fade = _ph(t, 0.55, 0.85)
            shake = S * 0.025 * math.sin(f * 2.4) if t < 0.3 else 0.0
        k = 1.0 - fade
        if moving:                                                   # bóng mờ + vệt sáng khi lao
            back = -1 if not self.D else 1
            for g_ in (2, 1):
                self.spear(cv, _ad(tp, self.dir, back * S * 0.16 * g_), 0.22 / g_ * k, f, 0, 0)
            cv.line("glow", [tp, _ad(tp, self.dir, -S * 1.6)], LOI_MID + (int(120 * k),), S * 0.05)
        if not self.D:
            a = f - self.hit_f
            if 0 <= a < 3:
                loi_flash(cv, self.c, S * 0.08, 1.0 - a * 0.35)
            if 0 <= a < 7:
                u = a / 6.0
                rx = S * (0.15 + 0.6 * _eo(u))
                loi_ring(cv, self.c, rx, rx * 0.28, 1.0 - u, S * 0.012)
            if self.boom and 0 <= a < 10:                             # nổ chấn (bóc từ ảnh nổ vàng tím)
                u = a / 9.0
                gn = [1.6 if a < 2 else (0.35 if (a + s_) % 4 == 0 else 1.1) for s_ in range(8)]
                bim, bcm = self.boom.frame(_ph(u, 0.45, 0.97) * 1.15, _eo(_ph(u, 0, 0.3)) * 1.15, gn, 1.5 if a < 2 else 1.0,
                                           1.0, _ph(u, 0.3, 0.8))
                bpin = (self.boom.w * 0.5, self.boom.h * 0.82)
                _place(cv, bim, bpin, self.c, 0.75 + 0.2 * _eo(u))
                _place(cv, _tinted(bcm, self.boom.tint, 1.3), bpin, self.c, 0.75 + 0.2 * _eo(u), 0, 1.0, "glow")
        stuck = (not self.D and t >= 0.2) or (self.D and t < 0.3)
        coil = (self.pulse(f) if stuck else 0.6) * k
        self.spear(cv, tp, k, f, shake, coil)
        if stuck and k > 0.1:                                        # điện toé quanh chỗ cắm
            for j, arc in enumerate(self.arcs):
                if (f + j) % 2 == 0:
                    arc.draw(cv, 1.0, 0.0, 0.85 * k, S * 0.004, self.jr, xf=lambda q, c=self.c: (c[0] + q[0], c[1] + q[1]))
        if self.D and 0.3 * (self.n - 1) <= f <= 0.3 * (self.n - 1) + 3:
            loi_flash(cv, self.c, S * 0.07, 0.8)


SKULLS = [("daulau2", 45, 65, 27), ("daulau2", 163, 70, 25), ("daulau3", 65, 105, 28), ("daulau3", 105, 40, 22),
          ("daulau1", 40, 75, 22), ("daulau2", 131, 31, 13), ("daulau3", 25, 50, 13), ("daulau3", 167, 60, 12)]
_SKULL_CACHE = {}


def skull_sprite(k):
    """Đầu lâu thứ k bóc khỏi ảnh (cắt tròn mép mềm, bỏ khói / xoáy xung quanh)."""
    if k in _SKULL_CACHE:
        return _SKULL_CACHE[k]
    import numpy as np
    name, cx, cy, r = SKULLS[k % len(SKULLS)]
    src = fx_src(name)
    if src is None:
        return None
    R = int(r * 1.12)
    box = (cx - R, cy - int(R * 1.05), cx + R, cy + int(R * 1.15))
    im = src.crop(box)
    a = np.asarray(im).astype(np.float32)
    h, w = a.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.hypot((xx - w / 2.0) / (w / 2.0), (yy - h * 0.47) / (h * 0.5))
    a[..., 3] *= np.clip((1.0 - d) / 0.18, 0, 1)
    lum = a[..., :3].mean(2)
    sat = a[..., :3].max(2) - a[..., :3].min(2)
    a[..., 3] *= np.clip(1.0 - (sat - 60) / 160.0 * (lum > 150), 0.25, 1)      # bớt quầng lửa tím sáng loang ra
    out = Image.fromarray(a.astype(np.uint8), "RGBA")
    _SKULL_CACHE[k] = out
    return out


class DauLauBay(Vfx):
    """Đầu lâu ma quỷ (chỉ đầu lâu, bóc từ ảnh): gõ – từng cái hiện ra theo nhiễu, nhỏ trước to sau, bay lên lắc lư,
    mắt loé theo nhịp, tan dần ở trên cao; xoá – các đầu lâu lao bổ xuống chữ, thu nhỏ rồi biến mất."""
    name, frames, anchor, box = "skull", 22, (0.5, 0.95), (1.2, 2.0)

    def init(self):
        r = self.rnd
        self.items = []
        order = [5, 6, 4, 3, 2] if r.random() < 0.5 else [7, 5, 1, 0, 2]
        for j, k in enumerate(order):
            im = skull_sprite(k)
            if im is None:
                continue
            target = self.S * (0.16 + 0.07 * j)                                     # nhỏ rồi to dần
            sc = target / float(max(im.size))
            self.items.append(dict(im=im, sc=sc, t0=j * 0.1, x=r.uniform(-0.22, 0.22) * self.S, sway=r.choice((-1, 1)),
                                   noise=make_noise(im.width + 4, im.height + 4, self.seed * 17 + j, cell=max(3, im.width // 8))))
        self.ok = bool(self.items)

    def draw(self, cv, f, t):
        for j, it in enumerate(self.items):
            u = (t - it["t0"]) / 0.62
            if u < 0 or u > 1:
                continue
            if not self.D:
                y = self.c[1] - self.S * (0.15 + 1.25 * _eo(u))
                x = self.c[0] + it["x"] + math.sin(u * 7) * self.S * 0.06 * it["sway"]
                rot = math.sin(u * 8) * 10 * it["sway"]
                sc = it["sc"] * (0.6 + 0.4 * _eo(_ph(u, 0, 0.3)))
                thr = (1 - _ph(u, 0, 0.25)) * 0.9 + _ph(u, 0.72, 1.0) * 0.95
            else:
                y = self.c[1] - self.S * (1.4 - 1.3 * _ei(u))
                x = self.c[0] + it["x"] * (1 - _ei(u))
                rot = math.sin(u * 14) * 6
                sc = it["sc"] * (1.0 - 0.7 * _ph(u, 0.7, 1.0))
                thr = (1 - _ph(u, 0, 0.2)) * 0.9 + _ph(u, 0.85, 1.0) * 0.95
            im = dissolve(it["im"], thr, it["noise"])                           # hiện ra / tan theo nhiễu, mép cháy tím
            cv.stamp(im, (x, y), sc, rot)
            eye = 0.5 + 0.5 * abs(math.sin(f * 0.9 + j))                        # mắt loé theo nhịp
            k = (1 - thr) * eye
            if k > 0.05:
                for sx in (-1, 1):
                    e = (x + sx * it["im"].width * 0.19 * sc, y - it["im"].height * 0.02 * sc)
                    cv.ell("glow", e, it["im"].width * 0.13 * sc, it["im"].width * 0.1 * sc, (200, 110, 255, int(220 * k)))
                    cv.ell("base", e, it["im"].width * 0.04 * sc, it["im"].width * 0.03 * sc, (255, 240, 255, int(255 * k)))


DauLauBay.fallback = DauLauQuy


# ── các hiệu ứng (bảng thông số: ảnh nào, tâm năng lượng ở đâu, lan theo kiểu nào, đan xen sợi nào) ──
_SV = ["setvang%d" % i for i in range(1, 10)]
_ST = ["settim%d" % i for i in range(1, 6)]


def _fx(key, frames, box, anchor, layers, strands=None, parts=None, ring=True, grow=0.28, fade=0.55, base=None):
    cls = type("Fx_" + key, (ImgVfx,), dict(name=key, frames=frames, box=box, anchor=anchor, layers=layers,
                                             strands=strands, parts_kind=parts, strand_ring=ring, grow_end=grow,
                                             fade_start=fade))
    cls.fallback = base
    return cls


IMG_FX = [
    LoiTinhLienHoan, LoiThuongTu, DauLauBay,
    _fx("bolt", 15, (1.5, 1.5), (0.5, 0.5), [dict(src="tia_chop", size=1.35)], (_ST + _SV, 5, 0.5), "spark",
        base=LoiTinhBaoPhat),
    _fx("novang", 15, (1.5, 1.5), (0.5, 0.5), [dict(src="no_vang", size=1.35, rocks=True), dict(src="tim_no", size=0.9, origin=(0.5, 0.86),
        pin=(0.5, 0.5), role="weave", rocks=False)], (_ST, 4, 0.45), "spark", base=TuLoiBungNo),
    _fx("kimtinh", 16, (1.4, 1.4), (0.5, 0.5), [dict(src="kimtinh1", size=1.2, t1=0.62), dict(src="kimtinh2", size=1.25, t0=0.3,
        role="weave")], (_SV, 4, 0.45), "spark", base=LoiTinhBaoPhat),
    _fx("song", 16, (1.6, 1.15), (0.5, 0.86), [dict(src="no_vang_tim", size=1.5, origin=(0.5, 0.82), rocks=True)], (_ST + _SV, 4, 0.5),
        None, base=TuLoiBungNo),
    _fx("tuno", 16, (1.6, 1.15), (0.5, 0.86), [dict(src="tim_no", size=1.5, origin=(0.5, 0.86))], (_SV, 4, 0.5), None,
        base=TuLoiBungNo),
    _fx("datno", 16, (1.6, 1.15), (0.5, 0.86), [dict(src="no_dat", size=1.5, origin=(0.52, 0.82), rocks=True)], (_ST, 4, 0.5), None,
        base=DiaChanLoi),
    _fx("diachan", 16, (1.8, 0.8), (0.5, 0.82), [dict(src="datvang1", size=0.9, origin=(0.5, 0.9), t1=0.5),
        dict(src="datvang3", size=1.7, origin=(0.5, 0.85), t0=0.15, rocks=True), dict(src="datvang2", size=1.2, origin=(0.5, 0.85),
        t0=0.35, role="weave")], None, "spark", base=DiaChanLoi),
    _fx("hoan", 16, (1.4, 1.4), (0.5, 0.5), [dict(src="vongvang", size=1.05, reveal="spin", rotv=-40),
        dict(src="hoanvang1", size=1.2, role="weave", t0=0.25, rotv=30)], (_SV, 3, 0.35), "spark", base=LoiHoan),
    _fx("xoan", 16, (1.4, 1.4), (0.5, 0.5), [dict(src="xoanvang1", size=1.2, reveal="spin", rotv=-120),
        dict(src="xoanvang2", size=1.1, reveal="spin", rotv=-90, role="weave", t0=0.2)], (_ST, 3, 0.35), None, base=LoiXoay),
    _fx("thunder", 15, (0.9, 1.7), (0.5, 0.94), [dict(src="loidien2", size=1.6, origin=(0.5, 0.0), pin=(0.5, 0.97),
        reveal="down", nsec=5), dict(src="loidien3", size=1.5, origin=(0.5, 0.0), pin=(0.5, 0.97), reveal="down", nsec=5,
        role="weave")], (_ST, 3, 0.5), "spark", ring=False, grow=0.18, fade=0.6, base=ThienLoiGiang),
    _fx("loiphat", 16, (0.9, 1.7), (0.5, 0.94), [dict(src="loiphat2", size=1.6, origin=(0.5, 0.0), pin=(0.5, 0.97),
        reveal="down", nsec=5), dict(src="loiphat3", size=1.5, origin=(0.5, 0.0), pin=(0.5, 0.97), reveal="down", nsec=5,
        role="weave")], (_ST, 3, 0.5), None, ring=False, grow=0.18, fade=0.62, base=LoiPhatTru),
    _fx("cotvang", 16, (1.1, 1.7), (0.5, 0.94), [dict(src="cotvang1", size=1.6, origin=(0.5, 0.0), pin=(0.5, 0.97),
        reveal="down", nsec=5), dict(src="truvong", size=1.4, origin=(0.5, 0.0), pin=(0.5, 0.97), reveal="down", nsec=5,
        role="weave", t0=0.2)], (_SV, 3, 0.5), "spark", ring=False, grow=0.18, fade=0.62, base=LoiPhatTru),
    _fx("loikiep", 16, (1.2, 1.7), (0.5, 0.94), [dict(src="loikiep", size=1.6, origin=(0.5, 0.0), pin=(0.5, 0.97),
        reveal="down", nsec=6), dict(src="loiquang", size=1.5, origin=(0.5, 0.0), pin=(0.5, 0.97), reveal="down", nsec=6,
        role="weave")], (_SV + _ST, 4, 0.5), None, ring=False, grow=0.2, fade=0.62, base=LoiPhatTru),
    _fx("settia", 20, (1.6, 1.6), (0.5, 0.94), [dict(src="setvang5", size=1.3, origin=(0.5, 0.0), pin=(0.5, 0.98),
        reveal="down", nsec=3, t1=0.45), dict(src="settim2", size=1.3, origin=(0.5, 0.0), pin=(0.5, 0.98), reveal="down",
        nsec=3, t0=0.3, t1=0.8, role="weave"), dict(src="setvang7", size=1.25, origin=(0.5, 0.0), pin=(0.5, 0.98),
        reveal="down", nsec=3, t0=0.55)], (_SV + _ST, 7, 0.9), "spark", ring=False, grow=0.15, fade=0.5, base=LoiLienHoi),
    _fx("dragon", 20, (1.5, 1.5), (0.5, 0.5), [dict(src="loilong", size=1.3, origin=(0.18, 0.28), pin=(0.5, 0.5), nsec=8,
        rotv=8)],
        (_ST, 3, 0.4), "spark", grow=0.4, fade=0.62, base=LoiLong),
    _fx("slash", 16, (1.6, 1.45), (0.5, 0.55), [dict(src="matrao1", size=1.15, reveal="wipe", wipe=135, origin=(0.9, 0.1),
        pin=(0.5, 0.5), t1=0.6, vig=True, steady=True, lunge=True, move=((0.25, -0.25), (-0.1, 0.1)), ease=_ei),
        dict(src="matrao3", size=1.1, reveal="wipe", wipe=200, origin=(0.95, 0.4), pin=(0.5, 0.5), t0=0.32, vig=True,
        steady=True, move=((0.2, 0.0), (-0.22, 0.05)), ease=_ei)], None, None, grow=0.25, fade=0.45, base=MaTrao),
    _fx("madoc", 20, (1.8, 1.6), (0.35, 0.78), [dict(src="madoc1", size=0.9, origin=(0.5, 1.0), reveal="up", t1=0.42,
        vig=True, steady=True, sway=6), dict(src="madoc3", size=1.15, origin=(0.3, 0.35), t0=0.3, vig=True, steady=True,
        move=((0.05, -0.15), (0.6, -0.55)), ease=_ei, sway=5)], None, "toxic", grow=0.3, fade=0.55, base=MaDocLong),
    _fx("bingan", 22, (1.2, 1.55), (0.5, 0.95), [dict(src="bingan2", size=1.2, origin=(0.5, 1.0), pin=(0.5, 0.98),
        reveal="up", t1=0.4, nsec=4, vig=True, steady=True), dict(src="bingan3", size=1.45, origin=(0.5, 1.0),
        pin=(0.5, 0.98), reveal="up", t0=0.25, nsec=4, vig=True, steady=True, sway=4)], None, "petal", grow=0.35, fade=0.68,
        base=BiNganHoa),
    _fx("sword", 18, (2.0, 2.2), (0.5, 0.9), [dict(src="phikiem3", size=1.1, reveal="wipe", wipe=60, origin=(0.1, 0.0),
        pin=(0.5, 0.75), t1=0.42, vig=True, steady=True, move=((-0.45, -0.35), (0.25, 0.05)), ease=_ei),
        dict(src="phikiem5", size=1.4, origin=(0.5, 0.92), pin=(0.5, 0.92), t0=0.3, nsec=6, vig=True, steady=True,
        move=((0.0, -0.4), (0.0, 0.0)), ease=_ei)], None, "spark", grow=0.2, fade=0.6, base=SongPhiKiem),
]

LoiTinhLienHoan.fallback = LoiXich
LoiThuongTu.fallback = LoiThuong


# ══ danh sách hiệu ứng (giữ dạng (mã, tên, hàm dựng, điểm neo) để giao diện / cài đặt cũ dùng tiếp) ══
VFX_LABELS = {
    "lientinh": "⚡ Lôi tinh liên hoàn", "loithuong": "⚡ Lôi thương xuyên chữ",
    "bolt": "⚡ Lôi tinh bạo phát", "novang": "⚡ Kim lôi bạo (vàng + tím)", "kimtinh": "⚡ Kim lôi tinh",
    "song": "⚡ Song lôi bùng nổ (vàng tím)", "tuno": "⚡ Tử lôi bùng nổ (tím)", "datno": "⚡ Địa lôi nổ (vàng)",
    "diachan": "⚡ Địa chấn lôi", "hoan": "⚡ Lôi hoàn", "xoan": "⚡ Lốc xoáy lôi", "thunder": "⚡ Lôi điện giáng (tím)",
    "loiphat": "⚡ Lôi phạt", "cotvang": "⚡ Thiên lôi trụ (vàng)", "loikiep": "⚡ Lôi kiếp (tím + vàng)",
    "settia": "⚡ Sấm sét liên hồi", "dragon": "⚡ Lôi long", "slash": "Ma trảo", "madoc": "Ma độc long",
    "bingan": "Bỉ ngạn hoa nở", "skull": "Đầu lâu ma quỷ bay lên", "sword": "Phi kiếm giáng thế",
}
# mã cũ -> mẫu mới gần nhất
FX_ALIAS = {"chain": "lientinh", "gai": "loithuong", "chau": "xoan", "xoanvang": "xoan", "loiquang": "loikiep", "loian": "loikiep",
            "longvang": "dragon", "xatim": "xoan", "hammer": "thunder", "darkflame": "tuno", "holy": "kimtinh",
            "hellfire": "tuno", "ice": "hoan", "star": "kimtinh", "shock": "hoan", "shatter": "novang", "blackhole": "xoan",
            "explode": "novang", "plasma": "xoan", "storm": "settia", "spear": "sword", "claw": "slash", "bloodbolt": "bolt",
            "pillar": "cotvang", "net": "hoan"}


FX_BROKEN = {}                       # mẫu hiệu ứng dựng lỗi -> lý do (hiện ở tab Cài đặt để dễ kiểm tra)
NUMPY_STATE = {"s": "?"}             # ok / thiếu / đang cài / lỗi cài


def numpy_ok():
    try:
        import numpy  # noqa: F401
        return True
    except Exception:
        return False


def ensure_numpy(app):
    """Hiệu ứng gõ phím cần thư viện numpy. Máy chưa có thì tự cài ở luồng phụ (không làm đứng app), cài xong dùng ngay."""
    if numpy_ok():
        NUMPY_STATE["s"] = "ok"
        return

    def run():
        import subprocess
        import importlib
        import site
        NUMPY_STATE["s"] = "đang cài"
        exe = sys.executable
        d = os.path.dirname(exe)
        for cand in ("python.exe", "python3.exe"):
            if os.path.exists(os.path.join(d, cand)):
                exe = os.path.join(d, cand)
                break
        base = [exe, "-m", "pip", "install", "--disable-pip-version-check", "--quiet"]
        lib = os.path.join(BASE_DIR, "ThuVien")
        tries = [base + ["--no-index", "--find-links", lib, "numpy"], base + ["numpy"], base + ["--user", "numpy"]]
        for cmd in tries:
            try:
                subprocess.run(cmd, cwd=BASE_DIR, timeout=600, capture_output=True,
                               creationflags=0x08000000 if IS_WIN else 0)            # CREATE_NO_WINDOW
            except Exception:
                continue
            try:
                site.addsitedir(site.getusersitepackages())
            except Exception:
                pass
            importlib.invalidate_caches()
            sys.modules.pop("numpy", None)
            if numpy_ok():
                NUMPY_STATE["s"] = "ok"
                FX_BROKEN.clear()

                def done():
                    for pl in (app.keyfx.bolt, app.keyfx.slash):
                        with pl.lock:
                            pl.cache.clear()                     # dựng lại hiệu ứng bằng ảnh đầy đủ
                    app.say("Đã cài xong thư viện numpy ✓", "Hiệu ứng gõ phím hoạt động đầy đủ rồi nhé!", timeout=6)
                    app.keyfx.warm()
                app.root.after(0, done)
                return
        NUMPY_STATE["s"] = "lỗi cài"
        log_error_msg("Không cài được numpy – hiệu ứng gõ phím dùng bản vẽ dự phòng")
    NUMPY_STATE["s"] = "thiếu"
    threading.Thread(target=run, daemon=True).start()


def _vfx_maker(cls):
    def maker(size, seed=0, mode="T", power=1.0, speed=1.0):
        try:
            fx = cls(size, seed, mode, power, speed)
            if not getattr(fx, "ok", True) and getattr(cls, "fallback", None):
                return cls.fallback(size, seed, mode, power, speed).bake()     # thiếu ảnh: dùng bản vẽ bằng code
            return fx.bake()
        except Exception:
            # lỗi khi dựng (thường do máy thiếu numpy): KHÔNG để mất hiệu ứng – chuyển sang bản vẽ bằng code
            if cls.name not in FX_BROKEN:
                FX_BROKEN[cls.name] = traceback.format_exc().strip().splitlines()[-1][:120]
                log_error()
            for fb in (getattr(cls, "fallback", None), LoiXich):
                if fb is None:
                    continue
                try:
                    return fb(size, seed, mode, power, speed).bake()
                except Exception:
                    continue
            raise
    maker.cls = cls
    return maker


FX_EFFECTS = [(c.name, VFX_LABELS[c.name], _vfx_maker(c), c.anchor) for c in IMG_FX]
FX_BY_KEY = {e[0]: e for e in FX_EFFECTS}
FX_THUNDER = tuple(e[0] for e in FX_EFFECTS if e[1].startswith("⚡"))


def fx_resolve(key):
    """Đổi lựa chọn ngẫu nhiên / mã cũ thành một mẫu cụ thể."""
    key = FX_ALIAS.get(key, key)
    if key == "random_thunder":
        return random.choice(FX_THUNDER)
    if key == "random" or key not in FX_BY_KEY:
        return random.choice([e[0] for e in FX_EFFECTS])
    return key


FX_CHOICES = [("random", "★ Ngẫu nhiên (đổi mỗi lần)"), ("random_thunder", "★ Ngẫu nhiên hệ Lôi (sấm sét)")] + [(e[0], e[1]) for e in FX_EFFECTS]


class _VfxBaker:
    """Luồng phụ dựng sẵn biến thể hiệu ứng (không làm khựng giao diện / nhân vật)."""

    def __init__(self):
        import queue
        self.q = queue.Queue()
        self.busy = set()
        self.th = None

    def ask(self, job, fn):
        if job in self.busy:
            return
        self.busy.add(job)
        self.q.put((job, fn))
        if self.th is None or not self.th.is_alive():
            self.th = threading.Thread(target=self._run, daemon=True)
            self.th.start()

    def _run(self):
        while True:
            try:
                job, fn = self.q.get(timeout=5)
            except Exception:
                return
            try:
                fn()
            except Exception:
                log_error()
            self.busy.discard(job)


VFX_BAKER = _VfxBaker()


class FxPlayer:
    """Phát hiệu ứng tại con trỏ nhập. Mỗi hiệu ứng là một cửa sổ trong suốt riêng (chuột bấm xuyên, không giành focus),
    tối đa MAX_LIVE cái cùng lúc: gõ dồn thì hiệu ứng chồng lớp, cái cũ nhất bị đẩy nhanh sang pha tan biến."""
    VARIANTS = 4
    MAX_LIVE = 3
    TICK = 40

    def __init__(self, app, default_key, mode="T"):
        self.app = app
        self.default_key = default_key
        self.mode = mode
        self.cache = {}                          # (mẫu, cỡ, chế độ) -> [dãy frame đã mã hoá]
        self.live = []                           # hiệu ứng đang chạy: dict(seq, i, pos, anchor, slot)
        self.slots = []                          # cửa sổ lớp (tạo dần, dùng lại)
        self.job = None
        self.last_key = None
        self.played = 0
        self.lock = threading.Lock()
        self.lw = IS_WIN or None                 # tương thích kiểm tra cũ

    def _slot(self):
        used = {e["slot"] for e in self.live}
        for k in range(len(self.slots)):
            if k not in used:
                return k
        if not IS_WIN:
            self.slots.append(None)
            return len(self.slots) - 1
        try:
            w = tk.Toplevel(self.app.root)
            w.overrideredirect(True)
            w.attributes("-topmost", True)
            w.geometry("1x1+-50+-50")
            lw = LayeredWin(w, extra_ex=0x20 | 0x08000000)     # WS_EX_TRANSPARENT | WS_EX_NOACTIVATE
            lw.update(-50, -50, 1, 1, b"\0\0\0\0")
            self.slots.append(lw)
        except Exception:
            log_error()
            self.slots.append(None)
        return len(self.slots) - 1

    @staticmethod
    def _enc(frames):
        return [(im.convert("RGBa").tobytes("raw", "BGRa"), im.width, im.height) for im in frames]

    def variants(self, key, size, mode=None):
        """Trả về các biến thể đã dựng. Lần đầu dựng 1 biến thể ngay, phần còn lại dựng ở luồng phụ."""
        mode = mode or self.mode
        k = (key, size, mode)
        with self.lock:
            vs = self.cache.get(k)
        if not vs:
            maker = FX_BY_KEY[key][2]
            vs = [self._enc(maker(size, 0, mode))]
            with self.lock:
                self.cache[k] = vs
                while len(self.cache) > 24:
                    self.cache.pop(next(iter(self.cache)))
        if len(vs) < self.VARIANTS:
            def more(k=k, key=key, size=size, mode=mode):
                maker = FX_BY_KEY[key][2]
                for seed in range(1, self.VARIANTS):
                    seq = self._enc(maker(size, seed, mode))
                    with self.lock:
                        lst = self.cache.get(k)
                        if lst is not None and len(lst) < self.VARIANTS:
                            lst.append(seq)
            VFX_BAKER.ask(k, more)
        return vs

    def play(self, x, y, size, key=None, mode=None):
        mode = mode or self.mode
        key = fx_resolve(key or self.default_key)
        self.last_key = key
        vs = self.variants(key, size, mode)
        seq = random.choice(list(vs))
        if len(self.live) >= self.MAX_LIVE:                    # quá tải: cái cũ nhất nhảy sang pha tan biến
            old = self.live[0]
            old["i"] = max(old["i"], len(old["seq"]) - 3)
            if len(self.live) >= self.MAX_LIVE + 1:
                self._end(self.live.pop(0))
        self.live.append(dict(seq=seq, i=0, pos=(int(x), int(y)), anchor=FX_BY_KEY[key][3], slot=self._slot()))
        self.played += 1
        if self.job is None:
            self._step()

    def _end(self, e):
        lw = self.slots[e["slot"]] if e["slot"] < len(self.slots) else None
        if lw:
            try:
                lw.update(-50, -50, 1, 1, b"\0\0\0\0")
            except Exception:
                log_error()

    def _step(self):
        alive = []
        for e in self.live:
            if e["i"] >= len(e["seq"]):
                self._end(e)                                     # hết hiệu ứng: ẩn cửa sổ, không để lại hình
                continue
            data, w, h = e["seq"][e["i"]]
            lw = self.slots[e["slot"]] if e["slot"] < len(self.slots) else None
            if lw:
                try:
                    ax, ay = e["anchor"]
                    lw.update(e["pos"][0] - int(w * ax), e["pos"][1] - int(h * ay), w, h, data, self._alpha())
                except Exception:
                    log_error()
            e["i"] += 1
            alive.append(e)
        self.live = alive
        self.job = self.app.root.after(self._tick(), self._step) if self.live else None

    def _alpha(self):
        try:
            return int(255 * max(0.15, min(1.0, float(self.app.store.s.get("key_fx_alpha", 1.0)))))
        except Exception:
            return 255

    def _tick(self):
        """Nhịp phát theo thanh trượt tốc độ: 0.4 (chậm, 100 ms/khung) .. 2.0 (nhanh, 20 ms/khung)."""
        try:
            sp = max(0.4, min(2.0, float(self.app.store.s.get("key_fx_speed", 1.0))))
        except Exception:
            sp = 1.0
        return max(20, int(round(self.TICK / sp)))


class KeyFx:
    def __init__(self, app):
        self.app = app
        self.bolt = FxPlayer(app, "bolt", "T")    # kênh hiệu ứng khi gõ
        self.slash = FxPlayer(app, "slash", "D")  # kênh hiệu ứng khi xoá (diễn biến ngược: hút vào, rút về, tan rã)
        self.t_last = {"T": 0.0, "D": 0.0}
        self.prev_caret = None                    # (vị trí con trỏ nhập, lúc ghi) – để biết nội dung có đổi không
        self.skipped = 0
        self.hist = {"T": [], "D": []}
        self.cool = {"T": 0.0, "D": 0.0}
        self.last_pos = None
        self.finder = CaretFinder()
        try:
            app.root.after(2500, self.warm)
        except Exception:
            pass
        self.wait = None                          # (mã yêu cầu, loại, lúc hỏi, vị trí chuột dự phòng)
        self.rid = 0
        self.stats = {}                           # tên chương trình -> cách tìm con trỏ nhập lần gần nhất
        self.last_info = ""

    def size(self, text_h=None):
        """Cỡ hiệu ứng: theo cỡ chữ phần mềm (chiều cao con trỏ nhập) nếu bật, nhân thêm hệ số trên thanh trượt."""
        s = self.app.store.s
        k = float(s.get("key_fx_size", 1.0))
        if s.get("key_fx_autosize", True) and text_h and 6 <= text_h <= 300:
            base = text_h * 6.0
        else:
            base = 150 * self.app.dpi
        return int(max(60, min(560, round(base * k / 20.0) * 20)))

    def _note(self, how):
        exe = get_foreground_exe() or "?"
        self.stats[exe] = how
        self.last_info = "%s → %s" % (app_name(exe) if exe != "?" else "?", how)

    def _play(self, kind, pos, text_h=None):
        s = self.app.store.s
        self.last_pos = pos
        self.last_size = self.size(text_h)
        if text_h:
            self.last_info = self.last_info + " • cỡ chữ %dpx" % text_h
        try:
            if kind == "T":
                self.bolt.play(pos[0], pos[1], self.last_size, s.get("key_fx_type", "bolt"))
            else:
                self.slash.play(pos[0], pos[1], self.last_size, s.get("key_fx_del", "slash"))
        except Exception:                                  # một mẫu lỗi không được làm hỏng cả vòng xử lý phím
            log_error()
            try:
                (self.bolt if kind == "T" else self.slash).play(pos[0], pos[1], self.last_size, "lientinh" if kind == "T"
                                                               else "loithuong")
            except Exception:
                pass

    def _pointer(self):
        px, py = self.app.root.winfo_pointerxy()
        return (px + 14, py + 18)

    MIN_GAP = {"T": 0.045, "D": 0.06}           # giữ phím lặp quá dày thì gộp; gõ bình thường lần nào cũng có hiệu ứng

    def _changed(self, pos):
        """Con trỏ nhập có dịch chuyển so với lần trước không (= nội dung thật sự thay đổi)."""
        prev = self.prev_caret
        if prev is None or pos is None:
            return True
        (px, py), pt = prev
        return abs(pos[0] - px) > 1 or abs(pos[1] - py) > 1

    def _remember(self, pos):
        if pos is not None:
            self.prev_caret = (pos, time_now())

    def on_key(self, kind, vk=None):
        s = self.app.store.s
        if not s.get("key_fx", True) or self.app.fs_hidden:
            return
        t = time_now()
        if t - self.t_last[kind] >= self.MIN_GAP[kind]:
            self.t_last[kind] = t
            r = caret_info()                                # 1) con trỏ hệ thống: nhanh, làm ngay
            pos, pw, th = r[0], r[1], (r[2] if len(r) > 2 else None)
            if pw:
                return                                      # ô mật khẩu: không hiệu ứng
            if pos is not None:
                self._note("con trỏ hệ thống")
                if vk == 0x2E or self._changed(pos):        # Delete xoá chữ bên phải: con trỏ đứng yên vẫn tính
                    self._remember(pos)
                    self._play(kind, pos, th)
                else:                                       # chưa thấy dịch chuyển: phần mềm có thể chưa kịp xử lý -> xem lại
                    self.app.root.after(70, lambda: self._recheck(kind, th))
            elif self.finder.available():
                self.rid += 1                               # 2) hỏi UI Automation / MSAA ở tiến trình phụ
                self.wait = (self.rid, kind, t, self._pointer(), vk)
                self.finder.request(self.rid)
            else:
                self._note("cạnh chuột")
                self._play(kind, self._pointer())
            self.t_last[kind] = time_now()                  # lần đầu dựng hình có thể lâu -> tính mốc sau khi phát
        self._react(kind, t)

    def _recheck(self, kind, th):
        try:
            r = caret_info()
            pos = r[0]
            if pos is not None and self._changed(pos):
                self._remember(pos)
                self._play(kind, pos, (r[2] if len(r) > 2 else None) or th)
            else:
                self.skipped += 1
                self._note("nội dung không đổi – bỏ qua")
        except Exception:
            log_error()

    def warm(self):
        """Nạp sẵn ảnh + dựng sẵn mẫu đang chọn khi máy rảnh, để phím đầu tiên không bị khựng."""
        try:
            s = self.app.store.s
            if not s.get("key_fx", True):
                return
            sz = self.size()
            for pl, k in ((self.bolt, s.get("key_fx_type", "bolt")), (self.slash, s.get("key_fx_del", "slash"))):
                if k in FX_BY_KEY:
                    pl.variants(k, sz)
        except Exception:
            log_error()

    def poll(self, idle=False):
        """Gọi mỗi nhịp từ luồng chính: nhận kết quả tìm con trỏ nhập, quá hạn thì hiện cạnh chuột.
        idle (không có phím đang chờ): ghi lại vị trí con trỏ nhập lúc yên – hook luôn nhận phím TRƯỚC phần mềm đích,
        nên đây chắc chắn là vị trí trước cú bấm tiếp theo (Home, bấm chuột chỗ khác... không bị tính nhầm là sửa chữ)."""
        self._pn = getattr(self, "_pn", 0) + 1
        if idle and self._pn % 2 == 0 and self.app.store.s.get("key_fx", True) and not self.wait:
            try:
                r = caret_info()
                if r[0] is not None and not r[1]:
                    self.prev_caret = (r[0], time_now())
            except Exception:
                pass
        while True:
            try:
                res = self.finder.results.get_nowait()
            except Exception:
                break
            rid, pos, pw, how = res[:4]
            th = res[4] if len(res) > 4 else None
            if self.wait and rid == self.wait[0]:
                _, kind, _t, ptr, vk = self.wait
                self.wait = None
                if pw:
                    self._note("ô mật khẩu – bỏ qua")
                    continue
                self._note(how or "cạnh chuột")
                if pos is not None and vk != 0x2E and not self._changed(pos):
                    self.skipped += 1
                    self._note("nội dung không đổi – bỏ qua")
                    continue
                self._remember(pos)
                self._play(kind, pos or ptr, th if pos else None)
        if self.wait and time_now() - self.wait[2] > 0.25:
            _, kind, _t, ptr, _vk = self.wait
            self.wait = None
            self._note("cạnh chuột (phần mềm chậm trả lời)")
            self._play(kind, ptr)

    def _react(self, kind, t):
        s = self.app.store.s
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
                pos = self.last_pos or self._pointer()
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
            PACK_META.clear()
            PACK_META.update(pk.meta)
            # nhân vật đổi cách thả rơi / đập tường ở bản mới (meta "rev" tăng) -> áp dụng mặc định mới một lần
            rev = int(pk.meta.get("rev", 0) or 0)
            pr = dict(s.get("pack_rev") or {})
            kk = pack_key(s.get("pack") or "")
            if rev and pr.get(kk, 0) < rev:
                for k2 in ("drop_action", "wall_hit_action"):
                    if pk.meta.get(k2):
                        s[k2] = pk.meta[k2]
                pr[kk] = rev
                s["pack_rev"] = pr
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
        self.root.after(1500, lambda: ensure_numpy(self))
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

    def switch_pack(self, ref):
        """Đổi nhân vật: cất bộ gán chuột / tên của nhân vật cũ, lấy lại bộ của nhân vật mới (lần đầu = mặc định)."""
        import copy
        s = self.store.s
        old = s.get("pack") or ""
        if ref == old and self.pet.pack is not None:
            return False
        prof = s.get("profiles") or {}
        prof[pack_key(old)] = {k: copy.deepcopy(s.get(k)) for k in PROFILE_KEYS}
        path = pack_resolve(ref) or BUILTIN_PACK
        if not os.path.isdir(path):
            return False
        s["pack"] = ref
        saved = prof.get(pack_key(ref))
        if saved:
            s.update(copy.deepcopy(saved))
        else:
            name = ""
            try:
                name = ShimejiPack(path).name
            except Exception:
                pass
            s.update(pack_defaults(pack_meta(path), name))
        s["profiles"] = prof
        self.store.fix_triggers()
        self.store.save()
        self.pet.apply_look()
        return True

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
            self.keyfx.finder.stop()
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
        ttk.Label(left, text="Chọn nhân vật:").pack(anchor="w", pady=(8, 0))
        bf = ttk.Frame(left)
        bf.pack(anchor="w")
        self.packcb = ttk.Combobox(bf, state="readonly", width=20)
        self.packcb.pack(side="left")
        self.packcb.bind("<<ComboboxSelected>>", lambda e: self.pick_pack())
        ttk.Button(bf, text="Nạp Shimeji khác", style="Small.TButton", command=self.load_pack).pack(side="left", padx=4)

        right = ttk.Frame(f)
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))
        ttk.Label(right, text="Động tác của nhân vật", style="H.TLabel").pack(anchor="w")
        ttk.Label(right, text="Nhấp đúp hoặc nhấn Space để bật/tắt 'Tự làm'. Động tác tắt tự làm vẫn dùng được khi gán chuột.",
                  foreground=C_MUTED, wraplength=520).pack(anchor="w")
        cols = ("name", "group", "assign", "free")
        tv = ttk.Treeview(right, columns=cols, show="headings", selectmode="browse")
        for c, h, w in (("name", "Động tác", 235), ("group", "Nhóm", 80), ("assign", "Đang gán cho", 145), ("free", "Tự làm", 55)):
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
        self.app.switch_pack(pack_ref(dst))
        self.refresh(True)

    def reset_pack(self):
        self.app.switch_pack("")
        self.refresh(True)

    def fill_packs(self):
        self._packs = available_packs()
        self.packcb.config(values=[b for _, b in self._packs])
        cur = self.app.store.s.get("pack") or ""
        self.packcb.set(next((b for r, b in self._packs if r == cur), self.app.pet.pack.name if self.app.pet.pack else ""))

    def pick_pack(self):
        lab = self.packcb.get()
        ref = next((r for r, b in self._packs if b == lab), None)
        if ref is None:
            return
        self.app.switch_pack(ref)
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
        pk = self.app.pet.pack
        d = pack_defaults(pk.meta if pk else {}, pk.name if pk else "")
        self.app.set_setting("triggers", d["triggers"])
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
        self.kauto_v = tk.BooleanVar(value=s.get("key_fx_autosize", True))
        ttk.Checkbutton(kf, text="Kích thước theo cỡ chữ của phần mềm (chữ to → hiệu ứng to)", variable=self.kauto_v,
                        command=lambda: self.app.set_setting("key_fx_autosize", self.kauto_v.get())
                        ).grid(row=9, column=0, columnspan=2, sticky="w")

        def slider(row, text, key, lo, hi, fmt):
            ttk.Label(kf, text=text).grid(row=row, column=0, sticky="w", pady=3)
            fr = ttk.Frame(kf)
            fr.grid(row=row, column=1, sticky="w", padx=6)
            v = tk.DoubleVar(value=float(s.get(key, 1.0)))
            lab = ttk.Label(fr, text=fmt(v.get()), width=12, style="Muted.TLabel")
            sc = ttk.Scale(fr, from_=lo, to=hi, variable=v, length=200,
                           command=lambda _x: lab.config(text=fmt(v.get())))
            sc.pack(side="left")
            lab.pack(side="left", padx=6)
            sc.bind("<ButtonRelease-1>", lambda e: self.app.set_setting(key, round(v.get(), 2)))
            return v
        self.kalpha_v = slider(10, "Độ đậm (trong suốt):", "key_fx_alpha", 0.15, 1.0, lambda x: "%d%%" % round(x * 100))
        self.kspeed_v = slider(11, "Tốc độ xuất hiện:", "key_fx_speed", 0.4, 2.0,
                               lambda x: ("chậm " if x < 0.9 else ("nhanh " if x > 1.1 else "vừa ")) + "×%.1f" % x)
        ttk.Label(kf, text="Hệ số cỡ:").grid(row=3, column=0, sticky="w", pady=4)
        self.kfs_v = tk.DoubleVar(value=s.get("key_fx_size", 1.0))
        ksc = ttk.Scale(kf, from_=0.4, to=2.5, variable=self.kfs_v, length=200)
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
                                                         self.fx_preview_set(lab2k[self.fxt.get()], "T")))
        self.fxd.bind("<<ComboboxSelected>>", lambda e: (self.app.set_setting("key_fx_del", lab2k[self.fxd.get()]),
                                                         self.fx_preview_set(lab2k[self.fxd.get()], "D")))
        tb = ttk.Frame(kf)
        tb.grid(row=6, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Button(tb, text="⚡ Thử gõ trên màn hình", style="Small.TButton",
                   command=lambda: self._kfx_demo("T")).pack(side="left")
        ttk.Button(tb, text="✕ Thử xoá trên màn hình", style="Small.TButton",
                   command=lambda: self._kfx_demo("D")).pack(side="left", padx=6)
        ttk.Label(kf, text="App chỉ nhận biết 'vừa gõ' hay 'vừa xoá', không ghi lại phím nào. Tự tắt ở ô mật khẩu và khi "
                           "trình chiếu. Tắt mục này là gỡ hẳn chức năng bắt phím.", style="Muted.TLabel", wraplength=470,
                  justify="left").grid(row=7, column=0, columnspan=2, sticky="w")
        self.kdiag = ttk.Label(kf, text="", style="Muted.TLabel", wraplength=470, justify="left")
        self.kdiag.grid(row=8, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.kdiag_loop()
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

    def kdiag_loop(self):
        """Cho biết phần mềm vừa gõ tìm được con trỏ nhập bằng cách nào (để kiểm tra Chrome, Zalo...)."""
        if not self.alive():
            return
        kf = self.app.keyfx
        txt = "Vị trí hiệu ứng lần gõ gần nhất: " + (kf.last_info or "chưa gõ")
        st = NUMPY_STATE.get("s")
        if st == "đang cài":
            txt = "⏳ Đang tự cài thư viện numpy cho hiệu ứng (cần mạng, vài phút)...\n" + txt
        elif st in ("thiếu", "lỗi cài"):
            txt = ("⚠ Máy thiếu thư viện numpy nên hiệu ứng đang dùng bản vẽ dự phòng. Cách sửa: chạy lại ChayChibi.bat khi "
                   "có mạng, hoặc mở cmd gõ:  py -m pip install numpy\n") + txt
        elif FX_BROKEN:
            txt = "⚠ Mẫu lỗi (đang dùng bản dự phòng): " + ", ".join(FX_BROKEN) + "\n" + txt
        if kf.stats:
            txt += "\n" + " • ".join("%s: %s" % (app_name(e) if e != "?" else "?", h) for e, h in list(kf.stats.items())[-5:])
        self.kdiag.config(text=txt)
        self.win.after(1000, self.kdiag_loop)

    def fx_preview_set(self, key, mode="T"):
        self._fxp.update(key=key, mode=mode, frames=[], i=0)

    def fx_preview_loop(self):
        """Ô xem trước: phát lặp mẫu đang chọn trên nền tối, có dòng chữ giả làm chỗ gõ."""
        if not self.alive():
            return
        try:
            p = self._fxp
            if not p["frames"] or p["i"] >= len(p["frames"]) + 6:
                key = p["key"]
                key = fx_resolve(key)
                e = FX_BY_KEY[key]
                mode = p.get("mode", "T")
                frames = e[2](150, random.randint(0, 99), mode)
                p.update(frames=frames, i=0, anchor=e[3], name=e[1] + ("  (khi xoá)" if mode == "D" else "  (khi gõ)"))
            cv = self.fxprev
            cv.delete("all")
            cv.create_text(130, 150, text="Nhắc việc|", fill="#cfc6e6", font=(FONT, 13))
            cv.create_text(130, 14, text=p.get("name", ""), fill=C_GOLD, font=(FONT, 9, "bold"))
            if p["i"] < len(p["frames"]):
                im = p["frames"][p["i"]]
                al = float(self.app.store.s.get("key_fx_alpha", 1.0))
                if al < 0.999:
                    im = im.copy()
                    im.putalpha(im.getchannel("A").point(lambda v: int(v * al)))
                ax, ay = p["anchor"]
                self._fxp_img = ImageTk.PhotoImage(im)
                cv.create_image(178 - im.width * ax, 150 - im.height * ay, image=self._fxp_img, anchor="nw")
            p["i"] += 1
        except Exception:
            log_error()
        self.win.after(self.app.keyfx.bolt._tick(), self.fx_preview_loop)

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
            self.fill_packs()
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
SKIP_ITEMS = ("ChibiData", "__pycache__")
INSTALL_ITEMS = ["ChibiNhacViec.pyw", "ChayChibi.bat", "README.md", "version.json", "NhanVat", "HieuUng", "tests", "tools"]
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
        # chép MỌI thứ trong gói (thư mục mới ở bản sau cũng được chép), trừ dữ liệu người dùng
        items = list(INSTALL_ITEMS) + [n for n in os.listdir(root) if n not in INSTALL_ITEMS and n not in SKIP_ITEMS
                                       and not n.startswith(".")]
        for it in items:
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
    if "--caret-helper" in sys.argv:          # tiến trình phụ tìm con trỏ nhập
        caret_helper_main()
        return
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
