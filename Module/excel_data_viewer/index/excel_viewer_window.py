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
from PyQt6.QtCore import pyqtSignal, Qt, QThread, QDate, QMetaObject, Q_ARG
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QGroupBox, QScrollArea,
    QComboBox, QDateEdit, QListWidget, QListWidgetItem, QSplitter
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
from public.entity.queue.ObjectQueueItem import ObjectQueueItem
from public.config_class.global_setting import global_setting


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
class ExcelDownloadThread(QThread):
    download_finished = pyqtSignal(str, str)
    download_failed = pyqtSignal(str, str)
    
    def __init__(self, client, file_id, save_path, device_id):
        super().__init__()
        self.client = client
        self.file_id = file_id
        self.save_path = Path(save_path)
        self.device_id = device_id
    
    def run(self):
        try:
            logger.info(f"下载: {self.save_path.name}")
            if self.file_id is None:
                raise Exception("file_id为None")
            self.save_path.parent.mkdir(parents=True, exist_ok=True)
            self.client.download_excel_file(self.file_id, self.save_path)
            logger.info(f"✅ 下载完成")
            self.download_finished.emit(str(self.save_path), self.device_id)
        except Exception as e:
            logger.error(f"❌ 下载失败: {e}")
            self.download_failed.emit(str(e), self.device_id)


class ExcelViewerQueueThread(MyQThread):
    def __init__(self, name, window):
        super().__init__(name)
        self.queue = None
        self.window = window
    
    def dosomething(self):
        if not self.queue.empty():
            try:
                message: ObjectQueueItem = self.queue.get()
                if message and not message.is_Empty():
                    if isinstance(message, ObjectQueueItem) and message.to == 'excel_data_viewer':
                        if message.title == 'new_excel_data' and message.data:
                            self.window.update_data_signal.emit(message.data)
            except Exception as e:
                logger.error(f"队列错误: {e}")


# ==================== 主窗口 ====================
class ExcelDataViewerWindow(ThemedWindow):
    update_data_signal = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__()
        self.setWindowTitle("电量数据查看器")
        self.resize(1400, 900)
        
        # 数据存储
        self.device_data = {}  # {device_id: {sheet_name: xlsx_data}}
        self.device_tab_dict = {}  # {device_id: device_tab_widget}
        self.history_data = []
        
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
        
        # 连接信号
        self.update_data_signal.connect(self.on_new_data_received)
    
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
        layout.addWidget(self.main_tabs)
    
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
    
    def on_new_data_received(self, data: dict):
        """接收新数据"""
        logger.info(f"收到新数据: {data}")
        
        device_id = data.get('device_id', 'unknown')
        file_id = data.get('file_id')
        file_name = data.get('file_name', 'unknown')
        
        self.status_label.setText(f"状态: 正在下载 - 设备 {device_id}")
        
        if file_id and self.server_client:
            try:
                data_dir = Path("data/excel") / device_id
                data_dir.mkdir(parents=True, exist_ok=True)
                save_path = data_dir / file_name
                
                thread = ExcelDownloadThread(
                    self.server_client.client,
                    file_id,
                    save_path,
                    device_id
                )
                # 使用QueuedConnection确保槽函数在主线程中执行
                thread.download_finished.connect(self.on_download_finished, Qt.ConnectionType.QueuedConnection)
                thread.download_failed.connect(self.on_download_failed, Qt.ConnectionType.QueuedConnection)
                
                self.active_threads.append(thread)
                thread.start()
                
            except Exception as e:
                logger.error(f"启动下载失败: {e}")
    
    def on_download_finished(self, file_path: str, device_id: str):
        """下载完成"""
        logger.info(f"下载完成: {file_path}")
        
        try:
            # 解析Excel（所有Sheet）
            sheet_data_dict = self.parse_excel_all_sheets(file_path)
            if not sheet_data_dict:
                raise Exception("Excel解析失败")
            
            # 保存数据
            self.device_data[device_id] = sheet_data_dict
            
            # 创建或更新设备选项卡
            self.create_or_update_device_tab(device_id, sheet_data_dict)
            
            # 保存历史
            self.save_history(file_path, device_id)
            
            self.status_label.setText(f"状态: 加载完成 - 设备 {device_id}")
            logger.info("✅ 数据加载完成")
            
        except Exception as e:
            import traceback
            logger.error(f"处理失败: {e}\n{traceback.format_exc()}")
            self.status_label.setText(f"状态: 失败 - {e}")
    
    def on_download_failed(self, error: str, device_id: str):
        """下载失败"""
        self.status_label.setText(f"状态: 下载失败 - {error}")
    
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
    
    def create_or_update_device_tab(self, device_id: str, sheet_data_dict: dict):
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
        device_tab = self.create_device_tab_content(device_id, sheet_data_dict)
        self.device_tabs.addTab(device_tab, f"设备 {device_id}")
        self.device_tab_dict[device_id] = device_tab
        
        # 切换到新选项卡
        self.device_tabs.setCurrentWidget(device_tab)
        self.main_tabs.setCurrentIndex(0)
        
        logger.info(f"✅ 设备选项卡创建完成")
    
    def create_device_tab_content(self, device_id: str, sheet_data_dict: dict) -> QWidget:
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
    
    def save_history(self, file_path: str, device_id: str):
        """保存历史"""
        record = {
            'file_path': file_path,
            'device_id': device_id,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'file_name': Path(file_path).name
        }
        self.history_data.append(record)
        
        if device_id not in [self.history_device_combo.itemText(i) 
                             for i in range(1, self.history_device_combo.count())]:
            self.history_device_combo.addItem(device_id)
    
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
    
    def set_server_client(self, client: Client_server):
        """设置服务端客户端"""
        self.server_client = client
    
    def closeEvent(self, event):
        """关闭事件"""
        if hasattr(self, 'queue_thread'):
            self.queue_thread.stop()
        
        for thread in self.active_threads:
            if thread.isRunning():
                thread.terminate()
                thread.wait(1000)
        
        super().closeEvent(event)
    
    def refresh_data(self):
        """刷新数据"""
        pass
