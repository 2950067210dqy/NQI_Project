"""报警延迟可视化页面。"""
import json
import time
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QGridLayout, QGroupBox, QHeaderView, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from public.entity.BaseWindow import BaseWindow
from Service.connect_server_service.api.api_client import UpperAPIClient

EXCEL_SUFFIXES = {".xlsx", ".xls"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp"}


def _server_url():
    """读取当前服务器地址。"""
    url = "http://localhost:8000"
    try:
        from public.config_class.global_setting import global_setting
        url = global_setting.get_setting("connect_server", {}).get("server", {}).get("url", url)
    except Exception:
        pass
    return str(url or "http://localhost:8000").strip().rstrip("/")


def _collect_files(folder, suffixes):
    """递归读取目录中的支持文件。"""
    if not folder:
        return []
    root = Path(folder)
    if not root.is_dir():
        raise ValueError(f"文件夹不存在: {folder}")
    return sorted(
        (p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in suffixes),
        key=lambda p: str(p).lower(),
    )



class AlarmLatencyWorker(QThread):
    """顺序上传文件并读取服务端测量结果，避免并发队列干扰单文件延迟。"""

    progress_changed = pyqtSignal(dict)
    step_finished = pyqtSignal(dict)
    log_message = pyqtSignal(str)
    finished_with_summary = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, base_url, excel_folder, image_folder,
                 threshold_ms, timeout_seconds):
        super().__init__()
        self.base_url = base_url
        self.excel_folder = excel_folder
        self.image_folder = image_folder
        self.threshold_ms = float(threshold_ms)
        self.timeout_seconds = timeout_seconds
        self._stop_requested = False

    def request_stop(self):
        self._stop_requested = True

    @staticmethod
    def _summary(records, current, planned, started):
        values = [r["server_latency_ms"] for r in records if r["server_latency_ms"] is not None]
        target_count = sum(1 for r in records if r["target_met"])
        failures = sum(1 for r in records if r["status"] == "失败")
        return {
            "current": current, "planned": planned, "completed": len(records),
            "measured": len(values), "target_count": target_count,
            "alarm_count": sum(1 for r in records if r["alarm_triggered"]),
            "failures": failures,
            "average_ms": sum(values) / len(values) if values else 0.0,
            "max_ms": max(values) if values else 0.0,
            "compliance_rate": target_count / len(values) if values else 0.0,
            "passed": bool(values) and target_count == len(values) and failures == 0,
            "elapsed_seconds": time.perf_counter() - started,
        }

    def run(self):
        try:
            files = [("excel", p) for p in _collect_files(self.excel_folder, EXCEL_SUFFIXES)]
            files += [("image", p) for p in _collect_files(self.image_folder, IMAGE_SUFFIXES)]
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        if not files:
            self.failed.emit("所选文件夹中没有可测试的 Excel 或图片文件。")
            return

        client = UpperAPIClient(self.base_url, timeout=max(10, self.timeout_seconds))
        records = []
        started = time.perf_counter()
        self.log_message.emit(
            f"开始测试 {len(files)} 个文件，达标条件：服务器报警判定延迟 < {self.threshold_ms:.0f}ms。"
        )
        for index, (data_type, file_path) in enumerate(files, 1):
            if self._stop_requested:
                break
            type_text = "电量数据" if data_type == "excel" else "几何量数据"
            local_started = time.perf_counter()
            try:
                upload_started = time.perf_counter()
                result = client.upload_alarm_latency_file(file_path)
                upload_ms = (time.perf_counter() - upload_started) * 1000
                test_id = str(result.get("test_id") or "")
                self.log_message.emit(
                    f"[{index}/{len(files)}] 临时文件已处理并删除，测试编号={test_id}。"
                )
                latency = float(result.get("alarm_latency_ms") or 0.0)
                alarm_info = result.get("alarm_info") or {}
                alarm_triggered = bool(result.get("alarm_triggered"))
                record = {
                    "index": index, "data_type": data_type, "data_type_text": type_text,
                    "file_path": str(file_path), "file_name": file_path.name,
                    "test_id": test_id, "upload_ms": round(upload_ms, 3),
                    "server_latency_ms": round(latency, 3),
                    "total_ms": round((time.perf_counter() - local_started) * 1000, 3),
                    "alarm_triggered": alarm_triggered,
                    "alarm_message": alarm_info.get("message") or (
                        "已触发预警" if alarm_triggered else "规则判断完成，未触发预警"
                    ),
                    "processing_status": result.get("processing_status"),
                    "processing_error": result.get("processing_error"),
                    "target_ms": self.threshold_ms,
                    "target_met": latency < self.threshold_ms,
                    "status": "达标" if latency < self.threshold_ms else "超标",
                    "upload_result": result, "latency_result": result,
                }
            except Exception as exc:
                record = {
                    "index": index, "data_type": data_type, "data_type_text": type_text,
                    "file_path": str(file_path), "file_name": file_path.name,
                    "test_id": None, "upload_ms": None, "server_latency_ms": None,
                    "total_ms": round((time.perf_counter() - local_started) * 1000, 3),
                    "alarm_triggered": False, "alarm_message": "",
                    "processing_status": "error", "processing_error": str(exc),
                    "target_ms": self.threshold_ms, "target_met": False, "status": "失败",
                }
            records.append(record)
            self.step_finished.emit(record)
            latency_text = (
                f"{record['server_latency_ms']:.3f}ms"
                if record["server_latency_ms"] is not None else record["processing_error"]
            )
            self.log_message.emit(f"[{index}/{len(files)}] {record['status']}：{latency_text}")
            self.progress_changed.emit(self._summary(records, index, len(files), started))

        summary = self._summary(records, len(records), len(files), started)
        summary["stopped"] = self._stop_requested
        self.finished_with_summary.emit(summary)

class AlarmLatencyVisualizationWindow(BaseWindow):
    """选择目录并实时展示报警延迟、进度和测试明细。"""

    def __init__(self):
        super().__init__()
        self.worker = None
        self.records = []
        self.setWindowTitle("报警延迟可视化")
        self.resize(1380, 860)
        self._init_ui()

    def _init_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        group = QGroupBox("测试配置")
        grid = QGridLayout(group)
        self.server_label = QLabel(_server_url())
        self.test_device_label = QLabel("upper_client")
        self.excel_folder_edit = self._folder_edit("选择包含电量 Excel 的文件夹")
        self.image_folder_edit = self._folder_edit("选择包含几何量图片的文件夹")
        self.excel_browse_btn = QPushButton("选择电量文件夹")
        self.image_browse_btn = QPushButton("选择图片文件夹")
        self.excel_browse_btn.clicked.connect(
            lambda: self._select_folder(self.excel_folder_edit, "选择电量数据文件夹")
        )
        self.image_browse_btn.clicked.connect(
            lambda: self._select_folder(self.image_folder_edit, "选择几何量图片文件夹")
        )
        self.threshold_spin = QSpinBox()
        self.threshold_spin.setRange(1, 1000)
        self.threshold_spin.setValue(1000)
        self.threshold_spin.setSuffix(" ms")
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 300)
        self.timeout_spin.setValue(60)
        self.timeout_spin.setSuffix(" s")
        self.start_btn = QPushButton("开始测试")
        self.stop_btn = QPushButton("停止")
        self.clear_btn = QPushButton("清空结果")
        self.stop_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.start_test)
        self.stop_btn.clicked.connect(self.stop_test)
        self.clear_btn.clicked.connect(self.clear_results)

        grid.addWidget(QLabel("服务器地址"), 0, 0)
        grid.addWidget(self.server_label, 0, 1, 1, 4)
        grid.addWidget(QLabel("测试设备码"), 0, 5)
        grid.addWidget(self.test_device_label, 0, 6)
        grid.addWidget(QLabel("延迟阈值"), 0, 7)
        grid.addWidget(self.threshold_spin, 0, 8)
        grid.addWidget(QLabel("电量文件夹"), 1, 0)
        grid.addWidget(self.excel_folder_edit, 1, 1, 1, 6)
        grid.addWidget(self.excel_browse_btn, 1, 7, 1, 2)
        grid.addWidget(QLabel("图片文件夹"), 2, 0)
        grid.addWidget(self.image_folder_edit, 2, 1, 1, 6)
        grid.addWidget(self.image_browse_btn, 2, 7, 1, 2)
        grid.addWidget(QLabel("单文件超时"), 3, 0)
        grid.addWidget(self.timeout_spin, 3, 1)
        grid.addWidget(self.start_btn, 3, 6)
        grid.addWidget(self.stop_btn, 3, 7)
        grid.addWidget(self.clear_btn, 3, 8)

        self.tip_label = QLabel(
            "提示：报警延迟测试文件、预警通知和消息均不进入数据库或服务器消息队列；"
            "测试预警仅在当前上位机实时显示，每个文件完成后服务器立即删除临时文件。"
        )
        self.tip_label.setWordWrap(True)
        self.tip_label.setStyleSheet("color: #9a6700; font-weight: 600;")
        self.progress_bar = QProgressBar()
        self.summary_label = QLabel(
            "等待开始。达标条件：服务器临时文件解析与报警规则判定延迟严格小于 1000ms。"
        )
        metrics = QHBoxLayout()
        self.metric_labels = {
            "measured": QLabel("已测量: 0"),
            "alarm": QLabel("触发预警: 0"),
            "average": QLabel("平均: 0.000ms"),
            "max": QLabel("最大: 0.000ms"),
            "rate": QLabel("达标率: 0.00%"),
        }
        for label in self.metric_labels.values():
            metrics.addWidget(label)
        metrics.addStretch(1)

        headers = [
            "序号", "执行时间", "类型", "文件名", "测试编号", "请求总耗时(ms)",
            "服务器报警延迟(ms)", "端到端耗时(ms)", "是否预警", "处理状态", "结果",
        ]
        self.table = QTableWidget(0, len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.show_selected_detail)

        details = QHBoxLayout()
        self.detail_text = QPlainTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setPlaceholderText("选择记录查看上传响应、报警信息和判定过程。")
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("测试过程日志")
        details.addWidget(self.detail_text, 1)
        details.addWidget(self.log_text, 1)

        root.addWidget(group)
        root.addWidget(self.tip_label)
        root.addWidget(self.progress_bar)
        root.addWidget(self.summary_label)
        root.addLayout(metrics)
        root.addWidget(self.table, 3)
        root.addLayout(details, 2)
        self.setCentralWidget(central)
        self.statusBar().showMessage("报警延迟可视化就绪")

    @staticmethod
    def _folder_edit(placeholder):
        edit = QLineEdit()
        edit.setReadOnly(True)
        edit.setPlaceholderText(placeholder)
        return edit

    def _select_folder(self, target, title):
        folder = QFileDialog.getExistingDirectory(self, title, target.text())
        if folder:
            target.setText(folder)

    def start_test(self):
        if self.worker is not None and self.worker.isRunning():
            return
        if not self.excel_folder_edit.text() and not self.image_folder_edit.text():
            QMessageBox.warning(self, "配置不完整", "请至少选择一个电量或图片文件夹。")
            return

        self.clear_results()
        self.server_label.setText(_server_url())
        self.worker = AlarmLatencyWorker(
            self.server_label.text(),
            self.excel_folder_edit.text(), self.image_folder_edit.text(),
            self.threshold_spin.value(), self.timeout_spin.value(),
        )
        self.worker.step_finished.connect(self.add_step_record)
        self.worker.progress_changed.connect(self.update_progress)
        self.worker.log_message.connect(self.append_log)
        self.worker.finished_with_summary.connect(self.finish_test)
        self.worker.failed.connect(self.fail_test)
        self._set_running(True)
        self.worker.start()

    def stop_test(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.request_stop()
            self.stop_btn.setEnabled(False)

    def clear_results(self):
        if self.worker is not None and self.worker.isRunning():
            return
        self.records.clear()
        self.table.setRowCount(0)
        self.progress_bar.setValue(0)
        self.detail_text.clear()
        self.log_text.clear()
        self.summary_label.setText(
            "等待开始。达标条件：服务器临时文件解析与报警规则判定延迟严格小于 1000ms。"
        )
        self._update_metrics({})

    def _set_running(self, running):
        for widget in (
            self.start_btn, self.clear_btn, self.excel_browse_btn,
            self.image_browse_btn, self.threshold_spin, self.timeout_spin,
        ):
            widget.setEnabled(not running)
        self.stop_btn.setEnabled(running)

    def add_step_record(self, record):
        record["executed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        self.records.append(record)
        # 排序开启时，写入第一列就会立即移动新行，后续列会被写到错误行。
        self.table.setSortingEnabled(False)
        row = self.table.rowCount()
        self.table.insertRow(row)
        values = [
            record["index"], record["executed_at"], record["data_type_text"],
            record["file_name"], record.get("test_id") or "",
            "" if record.get("upload_ms") is None else f"{record['upload_ms']:.3f}",
            "" if record.get("server_latency_ms") is None else f"{record['server_latency_ms']:.3f}",
            f"{record['total_ms']:.3f}",
            "是" if record.get("alarm_triggered") else "否",
            record.get("processing_status") or "", record["status"],
        ]
        for col, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            item.setToolTip(str(value))
            if col == 10:
                color = Qt.GlobalColor.darkGreen if value == "达标" else Qt.GlobalColor.red
                item.setForeground(color)
            if col == 0:
                item.setData(Qt.ItemDataRole.UserRole, record)
            self.table.setItem(row, col, item)
        self.table.setSortingEnabled(True)
        self.table.sortItems(1, Qt.SortOrder.DescendingOrder)
        self.table.selectRow(0)
        self._show_test_alarm_toast(record)

    def _show_test_alarm_toast(self, record):
        """测试预警只在当前上位机即时显示，不进入正式状态栏、数据库或消息队列。"""
        if not record.get("alarm_triggered"):
            return
        message = (
            f"[报警延迟测试] {record.get('file_name', '')}: "
            f"{record.get('alarm_message') or '触发测试预警'}"
        )
        payload = {
            "is_latency_test": True,
            "message": message,
            "file_name": record.get("file_name"),
            "data_type": record.get("data_type"),
            "test_id": record.get("test_id"),
        }
        for window in QApplication.topLevelWidgets():
            show_toast = getattr(window, "show_alarm_toast", None)
            if callable(show_toast):
                show_toast(message, payload)
                return

    def update_progress(self, summary):
        self.progress_bar.setValue(
            int(summary["current"] * 100 / max(1, summary["planned"]))
        )
        self.summary_label.setText(
            f"进度 {summary['current']}/{summary['planned']}，已测量 {summary['measured']}，"
            f"低于阈值 {summary['target_count']}，达标率 {summary['compliance_rate']:.2%}。"
        )
        self._update_metrics(summary)

    def _update_metrics(self, summary):
        self.metric_labels["measured"].setText(f"已测量: {summary.get('measured', 0)}")
        self.metric_labels["alarm"].setText(f"触发预警: {summary.get('alarm_count', 0)}")
        self.metric_labels["average"].setText(f"平均: {summary.get('average_ms', 0):.3f}ms")
        self.metric_labels["max"].setText(f"最大: {summary.get('max_ms', 0):.3f}ms")
        self.metric_labels["rate"].setText(
            f"达标率: {summary.get('compliance_rate', 0):.2%}"
        )

    def append_log(self, message):
        self.log_text.appendPlainText(
            f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} {message}"
        )

    def finish_test(self, summary):
        self._set_running(False)
        status = "已停止" if summary.get("stopped") else (
            "通过" if summary["passed"] else "未通过"
        )
        if not summary.get("stopped"):
            self.progress_bar.setValue(100)
        self.summary_label.setText(
            f"{status}：完成 {summary['completed']}/{summary['planned']}，"
            f"触发预警 {summary['alarm_count']}，平均 {summary['average_ms']:.3f}ms，"
            f"最大 {summary['max_ms']:.3f}ms，达标率 {summary['compliance_rate']:.2%}。"
        )
        self._update_metrics(summary)
        self.append_log(self.summary_label.text())

    def fail_test(self, message):
        self._set_running(False)
        self.append_log(f"测试失败: {message}")
        QMessageBox.critical(self, "报警延迟测试失败", message)

    def show_selected_detail(self):
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return
        item = self.table.item(rows[0].row(), 0)
        record = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not isinstance(record, dict):
            return
        detail = {
            "文件路径": record.get("file_path"),
            "测试编号": record.get("test_id"),
            "数据类型": record.get("data_type_text"),
            "请求总耗时(ms)": record.get("upload_ms"),
            "服务器报警判定延迟(ms)": record.get("server_latency_ms"),
            "端到端耗时(ms)": record.get("total_ms"),
            "阈值(ms，严格小于)": record.get("target_ms"),
            "是否达标": record.get("target_met"),
            "是否触发预警": record.get("alarm_triggered"),
            "预警信息": record.get("alarm_message"),
            "处理状态": record.get("processing_status"),
            "处理错误": record.get("processing_error"),
            "上传接口响应": record.get("upload_result"),
            "报警延迟接口响应": record.get("latency_result"),
        }
        self.detail_text.setPlainText(
            json.dumps(detail, ensure_ascii=False, indent=2, default=str)
        )

    def closeEvent(self, event):
        if self.worker is not None and self.worker.isRunning():
            self.worker.request_stop()
            self.worker.wait(3000)
        super().closeEvent(event)
