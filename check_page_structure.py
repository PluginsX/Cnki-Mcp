#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
页面结构检查脚本

功能：
1. 打开知网首页
2. 检查页面中所有可能的拖拽拼图元素
3. 输出详细的页面结构信息
4. 帮助确定正确的选择器
"""

import sys
import os
import time
from src.cnki_mcp.browser import CNKIBrowser

def check_page_structure():
    """检查页面结构"""
    print("=" * 80)
    print("页面结构检查")
    print("=" * 80)
    
    browser = None
    
    try:
        # 初始化浏览器
        print("初始化浏览器...")
        browser = CNKIBrowser()
        success = browser.initialize()
        if not success:
            print("浏览器初始化失败")
            return
        
        # 打开知网首页
        print("打开知网首页...")
        browser._page.goto('https://www.cnki.net/', timeout=30000)
        
        # 等待页面加载
        time.sleep(5)
        
        # 检查页面标题
        print(f"页面标题: {browser._page.title()}")
        
        # 检查所有可能的验证相关元素
        print("\n检查验证相关元素...")
        
        # 常见的拖拽拼图选择器
        common_selectors = [
            # 知网可能的选择器
            '.verifybox',
            '.verify-wrap',
            '.slider-verify',
            '#nc_1_wrapper',  # 极验验证
            '.geetest',        # 极验验证
            '.captcha',
            '.slide-captcha',
            '.drag-captcha',
            
            # 检查所有div元素，寻找包含verify的
            'div[class*="verify"]',
            'div[class*="captcha"]',
            'div[class*="slide"]',
            'div[class*="drag"]',
        ]
        
        for selector in common_selectors:
            try:
                elements = browser._page.locator(selector)
                count = elements.count()
                if count > 0:
                    print(f"找到元素: {selector} (数量: {count})")
                    # 打印元素的HTML
                    for i in range(min(count, 3)):
                        html = elements.nth(i).inner_html()
                        print(f"  元素{i+1} HTML: {html[:200]}...")
            except Exception as e:
                print(f"检查 {selector} 时出错: {e}")
        
        # 检查所有img元素，寻找可能的拼图图片
        print("\n检查图片元素...")
        try:
            images = browser._page.locator('img')
            count = images.count()
            print(f"找到图片: {count} 张")
            for i in range(min(count, 10)):
                src = images.nth(i).get_attribute('src')
                alt = images.nth(i).get_attribute('alt')
                if src:
                    print(f"  图片{i+1}: {src}")
        except Exception as e:
            print(f"检查图片时出错: {e}")
        
        # 检查所有可拖动元素
        print("\n检查可拖动元素...")
        try:
            draggables = browser._page.locator('[draggable="true"]')
            count = draggables.count()
            if count > 0:
                print(f"找到可拖动元素: {count} 个")
                for i in range(min(count, 3)):
                    html = draggables.nth(i).inner_html()
                    print(f"  可拖动元素{i+1}: {html[:100]}...")
        except Exception as e:
            print(f"检查可拖动元素时出错: {e}")
        
        # 保存页面HTML到文件
        print("\n保存页面HTML到文件...")
        html_content = browser._page.content()
        with open('page_structure.html', 'w', encoding='utf-8') as f:
            f.write(html_content)
        print("页面HTML已保存到 page_structure.html")
        
        print("\n" + "=" * 80)
        print("页面结构检查完成")
        print("=" * 80)
        
    except Exception as e:
        print(f"检查过程中出错: {e}")
    finally:
        if browser:
            # 不关闭浏览器，让用户可以观察
            pass

def main():
    """主函数"""
    check_page_structure()

if __name__ == '__main__':
    main()
