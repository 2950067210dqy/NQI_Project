import typing
from abc import ABC, abstractmethod

from PyQt6.QtCore import QSize
from PyQt6.QtGui import QGuiApplication

from public.entity.BaseWindow import BaseWindow
from public.entity.enum.Public_Enum import Frame_state


class BaseInterfaceWidget(ABC):

    def __init__(self):
        self.type =None
        # 中间窗口
        self.frame_obj:BaseWindow =None
        # 窗口状态
        self.frame_obj_state=Frame_state.Default
        #  左侧窗口
        self.left_frame_obj:  BaseWindow = None
        self.left_frame_obj_state=Frame_state.Default
        #  右侧窗口
        self.right_frame_obj: BaseWindow = None
        self.right_frame_obj_state=Frame_state.Default
        #  bottom窗口
        self.bottom_frame_obj: BaseWindow = None
        self.bottom_frame_obj_state=Frame_state.Default
    @abstractmethod
    def get_type(self)->int:
        """获得类型BaseInterfaceType"""
        pass

    @abstractmethod
    def create_middle_window(self) -> BaseWindow:
        """创建并返回自定义的界面部件middle WINDOW"""
        pass

    @abstractmethod
    def create_left_window(self) -> BaseWindow:
        """创建并返回自定义的界面部件left WINDOW"""
        pass
    @abstractmethod
    def create_right_window(self) -> BaseWindow:
        """创建并返回自定义的界面部件right WINDOW"""
        pass

    @abstractmethod
    def create_bottom_window(self) -> BaseWindow:
        """创建并返回自定义的界面部件bottom WINDOW"""
        pass
    def is_all_closed(self):
        """所有窗口是否关闭"""
        closed_state = [Frame_state.Closed, Frame_state.Default]
        if self.frame_obj_state in closed_state and self.left_frame_obj_state in closed_state and self.right_frame_obj_state in closed_state and self.bottom_frame_obj_state in closed_state:
            return True
        else:
            return False
    def close(self):
        """关闭所有窗口 若有"""
        if self.frame_obj is not None:
            self.frame_obj.close()
        if self.left_frame_obj is not None:
            self.left_frame_obj.close()
        if self.right_frame_obj is not None:
            self.right_frame_obj.close()
        if self.bottom_frame_obj is not None:
            self.bottom_frame_obj.close()
    def show(self):
        """显示页面"""
        if self.frame_obj is not None:
            self.frame_obj.show_frame()
        if self.left_frame_obj is not None:
            self.left_frame_obj.show_frame()
        if self.right_frame_obj is not None:
            self.right_frame_obj.show_frame()
        if self.bottom_frame_obj is not None:
            self.bottom_frame_obj.show_frame()
    def hide(self):
        """隐藏页面"""
        if self.frame_obj is not None:
            self.frame_obj.hide()
        if self.left_frame_obj is not None:
            self.left_frame_obj.hide()
        if self.right_frame_obj is not None:
            self.right_frame_obj.hide()
        if self.bottom_frame_obj is not None:
            self.bottom_frame_obj.hide()
    def setParent(self, parent):
        """设置父界面"""
        if self.frame_obj is not None:
            self.frame_obj.setParent(parent)
        if self.left_frame_obj is not None:
            self.left_frame_obj.setParent(parent)
        if self.right_frame_obj is not None:
            self.right_frame_obj.setParent(parent)
        if self.bottom_frame_obj is not None:
            self.bottom_frame_obj.setParent(parent)
    @typing.overload
    def setMinimumSize(self,width:int,height:int)->None:...
    @typing.overload
    def setMinimumSize(self)->None:...

    @staticmethod
    def _bounded_minimum_size(window: BaseWindow, suggested: QSize) -> QSize:
        """限制模块最小尺寸，避免大页面把主窗口或独立窗口撑到屏幕外。"""
        screen = None
        if window is not None:
            screen = window.screen() or QGuiApplication.screenAt(window.frameGeometry().center())
        screen = screen or QGuiApplication.primaryScreen()
        available = screen.availableGeometry() if screen is not None else None
        if available is None:
            return suggested
        max_width = max(320, int(available.width() * 0.92))
        max_height = max(240, int(available.height() * 0.88))
        return QSize(min(suggested.width(), max_width), min(suggested.height(), max_height))

    def _set_bounded_minimum_size(self, window: BaseWindow):
        if window is None:
            return
        window.setMinimumSize(self._bounded_minimum_size(window, window.calculate_minimum_suggested_size()))

    # 这里是实际的实现
    def setMinimumSize(self, width: typing.Union[int]=None,height: typing.Union[int]=None) -> typing.Union[None]:
        if width is None and height is None:
            self._set_bounded_minimum_size(self.frame_obj)
            self._set_bounded_minimum_size(self.left_frame_obj)
            self._set_bounded_minimum_size(self.right_frame_obj)
            self._set_bounded_minimum_size(self.bottom_frame_obj)
        elif isinstance(width, int) and isinstance(height, int):
            # 设置最小界面大小
            if self.frame_obj is not None:
                self.frame_obj.setMinimumSize(width, height)
            if self.left_frame_obj is not None:
                self.left_frame_obj.setMinimumSize(width, height)
            if self.right_frame_obj is not None:
                self.right_frame_obj.setMinimumSize(width, height)
            if self.bottom_frame_obj is not None:
                self.bottom_frame_obj.setMinimumSize(width, height)
        else:
            raise ValueError("Invalid type")