@echo off
chcp 65001 >nul
setlocal EnableExtensions
REM Pure client build; run from project root (caller cd first).

if not exist ".venv\Scripts\python.exe" (
  echo Missing .venv\Scripts\python.exe
  echo Run: py -3 -m venv .venv
  echo Then: .venv\Scripts\pip install -r requirements.txt pyinstaller
  exit /b 1
)

if not exist ".venv\Scripts\pyinstaller.exe" (
  echo Installing pyinstaller...
  .venv\Scripts\pip install pyinstaller
  if errorlevel 1 exit /b 1
)

echo Generating assets\app.ico ...
.venv\Scripts\python.exe scripts\generate_app_icon.py
if errorlevel 1 (
  echo generate_app_icon.py failed. pip install pillow
  exit /b 1
)

echo Building client bundle...
.venv\Scripts\python.exe -m PyInstaller -y --clean "%CD%\warehouse_dispatch.spec"
if errorlevel 1 (
  echo PyInstaller failed.
  exit /b 1
)

endlocal & exit /b 0
