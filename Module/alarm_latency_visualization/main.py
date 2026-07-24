"""报警延迟可视化模块入口。"""
from Module.alarm_latency_visualization.index.alarm_latency_window import AlarmLatencyVisualizationWindow
from my_abc.BaseInterfaceWidget import BaseInterfaceWidget
from my_abc.BaseModule import BaseModule
from my_abc.BaseService import BaseService
from public.entity.BaseWindow import BaseWindow
from public.entity.enum.Public_Enum import BaseInterfaceType, AppState


class AlarmLatencyVisualizationService(BaseService):
    """保持与上位机模块生命周期一致。"""

    def start(self, resolve, reject):
        resolve()

    def stop(self):
        pass


class AlarmLatencyVisualizationWidget(BaseInterfaceWidget):
    """报警延迟可视化界面组件。"""

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
        return AlarmLatencyVisualizationWindow()

    def create_left_window(self) -> BaseWindow:
        return None

    def create_right_window(self) -> BaseWindow:
        return None

    def create_bottom_window(self) -> BaseWindow:
        return None


class AlarmLatencyVisualizationModule(BaseModule):
    """上传真实电量和几何量文件并可视化服务器报警延迟。"""

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
        return "AlarmLatencyVisualizationModule"

    def get_title(self):
        return "报警延迟可视化"

    def get_menu_name(self):
        return {"id": 1, "text": "工具"}

    def create_service(self) -> BaseService:
        return AlarmLatencyVisualizationService()

    def get_interface_widget(self) -> BaseInterfaceWidget:
        widget = AlarmLatencyVisualizationWidget()
        widget.module = self
        return widget
