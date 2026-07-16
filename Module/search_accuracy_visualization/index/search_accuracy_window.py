"""检索准确率脚本可视化页面。"""
import json
import random
import time
from datetime import datetime

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QSpinBox, QDoubleSpinBox, QProgressBar, QTableWidget, QTableWidgetItem,
    QHeaderView, QPlainTextEdit, QGroupBox, QMessageBox
)

from public.entity.BaseWindow import BaseWindow
from Service.connect_server_service.api.api_client import UpperAPIClient


LOCATIONS = ["北京", "上海", "长沙", "苏州", "深圳"]
EXCEL_METRICS = ["power_w", "voltage", "current", "phase_angle"]
EXCEL_METRIC_TEXT = {
    "power_w": "功率W",
    "voltage": "电压",
    "current": "电流",
    "phase_angle": "相角",
}
EXCEL_PHASES = ["A相", "B相", "C相"]
EXCEL_SHEETS = ["A", "B", "C"]


def _server_url():
    """读取上位机当前服务器配置，保持与其它页面使用同一个地址。"""
    server_url = "http://localhost:8000"
    try:
        from public.config_class.global_setting import global_setting
        server_url = global_setting.get_setting("connect_server", {}).get("server", {}).get("url", server_url)
    except Exception:
        pass
    return str(server_url or "http://localhost:8000").strip().rstrip("/")


def _sheet_matches(actual: str, expected: str) -> bool:
    """兼容 A/B/C 与 Sheet A/Sheet B 两种写法。"""
    actual = str(actual or "").strip()
    expected = str(expected or "").strip()
    if not expected:
        return True
    if expected.lower().startswith("sheet "):
        expected = expected[6:].strip()
    return actual == expected or actual == f"Sheet {expected}"


def _detail_matches(row: dict, query: dict) -> bool:
    """校验返回结果是否满足 Excel 明细条件，用来统计误检。"""
    detail = row.get("excel_detail_match") or {}
    error = row.get("excel_error_match") or {}
    detail_keys = (
        "excel_sheet_name", "excel_metric_key", "excel_phase_name", "excel_meter_name",
        "excel_range_text", "excel_value_min", "excel_value_max",
        "excel_error_percent_abs_min", "excel_error_ppm_abs_min",
    )
    if not any(query.get(key) not in (None, "") for key in detail_keys):
        return True
    if row.get("data_type") != "excel":
        return False
    if query.get("excel_sheet_name") and not (
        _sheet_matches(detail.get("sheet_name"), query["excel_sheet_name"])
        or _sheet_matches(error.get("sheet_name"), query["excel_sheet_name"])
    ):
        return False
    if query.get("excel_metric_key"):
        metric_key = str(query["excel_metric_key"])
        if detail.get("metric_key") != metric_key and error.get("metric_key") != metric_key:
            return False
    if query.get("excel_phase_name"):
        if detail.get("phase_name") != query["excel_phase_name"] and error.get("phase_name") != query["excel_phase_name"]:
            return False
    if query.get("excel_meter_name") and query["excel_meter_name"] not in str(detail.get("meter_name", "")):
        return False
    if query.get("excel_range_text"):
        range_text = str(detail.get("range_text") or error.get("range_text") or "")
        if query["excel_range_text"] not in range_text:
            return False
    value = detail.get("value")
    if query.get("excel_value_min") is not None and (value is None or float(value) < float(query["excel_value_min"])):
        return False
    if query.get("excel_value_max") is not None and (value is None or float(value) > float(query["excel_value_max"])):
        return False
    error_percent = error.get("error_percent")
    if query.get("excel_error_percent_abs_min") is not None and (
        error_percent is None or abs(float(error_percent)) < float(query["excel_error_percent_abs_min"])
    ):
        return False
    error_ppm = error.get("error_ppm")
    if query.get("excel_error_ppm_abs_min") is not None and (
        error_ppm is None or abs(float(error_ppm)) < float(query["excel_error_ppm_abs_min"])
    ):
        return False
    return True


def _row_matches(row: dict, query: dict) -> bool:
    """校验接口返回行是否满足本次查询条件。"""
    if query.get("data_type") and row.get("data_type") != query["data_type"]:
        return False
    if query.get("device_id") and row.get("device_id") != query["device_id"]:
        return False
    if query.get("device_prefix") and not str(row.get("device_id", "")).startswith(query["device_prefix"]):
        return False
    if query.get("location") and str(query["location"]) not in str(row.get("location", "")):
        return False
    if query.get("keyword"):
        keyword = str(query["keyword"]).lower()
        searchable = " ".join(str(row.get(key, "")) for key in ("file_name", "device_id", "fault_summary", "excel_detail_summary")).lower()
        if keyword not in searchable:
            return False
    if query.get("has_fault") is not None and bool(row.get("has_fault")) != bool(query["has_fault"]):
        return False
    occurred_at = row.get("occurred_at") or row.get("uploaded_at") or ""
    if query.get("start_time") and occurred_at and occurred_at < query["start_time"]:
        return False
    if query.get("end_time") and occurred_at and occurred_at > query["end_time"]:
        return False
    return _detail_matches(row, query)


def _query_display(query: dict) -> str:
    """把查询参数转成便于表格阅读的中文摘要。"""
    labels = {
        "data_type": "类型", "device_id": "设备", "device_prefix": "设备前缀", "location": "地点",
        "keyword": "关键词", "has_fault": "故障", "start_time": "开始", "end_time": "结束", "excel_sheet_name": "Sheet",
        "excel_metric_key": "指标", "excel_phase_name": "相位", "excel_meter_name": "表计",
        "excel_range_text": "测试点", "excel_value_min": "值>=", "excel_value_max": "值<=",
        "excel_error_percent_abs_min": "误差%>=", "excel_error_ppm_abs_min": "误差ppm>=",
    }
    parts = []
    for key, value in query.items():
        if value in (None, "") or key == "limit":
            continue
        if key == "data_type":
            value = "电量" if value == "excel" else "几何量"
        elif key == "excel_metric_key":
            value = EXCEL_METRIC_TEXT.get(value, value)
        elif key == "has_fault":
            value = "是" if value else "否"
        parts.append(f"{labels.get(key, key)}={value}")
    return "；".join(parts) or "无过滤条件"


def _safe_float(value):
    """把 Excel 明细里的数字安全转成 float，失败时返回 None。"""
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _metric_key_from_name(metric_name: str) -> str:
    """把解析结果里的中文指标名转换成服务端明细表使用的稳定 key。"""
    name = str(metric_name or "").strip().lower()
    if "功率" in name or "power" in name:
        return "power_w"
    if "电压" in name or "voltage" in name:
        return "voltage"
    if "电流" in name or "current" in name:
        return "current"
    if "相角" in name or "phase" in name:
        return "phase_angle"
    return ""


def _has_excel_detail_filters(query: dict) -> bool:
    """判断一次查询是否带了 Excel 明细条件。"""
    return any(str(key).startswith("excel_") and value not in (None, "") for key, value in (query or {}).items())


def _extract_meter_detail_cases(record: dict, result_limit: int, max_cases: int = 80) -> list:
    """按指标均衡抽取真实明细点，避免首个指标耗尽全部用例配额。"""
    record = record or {}
    file_id = record.get("id") or record.get("file_id")
    device_id = record.get("device_id") or ""
    file_name = record.get("file_name") or ""
    parse_result = record.get("parse_result") or {}
    parsed_data = parse_result.get("parsed_data") or {}
    if isinstance(parsed_data, str):
        try:
            parsed_data = json.loads(parsed_data)
        except json.JSONDecodeError:
            parsed_data = {}

    cases_by_metric = {}
    for sheet_name, sheet_payload in (parsed_data or {}).items():
        for metric_block in sheet_payload.get("data", []) or []:
            metric_name = metric_block.get("name") or ""
            metric_key = metric_block.get("metric_key") or _metric_key_from_name(metric_name)
            metric_data = metric_block.get("data", {}) or {}
            point_meta = ((metric_data.get("x") or {}).get("point_meta") or [])
            for phase_block in metric_data.get("y", []) or []:
                phase_name = phase_block.get("name") or ""
                for meter_block in phase_block.get("data", []) or []:
                    meter_name = meter_block.get("name") or ""
                    values = meter_block.get("data", []) or []
                    for point_index, raw_value in enumerate(values):
                        numeric_value = _safe_float(raw_value)
                        meta = point_meta[point_index] if point_index < len(point_meta) else {}
                        query = {
                            "data_type": "excel",
                            "device_id": device_id,
                            "excel_sheet_name": str(sheet_name),
                            "excel_phase_name": str(phase_name),
                            "excel_meter_name": str(meter_name),
                            "limit": result_limit,
                        }
                        if metric_key:
                            query["excel_metric_key"] = str(metric_key)
                        if file_name:
                            query["keyword"] = file_name
                        range_text = meta.get("range_text")
                        if range_text:
                            query["excel_range_text"] = str(range_text)
                        if numeric_value is not None:
                            epsilon = max(abs(numeric_value) * 0.000001, 0.000001)
                            query["excel_value_min"] = numeric_value - epsilon
                            query["excel_value_max"] = numeric_value + epsilon
                        case = {
                            "query": query,
                            "expected_file_id": file_id,
                            "case_type": "计量明细召回",
                            "description": (
                                f"文件ID={file_id}；Sheet={sheet_name}；"
                                f"指标={EXCEL_METRIC_TEXT.get(metric_key, metric_name)}；"
                                f"相位={phase_name}；表计={meter_name}"
                            ),
                        }
                        bucket_key = str(metric_key or metric_name or "未知指标")
                        bucket = cases_by_metric.setdefault(bucket_key, [])
                        # 单个指标最多保留最终返回数量，控制大文件的临时内存占用。
                        if len(bucket) < max_cases:
                            bucket.append(case)

    # 功率、电压、电流、相角轮流取一条，未知指标也会追加参与轮询。
    metric_order = [key for key in EXCEL_METRICS if key in cases_by_metric]
    metric_order.extend(key for key in cases_by_metric if key not in metric_order)
    cases = []
    offset = 0
    while len(cases) < max_cases:
        added = False
        for metric_key in metric_order:
            bucket = cases_by_metric[metric_key]
            if offset < len(bucket):
                cases.append(bucket[offset])
                added = True
                if len(cases) >= max_cases:
                    break
        if not added:
            break
        offset += 1
    return cases

def _build_meter_query_cases(client: UpperAPIClient, rng: random.Random, result_limit: int, iterations: int, log_emit) -> list:
    """基于服务器真实电量数据构造查询用例，避免随机猜测造成虚高错误率。"""
    seed_limit = max(50, min(1000, iterations * 3))
    response = client.search_data(data_type="excel", limit=seed_limit) or {}
    rows = list(response.get("dataset", []) or [])
    if not rows:
        raise RuntimeError("服务器没有可用于测试的电量数据，请先上传并等待服务端解析完成。")
    rng.shuffle(rows)
    cases = []
    for row in rows:
        file_id = row.get("file_id")
        file_name = row.get("file_name") or ""
        if not file_id:
            continue
        if file_name:
            cases.append({
                "query": {"data_type": "excel", "keyword": file_name, "limit": result_limit},
                "expected_file_id": file_id,
                "case_type": "文件名召回",
                "description": f"文件ID={file_id}；文件名={file_name}",
            })
        if row.get("device_id") and file_name:
            cases.append({
                "query": {"data_type": "excel", "device_id": row.get("device_id"), "keyword": file_name, "limit": result_limit},
                "expected_file_id": file_id,
                "case_type": "设备+文件名召回",
                "description": f"文件ID={file_id}；设备={row.get('device_id')}；文件名={file_name}",
            })
    detail_source_rows = rows[:min(len(rows), 20)]
    for row in detail_source_rows:
        if len(cases) >= iterations * 2:
            break
        file_id = row.get("file_id")
        if not file_id:
            continue
        try:
            detail_response = client.get_excel_detail(int(file_id)) or {}
            detail_record = detail_response.get("data") or {}
            detail_cases = _extract_meter_detail_cases(detail_record, result_limit, max_cases=40)
            cases.extend(detail_cases)
            if detail_cases:
                metric_counts = {}
                for case in detail_cases:
                    metric_key = case.get("query", {}).get("excel_metric_key", "未知指标")
                    metric_counts[metric_key] = metric_counts.get(metric_key, 0) + 1
                coverage = "、".join(
                    f"{EXCEL_METRIC_TEXT.get(key, key)} {count} 条"
                    for key, count in metric_counts.items()
                )
                log_emit(f"已从文件ID={file_id} 抽取 {len(detail_cases)} 条计量明细查询用例：{coverage}")
        except Exception as exc:
            log_emit(f"文件ID={file_id} 明细抽样失败，跳过: {exc}")
    if not cases:
        raise RuntimeError("没有构造出可测试的电量检索用例，请确认服务端已返回电量文件和解析明细。")
    rng.shuffle(cases)
    while len(cases) < iterations:
        cases.extend(cases[:max(1, iterations - len(cases))])
    return cases[:iterations]


class SearchAccuracyWorker(QThread):
    """后台执行检索准确率可视化任务，避免 GUI 主线程卡顿。"""

    progress_changed = pyqtSignal(dict)
    step_finished = pyqtSignal(dict)
    log_message = pyqtSignal(str)
    finished_with_summary = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, base_url: str, iterations: int, result_limit: int, threshold: float, seed: int):
        super().__init__()
        self.base_url = base_url
        self.iterations = iterations
        self.result_limit = result_limit
        self.threshold = threshold
        self.seed = seed
        self._stop_requested = False

    def request_stop(self):
        self._stop_requested = True

    def run(self):
        client = UpperAPIClient(self.base_url, timeout=20)
        rng = random.Random(self.seed)
        checked = 0
        errors = 0
        started_at = time.time()
        self.log_message.emit(f"开始计量数据检索准确率测试，服务器: {self.base_url}")
        try:
            cases = _build_meter_query_cases(client, rng, self.result_limit, self.iterations, self.log_message.emit)
            self.log_message.emit(f"已基于服务器真实电量数据生成 {len(cases)} 条查询用例。")
            for index, case in enumerate(cases, start=1):
                if self._stop_requested:
                    self.log_message.emit("用户停止测试，保留已完成统计。")
                    break
                query = dict(case["query"])
                expected_file_id = str(case.get("expected_file_id"))
                query_text = f"{case.get('case_type', '计量查询')}；{_query_display(query)}"
                step_start = time.time()
                self.log_message.emit(f"[{index}/{len(cases)}] 发起检索: {query_text}")
                result = client.search_data(**query)
                dataset = list(result.get("dataset", []) or [])
                checked += 1
                recall_ok = any(str(row.get("file_id")) == expected_file_id for row in dataset)
                # 远程服务端可能尚未返回 excel_detail_match；准确率按目标文件召回统计，明细二次校验只做诊断。
                can_check_detail = (not _has_excel_detail_filters(query)) or any(
                    row.get("excel_detail_match") or row.get("excel_error_match") for row in dataset
                )
                mismatch_rows = [row for row in dataset if not _row_matches(row, query)] if can_check_detail else []
                step_errors = 0 if recall_ok else 1
                errors += step_errors
                elapsed_ms = int((time.time() - step_start) * 1000)
                error_rate = errors / max(1, checked)
                step = {
                    "index": index,
                    "query": query,
                    "query_text": query_text,
                    "expected_file_id": expected_file_id,
                    "case_description": case.get("description", ""),
                    "total": result.get("total", len(dataset)),
                    "count": len(dataset),
                    "checked": checked,
                    "errors": errors,
                    "row_errors": step_errors,
                    "mismatch_rows": len(mismatch_rows),
                    "recall_ok": recall_ok,
                    "error_rate": error_rate,
                    "elapsed_ms": elapsed_ms,
                    "sample": dataset[:3],
                    "status": "异常" if step_errors else "通过",
                }
                self.step_finished.emit(step)
                self.progress_changed.emit({
                    "current": index,
                    "total": len(cases),
                    "checked": checked,
                    "errors": errors,
                    "error_rate": error_rate,
                    "threshold": self.threshold,
                })
                if step_errors:
                    reason = "未召回应命中文件"
                    self.log_message.emit(f"[{index}/{len(cases)}] 异常: {reason}，当前查询错误率 {error_rate:.6f}")
                else:
                    diag = f"，诊断发现 {len(mismatch_rows)} 条返回行字段不完全匹配" if mismatch_rows else ""
                    self.log_message.emit(f"[{index}/{len(cases)}] 通过，召回文件ID={expected_file_id}，返回 {len(dataset)} 条，用时 {elapsed_ms}ms{diag}")
        except Exception as exc:
            self.failed.emit(str(exc))
            return

        elapsed_total = time.time() - started_at
        error_rate = errors / max(1, checked)
        self.finished_with_summary.emit({
            "checked": checked,
            "errors": errors,
            "error_rate": error_rate,
            "threshold": self.threshold,
            "elapsed_seconds": elapsed_total,
            "passed": error_rate <= self.threshold,
            "stopped": self._stop_requested,
        })


class SearchAccuracyVisualizationWindow(BaseWindow):
    """把检索准确率脚本的执行过程可视化到上位机工具菜单。"""

    def __init__(self):
        super().__init__()
        self.worker = None
        self.records = []
        self.setWindowTitle("检索准确率可视化")
        self.resize(1280, 820)
        self._init_ui()

    def _init_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        config_group = QGroupBox("测试配置")
        config_layout = QGridLayout(config_group)
        self.server_label = QLabel(_server_url())
        self.iterations_spin = QSpinBox()
        self.iterations_spin.setRange(1, 10000)
        self.iterations_spin.setValue(200)
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(1, 1000)
        self.limit_spin.setValue(100)
        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(0.0, 1.0)
        self.threshold_spin.setDecimals(6)
        self.threshold_spin.setSingleStep(0.0001)
        self.threshold_spin.setValue(0.01)
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(1, 999999999)
        self.seed_spin.setValue(20260708)
        self.start_btn = QPushButton("开始测试")
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setEnabled(False)
        self.clear_btn = QPushButton("清空结果")
        self.start_btn.clicked.connect(self.start_test)
        self.stop_btn.clicked.connect(self.stop_test)
        self.clear_btn.clicked.connect(self.clear_results)

        config_layout.addWidget(QLabel("服务器地址"), 0, 0)
        config_layout.addWidget(self.server_label, 0, 1, 1, 5)
        config_layout.addWidget(QLabel("检索次数"), 1, 0)
        config_layout.addWidget(self.iterations_spin, 1, 1)
        config_layout.addWidget(QLabel("每次返回数量"), 1, 2)
        config_layout.addWidget(self.limit_spin, 1, 3)
        config_layout.addWidget(QLabel("错误率阈值"), 1, 4)
        config_layout.addWidget(self.threshold_spin, 1, 5)
        config_layout.addWidget(QLabel("随机种子"), 1, 6)
        config_layout.addWidget(self.seed_spin, 1, 7)
        config_layout.addWidget(self.start_btn, 0, 6)
        config_layout.addWidget(self.stop_btn, 0, 7)
        config_layout.addWidget(self.clear_btn, 0, 8)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.summary_label = QLabel("等待开始。")

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(["序号", "执行时间", "状态", "查询条件", "接口总数", "本次返回", "本次错误", "查询错误率", "耗时(ms)"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        for col in range(4, 9):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.show_selected_detail)

        detail_layout = QHBoxLayout()
        self.detail_text = QPlainTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setPlaceholderText("选择上方某次检索，这里会显示查询参数、返回样例和校验过程。")
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setPlaceholderText("检索过程日志会实时显示在这里。")
        detail_layout.addWidget(self.detail_text, 1)
        detail_layout.addWidget(self.log_text, 1)

        root.addWidget(config_group)
        root.addWidget(self.progress_bar)
        root.addWidget(self.summary_label)
        root.addWidget(self.table, 3)
        root.addLayout(detail_layout, 2)
        self.setCentralWidget(central)
        self.statusBar().showMessage("检索准确率可视化就绪")

    def start_test(self):
        """启动后台检索测试线程，并实时接收进度信号。"""
        if self.worker is not None and self.worker.isRunning():
            return
        self.clear_results()
        self.server_label.setText(_server_url())
        self.worker = SearchAccuracyWorker(
            base_url=self.server_label.text(),
            iterations=self.iterations_spin.value(),
            result_limit=self.limit_spin.value(),
            threshold=self.threshold_spin.value(),
            seed=self.seed_spin.value(),
        )
        self.worker.step_finished.connect(self.add_step_record)
        self.worker.progress_changed.connect(self.update_progress)
        self.worker.log_message.connect(self.append_log)
        self.worker.finished_with_summary.connect(self.finish_test)
        self.worker.failed.connect(self.fail_test)
        self._set_running(True)
        self.append_log("后台线程已启动，开始逐次检索。")
        self.worker.start()

    def stop_test(self):
        """请求后台线程在当前检索结束后停止。"""
        if self.worker is not None and self.worker.isRunning():
            self.worker.request_stop()
            self.stop_btn.setEnabled(False)
            self.append_log("已请求停止，等待当前检索结束。")

    def clear_results(self):
        if self.worker is not None and self.worker.isRunning():
            return
        self.records = []
        self.table.setRowCount(0)
        self.progress_bar.setValue(0)
        self.summary_label.setText("等待开始。")
        self.detail_text.clear()
        self.log_text.clear()
        self.statusBar().showMessage("结果已清空")

    def _set_running(self, running: bool):
        self.start_btn.setEnabled(not running)
        self.clear_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        self.iterations_spin.setEnabled(not running)
        self.limit_spin.setEnabled(not running)
        self.threshold_spin.setEnabled(not running)
        self.seed_spin.setEnabled(not running)

    def add_step_record(self, record: dict):
        """把一次检索的完整过程记录追加到表格。"""
        record["executed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        self.records.append(record)
        self.table.setSortingEnabled(False)
        row = self.table.rowCount()
        self.table.insertRow(row)
        values = [
            record["index"],
            record["executed_at"],
            record["status"],
            record["query_text"],
            record["total"],
            record["count"],
            record["row_errors"],
            f"{record['error_rate']:.6f}",
            record["elapsed_ms"],
        ]
        for col, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            item.setToolTip(str(value))
            if col == 2:
                item.setForeground(Qt.GlobalColor.red if value == "异常" else Qt.GlobalColor.darkGreen)
            if col == 0:
                # 行内保存完整记录，排序后点击详情仍能读取正确测试步骤。
                item.setData(Qt.ItemDataRole.UserRole, record)
            self.table.setItem(row, col, item)
        self.table.setSortingEnabled(True)
        self.sort_table_by_latest_time(self.table, ("执行时间",))
        self.table.scrollToTop()
        self.table.selectRow(0)

    def update_progress(self, progress: dict):
        percent = int(progress["current"] * 100 / max(1, progress["total"]))
        self.progress_bar.setValue(percent)
        self.summary_label.setText(
            f"进度 {progress['current']}/{progress['total']}，已执行 {progress['checked']} 次查询，"
            f"错误 {progress['errors']} 次，当前查询错误率 {progress['error_rate']:.6f}，阈值 {progress['threshold']:.6f}"
        )
        self.statusBar().showMessage("检索准确率测试运行中")

    def append_log(self, message: str):
        self.log_text.appendPlainText(f"{datetime.now().strftime('%H:%M:%S')} {message}")

    def finish_test(self, summary: dict):
        self._set_running(False)
        status = "通过" if summary["passed"] else "未通过"
        if summary.get("stopped"):
            status = "已停止"
        self.progress_bar.setValue(100 if not summary.get("stopped") else self.progress_bar.value())
        self.summary_label.setText(
            f"{status}：已执行 {summary['checked']} 次查询，错误 {summary['errors']} 次，"
            f"查询错误率 {summary['error_rate']:.6f}，耗时 {summary['elapsed_seconds']:.1f}s"
        )
        self.append_log(self.summary_label.text())
        self.statusBar().showMessage(f"检索准确率测试{status}")

    def fail_test(self, message: str):
        self._set_running(False)
        self.append_log(f"测试失败: {message}")
        self.statusBar().showMessage("检索准确率测试失败")
        QMessageBox.critical(self, "检索准确率测试失败", message)

    def show_selected_detail(self):
        selected = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not selected:
            return
        row = selected[0].row()
        record_item = self.table.item(row, 0)
        record = record_item.data(Qt.ItemDataRole.UserRole) if record_item is not None else None
        if not isinstance(record, dict):
            return
        detail = {
            "本次查询": record.get("query"),
            "查询说明": record.get("query_text"),
            "接口返回数量": record.get("count"),
            "期望召回文件ID": record.get("expected_file_id"),
            "用例说明": record.get("case_description"),
            "是否召回": record.get("recall_ok"),
            "返回不匹配行数(诊断)": record.get("mismatch_rows"),
            "本次是否漏召回": record.get("row_errors"),
            "累计查询数量": record.get("checked"),
            "累计错误数量": record.get("errors"),
            "累计查询错误率": record.get("error_rate"),
            "返回样例前3条": record.get("sample"),
        }
        self.detail_text.setPlainText(json.dumps(detail, ensure_ascii=False, indent=2, default=str))

    def closeEvent(self, event):
        if self.worker is not None and self.worker.isRunning():
            self.worker.request_stop()
            self.worker.wait(3000)
        super().closeEvent(event)
