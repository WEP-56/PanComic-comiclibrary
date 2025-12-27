"""Chapter data model."""

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class Chapter:
    """Chapter metadata model.
    
    Represents a single episode or volume of a comic.
    """
    
    id: str
    comic_id: str
    title: str
    chapter_number: int
    page_count: int
    is_downloaded: bool
    download_path: Optional[str]
    source: str  # "jmcomic", "picacg", or "user"
    
    def __post_init__(self):
        """Validate required fields after initialization."""
        # Validate required string fields are not empty
        if not self.id or not isinstance(self.id, str):
            raise ValueError("Chapter id must be a non-empty string")
        if not self.comic_id or not isinstance(self.comic_id, str):
            raise ValueError("Chapter comic_id must be a non-empty string")
        if not self.title or not isinstance(self.title, str):
            raise ValueError("Chapter title must be a non-empty string")
        
        # Validate source
        valid_sources = ["jmcomic", "picacg", "user"]
        if self.source not in valid_sources:
            raise ValueError(f"Chapter source must be one of {valid_sources}, got '{self.source}'")
        
        # Validate chapter_number (must be non-negative integer, 0 is allowed for some sources)
        if not isinstance(self.chapter_number, int) or self.chapter_number < 0:
            raise ValueError("Chapter chapter_number must be a non-negative integer")
        
        # Validate page_count (must be non-negative integer)
        if not isinstance(self.page_count, int) or self.page_count < 0:
            raise ValueError("Chapter page_count must be a non-negative integer")
        
        # Validate boolean
        if not isinstance(self.is_downloaded, bool):
            raise ValueError("Chapter is_downloaded must be a boolean")
        
        # Validate download_path consistency
        if self.is_downloaded and not self.download_path:
            raise ValueError("Chapter download_path must be set when is_downloaded is True")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert Chapter to dictionary for serialization.
        
        Returns:
            Dictionary representation of the Chapter with all fields.
        """
        return {
            'id': self.id,
            'comic_id': self.comic_id,
            'title': self.title,
            'chapter_number': self.chapter_number,
            'page_count': self.page_count,
            'is_downloaded': self.is_downloaded,
            'download_path': self.download_path,
            'source': self.source,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Chapter':
        """Create Chapter from dictionary.
        
        Args:
            data: Dictionary containing chapter data.
            
        Returns:
            Chapter instance created from the dictionary.
            
        Raises:
            ValueError: If required fields are missing or invalid.
        """
        return cls(
            id=data['id'],
            comic_id=data['comic_id'],
            title=data['title'],
            chapter_number=data['chapter_number'],
            page_count=data['page_count'],
            is_downloaded=data['is_downloaded'],
            download_path=data.get('download_path'),
            source=data['source'],
        )
