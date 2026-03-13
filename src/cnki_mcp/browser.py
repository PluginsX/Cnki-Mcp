"""知网浏览器自动化模块 - 单例模式，保持会话"""

import time
import random
import atexit
import sys
import re
from typing import Optional

from playwright.sync_api import sync_playwright, Browser, Page, TimeoutError, Playwright

from .models import CNKIQueryRequest, CNKIQueryResult, CNKIPaper, SEARCH_TYPE_NAMES, SearchType


def safe_print(msg: str):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('utf-8', errors='replace').decode('utf-8'))


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

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ],
            slow_mo=100
        )
        context = self._browser.new_context(
            user_agent=self.USER_AGENT,
            viewport={"width": 1920, "height": 1080}
        )
        context.add_init_script(self.ANTI_DETECT_SCRIPT)
        self._page = context.new_page()
        self._page.set_default_timeout(60000)
        return self._page

    def _random_delay(self, min_sec: float = 0.5, max_sec: float = 2.0):
        time.sleep(random.uniform(min_sec, max_sec))

    def _check_captcha(self, page: Page) -> bool:
        for selector in self.CAPTCHA_SELECTORS:
            try:
                elem = page.locator(selector).first
                if elem.is_visible(timeout=500):
                    return True
            except Exception:
                continue
        try:
            page_content = page.content()
            if "验证" in page_content or "安全" in page_content:
                for selector in self.CAPTCHA_SELECTORS:
                    try:
                        if page.locator(selector).count() > 0:
                            return True
                    except Exception:
                        continue
        except Exception:
            pass
        return False

    def _wait_for_captcha(self, page: Page, max_wait: int = 0):
        safe_print("\n" + "=" * 60)
        safe_print("[!] 检测到安全验证（拼图验证码）")
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
                self._random_delay(2, 3)
                return True
            time.sleep(1)
            wait_count += 1
            if wait_count % 10 == 0:
                safe_print(f"    等待验证中... 已等待 {wait_count} 秒")
        
        return False

    def initialize(self) -> bool:
        safe_print("\n" + "=" * 60)
        safe_print("[*] 初始化知网检索服务")
        safe_print("=" * 60)
        safe_print("\n    正在启动浏览器...")
        
        try:
            page = self._init_browser()
            
            safe_print("    正在打开知网首页...")
            page.goto(self.BASE_URL, wait_until="networkidle", timeout=60000)
            self._random_delay(2, 3)

            max_attempts = 5
            for attempt in range(max_attempts):
                if self._check_captcha(page):
                    safe_print("\n    [!] 检测到安全验证，请完成验证...")
                    if not self._wait_for_captcha(page):
                        safe_print("    [X] 初始化失败：验证超时")
                        return False
                    self._random_delay(2, 3)
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
                    self._random_delay(2, 3)
                    if self._check_captcha(page):
                        safe_print("\n    [!] 检测到安全验证，请完成验证...")
                        if not self._wait_for_captcha(page):
                            safe_print("    [X] 初始化失败：验证超时")
                            return False
                        self._random_delay(2, 3)

            try:
                page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass

            self._ready = True
            safe_print("\n" + "=" * 60)
            safe_print("[OK] 知网检索服务初始化完成！")
            safe_print("    浏览器窗口将保持打开，后续查询将复用此会话")
            safe_print("=" * 60 + "\n")
            return True

        except Exception as e:
            safe_print(f"    [X] 初始化失败：{str(e)}")
            return False

    def is_ready(self) -> bool:
        return self._ready and self._page is not None

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

        page = self._page
        
        try:
            safe_print(f"\n正在执行检索：{request.keyword}...")
            safe_print(f"搜索类型：{SEARCH_TYPE_NAMES.get(request.search_type, request.search_type.value)}")
            
            # 先访问知网首页
            safe_print("正在访问知网首页...")
            page.goto(self.BASE_URL, wait_until="networkidle", timeout=60000)
            self._random_delay(2, 3)
            
            if self._check_captcha(page):
                if not self._wait_for_captcha(page):
                    raise Exception("验证超时，请重试")
            
            # 填写搜索关键词
            safe_print("正在填写搜索框...")
            search_input = page.locator("#txt_search").first
            search_input.click()
            self._random_delay(0.3, 0.5)
            search_input.fill("")
            self._random_delay(0.3, 0.5)
            search_input.type(request.keyword, delay=50)
            self._random_delay(0.5, 1)
            
            # 如果需要切换搜索类型，在搜索前切换
            if request.search_type != SearchType.SU:
                self.switch_search_type(page, request.search_type)
            
            # 点击搜索按钮
            search_btn = page.locator("input.search-btn").first
            search_btn.click()
            safe_print("已点击搜索按钮")
            
            max_wait = 30
            waited = 0
            result_loaded = False
            
            while waited < max_wait:
                self._random_delay(1, 2)
                waited += 2
                
                if self._check_captcha(page):
                    if not self._wait_for_captcha(page):
                        raise Exception("验证超时，请重试")
                
                try:
                    result_links = page.locator("a[href*='kcms'], a[href*='detail']").count()
                    if result_links > 0:
                        safe_print(f"检测到 {result_links} 个搜索结果链接")
                        result_loaded = True
                        break
                except Exception:
                    pass
                
                try:
                    if page.locator("#ModuleSearchResult").count() > 0:
                        content = page.locator("#ModuleSearchResult").inner_text(timeout=1000)
                        if content and len(content) > 50:
                            safe_print("检测到搜索结果内容")
                            result_loaded = True
                            break
                except Exception:
                    pass
            
            if not result_loaded:
                safe_print("警告：搜索结果可能未完全加载")
            
            self._random_delay(2, 3)
            
            # 如果需要筛选资源类型
            if request.filter_resource:
                if self.filter_by_resource(page, request.filter_resource):
                    # 筛选后等待新结果加载
                    self._random_delay(3, 5)
                    result_loaded = False
                    # 重新检测结果加载
                    for _ in range(10):
                        self._random_delay(1, 2)
                        try:
                            result_links = page.locator("a[href*='kcms'], a[href*='detail']").count()
                            if result_links > 0:
                                safe_print(f"筛选后检测到 {result_links} 个搜索结果链接")
                                result_loaded = True
                                break
                        except Exception:
                            pass
                    if not result_loaded:
                        safe_print("警告：筛选后结果可能未完全加载")

            safe_print("正在解析检索结果...")
            results = self._parse_results(page, request.page_size, request.search_type)
            
            if not results:
                safe_print("标准解析失败，尝试备用解析方法...")
                results = self._try_alternative_parse(page, request.page_size)

            safe_print(f"检索完成，共获取 {len(results)} 条结果\n")
            return CNKIQueryResult(
                total=len(results),
                page_num=request.page_num,
                page_size=request.page_size,
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
        
        try:
            page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass

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

        return CNKIPaper(
            title=title,
            author=author,
            source=source,
            publish_time=publish_time,
            abstract=abstract,
            link=link
        )

    def get_paper_detail(self, paper_url: str) -> Optional[CNKIPaper]:
        """获取文章详细信息，包括摘要、关键词、引用格式等"""
        if not self.is_ready():
            if not self.initialize():
                raise Exception("服务未初始化，请先完成验证")

        page = self._page
        paper = CNKIPaper(link=paper_url)
        
        try:
            safe_print(f"\n正在获取文章详情：{paper_url}")
            page.goto(paper_url, wait_until="networkidle", timeout=60000)
            self._random_delay(3, 5)
            
            if self._check_captcha(page):
                if not self._wait_for_captcha(page):
                    raise Exception("验证超时，请重试")
            
            try:
                page.wait_for_load_state("domcontentloaded", timeout=10000)
            except Exception:
                pass
            
            self._random_delay(2, 3)
            
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
                "h1",
                ".doc-title h1",
                ".title h1",
            ]
            for selector in title_selectors:
                try:
                    elem = page.locator(selector).first
                    if elem:
                        text = elem.inner_text(timeout=2000).strip()
                        if text and len(text) > 5:
                            paper.title = text
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
        
        return paper

    def _get_citation_formats(self, page: Page, paper: CNKIPaper) -> CNKIPaper:
        """获取引用格式"""
        try:
            citation_button = page.locator('a[onclick="getQuotes()"]').first
            if not citation_button.is_visible(timeout=2000):
                citation_button = page.locator("a:has-text('引用')").first
            
            if citation_button and citation_button.is_visible(timeout=2000):
                citation_button.click()
                self._random_delay(2, 3)
                safe_print("已点击引用按钮")
                
                self._random_delay(1, 2)
                
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
