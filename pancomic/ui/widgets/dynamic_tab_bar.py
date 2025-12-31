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
        self._current_theme = 'dark'  # 默认深色主题
        self._setup_ui()
    
    def _setup_ui(self):
        self.setWindowTitle("添加漫画源")
        self.setFixedSize(300, 400)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 标题
        self.title_label = QLabel("选择要添加的漫画源")
        self.title_label.setObjectName("titleLabel")
        layout.addWidget(self.title_label)
        
        # 漫画源列表
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("sourceList")
        
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
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        self.cancel_btn.setObjectName("cancelButton")
        
        self.add_btn = QPushButton("添加")
        self.add_btn.clicked.connect(self._on_add_clicked)
        self.add_btn.setObjectName("addButton")
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.add_btn)
        layout.addLayout(btn_layout)
        
        # 应用默认主题
        self.apply_theme('dark')
    
    def apply_theme(self, theme: str):
        """应用主题到对话框"""
        self._current_theme = theme
        
        if theme == 'light':
            # 浅色主题配色
            bg_primary = '#FFFFFF'
            bg_secondary = '#F5F5F5'
            text_primary = '#000000'
            text_secondary = '#333333'
            text_muted = '#666666'
            border_color = '#E0E0E0'
            accent_color = '#0078D4'
            item_hover = '#F0F0F0'
            item_selected = '#0078D4'
            disabled_text = '#999999'
            cancel_bg = '#E8E8E8'
            cancel_hover = '#D0D0D0'
        else:
            # 深色主题配色
            bg_primary = '#1e1e1e'
            bg_secondary = '#2b2b2b'
            text_primary = '#ffffff'
            text_secondary = '#cccccc'
            text_muted = '#888888'
            border_color = '#3a3a3a'
            accent_color = '#0078d4'
            item_hover = '#3a3a3a'
            item_selected = '#0078d4'
            disabled_text = '#666666'
            cancel_bg = '#3a3a3a'
            cancel_hover = '#4a4a4a'
        
        # 应用样式
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_primary};
                color: {text_primary};
            }}
            
            #titleLabel {{
                color: {text_primary};
                font-size: 16px;
                font-weight: bold;
            }}
            
            #sourceList {{
                background-color: {bg_secondary};
                border: 1px solid {border_color};
                border-radius: 8px;
                color: {text_primary};
            }}
            
            #sourceList::item {{
                padding: 12px;
                border-bottom: 1px solid {border_color};
                color: {text_primary};
            }}
            
            #sourceList::item:hover {{
                background-color: {item_hover};
            }}
            
            #sourceList::item:selected {{
                background-color: {item_selected};
                color: white;
            }}
            
            #sourceList::item:disabled {{
                color: {disabled_text};
                background-color: transparent;
            }}
            
            #cancelButton {{
                background-color: {cancel_bg};
                color: {text_primary};
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: bold;
            }}
            
            #cancelButton:hover {{
                background-color: {cancel_hover};
                border-color: {accent_color};
            }}
            
            #addButton {{
                background-color: {accent_color};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: bold;
            }}
            
            #addButton:hover {{
                background-color: #1084d8;
            }}
            
            #addButton:pressed {{
                background-color: #006cbd;
            }}
        """)
    
    def showEvent(self, event):
        """对话框显示时应用父窗口的主题"""
        super().showEvent(event)
        # 尝试从父窗口获取当前主题
        if self.parent() and hasattr(self.parent(), '_current_theme'):
            self.apply_theme(self.parent()._current_theme)
        elif self.parent() and hasattr(self.parent(), 'parent') and hasattr(self.parent().parent(), '_current_theme'):
            # 如果父窗口的父窗口有主题设置
            self.apply_theme(self.parent().parent()._current_theme)
    
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
            {"key": "download", "name": "漫画下载"},
            {"key": "settings", "name": "设置"}
        ]
        
        # 当前选中的标签 key
        self.current_tab: Optional[str] = None
        
        # 当前主题
        self._current_theme: str = 'dark'
        
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
        self.add_btn.setObjectName("add_button")  # 设置对象名称用于样式选择
        self.add_btn.clicked.connect(self._on_add_clicked)
        # 移除硬编码样式，使用apply_theme控制
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
        # 应用当前主题到对话框
        dialog.apply_theme(self._current_theme)
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
        
        # 根据当前主题设置菜单样式
        if self._current_theme == 'light':
            menu_bg = '#FFFFFF'
            menu_text = '#000000'
            menu_border = '#E0E0E0'
            menu_hover = '#F0F0F0'
            menu_selected = '#0078D4'
        else:
            menu_bg = '#2b2b2b'
            menu_text = '#ffffff'
            menu_border = '#3a3a3a'
            menu_hover = '#3a3a3a'
            menu_selected = '#0078d4'
        
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {menu_bg};
                color: {menu_text};
                border: 1px solid {menu_border};
                border-radius: 4px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 8px 24px;
                border-radius: 4px;
            }}
            QMenu::item:hover {{
                background-color: {menu_hover};
            }}
            QMenu::item:selected {{
                background-color: {menu_selected};
                color: white;
            }}
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
    
    def apply_theme(self, theme: str):
        """应用主题到标签栏组件"""
        self._current_theme = theme  # 保存当前主题
        
        if theme == 'light':
            # 浅色主题配色
            bg_primary = '#FFFFFF'
            bg_secondary = '#F5F5F5'
            text_primary = '#000000'
            text_secondary = '#666666'
            border_color = '#E0E0E0'
            accent_color = '#0078D4'
            button_bg = '#E8E8E8'      # 浅灰色按钮背景
            button_hover = '#D0D0D0'   # 悬停时更深的灰色
            button_active = '#0078D4'  # 选中时蓝色
            add_button_bg = '#E8E8E8'  # 添加按钮背景
            add_button_text = '#666666'  # 添加按钮文字颜色
            add_button_hover_bg = '#D0D0D0'
            add_button_hover_text = '#333333'
        else:
            # 深色主题配色
            bg_primary = '#1e1e1e'
            bg_secondary = '#2b2b2b'
            text_primary = '#ffffff'
            text_secondary = '#cccccc'
            border_color = '#3a3a3a'
            accent_color = '#0078d4'
            button_bg = '#2b2b2b'
            button_hover = '#3a3a3a'
            button_active = '#0078d4'
            add_button_bg = '#2b2b2b'
            add_button_text = '#888888'
            add_button_hover_bg = '#3a3a3a'
            add_button_hover_text = '#ffffff'
        
        # 应用标签栏样式
        self.setStyleSheet(f"""
            DynamicTabBar {{
                background-color: {bg_primary};
                border-bottom: 1px solid {border_color};
            }}
            
            QToolButton {{
                background-color: {button_bg};
                color: {text_primary};
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 14px;
                font-weight: bold;
                margin: 2px;
            }}
            
            QToolButton:hover {{
                background-color: {button_hover};
                border-color: {accent_color};
            }}
            
            QToolButton:checked {{
                background-color: {button_active};
                color: white;
                border-color: {button_active};
            }}
            
            QToolButton:pressed {{
                background-color: {accent_color};
                color: white;
            }}
            
            /* 添加按钮特殊样式 */
            QToolButton#add_button {{
                background-color: {add_button_bg};
                color: {add_button_text};
                border: 1px solid {border_color};
                border-radius: 4px;
                font-size: 18px;
                font-weight: bold;
                padding: 6px;
            }}
            
            QToolButton#add_button:hover {{
                background-color: {add_button_hover_bg};
                color: {add_button_hover_text};
                border-color: {accent_color};
            }}
            
            QToolButton#add_button:pressed {{
                background-color: {accent_color};
                color: white;
            }}
        """)
