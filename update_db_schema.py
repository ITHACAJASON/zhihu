#!/usr/bin/env python3
from postgres_models import PostgreSQLManager

def update_schema():
    """更新数据库表结构，添加新的状态字段"""
    db = PostgreSQLManager()
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 添加search_stage_status字段
            cursor.execute("""
                ALTER TABLE task_info 
                ADD COLUMN IF NOT EXISTS search_stage_status VARCHAR(20) DEFAULT 'not_started'
            """)
            
            # 添加qa_stage_status字段
            cursor.execute("""
                ALTER TABLE task_info 
                ADD COLUMN IF NOT EXISTS qa_stage_status VARCHAR(20) DEFAULT 'not_started'
            """)
            
            conn.commit()
            print("✅ 数据库表结构更新完成")
            print("   - 添加了 search_stage_status 字段")
            print("   - 添加了 qa_stage_status 字段")
            
    except Exception as e:
        print(f"❌ 数据库表结构更新失败: {e}")
        return False
    
    return True

if __name__ == "__main__":
    update_schema()