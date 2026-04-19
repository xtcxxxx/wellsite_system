import os
import sys

# Windows 任务栏/窗口图标：必须在导入 Qt、创建 QApplication 之前设置，否则易被归到「python.exe」或显示默认图标。
if sys.platform == "win32":
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "Wellsite.WarehouseDispatch.1.0"
        )
    except Exception:
        pass

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication, QDialog

from auth_service import AuthManager
from database import Database
from dispatch_manager import DispatchManager
from material_manager import MaterialManager
from ui.login_dialog import LoginDialog
from ui.main_window import MainWindow, bootstrap_frozen_resources, window_icon_qicon
from warehouse_manager import WarehouseManager


def app_data_dir() -> str:
    """开发时数据库在项目目录；打包后默认与 exe 同目录。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


if __name__ == "__main__":
    QCoreApplication.setApplicationName("仓库物资调度")
    QCoreApplication.setOrganizationName("Wellsite")

    app = QApplication(sys.argv)
    _icon = window_icon_qicon()
    if not _icon.isNull():
        app.setWindowIcon(_icon)
    bootstrap_frozen_resources()

    app.setStyleSheet("""...""")
    db_path = os.path.join(app_data_dir(), "wellsite.db")
    db = Database(db_path)

    exit_code = 0
    try:
        auth = AuthManager(db)
        warehouse_mgr = WarehouseManager(db)
        material_mgr = MaterialManager(db)
        dispatch_mgr = DispatchManager(db)

        login = LoginDialog(auth)
        if not _icon.isNull():
            login.setWindowIcon(_icon)
        if login.exec() != QDialog.Accepted:
            sys.exit(0)

        user = login.get_user()
        if not user:
            sys.exit(0)

        window = MainWindow(db, warehouse_mgr, material_mgr, dispatch_mgr, user)
        if not _icon.isNull():
            window.setWindowIcon(_icon)
        window.show()
        exit_code = app.exec()

    except Exception as e:
        print(f"程序启动失败: {e}")
        import traceback

        traceback.print_exc()
        exit_code = 1

    finally:
        db.close()

    sys.exit(exit_code)