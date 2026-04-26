"""
本仓库为「纯客户端」：仅连接共享 wellsite.db，不在 exe 旁使用本机库。
路径与 network_settings.json 仍与 exe 同目录。
"""
import json
import os
import sys


def app_data_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def network_settings_file() -> str:
    return os.path.join(app_data_dir(), "network_settings.json")


def read_network_settings_dict() -> dict:
    path = network_settings_file()
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def read_network_db_path() -> str:
    data = read_network_settings_dict()
    if not data or data.get("enabled") is False:
        return ""
    return str(data.get("db_path") or "").strip()


def local_wellsite_path() -> str:
    return os.path.join(app_data_dir(), "wellsite.db")


def resolved_shared_database_path() -> str:
    raw = (os.environ.get("WELLSITE_DB_PATH") or os.environ.get("WELLSITE_DB") or "").strip()
    if not raw:
        raw = read_network_db_path()
    if not raw:
        return ""
    return os.path.normpath(os.path.expandvars(str(raw).strip()))


def shared_pack_data_root() -> str:
    """
    与 wellsite.db 同级的目录（UNC 上通常即共享根）。
    程序仅将「Picture record」放在此目录下与库一起共享；无有效共享库路径时返回空字符串。
    """
    p = resolved_shared_database_path()
    if not p:
        return ""
    parent = os.path.dirname(p)
    return os.path.normpath(parent) if parent else ""
