"""
统一数据同步管理器
负责在后台读取服务端已处理完成的数据详情，并在需要时下载原始图片到本地缓存。
"""
from datetime import datetime
from pathlib import Path
from queue import Queue
from typing import Any, Dict
import threading

from PyQt6.QtCore import QObject, pyqtSignal, QThread, Qt
from loguru import logger

from public.function.Cache.cache_manager import cache_manager


class DownloadTask:
    """数据同步任务。"""

    def __init__(self, data_type: str, device_id: str, file_id: Any,
                 file_name: str, file_size: int = 0, timestamp: str = None):
        self.data_type = data_type
        self.device_id = device_id
        self.file_id = file_id
        self.file_name = file_name
        self.file_size = file_size
        self.timestamp = timestamp or datetime.now().strftime('%Y-%m-%d %H:%M:%S')


class DataSyncWorkerThread(QThread):
    """后台同步线程。"""

    sync_finished = pyqtSignal(str, str, str, object)  # data_type, file_path, device_id, detail
    sync_failed = pyqtSignal(str, str, str)            # data_type, error, device_id

    def __init__(self, client, task: DownloadTask):
        super().__init__()
        self.client = client
        self.task = task
        self.setTerminationEnabled(True)

    def run(self):
        try:
            task = self.task
            if task.file_id is None:
                raise ValueError("file_id 为 None")

            if task.data_type == 'excel':
                detail = self.client.get_excel_detail(task.file_id).get('data', {})
                file_path = detail.get('file_path', '')
            elif task.data_type == 'image':
                detail = self.client.get_image_detail(task.file_id).get('data', {})
                save_dir = Path('data/image') / task.device_id
                save_dir.mkdir(parents=True, exist_ok=True)
                save_path = save_dir / task.file_name
                self.client.download_image_file(task.file_id, save_path)
                detail['local_file_path'] = str(save_path)
                file_path = str(save_path)
            else:
                raise ValueError(f'未知的数据类型: {task.data_type}')

            self.sync_finished.emit(task.data_type, file_path, task.device_id, detail)
        except Exception as e:
            logger.error(f"[下载管理器] 同步失败: {e}")
            self.sync_failed.emit(self.task.data_type, str(e), self.task.device_id)


class DataDownloadManager(QObject):
    """统一数据同步管理器。"""

    excel_data_ready = pyqtSignal(str, str)
    image_data_ready = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.client = None
        self.active_threads = []
        self.download_queue = Queue()
        self.lock = threading.Lock()
        self.message_queue = None
        logger.info('[下载管理器] 初始化完成')

    def set_client(self, client):
        self.client = client
        logger.info('[下载管理器] 设置服务端客户端')

    def set_message_queue(self, queue):
        self.message_queue = queue
        logger.info('[下载管理器] 设置跨进程消息队列')

    def handle_new_data_notification(self, data: Dict[str, Any]):
        """根据服务端通知启动缓存同步任务。"""
        try:
            data_type_raw = data.get('type', '')
            device_id = data.get('device_id', 'unknown')
            file_id = data.get('file_id')
            file_name = data.get('file_name', 'unknown')
            file_size = data.get('file_size', 0)
            timestamp = data.get('timestamp', datetime.now().isoformat())

            if 'excel' in data_type_raw.lower():
                data_type = 'excel'
            elif 'image' in data_type_raw.lower():
                data_type = 'image'
            else:
                logger.warning(f'[下载管理器] 未知的数据类型: {data_type_raw}')
                return

            if not self.client:
                logger.error('[下载管理器] 服务端客户端未设置')
                return
            if not file_id:
                logger.error('[下载管理器] file_id 为空')
                return

            task = DownloadTask(
                data_type=data_type,
                device_id=device_id,
                file_id=file_id,
                file_name=file_name,
                file_size=file_size,
                timestamp=timestamp if isinstance(timestamp, str) else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )
            self._start_download(task)
        except Exception as e:
            logger.error(f'[下载管理器] 处理新数据通知失败: {e}')

    def _start_download(self, task: DownloadTask):
        try:
            with self.lock:
                thread = DataSyncWorkerThread(self.client.client, task)
                thread.sync_finished.connect(self._on_download_finished, Qt.ConnectionType.QueuedConnection)
                thread.sync_failed.connect(self._on_download_failed, Qt.ConnectionType.QueuedConnection)
                thread.finished.connect(lambda t=thread: self._on_thread_finished(t), Qt.ConnectionType.QueuedConnection)
                self.active_threads.append(thread)
                thread.start()
                logger.info(f'[下载管理器] 启动同步线程: {task.file_name}, 活跃线程数: {len(self.active_threads)}')
        except Exception as e:
            logger.error(f'[下载管理器] 启动同步失败: {e}')

    def _on_download_finished(self, data_type: str, file_path: str, device_id: str, detail: object):
        try:
            detail = detail or {}
            logger.info(f'[下载管理器] 同步完成: {detail.get("file_name", Path(file_path).name if file_path else "unknown")}, 类型: {data_type}, 设备: {device_id}')
            if data_type == 'excel':
                self._save_excel_to_cache(detail, device_id)
                self._send_queue_message('excel_data_viewer', 'cache_data_ready', {
                    'file_path': file_path,
                    'device_id': device_id,
                })
            elif data_type == 'image':
                self._save_image_to_cache(detail, device_id)
                self._send_queue_message('image_data_viewer', 'cache_data_ready', {
                    'file_path': detail.get('local_file_path', file_path),
                    'device_id': device_id,
                })
        except Exception as e:
            logger.error(f'[下载管理器] 处理同步完成失败: {e}')

    def _send_queue_message(self, target: str, title: str, data: dict):
        try:
            if self.message_queue is None:
                logger.warning('[下载管理器] 消息队列未设置，无法发送通知')
                return
            from public.entity.queue.ObjectQueueItem import ObjectQueueItem
            message = ObjectQueueItem(
                origin='download_manager',
                to=target,
                title=title,
                data=data,
                time=datetime.now().isoformat()
            )
            self.message_queue.put(message)
            logger.info(f'[下载管理器] 已发送队列消息到 {target}')
        except Exception as e:
            logger.error(f'[下载管理器] 发送队列消息失败: {e}')

    def _on_download_failed(self, data_type: str, error: str, device_id: str):
        logger.error(f'[下载管理器] 同步失败: 类型={data_type}, 设备={device_id}, 错误={error}')

    def _on_thread_finished(self, thread):
        try:
            with self.lock:
                if thread in self.active_threads:
                    self.active_threads.remove(thread)
                    logger.info(f'[下载管理器] 线程已清理，剩余活跃线程: {len(self.active_threads)}')
        except Exception as e:
            logger.error(f'[下载管理器] 清理线程失败: {e}')

    def _save_excel_to_cache(self, detail: Dict[str, Any], device_id: str):
        try:
            parse_result = detail.get('parse_result', {}) or {}
            cache_record = {
                'device_id': device_id,
                'file_path': detail.get('file_path', ''),
                'file_name': detail.get('file_name', ''),
                'timestamp': (detail.get('upload_time') or '').replace('T', ' ')[:19] or datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'sheet_count': parse_result.get('sheet_count', 0),
                'rated_voltage': parse_result.get('rated_voltage', 0),
                'rated_voltage_unit': parse_result.get('rated_voltage_unit', ''),
                'rated_frequency': parse_result.get('rated_frequency', 0),
                'rated_frequency_unit': parse_result.get('rated_frequency_unit', ''),
                'extra_data': detail,
            }
            cache_manager.save_excel_record(cache_record)
            logger.info(f"[下载管理器] 电量数据已保存到缓存: {detail.get('file_name')}")
        except Exception as e:
            logger.error(f'[下载管理器] 保存电量数据到缓存失败: {e}')

    def _save_image_to_cache(self, detail: Dict[str, Any], device_id: str):
        try:
            local_file_path = detail.get('local_file_path', '')
            cache_record = {
                'device_id': device_id,
                'file_path': local_file_path,
                'file_name': detail.get('file_name', ''),
                'original_path': local_file_path,
                'recognized_path': local_file_path,
                'timestamp': (detail.get('upload_time') or '').replace('T', ' ')[:19] or datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'file_size': detail.get('file_size', 0),
                'extra_data': detail,
            }
            cache_manager.save_image_record(cache_record)
            logger.info(f"[下载管理器] 几何量数据已保存到缓存: {detail.get('file_name')}")
        except Exception as e:
            logger.error(f'[下载管理器] 保存几何量数据到缓存失败: {e}')

    def stop_all_downloads(self):
        try:
            with self.lock:
                for thread in self.active_threads[:]:
                    if thread.isRunning():
                        thread.terminate()
                        thread.wait(1000)
                self.active_threads.clear()
                logger.info('[下载管理器] 已停止所有同步线程')
        except Exception as e:
            logger.error(f'[下载管理器] 停止同步失败: {e}')

    def get_statistics(self) -> Dict[str, Any]:
        return {
            'active_threads': len(self.active_threads),
            'queue_size': self.download_queue.qsize() if hasattr(self.download_queue, 'qsize') else 0
        }


download_manager = DataDownloadManager()
