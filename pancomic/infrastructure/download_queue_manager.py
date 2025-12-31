"""
下载队列管理器 - 已禁用
管理动漫视频的下载队列，支持单集下载和全集下载

注意：动漫下载功能已被移除，此文件已禁用。
如需重新启用，请移除此注释并恢复相关功能。
"""

# 动漫下载功能已移除 - 此文件已禁用
# 如需重新启用，请移除此注释

"""
import json
import os
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

from PySide6.QtCore import QObject, Signal, QTimer

from pancomic.models.anime import Anime
from pancomic.models.episode import Episode


class DownloadStatus(Enum):
    """下载状态枚举"""
    PENDING = "pending"      # 等待中
    DOWNLOADING = "downloading"  # 下载中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"       # 失败
    PAUSED = "paused"       # 暂停


@dataclass
class DownloadTask:
    """下载任务数据类"""
    task_id: str
    anime: Dict[str, Any]  # 动漫信息
    episode: Dict[str, Any]  # 剧集信息
    status: str = DownloadStatus.PENDING.value
    progress: int = 0  # 下载进度 0-100
    error_message: str = ""
    created_time: str = ""
    started_time: str = ""
    completed_time: str = ""
    output_path: str = ""
    stream_url: str = ""
    
    def __post_init__(self):
        if not self.created_time:
            self.created_time = datetime.now().isoformat()


class DownloadQueueManager(QObject):
    """
    下载队列管理器
    
    功能：
    1. 管理下载任务队列
    2. 支持单集和全集下载
    3. 持久化队列状态
    4. 提供队列操作接口
    """
    
    # 信号定义
    task_added = Signal(str)  # task_id
    task_started = Signal(str)  # task_id
    task_progress = Signal(str, int)  # task_id, progress
    task_completed = Signal(str, str)  # task_id, output_path
    task_failed = Signal(str, str)  # task_id, error
    queue_updated = Signal()  # 队列更新
    
    def __init__(self, queue_file_path: str = None):
        super().__init__()
        
        # 队列文件路径
        if queue_file_path is None:
            project_root = Path(__file__).parent.parent.parent
            downloads_dir = project_root / "downloads"
            downloads_dir.mkdir(exist_ok=True)
            queue_file_path = downloads_dir / "download_queue.json"
        
        self.queue_file_path = Path(queue_file_path)
        
        # 下载任务队列
        self._download_queue: List[DownloadTask] = []
        self._active_downloads: Dict[str, Any] = {}  # task_id -> downloader
        
        # 配置
        self.max_concurrent_downloads = 3  # 最大并发下载数
        
        # 加载队列
        self._load_queue()
        
        # 定时保存队列
        self._save_timer = QTimer()
        self._save_timer.timeout.connect(self._save_queue)
        self._save_timer.start(30000)  # 每30秒保存一次
    
    def add_episode_task(
        self, 
        anime: Anime, 
        episode: Episode, 
        stream_url: str = ""
    ) -> str:
        """
        添加单集下载任务
        
        Args:
            anime: 动漫信息
            episode: 剧集信息
            stream_url: 流地址（可选，后续获取）
            
        Returns:
            任务ID
        """
        task_id = f"{anime.id}_{episode.line}_{episode.ep}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        task = DownloadTask(
            task_id=task_id,
            anime=self._anime_to_dict(anime),
            episode=self._episode_to_dict(episode),
            stream_url=stream_url
        )
        
        self._download_queue.append(task)
        self._save_queue()
        
        self.task_added.emit(task_id)
        self.queue_updated.emit()
        
        print(f"[DownloadQueue] 添加单集任务: {anime.name} - {episode.name}")
        return task_id
    
    def add_series_tasks(
        self, 
        anime: Anime, 
        episodes: List[Episode], 
        line_index: int = 0
    ) -> List[str]:
        """
        添加全集下载任务
        
        Args:
            anime: 动漫信息
            episodes: 剧集列表
            line_index: 线路索引
            
        Returns:
            任务ID列表
        """
        task_ids = []
        
        for episode in episodes:
            # 检查是否已存在该剧集的任务
            if not self._is_episode_in_queue(anime.id, episode.line, episode.ep):
                task_id = self.add_episode_task(anime, episode)
                task_ids.append(task_id)
        
        print(f"[DownloadQueue] 添加全集任务: {anime.name}, 共{len(task_ids)}集")
        return task_ids
    
    def _is_episode_in_queue(self, anime_id: str, line: int, episode: int) -> bool:
        """检查剧集是否已在队列中"""
        for task in self._download_queue:
            if (task.anime.get('id') == anime_id and 
                task.episode.get('line') == line and 
                task.episode.get('ep') == episode and
                task.status != DownloadStatus.FAILED.value):
                return True
        return False
    
    def get_queue_tasks(self, status_filter: Optional[str] = None) -> List[DownloadTask]:
        """
        获取队列任务
        
        Args:
            status_filter: 状态过滤器
            
        Returns:
            任务列表
        """
        if status_filter:
            return [task for task in self._download_queue if task.status == status_filter]
        return self._download_queue.copy()
    
    def get_task(self, task_id: str) -> Optional[DownloadTask]:
        """获取指定任务"""
        for task in self._download_queue:
            if task.task_id == task_id:
                return task
        return None
    
    def update_task_status(self, task_id: str, status: DownloadStatus, **kwargs):
        """更新任务状态"""
        task = self.get_task(task_id)
        if not task:
            return
        
        task.status = status.value
        
        # 更新其他字段
        if 'progress' in kwargs:
            task.progress = kwargs['progress']
        if 'error_message' in kwargs:
            task.error_message = kwargs['error_message']
        if 'output_path' in kwargs:
            task.output_path = kwargs['output_path']
        if 'stream_url' in kwargs:
            task.stream_url = kwargs['stream_url']
        
        # 更新时间戳
        now = datetime.now().isoformat()
        if status == DownloadStatus.DOWNLOADING and not task.started_time:
            task.started_time = now
        elif status in [DownloadStatus.COMPLETED, DownloadStatus.FAILED]:
            task.completed_time = now
        
        self._save_queue()
        self.queue_updated.emit()
        
        # 发射相应信号
        if status == DownloadStatus.DOWNLOADING:
            self.task_started.emit(task_id)
        elif status == DownloadStatus.COMPLETED:
            self.task_completed.emit(task_id, task.output_path)
        elif status == DownloadStatus.FAILED:
            self.task_failed.emit(task_id, task.error_message)
    
    def update_task_progress(self, task_id: str, progress: int):
        """更新任务进度"""
        task = self.get_task(task_id)
        if task:
            task.progress = progress
            self.task_progress.emit(task_id, progress)
    
    def remove_task(self, task_id: str) -> bool:
        """移除任务"""
        for i, task in enumerate(self._download_queue):
            if task.task_id == task_id:
                del self._download_queue[i]
                self._save_queue()
                self.queue_updated.emit()
                return True
        return False
    
    def clear_completed_tasks(self):
        """清理已完成的任务"""
        self._download_queue = [
            task for task in self._download_queue 
            if task.status != DownloadStatus.COMPLETED.value
        ]
        self._save_queue()
        self.queue_updated.emit()
    
    def get_pending_tasks(self) -> List[DownloadTask]:
        """获取等待中的任务"""
        return [
            task for task in self._download_queue 
            if task.status == DownloadStatus.PENDING.value
        ]
    
    def get_active_download_count(self) -> int:
        """获取当前活跃下载数"""
        return len([
            task for task in self._download_queue 
            if task.status == DownloadStatus.DOWNLOADING.value
        ])
    
    def can_start_new_download(self) -> bool:
        """检查是否可以开始新的下载"""
        return self.get_active_download_count() < self.max_concurrent_downloads
    
    def _anime_to_dict(self, anime: Anime) -> Dict[str, Any]:
        """将Anime对象转换为字典"""
        return {
            'id': anime.id,
            'name': anime.name,
            'source': anime.source,
            'cover_url': anime.cover_url,
            'summary': anime.summary,
            'tags': anime.tags,
            'year': anime.year,
            'area': anime.area,
            'bangumi_url': getattr(anime, 'bangumi_url', ''),
            'alias': getattr(anime, 'alias', '')
        }
    
    def _episode_to_dict(self, episode: Episode) -> Dict[str, Any]:
        """将Episode对象转换为字典"""
        return {
            'index': episode.index,
            'name': episode.name,
            'url': episode.url,
            'line': episode.line,
            'ep': episode.ep,
            'anime_id': episode.anime_id
        }
    
    def _load_queue(self):
        """从文件加载队列"""
        try:
            if self.queue_file_path.exists():
                with open(self.queue_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                self._download_queue = []
                for task_data in data.get('tasks', []):
                    task = DownloadTask(**task_data)
                    self._download_queue.append(task)
                
                print(f"[DownloadQueue] 加载队列: {len(self._download_queue)}个任务")
        except Exception as e:
            print(f"[DownloadQueue] 加载队列失败: {e}")
            self._download_queue = []
    
    def _save_queue(self):
        """保存队列到文件"""
        try:
            data = {
                'tasks': [asdict(task) for task in self._download_queue],
                'updated_time': datetime.now().isoformat()
            }
            
            with open(self.queue_file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            print(f"[DownloadQueue] 保存队列失败: {e}")
    
    def cleanup(self):
        """清理资源"""
        if hasattr(self, '_save_timer'):
            self._save_timer.stop()
        self._save_queue()
    
    # 兼容性方法（为了与旧的download_page.py兼容）
    def reload(self):
        """重新加载队列（兼容性方法）"""
        self._load_queue()
    
    def get_all_items(self):
        """获取所有队列项（兼容性方法）"""
        return self.get_queue_tasks()