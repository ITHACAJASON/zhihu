#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从文本格式导入Cookies脚本
处理用户提供的浏览器导出格式
"""

import json
import os
from datetime import datetime

def parse_cookies_from_text(text):
    """从文本格式解析cookies"""
    lines = text.strip().split('\n')
    cookies = []
    
    i = 0
    while i < len(lines):
        try:
            # 跳过空行
            while i < len(lines) and not lines[i].strip():
                i += 1
            
            if i >= len(lines):
                break
            
            # 读取cookie信息（每个cookie占用多行）
            if i + 4 < len(lines):
                name = lines[i].strip()
                value = lines[i + 1].strip()
                domain = lines[i + 2].strip()
                path = lines[i + 3].strip()
                
                # 查找过期时间
                expires_str = ""
                secure = False
                http_only = False
                
                # 检查接下来的几行
                for j in range(i + 4, min(i + 10, len(lines))):
                    line = lines[j].strip()
                    
                    # 检查是否是过期时间
                    if ('2025' in line or '2026' in line or 'Session' in line) and 'T' in line:
                        expires_str = line
                    elif line == '✓' or line.lower() == 'true':
                        # 可能是secure或httpOnly标志
                        if j == i + 6:  # 假设第7行是secure
                            secure = True
                        elif j == i + 7:  # 假设第8行是httpOnly
                            http_only = True
                    elif line.lower() == 'medium' or line.lower() == 'high':
                        # 优先级信息，跳过
                        pass
                
                # 创建cookie对象
                cookie = {
                    "name": name,
                    "value": value,
                    "domain": domain if domain.startswith('.') else f".{domain}",
                    "path": path,
                    "secure": secure,
                    "httpOnly": http_only
                }
                
                # 添加过期时间
                if expires_str and 'Session' not in expires_str:
                    cookie["expires"] = expires_str
                
                cookies.append(cookie)
                print(f"解析cookie: {name} = {value[:50]}{'...' if len(value) > 50 else ''}")
                
                # 移动到下一个cookie
                i += 10  # 通常每个cookie占用约10行
            else:
                i += 1
                
        except Exception as e:
            print(f"解析第{i}行时出错: {e}")
            i += 1
    
    return cookies

def save_cookies(cookies, filename="cookies/zhihu_cookies.json"):
    """保存cookies到文件"""
    # 确保目录存在
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ 已保存 {len(cookies)} 个cookies到: {filename}")

def main():
    """主函数"""
    print("从文本导入Cookies工具")
    print("=" * 50)
    print("\n使用方法:")
    print("1. 从浏览器开发者工具复制cookies数据")
    print("2. 粘贴到下面的输入框中")
    print("3. 输入空行结束")
    
    print("\n请粘贴cookies数据 (输入空行结束):")
    lines = []
    while True:
        try:
            line = input()
            if not line.strip():
                break
            lines.append(line)
        except KeyboardInterrupt:
            print("\n操作已取消")
            return
        except EOFError:
            break
    
    if not lines:
        print("未输入数据")
        return
    
    # 合并所有行
    text = '\n'.join(lines)
    
    # 解析cookies
    cookies = parse_cookies_from_text(text)
    
    if not cookies:
        print("未解析到任何cookies")
        return
    
    # 保存cookies
    save_cookies(cookies)
    
    # 显示重要cookies
    important_cookies = ['z_c0', 'd_c0', '_zap', 'q_c1', 'tst', '_xsrf', '__zse_ck']
    print("\n重要cookies:")
    found_important = False
    for cookie in cookies:
        if cookie['name'] in important_cookies:
            value = cookie['value']
            display_value = value[:50] + '...' if len(str(value)) > 50 else value
            print(f"  {cookie['name']}: {display_value}")
            found_important = True
    
    if not found_important:
        print("  未找到重要的登录cookies，请确保数据格式正确")
    
    print("\n现在可以运行以下命令测试API:")
    print("python3 check_api_cookies.py")

if __name__ == "__main__":
    main()