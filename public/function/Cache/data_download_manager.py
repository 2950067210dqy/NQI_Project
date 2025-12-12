"""
统一数据下载管理器
负责在后台下载所有数据（电量和几何量），下载完成后存入缓存并通知页面更新
"""
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
from queue import Queue

from PyQt6.QtCore import QObject, pyqtSignal, QThread, Qt
from loguru import logger

from public.function.Cache.cache_manager import cache_manager


class DownloadTask:
    """下载任务"""
    def __init__(self, data_type: str, device_id: str, file_id: Any, 
                 file_name: str, file_size: int = 0, timestamp: str = None):
        """
        Args:
            data_type: 数据类型 ('excel' or 'image')
            device_id: 设备ID
            file_id: 文件ID（用于下载）
            file_name: 文件名
            file_size: 文件大小
            timestamp: 时间戳
        """
        self.data_type = data_type
        self.device_id = device_id
        self.file_id = file_id
        self.file_name = file_name
        self.file_size = file_size
        self.timestamp = timestamp or datetime.now().strftime('%Y-%m-%d %H:%M:%S')


class DownloadWorkerThread(QThread):
    """下载工作线程"""
    download_finished = pyqtSignal(str, str, str)  # data_type, file_path, device_id
    download_failed = pyqtSignal(str, str, str)    # data_type, error, device_id
    
    def __init__(self, client, task: DownloadTask):
        super().__init__()
        self.client = client
        self.task = task
        self.setTerminationEnabled(True)
    
    def run(self):
        """执行下载"""
        try:
            task = self.task
            
            # 确定保存路径
            if task.data_type == 'excel':
                save_dir = Path("data/excel") / task.device_id
                download_method = self.client.download_excel_file
            elif task.data_type == 'image':
                save_dir = Path("data/image") / task.device_id
                download_method = self.client.download_image_file
            else:
                raise ValueError(f"未知的数据类型: {task.data_type}")
            
            # 创建目录
            save_dir.mkdir(parents=True, exist_ok=True)
            save_path = save_dir / task.file_name
            
            logger.info(f"[下载管理器] 开始下载 {task.data_type}: {task.file_name}")
            
            # 执行下载
            if task.file_id is None:
                raise Exception("file_id 为 None")
            
            download_method(task.file_id, save_path)
            
            logger.info(f"[下载管理器] ✅ 下载完成: {save_path}")
            self.download_finished.emit(task.data_type, str(save_path), task.device_id)
            
        except Exception as e:
            import traceback
            logger.error(f"[下载管理器] ❌ 下载失败: {e}\n{traceback.format_exc()}")
            self.download_failed.emit(task.data_type, str(e), task.device_id)


class DataDownloadManager(QObject):
    """统一数据下载管理器"""
    
    # 信号：通知页面有新数据可用
    excel_data_ready = pyqtSignal(str, str)  # file_path, device_id
    image_data_ready = pyqtSignal(str, str)  # file_path, device_id
    
    def __init__(self):
        super().__init__()
        self.client = None  # 服务端客户端
        self.active_threads = []  # 活跃的下载线程
        self.download_queue = Queue()  # 下载队列（备用）
        self.lock = threading.Lock()  # 线程锁
        
        logger.info("[下载管理器] 初始化完成")
    
    def set_client(self, client):
        """设置服务端客户端"""
        self.client = client
        logger.info("[下载管理器] 设置服务端客户端")
    
    def handle_new_data_notification(self, data: Dict[str, Any]):
        """
        处理新数据通知，启动下载任务
        
        Args:
            data: 数据通知，格式：
                - type: 'excel_upload' or 'image_upload'
                - device_id: 设备ID
                - file_id: 文件ID
                - file_name: 文件名
                - file_size: 文件大小（可选）
                - timestamp: 时间戳（可选）
        """
        try:
            data_type_raw = data.get('type', '')
            device_id = data.get('device_id', 'unknown')
            file_id = data.get('file_id')
            file_name = data.get('file_name', 'unknown')
            file_size = data.get('file_size', 0)
            timestamp = data.get('timestamp', datetime.now().isoformat())
            
            # 确定数据类型
            if 'excel' in data_type_raw.lower():
                data_type = 'excel'
            elif 'image' in data_type_raw.lower():
                data_type = 'image'
            else:
                logger.warning(f"[下载管理器] 未知的数据类型: {data_type_raw}")
                return
            
            logger.info(f"[下载管理器] 收到新{data_type}数据通知: {file_name}, 设备: {device_id}")
            
            # 检查客户端
            if not self.client:
                logger.error("[下载管理器] 服务端客户端未设置")
                return
            
            if not file_id:
                logger.error("[下载管理器] file_id 为空")
                return
            
            # 创建下载任务
            task = DownloadTask(
                data_type=data_type,
                device_id=device_id,
                file_id=file_id,
                file_name=file_name,
                file_size=file_size,
                timestamp=timestamp if isinstance(timestamp, str) else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )
            
            # 启动下载线程
            self._start_download(task)
            
        except Exception as e:
            import traceback
            logger.error(f"[下载管理器] 处理新数据通知失败: {e}\n{traceback.format_exc()}")
    
    def _start_download(self, task: DownloadTask):
        """启动下载任务"""
        try:
            with self.lock:
                # 创建下载线程
                thread = DownloadWorkerThread(self.client.client, task)
                
                # 连接信号
                thread.download_finished.connect(
                    self._on_download_finished,
                    Qt.ConnectionType.QueuedConnection
                )
                thread.download_failed.connect(
                    self._on_download_failed,
                    Qt.ConnectionType.QueuedConnection
                )
                thread.finished.connect(
                    lambda t=thread: self._on_thread_finished(t),
                    Qt.ConnectionType.QueuedConnection
                )
                
                # 添加到活跃线程列表
                self.active_threads.append(thread)
                
                # 启动下载
                thread.start()
                
                logger.info(f"[下载管理器] 启动下载线程: {task.file_name}, 活跃线程数: {len(self.active_threads)}")
                
        except Exception as e:
            logger.error(f"[下载管理器] 启动下载失败: {e}")
    
    def _on_download_finished(self, data_type: str, file_path: str, device_id: str):
        """下载完成回调"""
        try:
            logger.info(f"[下载管理器] 下载完成: {Path(file_path).name}, 类型: {data_type}, 设备: {device_id}")
            
            # 保存到缓存
            if data_type == 'excel':
                self._save_excel_to_cache(file_path, device_id)
                # 通知电量数据页面
                self.excel_data_ready.emit(file_path, device_id)
                logger.info(f"[下载管理器] 已通知电量数据页面更新")
                
            elif data_type == 'image':
                self._save_image_to_cache(file_path, device_id)
                # 通知几何量数据页面
                self.image_data_ready.emit(file_path, device_id)
                logger.info(f"[下载管理器] 已通知几何量数据页面更新")
            
        except Exception as e:
            import traceback
            logger.error(f"[下载管理器] 处理下载完成失败: {e}\n{traceback.format_exc()}")
    
    def _on_download_failed(self, data_type: str, error: str, device_id: str):
        """下载失败回调"""
        logger.error(f"[下载管理器] 下载失败: 类型={data_type}, 设备={device_id}, 错误={error}")
    
    def _on_thread_finished(self, thread):
        """线程完成回调"""
        try:
            with self.lock:
                if thread in self.active_threads:
                    self.active_threads.remove(thread)
                    logger.info(f"[下载管理器] 线程已清理，剩余活跃线程: {len(self.active_threads)}")
        except Exception as e:
            logger.error(f"[下载管理器] 清理线程失败: {e}")
    
    def _save_excel_to_cache(self, file_path: str, device_id: str):
        """保存电量数据到缓存"""
        try:
            # 解析Excel获取元信息
            import pandas as pd
            excel_file = pd.ExcelFile(file_path)
            sheet_count = len(excel_file.sheet_names)
            
            # 尝试读取第一个sheet获取额定参数
            rated_voltage = 0
            rated_voltage_unit = ''
            rated_frequency = 0
            rated_frequency_unit = ''
            
            try:
                df = excel_file.parse(excel_file.sheet_names[0], header=None)
                data_clean = df.dropna()
                if not data_clean.empty:
                    import re
                    df_colum_0_unique = data_clean.drop_duplicates(subset=[data_clean.columns[0]])
                    df_colum_1_unique = data_clean.drop_duplicates(subset=[data_clean.columns[1]])
                    
                    rated_frequency = float("".join(re.findall(r'[0-9]', str(df_colum_1_unique.iloc[0, 1]))))
                    rated_frequency_unit = "".join(re.findall(r'[A-Za-z]', str(df_colum_1_unique.iloc[0, 1])))
                    rated_voltage = float("".join(re.findall(r'[0-9]', str(df_colum_0_unique.iloc[0, 0]).split(",")[0])))
                    rated_voltage_unit = "".join(re.findall(r'[A-Za-z]', str(df_colum_0_unique.iloc[0, 0]).split(",")[0]))
            except:
                pass
            
            # 保存到缓存
            cache_record = {
                'device_id': device_id,
                'file_path': file_path,
                'file_name': Path(file_path).name,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'sheet_count': sheet_count,
                'rated_voltage': rated_voltage,
                'rated_voltage_unit': rated_voltage_unit,
                'rated_frequency': rated_frequency,
                'rated_frequency_unit': rated_frequency_unit
            }
            
            cache_manager.save_excel_record(cache_record)
            logger.info(f"[下载管理器] 电量数据已保存到缓存: {Path(file_path).name}")
            
        except Exception as e:
            logger.error(f"[下载管理器] 保存电量数据到缓存失败: {e}")
    
    def _save_image_to_cache(self, file_path: str, device_id: str):
        """保存几何量数据到缓存"""
        try:
            cache_record = {
                'device_id': device_id,
                'file_path': file_path,
                'file_name': Path(file_path).name,
                'original_path': file_path,
                'recognized_path': file_path,  # 识别后会更新
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'file_size': Path(file_path).stat().st_size if Path(file_path).exists() else 0
            }
            
            cache_manager.save_image_record(cache_record)
            logger.info(f"[下载管理器] 几何量数据已保存到缓存: {Path(file_path).name}")
            
        except Exception as e:
            logger.error(f"[下载管理器] 保存几何量数据到缓存失败: {e}")
    
    def stop_all_downloads(self):
        """停止所有下载任务"""
        try:
            with self.lock:
                for thread in self.active_threads[:]:
                    if thread.isRunning():
                        thread.terminate()
                        thread.wait(1000)
                self.active_threads.clear()
                logger.info("[下载管理器] 已停止所有下载线程")
        except Exception as e:
            logger.error(f"[下载管理器] 停止下载失败: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'active_threads': len(self.active_threads),
            'queue_size': self.download_queue.qsize() if hasattr(self.download_queue, 'qsize') else 0
        }


# 全局下载管理器实例
download_manager = DataDownloadManager()

