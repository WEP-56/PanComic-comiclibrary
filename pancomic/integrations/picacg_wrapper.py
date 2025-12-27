"""
PicACG-qt Integration Wrapper

This module provides a direct integration with the original PicACG-qt project,
using it as a method library rather than rewriting the entire adapter.
"""

import sys
import os
import threading
from typing import Dict, Any, List, Optional, Callable
from PySide6.QtCore import QObject, Signal, QTimer
from concurrent.futures import ThreadPoolExecutor

# Import time and uuid with different names to avoid conflicts
import time as time_module
import uuid as uuid_module


class PicACGWrapper(QObject):
    """
    Wrapper for original PicACG-qt functionality.
    
    This class provides a clean interface to the original PicACG-qt project
    while maintaining thread safety and Qt signal integration.
    """
    
    # Signals for UI integration
    login_completed = Signal(bool, str)  # success, message
    login_failed = Signal(str)  # error message
    search_completed = Signal(list)  # comics list
    search_failed = Signal(str)  # error message
    chapters_completed = Signal(list)  # chapters list
    chapters_failed = Signal(str)  # error message
    images_completed = Signal(list)  # image URLs list
    images_failed = Signal(str)  # error message
    
    # Endpoint and server management signals
    endpoint_test_completed = Signal(dict)  # {endpoint: response_time}
    endpoint_changed = Signal(str)  # new_endpoint
    image_server_test_completed = Signal(dict)  # {server: response_time}
    image_server_changed = Signal(str)  # new_server
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize PicACG wrapper.
        
        Args:
            config: Configuration dictionary
        """
        super().__init__()
        
        self.config = config
        self._is_initialized = False
        self._is_logged_in = False
        
        # Original PicACG-qt modules (will be loaded on initialization)
        self._server = None
        self._user = None
        self._req_module = None
        self._res_module = None
        self._picacg_config = None
        self._setting = None
        self._status = None
        
        # Thread pool for background operations
        self._thread_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="PicACGWrapper")
        
        # API endpoints and image servers
        self._api_endpoints = [
            'https://picaapi.picacomic.com',     # 官方主API
            'https://bika-api.jpacg.cc',        # JP反代分流
            'https://188.114.98.153',           # IP直连分流
            'https://bika2-api.jpacg.cc',       # US反代分流
            'https://104.21.91.145',            # IP直连分流2
        ]
        
        self._image_servers = [
            'storage.diwodiwo.xyz',            # 图片分流2 (Diwo)
            's3.picacomic.com',                # 图片分流1 (S3)
            's2.picacomic.com',                # 图片分流3 (S2)
            'storage1.picacomic.com',          # 图片分流4 (Storage1)
            'storage-b.picacomic.com',         # 图片分流5 (Storage-B)
        ]
        
        # Current selections
        self._current_endpoint = self.config.get('endpoint', self._api_endpoints[0])
        self._current_image_server = self.config.get('image_server', self._image_servers[0])
        
        # Speed test results
        self._speed_test_results = {}
        self._image_speed_test_results = {}
    
    def initialize(self) -> bool:
        """
        Initialize the original PicACG-qt modules.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Add PicACG-qt source path to sys.path
            picacg_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'forapi', 'picacg', 'src'
            )
            
            if not os.path.exists(picacg_path):
                print(f"❌ PicACG-qt源码路径不存在: {picacg_path}")
                return False
            
            if picacg_path not in sys.path:
                sys.path.insert(0, picacg_path)
                print(f"✅ 添加PicACG-qt路径: {picacg_path}")
            
            # Import original PicACG modules
            from server.server import Server, Task
            from tools.user import User
            import server.req as req
            import server.res as res
            from config import config as picacg_config
            from config.setting import Setting
            from tools.status import Status
            
            # Initialize modules
            self._server = Server()
            self._user = User()
            self._req_module = req
            self._res_module = res
            self._picacg_config = picacg_config
            self._setting = Setting
            self._status = Status
            self._task_class = Task
            
            # Configure settings
            self._configure_settings()
            
            self._is_initialized = True
            print("✅ PicACG-qt模块初始化成功")
            return True
            
        except Exception as e:
            print(f"❌ PicACG-qt模块初始化失败: {e}")
            return False
    
    def _configure_settings(self) -> None:
        """Configure PicACG settings from config."""
        try:
            # Set API endpoint
            if self._current_endpoint.endswith('/'):
                self._picacg_config.Url = self._current_endpoint
            else:
                self._picacg_config.Url = self._current_endpoint + '/'
            
            # Set image server
            self._picacg_config.ImageUrl = f"https://{self._current_image_server}"
            
            # Set image quality
            image_quality = self.config.get('image_quality', 'original')
            self._picacg_config.ImageQuality = image_quality
            
            # Configure proxy if enabled
            if 'proxy' in self.config and self.config['proxy'].get('enabled'):
                proxy_config = self.config['proxy']
                if proxy_config.get('type') == 'http':
                    self._setting.IsHttpProxy.SetValue(1)
                    self._setting.HttpProxy.SetValue(proxy_config.get('url', ''))
                elif proxy_config.get('type') == 'socks5':
                    self._setting.IsHttpProxy.SetValue(2)
                    self._setting.Sock5Proxy.SetValue(proxy_config.get('url', ''))
                
                # Update proxy settings
                self._server.UpdateProxy()
            
            print(f"🔧 PicACG配置完成:")
            print(f"  API服务器: {self._current_endpoint}")
            print(f"  图片服务器: {self._current_image_server}")
            print(f"  图片质量: {image_quality}")
            
        except Exception as e:
            print(f"⚠️ PicACG配置失败: {e}")
    
    def is_initialized(self) -> bool:
        """Check if wrapper is initialized."""
        return self._is_initialized
    
    def is_logged_in(self) -> bool:
        """Check if user is logged in."""
        return self._is_logged_in and self._user and self._user.isLogin
    
    def login(self, email: str, password: str) -> None:
        """
        Login to PicACG.
        
        Args:
            email: User email
            password: User password
        """
        if not self._is_initialized:
            self.login_failed.emit("Wrapper not initialized")
            return
        
        def login_worker():
            try:
                self._do_login(email, password)
            except Exception as e:
                self.login_failed.emit(f"Login failed: {str(e)}")
        
        self._thread_pool.submit(login_worker)
    
    def _do_login(self, email: str, password: str) -> None:
        """Internal login method using original PicACG-qt with automatic failover."""
        # Try each endpoint until one works
        endpoints_to_try = [self._current_endpoint] + [
            ep for ep in self._api_endpoints if ep != self._current_endpoint
        ]
        
        for attempt, endpoint in enumerate(endpoints_to_try, 1):
            try:
                print(f"🔐 尝试登录 (端点 {attempt}/{len(endpoints_to_try)}): {endpoint}")
                
                # Temporarily switch endpoint
                old_endpoint = self._current_endpoint
                self._current_endpoint = endpoint
                
                # Update PicACG config
                if self._picacg_config:
                    if endpoint.endswith('/'):
                        self._picacg_config.Url = endpoint
                    else:
                        self._picacg_config.Url = endpoint + '/'
                
                # Create login request using original PicACG-qt
                # Note: LoginReq expects 'user' and 'passwd' parameters
                login_req = self._req_module.LoginReq(email, password)
                
                # Send login request
                task = self._server._Send(self._task_class(login_req), 0)
                
                # Check if task has status attribute and if it's Ok
                if hasattr(task, 'status') and task.status == self._status.Ok:
                    # Process login response - LoginBack returns (status, token)
                    status, token = self._user.LoginBack(task)
                    
                    if status == self._status.Ok and self._user.isLogin:
                        self._is_logged_in = True
                        
                        # Store credentials for auto-login
                        self.config['credentials'] = {
                            'email': email,
                            'password': password
                        }
                        
                        # Get user info
                        self._get_user_info()
                        
                        self.login_completed.emit(True, "Login successful")
                        print(f"✅ PicACG登录成功: {email}")
                        print(f"   使用端点: {endpoint}")
                        return
                    else:
                        print(f"   ⚠️ 端点 {endpoint} 返回错误: {status}")
                else:
                    print(f"   ⚠️ 端点 {endpoint} 请求失败")
                    
            except Exception as e:
                error_str = str(e)
                if 'timed out' in error_str or 'ConnectTimeout' in error_str:
                    print(f"   ⏱️ 端点 {endpoint} 超时")
                elif 'Connection' in error_str:
                    print(f"   🔌 端点 {endpoint} 连接失败")
                else:
                    print(f"   ❌ 端点 {endpoint} 错误: {error_str[:50]}")
                
                # Restore old endpoint for next attempt
                self._current_endpoint = old_endpoint
                continue
        
        # All endpoints failed
        error_msg = "Login failed - all endpoints failed"
        self.login_completed.emit(False, error_msg)
        print(f"❌ PicACG登录失败: {error_msg}")
        print(f"   已尝试所有 {len(endpoints_to_try)} 个端点")
        print(f"   建议: 检查网络连接或尝试使用VPN")
    
    def _get_user_info(self) -> None:
        """Get user information after login."""
        try:
            user_info_req = self._req_module.GetUserInfo()
            task = self._server._Send(self._task_class(user_info_req), 0)
            
            if hasattr(task, 'status') and task.status == self._status.Ok:
                self._user.UpdateUserInfoBack(task)
                print(f"✅ 获取用户信息成功")
            else:
                print(f"⚠️ 获取用户信息失败")
                
        except Exception as e:
            print(f"⚠️ 获取用户信息异常: {e}")
    
    def search(self, keyword: str, page: int = 1) -> None:
        """
        Search comics using original PicACG-qt.
        
        Args:
            keyword: Search keyword
            page: Page number
        """
        if not self._is_initialized:
            self.search_failed.emit("Wrapper not initialized")
            return
        
        if not self.is_logged_in():
            self.search_failed.emit("Please login first")
            return
        
        def search_worker():
            try:
                self._do_search(keyword, page)
            except Exception as e:
                self.search_failed.emit(f"Search failed: {str(e)}")
        
        self._thread_pool.submit(search_worker)
    
    def _do_search(self, keyword: str, page: int) -> None:
        """Internal search method using original PicACG-qt with automatic failover."""
        from pancomic.models.comic import Comic
        
        # Try each endpoint until one works
        endpoints_to_try = [self._current_endpoint] + [
            ep for ep in self._api_endpoints if ep != self._current_endpoint
        ]
        
        for attempt, endpoint in enumerate(endpoints_to_try, 1):
            try:
                print(f"🔍 搜索 (端点 {attempt}/{len(endpoints_to_try)}): {endpoint}")
                
                # Temporarily switch endpoint
                old_endpoint = self._current_endpoint
                self._current_endpoint = endpoint
                
                # Update PicACG config
                if self._picacg_config:
                    if endpoint.endswith('/'):
                        self._picacg_config.Url = endpoint
                    else:
                        self._picacg_config.Url = endpoint + '/'
                
                # Create advanced search request using original PicACG-qt
                # AdvancedSearchReq(page, categories, keyword="", sort="")
                search_req = self._req_module.AdvancedSearchReq(page, [], keyword, "dd")
                
                # Send search request
                task = self._server._Send(self._task_class(search_req), 0)
                
                if hasattr(task, 'status') and task.status == self._status.Ok:
                    # Process search response
                    comics = []
                    
                    # Parse response using original PicACG-qt response handling
                    if task.res and task.res.code == 200:
                        try:
                            comics_data = task.res.data.get("comics", {}).get("docs", [])
                            
                            for pica_comic in comics_data:
                                try:
                                    # Extract cover URL
                                    cover_url = ""
                                    if pica_comic.get("thumb"):
                                        thumb = pica_comic["thumb"]
                                        if thumb.get("fileServer") and thumb.get("path"):
                                            cover_url = f"{thumb['fileServer']}/static/{thumb['path']}"
                                    
                                    # Create Comic object
                                    comic = Comic(
                                        id=pica_comic.get("_id", ""),
                                        title=pica_comic.get("title", ""),
                                        author=pica_comic.get("author", "") or "未知作者",
                                        cover_url=cover_url or "placeholder://no-cover",
                                        description=pica_comic.get("description", ""),
                                        tags=pica_comic.get("tags", []),
                                        categories=pica_comic.get("categories", []),
                                        status="completed" if pica_comic.get("finished", False) else "ongoing",
                                        chapter_count=pica_comic.get("epsCount", 0),
                                        view_count=pica_comic.get("totalViews", 0),
                                        like_count=pica_comic.get("totalLikes", 0),
                                        is_favorite=pica_comic.get("isFavourite", False),
                                        source="picacg"
                                    )
                                    comics.append(comic)
                                    
                                except Exception as comic_error:
                                    print(f"❌ 处理漫画时出错: {comic_error}")
                                    continue
                            
                            self.search_completed.emit(comics)
                            print(f"✅ 搜索完成: 找到 {len(comics)} 个结果")
                            print(f"   使用端点: {endpoint}")
                            return
                            
                        except Exception as parse_error:
                            print(f"   ⚠️ 解析失败: {str(parse_error)[:50]}")
                    else:
                        print(f"   ⚠️ 端点返回错误代码: {task.res.code if task.res else 'unknown'}")
                else:
                    print(f"   ⚠️ 端点请求失败")
                    
            except Exception as e:
                error_str = str(e)
                if 'timed out' in error_str or 'ConnectTimeout' in error_str:
                    print(f"   ⏱️ 端点超时")
                elif 'Connection' in error_str:
                    print(f"   🔌 连接失败")
                else:
                    print(f"   ❌ 错误: {error_str[:50]}")
                continue
        
        # All endpoints failed
        error_msg = "Search failed - all endpoints failed"
        self.search_failed.emit(error_msg)
        print(f"❌ 搜索失败: {error_msg}")
    
    def get_chapters(self, comic_id: str) -> None:
        """
        Get chapters for a comic using original PicACG-qt.
        
        Args:
            comic_id: Comic ID
        """
        if not self._is_initialized:
            self.chapters_failed.emit("Wrapper not initialized")
            return
        
        if not self.is_logged_in():
            self.chapters_failed.emit("Please login first")
            return
        
        def chapters_worker():
            try:
                self._do_get_chapters(comic_id)
            except Exception as e:
                self.chapters_failed.emit(f"Get chapters failed: {str(e)}")
        
        self._thread_pool.submit(chapters_worker)
    
    def _do_get_chapters(self, comic_id: str) -> None:
        """Internal get chapters method using original PicACG-qt with automatic failover."""
        from pancomic.models.chapter import Chapter
        
        # Try each endpoint until one works
        endpoints_to_try = [self._current_endpoint] + [
            ep for ep in self._api_endpoints if ep != self._current_endpoint
        ]
        
        for attempt, endpoint in enumerate(endpoints_to_try, 1):
            try:
                print(f"📚 获取章节 (端点 {attempt}/{len(endpoints_to_try)}): {endpoint}")
                
                # Temporarily switch endpoint
                old_endpoint = self._current_endpoint
                self._current_endpoint = endpoint
                
                # Update PicACG config
                if self._picacg_config:
                    if endpoint.endswith('/'):
                        self._picacg_config.Url = endpoint
                    else:
                        self._picacg_config.Url = endpoint + '/'
                
                # Create chapters request using original PicACG-qt
                # GetComicsBookEpsReq(bookId="", page="1")
                chapters_req = self._req_module.GetComicsBookEpsReq(comic_id, "1")
                
                # Send chapters request
                task = self._server._Send(self._task_class(chapters_req), 0)
                
                if hasattr(task, 'status') and task.status == self._status.Ok:
                    # Process chapters response
                    chapters = []
                    
                    # Parse response using original PicACG-qt response handling
                    if task.res and task.res.code == 200:
                        try:
                            eps_data = task.res.data.get("eps", {})
                            docs = eps_data.get("docs", [])
                            
                            for i, chapter_data in enumerate(docs):
                                try:
                                    order = chapter_data.get("order", i + 1)
                                    chapter_id = str(order + 1)  # 使用order+1作为ID
                                    title = chapter_data.get("title", f"第{order}话")
                                    
                                    chapter = Chapter(
                                        id=chapter_id,
                                        comic_id=comic_id,
                                        title=title,
                                        chapter_number=order,
                                        page_count=0,
                                        is_downloaded=False,
                                        download_path=None,
                                        source="picacg"
                                    )
                                    chapters.append(chapter)
                                    
                                except Exception as chapter_error:
                                    print(f"❌ 处理章节时出错: {chapter_error}")
                                    continue
                            
                            self.chapters_completed.emit(chapters)
                            print(f"✅ 获取章节完成: 找到 {len(chapters)} 个章节")
                            print(f"   使用端点: {endpoint}")
                            return
                            
                        except Exception as parse_error:
                            print(f"   ⚠️ 解析失败: {str(parse_error)[:50]}")
                    else:
                        print(f"   ⚠️ 端点返回错误代码: {task.res.code if task.res else 'unknown'}")
                else:
                    print(f"   ⚠️ 端点请求失败")
                    
            except Exception as e:
                error_str = str(e)
                if 'timed out' in error_str or 'ConnectTimeout' in error_str:
                    print(f"   ⏱️ 端点超时")
                elif 'Connection' in error_str:
                    print(f"   🔌 连接失败")
                else:
                    print(f"   ❌ 错误: {error_str[:50]}")
                continue
        
        # All endpoints failed
        error_msg = "Get chapters failed - all endpoints failed"
        self.chapters_failed.emit(error_msg)
        print(f"❌ 获取章节失败: {error_msg}")
    
    def get_chapter_images(self, comic_id: str, chapter_id: str) -> None:
        """
        Get images for a chapter using original PicACG-qt.
        
        Args:
            comic_id: Comic ID
            chapter_id: Chapter ID (order+1 format)
        """
        if not self._is_initialized:
            self.images_failed.emit("Wrapper not initialized")
            return
        
        if not self.is_logged_in():
            self.images_failed.emit("Please login first")
            return
        
        def images_worker():
            try:
                self._do_get_chapter_images(comic_id, chapter_id)
            except Exception as e:
                self.images_failed.emit(f"Get images failed: {str(e)}")
        
        self._thread_pool.submit(images_worker)
    
    def _do_get_chapter_images(self, comic_id: str, chapter_id: str) -> None:
        """Internal get images method using original PicACG-qt with automatic failover."""
        # Try each endpoint until one works
        endpoints_to_try = [self._current_endpoint] + [
            ep for ep in self._api_endpoints if ep != self._current_endpoint
        ]
        
        for attempt, endpoint in enumerate(endpoints_to_try, 1):
            try:
                print(f"🖼️ 获取图片 (端点 {attempt}/{len(endpoints_to_try)}): {endpoint}")
                
                # Temporarily switch endpoint
                old_endpoint = self._current_endpoint
                self._current_endpoint = endpoint
                
                # Update PicACG config
                if self._picacg_config:
                    if endpoint.endswith('/'):
                        self._picacg_config.Url = endpoint
                    else:
                        self._picacg_config.Url = endpoint + '/'
                
                # Create images request using original PicACG-qt
                # GetComicsBookOrderReq(bookId="", epsId="", page="1")
                # Convert chapter_id back to order format (chapter_id is order+1)
                order = str(int(chapter_id) - 1)
                images_req = self._req_module.GetComicsBookOrderReq(comic_id, order, "1")
                
                # Send images request
                task = self._server._Send(self._task_class(images_req), 0)
                
                if hasattr(task, 'status') and task.status == self._status.Ok:
                    # Process images response
                    image_urls = []
                    
                    # Parse response using original PicACG-qt response handling
                    if task.res and task.res.code == 200:
                        try:
                            pages_data = task.res.data.get("pages", {})
                            docs = pages_data.get("docs", [])
                            
                            for page_data in docs:
                                try:
                                    media = page_data.get("media")
                                    if media and media.get("fileServer") and media.get("path"):
                                        file_server = media.get("fileServer")
                                        path = media.get("path")
                                        
                                        # Build image URL using current image server
                                        image_url = self._build_image_url(file_server, path)
                                        image_urls.append(image_url)
                                        
                                except Exception as img_error:
                                    print(f"❌ 处理图片时出错: {img_error}")
                                    continue
                            
                            self.images_completed.emit(image_urls)
                            print(f"✅ 获取图片完成: 找到 {len(image_urls)} 张图片")
                            print(f"   使用端点: {endpoint}")
                            return
                            
                        except Exception as parse_error:
                            print(f"   ⚠️ 解析失败: {str(parse_error)[:50]}")
                    else:
                        print(f"   ⚠️ 端点返回错误代码: {task.res.code if task.res else 'unknown'}")
                else:
                    print(f"   ⚠️ 端点请求失败")
                    
            except Exception as e:
                error_str = str(e)
                if 'timed out' in error_str or 'ConnectTimeout' in error_str:
                    print(f"   ⏱️ 端点超时")
                elif 'Connection' in error_str:
                    print(f"   🔌 连接失败")
                else:
                    print(f"   ❌ 错误: {error_str[:50]}")
                continue
        
        # All endpoints failed
        error_msg = "Get images failed - all endpoints failed"
        self.images_failed.emit(error_msg)
        print(f"❌ 获取图片失败: {error_msg}")
    
    def _build_image_url(self, original_server: str, path: str) -> str:
        """
        Build image URL with server replacement.
        
        Args:
            original_server: Original server URL
            path: Image path
            
        Returns:
            Complete image URL
        """
        # Use configured image server
        if self._current_image_server:
            return f"https://{self._current_image_server}/static/{path}"
        
        # Fallback to original server
        if not original_server.startswith("http"):
            original_server = f"https://{original_server}"
        
        if "/static/" not in original_server:
            return f"{original_server}/static/{path}"
        else:
            return f"{original_server}/{path}"
    
    def set_endpoint(self, endpoint: str) -> None:
        """Set API endpoint."""
        if endpoint in self._api_endpoints:
            self._current_endpoint = endpoint
            self.config['endpoint'] = endpoint
            
            # Update PicACG config
            if self._picacg_config:
                if endpoint.endswith('/'):
                    self._picacg_config.Url = endpoint
                else:
                    self._picacg_config.Url = endpoint + '/'
            
            self.endpoint_changed.emit(endpoint)
            print(f"🔄 切换API端点: {endpoint}")
    
    def set_image_server(self, server: str) -> None:
        """Set image server."""
        if server in self._image_servers:
            self._current_image_server = server
            self.config['image_server'] = server
            
            # Update PicACG config
            if self._picacg_config:
                self._picacg_config.ImageUrl = f"https://{server}"
            
            self.image_server_changed.emit(server)
            print(f"🔄 切换图片服务器: {server}")
    
    def get_api_endpoints(self) -> List[str]:
        """Get available API endpoints."""
        return self._api_endpoints.copy()
    
    def get_image_servers(self) -> List[str]:
        """Get available image servers."""
        return self._image_servers.copy()
    
    def get_current_endpoint(self) -> str:
        """Get current API endpoint."""
        return self._current_endpoint
    
    def get_current_image_server(self) -> str:
        """Get current image server."""
        return self._current_image_server
    
    def test_endpoints(self) -> None:
        """Test API endpoints speed."""
        def test_worker():
            try:
                self._do_test_endpoints()
            except Exception as e:
                print(f"❌ 端点测试异常: {e}")
        
        self._thread_pool.submit(test_worker)
    
    def _do_test_endpoints(self) -> None:
        """Internal endpoint testing method."""
        try:
            import requests
            import urllib3
            
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            results = {}
            
            for endpoint in self._api_endpoints:
                try:
                    start_time = time_module.time()
                    
                    headers = {
                        'User-Agent': 'okhttp/3.8.1',
                        'Accept': 'application/vnd.picacomic.com.v1+json',
                    }
                    
                    # Handle IP endpoints with Host header
                    if endpoint.startswith('https://104.21.91.145') or endpoint.startswith('https://188.114.98.153'):
                        headers['Host'] = 'picaapi.picacomic.com'
                    
                    response = requests.get(
                        f"{endpoint}/",
                        headers=headers,
                        timeout=10,
                        verify=False
                    )
                    
                    elapsed = time_module.time() - start_time
                    
                    if response.status_code < 500:
                        results[endpoint] = elapsed * 1000  # Convert to ms
                    else:
                        results[endpoint] = -1
                        
                except Exception as e:
                    results[endpoint] = -1
                    print(f"❌ 测试端点 {endpoint} 失败: {e}")
            
            self.endpoint_test_completed.emit(results)
            print(f"✅ 端点测试完成: {results}")
            
        except Exception as e:
            print(f"❌ 端点测试异常: {e}")
    
    def test_image_servers(self) -> None:
        """Test image servers speed."""
        def test_worker():
            try:
                self._do_test_image_servers()
            except Exception as e:
                print(f"❌ 图片服务器测试异常: {e}")
        
        self._thread_pool.submit(test_worker)
    
    def _do_test_image_servers(self) -> None:
        """Internal image server testing method."""
        try:
            import requests
            import urllib3
            
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            results = {}
            
            for server in self._image_servers:
                try:
                    start_time = time_module.time()
                    
                    test_urls = [
                        f"https://{server}/static/tobeimg/logo.png",
                        f"https://{server}/favicon.ico",
                        f"https://{server}/",
                    ]
                    
                    success = False
                    for test_url in test_urls:
                        try:
                            response = requests.get(
                                test_url,
                                timeout=10,
                                headers={'User-Agent': 'okhttp/3.8.1'},
                                verify=False
                            )
                            
                            if response.status_code < 400:
                                success = True
                                break
                        except:
                            continue
                    
                    elapsed = time_module.time() - start_time
                    
                    if success:
                        results[server] = elapsed * 1000  # Convert to ms
                    else:
                        results[server] = -1
                        
                except Exception as e:
                    results[server] = -1
                    print(f"❌ 测试图片服务器 {server} 失败: {e}")
            
            self.image_server_test_completed.emit(results)
            print(f"✅ 图片服务器测试完成: {results}")
            
        except Exception as e:
            print(f"❌ 图片服务器测试异常: {e}")
    
    def auto_login(self) -> None:
        """Attempt auto-login with stored credentials."""
        auto_login_enabled = self.config.get('auto_login', False)
        
        if not auto_login_enabled:
            print("ℹ️ PicACG自动登录未启用")
            return
        
        # Try credentials from config
        if 'credentials' in self.config:
            credentials = self.config['credentials']
            email = credentials.get('email', '')
            password = credentials.get('password', '')
        else:
            email = self.config.get('email', '')
            password = self.config.get('password', '')
        
        if email and password:
            print(f"🔄 PicACG自动登录: {email}")
            self.login(email, password)
        else:
            print("⚠️ PicACG自动登录: 缺少凭据")
    
    def logout(self) -> None:
        """Logout from PicACG."""
        try:
            if self._user:
                self._user.Logout()
            
            self._is_logged_in = False
            
            # Clear stored credentials
            if 'credentials' in self.config:
                del self.config['credentials']
            
            print("✅ PicACG登出成功")
            
        except Exception as e:
            print(f"⚠️ PicACG登出异常: {e}")
    
    def cleanup(self) -> None:
        """Clean up resources."""
        try:
            if hasattr(self, '_thread_pool'):
                self._thread_pool.shutdown(wait=False)
                print("✅ PicACG包装器线程池已清理")
        except Exception as e:
            print(f"⚠️ PicACG包装器清理失败: {e}")