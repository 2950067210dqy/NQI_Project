"""上位机报警预警中心界面。"""
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QSpinBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QGroupBox, QTabWidget
)
from loguru import logger

from public.entity.BaseWindow import BaseWindow
from Service.connect_server_service.api.api_client import UpperAPIClient


class FaultAlarmWindow(BaseWindow):
    """把报警预警与预警通知历史合并到同一页面，用标签页统一查看。"""

    STATUS_OPTIONS = [("全部", ""), ("未处理", "open"), ("已确认", "acknowledged"), ("已关闭", "closed")]
    NOTICE_STATUS_OPTIONS = [("全部", None), ("未读", "unread"), ("已读", "read")]

    def __init__(self):
        super().__init__()
        self.client = self._create_client()
        self.faults = []
        self.notifications = []
        self._fault_loading = False
        self._notification_loading = False
        self.setWindowTitle("报警预警")
        self.resize(1180, 760)
        self._init_ui()
        self.refresh_faults(show_loading=False)
        self.refresh_notifications(show_loading=False)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._auto_refresh_current_page)
        self.refresh_timer.start(15000)

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

        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(self._create_fault_tab(), "报警预警")
        self.tab_widget.addTab(self._create_notification_tab(), "预警通知历史")

        root.addWidget(self.tab_widget)
        self.setCentralWidget(central)
        self.statusBar().showMessage("报警预警中心就绪")

    def _create_fault_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        filter_group = QGroupBox("报警过滤")
        filter_layout = QHBoxLayout(filter_group)

        self.device_input = QLineEdit()
        self.device_input.setPlaceholderText("设备编号，例如 E001/G001")

        self.status_combo = QComboBox()
        for text, value in self.STATUS_OPTIONS:
            self.status_combo.addItem(text, value)

        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(1, 1000)
        self.limit_spin.setValue(100)

        self.refresh_btn = QPushButton("刷新")
        self.ack_btn = QPushButton("确认处理")
        self.close_btn = QPushButton("关闭报警")
        self.refresh_btn.clicked.connect(lambda: self.refresh_faults(show_loading=True))
        self.ack_btn.clicked.connect(lambda: self.update_selected_fault("acknowledged"))
        self.close_btn.clicked.connect(lambda: self.update_selected_fault("closed"))

        filter_layout.addWidget(QLabel("设备"))
        filter_layout.addWidget(self.device_input)
        filter_layout.addWidget(QLabel("状态"))
        filter_layout.addWidget(self.status_combo)
        filter_layout.addWidget(QLabel("数量"))
        filter_layout.addWidget(self.limit_spin)
        filter_layout.addWidget(self.refresh_btn)
        filter_layout.addWidget(self.ack_btn)
        filter_layout.addWidget(self.close_btn)

        self.summary_label = QLabel("报警列表加载中")
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(["报警ID", "设备", "类型", "文件ID", "故障类型", "级别", "来源", "状态", "消息"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSortingEnabled(True)

        layout.addWidget(filter_group)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.table)
        return tab

    def _create_notification_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        filter_group = QGroupBox("通知过滤")
        filter_layout = QHBoxLayout(filter_group)

        self.notice_device_input = QLineEdit()
        self.notice_device_input.setPlaceholderText("设备编号，例如 E001/G001")

        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("消息关键词")

        self.notice_status_combo = QComboBox()
        for text, value in self.NOTICE_STATUS_OPTIONS:
            self.notice_status_combo.addItem(text, value)

        self.notice_limit_spin = QSpinBox()
        self.notice_limit_spin.setRange(1, 1000)
        self.notice_limit_spin.setValue(100)

        self.notice_refresh_btn = QPushButton("刷新")
        self.mark_read_btn = QPushButton("标记已读")
        self.notice_refresh_btn.clicked.connect(lambda: self.refresh_notifications(show_loading=True))
        self.mark_read_btn.clicked.connect(self.mark_selected_read)

        filter_layout.addWidget(QLabel("设备"))
        filter_layout.addWidget(self.notice_device_input)
        filter_layout.addWidget(QLabel("关键词"))
        filter_layout.addWidget(self.keyword_input)
        filter_layout.addWidget(QLabel("状态"))
        filter_layout.addWidget(self.notice_status_combo)
        filter_layout.addWidget(QLabel("数量"))
        filter_layout.addWidget(self.notice_limit_spin)
        filter_layout.addWidget(self.notice_refresh_btn)
        filter_layout.addWidget(self.mark_read_btn)

        self.notice_summary_label = QLabel("预警通知历史加载中")
        self.notice_table = QTableWidget(0, 7)
        self.notice_table.setHorizontalHeaderLabels(["通知ID", "设备", "类型", "状态", "消息", "创建时间", "已读时间"])
        self.notice_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.notice_table.setAlternatingRowColors(True)
        self.notice_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.notice_table.setSortingEnabled(True)

        layout.addWidget(filter_group)
        layout.addWidget(self.notice_summary_label)
        layout.addWidget(self.notice_table)
        return tab

    def _auto_refresh_current_page(self):
        """定时刷新当前标签页，避免两边同时刷造成界面噪音。"""
        if self.tab_widget.currentIndex() == 0:
            self.refresh_faults(show_loading=False)
        else:
            self.refresh_notifications(show_loading=False)

    def refresh_faults(self, show_loading: bool = True):
        """异步读取报警记录。"""
        if self._fault_loading:
            return
        self._fault_loading = True

        device_id = self.device_input.text().strip() or None
        status = self.status_combo.currentData() or None
        limit = self.limit_spin.value()

        def task():
            return self.client.list_faults(device_id=device_id, status=status, limit=limit)

        def on_success(result):
            self._fault_loading = False
            self.faults = result.get("faults", [])
            self._fill_fault_table(self.faults)
            open_count = sum(1 for item in self.faults if item.get("status") == "open")
            self.summary_label.setText(
                f"共 {result.get('total', len(self.faults))} 条报警，当前显示 {len(self.faults)} 条，未处理 {open_count} 条"
            )
            self.statusBar().showMessage("报警列表已刷新")

        def on_error(message):
            self._fault_loading = False
            self.statusBar().showMessage("刷新报警失败")
            QMessageBox.critical(self, "刷新报警失败", message)

        self.run_async_task(
            task,
            on_success=on_success,
            on_error=on_error,
            loading_text="正在读取报警预警...",
            show_loading=show_loading,
            widgets=[self.refresh_btn, self.ack_btn, self.close_btn],
        )

    def update_selected_fault(self, status: str):
        """异步更新选中报警的处理状态。"""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择一条报警记录。")
            return
        fault_id_item = self.table.item(row, 0)
        if fault_id_item is None:
            return
        fault_id = int(fault_id_item.text())

        def task():
            return self.client.update_fault_status(fault_id, status=status)

        def on_success(_):
            self.statusBar().showMessage("报警状态已更新")
            self.refresh_faults(show_loading=False)

        self.run_async_task(
            task,
            on_success=on_success,
            on_error=lambda message: QMessageBox.critical(self, "更新失败", message),
            loading_text="正在更新报警状态...",
            widgets=[self.refresh_btn, self.ack_btn, self.close_btn],
        )

    def refresh_notifications(self, show_loading: bool = True):
        """异步读取预警通知历史。"""
        if self._notification_loading:
            return
        self._notification_loading = True

        device_id = self.notice_device_input.text().strip() or None
        keyword = self.keyword_input.text().strip() or None
        status = self.notice_status_combo.currentData()
        limit = self.notice_limit_spin.value()

        def task():
            return self.client.list_notifications(
                notification_type="fault_alarm",
                device_id=device_id,
                status=status,
                keyword=keyword,
                limit=limit,
            )

        def on_success(result):
            self._notification_loading = False
            self.notifications = result.get("notifications", [])
            self._fill_notification_table(self.notifications)
            unread_count = sum(1 for item in self.notifications if item.get("status") == "unread")
            self.notice_summary_label.setText(
                f"共 {result.get('total', len(self.notifications))} 条预警通知，当前显示 {len(self.notifications)} 条，未读 {unread_count} 条"
            )
            self.statusBar().showMessage("预警通知历史已刷新")

        def on_error(message):
            self._notification_loading = False
            self.statusBar().showMessage("刷新预警通知历史失败")
            QMessageBox.critical(self, "刷新失败", message)

        self.run_async_task(
            task,
            on_success=on_success,
            on_error=on_error,
            loading_text="正在读取预警通知历史...",
            show_loading=show_loading,
            widgets=[self.notice_refresh_btn, self.mark_read_btn],
        )

    def mark_selected_read(self):
        """异步把选中的预警通知标记为已读。"""
        row = self.notice_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择一条预警通知。")
            return
        notification_id_item = self.notice_table.item(row, 0)
        if notification_id_item is None:
            return
        notification_id = int(notification_id_item.text())

        def task():
            return self.client.mark_notification_read(notification_id)

        def on_success(_):
            self.statusBar().showMessage("预警通知已标记为已读")
            self.refresh_notifications(show_loading=False)

        self.run_async_task(
            task,
            on_success=on_success,
            on_error=lambda message: QMessageBox.critical(self, "标记失败", message),
            loading_text="正在标记预警通知...",
            widgets=[self.notice_refresh_btn, self.mark_read_btn],
        )

    def _fill_fault_table(self, rows):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row.get("id"),
                row.get("device_id"),
                "电量" if row.get("data_type") == "excel" else "几何量",
                row.get("file_id"),
                row.get("fault_type"),
                row.get("severity"),
                row.get("source"),
                row.get("status"),
                row.get("message"),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem("" if value is None else str(value))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row_index, col, item)
        self.table.setSortingEnabled(True)

    def _fill_notification_table(self, rows):
        self.notice_table.setSortingEnabled(False)
        self.notice_table.setRowCount(len(rows))
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
                self.notice_table.setItem(row_index, col, item)
        self.notice_table.setSortingEnabled(True)
