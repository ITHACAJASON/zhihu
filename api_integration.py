#!/usr/bin/env python3
"""
API爬虫集成模块
将基于API的答案爬取功能集成到现有的知乎爬虫系统中
"""

import time
import uuid
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from loguru import logger

from config import ZhihuConfig
from postgres_models import PostgreSQLManager, TaskInfo, Question, Answer
from zhihu_api_crawler import ZhihuAPIAnswerCrawler
from postgres_crawler import PostgresZhihuCrawler


class IntegratedZhihuCrawler:
    """集成的知乎爬虫类，结合Selenium和API两种方式"""
    
    def __init__(self, headless: bool = True, postgres_config: Dict = None, use_api_for_answers: bool = True):
        self.config = ZhihuConfig()
        self.db = PostgreSQLManager(postgres_config)
        self.use_api_for_answers = use_api_for_answers
        
        # 初始化Selenium爬虫（用于搜索和问题详情）
        self.selenium_crawler = PostgresZhihuCrawler(headless, postgres_config)
        
        # 初始化API爬虫（用于答案采集）
        if use_api_for_answers:
            self.api_crawler = ZhihuAPIAnswerCrawler(postgres_config)
            logger.info("已启用API答案爬取模式")
        else:
            self.api_crawler = None
            logger.info("使用传统Selenium答案爬取模式")
    
    def crawl_by_keyword_hybrid(self, keyword: str, start_date: str = None, 
                               end_date: str = None, max_questions: int = None,
                               max_answers_per_question: int = None) -> Dict:
        """混合模式爬取：Selenium搜索 + API获取答案"""
        task_id = str(uuid.uuid4())
        start_time = time.time()
        
        logger.info(f"开始混合模式爬取，关键字: {keyword}")
        logger.info(f"任务ID: {task_id}")
        
        # 创建任务记录
        task_id = self.db.create_task(
            keywords=keyword,
            start_date=start_date or self.config.DEFAULT_START_DATE,
            end_date=end_date or self.config.DEFAULT_END_DATE
        )
        
        try:
            # 第一阶段：使用Selenium搜索问题
            logger.info("=== 第一阶段：搜索问题 ===")
            search_results = self.selenium_crawler.search_questions(
                keyword, task_id, start_date, end_date
            )
            
            if not search_results:
                logger.warning("未找到相关问题")
                return self._build_result(task_id, keyword, [], [], start_time)
            
            # 限制问题数量
            if max_questions:
                search_results = search_results[:max_questions]
            
            logger.info(f"找到 {len(search_results)} 个相关问题")
            
            # 第二阶段：获取问题详情和答案
            logger.info("=== 第二阶段：获取问题详情和答案 ===")
            questions = []
            all_answers = []
            
            for i, search_result in enumerate(search_results, 1):
                logger.info(f"处理问题 {i}/{len(search_results)}: {search_result.title}")
                
                try:
                    # 获取问题详情（使用Selenium）
                    question = self.selenium_crawler.crawl_question_detail(
                        search_result.question_url, task_id
                    )
                    
                    if question:
                        questions.append(question)
                        self.db.save_question(question)
                        
                        # 获取答案（使用API或Selenium）
                        if self.use_api_for_answers and self.api_crawler:
                            answers = self._crawl_answers_via_api(
                                search_result.question_url, task_id, max_answers_per_question
                            )
                        else:
                            answers = self._crawl_answers_via_selenium(
                                search_result.question_url, question.question_id, 
                                task_id, start_date, end_date
                            )
                        
                        all_answers.extend(answers)
                        logger.info(f"问题 {i} 获取到 {len(answers)} 个答案")
                    
                    # 添加延时
                    time.sleep(2)
                    
                except Exception as e:
                    logger.error(f"处理问题 {i} 时出错: {e}")
                    continue
            
            # 更新任务状态
            task_info.search_stage_status = 'completed'
            task_info.qa_stage_status = 'completed'
            task_info.total_questions = len(questions)
            task_info.processed_questions = len(questions)
            task_info.total_answers = len(all_answers)
            task_info.processed_answers = len(all_answers)
            self.db.update_task(task_info)
            
            return self._build_result(task_id, keyword, questions, all_answers, start_time)
            
        except Exception as e:
            logger.error(f"混合模式爬取失败: {e}")
            # 更新任务状态为失败
            task_info.search_stage_status = 'failed'
            task_info.qa_stage_status = 'failed'
            self.db.update_task(task_info)
            raise
    
    def _crawl_answers_via_api(self, question_url: str, task_id: str, 
                              max_answers: int = None) -> List[Answer]:
        """使用API爬取答案"""
        try:
            result = self.api_crawler.crawl_answers_by_question_url(
                question_url=question_url,
                task_id=task_id,
                max_answers=max_answers,
                save_to_db=True
            )
            return result.get('answers', [])
            
        except Exception as e:
            logger.error(f"API爬取答案失败: {e}")
            return []
    
    def _crawl_answers_via_selenium(self, question_url: str, question_id: str,
                                   task_id: str, start_date: str, end_date: str) -> List[Answer]:
        """使用Selenium爬取答案（备用方案）"""
        try:
            answers, _ = self.selenium_crawler.crawl_answers(
                question_url, question_id, task_id, start_date, end_date
            )
            return answers
            
        except Exception as e:
            logger.error(f"Selenium爬取答案失败: {e}")
            return []
    
    def _build_result(self, task_id: str, keyword: str, questions: List[Question], 
                     answers: List[Answer], start_time: float) -> Dict:
        """构建结果字典"""
        end_time = time.time()
        duration = end_time - start_time
        
        return {
            'task_id': task_id,
            'keyword': keyword,
            'total_questions': len(questions),
            'total_answers': len(answers),
            'duration_seconds': round(duration, 2),
            'questions': questions,
            'answers': answers,
            'crawl_method': 'hybrid' if self.use_api_for_answers else 'selenium',
            'success': True
        }
    
    def crawl_answers_only_by_url(self, question_url: str, task_id: str = None,
                                 max_answers: int = None) -> Dict:
        """仅爬取指定问题的答案（API模式）"""
        if not self.use_api_for_answers or not self.api_crawler:
            raise ValueError("API答案爬取模式未启用")
        
        if not task_id:
            task_id = str(uuid.uuid4())
        
        logger.info(f"开始爬取指定问题的答案: {question_url}")
        
        result = self.api_crawler.crawl_answers_by_question_url(
            question_url=question_url,
            task_id=task_id,
            max_answers=max_answers,
            save_to_db=True
        )
        
        return result
    
    def test_api_functionality(self) -> bool:
        """测试API功能"""
        if not self.api_crawler:
            logger.error("API爬虫未初始化")
            return False
        
        return self.api_crawler.test_api_connection()
    
    def close(self):
        """关闭爬虫资源"""
        if self.selenium_crawler:
            self.selenium_crawler.close()
        logger.info("集成爬虫资源已关闭")


def demo_hybrid_crawling():
    """演示混合爬取功能"""
    print("=== 知乎混合爬虫演示 ===")
    
    # 初始化集成爬虫
    crawler = IntegratedZhihuCrawler(
        headless=True,  # 无头模式
        use_api_for_answers=True  # 启用API答案爬取
    )
    
    try:
        # 测试API连接
        print("\n1. 测试API连接...")
        if crawler.test_api_functionality():
            print("✓ API连接正常")
        else:
            print("✗ API连接失败")
            return
        
        # 演示仅爬取答案功能
        print("\n2. 演示API答案爬取...")
        test_url = "https://www.zhihu.com/question/25038841"
        result = crawler.crawl_answers_only_by_url(
            question_url=test_url,
            max_answers=5  # 限制答案数量用于演示
        )
        
        print(f"问题URL: {result['question_url']}")
        print(f"答案数量: {result['total_answers']}")
        print(f"耗时: {result['duration_seconds']} 秒")
        
        if result['answers']:
            print("\n前3个答案摘要:")
            for i, answer in enumerate(result['answers'][:3], 1):
                print(f"  答案{i}: {answer.author} | 点赞:{answer.vote_count} | 评论:{answer.comment_count}")
        
        # 演示混合爬取功能（可选，需要更多时间）
        print("\n3. 演示混合爬取功能...")
        print("提示：混合爬取需要更多时间，包含搜索和详情获取")
        
        # 取消注释以下代码来演示完整的混合爬取
        # hybrid_result = crawler.crawl_by_keyword_hybrid(
        #     keyword="人工智能",
        #     max_questions=2,  # 限制问题数量
        #     max_answers_per_question=3  # 限制每个问题的答案数量
        # )
        # print(f"混合爬取结果: {hybrid_result['total_questions']} 问题, {hybrid_result['total_answers']} 答案")
        
    except Exception as e:
        print(f"演示过程中出错: {e}")
    
    finally:
        crawler.close()
        print("\n演示完成")


if __name__ == "__main__":
    demo_hybrid_crawling()