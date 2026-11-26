"""Máy thiếu numpy: mọi hiệu ứng gõ phím vẫn phải ra hình (dùng bản vẽ dự phòng), lỗi phát hiệu ứng không làm hỏng vòng phím."""
import sys
sys.modules["numpy"] = None                       # giả lập máy chưa cài numpy
from common import load, check, RESULTS

C = load()
for key in C.FX_BY_KEY:
    for m in "TD":
        try:
            fr = C.FX_BY_KEY[key][2](60, 0, m)
            ok = sum(1 for f in fr if f.getbbox()) > 5
        except Exception:
            ok = False
        check(ok, "thiếu numpy vẫn có hình: %s (%s)" % (key, m))
check("lientinh" not in C.FX_BROKEN and "loithuong" not in C.FX_BROKEN, "Lôi tinh / Lôi thương vẽ thuần, không cần numpy")
check(C.numpy_ok() is False, "nhận biết đúng máy thiếu numpy")
print("\n%d/%d đạt" % (sum(RESULTS), len(RESULTS)))
sys.exit(0 if all(RESULTS) else 1)
