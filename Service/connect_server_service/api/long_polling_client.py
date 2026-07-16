"""
HTTP长轮询客户端 - 替代WebSocket
基于requests实现的长连接通知接收
"""
import requests
import threading
import time
from typing import Callable, Optional
from loguru import logger

from Service.connect_server_service.api.http_retry import create_retry_session


class LongPollingClient:
    """HTTP长轮询客户端。"""

    def __init__(
            self,
            server_url: str,
            client_id: str,
            device_id: Optional[str] = None,
            poll_interval: int = 2,
            timeout: int = 30,
            initial_timeout: int = 1,
    ):
        """
        初始化长轮询客户端。

        Args:
            server_url: 服务器地址（如 http://localhost:8000）
            client_id: 客户端唯一标识
            device_id: 可选，指定要监听的设备ID
            poll_interval: 成功返回后的空闲轮询间隔（秒）
        """
        self.server_url = str(server_url or '').strip().rstrip('/')
        self.client_id = client_id
        self.device_id = device_id
        self.connected = False
        self.running = False
        self.manual_stop = False

        # 回调函数
        self.on_notification: Optional[Callable] = None
        self.on_connected: Optional[Callable] = None
        self.on_disconnected: Optional[Callable] = None
        self.on_error: Optional[Callable] = None

        # 配置
        self.timeout = max(1, int(timeout))
        self.initial_timeout = min(max(1, int(initial_timeout)), 5)
        self.poll_interval = max(1, int(poll_interval))
        self.retry_interval = max(1, int(poll_interval))
        # 长轮询和普通 API 使用同一 INI 重试次数，最终失败后停止轮询。
        self.session = create_retry_session()

        logger.info(f"[长轮询客户端] 初始化: {client_id}, 设备过滤: {device_id}, 轮询间隔: {self.poll_interval}s")

    def _stop_for_connection_loss(self, reason: str, notify_error: bool = False):
        """长轮询连接异常后立即停止，避免服务器宕机时继续反复请求。"""
        logger.warning(f"[长轮询] 连接断开，停止后续轮询: {reason}")
        self.connected = False
        self.running = False
        if notify_error and self.on_error:
            self.on_error(reason)

    def start(self):
        """开始长轮询。"""
        self.running = True
        self.connected = False
        self.manual_stop = False

        logger.info(f"[长轮询客户端] 开始轮询: {self.server_url}")

        while self.running:
            try:
                # 首次短轮询只用于快速确认服务器可用，成功后恢复正常长轮询等待时间。
                server_wait_timeout = self.initial_timeout if not self.connected else self.timeout
                params = {
                    'client_id': self.client_id,
                    'timeout': server_wait_timeout,
                }
                if self.device_id:
                    params['device_id'] = self.device_id

                logger.debug('[长轮询] 发送请求...')
                response = self.session.get(
                    f"{self.server_url}/api/polling/notifications",
                    params=params,
                    timeout=server_wait_timeout + 5,
                )

                if response.status_code == 200:
                    data = response.json()
                    notifications = data.get('notifications', [])
                    if not self.connected:
                        self.connected = True
                        if self.on_connected:
                            self.on_connected()

                    if notifications:
                        logger.info(f"[长轮询] 收到 {len(notifications)} 条通知")
                        for notification in notifications:
                            if self.on_notification:
                                self.on_notification(notification)
                    else:
                        logger.debug('[长轮询] 无新通知')

                    if self.running:
                        time.sleep(self.poll_interval)
                else:
                    reason = f"服务器长轮询接口返回异常状态: HTTP {response.status_code}"
                    logger.warning(f"[长轮询] 请求失败: {response.status_code}")
                    self._stop_for_connection_loss(reason, notify_error=not self.connected)

            except requests.exceptions.Timeout as e:
                reason = f"连接服务器超时，长轮询已停止: {e}"
                logger.warning(f"[长轮询] 请求超时: {e}")
                self._stop_for_connection_loss(reason, notify_error=not self.connected)

            except requests.exceptions.ConnectionError as e:
                reason = f"服务器连接中断，长轮询已停止: {e}"
                logger.error(f"[长轮询] 连接错误: {e}")
                self._stop_for_connection_loss(reason, notify_error=not self.connected)

            except Exception as e:
                reason = f"长轮询异常，已停止: {e}"
                logger.error(f"[长轮询] 错误: {e}")
                self._stop_for_connection_loss(reason, notify_error=not self.connected)

        self.connected = False
        # Manual stop should not overwrite a newer successful connection on the UI.
        if self.on_disconnected and not self.manual_stop:
            self.on_disconnected()

        logger.info('[长轮询客户端] 已停止')

    def stop(self):
        """停止长轮询。"""
        self.manual_stop = True
        self.running = False
        logger.info('[长轮询客户端] 停止中...')

    def is_connected(self) -> bool:
        """检查是否已连接。"""
        return self.connected and self.running


class LongPollingThread(threading.Thread):
    """HTTP长轮询运行线程。"""

    def __init__(
            self,
            server_url: str,
            client_id: str,
            device_id: Optional[str] = None,
            poll_interval: int = 2,
            timeout: int = 30,
            initial_timeout: int = 1,
    ):
        super().__init__(daemon=True)
        self.client = LongPollingClient(
            server_url=server_url,
            client_id=client_id,
            device_id=device_id,
            poll_interval=poll_interval,
            timeout=timeout,
            initial_timeout=initial_timeout,
        )
        self.running = True

    def run(self):
        """运行线程。"""
        try:
            self.client.start()
        except Exception as e:
            logger.error(f"[长轮询线程] 错误: {e}")

    def stop(self):
        """停止线程。"""
        self.running = False
        self.client.stop()

    def join(self, timeout=None):
        """等待线程结束。"""
        super().join(timeout)

    def set_notification_callback(self, callback: Callable):
        """设置通知回调。"""
        self.client.on_notification = callback

    def set_connected_callback(self, callback: Callable):
        """设置连接成功回调。"""
        self.client.on_connected = callback

    def set_disconnected_callback(self, callback: Callable):
        """设置断开连接回调。"""
        self.client.on_disconnected = callback

    def set_error_callback(self, callback: Callable):
        """设置错误回调。"""
        self.client.on_error = callback

    def is_connected(self) -> bool:
        """检查是否已连接。"""
        return self.client.is_connected()
