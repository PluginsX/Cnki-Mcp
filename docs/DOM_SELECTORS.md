# 知网页面 DOM 选择器参考手册

> 基于实际页面分析的准确选择器清单

## 一、搜索结果页

### 1.1 结果统计信息

```python
# 结果总数
"span.pagerTitleCell"
# 示例文本: "找到1,557条结果"
# 提取方法: re.search(r'(\d+(?:,\d+)*)', text)

# 页码信息
"span.countPageMark"
# 示例文本: "1/78"
# 提取方法: re.search(r'(\d+)/(\d+)', text)
```

### 1.2 分页控件

```python
# 分页容器
"div.search-page"

# 上一页按钮
"div.search-page a.but-l"
# 文本: "<"

# 下一页按钮
"div.search-page a.but-r"
# 文本: ">"

# 当前页码
"div.search-page b"

# 总页数
"div.search-page em"
```

**注意**: 知网不支持直接跳转到指定页码，只能通过"上一页/下一页"按钮导航。

### 1.3 搜索类型切换

```python
# 容器（注意：这是搜索类型，不是排序！）
"div.sort.reopt"

# 当前选中的搜索类型
"div.sort-default span"
# 属性: title="主题"

# 搜索类型列表
"div.sort-list ul li"
# 属性: data-val="SU" (主题)
#       data-val="TI" (篇名)
#       data-val="AU" (作者)
#       data-val="KY" (关键词)
#       data-val="AB" (摘要)
#       data-val="FT" (全文)

# 选择特定类型
"div.sort-list ul li[data-val='AU'] a"
```

### 1.4 资源类型筛选

```python
# 筛选链接（通用）
"a[resource]"

# 具体资源类型
"a[resource='CROSSDB']"      # 总库
"a[resource='JOURNAL']"       # 学术期刊
"a[resource='DISSERTATION']"  # 学位论文
"a[resource='CONFERENCE']"    # 会议
"a[resource='NEWSPAPER']"     # 报纸
"a[resource='BOOK']"          # 图书
"a[resource='PATENT']"        # 专利
"a[resource='STANDARD']"      # 标准
"a[resource='ACHIEVEMENTS']"  # 成果
```

### 1.5 结果列表

```python
# 结果表格
"table.result-table-list"

# 表格行（每行一篇文章）
"table.result-table-list tbody tr"

# 单行内的元素
"td.seq"        # 序号
"td.name"       # 标题
"td.author"     # 作者
"td.source"     # 来源
"td.date"       # 日期
"td.data"       # 数据类型
"td.quote"      # 被引
"td.download"   # 下载
"td.operat"     # 操作

# 标题链接
"td.name a.fz14"
# 属性: href="https://kns.cnki.net/kcms2/article/abstract?v=..."

# 作者信息
"td.author div.authorinfo p"
```

## 二、论文详情页

### 2.1 基本信息

```python
# 标题
"h1"
".doc-title h1"

# 作者
".author"
".doc-author"

# 作者单位
".orgn"
".affiliation"

# 来源期刊
".sourcename"
".source"
```

### 2.2 摘要和关键词

```python
# 摘要
"#ChDivSummary"
".abstract-text"

# 关键词
"p.keywords"
".keywords"
```

### 2.3 引用格式

```python
# 引用按钮
"a[onclick*='getQuotes']"
"a:has-text('引用')"

# 引用弹窗
".quote-pop"

# 引用格式表格
".quote-pop table tbody tr"

# GB/T 7714-2015 格式
"td.quote-l:has-text('GB/T 7714-2015') + td.quote-r textarea.text"

# 知网研学格式
"td.quote-l:has-text('知网研学') + td.quote-r textarea.text"

# EndNote 格式
"td.quote-l:has-text('EndNote') + td.quote-r textarea.text"
```

### 2.4 其他元数据

```python
# DOI
"div.row li.top-space:has-text('DOI：')"

# 专辑
"div.row li.top-space:has-text('专辑：')"

# 专题
"div.row li.top-space:has-text('专题：')"

# 分类号
"div.row li.top-space:has-text('分类号：')"

# 在线发表时间
"div.row li.top-space:has-text('在线公开时间：')"

# 基金资助
"p.funds"
```

## 三、验证码检测

```python
# 验证码容器（多种可能）
".verify-wrap"
".slider-verify"
".geetest"
"#nc_1_wrapper"
".captcha"
".verify-box"
"iframe[src*='captcha']"
"iframe[src*='verify']"
".nc-container"
"#nc_1"
".slide-verify"
".slider"
```

## 四、页面类型判断

```python
def get_page_type(url: str) -> str:
    """通过URL判断页面类型"""
    if "kns8s/defaultresult" in url or "kns8s/search" in url:
        return "search_result"
    elif "kcms/detail" in url or "kcms2/article" in url:
        return "paper_detail"
    elif "kns.cnki.net" in url and url.count('/') <= 3:
        return "home"
    else:
        return "unknown"
```

## 五、等待策略

### 5.1 搜索结果页加载完成

```python
def wait_for_search_result_loaded(page, timeout=10000):
    """等待搜索结果页加载完成"""
    checks = [
        lambda: page.locator("span.pagerTitleCell").count() > 0,
        lambda: page.locator("table.result-table-list").count() > 0,
        lambda: page.locator("tbody tr").count() > 0,
    ]
    
    start_time = time.time()
    while (time.time() - start_time) * 1000 < timeout:
        if all(check() for check in checks):
            return True
        time.sleep(0.5)
    return False
```

### 5.2 详情页加载完成

```python
def wait_for_detail_page_loaded(page, timeout=10000):
    """等待详情页加载完成"""
    checks = [
        lambda: page.locator("h1").count() > 0,
        lambda: page.locator("#ChDivSummary").count() > 0 or 
                page.locator(".abstract-text").count() > 0,
    ]
    
    start_time = time.time()
    while (time.time() - start_time) * 1000 < timeout:
        if any(check() for check in checks):
            return True
        time.sleep(0.5)
    return False
```

## 六、常见问题

### Q1: 为什么没有排序控件？

**A**: 知网搜索结果页不支持前端排序切换。`div.sort` 实际上是**搜索类型切换**（主题/篇名/作者等），不是排序功能。

### Q2: 如何跳转到指定页码？

**A**: 知网不支持直接跳转到指定页码，只能通过"上一页/下一页"按钮逐页导航。

### Q3: 如何判断是否到达最后一页？

**A**: 通过 `span.countPageMark` 提取当前页码和总页数，比较即可。

### Q4: 选择器失效怎么办？

**A**: 知网可能会更新页面结构。建议：
1. 使用多重选择器策略（提供备用选择器）
2. 定期验证选择器有效性
3. 添加详细的错误日志

## 七、更新日志

| 日期 | 版本 | 更新内容 |
|------|------|----------|
| 2026-03-13 | v1.0 | 基于实际页面分析创建 |

---

**维护建议**: 每月验证一次选择器有效性，知网更新时及时调整。

