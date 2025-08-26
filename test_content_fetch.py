#!/usr/bin/env python3
"""
测试单个答案content获取功能
"""

import logging
from zhihu_api_crawler import ZhihuAPIAnswerCrawler

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_single_answer_content():
    """测试获取单个答案的content"""
    crawler = ZhihuAPIAnswerCrawler()

    # 使用一个已知的答案ID进行测试
    test_answer_id = "1102462571"  # 从API响应中获取的答案ID

    logger.info(f"测试获取答案 {test_answer_id} 的content")

    # 获取单个答案的content
    content = crawler.fetch_single_answer_content(test_answer_id)

    logger.info(f"获取到的content长度: {len(content)}")
    if content:
        logger.info("✅ 成功获取到content")
        logger.info(f"Content预览: {content[:200]}...")
    else:
        logger.warning("❌ 未获取到content")

    return content

def test_api_with_content():
    """测试API是否包含content字段"""
    crawler = ZhihuAPIAnswerCrawler()

    # 获取一页答案数据
    page_data = crawler.fetch_answers_page("378706911", offset=0, limit=1)

    if page_data and 'data' in page_data:
        answers_data = page_data['data']
        if answers_data:
            answer_data = answers_data[0]
            content = answer_data.get('content', '')
            answer_id = answer_data.get('id', '')

            logger.info(f"答案 {answer_id} 的content字段: {'存在' if content else '不存在'}")
            logger.info(f"Content长度: {len(content) if content else 0}")

            if not content and answer_id:
                logger.info("尝试单独获取content...")
                content = crawler.fetch_single_answer_content(str(answer_id))
                logger.info(f"单独获取的content长度: {len(content)}")

    return page_data

if __name__ == "__main__":
    logger.info("开始测试content获取功能")

    # 测试1: 获取单个答案的content
    logger.info("=== 测试1: 单个答案content获取 ===")
    test_single_answer_content()

    logger.info("\n=== 测试2: API响应content字段检查 ===")
    test_api_with_content()

    logger.info("测试完成")
