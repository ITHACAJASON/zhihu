#!/usr/bin/env python3
"""
增强版批量采集数据库中未处理问题的答案数据
包含反爬处理和自动验证解决功能
"""

import os
import json
import time
import hashlib
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from loguru import logger

from zhihu_api_crawler import ZhihuAPIAnswerCrawler
from postgres_models import PostgreSQLManager, TaskInfo, Question, Answer


class EnhancedBatchQuestionCrawler:
    """增强版批量采集数据库中问题的爬虫类"""

    def __init__(self):
        self.api_crawler = ZhihuAPIAnswerCrawler()
        self.db_manager = PostgreSQLManager()
        
        # 创建输出目录
        self.output_dir = Path("output") / "batch_crawl_enhanced"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 反爬处理配置
        self.max_403_retries = 3
        self.verification_wait_time = 60  # 验证后等待时间
        
        logger.info("增强版批量问题爬虫初始化完成")
        logger.info(f"输出目录: {self.output_dir}")

    def get_unprocessed_questions(self) -> List[Dict]:
        """获取所有未处理的问题"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT question_id, title, url, answer_count, task_id
                    FROM questions 
                    WHERE processed = FALSE
                    ORDER BY answer_count DESC
                """)
                
                questions = []
                for row in cursor.fetchall():
                    questions.append({
                        'question_id': row[0],
                        'title': row[1] or '未知标题',
                        'url': row[2],
                        'answer_count': row[3],
                        'task_id': row[4]
                    })
                
                return questions
                
        except Exception as e:
            logger.error(f"获取未处理问题失败: {e}")
            return []

    def _handle_403_error(self) -> bool:
        """处理403错误，尝试自动验证解决"""
        logger.warning("⚠️ 检测到403错误，尝试自动验证解决...")
        
        try:
            # 运行验证解决脚本
            result = subprocess.run(
                ["python3", "resolve_verification.py"],
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode == 0:
                logger.info("✅ 验证解决成功")
                logger.info(f"等待 {self.verification_wait_time} 秒后继续...")
                time.sleep(self.verification_wait_time)
                return True
            else:
                logger.error(f"验证解决失败: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("验证解决超时")
            return False
        except Exception as e:
            logger.error(f"验证解决过程出错: {e}")
            return False

    def _save_api_response(self, response_data: Dict, question_id: str, page_num: int,
                         cursor: str = None, offset: int = 0) -> str:
        """保存API响应数据到文件"""
        try:
            # 创建问题专用目录
            question_dir = self.output_dir / f"question_{question_id}"
            question_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if cursor:
                filename = f"api_response_page_{page_num}_cursor_{cursor[:10]}_{timestamp}.json"
            else:
                filename = f"api_response_page_{page_num}_offset_{offset}_{timestamp}.json"

            filepath = question_dir / filename

            # 添加元数据
            response_with_meta = {
                "metadata": {
                    "question_id": question_id,
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

    def _parse_answers_from_api(self, answers_data: List[Dict], question_id: str, task_id: str) -> List[Answer]:
        """从API响应中解析答案"""
        answers = []
        for answer_data in answers_data:
            answer = self.api_crawler.parse_answer_data(answer_data, question_id, task_id)
            if answer:
                answers.append(answer)
        return answers

    def crawl_question_answers_with_retry(self, question_info: Dict, max_answers: int = None) -> Dict:
        """带重试机制的爬取单个问题的所有答案"""
        question_id = question_info['question_id']
        question_url = question_info['url']
        task_id = question_info['task_id']
        expected_answers = question_info['answer_count']
        
        logger.info(f"🚀 开始爬取问题 {question_id} 的所有答案")
        logger.info(f"问题标题: {question_info['title']}")
        logger.info(f"预期答案数量: {expected_answers}")

        start_time = time.time()
        all_answers = []
        saved_files = []
        cursor = None
        offset = 0
        limit = 20
        page_count = 0
        total_api_calls = 0
        consecutive_403_errors = 0

        try:
            while True:
                page_count += 1
                total_api_calls += 1

                logger.info(f"📄 获取第 {page_count} 页答案 (cursor={cursor}, offset={offset})")

                # 获取数据
                response_data = self.api_crawler.fetch_answers_page(
                    question_id, cursor, offset, limit,
                    save_response_callback=lambda data, page, c, o: self._save_api_response(data, question_id, page, c, o),
                    page_num=page_count
                )
                
                # 检查是否是403错误导致的空响应
                if not response_data:
                    consecutive_403_errors += 1
                    logger.warning(f"第 {page_count} 页数据获取失败，连续失败次数: {consecutive_403_errors}")
                    
                    if consecutive_403_errors >= self.max_403_retries:
                        logger.error(f"连续 {consecutive_403_errors} 次获取失败，尝试验证解决...")
                        
                        if self._handle_403_error():
                            consecutive_403_errors = 0  # 重置失败计数
                            logger.info("验证解决成功，继续爬取...")
                            continue
                        else:
                            logger.error("验证解决失败，停止爬取当前问题")
                            break
                    else:
                        # 简单重试
                        logger.info(f"等待10秒后重试...")
                        time.sleep(10)
                        continue
                
                # 成功获取数据，重置失败计数
                consecutive_403_errors = 0
                saved_files.append(f"page_{page_count}_saved")

                # 解析分页信息
                paging = response_data.get('paging', {})
                is_end = paging.get('is_end', True)
                next_url = paging.get('next', '')

                # 获取答案数据
                answers_data = response_data.get('data', [])
                logger.info(f"📦 第 {page_count} 页获取到 {len(answers_data)} 个答案")

                # 解析答案数据
                page_answers = self._parse_answers_from_api(answers_data, question_id, task_id)
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
                time.sleep(5)  # 增加延时

                # 安全检查：避免无限循环
                if page_count > 500:
                    logger.warning(f"⚠️ 已达到最大页数限制，停止爬取")
                    break

            # 保存答案到数据库
            saved_to_db = False
            if all_answers:
                saved_to_db = self._save_answers_to_db(all_answers)

            # 标记问题为已处理
            if all_answers:
                self._mark_question_processed(question_id, task_id)

            end_time = time.time()
            duration = end_time - start_time

            result = {
                'question_id': question_id,
                'question_url': question_url,
                'task_id': task_id,
                'title': question_info['title'],
                'expected_answers': expected_answers,
                'total_answers': len(all_answers),
                'total_pages': page_count,
                'total_api_calls': total_api_calls,
                'saved_files_count': len(saved_files),
                'saved_files': saved_files,
                'saved_to_db': saved_to_db,
                'duration_seconds': round(duration, 2),
                'crawl_time': datetime.now().isoformat(),
                'completion_rate': round(len(all_answers) / expected_answers * 100, 2) if expected_answers > 0 else 0,
                'had_403_errors': consecutive_403_errors > 0
            }

            logger.info(f"🎉 问题 {question_id} 答案爬取完成")
            logger.info(f"📊 总共获取到 {len(all_answers)} 个答案")
            logger.info(f"📄 共请求了 {page_count} 页数据")
            logger.info(f"💾 保存了 {len(saved_files)} 个API响应文件")
            logger.info(f"⏱️ 耗时 {duration:.2f} 秒")
            logger.info(f"📈 完成率: {result['completion_rate']}%")

            return result

        except Exception as e:
            logger.error(f"爬取过程中发生错误: {e}")
            return {
                'question_id': question_id,
                'error': str(e),
                'total_answers': len(all_answers),
                'saved_files_count': len(saved_files),
                'saved_files': saved_files
            }

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

    def _mark_question_processed(self, question_id: str, task_id: str):
        """标记问题为已处理"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE questions 
                    SET processed = TRUE, updated_at = CURRENT_TIMESTAMP
                    WHERE question_id = %s AND task_id = %s
                """, (question_id, task_id))
                conn.commit()
                logger.info(f"✅ 问题 {question_id} 标记为已处理")
                
        except Exception as e:
            logger.error(f"标记问题处理状态失败: {e}")

    def crawl_all_unprocessed_questions(self, max_answers_per_question: int = None) -> Dict:
        """批量爬取所有未处理的问题 - 增强版"""
        logger.info("🚀 开始增强版批量爬取所有未处理的问题")
        
        # 获取未处理的问题
        questions = self.get_unprocessed_questions()
        if not questions:
            logger.info("没有未处理的问题")
            return {'total_questions': 0, 'results': []}

        logger.info(f"找到 {len(questions)} 个未处理的问题")
        
        # 排除已经处理过的问题378706911
        questions = [q for q in questions if q['question_id'] != '378706911']
        logger.info(f"排除已处理问题后，剩余 {len(questions)} 个问题")

        if not questions:
            logger.info("所有问题都已处理完成")
            return {'total_questions': 0, 'results': []}

        start_time = time.time()
        results = []
        total_answers = 0
        total_files = 0

        for i, question_info in enumerate(questions, 1):
            logger.info(f"\n{'='*80}")
            logger.info(f"处理第 {i}/{len(questions)} 个问题")
            logger.info(f"问题ID: {question_info['question_id']}")
            logger.info(f"预期答案数: {question_info['answer_count']}")
            logger.info(f"{'='*80}")

            # 爬取问题答案 - 使用增强版方法
            result = self.crawl_question_answers_with_retry(question_info, max_answers_per_question)
            results.append(result)

            # 统计
            if 'total_answers' in result:
                total_answers += result['total_answers']
            if 'saved_files_count' in result:
                total_files += result['saved_files_count']

            # 问题间延时
            if i < len(questions):
                wait_time = 60 if result.get('had_403_errors', False) else 30
                logger.info(f"⏳ 等待{wait_time}秒后处理下一个问题...")
                time.sleep(wait_time)

        end_time = time.time()
        total_duration = end_time - start_time

        summary = {
            'total_questions': len(questions),
            'total_answers_collected': total_answers,
            'total_files_saved': total_files,
            'total_duration_seconds': round(total_duration, 2),
            'average_time_per_question': round(total_duration / len(questions), 2) if questions else 0,
            'results': results,
            'crawl_time': datetime.now().isoformat()
        }

        # 保存批量爬取摘要
        self._save_batch_summary(summary)

        logger.info(f"\n🎉 增强版批量爬取任务完成!")
        logger.info(f"📊 处理问题数量: {len(questions)}")
        logger.info(f"📊 总共采集答案: {total_answers}")
        logger.info(f"📊 保存文件数量: {total_files}")
        logger.info(f"⏱️ 总耗时: {total_duration:.2f} 秒")

        return summary

    def _save_batch_summary(self, summary: Dict) -> str:
        """保存批量爬取摘要"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            summary_file = self.output_dir / f"enhanced_batch_summary_{timestamp}.json"

            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2, default=str)

            logger.info(f"✅ 增强版批量爬取摘要已保存: {summary_file}")
            return str(summary_file)

        except Exception as e:
            logger.error(f"保存批量爬取摘要失败: {e}")
            return ""


def main():
    """主函数"""
    try:
        # 初始化增强版批量爬虫
        crawler = EnhancedBatchQuestionCrawler()

        # 开始批量爬取
        logger.info("开始执行增强版批量问题答案采集任务...")
        summary = crawler.crawl_all_unprocessed_questions()

        # 输出最终结果
        print("\n" + "="*100)
        print("增强版批量问题答案采集任务完成！")
        print("="*100)
        print(f"处理问题数量: {summary['total_questions']}")
        print(f"总共采集答案: {summary['total_answers_collected']}")
        print(f"保存文件数量: {summary['total_files_saved']}")
        print(f"总耗时: {summary['total_duration_seconds']} 秒")
        print(f"平均每个问题耗时: {summary['average_time_per_question']} 秒")
        print(f"输出目录: {crawler.output_dir}")
        print("="*100)

        # 显示各问题详细结果
        if summary['results']:
            print("\n各问题处理结果:")
            for i, result in enumerate(summary['results'], 1):
                status = "成功" if result.get('saved_to_db', False) else "失败"
                completion = result.get('completion_rate', 0)
                had_403 = "有" if result.get('had_403_errors', False) else "无"
                print(f"{i}. 问题{result['question_id']}: {result.get('total_answers', 0)}个答案, "
                      f"完成率{completion}%, 状态: {status}, 403错误: {had_403}")

        return summary

    except Exception as e:
        logger.error(f"执行增强版批量采集任务时发生错误: {e}")
        import traceback
        logger.error(f"详细错误信息: {traceback.format_exc()}")
        return None


if __name__ == "__main__":
    main()
