"""
PicACG Integrated Page using original PicACG-qt as wrapper.

This page uses the PicACGWrapper to integrate directly with the original
PicACG-qt project, providing a more stable and feature-complete experience.
"""

from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QPushButton, 
    QLabel, QLineEdit, QScrollArea, QFrame, QMessageBox, QSizePolicy,
    QComboBox, QProgressBar
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QPixmap

from pancomic.integrations.picacg_wrapper import PicACGWrapper
from pancomic.models.comic import Comic
from pancomic.models.chapter import Chapter
from pancomic.infrastructure.download_manager import DownloadManager

# Disable SSL warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class PicACGIntegratedPage(QWidget):
    """
    PicACG integrated page using original PicACG-qt wrapper.
    
    This page provides the same split layout as JMComic but uses the
    original PicACG-qt functionality through a wrapper for better stability.
    """
    
    # Signals
    read_requested = Signal(object, object)  # Comic, Chapter
    download_requested = Signal(object, list)  # Comic, List[Chapter]
    settings_requested = Signal()  # Request to navigate to settings
    
    def __init__(self, config: dict, download_manager: DownloadManager, parent: Optional[QWidget] = None):
        """
        Initialize PicACG integrated page.
        
        Args:
            config: PicACG configuration
            download_manager: Download manager instance
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.config = config
        self.download_manager = download_manager
        
        # Initialize wrapper
        self.wrapper = PicACGWrapper(config)
        
        # State
        self._current_keyword = ""
        self._current_page = 1
        self._total_results = 0
        self._results_per_page = 12
        self._all_comics = []
        self._selected_comic = None
        self._comic_chapters = []
        
        # Speed test state
        self._api_test_results = {}
        self._image_test_results = {}
        
        # Setup UI
        self._setup_ui()
        
        # Connect signals
        self._connect_signals()
        
        # Initialize wrapper
        self._initialize_wrapper()
    
    def _setup_ui(self) -> None:
        """Setup the split layout UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Search bar with settings
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
        splitter.setSizes([625, 375])
        
        layout.addWidget(splitter)
    
    def _create_search_bar(self) -> QWidget:
        """Create search bar with integrated settings."""
        container = QWidget()
        container.setFixedHeight(120)  # Increased height for settings
        container.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                border-bottom: 1px solid #3a3a3a;
            }
        """)
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(10)
        
        # Top row: Search and login
        top_layout = QHBoxLayout()
        
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
        
        # Login section
        login_layout = QHBoxLayout()
        
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("邮箱")
        self.email_input.setFixedHeight(40)
        self.email_input.setFixedWidth(150)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("密码")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setFixedHeight(40)
        self.password_input.setFixedWidth(120)
        self.password_input.returnPressed.connect(self._on_login_clicked)
        
        self.login_button = QPushButton("登录")
        self.login_button.setFixedSize(60, 40)
        self.login_button.clicked.connect(self._on_login_clicked)
        
        self.login_status = QLabel("未登录")
        self.login_status.setStyleSheet("color: #ff4444; font-weight: bold; margin-left: 10px;")
        
        for widget in [self.email_input, self.password_input]:
            widget.setStyleSheet("""
                QLineEdit {
                    background-color: #1e1e1e;
                    border: 1px solid #3a3a3a;
                    border-radius: 6px;
                    padding: 0 10px;
                    color: #ffffff;
                    font-size: 12px;
                }
                QLineEdit:focus {
                    border: 1px solid #0078d4;
                }
            """)
        
        self.login_button.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                border: none;
                border-radius: 6px;
                color: #ffffff;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #34ce57;
            }
            QPushButton:pressed {
                background-color: #1e7e34;
            }
        """)
        
        login_layout.addWidget(QLabel("邮箱:"))
        login_layout.addWidget(self.email_input)
        login_layout.addWidget(QLabel("密码:"))
        login_layout.addWidget(self.password_input)
        login_layout.addWidget(self.login_button)
        login_layout.addWidget(self.login_status)
        login_layout.addStretch()
        
        top_layout.addWidget(self.search_bar)
        top_layout.addWidget(self.search_button)
        top_layout.addSpacing(20)
        top_layout.addLayout(login_layout)
        
        layout.addLayout(top_layout)
        
        # Bottom row: Server settings and speed test
        bottom_layout = QHBoxLayout()
        
        # API endpoint selection
        api_label = QLabel("API服务器:")
        api_label.setStyleSheet("color: #ffffff; font-size: 12px;")
        
        self.api_combo = QComboBox()
        self.api_combo.setFixedHeight(30)
        self.api_combo.setFixedWidth(200)
        self.api_combo.currentTextChanged.connect(self._on_api_endpoint_changed)
        
        self.api_test_button = QPushButton("测速")
        self.api_test_button.setFixedSize(50, 30)
        self.api_test_button.clicked.connect(self._test_api_endpoints)
        
        # Image server selection
        img_label = QLabel("图片服务器:")
        img_label.setStyleSheet("color: #ffffff; font-size: 12px;")
        
        self.image_combo = QComboBox()
        self.image_combo.setFixedHeight(30)
        self.image_combo.setFixedWidth(180)
        self.image_combo.currentTextChanged.connect(self._on_image_server_changed)
        
        self.image_test_button = QPushButton("测速")
        self.image_test_button.setFixedSize(50, 30)
        self.image_test_button.clicked.connect(self._test_image_servers)
        
        # Style for combos and test buttons
        combo_style = """
            QComboBox {
                background-color: #1e1e1e;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding: 5px;
                color: #ffffff;
                font-size: 11px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #ffffff;
                margin-right: 5px;
            }
        """
        
        test_button_style = """
            QPushButton {
                background-color: #6c757d;
                border: none;
                border-radius: 4px;
                color: #ffffff;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #7c8287;
            }
            QPushButton:pressed {
                background-color: #5a6268;
            }
        """
        
        self.api_combo.setStyleSheet(combo_style)
        self.image_combo.setStyleSheet(combo_style)
        self.api_test_button.setStyleSheet(test_button_style)
        self.image_test_button.setStyleSheet(test_button_style)
        
        bottom_layout.addWidget(api_label)
        bottom_layout.addWidget(self.api_combo)
        bottom_layout.addWidget(self.api_test_button)
        bottom_layout.addSpacing(20)
        bottom_layout.addWidget(img_label)
        bottom_layout.addWidget(self.image_combo)
        bottom_layout.addWidget(self.image_test_button)
        bottom_layout.addStretch()
        
        layout.addLayout(bottom_layout)
        
        return container
    
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
        
        self.read_button = QPushButton("阅读")
        self.download_button = QPushButton("下载")
        
        for btn in [self.read_button, self.download_button]:
            btn.setFixedHeight(40)
            btn.setStyleSheet("""
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
        
        self.read_button.clicked.connect(self._on_read_clicked)
        self.download_button.clicked.connect(self._on_download_clicked)
        
        buttons_layout.addWidget(self.read_button)
        buttons_layout.addWidget(self.download_button)
        
        details_layout.addLayout(buttons_layout)
        details_layout.addStretch()
        
        layout.addWidget(self.details_content)
        
        return panel
    
    def _initialize_wrapper(self) -> None:
        """Initialize the PicACG wrapper."""
        if self.wrapper.initialize():
            # Populate combo boxes
            self._populate_server_combos()
            
            # Try auto-login
            self.wrapper.auto_login()
            
            print("✅ PicACG集成页面初始化成功")
        else:
            QMessageBox.critical(
                self,
                "初始化失败",
                "无法初始化PicACG模块。请检查forapi/picacg目录是否存在。"
            )
    
    def _populate_server_combos(self) -> None:
        """Populate server combo boxes."""
        # API endpoints
        api_endpoints = self.wrapper.get_api_endpoints()
        current_endpoint = self.wrapper.get_current_endpoint()
        
        self.api_combo.clear()
        for endpoint in api_endpoints:
            # Create friendly names
            if "picaapi.picacomic.com" in endpoint:
                name = "官方API"
            elif "bika-api.jpacg.cc" in endpoint:
                name = "JP反代分流"
            elif "bika2-api.jpacg.cc" in endpoint:
                name = "US反代分流"
            elif "104.21.91.145" in endpoint:
                name = "IP直连1"
            elif "188.114.98.153" in endpoint:
                name = "IP直连2"
            else:
                name = endpoint
            
            self.api_combo.addItem(f"{name} ({endpoint})", endpoint)
            
            if endpoint == current_endpoint:
                self.api_combo.setCurrentIndex(self.api_combo.count() - 1)
        
        # Image servers
        image_servers = self.wrapper.get_image_servers()
        current_server = self.wrapper.get_current_image_server()
        
        self.image_combo.clear()
        for server in image_servers:
            # Create friendly names
            if "storage.diwodiwo.xyz" in server:
                name = "Diwo分流"
            elif "s3.picacomic.com" in server:
                name = "S3分流"
            elif "s2.picacomic.com" in server:
                name = "S2分流"
            elif "storage1.picacomic.com" in server:
                name = "Storage1分流"
            elif "storage-b.picacomic.com" in server:
                name = "Storage-B分流"
            else:
                name = server
            
            self.image_combo.addItem(f"{name} ({server})", server)
            
            if server == current_server:
                self.image_combo.setCurrentIndex(self.image_combo.count() - 1)
    
    def _connect_signals(self) -> None:
        """Connect wrapper signals."""
        self.wrapper.login_completed.connect(self._on_login_completed)
        self.wrapper.login_failed.connect(self._on_login_failed)
        self.wrapper.search_completed.connect(self._on_search_completed)
        self.wrapper.search_failed.connect(self._on_search_failed)
        self.wrapper.chapters_completed.connect(self._on_chapters_loaded)
        self.wrapper.chapters_failed.connect(self._on_chapters_failed)
        self.wrapper.images_completed.connect(self._on_images_loaded)
        self.wrapper.images_failed.connect(self._on_images_failed)
        self.wrapper.endpoint_test_completed.connect(self._on_endpoint_test_completed)
        self.wrapper.image_server_test_completed.connect(self._on_image_server_test_completed)
    
    def _on_login_clicked(self) -> None:
        """Handle login button click."""
        email = self.email_input.text().strip()
        password = self.password_input.text().strip()
        
        if not email or not password:
            QMessageBox.warning(self, "登录", "请输入邮箱和密码")
            return
        
        self.login_button.setEnabled(False)
        self.login_status.setText("登录中...")
        self.login_status.setStyleSheet("color: #ffa500; font-weight: bold; margin-left: 10px;")
        
        self.wrapper.login(email, password)
    
    def _on_login_completed(self, success: bool, message: str) -> None:
        """Handle login completion."""
        self.login_button.setEnabled(True)
        
        if success:
            self.login_status.setText("已登录")
            self.login_status.setStyleSheet("color: #00aa00; font-weight: bold; margin-left: 10px;")
            
            # Clear password for security
            self.password_input.clear()
            
            print(f"✅ 登录成功: {message}")
        else:
            self.login_status.setText("登录失败")
            self.login_status.setStyleSheet("color: #ff4444; font-weight: bold; margin-left: 10px;")
            
            QMessageBox.warning(self, "登录失败", message)
            print(f"❌ 登录失败: {message}")
    
    def _on_login_failed(self, error: str) -> None:
        """Handle login failure."""
        self.login_button.setEnabled(True)
        self.login_status.setText("未登录")
        self.login_status.setStyleSheet("color: #ff4444; font-weight: bold; margin-left: 10px;")
        
        QMessageBox.critical(self, "登录错误", f"登录时发生错误：{error}")
        print(f"❌ 登录错误: {error}")
    
    def _on_search_triggered(self) -> None:
        """Handle search button click."""
        keyword = self.search_bar.text().strip()
        if not keyword:
            return
        
        if not self.wrapper.is_logged_in():
            QMessageBox.warning(self, "搜索错误", "请先登录PicACG账号")
            return
        
        self._current_keyword = keyword
        self._current_page = 1
        self._perform_search()
    
    def _perform_search(self) -> None:
        """Perform search with current keyword and page."""
        self.search_button.setEnabled(False)
        self.results_label.setText("搜索中...")
        self.wrapper.search(self._current_keyword, self._current_page)
    
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
        self.results_label.setText("搜索失败")
        
        QMessageBox.warning(self, "搜索失败", f"搜索时发生错误：{error}")
    
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
        card = QFrame()
        card.setFixedHeight(80)
        card.setCursor(Qt.PointingHandCursor)
        card.setStyleSheet("""
            QFrame {
                background-color: #2b2b2b;
                border-radius: 8px;
                border: 1px solid #3a3a3a;
            }
            QFrame:hover {
                background-color: #3a3a3a;
                border: 1px solid #4a4a4a;
            }
        """)
        
        layout = QHBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        # Thumbnail
        thumb = QLabel()
        thumb.setFixedSize(45, 60)
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setStyleSheet("""
            QLabel {
                background-color: #1e1e1e;
                border-radius: 4px;
                color: #666666;
            }
        """)
        thumb.setText("...")
        layout.addWidget(thumb)
        
        # Load thumbnail asynchronously
        self._load_thumbnail(thumb, comic.cover_url)
        
        # Info container
        info_widget = QWidget()
        info_widget.setMinimumWidth(200)
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 5, 0, 5)
        info_layout.setSpacing(8)
        
        # Title
        title = QLabel(comic.title)
        title.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-weight: bold;
                font-size: 14px;
                background-color: transparent;
            }
        """)
        title.setWordWrap(True)
        title.setMaximumHeight(36)
        title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        
        # Author
        author = QLabel(f"作者: {comic.author}")
        author.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-size: 12px;
                background-color: transparent;
            }
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
            return
        
        # Use QThread to download thumbnail
        from PySide6.QtCore import QThread, QObject, Signal
        import requests
        
        class ThumbnailLoader(QObject):
            finished = Signal(object)
            
            def __init__(self, url):
                super().__init__()
                self.url = url
            
            def load(self):
                try:
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
                        self.finished.emit(None)
                except Exception:
                    self.finished.emit(None)
        
        def on_loaded(pixmap):
            if pixmap and not pixmap.isNull():
                scaled = pixmap.scaled(45, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                label.setPixmap(scaled)
            else:
                label.setText("×")
        
        thread = QThread()
        loader = ThumbnailLoader(url)
        loader.moveToThread(thread)
        
        thread.started.connect(loader.load)
        loader.finished.connect(on_loaded)
        loader.finished.connect(thread.quit)
        
        thread.start()
        
        # Store references
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
        self.wrapper.get_chapters(comic.id)
    
    def _load_cover(self, url: str) -> None:
        """Load cover image from URL."""
        if not url or url.startswith('placeholder'):
            self.cover_label.setText("无封面")
            return
        
        self.cover_label.setText("加载中...")
        
        # Similar to thumbnail loading but for cover
        from PySide6.QtCore import QThread, QObject, Signal
        import requests
        
        class ImageLoader(QObject):
            finished = Signal(object)
            
            def __init__(self, url):
                super().__init__()
                self.url = url
            
            def load(self):
                try:
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
                            self.finished.emit(None)
                    else:
                        self.finished.emit(None)
                except Exception:
                    self.finished.emit(None)
        
        def on_image_loaded(pixmap):
            if pixmap and not pixmap.isNull():
                scaled = pixmap.scaled(200, 267, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.cover_label.setPixmap(scaled)
            else:
                self.cover_label.setText("加载失败")
        
        thread = QThread()
        loader = ImageLoader(url)
        loader.moveToThread(thread)
        
        thread.started.connect(loader.load)
        loader.finished.connect(on_image_loaded)
        
        thread.start()
        
        # Store reference
        self._image_thread = thread
        self._image_loader = loader
    
    def _on_chapters_loaded(self, chapters: List[Chapter]) -> None:
        """Handle chapters loaded."""
        self._comic_chapters = chapters
        self.chapters_label.setText(f"章节: {len(chapters)} 话")
        print(f"✅ 章节加载完成: {len(chapters)} 个章节")
    
    def _on_chapters_failed(self, error: str) -> None:
        """Handle chapters load failure."""
        self.chapters_label.setText("章节: 加载失败")
        QMessageBox.warning(self, "章节加载失败", f"无法加载章节列表：{error}")
    
    def _on_images_loaded(self, images: List[str]) -> None:
        """Handle images load completion."""
        print(f"✅ 图片加载完成: {len(images)} 张图片")
    
    def _on_images_failed(self, error: str) -> None:
        """Handle images load failure."""
        QMessageBox.warning(self, "图片加载失败", f"无法加载图片：{error}")
    
    def _on_read_clicked(self) -> None:
        """Handle read button click."""
        if not self._selected_comic:
            QMessageBox.warning(self, "阅读", "请先选择一个漫画")
            return
        
        if not self._comic_chapters:
            QMessageBox.warning(self, "阅读", "章节加载中，请稍后再试")
            return
        
        # Select first chapter (handle PicACG reverse order)
        first_chapter = None
        if len(self._comic_chapters) == 1:
            first_chapter = self._comic_chapters[0]
        else:
            first_order = self._comic_chapters[0].chapter_number
            last_order = self._comic_chapters[-1].chapter_number
            
            if first_order > last_order:
                # Reverse order, select last as first
                first_chapter = self._comic_chapters[-1]
            else:
                # Normal order, select first
                first_chapter = self._comic_chapters[0]
        
        if first_chapter:
            self.read_requested.emit(self._selected_comic, first_chapter)
        else:
            QMessageBox.warning(self, "阅读", "无法确定第一章节")
    
    def _on_download_clicked(self) -> None:
        """Handle download button click."""
        if not self._selected_comic:
            QMessageBox.warning(self, "下载", "请先选择一个漫画")
            return
        
        if not self._comic_chapters:
            QMessageBox.warning(self, "下载", "章节加载中，请稍后再试")
            return
        
        self.download_requested.emit(self._selected_comic, self._comic_chapters)
    
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
    
    def _on_api_endpoint_changed(self, text: str) -> None:
        """Handle API endpoint change."""
        endpoint = self.api_combo.currentData()
        if endpoint:
            self.wrapper.set_endpoint(endpoint)
    
    def _on_image_server_changed(self, text: str) -> None:
        """Handle image server change."""
        server = self.image_combo.currentData()
        if server:
            self.wrapper.set_image_server(server)
    
    def _test_api_endpoints(self) -> None:
        """Test API endpoints speed."""
        self.api_test_button.setEnabled(False)
        self.api_test_button.setText("测试中")
        self.wrapper.test_endpoints()
    
    def _test_image_servers(self) -> None:
        """Test image servers speed."""
        self.image_test_button.setEnabled(False)
        self.image_test_button.setText("测试中")
        self.wrapper.test_image_servers()
    
    def _on_endpoint_test_completed(self, results: dict) -> None:
        """Handle endpoint test completion."""
        self.api_test_button.setEnabled(True)
        self.api_test_button.setText("测速")
        
        # Find fastest endpoint
        fastest_endpoint = None
        fastest_time = float('inf')
        
        for endpoint, time_ms in results.items():
            if time_ms > 0 and time_ms < fastest_time:
                fastest_time = time_ms
                fastest_endpoint = endpoint
        
        if fastest_endpoint:
            # Update combo box to show fastest
            for i in range(self.api_combo.count()):
                if self.api_combo.itemData(i) == fastest_endpoint:
                    self.api_combo.setCurrentIndex(i)
                    break
            
            QMessageBox.information(
                self,
                "测速完成",
                f"最快的API服务器: {fastest_endpoint}\n响应时间: {fastest_time:.0f}ms"
            )
        else:
            QMessageBox.warning(self, "测速失败", "所有API服务器都无法连接")
    
    def _on_image_server_test_completed(self, results: dict) -> None:
        """Handle image server test completion."""
        self.image_test_button.setEnabled(True)
        self.image_test_button.setText("测速")
        
        # Find fastest server
        fastest_server = None
        fastest_time = float('inf')
        
        for server, time_ms in results.items():
            if time_ms > 0 and time_ms < fastest_time:
                fastest_time = time_ms
                fastest_server = server
        
        if fastest_server:
            # Update combo box to show fastest
            for i in range(self.image_combo.count()):
                if self.image_combo.itemData(i) == fastest_server:
                    self.image_combo.setCurrentIndex(i)
                    break
            
            QMessageBox.information(
                self,
                "测速完成",
                f"最快的图片服务器: {fastest_server}\n响应时间: {fastest_time:.0f}ms"
            )
        else:
            QMessageBox.warning(self, "测速失败", "所有图片服务器都无法连接")
    
    def get_wrapper(self) -> PicACGWrapper:
        """Get the PicACG wrapper."""
        return self.wrapper
    
    def cleanup(self) -> None:
        """Clean up resources."""
        if hasattr(self, 'wrapper'):
            self.wrapper.cleanup()