# 浏览器初始化优化方案 v2.0（简洁版）

## 🎯 设计原则

**核心理念**：通过内部状态管理解决问题，而不是暴露给 Agent

**目标**：
- ✅ 避免重复弹窗
- ✅ 不增加新的 MCP 工具
- ✅ 对 Agent 透明，无需改变使用方式

## 💡 优化方案：内部状态锁 + 智能等待

### 方案概述

使用**进程内状态管理**（不需要文件或共享内存），通过异步锁和事件机制实现：

1. **异步锁** - 防止并发初始化
2. **事件通知** - 让等待的调用在初始化完成后继续
3. **状态标记** - 记录初始化状态（未开始/进行中/完成/失败）
4. **智能等待** - 后续调用自动等待首次初始化完成

### 核心代码

```python
# browser.py
import asyncio
from enum import Enum
from threading import Lock

class InitState(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class CNKIBrowser:
    # 类级别的状态管理
    _init_state: InitState = InitState.NOT_STARTED
    _init_lock = Lock()  # 线程锁（用于同步代码）
    _init_complete_event = None  # 异步事件（用于等待）
    
    def __init__(self):
        if CNKIBrowser._initialized:
            return
        CNKIBrowser._initialized = True
        
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
        self._ready: bool = False
        
        atexit.register(self._cleanup)
    
    def initialize(self) -> bool:
        """初始化浏览器（带锁保护，防止重复初始化）"""
        
        # 快速路径：如果已完成，直接返回
        if self._init_state == InitState.COMPLETED and self._ready:
            return True
        
        # 如果正在初始化中，返回 False（让调用者等待）
        if self._init_state == InitState.IN_PROGRESS:
            safe_print("⏳ 初始化正在进行中，请稍候...")
            return False
        
        # 获取锁，防止并发初始化
        with self._init_lock:
            # 双重检查（可能在等待锁期间已完成）
            if self._init_state == InitState.COMPLETED and self._ready:
                return True
            
            if self._init_state == InitState.IN_PROGRESS:
                return False
            
            # 标记为初始化中
            CNKIBrowser._init_state = InitState.IN_PROGRESS
            
            try:
                safe_print("\n" + "=" * 60)
                safe_print("[*] 初始化知网检索服务")
                safe_print("=" * 60)
                
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
                            CNKIBrowser._init_state = InitState.FAILED
                            return False
                        self._random_delay(2, 3)
                        continue
                    
                    try:
                        search_input = page.locator("input[type='text'], input.search-input, #txt_SearchText, .search-input").first
                        if search_input and search_input.is_visible(timeout=3000):
                            safe_print("    [OK] 页面加载成功")
                            break
                    except Exception:
                        pass
                    
                    if attempt < max_attempts - 1:
                        safe_print(f"    等待页面加载... ({attempt + 1}/{max_attempts})")
                        self._random_delay(2, 3)

                try:
                    page.wait_for_load_state("domcontentloaded", timeout=5000)
                except Exception:
                    pass

                self._ready = True
                CNKIBrowser._init_state = InitState.COMPLETED
                
                safe_print("\n" + "=" * 60)
                safe_print("[OK] 知网检索服务初始化完成！")
                safe_print("=" * 60 + "\n")
                return True

            except Exception as e:
                safe_print(f"    [X] 初始化失败：{str(e)}")
                CNKIBrowser._init_state = InitState.FAILED
                return False


# server.py
import asyncio

# 全局异步锁和事件
_init_async_lock = asyncio.Lock()
_init_complete_event = asyncio.Event()

async def ensure_browser_ready() -> bool:
    """确保浏览器已初始化（智能等待机制）"""
    browser = get_browser()
    
    # 快速路径：如果已就绪，直接返回
    if browser.is_ready():
        return True
    
    # 检查初始化状态
    init_state = browser._init_state
    
    # 如果正在初始化中，等待完成
    if init_state == "in_progress":
        safe_print("⏳ 检测到初始化正在进行，等待完成...", file=sys.stderr)
        
        try:
            # 等待初始化完成（最多5分钟）
            await asyncio.wait_for(_init_complete_event.wait(), timeout=300)
            return browser.is_ready()
        except asyncio.TimeoutError:
            safe_print("❌ 等待初始化超时", file=sys.stderr)
            return False
    
    # 如果未开始或失败，尝试初始化（带异步锁保护）
    async with _init_async_lock:
        # 双重检查（可能在等待锁期间已完成）
        if browser.is_ready():
            return True
        
        # 执行初始化
        safe_print("🚀 开始初始化浏览器...", file=sys.stderr)
        result = await asyncio.to_thread(browser.initialize)
        
        if result:
            # 通知所有等待的协程
            _init_complete_event.set()
        
        return result


# 修改所有工具调用
@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    if name == "cnki_search":
        try:
            request = CNKIQueryRequest(**arguments)
        except Exception as e:
            return [TextContent(type="text", text=f"参数错误：{str(e)}")]

        try:
            # 使用智能等待机制（对 Agent 透明）
            if not await ensure_browser_ready():
                return [TextContent(type="text", text="浏览器初始化失败或超时，请重试")]
            
            browser = get_browser()
            result = await asyncio.to_thread(browser.search, request)
            
            result_dict = result.model_dump()
            result_text = json.dumps(result_dict, ensure_ascii=False, indent=2)
            
            return [TextContent(type="text", text=result_text)]
            
        except Exception as e:
            return [TextContent(type="text", text=f"检索失败: {str(e)}")]
    
    elif name == "cnki_get_status":
        try:
            # 同样使用智能等待
            if not await ensure_browser_ready():
                return [TextContent(type="text", text="浏览器未初始化")]
            
            browser = get_browser()
            status = browser.get_page_status()
            result_text = json.dumps(status, ensure_ascii=False, indent=2)
            
            return [TextContent(type="text", text=result_text)]
            
        except Exception as e:
            return [TextContent(type="text", text=f"获取状态失败: {str(e)}")]
    
    # 其他工具类似...
```

## 🔄 工作流程

### 场景1：Agent 连续快速调用

```
时间线：
T0: Agent 调用 cnki_search()
    → ensure_browser_ready() 获取异步锁
    → 开始初始化，弹出浏览器
    → 状态标记为 IN_PROGRESS

T1: Agent 调用 cnki_get_status()
    → ensure_browser_ready() 检测到 IN_PROGRESS
    → 等待 _init_complete_event

T2: Agent 调用 cnki_navigate_page()
    → ensure_browser_ready() 检测到 IN_PROGRESS
    → 等待 _init_complete_event

T3: 用户完成验证码
    → 初始化完成
    → 状态标记为 COMPLETED
    → _init_complete_event.set() 通知所有等待者

T4: cnki_get_status() 继续执行 ✅
T5: cnki_navigate_page() 继续执行 ✅

结果：只弹出 1 个浏览器窗口
```

### 场景2：初始化完成后的调用

```
T0: 浏览器已初始化完成（状态 = COMPLETED）

T1: Agent 调用 cnki_search()
    → ensure_browser_ready() 快速路径
    → 检测到已就绪，直接返回 True
    → 立即执行搜索 ✅

无需等待，性能最优
```

## 📊 方案对比

| 方案 | 新增工具 | 复杂度 | Agent 感知 | 优雅度 |
|------|----------|--------|-----------|--------|
| 方案1（原）| 2个 | 高 | 需要主动调用 | ⭐⭐ |
| **方案2（新）** | **0个** | **中** | **完全透明** | **⭐⭐⭐⭐⭐** |

## ✨ 方案优势

1. **零侵入** - 不增加任何新工具
2. **透明化** - Agent 无需改变使用方式
3. **自动化** - 自动处理并发和等待
4. **高效** - 已初始化后零开销
5. **优雅** - 符合单一职责原则

## 🔧 实施步骤

### 1. 修改 models.py
```python
# 添加初始化状态枚举
class InitState(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
```

### 2. 修改 browser.py
- 添加类级别状态变量
- 在 `initialize()` 中添加锁保护
- 添加状态检查和双重检查

### 3. 修改 server.py
- 添加全局异步锁和事件
- 实现 `ensure_browser_ready()` 函数
- 修改所有工具调用使用新机制

### 4. 测试
- 测试并发调用场景
- 测试初始化失败重试
- 测试性能（已初始化后）

## ⚠️ 注意事项

### 1. 线程安全
- `browser.initialize()` 使用 `threading.Lock`（同步代码）
- `ensure_browser_ready()` 使用 `asyncio.Lock`（异步代码）

### 2. 超时处理
- 等待初始化最多 5 分钟
- 超时后返回失败，允许重试

### 3. 状态重置
- 初始化失败后，状态标记为 FAILED
- 下次调用时可以重新尝试初始化

### 4. 事件重置
- 如果需要重新初始化，需要重置事件：
```python
if init_state == "failed":
    _init_complete_event.clear()
```

## 🎯 预期效果

### 用户体验
```
Agent 连续调用 5 个工具：
1. cnki_search()         → 触发初始化，弹出浏览器
2. cnki_get_status()     → 自动等待...
3. cnki_navigate_page()  → 自动等待...
4. cnki_search()         → 自动等待...
5. cnki_batch_get_details() → 自动等待...

用户完成验证 → 所有调用依次执行

结果：
✅ 只有 1 个浏览器窗口
✅ Agent 无需关心初始化
✅ 用户体验流畅
```

### 性能
- **首次调用**: 需要初始化（3-30秒，取决于验证码）
- **后续调用**: 零开销（< 1ms 状态检查）

## 📝 实施清单

- [ ] 添加 `InitState` 枚举到 `models.py`
- [ ] 修改 `CNKIBrowser` 添加状态管理
- [ ] 优化 `initialize()` 方法添加锁保护
- [ ] 实现 `ensure_browser_ready()` 函数
- [ ] 修改所有工具调用逻辑
- [ ] 测试并发场景
- [ ] 更新文档

**预计时间**: 1-2 小时

---

## 🎊 总结

这个方案通过**内部状态管理**解决了并发初始化问题，而不是通过增加外部工具。

**核心思想**：
- 问题在内部解决，不暴露给外部
- 对 Agent 完全透明
- 保持接口简洁优雅

这才是真正优雅的解决方案！✨

