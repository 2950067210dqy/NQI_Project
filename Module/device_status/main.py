"""设备在线状态模块入口。"""
from Module.device_status.index.device_status_window import DeviceStatusWindow
from my_abc.BaseInterfaceWidget import BaseInterfaceWidget
from my_abc.BaseModule import BaseModule
from my_abc.BaseService import BaseService
from public.entity.BaseWindow import BaseWindow
from public.entity.enum.Public_Enum import BaseInterfaceType, AppState


class DeviceStatusService(BaseService):
    """设备状态服务占位。"""

    def start(self, resolve, reject):
        resolve()

    def stop(self):
        pass


class DeviceStatusWidget(BaseInterfaceWidget):
    """设备在线状态界面组件。"""

    def __init__(self):
        super().__init__()
        self.type = self.get_type()
        self.frame_obj = self.create_middle_window()
        self.left_frame_obj = None
        self.right_frame_obj = None
        self.bottom_frame_obj = None

    def get_type(self):
        return BaseInterfaceType.WINDOW

    def create_middle_window(self) -> BaseWindow:
        return DeviceStatusWindow()

    def create_left_window(self) -> BaseWindow:
        return None

    def create_right_window(self) -> BaseWindow:
        return None

    def create_bottom_window(self) -> BaseWindow:
        return None


class DeviceStatusModule(BaseModule):
    """查看下位机设备在线状态和最后心跳时间。"""

    def __init__(self):
        super().__init__()
        self.interface_widget = self.get_interface_widget()
        self.name = self.get_name()
        self.title = self.get_title()
        self.menu_name = self.get_menu_name()
        self.service = self.create_service()
        self.app_state = self.get_app_state()

    def get_app_state(self) -> AppState:
        return AppState.INITIALIZED

    def get_name(self):
        return "DeviceStatusModule"

    def get_title(self):
        return "设备在线状态"

    def get_menu_name(self):
        return {"id": 1, "text": "数据监控"}

    def create_service(self) -> BaseService:
        return DeviceStatusService()

    def get_interface_widget(self) -> BaseInterfaceWidget:
        widget = DeviceStatusWidget()
        widget.module = self
        return widget
