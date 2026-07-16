import configparser
import gc
import sys
from pathlib import Path

import requests
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QVBoxLayout,
)


AUTH_SECTION = "admin_auth"


def _runtime_root() -> Path:
    """源码环境返回项目根目录，打包环境返回 exe 所在目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _read_ini(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None)
    if path.is_file():
        parser.read(path, encoding="utf-8")
    return parser


def _auth_config_path() -> Path:
    return _runtime_root() / "config" / "admin_auth_config.ini"


def load_auth_preferences() -> tuple[bool, str]:
    """读取是否记住密码及已保存密码。"""
    parser = _read_ini(_auth_config_path())
    if not parser.has_section(AUTH_SECTION):
        return False, ""
    remember = parser.getboolean(AUTH_SECTION, "remember_password", fallback=False)
    password = parser.get(AUTH_SECTION, "saved_password", fallback="") if remember else ""
    return remember, password


def save_auth_preferences(remember: bool, password: str) -> None:
    """按用户选择写入全局认证 INI；取消记住时立即清空密码。"""
    path = _auth_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    parser = _read_ini(path)
    if not parser.has_section(AUTH_SECTION):
        parser.add_section(AUTH_SECTION)
    parser.set(AUTH_SECTION, "remember_password", "true" if remember else "false")
    parser.set(AUTH_SECTION, "saved_password", password if remember else "")
    with path.open("w", encoding="utf-8") as file:
        parser.write(file)


def load_server_url() -> str:
    parser = _read_ini(_runtime_root() / "config" / "connect_server_config.ini")
    url = parser.get("server", "url", fallback="").strip()
    if not url:
        raise ValueError("服务器地址未配置")
    return url.rstrip("/")


def verify_admin_password(password: str, timeout: float = 5.0) -> tuple[bool, str]:
    """调用服务器校验接口，不在客户端执行本地密码判断。"""
    try:
        response = requests.post(
            f"{load_server_url()}/api/admin/verify-password",
            json={"password": password},
            timeout=(3.0, timeout),
        )
        if response.status_code == 401:
            return False, "wrong_password"
        response.raise_for_status()
        if response.json().get("valid") is True:
            return True, ""
        return False, "服务器未确认管理员身份"
    except (requests.RequestException, ValueError) as exc:
        return False, f"无法连接服务器进行身份验证：{exc}"


class AdminPasswordVerifyThread(QThread):
    result_ready = pyqtSignal(bool, str)

    def __init__(self, password: str, parent=None):
        super().__init__(parent)
        self.password = password

    def run(self):
        self.result_ready.emit(*verify_admin_password(self.password))


class AdminPasswordDialog(QDialog):
    """上位机启动前的管理员密码验证窗口。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._accept_after_worker = False
        self.setWindowTitle("管理员身份验证")
        self.setModal(True)
        self.setMinimumWidth(460)
        self._build_ui()
        self._load_saved_password()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel("请输入管理员密码后进入上位机")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(title)

        form = QFormLayout()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("管理员密码")
        self.password_edit.returnPressed.connect(self._start_verification)
        form.addRow("管理员密码", self.password_edit)

        self.remember_checkbox = QCheckBox("记住密码")
        form.addRow("", self.remember_checkbox)
        layout.addLayout(form)

        self.hint_label = QLabel("如果密码错误，请联系管理员索要密码。")
        self.hint_label.setStyleSheet("color: #9A6700;")
        layout.addWidget(self.hint_label)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        layout.addWidget(self.progress)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.login_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.cancel_button = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        self.login_button.setText("登录")
        self.cancel_button.setText("退出")
        self.buttons.accepted.connect(self._start_verification)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _load_saved_password(self):
        remember, password = load_auth_preferences()
        self.remember_checkbox.setChecked(remember)
        self.password_edit.setText(password)
        self.password_edit.setFocus()
        if password:
            self.password_edit.selectAll()

    def _set_loading(self, loading: bool):
        self.password_edit.setEnabled(not loading)
        self.remember_checkbox.setEnabled(not loading)
        self.login_button.setEnabled(not loading)
        self.cancel_button.setEnabled(not loading)
        self.progress.setVisible(loading)

    def _start_verification(self):
        if self._worker is not None and self._worker.isRunning():
            return
        password = self.password_edit.text()
        if not password:
            self.status_label.setStyleSheet("color: #C62828;")
            self.status_label.setText("请输入管理员密码。")
            return

        self.status_label.setStyleSheet("color: #1F6FEB;")
        self.status_label.setText("正在连接服务器验证管理员密码...")
        self._set_loading(True)
        self._worker = AdminPasswordVerifyThread(password, self)
        self._worker.result_ready.connect(self._handle_verification_result)
        self._worker.finished.connect(self._handle_worker_finished)
        self._worker.start()

    def _handle_verification_result(self, valid: bool, message: str):
        if valid:
            save_auth_preferences(
                self.remember_checkbox.isChecked(),
                self.password_edit.text(),
            )
            self._accept_after_worker = True
            self.status_label.setStyleSheet("color: #2E7D32;")
            self.status_label.setText("管理员身份验证通过。")
            return

        self.status_label.setStyleSheet("color: #C62828;")
        if message == "wrong_password":
            # 数据库密码变更后清除旧记忆值，避免下次启动继续使用错误密码。
            save_auth_preferences(self.remember_checkbox.isChecked(), "")
            self.status_label.setText("密码错误，请联系管理员索要密码。")
            self.password_edit.setEnabled(True)
            self.password_edit.setFocus()
            self.password_edit.selectAll()
        else:
            self.status_label.setText(message)

    def _handle_worker_finished(self):
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()
        self._set_loading(False)
        if self._accept_after_worker:
            self._accept_after_worker = False
            self.accept()

    def reject(self):
        if self._worker is not None and self._worker.isRunning():
            return
        super().reject()


def request_admin_authentication() -> bool:
    """显示认证窗口；只有服务器校验成功才允许继续启动业务进程。"""
    app = QApplication.instance()
    owns_application = app is None
    if owns_application:
        app = QApplication(sys.argv)

    dialog = AdminPasswordDialog()
    accepted = dialog.exec() == QDialog.DialogCode.Accepted
    dialog.deleteLater()
    app.processEvents()
    if owns_application:
        app.quit()
        del app
        gc.collect()
    return accepted
