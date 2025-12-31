"""
樱花动漫(DM569)适配器 - 视频资源搜索
基于DM569Source API封装，提供动漫视频搜索、详情获取、播放地址解析等功能
"""

import asyncio
from typing import List, Dict, Any, Optional
from PySide6.QtCore import QObject, Signal, QThread, QTimer
from PySide6.QtWidgets import QApplication

from pancomic.models.anime import Anime
from pancomic.models.episode import Episode
from forapi.DM569Source.dm569_source import DM569Source


class DM569SearchWorker(QObject):
    """DM569搜索工作线程"""
    
    search_completed = Signal(list)  # List[Anime]
    search_failed = Signal(str)  # error message
    
    def __init__(self):
        super().__init__()
        self.source = DM569Source()
    
    def search_anime(self, keyword: str):
        """在工作线程中执行搜索"""
        try:
            results = self.source.search(keyword)
            
            # 转换为Anime对象
            anime_list = []
            seen_ids = set()  # 防止重复ID
            seen_titles = set()  # 防止重复标题
            
            for result in results:
                anime_id = result['id']
                anime_title = result['title'].strip()
                
                # 跳过重复的ID
                if anime_id in seen_ids:
                    continue
                
                # 跳过重复的标题（忽略大小写）
                title_lower = anime_title.lower()
                if title_lower in seen_titles:
                    continue
                
                # 验证ID是否为有效数字
                try:
                    int(anime_id)
                except (ValueError, TypeError):
                    continue  # 跳过无效ID
                
                # 跳过空标题
                if not anime_title:
                    continue
                
                seen_ids.add(anime_id)
                seen_titles.add(title_lower)
                
                anime = Anime(
                    id=anime_id,
                    name=anime_title,
                    cover_url=result.get('img', ''),
                    summary='',  # 搜索结果中没有详情，稍后获取
                    tags=[],  # 搜索结果中没有标签，稍后获取
                    year='',
                    area='',
                    status='',
                    source='dm569',
                    url=result['url']
                )
                anime_list.append(anime)
                
                # 限制结果数量，避免过多结果
                if len(anime_list) >= 12:
                    break
            
            self.search_completed.emit(anime_list)
            
        except Exception as e:
            self.search_failed.emit(str(e))


class DM569DetailWorker(QObject):
    """DM569详情获取工作线程"""
    
    detail_completed = Signal(dict)  # anime_detail
    detail_failed = Signal(str)  # error message
    
    def __init__(self):
        super().__init__()
        self.source = DM569Source()
    
    def get_anime_detail(self, anime_id: str):
        """获取动漫详情"""
        try:
            detail = self.source.get_detail(anime_id)
            if detail['success']:
                self.detail_completed.emit(detail)
            else:
                self.detail_failed.emit('获取详情失败')
        except Exception as e:
            self.detail_failed.emit(str(e))


class DM569EpisodesWorker(QObject):
    """DM569剧集获取工作线程"""
    
    episodes_completed = Signal(dict)  # episodes_data
    episodes_failed = Signal(str)  # error message
    
    def __init__(self):
        super().__init__()
        self.source = DM569Source()
    
    def get_episodes(self, anime_id: str):
        """获取剧集列表"""
        try:
            episodes_data = self.source.get_episodes(anime_id)
            self.episodes_completed.emit(episodes_data)
        except Exception as e:
            self.episodes_failed.emit(str(e))


class DM569VideoWorker(QObject):
    """DM569视频地址获取工作线程"""
    
    video_completed = Signal(dict)  # video_info
    video_failed = Signal(str)  # error message
    
    def __init__(self):
        super().__init__()
        self.source = DM569Source()
    
    def get_video_url(self, anime_id: str, line: int, episode: int):
        """获取视频播放地址 - 使用播放专用的简化方法"""
        try:
            print(f"[DM569VideoWorker] 开始获取视频URL: anime_id={anime_id}, line={line}, episode={episode}")
            # 使用播放专用方法，只获取Stream URL，不解析播放器页面
            video_info = self.source.get_stream_url_for_play(anime_id, line, episode)
            
            # 检查返回结果
            if video_info.get('success'):
                print(f"[DM569VideoWorker] ✓ 成功获取视频URL")
                self.video_completed.emit(video_info)
            else:
                error_msg = video_info.get('error', '未知错误')
                print(f"[DM569VideoWorker] ❌ 获取视频URL失败: {error_msg}")
                self.video_failed.emit(error_msg)
                
        except Exception as e:
            error_msg = f"获取视频URL异常: {str(e)}"
            print(f"[DM569VideoWorker] ❌ {error_msg}")
            import traceback
            traceback.print_exc()
            self.video_failed.emit(error_msg)


class DM569Adapter(QObject):
    """
    樱花动漫(DM569)适配器
    
    提供动漫视频资源的搜索、详情获取、播放地址解析等功能
    与番剧Wiki搜索形成互补，为用户提供更丰富的动漫资源
    """
    
    # 信号定义
    search_completed = Signal(list)  # List[Anime]
    search_failed = Signal(str)
    detail_completed = Signal(dict)  # anime_detail
    detail_failed = Signal(str)
    episodes_completed = Signal(dict)  # episodes_data
    episodes_failed = Signal(str)
    video_completed = Signal(dict)  # video_info
    video_failed = Signal(str)
    
    def __init__(self):
        super().__init__()
        self._search_worker = None
        self._search_thread = None
        self._detail_worker = None
        self._detail_thread = None
        self._episodes_worker = None
        self._episodes_thread = None
        self._video_worker = None
        self._video_thread = None
        
        self._setup_workers()
    
    def _setup_workers(self):
        """设置工作线程"""
        # 搜索工作线程
        self._search_thread = QThread()
        self._search_worker = DM569SearchWorker()
        self._search_worker.moveToThread(self._search_thread)
        self._search_worker.search_completed.connect(self.search_completed.emit)
        self._search_worker.search_failed.connect(self.search_failed.emit)
        self._search_thread.start()
        
        # 详情工作线程
        self._detail_thread = QThread()
        self._detail_worker = DM569DetailWorker()
        self._detail_worker.moveToThread(self._detail_thread)
        self._detail_worker.detail_completed.connect(self.detail_completed.emit)
        self._detail_worker.detail_failed.connect(self.detail_failed.emit)
        self._detail_thread.start()
        
        # 剧集工作线程
        self._episodes_thread = QThread()
        self._episodes_worker = DM569EpisodesWorker()
        self._episodes_worker.moveToThread(self._episodes_thread)
        self._episodes_worker.episodes_completed.connect(self.episodes_completed.emit)
        self._episodes_worker.episodes_failed.connect(self.episodes_failed.emit)
        self._episodes_thread.start()
        
        # 视频工作线程
        self._video_thread = QThread()
        self._video_worker = DM569VideoWorker()
        self._video_worker.moveToThread(self._video_thread)
        self._video_worker.video_completed.connect(self.video_completed.emit)
        self._video_worker.video_failed.connect(self.video_failed.emit)
        self._video_thread.start()
    
    def search(self, keyword: str):
        """
        搜索动漫视频资源
        
        Args:
            keyword: 搜索关键词
        """
        if self._search_worker:
            QTimer.singleShot(0, lambda: self._search_worker.search_anime(keyword))
    
    def get_detail(self, anime_id: str):
        """
        获取动漫详情
        
        Args:
            anime_id: 动漫ID
        """
        if self._detail_worker:
            QTimer.singleShot(0, lambda: self._detail_worker.get_anime_detail(anime_id))
    
    def get_episodes(self, anime_id: str):
        """
        获取剧集列表
        
        Args:
            anime_id: 动漫ID
        """
        if self._episodes_worker:
            QTimer.singleShot(0, lambda: self._episodes_worker.get_episodes(anime_id))
    
    def get_video_url(self, anime_id: str, line: int, episode: int):
        """
        获取视频播放地址
        
        Args:
            anime_id: 动漫ID
            line: 线路索引
            episode: 剧集索引
        """
        if self._video_worker:
            QTimer.singleShot(0, lambda: self._video_worker.get_video_url(anime_id, line, episode))
    
    def cleanup(self):
        """清理资源"""
        # 停止所有工作线程
        threads = [
            (self._search_thread, self._search_worker),
            (self._detail_thread, self._detail_worker),
            (self._episodes_thread, self._episodes_worker),
            (self._video_thread, self._video_worker)
        ]
        
        for thread, worker in threads:
            if thread and thread.isRunning():
                if worker:
                    # 断开所有信号连接
                    try:
                        worker.search_completed.disconnect()
                        worker.search_failed.disconnect()
                    except:
                        pass
                    try:
                        worker.detail_completed.disconnect()
                        worker.detail_failed.disconnect()
                    except:
                        pass
                    try:
                        worker.episodes_completed.disconnect()
                        worker.episodes_failed.disconnect()
                    except:
                        pass
                    try:
                        worker.video_completed.disconnect()
                        worker.video_failed.disconnect()
                    except:
                        pass
                thread.quit()
                if not thread.wait(3000):
                    thread.terminate()
                    thread.wait(1000)