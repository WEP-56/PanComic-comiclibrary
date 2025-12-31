"""Anime history manager for storing saved anime and local videos."""

import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from pancomic.models.anime import Anime


class AnimeHistoryManager:
    """
    Manager for anime history storage.
    
    Stores anime history in project_root/downloads/anime_history.json.
    Supports both Bangumi links and local downloaded videos.
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
        self.downloads_path = self.storage_path.parent / "anime"
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
        # Check if already exists (by ID and source)
        if any(str(a.id) == str(anime.id) and a.source == anime.source for a in self._history):
            return False
        
        # Set added time
        anime.added_time = datetime.now()
        
        # Add to beginning of list
        self._history.insert(0, anime)
        self._save()
        return True
    
    def remove(self, anime_id: str, source: str = None) -> bool:
        """
        Remove anime from history.
        
        Args:
            anime_id: ID of anime to remove
            source: Source of anime (optional, for better matching)
            
        Returns:
            True if removed, False if not found
        """
        for i, anime in enumerate(self._history):
            if str(anime.id) == str(anime_id):
                if source is None or anime.source == source:
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
    
    def get_local_videos(self) -> List[Dict[str, Any]]:
        """
        Get all local downloaded videos.
        
        Returns:
            List of local video information with metadata
        """
        local_videos = []
        
        if not self.downloads_path.exists():
            return local_videos
        
        # 扫描下载目录中的元数据文件
        for metadata_file in self.downloads_path.rglob("*.metadata.json"):
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                episode_data = metadata.get("episode", {})
                if episode_data.get("is_downloaded"):
                    anime_data = metadata.get("anime", {})
                    
                    # 创建本地视频信息
                    local_video = {
                        "anime": anime_data,
                        "episode": episode_data,
                        "metadata_file": str(metadata_file),
                        "is_local": True,
                        "download_path": episode_data.get("download_path", ""),
                        "download_time": episode_data.get("download_time", ""),
                        "completed_time": episode_data.get("completed_time", "")
                    }
                    local_videos.append(local_video)
                    
            except Exception as e:
                print(f"Error reading metadata file {metadata_file}: {e}")
        
        # 按下载时间排序（最新的在前）
        local_videos.sort(
            key=lambda x: x["episode"].get("completed_time", ""),
            reverse=True
        )
        
        return local_videos
    
    def get_anime_with_local_episodes(self) -> List[Dict[str, Any]]:
        """
        Get anime that have local downloaded episodes.
        
        Returns:
            List of anime with their local episodes
        """
        local_videos = self.get_local_videos()
        anime_episodes = {}
        
        # 按动漫分组
        for video in local_videos:
            anime_data = video["anime"]
            anime_id = str(anime_data.get("id", ""))
            
            if anime_id not in anime_episodes:
                anime_episodes[anime_id] = {
                    "anime": anime_data,
                    "episodes": [],
                    "is_local": True
                }
            
            anime_episodes[anime_id]["episodes"].append(video["episode"])
        
        # 转换为列表并按最新下载时间排序
        result = list(anime_episodes.values())
        result.sort(
            key=lambda x: max(
                ep.get("completed_time", "") for ep in x["episodes"]
            ) if x["episodes"] else "",
            reverse=True
        )
        
        return result
    
    def has_local_episodes(self, anime_id: str) -> bool:
        """
        Check if anime has local downloaded episodes.
        
        Args:
            anime_id: Anime ID
            
        Returns:
            True if has local episodes
        """
        local_videos = self.get_local_videos()
        return any(
            str(video["anime"].get("id", "")) == str(anime_id)
            for video in local_videos
        )
    
    def get_local_episodes_for_anime(self, anime_id: str) -> List[Dict[str, Any]]:
        """
        Get local episodes for specific anime.
        
        Args:
            anime_id: Anime ID
            
        Returns:
            List of local episodes for the anime
        """
        local_videos = self.get_local_videos()
        return [
            video for video in local_videos
            if str(video["anime"].get("id", "")) == str(anime_id)
        ]
    
    def reload(self) -> None:
        """Reload history from file (useful when another instance modified the file)."""
        self._load()
    
    def get_by_id(self, anime_id: str, source: str = None) -> Optional[Anime]:
        """
        Get anime by ID.
        
        Args:
            anime_id: Anime ID
            source: Source (optional, for better matching)
            
        Returns:
            Anime object or None
        """
        for anime in self._history:
            if str(anime.id) == str(anime_id):
                if source is None or anime.source == source:
                    return anime
        return None
    
    def exists(self, anime_id: str, source: str = None) -> bool:
        """
        Check if anime exists in history.
        
        Args:
            anime_id: Anime ID
            source: Source (optional, for better matching)
            
        Returns:
            True if exists
        """
        return any(
            str(a.id) == str(anime_id) and (source is None or a.source == source)
            for a in self._history
        )
    
    def count(self) -> int:
        """Get number of anime in history."""
        return len(self._history)
    
    def clear(self) -> None:
        """Clear all history."""
        self._history.clear()
        self._save()
    
    def cleanup_orphaned_metadata(self) -> int:
        """
        Clean up metadata files for videos that no longer exist.
        
        Returns:
            Number of orphaned metadata files removed
        """
        removed_count = 0
        
        if not self.downloads_path.exists():
            return removed_count
        
        for metadata_file in self.downloads_path.rglob("*.metadata.json"):
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                episode_data = metadata.get("episode", {})
                download_path = episode_data.get("download_path", "")
                
                # 检查视频文件是否存在
                if download_path and not Path(download_path).exists():
                    metadata_file.unlink()  # 删除元数据文件
                    removed_count += 1
                    print(f"Removed orphaned metadata: {metadata_file}")
                    
            except Exception as e:
                print(f"Error checking metadata file {metadata_file}: {e}")
        
        return removed_count
