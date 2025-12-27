"""Comic detail dialog showing full comic metadata and chapter list."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QListWidget, QListWidgetItem, QTextEdit
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from typing import Optional, List

from pancomic.models.comic import Comic
from pancomic.models.chapter import Chapter


class ComicDetailDialog(QDialog):
    """Dialog displaying full comic metadata and chapter list."""
    
    # Signals
    chapter_clicked = Signal(object)  # Chapter
    favorite_clicked = Signal(object)  # Comic
    download_clicked = Signal(object, list)  # Comic, List[Chapter]
    
    def __init__(self, comic: Comic, chapters: Optional[List[Chapter]] = None, parent: Optional[QWidget] = None):
        """
        Initialize ComicDetailDialog.
        
        Args:
            comic: Comic object with metadata
            chapters: List of chapters (optional)
            parent: Parent widget
        """
        super().__init__(parent)
        self.comic = comic
        self.chapters = chapters or []
        
        self.setWindowTitle(comic.title)
        self.setMinimumSize(800, 600)
        
        self._setup_ui()
        self._load_data()
    
    def _setup_ui(self) -> None:
        """Initialize UI layout."""
        main_layout = QVBoxLayout(self)
        
        # Create scroll area for content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Content widget
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)
        content_layout.setContentsMargins(20, 20, 20, 20)
        
        # Top section: Cover and basic info
        top_layout = QHBoxLayout()
        
        # Cover image
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(180, 240)
        self.cover_label.setScaledContents(True)
        self.cover_label.setStyleSheet("border: 1px solid #ccc; border-radius: 8px;")
        top_layout.addWidget(self.cover_label)
        
        # Basic info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(10)
        
        # Title
        self.title_label = QLabel()
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        info_layout.addWidget(self.title_label)
        
        # Author
        self.author_label = QLabel()
        self.author_label.setStyleSheet("font-size: 14px; color: #666;")
        info_layout.addWidget(self.author_label)
        
        # Status
        self.status_label = QLabel()
        self.status_label.setStyleSheet("font-size: 12px;")
        info_layout.addWidget(self.status_label)
        
        # Stats (chapters, views, likes)
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("font-size: 12px; color: #888;")
        info_layout.addWidget(self.stats_label)
        
        # Categories
        self.categories_label = QLabel()
        self.categories_label.setWordWrap(True)
        self.categories_label.setStyleSheet("font-size: 12px;")
        info_layout.addWidget(self.categories_label)
        
        # Tags
        self.tags_label = QLabel()
        self.tags_label.setWordWrap(True)
        self.tags_label.setStyleSheet("font-size: 12px;")
        info_layout.addWidget(self.tags_label)
        
        info_layout.addStretch()
        top_layout.addLayout(info_layout, 1)
        
        content_layout.addLayout(top_layout)
        
        # Description section
        desc_title = QLabel("简介:")
        desc_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        content_layout.addWidget(desc_title)
        
        self.description_text = QTextEdit()
        self.description_text.setReadOnly(True)
        self.description_text.setMaximumHeight(100)
        content_layout.addWidget(self.description_text)
        
        # Chapter list section
        chapter_title = QLabel("章节列表:")
        chapter_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        content_layout.addWidget(chapter_title)
        
        self.chapter_list = QListWidget()
        self.chapter_list.setMinimumHeight(200)
        self.chapter_list.itemClicked.connect(self._on_chapter_item_clicked)
        content_layout.addWidget(self.chapter_list)
        
        # Set content widget to scroll area
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        
        # Action buttons at bottom
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.favorite_button = QPushButton("收藏")
        self.favorite_button.clicked.connect(self._on_favorite_clicked)
        button_layout.addWidget(self.favorite_button)
        
        self.download_button = QPushButton("下载")
        self.download_button.clicked.connect(self._on_download_clicked)
        button_layout.addWidget(self.download_button)
        
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.close)
        button_layout.addWidget(close_button)
        
        main_layout.addLayout(button_layout)
    
    def _load_data(self) -> None:
        """Load comic data into UI components."""
        # Set title
        self.title_label.setText(self.comic.title)
        
        # Set author
        self.author_label.setText(f"作者: {self.comic.author}")
        
        # Set status
        status_text = "连载中" if self.comic.status == "ongoing" else "已完结"
        self.status_label.setText(f"状态: {status_text}")
        
        # Set stats
        stats_parts = []
        if self.comic.chapter_count > 0:
            stats_parts.append(f"{self.comic.chapter_count} 章")
        if self.comic.view_count > 0:
            stats_parts.append(f"{self.comic.view_count} 阅读")
        if self.comic.like_count > 0:
            stats_parts.append(f"{self.comic.like_count} 点赞")
        self.stats_label.setText(" | ".join(stats_parts))
        
        # Set categories
        if self.comic.categories:
            categories_text = "分类: " + ", ".join(self.comic.categories)
            self.categories_label.setText(categories_text)
        else:
            self.categories_label.hide()
        
        # Set tags
        if self.comic.tags:
            tags_text = "标签: " + ", ".join(self.comic.tags)
            self.tags_label.setText(tags_text)
        else:
            self.tags_label.hide()
        
        # Set description
        self.description_text.setPlainText(self.comic.description)
        
        # Update favorite button
        if self.comic.is_favorite:
            self.favorite_button.setText("取消收藏")
        else:
            self.favorite_button.setText("收藏")
        
        # Load cover image (placeholder for now)
        # In a real implementation, this would load from cache or download
        self.cover_label.setText("封面加载中...")
        self.cover_label.setAlignment(Qt.AlignCenter)
        
        # Load chapters
        self._load_chapters()
    
    def _load_chapters(self) -> None:
        """Load chapters into the chapter list."""
        self.chapter_list.clear()
        
        if not self.chapters:
            item = QListWidgetItem("暂无章节")
            item.setFlags(Qt.ItemIsEnabled)  # Not selectable
            self.chapter_list.addItem(item)
            return
        
        for chapter in self.chapters:
            # Format chapter text
            chapter_text = f"第 {chapter.chapter_number} 话"
            if chapter.title:
                chapter_text += f" - {chapter.title}"
            if chapter.is_downloaded:
                chapter_text += " [已下载]"
            
            item = QListWidgetItem(chapter_text)
            item.setData(Qt.UserRole, chapter)  # Store chapter object
            self.chapter_list.addItem(item)
    
    def _on_chapter_item_clicked(self, item: QListWidgetItem) -> None:
        """
        Handle chapter item click.
        
        Args:
            item: Clicked list item
        """
        chapter = item.data(Qt.UserRole)
        if chapter:
            self.chapter_clicked.emit(chapter)
    
    def _on_favorite_clicked(self) -> None:
        """Handle favorite button click."""
        self.favorite_clicked.emit(self.comic)
        
        # Toggle button text
        if self.comic.is_favorite:
            self.favorite_button.setText("收藏")
            self.comic.is_favorite = False
        else:
            self.favorite_button.setText("取消收藏")
            self.comic.is_favorite = True
    
    def _on_download_clicked(self) -> None:
        """Handle download button click."""
        # Download all chapters
        self.download_clicked.emit(self.comic, self.chapters)
    
    def set_cover_image(self, pixmap: QPixmap) -> None:
        """
        Set the cover image.
        
        Args:
            pixmap: Cover image pixmap
        """
        if not pixmap.isNull():
            self.cover_label.setPixmap(pixmap)
        else:
            self.cover_label.setText("封面加载失败")
            self.cover_label.setAlignment(Qt.AlignCenter)
    
    def update_chapters(self, chapters: List[Chapter]) -> None:
        """
        Update the chapter list.
        
        Args:
            chapters: New list of chapters
        """
        self.chapters = chapters
        self._load_chapters()
