"""
打包 exe 首次运行：尚无 network_settings.json 时，填写共享库路径并登录。
共享库若尚无用户，AuthManager 会在首次校验前写入默认账号（见 auth_service）。
"""
import json
import os
from typing import Any, Dict, Optional, Tuple

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QFormLayout,
    QSizePolicy,
    QCheckBox,
)
from PySide6.QtGui import QIcon

import remembered_credentials
from auth_service import AuthManager
from database import Database


class FrozenBootstrapDialog(QDialog):
    def __init__(self, settings_path: str, parent=None):
        super().__init__(parent)
        self._settings_path = settings_path
        self._db: Optional[Database] = None
        self._user: Optional[Dict[str, Any]] = None

        self.setWindowTitle("首次运行：连接共享数据库")
        self.setModal(True)
        self.resize(500, 300)

        self.setStyleSheet(
            """
            QDialog { background-color: #ffffff; }
            QLabel { color: #303133; }
            QLabel#bootstrapTip {
                margin: 0;
                padding: 0;
            }
            QLineEdit {
                background-color: #ffffff;
                border: 1px solid #dcdfe6;
                border-radius: 4px;
                padding: 6px 10px;
                color: #303133;
            }
            QLineEdit:focus { border-color: #409eff; }
            QPushButton {
                background-color: #ffffff;
                color: #606266;
                border: 1px solid #dcdfe6;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                color: #409eff;
                border-color: #c6e2ff;
                background-color: #ecf5ff;
            }
            QCheckBox {
                color: #303133;
                font-size: 13px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 10, 20, 14)
        root.setSpacing(6)

        tip = QLabel("请填写主机已共享的 wellsite.db 路径，并用该库中的账号登录。")
        tip.setObjectName("bootstrapTip")
        tip.setWordWrap(True)
        tip.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        tip.setContentsMargins(0, 0, 0, 0)
        root.addWidget(tip)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setVerticalSpacing(8)
        form.setHorizontalSpacing(10)

        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText(r"\\192.168.1.20\共享\wellsite.db")
        form.addRow("共享数据库：", self.path_edit)

        self.user_edit = QLineEdit()
        self.user_edit.setPlaceholderText("用户名")
        self.pass_edit = QLineEdit()
        self.pass_edit.setPlaceholderText("密码")
        self.pass_edit.setEchoMode(QLineEdit.Password)
        form.addRow("用户名：", self.user_edit)
        form.addRow("密码：", self.pass_edit)
        root.addLayout(form)

        self.remember_cb = QCheckBox(
            "记住共享路径、账号和密码（保存在本机，勿在公用电脑勾选）"
        )
        self.remember_cb.setChecked(False)
        root.addWidget(self.remember_cb)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("退出")
        btn_ok = QPushButton("连接并登录")
        btn_ok.setDefault(True)
        btn_ok.setStyleSheet(
            "background: #409eff; color: white; padding: 8px 24px; "
            "border-radius: 6px; font-size: 14px;"
        )
        btn_cancel.clicked.connect(self.reject)
        btn_ok.clicked.connect(self._try_connect)
        self.pass_edit.returnPressed.connect(self._try_connect)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        root.addLayout(btn_row)

        self._apply_remembered()

    def _apply_remembered(self) -> None:
        data = remembered_credentials.load()
        if not data.get("remember"):
            return
        p = str(data.get("db_path") or "").strip()
        u = str(data.get("username") or "").strip()
        pw = remembered_credentials.decode_password(data)
        if p:
            self.path_edit.setText(p)
        if u:
            self.user_edit.setText(u)
        if pw:
            self.pass_edit.setText(pw)
        self.remember_cb.setChecked(True)

    def _try_connect(self) -> None:
        raw = self.path_edit.text().strip()
        if not raw:
            QMessageBox.warning(self, "提示", "请填写共享数据库路径。")
            return
        norm = os.path.normpath(os.path.expandvars(raw))
        parent = os.path.dirname(norm)
        if parent and not os.path.isdir(parent):
            QMessageBox.warning(self, "路径无效", f"找不到共享文件夹：\n{parent}")
            return

        uname = self.user_edit.text().strip()
        pwd = self.pass_edit.text()
        if not uname or not pwd:
            QMessageBox.warning(self, "提示", "请输入用户名和密码。")
            return

        try:
            db = Database(norm)
            auth = AuthManager(db)
        except Exception as e:
            QMessageBox.critical(self, "连接失败", str(e))
            return

        user = auth.authenticate(uname, pwd)
        if not user:
            db.close()
            QMessageBox.warning(self, "登录失败", "用户名或密码错误。")
            return

        payload = {"enabled": True, "db_path": norm, "client": True}
        try:
            sp = os.path.dirname(self._settings_path)
            if sp:
                os.makedirs(sp, exist_ok=True)
            with open(self._settings_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except OSError as e:
            db.close()
            QMessageBox.critical(self, "保存失败", f"无法写入 network_settings.json：\n{e}")
            return

        self._db = db
        self._user = user
        remembered_credentials.save(
            self.remember_cb.isChecked(),
            norm,
            uname,
            pwd,
        )
        self.accept()

    def result(self) -> Tuple[Database, Dict[str, Any]]:
        assert self._db is not None and self._user is not None
        return self._db, self._user


def run_frozen_bootstrap(
    settings_path: str,
    icon: Optional[QIcon] = None,
) -> Optional[Tuple[Database, Dict[str, Any]]]:
    dlg = FrozenBootstrapDialog(settings_path)
    if icon is not None and not icon.isNull():
        dlg.setWindowIcon(icon)
    if dlg.exec() != QDialog.Accepted:
        return None
    db, user = dlg.result()
    return db, user
