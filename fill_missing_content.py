#!/usr/bin/env python3
"""
为数据库中缺少content的答案填充content
"""

import logging
from postgres_models import PostgreSQLManager
from zhihu_api_crawler import ZhihuAPIAnswerCrawler
from loguru import logger

def fill_missing_content():
    """为缺少content的答案填充content"""
    logger.info("开始为数据库中的答案填充content...")

    # 初始化组件
    db = PostgreSQLManager()
    crawler = ZhihuAPIAnswerCrawler()

    # 获取任务ID
    task_id = '8f6d2f94-8d62-4c17-ac50-756d437cef6b'

    # 获取所有答案
    answers = db.get_unprocessed_answers(task_id)
    logger.info(f"找到 {len(answers)} 个答案需要处理")

    # 统计和填充content
    filled_count = 0
    error_count = 0

    for i, answer in enumerate(answers):
        if not answer.content or len(answer.content) == 0:
            logger.debug(f"正在处理答案 {answer.answer_id} ({i+1}/{len(answers)})")

            try:
                # 获取content
                content = crawler.fetch_single_answer_content(answer.answer_id)

                if content:
                    # 更新答案的content
                    answer.content = content
                    filled_count += 1

                    # 重新保存到数据库
                    if db.save_answer(answer):
                        logger.debug(f"✅ 答案 {answer.answer_id} content已更新")
                    else:
                        logger.warning(f"❌ 答案 {answer.answer_id} 保存失败")
                        error_count += 1
                else:
                    logger.warning(f"❌ 无法获取答案 {answer.answer_id} 的content")
                    error_count += 1

                # 添加延时避免请求过快
                import time
                time.sleep(0.5)

            except Exception as e:
                logger.error(f"处理答案 {answer.answer_id} 时发生错误: {e}")
                error_count += 1

        # 每处理100个答案输出一次进度
        if (i + 1) % 100 == 0:
            logger.info(f"已处理 {i+1}/{len(answers)} 个答案，已填充 {filled_count} 个")

    logger.info("=== 处理完成 ===")
    logger.info(f"总共处理了 {len(answers)} 个答案")
    logger.info(f"成功填充 {filled_count} 个答案的content")
    logger.info(f"失败 {error_count} 个答案")
    logger.info(".1f"
    return filled_count, error_count

def verify_content_filled():
    """验证content是否已正确填充"""
    logger.info("验证content填充结果...")

    db = PostgreSQLManager()
    task_id = '8f6d2f94-8d62-4c17-ac50-756d437cef6b'

    answers = db.get_unprocessed_answers(task_id)

    # 检查前10个答案
    logger.info("检查前10个答案的content:")
    for i, answer in enumerate(answers[:10], 1):
        content_length = len(answer.content)
        logger.info(f"  答案 {i}: ID={answer.answer_id}, content长度={content_length}")
        if content_length > 0:
            logger.info(f"    内容预览: {answer.content[:100]}...")
        else:
            logger.warning(f"    答案 {answer.answer_id} 仍然没有content")

    # 统计总体情况
    empty_content_count = sum(1 for answer in answers if not answer.content or len(answer.content) == 0)
    logger.info(f"content为空的答案数量: {empty_content_count}/{len(answers)}")

    if empty_content_count == 0:
        logger.info("✅ 所有答案都有content！")
        return True
    else:
        logger.warning(f"❌ 仍有 {empty_content_count} 个答案没有content")
        return False

if __name__ == "__main__":
    # 首先验证当前状态
    logger.info("=== 填充前状态检查 ===")
    verify_content_filled()

    # 填充content
    logger.info("\\n=== 开始填充content ===")
    filled_count, error_count = fill_missing_content()

    # 验证结果
    logger.info("\\n=== 填充后验证 ===")
    success = verify_content_filled()

    if success:
        logger.info("🎉 content填充任务完成！")
    else:
        logger.warning("⚠️ 部分答案content填充失败")
