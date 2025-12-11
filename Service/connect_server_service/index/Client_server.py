import threading

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QMessageBox
from loguru import logger

from Service.connect_server_service.api.api_client import UpperAPIClient
from Service.connect_server_service.listener.notification_listener import NotificationListener
from public.config_class.global_setting import global_setting


class Client_server():
    def __init__(self):
        # 创建客户端
        self.client =None
        # 启动通知监听线程
        self.listener =None
        # 启动自动刷新定时器
        self.auto_refresh_timer=None
        #连接状态
        self.connected = False
    pass

    def connect_to_server(self):
        """连接到服务器"""
        try:
            server_url = global_setting.get_setting("connect_server", {}).get("server", {}).get("url", None)
            if server_url is None:
                # QMessageBox.warning(None, "警告", "服务器地址为空")
                return

            # 创建客户端
            self.client = UpperAPIClient(server_url)

            # 测试连接
            self.client.list_devices()

            # 启动通知监听线程
            self.listener = NotificationListener(self.client, int(global_setting.get_setting("connect_server", {}).get("server", {}).get('poll_interval',5)) )
            # self.listener.new_notification.connect(self.on_new_notification)
            self.listener.start()

            # 启动自动刷新定时器
            self.auto_refresh_timer = QTimer()
            # self.auto_refresh_timer.timeout.connect(self.auto_refresh_data)
            self.auto_refresh_timer.start(int(global_setting.get_setting("connect_server", {}).get("display", {}).get('auto_refresh_interval',5)) *1000)

            self.connected = True
            logger.info("连接服务器成功")
            # self.statusBar().showMessage("已连接 ✓")
            #
            #
            #
            # QMessageBox.information(None, "成功", "连接服务器成功！")

        except Exception as e:
            logger.error(f"连接失败: {e}", error=True)
            # QMessageBox.critical(None, "错误", f"连接失败: {e}")

    def disconnect_from_server(self):
        """断开服务器连接"""
        if self.listener:
            self.listener.stop()
            self.listener.wait()

        if self.auto_refresh_timer:
            self.auto_refresh_timer.stop()

        self.connected = False
        logger.error("已断开服务器连接")
        # self.statusBar().showMessage("未连接")