"""E-Hentai source page implementation."""

from typing import Optional, List
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt

from pancomic.ui.pages.base_source_page import BaseSourcePage
from pancomic.adapters.ehentai_adapter import EHentaiAdapter
from pancomic.models.comic import Comic
from pancomic.models.chapter import Chapter
from pancomic.infrastructure.download_manager import DownloadManager


class EHentaiPage(BaseSourcePage):
    """
    E-Hentai source page.
    
    This page provides interface for browsing E-Hentai comics.
    Currently hidden/disabled.
    """
    
    def __init__(self, adapter: EHentaiAdapter, download_manager: DownloadManager, parent: Optional[QWidget] = None):
        """
        Initialize EHentaiPage.
        
        Args:
            adapter: E-Hentai adapter instance
            download_manager: Download manager instance
            parent: Parent widget
        """
        super().__init__(adapter, download_manager, parent)
        self.adapter = adapter
        self._setup_hidden_ui()
    
    def _setup_hidden_ui(self) -> None:
        """Setup UI showing that EHentai is temporarily disabled."""
        # Clear existing layout
        for i in reversed(range(self.layout().count())):
            self.layout().itemAt(i).widget().setParent(None)
        
        # Add disabled message
        message_label = QLabel("E-Hentai功能暂时不可用")
        message_label.setAlignment(Qt.AlignCenter)
        message_label.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 18px;
                font-weight: bold;
                padding: 50px;
            }
        """)
        
        detail_label = QLabel("此功能正在维护中，请使用其他漫画源")
        detail_label.setAlignment(Qt.AlignCenter)
        detail_label.setStyleSheet("""
            QLabel {
                color: #666666;
                font-size: 14px;
                padding: 20px;
            }
        """)
        
        layout = QVBoxLayout()
        layout.addStretch()
        layout.addWidget(message_label)
        layout.addWidget(detail_label)
        layout.addStretch()
        
        # Replace the main layout
        self.setLayout(layout)
    
    def search_comics(self, keyword: str, page: int = 1) -> None:
        """Search comics (disabled)."""
        pass
    
    def load_more_comics(self) -> None:
        """Load more comics (disabled)."""
        pass
    
    def _on_search_completed(self, comics: List[Comic]) -> None:
        """Handle search completion (disabled)."""
        pass
    
    def _on_search_failed(self, error: str) -> None:
        """Handle search failure (disabled)."""
        pass