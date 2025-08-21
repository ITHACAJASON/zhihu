#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知乎API监控脚本
使用Selenium打开知乎网页，监控真实的API请求
"""

import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.keys import Keys
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class ZhihuAPIMonitor:
    def __init__(self):
        self.driver = None
        self.api_requests = []
        self.wait = None
        
    def setup_driver(self):
        """设置Chrome浏览器"""
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # 启用网络日志
        chrome_options.add_argument('--enable-logging')
        chrome_options.add_argument('--log-level=0')
        chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.wait = WebDriverWait(self.driver, 10)
            logger.info("Chrome浏览器启动成功")
        except Exception as e:
            logger.error(f"浏览器启动失败: {e}")
            raise
    
    def load_cookies(self):
        """加载cookies"""
        try:
            import pickle
            with open('cache/zhihu_cookies.pkl', 'rb') as f:
                cookies = pickle.load(f)
            
            # 先访问知乎主页
            self.driver.get('https://www.zhihu.com')
            time.sleep(2)
            
            # 添加cookies
            if isinstance(cookies, list):
                for cookie in cookies:
                    try:
                        self.driver.add_cookie(cookie)
                    except Exception as e:
                        logger.warning(f"添加cookie失败: {e}")
            
            logger.info(f"成功加载 {len(cookies)} 个cookies")
            
        except Exception as e:
            logger.warning(f"加载cookies失败: {e}")
    
    def monitor_network_requests(self):
        """监控网络请求"""
        logs = self.driver.get_log('performance')
        
        for log in logs:
            try:
                message = json.loads(log['message'])
                
                if message['message']['method'] == 'Network.responseReceived':
                    url = message['message']['params']['response']['url']
                    
                    # 过滤知乎API请求
                    if ('zhihu.com/api' in url or 'api.zhihu.com' in url) and \
                       ('search' in url or 'question' in url or 'answer' in url or 'content' in url):
                        
                        request_info = {
                            'url': url,
                            'method': message['message']['params']['response'].get('method', 'GET'),
                            'status': message['message']['params']['response']['status'],
                            'headers': message['message']['params']['response']['headers'],
                            'timestamp': log['timestamp']
                        }
                        
                        self.api_requests.append(request_info)
                        logger.info(f"发现相关API请求: {url}")
                        logger.info(f"状态码: {request_info['status']}")
                        
            except Exception as e:
                continue
    
    def perform_search(self, keyword="Python编程"):
        """执行搜索操作"""
        logger.info(f"\n=== 执行搜索: {keyword} ===")
        
        try:
            # 访问知乎首页
            self.driver.get('https://www.zhihu.com')
            time.sleep(3)
            
            # 查找搜索框
            search_box = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder*='搜索']"))
            )
            
            # 清空并输入搜索关键词
            search_box.clear()
            search_box.send_keys(keyword)
            time.sleep(1)
            
            # 监控网络请求
            self.monitor_network_requests()
            
            # 按回车搜索
            search_box.send_keys(Keys.RETURN)
            time.sleep(3)
            
            # 监控搜索结果页面的API请求
            self.monitor_network_requests()
            
            # 尝试点击"内容"标签
            try:
                content_tab = self.driver.find_element(By.XPATH, "//button[contains(text(), '内容')]")
                content_tab.click()
                time.sleep(2)
                self.monitor_network_requests()
            except:
                logger.info("未找到内容标签")
            
            # 滚动页面加载更多内容
            for i in range(3):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                self.monitor_network_requests()
            
            logger.info("搜索操作完成")
            
        except Exception as e:
            logger.error(f"搜索操作失败: {e}")
    
    def visit_specific_question(self, question_id="19551137"):
        """访问特定问题页面"""
        logger.info(f"\n=== 访问问题页面: {question_id} ===")
        
        try:
            url = f"https://www.zhihu.com/question/{question_id}"
            self.driver.get(url)
            time.sleep(3)
            
            # 监控初始加载的API请求
            self.monitor_network_requests()
            
            # 滚动页面加载更多答案
            for i in range(5):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                self.monitor_network_requests()
            
            # 尝试点击"加载更多"按钮
            try:
                load_more_btn = self.driver.find_element(By.XPATH, "//button[contains(text(), '加载更多')]")
                load_more_btn.click()
                time.sleep(3)
                self.monitor_network_requests()
            except:
                logger.info("未找到加载更多按钮")
            
            logger.info("问题页面访问完成")
            
        except Exception as e:
            logger.error(f"访问问题页面失败: {e}")
    
    def analyze_api_patterns(self):
        """分析API模式"""
        if not self.api_requests:
            logger.warning("未发现任何相关API请求")
            return
        
        logger.info(f"\n=== API分析结果 ===")
        logger.info(f"总共发现 {len(self.api_requests)} 个相关API请求")
        
        # 按类型分类
        search_apis = [req for req in self.api_requests if 'search' in req['url']]
        question_apis = [req for req in self.api_requests if 'question' in req['url']]
        answer_apis = [req for req in self.api_requests if 'answer' in req['url']]
        content_apis = [req for req in self.api_requests if 'content' in req['url']]
        
        logger.info(f"\n搜索相关API: {len(search_apis)}个")
        for api in search_apis:
            logger.info(f"  - {api['url']}")
        
        logger.info(f"\n问题相关API: {len(question_apis)}个")
        for api in question_apis:
            logger.info(f"  - {api['url']}")
        
        logger.info(f"\n答案相关API: {len(answer_apis)}个")
        for api in answer_apis:
            logger.info(f"  - {api['url']}")
        
        logger.info(f"\n内容相关API: {len(content_apis)}个")
        for api in content_apis:
            logger.info(f"  - {api['url']}")
        
        # 分析URL模式
        logger.info(f"\n=== URL模式分析 ===")
        unique_patterns = set()
        for req in self.api_requests:
            # 提取基础URL模式（去掉查询参数和ID）
            base_url = req['url'].split('?')[0]
            # 替换数字ID为占位符
            import re
            pattern = re.sub(r'/\d+', '/{id}', base_url)
            unique_patterns.add(pattern)
        
        for pattern in sorted(unique_patterns):
            logger.info(f"  - {pattern}")
    
    def save_detailed_results(self):
        """保存详细结果"""
        if self.api_requests:
            # 保存完整的API请求日志
            with open('detailed_api_requests.json', 'w', encoding='utf-8') as f:
                json.dump(self.api_requests, f, ensure_ascii=False, indent=2)
            
            # 保存简化的URL列表
            urls = [req['url'] for req in self.api_requests]
            with open('api_urls.txt', 'w', encoding='utf-8') as f:
                for url in sorted(set(urls)):
                    f.write(url + '\n')
            
            logger.info(f"\n详细结果已保存到:")
            logger.info(f"  - detailed_api_requests.json (完整请求信息)")
            logger.info(f"  - api_urls.txt (URL列表)")
    
    def run(self):
        """运行监控"""
        try:
            logger.info("开始知乎API监控...")
            
            # 设置浏览器
            self.setup_driver()
            
            # 加载cookies
            self.load_cookies()
            
            # 执行搜索操作
            self.perform_search("Python编程")
            
            # 访问特定问题页面
            self.visit_specific_question("19551137")
            
            # 再次搜索不同关键词
            self.perform_search("机器学习")
            
            # 分析API模式
            self.analyze_api_patterns()
            
            # 保存结果
            self.save_detailed_results()
            
        except Exception as e:
            logger.error(f"监控过程出错: {e}")
        
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("浏览器已关闭")

def main():
    monitor = ZhihuAPIMonitor()
    monitor.run()

if __name__ == '__main__':
    main()