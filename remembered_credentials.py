"""
本机记住「共享库路径 + 账号密码」，仅写入 exe/项目根旁的 remembered_login.json。
密码以 Base64 存储（非加密），勿在不可信环境勾选；勿提交该文件到版本库。
"""
from __future__ import annotations

import base64
import json
import os
from typing import Any, Dict

from runtime_flags import app_data_dir

FILENAME = "remembered_login.json"


def remembered_login_file() -> str:
    return os.path.join(app_data_dir(), FILENAME)


def load() -> Dict[str, Any]:
    path = remembered_login_file()
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def decode_password(data: Dict[str, Any]) -> str:
    raw = str(data.get("password_b64") or "").strip()
    if not raw:
        return ""
    try:
        return base64.standard_b64decode(raw.encode("ascii")).decode("utf-8")
    except Exception:
        return ""


def save(remember: bool, db_path: str, username: str, password: str) -> None:
    path = remembered_login_file()
    if not remember:
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass
        return
    payload = {
        "remember": True,
        "db_path": (db_path or "").strip(),
        "username": (username or "").strip(),
        "password_b64": base64.standard_b64encode(password.encode("utf-8")).decode("ascii"),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
