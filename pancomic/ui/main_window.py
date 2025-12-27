"""Main application window."""

from typing import Optional
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent

from pancomic.ui.pages.jmcomic_page import JMComicPage
from pancomic.ui.pages.ehentai_page import EHentaiPage
from pancomic.ui.pages.picacg_page import PicACGPage
from pancomic.ui.pages.anime_search_page import AnimeSearchPage
from pancomic.ui.pages.library_page import LibraryPage
from pancomic.ui.pages.download_page import DownloadPage
from pancomic.ui.pages.settings_page import SettingsPage
from pancomic.adapters.jmcomic_adapter import JMComicAdapter
from pancomic.adapters.ehentai_adapter import EHentaiAdapter
from pancomic.adapters.picacg_adapter import PicACGAdapter
from pancomic.core.config_manager import ConfigManager
from pancomic.infrastructure.download_manager import DownloadManager


class MainWindow(QMainWindow):
    """
    Main application window with tabbed interface.
    
    Provides a unified interface for browsing comics from multiple sources,
    managing local library, and configuring application settings.
    """
    
    # Signal emitted when window is closing
    closing = Signal()
    
    def __init__(
        self,
        config_manager: ConfigManager,
        jmcomic_adapter: JMComicAdapter,
        ehentai_adapter: EHentaiAdapter,
        picacg_adapter: PicACGAdapter,
        download_manager: DownloadManager,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize MainWindow.
        
        Args:
            config_manager: ConfigManager instance
            jmcomic_adapter: JMComic adapter instance
            ehentai_adapter: E-Hentai adapter instance
            picacg_adapter: PicACG adapter instance
            download_manager: DownloadManager instance
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.config_manager = config_manager
        self.jmcomic_adapter = jmcomic_adapter
        self.ehentai_adapter = ehentai_adapter
        self.picacg_adapter = picacg_adapter
        self.download_manager = download_manager
        
        # UI components
        self.tab_widget: Optional[QTabWidget] = None
        self.jmcomic_page: Optional[JMComicPage] = None
        self.ehentai_page: Optional[EHentaiPage] = None
        self.picacg_page: Optional[PicACGPage] = None
        self.anime_search_page: Optional[AnimeSearchPage] = None
        self.library_page: Optional[LibraryPage] = None
        self.download_page: Optional[DownloadPage] = None
        self.settings_page: Optional[SettingsPage] = None
        
        # Tab state preservation
        self._tab_states = {}
        
        # Setup UI
        self._setup_ui()
        
        # Apply initial theme
        theme = self.config_manager.get('general.theme', 'dark')
        self.apply_theme(theme)
    
    def _setup_ui(self) -> None:
        """Initialize UI components and layout."""
        # Set window properties
        self.setWindowTitle("PanComic - 多源漫画阅读器")
        
        # Set default window size (1400x900)
        window_width = self.config_manager.get('general.window_size.width', 1400)
        window_height = self.config_manager.get('general.window_size.height', 900)
        self.resize(window_width, window_height)
        
        # Set minimum window size
        self.setMinimumSize(1024, 768)
        
        # Create menu bar
        self._create_menu_bar()
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.North)
        self.tab_widget.setMovable(False)
        self.tab_widget.setDocumentMode(True)
        
        # Get download path for library
        download_path = self.config_manager.get('download.download_path', '')
        if not download_path:
            # Use downloads folder in project root as fallback
            from pathlib import Path
            project_root = Path(__file__).parent.parent.parent  # Go up to project root
            download_path = str(project_root / "downloads")
            # Save to config for future use
            self.config_manager.set('download.download_path', download_path)
        
        # Create pages
        self.jmcomic_page = JMComicPage(self.jmcomic_adapter, self.download_manager)
        self.ehentai_page = EHentaiPage(self.ehentai_adapter, self.download_manager)
        self.picacg_page = PicACGPage(self.picacg_adapter, self.download_manager)
        self.anime_search_page = AnimeSearchPage()
        self.library_page = LibraryPage(download_path)
        self.download_page = DownloadPage(self.download_manager)
        self.download_page.start_download_requested.connect(self._on_queue_start_download)
        
        # Create integrated settings page
        self.settings_page = SettingsPage(
            config_manager=self.config_manager,
            picacg_adapter=self.picacg_adapter,
            jmcomic_adapter=self.jmcomic_adapter,
            ehentai_adapter=self.ehentai_adapter,
            parent=self
        )
        
        # Connect JMComic page signals
        self.jmcomic_page.read_requested.connect(self._on_read_requested)
        self.jmcomic_page.download_requested.connect(self._on_download_requested)
        self.jmcomic_page.queue_requested.connect(self._on_queue_requested)
        self.jmcomic_page.settings_requested.connect(self._navigate_to_jmcomic_settings)
        
        # Connect EHentai page signals (disabled but kept for compatibility)
        # self.ehentai_page.read_requested.connect(self._on_read_requested)
        # self.ehentai_page.download_requested.connect(self._on_download_requested)
        
        # Connect PicACG page signals
        self.picacg_page.read_requested.connect(self._on_read_requested)
        self.picacg_page.download_requested.connect(self._on_download_requested)
        self.picacg_page.queue_requested.connect(self._on_queue_requested)
        self.picacg_page.settings_requested.connect(self._navigate_to_picacg_settings)
        
        # Connect anime search page signals
        self.anime_search_page.anime_added_to_history.connect(self._on_anime_added_to_history)
        
        # Connect library page signals
        self.library_page.comic_read_requested.connect(self._on_read_requested)
        
        # Connect settings page signals
        self.settings_page.settings_saved.connect(self._on_settings_saved)
        
        # Connect download manager signals (use QueuedConnection for thread safety)
        from PySide6.QtCore import Qt as QtCore_Qt
        self.download_manager.download_progress.connect(
            self._on_download_progress, QtCore_Qt.ConnectionType.QueuedConnection
        )
        self.download_manager.download_completed.connect(
            self._on_download_completed, QtCore_Qt.ConnectionType.QueuedConnection
        )
        self.download_manager.download_failed.connect(
            self._on_download_failed, QtCore_Qt.ConnectionType.QueuedConnection
        )
        
        # Add tabs (EHentai tab is hidden by default)
        self.tab_widget.addTab(self.jmcomic_page, "JMComic")
        # Hide EHentai tab for now
        # self.tab_widget.addTab(self.ehentai_page, "E-Hentai")
        self.tab_widget.addTab(self.picacg_page, "PicACG")
        self.tab_widget.addTab(self.anime_search_page, "动漫搜索")
        self.tab_widget.addTab(self.library_page, "资源库")
        self.tab_widget.addTab(self.download_page, "下载管理")
        self.tab_widget.addTab(self.settings_page, "设置")
        
        # Connect tab change signal for state preservation
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        
        # Add tab widget to layout
        main_layout.addWidget(self.tab_widget)
        
        # Apply tab widget styling
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #1e1e1e;
            }
            QTabBar::tab {
                background-color: #2b2b2b;
                color: #ffffff;
                padding: 12px 24px;
                margin-right: 2px;
                border: none;
                font-size: 14px;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QTabBar::tab:selected {
                background-color: #0078d4;
            }
            QTabBar::tab:hover:!selected {
                background-color: #3a3a3a;
            }
        """)
    
    def _create_menu_bar(self) -> None:
        """Create menu bar with download manager access."""
        from PySide6.QtGui import QAction
        
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar {
                background-color: #2b2b2b;
                color: #ffffff;
                border-bottom: 1px solid #3a3a3a;
                padding: 4px;
            }
            QMenuBar::item {
                background-color: transparent;
                padding: 6px 12px;
            }
            QMenuBar::item:selected {
                background-color: #3a3a3a;
            }
            QMenu {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #3a3a3a;
            }
            QMenu::item {
                padding: 6px 24px;
            }
            QMenu::item:selected {
                background-color: #0078d4;
            }
        """)
        
        # File menu
        file_menu = menubar.addMenu("ComicGo")
        
        # Download manager action
        download_action = QAction("下载管理", self)
        download_action.setShortcut("Ctrl+D")
        download_action.triggered.connect(self.show_download_manager)
        file_menu.addAction(download_action)
        
        file_menu.addSeparator()
        
        # Settings action
        settings_action = QAction("设置", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self.show_settings)
        file_menu.addAction(settings_action)
        
        file_menu.addSeparator()
        
        # Exit action
        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
    
    def _on_tab_changed(self, index: int) -> None:
        """
        Handle tab change event.
        
        Preserves state of the previous tab and restores state of the new tab.
        Auto-refreshes library when switching to it.
        
        Args:
            index: Index of the newly selected tab
        """
        # Get the widget at the current index
        current_widget = self.tab_widget.widget(index)
        
        # Check if switched to library page
        if current_widget == self.library_page and self.library_page:
            # Auto-refresh library to show latest downloads
            print("📚 切换到漫画库，自动刷新...")
            self.library_page.refresh()
    
    def show_settings(self) -> None:
        """Display settings page by switching to settings tab."""
        self.switch_to_tab('settings')
    
    def show_download_manager(self) -> None:
        """Display download manager by switching to download tab."""
        self.switch_to_tab('download')
        # Refresh the download page
        if self.download_page:
            self.download_page.refresh()
    
    def _on_read_requested(self, comic, chapter) -> None:
        """
        Handle read request from source page.
        
        Args:
            comic: Comic to read
            chapter: Chapter to read
        """
        # Import ReaderOverlay
        from pancomic.ui.widgets.reader_overlay import ReaderOverlay
        
        # Check if strip mode is enabled (from library page)
        strip_mode = False
        if self.library_page and hasattr(self.library_page, 'is_strip_mode'):
            strip_mode = self.library_page.is_strip_mode()
        
        # For user-imported comics, use local reader mode
        if comic.source == "user":
            try:
                # Close any existing reader overlay
                if hasattr(self, '_reader_overlay') and self._reader_overlay:
                    self._reader_overlay.close_reader()
                
                # Create reader overlay in local mode (no adapter needed)
                self._reader_overlay = ReaderOverlay(
                    comic.id, chapter, None, self, 
                    local_mode=True, strip_mode=strip_mode
                )
                
                # Connect reader signals
                self._reader_overlay.reader_closed.connect(self._on_reader_closed)
                
                # Show overlay
                self._reader_overlay.show()
                self._reader_overlay.setFocus()
                
            except Exception as e:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(
                    self,
                    "阅读器错误",
                    f"无法打开阅读器: {str(e)}"
                )
            return
        
        # Determine which adapter to use based on comic source
        adapter = None
        if comic.source == "jmcomic":
            adapter = self.jmcomic_adapter
        elif comic.source == "ehentai":
            adapter = self.ehentai_adapter
        elif comic.source == "picacg":
            adapter = self.picacg_adapter
        
        if not adapter:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "阅读", f"不支持的漫画源: {comic.source}")
            return
        
        # Create and show reader overlay
        try:
            # Close any existing reader overlay
            if hasattr(self, '_reader_overlay') and self._reader_overlay:
                self._reader_overlay.close_reader()
            
            # Create new reader overlay
            self._reader_overlay = ReaderOverlay(
                comic.id, chapter, adapter, self,
                strip_mode=strip_mode
            )
            
            # Connect reader signals
            self._reader_overlay.reader_closed.connect(self._on_reader_closed)
            
            # Show overlay
            self._reader_overlay.show()
            self._reader_overlay.setFocus()
            
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "阅读器错误",
                f"无法打开阅读器: {str(e)}"
            )
    
    def _on_reader_closed(self) -> None:
        """Handle reader overlay closed."""
        if hasattr(self, '_reader_overlay'):
            self._reader_overlay = None
    
    def resizeEvent(self, event) -> None:
        """
        Handle window resize event to maintain overlay coverage.
        
        Args:
            event: Resize event
        """
        super().resizeEvent(event)
        
        # Update reader overlay if active
        if hasattr(self, '_reader_overlay') and self._reader_overlay:
            self._reader_overlay.setGeometry(self.rect())
    
    def _on_download_requested(self, comic, chapters) -> None:
        """
        Handle download request from source page.
        
        Args:
            comic: Comic to download
            chapters: List of chapters to download
        """
        if not chapters:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "下载", "没有可下载的章节")
            return
        
        # Get download path from config
        download_path = self.config_manager.get('download.download_path', '')
        if not download_path:
            from pathlib import Path
            # Use downloads folder in project root as fallback
            project_root = Path(__file__).parent.parent.parent  # Go up to project root
            download_path = str(project_root / "downloads")
            # Save to config for future use
            self.config_manager.set('download.download_path', download_path)
        
        # Add download task
        task_id = self.download_manager.add_download(comic, chapters, download_path)
        
        # Refresh download page and switch to it
        if self.download_page:
            self.download_page.refresh()
        self.switch_to_tab('download')
        
        # Show confirmation
        from PySide6.QtWidgets import QMessageBox
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("下载已添加")
        msg.setText(f"已添加下载任务: {comic.title}")
        msg.setInformativeText(f"共 {len(chapters)} 章节\n\n")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #2b2b2b;
            }
            QMessageBox QLabel {
                color: #ffffff;
            }
            QPushButton {
                background-color: #0078d4;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 6px 20px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #1084d8;
            }
        """)
        msg.exec()
    
    def _on_queue_requested(self, comic, chapters) -> None:
        """
        Handle add to queue request from source page.
        
        Args:
            comic: Comic to add to queue
            chapters: List of chapters
        """
        if not chapters:
            return
        
        # Determine source from comic
        source = comic.source if hasattr(comic, 'source') and comic.source else 'unknown'
        
        # Add to download page queue
        if self.download_page:
            self.download_page.add_to_queue(comic, chapters, source)
    
    def _on_queue_start_download(self, item_data: dict) -> None:
        """
        Handle start download request from queue.
        
        Args:
            item_data: QueueItem data as dict
        """
        from pancomic.models.comic import Comic
        from pancomic.models.chapter import Chapter
        
        # Reconstruct Comic object with all required fields (use defaults for missing fields)
        comic = Comic(
            id=str(item_data['comic_id']),
            title=item_data.get('comic_title', '未知标题'),
            author=item_data.get('comic_author', '未知作者'),
            cover_url=item_data.get('comic_cover_url', ''),
            description=item_data.get('description'),
            tags=item_data.get('tags', []),
            categories=item_data.get('categories', []),
            status=item_data.get('status', 'completed'),
            chapter_count=item_data.get('chapter_count', 0),
            view_count=item_data.get('view_count', 0),
            like_count=item_data.get('like_count', 0),
            is_favorite=item_data.get('is_favorite', False),
            source=item_data['source']
        )
        
        # Reconstruct Chapter objects
        chapters = []
        for ch_data in item_data['chapters_data']:
            chapter = Chapter(
                id=ch_data['id'],
                comic_id=item_data['comic_id'],
                title=ch_data['title'],
                chapter_number=ch_data['chapter_number'],
                page_count=ch_data.get('page_count', 0),
                is_downloaded=False,
                download_path=None,
                source=item_data['source']
            )
            chapters.append(chapter)
        
        if not chapters:
            print(f"No chapters to download for {comic.title}")
            return
        
        # Get download path from config
        download_path = self.config_manager.get('download.download_path', '')
        if not download_path:
            from pathlib import Path
            project_root = Path(__file__).parent.parent.parent
            download_path = str(project_root / "downloads")
            self.config_manager.set('download.download_path', download_path)
        
        # Add download task
        print(f"Starting download from queue: {comic.title} ({len(chapters)} chapters)")
        task_id = self.download_manager.add_download(comic, chapters, download_path)
        
        # Refresh download page
        if self.download_page:
            self.download_page.refresh()
    
    def _on_download_progress(self, task_id: str, current: int, total: int) -> None:
        """
        Handle download progress update.
        
        Args:
            task_id: Task identifier
            current: Current progress
            total: Total items
        """
        # Update download page
        if self.download_page:
            self.download_page.update_progress(task_id, current, total)
    
    def _on_download_completed(self, task_id: str) -> None:
        """
        Handle download completion.
        
        Args:
            task_id: Task identifier
        """
        # Use QTimer to ensure UI updates happen in main thread
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, lambda: self._show_download_complete_notification())
    
    def _show_download_complete_notification(self) -> None:
        """Show download complete notification (must be called from main thread)."""
        # Refresh library to show newly downloaded comics
        if self.library_page:
            self.library_page.scan_library()
        
        # Refresh download page
        if self.download_page:
            self.download_page.refresh()
    
    def _on_download_failed(self, task_id: str, error: str) -> None:
        """
        Handle download failure.
        
        Args:
            task_id: Task identifier
            error: Error message
        """
        # Use QTimer to ensure UI updates happen in main thread
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, lambda: self._show_download_failed_notification(error))
    
    def _show_download_failed_notification(self, error: str) -> None:
        """Show download failed notification (must be called from main thread)."""
        # Refresh download page
        if self.download_page:
            self.download_page.refresh()
        
        # Show error notification
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(self, "下载失败", f"下载失败: {error}")
    
    def _on_settings_saved(self) -> None:
        """Handle settings saved event."""
        # Reload theme
        theme = self.config_manager.get('general.theme', 'dark')
        self.apply_theme(theme)
        
        # Update library path if changed
        download_path = self.config_manager.get('download.download_path', '')
        if download_path and self.library_page:
            self.library_page.set_download_path(download_path)
        
        # Update PicACG page login status
        if self.picacg_page and self.picacg_adapter.is_logged_in():
            self.picacg_page._on_settings_saved()
    
    def _navigate_to_picacg_settings(self) -> None:
        """Navigate to PicACG settings page."""
        # Switch to settings tab
        settings_index = -1
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == "设置":
                settings_index = i
                break
        
        if settings_index >= 0:
            self.tab_widget.setCurrentIndex(settings_index)
            
            # Navigate to PicACG settings section
            if self.settings_page:
                self.settings_page.navigate_to_picacg()
                print("🎯 已导航到PicACG设置")
    
    def _navigate_to_jmcomic_settings(self) -> None:
        """Navigate to JMComic settings page."""
        # Switch to settings tab
        settings_index = -1
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == "设置":
                settings_index = i
                break
        
        if settings_index >= 0:
            self.tab_widget.setCurrentIndex(settings_index)
            
            # Navigate to JMComic settings section
            if self.settings_page:
                self.settings_page.navigate_to_jmcomic()
                print("🎯 已导航到JMComic设置")
    
    def _on_anime_added_to_history(self, anime) -> None:
        """
        Handle anime added to history from search page.
        
        Args:
            anime: Anime object added to history
        """
        # Refresh library page anime history
        if self.library_page:
            self.library_page.refresh_anime_history()
    
    def apply_theme(self, theme: str) -> None:
        """
        Apply Fluent Design theme.
        
        Loads and applies QSS stylesheet for the specified theme.
        Supports immediate theme switching without restart.
        
        Args:
            theme: Theme name ('dark', 'light', or 'system')
        """
        # Handle system theme
        if theme == 'system':
            # For now, default to dark theme
            # In a full implementation, this would detect system theme
            theme = 'dark'
        
        # Load stylesheet
        from pathlib import Path
        stylesheet_path = Path(__file__).parent / 'styles' / f'fluent_{theme}.qss'
        
        if stylesheet_path.exists():
            try:
                with open(stylesheet_path, 'r', encoding='utf-8') as f:
                    stylesheet = f.read()
                
                # Clear all child widget stylesheets first to allow global theme to take effect
                self._clear_child_stylesheets()
                
                # Apply stylesheet to application
                self.setStyleSheet(stylesheet)
                
                # Apply theme to pages that have custom styles
                if self.library_page and hasattr(self.library_page, 'apply_theme'):
                    self.library_page.apply_theme(theme)
                if self.settings_page and hasattr(self.settings_page, 'apply_theme'):
                    self.settings_page.apply_theme(theme)
                if self.jmcomic_page and hasattr(self.jmcomic_page, 'apply_theme'):
                    self.jmcomic_page.apply_theme(theme)
                if self.picacg_page and hasattr(self.picacg_page, 'apply_theme'):
                    self.picacg_page.apply_theme(theme)
                if self.anime_search_page and hasattr(self.anime_search_page, 'apply_theme'):
                    self.anime_search_page.apply_theme(theme)
                if self.download_page and hasattr(self.download_page, 'apply_theme'):
                    self.download_page.apply_theme(theme)
                
                # Apply theme to tab widget and menu bar
                self._apply_theme_to_main_ui(theme)
                
                # Log theme change
                from pancomic.core.logger import Logger
                Logger.info(f"Applied theme: {theme}")
            except Exception as e:
                from pancomic.core.logger import Logger
                Logger.error(f"Failed to load theme '{theme}': {e}", exc_info=True)
        else:
            # Apply basic dark theme as fallback
            self._apply_fallback_theme()
    
    def _clear_child_stylesheets(self) -> None:
        """Clear stylesheets from child widgets to allow global theme to take effect."""
        # This is a simplified approach - in a full implementation,
        # each page should have its own apply_theme method
        pass
    
    def _apply_theme_to_main_ui(self, theme: str) -> None:
        """Apply theme to main UI components (tab widget, menu bar)."""
        if theme == 'light':
            bg_primary = '#FFFFFF'
            bg_secondary = '#F3F3F3'
            bg_tab = '#E8E8E8'
            text_primary = '#000000'
            border_color = '#E0E0E0'
            accent_color = '#0078D4'
        else:
            bg_primary = '#1e1e1e'
            bg_secondary = '#2b2b2b'
            bg_tab = '#2b2b2b'
            text_primary = '#ffffff'
            border_color = '#3a3a3a'
            accent_color = '#0078d4'
        
        # Tab widget
        if self.tab_widget:
            self.tab_widget.setStyleSheet(f"""
                QTabWidget::pane {{
                    border: none;
                    background-color: {bg_primary};
                }}
                QTabBar::tab {{
                    background-color: {bg_tab};
                    color: {text_primary};
                    padding: 12px 24px;
                    margin-right: 2px;
                    border: none;
                    font-size: 14px;
                    font-family: 'Segoe UI', Arial, sans-serif;
                }}
                QTabBar::tab:selected {{
                    background-color: {accent_color};
                    color: white;
                }}
                QTabBar::tab:hover:!selected {{
                    background-color: {border_color};
                }}
            """)
        
        # Menu bar
        menubar = self.menuBar()
        if menubar:
            menubar.setStyleSheet(f"""
                QMenuBar {{
                    background-color: {bg_secondary};
                    color: {text_primary};
                    border-bottom: 1px solid {border_color};
                    padding: 4px;
                }}
                QMenuBar::item {{
                    background-color: transparent;
                    padding: 6px 12px;
                }}
                QMenuBar::item:selected {{
                    background-color: {border_color};
                }}
                QMenu {{
                    background-color: {bg_secondary};
                    color: {text_primary};
                    border: 1px solid {border_color};
                }}
                QMenu::item {{
                    padding: 6px 24px;
                }}
                QMenu::item:selected {{
                    background-color: {accent_color};
                    color: white;
                }}
            """)
    
    def _apply_fallback_theme(self) -> None:
        """Apply basic fallback theme if stylesheet file is not found."""
        fallback_stylesheet = """
            QMainWindow {
                background-color: #1e1e1e;
            }
            QWidget {
                background-color: #1e1e1e;
                color: #ffffff;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QPushButton {
                background-color: #0078d4;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1084d8;
            }
            QPushButton:pressed {
                background-color: #006cbd;
            }
            QLineEdit {
                background-color: #2b2b2b;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 8px;
                color: #ffffff;
            }
            QLineEdit:focus {
                border: 1px solid #0078d4;
            }
        """
        self.setStyleSheet(fallback_stylesheet)
    
    def closeEvent(self, event: QCloseEvent) -> None:
        """
        Handle window close event.
        
        Saves window size and emits closing signal.
        
        Args:
            event: Close event
        """
        # Save settings before closing
        if self.settings_page:
            try:
                self.settings_page.save_settings()
                print("✅ 关闭时保存设置成功")
            except Exception as e:
                print(f"⚠️ 关闭时保存设置失败: {e}")
        
        # Save window size
        self.config_manager.set('general.window_size.width', self.width())
        self.config_manager.set('general.window_size.height', self.height())
        self.config_manager.save_config()
        
        # Emit closing signal
        self.closing.emit()
        
        # Stop all adapters
        if self.jmcomic_adapter:
            self.jmcomic_adapter.stop_worker_thread()
        if self.ehentai_adapter:
            self.ehentai_adapter.stop_worker_thread()
        if self.picacg_adapter:
            self.picacg_adapter.stop_worker_thread()
            # Clean up PicACG thread pool
            if hasattr(self.picacg_adapter, 'cleanup'):
                self.picacg_adapter.cleanup()
        
        # Accept the close event
        event.accept()
    
    def get_jmcomic_page(self) -> JMComicPage:
        """
        Get JMComic page.
        
        Returns:
            JMComic page instance
        """
        return self.jmcomic_page
    
    def get_picacg_page(self) -> PicACGPage:
        """
        Get PicACG page.
        
        Returns:
            PicACG page instance
        """
        return self.picacg_page
    
    def get_library_page(self) -> LibraryPage:
        """
        Get Library page.
        
        Returns:
            Library page instance
        """
        return self.library_page
    
    def switch_to_tab(self, tab_name: str) -> None:
        """
        Switch to a specific tab by name.
        
        Args:
            tab_name: Tab name ('jmcomic', 'picacg', 'anime', 'library', 'download', 'settings')
        """
        tab_map = {
            'jmcomic': 0,
            'picacg': 1,
            'anime': 2,
            'library': 3,
            'download': 4,
            'settings': 5
        }
        
        if tab_name.lower() in tab_map:
            self.tab_widget.setCurrentIndex(tab_map[tab_name.lower()])
