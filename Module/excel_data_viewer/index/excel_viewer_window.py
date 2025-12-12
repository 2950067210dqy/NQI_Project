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
from PyQt6.QtCore import pyqtSignal, Qt, QDate
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QGroupBox, QComboBox, QDateEdit, QListWidget, QListWidgetItem,
    QTableWidget, QTableWidgetItem, QPlainTextEdit, QHeaderView
)
from loguru import logger
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
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
        
        # 服务端连接
        self.server_client: Client_server = None
        self.active_threads = []
        
        # 初始化UI
        self.init_ui()
        
        # 队列监听
        self.queue_thread = ExcelViewerQueueThread("excel_queue", self)
        queue = global_setting.get_setting("queue", None)
        if queue:
            self.queue_thread.queue = queue
            self.queue_thread.start()
        
        # 连接缓存更新信号（从队列线程到主线程）
        self.cache_update_signal.connect(
            self.on_cache_data_ready,
            Qt.ConnectionType.QueuedConnection
        )
        
        # 加载历史缓存
        self.load_history_from_cache()
    
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
        self.main_tabs.addTab(self.create_cache_table_tab(), "缓存数据")
        self.main_tabs.addTab(self.create_trend_chart_tab(), "数据趋势")
        self.main_tabs.addTab(self.create_log_tab(), "日志")
        layout.addWidget(self.main_tabs)
    
    def showEvent(self, event):
        """窗口显示事件"""
        super().showEvent(event)
        self.is_visible = True
        logger.info("电量数据查看器窗口显示")
        
        # 加载最新缓存作为实时记录
        self.load_latest_from_cache()
    
    def hideEvent(self, event):
        """窗口隐藏事件"""
        super().hideEvent(event)
        self.is_visible = False
        logger.info("电量数据查看器窗口隐藏")
    
    def create_realtime_tab(self):
        """创建实时数据选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
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
        """
        下载管理器通知：缓存数据已就绪
        此时文件已下载并保存到缓存数据库，页面从缓存读取并显示
        """
        logger.info(f"[电量数据页面] 收到缓存数据就绪通知: {Path(file_path).name}, 设备: {device_id}")
        self.log_message(f"收到新数据通知: {Path(file_path).name}, 设备: {device_id}")
        
        try:
            # 更新状态
            self.status_label.setText(f"状态: 加载数据 - 设备 {device_id}")
            self.log_message(f"开始加载数据...")
            
            # 从缓存读取最新记录
            latest_record = cache_manager.get_latest_excel_record(device_id)
            if not latest_record:
                logger.warning(f"缓存中没有找到设备 {device_id} 的记录")
                self.log_message(f"警告: 缓存中没有找到设备 {device_id} 的记录")
                return
            
            file_path = latest_record['file_path']
            
            # 检查文件是否存在
            if not file_path or not Path(file_path).exists():
                logger.error(f"文件不存在: {file_path}")
                self.status_label.setText(f"状态: 文件不存在")
                self.log_message(f"错误: 文件不存在 - {file_path}")
                return
            
            # 解析Excel（所有Sheet）
            self.log_message(f"正在解析Excel文件...")
            sheet_data_dict = self.parse_excel_all_sheets(file_path)
            if not sheet_data_dict:
                raise Exception("Excel解析失败")
            
            self.log_message(f"解析成功，共 {len(sheet_data_dict)} 个Sheet")
            
            # 保存数据到内存
            self.device_data[device_id] = sheet_data_dict
            
            # 创建或更新设备选项卡
            self.log_message(f"创建设备选项卡...")
            file_name = Path(file_path).name
            self.create_or_update_device_tab(device_id, sheet_data_dict, file_name)
            
            # 更新历史列表（从缓存读取，无需手动保存）
            self._update_history_from_cache()
            
            self.status_label.setText(f"状态: 加载完成 - 设备 {device_id}")
            self.log_message(f"✅ 数据加载完成: {Path(file_path).name}")
            logger.info(f"✅ 数据加载完成: {Path(file_path).name}")
            
        except Exception as e:
            import traceback
            logger.error(f"处理缓存数据失败: {e}\n{traceback.format_exc()}")
            self.status_label.setText(f"状态: 加载失败 - {e}")
            self.log_message(f"❌ 加载失败: {e}")
    
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
        """解析单个Sheet（使用test/get_test.py的逻辑）"""
        try:
            data_each_counts = 36
            return_data = xlsx_data()
            return_data.name = sheet_name
            
            data_clean = data.dropna()
            if data_clean.empty:
                return None
            
            df_colum_0_unique = data_clean.drop_duplicates(subset=[data_clean.columns[0]])
            df_colum_1_unique = data_clean.drop_duplicates(subset=[data_clean.columns[1]])
            
            # 额定频率和电压
            return_data.rated_frequency = float("".join(re.findall(r'[0-9]', str(df_colum_1_unique.iloc[0, 1]))))
            return_data.rated_frequency_unit = "".join(re.findall(r'[A-Za-z]', str(df_colum_1_unique.iloc[0, 1])))
            return_data.rated_voltage = float("".join(re.findall(r'[0-9]', str(df_colum_0_unique.iloc[0, 0]).split(",")[0])))
            return_data.rated_voltage_unit = "".join(re.findall(r'[A-Za-z]', str(df_colum_0_unique.iloc[0, 0]).split(",")[0]))
            
            # X轴数据
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
                
                # 额定电流
                rated_current_unit = "".join(re.findall(r'[A-Za-z]', str(data_clean.iloc[row, 0]).strip().split(",")[1]))
                if rated_current_unit == "mA":
                    rated_current = float("".join(re.findall(r'[0-9]', str(data_clean.iloc[row, 0]).strip().split(",")[1]))) / 1000
                else:
                    rated_current = float("".join(re.findall(r'[0-9]', str(data_clean.iloc[row, 0]).strip().split(",")[1])))
                
                xlsx_datas_type_item_obj_x_data.append([data_clean.iloc[row, 2], rated_current])
            
            return_data.data[-1].data.x.data = xlsx_datas_type_item_obj_x_data
            
            # Y轴数据
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
            
            # 具体值
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
    
    def create_or_update_device_tab(self, device_id: str, sheet_data_dict: dict, file_name: str = None):
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
        device_tab = self.create_device_tab_content(device_id, sheet_data_dict, file_name)
        self.device_tabs.addTab(device_tab, f"设备 {device_id}")
        self.device_tab_dict[device_id] = device_tab
        
        # 切换到新选项卡
        self.device_tabs.setCurrentWidget(device_tab)
        self.main_tabs.setCurrentIndex(0)
        
        logger.info(f"✅ 设备选项卡创建完成")
    
    def create_device_tab_content(self, device_id: str, sheet_data_dict: dict, file_name: str = None) -> QWidget:
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
        """从缓存更新历史记录列表（增量更新）"""
        try:
            # 获取最新的几条记录
            records = cache_manager.get_excel_records(limit=10)
            
            # 获取已有的文件路径集合
            existing_paths = {item['file_path'] for item in self.history_data}
            
            # 添加新记录
            for record in records:
                if record['file_path'] not in existing_paths and Path(record['file_path']).exists():
                    history_item = {
                        'file_path': record['file_path'],
                        'device_id': record['device_id'],
                        'timestamp': record['timestamp'],
                        'file_name': record['file_name']
                    }
                    self.history_data.insert(0, history_item)  # 插入到开头
                    
                    # 添加设备到下拉框
                    device_id = record['device_id']
                    if device_id not in [self.history_device_combo.itemText(i) 
                                        for i in range(1, self.history_device_combo.count())]:
                        self.history_device_combo.addItem(device_id)
            
        except Exception as e:
            logger.error(f"更新历史记录失败: {e}")
    
    def load_history_data(self):
        """加载历史数据"""
        self.history_list.clear()
        
        selected_device = self.history_device_combo.currentText()
        start_date = self.start_date.date()
        end_date = self.end_date.date()
        
        for record in self.history_data:
            if selected_device != "全部设备" and record['device_id'] != selected_device:
                continue
            
            timestamp_str = record['timestamp']
            try:
                record_date = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S').date()
            except:
                continue
            
            if not (start_date <= record_date <= end_date):
                continue
            
            item = QListWidgetItem(f"{timestamp_str} - {record['device_id']} - {record['file_name']}")
            item.setData(Qt.ItemDataRole.UserRole, record)
            self.history_list.addItem(item)
    
    def on_history_item_clicked(self, item: QListWidgetItem):
        """点击历史记录"""
        record = item.data(Qt.ItemDataRole.UserRole)
        device_id = record['device_id']
        
        if device_id in self.device_data:
            self.history_display_tabs.clear()
            widget = self.create_device_tab_content(device_id, self.device_data[device_id])
            self.history_display_tabs.addTab(widget, f"{device_id} - {record['file_name']}")
    
    def load_history_from_cache(self):
        """从缓存加载历史记录"""
        try:
            logger.info("开始从缓存加载历史记录...")
            
            # 获取所有历史记录
            records = cache_manager.get_excel_records(limit=100)
            
            if not records:
                logger.info("缓存中没有历史记录")
                return
            
            # 加载到history_data
            for record in records:
                if Path(record['file_path']).exists():
                    history_item = {
                        'file_path': record['file_path'],
                        'device_id': record['device_id'],
                        'timestamp': record['timestamp'],
                        'file_name': record['file_name']
                    }
                    self.history_data.append(history_item)
                    
                    # 添加设备到下拉框
                    device_id = record['device_id']
                    if device_id not in [self.history_device_combo.itemText(i) 
                                        for i in range(1, self.history_device_combo.count())]:
                        self.history_device_combo.addItem(device_id)
            
            logger.info(f"✅ 从缓存加载了 {len(self.history_data)} 条历史记录")
            
        except Exception as e:
            logger.error(f"从缓存加载历史记录失败: {e}")
    
    def load_latest_from_cache(self):
        """从缓存加载最新记录作为实时显示"""
        try:
            logger.info("开始从缓存加载最新记录...")
            self.log_message("开始从缓存加载最新记录...")
            
            # 获取所有设备的最新记录
            devices = cache_manager.get_excel_devices()
            
            if not devices:
                logger.info("缓存中没有设备记录")
                self.log_message("缓存中没有设备记录")
                return
            
            self.log_message(f"找到 {len(devices)} 个设备的缓存数据")
            
            loaded_count = 0
            for device_id in devices:
                latest_record = cache_manager.get_latest_excel_record(device_id)
                
                if not latest_record:
                    continue
                
                file_path = latest_record['file_path']
                
                # 检查文件是否存在
                if not file_path or not Path(file_path).exists():
                    logger.warning(f"缓存记录的文件不存在: {file_path}")
                    self.log_message(f"警告: 缓存文件不存在 - {Path(file_path).name}")
                    continue
                
                # 解析并显示数据
                try:
                    self.log_message(f"正在加载设备 {device_id} 的数据...")
                    sheet_data_dict = self.parse_excel_all_sheets(file_path)
                    if sheet_data_dict:
                        self.device_data[device_id] = sheet_data_dict
                        file_name = Path(file_path).name
                        self.create_or_update_device_tab(device_id, sheet_data_dict, file_name)
                        loaded_count += 1
                        logger.info(f"✅ 从缓存加载设备 {device_id} 的数据")
                        self.log_message(f"✅ 设备 {device_id} 数据加载成功")
                except Exception as e:
                    logger.error(f"解析缓存文件失败 {file_path}: {e}")
                    self.log_message(f"错误: 解析失败 - {Path(file_path).name}")
            
            if loaded_count > 0:
                self.status_label.setText(f"状态: 已从缓存加载 {loaded_count} 个设备的数据")
                logger.info(f"✅ 从缓存加载了 {loaded_count} 个设备的最新数据")
                self.log_message(f"✅ 从缓存加载完成，共 {loaded_count} 个设备")
            else:
                logger.info("没有可加载的缓存数据")
                self.log_message("没有可加载的缓存数据")
                
        except Exception as e:
            logger.error(f"从缓存加载最新记录失败: {e}")
            self.log_message(f"❌ 加载失败: {e}")
    
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
        self.cache_table.setColumnCount(7)
        self.cache_table.setHorizontalHeaderLabels([
            "设备ID", "文件名", "时间", "Sheet数", "额定电压", "额定频率", "操作"
        ])
        self.cache_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.cache_table.setAlternatingRowColors(True)
        layout.addWidget(self.cache_table)
        
        # 初始加载
        self.load_cache_data_to_table()
        
        return tab
    
    def create_trend_chart_tab(self):
        """创建数据趋势图选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 控制区
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
        
        # 图表区域
        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
        from matplotlib.figure import Figure
        
        self.trend_figure = Figure(figsize=(12, 6))
        self.trend_canvas = FigureCanvasQTAgg(self.trend_figure)
        layout.addWidget(self.trend_canvas)
        
        # 加载设备列表
        devices = cache_manager.get_excel_devices()
        self.trend_device_combo.addItems(devices)
        
        return tab
    
    def log_message(self, message: str):
        """添加日志消息"""
        if not hasattr(self, 'log_text') or self.log_text is None:
            # 日志组件还未初始化，只记录到logger
            logger.info(f"[电量页面] {message}")
            return
        
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_text.appendPlainText(f"[{timestamp}] {message}")
    
    def load_cache_data_to_table(self):
        """加载缓存数据到表格"""
        try:
            records = cache_manager.get_excel_records(limit=100)
            
            self.cache_table.setRowCount(len(records))
            
            for row, record in enumerate(records):
                self.cache_table.setItem(row, 0, QTableWidgetItem(record['device_id']))
                self.cache_table.setItem(row, 1, QTableWidgetItem(record['file_name']))
                self.cache_table.setItem(row, 2, QTableWidgetItem(record['timestamp']))
                self.cache_table.setItem(row, 3, QTableWidgetItem(str(record.get('sheet_count', 0))))
                
                voltage_text = f"{record.get('rated_voltage', 0)}{record.get('rated_voltage_unit', '')}"
                self.cache_table.setItem(row, 4, QTableWidgetItem(voltage_text))
                
                freq_text = f"{record.get('rated_frequency', 0)}{record.get('rated_frequency_unit', '')}"
                self.cache_table.setItem(row, 5, QTableWidgetItem(freq_text))
                
                # 查看按钮
                view_btn = QPushButton("查看")
                view_btn.setStyleSheet("font-size: 9px; padding: 2px 8px;")
                view_btn.clicked.connect(lambda checked, r=record: self.view_cache_record(r))
                self.cache_table.setCellWidget(row, 6, view_btn)
            
            self.log_message(f"加载了 {len(records)} 条缓存记录")
            
        except Exception as e:
            logger.error(f"加载缓存数据失败: {e}")
            self.log_message(f"加载缓存数据失败: {e}")
    
    def view_cache_record(self, record: dict):
        """查看缓存记录"""
        try:
            file_path = record['file_path']
            device_id = record['device_id']
            
            if Path(file_path).exists():
                # 解析并显示
                sheet_data_dict = self.parse_excel_all_sheets(file_path)
                if sheet_data_dict:
                    self.device_data[device_id] = sheet_data_dict
                    self.create_or_update_device_tab(device_id, sheet_data_dict)
                    # 切换到实时数据选项卡
                    self.main_tabs.setCurrentIndex(0)
                    self.log_message(f"已加载缓存记录: {record['file_name']}")
            else:
                self.log_message(f"文件不存在: {file_path}")
                
        except Exception as e:
            logger.error(f"查看缓存记录失败: {e}")
            self.log_message(f"查看记录失败: {e}")
    
    def refresh_trend_chart(self):
        """刷新趋势图"""
        devices = cache_manager.get_excel_devices()
        current_device = self.trend_device_combo.currentText()
        
        self.trend_device_combo.clear()
        self.trend_device_combo.addItems(devices)
        
        if current_device in devices:
            self.trend_device_combo.setCurrentText(current_device)
        
        self.update_trend_chart(current_device)
    
    def update_trend_chart(self, device_id: str = None):
        """更新趋势图 - 从每个Excel提取实际测量数据"""
        try:
            if not device_id:
                device_id = self.trend_device_combo.currentText()
            
            if not device_id:
                return
            
            # 从缓存读取历史数据
            records = cache_manager.get_excel_records(device_id=device_id, limit=50)
            
            if not records:
                self.log_message(f"设备 {device_id} 没有历史数据")
                return
            
            # 解析数据
            timestamps = []
            values = []
            
            data_type = self.trend_data_type_combo.currentText()
            phase = self.trend_phase_combo.currentText()
            
            self.log_message(f"正在提取 {data_type} - {phase} 的数据...")
            
            for record in reversed(records):  # 从旧到新
                try:
                    file_path = record['file_path']
                    if not Path(file_path).exists():
                        continue
                    
                    # 解析Excel获取实际测量数据
                    sheet_data_dict = self.parse_excel_all_sheets(file_path)
                    if not sheet_data_dict:
                        continue
                    
                    # 取第一个Sheet的数据
                    first_sheet = list(sheet_data_dict.values())[0]
                    
                    # 找到对应的数据类型
                    data_type_item = None
                    for item in first_sheet.data:
                        if item.name == data_type:
                            data_type_item = item
                            break
                    
                    if not data_type_item:
                        continue
                    
                    # 找到对应的相位
                    phase_item = None
                    for p_item in data_type_item.data.y:
                        if phase in p_item.name:
                            phase_item = p_item
                            break
                    
                    if not phase_item or not phase_item.data:
                        continue
                    
                    # 取第一个设备的平均值作为代表值
                    if phase_item.data[0].data:
                        avg_value = sum(phase_item.data[0].data) / len(phase_item.data[0].data)
                        timestamps.append(datetime.strptime(record['timestamp'], '%Y-%m-%d %H:%M:%S'))
                        values.append(avg_value)
                    
                except Exception as e:
                    logger.error(f"解析记录失败: {e}")
                    continue
            
            # 绘制折线图
            self.trend_figure.clear()
            ax = self.trend_figure.add_subplot(111)
            
            if timestamps and values:
                ax.plot(timestamps, values, marker='o', linestyle='-', linewidth=2, markersize=6, color='#1976D2')
                ax.set_xlabel('时间', fontsize=11, fontweight='bold')
                ax.set_ylabel(data_type, fontsize=11, fontweight='bold')
                ax.set_title(f'设备 {device_id} - {data_type} ({phase}) 趋势图', fontsize=12, fontweight='bold')
                ax.grid(True, alpha=0.3, linestyle='--')
                
                # 旋转x轴标签
                import matplotlib.dates as mdates
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
                self.trend_figure.autofmt_xdate()
                
                self.log_message(f"绘制完成: {len(values)} 个数据点")
            else:
                ax.text(0.5, 0.5, f'暂无数据\n({data_type} - {phase})', ha='center', va='center', fontsize=14)
                self.log_message(f"没有可用数据")
            
            self.trend_canvas.draw()
            self.log_message(f"更新趋势图: 设备{device_id}, {data_type}, {phase}")
            
        except Exception as e:
            import traceback
            logger.error(f"更新趋势图失败: {e}\n{traceback.format_exc()}")
            self.log_message(f"更新趋势图失败: {e}")
    
    def set_server_client(self, client: Client_server):
        """设置服务端客户端"""
        self.server_client = client
    
    def closeEvent(self, event):
        """关闭事件"""
        if hasattr(self, 'queue_thread'):
            self.queue_thread.stop()
        
        # 断开下载管理器信号
        try:
            download_manager.excel_data_ready.disconnect(self.on_cache_data_ready)
        except:
            pass
        
        super().closeEvent(event)
    
    def refresh_data(self):
        """刷新数据"""
        pass
