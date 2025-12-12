"""
几何量图片数据查看器主窗口
包含两个选项卡：
1. 实时识别 - 2列4行共8个区域显示原图和识别图
2. 历史识别 - 查看所有历史识别记录
"""
import typing
import threading
from datetime import datetime
from pathlib import Path

from PyQt6 import QtGui
from PyQt6.QtCore import pyqtSignal, Qt, QSize, QThread
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
                              QLabel, QPushButton, QGroupBox, QGridLayout,
                              QScrollArea, QMessageBox, QListWidget, QListWidgetItem,
                              QSplitter, QFrame, QComboBox)
from PyQt6.QtGui import QPixmap, QImage
from loguru import logger

from Module.image_data_viewer.service.image_recognition import image_recognition_service
from Service.connect_server_service.index.Client_server import Client_server
from theme.ThemeQt6 import ThemedWindow
from public.entity.MyQThread import MyQThread
from public.entity.queue.ObjectQueueItem import ObjectQueueItem
from public.config_class.global_setting import global_setting


class ImageDownloadThread(QThread):
    """图片文件下载线程"""
    download_finished = pyqtSignal(str, str)  # file_path, device_id
    download_failed = pyqtSignal(str, str)    # error, device_id
    
    def __init__(self, client, file_id, save_path, device_id):
        super().__init__()
        self.client = client
        self.file_id = file_id
        self.save_path = Path(save_path)
        self.device_id = device_id
        self.setTerminationEnabled(True)
    
    def run(self):
        """执行下载"""
        try:
            logger.info(f"[下载线程] 开始下载图片: {self.save_path.name}, file_id={self.file_id}")
            
            if self.file_id is None:
                raise Exception("file_id 为 None，无法下载")
            
            self.save_path.parent.mkdir(parents=True, exist_ok=True)
            self.client.download_image_file(self.file_id, self.save_path)
            
            logger.info(f"[下载线程] 下载完成: {self.save_path}")
            self.download_finished.emit(str(self.save_path), self.device_id)
            
        except Exception as e:
            import traceback
            logger.error(f"[下载线程] 下载失败: {e}\n{traceback.format_exc()}")
            self.download_failed.emit(str(e), self.device_id)


class ImageViewerQueueThread(MyQThread):
    """队列监听线程"""
    
    def __init__(self, name, window):
        super().__init__(name)
        self.queue = None
        self.window = window  # 窗口引用
    
    def dosomething(self):
        if not self.queue.empty():
            try:
                message: ObjectQueueItem = self.queue.get()
            except Exception as e:
                logger.error(f"{self.name}发生错误{e}")
                return
            
            if message is not None and message.is_Empty():
                return
            
            if message is not None and isinstance(message, ObjectQueueItem) and message.to == 'image_data_viewer':
                logger.info(f"图片数据查看器收到消息: {message.title}")
                
                match message.title:
                    case 'new_image_data':
                        # 收到新的图片数据通知
                        data = message.data
                        if data and self.window:
                            self.window.update_data_signal.emit(data)
                    case _:
                        pass
            else:
                # 把消息放回去
                self.queue.put(message)


class ImageDisplayWidget(QFrame):
    """单个图片显示组件（包含原图和识别图）"""
    
    def __init__(self, index: int, parent=None):
        super().__init__(parent)
        self.index = index
        self.original_image_path = None
        self.recognized_image_path = None
        
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.init_ui()
    
    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        
        # 标题和文件名
        title_label = QLabel(f"位置 {self.index + 1}")
        title_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # 文件名标签
        self.filename_label = QLabel("--")
        self.filename_label.setStyleSheet("color: #666; font-size: 10px;")
        self.filename_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.filename_label.setWordWrap(True)
        layout.addWidget(self.filename_label)
        
        # 图片显示区域（左右分布）
        images_layout = QHBoxLayout()
        
        # 原图区域
        original_group = QGroupBox("原图")
        original_layout = QVBoxLayout(original_group)
        self.original_label = QLabel()
        self.original_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.original_label.setMinimumSize(200, 150)
        self.original_label.setStyleSheet("border: 1px solid #ccc; background: #f5f5f5;")
        self.original_label.setScaledContents(False)
        original_layout.addWidget(self.original_label)
        images_layout.addWidget(original_group)
        
        # 识别图区域
        recognized_group = QGroupBox("识别图")
        recognized_layout = QVBoxLayout(recognized_group)
        self.recognized_label = QLabel()
        self.recognized_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.recognized_label.setMinimumSize(200, 150)
        self.recognized_label.setStyleSheet("border: 1px solid #ccc; background: #f5f5f5;")
        self.recognized_label.setScaledContents(False)
        recognized_layout.addWidget(self.recognized_label)
        images_layout.addWidget(recognized_group)
        
        layout.addLayout(images_layout)
        
        # 状态显示
        self.status_label = QLabel("等待数据...")
        self.status_label.setStyleSheet("color: gray; font-size: 10px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
    
    def load_original_image(self, image_path: Path):
        """加载原图并自动识别"""
        try:
            self.original_image_path = image_path
            
            # 显示文件名
            self.filename_label.setText(image_path.name)
            
            # 加载原图
            pixmap = QPixmap(str(image_path))
            
            if pixmap.isNull():
                raise Exception("无法加载图片")
            
            # 缩放图片以适应标签
            scaled_pixmap = pixmap.scaled(
                self.original_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.original_label.setPixmap(scaled_pixmap)
            
            self.status_label.setText(f"已加载")
            self.status_label.setStyleSheet("color: green; font-size: 10px;")
            
            logger.info(f"位置 {self.index + 1} 加载原图: {image_path.name}")
            
            # 自动识别
            self.auto_recognize()
            
        except Exception as e:
            logger.error(f"加载图片失败: {e}")
            self.status_label.setText(f"加载失败")
            self.status_label.setStyleSheet("color: red; font-size: 10px;")
    
    def load_recognized_image(self, image_path: Path):
        """加载识别图"""
        try:
            self.recognized_image_path = image_path
            pixmap = QPixmap(str(image_path))
            
            if pixmap.isNull():
                raise Exception("无法加载图片")
            
            # 缩放图片以适应标签
            scaled_pixmap = pixmap.scaled(
                self.recognized_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.recognized_label.setPixmap(scaled_pixmap)
            
            self.status_label.setText(f"识别完成")
            self.status_label.setStyleSheet("color: blue; font-size: 10px;")
            
            logger.info(f"位置 {self.index + 1} 加载识别图: {image_path}")
            
        except Exception as e:
            logger.error(f"加载识别图失败: {e}")
    
    def auto_recognize(self):
        """自动识别"""
        if not self.original_image_path:
            return
        
        self.status_label.setText("识别中...")
        self.status_label.setStyleSheet("color: orange; font-size: 10px;")
        
        # 调用识别服务
        recognized_path = image_recognition_service.recognize_image(self.original_image_path)
        
        if recognized_path:
            self.load_recognized_image(recognized_path)
        else:
            self.status_label.setText("识别失败")
            self.status_label.setStyleSheet("color: red; font-size: 10px;")
    
    def clear(self):
        """清空显示"""
        self.original_label.clear()
        self.recognized_label.clear()
        self.original_image_path = None
        self.recognized_image_path = None
        
        self.filename_label.setText("--")
        self.status_label.setText("等待数据...")
        self.status_label.setStyleSheet("color: gray; font-size: 10px;")


class ImageDataViewerWindow(ThemedWindow):
    """几何量图片数据查看器窗口"""
    
    update_data_signal = pyqtSignal(dict)  # 接收新数据的信号
    
    def __init__(self, parent=None):
        super().__init__()
        self.setWindowTitle("几何量图片数据查看器")
        self.resize(1400, 900)
        
        # 数据存储
        self.image_display_widgets = []  # 图片显示组件（动态扩展）
        self.base_widget_count = 8  # 基础显示区域数量
        self.max_widget_count = 20  # ✅ 最大显示区域数量
        self.history_records = []  # 历史识别记录
        
        # ✅ FIFO队列管理：记录下一个要使用的区域索引
        self.next_widget_index = 0  # 下一个要使用的区域索引
        
        # ✅ 线程锁：保护多线程访问共享资源
        self.widget_access_lock = threading.Lock()  # 保护 get_next_widget_for_device 方法
        
        # ✅ 正在创建的设备tab标记（防止重复创建）
        self.creating_device_tabs = set()  # 正在创建中的device_id集合
        
        # 服务端连接
        self.server_client: Client_server = None
        
        # 下载线程列表
        self.active_download_threads = []
        
        # 队列监听线程
        self.queue_thread = ImageViewerQueueThread("image_viewer_queue_thread", self)
        queue = global_setting.get_setting("queue", None)
        if queue:
            self.queue_thread.queue = queue
            self.queue_thread.start()
            logger.info("图片数据查看器队列监听线程已启动")
        
        # 用于动态添加区域的引用
        self.grid_layout = None
        
        # 初始化 UI
        self.init_ui()
        
        # 连接信号
        self.update_data_signal.connect(self.on_new_image_received)
    
    def showEvent(self, a0: typing.Optional[QtGui.QShowEvent]) -> None:
        """窗口显示事件"""
        logger.info("几何量图片数据查看器窗口显示")
        super().showEvent(a0)
    
    def hideEvent(self, a0: typing.Optional[QtGui.QHideEvent]) -> None:
        """窗口隐藏事件"""
        logger.info("几何量图片数据查看器窗口隐藏")
        super().hideEvent(a0)
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        # 停止所有下载线程
        if hasattr(self, 'active_download_threads'):
            for thread in self.active_download_threads:
                if thread.isRunning():
                    thread.terminate()
                    thread.wait(1000)
            logger.info(f"已停止 {len(self.active_download_threads)} 个下载线程")
        
        # 停止队列监听线程
        if hasattr(self, 'queue_thread') and self.queue_thread:
            self.queue_thread.stop()
            logger.info("图片数据查看器队列监听线程已停止")
        
        super().closeEvent(event)
    
    def init_ui(self):
        """初始化界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        
        # 顶部信息栏
        info_layout = QHBoxLayout()
        self.status_label = QLabel("状态: 等待数据...")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        info_layout.addWidget(self.status_label)
        info_layout.addStretch()
        
        self.clear_all_btn = QPushButton("清空显示")
        self.clear_all_btn.clicked.connect(self.clear_all_displays)
        info_layout.addWidget(self.clear_all_btn)
        
        main_layout.addLayout(info_layout)
        
        # 选项卡
        self.tab_widget = QTabWidget()
        
        # 实时识别选项卡
        self.realtime_tab = self.create_realtime_tab()
        self.tab_widget.addTab(self.realtime_tab, "实时识别")
        
        # 历史识别选项卡
        self.history_tab = self.create_history_tab()
        self.tab_widget.addTab(self.history_tab, "历史识别")
        
        main_layout.addWidget(self.tab_widget)
    
    def create_device_image_tab(self, device_id: str) -> QWidget:
        """
        为设备创建图片显示选项卡
        ✅ 不初始化区域，等下载完成后动态添加
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 当前批次信息
        info_group = QGroupBox("当前批次信息")
        info_layout = QHBoxLayout(info_group)
        device_label = QLabel(f"设备: {device_id}")
        batch_label = QLabel("接收时间: --")
        count_label = QLabel("图片数量: 0")
        info_layout.addWidget(device_label)
        info_layout.addWidget(batch_label)
        info_layout.addWidget(count_label)
        info_layout.addStretch()
        layout.addWidget(info_group)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # 2列网格布局（可动态扩展到20个）
        grid_layout = QGridLayout()
        grid_layout.setSpacing(10)
        
        scroll_layout.addLayout(grid_layout)
        scroll_layout.addStretch()
        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_widget)
        
        layout.addWidget(scroll_area)
        
        # 保存引用
        tab.device_id = device_id
        tab.image_widgets = []  # ✅ 初始为空，动态添加
        tab.grid_layout = grid_layout
        tab.info_labels = {
            'device': device_label,
            'batch': batch_label,
            'count': count_label
        }
        
        logger.info(f"创建设备选项卡: {device_id}, 初始区域数量: 0")
        
        return tab
    
    def create_realtime_tab(self) -> QWidget:
        """创建实时识别选项卡（多设备选项卡）"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # ✅ 多设备选项卡
        self.device_image_tabs = QTabWidget()
        
        # 暂时添加占位选项卡
        placeholder_widget = QWidget()
        placeholder_layout = QVBoxLayout(placeholder_widget)
        placeholder_layout.addWidget(QLabel("等待数据..."))
        self.device_image_tabs.addTab(placeholder_widget, "无设备")
        
        layout.addWidget(self.device_image_tabs)
        
        return tab
    
    def create_history_tab(self) -> QWidget:
        """创建历史识别选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 筛选区域
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("设备:"))
        self.history_device_combo = QComboBox()
        self.history_device_combo.addItem("全部设备")
        filter_layout.addWidget(self.history_device_combo)
        
        filter_layout.addWidget(QLabel("图片类型:"))
        self.history_type_combo = QComboBox()
        self.history_type_combo.addItems(["全部类型", "brightness", "contrast", "其他"])
        filter_layout.addWidget(self.history_type_combo)
        
        filter_btn = QPushButton("筛选")
        filter_btn.clicked.connect(self.filter_history)
        filter_layout.addWidget(filter_btn)
        
        filter_layout.addStretch()
        layout.addLayout(filter_layout)
        
        # 分割器：列表和详情
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧：历史记录列表
        list_widget = QWidget()
        list_layout = QVBoxLayout(list_widget)
        list_layout.addWidget(QLabel("历史记录列表:"))
        
        self.history_list = QListWidget()
        self.history_list.itemClicked.connect(self.on_history_item_clicked)
        list_layout.addWidget(self.history_list)
        
        splitter.addWidget(list_widget)
        
        # 右侧：详情显示
        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)
        detail_layout.addWidget(QLabel("详情:"))
        
        # 原图和识别图并排显示
        images_layout = QHBoxLayout()
        
        history_original_group = QGroupBox("原图")
        history_original_layout = QVBoxLayout(history_original_group)
        self.history_original_label = QLabel()
        self.history_original_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.history_original_label.setMinimumSize(300, 300)
        self.history_original_label.setStyleSheet("border: 1px solid #ccc; background: #f5f5f5;")
        history_original_layout.addWidget(self.history_original_label)
        images_layout.addWidget(history_original_group)
        
        history_recognized_group = QGroupBox("识别图")
        history_recognized_layout = QVBoxLayout(history_recognized_group)
        self.history_recognized_label = QLabel()
        self.history_recognized_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.history_recognized_label.setMinimumSize(300, 300)
        self.history_recognized_label.setStyleSheet("border: 1px solid #ccc; background: #f5f5f5;")
        history_recognized_layout.addWidget(self.history_recognized_label)
        images_layout.addWidget(history_recognized_group)
        
        detail_layout.addLayout(images_layout)
        
        # 图片信息
        self.history_info_label = QLabel("选择一条记录查看详情")
        self.history_info_label.setWordWrap(True)
        detail_layout.addWidget(self.history_info_label)
        
        splitter.addWidget(detail_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        
        layout.addWidget(splitter)
        
        return tab
    
    def on_new_image_received(self, data: dict):
        """
        接收到新图片数据的槽函数
        data 格式: {
            'type': 'image_upload',
            'device_id': 'xxx',
            'file_id': 123,
            'file_name': 'xxx.png',
            'file_size': 234567,
            'timestamp': '2025-12-11T12:00:00'
        }
        """
        logger.info(f"收到新几何量图片通知: {data}")
        
        device_id = data.get('device_id', 'unknown')
        file_id = data.get('file_id')
        file_name = data.get('file_name', 'unknown')
        timestamp = data.get('timestamp', datetime.now().isoformat())
        
        # 更新状态
        self.status_label.setText(f"状态: 正在下载 - 设备 {device_id}")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: orange;")
        
        # 从服务端下载图片（使用线程避免阻塞 UI）
        if file_id and self.server_client:
            try:
                # 创建 data 目录
                data_dir = Path("data/image") / device_id
                data_dir.mkdir(parents=True, exist_ok=True)
                
                # 下载文件
                save_path = data_dir / file_name
                
                # 创建下载线程
                download_thread = ImageDownloadThread(
                    client=self.server_client.client,
                    file_id=file_id,
                    save_path=save_path,
                    device_id=device_id
                )
                
                # 连接信号（使用 Qt.ConnectionType.QueuedConnection 确保在主线程执行）
                download_thread.download_finished.connect(
                    self.on_image_download_finished,
                    Qt.ConnectionType.QueuedConnection
                )
                download_thread.download_failed.connect(
                    self.on_image_download_failed,
                    Qt.ConnectionType.QueuedConnection
                )
                download_thread.finished.connect(
                    lambda t=download_thread: self.on_thread_finished(t),
                    Qt.ConnectionType.QueuedConnection
                )
                
                # 添加到活跃线程列表
                self.active_download_threads.append(download_thread)
                
                # 启动下载
                download_thread.start()
                
                logger.info(f"启动图片下载线程: {file_name}, 活跃线程数: {len(self.active_download_threads)}")
                
            except Exception as e:
                logger.error(f"启动下载失败: {e}")
                self.status_label.setText(f"状态: 下载失败 - {str(e)}")
                self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: red;")
        else:
            logger.warning("缺少 file_id 或 server_client 未初始化")
    
    def get_or_create_device_image_tab(self, device_id: str):
        """
        获取或创建设备的图片显示选项卡
        ✅ 线程安全：加锁防止重复创建
        ✅ 防止并发创建：使用标记集合
        """
        with self.widget_access_lock:  # ✅ 加锁保护
            logger.debug(f"查找设备选项卡: {device_id}, 当前选项卡数量: {self.device_image_tabs.count()}")

            # ✅ 查找是否已存在
            for i in range(self.device_image_tabs.count()):
                tab = self.device_image_tabs.widget(i)
                tab_text = self.device_image_tabs.tabText(i)
                logger.debug(f"检查选项卡{i}: tabText='{tab_text}', hasattr(device_id)={hasattr(tab, 'device_id')}, device_id={getattr(tab, 'device_id', 'N/A')}")
                
                if hasattr(tab, 'device_id') and tab.device_id == device_id:
                    logger.info(f"✅ 找到现有设备选项卡: {device_id} (索引{i})")
                    return tab
            
            # ✅ 检查是否正在创建中
            if device_id in self.creating_device_tabs:
                logger.warning(f"⚠️ 设备 {device_id} 的tab正在创建中，等待完成...")
                # 等待创建完成后再次查找
                import time
                for _ in range(10):  # 最多等待1秒
                    time.sleep(0.1)
                    for i in range(self.device_image_tabs.count()):
                        tab = self.device_image_tabs.widget(i)
                        if hasattr(tab, 'device_id') and tab.device_id == device_id:
                            logger.info(f"✅ 等待后找到设备选项卡: {device_id}")
                            return tab
                logger.error(f"❌ 等待超时，强制创建: {device_id}")
            
            # ✅ 标记为正在创建
            self.creating_device_tabs.add(device_id)
            logger.info(f"开始创建设备选项卡: {device_id}")
            
            try:
                # 创建新的设备tab
                device_tab = self.create_device_image_tab(device_id)
                
                # 移除占位选项卡
                if self.device_image_tabs.count() == 1 and self.device_image_tabs.tabText(0) == "无设备":
                    logger.info("移除占位选项卡")
                    self.device_image_tabs.removeTab(0)
                
                # 添加新选项卡
                tab_index = self.device_image_tabs.addTab(device_tab, device_id)
                self.device_image_tabs.setCurrentIndex(tab_index)
                
                logger.info(f"✅ 创建完成: {device_id} (索引{tab_index}), 当前总数: {self.device_image_tabs.count()}")
                
                return device_tab
                
            finally:
                # ✅ 创建完成，移除标记
                self.creating_device_tabs.discard(device_id)
                logger.debug(f"移除创建标记: {device_id}")
    
    def get_next_widget_for_device(self, device_tab):
        """
        为设备获取下一个显示区域
        
        ✅ 新策略（简化版）：
        1. 如果区域数量 < 20：创建新区域
        2. 如果区域数量 = 20：FIFO前移所有图片，新图片放在最后
        
        ✅ 线程安全：使用锁保护整个方法
        
        Args:
            device_tab: 设备选项卡对象
        
        Returns:
            ImageDisplayWidget: 新创建或重用的显示区域
        """
        with self.widget_access_lock:
            image_widgets = device_tab.image_widgets
            grid_layout = device_tab.grid_layout
            current_count = len(image_widgets)
            
            logger.info(f"[设备{device_tab.device_id}] 当前区域数量: {current_count}/{self.max_widget_count}")
            
            # ✅ 策略1: 未达到最大数量，创建新区域
            if current_count < self.max_widget_count:
                index = current_count
                row = index // 2
                col = index % 2
                
                # 创建新的显示区域
                display_widget = ImageDisplayWidget(index)
                image_widgets.append(display_widget)
                grid_layout.addWidget(display_widget, row, col)
                
                logger.info(f"[设备{device_tab.device_id}] ✅ 创建新区域 {index}，总数: {len(image_widgets)}")
                return display_widget
            
            # ✅ 策略2: 达到最大数量，FIFO前移
            logger.info(f"[设备{device_tab.device_id}] 达到最大数量，执行FIFO前移")
            
            # 将所有图片向前移动一位
            for i in range(self.max_widget_count - 1):
                source_widget = image_widgets[i + 1]
                target_widget = image_widgets[i]
                
                # 复制图片路径
                if source_widget.original_image_path:
                    target_widget.load_original_image(source_widget.original_image_path)
                    logger.debug(f"[设备{device_tab.device_id}] 区域{i+1}图片移动到区域{i}")
                else:
                    target_widget.clear()
            
            # 清空最后一个区域，准备接收新图片
            last_widget = image_widgets[self.max_widget_count - 1]
            last_widget.clear()
            
            logger.info(f"[设备{device_tab.device_id}] ✅ FIFO前移完成，返回最后区域 {self.max_widget_count - 1}")
            return last_widget
    
    def get_next_display_widget(self):
        """
        获取下一个要使用的显示区域（FIFO队列方式）
        - 按顺序填充8个基础区域
        - 填满后继续添加，最多到20个
        - 超过20个后，循环覆盖（从第0个开始）
        """
        current_count = len(self.image_display_widgets)
        
        # 如果当前区域数量 < 20，且需要新区域
        if self.next_widget_index >= current_count and current_count < self.max_widget_count:
            # 添加新区域
            logger.info(f"添加新区域，当前数量: {current_count}, 需要索引: {self.next_widget_index}")
            self.ensure_display_capacity(self.next_widget_index + 1)
        
        # 获取区域（循环使用）
        widget_index = self.next_widget_index % len(self.image_display_widgets)
        widget = self.image_display_widgets[widget_index]
        
        logger.info(f"使用区域 {widget_index}（next_index={self.next_widget_index}, total={len(self.image_display_widgets)}）")
        
        # 如果区域已有图片，先清空（循环覆盖）
        if widget.original_image_path:
            logger.info(f"区域 {widget_index} 已有图片，将被覆盖")
            widget.clear()
        
        # 更新索引
        self.next_widget_index += 1
        
        return widget
    
    def load_images_batch(self, image_paths: list, device_id: str = ""):
        """
        批量加载图片
        Args:
            image_paths: 图片路径列表
            device_id: 设备 ID
        """
        # 更新批次信息
        self.current_device_label.setText(f"设备: {device_id}")
        self.current_batch_label.setText(f"接收时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.current_count_label.setText(f"图片数量: {len(image_paths)}")
        
        # 加载图片到各个显示组件
        for i, image_path in enumerate(image_paths):
            if i < len(self.image_display_widgets):
                self.image_display_widgets[i].load_original_image(Path(image_path))
        
        logger.info(f"批量加载 {len(image_paths)} 张图片")
    
    def check_download_results(self):
        """
        定时器回调：检查下载结果队列
        轮询间隔：100ms
        """
        # 一次只处理一个结果（避免UI阻塞）
        if self.image_downloader.has_results():
            result = self.image_downloader.get_result()
            if result:
                if result.success:
                    self.on_image_download_finished(result.file_path, result.device_id)
                else:
                    self.on_image_download_failed(result.error, result.device_id)
    
    def on_image_download_finished(self, file_path: str, device_id: str):
        """图片下载完成回调"""
        logger.info(f"========== 下载完成：{Path(file_path).name}, 设备：{device_id} ==========")
        
        self.status_label.setText(f"状态: 下载完成 - 设备 {device_id}")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: green;")
        
        # ✅ 获取或创建设备选项卡（方法内部已加锁）
        device_tab = self.get_or_create_device_image_tab(device_id)
        if not device_tab:
            logger.error(f"无法获取设备选项卡: {device_id}")
            return

        # ✅ 获取显示区域（方法内部已加锁）
        target_widget = self.get_next_widget_for_device(device_tab)
        if not target_widget:
            logger.error("无法获取显示区域")
            return

        # 加载图片
        target_widget.load_original_image(Path(file_path))
        logger.info(f"[设备{device_id}] ✅ 图片已加载到区域 {target_widget.index}: {Path(file_path).name}")

        # 保存到历史记录
        record = {
            'device_id': device_id,
            'file_name': Path(file_path).name,
            'original_path': file_path,
            'recognized_path': file_path,  # 识别后会更新
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        self.history_records.append(record)
        self.update_history_list()

        # ✅ 更新设备选项卡的显示信息（读取操作，锁在 get_next_widget_for_device 中已保护写入）
        with self.widget_access_lock:
            current_count = sum(1 for w in device_tab.image_widgets if w.original_image_path)
            widget_count = len(device_tab.image_widgets)

        device_tab.info_labels['count'].setText(f"图片数量: {current_count}/{widget_count}")
        device_tab.info_labels['batch'].setText(f"最后接收: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        logger.info(f"图片文件下载并显示成功: {file_path}，设备: {device_id}，区域: {target_widget.index if target_widget else 'Unknown'}")
    
    def on_image_download_failed(self, error: str, device_id: str):
        """图片下载失败回调"""
        self.status_label.setText(f"状态: 下载失败 - 设备 {device_id} - {error}")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: red;")
    
    def on_thread_finished(self, thread):
        """线程完成回调，清理线程引用"""
        try:
            if thread in self.active_download_threads:
                self.active_download_threads.remove(thread)
                logger.info(f"下载线程已完成并清理，剩余活跃线程: {len(self.active_download_threads)}")
        except Exception as e:
            logger.error(f"清理线程失败: {e}")
    
    def ensure_display_capacity(self, required_count: int):
        """
        确保有足够的显示区域
        如果需要的数量 > 当前区域数量，则动态添加
        """
        current_count = len(self.image_display_widgets)
        
        if required_count > current_count:
            # 需要添加更多区域
            add_count = required_count - current_count
            logger.info(f"需要添加 {add_count} 个显示区域（当前 {current_count}，需要 {required_count}）")
            
            for i in range(add_count):
                index = current_count + i
                display_widget = ImageDisplayWidget(index)
                
                # 计算网格位置（2列布局）
                row = index // 2
                col = index % 2
                
                # 添加到网格
                self.grid_layout.addWidget(display_widget, row, col)
                self.image_display_widgets.append(display_widget)
            
            logger.info(f"已添加 {add_count} 个临时显示区域，总数: {len(self.image_display_widgets)}")
    
    def shrink_display_widgets(self, target_count: int):
        """
        收缩显示区域到目标数量
        如果当前区域数量 > 基础数量（8），且所有额外区域都为空，则释放
        """
        current_count = len(self.image_display_widgets)
        
        if current_count > self.base_widget_count and target_count <= self.base_widget_count:
            # 检查是否可以收缩（额外区域都为空）
            can_shrink = True
            for i in range(self.base_widget_count, current_count):
                if self.image_display_widgets[i].original_image_path:
                    can_shrink = False
                    break
            
            if can_shrink:
                # 移除额外的区域
                remove_count = current_count - self.base_widget_count
                for i in range(remove_count):
                    widget = self.image_display_widgets.pop()
                    self.grid_layout.removeWidget(widget)
                    widget.deleteLater()
                
                logger.info(f"已释放 {remove_count} 个临时显示区域，剩余: {len(self.image_display_widgets)}")
    
    def clear_all_displays(self):
        """清空所有显示区域"""
        for widget in self.image_display_widgets:
            widget.clear()
        
        self.current_device_label.setText("设备: --")
        self.current_batch_label.setText("接收时间: --")
        self.current_count_label.setText("图片数量: 0")
        
        # ✅ 重置队列索引
        self.next_widget_index = 0
        
        # 收缩到基础数量
        self.shrink_display_widgets(self.base_widget_count)
        
        logger.info("已清空所有显示区域，重置队列索引")
    
    def update_history_list(self):
        """更新历史记录列表"""
        self.history_list.clear()
        
        for record in self.history_records:
            device_id = record.get('device_id', 'unknown')
            file_name = record.get('file_name', 'unknown')
            timestamp = record.get('timestamp', '')
            
            item_text = f"[{timestamp[:19]}] {device_id} - {file_name}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, record)
            self.history_list.addItem(item)
    
    def on_history_item_clicked(self, item: QListWidgetItem):
        """历史记录项点击"""
        record = item.data(Qt.ItemDataRole.UserRole)
        
        # 显示详情
        original_path = record.get('original_path')
        recognized_path = record.get('recognized_path')
        
        if original_path and Path(original_path).exists():
            # 加载原图
            pixmap = QPixmap(str(original_path))
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    300, 300,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.history_original_label.setPixmap(scaled_pixmap)
            else:
                self.history_original_label.setText("无法加载图片")
                logger.error(f"无法加载图片: {original_path}")
        else:
            self.history_original_label.setText("原图不存在")
            logger.warning(f"原图路径不存在: {original_path}")
        
        # 加载识别图
        if recognized_path and Path(recognized_path).exists():
            recognized_pixmap = QPixmap(str(recognized_path))
            if not recognized_pixmap.isNull():
                scaled_recognized_pixmap = recognized_pixmap.scaled(
                    300, 300,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.history_recognized_label.setPixmap(scaled_recognized_pixmap)
            else:
                self.history_recognized_label.setText("无法加载识别图")
        else:
            # 识别图使用原图（当前识别功能返回原图）
            if original_path and Path(original_path).exists():
                pixmap = QPixmap(str(original_path))
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(
                        300, 300,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    self.history_recognized_label.setPixmap(scaled_pixmap)
            else:
                self.history_recognized_label.setText("暂无识别图")
        
        # 显示信息
        info_text = f"设备: {record.get('device_id')}\n"
        info_text += f"文件: {record.get('file_name')}\n"
        info_text += f"时间: {record.get('timestamp')}\n"
        info_text += f"原图: {original_path}\n"
        info_text += f"识别图: {recognized_path if recognized_path else '未识别'}"
        self.history_info_label.setText(info_text)
    
    def filter_history(self):
        """筛选历史记录"""
        # TODO: 实现筛选逻辑
        logger.info("筛选历史记录")
    
    def set_server_client(self, client: Client_server):
        """设置服务端客户端"""
        self.server_client = client

