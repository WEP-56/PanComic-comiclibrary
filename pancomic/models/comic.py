"""Comic data model."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class Comic:
    """Comic metadata model.
    
    Unified comic data model across all sources (JMComic, PicACG).
    """
    
    id: str
    title: str
    author: str
    cover_url: str
    description: Optional[str]
    tags: List[str]
    categories: List[str]
    status: str  # "ongoing" or "completed"
    chapter_count: int
    view_count: int
    like_count: int
    is_favorite: bool
    source: str  # "jmcomic", "picacg", or "user"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Validate and normalize fields after initialization."""
        # Normalize and validate required string fields
        if not self.id or not isinstance(self.id, str):
            raise ValueError("Comic id must be a non-empty string")
        
        # Allow empty title but provide fallback
        if not isinstance(self.title, str):
            raise ValueError("Comic title must be a string")
        if not self.title.strip():
            object.__setattr__(self, 'title', '未知标题')
        
        # Allow empty author but provide fallback
        if not isinstance(self.author, str):
            raise ValueError("Comic author must be a string")
        if not self.author.strip():
            object.__setattr__(self, 'author', '未知作者')
        
        # Allow placeholder cover_url
        if not isinstance(self.cover_url, str):
            raise ValueError("Comic cover_url must be a string")
        if not self.cover_url.strip():
            object.__setattr__(self, 'cover_url', 'placeholder://no-cover')
        
        # Validate description
        if self.description is not None and not isinstance(self.description, str):
            raise ValueError("Comic description must be a string or None")
        
        # Validate source
        valid_sources = ["jmcomic", "picacg", "wnacg", "user"]
        if self.source not in valid_sources:
            raise ValueError(f"Comic source must be one of {valid_sources}, got '{self.source}'")
        
        # Validate status
        valid_statuses = ["ongoing", "completed"]
        if self.status not in valid_statuses:
            raise ValueError(f"Comic status must be one of {valid_statuses}, got '{self.status}'")
        
        # Validate lists
        if not isinstance(self.tags, list):
            raise ValueError("Comic tags must be a list")
        if not isinstance(self.categories, list):
            raise ValueError("Comic categories must be a list")
        
        # Validate numeric fields
        if not isinstance(self.chapter_count, int) or self.chapter_count < 0:
            raise ValueError("Comic chapter_count must be a non-negative integer")
        if not isinstance(self.view_count, int) or self.view_count < 0:
            raise ValueError("Comic view_count must be a non-negative integer")
        if not isinstance(self.like_count, int) or self.like_count < 0:
            raise ValueError("Comic like_count must be a non-negative integer")
        
        # Validate boolean
        if not isinstance(self.is_favorite, bool):
            raise ValueError("Comic is_favorite must be a boolean")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert Comic to dictionary for serialization.
        
        Returns:
            Dictionary representation of the Comic with all fields.
        """
        return {
            'id': self.id,
            'title': self.title,
            'author': self.author,
            'cover_url': self.cover_url,
            'description': self.description,
            'tags': self.tags.copy(),  # Copy to avoid external mutation
            'categories': self.categories.copy(),
            'status': self.status,
            'chapter_count': self.chapter_count,
            'view_count': self.view_count,
            'like_count': self.like_count,
            'is_favorite': self.is_favorite,
            'source': self.source,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Comic':
        """Create Comic from dictionary.
        
        Args:
            data: Dictionary containing comic data.
            
        Returns:
            Comic instance created from the dictionary.
            
        Raises:
            ValueError: If required fields are missing or invalid.
        """
        # Parse datetime fields if present
        created_at = None
        if data.get('created_at'):
            if isinstance(data['created_at'], str):
                created_at = datetime.fromisoformat(data['created_at'])
            elif isinstance(data['created_at'], datetime):
                created_at = data['created_at']
        
        updated_at = None
        if data.get('updated_at'):
            if isinstance(data['updated_at'], str):
                updated_at = datetime.fromisoformat(data['updated_at'])
            elif isinstance(data['updated_at'], datetime):
                updated_at = data['updated_at']
        
        return cls(
            id=data['id'],
            title=data['title'],
            author=data['author'],
            cover_url=data['cover_url'],
            description=data['description'],
            tags=data.get('tags', []),
            categories=data.get('categories', []),
            status=data['status'],
            chapter_count=data['chapter_count'],
            view_count=data['view_count'],
            like_count=data['like_count'],
            is_favorite=data['is_favorite'],
            source=data['source'],
            created_at=created_at,
            updated_at=updated_at,
        )
