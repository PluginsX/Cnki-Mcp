"""测试新增的状态感知和导航控制功能"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from cnki_mcp.browser import get_browser
from cnki_mcp.models import CNKIQueryRequest, SearchType


def safe_print(msg: str):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('utf-8', errors='replace').decode('utf-8'))


def test_status_and_navigation():
    """测试状态感知和导航控制功能"""
    safe_print("=" * 80)
    safe_print("测试新功能：状态感知 + 导航控制 + 批量获取")
    safe_print("=" * 80)
    
    browser = get_browser()
    
    # 1. 初始化
    if not browser.is_ready():
        safe_print("\n[1] 初始化浏览器...")
        if not browser.initialize():
            safe_print("初始化失败！")
            return
    
    # 2. 执行搜索
    safe_print("\n[2] 执行搜索：数字文物")
    request = CNKIQueryRequest(
        keyword="数字文物",
        search_type=SearchType.SU,
        page_size=5
    )
    
    try:
        result = browser.search(request)
        safe_print(f"搜索完成，获取到 {len(result.results)} 条结果")
    except Exception as e:
        safe_print(f"搜索失败：{e}")
        return
    
    # 3. 测试状态获取
    safe_print("\n[3] 测试 get_page_status()")
    safe_print("-" * 80)
    status = browser.get_page_status()
    safe_print(f"页面类型: {status.get('page_type')}")
    safe_print(f"结果总数: {status.get('result_count')}")
    safe_print(f"当前页码: {status.get('current_page')}")
    safe_print(f"总页数: {status.get('total_pages')}")
    safe_print(f"搜索类型: {status.get('search_type')}")
    safe_print(f"筛选条件: {status.get('filter_active')}")
    
    # 4. 测试翻页
    safe_print("\n[4] 测试 next_page()")
    safe_print("-" * 80)
    if browser.next_page():
        safe_print("✓ 翻页成功")
        status = browser.get_page_status()
        safe_print(f"当前页码: {status.get('current_page')}/{status.get('total_pages')}")
    else:
        safe_print("✗ 翻页失败")
    
    # 5. 测试返回上一页
    safe_print("\n[5] 测试 prev_page()")
    safe_print("-" * 80)
    if browser.prev_page():
        safe_print("✓ 返回上一页成功")
        status = browser.get_page_status()
        safe_print(f"当前页码: {status.get('current_page')}/{status.get('total_pages')}")
    else:
        safe_print("✗ 返回上一页失败")
    
    # 6. 测试批量获取（小规模测试）
    safe_print("\n[6] 测试 batch_get_details_across_pages()")
    safe_print("-" * 80)
    safe_print("批量获取 3 篇论文详情（最多翻 2 页）...")
    
    try:
        papers = browser.batch_get_details_across_pages(max_count=3, max_pages=2)
        safe_print(f"\n✓ 批量获取成功，共获取 {len(papers)} 篇")
        
        for i, paper in enumerate(papers, 1):
            safe_print(f"\n[{i}] {paper.title}")
            safe_print(f"    作者: {paper.author}")
            safe_print(f"    来源: {paper.source}")
            safe_print(f"    摘要: {paper.abstract[:100]}..." if len(paper.abstract) > 100 else f"    摘要: {paper.abstract}")
    except Exception as e:
        safe_print(f"✗ 批量获取失败：{e}")
        import traceback
        traceback.print_exc()
    
    # 7. 最终状态
    safe_print("\n[7] 最终状态")
    safe_print("-" * 80)
    status = browser.get_page_status()
    safe_print(f"当前页码: {status.get('current_page')}/{status.get('total_pages')}")
    
    safe_print("\n" + "=" * 80)
    safe_print("测试完成！")
    safe_print("=" * 80)


if __name__ == "__main__":
    test_status_and_navigation()

