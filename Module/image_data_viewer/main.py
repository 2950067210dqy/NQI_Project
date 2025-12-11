"""
几何量图片数据查看器模块主文件
"""
from Module.image_data_viewer.index.image_viewer_window import ImageDataViewerWindow
from my_abc.BaseInterfaceWidget import BaseInterfaceWidget
from my_abc.BaseModule import BaseModule
from my_abc.BaseService import BaseService
from public.entity.BaseWindow import BaseWindow
from public.entity.enum.Public_Enum import BaseInterfaceType, AppState


class ImageDataViewerService(BaseService):
    """几何量图片数据查看器服务"""
    
    def __init__(self):
        pass

    def start(self, resolve, reject):
        resolve()
    
    def stop(self):
        pass


class ImageDataViewerWidget(BaseInterfaceWidget):
    """几何量图片数据查看器界面组件"""
    
    def __init__(self):
        super().__init__()
        self.type = self.get_type()
        self.frame_obj = self.create_middle_window()
        self.left_frame_obj = self.create_left_window()
        self.right_frame_obj = self.create_right_window()
        self.bottom_frame_obj = self.create_bottom_window()

    def get_type(self):
        """获得类型"""
        return BaseInterfaceType.WINDOW
    
    def create_middle_window(self) -> BaseWindow:
        """创建中间窗口"""
        window = ImageDataViewerWindow()
        # 立即设置 server_client
        from public.config_class.global_setting import global_setting
        try:
            server_url = global_setting.get_setting("connect_server", {}).get("server", {}).get("url", None)
            if server_url:
                from Service.connect_server_service.api.api_client import UpperAPIClient
                class TempClient:
                    def __init__(self, url):
                        self.client = UpperAPIClient(url)
                window.set_server_client(TempClient(server_url))
        except:
            pass
        return window

    def create_left_window(self) -> BaseWindow:
        """创建左侧窗口"""
        return None

    def create_right_window(self) -> BaseWindow:
        """创建右侧窗口"""
        return None

    def create_bottom_window(self) -> BaseWindow:
        """创建底部窗口"""
        return None


class ImageDataViewerModule(BaseModule):
    """几何量图片数据查看器模块"""
    
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
        """返回组件名称"""
        return "ImageDataViewerModule"
    
    def get_title(self):
        """获取组件标题"""
        return "几何量图片查看器"
    
    def get_menu_name(self):
        """返回组件所属菜单{id:,text:}"""
        return {"id": 1, "text": "数据监控"}
    
    def create_service(self) -> BaseService:
        """创建并返回组件的相关服务"""
        return ImageDataViewerService()
    
    def get_interface_widget(self) -> BaseInterfaceWidget:
        """返回自定义界面构建器"""
        widget_builder = ImageDataViewerWidget()
        widget_builder.module = self
        return widget_builder

