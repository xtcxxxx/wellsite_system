"""登录窗口：校验用户名密码后返回当前用户信息。"""
from typing import Any, Dict, Optional

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFormLayout,
    QMessageBox,
)
from PySide6.QtCore import Qt

from auth_service import AuthManager


class LoginDialog(QDialog):
    def __init__(self, auth_mgr: AuthManager, parent=None):
        super().__init__(parent)
        self.auth_mgr = auth_mgr
        self._user: Optional[Dict[str, Any]] = None

        self.setWindowTitle("登录")
        self.setModal(True)
        self.resize(400, 200)
        self.setStyleSheet(
            """
            QDialog {
                background-color: #ffffff;
            }
            QLabel {
                color: #303133;
            }
            QLineEdit {
                background-color: #ffffff;
                border: 1px solid #dcdfe6;
                border-radius: 4px;
                padding: 6px 10px;
                color: #303133;
                selection-background-color: #409eff;
                selection-color: #ffffff;
            }
            QLineEdit:focus {
                border-color: #409eff;
            }
            QPushButton {
                background-color: #ffffff;
                color: #606266;
                border: 1px solid #dcdfe6;
                border-radius: 6px;
            }
            QPushButton:hover {
                color: #409eff;
                border-color: #c6e2ff;
                background-color: #ecf5ff;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("仓库物资调度管理系统")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #303133;")
        layout.addWidget(title)

        form = QFormLayout()
        self.user_edit = QLineEdit()
        self.user_edit.setPlaceholderText("用户名")
        self.pass_edit = QLineEdit()
        self.pass_edit.setPlaceholderText("密码")
        self.pass_edit.setEchoMode(QLineEdit.Password)
        form.addRow("用户名：", self.user_edit)
        form.addRow("密　码：", self.pass_edit)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_ok = QPushButton("登录")
        btn_ok.setDefault(True)
        btn_ok.setStyleSheet(
            "background: #409eff; color: white; padding: 8px 28px; "
            "border-radius: 6px; font-size: 14px;"
        )
        btn_cancel = QPushButton("退出")
        btn_cancel.setStyleSheet("padding: 8px 20px; border-radius: 6px;")
        btn_ok.clicked.connect(self._try_login)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

        self.pass_edit.returnPressed.connect(self._try_login)

    def get_user(self) -> Optional[Dict[str, Any]]:
        return self._user

    def _try_login(self) -> None:
        name = self.user_edit.text().strip()
        pwd = self.pass_edit.text()
        if not name or not pwd:
            QMessageBox.warning(self, "提示", "请输入用户名和密码")
            return
        user = self.auth_mgr.authenticate(name, pwd)
        if not user:
            QMessageBox.warning(self, "登录失败", "用户名或密码错误")
            self.pass_edit.clear()
            self.pass_edit.setFocus()
            return
        self._user = user
        self.accept()
