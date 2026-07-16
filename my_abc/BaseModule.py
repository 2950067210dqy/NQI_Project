# plugin_interface.py
import queue
from abc import abstractmethod, ABC

from PyQt6.QtCore import QPoint, QRect, QTimer
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QVBoxLayout, QWidget, QScrollArea, QHBoxLayout, QMainWindow

from index import Content_index
from index.Content_index import content_index
from my_abc import BaseInterfaceWidget

from my_abc.BaseService import BaseService
from public.entity.BaseWindow import BaseWindow
from public.entity.enum.Public_Enum import Frame_state, BaseInterfaceType, AppState
from public.function.promise.AsyPromise import AsyPromise
from theme.ThemeQt6 import ThemedWindow


class BaseModule(ABC):

    def __init__(self):
        self.interface_widget:BaseInterfaceWidget =None
        self.name =None
        self.title=None
        self.menu_name=None
        self.service:BaseService =None
        self.main_gui:BaseWindow =None
        self.app_state :AppState =None
        pass
    @abstractmethod
    def get_app_state(self) -> AppState:
        """返回该组件在程序什么状态才能被点击"""
        pass
    @abstractmethod
    def get_menu_name(self):
        """返回组件所属菜单{id:,text:} 在./config/gui_config.ini文件查看"""
        pass
    @abstractmethod
    def get_name(self):
        """返回组件名称"""
        pass
    @abstractmethod
    def get_title(self):
        """获取组件title"""
        pass
    @abstractmethod
    def create_service(self) -> BaseService:
        """创建并返回组件的相关服务"""
        pass

    @abstractmethod
    def get_interface_widget(self) -> BaseInterfaceWidget:
        """返回自定义界面构建器"""
        pass
    def close(self):
        """关闭所有窗口 若有"""
        if self.interface_widget is not None:
            self.interface_widget.close()
    def show(self):
        """显示页面"""
        if self.interface_widget is not None:
            # 重新加载页面 而不是加载之前的页面 start
            # self.interface_widget.close()
            self.interface_widget = None
            self.interface_widget=self.get_interface_widget()
            self.set_main_gui_to_children()
            # 重新加载页面 而不是加载之前的页面 end
            self.interface_widget.show()

    def hide(self):
        """隐藏页面"""
        if self.interface_widget is not None:
            self.interface_widget.hide()
    def setParent(self, parent):
        """设置父界面"""
        if self.interface_widget is not None:
            self.interface_widget.setParent(parent)
    def set_main_gui(self,main_gui:BaseWindow=None) -> None:
        # 获取主界面变量
        self.main_gui=main_gui
        pass
    def set_main_gui_to_children(self):
        # 设置父界面给所有子界面
        if self.interface_widget.frame_obj is not None:
            self.interface_widget.frame_obj.set_main_gui(self.main_gui)
            self.interface_widget.frame_obj_state = Frame_state.Opening
        if self.interface_widget.left_frame_obj is not None:
            self.interface_widget.left_frame_obj.set_main_gui(self.main_gui)
            self.interface_widget.left_frame_obj_state = Frame_state.Opening
        if self.interface_widget.right_frame_obj is not None:
            self.interface_widget.right_frame_obj.set_main_gui(self.main_gui)
            self.interface_widget.right_frame_obj_state = Frame_state.Opening
        if self.interface_widget.bottom_frame_obj is not None:
            self.interface_widget.bottom_frame_obj.set_main_gui(self.main_gui)
            self.interface_widget.bottom_frame_obj_state = Frame_state.Opening
        pass
    # 点击的方法
    def click_method(self):
        AsyPromise(self.start_service).then(
            lambda r:AsyPromise(self.adjustGUIPolicy).then()
        )
        # self.start_service()
        # self.adjustGUIPolicy()
    def _available_screen_rect(self) -> QRect:
        """获取主界面所在屏幕的可用区域，窗口模式统一用它做边界。"""
        if self.main_gui is not None:
            screen = self.main_gui.screen() or QGuiApplication.screenAt(self.main_gui.frameGeometry().center())
        else:
            screen = QGuiApplication.primaryScreen()
        return screen.availableGeometry() if screen is not None else QRect(0, 0, 1280, 720)

    def _bounded_global_rect(self, local_x: int, local_y: int, width: int, height: int) -> QRect:
        """把基于主窗口的局部矩形转换为屏幕矩形，并夹在可见屏幕内。"""
        available = self._available_screen_rect().adjusted(8, 8, -8, -8)
        if self.main_gui is not None:
            global_top_left = self.main_gui.mapToGlobal(QPoint(int(local_x), int(local_y)))
        else:
            global_top_left = QPoint(int(local_x), int(local_y))
        width = max(240, min(int(width), available.width()))
        height = max(180, min(int(height), available.height()))
        x = min(max(global_top_left.x(), available.left()), available.right() - width + 1)
        y = min(max(global_top_left.y(), available.top()), available.bottom() - height + 1)
        return QRect(x, y, width, height)

    def _bounded_screen_rect(self, global_x: int, global_y: int, width: int, height: int) -> QRect:
        """把已经是屏幕坐标的矩形夹在可见屏幕内。"""
        available = self._available_screen_rect().adjusted(0, 0, 0, 0)
        width = max(240, min(int(width), available.width()))
        height = max(180, min(int(height), available.height()))
        x = min(max(int(global_x), available.left()), available.right() - width + 1)
        y = min(max(int(global_y), available.top()), available.bottom() - height + 1)
        return QRect(x, y, width, height)

    def _move_window_frame_to_rect(self, window: QMainWindow, rect: QRect):
        """按外框目标矩形移动窗口，确保模块窗口不遮住主窗口状态栏。"""
        target_width = int(rect.width())
        target_height = int(rect.height())
        window.resize(target_width, target_height)

        frame_geometry = window.frameGeometry()
        frame_delta_width = max(0, frame_geometry.width() - window.geometry().width())
        frame_delta_height = max(0, frame_geometry.height() - window.geometry().height())

        # resize 设置的是内容区大小；这里反算内容区尺寸，让窗口外框落在目标矩形内。
        content_width = max(240, target_width - frame_delta_width)
        content_height = max(180, target_height - frame_delta_height)
        if content_width != window.width() or content_height != window.height():
            window.resize(content_width, content_height)
            frame_geometry = window.frameGeometry()

        client_offset = window.geometry().topLeft() - frame_geometry.topLeft()
        window.move(rect.topLeft() + client_offset)

    def _apply_bounded_screen_geometry(self, window: QMainWindow, global_x: int, global_y: int, width: int, height: int):
        """使用屏幕全局坐标设置模块窗口几何。"""
        # 模块独立窗口由 BaseModule 精确对齐，跳过 BaseWindow 的二次防越界移动。
        setattr(window, "_nqi_skip_auto_screen_adjust", True)
        rect = self._bounded_screen_rect(global_x, global_y, width, height)
        self._move_window_frame_to_rect(window, rect)

    def _apply_bounded_geometry(self, window: QMainWindow, local_x: int, local_y: int, width: int, height: int):
        """设置窗口几何并确保不会跑到屏幕外，避免标题栏被放到屏幕外。"""
        rect = self._bounded_global_rect(local_x, local_y, width, height)
        self._move_window_frame_to_rect(window, rect)
        if hasattr(window, "ensure_within_available_screen"):
            window.ensure_within_available_screen()

    def _module_window_global_top(self) -> int:
        """窗口模式的模块页面外框顶部与主窗口菜单栏底边对齐。"""
        if self.main_gui is None:
            return 0
        menu_bar = self.main_gui.menuBar()
        if menu_bar is not None:
            return menu_bar.mapToGlobal(QPoint(0, menu_bar.height())).y() + 1
        toolbar = getattr(self.main_gui, "toolbar", None)
        if toolbar is not None:
            return toolbar.mapToGlobal(QPoint(0, toolbar.height())).y() + 1
        central_widget = self.main_gui.centralWidget()
        return central_widget.mapToGlobal(QPoint(0, 0)).y() if central_widget is not None else 0

    def _module_window_global_left(self) -> int:
        """模块窗口左侧与主窗口内容外框左侧对齐。"""
        if self.main_gui is None:
            return 0
        return self.main_gui.frameGeometry().left()

    def _module_window_height(self, global_top: int) -> int:
        """计算菜单栏下方到状态栏上方的屏幕可用高度。"""
        if self.main_gui is None:
            return 720
        status_bar = self.main_gui.statusBar()
        if status_bar is not None and status_bar.isVisible():
            bottom = status_bar.mapToGlobal(QPoint(0, 0)).y()
        else:
            bottom = self.main_gui.frameGeometry().bottom()
        return max(240, bottom - global_top)

    def _align_module_window_later(self, window: QMainWindow, global_x: int, global_y: int, width: int, height: int):
        """窗口 show 后多次强制校准，避免 Qt 首次显示时按标题栏/最小尺寸改位置。"""
        setattr(window, "_nqi_skip_auto_screen_adjust", True)
        QTimer.singleShot(0, lambda: self._apply_bounded_screen_geometry(window, global_x, global_y, width, height))
        QTimer.singleShot(120, lambda: self._apply_bounded_screen_geometry(window, global_x, global_y, width, height))
        QTimer.singleShot(350, lambda: self._apply_bounded_screen_geometry(window, global_x, global_y, width, height))

    def start_service(self,resolve,reject):
        """开始服务"""
        if self.service is not None:
            AsyPromise(self.service.start).then(
                lambda r:resolve(r)
            ).catch( lambda e:reject(e))
        else:
            resolve(None)

    def adjustGUIPolicy(self,resolve,reject):
        if self.interface_widget is None or self.interface_widget.type is None or self.interface_widget.frame_obj is None or self.main_gui is None:
            reject(None)
            return

        self.set_main_gui_to_children()
        # 根据type来确定相关策略
        if self.interface_widget.type == BaseInterfaceType.WIDGET or self.interface_widget.type == BaseInterfaceType.FRAME:


            tab_content = QWidget()
            tab_content.setObjectName(f"tab_content_{self.menu_name['text']}_{self.name}")
            tab_layout = QVBoxLayout(tab_content)
            tab_layout.setObjectName(f"tab_content_{self.menu_name['text']}_{self.name}_layout")

            # 创建一个内容小部件并填充内容

            tab_frame = content_index()



            left_layout =tab_frame.findChild(QVBoxLayout, "left_layout")
            right_layout = tab_frame.findChild(QVBoxLayout, "right_layout")
            bottom_layout = tab_frame.findChild(QVBoxLayout, "bottom_layout")
            middle_layout =tab_frame.findChild(QVBoxLayout, "middle_layout")

            scroll_left_layout =    BaseWindow.add_scroll_area_if_not_exists( tab_frame.findChild(QVBoxLayout,"left_layout"))
            scroll_right_layout =   BaseWindow.add_scroll_area_if_not_exists( tab_frame.findChild(QVBoxLayout,"right_layout"))
            scroll_bottom_layout =  BaseWindow.add_scroll_area_if_not_exists( tab_frame.findChild(QVBoxLayout,"bottom_layout"))
            scroll_middle_layout =   BaseWindow.add_scroll_area_if_not_exists(tab_frame.findChild(QVBoxLayout,"middle_layout"))

            scroll_middle_layout.addWidget(self.interface_widget.frame_obj)
            scroll_left_layout.addWidget(self.interface_widget.left_frame_obj)
            scroll_right_layout.addWidget(self.interface_widget.right_frame_obj)
            scroll_bottom_layout.addWidget(self.interface_widget.bottom_frame_obj)
            self.interface_widget.setMinimumSize()
            # 拉伸系数的layout
            main_layout:QVBoxLayout = tab_frame.findChild(QVBoxLayout,"main_layout")
            top_layout:QHBoxLayout = tab_frame.findChild(QHBoxLayout,"top_layout")
            if self.interface_widget.bottom_frame_obj is None:
                "没有bottomlayout"
                main_layout.setStretchFactor(bottom_layout,0)
                main_layout.setStretchFactor(top_layout,6)
            else:
                main_layout.setStretchFactor(bottom_layout,2)
                main_layout.setStretchFactor(top_layout, 4)
            if self.interface_widget.left_frame_obj is None and self.interface_widget.right_frame_obj is None:
                top_layout.setStretchFactor(left_layout,0)
                top_layout.setStretchFactor(middle_layout,6)
                top_layout.setStretchFactor(right_layout,0)
            elif self.interface_widget.left_frame_obj is None:
                top_layout.setStretchFactor(left_layout, 0)
                top_layout.setStretchFactor(middle_layout, 5)
                top_layout.setStretchFactor(right_layout, 1)
            elif self.interface_widget.right_frame_obj is None:
                top_layout.setStretchFactor(left_layout, 1)
                top_layout.setStretchFactor(middle_layout, 5)
                top_layout.setStretchFactor(right_layout, 0)
            else:
                top_layout.setStretchFactor(left_layout, 1)
                top_layout.setStretchFactor(right_layout, 1)
                top_layout.setStretchFactor(middle_layout, 4)
            size_factor = 0.9
            if self.interface_widget.frame_obj is not None:
                self.interface_widget.frame_obj.menuBar().hide()
                self.interface_widget.frame_obj.statusBar().hide()
                self.interface_widget.frame_obj.resize(int(middle_layout.geometry().width()),
                                                       int(middle_layout.geometry().height()*size_factor-self.main_gui.statusBar().height()))


            if self.interface_widget.left_frame_obj is not None:
                self.interface_widget.left_frame_obj.menuBar().hide()
                self.interface_widget.left_frame_obj.statusBar().hide()
                self.interface_widget.left_frame_obj.resize(
                    int(left_layout.geometry().width()),
                    int(left_layout.geometry().height()*size_factor-self.main_gui.statusBar().height()))


            if self.interface_widget.right_frame_obj is not None:
                self.interface_widget.right_frame_obj.menuBar().hide()
                self.interface_widget.right_frame_obj.statusBar().hide()
                self.interface_widget.right_frame_obj.resize(int(right_layout.geometry().width()),
                                                             int(right_layout.geometry().height()*size_factor-self.main_gui.statusBar().height()))


            if self.interface_widget.bottom_frame_obj is not None:
                self.interface_widget.bottom_frame_obj.menuBar().hide()
                self.interface_widget.bottom_frame_obj.statusBar().hide()
                self.interface_widget.bottom_frame_obj.resize(int(bottom_layout.geometry().width()),
                                                              int(bottom_layout.geometry().height()*size_factor-self.main_gui.statusBar().height()))





            # 将 scroll_area 添加进去
            tab_layout.addWidget(tab_frame)
            self.main_gui.tab_widget.addTab(tab_content,self.title)

            # 将界面放入正在显示界面
            if self not in self.main_gui.active_module_widgets:
                self.main_gui.active_module_widgets.append(self)
            pass
        else:
            self.show()
            # WINDOW 模式下以主窗口中央区域顶部为起点，避免重复叠加工具栏高度导致子页面偏下。
            flag = 0
            # ，每部分layout占多少
            if self.interface_widget.bottom_frame_obj is None:
                "没有bottomlayout"
                v_stretch = {'top': 5, 'bottom': 0}
            else:
                v_stretch = {'top': 4, 'bottom': 1}
            if self.interface_widget.left_frame_obj is None and self.interface_widget.right_frame_obj is None:
                h_stretch = {'left': 0, 'middle': 5, 'right': 0}
            elif self.interface_widget.left_frame_obj is None:
                h_stretch = {'left': 0, 'middle': 4, 'right': 1}
            elif self.interface_widget.right_frame_obj is None:
                h_stretch = {'left': 1, 'middle': 4, 'right':0}
            else:
                h_stretch = {'left': 1, 'middle': 3, 'right': 1}

            h_all = h_stretch['left']+h_stretch['middle']+h_stretch['right']
            v_all = v_stretch['top']+v_stretch['bottom']
            module_left = self._module_window_global_left()
            module_top = self._module_window_global_top()
            module_height = self._module_window_height(module_top)
            h_each = self.main_gui.centralWidget().geometry().width()//h_all
            v_each = module_height//v_all

            self.interface_widget.setMinimumSize(0, 0)
            if self.interface_widget.left_frame_obj is not None:
                self.interface_widget.left_frame_obj.menuBar().show()
                self.interface_widget.left_frame_obj.statusBar().show()
                self.interface_widget.left_frame_obj.setWindowTitle(self.title)
                left_x = module_left
                left_y = module_top + flag
                left_w = h_each * (h_stretch['left'])
                left_h = v_each * (v_stretch['top'])
                self._apply_bounded_screen_geometry(self.interface_widget.left_frame_obj, left_x, left_y, left_w, left_h)
                self._align_module_window_later(self.interface_widget.left_frame_obj, left_x, left_y, left_w, left_h)
            if self.interface_widget.frame_obj is not None:
                self.interface_widget.frame_obj.menuBar().show()
                self.interface_widget.frame_obj.statusBar().show()
                self.interface_widget.frame_obj.setWindowTitle(self.title)
                middle_x = module_left + h_each * (h_stretch['left'])
                middle_y = module_top + flag
                middle_w = h_each * (h_stretch['middle'])
                middle_h = v_each * (v_stretch['top'])
                self._apply_bounded_screen_geometry(self.interface_widget.frame_obj, middle_x, middle_y, middle_w, middle_h)
                self._align_module_window_later(self.interface_widget.frame_obj, middle_x, middle_y, middle_w, middle_h)
            if self.interface_widget.right_frame_obj is not None:
                self.interface_widget.right_frame_obj.menuBar().show()
                self.interface_widget.right_frame_obj.statusBar().show()
                self.interface_widget.right_frame_obj.setWindowTitle(self.title)
                right_x = module_left + h_each * (h_stretch['middle'] + h_stretch['left'])
                right_y = module_top + flag
                right_w = h_each * (h_stretch['right'])
                right_h = v_each * (v_stretch['top'])
                self._apply_bounded_screen_geometry(self.interface_widget.right_frame_obj, right_x, right_y, right_w, right_h)
                self._align_module_window_later(self.interface_widget.right_frame_obj, right_x, right_y, right_w, right_h)
            if self.interface_widget.bottom_frame_obj is not None:
                self.interface_widget.bottom_frame_obj.menuBar().show()
                self.interface_widget.bottom_frame_obj.statusBar().show()
                self.interface_widget.bottom_frame_obj.setWindowTitle(self.title)
                bottom_x = module_left
                bottom_y = module_top + v_each * (v_stretch['top']) + flag
                bottom_w = self.main_gui.centralWidget().width()
                bottom_h = v_each * (v_stretch['bottom'])
                self._apply_bounded_screen_geometry(self.interface_widget.bottom_frame_obj, bottom_x, bottom_y, bottom_w, bottom_h)
                self._align_module_window_later(self.interface_widget.bottom_frame_obj, bottom_x, bottom_y, bottom_w, bottom_h)



            # 添加窗口
            if self not in  self.main_gui.open_windows:
                self.main_gui.open_windows.append(self)

            pass

        resolve()
        pass

