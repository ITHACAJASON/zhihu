#!/usr/bin/env python3
"""
批量采集知乎问题的示例脚本
演示如何使用crawl_specific_question.py进行批量处理
"""

from crawl_specific_question import SpecificQuestionCrawler
import logging
import time
from typing import List, Dict

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('batch_crawl.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class BatchZhihuCrawler:
    """批量知乎问题爬虫"""

    def __init__(self):
        self.results = []
        self.success_count = 0
        self.total_questions = 0

    def crawl_questions_batch(self, questions_config: List[Dict]) -> List[Dict]:
        """
        批量采集多个知乎问题

        Args:
            questions_config: 问题配置列表，每个元素包含:
                - url: 问题URL (必需)
                - task_name: 任务名称 (可选)
                - max_answers: 最大答案数 (可选)

        Returns:
            采集结果列表
        """
        self.total_questions = len(questions_config)
        logger.info(f"开始批量采集 {self.total_questions} 个问题")

        for i, config in enumerate(questions_config, 1):
            logger.info(f"\n{'='*80}")
            logger.info(f"开始处理第 {i}/{self.total_questions} 个问题")
            logger.info(f"{'='*80}")

            try:
                # 提取配置参数
                question_url = config.get('url')
                if not question_url:
                    logger.error(f"第 {i} 个配置缺少URL参数")
                    continue

                task_name = config.get('task_name', f'batch_crawl_question_{i}')
                max_answers = config.get('max_answers', None)

                logger.info(f"问题URL: {question_url}")
                logger.info(f"任务名称: {task_name}")
                logger.info(f"最大答案数: {max_answers or '不限制'}")

                # 初始化爬虫
                crawler = SpecificQuestionCrawler(
                    question_url=question_url,
                    task_name=task_name
                )

                # 开始采集
                start_time = time.time()
                result = crawler.crawl_all_answers(max_answers=max_answers)
                end_time = time.time()

                # 保存摘要
                summary_file = crawler.save_crawl_summary(result)

                # 记录结果
                result_record = {
                    "config": config,
                    "result": result,
                    "summary_file": summary_file,
                    "duration": end_time - start_time,
                    "success": True
                }

                self.results.append(result_record)
                self.success_count += 1

                logger.info(f"✅ 问题处理成功!")
                logger.info(f"📊 采集答案数量: {result.get('total_answers', 0)}")
                logger.info(f"📄 请求页数: {result.get('total_pages', 0)}")
                logger.info(f"⏱️ 耗时: {result['duration']:.2f} 秒")
                logger.info(f"💾 摘要文件: {summary_file}")

            except Exception as e:
                logger.error(f"❌ 处理问题时发生错误: {e}")
                result_record = {
                    "config": config,
                    "error": str(e),
                    "success": False
                }
                self.results.append(result_record)

            # 问题间延时，避免过于频繁请求
            if i < self.total_questions:
                wait_time = 30  # 30秒延时
                logger.info(f"⏳ 等待 {wait_time} 秒后处理下一个问题...")
                time.sleep(wait_time)

        return self.results

    def print_summary(self):
        """打印汇总结果"""
        print(f"\n{'='*100}")
        print("批量采集任务完成！")
        print(f"{'='*100}")

        if not self.results:
            print("没有处理任何问题")
            return

        print(f"总问题数: {self.total_questions}")
        print(f"成功处理: {self.success_count}")
        print(f"失败数量: {len(self.results) - self.success_count}")

        # 统计数据
        total_answers = 0
        total_pages = 0
        total_duration = 0

        for result in self.results:
            if result.get('success', False):
                result_data = result.get('result', {})
                total_answers += result_data.get('total_answers', 0)
                total_pages += result_data.get('total_pages', 0)
                total_duration += result.get('duration', 0)

        print(f"总答案数: {total_answers}")
        print(f"总请求页数: {total_pages}")
        print(f"总耗时: {total_duration:.2f} 秒")
        print(f"平均每问题耗时: {total_duration/self.total_questions:.2f} 秒" if self.total_questions > 0 else "平均每问题耗时: N/A")

        print(f"{'='*100}")


def main():
    """主函数 - 示例配置"""

    # 示例1: 基本配置
    basic_config = [
        {
            "url": "https://www.zhihu.com/question/378706911/answer/1080446596",
            "task_name": "留学生回国问题_完整采集",
            "max_answers": None  # 采集全部答案
        }
    ]

    # 示例2: 多个问题配置
    multi_questions_config = [
        {
            "url": "https://www.zhihu.com/question/378706911/answer/1080446596",
            "task_name": "留学生回国问题_完整采集",
            "max_answers": None
        },
        {
            "url": "https://www.zhihu.com/question/457478394/answer/1910416671937659055",
            "task_name": "海归硕士就业问题_样本采集",
            "max_answers": 100  # 限制采集100个答案
        },
        {
            "url": "https://www.zhihu.com/question/37197524",
            "task_name": "海归硕士工作难找_测试采集",
            "max_answers": 50   # 测试用，采集50个答案
        }
    ]

    # 示例3: 教育类问题配置
    education_config = [
        {
            "url": "https://www.zhihu.com/question/67330244/answer/115358091057",
            "task_name": "高校老师收入与海归选择_调研",
            "max_answers": 200
        },
        {
            "url": "https://www.zhihu.com/question/62674667/answer/251678451",
            "task_name": "美国博士毕业生回国情况_调研",
            "max_answers": 100
        }
    ]

    # 示例4: 社会热点问题配置
    social_config = [
        {
            "url": "https://www.zhihu.com/question/1891174215585076151/answer/190123456789",
            "task_name": "留学生回国相亲_社交降级_调研",
            "max_answers": 150
        }
    ]

    # 选择要执行的配置
    selected_config = multi_questions_config  # 可以切换为其他配置

    print("知乎问题批量采集示例")
    print(f"将处理 {len(selected_config)} 个问题")
    print("问题列表:")
    for i, config in enumerate(selected_config, 1):
        print(f"  {i}. {config['url']}")
        print(f"     任务: {config['task_name']}")
        print(f"     限制: {config['max_answers'] or '无限制'}")
        print()

    # 确认执行
    confirm = input("是否开始执行？(y/N): ")
    if confirm.lower() != 'y':
        print("已取消执行")
        return

    # 执行批量采集
    batch_crawler = BatchZhihuCrawler()
    results = batch_crawler.crawl_questions_batch(selected_config)

    # 打印汇总结果
    batch_crawler.print_summary()

    # 保存详细结果到文件
    import json
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = f"batch_crawl_result_{timestamp}.json"

    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump({
            "batch_info": {
                "total_questions": len(selected_config),
                "execute_time": datetime.now().isoformat(),
                "config": selected_config
            },
            "results": results
        }, f, ensure_ascii=False, indent=2)

    print(f"详细结果已保存到: {result_file}")

    return results


if __name__ == "__main__":
    main()
