# CNKI MCP Server

知网(CNKI)文献检索 MCP 服务

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

## 使用

提供以下 MCP 工具:

- `cnki_search`: 知网文献检索
  - `keyword`: 检索关键词 (必填)
  - `db_code`: 数据库代码 (CJFD/CDMD/CMFD, 默认 CJFD)
  - `page_size`: 每页条数 (1-50, 默认 10)
  - `page_num`: 页码 (默认 1)
