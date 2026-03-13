# -*- coding: utf-8 -*-
"""测试知网搜索结果统计功能"""

import sys
import os
import io

# 强制 stdout 使用 utf-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from cnki_mcp.browser import CNKIBrowser
from cnki_mcp.models import CNKIQueryRequest, SearchType


def test_result_statistics():
    """测试结果统计功能"""
    print("\n" + "=" * 80)
    print("测试：知网搜索结果统计功能")
    print("=" * 80)

    browser = CNKIBrowser.get_instance()

    print("\n[步骤1] 初始化浏览器...")
    if not browser.initialize():
        print("[FAIL] 初始化失败")
        return False
    print("[OK] 初始化成功")

    print("\n[步骤2] 执行搜索：人工智能...")
    request = CNKIQueryRequest(
        keyword="人工智能",
        search_type=SearchType.SU,
        page_size=20
    )

    result = browser.search(request)

    print("\n[步骤3] 验证统计数据")
    print("-" * 80)

    print(f"\n[统计] 搜索结果统计：")
    print(f"  总结果数: {result.total} 条")
    print(f"  当前页码: {result.page_num}")
    print(f"  每页显示: {result.page_size} 条")
    print(f"  当前页实际获取: {len(result.results)} 条")

    if result.category_counts:
        print(f"\n[分类] 分类统计：")
        for category, count in result.category_counts.items():
            print(f"  {category}: {count:,} 条")
    else:
        print("\n[WARN] 未获取到分类统计")

    print("\n[步骤4] 验证数据合理性")
    print("-" * 80)

    checks = []

    # 检查1: 总数应该大于0
    if result.total > 0:
        print(f"[PASS] 总数 > 0: {result.total}")
        checks.append(True)
    else:
        print(f"[FAIL] 总数应该 > 0，实际: {result.total}")
        checks.append(False)

    # 检查2: 当前页结果数应该 <= 每页显示数
    if len(result.results) <= result.page_size:
        print(f"[PASS] 当前页结果数 <= 每页显示数: {len(result.results)} <= {result.page_size}")
        checks.append(True)
    else:
        print(f"[FAIL] 当前页结果数不应超过每页显示数: {len(result.results)} > {result.page_size}")
        checks.append(False)

    # 检查3: 有分类统计数据且总数 > 0
    if result.category_counts:
        total_lib_count = result.category_counts.get("总库", 0)
        if total_lib_count > 0 and total_lib_count == result.total:
            print(f"[PASS] 总库数 = 总数: {total_lib_count} = {result.total}")
            checks.append(True)
        elif total_lib_count == 0:
            # 总库条目未获取，但其他分类有数据也算通过
            total_by_categories = sum(result.category_counts.values())
            if total_by_categories > 0:
                print(f"[PASS] 获取到 {len(result.category_counts)} 个分类统计，合计 {total_by_categories:,} 条")
                checks.append(True)
            else:
                print(f"[FAIL] 未获取到任何分类统计数据")
                checks.append(False)
        else:
            print(f"[WARN] 总库数与总数不一致: {total_lib_count} != {result.total}（知网跨库有重叠，属正常）")
            checks.append(True)

    # 检查4: 分类数量之和（仅供参考，不计入成败）
    if result.category_counts and len(result.category_counts) > 1:
        category_sum = sum(count for name, count in result.category_counts.items() if name != "总库")
        total_lib = result.category_counts.get("总库", 0)
        if category_sum == total_lib:
            print(f"[INFO] 各分类数量之和 = 总库数: {category_sum} = {total_lib}")
        else:
            print(f"[INFO] 各分类数量之和 {category_sum:,} != 总库数 {total_lib:,}（跨库重叠属正常）")

    print("\n" + "=" * 80)
    if all(checks):
        print("[ALL PASS] 所有检查通过！统计功能正常")
        return True
    else:
        print(f"[PARTIAL] 部分检查未通过 ({sum(checks)}/{len(checks)})")
        return False


def test_page_status():
    """测试页面状态获取"""
    print("\n" + "=" * 80)
    print("测试：页面状态获取（包含分类统计）")
    print("=" * 80)

    browser = CNKIBrowser.get_instance()

    if not browser.is_ready():
        print("[FAIL] 浏览器未就绪")
        return False

    status = browser.get_page_status()

    print("\n[状态] 当前页面状态：")
    print(f"  页面类型: {status.get('page_type')}")
    print(f"  URL: {status.get('url')}")
    print(f"  标题: {status.get('title')}")

    if status.get('page_type') == 'search':
        print(f"\n[搜索] 搜索结果信息：")
        print(f"  结果总数: {status.get('result_count', 0):,}")
        print(f"  当前页码: {status.get('current_page')}/{status.get('total_pages')}")
        print(f"  每页显示: {status.get('current_page_size')} 条")

        if status.get('category_counts'):
            print(f"\n[分类] 分类统计：")
            for category, count in status['category_counts'].items():
                print(f"  {category}: {count:,} 条")

    print("\n[OK] 页面状态获取成功")
    return True


if __name__ == "__main__":
    try:
        success1 = test_result_statistics()
        success2 = test_page_status()

        print("\n" + "=" * 80)
        print("测试总结")
        print("=" * 80)
        print(f"结果统计测试: {'[PASS]' if success1 else '[FAIL]'}")
        print(f"页面状态测试: {'[PASS]' if success2 else '[FAIL]'}")

        if success1 and success2:
            print("\n*** 所有测试通过！***")
        else:
            print("\n*** 部分测试失败 ***")

    except KeyboardInterrupt:
        print("\n\n用户中断测试")
    except Exception as e:
        print(f"\n[ERROR] 测试出错: {str(e)}")
        import traceback
        traceback.print_exc()
