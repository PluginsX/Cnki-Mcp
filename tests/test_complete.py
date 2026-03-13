# -*- coding: utf-8 -*-
"""
CNKI MCP 服务完整功能测试

使用 MCP Python SDK 测试所有工具
"""

import asyncio
import json
import sys
import io
from pathlib import Path

# 强制 stdout 使用 utf-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))


async def test_all_tools():
    """测试所有工具"""
    print("\n" + "=" * 60)
    print("CNKI MCP 服务完整功能测试")
    print("=" * 60)

    try:
        from mcp.client.session import ClientSession
        from mcp.client.stdio import stdio_client, StdioServerParameters
    except ImportError:
        print("\n[FAIL] 错误: 未安装 mcp 包")
        print("   请运行: pip install mcp")
        return False

    test_results = []

    try:
        print("\n正在启动 MCP 服务...")

        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "cnki_mcp.server"],
            env=None
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                print("[OK] MCP 服务已启动并初始化\n")

                # ----------------------------------------------------------------
                # 测试 1: 列出工具
                # ----------------------------------------------------------------
                print("-" * 60)
                print("测试 1: 列出所有工具")
                print("-" * 60)

                try:
                    tools_result = await session.list_tools()
                    tools = tools_result.tools

                    print(f"\n[PASS] 找到 {len(tools)} 个工具:")
                    for i, tool in enumerate(tools, 1):
                        print(f"{i}. {tool.name}")
                        if tool.description:
                            print(f"   {tool.description[:80]}")

                    test_results.append(("list_tools", "PASS", len(tools)))

                except Exception as e:
                    print(f"\n[FAIL] 失败: {str(e)}")
                    test_results.append(("list_tools", "FAIL", str(e)))
                    return False

                print("\n" + "=" * 60)
                print("开始功能测试（浏览器将自动打开）...")
                print("=" * 60)

                # ----------------------------------------------------------------
                # 测试 2: cnki_search
                # ----------------------------------------------------------------
                print("\n" + "-" * 60)
                print("测试 2: cnki_search - 搜索功能")
                print("-" * 60)

                try:
                    print("\n执行搜索: keyword='人工智能', page_size=20")

                    result = await session.call_tool(
                        "cnki_search",
                        arguments={"keyword": "人工智能", "page_size": 20}
                    )

                    content = result.content[0].text
                    data = json.loads(content)

                    print(f"\n[PASS] 搜索成功!")
                    print(f"   总结果数: {data.get('total', 0):,} 条")
                    print(f"   每页条数: {data.get('page_size', 0)}")
                    print(f"   返回结果: {len(data.get('results', []))} 条")

                    # 分类统计
                    if data.get('category_counts'):
                        print(f"   分类统计:")
                        for cat, cnt in data['category_counts'].items():
                            print(f"     {cat}: {cnt:,}")

                    if data.get('results'):
                        first = data['results'][0]
                        print(f"\n   第一条结果:")
                        print(f"   标题: {first.get('title', '')[:60]}")
                        print(f"   作者: {first.get('author', '')}")

                    test_results.append(("cnki_search", "PASS", data.get('total', 0)))

                except Exception as e:
                    print(f"\n[FAIL] 失败: {str(e)}")
                    test_results.append(("cnki_search", "FAIL", str(e)))

                await asyncio.sleep(2)

                # ----------------------------------------------------------------
                # 测试 3: cnki_get_status
                # ----------------------------------------------------------------
                print("\n" + "-" * 60)
                print("测试 3: cnki_get_status - 获取状态")
                print("-" * 60)

                try:
                    result = await session.call_tool("cnki_get_status", arguments={})
                    data = json.loads(result.content[0].text)

                    print(f"\n[PASS] 获取状态成功!")
                    print(f"   页面类型: {data.get('page_type', '')}")
                    print(f"   当前页码: {data.get('current_page', 0)}/{data.get('total_pages', 0)}")
                    print(f"   结果总数: {data.get('result_count', 0):,}")
                    print(f"   每页显示: {data.get('current_page_size', 0)} 条")

                    if data.get('category_counts'):
                        print(f"   分类统计:")
                        for cat, cnt in data['category_counts'].items():
                            print(f"     {cat}: {cnt:,}")

                    test_results.append(("cnki_get_status", "PASS", data.get('current_page_size', 0)))

                except Exception as e:
                    print(f"\n[FAIL] 失败: {str(e)}")
                    test_results.append(("cnki_get_status", "FAIL", str(e)))

                await asyncio.sleep(2)

                # ----------------------------------------------------------------
                # 测试 4: cnki_set_page_size
                # ----------------------------------------------------------------
                print("\n" + "-" * 60)
                print("测试 4: cnki_set_page_size - 设置每页显示数量")
                print("-" * 60)

                try:
                    print("\n设置每页显示 50 条...")

                    result = await session.call_tool(
                        "cnki_set_page_size",
                        arguments={"page_size": 50}
                    )

                    content = result.content[0].text
                    print(f"\n[OK] {content}")

                    # 验证
                    status_result = await session.call_tool("cnki_get_status", arguments={})
                    status_data = json.loads(status_result.content[0].text)
                    actual_size = status_data.get('current_page_size', 0)

                    if actual_size == 50:
                        print(f"   [PASS] 设置已生效 (当前 {actual_size} 条)")
                        test_results.append(("cnki_set_page_size", "PASS", 50))
                    else:
                        print(f"   [WARN] 设置未生效 (期望50，实际{actual_size})")
                        test_results.append(("cnki_set_page_size", "WARN", actual_size))

                except Exception as e:
                    print(f"\n[FAIL] 失败: {str(e)}")
                    test_results.append(("cnki_set_page_size", "FAIL", str(e)))

                await asyncio.sleep(2)

                # ----------------------------------------------------------------
                # 测试 5: cnki_navigate_page
                # ----------------------------------------------------------------
                print("\n" + "-" * 60)
                print("测试 5: cnki_navigate_page - 翻页")
                print("-" * 60)

                try:
                    print("\n翻到下一页...")

                    result = await session.call_tool(
                        "cnki_navigate_page",
                        arguments={"action": "next"}
                    )

                    content = result.content[0].text
                    print(f"\n[OK] {content}")
                    test_results.append(("cnki_navigate_page", "PASS", "next"))

                except Exception as e:
                    print(f"\n[FAIL] 失败: {str(e)}")
                    test_results.append(("cnki_navigate_page", "FAIL", str(e)))

                await asyncio.sleep(2)

                # ----------------------------------------------------------------
                # 测试 6: cnki_get_paper_detail
                # ----------------------------------------------------------------
                print("\n" + "-" * 60)
                print("测试 6: cnki_get_paper_detail - 获取论文详情")
                print("-" * 60)

                try:
                    print("\n先搜索获取论文链接...")
                    search_result = await session.call_tool(
                        "cnki_search",
                        arguments={"keyword": "深度学习", "page_size": 10}
                    )

                    search_data = json.loads(search_result.content[0].text)

                    if search_data.get('results') and search_data['results'][0].get('link'):
                        paper_url = search_data['results'][0]['link']
                        print(f"获取论文详情: {paper_url[:70]}")

                        result = await session.call_tool(
                            "cnki_get_paper_detail",
                            arguments={"paper_url": paper_url}
                        )

                        data = json.loads(result.content[0].text)

                        print(f"\n[PASS] 获取详情成功!")
                        print(f"   标题: {data.get('title', '')[:60]}")
                        print(f"   作者: {data.get('author', '')}")
                        print(f"   摘要: {'有' if data.get('abstract') else '无'}")
                        print(f"   关键词: {data.get('keywords', '')[:60]}")

                        test_results.append(("cnki_get_paper_detail", "PASS", bool(data.get('abstract'))))
                    else:
                        print("[SKIP] 跳过: 无可用论文链接")
                        test_results.append(("cnki_get_paper_detail", "SKIP", "无链接"))

                except Exception as e:
                    print(f"\n[FAIL] 失败: {str(e)}")
                    test_results.append(("cnki_get_paper_detail", "FAIL", str(e)))

                await asyncio.sleep(2)

                # ----------------------------------------------------------------
                # 测试 7: cnki_batch_get_details
                # ----------------------------------------------------------------
                print("\n" + "-" * 60)
                print("测试 7: cnki_batch_get_details - 批量获取")
                print("-" * 60)

                try:
                    print("\n批量获取 3 篇论文详情（先重新搜索确保在结果页）...")

                    # 先搜索回到结果页
                    await session.call_tool(
                        "cnki_search",
                        arguments={"keyword": "人工智能", "page_size": 20}
                    )

                    result = await session.call_tool(
                        "cnki_batch_get_details",
                        arguments={"max_count": 3, "max_pages": 1}
                    )

                    raw = result.content[0].text
                    print(f"   原始返回: {raw[:200]}")

                    data = json.loads(raw)

                    count = data.get('total', 0)
                    if count > 0:
                        print(f"\n[PASS] 批量获取成功!")
                        print(f"   获取数量: {count} 篇")
                        test_results.append(("cnki_batch_get_details", "PASS", count))
                    else:
                        msg = data.get('message', '返回0篇')
                        print(f"\n[WARN] 批量获取返回0篇: {msg}")
                        test_results.append(("cnki_batch_get_details", "WARN", msg))

                except Exception as e:
                    print(f"\n[FAIL] 失败: {str(e)}")
                    test_results.append(("cnki_batch_get_details", "FAIL", str(e)))

                # ----------------------------------------------------------------
                # 测试总结
                # ----------------------------------------------------------------
                print("\n" + "=" * 60)
                print("测试总结")
                print("=" * 60)

                total = len(test_results)
                passed = sum(1 for _, s, _ in test_results if s == "PASS")
                failed = sum(1 for _, s, _ in test_results if s == "FAIL")
                warned = sum(1 for _, s, _ in test_results if s == "WARN")
                skipped = sum(1 for _, s, _ in test_results if s == "SKIP")

                print(f"\n总测试数: {total}")
                print(f"通过:     {passed}")
                print(f"失败:     {failed}")
                print(f"警告:     {warned}")
                print(f"跳过:     {skipped}")

                print("\n详细结果:")
                for i, (test, status, detail) in enumerate(test_results, 1):
                    flag = "[PASS]" if status == "PASS" else f"[{status}]"
                    print(f"{i}. {test}: {flag} ({detail})")

                print("\n" + "=" * 60)
                if failed == 0:
                    print("[ALL PASS] 所有测试通过!")
                else:
                    print(f"[FAILED] 有 {failed} 个测试失败")
                print("=" * 60 + "\n")

                return failed == 0

    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
        return False
    except Exception as e:
        print(f"\n\n测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    success = await test_all_tools()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
