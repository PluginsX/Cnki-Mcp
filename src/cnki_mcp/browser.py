"""知网浏览器自动化模块 - 单例模式，保持会话"""

import time
import random
import atexit
import sys
import re
from typing import Optional
from threading import Lock

from playwright.sync_api import sync_playwright, Browser, Page, TimeoutError, Playwright

from .models import CNKIQueryRequest, CNKIQueryResult, CNKIPaper, SEARCH_TYPE_NAMES, SearchType, PageState, InitState
from .config import ConfigManager, get_captcha

# 尝试导入自动验证模块，失败时不影响主功能
try:
    from .AutomaticVerification import auto_verify_with_retry
except ImportError:
    auto_verify_with_retry = None


def safe_print(msg: str):
    try:
        print(msg, flush=True)  # 强制刷新缓冲区
        sys.stderr.write(msg + '\n')  # 同时输出到 stderr
        sys.stderr.flush()
    except UnicodeEncodeError:
        # 替换 Unicode 符号为 ASCII 等价物
        msg_safe = msg.replace('✓', '[OK]').replace('✗', '[FAIL]').replace('•', '-').replace('→', '->').replace('⚠', '[!]')
        try:
            print(msg_safe, flush=True)
            sys.stderr.write(msg_safe + '\n')
            sys.stderr.flush()
        except UnicodeEncodeError:
            # 最后的手段：只保留 ASCII 字符
            msg_ascii = msg_safe.encode('ascii', errors='replace').decode('ascii')
            print(msg_ascii, flush=True)
            sys.stderr.write(msg_ascii + '\n')
            sys.stderr.flush()


class CNKIBrowser:
    BASE_URL = "https://kns.cnki.net/"
    SEARCH_URL = "https://kns.cnki.net/kns8s/search"
    
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    
    ANTI_DETECT_SCRIPT = """
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined
    })
    """

    CAPTCHA_SELECTORS = [
        # 腾讯云验证码选择器（知网新版）
        ".tencent-captcha-dy__container",
        # 旧版知网验证码选择器
        ".verifybox",
        ".verify-img-panel",
        ".verify-sub-block",
        ".verify-move-block",
        # 拼图验证码选择器
        ".security-verify",
        "#verify-code",
        ".puzzle-verify",
        ".verify-dialog",
        # 通用验证码选择器
        ".verify-wrap",
        ".slider-verify",
        ".geetest",
        "#nc_1_wrapper",
        ".captcha",
        ".verify-box",
        "iframe[src*='captcha']",
        "iframe[src*='verify']",
        ".nc-container",
        "#nc_1",
        ".slide-verify",
        ".slider",
    ]

    _instance: Optional['CNKIBrowser'] = None
    _initialized: bool = False
    
    # 类级别的初始化状态管理
    _init_state: InitState = InitState.NOT_STARTED
    _init_lock = Lock()  # 线程锁，防止并发初始化

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if CNKIBrowser._initialized:
            return
        CNKIBrowser._initialized = True
        
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
        self._ready: bool = False
        
        atexit.register(self._cleanup)

    @classmethod
    def get_instance(cls) -> 'CNKIBrowser':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _init_browser(self) -> Page:
        if self._page and self._browser:
            try:
                self._page.evaluate("1")
                return self._page
            except Exception:
                self._cleanup()

        safe_print("    [DEBUG] 读取配置...")
        # 从配置文件读取参数
        config = ConfigManager.get_instance()
        slow_mo = config.get_delay('browser_slow_mo', 100)
        viewport_width = config.get_optimization('viewport_width', 1920)
        viewport_height = config.get_optimization('viewport_height', 1080)
        page_timeout = config.get_timeout('page_goto_timeout', 60000)
        headless = config.get_optimization('enable_headless', False)

        safe_print("    [DEBUG] 启动 Playwright...")
        self._playwright = sync_playwright().start()
        
        safe_print("    [DEBUG] 启动 Chromium...")
        self._browser = self._playwright.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ],
            slow_mo=slow_mo
        )
        
        safe_print("    [DEBUG] 创建浏览器上下文...")
        context = self._browser.new_context(
            user_agent=self.USER_AGENT,
            viewport={"width": viewport_width, "height": viewport_height}
        )
        
        safe_print("    [DEBUG] 注入反检测脚本...")
        context.add_init_script(self.ANTI_DETECT_SCRIPT)
        
        safe_print("    [DEBUG] 创建新页面...")
        self._page = context.new_page()
        self._page.set_default_timeout(page_timeout)
        
        safe_print("    [DEBUG] 浏览器初始化完成")
        return self._page

    def _random_delay(self, min_sec: float = None, max_sec: float = None):
        """随机延迟，支持从配置文件读取默认值"""
        if min_sec is None:
            config = ConfigManager.get_instance()
            min_sec = config.get_delay('random_delay_min', 0.5)
        if max_sec is None:
            config = ConfigManager.get_instance()
            max_sec = config.get_delay('random_delay_max', 2.0)
        time.sleep(random.uniform(min_sec, max_sec))

    def _check_captcha(self, page: Page) -> bool:
        """检测页面是否出现验证码
        
        Returns:
            bool: 是否检测到验证码
        """
        # 快速检查：先用 count() 判断元素是否存在（不等待）
        for selector in self.CAPTCHA_SELECTORS:
            try:
                count = page.locator(selector).count()
                if count > 0:
                    # 元素存在，再检查是否可见
                    try:
                        elem = page.locator(selector).first
                        if elem.is_visible(timeout=500):
                            safe_print(f"[验证码检测] 发现验证码元素: {selector}")
                            return True
                    except Exception:
                        # 即使不可见，只要元素存在就认为有验证码
                        safe_print(f"[验证码检测] 发现验证码元素（可能隐藏）: {selector}")
                        return True
            except Exception:
                continue
        
        return False

    def _wait_for_captcha(self, page: Page, max_wait: int = 0):
        """等待并处理验证码
        
        Args:
            page: Playwright 页面对象
            max_wait: 最大等待时间（秒），0 表示无限等待
            
        Returns:
            bool: 验证是否成功
        """
        # 检查是否启用自动验证
        auto_verify_enabled = get_captcha('auto_verify', False)
        safe_print(f"[验证码处理] auto_verify_enabled: {auto_verify_enabled}")
        safe_print(f"[验证码处理] auto_verify_with_retry 可用: {auto_verify_with_retry is not None}")
        
        if auto_verify_enabled and auto_verify_with_retry:
            safe_print("\n" + "=" * 60)
            safe_print("[!] 检测到安全验证（拼图验证码）")
            safe_print("[*] 启用自动验证模式")
            safe_print("=" * 60)
            
            # 获取自动验证配置
            max_retry = get_captcha('max_retry', 3)
            drag_duration = get_captcha('drag_duration', 1.0)
            verify_method = get_captcha('verify_method', 'iou')
            
            safe_print(f"\n    自动验证配置：")
            safe_print(f"    - 最大重试次数: {max_retry}")
            safe_print(f"    - 拖拽时长: {drag_duration}秒")
            safe_print(f"    - 验证方法: {verify_method}")
            safe_print("\n    正在进行自动验证...")
            safe_print("=" * 60 + "\n")
            
            # 等待验证码完全加载
            safe_print("[自动验证] 等待验证码元素完全加载...")
            
            # 执行自动验证
            try:
                success = auto_verify_with_retry(
                    page=page,
                    max_retry=max_retry,
                    method=verify_method,
                    drag_duration=drag_duration
                )
                
                if success:
                    safe_print("\n[OK] 自动验证成功！\n")
                    return True
                else:
                    safe_print("\n[X] 自动验证失败，切换到手动验证模式\n")
            except Exception as e:
                safe_print(f"\n[X] 自动验证过程出错：{str(e)}")
                safe_print("[*] 切换到手动验证模式\n")
                import traceback
                traceback.print_exc()
        else:
            if not auto_verify_enabled:
                safe_print("[验证码处理] 自动验证未启用（配置文件 captcha.auto_verify = false）")
            if auto_verify_with_retry is None:
                safe_print("[验证码处理] 自动验证模块导入失败")
        
        # 手动验证模式
        config = ConfigManager.get_instance()
        check_interval = config.get_delay('captcha_check_interval', 1.0)
        wait_after_complete_min = config.get_delay('captcha_wait_after_complete_min', 2.0)
        wait_after_complete_max = config.get_delay('captcha_wait_after_complete_max', 3.0)
        
        safe_print("\n" + "=" * 60)
        safe_print("[!] 检测到安全验证（拼图验证码）")
        safe_print("[*] 手动验证模式")
        safe_print("=" * 60)
        safe_print("\n    请在浏览器窗口中完成以下操作：")
        safe_print("    1. 拖动滑块完成拼图验证")
        safe_print("    2. 等待页面自动跳转")
        safe_print("\n    等待验证完成中...（无时间限制）")
        safe_print("=" * 60 + "\n")
        
        wait_count = 0
        while True:
            if not self._check_captcha(page):
                safe_print("[OK] 验证完成！\n")
                self._random_delay(wait_after_complete_min, wait_after_complete_max)
                return True
            time.sleep(check_interval)
            wait_count += 1
            if wait_count % 10 == 0:
                safe_print(f"    等待验证中... 已等待 {wait_count * check_interval:.0f} 秒")
        
        return False

    def initialize(self) -> bool:
        """初始化浏览器（带锁保护，防止重复初始化）"""
        
        # 快速路径：如果已完成，直接返回
        if CNKIBrowser._init_state == InitState.COMPLETED and self._ready:
            return True
        
        # 如果正在初始化中，返回 False（让调用者等待）
        if CNKIBrowser._init_state == InitState.IN_PROGRESS:
            safe_print("⏳ 初始化正在进行中，请稍候...")
            return False
        
        # 获取锁，防止并发初始化
        with CNKIBrowser._init_lock:
            # 双重检查（可能在等待锁期间已完成）
            if CNKIBrowser._init_state == InitState.COMPLETED and self._ready:
                return True
            
            if CNKIBrowser._init_state == InitState.IN_PROGRESS:
                return False
            
            # 标记为初始化中
            CNKIBrowser._init_state = InitState.IN_PROGRESS
            
            try:
                safe_print("\n" + "=" * 60)
                safe_print("[*] 初始化知网检索服务")
                safe_print("=" * 60)
                safe_print("\n    [1/6] 正在启动浏览器...")

                page = self._init_browser()
                safe_print("    [OK] 浏览器启动成功")

                config = ConfigManager.get_instance()
                page_goto_timeout = config.get_timeout('page_goto_timeout', 60000)
                page_load_wait_min = config.get_delay('page_load_wait', 2.0)
                page_load_wait_max = page_load_wait_min + 1.0

                safe_print("    [2/6] 正在打开知网首页...")
                safe_print(f"    URL: {self.BASE_URL}")
                page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=page_goto_timeout)
                safe_print("    [OK] 页面加载完成")
                
                # 等待 1 秒让页面渲染
                safe_print("    [3/6] 等待页面渲染（1秒）...")
                time.sleep(1)
                safe_print("    [OK] 等待完成")
                
                # 立即开始寻找验证码
                safe_print("    [4/6] 开始寻找验证码...")
                captcha_found = False
                for check_attempt in range(5):
                    safe_print(f"    检查 {check_attempt + 1}/5...")
                    if self._check_captcha(page):
                        captcha_found = True
                        safe_print("\n    [!] 发现验证码！立即启动自动验证...")
                        if not self._wait_for_captcha(page):
                            safe_print("    [X] 初始化失败：验证超时")
                            CNKIBrowser._init_state = InitState.FAILED
                            return False
                        safe_print("    [OK] 验证完成，继续初始化...")
                        time.sleep(2)
                        break
                    else:
                        safe_print(f"    第 {check_attempt + 1} 次：未发现验证码")
                        if check_attempt < 4:
                            time.sleep(1)
                
                if not captcha_found:
                    safe_print("    [OK] 未检测到验证码，继续初始化...")
                
                # 等待搜索框出现
                safe_print("    [5/6] 等待搜索框出现...")
                try:
                    page.wait_for_selector("#txt_search, input.search-input, #txt_SearchText", state="visible", timeout=10000)
                    safe_print("    [OK] 搜索框已出现")
                except Exception as e:
                    safe_print(f"    [!] 警告：搜索框未出现 ({e})")
                    time.sleep(2)

                max_attempts = 5
                safe_print("    [6/6] 最后检查...")
                for attempt in range(max_attempts):
                    # 最后再检查一次验证码
                    if self._check_captcha(page):
                        safe_print("\n    [!] 再次检测到验证码...")
                        if not self._wait_for_captcha(page):
                            safe_print("    [X] 初始化失败：验证超时")
                            CNKIBrowser._init_state = InitState.FAILED
                            return False
                        time.sleep(2)
                        continue

                    try:
                        search_input = page.locator("input[type='text'], input.search-input, #txt_SearchText, .search-input").first
                        if search_input and search_input.is_visible(timeout=3000):
                            safe_print("    [OK] 页面加载成功，检测到搜索框")
                            break
                    except Exception:
                        pass

                    if attempt < max_attempts - 1:
                        safe_print(f"    等待页面加载... ({attempt + 1}/{max_attempts})")
                        time.sleep(2)
                        if self._check_captcha(page):
                            safe_print("\n    [!] 检测到安全验证，请完成验证...")
                            if not self._wait_for_captcha(page):
                                safe_print("    [X] 初始化失败：验证超时")
                                CNKIBrowser._init_state = InitState.FAILED
                                return False
                            time.sleep(2)

                try:
                    page.wait_for_load_state("domcontentloaded", timeout=5000)
                except Exception:
                    pass

                self._ready = True
                CNKIBrowser._init_state = InitState.COMPLETED

                safe_print("\n" + "=" * 60)
                safe_print("[OK] 知网检索服务初始化完成！")
                safe_print("    浏览器窗口将保持打开，后续查询将复用此会话")
                safe_print("=" * 60 + "\n")
                return True

            except Exception as e:
                safe_print(f"    [X] 初始化失败：{str(e)}")
                import traceback
                traceback.print_exc()
                CNKIBrowser._init_state = InitState.FAILED
                return False

    def is_ready(self) -> bool:
        return self._ready and self._page is not None

    def _reset_on_timeout(self):
        """超时后的浏览器状态恢复机制"""
        safe_print("[RECOVERY] 尝试恢复浏览器状态...")
        try:
            if not self._page:
                return
            
            # 1. 关闭所有可见的弹窗
            try:
                self._page.evaluate("""
                    () => {
                        document.querySelectorAll('[class*=close], [class*=Close], .layui-layer-close').forEach(el => {
                            try { el.click(); } catch(e) {}
                        });
                    }
                """)
                safe_print("  已关闭弹窗")
            except Exception:
                pass
            
            # 2. 回到首页
            try:
                self._page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=10000)
                self._random_delay(2, 3)
                safe_print("  已回到首页")
            except Exception as e:
                safe_print(f"  回到首页失败：{e}")
            
            safe_print("[RECOVERY] 浏览器状态已重置")
        except Exception as e:
            safe_print(f"[RECOVERY_ERROR] 恢复过程异常：{e}")

    # ==================== 状态感知方法 ====================
    
    def _get_current_page_type(self) -> PageState:
        """通过URL判断当前页面类型"""
        if not self._page:
            return PageState.UNKNOWN
        
        try:
            url = self._page.url
            if "kns8s/defaultresult" in url or "kns8s/search" in url:
                return PageState.SEARCH_RESULT
            elif "kcms/detail" in url or "kcms2/article" in url:
                return PageState.PAPER_DETAIL
            elif "kns.cnki.net" in url and url.count('/') <= 3:
                return PageState.HOME
        except Exception:
            pass
        
        return PageState.UNKNOWN
    
    def _extract_result_count(self) -> int:
        """提取搜索结果总数（从知网页面直接获取）"""
        try:
            # 方法1: 从 pagerTitleCell 提取 "共找到 671 条结果"
            elem = self._page.locator("span.pagerTitleCell em").first
            if elem and elem.is_visible(timeout=2000):
                text = elem.inner_text().strip()
                count = int(text.replace(',', ''))
                safe_print(f"从页面标题获取结果总数: {count}")
                return count
        except Exception as e:
            safe_print(f"方法1失败: {str(e)}")
        
        try:
            # 方法2: 从 pagerTitleCell 的完整文本提取
            elem = self._page.locator("span.pagerTitleCell").first
            if elem and elem.is_visible(timeout=2000):
                text = elem.inner_text()
                # 提取 "共找到 1,557 条结果" 中的数字
                match = re.search(r'(\d+(?:,\d+)*)', text)
                if match:
                    count = int(match.group(1).replace(',', ''))
                    safe_print(f"从页面标题文本获取结果总数: {count}")
                    return count
        except Exception as e:
            safe_print(f"方法2失败: {str(e)}")
        
        safe_print("警告：无法获取结果总数，返回0")
        return 0
    
    def _extract_category_counts(self) -> dict[str, int]:
        """提取各分类的结果数量
        
        知网页面上数字有两种格式：
          - 纯数字：如 "7429"
          - 万为单位：如 "24.98万"、"41.20万"
        同一 resource 会出现多次（父级 + 子级展开），
        只保留每个 resource 的第一条（即顶级分类）。
        使用 evaluate() 在浏览器端一次性批量提取，避免串行 IPC 调用。
        
        Returns:
            dict: 分类名称 -> 结果数量的映射（去重后，按页面顺序）
        """
        try:
            raw = self._page.evaluate("""
                () => {
                    const results = [];
                    const seen = new Set();
                    const links = document.querySelectorAll('a[resource][name="classify"]');
                    for (const link of links) {
                        const resource = link.getAttribute('resource') || '';
                        if (!resource || seen.has(resource)) continue;
                        seen.add(resource);
                        const span = link.querySelector('span');
                        const em = link.querySelector('em');
                        if (!span || !em) continue;
                        const name = span.textContent.trim();
                        const emText = em.textContent.trim();
                        if (!name || !emText) continue;
                        results.push([name, emText]);
                    }
                    return results;
                }
            """)
        except Exception as e:
            safe_print(f"提取分类统计失败: {str(e)}")
            return {}

        def parse_count(text: str) -> int:
            text = text.strip().replace(',', '')
            if not text:
                return -1
            if '万' in text:
                num_str = text.replace('万', '').strip()
                try:
                    return int(float(num_str) * 10000)
                except ValueError:
                    return -1
            try:
                return int(text)
            except ValueError:
                return -1

        category_counts = {}
        for name, em_text in (raw or []):
            count = parse_count(em_text)
            if count >= 0:
                category_counts[name] = count
                safe_print(f"  {name}: {count}")

        return category_counts
    
    def _extract_page_info(self) -> tuple[int, int]:
        """提取当前页码和总页数"""
        try:
            # 方法1: 从 span.countPageMark 提取 "1/78"
            elem = self._page.locator("span.countPageMark").first
            if elem and elem.is_visible(timeout=2000):
                text = elem.inner_text()
                match = re.search(r'(\d+)/(\d+)', text)
                if match:
                    return int(match.group(1)), int(match.group(2))
        except Exception:
            pass
        
        try:
            # 方法2: 从分页按钮推断 - 当前页用 class="cur"
            cur_link = self._page.locator("div.pagesnums a.cur[data-curpage]").first
            if cur_link and cur_link.is_visible(timeout=1000):
                cur = int(cur_link.get_attribute("data-curpage") or "1")
                # 总页数取最后一个 data-curpage
                all_links = self._page.locator("div.pagesnums a[data-curpage]").all()
                pages = []
                for lnk in all_links:
                    try:
                        val = lnk.get_attribute("data-curpage")
                        if val:
                            pages.append(int(val))
                    except Exception:
                        pass
                total = max(pages) if pages else cur
                return cur, total
        except Exception:
            pass
        
        return 1, 1
    
    def _wait_for_page_loaded(self, timeout: int = 10000) -> bool:
        """等待搜索结果页加载完成（区分「有结果」和「无结果」，不等超时）
        
        特别处理：
        - 结果数为 '0' → 视为无结果
        - 结果数为 'undefined' / 空字符串 → 视为已加载但无有效结果，按 0 条处理
        """
        # 同时等待"有结果"或"无结果提示"，任意一个出现即返回，避免傻等超时
        RESULT_SELECTOR = "table.result-table-list tbody tr"
        NO_RESULT_SELECTORS = [
            "p.no-content",          # 知网真实无结果提示：<p class="no-content">抱歉，暂无数据...</p>
            ".tips-nodata",
            ".no-result",
            ".kns-result-none",
            "p.tips",
            "span.pagerTitleCell em",  # 结果数为0时也会出现
        ]
        try:
            # 先等待分页标题（几乎总会出现，有结果和无结果都会出现）
            self._page.wait_for_selector(
                "span.pagerTitleCell",
                state="visible",
                timeout=timeout
            )
            # 检查结果数是否为0（快速路径：无结果直接返回True，表示页面已加载完成）
            try:
                em = self._page.locator("span.pagerTitleCell em").first
                if em.is_visible(timeout=500):
                    count_text = em.inner_text(timeout=500).strip().replace(',', '')
                    # '0' = 确认 0 条；空字符串 / 'undefined' 也按 0 条处理，避免长时间等待
                    if count_text in ('0', '', 'undefined', 'null', '-'):
                        safe_print(f"[无结果] 知网结果计数异常/为0（{count_text!r}），视为0条结果，页面已加载完成")
                        return True
            except Exception:
                pass
        except Exception:
            pass

        # 等待结果行出现
        try:
            self._page.wait_for_selector(
                RESULT_SELECTOR,
                state="visible",
                timeout=timeout
            )
            return True
        except Exception:
            pass

        # 备用：检查是否有「无结果」提示元素（说明页面已加载完成，只是没有数据）
        for sel in NO_RESULT_SELECTORS:
            try:
                if self._page.locator(sel).first.is_visible(timeout=500):
                    safe_print(f"[无结果] 检测到无结果提示元素：{sel}")
                    return True
            except Exception:
                continue

        # 最后备用：等待任意结果行
        try:
            self._page.wait_for_selector("tbody tr", state="visible", timeout=3000)
            return True
        except Exception:
            return False
    
    def get_page_status(self) -> dict:
        """获取当前页面完整状态
        
        Returns:
            dict: 页面状态信息
        """
        if not self.is_ready():
            return {"error": "浏览器未初始化"}
        
        page_type = self._get_current_page_type()
        status = {
            "page_type": page_type.value,
            "url": self._page.url,
            "title": self._page.title(),
            "is_loading": False,
            "has_error": False,
        }
        
        # 如果是搜索结果页，提取详细信息
        if page_type == PageState.SEARCH_RESULT:
            status["result_count"] = self._extract_result_count()
            current_page, total_pages = self._extract_page_info()
            status["current_page"] = current_page
            status["total_pages"] = total_pages
            
            # 获取当前每页显示数量
            status["current_page_size"] = self.get_current_page_size()
            
            # 获取分类统计
            status["category_counts"] = self._extract_category_counts()
            
            # 检测当前搜索类型
            try:
                sort_default = self._page.locator("div.sort-default span").first
                if sort_default and sort_default.is_visible(timeout=1000):
                    status["search_type"] = sort_default.get_attribute("title") or ""
            except Exception:
                status["search_type"] = ""
            
            # 检测当前筛选条件
            try:
                active_filter = self._page.locator("a[resource].active, a[resource].cur").first
                if active_filter and active_filter.is_visible(timeout=1000):
                    status["filter_active"] = active_filter.get_attribute("resource") or ""
                else:
                    status["filter_active"] = ""
            except Exception:
                status["filter_active"] = ""
        
        return status
    
    # ==================== 导航控制方法 ====================
    
    def get_current_page_size(self) -> int:
        """获取当前每页显示数量
        
        Returns:
            int: 当前每页显示数量（10/20/50），默认10
        """
        if self._get_current_page_type() != PageState.SEARCH_RESULT:
            return 10
        
        try:
            elem = self._page.locator("#perPageDiv .sort-default span").first
            if elem and elem.is_visible(timeout=2000):
                text = elem.inner_text().strip()
                page_size = int(text)
                if page_size in [10, 20, 50]:
                    return page_size
        except Exception:
            pass
        
        return 10  # 默认值
    
    def set_page_size(self, page_size: int) -> bool:
        """设置每页显示数量
        
        Args:
            page_size: 每页显示数量（10/20/50）
            
        Returns:
            bool: 是否设置成功
        """
        if page_size not in [10, 20, 50]:
            safe_print(f"错误：page_size 必须是 10、20 或 50，当前值：{page_size}")
            return False
        
        if self._get_current_page_type() != PageState.SEARCH_RESULT:
            safe_print("错误：当前不在搜索结果页，无法设置每页显示数量")
            return False
        
        # 检查是否已经是目标值
        current_size = self.get_current_page_size()
        if current_size == page_size:
            safe_print(f"当前已经是每页显示 {page_size} 条，无需修改")
            return True
        
        config = ConfigManager.get_instance()
        dropdown_delay_min = config.get_delay('dropdown_delay_min', 0.5)
        dropdown_delay_max = config.get_delay('dropdown_delay_max', 1.0)
        option_click_delay_min = config.get_delay('option_click_delay_min', 1.0)
        option_click_delay_max = config.get_delay('option_click_delay_max', 2.0)
        page_size_change_delay_min = config.get_delay('page_size_change_delay_min', 3.0)
        page_size_change_delay_max = config.get_delay('page_size_change_delay_max', 5.0)
        
        try:
            safe_print(f"正在设置每页显示数量：{current_size} → {page_size}...")
            
            # 1. 点击下拉菜单
            dropdown = self._page.locator("#perPageDiv .sort-default").first
            if not dropdown or not dropdown.is_visible(timeout=2000):
                safe_print("未找到每页显示数量下拉菜单")
                return False
            
            dropdown.click()
            self._random_delay(dropdown_delay_min, dropdown_delay_max)
            safe_print("已打开下拉菜单")
            
            # 2. 选择对应数量
            option = self._page.locator(f"#perPageDiv ul.sort-list li[data-val='{page_size}'] a").first
            if not option or not option.is_visible(timeout=2000):
                safe_print(f"未找到选项：{page_size}")
                return False
            
            option.click()
            safe_print(f"已点击选项：{page_size}")
            
            # 3. 等待页面重新加载：优先用 wait_for_selector，而非固定睡眠
            try:
                self._page.wait_for_selector(
                    "table.result-table-list tbody tr",
                    state="visible",
                    timeout=int(page_size_change_delay_max * 1000 * 3)
                )
            except Exception:
                self._random_delay(page_size_change_delay_min, page_size_change_delay_max)
            
            # 4. 验证设置是否成功
            new_size = self.get_current_page_size()
            if new_size == page_size:
                safe_print(f"成功设置每页显示 {page_size} 条")
                return True
            
            # 备用验证：检查实际结果行数
            try:
                row_count = self._page.locator("tbody tr").count()
                if row_count > 0:
                    safe_print(f"页面已加载（{row_count} 行），视为设置成功")
                    return True
            except Exception:
                pass
            
            safe_print(f"设置后验证失败：期望 {page_size}，实际 {new_size}")
            return False
            
        except Exception as e:
            safe_print(f"设置每页显示数量失败：{str(e)}")
            return False
    
    def next_page(self) -> bool:
        """跳转到下一页
        
        Returns:
            bool: 是否成功跳转
        """
        if self._get_current_page_type() != PageState.SEARCH_RESULT:
            safe_print("错误：当前不在搜索结果页")
            return False
        
        try:
            # 获取当前页码
            current_page, total_pages = self._extract_page_info()
            safe_print(f"当前页码: {current_page}/{total_pages}")
            
            if current_page >= total_pages:
                safe_print(f"已经是最后一页 ({current_page}/{total_pages})")
                return False
            
            # 查找下一页按钮（真实选择器: #PageNext）
            next_btn = self._page.locator("#PageNext").first
            if not next_btn or not next_btn.is_visible(timeout=3000):
                # 备用：data-curpage 指向下一页的链接
                next_btn = self._page.locator(f"a[data-curpage='{current_page + 1}']").first
                if not next_btn or not next_btn.is_visible(timeout=2000):
                    safe_print("未找到下一页按钮")
                    return False
            
            # 检查按钮是否被禁用
            btn_class = next_btn.get_attribute("class") or ""
            if "disabled" in btn_class or "disable" in btn_class:
                safe_print("下一页按钮已禁用")
                return False
            
            safe_print(f"正在跳转到第 {current_page + 1} 页...")
            
            # 点击按钮
            next_btn.click()
            safe_print("已点击下一页按钮")
            
            # 等待新页面加载完成（事件驱动，不固定睡眠）
            safe_print("等待页面加载...")
            if self._wait_for_page_loaded(timeout=20000):
                new_page, _ = self._extract_page_info()
                safe_print(f"加载后页码: {new_page}/{total_pages}")
                
                if new_page == current_page + 1:
                    safe_print(f"成功跳转到第 {new_page} 页")
                    return True
                elif new_page == current_page:
                    # 页码未变化，短暂等待后重试读取
                    self._random_delay(1, 2)
                    new_page, _ = self._extract_page_info()
                    if new_page == current_page + 1:
                        safe_print(f"成功跳转到第 {new_page} 页")
                        return True
                    safe_print(f"警告：页码未变化，可能翻页失败")
                    return False
                else:
                    safe_print(f"警告：页码异常（期望{current_page + 1}，实际{new_page}）")
                    return False
            else:
                safe_print("页面加载超时")
                return False
            
        except Exception as e:
            safe_print(f"翻页失败：{str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def prev_page(self) -> bool:
        """跳转到上一页
        
        Returns:
            bool: 是否成功跳转
        """
        if self._get_current_page_type() != PageState.SEARCH_RESULT:
            safe_print("错误：当前不在搜索结果页")
            return False
        
        try:
            # 获取当前页码
            current_page, total_pages = self._extract_page_info()
            safe_print(f"当前页码: {current_page}/{total_pages}")
            
            if current_page <= 1:
                safe_print("已经是第一页")
                return False
            
            # 查找上一页按钮（用 data-curpage 定位前一页）
            prev_btn = self._page.locator(f"a[data-curpage='{current_page - 1}']").first
            if not prev_btn or not prev_btn.is_visible(timeout=3000):
                # 备用：id=PagePrev
                prev_btn = self._page.locator("#PagePrev").first
                if not prev_btn or not prev_btn.is_visible(timeout=2000):
                    safe_print("未找到上一页按钮")
                    return False
            
            # 检查按钮是否被禁用
            btn_class = prev_btn.get_attribute("class") or ""
            if "disabled" in btn_class or "disable" in btn_class:
                safe_print("上一页按钮已禁用")
                return False
            
            safe_print(f"正在跳转到第 {current_page - 1} 页...")
            
            # 点击按钮
            prev_btn.click()
            safe_print("已点击上一页按钮")
            
            # 等待新页面加载完成（事件驱动，不固定睡眠）
            safe_print("等待页面加载...")
            if self._wait_for_page_loaded(timeout=20000):
                new_page, _ = self._extract_page_info()
                safe_print(f"加载后页码: {new_page}/{total_pages}")
                
                if new_page == current_page - 1:
                    safe_print(f"✓ 成功跳转到第 {new_page} 页")
                    return True
                elif new_page == current_page:
                    # 页码未变化，短暂等待后重试
                    self._random_delay(1, 2)
                    new_page, _ = self._extract_page_info()
                    if new_page == current_page - 1:
                        safe_print(f"✓ 成功跳转到第 {new_page} 页")
                        return True
                    safe_print(f"警告：页码未变化，可能翻页失败")
                    return False
                else:
                    safe_print(f"警告：页码异常（期望{current_page - 1}，实际{new_page}）")
                    return False
            else:
                safe_print("页面加载超时")
                return False
            
        except Exception as e:
            safe_print(f"翻页失败：{str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def switch_search_type(self, page: Page, search_type: SearchType) -> bool:
        """切换搜索类型
        
        Args:
            page: Playwright 页面对象
            search_type: 要切换到的搜索类型
            
        Returns:
            bool: 是否成功切换
        """
        if search_type == SearchType.SU:
            return True  # 默认就是主题搜索，不需要切换
            
        safe_print(f"正在切换搜索类型到：{SEARCH_TYPE_NAMES.get(search_type, search_type.value)}...")
        
        try:
            type_dropdown = page.locator(".sort-default span").first
            if not type_dropdown or not type_dropdown.is_visible(timeout=2000):
                safe_print("警告：未找到搜索类型下拉菜单")
                return False
            
            type_dropdown.click()
            self._random_delay(1, 2)
            safe_print("已打开搜索类型下拉菜单")
            
            type_option = page.locator(f"li[data-val='{search_type.value}'] a").first
            if type_option and type_option.is_visible(timeout=2000):
                type_option.click()
                safe_print(f"已选择：{SEARCH_TYPE_NAMES.get(search_type)}")
                self._random_delay(1, 2)
                return True
            
            safe_print(f"警告：未找到 {SEARCH_TYPE_NAMES.get(search_type)} 选项")
            return False
            
        except Exception as e:
            safe_print(f"切换搜索类型失败：{str(e)}")
            return False
    
    def filter_by_resource(self, page: Page, resource_type: str) -> bool:
        """按资源类型筛选搜索结果
        
        Args:
            page: Playwright 页面对象
            resource_type: 资源类型，如 "DISSERTATION"(学位论文), "JOURNAL"(期刊), 
                          "CONFERENCE"(会议), "NEWSPAPER"(报纸) 等
            
        Returns:
            bool: 是否成功筛选
        """
        resource_names = {
            "DISSERTATION": "学位论文",
            "JOURNAL": "学术期刊",
            "CONFERENCE": "会议",
            "NEWSPAPER": "报纸",
            "BOOK": "图书",
            "PATENT": "专利",
            "STANDARD": "标准",
            "ACHIEVEMENTS": "成果",
        }
        
        safe_print(f"正在筛选：{resource_names.get(resource_type, resource_type)}...")
        
        try:
            # 查找对应的资源类型链接
            filter_link = page.locator(f"a[resource='{resource_type}']").first
            if filter_link and filter_link.is_visible(timeout=2000):
                filter_link.click()
                safe_print(f"已点击：{resource_names.get(resource_type, resource_type)}")
                self._random_delay(3, 5)  # 等待新结果加载
                return True
            
            safe_print(f"警告：未找到 {resource_names.get(resource_type, resource_type)} 筛选选项")
            return False
            
        except Exception as e:
            safe_print(f"筛选失败：{str(e)}")
            return False
    
    def search(self, request: CNKIQueryRequest) -> CNKIQueryResult:
        if not self.is_ready():
            if not self.initialize():
                raise Exception("服务未初始化，请先完成验证")

        config = ConfigManager.get_instance()
        page_goto_timeout = config.get_timeout('page_goto_timeout', 60000)
        page_load_wait_min = config.get_delay('page_load_wait', 2.0)
        page_load_wait_max = page_load_wait_min + 1.0
        click_delay_min = config.get_delay('click_delay_min', 0.3)
        click_delay_max = config.get_delay('click_delay_max', 0.5)
        input_delay = config.get_delay('input_delay', 50)
        search_result_wait_min = config.get_delay('search_result_wait_min', 1.0)
        search_result_wait_max = config.get_delay('search_result_wait_max', 2.0)
        filter_delay_min = config.get_delay('option_click_delay_min', 1.0)
        filter_delay_max = config.get_delay('option_click_delay_max', 2.0)

        page = self._page
        
        try:
            safe_print(f"\n正在执行检索：{request.keyword}...")
            safe_print(f"搜索类型：{SEARCH_TYPE_NAMES.get(request.search_type, request.search_type.value)}")
            
            # 访问知网首页，使用 domcontentloaded 而非 networkidle 避免长时间等待
            safe_print("正在访问知网首页...")
            page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=page_goto_timeout)
            # 等待搜索框出现，而非固定延迟
            try:
                page.wait_for_selector("#txt_search", state="visible", timeout=10000)
            except Exception:
                self._random_delay(page_load_wait_min, page_load_wait_max)
            
            if self._check_captcha(page):
                if not self._wait_for_captcha(page):
                    raise Exception("验证超时，请重试")
            
            # 填写搜索关键词
            safe_print("正在填写搜索框...")
            search_input = page.locator("#txt_search").first
            search_input.click()
            self._random_delay(click_delay_min, click_delay_max)
            search_input.fill("")
            self._random_delay(click_delay_min, click_delay_max)
            search_input.type(request.keyword, delay=int(input_delay))
            self._random_delay(0.5, 1)
            
            # 如果需要切换搜索类型，在搜索前切换
            if request.search_type != SearchType.SU:
                self.switch_search_type(page, request.search_type)
            
            # 点击搜索按钮
            search_btn = page.locator("input.search-btn").first
            search_btn.click()
            safe_print("已点击搜索按钮")
            
            # 等待搜索结果加载：「有结果」或「无结果提示」任意一个出现即返回，不串行等待
            # 合并所有可能出现的元素为一个选择器，彻底避免多次超时叠加
            RESULT_OR_EMPTY_SELECTOR = (
                "span.pagerTitleCell, "       # 有结果时的分页标题（最可靠）
                "p.no-content, "              # 知网真实无结果提示
                "table.result-table-list, "   # 结果表格
                "a[href*='kcms'], "           # 结果链接
                ".tips-nodata, "              # 其他无结果提示
                ".no-result"
            )
            result_loaded = False
            try:
                page.wait_for_selector(RESULT_OR_EMPTY_SELECTOR, state="visible", timeout=20000)
                result_loaded = True
                safe_print("检测到结果页元素（有结果或无结果提示）")
            except Exception:
                safe_print("警告：等待搜索结果超时，继续尝试解析")

            # 快速判断是否为无结果，是则提前返回空结果，不再执行后续解析
            try:
                no_content = page.locator("p.no-content").first
                if no_content.is_visible(timeout=500):
                    msg = no_content.inner_text(timeout=500).strip()
                    safe_print(f"[无结果] 知网返回空页面：{msg}")
                    return CNKIQueryResult(
                        total=0,
                        page_num=request.page_num,
                        page_size=request.page_size,
                        category_counts={},
                        results=[]
                    )
            except Exception:
                pass

            # 检查验证码（等待结果后再检查一次）
            if self._check_captcha(page):
                if not self._wait_for_captcha(page):
                    raise Exception("验证超时，请重试")
            
            if not result_loaded:
                safe_print("警告：搜索结果可能未完全加载")
            
            # 如果需要设置每页显示数量
            if request.page_size != self.get_current_page_size():
                safe_print(f"需要调整每页显示数量为 {request.page_size} 条...")
                if not self.set_page_size(request.page_size):
                    safe_print("警告：设置每页显示数量失败，将使用当前设置")
                # set_page_size 内部已用 wait_for_selector 等待，无需额外延迟
            
            # 如果需要筛选资源类型
            if request.filter_resource:
                if self.filter_by_resource(page, request.filter_resource):
                    # 筛选后：用合并选择器同时等待「有结果」或「无结果提示」，任意一个出现即返回
                    try:
                        page.wait_for_selector(
                            RESULT_OR_EMPTY_SELECTOR,
                            state="visible",
                            timeout=15000
                        )
                        safe_print("筛选后检测到结果页元素")
                    except Exception:
                        safe_print("警告：筛选后结果可能未完全加载")
                    # 检查筛选后是否无结果，提前返回
                    try:
                        no_content = page.locator("p.no-content").first
                        if no_content.is_visible(timeout=500):
                            msg = no_content.inner_text(timeout=500).strip()
                            safe_print(f"[无结果] 筛选后知网返回空页面：{msg}")
                            return CNKIQueryResult(
                                total=0,
                                page_num=request.page_num,
                                page_size=request.page_size,
                                category_counts={},
                                results=[]
                            )
                    except Exception:
                        pass

            safe_print("正在解析检索结果...")
            # 获取实际的每页显示数量
            actual_page_size = self.get_current_page_size()
            
            # 获取真实的结果总数（从知网页面）
            total_count = self._extract_result_count()
            safe_print(f"知网显示结果总数: {total_count}")
            
            # 获取分类统计
            safe_print("获取分类统计:")
            category_counts = self._extract_category_counts()
            
            # 解析当前页的结果
            results = self._parse_results(page, actual_page_size, request.search_type)
            
            if not results:
                safe_print("标准解析失败，尝试备用解析方法...")
                results = self._try_alternative_parse(page, actual_page_size)

            safe_print(f"检索完成，总数 {total_count} 条，当前页获取 {len(results)} 条\n")
            return CNKIQueryResult(
                total=total_count,  # 使用知网的真实总数
                page_num=request.page_num,
                page_size=actual_page_size,
                category_counts=category_counts,  # 添加分类统计
                results=results
            )

        except TimeoutError as e:
            raise Exception(f"页面加载超时：{str(e)}")
        except Exception as e:
            raise Exception(f"检索失败：{str(e)}")

    def _parse_results(self, page: Page, page_size: int, search_type: Optional[SearchType] = None) -> list[CNKIPaper]:
        results = []
        
        selectors = [
            ".result-table-list tbody tr",
            "#gridTable .result-tr",
            ".result-table-list tr",
            ".s-single-result",
            ".article-item",
            ".list-item",
            "table.result-table-list tr",
        ]
        
        for selector in selectors:
            try:
                items = page.locator(selector).all()
                if items and len(items) > 0:
                    for item in items[:page_size]:
                        paper = self._parse_item(item, search_type)
                        if paper.title:
                            results.append(paper)
                    if results:
                        return results
            except Exception:
                continue

        return results

    def _try_alternative_parse(self, page: Page, page_size: int) -> list[CNKIPaper]:
        results = []
        
        # 注意：这里不使用 networkidle 等待，避免无结果时不必要的等待
        # 如果走到此备用解析说明标准解析已失败，直接尝试链接方式
        try:
            all_links = page.locator("a[href*='kcms'], a[href*='detail']").all()
            seen_titles = set()
            seen_links = set()
            
            for link in all_links:
                try:
                    href = link.get_attribute("href") or ""
                    if not href or href in seen_links:
                        continue
                    if "kcms" not in href and "detail" not in href:
                        continue
                    
                    title = link.inner_text(timeout=1000).strip()
                    
                    if not title or len(title) < 5 or title in seen_titles:
                        continue
                    
                    seen_titles.add(title)
                    seen_links.add(href)
                    author = ""
                    source = ""
                    publish_time = ""
                    
                    try:
                        element = link
                        for _ in range(5):
                            try:
                                element = element.locator("xpath=..")
                                element_text = element.inner_text(timeout=500)
                                if element_text and len(element_text) > len(title) + 30:
                                    break
                            except Exception:
                                break
                        
                        parent_text = element.inner_text(timeout=1000)
                        lines = [l.strip() for l in parent_text.split('\n') if l.strip()]
                        
                        title_idx = -1
                        for i, line in enumerate(lines):
                            if title == line:
                                title_idx = i
                                break
                        
                        if title_idx == -1:
                            for i, line in enumerate(lines):
                                if title in line and len(line) < len(title) + 20:
                                    title_idx = i
                                    break
                        
                        if title_idx >= 0:
                            remaining = []
                            for i in range(title_idx + 1, len(lines)):
                                part = lines[i].strip()
                                if part and part != title and part not in remaining:
                                    remaining.append(part)
                            
                            if len(remaining) >= 2:
                                author = remaining[1]
                            if len(remaining) >= 3:
                                source = remaining[2]
                            if len(remaining) >= 4:
                                publish_time = remaining[3]
                    except Exception as e:
                        pass
                    
                    results.append(CNKIPaper(
                        title=title,
                        author=author,
                        source=source,
                        publish_time=publish_time,
                        abstract="",
                        link=href
                    ))
                    if len(results) >= page_size:
                        break
                except Exception:
                    continue
        except Exception:
            pass

        return results

    def _parse_item(self, item, search_type: Optional[SearchType] = None) -> CNKIPaper:
        title = ""
        author = ""
        source = ""
        publish_time = ""
        abstract = ""
        link = ""
        download_url = ""

        try:
            title_link = item.locator("td.name a, a[href*='kcms'], a[href*='detail'], a.fz14").first
            if title_link:
                title = title_link.inner_text(timeout=2000).strip()
                link = title_link.get_attribute("href") or ""
        except Exception:
            pass

        try:
            author_elem = item.locator("td.author").first
            if author_elem:
                author = author_elem.inner_text(timeout=2000).strip()
        except Exception:
            pass

        try:
            source_elem = item.locator("td.source").first
            if source_elem:
                source = source_elem.inner_text(timeout=2000).strip()
        except Exception:
            pass

        try:
            time_elem = item.locator("td.date, td.time").first
            if time_elem:
                publish_time = time_elem.inner_text(timeout=2000).strip()
        except Exception:
            pass

        # 提取搜索结果列表中的下载链接
        try:
            dl_btn = item.locator("td.operat a.downloadlink").first
            if dl_btn:
                href = dl_btn.get_attribute("href") or ""
                if "bar.cnki.net" in href or "download" in href:
                    download_url = href
        except Exception:
            pass

        return CNKIPaper(
            title=title,
            author=author,
            source=source,
            publish_time=publish_time,
            abstract=abstract,
            link=link,
            download_url=download_url,
            can_download=bool(download_url)
        )

    def get_paper_detail(self, paper_url: str) -> Optional[CNKIPaper]:
        """获取文章详细信息，包括摘要、关键词、引用格式等"""
        if not self.is_ready():
            if not self.initialize():
                raise Exception("服务未初始化，请先完成验证")

        config = ConfigManager.get_instance()
        page_goto_timeout = config.get_timeout('page_goto_timeout', 60000)
        detail_page_load_delay_min = config.get_delay('detail_page_load_delay_min', 3.0)
        detail_page_load_delay_max = config.get_delay('detail_page_load_delay_max', 5.0)
        page_load_state_timeout = config.get_timeout('page_load_state_timeout', 5000)
        page_load_wait_min = config.get_delay('page_load_wait', 2.0)
        page_load_wait_max = page_load_wait_min + 1.0

        page = self._page
        paper = CNKIPaper(link=paper_url)
        
        try:
            safe_print(f"\n正在获取文章详情：{paper_url}")
            # 使用 domcontentloaded 代替 networkidle，避免等待所有资源加载完毕
            page.goto(paper_url, wait_until="domcontentloaded", timeout=page_goto_timeout)
            
            # 等待关键内容出现，而非固定延迟
            try:
                page.wait_for_selector(".wx-tit h1, div.doc h1, h1", timeout=8000)
            except Exception:
                pass
            
            if self._check_captcha(page):
                if not self._wait_for_captcha(page):
                    raise Exception("验证超时，请重试")
            
            self._random_delay(1.0, 1.5)
            
            paper = self._parse_paper_detail(page, paper_url)
            
            safe_print("正在获取引用格式...")
            paper = self._get_citation_formats(page, paper)
            
            safe_print("[OK] 文章详情获取完成\n")
            return paper

        except Exception as e:
            safe_print(f"[X] 获取文章详情失败：{str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_paper_detail(self, page: Page, paper_url: str) -> CNKIPaper:
        """解析文章详情页"""
        paper = CNKIPaper(link=paper_url)
        
        try:
            title_selectors = [
                ".wx-tit h1",      # 知网详情页主标题容器（最精准）
                "div.doc h1",
                "div.main h1",
                "h1",              # 兜底：遍历所有 h1，取可见且有内容的
            ]
            for selector in title_selectors:
                try:
                    elems = page.locator(selector).all()
                    for elem in elems:
                        try:
                            # 只取可见元素，避免拿到隐藏的"自动登录"等干扰项
                            if not elem.is_visible(timeout=500):
                                continue
                            text = elem.inner_text(timeout=2000).strip()
                            if text and len(text) > 5:
                                paper.title = text
                                break
                        except Exception:
                            continue
                    if paper.title:
                        break
                except Exception:
                    continue
        except Exception:
            pass
        
        try:
            author_selectors = [
                ".author",
                ".doc-author",
                ".author-text",
            ]
            for selector in author_selectors:
                try:
                    elem = page.locator(selector).first
                    if elem:
                        text = elem.inner_text(timeout=2000).strip()
                        if text:
                            paper.author = text
                            break
                except Exception:
                    continue
        except Exception:
            pass
        
        try:
            org_selectors = [
                ".orgn",
                ".affiliation",
                ".author-affiliation",
            ]
            for selector in org_selectors:
                try:
                    elem = page.locator(selector).first
                    if elem:
                        text = elem.inner_text(timeout=2000).strip()
                        if text:
                            paper.author_affiliation = text
                            break
                except Exception:
                    continue
        except Exception:
            pass
        
        try:
            source_selectors = [
                ".sourcename",
                ".source",
                ".journal-name",
            ]
            for selector in source_selectors:
                try:
                    elem = page.locator(selector).first
                    if elem:
                        text = elem.inner_text(timeout=2000).strip()
                        if text:
                            paper.source = text
                            break
                except Exception:
                    continue
        except Exception:
            pass
        
        try:
            elem = page.locator("#ChDivSummary").first
            if elem:
                paper.abstract = elem.inner_text(timeout=2000).strip()
        except Exception:
            try:
                abstract_selectors = [
                    ".abstract-text",
                    ".abstract",
                ]
                for selector in abstract_selectors:
                    try:
                        elem = page.locator(selector).first
                        if elem:
                            text = elem.inner_text(timeout=2000).strip()
                            if text and len(text) > 20:
                                paper.abstract = text
                                break
                    except Exception:
                        continue
            except Exception:
                pass
        
        try:
            elem = page.locator("p.keywords").first
            if elem:
                paper.keywords = elem.inner_text(timeout=2000).strip()
        except Exception:
            try:
                keyword_selectors = [
                    ".keywords",
                    ".keyword-list",
                ]
                for selector in keyword_selectors:
                    try:
                        elem = page.locator(selector).first
                        if elem:
                            text = elem.inner_text(timeout=2000).strip()
                            if text:
                                paper.keywords = text
                                break
                    except Exception:
                        continue
            except Exception:
                pass
        
        try:
            elem = page.locator("p.funds").first
            if elem:
                paper.fund = elem.inner_text(timeout=2000).strip()
        except Exception:
            pass
        
        try:
            row_divs = page.locator("div.row").all()
            for row in row_divs:
                try:
                    row_text = row.inner_text(timeout=1000)
                    if "DOI：" in row_text:
                        try:
                            li_elems = row.locator("li.top-space").all()
                            for li in li_elems:
                                li_text = li.inner_text(timeout=1000)
                                if "DOI：" in li_text:
                                    paper.doi = li_text.replace("DOI：", "").strip()
                                elif "专辑：" in li_text:
                                    paper.album = li_text.replace("专辑：", "").strip()
                                elif "专题：" in li_text:
                                    paper.topic = li_text.replace("专题：", "").strip()
                                elif "分类号：" in li_text:
                                    paper.classification = li_text.replace("分类号：", "").strip()
                                elif "在线公开时间：" in li_text:
                                    paper.online_publish_time = li_text.replace("在线公开时间：", "").strip()
                        except Exception:
                            pass
                except Exception:
                    continue
        except Exception:
            pass
        
        # 提取详情页 CAJ / PDF 下载链接
        try:
            caj_elem = page.locator("#cajDown").first
            if caj_elem:
                href = caj_elem.get_attribute("href") or ""
                if href:
                    paper.caj_url = href
        except Exception:
            pass
        
        try:
            pdf_elem = page.locator("#pdfDown").first
            if pdf_elem:
                href = pdf_elem.get_attribute("href") or ""
                if href:
                    paper.pdf_url = href
        except Exception:
            pass
        
        # 只要有任意下载链接就标记为可下载
        if paper.caj_url or paper.pdf_url:
            paper.can_download = True
        
        return paper

    def _get_citation_formats(self, page: Page, paper: CNKIPaper) -> CNKIPaper:
        """获取引用格式"""
        config = ConfigManager.get_instance()
        citation_button_delay_min = config.get_delay('citation_button_delay_min', 2.0)
        citation_button_delay_max = config.get_delay('citation_button_delay_max', 3.0)
        page_load_wait_min = config.get_delay('page_load_wait', 2.0)
        page_load_wait_max = page_load_wait_min + 1.0
        
        try:
            citation_button = page.locator('a[onclick="getQuotes()"]').first
            if not citation_button.is_visible(timeout=2000):
                citation_button = page.locator("a:has-text('引用')").first
            
            if citation_button and citation_button.is_visible(timeout=2000):
                citation_button.click()
                safe_print("已点击引用按钮")
                # 等待引用弹窗出现，而非固定延迟
                try:
                    page.wait_for_selector(".quote-pop", state="visible", timeout=4000)
                except Exception:
                    self._random_delay(0.5, 1.0)
                
                try:
                    quote_dialog = page.locator(".quote-pop").first
                    if quote_dialog.is_visible(timeout=3000):
                        safe_print("检测到引用弹窗")
                        
                        rows = quote_dialog.locator("table tbody tr").all()
                        
                        for row in rows:
                            try:
                                label_cell = row.locator("td.quote-l").first
                                value_cell = row.locator("td.quote-r").first
                                
                                if label_cell and value_cell:
                                    label_text = label_cell.inner_text(timeout=1000).strip()
                                    
                                    if "GB/T 7714-2015" in label_text:
                                        textarea = value_cell.locator("textarea.text").first
                                        if textarea:
                                            try:
                                                paper.citation_gbt = textarea.input_value(timeout=1000).strip()
                                            except Exception:
                                                paper.citation_gbt = textarea.inner_text(timeout=1000).strip()
                                            safe_print(f"已获取 GB/T 7714-2015 格式：{paper.citation_gbt[:50]}...")
                                    
                                    elif "知网研学" in label_text:
                                        textarea = value_cell.locator("textarea.text").first
                                        if textarea:
                                            try:
                                                paper.citation_cnki = textarea.input_value(timeout=1000).strip()
                                            except Exception:
                                                paper.citation_cnki = textarea.inner_text(timeout=1000).strip()
                                            safe_print(f"已获取知网研学格式")
                                    
                                    elif "EndNote" in label_text:
                                        textarea = value_cell.locator("textarea.text").first
                                        if textarea:
                                            try:
                                                paper.citation_endnote = textarea.input_value(timeout=1000).strip()
                                            except Exception:
                                                paper.citation_endnote = textarea.inner_text(timeout=1000).strip()
                                            safe_print(f"已获取 EndNote 格式")
                            except Exception:
                                continue
                        
                        try:
                            close_btn = quote_dialog.locator(".layui-layer-close").first
                            if close_btn and close_btn.is_visible(timeout=1000):
                                close_btn.click()
                                self._random_delay(0.5, 1)
                        except Exception:
                            pass
                except Exception as e:
                    safe_print(f"解析引用弹窗失败：{str(e)}")
        
        except Exception as e:
            safe_print(f"获取引用格式时出错：{str(e)}")
        
        return paper
    
    # ==================== 下载方法 ====================

    def download_paper(
        self,
        paper_url: str,
        fmt: str = "pdf",
        save_dir: str = ""
    ) -> "CNKIDownloadResult":
        """下载论文文件

        策略：
        1. 先访问详情页，获取 CAJ / PDF 下载链接
        2. 用 Playwright 监听文件下载事件，点击对应按钮
        3. 若点击后未触发下载（跳转到付费页面），视为无权限，返回失败

        Args:
            paper_url: 论文详情页 URL
            fmt:       下载格式，'pdf' 或 'caj'（默认 pdf）
            save_dir:  本地保存目录；为空时自动使用用户 Downloads 目录

        Returns:
            CNKIDownloadResult
        """
        from .models import CNKIDownloadResult
        import os

        if not self.is_ready():
            if not self.initialize():
                return CNKIDownloadResult(success=False, message="服务未初始化")

        config = ConfigManager.get_instance()
        page_goto_timeout = config.get_timeout('page_goto_timeout', 60000)
        detail_page_load_delay_min = config.get_delay('detail_page_load_delay_min', 3.0)
        detail_page_load_delay_max = config.get_delay('detail_page_load_delay_max', 5.0)
        download_button_delay_min = config.get_delay('download_button_delay_min', 1.0)
        download_button_delay_max = config.get_delay('download_button_delay_max', 2.0)
        download_timeout = config.get_timeout('download_timeout', 30000)

        fmt = fmt.lower().strip()
        if fmt not in ("pdf", "caj"):
            fmt = "pdf"

        # save_dir 为空时自动回退到用户 Downloads 目录
        if not save_dir or not save_dir.strip():
            save_dir = os.path.join(os.path.expanduser("~"), "Downloads")
            safe_print(f"未指定保存目录，自动使用：{save_dir}")
        else:
            save_dir = os.path.expanduser(save_dir.strip())

        page = self._page
        safe_print(f"\n正在准备下载（{fmt.upper()}）：{paper_url}")

        try:
            # 1. 访问详情页
            page.goto(paper_url, wait_until="domcontentloaded", timeout=page_goto_timeout)
            # 等待下载按钮出现，而非固定延迟
            try:
                page.wait_for_selector("#pdfDown, #cajDown, .download-btns", state="visible", timeout=8000)
            except Exception:
                self._random_delay(detail_page_load_delay_min, detail_page_load_delay_max)

            if self._check_captcha(page):
                if not self._wait_for_captcha(page):
                    return CNKIDownloadResult(success=False, message="验证码超时")

            # 2. 定位下载按钮
            btn_id = "#pdfDown" if fmt == "pdf" else "#cajDown"
            btn = page.locator(btn_id).first

            try:
                btn_visible = btn.is_visible(timeout=5000)
            except Exception:
                btn_visible = False

            if not btn_visible:
                # 备用：在 .download-btns 里按文本查找
                try:
                    btn = page.locator(
                        f".download-btns a:has-text('{'PDF' if fmt == 'pdf' else 'CAJ'}下载')"
                    ).first
                    btn_visible = btn.is_visible(timeout=3000)
                except Exception:
                    btn_visible = False

            if not btn_visible:
                return CNKIDownloadResult(
                    success=False,
                    format=fmt,
                    message=f"未找到 {fmt.upper()} 下载按钮，该文章可能不支持此格式"
                )

            # 3. 获取下载链接 href，提前判断
            download_href = btn.get_attribute("href") or ""
            if not download_href:
                return CNKIDownloadResult(
                    success=False, format=fmt, message="下载按钮没有链接"
                )

            # 4. 用 expect_download 监听文件下载事件
            safe_print(f"正在点击 {fmt.upper()} 下载按钮...")
            os.makedirs(save_dir, exist_ok=True)

            try:
                with page.expect_download(timeout=download_timeout) as dl_info:
                    btn.click()

                download = dl_info.value
                suggested = download.suggested_filename or f"paper.{fmt}"
                save_path = os.path.join(save_dir, suggested)
                download.save_as(save_path)

                safe_print(f"[OK] 下载成功：{save_path}")
                return CNKIDownloadResult(
                    success=True,
                    file_path=os.path.abspath(save_path),
                    file_name=suggested,
                    format=fmt,
                    message=f"下载成功"
                )

            except Exception as dl_err:
                # expect_download 超时 = 没有触发文件下载，说明跳转到了付费页面
                safe_print(f"未触发文件下载（可能跳转到付费页面）：{str(dl_err)}")

                # 检查当前 URL 是否还在 bar.cnki.net
                cur_url = page.url
                safe_print(f"当前页面：{cur_url}")

                if "bar.cnki.net" in cur_url or "download" in cur_url:
                    msg = "点击后仍在下载域名，但未收到文件，可能网络问题"
                else:
                    msg = "无下载权限：点击后跳转到付费页面，请确认账号已登录且有下载权限"

                # 回退到详情页，避免影响后续操作
                try:
                    page.go_back(timeout=5000)
                    self._random_delay(1, 2)
                except Exception:
                    pass

                return CNKIDownloadResult(
                    success=False, format=fmt, message=msg
                )

        except Exception as e:
            safe_print(f"下载失败：{str(e)}")
            import traceback
            traceback.print_exc()
            return CNKIDownloadResult(
                success=False, format=fmt, message=f"下载异常：{str(e)}"
            )

    # ==================== 批量操作方法 ====================
    
    def batch_get_details_across_pages(
        self,
        max_count: int = 20,
        max_pages: int = 5
    ) -> list[CNKIPaper]:
        """跨页批量获取论文详情
        
        Args:
            max_count: 最大获取数量
            max_pages: 最大翻页数
            
        Returns:
            list[CNKIPaper]: 论文详情列表
        """
        config = ConfigManager.get_instance()
        batch_operation_delay_min = config.get_delay('batch_operation_delay_min', 3.0)
        batch_operation_delay_max = config.get_delay('batch_operation_delay_max', 5.0)
        
        if self._get_current_page_type() != PageState.SEARCH_RESULT:
            safe_print("错误：当前不在搜索结果页")
            return []
        
        all_papers = []
        pages_visited = 0
        
        safe_print(f"\n开始批量获取，目标 {max_count} 篇，最多翻 {max_pages} 页")
        safe_print("=" * 60)
        
        while len(all_papers) < max_count and pages_visited < max_pages:
            # 获取当前页结果
            current_page, total_pages = self._extract_page_info()
            safe_print(f"\n[页 {current_page}/{total_pages}] 正在解析...")
            
            results = self._parse_results(self._page, page_size=20)
            safe_print(f"  当前页找到 {len(results)} 条结果")
            
            # 获取详情
            for i, paper in enumerate(results):
                if len(all_papers) >= max_count:
                    break
                
                if paper.link:
                    safe_print(f"  [{len(all_papers)+1}/{max_count}] {paper.title[:40]}...")
                    detail = self.get_paper_detail(paper.link)
                    if detail:
                        all_papers.append(detail)
                    self._random_delay(batch_operation_delay_min, batch_operation_delay_max)
            
            # 检查是否需要翻页
            if len(all_papers) >= max_count:
                break
            
            pages_visited += 1
            if pages_visited >= max_pages:
                break
            
            # 翻到下一页
            if current_page < total_pages:
                safe_print(f"\n准备翻到下一页...")
                if not self.next_page():
                    safe_print("无法翻页，停止批量获取")
                    break
            else:
                safe_print("已到最后一页")
                break
        
        safe_print("\n" + "=" * 60)
        safe_print(f"批量获取完成！共获取 {len(all_papers)} 篇")
        safe_print("=" * 60 + "\n")
        return all_papers

    def _cleanup(self):
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
        self._browser = None
        self._page = None
        self._playwright = None
        self._ready = False

    def close(self):
        self._cleanup()
        CNKIBrowser._instance = None
        CNKIBrowser._initialized = False


def get_browser() -> CNKIBrowser:
    return CNKIBrowser.get_instance()
