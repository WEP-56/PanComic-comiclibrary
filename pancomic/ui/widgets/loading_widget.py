"""Loading widget with animated indicator."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPainter, QColor, QPen


class LoadingWidget(QWidget):
    """
    Animated loading indicator widget with Fluent Design styling.
    
    Displays a spinning circle animation to indicate loading state.
    Can be shown/hidden as needed.
    """
    
    def __init__(self, parent=None):
        """
        Initialize LoadingWidget.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Widget properties
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        
        # Setup UI
        self._setup_ui()
        
        # Initially hidden
        self.hide()
    
    def _setup_ui(self) -> None:
        """Initialize UI components and layout."""
        # Set widget properties
        self.setFixedSize(80, 80)
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Optional: Add loading text label
        self._label = QLabel("加载中...", self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet("""
            QLabel {
                color: #0078d4;
                font-size: 12px;
                font-family: 'Segoe UI', Arial, sans-serif;
                margin-top: 5px;
            }
        """)
        layout.addWidget(self._label)
        
        # Set background
        self.setStyleSheet("""
            LoadingWidget {
                background-color: transparent;
            }
        """)
    
    def _rotate(self) -> None:
        """Update rotation angle and trigger repaint."""
        self._angle = (self._angle + 10) % 360
        self.update()
    
    def paintEvent(self, event) -> None:
        """
        Paint the loading spinner.
        
        Args:
            event: Paint event
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Calculate center and radius
        center_x = self.width() // 2
        center_y = (self.height() - self._label.height()) // 2
        radius = 20
        
        # Draw spinning arcs
        pen = QPen(QColor("#0078d4"))
        pen.setWidth(3)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        
        # Draw multiple arcs with decreasing opacity for trail effect
        for i in range(8):
            angle_offset = i * 45
            current_angle = (self._angle + angle_offset) % 360
            
            # Calculate opacity (fade out for trailing arcs)
            opacity = 1.0 - (i * 0.12)
            color = QColor("#0078d4")
            color.setAlphaF(opacity)
            pen.setColor(color)
            painter.setPen(pen)
            
            # Draw arc
            start_angle = current_angle * 16  # Qt uses 1/16th degree units
            span_angle = 30 * 16  # 30 degree arc
            
            painter.drawArc(
                center_x - radius,
                center_y - radius,
                radius * 2,
                radius * 2,
                start_angle,
                span_angle
            )
    
    def show(self) -> None:
        """Show the loading widget and start animation."""
        super().show()
        self._timer.start(50)  # Update every 50ms for smooth animation
    
    def hide(self) -> None:
        """Hide the loading widget and stop animation."""
        self._timer.stop()
        super().hide()
    
    def set_text(self, text: str) -> None:
        """
        Set the loading text.
        
        Args:
            text: Text to display below spinner
        """
        self._label.setText(text)
    
    def is_loading(self) -> bool:
        """
        Check if widget is currently showing.
        
        Returns:
            True if loading widget is visible
        """
        return self.isVisible()
