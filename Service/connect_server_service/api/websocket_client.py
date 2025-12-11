import asyncio
import json
import websockets
from typing import Callable, Optional
from loguru import logger
from datetime import datetime
import threading
from queue import Queue


class WebSocketClient:
    """WebSocket 客户端"""

    def __init__(self, server_url: str, client_id: str, device_id: str = None):
        """
        初始化 WebSocket 客户端

        Args:
            server_url: 服务器地址（如 http://localhost:8000）
            client_id: 客户端唯一标识
            device_id: 可选，指定要监听的设备ID
        """
        # 转换 http/https 为 ws/wss
        self.ws_url = server_url.replace("http://", "ws://").replace("https://", "wss://")
        self.client_id = client_id
        self.device_id = device_id
        self.websocket = None
        self.connected = False
        self.running = False

        # 消息队列和回调
        self.message_queue = Queue()
        self.on_notification: Optional[Callable] = None
        self.on_connected: Optional[Callable] = None
        self.on_disconnected: Optional[Callable] = None
        self.on_error: Optional[Callable] = None

        # 心跳相关
        self.heartbeat_interval = 30  # 秒
        self.last_heartbeat = datetime.now()

    async def connect(self):
        """连接到 WebSocket 服务器"""
        try:
            # 构建 WebSocket URL - 使用新的上位机端点
            ws_endpoint = f"{self.ws_url}/ws/upper"
            if self.device_id:
                ws_endpoint += f"?device_id={self.device_id}"

            logger.info(f"正在连接 WebSocket: {ws_endpoint}")

            async with websockets.connect(ws_endpoint) as websocket:
                self.websocket = websocket
                self.connected = True
                self.running = True

                logger.info(f"WebSocket 已连接: {self.client_id} (device_filter={self.device_id})")

                # 调用连接成功回调
                if self.on_connected:
                    self.on_connected()

                # 接收消息循环
                await self._receive_messages()

        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket 连接已关闭")
            self.connected = False
        except asyncio.CancelledError:
            logger.info("WebSocket 连接被取消")
            self.connected = False
        except Exception as e:
            logger.error(f"WebSocket 连接错误: {e}")
            self.connected = False
            if self.on_error:
                self.on_error(str(e))
        finally:
            self.websocket = None
            if self.on_disconnected:
                self.on_disconnected()

    async def _receive_messages(self):
        """接收消息"""
        try:
            while self.running and self.websocket:
                try:
                    message = await asyncio.wait_for(
                        self.websocket.recv(),
                        timeout=60  # 60秒超时
                    )

                    # 服务端可能发送简单的 "pong" 字符串或 JSON
                    if message.strip().lower() == "pong":
                        self.last_heartbeat = datetime.now()
                        logger.debug("心跳响应收到")
                        continue

                    # 解析 JSON 消息
                    try:
                        data = json.loads(message)
                        message_type = data.get("type", "")

                        # 处理各类通知 (excel_upload, image_upload)
                        if message_type in ["excel_upload", "image_upload"]:
                            # 处理数据上传通知
                            logger.info(f"收到通知: {message_type} - 设备 {data.get('device_id')} - {data.get('file_name')}")

                            # 加入消息队列
                            self.message_queue.put(data)

                            # 调用通知回调
                            if self.on_notification:
                                self.on_notification(data)

                        elif message_type == "pong":
                            self.last_heartbeat = datetime.now()
                            logger.debug("心跳响应收到")

                        else:
                            # 未知消息类型，但也处理
                            logger.info(f"收到消息: {data}")
                            self.message_queue.put(data)
                            if self.on_notification:
                                self.on_notification(data)

                    except json.JSONDecodeError:
                        logger.warning(f"无法解析消息: {message}")

                except asyncio.TimeoutError:
                    # 发送心跳
                    try:
                        await self._send_ping()
                    except Exception as e:
                        logger.error(f"发送心跳失败: {e}")
                        break

        except Exception as e:
            logger.error(f"接收消息错误: {e}")
            if self.on_error:
                self.on_error(str(e))

    async def _send_ping(self):
        """发送心跳"""
        if self.websocket and self.connected:
            try:
                # 服务端期望简单的 "ping" 字符串
                await self.websocket.send("ping")
                logger.debug("心跳已发送")
            except Exception as e:
                logger.error(f"发送心跳失败: {e}")
                self.connected = False

    async def disconnect(self):
        """断开连接"""
        self.running = False

        if self.websocket:
            try:
                await self.websocket.close()
            except:
                pass

        self.websocket = None
        self.connected = False
        logger.info(f"WebSocket 连接已断开: {self.client_id}")

    def get_message(self, timeout: float = 1.0) -> Optional[dict]:
        """获取消息队列中的消息"""
        try:
            return self.message_queue.get(timeout=timeout)
        except:
            return None

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.connected and self.websocket is not None


class WebSocketThread(threading.Thread):
    """WebSocket 运行线程"""

    def __init__(self, server_url: str, client_id: str, device_id: str = None):
        super().__init__(daemon=True)
        self.client = WebSocketClient(server_url, client_id, device_id)
        self.loop = None
        self.running = True

    def run(self):
        """运行线程"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        try:
            self.loop.run_until_complete(self.client.connect())
        except Exception as e:
            logger.error(f"WebSocket 线程错误: {e}")
        finally:
            self.loop.close()

    def stop(self):
        """停止线程"""
        self.running = False

        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.client.disconnect(),
                self.loop
            )

    def set_notification_callback(self, callback: Callable):
        """设置通知回调"""
        self.client.on_notification = callback

    def set_connected_callback(self, callback: Callable):
        """设置连接成功回调"""
        self.client.on_connected = callback

    def set_disconnected_callback(self, callback: Callable):
        """设置断开连接回调"""
        self.client.on_disconnected = callback

    def set_error_callback(self, callback: Callable):
        """设置错误回调"""
        self.client.on_error = callback

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.client.is_connected()