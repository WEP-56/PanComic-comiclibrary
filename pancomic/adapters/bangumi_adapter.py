"""Bangumi API adapter for anime search."""

import requests
from typing import List, Optional, Dict, Any
from pancomic.models.anime import Anime


class BangumiAdapter:
    """
    Adapter for Bangumi API.
    
    Provides search functionality for anime, books, games, music, and real content.
    """
    
    BASE_URL = "https://api.bgm.tv/v0"
    
    # Type mapping: display name -> API type number
    TYPE_MAP = {
        "动画": 2,
        "书籍": 1,
        "游戏": 4,
        "音乐": 3,
        "真实": 6,
    }
    
    def __init__(self):
        """Initialize BangumiAdapter."""
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "PanComic/1.0 (https://github.com/pancomic)",
            "Accept": "application/json",
        })
        # Disable SSL verification for network issues
        self._session.verify = False
        
        # Suppress SSL warnings
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    def search(
        self,
        keyword: str,
        page: int = 1,
        per_page: int = 6,
        type_filter: str = "动画",
        sort: str = "rank",
        year: Optional[int] = None,
        tags: Optional[List[str]] = None,
        exclude_tags: Optional[List[str]] = None,
    ) -> tuple[List[Anime], int]:
        """
        Search for anime/subjects on Bangumi.
        
        Args:
            keyword: Search keyword
            page: Page number (1-indexed)
            per_page: Results per page (default 6)
            type_filter: Type filter (动画/书籍/游戏/音乐/真实)
            sort: Sort order ("rank" for rating desc, "rank_asc" for rating asc)
            year: Filter by year
            tags: List of tags to include
            exclude_tags: List of tags to exclude
            
        Returns:
            Tuple of (list of Anime objects, total count)
        """
        url = f"{self.BASE_URL}/search/subjects"
        
        # Build request body
        body: Dict[str, Any] = {
            "keyword": keyword,
            "filter": {
                "type": [self.TYPE_MAP.get(type_filter, 2)],
            },
        }
        
        # Add year filter
        if year:
            body["filter"]["air_date"] = [f">={year}-01-01", f"<={year}-12-31"]
        
        # Add tag filters
        if tags:
            body["filter"]["tag"] = tags
        
        # Add sort
        if sort == "rank":
            body["sort"] = "rank"
        elif sort == "rank_asc":
            body["sort"] = "rank"
            # Note: Bangumi API doesn't support ascending rank directly
        
        # Pagination
        params = {
            "limit": per_page,
            "offset": (page - 1) * per_page,
        }
        
        try:
            response = self._session.post(url, json=body, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            # Parse results
            results = []
            for item in data.get("data", []):
                anime = Anime.from_api_response(item)
                
                # Apply client-side tag exclusion
                if exclude_tags:
                    anime_tags_lower = [t.lower() for t in anime.tags]
                    if any(et.lower() in anime_tags_lower for et in exclude_tags):
                        continue
                
                results.append(anime)
            
            total = data.get("total", len(results))
            return results, total
            
        except requests.RequestException as e:
            print(f"Bangumi search error: {e}")
            return [], 0
    
    def get_detail(self, subject_id: int) -> Optional[Anime]:
        """
        Get detailed information for a subject.
        
        Args:
            subject_id: Bangumi subject ID
            
        Returns:
            Anime object or None if not found
        """
        url = f"{self.BASE_URL}/subjects/{subject_id}"
        
        try:
            response = self._session.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            return Anime.from_api_response(data)
            
        except requests.RequestException as e:
            print(f"Bangumi get_detail error: {e}")
            return None
    
    def get_available_years(self) -> List[int]:
        """
        Get list of available years for filtering.
        
        Returns:
            List of years from 1990 to current year
        """
        from datetime import datetime
        current_year = datetime.now().year
        return list(range(current_year, 1989, -1))
