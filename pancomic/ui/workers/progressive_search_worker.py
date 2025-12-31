"""
渐进式搜索工作线程系统
解决"伪异步"问题，实现真正的异步渐进式渲染

架构：
1. 爬虫线程池 - 负责网络请求
2. 解析线程池 - 负责数据解析  
3. 渐进式发送 - 每解析完一批数据立即发送给UI
"""

import time
import threading
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue, Empty
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal, Slot, QTimer
from PySide6.QtWidgets import QApplication

from pancomic.models.comic import Comic


@dataclass
class SearchTask:
    """搜索任务"""
    keyword: str
    page: int
    task_id: str
    
    
@dataclass
class ComicBatch:
    """漫画批次数据"""
    comics: List[Comic]
    batch_index: int
    total_batches: int
    task_id: str
    is_final: bool = False
    timestamp: float = 0.0  # 批次创建时间戳
    
    def __post_init__(self):
        """初始化后处理"""
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class CrawlerWorker:
    """爬虫工作者 - 负责网络请求"""
    
    def __init__(self, adapter):
        self.adapter = adapter
        
    def fetch_search_data(self, keyword: str, page: int) -> Dict[str, Any]:
        """获取搜索数据"""
        try:
            return self.adapter.search(keyword, page)
        except Exception as e:
            print(f"[ERROR] 爬虫请求失败: {e}")
            raise


class ParserWorker:
    """解析工作者 - 负责数据解析"""
    
    def __init__(self):
        pass
        
    def parse_comic_batch(self, raw_comics: List[Dict], batch_index: int) -> List[Comic]:
        """解析漫画批次数据"""
        comics = []
        
        for comic_data in raw_comics:
            try:
                comic = Comic(
                    id=comic_data["comic_id"],
                    title=comic_data["title"],
                    author="",  # 详情页获取
                    cover_url=comic_data["cover"],
                    description=comic_data["description"],
                    tags=[],
                    categories=[],
                    status="completed",
                    chapter_count=1,  # WNACG只有一个章节
                    view_count=0,
                    like_count=0,
                    is_favorite=False,
                    source="wnacg"
                )
                comics.append(comic)
            except Exception as e:
                print(f"[ERROR] 解析漫画数据失败: {e}")
                continue
                
        return comics


class ProgressiveSearchWorker(QObject):
    """
    渐进式搜索工作线程
    
    特点：
    1. 使用线程池进行爬虫和解析
    2. 每解析完一批数据立即发送给UI
    3. 避免一次性创建大量UI组件
    """
    
    # 信号定义
    batch_ready = Signal(object)  # ComicBatch - 批次数据就绪
    search_completed = Signal(str, int)  # task_id, max_page - 搜索完成
    search_failed = Signal(str, str)  # task_id, error_message - 搜索失败
    progress_updated = Signal(str, int, int)  # task_id, current, total - 进度更新
    
    def __init__(self, adapter, batch_size: int = 6):
        """
        初始化渐进式搜索工作线程
        
        Args:
            adapter: 漫画源适配器
            batch_size: 每批处理的漫画数量
        """
        super().__init__()
        
        self.adapter = adapter
        self.batch_size = batch_size
        
        # 线程池
        self.crawler_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="Crawler")
        self.parser_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="Parser")
        
        # 工作者
        self.crawler = CrawlerWorker(adapter)
        self.parser = ParserWorker()
        
        # 任务管理
        self.current_tasks: Dict[str, SearchTask] = {}
        self.is_running = True
        
        # 性能监控
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_comics_processed': 0,
            'average_batch_time': 0.0
        }
    
    @Slot(str, int, str)
    def start_progressive_search(self, keyword: str, page: int, task_id: str):
        """
        开始渐进式搜索
        
        Args:
            keyword: 搜索关键词
            page: 页码
            task_id: 任务ID
        """
        if not self.is_running:
            return
            
        task = SearchTask(keyword, page, task_id)
        self.current_tasks[task_id] = task
        
        print(f"[INFO] 开始渐进式搜索: {keyword}, 页码: {page}, 任务ID: {task_id}")
        
        # 提交爬虫任务
        future = self.crawler_pool.submit(self._execute_search, task)
        
        # 监控任务完成
        def on_crawl_done():
            try:
                if future.done() and not future.cancelled():
                    if future.exception():
                        error_msg = str(future.exception())
                        print(f"[ERROR] 爬虫任务失败: {error_msg}")
                        self.search_failed.emit(task_id, error_msg)
                    # 成功的情况在_execute_search中处理
            except Exception as e:
                print(f"[ERROR] 监控爬虫任务异常: {e}")
                self.search_failed.emit(task_id, str(e))
        
        # 使用QTimer延迟检查，避免阻塞
        QTimer.singleShot(100, on_crawl_done)
    
    def _execute_search(self, task: SearchTask):
        """执行搜索任务"""
        start_time = time.time()
        
        try:
            # 1. 爬虫阶段 - 获取原始数据
            print(f"[INFO] 爬虫阶段开始: {task.keyword}")
            raw_data = self.crawler.fetch_search_data(task.keyword, task.page)
            
            comics_data = raw_data.get("comics", [])
            max_page = raw_data.get("max_page", 1)
            
            if not comics_data:
                print(f"[WARN] 没有找到漫画数据: {task.keyword}")
                self.search_completed.emit(task.task_id, max_page)
                return
            
            total_comics = len(comics_data)
            print(f"[INFO] 获取到 {total_comics} 个漫画，开始分批解析")
            
            # 2. 分批解析阶段
            batches = self._split_into_batches(comics_data, self.batch_size)
            total_batches = len(batches)
            
            # 提交解析任务
            parse_futures = []
            for batch_index, batch_data in enumerate(batches):
                future = self.parser_pool.submit(
                    self._parse_and_emit_batch, 
                    batch_data, 
                    batch_index, 
                    total_batches, 
                    task.task_id
                )
                parse_futures.append(future)
            
            # 等待所有解析任务完成
            completed_batches = 0
            for future in as_completed(parse_futures):
                try:
                    future.result()  # 获取结果，如果有异常会抛出
                    completed_batches += 1
                    
                    # 更新进度
                    self.progress_updated.emit(task.task_id, completed_batches, total_batches)
                    
                except Exception as e:
                    print(f"[ERROR] 解析批次失败: {e}")
            
            # 3. 搜索完成
            elapsed_time = time.time() - start_time
            print(f"[INFO] 搜索完成: {task.keyword}, 耗时: {elapsed_time:.2f}s, 批次: {total_batches}")
            
            # 更新统计
            self.stats['total_requests'] += 1
            self.stats['successful_requests'] += 1
            self.stats['total_comics_processed'] += total_comics
            
            # 发送完成信号
            self.search_completed.emit(task.task_id, max_page)
            
        except Exception as e:
            print(f"[ERROR] 搜索执行失败: {e}")
            self.stats['total_requests'] += 1
            self.stats['failed_requests'] += 1
            self.search_failed.emit(task.task_id, str(e))
        
        finally:
            # 清理任务
            if task.task_id in self.current_tasks:
                del self.current_tasks[task.task_id]
    
    def _split_into_batches(self, comics_data: List[Dict], batch_size: int) -> List[List[Dict]]:
        """将漫画数据分割成批次"""
        batches = []
        for i in range(0, len(comics_data), batch_size):
            batch = comics_data[i:i + batch_size]
            batches.append(batch)
        return batches
    
    def _parse_and_emit_batch(self, batch_data: List[Dict], batch_index: int, total_batches: int, task_id: str):
        """解析并发送批次数据"""
        batch_start_time = time.time()
        
        try:
            # 解析批次数据
            comics = self.parser.parse_comic_batch(batch_data, batch_index)
            
            if comics:
                # 创建批次对象
                comic_batch = ComicBatch(
                    comics=comics,
                    batch_index=batch_index,
                    total_batches=total_batches,
                    task_id=task_id,
                    is_final=(batch_index == total_batches - 1)
                )
                
                # 立即发送给UI线程
                self.batch_ready.emit(comic_batch)
                
                batch_time = time.time() - batch_start_time
                print(f"[INFO] 批次 {batch_index + 1}/{total_batches} 解析完成: {len(comics)} 个漫画, 耗时: {batch_time:.3f}s")
                
                # 更新平均批次时间
                if self.stats['average_batch_time'] == 0:
                    self.stats['average_batch_time'] = batch_time
                else:
                    self.stats['average_batch_time'] = (self.stats['average_batch_time'] + batch_time) / 2
            
        except Exception as e:
            print(f"[ERROR] 解析批次 {batch_index} 失败: {e}")
            raise
    
    @Slot(str)
    def cancel_search(self, task_id: str):
        """取消搜索任务"""
        if task_id in self.current_tasks:
            print(f"[INFO] 取消搜索任务: {task_id}")
            del self.current_tasks[task_id]
            
            # 发送取消信号，让UI知道任务已取消
            self.search_failed.emit(task_id, "用户取消搜索")
    
    def cancel_all_tasks(self):
        """取消所有搜索任务"""
        task_ids = list(self.current_tasks.keys())
        for task_id in task_ids:
            self.cancel_search(task_id)
        print(f"[INFO] 已取消 {len(task_ids)} 个搜索任务")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        return self.stats.copy()
    
    def cleanup(self):
        """清理资源"""
        print("[INFO] ProgressiveSearchWorker cleanup started...")
        
        self.is_running = False
        
        # 清理任务
        self.current_tasks.clear()
        
        # 关闭线程池
        try:
            print("[INFO] Shutting down crawler pool...")
            self.crawler_pool.shutdown(wait=True, timeout=5.0)
            print("[INFO] Crawler pool shut down")
        except Exception as e:
            print(f"[ERROR] Error shutting down crawler pool: {e}")
        
        try:
            print("[INFO] Shutting down parser pool...")
            self.parser_pool.shutdown(wait=True, timeout=5.0)
            print("[INFO] Parser pool shut down")
        except Exception as e:
            print(f"[ERROR] Error shutting down parser pool: {e}")
        
        print("[INFO] ProgressiveSearchWorker cleanup completed")