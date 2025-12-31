"""
动漫下载工作线程 - 已禁用
将整个动漫下载过程（包括URL解析和视频下载）从主线程中分离

注意：动漫下载功能已被移除，此文件已禁用。
如需重新启用，请移除此注释并恢复相关功能。
"""

# 动漫下载功能已移除 - 此文件已禁用
# 如需重新启用，请移除此注释

"""
import os
from typing import Dict, Any
from pathlib import Path
from datetime import datetime

from PySide6.QtCore import QObject, Signal, QThread, QTimer
from PySide6.QtWidgets import QApplication

from pancomic.models.anime import Anime
from pancomic.models.episode import Episode
from pancomic.adapters.dm569_adapter import DM569Adapter
from pancomic.infrastructure.video_downloader import VideoDownloader


class AnimeDownloadTask(QObject):
    """动漫下载任务工作线程"""
    
    # 信号定义
    task_started = Signal(str)  # task_id
    url_extraction_started = Signal(str)  # task_id
    url_extraction_completed = Signal(str, str)  # task_id, stream_url
    url_extraction_failed = Signal(str, str)  # task_id, error
    download_started = Signal(str)  # task_id
    download_progress = Signal(str, int, int)  # task_id, current, total
    download_completed = Signal(str, str)  # task_id, output_path
    download_failed = Signal(str, str)  # task_id, error
    task_completed = Signal(str)  # task_id
    task_failed = Signal(str, str)  # task_id, error
    
    def __init__(self, download_base_path: str):
        super().__init__()
        self.download_base_path = download_base_path
        self._dm569_adapter = None
        self._video_downloader = None
        self._current_task = None
        
        # 设置DM569适配器
        self._setup_dm569_adapter()
    
    def _setup_dm569_adapter(self):
        """设置DM569适配器"""
        try:
            self._dm569_adapter = DM569Adapter()
            
            # 连接信号
            self._dm569_adapter.video_completed.connect(self._on_video_url_ready)
            self._dm569_adapter.video_failed.connect(self._on_video_url_failed)
            
            print("[AnimeDownloadTask] DM569适配器设置完成")
            
        except Exception as e:
            print(f"[AnimeDownloadTask] 设置DM569适配器失败: {e}")
    
    def start_download(self, anime: Anime, episode: Episode, line: int = 0):
        """开始下载任务"""
        try:
            # 生成任务ID
            task_id = f"anime_{anime.id}_{line}_{episode.ep}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            self._current_task = {
                'task_id': task_id,
                'anime': anime,
                'episode': episode,
                'line': line,
                'status': 'started'
            }
            
            print(f"[AnimeDownloadTask] 开始下载任务: {task_id}")
            print(f"[AnimeDownloadTask] 动漫: {anime.name}")
            print(f"[AnimeDownloadTask] 剧集: {episode.name} (第{episode.ep}集)")
            print(f"[AnimeDownloadTask] 线路: {line}")
            
            self.task_started.emit(task_id)
            
            # 开始URL提取
            self._start_url_extraction()
            
        except Exception as e:
            error_msg = f"启动下载任务失败: {str(e)}"
            print(f"[AnimeDownloadTask] {error_msg}")
            import traceback
            traceback.print_exc()
            
            if self._current_task:
                self.task_failed.emit(self._current_task['task_id'], error_msg)
            else:
                self.task_failed.emit("unknown", error_msg)
    
    def _start_url_extraction(self):
        """开始URL提取"""
        try:
            if not self._current_task:
                return
            
            task_id = self._current_task['task_id']
            anime = self._current_task['anime']
            episode = self._current_task['episode']
            line = self._current_task['line']
            
            print(f"[AnimeDownloadTask] 开始URL提取: {task_id}")
            self.url_extraction_started.emit(task_id)
            
            # 更新任务状态
            self._current_task['status'] = 'extracting_url'
            
            # 请求视频URL
            if self._dm569_adapter:
                self._dm569_adapter.get_video_url(str(anime.id), line, episode.ep - 1)  # episode.ep是1-based，需要转换为0-based
            else:
                self._on_video_url_failed("DM569适配器未初始化")
                
        except Exception as e:
            error_msg = f"URL提取失败: {str(e)}"
            print(f"[AnimeDownloadTask] {error_msg}")
            import traceback
            traceback.print_exc()
            
            if self._current_task:
                self.url_extraction_failed.emit(self._current_task['task_id'], error_msg)
                self.task_failed.emit(self._current_task['task_id'], error_msg)
    
    def _on_video_url_ready(self, video_info: Dict[str, Any]):
        """处理视频URL准备完成"""
        try:
            if not self._current_task:
                return
            
            task_id = self._current_task['task_id']
            
            print(f"[AnimeDownloadTask] 收到视频URL: {task_id}")
            print(f"[AnimeDownloadTask] 视频信息: {video_info}")
            
            if not video_info.get('success'):
                error = video_info.get('error', '获取视频URL失败')
                print(f"[AnimeDownloadTask] 视频URL获取失败: {error}")
                self.url_extraction_failed.emit(task_id, error)
                self.task_failed.emit(task_id, error)
                return
            
            # 获取stream_url，优先使用real_m3u8对应的URL
            stream_url = video_info.get('stream_url', '')
            real_m3u8 = video_info.get('real_m3u8', '')
            
            if not stream_url:
                error = "视频URL为空"
                print(f"[AnimeDownloadTask] {error}")
                self.url_extraction_failed.emit(task_id, error)
                self.task_failed.emit(task_id, error)
                return
            
            # 检查是否获取到了有效的M3U8内容
            if real_m3u8 and '#EXT' in real_m3u8:
                print(f"[AnimeDownloadTask] ✓ 获取到有效的M3U8内容，长度: {len(real_m3u8)}")
            elif '<html' in real_m3u8.lower():
                error = "获取到的是HTML错误页面，不是有效的M3U8内容"
                print(f"[AnimeDownloadTask] {error}")
                self.url_extraction_failed.emit(task_id, error)
                self.task_failed.emit(task_id, error)
                return
            else:
                print(f"[AnimeDownloadTask] 警告: M3U8内容可能无效，长度: {len(real_m3u8)}")
            
            print(f"[AnimeDownloadTask] ✓ URL提取成功: {stream_url}")
            self.url_extraction_completed.emit(task_id, stream_url)
            
            # 更新任务状态
            self._current_task['status'] = 'downloading'
            self._current_task['stream_url'] = stream_url
            
            # 开始视频下载
            self._start_video_download(stream_url)
            
        except Exception as e:
            error_msg = f"处理视频URL时发生异常: {str(e)}"
            print(f"[AnimeDownloadTask] {error_msg}")
            import traceback
            traceback.print_exc()
            
            if self._current_task:
                self.url_extraction_failed.emit(self._current_task['task_id'], error_msg)
                self.task_failed.emit(self._current_task['task_id'], error_msg)
    
    def _on_video_url_failed(self, error: str):
        """处理视频URL获取失败"""
        try:
            if not self._current_task:
                return
            
            task_id = self._current_task['task_id']
            
            print(f"[AnimeDownloadTask] 视频URL获取失败: {task_id}, 错误: {error}")
            self.url_extraction_failed.emit(task_id, error)
            self.task_failed.emit(task_id, error)
            
        except Exception as e:
            print(f"[AnimeDownloadTask] 处理视频URL失败时发生异常: {e}")
    
    def _start_video_download(self, stream_url: str):
        """开始视频下载"""
        try:
            if not self._current_task:
                return
            
            task_id = self._current_task['task_id']
            anime = self._current_task['anime']
            episode = self._current_task['episode']
            
            print(f"[AnimeDownloadTask] 开始视频下载: {task_id}")
            print(f"[AnimeDownloadTask] Stream URL: {stream_url}")
            
            # 创建视频下载器
            if not self._video_downloader:
                self._video_downloader = VideoDownloader(self.download_base_path)
                
                # 连接信号
                self._video_downloader.download_started.connect(self._on_download_started)
                self._video_downloader.download_progress.connect(self._on_download_progress)
                self._video_downloader.download_completed.connect(self._on_download_completed)
                self._video_downloader.download_failed.connect(self._on_download_failed)
            
            # 检查FFmpeg可用性
            if not self._video_downloader.is_ffmpeg_available():
                error = f"FFmpeg不可用，路径: {self._video_downloader.ffmpeg_path}"
                print(f"[AnimeDownloadTask] {error}")
                self.download_failed.emit(task_id, error)
                self.task_failed.emit(task_id, error)
                return
            
            # 开始下载
            download_task_id = self._video_downloader.download_episode(anime, episode, stream_url)
            
            # 更新任务信息
            self._current_task['download_task_id'] = download_task_id
            
            print(f"[AnimeDownloadTask] 视频下载已启动: {download_task_id}")
            
        except Exception as e:
            error_msg = f"启动视频下载失败: {str(e)}"
            print(f"[AnimeDownloadTask] {error_msg}")
            import traceback
            traceback.print_exc()
            
            if self._current_task:
                self.download_failed.emit(self._current_task['task_id'], error_msg)
                self.task_failed.emit(self._current_task['task_id'], error_msg)
    
    def _on_download_started(self, download_task_id: str):
        """处理下载开始"""
        try:
            if not self._current_task or self._current_task.get('download_task_id') != download_task_id:
                return
            
            task_id = self._current_task['task_id']
            print(f"[AnimeDownloadTask] 下载已开始: {task_id}")
            self.download_started.emit(task_id)
            
        except Exception as e:
            print(f"[AnimeDownloadTask] 处理下载开始时发生异常: {e}")
    
    def _on_download_progress(self, download_task_id: str, current: int, total: int):
        """处理下载进度"""
        try:
            if not self._current_task or self._current_task.get('download_task_id') != download_task_id:
                return
            
            task_id = self._current_task['task_id']
            self.download_progress.emit(task_id, current, total)
            
        except Exception as e:
            print(f"[AnimeDownloadTask] 处理下载进度时发生异常: {e}")
    
    def _on_download_completed(self, download_task_id: str, output_path: str):
        """处理下载完成"""
        try:
            if not self._current_task or self._current_task.get('download_task_id') != download_task_id:
                return
            
            task_id = self._current_task['task_id']
            
            print(f"[AnimeDownloadTask] 下载完成: {task_id}")
            print(f"[AnimeDownloadTask] 输出文件: {output_path}")
            
            self.download_completed.emit(task_id, output_path)
            self.task_completed.emit(task_id)
            
            # 清理任务
            self._cleanup_task()
            
        except Exception as e:
            print(f"[AnimeDownloadTask] 处理下载完成时发生异常: {e}")
    
    def _on_download_failed(self, download_task_id: str, error: str):
        """处理下载失败"""
        try:
            if not self._current_task or self._current_task.get('download_task_id') != download_task_id:
                return
            
            task_id = self._current_task['task_id']
            
            print(f"[AnimeDownloadTask] 下载失败: {task_id}, 错误: {error}")
            
            self.download_failed.emit(task_id, error)
            self.task_failed.emit(task_id, error)
            
            # 清理任务
            self._cleanup_task()
            
        except Exception as e:
            print(f"[AnimeDownloadTask] 处理下载失败时发生异常: {e}")
    
    def _cleanup_task(self):
        """清理当前任务"""
        try:
            if self._current_task:
                print(f"[AnimeDownloadTask] 清理任务: {self._current_task['task_id']}")
                self._current_task = None
            
        except Exception as e:
            print(f"[AnimeDownloadTask] 清理任务时发生异常: {e}")
    
    def cancel_current_task(self):
        """取消当前任务"""
        try:
            if not self._current_task:
                return False
            
            task_id = self._current_task['task_id']
            print(f"[AnimeDownloadTask] 取消任务: {task_id}")
            
            # 如果有下载任务，取消它
            if self._video_downloader and 'download_task_id' in self._current_task:
                download_task_id = self._current_task['download_task_id']
                self._video_downloader.cancel_download(download_task_id)
            
            # 清理任务
            self._cleanup_task()
            
            return True
            
        except Exception as e:
            print(f"[AnimeDownloadTask] 取消任务时发生异常: {e}")
            return False
    
    def cleanup(self):
        """清理所有资源"""
        try:
            print("[AnimeDownloadTask] 开始清理资源")
            
            # 取消当前任务
            self.cancel_current_task()
            
            # 清理视频下载器
            if self._video_downloader:
                self._video_downloader.cleanup()
                self._video_downloader = None
            
            # 清理DM569适配器
            if self._dm569_adapter:
                self._dm569_adapter.cleanup()
                self._dm569_adapter = None
            
            print("[AnimeDownloadTask] 资源清理完成")
            
        except Exception as e:
            print(f"[AnimeDownloadTask] 清理资源时发生异常: {e}")


class AnimeDownloadManager(QObject):
    """动漫下载管理器"""
    
    # 信号定义
    task_started = Signal(str)  # task_id
    url_extraction_started = Signal(str)  # task_id
    url_extraction_completed = Signal(str, str)  # task_id, stream_url
    url_extraction_failed = Signal(str, str)  # task_id, error
    download_started = Signal(str)  # task_id
    download_progress = Signal(str, int, int)  # task_id, current, total
    download_completed = Signal(str, str)  # task_id, output_path
    download_failed = Signal(str, str)  # task_id, error
    task_completed = Signal(str)  # task_id
    task_failed = Signal(str, str)  # task_id, error
    
    def __init__(self, download_base_path: str):
        super().__init__()
        self.download_base_path = download_base_path
        self._active_tasks: Dict[str, QThread] = {}
        self._task_workers: Dict[str, AnimeDownloadTask] = {}
    
    def start_download(self, anime: Anime, episode: Episode, line: int = 0) -> str:
        """开始下载任务"""
        try:
            # 创建工作线程
            thread = QThread()
            worker = AnimeDownloadTask(self.download_base_path)
            worker.moveToThread(thread)
            
            # 连接信号
            worker.task_started.connect(self.task_started.emit)
            worker.url_extraction_started.connect(self.url_extraction_started.emit)
            worker.url_extraction_completed.connect(self.url_extraction_completed.emit)
            worker.url_extraction_failed.connect(self.url_extraction_failed.emit)
            worker.download_started.connect(self.download_started.emit)
            worker.download_progress.connect(self.download_progress.emit)
            worker.download_completed.connect(self.download_completed.emit)
            worker.download_failed.connect(self.download_failed.emit)
            worker.task_completed.connect(self._on_task_completed)
            worker.task_failed.connect(self._on_task_failed)
            
            # 启动线程
            thread.start()
            
            # 生成任务ID（临时的，真正的ID由worker生成）
            temp_task_id = f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # 存储引用
            self._active_tasks[temp_task_id] = thread
            self._task_workers[temp_task_id] = worker
            
            # 启动下载任务
            QTimer.singleShot(0, lambda: worker.start_download(anime, episode, line))
            
            print(f"[AnimeDownloadManager] 下载任务已提交: {temp_task_id}")
            return temp_task_id
            
        except Exception as e:
            error_msg = f"提交下载任务失败: {str(e)}"
            print(f"[AnimeDownloadManager] {error_msg}")
            import traceback
            traceback.print_exc()
            return ""
    
    def _on_task_completed(self, task_id: str):
        """处理任务完成"""
        try:
            print(f"[AnimeDownloadManager] 任务完成: {task_id}")
            self.task_completed.emit(task_id)
            self._cleanup_task(task_id)
            
        except Exception as e:
            print(f"[AnimeDownloadManager] 处理任务完成时发生异常: {e}")
    
    def _on_task_failed(self, task_id: str, error: str):
        """处理任务失败"""
        try:
            print(f"[AnimeDownloadManager] 任务失败: {task_id}, 错误: {error}")
            self.task_failed.emit(task_id, error)
            self._cleanup_task(task_id)
            
        except Exception as e:
            print(f"[AnimeDownloadManager] 处理任务失败时发生异常: {e}")
    
    def _cleanup_task(self, task_id: str):
        """清理任务"""
        try:
            # 查找对应的任务（可能task_id已经改变）
            worker_to_cleanup = None
            thread_to_cleanup = None
            key_to_remove = None
            
            for key, worker in self._task_workers.items():
                if hasattr(worker, '_current_task') and worker._current_task and worker._current_task.get('task_id') == task_id:
                    worker_to_cleanup = worker
                    thread_to_cleanup = self._active_tasks.get(key)
                    key_to_remove = key
                    break
            
            # 如果没找到，可能是临时ID
            if not worker_to_cleanup and task_id in self._task_workers:
                worker_to_cleanup = self._task_workers[task_id]
                thread_to_cleanup = self._active_tasks.get(task_id)
                key_to_remove = task_id
            
            if worker_to_cleanup:
                try:
                    worker_to_cleanup.cleanup()
                except Exception as e:
                    print(f"[AnimeDownloadManager] 清理worker失败: {e}")
            
            if thread_to_cleanup and thread_to_cleanup.isRunning():
                try:
                    thread_to_cleanup.quit()
                    if not thread_to_cleanup.wait(5000):
                        thread_to_cleanup.terminate()
                        thread_to_cleanup.wait(2000)
                except Exception as e:
                    print(f"[AnimeDownloadManager] 清理线程失败: {e}")
            
            if key_to_remove:
                try:
                    if key_to_remove in self._task_workers:
                        del self._task_workers[key_to_remove]
                    if key_to_remove in self._active_tasks:
                        del self._active_tasks[key_to_remove]
                except Exception as e:
                    print(f"[AnimeDownloadManager] 清理引用失败: {e}")
            
            print(f"[AnimeDownloadManager] 任务清理完成: {task_id}")
            
        except Exception as e:
            print(f"[AnimeDownloadManager] 清理任务时发生异常: {e}")
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        try:
            # 查找对应的worker
            for key, worker in self._task_workers.items():
                if hasattr(worker, '_current_task') and worker._current_task and worker._current_task.get('task_id') == task_id:
                    return worker.cancel_current_task()
            
            return False
            
        except Exception as e:
            print(f"[AnimeDownloadManager] 取消任务时发生异常: {e}")
            return False
    
    def cleanup(self):
        """清理所有任务"""
        try:
            print("[AnimeDownloadManager] 开始清理所有任务")
            
            # 复制任务列表，避免在迭代时修改
            task_keys = list(self._task_workers.keys())
            
            for key in task_keys:
                try:
                    worker = self._task_workers.get(key)
                    if worker and hasattr(worker, '_current_task') and worker._current_task:
                        task_id = worker._current_task.get('task_id', key)
                        self._cleanup_task(task_id)
                    else:
                        self._cleanup_task(key)
                except Exception as e:
                    print(f"[AnimeDownloadManager] 清理任务失败: {key}, 错误: {e}")
            
            # 强制清理所有引用
            self._active_tasks.clear()
            self._task_workers.clear()
            
            print("[AnimeDownloadManager] 所有任务清理完成")
            
        except Exception as e:
            print(f"[AnimeDownloadManager] 清理所有任务时发生异常: {e}")