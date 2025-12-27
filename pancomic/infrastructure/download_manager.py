"""Download manager for PanComic application."""

import uuid
from pathlib import Path
from typing import Dict, List, Optional, Callable
from datetime import datetime
import threading

try:
    from PySide6.QtCore import QObject, Signal, QThreadPool, QRunnable, Slot
except ImportError:
    # Fallback for testing without PySide6
    class QObject:
        pass
    
    class Signal:
        def __init__(self, *args):
            pass
        
        def emit(self, *args):
            pass
    
    class QThreadPool:
        @staticmethod
        def globalInstance():
            return None
    
    class QRunnable:
        pass
    
    def Slot(*args):
        def decorator(func):
            return func
        return decorator

from pancomic.models.comic import Comic
from pancomic.models.chapter import Chapter
from pancomic.models.download_task import DownloadTask


class DownloadWorker(QRunnable):
    """Worker for downloading a single chapter."""
    
    def __init__(
        self,
        task_id: str,
        comic: Comic,
        chapter: Chapter,
        download_path: Path,
        download_func: Callable,
        on_progress: Callable,
        on_complete: Callable,
        on_error: Callable
    ):
        """
        Initialize download worker.
        
        Args:
            task_id: Task identifier
            comic: Comic being downloaded
            chapter: Chapter to download
            download_path: Path to save downloaded files
            download_func: Function to perform the actual download
            on_progress: Callback for progress updates
            on_complete: Callback when download completes
            on_error: Callback when download fails
        """
        super().__init__()
        self.task_id = task_id
        self.comic = comic
        self.chapter = chapter
        self.download_path = download_path
        self.download_func = download_func
        self.on_progress = on_progress
        self.on_complete = on_complete
        self.on_error = on_error
        self._cancelled = False
    
    def cancel(self):
        """Cancel the download."""
        self._cancelled = True
    
    @Slot()
    def run(self):
        """Execute the download."""
        try:
            if self._cancelled:
                return
            
            # Call the download function
            # This should be provided by the adapter
            self.download_func(
                self.comic,
                self.chapter,
                self.download_path,
                lambda current, total: self.on_progress(self.task_id, self.chapter.id, int(current/total*100) if total > 0 else 0)
            )
            
            if not self._cancelled:
                self.on_complete(self.task_id, self.chapter.id)
                
        except Exception as e:
            if not self._cancelled:
                self.on_error(self.task_id, self.chapter.id, str(e))


class DownloadManager(QObject):
    """
    Download manager with task queue and concurrent download limiting.
    
    Manages comic download tasks with progress tracking, pause/resume,
    and automatic retry functionality.
    """
    
    # Signals for download events
    download_progress = Signal(str, int, int)  # task_id, current, total
    download_completed = Signal(str)  # task_id
    download_failed = Signal(str, str)  # task_id, error
    chapter_progress = Signal(str, str, int)  # task_id, chapter_id, progress
    chapter_completed = Signal(str, str)  # task_id, chapter_id
    chapter_failed = Signal(str, str, str)  # task_id, chapter_id, error
    
    def __init__(self, max_concurrent: int = 3, auto_retry: bool = True, max_retries: int = 3):
        """
        Initialize DownloadManager.
        
        Args:
            max_concurrent: Maximum number of concurrent downloads
            auto_retry: Whether to automatically retry failed downloads
            max_retries: Maximum number of retry attempts
        """
        super().__init__()
        
        self.max_concurrent = max_concurrent
        self.auto_retry = auto_retry
        self.max_retries = max_retries
        
        # Active download tasks
        self.active_tasks: Dict[str, DownloadTask] = {}
        
        # Queued download tasks
        self.queued_tasks: List[DownloadTask] = []
        
        # Completed/failed tasks (for display)
        self.completed_tasks: Dict[str, DownloadTask] = {}
        
        # Download workers
        self.workers: Dict[str, List[DownloadWorker]] = {}
        
        # Retry counts
        self.retry_counts: Dict[str, int] = {}
        
        # Create dedicated thread pool for downloads (not shared with global pool)
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(max_concurrent)
        
        # Lock for thread-safe operations
        self._lock = threading.Lock()
        
        # Download functions per source (to be set by adapters)
        self.download_functions: Dict[str, Callable] = {}
    
    def register_download_function(self, source: str, download_func: Callable) -> None:
        """
        Register a download function for a specific source.
        
        Args:
            source: Source name ('jmcomic', 'picacg')
            download_func: Function to download a chapter
        """
        self.download_functions[source] = download_func
    
    def add_download(
        self,
        comic: Comic,
        chapters: List[Chapter],
        download_path: str
    ) -> str:
        """
        Add a download task.
        
        Args:
            comic: Comic to download
            chapters: List of chapters to download
            download_path: Base path for downloads
            
        Returns:
            Task ID
        """
        # Generate unique task ID
        task_id = str(uuid.uuid4())
        
        # Create download task
        task = DownloadTask(
            task_id=task_id,
            comic=comic,
            chapters=chapters,
            status="queued",
            progress=0,
            current_chapter=0,
            total_chapters=len(chapters),
            error_message=None,
            created_at=datetime.now()
        )
        
        # Store download path in task
        task.download_path = download_path
        
        with self._lock:
            # Add to queue
            self.queued_tasks.append(task)
            
            # Initialize retry count
            self.retry_counts[task_id] = 0
            
            # Process queue
            self._process_queue()
        
        return task_id
    
    def _process_queue(self) -> None:
        """
        Process queued downloads.
        
        This method should be called while holding _lock.
        """
        # Count active downloads
        active_count = len([t for t in self.active_tasks.values() if t.status == "downloading"])
        
        # Start queued downloads if we have capacity
        while active_count < self.max_concurrent and self.queued_tasks:
            task = self.queued_tasks.pop(0)
            self._start_download(task)
            active_count += 1
    
    def _start_download(self, task: DownloadTask) -> None:
        """
        Start downloading a task.
        
        Args:
            task: Download task to start
        """
        task.status = "downloading"
        self.active_tasks[task.task_id] = task
        
        # Get download function for this source
        download_func = self.download_functions.get(task.comic.source)
        if not download_func:
            # Handle missing download function
            error_msg = f"No download function registered for source: {task.comic.source}"
            task.mark_failed(error_msg)
            self.completed_tasks[task.task_id] = task
            del self.active_tasks[task.task_id]
            # Emit signal will be done after lock is released
            return
        
        # Use the download path from the task (stored during add_download)
        from pathlib import Path
        if hasattr(task, 'download_path') and task.download_path:
            download_path = Path(task.download_path)
        else:
            # Fallback to default path
            download_path = Path.home() / "Downloads" / "PanComic"
        
        download_path.mkdir(parents=True, exist_ok=True)
        
        # Create workers for each chapter
        workers = []
        for chapter in task.chapters:
            worker = DownloadWorker(
                task_id=task.task_id,
                comic=task.comic,
                chapter=chapter,
                download_path=download_path,
                download_func=download_func,
                on_progress=self._on_chapter_progress,
                on_complete=self._on_chapter_complete,
                on_error=self._on_chapter_error
            )
            workers.append(worker)
            
            if self.thread_pool:
                self.thread_pool.start(worker)
        
        self.workers[task.task_id] = workers
    
    def _on_chapter_progress(self, task_id: str, chapter_id: str, progress: int) -> None:
        """
        Handle chapter download progress.
        
        Args:
            task_id: Task identifier
            chapter_id: Chapter identifier
            progress: Progress percentage (0-100)
        """
        self.chapter_progress.emit(task_id, chapter_id, progress)
    
    def _on_chapter_complete(self, task_id: str, chapter_id: str) -> None:
        """
        Handle chapter download completion.
        
        Args:
            task_id: Task identifier
            chapter_id: Chapter identifier
        """
        should_emit_progress = False
        should_emit_completed = False
        current_chapter = 0
        total_chapters = 0
        
        with self._lock:
            if task_id not in self.active_tasks:
                return
            
            task = self.active_tasks[task_id]
            task.current_chapter += 1
            task.progress = task.calculate_progress()
            current_chapter = task.current_chapter
            total_chapters = task.total_chapters
            should_emit_progress = True
            
            # Check if all chapters are complete
            if task.current_chapter >= task.total_chapters:
                task.mark_completed()
                self.completed_tasks[task_id] = task
                del self.active_tasks[task_id]
                if task_id in self.workers:
                    del self.workers[task_id]
                should_emit_completed = True
                self._process_queue()
        
        # Emit signals outside of lock to prevent deadlock
        self.chapter_completed.emit(task_id, chapter_id)
        if should_emit_progress:
            self.download_progress.emit(task_id, current_chapter, total_chapters)
        if should_emit_completed:
            self.download_completed.emit(task_id)
    
    def _on_chapter_error(self, task_id: str, chapter_id: str, error: str) -> None:
        """
        Handle chapter download error.
        
        Args:
            task_id: Task identifier
            chapter_id: Chapter identifier
            error: Error message
        """
        # Emit signal outside of lock
        self.chapter_failed.emit(task_id, chapter_id, error)
        
        should_emit_failed = False
        error_msg = ""
        
        with self._lock:
            if task_id not in self.active_tasks:
                return
            
            # Check if we should retry
            if self.auto_retry and self.retry_counts.get(task_id, 0) < self.max_retries:
                self.retry_counts[task_id] += 1
                # Re-queue the task
                task = self.active_tasks[task_id]
                task.status = "queued"
                self.queued_tasks.append(task)
                del self.active_tasks[task_id]
                self._process_queue()
            else:
                # Max retries exceeded, mark as failed
                task = self.active_tasks[task_id]
                error_msg = f"Chapter {chapter_id} failed: {error}"
                task.mark_failed(error_msg)
                self.completed_tasks[task_id] = task
                del self.active_tasks[task_id]
                if task_id in self.workers:
                    del self.workers[task_id]
                should_emit_failed = True
                self._process_queue()
        
        # Emit signal outside of lock
        if should_emit_failed:
            self.download_failed.emit(task_id, error_msg)
    
    def cancel_download(self, task_id: str) -> None:
        """
        Cancel a download task.
        
        Args:
            task_id: Task identifier
        """
        with self._lock:
            # Check if task is active
            if task_id in self.active_tasks:
                # Cancel all workers
                if task_id in self.workers:
                    for worker in self.workers[task_id]:
                        worker.cancel()
                    del self.workers[task_id]
                
                # Remove from active tasks
                del self.active_tasks[task_id]
                
                # Process next queued task
                self._process_queue()
            
            # Check if task is queued
            else:
                self.queued_tasks = [t for t in self.queued_tasks if t.task_id != task_id]
    
    def pause_download(self, task_id: str) -> None:
        """
        Pause a download task.
        
        Args:
            task_id: Task identifier
        """
        with self._lock:
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                task.pause()
                
                # Cancel workers (they will need to be restarted on resume)
                if task_id in self.workers:
                    for worker in self.workers[task_id]:
                        worker.cancel()
                    del self.workers[task_id]
                
                # Process next queued task
                self._process_queue()
    
    def resume_download(self, task_id: str) -> None:
        """
        Resume a paused download task.
        
        Args:
            task_id: Task identifier
        """
        with self._lock:
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                if task.status == "paused":
                    task.resume()
                    # Move to queue for processing
                    self.queued_tasks.insert(0, task)  # Add to front of queue
                    del self.active_tasks[task_id]
                    self._process_queue()
    
    def get_task(self, task_id: str) -> Optional[DownloadTask]:
        """
        Get download task by ID.
        
        Args:
            task_id: Task identifier
            
        Returns:
            DownloadTask if found, None otherwise
        """
        with self._lock:
            # Check active tasks first
            if task_id in self.active_tasks:
                return self.active_tasks[task_id]
            # Check completed tasks
            if task_id in self.completed_tasks:
                return self.completed_tasks[task_id]
            # Check queued tasks
            for task in self.queued_tasks:
                if task.task_id == task_id:
                    return task
            return None
    
    def get_active_tasks(self) -> List[DownloadTask]:
        """
        Get all active download tasks (including completed/failed for display).
        
        Returns:
            List of active DownloadTask instances
        """
        with self._lock:
            # Return active tasks + completed tasks for display
            all_tasks = list(self.active_tasks.values()) + list(self.completed_tasks.values())
            return all_tasks
    
    def get_queued_tasks(self) -> List[DownloadTask]:
        """
        Get all queued download tasks.
        
        Returns:
            List of queued DownloadTask instances
        """
        with self._lock:
            return list(self.queued_tasks)
    
    def set_max_concurrent(self, max_concurrent: int) -> None:
        """
        Set maximum concurrent downloads.
        
        Args:
            max_concurrent: New maximum concurrent downloads
        """
        with self._lock:
            self.max_concurrent = max_concurrent
            self.thread_pool.setMaxThreadCount(max_concurrent)
            self._process_queue()

    def clear_completed(self) -> None:
        """Clear all completed and failed tasks from history."""
        with self._lock:
            self.completed_tasks.clear()
    
    def get_completed_tasks(self) -> List[DownloadTask]:
        """
        Get all completed/failed tasks.
        
        Returns:
            List of completed DownloadTask instances
        """
        with self._lock:
            return list(self.completed_tasks.values())
