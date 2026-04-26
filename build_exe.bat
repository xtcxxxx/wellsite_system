@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo Step 1: In CMD run .venv\Scripts\activate.bat ^(PowerShell: .venv\Scripts\Activate.ps1^) before pip commands.
echo Step 2: First time: pip install -r requirements.txt pyinstaller
echo This bat uses .venv\Scripts\python.exe directly; double-click still works without activate.
echo If Fatal error in launcher: delete .venv, py -3 -m venv .venv, then pip install again.
echo.

call "%~dp0scripts\build_pyinstaller_core.bat"
if errorlevel 1 (
  echo.
  echo BUILD FAILED.
  pause
  exit /b 1
)

echo.
if exist "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\update_desktop_shortcut.ps1"
if not exist "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" echo PowerShell not found, skipped desktop shortcut.

echo.
echo OK. Output under dist\ (client folder name matches app title with client suffix).
pause
