#!/usr/bin/env python3
"""
知乎爬虫主要模块 - PostgreSQL版本
支持实时数据存储和任务恢复机制
"""

import os
import time
import random
import re
import json
import pickle
from urllib.parse import urljoin, urlparse, parse_qs
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from loguru import logger

from config import ZhihuConfig
from postgres_models import PostgreSQLManager, TaskInfo, SearchResult, Question, Answer, Comment
from selenium.webdriver.chrome.service import Service


class PostgresZhihuCrawler:
    """知乎爬虫主类 - PostgreSQL版本"""
    
    def __init__(self, headless: bool = True, postgres_config: Dict = None):
        self.config = ZhihuConfig()
        self.headless = headless
        self.driver = None
        self.wait = None
        self.session_error_count = 0  # 会话错误计数器
        self.max_session_errors = 3   # 最大会话错误次数
        
        # 初始化PostgreSQL数据库管理器
        self.db = PostgreSQLManager(postgres_config)
        
        self.cache_dir = Path("cache")
        self.cache_dir.mkdir(exist_ok=True)
        self.setup_logger()
        self.setup_driver()
        
        # 尝试加载已保存的cookies
        self.load_cookies()
    
    def setup_logger(self):
        """设置日志"""
        self.config.create_directories()
        logger.add(
            self.config.LOG_FILE,
            rotation="100 MB",
            retention="30 days",
            level=self.config.LOG_LEVEL,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
            encoding="utf-8"
        )
    
    def setup_driver(self):
        """设置Chrome驱动"""
        try:
            options = Options()
            
            if self.headless:
                options.add_argument('--headless')
            
            # 基础配置
            options.add_argument(f'--window-size={self.config.WINDOW_SIZE[0]},{self.config.WINDOW_SIZE[1]}')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-blink-features=AutomationControlled')
            
            # 反检测配置
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # 使用Safari User-Agent（经测试效果最好）
            safari_ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"
            options.add_argument(f'--user-agent={safari_ua}')
            logger.info(f"使用优化的User-Agent: Safari")
            
            # 初始化驱动
            chromedriver_path = ChromeDriverManager().install()
            # 修复webdriver-manager路径问题
            if 'THIRD_PARTY_NOTICES.chromedriver' in chromedriver_path:
                import os
                chromedriver_dir = os.path.dirname(chromedriver_path)
                actual_chromedriver = os.path.join(chromedriver_dir, 'chromedriver')
                if os.path.exists(actual_chromedriver):
                    chromedriver_path = actual_chromedriver
            
            self.driver = webdriver.Chrome(
                service=Service(chromedriver_path),
                options=options
            )
            
            # 执行反检测脚本
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
            self.driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']})")
            
            logger.info("反检测脚本执行完成")
            
            self.wait = WebDriverWait(self.driver, self.config.ELEMENT_WAIT_TIMEOUT)
            
            logger.info("Chrome驱动初始化成功")
            
        except Exception as e:
            logger.error(f"Chrome驱动初始化失败: {e}")
            raise
    
    def save_cookies(self):
        """保存cookies到文件"""
        try:
            cookies_file = self.cache_dir / "zhihu_cookies.pkl"
            with open(cookies_file, 'wb') as f:
                pickle.dump(self.driver.get_cookies(), f)
            logger.info(f"Cookies已保存到: {cookies_file}")
        except Exception as e:
            logger.warning(f"保存cookies失败: {e}")
    
    def load_cookies(self):
        """从文件加载cookies"""
        try:
            cookies_file = self.cache_dir / "zhihu_cookies.pkl"
            if cookies_file.exists():
                # 先访问知乎首页
                self.driver.get(self.config.BASE_URL)
                time.sleep(2)
                
                # 加载cookies
                with open(cookies_file, 'rb') as f:
                    cookies = pickle.load(f)
                
                for cookie in cookies:
                    try:
                        self.driver.add_cookie(cookie)
                    except Exception as e:
                        logger.debug(f"添加cookie失败: {e}")
                
                # 刷新页面使cookies生效
                self.driver.refresh()
                time.sleep(2)
                
                logger.info("Cookies加载成功")
            else:
                logger.info("未找到cookies文件")
        except Exception as e:
            logger.warning(f"加载cookies失败: {e}")
    
    def check_login_status(self) -> bool:
        """检查登录状态"""
        try:
            self.driver.get(self.config.BASE_URL)
            time.sleep(3)
            
            # 检查是否存在登录按钮
            login_buttons = self.driver.find_elements(By.XPATH, "//button[contains(text(), '登录')]")
            if login_buttons:
                logger.info("未登录状态")
                return False
            
            # 检查是否存在用户头像或用户菜单
            user_elements = self.driver.find_elements(By.CSS_SELECTOR, ".Avatar, .AppHeader-userInfo")
            if user_elements:
                logger.info("已登录状态")
                return True
            
            logger.info("登录状态未知")
            return False
            
        except Exception as e:
            logger.error(f"检查登录状态失败: {e}")
            return False
    
    def reset_driver(self) -> bool:
        """重置浏览器驱动，解决会话失效问题"""
        try:
            logger.info("正在重置浏览器驱动...")
            if self.driver:
                try:
                    self.driver.quit()
                except Exception as e:
                    logger.warning(f"关闭旧驱动失败: {e}")
            
            # 重新设置驱动
            self.setup_driver()
            
            # 重新加载cookies
            self.load_cookies()
            
            # 检查登录状态
            if not self.check_login_status():
                logger.warning("重置驱动后未检测到登录状态，可能需要重新登录")
            else:
                logger.info("浏览器驱动重置成功，并保持了登录状态")
                self.session_error_count = 0  # 重置会话错误计数
            
            return True
        except Exception as e:
            logger.error(f"重置浏览器驱动失败: {e}")
            return False
    
    def handle_session_error(self, operation_name: str = "未知操作", max_retries: int = 3) -> bool:
        """处理会话错误，尝试重置驱动并重试操作"""
        self.session_error_count += 1
        
        if self.session_error_count > self.max_session_errors:
            logger.error(f"会话错误次数过多 ({self.session_error_count}/{self.max_session_errors})，需要重新登录")
            return False
        
        for retry in range(max_retries):
            try:
                logger.warning(f"{operation_name} 遇到会话错误，正在尝试重置驱动 (尝试 {retry+1}/{max_retries})")
                if self.reset_driver():
                    logger.info(f"驱动重置成功，准备重试 {operation_name}")
                    return True
            except Exception as e:
                logger.error(f"处理会话错误失败: {e}")
        
        logger.error(f"{operation_name} 会话错误处理失败，已达到最大重试次数")
        return False
    
    def manual_login_prompt(self) -> bool:
        """提示用户手动登录"""
        logger.info("请在浏览器中手动登录知乎...")
        logger.info("登录完成后，请在终端按回车键继续...")
        
        # 等待用户登录
        input("按回车键继续...")
        
        # 保存登录后的cookies
        self.save_cookies()
        
        # 再次检查登录状态
        if self.check_login_status():
            logger.info("登录成功")
            return True
        else:
            logger.error("登录失败，请重新尝试")
            return False
    
    def switch_to_non_headless_for_login(self) -> bool:
        """切换到非无头模式进行登录"""
        logger.info("无头模式下未检测到登录状态，正在切换到非无头模式进行登录...")
        
        try:
            # 关闭当前无头模式的浏览器
            if self.driver:
                self.driver.quit()
            
            # 切换到非无头模式
            original_headless = self.headless
            self.headless = False
            
            # 重新初始化浏览器
            self.setup_driver()
            
            # 加载cookies
            self.load_cookies()
            
            # 检查登录状态
            if self.check_login_status():
                logger.info("检测到已登录状态")
                login_success = True
            else:
                # 提示用户登录
                login_success = self.manual_login_prompt()
            
            if login_success:
                # 保存cookies
                self.save_cookies()
                
                # 关闭非无头模式浏览器
                if self.driver:
                    self.driver.quit()
                
                # 恢复无头模式
                self.headless = original_headless
                self.setup_driver()
                self.load_cookies()
                
                # 验证登录状态
                if self.check_login_status():
                    logger.info("登录成功，已切换回无头模式")
                    return True
                else:
                    logger.error("切换回无头模式后登录状态丢失")
                    return False
            else:
                # 恢复原始设置
                self.headless = original_headless
                self.setup_driver()
                logger.error("登录失败")
                return False
                
        except Exception as e:
            logger.error(f"切换登录模式失败: {e}")
            # 恢复原始设置
            try:
                self.headless = original_headless
                self.setup_driver()
            except:
                pass
            return False
    
    def list_unfinished_tasks(self) -> List[TaskInfo]:
        """列出所有未完成的任务"""
        try:
            return self.db.get_unfinished_tasks()
        except Exception as e:
            logger.error(f"列出未完成任务失败: {e}")
            return []
    
    def random_delay(self, min_delay: float = None, max_delay: float = None):
        """随机延时"""
        min_delay = min_delay or self.config.MIN_DELAY
        max_delay = max_delay or self.config.MAX_DELAY
        delay = random.uniform(min_delay, max_delay)
        time.sleep(delay)
    
    def scroll_to_load_more(self) -> bool:
        """滚动页面加载更多内容，使用特定滑动策略解决懒加载问题，持续滚动直到所有答案加载完成"""
        try:
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            unchanged_count = 0  # 连续高度不变的次数
            max_unchanged = 5    # 增加连续高度不变的次数阈值
            answer_count_before = 0
            expected_answer_count = 0  # 预期的答案总数
        except WebDriverException as e:
            if "invalid session id" in str(e).lower():
                logger.error(f"滚动加载时遇到会话错误: {e}")
                if self.handle_session_error("滚动加载"):
                    # 会话已重置，重新尝试滚动加载
                    return self.scroll_to_load_more()
                return False
            raise
        
        try:
            
            # 尝试获取问题的预期答案总数
            try:
                answer_count_element = self.driver.find_element(By.CSS_SELECTOR, self.config.SELECTORS["question_answer_count"])
                expected_answer_count = self._parse_count(answer_count_element.text)
                logger.info(f"问题标记的总回答数: {expected_answer_count}")
            except Exception as e:
                logger.debug(f"获取问题标记的总回答数失败: {e}")
            
            # 记录初始答案数量
            try:
                # 使用正确的选择器键名，并提供备用选择器
                answers_selector = self.config.SELECTORS.get("answers_list", ".List-item, .Card.AnswerCard, .Card.MoreAnswers > div > div")
                answer_elements = self.driver.find_elements(By.CSS_SELECTOR, answers_selector)
                answer_count_before = len(answer_elements)
                logger.info(f"开始滚动前，找到 {answer_count_before} 个答案")
            except Exception as e:
                logger.debug(f"获取初始答案数量失败: {e}")
            
            # 持续滚动直到所有答案加载完成
            scroll_count = 0
            while True:
                scroll_count += 1
                # 滚动到页面底部
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                logger.info(f"执行第 {scroll_count} 次滚动加载")
                
                # 等待新内容加载，增加等待时间
                time.sleep(self.config.SCROLL_PAUSE_TIME * 2)  # 增加等待时间
                
                # 检查是否出现"没有更多了"的提示
                try:
                    no_more_texts = ["没有更多了", "没有更多内容", "已经到底了", "暂时没有更多"]
                    page_text = self.driver.find_element(By.TAG_NAME, "body").text
                    for no_more_text in no_more_texts:
                        if no_more_text in page_text:
                            logger.info(f"检测到'{no_more_text}'提示，停止滚动")
                            return True
                except Exception as e:
                    logger.debug(f"检测'没有更多了'提示失败: {e}")
                
                # 检查页面高度是否有变化
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    unchanged_count += 1
                    logger.info(f"页面高度未变化 {unchanged_count}/{max_unchanged}，继续滚动 (第{scroll_count}次)")
                    
                    # 如果连续多次高度不变，检查是否已加载所有答案
                    if unchanged_count >= max_unchanged:
                        # 检查当前答案数量
                        try:
                            answers_selector = self.config.SELECTORS.get("answers_list", ".List-item, .Card.AnswerCard, .Card.MoreAnswers > div > div")
                            current_answers = self.driver.find_elements(By.CSS_SELECTOR, answers_selector)
                            current_count = len(current_answers)
                            
                            # 如果已知预期答案总数，且已加载数量接近或超过预期，则认为加载完成
                            if expected_answer_count > 0 and current_count >= expected_answer_count * 0.95:  # 允许5%的误差
                                logger.info(f"已加载 {current_count} 个答案，接近或超过预期总数 {expected_answer_count}，停止滚动")
                                break
                            
                            # 更新答案数量
                            answer_count_before = current_count
                        except Exception as e:
                            logger.debug(f"检查当前答案数量失败: {e}")
                            
                            # 如果无法检查答案数量，但连续多次高度不变，也认为加载完成
                            if unchanged_count >= max_unchanged * 2:
                                logger.info(f"连续 {unchanged_count} 次滚动后页面高度未变化，停止滚动")
                                break
                    
                    # 尝试点击"显示更多"按钮 - 使用更多选择器
                    try:
                        # 尝试使用多种选择器查找并点击"显示更多"按钮
                        show_more_selectors = [
                            self.config.SELECTORS["load_more_answers"],
                            ".QuestionAnswers-answerAdd button", 
                            ".AnswerListV2-answerAdd button", 
                            "button:contains('显示更多')", 
                            "button:contains('更多回答')",
                            "button.QuestionMainAction",
                            ".List-headerText+button",
                            ".List-header button"
                        ]
                        
                        for selector in show_more_selectors:
                            try:
                                show_more_buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                                for btn in show_more_buttons:
                                    if btn.is_displayed() and ("更多" in btn.text or "显示" in btn.text):
                                        logger.info(f"找到并点击'显示更多'按钮: {btn.text}")
                                        try:
                                            # 尝试直接点击
                                            btn.click()
                                            logger.info("直接点击'显示更多'按钮成功")
                                        except Exception as e:
                                            logger.debug(f"直接点击'显示更多'按钮失败: {e}，尝试JavaScript点击")
                                            self.driver.execute_script("arguments[0].click();", btn)
                                            logger.info("通过JavaScript点击'显示更多'按钮成功")
                                        
                                        time.sleep(3)  # 增加等待时间
                                        unchanged_count = 0  # 重置计数器
                                        break
                            except Exception as e:
                                logger.debug(f"尝试选择器 {selector} 查找'显示更多'按钮失败: {e}")
                    except Exception as e:
                        logger.debug(f"尝试点击'显示更多'按钮失败: {e}")
                    
                    # 尝试使用XPath查找并点击按钮
                    if unchanged_count >= 2:
                        try:
                            xpath_expressions = [
                                "//button[contains(text(), '显示更多')]",
                                "//button[contains(text(), '更多回答')]",
                                "//button[contains(text(), '加载更多')]"
                            ]
                            
                            for xpath in xpath_expressions:
                                elements = self.driver.find_elements(By.XPATH, xpath)
                                for element in elements:
                                    if element.is_displayed():
                                        logger.info(f"通过XPath找到'显示更多'按钮: {element.text}")
                                        try:
                                            element.click()
                                            logger.info("直接点击XPath找到的'显示更多'按钮成功")
                                        except Exception as e:
                                            logger.debug(f"直接点击XPath找到的'显示更多'按钮失败: {e}，尝试JavaScript点击")
                                            self.driver.execute_script("arguments[0].click();", element)
                                            logger.info("通过JavaScript点击XPath找到的'显示更多'按钮成功")
                                        
                                        time.sleep(3)  # 增加等待时间
                                        unchanged_count = 0  # 重置计数器
                                        break
                        except Exception as e:
                            logger.debug(f"通过XPath查找'显示更多'按钮失败: {e}")
                    
                    # 尝试使用更复杂的JavaScript查找和点击按钮
                    if unchanged_count >= 3:
                        js_script = """
                        function findAndClickLoadMoreButton() {
                            // 通过文本内容查找按钮
                            var allButtons = document.querySelectorAll('button');
                            for (var i = 0; i < allButtons.length; i++) {
                                var btn = allButtons[i];
                                var text = btn.textContent.trim();
                                if (text.includes('显示更多') || text.includes('更多回答') || text.includes('加载更多')) {
                                    btn.click();
                                    return '通过文本内容找到并点击了加载更多按钮: ' + text;
                                }
                            }
                            
                            // 通过常见类名查找
                            var buttonClasses = [
                                '.QuestionMainAction', '.QuestionAnswers-answerAdd button', 
                                '.AnswerListV2-answerAdd button', '.List-headerText+button',
                                '.List-header button'
                            ];
                            
                            for (var i = 0; i < buttonClasses.length; i++) {
                                var buttons = document.querySelectorAll(buttonClasses[i]);
                                for (var j = 0; j < buttons.length; j++) {
                                    var button = buttons[j];
                                    if (button.offsetParent !== null) { // 检查元素是否可见
                                        button.click();
                                        return '通过类名找到并点击了加载更多按钮: ' + buttonClasses[i];
                                    }
                                }
                            }
                            
                            return false;
                        }
                        return findAndClickLoadMoreButton();
                        """
                        result = self.driver.execute_script(js_script)
                        if result:
                            logger.info(f"通过JavaScript成功点击'显示更多'按钮: {result}")
                            time.sleep(3)  # 增加等待时间
                            unchanged_count = 0  # 重置计数器
                    
                    # 检查当前答案数量
                    current_count = 0
                    try:
                        # 使用正确的选择器键名，并提供备用选择器
                        answers_selector = self.config.SELECTORS.get("answers_list", ".List-item, .Card.AnswerCard, .Card.MoreAnswers > div > div")
                        current_answers = self.driver.find_elements(By.CSS_SELECTOR, answers_selector)
                        current_count = len(current_answers)
                        logger.info(f"当前答案数量: {current_count}，初始答案数量: {answer_count_before}")
                        
                        # 如果答案数量有显著增加，继续滚动
                        if current_count > answer_count_before + 5:
                            logger.info(f"答案数量已增加 {current_count - answer_count_before}，继续滚动")
                            unchanged_count = 0  # 重置计数器
                    except Exception as e:
                        logger.debug(f"检查当前答案数量失败: {e}")
                    
                    # 如果连续多次高度不变，尝试特殊滑动策略
                    if unchanged_count >= 4:
                        logger.info("尝试特殊滑动策略：向上滑动至页面1/3处，然后再次下滑")
                        try:
                            # 获取当前页面高度
                            current_height = self.driver.execute_script("return document.body.scrollHeight")
                            # 向上滑动到页面1/3处
                            self.driver.execute_script(f"window.scrollTo(0, {current_height / 3});")
                            time.sleep(2)  # 等待页面响应
                            # 再次向下滑动到底部
                            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                            time.sleep(3)  # 等待加载
                            
                            # 检查特殊滑动后的答案数量
                            try:
                                new_answers = self.driver.find_elements(By.CSS_SELECTOR, answers_selector)
                                new_count = len(new_answers)
                                logger.info(f"特殊滑动后答案数量: {new_count}，之前数量: {current_count}")
                                if new_count > current_count:
                                    logger.info(f"特殊滑动策略有效，答案数量增加了 {new_count - current_count}")
                                    unchanged_count = 0  # 重置计数器
                                    current_count = new_count
                            except Exception as e:
                                logger.debug(f"检查特殊滑动后答案数量失败: {e}")
                        except Exception as e:
                            logger.debug(f"执行特殊滑动策略失败: {e}")
                    
                    # 检查是否已加载所有答案（通过比较预期答案数与实际加载数）
                    if expected_answer_count > 0 and current_count > 0:
                        # 考虑到可能有一些答案被删除或隐藏，允许有少量差异
                        if current_count >= expected_answer_count * 0.9:
                            logger.info(f"已加载大部分答案：当前 {current_count}，预期 {expected_answer_count}，停止滚动")
                            break
                    
                    # 如果连续多次高度不变，检查答案数量是否也没有变化
                    if unchanged_count >= max_unchanged:
                        # 检查答案数量是否也没有变化
                        try:
                            answers_selector = self.config.SELECTORS.get("answers_list", ".List-item, .Card.AnswerCard, .Card.MoreAnswers > div > div")
                            final_answers = self.driver.find_elements(By.CSS_SELECTOR, answers_selector)
                            final_count = len(final_answers)
                            
                            if final_count == answer_count_before:
                                logger.info(f"页面高度连续{max_unchanged}次未变化且答案数量也未变化（{final_count}个），停止滚动")
                                break
                            else:
                                logger.info(f"页面高度未变化但答案数量有变化（从{answer_count_before}到{final_count}），继续滚动")
                                answer_count_before = final_count
                                unchanged_count = 0  # 重置计数器
                        except Exception as e:
                            logger.debug(f"检查最终答案数量失败: {e}")
                            logger.info(f"页面高度连续{max_unchanged}次未变化，停止滚动")
                            break
                else:
                    unchanged_count = 0  # 重置计数器
                    last_height = new_height
                    logger.info(f"滚动第{scroll_count}次，页面高度变化: {new_height}")
            
            # 最后再尝试一次点击加载更多按钮
            try:
                js_script = """
                var buttons = document.querySelectorAll('button');
                var clicked = false;
                for (var i = 0; i < buttons.length; i++) {
                    var btn = buttons[i];
                    if ((btn.textContent.includes('显示更多') || btn.textContent.includes('更多回答')) && btn.offsetParent !== null) {
                        btn.click();
                        clicked = true;
                        break;
                    }
                }
                return clicked;
                """
                clicked = self.driver.execute_script(js_script)
                if clicked:
                    logger.info("最后一次通过JavaScript成功点击'显示更多'按钮")
                    time.sleep(3)  # 等待加载
            except Exception as e:
                logger.debug(f"最后一次尝试点击'显示更多'按钮失败: {e}")
            
            # 最后一次尝试特殊滑动策略
            try:
                # 获取当前页面高度
                current_height = self.driver.execute_script("return document.body.scrollHeight")
                # 向上滑动到页面1/3处
                self.driver.execute_script(f"window.scrollTo(0, {current_height / 3});")
                time.sleep(2)  # 等待页面响应
                # 再次向下滑动到底部
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(3)  # 等待加载
                logger.info("执行最后一次特殊滑动策略")
            except Exception as e:
                logger.debug(f"执行最后一次特殊滑动策略失败: {e}")
            
            # 检查最终加载的答案数量
            try:
                # 使用正确的选择器键名，并提供备用选择器
                answers_selector = self.config.SELECTORS.get("answers_list", ".List-item, .Card.AnswerCard, .Card.MoreAnswers > div > div")
                answer_elements = self.driver.find_elements(By.CSS_SELECTOR, answers_selector)
                answer_count_after = len(answer_elements)
                logger.info(f"滚动加载完成，找到 {answer_count_after} 个答案，初始有 {answer_count_before} 个答案")
                
                # 如果有预期答案数，比较加载结果
                if expected_answer_count > 0:
                    completion_percentage = (answer_count_after / expected_answer_count) * 100
                    logger.info(f"答案加载完成度: {completion_percentage:.2f}%（{answer_count_after}/{expected_answer_count}）")
                
                # 尝试其他选择器，如果答案数量少于预期
                if answer_count_after <= 5 or (expected_answer_count > 0 and answer_count_after < expected_answer_count * 0.7):
                    alternative_selectors = [
                        ".AnswerItem",
                        ".List-item",
                        ".ContentItem",
                        ".AnswerCard",
                        "div[data-za-detail-view-path-module='AnswerItem']"
                    ]
                    
                    for selector in alternative_selectors:
                        try:
                            alt_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            if len(alt_elements) > answer_count_after:
                                logger.info(f"使用替代选择器 {selector} 找到 {len(alt_elements)} 个答案")
                                answer_count_after = len(alt_elements)
                        except Exception as e:
                            logger.debug(f"尝试替代选择器 {selector} 失败: {e}")
            except Exception as e:
                logger.debug(f"获取最终答案数量失败: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"滚动加载失败: {e}")
            return False
    
    def extract_id_from_url(self, url: str) -> str:
        """从URL中提取ID"""
        try:
            # 知乎问题URL格式: https://www.zhihu.com/question/123456789
            # 知乎答案URL格式: https://www.zhihu.com/question/123456789/answer/987654321
            
            if '/question/' in url:
                # 提取问题ID
                match = re.search(r'/question/(\d+)', url)
                if match:
                    return match.group(1)
            
            if '/answer/' in url:
                # 提取答案ID
                match = re.search(r'/answer/(\d+)', url)
                if match:
                    return match.group(1)
            
            # 如果无法提取，返回URL的hash值
            return str(hash(url))
            
        except Exception as e:
            logger.warning(f"提取ID失败: {e}")
            return str(hash(url))
    
    def search_questions(self, keyword: str, task_id: str, start_date: str = None, end_date: str = None) -> List[SearchResult]:
        """搜索问题并实时保存到数据库"""
        start_date = start_date or self.config.DEFAULT_START_DATE
        end_date = end_date or self.config.DEFAULT_END_DATE
        
        if not self.config.validate_date_range(start_date, end_date):
            raise ValueError("日期范围无效")
        
        logger.info(f"开始搜索关键字: {keyword}, 时间范围: {start_date} 至 {end_date}")
        
        search_results = []
        
        try:
            # 构建搜索URL
            search_url = f"{self.config.SEARCH_URL}?type=content&q={keyword}"
            logger.info(f"访问搜索URL: {search_url}")
            self.driver.get(search_url)
            self.random_delay()
            
            # 调试：输出页面标题和URL
            logger.info(f"页面标题: {self.driver.title}")
            logger.info(f"当前URL: {self.driver.current_url}")
            
            # 调试：检查页面是否需要登录
            if "login" in self.driver.current_url.lower() or "登录" in self.driver.page_source:
                logger.warning("页面可能需要登录")
            
            # 等待搜索结果加载
            try:
                self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, self.config.SELECTORS["search_results"])))
                logger.info("搜索结果元素加载成功")
            except TimeoutException:
                logger.error("搜索结果加载超时")
                return search_results
            
            # 滚动加载更多结果
            self.scroll_to_load_more()
            
            # 解析搜索结果
            result_elements = self.driver.find_elements(By.CSS_SELECTOR, self.config.SELECTORS["search_results"])
            logger.info(f"找到 {len(result_elements)} 个搜索结果元素")
            
            for i, element in enumerate(result_elements):
                try:
                    # 尝试多种方式提取问题链接和标题
                    try:
                        # 首先尝试使用配置的CSS选择器
                        link_element = element.find_element(By.CSS_SELECTOR, self.config.SELECTORS["search_question_title"])
                        question_url = link_element.get_attribute('href')
                        question_title = link_element.text.strip()
                    except NoSuchElementException:
                        # 如果找不到特定选择器，尝试查找任何a标签
                        logger.info("尝试使用备用方法查找链接")
                        link_elements = element.find_elements(By.TAG_NAME, "a")
                        if link_elements:
                            for link in link_elements:
                                temp_url = link.get_attribute('href')
                                if temp_url and ('/question/' in temp_url or '/answer/' in temp_url):
                                    question_url = temp_url
                                    question_title = link.text.strip()
                                    if not question_title:
                                        # 如果链接没有文本，尝试查找附近的标题元素
                                        title_elements = element.find_elements(By.CSS_SELECTOR, "h2, .ContentItem-title")
                                        if title_elements:
                                            question_title = title_elements[0].text.strip()
                                    break
                            else:
                                # 如果没有找到合适的链接，记录并跳过
                                logger.warning(f"在第{i+1}个结果中未找到合适的问题链接")
                                continue
                        else:
                            # 如果没有找到任何链接，记录并跳过
                            logger.warning(f"在第{i+1}个结果中未找到任何链接")
                            continue
                    
                    logger.debug(f"找到问题链接: {question_url}, 标题: {question_title}")
                    
                    if not question_url or not question_title:
                        logger.warning(f"第{i+1}个结果的URL或标题为空")
                        continue
                    
                    # 确保URL是完整的
                    if not question_url.startswith('http'):
                        question_url = urljoin(self.config.BASE_URL, question_url)
                    
                    # 过滤掉非问题链接（专栏、文章等）
                    if not ('/question/' in question_url or '/answer/' in question_url):
                        logger.debug(f"跳过非问题链接: {question_url}")
                        continue
                    
                    # 提取问题ID
                    question_id = self.extract_id_from_url(question_url)
                    
                    # 创建搜索结果对象
                    search_result = SearchResult(
                        result_id="",  # 将在__post_init__中自动生成
                        task_id=task_id,
                        question_id=question_id,
                        question_url=question_url,
                        title=question_title
                    )
                    
                    # 添加到搜索结果列表
                    search_results.append(search_result)
                    logger.info(f"搜索结果已添加: {question_title[:50]}...")
                    
                except Exception as e:
                    logger.warning(f"解析搜索结果失败 (第{i+1}个): {e}")
                    continue
            
            # 批量保存搜索结果到数据库
            if search_results:
                if self.db.save_search_results(search_results):
                    logger.info(f"搜索完成，共找到并保存 {len(search_results)} 个结果")
                else:
                    logger.error("批量保存搜索结果失败")
            else:
                logger.info("搜索完成，未找到任何结果")
            
            return search_results
            
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return search_results
    
    def crawl_question_detail(self, question_url: str, task_id: str, max_retries: int = 3) -> Optional[Question]:
        """爬取问题详情并实时保存到数据库"""
        for attempt in range(max_retries):
            try:
                logger.info(f"开始爬取问题详情 (尝试 {attempt + 1}/{max_retries}): {question_url}")
                
                if not question_url.startswith('http'):
                    question_url = urljoin(self.config.BASE_URL, question_url)
                
                try:
                    self.driver.get(question_url)
                    self.random_delay()
                except WebDriverException as e:
                    if "invalid session id" in str(e).lower():
                        logger.error(f"爬取问题详情时遇到会话错误: {e}")
                        if self.handle_session_error("爬取问题详情"):
                            # 会话已重置，重新尝试访问
                            self.driver.get(question_url)
                            self.random_delay()
                        else:
                            raise
                
                # 等待页面加载完成
                self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                
                # 等待问题标题加载
                try:
                    self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, self.config.SELECTORS["question_title"])))
                except TimeoutException:
                    logger.warning("问题标题元素加载超时")
                
                # 额外等待确保页面完全渲染
                self.random_delay(2, 4)
                
                # 提取问题ID
                question_id = self.extract_id_from_url(question_url)
                
                # 提取问题标题
                try:
                    title_element = self.driver.find_element(By.CSS_SELECTOR, self.config.SELECTORS["question_title"])
                    title = title_element.text.strip()
                except NoSuchElementException:
                    title = "无标题"
                    logger.warning("未找到问题标题")
                
                # 提取问题内容
                try:
                    content_element = self.driver.find_element(By.CSS_SELECTOR, self.config.SELECTORS["question_detail"])
                    content = content_element.text.strip()
                except NoSuchElementException:
                    content = ""
                    logger.debug("未找到问题内容")
                
                # 提取作者信息
                try:
                    author_element = self.driver.find_element(By.CSS_SELECTOR, self.config.SELECTORS["question_author"])
                    author = author_element.text.strip()
                except NoSuchElementException:
                    author = "匿名用户"
                    logger.debug("未找到问题作者")
                
                # 提取关注数
                try:
                    follow_element = self.driver.find_element(By.CSS_SELECTOR, self.config.SELECTORS["question_follow_count"])
                    follow_count = self._parse_count(follow_element.text)
                except NoSuchElementException:
                    follow_count = 0
                    logger.debug("未找到关注数")
                
                # 提取浏览量
                try:
                    view_element = self.driver.find_element(By.CSS_SELECTOR, self.config.SELECTORS["question_view_count"])
                    view_count = self._parse_count(view_element.text)
                except NoSuchElementException:
                    view_count = 0
                    logger.debug("未找到浏览量")
                
                # 提取答案数
                try:
                    answer_element = self.driver.find_element(By.CSS_SELECTOR, self.config.SELECTORS["question_answer_count"])
                    answer_count = self._parse_count(answer_element.text)
                except NoSuchElementException:
                    answer_count = 0
                    logger.debug("未找到答案数")
                
                # 提取标签
                tags = []
                try:
                    tag_elements = self.driver.find_elements(By.CSS_SELECTOR, self.config.SELECTORS["question_tags"])
                    tags = [tag.text.strip() for tag in tag_elements if tag.text.strip()]
                except NoSuchElementException:
                    logger.debug("未找到标签")
                
                # 创建问题对象
                question = Question(
                    question_id=question_id,
                    task_id=task_id,
                    title=title,
                    content=content,
                    author=author,
                    create_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # 使用PostgreSQL兼容的时间戳格式
                    follow_count=follow_count,
                    view_count=view_count,
                    answer_count=answer_count,
                    url=question_url,
                    tags=tags,
                    crawl_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
                
                # 实时保存问题到数据库
                if self.db.save_question(question):
                    logger.info(f"问题详情已保存: {title[:50]}...")
                    return question
                else:
                    logger.error("保存问题详情失败")
                    return None
                
            except Exception as e:
                logger.warning(f"爬取问题详情失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    self.random_delay(3, 6)
                    continue
                else:
                    logger.error(f"爬取问题详情最终失败: {question_url}")
                    return None
    
    def crawl_answers(self, question_url: str, question_id: str, task_id: str, start_date: str, end_date: str) -> Tuple[List[Answer], int]:
        """爬取问题的所有答案，并抓取每个答案的评论；返回 (answers, total_comments)"""
        try:
            logger.info(f"开始爬取问题答案: {question_url}")
            
            if not question_url.startswith('http'):
                question_url = urljoin(self.config.BASE_URL, question_url)
            
            try:
                self.driver.get(question_url)
                self.random_delay()
            except WebDriverException as e:
                if "invalid session id" in str(e).lower():
                    logger.error(f"爬取答案时遇到会话错误: {e}")
                    if self.handle_session_error("爬取答案"):
                        # 会话已重置，重新尝试访问
                        self.driver.get(question_url)
                        self.random_delay()
                    else:
                        return [], 0
                else:
                    raise
            
            # 等待页面加载
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            # 检查并点击"查看全部回答"按钮（如果存在）
            try:
                # 尝试多种可能的选择器来定位"查看全部回答"按钮
                load_all_answers_selectors = [
                    "#root > div > main > div > div > div.Question-main > div.ListShortcut > div > div:nth-child(1) > a",
                    "a[href*='answers']",
                    "a:contains('查看全部回答')",
                    "a:contains('全部回答')",
                    ".QuestionMainAction a",
                    ".QuestionHeader-footer a",
                    ".QuestionHeader-main a",
                    ".QuestionHeader-title+div a",
                    ".QuestionHeader-side a",
                    "a.QuestionMainAction",
                    "a.Button--primary",
                    "a.Button--blue"
                ]
                
                # 首先尝试通过文本内容查找按钮
                load_all_answers_btn = None
                try:
                    # 使用XPath通过文本内容查找
                    xpath_expressions = [
                        "//a[contains(text(), '查看全部回答')]",
                        "//a[contains(text(), '全部回答')]",
                        "//a[contains(text(), '查看全部')]",
                        "//button[contains(text(), '查看全部回答')]",
                        "//button[contains(text(), '全部回答')]",
                        "//button[contains(text(), '查看全部')]"
                    ]
                    
                    for xpath in xpath_expressions:
                        elements = self.driver.find_elements(By.XPATH, xpath)
                        for element in elements:
                            if element.is_displayed():
                                load_all_answers_btn = element
                                logger.info(f"通过XPath找到'查看全部回答'按钮: {element.text}")
                                break
                        if load_all_answers_btn:
                            break
                except Exception as e:
                    logger.debug(f"通过XPath查找'查看全部回答'按钮失败: {e}")
                
                # 如果通过XPath未找到，尝试CSS选择器
                if not load_all_answers_btn:
                    for selector in load_all_answers_selectors:
                        try:
                            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            for element in elements:
                                if element.is_displayed() and ("全部回答" in element.text or "查看全部" in element.text):
                                    load_all_answers_btn = element
                                    logger.info(f"通过CSS选择器找到'查看全部回答'按钮: {element.text}")
                                    break
                            if load_all_answers_btn:
                                break
                        except Exception as e:
                            logger.debug(f"尝试CSS选择器 {selector} 失败: {e}")
                
                # 如果找到按钮，尝试多种方式点击它
                if load_all_answers_btn and load_all_answers_btn.is_displayed():
                    logger.info(f"发现'查看全部回答'按钮，文本: {load_all_answers_btn.text}，点击加载全部回答")
                    
                    # 尝试多种点击方法
                    try:
                        # 方法1: 直接点击
                        load_all_answers_btn.click()
                        logger.info("直接点击'查看全部回答'按钮成功")
                    except Exception as e:
                        logger.debug(f"直接点击'查看全部回答'按钮失败: {e}，尝试JavaScript点击")
                        try:
                            # 方法2: JavaScript点击
                            self.driver.execute_script("arguments[0].click();", load_all_answers_btn)
                            logger.info("通过JavaScript点击'查看全部回答'按钮成功")
                        except Exception as e:
                            logger.debug(f"通过JavaScript点击'查看全部回答'按钮失败: {e}")
                    
                    # 增加等待时间，确保页面加载
                    self.random_delay(5, 8)
                    
                    # 等待页面加载完成
                    try:
                        # 使用正确的选择器键名
                        answers_selector = self.config.SELECTORS.get("answers_list", ".List-item, .Card.AnswerCard, .Card.MoreAnswers > div > div")
                        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, answers_selector)))
                        logger.info("'查看全部回答'后页面加载完成")
                    except TimeoutException:
                        logger.warning("'查看全部回答'后页面加载超时")
                else:
                    # 尝试使用更复杂的JavaScript查找和点击按钮
                    logger.info("尝试使用JavaScript查找和点击'查看全部回答'按钮")
                    js_script = """
                    function findAndClickButton() {
                        // 通过文本内容查找链接
                        var allLinks = document.querySelectorAll('a, button');
                        for (var i = 0; i < allLinks.length; i++) {
                            var el = allLinks[i];
                            var text = el.textContent.trim();
                            if (text.includes('全部回答') || text.includes('查看全部')) {
                                el.click();
                                return '通过文本内容找到并点击了按钮: ' + text;
                            }
                        }
                        
                        // 通过URL查找链接
                        var answerLinks = document.querySelectorAll('a[href*="answers"]');
                        for (var i = 0; i < answerLinks.length; i++) {
                            var link = answerLinks[i];
                            if (link.offsetParent !== null) { // 检查元素是否可见
                                link.click();
                                return '通过URL找到并点击了答案链接';
                            }
                        }
                        
                        // 通过常见类名查找
                        var buttonClasses = [
                            '.QuestionMainAction', '.Button--primary', '.Button--blue',
                            '.QuestionHeader-main a', '.QuestionHeader-side a'
                        ];
                        
                        for (var i = 0; i < buttonClasses.length; i++) {
                            var buttons = document.querySelectorAll(buttonClasses[i]);
                            for (var j = 0; j < buttons.length; j++) {
                                var button = buttons[j];
                                if (button.offsetParent !== null) { // 检查元素是否可见
                                    button.click();
                                    return '通过类名找到并点击了按钮: ' + buttonClasses[i];
                                }
                            }
                        }
                        
                        return false;
                    }
                    return findAndClickButton();
                    """
                    result = self.driver.execute_script(js_script)
                    if result:
                        logger.info(f"通过JavaScript成功点击'查看全部回答'按钮: {result}")
                        self.random_delay(5, 8)
                        
                        # 等待页面加载完成
                        try:
                            # 使用正确的选择器键名，并提供备用选择器
                            answers_selector = self.config.SELECTORS.get("answers_list", ".List-item, .Card.AnswerCard, .Card.MoreAnswers > div > div")
                            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, answers_selector)))
                            logger.info("'查看全部回答'后页面加载完成")
                        except TimeoutException:
                            logger.warning("'查看全部回答'后页面加载超时")
                    else:
                        logger.debug("未发现'查看全部回答'按钮，继续正常流程")
            except Exception as e:
                logger.debug(f"尝试点击'查看全部回答'按钮时出错: {e}，继续正常流程")
            
            # 等待答案列表加载
            try:
                # 使用正确的选择器键名，并提供备用选择器
                answers_selector = self.config.SELECTORS.get("answers_list", ".List-item, .Card.AnswerCard, .Card.MoreAnswers > div > div")
                self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, answers_selector)))
            except TimeoutException:
                logger.warning("答案列表加载超时")
                return [], 0
            
            # 检查是否有"加载更多"按钮，尝试多种选择器
            load_more_selectors = [
                self.config.SELECTORS["load_more_answers"],
                "button:contains('显示更多')", 
                "button:contains('更多回答')",
                "button.QuestionMainAction",
                ".QuestionAnswers-answerAdd button", 
                ".AnswerListV2-answerAdd button",
                ".List-headerText+button",
                ".List-header button"
            ]
            
            for selector in load_more_selectors:
                try:
                    load_more_btns = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for load_more_btn in load_more_btns:
                        if load_more_btn.is_displayed() and ("更多" in load_more_btn.text or "显示" in load_more_btn.text):
                            logger.info(f"发现'加载更多'按钮，文本: {load_more_btn.text}，点击加载更多答案")
                            try:
                                # 尝试直接点击
                                load_more_btn.click()
                                logger.info("直接点击'加载更多'按钮成功")
                            except Exception as e:
                                logger.debug(f"直接点击'加载更多'按钮失败: {e}，尝试JavaScript点击")
                                try:
                                    # 尝试JavaScript点击
                                    self.driver.execute_script("arguments[0].click();", load_more_btn)
                                    logger.info("通过JavaScript点击'加载更多'按钮成功")
                                except Exception as e:
                                    logger.debug(f"通过JavaScript点击'加载更多'按钮失败: {e}")
                            
                            self.random_delay(3, 5)
                            break
                except Exception as e:
                    logger.debug(f"尝试选择器 {selector} 查找'加载更多'按钮失败: {e}")
            
            # 尝试使用XPath查找加载更多按钮
            try:
                xpath_expressions = [
                    "//button[contains(text(), '显示更多')]",
                    "//button[contains(text(), '更多回答')]",
                    "//button[contains(text(), '加载更多')]"
                ]
                
                for xpath in xpath_expressions:
                    elements = self.driver.find_elements(By.XPATH, xpath)
                    for element in elements:
                        if element.is_displayed():
                            logger.info(f"通过XPath找到'加载更多'按钮: {element.text}")
                            try:
                                element.click()
                                logger.info("直接点击XPath找到的'加载更多'按钮成功")
                            except Exception as e:
                                logger.debug(f"直接点击XPath找到的'加载更多'按钮失败: {e}，尝试JavaScript点击")
                                try:
                                    self.driver.execute_script("arguments[0].click();", element)
                                    logger.info("通过JavaScript点击XPath找到的'加载更多'按钮成功")
                                except Exception as e:
                                    logger.debug(f"通过JavaScript点击XPath找到的'加载更多'按钮失败: {e}")
                            
                            self.random_delay(3, 5)
                            break
            except Exception as e:
                logger.debug(f"通过XPath查找'加载更多'按钮失败: {e}")
                
            # 尝试使用JavaScript查找和点击加载更多按钮
            js_script = """
            function findAndClickLoadMoreButton() {
                // 通过文本内容查找按钮
                var allButtons = document.querySelectorAll('button');
                for (var i = 0; i < allButtons.length; i++) {
                    var btn = allButtons[i];
                    var text = btn.textContent.trim();
                    if (text.includes('显示更多') || text.includes('更多回答') || text.includes('加载更多')) {
                        btn.click();
                        return '通过文本内容找到并点击了加载更多按钮: ' + text;
                    }
                }
                
                // 通过常见类名查找
                var buttonClasses = [
                    '.QuestionMainAction', '.QuestionAnswers-answerAdd button', 
                    '.AnswerListV2-answerAdd button', '.List-headerText+button',
                    '.List-header button'
                ];
                
                for (var i = 0; i < buttonClasses.length; i++) {
                    var buttons = document.querySelectorAll(buttonClasses[i]);
                    for (var j = 0; j < buttons.length; j++) {
                        var button = buttons[j];
                        if (button.offsetParent !== null) { // 检查元素是否可见
                            button.click();
                            return '通过类名找到并点击了加载更多按钮: ' + buttonClasses[i];
                        }
                    }
                }
                
                return false;
            }
            return findAndClickLoadMoreButton();
            """
            result = self.driver.execute_script(js_script)
            if result:
                logger.info(f"通过JavaScript成功点击'加载更多'按钮: {result}")
                self.random_delay(3, 5)
            
            # 滚动加载更多答案，不限制滚动次数
            self.scroll_to_load_more()  # 移除滚动次数限制，确保加载所有答案
            
            # 获取所有答案元素
            # 使用正确的选择器键名，并提供备用选择器
            answers_selector = self.config.SELECTORS.get("answers_list", ".List-item, .Card.AnswerCard, .Card.MoreAnswers > div > div")
            answer_elements = self.driver.find_elements(By.CSS_SELECTOR, answers_selector)
            logger.info(f"找到 {len(answer_elements)} 个答案")
            
            # 如果答案数量少于预期，尝试其他选择器
            if len(answer_elements) <= 5:
                logger.info("答案数量少于预期，尝试其他选择器")
                alternative_selectors = [
                    ".AnswerItem",
                    ".List-item",
                    ".ContentItem",
                    ".AnswerCard",
                    "div[data-za-detail-view-path-module='AnswerItem']"
                ]
                
                for selector in alternative_selectors:
                    try:
                        alt_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if len(alt_elements) > len(answer_elements):
                            logger.info(f"使用替代选择器 {selector} 找到 {len(alt_elements)} 个答案")
                            answer_elements = alt_elements
                    except Exception as e:
                        logger.debug(f"尝试替代选择器 {selector} 失败: {e}")
            
            # 如果仍然只有少量答案，尝试使用JavaScript获取
            if len(answer_elements) <= 5:
                logger.info("尝试使用JavaScript获取所有答案元素")
                js_script = """
                return Array.from(document.querySelectorAll('.List-item, .AnswerItem, .ContentItem, .AnswerCard')).filter(el => {
                    return el.querySelector('.RichContent') || el.querySelector('.RichText') || el.querySelector('.ContentItem-content');
                });
                """
                js_elements = self.driver.execute_script(js_script)
                if js_elements and len(js_elements) > len(answer_elements):
                    logger.info(f"通过JavaScript找到 {len(js_elements)} 个答案")
                    answer_elements = js_elements
            
            answers = []
            total_comments_saved = 0
            
            for i, element in enumerate(answer_elements):
                try:
                    # 提取答案内容
                    try:
                        content_element = element.find_element(By.CSS_SELECTOR, self.config.SELECTORS["answer_content"])
                        content = content_element.text.strip()
                    except NoSuchElementException:
                        content = ""
                        logger.debug(f"答案 {i+1} 未找到内容")
                    
                    # 提取作者信息
                    try:
                        author_element = element.find_element(By.CSS_SELECTOR, self.config.SELECTORS["answer_author"])
                        author = author_element.text.strip()
                        author_url = author_element.get_attribute('href') or ""
                    except NoSuchElementException:
                        author = "匿名用户"
                        author_url = ""
                        logger.debug(f"答案 {i+1} 未找到作者")
                    
                    # 提取创建时间
                    try:
                        time_element = element.find_element(By.CSS_SELECTOR, self.config.SELECTORS["answer_time"])
                        create_time_text = time_element.text.strip()
                    except NoSuchElementException:
                        create_time_text = ""
                        logger.debug(f"答案 {i+1} 未找到时间")
                    
                    # 提取点赞数
                    try:
                        vote_element = element.find_element(By.CSS_SELECTOR, self.config.SELECTORS["answer_vote_count"])
                        vote_count = self._parse_count(vote_element.text)
                    except NoSuchElementException:
                        vote_count = 0
                        logger.debug(f"答案 {i+1} 未找到点赞数")
                    
                    # 提取评论数
                    try:
                        # 尝试找到评论按钮，通常包含评论数
                        comment_btn = element.find_element(By.CSS_SELECTOR, "button[aria-label*='评论'], .ContentItem-actions button:nth-child(2)")
                        comment_text = comment_btn.text.strip()
                        # 检查按钮文本是否为"添加评论"，如果是则认为无评论
                        if comment_text == "添加评论" or comment_text == "评论":
                            comment_count = 0
                        else:
                            # 从文本中提取数字，例如 "10 条评论" 提取 10
                            comment_count = self._parse_count(comment_text)
                    except NoSuchElementException:
                        comment_count = 0
                        logger.debug(f"答案 {i+1} 未找到评论数")
                    
                    # 提取答案URL
                    try:
                        url_element = element.find_element(By.CSS_SELECTOR, "a[href*='/answer/']")
                        answer_url = url_element.get_attribute('href')
                        if not answer_url.startswith('http'):
                            answer_url = urljoin(self.config.BASE_URL, answer_url)
                    except NoSuchElementException:
                        answer_url = f"{question_url}#answer_{i}"
                    
                    # 提取答案ID
                    answer_id = self.extract_id_from_url(answer_url)
                    if not answer_id or answer_id == str(hash(answer_url)):
                        answer_id = f"{question_id}_{i}"
                    
                    # 创建答案对象
                    answer = Answer(
                        answer_id=answer_id,
                        question_id=question_id,
                        task_id=task_id,
                        content=content,
                        author=author,
                        author_url=author_url,
                        create_time=self.parse_date_to_pg_timestamp(create_time_text),
                        update_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # 添加更新时间
                        vote_count=vote_count,
                        comment_count=comment_count,  # 添加评论数
                        url=answer_url,
                        crawl_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    )
                    
                    # 实时保存答案到数据库
                    if self.db.save_answer(answer):
                        answers.append(answer)
                        logger.info(f"答案已保存: 作者={author}, 点赞={vote_count}, 评论={comment_count}")
                        
                        # 只在评论数不为0时才采集评论
                        if comment_count > 0:
                            logger.info(f"开始采集评论，评论数: {comment_count}")
                            comments = self.crawl_comments(element, answer_id, task_id)
                            for comment in comments:
                                # 时间过滤（如果可以解析）
                                c_dt = self.parse_date_from_text(comment.create_time)
                                if self.is_within_date_range(c_dt, start_date, end_date):
                                    if self.db.save_comment(comment):
                                        total_comments_saved += 1
                            
                            logger.info(f"答案评论处理完成，评论数: {len(comments)}")
                        else:
                            logger.info(f"答案无评论，跳过评论采集")
                    
                except Exception as e:
                    logger.warning(f"解析答案失败 (第{i+1}个): {e}")
                    continue
            
            logger.info(f"答案爬取完成，共保存 {len(answers)} 个答案，{total_comments_saved} 条评论")
            return answers, total_comments_saved
            
        except Exception as e:
            logger.error(f"爬取答案失败: {e}")
            return [], 0
    
    def crawl_comments(self, answer_element, answer_id: str, task_id: str) -> List[Comment]:
        """爬取答案的评论并实时保存到数据库"""
        try:
            logger.info(f"开始爬取答案评论: {answer_id}")
            
            # 检查会话是否有效
            try:
                # 简单的会话检查，尝试执行一个简单的JavaScript命令
                self.driver.execute_script("return document.readyState")
            except WebDriverException as e:
                if "invalid session id" in str(e).lower():
                    logger.error(f"爬取评论时遇到会话错误: {e}")
                    if self.handle_session_error("爬取评论"):
                        # 会话已重置，但无法继续当前评论爬取，返回空列表
                        logger.warning("会话已重置，但无法继续当前评论爬取，将在下次尝试")
                    return []
            
            comments = []
            max_comment_attempts = 3  # 最大评论点击尝试次数
            
            # 首先尝试点击评论展开按钮
            for attempt in range(max_comment_attempts):
                try:
                    # 尝试多种方式定位评论按钮
                    comment_btn = None
                    
                    # 方法1: 使用基于分析结果的正确选择器
                    comment_btn_selectors = [
                        ".Button.QuestionHeader-Comment",  # 问题页面的评论按钮
                        ".Button.ContentItem-action",     # 答案的评论按钮
                        "button[aria-label*='评论']",      # 通过aria-label查找
                        "button[aria-label*='条评论']",    # 包含"条评论"的按钮
                        self.config.SELECTORS["comments_button"],  # 配置的选择器
                    ]
                    
                    for selector in comment_btn_selectors:
                        try:
                            comment_btn = answer_element.find_element(By.CSS_SELECTOR, selector)
                            if comment_btn and comment_btn.is_displayed():
                                logger.info(f"使用选择器 '{selector}' 找到评论按钮 (尝试 {attempt+1}/{max_comment_attempts})")
                                break
                        except NoSuchElementException:
                            continue
                        except Exception as e:
                            logger.debug(f"使用选择器 '{selector}' 查找评论按钮失败: {e}")
                            continue
                    
                    # 方法2: 如果上面的选择器都没找到，尝试更广泛的查找
                    if not comment_btn:
                        try:
                            # 尝试查找所有按钮，然后检查文本内容
                            all_buttons = answer_element.find_elements(By.TAG_NAME, "button")
                            for btn in all_buttons:
                                btn_text = btn.text.strip()
                                aria_label = btn.get_attribute("aria-label") or ""
                                if ("评论" in btn_text or "条评论" in btn_text or 
                                    "评论" in aria_label or "条评论" in aria_label):
                                    comment_btn = btn
                                    logger.info(f"通过文本/aria-label找到评论按钮: '{btn_text}' / '{aria_label}' (尝试 {attempt+1}/{max_comment_attempts})")
                                    break
                        except Exception as e:
                            logger.debug(f"通过文本/aria-label查找评论按钮失败: {e}")
                    
                    # 方法3: 查找包含评论文本的按钮
                    if not comment_btn:
                        buttons = answer_element.find_elements(By.TAG_NAME, "button")
                        for btn in buttons:
                            btn_text = btn.text.strip()
                            if "评论" in btn_text:
                                comment_btn = btn
                                logger.info(f"通过按钮文本找到评论按钮: '{btn_text}' (尝试 {attempt+1}/{max_comment_attempts})")
                                break
                    
                    # 方法4: 查找ContentItem-actions中的按钮
                    if not comment_btn:
                        action_buttons = answer_element.find_elements(By.CSS_SELECTOR, ".ContentItem-actions button, .RichContent-actions button")
                        if len(action_buttons) > 1:
                            # 通常第二个按钮是评论按钮
                            comment_btn = action_buttons[1]
                            logger.info(f"通过操作按钮位置找到评论按钮 (尝试 {attempt+1}/{max_comment_attempts})")
                    
                    # 方法5: 使用XPath查找评论按钮
                    if not comment_btn:
                        try:
                            xpath_expressions = [
                                ".//button[contains(text(), '评论')]",
                                ".//button[contains(@class, 'Button--plain')][contains(text(), '评论')]",
                                ".//button[contains(@class, 'ContentItem-action')][contains(text(), '评论')]",
                                ".//button[contains(@aria-label, '评论')]"
                            ]
                            
                            for xpath in xpath_expressions:
                                elements = answer_element.find_elements(By.XPATH, xpath)
                                if elements:
                                    comment_btn = elements[0]
                                    logger.info(f"通过XPath找到评论按钮: {xpath} (尝试 {attempt+1}/{max_comment_attempts})")
                                    break
                        except Exception as e:
                            logger.debug(f"通过XPath查找评论按钮失败: {e}")
                    
                    # 方法6: 使用JavaScript查找评论按钮
                    if not comment_btn:
                        try:
                            js_script = """
                            function findCommentButton(element) {
                                // 查找所有按钮
                                var buttons = element.querySelectorAll('button');
                                for (var i = 0; i < buttons.length; i++) {
                                    var btn = buttons[i];
                                    // 检查文本内容
                                    if (btn.textContent.includes('评论')) {
                                        return btn;
                                    }
                                    // 检查aria-label属性
                                    if (btn.getAttribute('aria-label') && btn.getAttribute('aria-label').includes('评论')) {
                                        return btn;
                                    }
                                }
                                return null;
                            }
                            return findCommentButton(arguments[0]);
                            """
                            comment_btn = self.driver.execute_script(js_script, answer_element)
                            if comment_btn:
                                logger.info(f"通过JavaScript找到评论按钮 (尝试 {attempt+1}/{max_comment_attempts})")
                        except Exception as e:
                            logger.debug(f"通过JavaScript查找评论按钮失败: {e}")
                    
                    # 方法5: 使用XPath查找包含评论文本的按钮
                    if not comment_btn:
                        try:
                            comment_btn = answer_element.find_element(By.XPATH, ".//button[contains(text(), '评论')]")
                            logger.info(f"通过XPath找到评论按钮 (尝试 {attempt+1}/{max_comment_attempts})")
                        except NoSuchElementException:
                            pass
                    
                    if comment_btn and comment_btn.is_displayed():
                        logger.info(f"发现评论按钮，点击展开评论: {answer_id} (尝试 {attempt+1}/{max_comment_attempts})")
                        
                        # 尝试多种点击方式
                        try:
                            # 方法1: 直接点击
                            comment_btn.click()
                            logger.debug("使用直接点击方法")
                        except Exception as click_error:
                            logger.debug(f"直接点击失败: {click_error}，尝试JavaScript点击")
                            try:
                                # 方法2: JavaScript点击
                                self.driver.execute_script("arguments[0].click();", comment_btn)
                                logger.debug("使用JavaScript点击方法")
                            except Exception as js_error:
                                logger.debug(f"JavaScript点击也失败: {js_error}，尝试Actions点击")
                                try:
                                    # 方法3: Actions点击
                                    ActionChains(self.driver).move_to_element(comment_btn).click().perform()
                                    logger.debug("使用Actions点击方法")
                                except Exception as action_error:
                                    logger.warning(f"所有点击方法都失败: {action_error}")
                                    if attempt == max_comment_attempts - 1:
                                        raise
                                    continue
                        
                        # 增加等待时间，确保评论加载完成
                        self.random_delay(3, 5)
                        
                        # 检查评论是否已加载
                        comment_elements = answer_element.find_elements(By.CSS_SELECTOR, ".CommentItem, .NestComment, .CommentItemV2")
                        if comment_elements:
                            logger.info(f"评论已成功加载，找到 {len(comment_elements)} 个评论")
                            
                            # 检查是否有"加载更多评论"按钮，如果有则点击
                            try:
                                load_more_selectors = self.config.SELECTORS["load_more_comments"].split(", ")
                                for load_more_selector in load_more_selectors:
                                    try:
                                        load_more_btn = self.driver.find_element(By.CSS_SELECTOR, load_more_selector.strip())
                                        if load_more_btn and load_more_btn.is_displayed():
                                            logger.info(f"发现加载更多评论按钮，点击加载全部评论")
                                            self.driver.execute_script("arguments[0].click();", load_more_btn)
                                            self.random_delay(3, 5)  # 等待加载完成
                                            
                                            # 重新获取评论元素
                                            updated_comment_elements = answer_element.find_elements(By.CSS_SELECTOR, ".CommentItem, .NestComment, .CommentItemV2")
                                            if len(updated_comment_elements) > len(comment_elements):
                                                logger.info(f"成功加载更多评论，评论数从 {len(comment_elements)} 增加到 {len(updated_comment_elements)}")
                                                comment_elements = updated_comment_elements
                                            break
                                    except (NoSuchElementException, WebDriverException):
                                        continue
                            except Exception as load_more_error:
                                logger.debug(f"检查加载更多评论按钮失败: {load_more_error}")
                            
                            break
                        else:
                            logger.warning(f"评论按钮已点击，但未找到评论 (尝试 {attempt+1}/{max_comment_attempts})")
                            if attempt < max_comment_attempts - 1:
                                # 如果还有尝试次数，等待更长时间后重试
                                self.random_delay(2, 3)
                    else:
                        logger.warning(f"未找到可见的评论按钮 (尝试 {attempt+1}/{max_comment_attempts})")
                        if attempt < max_comment_attempts - 1:
                            # 尝试滚动到答案元素，使评论按钮可见
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", answer_element)
                            self.random_delay(1, 2)
                
                except Exception as e:
                    logger.warning(f"尝试点击评论按钮失败: {answer_id}, 错误: {e} (尝试 {attempt+1}/{max_comment_attempts})")
                    if attempt < max_comment_attempts - 1:
                        self.random_delay(2, 3)
            
            # 等待评论加载并查找评论元素
            self.random_delay(2, 3)  # 给评论加载更多时间
            
            try:
                # 检查会话是否有效
                try:
                    self.driver.execute_script("return document.readyState")
                except WebDriverException as e:
                    if "invalid session id" in str(e).lower():
                        logger.error(f"查找评论元素时遇到会话错误: {e}")
                        if self.handle_session_error("查找评论元素"):
                            logger.warning("会话已重置，但无法继续当前评论爬取，将在下次尝试")
                        return []
                
                # 首先尝试使用配置的选择器
                comment_elements = []
                
                # 定义更全面的评论选择器列表，基于实际分析结果
                possible_selectors = [
                    # 基于temp文件分析的实际选择器
                    ".CommentItem-content",  # 从分析中发现的评论内容容器
                    ".CommentItem",  # 评论项容器
                    ".Comments-container .CommentItem",  # 评论容器中的评论项
                    ".Comments-container > div",  # 评论容器的直接子元素
                    ".Comments-container div[class*='Comment']",  # 包含Comment的class
                    ".Comments-container div[class*='css-']",  # 动态CSS类名
                    # 原有选择器作为备用
                    self.config.SELECTORS["comments_list"],
                    ".Comments-container .NestComment", 
                    ".Comments-container .NestComment--rootComment",
                    ".Comments-container .NestComment--child",
                    ".Comments-container .CommentItemV2",
                    ".Comments-container div[role='comment']",
                    ".Comments-container div[tabindex='-1']",
                    ".Comments-container .Comment",
                    ".Comments-container li",
                    ".Comments-container > *",
                    # 知乎新版选择器
                    ".css-1ygdre8",  # 知乎新版评论容器
                    ".css-8txec8",   # 知乎新版评论项
                    ".css-1j1mo71",  # 知乎新版评论内容
                    ".CommentContent",  # 评论内容
                    ".RichContent-CommentContent",  # 富文本评论内容
                    "div[data-za-detail-view-path-module='CommentItem']",  # 通过数据属性查找
                    "div[data-za-detail-view-path-module='Comment']",
                    ".AnswerCard .CommentItem",  # 答案卡片中的评论
                    ".AnswerItem .CommentItem",  # 答案项中的评论
                    ".ContentItem-actions + div",  # 操作栏后面的评论区
                    ".RichContent-actions + div"  # 富文本操作栏后面的评论区
                ]
                
                # 尝试所有可能的选择器
                for selector in possible_selectors:
                    try:
                        elements = answer_element.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            comment_elements = elements
                            logger.info(f"使用选择器 '{selector}' 找到 {len(elements)} 个评论")
                            break
                    except Exception as selector_error:
                        logger.debug(f"使用选择器 '{selector}' 查找评论失败: {selector_error}")
                
                # 如果仍然没有找到评论，尝试使用XPath
                if not comment_elements:
                    try:
                        xpath_patterns = [
                            ".//div[contains(@class, 'Comment')]",
                            ".//div[contains(@class, 'comment')]",
                            ".//div[@role='comment']",
                            ".//div[contains(@class, 'CommentItem')]",
                            ".//div[contains(@class, 'NestComment')]"
                        ]
                        
                        for xpath in xpath_patterns:
                            elements = answer_element.find_elements(By.XPATH, xpath)
                            if elements:
                                comment_elements = elements
                                logger.info(f"使用XPath '{xpath}' 找到 {len(elements)} 个评论")
                                break
                    except Exception as xpath_error:
                        logger.debug(f"使用XPath查找评论失败: {xpath_error}")
                
                # 如果评论数量为0，尝试再次点击评论按钮并等待更长时间
                if not comment_elements:
                    logger.warning("未找到评论元素，尝试再次点击评论按钮")
                    try:
                        # 尝试再次查找并点击评论按钮
                        buttons = answer_element.find_elements(By.TAG_NAME, "button")
                        for btn in buttons:
                            if "评论" in btn.text.strip():
                                logger.info("找到评论按钮，再次点击")
                                self.driver.execute_script("arguments[0].click();", btn)
                                self.random_delay(4, 6)  # 等待更长时间
                                
                                # 再次尝试查找评论
                                for selector in possible_selectors:
                                    try:
                                        elements = answer_element.find_elements(By.CSS_SELECTOR, selector)
                                        if elements:
                                            comment_elements = elements
                                            logger.info(f"再次尝试后使用选择器 '{selector}' 找到 {len(elements)} 个评论")
                                            break
                                    except Exception:
                                        pass
                                break
                    except Exception as retry_error:
                        logger.warning(f"再次尝试点击评论按钮失败: {retry_error}")
                
                # 尝试查找隐藏的评论元素
                if not comment_elements:
                    try:
                        # 执行JavaScript来查找可能被隐藏的评论元素
                        js_result = self.driver.execute_script("""
                            return Array.from(document.querySelectorAll('*')).filter(el => {
                                const text = el.textContent.toLowerCase();
                                return (text.includes('评论') || text.includes('comment')) && 
                                       (el.className.includes('Comment') || el.className.includes('comment'));
                            });
                        """)
                        
                        if js_result and len(js_result) > 0:
                            logger.info(f"通过JavaScript找到 {len(js_result)} 个可能的评论元素")
                            comment_elements = js_result
                    except Exception as js_error:
                        logger.debug(f"使用JavaScript查找评论失败: {js_error}")
                
                logger.info(f"最终找到 {len(comment_elements)} 个评论")
                
                for j, comment_element in enumerate(comment_elements):
                    try:
                        # 检查会话是否有效
                        try:
                            self.driver.execute_script("return document.readyState")
                        except WebDriverException as e:
                            if "invalid session id" in str(e).lower():
                                logger.error(f"提取评论内容时遇到会话错误: {e}")
                                if self.handle_session_error("提取评论内容"):
                                    logger.warning("会话已重置，但无法继续当前评论爬取，将在下次尝试")
                                return []
                        
                        # 提取评论内容
                        content = ""
                        max_retries = 3
                        retry_count = 0
                        
                        while not content and retry_count < max_retries:
                            try:
                                # 尝试多种方式获取评论内容
                                try:
                                    content_element = comment_element.find_element(By.CSS_SELECTOR, self.config.SELECTORS["comment_content"])
                                except NoSuchElementException:
                                    # 尝试其他可能的内容选择器
                                    possible_content_selectors = [
                                        ".CommentItem-content", 
                                        ".NestComment-content",
                                        ".CommentItemV2-content",
                                        ".RichText",
                                        "p",  # 简单的段落元素
                                        "div[class*='content']",  # 任何包含content的类名
                                        "div[class*='text']",  # 任何包含text的类名
                                        "div.content",
                                        "div.text",
                                        "span.content",
                                        "div.comment-content",
                                        "div.comment-text",
                                        "div[role='comment'] > div",
                                        "div[role='comment'] p",
                                        # 添加更多可能的选择器
                                        ".css-1j1mo71",  # 知乎新版评论内容
                                        ".CommentContent",  # 评论内容
                                        ".RichContent-CommentContent",  # 富文本评论内容
                                        ".CommentRichText",  # 评论富文本
                                        ".Comment-content",  # 评论内容
                                        ".Comment-text",  # 评论文本
                                        ".css-8txec8 div",  # 知乎新版评论项中的div
                                        ".css-1ygdre8 div",  # 知乎新版评论容器中的div
                                        "div[data-za-detail-view-path-module='CommentItem'] div",  # 通过数据属性查找的评论项中的div
                                        "div[data-za-detail-view-path-module='Comment'] div",  # 通过数据属性查找的评论中的div
                                        "*",  # 最后尝试直接获取元素本身的文本
                                        ".",  # 当前元素
                                        "*[class*='comment']",  # 任何包含comment的类名
                                        "*[class*='Comment']",  # 任何包含Comment的类名
                                        "*[class*='content']",  # 任何包含content的类名
                                        "*[class*='Content']",  # 任何包含Content的类名
                                        "*[class*='text']",  # 任何包含text的类名
                                        "*[class*='Text']",  # 任何包含Text的类名
                                        "*[class*='rich']",  # 任何包含rich的类名
                                        "*[class*='Rich']"  # 任何包含Rich的类名
                                    ]
                                    
                                    content_element = None
                                    for selector in possible_content_selectors:
                                        try:
                                            content_element = comment_element.find_element(By.CSS_SELECTOR, selector)
                                            if content_element:
                                                logger.debug(f"评论 {j+1} 使用选择器 '{selector}' 找到内容元素")
                                                break
                                        except NoSuchElementException:
                                            continue
                                        except Exception as selector_error:
                                            logger.debug(f"评论 {j+1} 使用选择器 '{selector}' 查找内容失败: {selector_error}")
                                            continue
                                
                                # 如果没有找到内容元素，尝试使用XPath
                                if not content_element:
                                    xpath_patterns = [
                                        ".//div[contains(@class, 'content')]",
                                        ".//div[contains(@class, 'text')]",
                                        ".//p",
                                        ".//span[contains(@class, 'content')]",
                                        ".//div[contains(@class, 'RichText')]",
                                        # 添加更多XPath模式
                                        ".//div[contains(@class, 'Comment')]",
                                        ".//div[contains(@class, 'comment')]",
                                        ".//div[contains(@class, 'Content')]",
                                        ".//div[contains(@class, 'Text')]",
                                        ".//span[contains(@class, 'text')]",
                                        ".//span[contains(@class, 'Text')]",
                                        ".//div[contains(@class, 'Rich')]",
                                        ".//div[contains(@class, 'rich')]",
                                        ".//*[contains(@class, 'content')]",
                                        ".//*[contains(@class, 'text')]",
                                        ".//*[contains(@class, 'comment')]",
                                        ".//*[contains(@class, 'Comment')]",
                                        ".//*[contains(@class, 'Rich')]",
                                        ".//*[contains(@class, 'rich')]",
                                        ".//div",  # 最后尝试任何div
                                        ".//span",  # 最后尝试任何span
                                        ".//*"  # 最后尝试任何元素
                                    ]
                                    
                                    for xpath in xpath_patterns:
                                        try:
                                            content_element = comment_element.find_element(By.XPATH, xpath)
                                            if content_element:
                                                logger.debug(f"评论 {j+1} 使用XPath '{xpath}' 找到内容元素")
                                                break
                                        except NoSuchElementException:
                                            continue
                                        except Exception as xpath_error:
                                            logger.debug(f"评论 {j+1} 使用XPath '{xpath}' 查找内容失败: {xpath_error}")
                                            continue
                                
                                # 如果找到了内容元素，获取文本
                                if content_element:
                                    content = content_element.text.strip()
                                    if not content:  # 如果文本为空，尝试获取innerHTML
                                        try:
                                            content = self.driver.execute_script("return arguments[0].innerHTML;", content_element)
                                            content = re.sub('<[^<]+?>', '', content).strip()  # 简单去除HTML标签
                                        except Exception as js_error:
                                            logger.debug(f"评论 {j+1} 获取innerHTML失败: {js_error}")
                                
                                # 如果仍然没有内容，尝试使用JavaScript获取
                                if not content:
                                    try:
                                        content = self.driver.execute_script("""
                                            var element = arguments[0];
                                            var textContent = '';
                                            
                                            // 尝试找到包含文本的子元素 - 扩展选择器列表
                                            var contentSelectors = [
                                                'p', 'div.content', 'div.text', 'span.content', 'div.RichText',
                                                '.CommentItem-content', '.NestComment-content', '.CommentItemV2-content',
                                                '.CommentContent', '.RichContent-CommentContent', '.CommentRichText',
                                                '.Comment-content', '.Comment-text', '.css-1j1mo71',
                                                'div[class*="content"]', 'div[class*="text"]', 'div[class*="comment"]',
                                                'div[class*="Comment"]', 'span[class*="content"]', 'span[class*="text"]',
                                                'div[class*="Rich"]', 'div[class*="rich"]'
                                            ];
                                            
                                            // 构建选择器字符串
                                            var selectorString = contentSelectors.join(', ');
                                            var contentElements = element.querySelectorAll(selectorString);
                                            
                                            if (contentElements.length > 0) {
                                                for (var i = 0; i < contentElements.length; i++) {
                                                    if (contentElements[i].textContent.trim()) {
                                                        textContent += contentElements[i].textContent.trim() + ' ';
                                                    }
                                                }
                                            }
                                            
                                            // 如果没有找到特定元素，尝试查找所有可能包含文本的元素
                                            if (!textContent) {
                                                // 查找所有子元素
                                                var allElements = element.querySelectorAll('*');
                                                for (var i = 0; i < allElements.length; i++) {
                                                    var elementText = allElements[i].textContent.trim();
                                                    // 过滤掉可能是作者、时间等信息的短文本
                                                    if (elementText && elementText.length > 5 && 
                                                        !elementText.match(/^(\d+分钟前|\d+小时前|\d+天前|刚刚|\d{4}-\d{2}-\d{2}|举报|回复|赞同|\d+人赞同)$/)) {
                                                        textContent += elementText + ' ';
                                                    }
                                                }
                                            }
                                            
                                            // 如果仍然没有找到文本，获取元素自身的文本
                                            if (!textContent) {
                                                textContent = element.textContent.trim();
                                            }
                                            
                                            return textContent;
                                        """, comment_element)
                                        
                                        if content:
                                            logger.debug(f"评论 {j+1} 使用JavaScript获取内容成功")
                                    except Exception as js_error:
                                        logger.debug(f"评论 {j+1} 使用JavaScript获取内容失败: {js_error}")
                                
                                # 如果仍然没有内容，直接获取评论元素的文本
                                if not content:
                                    content = comment_element.text.strip()
                                    if content:
                                        logger.debug(f"评论 {j+1} 使用元素自身文本作为内容")
                                    else:
                                        logger.debug(f"评论 {j+1} 未找到内容")
                                
                                # 如果内容太长，可能包含了其他信息，尝试提取有效内容
                                if content:
                                    # 清理内容，移除常见的无关文本
                                    content = re.sub(r'(\d+人赞同了该回答|\d+条评论|\d+个回复|举报|回复|赞同|\d+赞同|\d+分钟前|\d+小时前|\d+天前|刚刚|\d{4}-\d{2}-\d{2})', '', content)
                                    content = re.sub(r'\s+', ' ', content).strip()  # 合并多个空白字符
                                    
                                    # 如果内容仍然很长，尝试提取第一段有意义的文本
                                    if len(content) > 1000:
                                        lines = content.split('\n')
                                        if len(lines) > 1:
                                            # 尝试找到不包含作者、时间等信息的第一段文本
                                            meaningful_content = ""
                                            for line in lines:
                                                line = line.strip()
                                                if line and len(line) > 10 and not any(keyword in line.lower() for keyword in 
                                                                                      ['作者', '时间', '点赞', '回复', '举报', '赞同', '评论', '发布于']):
                                                    meaningful_content += line + " "
                                                    if len(meaningful_content) > 100:  # 如果已经有足够长的内容，可以停止
                                                        break
                                            
                                            if meaningful_content:
                                                content = meaningful_content.strip()
                                                logger.debug(f"评论 {j+1} 内容过长，提取有意义的文本")
                                            else:
                                                # 如果没有找到有意义的内容，取第一段非空文本
                                                for line in lines:
                                                    if line.strip():
                                                        content = line.strip()
                                                        logger.debug(f"评论 {j+1} 内容过长，提取第一段非空文本")
                                                        break
                            
                            except Exception as e:
                                logger.warning(f"评论 {j+1} 提取内容时出错: {e}")
                                retry_count += 1
                                self.random_delay(1, 2)  # 短暂延迟后重试
                                
                                # 如果是最后一次重试，直接获取元素文本
                                if retry_count == max_retries - 1:
                                    try:
                                        content = comment_element.text.strip()
                                        logger.debug(f"评论 {j+1} 最后尝试使用元素文本")
                                    except Exception as last_error:
                                        logger.error(f"评论 {j+1} 最后尝试获取内容失败: {last_error}")
                                        content = ""
                            
                            # 如果获取到内容，跳出重试循环
                            if content:
                                break
                        
                        # 提取评论作者
                        author = "匿名用户"
                        author_url = ""
                        max_retries = 2
                        retry_count = 0
                        
                        while retry_count < max_retries:
                            try:
                                # 尝试多种方式获取作者信息
                                try:
                                    author_element = comment_element.find_element(By.CSS_SELECTOR, self.config.SELECTORS["comment_author"])
                                except NoSuchElementException:
                                    # 尝试其他可能的作者选择器
                                    possible_author_selectors = [
                                        ".UserLink-link", 
                                        ".NestComment-avatar + a",
                                        ".CommentItemV2-meta a",
                                        "a[class*='author']",  # 任何包含author的类名
                                        "a[href*='/people/']",  # 指向用户主页的链接
                                        "a.name",
                                        "a.username",
                                        "a.user-name",
                                        "a.user-link",
                                        "a[href*='u/']",  # 可能的用户链接格式
                                        "div[class*='author'] a",  # 作者容器中的链接
                                        "div[class*='user'] a",  # 用户容器中的链接
                                        ".CommentRichText-username a",  # 富文本评论中的用户名
                                        ".RichText-UserLink a",  # 富文本中的用户链接
                                        ".CommentContent-user a",  # 评论内容中的用户
                                        ".CommentItem-meta a",  # 评论项元数据中的链接
                                        ".CommentItem-author",  # 评论项作者
                                        ".CommentItem-authorName",  # 评论项作者名
                                        "[data-zop-usertoken] a",  # 带有用户标记的元素中的链接
                                        "[data-za-detail-view-element_name='User'] a",  # 知乎数据属性
                                        ".css-1gomreu a",  # 可能的CSS类名
                                        ".css-1oy4rvw a",  # 可能的CSS类名
                                        ".AuthorInfo-name a"  # 作者信息中的名称
                                    ]
                                    
                                    author_element = None
                                    for selector in possible_author_selectors:
                                        try:
                                            elements = comment_element.find_elements(By.CSS_SELECTOR, selector)
                                            for element in elements:
                                                text = element.text.strip()
                                                if text and len(text) < 30:  # 用户名通常不会太长
                                                    author_element = element
                                                    logger.debug(f"评论 {j+1} 使用选择器 '{selector}' 找到作者元素")
                                                    break
                                            if author_element:
                                                break
                                        except NoSuchElementException:
                                            continue
                                        except Exception as selector_error:
                                            logger.debug(f"评论 {j+1} 使用选择器 '{selector}' 查找作者失败: {selector_error}")
                                            continue
                                
                                # 如果没有找到作者元素，尝试使用XPath
                                if not author_element:
                                    xpath_patterns = [
                                        ".//a[contains(@href, '/people/')]",
                                        ".//a[contains(@href, '/u/')]",
                                        ".//a[contains(@class, 'author')]",
                                        ".//a[contains(@class, 'user')]",
                                        ".//div[contains(@class, 'author')]//a",
                                        ".//div[contains(@class, 'user')]//a",
                                        ".//a[contains(@class, 'UserLink')]",
                                        ".//span[contains(@class, 'UserLink')]//a",
                                        ".//div[contains(@class, 'CommentItem-meta')]//a",
                                        ".//div[contains(@class, 'RichContent-inner')]//a[contains(@class, 'UserLink')]",
                                        ".//div[contains(@class, 'CommentRichText')]//a",
                                        ".//div[contains(@class, 'css-')]//a[contains(@href, '/people/')]",
                                        ".//div[contains(@data-zop, 'authorName')]//a",
                                        ".//a[@data-za-detail-view-element_name='User']",
                                        ".//div[contains(@class, 'AuthorInfo')]//a"
                                    ]
                                    
                                    for xpath in xpath_patterns:
                                        try:
                                            elements = comment_element.find_elements(By.XPATH, xpath)
                                            for element in elements:
                                                text = element.text.strip()
                                                if text and len(text) < 30:  # 用户名通常不会太长
                                                    author_element = element
                                                    logger.debug(f"评论 {j+1} 使用XPath '{xpath}' 找到作者元素")
                                                    break
                                            if author_element:
                                                break
                                        except NoSuchElementException:
                                            continue
                                        except Exception as xpath_error:
                                            logger.debug(f"评论 {j+1} 使用XPath '{xpath}' 查找作者失败: {xpath_error}")
                                            continue
                                
                                # 如果找到了作者元素，获取文本和链接
                                if author_element:
                                    author = author_element.text.strip()
                                    if not author:  # 如果文本为空，尝试获取title或aria-label属性
                                        author = author_element.get_attribute('title') or author_element.get_attribute('aria-label') or "匿名用户"
                                    author_url = author_element.get_attribute('href') or ""
                                    logger.debug(f"评论 {j+1} 找到作者: {author}")
                                    break  # 成功获取作者，跳出重试循环
                                else:
                                    # 尝试使用JavaScript查找作者
                                    try:
                                        js_result = self.driver.execute_script("""
                                            var element = arguments[0];
                                            var authorInfo = { name: '', url: '' };
                                            
                                            // 1. 查找所有链接
                                            var links = element.querySelectorAll('a');
                                            for (var i = 0; i < links.length; i++) {
                                                var link = links[i];
                                                var href = link.getAttribute('href') || '';
                                                var text = link.textContent.trim();
                                                
                                                // 检查是否是用户链接
                                                if ((href.includes('/people/') || href.includes('/u/')) && 
                                                    text && text.length < 30 && 
                                                    !text.includes('举报') && !text.includes('回复') && 
                                                    !text.includes('赞同')) {
                                                    authorInfo.name = text;
                                                    authorInfo.url = href;
                                                    return authorInfo;
                                                }
                                            }
                                            
                                            // 2. 尝试通过特定类名查找
                                            var authorSelectors = [
                                                '.UserLink-link', '.CommentItem-author', '.CommentItem-authorName',
                                                '.AuthorInfo-name', '.RichText-UserLink', '.CommentRichText-username',
                                                '[data-zop-usertoken]', '[data-za-detail-view-element_name="User"]'
                                            ];
                                            
                                            for (var i = 0; i < authorSelectors.length; i++) {
                                                var authorElements = element.querySelectorAll(authorSelectors[i]);
                                                for (var j = 0; j < authorElements.length; j++) {
                                                    var el = authorElements[j];
                                                    var text = el.textContent.trim();
                                                    if (text && text.length < 30) {
                                                        authorInfo.name = text;
                                                        // 如果元素本身是链接
                                                        if (el.tagName === 'A') {
                                                            authorInfo.url = el.getAttribute('href') || '';
                                                        } else {
                                                            // 查找元素内的链接
                                                            var innerLink = el.querySelector('a');
                                                            if (innerLink) {
                                                                authorInfo.url = innerLink.getAttribute('href') || '';
                                                            }
                                                        }
                                                        return authorInfo;
                                                    }
                                                }
                                            }
                                            
                                            // 3. 查找所有可能包含作者名的元素
                                            var allElements = element.querySelectorAll('*');
                                            for (var i = 0; i < allElements.length; i++) {
                                                var el = allElements[i];
                                                var className = el.className || '';
                                                
                                                // 检查类名是否包含作者相关关键词
                                                if ((className.includes('author') || className.includes('user') || 
                                                     className.includes('name')) && el.textContent) {
                                                    var text = el.textContent.trim();
                                                    if (text && text.length < 30 && 
                                                        !text.includes('举报') && !text.includes('回复') && 
                                                        !text.includes('赞同')) {
                                                        authorInfo.name = text;
                                                        // 查找元素内的链接
                                                        var innerLink = el.querySelector('a');
                                                        if (innerLink) {
                                                            authorInfo.url = innerLink.getAttribute('href') || '';
                                                        }
                                                        return authorInfo;
                                                    }
                                                }
                                            }
                                            
                                            return authorInfo;
                                        """, comment_element)
                                        
                                        if js_result and js_result.get('name'):
                                            author = js_result.get('name')
                                            author_url = js_result.get('url') or ""
                                            logger.debug(f"评论 {j+1} 使用JavaScript找到作者: {author}")
                                            break  # 成功获取作者，跳出重试循环
                                    except Exception as js_error:
                                        logger.debug(f"评论 {j+1} 使用JavaScript查找作者失败: {js_error}")
                            
                            except Exception as e:
                                logger.warning(f"评论 {j+1} 提取作者时出错: {e}")
                            except WebDriverException as wde:
                                if "invalid session id" in str(wde).lower():
                                    logger.warning(f"提取评论时间时遇到会话错误: {wde}")
                                    self.handle_session_error()
                                else:
                                    logger.warning(f"提取评论时间时遇到WebDriver错误: {wde}")
                            except Exception as e:
                                logger.warning(f"评论 {j+1} 提取时间时出错: {e}")
                            
                            retry_count += 1
                            if retry_count < max_retries:
                                self.random_delay(0.5, 1)  # 短暂延迟后重试
                        
                        if author == "匿名用户":
                            logger.debug(f"评论 {j+1} 未找到作者或提取失败，使用默认值")
                        
                        # 清理作者名称，去除可能的特殊字符
                        author = re.sub(r'[\r\n\t]+', ' ', author).strip()
                        
                        # 提取评论时间
                        create_time = ""
                        max_retries = 2
                        retry_count = 0
                        
                        while retry_count < max_retries:
                            try:
                                # 检查会话是否有效
                                if not self.is_session_valid():
                                    logger.warning("会话无效，尝试重置驱动")
                                    self.handle_session_error()
                                
                                # 尝试多种方式获取评论时间
                                try:
                                    time_element = comment_element.find_element(By.CSS_SELECTOR, self.config.SELECTORS["comment_time"])
                                except NoSuchElementException:
                                    # 尝试其他可能的时间选择器
                                    possible_time_selectors = [
                                        ".CommentItem-meta span", 
                                        ".NestComment-meta span",
                                        ".CommentItemV2-meta span",
                                        ".CommentRichText-time",
                                        ".CommentTime",
                                        ".CommentItem-time",
                                        ".css-1gomreu span",  # 可能的CSS类名
                                        ".css-1oy4rvw span",  # 可能的CSS类名
                                        "[data-tooltip-text*='发布于']",  # 带有发布时间提示的元素
                                        "[data-tooltip*='发布于']",  # 带有发布时间提示的元素
                                        "time",  # HTML5时间元素
                                        "span[data-time]",  # 带有时间数据的span
                                        "span[datetime]",  # 带有日期时间的span
                                        "span.time",  # 时间类span
                                        "span.date",  # 日期类span
                                        "span.timestamp",  # 时间戳类span
                                        "span[class*='time']",  # 任何包含time的类名
                                        "time",  # HTML5时间元素
                                        ".comment-time",
                                        ".comment-date",
                                        "span.date",
                                        "span.timestamp",
                                        "span[datetime]",  # 带有datetime属性的span
                                        "*[data-tooltip-text*='20']",  # 带有日期提示的元素
                                        "*[title*='20']",  # 标题中包含年份的元素
                                        ".CommentItemV2-meta div",  # 评论元数据容器
                                        ".CommentItem-meta div",
                                        ".NestComment-meta div"
                                    ]
                                    
                                    time_element = None
                                    for selector in possible_time_selectors:
                                        try:
                                            elements = comment_element.find_elements(By.CSS_SELECTOR, selector)
                                            for element in elements:
                                                text = element.text.strip()
                                                # 检查是否包含时间相关词汇
                                                if any(keyword in text for keyword in ["分钟前", "小时前", "天前", "月前", "年前", "昨天", "前天", "刚刚", "20"]):
                                                    time_element = element
                                                    logger.debug(f"评论 {j+1} 使用选择器 '{selector}' 找到时间元素: {text}")
                                                    break
                                            if time_element:
                                                break
                                        except NoSuchElementException:
                                            continue
                                        except Exception as selector_error:
                                            logger.debug(f"评论 {j+1} 使用选择器 '{selector}' 查找时间失败: {selector_error}")
                                            continue
                                
                                # 如果没有找到时间元素，尝试使用XPath
                                if not time_element:
                                    xpath_patterns = [
                                        ".//time",
                                        ".//span[contains(@class, 'time')]",
                                        ".//span[contains(text(), '分钟前') or contains(text(), '小时前') or contains(text(), '天前') or contains(text(), '月前') or contains(text(), '年前')]",
                                        ".//span[contains(text(), '昨天') or contains(text(), '前天') or contains(text(), '刚刚')]",
                                        ".//span[contains(@title, '20')]",  # 标题中包含年份的元素
                                        ".//span[contains(@data-tooltip, '发布于')]",  # 带有发布时间提示的元素
                                        ".//span[contains(@data-tooltip-text, '发布于')]",  # 带有发布时间提示的元素
                                        ".//span[@data-time]",  # 带有时间数据的span
                                        ".//span[@datetime]",  # 带有日期时间的span
                                        ".//div[contains(@class, 'meta')]//span",  # 元数据容器中的span
                                        ".//div[contains(@class, 'Meta')]//span",  # 元数据容器中的span
                                        ".//div[contains(@class, 'time')]",  # 包含time的div
                                        ".//div[contains(@class, 'date')]",  # 包含date的div
                                        ".//span[contains(text(), '20')]",  # 包含年份的span
                                        ".//div[contains(text(), '20')]",  # 包含年份的div
                                        ".//span[contains(@data-tooltip, '20')]",  # 提示中包含年份的元素
                                        ".//span[contains(text(), '20')]",  # 文本中包含年份的元素
                                    ]
                                    
                                    for xpath in xpath_patterns:
                                        try:
                                            elements = comment_element.find_elements(By.XPATH, xpath)
                                            for element in elements:
                                                text = element.text.strip()
                                                if text and len(text) < 50:  # 时间文本通常不会太长
                                                    time_element = element
                                                    logger.debug(f"评论 {j+1} 使用XPath '{xpath}' 找到时间元素: {text}")
                                                    break
                                            if time_element:
                                                break
                                        except NoSuchElementException:
                                            continue
                                        except Exception as xpath_error:
                                            logger.debug(f"评论 {j+1} 使用XPath '{xpath}' 查找时间失败: {xpath_error}")
                                            continue
                                
                                # 如果仍然没有找到时间元素，尝试查找所有span元素
                                if not time_element:
                                    try:
                                        spans = comment_element.find_elements(By.TAG_NAME, "span")
                                        for span in spans:
                                            try:
                                                text = span.text.strip()
                                                # 检查文本是否包含时间相关词汇
                                                if any(time_word in text for time_word in ["前", "分钟", "小时", "天", "月", "年", "昨天", "前天", "刚刚"]):
                                                    time_element = span
                                                    logger.debug(f"评论 {j+1} 在span元素中找到时间: {text}")
                                                    break
                                                # 检查是否包含日期格式 (年-月-日 或 月-日)
                                                if re.search(r'\d{4}-\d{1,2}-\d{1,2}|\d{1,2}-\d{1,2}|\d{4}/\d{1,2}/\d{1,2}', text):
                                                    time_element = span
                                                    logger.debug(f"评论 {j+1} 在span元素中找到日期格式: {text}")
                                                    break
                                            except Exception as span_error:
                                                continue
                                    except Exception as span_error:
                                        logger.debug(f"评论 {j+1} 查找span元素失败: {span_error}")
                            except Exception as e:
                                logger.debug(f"评论 {j+1} 提取时间时出错: {e}")
                                continue     
                            # 如果仍然没有找到时间元素，尝试使用JavaScript
                            if not time_element:
                                try:
                                    js_result = self.driver.execute_script("""
                                    function findTimeElement(element) {
                                        // 时间相关关键词
                                        const timeKeywords = ['前', '分钟', '小时', '天', '月', '年', '昨天', '前天', '刚刚', '发布于'];
                                        const datePattern = /\d{4}[-/年]\d{1,2}[-/月]\d{1,2}|\d{1,2}[-/月]\d{1,2}|\d{4}\.\d{1,2}\.\d{1,2}/;
                                        
                                        // 1. 检查特定的时间相关类名
                                        const timeClasses = ['time', 'date', 'timestamp', 'CommentTime', 'CommentRichText-time'];
                                        for (const cls of timeClasses) {
                                            const timeElements = element.querySelectorAll('*[class*="' + cls + '"]');
                                            for (const el of timeElements) {
                                                if (el.textContent && (timeKeywords.some(keyword => el.textContent.includes(keyword)) || datePattern.test(el.textContent))) {
                                                    return el.textContent.trim();
                                                }
                                            }
                                        }
                                        
                                        // 2. 检查特定属性
                                        const timeAttrs = ['data-time', 'datetime', 'data-tooltip', 'data-tooltip-text', 'title'];
                                        for (const attr of timeAttrs) {
                                            const elements = element.querySelectorAll(`*[${attr}]`);
                                            for (const el of elements) {
                                                const attrValue = el.getAttribute(attr);
                                                if (attrValue && (timeKeywords.some(keyword => attrValue.includes(keyword)) || datePattern.test(attrValue))) {
                                                    return attrValue.trim();
                                                }
                                                if (el.textContent && (timeKeywords.some(keyword => el.textContent.includes(keyword)) || datePattern.test(el.textContent))) {
                                                    return el.textContent.trim();
                                                }
                                            }
                                        }
                                        
                                        // 3. 检查元数据区域
                                        const metaElements = element.querySelectorAll('*[class*="meta"], *[class*="Meta"]');
                                        for (const meta of metaElements) {
                                            const spans = meta.querySelectorAll('span');
                                            for (const span of spans) {
                                                if (span.textContent && (timeKeywords.some(keyword => span.textContent.includes(keyword)) || datePattern.test(span.textContent))) {
                                                    return span.textContent.trim();
                                                }
                                            }
                                        }
                                        
                                        // 4. 检查所有文本节点
                                        const textNodes = [];
                                        const walk = document.createTreeWalker(element, NodeFilter.SHOW_TEXT, null, false);
                                        let node;
                                        while (node = walk.nextNode()) {
                                            const text = node.textContent.trim();
                                            if (text && (timeKeywords.some(keyword => text.includes(keyword)) || datePattern.test(text))) {
                                                textNodes.push(text);
                                            }
                                        }
                                        
                                        if (textNodes.length > 0) {
                                            // 返回最短的时间文本，通常时间文本较短
                                            return textNodes.sort((a, b) => a.length - b.length)[0];
                                        }
                                        
                                        return null;
                                    }
                                    
                                    return findTimeElement(arguments[0]);
                                    """, comment_element)
                                    
                                    if js_result:
                                            logger.debug(f"评论 {j+1} 使用JavaScript找到时间: {js_result}")
                                            time_text = js_result
                                except Exception as js_error:
                                    logger.debug(f"评论 {j+1} 使用JavaScript查找时间失败: {js_error}")
                                    pass
                                except Exception as spans_error:
                                    logger.debug(f"评论 {j+1} 查找所有span元素失败: {spans_error}")
                                
                                # 如果找到了时间元素，获取文本
                                if time_element:
                                    # 尝试从元素属性中获取更精确的时间
                                    datetime_attr = time_element.get_attribute('datetime') or time_element.get_attribute('title') or time_element.get_attribute('data-tooltip') or time_element.get_attribute('data-tooltip-text') or time_element.get_attribute('data-time')
                                    if datetime_attr and ('20' in datetime_attr or '-' in datetime_attr or '/' in datetime_attr or '年' in datetime_attr or '月' in datetime_attr):
                                        logger.debug(f"评论 {j+1} 从属性中获取时间: {datetime_attr}")
                                        create_time = datetime_attr
                                    else:
                                        create_time = time_element.text.strip()
                                        logger.debug(f"评论 {j+1} 从文本中获取时间: {create_time}")
                                    
                                    # 清理时间文本
                                    create_time = self.clean_time_text(create_time)
                                    break  # 成功获取时间，跳出重试循环
                                else:
                                    # 尝试使用JavaScript查找时间
                                    try:
                                        js_result = self.driver.execute_script("""
                                            var element = arguments[0];
                                            var timeInfo = { text: '', attr: '' };
                                            
                                            // 时间相关关键词和正则表达式
                                            var timeKeywords = ['前', '分钟', '小时', '天', '月', '年', '昨天', '前天', '刚刚', '发布于'];
                                            var datePattern = /\d{4}[-/年]\d{1,2}[-/月]\d{1,2}|\d{1,2}[-/月]\d{1,2}|\d{4}\.\d{1,2}\.\d{1,2}/;
                                            
                                            // 查找所有可能包含时间的元素
                                            var timeElements = element.querySelectorAll('time, span[class*="time"], div[class*="time"], span[class*="date"], div[class*="date"], span[data-tooltip], span[data-tooltip-text], span[title], span[datetime], span[data-time], *[class*="meta"] span, *[class*="Meta"] span');
                                            for (var i = 0; i < timeElements.length; i++) {
                                                var el = timeElements[i];
                                                
                                                // 检查元素文本
                                                var text = el.textContent.trim();
                                                if (text) {
                                                    // 检查是否包含时间关键词或日期格式
                                                    if (timeKeywords.some(function(keyword) { return text.includes(keyword); }) || datePattern.test(text)) {
                                                        timeInfo.text = text;
                                                        break;
                                                    }
                                                }
                                                
                                                // 检查元素属性
                                                var attrs = ['datetime', 'title', 'data-tooltip', 'data-tooltip-text', 'data-time'];
                                                for (var j = 0; j < attrs.length; j++) {
                                                    if (el.hasAttribute(attrs[j])) {
                                                        var attrValue = el.getAttribute(attrs[j]);
                                                        if (attrValue && (timeKeywords.some(function(keyword) { return attrValue.includes(keyword); }) || datePattern.test(attrValue) || attrValue.includes('20'))) {
                                                            timeInfo.attr = attrValue;
                                                            break;
                                                        }
                                                    }
                                                }
                                                // 已经在上面处理过文本和属性，这里不需要重复
                                                
                                                // 如果已经找到了时间信息，就跳出循环
                                                if (timeInfo.text || timeInfo.attr) {
                                                    break;
                                                }
                                            }
                                            
                                            // 如果没有找到，查找所有span
                                            if (!timeInfo.text) {
                                                var spans = element.querySelectorAll('span');
                                                for (var i = 0; i < spans.length; i++) {
                                                    var text = spans[i].textContent.trim();
                                                    if (text.match(/分钟前|小时前|天前|月前|年前|昨天|前天|刚刚/) || 
                                                        text.match(/\d{4}-\d{1,2}-\d{1,2}/)) {
                                                        timeInfo.text = text;
                                                        break;
                                                    }
                                                }
                                            }
                                            
                                            return timeInfo;
                                        """, comment_element)
                                        
                                        if js_result and (js_result.get('text') or js_result.get('attr')):
                                            create_time = js_result.get('attr') if js_result.get('attr') else js_result.get('text')
                                            logger.debug(f"评论 {j+1} 使用JavaScript找到时间: {create_time}")
                                            break  # 成功获取时间，跳出重试循环
                                    except Exception as js_error:
                                        logger.debug(f"评论 {j+1} 使用JavaScript查找时间失败: {js_error}")
                            
                            
                            retry_count += 1
                            if retry_count < max_retries:
                                self.random_delay(0.5, 1)  # 短暂延迟后重试
                        
                        if not create_time:
                            logger.debug(f"评论 {j+1} 未找到时间或提取失败，使用当前时间作为默认值")
                        
                        # 提取点赞数
                        vote_count = 0
                        max_retries = 2
                        retry_count = 0
                        
                        while retry_count < max_retries:
                            try:
                                # 检查会话是否有效
                                if not self.is_session_valid():
                                    logger.warning("会话无效，尝试重置驱动")
                                    self.handle_session_error()
                                
                                # 尝试多种方式获取点赞数
                                try:
                                    vote_element = comment_element.find_element(By.CSS_SELECTOR, self.config.SELECTORS["comment_vote"])
                                except NoSuchElementException:
                                    # 尝试其他可能的点赞数选择器
                                    possible_vote_selectors = [
                                        ".CommentItem-like", 
                                        ".NestComment-likeCount",
                                        ".CommentItemV2-like",
                                        "button[class*='like']",  # 任何包含like的按钮
                                        "span[class*='vote']",  # 任何包含vote的span
                                        "span[class*='like']",  # 任何包含like的span
                                        ".like-button",
                                        ".vote-button",
                                        ".vote-count",
                                        ".like-count",
                                        "button[aria-label*='赞']",  # 带有赞相关aria-label的按钮
                                        "*[data-tooltip-text*='赞']",  # 带有赞相关提示的元素
                                        "*[title*='赞']",  # 标题中包含赞的元素
                                        "button[class*='Vote']",  # 大写的Vote
                                        "span[class*='Vote']",  # 大写的Vote
                                        "div[class*='like']",  # 包含like的div
                                        "div[class*='vote']",  # 包含vote的div
                                    ]
                                    
                                    vote_element = None
                                    for selector in possible_vote_selectors:
                                        try:
                                            elements = comment_element.find_elements(By.CSS_SELECTOR, selector)
                                            for element in elements:
                                                text = element.text.strip()
                                                # 检查是否是数字或包含数字
                                                if text and (text.isdigit() or re.search(r'\d+', text)):
                                                    vote_element = element
                                                    logger.debug(f"评论 {j+1} 使用选择器 '{selector}' 找到点赞元素: {text}")
                                                    break
                                            if vote_element:
                                                break
                                        except NoSuchElementException:
                                            continue
                                        except Exception as selector_error:
                                            logger.debug(f"评论 {j+1} 使用选择器 '{selector}' 查找点赞失败: {selector_error}")
                                            continue
                                
                                # 如果没有找到点赞元素，尝试使用XPath
                                if not vote_element:
                                    xpath_patterns = [
                                        ".//button[contains(@class, 'like')]",
                                        ".//span[contains(@class, 'like')]",
                                        ".//button[contains(@class, 'vote')]",
                                        ".//span[contains(@class, 'vote')]",
                                        ".//button[contains(@aria-label, '赞')]",
                                        ".//span[contains(text(), '赞')]/following-sibling::span",  # 赞后面的数字
                                        ".//span[text()='赞']/following-sibling::span",  # 精确匹配赞后面的数字
                                        ".//button[contains(@class, 'Vote')]",  # 大写的Vote
                                        ".//span[contains(@class, 'Vote')]",  # 大写的Vote
                                        ".//div[contains(@class, 'like')]",  # 包含like的div
                                        ".//div[contains(@class, 'vote')]",  # 包含vote的div
                                    ]
                                    
                                    for xpath in xpath_patterns:
                                        try:
                                            elements = comment_element.find_elements(By.XPATH, xpath)
                                            for element in elements:
                                                text = element.text.strip()
                                                # 提取数字
                                                if text:
                                                    numbers = re.findall(r'\d+', text)
                                                    if numbers:
                                                        vote_element = element
                                                        logger.debug(f"评论 {j+1} 使用XPath '{xpath}' 找到点赞元素: {text}")
                                                        break
                                            if vote_element:
                                                break
                                        except NoSuchElementException:
                                            continue
                                        except Exception as xpath_error:
                                            logger.debug(f"评论 {j+1} 使用XPath '{xpath}' 查找点赞失败: {xpath_error}")
                                            continue
                                
                                # 如果找到了点赞元素，获取文本并提取数字
                                if vote_element:
                                    vote_text = vote_element.text.strip()
                                    # 尝试使用_parse_count方法解析
                                    vote_count = self._parse_count(vote_text)
                                    
                                    # 如果_parse_count返回0，尝试直接提取数字
                                    if vote_count == 0 and vote_text:
                                        numbers = re.findall(r'\d+', vote_text)
                                        if numbers:
                                            vote_count = int(numbers[0])
                                    
                                    # 如果仍然为0，检查元素的属性
                                    if vote_count == 0:
                                        for attr in ['aria-label', 'title', 'data-tooltip']:
                                            attr_value = vote_element.get_attribute(attr)
                                            if attr_value:
                                                numbers = re.findall(r'\d+', attr_value)
                                                if numbers:
                                                    vote_count = int(numbers[0])
                                                    logger.debug(f"评论 {j+1} 从{attr}属性获取点赞数: {vote_count}")
                                                    break
                                    
                                    logger.debug(f"评论 {j+1} 点赞数: {vote_count}")
                                    break  # 成功获取点赞数，跳出重试循环
                                else:
                                    # 尝试使用JavaScript查找点赞数
                                    try:
                                        js_result = self.driver.execute_script("""
                                            var element = arguments[0];
                                            var voteInfo = { count: 0 };
                                            
                                            // 查找所有可能包含点赞数的元素
                                            var voteElements = element.querySelectorAll('button[class*="like"], span[class*="like"], button[class*="vote"], span[class*="vote"], button[class*="Vote"], span[class*="Vote"], div[class*="like"], div[class*="vote"]');
                                            for (var i = 0; i < voteElements.length; i++) {
                                                var el = voteElements[i];
                                                var text = el.textContent.trim();
                                                var match = text.match(/\d+/);
                                                if (match) {
                                                    voteInfo.count = parseInt(match[0]);
                                                    break;
                                                }
                                                
                                                // 检查属性
                                                var attrs = ['aria-label', 'title', 'data-tooltip'];
                                                for (var j = 0; j < attrs.length; j++) {
                                                    var attrValue = el.getAttribute(attrs[j]);
                                                    if (attrValue) {
                                                        match = attrValue.match(/\d+/);
                                                        if (match) {
                                                            voteInfo.count = parseInt(match[0]);
                                                            break;
                                                        }
                                                    }
                                                }
                                                
                                                if (voteInfo.count > 0) break;
                                            }
                                            
                                            return voteInfo;
                                        """, comment_element)
                                        
                                        if js_result and js_result.get('count'):
                                            vote_count = js_result.get('count')
                                            logger.debug(f"评论 {j+1} 使用JavaScript找到点赞数: {vote_count}")
                                            break  # 成功获取点赞数，跳出重试循环
                                    except Exception as js_error:
                                        logger.debug(f"评论 {j+1} 使用JavaScript查找点赞数失败: {js_error}")
                            
                            except WebDriverException as wde:
                                if "invalid session id" in str(wde).lower():
                                    logger.warning(f"提取点赞数时遇到会话错误: {wde}")
                                    self.handle_session_error()
                                else:
                                    logger.warning(f"提取点赞数时遇到WebDriver错误: {wde}")
                            except Exception as e:
                                logger.warning(f"评论 {j+1} 提取点赞数时出错: {e}")
                            
                            retry_count += 1
                            if retry_count < max_retries and vote_count == 0:  # 只有在未获取到点赞数时才重试
                                self.random_delay(0.5, 1)  # 短暂延迟后重试
                        
                        if vote_count == 0:
                            logger.debug(f"评论 {j+1} 未找到点赞数或点赞数为0")
                        
                        # 生成评论ID
                        comment_id = f"{answer_id}_comment_{j}"
                        
                        # 创建评论对象
                        comment = Comment(
                            comment_id=comment_id,
                            answer_id=answer_id,
                            task_id=task_id,
                            content=content,
                            author=author,
                            author_url=author_url,
                            create_time=self.parse_date_to_pg_timestamp(create_time),
                            vote_count=vote_count,
                            crawl_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        )
                        
                        comments.append(comment)
                        
                    except Exception as e:
                        logger.warning(f"解析评论失败 (第{j+1}个): {e}")
                        continue
                
            except NoSuchElementException:
                logger.debug(f"未找到评论列表: {answer_id}")
            
            logger.info(f"评论爬取完成，共找到 {len(comments)} 个评论")
            return comments
            
        except Exception as e:
            logger.error(f"爬取评论失败: {e}")
            return []
    
    def clean_time_text(self, text: str) -> str:
        """清理时间文本，移除无关内容并标准化格式"""
        if not text:
            return ""
        
        # 移除常见的无关前缀和后缀
        prefixes = ["发布于", "编辑于", "发表于", "回答于", "创建于", "更新于", "提问于"]
        for prefix in prefixes:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
        
        # 移除括号内容，如 (编辑过)
        text = re.sub(r'\(.*?\)', '', text)
        
        # 移除多余空格
        text = re.sub(r'\s+', ' ', text).strip()
        
        # 处理特殊格式
        # 将 "xx-xx xx:xx" 转换为 "xx-xx-xx xx:xx"
        if re.match(r'^\d{2}-\d{2}\s\d{2}:\d{2}$', text):
            current_year = datetime.now().year
            text = f"{current_year}-{text}"
        
        # 将 "昨天 xx:xx" 转换为日期
        if text.startswith("昨天"):
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            time_part = re.search(r'\d{2}:\d{2}', text)
            if time_part:
                text = f"{yesterday} {time_part.group(0)}"
            else:
                text = yesterday
        
        # 将 "前天 xx:xx" 转换为日期
        if text.startswith("前天"):
            day_before_yesterday = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
            time_part = re.search(r'\d{2}:\d{2}', text)
            if time_part:
                text = f"{day_before_yesterday} {time_part.group(0)}"
            else:
                text = day_before_yesterday
        
        # 处理 "x月x日" 格式
        if re.match(r'^\d{1,2}月\d{1,2}日$', text):
            current_year = datetime.now().year
            text = f"{current_year}年{text}"
        
        # 处理 "x年x月x日" 格式
        if re.match(r'^\d{4}年\d{1,2}月\d{1,2}日$', text):
            text = text.replace('年', '-').replace('月', '-').replace('日', '')
        
        # 处理 "刚刚" 格式
        if text == "刚刚":
            text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        return text
    
    def parse_date_from_text(self, text: str) -> Optional[datetime]:
        """从文本中解析日期"""
        if not text:
            return None
        
        # 先清理时间文本
        text = self.clean_time_text(text)
        
        try:
            # 处理相对时间
            if '分钟前' in text:
                minutes = int(re.search(r'(\d+)分钟前', text).group(1))
                return datetime.now() - timedelta(minutes=minutes)
            elif '小时前' in text:
                hours = int(re.search(r'(\d+)小时前', text).group(1))
                return datetime.now() - timedelta(hours=hours)
            elif '天前' in text:
                days = int(re.search(r'(\d+)天前', text).group(1))
                return datetime.now() - timedelta(days=days)
            elif '月前' in text:
                months = int(re.search(r'(\d+)月前', text).group(1))
                return datetime.now() - timedelta(days=months*30)
            elif '年前' in text:
                years = int(re.search(r'(\d+)年前', text).group(1))
                return datetime.now() - timedelta(days=years*365)
            
            # 处理绝对时间格式
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%m-%d %H:%M', '%Y-%m-%d %H:%M', '%m月%d日', '%Y-%m-%d']:
                try:
                    return datetime.strptime(text, fmt)
                except ValueError:
                    continue
            
            return None
            
        except Exception as e:
            logger.debug(f"解析日期失败: {text}, {e}")
            return None
            
    def parse_date_to_pg_timestamp(self, text: str) -> str:
        """将文本日期转换为PostgreSQL兼容的时间戳格式"""
        if not text:
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
        dt = self.parse_date_from_text(text)
        if dt:
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            # 如果无法解析，返回当前时间
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def is_session_valid(self) -> bool:
        """检查当前会话是否有效"""
        try:
            # 尝试执行一个简单的JavaScript命令来检查会话是否有效
            self.driver.execute_script("return document.readyState")
            return True
        except WebDriverException as e:
            if "invalid session id" in str(e).lower():
                logger.warning("检测到无效的会话ID")
                return False
            # 其他WebDriver异常可能不是会话问题
            logger.warning(f"会话检查时遇到其他WebDriver异常: {e}")
            return True  # 不确定的情况下假设会话有效
        except Exception as e:
            logger.warning(f"会话检查时遇到未知异常: {e}")
            return True  # 不确定的情况下假设会话有效
    
    def is_within_date_range(self, dt: Optional[datetime], start_date: str, end_date: str) -> bool:
        """检查日期是否在指定范围内"""
        if not dt:
            return True  # 如果无法解析日期，默认包含
        
        try:
            start_dt = datetime.strptime(start_date, self.config.DATE_FORMAT)
            end_dt = datetime.strptime(end_date, self.config.DATE_FORMAT)
            return start_dt <= dt <= end_dt
        except Exception:
            return True  # 如果日期格式错误，默认包含
    
    def _parse_count(self, count_text: str) -> int:
        """解析数量文本（如：1.2万 -> 12000）"""
        if not count_text:
            return 0
        
        try:
            # 移除非数字字符（除了小数点和万、千等单位）
            count_text = count_text.strip()
            
            if '万' in count_text:
                number = float(re.search(r'([\d.]+)', count_text).group(1))
                return int(number * 10000)
            elif '千' in count_text:
                number = float(re.search(r'([\d.]+)', count_text).group(1))
                return int(number * 1000)
            else:
                # 直接提取数字
                match = re.search(r'([\d,]+)', count_text)
                if match:
                    return int(match.group(1).replace(',', ''))
            
            return 0
            
        except Exception as e:
            logger.debug(f"解析数量失败: {count_text}, {e}")
            return 0
    
    def crawl_by_keyword(self, keyword: str, start_date: str = None, end_date: str = None, process_immediately: bool = True) -> Dict:
        """按关键字爬取数据（PostgreSQL版本）
        
        Args:
            keyword: 搜索关键字
            start_date: 开始日期
            end_date: 结束日期
            process_immediately: 是否立即处理搜索结果（爬取问题详情和答案）
        """
        start_date = start_date or self.config.DEFAULT_START_DATE
        end_date = end_date or self.config.DEFAULT_END_DATE
        
        logger.info(f"开始爬取关键字: {keyword}")
        
        # 创建任务并确保成功
        task_id = None
        try:
            task_id = self.db.create_task(
                keywords=keyword,
                start_date=start_date,
                end_date=end_date
            )
            logger.info(f"创建任务: {task_id}")
        except Exception as e:
            logger.error(f"创建任务失败: {e}")
            # 如果创建失败，尝试获取已存在的任务
            existing_tasks = self.db.get_tasks_by_keyword(keyword)
            if existing_tasks:
                task_id = existing_tasks[0].task_id
                logger.info(f"使用已存在的任务: {task_id}")
            else:
                logger.error("无法创建或找到任务，终止爬取")
                return {
                    'task_id': None,
                    'keyword': keyword,
                    'total_questions': 0,
                    'total_answers': 0,
                    'total_comments': 0,
                    'failed_questions': 0
                }
        
        stats = {
            'task_id': task_id,
            'keyword': keyword,
            'total_questions': 0,
            'total_answers': 0,
            'total_comments': 0,
            'failed_questions': 0
        }
        
        try:
            # 1. 搜索问题并实时保存
            search_results = self.search_questions(keyword, task_id, start_date, end_date)
            stats['total_questions'] = len(search_results)
            
            if not search_results:
                logger.warning("未找到任何搜索结果")
                self.db.update_task_status(task_id, status='completed', total_questions=0, total_answers=0, total_comments=0)
                return stats
            
            # 2. 如果需要立即处理，则遍历每个问题，爬取详情和答案
            if process_immediately:
                for i, search_result in enumerate(search_results, 1):
                    try:
                        logger.info(f"处理问题 {i}/{len(search_results)}: {search_result.title[:50]}...")
                        
                        # 爬取问题详情并实时保存
                        question = self.crawl_question_detail(search_result.question_url, task_id)
                        if question:
                            # 爬取答案及评论并实时保存
                            answers, comments_saved = self.crawl_answers(
                                search_result.question_url, 
                                search_result.question_id, 
                                task_id,
                                start_date, 
                                end_date
                            )
                            stats['total_answers'] += len(answers)
                            stats['total_comments'] += comments_saved
                            
                            logger.info(f"问题处理完成，答案数: {len(answers)}，评论数: {comments_saved}")
                        else:
                            stats['failed_questions'] += 1
                            logger.warning(f"问题详情爬取失败: {search_result.title}")
                        
                        # 随机延时，避免过于频繁的请求
                        self.random_delay(2, 5)
                        
                    except Exception as e:
                        stats['failed_questions'] += 1
                        logger.error(f"处理问题失败: {e}")
                        continue
            
            # 更新任务状态为完成
            self.db.update_task_status(
                task_id,
                status='completed',
                total_questions=stats['total_questions'],
                total_answers=stats['total_answers'],
                total_comments=stats['total_comments']
            )
            
            logger.info(f"爬取完成: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"爬取过程中发生错误: {e}")
            # 更新任务状态为失败
            self.db.update_task_status(task_id, status='failed')
            return stats
    
    def resume_task(self, task_id: str) -> Dict:
        """恢复中断的任务"""
        logger.info(f"恢复任务: {task_id}")
        
        # 获取任务信息
        task_info = self.db.get_task_info(task_id)
        if not task_info:
            logger.error(f"任务不存在: {task_id}")
            return {}
        
        logger.info(f"任务信息: {task_info.keywords}, 状态: {task_info.status}")
        
        stats = {
            'task_id': task_id,
            'keyword': task_info.keywords,
            'total_questions': 0,
            'total_answers': 0,
            'total_comments': 0,
            'failed_questions': 0
        }
        
        try:
            # 获取未处理的搜索结果
            unprocessed_search_results = self.db.get_unprocessed_search_results(task_id)
            logger.info(f"发现 {len(unprocessed_search_results)} 个未处理的搜索结果")
            
            if not unprocessed_search_results:
                # 检查是否有未处理的问题
                unprocessed_questions = self.db.get_unprocessed_questions(task_id)
                logger.info(f"发现 {len(unprocessed_questions)} 个未处理的问题")
                
                if not unprocessed_questions:
                    # 检查是否有未处理的答案
                    unprocessed_answers = self.db.get_unprocessed_answers(task_id)
                    logger.info(f"发现 {len(unprocessed_answers)} 个未处理的答案")
                    
                    if not unprocessed_answers:
                        logger.info("任务已完成，无需恢复")
                        self.db.update_task_status(task_id, status='completed')
                        return stats
                    
                    # 处理未处理的答案（爬取评论）
                    for answer in unprocessed_answers:
                        try:
                            # 这里需要重新访问答案页面来爬取评论
                            # 由于答案已存在，主要是爬取评论
                            logger.info(f"处理答案评论: {answer.answer_id}")
                            
                            # 构建答案URL并访问
                            if answer.url:
                                self.driver.get(answer.url)
                                self.random_delay()
                                
                                # 查找答案元素并爬取评论
                                answer_elements = self.driver.find_elements(By.CSS_SELECTOR, self.config.SELECTORS["answer_list"])
                                if answer_elements:
                                    comments = self.crawl_comments(answer_elements[0], answer.answer_id, task_id)
                                    for comment in comments:
                                        if self.db.save_comment(comment):
                                            stats['total_comments'] += 1
                                    
                                    # 标记答案为已处理
                                    self.db.mark_answer_processed(answer.answer_id)
                            
                        except Exception as e:
                            logger.error(f"处理答案失败: {e}")
                            continue
                
                else:
                    # 处理未处理的问题（爬取答案和评论）
                    for question in unprocessed_questions:
                        try:
                            logger.info(f"处理问题: {question.title[:50]}...")
                            
                            # 爬取答案及评论
                            answers, comments_saved = self.crawl_answers(
                                question.url,
                                question.question_id,
                                task_id,
                                task_info.start_date,
                                task_info.end_date
                            )
                            
                            stats['total_answers'] += len(answers)
                            stats['total_comments'] += comments_saved
                            
                            # 标记问题为已处理
                            self.db.mark_question_processed(question.question_id)
                            
                            logger.info(f"问题处理完成，答案数: {len(answers)}，评论数: {comments_saved}")
                            
                        except Exception as e:
                            stats['failed_questions'] += 1
                            logger.error(f"处理问题失败: {e}")
                            continue
            
            else:
                # 处理未处理的搜索结果（爬取问题详情、答案和评论）
                for i, search_result in enumerate(unprocessed_search_results, 1):
                    try:
                        logger.info(f"处理搜索结果 {i}/{len(unprocessed_search_results)}: {search_result.title[:50]}...")
                        
                        # 爬取问题详情
                        question = self.crawl_question_detail(search_result.question_url, task_id)
                        if question:
                            # 爬取答案及评论
                            answers, comments_saved = self.crawl_answers(
                                search_result.question_url,
                                search_result.question_id,
                                task_id,
                                task_info.start_date,
                                task_info.end_date
                            )
                            
                            stats['total_questions'] += 1
                            stats['total_answers'] += len(answers)
                            stats['total_comments'] += comments_saved
                            
                            # 标记搜索结果为已处理
                            self.db.mark_search_result_processed(search_result.question_id, task_id)
                            
                            logger.info(f"搜索结果处理完成，答案数: {len(answers)}，评论数: {comments_saved}")
                        else:
                            stats['failed_questions'] += 1
                            logger.warning(f"问题详情爬取失败: {search_result.title}")
                        
                        # 随机延时
                        self.random_delay(2, 5)
                        
                    except Exception as e:
                        stats['failed_questions'] += 1
                        logger.error(f"处理搜索结果失败: {e}")
                        continue
            
            # 更新任务状态
            self.db.update_task_status(
                task_id,
                status='completed',
                total_questions=stats['total_questions'],
                total_answers=stats['total_answers'],
                total_comments=stats['total_comments']
            )
            
            logger.info(f"任务恢复完成: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"任务恢复失败: {e}")
            self.db.update_task_status(task_id, status='failed')
            return stats
    
    def batch_search_questions(self, keyword_list: List[str], start_date: str = None, end_date: str = None) -> List[str]:
        """批量搜索多个关键字的问题，但不立即处理详情和答案
        
        Args:
            keyword_list: 搜索关键字列表
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            任务ID列表
        """
        start_date = start_date or self.config.DEFAULT_START_DATE
        end_date = end_date or self.config.DEFAULT_END_DATE
        
        logger.info(f"开始批量搜索关键字，数量: {len(keyword_list)}")
        task_ids = []
        
        for i, keyword in enumerate(keyword_list, 1):
            try:
                logger.info(f"搜索关键字 {i}/{len(keyword_list)}: {keyword}")
                
                # 使用crawl_by_keyword但不立即处理搜索结果
                stats = self.crawl_by_keyword(keyword, start_date, end_date, process_immediately=False)
                if stats['task_id']:
                    task_ids.append(stats['task_id'])
                    logger.info(f"关键字 '{keyword}' 搜索完成，找到问题数: {stats['total_questions']}")
                
                # 随机延时，避免过于频繁的请求
                self.random_delay(1, 3)
                
            except Exception as e:
                logger.error(f"搜索关键字 '{keyword}' 失败: {e}")
                continue
        
        logger.info(f"批量搜索完成，成功创建任务数: {len(task_ids)}")
        return task_ids
    
    def batch_process_search_results(self, task_ids: List[str]) -> Dict:
        """批量处理之前搜索的结果（爬取问题详情和答案）
        
        Args:
            task_ids: 任务ID列表
            
        Returns:
            统计信息
        """
        if not task_ids:
            logger.warning("没有任务需要处理")
            return {
                'total_tasks': 0,
                'processed_tasks': 0,
                'total_questions': 0,
                'total_answers': 0,
                'total_comments': 0,
                'failed_questions': 0
            }
        
        logger.info(f"开始批量处理搜索结果，任务数: {len(task_ids)}")
        
        # 统计信息
        stats = {
            'total_tasks': len(task_ids),
            'processed_tasks': 0,
            'total_questions': 0,
            'total_answers': 0,
            'total_comments': 0,
            'failed_questions': 0
        }
        
        # 获取所有任务的未处理搜索结果
        all_search_results = []
        for task_id in task_ids:
            try:
                # 获取任务信息
                task_info = self.db.get_task_info(task_id)
                if not task_info:
                    logger.error(f"任务不存在: {task_id}")
                    continue
                
                # 获取未处理的搜索结果
                search_results = self.db.get_unprocessed_search_results(task_id)
                logger.info(f"任务 {task_id} 有 {len(search_results)} 个未处理的搜索结果")
                all_search_results.extend(search_results)
            except Exception as e:
                logger.error(f"获取任务 {task_id} 的搜索结果失败: {e}")
        
        # 对搜索结果进行去重（按问题ID去重）
        unique_results = {}
        for result in all_search_results:
            if result.question_id not in unique_results:
                unique_results[result.question_id] = result
        
        unique_search_results = list(unique_results.values())
        logger.info(f"去重后共有 {len(unique_search_results)} 个搜索结果需要处理")
        
        # 处理去重后的搜索结果
        for i, search_result in enumerate(unique_search_results, 1):
            try:
                logger.info(f"处理问题 {i}/{len(unique_search_results)}: {search_result.title[:50]}...")
                
                # 爬取问题详情并实时保存
                question = self.crawl_question_detail(search_result.question_url, search_result.task_id)
                if question:
                    # 爬取答案及评论并实时保存
                    task_info = self.db.get_task_info(search_result.task_id)
                    answers, comments_saved = self.crawl_answers(
                        search_result.question_url, 
                        search_result.question_id, 
                        search_result.task_id,
                        task_info.start_date, 
                        task_info.end_date
                    )
                    stats['total_questions'] += 1
                    stats['total_answers'] += len(answers)
                    stats['total_comments'] += comments_saved
                    
                    # 标记搜索结果为已处理
                    self.db.mark_processed('search_results', 'question_id', search_result.question_id, search_result.task_id)
                    
                    logger.info(f"问题处理完成，答案数: {len(answers)}，评论数: {comments_saved}")
                else:
                    stats['failed_questions'] += 1
                    logger.warning(f"问题详情爬取失败: {search_result.title}")
                
                # 随机延时，避免过于频繁的请求
                self.random_delay(2, 5)
                
            except Exception as e:
                stats['failed_questions'] += 1
                logger.error(f"处理问题失败: {e}")
                continue
        
        # 更新所有任务的状态为完成
        for task_id in task_ids:
            try:
                self.db.update_task_status(
                    task_id,
                    status='completed',
                    stage='answers'
                )
                stats['processed_tasks'] += 1
            except Exception as e:
                logger.error(f"更新任务 {task_id} 状态失败: {e}")
        
        logger.info(f"批量处理完成: {stats}")
        return stats
    
    def list_incomplete_tasks(self) -> List[TaskInfo]:
        """列出所有未完成的任务"""
        return self.db.get_unfinished_tasks()
    
    def close(self):
        """关闭浏览器和数据库连接"""
        try:
            if self.driver:
                self.driver.quit()
                logger.info("浏览器已关闭")
        except Exception as e:
            logger.warning(f"关闭浏览器失败: {e}")
        
        try:
            if self.db:
                self.db.close()
                logger.info("数据库连接已关闭")
        except Exception as e:
            logger.warning(f"关闭数据库连接失败: {e}")