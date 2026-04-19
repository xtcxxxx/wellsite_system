@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo  用备份的 wellsite.db 恢复数据库
echo ============================================
echo.
echo 请先关闭「仓库物资调度」程序（含 exe），再执行本脚本。
echo.
echo 用法（任选一种）：
echo   1. 将备份的 wellsite.db 拖到本 bat 图标上
echo   2. 在本窗口输入备份文件完整路径后回车
echo.
if not "%~1"=="" goto RUN

set /p SRC=请输入备份 wellsite.db 的路径: 
if "%SRC%"=="" (
  echo 未输入路径，已取消。
  pause
  exit /b 1
)
set "ARG1=%SRC%"
goto RUN2

:RUN
set "ARG1=%~1"

:RUN2
if not exist ".venv\Scripts\python.exe" (
  echo 未找到 .venv\Scripts\python.exe，请在项目根目录运行本 bat。
  pause
  exit /b 1
)

.venv\Scripts\python.exe scripts\restore_wellsite_db.py "%ARG1%"
if errorlevel 1 (
  echo.
  echo 恢复失败，请根据上方提示检查路径与文件是否为 SQLite 数据库。
)
echo.
pause
