import time
from datetime import datetime

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QStatusBar, QLabel, QProgressBar, QPushButton

from public.component.list_view.Custom_List_view import CustomListView
from public.config_class.global_setting import global_setting
from public.entity.MyQThread import MyQThread
from public.entity.enum.Public_Enum import AppState
from public.util.time_util import time_util


class Time_thread(MyQThread):


    def __init__(self, update_time_main_signal):
        super(Time_thread, self).__init__(name="time_thread")
        # 获取主线程更新界面信号
        self.update_time_main_signal: pyqtSignal = update_time_main_signal
        pass

    def dosomething(self):
        # 不断获取系统时间

        # 实时获取当前时间（精确到微秒）
        current_time = datetime.now()

        # 转换为目标格式
        formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
        # 将时间发送信号到绑定槽函数
        self.update_time_main_signal.emit(formatted_time)
        time.sleep(1)
        # print(formatted_time)
        pass

    pass


class CustomStatusBar(QStatusBar):
    # update_time的更新界面的主信号
    update_time_main_signal_gui_update = pyqtSignal(str)

    def __init__(self,main_gui,is_main=True):
        super().__init__()
        self.main_gui = main_gui
        if is_main:
            #添加时间label
            self.time_label = QLabel()
            self.time_label.setObjectName("time_label")
            self.addWidget(self.time_label)

            #程序状态
            self.app_status_label = QLabel("INITIALIZED")
            self.app_status_label.setObjectName("app_status_label")
            self.addWidget(self.app_status_label)

        # 添加 tip
        self.tip_label =None
        # self.addWidget(self.tip_label)
        if is_main:

            # 添加连接服务器地址显示
            self.server_label = QLabel("当前未连接服务器")
            self.addWidget(self.server_label)

            # 添加 QProgressBar
            self.progress_bar = QProgressBar()
            self.progress_bar.setMaximum(100)
            self.progress_bar.setValue(0)
            # self.addWidget(self.progress_bar)  # 将进度条添加为永久小部件

        self.tip_btn = QPushButton("教程帮助")
        self.tip_btn.setStyleSheet("QPushButton { font-weight:bolder; font-size: 15px;padding: 5px; }")
        self.tip_btn.clicked.connect(self.main_gui.restart_tutorial)

        self.addPermanentWidget(self.tip_btn)
        if is_main:
            # 将更新时间信号绑定更新时间label界面函数
            self.update_time_main_signal_gui_update.connect(self.update_time_function_start_gui_update)
            # 启动子线程
            self.time_thread = Time_thread(update_time_main_signal=self.update_time_main_signal_gui_update)
            self.time_thread.start()


    def update_tip(self, message):
        if self.tip_label is None:
            self.tip_label = CustomListView()
            self.addWidget(self.tip_label)
        self.tip_label.insert_data(message)
    def update_server_label(self,message):
        self.server_label.setText(message)
    def set_progress(self, value):
        self.progress_bar.setValue(value)
    def update_app_state(self):
        app_state = global_setting.get_setting("app_state",AppState.INITIALIZED)
        self.app_status_label.setText(app_state.value.get("text"))




    def update_time_function_start_gui_update(self, timeStr=""):
        #  获取控件
        # time_label: QLabel = self.findChild(QLabel, "time_label")
        # 设置文本
        self.time_label.setText(timeStr)
        pass