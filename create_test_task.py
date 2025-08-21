#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建测试任务脚本
用于演示任务恢复功能
"""

import sys
import argparse
from postgres_models import PostgreSQLManager, TaskInfo
from datetime import datetime

def create_test_task(keywords: str, search_stage: str = 'not_started', qa_stage: str = 'not_started'):
    """
    创建一个测试任务
    
    Args:
        keywords: 关键词
        search_stage: 搜索阶段状态 (not_started, in_progress, completed)
        qa_stage: 问答阶段状态 (not_started, in_progress, completed)
    """
    try:
        db = PostgreSQLManager()
        
        # 创建任务
        task_id = db.create_task(
            keywords=keywords,
            start_date="2024-01-01",
            end_date="2024-12-31"
        )
        
        # 更新任务状态
        if search_stage != 'not_started' or qa_stage != 'not_started':
            db.update_task_status(
                task_id=task_id,
                search_stage_status=search_stage,
                qa_stage_status=qa_stage,
                total_questions=10,
                processed_questions=5,
                total_answers=50,
                processed_answers=25
            )
        
        print(f"✅ 创建测试任务成功:")
        print(f"   任务ID: {task_id}")
        print(f"   关键词: {keywords}")
        print(f"   搜索阶段: {search_stage}")
        print(f"   问答阶段: {qa_stage}")
        
        return task_id
        
    except Exception as e:
        print(f"❌ 创建测试任务失败: {e}")
        return None

def update_task_status(task_id: str, search_stage: str = None, qa_stage: str = None):
    """
    更新任务状态
    
    Args:
        task_id: 任务ID
        search_stage: 搜索阶段状态
        qa_stage: 问答阶段状态
    """
    try:
        db = PostgreSQLManager()
        
        # 检查任务是否存在
        task_info = db.get_task_info(task_id)
        if not task_info:
            print(f"❌ 任务不存在: {task_id}")
            return False
        
        # 更新状态
        update_params = {'task_id': task_id}
        if search_stage:
            update_params['search_stage_status'] = search_stage
        if qa_stage:
            update_params['qa_stage_status'] = qa_stage
            
        db.update_task_status(**update_params)
        
        print(f"✅ 任务状态更新成功:")
        print(f"   任务ID: {task_id}")
        print(f"   关键词: {task_info.keywords}")
        if search_stage:
            print(f"   搜索阶段: {task_info.search_stage_status} -> {search_stage}")
        if qa_stage:
            print(f"   问答阶段: {task_info.qa_stage_status} -> {qa_stage}")
        
        return True
        
    except Exception as e:
        print(f"❌ 更新任务状态失败: {e}")
        return False

def list_all_tasks():
    """
    列出所有任务
    """
    try:
        db = PostgreSQLManager()
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT task_id, keywords, search_stage_status, qa_stage_status, created_at
                FROM task_info 
                ORDER BY created_at DESC
            ''')
            
            tasks = cursor.fetchall()
            
        if not tasks:
            print("📋 没有找到任何任务")
            return
        
        print(f"📋 找到 {len(tasks)} 个任务:")
        print("-" * 100)
        print(f"{'任务ID':<40} {'关键词':<20} {'搜索阶段':<12} {'问答阶段':<12} {'创建时间':<20}")
        print("-" * 100)
        
        for task in tasks:
            task_id, keywords, search_stage, qa_stage, created_at = task
            print(f"{task_id:<40} {keywords:<20} {search_stage:<12} {qa_stage:<12} {str(created_at)[:19]:<20}")
        
        print("-" * 100)
        
    except Exception as e:
        print(f"❌ 列出任务失败: {e}")

def main():
    parser = argparse.ArgumentParser(description='创建和管理测试任务')
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 创建任务命令
    create_parser = subparsers.add_parser('create', help='创建测试任务')
    create_parser.add_argument('keywords', help='关键词')
    create_parser.add_argument('--search-stage', default='not_started', 
                              choices=['not_started', 'in_progress', 'completed'],
                              help='搜索阶段状态 (默认: not_started)')
    create_parser.add_argument('--qa-stage', default='not_started',
                              choices=['not_started', 'in_progress', 'completed'],
                              help='问答阶段状态 (默认: not_started)')
    
    # 更新状态命令
    update_parser = subparsers.add_parser('update', help='更新任务状态')
    update_parser.add_argument('task_id', help='任务ID')
    update_parser.add_argument('--search-stage', choices=['not_started', 'in_progress', 'completed'],
                              help='搜索阶段状态')
    update_parser.add_argument('--qa-stage', choices=['not_started', 'in_progress', 'completed'],
                              help='问答阶段状态')
    
    # 列出任务命令
    list_parser = subparsers.add_parser('list', help='列出所有任务')
    
    # 创建演示场景命令
    demo_parser = subparsers.add_parser('demo', help='创建演示场景')
    
    args = parser.parse_args()
    
    if args.command == 'create':
        create_test_task(args.keywords, getattr(args, 'search_stage', 'not_started'), getattr(args, 'qa_stage', 'not_started'))
    elif args.command == 'update':
        update_task_status(args.task_id, getattr(args, 'search_stage', None), getattr(args, 'qa_stage', None))
    elif args.command == 'list':
        list_all_tasks()
    elif args.command == 'demo':
        print("🎭 创建演示场景...")
        print()
        
        # 创建几个不同状态的测试任务
        scenarios = [
            ("Python编程", "in_progress", "not_started"),
            ("机器学习", "completed", "in_progress"),
            ("数据科学", "completed", "completed"),
            ("人工智能", "in_progress", "not_started")
        ]
        
        for keywords, search_stage, qa_stage in scenarios:
            task_id = create_test_task(keywords, search_stage, qa_stage)
            if task_id:
                print()
        
        print("\n🎉 演示场景创建完成！")
        print("\n现在你可以使用以下命令测试任务恢复功能:")
        print("  python3 resume_tasks.py --list")
        print("  python3 resume_tasks.py --resume-all")
        print("  python3 resume_tasks.py --keyword 'Python编程'")
        
    else:
        parser.print_help()

if __name__ == '__main__':
    main()