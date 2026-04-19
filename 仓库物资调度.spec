# -*- mode: python ; coding: utf-8 -*-
import os


def _project_data_files(project_root):
    """将项目内非 Python 数据文件打进包（排除 venv / 构建输出 / 本地数据库）。"""
    skip_dirs = {".venv", "dist", "build", "__pycache__", ".git", ".cursor"}
    skip_files = {"wellsite.db"}
    out = []
    for dirpath, dirnames, filenames in os.walk(project_root):
        dirnames[:] = sorted(d for d in dirnames if d not in skip_dirs)
        for fn in filenames:
            if fn.endswith(".pyc") or fn.endswith(".py"):
                continue
            if fn in skip_files:
                continue
            src = os.path.join(dirpath, fn)
            rel = os.path.relpath(src, project_root)
            dest_dir = os.path.dirname(rel)
            if not dest_dir or dest_dir == ".":
                dest_dir = os.curdir
            out.append((src, dest_dir))
    return out


_bundle = _project_data_files(SPECPATH)

_app_icon = os.path.normpath(os.path.join(SPECPATH, "assets", "app.ico"))

a = Analysis(
    ["main.py"],
    pathex=[SPECPATH],
    binaries=[],
    datas=_bundle,
    hiddenimports=["openpyxl.cell._writer"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="仓库物资调度",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_app_icon if os.path.isfile(_app_icon) else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="仓库物资调度",
)
