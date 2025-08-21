#!/usr/bin/env python3
from postgres_models import PostgreSQLManager
import uuid

def create_stage_test_tasks():
    """创建不同阶段状态的测试任务"""
    db = PostgreSQLManager()
    
    # 测试任务1：搜索阶段进行中
    task1_id = str(uuid.uuid4())
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO task_info 
            (task_id, keywords, start_date, end_date, status, current_stage, 
             search_stage_status, qa_stage_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (task1_id, '测试搜索阶段', '2024-01-01', '2024-12-31', 
              'running', 'search', 'in_progress', 'not_started'))
        conn.commit()
    
    print(f"✅ 创建测试任务1: {task1_id} (搜索阶段进行中)")
    
    # 测试任务2：搜索完成，问答阶段进行中
    task2_id = str(uuid.uuid4())
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO task_info 
            (task_id, keywords, start_date, end_date, status, current_stage, 
             search_stage_status, qa_stage_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (task2_id, '测试问答阶段', '2024-01-01', '2024-12-31', 
              'running', 'questions', 'completed', 'in_progress'))
        conn.commit()
    
    print(f"✅ 创建测试任务2: {task2_id} (问答阶段进行中)")
    
    # 测试任务3：两个阶段都未开始
    task3_id = str(uuid.uuid4())
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO task_info 
            (task_id, keywords, start_date, end_date, status, current_stage, 
             search_stage_status, qa_stage_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (task3_id, '测试重新开始', '2024-01-01', '2024-12-31', 
              'running', 'search', 'not_started', 'not_started'))
        conn.commit()
    
    print(f"✅ 创建测试任务3: {task3_id} (两阶段未开始)")
    
    return [task1_id, task2_id, task3_id]

def test_recovery_strategy():
    """测试恢复策略判断"""
    db = PostgreSQLManager()
    
    task_ids = create_stage_test_tasks()
    
    print("\n🔍 测试恢复策略判断:")
    for task_id in task_ids:
        strategy_info = db.determine_task_resume_strategy(task_id)
        task_info = db.get_task_info(task_id)
        print(f"\n任务: {task_info.keywords}")
        print(f"  搜索阶段: {task_info.search_stage_status}")
        print(f"  问答阶段: {task_info.qa_stage_status}")
        print(f"  恢复策略: {strategy_info}")
    
    return task_ids

if __name__ == "__main__":
    test_recovery_strategy()