# pancomic/adapters/kaobei_adapter.py
"""
拷贝漫画 (Kaobei) PanComic 适配器
基于 ComicGUISpider 项目移植
"""
import sys
import os
from typing import Dict, Any, List
from pathlib import Path
from PySide6.QtCore import QTimer

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from forapi.kaobei_source import KaobeiSourceSync
from pancomic.adapters.base_adapter import BaseSourceAdapter
from pancomic.models.comic import Comic
from pancomic.models.chapter import Chapter


class KaobeiAdapter(BaseSourceAdapter):
    """拷贝漫画 PanComic 标准适配器"""
    
    SOURCE_NAME = "kaobei"
    SOURCE_DISPLAY_NAME = "拷贝漫画"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api = None

    def initialize(self) -> None:
        """初始化适配器"""
        try:
            domain = self.config.get('domain', 'api.2025copy.com')
            self.api = KaobeiSourceSync(domain)
            
            print(f"[INFO] Kaobei: 使用域名: {domain}")
            self._is_initialized = True
            
        except Exception as e:
            print(f"Failed to initialize Kaobei adapter: {e}")
            self._is_initialized = False

    def search(self, keyword: str, page: int = 1) -> Dict[str, Any]:
        """
        搜索漫画 (同步版本，用于直接调用)
        
        Returns:
            {
                "comics": [...],
                "max_page": int
            }
        """
        if not self.api:
            raise RuntimeError("Adapter not initialized")
            
        comics, max_page = self.api.search(keyword, page)
        return {
            "comics": [
                {
                    "comic_id": c["id"],
                    "title": c["title"],
                    "cover": c["cover"],
                    "description": c.get("description", ""),
                    "preview_url": c.get("preview_url", ""),
                }
                for c in comics
            ],
            "max_page": max_page,
        }

    def get_comic_detail(self, comic_id: str) -> None:
        """异步获取漫画详情 (基类要求的方法)"""
        # 这个方法是基类要求的，但主要用同步方式
        pass

    def get_comic_details(self, comic_id: str) -> Dict[str, Any]:
        """
        获取漫画详情 (同步版本)
        
        Returns:
            {
                "title": str,
                "cover": str,
                "description": str,
                "tags": list,
                "authors": list,
                "chapters": list,
            }
        """
        if not self.api:
            raise RuntimeError("Adapter not initialized")
            
        details = self.api.get_comic_details(comic_id)
        
        return {
            "title": details["title"],
            "cover": details["cover"],
            "description": details.get("description", ""),
            "tags": details.get("tags", []),
            "authors": details.get("authors", ["未知"]),
            "category": details.get("category", ""),
            "pages": details.get("pages", 0),
            "chapters": details.get("chapters", []),
            "subId": comic_id,
        }

    def get_chapters(self, comic_id: str) -> None:
        """异步获取章节列表 (基类要求的方法)"""
        try:
            details = self.get_comic_details(comic_id)
            chapters_data = details.get("chapters", [])
            
            chapters = []
            for ch_data in chapters_data:
                chapter = Chapter(
                    id=ch_data["chapter_id"],
                    comic_id=comic_id,
                    title=ch_data["title"],
                    chapter_number=int(ch_data["chapter_id"]),
                    page_count=0,  # 需要从图片列表获取
                    is_downloaded=False,
                    download_path=None,
                    source="kaobei"
                )
                chapters.append(chapter)
            
            self.chapters_completed.emit(chapters)
        except Exception as e:
            self.chapters_failed.emit(str(e))

    def get_chapter_images(self, comic_id: str, chapter_id: str) -> List[str]:
        """
        获取章节图片 (同步版本，用于下载)
        
        Returns:
            图片 URL 列表
        """
        if not self.api:
            raise RuntimeError("Adapter not initialized")
        
        try:
            images = self.api.get_chapter_images(comic_id, chapter_id)
            
            # 发送异步信号给阅读器
            QTimer.singleShot(0, lambda: self.images_completed.emit(images))
            
            return images
        except Exception as e:
            print(f"[ERROR] 获取图片失败: {e}")
            # 发送失败信号
            QTimer.singleShot(0, lambda: self.images_failed.emit(str(e)))
            raise e

    def login(self, credentials: Dict[str, str]) -> None:
        """登录 (拷贝漫画不需要登录)"""
        # 拷贝漫画不需要登录
        QTimer.singleShot(0, lambda: self.login_completed.emit(True, "拷贝漫画无需登录"))

    def download_chapter(self, comic: Comic, chapter: Chapter, download_path: str, progress_callback=None) -> bool:
        """
        下载章节
        
        Args:
            comic: 漫画对象
            chapter: 章节对象
            download_path: 下载路径
            progress_callback: 进度回调函数 (current, total)
            
        Returns:
            是否下载成功
        """
        try:
            if not self.api:
                raise RuntimeError("Adapter not initialized")
            
            # 获取图片列表
            images = self.get_chapter_images(comic.id, chapter.id)
            
            if not images:
                print(f"No images found for comic {comic.id}, chapter {chapter.id}")
                return False
            
            # 创建下载目录
            import os
            import json
            from pathlib import Path
            from datetime import datetime
            
            comic_dir = Path(download_path) / "kaobei" / comic.id
            chapter_dir = comic_dir / f"chapter_{chapter.id}"
            chapter_dir.mkdir(parents=True, exist_ok=True)
            
            # 下载图片
            import httpx
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': f'https://{self.api.pc_domain}/',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8'
            }
            
            success_count = 0
            total_images = len(images)
            
            with httpx.Client(headers=headers, timeout=30) as client:
                for i, img_url in enumerate(images, 1):
                    try:
                        # 报告进度
                        if progress_callback:
                            progress_callback(i, total_images)
                        
                        # 获取文件扩展名
                        ext = self._get_image_extension(img_url)
                        
                        # 下载图片
                        response = client.get(img_url)
                        response.raise_for_status()
                        
                        # 保存图片
                        img_path = chapter_dir / f"{i:03d}.{ext}"
                        with open(img_path, 'wb') as f:
                            f.write(response.content)
                        
                        success_count += 1
                        print(f"Downloaded {i}/{total_images}: {img_path.name}")
                        
                    except Exception as e:
                        print(f"Failed to download image {i}: {e}")
                        continue
            
            if success_count == 0:
                print("No images were downloaded successfully")
                return False
            
            # 生成metadata.json
            self._generate_metadata(comic, chapter, comic_dir, success_count)
            
            print(f"Download completed: {success_count}/{total_images} images")
            return success_count > 0
            
        except Exception as e:
            print(f"Download failed: {e}")
            return False
    
    def _get_image_extension(self, img_url: str) -> str:
        """获取图片扩展名"""
        ext = img_url.split('.')[-1].split('?')[0].lower()
        if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
            return ext
        return 'jpg'  # 默认扩展名
    
    def _generate_metadata(self, comic: Comic, chapter: Chapter, comic_dir: Path, page_count: int):
        """生成标准的 metadata.json"""
        import json
        from datetime import datetime
        
        download_time = datetime.now()
        
        # 获取漫画详情用于metadata
        try:
            details = self.get_comic_details(comic.id)
        except:
            details = {}
        
        metadata = {
            'id': comic.id,
            'title': comic.title,
            'author': ', '.join(details.get('authors', ['未知'])),
            'cover_url': comic.cover_url,
            'description': details.get('description', ''),
            'tags': details.get('tags', []),
            'categories': [details.get('category', '拷贝漫画')],
            'status': 'completed',
            'chapter_count': len(details.get('chapters', [])),
            'view_count': 0,
            'like_count': 0,
            'is_favorite': False,
            'source': 'kaobei',
            'created_at': download_time.isoformat(),
            'chapters': {
                chapter.id: {
                    'id': chapter.id,
                    'title': chapter.title,
                    'chapter_number': chapter.chapter_number,
                    'page_count': page_count,
                    'download_path': str(comic_dir / f"chapter_{chapter.id}"),
                    'downloaded_at': download_time.isoformat()
                }
            },
            'download_info': {
                'created_time': download_time.isoformat(),
                'updated_time': download_time.isoformat(),
                'status': 'completed'
            }
        }
        
        metadata_file = comic_dir / 'metadata.json'
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        print(f"Metadata saved to: {metadata_file}")
    
    def supports_login(self) -> bool:
        """是否支持登录"""
        return False
    
    def get_available_domains(self) -> List[str]:
        """获取可用域名列表"""
        return [
            "api.2025copy.com",
            "www.2025copy.com"
        ]
    
    def close(self):
        """关闭资源"""
        if self.api:
            self.api.close()