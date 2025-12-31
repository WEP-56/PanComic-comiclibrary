"""
优化的拷贝漫画页面 - 使用简化的渐进式渲染避免UI卡顿

主要优化：
1. 使用简单的工作线程避免异步事件循环问题
2. 逐个渲染卡片，消除瞬间卡顿
3. 智能图片加载管理
4. 保持与原始页面相同的搜索逻辑
"""

import uuid
import time
from typing import Optional, List, Dict
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, 
    QLabel, QPushButton, QScrollArea, QFrame, QLineEdit, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QThread, QObject, Slot, QTimer, QRect
from PySide6.QtGui import QCursor

from pancomic.adapters.kaobei_adapter import KaobeiAdapter
from pancomic.models.comic import Comic
from pancomic.models.chapter import Chapter
from pancomic.infrastructure.download_manager import DownloadManager
from pancomic.ui.widgets.image_load_manager import ImageLoadManager


class SimpleKaobeiSearchWorker(QObject):
    """简化的拷贝漫画搜索工作线程 - 避免异步事件循环问题"""
    
    search_completed = Signal(list, int)  # comics, max_page
    search_failed = Signal(str)  # error_message
    details_completed = Signal(dict)  # comic_details
    details_failed = Signal(str)  # error_message
    
    def __init__(self, adapter: KaobeiAdapter):
        super().__init__()
        self.adapter = adapter
    
    @Slot(str, int)
    def search_comics(self, keyword: str, page: int):
        """在工作线程中执行搜索 - 使用同步方式避免事件循环问题"""
        try:
            result = self.adapter.search(keyword, page)
            # 转换为 Comic 对象
            comics = []
            for data in result["comics"]:
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
                comics.append(comic)
            
            self.search_completed.emit(comics, result["max_page"])
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
    优化的拷贝漫画页面 - 简化的渐进式渲染
    
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
        self._card_render_interval = 16  # 16ms = ~60fps
        self._cards_per_frame = 1  # 每帧渲染1个卡片
        
        # 工作线程 - 使用简化版本
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
        
        # 结果标题
        header_layout = QHBoxLayout()
        
        self.results_label = QLabel("搜索结果")
        self.results_label.setObjectName("resultsLabel")
        
        self.results_count_label = QLabel("")
        self.results_count_label.setObjectName("resultsCountLabel")
        
        header_layout.addWidget(self.results_label)
        header_layout.addStretch()
        header_layout.addWidget(self.results_count_label)
        
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
        pagination_layout = QHBoxLayout()
        
        self.prev_button = QPushButton("上一页")
        self.prev_button.setFixedHeight(35)
        self.prev_button.setEnabled(False)
        self.prev_button.clicked.connect(self._on_prev_page)
        
        self.page_label = QLabel("第 1 页")
        self.page_label.setAlignment(Qt.AlignCenter)
        self.page_label.setObjectName("pageLabel")
        
        self.next_button = QPushButton("下一页")
        self.next_button.setFixedHeight(35)
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
        self.read_button.clicked.connect(self._on_read_clicked)
        
        self.download_button = QPushButton("下载")
        self.download_button.setFixedHeight(40)
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self._on_download_clicked)
        
        self.queue_button = QPushButton("加入队列")
        self.queue_button.setFixedHeight(40)
        self.queue_button.setEnabled(False)
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
        """设置简化的搜索工作线程"""
        self._worker_thread = QThread()
        self._worker = SimpleKaobeiSearchWorker(self.adapter)
        self._worker.moveToThread(self._worker_thread)
        
        # 连接信号
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
        
        # 停止所有当前活动
        self._stop_all_activities()
        
        # 开始新搜索
        self._current_keyword = keyword
        self._current_page = 1
        self._current_task_id = str(uuid.uuid4())
        
        # 重置状态
        self._clear_results()
        self._reset_render_state()
        self._search_start_time = time.time()
        
        # 更新UI状态
        self.status_label.setText("搜索中...")
        self.search_button.setEnabled(False)
        
        # 发送搜索请求
        self._progressive_worker.start_progressive_search(keyword, self._current_page, self._current_task_id)
    
    def _stop_all_activities(self):
        """停止所有当前活动"""
        # 1. 取消当前搜索任务
        if self._current_task_id:
            self._progressive_worker.cancel_search(self._current_task_id)
            self._current_task_id = None
        
        # 2. 停止渲染定时器
        if self._render_timer.isActive():
            self._render_timer.stop()
        
        # 3. 停止卡片渲染定时器
        if self._is_rendering_cards:
            self._stop_card_rendering()
        
        # 4. 停止滚动定时器
        if hasattr(self, '_scroll_timer') and self._scroll_timer.isActive():
            self._scroll_timer.stop()
        
        # 5. 清空待处理批次和卡片
        self._pending_batches.clear()
        self._pending_comics.clear()
        
        # 6. 清理图片加载队列
        if self._image_manager:
            self._image_manager.clear_queue()
    
    def _reset_render_state(self):
        """重置渲染状态"""
        self._rendered_count = 0
        self._total_expected = 0
        self._pending_batches.clear()
        self._pending_comics.clear()
        self._render_times.clear()
        self._is_rendering_cards = False
    
    @Slot(object)
    def _on_batch_ready(self, batch: ComicBatch):
        """处理批次数据就绪"""
        # 检查任务是否仍然有效
        if batch.task_id != self._current_task_id:
            print(f"[DEBUG] 忽略过期批次: {batch.task_id} (当前: {self._current_task_id})")
            return
        
        print(f"[DEBUG] 接收到批次 {batch.batch_index + 1}/{batch.total_batches}: {len(batch.comics)} 个漫画")
        
        # 添加到待处理队列
        self._pending_batches.append(batch)
        
        # 启动渲染定时器（防抖）
        if not self._render_timer.isActive():
            self._render_timer.start(50)  # 50ms后处理
    
    def _process_pending_batches(self):
        """处理待渲染的批次 - 添加到逐个渲染队列"""
        if not self._pending_batches:
            return
        
        # 再次检查任务有效性
        valid_batches = []
        for batch in self._pending_batches:
            if batch.task_id == self._current_task_id:
                valid_batches.append(batch)
            else:
                print(f"[WARN] 丢弃过期批次: {batch.task_id}")
        
        if not valid_batches:
            self._pending_batches.clear()
            return
        
        batch_start = time.time()
        
        # 将所有批次的漫画添加到逐个渲染队列
        new_comics = []
        for batch in valid_batches:
            new_comics.extend(batch.comics)
            self._all_comics.extend(batch.comics)
        
        # 添加到待渲染队列
        self._pending_comics.extend(new_comics)
        
        batch_time = time.time() - batch_start
        self._render_times.append(batch_time)
        
        total_added = len(new_comics)
        print(f"[INFO] 批次处理完成: {total_added} 个漫画添加到渲染队列, 耗时: {batch_time:.3f}s")
        
        # 清空待处理批次
        self._pending_batches.clear()
        
        # 开始逐个渲染（如果还没在渲染）
        if not self._is_rendering_cards and self._pending_comics:
            self._start_card_rendering()
    
    def _start_card_rendering(self):
        """开始逐个渲染卡片"""
        if self._is_rendering_cards:
            return
        
        self._is_rendering_cards = True
        print(f"[INFO] 开始逐个渲染: {len(self._pending_comics)} 个卡片待渲染")
        
        # 启动渲染定时器
        self._card_render_timer.start(self._card_render_interval)
    
    def _render_next_card(self):
        """渲染下一个或几个卡片"""
        if not self._pending_comics:
            # 渲染完成
            self._stop_card_rendering()
            return
        
        # 检查任务是否仍然有效
        if not self._current_task_id:
            print("[WARN] 任务已取消，停止卡片渲染")
            self._stop_card_rendering()
            return
        
        # 渲染一个或多个卡片（根据配置）
        cards_to_render = min(self._cards_per_frame, len(self._pending_comics))
        
        for _ in range(cards_to_render):
            if not self._pending_comics:
                break
                
            comic = self._pending_comics.pop(0)
            card = self._create_result_card(comic)
            
            # 插入到布局中（在stretch之前）
            insert_index = max(0, self.results_layout.count() - 1)
            self.results_layout.insertWidget(insert_index, card)
            
            # 更新计数
            self._rendered_count += 1
        
        # 更新显示计数
        self.results_count_label.setText(f"已显示 {self._rendered_count} 个结果")
        
        # 确保有stretch
        if self.results_layout.count() == 0 or not self.results_layout.itemAt(self.results_layout.count() - 1).spacerItem():
            self.results_layout.addStretch()
        
        # 每渲染N个卡片后触发一次可见图片加载
        if self._rendered_count % self._render_batch_trigger == 0:
            QTimer.singleShot(50, self._load_visible_images)
    
    def set_render_speed(self, speed: str):
        """设置渲染速度
        
        Args:
            speed: 'slow' (慢速), 'normal' (正常), 'fast' (快速)
        """
        if speed == 'slow':
            self._card_render_interval = 33  # 30fps
            self._cards_per_frame = 1
            self._render_batch_trigger = 3
        elif speed == 'normal':
            self._card_render_interval = 16  # 60fps
            self._cards_per_frame = 1
            self._render_batch_trigger = 5
        elif speed == 'fast':
            self._card_render_interval = 8   # 120fps
            self._cards_per_frame = 2
            self._render_batch_trigger = 8
        
        print(f"[INFO] 渲染速度设置为: {speed} (间隔: {self._card_render_interval}ms, 每帧: {self._cards_per_frame}个)")
    
    def _stop_card_rendering(self):
        """停止卡片渲染"""
        if not self._is_rendering_cards:
            return
        
        self._is_rendering_cards = False
        self._card_render_timer.stop()
        
        remaining = len(self._pending_comics)
        if remaining > 0:
            print(f"[INFO] 卡片渲染停止，剩余 {remaining} 个待渲染")
        else:
            print(f"[INFO] 卡片渲染完成，总共渲染 {self._rendered_count} 个")
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
    
    @Slot(str, int)
    def _on_search_completed(self, task_id: str, max_page: int):
        """处理搜索完成"""
        if task_id != self._current_task_id:
            return
        
        # 更新UI (但不立即重置任务ID，等待批次处理完成)
        self.status_label.setText(f"找到 {len(self._all_comics)} 个结果")
        self.search_button.setEnabled(True)
        
        # 更新分页
        self.page_label.setText(f"第 {self._current_page} 页 / 共 {max_page} 页")
        self.prev_button.setEnabled(self._current_page > 1)
        self.next_button.setEnabled(self._current_page < max_page)
        
        # 延迟重置任务ID，给批次处理留出时间
        QTimer.singleShot(1000, self._delayed_reset_task_id)
    
    @Slot(str, str)
    def _on_search_failed(self, task_id: str, error_message: str):
        """处理搜索失败"""
        if task_id != self._current_task_id:
            return
        
        # 停止所有相关活动
        self._stop_all_activities()
        
        # 更新UI
        self.status_label.setText(f"搜索失败: {error_message}")
        self._reset_search_ui()
    
    def _delayed_reset_task_id(self):
        """延迟重置任务ID"""
        self._current_task_id = None
    
    def _reset_search_ui(self):
        """重置搜索UI状态"""
        self.search_button.setEnabled(True)
    
    def _on_comic_selected(self, comic: Comic):
        """处理漫画选择"""
        self._selected_comic = comic
        self._selected_comic_details = None
        
        # 显示基本信息
        self._show_comic_basic_info(comic)
        
        # 异步获取详细信息
        QTimer.singleShot(0, lambda: self._get_comic_details(comic.id))
    
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
    
    def _get_comic_details(self, comic_id: str):
        """获取漫画详情"""
        try:
            details = self.adapter.get_comic_details(comic_id)
            self._on_details_completed(details)
        except Exception as e:
            self._on_details_failed(str(e))
    
    def _on_details_completed(self, details: dict):
        """处理详情获取完成"""
        self._selected_comic_details = details
        
        # 更新详细信息
        authors = ', '.join(details.get('authors', ['未知']))
        self.author_label.setText(f"作者: {authors}")
        
        category = details.get('category', '拷贝漫画')
        self.category_label.setText(f"分类: {category}")
        
        chapters = details.get('chapters', [])
        self.chapters_label.setText(f"章节: {len(chapters)} 话")
        
        # 更新搜索结果卡片的章节信息
        self._update_comic_card_info(self._selected_comic, len(chapters))
        
        # 启用按钮
        if chapters:
            self.read_button.setEnabled(True)
            self.download_button.setEnabled(True)
            self.queue_button.setEnabled(True)
    
    def _on_details_failed(self, error: str):
        """处理详情获取失败"""
        self.chapters_label.setText(f"获取详情失败: {error}")
        print(f"[ERROR] Failed to get comic details: {error}")
    
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
            print(f"[WARN] Failed to update card info: {e}")
    
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
        
        self._all_comics.clear()
        self._rendered_count = 0
        self.results_count_label.setText("")
    
    def _on_prev_page(self):
        """上一页"""
        if self._current_page > 1:
            self._current_page -= 1
            self._on_search_clicked()
    
    def _on_next_page(self):
        """下一页"""
        self._current_page += 1
        self._on_search_clicked()
    
    def _on_read_clicked(self):
        """处理阅读按钮点击"""
        if not self._selected_comic or not self._selected_comic_details:
            return
        
        chapters = self._selected_comic_details.get('chapters', [])
        if not chapters:
            QMessageBox.warning(self, "提示", "没有可阅读的章节")
            return
        
        # 创建章节对象
        first_chapter_data = chapters[0]
        chapter = Chapter(
            id=first_chapter_data["chapter_id"],
            comic_id=self._selected_comic.id,
            title=first_chapter_data["title"],
            chapter_number=1,
            page_count=0,
            is_downloaded=False,
            download_path=None,
            source="kaobei"
        )
        
        # 发送阅读请求信号
        self.read_requested.emit(self._selected_comic, chapter)
    
    def _on_download_clicked(self):
        """处理下载按钮点击"""
        if not self._selected_comic or not self._selected_comic_details:
            return
        
        chapters = self._selected_comic_details.get('chapters', [])
        if not chapters:
            QMessageBox.warning(self, "提示", "没有可下载的章节")
            return
        
        # 创建章节对象列表
        chapter_objects = []
        for i, ch_data in enumerate(chapters):
            chapter = Chapter(
                id=ch_data["chapter_id"],
                comic_id=self._selected_comic.id,
                title=ch_data["title"],
                chapter_number=i + 1,  # 使用索引+1作为章节号
                page_count=0,
                is_downloaded=False,
                download_path=None,
                source="kaobei"
            )
            chapter_objects.append(chapter)
        
        # 发送下载请求信号
        self.download_requested.emit(self._selected_comic, chapter_objects)
    
    def _on_queue_clicked(self):
        """处理加入队列按钮点击"""
        if not self._selected_comic or not self._selected_comic_details:
            return
        
        chapters = self._selected_comic_details.get('chapters', [])
        if not chapters:
            QMessageBox.warning(self, "提示", "没有可下载的章节")
            return
        
        # 创建章节对象列表
        chapter_objects = []
        for i, ch_data in enumerate(chapters):
            chapter = Chapter(
                id=ch_data["chapter_id"],
                comic_id=self._selected_comic.id,
                title=ch_data["title"],
                chapter_number=i + 1,  # 使用索引+1作为章节号
                page_count=0,
                is_downloaded=False,
                download_path=None,
                source="kaobei"
            )
            chapter_objects.append(chapter)
        
        # 发送队列请求信号
        self.queue_requested.emit(self._selected_comic, chapter_objects)
    
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
                if hasattr(self, '_progressive_worker') and self._progressive_worker:
                    self._progressive_worker.batch_ready.disconnect()
                    self._progressive_worker.search_completed.disconnect()
                    self._progressive_worker.search_failed.disconnect()
                
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
        """应用主题"""
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
            card_bg = '#FFFFFF'
            card_hover = '#F0F0F0'
        else:
            # 深色主题配色
            bg_primary = '#1e1e1e'
            bg_secondary = '#2b2b2b'
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
            
            #resultCard {{
                background-color: {card_bg};
                border: 1px solid {border_color};
                border-radius: 6px;
            }}
            #resultCard:hover {{
                background-color: {card_hover};
                border-color: {accent_color};
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