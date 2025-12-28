# forapi/wnacg_source.py
"""
绅士漫画 (WNACG) API 封装
基于 ComicGUISpider 项目移植
"""
import re
import httpx
from lxml import etree
from urllib.parse import quote
from typing import List, Dict, Optional


class WNACGSource:
    """绅士漫画 API 封装"""
    
    name = "wnacg"
    publish_domain = "wn01.link"
    publish_url = f"https://{publish_domain}"
    
    # 从 ComicGUISpider 复制的 headers
    headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "user-agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Mobile Safari/537.36 Edg/133.0.0.0"
    }
    
    book_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'no-cache',
    }
    
    def __init__(self, domain=None):
        self.domain = domain
        self.client = None
    
    async def _get_client(self):
        """获取 httpx 客户端"""
        if not self.client:
            self.client = httpx.AsyncClient(
                headers=self.book_headers,
                timeout=30.0,
                follow_redirects=True
            )
        return self.client
    
    async def _get_domain(self):
        """从发布页获取可用域名"""
        # 如果已经有域名，直接返回
        if self.domain:
            return self.domain
        
        print("[INFO] 正在寻找可用域名...")
        
        try:
            print("[INFO] 从导航页获取域名...")
            async with httpx.AsyncClient() as client:
                resp = await client.get(self.publish_url, headers=self.headers)
                html = etree.HTML(resp.text)
                hrefs = html.xpath('//div[@class="main"]//li[not(contains(.,"發佈頁") or contains(.,"发布页"))]/a/@href')
                
                # 过滤掉无效链接
                valid_domains = []
                for href in hrefs:
                    domain = re.sub(r"https?://", "", href).strip("/")
                    if not re.search(r"google|email|link|wn01\.link", domain):
                        valid_domains.append(domain)
                
                print(f"[INFO] 导航页域名: {valid_domains}")
                
                # 测试域名可用性
                for domain in valid_domains:
                    print(f"[INFO] 测试域名: {domain}")
                    if await self._test_domain(domain):
                        self.domain = domain
                        print(f"[SUCCESS] 可用域名: {domain}")
                        return domain
                        
        except Exception as e:
            print(f"[WARN] 获取域名失败: {e}")
        
        # 使用默认域名
        print("[WARN] 使用默认域名")
        self.domain = "www.wnacg.com"
        return self.domain
    
    async def _test_domain(self, domain):
        """测试域名是否可用"""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"https://{domain}/", headers=self.headers, timeout=10)
                return resp.status_code == 200
        except:
            return False
    
    def _parse_search_item(self, target):
        """解析搜索结果项"""
        pic_elem = target.xpath('./div[contains(@class, "pic")]/a')
        if not pic_elem:
            return None
        
        pre_url = pic_elem[0].get('href')
        if not pre_url:
            return None
        
        # 提取 ID
        id_match = re.search(r'-aid-(\d+)', pre_url)
        if not id_match:
            return None
        
        gallery_id = id_match.group(1)
        
        # 标题
        title = pic_elem[0].get('title', '')
        
        # 封面
        img_elem = pic_elem[0].xpath('./img/@src')
        cover = ""
        if img_elem:
            cover = "https:" + img_elem[0] if img_elem[0].startswith("//") else img_elem[0]
        
        # 页数
        info_elem = target.xpath('.//div[contains(@class, "info_col")]/text()')
        pages = 0
        if info_elem:
            page_match = re.search(r'(\d+)[張张]', info_elem[0].strip())
            if page_match:
                pages = int(page_match.group(1))
        
        return {
            "id": gallery_id,
            "title": title,
            "cover": cover,
            "pages": pages,
            "preview_url": f"https://{self.domain}{pre_url}",
            "gallery_url": f"https://{self.domain}{pre_url.replace('index', 'gallery')}"
        }
    
    async def search(self, keyword: str, page: int = 1) -> tuple:
        """搜索漫画"""
        domain = await self._get_domain()
        url = f'https://{domain}/search/?f=_all&s=create_time_DESC&syn=yes&q={quote(keyword)}'
        if page > 1:
            url += f'&p={page}'
        
        client = await self._get_client()
        resp = await client.get(url, headers={"Referer": f"https://{domain}/"})
        resp.raise_for_status()
        
        html = etree.HTML(resp.text)
        results = []
        
        # 解析搜索结果
        targets = html.xpath('//li[contains(@class, "gallary_item")]')
        for target in targets:
            item = self._parse_search_item(target)
            if item:
                results.append(item)
        
        # 获取总页数
        max_page = 1
        total_elem = html.xpath('//p[@class="result"]/b/text()')
        if total_elem:
            try:
                total = int(total_elem[0].replace(',', ''))
                max_page = (total + 23) // 24  # 每页24个
            except:
                pass
        
        return results, max_page
    
    async def get_gallery_details(self, gallery_id: str) -> dict:
        """获取本子详情"""
        domain = await self._get_domain()
        url = f"https://{domain}/photos-index-page-1-aid-{gallery_id}.html"
        
        client = await self._get_client()
        resp = await client.get(url)
        resp.raise_for_status()
        
        html = etree.HTML(resp.text)
        
        # 标题
        title_elem = html.xpath('//div[@class="userwrap"]/h2/text()')
        title = title_elem[0].strip() if title_elem else ""
        
        # 封面
        cover_elem = html.xpath('//div[@class="userwrap"]//div[@class="asTBcell uwthumb"]/img/@src')
        cover = ""
        if cover_elem:
            cover = "https:" + cover_elem[0] if cover_elem[0].startswith("//") else cover_elem[0]
        
        # 分类和页数
        labels = html.xpath('//div[@class="asTBcell uwconn"]/label/text()')
        category, pages = "", 0
        for label in labels:
            if "分類" in label or "分类" in label:
                category = label.split("：")[-1].strip()
            elif "頁數" in label or "页数" in label:
                try:
                    # 提取数字部分，处理 "31P" 这样的格式
                    page_text = label.split("：")[-1].strip()
                    import re
                    page_match = re.search(r'(\d+)', page_text)
                    if page_match:
                        pages = int(page_match.group(1))
                except Exception as e:
                    print(f"[WARN] 解析页数失败: {label} -> {e}")
                    pass
        
        # 标签
        tags = [t.strip() for t in html.xpath('//a[@class="tagshow"]/text()') if t.strip()]
        
        # 描述
        desc_elem = html.xpath('//div[@class="asTBcell uwconn"]/p/text()')
        description = desc_elem[0].strip() if desc_elem else ""
        
        # 上传者
        uploader_elem = html.xpath('//div[@class="asTBcell uwuinfo"]/a/p/text()')
        uploader = uploader_elem[0].strip() if uploader_elem else ""
        
        return {
            "id": gallery_id,
            "title": title,
            "cover": cover,
            "category": category,
            "pages": pages,
            "tags": tags,
            "description": description,
            "uploader": uploader,
        }
    
    async def get_gallery_images(self, gallery_id: str) -> List[str]:
        """获取本子所有图片"""
        domain = await self._get_domain()
        url = f"https://{domain}/photos-gallery-aid-{gallery_id}.html"
        
        client = await self._get_client()
        referer = f"https://{domain}/photos-index-page-1-aid-{gallery_id}.html"
        resp = await client.get(url, headers={"Referer": referer})
        resp.raise_for_status()
        
        # 使用正则提取图片 URL（参考 ComicGUISpider 的方法）
        doc_wlns = re.split(r';[\n\s]+?document\.writeln', resp.text)
        selected_doc = next(filter(lambda _: "var imglist" in _, doc_wlns), "")
        
        if selected_doc:
            targets = re.findall(r'(//.*?(jp[e]?g|png|webp))', selected_doc)
            images = [f"https:{target[0]}" for target in targets]
        else:
            # 备用方法
            pattern = r'//[^"]+/[^"]+\.(jpg|jpeg|png|gif|webp)'
            matches = re.findall(pattern, resp.text, re.IGNORECASE)
            images = [f"https:{match}" for match in matches]
        
        return list(dict.fromkeys(images))  # 去重
    
    async def close(self):
        """关闭客户端"""
        if self.client:
            await self.client.aclose()


# 同步包装器
class WNACGSourceSync:
    """同步版本的 WNACG API，避免asyncio事件循环冲突"""
    
    def __init__(self, domain=None):
        self.domain = domain
        self.client = None
        self.publish_domain = "wn01.link"
        self.publish_url = f"https://{self.publish_domain}"
        
        # 从 ComicGUISpider 复制的 headers
        self.headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "user-agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Mobile Safari/537.36 Edg/133.0.0.0"
        }
        
        self.book_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'no-cache',
        }
    
    def _get_client(self):
        """获取 httpx 同步客户端"""
        if not self.client:
            import httpx
            self.client = httpx.Client(
                headers=self.book_headers,
                timeout=30.0,
                follow_redirects=True
            )
        return self.client
    
    def _get_domain(self):
        """从发布页获取可用域名（同步版本）"""
        # 如果已经有域名，直接返回
        if self.domain:
            return self.domain
        
        print("[INFO] 正在寻找可用域名...")
        
        try:
            print("[INFO] 从导航页获取域名...")
            import httpx
            with httpx.Client() as client:
                resp = client.get(self.publish_url, headers=self.headers)
                html = etree.HTML(resp.text)
                hrefs = html.xpath('//div[@class="main"]//li[not(contains(.,"發佈頁") or contains(.,"发布页"))]/a/@href')
                
                # 过滤掉无效链接
                valid_domains = []
                for href in hrefs:
                    domain = re.sub(r"https?://", "", href).strip("/")
                    if not re.search(r"google|email|link|wn01\.link", domain):
                        valid_domains.append(domain)
                
                print(f"[INFO] 导航页域名: {valid_domains}")
                
                # 测试域名可用性
                for domain in valid_domains:
                    print(f"[INFO] 测试域名: {domain}")
                    if self._test_domain(domain):
                        self.domain = domain
                        print(f"[SUCCESS] 可用域名: {domain}")
                        return domain
                        
        except Exception as e:
            print(f"[WARN] 获取域名失败: {e}")
        
        # 使用默认域名
        print("[WARN] 使用默认域名")
        self.domain = "www.wnacg.com"
        return self.domain
    
    def _test_domain(self, domain):
        """测试域名是否可用（同步版本）"""
        try:
            import httpx
            with httpx.Client() as client:
                resp = client.get(f"https://{domain}/", headers=self.headers, timeout=10)
                return resp.status_code == 200
        except:
            return False
    
    def _parse_search_item(self, target):
        """解析搜索结果项"""
        pic_elem = target.xpath('./div[contains(@class, "pic")]/a')
        if not pic_elem:
            return None
        
        pre_url = pic_elem[0].get('href')
        if not pre_url:
            return None
        
        # 提取 ID
        id_match = re.search(r'-aid-(\d+)', pre_url)
        if not id_match:
            return None
        
        gallery_id = id_match.group(1)
        
        # 标题
        title = pic_elem[0].get('title', '')
        
        # 封面
        img_elem = pic_elem[0].xpath('./img/@src')
        cover = ""
        if img_elem:
            cover = "https:" + img_elem[0] if img_elem[0].startswith("//") else img_elem[0]
        
        # 页数
        info_elem = target.xpath('.//div[contains(@class, "info_col")]/text()')
        pages = 0
        if info_elem:
            page_match = re.search(r'(\d+)[張张]', info_elem[0].strip())
            if page_match:
                pages = int(page_match.group(1))
        
        return {
            "id": gallery_id,
            "title": title,
            "cover": cover,
            "pages": pages,
            "preview_url": f"https://{self.domain}{pre_url}",
            "gallery_url": f"https://{self.domain}{pre_url.replace('index', 'gallery')}"
        }
    
    def search(self, keyword: str, page: int = 1):
        """搜索漫画（同步版本）"""
        domain = self._get_domain()
        url = f'https://{domain}/search/?f=_all&s=create_time_DESC&syn=yes&q={quote(keyword)}'
        if page > 1:
            url += f'&p={page}'
        
        client = self._get_client()
        resp = client.get(url, headers={"Referer": f"https://{domain}/"})
        resp.raise_for_status()
        
        html = etree.HTML(resp.text)
        results = []
        
        # 解析搜索结果
        targets = html.xpath('//li[contains(@class, "gallary_item")]')
        for target in targets:
            item = self._parse_search_item(target)
            if item:
                results.append(item)
        
        # 获取总页数
        max_page = 1
        total_elem = html.xpath('//p[@class="result"]/b/text()')
        if total_elem:
            try:
                total = int(total_elem[0].replace(',', ''))
                max_page = (total + 23) // 24  # 每页24个
            except:
                pass
        
        return results, max_page
    
    def get_gallery_details(self, gallery_id: str):
        """获取本子详情（同步版本）"""
        domain = self._get_domain()
        url = f"https://{domain}/photos-index-page-1-aid-{gallery_id}.html"
        
        client = self._get_client()
        resp = client.get(url)
        resp.raise_for_status()
        
        html = etree.HTML(resp.text)
        
        # 标题
        title_elem = html.xpath('//div[@class="userwrap"]/h2/text()')
        title = title_elem[0].strip() if title_elem else ""
        
        # 封面
        cover_elem = html.xpath('//div[@class="userwrap"]//div[@class="asTBcell uwthumb"]/img/@src')
        cover = ""
        if cover_elem:
            cover = "https:" + cover_elem[0] if cover_elem[0].startswith("//") else cover_elem[0]
        
        # 分类和页数
        labels = html.xpath('//div[@class="asTBcell uwconn"]/label/text()')
        category, pages = "", 0
        for label in labels:
            if "分類" in label or "分类" in label:
                category = label.split("：")[-1].strip()
            elif "頁數" in label or "页数" in label:
                try:
                    # 提取数字部分，处理 "31P" 这样的格式
                    page_text = label.split("：")[-1].strip()
                    import re
                    page_match = re.search(r'(\d+)', page_text)
                    if page_match:
                        pages = int(page_match.group(1))
                except Exception as e:
                    print(f"[WARN] 解析页数失败: {label} -> {e}")
                    pass
        
        # 标签
        tags = [t.strip() for t in html.xpath('//a[@class="tagshow"]/text()') if t.strip()]
        
        # 描述
        desc_elem = html.xpath('//div[@class="asTBcell uwconn"]/p/text()')
        description = desc_elem[0].strip() if desc_elem else ""
        
        # 上传者
        uploader_elem = html.xpath('//div[@class="asTBcell uwuinfo"]/a/p/text()')
        uploader = uploader_elem[0].strip() if uploader_elem else ""
        
        return {
            "id": gallery_id,
            "title": title,
            "cover": cover,
            "category": category,
            "pages": pages,
            "tags": tags,
            "description": description,
            "uploader": uploader,
        }
    
    def get_gallery_images(self, gallery_id: str):
        """获取本子所有图片（同步版本）"""
        domain = self._get_domain()
        url = f"https://{domain}/photos-gallery-aid-{gallery_id}.html"
        
        client = self._get_client()
        referer = f"https://{domain}/photos-index-page-1-aid-{gallery_id}.html"
        resp = client.get(url, headers={"Referer": referer})
        resp.raise_for_status()
        
        # 使用正则提取图片 URL（参考 ComicGUISpider 的方法）
        doc_wlns = re.split(r';[\n\s]+?document\.writeln', resp.text)
        selected_doc = next(filter(lambda _: "var imglist" in _, doc_wlns), "")
        
        if selected_doc:
            targets = re.findall(r'(//.*?(jp[e]?g|png|webp))', selected_doc)
            images = [f"https:{target[0]}" for target in targets]
        else:
            # 备用方法
            pattern = r'//[^"]+/[^"]+\.(jpg|jpeg|png|gif|webp)'
            matches = re.findall(pattern, resp.text, re.IGNORECASE)
            images = [f"https:{match}" for match in matches]
        
        return list(dict.fromkeys(images))  # 去重
    
    def close(self):
        """关闭客户端"""
        if self.client:
            self.client.close()
            self.client = None