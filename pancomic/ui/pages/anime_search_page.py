"""Anime search page using Bangumi API with detail panel."""

import webbrowser
from typing import List, Optional, Set
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox, 
    QLabel, QPushButton, QFrame, QMenu, QMessageBox, QSplitter,
    QScrollArea, QTextEdit
)
from PySide6.QtCore import Qt, Signal, QThread, QObject
from PySide6.QtGui import QAction, QCursor, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from pancomic.models.anime import Anime
from pancomic.adapters.bangumi_adapter import BangumiAdapter
from pancomic.infrastructure.anime_history_manager import AnimeHistoryManager
from pancomic.ui.widgets.anime_grid import AnimeGrid
from pancomic.ui.widgets.loading_widget import LoadingWidget


class SearchWorker(QObject):
    """Worker for async search."""
    
    finished = Signal(list, int)  # results, total
    error = Signal(str)
    
    def __init__(self, adapter: BangumiAdapter):
        super().__init__()
        self.adapter = adapter
        self.keyword = ""
        self.page = 1
        self.type_filter = "动画"
        self.sort = "rank"
        self.year = None
        self.include_tags: List[str] = []
        self.exclude_tags: List[str] = []
    
    def search(self):
        try:
            results, total = self.adapter.search(
                keyword=self.keyword,
                page=self.page,
                per_page=6,
                type_filter=self.type_filter,
                sort=self.sort,
                year=self.year,
                tags=self.include_tags if self.include_tags else None,
                exclude_tags=self.exclude_tags if self.exclude_tags else None,
            )
            self.finished.emit(results, total)
        except Exception as e:
            self.error.emit(str(e))


class AnimeDetailPanel(QWidget):
    """Detail panel showing selected anime information."""
    
    open_link_requested = Signal(str)
    add_to_history_requested = Signal(object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_anime: Optional[Anime] = None
        self._network_manager = QNetworkAccessManager(self)
        self._network_manager.finished.connect(self._on_cover_loaded)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Placeholder when no anime selected
        self.placeholder = QLabel("双击左侧卡片查看详情")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setStyleSheet("color: #666666; font-size: 16px;")
        layout.addWidget(self.placeholder)
        
        # Detail content (hidden initially)
        self.detail_content = QWidget()
        detail_layout = QVBoxLayout(self.detail_content)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(15)
        
        # Cover image
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(200, 280)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setStyleSheet("""
            QLabel {
                background-color: #2b2b2b;
                border-radius: 8px;
                border: 1px solid #3a3a3a;
            }
        """)
        detail_layout.addWidget(self.cover_label, alignment=Qt.AlignmentFlag.AlignHCenter)
        
        # Title
        self.title_label = QLabel()
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("color: #ffffff; font-size: 18px; font-weight: bold;")
        detail_layout.addWidget(self.title_label)
        
        # Original name
        self.original_label = QLabel()
        self.original_label.setWordWrap(True)
        self.original_label.setStyleSheet("color: #888888; font-size: 14px;")
        detail_layout.addWidget(self.original_label)
        
        # Info row
        self.info_label = QLabel()
        self.info_label.setStyleSheet("color: #aaaaaa; font-size: 13px;")
        detail_layout.addWidget(self.info_label)
        
        # Rating
        self.rating_label = QLabel()
        self.rating_label.setStyleSheet("color: #ffd700; font-size: 16px; font-weight: bold;")
        detail_layout.addWidget(self.rating_label)
        
        # Tags
        self.tags_label = QLabel()
        self.tags_label.setWordWrap(True)
        self.tags_label.setStyleSheet("color: #cccccc; font-size: 12px;")
        detail_layout.addWidget(self.tags_label)
        
        # Summary (scrollable)
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setStyleSheet("""
            QTextEdit {
                background-color: #252525;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                color: #cccccc;
                font-size: 13px;
                padding: 10px;
            }
        """)
        detail_layout.addWidget(self.summary_text)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self.link_btn = QPushButton("🔗 跳转链接")
        self.link_btn.setFixedHeight(40)
        self.link_btn.clicked.connect(self._on_open_link)
        self.link_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1084d8; }
        """)
        btn_layout.addWidget(self.link_btn)
        
        self.history_btn = QPushButton("📚 加入历史")
        self.history_btn.setFixedHeight(40)
        self.history_btn.clicked.connect(self._on_add_to_history)
        self.history_btn.setStyleSheet("""
            QPushButton {
                background-color: #107c10;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #0e6b0e; }
        """)
        btn_layout.addWidget(self.history_btn)
        
        detail_layout.addLayout(btn_layout)
        
        self.detail_content.hide()
        layout.addWidget(self.detail_content)
        
        layout.addStretch()
        
        self.setStyleSheet("background-color: #1e1e1e;")
    
    def show_anime(self, anime: Anime):
        """Display anime details."""
        self._current_anime = anime
        self.placeholder.hide()
        self.detail_content.show()
        
        # Update labels
        self.title_label.setText(anime.name or "无标题")
        self.original_label.setText(anime.name_cn if anime.name_cn != anime.name else "")
        
        info_parts = []
        if anime.air_date:
            info_parts.append(f"📅 {anime.air_date}")
        if anime.eps_count > 0:
            info_parts.append(f"🎬 {anime.eps_count}集")
        if anime.rank > 0:
            info_parts.append(f"🏆 #{anime.rank}")
        self.info_label.setText("  |  ".join(info_parts))
        
        if anime.rating > 0:
            self.rating_label.setText(f"★ {anime.rating:.1f}")
        else:
            self.rating_label.setText("")
        
        if anime.tags:
            self.tags_label.setText("标签: " + ", ".join(anime.tags[:10]))
        else:
            self.tags_label.setText("")
        
        self.summary_text.setText(anime.summary or "暂无简介")
        
        # Load cover
        self.cover_label.setText("加载中...")
        if anime.cover_url:
            request = QNetworkRequest(anime.cover_url)
            self._network_manager.get(request)
    
    def _on_cover_loaded(self, reply: QNetworkReply):
        if reply.error() == QNetworkReply.NetworkError.NoError:
            data = reply.readAll()
            pixmap = QPixmap()
            if pixmap.loadFromData(data):
                scaled = pixmap.scaled(200, 280, Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation)
                self.cover_label.setPixmap(scaled)
        reply.deleteLater()
    
    def _on_open_link(self):
        if self._current_anime and self._current_anime.bangumi_url:
            self.open_link_requested.emit(self._current_anime.bangumi_url)
    
    def _on_add_to_history(self):
        if self._current_anime:
            self.add_to_history_requested.emit(self._current_anime)

    def apply_theme(self, theme: str) -> None:
        """Apply theme to detail panel components."""
        if theme == 'light':
            bg_primary = '#FFFFFF'
            bg_secondary = '#F3F3F3'
            bg_card = '#FAFAFA'
            text_primary = '#000000'
            text_secondary = '#333333'
            text_muted = '#666666'
            border_color = '#E0E0E0'
        else:
            bg_primary = '#1e1e1e'
            bg_secondary = '#2b2b2b'
            bg_card = '#252525'
            text_primary = '#ffffff'
            text_secondary = '#cccccc'
            text_muted = '#888888'
            border_color = '#3a3a3a'
        
        # Panel background
        self.setStyleSheet(f"background-color: {bg_primary};")
        
        # Placeholder
        if hasattr(self, 'placeholder'):
            self.placeholder.setStyleSheet(f"color: {text_muted}; font-size: 16px;")
        
        # Cover label
        if hasattr(self, 'cover_label'):
            self.cover_label.setStyleSheet(f"""
                QLabel {{
                    background-color: {bg_secondary};
                    border-radius: 8px;
                    border: 1px solid {border_color};
                }}
            """)
        
        # Title label
        if hasattr(self, 'title_label'):
            self.title_label.setStyleSheet(f"color: {text_primary}; font-size: 18px; font-weight: bold;")
        
        # Original label
        if hasattr(self, 'original_label'):
            self.original_label.setStyleSheet(f"color: {text_muted}; font-size: 14px;")
        
        # Info label
        if hasattr(self, 'info_label'):
            self.info_label.setStyleSheet(f"color: {text_secondary}; font-size: 13px;")
        
        # Tags label
        if hasattr(self, 'tags_label'):
            self.tags_label.setStyleSheet(f"color: {text_secondary}; font-size: 12px;")
        
        # Summary text
        if hasattr(self, 'summary_text'):
            self.summary_text.setStyleSheet(f"""
                QTextEdit {{
                    background-color: {bg_card};
                    border: 1px solid {border_color};
                    border-radius: 8px;
                    color: {text_secondary};
                    font-size: 13px;
                    padding: 10px;
                }}
            """)


class AnimeSearchPage(QWidget):
    """
    Anime search page with left-right layout.
    
    Left: Search results grid
    Right: Detail panel
    """
    
    anime_added_to_history = Signal(object)
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self.adapter = BangumiAdapter()
        self.history_manager = AnimeHistoryManager()
        
        self._current_page = 1
        self._total_results = 0
        self._include_tags: Set[str] = set()
        self._exclude_tags: Set[str] = set()
        
        self._search_thread: Optional[QThread] = None
        self._search_worker: Optional[SearchWorker] = None
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Toolbar
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)
        
        # Tag filter bar
        self.tag_filter_bar = self._create_tag_filter_bar()
        self.tag_filter_bar.hide()
        layout.addWidget(self.tag_filter_bar)
        
        # Main content with splitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(4)
        self.splitter.setStyleSheet("""
            QSplitter::handle { background-color: #3a3a3a; }
            QSplitter::handle:hover { background-color: #0078d4; }
        """)
        
        # Left: Search results
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        
        # Anime grid
        self.anime_grid = AnimeGrid(columns=3)
        self.anime_grid.anime_clicked.connect(self._on_anime_clicked)
        self.anime_grid.anime_double_clicked.connect(self._on_anime_double_clicked)
        self.anime_grid.anime_right_clicked.connect(self._on_anime_right_clicked)
        self.anime_grid.tag_include_requested.connect(self._on_tag_include)
        self.anime_grid.tag_exclude_requested.connect(self._on_tag_exclude)
        left_layout.addWidget(self.anime_grid)
        
        # Loading widget
        self.loading_widget = LoadingWidget(left_panel)
        self.loading_widget.hide()
        
        self.splitter.addWidget(left_panel)
        
        # Right: Detail panel (scrollable)
        self.right_scroll = QScrollArea()
        self.right_scroll.setWidgetResizable(True)
        self.right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.right_scroll.setStyleSheet("""
            QScrollArea { background-color: #1e1e1e; border: none; }
            QScrollBar:vertical {
                background-color: #2b2b2b; width: 10px; border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background-color: #3a3a3a; border-radius: 5px; min-height: 20px;
            }
        """)
        
        self.detail_panel = AnimeDetailPanel()
        self.detail_panel.open_link_requested.connect(self._open_link)
        self.detail_panel.add_to_history_requested.connect(self._add_to_history)
        self.right_scroll.setWidget(self.detail_panel)
        
        self.splitter.addWidget(self.right_scroll)
        
        # Set initial sizes (60:40)
        self.splitter.setSizes([600, 400])
        
        layout.addWidget(self.splitter)
        
        # Pagination bar
        self.pagination_bar = self._create_pagination_bar()
        layout.addWidget(self.pagination_bar)
        
        self.setStyleSheet("AnimeSearchPage { background-color: #1e1e1e; }")
    
    def _create_toolbar(self) -> QWidget:
        self.toolbar = QWidget()
        self.toolbar.setFixedHeight(60)
        self.toolbar.setStyleSheet("background-color: #2b2b2b; border-bottom: 1px solid #3a3a3a;")
        
        layout = QHBoxLayout(self.toolbar)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(10)
        
        # Search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索动漫...")
        self.search_input.setFixedHeight(40)
        self.search_input.returnPressed.connect(self._on_search)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #1e1e1e; border: 1px solid #3a3a3a;
                border-radius: 8px; padding: 0 15px; color: #ffffff; font-size: 14px;
            }
            QLineEdit:focus { border: 1px solid #0078d4; }
            QLineEdit::placeholder { color: #888888; }
        """)
        layout.addWidget(self.search_input)
        
        # Search button
        self.search_btn = QPushButton("🔍 搜索")
        self.search_btn.setFixedSize(80, 40)
        self.search_btn.clicked.connect(self._on_search)
        self.search_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4; color: #ffffff; border: none;
                border-radius: 8px; font-size: 14px; font-weight: bold;
            }
            QPushButton:hover { background-color: #1084d8; }
        """)
        layout.addWidget(self.search_btn)
        
        layout.addWidget(self._create_vseparator())
        
        # Type filter
        self.type_label = QLabel("类型:")
        self.type_label.setStyleSheet("color: #ffffff; font-size: 14px; background: transparent;")
        layout.addWidget(self.type_label)
        
        self.type_combo = QComboBox()
        self.type_combo.addItems(["动画", "书籍", "游戏", "音乐", "真实"])
        self.type_combo.setFixedSize(100, 40)
        self.type_combo.currentIndexChanged.connect(self._on_filter_changed)
        self._style_combo(self.type_combo)
        layout.addWidget(self.type_combo)
        
        # Sort filter
        self.sort_label = QLabel("排序:")
        self.sort_label.setStyleSheet("color: #ffffff; font-size: 14px; background: transparent;")
        layout.addWidget(self.sort_label)
        
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("评分 (高到低)", "rank")
        self.sort_combo.addItem("评分 (低到高)", "rank_asc")
        self.sort_combo.setFixedSize(130, 40)
        self.sort_combo.currentIndexChanged.connect(self._on_filter_changed)
        self._style_combo(self.sort_combo)
        layout.addWidget(self.sort_combo)
        
        # Year filter
        self.year_label = QLabel("年份:")
        self.year_label.setStyleSheet("color: #ffffff; font-size: 14px; background: transparent;")
        layout.addWidget(self.year_label)
        
        self.year_combo = QComboBox()
        self.year_combo.addItem("全部", None)
        for year in self.adapter.get_available_years():
            self.year_combo.addItem(str(year), year)
        self.year_combo.setFixedSize(100, 40)
        self.year_combo.currentIndexChanged.connect(self._on_filter_changed)
        self._style_combo(self.year_combo)
        layout.addWidget(self.year_combo)
        
        return self.toolbar

    def _create_tag_filter_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(40)
        bar.setStyleSheet("background-color: #252525; border-bottom: 1px solid #3a3a3a;")
        
        self.tag_layout = QHBoxLayout(bar)
        self.tag_layout.setContentsMargins(20, 5, 20, 5)
        self.tag_layout.setSpacing(8)
        
        self.tag_filter_label = QLabel("标签过滤:")
        self.tag_filter_label.setStyleSheet("color: #888888; font-size: 12px; background: transparent;")
        self.tag_layout.addWidget(self.tag_filter_label)
        
        self.tag_layout.addStretch()
        
        self.clear_tags_btn = QPushButton("清除")
        self.clear_tags_btn.setFixedSize(60, 28)
        self.clear_tags_btn.clicked.connect(self._clear_tags)
        self.clear_tags_btn.setStyleSheet("""
            QPushButton { background-color: #3a3a3a; color: #ffffff; border: none; border-radius: 4px; font-size: 12px; }
            QPushButton:hover { background-color: #4a4a4a; }
        """)
        self.tag_layout.addWidget(self.clear_tags_btn)
        
        return bar
    
    def _create_pagination_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(50)
        bar.setStyleSheet("background-color: #2b2b2b; border-top: 1px solid #3a3a3a;")
        
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(10)
        
        layout.addStretch()
        
        self.prev_btn = QPushButton("◀ 上一页")
        self.prev_btn.setFixedSize(100, 30)
        self.prev_btn.clicked.connect(self._on_prev_page)
        self.prev_btn.setEnabled(False)
        self._style_page_btn(self.prev_btn)
        layout.addWidget(self.prev_btn)
        
        self.page_label = QLabel("第 1 页")
        self.page_label.setStyleSheet("color: #ffffff; font-size: 14px; background: transparent;")
        layout.addWidget(self.page_label)
        
        self.next_btn = QPushButton("下一页 ▶")
        self.next_btn.setFixedSize(100, 30)
        self.next_btn.clicked.connect(self._on_next_page)
        self.next_btn.setEnabled(False)
        self._style_page_btn(self.next_btn)
        layout.addWidget(self.next_btn)
        
        layout.addStretch()
        
        self.results_label = QLabel("")
        self.results_label.setStyleSheet("color: #888888; font-size: 12px; background: transparent;")
        layout.addWidget(self.results_label)
        
        return bar
    
    def _create_vseparator(self) -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet("background-color: #3a3a3a;")
        return sep
    
    def _style_combo(self, combo: QComboBox) -> None:
        combo.setStyleSheet("""
            QComboBox {
                background-color: #1e1e1e; border: 1px solid #3a3a3a;
                border-radius: 8px; padding: 0 15px; color: #ffffff; font-size: 14px;
            }
            QComboBox:hover { border: 1px solid #4a4a4a; }
            QComboBox::drop-down { border: none; width: 30px; }
            QComboBox::down-arrow {
                image: none; border-left: 5px solid transparent;
                border-right: 5px solid transparent; border-top: 5px solid #ffffff; margin-right: 10px;
            }
            QComboBox QAbstractItemView {
                background-color: #2b2b2b; border: 1px solid #3a3a3a;
                selection-background-color: #0078d4; color: #ffffff;
            }
        """)
    
    def _style_page_btn(self, btn: QPushButton) -> None:
        btn.setStyleSheet("""
            QPushButton { background-color: #3a3a3a; color: #ffffff; border: none; border-radius: 4px; font-size: 12px; }
            QPushButton:hover { background-color: #4a4a4a; }
            QPushButton:disabled { background-color: #2a2a2a; color: #666666; }
        """)
    
    def _on_search(self) -> None:
        keyword = self.search_input.text().strip()
        if not keyword:
            return
        self._current_page = 1
        self._do_search()
    
    def _on_filter_changed(self) -> None:
        if self.search_input.text().strip():
            self._current_page = 1
            self._do_search()
    
    def _on_prev_page(self) -> None:
        if self._current_page > 1:
            self._current_page -= 1
            self._do_search()
    
    def _on_next_page(self) -> None:
        total_pages = (self._total_results + 5) // 6
        if self._current_page < total_pages:
            self._current_page += 1
            self._do_search()
    
    def _do_search(self) -> None:
        keyword = self.search_input.text().strip()
        if not keyword:
            return
        
        self.loading_widget.show()
        self.anime_grid.clear()
        
        if self._search_thread and self._search_thread.isRunning():
            self._search_thread.quit()
            self._search_thread.wait()
        
        self._search_thread = QThread()
        self._search_worker = SearchWorker(self.adapter)
        self._search_worker.keyword = keyword
        self._search_worker.page = self._current_page
        self._search_worker.type_filter = self.type_combo.currentText()
        self._search_worker.sort = self.sort_combo.currentData()
        self._search_worker.year = self.year_combo.currentData()
        self._search_worker.include_tags = list(self._include_tags)
        self._search_worker.exclude_tags = list(self._exclude_tags)
        
        self._search_worker.moveToThread(self._search_thread)
        self._search_thread.started.connect(self._search_worker.search)
        self._search_worker.finished.connect(self._on_search_finished)
        self._search_worker.error.connect(self._on_search_error)
        
        self._search_thread.start()

    def _on_search_finished(self, results: List[Anime], total: int) -> None:
        self.loading_widget.hide()
        self._total_results = total
        
        self.anime_grid.set_animes(results)
        self._update_pagination()
        
        if self._search_thread:
            self._search_thread.quit()
            self._search_thread.wait()
            self._search_thread = None
        self._search_worker = None
    
    def _on_search_error(self, error: str) -> None:
        self.loading_widget.hide()
        QMessageBox.warning(self, "搜索失败", f"搜索出错: {error}")
        
        if self._search_thread:
            self._search_thread.quit()
            self._search_thread.wait()
            self._search_thread = None
        self._search_worker = None
    
    def _update_pagination(self) -> None:
        total_pages = max(1, (self._total_results + 5) // 6)
        self.page_label.setText(f"第 {self._current_page} / {total_pages} 页")
        self.results_label.setText(f"共 {self._total_results} 个结果")
        self.prev_btn.setEnabled(self._current_page > 1)
        self.next_btn.setEnabled(self._current_page < total_pages)
    
    def _on_tag_include(self, tag: str) -> None:
        self._exclude_tags.discard(tag)
        self._include_tags.add(tag)
        self._update_tag_bar()
        self._on_filter_changed()
    
    def _on_tag_exclude(self, tag: str) -> None:
        self._include_tags.discard(tag)
        self._exclude_tags.add(tag)
        self._update_tag_bar()
        self._on_filter_changed()
    
    def _update_tag_bar(self) -> None:
        while self.tag_layout.count() > 2:
            item = self.tag_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
        
        self.tag_layout.insertStretch(1)
        
        for tag in self._include_tags:
            label = QPushButton(f"+ {tag}")
            label.setFixedHeight(24)
            label.clicked.connect(lambda checked, t=tag: self._remove_include_tag(t))
            label.setStyleSheet("""
                QPushButton { background-color: #0078d4; color: #ffffff; border: none; border-radius: 4px; padding: 2px 8px; font-size: 11px; }
                QPushButton:hover { background-color: #1084d8; }
            """)
            self.tag_layout.insertWidget(1, label)
        
        for tag in self._exclude_tags:
            label = QPushButton(f"× {tag}")
            label.setFixedHeight(24)
            label.clicked.connect(lambda checked, t=tag: self._remove_exclude_tag(t))
            label.setStyleSheet("""
                QPushButton { background-color: #c42b1c; color: #ffffff; border: none; border-radius: 4px; padding: 2px 8px; font-size: 11px; }
                QPushButton:hover { background-color: #d13438; }
            """)
            self.tag_layout.insertWidget(1, label)
        
        if self._include_tags or self._exclude_tags:
            self.tag_filter_bar.show()
        else:
            self.tag_filter_bar.hide()
    
    def _remove_include_tag(self, tag: str) -> None:
        self._include_tags.discard(tag)
        self._update_tag_bar()
        self._on_filter_changed()
    
    def _remove_exclude_tag(self, tag: str) -> None:
        self._exclude_tags.discard(tag)
        self._update_tag_bar()
        self._on_filter_changed()
    
    def _clear_tags(self) -> None:
        self._include_tags.clear()
        self._exclude_tags.clear()
        self._update_tag_bar()
        self._on_filter_changed()
    
    def _on_anime_clicked(self, anime: Anime) -> None:
        """Single click - show in detail panel."""
        self.detail_panel.show_anime(anime)
    
    def _on_anime_double_clicked(self, anime: Anime) -> None:
        """Double click - show in detail panel."""
        self.detail_panel.show_anime(anime)
    
    def _on_anime_right_clicked(self, anime: Anime) -> None:
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #2b2b2b; border: 1px solid #3a3a3a; border-radius: 8px; padding: 5px; }
            QMenu::item { background-color: transparent; color: #ffffff; padding: 8px 20px; border-radius: 4px; }
            QMenu::item:selected { background-color: #0078d4; }
        """)
        
        add_action = QAction("📚 加入动漫历史", self)
        add_action.triggered.connect(lambda: self._add_to_history(anime))
        menu.addAction(add_action)
        
        copy_action = QAction("🔗 复制链接", self)
        copy_action.triggered.connect(lambda: self._copy_link(anime))
        menu.addAction(copy_action)
        
        menu.exec(QCursor.pos())
    
    def _open_link(self, url: str) -> None:
        webbrowser.open(url)
    
    def _add_to_history(self, anime: Anime) -> None:
        if self.history_manager.add(anime):
            self.anime_added_to_history.emit(anime)
            QMessageBox.information(self, "添加成功", f"《{anime.name}》已加入动漫历史")
        else:
            QMessageBox.information(self, "已存在", f"《{anime.name}》已在动漫历史中")
    
    def _copy_link(self, anime: Anime) -> None:
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(anime.bangumi_url)

    def apply_theme(self, theme: str) -> None:
        """Apply theme to anime search page components."""
        if theme == 'light':
            bg_primary = '#FFFFFF'
            bg_secondary = '#F3F3F3'
            bg_card = '#FAFAFA'
            text_primary = '#000000'
            text_secondary = '#333333'
            text_muted = '#666666'
            border_color = '#E0E0E0'
            accent_color = '#0078D4'
        else:
            bg_primary = '#1e1e1e'
            bg_secondary = '#2b2b2b'
            bg_card = '#252525'
            text_primary = '#ffffff'
            text_secondary = '#cccccc'
            text_muted = '#888888'
            border_color = '#3a3a3a'
            accent_color = '#0078d4'
        
        # Main page background
        self.setStyleSheet(f"AnimeSearchPage {{ background-color: {bg_primary}; }}")
        
        # Toolbar
        if hasattr(self, 'toolbar'):
            self.toolbar.setStyleSheet(f"background-color: {bg_secondary}; border-bottom: 1px solid {border_color};")
        
        # Toolbar labels
        for attr in ['type_label', 'sort_label', 'year_label']:
            if hasattr(self, attr):
                getattr(self, attr).setStyleSheet(f"color: {text_primary}; font-size: 14px; background: transparent;")
        
        # Search input
        if hasattr(self, 'search_input'):
            self.search_input.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {bg_primary}; border: 1px solid {border_color};
                    border-radius: 8px; padding: 0 15px; color: {text_primary}; font-size: 14px;
                }}
                QLineEdit:focus {{ border: 1px solid {accent_color}; }}
                QLineEdit::placeholder {{ color: {text_muted}; }}
            """)
        
        # Combo boxes
        for attr in ['type_combo', 'sort_combo', 'year_combo']:
            if hasattr(self, attr):
                getattr(self, attr).setStyleSheet(f"""
                    QComboBox {{
                        background-color: {bg_primary}; border: 1px solid {border_color};
                        border-radius: 8px; padding: 0 15px; color: {text_primary}; font-size: 14px;
                    }}
                    QComboBox:hover {{ border: 1px solid {text_muted}; }}
                    QComboBox::drop-down {{ border: none; width: 30px; }}
                    QComboBox::down-arrow {{
                        image: none; border-left: 5px solid transparent;
                        border-right: 5px solid transparent; border-top: 5px solid {text_primary}; margin-right: 10px;
                    }}
                    QComboBox QAbstractItemView {{
                        background-color: {bg_secondary}; border: 1px solid {border_color};
                        selection-background-color: {accent_color}; color: {text_primary};
                    }}
                """)
        
        # Splitter
        if hasattr(self, 'splitter'):
            self.splitter.setStyleSheet(f"""
                QSplitter::handle {{ background-color: {border_color}; }}
                QSplitter::handle:hover {{ background-color: {accent_color}; }}
            """)
        
        # Right scroll area
        if hasattr(self, 'right_scroll'):
            self.right_scroll.setStyleSheet(f"""
                QScrollArea {{ background-color: {bg_primary}; border: none; }}
                QScrollBar:vertical {{
                    background-color: {bg_secondary}; width: 10px; border-radius: 5px;
                }}
                QScrollBar::handle:vertical {{
                    background-color: {border_color}; border-radius: 5px; min-height: 20px;
                }}
            """)
        
        # Tag filter bar
        if hasattr(self, 'tag_filter_bar'):
            self.tag_filter_bar.setStyleSheet(f"background-color: {bg_card}; border-bottom: 1px solid {border_color};")
        
        # Tag filter label
        if hasattr(self, 'tag_filter_label'):
            self.tag_filter_label.setStyleSheet(f"color: {text_muted}; font-size: 12px; background: transparent;")
        
        # Clear tags button
        if hasattr(self, 'clear_tags_btn'):
            self.clear_tags_btn.setStyleSheet(f"""
                QPushButton {{ background-color: {border_color}; color: {text_primary}; border: none; border-radius: 4px; font-size: 12px; }}
                QPushButton:hover {{ background-color: {text_muted}; }}
            """)
        
        # Pagination bar
        if hasattr(self, 'pagination_bar'):
            self.pagination_bar.setStyleSheet(f"background-color: {bg_secondary}; border-top: 1px solid {border_color};")
        
        # Page label
        if hasattr(self, 'page_label'):
            self.page_label.setStyleSheet(f"color: {text_primary}; font-size: 14px; background: transparent;")
        
        # Results label
        if hasattr(self, 'results_label'):
            self.results_label.setStyleSheet(f"color: {text_muted}; font-size: 12px; background: transparent;")
        
        # Navigation buttons
        for attr in ['prev_btn', 'next_btn']:
            if hasattr(self, attr):
                getattr(self, attr).setStyleSheet(f"""
                    QPushButton {{
                        background-color: {border_color};
                        color: {text_primary};
                        border: none;
                        border-radius: 4px;
                        font-size: 12px;
                    }}
                    QPushButton:hover {{
                        background-color: {text_muted};
                    }}
                    QPushButton:disabled {{
                        background-color: {bg_secondary};
                        color: {text_muted};
                    }}
                """)
        
        # Apply theme to detail panel
        if hasattr(self, 'detail_panel'):
            self.detail_panel.apply_theme(theme)
        
        # Apply theme to anime grid
        if hasattr(self, 'anime_grid') and hasattr(self.anime_grid, 'apply_theme'):
            self.anime_grid.apply_theme(theme)
