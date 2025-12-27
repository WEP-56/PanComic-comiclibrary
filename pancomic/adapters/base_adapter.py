"""Base adapter interface for comic sources."""

from abc import ABCMeta, abstractmethod
from typing import Dict, Any, List, Optional
from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtCore import QMetaObject as QtMetaObject


# Create a compatible metaclass that combines QObject's metaclass and ABCMeta
class AdapterMeta(type(QObject), ABCMeta):
    """Metaclass that combines QObject and ABC metaclasses."""
    pass


class BaseSourceAdapter(QObject, metaclass=AdapterMeta):
    """
    Abstract base class for comic source adapters.
    
    Each adapter wraps an original comic source project and provides
    a unified interface while maintaining thread isolation.
    """
    
    # Signals for async operations
    search_completed = Signal(list)  # List[Comic]
    search_failed = Signal(str)  # error_message
    
    comic_detail_completed = Signal(object)  # Comic
    comic_detail_failed = Signal(str)  # error_message
    
    chapters_completed = Signal(list)  # List[Chapter]
    chapters_failed = Signal(str)  # error_message
    
    images_completed = Signal(list)  # List[str] (image URLs)
    images_failed = Signal(str)  # error_message
    
    login_completed = Signal(bool, str)  # success, message
    login_failed = Signal(str)  # error_message
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the adapter.
        
        Args:
            config: Source-specific configuration dictionary
        """
        super().__init__()
        self.config = config
        self.worker_thread: Optional[QThread] = None
        self.original_module: Any = None
        self._is_initialized = False
        
    @abstractmethod
    def initialize(self) -> None:
        """
        Initialize the original project module.
        
        This method should:
        - Import and setup the original project modules
        - Configure domain, proxy, and other settings
        - Prepare the adapter for operations
        """
        pass
    
    @abstractmethod
    def search(self, keyword: str, page: int = 1) -> None:
        """
        Search comics with the given keyword.
        
        This method queues the search operation to the worker thread
        and returns immediately. Results are emitted via search_completed signal.
        
        Args:
            keyword: Search keyword
            page: Page number (default: 1)
        """
        pass
    
    @abstractmethod
    def get_comic_detail(self, comic_id: str) -> None:
        """
        Get detailed information about a comic.
        
        This method queues the operation to the worker thread
        and returns immediately. Results are emitted via comic_detail_completed signal.
        
        Args:
            comic_id: Unique identifier for the comic
        """
        pass
    
    @abstractmethod
    def get_chapters(self, comic_id: str) -> None:
        """
        Get the list of chapters for a comic.
        
        This method queues the operation to the worker thread
        and returns immediately. Results are emitted via chapters_completed signal.
        
        Args:
            comic_id: Unique identifier for the comic
        """
        pass
    
    @abstractmethod
    def get_chapter_images(self, comic_id: str, chapter_id: str) -> None:
        """
        Get the list of image URLs for a chapter.
        
        This method queues the operation to the worker thread
        and returns immediately. Results are emitted via images_completed signal.
        
        Args:
            comic_id: Unique identifier for the comic
            chapter_id: Unique identifier for the chapter
        """
        pass
    
    @abstractmethod
    def login(self, credentials: Dict[str, str]) -> None:
        """
        Authenticate with the comic source.
        
        This method queues the authentication operation to the worker thread
        and returns immediately. Results are emitted via login_completed signal.
        
        Args:
            credentials: Dictionary containing authentication credentials
                        (e.g., username, password, cookies, etc.)
        """
        pass
    
    def start_worker_thread(self) -> None:
        """
        Start the dedicated worker thread for this source.
        
        This ensures all operations for this source run in isolation
        from other sources and the main UI thread.
        """
        if self.worker_thread is None:
            self.worker_thread = QThread()
            self.moveToThread(self.worker_thread)
            self.worker_thread.start()
    
    def stop_worker_thread(self) -> None:
        """
        Stop the worker thread and clean up resources.
        """
        if self.worker_thread is not None:
            self.worker_thread.quit()
            self.worker_thread.wait()
            self.worker_thread = None
    
    def is_initialized(self) -> bool:
        """
        Check if the adapter has been initialized.
        
        Returns:
            True if initialized, False otherwise
        """
        return self._is_initialized
    
    def get_source_name(self) -> str:
        """
        Get the name of this comic source.
        
        Returns:
            Source name (e.g., "jmcomic", "picacg")
        """
        return self.__class__.__name__.replace("Adapter", "").lower()
