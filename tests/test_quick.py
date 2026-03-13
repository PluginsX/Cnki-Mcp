"""
CNKI MCP 服务快速测试脚本

简单测试基础功能是否正常
"""

import subprocess
import json
import sys
import time
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))


def send_mcp_request(process, method, params=None):
    """发送 MCP 请求"""
    request = {
        "jsonrpc": "2.0",
        "id": int(time.time() * 1000),
        "method": method,
        "params": params or {}
    }
    
    request_json = json.dumps(request) + "\n"
    process.stdin.write(request_json)
    process.stdin.flush()
    
    # 读取响应
    response_line = process.stdout.readline()
    if response_line:
        return json.loads(response_line)
    return None


def test_basic_functionality():
    """测试基础功能"""
    print("\n" + "=" * 60)
    print("CNKI MCP 服务快速测试")
    print("=" * 60)
    
    # 启动 MCP 服务
    print("\n正在启动 MCP 服务...")
    
    try:
        process = subprocess.Popen(
            [sys.executable, "-m", "cnki_mcp.server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            encoding='utf-8'
        )
        
        print("✓ MCP 服务已启动")
        
        # 等待服务初始化
        time.sleep(2)
        
        # 测试 1: 初始化
        print("\n" + "-" * 60)
        print("测试 1: 初始化连接")
        print("-" * 60)
        
        response = send_mcp_request(process, "initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        })
        
        if response and "result" in response:
            print("✓ 初始化成功")
            print(f"   服务名称: {response['result'].get('serverInfo', {}).get('name', 'N/A')}")
        else:
            print("✗ 初始化失败")
            return False
        
        # 测试 2: 列出工具
        print("\n" + "-" * 60)
        print("测试 2: 列出所有工具")
        print("-" * 60)
        
        response = send_mcp_request(process, "tools/list")
        
        if response and "result" in response:
            tools = response['result'].get('tools', [])
            print(f"✓ 找到 {len(tools)} 个工具:")
            for tool in tools:
                print(f"   - {tool.get('name', 'N/A')}")
        else:
            print("✗ 列出工具失败")
            return False
        
        print("\n" + "=" * 60)
        print("基础测试完成！")
        print("=" * 60)
        
        # 关闭进程
        process.terminate()
        process.wait(timeout=5)
        
        return True
        
    except Exception as e:
        print(f"\n✗ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_basic_functionality()
    sys.exit(0 if success else 1)

