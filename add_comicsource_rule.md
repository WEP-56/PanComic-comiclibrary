# PanComic 漫画源集成完整指南

## 快速检查清单

创建新漫画源时，需要按顺序完成以下项目：

### 第一阶段: API 开发和测试
- [ ] 创建 `forapi/{source_name}_source.py` - API封装
- [ ] 创建测试套件 `test_{source_name}/` 
  - [ ] `{source_name}_api.py` - API测试
  - [ ] `{source_name}_adapter.py` - 适配器测试  
  - [ ] `{source_name}_test.py` - 集成测试
- [ ] 验证反爬虫策略稳定性
- [ ] 测试搜索、详情、图片获取功能

### 第二阶段: 适配器开发
- [ ] 创建 `pancomic/adapters/{source_name}_adapter.py` - 适配器
- [ ] 继承 `BaseSourceAdapter` 确保接口一致性
- [ ] 实现所有必需方法 (search, get_comic_details, get_chapter_images, download_chapter)
- [ ] 处理数据模型转换 (API数据 → Comic/Chapter对象)
- [ ] 添加完善的错误处理和日志记录

### 第三阶段: 核心系统集成
- [ ] 在 `downloads/config.json` 中添加源配置
- [ ] 在 `pancomic/core/app.py` 中注册适配器
- [ ] 在 `pancomic/ui/main_window.py` 中注册源
- [ ] 更新 `pancomic/models/comic.py` 和 `chapter.py` 的 valid_sources
- [ ] 在 `SourceTabManager` 中注册新源

### 第四阶段: UI 开发
- [ ] 创建 `pancomic/ui/pages/{source_name}_page.py` - 页面UI
- [ ] 遵循分割式布局规范 (5:3 比例)
- [ ] 实现异步搜索工作线程
- [ ] 集成智能图片加载管理器
- [ ] 实现懒加载和性能优化
- [ ] 集成设置到统一设置页面 (不创建独立设置对话框)

### 第五阶段: 测试和优化
- [ ] 测试完整工作流程 (搜索 → 详情 → 阅读 → 下载)
- [ ] 验证下载文件格式符合规范
- [ ] 测试主题切换功能
- [ ] 性能测试和优化
- [ ] 清理调试信息和代码优化


## 概述
本文档基于集成绅士漫画时的实际经验，提供了完整的漫画源集成指南。每个漫画源的页面布局都遵循统一的设计规范，确保用户体验的一致性和代码的可维护性。

## 集成架构概览

### 三层架构设计
```
┌─────────────────────────────────────────────────────────────┐
│                        UI 层                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   页面组件      │  │   设置集成      │  │   主题支持      │ │
│  │ {Source}Page    │  │ SettingsPage    │  │ apply_theme()   │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                      适配器层                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   数据转换      │  │   下载管理      │  │   错误处理      │ │
│  │ BaseAdapter     │  │ download_chapter│  │ Exception       │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                      API 层                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   网络请求      │  │   反爬虫策略    │  │   数据解析      │ │
│  │ httpx/requests  │  │ Headers/Proxy   │  │ lxml/BeautifulSoup│ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 关键设计原则
1. **分层解耦**: API层、适配器层、UI层职责清晰，便于维护和测试
2. **异步优先**: 所有网络操作使用异步架构，避免阻塞UI线程
3. **性能优化**: 实现懒加载、缓存、并发控制等优化策略
4. **统一规范**: 遵循统一的接口规范和UI设计模式

## 0. 集成前准备工作

### 0.1 技术调研
在开始集成前，需要完成以下调研工作：

1. **目标网站分析**
   - 网站结构和API接口分析
   - 反爬虫策略识别 (Cloudflare, 验证码, IP限制等)
   - 数据格式和字段映射分析
   - 是否需要登录认证

2. **现有方案调研**
   - 查找是否有成熟的爬虫方案 (如 ComicGUISpider)
   - 分析其他项目的实现方式
   - 评估技术可行性和稳定性

3. **特殊需求识别**
   - 是否有章节概念 (如 WNACG 是本子站，无章节)
   - 图片加载方式 (直链、需要Referer、需要特殊headers)
   - 域名变化频率和获取方式

### 0.2 开发环境准备
```bash
# 创建测试目录
mkdir test_{source_name}
cd test_{source_name}

# 创建测试文件
touch {source_name}_api.py
touch {source_name}_adapter.py  
touch {source_name}_test.py
```

### 0.3 依赖库选择
根据目标网站特点选择合适的库：
- **httpx**: 现代异步HTTP客户端，推荐用于新项目
- **requests**: 传统同步HTTP客户端，简单易用
- **lxml**: 高性能XML/HTML解析器
- **BeautifulSoup**: 易用的HTML解析器
- **curl_cffi**: 模拟浏览器请求，绕过某些反爬虫 (谨慎使用)

## 0.5 API 层开发规范

### 0.5.1 文件结构
```python
# forapi/{source_name}_source.py
class {SourceName}Source:
    """异步版本 - 主要实现"""
    
    async def search(self, keyword: str, page: int = 1) -> tuple
    async def get_comic_details(self, comic_id: str) -> dict
    async def get_chapter_images(self, comic_id: str, chapter_id: str) -> list

class {SourceName}SourceSync:
    """同步版本 - 避免事件循环冲突"""
    
    def search(self, keyword: str, page: int = 1) -> tuple
    def get_comic_details(self, comic_id: str) -> dict  
    def get_chapter_images(self, comic_id: str, chapter_id: str) -> list
```

### 0.5.2 反爬虫策略
基于 WNACG 集成经验，推荐的反爬虫策略：

```python
# 使用验证过的 headers
headers = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "referer": "https://example.com/",
    "cache-control": "no-cache",
}

# 域名管理策略
class DomainManager:
    def __init__(self):
        self.cached_domain = None
        self.publish_url = "https://导航页地址"
    
    def get_domain(self):
        """优先使用缓存域名，失败时重新获取"""
        if self.cached_domain and self._test_domain(self.cached_domain):
            return self.cached_domain
        return self._discover_domain()
```

### 0.5.3 数据解析规范
```python
def _parse_search_item(self, element) -> dict:
    """解析搜索结果项，返回标准格式"""
    return {
        "id": "漫画ID",
        "title": "标题", 
        "cover": "封面URL",
        "author": "作者",
        "description": "描述",
        "tags": ["标签1", "标签2"],
        "pages": 页数,  # 如果适用
        "preview_url": "预览页URL"
    }

def _parse_comic_details(self, html) -> dict:
    """解析漫画详情，返回标准格式"""
    return {
        "id": "漫画ID",
        "title": "标题",
        "cover": "封面URL", 
        "description": "详细描述",
        "authors": ["作者1", "作者2"],
        "tags": ["标签1", "标签2"],
        "category": "分类",
        "pages": 总页数,
        "chapters": [
            {
                "chapter_id": "章节ID",
                "title": "章节标题",
                "group": "汉化组"  # 可选
            }
        ]
    }
```

## 0.6 适配器层开发规范

### 0.6.1 基础结构
```python
# pancomic/adapters/{source_name}_adapter.py
from pancomic.adapters.base_adapter import BaseSourceAdapter
from forapi.{source_name}_source import {SourceName}SourceSync

class {SourceName}Adapter(BaseSourceAdapter):
    SOURCE_NAME = "source_name"
    SOURCE_DISPLAY_NAME = "显示名称"
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api = None
    
    def initialize(self) -> None:
        """初始化适配器，处理配置和域名缓存"""
        try:
            # 从配置获取缓存域名
            domain = self.config.get('domain', '默认域名')
            self.api = {SourceName}SourceSync(domain)
            self._is_initialized = True
        except Exception as e:
            print(f"Failed to initialize {self.SOURCE_NAME} adapter: {e}")
            self._is_initialized = False
```

### 0.6.2 数据转换规范
```python
def search(self, keyword: str, page: int = 1) -> Dict[str, Any]:
    """搜索漫画并转换为标准格式"""
    if not self.api:
        raise RuntimeError("Adapter not initialized")
    
    comics_data, max_page = self.api.search(keyword, page)
    
    return {
        "comics": [
            {
                "comic_id": c["id"],
                "title": c["title"],
                "cover": c["cover"],
                "description": c.get("description", ""),
                "preview_url": c.get("preview_url", ""),
            }
            for c in comics_data
        ],
        "max_page": max_page,
    }

def get_comic_details(self, comic_id: str) -> Dict[str, Any]:
    """获取漫画详情并处理特殊情况"""
    if not self.api:
        raise RuntimeError("Adapter not initialized")
    
    details = self.api.get_comic_details(comic_id)
    
    # 处理无章节概念的源 (如 WNACG)
    if not details.get("chapters"):
        details["chapters"] = [
            {
                "chapter_id": "1",
                "title": "全本",
                "group": "default",
            }
        ]
    
    return details
```

### 0.6.3 下载功能实现
```python
def download_chapter(self, comic: Comic, chapter: Chapter, download_path: str, progress_callback=None) -> bool:
    """完整的下载流程实现"""
    try:
        # 1. 获取图片列表
        images = self.get_chapter_images(comic.id, chapter.id)
        if not images:
            return False
        
        # 2. 创建目录结构
        from pathlib import Path
        comic_dir = Path(download_path) / self.SOURCE_NAME / comic.id
        chapter_dir = comic_dir / f"chapter_{chapter.id}"
        chapter_dir.mkdir(parents=True, exist_ok=True)
        
        # 3. 下载图片
        success_count = 0
        total_images = len(images)
        
        with httpx.Client(headers=self.api.headers, timeout=30) as client:
            for i, img_url in enumerate(images, 1):
                try:
                    # 报告进度
                    if progress_callback:
                        progress_callback(i, total_images)
                    
                    # 下载并保存
                    response = client.get(img_url)
                    response.raise_for_status()
                    
                    ext = self._get_image_extension(img_url)
                    img_path = chapter_dir / f"{i:03d}.{ext}"
                    
                    with open(img_path, 'wb') as f:
                        f.write(response.content)
                    
                    success_count += 1
                    
                except Exception as e:
                    print(f"Failed to download image {i}: {e}")
                    continue
        
        # 4. 生成 metadata.json
        self._generate_metadata(comic, chapter, comic_dir, success_count)
        
        return success_count > 0
        
    except Exception as e:
        print(f"Download failed: {e}")
        return False

def _generate_metadata(self, comic: Comic, chapter: Chapter, comic_dir: Path, page_count: int):
    """生成标准的 metadata.json"""
    import json
    from datetime import datetime
    
    download_time = datetime.now()
    
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
        'source': self.SOURCE_NAME,
        'created_at': download_time.isoformat(),
        'chapters': {
            chapter.id: {
                'id': chapter.id,
                'title': chapter.title,
                'chapter_number': chapter.chapter_number,
                'page_count': page_count,
                'download_path': str(comic_dir / f"chapter_{chapter.id}"),
                'downloaded_at': download_time.isoformat()
            }
        },
        'download_info': {
            'created_time': download_time.isoformat(),
            'updated_time': download_time.isoformat(),
            'status': 'completed'
        }
    }
    
    metadata_file = comic_dir / 'metadata.json'
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
```

## 0.7 核心系统集成

### 0.7.1 配置文件更新
```json
// downloads/config.json
{
  "{source_name}": {
    "enabled": true,
    "domain": "默认域名",
    "auto_domain_discovery": true,
    // 其他源特定配置
    "username": "",  // 如果需要登录
    "password": "",
    "auto_login": false
  }
}
```

### 0.7.2 应用初始化集成
```python
# pancomic/core/app.py
from pancomic.adapters.{source_name}_adapter import {SourceName}Adapter

class Application:
    def __init__(self):
        # 添加适配器属性
        self.{source_name}_adapter: Optional[{SourceName}Adapter] = None
    
    def _initialize_adapters(self):
        """初始化所有适配器"""
        # 添加新适配器初始化
        {source_name}_config = self.config_manager.get_source_config('{source_name}')
        self.{source_name}_adapter = {SourceName}Adapter({source_name}_config)
        self.{source_name}_adapter.initialize()
        
        if self.{source_name}_adapter.is_initialized:
            print(f"[INFO] {SourceName} adapter initialized")
        else:
            print(f"[WARN] {SourceName} adapter failed to initialize")
```

### 0.7.3 主窗口集成
```python
# pancomic/ui/main_window.py
from pancomic.ui.pages.{source_name}_page import {SourceName}Page

class MainWindow(QMainWindow):
    def __init__(self, ..., {source_name}_adapter: {SourceName}Adapter, ...):
        self.{source_name}_adapter = {source_name}_adapter
    
    def _register_sources(self):
        """注册所有漫画源"""
        # 添加新源注册
        self.tab_manager.register_source(
            '{source_name}',
            '显示名称',
            lambda: {SourceName}Page(
                self.{source_name}_adapter,
                self.download_manager,
                self
            )
        )
```

### 0.7.4 数据模型更新
```python
# pancomic/models/comic.py 和 chapter.py
# 更新 valid_sources 列表
valid_sources = ["jmcomic", "picacg", "wnacg", "{source_name}", "user"]
```

## 1. UI 层开发规范

### 1.0 性能优化核心原则

基于 WNACG 集成的实际经验，UI 层必须遵循以下性能优化原则：

#### 1.0.1 异步架构设计
```python
class {SourceName}SearchWorker(QObject):
    """独立工作线程处理网络请求"""
    
    search_completed = Signal(list, int)  # comics, max_page
    search_failed = Signal(str)  # error_message
    details_completed = Signal(dict)  # comic_details
    details_failed = Signal(str)  # error_message
    
    def __init__(self, adapter):
        super().__init__()
        self.adapter = adapter
    
    @Slot(str, int)
    def search_comics(self, keyword: str, page: int):
        """在工作线程中执行搜索"""
        try:
            result = self.adapter.search(keyword, page)
            # 转换为 Comic 对象
            comics = [self._create_comic_object(data) for data in result["comics"]]
            self.search_completed.emit(comics, result["max_page"])
        except Exception as e:
            self.search_failed.emit(str(e))
```

#### 1.0.2 智能图片加载管理器
```python
class ImageLoadManager(QObject):
    """优化的图片加载管理器 - 核心性能组件"""
    
    def __init__(self, max_concurrent=2):
        super().__init__()
        self.max_concurrent = max_concurrent  # 限制并发数，避免卡顿
        self.loading_queue = []  # 加载队列
        self.cache = {}  # 图片缓存
        self.current_loading = 0
        self.pending_requests = {}  # 待处理请求
        
        # 工作线程
        self._worker_thread = QThread()
        self._worker = ImageLoadWorker()
        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.start()
        
        # 懒加载定时器
        self.lazy_timer = QTimer()
        self.lazy_timer.setSingleShot(True)
        self.lazy_timer.timeout.connect(self._process_lazy_queue)
    
    def request_image(self, label: QLabel, url: str, priority: int = 0, lazy: bool = True):
        """请求加载图片 - 支持懒加载和优先级"""
        # 检查缓存
        if url in self.cache:
            self._apply_cached_image(label, url)
            return
        
        # 懒加载策略 - 延迟处理，只加载可见图片
        if lazy:
            self.pending_requests[label] = (url, priority)
            if not self.lazy_timer.isActive():
                self.lazy_timer.start(200)  # 200ms后处理
        else:
            self._load_immediately(label, url, priority)
    
    def _is_label_visible(self, label: QLabel) -> bool:
        """检查标签是否在可见区域 - 关键优化"""
        try:
            if not label or not label.isVisible():
                return False
            
            # 获取滚动区域
            parent = label.parent()
            while parent and not isinstance(parent, QScrollArea):
                parent = parent.parent()
            
            if not parent:
                return True
            
            # 可见性检测算法
            scroll_area = parent
            viewport = scroll_area.viewport()
            label_pos = label.mapTo(viewport, label.rect().topLeft())
            label_rect = QRect(label_pos, label.size())
            viewport_rect = viewport.rect()
            
            return label_rect.intersects(viewport_rect)
            
        except Exception:
            return True  # 出错时认为可见
    
    def _process_lazy_queue(self):
        """处理懒加载队列 - 只加载可见图片"""
        visible_requests = []
        
        for label, (url, priority) in list(self.pending_requests.items()):
            if self._is_label_visible(label):
                visible_requests.append((priority, label, url))
        
        # 按优先级排序，限制批量大小
        visible_requests.sort(key=lambda x: x[0], reverse=True)
        max_batch = min(4, len(visible_requests))
        
        for i in range(max_batch):
            priority, label, url = visible_requests[i]
            self._add_to_queue(label, url, priority)
            if label in self.pending_requests:
                del self.pending_requests[label]
        
        # 如果还有待处理请求，继续延迟处理
        if self.pending_requests:
            self.lazy_timer.start(800)
```

#### 1.0.3 页面生命周期管理
```python
class {SourceName}Page(QWidget):
    def __init__(self, adapter, download_manager, parent=None):
        super().__init__(parent)
        
        # 核心组件
        self.adapter = adapter
        self.download_manager = download_manager
        
        # 异步工作线程
        self._worker_thread = None
        self._worker = None
        
        # 图片加载管理器 (保守的并发设置)
        self._image_manager = ImageLoadManager(max_concurrent=1)
        
        # 设置UI和工作线程
        self._setup_ui()
        self._setup_worker_thread()
    
    def _setup_worker_thread(self):
        """设置异步工作线程"""
        self._worker_thread = QThread()
        self._worker = {SourceName}SearchWorker(self.adapter)
        self._worker.moveToThread(self._worker_thread)
        
        # 连接信号
        self._worker.search_completed.connect(self._on_search_completed)
        self._worker.search_failed.connect(self._on_search_failed)
        self._worker.details_completed.connect(self._on_details_completed)
        self._worker.details_failed.connect(self._on_details_failed)
        
        # 连接页面信号到工作线程
        self._search_requested.connect(self._worker.search_comics)
        self._details_requested.connect(self._worker.get_comic_details)
        
        self._worker_thread.start()
    
    def cleanup(self):
        """页面销毁时清理资源 - 防止内存泄漏"""
        # 停止工作线程
        if self._worker_thread and self._worker_thread.isRunning():
            self._worker_thread.quit()
            self._worker_thread.wait()
        
        # 清理图片管理器
        if self._image_manager:
            self._image_manager.cleanup()
        
        # 清理其他资源
        self._clear_results()
```

### 1.0.4 常见性能陷阱和解决方案

#### 陷阱1: 启动时网络请求阻塞
**问题**: 每次启动都要获取域名，导致启动缓慢
```python
# ❌ 错误做法
def initialize(self):
    domain = self._get_domain_from_network()  # 阻塞网络请求
    self.api = SourceAPI(domain)

# ✅ 正确做法  
def initialize(self):
    cached_domain = self.config.get('domain', 'default.domain.com')
    self.api = SourceAPI(cached_domain)  # 使用缓存域名
    # 可选：后台异步验证域名有效性
```

#### 陷阱2: 大量图片同时加载
**问题**: 搜索结果显示时同时加载所有封面图，导致界面卡顿
```python
# ❌ 错误做法
def display_results(self, comics):
    for comic in comics:
        card = self.create_card(comic)
        # 立即加载所有封面图
        self.load_cover_image(card.thumb_label, comic.cover_url)

# ✅ 正确做法
def display_results(self, comics):
    for comic in comics:
        card = self.create_card(comic)
        # 懒加载，只加载可见图片
        self._image_manager.request_image(
            card.thumb_label, 
            comic.cover_url, 
            priority=1, 
            lazy=True
        )
```

#### 陷阱3: 主线程网络请求
**问题**: 在主线程执行网络请求导致界面冻结
```python
# ❌ 错误做法
def on_search_clicked(self):
    keyword = self.search_bar.text()
    results = self.adapter.search(keyword)  # 阻塞主线程
    self.display_results(results)

# ✅ 正确做法
def on_search_clicked(self):
    keyword = self.search_bar.text()
    self.status_label.setText("搜索中...")
    # 发送信号到工作线程
    self._search_requested.emit(keyword, 1)

@Slot(list, int)
def _on_search_completed(self, comics, max_page):
    self.status_label.setText("搜索完成")
    self.display_results(comics)
```

#### 陷阱4: 内存泄漏
**问题**: 页面切换时未清理资源，导致内存泄漏
```python
# ❌ 错误做法
class SourcePage(QWidget):
    def __init__(self):
        self._worker_thread = QThread()
        # 没有清理机制

# ✅ 正确做法
class SourcePage(QWidget):
    def cleanup(self):
        if self._worker_thread:
            self._worker_thread.quit()
            self._worker_thread.wait()
        if self._image_manager:
            self._image_manager.cleanup()
```

### 1.0.5 性能监控和调试
```python
# 添加性能监控代码
import time

class PerformanceMonitor:
    @staticmethod
    def time_function(func_name):
        def decorator(func):
            def wrapper(*args, **kwargs):
                start_time = time.time()
                result = func(*args, **kwargs)
                end_time = time.time()
                print(f"[PERF] {func_name}: {end_time - start_time:.3f}s")
                return result
            return wrapper
        return decorator

# 使用示例
@PerformanceMonitor.time_function("搜索")
def search(self, keyword, page):
    return self.adapter.search(keyword, page)
```

### 1.1 整体布局结构
所有漫画源页面都采用**分割式布局**：
- **顶部搜索栏**：固定高度 60px
- **主体分割区域**：左右分割，比例 5:3 (62.5% : 37.5%)
  - **左侧面板**：搜索结果列表 + 分页控件
  - **右侧面板**：漫画详情 + 操作按钮

### 1.2 搜索栏组件 (固定高度 60px)
```python
# 搜索栏布局参考代码
def _create_search_bar(self) -> QWidget:
    search_container = QWidget()
    search_container.setFixedHeight(60)
    search_container.setStyleSheet("""
        QWidget {
            background-color: #2b2b2b;  //颜色相关需要兼顾深色浅色模式
            border-bottom: 1px solid #3a3a3a;
        }
    """)
    
    layout = QHBoxLayout(search_container)
    layout.setContentsMargins(20, 10, 20, 10)
    layout.setSpacing(10)
    
    # 1. 搜索输入框 (自适应宽度)
    self.search_bar = QLineEdit()
    self.search_bar.setPlaceholderText("搜索{SOURCE_NAME}漫画...")
    self.search_bar.setFixedHeight(40)
    
    # 2. 搜索按钮 (固定宽度 80px)
    self.search_button = QPushButton("搜索")
    self.search_button.setFixedSize(80, 40)
    
    # 3. 设置按钮 (固定宽度 60px)
    settings_btn = QPushButton("设置")
    settings_btn.setFixedSize(60, 40)
    settings_btn.clicked.connect(self._navigate_to_settings)
    
    # 4. 登录状态 (如果支持登录)
    self.login_status = QLabel("未登录")
    self.login_status.setStyleSheet("color: #ff4444; font-weight: bold; margin-left: 20px;")
    
    layout.addWidget(self.search_bar)      # 自适应
    layout.addWidget(self.search_button)   # 80px
    layout.addWidget(settings_btn)         # 60px  
    layout.addWidget(self.login_status)    # 自适应
    
    return search_container
```

### 1.3 左侧搜索结果面板
```python
def _create_results_panel(self) -> QWidget:
    panel = QWidget()
    panel.setStyleSheet("background-color: #1e1e1e;")
    
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setSpacing(10)
    
    # 结果标题
    self.results_label = QLabel("搜索结果")
    
    # 滚动区域 - 显示漫画卡片
    scroll = QScrollArea()
    self.results_container = QWidget()
    self.results_layout = QVBoxLayout(self.results_container)
    scroll.setWidget(self.results_container)
    
    # 分页控件
    pagination_layout = QHBoxLayout()
    self.prev_button = QPushButton("上一页")
    self.page_label = QLabel("第 1 页")
    self.next_button = QPushButton("下一页")
    
    pagination_layout.addWidget(self.prev_button)
    pagination_layout.addStretch()
    pagination_layout.addWidget(self.page_label)
    pagination_layout.addStretch()
    pagination_layout.addWidget(self.next_button)
    
    layout.addWidget(self.results_label)
    layout.addWidget(scroll)
    layout.addLayout(pagination_layout)
    
    return panel
```

### 1.4 右侧详情面板
```python
def _create_details_panel(self) -> QWidget:
    panel = QWidget()
    panel.setStyleSheet("background-color: #252525;")
    
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(20, 20, 20, 20)
    layout.setSpacing(15)
    
    # 占位符
    self.details_placeholder = QLabel("← 选择一个漫画查看详情")
    self.details_placeholder.setAlignment(Qt.AlignCenter)
    
    # 详情内容
    self.details_content = QWidget()
    details_layout = QVBoxLayout(self.details_content)
    
    # 封面图片 (固定尺寸 200x267, 3:4比例)
    self.cover_label = QLabel()
    self.cover_label.setFixedSize(200, 267)
    self.cover_label.setAlignment(Qt.AlignCenter)
    
    # 标题和信息
    self.title_label = QLabel()
    self.author_label = QLabel()
    self.category_label = QLabel()
    self.id_label = QLabel()
    self.chapters_label = QLabel()
    
    # 操作按钮 (固定高度 40px)
    buttons_layout = QHBoxLayout()
    self.read_button = QPushButton("阅读")
    self.download_button = QPushButton("下载")
    self.queue_button = QPushButton("加入队列")
    
    for btn in [self.read_button, self.download_button, self.queue_button]:
        btn.setFixedHeight(40)
    
    buttons_layout.addWidget(self.read_button)
    buttons_layout.addWidget(self.download_button)
    buttons_layout.addWidget(self.queue_button)
    
    details_layout.addWidget(self.cover_label, 0, Qt.AlignHCenter)
    details_layout.addWidget(self.title_label)
    details_layout.addWidget(self.author_label)
    details_layout.addWidget(self.category_label)
    details_layout.addWidget(self.id_label)
    details_layout.addWidget(self.chapters_label)
    details_layout.addLayout(buttons_layout)
    details_layout.addStretch()
    
    layout.addWidget(self.details_placeholder)
    layout.addWidget(self.details_content)
    
    return panel
```

### 1.5 漫画卡片样式 (固定高度 80px)
```python
def _create_result_card(self, comic) -> QWidget:
    card = QFrame()
    card.setFixedHeight(80)
    card.setCursor(Qt.PointingHandCursor)
    
    layout = QHBoxLayout(card)
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setSpacing(15)
    
    # 缩略图 (固定尺寸 45x60)
    thumb = QLabel()
    thumb.setFixedSize(45, 60)
    thumb.setAlignment(Qt.AlignCenter)
    
    # 信息区域
    info_widget = QWidget()
    info_layout = QVBoxLayout(info_widget)
    
    # 标题 (最大高度 36px, 支持2行)
    title = QLabel(comic.title)
    title.setMaximumHeight(36)
    title.setWordWrap(True)
    
    # 作者 (单行)
    author = QLabel(f"作者: {comic.author}")
    
    info_layout.addWidget(title)
    info_layout.addWidget(author)
    info_layout.addStretch()
    
    layout.addWidget(thumb)
    layout.addWidget(info_widget, 1)
    
    return card
```

## 2. 热插拔标签页集成

### 2.1 标签页注册
每个漫画源需要在 `SourceTabManager` 中注册：
```python
# 在 source_tab_manager.py 中添加
AVAILABLE_SOURCES = {
    "jmcomic": {"name": "禁漫天堂", "class": "JMComicPage"},
    "picacg": {"name": "PicACG", "class": "PicACGPage"},
    "wnacg": {"name": "绅士漫画", "class": "WNACGPage"},  # 新增
    # ... 其他源
}
```

### 2.2 页面类命名规范
- 文件名：`{source_name}_page.py`
- 类名：`{SourceName}Page`
- 继承：`QWidget`
- 信号：`read_requested`, `download_requested`, `queue_requested`, `settings_requested`

## 3. 设置页面规范

### 3.1 设置对话框结构
```python
class {SourceName}SettingsDialog(QDialog):
    settings_saved = Signal()
    
    def __init__(self, adapter, parent=None):
        super().__init__(parent)
        self.adapter = adapter
        self.setWindowTitle(f"{SOURCE_DISPLAY_NAME} 设置")
        self.setMinimumSize(500, 600)
        self.setModal(True)
        self._setup_ui()
        self._load_current_settings()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 1. 标题
        title = QLabel(f"{SOURCE_DISPLAY_NAME} 设置")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # 2. 登录设置组 (如果支持)
        if self.adapter.supports_login():
            login_group = self._create_login_group()
            layout.addWidget(login_group)
        
        # 3. 域名/API/分流设置组
        api_group = self._create_api_group()
        layout.addWidget(api_group)
        
        # 4. 其他设置组 (可选)
        other_group = self._create_other_group()
        layout.addWidget(other_group)
        
        # 5. 按钮组
        buttons = self._create_buttons()
        layout.addWidget(buttons)
```

### 3.2 登录设置组 (如果支持登录)
```python
def _create_login_group(self) -> QGroupBox:
    group = QGroupBox("登录设置")
    layout = QVBoxLayout(group)
    
    # 用户名/邮箱
    self.username_edit = QLineEdit()
    self.username_edit.setPlaceholderText("输入用户名/邮箱")
    
    # 密码
    self.password_edit = QLineEdit()
    self.password_edit.setEchoMode(QLineEdit.Password)
    self.password_edit.setPlaceholderText("输入密码")
    
    # 测试登录按钮
    self.login_test_btn = QPushButton("测试登录")
    
    # 自动登录选项
    self.auto_login_checkbox = QCheckBox("启动时自动登录")
    
    layout.addWidget(QLabel("用户名/邮箱:"))
    layout.addWidget(self.username_edit)
    layout.addWidget(QLabel("密码:"))
    layout.addWidget(self.password_edit)
    layout.addWidget(self.login_test_btn)
    layout.addWidget(self.auto_login_checkbox)
    
    return group
```

### 3.3 域名/API设置组
```python
def _create_api_group(self) -> QGroupBox:
    group = QGroupBox("域名/API 设置")
    layout = QVBoxLayout(group)
    
    # 域名选择 (如果支持多域名)
    if hasattr(self.adapter, 'get_available_domains'):
        self.domain_combo = QComboBox()
        self.domain_combo.addItems(self.adapter.get_available_domains())
        
        domain_test_layout = QHBoxLayout()
        self.domain_test_btn = QPushButton("测试域名")
        self.domain_result_label = QLabel("点击测试域名可用性")
        domain_test_layout.addWidget(self.domain_test_btn)
        domain_test_layout.addWidget(self.domain_result_label, 1)
        
        layout.addWidget(QLabel("域名选择:"))
        layout.addWidget(self.domain_combo)
        layout.addLayout(domain_test_layout)
    
    # API分流选择 (如果支持)
    if hasattr(self.adapter, 'get_api_endpoints'):
        self.api_combo = QComboBox()
        self.api_combo.addItems(self.adapter.get_api_endpoints())
        
        api_test_layout = QHBoxLayout()
        self.api_test_btn = QPushButton("测试API分流")
        self.api_result_label = QLabel("点击测试API响应时间")
        api_test_layout.addWidget(self.api_test_btn)
        api_test_layout.addWidget(self.api_result_label, 1)
        
        layout.addWidget(QLabel("API 端点:"))
        layout.addWidget(self.api_combo)
        layout.addLayout(api_test_layout)
    
    return group
```

### 3.4 设置永久化
```python
def _save_settings(self):
    """保存设置到配置文件"""
    from pancomic.core.app import App
    app = App()
    config_manager = app.config_manager
    
    # 保存登录设置
    if hasattr(self, 'username_edit'):
        config_manager.set(f'{self.adapter.SOURCE_NAME}.username', self.username_edit.text())
        config_manager.set(f'{self.adapter.SOURCE_NAME}.password', self.password_edit.text())
        config_manager.set(f'{self.adapter.SOURCE_NAME}.auto_login', self.auto_login_checkbox.isChecked())
    
    # 保存域名/API设置
    if hasattr(self, 'domain_combo'):
        config_manager.set(f'{self.adapter.SOURCE_NAME}.domain', self.domain_combo.currentText())
    if hasattr(self, 'api_combo'):
        config_manager.set(f'{self.adapter.SOURCE_NAME}.api_endpoint', self.api_combo.currentText())
    
    # 保存配置文件
    config_manager.save()
    
    # 发送信号
    self.settings_saved.emit()
```

## 4. 下载文件格式规范

### 4.1 目录结构
```
downloads/
├── {source_name}/           # 漫画源名称 (如: wnacg, jmcomic, picacg)
│   ├── {comic_id}/          # 漫画ID目录
│   │   ├── metadata.json    # 漫画元数据
│   │   ├── cover.jpg        # 封面图片 (可选)
│   │   └── {chapter_id}/    # 章节目录
│   │       ├── 001.jpg      # 图片文件 (按页码命名)
│   │       ├── 002.jpg
│   │       └── ...
│   └── {comic_id2}/
└── {source_name2}/
```

### 4.2 metadata.json 格式
```json
{
    "source": "wnacg",
    "comic_id": "337185",
    "title": "鹿島とHな私生活",
    "author": "タケユウ",
    "tags": ["艦これ", "同人誌"],
    "category": "同人誌 / 漢化",
    "pages": 24,
    "chapters": [
        {
            "chapter_id": "1",
            "title": "全本",
            "pages": 24,
            "downloaded": true,
            "download_time": "2025-01-01T12:00:00Z"
        }
    ],
    "download_info": {
        "created_time": "2025-01-01T12:00:00Z",
        "updated_time": "2025-01-01T12:00:00Z",
        "total_size": 52428800,
        "status": "completed"
    }
}
```

### 4.3 文件命名规范
- **图片文件**：`{page:03d}.{ext}` (如: 001.jpg, 002.png)
- **封面文件**：`cover.{ext}`
- **元数据文件**：`metadata.json`
- **章节目录**：`{chapter_id}` 或 `chapter_{chapter_id}`

## 5. 适配器接口规范

### 5.1 必需方法
```python
class {SourceName}Adapter:
    SOURCE_NAME = "source_name"
    SOURCE_DISPLAY_NAME = "显示名称"
    
    def search(self, keyword: str, page: int = 1) -> dict
    def get_comic_details(self, comic_id: str) -> dict
    def get_chapter_images(self, comic_id: str, chapter_id: str) -> list
    
    # 可选方法
    def supports_login(self) -> bool
    def get_available_domains(self) -> list
    def get_api_endpoints(self) -> list
```

### 5.2 信号定义
```python
# 页面类必需信号
read_requested = Signal(object, object)      # Comic, Chapter
download_requested = Signal(object, list)   # Comic, List[Chapter]
queue_requested = Signal(object, list)      # Comic, List[Chapter]
settings_requested = Signal()               # 打开设置页面
```

## 6. 主题支持

每个页面都需要实现 `apply_theme(theme: str)` 方法：
```python
def apply_theme(self, theme: str):
    """应用主题到页面组件"""
    if theme == 'light':
        # 浅色主题配色
        bg_primary = '#FFFFFF'
        text_primary = '#000000'
        # ...
    else:
        # 深色主题配色
        bg_primary = '#1e1e1e'
        text_primary = '#ffffff'
        # ...
    
    # 应用样式到各个组件
    self.setStyleSheet(f"background-color: {bg_primary};")
    # ...
```

## 7. 常见问题和解决方案

### 7.1 集成过程中的常见错误

#### 错误1: 适配器初始化失败
```
KeyError: "Source 'source_name' not found in configuration"
```
**原因**: 配置文件中缺少源配置
**解决方案**:
```json
// downloads/config.json 中添加
{
  "source_name": {
    "enabled": true,
    "domain": "default.domain.com"
  }
}
```

#### 错误2: 数据模型验证失败
```
ValueError: Comic source must be one of ['jmcomic', 'picacg', 'wnacg'], got 'new_source'
```
**原因**: 新源未添加到 valid_sources 列表
**解决方案**:
```python
# pancomic/models/comic.py 和 chapter.py
valid_sources = ["jmcomic", "picacg", "wnacg", "new_source", "user"]
```

#### 错误3: 下载方法参数不匹配
```
TypeError: download_chapter() missing 1 required positional argument: 'progress_callback'
```
**原因**: 基类接口更新，缺少新参数
**解决方案**:
```python
def download_chapter(self, comic: Comic, chapter: Chapter, download_path: str, progress_callback=None) -> bool:
    # 实现下载逻辑
    if progress_callback:
        progress_callback(current, total)
```

#### 错误4: 工作线程相关错误
```
QThread: Destroyed while thread is still running
```
**原因**: 页面销毁时未正确清理线程
**解决方案**:
```python
def cleanup(self):
    if self._worker_thread and self._worker_thread.isRunning():
        self._worker_thread.quit()
        self._worker_thread.wait(3000)  # 等待最多3秒
```

### 7.2 性能问题诊断

#### 问题1: 启动缓慢
**症状**: 应用启动需要3-5秒
**诊断步骤**:
1. 检查是否有启动时的网络请求
2. 查看日志中的域名获取过程
3. 检查配置文件是否有缓存域名

**解决方案**:
```python
# 使用缓存域名，避免启动时网络请求
def initialize(self):
    cached_domain = self.config.get('domain', 'default.domain.com')
    self.api = SourceAPI(cached_domain)
```

#### 问题2: 搜索结果显示卡顿
**症状**: 搜索完成后界面冻结2-3秒
**诊断步骤**:
1. 检查是否在主线程执行网络请求
2. 查看图片加载策略
3. 监控内存使用情况

**解决方案**:
```python
# 实现异步搜索 + 懒加载图片
class SearchWorker(QObject):
    @Slot(str, int)
    def search_comics(self, keyword, page):
        # 在工作线程中执行搜索
        pass

# 懒加载图片
self._image_manager.request_image(label, url, lazy=True)
```

#### 问题3: 内存占用持续增长
**症状**: 长时间使用后内存占用越来越高
**诊断步骤**:
1. 检查图片缓存是否有大小限制
2. 查看是否有未清理的资源
3. 检查工作线程是否正确关闭

**解决方案**:
```python
# 限制缓存大小
class ImageLoadManager:
    def __init__(self, max_cache_size=100):
        self.cache = {}
        self.max_cache_size = max_cache_size
    
    def _add_to_cache(self, url, pixmap):
        if len(self.cache) >= self.max_cache_size:
            # 清理最旧的缓存
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
        self.cache[url] = pixmap
```

### 7.3 网络相关问题

#### 问题1: 反爬虫检测
**症状**: 搜索返回空结果或403错误
**解决方案**:
```python
# 使用验证过的headers
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://target-site.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# 添加请求间隔
import time
time.sleep(0.5)  # 500ms间隔
```

#### 问题2: 域名失效
**症状**: 网络请求超时或连接失败
**解决方案**:
```python
def refresh_domain(self):
    """手动刷新域名"""
    try:
        new_domain = self._discover_domain()
        if new_domain:
            self.config['domain'] = new_domain
            self.api.domain = new_domain
            return new_domain
    except Exception as e:
        print(f"域名刷新失败: {e}")
        raise
```

### 7.4 UI相关问题

#### 问题1: 图片显示异常
**症状**: 封面图片显示为"×"或空白
**诊断步骤**:
1. 检查图片URL是否有效
2. 查看是否需要特殊headers
3. 检查图片格式是否支持

**解决方案**:
```python
def load_image(self, url):
    try:
        # 使用正确的headers
        response = self.client.get(url, headers=self.image_headers)
        response.raise_for_status()
        
        pixmap = QPixmap()
        if pixmap.loadFromData(response.content):
            return pixmap
        else:
            print(f"图片格式不支持: {url}")
            return None
    except Exception as e:
        print(f"图片加载失败: {e}")
        return None
```

#### 问题2: 主题切换不生效
**症状**: 切换主题后部分组件颜色未更新
**解决方案**:
```python
def apply_theme(self, theme):
    """确保所有组件都应用主题"""
    colors = self._get_theme_colors(theme)
    
    # 更新所有组件样式
    self.setStyleSheet(f"background-color: {colors['bg_primary']};")
    self.search_bar.setStyleSheet(f"color: {colors['text_primary']};")
    # ... 更新其他组件
    
    # 递归更新子组件
    for child in self.findChildren(QWidget):
        if hasattr(child, 'apply_theme'):
            child.apply_theme(theme)
```

### 7.5 调试技巧

#### 7.5.1 日志记录
```python
import logging

# 设置详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def search(self, keyword, page):
    logger.debug(f"开始搜索: keyword={keyword}, page={page}")
    try:
        result = self.api.search(keyword, page)
        logger.debug(f"搜索完成: {len(result['comics'])} 个结果")
        return result
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        raise
```

#### 7.5.2 性能分析
```python
import cProfile
import pstats

def profile_search():
    """性能分析搜索功能"""
    profiler = cProfile.Profile()
    profiler.enable()
    
    # 执行搜索
    adapter.search("test", 1)
    
    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(10)  # 显示前10个最耗时的函数
```

#### 7.5.3 内存监控
```python
import psutil
import os

def monitor_memory():
    """监控内存使用"""
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    print(f"内存使用: {memory_info.rss / 1024 / 1024:.2f} MB")
```

## 8. 最佳实践总结

### 8.1 开发流程最佳实践
1. **先测试API稳定性**: 在独立测试环境验证反爬虫策略
2. **分阶段集成**: API → 适配器 → 核心集成 → UI → 优化
3. **性能优先**: 从一开始就考虑异步架构和性能优化
4. **完善错误处理**: 每个网络请求都要有异常处理

### 8.2 代码质量最佳实践
1. **遵循命名规范**: 文件名、类名、方法名保持一致
2. **完善文档注释**: 每个公共方法都要有详细注释
3. **单元测试**: 为关键功能编写测试用例
4. **代码审查**: 集成前进行代码审查

### 8.3 性能优化最佳实践
1. **异步优先**: 所有网络操作使用异步架构
2. **懒加载**: 图片和数据按需加载
3. **缓存策略**: 合理使用缓存，但要控制大小
4. **资源清理**: 及时清理不再使用的资源

### 8.4 用户体验最佳实践
1. **响应式设计**: 界面要能适应不同窗口大小
2. **加载状态**: 长时间操作要显示进度
3. **错误提示**: 友好的错误信息和恢复建议
4. **一致性**: 保持与其他源的界面一致性

---

## 结语

本指南基于 WNACG 集成的实际经验编写，涵盖了从API开发到UI集成的完整流程。遵循这些规范和最佳实践，可以确保新漫画源的集成质量和性能。

关键成功因素:
1. **充分的前期调研和准备**
2. **遵循分层架构和接口规范**  
3. **重视性能优化和用户体验**
4. **完善的错误处理和资源管理**

每个新源的集成都是对系统架构的验证和完善，通过不断积累经验，PanComic 的扩展性和稳定性将持续提升。

---

