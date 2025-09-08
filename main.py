#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能知乎爬虫系统主入口

整合动态参数获取+API批量请求的完整解决方案
"""

import asyncio
import click
import json
import time
from pathlib import Path
from loguru import logger
import sys
from typing import List, Optional

from smart_crawler import SmartCrawler
from monitor_recovery import MonitorRecovery
from params_pool_manager import ParamsPoolManager
from dynamic_params_extractor import DynamicParamsExtractor


# 配置日志
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - <level>{message}</level>",
    level="INFO"
)


@click.group()
@click.option('--debug', is_flag=True, help='启用调试模式')
def cli(debug):
    """智能知乎爬虫系统 - 动态参数获取+API批量请求"""
    if debug:
        logger.remove()
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level="DEBUG"
        )


@cli.command()
@click.argument('question_ids', nargs=-1, required=True)
@click.option('--limit', default=20, help='每页回答数量')
@click.option('--output', '-o', help='输出文件路径')
@click.option('--concurrent', default=5, help='最大并发数')
@click.option('--db-path', default='params_pool.db', help='参数池数据库路径')
@click.option('--user-data-dir', help='Chrome用户数据目录')
@click.option('--monitor', is_flag=True, help='启用监控')
def crawl(question_ids: tuple, limit: int, output: Optional[str], 
          concurrent: int, db_path: str, user_data_dir: Optional[str], monitor: bool):
    """爬取指定问题的回答数据
    
    QUESTION_IDS: 一个或多个问题ID
    
    示例:
        python main.py crawl 19550225 20831813 --limit 10 --output results.json
    """
    asyncio.run(_crawl_async(
        list(question_ids), limit, output, concurrent, 
        db_path, user_data_dir, monitor
    ))


async def _crawl_async(question_ids: List[str], limit: int, output: Optional[str],
                      concurrent: int, db_path: str, user_data_dir: Optional[str], 
                      monitor: bool):
    """异步爬取函数"""
    logger.info(f"🚀 开始爬取 {len(question_ids)} 个问题")
    
    # 创建智能爬虫
    async with SmartCrawler(
        params_db_path=db_path,
        max_concurrent=concurrent,
        user_data_dir=user_data_dir
    ) as crawler:
        
        # 启动监控（如果需要）
        monitor_system = None
        if monitor:
            params_manager = ParamsPoolManager(db_path)
            monitor_system = MonitorRecovery(params_manager)
            monitor_system.start_monitoring()
            logger.info("📊 监控系统已启动")
            
        try:
            # 进度回调
            def progress_callback(current, total, result):
                status = "✅" if result.success else "❌"
                logger.info(f"📋 进度: {current}/{total} {status} {result.question_id} ({result.response_time:.2f}s)")
                
            # 批量爬取
            results = await crawler.batch_crawl(
                question_ids,
                limit=limit,
                progress_callback=progress_callback
            )
            
            # 统计结果
            successful_count = sum(1 for r in results if r.success)
            total_count = len(results)
            
            logger.info(f"🎉 爬取完成: {successful_count}/{total_count} 成功")
            
            # 输出统计信息
            stats = crawler.get_stats()
            logger.info(f"📊 统计信息: {json.dumps(stats, indent=2, ensure_ascii=False)}")
            
            # 保存结果
            if output:
                await _save_results(results, output)
                logger.info(f"💾 结果已保存到: {output}")
            else:
                # 输出到控制台
                _print_results(results)
                
        finally:
            # 停止监控
            if monitor_system:
                monitor_system.stop_monitoring()
                logger.info("📊 监控系统已停止")


async def _save_results(results, output_path: str):
    """保存爬取结果"""
    output_data = {
        'timestamp': time.time(),
        'total_questions': len(results),
        'successful_questions': sum(1 for r in results if r.success),
        'results': [
            {
                'question_id': r.question_id,
                'success': r.success,
                'error': r.error,
                'response_time': r.response_time,
                'data': r.data
            }
            for r in results
        ]
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)


def _print_results(results):
    """打印结果到控制台"""
    for result in results:
        if result.success and result.data:
            logger.info(f"\n📄 问题 {result.question_id}:")
            data = result.data.get('data', [])
            logger.info(f"  回答数量: {len(data)}")
            
            for i, answer in enumerate(data[:3], 1):  # 只显示前3个回答
                author = answer.get('author', {}).get('name', '未知用户')
                voteup_count = answer.get('voteup_count', 0)
                content = answer.get('content', '')[:100] + '...' if len(answer.get('content', '')) > 100 else answer.get('content', '')
                
                logger.info(f"  {i}. {author} (👍{voteup_count}): {content}")
        else:
            logger.error(f"❌ 问题 {result.question_id}: {result.error}")


@cli.command()
@click.argument('question_ids', nargs=-1, required=True)
@click.option('--db-path', default='params_pool.db', help='参数池数据库路径')
@click.option('--user-data-dir', help='Chrome用户数据目录')
@click.option('--headless/--no-headless', default=True, help='是否使用无头模式')
def extract_params(question_ids: tuple, db_path: str, user_data_dir: Optional[str], headless: bool):
    """提取反爬虫参数到参数池
    
    QUESTION_IDS: 一个或多个问题ID
    
    示例:
        python main.py extract-params 19550225 20831813 --no-headless
    """
    logger.info(f"🔍 开始提取 {len(question_ids)} 个问题的参数")
    
    # 创建参数池管理器
    params_manager = ParamsPoolManager(db_path)
    
    # 创建参数提取器
    with DynamicParamsExtractor(headless=headless, user_data_dir=user_data_dir) as extractor:
        
        successful_count = 0
        
        for i, question_id in enumerate(question_ids, 1):
            logger.info(f"📋 处理第 {i}/{len(question_ids)} 个问题: {question_id}")
            
            try:
                params = extractor.extract_params_from_question(question_id)
                
                if params and extractor.validate_params(params):
                    params['question_id'] = question_id
                    
                    if params_manager.add_params(params):
                        successful_count += 1
                        logger.info(f"✅ 参数提取成功: {question_id}")
                    else:
                        logger.warning(f"⚠️ 参数添加失败: {question_id}")
                else:
                    logger.warning(f"⚠️ 参数提取失败: {question_id}")
                    
            except Exception as e:
                logger.error(f"❌ 处理问题 {question_id} 时出错: {e}")
                
            # 添加延时
            if i < len(question_ids):
                time.sleep(2)
                
    logger.info(f"🎉 参数提取完成: {successful_count}/{len(question_ids)} 成功")
    
    # 显示参数池状态
    stats = params_manager.get_pool_stats()
    logger.info(f"📊 参数池状态: {json.dumps(stats, indent=2, ensure_ascii=False)}")


@cli.command()
@click.option('--db-path', default='params_pool.db', help='参数池数据库路径')
def pool_status(db_path: str):
    """查看参数池状态"""
    params_manager = ParamsPoolManager(db_path)
    stats = params_manager.get_pool_stats()
    
    logger.info("📊 参数池状态:")
    logger.info(f"  总参数数: {stats['total_count']}")
    logger.info(f"  活跃参数数: {stats['active_count']}")
    logger.info(f"  新鲜参数数: {stats['fresh_count']}")
    logger.info(f"  平均成功率: {stats['avg_success_rate']:.2%}")
    logger.info(f"  最旧参数年龄: {stats['oldest_age_minutes']:.1f} 分钟")
    logger.info(f"  最新参数年龄: {stats['newest_age_minutes']:.1f} 分钟")


@cli.command()
@click.option('--db-path', default='params_pool.db', help='参数池数据库路径')
@click.option('--interval', default=60, help='监控间隔（秒）')
@click.option('--duration', default=3600, help='监控持续时间（秒）')
@click.option('--export', help='导出指标文件路径')
def monitor(db_path: str, interval: int, duration: int, export: Optional[str]):
    """启动监控系统"""
    logger.info(f"📊 启动监控系统，间隔: {interval}秒，持续: {duration}秒")
    
    params_manager = ParamsPoolManager(db_path)
    monitor_system = MonitorRecovery(
        params_manager=params_manager,
        monitor_interval=interval,
        recovery_enabled=True
    )
    
    try:
        monitor_system.start_monitoring()
        
        # 运行指定时间
        time.sleep(duration)
        
    except KeyboardInterrupt:
        logger.info("⚠️ 监控被用户中断")
    finally:
        monitor_system.stop_monitoring()
        
        # 导出指标
        if export:
            if monitor_system.export_metrics(export):
                logger.info(f"📄 监控指标已导出到: {export}")
            else:
                logger.error("❌ 导出监控指标失败")
                
        # 显示最终报告
        health_report = monitor_system.get_health_report()
        logger.info(f"📊 最终健康度报告: {json.dumps(health_report, indent=2, ensure_ascii=False)}")


@cli.command()
@click.option('--db-path', default='params_pool.db', help='参数池数据库路径')
def cleanup(db_path: str):
    """清理过期参数"""
    params_manager = ParamsPoolManager(db_path)
    
    # 清理前状态
    before_stats = params_manager.get_pool_stats()
    logger.info(f"清理前参数数: {before_stats['total_count']}")
    
    # 执行清理
    cleaned_count = params_manager.cleanup_expired_params()
    
    # 清理后状态
    after_stats = params_manager.get_pool_stats()
    logger.info(f"清理后参数数: {after_stats['total_count']}")
    logger.info(f"🧹 清理了 {cleaned_count} 个过期参数")


@cli.command()
def test():
    """运行系统测试"""
    asyncio.run(_test_async())


async def _test_async():
    """异步测试函数"""
    logger.info("🧪 开始运行系统测试...")
    
    try:
        # 导入测试模块
        from test_smart_crawler import SmartCrawlerTester
        
        tester = SmartCrawlerTester()
        success = await tester.run_integration_test()
        
        if success:
            logger.info("🎉 所有测试通过！")
        else:
            logger.error("💥 部分测试失败")
            sys.exit(1)
            
    except ImportError as e:
        logger.error(f"❌ 无法导入测试模块: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ 测试过程中发生异常: {e}")
        sys.exit(1)


@cli.command()
@click.option('--file', '-f', help='从文件读取问题ID列表')
@click.option('--limit', default=20, help='每页回答数量')
@click.option('--output', '-o', required=True, help='输出目录')
@click.option('--concurrent', default=5, help='最大并发数')
@click.option('--db-path', default='params_pool.db', help='参数池数据库路径')
@click.option('--user-data-dir', help='Chrome用户数据目录')
def batch(file: Optional[str], limit: int, output: str, 
          concurrent: int, db_path: str, user_data_dir: Optional[str]):
    """批量爬取模式
    
    从文件读取问题ID列表进行批量爬取
    
    示例:
        python main.py batch -f questions.txt -o results/ --concurrent 10
    """
    if not file:
        logger.error("❌ 请指定问题ID文件 (--file)")
        sys.exit(1)
        
    # 读取问题ID列表
    try:
        with open(file, 'r', encoding='utf-8') as f:
            question_ids = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        logger.error(f"❌ 文件不存在: {file}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ 读取文件失败: {e}")
        sys.exit(1)
        
    if not question_ids:
        logger.error("❌ 文件中没有有效的问题ID")
        sys.exit(1)
        
    logger.info(f"📋 从文件 {file} 读取到 {len(question_ids)} 个问题ID")
    
    # 创建输出目录
    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成输出文件名
    timestamp = int(time.time())
    output_file = output_dir / f"batch_results_{timestamp}.json"
    
    # 执行批量爬取
    asyncio.run(_crawl_async(
        question_ids, limit, str(output_file), concurrent, 
        db_path, user_data_dir, True  # 启用监控
    ))


if __name__ == '__main__':
    cli()