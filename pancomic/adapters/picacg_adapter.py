"""PicACG adapter implementation."""

import sys
import os
import threading
from typing import Dict, Any, List, Optional
from PySide6.QtCore import QMetaObject, Qt, Q_ARG, Signal, QTimer, Slot

# Import time and uuid with different names to avoid conflicts
import time as time_module
import uuid as uuid_module
import hmac
from hashlib import sha256

from .base_adapter import BaseSourceAdapter
from ..models.comic import Comic
from ..models.chapter import Chapter


class PicACGAdapter(BaseSourceAdapter):
    """
    Adapter for PicACG-qt integration.
    
    This adapter wraps the original PicACG-qt project and provides
    a unified interface while maintaining thread isolation.
    Includes API endpoint selection and automatic failover.
    """
    
    # Additional signals for endpoint and image server management
    endpoint_test_completed = Signal(dict)  # {endpoint: response_time}
    endpoint_changed = Signal(str)  # new_endpoint
    image_server_test_completed = Signal(dict)  # {server: response_time}
    image_server_changed = Signal(str)  # new_server
    
    # PicACG API配置 - 与原版PicACG-qt保持一致
    API_KEY = "C69BAF41DA5ABD1FFEDC6D2FEA56B"
    APP_CHANNEL = "3"
    VERSION = "2.2.1.3.3.4"
    BUILD_VERSION = "45"
    ACCEPT = "application/vnd.picacomic.com.v1+json"
    AGENT = "okhttp/3.8.1"
    PLATFORM = "android"
    UUID = "defaultUuid"
    UPDATE_VERSION = "v1.5.3"
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the PicACG adapter.
        
        Args:
            config: PicACG-specific configuration dictionary
        """
        super().__init__(config)
        self._picacg_module = None
        self._current_endpoint = None
        self._available_endpoints = []
        self._endpoint_index = 0
        self._server = None
        self._user = None
        self._req_module = None
        self._res_module = None
        self._is_logged_in = False
        self._auth_token = None
        self._speed_test_results = {}
        self._speed_test_timer = QTimer()
        self._speed_test_timer.timeout.connect(self._on_speed_test_timeout)
        
        # 初始化默认的API端点和图片服务器列表
        self._api_endpoints = [
            'https://picaapi.picacomic.com',
            'https://bika-api.jpacg.cc',
            'https://188.114.98.153',
            'https://bika2-api.jpacg.cc',
            'https://104.21.91.145',
        ]
        self._image_servers = [
            'storage.diwodiwo.xyz',
            'storage-b.picacomic.com',
            's3.picacomic.com',
            's2.picacomic.com',
            'storage1.picacomic.com',
        ]
        self._current_image_server = self._image_servers[0]
        self._image_server_index = 0
        
        # Thread pool for background operations
        from concurrent.futures import ThreadPoolExecutor
        self._thread_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="PicACG")
        
    def initialize(self) -> None:
        """
        Initialize the PicACG-qt modules.
        
        This method:
        - Adds the PicACG-qt source path to sys.path
        - Imports necessary modules from the original project
        - Configures API endpoint, image quality, proxy, and other settings
        - Marks the adapter as initialized
        """
        try:
            # Add PicACG-qt source path to sys.path
            picacg_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'forapi', 'picacg', 'src'
            )
            
            if picacg_path not in sys.path:
                sys.path.insert(0, picacg_path)
            
            # Import PicACG modules
            from server.server import Server
            from tools.user import User
            import server.req as req
            import server.res as res
            from config import config as picacg_config
            from config.setting import Setting
            from tools.status import Status
            
            self._server = Server()
            self._user = User()
            self._req_module = req
            self._res_module = res
            self._picacg_config = picacg_config
            self._setting = Setting
            self._status = Status
            
            # Initialize available API endpoints - 基于原版PicACG-qt的ApiDomain配置
            self._api_endpoints = self.config.get('api_endpoints', [
                'https://picaapi.picacomic.com',     # 官方主API
                'https://post-api.wikawika.xyz',     # 备用API (来自原版配置)
                'https://bika-api.jpacg.cc',        # JP反代分流
                'https://188.114.98.153',           # IP直连分流
                'https://bika2-api.jpacg.cc',       # US反代分流
                'https://104.21.91.145',            # IP直连分流2
            ])
            
            # Initialize available image servers (5个图片分流) - 用户可通过测速选择
            self._image_servers = self.config.get('image_servers', [
                'storage.diwodiwo.xyz',            # 图片分流2 (Diwo)
                'storage-b.picacomic.com',         # 图片分流5 (Storage-B)
                's3.picacomic.com',                 # 图片分流1 (S3)
                's2.picacomic.com',                # 图片分流3 (S2)
                'storage1.picacomic.com',          # 图片分流4 (Storage1)
            ])
            
            # For backward compatibility
            self._available_endpoints = self._api_endpoints
            
            # Set current API endpoint and image server (use user settings)
            self._current_endpoint = self.config.get('endpoint', self._api_endpoints[0])  # Default to official API
            self._current_image_server = self.config.get('image_server', self._image_servers[0])  # Default to Diwo
            
            # 记录当前配置
            print(f"🔧 PicACG配置:")
            print(f"  API服务器: {self._current_endpoint}")
            print(f"  图片服务器: {self._current_image_server}")
            print(f"  自动登录: {self.config.get('auto_login', False)}")
            
            # Normalize endpoint (remove trailing slash)
            if self._current_endpoint.endswith('/'):
                self._current_endpoint = self._current_endpoint[:-1]
            
            self._endpoint_index = self._api_endpoints.index(self._current_endpoint) if self._current_endpoint in self._api_endpoints else 1
            self._image_server_index = self._image_servers.index(self._current_image_server) if self._current_image_server in self._image_servers else 0
            
            # Configure image quality from config
            image_quality = self.config.get('image_quality', 'original')
            self._picacg_config.ImageQuality = image_quality
            
            # Set image server URL in PicACG config
            self._picacg_config.ImageUrl = f"https://{self._current_image_server}"
            
            # Configure proxy from config
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
            
            # Set API endpoint (PicACG config expects trailing slash)
            self._picacg_config.Url = self._current_endpoint + '/' if not self._current_endpoint.endswith('/') else self._current_endpoint
            
            self._is_initialized = True
            
        except Exception as e:
            error_msg = f"Failed to initialize PicACG adapter: {str(e)}"
            self.login_failed.emit(error_msg)
            raise
    
    def set_endpoint(self, endpoint: str) -> None:
        """
        Set the API endpoint to use.
        
        Args:
            endpoint: API endpoint URL
        """
        if endpoint in self._available_endpoints:
            self._current_endpoint = endpoint
            self._endpoint_index = self._available_endpoints.index(endpoint)
            self.config['endpoint'] = endpoint
            self.endpoint_changed.emit(endpoint)
    
    def get_current_endpoint(self) -> str:
        """
        Get the currently configured API endpoint.
        
        Returns:
            Current API endpoint URL
        """
        return self._current_endpoint
    
    def get_current_image_server(self) -> str:
        """
        Get the currently configured image server.
        
        Returns:
            Current image server domain
        """
        return self._current_image_server
    
    def set_image_server(self, server: str) -> None:
        """
        Set the image server to use.
        
        Args:
            server: Image server domain
        """
        if server in self._image_servers:
            self._current_image_server = server
            self._image_server_index = self._image_servers.index(server)
            self.config['image_server'] = server
            
            # Update PicACG config if available - handle gracefully
            try:
                if hasattr(self, '_picacg_config') and self._picacg_config:
                    # Set the image server URL directly in config
                    # This is used by the original PicACG code for image requests
                    self._picacg_config.ImageUrl = f"https://{server}"
            except Exception:
                # If config update fails, just continue - not critical
                pass
            
            # Emit signal for UI update
            self.image_server_changed.emit(server)
    
    def get_api_endpoints(self) -> List[str]:
        """Get all available API endpoints."""
        return self._api_endpoints.copy()
    
    def get_image_servers(self) -> List[str]:
        """Get all available image servers."""
        return self._image_servers.copy()
    
    def test_endpoints(self) -> None:
        """
        Test response time for all available API endpoints.
        
        Results are emitted via endpoint_test_completed signal.
        """
        if not self._is_initialized:
            return
        
        self._speed_test_results = {}
        self._speed_test_timer.start(15000)  # 15 second timeout for more endpoints
        
        # Test each API endpoint
        for endpoint in self._api_endpoints:
            threading.Thread(
                target=self._test_single_endpoint,
                args=(endpoint,),
                daemon=True
            ).start()
    
    def test_image_servers(self) -> None:
        """
        Test response time for all available image servers.
        
        Results are emitted via image_server_test_completed signal.
        """
        if not self._is_initialized:
            return
        
        self._image_speed_test_results = {}
        self._image_speed_test_timer = QTimer()
        self._image_speed_test_timer.timeout.connect(self._on_image_speed_test_timeout)
        self._image_speed_test_timer.start(15000)  # 15 second timeout
        
        # Test each image server
        for server in self._image_servers:
            threading.Thread(
                target=self._test_single_image_server,
                args=(server,),
                daemon=True
            ).start()
    
    def _test_single_endpoint(self, endpoint: str) -> None:
        """
        Test a single endpoint response time using basic connectivity approach.
        
        Args:
            endpoint: Endpoint URL to test
        """
        try:
            import requests
            import urllib3
            
            # Disable SSL warnings for testing
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            start_time = time_module.time()
            
            # Simple headers for basic connectivity test
            headers = {
                'User-Agent': 'okhttp/3.8.1',
                'Accept': 'application/vnd.picacomic.com.v1+json',
            }
            
            # Handle IP endpoints with Host header
            if endpoint.startswith('https://104.21.91.145') or endpoint.startswith('https://188.114.98.153'):
                headers['Host'] = 'picaapi.picacomic.com'
            
            # Test basic connectivity (just root path)
            test_url = f"{endpoint}/"
            
            response = requests.get(
                test_url,
                headers=headers,
                timeout=10,
                verify=False,  # Skip SSL verification
                allow_redirects=True
            )
            
            elapsed = time_module.time() - start_time
            
            # Any response < 500 means server is reachable
            if response.status_code < 500:
                self._speed_test_results[endpoint] = elapsed * 1000  # Convert to ms
            else:
                self._speed_test_results[endpoint] = -1
            
            # Check if all tests completed
            if len(self._speed_test_results) == len(self._api_endpoints):
                self._speed_test_timer.stop()
                self.endpoint_test_completed.emit(self._speed_test_results.copy())
                
        except Exception as e:
            self._speed_test_results[endpoint] = -1
            
            # Check if all tests completed
            if len(self._speed_test_results) == len(self._api_endpoints):
                self._speed_test_timer.stop()
                self.endpoint_test_completed.emit(self._speed_test_results.copy())
    
    def _on_speed_test_timeout(self) -> None:
        """Handle API speed test timeout."""
        self._speed_test_timer.stop()
        
        # Mark untested endpoints as failed
        for endpoint in self._api_endpoints:
            if endpoint not in self._speed_test_results:
                self._speed_test_results[endpoint] = -1
        
        self.endpoint_test_completed.emit(self._speed_test_results.copy())
    
    def _test_single_image_server(self, server: str) -> None:
        """
        Test a single image server response time.
        
        Args:
            server: Image server domain to test
        """
        try:
            import requests
            import urllib3
            
            # Disable SSL warnings for testing
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            # Test with a known small image or favicon
            test_urls = [
                f"https://{server}/static/tobeimg/logo.png",
                f"https://{server}/favicon.ico",
                f"https://{server}/",  # Just test basic connectivity
            ]
            
            start_time = time_module.time()
            success = False
            
            for test_url in test_urls:
                try:
                    response = requests.get(
                        test_url, 
                        timeout=10, 
                        headers={'User-Agent': 'okhttp/3.8.1'},
                        verify=False,  # Skip SSL verification for testing
                        allow_redirects=True
                    )
                    
                    # Accept any successful response (200, 301, 302, etc.)
                    if response.status_code < 400:
                        success = True
                        break
                except:
                    continue
            
            elapsed = time_module.time() - start_time
            
            if success:
                self._image_speed_test_results[server] = elapsed * 1000  # Convert to ms
            else:
                self._image_speed_test_results[server] = -1
            
            # Check if all tests completed
            if len(self._image_speed_test_results) == len(self._image_servers):
                self._image_speed_test_timer.stop()
                self.image_server_test_completed.emit(self._image_speed_test_results.copy())
                
        except Exception as e:
            self._image_speed_test_results[server] = -1
            
            # Check if all tests completed
            if len(self._image_speed_test_results) == len(self._image_servers):
                self._image_speed_test_timer.stop()
                self.image_server_test_completed.emit(self._image_speed_test_results.copy())
    
    def _on_image_speed_test_timeout(self) -> None:
        """Handle image server speed test timeout."""
        self._image_speed_test_timer.stop()
        
        # Mark untested servers as failed
        for server in self._image_servers:
            if server not in self._image_speed_test_results:
                self._image_speed_test_results[server] = -1
        
        self.image_server_test_completed.emit(self._image_speed_test_results.copy())
    
    def _try_next_endpoint(self) -> bool:
        """
        Try the next available endpoint (failover).
        
        Returns:
            True if switched to next endpoint, False if no more endpoints
        """
        if len(self._api_endpoints) <= 1:
            return False
        
        # Move to next endpoint
        self._endpoint_index = (self._endpoint_index + 1) % len(self._api_endpoints)
        self._current_endpoint = self._api_endpoints[self._endpoint_index]
        
        # Update PicACG config URL
        if hasattr(self, '_picacg_config') and self._picacg_config:
            self._picacg_config.Url = self._current_endpoint + '/' if not self._current_endpoint.endswith('/') else self._current_endpoint
        
        self.endpoint_changed.emit(self._current_endpoint)
        
        return True
    
    def _get_signature_key(self) -> str:
        """获取签名密钥"""
        return '~d}$Q7$eIni=V)9\\RK/P.RM4;9[7|@/CA}b~OW!3?EV`:<>M7pddUBL5n|0/*Cn'
    
    def _create_signature_data(self, base_url: str, path: str, timestamp: str, nonce: str, method: str) -> str:
        """创建签名数据 - 按照原版PicACG-qt逻辑"""
        # 根据原版 __ConFromNative 方法的逻辑
        # datas = [config.Url, path, timestamp, nonce, method, config.ApiKey, config.Version, config.BuildVersion]
        # 签名数据顺序: path + timestamp + nonce + method + api_key
        key = ""
        key += path  # v37 = str(datas[1]) - path
        key += timestamp  # v7 = str(datas[2]) - timestamp  
        key += nonce  # v35 = str(datas[3]) - nonce
        key += method  # v36 = str(datas[4]) - method
        key += self.API_KEY  # v8 = str(datas[5]) - api_key
        return key
    
    def _hash_key(self, src: str, key: str) -> str:
        """生成HMAC签名"""
        appsecret = key.encode('utf-8')
        data = src.lower().encode('utf-8')
        signature = hmac.new(appsecret, data, digestmod=sha256).hexdigest()
        return signature
    
    def _get_signed_headers(self, base_url: str, path: str, method: str = "POST") -> Dict[str, str]:
        """获取带签名的请求头"""
        now = str(int(time_module.time()))
        nonce = str(uuid_module.uuid1()).replace("-", "")
        
        # 创建签名数据
        signature_data = self._create_signature_data(base_url, path, now, nonce, method)
        
        # 生成签名
        signature_key = self._get_signature_key()
        signature = self._hash_key(signature_data, signature_key)
        
        headers = {
            "api-key": self.API_KEY,
            "accept": self.ACCEPT,  # 注意：原版使用小写的accept
            "app-channel": self.APP_CHANNEL,
            "time": now,
            "app-uuid": self.UUID,
            "nonce": nonce,
            "signature": signature,
            "app-version": self.VERSION,
            "image-quality": "original",
            "app-platform": self.PLATFORM,
            "app-build-version": self.BUILD_VERSION,
            "user-agent": self.AGENT,
            "version": self.UPDATE_VERSION,
        }
        
        if method.lower() in ["post", "put"]:
            headers["Content-Type"] = "application/json; charset=UTF-8"
        
        return headers
    
    def search(self, keyword: str, page: int = 1) -> None:
        """
        Search comics with the given keyword.
        
        This method performs search directly and emits results via signals.
        
        Args:
            keyword: Search keyword
            page: Page number (default: 1)
        """
        if not self._is_initialized:
            self.search_failed.emit("Adapter not initialized")
            return
        
        # Use thread pool to avoid blocking UI
        def search_worker():
            try:
                self._do_search(keyword, page)
            except Exception as e:
                self.search_failed.emit(f"Search worker failed: {str(e)}")
        
        # Submit to thread pool
        self._thread_pool.submit(search_worker)
    
    def _do_search(self, keyword: str, page: int) -> None:
        """
        Internal method to perform search in worker thread using direct HTTP requests.
        
        Args:
            keyword: Search keyword
            page: Page number
        """
        try:
            import requests
            import urllib3
            
            # Disable SSL warnings
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            if not self._is_logged_in or not self._auth_token:
                self.search_failed.emit("Please login first")
                return
            
            # 使用直接的HTTP请求进行搜索
            base_url = self._current_endpoint + "/"
            path = "comics/advanced-search"
            search_url = f"{self._current_endpoint}/{path}"
            
            # 获取带签名的请求头
            headers = self._get_signed_headers(base_url, path, "POST")
            headers["authorization"] = self._auth_token  # 添加认证token
            
            # 搜索数据
            search_data = {
                "keyword": keyword,
                "page": page,
                "categories": [],
                "sort": "dd"  # 按日期降序排序
            }
            
            response = requests.post(
                search_url,
                json=search_data,
                headers=headers,
                timeout=15,
                verify=False
            )
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    comics_data = data.get("data", {}).get("comics", {}).get("docs", [])
                    
                    comics = []
                    for i, pica_comic in enumerate(comics_data):
                        try:
                            # Extract cover URL
                            cover_url = ""
                            if pica_comic.get("thumb"):
                                thumb = pica_comic["thumb"]
                                if thumb.get("fileServer") and thumb.get("path"):
                                    cover_url = f"{thumb['fileServer']}/static/{thumb['path']}"
                            
                            # Create Comic object with safe data handling
                            comic_id = pica_comic.get("_id", "")
                            title = pica_comic.get("title", "")
                            author = pica_comic.get("author", "") or "未知作者"  # Handle empty author
                            description = pica_comic.get("description", "") or None  # Handle empty description
                            
                            # Ensure required fields are not empty
                            if not comic_id:
                                comic_id = f"unknown_{hash(str(pica_comic))}"
                            if not title:
                                title = "未知标题"
                            if not cover_url:
                                cover_url = "placeholder://no-cover"
                            
                            # Debug logging for problematic data
                            print(f"🔍 处理漫画 {i+1}: id={comic_id}, title={title}, author={author}")
                            
                            comic = Comic(
                                id=comic_id,
                                title=title,
                                author=author,
                                cover_url=cover_url,
                                description=description,
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
                            print(f"❌ 处理漫画 {i+1} 时出错: {comic_error}")
                            print(f"   原始数据: {pica_comic}")
                            # 跳过有问题的漫画，继续处理其他的
                            continue
                    
                    self.search_completed.emit(comics)
                    return
                    
                except Exception as parse_error:
                    self.search_failed.emit(f"Failed to parse search results: {str(parse_error)}")
                    return
            
            elif response.status_code == 401:
                self.search_failed.emit("Authentication failed. Please login again.")
                return
            
            else:
                self.search_failed.emit(f"Search failed: HTTP {response.status_code}")
                return
                
        except Exception as e:
            self.search_failed.emit(f"Search failed: {str(e)}")
    
    def get_comic_detail(self, comic_id: str) -> None:
        """
        Get detailed information about a comic.
        
        This method performs operation directly and emits results via signals.
        
        Args:
            comic_id: Unique identifier for the comic
        """
        if not self._is_initialized:
            self.comic_detail_failed.emit("Adapter not initialized")
            return
        
        # Use thread pool to avoid blocking UI
        def detail_worker():
            try:
                self._do_get_comic_detail(comic_id)
            except Exception as e:
                self.comic_detail_failed.emit(f"Comic detail worker failed: {str(e)}")
        
        # Submit to thread pool
        self._thread_pool.submit(detail_worker)
    
    def _do_get_comic_detail(self, comic_id: str) -> None:
        """
        Internal method to get comic detail in worker thread using direct HTTP requests.
        
        Args:
            comic_id: Comic identifier
        """
        try:
            import requests
            import urllib3
            
            # Disable SSL warnings
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            if not self._is_logged_in or not self._auth_token:
                self.comic_detail_failed.emit("Please login first")
                return
            
            # 使用直接的HTTP请求获取漫画详情
            base_url = self._current_endpoint + "/"
            path = f"comics/{comic_id}"
            detail_url = f"{self._current_endpoint}/{path}"
            
            # 获取带签名的请求头
            headers = self._get_signed_headers(base_url, path, "GET")
            headers["authorization"] = self._auth_token
            
            # 为IP服务器和反代服务器添加Host头
            if any(domain in self._current_endpoint for domain in ['104.21.91.145', '188.114.98.153', 'bika-api', 'bika2-api']):
                headers['Host'] = 'picaapi.picacomic.com'
            
            response = requests.get(
                detail_url,
                headers=headers,
                timeout=15,
                verify=False
            )
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    pica_comic = data.get("data", {}).get("comic", {})
                    
                    if not pica_comic:
                        self.comic_detail_failed.emit(f"Comic not found: {comic_id}")
                        return
                    
                    # Extract cover URL
                    cover_url = ""
                    if pica_comic.get("thumb"):
                        thumb = pica_comic["thumb"]
                        if thumb.get("fileServer") and thumb.get("path"):
                            cover_url = f"{thumb['fileServer']}/static/{thumb['path']}"
                    
                    # Create detailed Comic object with safe data handling
                    comic_id = pica_comic.get("_id", "")
                    title = pica_comic.get("title", "")
                    author = pica_comic.get("author", "") or "未知作者"  # Handle empty author
                    description = pica_comic.get("description", "") or None  # Handle empty description
                    
                    # Ensure required fields are not empty
                    if not comic_id:
                        comic_id = f"unknown_{hash(str(pica_comic))}"
                    if not title:
                        title = "未知标题"
                    if not cover_url:
                        cover_url = "placeholder://no-cover"
                    
                    comic = Comic(
                        id=comic_id,
                        title=title,
                        author=author,
                        cover_url=cover_url,
                        description=description,
                        tags=pica_comic.get("tags", []),
                        categories=pica_comic.get("categories", []),
                        status="completed" if pica_comic.get("finished", False) else "ongoing",
                        chapter_count=pica_comic.get("epsCount", 0),
                        view_count=pica_comic.get("totalViews", 0),
                        like_count=pica_comic.get("totalLikes", 0),
                        is_favorite=pica_comic.get("isFavourite", False),
                        source="picacg"
                    )
                    
                    self.comic_detail_completed.emit(comic)
                    return
                    
                except Exception as parse_error:
                    self.comic_detail_failed.emit(f"Failed to parse comic detail: {str(parse_error)}")
                    return
            
            elif response.status_code == 401:
                self.comic_detail_failed.emit("Authentication failed. Please login again.")
                return
            
            else:
                self.comic_detail_failed.emit(f"Get comic detail failed: HTTP {response.status_code}")
                return
                
        except Exception as e:
            self.comic_detail_failed.emit(f"Failed to get comic detail: {str(e)}")
    
    def get_chapters(self, comic_id: str) -> None:
        """
        Get the list of chapters for a comic.
        
        This method performs operation directly and emits results via signals.
        
        Args:
            comic_id: Unique identifier for the comic
        """
        if not self._is_initialized:
            self.chapters_failed.emit("Adapter not initialized")
            return
        
        # Use thread pool to avoid blocking UI
        def chapters_worker():
            try:
                self._do_get_chapters(comic_id)
            except Exception as e:
                self.chapters_failed.emit(f"Chapters worker failed: {str(e)}")
        
        # Submit to thread pool
        self._thread_pool.submit(chapters_worker)
    
    def _do_get_chapters(self, comic_id: str) -> None:
        """
        Internal method to get chapters in worker thread using direct HTTP requests.
        
        Args:
            comic_id: Comic identifier
        """
        try:
            import requests
            import urllib3
            
            # Disable SSL warnings
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            if not self._is_logged_in or not self._auth_token:
                self.chapters_failed.emit("Please login first")
                return
            
            print(f"📚 获取PicACG漫画章节: {comic_id}")
            
            # 使用直接的HTTP请求获取章节信息
            base_url = self._current_endpoint + "/"
            path = f"comics/{comic_id}/eps"
            chapters_url = f"{self._current_endpoint}/{path}"
            
            # 获取带签名的请求头
            headers = self._get_signed_headers(base_url, path, "GET")
            headers["authorization"] = self._auth_token
            
            # 关键修复：不带page参数！
            response = requests.get(
                chapters_url,
                headers=headers,
                timeout=15,
                verify=False
            )
            
            print(f"📥 章节响应: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    
                    if data.get('code') != 200:
                        print(f"❌ API返回错误: {data}")
                        self.chapters_failed.emit(f"API error: {data.get('message', 'Unknown error')}")
                        return
                    
                    if 'data' not in data:
                        print(f"❌ 响应中没有data字段: {data}")
                        self.chapters_failed.emit("No data field in response")
                        return
                    
                    eps_data = data.get("data", {}).get("eps", {})
                    docs = eps_data.get("docs", [])
                    total = eps_data.get("total", 0)
                    
                    print(f"📖 找到 {len(docs)} 个章节 (总计 {total})")
                    
                    if not docs:
                        print(f"📭 没有找到章节，创建默认章节")
                        # 如果没有章节，创建默认章节
                        chapter = Chapter(
                            id="1",
                            comic_id=comic_id,
                            title="第1话",
                            chapter_number=1,
                            page_count=0,
                            is_downloaded=False,
                            download_path=None,
                            source="picacg"
                        )
                        chapters = [chapter]
                    else:
                        # 创建章节对象
                        chapters = []
                        for i, chapter_data in enumerate(docs):
                            try:
                                # 使用order作为章节ID（API需要这个值）
                                order = chapter_data.get("order", i + 1)
                                chapter_id = str(order)  # 直接使用order作为ID
                                title = chapter_data.get("title", f"第{order}话")
                                
                                chapter = Chapter(
                                    id=chapter_id,  # 使用order作为ID
                                    comic_id=comic_id,
                                    title=title,
                                    chapter_number=order,
                                    page_count=0,  # 页数将在获取图片时确定
                                    is_downloaded=False,
                                    download_path=None,
                                    source="picacg"
                                )
                                chapters.append(chapter)
                                
                                print(f"  章节 {order}: {title} (ID: {chapter_id})")
                                
                            except Exception as chapter_error:
                                print(f"❌ 处理章节 {i+1} 时出错: {chapter_error}")
                                continue
                    
                    print(f"✅ 成功获取 {len(chapters)} 个章节")
                    self.chapters_completed.emit(chapters)
                    return
                    
                except Exception as parse_error:
                    print(f"❌ 解析章节响应失败: {parse_error}")
                    print(f"原始响应: {response.text[:500]}...")
                    self.chapters_failed.emit(f"Failed to parse chapters response: {str(parse_error)}")
                    return
            
            elif response.status_code == 401:
                print(f"❌ 章节API认证失败: 401")
                self.chapters_failed.emit("Authentication failed. Please login again.")
                return
            
            else:
                print(f"❌ 章节API错误: {response.status_code}")
                print(f"错误响应: {response.text[:200]}...")
                self.chapters_failed.emit(f"Chapters API failed: HTTP {response.status_code}")
                return
                
        except Exception as e:
            print(f"❌ 章节获取异常: {e}")
            self.chapters_failed.emit(f"Failed to get chapters: {str(e)}")
    

    
    def get_chapter_images(self, comic_id: str, chapter_id: str) -> None:
        """
        Get the list of image URLs for a chapter.
        
        This method performs operation directly and emits results via signals.
        
        Args:
            comic_id: Unique identifier for the comic
            chapter_id: Chapter order value (used in API: /comics/{id}/order/{order}/pages)
        """
        if not self._is_initialized:
            self.images_failed.emit("Adapter not initialized")
            return
        
        # Use thread pool to avoid blocking UI
        def images_worker():
            try:
                self._do_get_chapter_images(comic_id, chapter_id)
            except Exception as e:
                self.images_failed.emit(f"Chapter images worker failed: {str(e)}")
        
        # Submit to thread pool
        self._thread_pool.submit(images_worker)
    
    def _do_get_chapter_images(self, comic_id: str, chapter_id: str) -> None:
        """
        获取章节图片URL列表 - 简化版本
        
        只从API获取图片URL，不做任何测试。
        图片加载交给Qt处理，Qt会自动带正确的Headers。
        
        Args:
            comic_id: Comic identifier
            chapter_id: Chapter identifier (就是章节的order值)
        """
        try:
            import requests
            import urllib3
            
            # Disable SSL warnings
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            if not self._is_logged_in or not self._auth_token:
                self.images_failed.emit("Please login first")
                return
            
            print(f"🖼️ 获取图片URL: 漫画={comic_id}, 章节={chapter_id}")
            
            # 简单获取图片URL
            success = self._smart_get_images(comic_id, chapter_id)
            if not success:
                error_msg = "无法获取图片URL。请检查网络连接或稍后重试。"
                self.images_failed.emit(error_msg)
                    
        except Exception as e:
            print(f"❌ 图片获取异常: {e}")
            self.images_failed.emit(f"Failed to get chapter images: {str(e)}")
    
    def _smart_get_images(self, comic_id: str, chapter_id: str) -> bool:
        """
        获取图片URL列表 - 简化版本，只获取URL不测试
        
        Args:
            comic_id: 漫画ID
            chapter_id: 章节ID
            
        Returns:
            是否成功获取图片URL
        """
        try:
            import requests
            
            print(f"🖼️ 获取图片URL列表...")
            
            base_url = self._current_endpoint + "/"
            path = f"comics/{comic_id}/order/{chapter_id}/pages"
            pages_url = f"{self._current_endpoint}/{path}"
            
            # 获取带签名的请求头
            headers = self._get_signed_headers(base_url, path, "GET")
            headers["authorization"] = self._auth_token
            
            # 简单请求，不带page参数（与原版picacg-qt一致）
            response = requests.get(
                pages_url,
                headers=headers,
                timeout=15,
                verify=False
            )
            
            print(f"📥 API响应: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                # 检查响应格式
                if (data.get('code') == 200 and 
                    'data' in data and 
                    isinstance(data['data'], dict) and
                    'pages' in data['data']):
                    
                    pages_data = data['data']['pages']
                    
                    if isinstance(pages_data, dict):
                        docs = pages_data.get("docs", [])
                        total = pages_data.get("total", 0)
                        
                        print(f"✅ 找到 {len(docs)} 张图片 (总计 {total})")
                        
                        # 处理空白章节
                        if total == 0:
                            print(f"⚠️ 空白章节")
                            self.images_completed.emit([])
                            return True
                        
                        if docs:
                            # 提取图片URL - 只构建URL，不测试
                            image_urls = []
                            for i, page_data in enumerate(docs):
                                try:
                                    media = page_data.get("media")
                                    if media and media.get("fileServer") and media.get("path"):
                                        file_server = media.get("fileServer")
                                        path_img = media.get("path")
                                        
                                        # 构建URL - 交给Qt加载
                                        image_url = self._build_image_url(file_server, path_img)
                                        image_urls.append(image_url)
                                        
                                except Exception as img_error:
                                    print(f"❌ 处理图片 {i+1} 时出错: {img_error}")
                                    continue
                            
                            if image_urls:
                                print(f"✅ 成功获取 {len(image_urls)} 个图片URL")
                                self.images_completed.emit(image_urls)
                                return True
                
                print(f"❌ 响应格式错误")
                return False
                
            else:
                print(f"❌ HTTP错误: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ 获取图片URL异常: {e}")
            return False
    
    def login(self, credentials: Dict[str, str]) -> None:
        """
        Authenticate with PicACG.
        
        This method performs login directly and emits results via signals.
        
        Args:
            credentials: Dictionary containing 'email' and 'password'
        """
        if not self._is_initialized:
            self.login_failed.emit("Adapter not initialized")
            return
        
        # Use thread pool to avoid blocking UI
        def login_worker():
            try:
                self._do_login(credentials)
            except Exception as e:
                self.login_failed.emit(f"Login worker failed: {str(e)}")
        
        # Submit to thread pool
        self._thread_pool.submit(login_worker)
    
    def _do_login(self, credentials: Dict[str, str]) -> None:
        """
        Internal method to perform login in worker thread.
        
        Args:
            credentials: Login credentials
        """
        try:
            import requests
            import urllib3
            
            # Disable SSL warnings
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            email = credentials.get('email', '')
            password = credentials.get('password', '')
            
            if not email or not password:
                self.login_completed.emit(False, "Email and password are required")
                return
            
            # 使用直接的HTTP请求进行登录，避免复杂的PicACG内部逻辑
            base_url = self._current_endpoint + "/"
            path = "auth/sign-in"
            login_url = f"{self._current_endpoint}/{path}"
            
            # 获取带签名的请求头
            headers = self._get_signed_headers(base_url, path, "POST")
            
            # 为IP服务器和反代服务器添加Host头
            if any(domain in self._current_endpoint for domain in ['104.21.91.145', '188.114.98.153', 'bika-api', 'bika2-api']):
                headers['Host'] = 'picaapi.picacomic.com'
            
            # 登录数据
            login_data = {
                'email': email,
                'password': password
            }
            
            response = requests.post(
                login_url,
                json=login_data,
                headers=headers,
                timeout=15,
                verify=False
            )
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get('data', {}).get('token'):
                        self._is_logged_in = True
                        self._auth_token = data['data']['token']
                        
                        # Store credentials in config for auto-login
                        self.config['credentials'] = {
                            'email': email,
                            'password': password
                        }
                        
                        self.login_completed.emit(True, "Login successful")
                        return
                    else:
                        self.login_completed.emit(False, "No token in response")
                        return
                except:
                    self.login_completed.emit(False, "Invalid response format")
                    return
            
            elif response.status_code == 400:
                try:
                    data = response.json()
                    error_msg = data.get('error', 'Bad request')
                    self.login_completed.emit(False, f"Login failed: {error_msg}")
                except:
                    self.login_completed.emit(False, "Bad request")
                return
            
            elif response.status_code == 401:
                self.login_completed.emit(False, "Invalid email or password")
                return
            
            else:
                self.login_completed.emit(False, f"HTTP {response.status_code}")
                return
                
        except Exception as e:
            self.login_failed.emit(f"Login failed: {str(e)}")
    
    def _get_user_info(self) -> None:
        """Get user information after login."""
        try:
            user_info_req = self._req_module.GetUserInfo()
            task = self._server._Send(self._server.Task(user_info_req), 0)
            
            if task.status == self._status.Ok:
                self._user.UpdateUserInfoBack(task)
                
        except Exception as e:
            # User info is not critical, just log the error
            pass
    
    def logout(self) -> None:
        """Logout from PicACG."""
        self._is_logged_in = False
        self._auth_token = None
        self._user.Logout()
        
        # Clear stored credentials
        if 'credentials' in self.config:
            del self.config['credentials']
    
    def is_logged_in(self) -> bool:
        """Check if user is logged in."""
        return self._is_logged_in
    
    def _build_image_url(self, original_server: str, path: str) -> str:
        """
        构建图片URL - 简单返回URL，交给Qt加载
        
        PicACG的图片需要特定的Headers（Referer/UA），
        Qt会自动处理这些，所以我们只需要返回正确的URL。
        
        Args:
            original_server: API返回的原始服务器URL
            path: 图片路径
            
        Returns:
            完整的图片URL
        """
        # 确保服务器URL格式正确
        if not original_server.startswith("http"):
            original_server = f"https://{original_server}"
        
        # 构建完整URL
        if "/static/" not in original_server:
            final_url = f"{original_server}/static/{path}"
        else:
            final_url = f"{original_server}/{path}"
        
        return final_url
    
    def cleanup(self) -> None:
        """Clean up resources including thread pool."""
        try:
            if hasattr(self, '_thread_pool'):
                self._thread_pool.shutdown(wait=False)
                print("✅ PicACG线程池已清理")
        except Exception as e:
            print(f"⚠️ PicACG线程池清理失败: {e}")
    
    def auto_login(self) -> None:
        """Attempt auto-login with stored credentials."""
        # Check if auto-login is enabled in config
        auto_login_enabled = self.config.get('auto_login', False)
        
        if not auto_login_enabled:
            print("ℹ️ PicACG自动登录未启用")
            return
        
        # Try credentials from config first
        if 'credentials' in self.config:
            credentials = self.config['credentials']
            if credentials.get('email') and credentials.get('password'):
                print(f"🔄 PicACG自动登录: {credentials.get('email')}")
                self.login(credentials)
                return
        
        # Fallback to direct config values
        email = self.config.get('email', '')
        password = self.config.get('password', '')
        
        if email and password:
            print(f"🔄 PicACG自动登录(备用): {email}")
            credentials = {'email': email, 'password': password}
            self.login(credentials)
        else:
            print("⚠️ PicACG自动登录: 缺少凭据")

    def download_chapter(
        self,
        comic: Comic,
        chapter: Chapter,
        download_path: str,
        progress_callback=None
    ) -> bool:
        """
        Download a chapter following the same structure as JMComic.
        
        Structure: download_path/picacg/comic_id/chapter_xxx/images
        
        Args:
            comic: Comic object
            chapter: Chapter to download
            download_path: Base download path
            progress_callback: Optional callback for progress updates
            
        Returns:
            True if download successful, False otherwise
        """
        try:
            import requests
            import urllib3
            import json
            from pathlib import Path
            from datetime import datetime
            
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            print(f"📥 下载章节: {comic.title} - {chapter.title}")
            
            # Create download directory structure: download_path/picacg/comic_id/
            source_dir = Path(download_path) / "picacg"
            comic_dir = source_dir / comic.id
            chapter_dir = comic_dir / f"chapter_{chapter.id}"
            chapter_dir.mkdir(parents=True, exist_ok=True)
            
            # Create or update comic metadata
            metadata_file = comic_dir / 'metadata.json'
            if not metadata_file.exists():
                metadata = {
                    'id': comic.id,
                    'title': comic.title,
                    'author': comic.author,
                    'cover_url': comic.cover_url,
                    'description': comic.description,
                    'tags': comic.tags,
                    'categories': comic.categories,
                    'status': comic.status,
                    'chapter_count': comic.chapter_count,
                    'view_count': comic.view_count,
                    'like_count': comic.like_count,
                    'is_favorite': comic.is_favorite,
                    'source': comic.source,
                    'created_at': datetime.now().isoformat(),
                    'chapters': {}
                }
                
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            # Get image URLs
            print(f"🔍 获取图片URL...")
            
            # We need to get images synchronously for download
            base_url = self._current_endpoint + "/"
            path = f"comics/{comic.id}/order/{chapter.id}/pages"
            pages_url = f"{self._current_endpoint}/{path}"
            
            headers = self._get_signed_headers(base_url, path, "GET")
            headers["authorization"] = self._auth_token
            
            response = requests.get(
                pages_url,
                headers=headers,
                timeout=15,
                verify=False
            )
            
            if response.status_code != 200:
                print(f"❌ 获取图片列表失败: HTTP {response.status_code}")
                return False
            
            data = response.json()
            
            if not (data.get('code') == 200 and 'data' in data):
                print(f"❌ 响应格式错误")
                return False
            
            pages_data = data['data'].get('pages', {})
            docs = pages_data.get('docs', [])
            
            if not docs:
                print(f"⚠️ 章节没有图片")
                return True  # Empty chapter is not an error
            
            print(f"📥 开始下载 {len(docs)} 张图片...")
            
            # Download each image
            for i, page_data in enumerate(docs):
                try:
                    media = page_data.get("media")
                    if not media or not media.get("fileServer") or not media.get("path"):
                        continue
                    
                    # Build image URL
                    file_server = media.get("fileServer")
                    path_img = media.get("path")
                    image_url = self._build_image_url(file_server, path_img)
                    
                    # Get file extension
                    original_name = media.get("originalName", f"page_{i+1}.jpg")
                    ext = Path(original_name).suffix or ".jpg"
                    
                    # Download image
                    image_path = chapter_dir / f"{i+1:03d}{ext}"
                    
                    if image_path.exists():
                        print(f"  ⏭️ 跳过已存在: {image_path.name}")
                        if progress_callback:
                            progress_callback(i + 1, len(docs))
                        continue
                    
                    # Use proper headers for image download
                    img_headers = {
                        'User-Agent': 'okhttp/3.8.1',
                        'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                    }
                    
                    img_response = requests.get(
                        image_url,
                        headers=img_headers,
                        timeout=30,
                        verify=False
                    )
                    
                    if img_response.status_code == 200:
                        image_path.write_bytes(img_response.content)
                        print(f"  ✅ 下载完成: {image_path.name}")
                    else:
                        print(f"  ❌ 下载失败: {image_path.name} (HTTP {img_response.status_code})")
                    
                    # Update progress
                    if progress_callback:
                        progress_callback(i + 1, len(docs))
                    
                except Exception as img_error:
                    print(f"  ❌ 下载图片 {i+1} 失败: {img_error}")
                    continue
            
            # Update metadata with chapter info
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                metadata['chapters'][chapter.id] = {
                    'id': chapter.id,
                    'title': chapter.title,
                    'chapter_number': chapter.chapter_number,
                    'page_count': len(docs),
                    'download_path': str(chapter_dir),
                    'downloaded_at': datetime.now().isoformat()
                }
                
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"⚠️ 更新metadata失败: {e}")
            
            # Mark chapter as downloaded
            chapter.is_downloaded = True
            chapter.download_path = str(chapter_dir)
            
            print(f"✅ 章节下载完成: {chapter.title} ({len(docs)} 张图片)")
            return True
            
        except Exception as e:
            print(f"❌ 下载章节失败: {e}")
            return False
