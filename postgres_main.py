#!/usr/bin/env python3
"""
知乎爬虫主程序 - PostgreSQL版本
支持任务恢复和实时数据存储
"""

import click
import sys
from pathlib import Path
from loguru import logger
from typing import Dict, Optional

from config import ZhihuConfig
from postgres_crawler import PostgresZhihuCrawler
from postgres_models import PostgreSQLManager
from api_integration import IntegratedZhihuCrawler
from zhihu_api_crawler import ZhihuAPIAnswerCrawler


def setup_logger():
    """设置日志"""
    config = ZhihuConfig()
    config.create_directories()
    
    logger.remove()  # 移除默认处理器
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    logger.add(
        config.LOG_FILE,
        rotation="100 MB",
        retention="30 days",
        level=config.LOG_LEVEL,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
        encoding="utf-8"
    )


def get_postgres_config() -> Dict:
    """获取PostgreSQL配置"""
    config = ZhihuConfig()
    return config.POSTGRES_CONFIG


@click.group()
def cli():
    """知乎爬虫 - PostgreSQL版本"""
    setup_logger()


@cli.command()
@click.option('--keyword', '-k', required=True, help='搜索关键字')
@click.option('--start-date', '-s', help='开始日期 (YYYY-MM-DD)')
@click.option('--end-date', '-e', help='结束日期 (YYYY-MM-DD)')
@click.option('--headless/--no-headless', default=True, help='是否使用无头模式')
def crawl(keyword: str, start_date: Optional[str], end_date: Optional[str], headless: bool):
    """爬取指定关键字的知乎数据"""
    logger.info(f"开始爬取关键字: {keyword}")
    
    postgres_config = get_postgres_config()
    crawler = None
    
    try:
        # 初始化爬虫
        crawler = PostgresZhihuCrawler(headless=headless, postgres_config=postgres_config)
        
        # 检查登录状态
        if not crawler.check_login_status():
            logger.error("未检测到登录状态，必须先登录才能进行数据采集")
            if not headless:
                if not crawler.manual_login_prompt():
                    logger.error("登录失败，无法继续采集")
                    return
            else:
                # 无头模式下切换到非无头模式进行登录
                if not crawler.switch_to_non_headless_for_login():
                    logger.error("登录失败，无法继续采集")
                    return
        
        # 开始爬取
        stats = crawler.crawl_by_keyword(keyword, start_date, end_date)
        
        # 输出统计信息
        logger.info("=" * 50)
        logger.info("爬取完成统计:")
        logger.info(f"任务ID: {stats['task_id']}")
        logger.info(f"关键字: {stats['keyword']}")
        logger.info(f"问题数: {stats['total_questions']}")
        logger.info(f"答案数: {stats['total_answers']}")

        logger.info(f"失败问题数: {stats['failed_questions']}")
        logger.info("=" * 50)
        
    except KeyboardInterrupt:
        logger.warning("用户中断爬取")
        # 如果有当前任务，将其状态更新为paused
        if crawler and hasattr(crawler, 'current_task_id') and crawler.current_task_id:
            try:
                crawler.db.update_task_status(crawler.current_task_id)
                logger.info(f"任务 {crawler.current_task_id} 状态已更新为 paused")
            except Exception as e:
                logger.error(f"更新任务状态失败: {e}")
    except Exception as e:
        logger.error(f"爬取失败: {e}")
        sys.exit(1)
    finally:
        if crawler:
            crawler.close()


@cli.command()
@click.option('--keywords', '-k', required=True, help='多个关键字，用逗号分隔')
@click.option('--start-date', '-s', help='开始日期 (YYYY-MM-DD)')
@click.option('--end-date', '-e', help='结束日期 (YYYY-MM-DD)')
@click.option('--headless/--no-headless', default=True, help='是否使用无头模式')
@click.option('--batch-mode/--no-batch-mode', default=True, help='是否使用批量模式（先搜索所有关键字，再处理详情）')
def batch_crawl(keywords: str, start_date: Optional[str], end_date: Optional[str], headless: bool, batch_mode: bool):
    """批量爬取多个关键字的知乎数据
    
    批量模式下，会先搜索所有关键字并保存搜索结果，然后再统一处理问题详情和答案，可以有效去重。
    非批量模式下，会逐个处理关键字，每个关键字搜索完成后立即处理问题详情和答案。
    """
    keyword_list = [k.strip() for k in keywords.split(',') if k.strip()]
    logger.info(f"开始批量爬取，关键字数量: {len(keyword_list)}")
    
    postgres_config = get_postgres_config()
    crawler = None
    
    try:
        # 初始化爬虫
        crawler = PostgresZhihuCrawler(headless=headless, postgres_config=postgres_config)
        
        # 检查登录状态
        if not crawler.check_login_status():
            logger.error("未检测到登录状态，必须先登录才能进行数据采集")
            if not headless:
                if not crawler.manual_login_prompt():
                    logger.error("登录失败，无法继续采集")
                    return
            else:
                # 无头模式下切换到非无头模式进行登录
                if not crawler.switch_to_non_headless_for_login():
                    logger.error("登录失败，无法继续采集")
                    return
        
        total_stats = {
            'total_tasks': len(keyword_list),
            'completed_tasks': 0,
            'total_questions': 0,
            'total_answers': 0,

            'failed_questions': 0
        }
        
        if batch_mode:
            # 批量模式：先搜索所有关键字，再处理详情
            logger.info("使用批量模式：先搜索所有关键字，再统一处理问题详情和答案")
            
            # 第一阶段：批量搜索所有关键字
            task_ids = crawler.batch_search_questions(keyword_list, start_date, end_date)
            logger.info(f"搜索阶段完成，共创建 {len(task_ids)} 个任务")
            
            # 第二阶段：批量处理搜索结果（爬取问题详情和答案）
            if task_ids:
                logger.info("开始处理搜索结果（爬取问题详情和答案）...")
                stats = crawler.batch_process_search_results(task_ids)
                
                # 更新总体统计信息
                total_stats['completed_tasks'] = stats['processed_tasks']
                total_stats['total_questions'] = stats['total_questions']
                total_stats['total_answers'] = stats['total_answers']

                total_stats['failed_questions'] = stats['failed_questions']
            else:
                logger.warning("没有成功创建任务，跳过处理阶段")
        else:
            # 非批量模式：逐个处理关键字（搜索完立即处理详情）
            logger.info("使用非批量模式：逐个处理关键字，搜索完立即处理问题详情和答案")
            
            # 逐个处理关键字
            for i, keyword in enumerate(keyword_list, 1):
                try:
                    logger.info(f"处理关键字 {i}/{len(keyword_list)}: {keyword}")
                    
                    stats = crawler.crawl_by_keyword(keyword, start_date, end_date, process_immediately=True)
                    
                    total_stats['completed_tasks'] += 1
                    total_stats['total_questions'] += stats['total_questions']
                    total_stats['total_answers'] += stats['total_answers']

                    total_stats['failed_questions'] += stats['failed_questions']
                    
                    logger.info(f"关键字 '{keyword}' 处理完成")
                    
                except Exception as e:
                    logger.error(f"处理关键字 '{keyword}' 失败: {e}")
                    continue
        
        # 输出总体统计信息
        logger.info("=" * 50)
        logger.info("批量爬取完成统计:")
        logger.info(f"总任务数: {total_stats['total_tasks']}")
        logger.info(f"完成任务数: {total_stats['completed_tasks']}")
        logger.info(f"总问题数: {total_stats['total_questions']}")
        logger.info(f"总答案数: {total_stats['total_answers']}")

        logger.info(f"失败问题数: {total_stats['failed_questions']}")
        logger.info("=" * 50)
        
    except KeyboardInterrupt:
        logger.warning("用户中断批量爬取")
    except Exception as e:
        logger.error(f"批量爬取失败: {e}")
        sys.exit(1)
    finally:
        if crawler:
            crawler.close()


@cli.command()
@click.option('--task-id', '-t', help='指定要恢复的任务ID')
@click.option('--headless/--no-headless', default=True, help='是否使用无头模式')
def resume(task_id: Optional[str], headless: bool):
    """恢复中断的任务"""
    postgres_config = get_postgres_config()
    crawler = None
    
    try:
        # 初始化爬虫
        crawler = PostgresZhihuCrawler(headless=headless, postgres_config=postgres_config)
        
        if task_id:
            # 恢复指定任务
            logger.info(f"恢复指定任务: {task_id}")
            stats = crawler.resume_task(task_id)
            
            if stats:
                logger.info("=" * 50)
                logger.info("任务恢复完成统计:")
                logger.info(f"任务ID: {stats['task_id']}")
                logger.info(f"关键字: {stats['keyword']}")
                logger.info(f"问题数: {stats['total_questions']}")
                logger.info(f"答案数: {stats['total_answers']}")

                logger.info(f"失败问题数: {stats['failed_questions']}")
                logger.info("=" * 50)
            else:
                logger.error(f"任务恢复失败: {task_id}")
        else:
            # 列出所有未完成任务并让用户选择
            incomplete_tasks = crawler.list_unfinished_tasks()
            
            if not incomplete_tasks:
                logger.info("没有未完成的任务")
                return
            
            logger.info("发现以下未完成的任务:")
            for i, task in enumerate(incomplete_tasks, 1):
                logger.info(f"{i}. 任务ID: {task.task_id}")
                logger.info(f"   关键字: {task.keywords}")
                logger.info(f"   搜索阶段: {task.search_stage_status}, 问答阶段: {task.qa_stage_status}")
                logger.info(f"   创建时间: {task.created_at}")
                logger.info(f"   更新时间: {task.updated_at}")
                logger.info("-" * 30)
            
            # 让用户选择要恢复的任务
            try:
                choice = input(f"请选择要恢复的任务 (1-{len(incomplete_tasks)}) 或按回车退出: ").strip()
                if not choice:
                    logger.info("用户取消操作")
                    return
                
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(incomplete_tasks):
                    selected_task = incomplete_tasks[choice_idx]
                    logger.info(f"恢复任务: {selected_task.task_id}")
                    
                    # 检查登录状态
                    if not crawler.check_login_status():
                        logger.error("未检测到登录状态，必须先登录才能进行数据采集")
                        if not headless:
                            if not crawler.manual_login_prompt():
                                logger.error("登录失败，无法继续采集")
                                return
                        else:
                            # 无头模式下切换到非无头模式进行登录
                            if not crawler.switch_to_non_headless_for_login():
                                logger.error("登录失败，无法继续采集")
                                return
                    
                    stats = crawler.resume_task(selected_task.task_id)
                    
                    if stats:
                        logger.info("=" * 50)
                        logger.info("任务恢复完成统计:")
                        logger.info(f"任务ID: {stats['task_id']}")
                        logger.info(f"关键字: {stats['keyword']}")
                        logger.info(f"问题数: {stats['total_questions']}")
                        logger.info(f"答案数: {stats['total_answers']}")

                        logger.info(f"失败问题数: {stats['failed_questions']}")
                        logger.info("=" * 50)
                    else:
                        logger.error(f"任务恢复失败: {selected_task.task_id}")
                else:
                    logger.error("无效的选择")
                    
            except ValueError:
                logger.error("无效的输入")
            except KeyboardInterrupt:
                logger.info("用户取消操作")
        
    except Exception as e:
        logger.error(f"任务恢复失败: {e}")
        sys.exit(1)
    finally:
        if crawler:
            crawler.close()


@cli.command()
def list_tasks():
    """列出所有任务"""
    postgres_config = get_postgres_config()
    
    try:
        db = PostgreSQLManager(postgres_config)
        
        # 获取所有未完成任务
        incomplete_tasks = db.get_unfinished_tasks()
        
        if incomplete_tasks:
            logger.info("未完成的任务:")
            for task in incomplete_tasks:
                logger.info(f"任务ID: {task.task_id}")
                logger.info(f"关键字: {task.keywords}")
                logger.info(f"搜索阶段: {task.search_stage_status}, 问答阶段: {task.qa_stage_status}")
                logger.info(f"创建时间: {task.created_at}")
                logger.info(f"更新时间: {task.updated_at}")
                logger.info("-" * 30)
        else:
            logger.info("没有未完成的任务")
        
        db.close()
        
    except Exception as e:
        logger.error(f"列出任务失败: {e}")
        sys.exit(1)


@cli.command()
def init_db():
    """初始化PostgreSQL数据库"""
    postgres_config = get_postgres_config()
    
    try:
        logger.info("初始化PostgreSQL数据库...")
        db = PostgreSQLManager(postgres_config)
        logger.info("数据库初始化成功")
        db.close()
        
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        sys.exit(1)


@cli.command()
@click.option('--sqlite-path', help='SQLite数据库路径')
@click.option('--backup/--no-backup', default=True, help='是否备份SQLite数据库')
def migrate(sqlite_path: Optional[str], backup: bool):
    """从SQLite迁移数据到PostgreSQL"""
    from migrate_to_postgres import DatabaseMigrator
    
    postgres_config = get_postgres_config()
    
    try:
        logger.info("开始数据迁移...")
        migrator = DatabaseMigrator(sqlite_path, postgres_config)
        
        if migrator.migrate_all_data(backup):
            logger.info("数据迁移成功")
        else:
            logger.error("数据迁移失败")
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"数据迁移失败: {e}")
        sys.exit(1)


@cli.command()
@click.option('--question-url', '-u', required=True, help='问题URL')
@click.option('--max-answers', '-m', type=int, help='最大答案数量限制')
@click.option('--task-id', '-t', help='任务ID（可选）')
def api_crawl_answers(question_url: str, max_answers: Optional[int], task_id: Optional[str]):
    """使用API爬取指定问题的答案"""
    logger.info(f"开始使用API爬取问题答案: {question_url}")
    
    postgres_config = get_postgres_config()
    
    try:
        # 初始化API爬虫
        api_crawler = ZhihuAPIAnswerCrawler(postgres_config)
        
        # 测试API连接
        if not api_crawler.test_api_connection():
            logger.error("API连接测试失败，请检查网络连接")
            return
        
        # 爬取答案
        result = api_crawler.crawl_answers_by_question_url(
            question_url=question_url,
            task_id=task_id,
            max_answers=max_answers,
            save_to_db=True
        )
        
        # 输出结果
        logger.info("=" * 50)
        logger.info("API答案爬取完成:")
        logger.info(f"问题URL: {result['question_url']}")
        logger.info(f"任务ID: {result['task_id']}")
        logger.info(f"答案数量: {result['total_answers']}")
        logger.info(f"保存状态: {result['saved_to_db']}")
        logger.info(f"耗时: {result['duration_seconds']} 秒")
        logger.info("=" * 50)
        
        # 显示答案摘要
        if result['answers']:
            logger.info("答案摘要 (前5个):")
            for i, answer in enumerate(result['answers'][:5], 1):
                logger.info(f"  答案{i}: {answer.author} | 点赞:{answer.vote_count} | 评论:{answer.comment_count}")
        
    except Exception as e:
        logger.error(f"API答案爬取失败: {e}")
        sys.exit(1)


@cli.command()
@click.option('--keyword', '-k', required=True, help='搜索关键字')
@click.option('--start-date', '-s', help='开始日期 (YYYY-MM-DD)')
@click.option('--end-date', '-e', help='结束日期 (YYYY-MM-DD)')
@click.option('--headless/--no-headless', default=True, help='是否使用无头模式')
@click.option('--max-questions', '-q', type=int, help='最大问题数量限制')
@click.option('--max-answers', '-a', type=int, help='每个问题的最大答案数量限制')
def hybrid_crawl(keyword: str, start_date: Optional[str], end_date: Optional[str], 
                headless: bool, max_questions: Optional[int], max_answers: Optional[int]):
    """混合模式爬取：Selenium搜索 + API获取答案"""
    logger.info(f"开始混合模式爬取关键字: {keyword}")
    
    postgres_config = get_postgres_config()
    crawler = None
    
    try:
        # 初始化集成爬虫
        crawler = IntegratedZhihuCrawler(
            headless=headless, 
            postgres_config=postgres_config,
            use_api_for_answers=True
        )
        
        # 测试API功能
        if not crawler.test_api_functionality():
            logger.error("API功能测试失败，将使用传统Selenium模式")
            crawler.use_api_for_answers = False
        
        # 开始混合爬取
        result = crawler.crawl_by_keyword_hybrid(
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
            max_questions=max_questions,
            max_answers_per_question=max_answers
        )
        
        # 输出统计信息
        logger.info("=" * 50)
        logger.info("混合模式爬取完成:")
        logger.info(f"任务ID: {result['task_id']}")
        logger.info(f"关键字: {result['keyword']}")
        logger.info(f"问题数: {result['total_questions']}")
        logger.info(f"答案数: {result['total_answers']}")
        logger.info(f"爬取方式: {result['crawl_method']}")
        logger.info(f"耗时: {result['duration_seconds']} 秒")
        logger.info("=" * 50)
        
    except KeyboardInterrupt:
        logger.warning("用户中断爬取")
    except Exception as e:
        logger.error(f"混合模式爬取失败: {e}")
        sys.exit(1)
    finally:
        if crawler:
            crawler.close()


@cli.command()
def test_api():
    """测试API连接和功能"""
    logger.info("开始测试API功能")
    
    postgres_config = get_postgres_config()
    
    try:
        # 测试API爬虫
        api_crawler = ZhihuAPIAnswerCrawler(postgres_config)
        
        if api_crawler.test_api_connection():
            logger.info("✓ API连接测试成功")
            
            # 进行一个简单的答案爬取测试
            test_url = "https://www.zhihu.com/question/25038841"
            logger.info(f"测试爬取问题: {test_url}")
            
            result = api_crawler.crawl_answers_by_question_url(
                question_url=test_url,
                max_answers=3,  # 限制测试数量
                save_to_db=False  # 测试时不保存到数据库
            )
            
            logger.info(f"✓ 测试爬取成功，获取到 {result['total_answers']} 个答案")
            logger.info("API功能正常")
        else:
            logger.error("✗ API连接测试失败")
            
    except Exception as e:
        logger.error(f"API测试失败: {e}")


if __name__ == '__main__':
    cli()