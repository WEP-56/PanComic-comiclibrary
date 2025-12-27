"""Database management for PanComic application."""

import sqlite3
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from pancomic.models.comic import Comic
from pancomic.models.chapter import Chapter


class Database:
    """SQLite database manager for storing comic metadata and download records."""
    
    def __init__(self, db_path: str):
        """
        Initialize Database.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path)
        self.connection: Optional[sqlite3.Connection] = None
        
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Connect to database
        self._connect()
    
    def _connect(self) -> None:
        """Establish connection to the database."""
        self.connection = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False  # Allow multi-threaded access
        )
        self.connection.row_factory = sqlite3.Row  # Enable column access by name
    
    def close(self) -> None:
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def initialize_schema(self) -> None:
        """Create database tables if they don't exist."""
        if not self.connection:
            self._connect()
        
        cursor = self.connection.cursor()
        
        # Comics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS comics (
                id TEXT NOT NULL,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                cover_url TEXT NOT NULL,
                description TEXT NOT NULL,
                tags TEXT NOT NULL,
                categories TEXT NOT NULL,
                status TEXT NOT NULL,
                chapter_count INTEGER NOT NULL,
                view_count INTEGER NOT NULL,
                like_count INTEGER NOT NULL,
                is_favorite INTEGER NOT NULL,
                created_at TEXT,
                updated_at TEXT,
                PRIMARY KEY (id, source)
            )
        ''')
        
        # Chapters table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chapters (
                id TEXT NOT NULL,
                comic_id TEXT NOT NULL,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                chapter_number INTEGER NOT NULL,
                page_count INTEGER NOT NULL,
                is_downloaded INTEGER NOT NULL,
                download_path TEXT,
                PRIMARY KEY (id, source),
                FOREIGN KEY (comic_id, source) REFERENCES comics(id, source)
            )
        ''')
        
        # Download records table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS download_records (
                task_id TEXT PRIMARY KEY,
                comic_id TEXT NOT NULL,
                source TEXT NOT NULL,
                status TEXT NOT NULL,
                progress INTEGER NOT NULL,
                current_chapter INTEGER NOT NULL,
                total_chapters INTEGER NOT NULL,
                error_message TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                FOREIGN KEY (comic_id, source) REFERENCES comics(id, source)
            )
        ''')
        
        # Favorites table (for quick favorite lookups)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS favorites (
                comic_id TEXT NOT NULL,
                source TEXT NOT NULL,
                added_at TEXT NOT NULL,
                PRIMARY KEY (comic_id, source),
                FOREIGN KEY (comic_id, source) REFERENCES comics(id, source)
            )
        ''')
        
        # Create indexes for better query performance
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_comics_source 
            ON comics(source)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_comics_favorite 
            ON comics(is_favorite)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_chapters_comic 
            ON chapters(comic_id, source)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_download_records_status 
            ON download_records(status)
        ''')
        
        self.connection.commit()
    
    def save_comic(self, comic: Comic) -> None:
        """
        Save or update comic metadata.
        
        Args:
            comic: Comic instance to save
        """
        if not self.connection:
            self._connect()
        
        cursor = self.connection.cursor()
        
        # Convert lists to JSON strings
        tags_json = json.dumps(comic.tags)
        categories_json = json.dumps(comic.categories)
        
        # Convert datetime to ISO format strings
        created_at = comic.created_at.isoformat() if comic.created_at else None
        updated_at = comic.updated_at.isoformat() if comic.updated_at else None
        
        cursor.execute('''
            INSERT OR REPLACE INTO comics (
                id, source, title, author, cover_url, description,
                tags, categories, status, chapter_count, view_count,
                like_count, is_favorite, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            comic.id, comic.source, comic.title, comic.author,
            comic.cover_url, comic.description, tags_json, categories_json,
            comic.status, comic.chapter_count, comic.view_count,
            comic.like_count, 1 if comic.is_favorite else 0,
            created_at, updated_at
        ))
        
        # Update favorites table
        if comic.is_favorite:
            cursor.execute('''
                INSERT OR IGNORE INTO favorites (comic_id, source, added_at)
                VALUES (?, ?, ?)
            ''', (comic.id, comic.source, datetime.now().isoformat()))
        else:
            cursor.execute('''
                DELETE FROM favorites WHERE comic_id = ? AND source = ?
            ''', (comic.id, comic.source))
        
        self.connection.commit()
    
    def get_comic(self, comic_id: str, source: str) -> Optional[Comic]:
        """
        Retrieve comic metadata.
        
        Args:
            comic_id: Comic ID
            source: Comic source ('jmcomic', or 'picacg')
            
        Returns:
            Comic instance if found, None otherwise
        """
        if not self.connection:
            self._connect()
        
        cursor = self.connection.cursor()
        cursor.execute('''
            SELECT * FROM comics WHERE id = ? AND source = ?
        ''', (comic_id, source))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        # Parse JSON fields
        tags = json.loads(row['tags'])
        categories = json.loads(row['categories'])
        
        # Parse datetime fields
        created_at = datetime.fromisoformat(row['created_at']) if row['created_at'] else None
        updated_at = datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
        
        return Comic(
            id=row['id'],
            source=row['source'],
            title=row['title'],
            author=row['author'],
            cover_url=row['cover_url'],
            description=row['description'],
            tags=tags,
            categories=categories,
            status=row['status'],
            chapter_count=row['chapter_count'],
            view_count=row['view_count'],
            like_count=row['like_count'],
            is_favorite=bool(row['is_favorite']),
            created_at=created_at,
            updated_at=updated_at
        )
    
    def get_downloaded_comics(self) -> List[Comic]:
        """
        Get all downloaded comics.
        
        Returns:
            List of Comic instances that have been downloaded
        """
        if not self.connection:
            self._connect()
        
        cursor = self.connection.cursor()
        
        # Get comics that have at least one downloaded chapter
        cursor.execute('''
            SELECT DISTINCT c.* FROM comics c
            INNER JOIN chapters ch ON c.id = ch.comic_id AND c.source = ch.source
            WHERE ch.is_downloaded = 1
            ORDER BY c.updated_at DESC
        ''')
        
        comics = []
        for row in cursor.fetchall():
            tags = json.loads(row['tags'])
            categories = json.loads(row['categories'])
            created_at = datetime.fromisoformat(row['created_at']) if row['created_at'] else None
            updated_at = datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
            
            comic = Comic(
                id=row['id'],
                source=row['source'],
                title=row['title'],
                author=row['author'],
                cover_url=row['cover_url'],
                description=row['description'],
                tags=tags,
                categories=categories,
                status=row['status'],
                chapter_count=row['chapter_count'],
                view_count=row['view_count'],
                like_count=row['like_count'],
                is_favorite=bool(row['is_favorite']),
                created_at=created_at,
                updated_at=updated_at
            )
            comics.append(comic)
        
        return comics
    
    def save_chapter(self, chapter: Chapter) -> None:
        """
        Save or update chapter metadata.
        
        Args:
            chapter: Chapter instance to save
        """
        if not self.connection:
            self._connect()
        
        cursor = self.connection.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO chapters (
                id, comic_id, source, title, chapter_number,
                page_count, is_downloaded, download_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            chapter.id, chapter.comic_id, chapter.source, chapter.title,
            chapter.chapter_number, chapter.page_count,
            1 if chapter.is_downloaded else 0, chapter.download_path
        ))
        
        self.connection.commit()
    
    def get_chapters(self, comic_id: str, source: str) -> List[Chapter]:
        """
        Get all chapters for a comic.
        
        Args:
            comic_id: Comic ID
            source: Comic source
            
        Returns:
            List of Chapter instances
        """
        if not self.connection:
            self._connect()
        
        cursor = self.connection.cursor()
        cursor.execute('''
            SELECT * FROM chapters 
            WHERE comic_id = ? AND source = ?
            ORDER BY chapter_number ASC
        ''', (comic_id, source))
        
        chapters = []
        for row in cursor.fetchall():
            chapter = Chapter(
                id=row['id'],
                comic_id=row['comic_id'],
                source=row['source'],
                title=row['title'],
                chapter_number=row['chapter_number'],
                page_count=row['page_count'],
                is_downloaded=bool(row['is_downloaded']),
                download_path=row['download_path']
            )
            chapters.append(chapter)
        
        return chapters
    
    def save_download_record(
        self,
        task_id: str,
        comic_id: str,
        source: str,
        status: str,
        progress: int = 0,
        current_chapter: int = 0,
        total_chapters: int = 0,
        error_message: Optional[str] = None,
        completed_at: Optional[datetime] = None
    ) -> None:
        """
        Save or update download record.
        
        Args:
            task_id: Unique task identifier
            comic_id: Comic ID
            source: Comic source
            status: Download status
            progress: Progress percentage (0-100)
            current_chapter: Current chapter being downloaded
            total_chapters: Total chapters to download
            error_message: Error message if failed
            completed_at: Completion timestamp
        """
        if not self.connection:
            self._connect()
        
        cursor = self.connection.cursor()
        
        # Check if record exists
        cursor.execute('SELECT task_id FROM download_records WHERE task_id = ?', (task_id,))
        exists = cursor.fetchone() is not None
        
        completed_at_str = completed_at.isoformat() if completed_at else None
        
        if exists:
            # Update existing record
            cursor.execute('''
                UPDATE download_records
                SET status = ?, progress = ?, current_chapter = ?,
                    total_chapters = ?, error_message = ?, completed_at = ?
                WHERE task_id = ?
            ''', (
                status, progress, current_chapter, total_chapters,
                error_message, completed_at_str, task_id
            ))
        else:
            # Insert new record
            cursor.execute('''
                INSERT INTO download_records (
                    task_id, comic_id, source, status, progress,
                    current_chapter, total_chapters, error_message,
                    created_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                task_id, comic_id, source, status, progress,
                current_chapter, total_chapters, error_message,
                datetime.now().isoformat(), completed_at_str
            ))
        
        self.connection.commit()
    
    def get_download_record(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get download record by task ID.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Dictionary containing download record data, or None if not found
        """
        if not self.connection:
            self._connect()
        
        cursor = self.connection.cursor()
        cursor.execute('''
            SELECT * FROM download_records WHERE task_id = ?
        ''', (task_id,))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        return dict(row)
    
    def get_active_downloads(self) -> List[Dict[str, Any]]:
        """
        Get all active download records (queued or downloading).
        
        Returns:
            List of dictionaries containing download record data
        """
        if not self.connection:
            self._connect()
        
        cursor = self.connection.cursor()
        cursor.execute('''
            SELECT * FROM download_records 
            WHERE status IN ('queued', 'downloading', 'paused')
            ORDER BY created_at ASC
        ''')
        
        return [dict(row) for row in cursor.fetchall()]
    
    def delete_download_record(self, task_id: str) -> None:
        """
        Delete a download record.
        
        Args:
            task_id: Task identifier
        """
        if not self.connection:
            self._connect()
        
        cursor = self.connection.cursor()
        cursor.execute('DELETE FROM download_records WHERE task_id = ?', (task_id,))
        self.connection.commit()
    
    def get_favorites(self, source: Optional[str] = None) -> List[Comic]:
        """
        Get all favorite comics.
        
        Args:
            source: Optional source filter
            
        Returns:
            List of favorite Comic instances
        """
        if not self.connection:
            self._connect()
        
        cursor = self.connection.cursor()
        
        if source:
            cursor.execute('''
                SELECT c.* FROM comics c
                INNER JOIN favorites f ON c.id = f.comic_id AND c.source = f.source
                WHERE c.source = ?
                ORDER BY f.added_at DESC
            ''', (source,))
        else:
            cursor.execute('''
                SELECT c.* FROM comics c
                INNER JOIN favorites f ON c.id = f.comic_id AND c.source = f.source
                ORDER BY f.added_at DESC
            ''')
        
        comics = []
        for row in cursor.fetchall():
            tags = json.loads(row['tags'])
            categories = json.loads(row['categories'])
            created_at = datetime.fromisoformat(row['created_at']) if row['created_at'] else None
            updated_at = datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
            
            comic = Comic(
                id=row['id'],
                source=row['source'],
                title=row['title'],
                author=row['author'],
                cover_url=row['cover_url'],
                description=row['description'],
                tags=tags,
                categories=categories,
                status=row['status'],
                chapter_count=row['chapter_count'],
                view_count=row['view_count'],
                like_count=row['like_count'],
                is_favorite=True,
                created_at=created_at,
                updated_at=updated_at
            )
            comics.append(comic)
        
        return comics
