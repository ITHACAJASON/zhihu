#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试页面分析脚本
用于分析指定的知乎页面，获取问题信息和预期回答数量
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from postgres_crawler import PostgresZhihuCrawler
from postgres_models import PostgreSQLManager, Question
from config import ZhihuConfig
from loguru import logger
import time
from datetime import datetime

def analyze_test_page():
    """
    分析测试页面：https://www.zhihu.com/question/11259869114/answer/1938233030117426879
    """
    test_url = "https://www.zhihu.com/question/11259869114/answer/1938233030117426879"
    question_url = "https://www.zhihu.com/question/11259869114"
    
    logger.info(f"开始分析测试页面: {test_url}")
    
    # 初始化爬虫（使用非无头模式以便观察）
    crawler = PostgresZhihuCrawler(headless=False)
    
    try:
        # 访问问题页面
        logger.info(f"访问问题页面: {question_url}")
        crawler.driver.get(question_url)
        time.sleep(5)
        
        # 提取问题ID
        question_id = crawler.extract_id_from_url(question_url)
        logger.info(f"问题ID: {question_id}")
        
        # 获取问题标题
        try:
            title_element = crawler.driver.find_element_by_css_selector("h1.QuestionHeader-title")
            title = title_element.text.strip()
            logger.info(f"问题标题: {title}")
        except Exception as e:
            logger.warning(f"获取问题标题失败: {e}")
            title = "未知标题"
        
        # 获取预期回答数量（使用多种方法）
        expected_answer_count = 0
        
        # 方法1：使用现有的get_accurate_answer_count方法
        try:
            expected_answer_count = crawler.get_accurate_answer_count()
            logger.info(f"方法1 - get_accurate_answer_count: {expected_answer_count}")
        except Exception as e:
            logger.warning(f"方法1失败: {e}")
        
        # 方法2：查找页面上显示的回答数量
        if expected_answer_count == 0:
            try:
                # 查找回答数量显示元素
                answer_count_selectors = [
                    ".QuestionHeader-Comment .Button--plain",
                    ".QuestionHeader-actions .Button--plain",
                    "[data-za-detail-view-path-module='AnswerItem']",
                    ".List-headerText",
                    ".QuestionAnswers-answerAdd"
                ]
                
                for selector in answer_count_selectors:
                    try:
                        elements = crawler.driver.find_elements_by_css_selector(selector)
                        for element in elements:
                            text = element.text.strip()
                            if "个回答" in text or "条回答" in text:
                                import re
                                numbers = re.findall(r'\d+', text)
                                if numbers:
                                    expected_answer_count = int(numbers[0])
                                    logger.info(f"方法2 - 从'{text}'中提取到回答数量: {expected_answer_count}")
                                    break
                        if expected_answer_count > 0:
                            break
                    except Exception as e:
                        continue
            except Exception as e:
                logger.warning(f"方法2失败: {e}")
        
        # 方法3：通过JavaScript获取页面数据
        if expected_answer_count == 0:
            try:
                js_script = """
                // 查找包含回答数量的元素
                var elements = document.querySelectorAll('*');
                for (var i = 0; i < elements.length; i++) {
                    var text = elements[i].textContent;
                    if (text && (text.includes('个回答') || text.includes('条回答'))) {
                        var matches = text.match(/\d+/);
                        if (matches) {
                            return parseInt(matches[0]);
                        }
                    }
                }
                return 0;
                """
                result = crawler.driver.execute_script(js_script)
                if result and result > 0:
                    expected_answer_count = result
                    logger.info(f"方法3 - JavaScript提取到回答数量: {expected_answer_count}")
            except Exception as e:
                logger.warning(f"方法3失败: {e}")
        
        # 创建测试任务ID
        task_id = f"test_task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 保存问题信息到数据库
        if expected_answer_count > 0:
            question = Question(
                question_id=question_id,
                task_id=task_id,
                title=title,
                content="测试问题",
                author="未知",
                author_url="",
                create_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                follow_count=0,
                view_count=0,
                answer_count=expected_answer_count,
                url=question_url,
                tags=[],
                processed=False,
                crawl_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            
            # 保存到数据库
            if crawler.db.save_question(question):
                logger.info(f"问题信息已保存到数据库，任务ID: {task_id}")
                logger.info(f"预期回答数量: {expected_answer_count}")
            else:
                logger.error("保存问题信息到数据库失败")
        else:
            logger.error("未能获取到有效的回答数量")
        
        return {
            'question_id': question_id,
            'task_id': task_id,
            'title': title,
            'expected_answer_count': expected_answer_count,
            'question_url': question_url
        }
        
    except Exception as e:
        logger.error(f"分析测试页面失败: {e}")
        return None
    finally:
        # 关闭浏览器
        if hasattr(crawler, 'driver') and crawler.driver:
            crawler.driver.quit()

if __name__ == "__main__":
    result = analyze_test_page()
    if result:
        print(f"\n=== 测试页面分析结果 ===")
        print(f"问题ID: {result['question_id']}")
        print(f"任务ID: {result['task_id']}")
        print(f"问题标题: {result['title']}")
        print(f"预期回答数量: {result['expected_answer_count']}")
        print(f"问题URL: {result['question_url']}")
    else:
        print("测试页面分析失败")