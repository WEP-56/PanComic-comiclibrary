"""
拷贝漫画渐进式搜索工作线程
基于通用渐进式搜索工作线程，适配拷贝漫画的数据格式
"""

import time
from typing import List, Dict, Any
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal, Slot

from pancomic.models.comic import Comic
from pancomic.ui.workers.progressive_search_worker import (
    ProgressiveSearchWorker, CrawlerWorker, ParserWorker, ComicBatch
)


class KaobeiCrawlerWorker(CrawlerWorker):
    """拷贝漫画爬虫工作者"""
    
    def fetch_search_data(self, keyword: str, page: int) -> Dict[str, Any]:
        """获取拷贝漫画搜索数据"""
        try:
            print(f"[INFO] Kaobei爬虫: 搜索 '{keyword}' 第{page}页")
            result = self.adapter.search(keyword, page)
            
            comics_count = len(result.get("comics", []))
            print(f"[INFO] Kaobei爬虫: 获取到 {comics_count} 个漫画")
            
            return result
        except Exception as e:
            print(f"[ERROR] Kaobei爬虫请求失败: {e}")
            raise


class KaobeiParserWorker(ParserWorker):
    """拷贝漫画解析工作者"""
    
    def parse_comic_batch(self, raw_comics: List[Dict], batch_index: int) -> List[Comic]:
        """解析拷贝漫画批次数据"""
        comics = []
        
        for comic_data in raw_comics:
            try:
                # 拷贝漫画数据格式适配
                comic = Comic(
                    id=comic_data["comic_id"],
                    title=comic_data["title"],
                    author="未知",  # 从详情页获取
                    cover_url=comic_data["cover"],
                    description=comic_data.get("description", ""),
                    tags=[],
                    categories=["拷贝漫画"],
                    status="completed",
                    chapter_count=0,  # 从详情页获取
                    view_count=0,
                    like_count=0,
                    is_favorite=False,
                    source="kaobei"
                )
                comics.append(comic)
                
            except Exception as e:
                print(f"[ERROR] 解析拷贝漫画数据失败: {e}")
                print(f"[DEBUG] 问题数据: {comic_data}")
                continue
        
        print(f"[INFO] Kaobei解析: 批次 {batch_index + 1} 解析完成，{len(comics)} 个漫画")
        return comics


class KaobeiProgressiveSearchWorker(ProgressiveSearchWorker):
    """
    拷贝漫画渐进式搜索工作线程
    
    继承通用渐进式搜索工作线程，使用拷贝漫画专用的爬虫和解析工作者
    """
    
    def __init__(self, adapter, batch_size: int = 6):
        """
        初始化拷贝漫画渐进式搜索工作线程
        
        Args:
            adapter: KaobeiAdapter实例
            batch_size: 每批处理的漫画数量
        """
        # 调用父类初始化，但不设置工作者
        super().__init__(adapter, batch_size)
        
        # 使用拷贝漫画专用的工作者
        self.crawler = KaobeiCrawlerWorker(adapter)
        self.parser = KaobeiParserWorker()
        
        print(f"[INFO] KaobeiProgressiveSearchWorker 初始化完成，批次大小: {batch_size}")
    
    def get_source_name(self) -> str:
        """获取漫画源名称"""
        return "拷贝漫画"
    
    def get_stats_with_source(self) -> Dict[str, Any]:
        """获取带源信息的统计数据"""
        stats = self.get_stats()
        stats['source'] = self.get_source_name()
        stats['adapter_type'] = 'KaobeiAdapter'
        return stats