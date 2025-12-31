"""
PanComic 通知系统演示
实现非侵入式弹窗通知以及弹入，弹出，掉落，落地抖动等动画，绑定在主窗口右下角，位置置顶
"""

import sys
from typing import Optional, List
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QFrame, QGraphicsDropShadowEffect,
    QMainWindow, QTextEdit
)
from PySide6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, 
    QRect, QPoint, Signal, QObject
)
from PySide6.QtGui import QFont, QIcon, QPalette, QColor, QPixmap, QPainter


class NotificationWidget(QFrame):
    """单个通知弹窗组件"""
    
    # 信号
    closed = Signal(object)  # 通知关闭时发出信号
    
    def __init__(self, title: str, message: str, notification_type: str = "info", duration: int = 4000):
        super().__init__()
        
        self.notification_type = notification_type
        self.duration = duration
        
        # 设置窗口属性
        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint | 
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(380, 85)
        
        # 设置样式
        self._setup_style()
        
        # 创建UI
        self._setup_ui(title, message)
        
        # 设置阴影效果
        self._setup_shadow()
        
        # 设置动画
        self._setup_animations()
        
        # 设置自动关闭定时器
        if duration > 0:
            QTimer.singleShot(duration, self.close_notification)
    
    def _setup_style(self):
        """设置样式"""
        # 根据通知类型设置不同颜色
        colors = {
            "info": {"bg": "#2d3748", "border": "#4299e1", "icon": "ℹ️"},
            "success": {"bg": "#1a202c", "border": "#48bb78", "icon": "✅"},
            "warning": {"bg": "#2d2016", "border": "#ed8936", "icon": "⚠️"},
            "error": {"bg": "#2d1b1b", "border": "#f56565", "icon": "❌"},
            "download": {"bg": "#1a202c", "border": "#38b2ac", "icon": "⬇️"}
        }
        
        color_scheme = colors.get(self.notification_type, colors["info"])
        
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {color_scheme["bg"]};
                border: 4px solid {color_scheme["border"]};
                border-radius: 12px;
                padding: 6px;
            }}
            QLabel {{
                color: white;
                background: transparent;
                border: none;
                font-family: 'Microsoft YaHei', 'SimHei', sans-serif;
                margin: 0px;
                padding: 0px;
            }}
            QPushButton {{
                background: transparent;
                border: 2px solid transparent;
                color: #a0aec0;
                font-size: 18px;
                font-weight: bold;
                padding: 2px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                color: white;
                background-color: rgba(255, 255, 255, 0.2);
                border: 2px solid rgba(255, 255, 255, 0.3);
            }}
        """)
        
        self.icon_text = color_scheme["icon"]
    
    def _setup_ui(self, title: str, message: str):
        """创建UI组件"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 10, 8)
        layout.setSpacing(10)
        
        # 图标
        icon_label = QLabel(self.icon_text)
        icon_label.setFont(QFont("Segoe UI Emoji", 16))
        icon_label.setFixedSize(24, 24)
        icon_label.setAlignment(Qt.AlignCenter)
        
        # 文本区域
        text_layout = QVBoxLayout()
        text_layout.setSpacing(0)  # 完全去掉行距
        text_layout.setContentsMargins(0, 0, 0, 0)
        
        # 标题
        title_label = QLabel(title)
        title_font = QFont("Microsoft YaHei", 10)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setFixedHeight(18)  # 固定标题高度
        title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        # 消息
        message_label = QLabel(message)
        message_font = QFont("Microsoft YaHei", 9)
        message_label.setFont(message_font)
        message_label.setWordWrap(True)
        message_label.setStyleSheet("color: #e2e8f0; margin-top: 2px;")
        message_label.setFixedHeight(35)  # 固定消息高度
        message_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        
        text_layout.addWidget(title_label)
        text_layout.addWidget(message_label)
        text_layout.addStretch()
        
        # 关闭按钮
        close_btn = QPushButton("×")
        close_btn.setFixedSize(22, 22)
        close_btn.clicked.connect(self.close_notification)
        
        # 添加到主布局
        layout.addWidget(icon_label, 0, Qt.AlignTop)
        layout.addLayout(text_layout, 1)
        layout.addWidget(close_btn, 0, Qt.AlignTop)
    
    def _setup_shadow(self):
        """设置阴影效果"""
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 6)
        self.setGraphicsEffect(shadow)
    
    def _setup_animations(self):
        """设置动画"""
        # 滑入动画
        self.slide_in_animation = QPropertyAnimation(self, b"geometry")
        self.slide_in_animation.setDuration(300)
        self.slide_in_animation.setEasingCurve(QEasingCurve.OutCubic)
        
        # 滑出动画
        self.slide_out_animation = QPropertyAnimation(self, b"geometry")
        self.slide_out_animation.setDuration(250)
        self.slide_out_animation.setEasingCurve(QEasingCurve.InCubic)
        self.slide_out_animation.finished.connect(self.hide)
        self.slide_out_animation.finished.connect(lambda: self.closed.emit(self))
    
    def show_notification(self, target_pos: QPoint):
        """显示通知（带滑入动画）"""
        # 起始位置（从右侧滑入）
        start_pos = QPoint(target_pos.x() + 450, target_pos.y())
        start_rect = QRect(start_pos, self.size())
        
        # 目标位置
        target_rect = QRect(target_pos, self.size())
        
        # 设置起始位置并显示
        self.setGeometry(start_rect)
        self.show()
        
        # 开始滑入动画
        self.slide_in_animation.setStartValue(start_rect)
        self.slide_in_animation.setEndValue(target_rect)
        self.slide_in_animation.start()
    
    def close_notification(self):
        """关闭通知（带滑出动画）"""
        if self.slide_out_animation.state() == QPropertyAnimation.Running:
            return
        
        # 滑出到右侧
        current_rect = self.geometry()
        end_rect = QRect(
            current_rect.x() + 450, 
            current_rect.y(), 
            current_rect.width(), 
            current_rect.height()
        )
        
        self.slide_out_animation.setStartValue(current_rect)
        self.slide_out_animation.setEndValue(end_rect)
        self.slide_out_animation.start()


class NotificationManager(QObject):
    """通知管理器"""
    
    def __init__(self, parent_window: QWidget):
        super().__init__()
        self.parent_window = parent_window
        self.notifications: List[NotificationWidget] = []
        self.spacing = 10  # 通知之间的间距
    
    def show_notification(self, title: str, message: str, notification_type: str = "info", duration: int = 4000):
        """显示新通知"""
        # 创建通知
        notification = NotificationWidget(title, message, notification_type, duration)
        notification.closed.connect(self._on_notification_closed)
        
        # 计算位置
        pos = self._calculate_position()
        
        # 添加到列表
        self.notifications.append(notification)
        
        # 显示通知
        notification.show_notification(pos)
    
    def _calculate_position(self) -> QPoint:
        """计算新通知的位置"""
        # 获取父窗口的全局位置和大小
        parent_global_rect = self.parent_window.geometry()
        
        # 基础位置（相对于父窗口的右下角）
        base_x = parent_global_rect.right() - 400  # 通知宽度 + 边距
        base_y = parent_global_rect.bottom() - 120  # 底部边距
        
        # 根据现有通知数量调整Y位置（向上堆叠）
        offset_y = len(self.notifications) * (85 + self.spacing)  # 通知高度 + 间距
        
        return QPoint(base_x, base_y - offset_y)
    
    def _on_notification_closed(self, notification: NotificationWidget):
        """处理通知关闭"""
        if notification in self.notifications:
            self.notifications.remove(notification)
            notification.deleteLater()
            
            # 重新排列剩余通知
            self._rearrange_notifications()
    
    def _rearrange_notifications(self):
        """重新排列通知位置 - 添加下落动画"""
        parent_global_rect = self.parent_window.geometry()
        base_x = parent_global_rect.right() - 400
        base_y = parent_global_rect.bottom() - 120
        
        # 为每个通知创建下落动画
        for i, notification in enumerate(self.notifications):
            # 计算新位置
            offset_y = i * (85 + self.spacing)
            new_pos = QPoint(base_x, base_y - offset_y)
            new_rect = QRect(new_pos, notification.size())
            
            # 创建下落动画
            move_animation = QPropertyAnimation(notification, b"geometry")
            move_animation.setDuration(400)  # 稍微长一点的动画时间
            move_animation.setEasingCurve(QEasingCurve.OutBounce)  # 弹跳效果
            move_animation.setStartValue(notification.geometry())
            move_animation.setEndValue(new_rect)
            move_animation.start()
            
            # 保存动画引用，防止被垃圾回收
            notification._move_animation = move_animation
    
    def clear_all(self):
        """清除所有通知"""
        for notification in self.notifications[:]:
            notification.close_notification()


class MainWindow(QMainWindow):
    """主窗口演示"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PanComic 通知系统演示")
        self.setGeometry(100, 100, 800, 600)
        
        # 创建通知管理器
        self.notification_manager = NotificationManager(self)
        
        # 设置UI
        self._setup_ui()
        
        # 监听窗口移动和大小变化
        self.installEventFilter(self)
        
        # 设置样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a202c;
            }
            QPushButton {
                background-color: #4299e1;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-size: 13px;
                font-weight: bold;
                font-family: 'Microsoft YaHei', sans-serif;
            }
            QPushButton:hover {
                background-color: #3182ce;
            }
            QPushButton:pressed {
                background-color: #2c5282;
            }
            QTextEdit {
                background-color: #2d3748;
                color: white;
                border: 2px solid #4a5568;
                border-radius: 8px;
                padding: 12px;
                font-family: 'Microsoft YaHei', 'Consolas', monospace;
                font-size: 12px;
            }
            QLabel {
                color: white;
                font-size: 14px;
                font-family: 'Microsoft YaHei', sans-serif;
            }
        """)
    
    def _setup_ui(self):
        """设置UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)
        
        # 标题
        title_label = QLabel("PanComic 通知系统演示")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        
        # 说明文本
        info_text = QTextEdit()
        info_text.setMaximumHeight(120)
        info_text.setPlainText(
            "点击下面的按钮测试不同类型的通知弹窗：\n"
            "• 通知会从右侧滑入\n"
            "• 多个通知会自动堆叠\n"
            "• 4秒后自动消失，或点击×手动关闭\n"
            "• 关闭时其他通知会自动重新排列"
        )
        info_text.setReadOnly(True)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        
        # 各种类型的通知按钮
        buttons = [
            ("📥 添加到下载队列", "success", "下载任务", "《进击的巨人》已添加到下载队列"),
            ("⬇️ 开始下载", "download", "下载开始", "正在下载《进击的巨人》第1话"),
            ("✅ 下载完成", "success", "下载完成", "《进击的巨人》第1话下载完成"),
            ("⚠️ 网络错误", "warning", "连接警告", "网络连接不稳定，正在重试..."),
            ("❌ 下载失败", "error", "下载失败", "《进击的巨人》下载失败：网络超时"),
            ("ℹ️ 系统信息", "info", "系统提示", "PanComic 已更新到最新版本")
        ]
        
        for btn_text, notif_type, title, message in buttons:
            btn = QPushButton(btn_text)
            btn.clicked.connect(lambda checked, t=notif_type, ti=title, m=message: 
                              self.notification_manager.show_notification(ti, m, t))
            button_layout.addWidget(btn)
        
        # 清除按钮
        clear_btn = QPushButton("🗑️ 清除所有通知")
        clear_btn.clicked.connect(self.notification_manager.clear_all)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #e53e3e;
            }
            QPushButton:hover {
                background-color: #c53030;
            }
        """)
        
        # 添加到布局
        layout.addWidget(title_label)
        layout.addWidget(info_text)
        layout.addLayout(button_layout)
        layout.addWidget(clear_btn)
        layout.addStretch()
    
    def eventFilter(self, obj, event):
        """处理窗口事件，让通知跟随窗口移动"""
        if obj == self and event.type() in [event.Type.Move, event.Type.Resize]:
            # 窗口移动或大小改变时，重新排列通知
            if hasattr(self, 'notification_manager'):
                QTimer.singleShot(50, self.notification_manager._rearrange_notifications)
        return super().eventFilter(obj, event)


def main():
    app = QApplication(sys.argv)
    
    # 设置应用样式
    app.setStyle('Fusion')
    
    window = MainWindow()
    window.show()
    
    # 显示欢迎通知
    QTimer.singleShot(1000, lambda: window.notification_manager.show_notification(
        "欢迎使用", "PanComic 通知系统演示已启动", "info", 3000
    ))
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()