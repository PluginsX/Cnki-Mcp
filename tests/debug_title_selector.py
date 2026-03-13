# -*- coding: utf-8 -*-
"""
调试详情页标题选择器
访问一篇已知文章，打印各候选选择器的实际内容
"""
import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

TEST_URL = (
    "https://kns.cnki.net/kcms2/article/abstract?"
    "v=esvOG1ozB-h29mfbphzpiREclFUqJtcTxgYDL4ICnoy-o4g2Zqzp8XvdQwEwQDf2X0m2nU1_Ngpc_"
    "TzYLmIWV7gDDDEBuqxYtmm-jkop59SKQhEyd4sKl4-ApotPLC9CJQ3gE0mE9tiUD7CwnLDv4Z6_Kxbx"
    "suLPjCJ1MghUP0Kou-8IbC4sJw==&uniplatform=NZKPT&language=CHS"
)

CANDIDATE_SELECTORS = [
    "h1",
    ".doc-title h1",
    ".title h1",
    ".wx-tit h1",
    ".article-title",
    ".knsTit",
    "#ChDivTitle",
    ".doc-main-info h1",
    ".doc-main-info .doc-title",
    ".title",
    "[class*='title'] h1",
    "[class*='Title'] h1",
    "div.doc h1",
    "div.main h1",
]

def main():
    from cnki_mcp.browser import CNKIBrowser
    browser = CNKIBrowser.get_instance()

    print("初始化浏览器...")
    if not browser.initialize():
        print("[FAIL] 初始化失败")
        return

    page = browser._page
    print(f"\n访问详情页...\n{TEST_URL[:80]}...\n")
    page.goto(TEST_URL, wait_until="networkidle", timeout=60000)
    browser._random_delay(2, 3)

    print("=" * 60)
    print("候选标题选择器检测结果：")
    print("=" * 60)
    for sel in CANDIDATE_SELECTORS:
        try:
            elems = page.locator(sel).all()
            if not elems:
                print(f"  {sel:<40} → 未找到元素")
                continue
            for i, elem in enumerate(elems[:3]):
                try:
                    text = elem.inner_text(timeout=2000).strip()
                    vis  = elem.is_visible(timeout=1000)
                    print(f"  {sel:<40} [{i}] vis={vis} len={len(text):3d}  '{text[:60]}'")
                except Exception as e:
                    print(f"  {sel:<40} [{i}] 读取异常: {e}")
        except Exception as e:
            print(f"  {sel:<40} → 选择器异常: {e}")

    # 额外：打印页面 <title>
    print()
    try:
        page_title = page.title()
        print(f"页面 <title>: {page_title}")
    except Exception:
        pass

    # 打印所有 h1 节点的 outerHTML
    print()
    print("所有 h1 节点的 outerHTML：")
    try:
        h1s = page.locator("h1").all()
        if not h1s:
            print("  (无 h1 节点)")
        for i, h in enumerate(h1s):
            try:
                html = h.evaluate("el => el.outerHTML")
                print(f"  [{i}] {str(html)[:200]}")
            except Exception as e:
                print(f"  [{i}] 读取失败: {e}")
    except Exception as e:
        print(f"  异常: {e}")

    # 打印 document.title 和 og:title
    print()
    print("JavaScript 元数据：")
    try:
        doc_title = page.evaluate("() => document.title")
        print(f"  document.title: {doc_title}")
    except Exception:
        pass
    try:
        og_title = page.evaluate(
            "() => { const m = document.querySelector('meta[property=\"og:title\"]'); "
            "return m ? m.content : ''; }"
        )
        print(f"  og:title meta: {og_title}")
    except Exception:
        pass
    try:
        dc_title = page.evaluate(
            "() => { const m = document.querySelector('meta[name=\"citation_title\"]'); "
            "return m ? m.content : ''; }"
        )
        print(f"  citation_title meta: {dc_title}")
    except Exception:
        pass


if __name__ == "__main__":
    main()

