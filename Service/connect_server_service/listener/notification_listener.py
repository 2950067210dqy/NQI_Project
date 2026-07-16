from PyQt6.QtCore import QThread, pyqtSignal
import time
from loguru import logger

from Service.connect_server_service.api.api_client import UpperAPIClient


class NotificationListener(QThread):
    """通知监听线程"""
    new_notification = pyqtSignal(dict)

    def __init__(self, client: UpperAPIClient, poll_interval: int = 5):
        super().__init__()
        self.client = client
        self.poll_interval = poll_interval
        self.running = True
        self.last_notification_ids = set()

    def run(self):
        """运行监听"""
        logger.info("Notification listener started")

        while self.running:
            try:
                result = self.client.get_unread_notifications()
                notifications = result.get('notifications', [])

                for notification in notifications:
                    notif_id = notification['id']
                    if notif_id not in self.last_notification_ids:
                        self.new_notification.emit(notification)
                        self.last_notification_ids.add(notif_id)

                time.sleep(self.poll_interval)

            except Exception as e:
                logger.error(f"Notification polling error: {e}")
                # API 客户端已完成 INI 配置次数的尝试；最终失败后退出，避免旧监听器持续请求和弹错。
                self.running = False
                break

    def stop(self):
        """停止监听"""
        self.running = False
        logger.info("Notification listener stopped")