"""PicACG source page with split layout."""

from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QPushButton, 
    QLabel, QLineEdit, QScrollArea, QFrame, QMessageBox, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap

from pancomic.adapters.picacg_adapter import PicACGAdapter
from pancomic.models.comic import Comic
from pancomic.models.chapter import Chapter
from pancomic.infrastructure.download_manager import DownloadManager

# Disable SSL warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class PicACGPage(QWidget):
    """
    PicACG source page with split layout.
    
    Left panel: Search results with pagination (12 per page)
    Right panel: Comic details with read/download buttons
    """
    
    # Signals
    read_requested = Signal(object, object)  # Comic, Chapter
    download_requested = Signal(object, list)  # Comic, List[Chapter]
    queue_requested = Signal(object, list)  # Comic, List[Chapter] - add to queue
    settings_requested = Signal()  # Request to navigate to settings
    
    def __init__(self, adapter: PicACGAdapter, download_manager: DownloadManager, parent: Optional[QWidget] = None):
        """
        Initialize PicACGPage.
        
        Args:
            adapter: PicACG adapter instance
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
        self._results_per_page = 12  # Same as JMComic
        self._all_comics = []
        self._selected_comic = None
        self._comic_chapters = []
        self._current_theme = 'dark'  # Track current theme
        
        # Initialize adapter if needed
        if not self.adapter.is_initialized():
            self.adapter.initialize()
        
        # Setup UI
        self._setup_ui()
        
        # Connect signals
        self._connect_signals()
        
        # Auto-login if enabled and credentials are stored
        self._check_auto_login()
    
    def _setup_ui(self) -> None:
        """Setup the split layout UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Search bar (same as JMComic)
        search_container = self._create_search_bar()
        layout.addWidget(search_container)
        
        # Split view: Left (results) | Right (details)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #3a3a3a;
            }
        """)
        
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
        """Create search bar widget."""
        self.search_container = QWidget()
        self.search_container.setFixedHeight(60)
        self.search_container.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                border-bottom: 1px solid #3a3a3a;
            }
        """)
        
        layout = QHBoxLayout(self.search_container)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(10)
        
        # Search input
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("搜索PicACG漫画...")
        self.search_bar.setFixedHeight(40)
        self.search_bar.returnPressed.connect(self._on_search_triggered)
        self.search_bar.setStyleSheet("""
            QLineEdit {
                background-color: #1e1e1e;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 0 15px;
                color: #ffffff;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #0078d4;
            }
        """)
        
        # Search button
        self.search_button = QPushButton("搜索")
        self.search_button.setFixedSize(80, 40)
        self.search_button.clicked.connect(self._on_search_triggered)
        self.search_button.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                border: none;
                border-radius: 8px;
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1084d8;
            }
            QPushButton:pressed {
                background-color: #006cbd;
            }
        """)
        
        # Settings button
        settings_btn = QPushButton("设置")
        settings_btn.setFixedSize(60, 40)
        settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
            QPushButton:pressed {
                background-color: #444444;
            }
        """)
        settings_btn.clicked.connect(self._navigate_to_settings)
        
        # Login status
        self.login_status = QLabel("未登录")
        self.login_status.setStyleSheet("color: #ff4444; font-weight: bold; margin-left: 20px;")
        
        layout.addWidget(self.search_bar)
        layout.addWidget(self.search_button)
        layout.addWidget(settings_btn)
        layout.addWidget(self.login_status)
        
        return self.search_container
    
    def _create_results_panel(self) -> QWidget:
        """Create left panel for search results."""
        self.results_panel = QWidget()
        self.results_panel.setStyleSheet("background-color: #1e1e1e;")
        
        layout = QVBoxLayout(self.results_panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Results header
        header_layout = QHBoxLayout()
        self.results_label = QLabel("搜索结果")
        self.results_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 16px;
                font-weight: bold;
            }
        """)
        header_layout.addWidget(self.results_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Results scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)
        
        # Results container
        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setSpacing(5)
        self.results_layout.addStretch()
        
        scroll.setWidget(self.results_container)
        layout.addWidget(scroll)
        
        # Pagination controls
        pagination_layout = QHBoxLayout()
        
        self.prev_button = QPushButton("上一页")
        self.prev_button.setFixedHeight(32)
        self.prev_button.clicked.connect(self._on_prev_page)
        self.prev_button.setEnabled(False)
        
        self.page_label = QLabel("第 1 页")
        self.page_label.setAlignment(Qt.AlignCenter)
        self.page_label.setStyleSheet("color: #ffffff;")
        
        self.next_button = QPushButton("下一页")
        self.next_button.setFixedHeight(32)
        self.next_button.clicked.connect(self._on_next_page)
        self.next_button.setEnabled(False)
        
        for btn in [self.prev_button, self.next_button]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #3a3a3a;
                    border: none;
                    border-radius: 4px;
                    color: #ffffff;
                    padding: 0 20px;
                }
                QPushButton:hover:enabled {
                    background-color: #4a4a4a;
                }
                QPushButton:disabled {
                    color: #666666;
                }
            """)
        
        pagination_layout.addWidget(self.prev_button)
        pagination_layout.addStretch()
        pagination_layout.addWidget(self.page_label)
        pagination_layout.addStretch()
        pagination_layout.addWidget(self.next_button)
        
        layout.addLayout(pagination_layout)
        
        return self.results_panel
    
    def _create_details_panel(self) -> QWidget:
        """Create right panel for comic details."""
        self.details_panel = QWidget()
        self.details_panel.setStyleSheet("background-color: #252525;")
        
        layout = QVBoxLayout(self.details_panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Placeholder message
        self.details_placeholder = QLabel("← 选择一个漫画查看详情")
        self.details_placeholder.setAlignment(Qt.AlignCenter)
        self.details_placeholder.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 14px;
            }
        """)
        layout.addWidget(self.details_placeholder)
        
        # Details content (hidden initially)
        self.details_content = QWidget()
        self.details_content.hide()
        details_layout = QVBoxLayout(self.details_content)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(15)
        
        # Cover image
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(200, 267)  # 3:4 ratio
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setStyleSheet("""
            QLabel {
                background-color: #1e1e1e;
                border-radius: 8px;
            }
        """)
        details_layout.addWidget(self.cover_label, 0, Qt.AlignHCenter)
        
        # Title
        self.title_label = QLabel()
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 16px;
                font-weight: bold;
            }
        """)
        details_layout.addWidget(self.title_label)
        
        # Info grid
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setSpacing(8)
        
        self.author_label = QLabel()
        self.category_label = QLabel()
        self.id_label = QLabel()
        self.chapters_label = QLabel()
        
        for label in [self.author_label, self.category_label, self.id_label, self.chapters_label]:
            label.setStyleSheet("color: #cccccc; font-size: 13px;")
            label.setWordWrap(True)
            info_layout.addWidget(label)
        
        details_layout.addWidget(info_widget)
        
        # Action buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)
        
        self.read_button = QPushButton("阅读")
        self.read_button.setFixedHeight(40)
        self.read_button.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                border: none;
                border-radius: 8px;
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1084d8; }
            QPushButton:pressed { background-color: #006cbd; }
        """)
        self.read_button.clicked.connect(self._on_read_clicked)
        buttons_layout.addWidget(self.read_button)
        
        self.download_button = QPushButton("下载")
        self.download_button.setFixedHeight(40)
        self.download_button.setStyleSheet("""
            QPushButton {
                background-color: #107c10;
                border: none;
                border-radius: 8px;
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #0e6b0e; }
            QPushButton:pressed { background-color: #0c5a0c; }
        """)
        self.download_button.clicked.connect(self._on_download_clicked)
        buttons_layout.addWidget(self.download_button)
        
        self.queue_button = QPushButton("加入队列")
        self.queue_button.setFixedHeight(40)
        self.queue_button.setStyleSheet("""
            QPushButton {
                background-color: #5c2d91;
                border: none;
                border-radius: 8px;
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #6b3fa0; }
            QPushButton:pressed { background-color: #4a2373; }
        """)
        self.queue_button.clicked.connect(self._on_add_to_queue_clicked)
        buttons_layout.addWidget(self.queue_button)
        
        details_layout.addLayout(buttons_layout)
        
        # Chapter buttons container (will be populated when chapters load)
        self.chapter_buttons_container = QWidget()
        self.chapter_buttons_layout = QVBoxLayout(self.chapter_buttons_container)
        self.chapter_buttons_layout.setContentsMargins(0, 10, 0, 0)
        self.chapter_buttons_layout.setSpacing(5)
        details_layout.addWidget(self.chapter_buttons_container)
        
        details_layout.addStretch()
        
        layout.addWidget(self.details_content)
        
        return self.details_panel
    
    def _connect_signals(self) -> None:
        """Connect adapter signals."""
        self.adapter.search_completed.connect(self._on_search_completed)
        self.adapter.search_failed.connect(self._on_search_failed)
        self.adapter.chapters_completed.connect(self._on_chapters_loaded)
        self.adapter.chapters_failed.connect(self._on_chapters_failed)
        self.adapter.images_completed.connect(self._on_images_loaded)
        self.adapter.images_failed.connect(self._on_images_failed)
        self.adapter.login_completed.connect(self._on_login_completed)
        self.adapter.login_failed.connect(self._on_login_failed)
    
    def _on_search_triggered(self) -> None:
        """Handle search button click."""
        keyword = self.search_bar.text().strip()
        if not keyword:
            return
        
        if not self.adapter.is_logged_in():
            QMessageBox.warning(self, "搜索错误", "请先在设置中登录PicACG账号")
            return
        
        self._current_keyword = keyword
        self._current_page = 1
        self._perform_search()
    
    def _perform_search(self) -> None:
        """Perform search with current keyword and page."""
        self.search_button.setEnabled(False)
        self.results_label.setText("搜索中...")
        self.adapter.search(self._current_keyword, self._current_page)
    
    def _on_search_completed(self, comics: List[Comic]) -> None:
        """Handle search completion."""
        self.search_button.setEnabled(True)
        self._all_comics = comics
        self._total_results = len(comics)
        
        # Update results label
        self.results_label.setText(f"搜索结果 ({self._total_results} 个)")
        
        # Display current page
        self._display_current_page()
        
        # Update pagination
        self._update_pagination()
    
    def _on_search_failed(self, error: str) -> None:
        """Handle search failure with user-friendly message."""
        self.search_button.setEnabled(True)
        self.results_label.setText("搜索失败")
        
        # Provide user-friendly error message
        if "认证" in error or "login" in error.lower():
            QMessageBox.warning(
                self,
                "认证失败",
                "登录状态已过期，请重新登录。\n\n"
                "请到设置页面重新登录PicACG账号。"
            )
        elif "网络" in error or "timeout" in error.lower():
            QMessageBox.warning(
                self,
                "网络错误",
                "网络连接超时或不稳定。\n\n"
                "建议解决方案：\n"
                "• 检查网络连接\n"
                "• 在设置中切换API服务器\n"
                "• 稍后重试"
            )
        else:
            QMessageBox.warning(
                self,
                "搜索失败",
                f"搜索时发生错误：{error}\n\n"
                "请检查网络连接或稍后重试。"
            )
    
    def _display_current_page(self) -> None:
        """Display comics for current page."""
        # Clear existing results
        while self.results_layout.count() > 1:
            item = self.results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Calculate page range
        start_idx = (self._current_page - 1) * self._results_per_page
        end_idx = min(start_idx + self._results_per_page, self._total_results)
        
        # Display comics for this page
        for i in range(start_idx, end_idx):
            comic = self._all_comics[i]
            card = self._create_result_card(comic)
            self.results_layout.insertWidget(i - start_idx, card)
    
    def _create_result_card(self, comic: Comic) -> QWidget:
        """Create a result card widget."""
        # Get theme colors
        if self._current_theme == 'light':
            bg_card = '#FAFAFA'
            bg_card_hover = '#F0F0F0'
            text_primary = '#000000'
            text_secondary = '#333333'
            border_color = '#E0E0E0'
            border_hover = '#CCCCCC'
            thumb_bg = '#F3F3F3'
        else:
            bg_card = '#2b2b2b'
            bg_card_hover = '#3a3a3a'
            text_primary = '#ffffff'
            text_secondary = '#cccccc'
            border_color = '#3a3a3a'
            border_hover = '#4a4a4a'
            thumb_bg = '#1e1e1e'
        
        card = QFrame()
        card.setFixedHeight(80)
        card.setCursor(Qt.PointingHandCursor)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_card};
                border-radius: 8px;
                border: 1px solid {border_color};
            }}
            QFrame:hover {{
                background-color: {bg_card_hover};
                border: 1px solid {border_hover};
            }}
        """)
        
        layout = QHBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # Thumbnail
        thumb = QLabel()
        thumb.setFixedSize(45, 60)
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setStyleSheet(f"""
            QLabel {{
                background-color: {thumb_bg};
                border-radius: 4px;
                color: #666666;
            }}
        """)
        thumb.setText("...")
        layout.addWidget(thumb)
        
        # Load thumbnail asynchronously
        self._load_thumbnail(thumb, comic.cover_url)
        
        # Info container
        info_widget = QWidget()
        info_widget.setMinimumWidth(200)  # Ensure minimum width for text
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 5, 0, 5)
        info_layout.setSpacing(8)
        
        # Title
        title = QLabel(comic.title)
        title.setStyleSheet(f"""
            QLabel {{
                color: {text_primary};
                font-weight: bold;
                font-size: 14px;
                background-color: transparent;
            }}
        """)
        title.setWordWrap(True)
        title.setMaximumHeight(36)  # Allow for 2 lines
        title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        
        # Author
        author = QLabel(f"作者: {comic.author}")
        author.setStyleSheet(f"""
            QLabel {{
                color: {text_secondary};
                font-size: 12px;
                background-color: transparent;
            }}
        """)
        author.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        info_layout.addWidget(title)
        info_layout.addWidget(author)
        info_layout.addStretch()
        
        layout.addWidget(info_widget, 1)
        
        # Make card clickable
        card.mousePressEvent = lambda e: self._on_comic_selected(comic)
        
        return card
    
    def _load_thumbnail(self, label: QLabel, url: str) -> None:
        """Load thumbnail image for result card."""
        if not url or url.startswith('placeholder'):
            label.setText("无图")
            label.setStyleSheet("""
                QLabel {
                    background-color: #1e1e1e;
                    border-radius: 4px;
                    color: #666666;
                    font-size: 10px;
                }
            """)
            return
        
        # Use QThread to download thumbnail
        from PySide6.QtCore import QThread, QObject, Signal
        from PySide6.QtGui import QPixmap
        import requests
        
        class ThumbnailLoader(QObject):
            finished = Signal(object)  # QPixmap or None
            
            def __init__(self, url):
                super().__init__()
                self.url = url
            
            def load(self):
                try:
                    # Use proper headers for PicACG image servers
                    headers = {
                        'User-Agent': 'okhttp/3.8.1',
                        'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                    }
                    
                    response = requests.get(self.url, headers=headers, timeout=8, verify=False)
                    if response.status_code == 200:
                        pixmap = QPixmap()
                        if pixmap.loadFromData(response.content):
                            self.finished.emit(pixmap)
                        else:
                            self.finished.emit(None)
                    else:
                        print(f"Thumbnail HTTP {response.status_code} for {self.url}")
                        self.finished.emit(None)
                except Exception as e:
                    print(f"Thumbnail load error for {self.url}: {e}")
                    self.finished.emit(None)
        
        def on_loaded(pixmap):
            if pixmap and not pixmap.isNull():
                scaled = pixmap.scaled(
                    45, 60,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                label.setPixmap(scaled)
                label.setStyleSheet("""
                    QLabel {
                        background-color: #1e1e1e;
                        border-radius: 4px;
                    }
                """)
            else:
                label.setText("×")
                label.setStyleSheet("""
                    QLabel {
                        background-color: #1e1e1e;
                        border-radius: 4px;
                        color: #666666;
                        font-size: 12px;
                    }
                """)
        
        # Create and start thread
        thread = QThread()
        loader = ThumbnailLoader(url)
        loader.moveToThread(thread)
        
        thread.started.connect(loader.load)
        loader.finished.connect(on_loaded)
        loader.finished.connect(thread.quit)
        
        thread.start()
        
        # Store references to prevent garbage collection
        if not hasattr(self, '_thumbnail_threads'):
            self._thumbnail_threads = []
        self._thumbnail_threads.append((thread, loader))
    
    def _on_comic_selected(self, comic: Comic) -> None:
        """Handle comic selection."""
        self._selected_comic = comic
        
        # Hide placeholder, show details
        self.details_placeholder.hide()
        self.details_content.show()
        
        # Update details
        self.title_label.setText(comic.title)
        self.author_label.setText(f"作者: {comic.author}")
        self.category_label.setText(f"分类: {', '.join(comic.categories)}")
        self.id_label.setText(f"ID: {comic.id}")
        self.chapters_label.setText("章节: 加载中...")
        
        # Clear existing chapter buttons
        while self.chapter_buttons_layout.count():
            item = self.chapter_buttons_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Load cover
        self._load_cover(comic.cover_url)
        
        # Load chapters
        self.adapter.get_chapters(comic.id)
    
    def _load_cover(self, url: str) -> None:
        """Load cover image from URL."""
        if not url or url.startswith('placeholder'):
            self.cover_label.setText("无封面")
            return
        
        self.cover_label.setText("加载中...")
        
        # Use QThread to download image with proper headers
        from PySide6.QtCore import QThread, QObject, Signal
        from PySide6.QtGui import QPixmap
        import requests
        
        class ImageLoader(QObject):
            finished = Signal(object)  # QPixmap or None
            
            def __init__(self, url):
                super().__init__()
                self.url = url
            
            def load(self):
                try:
                    # Use proper headers for PicACG image servers
                    headers = {
                        'User-Agent': 'okhttp/3.8.1',
                        'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                    }
                    
                    response = requests.get(self.url, headers=headers, timeout=15, verify=False)
                    if response.status_code == 200:
                        pixmap = QPixmap()
                        if pixmap.loadFromData(response.content):
                            self.finished.emit(pixmap)
                        else:
                            print(f"Failed to decode cover image from {self.url}")
                            self.finished.emit(None)
                    else:
                        print(f"Cover HTTP {response.status_code} for {self.url}")
                        self.finished.emit(None)
                except Exception as e:
                    print(f"Failed to load cover from {self.url}: {e}")
                    self.finished.emit(None)
        
        def on_image_loaded(pixmap):
            if pixmap and not pixmap.isNull():
                # Scale to fit
                scaled = pixmap.scaled(
                    200, 267,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.cover_label.setPixmap(scaled)
            else:
                self.cover_label.setText("加载失败")
            
            # Clean up
            if hasattr(self, '_image_thread'):
                self._image_thread.quit()
                self._image_thread.wait()
        
        # Create thread
        self._image_thread = QThread()
        self._image_loader = ImageLoader(url)
        self._image_loader.moveToThread(self._image_thread)
        
        # Connect signals
        self._image_thread.started.connect(self._image_loader.load)
        self._image_loader.finished.connect(on_image_loaded)
        
        # Start thread
        self._image_thread.start()
    
    def _on_chapters_loaded(self, chapters: List[Chapter]) -> None:
        """Handle chapters loaded."""
        print(f"Chapters loaded: {len(chapters)} chapters")
        for i, chapter in enumerate(chapters):
            print(f"  Chapter {i+1}: {chapter.title} (ID: {chapter.id})")
        
        self._comic_chapters = chapters
        self.chapters_label.setText(f"章节: {len(chapters)} 话")
        
        # Create chapter buttons
        self._create_chapter_buttons(chapters)
    
    def _create_chapter_buttons(self, chapters: List[Chapter]) -> None:
        """Create chapter selection buttons."""
        # Clear existing buttons
        while self.chapter_buttons_layout.count():
            item = self.chapter_buttons_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not chapters or len(chapters) <= 1:
            return
        
        # Get theme colors
        if self._current_theme == 'light':
            btn_bg, btn_text = '#E0E0E0', '#333333'
        else:
            btn_bg, btn_text = '#3a3a3a', '#cccccc'
        
        btn_style = f"""
            QLabel {{
                background-color: {btn_bg};
                color: {btn_text};
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 11px;
            }}
            QLabel:hover {{
                background-color: #0078d4;
                color: #ffffff;
            }}
        """
        
        # Sort chapters by chapter_number (ascending order for display)
        sorted_chapters = sorted(chapters, key=lambda c: c.chapter_number)
        
        # Create rows of buttons (6 per row)
        BUTTONS_PER_ROW = 6
        current_row = None
        current_row_layout = None
        
        for i, chapter in enumerate(sorted_chapters):
            if i % BUTTONS_PER_ROW == 0:
                current_row = QWidget()
                current_row_layout = QHBoxLayout(current_row)
                current_row_layout.setContentsMargins(0, 0, 0, 0)
                current_row_layout.setSpacing(4)
                current_row_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
                self.chapter_buttons_layout.addWidget(current_row)
            
            btn = QLabel(f"第{chapter.chapter_number}话")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(btn_style)
            btn.mousePressEvent = lambda e, ch=chapter: self._on_chapter_button_clicked(ch)
            current_row_layout.addWidget(btn)
        
        # Add stretch to last row
        if current_row_layout:
            current_row_layout.addStretch()
    
    def _on_chapter_button_clicked(self, chapter: Chapter) -> None:
        """Handle chapter button click - start reading that chapter."""
        if self._selected_comic:
            self.read_requested.emit(self._selected_comic, chapter)
    
    def _on_chapters_failed(self, error: str) -> None:
        """Handle chapters load failure with user-friendly message."""
        print(f"Chapters load failed: {error}")
        self.chapters_label.setText("章节: 加载失败")
        
        # Provide user-friendly error message
        if "认证" in error or "login" in error.lower():
            QMessageBox.warning(
                self,
                "认证失败",
                "登录状态已过期，请重新登录。\n\n"
                "请到设置页面重新登录PicACG账号。"
            )
        elif "500" in error:
            QMessageBox.warning(
                self,
                "服务器错误", 
                "服务器返回错误，无法加载章节列表。\n\n"
                "建议解决方案：\n"
                "• 稍后重试\n"
                "• 在设置中切换API服务器\n"
                "• 尝试其他漫画"
            )
        else:
            QMessageBox.warning(
                self,
                "章节加载失败",
                f"无法加载章节列表：{error}\n\n"
                "请稍后重试或尝试其他漫画。"
            )
    
    def _on_images_loaded(self, images: List[str]) -> None:
        """Handle images load completion."""
        print(f"Images loaded: {len(images)} images")
        # Images are loaded successfully, reader can proceed
        # This is mainly for logging, the actual reading is handled by the reader component
    
    def _on_images_failed(self, error: str) -> None:
        """Handle images load failure with user-friendly message."""
        print(f"Images load failed: {error}")
        
        # Provide user-friendly error message with suggestions
        if "所有API服务器都无法获取此漫画的图片" in error:
            QMessageBox.warning(
                self, 
                "图片加载失败", 
                "无法加载此漫画的图片。\n\n"
                "可能的原因：\n"
                "• 此漫画在服务器上暂时不可用\n"
                "• 网络连接问题\n"
                "• 服务器维护中\n\n"
                "建议解决方案：\n"
                "• 尝试其他漫画\n"
                "• 稍后重试\n"
                "• 在设置中切换API服务器\n"
                "• 检查网络连接"
            )
        elif "500" in error:
            QMessageBox.warning(
                self,
                "服务器错误",
                "服务器返回错误，请稍后重试。\n\n"
                "如果问题持续存在，请尝试：\n"
                "• 在设置中切换到其他API服务器\n"
                "• 尝试阅读其他漫画"
            )
        elif "认证" in error or "login" in error.lower():
            QMessageBox.warning(
                self,
                "认证失败", 
                "登录状态已过期，请重新登录。\n\n"
                "请到设置页面重新登录PicACG账号。"
            )
        else:
            QMessageBox.warning(
                self,
                "图片加载失败",
                f"无法加载图片：{error}\n\n"
                "请稍后重试或尝试其他漫画。"
            )
    
    def _on_read_clicked(self) -> None:
        """Handle read button click."""
        print(f"Read button clicked. Comic: {self._selected_comic is not None}, Chapters: {len(self._comic_chapters) if self._comic_chapters else 0}")
        
        if not self._selected_comic:
            QMessageBox.warning(self, "阅读", "请先选择一个漫画")
            return
        
        if not self._comic_chapters:
            QMessageBox.warning(self, "阅读", "章节加载中，请稍后再试")
            return
        
        # 修复章节选择逻辑：PicACG章节是倒序排列的
        # 需要选择正确的第一章
        first_chapter = None
        
        if len(self._comic_chapters) == 1:
            # 只有一章，直接选择
            first_chapter = self._comic_chapters[0]
        else:
            # 多章节，检查顺序
            first_order = self._comic_chapters[0].chapter_number
            last_order = self._comic_chapters[-1].chapter_number
            
            if first_order > last_order:
                # 倒序排列（PicACG的标准情况），选择最后一个作为第一章
                first_chapter = self._comic_chapters[-1]
                print(f"检测到倒序章节，选择索引 {len(self._comic_chapters)-1} 作为第一章")
            else:
                # 正序排列，选择第一个
                first_chapter = self._comic_chapters[0]
                print(f"检测到正序章节，选择索引 0 作为第一章")
        
        if first_chapter:
            print(f"Selected first chapter: {first_chapter.title} (order: {first_chapter.chapter_number})")
            self.read_requested.emit(self._selected_comic, first_chapter)
        else:
            QMessageBox.warning(self, "阅读", "无法确定第一章节")
    
    def _on_download_clicked(self) -> None:
        """Handle download button click."""
        print(f"Download button clicked. Comic: {self._selected_comic is not None}, Chapters: {len(self._comic_chapters) if self._comic_chapters else 0}")
        
        if not self._selected_comic:
            QMessageBox.warning(self, "下载", "请先选择一个漫画")
            return
        
        if not self._comic_chapters:
            QMessageBox.warning(self, "下载", "章节加载中，请稍后再试")
            return
        
        # Emit signal to download all chapters
        self.download_requested.emit(self._selected_comic, self._comic_chapters)
    
    def _on_add_to_queue_clicked(self) -> None:
        """Handle add to queue button click."""
        if not self._selected_comic:
            QMessageBox.warning(self, "加入队列", "请先选择一个漫画")
            return
        
        if not self._comic_chapters:
            QMessageBox.warning(self, "加入队列", "章节加载中，请稍后再试")
            return
        
        # Emit signal to add to queue
        self.queue_requested.emit(self._selected_comic, self._comic_chapters)
    
    def _on_prev_page(self) -> None:
        """Handle previous page button."""
        if self._current_page > 1:
            self._current_page -= 1
            self._display_current_page()
            self._update_pagination()
    
    def _on_next_page(self) -> None:
        """Handle next page button."""
        total_pages = (self._total_results + self._results_per_page - 1) // self._results_per_page
        if self._current_page < total_pages:
            self._current_page += 1
            self._display_current_page()
            self._update_pagination()
    
    def _update_pagination(self) -> None:
        """Update pagination controls."""
        total_pages = (self._total_results + self._results_per_page - 1) // self._results_per_page
        
        self.page_label.setText(f"第 {self._current_page} / {total_pages} 页")
        self.prev_button.setEnabled(self._current_page > 1)
        self.next_button.setEnabled(self._current_page < total_pages)
    
    def _on_login_completed(self, success: bool, message: str) -> None:
        """Handle login completion."""
        if success:
            self.login_status.setText("已登录")
            self.login_status.setStyleSheet("color: #00aa00; font-weight: bold; margin-left: 20px;")
        else:
            self.login_status.setText("登录失败")
            self.login_status.setStyleSheet("color: #ff4444; font-weight: bold; margin-left: 20px;")
    
    def _on_login_failed(self, error: str) -> None:
        """Handle login failure."""
        self.login_status.setText("未登录")
        self.login_status.setStyleSheet("color: #ff4444; font-weight: bold; margin-left: 20px;")
    
    def _navigate_to_settings(self) -> None:
        """导航到设置页面的PicACG部分"""
        # 发送信号请求导航到设置页面
        self.settings_requested.emit()
    
    def _on_settings_saved(self) -> None:
        """Handle settings saved."""
        # Check if adapter is now logged in
        if self.adapter.is_logged_in():
            self.login_status.setText("已登录")
            self.login_status.setStyleSheet("color: #00aa00; font-weight: bold; margin-left: 20px;")
        else:
            # Try auto-login with new settings
            self.adapter.auto_login()
    
    def _check_auto_login(self) -> None:
        """检查并执行自动登录"""
        try:
            # 从全局应用获取配置管理器
            from pancomic.core.app import App
            app = App()
            if app and app.config_manager:
                config_manager = app.config_manager
                
                # 检查自动登录设置
                auto_login = config_manager.get('picacg.auto_login', False)
                email = config_manager.get('picacg.email', '')
                password = config_manager.get('picacg.password', '')
                
                print(f"🔍 自动登录检查: auto_login={auto_login}, email={email}, has_password={bool(password)}")
                
                if auto_login and email and password:
                    print(f"🔄 执行自动登录: {email}")
                    
                    # 更新适配器配置
                    self.adapter.config.update({
                        'auto_login': True,
                        'email': email,
                        'password': password,
                        'credentials': {
                            'email': email,
                            'password': password
                        }
                    })
                    
                    # 执行自动登录
                    self.adapter.auto_login()
                else:
                    print("ℹ️ 自动登录未启用或缺少凭据")
            else:
                print("⚠️ 无法获取配置管理器，跳过自动登录")
                
        except Exception as e:
            print(f"❌ 自动登录检查失败: {e}")
    
    def get_adapter(self) -> PicACGAdapter:
        """Get the PicACG adapter."""
        return self.adapter


    def apply_theme(self, theme: str) -> None:
        """Apply theme to PicACG page components."""
        self._current_theme = theme  # Save current theme
        
        if theme == 'light':
            bg_primary = '#FFFFFF'
            bg_secondary = '#F3F3F3'
            bg_card = '#FAFAFA'
            text_primary = '#000000'
            text_secondary = '#333333'
            text_muted = '#666666'
            border_color = '#E0E0E0'
            accent_color = '#0078D4'
        else:
            bg_primary = '#1e1e1e'
            bg_secondary = '#2b2b2b'
            bg_card = '#252525'
            text_primary = '#ffffff'
            text_secondary = '#cccccc'
            text_muted = '#888888'
            border_color = '#3a3a3a'
            accent_color = '#0078d4'
        
        # Main page background
        self.setStyleSheet(f"background-color: {bg_primary};")
        
        # Search container
        if hasattr(self, 'search_container'):
            self.search_container.setStyleSheet(f"""
                QWidget {{
                    background-color: {bg_secondary};
                    border-bottom: 1px solid {border_color};
                }}
            """)
        
        # Search bar
        if hasattr(self, 'search_bar'):
            self.search_bar.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {bg_primary};
                    border: 1px solid {border_color};
                    border-radius: 8px;
                    padding: 0 15px;
                    color: {text_primary};
                    font-size: 14px;
                }}
                QLineEdit:focus {{
                    border: 1px solid {accent_color};
                }}
            """)
        
        # Results panel (left)
        if hasattr(self, 'results_panel'):
            self.results_panel.setStyleSheet(f"background-color: {bg_primary};")
        
        # Details panel (right)
        if hasattr(self, 'details_panel'):
            self.details_panel.setStyleSheet(f"background-color: {bg_card};")
        
        # Results label
        if hasattr(self, 'results_label'):
            self.results_label.setStyleSheet(f"color: {text_primary}; font-size: 14px; font-weight: bold;")
        
        # Page label
        if hasattr(self, 'page_label'):
            self.page_label.setStyleSheet(f"color: {text_primary};")
        
        # Details placeholder
        if hasattr(self, 'details_placeholder'):
            self.details_placeholder.setStyleSheet(f"color: {text_muted}; font-size: 16px;")
        
        # Title label
        if hasattr(self, 'title_label'):
            self.title_label.setStyleSheet(f"color: {text_primary}; font-size: 18px; font-weight: bold;")
        
        # Info labels
        for attr in ['author_label', 'category_label', 'id_label', 'chapters_label']:
            if hasattr(self, attr):
                getattr(self, attr).setStyleSheet(f"color: {text_secondary}; font-size: 13px;")
        
        # Scroll area
        if hasattr(self, 'results_scroll'):
            self.results_scroll.setStyleSheet(f"""
                QScrollArea {{
                    border: none;
                    background-color: {bg_primary};
                }}
                QScrollBar:vertical {{
                    background-color: {bg_secondary};
                    width: 12px;
                }}
                QScrollBar::handle:vertical {{
                    background-color: {border_color};
                    border-radius: 6px;
                }}
            """)
        
        # Navigation buttons
        for attr in ['prev_button', 'next_button']:
            if hasattr(self, attr):
                getattr(self, attr).setStyleSheet(f"""
                    QPushButton {{
                        background-color: {border_color};
                        color: {text_primary};
                        border: none;
                        border-radius: 4px;
                        padding: 8px 16px;
                    }}
                    QPushButton:hover {{
                        background-color: {text_muted};
                    }}
                    QPushButton:disabled {{
                        background-color: {bg_secondary};
                        color: {text_muted};
                    }}
                """)
        
        # Re-display search results with new theme
        if self._all_comics:
            self._display_current_page()
