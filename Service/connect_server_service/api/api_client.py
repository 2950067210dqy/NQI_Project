from typing import List, Dict, Optional
from pathlib import Path
from loguru import logger

from Service.connect_server_service.api.http_retry import create_retry_session


class UpperAPIClient:
    """上位机API客户端"""

    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = str(base_url or '').strip().rstrip('/')
        self.timeout = timeout
        # 所有业务请求按 INI 配置尝试，只有最终失败才会传给页面错误回调。
        self.session = create_retry_session()

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

    # ==================== 报警延迟测试接口 ====================

    def upload_alarm_latency_file(self, file_path: Path) -> Dict:
        """上传不落正式文件记录的报警延迟测试文件。"""
        file_path = Path(file_path)
        url = f"{self.base_url}/api/alarm-latency/test"
        # 测试 POST 禁止自动重试，避免网络异常时重复触发预警。
        upload_session = create_retry_session(max_attempts=1)
        with file_path.open("rb") as stream:
            response = upload_session.post(
                url,
                files={"file": (file_path.name, stream)},
                timeout=max(self.timeout, 5),
            )
        response.raise_for_status()
        return response.json()

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

    def list_devices(self, timeout: int = None) -> Dict:
        """获取设备列表；状态栏后台轮询可传入较短超时，避免设备离线或服务端慢响应时拖住界面。"""
        try:
            url = f"{self.base_url}/api/devices/list"
            response = self.session.get(url, timeout=timeout or self.timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to list devices: {e}")
            raise

    def list_registration_requests(
            self,
            status: str = None,
            device_id: str = None,
            keyword: str = None
    ) -> Dict:
        """获取设备注册申请列表，供上位机审批页面筛选展示。"""
        url = f"{self.base_url}/api/device/registration-requests"
        params = {
            "status": status,
            "device_id": device_id,
            "keyword": keyword,
        }
        response = self.session.get(
            url,
            params={k: v for k, v in params.items() if v not in (None, "")},
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def approve_registration_request(self, request_id: int, review_message: str = "approved") -> Dict:
        """批准下位机注册申请。"""
        url = f"{self.base_url}/api/device/registration-requests/{request_id}/approve"
        response = self.session.post(url, data={"review_message": review_message}, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def reject_registration_request(self, request_id: int, review_message: str = "rejected") -> Dict:
        """驳回下位机注册申请。"""
        url = f"{self.base_url}/api/device/registration-requests/{request_id}/reject"
        response = self.session.post(url, data={"review_message": review_message}, timeout=self.timeout)
        response.raise_for_status()
        return response.json()
    def search_data(self, **filters) -> Dict:
        """按时间、地点、故障、设备号等条件检索数据集。"""
        url = f"{self.base_url}/api/search/data"
        # 空字符串不应作为检索条件传给服务端，否则可编辑下拉框清空后仍可能干扰精细字段过滤。
        params = {key: value for key, value in filters.items() if value not in (None, "")}
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def list_faults(self, device_id: str = None, status: str = None, limit: int = 100, skip: int = 0) -> Dict:
        """查询故障报警记录。"""
        url = f"{self.base_url}/api/faults"
        params = {"device_id": device_id, "status": status, "limit": limit, "skip": skip}
        response = self.session.get(url, params={k: v for k, v in params.items() if v is not None}, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def report_fault(self, device_id: str, data_type: str, file_id: int, message: str, severity: str = "warning") -> Dict:
        """手动提交故障反馈。"""
        url = f"{self.base_url}/api/faults/report"
        response = self.session.post(url, data={
            "device_id": device_id,
            "data_type": data_type,
            "file_id": file_id,
            "message": message,
            "severity": severity
        }, timeout=self.timeout)
        response.raise_for_status()
        return response.json()
    def update_fault_status(self, fault_id: int, status: str = "acknowledged") -> Dict:
        """更新故障报警状态，用于上位机报警预警界面的确认和关闭操作。"""
        url = f"{self.base_url}/api/faults/{fault_id}/status"
        response = self.session.post(url, data={"status": status}, timeout=self.timeout)
        response.raise_for_status()
        return response.json()


    def list_alarm_rules(self, data_type: str = None, enabled: bool = None) -> Dict:
        """获取服务器预警规则列表，供上位机预警配置界面展示。"""
        url = f"{self.base_url}/api/alarm-rules"
        params = {"data_type": data_type, "enabled": enabled}
        response = self.session.get(
            url,
            params={k: v for k, v in params.items() if v is not None},
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()

    def save_alarm_rule(self, payload: Dict) -> Dict:
        """保存预警规则到服务器，可用于新增或更新。"""
        url = f"{self.base_url}/api/alarm-rules/save"
        response = self.session.post(url, json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def list_notifications(
            self,
            notification_type: str = None,
            device_id: str = None,
            status: str = None,
            keyword: str = None,
            limit: int = 100,
            skip: int = 0
    ) -> Dict:
        """查询通知历史，可用于预警通知历史界面。"""
        url = f"{self.base_url}/api/notifications"
        params = {
            "notification_type": notification_type,
            "device_id": device_id,
            "status": status,
            "keyword": keyword,
            "limit": limit,
            "skip": skip,
        }
        response = self.session.get(
            url,
            params={k: v for k, v in params.items() if v is not None},
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()
