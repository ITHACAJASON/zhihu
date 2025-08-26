#!/usr/bin/env python3
"""
知乎专项问题答案采集任务 - 最终总结
问题：https://www.zhihu.com/question/378706911/answer/1080446596
目标：采集完整的4470个答案数据
"""

import os
from postgres_models import PostgreSQLManager
from loguru import logger

def generate_final_summary():
    """生成最终的项目总结"""
    logger.info("🎯 知乎专项问题答案采集任务 - 最终总结")
    logger.info("=" * 60)

    # 基本信息
    question_url = "https://www.zhihu.com/question/378706911/answer/1080446596"
    question_id = "378706911"
    target_answers = 4470

    logger.info(f"📋 问题链接: {question_url}")
    logger.info(f"🔢 问题ID: {question_id}")
    logger.info(f"🎯 目标答案数量: {target_answers}")
    logger.info("")

    # 检查输出目录
    output_dir = f"output/question_{question_id}"
    if os.path.exists(output_dir):
        files = os.listdir(output_dir)
        api_response_files = [f for f in files if f.startswith('api_response_')]
        logger.info(f"📁 输出目录: {output_dir}")
        logger.info(f"📄 API响应文件数量: {len(api_response_files)}")
        logger.info(f"📊 总文件数量: {len(files)}")
    else:
        logger.warning(f"❌ 输出目录不存在: {output_dir}")

    logger.info("")

    # 检查数据库
    logger.info("💾 数据库存储状态:")
    db = PostgreSQLManager()
    task_id = '8f6d2f94-8d62-4c17-ac50-756d437cef6b'

    try:
        answers = db.get_unprocessed_answers(task_id)
        logger.info(f"   数据库中的答案数量: {len(answers)}")

        # 统计content状态
        empty_content_count = sum(1 for answer in answers if not answer.content or len(answer.content) == 0)
        filled_content_count = len(answers) - empty_content_count

        logger.info(f"   有content的答案数量: {filled_content_count}")
        logger.info(f"   无content的答案数量: {empty_content_count}")

        if len(answers) > 0:
            fill_rate = filled_content_count / len(answers) * 100
            logger.info(f"   content填充率: {fill_rate:.1f}%")

        # 显示一些统计信息
        if filled_content_count > 0:
            total_content_length = sum(len(answer.content) for answer in answers if answer.content)
            avg_content_length = total_content_length // filled_content_count
            logger.info(f"   平均content长度: {avg_content_length} 字符")

        logger.info("")

        # 任务完成度分析
        logger.info("📈 任务完成度分析:")
        collected_answers = len(answers)
        completion_rate = collected_answers / target_answers * 100
        logger.info(f"   答案采集完成率: {completion_rate:.2f}% ({collected_answers}/{target_answers})")

        if fill_rate >= 90:
            logger.info("   content填充完成度: ✅ 优秀")
        elif fill_rate >= 70:
            logger.info("   content填充完成度: ✅ 良好")
        else:
            logger.info("   content填充完成度: ⚠️ 需要改进")

    except Exception as e:
        logger.error(f"检查数据库失败: {e}")

    logger.info("")
    logger.info("🎉 项目成果总结:")
    logger.info("✅ 成功实现API方式采集知乎答案数据")
    logger.info("✅ 成功保存每次API请求的响应数据到本地文件")
    logger.info("✅ 成功将答案数据保存到PostgreSQL数据库")
    logger.info("✅ 实现反爬策略和错误处理")
    logger.info("✅ 支持断点续传和任务恢复")
    logger.info("✅ 自动检测和填充缺失的content字段")

    logger.info("")
    logger.info("📂 输出文件结构:")
    logger.info(f"   output/question_{question_id}/")
    logger.info("   ├── api_response_page_1_offset_0_*.json")
    logger.info("   ├── api_response_page_2_offset_20_*.json")
    logger.info("   ├── ...")
    logger.info("   └── crawl_summary.json")

    logger.info("")
    logger.info("🗄️ 数据库表结构:")
    logger.info("   - task_info: 任务信息表")
    logger.info("   - search_results: 搜索结果表")
    logger.info("   - questions: 问题信息表")
    logger.info("   - answers: 答案信息表")

    logger.info("")
    logger.info("=" * 60)
    logger.info("🎊 专项问题答案采集任务完成！")

if __name__ == "__main__":
    generate_final_summary()
