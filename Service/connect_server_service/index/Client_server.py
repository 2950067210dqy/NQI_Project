from datetime import datetime
import threading
import time

from loguru import logger

from Service.connect_server_service.api.api_client import UpperAPIClient
from Service.connect_server_service.api.http_retry import get_request_max_attempts
from Service.connect_server_service.api.long_polling_client import LongPollingThread
from public.config_class.global_setting import global_setting
from public.entity.queue.ObjectQueueItem import ObjectQueueItem
from public.function.Cache.data_download_manager import download_manager


class Client_server():
    def __init__(self):
        self.client = None
        self.long_polling_thread = None
        self.listener = None
        self.auto_refresh_timer = None
        self.connected = False
        self.server_url = ''
        self.device_status_monitor_thread = None
        self.device_status_stop_event = threading.Event()
        self.last_device_status_map = {}
        self.device_status_failure_count = 0
        self.offline_alarm_ui_count = 0
        self.offline_alarm_toast_limit = 3

    def _push_main_window_message(self, title: str, data):
        queue = global_setting.get_setting('queue', None)
        if queue is None:
            return
        queue.put(
            ObjectQueueItem(
                origin='download_manager',
                to='MainWindow_index',
                title=title,
                data=data,
                time=datetime.now().isoformat(),
            )
        )

    def _push_tip(self, message: str):
        self._push_main_window_message('tip', {'message': message})

    def _push_background_task(self, message: str):
        self._push_main_window_message('background_task', {'message': message})

    @staticmethod
    def _normalize_server_url(server_url) -> str:
        """清理配置中的服务器地址，避免尾部空格或斜杠导致请求地址异常。"""
        return str(server_url or '').strip().rstrip('/')

    @staticmethod
    def _get_int_config(config: dict, *keys, default: int = 0) -> int:
        """从配置中按多个兼容 key 读取整数，配置缺失或格式错误时使用默认值。"""
        for key in keys:
            value = config.get(key)
            if value not in (None, ''):
                try:
                    return int(value)
                except (TypeError, ValueError):
                    logger.warning(f'[Client_server] 配置 {key}={value} 不是有效整数，已忽略')
        return int(default)

    def _start_device_status_monitor(self):
        """启动设备状态轮询线程，让上位机持续看到下位机在线/离线变化。"""
        if not self.client:
            return
        if self.device_status_monitor_thread and self.device_status_monitor_thread.is_alive():
            return
        self.device_status_stop_event.clear()
        self.device_status_monitor_thread = threading.Thread(
            target=self._device_status_monitor_loop,
            name='device_status_monitor',
            daemon=True,
        )
        self.device_status_monitor_thread.start()

    def _stop_device_status_monitor(self):
        """停止设备状态轮询线程。"""
        self.device_status_stop_event.set()
        if self.device_status_monitor_thread and self.device_status_monitor_thread.is_alive():
            self.device_status_monitor_thread.join(timeout=3)
        self.device_status_monitor_thread = None

    def _device_status_monitor_loop(self):
        """周期性拉取服务器设备列表，并把在线汇总发送到主窗口状态栏。"""
        server_config = global_setting.get_setting('connect_server', {}).get('server', {})
        interval = self._get_int_config(server_config, 'device_status_poll_interval', default=5)
        request_timeout = min(max(2, self._get_int_config(server_config, 'device_status_timeout', default=5)), 8)
        while not self.device_status_stop_event.is_set():
            try:
                result = self.client.list_devices(timeout=request_timeout)
                self.device_status_failure_count = 0
                devices = result.get('devices', [])
                online = sum(1 for item in devices if item.get('status') == 'online')
                total = len(devices)
                detail_lines = []
                current_status_map = {}
                for item in devices:
                    device_id = item.get('device_id', '')
                    status = item.get('status', 'unknown')
                    current_status_map[device_id] = status
                    detail_lines.append(f"{device_id}: {status} ({item.get('updated_at', '')})")

                if current_status_map != self.last_device_status_map:
                    if self.last_device_status_map:
                        for device_id, status in current_status_map.items():
                            previous_status = self.last_device_status_map.get(device_id)
                            if previous_status and previous_status != status:
                                self._push_tip(f'设备 {device_id} 状态变更: {previous_status} -> {status}')
                    self.last_device_status_map = current_status_map

                self._push_main_window_message('device_status_summary', {
                    'online': online,
                    'total': total,
                    'detail': '\n'.join(detail_lines) if detail_lines else '暂无设备信息',
                })
            except Exception as exc:
                # UpperAPIClient 已在本次调用内完成配置次数的尝试，不能再按轮询周期重复多轮。
                self.device_status_failure_count = get_request_max_attempts()
                short_error = str(exc).splitlines()[0][:160]
                logger.warning(f'设备状态轮询失败({self.device_status_failure_count}): {short_error}')
                self._push_background_task(
                    f'设备状态请求连续失败 {self.device_status_failure_count} 次，已暂停设备状态轮询'
                )
                break
            if self.device_status_stop_event.wait(interval):
                break

    def connect_to_server(self, auto_connect: bool = False):
        """连接到服务器，并启动 HTTP 长轮询监听。"""
        server_config = global_setting.get_setting('connect_server', {}).get('server', {})
        server_url = self._normalize_server_url(server_config.get('url', None))
        self.auto_connect = auto_connect
        if not server_url:
            self._push_main_window_message('connection_error', {
                'server_url': '',
                'status_text': '未配置服务器地址',
                'error': '服务器地址为空',
                'task': '等待配置服务器地址',
                'message': '未配置服务器地址',
                'auto_connect': auto_connect,
            })
            return

        try:
            if self.long_polling_thread:
                self.disconnect_from_server(notify_ui=False)

            self.server_url = server_url
            timeout = self._get_int_config(server_config, 'timeout', default=30)
            # 首次探测最长限制为5秒，避免错误配置重新造成30秒启动等待。
            initial_poll_timeout = min(
                max(1, self._get_int_config(server_config, 'initial_poll_timeout', default=1)),
                5,
            )
            poll_interval = self._get_int_config(server_config, 'http_poll_interval', 'poll_interval', default=2)
            client_id = str(server_config.get('client_id', 'upper_client_001')).strip() or 'upper_client_001'

            self._push_main_window_message('connecting', {
                'server_url': server_url,
                'status_text': '连接中',
                'task': '正在建立 HTTP 长轮询连接',
                'message': f'正在连接服务器: {server_url}',
                'auto_connect': auto_connect,
            })

            self.client = UpperAPIClient(server_url, timeout=timeout)
            self.last_device_status_map = {}
            self.device_status_failure_count = 0

            download_manager.set_client(self)
            queue = global_setting.get_setting('queue', None)
            if queue:
                download_manager.set_message_queue(queue)
                logger.info('[Client_server] 下载管理器消息队列已设置')

            logger.info('[Client_server] 使用HTTP长轮询模式')
            self.long_polling_thread = LongPollingThread(
                server_url=server_url,
                client_id=client_id,
                poll_interval=poll_interval,
                timeout=timeout,
                initial_timeout=initial_poll_timeout,
            )
            self.long_polling_thread.set_notification_callback(self.on_notification)
            self.long_polling_thread.set_connected_callback(self.on_connected)
            self.long_polling_thread.set_disconnected_callback(self.on_disconnected)
            self.long_polling_thread.set_error_callback(self.on_error)
            self.long_polling_thread.start()

            self.connected = False
            self._push_background_task('已启动服务器长轮询，等待服务器响应')
        except Exception as e:
            self.connected = False
            logger.error(f'连接失败: {e}')
            self._push_main_window_message('connection_error', {
                'server_url': self.server_url or server_url,
                'status_text': '连接失败',
                'error': str(e),
                'task': '服务器连接失败，后台轮询已停止',
                'message': '连接服务器失败',
                'auto_connect': auto_connect,
            })
            # 详细异常已经通过 connection_error 弹窗展示，状态栏只保留短提示，避免挤压布局。
            self._push_tip('连接服务器失败')

    def disconnect_from_server(self, notify_ui: bool = True):
        """断开服务器连接。"""
        download_manager.stop_all_downloads()
        self._stop_device_status_monitor()

        if self.long_polling_thread:
            self.long_polling_thread.stop()
            self.long_polling_thread.join(timeout=3)
            self.long_polling_thread = None

        if self.listener:
            self.listener.stop()
            self.listener.wait()
            self.listener = None

        if self.auto_refresh_timer:
            self.auto_refresh_timer.stop()
            self.auto_refresh_timer = None

        self.connected = False
        if notify_ui:
            self._push_main_window_message('disconnected', {
                'server_url': self.server_url,
                'status_text': '连接已断开',
                'task': '服务器连接已断开，后台轮询已停止',
                'message': '服务器连接已断开',
            })
        logger.info('已断开服务器连接')

    def on_notification(self, data: dict):
        """通知回调（HTTP长轮询）。"""
        notification_type = data.get('type', '')
        device_id = data.get('device_id', '')
        file_name = data.get('file_name', '')

        if notification_type == 'excel_upload':
            message = f'[通知] 收到电量数据上传通知: 设备 {device_id} - {file_name}'
            logger.info(message)
            self._push_tip(message)
            self._push_background_task('后台收到新的电量数据，服务器正在解析')
        elif notification_type == 'excel_processed':
            message = f'[通知] 电量数据解析完成: 设备 {device_id} - {file_name}'
            logger.info(message)
            self._push_tip(message)
            self._push_background_task('服务器已完成电量解析，正在同步缓存')
            download_manager.handle_new_data_notification(data)
        elif notification_type == 'image_upload':
            message = f'[通知] 收到几何量数据上传通知: 设备 {device_id} - {file_name}'
            logger.info(message)
            self._push_tip(message)
            self._push_background_task('后台收到新的几何量数据，服务器正在分析')
        elif notification_type == 'image_processed':
            message = f'[通知] 几何量图片分析完成: 设备 {device_id} - {file_name}'
            logger.info(message)
            self._push_tip(message)
            self._push_background_task('服务器已完成几何量分析，正在同步缓存')
            download_manager.handle_new_data_notification(data)
        elif notification_type == 'fault_alarm':
            fault_summary = data.get('fault_summary') or data.get('message') or '检测到疑似故障'
            message = data.get('message') or f'[报警] 设备 {device_id} - {file_name}: {fault_summary}'
            if not str(message).startswith('[报警]'):
                message = f'[报警] {message}'
            logger.warning(message)

            from_offline_queue = bool(data.get('from_offline_queue', False))
            suppress_toast = False
            if from_offline_queue:
                self.offline_alarm_ui_count += 1
                suppress_toast = self.offline_alarm_ui_count > self.offline_alarm_toast_limit
                if self.offline_alarm_ui_count == self.offline_alarm_toast_limit + 1:
                    # 离线队列可能积压很多条，摘要也走 latest_alarm 信号回主线程，避免队列线程直接刷新状态栏。
                    self._push_main_window_message('latest_alarm', {
                        'device_id': device_id,
                        'file_name': file_name,
                        'fault_summary': '离线预警较多，后续预警已写入报警预警页面，不再逐条弹窗',
                        'message': '[报警] 离线预警较多，后续预警已写入报警预警页面，不再逐条弹窗',
                        'timestamp': data.get('timestamp'),
                        'fault_id': data.get('fault_id'),
                        'notification_id': data.get('notification_id'),
                        'from_offline_queue': True,
                        'suppress_toast': True,
                    })
            else:
                self._push_tip(message)
                self._push_background_task('后台收到新的预警消息')

            if not suppress_toast:
                self._push_main_window_message('latest_alarm', {
                    'device_id': device_id,
                    'file_name': file_name,
                    'fault_summary': fault_summary,
                    'message': message,
                    'timestamp': data.get('timestamp'),
                    'fault_id': data.get('fault_id'),
                    'notification_id': data.get('notification_id'),
                    'from_offline_queue': from_offline_queue,
                    'suppress_toast': suppress_toast,
                })
        elif notification_type == 'device_register_request':
            request_id = data.get('request_id', '')
            message = f'[注册审批] 收到新的设备注册申请: {device_id} (申请ID: {request_id})'
            logger.info(message)
            self._push_tip(message)
        elif notification_type == 'device_register_approved':
            message = f'[注册审批] 设备注册审批通过: {device_id}'
            logger.info(message)
            self._push_tip(message)
        elif notification_type == 'device_register_rejected':
            review_message = data.get('review_message', '审批已驳回')
            message = f'[注册审批] 设备注册审批驳回: {device_id} - {review_message}'
            logger.warning(message)
            self._push_tip(message)
        else:
            message = f'[通知] 收到通知: {data}'
            logger.info(message)
            self._push_tip(message)

        self._ack_delivered_notification(data)

    def _ack_delivered_notification(self, data: dict):
        """上位机处理完数据库补发通知后，通知服务器从离线队列移除。"""
        notification_id = data.get('notification_id') or data.get('id')
        if not notification_id or self.client is None:
            return
        try:
            self.client.mark_notification_read(int(notification_id))
            logger.info(f"已确认服务器通知: {notification_id}")
        except Exception as exc:
            # ack 失败时保持服务端 unread，下次上线/轮询还能再次补发，避免离线预警丢失。
            logger.warning(f"确认服务器通知失败，稍后会再次补发 notification_id={notification_id}: {exc}")

    def on_connected(self):
        """连接成功回调。"""
        auto_connect = getattr(self, 'auto_connect', False)
        self.offline_alarm_ui_count = 0
        if not self.connected:
            self.connected = True
            self._push_main_window_message('connected', {
                'server_url': self.server_url,
                'status_text': '已连接',
                'message': '长轮询连接已建立',
                'auto_connect': auto_connect,
            })
            self._push_tip('连接服务器成功 (HTTP长轮询模式)')
            self._push_background_task('已连接服务器，后台正在同步设备状态与预警消息')
            self._start_device_status_monitor()
        self.auto_connect = False
        logger.info('[连接] 已连接到服务器')

    def on_disconnected(self):
        """断开连接回调。"""
        auto_connect = getattr(self, 'auto_connect', False)
        self.connected = False
        # 长轮询断开后同步停止其它服务器轮询，避免服务器宕机时继续发送请求。
        self._stop_device_status_monitor()
        download_manager.stop_all_downloads()
        self._push_main_window_message('disconnected', {
            'server_url': self.server_url,
            'status_text': '连接已断开',
            'task': '服务器长轮询已断开，后台轮询已停止',
            'message': '服务器连接已断开',
            'auto_connect': auto_connect,
        })
        self.auto_connect = False
        logger.warning('[连接] 连接已断开，后台轮询已停止')

    def on_error(self, error: str):
        """错误回调。"""
        auto_connect = getattr(self, 'auto_connect', False)
        self.connected = False
        self._push_main_window_message('connection_error', {
            'server_url': self.server_url,
            'status_text': '连接失败',
            'error': error,
            'task': '服务器长轮询异常，后台轮询已停止',
            'message': '服务器连接错误',
            'auto_connect': auto_connect,
        })
        self.auto_connect = False
        logger.error(f'[连接] 错误: {error}')
