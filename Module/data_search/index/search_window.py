"""上位机数据检索界面。"""
import json
from pathlib import Path

from PyQt6.QtCore import QDateTime, Qt, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QDateTimeEdit, QSpinBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QGroupBox, QCheckBox, QFileDialog
)
from loguru import logger

from public.entity.BaseWindow import BaseWindow
from Service.connect_server_service.api.api_client import UpperAPIClient


class DataSearchWindow(BaseWindow):
    """按时间、地点、故障和设备编号检索服务器数据集。"""

    LOCATIONS = ["", "北京", "上海", "长沙", "苏州", "深圳"]
    DATA_TYPES = [("全部", ""), ("电量数据", "excel"), ("几何量数据", "image")]
    FAULT_FLAGS = [("全部", None), ("仅故障", True), ("仅正常", False)]
    EXCEL_SHEETS = [("全部", ""), ("Sheet A", "A"), ("Sheet B", "B"), ("Sheet C", "C")]
    EXCEL_METRICS = [("全部", ""), ("功率W", "power_w"), ("电压", "voltage"), ("电流", "current"), ("相角", "phase_angle")]
    EXCEL_PHASES = [("全部", ""), ("A相", "A相"), ("B相", "B相"), ("C相", "C相")]

    def __init__(self):
        super().__init__()
        self.client = self._create_client()
        self.dataset = []
        self._search_loading = False
        self.setWindowTitle("数据检索")
        self.resize(1120, 720)
        self._init_ui()

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

        filter_group = QGroupBox("检索条件")
        filter_layout = QGridLayout(filter_group)
        filter_layout.setHorizontalSpacing(10)
        filter_layout.setVerticalSpacing(8)

        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("文件名、设备号、故障描述")

        self.data_type_combo = QComboBox()
        for text, value in self.DATA_TYPES:
            self.data_type_combo.addItem(text, value)

        self.location_combo = QComboBox()
        self.location_combo.addItems(self.LOCATIONS)
        self.location_combo.setEditable(True)
        self.location_combo.lineEdit().setPlaceholderText("输入或选择地点")
        self.location_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)

        self.device_combo = QComboBox()
        self.device_combo.addItem("全部设备", "")
        for device_id in [f"E{i:03d}" for i in range(1, 11)] + [f"G{i:03d}" for i in range(1, 11)]:
            self.device_combo.addItem(device_id, device_id)
        self.device_combo.setEditable(True)
        self.device_combo.lineEdit().setPlaceholderText("输入或选择设备编号")
        self.device_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)

        self.fault_combo = QComboBox()
        for text, value in self.FAULT_FLAGS:
            self.fault_combo.addItem(text, value)

        self.excel_sheet_combo = QComboBox()
        for text, value in self.EXCEL_SHEETS:
            self.excel_sheet_combo.addItem(text, value)
        self.excel_sheet_combo.setEditable(True)
        self.excel_sheet_combo.lineEdit().setPlaceholderText("A / B / C")

        self.excel_metric_combo = QComboBox()
        for text, value in self.EXCEL_METRICS:
            self.excel_metric_combo.addItem(text, value)

        self.excel_phase_combo = QComboBox()
        for text, value in self.EXCEL_PHASES:
            self.excel_phase_combo.addItem(text, value)

        self.excel_meter_input = QLineEdit()
        self.excel_meter_input.setPlaceholderText("表计名称，如 TD3310R")
        self.excel_range_input = QLineEdit()
        self.excel_range_input.setPlaceholderText("测试点，如 0.0° / 0.2A")
        self.excel_value_min_input = QLineEdit()
        self.excel_value_min_input.setPlaceholderText("数值最小")
        self.excel_value_max_input = QLineEdit()
        self.excel_value_max_input.setPlaceholderText("数值最大")
        self.excel_error_percent_input = QLineEdit()
        self.excel_error_percent_input.setPlaceholderText("误差%绝对值≥")
        self.excel_error_ppm_input = QLineEdit()
        self.excel_error_ppm_input.setPlaceholderText("误差ppm绝对值≥")
        self._excel_detail_widgets = [
            self.excel_sheet_combo, self.excel_metric_combo, self.excel_phase_combo,
            self.excel_meter_input, self.excel_range_input, self.excel_value_min_input,
            self.excel_value_max_input, self.excel_error_percent_input, self.excel_error_ppm_input,
        ]
        self.data_type_combo.currentIndexChanged.connect(self._sync_excel_filters_enabled)

        self.enable_time_checkbox = QCheckBox("启用时间范围")
        self.start_time_edit = QDateTimeEdit(QDateTime.currentDateTime().addDays(-7))
        self.end_time_edit = QDateTimeEdit(QDateTime.currentDateTime())
        for editor in (self.start_time_edit, self.end_time_edit):
            editor.setCalendarPopup(True)
            editor.setDisplayFormat("yyyy-MM-dd HH:mm:ss")

        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(1, 1000)
        self.limit_spin.setValue(100)
        self.excel_sheet_combo.setCurrentIndex(0)
        self.excel_metric_combo.setCurrentIndex(0)
        self.excel_phase_combo.setCurrentIndex(0)
        for editor in (
            self.excel_meter_input, self.excel_range_input, self.excel_value_min_input,
            self.excel_value_max_input, self.excel_error_percent_input, self.excel_error_ppm_input,
        ):
            editor.clear()
        self._sync_excel_filters_enabled()

        self.search_btn = QPushButton("检索")
        self.reset_btn = QPushButton("重置")
        self.search_btn.clicked.connect(self.search_dataset)
        self.reset_btn.clicked.connect(self.reset_filters)

        filter_layout.addWidget(QLabel("关键词"), 0, 0)
        filter_layout.addWidget(self.keyword_input, 0, 1, 1, 3)
        filter_layout.addWidget(QLabel("数据类型"), 0, 4)
        filter_layout.addWidget(self.data_type_combo, 0, 5)
        filter_layout.addWidget(QLabel("地点"), 1, 0)
        filter_layout.addWidget(self.location_combo, 1, 1)
        filter_layout.addWidget(QLabel("设备编号"), 1, 2)
        filter_layout.addWidget(self.device_combo, 1, 3)
        filter_layout.addWidget(QLabel("故障状态"), 1, 4)
        filter_layout.addWidget(self.fault_combo, 1, 5)
        filter_layout.addWidget(self.enable_time_checkbox, 2, 0)
        filter_layout.addWidget(self.start_time_edit, 2, 1, 1, 2)
        filter_layout.addWidget(self.end_time_edit, 2, 3, 1, 2)
        filter_layout.addWidget(QLabel("数量"), 2, 5)
        filter_layout.addWidget(self.limit_spin, 2, 6)
        filter_layout.addWidget(self.search_btn, 0, 6)
        filter_layout.addWidget(self.reset_btn, 1, 6)

        filter_layout.addWidget(QLabel("Excel Sheet"), 3, 0)
        filter_layout.addWidget(self.excel_sheet_combo, 3, 1)
        filter_layout.addWidget(QLabel("Excel 指标"), 3, 2)
        filter_layout.addWidget(self.excel_metric_combo, 3, 3)
        filter_layout.addWidget(QLabel("相位"), 3, 4)
        filter_layout.addWidget(self.excel_phase_combo, 3, 5)
        filter_layout.addWidget(QLabel("表计"), 3, 6)
        filter_layout.addWidget(self.excel_meter_input, 3, 7)
        filter_layout.addWidget(QLabel("测试点"), 4, 0)
        filter_layout.addWidget(self.excel_range_input, 4, 1)
        filter_layout.addWidget(QLabel("数值范围"), 4, 2)
        filter_layout.addWidget(self.excel_value_min_input, 4, 3)
        filter_layout.addWidget(self.excel_value_max_input, 4, 4)
        filter_layout.addWidget(self.excel_error_percent_input, 4, 5)
        filter_layout.addWidget(self.excel_error_ppm_input, 4, 6, 1, 2)

        self.summary_label = QLabel("等待检索")
        self.summary_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.table = QTableWidget(0, 11)
        self.table.setHorizontalHeaderLabels(["ID", "类型", "设备", "地点", "文件名", "故障", "故障摘要", "Excel命中明细", "发生时间", "下载地址", "操作"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(10, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)

        root.addWidget(filter_group)
        root.addWidget(self.summary_label)
        root.addWidget(self.table)
        self.setCentralWidget(central)
        self.statusBar().showMessage("数据检索就绪")
        self._sync_excel_filters_enabled()

    def _iso_time(self, editor: QDateTimeEdit):
        return editor.dateTime().toString("yyyy-MM-ddTHH:mm:ss")

    def _editable_combo_text(self, combo: QComboBox, empty_labels=None):
        """读取可编辑下拉框文本，避免手动输入时仍使用旧的 currentData。"""
        empty_labels = set(empty_labels or [])
        text = combo.currentText().strip()
        if not text or text in empty_labels:
            return None
        data = combo.currentData()
        return data if data not in (None, "") and text in empty_labels else text

    def _combo_value(self, combo: QComboBox):
        """优先使用下拉框绑定值；可编辑输入时回退到用户输入文本。"""
        text = combo.currentText().strip()
        data = combo.currentData()
        if not text or text == "全部":
            return None
        return data or text

    def _float_text(self, editor: QLineEdit, label: str):
        """把可选数字检索框转成 float，输入非法时给出明确提示。"""
        text = editor.text().strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError as exc:
            raise ValueError(f"{label} 必须填写数字") from exc

    def _sync_excel_filters_enabled(self):
        """只有全部/电量数据检索时启用 Excel 细字段，避免几何量检索误选。"""
        enabled = self.data_type_combo.currentData() in ("", "excel")
        for widget in self._excel_detail_widgets:
            widget.setEnabled(enabled)

    def _has_excel_filter_values(self, filters: dict) -> bool:
        """判断用户是否填写了 Excel 精细字段；填写后必须按电量数据收敛结果。"""
        keys = (
            "excel_sheet_name", "excel_metric_key", "excel_phase_name",
            "excel_meter_name", "excel_range_text", "excel_value_min", "excel_value_max",
            "excel_error_percent_abs_min", "excel_error_ppm_abs_min",
        )
        return any(filters.get(key) not in (None, "") for key in keys)

    def _sheet_matches(self, actual, expected) -> bool:
        """兼容数据库中的 A/B/C 与界面中的 Sheet A/Sheet B 写法。"""
        actual = str(actual or "").strip()
        expected = str(expected or "").strip()
        if not expected:
            return True
        if expected.lower().startswith("sheet "):
            expected = expected[6:].strip()
        return actual == expected or actual == f"Sheet {expected}"

    def _metric_matches(self, actual_key, actual_name, expected_key) -> bool:
        """兼容指标 key 和中文指标名，避免功率/电压这类条件因为展示名不同失效。"""
        expected = str(expected_key or "").strip()
        if not expected:
            return True
        metric_names = {
            "power_w": ("power_w", "功率", "功率W"),
            "voltage": ("voltage", "电压"),
            "current": ("current", "电流"),
            "phase_angle": ("phase_angle", "相角"),
        }.get(expected, (expected,))
        text = f"{actual_key or ''} {actual_name or ''}"
        return any(item and item in text for item in metric_names)

    def _detail_payload_matches(self, detail: dict, filters: dict, is_error: bool = False) -> bool:
        """检查服务端返回的 excel_detail_match/excel_error_match 是否满足界面条件。"""
        if not detail:
            return False
        if filters.get("excel_sheet_name") and not self._sheet_matches(detail.get("sheet_name"), filters["excel_sheet_name"]):
            return False
        if filters.get("excel_metric_key") and not self._metric_matches(detail.get("metric_key"), detail.get("metric_name"), filters["excel_metric_key"]):
            return False
        if filters.get("excel_phase_name") and detail.get("phase_name") != filters["excel_phase_name"]:
            return False
        if filters.get("excel_meter_name") and not is_error and filters["excel_meter_name"] not in str(detail.get("meter_name", "")):
            return False
        if filters.get("excel_range_text") and filters["excel_range_text"] not in str(detail.get("range_text", "")):
            return False
        if is_error:
            error_percent = detail.get("error_percent")
            if filters.get("excel_error_percent_abs_min") is not None and (
                error_percent is None or abs(float(error_percent)) < float(filters["excel_error_percent_abs_min"])
            ):
                return False
            error_ppm = detail.get("error_ppm")
            if filters.get("excel_error_ppm_abs_min") is not None and (
                error_ppm is None or abs(float(error_ppm)) < float(filters["excel_error_ppm_abs_min"])
            ):
                return False
            return True
        if filters.get("excel_error_percent_abs_min") is not None or filters.get("excel_error_ppm_abs_min") is not None:
            return False
        value = detail.get("value")
        if filters.get("excel_value_min") is not None and (value is None or float(value) < float(filters["excel_value_min"])):
            return False
        if filters.get("excel_value_max") is not None and (value is None or float(value) > float(filters["excel_value_max"])):
            return False
        return True

    def _excel_parsed_detail_matches(self, detail_response: dict, filters: dict) -> bool:
        """远程服务端未返回命中明细时，从 Excel 解析详情中做一次客户端兜底过滤。"""
        record = (detail_response or {}).get("data") or {}
        parse_result = record.get("parse_result") or {}
        parsed_data = parse_result.get("parsed_data") or {}
        if isinstance(parsed_data, str):
            try:
                parsed_data = json.loads(parsed_data)
            except json.JSONDecodeError:
                parsed_data = {}
        if filters.get("excel_error_percent_abs_min") is not None or filters.get("excel_error_ppm_abs_min") is not None:
            # 旧服务端详情接口通常只给数值明细，不给误差明细；有误差条件时不能用数值详情误判为命中。
            return False
        for sheet_name, sheet_payload in (parsed_data or {}).items():
            if filters.get("excel_sheet_name") and not self._sheet_matches(sheet_name, filters["excel_sheet_name"]):
                continue
            for metric_block in sheet_payload.get("data", []) or []:
                metric_name = metric_block.get("name") or ""
                metric_key = metric_block.get("metric_key") or ""
                if filters.get("excel_metric_key") and not self._metric_matches(metric_key, metric_name, filters["excel_metric_key"]):
                    continue
                metric_data = metric_block.get("data", {}) or {}
                point_meta = ((metric_data.get("x") or {}).get("point_meta") or [])
                for phase_block in metric_data.get("y", []) or []:
                    phase_name = phase_block.get("name") or ""
                    if filters.get("excel_phase_name") and phase_name != filters["excel_phase_name"]:
                        continue
                    for meter_block in phase_block.get("data", []) or []:
                        meter_name = meter_block.get("name") or ""
                        if filters.get("excel_meter_name") and filters["excel_meter_name"] not in str(meter_name):
                            continue
                        for point_index, raw_value in enumerate(meter_block.get("data", []) or []):
                            meta = point_meta[point_index] if point_index < len(point_meta) else {}
                            range_text = str(meta.get("range_text") or "")
                            if filters.get("excel_range_text") and filters["excel_range_text"] not in range_text:
                                continue
                            try:
                                value = float(raw_value)
                            except (TypeError, ValueError):
                                continue
                            if filters.get("excel_value_min") is not None and value < float(filters["excel_value_min"]):
                                continue
                            if filters.get("excel_value_max") is not None and value > float(filters["excel_value_max"]):
                                continue
                            return True
        return False

    def _filter_excel_rows_locally(self, rows: list, filters: dict) -> list:
        """服务端未完成精细过滤时的上位机兜底：只保留满足 Excel 条件的电量数据。"""
        filtered = []
        for row in rows:
            if row.get("data_type") != "excel":
                continue
            detail = row.get("excel_detail_match") or {}
            error_detail = row.get("excel_error_match") or {}
            if detail and self._detail_payload_matches(detail, filters):
                filtered.append(row)
                continue
            if error_detail and self._detail_payload_matches(error_detail, filters, is_error=True):
                filtered.append(row)
                continue
            file_id = row.get("file_id") or row.get("id")
            if not file_id:
                continue
            try:
                if self._excel_parsed_detail_matches(self.client.get_excel_detail(int(file_id)), filters):
                    filtered.append(row)
            except Exception as exc:
                logger.warning(f"本地兜底过滤 Excel 明细失败，file_id={file_id}: {exc}")
        return filtered

    def search_dataset(self):
        """异步调用服务器检索接口并刷新结果表。"""
        if self._search_loading:
            return
        self._search_loading = True

        excel_enabled = self.data_type_combo.currentData() in ("", "excel")
        try:
            filters = {
                "keyword": self.keyword_input.text().strip() or None,
                "data_type": self.data_type_combo.currentData() or None,
                "location": self._editable_combo_text(self.location_combo),
                "device_id": self._editable_combo_text(self.device_combo, {"全部设备"}),
                "has_fault": self.fault_combo.currentData(),
                "excel_sheet_name": self._combo_value(self.excel_sheet_combo) if excel_enabled else None,
                "excel_metric_key": self._combo_value(self.excel_metric_combo) if excel_enabled else None,
                "excel_phase_name": self._combo_value(self.excel_phase_combo) if excel_enabled else None,
                "excel_meter_name": (self.excel_meter_input.text().strip() or None) if excel_enabled else None,
                "excel_range_text": (self.excel_range_input.text().strip() or None) if excel_enabled else None,
                "excel_value_min": self._float_text(self.excel_value_min_input, "数值下限") if excel_enabled else None,
                "excel_value_max": self._float_text(self.excel_value_max_input, "数值上限") if excel_enabled else None,
                "excel_error_percent_abs_min": self._float_text(self.excel_error_percent_input, "误差百分比绝对值下限") if excel_enabled else None,
                "excel_error_ppm_abs_min": self._float_text(self.excel_error_ppm_input, "误差 ppm 绝对值下限") if excel_enabled else None,
                "limit": self.limit_spin.value(),
            }
            excel_fine_search = self._has_excel_filter_values(filters)
            if excel_fine_search:
                # 只要使用 Excel 精细字段，就强制按电量数据查询，避免“全部”类型返回几何量数据。
                filters["data_type"] = "excel"
        except ValueError as exc:
            self._search_loading = False
            QMessageBox.warning(self, "检索条件错误", str(exc))
            return
        if self.enable_time_checkbox.isChecked():
            filters["start_time"] = self._iso_time(self.start_time_edit)
            filters["end_time"] = self._iso_time(self.end_time_edit)

        def task():
            result = self.client.search_data(**filters)
            if excel_fine_search:
                dataset = list(result.get("dataset", []) or [])
                refined = self._filter_excel_rows_locally(dataset, filters)
                result["dataset"] = refined
                result["count"] = len(refined)
                result["total"] = len(refined)
            return result

        def on_success(result):
            self._search_loading = False
            self.dataset = result.get("dataset", [])
            self._fill_table(self.dataset)
            self.summary_label.setText(f"共命中 {result.get('total', len(self.dataset))} 条，当前显示 {len(self.dataset)} 条")
            self.statusBar().showMessage("检索完成")

        def on_error(message):
            self._search_loading = False
            self.statusBar().showMessage("检索失败")
            QMessageBox.critical(self, "检索失败", message)

        self.run_async_task(
            task,
            on_success=on_success,
            on_error=on_error,
            loading_text="正在检索服务器数据集...",
            widgets=[self.search_btn, self.reset_btn],
        )

    def reset_filters(self):
        self.show_loading("正在重置检索条件...")
        self.keyword_input.clear()
        self.data_type_combo.setCurrentIndex(0)
        self.location_combo.setCurrentIndex(0)
        self.device_combo.setCurrentIndex(0)
        self.fault_combo.setCurrentIndex(0)
        self.enable_time_checkbox.setChecked(False)
        self.limit_spin.setValue(100)
        self.excel_sheet_combo.setCurrentIndex(0)
        self.excel_metric_combo.setCurrentIndex(0)
        self.excel_phase_combo.setCurrentIndex(0)
        for editor in (
            self.excel_meter_input, self.excel_range_input, self.excel_value_min_input,
            self.excel_value_max_input, self.excel_error_percent_input, self.excel_error_ppm_input,
        ):
            editor.clear()
        self._sync_excel_filters_enabled()
        self.table.setRowCount(0)
        self.summary_label.setText("等待检索")
        self.statusBar().showMessage("检索条件已重置")
        self.hide_loading()


    def _row_to_viewer_record(self, row: dict) -> dict:
        """把检索结果转换成电量/几何量查看器可识别的记录结构。"""
        file_id = row.get("file_id") or row.get("id")
        upload_time = row.get("uploaded_at") or row.get("occurred_at") or ""
        # 电量查看器会在 processing_status=done 时主动补取详情；检索结果是文件索引，先按已完成处理交给查看器复核。
        return {
            "id": file_id,
            "file_id": file_id,
            "device_id": row.get("device_id") or "",
            "file_name": row.get("file_name") or "",
            "file_path": row.get("file_path") or row.get("download_url") or "",
            "upload_time": upload_time,
            "processing_status": row.get("processing_status") or "done",
            "alarm_info": row.get("alarm_info") or {},
        }

    def _find_loaded_module_window(self, module_name: str):
        """从主窗口已加载模块里找到对应页面窗口，供检索页跳转后定位记录。"""
        main_gui = getattr(self, "main_gui", None)
        for module in getattr(main_gui, "modules", []) or []:
            if getattr(module, "name", None) != module_name:
                continue
            interface_widget = getattr(module, "interface_widget", None)
            return getattr(interface_widget, "frame_obj", None)
        return None

    def view_dataset_row(self, row: dict):
        """打开对应数据查看页面，并尽量直接展示检索命中的那条数据。"""
        data_type = row.get("data_type")
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
                QMessageBox.information(self, "提示", "已打开对应查看页面。")

        QTimer.singleShot(250, load_record_in_viewer)
        self.statusBar().showMessage(f"正在打开 {row.get('file_name', '')}")

    def download_dataset_row(self, row: dict):
        """选择文件夹后从服务器下载检索命中的原始数据文件。"""
        data_type = row.get("data_type")
        file_id = row.get("file_id")
        if data_type not in {"excel", "image"} or not file_id:
            QMessageBox.warning(self, "下载失败", "当前记录缺少数据类型或文件编号。")
            return
        target_dir = QFileDialog.getExistingDirectory(
            self,
            "选择下载目录",
            str(Path.home() / "Downloads"),
        )
        if not target_dir:
            return
        default_name = f"{data_type}_{file_id}.xlsx" if data_type == "excel" else f"{data_type}_{file_id}.png"
        save_path = Path(target_dir) / (row.get("file_name") or default_name)

        def task():
            self.client.download_file(str(data_type), int(file_id), save_path)
            return save_path

        def on_success(downloaded_path: Path):
            self.statusBar().showMessage(f"下载完成: {downloaded_path}")
            QMessageBox.information(self, "下载完成", f"文件已下载到：\n{downloaded_path}")

        self.run_async_task(
            task,
            on_success=on_success,
            on_error=lambda message: QMessageBox.critical(self, "下载失败", message),
            loading_text=f"正在下载 {row.get('file_name') or default_name}...",
            widgets=[self.search_btn, self.reset_btn, self.table],
        )

    def _create_action_widget(self, row: dict) -> QWidget:
        """创建结果表每行的查看和下载按钮。"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)
        view_btn = QPushButton("查看")
        download_btn = QPushButton("下载")
        for button in (view_btn, download_btn):
            button.setMinimumWidth(52)
            button.setStyleSheet("font-size: 9px; padding: 2px 8px;")
        view_btn.clicked.connect(lambda checked=False, r=dict(row): self.view_dataset_row(r))
        download_btn.clicked.connect(lambda checked=False, r=dict(row): self.download_dataset_row(r))
        layout.addWidget(view_btn)
        layout.addWidget(download_btn)
        return widget

    def _fill_table(self, rows):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row.get("file_id"),
                "电量" if row.get("data_type") == "excel" else "几何量",
                row.get("device_id"),
                row.get("location"),
                row.get("file_name"),
                "是" if row.get("has_fault") else "否",
                row.get("fault_summary") or "",
                row.get("excel_detail_summary") or "",
                row.get("occurred_at") or row.get("uploaded_at") or "",
                row.get("download_url") or "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem("" if value is None else str(value))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row_index, col, item)
            self.table.setCellWidget(row_index, 10, self._create_action_widget(row))
        self.table.setSortingEnabled(True)
        self.sort_table_by_latest_time(self.table, ("发生时间",))

