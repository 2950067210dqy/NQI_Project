from datetime import datetime

from PyQt6.QtCore import QTimer
from loguru import logger

from Service.connect_server_service.api.api_client import UpperAPIClient
from Service.connect_server_service.api.websocket_client import WebSocketThread
from Service.connect_server_service.api.long_polling_client import LongPollingThread
from public.config_class.global_setting import global_setting
from public.entity.queue.ObjectQueueItem import ObjectQueueItem
from public.function.Cache.data_download_manager import download_manager


class Client_server():
    def __init__(self):
        # 创建客户端
        self.client = None
        # WebSocket 连接线程（用于实时通知）
        self.ws_thread = None
        # HTTP长轮询线程（替代WebSocket）
        self.long_polling_thread = None
        # 连接模式：'websocket' 或 'long_polling'
        self.connection_mode = 'long_polling'  # 默认使用长轮询
        # 启动通知监听线程（已弃用）
        self.listener = None
        # 启动自动刷新定时器
        self.auto_refresh_timer = None
        # 连接状态
        self.connected = False

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
            
            # 设置下载管理器的客户端和消息队列
            download_manager.set_client(self)
            queue = global_setting.get_setting("queue", None)
            if queue:
                download_manager.set_message_queue(queue)
                logger.info("[Client_server] 下载管理器消息队列已设置")

            # 设备过滤
            device_filter = global_setting.get_setting("connect_server", {}).get("server", {}).get("device_id", None)
            
            # 根据连接模式选择WebSocket或HTTP长轮询
            if self.connection_mode == 'long_polling':
                # 使用HTTP长轮询
                message = ObjectQueueItem(
                    origin="download_manager",
                    to="MainWindow_index",
                    title="tip",
                    data="[Client_server] 使用HTTP长轮询模式",
                    time=datetime.now().isoformat()
                )

                global_setting.get_setting("queue").put(message)
                logger.info("[Client_server] 使用HTTP长轮询模式")
                self.long_polling_thread = LongPollingThread(
                    server_url=server_url,
                    client_id="upper_client",
                    device_id=device_filter
                )
                
                # 设置回调（接口与WebSocket相同）
                self.long_polling_thread.set_notification_callback(self.on_notification)
                self.long_polling_thread.set_connected_callback(self.on_connected)
                self.long_polling_thread.set_disconnected_callback(self.on_disconnected)
                self.long_polling_thread.set_error_callback(self.on_error)
                
                # 启动长轮询线程
                self.long_polling_thread.start()
                
            else:
                # 使用WebSocket（向后兼容）
                logger.info("[Client_server] 使用WebSocket模式")
                self.ws_thread = WebSocketThread(
                    server_url=server_url,
                    client_id="upper_client",
                    device_id=device_filter
                )
                
                # 设置 WebSocket 回调
                self.ws_thread.set_notification_callback(self.on_notification)
                self.ws_thread.set_connected_callback(self.on_connected)
                self.ws_thread.set_disconnected_callback(self.on_disconnected)
                self.ws_thread.set_error_callback(self.on_error)
                
                # 启动 WebSocket 线程
                self.ws_thread.start()

            # 启动自动刷新定时器
            self.auto_refresh_timer = QTimer()
            # self.auto_refresh_timer.timeout.connect(self.auto_refresh_data)
            self.auto_refresh_timer.start(int(global_setting.get_setting("connect_server", {}).get("display", {}).get('auto_refresh_interval',5)) *1000)

            self.connected = True
            mode_name = "HTTP长轮询" if self.connection_mode == 'long_polling' else "WebSocket"
            logger.info(f"连接服务器成功 ({mode_name} 模式)")
            # 使用HTTP长轮询
            message = ObjectQueueItem(
                origin="download_manager",
                to="MainWindow_index",
                title="tip",
                data=f"连接服务器成功 ({mode_name} 模式)",
                time=datetime.now().isoformat()
            )

            global_setting.get_setting("queue").put(message)
            message = ObjectQueueItem(
                origin="download_manager",
                to="MainWindow_index",
                title="connected",
                data = server_url,
                time=datetime.now().isoformat()
            )

            global_setting.get_setting("queue").put(message)

        except Exception as e:
            logger.error(f"连接失败: {e}", error=True)

    def disconnect_from_server(self):
        """断开服务器连接"""
        # 停止所有下载任务
        download_manager.stop_all_downloads()
        
        # 停止 WebSocket 连接
        if self.ws_thread:
            self.ws_thread.stop()
            self.ws_thread.join(timeout=3)
        
        # 停止 HTTP长轮询连接
        if self.long_polling_thread:
            self.long_polling_thread.stop()
            self.long_polling_thread.join(timeout=3)
            
        # 停止旧的轮询监听（如果存在）
        if self.listener:
            self.listener.stop()
            self.listener.wait()

        if self.auto_refresh_timer:
            self.auto_refresh_timer.stop()

        self.connected = False
        logger.info("已断开服务器连接")
    
    def on_notification(self, data: dict):
        """通知回调（WebSocket和HTTP长轮询通用）"""
        notification_type = data.get("type", "")
        device_id = data.get("device_id", "")
        file_name = data.get("file_name", "")
        
        if notification_type == "excel_upload":
            logger.info(f"[通知] 收到电量数据上传通知: 设备 {device_id} - {file_name}")
            message = ObjectQueueItem(
                origin="download_manager",
                to="MainWindow_index",
                title="tip",
                data=f"[通知] 收到电量数据上传通知: 设备 {device_id} - {file_name}",
                time=datetime.now().isoformat()
            )

            global_setting.get_setting("queue").put(message)
            download_manager.handle_new_data_notification(data)
                
        elif notification_type == "image_upload":
            logger.info(f"[通知] 收到几何量数据上传通知: 设备 {device_id} - {file_name}")
            message = ObjectQueueItem(
                origin="download_manager",
                to="MainWindow_index",
                title="tip",
                data=f"[通知] 收到几何量数据上传通知: 设备 {device_id} - {file_name}",
                time=datetime.now().isoformat()
            )

            global_setting.get_setting("queue").put(message)
            download_manager.handle_new_data_notification(data)
        else:
            logger.info(f"[通知] 收到通知: {data}")
            message = ObjectQueueItem(
                origin="download_manager",
                to="MainWindow_index",
                title="tip",
                data=f"[通知] 收到通知: {data}",
                time=datetime.now().isoformat()
            )

            global_setting.get_setting("queue").put(message)
    
    def on_connected(self):
        """连接成功回调"""
        logger.info("[连接] 已连接到服务器")
    
    def on_disconnected(self):
        """断开连接回调"""
        logger.warning("[连接] 连接已断开")
    
    def on_error(self, error: str):
        """错误回调"""
        logger.error(f"[连接] 错误: {error}")