"""上位机设备注册审批界面。"""
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QGroupBox
)
from loguru import logger

from Service.connect_server_service.api.api_client import UpperAPIClient
from Service.connect_server_service.api.http_retry import format_request_error, get_request_max_attempts
from public.entity.BaseWindow import BaseWindow


class RegistrationApprovalWindow(BaseWindow):
    """展示下位机注册申请，并支持上位机审批和驳回。"""

    STATUS_OPTIONS = [("全部", ""), ("待审批", "pending"), ("已通过", "approved"), ("已驳回", "rejected")]

    def __init__(self):
        super().__init__()
        self.client = self._create_client()
        self.requests_data = []
        self._loading_requests = False
        # 审批请求执行期间暂停自动刷新，避免批准/驳回后刷新线程与审批线程同时更新界面。
        self._reviewing_request = False
        self._server_failure_dialog_shown = False
        self.setWindowTitle("设备注册审批")
        self.resize(1180, 720)
        self._init_ui()

        # 先建立定时器，配置次数全部失败时才能可靠停止后续自动请求。
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(lambda: self.refresh_requests(show_loading=False))
        self.refresh_timer.start(10000)
        self.refresh_requests(show_loading=False)

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

        filter_group = QGroupBox("审批过滤")
        filter_layout = QHBoxLayout(filter_group)

        self.status_combo = QComboBox()
        for text, value in self.STATUS_OPTIONS:
            self.status_combo.addItem(text, value)

        self.device_input = QLineEdit()
        self.device_input.setPlaceholderText("设备编号，例如 E001/G001")

        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("设备名称 / IP / 硬件密钥 / 审批意见")

        self.review_input = QLineEdit()
        self.review_input.setPlaceholderText("审批意见，留空则使用默认说明")

        self.refresh_btn = QPushButton("刷新")
        self.approve_btn = QPushButton("批准")
        self.reject_btn = QPushButton("驳回")
        self.refresh_btn.clicked.connect(lambda: self.refresh_requests(show_loading=True))
        self.approve_btn.clicked.connect(self.approve_selected_request)
        self.reject_btn.clicked.connect(self.reject_selected_request)

        filter_layout.addWidget(QLabel("状态"))
        filter_layout.addWidget(self.status_combo)
        filter_layout.addWidget(QLabel("设备"))
        filter_layout.addWidget(self.device_input)
        filter_layout.addWidget(QLabel("关键词"))
        filter_layout.addWidget(self.keyword_input)
        filter_layout.addWidget(QLabel("审批意见"))
        filter_layout.addWidget(self.review_input)
        filter_layout.addWidget(self.refresh_btn)
        filter_layout.addWidget(self.approve_btn)
        filter_layout.addWidget(self.reject_btn)

        self.summary_label = QLabel("注册审批数据加载中")
        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels([
            "申请ID", "设备编号", "设备名称", "设备IP", "所在城市", "硬件密钥",
            "状态", "审批意见", "申请时间", "审批时间"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSortingEnabled(True)

        root.addWidget(filter_group)
        root.addWidget(self.summary_label)
        root.addWidget(self.table)
        self.setCentralWidget(central)
        self.statusBar().showMessage("设备注册审批就绪")

    def refresh_requests(self, show_loading: bool = True):
        """异步刷新注册申请列表。"""
        if self._loading_requests or self._reviewing_request:
            return
        self._loading_requests = True

        status = self.status_combo.currentData() or None
        device_id = self.device_input.text().strip() or None
        keyword = self.keyword_input.text().strip() or None

        def task():
            return self.client.list_registration_requests(status=status, device_id=device_id, keyword=keyword)

        def on_success(result):
            self._loading_requests = False
            self._server_failure_dialog_shown = False
            if show_loading and not self.refresh_timer.isActive():
                self.refresh_timer.start(10000)
            self.requests_data = result.get("requests", [])
            self._fill_table(self.requests_data)
            pending_count = sum(1 for item in self.requests_data if item.get("status") == "pending")
            self.summary_label.setText(
                f"共 {result.get('count', len(self.requests_data))} 条注册申请，当前待审批 {pending_count} 条"
            )
            self.statusBar().showMessage("注册申请列表已刷新")

        def on_error(message):
            self._loading_requests = False
            self.refresh_timer.stop()
            self.summary_label.setText(f"服务器请求失败 {get_request_max_attempts()} 次，自动刷新已暂停，请点击刷新重试")
            self.statusBar().showMessage("服务器已断开，注册审批自动刷新已暂停")
            # 自动请求每次宕机只弹一次；用户手动刷新失败时允许再次提示。
            if show_loading or not self._server_failure_dialog_shown:
                QMessageBox.warning(self, "刷新失败", format_request_error(message))
                self._server_failure_dialog_shown = True

        self.run_async_task(
            task,
            on_success=on_success,
            on_error=on_error,
            loading_text="正在读取注册审批数据...",
            show_loading=show_loading,
            widgets=[self.refresh_btn, self.approve_btn, self.reject_btn],
        )

    def _get_selected_request(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择一条注册申请。")
            return None
        request_id_item = self.table.item(row, 0)
        status_item = self.table.item(row, 6)
        if request_id_item is None or status_item is None:
            return None
        return int(request_id_item.text()), status_item.text()

    def _set_review_controls_enabled(self, enabled: bool):
        """统一控制审批相关按钮，防止重复点击导致后台任务和界面刷新互相抢状态。"""
        for widget in (self.refresh_btn, self.approve_btn, self.reject_btn):
            if widget is not None:
                widget.setEnabled(enabled)

    def _run_review_request(self, action: str):
        """执行批准/驳回审批请求，并在结束后安全刷新列表。"""
        if self._reviewing_request:
            self.statusBar().showMessage("正在处理上一条审批请求，请稍候")
            return
        selected = self._get_selected_request()
        if not selected:
            return
        request_id, status = selected
        if status != "pending":
            QMessageBox.information(self, "提示", "只有待审批的申请可以审批。")
            return

        is_approve = action == "approve"
        review_message = self.review_input.text().strip() or ("approved" if is_approve else "rejected")
        title = "批准" if is_approve else "驳回"
        self._reviewing_request = True
        self._set_review_controls_enabled(False)
        if self.refresh_timer.isActive():
            self.refresh_timer.stop()

        def task():
            if is_approve:
                return self.client.approve_registration_request(request_id, review_message=review_message)
            return self.client.reject_registration_request(request_id, review_message=review_message)

        def finish_review(restart_timer: bool = True):
            # 所有 UI 恢复都放在主线程回调里执行，避免审批后自动刷新与 loading 清理交叉。
            self._reviewing_request = False
            self._set_review_controls_enabled(True)
            if restart_timer and not self.refresh_timer.isActive():
                self.refresh_timer.start(10000)

        def on_success(_):
            finish_review()
            self.statusBar().showMessage(f"注册申请已{title}")
            QTimer.singleShot(0, lambda: self.refresh_requests(show_loading=False))

        def on_error(message):
            finish_review(restart_timer=False)
            self.refresh_timer.stop()
            self.statusBar().showMessage(f"注册申请{title}失败，自动刷新已暂停")
            QMessageBox.warning(self, f"{title}失败", format_request_error(message))

        self.run_async_task(
            task,
            on_success=on_success,
            on_error=on_error,
            loading_text=f"正在{title}注册申请...",
            widgets=[self.refresh_btn, self.approve_btn, self.reject_btn],
        )

    def approve_selected_request(self):
        """异步批准选中的注册申请。"""
        self._run_review_request("approve")

    def reject_selected_request(self):
        """异步驳回选中的注册申请。"""
        self._run_review_request("reject")

    def _fill_table(self, rows):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row.get("id"),
                row.get("device_id"),
                row.get("device_name"),
                row.get("device_ip"),
                # 下位机注册时带上城市，审批人员可以在这里直接确认来源地。
                row.get("location") or "",
                row.get("hardware_key"),
                row.get("status"),
                row.get("review_message") or "",
                row.get("requested_at") or "",
                row.get("reviewed_at") or "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem("" if value is None else str(value))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row_index, col, item)
        self.table.setSortingEnabled(True)
        self.sort_table_by_latest_time(self.table, ("申请时间", "审批时间"))
