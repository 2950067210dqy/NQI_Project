"""上位机设备在线状态界面。"""
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
)
from loguru import logger

from public.entity.BaseWindow import BaseWindow
from Service.connect_server_service.api.api_client import UpperAPIClient
from Service.connect_server_service.api.http_retry import format_request_error, get_request_max_attempts


class DeviceStatusWindow(BaseWindow):
    """显示所有下位机设备的在线状态、地址和最近更新时间。"""

    def __init__(self):
        super().__init__()
        self.client = self._create_client()
        self.devices = []
        self._loading_devices = False
        self._server_failure_dialog_shown = False
        self.setWindowTitle("设备在线状态")
        self.resize(1080, 720)
        self._init_ui()

        # 先创建定时器，初次请求最终失败时可以立即停止后续自动刷新。
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(lambda: self.refresh_devices(show_loading=False))
        self.refresh_timer.start(5000)
        self.refresh_devices(show_loading=False)

    def _create_client(self):
        server_url = "http://localhost:8000"
        try:
            from public.config_class.global_setting import global_setting
            server_url = global_setting.get_setting("connect_server", {}).get("server", {}).get("url", server_url)
        except Exception as exc:
            logger.warning(f"读取服务器配置失败，使用默认地址: {exc}")
        return UpperAPIClient(server_url)

    def _init_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        top_bar = QHBoxLayout()
        self.summary_label = QLabel("设备状态加载中")
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(lambda: self.refresh_devices(show_loading=True))
        top_bar.addWidget(self.summary_label)
        top_bar.addStretch()
        top_bar.addWidget(self.refresh_btn)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["设备编号", "设备名称", "IP 地址", "所在城市", "在线状态", "创建时间", "最后心跳"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSortingEnabled(True)

        root.addLayout(top_bar)
        root.addWidget(self.table)
        self.setCentralWidget(central)
        self.statusBar().showMessage("设备在线状态就绪")

    def refresh_devices(self, show_loading: bool = True):
        """异步拉取设备列表并刷新在线状态表格。"""
        if self._loading_devices:
            return
        self._loading_devices = True

        def task():
            # 设备在线状态是高频刷新请求，使用短超时避免下位机离线或服务端慢响应时拖住页面。
            return self.client.list_devices(timeout=5)

        def on_success(result):
            self._loading_devices = False
            self._server_failure_dialog_shown = False
            self.devices = result.get("devices", [])
            self._fill_table(self.devices)
            online = sum(1 for item in self.devices if item.get("status") == "online")
            total = len(self.devices)
            self.summary_label.setText(f"共 {total} 台设备，在线 {online} 台，离线 {total - online} 台")
            if show_loading and getattr(self, "refresh_timer", None) is not None and not self.refresh_timer.isActive():
                self.refresh_timer.start(5000)
            self.statusBar().showMessage("设备状态已刷新")

        def on_error(message):
            self._loading_devices = False
            self.refresh_timer.stop()
            self.summary_label.setText(f"服务器请求失败 {get_request_max_attempts()} 次，设备状态自动刷新已暂停，请点击刷新重试")
            self.statusBar().showMessage("服务器已断开，设备状态自动刷新已暂停")
            # 自动刷新在一次宕机期间只提示一次；手动重试最终失败时仍给出明确反馈。
            if show_loading or not self._server_failure_dialog_shown:
                QMessageBox.warning(self, "刷新失败", format_request_error(message))
                self._server_failure_dialog_shown = True

        self.run_async_task(
            task,
            on_success=on_success,
            on_error=on_error,
            loading_text="正在读取设备在线状态...",
            show_loading=show_loading,
            widgets=[self.refresh_btn],
        )

    def _fill_table(self, rows):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row.get("device_id"),
                row.get("device_name"),
                row.get("device_ip"),
                # 服务器会通过认证、心跳和上传接口持续刷新这个城市字段。
                row.get("location") or "",
                row.get("status"),
                row.get("created_at") or "",
                row.get("updated_at") or "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem("" if value is None else str(value))
                if col == 4:
                    if str(value) == "online":
                        item.setForeground(Qt.GlobalColor.darkGreen)
                    else:
                        item.setForeground(Qt.GlobalColor.red)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row_index, col, item)
        self.table.setSortingEnabled(True)
        self.sort_table_by_latest_time(self.table, ("最后心跳", "创建时间"))
