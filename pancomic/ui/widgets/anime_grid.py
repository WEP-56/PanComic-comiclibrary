"""Anime grid widget with responsive layout support."""

import os
from typing import List, Optional
from PySide6.QtWidgets import (
    QWidget, QScrollArea, QGridLayout, QLabel, QVBoxLayout, QFrame
)
from PySide6.QtCore import Qt, Signal
from pancomic.models.anime import Anime
from pancomic.ui.widgets.anime_card import AnimeCard


class AnimeGrid(QScrollArea):
    """Grid layout for displaying anime cards with responsive columns."""
    
    # Signals for anime interactions
    anime_clicked = Signal(object)  # Anime object
    anime_double_clicked = Signal(object)  # Anime object
    anime_right_clicked = Signal(object)  # Anime object
    tag_include_requested = Signal(str)  # Tag to include in filter
    tag_exclude_requested = Signal(str)  # Tag to exclude from filter

    def __init__(self, parent: Optional[QWidget] = None, columns: int = 3):
        """
        Initialize AnimeGrid.
        
        Args:
            parent: Parent widget
            columns: Number of columns in the grid (will be adjusted based on container width)
        """
        super().__init__(parent)
        
        # Store initial columns value
        self.initial_columns = columns
        
        # Main container widget
        self.container = QWidget()
        self.setWidget(self.container)
        self.setWidgetResizable(True)
        
        # Grid layout for anime cards
        self.grid_layout = QGridLayout(self.container)
        self.grid_layout.setContentsMargins(20, 20, 20, 20)  # 20px margins
        self.grid_layout.setSpacing(15)  # 15px spacing between items
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        # List to keep track of anime cards for theme support
        self._anime_cards = []
        
        # Track current column count
        self._current_columns = columns
        
        # Initially set up the UI
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Setup UI components."""
        # Set scroll area properties
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setFrameShape(QFrame.Shape.NoFrame)
        
        # Apply default theme
        self.apply_theme('dark')
    
    def resizeEvent(self, event):
        """Handle resize event to adjust grid columns."""
        super().resizeEvent(event)
        # Adjust columns after resize
        self._adjust_columns()
    
    def _adjust_columns(self) -> None:
        """Adjust the number of columns based on container width."""
        if not self._anime_cards:
            return
            
        # Calculate available width (subtract margins)
        available_width = self.viewport().width() - 40  # 20px margins on each side
        
        # AnimeCard width is 200px
        card_width = 200
        spacing = 15  # Grid spacing from layout
        
        # Calculate how many columns fit in the available width
        # Each column takes up card_width + spacing (except for the last column)
        potential_columns = max(1, (available_width + spacing) // (card_width + spacing))
        
        # Only update if we have a valid column count
        if potential_columns >= 1:
            self._rearrange_cards(potential_columns)
    
    def _rearrange_cards(self, columns: int) -> None:
        """Rearrange anime cards with new column count."""
        if not self._anime_cards:
            return
        
        # Update current columns
        self._current_columns = columns
        
        # Remove all cards from the layout
        for card in self._anime_cards:
            self.grid_layout.removeWidget(card)
        
        # Add cards back with new column arrangement
        for i, card in enumerate(self._anime_cards):
            row = i // columns
            col = i % columns
            self.grid_layout.addWidget(card, row, col)
    
    def add_animes(self, animes: List[Anime]) -> None:
        """
        Add anime cards to the grid.
        
        Args:
            animes: List of Anime objects to display
        """
        for anime in animes:
            card = AnimeCard(anime)
            
            # Connect signals
            card.clicked.connect(lambda a=anime: self.anime_clicked.emit(a))
            card.double_clicked.connect(lambda a=anime: self.anime_double_clicked.emit(a))
            card.right_clicked.connect(lambda a=anime: self.anime_right_clicked.emit(a))
            card.tag_include_requested.connect(self.tag_include_requested)
            card.tag_exclude_requested.connect(self.tag_exclude_requested)
            
            # Add to layout using the current number of columns
            current_row = self.grid_layout.count() // self._current_columns
            current_col = self.grid_layout.count() % self._current_columns
            
            self.grid_layout.addWidget(card, current_row, current_col)
            
            # Store reference for theme support and column adjustment
            self._anime_cards.append(card)
        
        # Adjust columns after adding anime cards
        self._adjust_columns()
    
    def set_animes(self, animes: List[Anime]) -> None:
        """
        Replace current anime list with new list.
        
        Args:
            animes: New list of Anime objects
        """
        self.clear()
        self.add_animes(animes)
    
    def clear(self) -> None:
        """Clear all anime cards from the grid."""
        # Remove and delete all cards
        for card in self._anime_cards:
            self.grid_layout.removeWidget(card)
            card.deleteLater()
        
        # Clear the list
        self._anime_cards.clear()
    
    def apply_theme(self, theme: str) -> None:
        """
        Apply theme to the grid and all anime cards.
        
        Args:
            theme: Theme name ('light' or 'dark')
        """
        if theme == 'light':
            # Light theme colors
            bg_primary = '#FFFFFF'
            bg_secondary = '#F3F3F3'
            text_primary = '#000000'
            text_secondary = '#333333'
            border_color = '#E0E0E0'
        else:
            # Dark theme colors
            bg_primary = '#1e1e1e'
            bg_secondary = '#2b2b2b'
            text_primary = '#ffffff'
            text_secondary = '#cccccc'
            border_color = '#3a3a3a'
        
        # Scroll area background
        self.setStyleSheet(f"""
            QScrollArea {{
                background-color: {bg_primary};
                border: none;
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
            QScrollBar::handle:vertical:hover {{ background-color: {text_secondary}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
        """)
        
        # Container background
        self.container.setStyleSheet(f"background-color: {bg_primary};")
        
        # Apply theme to all anime cards
        for card in self._anime_cards:
            if hasattr(card, 'apply_theme'):
                card.apply_theme(theme)