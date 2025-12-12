"""
HTTP长轮询客户端 - 替代WebSocket
基于requests实现的长连接通知接收
"""
import requests
import threading
import time
from typing import Callable, Optional
from loguru import logger
from datetime import datetime


class LongPollingClient:
    """HTTP长轮询客户端"""
    
    def __init__(self, server_url: str, client_id: str, device_id: Optional[str] = None):
        """
        初始化长轮询客户端
        
        Args:
            server_url: 服务器地址（如 http://localhost:8000）
            client_id: 客户端唯一标识
            device_id: 可选，指定要监听的设备ID
        """
        self.server_url = server_url.rstrip('/')
        self.client_id = client_id
        self.device_id = device_id
        self.connected = False
        self.running = False
        
        # 回调函数
        self.on_notification: Optional[Callable] = None
        self.on_connected: Optional[Callable] = None
        self.on_disconnected: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        
        # 配置
        self.timeout = 30  # 长轮询超时时间（秒）
        self.retry_interval = 5  # 重试间隔（秒）
        
        logger.info(f"[长轮询客户端] 初始化: {client_id}, 设备过滤: {device_id}")
    
    def start(self):
        """开始长轮询"""
        self.running = True
        self.connected = True
        
        if self.on_connected:
            self.on_connected()
        
        logger.info(f"[长轮询客户端] 开始轮询: {self.server_url}")
        
        while self.running:
            try:
                # 构建请求参数
                params = {
                    'client_id': self.client_id,
                    'timeout': self.timeout
                }
                
                if self.device_id:
                    params['device_id'] = self.device_id
                
                # 发送长轮询请求
                logger.debug(f"[长轮询] 发送请求...")
                response = requests.get(
                    f"{self.server_url}/api/polling/notifications",
                    params=params,
                    timeout=self.timeout + 5  # 请求超时比服务器超时多5秒
                )
                
                if response.status_code == 200:
                    data = response.json()
                    notifications = data.get('notifications', [])
                    
                    if notifications:
                        logger.info(f"[长轮询] 收到 {len(notifications)} 条通知")
                        
                        # 处理每条通知
                        for notification in notifications:
                            if self.on_notification:
                                self.on_notification(notification)
                    else:
                        logger.debug(f"[长轮询] 无新通知")
                else:
                    logger.warning(f"[长轮询] 请求失败: {response.status_code}")
                    time.sleep(self.retry_interval)
                    
            except requests.exceptions.Timeout:
                # 超时是正常的，继续下一次轮询
                logger.debug(f"[长轮询] 请求超时，继续...")
                continue
                
            except requests.exceptions.ConnectionError as e:
                logger.error(f"[长轮询] 连接错误: {e}")
                self.connected = False
                if self.on_error:
                    self.on_error(str(e))
                time.sleep(self.retry_interval)
                
            except Exception as e:
                logger.error(f"[长轮询] 错误: {e}")
                if self.on_error:
                    self.on_error(str(e))
                time.sleep(self.retry_interval)
        
        self.connected = False
        if self.on_disconnected:
            self.on_disconnected()
        
        logger.info(f"[长轮询客户端] 已停止")
    
    def stop(self):
        """停止长轮询"""
        self.running = False
        logger.info(f"[长轮询客户端] 停止中...")
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.connected and self.running


class LongPollingThread(threading.Thread):
    """HTTP长轮询运行线程"""
    
    def __init__(self, server_url: str, client_id: str, device_id: Optional[str] = None):
        super().__init__(daemon=True)
        self.client = LongPollingClient(server_url, client_id, device_id)
        self.running = True
    
    def run(self):
        """运行线程"""
        try:
            self.client.start()
        except Exception as e:
            logger.error(f"[长轮询线程] 错误: {e}")
    
    def stop(self):
        """停止线程"""
        self.running = False
        self.client.stop()
    
    def join(self, timeout=None):
        """等待线程结束"""
        self.stop()
        super().join(timeout)
    
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

