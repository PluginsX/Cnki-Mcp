# 知网浏览器 MCP 服务升级计划

## 一、现状分析

### 1.1 当前架构特点
- **单例浏览器模式**：通过单例模式维护浏览器实例，保持会话状态
- **基础搜索功能**：支持主题、篇名、作者等搜索类型
- **结果筛选**：支持按资源类型（期刊、学位论文等）筛选
- **详情获取**：可获取单篇论文的摘要、关键词、引用格式等元数据

### 1.2 与纯 API 服务的本质区别
**优势：**
- 可视化操作：可看到真实页面，便于调试和验证
- 绕过 API 限制：不依赖官方 API，避免调用次数限制
- 灵活性强：可模拟真实用户行为，适应网站变化

**劣势：**
- 状态管理薄弱：无法准确知道当前页面状态（搜索结果页、详情页、首页等）
- 导航能力有限：不支持分页、排序、前进后退等操作
- 缺乏上下文记忆：每次调用都从头开始，无法基于上一步结果继续操作
- 盲目执行：无法判断当前操作是否成功，页面是否加载完成

### 1.3 核心问题
**当前服务缺乏对浏览器页面内容和状态的精确控制能力，导致：**
1. 无法判断当前页面类型（首页/搜索结果页/详情页）
2. 无法获取搜索结果总数、当前页码、总页数等信息
3. 无法进行分页导航（下一页、上一页、跳转指定页）
4. 无法按被引频次、下载量、时间等排序
5. 无法保留搜索历史，每次调用都是独立操作
6. 无法批量获取多篇论文详情
7. 无法判断页面加载状态，容易误判

---

## 二、升级目标

### 2.1 核心目标
**赋予智能体对浏览器页面的完全控制能力，实现：**
- **状态感知**：随时知道当前页面类型、内容、状态
- **精确导航**：可在不同页面间灵活跳转
- **上下文记忆**：保留操作历史，支持基于上一步结果继续操作
- **批量操作**：支持批量获取、批量导出等高效操作

### 2.2 具体能力指标
1. ✅ 可获取当前页面状态报告（页面类型、搜索结果数、筛选条件等）
2. ✅ 可实现分页导航（下一页、上一页、跳转指定页）
3. ✅ 可实现结果排序（按被引、下载、时间、相关性）
4. ✅ 可保留搜索历史，支持回溯和切换
5. ✅ 可批量获取 N 篇论文详情
6. ✅ 可导出搜索结果为多种格式（Excel、CSV、EndNote 等）
7. ✅ 可检测页面加载状态，避免误判

---

## 三、技术架构设计

### 3.1 分层架构

#### **高层流程方法**（一键式完整流程）
```python
# 示例：一键检索并获取前 N 篇详情
async def search_and_get_details(
    keyword: str,
    search_type: str = "SU",
    top_n: int = 10,
    filter_resource: str = "",
    sort_by: str = "relevance"
) -> list[CNKIPaper]:
    """一站式检索：搜索 -> 筛选 -> 排序 -> 获取前 N 篇详情"""
```

#### **中层操作方法**（独立操作步骤）
```python
# 示例：独立的搜索、筛选、排序、分页等方法
async def navigate_to_page(page_num: int) -> bool:
    """跳转到指定页码"""
    
async def sort_results(sort_type: str) -> bool:
    """按指定方式排序：relevance(相关性), cited(被引), downloaded(下载), date(时间)"""
    
async def get_current_page_status() -> dict:
    """获取当前页面状态报告"""
```

#### **底层原子方法**（细粒度状态查询和控制）
```python
# 示例：页面元素检测、状态查询
def _get_current_page_type() -> str:
    """判断当前页面类型：home, search_result, paper_detail"""
    
def _get_result_count() -> int:
    """获取当前搜索结果总数"""
    
def _get_current_page_number() -> int:
    """获取当前页码"""
    
def _wait_for_element(selector: str, timeout: int = 5000) -> bool:
    """等待指定元素出现"""
```

### 3.2 状态管理系统

#### **页面状态枚举**
```python
class PageState(str, Enum):
    HOME = "home"              # 知网首页
    SEARCH_RESULT = "search"   # 搜索结果页
    PAPER_DETAIL = "detail"    # 论文详情页
    UNKNOWN = "unknown"        # 未知页面
```

#### **搜索会话状态**
```python
class SearchSession(BaseModel):
    session_id: str
    keyword: str
    search_type: SearchType
    db_code: str
    filter_resource: str = ""
    sort_by: str = "relevance"
    current_page: int = 1
    total_pages: int = 1
    total_results: int = 0
    current_results: list[CNKIPaper] = []
    created_at: datetime
    last_accessed: datetime
    history: list[str] = []  # 操作历史
```

#### **状态管理器**
```python
class StateManager:
    def __init__(self):
        self.current_session: Optional[SearchSession] = None
        self.session_history: list[SearchSession] = []
        self.page_cache: dict[str, str] = {}  # URL -> HTML 缓存
    
    def save_session(self, session: SearchSession):
        """保存当前会话"""
    
    def restore_session(self, session_id: str) -> bool:
        """恢复指定会话"""
    
    def get_current_status(self) -> dict:
        """获取当前状态报告"""
```

---

## 四、具体实现任务

### 4.1 第一阶段：状态感知能力（优先级：高）

#### 任务 1.1：实现页面状态检测方法
**文件**: `browser.py`

```python
def get_page_status(self) -> dict:
    """获取当前页面状态
    
    返回:
        {
            "page_type": "search_result",  # 页面类型
            "url": "https://...",          # 当前 URL
            "title": "搜索结果 - 知网",     # 页面标题
            "result_count": 1234,          # 搜索结果总数（仅搜索结果页）
            "current_page": 1,             # 当前页码（仅搜索结果页）
            "total_pages": 50,             # 总页数（仅搜索结果页）
            "current_results": 20,         # 当前页结果数
            "filter_active": "DISSERTATION",  # 当前筛选条件
            "sort_by": "relevance",        # 当前排序方式
            "is_loading": False,           # 是否正在加载
            "has_error": False,            # 是否有错误
            "error_message": ""            # 错误信息
        }
    """
```

**实现要点**：
- 通过 URL 判断页面类型
- 提取搜索结果总数（解析"找到 X 条结果"）
- 提取当前页码和总页数（解析分页控件）
- 检测当前激活的筛选条件
- 检测当前排序方式

#### 任务 1.2：实现状态报告 MCP 工具
**文件**: `server.py`

```python
@server.call_tool()
async def cnki_get_status() -> list[TextContent]:
    """获取当前浏览器页面状态"""
    browser = get_browser()
    status = browser.get_page_status()
    return [TextContent(type="text", text=json.dumps(status, ensure_ascii=False, indent=2))]
```

**工具定义**：
```python
Tool(
    name="cnki_get_status",
    description="获取当前浏览器页面状态报告，包括页面类型、搜索结果数、当前页码、筛选条件等信息",
    inputSchema={"type": "object", "properties": {}}
)
```

---

### 4.2 第二阶段：导航控制能力（优先级：高）

#### 任务 2.1：实现分页导航方法
**文件**: `browser.py`

```python
def navigate_to_page(self, page_num: int) -> bool:
    """跳转到指定页码
    
    Args:
        page_num: 目标页码
        
    Returns:
        bool: 是否成功跳转
    """
    # 检测当前是否在搜索结果页
    if self._get_current_page_type() != PageState.SEARCH_RESULT:
        safe_print("错误：当前不在搜索结果页")
        return False
    
    # 获取总页数
    total_pages = self._get_total_pages()
    if page_num < 1 or page_num > total_pages:
        safe_print(f"错误：页码超出范围 (1-{total_pages})")
        return False
    
    # 点击分页控件
    try:
        # 查找分页控件
        page_control = self._page.locator(".page-control").first
        # 查找目标页码按钮
        target_btn = page_control.locator(f"a[rel='{page_num}']").first
        if target_btn and target_btn.is_visible(timeout=2000):
            target_btn.click()
            self._random_delay(3, 5)  # 等待新页面加载
            return True
        
        # 如果页码按钮不存在，尝试使用"下一页"按钮
        if page_num > self._get_current_page_number():
            next_btn = page_control.locator("a[rel='next']").first
            if next_btn and next_btn.is_visible(timeout=2000):
                for _ in range(page_num - self._get_current_page_number()):
                    next_btn.click()
                    self._random_delay(3, 5)
                return True
        
        return False
    except Exception as e:
        safe_print(f"分页失败：{str(e)}")
        return False
```

#### 任务 2.2：实现下一页/上一页方法
```python
def next_page(self) -> bool:
    """跳转到下一页"""
    current = self._get_current_page_number()
    return self.navigate_to_page(current + 1)

def prev_page(self) -> bool:
    """跳转到上一页"""
    current = self._get_current_page_number()
    if current > 1:
        return self.navigate_to_page(current - 1)
    return False
```

#### 任务 2.3：添加 MCP 工具
**文件**: `server.py`

```python
Tool(
    name="cnki_navigate_page",
    description="在搜索结果中跳转到指定页码",
    inputSchema={
        "type": "object",
        "properties": {
            "page_num": {"type": "integer", "description": "目标页码", "minimum": 1},
            "action": {"type": "string", "description": "快捷操作：next(下一页), prev(上一页)", "enum": ["next", "prev"]}
        }
    }
)
```

---

### 4.3 第三阶段：排序控制能力（优先级：中）

#### 任务 3.1：实现排序方法
**文件**: `browser.py`

```python
def sort_results(self, sort_type: str) -> bool:
    """按指定方式排序搜索结果
    
    Args:
        sort_type: 排序方式
            - relevance: 相关度（默认）
            - cited: 被引频次
            - downloaded: 下载量
            - date: 发表时间
            
    Returns:
        bool: 是否成功排序
    """
    sort_names = {
        "relevance": "相关度",
        "cited": "被引",
        "downloaded": "下载",
        "date": "时间",
    }
    
    safe_print(f"正在按 {sort_names.get(sort_type, sort_type)} 排序...")
    
    try:
        # 查找排序控件
        sort_control = self._page.locator(".sort-order").first
        if not sort_control or not sort_control.is_visible(timeout=2000):
            safe_print("警告：未找到排序控件")
            return False
        
        # 点击排序按钮
        sort_control.click()
        self._random_delay(1, 2)
        
        # 选择排序方式
        sort_option = self._page.locator(f"li[data-order='{sort_type}']").first
        if sort_option and sort_option.is_visible(timeout=2000):
            sort_option.click()
            self._random_delay(3, 5)  # 等待新结果加载
            safe_print(f"已按 {sort_names.get(sort_type)} 排序")
            return True
        
        safe_print(f"警告：未找到 {sort_names.get(sort_type)} 排序选项")
        return False
        
    except Exception as e:
        safe_print(f"排序失败：{str(e)}")
        return False
```

#### 任务 3.2：添加 MCP 工具
**文件**: `server.py`

```python
Tool(
    name="cnki_sort_results",
    description="按指定方式排序搜索结果",
    inputSchema={
        "type": "object",
        "properties": {
            "sort_type": {
                "type": "string",
                "description": "排序方式：relevance(相关度), cited(被引频次), downloaded(下载量), date(发表时间)",
                "enum": ["relevance", "cited", "downloaded", "date"]
            }
        },
        "required": ["sort_type"]
    }
)
```

---

### 4.4 第四阶段：搜索历史与缓存（优先级：中）

#### 任务 4.1：实现搜索会话管理
**文件**: `browser.py`

```python
from datetime import datetime
import uuid

class SearchSession(BaseModel):
    session_id: str
    keyword: str
    search_type: SearchType
    db_code: str
    filter_resource: str = ""
    sort_by: str = "relevance"
    current_page: int = 1
    total_pages: int = 1
    total_results: int = 0
    current_results: list[CNKIPaper] = []
    created_at: datetime
    last_accessed: datetime
    history: list[str] = []  # 操作历史，如 ["search", "filter:DISSERTATION", "sort:cited", "page:2"]

class StateManager:
    def __init__(self):
        self.current_session: Optional[SearchSession] = None
        self.session_history: list[SearchSession] = []
        self.page_cache: dict[str, str] = {}  # URL -> HTML 缓存
    
    def create_session(self, **kwargs) -> SearchSession:
        """创建新会话"""
        session = SearchSession(
            session_id=str(uuid.uuid4()),
            created_at=datetime.now(),
            last_accessed=datetime.now(),
            **kwargs
        )
        self.session_history.append(session)
        return session
    
    def update_session(self, **kwargs):
        """更新当前会话"""
        if self.current_session:
            for key, value in kwargs.items():
                if hasattr(self.current_session, key):
                    setattr(self.current_session, key, value)
            self.current_session.last_accessed = datetime.now()
    
    def save_session(self):
        """保存当前会话到历史"""
        if self.current_session:
            self.current_session.history.append(self._get_operation_description())
    
    def list_sessions(self) -> list[dict]:
        """列出所有会话"""
        return [
            {
                "session_id": s.session_id,
                "keyword": s.keyword,
                "search_type": s.search_type.value,
                "created_at": s.created_at.isoformat(),
                "last_accessed": s.last_accessed.isoformat(),
            }
            for s in self.session_history
        ]
    
    def restore_session(self, session_id: str) -> bool:
        """恢复指定会话"""
        for session in self.session_history:
            if session.session_id == session_id:
                self.current_session = session
                return True
        return False
```

#### 任务 4.2：添加 MCP 工具
**文件**: `server.py`

```python
Tool(
    name="cnki_list_sessions",
    description="列出所有搜索会话历史",
    inputSchema={"type": "object", "properties": {}}
)

Tool(
    name="cnki_restore_session",
    description="恢复指定搜索会话",
    inputSchema={
        "type": "object",
        "properties": {
            "session_id": {"type": "string", "description": "会话 ID（从 cnki_list_sessions 获取）"}
        },
        "required": ["session_id"]
    }
)
```

---

### 4.5 第五阶段：批量操作能力（优先级：低）

#### 任务 5.1：实现批量获取详情
**文件**: `browser.py`

```python
def batch_get_details(
    self,
    paper_indices: list[int] = None,
    max_count: int = 10
) -> list[CNKIPaper]:
    """批量获取论文详情
    
    Args:
        paper_indices: 要获取的论文索引列表（从当前搜索结果中选择，0-based）
        max_count: 最大获取数量（当 paper_indices 为 None 时使用）
        
    Returns:
        list[CNKIPaper]: 论文详情列表
    """
    # 检测当前是否在搜索结果页
    if self._get_current_page_type() != PageState.SEARCH_RESULT:
        safe_print("错误：当前不在搜索结果页")
        return []
    
    # 获取当前结果
    current_results = self._parse_results(self._page, page_size=50)
    
    # 确定要获取的论文
    if paper_indices:
        papers_to_get = [current_results[i] for i in paper_indices if i < len(current_results)]
    else:
        papers_to_get = current_results[:max_count]
    
    safe_print(f"准备批量获取 {len(papers_to_get)} 篇论文详情...")
    
    # 批量获取详情
    results = []
    for i, paper in enumerate(papers_to_get, 1):
        safe_print(f"[{i}/{len(papers_to_get)}] 正在获取：{paper.title}")
        detail = self.get_paper_detail(paper.link)
        if detail:
            results.append(detail)
        self._random_delay(2, 3)  # 避免请求过快
    
    safe_print(f"批量获取完成，成功 {len(results)}/{len(papers_to_get)} 篇")
    return results
```

#### 任务 5.2：添加 MCP 工具
**文件**: `server.py`

```python
Tool(
    name="cnki_batch_get_details",
    description="批量获取多篇论文的详细信息",
    inputSchema={
        "type": "object",
        "properties": {
            "paper_indices": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "要获取的论文索引列表（0-based，从当前搜索结果中选择）"
            },
            "max_count": {
                "type": "integer",
                "description": "最大获取数量（当未指定 paper_indices 时使用）",
                "default": 10
            }
        }
    }
)
```

---

### 4.6 第六阶段：结果导出功能（优先级：低）

#### 任务 6.1：实现导出方法
**文件**: `browser.py`

```python
def export_results(
    self,
    output_file: str,
    format: str = "csv",
    paper_indices: list[int] = None
) -> bool:
    """导出搜索结果
    
    Args:
        output_file: 输出文件路径
        format: 导出格式：csv, excel, endnote, refworks
        paper_indices: 要导出的论文索引（None 表示导出当前页全部）
        
    Returns:
        bool: 是否成功导出
    """
    import csv
    import json
    
    # 获取要导出的结果
    current_results = self._parse_results(self._page, page_size=50)
    if paper_indices:
        results_to_export = [current_results[i] for i in paper_indices if i < len(current_results)]
    else:
        results_to_export = current_results
    
    safe_print(f"准备导出 {len(results_to_export)} 条结果到 {output_file}...")
    
    try:
        if format == "csv":
            with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'title', 'author', 'source', 'publish_time',
                    'abstract', 'keywords', 'doi', 'link'
                ])
                writer.writeheader()
                for paper in results_to_export:
                    writer.writerow(paper.model_dump())
        
        elif format == "excel":
            import pandas as pd
            df = pd.DataFrame([p.model_dump() for p in results_to_export])
            df.to_excel(output_file, index=False, engine='openpyxl')
        
        elif format == "endnote":
            # EndNote 导入格式
            with open(output_file, 'w', encoding='utf-8') as f:
                for paper in results_to_export:
                    f.write("%0 Journal Article\n")
                    f.write(f"%T {paper.title}\n")
                    f.write(f"%A {paper.author}\n")
                    f.write(f"%J {paper.source}\n")
                    f.write(f"%D {paper.publish_time}\n")
                    f.write(f"%X {paper.abstract}\n")
                    f.write(f"%K {paper.keywords}\n")
                    f.write(f"%R {paper.doi}\n")
                    f.write(f"%U {paper.link}\n")
                    f.write("\n")
        
        safe_print(f"导出成功：{output_file}")
        return True
        
    except Exception as e:
        safe_print(f"导出失败：{str(e)}")
        return False
```

#### 任务 6.2：添加 MCP 工具
**文件**: `server.py`

```python
Tool(
    name="cnki_export_results",
    description="导出搜索结果到文件",
    inputSchema={
        "type": "object",
        "properties": {
            "output_file": {"type": "string", "description": "输出文件路径"},
            "format": {
                "type": "string",
                "description": "导出格式：csv, excel, endnote, refworks",
                "enum": ["csv", "excel", "endnote", "refworks"],
                "default": "csv"
            },
            "paper_indices": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "要导出的论文索引（0-based，None 表示全部）"
            }
        },
        "required": ["output_file"]
    }
)
```

---

## 五、实施计划

### 5.1 第一阶段（1-2 天）：状态感知
- [ ] 实现 `get_page_status()` 方法
- [ ] 实现 `_get_current_page_type()` 等辅助方法
- [ ] 添加 `cnki_get_status` MCP 工具
- [ ] 测试：验证状态报告准确性

### 5.2 第二阶段（1-2 天）：导航控制
- [ ] 实现 `navigate_to_page()` 方法
- [ ] 实现 `next_page()` 和 `prev_page()` 方法
- [ ] 添加 `cnki_navigate_page` MCP 工具
- [ ] 测试：验证分页导航功能

### 5.3 第三阶段（1 天）：排序控制
- [ ] 实现 `sort_results()` 方法
- [ ] 添加 `cnki_sort_results` MCP 工具
- [ ] 测试：验证排序功能

### 5.4 第四阶段（2-3 天）：状态管理
- [ ] 实现 `StateManager` 类
- [ ] 集成到 `CNKIBrowser` 类
- [ ] 添加 `cnki_list_sessions` 和 `cnki_restore_session` 工具
- [ ] 测试：验证会话管理功能

### 5.5 第五阶段（2 天）：批量操作
- [ ] 实现 `batch_get_details()` 方法
- [ ] 添加 `cnki_batch_get_details` MCP 工具
- [ ] 测试：验证批量获取功能

### 5.6 第六阶段（2 天）：结果导出
- [ ] 实现 `export_results()` 方法
- [ ] 添加 `cnki_export_results` MCP 工具
- [ ] 测试：验证导出功能

### 5.7 第七阶段（1 天）：集成测试与文档
- [ ] 编写集成测试
- [ ] 更新文档
- [ ] 性能优化

---

## 六、预期效果

### 6.1 智能体自主规划能力提升
**升级前**：
```
用户：搜索作者"王淑慧"的学位论文，按被引排序，获取前 5 篇详情
智能体：（无法完成，需要分多次独立调用）
```

**升级后**：
```
用户：搜索作者"王淑慧"的学位论文，按被引排序，获取前 5 篇详情
智能体：
1. 调用 cnki_search(keyword="王淑慧", search_type="AU", filter_resource="DISSERTATION")
2. 调用 cnki_get_status() 确认搜索结果
3. 调用 cnki_sort_results(sort_type="cited")
4. 调用 cnki_batch_get_details(paper_indices=[0,1,2,3,4], max_count=5)
5. 返回完整结果
```

### 6.2 灵活的操作组合
**示例场景**：
1. **跨页检索**：搜索 -> 翻页 -> 获取指定页的详情
2. **多条件筛选**：搜索 -> 筛选资源类型 -> 排序 -> 导出结果
3. **回溯对比**：搜索 A -> 保存会话 -> 搜索 B -> 恢复会话 A -> 对比结果
4. **批量处理**：搜索 -> 批量获取 50 篇详情 -> 导出为 Excel

### 6.3 错误恢复能力
**升级前**：操作失败后无法恢复，需要从头开始
**升级后**：
- 可检测当前状态，判断操作是否成功
- 可通过会话历史恢复到任意操作点
- 可基于当前状态决定下一步操作

---

## 七、技术要点

### 7.1 页面元素定位策略
**搜索结果页关键元素**：
```python
# 结果总数
".total-results"  # 文本："找到 1,234 条结果"

# 分页控件
".page-control"
"li.page-item"  # 页码按钮
"a[rel='next']"  # 下一页
"a[rel='prev']"  # 上一页

# 排序控件
".sort-order"
"li[data-order='cited']"  # 按被引排序

# 筛选选项
"a[resource='DISSERTATION']"  # 学位论文
"a[resource='JOURNAL']"  # 期刊
```

### 7.2 状态检测技巧
```python
def _get_current_page_type(self) -> str:
    """通过 URL 和页面内容判断页面类型"""
    current_url = self._page.url
    
    if "kns.cnki.net/kns8s/search" in current_url:
        return PageState.SEARCH_RESULT
    elif "kns.cnki.net/kcms/detail" in current_url:
        return PageState.PAPER_DETAIL
    elif "kns.cnki.net/" in current_url:
        return PageState.HOME
    else:
        return PageState.UNKNOWN
```

### 7.3 等待策略
```python
def _wait_for_results_loaded(self, timeout: int = 10000) -> bool:
    """等待搜索结果加载完成"""
    start_time = time.time()
    
    while time.time() - start_time < timeout / 1000:
        # 检测结果链接
        result_links = self._page.locator("a[href*='kcms']").count()
        if result_links > 0:
            # 检测分页控件
            page_control = self._page.locator(".page-control").count()
            if page_control > 0:
                return True
        
        time.sleep(0.5)
    
    return False
```

---

## 八、风险评估与应对

### 8.1 网站结构变化风险
**风险**：知网网页结构变化导致选择器失效
**应对**：
- 使用多重选择器策略
- 添加备用解析方法
- 定期更新和维护选择器

### 8.2 反爬虫机制风险
**风险**：频繁操作触发反爬虫机制
**应对**：
- 添加随机延迟
- 限制单次会话操作频率
- 模拟真实用户行为

### 8.3 浏览器资源占用风险
**风险**：长时间运行占用大量内存
**应对**：
- 实现浏览器自动清理机制
- 添加会话超时自动关闭
- 提供手动清理接口

---

## 九、总结

本升级计划的核心思想是：**将浏览器从单纯的工具执行器升级为可感知、可控制、可记忆的智能代理**。

通过实现状态感知、导航控制、排序控制、会话管理、批量操作和结果导出六大模块，赋予智能体以下关键能力：

1. **状态感知**：随时知道"我在哪"、"有什么"、"什么状态"
2. **精确控制**：可以"去那里"、"这样做"、"获取那些"
3. **上下文记忆**：记得"做过什么"、"结果如何"、"可以恢复"
4. **批量高效**：能够"一次获取"、"批量处理"、"导出结果"

这将使知网检索 MCP 服务从简单的 API 封装升级为真正的智能检索代理，为智能体提供灵活强大的自主规划能力。

---

**文档版本**: v1.0  
**创建时间**: 2026-03-13  
**作者**: AI Assistant  
**状态**: 待实施
