@echo off
setlocal
cd /d "%~dp0"
echo ============================================
echo   FaceID Next - o'rnatish
echo ============================================
set "PY="
for %%V in (3.13 3.12 3.11) do (
  if not defined PY (
    py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V"
  )
)
if not defined PY (
  python -c "import sys; assert sys.version_info >= (3, 11)" >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo Python 3.11+ topilmadi. https://www.python.org/downloads/ dan Python 3.12 yoki 3.13 ni o'rnating
  echo ^(o'rnatishda "Add python.exe to PATH" belgisini qo'ying^).
  pause
  exit /b 1
)
echo Python: %PY%
if not exist .venv (
  %PY% -m venv .venv || goto :err
)
call .venv\Scripts\activate.bat || goto :err
python -m pip install --upgrade pip || goto :err
python -m pip install -r requirements.txt || goto :err
echo.
echo Neyron tarmoq modellari yuklab olinmoqda (~290 MB, bir marta)...
python -m faceid models || goto :err
echo.
python -m faceid doctor
echo.
echo Tayyor! Ilovani ishga tushirish uchun: run.bat
pause
exit /b 0

:err
echo.
echo Xatolik yuz berdi. Yuqoridagi xabarni tekshiring.
pause
exit /b 1
