# 知网搜索结果统计优化

## 问题描述

### 原有问题
之前的实现存在严重的统计缺陷：
1. **只统计当前页显示的结果数量**，而不是真实的总数
2. **无法获取分类统计信息**（学术期刊、学位论文等各有多少条）
3. 用户无法了解搜索结果的完整分布情况

### 知网页面提供的数据
知网搜索结果页面本身就直接提供了完整的统计数据：

#### 1. 总结果数
```html
<span class="pagerTitleCell">
    <span>共找到</span>
    <em>671</em>
    <span>条结果</span>
</span>
```

#### 2. 总库统计
```html
<a data-id="all" class="all" name="classify" resource="CROSSDB">
    <span>总库</span>
    <em>671</em>
</a>
```

#### 3. 各分类统计
```html
<li>
    <a name="classify" resource="JOURNAL">
        <span>学术期刊</span>
        <em>500</em>
    </a>
</li>
<li>
    <a name="classify" resource="DISSERTATION">
        <span>学位论文</span>
        <em>120</em>
    </a>
</li>
<!-- 更多分类... -->
```

## 优化方案

### 1. 直接提取真实总数
从页面的 `pagerTitleCell` 元素中提取真实的结果总数，而不是统计当前页的结果数量。

### 2. 提取分类统计
解析页面上的分类链接，获取每个分类的结果数量：
- 总库
- 学术期刊
- 学位论文
- 会议论文
- 报纸
- 图书
- 专利
- 标准
- 成果
- 等等...

### 3. 数据模型更新
在 `CNKIQueryResult` 中添加 `category_counts` 字段：
```python
class CNKIQueryResult(BaseModel):
    total: int  # 真实总数（从知网页面获取）
    page_num: int
    page_size: int
    category_counts: dict[str, int]  # 各分类统计
    results: list[CNKIPaper]  # 当前页的结果列表
```

## 实现细节

### 1. `_extract_result_count()` 方法优化
```python
def _extract_result_count(self) -> int:
    """提取搜索结果总数（从知网页面直接获取）"""
    # 方法1: 从 <em> 标签提取
    elem = self._page.locator("span.pagerTitleCell em").first
    if elem and elem.is_visible(timeout=2000):
        text = elem.inner_text().strip()
        return int(text.replace(',', ''))
    
    # 方法2: 从完整文本提取
    elem = self._page.locator("span.pagerTitleCell").first
    if elem and elem.is_visible(timeout=2000):
        text = elem.inner_text()
        match = re.search(r'(\d+(?:,\d+)*)', text)
        if match:
            return int(match.group(1).replace(',', ''))
    
    return 0
```

### 2. 新增 `_extract_category_counts()` 方法
```python
def _extract_category_counts(self) -> dict[str, int]:
    """提取各分类的结果数量"""
    category_counts = {}
    
    # 获取总库
    total_link = self._page.locator('a[resource="CROSSDB"]').first
    if total_link:
        span = total_link.locator("span").first
        em = total_link.locator("em").first
        if span and em:
            name = span.inner_text().strip()
            count = int(em.inner_text().strip().replace(',', ''))
            category_counts[name] = count
    
    # 获取各分类
    category_links = self._page.locator('a[resource][name="classify"]').all()
    for link in category_links:
        resource = link.get_attribute("resource")
        if resource == "CROSSDB":
            continue
        
        span = link.locator("span").first
        em = link.locator("em").first
        if span and em:
            name = span.inner_text().strip()
            count = int(em.inner_text().strip().replace(',', ''))
            category_counts[name] = count
    
    return category_counts
```

### 3. 搜索方法更新
```python
def search(self, request: CNKIQueryRequest) -> CNKIQueryResult:
    # ... 执行搜索 ...
    
    # 获取真实总数
    total_count = self._extract_result_count()
    
    # 获取分类统计
    category_counts = self._extract_category_counts()
    
    # 解析当前页结果
    results = self._parse_results(page, actual_page_size, request.search_type)
    
    return CNKIQueryResult(
        total=total_count,  # 真实总数
        page_num=request.page_num,
        page_size=actual_page_size,
        category_counts=category_counts,  # 分类统计
        results=results  # 当前页结果
    )
```

### 4. 页面状态方法更新
```python
def get_page_status(self) -> dict:
    """获取当前页面完整状态"""
    # ...
    
    if page_type == PageState.SEARCH_RESULT:
        status["result_count"] = self._extract_result_count()
        status["category_counts"] = self._extract_category_counts()
        # ...
    
    return status
```

## 优化效果

### 优化前
```json
{
  "total": 20,  // ❌ 只是当前页的数量
  "page_num": 1,
  "page_size": 20,
  "results": [...]  // 20条结果
}
```

### 优化后
```json
{
  "total": 671,  // ✅ 真实总数
  "page_num": 1,
  "page_size": 20,
  "category_counts": {  // ✅ 完整的分类统计
    "总库": 671,
    "学术期刊": 500,
    "学位论文": 120,
    "会议": 30,
    "报纸": 15,
    "图书": 6
  },
  "results": [...]  // 当前页的20条结果
}
```

## 数据验证

### 验证规则
1. **总数 > 0**：搜索结果总数应该大于0
2. **当前页结果数 ≤ 每页显示数**：当前页实际获取的结果不应超过设置的每页显示数
3. **总库数 = 总数**：分类统计中的"总库"数量应该等于总结果数
4. **分类数量合理**：各分类的数量之和应该等于总库数（可能有重叠）

### 测试脚本
创建了 `tests/test_statistics.py` 用于验证：
- 统计数据的正确性
- 分类统计的完整性
- 数据的合理性验证

## 使用示例

### Python 脚本调用
```python
from cnki_mcp.browser import CNKIBrowser
from cnki_mcp.models import CNKIQueryRequest, SearchType

browser = CNKIBrowser.get_instance()
browser.initialize()

# 执行搜索
result = browser.search(CNKIQueryRequest(
    keyword="人工智能",
    search_type=SearchType.SU,
    page_size=20
))

# 查看统计
print(f"总结果数: {result.total}")
print(f"当前页: {result.page_num}")
print(f"每页显示: {result.page_size}")
print(f"当前页实际获取: {len(result.results)}")

# 查看分类统计
for category, count in result.category_counts.items():
    print(f"{category}: {count}")
```

### MCP 工具调用
```json
{
  "name": "cnki_search",
  "arguments": {
    "keyword": "人工智能",
    "search_type": "SU",
    "page_size": 20
  }
}
```

返回结果包含完整的统计信息。

## 总结

这次优化解决了统计数据不准确的核心问题：
1. ✅ 直接从知网页面获取真实的结果总数
2. ✅ 提供完整的分类统计信息
3. ✅ 区分"总数"和"当前页结果数"
4. ✅ 数据验证机制确保准确性

用户现在可以：
- 了解搜索结果的真实规模
- 查看各分类的分布情况
- 做出更明智的筛选决策

