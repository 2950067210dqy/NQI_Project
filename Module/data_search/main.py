"""数据检索模块入口。"""
from Module.data_search.index.search_window import DataSearchWindow
from my_abc.BaseInterfaceWidget import BaseInterfaceWidget
from my_abc.BaseModule import BaseModule
from my_abc.BaseService import BaseService
from public.entity.BaseWindow import BaseWindow
from public.entity.enum.Public_Enum import BaseInterfaceType, AppState


class DataSearchService(BaseService):
    """数据检索服务占位，保留与项目模块体系一致的生命周期。"""

    def start(self, resolve, reject):
        resolve()

    def stop(self):
        pass


class DataSearchWidget(BaseInterfaceWidget):
    """数据检索界面组件。"""

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
        return DataSearchWindow()

    def create_left_window(self) -> BaseWindow:
        return None

    def create_right_window(self) -> BaseWindow:
        return None

    def create_bottom_window(self) -> BaseWindow:
        return None


class DataSearchModule(BaseModule):
    """按时间、地点、故障、设备等条件检索服务器数据集。"""

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
        return "DataSearchModule"

    def get_title(self):
        return "数据检索"

    def get_menu_name(self):
        return {"id": 1, "text": "数据监控"}

    def create_service(self) -> BaseService:
        return DataSearchService()

    def get_interface_widget(self) -> BaseInterfaceWidget:
        widget = DataSearchWidget()
        widget.module = self
        return widget