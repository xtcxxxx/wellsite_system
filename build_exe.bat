@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo 安装打包工具请执行（两行分开，不要打成 pyinstallerpip）:
echo   .venv\Scripts\pip install pyinstaller
echo.

if not exist ".venv\Scripts\pyinstaller.exe" (
  echo 未找到 pyinstaller，正在尝试安装...
  .venv\Scripts\pip install pyinstaller
)

echo 根据 assets\app_icon_source.png 生成 app.ico ...
.venv\Scripts\python.exe scripts\generate_app_icon.py
if errorlevel 1 (
  echo 图标脚本失败，请确认已 pip install pillow
  pause
  exit /b 1
)

.venv\Scripts\pyinstaller.exe -y --clean "仓库物资调度.spec"

echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\update_desktop_shortcut.ps1"

echo.
echo 完成。exe 在 dist\仓库物资调度\ 目录（目录模式；项目内资源已打入 _internal，首次运行会在 exe 同目录生成 wellsite.db、warehouse_layout.json 等可写文件）。
echo 桌面「仓库物资调度」快捷方式已随打包更新；若图标仍是旧的，请按脚本提示刷新图标缓存，或删掉桌面旧快捷后重新运行本 bat。
pause
