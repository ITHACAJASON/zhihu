#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
手动更新知乎cookies脚本
当自动验证失败时，使用此脚本手动更新cookies
"""

import json
import pickle
import os

def get_cookie_input(cookie_name, description):
    """获取用户输入的cookie值"""
    print(f"\n请从浏览器开发者工具中复制 {cookie_name} 的值")
    print(f"说明: {description}")
    value = input(f"请输入 {cookie_name} 的值 (直接回车跳过): ").strip()
    return value if value else None

def main():
    print("知乎Cookies手动更新工具")
    print("=" * 50)
    print("\n使用说明:")
    print("1. 在浏览器中完成知乎人机验证")
    print("2. 按F12打开开发者工具")
    print("3. 切换到 Application/应用程序 -> Cookies -> https://www.zhihu.com")
    print("4. 找到以下重要的cookies并复制其值")
    
    # 获取重要的cookies
    cookies_to_update = {
        'z_c0': '用户认证token，最重要的cookie',
        'd_c0': '设备标识cookie',
        '_zap': '会话标识cookie',
        'q_c1': '问题相关cookie',
        'tst': '时间戳cookie'
    }
    
    new_cookies = []
    
    for cookie_name, description in cookies_to_update.items():
        value = get_cookie_input(cookie_name, description)
        if value:
            new_cookies.append({
                'name': cookie_name,
                'value': value,
                'domain': '.zhihu.com',
                'path': '/',
                'secure': True,
                'httpOnly': False
            })
    
    if not new_cookies:
        print("\n没有输入任何cookies，退出程序")
        return
    
    # 尝试加载现有cookies并合并
    existing_cookies = []
    try:
        if os.path.exists('cache/zhihu_cookies.pkl'):
            with open('cache/zhihu_cookies.pkl', 'rb') as f:
                existing_cookies = pickle.load(f)
                print(f"\n加载了 {len(existing_cookies)} 个现有cookies")
    except Exception as e:
        print(f"\n加载现有cookies失败: {e}")
    
    # 合并cookies（新的覆盖旧的）
    cookie_dict = {}
    
    # 先添加现有cookies
    for cookie in existing_cookies:
        if isinstance(cookie, dict) and 'name' in cookie:
            cookie_dict[cookie['name']] = cookie
    
    # 再添加新cookies（覆盖同名的）
    for cookie in new_cookies:
        cookie_dict[cookie['name']] = cookie
    
    final_cookies = list(cookie_dict.values())
    
    # 确保目录存在
    os.makedirs('cache', exist_ok=True)
    os.makedirs('cookies', exist_ok=True)
    
    # 保存cookies
    try:
        # 保存为pickle格式
        with open('cache/zhihu_cookies.pkl', 'wb') as f:
            pickle.dump(final_cookies, f)
        
        # 保存为JSON格式
        with open('cookies/zhihu_cookies.json', 'w', encoding='utf-8') as f:
            json.dump(final_cookies, f, ensure_ascii=False, indent=2)
        
        print(f"\n✓ 成功保存 {len(final_cookies)} 个cookies")
        print("  - cache/zhihu_cookies.pkl")
        print("  - cookies/zhihu_cookies.json")
        
        # 显示保存的cookies名称
        cookie_names = [c['name'] for c in final_cookies]
        print(f"\n保存的cookies: {', '.join(cookie_names)}")
        
        print("\n现在可以运行以下命令测试API:")
        print("python3 postgres_main.py test-api")
        
    except Exception as e:
        print(f"\n保存cookies失败: {e}")

if __name__ == "__main__":
    main()