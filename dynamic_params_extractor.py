#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
动态反爬虫参数提取器

从真实浏览器请求中提取知乎API所需的反爬虫参数
"""

import json
import time
import re
from typing import Dict, Optional, List
from urllib.parse import urlparse, parse_qs
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from loguru import logger
import random


class DynamicParamsExtractor:
    """动态反爬虫参数提取器"""
    
    def __init__(self, headless: bool = False, user_data_dir: Optional[str] = None):
        """
        初始化参数提取器
        
        Args:
            headless: 是否使用无头模式
            user_data_dir: Chrome用户数据目录，用于保持登录状态
        """
        self.headless = headless
        self.user_data_dir = user_data_dir
        self.driver = None
        self.network_logs = []
        self._extracted_params = None
        
    def __enter__(self):
        """上下文管理器入口"""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
        
    def _setup_driver(self) -> webdriver.Chrome:
        """设置Chrome驱动"""
        options = Options()
        
        if self.headless:
            options.add_argument('--headless=new')  # 使用新版无头模式
            # 设置窗口大小，模拟真实显示器
            options.add_argument('--window-size=1920,1080')
        else:
            # 非无头模式下确保浏览器可见
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu-sandbox')
            options.add_argument('--remote-debugging-port=9222')
            # Mac系统特定配置，确保窗口可见
            options.add_argument('--disable-background-timer-throttling')
            options.add_argument('--disable-backgrounding-occluded-windows')
            options.add_argument('--disable-renderer-backgrounding')
            options.add_argument('--new-window')
            
        if self.user_data_dir:
            options.add_argument(f'--user-data-dir={self.user_data_dir}')
        
        # 增强反自动化检测能力
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('useAutomationExtension', False)
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        
        # 模拟更真实的浏览器环境
        options.add_argument('--disable-web-security')
        options.add_argument('--allow-running-insecure-content')
        options.add_argument('--lang=zh-CN,zh,en-US,en')
        options.add_argument('--disable-features=IsolateOrigins,site-per-process')
        
        # 启用网络日志
        options.add_argument('--enable-logging')
        options.add_argument('--log-level=0')
        
        # 设置性能日志
        caps = {
            'goog:loggingPrefs': {
                'performance': 'ALL',
                'browser': 'ALL'
            }
        }
        options.set_capability('goog:loggingPrefs', caps['goog:loggingPrefs'])
        
        # 随机User-Agent - 扩展更多选项
        user_agents = [
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0'
        ]
        options.add_argument(f'--user-agent={random.choice(user_agents)}')
        
        try:
            # 为Mac ARM64架构优化ChromeDriver安装
            try:
                # 尝试使用系统安装的ChromeDriver
                import shutil
                system_chromedriver = shutil.which('chromedriver')
                if system_chromedriver:
                    logger.info(f"🔍 使用系统ChromeDriver: {system_chromedriver}")
                    service = Service(system_chromedriver)
                else:
                    # 使用webdriver-manager，指定正确的架构
                    from webdriver_manager.chrome import ChromeDriverManager
                    from webdriver_manager.utils import ChromeType
                    logger.info("📥 下载适用于当前系统的ChromeDriver...")
                    service = Service(ChromeDriverManager().install())
            except Exception as e:
                logger.warning(f"ChromeDriver自动安装失败: {e}，尝试使用默认方式")
                service = Service(ChromeDriverManager().install())
                
            driver = webdriver.Chrome(service=service, options=options)
            driver.set_window_size(1280, 800)
            return driver
            
        except Exception as e:
            logger.error(f"设置Chrome驱动失败: {e}")
            raise
    
    def extract_params_from_url(self, url: str, timeout: int = 60) -> Optional[Dict]:
        """从URL中提取参数
        
        Args:
            url: 知乎问题URL
            timeout: 超时时间（秒）
            
        Returns:
            提取的参数字典，如果失败则返回None
        """
        logger.info(f"🔍 从URL提取参数: {url}")
        
        # 检查驱动是否已初始化
        if not self.driver:
            try:
                self.driver = self._setup_driver()
            except Exception as e:
                logger.error(f"初始化驱动失败: {e}")
                return None
        
        try:
            # 访问页面
            self.driver.get(url)
            logger.info("✅ 页面加载中...")
            
            # 等待页面加载完成
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # 模拟用户行为触发feeds请求
            params = self._simulate_user_behavior()
            
            # 如果已经提取到参数，直接返回
            if params:
                return params
                
            # 否则等待并尝试从日志中提取
            logger.info("⏳ 等待网络请求完成...")
            time.sleep(2)  # 给网络请求一些时间完成
            
            # 从网络日志中提取参数
            return self._extract_params_from_logs()
            
        except Exception as e:
            logger.error(f"提取参数失败: {e}")
            return None
            
    def _simulate_user_behavior(self) -> Optional[Dict]:
        """模拟用户行为并提取参数"""
        try:
            if self.headless:
                # 无头模式下自动滚动页面
                params = self._auto_scroll_and_trigger_feeds()
                if params:
                    return params
                else:
                    logger.warning("⚠️ 未能捕获到请求参数，请尝试手动模式")
                    return None
            else:
                # 非无头模式下提示用户操作
                logger.info("🖱️ 请在浏览器中操作:")
                logger.info("   1. 向下滚动页面")
                logger.info("   2. 等待页面加载更多回答")
                logger.info("   3. 完成后在此输入 'done'")
                
                while True:
                    user_input = input("👉 输入'done'继续，或'help'查看帮助: ")
                    if user_input == 'done':
                        # 尝试从日志中提取参数
                        extracted_params = self._extract_params_from_logs()
                        
                        # 将提取的参数存储到实例变量中
                        self._extracted_params = extracted_params
                        return self._extracted_params
                        
                    elif user_input == 'help':
                        logger.info("💡 操作提示:")
                        logger.info("   - 在浏览器中向下滚动页面")
                        logger.info("   - 等待页面加载更多回答")
                        logger.info("   - 看到新内容出现后输入 'done'")
                    else:
                        logger.info("请输入 'done' 继续，或输入 'help' 查看帮助")
        except Exception as e:
            logger.error(f"用户操作模式出错: {e}")
            return None
            
    def _extract_params_from_logs(self) -> Optional[Dict]:
        """从浏览器网络日志中提取参数"""
        logger.info("📊 开始分析性能日志...")
        
        # 检查是否已经在_simulate_user_behavior中提取了参数
        if hasattr(self, '_extracted_params') and self._extracted_params:
            logger.info("✅ 使用已提取的参数")
            return self._extracted_params
        
        try:
            # 尝试获取不同类型的日志
            logs = []
            try:
                logs = self.driver.get_log('performance')
                logger.info(f"📊 获取到 {len(logs)} 条性能日志")
            except Exception as e:
                logger.warning(f"获取性能日志失败: {e}，尝试获取浏览器日志")
                try:
                    logs = self.driver.get_log('browser')
                    logger.info(f"📊 获取到 {len(logs)} 条浏览器日志")
                except Exception as e:
                    logger.warning(f"获取浏览器日志失败: {e}")
            
            # 分析feeds请求和提取参数
            feeds_requests = []
            api_requests = []
            
            for entry in logs:
                try:
                    message = json.loads(entry['message'])
                    log = message.get('message', {})
                    method = log.get('method')
                    
                    # 检查多种网络事件类型
                    if method == 'Network.requestWillBeSent':
                        params = log.get('params', {})
                        request = params.get('request', {})
                        url = request.get('url', '')
                        
                        if '/feeds' in url:
                            feeds_requests.append({
                                'url': url,
                                'headers': request.get('headers', {}),
                                'type': 'requestWillBeSent'
                            })
                            logger.info(f"✅ 发现feeds请求: {url}")
                        elif 'zhihu.com/api' in url:
                            api_requests.append({
                                'url': url,
                                'headers': request.get('headers', {}),
                                'type': 'requestWillBeSent'
                            })
                            logger.info(f"✅ 发现API请求: {url}")
                    elif method == 'Network.requestWillBeSentExtraInfo':
                        params = log.get('params', {})
                        headers = params.get('headers', {})
                        
                        # 查找对应的feeds请求并更新headers
                        for req in feeds_requests:
                            if any(key.lower().startswith('x-zse') for key in headers.keys()):
                                req['headers'].update(headers)
                                logger.info("✅ 更新了请求头信息")
                except (KeyError, json.JSONDecodeError):
                    continue
            
            logger.info(f"🎯 共发现 {len(feeds_requests)} 个feeds请求")
            logger.info(f"📡 共发现 {len(api_requests)} 个API请求")
            
            # 尝试从找到的请求中提取参数
            all_requests = feeds_requests + api_requests
            for req in all_requests:
                headers = req['headers']
                logger.info(f"📋 检查请求头: {list(headers.keys())}")
                
                # 提取关键参数
                params = {
                    'x_zse_96': headers.get('x-zse-96') or headers.get('X-Zse-96'),
                    'x_zst_81': headers.get('x-zst-81') or headers.get('X-Zst-81'),
                    'x_zse_93': headers.get('x-zse-93') or headers.get('X-Zse-93') or '101_3_3.0',  # 提供默认值
                    'x_xsrftoken': headers.get('x-xsrftoken') or headers.get('X-Xsrftoken'),
                    'x_zse_83': headers.get('x-zse-83') or headers.get('X-Zse-83'),
                    'x_du_bid': headers.get('x-du-bid') or headers.get('X-Du-Bid'),
                    'session_id': self._extract_session_id(headers.get('cookie', '') or headers.get('Cookie', '')),
                    'user_agent': headers.get('user-agent') or headers.get('User-Agent'),
                    'referer': headers.get('referer') or headers.get('Referer') or 'https://www.zhihu.com/',
                    'timestamp': int(time.time())
                }
                
                # 尝试从cookie中提取更多参数
                cookie_str = headers.get('cookie', '') or headers.get('Cookie', '')
                if cookie_str:
                    d_c0_match = re.search(r'd_c0=([^;]+)', cookie_str)
                    if d_c0_match and not params['x_zst_81']:
                        params['x_zst_81'] = d_c0_match.group(1)
                
                logger.info(f"🔑 提取的参数: x_zse_96={bool(params['x_zse_96'])}, x_zst_81={bool(params['x_zst_81'])}, session_id={bool(params['session_id'])}")
                
                # 验证参数完整性 - 放宽条件
                if (params['x_zse_96'] or params['x_zse_93']) and (params['x_zst_81'] or params['session_id']) and params['user_agent']:
                    logger.info("✅ 成功提取到足够参数")
                    # 确保x_zse_96存在，如果没有则使用x_zse_93
                    if not params['x_zse_96'] and params['x_zse_93']:
                        params['x_zse_96'] = params['x_zse_93']
                    # 确保x_zst_81存在，如果没有则使用session_id
                    if not params['x_zst_81'] and params['session_id']:
                        params['x_zst_81'] = params['session_id']
                    return params
            
            # 如果没有从请求头中找到完整参数，尝试从cookies中提取
            try:
                cookies = self.driver.get_cookies()
                if cookies:
                    logger.info(f"✅ 获取到 {len(cookies)} 个cookies")
                    cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
                    
                    # 构建基本参数
                    params = {
                        'session_id': cookie_dict.get('z_c0') or cookie_dict.get('_zap'),
                        'x_zst_81': cookie_dict.get('d_c0'),  # 尝试使用d_c0作为替代
                        'user_agent': self.driver.execute_script("return navigator.userAgent;"),
                        'timestamp': int(time.time())
                    }
                    
                    if params['session_id'] and params['user_agent']:
                        logger.info("✅ 从cookies中提取到基本参数")
                        return params
            except Exception as e:
                logger.warning(f"从cookies提取参数失败: {e}")
            
            logger.warning("⚠️ 未找到包含完整参数的请求")
            return None
            
        except Exception as e:
            logger.error(f"提取参数时出错: {e}")
            return None
            
    def _extract_session_id(self, cookie_string: str) -> Optional[str]:
        """从cookie字符串中提取session_id"""
        if not cookie_string:
            return None
            
        # 查找各种可能的session标识
        patterns = [
            r'z_c0=([^;]+)',
            r'session_id=([^;]+)',
            r'_zap=([^;]+)',
            r'tst=([^;]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, cookie_string)
            if match:
                return match.group(1)
                
        return None
        
    def _auto_scroll_and_trigger_feeds(self, max_scrolls: int = 15, scroll_delay: float = 1.0, timeout: int = 45) -> Optional[Dict]:
        """自动滚动页面并触发feeds请求，提取参数
        
        Args:
            max_scrolls: 最大滚动次数
            scroll_delay: 每次滚动后的延迟时间（秒）
            timeout: 超时时间（秒）
            
        Returns:
            提取的参数字典，如果失败则返回None
        """
        logger.info("🖱️ 自动滚动页面触发请求...")
        
        # 导入必要的模块
        from selenium.webdriver.common.action_chains import ActionChains
        from selenium.webdriver.common.keys import Keys
        import random
        
        # 尝试直接从页面获取cookies
        try:
            cookies = self.driver.get_cookies()
            if cookies:
                logger.info(f"✅ 获取到 {len(cookies)} 个cookies")
                cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
                # 构建基本参数
                params = {
                    'session_id': cookie_dict.get('z_c0') or cookie_dict.get('_zap'),
                    'x_zst_81': cookie_dict.get('d_c0'),  # 尝试使用d_c0作为替代
                    'user_agent': self.driver.execute_script("return navigator.userAgent;"),
                    'timestamp': int(time.time())
                }
                
                if params['session_id'] and params['user_agent']:
                    logger.info("✅ 从cookies中提取到基本参数")
                    # 尝试获取更多参数
                    self._extracted_params = params
        except Exception as e:
            logger.warning(f"从cookies提取参数失败: {e}")
        
        # 等待页面完全加载
        logger.info("⏳ 等待页面完全加载...")
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".Question-main"))
            )
            logger.info("✅ 页面主体已加载")
        except TimeoutException:
            logger.warning("⚠️ 等待页面加载超时，继续执行")
        
        # 创建ActionChains对象用于模拟鼠标行为
        actions = ActionChains(self.driver)
        
        # 模拟初始鼠标移动和点击行为
        self._simulate_initial_interaction(actions)
        
        start_time = time.time()
        scroll_count = 0
        network_log_count = 0
        feeds_request_detected = False
        
        # 获取页面高度
        page_height = self.driver.execute_script("return document.body.scrollHeight")
        viewport_height = self.driver.execute_script("return window.innerHeight")
        
        while scroll_count < max_scrolls and time.time() - start_time < timeout:
            # 记录当前网络日志数量
            try:
                current_logs = self.driver.get_log('performance')
                network_log_count = len(current_logs)
                logger.info(f"📊 当前网络日志数量: {network_log_count}")
            except Exception as e:
                logger.warning(f"获取网络日志失败: {e}")
            
            # 随机化滚动行为
            scroll_type = random.choice(['smooth', 'chunk', 'pause'])
            scroll_distance = random.randint(300, 800)  # 随机滚动距离
            
            if scroll_type == 'smooth':
                # 平滑滚动
                logger.info(f"🖱️ 执行平滑滚动 ({scroll_distance}px)")
                for i in range(0, scroll_distance, 50):
                    self.driver.execute_script(f"window.scrollBy(0, 50);")
                    time.sleep(random.uniform(0.05, 0.15))  # 微小随机延迟
            elif scroll_type == 'chunk':
                # 块状滚动
                logger.info(f"🖱️ 执行块状滚动 ({scroll_distance}px)")
                self.driver.execute_script(f"window.scrollBy(0, {scroll_distance});")
            else:  # pause
                # 暂停滚动，模拟阅读
                logger.info("👀 模拟阅读暂停 (0.5-2秒)")
                time.sleep(random.uniform(0.5, 2.0))
                continue
            
            scroll_count += 1
            logger.info(f"⬇️ 滚动页面 ({scroll_count}/{max_scrolls})")
            
            # 随机模拟用户交互
            if random.random() < 0.3:  # 30%概率执行交互
                self._simulate_random_interaction(actions)
            
            # 等待新内容加载，随机延迟
            actual_delay = scroll_delay * random.uniform(0.8, 1.5)  # 随机化延迟
            time.sleep(actual_delay)
            
            # 检查是否有新的网络日志
            try:
                new_logs = self.driver.get_log('performance')
                new_log_count = len(new_logs)
                
                if new_log_count > network_log_count:
                    logger.info(f"📡 检测到新的网络请求: {new_log_count - network_log_count} 条")
                    
                    # 检查是否有feeds请求
                    for entry in new_logs:
                        try:
                            message = json.loads(entry['message'])
                            log = message.get('message', {})
                            method = log.get('method')
                            
                            if method == 'Network.requestWillBeSent':
                                params = log.get('params', {})
                                request = params.get('request', {})
                                url = request.get('url', '')
                                
                                if '/feeds' in url or 'zhihu.com/api' in url:
                                    feeds_request_detected = True
                                    logger.info(f"✅ 检测到目标请求: {url}")
                                    
                                    # 尝试提取参数
                                    params = self._extract_params_from_logs()
                                    if params:
                                        logger.info("✅ 成功提取参数")
                                        return params
                        except Exception as e:
                            continue
            except Exception as e:
                logger.warning(f"获取或分析网络日志失败: {e}")
            
            # 如果已经检测到feeds请求但未能提取参数，继续滚动
            if feeds_request_detected:
                logger.info("🔄 已检测到请求，继续滚动以获取更多数据...")
            
            # 检查是否已经滚动到页面底部，如果是则等待新内容加载
            current_scroll = self.driver.execute_script("return window.pageYOffset;")
            if current_scroll + viewport_height >= page_height - 200:  # 接近底部
                logger.info("⏳ 已接近页面底部，等待加载更多内容...")
                time.sleep(2)  # 等待加载更多
                # 重新获取页面高度
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height > page_height:
                    logger.info(f"📄 页面高度增加: {page_height} -> {new_height}")
                    page_height = new_height
        
        # 超时或达到最大滚动次数
        if time.time() - start_time >= timeout:
            logger.warning(f"⚠️ 自动滚动超时 ({timeout}秒)")
        else:
            logger.info(f"✅ 完成自动滚动 ({scroll_count}次)")
        
        # 最后一次尝试提取参数
        return self._extract_params_from_logs()
        
    def batch_extract_params(self, urls: List[str], timeout: int = 60) -> Dict[str, Optional[Dict]]:
        """批量提取多个问题的反爬虫参数
        
        Args:
            urls: 知乎问题URL列表
            timeout: 每个URL的超时时间（秒）
            
        Returns:
            URL到参数的映射字典
        """
        results = {}
        
        for url in urls:
            try:
                logger.info(f"🔄 处理URL: {url}")
                params = self.extract_params_from_url(url, timeout)
                results[url] = params
                
                if params:
                    logger.info(f"✅ 成功提取参数: {url}")
                else:
                    logger.warning(f"⚠️ 提取参数失败: {url}")
                    
            except Exception as e:
                logger.error(f"处理URL时出错: {url}, {e}")
                results[url] = None
                
        return results
        
    def extract_params_from_question(self, question_id: str, timeout: int = 60) -> Optional[Dict]:
        """从问题ID提取参数
        
        Args:
            question_id: 知乎问题ID
            timeout: 超时时间（秒）
            
        Returns:
            提取的参数字典，如果失败则返回None
        """
        url = f"https://www.zhihu.com/question/{question_id}"
        logger.info(f"🔍 从问题ID提取参数: {question_id}")
        return self.extract_params_from_url(url, timeout)
        
    def _simulate_initial_interaction(self, actions):
        """模拟初始用户交互行为
        
        Args:
            actions: ActionChains对象
        """
        try:
            logger.info("🖱️ 模拟初始用户交互...")
            
            # 随机移动鼠标到页面不同位置
            window_width = self.driver.execute_script("return window.innerWidth;")
            window_height = self.driver.execute_script("return window.innerHeight;")
            
            # 移动到标题区域
            try:
                title_element = self.driver.find_element(By.CSS_SELECTOR, "h1.QuestionHeader-title")
                actions.move_to_element(title_element)
                actions.pause(random.uniform(0.3, 0.8))
                actions.perform()
                logger.info("✅ 鼠标移动到标题区域")
            except Exception:
                # 如果找不到特定元素，移动到随机位置
                x, y = random.randint(100, window_width-100), random.randint(100, 300)
                actions.move_by_offset(x, y)
                actions.pause(random.uniform(0.3, 0.8))
                actions.perform()
                logger.info(f"✅ 鼠标移动到随机位置 ({x}, {y})")
            
            # 模拟阅读暂停
            time.sleep(random.uniform(1.0, 2.5))
            
        except Exception as e:
            logger.warning(f"模拟初始交互失败: {e}")
    
    def _simulate_random_interaction(self, actions):
        """模拟随机用户交互行为
        
        Args:
            actions: ActionChains对象
        """
        try:
            # 随机选择一种交互行为
            interaction_type = random.choice(['hover', 'click', 'pause', 'highlight'])
            
            if interaction_type == 'hover':
                # 尝试悬停在回答、评论或按钮上
                selectors = [
                    ".List-item", ".ContentItem", ".Button", ".QuestionHeader-title",
                    ".QuestionRichText", ".FollowButton", ".VoteButton"
                ]
                
                try:
                    # 随机选择一个选择器并找到元素
                    selector = random.choice(selectors)
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if elements:
                        # 随机选择一个元素
                        element = random.choice(elements)
                        # 滚动到元素可见
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                        # 悬停在元素上
                        actions.move_to_element(element)
                        actions.pause(random.uniform(0.3, 1.0))
                        actions.perform()
                        logger.info(f"✅ 鼠标悬停在元素上: {selector}")
                        return
                except Exception as e:
                    logger.debug(f"悬停交互失败: {e}")
                    
                # 如果找不到元素，移动到随机位置
                window_width = self.driver.execute_script("return window.innerWidth;")
                x, y = random.randint(100, window_width-100), random.randint(100, 300)
                actions.move_by_offset(x, y)
                actions.pause(random.uniform(0.3, 0.8))
                actions.perform()
                logger.info(f"✅ 鼠标移动到随机位置 ({x}, {y})")
                
            elif interaction_type == 'click':
                # 尝试点击安全的元素（展开更多、显示全部等）
                safe_click_selectors = [
                    ".QuestionRichText-more", ".ContentItem-expandButton",
                    ".Comments-actions button", ".Pagination button"
                ]
                
                try:
                    # 随机选择一个选择器并找到元素
                    selector = random.choice(safe_click_selectors)
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if elements:
                        # 随机选择一个元素
                        element = random.choice(elements)
                        # 滚动到元素可见
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                        # 点击元素
                        actions.move_to_element(element)
                        actions.pause(random.uniform(0.2, 0.5))
                        actions.click()
                        actions.perform()
                        logger.info(f"✅ 点击元素: {selector}")
                        # 等待内容加载
                        time.sleep(random.uniform(0.5, 1.5))
                        return
                except Exception as e:
                    logger.debug(f"点击交互失败: {e}")
            
            elif interaction_type == 'highlight':
                # 模拟文本选择/高亮
                try:
                    text_selectors = [".RichText", ".QuestionRichText", ".ContentItem-content"]
                    selector = random.choice(text_selectors)
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if elements:
                        element = random.choice(elements)
                        # 滚动到元素可见
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                        # 双击模拟选择文本
                        actions.move_to_element(element)
                        actions.pause(random.uniform(0.2, 0.5))
                        actions.double_click()
                        actions.perform()
                        logger.info(f"✅ 模拟文本选择: {selector}")
                        time.sleep(random.uniform(0.3, 0.8))
                        # 取消选择
                        actions.move_by_offset(50, 50).click().perform()
                        return
                except Exception as e:
                    logger.debug(f"文本选择交互失败: {e}")
            
            else:  # pause - 模拟阅读暂停
                pause_time = random.uniform(0.8, 2.0)
                logger.info(f"👀 模拟阅读暂停 ({pause_time:.1f}秒)")
                time.sleep(pause_time)
                
        except Exception as e:
            logger.warning(f"模拟随机交互失败: {e}")
    
    def validate_params(self, params: Dict) -> bool:
        """验证参数是否有效
        
        Args:
            params: 参数字典
            
        Returns:
            参数是否有效
        """
        if not params or not isinstance(params, dict):
            logger.warning("⚠️ 参数无效或不是字典类型")
            return False
            
        # 必须有user_agent
        if not params.get('user_agent'):
            logger.warning("⚠️ 缺少user_agent参数")
            return False
            
        # 确保有x_zse_93参数，如果没有则添加默认值
        if not params.get('x_zse_93'):
            params['x_zse_93'] = '101_3_3.0'
            logger.info("✅ 添加默认x_zse_93参数: 101_3_3.0")
        
        # 放宽条件：只要有user_agent和至少一个其他参数即可
        has_any_param = any([
            params.get('x_zse_96'),
            params.get('x_zst_81'),
            params.get('session_id'),
            params.get('x_zse_93'),
            params.get('x_xsrftoken')
        ])
        
        if not has_any_param:
            logger.warning("⚠️ 缺少任何关键参数")
            return False
        
        logger.info("✅ 参数验证通过")
        return True
        
    def close(self):
        """关闭浏览器驱动"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("✅ 已关闭浏览器驱动")
            except Exception as e:
                logger.error(f"关闭驱动时出错: {e}")
            finally:
                self.driver = None