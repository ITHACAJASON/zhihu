"""
命令行入口
"""

import sys
import click
from loguru import logger

from crawler import ZhihuCrawler
from config import ZhihuConfig

@click.group()
def cli():
    """知乎爬虫工具"""
    pass

@cli.command()
@click.option('--keyword', required=True, help='搜索关键字')
@click.option('--start', 'start_date', default=ZhihuConfig.DEFAULT_START_DATE, help='开始日期，格式 YYYY-MM-DD')
@click.option('--end', 'end_date', default=ZhihuConfig.DEFAULT_END_DATE, help='结束日期，格式 YYYY-MM-DD')
@click.option('--headless/--no-headless', default=True, help='是否使用无头模式')
@click.option('--db', 'db_path', default=None, help='数据库文件路径')
@click.option('--log-level', default='INFO', help='日志级别')
def single(keyword: str, start_date: str, end_date: str, headless: bool, db_path: str, log_level: str):
    """单关键字爬取"""
    logger.remove()
    logger.add(sys.stderr, level=log_level)
    
    crawler = ZhihuCrawler(headless=headless, db_path=db_path)
    try:
        stats = crawler.crawl_by_keyword(keyword, start_date, end_date)
        click.echo(f"爬取完成: {stats}")
    finally:
        crawler.close()

@cli.command()
@click.option('--start', 'start_date', default=ZhihuConfig.DEFAULT_START_DATE, help='开始日期，格式 YYYY-MM-DD')
@click.option('--end', 'end_date', default=ZhihuConfig.DEFAULT_END_DATE, help='结束日期，格式 YYYY-MM-DD')
@click.option('--headless/--no-headless', default=True, help='是否使用无头模式')
@click.option('--db', 'db_path', default=None, help='数据库文件路径')
@click.option('--log-level', default='INFO', help='日志级别')
@click.option('--resume-task', type=int, default=None, help='恢复指定任务ID')
@click.option('--use-cache/--no-cache', default=True, help='是否使用缓存文件（默认启用）')
def batch(start_date: str, end_date: str, headless: bool, db_path: str, log_level: str, resume_task: int, use_cache: bool):
    """批量关键字爬取（海归相关）"""
    # 预定义的关键字列表
    keywords = ["海归 回国", "留学生 回国", "海外 回国", "博士 回国"]
    
    logger.remove()
    logger.add(sys.stderr, level=log_level)
    
    crawler = ZhihuCrawler(headless=headless, db_path=db_path)
    try:
        stats = crawler.crawl_by_multiple_keywords(keywords, start_date, end_date, resume_task, use_cache)
        click.echo(f"批量爬取完成: {stats}")
    finally:
        crawler.close()

@cli.command()
@click.option('--keywords', required=True, help='多个关键字，用逗号分隔')
@click.option('--start', 'start_date', default=ZhihuConfig.DEFAULT_START_DATE, help='开始日期，格式 YYYY-MM-DD')
@click.option('--end', 'end_date', default=ZhihuConfig.DEFAULT_END_DATE, help='结束日期，格式 YYYY-MM-DD')
@click.option('--headless/--no-headless', default=True, help='是否使用无头模式')
@click.option('--db', 'db_path', default=None, help='数据库文件路径')
@click.option('--log-level', default='INFO', help='日志级别')
@click.option('--resume-task', type=int, default=None, help='恢复指定任务ID')
@click.option('--use-cache/--no-cache', default=True, help='是否使用缓存文件（默认启用）')
def multi(keywords: str, start_date: str, end_date: str, headless: bool, db_path: str, log_level: str, resume_task: int, use_cache: bool):
    """自定义多关键字爬取"""
    keyword_list = [k.strip() for k in keywords.split(',') if k.strip()]
    
    if not keyword_list:
        click.echo("错误：请提供至少一个关键字")
        return
    
    logger.remove()
    logger.add(sys.stderr, level=log_level)
    
    crawler = ZhihuCrawler(headless=headless, db_path=db_path)
    try:
        stats = crawler.crawl_by_multiple_keywords(keyword_list, start_date, end_date, resume_task, use_cache)
        click.echo(f"多关键字爬取完成: {stats}")
    finally:
        crawler.close()

@cli.command()
@click.option('--task-id', type=int, required=True, help='要恢复的任务ID')
@click.option('--headless/--no-headless', default=True, help='是否使用无头模式')
@click.option('--db', 'db_path', default=None, help='数据库文件路径')
@click.option('--log-level', default='INFO', help='日志级别')
def resume(task_id: int, headless: bool, db_path: str, log_level: str):
    """恢复未完成的爬取任务"""
    logger.remove()
    logger.add(sys.stderr, level=log_level)
    
    crawler = ZhihuCrawler(headless=headless, db_path=db_path)
    try:
        stats = crawler.resume_task(task_id)
        click.echo(f"任务恢复完成: {stats}")
    finally:
        crawler.close()

@cli.command()
@click.option('--db', 'db_path', default=None, help='数据库文件路径')
def list_tasks(db_path: str):
    """列出所有未完成的任务"""
    from models import DatabaseManager
    
    db = DatabaseManager(db_path)
    incomplete_tasks = db.get_incomplete_tasks()
    
    if not incomplete_tasks:
        click.echo("没有未完成的任务")
        return
    
    click.echo("未完成的任务列表:")
    click.echo("-" * 80)
    
    for task in incomplete_tasks:
        click.echo(f"任务ID: {task['id']}")
        click.echo(f"类型: {task['task_type']}")
        click.echo(f"关键字: {', '.join(task['keywords'])}")
        click.echo(f"当前阶段: {task['current_stage']}")
        click.echo(f"创建时间: {task['created_at']}")
        click.echo(f"问题数: {task['total_questions']}, 答案数: {task['total_answers']}, 评论数: {task['total_comments']}")
        click.echo("-" * 80)

if __name__ == '__main__':
    cli()