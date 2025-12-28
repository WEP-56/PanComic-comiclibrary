# pancomic/adapters/wnacg_adapter.py
"""
绅士漫画 (WNACG) PanComic 适配器
基于 ComicGUISpider 项目移植
"""
import sys
import os
from typing import Dict, Any, List
from PySide6.QtCore import QTimer

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from forapi.wnacg_source import WNACGSourceSync
from pancomic.adapters.base_adapter import BaseSourceAdapter
from pancomic.models.comic import Comic
from pancomic.models.chapter import Chapter


class WNACGAdapter(BaseSourceAdapter):
    """PanComic 标准适配器"""
    
    SOURCE_NAME = "wnacg"
    SOURCE_DISPLAY_NAME = "绅士漫画"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api = None

    def initialize(self) -> None:
        """初始化适配器"""
        try:
            domain = self.config.get('domain', 'www.wn06.ru')  # 默认使用wn06.ru
            self.api = WNACGSourceSync(domain)
            
            # 只有在配置中没有域名时才自动获取
            if not domain or domain == "":
                print("[INFO] WNACG: 配置中无域名，使用默认域名")
                self.api.domain = 'www.wn06.ru'
            else:
                print(f"[INFO] WNACG: 使用配置域名: {domain}")
                self.api.domain = domain
            
            self._is_initialized = True
        except Exception as e:
            print(f"Failed to initialize WNACG adapter: {e}")
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
                    "description": f"{c.get('pages', 0)}页",
                    "preview_url": c.get("preview_url", ""),
                }
                for c in comics
            ],
            "max_page": max_page,
        }

    def get_comic_detail(self, comic_id: str) -> None:
        """异步获取漫画详情 (基类要求的方法)"""
        # 这个方法是基类要求的，但WNACG适配器主要用同步方式
        # 可以在这里实现异步版本，或者保持空实现
        pass

    def get_comic_details(self, comic_id: str) -> Dict[str, Any]:
        """
        获取漫画详情 (同步版本)
        
        WNACG 是本子站，没有章节概念，整本就是一个"章节"
        
        Returns:
            {
                "title": str,
                "cover": str,
                "description": str,
                "tags": list,
                "authors": list,
                "chapters": list,  # 只有一个章节
            }
        """
        if not self.api:
            raise RuntimeError("Adapter not initialized")
            
        d = self.api.get_gallery_details(comic_id)
        
        return {
            "title": d["title"],
            "cover": d["cover"],
            "description": d.get("description", ""),
            "tags": d.get("tags", []),
            "authors": [d.get("uploader", "未知")] if d.get("uploader") else ["绅士漫画"],
            "category": d.get("category", ""),
            "pages": d.get("pages", 0),
            # WNACG 没有章节概念，整本作为一个章节
            "chapters": [
                {
                    "chapter_id": "1",
                    "title": "全本",
                    "group": "default",
                }
            ],
            "subId": comic_id,
        }

    def get_chapters(self, comic_id: str) -> None:
        """异步获取章节列表 (基类要求的方法)"""
        # WNACG只有一个章节，直接发送信号
        try:
            details = self.get_comic_details(comic_id)
            chapters_data = details.get("chapters", [])
            
            from pancomic.models.chapter import Chapter
            chapters = []
            for ch_data in chapters_data:
                chapter = Chapter(
                    id=ch_data["chapter_id"],
                    comic_id=comic_id,
                    title=ch_data["title"],
                    chapter_number=1,
                    page_count=details.get('pages', 0),
                    is_downloaded=False,
                    download_path=None,
                    source="wnacg"
                )
                chapters.append(chapter)
            
            self.chapters_completed.emit(chapters)
        except Exception as e:
            self.chapters_failed.emit(str(e))

    def get_chapter_images(self, comic_id: str, chapter_id: str = None) -> List[str]:
        """
        获取章节图片 (同步版本，用于下载)
        
        对于 WNACG，chapter_id 被忽略，直接返回整本图片
        
        Returns:
            图片 URL 列表
        """
        if not self.api:
            raise RuntimeError("Adapter not initialized")
        
        try:
            images = self.api.get_gallery_images(comic_id)
            
            # 发送异步信号给阅读器
            QTimer.singleShot(0, lambda: self.images_completed.emit(images))
            
            return images
        except Exception as e:
            print(f"[ERROR] 获取图片失败: {e}")
            # 发送失败信号
            QTimer.singleShot(0, lambda: self.images_failed.emit(str(e)))
            raise e

    def login(self, credentials: Dict[str, str]) -> None:
        """登录 (WNACG不需要登录)"""
        # WNACG不需要登录
        QTimer.singleShot(0, lambda: self.login_completed.emit(True, "WNACG无需登录"))

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
                print(f"No images found for comic {comic.id}")
                return False
            
            # 创建下载目录
            import os
            import json
            from pathlib import Path
            from datetime import datetime
            
            # 使用简单的comic_id作为文件夹名，与其他源保持一致
            comic_dir = Path(download_path) / "wnacg" / comic.id
            chapter_dir = comic_dir / "chapter_1"  # 使用标准的chapter_xxx格式
            chapter_dir.mkdir(parents=True, exist_ok=True)
            
            # 下载图片
            import httpx
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': f'https://{self.api.domain}/',
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
                        ext = img_url.split('.')[-1].split('?')[0]
                        if ext not in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                            ext = 'jpg'
                        
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
                'categories': [details.get('category', '绅士漫画')],
                'status': 'completed',
                'chapter_count': 1,
                'view_count': 0,
                'like_count': 0,
                'is_favorite': False,
                'source': 'wnacg',
                'created_at': download_time.isoformat(),
                'chapters': {
                    '1': {
                        'id': '1',
                        'title': '全本',
                        'chapter_number': 1,
                        'page_count': success_count,
                        'download_path': str(chapter_dir),
                        'downloaded_at': download_time.isoformat()
                    }
                },
                'download_info': {
                    'created_time': download_time.isoformat(),
                    'updated_time': download_time.isoformat(),
                    'total_size': sum(
                        (chapter_dir / f"{i:03d}.jpg").stat().st_size 
                        for i in range(1, success_count + 1)
                        if (chapter_dir / f"{i:03d}.jpg").exists()
                    ),
                    'status': 'completed'
                }
            }
            
            # 保存metadata.json
            metadata_file = comic_dir / 'metadata.json'
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            print(f"Download completed: {success_count}/{total_images} images")
            print(f"Metadata saved to: {metadata_file}")
            return success_count > 0
            
        except Exception as e:
            print(f"Download failed: {e}")
            return False
    
    def refresh_domain(self) -> str:
        """手动刷新域名并保存到配置"""
        if not self.api:
            raise RuntimeError("Adapter not initialized")
        
        print("[INFO] WNACG: 手动刷新域名...")
        
        # 清除当前域名，强制重新获取
        old_domain = self.api.domain
        self.api.domain = None
        
        try:
            # 执行搜索触发域名获取
            self.api.search("test", 1)
            new_domain = self.api.domain
            
            if new_domain and new_domain != old_domain:
                # 保存新域名到配置
                self.config['domain'] = new_domain
                print(f"[INFO] WNACG: 域名已更新: {old_domain} → {new_domain}")
                return new_domain
            else:
                print(f"[INFO] WNACG: 域名未变化: {new_domain}")
                return new_domain or old_domain
                
        except Exception as e:
            # 恢复旧域名
            self.api.domain = old_domain
            print(f"[ERROR] WNACG: 域名刷新失败: {e}")
            raise e
    
    def close(self):
        """关闭资源"""
        if self.api:
            self.api.close()