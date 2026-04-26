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
from runtime_flags import (
    local_wellsite_path,
    network_settings_file,
    read_network_db_path,
    resolved_shared_database_path,
)
from ui.login_dialog import LoginDialog
from ui.main_window import MainWindow, bootstrap_frozen_resources, window_icon_qicon
from warehouse_manager import WarehouseManager


def enforce_client_no_local_wellsite_file() -> None:
    """禁止在 exe 旁保留本机 wellsite.db。"""
    p = local_wellsite_path()
    if os.path.isfile(p):
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.critical(
            None,
            "客户端",
            "本程序仅允许使用共享数据库，不能在 exe 旁使用本机 wellsite.db。\n"
            f"请删除该文件后重试：\n{p}",
        )
        sys.exit(1)


def needs_frozen_bootstrap_wizard() -> bool:
    """打包 exe：共享库不可用时需要「首次连接共享库」向导。"""
    if not getattr(sys, "frozen", False):
        return False

    if os.environ.get("WELLSITE_DB_PATH") or os.environ.get("WELLSITE_DB"):
        rp = resolved_shared_database_path()
        return not (rp and os.path.isfile(rp))

    rp = resolved_shared_database_path()
    return not (rp and os.path.isfile(rp))


def effective_db_path_for_startup() -> tuple:
    """
    返回 (数据库路径 或 None, 是否需要在登录后提示配置网络)。
    仅允许已存在的共享 wellsite.db，不回落本机路径。
    """
    cfg_raw = (os.environ.get("WELLSITE_DB_PATH") or os.environ.get("WELLSITE_DB") or "").strip()
    if not cfg_raw:
        cfg_raw = read_network_db_path()
    if not cfg_raw:
        return None, False
    shared = os.path.normpath(os.path.expandvars(str(cfg_raw).strip()))
    if os.path.isfile(shared):
        return shared, False
    return None, False


def configured_db_path() -> str:
    return os.environ.get("WELLSITE_DB_PATH") or os.environ.get("WELLSITE_DB") or read_network_db_path()


if __name__ == "__main__":
    QCoreApplication.setApplicationName("仓库物资调度")
    QCoreApplication.setOrganizationName("Wellsite")

    app = QApplication(sys.argv)
    _icon = window_icon_qicon()
    if not _icon.isNull():
        app.setWindowIcon(_icon)

    enforce_client_no_local_wellsite_file()
    bootstrap_frozen_resources()

    app.setStyleSheet("""...""")

    db = None
    exit_code = 0
    try:
        post_login_network_hint = False
        user = None

        if needs_frozen_bootstrap_wizard():
            from ui.frozen_bootstrap_dialog import run_frozen_bootstrap

            boot = run_frozen_bootstrap(network_settings_file(), _icon)
            if not boot:
                sys.exit(0)
            db, user = boot
            post_login_network_hint = False
        else:
            db_path, post_login_network_hint = effective_db_path_for_startup()
            if db_path is None:
                from PySide6.QtWidgets import QMessageBox

                bad = configured_db_path()
                bad = (
                    os.path.normpath(os.path.expandvars(str(bad).strip()))
                    if bad
                    else ""
                )
                if not bad:
                    QMessageBox.critical(
                        None,
                        "客户端",
                        "本程序仅允许连接共享 wellsite.db。\n"
                        "请配置可访问的共享路径；首次运行请完成「连接共享数据库」向导。",
                    )
                else:
                    QMessageBox.critical(
                        None,
                        "无法连接数据库",
                        "已配置共享数据库，但当前无法打开该文件，程序无法启动，也不能登录。\n\n"
                        f"路径：\n{bad}\n\n"
                        "请检查：主机是否开机、是否在同一局域网、共享文件夹权限、路径是否正确。\n"
                        "故障排除后再启动。",
                    )
                sys.exit(1)
            db = Database(db_path)
            auth = AuthManager(db)
            login = LoginDialog(auth)
            if not _icon.isNull():
                login.setWindowIcon(_icon)
            if login.exec() != QDialog.Accepted:
                sys.exit(0)

            user = login.get_user()
            if not user:
                sys.exit(0)

        warehouse_mgr = WarehouseManager(db)
        material_mgr = MaterialManager(db)
        dispatch_mgr = DispatchManager(db)

        window = MainWindow(
            db,
            warehouse_mgr,
            material_mgr,
            dispatch_mgr,
            user,
            post_login_network_hint=post_login_network_hint,
        )
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
        if db is not None:
            db.close()

    sys.exit(exit_code)
