"""Download queue manager for persistent queue storage."""

import json
import os
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path


@dataclass
class QueueItem:
    """Represents a queued download item."""
    id: str
    comic_id: str
    comic_title: str
    comic_author: str
    comic_cover_url: str
    source: str  # 'jmcomic' or 'picacg'
    chapter_count: int
    chapters_data: List[Dict]  # Serialized chapter data
    added_at: str
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'QueueItem':
        return cls(**data)


class DownloadQueueManager:
    """Manages persistent download queue storage."""
    
    _instance = None
    
    def __new__(cls, download_path: str = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, download_path: str = None):
        if self._initialized:
            return
        
        self._download_path = download_path or "E:/PanComic/downloads"
        self._queue_file = Path(self._download_path) / "download_queue.json"
        self._queue: List[QueueItem] = []
        self._load_queue()
        self._initialized = True
    
    def _load_queue(self) -> None:
        """Load queue from file."""
        try:
            if self._queue_file.exists():
                with open(self._queue_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._queue = [QueueItem.from_dict(item) for item in data]
        except Exception as e:
            print(f"Error loading download queue: {e}")
            self._queue = []
    
    def _save_queue(self) -> None:
        """Save queue to file."""
        try:
            self._queue_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._queue_file, 'w', encoding='utf-8') as f:
                json.dump([item.to_dict() for item in self._queue], f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving download queue: {e}")
    
    def add_to_queue(self, comic, chapters: List, source: str) -> str:
        """Add a comic to the download queue."""
        import uuid
        
        item_id = str(uuid.uuid4())[:8]
        
        # Serialize chapters
        chapters_data = []
        for ch in chapters:
            chapters_data.append({
                'id': ch.id,
                'title': ch.title,
                'chapter_number': ch.chapter_number,
                'page_count': getattr(ch, 'page_count', 0)
            })
        
        item = QueueItem(
            id=item_id,
            comic_id=comic.id,
            comic_title=comic.title,
            comic_author=comic.author,
            comic_cover_url=comic.cover_url or '',
            source=source,
            chapter_count=len(chapters),
            chapters_data=chapters_data,
            added_at=datetime.now().isoformat()
        )
        
        # Check if already in queue
        for existing in self._queue:
            if existing.comic_id == comic.id and existing.source == source:
                return existing.id  # Already in queue
        
        self._queue.append(item)
        self._save_queue()
        return item_id
    
    def remove_from_queue(self, item_id: str) -> bool:
        """Remove an item from the queue."""
        for i, item in enumerate(self._queue):
            if item.id == item_id:
                self._queue.pop(i)
                self._save_queue()
                return True
        return False
    
    def get_all_items(self) -> List[QueueItem]:
        """Get all items in the queue."""
        return self._queue.copy()
    
    def get_item(self, item_id: str) -> Optional[QueueItem]:
        """Get a specific item by ID."""
        for item in self._queue:
            if item.id == item_id:
                return item
        return None
    
    def clear_queue(self) -> None:
        """Clear all items from the queue."""
        self._queue.clear()
        self._save_queue()
    
    def remove_items(self, item_ids: List[str]) -> int:
        """Remove multiple items from the queue."""
        removed = 0
        self._queue = [item for item in self._queue if item.id not in item_ids or not (removed := removed + 1)]
        # Fix the count
        original_len = len(self._queue) + len(item_ids)
        new_queue = [item for item in self._queue if item.id not in item_ids]
        removed = len(self._queue) - len(new_queue)
        self._queue = new_queue
        self._save_queue()
        return removed
    
    def reload(self) -> None:
        """Reload queue from file."""
        self._load_queue()
