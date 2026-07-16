"""服务器消息中心模块入口。"""
from Module.server_message_center.index.server_message_center_window import ServerMessageCenterWindow
from my_abc.BaseInterfaceWidget import BaseInterfaceWidget
from my_abc.BaseModule import BaseModule
from my_abc.BaseService import BaseService
from public.entity.BaseWindow import BaseWindow
from public.entity.enum.Public_Enum import BaseInterfaceType, AppState


class ServerMessageCenterService(BaseService):
    """服务器消息中心服务占位。"""

    def start(self, resolve, reject):
        resolve()

    def stop(self):
        pass


class ServerMessageCenterWidget(BaseInterfaceWidget):
    """服务器消息中心界面组件。"""

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
        return ServerMessageCenterWindow()

    def create_left_window(self) -> BaseWindow:
        return None

    def create_right_window(self) -> BaseWindow:
        return None

    def create_bottom_window(self) -> BaseWindow:
        return None


class ServerMessageCenterModule(BaseModule):
    """查看自定义状态栏中累积的服务器消息。"""

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
        return "ServerMessageCenterModule"

    def get_title(self):
        return "服务器消息中心"

    def get_menu_name(self):
        return {"id": 1, "text": "设备"}

    def create_service(self) -> BaseService:
        return ServerMessageCenterService()

    def get_interface_widget(self) -> BaseInterfaceWidget:
        widget = ServerMessageCenterWidget()
        widget.module = self
        return widget
