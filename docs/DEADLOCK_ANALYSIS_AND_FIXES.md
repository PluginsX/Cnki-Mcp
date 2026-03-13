# MCP 服务假死问题分析与优化方案

## 问题现象

连续多次调用 MCP 工具后，服务陷入假死状态：
- 浏览器本身正常运行，无卡顿
- MCP 服务无反馈，长期等待（几十分钟）
- 最终超时失败
- 手动操作浏览器正常

## 根本原因分析

### 1. **单线程池 + 同步阻塞操作 = 任务堆积**

```python
_browser_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="playwright")
```

**问题**：
- 所有 Playwright 操作都在同一个线程中执行
- 若某个操作阻塞（如网络超时、页面加载缓慢），后续任务全部排队等待
- 没有超时保护，阻塞操作可能永久占用线程

**症状**：
```
Task A (search) 阻塞 → Task B (get_detail) 等待 → Task C (navigate) 等待 → ...
```

### 2. **缺少操作级超时控制**

当前代码中：
- `run_in_browser_thread()` 无超时参数
- Playwright 操作本身有超时（如 `timeout=60000`），但若操作卡在 Python 层（如 JSON 序列化、数据处理），超时无效
- 异步任务无全局超时保护

**风险场景**：
```python
# 若 browser.search() 在某个环节卡住，整个线程被占用
result = await run_in_browser_thread(browser.search, request)  # 无超时
```

### 3. **异常处理不完整，导致资源泄漏**

```python
try:
    result = await run_in_browser_thread(browser.search, request)
except Exception as e:
    return [TextContent(type="text", text=f"检索失败: {str(e)}")]
```

**问题**：
- 若 `run_in_browser_thread` 超时或异常，线程可能处于不确定状态
- 没有清理机制（如重置浏览器状态、释放锁）
- 后续调用继承了前一个调用的污染状态

### 4. **全局锁 + 异步事件的协调不当**

```python
async with _init_async_lock:
    # 初始化浏览器
    result = await run_in_browser_thread(browser.initialize)
    if result:
        _init_complete_event.set()
```

**问题**：
- 若 `browser.initialize()` 在线程中超时，锁永不释放
- 后续所有调用都会在 `async with _init_async_lock` 处无限等待
- 没有超时保护的异步锁

### 5. **Playwright 页面状态污染**

连续操作后，页面可能处于：
- 弹窗未关闭
- 导航未完成
- 验证码未处理
- 网络连接断开

后续操作基于污染状态执行，导致选择器失效、超时增加。

### 6. **缺少心跳 / 健康检查机制**

MCP 服务无法向 Agent 报告：
- 当前线程状态（忙碌 / 空闲）
- 待处理任务队列长度
- 上一个操作的耗时

Agent 无法判断是否真的卡住，只能盲目等待。

---

## 优化方案

### 方案 A：操作级超时 + 异常恢复

#### A1. 为 `run_in_browser_thread` 添加超时

```python
async def run_in_browser_thread(func, *args, timeout_sec=120):
    """在固定的 Playwright 专用线程中执行函数，带超时保护"""
    loop = asyncio.get_event_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(_browser_executor, func, *args),
            timeout=timeout_sec
        )
    except asyncio.TimeoutError:
        safe_print(f"[TIMEOUT] {func.__name__} 超过 {timeout_sec}s，强制中断", file=sys.stderr)
        # 触发浏览器状态重置
        try:
            browser = get_browser()
            browser._reset_on_timeout()
        except Exception:
            pass
        raise TimeoutError(f"操作超时：{func.__name__}")
```

#### A2. 在 browser.py 中添加超时恢复机制

```python
def _reset_on_timeout(self):
    """超时后的恢复机制"""
    safe_print("[RECOVERY] 尝试恢复浏览器状态...")
    try:
        # 关闭所有弹窗
        self._page.evaluate("() => { document.querySelectorAll('[class*=close]').forEach(el => el.click()); }")
    except Exception:
        pass
    
    try:
        # 回到首页
        self._page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=10000)
    except Exception:
        pass
    
    safe_print("[RECOVERY] 浏览器状态已重置")
```

#### A3. 为每个工具调用设置超时

```python
@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    # 根据工具类型设置不同超时
    TOOL_TIMEOUTS = {
        "cnki_search": 120,
        "cnki_get_paper_detail": 90,
        "cnki_navigate_page": 60,
        "cnki_batch_get_details": 180,
        "cnki_download_paper": 300,
    }
    
    timeout = TOOL_TIMEOUTS.get(name, 120)
    
    try:
        return await asyncio.wait_for(
            _call_tool_impl(name, arguments),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        return [TextContent(
            type="text",
            text=f"工具执行超时（{timeout}s）。浏览器状态已重置，请重试。"
        )]
    except Exception as e:
        return [TextContent(type="text", text=f"工具执行失败: {str(e)}")]
```

---

### 方案 B：任务队列 + 优先级调度

#### B1. 使用 asyncio.Queue 管理任务

```python
import asyncio
from collections import deque

class BrowserTaskQueue:
    def __init__(self, max_queue_size=50):
        self.queue = asyncio.Queue(maxsize=max_queue_size)
        self.active_task = None
        self.task_history = deque(maxlen=100)  # 最近 100 个任务记录
    
    async def submit(self, func, *args, priority=0, timeout=120):
        """提交任务到队列"""
        task_id = f"{func.__name__}_{time.time()}"
        task_info = {
            "id": task_id,
            "func": func.__name__,
            "priority": priority,
            "submitted_at": time.time(),
            "status": "queued"
        }
        
        try:
            await asyncio.wait_for(
                self.queue.put((priority, task_id, func, args, timeout)),
                timeout=5
            )
            self.task_history.append(task_info)
            return task_id
        except asyncio.TimeoutError:
            return None
    
    async def process_queue(self):
        """后台处理队列中的任务"""
        while True:
            try:
                priority, task_id, func, args, timeout = await self.queue.get()
                
                self.active_task = task_id
                safe_print(f"[EXEC] 执行任务 {task_id}: {func.__name__}", file=sys.stderr)
                
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(_browser_executor, func, *args),
                    timeout=timeout
                )
                
                safe_print(f"[OK] 任务 {task_id} 完成", file=sys.stderr)
                self.active_task = None
                
            except asyncio.TimeoutError:
                safe_print(f"[TIMEOUT] 任务 {task_id} 超时", file=sys.stderr)
                self.active_task = None
                # 触发恢复
                try:
                    get_browser()._reset_on_timeout()
                except Exception:
                    pass
            except Exception as e:
                safe_print(f"[ERROR] 任务 {task_id} 异常: {e}", file=sys.stderr)
                self.active_task = None

_task_queue = BrowserTaskQueue()
```

#### B2. 修改 `run_in_browser_thread` 使用队列

```python
async def run_in_browser_thread(func, *args, timeout_sec=120):
    """通过任务队列执行，避免直接阻塞"""
    task_id = await _task_queue.submit(func, *args, timeout=timeout_sec)
    if not task_id:
        raise RuntimeError("任务队列已满，请稍后重试")
    
    # 等待任务完成（由后台处理器处理）
    # 这里需要实现任务结果的回调机制
    ...
```

---

### 方案 C：健康检查 + 状态监控

#### C1. 添加 `cnki_get_health` 工具

```python
Tool(
    name="cnki_get_health",
    description="获取 MCP 服务健康状态，包括浏览器状态、任务队列、最近操作等。",
    inputSchema={"type": "object", "properties": {}}
)

@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    elif name == "cnki_get_health":
        browser = get_browser()
        health = {
            "status": "healthy" if browser.is_ready() else "initializing",
            "browser_ready": browser.is_ready(),
            "init_state": browser._init_state.value,
            "active_task": _task_queue.active_task,
            "queue_size": _task_queue.queue.qsize(),
            "recent_tasks": [
                {
                    "id": t["id"],
                    "func": t["func"],
                    "status": t["status"],
                    "age_sec": time.time() - t["submitted_at"]
                }
                for t in list(_task_queue.task_history)[-10:]
            ]
        }
        return [TextContent(type="text", text=json.dumps(health, ensure_ascii=False, indent=2))]
```

#### C2. Agent 可定期调用健康检查

```
Agent 逻辑：
1. 调用工具 A
2. 等待 30s
3. 若无响应，调用 cnki_get_health
4. 若 queue_size > 10 或 active_task 长期不变，判定为卡住
5. 提示用户或自动重启服务
```

---

### 方案 D：页面状态隔离 + 会话管理

#### D1. 为每个搜索会话创建独立上下文

```python
class SearchSession:
    def __init__(self, session_id):
        self.session_id = session_id
        self.created_at = time.time()
        self.last_activity = time.time()
        self.page_state = {}
        self.timeout_sec = 300  # 5 分钟超时
    
    def is_expired(self):
        return time.time() - self.last_activity > self.timeout_sec
    
    def touch(self):
        self.last_activity = time.time()

_sessions = {}  # session_id -> SearchSession

def get_or_create_session(session_id=None):
    if not session_id:
        session_id = str(uuid.uuid4())
    
    if session_id not in _sessions:
        _sessions[session_id] = SearchSession(session_id)
    
    session = _sessions[session_id]
    if session.is_expired():
        # 清理过期会话
        del _sessions[session_id]
        session = SearchSession(session_id)
        _sessions[session_id] = session
    
    session.touch()
    return session
```

#### D2. 工具调用时传入 session_id

```python
@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    session_id = arguments.get("_session_id")  # Agent 可选传入
    session = get_or_create_session(session_id)
    
    # 在工具执行前检查页面状态
    browser = get_browser()
    if session.page_state.get("needs_reset"):
        browser._reset_on_timeout()
        session.page_state["needs_reset"] = False
    
    # 执行工具...
```

---

### 方案 E：日志 + 诊断工具

#### E1. 详细的操作日志

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('cnki_mcp.log'),
        logging.StreamHandler(sys.stderr)
    ]
)

logger = logging.getLogger("cnki_mcp")

async def run_in_browser_thread(func, *args, timeout_sec=120):
    logger.info(f"[START] {func.__name__} (timeout={timeout_sec}s)")
    start = time.time()
    try:
        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(_browser_executor, func, *args),
            timeout=timeout_sec
        )
        elapsed = time.time() - start
        logger.info(f"[OK] {func.__name__} 完成 ({elapsed:.1f}s)")
        return result
    except asyncio.TimeoutError:
        logger.error(f"[TIMEOUT] {func.__name__} 超时 ({timeout_sec}s)")
        raise
    except Exception as e:
        logger.error(f"[ERROR] {func.__name__} 异常: {e}", exc_info=True)
        raise
```

#### E2. 添加 `cnki_get_logs` 工具

```python
Tool(
    name="cnki_get_logs",
    description="获取最近的 MCP 服务日志，用于诊断问题。",
    inputSchema={
        "type": "object",
        "properties": {
            "lines": {
                "type": "integer",
                "description": "返回最近 N 行日志",
                "default": 50
            }
        }
    }
)
```

---

## 实施优先级

| 优先级 | 方案 | 工作量 | 效果 | 建议 |
|--------|------|--------|------|------|
| **P0** | A1 + A2 | 中 | 高 | **立即实施** |
| **P1** | C1 + C2 | 小 | 中 | 配合 P0 |
| **P2** | B1 + B2 | 大 | 高 | 后续优化 |
| **P3** | D1 + D2 | 中 | 中 | 可选 |
| **P4** | E1 + E2 | 小 | 中 | 诊断工具 |

---

## 快速修复清单（P0）

### 1. 修改 `run_in_browser_thread`

```python
async def run_in_browser_thread(func, *args, timeout_sec=120):
    """在固定的 Playwright 专用线程中执行函数，带超时保护"""
    loop = asyncio.get_event_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(_browser_executor, func, *args),
            timeout=timeout_sec
        )
    except asyncio.TimeoutError:
        safe_print(f"[TIMEOUT] {func.__name__} 超过 {timeout_sec}s", file=sys.stderr)
        try:
            get_browser()._reset_on_timeout()
        except Exception:
            pass
        raise TimeoutError(f"操作超时：{func.__name__}")
```

### 2. 在 browser.py 中添加 `_reset_on_timeout`

```python
def _reset_on_timeout(self):
    """超时后的恢复机制"""
    safe_print("[RECOVERY] 尝试恢复浏览器状态...")
    try:
        # 关闭弹窗
        self._page.evaluate("() => { document.querySelectorAll('[class*=close]').forEach(el => el.click()); }")
    except Exception:
        pass
    try:
        # 回到首页
        self._page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=10000)
    except Exception:
        pass
```

### 3. 为每个工具调用添加超时

```python
TOOL_TIMEOUTS = {
    "cnki_search": 120,
    "cnki_get_paper_detail": 90,
    "cnki_navigate_page": 60,
    "cnki_batch_get_details": 180,
    "cnki_download_paper": 300,
}

timeout = TOOL_TIMEOUTS.get(name, 120)

try:
    # 执行工具逻辑
    ...
except asyncio.TimeoutError:
    return [TextContent(type="text", text=f"工具执行超时（{timeout}s）。浏览器已重置，请重试。")]
```

### 4. 添加 `cnki_get_health` 工具

让 Agent 可以检查服务状态，判断是否真的卡住。

---

## 测试验证

创建压力测试脚本：

```python
# tests/test_concurrent_calls.py
async def test_concurrent_calls():
    """模拟 Agent 连续调用"""
    tasks = []
    for i in range(10):
        task = call_tool("cnki_search", {"keyword": f"测试{i}"})
        tasks.append(task)
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 验证：
    # 1. 所有任务都有响应（无假死）
    # 2. 超时任务返回明确的超时消息
    # 3. 浏览器状态可恢复
```

---

## 总结

**根本原因**：单线程 + 无超时 + 无恢复 = 假死

**快速修复**：添加超时 + 恢复机制 + 健康检查

**长期优化**：任务队列 + 会话隔离 + 详细日志

