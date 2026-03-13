# 知网检索 MCP 服务升级策略 v3.0

> **升级目标**：实现完整的分页控制、全面的分类筛选、精准的结果统计

## 📋 需求分析

### 1. 单页显示数量控制

**现状**：
- ❌ `page_size` 参数已定义但未实际生效
- ❌ 只是限制解析结果数量，不控制知网页面显示

**需求**：
- ✅ 支持切换知网页面的每页显示数量（10/20/50）
- ✅ 通过操作下拉列表实现真实的分页控制

**DOM 结构**：
```html
<div class="sort" id="perPageDiv">
    <div class="sort-default">
        <span>50</span>
        <i class="icon icon-sort"></i>
    </div>
    <ul class="sort-list" style="display: none;">
        <li data-val="10"><a href="javascript:void(0);">10</a></li>
        <li data-val="20"><a href="javascript:void(0);">20</a></li>
        <li data-val="50" class="cur"><a href="javascript:void(0);">50</a></li>
    </ul>
</div>
```

### 2. 全面的分类筛选

**现状**：
- ✅ 已支持基础资源类型筛选（学位论文、期刊等）
- ❌ 不支持父子组合筛选项
- ❌ 不支持多维度筛选（学科、年份、来源等）

**需求**：
- ✅ 支持所有知网原生筛选项
- ✅ 支持父子组合筛选（如：学科 → 子学科）
- ✅ 支持多维度同时筛选
- ✅ 获取每个筛选项的结果数量

**知网筛选维度**（基于实际页面）：
1. **资源类型**：学术期刊、学位论文、会议、报纸、年鉴、图书、专利、标准、成果、学术辑刊
2. **学科分类**：多级分类树（父类 → 子类）
3. **发表年份**：年份范围筛选
4. **来源期刊/机构**：具体出版来源
5. **作者单位**：机构筛选
6. **基金资助**：基金项目筛选
7. **文献类型**：研究论文、综述、案例等

### 3. 结果数量统计强化

**现状**：
- ✅ 可获取总结果数
- ❌ 首次搜索时统计信息不完整
- ❌ 无法获取分类别的结果数量

**需求**：
- ✅ 首次搜索立即获取完整统计信息
- ✅ 获取每个筛选项对应的结果数量
- ✅ 提供结果分布概览

## 🎯 升级策略

### 阶段一：单页显示数量控制（优先级：高）

#### 1.1 实现方案

```python
class CNKIBrowser:
    def set_page_size(self, page_size: int) -> bool:
        """设置每页显示数量
        
        Args:
            page_size: 每页显示数量（10/20/50）
            
        Returns:
            bool: 是否设置成功
        """
        if page_size not in [10, 20, 50]:
            safe_print(f"错误：page_size 必须是 10、20 或 50")
            return False
        
        if self._get_current_page_type() != PageState.SEARCH_RESULT:
            safe_print("错误：当前不在搜索结果页")
            return False
        
        try:
            # 1. 点击下拉菜单
            dropdown = self._page.locator("#perPageDiv .sort-default").first
            if not dropdown or not dropdown.is_visible(timeout=2000):
                safe_print("未找到每页显示数量下拉菜单")
                return False
            
            dropdown.click()
            self._random_delay(0.5, 1)
            
            # 2. 选择对应数量
            option = self._page.locator(f"#perPageDiv ul.sort-list li[data-val='{page_size}'] a").first
            if not option or not option.is_visible(timeout=2000):
                safe_print(f"未找到选项：{page_size}")
                return False
            
            option.click()
            safe_print(f"已设置每页显示 {page_size} 条")
            self._random_delay(3, 5)
            
            # 3. 等待页面重新加载
            if self._wait_for_page_loaded():
                safe_print(f"✓ 页面已刷新，当前每页显示 {page_size} 条")
                return True
            
            return False
            
        except Exception as e:
            safe_print(f"设置每页显示数量失败：{str(e)}")
            return False
    
    def get_current_page_size(self) -> int:
        """获取当前每页显示数量"""
        try:
            elem = self._page.locator("#perPageDiv .sort-default span").first
            if elem and elem.is_visible(timeout=2000):
                text = elem.inner_text().strip()
                return int(text)
        except Exception:
            pass
        return 10  # 默认值
```

#### 1.2 修改搜索逻辑

```python
def search(self, request: CNKIQueryRequest) -> CNKIQueryResult:
    # ... 现有搜索逻辑 ...
    
    # 在搜索完成后，设置每页显示数量
    if request.page_size != self.get_current_page_size():
        if self.set_page_size(request.page_size):
            # 重新解析结果
            results = self._parse_results(page, request.page_size, request.search_type)
    
    # ... 返回结果 ...
```

#### 1.3 新增 MCP 工具

```python
Tool(
    name="cnki_set_page_size",
    description="设置搜索结果每页显示数量（10/20/50条）。修改后页面会自动刷新。",
    inputSchema={
        "type": "object",
        "properties": {
            "page_size": {
                "type": "integer",
                "description": "每页显示数量",
                "enum": [10, 20, 50]
            }
        },
        "required": ["page_size"]
    }
)
```

### 阶段二：全面分类筛选系统（优先级：高）

#### 2.1 数据模型设计

```python
class FilterCategory(str, Enum):
    """筛选类别"""
    RESOURCE = "resource"           # 资源类型
    SUBJECT = "subject"             # 学科分类
    YEAR = "year"                   # 发表年份
    SOURCE = "source"               # 来源期刊/机构
    AUTHOR_ORG = "author_org"       # 作者单位
    FUND = "fund"                   # 基金资助
    DOC_TYPE = "doc_type"           # 文献类型

class FilterOption(BaseModel):
    """筛选选项"""
    category: FilterCategory        # 筛选类别
    code: str                       # 选项代码
    name: str                       # 选项名称
    count: int = 0                  # 结果数量
    parent_code: str = ""           # 父选项代码（用于多级筛选）
    children: list['FilterOption'] = []  # 子选项

class FilterState(BaseModel):
    """当前筛选状态"""
    active_filters: dict[FilterCategory, list[str]] = {}  # 已激活的筛选
    available_options: dict[FilterCategory, list[FilterOption]] = {}  # 可用选项

class CNKISearchResult(BaseModel):
    """增强的搜索结果"""
    total: int
    page_num: int
    page_size: int
    results: list[CNKIPaper]
    
    # 新增：筛选状态
    filter_state: FilterState
    
    # 新增：结果分布统计
    distribution: dict[str, int] = {}  # 如：{"学术期刊": 1200, "学位论文": 357}
```

#### 2.2 筛选项解析

```python
class CNKIBrowser:
    def get_available_filters(self) -> FilterState:
        """获取当前可用的所有筛选项及其结果数量
        
        Returns:
            FilterState: 筛选状态对象
        """
        if self._get_current_page_type() != PageState.SEARCH_RESULT:
            return FilterState()
        
        filter_state = FilterState()
        
        # 1. 解析资源类型筛选
        filter_state.available_options[FilterCategory.RESOURCE] = \
            self._parse_resource_filters()
        
        # 2. 解析学科分类筛选
        filter_state.available_options[FilterCategory.SUBJECT] = \
            self._parse_subject_filters()
        
        # 3. 解析年份筛选
        filter_state.available_options[FilterCategory.YEAR] = \
            self._parse_year_filters()
        
        # 4. 解析其他筛选项...
        
        return filter_state
    
    def _parse_resource_filters(self) -> list[FilterOption]:
        """解析资源类型筛选项"""
        options = []
        
        try:
            # 查找所有资源类型链接
            links = self._page.locator("a[resource]").all()
            
            for link in links:
                try:
                    code = link.get_attribute("resource") or ""
                    if not code:
                        continue
                    
                    # 提取名称和数量
                    text = link.inner_text(timeout=1000).strip()
                    
                    # 解析数量（如："学术期刊(1,234)"）
                    match = re.search(r'(.+?)\((\d+(?:,\d+)*)\)', text)
                    if match:
                        name = match.group(1).strip()
                        count = int(match.group(2).replace(',', ''))
                    else:
                        name = text
                        count = 0
                    
                    # 检查是否已激活
                    is_active = "active" in (link.get_attribute("class") or "")
                    
                    options.append(FilterOption(
                        category=FilterCategory.RESOURCE,
                        code=code,
                        name=name,
                        count=count
                    ))
                    
                except Exception:
                    continue
        
        except Exception as e:
            safe_print(f"解析资源类型筛选失败：{str(e)}")
        
        return options
    
    def _parse_subject_filters(self) -> list[FilterOption]:
        """解析学科分类筛选项（支持多级）"""
        options = []
        
        try:
            # 查找学科分类容器
            subject_container = self._page.locator(".subject-filter, .classify-filter").first
            if not subject_container:
                return options
            
            # 解析一级分类
            parent_items = subject_container.locator(".parent-item, .level-1").all()
            
            for parent_item in parent_items:
                try:
                    parent_link = parent_item.locator("a").first
                    parent_code = parent_link.get_attribute("data-code") or ""
                    parent_text = parent_link.inner_text(timeout=1000).strip()
                    
                    # 解析父类名称和数量
                    match = re.search(r'(.+?)\((\d+(?:,\d+)*)\)', parent_text)
                    if match:
                        parent_name = match.group(1).strip()
                        parent_count = int(match.group(2).replace(',', ''))
                    else:
                        parent_name = parent_text
                        parent_count = 0
                    
                    parent_option = FilterOption(
                        category=FilterCategory.SUBJECT,
                        code=parent_code,
                        name=parent_name,
                        count=parent_count,
                        children=[]
                    )
                    
                    # 解析子分类
                    child_items = parent_item.locator(".child-item, .level-2").all()
                    for child_item in child_items:
                        try:
                            child_link = child_item.locator("a").first
                            child_code = child_link.get_attribute("data-code") or ""
                            child_text = child_link.inner_text(timeout=1000).strip()
                            
                            match = re.search(r'(.+?)\((\d+(?:,\d+)*)\)', child_text)
                            if match:
                                child_name = match.group(1).strip()
                                child_count = int(match.group(2).replace(',', ''))
                            else:
                                child_name = child_text
                                child_count = 0
                            
                            parent_option.children.append(FilterOption(
                                category=FilterCategory.SUBJECT,
                                code=child_code,
                                name=child_name,
                                count=child_count,
                                parent_code=parent_code
                            ))
                        except Exception:
                            continue
                    
                    options.append(parent_option)
                    
                except Exception:
                    continue
        
        except Exception as e:
            safe_print(f"解析学科分类筛选失败：{str(e)}")
        
        return options
    
    def apply_filter(self, category: FilterCategory, code: str) -> bool:
        """应用筛选条件
        
        Args:
            category: 筛选类别
            code: 筛选选项代码
            
        Returns:
            bool: 是否成功应用
        """
        if self._get_current_page_type() != PageState.SEARCH_RESULT:
            safe_print("错误：当前不在搜索结果页")
            return False
        
        try:
            if category == FilterCategory.RESOURCE:
                # 资源类型筛选
                link = self._page.locator(f"a[resource='{code}']").first
            elif category == FilterCategory.SUBJECT:
                # 学科分类筛选
                link = self._page.locator(f"a[data-code='{code}']").first
            else:
                safe_print(f"暂不支持的筛选类别：{category}")
                return False
            
            if not link or not link.is_visible(timeout=2000):
                safe_print(f"未找到筛选选项：{code}")
                return False
            
            link.click()
            safe_print(f"已应用筛选：{category.value} = {code}")
            self._random_delay(3, 5)
            
            # 等待页面重新加载
            if self._wait_for_page_loaded():
                safe_print("✓ 筛选已生效")
                return True
            
            return False
            
        except Exception as e:
            safe_print(f"应用筛选失败：{str(e)}")
            return False
    
    def clear_filter(self, category: FilterCategory) -> bool:
        """清除指定类别的筛选
        
        Args:
            category: 筛选类别
            
        Returns:
            bool: 是否成功清除
        """
        # 通常点击"全部"或"清除"按钮
        try:
            if category == FilterCategory.RESOURCE:
                # 点击"总库"或"全部"
                link = self._page.locator("a[resource='CROSSDB']").first
            else:
                # 查找清除按钮
                link = self._page.locator(f".clear-filter[data-category='{category.value}']").first
            
            if link and link.is_visible(timeout=2000):
                link.click()
                self._random_delay(3, 5)
                return True
            
            return False
            
        except Exception as e:
            safe_print(f"清除筛选失败：{str(e)}")
            return False
```

#### 2.3 新增 MCP 工具

```python
Tool(
    name="cnki_get_filters",
    description="获取当前搜索结果的所有可用筛选项，包括每个选项的结果数量。支持多级筛选（如学科分类的父子关系）。",
    inputSchema={
        "type": "object",
        "properties": {}
    }
),

Tool(
    name="cnki_apply_filter",
    description="应用筛选条件。支持资源类型、学科分类、年份等多维度筛选。",
    inputSchema={
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": "筛选类别",
                "enum": ["resource", "subject", "year", "source", "author_org", "fund", "doc_type"]
            },
            "code": {
                "type": "string",
                "description": "筛选选项代码（从cnki_get_filters获取）"
            }
        },
        "required": ["category", "code"]
    }
),

Tool(
    name="cnki_clear_filter",
    description="清除指定类别的筛选条件，恢复到全部结果。",
    inputSchema={
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": "要清除的筛选类别",
                "enum": ["resource", "subject", "year", "source", "author_org", "fund", "doc_type"]
            }
        },
        "required": ["category"]
    }
)
```

### 阶段三：结果统计强化（优先级：中）

#### 3.1 增强搜索结果

```python
def search(self, request: CNKIQueryRequest) -> CNKIQueryResult:
    # ... 现有搜索逻辑 ...
    
    # 在搜索完成后，立即获取完整统计信息
    filter_state = self.get_available_filters()
    
    # 构建结果分布统计
    distribution = {}
    for category, options in filter_state.available_options.items():
        for option in options:
            if option.count > 0:
                distribution[option.name] = option.count
    
    return CNKIQueryResult(
        total=len(results),
        page_num=request.page_num,
        page_size=request.page_size,
        results=results,
        filter_state=filter_state,
        distribution=distribution
    )
```

#### 3.2 状态查询增强

```python
def get_page_status(self) -> dict:
    """获取当前页面完整状态（增强版）"""
    status = {
        # ... 现有状态信息 ...
    }
    
    if page_type == PageState.SEARCH_RESULT:
        # 添加筛选状态
        filter_state = self.get_available_filters()
        status["filters"] = filter_state.model_dump()
        
        # 添加当前页面大小
        status["current_page_size"] = self.get_current_page_size()
        
        # 添加结果分布
        status["distribution"] = {
            opt.name: opt.count 
            for opts in filter_state.available_options.values() 
            for opt in opts if opt.count > 0
        }
    
    return status
```

## 📊 实施计划

### 第一周：单页显示数量控制

- [ ] Day 1-2: 实现 `set_page_size()` 和 `get_current_page_size()`
- [ ] Day 3: 修改 `search()` 方法集成分页控制
- [ ] Day 4: 添加 `cnki_set_page_size` MCP 工具
- [ ] Day 5: 测试验证

### 第二周：基础筛选系统

- [ ] Day 1-2: 实现资源类型筛选解析和应用
- [ ] Day 3-4: 实现学科分类筛选（多级）
- [ ] Day 5: 添加相关 MCP 工具

### 第三周：高级筛选和统计

- [ ] Day 1-2: 实现年份、来源等其他筛选维度
- [ ] Day 3: 增强结果统计功能
- [ ] Day 4-5: 集成测试和优化

## 🎯 预期效果

### 使用场景示例

```python
# 场景1：精确控制分页
agent.call("cnki_search", {
    "keyword": "人工智能",
    "page_size": 50  # 每页显示50条
})

# 场景2：获取筛选选项
filters = agent.call("cnki_get_filters")
# 返回：
# {
#   "resource": [
#     {"code": "JOURNAL", "name": "学术期刊", "count": 1234},
#     {"code": "DISSERTATION", "name": "学位论文", "count": 567}
#   ],
#   "subject": [
#     {
#       "code": "TP", "name": "自动化技术", "count": 800,
#       "children": [
#         {"code": "TP18", "name": "人工智能理论", "count": 450}
#       ]
#     }
#   ]
# }

# 场景3：应用筛选
agent.call("cnki_apply_filter", {
    "category": "resource",
    "code": "JOURNAL"  # 只看期刊
})

# 场景4：多级筛选
agent.call("cnki_apply_filter", {
    "category": "subject",
    "code": "TP18"  # 筛选到具体子学科
})

# 场景5：查看完整统计
status = agent.call("cnki_get_status")
# 返回包含：
# - 总结果数
# - 当前页码/总页数
# - 当前页面大小
# - 各类别结果分布
# - 已激活的筛选条件
```

## ✨ 核心优势

1. **精确控制**：真实控制知网页面行为，不是模拟
2. **完整信息**：首次搜索即获得全面统计
3. **灵活筛选**：支持多维度、多级别组合筛选
4. **透明状态**：随时查询当前筛选和统计状态
5. **向后兼容**：不影响现有功能

## 🔧 技术要点

1. **DOM 选择器**：需要实际页面验证所有选择器
2. **等待策略**：筛选后需要等待页面重新加载
3. **状态同步**：保持内部状态与页面状态一致
4. **错误处理**：优雅处理选择器失效和网络问题
5. **性能优化**：缓存筛选选项，避免重复解析

---

**制定时间**：2026-03-13  
**预计完成**：3周  
**优先级**：高

