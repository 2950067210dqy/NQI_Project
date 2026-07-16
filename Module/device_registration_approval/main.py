"""设备注册审批模块入口。"""
from Module.device_registration_approval.index.registration_approval_window import RegistrationApprovalWindow
from my_abc.BaseInterfaceWidget import BaseInterfaceWidget
from my_abc.BaseModule import BaseModule
from my_abc.BaseService import BaseService
from public.entity.BaseWindow import BaseWindow
from public.entity.enum.Public_Enum import BaseInterfaceType, AppState


class RegistrationApprovalService(BaseService):
    """设备注册审批服务占位。"""

    def start(self, resolve, reject):
        resolve()

    def stop(self):
        pass


class RegistrationApprovalWidget(BaseInterfaceWidget):
    """设备注册审批界面组件。"""

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
        return RegistrationApprovalWindow()

    def create_left_window(self) -> BaseWindow:
        return None

    def create_right_window(self) -> BaseWindow:
        return None

    def create_bottom_window(self) -> BaseWindow:
        return None


class RegistrationApprovalModule(BaseModule):
    """下位机设备注册审批和审批历史查看界面。"""

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
        return "RegistrationApprovalModule"

    def get_title(self):
        return "设备注册审批"

    def get_menu_name(self):
        return {"id": 1, "text": "数据监控"}

    def create_service(self) -> BaseService:
        return RegistrationApprovalService()

    def get_interface_widget(self) -> BaseInterfaceWidget:
        widget = RegistrationApprovalWidget()
        widget.module = self
        return widget
