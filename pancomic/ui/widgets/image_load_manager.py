# pancomic/ui/widgets/image_load_manager.py
"""
简化的图片加载管理器 - 解决线程冲突和卡顿问题
"""
import requests
from typing import Dict
from pathlib import Path

from PySide6.QtWidgets import QLabel
from PySide6.QtCore import QObject, QThread, Signal, QTimer
from PySide6.QtGui import QPixmap


class SimpleImageWorker(QObject):
    """简化的图片加载工作线程 - 使用requests避免asyncio冲突"""
    
    image_loaded = Signal(str, QPixmap)  # url, pixmap
    image_failed = Signal(str)  # url
    
    def __init__(self):
        super().__init__()
        self.session = None
    
    def _get_session(self):
        """获取requests会话"""
        if not self.session:
            self.session = requests.Session()
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8'
            })
        return self.session
    
    def load_image(self, url: str):
        """加载图片 - 使用requests同步请求"""
        try:
            session = self._get_session()
            response = session.get(url, timeout=10)
            response.raise_for_status()
            
            pixmap = QPixmap()
            if pixmap.loadFromData(response.content):
                self.image_loaded.emit(url, pixmap)
            else:
                self.image_failed.emit(url)
                
        except Exception as e:
            print(f"[WARN] Failed to load image {url}: {e}")
            self.image_failed.emit(url)
    
    def cleanup(self):
        """清理资源"""
        if self.session:
            self.session.close()
            self.session = None


class ImageLoadManager(QObject):
    """简化的图片加载管理器 - 专注性能和稳定性"""
    
    # 信号定义
    image_loaded = Signal(QLabel, QPixmap)  # label, pixmap
    
    def __init__(self, max_concurrent=1):
        super().__init__()
        self.max_concurrent = max_concurrent  # 限制并发数为1，避免卡顿
        self.cache = {}  # 图片缓存
        self.loading_urls = set()  # 正在加载的URL
        self.label_url_map = {}  # 标签到URL的映射
        self.max_cache_size = 50  # 减少缓存大小
        
        # 工作线程
        self._worker_thread = QThread()
        self._worker = SimpleImageWorker()
        self._worker.moveToThread(self._worker_thread)
        
        # 连接信号
        self._worker.image_loaded.connect(self._on_image_loaded)
        self._worker.image_failed.connect(self._on_image_failed)
        
        self._worker_thread.start()
    
    def request_image(self, label: QLabel, url: str, priority: int = 0, lazy: bool = False):
        """请求加载图片 - 简化逻辑"""
        if not url or not label:
            label.setText("无图")
            return
        
        # 检查缓存
        if url in self.cache:
            self._apply_cached_image(label, url)
            return
        
        # 检查是否正在加载
        if url in self.loading_urls:
            self.label_url_map[label] = url
            return
        
        # 开始加载
        self.loading_urls.add(url)
        self.label_url_map[label] = url
        
        # 延迟加载以避免UI卡顿
        QTimer.singleShot(50, lambda: self._worker.load_image(url))
    
    def _apply_cached_image(self, label: QLabel, url: str):
        """应用缓存的图片"""
        try:
            from PySide6.QtCore import Qt
            pixmap = self.cache[url]
            if pixmap and not pixmap.isNull():
                # 缩放图片以适应标签大小
                scaled_pixmap = pixmap.scaled(
                    label.size(), 
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                label.setPixmap(scaled_pixmap)
            else:
                label.setText("×")
        except Exception as e:
            print(f"[ERROR] Failed to apply cached image: {e}")
            label.setText("×")
    
    def _on_image_loaded(self, url: str, pixmap: QPixmap):
        """处理图片加载完成"""
        # 添加到缓存
        self._add_to_cache(url, pixmap)
        
        # 更新所有等待此URL的标签
        labels_to_update = []
        for label, mapped_url in list(self.label_url_map.items()):
            if mapped_url == url:
                labels_to_update.append(label)
        
        # 应用图片到标签并发出信号
        for label in labels_to_update:
            if label and not label.isHidden():
                self._apply_cached_image(label, url)
                # 发出信号通知外部
                self.image_loaded.emit(label, pixmap)
        
        # 清理
        self.loading_urls.discard(url)
        
        # 清理标签映射
        for label in labels_to_update:
            if label in self.label_url_map:
                del self.label_url_map[label]
    
    def _on_image_failed(self, url: str):
        """处理图片加载失败"""
        # 更新所有等待此URL的标签
        labels_to_update = []
        for label, mapped_url in list(self.label_url_map.items()):
            if mapped_url == url:
                labels_to_update.append(label)
        
        # 显示失败标识
        for label in labels_to_update:
            if label and not label.isHidden():
                label.setText("×")
        
        # 清理
        self.loading_urls.discard(url)
        
        # 清理标签映射
        for label in labels_to_update:
            if label in self.label_url_map:
                del self.label_url_map[label]
    
    def _add_to_cache(self, url: str, pixmap: QPixmap):
        """添加到缓存"""
        if len(self.cache) >= self.max_cache_size:
            # 清理最旧的缓存
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
        
        self.cache[url] = pixmap
    
    def clear_cache(self):
        """清空缓存"""
        self.cache.clear()
    
    def clear_queue(self):
        """清空加载队列"""
        self.loading_urls.clear()
        self.label_url_map.clear()
        print("[INFO] 图片加载队列已清理")
    
    def force_load_visible(self, scroll_area):
        """强制加载可见区域的图片 - 兼容性方法"""
        # 这是一个兼容性方法，实际上我们的简化版本不需要特殊处理
        pass
    
    def cleanup(self):
        """清理资源"""
        # 清空数据
        self.cache.clear()
        self.loading_urls.clear()
        self.label_url_map.clear()
        
        # 停止工作线程
        if self._worker_thread and self._worker_thread.isRunning():
            self._worker.cleanup()
            self._worker_thread.quit()
            self._worker_thread.wait(3000)
        
        print("[INFO] ImageLoadManager cleaned up")