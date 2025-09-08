#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版Cookies导出脚本
通过浏览器开发者工具手动复制cookies
"""

import json
import os
from datetime import datetime

def parse_cookie_string(cookie_string):
    """解析浏览器复制的cookie字符串"""
    cookies = []
    
    # 按分号分割cookie字符串
    cookie_pairs = cookie_string.split(';')
    
    for pair in cookie_pairs:
        pair = pair.strip()
        if '=' in pair:
            name, value = pair.split('=', 1)
            name = name.strip()
            value = value.strip()
            
            cookie = {
                "name": name,
                "value": value,
                "domain": ".zhihu.com",
                "path": "/",
                "secure": True,
                "httpOnly": False
            }
            cookies.append(cookie)
    
    return cookies

def parse_browser_export_format(lines):
    """解析浏览器导出的表格格式数据"""
    cookies = []
    
    # 跳过空行
    lines = [line.strip() for line in lines if line.strip()]
    
    i = 0
    while i < len(lines):
        try:
            # 每个cookie占用多行
            if i + 4 < len(lines):
                name = lines[i].strip()
                value = lines[i + 1].strip()
                domain = lines[i + 2].strip()
                path = lines[i + 3].strip()
                
                # 跳过一些可能的额外信息行
                expires_line = ""
                j = i + 4
                while j < len(lines) and j < i + 8:
                    if "2026" in lines[j] or "2025" in lines[j] or "Session" in lines[j]:
                        expires_line = lines[j].strip()
                        break
                    j += 1
                
                cookie = {
                    "name": name,
                    "value": value,
                    "domain": domain,
                    "path": path,
                    "secure": True,
                    "httpOnly": False
                }
                
                # 处理过期时间
                if expires_line and "Session" not in expires_line:
                    try:
                        # 尝试解析ISO格式的时间
                        if "T" in expires_line and "Z" in expires_line:
                            cookie["expires"] = expires_line
                    except:
                        pass
                
                cookies.append(cookie)
                print(f"解析cookie: {name} = {value[:50]}{'...' if len(value) > 50 else ''}")
                
                # 移动到下一个cookie（通常间隔6-8行）
                i += 8
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
    print("简化版Cookies导出工具")
    print("=" * 50)
    print("\n使用方法:")
    print("1. 在Chrome中打开 https://www.zhihu.com")
    print("2. 按F12打开开发者工具")
    print("3. 切换到 Application -> Cookies -> https://www.zhihu.com")
    print("4. 选择所有cookies并复制")
    print("\n选择导入方式:")
    print("1. 粘贴cookie字符串 (格式: name1=value1; name2=value2; ...)")
    print("2. 粘贴浏览器表格数据 (多行格式)")
    
    choice = input("\n请选择 (1 或 2): ").strip()
    
    if choice == "1":
        print("\n请粘贴cookie字符串 (按回车结束):")
        cookie_string = input().strip()
        
        if not cookie_string:
            print("未输入cookie字符串")
            return
        
        cookies = parse_cookie_string(cookie_string)
        
    elif choice == "2":
        print("\n请粘贴浏览器表格数据 (输入空行结束):")
        lines = []
        while True:
            line = input()
            if not line.strip():
                break
            lines.append(line)
        
        if not lines:
            print("未输入数据")
            return
        
        cookies = parse_browser_export_format(lines)
        
    else:
        print("无效选择")
        return
    
    if not cookies:
        print("未解析到任何cookies")
        return
    
    # 保存cookies
    save_cookies(cookies)
    
    # 显示重要cookies
    important_cookies = ['z_c0', 'd_c0', '_zap', 'q_c1', 'tst', '_xsrf']
    print("\n重要cookies:")
    found_important = False
    for cookie in cookies:
        if cookie['name'] in important_cookies:
            value = cookie['value']
            display_value = value[:50] + '...' if len(str(value)) > 50 else value
            print(f"  {cookie['name']}: {display_value}")
            found_important = True
    
    if not found_important:
        print("  未找到重要的登录cookies，请确保已登录知乎")
    
    print("\n现在可以运行以下命令测试API:")
    print("python3 check_api_cookies.py")

if __name__ == "__main__":
    main()