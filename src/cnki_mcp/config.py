"""配置管理模块 - 集中管理所有延迟和超时参数"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional


class ConfigManager:
    """配置管理器 - 单例模式"""
    
    _instance: Optional['ConfigManager'] = None
    _config: Dict[str, Any] = {}
    _config_path: Optional[Path] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化配置管理器"""
        if not self._config:
            self._load_config()
    
    @classmethod
    def get_instance(cls) -> 'ConfigManager':
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def _load_config(self):
        """从配置文件加载配置"""
        # 查找配置文件
        config_paths = [
            # 1. 相对于当前文件的路径（src/cnki_mcp/config.py -> ../../config/config.json）
            Path(__file__).parent.parent.parent / "config" / "config.json",
            # 2. 相对于当前文件的路径（备用）
            Path(__file__).parent.parent / "config" / "config.json",
            # 3. 当前工作目录
            Path.cwd() / "config" / "config.json",
            Path.cwd() / "config.json",
        ]
        
        for path in config_paths:
            if path.exists():
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        self._config = json.load(f)
                    self._config_path = path
                    print(f"[CONFIG] 已加载配置文件：{path}")
                    return
                except Exception as e:
                    print(f"[CONFIG] 加载配置文件失败 {path}：{e}")
        
        # 如果没有找到配置文件，使用默认配置
        print("[CONFIG] 未找到配置文件，使用默认配置")
        self._config = self._get_default_config()
    
    @staticmethod
    def _get_default_config() -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "delays": {
                "browser_slow_mo": 100,
                "random_delay_min": 0.5,
                "random_delay_max": 2.0,
                "page_load_wait": 2.0,
                "click_delay_min": 0.3,
                "click_delay_max": 0.5,
                "input_delay": 50,
                "dropdown_delay_min": 0.5,
                "dropdown_delay_max": 1.0,
                "option_click_delay_min": 1.0,
                "option_click_delay_max": 2.0,
                "page_size_change_delay_min": 3.0,
                "page_size_change_delay_max": 5.0,
                "search_result_wait_min": 1.0,
                "search_result_wait_max": 2.0,
                "page_navigation_delay_min": 2.0,
                "page_navigation_delay_max": 3.0,
                "detail_page_load_delay_min": 3.0,
                "detail_page_load_delay_max": 5.0,
                "citation_button_delay_min": 2.0,
                "citation_button_delay_max": 3.0,
                "download_button_delay_min": 1.0,
                "download_button_delay_max": 2.0,
                "batch_operation_delay_min": 3.0,
                "batch_operation_delay_max": 5.0,
                "captcha_check_interval": 1.0,
                "captcha_wait_after_complete_min": 2.0,
                "captcha_wait_after_complete_max": 3.0,
            },
            "timeouts": {
                "page_goto_timeout": 60000,
                "page_load_state_timeout": 5000,
                "element_visible_timeout": 2000,
                "element_click_timeout": 3000,
                "page_loaded_timeout": 15000,
                "search_result_timeout": 20000,
                "detail_page_timeout": 10000,
                "download_timeout": 30000,
            },
            "optimization": {
                "enable_cache": True,
                "clear_cache_on_init": False,
                "max_retry_attempts": 3,
                "enable_headless": False,
                "viewport_width": 1920,
                "viewport_height": 1080,
            },
            "detection": {
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "disable_automation_detection": True,
                "disable_infobars": True,
                "sandbox_disabled": True,
            },
            "captcha": {
                "auto_verify": True,
                "max_retry": 10,
                "drag_duration": 0.5,
                "verify_method": "iou",
            }
        }
    
    def get(self, section: str, key: str, default: Any = None) -> Any:
        """获取配置值
        
        Args:
            section: 配置段（delays、timeouts、optimization、detection）
            key: 配置键
            default: 默认值
            
        Returns:
            配置值
        """
        try:
            return self._config.get(section, {}).get(key, default)
        except Exception:
            return default
    
    def get_delay(self, key: str, default: Any = None) -> Any:
        """获取延迟配置"""
        return self.get("delays", key, default)
    
    def get_timeout(self, key: str, default: Any = None) -> Any:
        """获取超时配置"""
        return self.get("timeouts", key, default)
    
    def get_optimization(self, key: str, default: Any = None) -> Any:
        """获取优化配置"""
        return self.get("optimization", key, default)
    
    def get_detection(self, key: str, default: Any = None) -> Any:
        """获取检测配置"""
        return self.get("detection", key, default)
    
    def get_captcha(self, key: str, default: Any = None) -> Any:
        """获取验证码配置"""
        return self.get("captcha", key, default)
    
    def reload(self):
        """重新加载配置文件"""
        self._config = {}
        self._load_config()
    
    def save(self, config: Dict[str, Any], path: Optional[Path] = None):
        """保存配置到文件
        
        Args:
            config: 配置字典
            path: 保存路径，如果为空则使用当前配置文件路径
        """
        save_path = path or self._config_path
        if not save_path:
            raise ValueError("未指定保存路径")
        
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        self._config = config
        print(f"[CONFIG] 配置已保存到：{save_path}")
    
    def print_config(self):
        """打印当前配置"""
        print("\n" + "=" * 70)
        print("当前配置")
        print("=" * 70)
        print(json.dumps(self._config, indent=2, ensure_ascii=False))
        print("=" * 70 + "\n")
    
    def get_all(self) -> Dict[str, Any]:
        """获取所有配置"""
        return self._config.copy()


# 全局配置管理器实例
config = ConfigManager.get_instance()


# 便捷函数
def get_delay(key: str, default: Any = None) -> Any:
    """获取延迟配置"""
    return config.get_delay(key, default)


def get_timeout(key: str, default: Any = None) -> Any:
    """获取超时配置"""
    return config.get_timeout(key, default)


def get_optimization(key: str, default: Any = None) -> Any:
    """获取优化配置"""
    return config.get_optimization(key, default)


def get_detection(key: str, default: Any = None) -> Any:
    """获取检测配置"""
    return config.get_detection(key, default)


def get_captcha(key: str, default: Any = None) -> Any:
    """获取验证码配置"""
    return config.get_captcha(key, default)


if __name__ == "__main__":
    # 测试配置管理器
    cfg = ConfigManager.get_instance()
    cfg.print_config()
    
    print("延迟配置示例：")
    print(f"  random_delay_min: {cfg.get_delay('random_delay_min')}")
    print(f"  random_delay_max: {cfg.get_delay('random_delay_max')}")
    
    print("\n超时配置示例：")
    print(f"  page_goto_timeout: {cfg.get_timeout('page_goto_timeout')}")
    print(f"  search_result_timeout: {cfg.get_timeout('search_result_timeout')}")
    
    print("\n优化配置示例：")
    print(f"  enable_cache: {cfg.get_optimization('enable_cache')}")
    print(f"  clear_cache_on_init: {cfg.get_optimization('clear_cache_on_init')}")

