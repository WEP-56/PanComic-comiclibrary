"""Full-screen comic reader window with keyboard navigation, zoom, and pan."""

from PySide6.QtWidgets import QMainWindow, QLabel, QWidget, QVBoxLayout, QHBoxLayout, QScrollArea
from PySide6.QtCore import Qt, Signal, QTimer, QPoint
from PySide6.QtGui import QPixmap, QKeyEvent, QWheelEvent, QMouseEvent, QCursor
from typing import Optional, List

from pancomic.models.chapter import Chapter
from pancomic.adapters.base_adapter import BaseSourceAdapter


class ReaderWindow(QMainWindow):
    """Full-screen comic reader with page navigation and preloading."""
    
    # Signals
    page_changed = Signal(int)  # Current page number
    reader_closed = Signal()
    
    def __init__(
        self,
        comic_id: str,
        chapter: Chapter,
        adapter: BaseSourceAdapter,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize ReaderWindow.
        
        Args:
            comic_id: Comic ID
            chapter: Chapter to read
            adapter: Source adapter for loading images
            parent: Parent widget
        """
        super().__init__(parent)
        self.comic_id = comic_id
        self.chapter = chapter
        self.adapter = adapter
        
        self.current_page = 0
        self.images: List[str] = []  # List of image URLs or paths
        self.preload_count = 3  # Number of pages to preload in each direction
        
        # Image cache for preloaded pages
        self.image_cache: dict[int, QPixmap] = {}
        
        # Zoom and pan state
        self.zoom_factor = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 5.0
        self.zoom_step = 0.1
        
        # Pan state
        self.is_panning = False
        self.last_pan_point = QPoint()
        self.original_pixmap: Optional[QPixmap] = None
        
        self._setup_ui()
        self._load_chapter()
    
    def _setup_ui(self) -> None:
        """Initialize UI layout."""
        # Set window to fullscreen
        self.setWindowState(Qt.WindowFullScreen)
        self.setWindowTitle(f"{self.chapter.title} - 阅读器")
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Scroll area for zoom and pan
        self.scroll_area = QScrollArea()
        self.scroll_area.setStyleSheet("background-color: #000;")
        self.scroll_area.setAlignment(Qt.AlignCenter)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Image display area
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: #000;")
        self.image_label.setScaledContents(False)  # We'll handle scaling manually
        self.image_label.setMinimumSize(1, 1)
        
        # Enable mouse tracking for pan
        self.image_label.setMouseTracking(True)
        
        self.scroll_area.setWidget(self.image_label)
        main_layout.addWidget(self.scroll_area, 1)
        
        # Control bar at bottom
        control_layout = QHBoxLayout()
        control_layout.setContentsMargins(10, 5, 10, 5)
        
        # Page indicator
        self.page_indicator = QLabel()
        self.page_indicator.setStyleSheet(
            "color: white; background-color: rgba(0, 0, 0, 150); "
            "padding: 5px 10px; border-radius: 4px; font-size: 14px;"
        )
        control_layout.addStretch()
        control_layout.addWidget(self.page_indicator)
        control_layout.addStretch()
        
        main_layout.addLayout(control_layout)
        
        # Set focus policy to receive keyboard events
        self.setFocusPolicy(Qt.StrongFocus)
        
        # Initialize page indicator
        self._update_page_indicator()
    
    def _load_chapter(self) -> None:
        """
        Load chapter images.
        
        Detects if chapter is local or remote and loads accordingly:
        - Local chapters: Load from disk without network requests
        - Remote chapters: Load via adapter with network requests
        """
        # Show loading message
        self.image_label.setText("加载中...")
        self.image_label.setStyleSheet("background-color: #000; color: white; font-size: 18px;")
        
        # Detect if chapter is downloaded (local) or remote
        if self.chapter.is_downloaded and self.chapter.download_path:
            # Load from local storage - no network requests
            self._load_local_chapter()
        else:
            # Load from remote source via adapter
            self._load_remote_chapter()
    
    def _load_local_chapter(self) -> None:
        """Load chapter from local storage without network requests."""
        from pathlib import Path
        
        print(f"[DEBUG] Loading local chapter: {self.chapter.title}")
        print(f"[DEBUG] Chapter ID: {self.chapter.id}")
        print(f"[DEBUG] Download path: {self.chapter.download_path}")
        print(f"[DEBUG] Is downloaded: {self.chapter.is_downloaded}")
        
        if not self.chapter.download_path:
            print("[ERROR] No download path")
            self.image_label.setText("本地路径未找到")
            return
        
        chapter_path = Path(self.chapter.download_path)
        print(f"[DEBUG] Checking path exists: {chapter_path}")
        
        if not chapter_path.exists():
            print(f"[ERROR] Path does not exist: {chapter_path}")
            self.image_label.setText(f"本地文件不存在: {chapter_path}")
            return
        
        # Get all image files in the directory
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
        
        try:
            # Sort files naturally (1, 2, 10 instead of 1, 10, 2)
            image_files = []
            for f in chapter_path.iterdir():
                if f.is_file() and f.suffix.lower() in image_extensions:
                    image_files.append(str(f))
            
            print(f"[DEBUG] Found {len(image_files)} image files")
            
            # Sort by filename (natural sort for page numbers)
            image_files.sort(key=lambda x: Path(x).name)
            
            self.images = image_files
            
            if self.images:
                print(f"[DEBUG] Loading first page: {self.images[0]}")
                self.show_page(0)
            else:
                print("[ERROR] No image files found")
                self.image_label.setText("未找到图片文件")
        except Exception as e:
            print(f"[ERROR] Exception in _load_local_chapter: {e}")
            import traceback
            traceback.print_exc()
            self.image_label.setText(f"加载本地章节失败: {str(e)}")
    
    def _load_remote_chapter(self) -> None:
        """Load chapter from remote source via adapter."""
        # Connect to adapter signal if available
        try:
            if hasattr(self.adapter, 'images_completed'):
                self.adapter.images_completed.connect(self._on_images_loaded)
            
            # Request chapter images
            self.adapter.get_chapter_images(self.comic_id, self.chapter.id)
        except (RuntimeError, AttributeError) as e:
            # Handle case where adapter doesn't support signals or is not properly initialized
            self.image_label.setText(f"加载失败: {str(e)}")
    
    def _on_images_loaded(self, images: List[str]) -> None:
        """
        Handle images loaded from adapter.
        
        Args:
            images: List of image URLs
        """
        self.images = images
        
        if self.images:
            self.show_page(0)
        else:
            self.image_label.setText("未找到图片")
    
    def show_page(self, page: int) -> None:
        """
        Display a specific page.
        
        Args:
            page: Page number (0-indexed)
        """
        if not self.images or page < 0 or page >= len(self.images):
            return
        
        self.current_page = page
        
        # Update page indicator
        self._update_page_indicator()
        
        # Load image
        image_source = self.images[page]
        
        # Check if image is in cache
        if page in self.image_cache:
            pixmap = self.image_cache[page]
        else:
            # Load image
            pixmap = self._load_image(image_source)
            if not pixmap.isNull():
                self.image_cache[page] = pixmap
        
        # Display image
        if not pixmap.isNull():
            self.original_pixmap = pixmap
            self.zoom_factor = 1.0  # Reset zoom when changing pages
            self._update_image_display()
        else:
            self.image_label.setText(f"图片加载失败: 第 {page + 1} 页")
        
        # Preload adjacent pages
        self.preload_pages()
        
        # Emit signal
        self.page_changed.emit(page)
    
    def _load_image(self, source: str) -> QPixmap:
        """
        Load image from source (file path or URL).
        
        For local chapters, loads directly from disk without network requests.
        For remote chapters, would use ImageCache (not implemented in this task).
        
        Args:
            source: Image source (file path or URL)
            
        Returns:
            Loaded pixmap
        """
        from pathlib import Path
        
        # Check if it's a local file path
        source_path = Path(source)
        if source_path.exists() and source_path.is_file():
            # Load from local disk - no network request
            try:
                pixmap = QPixmap(str(source_path))
                if not pixmap.isNull():
                    return pixmap
            except Exception as e:
                print(f"Failed to load local image {source}: {e}")
                return QPixmap()
        
        # Otherwise, it's a URL - would need to download via ImageCache
        # For now, return empty pixmap
        # In a real implementation, this would use ImageCache to download
        return QPixmap()
    
    def preload_pages(self) -> None:
        """Preload adjacent pages for smooth navigation."""
        # Preload next pages
        for i in range(1, self.preload_count + 1):
            page = self.current_page + i
            if page < len(self.images) and page not in self.image_cache:
                image_source = self.images[page]
                pixmap = self._load_image(image_source)
                if not pixmap.isNull():
                    self.image_cache[page] = pixmap
        
        # Preload previous pages
        for i in range(1, self.preload_count + 1):
            page = self.current_page - i
            if page >= 0 and page not in self.image_cache:
                image_source = self.images[page]
                pixmap = self._load_image(image_source)
                if not pixmap.isNull():
                    self.image_cache[page] = pixmap
        
        # Clean up cache for pages far from current
        pages_to_remove = []
        for cached_page in self.image_cache.keys():
            if abs(cached_page - self.current_page) > self.preload_count * 2:
                pages_to_remove.append(cached_page)
        
        for page in pages_to_remove:
            del self.image_cache[page]
    
    def next_page(self) -> None:
        """Navigate to the next page."""
        if self.current_page < len(self.images) - 1:
            self.show_page(self.current_page + 1)
    
    def prev_page(self) -> None:
        """Navigate to the previous page."""
        if self.current_page > 0:
            self.show_page(self.current_page - 1)
    
    def _update_page_indicator(self) -> None:
        """Update the page number indicator."""
        if self.images:
            text = f"{self.current_page + 1} / {len(self.images)}"
            self.page_indicator.setText(text)
        else:
            self.page_indicator.setText("0 / 0")
    
    def keyPressEvent(self, event: QKeyEvent) -> None:
        """
        Handle keyboard events for navigation and zoom.
        
        Args:
            event: Key event
        """
        key = event.key()
        modifiers = event.modifiers()
        
        # Next page: Right arrow, Down arrow, Space, Page Down
        if key in (Qt.Key_Right, Qt.Key_Down, Qt.Key_Space, Qt.Key_PageDown):
            self.next_page()
        
        # Previous page: Left arrow, Up arrow, Backspace, Page Up
        elif key in (Qt.Key_Left, Qt.Key_Up, Qt.Key_Backspace, Qt.Key_PageUp):
            self.prev_page()
        
        # Zoom in: Plus, Equal (for + without shift)
        elif key in (Qt.Key_Plus, Qt.Key_Equal) and modifiers == Qt.ControlModifier:
            self.zoom_in()
        
        # Zoom out: Minus
        elif key == Qt.Key_Minus and modifiers == Qt.ControlModifier:
            self.zoom_out()
        
        # Reset zoom: 0 or Ctrl+0
        elif key == Qt.Key_0 and (modifiers == Qt.ControlModifier or modifiers == Qt.NoModifier):
            self.reset_zoom()
        
        # First page: Home
        elif key == Qt.Key_Home:
            if self.images:
                self.show_page(0)
        
        # Last page: End
        elif key == Qt.Key_End:
            if self.images:
                self.show_page(len(self.images) - 1)
        
        # Close reader: Escape
        elif key == Qt.Key_Escape:
            self.close()
        
        else:
            super().keyPressEvent(event)
    
    def closeEvent(self, event) -> None:
        """
        Handle window close event.
        
        Args:
            event: Close event
        """
        # Clear image cache
        self.image_cache.clear()
        
        # Emit signal
        self.reader_closed.emit()
        
        super().closeEvent(event)
    
    def resizeEvent(self, event) -> None:
        """
        Handle window resize event.
        
        Args:
            event: Resize event
        """
        super().resizeEvent(event)
        
        # Update image display with current zoom
        if self.original_pixmap:
            self._update_image_display()
    
    def wheelEvent(self, event: QWheelEvent) -> None:
        """
        Handle mouse wheel events for zooming.
        
        Args:
            event: Wheel event
        """
        if event.modifiers() == Qt.ControlModifier or True:  # Always allow zoom
            # Get wheel delta
            delta = event.angleDelta().y()
            
            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            
            event.accept()
        else:
            super().wheelEvent(event)
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse press events for panning.
        
        Args:
            event: Mouse event
        """
        if event.button() == Qt.LeftButton and self.zoom_factor > 1.0:
            self.is_panning = True
            self.last_pan_point = event.globalPosition().toPoint()
            self.setCursor(QCursor(Qt.ClosedHandCursor))
            event.accept()
        else:
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse move events for panning.
        
        Args:
            event: Mouse event
        """
        if self.is_panning and event.buttons() == Qt.LeftButton:
            # Calculate pan delta
            current_point = event.globalPosition().toPoint()
            delta = current_point - self.last_pan_point
            self.last_pan_point = current_point
            
            # Update scroll position
            h_scroll = self.scroll_area.horizontalScrollBar()
            v_scroll = self.scroll_area.verticalScrollBar()
            
            h_scroll.setValue(h_scroll.value() - delta.x())
            v_scroll.setValue(v_scroll.value() - delta.y())
            
            event.accept()
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse release events.
        
        Args:
            event: Mouse event
        """
        if event.button() == Qt.LeftButton and self.is_panning:
            self.is_panning = False
            self.setCursor(QCursor(Qt.ArrowCursor))
            event.accept()
        else:
            super().mouseReleaseEvent(event)
    
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
        
        # Calculate display size
        if self.zoom_factor == 1.0:
            # Fit to screen
            available_size = self.scroll_area.size()
            scaled_pixmap = self.original_pixmap.scaled(
                available_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
        else:
            # Use zoom factor
            original_size = self.original_pixmap.size()
            new_size = original_size * self.zoom_factor
            scaled_pixmap = self.original_pixmap.scaled(
                new_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
        
        # Update image label
        self.image_label.setPixmap(scaled_pixmap)
        self.image_label.resize(scaled_pixmap.size())
        
        # Update cursor based on zoom level
        if self.zoom_factor > 1.0:
            self.image_label.setCursor(QCursor(Qt.OpenHandCursor))
        else:
            self.image_label.setCursor(QCursor(Qt.ArrowCursor))
