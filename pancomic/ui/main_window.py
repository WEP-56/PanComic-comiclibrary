"""Main application window with dynamic tab system."""

from typing import Optional
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QStackedWidget
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent

from pancomic.ui.widgets.dynamic_tab_bar import DynamicTabBar
from pancomic.ui.widgets.source_tab_manager import SourceTabManager
from pancomic.ui.pages.jmcomic_page import JMComicPage
from pancomic.ui.pages.ehentai_page import EHentaiPage
from pancomic.ui.pages.picacg_page import PicACGPage
from pancomic.ui.pages.wnacg_page import WNACGPage
from pancomic.ui.pages.anime_search_page import AnimeSearchPage
from pancomic.ui.pages.library_page import LibraryPage
from pancomic.ui.pages.download_page import DownloadPage
from pancomic.ui.pages.settings_page import SettingsPage
from pancomic.adapters.jmcomic_adapter import JMComicAdapter
from pancomic.adapters.ehentai_adapter import EHentaiAdapter
from pancomic.adapters.picacg_adapter import PicACGAdapter
from pancomic.adapters.wnacg_adapter import WNACGAdapter
from pancomic.adapters.wnacg_adapter import WNACGAdapter
from pancomic.core.config_manager import ConfigManager
from pancomic.infrastructure.download_manager import DownloadManager


class MainWindow(QMainWindow):
    """
    Main application window with dynamic tabbed interface.
    
    Features:
    - Dynamic source tabs (add/remove/reorder)
    - Fixed tabs (Library, Downloads, Settings)
    - Lazy loading for performance
    - Tab state persistence
    """
    
    closing = Signal()
    
    def __init__(
        self,
        config_manager: ConfigManager,
        jmcomic_adapter: JMComicAdapter,
        ehentai_adapter: EHentaiAdapter,
        picacg_adapter: PicACGAdapter,
        wnacg_adapter: WNACGAdapter,
        download_manager: DownloadManager,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        
        self.config_manager = config_manager
        self.jmcomic_adapter = jmcomic_adapter
        self.ehentai_adapter = ehentai_adapter
        self.picacg_adapter = picacg_adapter
        self.wnacg_adapter = wnacg_adapter
        self.download_manager = download_manager
        
        # Tab management
        self.tab_bar: Optional[DynamicTabBar] = None
        self.tab_manager: Optional[SourceTabManager] = None
        self.stacked_widget: Optional[QStackedWidget] = None
        
        # Page references (for fixed pages)
        self.library_page: Optional[LibraryPage] = None
        self.download_page: Optional[DownloadPage] = None
        self.settings_page: Optional[SettingsPage] = None
        
        # Setup
        self._setup_ui()
        self._register_sources()
        self._setup_fixed_pages()
        self._restore_tabs()
        self._connect_download_signals()
        
        # Apply theme
        theme = self.config_manager.get('general.theme', 'dark')
        self.apply_theme(theme)
    
    def _setup_ui(self):
        """Initialize UI components."""
        self.setWindowTitle("PanComic")
        
        window_width = self.config_manager.get('general.window_size.width', 1400)
        window_height = self.config_manager.get('general.window_size.height', 900)
        self.resize(window_width, window_height)
        self.setMinimumSize(1024, 768)
        
        # Menu bar
        self._create_menu_bar()
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Dynamic tab bar
        self.tab_bar = DynamicTabBar()
        self.tab_bar.tab_selected.connect(self._on_tab_selected)
        self.tab_bar.tab_closed.connect(self._on_tab_closed)
        self.tab_bar.tab_added.connect(self._on_tab_added)
        self.tab_bar.tabs_reordered.connect(self._on_tabs_reordered)
        layout.addWidget(self.tab_bar)
        
        # Stacked widget for pages
        self.stacked_widget = QStackedWidget()
        layout.addWidget(self.stacked_widget)
        
        # Tab manager
        self.tab_manager = SourceTabManager()
        self.tab_manager.set_stacked_widget(self.stacked_widget)
        self.tab_manager.page_created.connect(self._on_page_created)
    
    def _register_sources(self):
        """Register available comic sources."""
        # JMComic
        self.tab_manager.register_source(
            "jmcomic", "JMComic",
            lambda: self._create_jmcomic_page()
        )
        
        # PicACG
        self.tab_manager.register_source(
            "picacg", "PicACG",
            lambda: self._create_picacg_page()
        )
        
        # WNACG (绅士漫画)
        self.tab_manager.register_source(
            "wnacg", "绅士漫画",
            lambda: self._create_wnacg_page()
        )
        
        # Anime Search
        self.tab_manager.register_source(
            "anime", "动漫搜索",
            lambda: self._create_anime_page()
        )
        
        # E-Hentai (hidden for now)
        # self.tab_manager.register_source(
        #     "ehentai", "E-Hentai",
        #     lambda: self._create_ehentai_page()
        # )
        
        # Set available sources for tab bar
        self.tab_bar.set_available_sources(
            self.tab_manager.get_available_sources()
        )
    
    def _setup_fixed_pages(self):
        """Setup fixed pages (Library, Downloads, Settings)."""
        download_path = self._get_download_path()
        
        # Library
        self.library_page = LibraryPage(download_path)
        self.library_page.comic_read_requested.connect(self._on_read_requested)
        self.tab_manager.register_fixed_page("library", "资源库", self.library_page)
        
        # Downloads
        self.download_page = DownloadPage(self.download_manager)
        self.download_page.start_download_requested.connect(self._on_queue_start_download)
        self.tab_manager.register_fixed_page("download", "下载管理", self.download_page)
        
        # Settings
        self.settings_page = SettingsPage(
            config_manager=self.config_manager,
            picacg_adapter=self.picacg_adapter,
            jmcomic_adapter=self.jmcomic_adapter,
            ehentai_adapter=self.ehentai_adapter,
            wnacg_adapter=self.wnacg_adapter,
            parent=self
        )
        self.settings_page.settings_saved.connect(self._on_settings_saved)
        self.tab_manager.register_fixed_page("settings", "设置", self.settings_page)
    
    def _restore_tabs(self):
        """Restore tabs from saved config."""
        saved_tabs = self.tab_manager.load_tabs_config()
        
        # Add saved dynamic tabs
        for key in saved_tabs:
            sources = self.tab_manager.get_available_sources()
            for source in sources:
                if source["key"] == key:
                    self.tab_bar.add_dynamic_tab(key, source["name"], select=False)
                    break
        
        # Select first tab or library
        if saved_tabs:
            self.tab_bar.select_tab(saved_tabs[0])
        else:
            self.tab_bar.select_tab("library")
    
    def _get_download_path(self) -> str:
        """Get download path from config."""
        download_path = self.config_manager.get('download.download_path', '')
        if not download_path:
            from pathlib import Path
            project_root = Path(__file__).parent.parent.parent
            download_path = str(project_root / "downloads")
            self.config_manager.set('download.download_path', download_path)
        return download_path
    
    # ==================== Page Factories ====================
    
    def _create_jmcomic_page(self) -> JMComicPage:
        """Create JMComic page."""
        page = JMComicPage(self.jmcomic_adapter, self.download_manager)
        page.read_requested.connect(self._on_read_requested)
        page.download_requested.connect(self._on_download_requested)
        page.queue_requested.connect(self._on_queue_requested)
        page.settings_requested.connect(self._navigate_to_jmcomic_settings)
        return page
    
    def _create_picacg_page(self) -> PicACGPage:
        """Create PicACG page."""
        page = PicACGPage(self.picacg_adapter, self.download_manager)
        page.read_requested.connect(self._on_read_requested)
        page.download_requested.connect(self._on_download_requested)
        page.queue_requested.connect(self._on_queue_requested)
        page.settings_requested.connect(self._navigate_to_picacg_settings)
        return page
    
    def _create_wnacg_page(self) -> WNACGPage:
        """Create WNACG page."""
        page = WNACGPage(self.wnacg_adapter, self.download_manager)
        page.read_requested.connect(self._on_read_requested)
        page.download_requested.connect(self._on_download_requested)
        page.queue_requested.connect(self._on_queue_requested)
        page.settings_requested.connect(self._navigate_to_wnacg_settings)
        return page
    
    def _create_anime_page(self) -> AnimeSearchPage:
        """Create Anime search page."""
        page = AnimeSearchPage()
        page.anime_added_to_history.connect(self._on_anime_added_to_history)
        return page
    
    def _create_ehentai_page(self) -> EHentaiPage:
        """Create E-Hentai page."""
        return EHentaiPage(self.ehentai_adapter, self.download_manager)
    
    # ==================== Tab Events ====================
    
    def _on_tab_selected(self, key: str):
        """Handle tab selection."""
        self.tab_manager.switch_to(key)
        
        # Auto-refresh library
        if key == "library" and self.library_page:
            print("📚 切换到资源库，自动刷新...")
            self.library_page.refresh()
    
    def _on_tab_closed(self, key: str):
        """Handle tab close."""
        self.tab_manager.remove_page(key)
        self._save_tabs_config()
    
    def _on_tab_added(self, key: str):
        """Handle tab added."""
        self._save_tabs_config()
    
    def _on_tabs_reordered(self, keys: list):
        """Handle tabs reordered."""
        self._save_tabs_config()
    
    def _on_page_created(self, key: str, page):
        """Handle page created (lazy load complete)."""
        # Apply current theme to new page
        theme = self.config_manager.get('general.theme', 'dark')
        if hasattr(page, 'apply_theme'):
            page.apply_theme(theme)
    
    def _save_tabs_config(self):
        """Save current tabs configuration."""
        keys = self.tab_bar.get_dynamic_tab_keys()
        self.tab_manager.save_tabs_config(keys)
    
    # ==================== Menu Bar ====================
    
    def _create_menu_bar(self):
        """Create menu bar."""
        from PySide6.QtGui import QAction
        
        menubar = self.menuBar()
        file_menu = menubar.addMenu("PanComic")
        
        download_action = QAction("下载管理", self)
        download_action.setShortcut("Ctrl+D")
        download_action.triggered.connect(lambda: self.tab_bar.select_tab("download"))
        file_menu.addAction(download_action)
        
        file_menu.addSeparator()
        
        settings_action = QAction("设置", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(lambda: self.tab_bar.select_tab("settings"))
        file_menu.addAction(settings_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    # ==================== Download Signals ====================
    
    def _connect_download_signals(self):
        """Connect download manager signals."""
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
    
    def _on_download_progress(self, task_id: str, current: int, total: int):
        if self.download_page:
            self.download_page.update_progress(task_id, current, total)
    
    def _on_download_completed(self, task_id: str):
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self._on_download_complete_ui)
    
    def _on_download_complete_ui(self):
        if self.library_page:
            self.library_page.scan_library()
        if self.download_page:
            self.download_page.refresh()
    
    def _on_download_failed(self, task_id: str, error: str):
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, lambda: self._on_download_failed_ui(error))
    
    def _on_download_failed_ui(self, error: str):
        if self.download_page:
            self.download_page.refresh()
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(self, "下载失败", f"下载失败: {error}")
    
    # ==================== Page Actions ====================
    
    def _on_read_requested(self, comic, chapter):
        """Handle read request."""
        from pancomic.ui.widgets.reader_overlay import ReaderOverlay
        
        strip_mode = False
        if self.library_page and hasattr(self.library_page, 'is_strip_mode'):
            strip_mode = self.library_page.is_strip_mode()
        
        # User imported comics
        if comic.source == "user":
            try:
                if hasattr(self, '_reader_overlay') and self._reader_overlay:
                    self._reader_overlay.close_reader()
                
                self._reader_overlay = ReaderOverlay(
                    comic.id, chapter, None, self,
                    local_mode=True, strip_mode=strip_mode
                )
                self._reader_overlay.reader_closed.connect(self._on_reader_closed)
                self._reader_overlay.show()
                self._reader_overlay.setFocus()
            except Exception as e:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "阅读器错误", f"无法打开阅读器: {str(e)}")
            return
        
        # Determine adapter
        adapter = None
        if comic.source == "jmcomic":
            adapter = self.jmcomic_adapter
        elif comic.source == "ehentai":
            adapter = self.ehentai_adapter
        elif comic.source == "picacg":
            adapter = self.picacg_adapter
        elif comic.source == "wnacg":
            adapter = self.wnacg_adapter
        
        if not adapter:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "阅读", f"不支持的漫画源: {comic.source}")
            return
        
        try:
            if hasattr(self, '_reader_overlay') and self._reader_overlay:
                self._reader_overlay.close_reader()
            
            self._reader_overlay = ReaderOverlay(
                comic.id, chapter, adapter, self,
                strip_mode=strip_mode
            )
            self._reader_overlay.reader_closed.connect(self._on_reader_closed)
            self._reader_overlay.show()
            self._reader_overlay.setFocus()
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "阅读器错误", f"无法打开阅读器: {str(e)}")
    
    def _on_reader_closed(self):
        if hasattr(self, '_reader_overlay'):
            self._reader_overlay = None
    
    def _on_download_requested(self, comic, chapters):
        """Handle download request."""
        if not chapters:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "下载", "没有可下载的章节")
            return
        
        download_path = self._get_download_path()
        task_id = self.download_manager.add_download(comic, chapters, download_path)
        
        if self.download_page:
            self.download_page.refresh()
        self.tab_bar.select_tab("download")
        
        from PySide6.QtWidgets import QMessageBox
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("下载已添加")
        msg.setText(f"已添加下载任务: {comic.title}")
        msg.setInformativeText(f"共 {len(chapters)} 章节")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec()
    
    def _on_queue_requested(self, comic, chapters):
        """Handle add to queue request."""
        if not chapters:
            return
        source = comic.source if hasattr(comic, 'source') and comic.source else 'unknown'
        if self.download_page:
            self.download_page.add_to_queue(comic, chapters, source)
    
    def _on_queue_start_download(self, item_data: dict):
        """Handle start download from queue."""
        from pancomic.models.comic import Comic
        from pancomic.models.chapter import Chapter
        
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
            return
        
        download_path = self._get_download_path()
        self.download_manager.add_download(comic, chapters, download_path)
        
        if self.download_page:
            self.download_page.refresh()
    
    def _on_settings_saved(self):
        """Handle settings saved."""
        theme = self.config_manager.get('general.theme', 'dark')
        self.apply_theme(theme)
        
        download_path = self.config_manager.get('download.download_path', '')
        if download_path and self.library_page:
            self.library_page.set_download_path(download_path)
        
        # Update PicACG page if exists
        picacg_page = self.tab_manager.get_page("picacg") if self.tab_manager.is_page_created("picacg") else None
        if picacg_page and self.picacg_adapter.is_logged_in():
            if hasattr(picacg_page, '_on_settings_saved'):
                picacg_page._on_settings_saved()
    
    def _navigate_to_picacg_settings(self):
        """Navigate to PicACG settings."""
        self.tab_bar.select_tab("settings")
        if self.settings_page:
            self.settings_page.navigate_to_picacg()
    
    def _navigate_to_jmcomic_settings(self):
        """Navigate to JMComic settings."""
        self.tab_bar.select_tab("settings")
        if self.settings_page:
            self.settings_page.navigate_to_jmcomic()
    
    def _navigate_to_wnacg_settings(self):
        """Navigate to WNACG settings."""
        self.tab_bar.select_tab("settings")
        if self.settings_page:
            self.settings_page.navigate_to_wnacg()
    
    def _on_anime_added_to_history(self, anime):
        """Handle anime added to history."""
        if self.library_page:
            self.library_page.refresh_anime_history()
    
    # ==================== Theme ====================
    
    def apply_theme(self, theme: str):
        """Apply theme to application."""
        if theme == 'system':
            theme = 'dark'
        
        from pathlib import Path
        stylesheet_path = Path(__file__).parent / 'styles' / f'fluent_{theme}.qss'
        
        if stylesheet_path.exists():
            try:
                with open(stylesheet_path, 'r', encoding='utf-8') as f:
                    stylesheet = f.read()
                self.setStyleSheet(stylesheet)
                
                # Apply to pages
                for page in [self.library_page, self.settings_page, self.download_page]:
                    if page and hasattr(page, 'apply_theme'):
                        page.apply_theme(theme)
                
                # Apply to dynamic pages
                if self.tab_manager:
                    for key in self.tab_bar.get_dynamic_tab_keys():
                        if self.tab_manager.is_page_created(key):
                            page = self.tab_manager.get_page(key)
                            if page and hasattr(page, 'apply_theme'):
                                page.apply_theme(theme)
                
                self._apply_theme_to_main_ui(theme)
            except Exception as e:
                print(f"Failed to load theme: {e}")
        else:
            self._apply_fallback_theme()
    
    def _apply_theme_to_main_ui(self, theme: str):
        """Apply theme to tab bar and menu."""
        if theme == 'light':
            bg = '#F3F3F3'
            text = '#000000'
            border = '#E0E0E0'
        else:
            bg = '#2b2b2b'
            text = '#ffffff'
            border = '#3a3a3a'
        
        self.menuBar().setStyleSheet(f"""
            QMenuBar {{
                background-color: {bg};
                color: {text};
                border-bottom: 1px solid {border};
                padding: 4px;
            }}
            QMenuBar::item {{
                background-color: transparent;
                padding: 6px 12px;
            }}
            QMenuBar::item:selected {{
                background-color: {border};
            }}
            QMenu {{
                background-color: {bg};
                color: {text};
                border: 1px solid {border};
            }}
            QMenu::item {{
                padding: 6px 24px;
            }}
            QMenu::item:selected {{
                background-color: #0078d4;
                color: white;
            }}
        """)
    
    def _apply_fallback_theme(self):
        """Apply fallback theme."""
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e1e; }
            QWidget { background-color: #1e1e1e; color: #ffffff; }
        """)
    
    # ==================== Window Events ====================
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_reader_overlay') and self._reader_overlay:
            self._reader_overlay.setGeometry(self.rect())
    
    def closeEvent(self, event: QCloseEvent):
        """Handle window close."""
        # Save settings
        if self.settings_page:
            try:
                self.settings_page.save_settings()
            except Exception as e:
                print(f"保存设置失败: {e}")
        
        # Save tabs config
        self._save_tabs_config()
        
        # Save window size
        self.config_manager.set('general.window_size.width', self.width())
        self.config_manager.set('general.window_size.height', self.height())
        self.config_manager.save_config()
        
        self.closing.emit()
        
        # Stop adapters
        if self.jmcomic_adapter:
            self.jmcomic_adapter.stop_worker_thread()
        if self.ehentai_adapter:
            self.ehentai_adapter.stop_worker_thread()
        if self.picacg_adapter:
            self.picacg_adapter.stop_worker_thread()
            if hasattr(self.picacg_adapter, 'cleanup'):
                self.picacg_adapter.cleanup()
        if self.wnacg_adapter:
            self.wnacg_adapter.stop_worker_thread()
        
        # Cleanup tab manager
        if self.tab_manager:
            self.tab_manager.cleanup()
        
        event.accept()
    
    # ==================== Public API ====================
    
    def get_jmcomic_page(self) -> Optional[JMComicPage]:
        """Get JMComic page (may trigger lazy load)."""
        return self.tab_manager.get_page("jmcomic") if self.tab_manager else None
    
    def get_picacg_page(self) -> Optional[PicACGPage]:
        """Get PicACG page (may trigger lazy load)."""
        return self.tab_manager.get_page("picacg") if self.tab_manager else None
    
    def get_library_page(self) -> Optional[LibraryPage]:
        """Get Library page."""
        return self.library_page
    
    def switch_to_tab(self, tab_name: str):
        """Switch to a specific tab."""
        self.tab_bar.select_tab(tab_name)
    
    def show_settings(self):
        """Show settings page."""
        self.tab_bar.select_tab("settings")
    
    def show_download_manager(self):
        """Show download manager."""
        self.tab_bar.select_tab("download")
        if self.download_page:
            self.download_page.refresh()
