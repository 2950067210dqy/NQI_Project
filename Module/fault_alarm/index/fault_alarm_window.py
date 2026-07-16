"""上位机报警预警中心界面。"""
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QSpinBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QGroupBox, QTabWidget, QFileDialog
)
from loguru import logger

from public.entity.BaseWindow import BaseWindow
from public.util.alarm_message_formatter import (
    display_severity, display_source, display_status, format_alarm_message,
)
from Service.connect_server_service.api.api_client import UpperAPIClient


def format_server_request_error(message: str) -> str:
    """把网络库异常转换为用户可理解的中文提示，避免显示冗长英文堆栈。"""
    detail = str(message or "")
    lowered = detail.lower()
    if "502" in detail or "bad gateway" in lowered:
        return "服务器网关暂时无法连接后台服务（HTTP 502），请确认服务器程序正在运行后重试。"
    if "503" in detail or "service unavailable" in lowered:
        return "服务器当前不可用（HTTP 503），请稍后重试。"
    if "504" in detail or "gateway timeout" in lowered:
        return "服务器响应超时（HTTP 504），请稍后重试。"
    if "timed out" in lowered or "timeout" in lowered:
        return "连接服务器超时，请稍后重试。"
    if "connection" in lowered or "连接" in detail:
        return "无法连接服务器，请检查服务器状态和网络连接。"
    return "服务器数据读取失败，请稍后重试。"


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
        self._server_failure_dialog_shown = False
        self.setWindowTitle("报警预警")
        self.resize(1180, 760)
        self._init_ui()

        # 先创建定时器再发起首轮请求，确保快速失败时也能可靠暂停轮询。
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._auto_refresh_current_page)
        self.refresh_timer.start(15000)
        self.refresh_faults(show_loading=False)
        self.refresh_notifications(show_loading=False)

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
        self.table = QTableWidget(0, 11)
        self.table.setHorizontalHeaderLabels(
            ["报警ID", "时间", "设备", "类型", "文件ID", "故障类型", "级别", "来源", "状态", "消息", "操作"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(10, QHeaderView.ResizeMode.ResizeToContents)
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
        self.notice_table = QTableWidget(0, 8)
        self.notice_table.setHorizontalHeaderLabels(
            ["通知ID", "设备", "类型", "状态", "消息", "创建时间", "已读时间", "操作"]
        )
        self.notice_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.notice_table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
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
            self._server_failure_dialog_shown = False
            # 手动刷新成功代表服务已经恢复，重新启用页面自动刷新。
            if show_loading and hasattr(self, "refresh_timer") and not self.refresh_timer.isActive():
                self.refresh_timer.start(15000)
            self.faults = result.get("faults", [])
            self._fill_fault_table(self.faults)
            open_count = sum(1 for item in self.faults if item.get("status") == "open")
            self.summary_label.setText(
                f"共 {result.get('total', len(self.faults))} 条报警，当前显示 {len(self.faults)} 条，未处理 {open_count} 条"
            )
            self.statusBar().showMessage("报警列表已刷新")

        def on_error(message):
            self._fault_loading = False
            friendly_message = format_server_request_error(message)
            # 服务不可用时暂停轮询，避免持续堆积失败请求；手动刷新成功后会恢复。
            if hasattr(self, "refresh_timer"):
                self.refresh_timer.stop()
            self.summary_label.setText(f"报警数据暂未加载：{friendly_message}")
            self.statusBar().showMessage("服务器暂时不可用，报警数据未刷新")
            logger.warning(f"刷新报警失败: {message}")
            # 两个标签页共用失败标记，服务器宕机时只显示一次最终失败提示。
            if show_loading or not self._server_failure_dialog_shown:
                QMessageBox.warning(self, "报警数据加载失败", friendly_message)
                self._server_failure_dialog_shown = True

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
            self._server_failure_dialog_shown = False
            # 手动刷新成功代表服务已经恢复，重新启用页面自动刷新。
            if show_loading and hasattr(self, "refresh_timer") and not self.refresh_timer.isActive():
                self.refresh_timer.start(15000)
            self.notifications = result.get("notifications", [])
            self._fill_notification_table(self.notifications)
            unread_count = sum(1 for item in self.notifications if item.get("status") == "unread")
            self.notice_summary_label.setText(
                f"共 {result.get('total', len(self.notifications))} 条预警通知，当前显示 {len(self.notifications)} 条，未读 {unread_count} 条"
            )
            self.statusBar().showMessage("预警通知历史已刷新")

        def on_error(message):
            self._notification_loading = False
            friendly_message = format_server_request_error(message)
            # 与报警列表共用轮询定时器，失败后等待用户手动重试，防止离线请求风暴。
            if hasattr(self, "refresh_timer"):
                self.refresh_timer.stop()
            self.notice_summary_label.setText(f"预警通知暂未加载：{friendly_message}")
            self.statusBar().showMessage("服务器暂时不可用，预警通知未刷新")
            logger.warning(f"刷新预警通知历史失败: {message}")
            if show_loading or not self._server_failure_dialog_shown:
                QMessageBox.warning(self, "预警通知加载失败", friendly_message)
                self._server_failure_dialog_shown = True

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

    def _row_to_viewer_record(self, row: dict) -> dict:
        """把报警或通知记录转换为数据查看器能够直接定位的结构。"""
        file_id = row.get("file_id")
        return {
            "id": file_id,
            "file_id": file_id,
            "device_id": row.get("device_id") or "",
            "file_name": row.get("file_name") or "",
            "file_path": row.get("file_path") or row.get("download_url") or "",
            "upload_time": row.get("created_at") or "",
            "processing_status": "done",
            "alarm_info": {"message": row.get("message") or ""},
        }

    def _find_loaded_module_window(self, module_name: str):
        """从主窗口已加载模块中取得数据查看器窗口。"""
        main_gui = getattr(self, "main_gui", None)
        for module in getattr(main_gui, "modules", []) or []:
            if getattr(module, "name", None) != module_name:
                continue
            interface_widget = getattr(module, "interface_widget", None)
            return getattr(interface_widget, "frame_obj", None)
        return None

    def view_data_row(self, row: dict):
        """打开电量或几何量查看页面，并定位到当前预警关联的文件。"""
        data_type = row.get("data_type")
        file_id = row.get("file_id")
        if data_type not in {"excel", "image"} or not file_id:
            QMessageBox.information(self, "无法查看", "该预警没有关联可查看的服务器数据文件。")
            return

        module_name = "ExcelDataViewerModule" if data_type == "excel" else "ImageDataViewerModule"
        main_gui = getattr(self, "main_gui", None)
        if main_gui is None or not hasattr(main_gui, "open_module_by_name"):
            QMessageBox.warning(self, "查看失败", "当前无法访问主窗口，不能打开数据查看页面。")
            return
        if not main_gui.open_module_by_name(module_name):
            QMessageBox.warning(self, "查看失败", "未找到对应的数据查看页面。")
            return

        record = self._row_to_viewer_record(row)

        def load_record_in_viewer():
            viewer = self._find_loaded_module_window(module_name)
            if viewer is None:
                QMessageBox.information(self, "提示", "已打开对应查看页面，请在页面内刷新后查看该数据。")
                return
            if data_type == "excel" and hasattr(viewer, "view_cache_record"):
                viewer.view_cache_record(record)
            elif data_type == "image" and hasattr(viewer, "view_image_cache_record"):
                viewer.view_image_cache_record(record)
            else:
                QMessageBox.information(self, "提示", "已打开对应数据查看页面。")

        QTimer.singleShot(250, load_record_in_viewer)
        self.statusBar().showMessage(f"正在打开预警关联文件：{row.get('file_name') or file_id}")

    def download_data_row(self, row: dict):
        """由用户选择目录后，在后台下载当前预警关联的原始文件。"""
        data_type = row.get("data_type")
        file_id = row.get("file_id")
        if data_type not in {"excel", "image"} or not file_id:
            QMessageBox.information(self, "无法下载", "该预警没有关联可下载的服务器数据文件。")
            return

        target_dir = QFileDialog.getExistingDirectory(
            self,
            "选择下载目录",
            str(Path.home() / "Downloads"),
        )
        if not target_dir:
            return
        default_name = f"excel_{file_id}.xlsx" if data_type == "excel" else f"image_{file_id}.png"
        # 只采用文件名部分，避免服务端路径意外改变用户选择的下载目录。
        file_name = Path(str(row.get("file_name") or default_name)).name
        save_path = Path(target_dir) / file_name

        def task():
            self.client.download_file(str(data_type), int(file_id), save_path)
            return save_path

        def on_success(downloaded_path: Path):
            self.statusBar().showMessage(f"下载完成：{downloaded_path}")
            QMessageBox.information(self, "下载完成", f"文件已下载到：\n{downloaded_path}")

        self.run_async_task(
            task,
            on_success=on_success,
            on_error=lambda message: QMessageBox.warning(
                self, "下载失败", format_server_request_error(message)
            ),
            loading_text=f"正在下载 {file_name}...",
            widgets=[self.tab_widget],
        )

    def _create_data_action_widget(self, row: dict) -> QWidget:
        """为报警和通知表格创建统一的查看、下载按钮。"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        view_btn = QPushButton("查看")
        download_btn = QPushButton("下载")
        has_file = row.get("data_type") in {"excel", "image"} and bool(row.get("file_id"))
        for button in (view_btn, download_btn):
            button.setMinimumWidth(52)
            button.setStyleSheet("font-size: 9px; padding: 2px 8px;")
            button.setEnabled(has_file)
            if not has_file:
                button.setToolTip("该通知未关联服务器数据文件")
        view_btn.clicked.connect(lambda checked=False, item=dict(row): self.view_data_row(item))
        download_btn.clicked.connect(lambda checked=False, item=dict(row): self.download_data_row(item))
        layout.addWidget(view_btn)
        layout.addWidget(download_btn)
        return widget

    def _fill_fault_table(self, rows):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row.get("id"),
                # 服务端报警记录按 created_at 返回，这里直接展示给上位机操作人员排查时间线。
                self._format_time(row.get("created_at")),
                row.get("device_id"),
                "电量" if row.get("data_type") == "excel" else "几何量",
                row.get("file_id"),
                row.get("fault_type"),
                display_severity(row.get("severity")),
                display_source(row.get("source")),
                display_status(row.get("status")),
                format_alarm_message(row.get("message")),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem("" if value is None else str(value))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row_index, col, item)
            self.table.setCellWidget(row_index, 10, self._create_data_action_widget(row))
        self.table.setSortingEnabled(True)
        self.sort_table_by_latest_time(self.table, ("时间",))

    def _fill_notification_table(self, rows):
        self.notice_table.setSortingEnabled(False)
        self.notice_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row.get("id"),
                row.get("device_id"),
                row.get("notification_type"),
                display_status(row.get("status")),
                format_alarm_message(row.get("message")),
                self._format_time(row.get("created_at")),
                self._format_time(row.get("read_at")),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem("" if value is None else str(value))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.notice_table.setItem(row_index, col, item)
            self.notice_table.setCellWidget(row_index, 7, self._create_data_action_widget(row))
        self.notice_table.setSortingEnabled(True)
        self.sort_table_by_latest_time(self.notice_table, ("创建时间", "已读时间"))

    def _format_time(self, value):
        """把服务端 ISO 时间转成表格中更容易阅读的时间文本。"""
        if not value:
            return ""
        text = str(value).replace("T", " ")
        if "." in text:
            text = text.split(".", 1)[0]
        return text
