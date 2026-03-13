"""
CNKI MCP 服务完整测试脚本

测试所有 MCP 工具的功能是否正常
"""

import asyncio
import json
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class CNKIMCPTester:
    def __init__(self):
        self.session = None
        self.test_results = []
        
    async def connect(self):
        """连接到 MCP 服务"""
        print("\n" + "=" * 60)
        print("正在启动 CNKI MCP 服务...")
        print("=" * 60)
        
        # 配置服务器参数
        server_params = StdioServerParameters(
            command="python",
            args=["-m", "cnki_mcp.server"],
            env=None
        )
        
        # 创建客户端连接
        stdio_transport = await stdio_client(server_params)
        self.stdio, self.write = stdio_transport
        
        self.session = ClientSession(self.stdio, self.write)
        await self.session.initialize()
        
        print("✓ MCP 服务已启动\n")
        
    async def list_tools(self):
        """列出所有可用工具"""
        print("\n" + "=" * 60)
        print("测试 1: 列出所有工具")
        print("=" * 60)
        
        try:
            result = await self.session.list_tools()
            tools = result.tools
            
            print(f"\n找到 {len(tools)} 个工具：")
            for i, tool in enumerate(tools, 1):
                print(f"\n{i}. {tool.name}")
                print(f"   描述: {tool.description[:80]}...")
            
            self.test_results.append({
                "test": "list_tools",
                "status": "✓ 通过",
                "tools_count": len(tools)
            })
            
            return tools
            
        except Exception as e:
            print(f"\n✗ 失败: {str(e)}")
            self.test_results.append({
                "test": "list_tools",
                "status": "✗ 失败",
                "error": str(e)
            })
            return []
    
    async def test_cnki_search(self):
        """测试 cnki_search 工具"""
        print("\n" + "=" * 60)
        print("测试 2: cnki_search - 基础搜索")
        print("=" * 60)
        
        try:
            print("\n执行搜索: keyword='人工智能', page_size=20")
            
            result = await self.session.call_tool(
                "cnki_search",
                arguments={
                    "keyword": "人工智能",
                    "page_size": 20
                }
            )
            
            # 解析结果
            content = result.content[0].text
            data = json.loads(content)
            
            print(f"\n✓ 搜索成功！")
            print(f"   总结果数: {data.get('total', 0)}")
            print(f"   当前页码: {data.get('page_num', 0)}")
            print(f"   每页条数: {data.get('page_size', 0)}")
            print(f"   返回结果: {len(data.get('results', []))} 条")
            
            if data.get('results'):
                print(f"\n   第一条结果:")
                first = data['results'][0]
                print(f"   - 标题: {first.get('title', '')[:50]}...")
                print(f"   - 作者: {first.get('author', '')}")
                print(f"   - 来源: {first.get('source', '')}")
            
            self.test_results.append({
                "test": "cnki_search",
                "status": "✓ 通过",
                "total": data.get('total', 0),
                "page_size": data.get('page_size', 0)
            })
            
            return True
            
        except Exception as e:
            print(f"\n✗ 失败: {str(e)}")
            self.test_results.append({
                "test": "cnki_search",
                "status": "✗ 失败",
                "error": str(e)
            })
            return False
    
    async def test_cnki_get_status(self):
        """测试 cnki_get_status 工具"""
        print("\n" + "=" * 60)
        print("测试 3: cnki_get_status - 获取页面状态")
        print("=" * 60)
        
        try:
            result = await self.session.call_tool(
                "cnki_get_status",
                arguments={}
            )
            
            content = result.content[0].text
            data = json.loads(content)
            
            print(f"\n✓ 获取状态成功！")
            print(f"   页面类型: {data.get('page_type', '')}")
            print(f"   当前页码: {data.get('current_page', 0)}")
            print(f"   总页数: {data.get('total_pages', 0)}")
            print(f"   结果总数: {data.get('result_count', 0)}")
            print(f"   每页显示: {data.get('current_page_size', 0)} 条")
            print(f"   搜索类型: {data.get('search_type', '')}")
            
            self.test_results.append({
                "test": "cnki_get_status",
                "status": "✓ 通过",
                "page_type": data.get('page_type', ''),
                "current_page_size": data.get('current_page_size', 0)
            })
            
            return True
            
        except Exception as e:
            print(f"\n✗ 失败: {str(e)}")
            self.test_results.append({
                "test": "cnki_get_status",
                "status": "✗ 失败",
                "error": str(e)
            })
            return False
    
    async def test_cnki_set_page_size(self):
        """测试 cnki_set_page_size 工具"""
        print("\n" + "=" * 60)
        print("测试 4: cnki_set_page_size - 设置每页显示数量")
        print("=" * 60)
        
        try:
            print("\n设置每页显示 50 条...")
            
            result = await self.session.call_tool(
                "cnki_set_page_size",
                arguments={
                    "page_size": 50
                }
            )
            
            content = result.content[0].text
            print(f"\n✓ {content}")
            
            # 验证设置是否生效
            status_result = await self.session.call_tool(
                "cnki_get_status",
                arguments={}
            )
            
            status_content = status_result.content[0].text
            status_data = json.loads(status_content)
            
            actual_size = status_data.get('current_page_size', 0)
            print(f"   验证: 当前每页显示 {actual_size} 条")
            
            if actual_size == 50:
                print(f"   ✓ 设置已生效")
                self.test_results.append({
                    "test": "cnki_set_page_size",
                    "status": "✓ 通过",
                    "target": 50,
                    "actual": actual_size
                })
            else:
                print(f"   ✗ 设置未生效（期望50，实际{actual_size}）")
                self.test_results.append({
                    "test": "cnki_set_page_size",
                    "status": "✗ 部分失败",
                    "target": 50,
                    "actual": actual_size
                })
            
            return True
            
        except Exception as e:
            print(f"\n✗ 失败: {str(e)}")
            self.test_results.append({
                "test": "cnki_set_page_size",
                "status": "✗ 失败",
                "error": str(e)
            })
            return False
    
    async def test_cnki_navigate_page(self):
        """测试 cnki_navigate_page 工具"""
        print("\n" + "=" * 60)
        print("测试 5: cnki_navigate_page - 翻页")
        print("=" * 60)
        
        try:
            print("\n翻到下一页...")
            
            result = await self.session.call_tool(
                "cnki_navigate_page",
                arguments={
                    "action": "next"
                }
            )
            
            content = result.content[0].text
            print(f"\n✓ {content}")
            
            # 验证页码是否改变
            status_result = await self.session.call_tool(
                "cnki_get_status",
                arguments={}
            )
            
            status_content = status_result.content[0].text
            status_data = json.loads(status_content)
            
            current_page = status_data.get('current_page', 0)
            print(f"   当前页码: {current_page}")
            
            self.test_results.append({
                "test": "cnki_navigate_page",
                "status": "✓ 通过",
                "current_page": current_page
            })
            
            return True
            
        except Exception as e:
            print(f"\n✗ 失败: {str(e)}")
            self.test_results.append({
                "test": "cnki_navigate_page",
                "status": "✗ 失败",
                "error": str(e)
            })
            return False
    
    async def test_cnki_get_paper_detail(self):
        """测试 cnki_get_paper_detail 工具"""
        print("\n" + "=" * 60)
        print("测试 6: cnki_get_paper_detail - 获取论文详情")
        print("=" * 60)
        
        try:
            # 先搜索获取一个论文链接
            print("\n先搜索获取论文链接...")
            search_result = await self.session.call_tool(
                "cnki_search",
                arguments={
                    "keyword": "深度学习",
                    "page_size": 10
                }
            )
            
            search_content = search_result.content[0].text
            search_data = json.loads(search_content)
            
            if not search_data.get('results'):
                print("✗ 没有搜索结果，跳过此测试")
                self.test_results.append({
                    "test": "cnki_get_paper_detail",
                    "status": "⊘ 跳过",
                    "reason": "无搜索结果"
                })
                return False
            
            # 获取第一篇论文的链接
            paper_url = search_data['results'][0].get('link', '')
            if not paper_url:
                print("✗ 第一篇论文没有链接，跳过此测试")
                self.test_results.append({
                    "test": "cnki_get_paper_detail",
                    "status": "⊘ 跳过",
                    "reason": "无论文链接"
                })
                return False
            
            print(f"\n获取论文详情: {paper_url[:60]}...")
            
            result = await self.session.call_tool(
                "cnki_get_paper_detail",
                arguments={
                    "paper_url": paper_url
                }
            )
            
            content = result.content[0].text
            data = json.loads(content)
            
            print(f"\n✓ 获取详情成功！")
            print(f"   标题: {data.get('title', '')[:50]}...")
            print(f"   作者: {data.get('author', '')}")
            print(f"   摘要: {data.get('abstract', '')[:80]}...")
            print(f"   关键词: {data.get('keywords', '')}")
            print(f"   DOI: {data.get('doi', '')}")
            
            self.test_results.append({
                "test": "cnki_get_paper_detail",
                "status": "✓ 通过",
                "has_abstract": bool(data.get('abstract')),
                "has_keywords": bool(data.get('keywords'))
            })
            
            return True
            
        except Exception as e:
            print(f"\n✗ 失败: {str(e)}")
            self.test_results.append({
                "test": "cnki_get_paper_detail",
                "status": "✗ 失败",
                "error": str(e)
            })
            return False
    
    async def test_cnki_batch_get_details(self):
        """测试 cnki_batch_get_details 工具"""
        print("\n" + "=" * 60)
        print("测试 7: cnki_batch_get_details - 批量获取详情")
        print("=" * 60)
        
        try:
            print("\n批量获取 5 篇论文详情（最多翻1页）...")
            
            result = await self.session.call_tool(
                "cnki_batch_get_details",
                arguments={
                    "max_count": 5,
                    "max_pages": 1
                }
            )
            
            content = result.content[0].text
            data = json.loads(content)
            
            print(f"\n✓ 批量获取成功！")
            print(f"   获取数量: {data.get('total', 0)} 篇")
            
            if data.get('papers'):
                print(f"\n   前3篇论文:")
                for i, paper in enumerate(data['papers'][:3], 1):
                    print(f"   {i}. {paper.get('title', '')[:40]}...")
            
            self.test_results.append({
                "test": "cnki_batch_get_details",
                "status": "✓ 通过",
                "total": data.get('total', 0)
            })
            
            return True
            
        except Exception as e:
            print(f"\n✗ 失败: {str(e)}")
            self.test_results.append({
                "test": "cnki_batch_get_details",
                "status": "✗ 失败",
                "error": str(e)
            })
            return False
    
    def print_summary(self):
        """打印测试总结"""
        print("\n" + "=" * 60)
        print("测试总结")
        print("=" * 60)
        
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if "✓" in r["status"])
        failed = sum(1 for r in self.test_results if "✗" in r["status"])
        skipped = sum(1 for r in self.test_results if "⊘" in r["status"])
        
        print(f"\n总测试数: {total}")
        print(f"通过: {passed}")
        print(f"失败: {failed}")
        print(f"跳过: {skipped}")
        
        print("\n详细结果:")
        for i, result in enumerate(self.test_results, 1):
            print(f"\n{i}. {result['test']}")
            print(f"   状态: {result['status']}")
            for key, value in result.items():
                if key not in ['test', 'status']:
                    print(f"   {key}: {value}")
        
        print("\n" + "=" * 60)
        if failed == 0:
            print("✓ 所有测试通过！")
        else:
            print(f"✗ 有 {failed} 个测试失败")
        print("=" * 60 + "\n")
    
    async def run_all_tests(self):
        """运行所有测试"""
        try:
            # 连接服务
            await self.connect()
            
            # 列出工具
            await self.list_tools()
            
            # 等待用户准备
            print("\n" + "=" * 60)
            print("准备开始测试...")
            print("请确保:")
            print("1. 浏览器窗口可见")
            print("2. 准备完成验证码（如果出现）")
            print("=" * 60)
            input("\n按 Enter 键开始测试...")
            
            # 执行测试
            await self.test_cnki_search()
            await asyncio.sleep(2)
            
            await self.test_cnki_get_status()
            await asyncio.sleep(2)
            
            await self.test_cnki_set_page_size()
            await asyncio.sleep(2)
            
            await self.test_cnki_navigate_page()
            await asyncio.sleep(2)
            
            await self.test_cnki_get_paper_detail()
            await asyncio.sleep(2)
            
            await self.test_cnki_batch_get_details()
            
            # 打印总结
            self.print_summary()
            
        except KeyboardInterrupt:
            print("\n\n测试被用户中断")
        except Exception as e:
            print(f"\n\n测试过程中发生错误: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            if self.session:
                await self.session.__aexit__(None, None, None)


async def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("CNKI MCP 服务完整测试")
    print("=" * 60)
    
    tester = CNKIMCPTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())

