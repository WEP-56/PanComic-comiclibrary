"""Episode data model for anime episodes."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Episode:
    """
    Data class representing an anime episode.
    
    Attributes:
        index: Episode index (1-based)
        name: Episode name/title
        url: Episode URL
        line: Line/Route number (for DM569)
        ep: Episode number (for DM569)
        anime_id: Parent anime ID
        duration: Episode duration in minutes
        air_date: Air date string
        description: Episode description
        is_downloaded: Whether episode is downloaded locally
        download_path: Local download path
        stream_url: Direct stream URL (for DM569)
        m3u8_content: M3U8 playlist content (for DM569)
    """
    index: int
    name: str
    url: str = ""
    line: int = 0
    ep: int = 0
    anime_id: str = ""
    duration: int = 0
    air_date: str = ""
    description: str = ""
    is_downloaded: bool = False
    download_path: str = ""
    stream_url: str = ""
    m3u8_content: str = ""
    
    def to_dict(self) -> dict:
        """
        Convert to dictionary for JSON serialization.
        
        Returns:
            Dictionary representation
        """
        return {
            "index": self.index,
            "name": self.name,
            "url": self.url,
            "line": self.line,
            "ep": self.ep,
            "anime_id": self.anime_id,
            "duration": self.duration,
            "air_date": self.air_date,
            "description": self.description,
            "is_downloaded": self.is_downloaded,
            "download_path": self.download_path,
            "stream_url": self.stream_url,
            "m3u8_content": self.m3u8_content,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Episode':
        """
        Create Episode from dictionary.
        
        Args:
            data: Dictionary data
            
        Returns:
            Episode instance
        """
        return cls(
            index=data.get("index", 0),
            name=data.get("name", ""),
            url=data.get("url", ""),
            line=data.get("line", 0),
            ep=data.get("ep", 0),
            anime_id=data.get("anime_id", ""),
            duration=data.get("duration", 0),
            air_date=data.get("air_date", ""),
            description=data.get("description", ""),
            is_downloaded=data.get("is_downloaded", False),
            download_path=data.get("download_path", ""),
            stream_url=data.get("stream_url", ""),
            m3u8_content=data.get("m3u8_content", ""),
        )