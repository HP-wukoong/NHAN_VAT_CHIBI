@echo off
chcp 65001 >nul
title Chibi Nhac Viec
cd /d "%~dp0"

rem ---- Tim Python ----
set "PY="
where py >nul 2>nul && set "PY=py -3"
if defined PY goto :havepy
where python >nul 2>nul && set "PY=python"
if defined PY goto :havepy
echo.
echo  KHONG TIM THAY PYTHON.
echo  Hay cai Python 3.9 tro len tai https://www.python.org/downloads/
echo  Khi cai nho tick o "Add python.exe to PATH".
echo.
pause
exit /b 1

:havepy
%PY% -c "import tkinter" >nul 2>nul
if errorlevel 1 (
  echo  Python thieu tkinter. Hay cai lai Python ban day du tu python.org.
  pause
  exit /b 1
)

rem ---- Pillow: BAT BUOC de ve nhan vat ----
%PY% -c "import PIL" >nul 2>nul
if not errorlevel 1 goto :run
echo  Dang cai Pillow - chi lan dau...
%PY% -m pip install --quiet --disable-pip-version-check --no-index --find-links "%~dp0ThuVien" pillow >nul 2>nul
%PY% -c "import PIL" >nul 2>nul
if not errorlevel 1 goto :run
%PY% -m pip install --quiet --disable-pip-version-check pillow
%PY% -c "import PIL" >nul 2>nul
if not errorlevel 1 goto :run
echo.
echo  CHUA CAI DUOC PILLOW.
echo  - May co mang: chay lai file nay.
echo  - May khong mang: giai nen goi "BoCaiPillow_Offline" vao thu muc ThuVien roi chay lai.
echo.
pause
exit /b 1

:run
set "PYW="
where pyw >nul 2>nul && set "PYW=pyw -3"
if not defined PYW (
  where pythonw >nul 2>nul && set "PYW=pythonw"
)
if defined PYW (
  start "" %PYW% "%~dp0ChibiNhacViec.pyw"
) else (
  start "" %PY% "%~dp0ChibiNhacViec.pyw"
)
exit /b 0
