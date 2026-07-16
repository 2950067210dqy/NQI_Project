"""
几何量图片数据查看器主窗口
包含两个选项卡：
1. 实时识别 - 2列4行共8个区域显示原图和识别图
2. 历史识别 - 查看所有历史识别记录
"""
import typing
import threading
import hashlib
from datetime import datetime
from pathlib import Path

from PyQt6 import QtGui
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
                              QLabel, QPushButton, QGroupBox, QGridLayout,
                              QScrollArea, QListWidget, QListWidgetItem,
                              QSplitter, QFrame, QComboBox, QTableWidget, QTableWidgetItem,
                              QPlainTextEdit, QHeaderView, QFileDialog, QMessageBox, QProgressBar, QApplication)
from PyQt6.QtGui import QPixmap
from loguru import logger

from Service.connect_server_service.index.Client_server import Client_server
from theme.ThemeQt6 import ThemedWindow
from public.entity.MyQThread import MyQThread
from public.config_class.global_setting import global_setting
from public.function.Cache.cache_manager import cache_manager
from public.function.Cache.data_download_manager import download_manager
from public.util.alarm_message_formatter import format_alarm_message


class ImageViewerQueueThread(MyQThread):
    """队列监听线程 - 监听跨进程消息"""
    
    def __init__(self, name, window):
        super().__init__(name)
        self.queue = None
        self.window = window  # 窗口引用
    
    def dosomething(self):
        """监听队列消息"""
        if not self.queue.empty():
            try:
                from public.entity.queue.ObjectQueueItem import ObjectQueueItem
                message: ObjectQueueItem = self.queue.get()
                if message and not message.is_Empty():
                    logger.critical(f"{self.name}:{message}")
                    if isinstance(message, ObjectQueueItem) and message.to == 'image_data_viewer':
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


class ImageDisplayWidget(QFrame):
    """单个图片显示组件（包含原图和识别图）"""
    
    def __init__(self, index: int, parent=None):
        super().__init__(parent)
        self.index = index
        self.original_image_path = None
        self.recognized_image_path = None
        self.has_fault = None  # 识别结果
        
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
        self.original_label.setFixedSize(150, 150)  # 固定大小
        self.original_label.setStyleSheet("border: 1px solid #ccc; background: #f5f5f5;")
        self.original_label.setScaledContents(False)
        original_layout.addWidget(self.original_label)
        images_layout.addWidget(original_group)
        
        # 识别图区域
        recognized_group = QGroupBox("识别图")
        recognized_layout = QVBoxLayout(recognized_group)
        self.recognized_label = QLabel()
        self.recognized_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.recognized_label.setFixedSize(150, 150)  # 固定大小
        self.recognized_label.setStyleSheet("border: 1px solid #ccc; background: #f5f5f5;")
        self.recognized_label.setScaledContents(False)
        recognized_layout.addWidget(self.recognized_label)
        
        # 识别结果标签
        self.recognition_result_label = QLabel("等待识别...")
        self.recognition_result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.recognition_result_label.setStyleSheet("font-size: 10px; font-weight: bold;")
        recognized_layout.addWidget(self.recognition_result_label)
        
        images_layout.addWidget(recognized_group)
        
        layout.addLayout(images_layout)
        
        # 状态显示
        self.status_label = QLabel("等待数据...")
        self.status_label.setStyleSheet("color: gray; font-size: 10px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
    
    def load_original_image(self, image_path: Path):
        """加载原图，识别结果由服务端分析后单独回填。"""
        try:
            self.original_image_path = image_path
            self.filename_label.setText(image_path.name)
            pixmap = QPixmap(str(image_path))
            if pixmap.isNull():
                raise Exception("无法加载图片")
            scaled_pixmap = pixmap.scaled(
                self.original_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.original_label.setPixmap(scaled_pixmap)
            self.recognized_label.setPixmap(scaled_pixmap)
            self.recognition_result_label.setText("等待服务器分析...")
            self.recognition_result_label.setStyleSheet("font-size: 10px; font-weight: bold; color: #666;")
            self.status_label.setText("已加载")
            self.status_label.setStyleSheet("color: green; font-size: 10px;")
            logger.info(f"位置 {self.index + 1} 加载原图: {image_path.name}")
        except Exception as e:
            logger.error(f"加载图片失败: {e}")
            self.status_label.setText("加载失败")
            self.status_label.setStyleSheet("color: red; font-size: 10px;")

    def load_recognized_image(self, image_path: Path, has_fault: bool = False, summary: str = ''):
        """加载识别图并显示服务端分析结果。"""
        try:
            self.recognized_image_path = image_path
            self.has_fault = has_fault
            pixmap = QPixmap(str(image_path))
            if pixmap.isNull():
                raise Exception("无法加载图片")
            scaled_pixmap = pixmap.scaled(
                self.recognized_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.recognized_label.setPixmap(scaled_pixmap)
            if has_fault:
                self.recognition_result_label.setText("识别故障 ⚠")
                self.recognition_result_label.setStyleSheet("color: red; font-size: 11px; font-weight: bold;")
            else:
                self.recognition_result_label.setText("未识别故障 ✓")
                self.recognition_result_label.setStyleSheet("color: green; font-size: 11px; font-weight: bold;")
            self.status_label.setText(summary or "识别完成")
            self.status_label.setStyleSheet("color: blue; font-size: 10px;")
            logger.info(f"位置 {self.index + 1} 加载识别图: {image_path}, 故障: {has_fault}")
        except Exception as e:
            logger.error(f"加载识别图失败: {e}")

    def apply_server_analysis(self, analysis_result: dict, fallback_image_path: Path):
        """应用服务端分析结果。"""
        analysis_result = analysis_result or {}
        has_fault = analysis_result.get('has_fault', False)
        summary = analysis_result.get('analysis_summary', '')
        self.load_recognized_image(fallback_image_path, has_fault, summary)

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
    cache_update_signal = pyqtSignal(str, str)  # file_path, device_id - 从队列线程发送到主线程
    
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
        
        # 窗口状态
        self.is_visible = False  # 窗口是否可见
        
        # UI组件
        self.log_text = None  # 日志文本框（稍后创建）
        self.realtime_loading_bar = None  # 实时识别页加载条
        self.realtime_loading_label = None
        self._realtime_loading_count = 0
        
        # 服务端连接
        self.server_client: Client_server = None
        
        # 下载线程列表
        self.active_download_threads = []
        self.cache_bootstrap_started = False
        self.history_cache_loaded = False
        self.latest_cache_loaded = False
        self.displayed_image_file_ids = set()  # 记录实时识别页已显示的图片，避免同一张图被多次插入。
        
        # 队列监听线程
        self.queue_thread = ImageViewerQueueThread("image_viewer_queue_thread", self)
        queue = global_setting.get_setting("queue", None)
        if queue:
            self.queue_thread.queue = queue
            # 跨进程消息由主窗口统一分发，避免多个线程争抢同一队列。
            logger.info("图片数据查看器已使用主窗口统一消息分发")
        
        # 用于动态添加区域的引用
        self.grid_layout = None
        
        # 初始化 UI
        self.init_ui()
        
        # 连接缓存更新信号（从队列线程到主线程）
        self.cache_update_signal.connect(
            self.on_cache_data_ready,
            Qt.ConnectionType.QueuedConnection
        )
        # 启动阶段不阻塞主界面；缓存改为在页面显示后后台加载。
        self.report_background_task('主界面已显示，等待加载服务器几何量数据')
    

    def showEvent(self, a0: typing.Optional[QtGui.QShowEvent]) -> None:
        """窗口显示事件"""
        logger.info("几何量图片数据查看器窗口已显示")
        self.is_visible = True
        super().showEvent(a0)
        if not self.cache_bootstrap_started:
            self.cache_bootstrap_started = True
            self.report_background_task('正在从服务器加载几何量分析结果')
            QTimer.singleShot(120, self.bootstrap_cache_load)

    def hideEvent(self, a0: typing.Optional[QtGui.QHideEvent]) -> None:
        """窗口隐藏事件"""
        logger.info("几何量图片数据查看器窗口隐藏")
        self.is_visible = False
        super().hideEvent(a0)

    def closeEvent(self, event):
        """窗口关闭事件"""
        if hasattr(self, 'queue_thread') and self.queue_thread:
            self.queue_thread.stop()
            logger.info("图片数据查看器队列监听线程已停止")
        super().closeEvent(event)

    def report_background_task(self, message: str):
        """把几何量页面后台任务同步到主窗口状态栏。"""
        try:
            if self.main_gui is not None and getattr(self.main_gui, 'status_bar', None) is not None:
                self.main_gui.status_bar.update_background_task(message)
        except Exception:
            pass

    def _begin_realtime_loading(self, text: str = "正在加载几何量实时数据..."):
        """显示实时识别页内加载条；下载远程图片时给用户持续反馈。"""
        self._realtime_loading_count += 1
        if self.realtime_loading_label is not None:
            self.realtime_loading_label.setText(text)
            self.realtime_loading_label.setVisible(True)
        if self.realtime_loading_bar is not None:
            self.realtime_loading_bar.setRange(0, 0)
            self.realtime_loading_bar.setVisible(True)
        QApplication.processEvents()

    def _end_realtime_loading(self):
        """隐藏实时识别页内加载条，支持嵌套加载调用。"""
        if self._realtime_loading_count > 0:
            self._realtime_loading_count -= 1
        if self._realtime_loading_count > 0:
            return
        if self.realtime_loading_label is not None:
            self.realtime_loading_label.setVisible(False)
        if self.realtime_loading_bar is not None:
            self.realtime_loading_bar.setVisible(False)

    def _get_api_client(self):
        """返回页面用于读取服务器分析结果的 API 客户端。"""
        return getattr(self.server_client, 'client', None) if self.server_client else None

    def _fetch_image_records(self, device_id: str = None, limit: int = 100):
        """直接从服务端读取图片记录列表。"""
        api = self._get_api_client()
        if api is None:
            return []
        response = api.list_image_data(device_id=device_id, limit=limit, skip=0) or {}
        return list(response.get('data', []))

    def _fetch_image_detail(self, file_id: int):
        """读取包含 analysis_result 的完整图片记录。"""
        api = self._get_api_client()
        if api is None:
            return None
        response = api.get_image_detail(file_id) or {}
        return response.get('data')

    def _normalize_image_record(self, record: dict) -> dict:
        """统一列表/详情记录结构。"""
        record = record or {}
        analysis_result = record.get('analysis_result') or {}
        upload_time = record.get('upload_time') or ''
        return {
            'file_id': record.get('id') or record.get('file_id'),
            'device_id': record.get('device_id', ''),
            'file_name': record.get('file_name', ''),
            'timestamp': upload_time.replace('T', ' ')[:19] if upload_time else '',
            'upload_time': upload_time,
            'file_path': record.get('file_path', ''),
            'recognized_path': analysis_result.get('recognized_path') or record.get('recognized_path') or record.get('file_path', ''),
            'analysis_result': analysis_result,
            'processing_status': record.get('processing_status', ''),
            'processing_error': record.get('processing_error'),
            'image_type': record.get('image_type', ''),
            'alarm_info': record.get('alarm_info') or {},
        }

    def _format_alarm_text(self, alarm_info: dict) -> str:
        """把服务端预警结构转换为几何量页面可读的中文文本。"""
        alarm_info = alarm_info or {}
        if not alarm_info.get('has_alarm'):
            return "无预警"
        severity_map = {"critical": "严重", "warning": "预警", "info": "提示"}
        severity = severity_map.get(alarm_info.get('severity'), alarm_info.get('severity') or "预警")
        # 历史记录可能仍包含 sharpness_score、lt 等内部编码，显示前统一翻译为中文。
        message = format_alarm_message(alarm_info.get('message') or "检测到预警")
        created_at = (alarm_info.get('created_at') or '').replace('T', ' ')[:19]
        return f"[{severity}] {created_at} {message}".strip()

    def _make_alarm_table_item(self, alarm_info: dict) -> QTableWidgetItem:
        """创建预警表格单元格，有预警时用红色并保留完整 tooltip。"""
        text = self._format_alarm_text(alarm_info)
        item = QTableWidgetItem(text)
        item.setToolTip(text)
        if (alarm_info or {}).get('has_alarm'):
            item.setForeground(Qt.GlobalColor.red)
        return item

    def _get_preview_cache_dir(self) -> Path:
        """Store remote image previews locally so QPixmap can render them."""
        cache_dir = Path.home() / ".nqi_upper_cache" / "image_preview"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    def _build_remote_file_url(self, file_path: str):
        """Build a server URL for a relative file path returned by the API."""
        if not file_path:
            return None
        normalized = str(file_path).replace(chr(92), "/")
        if normalized.startswith("http://") or normalized.startswith("https://"):
            return normalized
        uploads_index = normalized.lower().find("/uploads/")
        if uploads_index >= 0:
            normalized = normalized[uploads_index:]
        api = self._get_api_client()
        if api is None:
            return None
        if normalized.startswith("uploads/"):
            normalized = f"/{normalized}"
        if normalized.startswith("/"):
            return f"{api.base_url}{normalized}"
        return f"{api.base_url}/{normalized}"

    def _ensure_local_image_path(self, file_path: str, file_id=None, fallback_name: str = "image.png"):
        """Resolve a server image path into a local file that QPixmap can open."""
        try:
            if file_path:
                local_path = Path(file_path)
                if local_path.exists():
                    return local_path
            api = self._get_api_client()
            cache_dir = self._get_preview_cache_dir()
            suffix = Path(fallback_name).suffix or ".png"
            if file_id and api is not None:
                download_path = cache_dir / f"image_{file_id}{suffix}"
                if not download_path.exists():
                    api.download_image_file(int(file_id), download_path)
                if download_path.exists():
                    return download_path
            remote_url = self._build_remote_file_url(file_path)
            if remote_url is None or api is None:
                return None
            cache_name = hashlib.md5(remote_url.encode("utf-8")).hexdigest() + suffix
            cache_path = cache_dir / cache_name
            if cache_path.exists():
                return cache_path
            response = api.session.get(remote_url, timeout=api.timeout)
            response.raise_for_status()
            cache_path.write_bytes(response.content)
            return cache_path
        except Exception as exc:
            logger.warning(f"图片路径解析失败: file_path={file_path}, file_id={file_id}, error={exc}")
            return None


    def _download_image_record(self, record: dict):
        """Download one image record to a user-selected folder."""
        api = self._get_api_client()
        normalized = self._normalize_image_record(record)
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
        save_path = Path(target_dir) / normalized.get("file_name", f"image_{normalized['file_id']}.png")

        def task():
            api.download_image_file(int(normalized["file_id"]), save_path)
            return save_path

        def on_success(downloaded_path: Path):
            self.status_label.setText(f"状态: 已下载 - {normalized.get('file_name', '')}")
            self.log_message(f"图片已下载: {downloaded_path}")

        self.run_async_task(
            task,
            on_success=on_success,
            on_error=lambda message: QMessageBox.critical(self, "下载失败", message),
            loading_text=f"正在下载 {normalized.get('file_name', '')}...",
            widgets=[getattr(self, "cache_image_table", None)],
        )


    def _display_history_record(self, record: dict):
        """Display one image record in the history detail panel."""
        normalized = self._normalize_image_record(record)
        original_remote = self._build_remote_file_url(normalized.get("file_path")) or normalized.get("file_path") or ""
        recognized_remote = self._build_remote_file_url(normalized.get("recognized_path")) or normalized.get("recognized_path") or original_remote
        original_local = record.get("original_local_path") or self._ensure_local_image_path(
            normalized.get("file_path"),
            normalized.get("file_id"),
            normalized.get("file_name") or "image.png",
        )
        recognized_local = record.get("recognized_local_path") or self._ensure_local_image_path(
            normalized.get("recognized_path"),
            None,
            f"recognized_{normalized.get('file_name', 'image.png')}",
        ) or original_local
        self.history_original_label.clear()
        self.history_recognized_label.clear()
        if original_local and Path(original_local).exists():
            pixmap = QPixmap(str(original_local))
            if not pixmap.isNull():
                self.history_original_label.setPixmap(pixmap.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.history_original_label.setText("原图不可用")
        if recognized_local and Path(recognized_local).exists():
            pixmap = QPixmap(str(recognized_local))
            if not pixmap.isNull():
                self.history_recognized_label.setPixmap(pixmap.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.history_recognized_label.setText("识别图不可用")
        has_fault = normalized.get("analysis_result", {}).get("has_fault", False)
        summary = normalized.get("analysis_result", {}).get("analysis_summary", "")
        if has_fault:
            self.history_recognition_result_label.setText("识别故障 ⚠")
            self.history_recognition_result_label.setStyleSheet("color: red; font-size: 14px; font-weight: bold;")
        else:
            self.history_recognition_result_label.setText("未识别故障 ✓")
            self.history_recognition_result_label.setStyleSheet("color: green; font-size: 14px; font-weight: bold;")
        alarm_text = self._format_alarm_text(normalized.get('alarm_info') or {})
        self.history_info_label.setText(
            f"设备: {normalized.get('device_id', '')}\n"
            f"文件: {normalized.get('file_name', '')}\n"
            f"时间: {normalized.get('timestamp', '')}\n"
            f"状态: {normalized.get('processing_status', '')}\n"
            f"结论: {summary}\n"
            f"预警信息: {alarm_text}\n"
            f"原图路径: {original_remote}\n"
            f"识别图路径: {recognized_remote}"
        )


    def _load_image_record_into_ui(self, record: dict) -> bool:
        """Safely load one server image record into the realtime tab."""
        try:
            normalized = self._normalize_image_record(record)
            if not normalized.get("file_id"):
                return False
            if normalized.get("processing_status") != "done":
                self.status_label.setText(f"状态: 等待服务端分析 - {normalized.get('device_id', '')}")
                self.log_message(f"图片仍在服务端处理中: {normalized.get('file_name', '')}")
                return False
            original_local = record.get("original_local_path") or self._ensure_local_image_path(normalized.get("file_path"), normalized.get("file_id"), normalized.get("file_name") or "image.png")
            recognized_local = record.get("recognized_local_path") or self._ensure_local_image_path(normalized.get("recognized_path"), None, f"recognized_{normalized.get('file_name', 'image.png')}") or original_local
            if not original_local or not Path(original_local).exists():
                self.log_message(f"原图路径不可用: {normalized.get('file_path', '')}")
                return False
            device_tab = self.get_or_create_device_image_tab(normalized["device_id"])
            target_widget = self.get_next_widget_for_device(device_tab)
            if not target_widget:
                return False
            target_widget.load_original_image(Path(original_local))
            target_widget.apply_server_analysis(normalized.get("analysis_result", {}), Path(recognized_local or original_local))
            device_tab.info_labels["batch"].setText(f"最后接收: {normalized.get('timestamp', '')}")
            self.displayed_image_file_ids.add(int(normalized["file_id"]))
            with self.widget_access_lock:
                current_count = sum(1 for widget in device_tab.image_widgets if widget.original_image_path)
                device_tab.info_labels["count"].setText(f"图片数量: {current_count}")
            # 实时识别区域加载完成后，同步把该文件对应的服务端预警显示到页面状态栏。
            if (normalized.get('alarm_info') or {}).get('has_alarm'):
                self.status_label.setText(f"状态: 已加载设备 {normalized.get('device_id', '')} 的图片；预警: {self._format_alarm_text(normalized.get('alarm_info'))}")
            else:
                self.status_label.setText(f"状态: 已加载设备 {normalized.get('device_id', '')} 的图片")
            return True
        except Exception as exc:
            logger.error(f"加载几何量实时数据失败: {exc}")
            self.log_message(f"加载几何量实时数据失败: {exc}")
            return False


    def init_ui(self):
        """初始化界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        info_layout = QHBoxLayout()
        self.status_label = QLabel("状态: 等待数据...")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        info_layout.addWidget(self.status_label)
        info_layout.addStretch()
        self.clear_all_btn = QPushButton("清空显示")
        self.clear_all_btn.clicked.connect(self.clear_all_displays)
        info_layout.addWidget(self.clear_all_btn)
        main_layout.addLayout(info_layout)
        self.tab_widget = QTabWidget()
        self.realtime_tab = self.create_realtime_tab()
        self.tab_widget.addTab(self.realtime_tab, "实时识别")
        self.history_tab = self.create_history_tab()
        self.tab_widget.addTab(self.history_tab, "历史识别")
        self.cache_tab = self.create_cache_table_tab()
        self.tab_widget.addTab(self.cache_tab, "服务器数据")
        self.log_tab = self.create_log_tab()
        self.tab_widget.addTab(self.log_tab, "日志")
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
    
    def bootstrap_cache_load(self):
        """Load image page data and keep a visible loading mask during startup refresh."""
        self.show_loading("正在加载几何量图片数据...")
        QTimer.singleShot(20000, self.hide_loading)
        try:
            self.load_latest_from_cache()
            self.load_history_from_cache()
            self.load_cache_images_to_table(show_loading=False)
            self.report_background_task("Image server data loaded")
        except Exception as exc:
            logger.error(f"Image server data load failed: {exc}")
            self.report_background_task(f"Image server data load failed: {exc}")
        finally:
            self.hide_loading()

    def create_realtime_tab(self) -> QWidget:
        """创建实时识别选项卡（多设备选项卡）"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        loading_layout = QHBoxLayout()
        self.realtime_loading_label = QLabel("正在加载几何量实时数据...")
        self.realtime_loading_label.setStyleSheet("color: #1565c0; font-weight: bold;")
        self.realtime_loading_bar = QProgressBar()
        self.realtime_loading_bar.setRange(0, 0)
        self.realtime_loading_bar.setFixedHeight(16)
        self.realtime_loading_label.setVisible(False)
        self.realtime_loading_bar.setVisible(False)
        loading_layout.addWidget(self.realtime_loading_label)
        loading_layout.addWidget(self.realtime_loading_bar, 1)
        layout.addLayout(loading_layout)

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
        
        # 历史识别结果标签
        self.history_recognition_result_label = QLabel("等待识别...")
        self.history_recognition_result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.history_recognition_result_label.setStyleSheet("font-size: 12px; font-weight: bold;")
        history_recognized_layout.addWidget(self.history_recognition_result_label)
        
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
    
    def on_cache_data_ready(self, file_path: str, device_id: str):
        """收到新图片通知后，批量回源读取最近已分析图片，避免同批多图只显示一部分。"""
        logger.info(f"[几何量数据页面] 收到服务端数据通知: {Path(file_path).name if file_path else 'server_record'}, 设备: {device_id}")
        self.log_message(f"收到新图片通知: 设备 {device_id}")
        self._begin_realtime_loading("正在加载最新几何量实时数据...")
        try:
            records = []
            for raw_record in self._fetch_image_records(device_id=device_id, limit=20):
                normalized = self._normalize_image_record(raw_record)
                file_id = normalized.get("file_id")
                if normalized.get("processing_status") != "done" or not file_id:
                    continue
                if int(file_id) in self.displayed_image_file_ids:
                    continue
                records.append(raw_record)

            loaded_count = 0
            # 服务端按上传时间倒序返回；倒序插入可让最新图片最终停在实时页最前面。
            for raw_record in reversed(records):
                if self._load_image_record_into_ui(raw_record):
                    loaded_count += 1

            if loaded_count:
                self.load_history_from_cache()
                self.load_cache_images_to_table()
            else:
                self.log_message("暂未发现新的已分析图片，等待服务端分析完成。")
        finally:
            self._end_realtime_loading()
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
        
        ✅ 新策略（最新在前）：
        1. 如果区域数量 < 20：创建新区域在第0位
        2. 如果区域数量 = 20：删除最后一个，新区域在第0位
        3. 所有旧图片向后移动一位
        
        ✅ 线程安全：使用锁保护整个方法
        
        Args:
            device_tab: 设备选项卡对象
        
        Returns:
            ImageDisplayWidget: 用于显示新图片的区域（第0个）
        """
        with self.widget_access_lock:
            image_widgets = device_tab.image_widgets
            grid_layout = device_tab.grid_layout
            current_count = len(image_widgets)
            
            logger.info(f"[设备{device_tab.device_id}] 当前区域数量: {current_count}/{self.max_widget_count}")
            
            # 如果达到最大数量，删除最后一个区域
            if current_count >= self.max_widget_count:
                last_widget = image_widgets.pop()  # 移除最后一个
                grid_layout.removeWidget(last_widget)
                last_widget.deleteLater()
                logger.info(f"[设备{device_tab.device_id}] 删除最后一个区域")
            
            # 创建新区域（将被插入到第0位）
            new_widget = ImageDisplayWidget(0)
            
            # 所有现有区域向后移动
            for i in range(len(image_widgets) - 1, -1, -1):
                old_widget = image_widgets[i]
                # 更新索引
                old_widget.index = i + 1
                # 从网格中移除
                grid_layout.removeWidget(old_widget)
                # 重新添加到新位置
                new_row = (i + 1) // 2
                new_col = (i + 1) % 2
                grid_layout.addWidget(old_widget, new_row, new_col)
            
            # 插入新区域到第0位
            image_widgets.insert(0, new_widget)
            grid_layout.addWidget(new_widget, 0, 0)
            
            logger.info(f"[设备{device_tab.device_id}] ✅ 新区域已插入到第0位，总数: {len(image_widgets)}")
            return new_widget
    
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
    
    def _update_recognition_result_in_cache(self, file_path: str, has_fault: bool):
        """更新缓存中的识别结果"""
        try:
            import sqlite3
            import json
            
            conn = sqlite3.connect(str(cache_manager.image_db_path))
            cursor = conn.cursor()
            
            # 读取现有的extra_data
            cursor.execute("SELECT extra_data FROM image_records WHERE file_path = ?", (file_path,))
            row = cursor.fetchone()
            
            if row:
                extra_data = json.loads(row[0]) if row[0] else {}
                extra_data['has_fault'] = has_fault
                extra_data_str = json.dumps(extra_data, ensure_ascii=False)
                
                # 更新
                cursor.execute("""
                    UPDATE image_records 
                    SET extra_data = ?
                    WHERE file_path = ?
                """, (extra_data_str, file_path))
                
                conn.commit()
                logger.info(f"更新识别结果到缓存: {Path(file_path).name}, 故障={has_fault}")
            
            conn.close()
            
        except Exception as e:
            logger.error(f"更新识别结果失败: {e}")
    
    def _update_history_from_cache(self):
        """服务端模式下直接刷新历史记录。"""
        self.load_history_from_cache()
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
        """更新历史记录列表。"""
        self.history_list.clear()
        for record in self.history_records:
            item_text = f"[{record.get('timestamp', '')}] {record.get('device_id', 'unknown')} - {record.get('file_name', 'unknown')} [{record.get('processing_status', '')}]"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, record)
            self.history_list.addItem(item)
    def on_history_item_clicked(self, item: QListWidgetItem):
        """点击历史记录后读取服务端详情。"""
        record = item.data(Qt.ItemDataRole.UserRole) or {}
        if not record or not record.get('file_id'):
            return
        detail = self._fetch_image_detail(int(record['file_id'])) or record
        self._display_history_record(detail)
    def filter_history(self):
        """按设备和图片类型筛选服务端历史记录。"""
        selected_device = self.history_device_combo.currentText()
        selected_type = self.history_type_combo.currentText()
        filtered = []
        for record in self.history_records:
            if selected_device != '全部设备' and record.get('device_id') != selected_device:
                continue
            image_type = record.get('image_type') or '未分类'
            if selected_type != '全部类型' and image_type != selected_type:
                continue
            filtered.append(record)
        self.history_list.clear()
        for record in filtered:
            item = QListWidgetItem(f"[{record.get('timestamp', '')}] {record.get('device_id', 'unknown')} - {record.get('file_name', 'unknown')}")
            item.setData(Qt.ItemDataRole.UserRole, record)
            self.history_list.addItem(item)
    def load_history_from_cache(self):
        """直接从服务端加载图片历史记录。"""
        logger.info("开始从服务端加载图片历史记录...")
        records = [self._normalize_image_record(record) for record in self._fetch_image_records(limit=200)]
        self.history_records = records
        self.history_device_combo.clear(); self.history_device_combo.addItem('全部设备')
        for device_id in sorted({record.get('device_id') for record in records if record.get('device_id')}):
            self.history_device_combo.addItem(device_id)
        type_values = sorted({record.get('image_type') or '未分类' for record in records})
        self.history_type_combo.clear(); self.history_type_combo.addItem('全部类型')
        for image_type in type_values:
            self.history_type_combo.addItem(image_type)
        self.update_history_list()
    def load_latest_from_cache(self, show_realtime_loading: bool = True):
        """Load recent analyzed image records and skip bad records safely."""
        if show_realtime_loading:
            self._begin_realtime_loading("正在加载几何量实时数据...")
        try:
            logger.info("Loading latest image records from server...")
            records = list(self._fetch_image_records(limit=200))
            done_records = []
            for record in records:
                normalized = self._normalize_image_record(record)
                if normalized.get("device_id") and normalized.get("processing_status") == "done":
                    done_records.append(record)
            self.device_image_tabs.clear()
            self.displayed_image_file_ids.clear()
            loaded_count = 0
            for record in reversed(done_records[:self.max_widget_count]):
                normalized = self._normalize_image_record(record)
                try:
                    if self._load_image_record_into_ui(record):
                        loaded_count += 1
                except Exception as exc:
                    logger.warning(f"Skip broken image record {normalized.get('file_name', '')}: {exc}")
            if loaded_count == 0:
                placeholder_widget = QWidget()
                placeholder_layout = QVBoxLayout(placeholder_widget)
                placeholder_layout.addWidget(QLabel("等待服务端分析后的几何量图片数据..."))
                self.device_image_tabs.addTab(placeholder_widget, "暂无设备")
                self.status_label.setText("状态: 暂无已分析的几何量图片数据")
                return
            self.status_label.setText(f"状态: 已加载 {loaded_count} 张几何量图片数据")
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
        self.log_message("几何量数据页面日志已初始化")
        
        return tab
    
    def create_cache_table_tab(self):
        """创建缓存数据表格选项卡"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 顶部按钮区
        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.load_cache_images_to_table)
        btn_layout.addWidget(refresh_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # 表格
        self.cache_image_table = QTableWidget()
        self.cache_image_table.setColumnCount(7)
        self.cache_image_table.setHorizontalHeaderLabels([
            "设备ID", "文件名", "时间", "识别结果", "预警信息", "缩略图", "操作"
        ])
        self.cache_image_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.cache_image_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.cache_image_table.setAlternatingRowColors(True)
        self.cache_image_table.setRowHeight(0, 80)  # 设置行高
        layout.addWidget(self.cache_image_table)
        
        # 初始加载
        self.load_cache_images_to_table()
        
        return tab
    
    def log_message(self, message: str):
        """添加日志消息"""
        if not hasattr(self, 'log_text') or self.log_text is None:
            # 日志组件还未初始化，只记录到logger
            logger.info(f"[几何量页面] {message}")
            return
        
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.log_text.appendPlainText(f"[{timestamp}] {message}")
    
    def _populate_cache_images_table(self, records):
        """Render server image records in the cache table."""
        self.cache_image_table.setSortingEnabled(False)
        self.cache_image_table.setRowCount(len(records))
        for row, record in enumerate(records):
            self.cache_image_table.setRowHeight(row, 80)
            self.cache_image_table.setItem(row, 0, QTableWidgetItem(record.get("device_id", "")))
            self.cache_image_table.setItem(row, 1, QTableWidgetItem(record.get("file_name", "")))
            self.cache_image_table.setItem(row, 2, QTableWidgetItem(record.get("timestamp", "")))
            has_fault = record.get("analysis_result", {}).get("has_fault", False)
            result_text = record.get("processing_status", "pending") if record.get("processing_status") != "done" else ("识别故障 ⚠" if has_fault else "未识别故障 ✓")
            result_item = QTableWidgetItem(result_text)
            if record.get("processing_status") == "done":
                result_item.setForeground(Qt.GlobalColor.red if has_fault else Qt.GlobalColor.green)
            self.cache_image_table.setItem(row, 3, result_item)
            self.cache_image_table.setItem(row, 4, self._make_alarm_table_item(record.get("alarm_info") or {}))
            original_path = self._ensure_local_image_path(record.get("file_path"), record.get("file_id"), record.get("file_name") or "image.png")
            thumbnail_label = QLabel()
            thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if original_path and Path(original_path).exists():
                pixmap = QPixmap(str(original_path))
                if not pixmap.isNull():
                    thumbnail_label.setPixmap(pixmap.scaled(60, 60, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            else:
                thumbnail_label.setText("远程图片")
            self.cache_image_table.setCellWidget(row, 5, thumbnail_label)
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(2, 2, 2, 2)
            action_layout.setSpacing(6)
            view_btn = QPushButton("查看")
            view_btn.setStyleSheet("font-size: 9px; padding: 2px 8px;")
            view_btn.clicked.connect(lambda checked, r=record: self.view_image_cache_record(r))
            action_layout.addWidget(view_btn)
            download_btn = QPushButton("下载")
            download_btn.setStyleSheet("font-size: 9px; padding: 2px 8px;")
            download_btn.clicked.connect(lambda checked, r=record: self._download_image_record(r))
            action_layout.addWidget(download_btn)
            action_layout.addStretch()
            self.cache_image_table.setCellWidget(row, 6, action_widget)
        self.sort_table_by_latest_time(self.cache_image_table, ("时间",))
        self.log_message(f"Loaded {len(records)} image records from server")

    def load_cache_images_to_table(self, show_loading: bool = True):
        """Load image records asynchronously."""
        def task():
            return [self._normalize_image_record(record) for record in self._fetch_image_records(limit=100)]

        self.run_async_task(
            task,
            on_success=self._populate_cache_images_table,
            on_error=lambda message: QMessageBox.critical(self, "加载失败", message),
            loading_text="正在加载几何量图片数据...",
            show_loading=show_loading,
            widgets=[getattr(self, "cache_image_table", None)],
        )

    def view_image_cache_record(self, record: dict):
        """Load one image record detail asynchronously."""
        normalized = self._normalize_image_record(record)
        if not normalized.get("file_id"):
            QMessageBox.information(self, "提示", "当前记录缺少文件编号。")
            return

        def task():
            detail = self._fetch_image_detail(int(normalized["file_id"])) or record
            prepared = self._normalize_image_record(detail)
            prepared["original_local_path"] = str(self._ensure_local_image_path(prepared.get("file_path"), prepared.get("file_id"), prepared.get("file_name") or "image.png") or "")
            prepared["recognized_local_path"] = str(self._ensure_local_image_path(prepared.get("recognized_path"), None, f"recognized_{prepared.get('file_name', 'image.png')}") or prepared.get("original_local_path") or "")
            return prepared

        self._begin_realtime_loading(f"正在加载 {normalized.get('file_name', '')}...")

        def on_success(detail):
            try:
                self._display_history_record(detail)
                self.tab_widget.setCurrentIndex(1)
                self.log_message(f"Loaded image record: {normalized.get('file_name', '')}")
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
            widgets=[getattr(self, "cache_image_table", None)],
        )


    def set_server_client(self, client: Client_server):
        """设置服务端客户端，并在页面可见时触发后台刷新。"""
        self.server_client = client
        if self.is_visible:
            QTimer.singleShot(0, self.bootstrap_cache_load)
