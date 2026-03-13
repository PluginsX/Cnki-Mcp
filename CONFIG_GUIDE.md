# 配置系统使用指南

## 概述

知网 MCP 服务现已支持集中配置管理。所有延迟时间、超时参数、优化选项都可以通过 `config/config.json` 文件进行统一配置，无需修改代码。

## 配置文件位置

```
Cnki-Mcp/
├── config/
│   └── config.json          # 配置文件
└── src/
    └── cnki_mcp/
        ├── config.py        # 配置管理模块
        └── browser.py       # 使用配置的浏览器模块
```

## 配置结构

配置文件分为四个主要部分：

### 1. delays（延迟配置）

所有模拟操作的延迟时间，单位为秒（除特别说明外）。

```json
{
  "delays": {
    "browser_slow_mo": 100,                    // Playwright 减速参数（毫秒）
    "random_delay_min": 0.5,                   // 通用随机延迟最小值
    "random_delay_max": 2.0,                   // 通用随机延迟最大值
    "page_load_wait": 2.0,                     // 页面加载后等待时间
    "click_delay_min": 0.3,                    // 点击操作前后延迟最小值
    "click_delay_max": 0.5,                    // 点击操作前后延迟最大值
    "input_delay": 50,                         // 输入框输入字符间隔（毫秒）
    "dropdown_delay_min": 0.5,                 // 下拉菜单打开后延迟最小值
    "dropdown_delay_max": 1.0,                 // 下拉菜单打开后延迟最大值
    "option_click_delay_min": 1.0,             // 选择下拉菜单选项后延迟最小值
    "option_click_delay_max": 2.0,             // 选择下拉菜单选项后延迟最大值
    "page_size_change_delay_min": 3.0,         // 修改每页显示数量后延迟最小值
    "page_size_change_delay_max": 5.0,         // 修改每页显示数量后延迟最大值
    "search_result_wait_min": 1.0,             // 搜索结果加载检测间隔最小值
    "search_result_wait_max": 2.0,             // 搜索结果加载检测间隔最大值
    "page_navigation_delay_min": 2.0,          // 翻页操作后延迟最小值
    "page_navigation_delay_max": 3.0,          // 翻页操作后延迟最大值
    "detail_page_load_delay_min": 3.0,         // 详情页加载后延迟最小值
    "detail_page_load_delay_max": 5.0,         // 详情页加载后延迟最大值
    "citation_button_delay_min": 2.0,          // 点击引用按钮后延迟最小值
    "citation_button_delay_max": 3.0,          // 点击引用按钮后延迟最大值
    "download_button_delay_min": 1.0,          // 点击下载按钮后延迟最小值
    "download_button_delay_max": 2.0,          // 点击下载按钮后延迟最大值
    "batch_operation_delay_min": 3.0,          // 批量操作中每个项目间延迟最小值
    "batch_operation_delay_max": 5.0,          // 批量操作中每个项目间延迟最大值
    "captcha_check_interval": 1.0,             // 验证码检测间隔
    "captcha_wait_after_complete_min": 2.0,    // 验证码完成后延迟最小值
    "captcha_wait_after_complete_max": 3.0     // 验证码完成后延迟最大值
  }
}
```

### 2. timeouts（超时配置）

各种操作的超时时间，单位为毫秒。

```json
{
  "timeouts": {
    "page_goto_timeout": 60000,                // 页面导航超时
    "page_load_state_timeout": 5000,           // 页面加载状态等待超时
    "element_visible_timeout": 2000,           // 元素可见性检查超时
    "element_click_timeout": 3000,             // 元素点击超时
    "page_loaded_timeout": 15000,              // 页面完全加载超时
    "search_result_timeout": 20000,            // 搜索结果加载超时
    "detail_page_timeout": 10000,              // 详情页加载超时
    "download_timeout": 30000                  // 文件下载超时
  }
}
```

### 3. optimization（优化配置）

性能和行为优化选项。

```json
{
  "optimization": {
    "enable_cache": true,                      // 是否启用浏览器缓存
    "clear_cache_on_init": false,              // 初始化时是否清空缓存
    "max_retry_attempts": 3,                   // 操作失败时的最大重试次数
    "enable_headless": false,                  // 是否使用无头模式
    "viewport_width": 1920,                    // 浏览器窗口宽度
    "viewport_height": 1080                    // 浏览器窗口高度
  }
}
```

### 4. detection（检测配置）

反爬虫检测相关配置。

```json
{
  "detection": {
    "user_agent": "Mozilla/5.0 ...",            // 浏览器 User-Agent
    "disable_automation_detection": true,      // 是否禁用自动化检测标记
    "disable_infobars": true,                  // 是否禁用信息栏
    "sandbox_disabled": true                   // 是否禁用沙箱
  }
}
```

## 常见优化场景

### 场景 1：解决假死问题

如果出现假死（浏览器卡住），尝试增加延迟：

```json
{
  "delays": {
    "random_delay_min": 1.0,
    "random_delay_max": 3.0,
    "page_load_wait": 3.0,
    "browser_slow_mo": 150
  }
}
```

### 场景 2：加快操作速度

如果操作太慢，尝试减少延迟：

```json
{
  "delays": {
    "random_delay_min": 0.2,
    "random_delay_max": 0.8,
    "page_load_wait": 1.0,
    "browser_slow_mo": 50
  }
}
```

### 场景 3：解决搜索无结果问题

如果长周期任务后搜索无结果，尝试清空缓存：

```json
{
  "optimization": {
    "clear_cache_on_init": true
  }
}
```

### 场景 4：提高网络稳定性

如果网络不稳定，增加超时时间：

```json
{
  "timeouts": {
    "page_goto_timeout": 90000,
    "search_result_timeout": 30000,
    "download_timeout": 60000
  }
}
```

## 配置管理 API

### Python 代码中使用配置

```python
from cnki_mcp.config import ConfigManager, get_delay, get_timeout

# 方式 1：使用全局函数
delay_min = get_delay('random_delay_min')
delay_max = get_delay('random_delay_max')
timeout = get_timeout('page_goto_timeout')

# 方式 2：使用单例实例
config = ConfigManager.get_instance()
delay_min = config.get_delay('random_delay_min')
timeout = config.get_timeout('page_goto_timeout')
optimization = config.get_optimization('enable_cache')
detection = config.get_detection('user_agent')

# 重新加载配置
config.reload()

# 打印当前配置
config.print_config()

# 获取所有配置
all_config = config.get_all()
```

## 配置文件自动加载

配置管理器会自动在以下位置查找配置文件（按优先级）：

1. `<项目根目录>/config/config.json`
2. `<当前工作目录>/config/config.json`
3. `<当前工作目录>/config.json`

如果找不到配置文件，将使用内置的默认配置。

## 动态修改配置

配置可以在运行时动态修改，无需重启服务：

```python
from cnki_mcp.config import ConfigManager

config = ConfigManager.get_instance()

# 获取当前配置
current_config = config.get_all()

# 修改配置
current_config['delays']['random_delay_min'] = 0.3
current_config['delays']['random_delay_max'] = 1.0

# 保存配置
config.save(current_config)

# 重新加载配置
config.reload()
```

## 配置优化建议

### 1. 延迟时间

- **最小值**：不要设置太小（< 0.1 秒），容易被识别为自动化
- **最大值**：不要设置太大（> 5 秒），会严重影响效率
- **推荐范围**：0.5 - 3.0 秒

### 2. 超时时间

- **页面导航**：60000 毫秒（60 秒）
- **搜索结果**：20000 毫秒（20 秒）
- **下载**：30000 毫秒（30 秒）

### 3. 浏览器参数

- **slow_mo**：100 毫秒（模拟真实用户操作）
- **headless**：false（显示浏览器窗口便于调试）
- **viewport**：1920x1080（标准分辨率）

## 故障排查

### 问题 1：假死

**症状**：浏览器卡住，无响应

**解决方案**：
1. 增加 `random_delay_max` 值
2. 增加 `browser_slow_mo` 值
3. 增加各种 `*_delay_max` 值

### 问题 2：搜索无结果

**症状**：搜索返回 0 条结果

**解决方案**：
1. 设置 `clear_cache_on_init` 为 true
2. 增加 `page_load_wait` 值
3. 增加 `search_result_timeout` 值

### 问题 3：操作超时

**症状**：操作经常超时

**解决方案**：
1. 增加相应的 `*_timeout` 值
2. 检查网络连接
3. 增加 `page_load_wait` 值

### 问题 4：被识别为自动化

**症状**：频繁出现验证码

**解决方案**：
1. 增加所有延迟时间
2. 增加 `browser_slow_mo` 值
3. 确保 `disable_automation_detection` 为 true

## 配置文件示例

### 保守配置（稳定性优先）

```json
{
  "delays": {
    "browser_slow_mo": 150,
    "random_delay_min": 1.0,
    "random_delay_max": 3.0,
    "page_load_wait": 3.0
  },
  "timeouts": {
    "page_goto_timeout": 90000,
    "search_result_timeout": 30000
  },
  "optimization": {
    "clear_cache_on_init": true
  }
}
```

### 激进配置（速度优先）

```json
{
  "delays": {
    "browser_slow_mo": 50,
    "random_delay_min": 0.2,
    "random_delay_max": 0.8,
    "page_load_wait": 1.0
  },
  "timeouts": {
    "page_goto_timeout": 45000,
    "search_result_timeout": 15000
  },
  "optimization": {
    "clear_cache_on_init": false
  }
}
```

### 平衡配置（推荐）

```json
{
  "delays": {
    "browser_slow_mo": 100,
    "random_delay_min": 0.5,
    "random_delay_max": 2.0,
    "page_load_wait": 2.0
  },
  "timeouts": {
    "page_goto_timeout": 60000,
    "search_result_timeout": 20000
  },
  "optimization": {
    "clear_cache_on_init": false
  }
}
```

## 总结

通过配置文件，你可以：

✓ 快速调整延迟时间，找到最优平衡点
✓ 根据网络环境调整超时时间
✓ 启用/禁用各种优化选项
✓ 无需修改代码，即可改变服务行为
✓ 为不同场景创建不同的配置文件

建议：

1. 从默认配置开始
2. 根据实际情况逐步调整
3. 记录有效的配置组合
4. 为不同场景保存多个配置文件


