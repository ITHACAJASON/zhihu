import time
import random
import logging
import json
import re
from typing import List, Dict, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from database import DatabaseManager
from config import get_crawler_config

class ZhihuCrawler:
    """知乎爬虫类"""
    
    def __init__(self, db_manager: DatabaseManager, headless: bool = False):
        self.db_manager = db_manager
        self.driver = None
        self.wait = None
        self.headless = headless
        self.config = get_crawler_config()
        self.answers_per_cleanup = self.config['answers_per_cleanup']
        self.scroll_delay = self.config['scroll_delay']
        self.current_answer_count = 0
        
    def setup_driver(self):
        """初始化Chrome浏览器驱动"""
        try:
            chrome_options = Options()
            if self.headless:
                chrome_options.add_argument('--headless')
            
            # 反反爬设置
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # 设置用户代理
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # 尝试自动下载ChromeDriver，失败则使用系统PATH
            try:
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            except Exception as driver_error:
                logging.warning(f"自动下载ChromeDriver失败: {driver_error}")
                logging.info("尝试使用系统PATH中的chromedriver")
                # 尝试使用系统PATH中的chromedriver
                self.driver = webdriver.Chrome(options=chrome_options)
            
            # 执行反检测脚本
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.wait = WebDriverWait(self.driver, 10)
            logging.info("Chrome浏览器驱动初始化成功")
            
        except Exception as e:
            logging.error(f"浏览器驱动初始化失败: {e}")
            raise
    
    def wait_for_login(self):
        """等待用户手动登录"""
        print("\n=== 请在浏览器中登录知乎账号 ===")
        print("1. 浏览器将自动打开知乎登录页面")
        print("2. 请手动完成登录操作")
        print("3. 登录成功后，在控制台输入 'done' 继续")
        print("4. 如需退出，输入 'quit'")
        
        # 打开知乎登录页面
        self.driver.get('https://www.zhihu.com/signin')
        
        while True:
            user_input = input("\n请输入 'done' 继续或 'quit' 退出: ").strip().lower()
            if user_input == 'done':
                # 检查是否已登录
                if self.check_login_status():
                    print("登录验证成功！")
                    break
                else:
                    print("未检测到登录状态，请确保已完成登录")
            elif user_input == 'quit':
                print("用户取消操作")
                return False
            else:
                print("无效输入，请输入 'done' 或 'quit'")
        
        return True
    
    def check_login_status(self) -> bool:
        """检查登录状态"""
        try:
            # 检查页面是否包含用户信息
            self.driver.get('https://www.zhihu.com')
            time.sleep(2)
            
            # 查找用户头像或用户菜单
            user_elements = self.driver.find_elements(By.CSS_SELECTOR, '.Avatar, .Menu-item, [data-za-detail-view-element_name="Profile"]')
            return len(user_elements) > 0
            
        except Exception as e:
            logging.error(f"检查登录状态失败: {e}")
            return False
    
    def crawl_question_answers(self, question_url: str, target_count: int) -> int:
        """爬取问题的所有回答"""
        try:
            logging.info(f"开始爬取问题: {question_url}，目标回答数: {target_count}")
            
            # 访问问题页面
            self.driver.get(question_url)
            time.sleep(random.uniform(0.67, 1.33))
            
            # 点击"查看全部回答"按钮
            self.click_view_all_answers()
            
            crawled_answer_ids = []  # 只保存ID用于去重判断
            pending_answers = []     # 待批量保存的回答数据
            self.current_answer_count = 0
            no_new_data_count = 0  # 连续无新数据的次数
            batch_size = 50          # 批量保存大小
            
            while len(crawled_answer_ids) < target_count:
                # 记录滚动前的回答数量
                previous_count = len(crawled_answer_ids)
                
                # 滚动加载更多回答
                self.scroll_to_load_more()
                
                # 获取当前页面的回答
                new_answers = self.extract_answers_from_page()
                
                # 过滤重复回答并记录新增数据
                new_answer_ids = []
                for answer in new_answers:
                    if answer['answer_id'] not in crawled_answer_ids:
                        crawled_answer_ids.append(answer['answer_id'])
                        new_answer_ids.append(answer['answer_id'])
                        pending_answers.append(answer)
                
                # 只打印新增的回答ID
                if new_answer_ids:
                    logging.info(f"新增回答ID: {new_answer_ids}")
                
                # 批量保存到数据库
                if len(pending_answers) >= batch_size or len(crawled_answer_ids) >= target_count:
                    saved_count = self.db_manager.save_answers_batch(question_url, pending_answers)
                    self.current_answer_count += saved_count
                    pending_answers.clear()  # 清空待保存列表
                    
                    # 执行优化的DOM清理
                    self.cleanup_dom_optimized()
                    logging.info(f"已批量保存 {saved_count} 个回答，当前总计 {self.current_answer_count} 个")
                
                # 检查是否有新数据
                if len(crawled_answer_ids) == previous_count:
                    no_new_data_count += 1
                    logging.info(f"本次滚动无新数据，连续无新数据次数: {no_new_data_count}")
                    
                    # 如果连续3次无新数据，触发重试机制
                    if no_new_data_count >= 3:
                        logging.info("连续3次无新数据，触发滚动重试机制")
                        self.scroll_retry_mechanism()
                        no_new_data_count = 0  # 重置计数器
                else:
                    no_new_data_count = 0  # 有新数据时重置计数器
                
                logging.info(f"当前已采集 {len(crawled_answer_ids)} 个回答")
                
                # 检查是否还有更多回答可加载
                if not self.has_more_answers():
                    logging.info("已到达页面底部，无更多回答")
                    break
                
                # 滚动间隔延时
                time.sleep(random.uniform(*self.scroll_delay))
            
            # 保存剩余的回答数据
            if pending_answers:
                saved_count = self.db_manager.save_answers_batch(question_url, pending_answers)
                self.current_answer_count += saved_count
                logging.info(f"保存剩余 {saved_count} 个回答")
            
            # 更新数据库中的爬取状态
            status = "completed" if len(crawled_answer_ids) >= target_count else "partial"
            self.db_manager.update_crawl_status(question_url, status, len(crawled_answer_ids))
            
            logging.info(f"问题爬取完成，共采集 {len(crawled_answer_ids)} 个回答")
            return len(crawled_answer_ids)
            
        except Exception as e:
            logging.error(f"爬取问题回答失败: {e}")
            return 0
    
    def click_view_all_answers(self):
        """点击查看全部回答按钮"""
        try:
            # 查找"查看全部回答"按钮的多种可能选择器
            view_all_selectors = [
                '.Card.ViewAll a[data-za-detail-view-element_name="ViewAll"]',
                '.ViewAll-QuestionMainAction',
                '.Card.ViewAll a',
                'a[data-za-detail-view-element_name="ViewAll"]',
                'button[data-za-detail-view-element_name="QuestionAnswers-more"]',
                '.QuestionAnswers-more button'
            ]
            
            for selector in view_all_selectors:
                try:
                    # 等待按钮出现并可点击
                    view_all_btn = self.wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    
                    # 滚动到按钮位置
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", view_all_btn)
                    
                    # 点击按钮
                    self.driver.execute_script("arguments[0].click();", view_all_btn)
                    logging.info(f"成功点击查看全部回答按钮: {selector}")
                    return True
                    
                except TimeoutException:
                    continue
                except Exception as e:
                    logging.warning(f"点击按钮失败 {selector}: {e}")
                    continue
            
            # 如果没有找到按钮，尝试通过文本查找（仅查找button元素）
            try:
                # 只查找button标签，避免点击a标签链接
                elements = self.driver.find_elements(By.TAG_NAME, "button")
                for element in elements:
                    element_text = element.text.strip()
                    if "查看全部" in element_text or "个回答" in element_text:
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                        self.driver.execute_script("arguments[0].click();", element)
                        logging.info(f"通过文本找到并点击按钮元素: {element_text}")
                        return True
            except Exception as e:
                logging.warning(f"通过文本查找按钮失败: {e}")
            
            logging.info("未找到查看全部回答按钮，可能已经显示所有回答")
            return False
            
        except Exception as e:
            logging.warning(f"点击查看全部回答按钮失败: {e}")
            return False
    
    def scroll_to_load_more(self):
        """直接跳转到页面底部加载更多回答"""
        try:
            # 直接跳转到页面底部
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            
            logging.info("直接跳转到页面底部")
            
            # 等待页面加载
            time.sleep(0.5)
            
            # 尝试查找并点击"加载更多"按钮（如果存在）
            load_more_selectors = [
                '.QuestionAnswers-more button',  # 问题回答区域的加载更多按钮
                'button[class*="QuestionAnswers"][class*="more"]',  # 包含QuestionAnswers和more的按钮
                '.List-more button',  # 列表区域的加载更多按钮
                '.QuestionAnswers-actions button',  # 问题回答操作区域的按钮
                'button[class*="LoadMore"]'  # 包含LoadMore的按钮
            ]
            
            for selector in load_more_selectors:
                try:
                    load_more_btn = WebDriverWait(self.driver, 2).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    # 确保按钮在视口内且不是搜索按钮
                    if ('SearchBar' not in load_more_btn.get_attribute('class') and 
                        'Search' not in (load_more_btn.get_attribute('aria-label') or '')):
                        self.driver.execute_script("arguments[0].click();", load_more_btn)
                        logging.info(f"成功点击加载更多按钮: {selector}")
                        break
                except TimeoutException:
                    continue
                
        except Exception as e:
            logging.warning(f"滚动加载失败: {e}")
    
    def extract_answers_from_page(self) -> List[Dict]:
        """从当前页面提取回答数据"""
        answers = []
        try:
            # 查找所有回答元素
            answer_elements = self.driver.find_elements(By.CSS_SELECTOR, '.List-item')
            logging.info(f"找到 {len(answer_elements)} 个List-item元素")
            
            for i, element in enumerate(answer_elements):
                try:
                    answer_data = self.extract_single_answer(element, i)
                    if answer_data:
                        answers.append(answer_data)
                    else:
                        logging.warning(f"第 {i+1} 个元素未能提取到有效数据")
                except Exception as e:
                    logging.warning(f"提取第 {i+1} 个回答失败: {e}")
                    continue
                    
        except Exception as e:
            logging.error(f"提取页面回答失败: {e}")
            
        logging.info(f"本次提取到 {len(answers)} 个有效回答")
        return answers
    
    def extract_single_answer(self, element, index: int = 0) -> Optional[Dict]:
        """提取单个回答的数据"""
        try:
            # 获取回答ID - 尝试多种方式
            answer_id = None
            
            # 方式1: 直接从元素获取
            answer_id = element.get_attribute('data-id') or element.get_attribute('id')
            
            # 方式2: 从子元素的href属性获取（不触发点击）
            if not answer_id:
                try:
                    # 查找包含answer链接的元素，但只获取属性，不进行任何操作
                    answer_links = element.find_elements(By.CSS_SELECTOR, 'a[href*="/answer/"]')
                    for link in answer_links:
                        href = link.get_attribute('href')
                        if href and '/answer/' in href:
                            answer_id = href.split('/answer/')[-1].split('?')[0]
                            break
                except:
                    pass
            
            # 方式3: 从data-za-detail-view-id获取
            if not answer_id:
                try:
                    answer_id = element.get_attribute('data-za-detail-view-id')
                except:
                    pass
            
            # 方式4: 使用索引作为临时ID
            if not answer_id:
                answer_id = f"temp_answer_{index}_{int(time.time())}"
                logging.warning(f"无法获取回答ID，使用临时ID: {answer_id}")
            
            logging.debug(f"获取到回答ID: {answer_id}")
            
            # 获取作者信息
            author = "匿名用户"
            try:
                author_selectors = ['.AuthorInfo-name', '.UserLink-link', '.AuthorInfo .Popover div']
                for selector in author_selectors:
                    try:
                        author_element = element.find_element(By.CSS_SELECTOR, selector)
                        if author_element and author_element.text.strip():
                            author = author_element.text.strip()
                            break
                    except:
                        continue
            except Exception as e:
                logging.debug(f"获取作者信息失败: {e}")
            
            # 获取回答内容 - 使用正确的选择器
            content = ""
            try:
                # 根据用户提供的信息，回答正文在 .RichContent-inner 中
                content_element = element.find_element(By.CSS_SELECTOR, '.RichContent-inner')
                if content_element and content_element.text.strip():
                    content = content_element.text.strip()
                    logging.debug(f"成功获取回答内容，长度: {len(content)}")
                else:
                    # 备选选择器
                    backup_selectors = ['.CopyrightRichText-richText', '.RichText', '.AnswerItem-content']
                    for selector in backup_selectors:
                        try:
                            content_element = element.find_element(By.CSS_SELECTOR, selector)
                            if content_element and content_element.text.strip():
                                content = content_element.text.strip()
                                logging.debug(f"使用备选选择器 {selector} 获取内容，长度: {len(content)}")
                                break
                        except:
                            continue
            except Exception as e:
                logging.debug(f"获取回答内容失败: {e}")
            
            # 获取点赞数 - 使用正确的选择器
            vote_count = 0
            try:
                # 根据用户提供的信息，在 .ContentItem-actions 中查找赞同按钮
                actions_element = element.find_element(By.CSS_SELECTOR, '.ContentItem-actions')
                if actions_element:
                    # 查找赞同按钮，按钮的 aria-label 包含赞同数量
                    vote_button = actions_element.find_element(By.CSS_SELECTOR, 'button.VoteButton[aria-label*="赞同"]')
                    if vote_button:
                        aria_label = vote_button.get_attribute('aria-label')
                        if aria_label:
                            # 从 aria-label 中提取数字，格式如 "赞同 131 "
                            import re
                            match = re.search(r'赞同\s+(\d+)', aria_label)
                            if match:
                                vote_count = int(match.group(1))
                                logging.debug(f"从 aria-label 获取点赞数: {vote_count}")
                            else:
                                # 尝试从按钮文本中获取
                                button_text = vote_button.text.strip()
                                vote_count = self.parse_vote_count(button_text)
                                logging.debug(f"从按钮文本获取点赞数: {vote_count}")
                        else:
                            # 备选方案：从按钮文本获取
                            button_text = vote_button.text.strip()
                            vote_count = self.parse_vote_count(button_text)
                            logging.debug(f"从按钮文本获取点赞数: {vote_count}")
                    else:
                        logging.debug("未找到赞同按钮")
                else:
                    # 备选选择器
                    backup_selectors = ['.VoteButton--up .Button-label', '.VoteButton .Voters', '.Button--plain']
                    for selector in backup_selectors:
                        try:
                            vote_element = element.find_element(By.CSS_SELECTOR, selector)
                            if vote_element and vote_element.text.strip():
                                vote_text = vote_element.text.strip()
                                vote_count = self.parse_vote_count(vote_text)
                                logging.debug(f"使用备选选择器 {selector} 获取点赞数: {vote_count}")
                                break
                        except:
                            continue
            except Exception as e:
                logging.debug(f"获取点赞数失败: {e}")
            
            # 获取创建时间
            created_time = None
            try:
                time_selectors = ['.ContentItem-time', '.AnswerItem-time', 'time']
                for selector in time_selectors:
                    try:
                        time_element = element.find_element(By.CSS_SELECTOR, selector)
                        if time_element:
                            created_time = time_element.get_attribute('datetime') or time_element.text.strip()
                            if created_time:
                                break
                    except:
                        continue
            except Exception as e:
                logging.debug(f"获取创建时间失败: {e}")
            
            # 验证数据完整性
            if not content and not author:
                logging.warning(f"回答 {answer_id} 缺少关键数据，跳过")
                return None
            
            return {
                'answer_id': answer_id,
                'author': author,
                'content': content[:5000],  # 限制内容长度
                'vote_count': vote_count,
                'created_time': created_time
            }
            
        except NoSuchElementException:
            return None
        except Exception as e:
            logging.warning(f"解析回答数据失败: {e}")
            return None
    
    def parse_vote_count(self, vote_text: str) -> int:
        """解析点赞数文本"""
        try:
            if not vote_text or vote_text == "赞同":
                return 0
            
            # 处理"1.2万"这种格式
            if "万" in vote_text:
                number = float(re.findall(r'[\d.]+', vote_text)[0])
                return int(number * 10000)
            elif "千" in vote_text:
                number = float(re.findall(r'[\d.]+', vote_text)[0])
                return int(number * 1000)
            else:
                # 提取数字
                numbers = re.findall(r'\d+', vote_text)
                return int(numbers[0]) if numbers else 0
                
        except Exception:
            return 0
    
    def cleanup_dom(self):
        """清理DOM，移除已处理的回答元素"""
        try:
            # 温和地清理DOM，只清理图片和视频等大内容
            self.driver.execute_script("""
                // 移除图片和视频等大内容，保留文本和页面结构
                var images = document.querySelectorAll('.List-item img, .AnswerItem img');
                var videos = document.querySelectorAll('.List-item video, .AnswerItem video');
                
                // 只移除前面已处理的图片和视频
                for (var i = 0; i < Math.max(0, images.length - 20); i++) {
                    if (images[i]) {
                        images[i].remove();
                    }
                }
                
                for (var i = 0; i < Math.max(0, videos.length - 10); i++) {
                    if (videos[i]) {
                        videos[i].remove();
                    }
                }
                
                // 强制垃圾回收
                if (window.gc) {
                    window.gc();
                }
            """)
            
            logging.info("DOM清理完成")
            
        except Exception as e:
            logging.warning(f"DOM清理失败: {e}")
    
    def cleanup_dom_optimized(self):
        """优化的DOM清理，更彻底地清理已采集的回答节点"""
        try:
            self.driver.execute_script("""
                // 获取所有回答元素
                var listItems = document.querySelectorAll('.List-item');
                var totalItems = listItems.length;
                
                // 保留最后20个回答元素，移除其他已采集的回答
                var keepCount = Math.min(20, totalItems);
                var removeCount = Math.max(0, totalItems - keepCount);
                
                for (var i = 0; i < removeCount; i++) {
                    if (listItems[i]) {
                        // 移除整个回答节点
                        listItems[i].remove();
                    }
                }
                
                // 清理其他大内容元素
                var images = document.querySelectorAll('img');
                var videos = document.querySelectorAll('video');
                var iframes = document.querySelectorAll('iframe');
                
                // 移除多余的媒体内容
                for (var i = 0; i < Math.max(0, images.length - 30); i++) {
                    if (images[i]) {
                        images[i].remove();
                    }
                }
                
                for (var i = 0; i < Math.max(0, videos.length - 5); i++) {
                    if (videos[i]) {
                        videos[i].remove();
                    }
                }
                
                for (var i = 0; i < Math.max(0, iframes.length - 5); i++) {
                    if (iframes[i]) {
                        iframes[i].remove();
                    }
                }
                
                // 强制垃圾回收
                if (window.gc) {
                    window.gc();
                }
                
                return {
                    removed: removeCount,
                    remaining: keepCount
                };
            """)
            
            logging.info("优化DOM清理完成，移除已采集的回答节点")
            
        except Exception as e:
            logging.warning(f"优化DOM清理失败: {e}")
    
    def scroll_retry_mechanism(self):
        """页面回滚机制：执行两次向上滚动操作"""
        try:
            logging.info("触发页面回滚机制：连续3次到达底部且无新内容")
            
            # 第一次向上滚动
            self.driver.execute_script("window.scrollBy(0, -800);")
            time.sleep(random.uniform(*self.scroll_delay))
            logging.info("执行第一次向上滚动")
            
            # 第二次向上滚动
            self.driver.execute_script("window.scrollBy(0, -800);")
            time.sleep(random.uniform(*self.scroll_delay))
            logging.info("执行第二次向上滚动")
            
            logging.info("页面回滚机制完成，恢复向下滚动功能")
            
        except Exception as e:
            logging.warning(f"页面回滚机制失败: {e}")
    
    def has_more_answers(self) -> bool:
        """检查是否还有更多回答可加载"""
        try:
            # 首先检查是否出现"写回答"按钮，如果出现则表示已到达页面底部，没有更多回答
            write_answer_buttons = self.driver.find_elements(
                By.XPATH, 
                "//button[contains(@class, 'QuestionAnswers-answerButton') and contains(text(), '写回答')]"
            )
            if write_answer_buttons:
                logging.info("检测到'写回答'按钮，回答采集完毕")
                return False
            
            # 检查是否有"加载更多"按钮
            load_more_buttons = self.driver.find_elements(By.CSS_SELECTOR, '.Button--primary, .QuestionAnswers-more button')
            if load_more_buttons:
                return True
            
            # 检查当前页面高度，但不主动滚动
            current_scroll_position = self.driver.execute_script("return window.pageYOffset")
            page_height = self.driver.execute_script("return document.body.scrollHeight")
            window_height = self.driver.execute_script("return window.innerHeight")
            
            # 如果还没有滚动到接近底部，认为还有更多内容
            if current_scroll_position + window_height < page_height - 1000:
                return True
            
            return False
            
        except Exception as e:
            logging.warning(f"检查更多回答失败: {e}")
            return False
    
    def close(self):
        """关闭浏览器"""
        if self.driver:
            self.driver.quit()
            logging.info("浏览器已关闭")