#!/usr/bin/env python3
"""
测试完整的content获取和保存流程
"""

import logging
from crawl_specific_question import SpecificQuestionCrawler

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_full_content_crawl():
    """测试完整的content获取和保存流程"""
    # 创建爬虫实例
    crawler = SpecificQuestionCrawler(
        'https://www.zhihu.com/question/378706911/answer/1080446596',
        'test_content_crawl'
    )

    logger.info("开始测试完整的content获取流程")

    # 测试获取少量答案并填充content
    result = crawler.crawl_all_answers(max_answers=5)

    logger.info("=== 测试结果 ===")
    logger.info(f"获取答案数量: {result.get('total_answers', 0)}")
    logger.info(f"请求页数: {result.get('total_pages', 0)}")
    logger.info(f"保存到数据库: {result.get('saved_to_db', False)}")

    # 检查答案的content
    answers = result.get('answers', [])
    if answers:
        logger.info("=== 答案content检查 ===")
        for i, answer in enumerate(answers[:3], 1):  # 只检查前3个
            content_length = len(answer.content)
            logger.info(f"答案 {i}: ID={answer.answer_id}, content长度={content_length}")
            if content_length > 0:
                logger.info(f"  Content预览: {answer.content[:100]}...")
            else:
                logger.warning(f"  答案 {answer.answer_id} 没有content")

    # 检查数据库中的数据
    try:
        from postgres_models import PostgreSQLManager
        db = PostgreSQLManager()
        saved_answers = db.get_unprocessed_answers(crawler.task_id)

        logger.info(f"数据库中找到 {len(saved_answers)} 个答案")
        if saved_answers:
            for answer in saved_answers[:3]:  # 只检查前3个
                logger.info(f"  数据库答案: ID={answer.answer_id}, content长度={len(answer.content)}")
    except Exception as e:
        logger.error(f"检查数据库失败: {e}")

    return result

if __name__ == "__main__":
    test_full_content_crawl()
