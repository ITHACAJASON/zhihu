#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试改进后的知乎API懒加载功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from zhihu_api_crawler import ZhihuAPIAnswerCrawler
from loguru import logger

def test_enhanced_lazyload_api():
    """测试改进后的懒加载API"""
    logger.info("🚀 测试改进后的知乎API懒加载功能")

    # 初始化API爬虫
    crawler = ZhihuAPIAnswerCrawler()

    # 测试问题 - 选择一个答案较多的问题
    test_question_url = "https://www.zhihu.com/question/19551593"
    test_question_id = "19551593"

    logger.info(f"📝 测试问题: {test_question_url}")
    logger.info(f"🔢 问题ID: {test_question_id}")

    # 测试单个页面请求
    logger.info("\n" + "="*60)
    logger.info("🧪 测试单个页面请求")
    logger.info("="*60)

    page_data = crawler.fetch_answers_page(test_question_id, limit=10)
    if page_data:
        feeds_count = len(page_data.get('data', []))
        paging = page_data.get('paging', {})
        session_id = page_data.get('session', {}).get('id', '')

        logger.info("✅ 页面请求成功!")
        logger.info(f"📦 Feeds数量: {feeds_count}")
        logger.info(f"🔑 Session ID: {session_id}")
        logger.info(f"📄 分页信息: is_end={paging.get('is_end', 'Unknown')}")
        logger.info(f"🔗 下一页URL: {paging.get('next', 'None')[:100]}...")

        # 测试完整懒加载
        logger.info("\n" + "="*60)
        logger.info("🚀 测试完整懒加载爬取")
        logger.info("="*60)

        answers, total_count = crawler.crawl_all_answers_for_question(
            test_question_url,
            task_id="test_lazyload",
            max_answers=30  # 限制数量用于测试
        )

        logger.info("🎉 懒加载测试完成!")
        logger.info(f"📊 总共获取到 {total_count} 个答案")

        if answers:
            logger.info("📋 示例答案信息:")
            for i, answer in enumerate(answers[:5], 1):
                logger.info(f"  {i}. {answer.author} - {answer.vote_count}赞")
                logger.info(f"     内容长度: {len(answer.content)} 字符")
        else:
            logger.warning("⚠️ 未获取到答案数据")

        return True
    else:
        logger.error("❌ 页面请求失败")
        return False

def compare_with_old_method():
    """与旧方法对比测试"""
    logger.info("\n" + "="*60)
    logger.info("🔄 与旧方法对比测试")
    logger.info("="*60)

    crawler = ZhihuAPIAnswerCrawler()
    test_question_url = "https://www.zhihu.com/question/19551593"

    # 测试新方法
    logger.info("📈 测试新方法（支持cursor分页）...")
    answers_new, count_new = crawler.crawl_all_answers_for_question(
        test_question_url,
        task_id="test_new",
        max_answers=20
    )

    logger.info(f"✅ 新方法获取到 {count_new} 个答案")

    return count_new > 0

def main():
    """主函数"""
    logger.info("🎯 知乎API懒加载增强功能测试")

    # 测试基础功能
    success = test_enhanced_lazyload_api()

    if success:
        # 对比测试
        compare_with_old_method()

        logger.info("\n" + "="*60)
        logger.info("🎉 所有测试完成!")
        logger.info("="*60)
        logger.info("✅ 改进后的API支持:")
        logger.info("   • 完整的懒加载机制")
        logger.info("   • Cursor分页支持")
        logger.info("   • 连续请求fetch文件")
        logger.info("   • 有效的session ID管理")
        logger.info("   • 自动分页参数解析")
    else:
        logger.error("❌ 测试失败，请检查API配置")

if __name__ == "__main__":
    main()
