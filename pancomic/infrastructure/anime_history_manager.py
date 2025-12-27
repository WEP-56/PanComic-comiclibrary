"""Anime history manager for storing saved anime."""

import json
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from pancomic.models.anime import Anime


class AnimeHistoryManager:
    """
    Manager for anime history storage.
    
    Stores anime history in project_root/downloads/anime_history.json.
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize AnimeHistoryManager.
        
        Args:
            storage_path: Path to the JSON storage file. If None, uses default.
        """
        if storage_path is None:
            # Default to project_root/downloads/anime_history.json
            from pathlib import Path
            project_root = Path(__file__).parent.parent.parent  # Go up to project root
            storage_path = str(project_root / "downloads" / "anime_history.json")
        
        self.storage_path = Path(storage_path)
        self._history: List[Anime] = []
        self._load()
    
    def _load(self) -> None:
        """Load history from file."""
        if not self.storage_path.exists():
            self._history = []
            return
        
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self._history = [Anime.from_dict(item) for item in data]
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            print(f"Error loading anime history: {e}")
            self._history = []
    
    def _save(self) -> None:
        """Save history to file."""
        # Ensure directory exists
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            data = [anime.to_dict() for anime in self._history]
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving anime history: {e}")
    
    def add(self, anime: Anime) -> bool:
        """
        Add anime to history.
        
        Args:
            anime: Anime to add
            
        Returns:
            True if added, False if already exists
        """
        # Check if already exists
        if any(a.id == anime.id for a in self._history):
            return False
        
        # Set added time
        anime.added_time = datetime.now()
        
        # Add to beginning of list
        self._history.insert(0, anime)
        self._save()
        return True
    
    def remove(self, anime_id: int) -> bool:
        """
        Remove anime from history.
        
        Args:
            anime_id: ID of anime to remove
            
        Returns:
            True if removed, False if not found
        """
        for i, anime in enumerate(self._history):
            if anime.id == anime_id:
                del self._history[i]
                self._save()
                return True
        return False
    
    def get_all(self) -> List[Anime]:
        """
        Get all anime in history.
        
        Returns:
            List of Anime objects (newest first)
        """
        return self._history.copy()
    
    def reload(self) -> None:
        """Reload history from file (useful when another instance modified the file)."""
        self._load()
    
    def get_by_id(self, anime_id: int) -> Optional[Anime]:
        """
        Get anime by ID.
        
        Args:
            anime_id: Anime ID
            
        Returns:
            Anime object or None
        """
        for anime in self._history:
            if anime.id == anime_id:
                return anime
        return None
    
    def exists(self, anime_id: int) -> bool:
        """
        Check if anime exists in history.
        
        Args:
            anime_id: Anime ID
            
        Returns:
            True if exists
        """
        return any(a.id == anime_id for a in self._history)
    
    def count(self) -> int:
        """Get number of anime in history."""
        return len(self._history)
    
    def clear(self) -> None:
        """Clear all history."""
        self._history.clear()
        self._save()
