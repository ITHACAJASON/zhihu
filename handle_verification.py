#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知乎人机验证处理脚本
当API返回403错误并要求验证时，使用此脚本处理
"""

import time
import json
import pickle
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

def setup_driver():
    """设置Chrome浏览器"""
    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def load_cookies_to_browser(driver, cookies_file):
    """加载cookies到浏览器"""
    try:
        # 先访问知乎主页
        driver.get('https://www.zhihu.com')
        time.sleep(2)
        
        # 加载cookies
        if cookies_file.endswith('.pkl'):
            with open(cookies_file, 'rb') as f:
                cookies = pickle.load(f)
                for cookie in cookies:
                    try:
                        driver.add_cookie({
                            'name': cookie['name'],
                            'value': cookie['value'],
                            'domain': cookie.get('domain', '.zhihu.com'),
                            'path': cookie.get('path', '/'),
                            'secure': cookie.get('secure', False)
                        })
                    except Exception as e:
                        print(f"添加cookie失败: {e}")
        elif cookies_file.endswith('.json'):
            with open(cookies_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
                for cookie in cookies:
                    try:
                        driver.add_cookie({
                            'name': cookie['name'],
                            'value': cookie['value'],
                            'domain': cookie.get('domain', '.zhihu.com'),
                            'path': cookie.get('path', '/'),
                            'secure': cookie.get('secure', False)
                        })
                    except Exception as e:
                        print(f"添加cookie失败: {e}")
        
        print("Cookies加载完成")
        return True
    except Exception as e:
        print(f"加载cookies失败: {e}")
        return False

def handle_verification(verification_url):
    """处理人机验证"""
    print(f"检测到需要人机验证: {verification_url}")
    print("正在启动浏览器进行验证...")
    
    driver = setup_driver()
    
    try:
        # 加载现有cookies
        load_cookies_to_browser(driver, 'cache/zhihu_cookies.pkl')
        
        # 访问验证页面
        driver.get(verification_url)
        print("请在浏览器中完成人机验证...")
        
        # 等待用户完成验证
        print("等待验证完成，请在浏览器中操作...")
        print("验证完成后，请按回车键继续...")
        input()
        
        # 验证完成后，保存新的cookies
        cookies = driver.get_cookies()
        
        # 保存为pickle格式
        with open('cache/zhihu_cookies.pkl', 'wb') as f:
            pickle.dump(cookies, f)
        
        # 保存为JSON格式
        with open('cookies/zhihu_cookies.json', 'w', encoding='utf-8') as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        
        print("新的cookies已保存")
        
        # 测试验证是否成功
        test_url = "https://www.zhihu.com/api/v4/questions/1912780463006782640/feeds?cursor=ee671897bdd2e1fc2ce973090620b7b9&include=data%5B%2A%5D.is_normal&limit=5&offset=2&order=default&platform=desktop&session_id=1755767448795417470&ws_qiangzhisafe=0"
        driver.get(test_url)
        time.sleep(3)
        
        page_source = driver.page_source
        if '"error"' not in page_source and '"data"' in page_source:
            print("✓ 验证成功！API现在可以正常访问")
            return True
        else:
            print("验证可能未完成，请重试")
            return False
            
    except Exception as e:
        print(f"验证过程中出错: {e}")
        return False
    finally:
        driver.quit()

def main():
    """主函数"""
    verification_url = "https://www.zhihu.com/account/unhuman?type=Q8J2L3&need_login=false&session=5ce0198591dfdc49c36534d1aa80cecb&next=%2Fquestion%2F1912780463006782640"
    
    print("知乎人机验证处理工具")
    print("=" * 50)
    
    success = handle_verification(verification_url)
    
    if success:
        print("\n验证完成！现在可以重新运行API测试")
        print("运行命令: python3 postgres_main.py test-api")
    else:
        print("\n验证失败，请重试或手动访问知乎完成验证")

if __name__ == "__main__":
    main()