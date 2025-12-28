"""
Dynamic Tab Bar Widget - 支持热插拔的标签栏组件

功能：
- 动态添加/删除漫画源标签
- 拖动排序
- 右键菜单
- 固定标签（资源库、下载管理、设置）
"""

from typing import Optional, List, Dict
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QTabBar, QToolButton, 
    QMenu, QDialog, QVBoxLayout, QListWidget, 
    QListWidgetItem, QPushButton, QLabel, QFrame
)
from PySide6.QtCore import Qt, Signal, QPoint, QMimeData
from PySide6.QtGui import QDrag, QMouseEvent, QAction


class SourceSelectorDialog(QDialog):
    """漫画源选择对话框"""
    
    source_selected = Signal(str)  # 选中的漫画源 key
    
    def __init__(self, available_sources: List[Dict], added_sources: List[str], parent=None):
        """
        Args:
            available_sources: 可用的漫画源列表 [{"key": "jmcomic", "name": "JMComic"}, ...]
            added_sources: 已添加的漫画源 key 列表
        """
        super().__init__(parent)
        self.available_sources = available_sources
        self.added_sources = added_sources
        self._setup_ui()
    
    def _setup_ui(self):
        self.setWindowTitle("添加漫画源")
        self.setFixedSize(300, 400)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 标题
        title = QLabel("选择要添加的漫画源")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)
        
        # 漫画源列表
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #2b2b2b;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
            }
            QListWidget::item {
                padding: 12px;
                border-bottom: 1px solid #3a3a3a;
            }
            QListWidget::item:hover {
                background-color: #3a3a3a;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
            }
        """)
        
        for source in self.available_sources:
            item = QListWidgetItem()
            key = source["key"]
            name = source["name"]
            
            if key in self.added_sources:
                item.setText(f"✓ {name}")
                item.setData(Qt.UserRole, key)
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)  # 禁用已添加的
            else:
                item.setText(name)
                item.setData(Qt.UserRole, key)
            
            self.list_widget.addItem(item)
        
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.list_widget)
        
        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
        """)
        
        add_btn = QPushButton("添加")
        add_btn.clicked.connect(self._on_add_clicked)
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background-color: #1084d8;
            }
        """)
        
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(add_btn)
        layout.addLayout(btn_layout)
        
        # 对话框样式
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: white;
            }
            QLabel {
                color: white;
            }
        """)
    
    def _on_item_double_clicked(self, item: QListWidgetItem):
        if item.flags() & Qt.ItemIsEnabled:
            key = item.data(Qt.UserRole)
            self.source_selected.emit(key)
            self.accept()
    
    def _on_add_clicked(self):
        current = self.list_widget.currentItem()
        if current and (current.flags() & Qt.ItemIsEnabled):
            key = current.data(Qt.UserRole)
            self.source_selected.emit(key)
            self.accept()


class DynamicTabBar(QWidget):
    """
    动态标签栏组件
    
    左侧：动态漫画源标签（可拖动、关闭）+ 添加按钮
    右侧：固定标签（资源库、下载管理、设置）
    """
    
    # 信号
    tab_selected = Signal(str)  # 标签被选中，参数为 tab_key
    tab_closed = Signal(str)  # 标签被关闭，参数为 tab_key
    tab_added = Signal(str)  # 标签被添加，参数为 source_key
    tabs_reordered = Signal(list)  # 标签顺序改变，参数为新的 key 列表
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 可用的漫画源配置
        self.available_sources: List[Dict] = []
        
        # 当前动态标签 [{"key": "jmcomic", "name": "JMComic"}, ...]
        self.dynamic_tabs: List[Dict] = []
        
        # 固定标签
        self.fixed_tabs = [
            {"key": "library", "name": "资源库"},
            {"key": "download", "name": "下载管理"},
            {"key": "settings", "name": "设置"}
        ]
        
        # 当前选中的标签 key
        self.current_tab: Optional[str] = None
        
        # UI 组件
        self._tab_buttons: Dict[str, QToolButton] = {}
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 动态标签区域
        self.dynamic_area = QWidget()
        self.dynamic_layout = QHBoxLayout(self.dynamic_area)
        self.dynamic_layout.setContentsMargins(0, 0, 0, 0)
        self.dynamic_layout.setSpacing(2)
        
        # 添加按钮
        self.add_btn = QToolButton()
        self.add_btn.setText("+")
        self.add_btn.setFixedSize(36, 36)
        self.add_btn.clicked.connect(self._on_add_clicked)
        self.add_btn.setStyleSheet("""
            QToolButton {
                background-color: #2b2b2b;
                color: #888;
                border: none;
                border-radius: 4px;
                font-size: 18px;
                font-weight: bold;
            }
            QToolButton:hover {
                background-color: #3a3a3a;
                color: white;
            }
        """)
        self.dynamic_layout.addWidget(self.add_btn)
        
        layout.addWidget(self.dynamic_area)
        
        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setStyleSheet("background-color: #3a3a3a;")
        separator.setFixedWidth(1)
        layout.addWidget(separator)
        
        # 固定标签区域
        self.fixed_area = QWidget()
        self.fixed_layout = QHBoxLayout(self.fixed_area)
        self.fixed_layout.setContentsMargins(8, 0, 0, 0)
        self.fixed_layout.setSpacing(2)
        
        # 创建固定标签
        for tab in self.fixed_tabs:
            btn = self._create_tab_button(tab["key"], tab["name"], closable=False)
            self.fixed_layout.addWidget(btn)
            self._tab_buttons[tab["key"]] = btn
        
        layout.addWidget(self.fixed_area)
        layout.addStretch()
        
        # 整体样式
        self.setStyleSheet("""
            DynamicTabBar {
                background-color: #1e1e1e;
                border-bottom: 1px solid #3a3a3a;
            }
        """)
        self.setFixedHeight(44)
    
    def _create_tab_button(self, key: str, name: str, closable: bool = True) -> QToolButton:
        """创建标签按钮"""
        btn = QToolButton()
        btn.setText(name)
        btn.setCheckable(True)
        btn.setProperty("tab_key", key)
        btn.setProperty("closable", closable)
        btn.clicked.connect(lambda: self._on_tab_clicked(key))
        btn.setContextMenuPolicy(Qt.CustomContextMenu)
        btn.customContextMenuRequested.connect(lambda pos: self._show_context_menu(key, pos))
        
        # 样式
        base_style = """
            QToolButton {
                background-color: #2b2b2b;
                color: white;
                border: none;
                padding: 10px 20px;
                font-size: 14px;
            }
            QToolButton:hover {
                background-color: #3a3a3a;
            }
            QToolButton:checked {
                background-color: #0078d4;
            }
        """
        btn.setStyleSheet(base_style)
        
        return btn
    
    def set_available_sources(self, sources: List[Dict]):
        """设置可用的漫画源列表"""
        self.available_sources = sources
    
    def add_dynamic_tab(self, key: str, name: str, select: bool = True):
        """添加动态标签"""
        if any(t["key"] == key for t in self.dynamic_tabs):
            # 已存在，直接选中
            if select:
                self.select_tab(key)
            return
        
        # 创建按钮
        btn = self._create_tab_button(key, name, closable=True)
        
        # 插入到添加按钮之前
        insert_index = self.dynamic_layout.count() - 1  # 添加按钮之前
        self.dynamic_layout.insertWidget(insert_index, btn)
        
        self._tab_buttons[key] = btn
        self.dynamic_tabs.append({"key": key, "name": name})
        
        if select:
            self.select_tab(key)
        
        self.tab_added.emit(key)
    
    def remove_dynamic_tab(self, key: str):
        """移除动态标签"""
        if key not in self._tab_buttons:
            return
        
        btn = self._tab_buttons.pop(key)
        self.dynamic_layout.removeWidget(btn)
        btn.deleteLater()
        
        self.dynamic_tabs = [t for t in self.dynamic_tabs if t["key"] != key]
        
        # 如果关闭的是当前标签，切换到其他标签
        if self.current_tab == key:
            if self.dynamic_tabs:
                self.select_tab(self.dynamic_tabs[-1]["key"])
            else:
                self.select_tab("library")
        
        self.tab_closed.emit(key)
    
    def select_tab(self, key: str):
        """选中标签"""
        if key == self.current_tab:
            return
        
        # 取消之前的选中状态
        if self.current_tab and self.current_tab in self._tab_buttons:
            self._tab_buttons[self.current_tab].setChecked(False)
        
        # 设置新的选中状态
        if key in self._tab_buttons:
            self._tab_buttons[key].setChecked(True)
            self.current_tab = key
            self.tab_selected.emit(key)
    
    def get_dynamic_tab_keys(self) -> List[str]:
        """获取当前动态标签的 key 列表"""
        return [t["key"] for t in self.dynamic_tabs]
    
    def _on_tab_clicked(self, key: str):
        self.select_tab(key)
    
    def _on_add_clicked(self):
        """点击添加按钮"""
        added_keys = [t["key"] for t in self.dynamic_tabs]
        dialog = SourceSelectorDialog(self.available_sources, added_keys, self)
        dialog.source_selected.connect(self._on_source_selected)
        dialog.exec()
    
    def _on_source_selected(self, key: str):
        """选择了漫画源"""
        # 查找漫画源名称
        for source in self.available_sources:
            if source["key"] == key:
                self.add_dynamic_tab(key, source["name"])
                break
    
    def _show_context_menu(self, key: str, pos: QPoint):
        """显示右键菜单"""
        btn = self._tab_buttons.get(key)
        if not btn:
            return
        
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2b2b2b;
                color: white;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 24px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #0078d4;
            }
        """)
        
        closable = btn.property("closable")
        
        if closable:
            close_action = menu.addAction("关闭此标签")
            close_action.triggered.connect(lambda: self.remove_dynamic_tab(key))
            
            if len(self.dynamic_tabs) > 1:
                close_others = menu.addAction("关闭其他标签")
                close_others.triggered.connect(lambda: self._close_other_tabs(key))
            
            menu.addSeparator()
            
            # 移动选项
            idx = next((i for i, t in enumerate(self.dynamic_tabs) if t["key"] == key), -1)
            if idx > 0:
                move_left = menu.addAction("移到最左")
                move_left.triggered.connect(lambda: self._move_tab_to(key, 0))
            if idx < len(self.dynamic_tabs) - 1:
                move_right = menu.addAction("移到最右")
                move_right.triggered.connect(lambda: self._move_tab_to(key, len(self.dynamic_tabs) - 1))
        
        menu.exec(btn.mapToGlobal(pos))
    
    def _close_other_tabs(self, keep_key: str):
        """关闭其他标签"""
        keys_to_remove = [t["key"] for t in self.dynamic_tabs if t["key"] != keep_key]
        for key in keys_to_remove:
            self.remove_dynamic_tab(key)
    
    def _move_tab_to(self, key: str, target_index: int):
        """移动标签到指定位置"""
        # 找到当前位置
        current_idx = next((i for i, t in enumerate(self.dynamic_tabs) if t["key"] == key), -1)
        if current_idx == -1 or current_idx == target_index:
            return
        
        # 移动数据
        tab_data = self.dynamic_tabs.pop(current_idx)
        self.dynamic_tabs.insert(target_index, tab_data)
        
        # 重新排列 UI
        btn = self._tab_buttons[key]
        self.dynamic_layout.removeWidget(btn)
        self.dynamic_layout.insertWidget(target_index, btn)
        
        self.tabs_reordered.emit([t["key"] for t in self.dynamic_tabs])
