"""
简化优化的拷贝漫画页面 - 修复异步事件循环问题

主要优化：
1. 使用简单的工作线程避免异步事件循环问题
2. 逐个渲染卡片，消除瞬间卡顿
3. 智能图片加载管理
4. 保持与原始页面相同的搜索逻辑
"""

from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, 
    QLabel, QPushButton, QScrollArea, QFrame, QLineEdit, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QThread, QObject, Slot, QTimer
from PySide6.QtGui import QCursor

from pancomic.adapters.kaobei_adapter import KaobeiAdapter
from pancomic.models.comic import Comic
from pancomic.models.chapter import Chapter
from pancomic.infrastructure.download_manager import DownloadManager
from pancomic.ui.widgets.image_load_manager import ImageLoadManager


class ProgressiveKaobeiSearchWorker(QObject):
    """真正渐进式拷贝漫画搜索工作线程 - 逐个处理和发送数据"""
    
    batch_ready = Signal(list)  # 批次漫画数据
    search_completed = Signal(int)  # max_page
    search_failed = Signal(str)  # error_message
    details_completed = Signal(dict)  # comic_details
    details_failed = Signal(str)  # error_message
    
    def __init__(self, adapter: KaobeiAdapter):
        super().__init__()
        self.adapter = adapter
        self.batch_size = 4  # 每批发送4个漫画到主线程
        self.process_delay = 0.05  # 50ms处理延迟
    
    @Slot(str, int)
    def search_comics(self, keyword: str, page: int):
        """真正渐进式搜索 - 逐个处理数据，分批发送到主线程"""
        try:
            # 1. 获取原始数据
            result = self.adapter.search(keyword, page)
            raw_comics = result["comics"]
            max_page = result["max_page"]
            
            # 2. 逐个处理数据，分批发送
            current_batch = []
            
            for i, data in enumerate(raw_comics):
                # 逐个转换为 Comic 对象
                comic = Comic(
                    id=data["comic_id"],
                    title=data["title"],
                    author="未知",  # 从详情页获取
                    cover_url=data["cover"],
                    description=data.get("description", ""),
                    tags=[],
                    categories=["拷贝漫画"],
                    status="completed",
                    chapter_count=0,
                    view_count=0,
                    like_count=0,
                    is_favorite=False,
                    source="kaobei"
                )
                
                current_batch.append(comic)
                
                # 当批次满了或者是最后一个，发送到主线程
                if len(current_batch) >= self.batch_size or i == len(raw_comics) - 1:
                    self.batch_ready.emit(current_batch.copy())
                    current_batch.clear()
                    
                    # 给主线程时间处理这批数据
                    import time
                    time.sleep(self.process_delay)
            
            # 3. 所有批次发送完毕
            self.search_completed.emit(max_page)
            
        except Exception as e:
            self.search_failed.emit(str(e))
    
    @Slot(str)
    def get_comic_details(self, comic_id: str):
        """在工作线程中获取漫画详情"""
        try:
            details = self.adapter.get_comic_details(comic_id)
            self.details_completed.emit(details)
        except Exception as e:
            self.details_failed.emit(str(e))


class OptimizedKaobeiPage(QWidget):
    """
    简化优化的拷贝漫画页面
    
    特点：
    1. 使用简单的工作线程避免异步问题
    2. 逐个渲染卡片，避免UI线程阻塞
    3. 智能图片加载
    4. 保持与原始页面相同的搜索逻辑
    """
    
    # 信号定义
    read_requested = Signal(object, object)  # Comic, Chapter
    download_requested = Signal(object, list)  # Comic, List[Chapter]
    queue_requested = Signal(object, list)  # Comic, List[Chapter]
    settings_requested = Signal()
    
    def __init__(self, adapter: KaobeiAdapter, download_manager: DownloadManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self.adapter = adapter
        self.download_manager = download_manager
        
        # 搜索状态 - 与原始页面保持一致
        self.current_page = 1
        self.max_page = 1
        self.current_keyword = ""
        self.search_results = []
        self.selected_comic = None
        self.selected_comic_details = None
        self._current_theme = 'dark'
        
        # 逐个渲染状态
        self._pending_comics = []
        self._is_rendering_cards = False
        self._card_render_timer = QTimer()
        self._card_render_timer.timeout.connect(self._render_next_card)
        self._card_render_interval = 8  # 8ms = ~120fps，更流畅
        self._cards_per_frame = 1  # 每帧渲染1个卡片
        
        # 工作线程 - 使用渐进式版本
        self._worker_thread = None
        self._worker = None
        
        # 图片加载管理器
        self._image_manager = ImageLoadManager(max_concurrent=2)
        self._image_manager.image_loaded.connect(self._on_image_loaded)
        
        # 设置UI
        self._setup_ui()
        self._setup_worker_thread()
        
        # 应用默认主题
        self.apply_theme('dark')
    
    def _setup_ui(self):
        """设置UI界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 搜索栏
        search_container = self._create_search_bar()
        layout.addWidget(search_container)
        
        # 主体分割区域
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        
        # 左侧：搜索结果
        self.results_panel = self._create_results_panel()
        splitter.addWidget(self.results_panel)
        
        # 右侧：详情面板
        self.details_panel = self._create_details_panel()
        splitter.addWidget(self.details_panel)
        
        # 设置分割比例 5:3
        splitter.setSizes([625, 375])
        
        layout.addWidget(splitter)
    
    def _create_search_bar(self) -> QWidget:
        """创建搜索栏 - 遵循统一布局规范"""
        search_container = QWidget()
        search_container.setFixedHeight(60)  # 统一高度 60px
        search_container.setObjectName("searchContainer")
        
        layout = QHBoxLayout(search_container)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(10)
        
        # 1. 搜索输入框 (自适应宽度)
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("搜索拷贝漫画... (支持: 更新、排名日/周/月/总、男/女向)")
        self.search_bar.setFixedHeight(40)
        self.search_bar.returnPressed.connect(self._on_search_clicked)
        
        # 2. 搜索按钮 (固定宽度 80px)
        self.search_button = QPushButton("搜索")
        self.search_button.setFixedSize(80, 40)
        self.search_button.clicked.connect(self._on_search_clicked)
        
        # 3. 设置按钮 (固定宽度 60px)
        settings_btn = QPushButton("设置")
        settings_btn.setFixedSize(60, 40)
        settings_btn.clicked.connect(self.settings_requested.emit)
        
        # 4. 状态标签 (自适应)
        self.status_label = QLabel("输入关键词开始搜索")
        self.status_label.setObjectName("statusLabel")
        
        layout.addWidget(self.search_bar)      # 自适应
        layout.addWidget(self.search_button)   # 80px
        layout.addWidget(settings_btn)         # 60px  
        layout.addWidget(self.status_label)    # 自适应
        
        return search_container
    
    def _create_results_panel(self) -> QWidget:
        """创建左侧搜索结果面板 - 遵循统一布局规范"""
        panel = QWidget()
        panel.setObjectName("resultsPanel")
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 结果标题 - 遵循jmcomic标准格式
        header_layout = QHBoxLayout()
        
        self.results_label = QLabel("搜索结果")
        self.results_label.setObjectName("resultsLabel")
        
        header_layout.addWidget(self.results_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # 滚动区域 - 显示漫画卡片
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 监听滚动事件
        scroll.verticalScrollBar().valueChanged.connect(self._on_scroll_changed)
        
        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setContentsMargins(5, 5, 5, 5)
        self.results_layout.setSpacing(5)
        self.results_layout.addStretch()  # 底部弹簧
        
        scroll.setWidget(self.results_container)
        self.results_scroll_area = scroll
        
        # 分页控件
        # 分页控件 - 遵循jmcomic标准格式
        pagination_layout = QHBoxLayout()
        
        self.prev_button = QPushButton("上一页")
        self.prev_button.setFixedHeight(32)  # 与jmcomic保持一致
        self.prev_button.setEnabled(False)
        self.prev_button.clicked.connect(self._on_prev_page)
        
        self.page_label = QLabel("第 1 页")
        self.page_label.setAlignment(Qt.AlignCenter)
        self.page_label.setObjectName("pageLabel")
        
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
        
        return panel
    
    def _create_details_panel(self) -> QWidget:
        """创建右侧详情面板 - 遵循统一布局规范"""
        panel = QWidget()
        panel.setObjectName("detailsPanel")
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 占位符
        self.details_placeholder = QLabel("← 选择一个漫画查看详情")
        self.details_placeholder.setAlignment(Qt.AlignCenter)
        self.details_placeholder.setObjectName("detailsPlaceholder")
        
        # 详情内容
        self.details_content = QWidget()
        self.details_content.setVisible(False)
        details_layout = QVBoxLayout(self.details_content)
        
        # 封面图片 (固定尺寸 200x267, 3:4比例)
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(200, 267)
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setObjectName("coverLabel")
        self.cover_label.setText("加载中...")
        
        # 标题和信息
        self.title_label = QLabel()
        self.title_label.setWordWrap(True)
        self.title_label.setObjectName("titleLabel")
        
        self.author_label = QLabel()
        self.author_label.setObjectName("authorLabel")
        
        self.category_label = QLabel()
        self.category_label.setObjectName("categoryLabel")
        
        self.id_label = QLabel()
        self.id_label.setObjectName("idLabel")
        
        self.chapters_label = QLabel()
        self.chapters_label.setObjectName("chaptersLabel")
        
        # 操作按钮 (固定高度 40px)
        buttons_layout = QHBoxLayout()
        
        self.read_button = QPushButton("阅读")
        self.read_button.setFixedHeight(40)
        self.read_button.setEnabled(False)
        self.read_button.setObjectName("actionButton")  # 添加对象名
        self.read_button.clicked.connect(self._on_read_clicked)
        
        self.download_button = QPushButton("下载")
        self.download_button.setFixedHeight(40)
        self.download_button.setEnabled(False)
        self.download_button.setObjectName("actionButton")  # 添加对象名
        self.download_button.clicked.connect(self._on_download_clicked)
        
        self.queue_button = QPushButton("加入队列")
        self.queue_button.setFixedHeight(40)
        self.queue_button.setEnabled(False)
        self.queue_button.setObjectName("actionButton")  # 添加对象名
        self.queue_button.clicked.connect(self._on_queue_clicked)
        
        buttons_layout.addWidget(self.read_button)
        buttons_layout.addWidget(self.download_button)
        buttons_layout.addWidget(self.queue_button)
        
        details_layout.addWidget(self.cover_label, 0, Qt.AlignHCenter)
        details_layout.addWidget(self.title_label)
        details_layout.addWidget(self.author_label)
        details_layout.addWidget(self.category_label)
        details_layout.addWidget(self.id_label)
        details_layout.addWidget(self.chapters_label)
        details_layout.addLayout(buttons_layout)
        details_layout.addStretch()
        
        layout.addWidget(self.details_placeholder)
        layout.addWidget(self.details_content)
        
        return panel
    
    def _setup_worker_thread(self):
        """设置渐进式搜索工作线程"""
        self._worker_thread = QThread()
        self._worker = ProgressiveKaobeiSearchWorker(self.adapter)
        self._worker.moveToThread(self._worker_thread)
        
        # 连接信号
        self._worker.batch_ready.connect(self._on_batch_ready)
        self._worker.search_completed.connect(self._on_search_completed)
        self._worker.search_failed.connect(self._on_search_failed)
        self._worker.details_completed.connect(self._on_details_completed)
        self._worker.details_failed.connect(self._on_details_failed)
        
        # 启动线程
        self._worker_thread.start()
    
    # 事件处理
    def _on_search_clicked(self):
        """处理搜索点击"""
        keyword = self.search_bar.text().strip()
        if not keyword:
            QMessageBox.warning(self, "提示", "请输入搜索关键词")
            return
        
        self.current_keyword = keyword
        self.current_page = 1
        self._search_comics(keyword, 1)
    
    def _search_comics(self, keyword: str, page: int):
        """执行搜索 - 与原始页面逻辑保持一致"""
        self.status_label.setText("搜索中...")
        self.search_button.setEnabled(False)
        self.prev_button.setEnabled(False)
        self.next_button.setEnabled(False)
        
        # 清空当前结果
        self._clear_results()
        self.search_results.clear()  # 重置搜索结果列表
        
        # 发送搜索请求到工作线程
        QTimer.singleShot(0, lambda: self._worker.search_comics(keyword, page))
    
    def _stop_all_activities(self):
        """停止所有当前活动"""
        # 停止卡片渲染定时器
        if self._is_rendering_cards:
            self._stop_card_rendering()
        
        # 清空待渲染卡片
        self._pending_comics.clear()
        
        # 清理图片加载队列
        if self._image_manager:
            self._image_manager.clear_queue()
    
    @Slot(list)
    def _on_batch_ready(self, comics: List[Comic]):
        """处理批次数据就绪 - 直接添加到渲染队列"""
        # 将批次漫画添加到待渲染队列
        self._pending_comics.extend(comics)
        self.search_results.extend(comics)
        
        # 如果还没开始渲染，开始渲染
        if not self._is_rendering_cards and self._pending_comics:
            self._start_card_rendering()
    
    @Slot(int)
    def _on_search_completed(self, max_page: int):
        """处理搜索完成"""
        self.max_page = max_page
        
        # 更新搜索结果标题 - 遵循jmcomic标准格式
        total_results = len(self.search_results)
        self.results_label.setText(f"搜索结果 ({total_results} 个)")
        self.status_label.setText(f"找到 {total_results} 个结果")
        self.search_button.setEnabled(True)
        
        # 更新分页控件
        self.page_label.setText(f"第 {self.current_page} 页 / 共 {max_page} 页")
        self.prev_button.setEnabled(self.current_page > 1)
        self.next_button.setEnabled(self.current_page < max_page)
    
    @Slot(str)
    def _on_search_failed(self, error: str):
        """处理搜索失败"""
        self.status_label.setText(f"搜索失败: {error}")
        self.search_button.setEnabled(True)
        self.prev_button.setEnabled(False)
        self.next_button.setEnabled(False)
        
        QMessageBox.warning(self, "搜索失败", f"搜索失败:\n{error}")
    
    def _start_card_rendering(self):
        """开始逐个渲染卡片"""
        if self._is_rendering_cards:
            return
        
        self._is_rendering_cards = True
        self._card_render_timer.start(self._card_render_interval)
    
    def _render_next_card(self):
        """渲染下一个卡片"""
        if not self._pending_comics:
            # 渲染完成
            self._stop_card_rendering()
            return
        
        # 渲染一个卡片
        comic = self._pending_comics.pop(0)
        card = self._create_result_card(comic)
        
        # 插入到布局中（在stretch之前）
        insert_index = max(0, self.results_layout.count() - 1)
        self.results_layout.insertWidget(insert_index, card)
        
        # 更新显示计数 - 移除，因为已在搜索完成时统一更新标题
        
        # 确保有stretch
        if self.results_layout.count() == 0 or not self.results_layout.itemAt(self.results_layout.count() - 1).spacerItem():
            self.results_layout.addStretch()
    
    def _stop_card_rendering(self):
        """停止卡片渲染"""
        if not self._is_rendering_cards:
            return
        
        self._is_rendering_cards = False
        self._card_render_timer.stop()
        
        # 最后触发一次可见图片加载
        QTimer.singleShot(100, self._load_visible_images)
    
    def _create_result_card(self, comic: Comic) -> QWidget:
        """创建结果卡片"""
        card = QFrame()
        card.setFixedHeight(80)
        card.setCursor(Qt.PointingHandCursor)
        card.setObjectName("resultCard")
        
        # 存储漫画对象
        card.comic = comic
        
        layout = QHBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # 缩略图
        thumb = QLabel()
        thumb.setFixedSize(45, 60)
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setObjectName("thumbLabel")
        thumb.setText("加载中")
        
        # 延迟加载封面图片
        if comic.cover_url:
            self._image_manager.request_image(thumb, comic.cover_url, priority=1, lazy=True)
        
        # 信息区域
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(3)
        
        # 标题
        title = QLabel(comic.title)
        title.setMaximumHeight(36)
        title.setWordWrap(True)
        title.setObjectName("cardTitle")
        
        # 描述 - 初始显示为"获取章节信息中..."
        desc = QLabel("获取章节信息中...")
        desc.setObjectName("cardDescription")
        
        info_layout.addWidget(title)
        info_layout.addWidget(desc)
        info_layout.addStretch()
        
        layout.addWidget(thumb)
        layout.addWidget(info_widget, 1)
        
        # 点击事件
        card.mousePressEvent = lambda event: self._on_comic_selected(comic)
        
        return card
    
    def _on_comic_selected(self, comic: Comic):
        """处理漫画选择"""
        self.selected_comic = comic
        self.selected_comic_details = None
        
        # 显示基本信息
        self._show_comic_basic_info(comic)
        
        # 异步获取详细信息
        QTimer.singleShot(0, lambda: self._worker.get_comic_details(comic.id))
    
    def _show_comic_basic_info(self, comic: Comic):
        """显示漫画基本信息"""
        self.details_placeholder.setVisible(False)
        self.details_content.setVisible(True)
        
        # 更新基本信息
        self.title_label.setText(comic.title)
        self.author_label.setText(f"作者: {comic.author}")
        self.category_label.setText(f"分类: 拷贝漫画")
        self.id_label.setText(f"ID: {comic.id}")
        self.chapters_label.setText("获取章节信息中...")
        
        # 加载封面图片
        self.cover_label.setText("加载中...")
        if comic.cover_url:
            self._image_manager.request_image(self.cover_label, comic.cover_url, priority=0, lazy=False)
        
        # 暂时禁用按钮
        self.read_button.setEnabled(False)
        self.download_button.setEnabled(False)
        self.queue_button.setEnabled(False)
    
    @Slot(dict)
    def _on_details_completed(self, details: dict):
        """处理详情获取完成"""
        self.selected_comic_details = details
        
        # 更新详细信息
        authors = ', '.join(details.get('authors', ['未知']))
        self.author_label.setText(f"作者: {authors}")
        
        category = details.get('category', '拷贝漫画')
        self.category_label.setText(f"分类: {category}")
        
        chapters = details.get('chapters', [])
        self.chapters_label.setText(f"章节: {len(chapters)} 话")
        
        # 更新搜索结果卡片的章节信息
        self._update_comic_card_info(self.selected_comic, len(chapters))
        
        # 启用按钮
        if chapters:
            self.read_button.setEnabled(True)
            self.download_button.setEnabled(True)
            self.queue_button.setEnabled(True)
    
    @Slot(str)
    def _on_details_failed(self, error: str):
        """处理详情获取失败"""
        self.chapters_label.setText(f"获取详情失败: {error}")
    
    def _update_comic_card_info(self, comic: Comic, chapter_count: int):
        """更新搜索结果卡片的章节信息"""
        try:
            # 查找对应的卡片
            for i in range(self.results_layout.count() - 1):  # 排除底部弹簧
                item = self.results_layout.itemAt(i)
                if item and item.widget():
                    card = item.widget()
                    if hasattr(card, 'comic') and card.comic.id == comic.id:
                        # 找到对应的卡片，更新描述信息
                        info_widget = card.findChild(QWidget)
                        if info_widget:
                            layout = info_widget.layout()
                            if layout and layout.count() >= 2:
                                desc_label = layout.itemAt(1).widget()
                                if isinstance(desc_label, QLabel):
                                    desc_label.setText(f"共 {chapter_count} 话")
                        break
        except Exception as e:
            pass  # 静默处理错误
    
    def _on_image_loaded(self, label: QLabel, pixmap):
        """处理图片加载完成"""
        if pixmap and not pixmap.isNull():
            if label == self.cover_label:
                scaled = pixmap.scaled(200, 267, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            else:
                scaled = pixmap.scaled(45, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            label.setPixmap(scaled)
        else:
            label.setText("×")
    
    def _on_scroll_changed(self, value):
        """处理滚动事件"""
        if not hasattr(self, '_scroll_timer'):
            self._scroll_timer = QTimer()
            self._scroll_timer.setSingleShot(True)
            self._scroll_timer.timeout.connect(self._load_visible_images)
        
        self._scroll_timer.start(100)
    
    def _load_visible_images(self):
        """加载可见区域的图片"""
        if hasattr(self, 'results_scroll_area'):
            self._image_manager.force_load_visible(self.results_scroll_area)
    
    def _clear_results(self):
        """清空搜索结果"""
        while self.results_layout.count():
            child = self.results_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        self.search_results.clear()
        # 重置搜索结果标题
        self.results_label.setText("搜索结果")
    
    def _on_prev_page(self):
        """上一页"""
        if self.current_page > 1:
            self.current_page -= 1
            self._search_comics(self.current_keyword, self.current_page)
    
    def _on_next_page(self):
        """下一页"""
        if self.current_page < self.max_page:
            self.current_page += 1
            self._search_comics(self.current_keyword, self.current_page)
    
    def _on_read_clicked(self):
        """处理阅读按钮点击"""
        if not self.selected_comic or not self.selected_comic_details:
            return
        
        chapters = self.selected_comic_details.get('chapters', [])
        if not chapters:
            QMessageBox.warning(self, "提示", "没有可阅读的章节")
            return
        
        # 创建章节对象
        first_chapter_data = chapters[0]
        chapter = Chapter(
            id=first_chapter_data["chapter_id"],
            comic_id=self.selected_comic.id,
            title=first_chapter_data["title"],
            chapter_number=1,
            page_count=0,
            is_downloaded=False,
            download_path=None,
            source="kaobei"
        )
        
        # 发送阅读请求信号
        self.read_requested.emit(self.selected_comic, chapter)
    
    def _on_download_clicked(self):
        """处理下载按钮点击"""
        if not self.selected_comic or not self.selected_comic_details:
            return
        
        chapters = self.selected_comic_details.get('chapters', [])
        if not chapters:
            QMessageBox.warning(self, "提示", "没有可下载的章节")
            return
        
        # 创建章节对象列表
        chapter_objects = []
        for i, ch_data in enumerate(chapters):
            chapter = Chapter(
                id=ch_data["chapter_id"],
                comic_id=self.selected_comic.id,
                title=ch_data["title"],
                chapter_number=i + 1,  # 使用索引+1作为章节号
                page_count=0,
                is_downloaded=False,
                download_path=None,
                source="kaobei"
            )
            chapter_objects.append(chapter)
        
        # 发送下载请求信号
        self.download_requested.emit(self.selected_comic, chapter_objects)
    
    def _on_queue_clicked(self):
        """处理加入队列按钮点击"""
        if not self.selected_comic or not self.selected_comic_details:
            return
        
        chapters = self.selected_comic_details.get('chapters', [])
        if not chapters:
            QMessageBox.warning(self, "提示", "没有可下载的章节")
            return
        
        # 创建章节对象列表
        chapter_objects = []
        for i, ch_data in enumerate(chapters):
            chapter = Chapter(
                id=ch_data["chapter_id"],
                comic_id=self.selected_comic.id,
                title=ch_data["title"],
                chapter_number=i + 1,  # 使用索引+1作为章节号
                page_count=0,
                is_downloaded=False,
                download_path=None,
                source="kaobei"
            )
            chapter_objects.append(chapter)
        
        # 发送队列请求信号
        self.queue_requested.emit(self.selected_comic, chapter_objects)
    
    def showEvent(self, event):
        """页面显示事件"""
        super().showEvent(event)
    
    def hideEvent(self, event):
        """页面隐藏事件 - 停止所有活动"""
        self._stop_all_activities()
        super().hideEvent(event)
    
    def closeEvent(self, event):
        """页面关闭事件 - 清理资源"""
        self.cleanup()
        super().closeEvent(event)
    
    def cleanup(self):
        """页面销毁时清理资源 - 防止内存泄漏"""
        try:
            # 停止所有活动
            self._stop_all_activities()
            
            # 停止工作线程
            if hasattr(self, '_worker_thread') and self._worker_thread and self._worker_thread.isRunning():
                # 先断开信号连接，防止清理过程中触发信号
                if hasattr(self, '_worker') and self._worker:
                    self._worker.batch_ready.disconnect()
                    self._worker.search_completed.disconnect()
                    self._worker.search_failed.disconnect()
                    self._worker.details_completed.disconnect()
                    self._worker.details_failed.disconnect()
                
                self._worker_thread.quit()
                if not self._worker_thread.wait(3000):  # 等待最多3秒
                    self._worker_thread.terminate()
                    self._worker_thread.wait(1000)  # 再等1秒
        except Exception as e:
            print(f"[ERROR] Error stopping worker thread: {e}")
        
        try:
            # 清理图片管理器
            if hasattr(self, '_image_manager') and self._image_manager:
                self._image_manager.cleanup()
        except Exception as e:
            print(f"[ERROR] Error cleaning up image manager: {e}")
        
        try:
            # 清理其他资源
            self._clear_results()
        except Exception as e:
            print(f"[ERROR] Error clearing results: {e}")
    
    def apply_theme(self, theme: str):
        """应用主题 - 遵循jmcomic标准"""
        self._current_theme = theme
        
        if theme == 'light':
            # 浅色主题配色
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
            # 深色主题配色
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
        
        # 应用样式
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_primary};
                color: {text_primary};
            }}
            
            QLineEdit {{
                background-color: {bg_primary};
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 8px 12px;
                color: {text_primary};
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
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: #1084d8;
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
            
            #thumbLabel {{
                background-color: {bg_secondary};
                border: 1px solid {border_color};
                border-radius: 4px;
                color: {text_muted};
            }}
            
            #cardTitle {{
                color: {text_primary};
                font-weight: bold;
            }}
            
            #cardDescription {{
                color: {text_muted};
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