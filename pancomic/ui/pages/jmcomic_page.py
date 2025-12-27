"""JMComic source page with split layout."""

from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, 
    QLabel, QPushButton, QScrollArea, QFrame
)
from PySide6.QtCore import Qt, Signal

from pancomic.ui.pages.base_source_page import BaseSourcePage
from pancomic.adapters.jmcomic_adapter import JMComicAdapter
from pancomic.models.comic import Comic
from pancomic.models.chapter import Chapter
from pancomic.infrastructure.download_manager import DownloadManager

# Disable SSL warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class JMComicPage(QWidget):
    """
    JMComic source page with split layout.
    
    Left panel: Search results with pagination (12 per page)
    Right panel: Comic details with read/download buttons
    """
    
    # Signals
    read_requested = Signal(object, object)  # Comic, Chapter
    download_requested = Signal(object, list)  # Comic, List[Chapter]
    queue_requested = Signal(object, list)  # Comic, List[Chapter] - add to queue
    settings_requested = Signal()  # Request to navigate to settings
    
    def __init__(self, adapter: JMComicAdapter, download_manager: DownloadManager, parent: Optional[QWidget] = None):
        """
        Initialize JMComicPage.
        
        Args:
            adapter: JMComic adapter instance
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
        
        # Search bar (same as before)
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
        from PySide6.QtWidgets import QLineEdit
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("搜索JMComic漫画...")
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
    
    def _navigate_to_settings(self) -> None:
        """Navigate to JMComic settings page."""
        self.settings_requested.emit()
    
    def update_login_status(self) -> None:
        """Update login status display."""
        try:
            # Check if adapter has qt_owner with user info
            if self.adapter._jmcomic_module:
                qt_owner = self.adapter._jmcomic_module.get('qt_owner')
                if qt_owner and hasattr(qt_owner, 'user') and qt_owner.user.isLogin:
                    username = qt_owner.user.userName or "用户"
                    self.login_status.setText(f"已登录: {username}")
                    self.login_status.setStyleSheet("color: #44ff44; font-weight: bold; margin-left: 20px;")
                    return
        except Exception as e:
            print(f"[JMComic] Error checking login status: {e}")
        
        self.login_status.setText("未登录")
        self.login_status.setStyleSheet("color: #ff4444; font-weight: bold; margin-left: 20px;")
    
    def showEvent(self, event) -> None:
        """Handle show event to update login status."""
        super().showEvent(event)
        self.update_login_status()
    
    def _create_results_panel(self) -> QWidget:
        """Create left panel for search results."""
        panel = QWidget()
        panel.setStyleSheet("background-color: #1e1e1e;")
        
        layout = QVBoxLayout(panel)
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
        
        return panel
    
    def _create_details_panel(self) -> QWidget:
        """Create right panel for comic details."""
        panel = QWidget()
        panel.setStyleSheet("background-color: #252525;")
        
        layout = QVBoxLayout(panel)
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
        details_layout.addStretch()
        
        layout.addWidget(self.details_content)
        
        return panel
    
    def _connect_signals(self) -> None:
        """Connect adapter signals."""
        self.adapter.search_completed.connect(self._on_search_completed)
        self.adapter.search_failed.connect(self._on_search_failed)
        self.adapter.chapters_completed.connect(self._on_chapters_loaded)
        self.adapter.chapters_failed.connect(self._on_chapters_failed)
        self.adapter.login_completed.connect(self._on_login_completed)
    
    def _check_auto_login(self) -> None:
        """检查并执行自动登录"""
        try:
            from pancomic.core.app import App
            app = App()
            if app and app.config_manager:
                config_manager = app.config_manager
                
                # 检查自动登录设置
                auto_login = config_manager.get('jmcomic.auto_login', False)
                username = config_manager.get('jmcomic.username', '')
                password = config_manager.get('jmcomic.password', '')
                
                print(f"🔍 JMComic自动登录检查: auto_login={auto_login}, username={username}, has_password={bool(password)}")
                
                if auto_login and username and password:
                    print(f"🔄 JMComic执行自动登录: {username}")
                    
                    # 先应用分流设置
                    api_index = config_manager.get('jmcomic.api_proxy', 5)  # 默认CDN分流
                    img_index = config_manager.get('jmcomic.img_proxy', 5)
                    cdn_api_ip = config_manager.get('jmcomic.cdn_api_ip', '104.18.227.172')
                    cdn_img_ip = config_manager.get('jmcomic.cdn_img_ip', '104.18.227.172')
                    
                    self.adapter.update_proxy_settings(api_index, img_index, cdn_api_ip, cdn_img_ip)
                    
                    # 执行登录
                    self.adapter.login({'username': username, 'password': password})
                else:
                    print("ℹ️ JMComic自动登录未启用或缺少凭据")
        except Exception as e:
            print(f"❌ JMComic自动登录检查失败: {e}")
    
    def _on_login_completed(self, success: bool, message: str) -> None:
        """Handle login completion."""
        if success:
            print(f"✅ JMComic登录成功: {message}")
        else:
            print(f"❌ JMComic登录失败: {message}")
        self.update_login_status()
    
    def _on_search_triggered(self) -> None:
        """Handle search button click."""
        keyword = self.search_bar.text().strip()
        if not keyword:
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
        """Handle search failure."""
        self.search_button.setEnabled(True)
        self.results_label.setText(f"搜索失败: {error}")
    
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
        from PySide6.QtWidgets import QSizePolicy
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
        if not url:
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
                    # Use proper headers for JMComic image servers
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Linux; Android 7.1.2; DT1901A Build/N2G47O; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/86.0.4240.198 Mobile Safari/537.36',
                        'Referer': 'https://www.jmapiproxyxxx.vip/',
                        'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                        'Accept-Encoding': 'gzip, deflate',
                        'Connection': 'keep-alive'
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
        
        # Load cover
        self._load_cover(comic.cover_url)
        
        # Load chapters
        self.adapter.get_chapters(comic.id)
    
    def _load_cover(self, url: str) -> None:
        """Load cover image from URL."""
        if not url:
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
                    # Use proper headers for JMComic image servers
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Linux; Android 7.1.2; DT1901A Build/N2G47O; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/86.0.4240.198 Mobile Safari/537.36',
                        'Referer': 'https://www.jmapiproxyxxx.vip/',
                        'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                        'Accept-Encoding': 'gzip, deflate',
                        'Connection': 'keep-alive'
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
    
    def _on_chapters_failed(self, error: str) -> None:
        """Handle chapters load failure."""
        print(f"Chapters load failed: {error}")
        self.chapters_label.setText(f"章节: 加载失败 ({error})")
    
    def _on_read_clicked(self) -> None:
        """Handle read button click."""
        print(f"Read button clicked. Comic: {self._selected_comic is not None}, Chapters: {len(self._comic_chapters) if self._comic_chapters else 0}")
        
        if not self._selected_comic:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "阅读", "请先选择一个漫画")
            return
        
        if not self._comic_chapters:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "阅读", "章节加载中，请稍后再试")
            return
        
        # Emit signal to open reader with first chapter
        self.read_requested.emit(self._selected_comic, self._comic_chapters[0])
    
    def _on_download_clicked(self) -> None:
        """Handle download button click."""
        print(f"Download button clicked. Comic: {self._selected_comic is not None}, Chapters: {len(self._comic_chapters) if self._comic_chapters else 0}")
        
        if not self._selected_comic:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "下载", "请先选择一个漫画")
            return
        
        if not self._comic_chapters:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "下载", "章节加载中，请稍后再试")
            return
        
        # Emit signal to download all chapters
        self.download_requested.emit(self._selected_comic, self._comic_chapters)
    
    def _on_add_to_queue_clicked(self) -> None:
        """Handle add to queue button click."""
        from PySide6.QtWidgets import QMessageBox
        
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

    def apply_theme(self, theme: str) -> None:
        """Apply theme to JMComic page components."""
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
