# 知网 MCP 服务升级计划 v2.0（基于实际DOM结构）

> **核心理念**: 将浏览器从"盲目执行器"升级为"可感知、可控制、可记忆"的智能代理

## 一、实际DOM结构分析结果

### 1.1 搜索结果页关键元素（已验证）

```python
# 结果总数
"span.pagerTitleCell"  # 文本: "找到1,557条结果"

# 页码信息
"span.countPageMark"   # 文本: "1/78" (当前页/总页数)

# 分页控件
"div.search-page"      # 容器
  "a.but-l"            # 上一页按钮 (<)
  "a.but-r"            # 下一页按钮 (>)
  "b"                  # 当前页码
  "em"                 # 总页数

# 搜索类型切换（这是搜索类型，不是排序！）
"div.sort.reopt"       # 容器
  "div.sort-default"   # 当前选中类型显示
  "ul > li[data-val]"  # 类型选项列表
    # data-val: SU(主题), TI(篇名), AU(作者), KY(关键词), etc.

# 结果列表
"table.result-table-list"
  "tbody > tr"         # 每一行是一篇文章
    "td.name > a.fz14" # 标题链接
    "td.author"        # 作者
    "td.source"        # 来源
    "td.date"          # 日期

# 资源类型筛选
"a[resource='DISSERTATION']"  # 学位论文
"a[resource='JOURNAL']"       # 学术期刊
"a[resource='CONFERENCE']"    # 会议
```

### 1.2 重要发现

**⚠️ 关键问题**: 
- **没有找到排序控件**！知网搜索结果页可能不支持前端排序切换
- `div.sort` 实际上是**搜索类型切换**，不是排序功能
- 分页控件非常简单，只有"上一页/下一页"按钮，没有页码跳转

## 二、升级架构设计

### 2.1 核心能力分层

```
┌─────────────────────────────────────────────────┐
│  MCP 工具层（Agent 调用接口）                      │
├─────────────────────────────────────────────────┤
│  业务流程层（组合操作）                            │
│  - search_and_get_details()                     │
│  - batch_navigate_and_collect()                 │
├─────────────────────────────────────────────────┤
│  页面操作层（原子操作）                            │
│  - get_page_status()                            │
│  - next_page() / prev_page()                    │
│  - switch_search_type()                         │
│  - filter_by_resource()                         │
├─────────────────────────────────────────────────┤
│  状态管理层（会话状态）                            │
│  - StateManager                                 │
│  - SearchSession                                │
├─────────────────────────────────────────────────┤
│  底层检测层（DOM 查询）                            │
│  - _get_current_page_type()                     │
│  - _extract_result_count()                      │
│  - _extract_page_info()                         │
│  - _wait_for_page_loaded()                      │
└─────────────────────────────────────────────────┘
```

### 2.2 状态管理模型

```python
class PageState(str, Enum):
    HOME = "home"              # 知网首页
    SEARCH_RESULT = "search"   # 搜索结果页
    PAPER_DETAIL = "detail"    # 论文详情页
    UNKNOWN = "unknown"        # 未知页面

class SearchSession(BaseModel):
    session_id: str
    keyword: str
    search_type: SearchType
    filter_resource: str = ""
    
    # 页面状态
    current_page: int = 1
    total_pages: int = 0
    total_results: int = 0
    
    # 当前结果缓存
    current_results: list[CNKIPaper] = []
    
    # 时间戳
    created_at: datetime
    last_accessed: datetime
    
    # 操作历史
    history: list[str] = []
```

## 三、实施任务清单

### 阶段1: 状态感知能力（优先级：最高）⭐⭐⭐

#### 任务 1.1: 实现底层检测方法

```python
def _get_current_page_type(self) -> PageState:
    """通过URL判断页面类型"""
    url = self._page.url
    if "kns8s/defaultresult" in url or "kns8s/search" in url:
        return PageState.SEARCH_RESULT
    elif "kcms/detail" in url or "kcms2/article" in url:
        return PageState.PAPER_DETAIL
    elif "kns.cnki.net" in url and url.count('/') <= 3:
        return PageState.HOME
    return PageState.UNKNOWN

def _extract_result_count(self) -> int:
    """提取搜索结果总数"""
    try:
        elem = self._page.locator("span.pagerTitleCell").first
        if elem and elem.is_visible(timeout=2000):
            text = elem.inner_text()
            # 提取 "找到1,557条结果" 中的数字
            match = re.search(r'(\d+(?:,\d+)*)', text)
            if match:
                return int(match.group(1).replace(',', ''))
    except Exception:
        pass
    return 0

def _extract_page_info(self) -> tuple[int, int]:
    """提取当前页码和总页数"""
    try:
        elem = self._page.locator("span.countPageMark").first
        if elem and elem.is_visible(timeout=2000):
            text = elem.inner_text()  # "1/78"
            match = re.search(r'(\d+)/(\d+)', text)
            if match:
                return int(match.group(1)), int(match.group(2))
    except Exception:
        pass
    return 1, 1

def _wait_for_page_loaded(self, timeout: int = 10000) -> bool:
    """等待搜索结果页加载完成"""
    start_time = time.time()
    while (time.time() - start_time) * 1000 < timeout:
        try:
            # 检查结果总数元素是否出现
            if self._page.locator("span.pagerTitleCell").count() > 0:
                # 检查结果表格是否出现
                if self._page.locator("table.result-table-list").count() > 0:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False
```

#### 任务 1.2: 实现页面状态报告

```python
def get_page_status(self) -> dict:
    """获取当前页面完整状态"""
    if not self.is_ready():
        return {"error": "浏览器未初始化"}
    
    page_type = self._get_current_page_type()
    status = {
        "page_type": page_type.value,
        "url": self._page.url,
        "title": self._page.title(),
        "is_loading": False,
        "has_error": False,
    }
    
    # 如果是搜索结果页，提取详细信息
    if page_type == PageState.SEARCH_RESULT:
        status["result_count"] = self._extract_result_count()
        current_page, total_pages = self._extract_page_info()
        status["current_page"] = current_page
        status["total_pages"] = total_pages
        
        # 检测当前搜索类型
        try:
            sort_default = self._page.locator("div.sort-default span").first
            if sort_default:
                status["search_type"] = sort_default.get_attribute("title") or ""
        except Exception:
            status["search_type"] = ""
        
        # 检测当前筛选条件
        try:
            active_filter = self._page.locator("a[resource].active, a[resource].cur").first
            if active_filter:
                status["filter_active"] = active_filter.get_attribute("resource") or ""
        except Exception:
            status["filter_active"] = ""
    
    return status
```

#### 任务 1.3: 添加 MCP 工具

```python
@server.call_tool()
async def cnki_get_status() -> list[TextContent]:
    """获取当前浏览器页面状态"""
    browser = get_browser()
    status = browser.get_page_status()
    return [TextContent(
        type="text",
        text=json.dumps(status, ensure_ascii=False, indent=2)
    )]

# 工具定义
Tool(
    name="cnki_get_status",
    description="获取当前知网页面状态，包括页面类型、搜索结果数、当前页码、总页数等信息。用于Agent了解当前浏览器状态。",
    inputSchema={"type": "object", "properties": {}}
)
```

### 阶段2: 导航控制能力（优先级：高）⭐⭐⭐

#### 任务 2.1: 实现分页导航

```python
def next_page(self) -> bool:
    """跳转到下一页"""
    if self._get_current_page_type() != PageState.SEARCH_RESULT:
        safe_print("错误：当前不在搜索结果页")
        return False
    
    try:
        # 查找下一页按钮
        next_btn = self._page.locator("div.search-page a.but-r").first
        if not next_btn or not next_btn.is_visible(timeout=2000):
            safe_print("未找到下一页按钮")
            return False
        
        # 获取当前页码
        current_page, total_pages = self._extract_page_info()
        if current_page >= total_pages:
            safe_print(f"已经是最后一页 ({current_page}/{total_pages})")
            return False
        
        safe_print(f"正在跳转到第 {current_page + 1} 页...")
        next_btn.click()
        self._random_delay(3, 5)
        
        # 等待新页面加载
        if self._wait_for_page_loaded():
            new_page, _ = self._extract_page_info()
            if new_page == current_page + 1:
                safe_print(f"成功跳转到第 {new_page} 页")
                return True
        
        safe_print("页面加载失败或页码未变化")
        return False
        
    except Exception as e:
        safe_print(f"翻页失败：{str(e)}")
        return False

def prev_page(self) -> bool:
    """跳转到上一页"""
    if self._get_current_page_type() != PageState.SEARCH_RESULT:
        safe_print("错误：当前不在搜索结果页")
        return False
    
    try:
        # 查找上一页按钮
        prev_btn = self._page.locator("div.search-page a.but-l").first
        if not prev_btn or not prev_btn.is_visible(timeout=2000):
            safe_print("未找到上一页按钮")
            return False
        
        # 获取当前页码
        current_page, _ = self._extract_page_info()
        if current_page <= 1:
            safe_print("已经是第一页")
            return False
        
        safe_print(f"正在跳转到第 {current_page - 1} 页...")
        prev_btn.click()
        self._random_delay(3, 5)
        
        # 等待新页面加载
        if self._wait_for_page_loaded():
            new_page, _ = self._extract_page_info()
            if new_page == current_page - 1:
                safe_print(f"成功跳转到第 {new_page} 页")
                return True
        
        safe_print("页面加载失败或页码未变化")
        return False
        
    except Exception as e:
        safe_print(f"翻页失败：{str(e)}")
        return False
```

#### 任务 2.2: 添加 MCP 工具

```python
@server.call_tool()
async def cnki_navigate_page(action: str) -> list[TextContent]:
    """在搜索结果中翻页"""
    browser = get_browser()
    
    if action == "next":
        success = await asyncio.to_thread(browser.next_page)
    elif action == "prev":
        success = await asyncio.to_thread(browser.prev_page)
    else:
        return [TextContent(type="text", text=f"错误：未知操作 {action}")]
    
    if success:
        status = browser.get_page_status()
        return [TextContent(
            type="text",
            text=f"翻页成功！当前第 {status.get('current_page')} 页，共 {status.get('total_pages')} 页"
        )]
    else:
        return [TextContent(type="text", text="翻页失败")]

# 工具定义
Tool(
    name="cnki_navigate_page",
    description="在搜索结果中翻页（上一页/下一页）。注意：知网不支持直接跳转到指定页码。",
    inputSchema={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "翻页操作：next(下一页), prev(上一页)",
                "enum": ["next", "prev"]
            }
        },
        "required": ["action"]
    }
)
```

### 阶段3: 批量操作能力（优先级：中）⭐⭐

#### 任务 3.1: 实现跨页批量获取

```python
def batch_get_details_across_pages(
    self,
    max_count: int = 20,
    max_pages: int = 5
) -> list[CNKIPaper]:
    """跨页批量获取论文详情
    
    Args:
        max_count: 最大获取数量
        max_pages: 最大翻页数
        
    Returns:
        论文详情列表
    """
    if self._get_current_page_type() != PageState.SEARCH_RESULT:
        safe_print("错误：当前不在搜索结果页")
        return []
    
    all_papers = []
    pages_visited = 0
    
    safe_print(f"开始批量获取，目标 {max_count} 篇，最多翻 {max_pages} 页")
    
    while len(all_papers) < max_count and pages_visited < max_pages:
        # 获取当前页结果
        current_page, total_pages = self._extract_page_info()
        safe_print(f"\n[页 {current_page}/{total_pages}] 正在解析...")
        
        results = self._parse_results(self._page, page_size=20)
        safe_print(f"  当前页找到 {len(results)} 条结果")
        
        # 获取详情
        for i, paper in enumerate(results):
            if len(all_papers) >= max_count:
                break
            
            if paper.link:
                safe_print(f"  [{len(all_papers)+1}/{max_count}] {paper.title[:40]}...")
                detail = self.get_paper_detail(paper.link)
                if detail:
                    all_papers.append(detail)
                self._random_delay(3, 5)  # 避免请求过快
        
        # 检查是否需要翻页
        if len(all_papers) >= max_count:
            break
        
        pages_visited += 1
        if pages_visited >= max_pages:
            break
        
        # 翻到下一页
        if not self.next_page():
            safe_print("无法翻页，停止批量获取")
            break
    
    safe_print(f"\n批量获取完成！共获取 {len(all_papers)} 篇")
    return all_papers
```

#### 任务 3.2: 添加 MCP 工具

```python
Tool(
    name="cnki_batch_get_details",
    description="跨页批量获取多篇论文的详细信息。会自动翻页直到达到目标数量或页数限制。",
    inputSchema={
        "type": "object",
        "properties": {
            "max_count": {
                "type": "integer",
                "description": "最大获取数量（建议≤20，避免触发反爬虫）",
                "default": 10,
                "minimum": 1,
                "maximum": 50
            },
            "max_pages": {
                "type": "integer",
                "description": "最大翻页数",
                "default": 3,
                "minimum": 1,
                "maximum": 10
            }
        }
    }
)
```

### 阶段4: 会话管理（优先级：中）⭐⭐

#### 任务 4.1: 实现简化版会话管理

```python
class StateManager:
    def __init__(self):
        self.current_session: Optional[SearchSession] = None
        self.session_history: list[SearchSession] = []
    
    def create_session(self, keyword: str, search_type: SearchType, **kwargs) -> SearchSession:
        """创建新会话"""
        session = SearchSession(
            session_id=str(uuid.uuid4())[:8],
            keyword=keyword,
            search_type=search_type,
            created_at=datetime.now(),
            last_accessed=datetime.now(),
            **kwargs
        )
        self.current_session = session
        self.session_history.append(session)
        return session
    
    def update_session(self, **kwargs):
        """更新当前会话"""
        if self.current_session:
            for key, value in kwargs.items():
                if hasattr(self.current_session, key):
                    setattr(self.current_session, key, value)
            self.current_session.last_accessed = datetime.now()
    
    def get_session_summary(self) -> dict:
        """获取当前会话摘要"""
        if not self.current_session:
            return {"error": "无活动会话"}
        
        s = self.current_session
        return {
            "session_id": s.session_id,
            "keyword": s.keyword,
            "search_type": s.search_type.value,
            "current_page": s.current_page,
            "total_pages": s.total_pages,
            "total_results": s.total_results,
            "created_at": s.created_at.isoformat(),
        }
```

## 四、MCP 工具完整清单

### 4.1 核心工具（必须实现）

| 工具名 | 功能 | 优先级 |
|--------|------|--------|
| `cnki_search` | 执行搜索（已有） | ✅ 已实现 |
| `cnki_get_paper_detail` | 获取论文详情（已有） | ✅ 已实现 |
| `cnki_get_status` | 获取页面状态 | ⭐⭐⭐ 最高 |
| `cnki_navigate_page` | 翻页（上一页/下一页） | ⭐⭐⭐ 高 |
| `cnki_batch_get_details` | 批量获取详情 | ⭐⭐ 中 |

### 4.2 辅助工具（可选实现）

| 工具名 | 功能 | 优先级 |
|--------|------|--------|
| `cnki_get_session_info` | 获取当前会话信息 | ⭐ 低 |
| `cnki_export_results` | 导出结果为CSV | ⭐ 低 |

## 五、关键注意事项

### 5.1 浏览器状态管理

**⚠️ 核心原则**: 每次操作前必须验证页面状态

```python
# 错误示例（盲目执行）
def bad_next_page(self):
    self._page.locator("a.but-r").click()  # 可能不在搜索结果页！

# 正确示例（先检查状态）
def good_next_page(self):
    if self._get_current_page_type() != PageState.SEARCH_RESULT:
        return False
    # ... 继续执行
```

### 5.2 页面加载等待策略

```python
def _wait_for_page_loaded(self, timeout: int = 10000) -> bool:
    """多重检测确保页面加载完成"""
    checks = [
        lambda: self._page.locator("span.pagerTitleCell").count() > 0,
        lambda: self._page.locator("table.result-table-list").count() > 0,
        lambda: self._page.locator("tbody tr").count() > 0,
    ]
    
    start_time = time.time()
    while (time.time() - start_time) * 1000 < timeout:
        if all(check() for check in checks):
            return True
        time.sleep(0.5)
    return False
```

### 5.3 反爬虫策略

1. **延迟控制**: 批量操作时每篇论文间隔 3-5 秒
2. **数量限制**: 单次批量获取建议 ≤ 20 篇
3. **错误恢复**: 遇到验证码时暂停并提示用户

### 5.4 错误处理

```python
def safe_operation(self, operation_name: str, operation_func):
    """安全执行操作，带错误恢复"""
    try:
        # 检查验证码
        if self._check_captcha(self._page):
            self._wait_for_captcha(self._page)
        
        # 执行操作
        result = operation_func()
        
        # 验证操作成功
        if self._check_captcha(self._page):
            self._wait_for_captcha(self._page)
        
        return result
        
    except Exception as e:
        safe_print(f"{operation_name} 失败：{str(e)}")
        return None
```

## 六、实施时间表

| 阶段 | 任务 | 预计时间 | 状态 |
|------|------|----------|------|
| 1 | 状态感知能力 | 1-2天 | ⏳ 待开始 |
| 2 | 导航控制能力 | 1-2天 | ⏳ 待开始 |
| 3 | 批量操作能力 | 1天 | ⏳ 待开始 |
| 4 | 会话管理 | 1天 | ⏳ 待开始 |
| 5 | 集成测试 | 1天 | ⏳ 待开始 |

**总计**: 5-7 天

## 七、验收标准

### 7.1 功能验收

- [ ] 可准确获取页面状态（页面类型、结果数、页码）
- [ ] 可成功翻页（上一页/下一页）
- [ ] 可批量获取跨页论文详情
- [ ] 操作失败时有明确的错误提示
- [ ] 遇到验证码时能正确处理

### 7.2 性能验收

- [ ] 状态查询响应时间 < 1秒
- [ ] 翻页操作完成时间 < 5秒
- [ ] 批量获取10篇论文 < 2分钟

### 7.3 稳定性验收

- [ ] 连续翻页10次无错误
- [ ] 批量获取20篇论文无中断
- [ ] 验证码处理成功率 100%

## 八、升级后的使用示例

### 示例1: 智能跨页检索

```
用户: "搜索'数字文物'相关的学位论文，获取前15篇的详细信息"

Agent执行流程:
1. cnki_search(keyword="数字文物", filter_resource="DISSERTATION")
2. cnki_get_status() → 确认搜索成功，共146条结果
3. cnki_batch_get_details(max_count=15, max_pages=2)
   → 自动翻页并获取详情
4. 返回15篇论文的完整信息
```

### 示例2: 状态感知导航

```
用户: "继续查看下一页的结果"

Agent执行流程:
1. cnki_get_status() → 当前第1页，共78页
2. cnki_navigate_page(action="next")
3. cnki_get_status() → 确认已到第2页
4. 返回第2页的结果列表
```

## 九、总结

本升级计划基于**实际DOM结构分析**，确保所有选择器和操作方法都是可行的。

**核心改进**:
1. ✅ 状态感知 - 随时知道"我在哪"
2. ✅ 精确导航 - 可靠的翻页控制
3. ✅ 批量高效 - 跨页自动获取
4. ✅ 错误恢复 - 验证码和异常处理

**与纯API服务的区别**:
- 依赖真实浏览器页面
- 需要等待页面加载
- 必须验证页面状态
- 需要处理验证码

升级后，Agent 将具备完整的自主规划能力，可灵活组合各种操作完成复杂任务！

---

**文档版本**: v2.0  
**创建时间**: 2026-03-13  
**基于**: 实际DOM结构分析  
**状态**: 待实施

