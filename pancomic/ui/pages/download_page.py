"""Download management page showing active downloads and queue."""

from typing import Dict, Optional, Set
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QProgressBar, QFrame, QSplitter, QCheckBox
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QPixmap

from pancomic.infrastructure.download_manager import DownloadManager
from pancomic.infrastructure.comic_queue_manager import ComicQueueManager, QueueItem
from pancomic.models.download_task import DownloadTask


class DownloadingTaskCard(QFrame):
    """Card widget for an active downloading task."""
    
    pause_clicked = Signal(str)
    cancel_clicked = Signal(str)
    
    def __init__(self, task: DownloadTask, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.task = task
        self.task_id = task.task_id
        self._current_theme = 'dark'
        self.setFixedHeight(80)
        self._setup_ui()
        self._update_ui()
    
    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)
        
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(50, 60)
        self.cover_label.setStyleSheet("border-radius: 4px; background-color: #3a3a3a;")
        layout.addWidget(self.cover_label)
        
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        
        self.title_label = QLabel()
        self.title_label.setObjectName("task_title")
        info_layout.addWidget(self.title_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setFixedHeight(18)
        info_layout.addWidget(self.progress_bar)
        
        self.chapter_label = QLabel()
        self.chapter_label.setObjectName("task_chapter")
        info_layout.addWidget(self.chapter_label)
        
        layout.addLayout(info_layout, 1)
        
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(4)
        
        self.pause_button = QPushButton("暂停")
        self.pause_button.setFixedSize(60, 28)
        self.pause_button.clicked.connect(self._on_pause)
        btn_layout.addWidget(self.pause_button)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setFixedSize(60, 28)
        self.cancel_button.setObjectName("cancel_btn")
        self.cancel_button.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self.cancel_button)
        
        layout.addLayout(btn_layout)
    
    def _on_pause(self):
        self.pause_clicked.emit(self.task_id)
    
    def _on_cancel(self):
        self.cancel_clicked.emit(self.task_id)
    
    def _update_ui(self) -> None:
        self.title_label.setText(self.task.comic.title if self.task.comic else "Unknown")
        self.progress_bar.setValue(self.task.progress)
        self.chapter_label.setText(f"章节: {self.task.current_chapter} / {self.task.total_chapters}")
        self.pause_button.setText("继续" if self.task.status == "paused" else "暂停")
    
    def update_task(self, task: DownloadTask) -> None:
        self.task = task
        self._update_ui()
    
    def update_progress_only(self, progress: int, current: int, total: int) -> None:
        self.progress_bar.setValue(progress)
        self.chapter_label.setText(f"章节: {current} / {total}")

    def apply_theme(self, theme: str) -> None:
        self._current_theme = theme
        if theme == 'light':
            bg, text, text_muted, border, accent = '#FFFFFF', '#000000', '#666666', '#E0E0E0', '#0078D4'
            bg_secondary = '#F3F3F3'
        else:
            bg, text, text_muted, border, accent = '#2b2b2b', '#ffffff', '#888888', '#3a3a3a', '#0078d4'
            bg_secondary = '#1e1e1e'
        
        self.setStyleSheet(f"""
            DownloadingTaskCard {{ background-color: {bg}; border: 1px solid {border}; border-radius: 8px; }}
            QLabel#task_title {{ font-size: 13px; font-weight: bold; color: {text}; }}
            QLabel#task_chapter {{ font-size: 11px; color: {text_muted}; }}
            QProgressBar {{ border: 1px solid {border}; border-radius: 4px; background-color: {bg_secondary}; text-align: center; color: {text}; }}
            QProgressBar::chunk {{ background-color: {accent}; border-radius: 3px; }}
            QPushButton {{ background-color: {border}; border: none; border-radius: 4px; color: {text}; font-size: 11px; }}
            QPushButton:hover {{ background-color: {text_muted}; }}
            QPushButton#cancel_btn {{ background-color: #c42b1c; color: white; }}
            QPushButton#cancel_btn:hover {{ background-color: #d13438; }}
        """)


class QueueTaskCard(QFrame):
    """Card widget for a queued task with checkbox."""
    
    start_clicked = Signal(str)
    remove_clicked = Signal(str)
    checked_changed = Signal(str, bool)
    
    def __init__(self, item: QueueItem, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.item = item
        self.item_id = item.id
        self._current_theme = 'dark'
        self._checked = False
        self.setFixedHeight(70)
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Checkbox
        self.checkbox = QCheckBox()
        self.checkbox.stateChanged.connect(self._on_check_changed)
        layout.addWidget(self.checkbox)
        
        # Cover
        self.cover_label = QLabel()
        self.cover_label.setFixedSize(40, 50)
        self.cover_label.setStyleSheet("border-radius: 4px; background-color: #3a3a3a;")
        self.cover_label.setText("...")
        layout.addWidget(self.cover_label)
        
        # Info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        
        self.title_label = QLabel(self.item.comic_title)
        self.title_label.setObjectName("queue_title")
        info_layout.addWidget(self.title_label)
        
        info_text = f"作者: {self.item.comic_author} | {self.item.chapter_count} 章节 | {self.item.source}"
        self.info_label = QLabel(info_text)
        self.info_label.setObjectName("queue_info")
        info_layout.addWidget(self.info_label)
        
        layout.addLayout(info_layout, 1)
        
        # Buttons (vertical)
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(4)
        
        self.start_button = QPushButton("下载")
        self.start_button.setFixedSize(60, 26)
        self.start_button.clicked.connect(lambda: self.start_clicked.emit(self.item_id))
        btn_layout.addWidget(self.start_button)
        
        self.remove_button = QPushButton("移除")
        self.remove_button.setFixedSize(60, 26)
        self.remove_button.setObjectName("remove_btn")
        self.remove_button.clicked.connect(lambda: self.remove_clicked.emit(self.item_id))
        btn_layout.addWidget(self.remove_button)
        
        layout.addLayout(btn_layout)
    
    def _on_check_changed(self, state: int) -> None:
        self._checked = state == Qt.CheckState.Checked.value
        self.checked_changed.emit(self.item_id, self._checked)
    
    def is_checked(self) -> bool:
        return self._checked
    
    def set_checked(self, checked: bool) -> None:
        self._checked = checked
        self.checkbox.setChecked(checked)
    
    def apply_theme(self, theme: str) -> None:
        self._current_theme = theme
        if theme == 'light':
            bg, text, text_muted, border, accent = '#FFFFFF', '#000000', '#666666', '#E0E0E0', '#0078D4'
        else:
            bg, text, text_muted, border, accent = '#2b2b2b', '#ffffff', '#888888', '#3a3a3a', '#0078d4'
        
        self.setStyleSheet(f"""
            QueueTaskCard {{ background-color: {bg}; border: 1px solid {border}; border-radius: 8px; }}
            QLabel#queue_title {{ font-size: 13px; font-weight: bold; color: {text}; }}
            QLabel#queue_info {{ font-size: 11px; color: {text_muted}; }}
            QCheckBox {{ spacing: 5px; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 3px; border: 1px solid {border}; background-color: {bg}; }}
            QCheckBox::indicator:checked {{ background-color: {accent}; border: 1px solid {accent}; }}
            QPushButton {{ background-color: {accent}; border: none; border-radius: 4px; color: white; font-size: 11px; }}
            QPushButton:hover {{ background-color: #1084d8; }}
            QPushButton#remove_btn {{ background-color: {border}; color: {text}; }}
            QPushButton#remove_btn:hover {{ background-color: #c42b1c; color: white; }}
        """)


class DownloadPage(QWidget):
    """Download management page with downloading and queue sections."""
    
    # Signal to request download start (DownloadTask data as dict)
    start_download_requested = Signal(dict)
    
    def __init__(self, download_manager: DownloadManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.download_manager = download_manager
        self.queue_manager = ComicQueueManager()
        self.downloading_widgets: Dict[str, DownloadingTaskCard] = {}
        self.queue_widgets: Dict[str, QueueTaskCard] = {}
        self._checked_items: Set[str] = set()
        self._current_theme = 'dark'
        self._is_refreshing = False
        
        self._setup_ui()
        self._connect_signals()
        
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._safe_refresh)
        self.refresh_timer.start(3000)
        
        QTimer.singleShot(100, self._safe_refresh)
    
    def showEvent(self, event):
        super().showEvent(event)
        if not self.refresh_timer.isActive():
            self.refresh_timer.start(3000)
        self._safe_refresh()
    
    def hideEvent(self, event):
        super().hideEvent(event)
        self.refresh_timer.stop()
    
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setHandleWidth(4)
        
        self.downloading_section = self._create_downloading_section()
        self.splitter.addWidget(self.downloading_section)
        
        self.queue_section = self._create_queue_section()
        self.splitter.addWidget(self.queue_section)
        
        self.splitter.setSizes([500, 500])
        layout.addWidget(self.splitter)
        self.apply_theme('dark')
    
    def _create_downloading_section(self) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(20, 15, 20, 10)
        layout.setSpacing(10)
        
        header = QHBoxLayout()
        self.downloading_title = QLabel("⬇️ 正在下载")
        self.downloading_title.setObjectName("section_title")
        header.addWidget(self.downloading_title)
        header.addStretch()
        
        self.downloading_count = QLabel("0 个任务")
        self.downloading_count.setObjectName("section_count")
        header.addWidget(self.downloading_count)
        
        self.clear_completed_btn = QPushButton("清除已完成")
        self.clear_completed_btn.setFixedHeight(28)
        self.clear_completed_btn.clicked.connect(self._on_clear_completed)
        header.addWidget(self.clear_completed_btn)
        layout.addLayout(header)
        
        self.downloading_scroll = QScrollArea()
        self.downloading_scroll.setWidgetResizable(True)
        self.downloading_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.downloading_scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        self.downloading_container = QWidget()
        self.downloading_layout = QVBoxLayout(self.downloading_container)
        self.downloading_layout.setSpacing(8)
        self.downloading_layout.setContentsMargins(0, 0, 0, 0)
        self.downloading_layout.addStretch()
        
        self.downloading_scroll.setWidget(self.downloading_container)
        layout.addWidget(self.downloading_scroll)
        
        self.downloading_empty = QLabel("暂无下载任务")
        self.downloading_empty.setObjectName("empty_label")
        self.downloading_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.downloading_layout.insertWidget(0, self.downloading_empty)
        
        return section
    
    def _create_queue_section(self) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(20, 10, 20, 15)
        layout.setSpacing(10)
        
        header = QHBoxLayout()
        self.queue_title = QLabel("📋 下载队列")
        self.queue_title.setObjectName("section_title")
        header.addWidget(self.queue_title)
        header.addStretch()
        
        self.queue_count = QLabel("0 个任务")
        self.queue_count.setObjectName("section_count")
        header.addWidget(self.queue_count)
        
        # Batch action buttons
        self.start_all_btn = QPushButton("全部开始")
        self.start_all_btn.setFixedHeight(28)
        self.start_all_btn.clicked.connect(self._on_start_all)
        header.addWidget(self.start_all_btn)
        
        self.start_selected_btn = QPushButton("开始勾选")
        self.start_selected_btn.setFixedHeight(28)
        self.start_selected_btn.clicked.connect(self._on_start_selected)
        header.addWidget(self.start_selected_btn)
        
        self.remove_all_btn = QPushButton("全部移除")
        self.remove_all_btn.setFixedHeight(28)
        self.remove_all_btn.clicked.connect(self._on_remove_all)
        header.addWidget(self.remove_all_btn)
        
        self.remove_selected_btn = QPushButton("移除勾选")
        self.remove_selected_btn.setFixedHeight(28)
        self.remove_selected_btn.clicked.connect(self._on_remove_selected)
        header.addWidget(self.remove_selected_btn)
        
        layout.addLayout(header)
        
        self.queue_scroll = QScrollArea()
        self.queue_scroll.setWidgetResizable(True)
        self.queue_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.queue_scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        self.queue_container = QWidget()
        self.queue_layout = QVBoxLayout(self.queue_container)
        self.queue_layout.setSpacing(8)
        self.queue_layout.setContentsMargins(0, 0, 0, 0)
        self.queue_layout.addStretch()
        
        self.queue_scroll.setWidget(self.queue_container)
        layout.addWidget(self.queue_scroll)
        
        self.queue_empty = QLabel("队列为空")
        self.queue_empty.setObjectName("empty_label")
        self.queue_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.queue_layout.insertWidget(0, self.queue_empty)
        
        return section

    def _connect_signals(self) -> None:
        from PySide6.QtCore import Qt as QtCore_Qt
        conn_type = QtCore_Qt.ConnectionType.QueuedConnection
        self.download_manager.download_progress.connect(self._on_download_progress, conn_type)
        self.download_manager.download_completed.connect(self._on_download_completed, conn_type)
        self.download_manager.download_failed.connect(self._on_download_failed, conn_type)
    
    def _safe_refresh(self) -> None:
        if self._is_refreshing:
            return
        self._is_refreshing = True
        try:
            self._load_tasks()
            self._load_queue()
        finally:
            self._is_refreshing = False
    
    def _load_tasks(self) -> None:
        try:
            active_tasks = self.download_manager.get_active_tasks()
        except Exception:
            return
        
        active_ids = {t.task_id for t in active_tasks}
        
        for task in active_tasks:
            if task.task_id not in self.downloading_widgets:
                self._add_downloading_widget(task)
            else:
                self.downloading_widgets[task.task_id].update_task(task)
        
        for task_id in list(self.downloading_widgets.keys()):
            if task_id not in active_ids:
                self._remove_downloading_widget(task_id)
        
        self._update_ui_state()
    
    def _load_queue(self) -> None:
        """Load queue items from persistent storage."""
        self.queue_manager.reload()
        items = self.queue_manager.get_all_items()
        
        item_ids = {item.id for item in items}
        
        for item in items:
            if item.id not in self.queue_widgets:
                self._add_queue_widget(item)
        
        for item_id in list(self.queue_widgets.keys()):
            if item_id not in item_ids:
                self._remove_queue_widget(item_id)
        
        self._update_ui_state()
    
    def _add_downloading_widget(self, task: DownloadTask) -> None:
        widget = DownloadingTaskCard(task, self.downloading_container)
        widget.apply_theme(self._current_theme)
        widget.pause_clicked.connect(self._on_pause_clicked)
        widget.cancel_clicked.connect(self._on_cancel_clicked)
        self.downloading_layout.insertWidget(self.downloading_layout.count() - 1, widget)
        self.downloading_widgets[task.task_id] = widget
    
    def _remove_downloading_widget(self, task_id: str) -> None:
        if task_id in self.downloading_widgets:
            widget = self.downloading_widgets.pop(task_id)
            self.downloading_layout.removeWidget(widget)
            widget.setParent(None)
            widget.deleteLater()
    
    def _add_queue_widget(self, item: QueueItem) -> None:
        widget = QueueTaskCard(item, self.queue_container)
        widget.apply_theme(self._current_theme)
        widget.start_clicked.connect(self._on_start_queue_item)
        widget.remove_clicked.connect(self._on_remove_queue_item)
        widget.checked_changed.connect(self._on_item_checked)
        self.queue_layout.insertWidget(self.queue_layout.count() - 1, widget)
        self.queue_widgets[item.id] = widget
    
    def _remove_queue_widget(self, item_id: str) -> None:
        if item_id in self.queue_widgets:
            widget = self.queue_widgets.pop(item_id)
            self.queue_layout.removeWidget(widget)
            widget.setParent(None)
            widget.deleteLater()
            self._checked_items.discard(item_id)
    
    def _update_ui_state(self) -> None:
        self.downloading_empty.setVisible(len(self.downloading_widgets) == 0)
        self.queue_empty.setVisible(len(self.queue_widgets) == 0)
        self.downloading_count.setText(f"{len(self.downloading_widgets)} 个任务")
        self.queue_count.setText(f"{len(self.queue_widgets)} 个任务")
    
    def _on_item_checked(self, item_id: str, checked: bool) -> None:
        if checked:
            self._checked_items.add(item_id)
        else:
            self._checked_items.discard(item_id)
    
    @Slot(str, int, int)
    def _on_download_progress(self, task_id: str, current: int, total: int) -> None:
        if task_id in self.downloading_widgets:
            progress = int(current / total * 100) if total > 0 else 0
            self.downloading_widgets[task_id].update_progress_only(progress, current, total)
    
    @Slot(str)
    def _on_download_completed(self, task_id: str) -> None:
        QTimer.singleShot(500, self._safe_refresh)
    
    @Slot(str, str)
    def _on_download_failed(self, task_id: str, error: str) -> None:
        QTimer.singleShot(500, self._safe_refresh)
    
    @Slot(str)
    def _on_pause_clicked(self, task_id: str) -> None:
        task = self.download_manager.get_task(task_id)
        if task:
            if task.status == "paused":
                self.download_manager.resume_download(task_id)
            else:
                self.download_manager.pause_download(task_id)
        QTimer.singleShot(100, self._safe_refresh)
    
    @Slot(str)
    def _on_cancel_clicked(self, task_id: str) -> None:
        self.download_manager.cancel_download(task_id)
        self._remove_downloading_widget(task_id)
        self._update_ui_state()
    
    @Slot(str)
    def _on_start_queue_item(self, item_id: str) -> None:
        """Start download for a single queue item."""
        item = self.queue_manager.get_item(item_id)
        if item:
            self.start_download_requested.emit(item.to_dict())
            self.queue_manager.remove_from_queue(item_id)
            self._remove_queue_widget(item_id)
            self._update_ui_state()
    
    @Slot(str)
    def _on_remove_queue_item(self, item_id: str) -> None:
        """Remove a single item from queue."""
        self.queue_manager.remove_from_queue(item_id)
        self._remove_queue_widget(item_id)
        self._update_ui_state()
    
    def _on_clear_completed(self) -> None:
        self.download_manager.clear_completed()
        QTimer.singleShot(100, self._safe_refresh)
    
    def _on_start_all(self) -> None:
        """Start all items in queue."""
        items = self.queue_manager.get_all_items()
        for item in items:
            self.start_download_requested.emit(item.to_dict())
        self.queue_manager.clear_queue()
        self._load_queue()
    
    def _on_start_selected(self) -> None:
        """Start selected items in queue."""
        for item_id in list(self._checked_items):
            item = self.queue_manager.get_item(item_id)
            if item:
                self.start_download_requested.emit(item.to_dict())
                self.queue_manager.remove_from_queue(item_id)
        self._checked_items.clear()
        self._load_queue()
    
    def _on_remove_all(self) -> None:
        """Remove all items from queue."""
        self.queue_manager.clear_queue()
        self._checked_items.clear()
        self._load_queue()
    
    def _on_remove_selected(self) -> None:
        """Remove selected items from queue."""
        for item_id in list(self._checked_items):
            self.queue_manager.remove_from_queue(item_id)
        self._checked_items.clear()
        self._load_queue()
    
    def add_to_queue(self, comic, chapters, source: str) -> None:
        """Add a comic to the download queue."""
        self.queue_manager.add_to_queue(comic, chapters, source)
        self._load_queue()
    
    def refresh(self) -> None:
        QTimer.singleShot(0, self._safe_refresh)
    
    def update_progress(self, task_id: str, current: int, total: int) -> None:
        self._on_download_progress(task_id, current, total)

    def apply_theme(self, theme: str) -> None:
        self._current_theme = theme
        
        if theme == 'light':
            bg_primary, bg_secondary = '#FFFFFF', '#F3F3F3'
            text_primary, text_muted = '#000000', '#666666'
            border_color, accent_color = '#E0E0E0', '#0078D4'
        else:
            bg_primary, bg_secondary = '#1e1e1e', '#2b2b2b'
            text_primary, text_muted = '#ffffff', '#888888'
            border_color, accent_color = '#3a3a3a', '#0078d4'
        
        self.setStyleSheet(f"DownloadPage {{ background-color: {bg_primary}; }}")
        
        self.splitter.setStyleSheet(f"""
            QSplitter::handle {{ background-color: {border_color}; }}
            QSplitter::handle:hover {{ background-color: {accent_color}; }}
        """)
        
        section_style = f"""
            QWidget {{ background-color: {bg_primary}; }}
            QLabel#section_title {{ font-size: 16px; font-weight: bold; color: {text_primary}; }}
            QLabel#section_count {{ font-size: 12px; color: {text_muted}; margin-right: 10px; }}
            QLabel#empty_label {{ font-size: 13px; color: {text_muted}; }}
            QPushButton {{ background-color: {bg_secondary}; border: 1px solid {border_color}; border-radius: 4px; color: {text_primary}; font-size: 12px; padding: 0 12px; }}
            QPushButton:hover {{ background-color: {border_color}; }}
            QScrollArea {{ background-color: {bg_primary}; border: none; }}
            QScrollBar:vertical {{ background-color: {bg_secondary}; width: 10px; border-radius: 5px; }}
            QScrollBar::handle:vertical {{ background-color: {border_color}; border-radius: 5px; min-height: 20px; }}
            QScrollBar::handle:vertical:hover {{ background-color: {text_muted}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        """
        
        self.downloading_section.setStyleSheet(section_style)
        self.queue_section.setStyleSheet(section_style)
        self.downloading_container.setStyleSheet(f"background-color: {bg_primary};")
        self.queue_container.setStyleSheet(f"background-color: {bg_primary};")
        
        for widget in self.downloading_widgets.values():
            widget.apply_theme(theme)
        for widget in self.queue_widgets.values():
            widget.apply_theme(theme)
