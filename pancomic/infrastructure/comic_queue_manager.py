"""
漫画下载队列管理器
为download_page.py提供兼容的队列管理接口
"""

import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from PySide6.QtCore import QObject, Signal

from pancomic.models.comic import Comic
from pancomic.models.chapter import Chapter


class QueueItem:
    """队列项目类，兼容原来的接口"""
    
    def __init__(self, comic: Comic, chapters: List[Chapter], source: str):
        self.id = f"{comic.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.comic = comic
        self.chapters = chapters
        self.source = source
        self.created_time = datetime.now().isoformat()
        
        # 添加兼容属性
        self.comic_title = comic.title
        self.comic_author = getattr(comic, 'author', '未知作者')
        self.chapter_count = len(chapters)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'id': self.id,
            'comic': {
                'id': self.comic.id,
                'title': self.comic.title,
                'author': self.comic.author,
                'cover_url': self.comic.cover_url,
                'description': self.comic.description,
                'tags': self.comic.tags,
                'categories': self.comic.categories,
                'status': self.comic.status,
                'chapter_count': self.comic.chapter_count,
                'view_count': self.comic.view_count,
                'like_count': self.comic.like_count,
                'is_favorite': self.comic.is_favorite,
                'source': self.comic.source
            },
            'chapters': [
                {
                    'id': chapter.id,
                    'title': chapter.title,
                    'chapter_number': chapter.chapter_number,
                    'page_count': chapter.page_count
                } for chapter in self.chapters
            ],
            'source': self.source,
            'created_time': self.created_time
        }


class ComicQueueManager(QObject):
    """
    漫画下载队列管理器
    为download_page.py提供兼容的接口
    """
    
    queue_updated = Signal()
    
    def __init__(self, queue_file_path: str = None):
        super().__init__()
        
        # 队列文件路径
        if queue_file_path is None:
            project_root = Path(__file__).parent.parent.parent
            downloads_dir = project_root / "downloads"
            downloads_dir.mkdir(exist_ok=True)
            queue_file_path = downloads_dir / "comic_queue.json"
        
        self.queue_file_path = Path(queue_file_path)
        self._queue_items: List[QueueItem] = []
        
        # 加载队列
        self._load_queue()
    
    def reload(self):
        """重新加载队列"""
        self._load_queue()
    
    def get_all_items(self) -> List[QueueItem]:
        """获取所有队列项目"""
        return self._queue_items.copy()
    
    def get_item(self, item_id: str) -> Optional[QueueItem]:
        """获取指定的队列项目"""
        for item in self._queue_items:
            if item.id == item_id:
                return item
        return None
    
    def add_to_queue(self, comic: Comic, chapters: List[Chapter], source: str) -> str:
        """添加到队列"""
        item = QueueItem(comic, chapters, source)
        self._queue_items.append(item)
        self._save_queue()
        self.queue_updated.emit()
        return item.id
    
    def remove_from_queue(self, item_id: str) -> bool:
        """从队列中移除"""
        for i, item in enumerate(self._queue_items):
            if item.id == item_id:
                del self._queue_items[i]
                self._save_queue()
                self.queue_updated.emit()
                return True
        return False
    
    def clear_queue(self):
        """清空队列"""
        self._queue_items.clear()
        self._save_queue()
        self.queue_updated.emit()
    
    def _load_queue(self):
        """从文件加载队列"""
        try:
            if self.queue_file_path.exists():
                with open(self.queue_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                self._queue_items = []
                for item_data in data.get('items', []):
                    # 重建Comic对象
                    comic_data = item_data['comic']
                    comic = Comic(
                        id=comic_data['id'],
                        title=comic_data['title'],
                        author=comic_data.get('author', '未知作者'),
                        cover_url=comic_data.get('cover_url', ''),
                        description=comic_data.get('description', ''),
                        tags=comic_data.get('tags', []),
                        categories=comic_data.get('categories', []),
                        status=comic_data.get('status', 'unknown'),
                        chapter_count=comic_data.get('chapter_count', 0),
                        view_count=comic_data.get('view_count', 0),
                        like_count=comic_data.get('like_count', 0),
                        is_favorite=comic_data.get('is_favorite', False),
                        source=comic_data['source']
                    )
                    
                    # 重建Chapter对象
                    chapters = []
                    for chapter_data in item_data['chapters']:
                        chapter = Chapter(
                            id=chapter_data['id'],
                            comic_id=comic_data['id'],
                            title=chapter_data['title'],
                            chapter_number=chapter_data.get('chapter_number', 0),
                            page_count=chapter_data.get('page_count', 0),
                            is_downloaded=False,
                            download_path=None,
                            source=comic_data['source']
                        )
                        chapters.append(chapter)
                    
                    # 创建QueueItem
                    item = QueueItem(comic, chapters, item_data['source'])
                    item.id = item_data['id']  # 保持原来的ID
                    item.created_time = item_data.get('created_time', datetime.now().isoformat())
                    
                    self._queue_items.append(item)
                
                print(f"[ComicQueueManager] 加载队列: {len(self._queue_items)}个项目")
        except Exception as e:
            print(f"[ComicQueueManager] 加载队列失败: {e}")
            self._queue_items = []
    
    def _save_queue(self):
        """保存队列到文件"""
        try:
            data = {
                'items': [item.to_dict() for item in self._queue_items],
                'updated_time': datetime.now().isoformat()
            }
            
            with open(self.queue_file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"[ComicQueueManager] 保存队列失败: {e}")