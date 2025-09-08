#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chrome浏览器Cookies导出脚本
自动从Chrome浏览器中提取知乎相关的cookies
"""

import sqlite3
import json
import os
import platform
from pathlib import Path
import base64
import subprocess
from datetime import datetime, timezone

def get_chrome_cookies_path():
    """获取Chrome cookies数据库路径"""
    system = platform.system()
    
    if system == "Darwin":  # macOS
        return os.path.expanduser("~/Library/Application Support/Google/Chrome/Default/Cookies")
    elif system == "Windows":
        return os.path.expanduser("~/AppData/Local/Google/Chrome/User Data/Default/Cookies")
    elif system == "Linux":
        return os.path.expanduser("~/.config/google-chrome/Default/Cookies")
    else:
        raise Exception(f"不支持的操作系统: {system}")

def decrypt_chrome_password(encrypted_value):
    """解密Chrome加密的cookie值 (仅适用于macOS)"""
    try:
        # 在macOS上，Chrome使用Keychain来加密cookies
        if platform.system() == "Darwin":
            # 尝试使用security命令获取Chrome Safe Storage密钥
            cmd = [
                "security", "find-generic-password",
                "-w", "-s", "Chrome Safe Storage",
                "-a", "Chrome"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                key = result.stdout.strip()
                # 这里需要更复杂的解密逻辑，暂时返回原值
                return encrypted_value.decode('utf-8', errors='ignore')
        return encrypted_value.decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"解密失败: {e}")
        return str(encrypted_value)

def extract_chrome_cookies(domain="zhihu.com"):
    """从Chrome中提取指定域名的cookies"""
    cookies_path = get_chrome_cookies_path()
    
    if not os.path.exists(cookies_path):
        raise FileNotFoundError(f"Chrome cookies文件不存在: {cookies_path}")
    
    # 复制cookies文件到临时位置（因为Chrome可能正在使用）
    temp_cookies_path = "/tmp/chrome_cookies_temp.db"
    import shutil
    try:
        shutil.copy2(cookies_path, temp_cookies_path)
    except Exception as e:
        print(f"警告: 无法复制cookies文件，尝试直接读取: {e}")
        temp_cookies_path = cookies_path
    
    cookies = []
    
    try:
        # 连接到SQLite数据库
        conn = sqlite3.connect(temp_cookies_path)
        cursor = conn.cursor()
        
        # 查询cookies表结构
        cursor.execute("PRAGMA table_info(cookies)")
        columns = [column[1] for column in cursor.fetchall()]
        print(f"Cookies表字段: {columns}")
        
        # 查询知乎相关的cookies
        query = """
        SELECT name, value, host_key, path, expires_utc, is_secure, is_httponly, encrypted_value
        FROM cookies 
        WHERE host_key LIKE ? OR host_key LIKE ?
        ORDER BY name
        """
        
        cursor.execute(query, (f"%{domain}%", f"%.{domain}%"))
        rows = cursor.fetchall()
        
        print(f"找到 {len(rows)} 个相关cookies")
        
        for row in rows:
            name, value, host_key, path, expires_utc, is_secure, is_httponly, encrypted_value = row
            
            # 如果value为空但encrypted_value不为空，尝试解密
            if not value and encrypted_value:
                try:
                    value = decrypt_chrome_password(encrypted_value)
                except Exception as e:
                    print(f"解密cookie {name} 失败: {e}")
                    continue
            
            # 转换过期时间
            if expires_utc:
                # Chrome使用的是微秒时间戳，从1601年1月1日开始
                # 转换为标准Unix时间戳
                try:
                    # Chrome时间戳是从1601-01-01开始的微秒数
                    chrome_epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
                    unix_epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
                    epoch_diff = (unix_epoch - chrome_epoch).total_seconds()
                    
                    unix_timestamp = (expires_utc / 1000000) - epoch_diff
                    expires_date = datetime.fromtimestamp(unix_timestamp, tz=timezone.utc)
                    expires_iso = expires_date.isoformat()
                except Exception as e:
                    print(f"转换过期时间失败: {e}")
                    expires_iso = None
            else:
                expires_iso = None
            
            cookie_data = {
                "name": name,
                "value": value,
                "domain": host_key,
                "path": path,
                "expires": expires_iso,
                "secure": bool(is_secure),
                "httpOnly": bool(is_httponly)
            }
            
            cookies.append(cookie_data)
            print(f"提取cookie: {name} = {value[:50]}{'...' if len(str(value)) > 50 else ''}")
        
        conn.close()
        
        # 清理临时文件
        if temp_cookies_path != cookies_path and os.path.exists(temp_cookies_path):
            os.remove(temp_cookies_path)
            
    except Exception as e:
        print(f"读取cookies数据库失败: {e}")
        raise
    
    return cookies

def save_cookies_to_json(cookies, output_file="chrome_zhihu_cookies.json"):
    """保存cookies到JSON文件"""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print(f"Cookies已保存到: {output_file}")

def convert_to_zhihu_format(cookies):
    """转换为知乎爬虫需要的格式"""
    zhihu_cookies = []
    
    for cookie in cookies:
        zhihu_cookie = {
            "name": cookie["name"],
            "value": cookie["value"],
            "domain": cookie["domain"],
            "path": cookie["path"],
            "secure": cookie["secure"],
            "httpOnly": cookie["httpOnly"]
        }
        
        if cookie["expires"]:
            zhihu_cookie["expires"] = cookie["expires"]
        
        zhihu_cookies.append(zhihu_cookie)
    
    return zhihu_cookies

def main():
    """主函数"""
    print("Chrome浏览器Cookies导出工具")
    print("=" * 50)
    
    try:
        # 检查Chrome是否正在运行
        print("\n注意: 请确保Chrome浏览器已关闭，否则可能无法读取cookies数据库")
        input("按回车键继续...")
        
        # 提取cookies
        print("\n正在提取知乎相关cookies...")
        cookies = extract_chrome_cookies("zhihu.com")
        
        if not cookies:
            print("未找到知乎相关的cookies，请确保已在Chrome中登录知乎")
            return
        
        # 保存原始格式
        save_cookies_to_json(cookies, "chrome_zhihu_cookies_raw.json")
        
        # 转换为知乎爬虫格式
        zhihu_cookies = convert_to_zhihu_format(cookies)
        save_cookies_to_json(zhihu_cookies, "cookies/zhihu_cookies.json")
        
        # 显示重要cookies
        important_cookies = ['z_c0', 'd_c0', '_zap', 'q_c1', 'tst', '_xsrf']
        print("\n重要cookies:")
        for cookie in zhihu_cookies:
            if cookie['name'] in important_cookies:
                value = cookie['value']
                display_value = value[:50] + '...' if len(str(value)) > 50 else value
                print(f"  {cookie['name']}: {display_value}")
        
        print(f"\n✓ 成功提取 {len(cookies)} 个cookies")
        print("✓ 已保存到 cookies/zhihu_cookies.json")
        print("\n现在可以运行以下命令测试API:")
        print("python3 check_api_cookies.py")
        
    except Exception as e:
        print(f"\n❌ 提取失败: {e}")
        print("\n可能的解决方案:")
        print("1. 确保Chrome浏览器已完全关闭")
        print("2. 确保已在Chrome中登录知乎")
        print("3. 检查Chrome cookies文件路径是否正确")
        print("4. 尝试手动复制cookies（使用 update_cookies_manual.py）")

if __name__ == "__main__":
    main()