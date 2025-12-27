"""Base class for comic source pages."""

from typing import List, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel
)
from PySide6.QtCore import Qt, Signal

from pancomic.adapters.base_adapter import BaseSourceAdapter
from pancomic.models.comic import Comic
from pancomic.models.chapter import Chapter
from pancomic.ui.widgets.comic_grid import ComicGrid
from pancomic.ui.widgets.loading_widget import LoadingWidget
from pancomic.ui.dialogs.comic_detail_dialog import ComicDetailDialog
from pancomic.infrastructure.download_manager import DownloadManager


class BaseSourcePage(QWidget):
    """
    Base class for comic source pages with common functionality.
    
    Provides search bar, comic grid, and loading indicator.
    Subclasses should connect to their specific adapters.
    """
    
    # Signals
    comic_selected = Signal(object)  # Comic object
    read_requested = Signal(object, object)  # Comic, Chapter
    download_requested = Signal(object, list)  # Comic, List[Chapter]
    
    def __init__(self, adapter: BaseSourceAdapter, download_manager: DownloadManager, parent=None):
        """
        Initialize BaseSourcePage.
        
        Args:
            adapter: Source adapter for this page
            download_manager: Download manager instance
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.adapter = adapter
        self.download_manager = download_manager
        self._current_keyword = ""
        self._current_page = 1
        self._is_loading = False
        self._has_more = True
        
        # Setup UI
        self._setup_ui()
        
        # Connect adapter signals
        self._connect_signals()
    
    def _setup_ui(self) -> None:
        """Initialize UI components and layout."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Search bar container
        search_container = QWidget()
        search_container.setFixedHeight(60)
        search_container.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                border-bottom: 1px solid #3a3a3a;
            }
        """)
        
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(20, 10, 20, 10)
        search_layout.setSpacing(10)
        
        # Search input
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("搜索漫画...")
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
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLineEdit:focus {
                border: 1px solid #0078d4;
            }
            QLineEdit::placeholder {
                color: #888888;
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
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QPushButton:hover {
                background-color: #1084d8;
            }
            QPushButton:pressed {
                background-color: #006cbd;
            }
            QPushButton:disabled {
                background-color: #3a3a3a;
                color: #888888;
            }
        """)
        
        # Clear button
        self.clear_button = QPushButton("清除")
        self.clear_button.setFixedSize(80, 40)
        self.clear_button.clicked.connect(self._on_clear_search)
        self.clear_button.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                border: none;
                border-radius: 8px;
                color: #ffffff;
                font-size: 14px;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
        """)
        
        search_layout.addWidget(self.search_bar)
        search_layout.addWidget(self.search_button)
        search_layout.addWidget(self.clear_button)
        
        layout.addWidget(search_container)
        
        # Content area with comic grid and loading widget
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # Comic grid
        self.comic_grid = ComicGrid(columns=6)
        self.comic_grid.comic_clicked.connect(self._on_comic_clicked)
        self.comic_grid.load_more_requested.connect(self._on_load_more)
        content_layout.addWidget(self.comic_grid)
        
        # Loading widget (overlay)
        self.loading_widget = LoadingWidget(content_widget)
        self.loading_widget.hide()
        
        layout.addWidget(content_widget)
        
        # Set page background
        self.setStyleSheet("""
            BaseSourcePage {
                background-color: #1e1e1e;
            }
        """)
    
    def _connect_signals(self) -> None:
        """Connect adapter signals to handlers."""
        # Search signals
        self.adapter.search_completed.connect(self._on_search_completed)
        self.adapter.search_failed.connect(self._on_search_failed)
        
        # Comic detail signals
        if hasattr(self.adapter, 'comic_detail_completed'):
            self.adapter.comic_detail_completed.connect(self._on_comic_detail_completed)
        if hasattr(self.adapter, 'comic_detail_failed'):
            self.adapter.comic_detail_failed.connect(self._on_comic_detail_failed)
        
        # Chapter signals
        if hasattr(self.adapter, 'chapters_completed'):
            self.adapter.chapters_completed.connect(self._on_chapters_completed)
        if hasattr(self.adapter, 'chapters_failed'):
            self.adapter.chapters_failed.connect(self._on_chapters_failed)
        
        # Image signals
        if hasattr(self.adapter, 'images_completed'):
            self.adapter.images_completed.connect(self._on_images_completed)
        if hasattr(self.adapter, 'images_failed'):
            self.adapter.images_failed.connect(self._on_images_failed)
    
    def _on_search_triggered(self) -> None:
        """Handle search button click or Enter key press."""
        keyword = self.search_bar.text().strip()
        
        if not keyword:
            return
        
        # Reset state for new search
        self._current_keyword = keyword
        self._current_page = 1
        self._has_more = True
        
        # Clear existing comics
        self.comic_grid.clear()
        
        # Perform search
        self.on_search(keyword)
    
    def _on_clear_search(self) -> None:
        """Handle clear button click."""
        self.search_bar.clear()
        self._current_keyword = ""
        self._current_page = 1
        self._has_more = True
        
        # Clear grid
        self.comic_grid.clear()
        
        # Optionally load default content
        self.on_clear()
    
    def _on_comic_clicked(self, comic: Comic) -> None:
        """
        Handle comic card click.
        
        Args:
            comic: Clicked comic object
        """
        self.on_comic_clicked(comic)
        self.comic_selected.emit(comic)
    
    def _on_load_more(self) -> None:
        """Handle lazy load request."""
        if self._is_loading or not self._has_more:
            return
        
        if self._current_keyword:
            # Load next page of search results
            self._current_page += 1
            self.on_search(self._current_keyword, self._current_page)
    
    def _on_search_completed(self, comics: List[Comic]) -> None:
        """
        Handle search completion.
        
        Args:
            comics: List of comics from search
        """
        self.hide_loading()
        
        if not comics:
            # No more results
            self._has_more = False
            
            if self.comic_grid.get_comic_count() == 0:
                # No results at all
                self._show_no_results()
        else:
            # Add comics to grid
            self.display_comics(comics)
    
    def _on_search_failed(self, error: str) -> None:
        """
        Handle search failure.
        
        Args:
            error: Error message
        """
        self.hide_loading()
        self._show_error(error)
    
    def _show_no_results(self) -> None:
        """Show no results message."""
        # This could be enhanced with a proper empty state widget
        pass
    
    def _show_error(self, error: str) -> None:
        """
        Show error message.
        
        Args:
            error: Error message to display
        """
        # This could be enhanced with a proper error dialog
        print(f"Error: {error}")
    
    # Public methods that can be overridden by subclasses
    
    def on_search(self, keyword: str, page: int = 1) -> None:
        """
        Handle search request.
        
        Subclasses can override to add custom behavior.
        
        Args:
            keyword: Search keyword
            page: Page number
        """
        self.show_loading()
        self.adapter.search(keyword, page)
    
    def on_comic_clicked(self, comic: Comic) -> None:
        """
        Handle comic click.
        
        Subclasses can override to add custom behavior.
        
        Args:
            comic: Clicked comic
        """
        # Show comic detail dialog
        self._show_comic_detail(comic)
    
    def _show_comic_detail(self, comic: Comic) -> None:
        """
        Show comic detail dialog.
        
        Args:
            comic: Comic to display
        """
        # Request chapters from adapter
        self.show_loading()
        
        # Create a callback to handle chapters loaded
        def on_chapters_loaded(chapters: List[Chapter]):
            self.hide_loading()
            
            # Create and show detail dialog
            dialog = ComicDetailDialog(comic, chapters, self)
            
            # Connect download signal
            dialog.download_clicked.connect(self._on_download_requested)
            
            # Connect chapter clicked signal to open reader
            dialog.chapter_clicked.connect(lambda chapter: self._on_chapter_clicked(comic, chapter))
            
            dialog.exec()
        
        def on_chapters_failed(error: str):
            self.hide_loading()
            self._show_error(f"Failed to load chapters: {error}")
        
        # Connect temporary signals
        self.adapter.chapters_completed.connect(on_chapters_loaded)
        self.adapter.chapters_failed.connect(on_chapters_failed)
        
        # Request chapters
        self.adapter.get_chapters(comic.id)
    
    def _on_download_requested(self, comic: Comic, chapters: List[Chapter]) -> None:
        """
        Handle download request from comic detail dialog.
        
        Args:
            comic: Comic to download
            chapters: Chapters to download
        """
        if not chapters:
            self._show_error("No chapters to download")
            return
        
        # Emit signal to let main window handle the download
        self.download_requested.emit(comic, chapters)
    
    def _on_chapter_clicked(self, comic: Comic, chapter: Chapter) -> None:
        """
        Handle chapter click to open reader.
        
        Args:
            comic: Comic being read
            chapter: Chapter to read
        """
        # Emit signal to let main window handle opening the reader
        self.read_requested.emit(comic, chapter)
    
    def on_clear(self) -> None:
        """
        Handle search clear.
        
        Subclasses can override to load default content.
        """
        pass
    
    def display_comics(self, comics: List[Comic]) -> None:
        """
        Display comics in the grid.
        
        Args:
            comics: List of comics to display
        """
        self.comic_grid.add_comics(comics)
    
    def show_loading(self) -> None:
        """Show loading indicator."""
        if not self._is_loading:
            self._is_loading = True
            self.loading_widget.show()
            self.search_button.setEnabled(False)
    
    def hide_loading(self) -> None:
        """Hide loading indicator."""
        if self._is_loading:
            self._is_loading = False
            self.loading_widget.hide()
            self.search_button.setEnabled(True)
    
    def clear_comics(self) -> None:
        """Clear all comics from the grid."""
        self.comic_grid.clear()
    
    def get_adapter(self) -> BaseSourceAdapter:
        """
        Get the adapter for this page.
        
        Returns:
            Source adapter
        """
        return self.adapter
    
    def _on_comic_detail_completed(self, comic: Comic) -> None:
        """
        Handle comic detail completion.
        
        Args:
            comic: Comic with detailed information
        """
        # This can be overridden by subclasses if needed
        pass
    
    def _on_comic_detail_failed(self, error: str) -> None:
        """
        Handle comic detail failure.
        
        Args:
            error: Error message
        """
        self._show_error(f"Failed to load comic details: {error}")
    
    def _on_chapters_completed(self, chapters: List[Chapter]) -> None:
        """
        Handle chapters completion.
        
        Args:
            chapters: List of chapters
        """
        # This can be overridden by subclasses if needed
        pass
    
    def _on_chapters_failed(self, error: str) -> None:
        """
        Handle chapters failure.
        
        Args:
            error: Error message
        """
        self._show_error(f"Failed to load chapters: {error}")
    
    def _on_images_completed(self, images: List[str]) -> None:
        """
        Handle images completion.
        
        Args:
            images: List of image URLs
        """
        # This can be overridden by subclasses if needed
        pass
    
    def _on_images_failed(self, error: str) -> None:
        """
        Handle images failure.
        
        Args:
            error: Error message
        """
        self._show_error(f"Failed to load images: {error}")
