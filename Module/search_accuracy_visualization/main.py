"""检索准确率可视化模块入口。"""
from Module.search_accuracy_visualization.index.search_accuracy_window import SearchAccuracyVisualizationWindow
from my_abc.BaseInterfaceWidget import BaseInterfaceWidget
from my_abc.BaseModule import BaseModule
from my_abc.BaseService import BaseService
from public.entity.BaseWindow import BaseWindow
from public.entity.enum.Public_Enum import BaseInterfaceType, AppState


class SearchAccuracyVisualizationService(BaseService):
    """检索准确率可视化服务占位，保持与项目模块生命周期一致。"""

    def start(self, resolve, reject):
        resolve()

    def stop(self):
        pass


class SearchAccuracyVisualizationWidget(BaseInterfaceWidget):
    """检索准确率可视化界面组件。"""

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
        return SearchAccuracyVisualizationWindow()

    def create_left_window(self) -> BaseWindow:
        return None

    def create_right_window(self) -> BaseWindow:
        return None

    def create_bottom_window(self) -> BaseWindow:
        return None


class SearchAccuracyVisualizationModule(BaseModule):
    """将检索准确率脚本可视化，展示每次检索请求、进度和错误率。"""

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
        return "SearchAccuracyVisualizationModule"

    def get_title(self):
        return "检索准确率可视化"

    def get_menu_name(self):
        return {"id": 1, "text": "工具"}

    def create_service(self) -> BaseService:
        return SearchAccuracyVisualizationService()

    def get_interface_widget(self) -> BaseInterfaceWidget:
        widget = SearchAccuracyVisualizationWidget()
        widget.module = self
        return widget
