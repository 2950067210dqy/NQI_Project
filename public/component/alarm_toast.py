from PyQt6.QtCore import QPoint, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from public.util.alarm_message_formatter import format_alarm_message


class AlarmToast(QFrame):
    """黄色常驻预警提示卡片，用户点击关闭按钮后才消失。"""

    close_requested = pyqtSignal(object)
    clicked = pyqtSignal(dict)

    def __init__(self, message: str, payload: dict = None, parent: QWidget = None):
        # Toast 必须是独立的置顶工具窗；作为主窗口子控件时会被模块顶层窗口遮挡。
        super().__init__(None)
        self.owner_window = parent
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.payload = payload or {}
        self.raw_message = format_alarm_message(message or "收到新的报警预警")
        self.setObjectName("alarmToast")
        self.setMinimumWidth(220)
        self.setMaximumWidth(360)
        self.setFixedWidth(360)
        self.setMinimumHeight(92)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QFrame#alarmToast {
                background: #fff7cc;
                border: 1px solid #f59e0b;
                border-left: 6px solid #d97706;
                border-radius: 8px;
            }
            QLabel#alarmToastTitle {
                color: #7c2d12;
                font-size: 14px;
                font-weight: bold;
                background: transparent;
            }
            QLabel#alarmToastMessage {
                color: #4b2500;
                font-size: 12px;
                background: transparent;
            }
            QPushButton#alarmToastClose {
                border: none;
                color: #92400e;
                background: transparent;
                font-size: 16px;
                font-weight: bold;
                padding: 0 6px;
            }
            QPushButton#alarmToastClose:hover {
                color: #451a03;
                background: rgba(245, 158, 11, 45);
                border-radius: 4px;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 10, 10)
        root.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        title = QLabel("报警预警")
        title.setObjectName("alarmToastTitle")
        close_btn = QPushButton("×")
        close_btn.setObjectName("alarmToastClose")
        close_btn.setFixedSize(24, 24)
        close_btn.clicked.connect(lambda: self.close_requested.emit(self))
        header.addWidget(title)
        header.addStretch()
        header.addWidget(close_btn)

        self.body_label = QLabel(self._wrap_message(self.raw_message))
        self.body_label.setObjectName("alarmToastMessage")
        self.body_label.setWordWrap(True)
        self.body_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

        root.addLayout(header)
        root.addWidget(self.body_label)

    def fit_width(self, width: int):
        """根据主窗口可见区域收缩 toast，避免右侧溢出屏幕。"""
        width = max(220, min(360, int(width)))
        self.setFixedWidth(width)
        self.body_label.setMaximumWidth(max(180, width - 34))
        wrap_limit = max(18, min(34, (width - 34) // 8))
        self.body_label.setText(self._wrap_message(self.raw_message, wrap_limit))

    @staticmethod
    def _wrap_message(message: str, limit: int = 34) -> str:
        """长文件名和指标串不一定会自然换行，这里主动加换行点。"""
        text = str(message or "")
        lines = []
        current = []
        current_len = 0
        break_chars = set(" _-/\\:;,.，。；、()[]{}=<>")
        for char in text:
            if char in "\r\n":
                if current:
                    lines.append("".join(current))
                    current = []
                    current_len = 0
                continue
            current.append(char)
            current_len += 1
            if current_len >= limit or (current_len >= 22 and char in break_chars):
                lines.append("".join(current).strip())
                current = []
                current_len = 0
        if current:
            lines.append("".join(current).strip())
        return "\n".join(line for line in lines if line)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.payload)
        super().mousePressEvent(event)


class AlarmToastManager:
    """管理主窗口右上角最多 3 条常驻预警 toast。"""

    def __init__(self, parent: QWidget, max_visible: int = 3):
        self.parent = parent
        self.max_visible = max_visible
        self.toasts = []

    def show_alarm(self, message: str, payload: dict = None):
        toast = AlarmToast(message, payload, self.parent)
        toast.close_requested.connect(self.remove_toast)
        toast.clicked.connect(self._open_alarm_page)
        self.toasts.insert(0, toast)
        while len(self.toasts) > self.max_visible:
            self.remove_toast(self.toasts[-1])
        self.reposition()
        toast.show()
        toast.raise_()
        return toast

    def remove_toast(self, toast):
        if toast in self.toasts:
            self.toasts.remove(toast)
        toast.hide()
        toast.deleteLater()
        self.reposition()

    def clear(self):
        for toast in list(self.toasts):
            self.remove_toast(toast)

    def reposition(self):
        if self.parent is None:
            return
        margin = 18
        spacing = 10
        y = margin
        parent_rect = QRect(self.parent.mapToGlobal(QPoint(0, 0)), self.parent.size())
        screen = self.parent.screen() or QGuiApplication.primaryScreen()
        available_rect = screen.availableGeometry() if screen is not None else parent_rect
        visible_rect = parent_rect.intersected(available_rect)
        if visible_rect.isEmpty():
            visible_rect = parent_rect

        # 使用主窗口和屏幕的交集计算宽度，主窗口贴屏幕边缘时也不会向右溢出。
        max_toast_width = max(220, min(360, visible_rect.width() - margin * 2))
        for toast in self.toasts:
            toast.fit_width(max_toast_width)
            toast.adjustSize()
            desired_global_x = min(
                parent_rect.right() - toast.width() - margin,
                available_rect.right() - toast.width() - margin,
            )
            desired_global_x = max(visible_rect.left() + margin, desired_global_x)
            desired_global_y = max(visible_rect.top() + margin, parent_rect.top() + y)
            # 独立工具窗使用屏幕全局坐标，避免受到任一模块窗口坐标系影响。
            toast.move(desired_global_x, desired_global_y)
            toast.raise_()
            y += toast.height() + spacing

    def _open_alarm_page(self, payload: dict):
        # 性能测试预警没有正式文件或历史记录，点击时不打开业务报警页面。
        if (payload or {}).get("is_latency_test"):
            return
        if hasattr(self.parent, 'open_fault_alarm_page'):
            self.parent.open_fault_alarm_page()
