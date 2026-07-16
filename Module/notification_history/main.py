"""预警通知历史模块入口。"""
from Module.notification_history.index.notification_history_window import NotificationHistoryWindow
from my_abc.BaseInterfaceWidget import BaseInterfaceWidget
from my_abc.BaseModule import BaseModule
from my_abc.BaseService import BaseService
from public.entity.BaseWindow import BaseWindow
from public.entity.enum.Public_Enum import BaseInterfaceType, AppState


class NotificationHistoryService(BaseService):
    """预警通知历史服务占位。"""

    def start(self, resolve, reject):
        resolve()

    def stop(self):
        pass


class NotificationHistoryWidget(BaseInterfaceWidget):
    """预警通知历史界面组件。"""

    def __init__(self):
        super().__init__()
        self.type = self.get_type()
        self.frame_obj = self.create_middle_window()
        self.left_frame_obj = self.create_left_window()
        self.right_frame_obj = self.create_right_window()
        self.bottom_frame_obj = self.create_bottom_window()

    def get_type(self):
        return BaseInterfaceType.WINDOW

    def create_middle_window(self) -> BaseWindow:
        return NotificationHistoryWindow()

    def create_left_window(self) -> BaseWindow:
        return None

    def create_right_window(self) -> BaseWindow:
        return None

    def create_bottom_window(self) -> BaseWindow:
        return None


class NotificationHistoryModule(BaseModule):
    """直接查看服务器 notifications 表中的预警通知历史。"""

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
        return "NotificationHistoryModule"

    def get_title(self):
        return "预警通知历史"

    def get_menu_name(self):
        return {"id": 1, "text": "数据监控"}

    def create_service(self) -> BaseService:
        return NotificationHistoryService()

    def get_interface_widget(self) -> BaseInterfaceWidget:
        widget = NotificationHistoryWidget()
        widget.module = self
        return widget
