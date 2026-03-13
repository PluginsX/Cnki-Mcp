"""CNKI MCP Server - 知网检索 MCP 服务主入口"""

import json
import asyncio
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .models import CNKIQueryRequest, CNKIQueryResult, SEARCH_TYPE_NAMES
from .browser import get_browser

APP_NAME = "cnki-mcp"
APP_VERSION = "0.1.0"

server = Server(APP_NAME)
_browser_initialized = False


def init_browser():
    global _browser_initialized
    if _browser_initialized:
        return True
    
    browser = get_browser()
    success = browser.initialize()
    if success:
        _browser_initialized = True
    return success


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="cnki_search",
            description="知网文献检索工具。通过关键词在中国知网 (CNKI) 检索学术文献。服务启动时会自动打开浏览器，请根据提示完成安全验证。",
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "检索关键词"
                    },
                    "search_type": {
                        "type": "string",
                        "description": "检索类型: SU=主题, TI=篇名, AU=作者, KY=关键词, AB=摘要, FT=全文",
                        "default": "SU",
                        "enum": ["SU", "TI", "AU", "KY", "AB", "FT"]
                    },
                    "db_code": {
                        "type": "string",
                        "description": "数据库代码: CJFD=期刊(默认), CDMD=硕博论文, CMFD=会议论文",
                        "default": "CJFD",
                        "enum": ["CJFD", "CDMD", "CMFD"]
                    },
                    "page_size": {
                        "type": "integer",
                        "description": "每页条数(1-50)",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50
                    },
                    "page_num": {
                        "type": "integer",
                        "description": "页码",
                        "default": 1,
                        "minimum": 1
                    },
                    "filter_resource": {
                        "type": "string",
                        "description": "筛选资源类型: DISSERTATION=学位论文, JOURNAL=学术期刊, CONFERENCE=会议, NEWSPAPER=报纸, BOOK=图书, PATENT=专利, STANDARD=标准, ACHIEVEMENTS=成果",
                        "default": ""
                    }
                },
                "required": ["keyword"]
            }
        ),
        Tool(
            name="cnki_get_paper_detail",
            description="获取知网文章详细信息，包括摘要、关键词、引用格式等完整元数据。",
            inputSchema={
                "type": "object",
                "properties": {
                    "paper_url": {
                        "type": "string",
                        "description": "文章详情页的URL（从cnki_search的结果中获取）"
                    }
                },
                "required": ["paper_url"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    if name == "cnki_search":
        try:
            # 智能识别搜索类型
            keyword = arguments.get("keyword", "")
            search_type = arguments.get("search_type")
            
            # 如果用户没有明确指定搜索类型，尝试根据关键词智能判断
            if not search_type:
                # 检查是否包含作者搜索的指示词
                author_indicators = ["作者", "author", "著者", "姓名"]
                if any(indicator in keyword for indicator in author_indicators):
                    search_type = "AU"
                    # 清理关键词，移除指示词
                    for indicator in author_indicators:
                        keyword = keyword.replace(indicator, "").strip()
                    arguments["keyword"] = keyword
                    arguments["search_type"] = search_type
            
            request = CNKIQueryRequest(**arguments)
        except Exception as e:
            return [TextContent(type="text", text=f"参数错误：{str(e)}")]

        try:
            browser = get_browser()
            
            if not browser.is_ready():
                init_result = await asyncio.to_thread(init_browser)
                if not init_result:
                    return [TextContent(type="text", text="浏览器初始化失败，请检查是否完成验证码")]
            
            result = await asyncio.to_thread(browser.search, request)
            
            result_dict = result.model_dump()
            result_text = json.dumps(result_dict, ensure_ascii=False, indent=2)
            
            return [TextContent(type="text", text=result_text)]
            
        except Exception as e:
            return [TextContent(type="text", text=f"检索失败: {str(e)}")]
    
    elif name == "cnki_get_paper_detail":
        try:
            paper_url = arguments.get("paper_url")
            if not paper_url:
                return [TextContent(type="text", text="错误：缺少paper_url参数")]
            
            browser = get_browser()
            
            if not browser.is_ready():
                init_result = await asyncio.to_thread(init_browser)
                if not init_result:
                    return [TextContent(type="text", text="浏览器初始化失败，请检查是否完成验证码")]
            
            paper = await asyncio.to_thread(browser.get_paper_detail, paper_url)
            
            if paper:
                paper_dict = paper.model_dump()
                result_text = json.dumps(paper_dict, ensure_ascii=False, indent=2)
                return [TextContent(type="text", text=result_text)]
            else:
                return [TextContent(type="text", text="获取文章详情失败")]
            
        except Exception as e:
            import traceback
            error_msg = f"获取文章详情失败: {str(e)}\n{traceback.format_exc()}"
            return [TextContent(type="text", text=error_msg)]
    
    else:
        return [TextContent(type="text", text=f"未知工具: {name}")]


def safe_print(msg: str, file=None):
    try:
        if file:
            print(msg, file=file)
        else:
            print(msg)
    except UnicodeEncodeError:
        encoded = msg.encode('utf-8', errors='replace').decode('utf-8')
        if file:
            print(encoded, file=file)
        else:
            print(encoded)


async def run_server():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    safe_print("\n" + "=" * 60, file=sys.stderr)
    safe_print("[*] 启动知网检索 MCP 服务", file=sys.stderr)
    safe_print("=" * 60, file=sys.stderr)
    safe_print("\n[*] 浏览器将在首次调用工具时初始化\n", file=sys.stderr)
    
    asyncio.run(run_server())
