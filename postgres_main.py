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
    return {
        'host': config.POSTGRES_HOST,
        'port': config.POSTGRES_PORT,
        'database': config.POSTGRES_DATABASE,
        'user': config.POSTGRES_USER,
        'password': config.POSTGRES_PASSWORD
    }


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
                logger.error("无头模式下无法进行登录，请先在非无头模式下登录")
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
        logger.info(f"评论数: {stats['total_comments']}")
        logger.info(f"失败问题数: {stats['failed_questions']}")
        logger.info("=" * 50)
        
    except KeyboardInterrupt:
        logger.warning("用户中断爬取")
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
def batch_crawl(keywords: str, start_date: Optional[str], end_date: Optional[str], headless: bool):
    """批量爬取多个关键字的知乎数据"""
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
                logger.error("无头模式下无法进行登录，请先在非无头模式下登录")
                return
        
        total_stats = {
            'total_tasks': len(keyword_list),
            'completed_tasks': 0,
            'total_questions': 0,
            'total_answers': 0,
            'total_comments': 0,
            'failed_questions': 0
        }
        
        # 逐个处理关键字
        for i, keyword in enumerate(keyword_list, 1):
            try:
                logger.info(f"处理关键字 {i}/{len(keyword_list)}: {keyword}")
                
                stats = crawler.crawl_by_keyword(keyword, start_date, end_date)
                
                total_stats['completed_tasks'] += 1
                total_stats['total_questions'] += stats['total_questions']
                total_stats['total_answers'] += stats['total_answers']
                total_stats['total_comments'] += stats['total_comments']
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
        logger.info(f"总评论数: {total_stats['total_comments']}")
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
                logger.info(f"评论数: {stats['total_comments']}")
                logger.info(f"失败问题数: {stats['failed_questions']}")
                logger.info("=" * 50)
            else:
                logger.error(f"任务恢复失败: {task_id}")
        else:
            # 列出所有未完成任务并让用户选择
            incomplete_tasks = crawler.list_incomplete_tasks()
            
            if not incomplete_tasks:
                logger.info("没有未完成的任务")
                return
            
            logger.info("发现以下未完成的任务:")
            for i, task in enumerate(incomplete_tasks, 1):
                logger.info(f"{i}. 任务ID: {task.task_id}")
                logger.info(f"   关键字: {task.keywords}")
                logger.info(f"   状态: {task.status}")
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
                            logger.error("无头模式下无法进行登录，请先在非无头模式下登录")
                            return
                    
                    stats = crawler.resume_task(selected_task.task_id)
                    
                    if stats:
                        logger.info("=" * 50)
                        logger.info("任务恢复完成统计:")
                        logger.info(f"任务ID: {stats['task_id']}")
                        logger.info(f"关键字: {stats['keyword']}")
                        logger.info(f"问题数: {stats['total_questions']}")
                        logger.info(f"答案数: {stats['total_answers']}")
                        logger.info(f"评论数: {stats['total_comments']}")
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
        incomplete_tasks = db.get_incomplete_tasks()
        
        if incomplete_tasks:
            logger.info("未完成的任务:")
            for task in incomplete_tasks:
                logger.info(f"任务ID: {task.task_id}")
                logger.info(f"关键字: {task.keywords}")
                logger.info(f"状态: {task.status}")
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


if __name__ == '__main__':
    cli()