"""Comic grid widget for displaying multiple comic cards."""

from typing import List
from PySide6.QtWidgets import (
    QScrollArea, QWidget, QGridLayout, QVBoxLayout
)
from PySide6.QtCore import Qt, Signal

from pancomic.models.comic import Comic
from pancomic.ui.widgets.comic_card import ComicCard


class ComicGrid(QScrollArea):
    """
    Grid layout for comic cards with lazy loading.
    
    Displays comics in a grid with configurable columns (default 6).
    Implements lazy loading by emitting load_more_requested signal
    when user scrolls to 80% of content height.
    """
    
    comic_clicked = Signal(object)  # Emits Comic object
    comic_double_clicked = Signal(object)  # Emits Comic object
    comic_right_clicked = Signal(object)  # Emits Comic object
    chapter_selected = Signal(object, str)  # Emits (Comic, chapter_id)
    load_more_requested = Signal()
    
    def __init__(self, columns: int = 6, parent=None):
        """
        Initialize ComicGrid.
        
        Args:
            columns: Number of columns in grid (default 6)
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.columns = columns
        self.initial_columns = columns  # Store initial column count
        self.cards: List[ComicCard] = []
        self._current_theme = 'dark'  # Track current theme
        
        # Setup UI
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Initialize UI components and layout."""
        # Configure scroll area
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Create container widget
        self.container = QWidget()
        self.setWidget(self.container)
        
        # Create main layout
        main_layout = QVBoxLayout(self.container)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(0)
        
        # Create grid layout
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(15)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        main_layout.addLayout(self.grid_layout)
        main_layout.addStretch()
        
        # Connect scroll event
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)
        
        # Apply styling
        self.setStyleSheet("""
            QScrollArea {
                background-color: #1e1e1e;
                border: none;
            }
            QWidget {
                background-color: #1e1e1e;
            }
            QScrollBar:vertical {
                background-color: #2b2b2b;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #3a3a3a;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #4a4a4a;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
    
    def resizeEvent(self, event):
        """Handle resize event to adjust grid columns."""
        super().resizeEvent(event)
        # Adjust columns after resize
        self._adjust_columns()
    
    def _adjust_columns(self):
        """Adjust the number of columns based on container width."""
        if not self.cards:
            return
            
        # Calculate available width (subtract margins)
        available_width = self.viewport().width() - 40  # 20px margins on each side
        
        # ComicCard width is 180px
        card_width = 180
        spacing = 15  # Grid spacing from layout
        
        # Calculate how many columns fit in the available width
        # Each column takes up card_width + spacing (except for the last column)
        potential_columns = max(1, (available_width + spacing) // (card_width + spacing))
        
        # Only update if the column count changed
        if potential_columns != self.columns and potential_columns >= 1:
            self.set_columns(potential_columns)
    
    def add_comics(self, comics: List[Comic], chapters_map: dict = None) -> None:
        """
        Add comics to the grid.
        
        Args:
            comics: List of Comic objects to add
            chapters_map: Optional dict mapping comic_id to chapters dict
        """
        if not comics:
            return
        
        chapters_map = chapters_map or {}
        start_index = len(self.cards)
        
        for i, comic in enumerate(comics):
            # Get chapters for this comic
            chapters = chapters_map.get(comic.id, {})
            
            # Create comic card with chapters
            card = ComicCard(comic, chapters=chapters)
            card.clicked.connect(lambda c=comic: self.comic_clicked.emit(c))
            card.double_clicked.connect(lambda c=comic: self.comic_double_clicked.emit(c))
            card.right_clicked.connect(lambda c=comic: self.comic_right_clicked.emit(c))
            
            # Connect chapter selection signal
            if chapters:
                card.chapter_selected.connect(
                    lambda ch_id, c=comic: self._on_chapter_selected(c, ch_id)
                )
            
            # Apply current theme to new card
            if hasattr(card, 'apply_theme'):
                card.apply_theme(self._current_theme)
            
            # Calculate grid position
            card_index = start_index + i
            row = card_index // self.columns
            col = card_index % self.columns
            
            # Add to grid
            self.grid_layout.addWidget(card, row, col)
            self.cards.append(card)
        
        # Adjust columns after adding comics
        self._adjust_columns()
    
    def clear(self) -> None:
        """Clear all comics from the grid."""
        # Remove all cards from layout
        for card in self.cards:
            self.grid_layout.removeWidget(card)
            card.deleteLater()
        
        self.cards.clear()
    
    def _on_scroll(self, value: int) -> None:
        """
        Handle scroll event for lazy loading.
        
        Emits load_more_requested signal when scrolled to 80% of content.
        
        Args:
            value: Current scroll position
        """
        scrollbar = self.verticalScrollBar()
        max_value = scrollbar.maximum()
        
        if max_value == 0:
            # No scrolling needed
            return
        
        # Calculate scroll percentage
        scroll_percentage = value / max_value
        
        # Trigger lazy load at 80%
        if scroll_percentage >= 0.8:
            self.load_more_requested.emit()
    
    def get_comic_count(self) -> int:
        """
        Get the number of comics currently displayed.
        
        Returns:
            Number of comic cards in grid
        """
        return len(self.cards)
    
    def get_comics(self) -> List[Comic]:
        """
        Get list of all comics currently displayed.
        
        Returns:
            List of Comic objects
        """
        return [card.comic for card in self.cards]
    
    def scroll_to_top(self) -> None:
        """Scroll to the top of the grid."""
        self.verticalScrollBar().setValue(0)
    
    def set_columns(self, columns: int) -> None:
        """
        Change the number of columns in the grid.
        
        This will re-layout all existing cards.
        
        Args:
            columns: New number of columns
        """
        if columns < 1:
            return
        
        self.columns = columns
        
        # Re-layout existing cards
        for i, card in enumerate(self.cards):
            row = i // self.columns
            col = i % self.columns
            
            # Remove from old position
            self.grid_layout.removeWidget(card)
            
            # Add to new position
            self.grid_layout.addWidget(card, row, col)
    
    def _on_chapter_selected(self, comic: Comic, chapter_id: str) -> None:
        """Handle chapter selection from a comic card."""
        self.chapter_selected.emit(comic, chapter_id)

    def apply_theme(self, theme: str) -> None:
        """Apply theme to comic grid."""
        self._current_theme = theme  # Save current theme
        
        if theme == 'light':
            bg_primary = '#FFFFFF'
            bg_secondary = '#F3F3F3'
            border_color = '#E0E0E0'
        else:
            bg_primary = '#1e1e1e'
            bg_secondary = '#2b2b2b'
            border_color = '#3a3a3a'
        
        self.setStyleSheet(f"""
            QScrollArea {{
                background-color: {bg_primary};
                border: none;
            }}
            QWidget {{
                background-color: {bg_primary};
            }}
            QScrollBar:vertical {{
                background-color: {bg_secondary};
                width: 12px;
                border-radius: 6px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {border_color};
                border-radius: 6px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: #4a4a4a;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
        """)
        
        # Apply theme to all cards
        for card in self.cards:
            if hasattr(card, 'apply_theme'):
                card.apply_theme(theme)