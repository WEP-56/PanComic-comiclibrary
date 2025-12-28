"""Resource library page for local comics and anime history."""

import os
import json
import webbrowser
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox, QLabel,
    QSplitter, QFrame, QScrollArea, QGridLayout, QMenu, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QCursor

from pancomic.models.comic import Comic
from pancomic.models.anime import Anime
from pancomic.ui.widgets.comic_grid import ComicGrid
from pancomic.ui.widgets.anime_card import AnimeCard
from pancomic.ui.widgets.anime_grid import AnimeGrid
from pancomic.ui.widgets.loading_widget import LoadingWidget
from pancomic.infrastructure.anime_history_manager import AnimeHistoryManager


class LibraryPage(QWidget):
    """
    Resource library page with 50:50 split.
    
    Top half: 我的漫画 (downloaded comics)
    Bottom half: 动漫历史 (saved anime from Bangumi search)
    """
    
    # Signals emitted for comic interactions
    comic_selected = Signal(object)  # Comic object
    comic_read_requested = Signal(object, object)  # Comic, Chapter objects
    comic_delete_requested = Signal(object)  # Comic object
    
    def __init__(self, download_path: str, parent: Optional[QWidget] = None):
        """
        Initialize LibraryPage.
        
        Args:
            download_path: Path to download directory
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.download_path = Path(download_path)
        self.local_comics: List[Comic] = []
        self.filtered_comics: List[Comic] = []
        self._current_filter = ""
        self._current_sort = "date_desc"
        self._chapters_map = {}  # Store chapters for each comic
        
        # Anime history manager
        self.anime_history_manager = AnimeHistoryManager()
        
        # Anime cards list for theme support
        self._anime_cards = []
        
        # Setup UI
        self._setup_ui()
        
        # Initial scan
        self.scan_library()
        self.refresh_anime_history()
        
        # Enable drag and drop
        self.setAcceptDrops(True)
        
        # Current theme (default to dark)
        self._current_theme = 'dark'
    
    def _setup_ui(self) -> None:
        """Initialize UI components and layout."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Create splitter for 50:50 layout
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setHandleWidth(4)
        
        # Top section: 我的漫画
        self.comics_section = self._create_comics_section()
        self.splitter.addWidget(self.comics_section)
        
        # Bottom section: 动漫历史
        self.anime_section = self._create_anime_section()
        self.splitter.addWidget(self.anime_section)
        
        # Set 50:50 ratio
        self.splitter.setSizes([500, 500])
        
        layout.addWidget(self.splitter)
        
        # Apply initial theme
        self.apply_theme('dark')
    
    def apply_theme(self, theme: str) -> None:
        """Apply theme to all components."""
        self._current_theme = theme
        
        if theme == 'light':
            # Light theme colors
            bg_primary = '#FFFFFF'
            bg_secondary = '#F3F3F3'
            bg_header = '#FAFAFA'
            text_primary = '#000000'
            text_secondary = '#333333'
            text_muted = '#666666'
            border_color = '#E0E0E0'
            accent_color = '#0078D4'
        else:
            # Dark theme colors
            bg_primary = '#1e1e1e'
            bg_secondary = '#2b2b2b'
            bg_header = '#2b2b2b'
            text_primary = '#ffffff'
            text_secondary = '#cccccc'
            text_muted = '#888888'
            border_color = '#3a3a3a'
            accent_color = '#0078d4'
        
        # Page background
        self.setStyleSheet(f"""
            LibraryPage {{
                background-color: {bg_primary};
            }}
        """)
        
        # Splitter
        self.splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {border_color};
            }}
            QSplitter::handle:hover {{
                background-color: {accent_color};
            }}
        """)
        
        # Comics section header
        self.comics_header.setStyleSheet(f"background-color: {bg_header}; border-bottom: 1px solid {border_color};")
        self.comics_title.setStyleSheet(f"color: {text_primary}; font-size: 16px; font-weight: bold; background: transparent;")
        self.count_label.setStyleSheet(f"color: {text_muted}; font-size: 12px; background: transparent;")
        
        # Search bar
        self.search_bar.setStyleSheet(f"""
            QLineEdit {{
                background-color: {bg_primary};
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 0 10px;
                color: {text_primary};
                font-size: 12px;
            }}
            QLineEdit:focus {{ border: 1px solid {accent_color}; }}
            QLineEdit::placeholder {{ color: {text_muted}; }}
        """)
        
        # Sort combo
        self.sort_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {bg_primary};
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 0 10px;
                color: {text_primary};
                font-size: 12px;
            }}
            QComboBox:hover {{ border: 1px solid {accent_color}; }}
            QComboBox::drop-down {{ border: none; width: 25px; }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid {text_primary};
                margin-right: 8px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {bg_secondary};
                border: 1px solid {border_color};
                selection-background-color: {accent_color};
                color: {text_primary};
            }}
        """)
        
        # Strip mode checkbox
        self.strip_mode_checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: {text_primary};
                font-size: 12px;
                spacing: 5px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 1px solid {border_color};
                background-color: {bg_primary};
            }}
            QCheckBox::indicator:checked {{
                background-color: {accent_color};
                border: 1px solid {accent_color};
            }}
            QCheckBox::indicator:hover {{
                border: 1px solid {accent_color};
            }}
        """)
        
        # Anime section header
        self.anime_header.setStyleSheet(f"background-color: {bg_header}; border-bottom: 1px solid {border_color};")
        self.anime_title.setStyleSheet(f"color: {text_primary}; font-size: 16px; font-weight: bold; background: transparent;")
        self.anime_count_label.setStyleSheet(f"color: {text_muted}; font-size: 12px; background: transparent;")
        
        # Comics section background
        self.comics_section.setStyleSheet(f"background-color: {bg_primary};")
        
        # Comic grid
        if hasattr(self.comic_grid, 'apply_theme'):
            self.comic_grid.apply_theme(theme)
        
        # Apply theme to anime grid if it exists
        if self.anime_grid and hasattr(self.anime_grid, 'apply_theme'):
            self.anime_grid.apply_theme(theme)
    
    def _create_comics_section(self) -> QWidget:
        """Create the comics section (top half)."""
        section = QWidget()
        section.setAcceptDrops(True)
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Section header
        self.comics_header = QWidget()
        self.comics_header.setFixedHeight(50)
        header_layout = QHBoxLayout(self.comics_header)
        header_layout.setContentsMargins(20, 0, 20, 0)
        header_layout.setSpacing(10)
        
        # Title
        self.comics_title = QLabel("📚 我的漫画")
        header_layout.addWidget(self.comics_title)
        
        # Search input
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("搜索本地漫画...")
        self.search_bar.setFixedHeight(30)
        self.search_bar.setFixedWidth(180)
        self.search_bar.textChanged.connect(self._on_search_changed)
        header_layout.addWidget(self.search_bar)
        
        # Sort combo
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("下载时间 (新到旧)", "date_desc")
        self.sort_combo.addItem("下载时间 (旧到新)", "date_asc")
        self.sort_combo.addItem("标题 (A-Z)", "title_asc")
        self.sort_combo.addItem("标题 (Z-A)", "title_desc")
        self.sort_combo.setFixedHeight(30)
        self.sort_combo.setFixedWidth(140)
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        header_layout.addWidget(self.sort_combo)
        
        # Refresh button
        from PySide6.QtWidgets import QPushButton
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.setFixedWidth(50)
        self.refresh_button.setFixedHeight(28)
        self.refresh_button.clicked.connect(self.scan_library)
        self.refresh_button.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                padding: 0px;
            }
            QPushButton:hover { background-color: #1084d8; }
        """)
        header_layout.addWidget(self.refresh_button)
        
        # Import button
        self.import_button = QPushButton("导入")
        self.import_button.setFixedWidth(50)
        self.import_button.setFixedHeight(28)
        self.import_button.clicked.connect(self._import_comic_folder)
        self.import_button.setStyleSheet("""
            QPushButton {
                background-color: #107c10;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                padding: 0px;
            }
            QPushButton:hover { background-color: #0e6b0e; }
        """)
        header_layout.addWidget(self.import_button)
        
        # Strip mode checkbox (条漫模式)
        from PySide6.QtWidgets import QCheckBox
        self.strip_mode_checkbox = QCheckBox("条漫模式")
        self.strip_mode_checkbox.setStyleSheet("""
            QCheckBox {
                color: #ffffff;
                font-size: 12px;
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 1px solid #5a5a5a;
                background-color: #1e1e1e;
            }
            QCheckBox::indicator:checked {
                background-color: #0078d4;
                border: 1px solid #0078d4;
            }
            QCheckBox::indicator:hover {
                border: 1px solid #0078d4;
            }
        """)
        self.strip_mode_checkbox.setToolTip("勾选后以竖向滚动方式阅读条漫")
        header_layout.addWidget(self.strip_mode_checkbox)
        
        header_layout.addStretch()
        
        # Count label
        self.count_label = QLabel("0 部漫画")
        header_layout.addWidget(self.count_label)
        
        layout.addWidget(self.comics_header)
        
        # Comic grid
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        self.comic_grid = ComicGrid(columns=6)
        self.comic_grid.comic_clicked.connect(self._on_comic_clicked)
        self.comic_grid.comic_double_clicked.connect(self._on_comic_double_clicked)
        self.comic_grid.comic_right_clicked.connect(self._on_comic_right_clicked)
        self.comic_grid.chapter_selected.connect(self._on_chapter_selected)
        content_layout.addWidget(self.comic_grid)
        
        self.loading_widget = LoadingWidget(content)
        self.loading_widget.hide()
        
        layout.addWidget(content)
        
        return section
    
    def _create_anime_section(self) -> QWidget:
        """Create the anime history section (bottom half)."""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Section header
        self.anime_header = QWidget()
        self.anime_header.setFixedHeight(50)
        header_layout = QHBoxLayout(self.anime_header)
        header_layout.setContentsMargins(20, 0, 20, 0)
        header_layout.setSpacing(10)
        
        # Title
        self.anime_title = QLabel("🎬 动漫历史")
        header_layout.addWidget(self.anime_title)
        
        # Refresh button for anime history
        from PySide6.QtWidgets import QPushButton
        self.anime_refresh_button = QPushButton("刷新")
        self.anime_refresh_button.setFixedWidth(50)
        self.anime_refresh_button.setFixedHeight(28)
        self.anime_refresh_button.clicked.connect(self.refresh_anime_history)
        self.anime_refresh_button.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                padding: 0px;
            }
            QPushButton:hover { background-color: #1084d8; }
        """)
        header_layout.addWidget(self.anime_refresh_button)
        
        header_layout.addStretch()
        
        # Count label
        self.anime_count_label = QLabel("0 部动漫")
        header_layout.addWidget(self.anime_count_label)
        
        layout.addWidget(self.anime_header)
        
        # Anime grid (scrollable)
        self.anime_grid = AnimeGrid(columns=3)
        self.anime_grid.anime_clicked.connect(self._on_anime_clicked)
        self.anime_grid.anime_double_clicked.connect(self._on_anime_double_clicked)
        self.anime_grid.anime_right_clicked.connect(self._on_anime_right_clicked)
        layout.addWidget(self.anime_grid)
        
        return section

    def _on_anime_clicked(self, anime: Anime) -> None:
        """Handle anime card click."""
        # For now, just print the anime info - in the future this could emit a signal
        print(f"Anime clicked: {anime.name}")
    
    def _on_anime_double_clicked(self, anime: Anime) -> None:
        """Open anime in browser."""
        if anime.bangumi_url:
            webbrowser.open(anime.bangumi_url)
    
    def _on_anime_right_clicked(self, anime: Anime) -> None:
        """Show context menu for anime."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2b2b2b;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 5px;
            }
            QMenu::item {
                background-color: transparent;
                color: #ffffff;
                padding: 8px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected { background-color: #0078d4; }
        """)
        
        # Delete from history
        delete_action = QAction("🗑️ 删除历史", self)
        delete_action.triggered.connect(lambda: self._delete_anime_history(anime))
        menu.addAction(delete_action)
        
        # Copy link
        copy_action = QAction("🔗 复制链接", self)
        copy_action.triggered.connect(lambda: self._copy_anime_link(anime))
        menu.addAction(copy_action)
        
        menu.exec(QCursor.pos())

    def scan_library(self) -> None:
        """
        Scan download directory for comics.
        
        Reads comic metadata from downloaded files and populates the library.
        """
        self.loading_widget.show()
        self.local_comics.clear()
        self._chapters_map = {}  # Store chapters for each comic
        
        if not self.download_path.exists():
            self.loading_widget.hide()
            self._update_display()
            return
        
        # Scan for comic directories
        # Expected structure: download_path/source/comic_id/metadata.json
        try:
            for source_dir in self.download_path.iterdir():
                if not source_dir.is_dir():
                    continue
                
                source_name = source_dir.name
                if source_name not in ['jmcomic', 'picacg', 'wnacg', 'user']:
                    continue
                
                # Scan comics in this source directory
                for comic_dir in source_dir.iterdir():
                    if not comic_dir.is_dir():
                        continue
                    
                    # Look for metadata.json
                    metadata_file = comic_dir / 'metadata.json'
                    if metadata_file.exists():
                        try:
                            with open(metadata_file, 'r', encoding='utf-8') as f:
                                metadata = json.load(f)
                            
                            # Create Comic object from metadata
                            comic = Comic.from_dict(metadata)
                            
                            # Add download date if available
                            if not comic.created_at:
                                # Use directory creation time as fallback
                                stat = comic_dir.stat()
                                comic.created_at = datetime.fromtimestamp(stat.st_ctime)
                            
                            self.local_comics.append(comic)
                            
                            # Store chapters data for this comic
                            chapters_data = metadata.get('chapters', {})
                            if chapters_data:
                                self._chapters_map[comic.id] = chapters_data
                        except (json.JSONDecodeError, ValueError, KeyError) as e:
                            # Skip invalid metadata files
                            print(f"Error loading comic metadata from {metadata_file}: {e}")
                            continue
        except Exception as e:
            print(f"Error scanning library: {e}")
        
        self.loading_widget.hide()
        
        # Apply current filter and sort
        self._update_display()
    
    def filter_comics(self, keyword: str) -> None:
        """
        Filter displayed comics by keyword.
        
        Searches in title and author fields.
        
        Args:
            keyword: Search keyword
        """
        self._current_filter = keyword.lower().strip()
        self._update_display()
    
    def sort_comics(self, sort_by: str) -> None:
        """
        Sort comics by specified criteria.
        
        Args:
            sort_by: Sort criteria (date_desc, date_asc, title_asc, title_desc, author_asc, author_desc)
        """
        self._current_sort = sort_by
        self._update_display()
    
    def _update_display(self) -> None:
        """Update the comic grid with filtered and sorted comics."""
        # Filter comics
        if self._current_filter:
            self.filtered_comics = [
                comic for comic in self.local_comics
                if self._current_filter in comic.title.lower() or
                   self._current_filter in comic.author.lower()
            ]
        else:
            self.filtered_comics = self.local_comics.copy()
        
        # Sort comics
        if self._current_sort == "date_desc":
            self.filtered_comics.sort(
                key=lambda c: c.created_at or datetime.min,
                reverse=True
            )
        elif self._current_sort == "date_asc":
            self.filtered_comics.sort(
                key=lambda c: c.created_at or datetime.min
            )
        elif self._current_sort == "title_asc":
            self.filtered_comics.sort(key=lambda c: c.title.lower())
        elif self._current_sort == "title_desc":
            self.filtered_comics.sort(key=lambda c: c.title.lower(), reverse=True)
        elif self._current_sort == "author_asc":
            self.filtered_comics.sort(key=lambda c: c.author.lower())
        elif self._current_sort == "author_desc":
            self.filtered_comics.sort(key=lambda c: c.author.lower(), reverse=True)
        
        # Build chapters map for filtered comics
        chapters_map = {}
        if hasattr(self, '_chapters_map'):
            for comic in self.filtered_comics:
                if comic.id in self._chapters_map:
                    chapters_map[comic.id] = self._chapters_map[comic.id]
        
        # Update grid
        self.comic_grid.clear()
        self.comic_grid.add_comics(self.filtered_comics, chapters_map)
        
        # Apply current theme to new cards
        if hasattr(self, '_current_theme'):
            self.comic_grid.apply_theme(self._current_theme)
        
        # Update count label
        self.count_label.setText(f"{len(self.filtered_comics)} 部漫画")
    
    def _on_search_changed(self, text: str) -> None:
        """
        Handle search text change.
        
        Args:
            text: Current search text
        """
        self.filter_comics(text)
    
    def _on_sort_changed(self, index: int) -> None:
        """
        Handle sort selection change.
        
        Args:
            index: Selected combo box index
        """
        sort_by = self.sort_combo.itemData(index)
        self.sort_comics(sort_by)
    
    def _on_comic_clicked(self, comic: Comic) -> None:
        """
        Handle comic card click.
        
        Args:
            comic: Clicked comic object
        """
        self.comic_selected.emit(comic)
    
    def _on_comic_double_clicked(self, comic: Comic) -> None:
        """
        Handle comic card double click - open reader.
        
        Args:
            comic: Double-clicked comic object
        """
        print(f"[DEBUG] Double-clicked comic: {comic.title}")
        print(f"[DEBUG] Comic ID: {comic.id}")
        print(f"[DEBUG] Comic source: {comic.source}")
        
        # Load the first available chapter for reading
        chapter = self._get_first_chapter(comic)
        print(f"[DEBUG] Got chapter: {chapter}")
        
        if chapter:
            print(f"[DEBUG] Chapter details:")
            print(f"  ID: {chapter.id}")
            print(f"  Title: {chapter.title}")
            print(f"  Download path: {chapter.download_path}")
            print(f"  Is downloaded: {chapter.is_downloaded}")
            print(f"  Page count: {chapter.page_count}")
            
            self.comic_read_requested.emit(comic, chapter)
        else:
            print("[ERROR] No chapter found")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "阅读", "未找到可阅读的章节")
    
    def _on_comic_right_clicked(self, comic: Comic) -> None:
        """
        Handle comic card right click - show context menu.
        
        Args:
            comic: Right-clicked comic object
        """
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction, QCursor
        
        # Create context menu
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2b2b2b;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 5px;
            }
            QMenu::item {
                background-color: transparent;
                color: #ffffff;
                padding: 8px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #0078d4;
            }
        """)
        
        # Add actions
        read_action = QAction("📖 阅读", self)
        read_action.triggered.connect(lambda: self._on_comic_double_clicked(comic))
        menu.addAction(read_action)
        
        delete_action = QAction("🗑️ 删除", self)
        delete_action.triggered.connect(lambda: self._confirm_delete_comic(comic))
        menu.addAction(delete_action)
        
        # Show menu at cursor position
        menu.exec(QCursor.pos())
    
    def _on_chapter_selected(self, comic: Comic, chapter_id: str) -> None:
        """
        Handle chapter button click - open specific chapter.
        
        Args:
            comic: Comic object
            chapter_id: ID of the selected chapter
        """
        chapter = self._get_chapter_by_id(comic, chapter_id)
        if chapter:
            self.comic_read_requested.emit(comic, chapter)
        else:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "阅读", "未找到该章节")
    
    def _get_chapter_by_id(self, comic: Comic, chapter_id: str) -> Optional['Chapter']:
        """
        Get a specific chapter by ID.
        
        Args:
            comic: Comic object
            chapter_id: Chapter ID to find
            
        Returns:
            Chapter object if found, None otherwise
        """
        try:
            # Load metadata to get chapter information
            comic_dir = self.download_path / comic.source / comic.id
            metadata_file = comic_dir / 'metadata.json'
            
            if not metadata_file.exists():
                return None
            
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            chapters_data = metadata.get('chapters', {})
            if chapter_id not in chapters_data:
                return None
            
            chapter_data = chapters_data[chapter_id]
            
            # Create Chapter object
            from pancomic.models.chapter import Chapter
            chapter = Chapter(
                id=chapter_data['id'],
                comic_id=comic.id,
                title=chapter_data['title'],
                chapter_number=chapter_data['chapter_number'],
                page_count=chapter_data['page_count'],
                is_downloaded=True,
                download_path=chapter_data['download_path'],
                source=comic.source
            )
            
            return chapter
            
        except Exception as e:
            print(f"Error loading chapter {chapter_id} for comic {comic.id}: {e}")
            return None
    
    def _get_first_chapter(self, comic: Comic) -> Optional['Chapter']:
        """
        Get the first available chapter for a comic.
        
        Args:
            comic: Comic object
            
        Returns:
            First chapter if available, None otherwise
        """
        try:
            print(f"[DEBUG] _get_first_chapter for comic: {comic.id}")
            
            # Load metadata to get chapter information
            comic_dir = self.download_path / comic.source / comic.id
            metadata_file = comic_dir / 'metadata.json'
            
            print(f"[DEBUG] Looking for metadata at: {metadata_file}")
            
            if not metadata_file.exists():
                print(f"[ERROR] Metadata file does not exist: {metadata_file}")
                return None
            
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            chapters_data = metadata.get('chapters', {})
            print(f"[DEBUG] Chapters data: {chapters_data}")
            
            if not chapters_data:
                print("[ERROR] No chapters data found")
                return None
            
            # Get the first chapter
            first_chapter_id = list(chapters_data.keys())[0]
            chapter_data = chapters_data[first_chapter_id]
            
            print(f"[DEBUG] First chapter ID: {first_chapter_id}")
            print(f"[DEBUG] Chapter data: {chapter_data}")
            
            # Create Chapter object
            from pancomic.models.chapter import Chapter
            chapter = Chapter(
                id=chapter_data['id'],
                comic_id=comic.id,
                title=chapter_data['title'],
                chapter_number=chapter_data['chapter_number'],
                page_count=chapter_data['page_count'],
                is_downloaded=True,
                download_path=chapter_data['download_path'],
                source=comic.source
            )
            
            print(f"[DEBUG] Created chapter successfully: {chapter}")
            return chapter
            
        except Exception as e:
            print(f"Error loading chapter for comic {comic.id}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _confirm_delete_comic(self, comic: Comic) -> None:
        """
        Show confirmation dialog for comic deletion.
        
        Args:
            comic: Comic to delete
        """
        from PySide6.QtWidgets import QMessageBox
        
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Question)
        msg.setWindowTitle("确认删除")
        msg.setText(f"确定要删除漫画《{comic.title}》吗？")
        msg.setInformativeText("此操作将删除所有下载的章节文件，无法撤销。")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        
        # Style the message box
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #2b2b2b;
            }
            QMessageBox QLabel {
                color: #ffffff;
            }
            QPushButton {
                background-color: #3a3a3a;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 6px 20px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton[text="Yes"] {
                background-color: #c42b1c;
            }
            QPushButton[text="Yes"]:hover {
                background-color: #d13438;
            }
        """)
        
        if msg.exec() == QMessageBox.Yes:
            self._delete_comic(comic)
    
    def _delete_comic(self, comic: Comic) -> None:
        """
        Delete a comic and its files.
        
        Args:
            comic: Comic to delete
        """
        try:
            import shutil
            
            # Delete comic directory
            comic_dir = self.download_path / comic.source / comic.id
            if comic_dir.exists():
                shutil.rmtree(comic_dir)
            
            # Refresh library
            self.scan_library()
            
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "删除成功", f"漫画《{comic.title}》已删除")
            
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "删除失败", f"删除漫画时出错: {str(e)}")
    
    def set_download_path(self, path: str) -> None:
        """
        Set the download path and rescan library.
        
        Args:
            path: New download path
        """
        self.download_path = Path(path)
        self.scan_library()
    
    def refresh(self) -> None:
        """Refresh the library by rescanning the download directory."""
        self.scan_library()
        self.refresh_anime_history()
    
    def refresh_anime_history(self) -> None:
        """Refresh the anime history display."""
        # Reload from file first (in case another instance modified it)
        self.anime_history_manager.reload()
        
        # Get anime history
        animes = self.anime_history_manager.get_all()
        
        # Update the anime grid
        if self.anime_grid:
            self.anime_grid.set_animes(animes)
        
        # Update count
        self.anime_count_label.setText(f"{len(animes)} 部动漫")
    
    def add_anime_to_history(self, anime: Anime) -> None:
        """
        Add anime to history (called from anime search page).
        
        Args:
            anime: Anime to add
        """
        self.anime_history_manager.add(anime)
        self.refresh_anime_history()
    
    def _delete_anime_history(self, anime: Anime) -> None:
        """Delete anime from history."""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setWindowTitle("确认删除")
        msg.setText(f"确定要从历史中删除《{anime.name}》吗？")
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        
        if msg.exec() == QMessageBox.StandardButton.Yes:
            self.anime_history_manager.remove(anime.id)
            self.refresh_anime_history()
    
    def _copy_anime_link(self, anime: Anime) -> None:
        """Copy anime link to clipboard."""
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(anime.bangumi_url)
    
    def get_comic_count(self) -> int:
        """
        Get the total number of comics in library.
        
        Returns:
            Number of comics
        """
        return len(self.local_comics)
    
    def get_filtered_count(self) -> int:
        """
        Get the number of filtered comics currently displayed.
        
        Returns:
            Number of filtered comics
        """
        return len(self.filtered_comics)
    
    def is_strip_mode(self) -> bool:
        """
        Check if strip mode (条漫模式) is enabled.
        
        Returns:
            True if strip mode is enabled
        """
        return self.strip_mode_checkbox.isChecked()
    
    def _import_comic_folder(self) -> None:
        """Open file dialog to import a comic folder."""
        from PySide6.QtWidgets import QFileDialog
        
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择漫画文件夹",
            "",
            QFileDialog.Option.ShowDirsOnly
        )
        
        if folder:
            self._do_import_folder(folder)
    
    def _do_import_folder(self, folder_path: str) -> None:
        """
        Import a folder as a comic.
        
        Args:
            folder_path: Path to the folder containing images
        """
        import shutil
        import uuid
        
        folder = Path(folder_path)
        
        # Check if folder contains images
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
        images = sorted([
            f for f in folder.iterdir() 
            if f.is_file() and f.suffix.lower() in image_extensions
        ])
        
        if not images:
            QMessageBox.warning(self, "导入失败", "所选文件夹中没有找到图片文件")
            return
        
        # Create user folder if not exists
        user_dir = self.download_path / 'user'
        user_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique ID for this comic
        comic_id = str(uuid.uuid4())[:8]
        comic_dir = user_dir / comic_id
        chapter_dir = comic_dir / 'chapter_1'
        chapter_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy images to chapter folder
        for i, img in enumerate(images):
            dest = chapter_dir / f"{i+1:03d}{img.suffix}"
            shutil.copy2(img, dest)
        
        # Get cover (first image)
        cover_path = chapter_dir / f"001{images[0].suffix}"
        
        # Create metadata
        metadata = {
            'id': comic_id,
            'title': folder.name,
            'author': '本地导入',
            'cover_url': str(cover_path),
            'description': None,
            'tags': [],
            'categories': ['本地导入'],
            'status': 'completed',
            'chapter_count': 1,
            'view_count': 0,
            'like_count': 0,
            'is_favorite': False,
            'source': 'user',
            'created_at': datetime.now().isoformat(),
            'imported_at': datetime.now().isoformat(),
            'chapters': {
                '1': {
                    'id': '1',
                    'title': '全部',
                    'chapter_number': 1,
                    'page_count': len(images),
                    'download_path': str(chapter_dir),
                    'downloaded_at': datetime.now().isoformat()
                }
            }
        }
        
        # Save metadata
        metadata_file = comic_dir / 'metadata.json'
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        # Refresh library
        self.scan_library()
        
        QMessageBox.information(self, "导入成功", f"已导入漫画《{folder.name}》\n共 {len(images)} 张图片")
    
    def dragEnterEvent(self, event) -> None:
        """Handle drag enter event for folder drop."""
        if event.mimeData().hasUrls():
            # Check if any URL is a directory
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    path = Path(url.toLocalFile())
                    if path.is_dir():
                        event.acceptProposedAction()
                        return
        event.ignore()
    
    def dragMoveEvent(self, event) -> None:
        """Handle drag move event."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event) -> None:
        """Handle drop event for folder import."""
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    path = Path(url.toLocalFile())
                    if path.is_dir():
                        self._do_import_folder(str(path))
                        event.acceptProposedAction()
                        return
        event.ignore()