#!/usr/bin/env python3
"""
批量为数据库中的答案填充content
"""

import logging
import time
from postgres_models import PostgreSQLManager
from zhihu_api_crawler import ZhihuAPIAnswerCrawler
from loguru import logger

def batch_fill_content(max_answers=None):
    """批量为答案填充content"""
    logger.info("开始批量填充答案content...")

    # 初始化组件
    db = PostgreSQLManager()
    crawler = ZhihuAPIAnswerCrawler()

    # 获取任务ID
    task_id = '8f6d2f94-8d62-4c17-ac50-756d437cef6b'

    # 获取所有答案
    answers = db.get_unprocessed_answers(task_id)
    logger.info(f"找到 {len(answers)} 个答案需要处理")

    if max_answers:
        answers = answers[:max_answers]
        logger.info(f"限制处理数量为 {max_answers} 个")

    # 处理答案
    filled_count = 0
    error_count = 0

    for i, answer in enumerate(answers):
        if not answer.content or len(answer.content) == 0:
            logger.debug(f"处理答案 {answer.answer_id} ({i+1}/{len(answers)})")

            try:
                # 获取content
                content = crawler.fetch_single_answer_content(answer.answer_id)

                if content and len(content) > 0:
                    # 更新答案对象
                    answer.content = content
                    filled_count += 1

                    # 保存到数据库
                    if db.save_answer(answer):
                        logger.debug(f"✅ 答案 {answer.answer_id} 已更新")
                    else:
                        logger.warning(f"❌ 答案 {answer.answer_id} 保存失败")
                        error_count += 1
                else:
                    logger.warning(f"❌ 无法获取答案 {answer.answer_id} 的content")
                    error_count += 1

            except Exception as e:
                logger.error(f"处理答案 {answer.answer_id} 时发生错误: {e}")
                error_count += 1

            # 添加延时
            time.sleep(0.5)

        # 每处理50个输出一次进度
        if (i + 1) % 50 == 0:
            logger.info(f"已处理 {i+1}/{len(answers)} 个答案，已填充 {filled_count} 个")

    logger.info("=== 批量处理完成 ===")
    logger.info(f"总共处理了 {len(answers)} 个答案")
    logger.info(f"成功填充 {filled_count} 个答案的content")
    logger.info(f"失败 {error_count} 个答案")
    if len(answers) > 0:
        success_rate = filled_count / len(answers) * 100
        logger.info(f"成功率: {success_rate:.1f}%")
    return filled_count, error_count

if __name__ == "__main__":
    # 先处理少量答案进行测试
    logger.info("测试批量处理，先处理10个答案...")
    filled_count, error_count = batch_fill_content(max_answers=10)

    if filled_count > 0:
        logger.info("✅ 批量处理测试成功！")
    else:
        logger.warning("⚠️ 批量处理测试失败")
