# -*- coding: utf-8 -*-
"""调试：检查知网分类统计的 HTML 结构"""

import sys
import os
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from cnki_mcp.browser import CNKIBrowser
from cnki_mcp.models import CNKIQueryRequest, SearchType


def debug_category_selectors():
    browser = CNKIBrowser.get_instance()
    browser.initialize()

    # 先搜索
    request = CNKIQueryRequest(keyword="人工智能", search_type=SearchType.SU, page_size=20)
    browser.search(request)

    page = browser._page

    print("\n=== 调试分类统计选择器 ===")

    # 1. 检查 a[resource][name="classify"]
    links1 = page.locator('a[resource][name="classify"]').all()
    print(f"\n[1] a[resource][name='classify'] => 共 {len(links1)} 个")
    for i, link in enumerate(links1[:30]):
        try:
            resource = link.get_attribute("resource") or ""
            span_text = ""
            em_text = ""
            try:
                span_text = link.locator("span").first.inner_text(timeout=500).strip()
            except Exception:
                pass
            try:
                em_text = link.locator("em").first.inner_text(timeout=500).strip()
            except Exception:
                pass
            inner = link.inner_text(timeout=500).strip().replace("\n", " ")
            print(f"  [{i}] resource={resource} | span={span_text} | em={em_text} | text={inner[:40]}")
        except Exception as e:
            print(f"  [{i}] 读取失败: {e}")

    # 2. 检查 a[name="classify"]
    links2 = page.locator('a[name="classify"]').all()
    print(f"\n[2] a[name='classify'] => 共 {len(links2)} 个")
    for i, link in enumerate(links2[:30]):
        try:
            resource = link.get_attribute("resource") or ""
            data_id = link.get_attribute("data-id") or ""
            inner = link.inner_text(timeout=500).strip().replace("\n", " ")
            print(f"  [{i}] resource={resource} | data-id={data_id} | text={inner[:50]}")
        except Exception as e:
            print(f"  [{i}] 读取失败: {e}")

    # 3. 检查 .type-tab a 或类似分类导航
    for sel in [".type-tab a", ".classify-nav a", ".db-type a",
                ".nav-classify a", "ul.nav li a[resource]",
                ".search-result-classify a", "div.classify a"]:
        try:
            items = page.locator(sel).all()
            if items:
                print(f"\n[3] {sel} => 共 {len(items)} 个")
                for i, item in enumerate(items[:10]):
                    try:
                        resource = item.get_attribute("resource") or ""
                        inner = item.inner_text(timeout=500).strip().replace("\n", " ")
                        print(f"  [{i}] resource={resource} | text={inner[:50]}")
                    except Exception:
                        pass
        except Exception:
            pass

    # 4. 直接抓取页面上所有包含 em 子元素的 a 标签
    print("\n[4] 所有含 em 的 a[resource] 标签:")
    try:
        links4 = page.locator('a[resource]:has(em)').all()
        print(f"    共 {len(links4)} 个")
        for i, link in enumerate(links4[:30]):
            try:
                resource = link.get_attribute("resource") or ""
                name_attr = link.get_attribute("name") or ""
                inner = link.inner_text(timeout=500).strip().replace("\n", " ")
                print(f"  [{i}] resource={resource} | name={name_attr} | text={inner[:50]}")
            except Exception as e:
                print(f"  [{i}] 读取失败: {e}")
    except Exception as e:
        print(f"    失败: {e}")


if __name__ == "__main__":
    debug_category_selectors()

