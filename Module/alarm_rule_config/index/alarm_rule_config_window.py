"""上位机预警配置界面。"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QDoubleSpinBox, QCheckBox, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QGroupBox
)
from PyQt6.QtCore import Qt
from loguru import logger

from public.entity.BaseWindow import BaseWindow
from Service.connect_server_service.api.api_client import UpperAPIClient


class AlarmRuleConfigWindow(BaseWindow):
    """查看并编辑服务器上的预警规则。"""

    DATA_TYPES = [("电量数据", "excel"), ("几何量数据", "image"), ("公共规则", "common")]
    COMMON_METRICS = [
        ("文件大小(KB)", "file_size_kb"),
        ("上传错误告警", "upload_error"),
        ("处理失败告警", "processing_failed"),
    ]
    EXCEL_METRICS = [
        ("Excel 全表数值单元格最大值", "max_numeric_value"),
        ("Excel 全表数值单元格最小值", "min_numeric_value"),
        ("Excel 全表数值单元格平均值", "avg_numeric_value"),
        ("电量数值数量", "numeric_value_count"),
        ("电量 Sheet 数", "sheet_count"),
        ("电量图表值数量", "chart_value_count"),
        ("电量误差值数量", "error_value_count"),
        ("功率最大值(W)", "power_w_max"),
        ("功率最小值(W)", "power_w_min"),
        ("功率平均值(W)", "power_w_avg"),
        ("电压最大值", "voltage_max"),
        ("电压最小值", "voltage_min"),
        ("电压平均值", "voltage_avg"),
        ("电流最大值", "current_max"),
        ("电流最小值", "current_min"),
        ("电流平均值", "current_avg"),
        ("相角最大值", "phase_angle_max"),
        ("相角最小值", "phase_angle_min"),
        ("相角平均值", "phase_angle_avg"),
        ("Sheet A 功率最大值(W)", "sheet_A_power_w_max"),
        ("Sheet A 功率最小值(W)", "sheet_A_power_w_min"),
        ("Sheet A 功率平均值(W)", "sheet_A_power_w_avg"),
        ("Sheet A 电压最大值", "sheet_A_voltage_max"),
        ("Sheet A 电压最小值", "sheet_A_voltage_min"),
        ("Sheet A 电压平均值", "sheet_A_voltage_avg"),
        ("Sheet A 电流最大值", "sheet_A_current_max"),
        ("Sheet A 电流最小值", "sheet_A_current_min"),
        ("Sheet A 电流平均值", "sheet_A_current_avg"),
        ("Sheet A 相角最大值", "sheet_A_phase_angle_max"),
        ("Sheet A 相角最小值", "sheet_A_phase_angle_min"),
        ("Sheet A 相角平均值", "sheet_A_phase_angle_avg"),
        ("Sheet B 功率最大值(W)", "sheet_B_power_w_max"),
        ("Sheet B 功率最小值(W)", "sheet_B_power_w_min"),
        ("Sheet B 功率平均值(W)", "sheet_B_power_w_avg"),
        ("Sheet B 电压最大值", "sheet_B_voltage_max"),
        ("Sheet B 电压最小值", "sheet_B_voltage_min"),
        ("Sheet B 电压平均值", "sheet_B_voltage_avg"),
        ("Sheet B 电流最大值", "sheet_B_current_max"),
        ("Sheet B 电流最小值", "sheet_B_current_min"),
        ("Sheet B 电流平均值", "sheet_B_current_avg"),
        ("Sheet B 相角最大值", "sheet_B_phase_angle_max"),
        ("Sheet B 相角最小值", "sheet_B_phase_angle_min"),
        ("Sheet B 相角平均值", "sheet_B_phase_angle_avg"),
        ("Sheet C 功率最大值(W)", "sheet_C_power_w_max"),
        ("Sheet C 功率最小值(W)", "sheet_C_power_w_min"),
        ("Sheet C 功率平均值(W)", "sheet_C_power_w_avg"),
        ("Sheet C 电压最大值", "sheet_C_voltage_max"),
        ("Sheet C 电压最小值", "sheet_C_voltage_min"),
        ("Sheet C 电压平均值", "sheet_C_voltage_avg"),
        ("Sheet C 电流最大值", "sheet_C_current_max"),
        ("Sheet C 电流最小值", "sheet_C_current_min"),
        ("Sheet C 电流平均值", "sheet_C_current_avg"),
        ("Sheet C 相角最大值", "sheet_C_phase_angle_max"),
        ("Sheet C 相角最小值", "sheet_C_phase_angle_min"),
        ("Sheet C 相角平均值", "sheet_C_phase_angle_avg"),
        ("功率误差/%最大绝对值", "power_w_error_percent_abs_max"),
        ("功率误差/ppm最大绝对值", "power_w_error_ppm_abs_max"),
        ("电压误差/%最大绝对值", "voltage_error_percent_abs_max"),
        ("电压误差/ppm最大绝对值", "voltage_error_ppm_abs_max"),
        ("电流误差/%最大绝对值", "current_error_percent_abs_max"),
        ("电流误差/ppm最大绝对值", "current_error_ppm_abs_max"),
        ("相角误差/%最大绝对值", "phase_angle_error_percent_abs_max"),
        ("相角误差/ppm最大绝对值", "phase_angle_error_ppm_abs_max"),
        ("Sheet A 功率误差/%最大绝对值", "sheet_A_power_w_error_percent_abs_max"),
        ("Sheet A 功率误差/ppm最大绝对值", "sheet_A_power_w_error_ppm_abs_max"),
        ("Sheet A 电压误差/%最大绝对值", "sheet_A_voltage_error_percent_abs_max"),
        ("Sheet A 电压误差/ppm最大绝对值", "sheet_A_voltage_error_ppm_abs_max"),
        ("Sheet A 电流误差/%最大绝对值", "sheet_A_current_error_percent_abs_max"),
        ("Sheet A 电流误差/ppm最大绝对值", "sheet_A_current_error_ppm_abs_max"),
        ("Sheet A 相角误差/%最大绝对值", "sheet_A_phase_angle_error_percent_abs_max"),
        ("Sheet A 相角误差/ppm最大绝对值", "sheet_A_phase_angle_error_ppm_abs_max"),
        ("Sheet B 功率误差/%最大绝对值", "sheet_B_power_w_error_percent_abs_max"),
        ("Sheet B 功率误差/ppm最大绝对值", "sheet_B_power_w_error_ppm_abs_max"),
        ("Sheet B 电压误差/%最大绝对值", "sheet_B_voltage_error_percent_abs_max"),
        ("Sheet B 电压误差/ppm最大绝对值", "sheet_B_voltage_error_ppm_abs_max"),
        ("Sheet B 电流误差/%最大绝对值", "sheet_B_current_error_percent_abs_max"),
        ("Sheet B 电流误差/ppm最大绝对值", "sheet_B_current_error_ppm_abs_max"),
        ("Sheet B 相角误差/%最大绝对值", "sheet_B_phase_angle_error_percent_abs_max"),
        ("Sheet B 相角误差/ppm最大绝对值", "sheet_B_phase_angle_error_ppm_abs_max"),
        ("Sheet C 功率误差/%最大绝对值", "sheet_C_power_w_error_percent_abs_max"),
        ("Sheet C 功率误差/ppm最大绝对值", "sheet_C_power_w_error_ppm_abs_max"),
        ("Sheet C 电压误差/%最大绝对值", "sheet_C_voltage_error_percent_abs_max"),
        ("Sheet C 电压误差/ppm最大绝对值", "sheet_C_voltage_error_ppm_abs_max"),
        ("Sheet C 电流误差/%最大绝对值", "sheet_C_current_error_percent_abs_max"),
        ("Sheet C 电流误差/ppm最大绝对值", "sheet_C_current_error_ppm_abs_max"),
        ("Sheet C 相角误差/%最大绝对值", "sheet_C_phase_angle_error_percent_abs_max"),
        ("Sheet C 相角误差/ppm最大绝对值", "sheet_C_phase_angle_error_ppm_abs_max"),
    ]
    IMAGE_METRICS = [
        ("几何量压缩率", "compression_ratio"),
        ("几何量原始大小(KB)", "original_size_kb"),
        ("几何量平均亮度", "mean_brightness"),
        ("几何量亮度标准差", "brightness_std"),
        ("几何量对比度", "contrast_score"),
        ("几何量清晰度", "sharpness_score"),
    ]
    METRICS = COMMON_METRICS + EXCEL_METRICS + IMAGE_METRICS
    OPERATORS = [(">", "gt"), (">=", "ge"), ("<", "lt"), ("<=", "le"), ("=", "eq"), ("!=", "ne"), ("启用即告警", "enabled")]
    SEVERITIES = [("提示", "info"), ("预警", "warning"), ("严重", "critical")]

    def __init__(self):
        super().__init__()
        self.client = self._create_client()
        self.rules = []
        self.current_rule_id = None
        self._loading_rules = False
        self.setWindowTitle("预警配置")
        self.resize(1180, 760)
        self._init_ui()
        self.refresh_rules(show_loading=False)

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

        form_group = QGroupBox("规则编辑")
        form_layout = QFormLayout(form_group)

        self.rule_name_input = QLineEdit()
        self.data_type_combo = QComboBox()
        for text, value in self.DATA_TYPES:
            self.data_type_combo.addItem(text, value)

        self.metric_combo = QComboBox()
        self.data_type_combo.currentIndexChanged.connect(self.on_data_type_changed)
        self._refresh_metric_combo()
        self.metric_combo.currentIndexChanged.connect(self.on_metric_changed)

        self.operator_combo = QComboBox()
        for text, value in self.OPERATORS:
            self.operator_combo.addItem(text, value)

        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(-999999999, 999999999)
        self.threshold_spin.setDecimals(3)
        self.threshold_spin.setValue(0)

        self.severity_combo = QComboBox()
        for text, value in self.SEVERITIES:
            self.severity_combo.addItem(text, value)

        self.enabled_checkbox = QCheckBox("启用规则")
        self.enabled_checkbox.setChecked(True)
        self.description_edit = QTextEdit()
        self.description_edit.setFixedHeight(90)

        form_layout.addRow("规则名称", self.rule_name_input)
        form_layout.addRow("数据类型", self.data_type_combo)
        form_layout.addRow("指标", self.metric_combo)
        form_layout.addRow("比较符", self.operator_combo)
        form_layout.addRow("阈值", self.threshold_spin)
        form_layout.addRow("告警级别", self.severity_combo)
        form_layout.addRow("启用状态", self.enabled_checkbox)
        form_layout.addRow("说明", self.description_edit)

        button_bar = QHBoxLayout()
        self.refresh_btn = QPushButton("刷新规则")
        self.save_btn = QPushButton("保存规则")
        self.new_btn = QPushButton("新建规则")
        self.refresh_btn.clicked.connect(lambda: self.refresh_rules(show_loading=True))
        self.save_btn.clicked.connect(self.save_rule)
        self.new_btn.clicked.connect(self.reset_form)
        button_bar.addWidget(self.refresh_btn)
        button_bar.addWidget(self.save_btn)
        button_bar.addWidget(self.new_btn)
        button_bar.addStretch()

        self.summary_label = QLabel("预警规则加载中")

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(["ID", "规则名称", "数据类型", "指标", "比较符", "阈值", "级别", "启用", "创建时间", "更新时间"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self.load_selected_rule)

        root.addWidget(form_group)
        root.addLayout(button_bar)
        root.addWidget(self.summary_label)
        root.addWidget(self.table)
        self.setCentralWidget(central)
        self.statusBar().showMessage("预警配置就绪")
        self.on_metric_changed()

    def _metrics_for_data_type(self, data_type: str):
        """按当前数据类型返回可配置指标，避免电量规则误选几何量指标。"""
        if data_type == "excel":
            return self.COMMON_METRICS + self.EXCEL_METRICS
        if data_type == "image":
            return self.COMMON_METRICS + self.IMAGE_METRICS
        return self.COMMON_METRICS

    def _refresh_metric_combo(self, selected_metric=None):
        """根据数据类型刷新指标下拉框，并尽量保留当前已选指标。"""
        current_metric = selected_metric if selected_metric is not None else self.metric_combo.currentData()
        self.metric_combo.blockSignals(True)
        self.metric_combo.clear()
        for text, value in self._metrics_for_data_type(self.data_type_combo.currentData()):
            self.metric_combo.addItem(text, value)
        index = self.metric_combo.findData(current_metric)
        self.metric_combo.setCurrentIndex(index if index >= 0 else 0)
        self.metric_combo.blockSignals(False)
        if hasattr(self, "threshold_spin") and hasattr(self, "operator_combo"):
            self.on_metric_changed()

    def on_data_type_changed(self):
        """数据类型变化时同步刷新指标列表。"""
        self._refresh_metric_combo()

    def on_metric_changed(self):
        metric_key = self.metric_combo.currentData()
        is_upload_error = metric_key == "upload_error"
        self.threshold_spin.setEnabled(not is_upload_error)
        if is_upload_error:
            index = self.operator_combo.findData("enabled")
            if index >= 0:
                self.operator_combo.setCurrentIndex(index)

    def refresh_rules(self, show_loading: bool = True):
        """异步从服务器读取预警规则。"""
        if self._loading_rules:
            return
        self._loading_rules = True

        def task():
            return self.client.list_alarm_rules()

        def on_success(result):
            self._loading_rules = False
            self.rules = result.get("rules", [])
            self._fill_table(self.rules)
            self.summary_label.setText(f"共加载 {len(self.rules)} 条预警规则")
            self.statusBar().showMessage("预警规则已刷新")

        def on_error(message):
            self._loading_rules = False
            self.statusBar().showMessage("刷新预警规则失败")
            QMessageBox.critical(self, "刷新失败", message)

        self.run_async_task(
            task,
            on_success=on_success,
            on_error=on_error,
            loading_text="正在加载预警规则...",
            show_loading=show_loading,
            widgets=[self.refresh_btn, self.save_btn, self.new_btn],
        )

    def reset_form(self):
        self.show_loading("正在重置规则表单...")
        self.current_rule_id = None
        self.rule_name_input.clear()
        self.data_type_combo.setCurrentIndex(0)
        self._refresh_metric_combo()
        self.metric_combo.setCurrentIndex(0)
        self.operator_combo.setCurrentIndex(0)
        self.threshold_spin.setValue(0)
        self.enabled_checkbox.setChecked(True)
        self.severity_combo.setCurrentIndex(1)
        self.description_edit.clear()
        self.on_metric_changed()
        self.hide_loading()

    def load_selected_rule(self):
        row = self.table.currentRow()
        if row < 0:
            return
        id_item = self.table.item(row, 0)
        if id_item is None:
            return

        # 表格会按更新时间重新排序，因此规则必须跟随单元格取回，不能再用可变的行号索引原列表。
        rule = id_item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(rule, dict):
            selected_id = id_item.text().strip()
            rule = next(
                (item for item in self.rules if str(item.get("id")) == selected_id),
                None,
            )
        if not rule:
            logger.warning(f"未找到表格所选预警规则: row={row}, id={id_item.text()}")
            return

        self.current_rule_id = rule.get("id")
        self.rule_name_input.setText(rule.get("rule_name") or "")
        self._set_combo_data(self.data_type_combo, rule.get("data_type"))
        self._refresh_metric_combo(rule.get("metric_key"))
        self._set_combo_data(self.metric_combo, rule.get("metric_key"))
        self._set_combo_data(self.operator_combo, rule.get("operator"))
        self._set_combo_data(self.severity_combo, rule.get("severity"))
        self.threshold_spin.setValue(float(rule.get("threshold_value") or 0))
        self.enabled_checkbox.setChecked(bool(rule.get("enabled", True)))
        self.description_edit.setPlainText(rule.get("description") or "")
        self.on_metric_changed()

    def save_rule(self):
        """异步保存当前编辑中的规则到服务器。"""
        payload = {
            "id": self.current_rule_id,
            "rule_name": self.rule_name_input.text().strip() or "未命名规则",
            "data_type": self.data_type_combo.currentData(),
            "metric_key": self.metric_combo.currentData(),
            "operator": self.operator_combo.currentData(),
            "threshold_value": self.threshold_spin.value(),
            "enabled": self.enabled_checkbox.isChecked(),
            "severity": self.severity_combo.currentData(),
            "description": self.description_edit.toPlainText().strip(),
        }
        if payload["metric_key"] == "upload_error":
            payload["operator"] = "enabled"
            payload["threshold_value"] = 1

        def task():
            return self.client.save_alarm_rule(payload)

        def on_success(_):
            self.statusBar().showMessage("预警规则已保存")
            self.refresh_rules(show_loading=False)

        self.run_async_task(
            task,
            on_success=on_success,
            on_error=lambda message: QMessageBox.critical(self, "保存失败", message),
            loading_text="正在保存预警规则...",
            widgets=[self.refresh_btn, self.save_btn, self.new_btn],
        )

    def _set_combo_data(self, combo: QComboBox, value):
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    @classmethod
    def _display_text(cls, value, choices):
        """将服务端原始枚举值转换为界面可读文本。"""
        mapping = {raw: text for text, raw in choices}
        return mapping.get(value, "" if value is None else str(value))

    @staticmethod
    def _format_time(value):
        """把服务端 ISO 时间转成表格里更容易看的格式。"""
        if not value:
            return ""
        text = str(value).replace("T", " ")
        return text[:19]

    def _fill_table(self, rows):
        # 排序会移动表格行；填充期间屏蔽选择信号，避免中间状态回填错误规则。
        self.table.blockSignals(True)
        try:
            self.table.setSortingEnabled(False)
            self.table.clearSelection()
            self.table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                values = [
                    row.get("id"),
                    row.get("rule_name"),
                    self._display_text(row.get("data_type"), self.DATA_TYPES),
                    self._display_text(row.get("metric_key"), self.METRICS),
                    self._display_text(row.get("operator"), self.OPERATORS),
                    row.get("threshold_value"),
                    self._display_text(row.get("severity"), self.SEVERITIES),
                    "是" if row.get("enabled") else "否",
                    self._format_time(row.get("created_at")),
                    self._format_time(row.get("updated_at")),
                ]
                for col, value in enumerate(values):
                    item = QTableWidgetItem("" if value is None else str(value))
                    if col == 0:
                        # UserRole 数据会随单元格一起排序，保证点击行始终对应服务端原规则。
                        item.setData(Qt.ItemDataRole.UserRole, dict(row))
                    if col == 7:
                        item.setForeground(Qt.GlobalColor.darkGreen if row.get("enabled") else Qt.GlobalColor.red)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.table.setItem(row_index, col, item)
            self.sort_table_by_latest_time(self.table, ("更新时间", "创建时间"))
        finally:
            self.table.blockSignals(False)









