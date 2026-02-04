import importlib
import json
import os
import time
from json import JSONDecodeError
from PyQt6 import QtCore
from PyQt6.QtCore import QTimer, QObject, pyqtSignal, Qt
from PyQt6.QtGui import QAction, QPixmap
from PyQt6.QtWidgets import QMessageBox, QVBoxLayout, QToolBar, QTabWidget, QDialog, QMenu, QMenuBar, QWidget, \
    QApplication, QLabel, QSizePolicy
from loguru import logger




from my_abc.BaseModule import BaseModule
from public.component.Guide_tutorial_interface.Tutorial_Manager import TutorialManager
from public.component.custom_status_bar import CustomStatusBar
from public.component.dialog.custom.loading_dialog_seconds import AnimatedLoadingDialog
from public.component.mask.LoadingMask import LoadingContext
from public.config_class.App_Setting import AppSettings
from public.config_class.global_setting import global_setting
from public.entity.MyQThread import MyQThread
from public.entity.enum.Public_Enum import BaseInterfaceType, AppState, Tutorial_Type
from public.entity.queue.ObjectQueueItem import ObjectQueueItem

from public.function.promise.AsyPromise import AsyPromise

from public.util.time_util import time_util
from theme.ThemeQt6 import ThemedWindow
from ui.MainWindow import Ui_MainWindow
#logger = logger.bind(category="gui_logger")


class read_queue_data_Thread(MyQThread):
    def __init__(self, name,window=None):
        super().__init__(name)
        self.queue = None

        self.window:MainWindow_Index = window


        pass

    def dosomething(self):
        if self.queue and  not self.queue.empty():
            try:
                message: ObjectQueueItem = self.queue.get()
            except Exception as e:
                logger.error(f"{self.name}发生错误{e}")
                return

            if message is not None and message.is_Empty():
                return
            if message is not None and isinstance(message, ObjectQueueItem) and message.to=='MainWindow_index':
                # logger.error(f"{self.name}_get_message:{message}")
                match message.title:
                    case "connected":
                        global_setting.set_setting("app_state",AppState.CONNECTED)
                        self.window.change_enable_component_app_state()
                        if self.window.status_bar is not None:
                            self.window.status_bar.update_server_label(f"已连接到服务器：{message.data}")
                            self.window.url = message.data
                        pass
                    case "tip":
                        if self.window.status_bar is not None:
                            self.window.status_bar.update_tip(message.data)
                            pass
                    case _:
                        pass

            else:
                # 把消息放回去
                self.queue.put(message)
    def close_stop_experiment_dialog(self):
        if self.window is not None and self.window.stop_dialog is not None:
            self.window.stop_dialog.update_progress_value(self.window.stop_dialog.progress_max)
read_queue_data_thread = read_queue_data_Thread(name="MainWindow_index_read_queue_data_thread")
class MainWindow_Index(ThemedWindow):
    # 根据程序状态来改变是否可以点击的组件
    change_enable_component_app_state_signal = QtCore.pyqtSignal()

    def close_window_handle(self):
        """
        关闭窗口执行的事件
        :return:
        """
        state = global_setting.get_setting("app_state", None)
        # 如果在开始实验期间关闭窗口
        if state is not None and state ==AppState.CONNECTED:
            # 停止
            pass
        # 关闭所有串口

    def closeEvent(self, event):
        app_state = global_setting.get_setting("app_state", AppState.INITIALIZED)
        if len(self.open_windows)!=0:
            # 可选择使用 QMessageBox 来确认是否关闭
            if app_state == AppState.CONNECTED:
                message="当前正在连接服务器，且还有其他子窗口未关闭,退出程序将断开连接，你确定要退出程序吗？"
            else:
                message ="当前还有其他子窗口未关闭，你确定要退出程序吗？"
            reply = QMessageBox.question(self, '关闭窗口',
                                         message,
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                for window in self.open_windows:
                    self.close_window_handle()
                    window.close()
                # 关闭所有窗口
                QApplication.closeAllWindows()
                event.accept()  # 关闭窗口
            else:
                event.ignore()  # 忽略关闭事件
        else:
            # 可选择使用 QMessageBox 来确认是否关闭
            if app_state == AppState.CONNECTED:
                message = "当前正在连接服务器,退出程序将断开连接，你确定要退出程序吗？"
            else:
                message = "你确定要退出程序吗？"
            reply = QMessageBox.question(self, '关闭窗口',
                                         message,
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.close_window_handle()
                # 关闭所有窗口
                QApplication.closeAllWindows()
                event.accept()  # 关闭窗口
            else:
                event.ignore()  # 忽略关闭事件
        pass
    def setup_tutorial(self):
        #实例化提示引导器 下面式实例化模板
        if self.tutorial:
            self.tutorial.end_tutorial()

        self.tutorial = TutorialManager(self, "MainWindow_index", Tutorial_Type.ARROW_GUIDE, global_setting.get_setting("app_setting", AppSettings()))

        # 连接教程完成信号
        self.tutorial.tutorial_completed.connect(self.on_tutorial_completed)

        # 添加更详细的引导步骤
        actions = self.menuBar().actions()
        widgets = self.findChildren(QObject, "temp_deleted_widget")
        for action in actions:
            action:QAction
            menu:QMenu = action.menu()
            if menu:
                # 获取菜单栏中的按钮控件
                geometry = self.menuBar().actionGeometry(action)
                if not widgets:
                    widget =QWidget()
                    widget.setParent(self)
                    widget.setGeometry(geometry)
                    widget.setObjectName("temp_deleted_widget")

                    # 对 file_menu 进行操作
                    self.tutorial.add_step(widget,
                                           f"单击此按钮是{action.text()}\n{menu.toolTip()}")
                else:
                    widget =widgets.pop(0)
                    widget.show()
                    self.tutorial.add_step(widget,
                                           f"单击此按钮是{action.text()}\n{menu.toolTip()}")
        for tool_bar_action in self.tool_bar_actions:
            self.tutorial.add_step(tool_bar_action['action'].associatedObjects()[1],
                               f"单击此按钮是{tool_bar_action['name']}\n{tool_bar_action['tip']}")
        # 状态栏提示
        self.tutorial.add_step(self.status_bar.time_label,
                               f"显示当前时间。")
        self.tutorial.add_step(self.status_bar.app_status_label,
                               f"显示当前程序状态 。\n 1.INITIALIZED: 初始化状态\n 2.APPLYING: 应用实验状态\n 3.CONFIGURING: 设备配置状态\n 4.MONITORING: 开始监测数据状态")

        self.tutorial.add_step(self.status_bar.tip_label,
                               f"显示当前帮助消息。")
        self.tutorial.add_step(self.status_bar.server_label,
                               f"显示当前服务器连接路径。")

        self.tutorial.add_step(self.status_bar.progress_bar,
                               f"显示进度条。")
        #步骤提示
        widgets = self.findChildren(QObject, "temp_deleted_widget")
        for action in actions:
            action: QAction
            menu: QMenu = action.menu()
            if menu:
                # 获取菜单栏中的按钮控件
                geometry = self.menuBar().actionGeometry(action)
                if not widgets:
                    widget = QWidget()
                    widget.setParent(self)
                    widget.setGeometry(geometry)
                    widget.setObjectName("temp_deleted_widget")

                    # 对 file_menu 进行操作
                    self.tutorial.add_step(widget,
                                           f"不知道怎么操作？请跟着步骤指引\n1.单击{action.text()}菜单\n2.在单击打开或导入")
                else:
                    widget = widgets.pop(0)
                    widget.show()
                    self.tutorial.add_step(widget,
                                           f"不知道怎么操作？请跟着步骤指引\n1.单击{action.text()}菜单\n2.在单击打开或导入")
            break
        self.tutorial.add_step(self.status_bar.tip_btn,
                               f"Tips：\n如果还不会操作，可再次单击该按钮查看教程。")
    def __init__(self):
        super().__init__()

        # tool——bar-action 工具栏的action [{'obj_name':'','name';",'action':QAction,'tip':''}]
        self.url = ""
        self.tool_bar_actions = []
        self.menu_bar_actions = []
        # 模块
        self.modules =[]
        # 正在显示的Widget
        self.active_module_widgets:[BaseModule]=[]
        # 打开的窗口
        self.open_windows:[BaseModule]=[]
        # 工具栏
        self.toolbar = None
        #状态栏
        self.status_bar:CustomStatusBar = None
        # 内容layout
        self.content_layout :QVBoxLayout =None
        # tab_widget
        self.tab_widget :QTabWidget =None
        # 实例化ui
        self._init_ui()
        # 实例化自定义ui
        self._init_customize_ui()
        # 实例化功能
        self._init_function()
        # 加载qss样式表
        self._init_custom_style_sheet()
        self._retranslateUi()
        # 实例化提示器
        self.setup_tutorial()
        # 自动启动提示教程 如果有提示页面的话
        QTimer.singleShot(400, self.start_tutorial_if_exists)
        pass
    # 实例化ui
    def _init_ui(self, title=""):
        # 将ui文件转成py文件后 直接实例化该py文件里的类对象  uic工具转换之后就是这一段代码
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        # 设置窗口大小为屏幕大小
        self.setGeometry(global_setting.get_setting("screen"))
        self.setObjectName("mainWindow_Index")
        pass
    def _init_customize_ui(self):
        global read_queue_data_thread
        read_queue_data_thread.queue = global_setting.get_setting("queue",None)
        read_queue_data_thread.window=self
        read_queue_data_thread.start()
        self.content_layout = self.findChild(QVBoxLayout,"content_layout")
        self.tab_widget:QTabWidget = self.findChild(QTabWidget,"tab_widget")
        # 启用标签关闭按钮
        self.tab_widget.setTabsClosable(True)
        # 允许标签拖动重新排序
        self.tab_widget.setMovable(True)
        # 连接标签关闭信号
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        # 加载模块
        self.modules = self.load_modules()
        # 实例化菜单
        # [{id:0,text:"文件"},....]
        menu_name=global_setting.get_setting("configer")['menu']['menu_name']
        self.menu_name = None
        if menu_name is not None and menu_name != "":
            try:
                self.menu_name =  json.loads(menu_name)
            except JSONDecodeError  as e:
                logger.error(f"读取菜单json字符串解析错误：{e}")
                self.menu_name = None
            except Exception as e:
                logger.error(e)
                self.menu_name = None
            if self.menu_name is not None:
                # 创建菜单栏
                self.create_menu_bar()
            pass
        # 创建工具栏
        self.create_tool_bar()
        # 初始化自定义状态栏
        self.status_bar = CustomStatusBar(self)
        self.setStatusBar(self.status_bar)
        super()._init_customize_ui()
        pass
    def _init_function(self):
        # 改变组件是否被点击
        self.change_enable_component_app_state()
        # 连接信号
        self.change_enable_component_app_state_signal.connect(self.change_enable_component_app_state)
        pass
    # 创建工具栏
    def create_tool_bar(self):
        # 创建 QToolBar
        self.toolbar = QToolBar("Toolbar")
        self.addToolBar(self.toolbar)
        # 创建动作（Action）
        name ="窗口变换"
        obj_name ="window_exchange"
        action_one = QAction(name, self)
        action_one.setObjectName(obj_name)
        action_one.setToolTip(name)
        action_one.triggered.connect(self.exchange_widget_and_window)
        self.tool_bar_actions.append({"name":name,"obj_name":obj_name,"action":action_one,"app_state":AppState.INITIALIZED,'tip':"单击此按钮会将打开的窗口变成内嵌抽屉页。"})
        name = "更改主题颜色"
        obj_name = "toggle_mode"
        action_two= QAction(name, self)
        action_two.setObjectName(obj_name)
        action_two.setToolTip(name)
        action_two.triggered.connect(self.toggle_theme)
        self.tool_bar_actions.append({"name":name,"obj_name":obj_name,"action":action_two,"app_state":AppState.INITIALIZED,'tip':"单击此按钮会将程序的主题颜色变换黑色和白色"})


        name = "重置教程页"
        obj_name = "reset_guidance"
        action_final = QAction(name, self)
        action_final.setObjectName(obj_name)
        action_final.setToolTip(name)
        action_final.triggered.connect(self.reset_guidance)
        action_final.setDisabled(True)
        self.tool_bar_actions.append(
            {"name": name, "obj_name": obj_name, "action": action_final, "app_state": AppState.INITIALIZED,
             'tip': "单击此按钮会将重置教程。"})




        # 将动作添加到工具栏
        self.toolbar.addAction(action_one)
        self.toolbar.addSeparator()
        self.toolbar.addAction(action_two)
        self.toolbar.addSeparator()

        self.toolbar.addAction(action_final)
        self.toolbar.addSeparator()
        # 创建一个空的QWidget作为占位符，让它扩展填充剩余空间
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self.toolbar.addWidget(spacer)
        icon_image = QLabel()
        icon_image.setAlignment(Qt.AlignmentFlag.AlignLeft)
        icon_image.setPixmap(QPixmap(global_setting.get_setting("configer")['window']['nqi_path']).scaledToHeight(50))
        self.toolbar.addWidget(icon_image)
        spacer_2 = QWidget()
        spacer_2.setFixedWidth(30)
        self.toolbar.addWidget(spacer_2)
        school_image = QLabel()
        school_image.setAlignment(Qt.AlignmentFlag.AlignRight)
        school_image.setPixmap(QPixmap(global_setting.get_setting("configer")['window']['school_path']).scaledToHeight(50))
        self.toolbar.addWidget(school_image)
    def create_menu_bar(self):
    # 创建菜单
        for menu_dict in self.menu_name:
            # 创建文件菜单
            menu = self.menuBar().addMenu(menu_dict['text'])
            menu.setToolTip(menu_dict.get('tip',""))
            # 从module加载组件...
            for module in self.modules:
                module:BaseModule
                module_menu_name = module.menu_name
                module_title = module.title
                if module_menu_name is not None and module_menu_name != "" and "id" in module_menu_name and "id" in menu_dict and menu_dict["id"] == module_menu_name["id"]:
                    # 创建menu action
                    module.set_main_gui(main_gui=self)
                    action = QAction(module_title, self)
                    action.setObjectName(f"{module.name}")
                    # 创建点击事件
                    # action.triggered.connect(module.start_service)
                    action.triggered.connect(module.click_method)
                    # action.triggered.connect( module.adjustGUIPolicy)
                    # action.triggered.connect( module.interface_widget.show)
                    self.menu_bar_actions.append(
                        {"name": module_title, "obj_name": f"{module.name}", "action": action, "app_state": module.app_state})
                    # 将操作添加到文件菜单
                    menu.addAction(action)
                    menu.addSeparator()  # 添加分隔线
        pass
    def _retranslateUi(self, **kwargs):
        _translate = QtCore.QCoreApplication.translate
        self.setWindowTitle(_translate(self.objectName(),global_setting.get_setting("configer")["window"]["title"]))
    pass
    def load_modules(self):
        #动态加载模块
        modules = []
        module_dir = 'Module'  # 插件目录
        # 递归遍历指定目录
        for dirpath, dirnames, filenames in os.walk(module_dir):
            for filename in filenames:
                if filename.endswith('.py'):
                    module_name = filename[:-3]# 去掉 .py 后缀
                    if module_name.startswith("main"):
                        file_path = os.path.join(dirpath, filename)
                        # 动态加载模块
                        spec = importlib.util.spec_from_file_location(module_name, file_path)
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)#装载module
                        # 查找到实现 BasePlugin 的类
                        for name, obj in module.__dict__.items():
                            if name =="BaseModule":
                                # 抽象类跳过
                                continue
                            if isinstance(obj, type) and issubclass(obj, BaseModule):
                                modules.append(obj())
        return modules
        pass
    def exchange_widget_and_window(self):
        """widget和window相互转换"""
        # 将module的显示方式改变
        for module in self.modules:
            if module.interface_widget.type == BaseInterfaceType.WIDGET or module.interface_widget.type == BaseInterfaceType.FRAME:
                module.interface_widget.type=BaseInterfaceType.WINDOW

            else:
                module.interface_widget.type=BaseInterfaceType.WIDGET
        new_open_windows = []
        new_active_module_widgets=[]
        # 将正在显示的方式进行改变
        if self.open_windows is not None and len(self.open_windows)!=0:
            #窗口-》frame
            # 将正在显示的方式进行改变
            index = 0
            last_module=None
            while index<len(self.open_windows) or len(self.open_windows)==1:
                if index>=len(self.open_windows):
                    index=0
                module = self.open_windows[index]
                if last_module is module:
                    break
                last_module = module
                module.close()
                if module not in self.active_module_widgets:
                    new_active_module_widgets.append(module)
                index+=1
        if self.active_module_widgets is not None and len(self.active_module_widgets)!=0:
            # 从初始布局中移除 label
            # frame-》窗口
            index = 0
            last_module = None
            while index<len(self.active_module_widgets) or len(self.active_module_widgets)==1:
                if index>=len(self.active_module_widgets):
                    index=0
                module = self.active_module_widgets[index]
                if last_module is module:
                    break
                last_module = module
                module.setParent(None)
                module.hide()
                if module not in self.open_windows:
                    new_open_windows.append(module)
                index+=1
        # 删除所有标签页和widgets
        while self.tab_widget.count() > 0:  # 直到没有标签页
            self.tab_widget.removeTab(0)  # 删除第一个标签页
        self.open_windows.extend(new_open_windows)
        self.active_module_widgets.extend(new_active_module_widgets)
        for module in self.open_windows:
            module.adjustGUIPolicy()
            module.interface_widget.setMinimumSize(0,0)
            module.interface_widget.show()
        for module in self.active_module_widgets:
            module.adjustGUIPolicy()
            module.interface_widget.setMinimumSize()
            module.interface_widget.show()
    # 切换白天黑夜主题功能
    def toggle_theme(self):
        # 根据当前主题变换主题
        new_theme = "dark" if global_setting.get_setting("theme_manager").current_theme == "light" else "light"
        # 将新主题关键字赋值回去
        global_setting.set_setting('style', new_theme)
        global_setting.get_setting("theme_manager").current_theme = new_theme
        # 更改样式
        self.setStyleSheet(global_setting.get_setting("theme_manager").get_style_sheet())
        pass







    def close_tab(self, index):
        """关闭标签页"""
        self.tab_widget.widget(index).hide()
        self.tab_widget.removeTab(index)
    def change_enable_component_app_state(self):
        # 更新程序状态值
        if self.status_bar is not None:
            self.status_bar.update_app_state()
        #根据程序状态来改变是否可以点击的组件'
        #设置是否可以点击 menu_bar
        for menu_bar_action in self.menu_bar_actions:
            if menu_bar_action["app_state"] > global_setting.get_setting("app_state",AppState.INITIALIZED):
                menu_bar_action["action"].setEnabled(False)
            else:
                menu_bar_action["action"].setEnabled(True)
                #特殊情况

        # 设置是否可以点击 tool_bar
        for tool_bar_action in self.tool_bar_actions:
            if tool_bar_action["app_state"] > global_setting.get_setting("app_state",AppState.INITIALIZED):
                tool_bar_action["action"].setEnabled(False)
            else:
                tool_bar_action["action"].setEnabled(True)
            # 特殊按钮需要特殊配置
            if tool_bar_action['obj_name'] in ["stop_experiment", "pause_experiment","toggle_mode","window_exchange"]:
                tool_bar_action["action"].setEnabled(False)
        pass


        pass
    def reset_guidance(self):
        """重置教程"""
        reply = QMessageBox.question(
            self,
            "确认重置",
            "这将重置所有页面的首次访问状态，下次进入各个页面时会再次显示引导教程。\n\n确定要继续吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # 重置程序首次运行状态
            self.tutorial.settings_manager.settings["first_run"] = True
            self.tutorial.settings_manager.settings["tutorial_completed"] = False

            # 获取所有以 "first_visit_" 开头的设置项并重置为 True
            keys_to_reset = []
            for key in self.tutorial.settings_manager.settings.keys():
                if key.startswith("first_visit_"):
                    keys_to_reset.append(key)

            # 重置所有页面的首次访问状态
            for key in keys_to_reset:
                self.tutorial.settings_manager.settings[key] = True

            # 也可以直接重置特定页面（如果已知页面名称）
            page_names = ["main_page", "project_page", "settings_page", "help_page"]  # 可根据实际页面名称调整
            for page_name in page_names:
                self.tutorial.settings_manager.settings[f"first_visit_{page_name}"] = True

            self.tutorial.settings_manager.save_settings()

            # 显示重置的页面信息
            reset_pages = [key.replace("first_visit_", "") for key in keys_to_reset]
            if reset_pages:
                pages_info = "、".join(reset_pages)
                message = f"所有状态已重置。\n\n已重置的页面: {pages_info}\n\n重新进入这些页面时将显示引导教程。"
            else:
                message = "首次运行状态已重置。\n重新启动程序或进入页面时将显示引导教程。"

            QMessageBox.information(
                self,
                "重置完成",
                message
            )

            self.status_bar.update_tip("✅ 所有页面的首次访问状态已重置")