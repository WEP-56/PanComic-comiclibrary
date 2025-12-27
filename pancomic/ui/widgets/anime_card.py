"""Anime card widget for displaying anime information from Bangumi."""

from typing import Optional, List, Callable
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QThread, QObject
from PySide6.QtGui import QPixmap, QMouseEvent, QPainter, QColor, QFont
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from pancomic.models.anime import Anime
from pancomic.infrastructure.image_cache import ImageCache


class AnimeImageLoader(QObject):
    """Worker for loading anime cover images asynchronously."""
    
    image_loaded = Signal(QPixmap)
    load_failed = Signal()
    
    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.url = url
        self._network_manager = QNetworkAccessManager(self)
        self._network_manager.finished.connect(self._on_download_finished)
    
    def load(self) -> None:
        """Start loading the image."""
        cache = ImageCache.instance()
        cached_pixmap = cache.get_image(self.url)
        
        if cached_pixmap is not None:
            self.image_loaded.emit(cached_pixmap)
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
                cache = ImageCache.instance()
                cache.cache_image(self.url, pixmap)
                self.image_loaded.emit(pixmap)
            else:
                self.load_failed.emit()
        else:
            self.load_failed.emit()
        reply.deleteLater()


class ClickableTagLabel(QLabel):
    """Tag label that emits signals on click."""
    
    include_clicked = Signal(str)  # Tag name
    exclude_clicked = Signal(str)  # Tag name
    
    def __init__(self, tag: str, parent=None):
        super().__init__(tag, parent)
        self.tag = tag
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
                background-color: #4a4a4a;
            }
        """)
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.include_clicked.emit(self.tag)
        elif event.button() == Qt.MouseButton.RightButton:
            self.exclude_clicked.emit(self.tag)
        super().mousePressEvent(event)


class AnimeCard(QWidget):
    """
    Anime card widget displaying cover, rating, date, episodes, title, and tags.
    
    Layout (top to bottom):
    - Cover image with rank badge and rating overlay
    - Date + Episodes bar
    - Title (name)
    - Original name (name_cn)
    - Tags (clickable)
    """
    
    clicked = Signal()
    double_clicked = Signal()
    right_clicked = Signal()
    tag_include_requested = Signal(str)  # Tag to include in filter
    tag_exclude_requested = Signal(str)  # Tag to exclude from filter
    
    def __init__(self, anime: Anime, parent=None):
        super().__init__(parent)
        
        self.anime = anime
        self._hovered = False
        self._cover_pixmap: Optional[QPixmap] = None
        self._loader_thread: Optional[QThread] = None
        self._image_loader: Optional[AnimeImageLoader] = None
        
        self._setup_ui()
        self.load_cover()
        self.setMouseTracking(True)
    
    def _setup_ui(self) -> None:
        """Initialize UI components and layout."""
        # Card width fixed, height flexible
        self.setFixedWidth(200)
        self.setMinimumHeight(350)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(0)
        
        # Cover container (for overlay badges)
        self.cover_container = QWidget()
        self.cover_container.setFixedSize(200, 260)
        cover_layout = QVBoxLayout(self.cover_container)
        cover_layout.setContentsMargins(0, 0, 0, 0)
        cover_layout.setSpacing(0)
        
        # Cover image label
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(200, 260)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setScaledContents(False)
        self.cover_label.setText("加载中...")
        self.cover_label.setStyleSheet("""
            QLabel {
                background-color: #2b2b2b;
                border-radius: 8px;
                border: 1px solid #3a3a3a;
                color: #888888;
                font-size: 12px;
            }
        """)
        cover_layout.addWidget(self.cover_label)
        
        layout.addWidget(self.cover_container)
        
        # Separator line
        self._add_separator(layout)
        
        # Date + Episodes bar
        info_bar = QWidget()
        info_bar.setFixedHeight(24)
        info_layout = QHBoxLayout(info_bar)
        info_layout.setContentsMargins(8, 4, 8, 4)
        info_layout.setSpacing(8)
        
        # Date
        date_text = self.anime.air_date if self.anime.air_date else "未知"
        self.date_label = QLabel(f"📅 {date_text}")
        self.date_label.setStyleSheet("color: #aaaaaa; font-size: 11px; background: transparent;")
        info_layout.addWidget(self.date_label)
        
        info_layout.addStretch()
        
        # Episodes
        eps_text = f"{self.anime.eps_count}集" if self.anime.eps_count > 0 else ""
        if eps_text:
            self.eps_label = QLabel(f"🎬 {eps_text}")
            self.eps_label.setStyleSheet("color: #aaaaaa; font-size: 11px; background: transparent;")
            info_layout.addWidget(self.eps_label)
        
        layout.addWidget(info_bar)
        
        # Separator line
        self._add_separator(layout)
        
        # Title (name)
        self.title_label = QLabel(self.anime.name or "无标题")
        self.title_label.setWordWrap(True)
        self.title_label.setMaximumHeight(40)
        self.title_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 13px;
                font-weight: bold;
                padding: 4px 8px;
                background: transparent;
            }
        """)
        layout.addWidget(self.title_label)
        
        # Separator line
        self._add_separator(layout)
        
        # Original name (name_cn)
        if self.anime.name_cn and self.anime.name_cn != self.anime.name:
            self.original_label = QLabel(self.anime.name_cn)
            self.original_label.setWordWrap(True)
            self.original_label.setMaximumHeight(30)
            self.original_label.setStyleSheet("""
                QLabel {
                    color: #888888;
                    font-size: 11px;
                    padding: 2px 8px;
                    background: transparent;
                }
            """)
            layout.addWidget(self.original_label)
            self._add_separator(layout)
        
        # Tags container
        self.tags_container = QWidget()
        tags_layout = QHBoxLayout(self.tags_container)
        tags_layout.setContentsMargins(8, 4, 8, 4)
        tags_layout.setSpacing(4)
        tags_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        # Add up to 4 tags
        for tag in self.anime.tags[:4]:
            tag_label = ClickableTagLabel(tag)
            tag_label.include_clicked.connect(self._on_tag_include)
            tag_label.exclude_clicked.connect(self._on_tag_exclude)
            tags_layout.addWidget(tag_label)
        
        if len(self.anime.tags) > 4:
            more_label = QLabel(f"+{len(self.anime.tags) - 4}")
            more_label.setStyleSheet("""
                QLabel {
                    color: #666666;
                    font-size: 10px;
                    background: transparent;
                }
            """)
            tags_layout.addWidget(more_label)
        
        tags_layout.addStretch()
        layout.addWidget(self.tags_container)
        
        layout.addStretch()
        
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("AnimeCard { background-color: #252525; border-radius: 8px; }")
    
    def _add_separator(self, layout: QVBoxLayout) -> None:
        """Add a horizontal separator line."""
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #3a3a3a;")
        layout.addWidget(line)
    
    def _on_tag_include(self, tag: str) -> None:
        self.tag_include_requested.emit(tag)
    
    def _on_tag_exclude(self, tag: str) -> None:
        self.tag_exclude_requested.emit(tag)
    
    def load_cover(self) -> None:
        """Load cover image asynchronously."""
        if not self.anime.cover_url:
            return
        
        self._loader_thread = QThread()
        self._image_loader = AnimeImageLoader(self.anime.cover_url)
        self._image_loader.moveToThread(self._loader_thread)
        
        self._loader_thread.started.connect(self._image_loader.load)
        self._image_loader.image_loaded.connect(self._on_cover_loaded)
        self._image_loader.load_failed.connect(self._on_cover_failed)
        
        self._loader_thread.start()
    
    def _on_cover_loaded(self, pixmap: QPixmap) -> None:
        self._cover_pixmap = pixmap
        
        scaled_pixmap = pixmap.scaled(
            200, 260,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )
        
        # Crop to fit
        if scaled_pixmap.width() > 200 or scaled_pixmap.height() > 260:
            x = (scaled_pixmap.width() - 200) // 2
            y = (scaled_pixmap.height() - 260) // 2
            scaled_pixmap = scaled_pixmap.copy(x, y, 200, 260)
        
        self.cover_label.setPixmap(scaled_pixmap)
        self.cover_label.setStyleSheet("""
            QLabel {
                background-color: #2b2b2b;
                border-radius: 8px;
                border: 1px solid #3a3a3a;
            }
        """)
        
        # Draw overlays
        self._draw_overlays()
        
        if self._loader_thread:
            self._loader_thread.quit()
            self._loader_thread.wait()
            self._loader_thread = None
        self._image_loader = None
    
    def _draw_overlays(self) -> None:
        """Draw rank badge and rating on cover."""
        if not self._cover_pixmap:
            return
        
        pixmap = self.cover_label.pixmap()
        if not pixmap:
            return
        
        # Create a copy to draw on
        result = QPixmap(pixmap)
        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw rank badge (top-left)
        if self.anime.rank > 0:
            badge_color = QColor("#0078d4")
            painter.setBrush(badge_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(8, 8, 40, 24, 4, 4)
            
            painter.setPen(QColor("#ffffff"))
            font = QFont("Segoe UI", 10, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(8, 8, 40, 24, Qt.AlignmentFlag.AlignCenter, f"#{self.anime.rank}")
        
        # Draw rating (bottom-right)
        if self.anime.rating > 0:
            rating_bg = QColor(0, 0, 0, 180)
            painter.setBrush(rating_bg)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(result.width() - 58, result.height() - 32, 50, 24, 4, 4)
            
            painter.setPen(QColor("#ffd700"))
            font = QFont("Segoe UI", 11, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(
                result.width() - 58, result.height() - 32, 50, 24,
                Qt.AlignmentFlag.AlignCenter,
                f"★{self.anime.rating:.1f}"
            )
        
        painter.end()
        self.cover_label.setPixmap(result)
    
    def _on_cover_failed(self) -> None:
        self.cover_label.setText("加载失败")
        self.cover_label.setStyleSheet("""
            QLabel {
                background-color: #2b2b2b;
                border-radius: 8px;
                border: 1px solid #3a3a3a;
                color: #ff6b6b;
                font-size: 12px;
            }
        """)
        
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
            
            overlay_color = QColor(255, 255, 255, 15)
            painter.fillRect(self.rect(), overlay_color)
            
            pen_color = QColor("#0078d4")
            pen_color.setAlpha(100)
            painter.setPen(pen_color)
            painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 8, 8)
    
    def __del__(self):
        if self._loader_thread and self._loader_thread.isRunning():
            self._loader_thread.quit()
            self._loader_thread.wait()

    def apply_theme(self, theme: str) -> None:
        """Apply theme to anime card."""
        if theme == 'light':
            bg_card = '#FAFAFA'
            text_primary = '#000000'
            text_secondary = '#333333'
            text_muted = '#666666'
            border_color = '#E0E0E0'
        else:
            bg_card = '#252525'
            text_primary = '#ffffff'
            text_secondary = '#cccccc'
            text_muted = '#888888'
            border_color = '#3a3a3a'
        
        # Card background
        self.setStyleSheet(f"AnimeCard {{ background-color: {bg_card}; border-radius: 8px; }}")
        
        # Cover label
        if hasattr(self, 'cover_label'):
            self.cover_label.setStyleSheet(f"""
                QLabel {{
                    background-color: {border_color};
                    border-radius: 8px;
                    border: 1px solid {border_color};
                    color: {text_muted};
                    font-size: 12px;
                }}
            """)
        
        # Date label
        if hasattr(self, 'date_label'):
            self.date_label.setStyleSheet(f"color: {text_secondary}; font-size: 11px; background: transparent;")
        
        # Episodes label
        if hasattr(self, 'eps_label'):
            self.eps_label.setStyleSheet(f"color: {text_secondary}; font-size: 11px; background: transparent;")
        
        # Title label
        if hasattr(self, 'title_label'):
            self.title_label.setStyleSheet(f"""
                QLabel {{
                    color: {text_primary};
                    font-size: 13px;
                    font-weight: bold;
                    padding: 4px 8px;
                    background: transparent;
                }}
            """)
        
        # Original label
        if hasattr(self, 'original_label'):
            self.original_label.setStyleSheet(f"""
                QLabel {{
                    color: {text_muted};
                    font-size: 11px;
                    padding: 2px 8px;
                    background: transparent;
                }}
            """)
