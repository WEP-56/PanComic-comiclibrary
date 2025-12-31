# pancomic/ui/pages/kaobei_page.py
"""
拷贝漫画 (Kaobei) 页面
遵循 PanComic 集成指南的分割式布局规范
"""
import sys
import os
from typing import Optional, List
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel, QLineEdit, 
    QPushButton, QScrollArea, QFrame, QMessageBox, QProgressBar
)
from PySide6.QtCore import Qt, Signal, QThread, QObject, Slot, QTimer
from PySide6.QtGui import QPixmap, QFont, QCursor

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from pancomic.adapters.kaobei_adapter import KaobeiAdapter
from pancomic.infrastructure.download_manager import DownloadManager
from pancomic.models.comic import Comic
from pancomic.models.chapter import Chapter
from pancomic.ui.widgets.image_load_manager import ImageLoadManager


class KaobeiSearchWorker(QObject):
    """拷贝漫画搜索工作线程"""
    
    search_completed = Signal(list, int)  # comics, max_page
    search_failed = Signal(str)  # error_message
    details_completed = Signal(dict)  # comic_details
    details_failed = Signal(str)  # error_message
    
    def __init__(self, adapter: KaobeiAdapter):
        super().__init__()
        self.adapter = adapter
    
    @Slot(str, int)
    def search_comics(self, keyword: str, page: int):
        """在工作线程中执行搜索"""
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


class KaobeiPage(QWidget):
    """拷贝漫画页面 - 遵循分割式布局规范"""
    
    # 信号定义
    read_requested = Signal(object, object)      # Comic, Chapter
    download_requested = Signal(object, list)   # Comic, List[Chapter]
    queue_requested = Signal(object, list)      # Comic, List[Chapter]
    settings_requested = Signal()               # 打开设置页面
    
    def __init__(self, adapter: KaobeiAdapter, download_manager: DownloadManager, parent=None):
        super().__init__(parent)
        
        # 核心组件
        self.adapter = adapter
        self.download_manager = download_manager
        
        # 状态变量
        self.current_page = 1
        self.max_page = 1
        self.current_keyword = ""
        self.search_results = []
        self.selected_comic = None
        self.selected_comic_details = None
        
        # 异步工作线程
        self._worker_thread = None
        self._worker = None
        
        # 图片加载管理器 (使用简化版本避免卡顿)
        self._image_manager = ImageLoadManager(max_concurrent=1)
        
        # 设置UI和工作线程
        self._setup_ui()
        self._setup_worker_thread()
    
    def _setup_ui(self):
        """设置UI界面 - 分割式布局"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 1. 顶部搜索栏 (固定高度 60px)
        search_container = self._create_search_bar()
        layout.addWidget(search_container)
        
        # 2. 主体分割区域 (左右分割，比例 5:3)
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧面板：搜索结果列表 + 分页控件
        left_panel = self._create_results_panel()
        splitter.addWidget(left_panel)
        
        # 右侧面板：漫画详情 + 操作按钮
        right_panel = self._create_details_panel()
        splitter.addWidget(right_panel)
        
        # 设置分割比例 5:3 (62.5% : 37.5%)
        splitter.setSizes([625, 375])
        
        layout.addWidget(splitter)
        
        # 应用样式
        self._apply_styles()
    
    def _create_search_bar(self) -> QWidget:
        """创建搜索栏组件 (固定高度 60px)"""
        search_container = QWidget()
        search_container.setFixedHeight(60)
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
        
        # 4. 状态标签
        self.status_label = QLabel("输入关键词开始搜索")
        self.status_label.setObjectName("statusLabel")
        
        layout.addWidget(self.search_bar)      # 自适应
        layout.addWidget(self.search_button)   # 80px
        layout.addWidget(settings_btn)         # 60px  
        layout.addWidget(self.status_label)    # 自适应
        
        return search_container
    
    def _create_results_panel(self) -> QWidget:
        """创建左侧搜索结果面板"""
        panel = QWidget()
        panel.setObjectName("resultsPanel")
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 结果标题
        self.results_label = QLabel("搜索结果")
        self.results_label.setObjectName("resultsLabel")
        
        # 滚动区域 - 显示漫画卡片
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setContentsMargins(5, 5, 5, 5)
        self.results_layout.setSpacing(5)
        self.results_layout.addStretch()  # 底部弹簧
        
        scroll.setWidget(self.results_container)
        
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
        
        layout.addWidget(self.results_label)
        layout.addWidget(scroll)
        layout.addLayout(pagination_layout)
        
        return panel
    
    def _create_details_panel(self) -> QWidget:
        """创建右侧详情面板"""
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
        """设置异步工作线程"""
        self._worker_thread = QThread()
        self._worker = KaobeiSearchWorker(self.adapter)
        self._worker.moveToThread(self._worker_thread)
        
        # 连接信号
        self._worker.search_completed.connect(self._on_search_completed)
        self._worker.search_failed.connect(self._on_search_failed)
        self._worker.details_completed.connect(self._on_details_completed)
        self._worker.details_failed.connect(self._on_details_failed)
        
        self._worker_thread.start()
    
    def _on_search_clicked(self):
        """处理搜索按钮点击"""
        keyword = self.search_bar.text().strip()
        if not keyword:
            QMessageBox.warning(self, "提示", "请输入搜索关键词")
            return
        
        self.current_keyword = keyword
        self.current_page = 1
        self._search_comics(keyword, 1)
    
    def _search_comics(self, keyword: str, page: int):
        """执行搜索"""
        self.status_label.setText("搜索中...")
        self.search_button.setEnabled(False)
        self.prev_button.setEnabled(False)
        self.next_button.setEnabled(False)
        
        # 清空当前结果
        self._clear_results()
        
        # 发送搜索请求到工作线程
        QTimer.singleShot(0, lambda: self._worker.search_comics(keyword, page))
    
    @Slot(list, int)
    def _on_search_completed(self, comics: List[Comic], max_page: int):
        """处理搜索完成"""
        self.search_results = comics
        self.max_page = max_page
        
        self.status_label.setText(f"找到 {len(comics)} 个结果")
        self.search_button.setEnabled(True)
        
        # 更新分页控件
        self.page_label.setText(f"第 {self.current_page} 页 / 共 {max_page} 页")
        self.prev_button.setEnabled(self.current_page > 1)
        self.next_button.setEnabled(self.current_page < max_page)
        
        # 显示结果
        self._display_results(comics)
    
    @Slot(str)
    def _on_search_failed(self, error: str):
        """处理搜索失败"""
        self.status_label.setText(f"搜索失败: {error}")
        self.search_button.setEnabled(True)
        self.prev_button.setEnabled(False)
        self.next_button.setEnabled(False)
        
        QMessageBox.warning(self, "搜索失败", f"搜索失败:\n{error}")
    
    def _display_results(self, comics: List[Comic]):
        """显示搜索结果"""
        # 清空现有结果
        self._clear_results()
        
        if not comics:
            no_results = QLabel("没有找到相关漫画")
            no_results.setAlignment(Qt.AlignCenter)
            no_results.setObjectName("noResultsLabel")
            self.results_layout.insertWidget(0, no_results)
            return
        
        # 创建漫画卡片
        for comic in comics:
            card = self._create_result_card(comic)
            self.results_layout.insertWidget(self.results_layout.count() - 1, card)
    
    def _create_result_card(self, comic: Comic) -> QWidget:
        """创建漫画卡片 (固定高度 80px)"""
        card = QFrame()
        card.setFixedHeight(80)
        card.setCursor(QCursor(Qt.PointingHandCursor))
        card.setObjectName("resultCard")
        
        # 存储漫画对象
        card.comic = comic
        
        layout = QHBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # 缩略图 (固定尺寸 45x60)
        thumb = QLabel()
        thumb.setFixedSize(45, 60)
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setObjectName("thumbLabel")
        thumb.setText("加载中")
        
        # 立即加载封面图片
        if comic.cover_url:
            self._image_manager.request_image(thumb, comic.cover_url, priority=1, lazy=False)
        
        # 信息区域
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(5)
        
        # 标题 (最大高度 36px, 支持2行)
        title = QLabel(comic.title)
        title.setMaximumHeight(36)
        title.setWordWrap(True)
        title.setObjectName("cardTitle")
        
        # 描述 (单行)
        description = QLabel(comic.description or "暂无描述")
        description.setObjectName("cardDescription")
        
        info_layout.addWidget(title)
        info_layout.addWidget(description)
        info_layout.addStretch()
        
        layout.addWidget(thumb)
        layout.addWidget(info_widget, 1)
        
        # 点击事件
        card.mousePressEvent = lambda event: self._on_card_clicked(comic)
        
        return card
    
    def _on_card_clicked(self, comic: Comic):
        """处理卡片点击"""
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
    
    def _clear_results(self):
        """清空搜索结果"""
        # 清空结果布局
        while self.results_layout.count() > 1:  # 保留底部弹簧
            child = self.results_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
    
    def _apply_styles(self):
        """应用样式"""
        self.setStyleSheet("""
            /* 搜索容器 */
            #searchContainer {
                background-color: #2b2b2b;
                border-bottom: 1px solid #3a3a3a;
            }
            
            /* 搜索输入框 */
            QLineEdit {
                padding: 8px 12px;
                background-color: #3a3a3a;
                border: 1px solid #4a4a4a;
                border-radius: 6px;
                color: white;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
            
            /* 按钮样式 */
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1084d8;
            }
            QPushButton:pressed {
                background-color: #006cbd;
            }
            QPushButton:disabled {
                background-color: #4a5568;
                color: #a0aec0;
            }
            
            /* 状态标签 */
            #statusLabel {
                color: #888888;
                font-size: 13px;
                margin-left: 20px;
            }
            
            /* 结果面板 */
            #resultsPanel {
                background-color: #1e1e1e;
                border-right: 1px solid #3a3a3a;
            }
            
            #resultsLabel {
                color: white;
                font-size: 16px;
                font-weight: bold;
                margin-bottom: 10px;
            }
            
            /* 漫画卡片 */
            #resultCard {
                background-color: #2d2d2d;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin: 2px 0;
            }
            #resultCard:hover {
                background-color: #3a3a3a;
                border-color: #4a4a4a;
            }
            
            #thumbLabel {
                background-color: #3a3a3a;
                border: 1px solid #4a4a4a;
                border-radius: 4px;
                color: #888888;
                font-size: 12px;
            }
            
            #cardTitle {
                color: white;
                font-weight: bold;
                font-size: 14px;
            }
            
            #cardDescription {
                color: #888888;
                font-size: 12px;
            }
            
            /* 分页标签 */
            #pageLabel {
                color: white;
                font-weight: bold;
                font-size: 14px;
            }
            
            /* 详情面板 */
            #detailsPanel {
                background-color: #252525;
            }
            
            #detailsPlaceholder {
                color: #888888;
                font-size: 16px;
                font-style: italic;
            }
            
            #coverLabel {
                background-color: #3a3a3a;
                border: 1px solid #4a4a4a;
                border-radius: 8px;
                color: #888888;
            }
            
            #titleLabel {
                color: white;
                font-size: 18px;
                font-weight: bold;
                margin: 10px 0;
            }
            
            #authorLabel, #categoryLabel, #idLabel, #chaptersLabel {
                color: #cccccc;
                font-size: 14px;
                margin: 5px 0;
            }
            
            /* 无结果标签 */
            #noResultsLabel {
                color: #888888;
                font-size: 16px;
                font-style: italic;
                margin: 50px 0;
            }
            
            /* 滚动条样式 */
            QScrollArea {
                border: none;
            }
            QScrollBar:vertical {
                background-color: #2d2d2d;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #4a4a4a;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #5a5a5a;
            }
        """)
    
    def apply_theme(self, theme: str):
        """应用主题到页面组件"""
        self._current_theme = theme
        
        if theme == 'light':
            # 浅色主题配色
            bg_primary = '#FFFFFF'
            bg_secondary = '#F5F5F5'
            bg_header = '#FAFAFA'
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
            bg_header = '#2b2b2b'
            text_primary = '#ffffff'
            text_secondary = '#cccccc'
            text_muted = '#888888'
            border_color = '#3a3a3a'
            accent_color = '#0078d4'
            card_bg = '#2d2d2d'
            card_hover = '#3a3a3a'
        
        # 应用主题样式
        self.setStyleSheet(f"""
            /* 搜索容器 */
            #searchContainer {{
                background-color: {bg_header};
                border-bottom: 1px solid {border_color};
            }}
            
            /* 搜索输入框 */
            QLineEdit {{
                padding: 8px 12px;
                background-color: {bg_primary};
                border: 1px solid {border_color};
                border-radius: 6px;
                color: {text_primary};
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border-color: {accent_color};
            }}
            
            /* 按钮样式 */
            QPushButton {{
                background-color: {accent_color};
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: #1084d8;
            }}
            QPushButton:pressed {{
                background-color: #006cbd;
            }}
            QPushButton:disabled {{
                background-color: #4a5568;
                color: #a0aec0;
            }}
            
            /* 状态标签 */
            #statusLabel {{
                color: {text_muted};
                font-size: 13px;
                margin-left: 20px;
            }}
            
            /* 结果面板 */
            #resultsPanel {{
                background-color: {bg_primary};
                border-right: 1px solid {border_color};
            }}
            
            #resultsLabel {{
                color: {text_primary};
                font-size: 16px;
                font-weight: bold;
                margin-bottom: 10px;
            }}
            
            /* 漫画卡片 */
            #resultCard {{
                background-color: {card_bg};
                border: 1px solid {border_color};
                border-radius: 8px;
                margin: 2px 0;
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
                font-size: 12px;
            }}
            
            #cardTitle {{
                color: {text_primary};
                font-weight: bold;
                font-size: 14px;
            }}
            
            #cardDescription {{
                color: {text_muted};
                font-size: 12px;
            }}
            
            /* 分页标签 */
            #pageLabel {{
                color: {text_primary};
                font-weight: bold;
                font-size: 14px;
            }}
            
            /* 详情面板 */
            #detailsPanel {{
                background-color: {bg_secondary};
            }}
            
            #detailsPlaceholder {{
                color: {text_muted};
                font-size: 16px;
                font-style: italic;
            }}
            
            #coverLabel {{
                background-color: {bg_secondary};
                border: 1px solid {border_color};
                border-radius: 8px;
                color: {text_muted};
            }}
            
            #titleLabel {{
                color: {text_primary};
                font-size: 18px;
                font-weight: bold;
                margin: 10px 0;
            }}
            
            #authorLabel, #categoryLabel, #idLabel, #chaptersLabel {{
                color: {text_secondary};
                font-size: 14px;
                margin: 5px 0;
            }}
            
            /* 无结果标签 */
            #noResultsLabel {{
                color: {text_muted};
                font-size: 16px;
                font-style: italic;
                margin: 50px 0;
            }}
            
            /* 滚动条样式 */
            QScrollArea {{
                border: none;
            }}
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
    
    def cleanup(self):
        """页面销毁时清理资源 - 防止内存泄漏"""
        print("[INFO] KaobeiPage cleanup started...")
        
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
        
        try:
            # 清理其他资源
            self._clear_results()
        except Exception as e:
            print(f"[ERROR] Error clearing results: {e}")
        
        print("[INFO] KaobeiPage cleanup completed")