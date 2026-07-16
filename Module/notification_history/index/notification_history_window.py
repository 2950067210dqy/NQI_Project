"""上位机预警通知历史界面。"""
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QSpinBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QGroupBox
)
from loguru import logger

from public.entity.BaseWindow import BaseWindow
from Service.connect_server_service.api.api_client import UpperAPIClient
from Service.connect_server_service.api.http_retry import format_request_error, get_request_max_attempts


class NotificationHistoryWindow(BaseWindow):
    """直接查看服务器 notifications 表中的 fault_alarm 历史通知。"""

    STATUS_OPTIONS = [("全部", None), ("未读", "unread"), ("已读", "read")]

    def __init__(self):
        super().__init__()
        self.client = self._create_client()
        self.notifications = []
        self._server_failure_dialog_shown = False
        self.setWindowTitle("预警通知历史")
        self.resize(1120, 720)
        self._init_ui()

        # 定时器先于首次请求创建，服务器宕机时可在最终失败后直接停止轮询。
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(lambda: self.refresh_notifications(show_error=False))
        self.refresh_timer.start(15000)
        self.refresh_notifications(show_error=False)

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

        filter_group = QGroupBox("通知过滤")
        filter_layout = QHBoxLayout(filter_group)

        self.device_input = QLineEdit()
        self.device_input.setPlaceholderText("设备编号，例如 E001/G001")

        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("消息关键词")

        self.status_combo = QComboBox()
        for text, value in self.STATUS_OPTIONS:
            self.status_combo.addItem(text, value)

        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(1, 1000)
        self.limit_spin.setValue(100)

        self.refresh_btn = QPushButton("刷新")
        self.mark_read_btn = QPushButton("标记已读")
        self.refresh_btn.clicked.connect(lambda: self.refresh_notifications(show_error=True))
        self.mark_read_btn.clicked.connect(self.mark_selected_read)

        filter_layout.addWidget(QLabel("设备"))
        filter_layout.addWidget(self.device_input)
        filter_layout.addWidget(QLabel("关键词"))
        filter_layout.addWidget(self.keyword_input)
        filter_layout.addWidget(QLabel("状态"))
        filter_layout.addWidget(self.status_combo)
        filter_layout.addWidget(QLabel("数量"))
        filter_layout.addWidget(self.limit_spin)
        filter_layout.addWidget(self.refresh_btn)
        filter_layout.addWidget(self.mark_read_btn)

        self.summary_label = QLabel("预警通知历史加载中")
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["通知ID", "设备", "类型", "状态", "消息", "创建时间", "已读时间"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSortingEnabled(True)

        root.addWidget(filter_group)
        root.addWidget(self.summary_label)
        root.addWidget(self.table)
        self.setCentralWidget(central)
        self.statusBar().showMessage("预警通知历史就绪")

    def refresh_notifications(self, show_error: bool = True):
        """从服务器 notifications 表加载预警通知历史。"""
        try:
            result = self.client.list_notifications(
                notification_type="fault_alarm",
                device_id=self.device_input.text().strip() or None,
                status=self.status_combo.currentData(),
                keyword=self.keyword_input.text().strip() or None,
                limit=self.limit_spin.value(),
            )
            self.notifications = result.get("notifications", [])
            self._server_failure_dialog_shown = False
            if show_error and not self.refresh_timer.isActive():
                self.refresh_timer.start(15000)
            self._fill_table(self.notifications)
            unread_count = sum(1 for item in self.notifications if item.get("status") == "unread")
            self.summary_label.setText(f"共 {result.get('total', len(self.notifications))} 条预警通知，当前显示 {len(self.notifications)} 条，未读 {unread_count} 条")
            self.statusBar().showMessage("预警通知历史已刷新")
        except Exception as exc:
            logger.exception(f"刷新预警通知历史失败: {exc}")
            self.refresh_timer.stop()
            self.summary_label.setText(f"服务器请求失败 {get_request_max_attempts()} 次，预警通知自动刷新已暂停，请点击刷新重试")
            self.statusBar().showMessage("服务器已断开，预警通知自动刷新已暂停")
            # 自动刷新只弹一次，避免服务器宕机期间反复打断用户操作。
            if show_error or not self._server_failure_dialog_shown:
                QMessageBox.warning(self, "刷新失败", format_request_error(str(exc)))
                self._server_failure_dialog_shown = True

    def mark_selected_read(self):
        """把选中的预警通知标记为已读。"""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择一条预警通知。")
            return
        notification_id_item = self.table.item(row, 0)
        if notification_id_item is None:
            return
        try:
            self.client.mark_notification_read(int(notification_id_item.text()))
            self.statusBar().showMessage("预警通知已标记为已读")
            self.refresh_notifications(show_error=False)
        except Exception as exc:
            logger.exception(f"标记预警通知已读失败: {exc}")
            QMessageBox.warning(self, "标记失败", format_request_error(str(exc)))

    def _fill_table(self, rows):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row.get("id"),
                row.get("device_id"),
                row.get("notification_type"),
                row.get("status"),
                row.get("message"),
                row.get("created_at") or "",
                row.get("read_at") or "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem("" if value is None else str(value))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row_index, col, item)
        self.table.setSortingEnabled(True)
        self.sort_table_by_latest_time(self.table, ("创建时间", "已读时间"))
