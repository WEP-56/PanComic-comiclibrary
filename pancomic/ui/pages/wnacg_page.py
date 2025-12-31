"""WNACG (绅士漫画) source page with split layout and async operations."""

from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, 
    QLabel, QPushButton, QScrollArea, QFrame, QLineEdit
)
from PySide6.QtCore import Qt, Signal, QThread, QObject, Slot, QTimer, QRect

from pancomic.adapters.wnacg_adapter import WNACGAdapter
from pancomic.models.comic import Comic
from pancomic.models.chapter import Chapter
from pancomic.infrastructure.download_manager import DownloadManager


class ImageLoadWorker(QObject):
    """图片加载工作线程"""
    
    image_loaded = Signal(str, object)  # url, pixmap
    
    def __init__(self):
        super().__init__()
        self.client = None
    
    def _get_client(self):
        """获取httpx客户端"""
        if not self.client:
            import httpx
            self.client = httpx.Client(
                timeout=8,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Referer': 'https://www.wnacg.com/',
                }
            )
        return self.client
    
    @Slot(str)
    def load_image(self, url: str):
        """在工作线程中加载图片"""
        try:
            from PySide6.QtGui import QPixmap
            
            client = self._get_client()
            response = client.get(url)
            
            if response.status_code == 200:
                pixmap = QPixmap()
                if pixmap.loadFromData(response.content):
                    self.image_loaded.emit(url, pixmap)
                else:
                    self.image_loaded.emit(url, None)
            else:
                self.image_loaded.emit(url, None)
                
        except Exception as e:
            print(f"Image load error: {e}")
            self.image_loaded.emit(url, None)
    
    def cleanup(self):
        """清理资源"""
        if self.client:
            self.client.close()
            self.client = None


class ImageLoadManager(QObject):
    """优化的图片加载管理器，使用独立工作线程"""
    
    image_loaded = Signal(QLabel, object)  # label, pixmap
    
    def __init__(self, max_concurrent=2):
        super().__init__()
        self.max_concurrent = max_concurrent
        self.loading_queue = []  # (priority, label, url, timestamp)
        self.loading_urls = set()  # 正在加载的URL
        self.cache = {}  # url -> pixmap
        self.current_loading = 0
        self.pending_requests = {}  # label -> (url, priority)
        self.label_url_map = {}  # label -> url (用于匹配返回结果)
        
        # 工作线程
        self._worker_thread = QThread()
        self._worker = ImageLoadWorker()
        self._worker.moveToThread(self._worker_thread)
        
        # 连接信号
        self._worker.image_loaded.connect(self._on_image_loaded)
        
        # 启动线程
        self._worker_thread.start()
        
        # 延迟加载定时器
        self.lazy_timer = QTimer()
        self.lazy_timer.setSingleShot(True)
        self.lazy_timer.timeout.connect(self._process_lazy_queue)
        
        # 加载调度定时器
        self.schedule_timer = QTimer()
        self.schedule_timer.setSingleShot(True)
        self.schedule_timer.timeout.connect(self._schedule_next_load)
        
    def request_image(self, label: QLabel, url: str, priority: int = 0, lazy: bool = True):
        """请求加载图片"""
        if not url:
            label.setText("无图")
            return
            
        # 检查缓存
        if url in self.cache:
            pixmap = self.cache[url]
            if pixmap and not pixmap.isNull():
                scaled = pixmap.scaled(45, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                label.setPixmap(scaled)
            else:
                label.setText("×")
            return
        
        # 检查是否已在加载
        if url in self.loading_urls:
            # 记录标签映射，以便加载完成时更新
            self.label_url_map[label] = url
            return
        
        # 存储待处理请求
        self.pending_requests[label] = (url, priority)
        self.label_url_map[label] = url
        
        if lazy:
            # 懒加载：延迟处理请求
            if not self.lazy_timer.isActive():
                self.lazy_timer.start(200)  # 200ms后开始处理
        else:
            # 立即加载（高优先级）
            self._add_to_queue(label, url, priority)
    
    def _process_lazy_queue(self):
        """处理懒加载队列"""
        # 只处理可见的图片
        visible_requests = []
        
        for label, (url, priority) in list(self.pending_requests.items()):
            if self._is_label_visible(label):
                visible_requests.append((priority, label, url))
        
        # 按优先级排序，只加载前几个
        visible_requests.sort(key=lambda x: x[0], reverse=True)
        
        # 限制同时加载的数量
        max_batch = min(4, len(visible_requests))  # 最多同时加载4个
        
        for i in range(max_batch):
            priority, label, url = visible_requests[i]
            self._add_to_queue(label, url, priority)
            if label in self.pending_requests:
                del self.pending_requests[label]
        
        # 如果还有待处理的请求，继续延迟处理
        if self.pending_requests:
            self.lazy_timer.start(800)  # 800ms后再次处理
    
    def _is_label_visible(self, label: QLabel) -> bool:
        """检查标签是否可见"""
        try:
            if not label or not label.isVisible():
                return False
            
            # 获取标签在父窗口中的位置
            parent = label.parent()
            while parent and not isinstance(parent, QScrollArea):
                parent = parent.parent()
            
            if not parent:
                return True  # 如果找不到滚动区域，认为可见
            
            # 简单的可见性检测
            scroll_area = parent
            viewport = scroll_area.viewport()
            
            if not viewport:
                return True
            
            # 获取标签相对于视口的位置
            label_pos = label.mapTo(viewport, label.rect().topLeft())
            label_rect = QRect(label_pos, label.size())
            viewport_rect = viewport.rect()
            
            # 检查是否有交集（即是否可见）
            return label_rect.intersects(viewport_rect)
            
        except Exception:
            return True  # 出错时认为可见
    
    def _add_to_queue(self, label: QLabel, url: str, priority: int):
        """添加到加载队列"""
        import time
        timestamp = time.time()
        self.loading_queue.append((priority, label, url, timestamp))
        self.loading_queue.sort(key=lambda x: (x[0], -x[3]), reverse=True)  # 按优先级和时间排序
        
        self._schedule_next_load()
    
    def _schedule_next_load(self):
        """调度下一个加载任务"""
        if self.current_loading >= self.max_concurrent or not self.loading_queue:
            return
            
        priority, label, url, timestamp = self.loading_queue.pop(0)
        
        # 检查标签是否仍然有效
        if not label or not label.isVisible():
            self._schedule_next_load()  # 跳过无效标签，尝试下一个
            return
        
        # 检查是否已在加载
        if url in self.loading_urls:
            self._schedule_next_load()  # 跳过已在加载的URL
            return
        
        self.current_loading += 1
        self.loading_urls.add(url)
        
        # 在工作线程中加载图片
        QTimer.singleShot(50, lambda: self._worker.load_image(url))
    
    @Slot(str, object)
    def _on_image_loaded(self, url: str, pixmap):
        """处理图片加载完成"""
        # 缓存图片
        self.cache[url] = pixmap
        
        # 更新所有等待此URL的标签
        labels_to_update = []
        for label, mapped_url in list(self.label_url_map.items()):
            if mapped_url == url:
                labels_to_update.append(label)
        
        # 在主线程中更新UI
        for label in labels_to_update:
            if label and label.isVisible():
                if pixmap and not pixmap.isNull():
                    scaled = pixmap.scaled(45, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    label.setPixmap(scaled)
                else:
                    label.setText("×")
        
        # 清理
        self.loading_urls.discard(url)
        self.current_loading -= 1
        
        # 清理标签映射
        for label in labels_to_update:
            if label in self.label_url_map:
                del self.label_url_map[label]
        
        # 调度下一个加载任务
        if not self.schedule_timer.isActive():
            self.schedule_timer.start(100)  # 100ms后调度下一个
    
    def clear_queue(self):
        """清空加载队列"""
        self.loading_queue.clear()
        self.pending_requests.clear()
        self.label_url_map.clear()
        self.loading_urls.clear()
        
        if self.lazy_timer.isActive():
            self.lazy_timer.stop()
        
        if self.schedule_timer.isActive():
            self.schedule_timer.stop()
        
        self.current_loading = 0
    
    def force_load_visible(self, scroll_area):
        """强制加载当前可见区域的图片"""
        if not self.pending_requests:
            return
        
        # 处理所有可见的待处理请求
        for label, (url, priority) in list(self.pending_requests.items()):
            if self._is_label_visible(label):
                self._add_to_queue(label, url, priority + 10)  # 提高优先级
                del self.pending_requests[label]
    
    def cleanup(self):
        """清理资源"""
        print("[INFO] ImageLoadManager cleanup started...")
        
        try:
            self.clear_queue()
        except Exception as e:
            print(f"[ERROR] Error clearing queue: {e}")
        
        try:
            if hasattr(self, '_worker_thread') and self._worker_thread and self._worker_thread.isRunning():
                print("[INFO] Stopping image worker thread...")
                # 清理工作线程
                if hasattr(self, '_worker') and self._worker:
                    self._worker.cleanup()
                
                self._worker_thread.quit()
                if not self._worker_thread.wait(3000):  # 等待最多3秒
                    print("[WARN] Image worker thread did not stop gracefully, terminating...")
                    self._worker_thread.terminate()
                    self._worker_thread.wait(1000)
                print("[INFO] Image worker thread stopped")
        except Exception as e:
            print(f"[ERROR] Error stopping image worker thread: {e}")
        
        print("[INFO] ImageLoadManager cleanup completed")


class WNACGSearchWorker(QObject):
    """WNACG搜索工作线程"""
    
    search_completed = Signal(list, int)  # comics, max_page
    search_failed = Signal(str)  # error_message
    details_completed = Signal(dict)  # comic_details
    details_failed = Signal(str)  # error_message
    
    def __init__(self, adapter: WNACGAdapter):
        super().__init__()
        self.adapter = adapter
        self._current_task = None
    
    @Slot(str, int)
    def search_comics(self, keyword: str, page: int):
        """搜索漫画"""
        self._current_task = ('search', keyword, page)
        try:
            result = self.adapter.search(keyword, page)
            comics_data = result["comics"]
            max_page = result["max_page"]
            
            # Convert to Comic objects
            comics = []
            for comic_data in comics_data:
                comic = Comic(
                    id=comic_data["comic_id"],
                    title=comic_data["title"],
                    author="",  # Will be filled in details
                    cover_url=comic_data["cover"],
                    description=comic_data["description"],
                    tags=[],
                    categories=[],
                    status="completed",
                    chapter_count=1,  # WNACG只有一个章节
                    view_count=0,
                    like_count=0,
                    is_favorite=False,
                    source="wnacg"
                )
                comics.append(comic)
            
            self.search_completed.emit(comics, max_page)
            
        except Exception as e:
            self.search_failed.emit(str(e))
    
    @Slot(str)
    def get_comic_details(self, comic_id: str):
        """获取漫画详情"""
        self._current_task = ('details', comic_id)
        try:
            details = self.adapter.get_comic_details(comic_id)
            self.details_completed.emit(details)
            
        except Exception as e:
            print(f"[ERROR] 获取详情失败: {e}")
            self.details_failed.emit(str(e))


class WNACGPage(QWidget):
    """
    WNACG (绅士漫画) source page with split layout and optimized image loading.
    
    Left panel: Search results with pagination (12 per page)
    Right panel: Comic details with read/download buttons
    """
    
    # Signals
    read_requested = Signal(object, object)  # Comic, Chapter
    download_requested = Signal(object, list)  # Comic, List[Chapter]
    queue_requested = Signal(object, list)  # Comic, List[Chapter] - add to queue
    settings_requested = Signal()  # Request to navigate to settings
    
    # Internal signals for worker communication
    _search_requested = Signal(str, int)  # keyword, page
    _details_requested = Signal(str)  # comic_id
    
    def __init__(self, adapter: WNACGAdapter, download_manager: DownloadManager, parent: Optional[QWidget] = None):
        """
        Initialize WNACGPage.
        
        Args:
            adapter: WNACG adapter instance
            download_manager: Download manager instance
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.adapter = adapter
        self.download_manager = download_manager
        
        # State
        self._current_keyword = ""
        self._current_page = 1
        self._total_results = 0
        self._results_per_page = 12
        self._all_comics = []
        self._selected_comic = None
        self._comic_chapters = []
        self._current_theme = 'dark'  # Track current theme
        self._current_display_count = 0
        
        # Worker thread for async operations
        self._worker_thread = None
        self._worker = None
        
        # Image loading manager (更保守的并发设置)
        self._image_manager = ImageLoadManager(1)  # 限制同时加载1张图片，避免卡顿
        self._image_manager.image_loaded.connect(self._on_image_loaded)
        
        # Setup UI
        self._setup_ui()
        
        # Setup worker thread
        self._setup_worker_thread()
        
        # Apply initial theme
        self.apply_theme('dark')
    
    def _on_image_loaded(self, label: QLabel, pixmap):
        """处理图片加载完成"""
        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(45, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            label.setPixmap(scaled)
        else:
            label.setText("×")
    
    def _setup_worker_thread(self):
        """Setup worker thread for async operations."""
        self._worker_thread = QThread()
        self._worker = WNACGSearchWorker(self.adapter)
        self._worker.moveToThread(self._worker_thread)
        
        # Connect worker signals
        self._worker.search_completed.connect(self._on_search_completed)
        self._worker.search_failed.connect(self._on_search_failed)
        self._worker.details_completed.connect(self._on_details_completed)
        self._worker.details_failed.connect(self._on_details_failed)
        
        # Connect page signals to worker
        self._search_requested.connect(self._worker.search_comics)
        self._details_requested.connect(self._worker.get_comic_details)
        
        # Start thread
        self._worker_thread.start()
    
    def _setup_ui(self) -> None:
        """Setup the split layout UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Search bar
        search_container = self._create_search_bar()
        layout.addWidget(search_container)
        
        # Split view: Left (results) | Right (details)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setObjectName("mainSplitter")  # 使用对象名，通过主题样式控制
        
        # Left panel: Search results
        self.results_panel = self._create_results_panel()
        splitter.addWidget(self.results_panel)
        
        # Right panel: Comic details
        self.details_panel = self._create_details_panel()
        splitter.addWidget(self.details_panel)
        
        # Set initial sizes (5:3 ratio)
        splitter.setSizes([625, 375])  # 62.5% : 37.5%
        
        layout.addWidget(splitter)
    
    def _create_search_bar(self) -> QWidget:
        """Create the search bar component."""
        search_container = QWidget()
        search_container.setFixedHeight(60)
        # 移除硬编码样式，使用apply_theme方法控制
        
        layout = QHBoxLayout(search_container)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(10)
        
        # Search input
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("搜索绅士漫画...")
        self.search_bar.setFixedHeight(40)
        self.search_bar.returnPressed.connect(self._on_search_clicked)
        
        # Search button
        self.search_button = QPushButton("搜索")
        self.search_button.setFixedSize(80, 40)
        self.search_button.clicked.connect(self._on_search_clicked)
        
        # Settings button
        settings_btn = QPushButton("设置")
        settings_btn.setFixedSize(60, 40)
        settings_btn.clicked.connect(self._navigate_to_settings)
        
        # Status label
        self.status_label = QLabel("就绪")
        # 移除硬编码样式
        
        layout.addWidget(self.search_bar)
        layout.addWidget(self.search_button)
        layout.addWidget(settings_btn)
        layout.addWidget(self.status_label)
        
        return search_container
    
    def _create_results_panel(self) -> QWidget:
        """Create the left results panel."""
        panel = QWidget()
        # 移除硬编码样式，使用apply_theme控制
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Results header - 遵循jmcomic标准格式
        header_layout = QHBoxLayout()
        self.results_label = QLabel("搜索结果")
        header_layout.addWidget(self.results_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Scroll area for results
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setObjectName("resultsScrollArea")  # 使用对象名，通过主题样式控制
        
        # 监听滚动事件
        scroll.verticalScrollBar().valueChanged.connect(self._on_scroll_changed)
        
        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(5)
        scroll.setWidget(self.results_container)
        
        # 存储滚动区域引用
        self.results_scroll_area = scroll
        
        # Pagination controls - 遵循jmcomic标准格式
        pagination_layout = QHBoxLayout()
        self.prev_button = QPushButton("上一页")
        self.prev_button.setFixedHeight(32)  # 与jmcomic保持一致
        self.prev_button.setEnabled(False)
        self.prev_button.clicked.connect(self._on_prev_page)
        
        self.page_label = QLabel("第 1 页")
        self.page_label.setAlignment(Qt.AlignCenter)
        
        self.next_button = QPushButton("下一页")
        self.next_button.setFixedHeight(32)  # 与jmcomic保持一致
        self.next_button.setEnabled(False)
        self.next_button.clicked.connect(self._on_next_page)
        
        pagination_layout.addWidget(self.prev_button)
        pagination_layout.addStretch()
        pagination_layout.addWidget(self.page_label)
        pagination_layout.addStretch()
        pagination_layout.addWidget(self.next_button)
        
        layout.addLayout(header_layout)
        layout.addWidget(scroll)
        layout.addLayout(pagination_layout)
        # 删除了加载更多按钮
        
        return panel
    
    def _create_details_panel(self) -> QWidget:
        """Create the right details panel."""
        panel = QWidget()
        # 移除硬编码样式
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Placeholder
        self.details_placeholder = QLabel("← 选择一个漫画查看详情")
        self.details_placeholder.setAlignment(Qt.AlignCenter)
        self.details_placeholder.setObjectName("detailsPlaceholder")  # 使用对象名，通过主题样式控制
        
        # Details content (initially hidden)
        self.details_content = QWidget()
        self.details_content.setVisible(False)
        details_layout = QVBoxLayout(self.details_content)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(15)
        
        # Cover image (fixed size 200x267, 3:4 ratio)
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(200, 267)
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setObjectName("coverLabel")  # 使用对象名，通过主题样式控制
        self.cover_label.setText("加载中...")
        
        # Title
        self.title_label = QLabel()
        self.title_label.setWordWrap(True)
        self.title_label.setObjectName("titleLabel")  # 使用对象名，通过主题样式控制
        
        # Info labels
        self.author_label = QLabel()
        self.author_label.setObjectName("infoLabel")  # 使用对象名，通过主题样式控制
        
        self.category_label = QLabel()
        self.category_label.setObjectName("infoLabel")  # 使用对象名，通过主题样式控制
        
        self.pages_label = QLabel()
        self.pages_label.setObjectName("infoLabel")  # 使用对象名，通过主题样式控制
        
        self.id_label = QLabel()
        self.id_label.setObjectName("infoLabel")  # 使用对象名，通过主题样式控制
        
        # Tags
        self.tags_label = QLabel()
        self.tags_label.setWordWrap(True)
        self.tags_label.setObjectName("infoLabel")  # 使用对象名，通过主题样式控制
        
        # Action buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)
        
        self.read_button = QPushButton("阅读")
        self.read_button.setFixedHeight(40)
        self.read_button.setEnabled(False)  # 初始禁用
        self.read_button.setObjectName("actionButton")  # 使用对象名，通过主题样式控制
        self.read_button.clicked.connect(self._on_read_clicked)
        
        self.download_button = QPushButton("下载")
        self.download_button.setFixedHeight(40)
        self.download_button.setEnabled(False)  # 初始禁用
        self.download_button.setObjectName("actionButton")  # 使用对象名，通过主题样式控制
        self.download_button.clicked.connect(self._on_download_clicked)
        
        self.queue_button = QPushButton("加入队列")
        self.queue_button.setFixedHeight(40)
        self.queue_button.setEnabled(False)  # 初始禁用
        self.queue_button.setObjectName("actionButton")  # 使用对象名，通过主题样式控制
        self.queue_button.clicked.connect(self._on_queue_clicked)
        
        buttons_layout.addWidget(self.read_button)
        buttons_layout.addWidget(self.download_button)
        buttons_layout.addWidget(self.queue_button)
        
        # Add components to details layout
        details_layout.addWidget(self.cover_label, 0, Qt.AlignHCenter)
        details_layout.addWidget(self.title_label)
        details_layout.addWidget(self.author_label)
        details_layout.addWidget(self.category_label)
        details_layout.addWidget(self.pages_label)
        details_layout.addWidget(self.id_label)
        details_layout.addWidget(self.tags_label)
        details_layout.addLayout(buttons_layout)
        details_layout.addStretch()
        
        # Add to main layout
        layout.addWidget(self.details_placeholder)
        layout.addWidget(self.details_content)
        
        return panel
    
    def _create_result_card(self, comic: Comic) -> QWidget:
        """Create a result card for a comic."""
        card = QFrame()
        card.setFixedHeight(80)
        card.setCursor(Qt.PointingHandCursor)
        card.setObjectName("resultCard")  # 使用对象名，通过主题样式控制
        
        # Store comic reference
        card.comic = comic
        
        # Click handler
        def on_card_clicked():
            self._on_comic_selected(comic)
        
        card.mousePressEvent = lambda event: on_card_clicked()
        
        layout = QHBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # Thumbnail (fixed size 45x60)
        thumb = QLabel()
        thumb.setFixedSize(45, 60)
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setObjectName("thumbLabel")  # 使用对象名，通过主题样式控制
        thumb.setText("加载中...")
        
        # Request thumbnail loading (lazy loading)
        if comic.cover_url:
            self._image_manager.request_image(thumb, comic.cover_url, priority=1, lazy=True)
        
        # Info area
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(3)
        
        # Title (max 2 lines)
        title = QLabel(comic.title)
        title.setMaximumHeight(36)
        title.setWordWrap(True)
        title.setObjectName("cardTitle")  # 使用对象名，通过主题样式控制
        
        # Description/pages info
        desc = QLabel(comic.description or f"ID: {comic.id}")
        desc.setObjectName("cardDescription")  # 使用对象名，通过主题样式控制
        
        info_layout.addWidget(title)
        info_layout.addWidget(desc)
        info_layout.addStretch()
        
        layout.addWidget(thumb)
        layout.addWidget(info_widget, 1)
        
        return card
    
    def _on_scroll_changed(self, value):
        """处理滚动事件，触发可见图片加载"""
        # 延迟触发，避免滚动时频繁调用
        if not hasattr(self, '_scroll_timer'):
            self._scroll_timer = QTimer()
            self._scroll_timer.setSingleShot(True)
            self._scroll_timer.timeout.connect(self._load_visible_images)
        
        self._scroll_timer.start(100)  # 100ms后触发
    
    def _load_visible_images(self):
        """加载当前可见区域的图片"""
        if hasattr(self, 'results_scroll_area'):
            self._image_manager.force_load_visible(self.results_scroll_area)
    
    # Event handlers
    def _navigate_to_settings(self):
        """Navigate to settings page."""
        self.settings_requested.emit()
    
    def _on_search_clicked(self):
        """Handle search button click."""
        keyword = self.search_bar.text().strip()
        if not keyword:
            return
        
        self._current_keyword = keyword
        self._current_page = 1
        self._current_display_count = 0
        
        # Clear previous results
        self._clear_results()
        
        # Update UI
        self.status_label.setText("搜索中...")
        self.search_button.setEnabled(False)
        
        # Clear image loading queue
        self._image_manager.clear_queue()
        
        # Start search
        self._search_requested.emit(keyword, self._current_page)
    
    def _on_prev_page(self):
        """Handle previous page button click."""
        if self._current_page > 1:
            self._current_page -= 1
            self._perform_search()
    
    def _on_next_page(self):
        """Handle next page button click."""
        self._current_page += 1
        self._perform_search()
    
    def _perform_search(self, append_results=False):
        """Perform search with current parameters."""
        if not self._current_keyword:
            return
        
        if not append_results:
            self._clear_results()
        
        self.status_label.setText("搜索中...")
        self.search_button.setEnabled(False)
        
        self._search_requested.emit(self._current_keyword, self._current_page)
    
    def _on_comic_selected(self, comic: Comic):
        """Handle comic selection."""
        self._selected_comic = comic
        
        # Show loading state
        self.details_placeholder.setVisible(False)
        self.details_content.setVisible(True)
        
        # Update basic info immediately
        self.title_label.setText(comic.title)
        self.id_label.setText(f"ID: {comic.id}")
        
        # Load cover image (immediate loading for details)
        if comic.cover_url:
            self._image_manager.request_image(self.cover_label, comic.cover_url, priority=10, lazy=False)
        
        # Request detailed info
        self._details_requested.emit(comic.id)
    
    def _on_read_clicked(self):
        """Handle read button click."""
        if not self._selected_comic or not self._comic_chapters:
            return
        
        # For WNACG, there's only one chapter
        chapter = self._comic_chapters[0]
        self.read_requested.emit(self._selected_comic, chapter)
    
    def _on_download_clicked(self):
        """Handle download button click."""
        if not self._selected_comic or not self._comic_chapters:
            return
        
        self.download_requested.emit(self._selected_comic, self._comic_chapters)
    
    def _on_queue_clicked(self):
        """Handle queue button click."""
        if not self._selected_comic or not self._comic_chapters:
            return
        
        self.queue_requested.emit(self._selected_comic, self._comic_chapters)
    
    # Worker signal handlers
    @Slot(list, int)
    def _on_search_completed(self, comics: List[Comic], max_page: int):
        """Handle search completion."""
        
        # Update status
        self.status_label.setText("搜索完成")
        self.search_button.setEnabled(True)
        
        # Store results
        if self._current_page == 1:
            self._all_comics = comics
            self._current_display_count = 0
        else:
            self._all_comics.extend(comics)
        
        # Display results (lazy loading - show 12 at a time)
        self._display_results(comics)
        
        # Update pagination
        self._update_pagination(max_page)
        
        # Update results label - 遵循jmcomic标准格式
        total_results = len(self._all_comics)
        self.results_label.setText(f"搜索结果 ({total_results} 个)")
        
        # 延迟加载初始可见的图片
        QTimer.singleShot(300, self._load_visible_images)
    
    @Slot(str)
    def _on_search_failed(self, error_message: str):
        """Handle search failure."""
        print(f"[ERROR] 搜索失败: {error_message}")
        self.status_label.setText(f"搜索失败: {error_message}")
        self.search_button.setEnabled(True)
    
    @Slot(dict)
    def _on_details_completed(self, details: dict):
        """Handle details completion."""
        
        # Update UI with detailed info
        self.title_label.setText(details["title"])
        self.author_label.setText(f"作者: {', '.join(details.get('authors', ['未知']))}")
        self.category_label.setText(f"分类: {details.get('category', '未知')}")
        self.pages_label.setText(f"页数: {details.get('pages', 0)} 页")
        
        # Tags
        tags = details.get("tags", [])
        if tags:
            self.tags_label.setText(f"标签: {', '.join(tags)}")
        else:
            self.tags_label.setText("")
        
        # Create chapters (WNACG only has one chapter)
        chapters_data = details.get("chapters", [])
        self._comic_chapters = []
        for ch_data in chapters_data:
            chapter = Chapter(
                id=ch_data["chapter_id"],
                comic_id=self._selected_comic.id,
                title=ch_data["title"],
                chapter_number=1,  # WNACG只有一个章节
                page_count=details.get('pages', 0),
                is_downloaded=False,
                download_path=None,
                source="wnacg"
            )
            self._comic_chapters.append(chapter)
        
        # Enable action buttons
        self.read_button.setEnabled(True)
        self.download_button.setEnabled(True)
        self.queue_button.setEnabled(True)
    
    @Slot(str)
    def _on_details_failed(self, error_message: str):
        """Handle details failure."""
        print(f"[ERROR] 详情加载失败: {error_message}")
        self.author_label.setText(f"加载失败: {error_message}")
    
    # Helper methods
    def _clear_results(self):
        """Clear search results."""
        # Clear layout
        while self.results_layout.count():
            child = self.results_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Reset state
        self._all_comics = []
        self._current_display_count = 0
        self.results_label.setText("搜索结果")
    
    def _display_results(self, comics: List[Comic]):
        """Display search results with lazy loading."""
        for comic in comics:
            card = self._create_result_card(comic)
            self.results_layout.addWidget(card)
            self._current_display_count += 1
        
        # Add stretch at the end
        self.results_layout.addStretch()
    
    def _update_pagination(self, max_page: int):
        """Update pagination controls."""
        self.page_label.setText(f"第 {self._current_page} 页 / 共 {max_page} 页")
        
        # Update button states
        self.prev_button.setEnabled(self._current_page > 1)
        self.next_button.setEnabled(self._current_page < max_page)
        
        # 删除了加载更多按钮的相关逻辑
    
    def apply_theme(self, theme: str):
        """Apply theme to the page."""
        self._current_theme = theme
        
        if theme == 'light':
            # Light theme colors
            bg_primary = '#FFFFFF'
            bg_secondary = '#F5F5F5'
            bg_tertiary = '#FAFAFA'
            text_primary = '#000000'
            text_secondary = '#333333'
            text_muted = '#666666'
            border_color = '#E0E0E0'
            accent_color = '#0078D4'
            card_bg = '#FFFFFF'
            card_hover = '#F0F0F0'
        else:
            # Dark theme colors (default)
            bg_primary = '#1e1e1e'
            bg_secondary = '#2b2b2b'
            bg_tertiary = '#252525'
            text_primary = '#ffffff'
            text_secondary = '#cccccc'
            text_muted = '#888888'
            border_color = '#3a3a3a'
            accent_color = '#0078d4'
            card_bg = '#2b2b2b'
            card_hover = '#333333'
        
        # Apply theme styles to the entire page
        self.setStyleSheet(f"""
            /* 主容器 */
            QWidget {{
                background-color: {bg_primary};
                color: {text_primary};
            }}
            
            /* 分割器 */
            #mainSplitter::handle {{
                background-color: {border_color};
            }}
            
            /* 滚动区域 */
            #resultsScrollArea {{
                border: none;
                background-color: transparent;
            }}
            
            /* 搜索栏 */
            QLineEdit {{
                background-color: {bg_primary};
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 8px 12px;
                color: {text_primary};
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border-color: {accent_color};
            }}
            
            /* 搜索按钮和设置按钮 */
            QPushButton {{
                background-color: {accent_color};
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: #1084d8;
            }}
            QPushButton:pressed {{
                background-color: #006cbd;
            }}
            QPushButton:disabled {{
                background-color: {text_muted};
                color: #a0aec0;
            }}
            
            /* 操作按钮 - 使用更强的选择器和!important强制应用 */
            QPushButton#actionButton {{
                background-color: {accent_color} !important;
                color: white !important;
                border: none !important;
                border-radius: 6px !important;
                font-weight: bold !important;
                font-size: 14px !important;
                padding: 8px 16px !important;
                min-width: 60px !important;
                min-height: 32px !important;
            }}
            QPushButton#actionButton:hover {{
                background-color: #1084d8 !important;
            }}
            QPushButton#actionButton:pressed {{
                background-color: #006cbd !important;
            }}
            QPushButton#actionButton:disabled {{
                background-color: {text_muted} !important;
                color: #a0aec0 !important;
            }}
            
            /* 结果卡片 - 添加淡色边框来区分卡片 */
            #resultCard {{
                background-color: {card_bg};
                border: 1px solid {border_color};
                border-radius: 6px;
            }}
            #resultCard:hover {{
                background-color: {card_hover};
            }}
            
            /* 卡片标题 */
            #cardTitle {{
                color: {text_primary};
                font-weight: bold;
                font-size: 13px;
                border: none;
            }}
            
            /* 卡片描述 */
            #cardDescription {{
                color: {text_secondary};
                font-size: 11px;
                border: none;
            }}
            
            /* 缩略图 - 移除边框 */
            #thumbLabel {{
                background-color: {bg_secondary};
                border: none;
                border-radius: 4px;
                color: {text_muted};
                font-size: 10px;
            }}
            
            /* 封面图片 - 移除边框 */
            #coverLabel {{
                background-color: {bg_secondary};
                border: none;
                border-radius: 8px;
                color: {text_muted};
            }}
            
            /* 标题标签 */
            #titleLabel {{
                color: {text_primary};
                font-size: 16px;
                font-weight: bold;
                border: none;
                margin-bottom: 5px;
            }}
            
            /* 信息标签 */
            #infoLabel {{
                color: {text_secondary};
                border: none;
                margin-bottom: 3px;
            }}
            
            /* 详情占位符 */
            #detailsPlaceholder {{
                color: {text_muted};
                font-size: 16px;
                font-style: italic;
                border: none;
            }}
            
            /* 标签 - 移除所有边框 */
            QLabel {{
                color: {text_primary};
                background: transparent;
                border: none;
            }}
            
            /* 滚动条 */
            QScrollBar:vertical {{
                background-color: {bg_secondary};
                width: 12px;
                border-radius: 6px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {border_color};
                border-radius: 6px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {text_muted};
            }}
        """)
        
        # 应用面板样式 - 遵循jmcomic标准
        if hasattr(self, 'results_panel'):
            self.results_panel.setStyleSheet(f"background-color: {bg_primary};")
        
        if hasattr(self, 'details_panel'):
            self.details_panel.setStyleSheet(f"background-color: {bg_tertiary};")
        
        # 应用分页按钮样式 - 遵循jmcomic标准
        pagination_style = f"""
            QPushButton {{
                background-color: {border_color};
                border: none;
                border-radius: 4px;
                color: {text_primary};
                padding: 0 20px;
            }}
            QPushButton:hover:enabled {{
                background-color: {text_muted};
            }}
            QPushButton:disabled {{
                color: {text_muted};
            }}
        """
        
        if hasattr(self, 'prev_button'):
            self.prev_button.setStyleSheet(pagination_style)
        if hasattr(self, 'next_button'):
            self.next_button.setStyleSheet(pagination_style)
        
        # 应用页码标签样式
        if hasattr(self, 'page_label'):
            self.page_label.setStyleSheet(f"color: {text_primary};")
        
        # 直接为操作按钮设置样式 - 确保样式被应用
        action_button_style = f"""
            QPushButton {{
                background-color: {accent_color};
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
                padding: 8px 16px;
                min-width: 60px;
                min-height: 32px;
            }}
            QPushButton:hover {{
                background-color: #1084d8;
            }}
            QPushButton:pressed {{
                background-color: #006cbd;
            }}
            QPushButton:disabled {{
                background-color: {text_muted};
                color: #a0aec0;
            }}
        """
        
        if hasattr(self, 'read_button'):
            self.read_button.setStyleSheet(action_button_style)
        if hasattr(self, 'download_button'):
            self.download_button.setStyleSheet(action_button_style)
        if hasattr(self, 'queue_button'):
            self.queue_button.setStyleSheet(action_button_style)
    
    def cleanup(self):
        """Cleanup resources when page is destroyed."""
        print("[INFO] WNACGPage cleanup started...")
        
        try:
            # 停止工作线程
            if hasattr(self, '_worker_thread') and self._worker_thread and self._worker_thread.isRunning():
                print("[INFO] Stopping worker thread...")
                # 先断开信号连接，防止清理过程中触发信号
                if hasattr(self, '_worker') and self._worker:
                    self._worker.search_completed.disconnect()
                    self._worker.search_failed.disconnect()
                    self._worker.details_completed.disconnect()
                    self._worker.details_failed.disconnect()
                
                self._worker_thread.quit()
                if not self._worker_thread.wait(3000):  # 等待最多3秒
                    print("[WARN] Worker thread did not stop gracefully, terminating...")
                    self._worker_thread.terminate()
                    self._worker_thread.wait(1000)  # 再等1秒
                print("[INFO] Worker thread stopped")
        except Exception as e:
            print(f"[ERROR] Error stopping worker thread: {e}")
        
        try:
            # 清理图片管理器
            if hasattr(self, '_image_manager') and self._image_manager:
                print("[INFO] Cleaning up image manager...")
                self._image_manager.cleanup()
        except Exception as e:
            print(f"[ERROR] Error cleaning up image manager: {e}")
        
        print("[INFO] WNACGPage cleanup completed")