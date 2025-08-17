"""
知乎爬虫主要模块
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
from models import DatabaseManager, Question, Answer, Comment
from selenium.webdriver.chrome.service import Service


class ZhihuCrawler:
    """知乎爬虫主类"""
    
    def __init__(self, headless: bool = True, db_path: str = None):
        self.config = ZhihuConfig()
        self.headless = headless
        self.driver = None
        self.wait = None
        self.db = DatabaseManager(db_path)
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
            
            # 设置超时
            self.driver.set_page_load_timeout(self.config.PAGE_LOAD_TIMEOUT)
            self.wait = WebDriverWait(self.driver, self.config.ELEMENT_WAIT_TIMEOUT)
            
            logger.info("Chrome驱动初始化成功")
            
        except Exception as e:
            logger.error(f"Chrome驱动初始化失败: {e}")
            raise
    
    def save_cookies(self):
        """保存当前会话的cookies"""
        try:
            # 确保cookies目录存在
            cookies_dir = os.path.dirname(self.config.COOKIES_FILE)
            if not os.path.exists(cookies_dir):
                os.makedirs(cookies_dir)
            
            # 获取当前cookies
            cookies = self.driver.get_cookies()
            
            # 保存到文件
            with open(self.config.COOKIES_FILE, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Cookies已保存到: {self.config.COOKIES_FILE}")
            
        except Exception as e:
            logger.error(f"保存cookies失败: {e}")
    
    def load_cookies(self):
        """加载已保存的cookies"""
        try:
            if not self.config.ENABLE_COOKIE_LOGIN:
                logger.info("Cookie登录功能已禁用")
                return
            
            if not os.path.exists(self.config.COOKIES_FILE):
                logger.info("未找到cookies文件，将在首次登录后保存")
                return
            
            # 先访问知乎主页
            self.driver.get(self.config.BASE_URL)
            self.random_delay()
            
            # 加载cookies
            with open(self.config.COOKIES_FILE, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            
            # 添加cookies到浏览器
            for cookie in cookies:
                try:
                    # 确保cookie的domain正确
                    if 'domain' not in cookie:
                        cookie['domain'] = self.config.COOKIE_DOMAIN
                    self.driver.add_cookie(cookie)
                except Exception as e:
                    logger.warning(f"添加cookie失败: {e}")
                    continue
            
            # 刷新页面使cookies生效
            self.driver.refresh()
            self.random_delay()
            
            logger.info("Cookies加载成功")
            
        except Exception as e:
            logger.error(f"加载cookies失败: {e}")
    
    def check_login_status(self) -> bool:
        """检查登录状态"""
        try:
            # 访问知乎主页
            self.driver.get(self.config.BASE_URL)
            self.random_delay()
            
            # 检查是否存在登录按钮（未登录状态）
            login_buttons = self.driver.find_elements(By.CSS_SELECTOR, ".SignFlow-accountInput, .Button--blue")
            if login_buttons:
                for btn in login_buttons:
                    if "登录" in btn.text or "注册" in btn.text:
                        logger.info("当前未登录状态")
                        return False
            
            # 检查是否存在用户头像或用户名（已登录状态）
            user_elements = self.driver.find_elements(By.CSS_SELECTOR, ".AppHeader-userInfo, .Avatar, .Menu-item")
            if user_elements:
                logger.info("当前已登录状态")
                return True
            
            logger.info("无法确定登录状态")
            return False
            
        except Exception as e:
            logger.error(f"检查登录状态失败: {e}")
            return False
    
    def manual_login_prompt(self):
        """提示用户手动登录"""
        try:
            if self.headless:
                logger.warning("当前为无头模式，无法进行手动登录。请使用 --no-headless 参数")
                return False
            
            logger.info("请在浏览器中手动登录知乎...")
            logger.info("登录完成后，请在终端按回车键继续...")
            
            # 访问登录页面
            self.driver.get("https://www.zhihu.com/signin")
            
            # 等待用户手动登录
            input("登录完成后按回车键继续...")
            
            # 检查登录状态
            if self.check_login_status():
                # 保存cookies
                self.save_cookies()
                logger.info("登录成功，cookies已保存")
                return True
            else:
                logger.warning("登录验证失败")
                return False
                
        except Exception as e:
            logger.error(f"手动登录过程出错: {e}")
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
                
                # 检查是否有新内容
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    logger.info(f"第{i+1}次滚动未发现新内容，停止滚动")
                    break
                
                last_height = new_height
                logger.info(f"第{i+1}次滚动完成，页面高度: {new_height}")
            
            return True
        except Exception as e:
            logger.error(f"滚动加载失败: {e}")
            return False
    
    def extract_id_from_url(self, url: str) -> str:
        """从URL中提取ID"""
        try:
            # 匹配问题ID: /question/123456
            question_match = re.search(r'/question/(\d+)', url)
            if question_match:
                return question_match.group(1)
            
            # 匹配答案ID: /answer/123456
            answer_match = re.search(r'/answer/(\d+)', url)
            if answer_match:
                return answer_match.group(1)
            
            # 从查询参数中提取
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            
            if 'id' in query_params:
                return query_params['id'][0]
            
            # 最后尝试从路径中提取数字
            path_numbers = re.findall(r'/(\d+)', parsed_url.path)
            if path_numbers:
                return path_numbers[-1]
            
            return ""
        except Exception as e:
            logger.error(f"提取ID失败: {e}, URL: {url}")
            return ""
    
    def search_questions(self, keyword: str, start_date: str = None, end_date: str = None) -> List[Dict]:
        """搜索问题"""
        start_date = start_date or self.config.DEFAULT_START_DATE
        end_date = end_date or self.config.DEFAULT_END_DATE
        
        if not self.config.validate_date_range(start_date, end_date):
            raise ValueError("日期范围无效")
        
        logger.info(f"开始搜索关键字: {keyword}, 时间范围: {start_date} 至 {end_date}")
        
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
                logger.warning(f"等待搜索结果超时，当前选择器: {self.config.SELECTORS['search_results']}")
                # 尝试其他可能的选择器
                alternative_selectors = [
                    ".SearchResult-Card",
                    ".List-item",
                    "[data-zop-feedlist-item]",
                    ".ContentItem"
                ]
                found_selector = None
                for selector in alternative_selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            logger.info(f"找到替代选择器: {selector}, 元素数量: {len(elements)}")
                            found_selector = selector
                            break
                    except:
                        continue
                
                if not found_selector:
                    # 输出页面源码的前1000字符用于调试
                    page_source_preview = self.driver.page_source[:1000]
                    logger.debug(f"页面源码预览: {page_source_preview}")
                    raise TimeoutException("未找到任何搜索结果元素")
                else:
                    # 更新配置中的选择器
                    self.config.SELECTORS["search_results"] = found_selector
            
            # 滚动加载更多结果
            self.scroll_to_load_more(10)
            
            # 提取搜索结果
            results = []
            result_elements = self.driver.find_elements(By.CSS_SELECTOR, self.config.SELECTORS["search_results"])
            
            for element in result_elements:
                try:
                    # 提取问题标题和链接
                    title_element = element.find_element(By.CSS_SELECTOR, self.config.SELECTORS["search_question_title"])
                    title = title_element.text.strip()
                    url = title_element.get_attribute("href")
                    
                    if not title or not url:
                        continue
                    
                    # 提取问题ID
                    question_id = self.extract_id_from_url(url)
                    if not question_id:
                        continue
                    
                    # 提取预览内容
                    preview = ""
                    try:
                        preview_element = element.find_element(By.CSS_SELECTOR, self.config.SELECTORS["search_answer_preview"])
                        preview = preview_element.text.strip()[:200]  # 限制长度
                    except NoSuchElementException:
                        pass
                    
                    result = {
                        'question_id': question_id,
                        'title': title,
                        'url': url,
                        'preview': preview
                    }
                    
                    results.append(result)
                    logger.info(f"找到问题: {title[:50]}...")
                    
                except Exception as e:
                    logger.warning(f"解析搜索结果项失败: {e}")
                    continue
            
            logger.info(f"搜索完成，共找到 {len(results)} 个问题")
            return results
            
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return []
    
    def crawl_question_detail(self, question_url: str, max_retries: int = 3) -> Optional[Question]:
        """爬取问题详情"""
        # 检查是否为专栏文章，如果是则跳过
        if 'zhuanlan.zhihu.com' in question_url:
            logger.warning(f"跳过专栏文章: {question_url}")
            return None
            
        for attempt in range(max_retries):
            try:
                logger.info(f"开始爬取问题详情 (尝试 {attempt + 1}/{max_retries}): {question_url}")
                
                self.driver.get(question_url)
                self.random_delay()
                
                # 等待页面加载，增加超时时间
                try:
                    self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, self.config.SELECTORS["question_title"])))
                except TimeoutException:
                    logger.warning(f"页面加载超时，尝试刷新页面: {question_url}")
                    self.driver.refresh()
                    self.random_delay(2, 4)
                    self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, self.config.SELECTORS["question_title"])))
                
                # 提取问题基本信息
                question_id = self.extract_id_from_url(question_url)
                
                # 问题标题 - 使用更精确的选择器或遍历找到有内容的元素
                title = ""
                title_selectors = [
                    ".QuestionPage .QuestionHeader-title",
                    ".QuestionHeader h1",
                    self.config.SELECTORS["question_title"]
                ]
                
                for selector in title_selectors:
                    try:
                        title_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for element in title_elements:
                            text = element.text.strip()
                            if text:  # 找到第一个有内容的标题元素
                                title = text
                                break
                        if title:
                            break
                    except NoSuchElementException:
                        continue
                
                if not title:
                    raise ValueError("问题标题为空")
                
                # 问题详情
                content = ""
                try:
                    content_element = self.driver.find_element(By.CSS_SELECTOR, self.config.SELECTORS["question_detail"])
                    content = content_element.text.strip()
                except NoSuchElementException:
                    pass
                
                # 关注数和浏览量
                follow_count = 0
                view_count = 0
                try:
                    stats_elements = self.driver.find_elements(By.CSS_SELECTOR, self.config.SELECTORS["question_follow_count"])
                    if len(stats_elements) >= 2:
                        follow_text = stats_elements[0].text.strip()
                        view_text = stats_elements[1].text.strip()
                        
                        follow_count = self._parse_count(follow_text)
                        view_count = self._parse_count(view_text)
                except (NoSuchElementException, IndexError):
                    pass
                
                question = Question(
                    question_id=question_id,
                    title=title,
                    content=content,
                    follow_count=follow_count,
                    view_count=view_count,
                    url=question_url
                )
                
                logger.info(f"问题详情爬取成功: {title[:50]}...")
                return question
                
            except (TimeoutException, NoSuchElementException, ValueError) as e:
                logger.warning(f"爬取问题详情失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    self.random_delay(3, 6)  # 重试前等待更长时间
                    continue
                else:
                    logger.error(f"问题详情爬取最终失败: {question_url}")
                    return None
            except WebDriverException as e:
                logger.error(f"WebDriver错误，跳过此问题: {e}")
                return None
            except Exception as e:
                logger.error(f"未知错误，跳过此问题: {e}")
                return None
                
        return None
    
    def parse_date_from_text(self, text: str) -> Optional[datetime]:
        """尽量从文本中解析日期时间（支持“YYYY-MM-DD”、“YYYY/MM/DD”、“YYYY-MM-DD HH:mm”、“今天/昨天”等）"""
        try:
            if not text:
                return None
            t = text.strip()
            now = datetime.now()
            # 常见中文相对时间
            if '今天' in t:
                return now.replace(hour=0, minute=0, second=0, microsecond=0)
            if '昨天' in t:
                d = now - timedelta(days=1)
                return d.replace(hour=0, minute=0, second=0, microsecond=0)
            if '前天' in t:
                d = now - timedelta(days=2)
                return d.replace(hour=0, minute=0, second=0, microsecond=0)
            # 匹配 YYYY-MM-DD HH:mm 或 YYYY-MM-DD
            m = re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:\s+(\d{1,2}):(\d{1,2}))?', t)
            if m:
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                hh = int(m.group(4)) if m.group(4) else 0
                mm = int(m.group(5)) if m.group(5) else 0
                return datetime(y, mo, d, hh, mm)
            # 匹配 YYYY年MM月DD日
            m2 = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', t)
            if m2:
                y, mo, d = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
                return datetime(y, mo, d)
            return None
        except Exception:
            return None

    def is_within_date_range(self, dt: Optional[datetime], start_date: str, end_date: str) -> bool:
        """检查 dt 是否在 [start_date, end_date]（闭区间）内；若无法解析时间则返回 True 以避免漏抓"""
        try:
            if dt is None:
                return True
            start = datetime.strptime(start_date, self.config.DATE_FORMAT)
            end = datetime.strptime(end_date, self.config.DATE_FORMAT)
            return start <= dt <= end + timedelta(days=1) - timedelta(seconds=1)
        except Exception:
            return True

    def crawl_answers(self, question_url: str, question_id: str, start_date: str, end_date: str) -> Tuple[List[Answer], int]:
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
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, self.config.SELECTORS["answers_list"])))
            
            # 滚动加载所有答案
            self.scroll_to_load_more(15)
            
            # 提取答案
            answers: List[Answer] = []
            total_comments_saved = 0
            answer_elements = self.driver.find_elements(By.CSS_SELECTOR, self.config.SELECTORS["answers_list"])
            
            for element in answer_elements:
                try:
                    # 提取答案内容
                    content_element = element.find_element(By.CSS_SELECTOR, self.config.SELECTORS["answer_content"])
                    content = content_element.text.strip()
                    if not content:
                        continue
                    
                    # 作者
                    author = ""
                    author_url = ""
                    try:
                        author_element = element.find_element(By.CSS_SELECTOR, self.config.SELECTORS["answer_author"])
                        author = author_element.text.strip()
                        author_url = author_element.get_attribute("href") or ""
                    except NoSuchElementException:
                        pass
                    
                    # 点赞
                    vote_count = 0
                    try:
                        vote_element = element.find_element(By.CSS_SELECTOR, self.config.SELECTORS["answer_vote_count"])
                        vote_count = self._parse_count(vote_element.text.strip())
                    except NoSuchElementException:
                        pass
                    
                    # 时间
                    create_time_text = ""
                    try:
                        time_element = element.find_element(By.CSS_SELECTOR, self.config.SELECTORS["answer_time"])
                        create_time_text = time_element.text.strip()
                    except NoSuchElementException:
                        pass
                    dt = self.parse_date_from_text(create_time_text)
                    if not self.is_within_date_range(dt, start_date, end_date):
                        continue
                    
                    # 答案URL/ID
                    answer_url = ""
                    answer_id = ""
                    try:
                        # 优先寻找包含 /answer/ 的链接
                        url_candidates = element.find_elements(By.CSS_SELECTOR, 'a')
                        for a in url_candidates:
                            href = a.get_attribute('href') or ''
                            if '/answer/' in href:
                                answer_url = href
                                break
                        if answer_url:
                            answer_id = self.extract_id_from_url(answer_url)
                    except NoSuchElementException:
                        pass
                    if not answer_id:
                        answer_id = f"{question_id}_{len(answers)}"
                    
                    answer = Answer(
                        answer_id=answer_id,
                        question_id=question_id,
                        content=content,
                        author=author,
                        author_url=author_url,
                        create_time=create_time_text,
                        vote_count=vote_count,
                        url=answer_url
                    )
                    self.db.save_answer(answer)
                    answers.append(answer)
                    
                    # 抓取评论并保存
                    comments = self.crawl_comments(element, answer_id)
                    for c in comments:
                        # 时间过滤（如果可以解析）
                        c_dt = self.parse_date_from_text(c.create_time)
                        if self.is_within_date_range(c_dt, start_date, end_date):
                            self.db.save_comment(c)
                            total_comments_saved += 1
                    
                    logger.info(f"答案保存: 作者={author}, 点赞={vote_count}, 评论数={len(comments)}")
                except Exception as e:
                    logger.warning(f"解析答案失败: {e}")
                    continue
            
            logger.info(f"答案爬取完成，共保存 {len(answers)} 个答案，{total_comments_saved} 条评论")
            return answers, total_comments_saved
            
        except Exception as e:
            logger.error(f"爬取答案失败: {e}")
            return [], 0

    def crawl_comments(self, answer_element, answer_id: str) -> List[Comment]:
        """爬取答案的评论"""
        try:
            logger.info(f"开始爬取答案评论: {answer_id}")
            
            comments = []
            
            # 首先尝试点击答案展开按钮（如果答案被折叠）
            try:
                expand_answer_btn = answer_element.find_element(By.CSS_SELECTOR, "#QuestionAnswers-answers > div > div > div > div:nth-child(2) > div > div:nth-child(4) > div > div > div.RichContent.RichContent--unescapable > div.ContentItem-actions > button:nth-child(2)")
                if expand_answer_btn.is_displayed() and "展开" in expand_answer_btn.text:
                    logger.info(f"发现答案展开按钮，点击展开答案: {answer_id}")
                    self.driver.execute_script("arguments[0].click();", expand_answer_btn)
                    self.random_delay(1, 2)
            except NoSuchElementException:
                logger.debug(f"答案 {answer_id} 无需展开或未找到展开按钮")
            
            # 点击展开评论按钮
            try:
                comments_button = answer_element.find_element(By.CSS_SELECTOR, self.config.SELECTORS["comments_button"])
                if "评论" in comments_button.text:
                    self.driver.execute_script("arguments[0].click();", comments_button)
                    self.random_delay(1, 2)
            except NoSuchElementException:
                logger.info(f"答案 {answer_id} 没有评论按钮")
                return comments
            
            # 等待评论加载
            try:
                self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, self.config.SELECTORS["comments_list"])))
            except TimeoutException:
                logger.info(f"答案 {answer_id} 没有评论或评论加载超时")
                return comments
            
            # 检查是否有评论弹窗，如果有则处理弹窗中的懒加载
            try:
                # 尝试点击查看更多评论按钮，可能会打开弹窗
                view_more_comments_btn = self.driver.find_element(By.CSS_SELECTOR, "#root > div > main > div > div > div.Question-main > div.ListShortcut > div > div.Card.AnswerCard.css-0 > div > div > div > div:nth-child(9) > div > div > div.css-u76jt1 > div.css-wu78cf > div")
                if view_more_comments_btn.is_displayed():
                    logger.info(f"发现查看更多评论按钮，点击打开评论弹窗: {answer_id}")
                    self.driver.execute_script("arguments[0].click();", view_more_comments_btn)
                    self.random_delay(2, 3)
                    
                    # 在弹窗中进行懒加载
                    try:
                        modal_container = self.driver.find_element(By.CSS_SELECTOR, "body > div:nth-child(74) > div > div > div.css-1aq8hf9 > div")
                        if modal_container.is_displayed():
                            logger.info(f"评论弹窗已打开，开始懒加载评论: {answer_id}")
                            
                            # 在弹窗中滚动加载更多评论
                            last_height = self.driver.execute_script("return arguments[0].scrollHeight", modal_container)
                            scroll_attempts = 0
                            max_scroll_attempts = 20
                            
                            while scroll_attempts < max_scroll_attempts:
                                # 滚动到弹窗底部
                                self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", modal_container)
                                self.random_delay(2, 3)
                                
                                # 检查是否有新内容加载
                                new_height = self.driver.execute_script("return arguments[0].scrollHeight", modal_container)
                                if new_height == last_height:
                                    scroll_attempts += 1
                                    if scroll_attempts >= 3:  # 连续3次没有新内容则停止
                                        break
                                else:
                                    scroll_attempts = 0
                                    last_height = new_height
                                    logger.debug(f"弹窗中加载了更多评论，继续滚动: {answer_id}")
                            
                            logger.info(f"弹窗懒加载完成: {answer_id}")
                    except NoSuchElementException:
                        logger.debug(f"未找到评论弹窗容器: {answer_id}")
            except NoSuchElementException:
                logger.debug(f"未找到查看更多评论按钮: {answer_id}")
            
            # 加载更多评论（原有逻辑保留）
            try:
                load_more_btn = answer_element.find_element(By.CSS_SELECTOR, self.config.SELECTORS["load_more_comments"])
                while load_more_btn.is_displayed():
                    self.driver.execute_script("arguments[0].click();", load_more_btn)
                    self.random_delay(1, 2)
                    try:
                        load_more_btn = answer_element.find_element(By.CSS_SELECTOR, self.config.SELECTORS["load_more_comments"])
                    except NoSuchElementException:
                        break
            except NoSuchElementException:
                pass
            
            # 提取评论
            comment_elements = answer_element.find_elements(By.CSS_SELECTOR, self.config.SELECTORS["comments_list"])
            
            for i, element in enumerate(comment_elements):
                try:
                    # 评论内容
                    content_element = element.find_element(By.CSS_SELECTOR, self.config.SELECTORS["comment_content"])
                    content = content_element.text.strip()
                    
                    if not content:
                        continue
                    
                    # 评论作者
                    author = ""
                    author_url = ""
                    try:
                        author_element = element.find_element(By.CSS_SELECTOR, self.config.SELECTORS["comment_author"])
                        author = author_element.text.strip()
                        author_url = author_element.get_attribute("href") or ""
                    except NoSuchElementException:
                        pass
                    
                    # 评论时间
                    create_time = ""
                    try:
                        time_element = element.find_element(By.CSS_SELECTOR, self.config.SELECTORS["comment_time"])
                        create_time = time_element.text.strip()
                    except NoSuchElementException:
                        pass
                    
                    # 点赞数
                    vote_count = 0
                    try:
                        vote_element = element.find_element(By.CSS_SELECTOR, self.config.SELECTORS["comment_vote"])
                        vote_count = self._parse_count(vote_element.text.strip())
                    except NoSuchElementException:
                        pass
                    
                    comment = Comment(
                        comment_id=f"{answer_id}_comment_{i}",
                        answer_id=answer_id,
                        content=content,
                        author=author,
                        author_url=author_url,
                        create_time=create_time,
                        vote_count=vote_count
                    )
                    
                    comments.append(comment)
                    
                except Exception as e:
                    logger.warning(f"解析评论失败: {e}")
                    continue
            
            logger.info(f"评论爬取完成，共找到 {len(comments)} 条评论")
            return comments
            
        except Exception as e:
            logger.error(f"爬取评论失败: {e}")
            return []
    
    def _parse_count(self, count_text: str) -> int:
        """解析数量文本（如 1.2万、3千等）"""
        try:
            count_text = count_text.strip()
            if not count_text or count_text == '--':
                return 0
            
            # 移除非数字中和文字以外的字符
            count_text = re.sub(r'[^\d\.\u4e00-\u9fff]', '', count_text)
            
            if '万' in count_text:
                number = float(count_text.replace('万', ''))
                return int(number * 10000)
            elif '千' in count_text:
                number = float(count_text.replace('千', ''))
                return int(number * 1000)
            elif '百' in count_text:
                number = float(count_text.replace('百', ''))
                return int(number * 100)
            else:
                return int(float(count_text))
        except (ValueError, TypeError):
            return 0
    
    def _generate_cache_filename(self, keywords: List[str], start_date: str = None, end_date: str = None) -> str:
        """生成缓存文件名"""
        keywords_str = "_".join(sorted(keywords)).replace(" ", "")
        date_str = f"{start_date or 'all'}_{end_date or 'all'}"
        return f"search_results_{keywords_str}_{date_str}.json"
    
    def save_search_results_to_file(self, search_results: List[Dict], keywords: List[str], start_date: str = None, end_date: str = None) -> str:
        """保存搜索结果到文件"""
        try:
            filename = self._generate_cache_filename(keywords, start_date, end_date)
            filepath = self.cache_dir / filename
            
            cache_data = {
                "keywords": keywords,
                "start_date": start_date,
                "end_date": end_date,
                "timestamp": datetime.now().isoformat(),
                "total_count": len(search_results),
                "results": search_results
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"搜索结果已保存到文件: {filepath} (共 {len(search_results)} 条)")
            return str(filepath)
        except Exception as e:
            logger.error(f"保存搜索结果到文件失败: {e}")
            return None
    
    def load_search_results_from_file(self, keywords: List[str], start_date: str = None, end_date: str = None) -> Optional[List[Dict]]:
        """从文件加载搜索结果"""
        try:
            filename = self._generate_cache_filename(keywords, start_date, end_date)
            filepath = self.cache_dir / filename
            
            if not filepath.exists():
                logger.info(f"缓存文件不存在: {filepath}")
                return None
            
            with open(filepath, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            results = cache_data.get('results', [])
            logger.info(f"从缓存文件加载搜索结果: {filepath} (共 {len(results)} 条)")
            logger.info(f"缓存创建时间: {cache_data.get('timestamp', 'unknown')}")
            
            return results
        except Exception as e:
            logger.error(f"从文件加载搜索结果失败: {e}")
            return None
    
    def check_cache_exists(self, keywords: List[str], start_date: str = None, end_date: str = None) -> bool:
        """检查缓存文件是否存在"""
        filename = self._generate_cache_filename(keywords, start_date, end_date)
        filepath = self.cache_dir / filename
        return filepath.exists()
    
    def crawl_by_keyword(self, keyword: str, start_date: str = None, end_date: str = None) -> Dict:
        """根据关键字进行完整爬取"""
        start_date = start_date or self.config.DEFAULT_START_DATE
        end_date = end_date or self.config.DEFAULT_END_DATE
        
        logger.info(f"开始完整爬取 - 关键字: {keyword}")
        
        # 检查登录状态
        if self.config.ENABLE_COOKIE_LOGIN:
            if not self.check_login_status():
                logger.warning("未检测到登录状态，建议先登录以获取更好的搜索结果")
                if not self.headless:
                    user_choice = input("是否现在登录？(y/n): ").lower().strip()
                    if user_choice == 'y':
                        if not self.manual_login_prompt():
                            logger.warning("登录失败，继续使用未登录状态")
                    else:
                        logger.info("跳过登录，继续爬取")
                else:
                    logger.info("无头模式下跳过登录提示")
        
        # 保存搜索记录
        search_record_id = self.db.save_search_record(keyword, start_date, end_date)
        
        stats = {
            'keyword': keyword,
            'total_questions': 0,
            'total_answers': 0,
            'total_comments': 0,
            'failed_questions': 0,
            'start_time': datetime.now().isoformat()
        }
        
        try:
            # 1. 搜索问题
            search_results = self.search_questions(keyword, start_date, end_date)
            stats['total_questions'] = len(search_results)
            
            if not search_results:
                logger.warning("未找到任何搜索结果")
                return stats
            
            # 2. 遍历每个问题
            for i, result in enumerate(search_results, 1):
                try:
                    logger.info(f"处理问题 {i}/{len(search_results)}: {result['title'][:50]}...")
                    
                    # 爬取问题详情
                    question = self.crawl_question_detail(result['url'])
                    if question:
                        self.db.save_question(question)
                        
                        # 爬取答案及评论
                        answers, comments_saved = self.crawl_answers(result['url'], question.question_id, start_date, end_date)
                        stats['total_answers'] += len(answers)
                        stats['total_comments'] += comments_saved
                        
                        logger.info(f"问题处理完成，答案数: {len(answers)}，评论保存: {comments_saved}")
                    else:
                        stats['failed_questions'] += 1
                        logger.warning(f"问题详情爬取失败: {result['title']}")
                    
                    # 随机延时，避免过于频繁的请求
                    self.random_delay(2, 5)
                    
                except Exception as e:
                    stats['failed_questions'] += 1
                    logger.error(f"处理问题失败: {e}")
                    continue
            
            stats['end_time'] = datetime.now().isoformat()
            
            # 更新搜索记录
            self.db.update_search_stats(
                search_record_id,
                stats['total_questions'],
                stats['total_answers'],
                stats['total_comments'],
                'completed'
            )
            
            logger.info(f"爬取完成 - 问题: {stats['total_questions']}, 答案: {stats['total_answers']}, 评论: {stats['total_comments']}")
            
        except Exception as e:
            logger.error(f"爬取过程出错: {e}")
            self.db.update_search_stats(search_record_id, 0, 0, 0, 'failed')
        
        return stats
    
    def crawl_by_multiple_keywords(self, keywords: List[str], start_date: str = None, end_date: str = None, resume_task_id: int = None, use_cache: bool = True) -> Dict:
        """根据多个关键字进行批量搜索和去重后爬取，支持任务中断继续执行"""
        start_date = start_date or self.config.DEFAULT_START_DATE
        end_date = end_date or self.config.DEFAULT_END_DATE
        
        # 检查是否有未完成的任务需要继续
        if resume_task_id:
            return self._resume_task(resume_task_id)
        
        logger.info(f"开始批量关键字爬取 - 关键字数量: {len(keywords)}")
        
        # 检查登录状态
        if self.config.ENABLE_COOKIE_LOGIN:
            if not self.check_login_status():
                logger.warning("未检测到登录状态，建议先登录以获取更好的搜索结果")
                if not self.headless:
                    user_choice = input("是否现在登录？(y/n): ").lower().strip()
                    if user_choice == 'y':
                        if not self.manual_login_prompt():
                            logger.warning("登录失败，继续使用未登录状态")
                    else:
                        logger.info("跳过登录，继续爬取")
                else:
                    logger.info("无头模式下跳过登录提示")
        
        # 创建新任务
        task_id = self.db.create_task('batch_keywords', keywords, start_date, end_date)
        logger.info(f"创建任务 ID: {task_id}")
        
        stats = {
            'task_id': task_id,
            'keywords': keywords,
            'total_questions': 0,
            'total_answers': 0,
            'total_comments': 0,
            'failed_questions': 0,
            'unique_questions': 0,
            'start_time': datetime.now().isoformat()
        }
        
        try:
            # 第一阶段：检查缓存或批量搜索所有关键字
            logger.info("第一阶段：检查缓存或批量搜索所有关键字")
            self.db.update_task_stage(task_id, 'search')
            
            # 检查是否存在缓存文件（仅在启用缓存时）
            cached_results = None
            if use_cache:
                cached_results = self.load_search_results_from_file(keywords, start_date, end_date)
            
            if cached_results:
                logger.info("发现缓存文件，从缓存加载搜索结果")
                all_search_results = cached_results
                
                # 为缓存结果创建搜索记录
                for keyword in keywords:
                    search_record_id = self.db.save_search_record(keyword, start_date, end_date)
                    keyword_results = [r for r in cached_results if r.get('source_keyword') == keyword]
                    self.db.update_search_stats(search_record_id, len(keyword_results), 0, 0, 'search_completed')
                    
                    # 为结果添加搜索记录ID
                    for result in keyword_results:
                        result['search_record_id'] = search_record_id
                        
            else:
                logger.info("未发现缓存文件，开始批量搜索")
                all_search_results = []
                
                for i, keyword in enumerate(keywords, 1):
                    logger.info(f"搜索关键字 {i}/{len(keywords)}: {keyword}")
                    search_record_id = self.db.save_search_record(keyword, start_date, end_date)
                    
                    try:
                        results = self.search_questions(keyword, start_date, end_date)
                        logger.info(f"关键字 '{keyword}' 找到 {len(results)} 个问题")
                        
                        # 为每个结果添加来源关键字信息
                        for result in results:
                            result['source_keyword'] = keyword
                            result['search_record_id'] = search_record_id
                        
                        all_search_results.extend(results)
                        
                        # 更新搜索记录
                        self.db.update_search_stats(search_record_id, len(results), 0, 0, 'search_completed')
                        
                    except Exception as e:
                        logger.error(f"搜索关键字 '{keyword}' 失败: {e}")
                        self.db.update_search_stats(search_record_id, 0, 0, 0, 'failed')
                        continue
                    
                    # 搜索间隔延时
                    self.random_delay(1, 3)
                
                # 保存搜索结果到缓存文件（仅在启用缓存时）
                if use_cache and all_search_results:
                    cache_file = self.save_search_results_to_file(all_search_results, keywords, start_date, end_date)
                    if cache_file:
                        logger.info(f"搜索结果已保存到缓存文件: {cache_file}")
            
            logger.info(f"搜索阶段完成，总共找到 {len(all_search_results)} 个问题（包含重复）")
            
            # 第二阶段：去重并保存问题URL
            logger.info("第二阶段：问题去重并保存URL")
            self.db.update_task_stage(task_id, 'deduplication')
            
            unique_questions = {}
            
            for result in all_search_results:
                question_id = self.extract_id_from_url(result['url'])
                if question_id not in unique_questions:
                    unique_questions[question_id] = result
                else:
                    # 如果已存在，合并来源关键字信息
                    existing = unique_questions[question_id]
                    if 'source_keywords' not in existing:
                        existing['source_keywords'] = [existing['source_keyword']]
                    if result['source_keyword'] not in existing['source_keywords']:
                        existing['source_keywords'].append(result['source_keyword'])
            
            unique_results = list(unique_questions.values())
            stats['total_questions'] = len(all_search_results)
            stats['unique_questions'] = len(unique_results)
            
            logger.info(f"去重完成，唯一问题数: {len(unique_results)}")
            
            if not unique_results:
                logger.warning("去重后未找到任何问题")
                self.db.complete_task(task_id, 0, 0, 0)
                return stats
            
            # 保存问题URL到数据库
            question_urls = []
            for result in unique_results:
                question_id = self.extract_id_from_url(result['url'])
                question_urls.append({
                    'question_id': question_id,
                    'url': result['url'],
                    'title': result['title']
                })
            
            self.db.save_question_urls(task_id, question_urls)
            logger.info(f"已保存 {len(question_urls)} 个问题URL到数据库")
            
            # 第三阶段：批量爬取问题详情
            logger.info("第三阶段：批量爬取问题详情")
            self.db.update_task_stage(task_id, 'question_details')
            
            processed_questions = []
            
            for i, result in enumerate(unique_results, 1):
                try:
                    question_id = self.extract_id_from_url(result['url'])
                    source_info = result.get('source_keywords', [result.get('source_keyword', '')])
                    logger.info(f"处理问题详情 {i}/{len(unique_results)}: {result['title'][:50]}... (来源: {', '.join(source_info)})")
                    
                    # 爬取问题详情
                    question = self.crawl_question_detail(result['url'])
                    if question:
                        self.db.save_question(question)
                        processed_questions.append(question_id)
                        
                        # 标记问题为已处理
                        self.db.mark_question_processed(task_id, question_id)
                        
                        logger.info(f"问题详情保存完成: {question.title[:50]}...")
                    else:
                        stats['failed_questions'] += 1
                        logger.warning(f"问题详情爬取失败: {result['title']}")
                    
                    # 更新任务进度
                    self.db.update_task_stage(task_id, 'question_details', processed_questions)
                    
                    # 随机延时
                    self.random_delay(1, 3)
                    
                except Exception as e:
                    stats['failed_questions'] += 1
                    logger.error(f"处理问题详情失败: {e}")
                    continue
            
            logger.info(f"问题详情爬取完成，成功处理 {len(processed_questions)} 个问题")
            
            # 第四阶段：批量爬取答案和评论
            logger.info("第四阶段：批量爬取答案和评论")
            self.db.update_task_stage(task_id, 'answers_comments')
            
            processed_answers = []
            
            for i, result in enumerate(unique_results, 1):
                try:
                    question_id = self.extract_id_from_url(result['url'])
                    logger.info(f"处理答案和评论 {i}/{len(unique_results)}: {result['title'][:50]}...")
                    
                    # 爬取答案及评论
                    answers, comments_saved = self.crawl_answers(result['url'], question_id, start_date, end_date)
                    stats['total_answers'] += len(answers)
                    stats['total_comments'] += comments_saved
                    
                    for answer in answers:
                        processed_answers.append(answer.answer_id)
                    
                    # 更新任务进度
                    self.db.update_task_stage(task_id, 'answers_comments', processed_questions, processed_answers)
                    
                    logger.info(f"答案和评论处理完成，答案数: {len(answers)}，评论数: {comments_saved}")
                    
                    # 随机延时，避免过于频繁的请求
                    self.random_delay(2, 5)
                    
                except Exception as e:
                    stats['failed_questions'] += 1
                    logger.error(f"处理答案和评论失败: {e}")
                    continue
            
            stats['end_time'] = datetime.now().isoformat()
            
            # 完成任务
            self.db.complete_task(task_id, stats['unique_questions'], stats['total_answers'], stats['total_comments'])
            
            logger.info(f"批量爬取完成 - 任务ID: {task_id}, 搜索到: {stats['total_questions']}, 去重后: {stats['unique_questions']}, 答案: {stats['total_answers']}, 评论: {stats['total_comments']}")
            
        except Exception as e:
            logger.error(f"批量爬取过程出错: {e}")
            # 任务失败时不更新为完成状态，保持running状态以便后续恢复
        
        return stats
    
    def _resume_task(self, task_id: int) -> Dict:
        """恢复未完成的任务"""
        logger.info(f"恢复任务 ID: {task_id}")
        
        # 获取任务信息
        incomplete_tasks = self.db.get_incomplete_tasks()
        task_info = None
        for task in incomplete_tasks:
            if task['id'] == task_id:
                task_info = task
                break
        
        if not task_info:
            logger.error(f"未找到任务 ID: {task_id}")
            return {'error': f'Task {task_id} not found'}
        
        logger.info(f"恢复任务: {task_info['task_type']}, 当前阶段: {task_info['current_stage']}")
        
        stats = {
            'task_id': task_id,
            'keywords': task_info['keywords'],
            'total_questions': task_info['total_questions'],
            'total_answers': task_info['total_answers'],
            'total_comments': task_info['total_comments'],
            'failed_questions': 0,
            'resume_time': datetime.now().isoformat()
        }
        
        try:
            current_stage = task_info['current_stage']
            
            if current_stage in ['search', 'deduplication']:
                logger.info("任务在搜索或去重阶段中断，重新开始完整流程")
                return self.crawl_by_multiple_keywords(
                    task_info['keywords'], 
                    task_info['start_date'], 
                    task_info['end_date']
                )
            
            elif current_stage == 'question_details':
                logger.info("从问题详情爬取阶段恢复")
                # 获取未处理的问题
                unprocessed_questions = self.db.get_unprocessed_questions(task_id)
                logger.info(f"发现 {len(unprocessed_questions)} 个未处理的问题")
                
                for i, question_info in enumerate(unprocessed_questions, 1):
                    try:
                        logger.info(f"处理问题详情 {i}/{len(unprocessed_questions)}: {question_info['title'][:50]}...")
                        
                        question = self.crawl_question_detail(question_info['url'])
                        if question:
                            self.db.save_question(question)
                            self.db.mark_question_processed(task_id, question_info['question_id'])
                            logger.info(f"问题详情保存完成")
                        else:
                            stats['failed_questions'] += 1
                            logger.warning(f"问题详情爬取失败")
                        
                        self.random_delay(1, 3)
                        
                    except Exception as e:
                        stats['failed_questions'] += 1
                        logger.error(f"处理问题详情失败: {e}")
                        continue
                
                # 继续到答案和评论阶段
                self.db.update_task_stage(task_id, 'answers_comments')
                current_stage = 'answers_comments'
            
            if current_stage == 'answers_comments':
                logger.info("处理答案和评论阶段")
                # 获取所有问题进行答案爬取
                all_questions = self.db.get_all_task_questions(task_id)
                
                for i, question_info in enumerate(all_questions, 1):
                    try:
                        logger.info(f"处理答案和评论 {i}/{len(all_questions)}: {question_info['title'][:50]}...")
                        
                        answers, comments_saved = self.crawl_answers(
                            question_info['url'], 
                            question_info['question_id'], 
                            task_info['start_date'], 
                            task_info['end_date']
                        )
                        
                        stats['total_answers'] += len(answers)
                        stats['total_comments'] += comments_saved
                        
                        logger.info(f"答案和评论处理完成，答案数: {len(answers)}，评论数: {comments_saved}")
                        
                        self.random_delay(2, 5)
                        
                    except Exception as e:
                        stats['failed_questions'] += 1
                        logger.error(f"处理答案和评论失败: {e}")
                        continue
                
                # 完成任务
                self.db.complete_task(task_id, len(all_questions), stats['total_answers'], stats['total_comments'])
                logger.info(f"任务恢复完成 - 任务ID: {task_id}")
            
        except Exception as e:
            logger.error(f"任务恢复过程出错: {e}")
        
        return stats
    
    def list_incomplete_tasks(self) -> List[Dict]:
        """列出所有未完成的任务"""
        return self.db.get_incomplete_tasks()
    
    def resume_task(self, task_id: int) -> Dict:
        """恢复指定的任务（公共接口）"""
        return self._resume_task(task_id)
    
    def close(self):
        """关闭浏览器"""
        if self.driver:
            self.driver.quit()
            logger.info("浏览器已关闭")