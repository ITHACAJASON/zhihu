#!/usr/bin/env python3
"""
专门用于采集指定知乎问题的完整答案数据
问题链接：https://www.zhihu.com/question/378706911/answer/1080446596
目标：采集完整的4470个答案数据
"""

import os
import json
import time
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from loguru import logger

from zhihu_api_crawler import ZhihuAPIAnswerCrawler
from postgres_models import PostgreSQLManager, TaskInfo, Question, Answer


class SpecificQuestionCrawler:
    """专门用于采集指定问题的爬虫类"""

    def __init__(self, question_url: str, task_name: str = None):
        self.question_url = question_url
        self.task_name = task_name or "specific_question_crawl"

        # 初始化组件
        self.api_crawler = ZhihuAPIAnswerCrawler()
        self.db_manager = PostgreSQLManager()

        # 提取问题ID
        self.question_id = self._extract_question_id()
        if not self.question_id:
            raise ValueError(f"无法从URL提取问题ID: {question_url}")

        # 创建输出目录
        self.output_dir = Path("output") / f"question_{self.question_id}"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 创建任务ID
        self.task_id = self._create_or_get_task()

        logger.info(f"专项问题爬虫初始化完成")
        logger.info(f"问题ID: {self.question_id}")
        logger.info(f"任务ID: {self.task_id}")
        logger.info(f"输出目录: {self.output_dir}")

    def _extract_question_id(self) -> Optional[str]:
        """提取问题ID"""
        return self.api_crawler.extract_question_id_from_url(self.question_url)

    def _create_or_get_task(self) -> str:
        """创建或获取任务"""
        # 查找现有任务
        existing_tasks = self.db_manager.get_tasks_by_keyword(self.task_name)
        if existing_tasks:
            task = existing_tasks[0]
            logger.info(f"找到现有任务: {task.task_id}")
            return task.task_id

        # 创建新任务
        task_id = self.db_manager.create_task(
            keywords=self.task_name,
            start_date="2024-01-01",  # 扩大时间范围
            end_date="2025-12-31"
        )
        logger.info(f"创建新任务: {task_id}")
        return task_id

    def _save_api_response(self, response_data: Dict, page_num: int,
                         cursor: str = None, offset: int = 0) -> str:
        """保存API响应数据到文件"""
        try:
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if cursor:
                filename = f"api_response_page_{page_num}_cursor_{cursor[:10]}_{timestamp}.json"
            else:
                filename = f"api_response_page_{page_num}_offset_{offset}_{timestamp}.json"

            filepath = self.output_dir / filename

            # 添加元数据
            response_with_meta = {
                "metadata": {
                    "question_id": self.question_id,
                    "question_url": self.question_url,
                    "task_id": self.task_id,
                    "page_num": page_num,
                    "cursor": cursor,
                    "offset": offset,
                    "timestamp": datetime.now().isoformat(),
                    "response_hash": hashlib.md5(json.dumps(response_data, sort_keys=True).encode()).hexdigest()
                },
                "response": response_data
            }

            # 保存到文件
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(response_with_meta, f, ensure_ascii=False, indent=2)

            logger.info(f"✅ API响应已保存: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"保存API响应失败: {e}")
            return ""

    def _fetch_answers_with_save(self, cursor: str = None, offset: int = 0,
                               limit: int = 20, page_num: int = 0) -> Tuple[Optional[Dict], str]:
        """获取答案并保存响应数据"""
        try:
            # 使用原有的API获取方法
            response_data = self.api_crawler.fetch_answers_page(
                self.question_id, cursor, offset, limit,
                save_response_callback=self._save_api_response,
                page_num=page_num
            )

            if response_data:
                # 响应数据已经在回调函数中保存了
                return response_data, f"page_{page_num}_saved"
            else:
                logger.warning("获取答案数据失败")
                return None, ""

        except Exception as e:
            logger.error(f"获取答案时发生错误: {e}")
            return None, ""

    def _parse_answers_from_api(self, answers_data: List[Dict]) -> List[Answer]:
        """从API响应中解析答案"""
        answers = []
        for answer_data in answers_data:
            answer = self.api_crawler.parse_answer_data(answer_data, self.question_id, self.task_id)
            if answer:
                answers.append(answer)
        return answers

    def crawl_all_answers(self, max_answers: int = None) -> Dict:
        """爬取所有答案并保存数据"""
        logger.info(f"🚀 开始爬取问题 {self.question_id} 的所有答案")
        logger.info(f"目标答案数量: {max_answers or '全部'}")

        start_time = time.time()
        all_answers = []
        saved_files = []
        cursor = None
        offset = 0
        limit = 20
        page_count = 0
        total_api_calls = 0

        try:
            while True:
                page_count += 1
                total_api_calls += 1

                logger.info(f"📄 获取第 {page_count} 页答案 (cursor={cursor}, offset={offset})")

                # 获取数据并保存响应
                page_data, saved_file = self._fetch_answers_with_save(cursor, offset, limit, page_count)
                if saved_file:
                    saved_files.append(saved_file)

                if not page_data:
                    logger.error(f"获取第 {page_count} 页数据失败")
                    break

                # 解析分页信息
                paging = page_data.get('paging', {})
                is_end = paging.get('is_end', True)
                next_url = paging.get('next', '')

                # 获取答案数据
                answers_data = page_data.get('data', [])
                logger.info(f"📦 第 {page_count} 页获取到 {len(answers_data)} 个答案")

                # 解析答案数据
                page_answers = self._parse_answers_from_api(answers_data)
                logger.info(f"📝 本页解析出 {len(page_answers)} 个有效答案")

                # 添加到总答案列表
                all_answers.extend(page_answers)

                # 检查是否达到最大答案数限制
                if max_answers and len(all_answers) >= max_answers:
                    logger.info(f"✅ 已达到最大答案数限制: {max_answers}")
                    break

                # 检查是否已经到最后一页
                if is_end:
                    logger.info(f"🎯 已到达最后一页")
                    break

                # 解析下一页参数
                if next_url:
                    next_params = self.api_crawler._parse_next_url_params(next_url)
                    if 'cursor' in next_params:
                        cursor = next_params['cursor']
                        logger.info(f"🔄 更新cursor: {cursor}")
                    elif 'offset' in next_params:
                        offset = int(next_params['offset'])
                        cursor = None
                        logger.info(f"🔄 更新offset: {offset}")
                    else:
                        offset += limit
                        cursor = None
                        logger.info(f"🔄 递增offset: {offset}")
                else:
                    offset += limit
                    cursor = None
                    logger.info(f"🔄 递增offset: {offset}")

                # 添加延时避免请求过快
                time.sleep(3)

                # 安全检查：避免无限循环
                if page_count > 500:  # 最多500页
                    logger.warning(f"⚠️ 已达到最大页数限制，停止爬取")
                    break

            # 填充答案的content字段
            if all_answers:
                all_answers = self._fill_answers_content(all_answers)

            # 保存答案到数据库
            saved_to_db = False
            if all_answers:
                saved_to_db = self._save_answers_to_db(all_answers)

            end_time = time.time()
            duration = end_time - start_time

            result = {
                'question_id': self.question_id,
                'question_url': self.question_url,
                'task_id': self.task_id,
                'total_answers': len(all_answers),
                'total_pages': page_count,
                'total_api_calls': total_api_calls,
                'saved_files_count': len(saved_files),
                'saved_files': saved_files,
                'saved_to_db': saved_to_db,
                'duration_seconds': round(duration, 2),
                'crawl_time': datetime.now().isoformat(),
                'answers': all_answers
            }

            logger.info(f"🎉 问题 {self.question_id} 答案爬取完成")
            logger.info(f"📊 总共获取到 {len(all_answers)} 个答案")
            logger.info(f"📄 共请求了 {page_count} 页数据")
            logger.info(f"💾 保存了 {len(saved_files)} 个API响应文件")
            logger.info(f"⏱️ 耗时 {duration:.2f} 秒")

            return result

        except Exception as e:
            logger.error(f"爬取过程中发生错误: {e}")
            return {
                'question_id': self.question_id,
                'error': str(e),
                'total_answers': len(all_answers),
                'saved_files_count': len(saved_files),
                'saved_files': saved_files
            }

    def _fill_answers_content(self, answers: List[Answer]) -> List[Answer]:
        """为答案列表填充content字段"""
        logger.info(f"开始为 {len(answers)} 个答案填充content")

        filled_count = 0
        for i, answer in enumerate(answers):
            if not answer.content and answer.answer_id:
                logger.debug(f"获取答案 {answer.answer_id} 的content ({i+1}/{len(answers)})")
                content = self.api_crawler.fetch_single_answer_content(answer.answer_id)

                if content:
                    answer.content = content
                    filled_count += 1

                    # 添加延时避免请求过快
                    time.sleep(0.5)
                else:
                    logger.warning(f"无法获取答案 {answer.answer_id} 的content")

        logger.info(f"成功填充 {filled_count}/{len(answers)} 个答案的content")
        return answers

    def _save_answers_to_db(self, answers: List[Answer]) -> bool:
        """保存答案数据到数据库"""
        try:
            saved_count = 0
            for answer in answers:
                # 生成内容哈希用于去重
                content_hash = hashlib.md5(answer.content.encode('utf-8')).hexdigest()
                answer.content_hash = content_hash

                if self.db_manager.save_answer(answer):
                    saved_count += 1
                else:
                    logger.warning(f"保存答案失败: {answer.answer_id}")

            logger.info(f"成功保存 {saved_count}/{len(answers)} 个答案到数据库")
            return saved_count == len(answers)

        except Exception as e:
            logger.error(f"保存答案到数据库失败: {e}")
            return False

    def save_crawl_summary(self, result: Dict) -> str:
        """保存爬取摘要信息"""
        try:
            summary_file = self.output_dir / "crawl_summary.json"

            summary = {
                "crawl_info": {
                    "question_id": self.question_id,
                    "question_url": self.question_url,
                    "task_id": self.task_id,
                    "task_name": self.task_name,
                    "crawl_time": datetime.now().isoformat(),
                    "target_answers": 4470
                },
                "results": result,
                "statistics": {
                    "total_answers_collected": result.get('total_answers', 0),
                    "total_pages": result.get('total_pages', 0),
                    "total_api_calls": result.get('total_api_calls', 0),
                    "saved_files_count": result.get('saved_files_count', 0),
                    "saved_to_db": result.get('saved_to_db', False),
                    "duration_seconds": result.get('duration_seconds', 0),
                    "completion_rate": round(result.get('total_answers', 0) / 4470 * 100, 2) if result.get('total_answers', 0) > 0 else 0
                }
            }

            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)

            logger.info(f"✅ 爬取摘要已保存: {summary_file}")
            return str(summary_file)

        except Exception as e:
            logger.error(f"保存爬取摘要失败: {e}")
            return ""


def main():
    """主函数"""
    # 指定的问题链接
    question_url = "https://www.zhihu.com/question/378706911/answer/1080446596"

    try:
        # 初始化爬虫
        crawler = SpecificQuestionCrawler(question_url, "question_378706911_full_crawl")

        # 开始爬取
        logger.info("开始执行专项问题答案采集任务...")
        result = crawler.crawl_all_answers(max_answers=4470)

        # 保存摘要
        summary_file = crawler.save_crawl_summary(result)

        # 输出结果
        print("\n" + "="*50)
        print("专项问题答案采集任务完成！")
        print("="*50)
        print(f"问题ID: {result.get('question_id', 'N/A')}")
        print(f"任务ID: {result.get('task_id', 'N/A')}")
        print(f"采集答案数量: {result.get('total_answers', 0)}")
        print(f"目标答案数量: 4470")
        print(f"完成率: {result.get('total_answers', 0)/4470*100:.2f}%")
        print(f"请求页数: {result.get('total_pages', 0)}")
        print(f"API调用次数: {result.get('total_api_calls', 0)}")
        print(f"保存文件数量: {result.get('saved_files_count', 0)}")
        print(f"数据库保存状态: {'成功' if result.get('saved_to_db', False) else '失败'}")
        print(f"耗时: {result.get('duration_seconds', 0)} 秒")
        print(f"输出目录: {crawler.output_dir}")
        if summary_file:
            print(f"摘要文件: {summary_file}")
        print("="*50)

        return result

    except Exception as e:
        logger.error(f"执行专项采集任务时发生错误: {e}")
        import traceback
        logger.error(f"详细错误信息: {traceback.format_exc()}")
        return None


if __name__ == "__main__":
    main()
