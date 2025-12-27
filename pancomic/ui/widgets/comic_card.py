"""Comic card widget for displaying comic information with chapter support."""

from typing import Optional, List, Dict
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
)
from PySide6.QtCore import Qt, Signal, QThread, QObject
from PySide6.QtGui import QPixmap, QMouseEvent, QPainter, QColor
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from pancomic.models.comic import Comic
from pancomic.infrastructure.image_cache import ImageCache


class ImageLoader(QObject):
    """Worker for loading images asynchronously."""
    
    image_loaded = Signal(QPixmap)
    load_failed = Signal()
    
    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.url = url
        self._network_manager = QNetworkAccessManager(self)
        self._network_manager.finished.connect(self._on_download_finished)
    
    def load(self) -> None:
        cache = ImageCache.instance()
        cached_pixmap = cache.get_image(self.url)
        if cached_pixmap is not None:
            self.image_loaded.emit(cached_pixmap)
            return
        if self.url.startswith('/') or (len(self.url) > 1 and self.url[1] == ':'):
            pixmap = QPixmap(self.url)
            if not pixmap.isNull():
                cache.cache_image(self.url, pixmap)
                self.image_loaded.emit(pixmap)
            else:
                self.load_failed.emit()
            return
        request = QNetworkRequest(self.url)
        request.setAttribute(QNetworkRequest.Attribute.CacheLoadControlAttribute, 
                           QNetworkRequest.CacheLoadControl.PreferCache)
        self._network_manager.get(request)
    
    def _on_download_finished(self, reply: QNetworkReply) -> None:
        if reply.error() == QNetworkReply.NetworkError.NoError:
            data = reply.readAll()
            pixmap = QPixmap()
            if pixmap.loadFromData(data):
                ImageCache.instance().cache_image(self.url, pixmap)
                self.image_loaded.emit(pixmap)
            else:
                self.load_failed.emit()
        else:
            self.load_failed.emit()
        reply.deleteLater()


class ChapterButton(QLabel):
    """Small label button for chapter selection, styled like anime tags."""
    chapter_clicked = Signal(str)
    
    def __init__(self, chapter_id: str, chapter_num: int, parent=None):
        super().__init__(f"第{chapter_num}话", parent)
        self.chapter_id = chapter_id
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._setup_style()
    
    def _setup_style(self):
        self.setStyleSheet("""
            QLabel {
                background-color: #3a3a3a;
                color: #cccccc;
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 10px;
            }
            QLabel:hover {
                background-color: #0078d4;
                color: #ffffff;
            }
        """)
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.chapter_clicked.emit(self.chapter_id)
        super().mousePressEvent(event)


class ExpandButton(QLabel):
    """Clickable expand/collapse button."""
    expand_clicked = Signal()
    
    def __init__(self, count: int, parent=None):
        super().__init__(f"+{count}", parent)
        self.count = count
        self.expanded = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._setup_style()
    
    def _setup_style(self):
        self.setStyleSheet("""
            QLabel {
                background-color: #3a3a3a;
                color: #cccccc;
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 10px;
            }
            QLabel:hover {
                background-color: #0078d4;
                color: #ffffff;
            }
        """)
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.expand_clicked.emit()
        super().mousePressEvent(event)
    
    def set_expanded(self, expanded: bool):
        self.expanded = expanded
        self.setText("-" if expanded else f"+{self.count}")


class ComicCard(QWidget):
    """Comic card with cover, title, and expandable chapter list."""
    
    clicked = Signal()
    double_clicked = Signal()
    right_clicked = Signal()
    chapter_selected = Signal(str)  # chapter_id
    
    MAX_VISIBLE_CHAPTERS = 6
    
    def __init__(self, comic: Comic, chapters: Optional[Dict] = None, parent=None):
        super().__init__(parent)
        self.comic = comic
        self.chapters = chapters or {}
        self._hovered = False
        self._cover_pixmap: Optional[QPixmap] = None
        self._loader_thread: Optional[QThread] = None
        self._image_loader: Optional[ImageLoader] = None
        self._chapters_expanded = False
        self._current_theme = 'dark'
        self._chapter_buttons: List[ChapterButton] = []
        self._hidden_chapters = []
        
        self._setup_ui()
        self.load_cover()
        self.setMouseTracking(True)

    def _setup_ui(self) -> None:
        has_multi_chapters = len(self.chapters) > 1
        base_height = 285 if not has_multi_chapters else 310
        self.setFixedSize(180, base_height)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 5)
        layout.setSpacing(2)
        
        # Cover container with fixed size
        self.cover_label = QLabel(self)
        self.cover_label.setFixedSize(180, 240)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setText("加载中...")
        layout.addWidget(self.cover_label)
        
        # Info container below cover
        info_container = QWidget(self)
        info_layout = QVBoxLayout(info_container)
        info_layout.setContentsMargins(5, 2, 5, 0)
        info_layout.setSpacing(1)
        
        # Title with background for readability
        self.title_label = QLabel(self)
        self.title_label.setFixedHeight(18)
        fm = self.title_label.fontMetrics()
        elided = fm.elidedText(self.comic.title, Qt.TextElideMode.ElideRight, 165)
        self.title_label.setText(elided)
        info_layout.addWidget(self.title_label)
        
        # Author
        self.author_label = QLabel(self)
        self.author_label.setFixedHeight(14)
        elided_author = fm.elidedText(self.comic.author, Qt.TextElideMode.ElideRight, 165)
        self.author_label.setText(elided_author)
        info_layout.addWidget(self.author_label)
        
        layout.addWidget(info_container)
        
        # Chapter row (only if multiple chapters)
        if has_multi_chapters:
            self.chapter_container = QWidget(self)
            self.chapter_layout = QHBoxLayout(self.chapter_container)
            self.chapter_layout.setContentsMargins(5, 2, 5, 0)
            self.chapter_layout.setSpacing(4)
            self.chapter_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
            self._create_chapter_buttons()
            layout.addWidget(self.chapter_container)
        
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_base_style()
    
    def _create_chapter_buttons(self) -> None:
        """Create chapter buttons with expand/collapse support."""
        if not self.chapters:
            return
        
        sorted_chapters = sorted(
            self.chapters.items(),
            key=lambda x: x[1].get('chapter_number', 0)
        )
        
        visible_count = min(len(sorted_chapters), self.MAX_VISIBLE_CHAPTERS)
        
        for i, (chapter_id, chapter_data) in enumerate(sorted_chapters[:visible_count]):
            chapter_num = chapter_data.get('chapter_number', i + 1)
            btn = ChapterButton(chapter_id, chapter_num, self)
            btn.chapter_clicked.connect(self._on_chapter_clicked)
            self._chapter_buttons.append(btn)
            self.chapter_layout.addWidget(btn)
        
        if len(sorted_chapters) > self.MAX_VISIBLE_CHAPTERS:
            self._hidden_chapters = sorted_chapters[self.MAX_VISIBLE_CHAPTERS:]
            self.expand_btn = ExpandButton(len(self._hidden_chapters), self)
            self.expand_btn.expand_clicked.connect(self._toggle_chapters)
            self.chapter_layout.addWidget(self.expand_btn)
        
        self.chapter_layout.addStretch()
    
    def _toggle_chapters(self) -> None:
        """Toggle between showing all chapters and collapsed view."""
        self._chapters_expanded = not self._chapters_expanded
        
        if self._chapters_expanded:
            # Show all hidden chapters
            insert_pos = self.chapter_layout.count() - 2  # Before expand_btn and stretch
            for chapter_id, chapter_data in self._hidden_chapters:
                chapter_num = chapter_data.get('chapter_number', 0)
                btn = ChapterButton(chapter_id, chapter_num, self)
                btn.chapter_clicked.connect(self._on_chapter_clicked)
                self._chapter_buttons.append(btn)
                self.chapter_layout.insertWidget(insert_pos, btn)
                insert_pos += 1
            
            self.expand_btn.set_expanded(True)
            # Adjust card height for expanded view
            extra_rows = (len(self._hidden_chapters) + self.MAX_VISIBLE_CHAPTERS - 1) // self.MAX_VISIBLE_CHAPTERS
            new_height = 310 + (extra_rows * 22)
            self.setFixedHeight(new_height)
        else:
            # Remove extra buttons
            for btn in self._chapter_buttons[self.MAX_VISIBLE_CHAPTERS:]:
                self.chapter_layout.removeWidget(btn)
                btn.deleteLater()
            self._chapter_buttons = self._chapter_buttons[:self.MAX_VISIBLE_CHAPTERS]
            
            self.expand_btn.set_expanded(False)
            self.setFixedHeight(310)
    
    def _on_chapter_clicked(self, chapter_id: str) -> None:
        self.chapter_selected.emit(chapter_id)
    
    def _apply_base_style(self) -> None:
        self.setStyleSheet("ComicCard { background-color: #252525; border-radius: 8px; }")
        self.cover_label.setStyleSheet("""
            QLabel {
                background-color: #2b2b2b;
                border-radius: 8px 8px 0 0;
                color: #888888;
                font-size: 12px;
            }
        """)
        self.title_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 12px;
                font-weight: bold;
                background: transparent;
            }
        """)
        self.author_label.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 10px;
                background: transparent;
            }
        """)

    def load_cover(self) -> None:
        if not self.comic.cover_url:
            self.cover_label.setText("无封面")
            return
        
        self._loader_thread = QThread()
        self._image_loader = ImageLoader(self.comic.cover_url)
        self._image_loader.moveToThread(self._loader_thread)
        
        self._loader_thread.started.connect(self._image_loader.load)
        self._image_loader.image_loaded.connect(self._on_cover_loaded)
        self._image_loader.load_failed.connect(self._on_cover_failed)
        
        self._loader_thread.start()
    
    def _on_cover_loaded(self, pixmap: QPixmap) -> None:
        self._cover_pixmap = pixmap
        scaled = pixmap.scaled(180, 240, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        if scaled.width() > 180 or scaled.height() > 240:
            x = (scaled.width() - 180) // 2
            y = (scaled.height() - 240) // 2
            scaled = scaled.copy(x, y, 180, 240)
        self.cover_label.setPixmap(scaled)
        self.cover_label.setStyleSheet("QLabel { background-color: #2b2b2b; border-radius: 8px 8px 0 0; }")
        self._cleanup_loader()
    
    def _on_cover_failed(self) -> None:
        self.cover_label.setText("加载失败")
        self.cover_label.setStyleSheet("QLabel { background-color: #2b2b2b; border-radius: 8px 8px 0 0; color: #ff6b6b; font-size: 12px; }")
        self._cleanup_loader()
    
    def _cleanup_loader(self) -> None:
        if self._loader_thread:
            self._loader_thread.quit()
            self._loader_thread.wait()
            self._loader_thread = None
        self._image_loader = None
    
    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)
    
    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        elif event.button() == Qt.MouseButton.RightButton:
            self.right_clicked.emit()
        super().mousePressEvent(event)
    
    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)
    
    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self._hovered:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            overlay = QColor(255, 255, 255, 15)
            painter.fillRect(self.rect(), overlay)
            pen_color = QColor("#0078d4")
            pen_color.setAlpha(100)
            painter.setPen(pen_color)
            painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 8, 8)
    
    def apply_theme(self, theme: str) -> None:
        self._current_theme = theme
        if theme == 'light':
            bg_card, bg_cover = '#FAFAFA', '#E0E0E0'
            text_primary, text_secondary = '#000000', '#666666'
            btn_bg, btn_text = '#E0E0E0', '#333333'
        else:
            bg_card, bg_cover = '#252525', '#2b2b2b'
            text_primary, text_secondary = '#ffffff', '#888888'
            btn_bg, btn_text = '#3a3a3a', '#cccccc'
        
        self.setStyleSheet(f"ComicCard {{ background-color: {bg_card}; border-radius: 8px; }}")
        self.cover_label.setStyleSheet(f"QLabel {{ background-color: {bg_cover}; border-radius: 8px 8px 0 0; color: {text_secondary}; font-size: 12px; }}")
        self.title_label.setStyleSheet(f"QLabel {{ color: {text_primary}; font-size: 12px; font-weight: bold; background: transparent; }}")
        self.author_label.setStyleSheet(f"QLabel {{ color: {text_secondary}; font-size: 10px; background: transparent; }}")
        
        btn_style = f"""
            QLabel {{
                background-color: {btn_bg};
                color: {btn_text};
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 10px;
            }}
            QLabel:hover {{
                background-color: #0078d4;
                color: #ffffff;
            }}
        """
        for btn in self._chapter_buttons:
            btn.setStyleSheet(btn_style)
        if hasattr(self, 'expand_btn'):
            self.expand_btn.setStyleSheet(btn_style)
    
    def __del__(self):
        if self._loader_thread and self._loader_thread.isRunning():
            self._loader_thread.quit()
            self._loader_thread.wait()
