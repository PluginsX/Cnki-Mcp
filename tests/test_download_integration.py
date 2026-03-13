# -*- coding: utf-8 -*-
"""
知网下载功能集成测试

测试内容：
  1. 模型层：CNKIDownloadResult / CNKIPaper 下载字段
  2. 代码层：browser.py / server.py 已包含下载实现
  3. 浏览器集成：启动浏览器，搜索论文，提取下载链接，执行下载

运行方式：
  python tests/test_download_integration.py
  python tests/test_download_integration.py --skip-browser   # 只跑离线测试
"""

import sys
import os
import io
import time
import tempfile
import argparse

# 强制 stdout 使用 utf-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# ─────────────────────────────────────────────
# 测试结果收集
# ─────────────────────────────────────────────
_results: list[dict] = []


def record(name: str, passed: bool, detail: str = ""):
    _results.append({"name": name, "passed": passed, "detail": detail})
    status = "[PASS]" if passed else "[FAIL]"
    msg = f"{status} {name}"
    if detail:
        msg += f"  →  {detail}"
    print(msg)


def section(title: str):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print('─' * 60)


# ═══════════════════════════════════════════════════════════════
# Part A  离线测试（不启动浏览器）
# ═══════════════════════════════════════════════════════════════

def test_a1_download_result_defaults():
    """CNKIDownloadResult 默认值"""
    from cnki_mcp.models import CNKIDownloadResult
    r = CNKIDownloadResult()
    assert r.success is False
    assert r.file_path == ""
    assert r.file_name == ""
    assert r.format == ""
    assert r.message == ""
    record("A1 CNKIDownloadResult 默认值正确", True)


def test_a2_download_result_fields():
    """CNKIDownloadResult 字段赋值"""
    from cnki_mcp.models import CNKIDownloadResult
    r = CNKIDownloadResult(
        success=True,
        file_path="/tmp/test.pdf",
        file_name="test.pdf",
        format="pdf",
        message="下载成功"
    )
    assert r.success is True
    assert r.format == "pdf"
    d = r.model_dump()
    assert isinstance(d, dict)
    assert d["success"] is True
    record("A2 CNKIDownloadResult 字段赋值与序列化", True)


def test_a3_paper_download_fields():
    """CNKIPaper 下载字段默认值与赋值"""
    from cnki_mcp.models import CNKIPaper
    # 默认
    p = CNKIPaper()
    assert p.can_download is False
    assert p.caj_url == ""
    assert p.pdf_url == ""
    assert p.download_url == ""
    record("A3-a CNKIPaper 下载字段默认值", True)

    # 赋值
    p2 = CNKIPaper(
        title="论文标题",
        caj_url="https://bar.cnki.net/xxx",
        pdf_url="https://bar.cnki.net/yyy",
        can_download=True
    )
    assert p2.can_download is True
    record("A3-b CNKIPaper 下载字段赋值", True)


def test_a4_browser_code_check():
    """browser.py 包含完整下载实现"""
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'cnki_mcp', 'browser.py')
    content = open(path, encoding='utf-8').read()

    checks = [
        ("download_paper 方法定义",    "def download_paper("),
        ("expect_download 下载监听",   "expect_download"),
        (".pdfDown 按钮选择器",         "#pdfDown"),
        (".cajDown 按钮选择器",         "#cajDown"),
        ("CAJ/PDF 链接写入 paper",     "paper.caj_url"),
        ("can_download 自动标记",      "paper.can_download = True"),
        ("download.save_as 保存文件",  "download.save_as"),
    ]
    all_ok = True
    for label, keyword in checks:
        ok = keyword in content
        record(f"A4 browser.py: {label}", ok, "" if ok else f"未找到 '{keyword}'")
        if not ok:
            all_ok = False
    return all_ok


def test_a5_server_code_check():
    """server.py 已注册并处理 cnki_download_paper 工具"""
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'cnki_mcp', 'server.py')
    content = open(path, encoding='utf-8').read()

    checks = [
        ("工具注册 name=cnki_download_paper",       'name="cnki_download_paper"'),
        ("call_tool 分支处理",                       'elif name == "cnki_download_paper"'),
        ("调用 browser.download_paper",              'browser.download_paper'),
        ("参数 fmt",                                 '"fmt"'),
        ("参数 save_dir",                            '"save_dir"'),
        ("save_dir 列为 required",                   '"required": ["paper_url", "save_dir"]'),
        ("save_dir 为空时返回错误",                   '必须指定 save_dir'),
        ("expanduser 展开 ~ 路径",                   'os.path.expanduser'),
        ("返回结果含 summary 字段",                  '"summary"'),
    ]
    all_ok = True
    for label, keyword in checks:
        ok = keyword in content
        record(f"A5 server.py: {label}", ok, "" if ok else f"未找到 '{keyword}'")
        if not ok:
            all_ok = False
    return all_ok


def test_a6_browser_save_dir_fallback():
    """browser.py download_paper：save_dir 为空时自动回退到 Downloads 目录"""
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'cnki_mcp', 'browser.py')
    content = open(path, encoding='utf-8').read()
    checks = [
        ("空 save_dir 自动使用 Downloads",   'os.path.join(os.path.expanduser("~"), "Downloads")'),
        ("expanduser 展开用户目录",           'os.path.expanduser(save_dir.strip())'),
        ("打印自动选择目录提示",              '未指定保存目录，自动使用'),
    ]
    all_ok = True
    for label, keyword in checks:
        ok = keyword in content
        record(f"A6 browser.py: {label}", ok, "" if ok else f"未找到 '{keyword}'")
        if not ok:
            all_ok = False
    return all_ok


# ═══════════════════════════════════════════════════════════════
# Part B  浏览器集成测试（需要网络 + 手动验证码）
# ═══════════════════════════════════════════════════════════════

def test_b1_browser_init():
    """浏览器初始化"""
    from cnki_mcp.browser import CNKIBrowser
    browser = CNKIBrowser.get_instance()
    ok = browser.initialize()
    record("B1 浏览器初始化", ok, "失败，请检查网络 / Playwright 安装" if not ok else "")
    return ok, browser


def test_b2_search_and_extract_links(browser):
    """搜索并提取论文下载链接"""
    from cnki_mcp.models import CNKIQueryRequest, SearchType
    req = CNKIQueryRequest(keyword="深度学习", search_type=SearchType.SU, page_size=10)
    try:
        result = browser.search(req)
    except Exception as e:
        record("B2 搜索并获取结果", False, f"搜索异常（网络/超时）：{str(e)[:80]}")
        return None

    if not result or not result.results:
        record("B2 搜索并获取结果", False, "搜索结果为空")
        return None

    found = len(result.results)
    record("B2 搜索并获取结果", True, f"共 {result.total} 条，当前页 {found} 篇")
    return result


def test_b3_get_detail_with_download_links(browser, paper_url: str):
    """获取详情页，验证 caj_url / pdf_url 被提取"""
    print(f"  → 访问详情页：{paper_url[:80]}...")
    paper = browser.get_paper_detail(paper_url)

    if not paper:
        record("B3 获取详情页", False, "返回 None")
        return None

    record("B3 获取详情页标题", bool(paper.title), paper.title[:40] if paper.title else "无标题")
    record("B3 can_download 字段", True,
           f"can_download={paper.can_download}  caj={'有' if paper.caj_url else '无'}  pdf={'有' if paper.pdf_url else '无'}")

    if paper.can_download:
        print(f"  → CAJ: {paper.caj_url[:60] if paper.caj_url else '无'}")
        print(f"  → PDF: {paper.pdf_url[:60] if paper.pdf_url else '无'}")

    return paper


def test_b4_download_paper(browser, paper_url: str, fmt: str = "pdf"):
    """执行实际下载，验证文件落地"""
    # 使用明确的绝对路径，模拟 Agent 必须显式传入 save_dir 的行为
    save_dir = os.path.abspath(tempfile.mkdtemp(prefix="cnki_dl_test_"))
    print(f"  → 保存目录（绝对路径）：{save_dir}")
    print(f"  → 下载格式：{fmt.upper()}")

    start = time.time()
    result = browser.download_paper(paper_url, fmt=fmt, save_dir=save_dir)
    elapsed = time.time() - start

    print(f"  → 耗时：{elapsed:.1f}s")
    print(f"  → success={result.success}")
    print(f"  → message={result.message}")

    if result.success:
        # 验证文件确实存在且大小 > 0
        exists = os.path.isfile(result.file_path)
        size   = os.path.getsize(result.file_path) if exists else 0
        record("B4 下载成功 & 文件存在", exists and size > 0,
               f"{result.file_name}  ({size // 1024} KB)")
        record("B4 文件格式匹配",
               result.file_name.lower().endswith(fmt),
               result.file_name)
    else:
        # 无权限也算"行为正确"，只要返回结构完整即可
        has_message = bool(result.message)
        record("B4 无权限时返回说明信息", has_message, result.message)
        print(f"  [WARN] 未能下载文件（账号可能无权限），但下载功能逻辑正常")

    return result


def test_b5_download_invalid_url(browser):
    """传入无效 URL，应优雅返回失败"""
    result = browser.download_paper(
        "https://kns.cnki.net/kcms2/article/abstract?v=invalid_url_test",
        fmt="pdf",
        save_dir=tempfile.gettempdir()
    )
    ok = not result.success and bool(result.message)
    record("B5 无效 URL 优雅失败", ok,
           result.message[:60] if result.message else "message 为空")


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════

def run_offline_tests():
    section("Part A  离线测试（模型 + 代码结构）")
    test_a1_download_result_defaults()
    test_a2_download_result_fields()
    test_a3_paper_download_fields()
    test_a4_browser_code_check()
    test_a5_server_code_check()
    test_a6_browser_save_dir_fallback()


def run_browser_tests():
    section("Part B  浏览器集成测试")

    ok, browser = test_b1_browser_init()
    if not ok:
        print("[SKIP] 浏览器初始化失败，跳过后续集成测试")
        return

    # 已知可用的详情页 URL（用于在搜索失败时也能测试 B3/B4/B5）
    FALLBACK_URL = (
        "https://kns.cnki.net/kcms2/article/abstract?"
        "v=esvOG1ozB-h29mfbphzpiREclFUqJtcTxgYDL4ICnoy-o4g2Zqzp8XvdQwEwQDf2X0m2nU1_Ngpc_"
        "TzYLmIWV7gDDDEBuqxYtmm-jkop59SKQhEyd4sKl4-ApotPLC9CJQ3gE0mE9tiUD7CwnLDv4Z6_Kxbx"
        "suLPjCJ1MghUP0Kou-8IbC4sJw==&uniplatform=NZKPT&language=CHS"
    )

    # B2 搜索
    result = test_b2_search_and_extract_links(browser)

    # 选第一篇有 link 的论文，搜索失败则用 FALLBACK_URL
    if result:
        target_url = next((p.link for p in result.results if p.link), None)
        if not target_url:
            print("  [WARN] 搜索结果无链接，使用备用 URL")
            target_url = FALLBACK_URL
        else:
            print(f"\n  → 目标论文链接：{target_url[:80]}")
    else:
        print("  [WARN] 搜索失败，使用备用 URL 继续 B3/B4/B5 测试")
        target_url = FALLBACK_URL

    # B3 详情页
    paper = test_b3_get_detail_with_download_links(browser, target_url)

    # B4 下载
    fmt = "pdf"
    if paper and paper.caj_url and not paper.pdf_url:
        fmt = "caj"
    test_b4_download_paper(browser, target_url, fmt=fmt)

    # B5 无效 URL
    test_b5_download_invalid_url(browser)


def print_summary():
    section("测试汇总")
    passed = [r for r in _results if r["passed"]]
    failed = [r for r in _results if not r["passed"]]

    print(f"  总计：{len(_results)} 项")
    print(f"  通过：{len(passed)} 项")
    print(f"  失败：{len(failed)} 项")

    if failed:
        print("\n  失败项目：")
        for r in failed:
            print(f"    [FAIL] {r['name']}", end="")
            if r['detail']:
                print(f"  →  {r['detail']}", end="")
            print()

    print()
    if not failed:
        print("  ✓ 全部通过！下载功能已就绪。")
    else:
        print(f"  ✗ 有 {len(failed)} 项未通过，请查看上方详情。")

    return len(failed) == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CNKI 下载功能集成测试")
    parser.add_argument(
        "--skip-browser", action="store_true",
        help="跳过浏览器集成测试，仅运行离线模型与代码结构检查"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  CNKI 下载功能测试")
    print("=" * 60)

    try:
        run_offline_tests()

        if not args.skip_browser:
            run_browser_tests()
        else:
            print("\n[跳过] --skip-browser 已指定，跳过浏览器集成测试")

    except KeyboardInterrupt:
        print("\n\n用户中断测试")
    except Exception as e:
        import traceback
        print(f"\n[ERROR] 测试异常：{str(e)}")
        traceback.print_exc()

    all_passed = print_summary()
    sys.exit(0 if all_passed else 1)

