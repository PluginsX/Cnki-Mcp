"""CNKI MCP Server - 知网检索 MCP 服务主入口"""

import json
import asyncio
import sys
from typing import Any
from concurrent.futures import ThreadPoolExecutor

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .models import CNKIQueryRequest, CNKIQueryResult, SEARCH_TYPE_NAMES, InitState
from .browser import get_browser

APP_NAME = "cnki-mcp"
APP_VERSION = "0.1.0"

server = Server(APP_NAME)

# Playwright 必须固定在同一个线程中运行，使用单线程池
_browser_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="playwright")

# 全局异步锁和事件（用于协调并发初始化）
_init_async_lock = asyncio.Lock()
_init_complete_event = asyncio.Event()


async def run_in_browser_thread(func, *args):
    """在固定的 Playwright 专用线程中执行函数，避免 greenlet 跨线程错误"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_browser_executor, func, *args)


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


async def ensure_browser_ready() -> bool:
    """确保浏览器已初始化（智能等待机制）"""
    browser = get_browser()

    if browser.is_ready():
        return True

    init_state = browser._init_state

    if init_state == InitState.IN_PROGRESS:
        safe_print("检测到初始化正在进行，等待完成...", file=sys.stderr)
        try:
            await asyncio.wait_for(_init_complete_event.wait(), timeout=300)
            return browser.is_ready()
        except asyncio.TimeoutError:
            safe_print("等待初始化超时", file=sys.stderr)
            return False

    async with _init_async_lock:
        if browser.is_ready():
            return True

        if init_state == InitState.FAILED:
            _init_complete_event.clear()

        safe_print("开始初始化浏览器...", file=sys.stderr)
        result = await run_in_browser_thread(browser.initialize)

        if result:
            _init_complete_event.set()

        return result


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
                        "description": "每页显示条数，支持10/20/50三个选项。设置后会自动调整知网页面的显示数量。",
                        "default": 10,
                        "enum": [10, 20, 50]
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
        ),
        Tool(
            name="cnki_get_status",
            description="获取当前知网页面状态，包括页面类型、搜索结果数、当前页码、总页数等信息。用于Agent了解当前浏览器状态。",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="cnki_navigate_page",
            description="在搜索结果中翻页（上一页/下一页）。注意：知网不支持直接跳转到指定页码，只能逐页导航。",
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
        ),
        Tool(
            name="cnki_batch_get_details",
            description="跨页批量获取多篇论文的详细信息。会自动翻页直到达到目标数量或页数限制。建议max_count≤20以避免触发反爬虫。",
            inputSchema={
                "type": "object",
                "properties": {
                    "max_count": {
                        "type": "integer",
                        "description": "最大获取数量（建议≤20）",
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
        ),
        Tool(
            name="cnki_set_page_size",
            description="设置搜索结果每页显示数量。支持10/20/50三个选项。修改后页面会自动刷新，当前页码保持不变。",
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
        ),
        Tool(
            name="cnki_download_paper",
            description="下载知网论文文件（PDF 或 CAJ 格式）。需要先通过 cnki_get_paper_detail 确认论文有下载链接（can_download=true）。实际能否下载取决于账号权限。\n\n重要：调用此工具时必须明确指定 save_dir（保存目录）。若用户未指定，Agent 应自动选择合适目录（如用户桌面 ~/Desktop 或 ~/Downloads），并在调用前告知用户文件将保存到哪里。",
            inputSchema={
                "type": "object",
                "properties": {
                    "paper_url": {
                        "type": "string",
                        "description": "论文详情页 URL（从 cnki_search 或 cnki_get_paper_detail 的结果中获取）"
                    },
                    "fmt": {
                        "type": "string",
                        "description": "下载格式：pdf 或 caj，默认 pdf",
                        "enum": ["pdf", "caj"],
                        "default": "pdf"
                    },
                    "save_dir": {
                        "type": "string",
                        "description": "文件保存目录的绝对路径。必须明确指定，不可省略。用户未指定时 Agent 应自行选择合理目录（如 ~/Downloads 或 ~/Desktop）并告知用户。"
                    }
                },
                "required": ["paper_url", "save_dir"]
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
            # 使用智能等待机制（对 Agent 透明）
            if not await ensure_browser_ready():
                return [TextContent(type="text", text="浏览器初始化失败或超时，请重试")]
            
            browser = get_browser()
            result = await run_in_browser_thread(browser.search, request)
            
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
            
            # 使用智能等待机制
            if not await ensure_browser_ready():
                return [TextContent(type="text", text="浏览器初始化失败或超时，请重试")]
            
            browser = get_browser()
            paper = await run_in_browser_thread(browser.get_paper_detail, paper_url)
            
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
    
    elif name == "cnki_get_status":
        try:
            if not await ensure_browser_ready():
                return [TextContent(type="text", text="浏览器未初始化")]

            browser = get_browser()
            status = await run_in_browser_thread(browser.get_page_status)
            result_text = json.dumps(status, ensure_ascii=False, indent=2)
            return [TextContent(type="text", text=result_text)]

        except Exception as e:
            return [TextContent(type="text", text=f"获取状态失败: {str(e)}")]
    
    elif name == "cnki_navigate_page":
        try:
            action = arguments.get("action")
            if not action:
                return [TextContent(type="text", text="错误：缺少action参数")]
            
            # 使用智能等待机制
            if not await ensure_browser_ready():
                return [TextContent(type="text", text="浏览器未初始化")]
            
            browser = get_browser()
            
            if action == "next":
                success = await run_in_browser_thread(browser.next_page)
            elif action == "prev":
                success = await run_in_browser_thread(browser.prev_page)
            else:
                return [TextContent(type="text", text=f"错误：未知操作 {action}")]
            
            if success:
                status = await run_in_browser_thread(browser.get_page_status)
                return [TextContent(
                    type="text",
                    text=f"翻页成功！当前第 {status.get('current_page')} 页，共 {status.get('total_pages')} 页"
                )]
            else:
                return [TextContent(type="text", text="翻页失败，请查看日志")]
            
        except Exception as e:
            return [TextContent(type="text", text=f"翻页失败: {str(e)}")]
    
    elif name == "cnki_batch_get_details":
        try:
            max_count = arguments.get("max_count", 10)
            max_pages = arguments.get("max_pages", 3)
            
            # 使用智能等待机制
            if not await ensure_browser_ready():
                return [TextContent(type="text", text="浏览器未初始化")]
            
            browser = get_browser()
            papers = await run_in_browser_thread(
                browser.batch_get_details_across_pages,
                max_count,
                max_pages
            )
            
            if papers:
                result = {
                    "total": len(papers),
                    "papers": [p.model_dump() for p in papers]
                }
            else:
                result = {"total": 0, "papers": [], "message": "未获取到论文详情，请先执行搜索"}
            result_text = json.dumps(result, ensure_ascii=False, indent=2)
            return [TextContent(type="text", text=result_text)]
            
        except Exception as e:
            import traceback
            error_msg = f"批量获取失败: {str(e)}\n{traceback.format_exc()}"
            return [TextContent(type="text", text=error_msg)]
    
    elif name == "cnki_set_page_size":
        try:
            page_size = arguments.get("page_size")
            if not page_size:
                return [TextContent(type="text", text="错误：缺少page_size参数")]
            
            if page_size not in [10, 20, 50]:
                return [TextContent(type="text", text=f"错误：page_size必须是10、20或50，当前值：{page_size}")]
            
            # 使用智能等待机制
            if not await ensure_browser_ready():
                return [TextContent(type="text", text="浏览器未初始化")]
            
            browser = get_browser()
            success = await run_in_browser_thread(browser.set_page_size, page_size)
            
            if success:
                status = await run_in_browser_thread(browser.get_page_status)
                return [TextContent(
                    type="text",
                    text=f"成功设置每页显示 {page_size} 条！当前第 {status.get('current_page', 1)} 页，共 {status.get('total_pages', 1)} 页"
                )]
            else:
                return [TextContent(type="text", text="设置每页显示数量失败，请查看日志")]
            
        except Exception as e:
            return [TextContent(type="text", text=f"设置失败: {str(e)}")]
    
    elif name == "cnki_download_paper":
        try:
            paper_url = arguments.get("paper_url")
            if not paper_url:
                return [TextContent(type="text", text="错误：缺少 paper_url 参数")]
            
            fmt = arguments.get("fmt", "pdf")
            save_dir = arguments.get("save_dir", "").strip()
            
            # save_dir 为必填项，未传时拒绝执行
            if not save_dir:
                return [TextContent(
                    type="text",
                    text=(
                        "错误：必须指定 save_dir（文件保存目录）。\n"
                        "请明确告知用户文件将保存到哪里，然后重新调用并传入 save_dir 参数。\n"
                        "建议目录：\n"
                        "  Windows: C:/Users/<用户名>/Downloads 或 C:/Users/<用户名>/Desktop\n"
                        "  macOS/Linux: ~/Downloads 或 ~/Desktop"
                    )
                )]
            
            import os
            # 展开 ~ 为实际用户目录
            save_dir = os.path.expanduser(save_dir)
            save_dir_abs = os.path.abspath(save_dir)
            
            if not await ensure_browser_ready():
                return [TextContent(type="text", text="浏览器初始化失败或超时，请重试")]
            
            browser = get_browser()
            result = await run_in_browser_thread(
                browser.download_paper, paper_url, fmt, save_dir_abs
            )
            
            result_dict = result.model_dump()
            
            # 构建人类可读的摘要
            if result.success:
                summary = (
                    f"下载成功！\n"
                    f"  文件名：{result.file_name}\n"
                    f"  保存路径：{result.file_path}\n"
                    f"  格式：{result.format.upper()}"
                )
            else:
                summary = (
                    f"下载失败：{result.message}\n"
                    f"  目标目录：{save_dir_abs}"
                )
            
            result_dict["summary"] = summary
            return [TextContent(type="text", text=json.dumps(result_dict, ensure_ascii=False, indent=2))]
            
        except Exception as e:
            import traceback
            error_msg = f"下载失败: {str(e)}\n{traceback.format_exc()}"
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
    safe_print("\n[*] 浏览器将在首次调用工具时自动初始化", file=sys.stderr)
    safe_print("[*] 多个并发调用会自动等待初始化完成\n", file=sys.stderr)
    
    asyncio.run(run_server())
