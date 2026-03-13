#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试 download_paper 功能（离线单元测试，不启动浏览器）"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from cnki_mcp.models import CNKIDownloadResult


def test_download_result_model():
    """测试 CNKIDownloadResult 模型"""
    # 成功结果
    ok = CNKIDownloadResult(
        success=True,
        file_path="/tmp/paper.pdf",
        file_name="paper.pdf",
        format="pdf",
        message="下载成功"
    )
    assert ok.success is True
    assert ok.file_path == "/tmp/paper.pdf"
    assert ok.format == "pdf"
    print("[OK] CNKIDownloadResult 成功模型测试通过")

    # 失败结果
    fail = CNKIDownloadResult(
        success=False,
        format="caj",
        message="无下载权限"
    )
    assert fail.success is False
    assert fail.file_path == ""
    assert fail.file_name == ""
    print("[OK] CNKIDownloadResult 失败模型测试通过")

    # 默认值
    default = CNKIDownloadResult()
    assert default.success is False
    assert default.format == ""
    print("[OK] CNKIDownloadResult 默认值测试通过")


def test_paper_download_fields():
    """测试 CNKIPaper 模型中的下载字段"""
    from cnki_mcp.models import CNKIPaper
    paper = CNKIPaper(
        title="测试论文",
        caj_url="https://bar.cnki.net/bar/download/order?...",
        pdf_url="https://bar.cnki.net/bar/download/order?...&format=PDF",
        can_download=True
    )
    assert paper.can_download is True
    assert "bar.cnki.net" in paper.caj_url
    assert "bar.cnki.net" in paper.pdf_url
    print("[OK] CNKIPaper 下载字段测试通过")

    paper_no_dl = CNKIPaper(title="无下载链接论文")
    assert paper_no_dl.can_download is False
    assert paper_no_dl.caj_url == ""
    assert paper_no_dl.pdf_url == ""
    print("[OK] CNKIPaper 无下载链接默认值测试通过")


def test_server_tool_list():
    """验证 server.py 中已注册 cnki_download_paper 工具"""
    server_path = os.path.join(
        os.path.dirname(__file__), '..', 'src', 'cnki_mcp', 'server.py'
    )
    with open(server_path, encoding='utf-8') as f:
        content = f.read()

    assert 'cnki_download_paper' in content, \
        "server.py 中未找到 cnki_download_paper 工具注册"
    print("[OK] server.py 中已注册 cnki_download_paper 工具")

    # 检查 call_tool 中的处理分支
    assert 'elif name == "cnki_download_paper"' in content, \
        "server.py 中未找到 cnki_download_paper 处理分支"
    print("[OK] server.py 中已有 cnki_download_paper 处理分支")


def test_browser_has_download_method():
    """验证 browser.py 中存在 download_paper 方法"""
    browser_path = os.path.join(
        os.path.dirname(__file__), '..', 'src', 'cnki_mcp', 'browser.py'
    )
    with open(browser_path, encoding='utf-8') as f:
        content = f.read()

    assert 'def download_paper(' in content, \
        "browser.py 中未找到 download_paper 方法"
    print("[OK] browser.py 中已定义 download_paper 方法")

    assert 'expect_download' in content, \
        "browser.py 中未找到 expect_download（Playwright 下载监听）"
    print("[OK] browser.py 中使用了 expect_download 监听下载事件")

    assert '#cajDown' in content and '#pdfDown' in content, \
        "browser.py 中未找到 #cajDown / #pdfDown 选择器"
    print("[OK] browser.py 中已有 CAJ/PDF 按钮选择器")


if __name__ == "__main__":
    print("=" * 55)
    print("  测试 download_paper 功能（静态代码验证）")
    print("=" * 55)

    tests = [
        test_download_result_model,
        test_paper_download_fields,
        test_server_tool_list,
        test_browser_has_download_method,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {t.__name__}: {e}")
            failed += 1

    print()
    print(f"结果：{passed} 通过 / {failed} 失败")
    if failed == 0:
        print("全部测试通过！下载功能已就绪。")
    sys.exit(0 if failed == 0 else 1)

