"""
Source Tab Manager - 漫画源标签管理器

负责：
- 漫画源页面的懒加载
- 标签状态持久化
- 漫画源注册和管理
"""

import json
from typing import Optional, Dict, List, Callable, Any
from pathlib import Path
from PySide6.QtWidgets import QWidget, QStackedWidget
from PySide6.QtCore import QObject, Signal


class SourceTabManager(QObject):
    """漫画源标签管理器"""
    
    # 信号
    page_created = Signal(str, object)  # 页面创建完成 (key, page)
    
    def __init__(self, config_path: str = None, parent=None):
        super().__init__(parent)
        
        # 配置文件路径
        if config_path:
            self.config_path = Path(config_path)
        else:
            self.config_path = Path(__file__).parent.parent.parent.parent / "downloads" / "tabs_config.json"
        
        # 注册的漫画源 {key: {"name": str, "factory": Callable}}
        self._registered_sources: Dict[str, Dict] = {}
        
        # 已创建的页面实例 {key: QWidget}
        self._pages: Dict[str, QWidget] = {}
        
        # 固定页面 {key: QWidget}
        self._fixed_pages: Dict[str, QWidget] = {}
        
        # 页面容器
        self.stacked_widget: Optional[QStackedWidget] = None
        
        # 当前活动的标签 key
        self.current_key: Optional[str] = None
    
    def set_stacked_widget(self, stacked: QStackedWidget):
        """设置页面容器"""
        self.stacked_widget = stacked
    
    def register_source(self, key: str, name: str, factory: Callable[[], QWidget]):
        """
        注册漫画源
        
        Args:
            key: 唯一标识符
            name: 显示名称
            factory: 页面工厂函数，返回 QWidget
        """
        self._registered_sources[key] = {
            "name": name,
            "factory": factory
        }
    
    def register_fixed_page(self, key: str, name: str, page: QWidget):
        """
        注册固定页面（资源库、下载管理、设置）
        
        Args:
            key: 唯一标识符
            name: 显示名称
            page: 页面实例
        """
        self._fixed_pages[key] = page
        if self.stacked_widget:
            self.stacked_widget.addWidget(page)
    
    def get_available_sources(self) -> List[Dict]:
        """获取所有可用的漫画源"""
        return [
            {"key": key, "name": info["name"]}
            for key, info in self._registered_sources.items()
        ]
    
    def get_page(self, key: str) -> Optional[QWidget]:
        """
        获取页面实例（懒加载）
        
        如果页面未创建，会调用工厂函数创建
        """
        # 检查固定页面
        if key in self._fixed_pages:
            return self._fixed_pages[key]
        
        # 检查已创建的动态页面
        if key in self._pages:
            return self._pages[key]
        
        # 懒加载：创建新页面
        if key in self._registered_sources:
            factory = self._registered_sources[key]["factory"]
            try:
                page = factory()
                self._pages[key] = page
                
                if self.stacked_widget:
                    self.stacked_widget.addWidget(page)
                
                self.page_created.emit(key, page)
                print(f"✅ 懒加载创建页面: {key}")
                return page
            except Exception as e:
                print(f"❌ 创建页面失败 {key}: {e}")
                return None
        
        return None
    
    def switch_to(self, key: str) -> bool:
        """
        切换到指定页面
        
        Returns:
            是否切换成功
        """
        page = self.get_page(key)
        if page and self.stacked_widget:
            self.stacked_widget.setCurrentWidget(page)
            self.current_key = key
            return True
        return False
    
    def remove_page(self, key: str):
        """移除动态页面"""
        if key in self._pages:
            page = self._pages.pop(key)
            if self.stacked_widget:
                self.stacked_widget.removeWidget(page)
            page.deleteLater()
            print(f"🗑️ 移除页面: {key}")
    
    def is_page_created(self, key: str) -> bool:
        """检查页面是否已创建"""
        return key in self._pages or key in self._fixed_pages
    
    def save_tabs_config(self, dynamic_tabs: List[str]):
        """
        保存标签配置
        
        Args:
            dynamic_tabs: 动态标签 key 列表（按顺序）
        """
        config = {
            "dynamic_tabs": dynamic_tabs,
            "version": 1
        }
        
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            print(f"💾 保存标签配置: {dynamic_tabs}")
        except Exception as e:
            print(f"❌ 保存标签配置失败: {e}")
    
    def load_tabs_config(self) -> List[str]:
        """
        加载标签配置
        
        Returns:
            动态标签 key 列表
        """
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                tabs = config.get("dynamic_tabs", [])
                print(f"📂 加载标签配置: {tabs}")
                return tabs
        except Exception as e:
            print(f"❌ 加载标签配置失败: {e}")
        
        # 默认配置
        return ["jmcomic", "picacg"]
    
    def cleanup(self):
        """清理所有页面"""
        for key in list(self._pages.keys()):
            self.remove_page(key)
