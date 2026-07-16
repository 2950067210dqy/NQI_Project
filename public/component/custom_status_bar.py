import time
from datetime import datetime
from collections import deque

from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtWidgets import QStatusBar, QLabel, QProgressBar, QPushButton, QSizePolicy

from public.config_class.global_setting import global_setting
from public.entity.MyQThread import MyQThread
from public.util.alarm_message_formatter import format_alarm_message
from public.entity.enum.Public_Enum import AppState

try:
    from public.function.Cache.data_download_manager import download_manager
except Exception:
    download_manager = None


class Time_thread(MyQThread):
    def __init__(self, update_time_main_signal):
        super(Time_thread, self).__init__(name='time_thread')
        self.update_time_main_signal: pyqtSignal = update_time_main_signal

    def dosomething(self):
        current_time = datetime.now()
        formatted_time = current_time.strftime('%Y-%m-%d %H:%M:%S')
        self.update_time_main_signal.emit(formatted_time)
        time.sleep(1)


class CustomStatusBar(QStatusBar):
    update_time_main_signal_gui_update = pyqtSignal(str)

    def __init__(self, main_gui, is_main=True):
        super().__init__()
        self.main_gui = main_gui
        self.reconnect_btn = None
        self.connection_status_label = None
        self.server_label = None
        self.download_status_label = None
        self.progress_bar = None
        self.time_label = None
        self.app_status_label = None
        self.background_task_label = None
        self.server_message_btn = None
        self.device_status_btn = None
        self.latest_alarm_btn = None
        self.server_messages = deque(maxlen=80)
        self.server_message_records = deque(maxlen=80)
        self.latest_alarm_payload = None
        self._compact_label_widths = {
            'tip': 300,
            'background': 340,
            'server': 300,
            'connection': 150,
        }

        if is_main:
            self.time_label = QLabel()
            self.time_label.setObjectName('time_label')
            self.addWidget(self.time_label)

            self.app_status_label = QLabel('INITIALIZED')
            self.app_status_label.setObjectName('app_status_label')
            self.addWidget(self.app_status_label)

        self.tip_label = QLabel('')
        self._prepare_compact_label(self.tip_label, self._compact_label_widths['tip'])
        self.addWidget(self.tip_label)

        if is_main:
            self.background_task_label = QLabel('后台: 空闲')
            self._prepare_compact_label(self.background_task_label, self._compact_label_widths['background'])
            self.background_task_label.setObjectName('background_task_label')
            self.addWidget(self.background_task_label)

            self.server_label = QLabel('当前未连接服务器')
            self._prepare_compact_label(self.server_label, self._compact_label_widths['server'])
            self.addWidget(self.server_label)

            self.connection_status_label = QLabel('服务器状态: 未连接')
            self._prepare_compact_label(self.connection_status_label, self._compact_label_widths['connection'])
            self.connection_status_label.setStyleSheet('QLabel { color: #b45309; font-weight: bold; }')
            self.addWidget(self.connection_status_label)

            self.server_message_btn = QPushButton('服务器消息(0)')
            self.server_message_btn.setStyleSheet('QPushButton { padding: 4px 10px; }')
            self.server_message_btn.setToolTip('暂无服务器消息')
            self.server_message_btn.clicked.connect(self.show_message_center)
            self.addWidget(self.server_message_btn)

            self.device_status_btn = QPushButton('设备在线: 0/0')
            self.device_status_btn.setStyleSheet('QPushButton { padding: 4px 10px; }')
            self.device_status_btn.setToolTip('点击查看设备在线状态')
            self.device_status_btn.clicked.connect(self.main_gui.open_device_status_page)
            self.addWidget(self.device_status_btn)

            self.latest_alarm_btn = QPushButton('最新预警: 暂无')
            self.latest_alarm_btn.setStyleSheet('QPushButton { padding: 4px 10px; }')
            self.latest_alarm_btn.setToolTip('点击查看预警通知历史')
            self.latest_alarm_btn.clicked.connect(self.open_latest_alarm_page)
            self.addWidget(self.latest_alarm_btn)

            self.reconnect_btn = QPushButton('连接服务器')
            self.reconnect_btn.setStyleSheet('QPushButton { padding: 4px 10px; font-weight: bold; }')
            self.reconnect_btn.clicked.connect(self.main_gui.reconnect_server)
            self.addWidget(self.reconnect_btn)

            self.download_status_label = QLabel('下载: 就绪')
            self.download_status_label.setStyleSheet('QLabel { color: green; font-weight: bold; }')
            self.addWidget(self.download_status_label)

            self.progress_bar = QProgressBar()
            self.progress_bar.setMaximum(100)
            self.progress_bar.setValue(0)

            if download_manager:
                download_manager.excel_data_ready.connect(
                    lambda path, device: self.on_download_completed('电量数据', device),
                    Qt.ConnectionType.QueuedConnection,
                )
                download_manager.image_data_ready.connect(
                    lambda path, device: self.on_download_completed('几何量数据', device),
                    Qt.ConnectionType.QueuedConnection,
                )

        self.tip_btn = QPushButton('教程帮助')
        self.tip_btn.setStyleSheet('QPushButton { font-weight:bolder; font-size: 15px; padding: 5px; }')
        self.tip_btn.clicked.connect(self.main_gui.restart_tutorial)
        # 当前业务界面不显示教程帮助按钮，保留对象供旧代码安全引用。
        self.tip_btn.hide()

        if is_main:
            self.update_time_main_signal_gui_update.connect(self.update_time_function_start_gui_update)
            self.time_thread = Time_thread(update_time_main_signal=self.update_time_main_signal_gui_update)
            self.time_thread.start()

    def _prepare_compact_label(self, label: QLabel, max_width: int):
        """限制状态栏单个文本块宽度，完整内容通过悬浮提示查看。"""
        if label is None:
            return
        label.setMaximumWidth(max_width)
        label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

    def _set_compact_text(self, label: QLabel, text: str, max_width: int):
        """状态栏显示短文本，防止异常详情把状态栏撑变形。"""
        if label is None:
            return
        value = str(text or '')
        label.setToolTip(value)
        metrics = QFontMetrics(label.font())
        display_text = metrics.elidedText(value, Qt.TextElideMode.ElideRight, max(60, max_width - 8))
        label.setText(display_text)

    def update_tip(self, message):
        self._set_compact_text(self.tip_label, message, self._compact_label_widths['tip'])

    def update_background_task(self, message: str):
        self._set_compact_text(
            self.background_task_label,
            f'后台: {message or "空闲"}',
            self._compact_label_widths['background'],
        )

    def update_server_label(self, message):
        self._set_compact_text(self.server_label, message, self._compact_label_widths['server'])

    def update_server_address(self, server_url: str):
        if self.server_label is None:
            return
        if server_url:
            self._set_compact_text(self.server_label, f'服务器地址: {server_url}', self._compact_label_widths['server'])
        else:
            self._set_compact_text(self.server_label, '当前未连接服务器', self._compact_label_widths['server'])

    def update_connection_status(self, status_text: str, connected=None):
        if self.connection_status_label is None or self.reconnect_btn is None:
            return
        if connected is True:
            self.connection_status_label.setStyleSheet('QLabel { color: green; font-weight: bold; }')
            self.reconnect_btn.setText('已连接')
            self.reconnect_btn.setEnabled(False)
        elif connected is False:
            self.connection_status_label.setStyleSheet('QLabel { color: red; font-weight: bold; }')
            self.reconnect_btn.setText('重新连接')
            self.reconnect_btn.setEnabled(True)
        else:
            self.connection_status_label.setStyleSheet('QLabel { color: #b45309; font-weight: bold; }')
            self.reconnect_btn.setText('连接中...')
            self.reconnect_btn.setEnabled(False)
        self._set_compact_text(
            self.connection_status_label,
            f'服务器状态: {status_text}',
            self._compact_label_widths['connection'],
        )

    def append_server_message(self, message: str, category: str = 'info', payload: dict = None):
        """记录最近服务器消息，并提供给服务器消息中心页面使用。"""
        if not message:
            return
        if category in {'fault_alarm', 'latest_alarm'} or any(token in str(message) for token in (' gt ', ' lt ', ' ge ', ' le ', 'sheet_', 'max_numeric_value')):
            message = format_alarm_message(message)
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        line = f'[{timestamp}] {message}'
        self.server_messages.appendleft(line)
        self.server_message_records.appendleft({
            'timestamp': timestamp,
            'category': category or 'info',
            'message': message,
            'payload': payload or {},
        })
        if self.server_message_btn is not None:
            self.server_message_btn.setText(f'服务器消息({len(self.server_messages)})')
            self.server_message_btn.setToolTip('\n'.join(self.server_messages))
        if hasattr(self.main_gui, 'notify_server_message_center_updated'):
            self.main_gui.notify_server_message_center_updated()

    def get_server_message_records(self):
        """返回最近服务器消息的结构化记录。"""
        return list(self.server_message_records)

    def clear_server_messages(self):
        """清空最近服务器消息。"""
        self.server_messages.clear()
        self.server_message_records.clear()
        if self.server_message_btn is not None:
            self.server_message_btn.setText('服务器消息(0)')
            self.server_message_btn.setToolTip('暂无服务器消息')
        self.update_tip('服务器消息已清空')
        if hasattr(self.main_gui, 'notify_server_message_center_updated'):
            self.main_gui.notify_server_message_center_updated()

    def show_message_center(self):
        """打开服务器消息中心页面。"""
        if hasattr(self.main_gui, 'open_server_message_center_page'):
            self.main_gui.open_server_message_center_page()
        elif self.server_messages:
            self.update_tip(self.server_messages[0])
        else:
            self.update_tip('暂无服务器消息')

    def update_device_summary(self, online: int, total: int, detail: str = ''):
        if self.device_status_btn is None:
            return
        self.device_status_btn.setText(f'设备在线: {online}/{total}')
        self.device_status_btn.setToolTip(detail or f'在线设备 {online} 台，总设备 {total} 台')

    def update_latest_alarm(self, message: str, payload: dict = None):
        self.latest_alarm_payload = payload or {}
        if self.latest_alarm_btn is None:
            return
        text = format_alarm_message(message) if message else '暂无'
        short_text = text if len(text) <= 32 else f'{text[:29]}...'
        self.latest_alarm_btn.setText(f'最新预警: {short_text}')
        self.latest_alarm_btn.setToolTip(text)

    def open_latest_alarm_page(self):
        if hasattr(self.main_gui, 'open_notification_history_page'):
            self.main_gui.open_notification_history_page()

    def set_progress(self, value):
        if self.progress_bar is not None:
            self.progress_bar.setValue(value)

    def update_app_state(self):
        if self.app_status_label is None:
            return
        app_state = global_setting.get_setting('app_state', AppState.INITIALIZED)
        self.app_status_label.setText(app_state.value.get('text'))

    def update_time_function_start_gui_update(self, timeStr=''):
        if self.time_label is not None:
            self.time_label.setText(timeStr)

    def on_download_completed(self, data_type: str, device_id: str):
        if self.download_status_label is None:
            return
        message = f'下载: {data_type} (设备{device_id}) ✓'
        self.download_status_label.setText(message)
        self.download_status_label.setStyleSheet('QLabel { color: green; font-weight: bold; }')
        self.append_server_message(message, category='download', payload={'device_id': device_id, 'data_type': data_type})
        QTimer.singleShot(3000, lambda: self.download_status_label.setText('下载: 就绪'))

