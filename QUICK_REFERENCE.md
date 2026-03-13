# 快速参考

## 测试脚本

### 快速验证（推荐先运行）
```bash
python tests/verify_setup.py
```
- 检查：模块、类、方法、枚举、对象、文件、环境
- 耗时：< 1 秒
- 无需浏览器

### 完整测试（需要浏览器）
```bash
python tests/test_complex_workflow.py
```
- 测试：初始化、搜索、翻页、详情、下载等
- 耗时：5-10 分钟
- 需要网络和浏览器

---

## 核心功能

| 功能 | 方法 | 说明 |
|------|------|------|
| 初始化 | `browser.initialize()` | 启动浏览器，打开知网 |
| 搜索 | `browser.search(request)` | 执行搜索查询 |
| 翻页 | `browser.next_page()` / `prev_page()` | 翻页导航 |
| 详情 | `browser.get_paper_detail(url)` | 获取文章详情 |
| 下载 | `browser.download_paper(url, fmt)` | 下载论文 |
| 批量 | `browser.batch_get_details_across_pages()` | 批量获取详情 |
| 状态 | `browser.get_page_status()` | 获取页面状态 |

---

## 数据模型

### 搜索请求
```python
from cnki_mcp.models import CNKIQueryRequest, SearchType

request = CNKIQueryRequest(
    keyword="机器学习",
    search_type=SearchType.SU,  # 主题搜索
    page_size=10,
    page_num=1
)
```

### 搜索结果
```python
result = browser.search(request)
print(f"总数：{result.total}")
print(f"当前页：{result.page_num}")
print(f"结果数：{len(result.results)}")
```

### 论文信息
```python
paper = result.results[0]
print(f"标题：{paper.title}")
print(f"作者：{paper.author}")
print(f"来源：{paper.source}")
print(f"可下载：{paper.can_download}")
```

---

## 常见操作

### 1. 初始化浏览器
```python
from cnki_mcp.browser import CNKIBrowser

browser = CNKIBrowser.get_instance()
if browser.initialize():
    print("初始化成功")
```

### 2. 执行搜索
```python
from cnki_mcp.models import CNKIQueryRequest, SearchType

request = CNKIQueryRequest(
    keyword="深度学习",
    search_type=SearchType.SU
)
result = browser.search(request)
print(f"找到 {result.total} 条结果")
```

### 3. 翻页
```python
# 下一页
if browser.next_page():
    print("已翻到下一页")

# 上一页
if browser.prev_page():
    print("已翻回上一页")
```

### 4. 获取详情
```python
paper = result.results[0]
detail = browser.get_paper_detail(paper.link)
print(f"摘要：{detail.abstract[:100]}...")
print(f"关键词：{detail.keywords}")
```

### 5. 下载论文
```python
result = browser.download_paper(
    paper_url=paper.link,
    fmt="pdf",
    save_dir="./downloads"
)
if result.success:
    print(f"下载成功：{result.file_path}")
else:
    print(f"下载失败：{result.message}")
```

### 6. 批量获取
```python
papers = browser.batch_get_details_across_pages(
    max_count=20,
    max_pages=3
)
print(f"获取了 {len(papers)} 篇文章")
```

---

## 搜索类型

| 类型 | 值 | 说明 |
|------|-----|------|
| 主题 | `SearchType.SU` | 按主题搜索 |
| 篇名 | `SearchType.TI` | 按论文标题搜索 |
| 作者 | `SearchType.AU` | 按作者搜索 |
| 关键词 | `SearchType.KY` | 按关键词搜索 |
| 摘要 | `SearchType.AB` | 按摘要搜索 |
| 全文 | `SearchType.FT` | 按全文搜索 |

---

## 每页显示数量

```python
# 获取当前每页数量
size = browser.get_current_page_size()

# 设置为 20 条/页
browser.set_page_size(20)

# 设置为 50 条/页
browser.set_page_size(50)
```

---

## 页面状态

```python
status = browser.get_page_status()
print(f"页面类型：{status['page_type']}")
print(f"当前页：{status['current_page']}")
print(f"总页数：{status['total_pages']}")
print(f"结果总数：{status['result_count']}")
print(f"分类统计：{status['category_counts']}")
```

---

## 错误处理

```python
try:
    result = browser.search(request)
except Exception as e:
    print(f"搜索失败：{e}")

# 下载时检查权限
result = browser.download_paper(url, fmt="pdf")
if not result.success:
    if "无下载权限" in result.message:
        print("需要登录或购买权限")
    else:
        print(f"下载失败：{result.message}")
```

---

## 文件位置

```
tests/
├── verify_setup.py              # 快速验证脚本
├── verify_setup.bat             # Windows 运行器
├── test_complex_workflow.py      # 综合测试脚本
├── run_complex_test.bat          # Windows 运行器
└── TEST_SCRIPTS_README.md        # 详细说明
```

---

## 虚拟环境

```bash
# 激活虚拟环境
venv\Scripts\activate

# 运行脚本
python tests/verify_setup.py
```

---

## 常见问题

**Q: 验证码怎么处理？**
A: 脚本会自动检测验证码，并等待用户在浏览器中完成验证。

**Q: 下载失败怎么办？**
A: 检查是否有下载权限，或查看 `result.message` 中的错误信息。

**Q: 如何修改下载目录？**
A: 在 `download_paper()` 中传入 `save_dir` 参数。

**Q: 支持哪些下载格式？**
A: 支持 PDF 和 CAJ 格式，通过 `fmt` 参数指定。

---

## 相关文档

- `TEST_SUMMARY.md` - 完整测试总结
- `tests/TEST_SCRIPTS_README.md` - 测试脚本详细说明
- `docs/DEADLOCK_ANALYSIS_AND_FIXES.md` - 死锁分析
- `docs/UPGRADE_STRATEGY_V3.md` - 升级策略

