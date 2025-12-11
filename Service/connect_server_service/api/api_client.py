import requests
from typing import List, Dict, Optional
from pathlib import Path
from loguru import logger


class UpperAPIClient:
    """上位机API客户端"""

    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()

    def get_unread_notifications(self) -> Dict:
        """获取未读通知"""
        try:
            url = f"{self.base_url}/api/notifications/unread"
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get notifications: {e}")
            raise

    def mark_notification_read(self, notification_id: int) -> Dict:
        """标记通知为已读"""
        try:
            url = f"{self.base_url}/api/notifications/{notification_id}/read"
            response = self.session.put(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to mark notification: {e}")
            raise

    # ==================== 电量数据接口 ====================

    def list_excel_data(self, device_id: str = None, limit: int = 100, skip: int = 0) -> Dict:
        """获取电量数据列表"""
        try:
            url = f"{self.base_url}/api/data/excel"
            params = {'limit': limit, 'skip': skip}
            if device_id:
                params['device_id'] = device_id

            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to list excel data: {e}")
            raise

    def get_excel_detail(self, file_id: int) -> Dict:
        """获取电量数据详情"""
        try:
            url = f"{self.base_url}/api/data/excel/{file_id}"
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get excel detail: {e}")
            raise

    def download_excel_file(self, file_id: int, save_path: Path) -> bool:
        """下载电量数据文件"""
        try:
            url = f"{self.base_url}/api/file/download/excel/{file_id}"
            response = self.session.get(url, stream=True, timeout=self.timeout)
            response.raise_for_status()

            save_path.parent.mkdir(parents=True, exist_ok=True)

            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            return True
        except Exception as e:
            logger.error(f"Failed to download excel file: {e}")
            raise

    # ==================== 几何量数据接口 ====================

    def list_image_data(self, device_id: str = None, limit: int = 100, skip: int = 0) -> Dict:
        """获取几何量数据列表"""
        try:
            url = f"{self.base_url}/api/data/image"
            params = {'limit': limit, 'skip': skip}
            if device_id:
                params['device_id'] = device_id

            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to list image data: {e}")
            raise

    def get_image_detail(self, file_id: int) -> Dict:
        """获取几何量数据详情"""
        try:
            url = f"{self.base_url}/api/data/image/{file_id}"
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get image detail: {e}")
            raise

    def download_image_file(self, file_id: int, save_path: Path) -> bool:
        """下载几何量数据文件"""
        try:
            url = f"{self.base_url}/api/file/download/image/{file_id}"
            response = self.session.get(url, stream=True, timeout=self.timeout)
            response.raise_for_status()

            save_path.parent.mkdir(parents=True, exist_ok=True)

            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            return True
        except Exception as e:
            logger.error(f"Failed to download image file: {e}")
            raise

    # ==================== 混合数据接口 ====================

    def list_all_data(self, device_id: str = None, limit: int = 100, skip: int = 0) -> Dict:
        """获取所有数据（电量和几何量）"""
        try:
            url = f"{self.base_url}/api/data/all"
            params = {'limit': limit, 'skip': skip}
            if device_id:
                params['device_id'] = device_id

            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to list all data: {e}")
            raise

    def download_file(self, data_type: str, file_id: int, save_path: Path) -> bool:
        """
        通用下载接口
        data_type: 'excel' 或 'image'
        """
        try:
            url = f"{self.base_url}/api/file/download/{data_type}/{file_id}"
            response = self.session.get(url, stream=True, timeout=self.timeout)
            response.raise_for_status()

            save_path.parent.mkdir(parents=True, exist_ok=True)

            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            return True
        except Exception as e:
            logger.error(f"Failed to download file: {e}")
            raise

    # ==================== 统计接口 ====================

    def get_device_statistics(self, device_id: str) -> Dict:
        """获取设备统计"""
        try:
            url = f"{self.base_url}/api/statistics/device/{device_id}"
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get device statistics: {e}")
            raise

    def get_system_overview(self) -> Dict:
        """获取系统统计概览"""
        try:
            url = f"{self.base_url}/api/statistics/overview"
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get system overview: {e}")
            raise

    # ==================== 设备接口 ====================

    def list_devices(self) -> Dict:
        """获取设备列表"""
        try:
            url = f"{self.base_url}/api/devices/list"
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to list devices: {e}")
            raise