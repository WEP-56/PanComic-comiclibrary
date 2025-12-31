"""
视频下载器 - 已禁用
基于FFmpeg的M3U8到MP4转换下载器

注意：动漫下载功能已被移除，此文件已禁用。
如需重新启用，请移除此注释并恢复相关功能。
"""

# 动漫下载功能已移除 - 此文件已禁用
# 如需重新启用，请移除此注释

"""
import os
import json
import subprocess
import threading
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from datetime import datetime

from PySide6.QtCore import QObject, Signal, QThread, QTimer
from PySide6.QtWidgets import QApplication

from pancomic.models.anime import Anime
from pancomic.models.episode import Episode


class VideoDownloadWorker(QObject):
    """视频下载工作线程"""
    
    progress_updated = Signal(str, int, int)  # task_id, current_percent, total_percent
    download_completed = Signal(str, str)  # task_id, output_path
    download_failed = Signal(str, str)  # task_id, error_message
    
    def __init__(self, ffmpeg_path: str):
        super().__init__()
        self.ffmpeg_path = ffmpeg_path
        self._should_stop = False
        self._current_process = None
    
    def __del__(self):
        """析构函数，确保进程被清理"""
        try:
            self.stop()
        except Exception as e:
            print(f"[VideoDownloadWorker] 析构函数清理失败: {e}")
    
    def stop(self):
        """停止下载"""
        try:
            print("[VideoDownloadWorker] 停止下载请求")
            self._should_stop = True
            
            # 终止当前进程
            if self._current_process and self._current_process.poll() is None:
                print("[VideoDownloadWorker] 终止FFmpeg进程")
                try:
                    self._current_process.terminate()
                    # 等待进程结束
                    try:
                        self._current_process.wait(timeout=5)
                        print("[VideoDownloadWorker] FFmpeg进程正常终止")
                    except subprocess.TimeoutExpired:
                        print("[VideoDownloadWorker] FFmpeg进程超时，强制杀死")
                        self._current_process.kill()
                        self._current_process.wait(timeout=2)
                except Exception as e:
                    print(f"[VideoDownloadWorker] 终止进程失败: {e}")
                finally:
                    self._current_process = None
        except Exception as e:
            print(f"[VideoDownloadWorker] 停止下载时发生异常: {e}")
    
    def download_video(self, task_id: str, m3u8_url: str, output_path: str, headers: Dict[str, str] = None):
        """下载M3U8视频并转换为MP4"""
        process = None
        try:
            print(f"[VideoDownloader] 开始下载任务: {task_id}")
            print(f"[VideoDownloader] M3U8 URL: {m3u8_url}")
            print(f"[VideoDownloader] 输出路径: {output_path}")
            
            # 确保输出目录存在
            try:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
            except Exception as e:
                raise Exception(f"创建输出目录失败: {e}")
            
            # 验证FFmpeg路径
            if not os.path.exists(self.ffmpeg_path):
                raise Exception(f"FFmpeg可执行文件不存在: {self.ffmpeg_path}")
            
            # 构造FFmpeg命令
            cmd = [
                self.ffmpeg_path,
                '-i', m3u8_url,
                '-c', 'copy',  # 直接流复制，不重新编码
                '-bsf:a', 'aac_adtstoasc',  # 修复音频流
                '-y',  # 覆盖输出文件
                '-loglevel', 'info',  # 设置日志级别
                output_path
            ]
            
            # 添加防盗链头部（如果有）
            if headers:
                header_str = ""
                for key, value in headers.items():
                    header_str += f"{key}: {value}\r\n"
                if header_str:
                    cmd.insert(1, '-headers')
                    cmd.insert(2, header_str.rstrip())
            
            print(f"[VideoDownloader] FFmpeg命令: {' '.join(cmd)}")
            
            # 执行FFmpeg命令
            try:
                self._current_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    universal_newlines=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                process = self._current_process  # 保持向后兼容
            except Exception as e:
                raise Exception(f"启动FFmpeg进程失败: {e}")
            
            # 监控进度和输出
            stderr_lines = []
            try:
                while True:
                    if self._should_stop:
                        print(f"[VideoDownloader] 用户取消下载: {task_id}")
                        if process and process.poll() is None:
                            process.terminate()
                            try:
                                process.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                process.kill()
                        return
                    
                    # 检查进程是否结束
                    if process.poll() is not None:
                        break
                    
                    # 读取stderr输出
                    try:
                        output = process.stderr.readline()
                        if output:
                            stderr_lines.append(output.strip())
                            print(f"[VideoDownloader] FFmpeg输出: {output.strip()}")
                            
                            # 解析FFmpeg输出中的进度信息
                            if 'time=' in output:
                                try:
                                    # 简单的进度估算
                                    self.progress_updated.emit(task_id, 50, 100)
                                except Exception as progress_error:
                                    print(f"[VideoDownloader] 进度更新失败: {progress_error}")
                    except Exception as read_error:
                        print(f"[VideoDownloader] 读取FFmpeg输出失败: {read_error}")
                        break
                        
            except Exception as monitor_error:
                print(f"[VideoDownloader] 监控进程失败: {monitor_error}")
                raise Exception(f"监控下载进程失败: {monitor_error}")
            
            # 等待进程完成并获取返回码
            try:
                return_code = process.wait(timeout=30)  # 30秒超时
            except subprocess.TimeoutExpired:
                print(f"[VideoDownloader] 进程超时，强制终止: {task_id}")
                process.kill()
                raise Exception("下载进程超时")
            except Exception as wait_error:
                raise Exception(f"等待进程完成失败: {wait_error}")
            
            # 收集完整的stderr输出
            try:
                remaining_stderr = process.stderr.read()
                if remaining_stderr:
                    stderr_lines.extend(remaining_stderr.strip().split('\n'))
            except Exception as stderr_error:
                print(f"[VideoDownloader] 读取剩余stderr失败: {stderr_error}")
            
            stderr_output = '\n'.join(stderr_lines)
            
            # 检查下载结果
            if return_code == 0:
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    print(f"[VideoDownloader] 下载成功完成: {output_path}")
                    print(f"[VideoDownloader] 文件大小: {os.path.getsize(output_path)} bytes")
                    self.download_completed.emit(task_id, output_path)
                else:
                    error_msg = f"下载完成但输出文件无效: {output_path}"
                    print(f"[VideoDownloader] {error_msg}")
                    self.download_failed.emit(task_id, error_msg)
            else:
                error_msg = f"FFmpeg执行失败 (返回码: {return_code})\nFFmpeg输出:\n{stderr_output}"
                print(f"[VideoDownloader] {error_msg}")
                self.download_failed.emit(task_id, error_msg)
                
        except Exception as e:
            error_msg = f"下载过程异常: {str(e)}"
            print(f"[VideoDownloader] {error_msg}")
            import traceback
            traceback.print_exc()
            
            # 确保进程被清理
            if process and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except:
                    try:
                        process.kill()
                    except:
                        pass
            
            # 清理进程引用
            self._current_process = None
            
            self.download_failed.emit(task_id, error_msg)
        
        finally:
            # 最终清理
            if process:
                try:
                    if process.poll() is None:
                        process.terminate()
                        process.wait(timeout=3)
                except:
                    try:
                        process.kill()
                    except:
                        pass
            
            # 清理进程引用
            self._current_process = None
    
    def stop(self):
        """停止下载"""
        self._should_stop = True


class VideoDownloader(QObject):
    """
    视频下载管理器
    
    功能：
    1. 使用本地FFmpeg下载M3U8视频
    2. 生成视频元数据文件
    3. 管理下载任务
    4. 支持下载进度监控
    """
    
    # 信号定义
    download_started = Signal(str)  # task_id
    download_progress = Signal(str, int, int)  # task_id, current, total
    download_completed = Signal(str, str)  # task_id, output_path
    download_failed = Signal(str, str)  # task_id, error
    
    def __init__(self, download_base_path: str):
        super().__init__()
        self.download_base_path = Path(download_base_path)
        self.anime_download_path = self.download_base_path / "anime"
        self.anime_download_path.mkdir(parents=True, exist_ok=True)
        
        # FFmpeg路径设置
        self.ffmpeg_path = self._get_ffmpeg_path()
        
        # 下载任务管理
        self._active_downloads: Dict[str, QThread] = {}
        self._download_workers: Dict[str, VideoDownloadWorker] = {}
        
        print(f"[VideoDownloader] 初始化完成，FFmpeg路径: {self.ffmpeg_path}")
    
    def __del__(self):
        """析构函数，确保资源清理"""
        try:
            print("[VideoDownloader] 析构函数调用，清理资源")
            self.cleanup()
        except Exception as e:
            print(f"[VideoDownloader] 析构函数清理失败: {e}")
    
    def _get_ffmpeg_path(self) -> str:
        """获取FFmpeg可执行文件路径"""
        # 项目根目录
        project_root = Path(__file__).parent.parent.parent
        
        # Windows平台
        if os.name == 'nt':
            # 正确的FFmpeg路径：pancomic/ffmpeg/bin/ffmpeg.exe
            ffmpeg_exe = project_root / "pancomic" / "ffmpeg" / "bin" / "ffmpeg.exe"
            if ffmpeg_exe.exists():
                return str(ffmpeg_exe)
            
            # 备选：检查系统PATH
            try:
                result = subprocess.run(['where', 'ffmpeg'], capture_output=True, text=True)
                if result.returncode == 0:
                    return result.stdout.strip().split('\n')[0]
            except:
                pass
        else:
            # Linux/macOS平台
            ffmpeg_bin = project_root / "pancomic" / "ffmpeg" / "bin" / "ffmpeg"
            if ffmpeg_bin.exists():
                return str(ffmpeg_bin)
            
            # 备选：检查系统PATH
            try:
                result = subprocess.run(['which', 'ffmpeg'], capture_output=True, text=True)
                if result.returncode == 0:
                    return result.stdout.strip()
            except:
                pass
        
        # 如果都找不到，返回默认值（会在使用时报错）
        return "ffmpeg"
    
    def is_ffmpeg_available(self) -> bool:
        """检查FFmpeg是否可用"""
        try:
            result = subprocess.run(
                [self.ffmpeg_path, '-version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def download_episode(
        self,
        anime: Anime,
        episode: Episode,
        m3u8_url: str,
        progress_callback: Optional[Callable] = None
    ) -> str:
        """
        下载单集视频
        
        Args:
            anime: 动漫信息
            episode: 剧集信息
            m3u8_url: M3U8流地址
            progress_callback: 进度回调函数
            
        Returns:
            任务ID
        """
        task_id = None
        try:
            # 生成任务ID
            task_id = f"{anime.id}_{episode.line}_{episode.ep}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            print(f"[VideoDownloader] 准备下载任务: {task_id}")
            print(f"[VideoDownloader] 动漫: {anime.name}")
            print(f"[VideoDownloader] 剧集: {episode.name} (第{episode.ep}集)")
            print(f"[VideoDownloader] M3U8 URL: {m3u8_url}")
            
            # 验证输入参数
            if not anime or not episode or not m3u8_url:
                raise ValueError("缺少必要的下载参数")
            
            if not m3u8_url.startswith(('http://', 'https://')):
                raise ValueError(f"无效的M3U8 URL: {m3u8_url}")
            
            # 创建动漫目录
            try:
                anime_dir = self.anime_download_path / self._sanitize_filename(anime.name)
                anime_dir.mkdir(parents=True, exist_ok=True)
                print(f"[VideoDownloader] 动漫目录: {anime_dir}")
            except Exception as e:
                raise Exception(f"创建动漫目录失败: {e}")
            
            # 生成输出文件名
            try:
                episode_filename = f"{self._sanitize_filename(episode.name)}.mp4"
                output_path = anime_dir / episode_filename
                print(f"[VideoDownloader] 输出文件: {output_path}")
            except Exception as e:
                raise Exception(f"生成输出文件名失败: {e}")
            
            # 检查FFmpeg是否可用
            if not self.is_ffmpeg_available():
                error_msg = f"FFmpeg不可用，路径: {self.ffmpeg_path}"
                print(f"[VideoDownloader] {error_msg}")
                self.download_failed.emit(task_id, error_msg)
                return task_id
            
            # 创建下载工作线程
            try:
                thread = QThread()
                worker = VideoDownloadWorker(self.ffmpeg_path)
                worker.moveToThread(thread)
                
                # 连接信号
                worker.progress_updated.connect(self.download_progress.emit)
                worker.download_completed.connect(self._on_download_completed)
                worker.download_failed.connect(self._on_download_failed)
                
                # 存储引用
                self._active_downloads[task_id] = thread
                self._download_workers[task_id] = worker
                
                print(f"[VideoDownloader] 创建工作线程成功: {task_id}")
                
            except Exception as e:
                raise Exception(f"创建下载线程失败: {e}")
            
            # 生成元数据
            try:
                self._create_episode_metadata(anime, episode, anime_dir, episode_filename, task_id)
                print(f"[VideoDownloader] 元数据创建成功: {task_id}")
            except Exception as e:
                print(f"[VideoDownloader] 元数据创建失败: {e}")
                # 元数据创建失败不应该阻止下载
            
            # 启动下载
            try:
                thread.started.connect(
                    lambda: worker.download_video(task_id, m3u8_url, str(output_path))
                )
                thread.start()
                
                self.download_started.emit(task_id)
                print(f"[VideoDownloader] 下载任务启动成功: {task_id}")
                
            except Exception as e:
                # 清理已创建的资源
                self._cleanup_task(task_id)
                raise Exception(f"启动下载任务失败: {e}")
            
            return task_id
            
        except Exception as e:
            error_msg = f"准备下载任务失败: {str(e)}"
            print(f"[VideoDownloader] {error_msg}")
            import traceback
            traceback.print_exc()
            
            if task_id:
                self.download_failed.emit(task_id, error_msg)
                # 清理可能已创建的资源
                self._cleanup_task(task_id)
            
            return task_id or f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    def _on_download_completed(self, task_id: str, output_path: str):
        """处理下载完成"""
        try:
            print(f"[VideoDownloader] 任务完成: {task_id}")
            print(f"[VideoDownloader] 输出文件: {output_path}")
            
            # 验证输出文件
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                print(f"[VideoDownloader] 文件大小: {file_size} bytes")
                
                if file_size == 0:
                    print(f"[VideoDownloader] 警告: 输出文件为空: {output_path}")
            else:
                print(f"[VideoDownloader] 警告: 输出文件不存在: {output_path}")
            
            # 更新元数据
            try:
                self._update_episode_metadata(task_id, output_path, True)
                print(f"[VideoDownloader] 元数据更新成功: {task_id}")
            except Exception as e:
                print(f"[VideoDownloader] 元数据更新失败: {e}")
                # 元数据更新失败不应该影响下载完成状态
            
            # 清理线程
            try:
                self._cleanup_task(task_id)
                print(f"[VideoDownloader] 任务清理成功: {task_id}")
            except Exception as e:
                print(f"[VideoDownloader] 任务清理失败: {e}")
            
            # 发送完成信号
            self.download_completed.emit(task_id, output_path)
            
        except Exception as e:
            print(f"[VideoDownloader] 处理下载完成时发生异常: {e}")
            import traceback
            traceback.print_exc()
            
            # 如果处理完成时出错，转为失败处理
            self._on_download_failed(task_id, f"处理下载完成时发生异常: {str(e)}")
    
    def _on_download_failed(self, task_id: str, error: str):
        """处理下载失败"""
        try:
            print(f"[VideoDownloader] 任务失败: {task_id}")
            print(f"[VideoDownloader] 错误信息: {error}")
            
            # 更新元数据
            try:
                self._update_episode_metadata(task_id, "", False, error)
                print(f"[VideoDownloader] 失败元数据更新成功: {task_id}")
            except Exception as e:
                print(f"[VideoDownloader] 失败元数据更新失败: {e}")
            
            # 清理线程
            try:
                self._cleanup_task(task_id)
                print(f"[VideoDownloader] 失败任务清理成功: {task_id}")
            except Exception as e:
                print(f"[VideoDownloader] 失败任务清理失败: {e}")
            
            # 发送失败信号
            self.download_failed.emit(task_id, error)
            
        except Exception as e:
            print(f"[VideoDownloader] 处理下载失败时发生异常: {e}")
            import traceback
            traceback.print_exc()
            
            # 确保失败信号被发送
            try:
                self.download_failed.emit(task_id, f"处理下载失败时发生异常: {str(e)}")
            except:
                pass
    
    def _cleanup_task(self, task_id: str):
        """清理下载任务"""
        try:
            print(f"[VideoDownloader] 开始清理任务: {task_id}")
            
            # 停止工作线程
            if task_id in self._download_workers:
                try:
                    worker = self._download_workers[task_id]
                    worker.stop()
                    print(f"[VideoDownloader] 工作线程停止信号发送: {task_id}")
                except Exception as e:
                    print(f"[VideoDownloader] 停止工作线程失败: {e}")
            
            # 清理线程
            if task_id in self._active_downloads:
                try:
                    thread = self._active_downloads[task_id]
                    if thread.isRunning():
                        print(f"[VideoDownloader] 等待线程结束: {task_id}")
                        thread.quit()
                        if not thread.wait(5000):  # 等待5秒
                            print(f"[VideoDownloader] 线程未正常结束，强制终止: {task_id}")
                            thread.terminate()
                            thread.wait(2000)  # 再等待2秒
                    
                    del self._active_downloads[task_id]
                    print(f"[VideoDownloader] 线程清理完成: {task_id}")
                except Exception as e:
                    print(f"[VideoDownloader] 清理线程失败: {e}")
                    # 即使清理失败，也要从字典中移除
                    try:
                        del self._active_downloads[task_id]
                    except:
                        pass
            
            # 清理工作线程引用
            if task_id in self._download_workers:
                try:
                    del self._download_workers[task_id]
                    print(f"[VideoDownloader] 工作线程引用清理完成: {task_id}")
                except Exception as e:
                    print(f"[VideoDownloader] 清理工作线程引用失败: {e}")
            
            print(f"[VideoDownloader] 任务清理完成: {task_id}")
            
        except Exception as e:
            print(f"[VideoDownloader] 清理任务时发生异常: {e}")
            import traceback
            traceback.print_exc()
            
            # 强制清理字典引用
            try:
                if task_id in self._active_downloads:
                    del self._active_downloads[task_id]
                if task_id in self._download_workers:
                    del self._download_workers[task_id]
            except:
                pass
    
    def cancel_download(self, task_id: str) -> bool:
        """取消下载任务"""
        try:
            print(f"[VideoDownloader] 取消下载任务: {task_id}")
            
            success = False
            
            # 停止工作线程
            if task_id in self._download_workers:
                try:
                    worker = self._download_workers[task_id]
                    worker.stop()
                    print(f"[VideoDownloader] 工作线程停止信号已发送: {task_id}")
                    success = True
                except Exception as e:
                    print(f"[VideoDownloader] 停止工作线程失败: {e}")
            
            # 清理任务
            self._cleanup_task(task_id)
            
            return success
            
        except Exception as e:
            print(f"[VideoDownloader] 取消下载任务时发生异常: {e}")
            import traceback
            traceback.print_exc()
            
            # 强制清理
            try:
                self._cleanup_task(task_id)
            except:
                pass
            
            return False
    
    def _create_episode_metadata(
        self,
        anime: Anime,
        episode: Episode,
        anime_dir: Path,
        episode_filename: str,
        task_id: str
    ):
        """创建剧集元数据文件"""
        # 创建或更新动漫级别的元数据
        anime_metadata_file = anime_dir / "anime_metadata.json"
        
        # 动漫基本信息
        anime_metadata = {
            "anime": {
                "id": anime.id,
                "name": anime.name,
                "source": anime.source,
                "cover_url": anime.cover_url,
                "summary": anime.summary,
                "tags": anime.tags,
                "year": anime.year,
                "area": anime.area,
                "bangumi_url": getattr(anime, 'bangumi_url', ''),
                "alias": getattr(anime, 'alias', ''),
                "created_time": datetime.now().isoformat(),
                "updated_time": datetime.now().isoformat()
            },
            "episodes": {}
        }
        
        # 如果动漫元数据文件已存在，加载现有数据
        if anime_metadata_file.exists():
            try:
                with open(anime_metadata_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                    anime_metadata["episodes"] = existing_data.get("episodes", {})
                    # 保留创建时间，更新修改时间
                    anime_metadata["anime"]["created_time"] = existing_data.get("anime", {}).get("created_time", anime_metadata["anime"]["created_time"])
            except Exception as e:
                print(f"[VideoDownloader] 读取现有动漫元数据失败: {e}")
        
        # 添加或更新当前剧集信息
        episode_key = f"line_{episode.line}_ep_{episode.ep}"
        anime_metadata["episodes"][episode_key] = {
            "index": episode.index,
            "name": episode.name,
            "line": episode.line,
            "ep": episode.ep,
            "filename": episode_filename,
            "download_time": datetime.now().isoformat(),
            "task_id": task_id,
            "is_downloaded": False,
            "download_path": "",
            "file_size": 0,
            "duration": "",
            "quality": ""
        }
        
        # 保存动漫元数据文件
        with open(anime_metadata_file, 'w', encoding='utf-8') as f:
            json.dump(anime_metadata, f, ensure_ascii=False, indent=2)
        
        # 同时创建单集元数据文件（向后兼容）
        episode_metadata = {
            "anime": anime_metadata["anime"],
            "episode": anime_metadata["episodes"][episode_key]
        }
        
        episode_metadata_file = anime_dir / f"{episode_filename}.metadata.json"
        with open(episode_metadata_file, 'w', encoding='utf-8') as f:
            json.dump(episode_metadata, f, ensure_ascii=False, indent=2)
    
    def _update_episode_metadata(
        self,
        task_id: str,
        output_path: str,
        success: bool,
        error: str = ""
    ):
        """更新剧集元数据"""
        # 查找对应的动漫元数据文件
        for anime_metadata_file in self.anime_download_path.rglob("anime_metadata.json"):
            try:
                with open(anime_metadata_file, 'r', encoding='utf-8') as f:
                    anime_metadata = json.load(f)
                
                # 查找对应的剧集
                episodes = anime_metadata.get("episodes", {})
                target_episode_key = None
                
                for episode_key, episode_data in episodes.items():
                    if episode_data.get("task_id") == task_id:
                        target_episode_key = episode_key
                        break
                
                if target_episode_key:
                    # 更新剧集元数据
                    episode_data = episodes[target_episode_key]
                    episode_data["is_downloaded"] = success
                    episode_data["download_path"] = output_path if success else ""
                    episode_data["completed_time"] = datetime.now().isoformat()
                    
                    if success and os.path.exists(output_path):
                        # 获取文件大小
                        episode_data["file_size"] = os.path.getsize(output_path)
                    
                    if not success:
                        episode_data["error"] = error
                    
                    # 更新动漫的修改时间
                    anime_metadata["anime"]["updated_time"] = datetime.now().isoformat()
                    
                    # 保存更新后的动漫元数据
                    with open(anime_metadata_file, 'w', encoding='utf-8') as f:
                        json.dump(anime_metadata, f, ensure_ascii=False, indent=2)
                    
                    # 同时更新单集元数据文件（向后兼容）
                    episode_metadata_pattern = anime_metadata_file.parent / f"*.metadata.json"
                    for episode_metadata_file in anime_metadata_file.parent.glob("*.metadata.json"):
                        if episode_metadata_file.name == "anime_metadata.json":
                            continue
                        
                        try:
                            with open(episode_metadata_file, 'r', encoding='utf-8') as f:
                                episode_metadata = json.load(f)
                            
                            if episode_metadata.get("episode", {}).get("task_id") == task_id:
                                episode_metadata["episode"] = episode_data
                                episode_metadata["anime"] = anime_metadata["anime"]
                                
                                with open(episode_metadata_file, 'w', encoding='utf-8') as f:
                                    json.dump(episode_metadata, f, ensure_ascii=False, indent=2)
                                break
                        except Exception as e:
                            print(f"[VideoDownloader] 更新单集元数据失败: {e}")
                    
                    return
                    
            except Exception as e:
                print(f"[VideoDownloader] 更新动漫元数据失败: {e}")
        
        # 如果没找到动漫元数据文件，尝试更新单集元数据文件（向后兼容）
        for metadata_file in self.anime_download_path.rglob("*.metadata.json"):
            if metadata_file.name == "anime_metadata.json":
                continue
                
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                if metadata.get("episode", {}).get("task_id") == task_id:
                    # 更新元数据
                    metadata["episode"]["is_downloaded"] = success
                    metadata["episode"]["download_path"] = output_path if success else ""
                    metadata["episode"]["completed_time"] = datetime.now().isoformat()
                    
                    if not success:
                        metadata["episode"]["error"] = error
                    
                    # 保存更新后的元数据
                    with open(metadata_file, 'w', encoding='utf-8') as f:
                        json.dump(metadata, f, ensure_ascii=False, indent=2)
                    return
                    
            except Exception as e:
                print(f"[VideoDownloader] 更新单集元数据失败: {e}")
    
    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名，移除非法字符"""
        import re
        # 移除或替换非法字符
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # 移除前后空格
        filename = filename.strip()
        # 限制长度
        if len(filename) > 100:
            filename = filename[:100]
        return filename or "未知"
    
    def get_downloaded_episodes(self, anime_id: str = None) -> list:
        """获取已下载的剧集列表"""
        episodes = []
        
        for metadata_file in self.anime_download_path.rglob("*.metadata.json"):
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                episode_data = metadata.get("episode", {})
                if episode_data.get("is_downloaded"):
                    anime_data = metadata.get("anime", {})
                    
                    # 如果指定了anime_id，只返回匹配的
                    if anime_id and str(anime_data.get("id")) != str(anime_id):
                        continue
                    
                    episodes.append({
                        "anime": anime_data,
                        "episode": episode_data,
                        "metadata_file": str(metadata_file)
                    })
                    
            except Exception as e:
                print(f"[VideoDownloader] 读取元数据失败: {e}")
        
        return episodes
    
    def cleanup(self):
        """清理所有下载任务"""
        print("[VideoDownloader] 开始清理所有下载任务")
        
        # 复制任务ID列表，避免在迭代时修改字典
        task_ids = list(self._active_downloads.keys())
        
        for task_id in task_ids:
            try:
                print(f"[VideoDownloader] 清理任务: {task_id}")
                self.cancel_download(task_id)
            except Exception as e:
                print(f"[VideoDownloader] 清理任务失败: {task_id}, 错误: {e}")
        
        # 强制清理所有引用
        self._active_downloads.clear()
        self._download_workers.clear()
        
        print("[VideoDownloader] 所有下载任务清理完成")