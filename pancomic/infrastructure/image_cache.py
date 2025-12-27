"""Image caching system for PanComic application."""

import hashlib
import os
from pathlib import Path
from typing import Optional, Dict
from collections import OrderedDict
from datetime import datetime
import threading

try:
    from PySide6.QtGui import QPixmap
    from PySide6.QtCore import QByteArray
except ImportError:
    # Fallback for testing without PySide6
    QPixmap = None
    QByteArray = None


class ImageCache:
    """
    Image caching system with LRU eviction.
    
    Implements a singleton pattern to ensure only one cache instance exists.
    Uses LRU (Least Recently Used) eviction when cache size exceeds the limit.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    @classmethod
    def instance(cls) -> 'ImageCache':
        """
        Get singleton instance of ImageCache.
        
        Returns:
            ImageCache singleton instance
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    # Create with default parameters - should be initialized properly later
                    cls._instance = cls.__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, cache_dir: str, max_size_mb: int = 500):
        """
        Initialize ImageCache.
        
        Args:
            cache_dir: Directory to store cached images
            max_size_mb: Maximum cache size in megabytes
            
        Note:
            Due to singleton pattern, __init__ may be called multiple times.
            Use _initialized flag to prevent re-initialization.
        """
        # Prevent re-initialization of singleton
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self.cache_dir = Path(cache_dir)
        self.max_size_mb = max_size_mb
        self.max_size_bytes = max_size_mb * 1024 * 1024
        
        # LRU cache: OrderedDict maintains insertion order
        # Key: URL, Value: (file_path, size_bytes, access_time)
        self.cache_index: OrderedDict[str, tuple[str, int, datetime]] = OrderedDict()
        
        # Current cache size in bytes
        self.current_size_bytes = 0
        
        # Thread lock for cache operations
        self._cache_lock = threading.Lock()
        
        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Load existing cache index
        self._load_cache_index()
        
        self._initialized = True
    
    def _url_to_filename(self, url: str) -> str:
        """
        Convert URL to a safe filename using hash.
        
        Args:
            url: Image URL
            
        Returns:
            Hashed filename
        """
        # Use SHA256 hash of URL as filename
        url_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()
        return f"{url_hash}.cache"
    
    def _load_cache_index(self) -> None:
        """Load existing cache files into the index."""
        if not self.cache_dir.exists():
            return
        
        for cache_file in self.cache_dir.glob('*.cache'):
            try:
                file_size = cache_file.stat().st_size
                access_time = datetime.fromtimestamp(cache_file.stat().st_atime)
                
                # We don't have the original URL, so we'll rebuild index on first access
                # For now, just track the size
                self.current_size_bytes += file_size
            except Exception:
                # Skip corrupted files
                continue
    
    def get_image(self, url: str) -> Optional[QPixmap]:
        """
        Get cached image by URL.
        
        Args:
            url: Image URL
            
        Returns:
            QPixmap if found in cache, None otherwise
        """
        if not url:
            return None
        
        with self._cache_lock:
            # Check if URL is in cache index
            if url not in self.cache_index:
                return None
            
            file_path, size, _ = self.cache_index[url]
            cache_file = Path(file_path)
            
            # Check if file exists
            if not cache_file.exists():
                # Remove from index if file is missing
                del self.cache_index[url]
                self.current_size_bytes -= size
                return None
            
            try:
                # Load image from cache
                if QPixmap is None:
                    # Testing mode without PySide6
                    return None
                
                pixmap = QPixmap(str(cache_file))
                
                if pixmap.isNull():
                    # Image is corrupted, remove from cache
                    cache_file.unlink()
                    del self.cache_index[url]
                    self.current_size_bytes -= size
                    return None
                
                # Update access time (move to end for LRU)
                self.cache_index.move_to_end(url)
                self.cache_index[url] = (file_path, size, datetime.now())
                
                # Update file access time
                cache_file.touch()
                
                return pixmap
                
            except Exception:
                # Failed to load image, remove from cache
                try:
                    cache_file.unlink()
                except Exception:
                    pass
                del self.cache_index[url]
                self.current_size_bytes -= size
                return None
    
    def cache_image(self, url: str, pixmap: QPixmap) -> None:
        """
        Cache an image.
        
        Args:
            url: Image URL (used as cache key)
            pixmap: QPixmap to cache
        """
        if not url or pixmap is None:
            return
        
        if QPixmap is None:
            # Testing mode without PySide6
            return
        
        if pixmap.isNull():
            return
        
        with self._cache_lock:
            filename = self._url_to_filename(url)
            file_path = self.cache_dir / filename
            
            # Save image to disk
            try:
                pixmap.save(str(file_path), 'PNG')
                file_size = file_path.stat().st_size
                
                # If URL already in cache, remove old entry
                if url in self.cache_index:
                    old_path, old_size, _ = self.cache_index[url]
                    self.current_size_bytes -= old_size
                    try:
                        Path(old_path).unlink()
                    except Exception:
                        pass
                
                # Add to cache index
                self.cache_index[url] = (str(file_path), file_size, datetime.now())
                self.current_size_bytes += file_size
                
                # Check if we need to evict old entries
                self._evict_if_needed()
                
            except Exception:
                # Failed to save image
                pass
    
    def _evict_if_needed(self) -> None:
        """
        Evict least recently used images if cache exceeds size limit.
        
        This method should be called while holding _cache_lock.
        """
        while self.current_size_bytes > self.max_size_bytes and self.cache_index:
            # Remove oldest (least recently used) entry
            url, (file_path, size, _) = self.cache_index.popitem(last=False)
            
            # Delete file
            try:
                Path(file_path).unlink()
            except Exception:
                pass
            
            self.current_size_bytes -= size
    
    def clear(self) -> None:
        """Clear all cached images."""
        with self._cache_lock:
            # Delete all cache files
            for url, (file_path, _, _) in self.cache_index.items():
                try:
                    Path(file_path).unlink()
                except Exception:
                    pass
            
            # Clear index
            self.cache_index.clear()
            self.current_size_bytes = 0
    
    def get_cache_size_mb(self) -> float:
        """
        Get current cache size in megabytes.
        
        Returns:
            Cache size in MB
        """
        with self._cache_lock:
            return self.current_size_bytes / (1024 * 1024)
    
    def get_cache_count(self) -> int:
        """
        Get number of cached images.
        
        Returns:
            Number of images in cache
        """
        with self._cache_lock:
            return len(self.cache_index)
    
    def contains(self, url: str) -> bool:
        """
        Check if URL is in cache.
        
        Args:
            url: Image URL
            
        Returns:
            True if URL is cached, False otherwise
        """
        with self._cache_lock:
            if url not in self.cache_index:
                return False
            
            file_path, _, _ = self.cache_index[url]
            return Path(file_path).exists()
    
    def remove(self, url: str) -> None:
        """
        Remove specific image from cache.
        
        Args:
            url: Image URL to remove
        """
        with self._cache_lock:
            if url in self.cache_index:
                file_path, size, _ = self.cache_index[url]
                
                # Delete file
                try:
                    Path(file_path).unlink()
                except Exception:
                    pass
                
                # Remove from index
                del self.cache_index[url]
                self.current_size_bytes -= size
    
    def set_max_size(self, max_size_mb: int) -> None:
        """
        Set maximum cache size and evict if necessary.
        
        Args:
            max_size_mb: New maximum cache size in megabytes
        """
        with self._cache_lock:
            self.max_size_mb = max_size_mb
            self.max_size_bytes = max_size_mb * 1024 * 1024
            self._evict_if_needed()
