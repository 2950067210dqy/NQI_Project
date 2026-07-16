"""服务器消息中心窗口。"""
import json

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QPlainTextEdit
)

from public.entity.BaseWindow import BaseWindow
from public.util.alarm_message_formatter import format_alarm_message


class ServerMessageCenterWindow(BaseWindow):
    """展示状态栏累积的服务器消息，并支持查看详情。"""

    def __init__(self):
        super().__init__()
        self.message_records = []
        self.setWindowTitle("服务器消息中心")
        self.resize(1100, 760)
        self._init_ui()

    def _init_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        top_bar = QHBoxLayout()
        self.summary_label = QLabel("服务器消息: 0 条")
        self.refresh_btn = QPushButton("刷新")
        self.clear_btn = QPushButton("清空消息")
        self.refresh_btn.clicked.connect(self.refresh_messages)
        self.clear_btn.clicked.connect(self.clear_messages)
        top_bar.addWidget(self.summary_label)
        top_bar.addStretch()
        top_bar.addWidget(self.refresh_btn)
        top_bar.addWidget(self.clear_btn)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["时间", "类型", "消息内容"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.show_selected_detail)

        detail_title = QLabel("消息详情")
        self.detail_text = QPlainTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setPlaceholderText("选择一条服务器消息后，这里会显示完整内容和原始详情。")

        root.addLayout(top_bar)
        root.addWidget(self.table)
        root.addWidget(detail_title)
        root.addWidget(self.detail_text)
        self.setCentralWidget(central)
        self.statusBar().showMessage("服务器消息中心就绪")

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_messages()

    def refresh_messages(self):
        """从主窗口状态栏读取最新服务器消息。"""
        status_bar = getattr(self.main_gui, 'status_bar', None)
        if status_bar is None or not hasattr(status_bar, 'get_server_message_records'):
            self.message_records = []
        else:
            self.message_records = status_bar.get_server_message_records()
        self._fill_table()
        self.statusBar().showMessage("服务器消息已刷新")

    def clear_messages(self):
        """清空状态栏中的服务器消息历史。"""
        status_bar = getattr(self.main_gui, 'status_bar', None)
        if status_bar is not None and hasattr(status_bar, 'clear_server_messages'):
            status_bar.clear_server_messages()
        self.message_records = []
        self._fill_table()
        self.detail_text.clear()
        self.statusBar().showMessage("服务器消息已清空")

    def _fill_table(self):
        self.table.setSortingEnabled(False)
        # 消息记录与表格保持相同的最新优先顺序，保证点击详情时仍能对应正确消息。
        self.message_records.sort(key=lambda record: str(record.get('timestamp', '')), reverse=True)
        self.table.setRowCount(len(self.message_records))
        self.summary_label.setText(f"服务器消息: {len(self.message_records)} 条")
        for row_index, record in enumerate(self.message_records):
            values = [
                record.get('timestamp', ''),
                record.get('category', ''),
                self._display_message(record.get('message', ''), record.get('category', '')),
            ]
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col_index == 0:
                    # 行内绑定原始消息，用户改变排序后详情仍与可见行一致。
                    item.setData(Qt.ItemDataRole.UserRole, record)
                if col_index == 1:
                    category = str(value)
                    if category in {'connection_error', 'fault_alarm', 'disconnected'}:
                        item.setForeground(Qt.GlobalColor.red)
                    elif category in {'connected', 'excel_processed', 'image_processed', 'download'}:
                        item.setForeground(Qt.GlobalColor.darkGreen)
                self.table.setItem(row_index, col_index, item)
        self.sort_table_by_latest_time(self.table, ("时间",))
        if self.message_records:
            self.table.selectRow(0)
        else:
            self.detail_text.setPlainText("暂无服务器消息。")


    def _display_message(self, message, category=''):
        """服务器消息展示给用户时，把报警规则码翻译成中文。"""
        if category in {'fault_alarm', 'latest_alarm', 'tip'} or 'alarm' in str(category):
            return format_alarm_message(message)
        text = str(message or '')
        if any(token in text for token in (' gt ', ' lt ', ' ge ', ' le ', 'sheet_', 'max_numeric_value')):
            return format_alarm_message(text)
        return text

    def _display_payload(self, payload):
        """详情中的 message/fault_summary 同步中文化，保留其他原始字段便于排查。"""
        if not isinstance(payload, dict):
            return payload
        display_payload = dict(payload)
        for key in ('message', 'fault_summary', 'error'):
            if key in display_payload and isinstance(display_payload[key], str):
                display_payload[key] = format_alarm_message(display_payload[key])
        return display_payload

    def show_selected_detail(self):
        current_row = self.table.currentRow()
        if current_row < 0 or current_row >= len(self.message_records):
            return
        record_item = self.table.item(current_row, 0)
        record = record_item.data(Qt.ItemDataRole.UserRole) if record_item is not None else None
        if not isinstance(record, dict):
            return
        payload = record.get('payload', {})
        display_message = self._display_message(record.get('message', ''), record.get('category', ''))
        display_payload = self._display_payload(payload)
        payload_text = json.dumps(display_payload, ensure_ascii=False, indent=2) if display_payload else '{}'
        detail = (
            f"时间: {record.get('timestamp', '')}\n"
            f"类型: {record.get('category', '')}\n"
            f"消息: {display_message}\n\n"
            f"详情:\n{payload_text}"
        )
        self.detail_text.setPlainText(detail)

    def _init_customize_ui(self):
        super()._init_customize_ui()

    def _init_function(self):
        pass

    def _init_style_sheet(self):
        pass

    def _init_custom_style_sheet(self):
        pass
