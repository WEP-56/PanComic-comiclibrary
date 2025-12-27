"""Download progress dialog showing active downloads."""

from typing import Dict, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QProgressBar, QFrame
)
from PySide6.QtCore import Qt, Signal, Slot

from pancomic.infrastructure.download_manager import DownloadManager
from pancomic.models.download_task import DownloadTask


class DownloadTaskWidget(QFrame):
    """Widget displaying a single download task with progress."""
    
    # Signals
    pause_clicked = Signal(str)  # task_id
    resume_clicked = Signal(str)  # task_id
    cancel_clicked = Signal(str)  # task_id
    
    def __init__(self, task: DownloadTask, parent: Optional[QWidget] = None):
        """
        Initialize DownloadTaskWidget.
        
        Args:
            task: Download task to display
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.task = task
        
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.setStyleSheet("""
            DownloadTaskWidget {
                background-color: #2b2b2b;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                padding: 10px;
                margin: 5px;
            }
        """)
        
        self._setup_ui()
        self._update_ui()
    
    def _setup_ui(self) -> None:
        """Initialize UI components."""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # Top row: Title and status
        top_layout = QHBoxLayout()
        
        # Title
        self.title_label = QLabel()
        self.title_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #ffffff;
            }
        """)
        top_layout.addWidget(self.title_label, 1)
        
        # Status
        self.status_label = QLabel()
        self.status_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #888888;
            }
        """)
        top_layout.addWidget(self.status_label)
        
        layout.addLayout(top_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                background-color: #1e1e1e;
                text-align: center;
                color: #ffffff;
                height: 24px;
            }
            QProgressBar::chunk {
                background-color: #0078d4;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # Bottom row: Chapter info and buttons
        bottom_layout = QHBoxLayout()
        
        # Chapter info
        self.chapter_label = QLabel()
        self.chapter_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #aaaaaa;
            }
        """)
        bottom_layout.addWidget(self.chapter_label, 1)
        
        # Buttons
        button_style = """
            QPushButton {
                background-color: #3a3a3a;
                border: none;
                border-radius: 4px;
                color: #ffffff;
                font-size: 12px;
                padding: 6px 12px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
            QPushButton:disabled {
                background-color: #2a2a2a;
                color: #666666;
            }
        """
        
        self.pause_button = QPushButton("暂停")
        self.pause_button.setStyleSheet(button_style)
        self.pause_button.clicked.connect(lambda: self.pause_clicked.emit(self.task.task_id))
        bottom_layout.addWidget(self.pause_button)
        
        self.resume_button = QPushButton("继续")
        self.resume_button.setStyleSheet(button_style)
        self.resume_button.clicked.connect(lambda: self.resume_clicked.emit(self.task.task_id))
        self.resume_button.hide()
        bottom_layout.addWidget(self.resume_button)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setStyleSheet(button_style + """
            QPushButton {
                background-color: #c42b1c;
            }
            QPushButton:hover {
                background-color: #d13438;
            }
            QPushButton:pressed {
                background-color: #a52313;
            }
        """)
        self.cancel_button.clicked.connect(lambda: self.cancel_clicked.emit(self.task.task_id))
        bottom_layout.addWidget(self.cancel_button)
        
        layout.addLayout(bottom_layout)
    
    def _update_ui(self) -> None:
        """Update UI with current task state."""
        # Update title
        self.title_label.setText(self.task.comic.title)
        
        # Update status
        status_text = {
            "queued": "排队中",
            "downloading": "下载中",
            "paused": "已暂停",
            "completed": "已完成",
            "failed": "失败"
        }.get(self.task.status, self.task.status)
        self.status_label.setText(status_text)
        
        # Update progress
        self.progress_bar.setValue(self.task.progress)
        
        # Update chapter info
        self.chapter_label.setText(
            f"章节: {self.task.current_chapter} / {self.task.total_chapters}"
        )
        
        # Update buttons based on status
        if self.task.status == "downloading":
            self.pause_button.show()
            self.resume_button.hide()
            self.cancel_button.setEnabled(True)
        elif self.task.status == "paused":
            self.pause_button.hide()
            self.resume_button.show()
            self.cancel_button.setEnabled(True)
        elif self.task.status in ["completed", "failed"]:
            self.pause_button.hide()
            self.resume_button.hide()
            self.cancel_button.setEnabled(False)
        else:  # queued
            self.pause_button.hide()
            self.resume_button.hide()
            self.cancel_button.setEnabled(True)
    
    def update_task(self, task: DownloadTask) -> None:
        """
        Update the task and refresh UI.
        
        Args:
            task: Updated download task
        """
        self.task = task
        self._update_ui()
    
    def update_progress(self, current: int, total: int) -> None:
        """
        Update progress display.
        
        Args:
            current: Current chapter number
            total: Total chapters
        """
        self.task.current_chapter = current
        self.task.total_chapters = total
        self.task.progress = self.task.calculate_progress()
        self._update_ui()


class DownloadProgressDialog(QDialog):
    """
    Dialog displaying active downloads with progress bars.
    
    Shows all active, queued, and recent downloads with controls
    to pause, resume, and cancel downloads.
    """
    
    def __init__(self, download_manager: DownloadManager, parent: Optional[QWidget] = None):
        """
        Initialize DownloadProgressDialog.
        
        Args:
            download_manager: Download manager instance
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.download_manager = download_manager
        self.task_widgets: Dict[str, DownloadTaskWidget] = {}
        
        self.setWindowTitle("下载管理")
        self.setMinimumSize(600, 400)
        self.resize(700, 500)
        
        self._setup_ui()
        self._connect_signals()
        self._load_tasks()
    
    def _setup_ui(self) -> None:
        """Initialize UI components."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Header
        header_layout = QHBoxLayout()
        
        title_label = QLabel("下载管理")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #ffffff;
            }
        """)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Clear completed button
        self.clear_button = QPushButton("清除已完成")
        self.clear_button.setFixedHeight(32)
        self.clear_button.clicked.connect(self._on_clear_completed)
        self.clear_button.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                border: none;
                border-radius: 4px;
                color: #ffffff;
                font-size: 13px;
                padding: 0 15px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
        """)
        header_layout.addWidget(self.clear_button)
        
        layout.addLayout(header_layout)
        
        # Scroll area for download tasks
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #1e1e1e;
            }
        """)
        
        # Container for task widgets
        self.tasks_container = QWidget()
        self.tasks_layout = QVBoxLayout(self.tasks_container)
        self.tasks_layout.setSpacing(5)
        self.tasks_layout.setContentsMargins(0, 0, 0, 0)
        self.tasks_layout.addStretch()
        
        scroll_area.setWidget(self.tasks_container)
        layout.addWidget(scroll_area)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_button = QPushButton("关闭")
        close_button.setFixedSize(100, 36)
        close_button.clicked.connect(self.close)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                border: none;
                border-radius: 8px;
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1084d8;
            }
            QPushButton:pressed {
                background-color: #006cbd;
            }
        """)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        
        # Set dialog background
        self.setStyleSheet("""
            DownloadProgressDialog {
                background-color: #1e1e1e;
            }
        """)
    
    def _connect_signals(self) -> None:
        """Connect download manager signals."""
        self.download_manager.download_progress.connect(self._on_download_progress)
        self.download_manager.download_completed.connect(self._on_download_completed)
        self.download_manager.download_failed.connect(self._on_download_failed)
    
    def _load_tasks(self) -> None:
        """Load all active and queued tasks."""
        # Get active tasks
        active_tasks = self.download_manager.get_active_tasks()
        for task in active_tasks:
            self._add_task_widget(task)
        
        # Get queued tasks
        queued_tasks = self.download_manager.get_queued_tasks()
        for task in queued_tasks:
            self._add_task_widget(task)
    
    def _add_task_widget(self, task: DownloadTask) -> None:
        """
        Add a task widget to the dialog.
        
        Args:
            task: Download task to add
        """
        if task.task_id in self.task_widgets:
            # Update existing widget
            self.task_widgets[task.task_id].update_task(task)
            return
        
        # Create new widget
        widget = DownloadTaskWidget(task, self.tasks_container)
        
        # Connect signals
        widget.pause_clicked.connect(self._on_pause_clicked)
        widget.resume_clicked.connect(self._on_resume_clicked)
        widget.cancel_clicked.connect(self._on_cancel_clicked)
        
        # Add to layout (before stretch)
        self.tasks_layout.insertWidget(self.tasks_layout.count() - 1, widget)
        
        # Store reference
        self.task_widgets[task.task_id] = widget
    
    def _remove_task_widget(self, task_id: str) -> None:
        """
        Remove a task widget from the dialog.
        
        Args:
            task_id: Task ID to remove
        """
        if task_id in self.task_widgets:
            widget = self.task_widgets[task_id]
            self.tasks_layout.removeWidget(widget)
            widget.deleteLater()
            del self.task_widgets[task_id]
    
    @Slot(str, int, int)
    def _on_download_progress(self, task_id: str, current: int, total: int) -> None:
        """
        Handle download progress update.
        
        Args:
            task_id: Task identifier
            current: Current chapter
            total: Total chapters
        """
        if task_id in self.task_widgets:
            self.task_widgets[task_id].update_progress(current, total)
    
    @Slot(str)
    def _on_download_completed(self, task_id: str) -> None:
        """
        Handle download completion.
        
        Args:
            task_id: Task identifier
        """
        # Get updated task
        task = self.download_manager.get_task(task_id)
        if task and task_id in self.task_widgets:
            self.task_widgets[task_id].update_task(task)
    
    @Slot(str, str)
    def _on_download_failed(self, task_id: str, error: str) -> None:
        """
        Handle download failure.
        
        Args:
            task_id: Task identifier
            error: Error message
        """
        # Get updated task
        task = self.download_manager.get_task(task_id)
        if task and task_id in self.task_widgets:
            self.task_widgets[task_id].update_task(task)
    
    @Slot(str)
    def _on_pause_clicked(self, task_id: str) -> None:
        """
        Handle pause button click.
        
        Args:
            task_id: Task identifier
        """
        self.download_manager.pause_download(task_id)
        
        # Update widget
        task = self.download_manager.get_task(task_id)
        if task and task_id in self.task_widgets:
            self.task_widgets[task_id].update_task(task)
    
    @Slot(str)
    def _on_resume_clicked(self, task_id: str) -> None:
        """
        Handle resume button click.
        
        Args:
            task_id: Task identifier
        """
        self.download_manager.resume_download(task_id)
        
        # Update widget
        task = self.download_manager.get_task(task_id)
        if task and task_id in self.task_widgets:
            self.task_widgets[task_id].update_task(task)
    
    @Slot(str)
    def _on_cancel_clicked(self, task_id: str) -> None:
        """
        Handle cancel button click.
        
        Args:
            task_id: Task identifier
        """
        self.download_manager.cancel_download(task_id)
        
        # Remove widget after a short delay
        self._remove_task_widget(task_id)
    
    def _on_clear_completed(self) -> None:
        """Clear all completed tasks from the list."""
        # Get list of completed task IDs
        completed_ids = [
            task_id for task_id, widget in self.task_widgets.items()
            if widget.task.status == "completed"
        ]
        
        # Remove completed task widgets
        for task_id in completed_ids:
            self._remove_task_widget(task_id)
    
    def refresh(self) -> None:
        """Refresh the task list."""
        # Clear existing widgets
        for task_id in list(self.task_widgets.keys()):
            self._remove_task_widget(task_id)
        
        # Reload tasks
        self._load_tasks()
