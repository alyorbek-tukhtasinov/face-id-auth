@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Avval install.bat ni ishga tushiring.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m faceid camera
echo.
pause
