"""Anime data model for Bangumi API and DM569."""

from dataclasses import dataclass, field
from typing import List, Optional, Union
from datetime import datetime


@dataclass
class Anime:
    """
    Data class representing an anime from Bangumi or DM569.
    
    Attributes:
        id: Unique identifier (int for Bangumi, str for DM569)
        name: Chinese/localized name
        name_cn: Original name (Japanese/English)
        cover_url: URL to cover image
        summary: Description/summary
        rating: Rating score (0-10)
        rank: Ranking position
        air_date: Air date string (YYYY-MM-DD)
        eps_count: Number of episodes
        tags: List of tags
        type: Type (anime, book, game, music, real)
        bangumi_url: URL to Bangumi page
        added_time: Time when added to history
        source: Data source ('bangumi' or 'dm569')
        url: Source URL (for DM569)
        area: Region/Area (for DM569)
        year: Year (for DM569)
        status: Status (for DM569)
        alias: Alternative names (for DM569)
    """
    id: Union[int, str]
    name: str
    name_cn: str = ""
    cover_url: str = ""
    summary: str = ""
    rating: float = 0.0
    rank: int = 0
    air_date: str = ""
    eps_count: int = 0
    tags: List[str] = field(default_factory=list)
    type: str = "anime"
    bangumi_url: str = ""
    added_time: Optional[datetime] = None
    source: str = "bangumi"  # 'bangumi' or 'dm569'
    url: str = ""  # DM569 source URL
    area: str = ""  # DM569 area
    year: str = ""  # DM569 year
    status: str = ""  # DM569 status
    alias: str = ""  # DM569 alternative names
    
    def __post_init__(self):
        """Generate bangumi_url if not provided."""
        if not self.bangumi_url and self.source == "bangumi" and self.id:
            self.bangumi_url = f"https://bangumi.tv/subject/{self.id}"
    
    @property
    def title(self) -> str:
        """Get display title (name or name_cn)."""
        return self.name or self.name_cn
    
    @property
    def description(self) -> str:
        """Get description (summary for compatibility)."""
        return self.summary
    
    @classmethod
    def from_api_response(cls, data: dict) -> 'Anime':
        """
        Create Anime from Bangumi API response.
        
        Args:
            data: API response dictionary
            
        Returns:
            Anime instance
        """
        # Extract images
        images = data.get("images", {})
        cover_url = images.get("large") or images.get("medium") or images.get("small") or ""
        
        # Extract rating
        rating_data = data.get("rating", {})
        rating = rating_data.get("score", 0.0) if rating_data else 0.0
        rank = rating_data.get("rank", 0) if rating_data else 0
        
        # Extract tags
        tags = [tag.get("name", "") for tag in data.get("tags", []) if tag.get("name")]
        
        # Map type number to string
        type_map = {1: "book", 2: "anime", 3: "music", 4: "game", 6: "real"}
        type_num = data.get("type", 2)
        type_str = type_map.get(type_num, "anime")
        
        return cls(
            id=data.get("id", 0),
            name=data.get("name", ""),
            name_cn=data.get("name_cn", ""),
            cover_url=cover_url,
            summary=data.get("summary", ""),
            rating=rating,
            rank=rank,
            air_date=data.get("date", "") or data.get("air_date", ""),
            eps_count=data.get("eps_count", 0) or data.get("eps", 0),
            tags=tags,
            type=type_str,
            source="bangumi"
        )
    
    @classmethod
    def from_dm569_detail(cls, detail_data: dict) -> 'Anime':
        """
        Create Anime from DM569 detail response.
        
        Args:
            detail_data: DM569 detail dictionary
            
        Returns:
            Anime instance
        """
        return cls(
            id=detail_data.get("id", ""),
            name=detail_data.get("title", ""),
            name_cn=detail_data.get("title", ""),
            cover_url=detail_data.get("cover", ""),
            summary=detail_data.get("intro", ""),
            rating=0.0,  # DM569 doesn't provide rating
            rank=0,
            air_date=detail_data.get("updated", ""),
            eps_count=0,  # Will be set from episodes data
            tags=detail_data.get("tags", []),
            type="anime",
            source="dm569",
            area=detail_data.get("area", ""),
            year=detail_data.get("year", ""),
            status="completed",  # Assume completed for DM569
            alias=detail_data.get("alias", "")
        )
    
    def to_dict(self) -> dict:
        """
        Convert to dictionary for JSON serialization.
        
        Returns:
            Dictionary representation
        """
        return {
            "id": self.id,
            "name": self.name,
            "name_cn": self.name_cn,
            "cover_url": self.cover_url,
            "summary": self.summary,
            "rating": self.rating,
            "rank": self.rank,
            "air_date": self.air_date,
            "eps_count": self.eps_count,
            "tags": self.tags,
            "type": self.type,
            "bangumi_url": self.bangumi_url,
            "added_time": self.added_time.isoformat() if self.added_time else None,
            "source": self.source,
            "url": self.url,
            "area": self.area,
            "year": self.year,
            "status": self.status,
            "alias": self.alias,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Anime':
        """
        Create Anime from dictionary.
        
        Args:
            data: Dictionary data
            
        Returns:
            Anime instance
        """
        added_time = None
        if data.get("added_time"):
            try:
                added_time = datetime.fromisoformat(data["added_time"])
            except (ValueError, TypeError):
                pass
        
        return cls(
            id=data.get("id", 0),
            name=data.get("name", ""),
            name_cn=data.get("name_cn", ""),
            cover_url=data.get("cover_url", ""),
            summary=data.get("summary", ""),
            rating=data.get("rating", 0.0),
            rank=data.get("rank", 0),
            air_date=data.get("air_date", ""),
            eps_count=data.get("eps_count", 0),
            tags=data.get("tags", []),
            type=data.get("type", "anime"),
            bangumi_url=data.get("bangumi_url", ""),
            added_time=added_time,
            source=data.get("source", "bangumi"),
            url=data.get("url", ""),
            area=data.get("area", ""),
            year=data.get("year", ""),
            status=data.get("status", ""),
            alias=data.get("alias", ""),
        )
