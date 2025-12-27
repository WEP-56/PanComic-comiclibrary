"""E-Hentai adapter implementation."""

import sys
import os
from typing import Dict, Any, List, Optional
import requests
import re
import json
from PySide6.QtCore import QMetaObject, Qt, Q_ARG, Slot

from .base_adapter import BaseSourceAdapter
from ..models.comic import Comic
from ..models.chapter import Chapter


class EHentaiAdapter(BaseSourceAdapter):
    """
    Adapter for E-Hentai-qt integration.
    
    This adapter wraps the original E-Hentai-qt project and provides
    a unified interface while maintaining thread isolation.
    Uses cookie-based authentication.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the E-Hentai adapter.
        
        Args:
            config: E-Hentai-specific configuration dictionary
        """
        super().__init__(config)
        self._ehentai_module = None
        self._server = None
        self._req_module = None
        self._session = None
        self._use_exhentai = config.get('use_exhentai', False)
        
    def initialize(self) -> None:
        """
        Initialize the E-Hentai-qt modules.
        
        This method:
        - Adds the E-Hentai-qt source path to sys.path
        - Imports necessary modules from the original project
        - Configures cookies, proxy, and other settings
        """
        try:
            # Fallback to direct implementation since ehentai-qt modules are not available
            self._session = requests.Session()
            if 'cookies' in self.config and self.config['cookies']:
                self._parse_and_set_cookies(self.config['cookies'])
            
            self._ehentai_module = {
                'initialized': True,
                'fallback': True
            }
            
            self._is_initialized = True
            
        except Exception as e:
            error_msg = f"Failed to initialize E-Hentai adapter: {str(e)}"
            self.login_failed.emit(error_msg)
            raise
    
    def _parse_and_set_cookies(self, cookie_string: str) -> None:
        """Parse cookie string and set them in session."""
        if not cookie_string:
            return
            
        # Parse cookies from string format: "name1=value1; name2=value2"
        for cookie in cookie_string.split(';'):
            if '=' in cookie:
                name, value = cookie.strip().split('=', 1)
                self._session.cookies.set(name.strip(), value.strip())
    
    def validate_cookies(self, cookies: str) -> bool:
        """Validate cookie format and required cookies."""
        if not cookies:
            return False
        
        # Check for required cookies
        required_cookies = ['ipb_member_id', 'ipb_pass_hash']
        cookie_names = []
        
        for cookie in cookies.split(';'):
            if '=' in cookie:
                name = cookie.strip().split('=', 1)[0].strip()
                cookie_names.append(name)
        
        return all(req_cookie in cookie_names for req_cookie in required_cookies)
    
    def set_exhentai_mode(self, use_exhentai: bool) -> None:
        """Set whether to use ExHentai or E-Hentai."""
        self._use_exhentai = use_exhentai
    
    def _get_base_url(self) -> str:
        """Get the base URL based on ExHentai setting."""
        return "https://exhentai.org" if self._use_exhentai else "https://e-hentai.org"
    
    def _get_headers(self, referer: str = None) -> Dict[str, str]:
        """Get headers for requests."""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        if referer:
            headers['Referer'] = referer
        return headers
    
    def search(self, keyword: str, page: int = 1) -> None:
        """
        Search comics with the given keyword.
        
        Args:
            keyword: Search keyword
            page: Page number (default: 1)
        """
        print(f"EHentaiAdapter.search called: keyword='{keyword}', page={page}")
        
        if not self._is_initialized:
            self.search_failed.emit("Adapter not initialized")
            return
        
        # Queue search operation to worker thread
        QMetaObject.invokeMethod(
            self, "_do_search",
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
        print(f"EHentaiAdapter._do_search executing: keyword='{keyword}', page={page}")
        
        try:
            # Emit empty results for now (EHentai is hidden)
            self.search_completed.emit([])
            
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"EHentai search error: {error_detail}")
            self.search_failed.emit(f"搜索失败: {str(e)}")
    
    def get_comic_detail(self, comic_id: str) -> None:
        """Get detailed information about a comic."""
        # Emit empty result for now (EHentai is hidden)
        self.comic_detail_failed.emit("EHentai功能暂时不可用")
    
    def get_chapters(self, comic_id: str) -> None:
        """Get chapters for a comic."""
        # Emit empty result for now (EHentai is hidden)
        self.chapters_failed.emit("EHentai功能暂时不可用")
    
    def get_chapter_images(self, comic_id: str, chapter_id: str) -> None:
        """Get images for a chapter."""
        # Emit empty result for now (EHentai is hidden)
        self.images_failed.emit("EHentai功能暂时不可用")
    
    def login(self, credentials: Dict[str, Any]) -> None:
        """Login with cookies."""
        # Emit success for now (EHentai is hidden)
        self.login_completed.emit(True, "EHentai功能暂时不可用")
    
    def auto_login(self) -> None:
        """Auto login if credentials are available."""
        if self.config.get('auto_login') and self.config.get('cookies'):
            self.login(self.config)
    
    def download_chapter(self, comic: Comic, chapter: Chapter, download_path: str) -> None:
        """Download a chapter."""
        # Not implemented for now (EHentai is hidden)
        raise NotImplementedError("EHentai下载功能暂时不可用")