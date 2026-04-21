"""登录与密码校验（PBKDF2）。首次无用户时由 AuthManager 写入默认账号。"""
import hashlib
import os
from typing import Any, Dict, Optional

from database import Database

_PBKDF2_ITERATIONS = 120_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        _PBKDF2_ITERATIONS,
    )
    return f"{salt.hex()}:{_PBKDF2_ITERATIONS}:{dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, iters_s, hash_hex = stored.split(":")
        iters = int(iters_s)
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iters,
        )
        return dk.hex() == hash_hex
    except (ValueError, AttributeError):
        return False


class AuthManager:
    def __init__(self, db: Database):
        self.db = db
        self.ensure_default_users()

    def ensure_default_users(self) -> None:
        """无用户时创建演示账号：admin / 132123，普通用户 wgd123 / 112233。"""
        n = self.db.fetch_scalar("SELECT COUNT(*) FROM users")
        if not n or int(n) == 0:
            self.db.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                ("admin", hash_password("132123"), "admin"),
            )
            self.db.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                ("wgd123", hash_password("112233"), "user"),
            )
            return
        # 已有库（例如早期版本）若尚无 wgd123，则补建默认普通账号
        row = self.db.fetchone(
            "SELECT id FROM users WHERE LOWER(username) = LOWER(?)",
            ("wgd123",),
        )
        if row is None:
            self.db.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                ("wgd123", hash_password("112233"), "user"),
            )
        # 仍使用旧默认密码 admin123 的管理员 → 新默认 132123（自定义密码不受影响）
        admin_row = self.db.fetchone(
            "SELECT id, password_hash FROM users WHERE LOWER(username) = LOWER(?)",
            ("admin",),
        )
        if admin_row and verify_password("admin123", admin_row["password_hash"] or ""):
            self.db.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (hash_password("132123"), int(admin_row["id"])),
            )

    def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        u = (username or "").strip()
        if not u:
            return None
        row = self.db.fetchone(
            """
            SELECT id, username, password_hash, role
            FROM users
            WHERE LOWER(username) = LOWER(?)
            """,
            (u,),
        )
        if not row:
            return None
        if not verify_password(password, row["password_hash"]):
            return None
        return {
            "id": int(row["id"]),
            "username": row["username"],
            "role": (row["role"] or "user").strip(),
        }
