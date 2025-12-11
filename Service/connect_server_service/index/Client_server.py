import threading
from datetime import datetime

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QMessageBox
from loguru import logger

from Service.connect_server_service.api.api_client import UpperAPIClient
from Service.connect_server_service.api.websocket_client import WebSocketThread
from Service.connect_server_service.listener.notification_listener import NotificationListener
from public.config_class.global_setting import global_setting
from public.entity.queue.ObjectQueueItem import ObjectQueueItem


class Client_server():
    def __init__(self):
        # 创建客户端
        self.client =None
        # WebSocket 连接线程（用于实时通知）
        self.ws_thread = None
        # 启动通知监听线程（已弃用，改用 WebSocket）
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

            # 启动 WebSocket 连接接收实时通知
            device_filter = global_setting.get_setting("connect_server", {}).get("server", {}).get("device_id", None)
            self.ws_thread = WebSocketThread(
                server_url=server_url,
                client_id="upper_client",
                device_id=device_filter  # 可选，只接收指定设备通知
            )
            
            # 设置 WebSocket 回调
            self.ws_thread.set_notification_callback(self.on_ws_notification)
            self.ws_thread.set_connected_callback(self.on_ws_connected)
            self.ws_thread.set_disconnected_callback(self.on_ws_disconnected)
            self.ws_thread.set_error_callback(self.on_ws_error)
            
            # 启动 WebSocket 线程
            self.ws_thread.start()

            # 启动自动刷新定时器
            self.auto_refresh_timer = QTimer()
            # self.auto_refresh_timer.timeout.connect(self.auto_refresh_data)
            self.auto_refresh_timer.start(int(global_setting.get_setting("connect_server", {}).get("display", {}).get('auto_refresh_interval',5)) *1000)

            self.connected = True
            logger.info("连接服务器成功 (WebSocket 模式)")
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
        # 停止 WebSocket 连接
        if self.ws_thread:
            self.ws_thread.stop()
            self.ws_thread.join(timeout=3)
            
        # 停止旧的轮询监听（如果存在）
        if self.listener:
            self.listener.stop()
            self.listener.wait()

        if self.auto_refresh_timer:
            self.auto_refresh_timer.stop()

        self.connected = False
        logger.info("已断开服务器连接")
        # self.statusBar().showMessage("未连接")
    
    def on_ws_notification(self, data: dict):
        """WebSocket 通知回调"""
        notification_type = data.get("type", "")
        device_id = data.get("device_id", "")
        file_name = data.get("file_name", "")
        
        if notification_type == "excel_upload":
            logger.info(f"[WebSocket] 收到电量数据上传通知: 设备 {device_id} - {file_name}")
            # 发送消息到 main_gui 进程的电量数据查看器
            queue = global_setting.get_setting("queue", None)
            if queue:
                queue.put(ObjectQueueItem(
                    origin="connect_server",
                    to="excel_data_viewer",
                    title="new_excel_data",
                    data=data,
                    time=datetime.now().isoformat()
                ))
                logger.info(f"已发送电量数据通知到队列")
                
        elif notification_type == "image_upload":
            logger.info(f"[WebSocket] 收到几何量数据上传通知: 设备 {device_id} - {file_name}")
            # 发送消息到 main_gui 进程的图片数据查看器
            queue = global_setting.get_setting("queue", None)
            if queue:
                queue.put(ObjectQueueItem(
                    origin="connect_server",
                    to="image_data_viewer",
                    title="new_image_data",
                    data=data,
                    time=datetime.now().isoformat()
                ))
                logger.info(f"已发送图片数据通知到队列")
        else:
            logger.info(f"[WebSocket] 收到通知: {data}")
    
    def on_ws_connected(self):
        """WebSocket 连接成功回调"""
        logger.info("[WebSocket] 已连接到服务器")
    
    def on_ws_disconnected(self):
        """WebSocket 断开连接回调"""
        logger.warning("[WebSocket] 连接已断开")
    
    def on_ws_error(self, error: str):
        """WebSocket 错误回调"""
        logger.error(f"[WebSocket] 错误: {error}")