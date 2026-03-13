# CNKI MCP Server

知网(CNKI)文献检索 MCP 服务

## 功能特性

### 核心功能
- ✅ 文献检索（支持主题、篇名、作者等6种搜索类型）
- ✅ 资源类型筛选（学位论文、期刊、会议等）
- ✅ 论文详情获取（摘要、关键词、引用格式等）
- ✅ **页面状态感知**（实时获取页面类型、结果数、页码）
- ✅ **智能导航控制**（上一页/下一页翻页）
- ✅ **批量跨页获取**（自动翻页批量获取论文详情）

### 技术特点
- 🌐 基于 Playwright 浏览器自动化
- 🔄 单例模式保持会话状态
- 🛡️ 完善的反爬虫策略
- 🤖 智能验证码处理
- 📊 实时页面状态监控

## 安装

```bash
pip install -e .
playwright install chromium
```

## 配置

在 IDE 的 `mcp.json` 中添加:

```json
{
  "mcpServers": {
    "CNKI": {
      "command": "C:\\Users\\Administrator\\Desktop\\Cnki-Mcp\\venv\\Scripts\\python.exe",
      "args": ["-m", "cnki_mcp.server"]
    }
  }
}
```

## MCP 工具清单

### 1. cnki_search
文献检索工具，支持多种搜索类型和筛选条件。

**参数**：
- `keyword` (必填): 检索关键词
- `search_type`: 检索类型 (SU/TI/AU/KY/AB/FT)
- `db_code`: 数据库代码 (CJFD/CDMD/CMFD)
- `page_size`: 每页条数 (1-50)
- `filter_resource`: 资源类型筛选

### 2. cnki_get_paper_detail
获取单篇论文的详细信息。

**参数**：
- `paper_url` (必填): 论文详情页URL

### 3. cnki_get_status ✨ 新增
获取当前页面状态信息。

**返回**：
- 页面类型（首页/搜索结果页/详情页）
- 搜索结果总数
- 当前页码/总页数
- 当前搜索类型
- 当前筛选条件

### 4. cnki_navigate_page ✨ 新增
在搜索结果中翻页。

**参数**：
- `action` (必填): 翻页操作 (next/prev)

### 5. cnki_batch_get_details ✨ 新增
跨页批量获取论文详情。

**参数**：
- `max_count`: 最大获取数量（建议≤20）
- `max_pages`: 最大翻页数

## 使用示例

### 基础搜索
```python
# Agent 调用
cnki_search(keyword="数字文物", filter_resource="DISSERTATION")
```

### 智能导航
```python
# 1. 执行搜索
cnki_search(keyword="人工智能", page_size=10)

# 2. 查看状态
cnki_get_status()
# 返回: {"page_type": "search", "result_count": 1557, "current_page": 1, "total_pages": 78}

# 3. 翻到下一页
cnki_navigate_page(action="next")

# 4. 再次查看状态
cnki_get_status()
# 返回: {"current_page": 2, "total_pages": 78}
```

### 批量获取
```python
# 搜索并批量获取前15篇论文详情
cnki_search(keyword="数字文物", filter_resource="DISSERTATION")
cnki_batch_get_details(max_count=15, max_pages=2)
# 自动翻页并获取详情
```

## 测试

```bash
# 测试新功能
python test_new_features.py
```

## 注意事项

1. **验证码处理**: 首次使用或触发验证码时，需要手动完成拼图验证
2. **反爬虫策略**: 批量获取时建议 max_count ≤ 20，避免触发反爬虫
3. **页面状态**: 使用导航功能前，确保已执行搜索并在搜索结果页
4. **浏览器会话**: 服务会保持浏览器会话，避免重复初始化

## 升级日志

### v0.2.0 (2026-03-13)
- ✨ 新增页面状态感知功能
- ✨ 新增智能导航控制（上一页/下一页）
- ✨ 新增批量跨页获取功能
- 🔧 优化页面加载等待策略
- 📝 完善文档和测试

### v0.1.0
- 基础搜索功能
- 论文详情获取
- 资源类型筛选
