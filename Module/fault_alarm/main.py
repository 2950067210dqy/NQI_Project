"""报警预警模块入口。"""
from Module.fault_alarm.index.fault_alarm_window import FaultAlarmWindow
from my_abc.BaseInterfaceWidget import BaseInterfaceWidget
from my_abc.BaseModule import BaseModule
from my_abc.BaseService import BaseService
from public.entity.BaseWindow import BaseWindow
from public.entity.enum.Public_Enum import BaseInterfaceType, AppState


class FaultAlarmService(BaseService):
    """报警预警服务占位，保留与项目模块体系一致的生命周期。"""

    def start(self, resolve, reject):
        resolve()

    def stop(self):
        pass


class FaultAlarmWidget(BaseInterfaceWidget):
    """报警预警界面组件。"""

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
        return FaultAlarmWindow()

    def create_left_window(self) -> BaseWindow:
        return None

    def create_right_window(self) -> BaseWindow:
        return None

    def create_bottom_window(self) -> BaseWindow:
        return None


class FaultAlarmModule(BaseModule):
    """故障报警、预警列表和人工确认处理界面。"""

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
        return "FaultAlarmModule"

    def get_title(self):
        return "报警预警"

    def get_menu_name(self):
        return {"id": 1, "text": "数据监控"}

    def create_service(self) -> BaseService:
        return FaultAlarmService()

    def get_interface_widget(self) -> BaseInterfaceWidget:
        widget = FaultAlarmWidget()
        widget.module = self
        return widget