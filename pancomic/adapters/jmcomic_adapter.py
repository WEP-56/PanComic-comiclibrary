"""JMComic adapter implementation."""

import sys
import os
from typing import Dict, Any, List, Callable
from PySide6.QtCore import QMetaObject, Qt, Q_ARG, Slot

from .base_adapter import BaseSourceAdapter
from ..models.comic import Comic
from ..models.chapter import Chapter


class JMComicAdapter(BaseSourceAdapter):
    """
    Adapter for JMComic-qt integration.
    
    This adapter wraps the original JMComic-qt project and provides
    a unified interface while maintaining thread isolation.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the JMComic adapter.
        
        Args:
            config: JMComic-specific configuration dictionary
        """
        super().__init__(config)
        self._jmcomic_module = None
        
    def initialize(self) -> None:
        """
        Initialize the JMComic-qt modules.
        
        This method:
        - Adds the JMComic-qt source path to sys.path
        - Imports necessary modules from the original project
        - Configures domain, proxy, and other settings
        - Marks the adapter as initialized
        
        Note: JMComic API currently returns "Not legal" for all requests.
        This module is temporarily disabled until the API issue is resolved.
        """
        try:
            # Add JMComic-qt source path to sys.path
            jmcomic_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'forapi', 'jmcomic', 'src'
            )
            
            if jmcomic_path not in sys.path:
                sys.path.insert(0, jmcomic_path)
            
            # Import JMComic modules
            from server import req as jm_req
            from server.server import Server
            from config.global_config import GlobalConfig
            from config.setting import Setting
            from config import config
            from qt_owner import QtOwner
            
            # Set API endpoint from config (default to mode 1 = cdnbea.club - 新的可用域名)
            api_endpoint = self.config.get('api_endpoint', 1)
            Setting.ProxySelectIndex.SetValue(api_endpoint)
            
            print(f"[JMComic] Using API endpoint index: {api_endpoint}")
            print(f"[JMComic] API URL: {GlobalConfig.GetApiUrl()}")
            print(f"[JMComic] HeaderVer: {GlobalConfig.HeaderVer.value}")
            
            # 创建 Server
            self._jmcomic_module = {
                'req': jm_req,
                'server': Server(),
                'global_config': GlobalConfig,
                'qt_owner': QtOwner(),
                'config': config
            }
            
            # Configure domain from config
            if 'domain' in self.config:
                # Set domain configuration
                pass
            
            # Configure proxy from config
            if 'proxy' in self.config and self.config['proxy'].get('enabled'):
                # Set proxy configuration
                pass
            
            self._is_initialized = True
            
        except Exception as e:
            error_msg = f"Failed to initialize JMComic adapter: {str(e)}"
            print(f"[JMComic] {error_msg}")
            # 不抛出异常，让应用继续运行
            self._is_initialized = False
    
    def search(self, keyword: str, page: int = 1) -> None:
        """
        Search comics with the given keyword.
        
        This method queues the search operation to the worker thread.
        Results are emitted via search_completed signal.
        
        Args:
            keyword: Search keyword
            page: Page number (default: 1)
        """
        if not self._is_initialized:
            self.search_failed.emit("Adapter not initialized")
            return
        
        # Queue the search operation to worker thread
        QMetaObject.invokeMethod(
            self,
            "_do_search",
            Qt.QueuedConnection,
            Q_ARG(str, keyword),
            Q_ARG(int, page)
        )
    
    @Slot(str, int)
    def _do_search(self, keyword: str, page: int) -> None:
        """
        Internal method to perform search in worker thread.
        
        Args:
            keyword: Search keyword
            page: Page number
        """
        try:
            import json
            
            # 检查模块是否初始化
            if not self._jmcomic_module:
                self.search_failed.emit("JMComic 模块未初始化，API 暂时不可用")
                return
            
            # Get JMComic modules
            jm_req = self._jmcomic_module['req']
            server = self._jmcomic_module['server']
            
            # 打印当前分流设置
            from config.setting import Setting
            from tools.tool import ToolUtil
            
            print(f"JMComic search: Searching for '{keyword}', page {page}")
            print(f"JMComic search: ProxySelectIndex={Setting.ProxySelectIndex.value}")
            
            # Create search request
            search_req = jm_req.GetSearchReq2(keyword, page=page)
            print(f"JMComic search: Request URL: {search_req.url}")
            
            # Send request synchronously
            res = server.Send(search_req, isASync=False)
            
            if not res:
                self.search_failed.emit("搜索请求失败：无响应")
                return
            
            # 检查响应状态
            print(f"JMComic search: Response code: {res.code}")
            if res.code != 200:
                self.search_failed.emit(f"搜索请求失败：HTTP {res.code}")
                return
            
            # 获取原始响应并解密 - 参考 GetSearchReq2Handler
            raw_text = res.GetText()
            if not raw_text:
                self.search_failed.emit("搜索响应为空")
                return
            
            print(f"JMComic search: Raw response length: {len(raw_text)}")
            
            # 解析 JSON 响应
            response_data = json.loads(raw_text)
            code = response_data.get("code")
            error_msg = response_data.get("errorMsg", "")
            message = response_data.get("message", "")
            
            if code != 200:
                final_error = error_msg or message or "搜索失败"
                print(f"JMComic search: API error: {final_error}")
                self.search_failed.emit(f"搜索失败：{final_error}")
                return
            
            # 解密 data 字段
            encrypted_data = response_data.get("data")
            if not encrypted_data:
                self.search_failed.emit("响应中没有数据")
                return
            
            # 使用 search_req.ParseData 解密数据
            decrypted_data = search_req.ParseData(encrypted_data)
            
            # 使用 ToolUtil.ParseSearch2 解析搜索结果
            total, book_list = ToolUtil.ParseSearch2(decrypted_data)
            
            print(f"JMComic search: Found {len(book_list)} books, total: {total}")
            
            # Convert book_list to our Comic objects
            comics = []
            GlobalConfig = self._jmcomic_module['global_config']
            
            for book in book_list:
                try:
                    # BookInfo 对象结构: book.baseInfo.id, book.baseInfo.title, etc.
                    # 获取分类
                    categories = []
                    if hasattr(book, 'baseInfo') and hasattr(book.baseInfo, 'category'):
                        categories = book.baseInfo.category if book.baseInfo.category else []
                    
                    # 获取封面 URL
                    cover_url = ""
                    if hasattr(book, 'baseInfo') and hasattr(book.baseInfo, 'coverUrl') and book.baseInfo.coverUrl:
                        img_url = GlobalConfig.GetImgUrl()
                        cover_url = f"{img_url}{book.baseInfo.coverUrl}"
                    
                    # 获取基本信息 - 注意 id 在 baseInfo 中
                    book_id = str(book.baseInfo.id) if hasattr(book, 'baseInfo') and hasattr(book.baseInfo, 'id') else ''
                    title = book.baseInfo.title if hasattr(book, 'baseInfo') and hasattr(book.baseInfo, 'title') else ''
                    author = book.baseInfo.author if hasattr(book, 'baseInfo') and hasattr(book.baseInfo, 'author') else '未知'
                    
                    if not book_id:
                        print(f"JMComic search: Skipping book with no ID")
                        continue
                    
                    comic = Comic(
                        id=book_id,
                        title=title,
                        author=author,
                        cover_url=cover_url,
                        description=None,
                        tags=[],
                        categories=categories,
                        status="ongoing",
                        chapter_count=0,
                        view_count=0,
                        like_count=0,
                        is_favorite=False,
                        source="jmcomic"
                    )
                    comics.append(comic)
                except Exception as e:
                    print(f"JMComic search: Error converting book: {e}")
                    continue
            
            print(f"JMComic search: Returning {len(comics)} comics")
            self.search_completed.emit(comics)
            
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"JMComic search error: {error_detail}")
            # 检查是否是 "Not legal" 相关的错误
            if "Not legal" in str(e) or "not 'list'" in str(e):
                self.search_failed.emit("JMComic API 暂时不可用")
            else:
                self.search_failed.emit(f"搜索失败: {str(e)}")
    
    def get_comic_detail(self, comic_id: str) -> None:
        """
        Get detailed information about a comic.
        
        This method queues the operation to the worker thread.
        Results are emitted via comic_detail_completed signal.
        
        Args:
            comic_id: Unique identifier for the comic
        """
        if not self._is_initialized:
            self.comic_detail_failed.emit("Adapter not initialized")
            return
        
        QMetaObject.invokeMethod(
            self,
            "_do_get_comic_detail",
            Qt.QueuedConnection,
            Q_ARG(str, comic_id)
        )
    
    @Slot(str)
    def _do_get_comic_detail(self, comic_id: str) -> None:
        """
        Internal method to get comic detail in worker thread.
        
        Args:
            comic_id: Comic identifier
        """
        try:
            # Placeholder implementation - will integrate with actual JMComic API
            # For now, create a dummy comic
            comic = None
            
            if comic:
                self.comic_detail_completed.emit(comic)
            else:
                self.comic_detail_failed.emit(f"Comic not found: {comic_id}")
                
        except Exception as e:
            self.comic_detail_failed.emit(f"Failed to get comic detail: {str(e)}")
    
    def get_chapters(self, comic_id: str) -> None:
        """
        Get the list of chapters for a comic.
        
        This method queues the operation to the worker thread.
        Results are emitted via chapters_completed signal.
        
        Args:
            comic_id: Unique identifier for the comic
        """
        if not self._is_initialized:
            self.chapters_failed.emit("Adapter not initialized")
            return
        
        QMetaObject.invokeMethod(
            self,
            "_do_get_chapters",
            Qt.QueuedConnection,
            Q_ARG(str, comic_id)
        )
    
    @Slot(str)
    def _do_get_chapters(self, comic_id: str) -> None:
        """
        Internal method to get chapters in worker thread.
        
        Args:
            comic_id: Comic identifier
        """
        try:
            if not self._jmcomic_module:
                self.chapters_failed.emit("JMComic module not loaded")
                return
            
            # Import required classes
            req = self._jmcomic_module['req']
            
            # Get server instance
            server = self._jmcomic_module['server']
            
            # Create book info request
            book_req = req.GetBookInfoReq2(comic_id)
            
            # Execute request
            res = server.Send(book_req, isASync=False)
            
            if res and res.code == 200:
                book_data = res
                
                # Parse chapters from book data
                chapters = []
                
                # JMComic books typically have episodes/chapters
                if hasattr(book_data, 'series') and book_data.series:
                    for idx, episode in enumerate(book_data.series):
                        chapter = Chapter(
                            id=str(episode.id),
                            comic_id=comic_id,
                            title=episode.name or f"第 {idx + 1} 话",
                            chapter_number=idx + 1,
                            page_count=len(episode.images) if hasattr(episode, 'images') else 0,
                            is_downloaded=False,
                            download_path=None,
                            source="jmcomic"
                        )
                        chapters.append(chapter)
                elif hasattr(book_data, 'eps') and book_data.eps:
                    # Episodes format
                    for idx, episode in enumerate(book_data.eps):
                        chapter = Chapter(
                            id=str(episode.id),
                            comic_id=comic_id,
                            title=episode.title or f"第 {idx + 1} 话",
                            chapter_number=idx + 1,
                            page_count=0,  # Will be determined when loading images
                            is_downloaded=False,
                            download_path=None,
                            source="jmcomic"
                        )
                        chapters.append(chapter)
                else:
                    # Single chapter comic
                    chapter = Chapter(
                        id=comic_id,
                        comic_id=comic_id,
                        title="完整版",
                        chapter_number=1,
                        page_count=0,  # Will be determined when loading images
                        is_downloaded=False,
                        download_path=None,
                        source="jmcomic"
                    )
                    chapters.append(chapter)
                
                self.chapters_completed.emit(chapters)
            else:
                # Fallback: create a single chapter for the comic
                chapter = Chapter(
                    id=comic_id,
                    comic_id=comic_id,
                    title="完整版",
                    chapter_number=1,
                    page_count=0,
                    is_downloaded=False,
                    download_path=None,
                    source="jmcomic"
                )
                self.chapters_completed.emit([chapter])
            
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"JMComic chapters error: {error_detail}")
            
            # Fallback: create a single chapter
            try:
                chapter = Chapter(
                    id=comic_id,
                    comic_id=comic_id,
                    title="完整版",
                    chapter_number=1,
                    page_count=0,
                    is_downloaded=False,
                    download_path=None,
                    source="jmcomic"
                )
                self.chapters_completed.emit([chapter])
            except:
                self.chapters_failed.emit(f"Failed to get chapters: {str(e)}")
    
    def get_chapter_images(self, comic_id: str, chapter_id: str) -> None:
        """
        Get the list of image URLs for a chapter.
        
        This method queues the operation to the worker thread.
        Results are emitted via images_completed signal.
        
        Args:
            comic_id: Unique identifier for the comic
            chapter_id: Unique identifier for the chapter
        """
        if not self._is_initialized:
            self.images_failed.emit("Adapter not initialized")
            return
        
        QMetaObject.invokeMethod(
            self,
            "_do_get_chapter_images",
            Qt.QueuedConnection,
            Q_ARG(str, comic_id),
            Q_ARG(str, chapter_id)
        )
    
    @Slot(str, str)
    def _do_get_chapter_images(self, comic_id: str, chapter_id: str) -> None:
        """
        Internal method to get chapter images in worker thread.
        
        Args:
            comic_id: Comic identifier
            chapter_id: Chapter identifier
        """
        try:
            if not self._jmcomic_module:
                self.images_failed.emit("JMComic module not loaded")
                return
            
            # Import required classes
            req = self._jmcomic_module['req']
            server = self._jmcomic_module['server']
            
            # Create chapter info request
            chapter_req = req.GetBookEpsInfoReq2(comic_id, chapter_id)
            
            # Execute request
            res = server.Send(chapter_req, isASync=False)
            
            if res and res.code == 200:
                # Parse JMComic response
                import json
                
                try:
                    # Get response text and parse JSON
                    response_text = res.GetText()
                    if not response_text:
                        self.images_failed.emit("Empty response")
                        return
                    
                    # Parse JSON response
                    json_data = json.loads(response_text)
                    
                    if json_data.get('code') != 200:
                        error_msg = json_data.get('message', 'Unknown error')
                        self.images_failed.emit(f"API error: {error_msg}")
                        return
                    
                    # Decrypt the data
                    encrypted_data = json_data.get('data')
                    if not encrypted_data:
                        self.images_failed.emit("No data in response")
                        return
                    
                    # Use the request's ParseData method to decrypt
                    decrypted_data = chapter_req.ParseData(encrypted_data)
                    chapter_data = json.loads(decrypted_data)
                    
                    # Parse image URLs from decrypted data
                    image_urls = []
                    images = chapter_data.get('images', [])
                    
                    if images:
                        # Get image server URL
                        GlobalConfig = self._jmcomic_module['global_config']
                        img_server = GlobalConfig.GetImgUrl()
                        
                        # Extract chapter ID for image paths
                        chapter_id_for_path = chapter_data.get('id', chapter_id)
                        
                        for image_name in images:
                            # Construct image URL: {img_server}/media/photos/{chapter_id}/{image_name}
                            image_url = f"{img_server}/media/photos/{chapter_id_for_path}/{image_name}"
                            image_urls.append(image_url)
                    
                except (json.JSONDecodeError, KeyError, AttributeError) as e:
                    print(f"Failed to parse chapter response: {e}")
                    self.images_failed.emit(f"Failed to parse response: {str(e)}")
                    return
                
                if image_urls:
                    print(f"Found {len(image_urls)} images for chapter {chapter_id}")
                    self.images_completed.emit(image_urls)
                else:
                    print(f"No images found for chapter {chapter_id}")
                    self.images_failed.emit("No images found in chapter")
            else:
                error_msg = f"Failed to get chapter data (code: {res.code if res else 'None'})"
                print(error_msg)
                self.images_failed.emit(error_msg)
            
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"JMComic chapter images error: {error_detail}")
            self.images_failed.emit(f"Failed to get chapter images: {str(e)}")
    
    def update_proxy_settings(self, api_index: int, img_index: int, cdn_api_ip: str, cdn_img_ip: str) -> None:
        """
        更新分流设置
        
        Args:
            api_index: API分流索引 (1-6)
            img_index: 图片分流索引 (1-6)
            cdn_api_ip: CDN API IP地址
            cdn_img_ip: CDN 图片 IP地址
        """
        if not self._is_initialized:
            return
        
        try:
            from config.setting import Setting
            from config.global_config import GlobalConfig
            from tools.tool import ToolUtil
            
            # 获取已初始化的 Server 实例
            server = self._jmcomic_module['server']
            
            # 设置分流索引
            Setting.ProxySelectIndex.SetValue(api_index)
            Setting.ProxyImgSelectIndex.SetValue(img_index)
            
            # 设置CDN地址
            if cdn_api_ip:
                Setting.PreferCDNIP.SetValue(cdn_api_ip)
            if cdn_img_ip:
                Setting.PreferCDNIPImg.SetValue(cdn_img_ip)
            
            # 更新DNS - CDN分流需要特殊处理
            from server.server import host_table
            
            if api_index == 5 and cdn_api_ip:
                address = cdn_api_ip
                # CDN分流需要把cdnxxx-proxy.vip映射到CDN IP
                cdn_domain = ToolUtil.GetUrlHost(GlobalConfig.CdnApiUrl.value)
                host_table[cdn_domain] = cdn_api_ip
            else:
                address = ""
            
            if img_index == 5 and cdn_img_ip:
                img_address = cdn_img_ip
                cdn_img_domain = ToolUtil.GetUrlHost(GlobalConfig.CdnImgUrl.value)
                host_table[cdn_img_domain] = cdn_img_ip
            else:
                img_address = ""
            
            # 使用已初始化的 server 实例更新 DNS 和代理
            server.UpdateDns(address, img_address)
            server.UpdateProxy()
            
            print(f"[JMComic] 分流设置已更新: API={api_index}, IMG={img_index}, CDN_API={cdn_api_ip}, CDN_IMG={cdn_img_ip}")
            print(f"[JMComic] 当前API URL: {GlobalConfig.GetApiUrl()}")
            
        except Exception as e:
            import traceback
            print(f"[JMComic] 更新分流设置失败: {e}")
            traceback.print_exc()
    
    def login(self, credentials: Dict[str, str]) -> None:
        """
        Authenticate with JMComic.
        
        This method queues the authentication operation to the worker thread.
        Results are emitted via login_completed signal.
        
        Args:
            credentials: Dictionary containing 'username' and 'password'
        """
        if not self._is_initialized:
            self.login_failed.emit("Adapter not initialized")
            return
        
        # Serialize credentials as JSON string for Qt meta system
        import json
        credentials_json = json.dumps(credentials)
        
        QMetaObject.invokeMethod(
            self,
            "_do_login",
            Qt.QueuedConnection,
            Q_ARG(str, credentials_json)
        )
    
    @Slot(str)
    def _do_login(self, credentials_json: str) -> None:
        """
        Internal method to perform login in worker thread.
        
        Args:
            credentials_json: JSON string of login credentials
        """
        try:
            import json
            credentials = json.loads(credentials_json)
            username = credentials.get('username', '')
            password = credentials.get('password', '')
            
            if not username or not password:
                self.login_completed.emit(False, "用户名和密码不能为空")
                return
            
            # Get JMComic modules
            jm_req = self._jmcomic_module['req']
            server = self._jmcomic_module['server']
            qt_owner = self._jmcomic_module['qt_owner']
            global_config = self._jmcomic_module['global_config']
            
            # 打印当前分流设置
            from config.setting import Setting
            from server.server import host_table
            from tools.tool import ToolUtil
            
            print(f"[JMComic Login] ProxySelectIndex: {Setting.ProxySelectIndex.value}")
            print(f"[JMComic Login] API URL: {global_config.GetApiUrl()}")
            print(f"[JMComic Login] host_table: {host_table}")
            
            # Create login request
            login_req = jm_req.LoginReq2(username, password)
            print(f"[JMComic Login] Request URL: {login_req.url}")
            
            # Send request synchronously (returns BaseRes directly)
            res = server.Send(login_req, isASync=False)
            
            print(f"[JMComic Login] Response code: {res.code if res else 'None'}")
            
            # Parse response - 参考 LoginReq2Handler 的实现
            if res and res.code == 200:
                # 获取原始响应文本
                raw_text = res.GetText()
                print(f"[JMComic Login] Raw response: {raw_text[:500] if raw_text else 'None'}")
                
                if not raw_text:
                    self.login_completed.emit(False, "登录响应为空")
                    return
                
                # 解析 JSON 响应
                response_data = json.loads(raw_text)
                code = response_data.get("code")
                error_msg = response_data.get("errorMsg", "")
                message = response_data.get("message", "")
                
                print(f"[JMComic Login] Response code in JSON: {code}")
                
                if code != 200:
                    # 登录失败
                    final_error = error_msg or message or "登录失败"
                    print(f"[JMComic Login] 登录失败: {final_error}")
                    self.login_completed.emit(False, final_error)
                    return
                
                # 解密 data 字段 - 这是关键步骤！
                encrypted_data = response_data.get("data")
                if not encrypted_data:
                    self.login_completed.emit(False, "响应中没有数据")
                    return
                
                print(f"[JMComic Login] Encrypted data length: {len(encrypted_data)}")
                
                # 使用 login_req.ParseData 解密数据
                decrypted_data = login_req.ParseData(encrypted_data)
                print(f"[JMComic Login] Decrypted data: {decrypted_data[:200] if decrypted_data else 'None'}")
                
                # 使用 ToolUtil.ParseLogin2 解析用户信息
                user = ToolUtil.ParseLogin2(decrypted_data)
                
                # 获取 cookies
                cookie_dict = {}
                if hasattr(res, 'raw') and hasattr(res.raw, 'cookies'):
                    for cookie in res.raw.cookies.jar:
                        cookie_dict[cookie.name] = cookie.value
                
                print(f"[JMComic Login] Login success! user_id: {user.uid}, cookies: {cookie_dict}")
                
                # 存储用户信息 - 使用 SetUser 方法或直接设置 user
                user.isLogin = True
                user.cookie = cookie_dict
                qt_owner.SetUser(user)
                
                self.login_completed.emit(True, f"登录成功！欢迎 {user.userName}")
            else:
                error_code = res.code if res else 'None'
                self.login_completed.emit(False, f"网络请求失败 (状态码: {error_code})")
                
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"JMComic login error: {error_detail}")
            self.login_completed.emit(False, f"登录失败: {str(e)}")
    
    def download_chapter(self, comic: 'Comic', chapter: 'Chapter', download_path: str, progress_callback: Callable = None) -> None:
        """
        Download a chapter to local storage.
        
        Args:
            comic: Comic being downloaded
            chapter: Chapter to download
            download_path: Base download path
            progress_callback: Callback for progress updates (current, total)
        """
        import os
        import json
        import requests
        import urllib3
        from pathlib import Path
        from datetime import datetime
        
        try:
            # Disable SSL warnings
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            # Create download directory structure: download_path/source/comic_id/
            source_dir = Path(download_path) / comic.source
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
            
            # Get chapter images
            if not self._is_initialized:
                raise Exception("Adapter not initialized")
            
            # Import required classes
            req = self._jmcomic_module['req']
            server = self._jmcomic_module['server']
            
            # Create chapter info request
            chapter_req = req.GetBookEpsInfoReq2(comic.id, chapter.id)
            
            # Execute request
            res = server.Send(chapter_req, isASync=False)
            
            if not res or res.code != 200:
                raise Exception(f"Failed to get chapter data (code: {res.code if res else 'None'})")
            
            # Parse chapter images
            import json
            response_text = res.GetText()
            if not response_text:
                raise Exception("Empty response")
            
            json_data = json.loads(response_text)
            if json_data.get('code') != 200:
                raise Exception(f"API error: {json_data.get('message', 'Unknown error')}")
            
            # Decrypt the data
            encrypted_data = json_data.get('data')
            if not encrypted_data:
                raise Exception("No data in response")
            
            decrypted_data = chapter_req.ParseData(encrypted_data)
            chapter_data = json.loads(decrypted_data)
            
            # Get image URLs
            images = chapter_data.get('images', [])
            if not images:
                raise Exception("No images found in chapter")
            
            # Get image server URL
            GlobalConfig = self._jmcomic_module['global_config']
            img_server = GlobalConfig.GetImgUrl()
            chapter_id_for_path = chapter_data.get('id', chapter.id)
            
            # Download images
            headers = {
                'User-Agent': 'Mozilla/5.0 (Linux; Android 7.1.2; DT1901A Build/N2G47O; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/86.0.4240.198 Mobile Safari/537.36',
                'Referer': 'https://www.jmapiproxyxxx.vip/',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            }
            
            session = requests.Session()
            session.headers.update(headers)
            
            total_images = len(images)
            
            for i, image_name in enumerate(images):
                # Construct image URL
                image_url = f"{img_server}/media/photos/{chapter_id_for_path}/{image_name}"
                
                # Download image
                response = session.get(image_url, timeout=30, verify=False)
                if response.status_code == 200:
                    # Descramble image using JMComic's algorithm
                    image_data = self._descramble_image_data(
                        response.content, 
                        chapter_id_for_path, 
                        chapter.id, 
                        image_name.split('.')[0] if '.' in image_name else image_name
                    )
                    
                    # Save image
                    image_path = chapter_dir / f"{i+1:03d}_{image_name}"
                    with open(image_path, 'wb') as f:
                        f.write(image_data)
                    
                    # Update progress
                    if progress_callback:
                        progress_callback(i + 1, total_images)
                else:
                    print(f"Failed to download image {image_name}: HTTP {response.status_code}")
            
            # Update metadata with chapter info
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                metadata['chapters'][chapter.id] = {
                    'id': chapter.id,
                    'title': chapter.title,
                    'chapter_number': chapter.chapter_number,
                    'page_count': total_images,
                    'download_path': str(chapter_dir),
                    'downloaded_at': datetime.now().isoformat()
                }
                
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"Failed to update metadata: {e}")
            
            # Mark chapter as downloaded
            chapter.is_downloaded = True
            chapter.download_path = str(chapter_dir)
            
            print(f"Successfully downloaded chapter: {chapter.title} ({total_images} images)")
            
        except Exception as e:
            print(f"Failed to download chapter {chapter.title}: {e}")
            raise
    
    def _descramble_image_data(self, image_data: bytes, eps_id: str, scramble_id: str, picture_name: str) -> bytes:
        """
        Descramble JMComic image data.
        
        Args:
            image_data: Raw image data
            eps_id: Episode ID
            scramble_id: Scramble ID
            picture_name: Picture name without extension
            
        Returns:
            Descrambled image data
        """
        try:
            # Import JMComic tools
            import sys
            import os
            
            # Add JMComic path for imports
            jmcomic_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'forapi', 'jmcomic', 'src'
            )
            if jmcomic_path not in sys.path:
                sys.path.insert(0, jmcomic_path)
            
            from tools.tool import ToolUtil
            
            # Descramble the image
            descrambled_data = ToolUtil.SegmentationPicture(
                image_data, 
                eps_id, 
                scramble_id, 
                picture_name
            )
            
            return descrambled_data
            
        except Exception as e:
            print(f"Failed to descramble image: {e}")
            # If descrambling fails, return original data
            return image_data
