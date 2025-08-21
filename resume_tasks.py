#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知乎爬虫任务恢复脚本
用于恢复中断的爬虫任务

使用方法:
1. 恢复所有未完成任务: python3 resume_tasks.py --all
2. 恢复特定关键词任务: python3 resume_tasks.py --keyword "博士回国"
3. 查看未完成任务列表: python3 resume_tasks.py --list
4. 恢复特定任务ID: python3 resume_tasks.py --task-id "task_id_here"
"""

import argparse
import sys
import time
from datetime import datetime
from postgres_crawler import PostgresZhihuCrawler

def print_banner():
    """打印脚本横幅"""
    print("="*60)
    print("           知乎爬虫任务恢复脚本")
    print("="*60)
    print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

def check_system_status(crawler):
    """检查系统状态"""
    print("🔍 检查系统状态...")
    
    # 检查数据库连接
    try:
        with crawler.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
        print("✅ 数据库连接正常")
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return False
    
    # 检查登录状态
    try:
        if not crawler.check_login_status():
            print("⚠️  登录状态无效，尝试加载cookies...")
            crawler.load_cookies()
            if crawler.check_login_status():
                print("✅ 登录状态已恢复")
            else:
                print("❌ 登录状态无效，请手动登录知乎")
                return False
        else:
            print("✅ 登录状态有效")
    except Exception as e:
        print(f"⚠️  无法检查登录状态: {e}")
    
    print()
    return True

def list_unfinished_tasks(crawler):
    """列出所有未完成的任务（使用新的两阶段状态判断）"""
    print("📋 查询中断任务...")
    
    try:
        # 使用新的中断任务查询方法
        interrupted_tasks = crawler.db.get_interrupted_tasks()
        
        if not interrupted_tasks:
            print("✅ 没有中断的任务")
            return []
        
        print(f"📊 找到 {len(interrupted_tasks)} 个中断任务:")
        print("-" * 100)
        print(f"{'序号':<4} {'任务ID':<20} {'关键词':<15} {'搜索阶段':<10} {'问答阶段':<10} {'创建时间':<20}")
        print("-" * 100)
        
        for i, task in enumerate(interrupted_tasks, 1):
            search_status = task.search_stage_status
            qa_status = task.qa_stage_status
            print(f"{i:<4} {task.task_id[:20]:<20} {task.keywords:<15} {search_status:<10} {qa_status:<10} {str(task.created_at)[:16]:<20}")
        
        print("-" * 100)
        print()
        return interrupted_tasks
        
    except Exception as e:
        print(f"❌ 查询任务失败: {e}")
        return []

def resume_task_by_keyword(crawler, keyword, start_date=None, end_date=None):
    """根据关键词恢复任务（使用新的两阶段恢复策略）"""
    print(f"🔍 查找关键词 '{keyword}' 的中断任务...")
    
    try:
        tasks = crawler.db.get_tasks_by_keyword(keyword)
        
        if not tasks:
            print(f"❌ 没有找到关键词 '{keyword}' 的任务，创建新任务")
            # 设置默认日期范围
            if not start_date:
                start_date = "2024-01-01"
            if not end_date:
                end_date = "2024-12-31"
            
            result = crawler.crawl_by_keyword(
                keyword=keyword,
                start_date=start_date,
                end_date=end_date,
                process_immediately=True
            )
            print(f"✅ 新任务 '{keyword}' 创建完成: {result}")
            return True
        
        # 找到中断的任务
        interrupted_tasks = []
        for task in tasks:
            if not (task.search_stage_status == 'completed' and task.qa_stage_status == 'completed'):
                interrupted_tasks.append(task)
        
        if not interrupted_tasks:
            print(f"✅ 关键词 '{keyword}' 的所有任务都已完成")
            return True
        
        print(f"📊 找到 {len(interrupted_tasks)} 个中断任务")
        
        # 恢复每个中断的任务
        success_count = 0
        for task in interrupted_tasks:
            try:
                if resume_single_task(crawler, task.task_id):
                    success_count += 1
            except Exception as e:
                print(f"❌ 任务 {task.task_id} 恢复失败: {e}")
                # 尝试重置驱动后重试
                print("🔄 重置浏览器驱动后重试...")
                try:
                    crawler.reset_driver()
                    time.sleep(10)
                    if resume_single_task(crawler, task.task_id):
                        success_count += 1
                except Exception as retry_error:
                    print(f"❌ 重试也失败: {retry_error}")
        
        print(f"\n📈 恢复结果: {success_count}/{len(interrupted_tasks)} 个任务成功恢复")
        return success_count == len(interrupted_tasks)
        
    except Exception as e:
        print(f"❌ 恢复任务失败: {e}")
        return False

def resume_single_task(crawler, task_id):
    """恢复单个任务（使用新的两阶段恢复策略）"""
    print(f"🔄 恢复任务: {task_id}")
    
    try:
        # 获取任务信息
        task_info = crawler.db.get_task_info(task_id)
        if not task_info:
            print(f"❌ 任务 {task_id} 不存在")
            return False
        
        print(f"📋 任务信息: {task_info.keywords} (搜索阶段: {task_info.search_stage_status}, 问答阶段: {task_info.qa_stage_status})")
        
        # 如果任务已完成，跳过
        if task_info.search_stage_status == 'completed' and task_info.qa_stage_status == 'completed':
            print(f"✅ 任务 {task_id} 已完成，跳过")
            return True
        
        # 确定恢复策略
        strategy_info = crawler.db.determine_task_resume_strategy(task_id)
        strategy = strategy_info.get('strategy', 'unknown')
        print(f"📋 恢复策略: {strategy_info.get('message', strategy)}")
        
        # 根据策略恢复任务
        if strategy == 'resume_search':
            print("🔍 继续搜索阶段...")
            # 更新搜索阶段状态为进行中
            crawler.db.update_stage_status(task_id, 'search_stage_status', 'in_progress')
            result = crawler.resume_search_stage(task_id)
        elif strategy == 'resume_qa':
            print("💬 继续问答采集阶段...")
            # 更新问答阶段状态为进行中
            crawler.db.update_stage_status(task_id, 'qa_stage_status', 'in_progress')
            result = crawler.resume_qa_stage(task_id)
        elif strategy == 'completed':
            print("✅ 任务已完成，无需恢复")
            return True
        else:
            print(f"🔄 从头开始任务...")
            # 重置两个阶段状态
            crawler.db.update_stage_status(task_id, 'search_stage_status', 'in_progress')
            crawler.db.update_stage_status(task_id, 'qa_stage_status', 'not_started')
            result = crawler.resume_task(task_id)
        
        print(f"✅ 任务 {task_id} 恢复完成: {result}")
        return True
        
    except Exception as e:
        print(f"❌ 任务 {task_id} 恢复失败: {e}")
        
        # 尝试重置驱动后重试
        print("🔄 重置浏览器驱动后重试...")
        try:
            crawler.reset_driver()
            time.sleep(10)
            result = crawler.resume_task(task_id)
            print(f"✅ 重试成功: {result}")
            return True
            
        except Exception as retry_error:
            print(f"❌ 重试也失败: {retry_error}")
            return False

def resume_task_by_id(crawler, task_id):
    """根据任务ID恢复任务"""
    print(f"🔄 恢复任务ID: {task_id}")
    
    try:
        # 获取任务信息
        task_info = crawler.db.get_task_by_id(task_id)
        if not task_info:
            print(f"❌ 未找到任务ID: {task_id}")
            return False
        
        print(f"📋 任务信息: 关键词='{task_info.keywords}', 搜索阶段='{task_info.search_stage_status}', 问答阶段='{task_info.qa_stage_status}'")
        
        # 使用新的单任务恢复函数
        return resume_single_task(crawler, task_id)
        
    except Exception as e:
        print(f"❌ 恢复任务失败: {e}")
        return False

def resume_all_tasks(crawler):
    """恢复所有中断的任务（使用新的两阶段恢复策略）"""
    print("🔄 开始恢复所有中断任务...")
    
    # 先列出所有中断任务
    interrupted_tasks = list_unfinished_tasks(crawler)
    
    if not interrupted_tasks:
        return True
    
    print(f"\n🚀 开始恢复 {len(interrupted_tasks)} 个任务...")
    
    success_count = 0
    for i, task in enumerate(interrupted_tasks, 1):
        print(f"\n[{i}/{len(interrupted_tasks)}] 恢复任务: {task.task_id}")
        
        if resume_single_task(crawler, task.task_id):
            success_count += 1
            print(f"✅ 任务 {task.task_id} 恢复成功")
        else:
            print(f"❌ 任务 {task.task_id} 恢复失败")
    
    print(f"\n📈 恢复完成: {success_count}/{len(interrupted_tasks)} 个任务成功")
    return success_count == len(interrupted_tasks)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="知乎爬虫任务恢复脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python3 resume_tasks.py --list                    # 查看未完成任务
  python3 resume_tasks.py --all                     # 恢复所有任务
  python3 resume_tasks.py --keyword "博士回国"        # 恢复特定关键词
  python3 resume_tasks.py --task-id "task_123"      # 恢复特定任务ID
        """
    )
    
    parser.add_argument('--list', action='store_true', help='列出所有未完成的任务')
    parser.add_argument('--all', action='store_true', help='恢复所有未完成的任务')
    parser.add_argument('--keyword', type=str, help='恢复指定关键词的任务')
    parser.add_argument('--task-id', type=str, help='恢复指定ID的任务')
    parser.add_argument('--start-date', type=str, default='2024-01-01', help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, default='2024-12-31', help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--headless', action='store_true', default=True, help='无头模式运行 (默认开启)')
    
    args = parser.parse_args()
    
    # 检查参数
    if not any([args.list, args.all, args.keyword, args.task_id]):
        parser.print_help()
        return
    
    print_banner()
    
    # 初始化爬虫
    print("🚀 初始化爬虫...")
    crawler = None
    
    try:
        crawler = PostgresZhihuCrawler(headless=args.headless)
        print("✅ 爬虫初始化完成")
        
        # 检查系统状态
        if not check_system_status(crawler):
            print("❌ 系统状态检查失败，请解决问题后重试")
            return
        
        # 执行相应操作
        if args.list:
            list_unfinished_tasks(crawler)
            
        elif args.all:
            resume_all_tasks(crawler)
            
        elif args.keyword:
            resume_task_by_keyword(crawler, args.keyword, args.start_date, args.end_date)
            
        elif args.task_id:
            resume_task_by_id(crawler, args.task_id)
        
        print("\n🎉 脚本执行完成")
        
    except KeyboardInterrupt:
        print("\n⚠️  用户中断操作")
        
    except Exception as e:
        print(f"\n❌ 脚本执行出错: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        if crawler:
            try:
                crawler.close()
                print("✅ 爬虫已关闭")
            except:
                pass

if __name__ == "__main__":
    main()