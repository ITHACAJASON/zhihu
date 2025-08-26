#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知乎API爬虫主程序
集成API方法到主要爬虫流程中
"""

import argparse
import time
from typing import List, Optional
from loguru import logger

from config import ZhihuConfig
from postgres_models import PostgreSQLManager, TaskInfo, Question, Answer
from zhihu_api_crawler import ZhihuAPIAnswerCrawler

class ZhihuAPIMain:
    """知乎API爬虫主程序"""

    def __init__(self, postgres_config: dict = None):
        self.config = ZhihuConfig()
        self.db = PostgreSQLManager(postgres_config)
        self.api_crawler = ZhihuAPIAnswerCrawler(postgres_config)

        # 设置日志
        logger.add(
            self.config.LOG_FILE,
            rotation="10 MB",
            level=self.config.LOG_LEVEL,
            encoding="utf-8"
        )

    def crawl_question_answers_api(self, question_url: str, task_id: str = None,
                                 max_answers: int = None, save_to_db: bool = True) -> dict:
        """使用API方法爬取指定问题的答案

        Args:
            question_url: 问题URL
            task_id: 任务ID，如果不提供则自动生成
            max_answers: 最大答案数量限制
            save_to_db: 是否保存到数据库

        Returns:
            爬取结果字典
        """
        start_time = time.time()

        logger.info(f"🕷️ 开始API爬取问题答案: {question_url}")

        # 使用API爬虫获取答案
        result = self.api_crawler.crawl_answers_by_question_url(
            question_url=question_url,
            task_id=task_id,
            max_answers=max_answers,
            save_to_db=save_to_db
        )

        end_time = time.time()
        duration = end_time - start_time

        logger.info(f"✅ API爬取完成: {result['total_answers']} 个答案，耗时 {duration:.2f} 秒")

        return result

    def batch_crawl_answers_api(self, question_urls: List[str], task_id_prefix: str = "api_batch",
                               max_answers_per_question: int = None) -> dict:
        """批量使用API方法爬取多个问题的答案

        Args:
            question_urls: 问题URL列表
            task_id_prefix: 任务ID前缀
            max_answers_per_question: 每个问题的最大答案数量

        Returns:
            批量爬取结果字典
        """
        start_time = time.time()
        total_questions = len(question_urls)
        total_answers = 0
        successful_questions = 0

        logger.info(f"📦 开始批量API爬取 {total_questions} 个问题")

        results = []

        for i, question_url in enumerate(question_urls, 1):
            logger.info(f"处理问题 {i}/{total_questions}: {question_url}")

            try:
                task_id = f"{task_id_prefix}_{i}"

                result = self.crawl_question_answers_api(
                    question_url=question_url,
                    task_id=task_id,
                    max_answers=max_answers_per_question,
                    save_to_db=True
                )

                if result['total_answers'] > 0:
                    successful_questions += 1

                total_answers += result['total_answers']
                results.append(result)

                logger.info(f"问题 {i} 完成: {result['total_answers']} 个答案")

                # 添加延时避免请求过快
                if i < total_questions:
                    time.sleep(1)

            except Exception as e:
                logger.error(f"处理问题 {i} 时出错: {e}")
                continue

        end_time = time.time()
        duration = end_time - start_time

        summary = {
            'total_questions': total_questions,
            'successful_questions': successful_questions,
            'total_answers': total_answers,
            'duration_seconds': round(duration, 2),
            'average_answers_per_question': round(total_answers / total_questions, 2) if total_questions > 0 else 0,
            'results': results
        }

        logger.info(f"📦 批量API爬取完成: {successful_questions}/{total_questions} 成功，{total_answers} 个答案，耗时 {duration:.2f} 秒")

        return summary

    def test_api_connection(self) -> bool:
        """测试API连接"""
        logger.info("🔍 测试API连接...")
        return self.api_crawler.test_api_connection()

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="知乎API爬虫")
    parser.add_argument("action", choices=["crawl", "batch", "test"], help="执行操作")
    parser.add_argument("--question-url", help="问题URL")
    parser.add_argument("--question-urls", nargs="*", help="问题URL列表")
    parser.add_argument("--max-answers", type=int, help="最大答案数量")
    parser.add_argument("--task-id", help="任务ID")

    args = parser.parse_args()

    # 初始化主程序
    main_crawler = ZhihuAPIMain()

    try:
        if args.action == "test":
            # 测试API连接
            if main_crawler.test_api_connection():
                logger.info("✅ API连接测试成功")
            else:
                logger.error("❌ API连接测试失败")

        elif args.action == "crawl":
            # 爬取单个问题
            if not args.question_url:
                logger.error("请提供问题URL: --question-url")
                return

            result = main_crawler.crawl_question_answers_api(
                question_url=args.question_url,
                task_id=args.task_id,
                max_answers=args.max_answers
            )

            print("\n" + "="*50)
            print("🎉 单个问题爬取完成!")
            print(f"📊 答案数量: {result['total_answers']}")
            print(f"⏱️ 耗时: {result['duration_seconds']:.2f} 秒")
            print(f"📋 任务ID: {result['task_id']}")

        elif args.action == "batch":
            # 批量爬取
            if not args.question_urls:
                logger.error("请提供问题URL列表: --question-urls")
                return

            result = main_crawler.batch_crawl_answers_api(
                question_urls=args.question_urls,
                max_answers_per_question=args.max_answers
            )

            print("\n" + "="*50)
            print("🎉 批量爬取完成!")
            print(f"📊 总问题数: {result['total_questions']}")
            print(f"📊 成功问题数: {result['successful_questions']}")
            print(f"📊 总答案数: {result['total_answers']}")
            print(f"⏱️ 总耗时: {result['duration_seconds']:.2f} 秒")
            print(f"📈 平均每题答案数: {result['average_answers_per_question']:.2f}")
    except KeyboardInterrupt:
        logger.info("用户中断操作")
    except Exception as e:
        logger.error(f"程序执行出错: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main()
