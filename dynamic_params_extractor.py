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
    
    def __init__(self, headless: bool = True, user_data_dir: Optional[str] = None):
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
        
    def _setup_driver(self) -> webdriver.Chrome:
        """设置Chrome驱动"""
        options = Options()
        
        if self.headless:
            options.add_argument('--headless')
            
        if self.user_data_dir:
            options.add_argument(f'--user-data-dir={self.user_data_dir}')
            
        # 启用网络日志
        options.add_argument('--enable-logging')
        options.add_argument('--log-level=0')
        options.add_experimental_option('useAutomationExtension', False)
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_argument('--disable-blink-features=AutomationControlled')
        
        # 设置性能日志
        caps = {
            'goog:loggingPrefs': {
                'performance': 'ALL',
                'browser': 'ALL'
            }
        }
        options.set_capability('goog:loggingPrefs', caps['goog:loggingPrefs'])
        
        # 随机User-Agent
        user_agents = [
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'
        ]
        options.add_argument(f'--user-agent={random.choice(user_agents)}')
        
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            
            # 设置窗口大小
            driver.set_window_size(1920, 1080)
            
            # 执行反检测脚本
            driver.execute_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
            """)
            
            return driver
            
        except Exception as e:
            logger.error(f"❌ 创建Chrome驱动失败: {e}")
            raise
            
    def extract_params_from_question(self, question_id: str, wait_time: int = 10) -> Optional[Dict]:
        """
        从问题页面提取反爬虫参数
        
        Args:
            question_id: 问题ID
            wait_time: 等待时间（秒）
            
        Returns:
            包含反爬虫参数的字典，失败返回None
        """
        question_url = f"https://www.zhihu.com/question/{question_id}"
        return self.extract_params_from_url(question_url, wait_time)
        
    def extract_params_from_url(self, url: str, wait_time: int = 10) -> Optional[Dict]:
        """
        从指定URL提取反爬虫参数
        
        Args:
            url: 目标URL
            wait_time: 等待时间（秒）
            
        Returns:
            包含反爬虫参数的字典，失败返回None
        """
        logger.info(f"🔍 开始从 {url} 提取反爬虫参数")
        
        try:
            if not self.driver:
                self.driver = self._setup_driver()
                
            # 访问页面
            self.driver.get(url)
            
            # 等待页面加载
            WebDriverWait(self.driver, wait_time).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # 模拟用户行为，触发feeds请求
            self._simulate_user_behavior()
            
            # 等待网络请求
            time.sleep(3)
            
            # 提取参数
            params = self._extract_params_from_logs()
            
            if params:
                logger.info(f"✅ 成功提取参数: session_id={params.get('session_id', 'N/A')[:20]}...")
                return params
            else:
                logger.warning("⚠️ 未能从网络日志中提取到有效参数")
                return None
                
        except TimeoutException:
            logger.error(f"❌ 页面加载超时: {url}")
            return None
        except Exception as e:
            logger.error(f"❌ 提取参数时出错: {e}")
            return None
            
    def _simulate_user_behavior(self):
        """模拟用户行为，触发feeds API请求"""
        try:
            # 滚动页面
            self.driver.execute_script("window.scrollTo(0, 500);")
            time.sleep(1)
            
            # 查找并点击"查看全部回答"按钮
            try:
                view_all_button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), '查看全部') or contains(text(), '更多回答')]")),
                )
                view_all_button.click()
                time.sleep(2)
            except TimeoutException:
                logger.debug("未找到'查看全部回答'按钮，继续其他操作")
                
            # 继续滚动，触发懒加载
            for i in range(3):
                self.driver.execute_script(f"window.scrollTo(0, {(i+2)*500});")
                time.sleep(1)
                
        except Exception as e:
            logger.debug(f"模拟用户行为时出错: {e}")
            
    def _extract_params_from_logs(self) -> Optional[Dict]:
        """从浏览器网络日志中提取参数"""
        try:
            logs = self.driver.get_log('performance')
            
            for log in logs:
                try:
                    message = json.loads(log['message'])
                    
                    # 查找feeds API请求
                    if (message.get('message', {}).get('method') == 'Network.requestWillBeSent'):
                        request = message['message']['params']['request']
                        url = request.get('url', '')
                        
                        if '/api/v4/questions/' in url and '/feeds' in url:
                            headers = request.get('headers', {})
                            
                            # 提取关键参数
                            params = {
                                'x_zse_96': headers.get('x-zse-96'),
                                'x_zst_81': headers.get('x-zst-81'),
                                'session_id': self._extract_session_id(headers.get('cookie', '')),
                                'user_agent': headers.get('user-agent'),
                                'referer': headers.get('referer'),
                                'timestamp': int(time.time())
                            }
                            
                            # 验证参数完整性
                            if params['x_zse_96'] and params['x_zst_81'] and params['session_id']:
                                return params
                                
                except (json.JSONDecodeError, KeyError) as e:
                    continue
                    
            return None
            
        except Exception as e:
            logger.error(f"❌ 解析网络日志失败: {e}")
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
        
    def batch_extract_params(self, question_ids: List[str], max_workers: int = 3) -> List[Dict]:
        """
        批量提取多个问题的反爬虫参数
        
        Args:
            question_ids: 问题ID列表
            max_workers: 最大并发数
            
        Returns:
            参数字典列表
        """
        logger.info(f"🔄 开始批量提取 {len(question_ids)} 个问题的参数")
        
        params_list = []
        
        for i, question_id in enumerate(question_ids, 1):
            logger.info(f"📋 处理第 {i}/{len(question_ids)} 个问题: {question_id}")
            
            params = self.extract_params_from_question(question_id)
            if params:
                params['question_id'] = question_id
                params_list.append(params)
                logger.info(f"✅ 第 {i} 个问题参数提取成功")
            else:
                logger.warning(f"⚠️ 第 {i} 个问题参数提取失败")
                
            # 添加随机延时，避免被检测
            if i < len(question_ids):
                delay = random.uniform(2, 5)
                logger.debug(f"⏱️ 等待 {delay:.1f} 秒...")
                time.sleep(delay)
                
        logger.info(f"🎉 批量提取完成，成功 {len(params_list)}/{len(question_ids)} 个")
        return params_list
        
    def validate_params(self, params: Dict) -> bool:
        """
        验证参数有效性
        
        Args:
            params: 参数字典
            
        Returns:
            参数是否有效
        """
        required_fields = ['x_zse_96', 'x_zst_81', 'session_id']
        
        # 检查必需字段
        for field in required_fields:
            if not params.get(field):
                logger.warning(f"⚠️ 参数验证失败: 缺少 {field}")
                return False
                
        # 检查参数格式
        if not params['x_zse_96'].startswith('2.0_'):
            logger.warning("⚠️ x-zse-96 格式不正确")
            return False
            
        if not params['x_zst_81'].startswith('3_2.0'):
            logger.warning("⚠️ x-zst-81 格式不正确")
            return False
            
        # 检查时效性（参数不应超过1小时）
        if 'timestamp' in params:
            age = time.time() - params['timestamp']
            if age > 3600:  # 1小时
                logger.warning(f"⚠️ 参数已过期，年龄: {age/60:.1f} 分钟")
                return False
                
        return True
        
    def close(self):
        """关闭浏览器驱动"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("🔒 浏览器驱动已关闭")
            except Exception as e:
                logger.warning(f"⚠️ 关闭浏览器驱动时出错: {e}")
            finally:
                self.driver = None
                
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()