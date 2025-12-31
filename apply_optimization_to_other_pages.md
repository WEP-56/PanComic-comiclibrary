# 将渐进式搜索优化应用到其他页面

简单来说，除了普通的线程分级1.爬虫线程。2.解析线程。
再增加一个3.分块渲染线程
在这个线程里，搜索结果解析过程中，每解析x个（pancomic一般是4个）就发给主线程一次，让主线程多次少量的渲染结果卡片。以防止解析的数据一下子全部给到主线程，造成卡顿

## 🎯 适用场景

这个优化方案适用于所有需要显示大量搜索结果的页面：

1. **拷贝漫画 (Kaobei) 页面** - 当前使用旧的实现
2. **PicACG 页面** - 如果存在类似问题
3. **JMComic 页面** - 如果存在类似问题
4. **其他未来的漫画源页面**

## 🔧 应用步骤

### 1. 复制核心组件

#### 复制渐进式工作线程
```bash
# 复制到项目中
cp pancomic/ui/workers/progressive_search_worker.py pancomic/ui/workers/
```

#### 修改适配器接口
```python
# 在新的工作线程中替换适配器
class ProgressiveSearchWorker(QObject):
    def __init__(self, adapter, batch_size: int = 6):
        # 替换为对应的适配器
        self.adapter = adapter  # KaobeiAdapter, PicACGAdapter 等
```

### 2. 修改页面实现

#### 替换搜索工作线程
```python
# 原来的实现
from pancomic.ui.pages.kaobei_page import KaobeiSearchWorker

# 替换为
from pancomic.ui.workers.progressive_search_worker import ProgressiveSearchWorker
```

#### 添加逐个渲染机制
```python
class OptimizedKaobeiPage(QWidget):
    def __init__(self, ...):
        # 添加渐进式渲染状态
        self._pending_comics = []
        self._is_rendering_cards = False
        self._card_render_timer = QTimer()
        self._card_render_timer.timeout.connect(self._render_next_card)
        
        # 设置渲染速度
        self.set_render_speed('normal')
```

#### 修改信号处理
```python
# 替换原来的搜索完成处理
@Slot(object)
def _on_batch_ready(self, batch: ComicBatch):
    """处理批次数据就绪"""
    if batch.task_id != self._current_task_id:
        return
    
    # 添加到逐个渲染队列
    self._pending_comics.extend(batch.comics)
    
    # 开始渲染
    if not self._is_rendering_cards:
        self._start_card_rendering()
```

### 3. 适配不同的数据结构

#### Kaobei 页面适配
```python
class KaobeiParserWorker:
    def parse_comic_batch(self, raw_comics: List[Dict], batch_index: int) -> List[Comic]:
        comics = []
        for comic_data in raw_comics:
            comic = Comic(
                id=comic_data["comic_id"],
                title=comic_data["title"],
                # ... Kaobei 特有的字段映射
                source="kaobei"
            )
            comics.append(comic)
        return comics
```

#### PicACG 页面适配
```python
class PicACGParserWorker:
    def parse_comic_batch(self, raw_comics: List[Dict], batch_index: int) -> List[Comic]:
        comics = []
        for comic_data in raw_comics:
            comic = Comic(
                id=comic_data["_id"],
                title=comic_data["title"],
                # ... PicACG 特有的字段映射
                source="picacg"
            )
            comics.append(comic)
        return comics
```

## 📋 完整的迁移清单

### ✅ 必须实现的组件

1. **ProgressiveSearchWorker** - 渐进式搜索工作线程
2. **CrawlerWorker** - 爬虫工作者（适配对应的API）
3. **ParserWorker** - 解析工作者（适配对应的数据格式）
4. **ComicBatch** - 批次数据结构
5. **逐个渲染机制** - _render_next_card, _start_card_rendering 等
6. **停止信号机制** - _stop_all_activities, cleanup 等

### ✅ 需要适配的部分

1. **API调用方式** - 不同漫画源的搜索API
2. **数据解析逻辑** - 不同的JSON结构
3. **Comic对象映射** - 字段名称可能不同
4. **错误处理** - 不同API的错误格式

### ✅ 可选的优化

1. **渲染速度配置** - 根据页面特点调整
2. **批次大小调整** - 根据数据量调整
3. **图片加载策略** - 根据图片大小调整
4. **进度显示方式** - 根据UI设计调整

## 🚀 快速应用示例

### 将优化应用到 Kaobei 页面

#### 1. 创建优化版本
```python
# pancomic/ui/pages/kaobei_page_optimized.py
from pancomic.ui.workers.progressive_search_worker import ProgressiveSearchWorker

class OptimizedKaobeiPage(QWidget):
    def __init__(self, adapter: KaobeiAdapter, ...):
        # 复制 OptimizedWNACGPage 的实现
        # 修改适配器和数据解析部分
```

#### 2. 修改适配器调用
```python
class KaobeiCrawlerWorker:
    def __init__(self, adapter):
        self.adapter = adapter
    
    def fetch_search_data(self, keyword: str, page: int) -> Dict[str, Any]:
        # 调用 KaobeiAdapter 的搜索方法
        return self.adapter.search(keyword, page)
```

#### 3. 修改数据解析
```python
class KaobeiParserWorker:
    def parse_comic_batch(self, raw_comics: List[Dict], batch_index: int) -> List[Comic]:
        # 解析 Kaobei 特有的数据格式
        # 返回 Comic 对象列表
```

#### 4. 更新主窗口
```python
# 在主窗口中替换页面
from pancomic.ui.pages.kaobei_page_optimized import OptimizedKaobeiPage

# 替换原来的 KaobeiPage
self.kaobei_page = OptimizedKaobeiPage(self.kaobei_adapter, self.download_manager)
```

## 🔍 测试验证

### 性能测试
1. **搜索30个结果** - 观察卡片出现方式
2. **重复搜索** - 验证停止机制
3. **快速切换** - 验证资源清理
4. **标签页关闭** - 验证完全清理

### 预期效果
- ✅ 卡片逐个流畅出现
- ✅ 封面图片逐个加载
- ✅ 无瞬间卡顿感
- ✅ 可随时取消/重新搜索





