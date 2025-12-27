"""Download task data model."""

from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

# Import Comic and Chapter models
from .comic import Comic
from .chapter import Chapter


@dataclass
class DownloadTask:
    """Download task model.
    
    Represents a comic download task with progress tracking.
    """
    
    task_id: str
    comic: Comic
    chapters: List[Chapter]
    status: str  # "queued", "downloading", "paused", "completed", "failed"
    progress: int  # 0-100
    current_chapter: int
    total_chapters: int
    error_message: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Validate required fields after initialization."""
        # Validate task_id
        if not self.task_id or not isinstance(self.task_id, str):
            raise ValueError("DownloadTask task_id must be a non-empty string")
        
        # Validate comic
        if not isinstance(self.comic, Comic):
            raise ValueError("DownloadTask comic must be a Comic instance")
        
        # Validate chapters
        if not isinstance(self.chapters, list):
            raise ValueError("DownloadTask chapters must be a list")
        if not all(isinstance(ch, Chapter) for ch in self.chapters):
            raise ValueError("DownloadTask chapters must contain only Chapter instances")
        
        # Validate status
        valid_statuses = ["queued", "downloading", "paused", "completed", "failed"]
        if self.status not in valid_statuses:
            raise ValueError(f"DownloadTask status must be one of {valid_statuses}, got '{self.status}'")
        
        # Validate progress (0-100)
        if not isinstance(self.progress, int) or not (0 <= self.progress <= 100):
            raise ValueError("DownloadTask progress must be an integer between 0 and 100")
        
        # Validate current_chapter
        if not isinstance(self.current_chapter, int) or self.current_chapter < 0:
            raise ValueError("DownloadTask current_chapter must be a non-negative integer")
        
        # Validate total_chapters
        if not isinstance(self.total_chapters, int) or self.total_chapters < 0:
            raise ValueError("DownloadTask total_chapters must be a non-negative integer")
        
        # Validate created_at
        if not isinstance(self.created_at, datetime):
            raise ValueError("DownloadTask created_at must be a datetime instance")
        
        # Validate completed_at if present
        if self.completed_at is not None and not isinstance(self.completed_at, datetime):
            raise ValueError("DownloadTask completed_at must be a datetime instance or None")
    
    def calculate_progress(self) -> int:
        """Calculate download progress as a percentage.
        
        Returns:
            Progress percentage (0-100) based on completed chapters.
        """
        if self.total_chapters == 0:
            return 0
        
        # Calculate progress based on completed chapters
        progress = int((self.current_chapter / self.total_chapters) * 100)
        return min(100, max(0, progress))  # Clamp to 0-100
    
    def update_progress(self, current_chapter: int) -> None:
        """Update progress based on current chapter.
        
        Args:
            current_chapter: Number of chapters completed so far.
        """
        if not isinstance(current_chapter, int) or current_chapter < 0:
            raise ValueError("current_chapter must be a non-negative integer")
        
        if current_chapter > self.total_chapters:
            raise ValueError("current_chapter cannot exceed total_chapters")
        
        self.current_chapter = current_chapter
        self.progress = self.calculate_progress()
    
    def mark_completed(self) -> None:
        """Mark the download task as completed."""
        self.status = "completed"
        self.progress = 100
        self.current_chapter = self.total_chapters
        self.completed_at = datetime.now()
        self.error_message = None
    
    def mark_failed(self, error_message: str) -> None:
        """Mark the download task as failed.
        
        Args:
            error_message: Description of the failure reason.
        """
        if not error_message or not isinstance(error_message, str):
            raise ValueError("error_message must be a non-empty string")
        
        self.status = "failed"
        self.error_message = error_message
    
    def pause(self) -> None:
        """Pause the download task."""
        if self.status == "downloading":
            self.status = "paused"
    
    def resume(self) -> None:
        """Resume the download task."""
        if self.status == "paused":
            self.status = "downloading"
    
    def is_active(self) -> bool:
        """Check if the task is currently active (downloading).
        
        Returns:
            True if status is "downloading", False otherwise.
        """
        return self.status == "downloading"
    
    def is_finished(self) -> bool:
        """Check if the task is finished (completed or failed).
        
        Returns:
            True if status is "completed" or "failed", False otherwise.
        """
        return self.status in ["completed", "failed"]
