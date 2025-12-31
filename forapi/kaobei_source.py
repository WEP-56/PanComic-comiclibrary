# forapi/kaobei_source.py
"""
拷贝漫画 (Kaobei) API 封装
基于 ComicGUISpider 项目移植
"""
import re
import json
import httpx
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlencode

# 导入解密工具
from .kaobei_utils import KaobeiUtils


class KaobeiSource:
    """拷贝漫画异步 API 封装"""
    
    name = "kaobei"
    pc_domain = "www.2025copy.com"
    api_domain = "api.2025copy.com"
    
    # 从 ComicGUISpider 复制的 headers
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:145.0) Gecko/20100101 Firefox/145.0',
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
        'dnts': '3',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache',
    }
    
    api_headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1',
        'Accept': 'application/json',
        'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
        'Origin': f'https://{pc_domain}',
        'Connection': 'keep-alive',
        'Accept-Encoding': 'gzip, compress, br',
        'platform': '1',
        'version': '2025.07.15',
        'webp': '1',
        'region': '0'
    }
    
    def __init__(self, domain=None):
        self.domain = domain or self.api_domain
        self.pc_domain = self.pc_domain
        self.client = None
        
        # AES 密钥 (从 ComicGUISpider 获取)
        self.aes_key = None
        self._init_aes_key()
    
    def _init_aes_key(self):
        """初始化 AES 密钥"""
        # 使用 KaobeiUtils 获取密钥
        try:
            self.aes_key = KaobeiUtils.get_aes_key()
            print(f"[INFO] AES key initialized: {self.aes_key[:8] if self.aes_key else 'None'}...")
        except Exception as e:
            print(f"[WARN] Failed to initialize AES key: {e}")
            self.aes_key = None
    
    async def _get_client(self):
        """获取 httpx 客户端"""
        if not self.client:
            self.client = httpx.AsyncClient(
                headers=self.api_headers,
                timeout=30.0,
                follow_redirects=True
            )
        return self.client
    
    async def search(self, keyword: str, page: int = 1) -> Tuple[List[Dict], int]:
        """
        搜索漫画
        
        Args:
            keyword: 搜索关键词
            page: 页码 (从1开始)
            
        Returns:
            (comics_list, max_page)
        """
        try:
            client = await self._get_client()
            
            # 计算 offset (每页20条)
            offset = (page - 1) * 20
            
            # 构建搜索URL
            if self._is_special_search(keyword):
                url = self._build_special_search_url(keyword, offset)
            else:
                url = f'https://{self.domain}/api/v3/search/comic?platform=1&limit=20&offset={offset}&q_type=&_update=false&q={keyword}'
            
            response = await client.get(url)
            response.raise_for_status()
            
            data = response.json()
            results = data.get('results', {}).get('list', [])
            
            # 解析搜索结果
            comics = []
            for item in results:
                comic = self._parse_search_item(item)
                if comic:
                    comics.append(comic)
            
            # 计算最大页数 (假设每页20条)
            total = data.get('results', {}).get('total', len(comics))
            max_page = (total + 19) // 20  # 向上取整
            
            return comics, max_page
            
        except Exception as e:
            print(f"[ERROR] Kaobei search failed: {e}")
            return [], 1
    
    def _is_special_search(self, keyword: str) -> bool:
        """检查是否为特殊搜索 (更新、排名等)"""
        return bool(re.search(r"(更新|排名)", keyword))
    
    def _build_special_search_url(self, keyword: str, offset: int) -> str:
        """构建特殊搜索URL"""
        if "更新" in keyword:
            return f'https://{self.domain}/api/v3/update/newest?limit=20&offset={offset}&_update=false'
        elif "排名" in keyword:
            params = {'offset': offset, 'limit': 20, '_update': 'false', 'type': 1}
            
            # 解析排名参数
            time_match = re.search(r"([日周月总])", keyword)
            kind_match = re.search(r"(轻小说|男|女)", keyword)
            
            # 时间类型
            time_map = {"日": "day", "周": "week", "月": "month", "总": "total"}
            if time_match:
                params['date_type'] = time_map.get(time_match.group(1), "day")
            else:
                params['date_type'] = "day"
            
            # 受众类型
            if kind_match:
                kind = kind_match.group(1)
                if kind == "轻小说":
                    params['type'] = 5
                elif kind == "男":
                    params['audience_type'] = 'male'
                elif kind == "女":
                    params['audience_type'] = 'female'
            else:
                params['audience_type'] = 'male'  # 默认男性向
            
            return f'https://{self.domain}/api/v3/ranks?{urlencode(params)}'
        
        return f'https://{self.domain}/api/v3/search/comic?platform=1&limit=20&offset={offset}&q_type=&_update=false&q={keyword}'
    
    def _parse_search_item(self, item: dict) -> Optional[Dict]:
        """解析搜索结果项"""
        try:
            # 处理不同的数据结构 (搜索 vs 排名 vs 更新)
            comic_data = item
            if 'comic' in item:
                comic_data = item['comic']
            elif 'book' in item:
                comic_data = item['book']
            
            # 提取作者信息
            authors = []
            if 'author' in comic_data and comic_data['author']:
                if isinstance(comic_data['author'], list):
                    authors = [author.get('name', '') for author in comic_data['author']]
                else:
                    authors = [str(comic_data['author'])]
            
            return {
                "id": comic_data.get('path_word', ''),
                "title": comic_data.get('name', ''),
                "cover": self._build_cover_url(comic_data.get('cover', '')),
                "author": ', '.join(authors) if authors else '未知',
                "description": "获取章节信息中...",  # 初始显示，后续会更新
                "tags": [],  # API 中没有直接的标签信息
                "pages": 0,  # 需要从详情页获取
                "preview_url": f"https://{self.pc_domain}/comic/{comic_data.get('path_word', '')}"
            }
            
        except Exception as e:
            print(f"[WARN] Failed to parse search item: {e}")
            return None
    
    def _build_cover_url(self, cover_path: str) -> str:
        """构建封面图片URL"""
        if not cover_path:
            return ""
        
        if cover_path.startswith('http'):
            return cover_path
        
        # 拷贝漫画的封面URL格式
        return f"https://cover.2025copy.com{cover_path}"
    
    async def get_comic_details(self, comic_id: str) -> Dict:
        """
        获取漫画详情
        
        Args:
            comic_id: 漫画的 path_word
            
        Returns:
            漫画详情字典
        """
        try:
            client = await self._get_client()
            
            # 1. 获取章节列表
            chapters_url = f"https://{self.domain}/api/v3/comic/{comic_id}/group/default/chapters?limit=300&offset=0&_update=false"
            print(f"[DEBUG] Fetching chapters from: {chapters_url}")
            
            response = await client.get(chapters_url)
            response.raise_for_status()
            
            response_data = response.json()
            
            if 'results' not in response_data:
                raise ValueError("API response missing 'results' field")
            
            results = response_data['results']
            
            # 检查数据格式并获取章节列表
            if isinstance(results, dict) and 'list' in results:
                chapters_list = results['list']
                print(f"[INFO] Found {len(chapters_list)} chapters")
            else:
                raise ValueError(f"Unexpected chapters data format: {type(results)}")
            
            # 2. 获取漫画基本信息（从第一个章节的详情API获取）
            comic_info = {"name": f"漫画 {comic_id}", "author": [], "theme": [], "brief": ""}
            
            if chapters_list:
                first_chapter = chapters_list[0]
                chapter_id = first_chapter.get('uuid')
                
                if chapter_id:
                    print(f"[DEBUG] Fetching comic info from chapter: {chapter_id}")
                    chapter_detail_url = f"https://{self.domain}/api/v3/comic/{comic_id}/chapter2/{chapter_id}?_update=false&platform=1"
                    
                    try:
                        chapter_response = await client.get(chapter_detail_url)
                        chapter_response.raise_for_status()
                        chapter_data = chapter_response.json()
                        
                        if 'results' in chapter_data and 'comic' in chapter_data['results']:
                            comic_info_from_chapter = chapter_data['results']['comic']
                            comic_info = {
                                "name": comic_info_from_chapter.get('name', f"漫画 {comic_id}"),
                                "author": [],  # 这个API似乎不包含作者信息
                                "theme": [],   # 这个API似乎不包含标签信息
                                "brief": f"共 {len(chapters_list)} 话",
                                "cover": ""    # 需要从其他地方获取
                            }
                            print(f"[INFO] Got comic info: {comic_info['name']}")
                    except Exception as e:
                        print(f"[WARN] Failed to get comic info from chapter API: {e}")
            
            # 3. 构建章节列表
            chapters = []
            for chapter in chapters_list:
                chapters.append({
                    "chapter_id": chapter.get('uuid', str(chapter.get('index', 0))),
                    "title": chapter.get('name', f"第{chapter.get('index', 0)+1}话"),
                    "group": "default",
                    "size": chapter.get('size', 0)
                })
            
            # 4. 构建返回数据
            return {
                "id": comic_id,
                "title": comic_info.get('name', f"漫画 {comic_id}"),
                "cover": self._build_cover_url(comic_info.get('cover', '')),
                "description": comic_info.get('brief', f"共 {len(chapters)} 话"),
                "authors": [author.get('name', '') for author in comic_info.get('author', [])] or ["未知"],
                "tags": [tag.get('name', '') for tag in comic_info.get('theme', [])],
                "category": "拷贝漫画",
                "pages": sum(ch.get('size', 0) for ch in chapters),
                "chapters": chapters
            }
            
        except Exception as e:
            print(f"[ERROR] Failed to get comic details: {e}")
            raise e
    
    async def get_chapter_images(self, comic_id: str, chapter_id: str) -> List[str]:
        """
        获取章节图片列表
        
        Args:
            comic_id: 漫画的 path_word
            chapter_id: 章节ID (uuid)
            
        Returns:
            图片URL列表
        """
        try:
            # 首先获取章节页面以获取 contentKey
            chapter_url = f"https://{self.pc_domain}/comic/{comic_id}/chapter/{chapter_id}"
            print(f"[DEBUG] Fetching chapter page: {chapter_url}")
            
            # 使用普通 headers 访问页面
            async with httpx.AsyncClient(headers=self.headers, timeout=30) as client:
                response = await client.get(chapter_url)
                response.raise_for_status()
                
                # 提取 contentKey
                content_key_match = re.search(r'var contentKey = ["\']([^"\']*)["\']', response.text)
                if not content_key_match:
                    print(f"[ERROR] contentKey not found in page")
                    print(f"[DEBUG] Page content length: {len(response.text)}")
                    # 尝试其他可能的模式
                    alt_patterns = [
                        r'contentKey\s*=\s*["\']([^"\']*)["\']',
                        r'"contentKey"\s*:\s*"([^"]*)"',
                        r'window\.contentKey\s*=\s*["\']([^"\']*)["\']'
                    ]
                    
                    for pattern in alt_patterns:
                        alt_match = re.search(pattern, response.text)
                        if alt_match:
                            content_key = alt_match.group(1)
                            print(f"[INFO] Found contentKey with alternative pattern: {pattern}")
                            break
                    else:
                        raise ValueError("无法找到 contentKey")
                else:
                    content_key = content_key_match.group(1)
                    print(f"[INFO] Found contentKey: {content_key[:20]}...")
                
                # 解密图片数据
                print(f"[DEBUG] Attempting to decrypt contentKey...")
                image_data = self._decrypt_chapter_data(content_key)
                
                # 提取图片URL
                image_urls = []
                if isinstance(image_data, list):
                    for img_item in image_data:
                        if isinstance(img_item, dict) and 'url' in img_item:
                            image_urls.append(img_item['url'])
                        elif isinstance(img_item, str):
                            # 如果直接是URL字符串
                            image_urls.append(img_item)
                elif isinstance(image_data, dict):
                    # 可能是其他格式的数据结构
                    if 'images' in image_data:
                        image_urls = image_data['images']
                    elif 'list' in image_data:
                        for item in image_data['list']:
                            if isinstance(item, dict) and 'url' in item:
                                image_urls.append(item['url'])
                
                print(f"[INFO] Found {len(image_urls)} images")
                if image_urls:
                    print(f"[DEBUG] First image URL: {image_urls[0][:80]}...")
                
                return image_urls
                
        except Exception as e:
            print(f"[ERROR] Failed to get chapter images: {e}")
            print(f"[DEBUG] Comic ID: {comic_id}, Chapter ID: {chapter_id}")
            raise e
    
    def _decrypt_chapter_data(self, encrypted_data) -> any:
        """
        解密章节数据
        
        使用 KaobeiUtils 进行实际解密
        """
        try:
            # 检查数据类型和格式
            if isinstance(encrypted_data, dict):
                # 如果已经是字典，可能不需要解密
                print("[DEBUG] Data is already a dict, no decryption needed")
                return encrypted_data
            
            if isinstance(encrypted_data, str):
                print(f"[DEBUG] Decrypting string data, length: {len(encrypted_data)}")
                return KaobeiUtils.decrypt_chapter_data(encrypted_data)
            
            # 其他类型，尝试转换为字符串
            encrypted_str = str(encrypted_data)
            print(f"[DEBUG] Converting to string and decrypting, length: {len(encrypted_str)}")
            return KaobeiUtils.decrypt_chapter_data(encrypted_str)
            
        except Exception as e:
            print(f"[ERROR] Failed to decrypt chapter data: {e}")
            print(f"[DEBUG] Data type: {type(encrypted_data)}")
            print(f"[DEBUG] Data content: {str(encrypted_data)[:200]}...")
            
            # 如果解密失败，返回占位符数据以便调试
            if isinstance(encrypted_data, str) and len(encrypted_data) < 100:
                # 图片数据解密失败
                return [{"url": "https://example.com/placeholder.jpg"}]
            else:
                # 章节数据解密失败
                return {
                    "build": {
                        "name": "解密失败",
                        "cover": "",
                        "brief": "解密功能出现问题，请检查API响应格式",
                        "author": [{"name": "未知"}],
                        "theme": [{"name": "解密失败"}],
                        "region": {"display": "未知"}
                    },
                    "groups": {
                        "default": {
                            "chapters": [
                                {
                                    "id": 1,
                                    "name": "解密失败",
                                    "size": 0
                                }
                            ]
                        }
                    }
                }
    
    async def close(self):
        """关闭客户端"""
        if self.client:
            await self.client.aclose()
            self.client = None


class KaobeiSourceSync:
    """拷贝漫画同步版本 - 避免事件循环冲突"""
    
    def __init__(self, domain=None):
        self.async_source = KaobeiSource(domain)
    
    def search(self, keyword: str, page: int = 1) -> Tuple[List[Dict], int]:
        """同步搜索"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果已经在事件循环中，创建新的事件循环
                import threading
                result = [None]
                exception = [None]
                
                def run_async():
                    try:
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        result[0] = new_loop.run_until_complete(self.async_source.search(keyword, page))
                        new_loop.close()
                    except Exception as e:
                        exception[0] = e
                
                thread = threading.Thread(target=run_async)
                thread.start()
                thread.join()
                
                if exception[0]:
                    raise exception[0]
                return result[0]
            else:
                return loop.run_until_complete(self.async_source.search(keyword, page))
        except RuntimeError:
            # 没有事件循环，创建新的
            return asyncio.run(self.async_source.search(keyword, page))
    
    def get_comic_details(self, comic_id: str) -> Dict:
        """同步获取漫画详情"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import threading
                result = [None]
                exception = [None]
                
                def run_async():
                    try:
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        result[0] = new_loop.run_until_complete(self.async_source.get_comic_details(comic_id))
                        new_loop.close()
                    except Exception as e:
                        exception[0] = e
                
                thread = threading.Thread(target=run_async)
                thread.start()
                thread.join()
                
                if exception[0]:
                    raise exception[0]
                return result[0]
            else:
                return loop.run_until_complete(self.async_source.get_comic_details(comic_id))
        except RuntimeError:
            return asyncio.run(self.async_source.get_comic_details(comic_id))
    
    def get_chapter_images(self, comic_id: str, chapter_id: str) -> List[str]:
        """同步获取章节图片"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import threading
                result = [None]
                exception = [None]
                
                def run_async():
                    try:
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        result[0] = new_loop.run_until_complete(self.async_source.get_chapter_images(comic_id, chapter_id))
                        new_loop.close()
                    except Exception as e:
                        exception[0] = e
                
                thread = threading.Thread(target=run_async)
                thread.start()
                thread.join()
                
                if exception[0]:
                    raise exception[0]
                return result[0]
            else:
                return loop.run_until_complete(self.async_source.get_chapter_images(comic_id, chapter_id))
        except RuntimeError:
            return asyncio.run(self.async_source.get_chapter_images(comic_id, chapter_id))
    
    def close(self):
        """关闭资源"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import threading
                
                def run_async():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    new_loop.run_until_complete(self.async_source.close())
                    new_loop.close()
                
                thread = threading.Thread(target=run_async)
                thread.start()
                thread.join()
            else:
                loop.run_until_complete(self.async_source.close())
        except RuntimeError:
            asyncio.run(self.async_source.close())