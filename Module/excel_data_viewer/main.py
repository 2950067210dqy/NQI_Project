"""
电量数据查看器模块主文件
"""
from Module.excel_data_viewer.index.excel_viewer_window import ExcelDataViewerWindow
from my_abc.BaseInterfaceWidget import BaseInterfaceWidget
from my_abc.BaseModule import BaseModule
from my_abc.BaseService import BaseService
from public.entity.BaseWindow import BaseWindow
from public.entity.enum.Public_Enum import BaseInterfaceType, AppState


class ExcelDataViewerService(BaseService):
    """电量数据查看器服务"""
    
    def __init__(self):
        self.window = None

    def start(self, resolve, reject):
        # 获取 server_client 并设置到窗口
        from public.config_class.global_setting import global_setting
        from Service.connect_server_service.index.Client_server import Client_server
        
        # 注意：这里需要获取 connect_server_service 的 client_server 实例
        # 由于是不同进程，我们通过配置获取服务器地址，创建自己的客户端
        try:
            server_url = global_setting.get_setting("connect_server", {}).get("server", {}).get("url", None)
            if server_url and self.window:
                from Service.connect_server_service.api.api_client import UpperAPIClient
                # 创建临时客户端用于下载（复用连接）
                class TempClient:
                    def __init__(self, url):
                        self.client = UpperAPIClient(url)
                
                temp_client = TempClient(server_url)
                self.window.set_server_client(temp_client)
        except Exception as e:
            from loguru import logger
            logger.error(f"设置 server_client 失败: {e}")
        
        resolve()
    
    def stop(self):
        pass
    
    def set_window(self, window):
        """设置窗口引用"""
        self.window = window


class ExcelDataViewerWidget(BaseInterfaceWidget):
    """电量数据查看器界面组件"""
    
    def __init__(self):
        super().__init__()
        self.type = self.get_type()
        self.frame_obj = self.create_middle_window()
        self.left_frame_obj = self.create_left_window()
        self.right_frame_obj = self.create_right_window()
        self.bottom_frame_obj = self.create_bottom_window()
        
        # 设置窗口引用到服务（延迟设置）
        if hasattr(self, 'module') and self.module and hasattr(self.module, 'service'):
            self.module.service.set_window(self.frame_obj)

    def get_type(self):
        """获得类型"""
        return BaseInterfaceType.WINDOW
    
    def create_middle_window(self) -> BaseWindow:
        """创建中间窗口"""
        window = ExcelDataViewerWindow()
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


class ExcelDataViewerModule(BaseModule):
    """电量数据查看器模块"""
    
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
        return "ExcelDataViewerModule"
    
    def get_title(self):
        """获取组件标题"""
        return "电量数据查看器"
    
    def get_menu_name(self):
        """返回组件所属菜单{id:,text:}"""
        return {"id": 1, "text": "数据监控"}
    
    def create_service(self) -> BaseService:
        """创建并返回组件的相关服务"""
        return ExcelDataViewerService()
    
    def get_interface_widget(self) -> BaseInterfaceWidget:
        """返回自定义界面构建器"""
        widget_builder = ExcelDataViewerWidget()
        widget_builder.module = self
        return widget_builder

