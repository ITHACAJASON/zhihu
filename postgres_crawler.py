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
            
            # 随机User-Agent
            user_agent = random.choice(self.config.USER_AGENTS)
            options.add_argument(f'--user-agent={user_agent}')
            
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
    
    def random_delay(self, min_delay: float = None, max_delay: float = None):
        """随机延时"""
        min_delay = min_delay or self.config.MIN_DELAY
        max_delay = max_delay or self.config.MAX_DELAY
        delay = random.uniform(min_delay, max_delay)
        time.sleep(delay)
    
    def scroll_to_load_more(self, scroll_times: int = 5) -> bool:
        """滚动页面加载更多内容"""
        try:
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            
            for i in range(scroll_times):
                # 滚动到页面底部
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                
                # 等待新内容加载
                time.sleep(self.config.SCROLL_PAUSE_TIME)
                
                # 检查页面高度是否有变化
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    logger.info(f"页面高度未变化，停止滚动 (第{i+1}次)")
                    break
                
                last_height = new_height
                logger.debug(f"滚动第{i+1}次，页面高度: {new_height}")
            
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
            self.scroll_to_load_more(10)
            
            # 解析搜索结果
            result_elements = self.driver.find_elements(By.CSS_SELECTOR, self.config.SELECTORS["search_results"])
            logger.info(f"找到 {len(result_elements)} 个搜索结果元素")
            
            for i, element in enumerate(result_elements):
                try:
                    # 提取问题链接
                    link_element = element.find_element(By.CSS_SELECTOR, "h2 a")
                    question_url = link_element.get_attribute('href')
                    question_title = link_element.text.strip()
                    
                    if not question_url or not question_title:
                        continue
                    
                    # 确保URL是完整的
                    if not question_url.startswith('http'):
                        question_url = urljoin(self.config.BASE_URL, question_url)
                    
                    # 提取问题ID
                    question_id = self.extract_id_from_url(question_url)
                    
                    # 创建搜索结果对象
                    search_result = SearchResult(
                        task_id=task_id,
                        question_id=question_id,
                        title=question_title,
                        url=question_url,
                        keyword=keyword,
                        rank=i + 1,
                        crawl_time=datetime.now().isoformat()
                    )
                    
                    # 实时保存搜索结果到数据库
                    if self.db.save_search_result(search_result):
                        search_results.append(search_result)
                        logger.info(f"搜索结果已保存: {question_title[:50]}...")
                    
                except Exception as e:
                    logger.warning(f"解析搜索结果失败 (第{i+1}个): {e}")
                    continue
            
            logger.info(f"搜索完成，共找到并保存 {len(search_results)} 个结果")
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
                
                self.driver.get(question_url)
                self.random_delay()
                
                # 等待页面加载
                self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                
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
                    content_element = self.driver.find_element(By.CSS_SELECTOR, self.config.SELECTORS["question_content"])
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
                    create_time="",  # 知乎问题页面通常不显示创建时间
                    follow_count=follow_count,
                    view_count=view_count,
                    answer_count=answer_count,
                    url=question_url,
                    tags=tags,
                    crawl_time=datetime.now().isoformat()
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
            
            self.driver.get(question_url)
            self.random_delay()
            
            # 等待页面加载
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            # 检查并点击"查看全部回答"按钮（如果存在）
            try:
                load_all_answers_btn = self.driver.find_element(By.CSS_SELECTOR, "#root > div > main > div > div > div.Question-main > div.ListShortcut > div > div:nth-child(1) > a")
                if load_all_answers_btn.is_displayed():
                    logger.info("发现'查看全部回答'按钮，点击加载全部回答")
                    self.driver.execute_script("arguments[0].click();", load_all_answers_btn)
                    self.random_delay(2, 3)
            except NoSuchElementException:
                logger.debug("未发现'查看全部回答'按钮，继续正常流程")
            
            # 等待答案列表加载
            try:
                self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, self.config.SELECTORS["answer_list"])))
            except TimeoutException:
                logger.warning("答案列表加载超时")
                return [], 0
            
            # 滚动加载更多答案
            self.scroll_to_load_more(15)
            
            # 获取所有答案元素
            answer_elements = self.driver.find_elements(By.CSS_SELECTOR, self.config.SELECTORS["answer_list"])
            logger.info(f"找到 {len(answer_elements)} 个答案")
            
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
                        create_time=create_time_text,
                        vote_count=vote_count,
                        url=answer_url,
                        crawl_time=datetime.now().isoformat()
                    )
                    
                    # 实时保存答案到数据库
                    if self.db.save_answer(answer):
                        answers.append(answer)
                        logger.info(f"答案已保存: 作者={author}, 点赞={vote_count}")
                        
                        # 抓取评论并实时保存
                        comments = self.crawl_comments(element, answer_id, task_id)
                        for comment in comments:
                            # 时间过滤（如果可以解析）
                            c_dt = self.parse_date_from_text(comment.create_time)
                            if self.is_within_date_range(c_dt, start_date, end_date):
                                if self.db.save_comment(comment):
                                    total_comments_saved += 1
                        
                        logger.info(f"答案评论处理完成，评论数: {len(comments)}")
                    
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
            
            comments = []
            
            # 首先尝试点击评论展开按钮
            try:
                comment_btn = answer_element.find_element(By.CSS_SELECTOR, "button[aria-label*='评论']")
                if comment_btn.is_displayed():
                    logger.info(f"发现评论按钮，点击展开评论: {answer_id}")
                    self.driver.execute_script("arguments[0].click();", comment_btn)
                    self.random_delay(1, 2)
            except NoSuchElementException:
                logger.debug(f"未发现评论按钮: {answer_id}")
            
            # 查找评论元素
            try:
                comment_elements = answer_element.find_elements(By.CSS_SELECTOR, self.config.SELECTORS["comment_list"])
                logger.info(f"找到 {len(comment_elements)} 个评论")
                
                for j, comment_element in enumerate(comment_elements):
                    try:
                        # 提取评论内容
                        try:
                            content_element = comment_element.find_element(By.CSS_SELECTOR, self.config.SELECTORS["comment_content"])
                            content = content_element.text.strip()
                        except NoSuchElementException:
                            content = ""
                            logger.debug(f"评论 {j+1} 未找到内容")
                        
                        # 提取评论作者
                        try:
                            author_element = comment_element.find_element(By.CSS_SELECTOR, self.config.SELECTORS["comment_author"])
                            author = author_element.text.strip()
                            author_url = author_element.get_attribute('href') or ""
                        except NoSuchElementException:
                            author = "匿名用户"
                            author_url = ""
                            logger.debug(f"评论 {j+1} 未找到作者")
                        
                        # 提取评论时间
                        try:
                            time_element = comment_element.find_element(By.CSS_SELECTOR, self.config.SELECTORS["comment_time"])
                            create_time = time_element.text.strip()
                        except NoSuchElementException:
                            create_time = ""
                            logger.debug(f"评论 {j+1} 未找到时间")
                        
                        # 提取点赞数
                        try:
                            vote_element = comment_element.find_element(By.CSS_SELECTOR, self.config.SELECTORS["comment_vote_count"])
                            vote_count = self._parse_count(vote_element.text)
                        except NoSuchElementException:
                            vote_count = 0
                            logger.debug(f"评论 {j+1} 未找到点赞数")
                        
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
                            create_time=create_time,
                            vote_count=vote_count,
                            crawl_time=datetime.now().isoformat()
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
    
    def parse_date_from_text(self, text: str) -> Optional[datetime]:
        """从文本中解析日期"""
        if not text:
            return None
        
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
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%m-%d %H:%M', '%m月%d日']:
                try:
                    return datetime.strptime(text, fmt)
                except ValueError:
                    continue
            
            return None
            
        except Exception as e:
            logger.debug(f"解析日期失败: {text}, {e}")
            return None
    
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
    
    def crawl_by_keyword(self, keyword: str, start_date: str = None, end_date: str = None) -> Dict:
        """按关键字爬取数据（PostgreSQL版本）"""
        start_date = start_date or self.config.DEFAULT_START_DATE
        end_date = end_date or self.config.DEFAULT_END_DATE
        
        logger.info(f"开始爬取关键字: {keyword}")
        
        # 创建任务
        task_id = self.db.create_task(
            keywords=keyword,
            start_date=start_date,
            end_date=end_date
        )
        
        logger.info(f"创建任务: {task_id}")
        
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
                self.db.update_task_status(task_id, 'completed', 0, 0, 0)
                return stats
            
            # 2. 遍历每个问题，爬取详情和答案
            for i, search_result in enumerate(search_results, 1):
                try:
                    logger.info(f"处理问题 {i}/{len(search_results)}: {search_result.title[:50]}...")
                    
                    # 爬取问题详情并实时保存
                    question = self.crawl_question_detail(search_result.url, task_id)
                    if question:
                        # 爬取答案及评论并实时保存
                        answers, comments_saved = self.crawl_answers(
                            search_result.url, 
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
                task_id=task_id,
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
            self.db.update_task_status(task_id, 'failed')
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
                        self.db.update_task_status(task_id, 'completed')
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
                        question = self.crawl_question_detail(search_result.url, task_id)
                        if question:
                            # 爬取答案及评论
                            answers, comments_saved = self.crawl_answers(
                                search_result.url,
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
                task_id=task_id,
                status='completed',
                total_questions=stats['total_questions'],
                total_answers=stats['total_answers'],
                total_comments=stats['total_comments']
            )
            
            logger.info(f"任务恢复完成: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"任务恢复失败: {e}")
            self.db.update_task_status(task_id, 'failed')
            return stats
    
    def list_incomplete_tasks(self) -> List[TaskInfo]:
        """列出所有未完成的任务"""
        return self.db.get_incomplete_tasks()
    
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