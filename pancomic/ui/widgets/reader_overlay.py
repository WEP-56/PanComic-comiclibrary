"""Reader overlay widget that displays over the main window."""

from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt, Signal, QTimer, QPoint, QThread, QObject, QMutex, QMutexLocker
from PySide6.QtGui import QPixmap, QKeyEvent, QPainter, QColor, QWheelEvent, QMouseEvent, QCursor
from typing import Optional, List, Dict
import queue
import threading

from pancomic.models.chapter import Chapter
from pancomic.adapters.base_adapter import BaseSourceAdapter


class ImageLoadWorker(QObject):
    """Worker for loading images in background thread."""
    
    image_loaded = Signal(int, bytes, str)  # page_index, image_data, source_path
    image_failed = Signal(int, str)  # page_index, error_message
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._task_queue = queue.Queue()
        self._stop_flag = False
        self._thread = None
        self._chapter_id = None
        self._descramble_func = None
        
    def set_descramble_func(self, func, chapter_id: str):
        """Set the descramble function and chapter ID."""
        self._descramble_func = func
        self._chapter_id = chapter_id
    
    def start(self):
        """Start the worker thread."""
        self._stop_flag = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
    
    def stop(self):
        """Stop the worker thread."""
        self._stop_flag = True
        # Add a None task to unblock the queue
        self._task_queue.put(None)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
    
    def add_task(self, page_index: int, image_source: str, priority: bool = False):
        """Add an image loading task."""
        self._task_queue.put((page_index, image_source))
    
    def clear_tasks(self):
        """Clear all pending tasks."""
        try:
            while True:
                self._task_queue.get_nowait()
        except queue.Empty:
            pass
    
    def _run(self):
        """Worker thread main loop."""
        while not self._stop_flag:
            try:
                task = self._task_queue.get(timeout=0.5)
                if task is None:
                    continue
                
                page_index, image_source = task
                
                if self._stop_flag:
                    break
                
                # Load the image data (not QPixmap - that must be done in GUI thread)
                image_data, source_path = self._load_image_data(image_source)
                
                if self._stop_flag:
                    break
                
                if image_data:
                    self.image_loaded.emit(page_index, image_data, source_path)
                else:
                    self.image_failed.emit(page_index, "加载失败")
                    
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Image load worker error: {e}")
    
    def _load_image_data(self, source: str) -> tuple:
        """Load image data from source (file path or URL). Returns (bytes, source_path)."""
        from pathlib import Path
        
        # Check if it's a local file path
        source_path = Path(source)
        if source_path.exists() and source_path.is_file():
            try:
                with open(source_path, 'rb') as f:
                    return f.read(), str(source_path)
            except Exception as e:
                print(f"Failed to load local image {source}: {e}")
                return None, source
        
        # Otherwise, it's a URL - download it
        elif source.startswith('http'):
            try:
                import requests
                import urllib3
                
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Linux; Android 7.1.2; DT1901A Build/N2G47O; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/86.0.4240.198 Mobile Safari/537.36',
                    'Referer': 'https://www.jmapiproxyxxx.vip/',
                    'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive'
                }
                
                response = requests.get(source, headers=headers, timeout=15, verify=False)
                if response.status_code == 200 and len(response.content) > 0:
                    # Descramble if needed
                    image_data = response.content
                    if self._descramble_func and self._chapter_id:
                        image_data = self._descramble_func(image_data, source, self._chapter_id)
                    return image_data, source
            except Exception as e:
                print(f"Failed to load remote image {source}: {e}")
        
        return None, source


class LoadingSpinner(QWidget):
    """A simple loading spinner widget."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        self.setFixedSize(60, 60)
        
    def start(self):
        """Start the spinner animation."""
        self._timer.start(50)
        
    def stop(self):
        """Stop the spinner animation."""
        self._timer.stop()
        
    def _rotate(self):
        """Rotate the spinner."""
        self._angle = (self._angle + 30) % 360
        self.update()
        
    def paintEvent(self, event):
        """Paint the spinner."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw spinning arc
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(self._angle)
        
        pen = painter.pen()
        pen.setWidth(4)
        pen.setColor(QColor(255, 255, 255, 200))
        painter.setPen(pen)
        
        # Draw arc segments with varying opacity
        for i in range(8):
            opacity = 255 - i * 30
            pen.setColor(QColor(255, 255, 255, max(opacity, 50)))
            painter.setPen(pen)
            painter.drawLine(0, -20, 0, -10)
            painter.rotate(45)


class ReaderOverlay(QWidget):
    """
    Reader overlay that displays over the main window with semi-transparent background.
    
    This widget covers the entire main window and provides comic reading functionality
    with keyboard navigation and background image preloading.
    """
    
    # Signals
    page_changed = Signal(int)  # Current page number
    reader_closed = Signal()
    
    def __init__(
        self,
        comic_id: str,
        chapter: Chapter,
        adapter: BaseSourceAdapter,
        parent: Optional[QWidget] = None,
        local_mode: bool = False,
        strip_mode: bool = False
    ):
        """
        Initialize ReaderOverlay.
        
        Args:
            comic_id: Comic ID
            chapter: Chapter to read
            adapter: Source adapter for loading images (can be None for local_mode)
            parent: Parent widget (main window)
            local_mode: If True, load images from local storage only
            strip_mode: If True, display images in vertical scroll mode (条漫模式)
        """
        super().__init__(parent)
        self.comic_id = comic_id
        self.chapter = chapter
        self.adapter = adapter
        self.local_mode = local_mode
        self.strip_mode = strip_mode
        
        self.current_page = 0
        self.images: List[str] = []  # List of image URLs or paths
        self.preload_range = 3  # Preload 3 pages ahead and behind
        
        # Image cache for loaded pages
        self.image_cache: Dict[int, QPixmap] = {}
        self._loading_pages: set = set()  # Pages currently being loaded
        
        # Background image loader
        self._image_worker = ImageLoadWorker()
        self._image_worker.image_loaded.connect(self._on_image_loaded)
        self._image_worker.image_failed.connect(self._on_image_failed)
        self._image_worker.set_descramble_func(self._descramble_jmcomic_image, chapter.id)
        self._image_worker.start()
        
        # Zoom state
        self.zoom_factor = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 5.0
        self.zoom_step = 0.1
        
        # Drag state
        self._is_dragging = False
        self._drag_start_pos = None
        self._scroll_start_h = 0
        self._scroll_start_v = 0
        
        # Track if widget is being destroyed
        self._is_closing = False
        
        # Original pixmap for zoom calculations
        self.original_pixmap: Optional[QPixmap] = None
        
        self._setup_ui()
        self._load_chapter()

    def _setup_ui(self) -> None:
        """Initialize UI layout."""
        from PySide6.QtWidgets import QLineEdit, QScrollArea, QStackedWidget
        
        # Make widget cover entire parent
        if self.parent():
            self.setGeometry(self.parent().rect())
        
        # Fullscreen state
        self._is_fullscreen = False
        self._parent_window = None
        
        # Set window flags and attributes
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("""
            ReaderOverlay {
                background-color: rgba(0, 0, 0, 200);
            }
        """)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        
        # Top control bar
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)
        
        # Close button
        self.close_button = QPushButton("✕")
        self.close_button.setFixedSize(32, 32)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 80);
                color: white;
                border: none;
                border-radius: 16px;
                font-size: 14px;
                font-weight: bold;
                min-width: 32px;
                max-width: 32px;
                min-height: 32px;
                max-height: 32px;
            }
            QPushButton:hover { background-color: rgba(255, 80, 80, 200); }
            QPushButton:pressed { background-color: rgba(255, 50, 50, 255); }
        """)
        self.close_button.clicked.connect(self.close_reader)
        
        # Page jump input
        self.page_input = QLineEdit()
        self.page_input.setFixedSize(55, 28)
        self.page_input.setPlaceholderText("页码")
        self.page_input.setAlignment(Qt.AlignCenter)
        self.page_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 80);
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 12px;
                padding: 0 5px;
            }
            QLineEdit:focus { background-color: rgba(255, 255, 255, 120); }
            QLineEdit::placeholder { color: rgba(255, 255, 255, 120); }
        """)
        self.page_input.returnPressed.connect(self._on_page_jump)
        
        # Jump button
        self.jump_button = QPushButton("跳转")
        self.jump_button.setFixedSize(45, 28)
        self.jump_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 120, 212, 180);
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 11px;
                min-width: 45px;
                max-width: 45px;
                min-height: 28px;
                max-height: 28px;
                padding: 0px;
            }
            QPushButton:hover { background-color: rgba(0, 140, 232, 255); }
        """)
        self.jump_button.clicked.connect(self._on_page_jump)
        
        # Fullscreen button
        self.fullscreen_button = QPushButton("⛶")
        self.fullscreen_button.setFixedSize(32, 32)
        self.fullscreen_button.setToolTip("全屏 (F11)")
        self.fullscreen_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 80);
                color: white;
                border: none;
                border-radius: 16px;
                font-size: 16px;
                min-width: 32px;
                max-width: 32px;
                min-height: 32px;
                max-height: 32px;
            }
            QPushButton:hover { background-color: rgba(255, 255, 255, 150); }
        """)
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)
        
        # Chapter title
        self.chapter_title = QLabel(self.chapter.title)
        self.chapter_title.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 14px;
                font-weight: bold;
                background-color: transparent;
            }
        """)
        
        top_bar.addWidget(self.close_button)
        top_bar.addWidget(self.page_input)
        top_bar.addWidget(self.jump_button)
        top_bar.addWidget(self.fullscreen_button)
        top_bar.addStretch()
        top_bar.addWidget(self.chapter_title)
        top_bar.addStretch()
        
        main_layout.addLayout(top_bar)
        
        # Image display area with scroll support
        self.scroll_area = QScrollArea()
        self.scroll_area.setAlignment(Qt.AlignCenter)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
        """)
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.mouseDoubleClickEvent = self._on_area_double_click
        
        # Container for image and loading spinner
        self.image_container = QWidget()
        self.image_container.setStyleSheet("background-color: transparent;")
        container_layout = QVBoxLayout(self.image_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setAlignment(Qt.AlignCenter)
        
        # Loading spinner
        self.loading_spinner = LoadingSpinner()
        self.loading_spinner.hide()
        
        # Loading label
        self.loading_label = QLabel("加载中...")
        self.loading_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 14px;
                background-color: transparent;
            }
        """)
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.hide()
        
        # Image label
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("""
            QLabel {
                background-color: transparent;
                color: white;
                font-size: 18px;
            }
        """)
        self.image_label.setScaledContents(False)
        self.image_label.setMinimumSize(1, 1)
        
        # Override events for zoom, drag and double click
        self.image_label.wheelEvent = self._image_wheel_event
        self.image_label.mousePressEvent = self._on_image_mouse_press
        self.image_label.mouseMoveEvent = self._on_image_mouse_move
        self.image_label.mouseReleaseEvent = self._on_image_mouse_release
        self.image_label.mouseDoubleClickEvent = self._on_image_double_click
        
        container_layout.addWidget(self.loading_spinner, 0, Qt.AlignCenter)
        container_layout.addWidget(self.loading_label, 0, Qt.AlignCenter)
        container_layout.addWidget(self.image_label, 0, Qt.AlignCenter)
        
        self.scroll_area.setWidget(self.image_container)
        main_layout.addWidget(self.scroll_area, 1)
        
        # Bottom control bar
        bottom_bar = QHBoxLayout()
        
        # Navigation buttons
        self.prev_button = QPushButton("◀ 上一页")
        self.next_button = QPushButton("下一页 ▶")
        
        for btn in [self.prev_button, self.next_button]:
            btn.setFixedHeight(40)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 255, 255, 100);
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-size: 14px;
                    padding: 0 20px;
                }
                QPushButton:hover { background-color: rgba(255, 255, 255, 150); }
                QPushButton:pressed { background-color: rgba(255, 255, 255, 200); }
                QPushButton:disabled {
                    background-color: rgba(255, 255, 255, 50);
                    color: rgba(255, 255, 255, 100);
                }
            """)
        
        self.prev_button.clicked.connect(self.prev_page)
        self.next_button.clicked.connect(self.next_page)
        
        # Page indicator
        self.page_indicator = QLabel()
        self.page_indicator.setStyleSheet("""
            QLabel {
                color: white;
                background-color: rgba(0, 0, 0, 150);
                padding: 8px 16px;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
        """)
        
        bottom_bar.addWidget(self.prev_button)
        bottom_bar.addStretch()
        bottom_bar.addWidget(self.page_indicator)
        bottom_bar.addStretch()
        bottom_bar.addWidget(self.next_button)
        
        main_layout.addLayout(bottom_bar)
        
        # Hide navigation controls in strip mode
        if self.strip_mode:
            self.page_input.hide()
            self.jump_button.hide()
            self.prev_button.hide()
            self.next_button.hide()
            self.page_indicator.setText("条漫模式")
            self.scroll_area.setWidgetResizable(True)
        
        # Set focus policy
        self.setFocusPolicy(Qt.StrongFocus)
        
        # Initialize page indicator
        self._update_page_indicator()
        self._update_navigation_buttons()

    def _load_chapter(self) -> None:
        """Load chapter images."""
        self._show_loading("加载章节信息...")
        
        if self.local_mode or (self.chapter.is_downloaded and self.chapter.download_path):
            self._load_local_chapter()
        else:
            self._load_remote_chapter()
    
    def _load_local_chapter(self) -> None:
        """Load chapter from local storage."""
        from pathlib import Path
        
        if not self.chapter.download_path:
            self._show_error("本地路径未找到")
            return
        
        chapter_path = Path(self.chapter.download_path)
        if not chapter_path.exists():
            self._show_error(f"本地文件不存在: {chapter_path}")
            return
        
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
        
        try:
            image_files = []
            for f in chapter_path.iterdir():
                if f.is_file() and f.suffix.lower() in image_extensions:
                    image_files.append(str(f))
            
            image_files.sort(key=lambda x: Path(x).name)
            self.images = image_files
            
            if self.images:
                if self.strip_mode:
                    self._show_strip_mode()
                else:
                    self._start_preloading()
                    self.show_page(0)
            else:
                self._show_error("未找到图片文件")
        except Exception as e:
            self._show_error(f"加载本地章节失败: {str(e)}")
    
    def _load_remote_chapter(self) -> None:
        """Load chapter from remote source via adapter."""
        try:
            if hasattr(self.adapter, 'images_completed'):
                self.adapter.images_completed.connect(self._on_images_loaded)
            self.adapter.get_chapter_images(self.comic_id, self.chapter.id)
        except (RuntimeError, AttributeError) as e:
            self._show_error(f"加载失败: {str(e)}")
    
    def _on_images_loaded(self, images: List[str]) -> None:
        """Handle images loaded from adapter."""
        self.images = images
        
        if self.images:
            if self.strip_mode:
                self._show_strip_mode()
            else:
                # Start preloading all images in background
                self._start_preloading()
                self.show_page(0)
        else:
            self._show_error("未找到图片")
    
    def _start_preloading(self) -> None:
        """Start preloading images in background."""
        if not self.images:
            return
        
        # Queue all images for preloading, starting from current page
        for i in range(len(self.images)):
            if i not in self.image_cache and i not in self._loading_pages:
                self._loading_pages.add(i)
                self._image_worker.add_task(i, self.images[i])
    
    def _on_image_loaded(self, page_index: int, image_data: bytes, source_path: str) -> None:
        """Handle image loaded from background worker."""
        if self._is_closing:
            return
        
        # Create QPixmap in GUI thread
        pixmap = QPixmap()
        if pixmap.loadFromData(image_data):
            if not pixmap.isNull() and pixmap.width() > 0 and pixmap.height() > 0:
                self._loading_pages.discard(page_index)
                self.image_cache[page_index] = pixmap
                
                # If this is the current page, display it
                if page_index == self.current_page:
                    self._display_image(pixmap)
                    self._update_page_indicator()
                    self._update_navigation_buttons()
                return
        
        # Failed to create pixmap
        self._loading_pages.discard(page_index)
        if page_index == self.current_page:
            self._show_error(f"第 {page_index + 1} 页加载失败\n点击重试")
    
    def _on_image_failed(self, page_index: int, error: str) -> None:
        """Handle image load failure."""
        if self._is_closing:
            return
        
        self._loading_pages.discard(page_index)
        
        # If this is the current page, show error
        if page_index == self.current_page:
            self._show_error(f"第 {page_index + 1} 页加载失败\n点击重试")
    
    def _show_loading(self, message: str = "加载中...") -> None:
        """Show loading state."""
        self.image_label.clear()
        self.image_label.hide()
        self.loading_label.setText(message)
        self.loading_label.show()
        self.loading_spinner.show()
        self.loading_spinner.start()
    
    def _hide_loading(self) -> None:
        """Hide loading state."""
        self.loading_spinner.stop()
        self.loading_spinner.hide()
        self.loading_label.hide()
        self.image_label.show()
    
    def _show_error(self, message: str) -> None:
        """Show error message."""
        self._hide_loading()
        self.image_label.setText(message)
    
    def _display_image(self, pixmap: QPixmap) -> None:
        """Display the given pixmap."""
        self._hide_loading()
        self.image_label.clear()
        
        self.original_pixmap = pixmap
        self.zoom_factor = 1.0
        self._update_image_display()
    
    def show_page(self, page: int) -> None:
        """Display a specific page."""
        if self._is_closing:
            return
        
        if not self.images or page < 0 or page >= len(self.images):
            return
        
        self.current_page = page
        self._update_page_indicator()
        self._update_navigation_buttons()
        
        # Check if image is in cache
        if page in self.image_cache:
            cached_pixmap = self.image_cache[page]
            if not cached_pixmap.isNull():
                self._display_image(cached_pixmap)
                self.page_changed.emit(page)
                return
        
        # Show loading and request image
        self._show_loading(f"加载第 {page + 1} 页...")
        
        # If not already loading, add to queue with priority
        if page not in self._loading_pages:
            self._loading_pages.add(page)
            self._image_worker.add_task(page, self.images[page], priority=True)
        
        self.page_changed.emit(page)
    
    def _show_strip_mode(self) -> None:
        """Display all images in vertical strip mode."""
        from PySide6.QtWidgets import QWidget, QVBoxLayout, QApplication
        
        if self._is_closing or not self.images:
            return
        
        strip_container = QWidget()
        strip_layout = QVBoxLayout(strip_container)
        strip_layout.setContentsMargins(0, 0, 0, 0)
        strip_layout.setSpacing(0)
        strip_layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        
        available_width = self.scroll_area.viewport().width() - 20
        if available_width <= 0:
            available_width = 800
        
        self.page_indicator.setText(f"加载中... 0/{len(self.images)}")
        
        for i, image_source in enumerate(self.images):
            pixmap = self._load_image_sync(image_source)
            
            if pixmap and not pixmap.isNull():
                if pixmap.width() > available_width:
                    scaled_pixmap = pixmap.scaledToWidth(available_width, Qt.SmoothTransformation)
                else:
                    scaled_pixmap = pixmap
                
                img_label = QLabel()
                img_label.setPixmap(scaled_pixmap)
                img_label.setAlignment(Qt.AlignCenter)
                img_label.setStyleSheet("background-color: transparent;")
                strip_layout.addWidget(img_label)
            
            if (i + 1) % 5 == 0 or i == len(self.images) - 1:
                self.page_indicator.setText(f"加载中... {i + 1}/{len(self.images)}")
                QApplication.processEvents()
        
        self.scroll_area.setWidget(strip_container)
        self.scroll_area.setWidgetResizable(False)
        
        strip_container.setMouseTracking(True)
        strip_container.mousePressEvent = self._on_strip_mouse_press
        strip_container.mouseMoveEvent = self._on_strip_mouse_move
        strip_container.mouseReleaseEvent = self._on_strip_mouse_release
        
        self.page_indicator.setText(f"条漫模式 · 共 {len(self.images)} 张")
        self._strip_container = strip_container
    
    def _load_image_sync(self, source: str) -> QPixmap:
        """Synchronously load image (for strip mode)."""
        from pathlib import Path
        
        source_path = Path(source)
        if source_path.exists() and source_path.is_file():
            try:
                pixmap = QPixmap(str(source_path))
                if not pixmap.isNull():
                    return pixmap
            except Exception:
                return QPixmap()
        
        elif source.startswith('http'):
            try:
                import requests
                import urllib3
                
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Linux; Android 7.1.2; DT1901A Build/N2G47O; wv) AppleWebKit/537.36',
                    'Referer': 'https://www.jmapiproxyxxx.vip/',
                    'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                }
                
                response = requests.get(source, headers=headers, timeout=15, verify=False)
                if response.status_code == 200 and len(response.content) > 0:
                    image_data = self._descramble_jmcomic_image(response.content, source, self.chapter.id)
                    
                    pixmap = QPixmap()
                    if pixmap.loadFromData(image_data):
                        return pixmap
            except Exception:
                pass
        
        return QPixmap()

    def _descramble_jmcomic_image(self, image_data: bytes, image_url: str, chapter_id: str) -> bytes:
        """Descramble JMComic segmented images."""
        try:
            import re
            import sys
            import os
            
            jmcomic_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
                'forapi', 'jmcomic', 'src'
            )
            if jmcomic_path not in sys.path:
                sys.path.insert(0, jmcomic_path)
            
            from tools.tool import ToolUtil
            
            match = re.search(r'/media/photos/(\d+)/([^/]+)', image_url)
            if not match:
                return image_data
            
            eps_id = match.group(1)
            image_name = match.group(2)
            picture_name = image_name.split('.')[0] if '.' in image_name else image_name
            scramble_id = chapter_id
            
            descrambled_data = ToolUtil.SegmentationPicture(
                image_data, eps_id, scramble_id, picture_name
            )
            
            return descrambled_data
            
        except Exception as e:
            print(f"Failed to descramble image: {e}")
            return image_data
    
    def _on_strip_mouse_press(self, event) -> None:
        """Handle mouse press on strip container."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self._drag_start_pos = event.globalPosition().toPoint()
            self._scroll_start_v = self.scroll_area.verticalScrollBar().value()
            self.setCursor(QCursor(Qt.ClosedHandCursor))
    
    def _on_strip_mouse_move(self, event) -> None:
        """Handle mouse move on strip container."""
        if self._is_dragging and self._drag_start_pos is not None:
            current_pos = event.globalPosition().toPoint()
            delta_y = current_pos.y() - self._drag_start_pos.y()
            self.scroll_area.verticalScrollBar().setValue(self._scroll_start_v - delta_y)
    
    def _on_strip_mouse_release(self, event) -> None:
        """Handle mouse release on strip container."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False
            self._drag_start_pos = None
            self.setCursor(QCursor(Qt.ArrowCursor))
    
    def next_page(self) -> None:
        """Navigate to the next page."""
        if self.current_page < len(self.images) - 1:
            self.show_page(self.current_page + 1)
    
    def prev_page(self) -> None:
        """Navigate to the previous page."""
        if self.current_page > 0:
            self.show_page(self.current_page - 1)
    
    def close_reader(self) -> None:
        """Close the reader overlay."""
        self._is_closing = True
        
        # Stop the image worker
        self._image_worker.stop()
        
        # Exit fullscreen first if needed
        if self._is_fullscreen:
            self.showNormal()
            self.setWindowFlags(Qt.Widget)
            if self._parent_window:
                self.setParent(self._parent_window)
            self._is_fullscreen = False
        
        self.reader_closed.emit()
        self.hide()
        self.deleteLater()
    
    def _update_page_indicator(self) -> None:
        """Update the page number indicator."""
        if self._is_closing:
            return
        if self.images:
            text = f"{self.current_page + 1} / {len(self.images)}"
            self.page_indicator.setText(text)
        else:
            self.page_indicator.setText("0 / 0")
    
    def _update_navigation_buttons(self) -> None:
        """Update navigation button states."""
        self.prev_button.setEnabled(self.current_page > 0)
        self.next_button.setEnabled(self.current_page < len(self.images) - 1)
    
    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle keyboard events for navigation and zoom."""
        key = event.key()
        modifiers = event.modifiers()
        
        if self.strip_mode:
            scroll_step = 100
            
            if key in (Qt.Key_Down, Qt.Key_Space, Qt.Key_PageDown):
                self.scroll_area.verticalScrollBar().setValue(
                    self.scroll_area.verticalScrollBar().value() + scroll_step
                )
                event.accept()
                return
            elif key in (Qt.Key_Up, Qt.Key_Backspace, Qt.Key_PageUp):
                self.scroll_area.verticalScrollBar().setValue(
                    self.scroll_area.verticalScrollBar().value() - scroll_step
                )
                event.accept()
                return
            elif key == Qt.Key_Home:
                self.scroll_area.verticalScrollBar().setValue(0)
                event.accept()
                return
            elif key == Qt.Key_End:
                self.scroll_area.verticalScrollBar().setValue(
                    self.scroll_area.verticalScrollBar().maximum()
                )
                event.accept()
                return
            elif key == Qt.Key_F11:
                self.toggle_fullscreen()
                event.accept()
                return
            elif key == Qt.Key_Escape:
                if self._is_fullscreen:
                    self.toggle_fullscreen()
                else:
                    self.close_reader()
                event.accept()
                return
            event.accept()
            return
        
        # Normal page mode
        if key in (Qt.Key_Right, Qt.Key_Down, Qt.Key_Space, Qt.Key_PageDown):
            self.next_page()
            event.accept()
            return
        elif key in (Qt.Key_Left, Qt.Key_Up, Qt.Key_Backspace, Qt.Key_PageUp):
            self.prev_page()
            event.accept()
            return
        elif key in (Qt.Key_Plus, Qt.Key_Equal) and modifiers == Qt.ControlModifier:
            self.zoom_in()
            event.accept()
            return
        elif key == Qt.Key_Minus and modifiers == Qt.ControlModifier:
            self.zoom_out()
            event.accept()
            return
        elif key == Qt.Key_0 and (modifiers == Qt.ControlModifier or modifiers == Qt.NoModifier):
            self.reset_zoom()
            event.accept()
            return
        elif key == Qt.Key_Home:
            if self.images:
                self.show_page(0)
            event.accept()
            return
        elif key == Qt.Key_End:
            if self.images:
                self.show_page(len(self.images) - 1)
            event.accept()
            return
        elif key == Qt.Key_F11:
            self.toggle_fullscreen()
            event.accept()
            return
        elif key == Qt.Key_Escape:
            if self._is_fullscreen:
                self.toggle_fullscreen()
            else:
                self.close_reader()
            event.accept()
            return
        
        event.accept()
    
    def _on_page_jump(self) -> None:
        """Handle page jump from input."""
        try:
            page_num = int(self.page_input.text())
            if 1 <= page_num <= len(self.images):
                self.show_page(page_num - 1)
                self.page_input.clear()
            else:
                self.page_input.clear()
                self.page_input.setPlaceholderText(f"1-{len(self.images)}")
        except ValueError:
            self.page_input.clear()
    
    def toggle_fullscreen(self) -> None:
        """Toggle fullscreen mode."""
        if not self._is_fullscreen:
            self._parent_window = self.parent()
            if self._parent_window:
                self._original_geometry = self.geometry()
                self.setParent(None)
                self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
                self.showFullScreen()
                self._is_fullscreen = True
                self.fullscreen_button.setText("⛶")
                self.fullscreen_button.setToolTip("退出全屏 (F11/Esc)")
        else:
            self.showNormal()
            self.setWindowFlags(Qt.Widget)
            if self._parent_window:
                self.setParent(self._parent_window)
                self.setGeometry(self._parent_window.rect())
            self.show()
            self._is_fullscreen = False
            self.fullscreen_button.setText("⛶")
            self.fullscreen_button.setToolTip("全屏 (F11)")
        
        self.setFocus()
        if not self.strip_mode:
            QTimer.singleShot(100, lambda: self.show_page(self.current_page))

    def _on_image_mouse_press(self, event) -> None:
        """Handle mouse press on image."""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.strip_mode:
                self._is_dragging = True
                self._drag_start_pos = event.globalPosition().toPoint()
                self._scroll_start_h = self.scroll_area.horizontalScrollBar().value()
                self._scroll_start_v = self.scroll_area.verticalScrollBar().value()
                self.setCursor(QCursor(Qt.ClosedHandCursor))
                return
            
            can_scroll_h = self.scroll_area.horizontalScrollBar().maximum() > 0
            can_scroll_v = self.scroll_area.verticalScrollBar().maximum() > 0
            
            if can_scroll_h or can_scroll_v:
                self._is_dragging = True
                self._drag_start_pos = event.globalPosition().toPoint()
                self._scroll_start_h = self.scroll_area.horizontalScrollBar().value()
                self._scroll_start_v = self.scroll_area.verticalScrollBar().value()
                self.image_label.setCursor(QCursor(Qt.ClosedHandCursor))
            else:
                # Try retry if image failed
                if self.image_label.text().startswith("第") and "加载失败" in self.image_label.text():
                    if self.current_page in self.image_cache:
                        del self.image_cache[self.current_page]
                    self._loading_pages.discard(self.current_page)
                    self.show_page(self.current_page)
    
    def _on_image_mouse_move(self, event) -> None:
        """Handle mouse move on image."""
        if self._is_dragging and self._drag_start_pos is not None:
            current_pos = event.globalPosition().toPoint()
            delta_x = current_pos.x() - self._drag_start_pos.x()
            delta_y = current_pos.y() - self._drag_start_pos.y()
            
            self.scroll_area.horizontalScrollBar().setValue(self._scroll_start_h - delta_x)
            self.scroll_area.verticalScrollBar().setValue(self._scroll_start_v - delta_y)
    
    def _on_image_mouse_release(self, event) -> None:
        """Handle mouse release on image."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False
            self._drag_start_pos = None
            if self.strip_mode:
                self.setCursor(QCursor(Qt.ArrowCursor))
            else:
                self._update_cursor()
    
    def _update_cursor(self) -> None:
        """Update cursor based on scroll state."""
        if self._is_closing:
            return
        
        if self.strip_mode:
            self.setCursor(QCursor(Qt.ArrowCursor))
            return
        
        can_scroll_h = self.scroll_area.horizontalScrollBar().maximum() > 0
        can_scroll_v = self.scroll_area.verticalScrollBar().maximum() > 0
        
        if can_scroll_h or can_scroll_v:
            self.image_label.setCursor(QCursor(Qt.OpenHandCursor))
        else:
            self.image_label.setCursor(QCursor(Qt.ArrowCursor))
    
    def _on_image_double_click(self, event) -> None:
        """Handle double click on image."""
        self._handle_double_click_navigation(event.position().x(), self.image_label.width())
    
    def _on_area_double_click(self, event) -> None:
        """Handle double click on scroll area."""
        self._handle_double_click_navigation(event.position().x(), self.scroll_area.width())
    
    def _handle_double_click_navigation(self, click_x: float, widget_width: int) -> None:
        """Handle double click navigation."""
        if widget_width <= 0:
            return
        
        relative_x = click_x / widget_width
        
        if relative_x < 0.33:
            self.prev_page()
        elif relative_x > 0.67:
            self.next_page()
    
    def resizeEvent(self, event) -> None:
        """Handle resize event."""
        super().resizeEvent(event)
        
        if self._is_closing:
            return
        
        if self.parent():
            self.setGeometry(self.parent().rect())
        
        if not self.strip_mode and self.images and 0 <= self.current_page < len(self.images):
            QTimer.singleShot(50, self._safe_refresh_page)
    
    def _safe_refresh_page(self) -> None:
        """Safely refresh the current page."""
        if self._is_closing:
            return
        try:
            if self.isVisible() and self.images:
                # Only update display, don't reload
                if self.current_page in self.image_cache:
                    self._update_image_display()
        except RuntimeError:
            pass
    
    def showEvent(self, event) -> None:
        """Handle show event."""
        super().showEvent(event)
        
        if self.parent():
            self.setGeometry(self.parent().rect())
        
        self.setFocus()
    
    def _image_wheel_event(self, event: QWheelEvent) -> None:
        """Handle mouse wheel events on image."""
        if self.strip_mode:
            self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().value() - event.angleDelta().y()
            )
            event.accept()
            return
        
        delta = event.angleDelta().y()
        
        if delta > 0:
            self.zoom_in()
        else:
            self.zoom_out()
        
        event.accept()
    
    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle mouse wheel events."""
        if self.strip_mode:
            self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().value() - event.angleDelta().y()
            )
            event.accept()
            return
        
        delta = event.angleDelta().y()
        
        if delta > 0:
            self.zoom_in()
        else:
            self.zoom_out()
        
        event.accept()
    
    def zoom_in(self) -> None:
        """Zoom in the image."""
        if self.zoom_factor < self.max_zoom:
            self.zoom_factor = min(self.zoom_factor + self.zoom_step, self.max_zoom)
            self._update_image_display()
    
    def zoom_out(self) -> None:
        """Zoom out the image."""
        if self.zoom_factor > self.min_zoom:
            self.zoom_factor = max(self.zoom_factor - self.zoom_step, self.min_zoom)
            self._update_image_display()
    
    def reset_zoom(self) -> None:
        """Reset zoom to fit screen."""
        self.zoom_factor = 1.0
        self._update_image_display()
    
    def _update_image_display(self) -> None:
        """Update the image display with current zoom factor."""
        if not self.original_pixmap:
            return
        
        if self.zoom_factor == 1.0:
            scroll_size = self.scroll_area.size()
            available_width = scroll_size.width() - 50
            available_height = scroll_size.height() - 50
            
            if available_width <= 0 or available_height <= 0:
                if self.parent():
                    parent_size = self.parent().size()
                    available_width = parent_size.width() - 150
                    available_height = parent_size.height() - 250
                else:
                    available_width = 800
                    available_height = 600
            
            original_width = self.original_pixmap.width()
            original_height = self.original_pixmap.height()
            
            if original_width > 0 and original_height > 0:
                width_scale = available_width / original_width
                height_scale = available_height / original_height
                scale_factor = min(width_scale, height_scale, 1.0)
                
                if scale_factor < 1.0:
                    new_width = int(original_width * scale_factor)
                    new_height = int(original_height * scale_factor)
                    scaled_pixmap = self.original_pixmap.scaled(
                        new_width, new_height,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                else:
                    scaled_pixmap = self.original_pixmap
            else:
                scaled_pixmap = self.original_pixmap
        else:
            original_size = self.original_pixmap.size()
            new_size = original_size * self.zoom_factor
            scaled_pixmap = self.original_pixmap.scaled(
                new_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
        
        self.image_label.setPixmap(scaled_pixmap)
        self.image_label.resize(scaled_pixmap.size())
        self.image_container.setMinimumSize(scaled_pixmap.size())
        
        QTimer.singleShot(50, self._update_cursor)
