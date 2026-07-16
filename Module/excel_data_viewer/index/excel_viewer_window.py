"""
电量数据查看器 - 完整层次结构版本
ExcelDataViewerWindow → device_tabs → device_tab → data_type_tabs → sheet_tabs → 数据类型tabs
"""
import re
import math
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field

import pandas as pd
from PyQt6.QtCore import pyqtSignal, Qt, QDate, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QGroupBox, QComboBox, QDateEdit, QListWidget, QListWidgetItem,
    QTableWidget, QTableWidgetItem, QPlainTextEdit, QHeaderView, QFileDialog, QMessageBox,
    QProgressBar, QApplication
)
from loguru import logger
import matplotlib
# 上位机使用 PyQt6，打包后必须使用通用 QtAgg 后端，避免 Qt5Agg 触发 PyQt5 后端导入失败。
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

from Service.connect_server_service.index.Client_server import Client_server
from theme.ThemeQt6 import ThemedWindow
from public.entity.MyQThread import MyQThread
from public.config_class.global_setting import global_setting
from public.function.Cache.cache_manager import cache_manager
from public.function.Cache.data_download_manager import download_manager
from public.util.alarm_message_formatter import format_alarm_message


# ==================== 数据结构 ====================
@dataclass
class xlsx_datas_device_item:
    name: str = ""
    data: list = field(default_factory=list)


@dataclass
class xlsx_datas_phase_item:
    name: str = ""
    data: list = field(default_factory=list)


@dataclass
class xlsx_datas_item_x:
    name: list = field(default_factory=list)
    data: list = field(default_factory=list)


@dataclass
class xlsx_datas_item:
    x: xlsx_datas_item_x = field(default_factory=xlsx_datas_item_x)
    y: list = field(default_factory=list)


@dataclass
class xlsx_datas_type_item:
    name: str = ""
    data: xlsx_datas_item = field(default_factory=xlsx_datas_item)


@dataclass
class xlsx_data:
    rated_voltage: float = 0
    rated_voltage_unit: str = ''
    rated_frequency: float = 0
    rated_frequency_unit: str = ''
    name: str = ""
    data: list = field(default_factory=list)


# ==================== 线程 ====================
class ExcelViewerQueueThread(MyQThread):
    """队列监听线程 - 监听跨进程消息"""
    def __init__(self, name, window):
        super().__init__(name)
        self.queue = None
        self.window = window
    
    def dosomething(self):
        """监听队列消息"""
        if not self.queue.empty():
            try:
                from public.entity.queue.ObjectQueueItem import ObjectQueueItem
                message: ObjectQueueItem = self.queue.get()
                if message and not message.is_Empty():
                    logger.critical(f"{self.name}:{message}")
                    if isinstance(message, ObjectQueueItem) and message.to == 'excel_data_viewer':
                        if message.title == 'cache_data_ready' and message.data:
                            # 收到缓存数据就绪通知（来自下载管理器）
                            file_path = message.data.get('file_path')
                            device_id = message.data.get('device_id')
                            if file_path and device_id:
                                # 通过信号发送到主线程（避免子线程直接操作UI）
                                self.window.cache_update_signal.emit(file_path, device_id)
                                logger.info(f"[队列线程] 已发送更新信号到主线程: {file_path}")
                    else:
                        # 把消息放回去
                        self.queue.put(message)
            except Exception as e:
                logger.error(f"[队列线程] 处理消息错误: {e}")


# ==================== 主窗口 ====================
class ExcelDataViewerWindow(ThemedWindow):
    update_data_signal = pyqtSignal(dict)
    cache_update_signal = pyqtSignal(str, str)  # file_path, device_id - 从队列线程发送到主线程
    
    def __init__(self, parent=None):
        super().__init__()
        self.setWindowTitle("电量数据查看器")
        self.resize(1400, 900)
        # 数据存储
        self.device_data = {}  # {device_id: {sheet_name: xlsx_data}}
        self.device_tab_dict = {}  # {device_id: device_tab_widget}
        self.history_data = []
        
        # 窗口状态
        self.is_visible = False  # 窗口是否可见
        
        # UI组件
        self.log_text = None  # 日志文本框（稍后创建）
        self.realtime_loading_bar = None  # 实时数据页加载条
        self.realtime_loading_label = None
        self._realtime_loading_count = 0
        
        # 服务端连接
        self.server_client: Client_server = None
        self.active_threads = []
        self.cache_bootstrap_started = False
        self.history_cache_loaded = False
        self.latest_cache_loaded = False
        self.pending_server_update = False  # 窗口未显示时收到服务端同步通知，只记录，等显示后再刷新 UI。
        self.pending_server_device_id = None
        self.displayed_excel_file_ids = set()  # 记录实时页已显示的电量文件，避免处理完成通知重复刷新同一条。
        
        # 初始化UI
        self.init_ui()
        
        # 队列监听
        self.queue_thread = ExcelViewerQueueThread("excel_queue", self)
        queue = global_setting.get_setting("queue", None)
        if queue:
            self.queue_thread.queue = queue
            # 跨进程消息由主窗口统一分发，避免多个线程争抢同一队列。
        
        # 连接缓存更新信号（从队列线程到主线程）
        self.cache_update_signal.connect(
            self.on_cache_data_ready,
            Qt.ConnectionType.QueuedConnection
        )
        # 启动阶段不阻塞主界面；缓存改为在页面显示后后台加载。
        self.report_background_task('主界面已显示，等待加载服务器电量数据')
    
    def init_ui(self):
        """初始化UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 状态栏
        status_layout = QHBoxLayout()
        self.status_label = QLabel("状态: 等待数据...")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        layout.addLayout(status_layout)
        
        # 主选项卡
        self.main_tabs = QTabWidget()
        self.main_tabs.addTab(self.create_realtime_tab(), "实时数据")
        self.main_tabs.addTab(self.create_history_tab(), "历史数据")
        self.main_tabs.addTab(self.create_cache_table_tab(), "服务器数据")
        self.main_tabs.addTab(self.create_trend_chart_tab(), "数据趋势")
        self.main_tabs.addTab(self.create_log_tab(), "日志")
        layout.addWidget(self.main_tabs)
    def showEvent(self, event):
        """窗口显示事件"""
        super().showEvent(event)
        self.is_visible = True
        logger.info("电量数据查看器窗口已显示")
        if not self.cache_bootstrap_started:
            self.cache_bootstrap_started = True
            self.report_background_task('正在从服务器加载电量解析结果')
            QTimer.singleShot(120, self.bootstrap_cache_load)
        elif self.pending_server_update:
            # 启动阶段页面未显示时可能已经收到同步消息；显示后再刷新，避免隐藏窗口操作 Qt/Matplotlib。
            self.pending_server_update = False
            QTimer.singleShot(120, lambda: self.on_cache_data_ready('server_record', self.pending_server_device_id or ''))

    def hideEvent(self, event):
        """窗口隐藏事件"""
        super().hideEvent(event)
        self.is_visible = False
        logger.info("电量数据查看器窗口隐藏")

    def report_background_task(self, message: str):
        """把电量页面后台任务同步到主窗口状态栏。"""
        try:
            if self.main_gui is not None and getattr(self.main_gui, 'status_bar', None) is not None:
                self.main_gui.status_bar.update_background_task(message)
        except Exception:
            pass

    def _begin_realtime_loading(self, text: str = "正在加载电量实时数据..."):
        """显示实时数据页内加载条；服务器请求可能较慢，先让界面给出明确反馈。"""
        self._realtime_loading_count += 1
        if self.realtime_loading_label is not None:
            self.realtime_loading_label.setText(text)
            self.realtime_loading_label.setVisible(True)
        if self.realtime_loading_bar is not None:
            self.realtime_loading_bar.setRange(0, 0)
            self.realtime_loading_bar.setVisible(True)
        QApplication.processEvents()

    def _end_realtime_loading(self):
        """隐藏实时数据页内加载条，支持嵌套加载调用。"""
        if self._realtime_loading_count > 0:
            self._realtime_loading_count -= 1
        if self._realtime_loading_count > 0:
            return
        if self.realtime_loading_label is not None:
            self.realtime_loading_label.setVisible(False)
        if self.realtime_loading_bar is not None:
            self.realtime_loading_bar.setVisible(False)

    def _get_api_client(self):
        """返回页面用于读取服务器解析结果的 API 客户端。"""
        return getattr(self.server_client, 'client', None) if self.server_client else None

    def _fetch_excel_records(self, device_id: str = None, limit: int = 100):
        """直接从服务端读取电量记录列表。"""
        api = self._get_api_client()
        if api is None:
            return []
        response = api.list_excel_data(device_id=device_id, limit=limit, skip=0) or {}
        return list(response.get('data', []))

    def _fetch_excel_detail(self, file_id: int):
        """读取包含 parsed_data 的完整电量记录。"""
        api = self._get_api_client()
        if api is None:
            return None
        response = api.get_excel_detail(file_id) or {}
        return response.get('data')

    def _normalize_excel_record(self, record: dict) -> dict:
        """统一列表/详情记录结构。"""
        record = record or {}
        parse_result = record.get('parse_result') or {}
        upload_time = record.get('upload_time') or ''
        alarm_info = record.get('alarm_info') or {}
        if not alarm_info.get('has_alarm') and record.get('fault_summary'):
            # 兼容旧服务端/旧列表接口：没有 alarm_info 时，用搜索索引的 fault_summary 兜底展示。
            alarm_info = {
                'has_alarm': True,
                'severity': record.get('severity') or 'warning',
                'status': record.get('fault_status') or 'open',
                'message': record.get('fault_summary'),
                'created_at': record.get('occurred_at') or upload_time,
            }
        return {
            'device_id': record.get('device_id', ''),
            'file_id': record.get('id') or record.get('file_id'),
            'file_name': record.get('file_name', ''),
            'file_path': record.get('file_path', ''),
            'timestamp': upload_time.replace('T', ' ')[:19] if upload_time else '',
            'upload_time': upload_time,
            'parse_result': parse_result,
            'sheet_count': parse_result.get('sheet_count', 0),
            'rated_voltage': parse_result.get('rated_voltage', 0),
            'rated_voltage_unit': parse_result.get('rated_voltage_unit', ''),
            'rated_frequency': parse_result.get('rated_frequency', 0),
            'rated_frequency_unit': parse_result.get('rated_frequency_unit', ''),
            'processing_status': record.get('processing_status', ''),
            'processing_error': record.get('processing_error'),
            'alarm_info': alarm_info,
        }

    def _format_alarm_text(self, alarm_info: dict) -> str:
        """把服务端预警结构转换为适合表格和详情页显示的中文文本。"""
        alarm_info = alarm_info or {}
        if not alarm_info.get('has_alarm'):
            return "无预警"
        severity_map = {"critical": "严重", "warning": "预警", "info": "提示"}
        severity = severity_map.get(alarm_info.get('severity'), alarm_info.get('severity') or "预警")
        # 兼容历史报警记录：服务端旧数据里可能还保留 gt/sheet_a_power_max 等内部字段名。
        message = format_alarm_message(alarm_info.get('message') or "检测到预警")
        created_at = (alarm_info.get('created_at') or '').replace('T', ' ')[:19]
        return f"[{severity}] {created_at} {message}".strip()

    def _make_alarm_table_item(self, alarm_info: dict) -> QTableWidgetItem:
        """创建预警单元格；有预警时用醒目颜色并保留完整 tooltip。"""
        text = self._format_alarm_text(alarm_info)
        item = QTableWidgetItem(text)
        item.setToolTip(text)
        if (alarm_info or {}).get('has_alarm'):
            item.setForeground(Qt.GlobalColor.red)
        return item

    def _pick_preferred_excel_record(self, records: list):
        """优先选取服务端已完成解析的记录。"""
        for record in records:
            if record.get('processing_status') == 'done':
                return record
        return records[0] if records else None

    def _download_excel_record(self, record: dict):
        """Download one Excel record to a user-selected folder."""
        api = self._get_api_client()
        normalized = self._normalize_excel_record(record)
        if api is None or not normalized.get("file_id"):
            QMessageBox.warning(self, "下载失败", "当前未连接到服务器。")
            self.log_message("下载失败: 当前未连接到服务器")
            return
        target_dir = QFileDialog.getExistingDirectory(
            self,
            "选择下载目录",
            str(Path.home() / "Downloads")
        )
        if not target_dir:
            return
        save_path = Path(target_dir) / normalized.get("file_name", f"excel_{normalized['file_id']}.xlsx")

        def task():
            api.download_excel_file(int(normalized["file_id"]), save_path)
            return save_path

        def on_success(downloaded_path: Path):
            self.status_label.setText(f"状态: 已下载 - {normalized.get('file_name', '')}")
            self.log_message(f"Excel 文件已下载: {downloaded_path}")

        self.run_async_task(
            task,
            on_success=on_success,
            on_error=lambda message: QMessageBox.critical(self, "下载失败", message),
            loading_text=f"正在下载 {normalized.get('file_name', '')}...",
            widgets=[getattr(self, "cache_table", None)],
        )

    def _load_excel_record_into_ui(self, record: dict, switch_to_realtime: bool = True) -> bool:
        """Safely load one server Excel record into the realtime tab."""
        try:
            normalized = self._normalize_excel_record(record)
            if not normalized.get("file_id"):
                return False
            if normalized.get("processing_status") != "done":
                self.status_label.setText(f"状态: 等待服务端解析 - {normalized.get('device_id', '')}")
                self.log_message(f"文件仍在服务端处理中: {normalized.get('file_name', '')}")
                return False
            parse_result = record.get("parse_result") or {}
            parsed_data = parse_result.get("parsed_data") if isinstance(parse_result, dict) else None
            # 列表接口只返回解析摘要，不返回完整 parsed_data；实时页必须补取详情才能渲染表格。
            detail = record if parsed_data else (self._fetch_excel_detail(int(normalized["file_id"])) or record)
            sheet_data_dict = self.build_sheet_data_dict_from_record(detail)
            if not sheet_data_dict:
                self.log_message(f"服务端未返回可显示的解析结果: {normalized.get('file_name', '')}")
                return False
            self.device_data[normalized["device_id"]] = sheet_data_dict
            detail_alarm_info = (detail or {}).get("alarm_info") or normalized.get("alarm_info") or {}
            self.create_or_update_device_tab(normalized["device_id"], sheet_data_dict, normalized.get("file_name"), detail_alarm_info)
            self.displayed_excel_file_ids.add(int(normalized["file_id"]))
            if switch_to_realtime and hasattr(self, "main_tabs") and self.main_tabs.count() > 0:
                self.main_tabs.setCurrentIndex(0)
            return True
        except Exception as exc:
            logger.error(f"加载电量实时数据失败: {exc}")
            self.log_message(f"加载电量实时数据失败: {exc}")
            return False


    def bootstrap_cache_load(self):
        """Load page data and keep a visible loading mask during startup refresh."""
        self.show_loading("正在加载电量数据...")
        QTimer.singleShot(20000, self.hide_loading)
        try:
            self.load_latest_from_cache()
            self.load_history_from_cache()
            self.load_cache_data_to_table(show_loading=False)
            self.refresh_trend_chart()
            self.report_background_task("电量数据加载完成")
        except Exception as exc:
            logger.error(f"Excel server data load failed: {exc}")
            self.report_background_task(f"电量数据加载失败: {exc}")
        finally:
            self.hide_loading()



    def create_realtime_tab(self):
        """创建实时数据选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        loading_layout = QHBoxLayout()
        self.realtime_loading_label = QLabel("正在加载电量实时数据...")
        self.realtime_loading_label.setStyleSheet("color: #1565c0; font-weight: bold;")
        self.realtime_loading_bar = QProgressBar()
        self.realtime_loading_bar.setRange(0, 0)
        self.realtime_loading_bar.setFixedHeight(16)
        self.realtime_loading_label.setVisible(False)
        self.realtime_loading_bar.setVisible(False)
        loading_layout.addWidget(self.realtime_loading_label)
        loading_layout.addWidget(self.realtime_loading_bar, 1)
        layout.addLayout(loading_layout)

        # 设备选项卡（第一层）
        self.device_tabs = QTabWidget()

        # 占位符
        placeholder = QWidget()
        placeholder_layout = QVBoxLayout(placeholder)
        placeholder_layout.addWidget(QLabel("等待数据..."))
        self.device_tabs.addTab(placeholder, "无设备")

        layout.addWidget(self.device_tabs)
        return tab


    def create_history_tab(self):
        """创建历史数据选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 筛选
        filter_group = QGroupBox("筛选条件")
        filter_layout = QHBoxLayout(filter_group)

        filter_layout.addWidget(QLabel("设备:"))
        self.history_device_combo = QComboBox()
        self.history_device_combo.addItem("全部设备")
        filter_layout.addWidget(self.history_device_combo)

        filter_layout.addWidget(QLabel("开始日期:"))
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate().addDays(-7))
        filter_layout.addWidget(self.start_date)

        filter_layout.addWidget(QLabel("结束日期:"))
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        filter_layout.addWidget(self.end_date)

        filter_btn = QPushButton("查询")
        filter_btn.clicked.connect(self.load_history_data)
        filter_layout.addWidget(filter_btn)
        filter_layout.addStretch()

        layout.addWidget(filter_group)

        # 历史列表
        self.history_list = QListWidget()
        self.history_list.itemClicked.connect(self.on_history_item_clicked)
        layout.addWidget(self.history_list)

        # 历史显示
        self.history_display_tabs = QTabWidget()
        layout.addWidget(self.history_display_tabs)

        return tab

    def on_cache_data_ready(self, file_path: str, device_id: str):
        """收到新数据通知后，直接回源服务端读取最新解析结果。"""
        logger.info(f"[电量数据页面] 收到服务端数据通知: {Path(file_path).name if file_path else 'server_record'}, 设备: {device_id}")
        if not self.is_visible:
            # 模块启动时窗口尚未显示，不能在隐藏页面里刷新复杂 Qt/Matplotlib 组件，否则可能触发原生崩溃。
            self.pending_server_update = True
            self.pending_server_device_id = device_id
            logger.info("[电量数据页面] 页面未显示，已延迟本次服务端数据刷新")
            return
        self.log_message(f"收到新数据通知: 设备 {device_id}")
        self._begin_realtime_loading("正在加载最新电量实时数据...")
        try:
            records = self._fetch_excel_records(device_id=device_id, limit=20)
            latest = self._pick_preferred_excel_record(records)
            if latest and self._load_excel_record_into_ui(latest):
                self.load_history_from_cache()
                self.load_cache_data_to_table()
                self.refresh_trend_chart()
            else:
                self.log_message("电量数据已上传，等待服务端解析完成后自动显示。")
        finally:
            self._end_realtime_loading()


    def parse_excel_all_sheets(self, file_path: str) -> dict:
        """
        解析Excel所有Sheet
        返回: {sheet_name: xlsx_data}
        """
        logger.info(f"解析Excel: {file_path}")

        try:
            excel_file = pd.ExcelFile(file_path)
            result = {}

            for sheet_name in excel_file.sheet_names:
                logger.info(f"解析Sheet: {sheet_name}")
                df = excel_file.parse(sheet_name, header=None)
                sheet_data = self.parse_single_sheet(df, sheet_name)

                if sheet_data:
                    result[sheet_name] = sheet_data
                    logger.info(f"✅ {sheet_name} 解析成功")

            logger.info(f"✅ 共解析{len(result)}个Sheet")
            return result

        except Exception as e:
            import traceback
            logger.error(f"解析失败: {e}\n{traceback.format_exc()}")
            return {}


    def parse_single_sheet(self, data, sheet_name: str) -> xlsx_data:
        """解析单个Sheet（保留旧逻辑，兼容历史本地缓存）。"""
        try:
            data_each_counts = 36
            return_data = xlsx_data()
            return_data.name = sheet_name

            data_clean = data.dropna()
            if data_clean.empty:
                return None

            df_colum_0_unique = data_clean.drop_duplicates(subset=[data_clean.columns[0]])
            df_colum_1_unique = data_clean.drop_duplicates(subset=[data_clean.columns[1]])

            return_data.rated_frequency = float("".join(re.findall(r'[0-9]', str(df_colum_1_unique.iloc[0, 1]))))
            return_data.rated_frequency_unit = "".join(re.findall(r'[A-Za-z]', str(df_colum_1_unique.iloc[0, 1])))
            return_data.rated_voltage = float("".join(re.findall(r'[0-9]', str(df_colum_0_unique.iloc[0, 0]).split(",")[0])))
            return_data.rated_voltage_unit = "".join(re.findall(r'[A-Za-z]', str(df_colum_0_unique.iloc[0, 0]).split(",")[0]))

            xlsx_datas_type_item_obj_x_data = []
            for row in range(data_clean.shape[0]):
                temp = row / data_each_counts
                index = math.floor(temp)

                if temp == 0:
                    xlsx_datas_type_item_obj = xlsx_datas_type_item()
                    xlsx_datas_type_item_obj.name = "功率W"
                    xlsx_datas_type_item_obj.data.x.name.append(str(data.iloc[3, 2]))
                    xlsx_datas_type_item_obj.data.x.name.append("电流/A")
                    return_data.data.append(xlsx_datas_type_item_obj)
                elif temp == 1:
                    xlsx_datas_type_item_obj = xlsx_datas_type_item()
                    xlsx_datas_type_item_obj.name = "电压"
                    xlsx_datas_type_item_obj.data.x.name.append(str(data.iloc[3, 2]))
                    xlsx_datas_type_item_obj.data.x.name.append("电流/A")
                    return_data.data.append(xlsx_datas_type_item_obj)
                    return_data.data[index - 1].data.x.data = xlsx_datas_type_item_obj_x_data
                    xlsx_datas_type_item_obj_x_data = []
                elif temp == 2:
                    xlsx_datas_type_item_obj = xlsx_datas_type_item()
                    xlsx_datas_type_item_obj.name = "电流"
                    xlsx_datas_type_item_obj.data.x.name.append(str(data.iloc[3, 2]))
                    xlsx_datas_type_item_obj.data.x.name.append("电流/A")
                    return_data.data.append(xlsx_datas_type_item_obj)
                    return_data.data[index - 1].data.x.data = xlsx_datas_type_item_obj_x_data
                    xlsx_datas_type_item_obj_x_data = []
                elif temp == 3:
                    xlsx_datas_type_item_obj = xlsx_datas_type_item()
                    xlsx_datas_type_item_obj.name = "相角"
                    xlsx_datas_type_item_obj.data.x.name.append(str(data.iloc[3, 2]))
                    xlsx_datas_type_item_obj.data.x.name.append("电流/A")
                    return_data.data.append(xlsx_datas_type_item_obj)
                    return_data.data[index - 1].data.x.data = xlsx_datas_type_item_obj_x_data
                    xlsx_datas_type_item_obj_x_data = []

                rated_current_unit = "".join(re.findall(r'[A-Za-z]', str(data_clean.iloc[row, 0]).strip().split(",")[1]))
                if rated_current_unit == "mA":
                    rated_current = float("".join(re.findall(r'[0-9]', str(data_clean.iloc[row, 0]).strip().split(",")[1]))) / 1000
                else:
                    rated_current = float("".join(re.findall(r'[0-9]', str(data_clean.iloc[row, 0]).strip().split(",")[1])))

                xlsx_datas_type_item_obj_x_data.append([data_clean.iloc[row, 2], rated_current])

            return_data.data[-1].data.x.data = xlsx_datas_type_item_obj_x_data

            df_rows_2_4_unique = data.iloc[3, 4:].dropna()
            df_rows_3_4 = data.iloc[4, 4:]

            for row in range(data_clean.shape[0]):
                temp = row / data_each_counts
                index = math.floor(temp)
                if temp == 0 or temp == 1 or temp == 2 or temp == 3:
                    for j in range(df_rows_2_4_unique.shape[0]):
                        xlsx_datas_phase_item_obj = xlsx_datas_phase_item()
                        xlsx_datas_phase_item_obj.name = df_rows_2_4_unique.iloc[j]

                        device_series = df_rows_3_4.drop_duplicates()[:-2]
                        for device_row in range(device_series.shape[0]):
                            xlsx_datas_device_item_obj = xlsx_datas_device_item()
                            xlsx_datas_device_item_obj.name = device_series.iloc[device_row]
                            xlsx_datas_phase_item_obj.data.append(xlsx_datas_device_item_obj)

                        return_data.data[index].data.y.append(xlsx_datas_phase_item_obj)

            for row in range(data_clean.shape[0]):
                temp = row / data_each_counts
                index = math.floor(temp)

                for j in range(df_rows_2_4_unique.shape[0]):
                    device_series = df_rows_3_4.drop_duplicates()[:-2]
                    for device_row in range(device_series.shape[0]):
                        return_data.data[index].data.y[j].data[device_row].data.append(
                            data_clean.iloc[row, int(df_rows_2_4_unique.index[j]) + device_row])

            return return_data
        except Exception as e:
            logger.error(f"解析Sheet失败: {e}")
            return None


    def deserialize_sheet_data_dict(self, parsed_data_dict: dict) -> dict:
        """把服务端返回的字典结构还原成页面原本使用的数据对象。"""
        result = {}
        for sheet_name, payload in (parsed_data_dict or {}).items():
            sheet = xlsx_data()
            sheet.name = payload.get('name', sheet_name)
            sheet.rated_voltage = payload.get('rated_voltage', 0)
            sheet.rated_voltage_unit = payload.get('rated_voltage_unit', '')
            sheet.rated_frequency = payload.get('rated_frequency', 0)
            sheet.rated_frequency_unit = payload.get('rated_frequency_unit', '')

            for type_payload in payload.get('data', []):
                type_item = xlsx_datas_type_item()
                type_item.name = type_payload.get('name', '')
                x_payload = type_payload.get('data', {}).get('x', {})
                type_item.data.x.name = list(x_payload.get('name', []))
                type_item.data.x.data = list(x_payload.get('data', []))

                for phase_payload in type_payload.get('data', {}).get('y', []):
                    phase_item = xlsx_datas_phase_item()
                    phase_item.name = phase_payload.get('name', '')
                    for device_payload in phase_payload.get('data', []):
                        device_item = xlsx_datas_device_item()
                        device_item.name = device_payload.get('name', '')
                        device_item.data = list(device_payload.get('data', []))
                        phase_item.data.append(device_item)
                    type_item.data.y.append(phase_item)

                sheet.data.append(type_item)
            result[sheet_name] = sheet
        return result

    def build_sheet_data_dict_from_record(self, record: dict) -> dict:
        """优先使用服务端解析结果，仅在本地路径可访问时回退本地解析。"""
        parse_result = record.get('parse_result') or {}
        extra_data = record.get('extra_data') or {}
        if not parse_result and isinstance(extra_data, dict):
            parse_result = extra_data.get('parse_result', {})
        parsed_data = parse_result.get('parsed_data') if isinstance(parse_result, dict) else None
        if parsed_data:
            return self.deserialize_sheet_data_dict(parsed_data)
        file_path = record.get('file_path', '')
        if file_path and Path(file_path).exists():
            return self.parse_excel_all_sheets(file_path)
        return {}


    def create_or_update_device_tab(self, device_id: str, sheet_data_dict: dict, file_name: str = None, alarm_info: dict = None):
        """创建或更新设备选项卡"""
        logger.info(f"创建设备选项卡: {device_id}")

        # 移除占位符
        if self.device_tabs.count() == 1 and self.device_tabs.tabText(0) == "无设备":
            self.device_tabs.removeTab(0)

        # 如果设备已存在，移除旧的
        if device_id in self.device_tab_dict:
            old_widget = self.device_tab_dict[device_id]
            index = self.device_tabs.indexOf(old_widget)
            if index >= 0:
                self.device_tabs.removeTab(index)

        # 创建新的设备选项卡
        device_tab = self.create_device_tab_content(device_id, sheet_data_dict, file_name, alarm_info)
        self.device_tabs.addTab(device_tab, f"设备 {device_id}")
        self.device_tab_dict[device_id] = device_tab

        # 切换到新选项卡
        self.device_tabs.setCurrentWidget(device_tab)
        self.main_tabs.setCurrentIndex(0)

        logger.info(f"✅ 设备选项卡创建完成")


    def create_device_tab_content(self, device_id: str, sheet_data_dict: dict, file_name: str = None, alarm_info: dict = None) -> QWidget:
        """
        创建设备选项卡内容
        层次：device_tab → data_type_tabs → sheet_tabs → 数据类型tabs
        """
        device_tab = QWidget()
        layout = QVBoxLayout(device_tab)

        # 设备信息
        info_group = QGroupBox("设备信息")
        info_layout = QVBoxLayout(info_group)

        first_sheet = list(sheet_data_dict.values())[0]
        info_layout.addWidget(QLabel(f"设备ID: {device_id}"))

        # 显示文件名（如果有）
        if file_name:
            file_label = QLabel(f"文件名: {file_name}")
            file_label.setStyleSheet("color: #0066cc; font-weight: bold;")
            info_layout.addWidget(file_label)

        info_layout.addWidget(QLabel(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"))
        # 数据文件已经触发预警时，在图表详情顶部同步展示完整预警摘要。
        if (alarm_info or {}).get('has_alarm'):
            alarm_label = QLabel(f"预警信息: {self._format_alarm_text(alarm_info)}")
            alarm_label.setWordWrap(True)
            alarm_label.setStyleSheet("color: #c62828; font-weight: bold;")
            info_layout.addWidget(alarm_label)
        info_layout.addWidget(QLabel(f"额定电压: {first_sheet.rated_voltage}{first_sheet.rated_voltage_unit}"))
        info_layout.addWidget(QLabel(f"额定频率: {first_sheet.rated_frequency}{first_sheet.rated_frequency_unit}"))
        layout.addWidget(info_group)

        # 数据类型选项卡（第二层）
        data_type_tabs = QTabWidget()

        # 为每个数据类型创建选项卡
        data_types = ["功率W", "电压", "电流", "相角"]
        for data_type_name in data_types:
            # Sheet选项卡（第三层）
            sheet_tabs = QTabWidget()

            # 为每个Sheet创建选项卡
            for sheet_name, sheet_data in sheet_data_dict.items():
                # 找到对应的数据类型
                data_type_item = None
                for item in sheet_data.data:
                    if item.name == data_type_name:
                        data_type_item = item
                        break

                if data_type_item:
                    # 创建图表
                    chart_widget = self.create_chart_widget(sheet_name, data_type_item)
                    sheet_tabs.addTab(chart_widget, f"Sheet {sheet_name}")

            data_type_tabs.addTab(sheet_tabs, data_type_name)

        layout.addWidget(data_type_tabs)

        # 保存引用
        device_tab.data_type_tabs = data_type_tabs
        device_tab.device_id = device_id

        return device_tab


    def create_chart_widget(self, sheet_name: str, data_type_item: xlsx_datas_type_item) -> QWidget:
        """创建图表Widget - 堆叠柱状图"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        fig = Figure(figsize=(14, 6))
        ax = fig.add_subplot(111)

        try:
            x_data = data_type_item.data.x.data
            y_data = data_type_item.data.y

            if x_data and y_data:
                # X轴标签（相角°和电流A）
                x_labels = [f"{x[0]:.1f}°\n{x[1]:.2f}A" for x in x_data]
                x_pos = range(len(x_labels))

                # ✅ 颜色方案：A/B/C相不同色系
                phase_colors = {
                    'A': ['#D32F2F', '#EF5350'],  # 红色系：设备1深，设备2浅
                    'B': ['#00897B', '#4DB6AC'],  # 青色系：设备1深，设备2浅
                    'C': ['#1976D2', '#64B5F6'],  # 蓝色系：设备1深，设备2浅
                }

                # ✅ 堆叠柱状图：每个相位一根柱子，设备堆叠显示
                bar_width = 0.25
                num_phases = len(y_data)

                # 为每个相位（A/B/C）绘制堆叠柱状图
                for phase_idx, phase_item in enumerate(y_data):
                    phase_name = phase_item.name

                    # 获取相位对应的颜色
                    if 'A' in phase_name:
                        colors = phase_colors['A']
                    elif 'B' in phase_name:
                        colors = phase_colors['B']
                    elif 'C' in phase_name:
                        colors = phase_colors['C']
                    else:
                        colors = ['#999999', '#CCCCCC']

                    # 计算柱子位置偏移
                    offset = (phase_idx - (num_phases - 1) / 2) * bar_width

                    # 堆叠绘制该相位的所有设备
                    bottom_values = None
                    for device_idx, device_item in enumerate(phase_item.data):
                        device_data = device_item.data
                        color = colors[device_idx % len(colors)]

                        # 绘制堆叠柱状图
                        ax.bar([x + offset for x in x_pos], 
                              device_data, 
                              bar_width,
                              bottom=bottom_values,
                              label=f"{phase_item.name}-{device_item.name}",
                              color=color,
                              alpha=0.85,
                              edgecolor='white',
                              linewidth=0.5)

                        # 更新底部值（用于堆叠）
                        if bottom_values is None:
                            bottom_values = device_data[:]
                        else:
                            bottom_values = [bottom_values[i] + device_data[i] for i in range(len(device_data))]
                # 设置刻度旋转45度
                ax.tick_params(axis='x', rotation=45)
                ax.set_xlabel('相角 (°) 和 电流 (A)', fontsize=9, fontweight='bold')
                ax.set_ylabel(data_type_item.name, fontsize=11, fontweight='bold')
                ax.set_title(f"{sheet_name} - {data_type_item.name}", fontsize=12, fontweight='bold')
                ax.set_xticks(x_pos)
                ax.set_xticklabels(x_labels, fontsize=7)

                # ✅ 图例放在图的外面（右侧），不遮挡图表
                ax.legend(loc='upper left', 
                         bbox_to_anchor=(1.02, 1), 
                         borderaxespad=0, 
                         frameon=True, 
                         fontsize=9,
                         title='相位-设备',
                         title_fontsize=10)

                ax.grid(True, alpha=0.3, linestyle='--', axis='y')

                # ✅ 调整布局，留出空间给图例
                fig.tight_layout(rect=[0, 0, 0.85, 1])
            else:
                ax.text(0.5, 0.5, f"无数据\n{sheet_name} - {data_type_item.name}",
                       ha='center', va='center', fontsize=12)

        except Exception as e:
            import traceback
            logger.error(f"绘图失败: {e}\n{traceback.format_exc()}")
            ax.text(0.5, 0.5, f"绘图失败:\n{e}", ha='center', va='center', fontsize=10)

        canvas = FigureCanvasQTAgg(fig)
        layout.addWidget(canvas)

        return widget

    def _update_history_from_cache(self):
        """服务端模式下直接刷新历史记录。"""
        self.load_history_from_cache()

    def load_history_data(self):
        """根据筛选条件加载历史数据。"""
        self.history_list.clear()
        selected_device = self.history_device_combo.currentText()
        start_date = self.start_date.date().toPyDate()
        end_date = self.end_date.date().toPyDate()
        for record in self.history_data:
            if selected_device != '全部设备' and record['device_id'] != selected_device:
                continue
            try:
                record_date = datetime.strptime(record['timestamp'], '%Y-%m-%d %H:%M:%S').date()
            except Exception:
                continue
            if not (start_date <= record_date <= end_date):
                continue
            item = QListWidgetItem(f"{record['timestamp']} - {record['device_id']} - {record['file_name']} [{record.get('processing_status', '')}]")
            item.setData(Qt.ItemDataRole.UserRole, record)
            self.history_list.addItem(item)

    def on_history_item_clicked(self, item: QListWidgetItem):
        """点击历史记录后读取服务端详情。"""
        record = item.data(Qt.ItemDataRole.UserRole)
        if not record or not record.get('file_id'):
            return
        detail = self._fetch_excel_detail(int(record['file_id'])) or record
        sheet_data_dict = self.build_sheet_data_dict_from_record(detail)
        if not sheet_data_dict:
            self.log_message(f"记录尚未解析完成: {record.get('file_name', '')}")
            return
        self.history_display_tabs.clear()
        detail_alarm_info = (detail or {}).get('alarm_info') or record.get('alarm_info') or {}
        widget = self.create_device_tab_content(record['device_id'], sheet_data_dict, record.get('file_name'), detail_alarm_info)
        self.history_display_tabs.addTab(widget, f"{record['device_id']} - {record['file_name']}")

    def load_history_from_cache(self):
        """直接从服务端加载历史记录。"""
        logger.info("开始从服务端加载电量历史记录...")
        records = [self._normalize_excel_record(record) for record in self._fetch_excel_records(limit=200)]
        self.history_data = records
        self.history_device_combo.clear()
        self.history_device_combo.addItem('全部设备')
        for device_id in sorted({record['device_id'] for record in records if record.get('device_id')}):
            self.history_device_combo.addItem(device_id)
        self.load_history_data()

    def load_latest_from_cache(self, show_realtime_loading: bool = True):
        """Load the latest parsed Excel record per device and skip bad records safely."""
        if show_realtime_loading:
            self._begin_realtime_loading("正在加载电量实时数据...")
        try:
            logger.info("Loading latest Excel records from server...")
            records = [self._normalize_excel_record(record) for record in self._fetch_excel_records(limit=200)]
            latest_by_device = {}
            for record in records:
                device_id = record.get("device_id")
                if not device_id or device_id in latest_by_device:
                    continue
                latest_by_device[device_id] = record
            self.device_tabs.clear()
            self.device_tab_dict.clear()
            self.device_data.clear()
            self.displayed_excel_file_ids.clear()
            loaded_count = 0
            for record in latest_by_device.values():
                try:
                    if self._load_excel_record_into_ui(record, switch_to_realtime=False):
                        loaded_count += 1
                except Exception as exc:
                    logger.warning(f"Skip broken Excel record {record.get('file_name', '')}: {exc}")
            if loaded_count == 0:
                placeholder = QWidget()
                placeholder_layout = QVBoxLayout(placeholder)
                placeholder_layout.addWidget(QLabel("等待服务端解析后的电量数据..."))
                self.device_tabs.addTab(placeholder, "暂无设备")
                self.status_label.setText("状态: 暂无已解析的电量数据")
                return
            self.status_label.setText(f"状态: 已加载 {loaded_count} 台设备的电量数据")
        finally:
            if show_realtime_loading:
                self._end_realtime_loading()



    def create_log_tab(self):
        """创建日志选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 日志文本框
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("font-family: Consolas; font-size: 10px; background-color: #1e1e1e; color: #d4d4d4;")
        self.log_text.setMaximumBlockCount(1000)  # 限制最大行数
        layout.addWidget(self.log_text)

        # 按钮区域
        btn_layout = QHBoxLayout()
        clear_btn = QPushButton("清空日志")
        clear_btn.clicked.connect(self.log_text.clear)
        btn_layout.addWidget(clear_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 添加初始日志
        self.log_message("电量数据页面日志已初始化")

        return tab


    def create_cache_table_tab(self):
        """创建缓存数据表格选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 顶部按钮区
        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.load_cache_data_to_table)
        btn_layout.addWidget(refresh_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 表格
        self.cache_table = QTableWidget()
        self.cache_table.setColumnCount(8)
        self.cache_table.setHorizontalHeaderLabels([
            "设备ID", "文件名", "时间", "Sheet数", "额定电压", "额定频率", "预警信息", "操作"
        ])
        self.cache_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.cache_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.cache_table.setAlternatingRowColors(True)
        layout.addWidget(self.cache_table)

        # 初始加载
        self.load_cache_data_to_table()

        return tab

    def create_trend_chart_tab(self):
        """创建数据趋势图选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        control_layout = QHBoxLayout()
        control_layout.addWidget(QLabel("选择设备:"))
        self.trend_device_combo = QComboBox()
        self.trend_device_combo.currentTextChanged.connect(self.update_trend_chart)
        control_layout.addWidget(self.trend_device_combo)
        control_layout.addWidget(QLabel("数据类型:"))
        self.trend_data_type_combo = QComboBox()
        self.trend_data_type_combo.addItems(["功率W", "电压", "电流", "相角"])
        self.trend_data_type_combo.currentTextChanged.connect(self.update_trend_chart)
        control_layout.addWidget(self.trend_data_type_combo)
        control_layout.addWidget(QLabel("相位:"))
        self.trend_phase_combo = QComboBox()
        self.trend_phase_combo.addItems(["A相", "B相", "C相"])
        self.trend_phase_combo.currentTextChanged.connect(self.update_trend_chart)
        control_layout.addWidget(self.trend_phase_combo)
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.refresh_trend_chart)
        control_layout.addWidget(refresh_btn)
        control_layout.addStretch()
        layout.addLayout(control_layout)
        self.trend_figure = Figure(figsize=(12, 6))
        self.trend_canvas = FigureCanvasQTAgg(self.trend_figure)
        layout.addWidget(self.trend_canvas)
        return tab


    def log_message(self, message: str):
        """添加日志消息"""
        if not hasattr(self, 'log_text') or self.log_text is None:
            # 日志组件还未初始化，只记录到logger
            logger.info(f"[电量页面] {message}")
            return

        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_text.appendPlainText(f"[{timestamp}] {message}")

    def _populate_cache_table(self, records):
        """Render Excel records in the server data table."""
        self.cache_table.setSortingEnabled(False)
        self.cache_table.setRowCount(len(records))
        for row, record in enumerate(records):
            status = record.get("processing_status", "pending")
            self.cache_table.setItem(row, 0, QTableWidgetItem(record.get("device_id", "")))
            self.cache_table.setItem(row, 1, QTableWidgetItem(record.get("file_name", "")))
            self.cache_table.setItem(row, 2, QTableWidgetItem(record.get("timestamp", "")))
            self.cache_table.setItem(row, 3, QTableWidgetItem(str(record.get("sheet_count", 0)) if status == "done" else status))
            voltage_text = "--" if status != "done" else f"{record.get('rated_voltage', 0)}{record.get('rated_voltage_unit', '')}"
            freq_text = "--" if status != "done" else f"{record.get('rated_frequency', 0)}{record.get('rated_frequency_unit', '')}"
            self.cache_table.setItem(row, 4, QTableWidgetItem(voltage_text))
            self.cache_table.setItem(row, 5, QTableWidgetItem(freq_text))
            self.cache_table.setItem(row, 6, self._make_alarm_table_item(record.get("alarm_info") or {}))
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(2, 2, 2, 2)
            action_layout.setSpacing(6)
            view_btn = QPushButton("查看")
            view_btn.setStyleSheet("font-size: 9px; padding: 2px 8px;")
            view_btn.clicked.connect(lambda checked, r=record: self.view_cache_record(r))
            action_layout.addWidget(view_btn)
            download_btn = QPushButton("下载")
            download_btn.setStyleSheet("font-size: 9px; padding: 2px 8px;")
            download_btn.clicked.connect(lambda checked, r=record: self._download_excel_record(r))
            action_layout.addWidget(download_btn)
            action_layout.addStretch()
            self.cache_table.setCellWidget(row, 7, action_widget)
        self.sort_table_by_latest_time(self.cache_table, ("时间",))
        self.log_message(f"Loaded {len(records)} Excel records from server")

    def load_cache_data_to_table(self, show_loading: bool = True):
        """Load Excel records asynchronously so the page does not freeze."""
        def task():
            return [self._normalize_excel_record(record) for record in self._fetch_excel_records(limit=100)]

        def on_success(records):
            self._populate_cache_table(records)

        self.run_async_task(
            task,
            on_success=on_success,
            on_error=lambda message: QMessageBox.critical(self, "加载失败", message),
            loading_text="正在加载电量数据...",
            show_loading=show_loading,
            widgets=[getattr(self, "cache_table", None)],
        )

    def view_cache_record(self, record: dict):
        """Load one Excel record detail asynchronously and switch to the realtime tab."""
        normalized = self._normalize_excel_record(record)
        if not normalized.get("file_id"):
            QMessageBox.information(self, "提示", "当前记录缺少文件编号。")
            return

        def task():
            if normalized.get("processing_status") == "done":
                return self._fetch_excel_detail(int(normalized["file_id"])) or record
            return record

        self._begin_realtime_loading(f"正在加载 {normalized.get('file_name', '')}...")

        def on_success(detail):
            try:
                if self._load_excel_record_into_ui(detail):
                    self.log_message(f"Loaded Excel record: {normalized.get('file_name', '')}")
                else:
                    QMessageBox.information(self, "提示", "该记录尚未完成解析或暂无可显示的数据。")
            finally:
                self._end_realtime_loading()

        def on_error(message):
            self._end_realtime_loading()
            QMessageBox.critical(self, "加载失败", message)

        self.run_async_task(
            task,
            on_success=on_success,
            on_error=on_error,
            loading_text=f"正在加载 {normalized.get('file_name', '')}...",
            widgets=[getattr(self, "cache_table", None)],
        )

    def refresh_trend_chart(self):
        """刷新趋势图设备列表。"""
        devices = sorted({record['device_id'] for record in self.history_data if record.get('device_id')})
        current_device = self.trend_device_combo.currentText()
        self.trend_device_combo.clear()
        self.trend_device_combo.addItems(devices)
        if current_device in devices:
            self.trend_device_combo.setCurrentText(current_device)
        self.update_trend_chart(self.trend_device_combo.currentText())

    def update_trend_chart(self, device_id: str = None):
        """基于服务端解析后的结构化数据绘制趋势图。"""
        try:
            if not device_id:
                device_id = self.trend_device_combo.currentText()
            if not device_id:
                return
            records = [record for record in self._fetch_excel_records(device_id=device_id, limit=20) if record.get('processing_status') == 'done']
            if not records:
                self.trend_figure.clear()
                ax = self.trend_figure.add_subplot(111)
                ax.text(0.5, 0.5, '暂无可用趋势数据', ha='center', va='center', transform=ax.transAxes)
                self.trend_canvas.draw()
                self.log_message(f"设备 {device_id} 没有已解析的历史数据")
                return
            data_type = self.trend_data_type_combo.currentText()
            phase = self.trend_phase_combo.currentText()
            timestamps = []
            values = []
            for record in reversed(records):
                detail = self._fetch_excel_detail(int(record['id']))
                if not detail:
                    continue
                sheet_data_dict = self.build_sheet_data_dict_from_record(detail)
                if not sheet_data_dict:
                    continue
                selected_value = None
                for sheet in sheet_data_dict.values():
                    for data_type_item in sheet.data:
                        if data_type_item.name != data_type:
                            continue
                        for phase_item in data_type_item.data.y:
                            if phase_item.name != phase:
                                continue
                            for device_item in phase_item.data:
                                numeric_values = []
                                for raw_value in device_item.data:
                                    try:
                                        numeric_values.append(float(raw_value))
                                    except Exception:
                                        continue
                                if numeric_values:
                                    selected_value = sum(numeric_values) / len(numeric_values)
                                    break
                            if selected_value is not None:
                                break
                        if selected_value is not None:
                            break
                    if selected_value is not None:
                        break
                if selected_value is None:
                    continue
                timestamps.append((detail.get('upload_time') or '').replace('T', ' ')[:19])
                values.append(selected_value)
            self.trend_figure.clear()
            ax = self.trend_figure.add_subplot(111)
            if values:
                ax.plot(range(len(values)), values, marker='o', linewidth=1.5)
                ax.set_xticks(range(len(timestamps)))
                ax.set_xticklabels(timestamps, rotation=30, ha='right', fontsize=8)
                ax.set_title(f'{device_id} - {data_type} - {phase}')
                ax.set_ylabel(data_type)
                ax.grid(True, linestyle='--', alpha=0.35)
            else:
                ax.text(0.5, 0.5, '暂无可用趋势数据', ha='center', va='center', transform=ax.transAxes)
                ax.set_axis_off()
            self.trend_figure.tight_layout()
            self.trend_canvas.draw()
        except Exception as e:
            logger.error(f"更新趋势图失败: {e}")
            self.log_message(f"更新趋势图失败: {e}")

    def set_server_client(self, client: Client_server):
        """设置服务端客户端，并在页面可见时触发后台刷新。"""
        self.server_client = client
        if self.is_visible:
            QTimer.singleShot(0, self.bootstrap_cache_load)

    def closeEvent(self, event):
        """关闭事件"""
        if hasattr(self, 'queue_thread'):
            self.queue_thread.stop()
        super().closeEvent(event)

    def refresh_data(self):
        """刷新数据"""
        self.bootstrap_cache_load()




