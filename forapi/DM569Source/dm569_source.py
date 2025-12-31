#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DM569动漫网站爬虫类 - 已修复
支持 /artdetail-{id}.html 格式
"""

import re
import json
import base64
import urllib.parse
from typing import List, Dict, Optional, Any

import requests
from bs4 import BeautifulSoup


class DM569Source:
    """DM569动漫网站数据源类"""

    BASE_URL = "https://www.dm569.com"

    # 搜索URL模式列表（按优先级排序）
    SEARCH_URL_PATTERNS = [
        f"{BASE_URL}/search/-------------.html?wd={{keyword}}",
        f"{BASE_URL}/search.php?wd={{keyword}}",
        f"{BASE_URL}/search?q={{keyword}}",
        f"{BASE_URL}/index.php/vod/search.html?wd={{keyword}}",
    ]

    # 默认请求头
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    def __init__(self, timeout: int = 10):
        """
        初始化 Session 和请求头

        Args:
            timeout: 请求超时时间（秒）
        """
        self.session = requests.Session()
        self.session.headers.update(self.DEFAULT_HEADERS)
        self.session.verify = False
        self.timeout = timeout
        requests.packages.urllib3.disable_warnings()

    def _request(self, url: str) -> requests.Response:
        """发送HTTP请求"""
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            print(f"[DM569Source] 请求失败: {url}, 错误: {e}")
            raise

    def _extract_js_variable(self, html: str, var_name: str) -> Optional[Dict]:
        """
        从HTML中提取JavaScript变量值
        使用括号计数法确保提取完整的JSON对象
        """
        try:
            pattern = rf"var\s+{re.escape(var_name)}\s*=\s*"
            match = re.search(pattern, html)
            if not match:
                return None

            start_pos = match.end()
            content = html[start_pos:]

            depth = 0
            in_string = False
            escape_next = False
            obj_end = -1
            start_char = content[0]

            if start_char not in '{[':
                return None

            depth = 1
            for i, char in enumerate(content[1:], 1):
                if escape_next:
                    escape_next = False
                    continue

                if char == '\\':
                    escape_next = True
                elif char in '"\'':
                    in_string = not in_string
                elif not in_string:
                    if char in '{[':
                        depth += 1
                    elif char in '}]':
                        depth -= 1
                        if depth == 0:
                            obj_end = i
                            break

            if obj_end == -1:
                return None

            json_str = content[:obj_end + 1]

            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
                json_str = re.sub(r'//.*', '', json_str)
                return json.loads(json_str)

        except Exception as e:
            print(f"[DM569Source] 提取JS变量 {var_name} 失败: {e}")
            return None

    def _extract_mac_player_config(self, html: str) -> Optional[Dict]:
        """从HTML中提取 MacPlayerConfig 对象"""
        for var_name in ['MacPlayerConfig', 'MacPlayer', 'player_config', 'config']:
            config = self._extract_js_variable(html, var_name)
            if config:
                return config

        pattern = r'MacPlayerConfig\s*=\s*(\{.*?\})\s*;?'
        match = re.search(pattern, html, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        return None

    def _decrypt_layer1(self, url: str, encrypt: int) -> str:
        """
        第一层解密：解密播放页JS变量中的url字段
        Args:
            url: 加密的URL字符串
            encrypt: 加密类型 (0=无/URLDecode, 1=unescape, 2=base64+unescape)
        Returns:
            解密后的URL字符串
        """
        try:
            if encrypt == 0:
                return urllib.parse.unquote(url)
            elif encrypt == 1:
                return urllib.parse.unquote(url)
            elif encrypt == 2:
                decoded = base64.b64decode(url).decode("utf-8")
                return urllib.parse.unquote(decoded)
            else:
                return url
        except Exception as e:
            print(f"[DM569Source] 第一层解密失败: {e}, 返回原URL")
            return url

    def _get_player_parse_url(self, html: str, player_from: str) -> Optional[str]:
        """从HTML中获取指定播放器的解析URL"""
        config = self._extract_mac_player_config(html)
        if config:
            if 'player_list' in config:
                player_list = config['player_list']
                if player_from in player_list:
                    parse_url = player_list[player_from].get('parse')
                    if parse_url:
                        return parse_url

        pattern = r'player_list\s*[:=]\s*\{(.*?)\}'
        match = re.search(pattern, html, re.DOTALL)
        if match:
            try:
                player_list_str = '{' + match.group(1) + '}'
                player_list_str = player_list_str.replace("'", '"')
                player_list = json.loads(player_list_str)
                if player_from in player_list:
                    return player_list[player_from].get('parse')
            except Exception:
                pass

        common_patterns = [
            r'parse["\']?\s*[:=]\s*["\'](.*?)["\']',
            r'url["\']?\s*[:=]\s*["\'](https?://[^"\']*?m3u8[^"\']*?)["\']',
        ]
        for pattern in common_patterns:
            matches = re.findall(pattern, html)
            if matches:
                for m in matches:
                    if 'm3u8' in m or 'php' in m:
                        return m
        return None

    def _extract_vid(self, href: str) -> Optional[str]:
        """
        从URL中提取视频ID
        已修复：支持 /video/{id}.html 格式
        """
        patterns = [
            r'/video/(\d+)\.html',  # 新增：video 格式（最重要！）
            r'/play-(\d+)-',  # 播放页格式
            r'/artdetail-(\d+)\.html',  # 小说/文章（需要过滤）
            r'/voddetail-(\d+)\.html',  # vod detail 格式
            r'[?&]id=(\d+)',  # URL参数格式
            r'/detail/(\d+)',  # 路径格式
            r'/voddetail/(\d+)',  # 路径格式
            r'/(\d+)\.html',  # 通用数字ID
        ]
        for pattern in patterns:
            match = re.search(pattern, href)
            if match:
                return match.group(1)
        return None

    def _extract_ep_params(self, href: str) -> tuple:
        """
        从播放页URL中提取线路和剧集参数
        用于 /play-{vid}-{ep}.html 或 /play-{vid}-{line}-{ep}.html 格式
        返回: (vid, line, ep)
        """
        # 格式1: /play-{vid}-{ep}.html
        match = re.search(r'/play-(\d+)-(\d+)\.html', href)
        if match:
            return match.group(1), 0, match.group(2)

        # 格式2: /play-{vid}-{line}-{ep}.html
        match = re.search(r'/play-(\d+)-(\d+)-(\d+)\.html', href)
        if match:
            return match.group(1), match.group(2), match.group(3)

        return None, None, None

    def search(self, keyword: str) -> List[Dict[str, Any]]:
        """
        搜索动漫 - 增强版，支持多种URL模式和解析方式
        Args:
            keyword: 搜索关键词
        Returns:
            搜索结果列表，每项包含 id, title 等信息
        """
        encoded_keyword = urllib.parse.quote(keyword)

        # 尝试所有搜索URL模式
        for pattern in self.SEARCH_URL_PATTERNS:
            url = pattern.format(keyword=encoded_keyword)

            try:
                response = self._request(url)
                response.encoding = 'utf-8'
                html = response.text

                # 检查是否包含关键词
                if keyword not in html:
                    continue

                results = self._parse_search_results(html, url)
                if results:
                    return results

            except Exception as e:
                print(f"[DM569Source] 搜索URL {url} 失败: {e}")
                continue

        return []

    def _parse_search_results(self, html: str, source_url: str) -> List[Dict[str, Any]]:
        """解析搜索结果 - 修复版"""
        soup = BeautifulSoup(html, 'html.parser')
        results = []

        # 选择器优先级列表（已更新）
        selector_strategies = [
            {
                'name': '.myui-vodlist__media li',  # 优先：搜索结果列表
                'extractor': lambda item: self._extract_from_search_item(item)
            },
            {
                'name': 'a[href*="/video/"]',  # video 链接
                'extractor': lambda item: self._extract_from_link(item)
            },
            {
                'name': 'a[href*="detail"]',  # 通用详情页
                'extractor': lambda item: self._extract_from_link(item)
            },
        ]

        for strategy in selector_strategies:
            selector_name = strategy['name']
            extractor = strategy['extractor']

            items = soup.select(selector_name)
            if items:
                print(f"[DM569Source] 使用选择器 '{selector_name}' 找到 {len(items)} 个元素")

                for item in items:
                    try:
                        result = extractor(item)
                        if result and result.get('id'):
                            if not any(r['id'] == result['id'] for r in results):
                                results.append(result)
                    except Exception as e:
                        continue

                if results:
                    break

        return self._deduplicate_results(results)

    def _extract_from_search_item(self, item) -> Optional[Dict]:
        """从搜索结果列表项中提取信息"""
        # 查找详情页链接
        detail_link = item.select_one('a[href*="/video/"]')
        if not detail_link:
            detail_link = item.select_one('.detail .title a')

        if not detail_link:
            return None

        href = detail_link.get('href', '')

        # 过滤掉小说/文章
        if 'artdetail' in href:
            return None

        # 查找标题
        title_elem = item.select_one('.detail .title a, .title')
        title = title_elem.get_text(strip=True) if title_elem else detail_link.get('title', '')

        # 查找封面图
        img_elem = item.select_one('img, a.myui-vodlist__thumb')
        img_url = ''
        if img_elem and img_elem.name == 'img':
            img_url = img_elem.get('data-original', '') or img_elem.get('src', '')
        elif img_elem:
            img_url = img_elem.get('data-original', '')

        # 提取ID
        vid = self._extract_vid(href)
        if not vid:
            return None

        return {
            'id': vid,
            'title': title,
            'url': self._normalize_url(href),
            'img': img_url
        }

    def _extract_from_link(self, link) -> Optional[Dict]:
        """从链接中提取信息 - 增强版：过滤小说内容"""
        href = link.get('href', '')
        title = link.get('title', '') or link.get_text(strip=True)

        # 跳过空的href或非detail链接
        if not href or 'detail' not in href:
            return None

        # 新增：过滤掉小说/文章类型（artdetail = article detail）
        if 'artdetail' in href:
            print(f"[DM569Source] 跳过小说/文章: {href}")
            return None

        # 只保留视频类型（voddetail, play 等）
        video_patterns = ['voddetail', 'play', 'video', 'vod']
        if not any(pattern in href for pattern in video_patterns):
            print(f"[DM569Source] 跳过非视频链接: {href}")
            return None

        vid = self._extract_vid(href)
        if not vid:
            return None

        return {
            'id': vid,
            'title': title,
            'url': self._normalize_url(href),
            'img': ''
        }

    def _extract_from_module_item(self, item) -> Optional[Dict]:
        """从module-item中提取信息"""
        link = item.select_one('a')
        if not link:
            return None

        href = link.get('href', '')
        title_elem = item.select_one('.module-item-title, .video-title, .title')
        title = title_elem.get_text(strip=True) if title_elem else link.get('title', '') or link.get_text(strip=True)

        vid = self._extract_vid(href)
        if not vid:
            return None

        return {
            'id': vid,
            'title': title,
            'url': self._normalize_url(href),
            'img': ''
        }

    def _deduplicate_results(self, results: List[Dict]) -> List[Dict]:
        """去重结果"""
        seen = set()
        unique = []
        for r in results:
            if r['id'] not in seen:
                seen.add(r['id'])
                unique.append(r)
        return unique

    def _normalize_url(self, url: str) -> str:
        """标准化URL，补全相对路径"""
        if url.startswith('http://') or url.startswith('https://'):
            return url
        elif url.startswith('/'):
            return self.BASE_URL + url
        else:
            return f"{self.BASE_URL}/{url.lstrip('/')}"

    def get_episodes(self, vid: str) -> Dict[str, Any]:
        """
        获取动漫的所有线路和剧集 - 适配版 (基于 33.html)
        Args:
            vid: 动漫ID
        Returns:
            字典结构，包含所有线路和剧集信息
        """
        url = f"{self.BASE_URL}/video/{vid}.html"

        try:
            response = self._request(url)
            response.encoding = 'utf-8'
            html = response.text
            soup = BeautifulSoup(html, 'html.parser')

            # 1. 获取标题
            title_elem = soup.select_one('.title, h1, .detail-title')
            title = title_elem.get_text(strip=True) if title_elem else ''

            result = {
                'title': title,
                'lines': []
            }

            # 2. 查找播放列表容器
            # 根据HTML，容器是 .tab-content，线路是 .tab-pane
            playlists = soup.select('.tab-content .tab-pane')

            for idx, playlist in enumerate(playlists):
                # 获取线路ID (例如 playlist1, playlist4)
                playlist_id = playlist.get('id', '')
                if not playlist_id:
                    continue

                # 从导航栏获取线路名称 (对应 data-toggle="tab" 的链接文本)
                # 查找 <li><a href="#playlistX" ...>
                # 注意：如果HTML里没有tab导航，就使用默认名称
                line_name_elem = soup.select_one(f'li a[href="#{playlist_id}"]')
                line_name = line_name_elem.get_text(strip=True) if line_name_elem else f'线路{idx + 1}'

                # 3. 查找该线路下的剧集列表 <ul class="myui-content__list ...">
                list_ul = playlist.select_one('.myui-content__list')
                if not list_ul:
                    continue

                # 4. 遍历所有链接
                items = list_ul.select('a')
                episodes = []

                for ep_idx, item in enumerate(items):
                    href = item.get('href', '')
                    ep_name = item.get_text(strip=True)

                    if not href:
                        continue

                    # 5. 提取参数 (例如 /play/33-1-1.html -> vid=33, line=1, ep=1)
                    # 使用已有的 _extract_ep_params 方法
                    play_vid, play_line, play_ep = self._extract_ep_params(href)

                    # 如果提取失败，尝试从 playlist_id 解析线路号
                    if not play_line and playlist_id.startswith('playlist'):
                        try:
                            play_line = int(playlist_id.replace('playlist', ''))
                        except ValueError:
                            play_line = idx

                    # 如果仍然没有线路号，使用索引
                    if not play_line:
                        play_line = idx + 1

                    # 如果没有集数，使用索引
                    if not play_ep:
                        play_ep = ep_idx + 1

                    episodes.append({
                        'index': ep_idx + 1,
                        'name': ep_name,
                        'url': self._normalize_url(href),
                        'line': int(play_line) if play_line else 0,
                        'ep': int(play_ep) if play_ep else ep_idx + 1
                    })

                if episodes:
                    result['lines'].append({
                        'name': line_name,
                        'episodes': episodes
                    })

            return result

        except Exception as e:
            print(f"[DM569Source] 获取剧集列表失败 (vid={vid}): {e}")
            import traceback
            traceback.print_exc()
            return {'title': '', 'lines': []}

    def get_detail(self, vid: str) -> Dict[str, Any]:
        """
        获取动漫的详细信息 (基于实际 HTML 结构终极修正版)
        """
        url = f"{self.BASE_URL}/video/{vid}.html"
        result = {
            'id': vid,
            'title': '',
            'cover': '',
            'info': '',
            'intro': '',
            'tags': [],
            'actors': [],
            'director': '',
            'year': '',
            'area': '',
            'updated': '',
            'alias': '',
            'success': False
        }

        try:
            response = self._request(url)
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')

            # -----------------------------------------------------
            # 1. 获取标题
            # HTML: <h1 class="title text-fff">海贼王</h1>
            # -----------------------------------------------------
            h1_elem = soup.select_one('h1.title')
            if h1_elem:
                result['title'] = h1_elem.get_text(strip=True)

            # -----------------------------------------------------
            # 2. 获取封面图
            # HTML: <img class="lazyload" ... data-original="..." />
            # -----------------------------------------------------
            # 锁定 class="lazyload" 的 img 标签
            img_elem = soup.select_one('img.lazyload')
            if img_elem:
                # 优先取 data-original (真实图片地址)，否则取 src
                result['cover'] = img_elem.get('data-original') or img_elem.get('src', '')
                result['cover'] = self._normalize_url(result['cover'])

            # -----------------------------------------------------
            # 3. 获取简介
            # HTML: <span class="sketch">电视动画《航海王》改编自...</span>
            # -----------------------------------------------------
            # 锁定 class="sketch" 的 span 标签
            sketch_elem = soup.select_one('span.sketch')
            if sketch_elem:
                result['intro'] = sketch_elem.get_text(' ', strip=True)

            # -----------------------------------------------------
            # 4. 获取别名
            # HTML: <p class="data"><span class="text-muted">别名：</span>航海王,One Piece</p>
            # -----------------------------------------------------
            for p in soup.select('p.data'):
                # 检查文本里是否包含 "别名："
                if '别名：' in p.get_text():
                    # 获取 p 标签的完整文本，去掉 "别名："
                    full_text = p.get_text(strip=True)
                    result['alias'] = full_text.replace('别名：', '').strip()
                    break

            # -----------------------------------------------------
            # 5. 获取分类/标签
            # HTML: <p class="data">... <a>搞笑</a> <a>冒险</a> ...</p>
            # -----------------------------------------------------
            # 我们需要找到包含 "分类：" 的那个 p 标签
            tags_p = None
            for p in soup.select('p.data'):
                if '分类：' in p.get_text():
                    tags_p = p
                    break

            if tags_p:
                # 提取该标签下所有的 <a> 标签文本
                tags_links = tags_p.select('a')
                result['tags'] = [a.get_text(strip=True) for a in tags_links]

            # -----------------------------------------------------
            # 6. 获取地区
            # HTML: <span class="text-muted hidden-xs">地区：</span><a>日本</a>
            # -----------------------------------------------------
            # 同样在 p.data 里找
            for p in soup.select('p.data'):
                if '地区：' in p.get_text():
                    a_tag = p.select_one('a')
                    if a_tag:
                        result['area'] = a_tag.get_text(strip=True)

            # -----------------------------------------------------
            # 7. 获取年份
            # HTML: <p class="data">...<span class="text-muted">年份：</span><a>1999</a>...</p>
            # -----------------------------------------------------
            for p in soup.select('p.data'):
                if '年份：' in p.get_text():
                    a_tag = p.select_one('a')
                    if a_tag:
                        result['year'] = a_tag.get_text(strip=True)

            # -----------------------------------------------------
            # 8. 获取更新时间
            # HTML: <p class="data hidden-sm hidden-xs"><span class="text-muted">更新：</span>2025-12-29</p>
            # -----------------------------------------------------
            for p in soup.select('p.data'):
                if '更新：' in p.get_text():
                    full_text = p.get_text(strip=True)
                    result['updated'] = full_text.replace('更新：', '').strip()

            result['success'] = True
            return result

        except Exception as e:
            print(f"[DM569Source] 获取详情失败: {e}")
            import traceback
            traceback.print_exc()
            return result

    def get_video_url(self, vid: str, line: int = 0, ep: int = 0) -> Dict[str, Any]:
        """
        获取真实的视频播放地址 - 终极修复版 (优先 player_aaaa)
        
        Args:
            vid: 视频ID
            line: 线路索引 (从0开始)
            ep: 剧集索引 (从0开始)
        
        Returns:
            包含视频信息的字典
        """
        return self._get_video_url_internal(vid, line, ep, for_play_only=False)
    
    def get_stream_url_for_play(self, vid: str, line: int = 0, ep: int = 0) -> Dict[str, Any]:
        """
        获取用于播放的Stream URL - 简化版，不解析播放器页面
        
        Args:
            vid: 视频ID
            line: 线路索引 (从0开始)
            ep: 剧集索引 (从0开始)
        
        Returns:
            包含Stream URL的字典
        """
        return self._get_video_url_internal(vid, line, ep, for_play_only=True)
    
    def _get_video_url_internal(self, vid: str, line: int = 0, ep: int = 0, for_play_only: bool = False) -> Dict[str, Any]:
        """
        获取真实的视频播放地址 - 终极修复版 (优先 player_aaaa)
        """
        result = {
            'stream_url': '',
            'real_m3u8': '',
            'success': False,
            'error': ''
        }

        try:
            # 1. 获取剧集列表
            episodes_data = self.get_episodes(vid)
            if not episodes_data or not episodes_data.get('lines'):
                result['error'] = '无法获取剧集列表'
                return result

            # 安全检查索引
            if line < 0 or line >= len(episodes_data['lines']):
                result['error'] = f'线路索引超出范围'
                return result
            if ep < 0 or ep >= len(episodes_data['lines'][line]['episodes']):
                result['error'] = f'剧集索引超出范围'
                return result

            play_url = episodes_data['lines'][line]['episodes'][ep]['url']
            print(f"\n=== 获取第 {line + 1} 线路 第 {ep + 1} 集播放地址 ===")
            print(f"[DM569Source] 播放页URL: {play_url}")

            # 2. 请求播放页
            response = self._request(play_url)
            response.encoding = 'utf-8'
            play_html = response.text
            self.session.headers['Referer'] = play_url

            # ---------------------------------------------------------
            # 3. 提取播放器配置 (健壮版：使用括号计数法，避免 Extra data)
            # ---------------------------------------------------------
            # ---------------------------------------------------------
            # 3. 提取播放器配置 (健壮版：使用括号计数法，避免 Extra data)
            # ---------------------------------------------------------
            player_var = None
            encrypt_type = 0
            player_from = 'mp4'

            # 策略 A: 使用括号计数法提取 player_aaaa (最可靠)
            print("[DM569Source] 正在尝试提取 player_aaaa (括号计数法) ...")

            # 1. 先找到 var player_aaaa = 的位置
            match_start = re.search(r'var\s+player_aaaa\s*=\s*', play_html)
            if match_start:
                start_pos = match_start.end()
                content = play_html[start_pos:]

                # 2. 从第一个字符开始匹配 (应该是 {)
                if content and content[0] == '{':
                    depth = 1
                    obj_end = -1

                    # 3. 遍历后续字符，计算括号深度
                    # 我们需要忽略字符串内部的括号，否则 "url": "}" 会误导计数
                    in_string = False
                    escape_next = False
                    string_char = ""  # 记录是单引号还是双引号

                    for i, char in enumerate(content[1:], 1):
                        if escape_next:
                            escape_next = False
                            continue

                        if char == '\\':
                            escape_next = True
                        elif char in '"\'':
                            if not in_string:
                                in_string = True
                                string_char = char
                            elif char == string_char:
                                in_string = False
                        elif not in_string:
                            if char == '{':
                                depth += 1
                            elif char == '}':
                                depth -= 1
                                if depth == 0:
                                    obj_end = i
                                    break

                    # 4. 如果找到了闭合括号，截取完整的 JSON 字符串
                    if obj_end != -1:
                        json_str = content[:obj_end + 1]

                        # 5. 尝试解析 JSON
                        try:
                            player_var = json.loads(json_str)
                            print(f"[DM569Source] ✓ 成功提取并解析 player_aaaa (长度: {len(json_str)})")
                        except json.JSONDecodeError as e:
                            # 如果还是失败，尝试把非 JSON 字符（如注释）清理一下再试
                            print(f"[DM569Source] 原始JSON解析失败，尝试清理注释: {e}")
                            # 移除 // 注释 (简单移除，不处理跨行)
                            json_str = re.sub(r'//.*', '', json_str)
                            # 移除 /* */ 注释
                            json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
                            try:
                                player_var = json.loads(json_str)
                                print("[DM569Source] ✓ 清理后解析成功")
                            except Exception as e2:
                                print(f"[DM569Source] 清理后仍解析失败: {e2}")

            # 策略 B: 策略 A 失败，回退到通用提取
            if not player_var:
                print("[DM569Source] 未找到 player_aaaa 或解析失败，尝试通用配置提取...")
                player_var = self._extract_mac_player_config(play_html)

            if not player_var:
                result['error'] = '无法提取播放器配置变量'
                return result

            # ---------------------------------------------------------
            # 4. 提取关键参数
            # ---------------------------------------------------------
            # 优先从 player_aaaa 获取，如果没有再尝试 get('url')
            # 注意：根据你提供的 HTML，player_aaaa 里的 url 是加密过的，encrypt=0 表示这是 URL 编码 (不是 Base64)
            encrypted_url = player_var.get('url', '')

            # 尝试从 'encrypt' 字段获取加密类型，默认为 0
            # DM569 的 player_aaaa 通常 encrypt=0 (表示只是 URL 编码)，encrypt=2 (Base64)
            encrypt_type = int(player_var.get('encrypt', 0))

            # 获取播放器来源 (通常影响解析接口)
            player_from = player_var.get('from', 'mp4')

            if not encrypted_url:
                result['error'] = '配置变量中未找到 url 字段'
                return result

            print(f"[DM569Source] 原始加密URL: {encrypted_url}")
            print(f"[DM569Source] 加密类型 (encrypt): {encrypt_type}")
            print(f"[DM569Source] 播放器来源: {player_from}")

            # ---------------------------------------------------------
            # 5. 第一层解密
            # ---------------------------------------------------------
            try:
                # 根据你提供的日志：2z2X%2Fl7NF... 明显是 URL 编码 (%2B = +)
                # 如果 encrypt=0，通常只需要 urllib.parse.unquote
                if encrypt_type == 0:
                    decrypted_str = urllib.parse.unquote(encrypted_url)
                elif encrypt_type == 1:
                    decrypted_str = urllib.parse.unquote(encrypted_url)
                elif encrypt_type == 2:
                    # Base64 解码 (需要补全 padding)
                    missing_padding = len(encrypted_url) % 4
                    if missing_padding:
                        encrypted_url += '=' * (4 - missing_padding)
                    decoded_bytes = base64.b64decode(encrypted_url)
                    decrypted_str = decoded_bytes.decode('utf-8')
                    decrypted_str = urllib.parse.unquote(decrypted_str)
                else:
                    decrypted_str = encrypted_url

                print(f"[DM569Source] 第一层解密后URL: {decrypted_str}")

            except Exception as e:
                print(f"[DM569Source] 第一层解密失败: {e}")
                decrypted_str = encrypted_url

            # ---------------------------------------------------------
            # 6. 构造最终播放地址
            # ---------------------------------------------------------

            # 常见的解析接口
            # 如果解密后的地址已经是 http 开头的完整链接，可能不需要再拼接解析接口
            # 但根据 DM569 的习惯，通常还需要请求一次 danmu.yhdmjx.com/m3u8.php

            common_parse_urls = [
                'https://danmu.yhdmjx.com/m3u8.php?url=',  # DM569 默认
                'https://jx.ydm21.cn/m3u8.php?url=',
                'https://jx.xmflv.com/?url=',
                'https://www.ckplayer.vip/jiexi/?url=',
                'https://jx.m3u8.tv/jiexi/?url='
            ]

            final_stream_url = ""

            # 如果解密后的地址本身看起来就像一个解析地址 (包含 m3u8.php)，就直接用
            if 'm3u8.php' in decrypted_str or decrypted_str.startswith('http'):
                final_stream_url = decrypted_str
            else:
                # 否则，拼接解析接口
                # 注意：这里需要对解密后的参数再次进行 URL 编码，因为它是作为参数传递的
                parse_base = common_parse_urls[0]  # 默认用 DM569 自己的接口
                safe_param = urllib.parse.quote(decrypted_str)
                final_stream_url = parse_base + safe_param

            # URL 标准化清洗
            from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
            parsed = urlparse(final_stream_url)
            clean_query = urlencode(parse_qs(parsed.query), doseq=True)
            final_clean_url = urlunparse(
                (parsed.scheme, parsed.netloc, parsed.path, parsed.params, clean_query, parsed.fragment))

            print(f"[DM569Source] 最终Stream URL: {final_clean_url}")

            # 如果只是为了播放，直接返回Stream URL
            if for_play_only:
                print(f"[DM569Source] 播放模式：直接返回Stream URL")
                result['stream_url'] = final_clean_url
                result['success'] = True
                return result

            # ---------------------------------------------------------
            # 7. 请求 Stream 接口，获取真实 M3U8 内容 (仅下载模式)
            # ---------------------------------------------------------
            try:
                # 临时添加 Referer 头（防盗链）
                old_referer = self.session.headers.get('Referer', '')
                self.session.headers['Referer'] = play_url  # 使用播放页作为 Referer
                self.session.headers['Origin'] = 'https://www.dm569.com'

                print(f"[DM569Source] 请求Stream接口: {final_clean_url}")
                stream_response = self._request(final_clean_url)
                stream_response.encoding = 'utf-8'
                m3u8_content = stream_response.text

                print(f"[DM569Source] Stream响应状态码: {stream_response.status_code}")
                print(f"[DM569Source] Stream响应Content-Type: {stream_response.headers.get('Content-Type', 'Unknown')}")
                print(f"[DM569Source] Stream响应内容长度: {len(m3u8_content)}")
                print(f"[DM569Source] Stream响应前200字符: {m3u8_content[:200]}")

                # 恢复原来的 Referer
                if old_referer:
                    self.session.headers['Referer'] = old_referer
                else:
                    if 'Referer' in self.session.headers:
                        del self.session.headers['Referer']
                if 'Origin' in self.session.headers:
                    del self.session.headers['Origin']

                # 检查是否返回了HTML播放器页面
                if '<html' in m3u8_content.lower() or '<!doctype' in m3u8_content.lower():
                    print(f"[DM569Source] 检测到HTML播放器页面，尝试解析真实视频源...")
                    
                    # 解析播放器页面
                    real_video_url = self._parse_player_page(m3u8_content, final_clean_url)
                    
                    if real_video_url:
                        print(f"[DM569Source] ✓ 从播放器页面解析到真实视频URL: {real_video_url}")
                        
                        # 请求真实的视频URL
                        try:
                            real_response = self._request(real_video_url)
                            real_content = real_response.text
                            
                            if '#EXT' in real_content:
                                print(f"[DM569Source] ✓ 获取到有效的M3U8内容")
                                result['stream_url'] = real_video_url
                                result['real_m3u8'] = real_content
                                result['success'] = True
                                return result
                            else:
                                print(f"[DM569Source] ❌ 真实URL返回的不是M3U8内容")
                        except Exception as e:
                            print(f"[DM569Source] ❌ 请求真实视频URL失败: {e}")
                    
                    # 如果解析播放器页面失败，检查是否是"解析不到该播放地址"错误
                    if '解析不到该播放地址' in m3u8_content or '出现错误' in m3u8_content:
                        print(f"[DM569Source] 检测到解析错误，尝试其他解析接口...")
                        
                        # 尝试其他解析接口
                        for parse_url in common_parse_urls[1:]:  # 跳过第一个已经试过的
                            try:
                                safe_param = urllib.parse.quote(decrypted_str)
                                alt_stream_url = parse_url + safe_param
                                print(f"[DM569Source] 尝试备用解析接口: {alt_stream_url}")
                                
                                alt_response = self._request(alt_stream_url)
                                alt_content = alt_response.text
                                
                                if '<html' not in alt_content.lower() and '#EXT' in alt_content:
                                    print(f"[DM569Source] ✓ 备用接口成功")
                                    result['stream_url'] = alt_stream_url
                                    result['real_m3u8'] = alt_content
                                    result['success'] = True
                                    return result
                                elif '<html' in alt_content.lower():
                                    # 尝试解析这个播放器页面
                                    alt_real_url = self._parse_player_page(alt_content, alt_stream_url)
                                    if alt_real_url:
                                        try:
                                            alt_real_response = self._request(alt_real_url)
                                            alt_real_content = alt_real_response.text
                                            if '#EXT' in alt_real_content:
                                                print(f"[DM569Source] ✓ 备用接口播放器解析成功")
                                                result['stream_url'] = alt_real_url
                                                result['real_m3u8'] = alt_real_content
                                                result['success'] = True
                                                return result
                                        except Exception as e:
                                            print(f"[DM569Source] 备用接口播放器解析失败: {e}")
                                    
                            except Exception as e:
                                print(f"[DM569Source] 备用接口失败: {e}")
                                continue
                        
                        # 所有解析接口都失败，尝试直接使用解密后的URL
                        if decrypted_str.startswith('http'):
                            try:
                                print(f"[DM569Source] 尝试直接访问解密URL: {decrypted_str}")
                                direct_response = self._request(decrypted_str)
                                direct_content = direct_response.text
                                
                                if '#EXT' in direct_content:
                                    print(f"[DM569Source] ✓ 直接访问成功")
                                    result['stream_url'] = decrypted_str
                                    result['real_m3u8'] = direct_content
                                    result['success'] = True
                                    return result
                                    
                            except Exception as e:
                                print(f"[DM569Source] 直接访问失败: {e}")
                    
                    result['error'] = f'播放器页面解析失败，无法找到真实视频源'
                    return result

                # 情况A: 返回的是 JSON
                if m3u8_content.strip().startswith('{'):
                    try:
                        json_data = json.loads(m3u8_content)
                        print(f"[DM569Source] 解析JSON响应: {json_data}")
                        
                        # 检查是否包含getVideoInfo函数调用
                        url_field = json_data.get('url', '')
                        if 'getVideoInfo' in url_field:
                            print(f"[DM569Source] 检测到getVideoInfo加密，尝试解密...")
                            
                            # 提取加密字符串
                            match = re.search(r'getVideoInfo\s*\(\s*["\']([^"\']+)["\']', url_field)
                            if match:
                                encrypted_string = match.group(1)
                                print(f"[DM569Source] 提取到加密字符串，长度: {len(encrypted_string)}")
                                
                                # 尝试解密
                                decrypted_url = self._decrypt_video_url(encrypted_string)
                                if decrypted_url:
                                    print(f"[DM569Source] ✓ 解密成功: {decrypted_url}")
                                    
                                    # 请求解密后的URL
                                    try:
                                        real_response = self._request(decrypted_url)
                                        real_content = real_response.text
                                        
                                        if '#EXT' in real_content:
                                            result['stream_url'] = decrypted_url
                                            result['real_m3u8'] = real_content
                                            result['success'] = True
                                            print(f"✓ 解密并获取M3U8成功，长度: {len(result['real_m3u8'])}")
                                            return result
                                        else:
                                            print(f"[DM569Source] ❌ 解密URL返回的不是M3U8内容")
                                    except Exception as e:
                                        print(f"[DM569Source] ❌ 请求解密URL失败: {e}")
                                else:
                                    print(f"[DM569Source] ❌ 解密失败")
                        
                        # 寻找其他可能的真实URL字段
                        for key in ['data', 'link', 'playUrl', 'url_list', 'm3u8']:
                            if key in json_data:
                                real_url = json_data[key]
                                if isinstance(real_url, list) and real_url:
                                    real_url = real_url[0]
                                if real_url and isinstance(real_url, str) and real_url.startswith('http'):
                                    print(f"[DM569Source] 从JSON提取到真实URL: {real_url}")
                                    real_response = self._request(real_url)
                                    result['stream_url'] = real_url
                                    result['real_m3u8'] = real_response.text
                                    result['success'] = True
                                    print(f"✓ 解析JSON成功，M3U8长度: {len(result['real_m3u8'])}")
                                    return result
                    except Exception as e:
                        print(f"[DM569Source] JSON解析失败: {e}")

                # 情况B: 直接是 M3U8 内容
                if m3u8_content.strip().startswith('#EXT'):
                    result['stream_url'] = final_clean_url
                    result['real_m3u8'] = m3u8_content
                    result['success'] = True
                    print(f"✓ 直接获取M3U8成功，长度: {len(result['real_m3u8'])}")
                    return result

                # 情况C: 内容里包含 M3U8 链接
                m3u8_match = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', m3u8_content)
                if m3u8_match:
                    real_m3u8_url = m3u8_match.group(1)
                    print(f"[DM569Source] 从响应中提取到M3U8链接: {real_m3u8_url}")
                    real_response = self._request(real_m3u8_url)
                    result['stream_url'] = real_m3u8_url
                    result['real_m3u8'] = real_response.text
                    result['success'] = True
                    print(f"✓ 提取M3U8链接成功，长度: {len(result['real_m3u8'])}")
                    return result

                # 其他情况，返回错误
                result['error'] = f'无法从响应中提取有效的M3U8内容: {m3u8_content[:200]}'
                result['stream_url'] = final_clean_url
                result['real_m3u8'] = m3u8_content

            except Exception as e:
                result['error'] = f'请求Stream失败: {e}'
                result['stream_url'] = final_clean_url
                result['real_m3u8'] = decrypted_str
                print(f"[DM569Source] Stream请求异常: {e}")

            return result

        except Exception as e:
            result['error'] = f'逻辑异常: {e}'
            import traceback
            traceback.print_exc()
            return result

    def _decrypt_video_url(self, encrypted_string: str) -> Optional[str]:
        """
        解密视频URL - 使用AES解密
        基于从播放器页面提取的加密逻辑
        
        Args:
            encrypted_string: 加密的字符串
            
        Returns:
            解密后的URL，如果解密失败则返回None
        """
        try:
            print(f"[DM569Source] 开始AES解密视频URL，长度: {len(encrypted_string)}")
            
            # 尝试导入AES解密库
            try:
                from Crypto.Cipher import AES
                from Crypto.Util.Padding import unpad
            except ImportError:
                print(f"[DM569Source] ❌ 缺少pycryptodome库，尝试基础解密方法")
                return self._decrypt_video_url_fallback(encrypted_string)
            
            # 基于JavaScript代码的密钥和IV
            base_key = "yhdm"  # 从JavaScript中提取的密钥
            
            # 尝试不同的密钥格式
            key_variants = [
                base_key,  # 原始密钥
                base_key.ljust(16, '\0'),  # 用null填充到16字节
                (base_key * 4)[:16],  # 重复到16字节
                base64.b64encode(base_key.encode()).decode(),  # Base64编码
            ]
            
            for i, key in enumerate(key_variants):
                try:
                    print(f"[DM569Source] 尝试密钥格式 {i+1}: {key}")
                    
                    # 处理密钥长度
                    if len(key) < 16:
                        processed_key = key.ljust(16, '\0')
                    elif len(key) > 16:
                        processed_key = key[:16]
                    else:
                        processed_key = key
                    
                    # Base64解码加密字符串
                    encrypted_bytes = base64.b64decode(encrypted_string)
                    
                    # 尝试ECB模式
                    try:
                        cipher = AES.new(processed_key.encode('utf-8'), AES.MODE_ECB)
                        decrypted_bytes = cipher.decrypt(encrypted_bytes)
                        
                        # 去除填充
                        try:
                            decrypted_bytes = unpad(decrypted_bytes, AES.block_size)
                        except ValueError:
                            # 手动去除填充
                            padding_length = decrypted_bytes[-1]
                            if padding_length <= AES.block_size:
                                decrypted_bytes = decrypted_bytes[:-padding_length]
                        
                        # 转换为字符串
                        decrypted_str = decrypted_bytes.decode('utf-8')
                        
                        if self._is_valid_video_url(decrypted_str):
                            print(f"[DM569Source] ✓ AES-ECB解密成功: {decrypted_str[:100]}...")
                            return decrypted_str
                            
                    except Exception as e:
                        print(f"[DM569Source] ECB模式失败: {e}")
                    
                    # 如果ECB失败，尝试CBC模式（使用固定IV）
                    try:
                        # 使用固定IV或从密钥派生IV
                        iv = "a0bb57a7e0700c92"[:16].ljust(16, '\0')
                        cipher = AES.new(processed_key.encode('utf-8'), AES.MODE_CBC, iv.encode('utf-8'))
                        decrypted_bytes = cipher.decrypt(encrypted_bytes)
                        
                        # 去除填充
                        try:
                            decrypted_bytes = unpad(decrypted_bytes, AES.block_size)
                        except ValueError:
                            padding_length = decrypted_bytes[-1]
                            if padding_length <= AES.block_size:
                                decrypted_bytes = decrypted_bytes[:-padding_length]
                        
                        decrypted_str = decrypted_bytes.decode('utf-8')
                        
                        if self._is_valid_video_url(decrypted_str):
                            print(f"[DM569Source] ✓ AES-CBC解密成功: {decrypted_str[:100]}...")
                            return decrypted_str
                            
                    except Exception as e:
                        print(f"[DM569Source] CBC模式失败: {e}")
                        
                except Exception as e:
                    print(f"[DM569Source] 密钥格式 {i+1} 失败: {e}")
                    continue
            
            print(f"[DM569Source] ❌ 所有AES解密方法都失败")
            
            # 回退到基础解密方法
            return self._decrypt_video_url_fallback(encrypted_string)
            
        except Exception as e:
            print(f"[DM569Source] AES解密过程异常: {e}")
            return self._decrypt_video_url_fallback(encrypted_string)
    
    def _decrypt_video_url_fallback(self, encrypted_string: str) -> Optional[str]:
        """
        回退解密方法 - 使用基础的Base64等方法
        """
        try:
            print(f"[DM569Source] 使用回退解密方法...")
            
            # 方法1: 直接Base64解码
            try:
                decoded = base64.b64decode(encrypted_string).decode('utf-8')
                if self._is_valid_video_url(decoded):
                    print(f"[DM569Source] ✓ 回退方法1成功 (直接Base64): {decoded[:100]}...")
                    return decoded
            except Exception:
                pass
            
            # 方法2: Base64 + URL解码
            try:
                decoded = base64.b64decode(encrypted_string).decode('utf-8')
                url_decoded = urllib.parse.unquote(decoded)
                if self._is_valid_video_url(url_decoded):
                    print(f"[DM569Source] ✓ 回退方法2成功 (Base64+URL): {url_decoded[:100]}...")
                    return url_decoded
            except Exception:
                pass
            
            # 方法3: URL解码 + Base64
            try:
                url_decoded = urllib.parse.unquote(encrypted_string)
                decoded = base64.b64decode(url_decoded).decode('utf-8')
                if self._is_valid_video_url(decoded):
                    print(f"[DM569Source] ✓ 回退方法3成功 (URL+Base64): {decoded[:100]}...")
                    return decoded
            except Exception:
                pass
            
            print(f"[DM569Source] ❌ 所有回退解密方法都失败")
            return None
            
        except Exception as e:
            print(f"[DM569Source] 回退解密异常: {e}")
            return None
    
    def _is_valid_video_url(self, url: str) -> bool:
        """检查是否是有效的视频URL"""
        if not url or not isinstance(url, str):
            return False
        
        # 检查是否包含HTTP协议
        if not url.startswith(('http://', 'https://')):
            return False
        
        # 检查是否包含视频相关的扩展名或关键词
        video_indicators = ['.m3u8', '.mp4', '.flv', '.avi', '.mkv', 'video', 'stream', 'play']
        return any(indicator in url.lower() for indicator in video_indicators)

    def _parse_player_page(self, html_content: str, player_url: str) -> Optional[str]:
        """
        解析播放器页面，提取真实的视频源URL
        
        Args:
            html_content: 播放器页面的HTML内容
            player_url: 播放器页面的URL（用于补全相对路径）
            
        Returns:
            真实的视频源URL，如果未找到则返回None
        """
        try:
            print(f"[DM569Source] 开始解析播放器页面...")
            
            from bs4 import BeautifulSoup
            from urllib.parse import urljoin
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 查找所有script标签
            scripts = soup.find_all('script')
            print(f"[DM569Source] 找到 {len(scripts)} 个script标签")
            
            video_sources = []
            
            # 分析每个script标签
            for i, script in enumerate(scripts):
                script_content = script.get_text() if script.get_text() else ""
                src = script.get('src', '')
                
                # 如果是外部脚本，尝试获取内容
                if src:
                    try:
                        if src.startswith('http'):
                            script_response = self._request(src)
                        elif src.startswith('/') or src.startswith('./'):
                            full_src = urljoin(player_url, src)
                            script_response = self._request(full_src)
                        else:
                            continue
                        
                        script_content = script_response.text
                        print(f"[DM569Source] 获取外部脚本成功: {src}")
                    except Exception as e:
                        print(f"[DM569Source] 获取外部脚本失败: {src}, 错误: {e}")
                        continue
                
                if not script_content:
                    continue
                
                # 在脚本中查找视频相关的URL
                video_patterns = [
                    # M3U8 URL模式
                    r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)',
                    r'"(https?://[^"]+\.m3u8[^"]*)"',
                    r"'(https?://[^']+\.m3u8[^']*)'",
                    
                    # MP4 URL模式
                    r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)',
                    r'"(https?://[^"]+\.mp4[^"]*)"',
                    r"'(https?://[^']+\.mp4[^']*)'",
                    
                    # 通用视频URL模式
                    r'"url":\s*"([^"]+)"',
                    r"'url':\s*'([^']+)'",
                    r'url:\s*"([^"]+)"',
                    r"url:\s*'([^']+)'",
                    
                    # 播放器配置模式
                    r'player_aaaa\s*=\s*"([^"]+)"',
                    r"player_aaaa\s*=\s*'([^']+)'",
                    r'var\s+player_aaaa\s*=\s*"([^"]+)"',
                    r"var\s+player_aaaa\s*=\s*'([^']+)'",
                    
                    # 其他可能的视频源模式
                    r'src:\s*"([^"]+)"',
                    r"src:\s*'([^']+)'",
                    r'source:\s*"([^"]+)"',
                    r"source:\s*'([^']+)'",
                ]
                
                for pattern in video_patterns:
                    matches = re.findall(pattern, script_content, re.IGNORECASE)
                    for match in matches:
                        if isinstance(match, tuple):
                            match = match[0] if match[0] else (match[1] if len(match) > 1 else "")
                        
                        if match and match not in video_sources:
                            # 跳过明显不是视频的URL
                            if any(skip in match.lower() for skip in ['javascript:', 'data:', 'blob:', '#']):
                                continue
                            
                            video_sources.append(match)
                            print(f"[DM569Source] 找到可能的视频源: {match}")
            
            # 查找iframe标签
            iframes = soup.find_all('iframe')
            for iframe in iframes:
                src = iframe.get('src', '')
                if src and src not in video_sources:
                    video_sources.append(src)
                    print(f"[DM569Source] 找到iframe源: {src}")
            
            # 查找video标签
            videos = soup.find_all('video')
            for video in videos:
                src = video.get('src', '')
                if src and src not in video_sources:
                    video_sources.append(src)
                    print(f"[DM569Source] 找到video源: {src}")
                
                # 查找source子标签
                sources = video.find_all('source')
                for source in sources:
                    src = source.get('src', '')
                    if src and src not in video_sources:
                        video_sources.append(src)
                        print(f"[DM569Source] 找到source源: {src}")
            
            print(f"[DM569Source] 总共找到 {len(video_sources)} 个可能的视频源")
            
            # 验证每个视频源
            for source in video_sources:
                try:
                    # 补全相对URL
                    if source.startswith('/'):
                        source = urljoin(player_url, source)
                    elif not source.startswith('http'):
                        source = urljoin(player_url, source)
                    
                    print(f"[DM569Source] 验证视频源: {source}")
                    
                    # 发送HEAD请求检查
                    head_response = self.session.head(source, timeout=5, allow_redirects=True)
                    content_type = head_response.headers.get('Content-Type', '').lower()
                    
                    print(f"[DM569Source] 状态码: {head_response.status_code}, Content-Type: {content_type}")
                    
                    if head_response.status_code == 200:
                        # 检查是否是视频相关的内容类型
                        if any(vtype in content_type for vtype in ['video/', 'application/vnd.apple.mpegurl', 'application/x-mpegurl', 'text/plain']):
                            print(f"[DM569Source] ✓ 找到有效的视频源: {source}")
                            return source
                        elif '.m3u8' in source:
                            # 即使Content-Type不对，如果URL包含.m3u8也尝试一下
                            print(f"[DM569Source] ✓ 找到M3U8 URL: {source}")
                            return source
                            
                except Exception as e:
                    print(f"[DM569Source] 验证视频源失败: {source}, 错误: {e}")
                    continue
            
            print(f"[DM569Source] ❌ 未找到有效的视频源")
            return None
            
        except Exception as e:
            print(f"[DM569Source] 解析播放器页面时发生异常: {e}")
            import traceback
            traceback.print_exc()
            return None

    def __del__(self):
        """清理资源"""
        if hasattr(self, 'session'):
            self.session.close()


# 测试代码
 #if __name__ == "__main__":
 #   import sys

  #  source = DM569Source()

   # if len(sys.argv) > 1:
    #    keyword = sys.argv[1]
    #else:
     #   keyword = "海贼王"

    #print(f"\n=== 搜索: {keyword} ===")
   # results = source.search(keyword)

    #if results:
     #   print(f"✓ 找到 {len(results)} 个结果\n")
      #  for i, item in enumerate(results[:5]):
       #     print(f"{i + 1}. [{item['id']}] {item['title']}")
        #    print(f"   URL: {item['url']}")
    #else:
     #   print("✗ 未找到任何结果，请检查网站是否可访问")

    #if results:
     #   first_id = results[0]['id']
      #  print(f"\n=== 开始获取 [{first_id}] 的视频地址 ===")
        # 获取第 0 条线路的第 0 集 (通常就是正片第一集)
       # video_info = source.get_video_url(vid=first_id, line=0, ep=0)

       # if video_info['success']:
       #     print(f"✓ 成功获取视频流！")
       #     print(f"Stream URL: {video_info['stream_url']}")
        #    print(f"M3U8 内容预览: {video_info['real_m3u8'][:100]}...")
       # else:
         #   print(f"✗ 获取失败: {video_info['error']}")