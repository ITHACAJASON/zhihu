#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新answers表结构，添加content_hash字段
"""

import psycopg2
from config import ZhihuConfig
import logging

def update_answers_table():
    """更新answers表，添加content_hash字段"""
    config = ZhihuConfig()
    
    try:
        # 连接数据库
        conn = psycopg2.connect(
            host=config.POSTGRES_CONFIG['host'],
            port=config.POSTGRES_CONFIG['port'],
            database=config.POSTGRES_CONFIG['database'],
            user=config.POSTGRES_CONFIG['user'],
            password=config.POSTGRES_CONFIG['password']
        )
        
        cursor = conn.cursor()
        
        # 检查content_hash字段是否存在
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='answers' AND column_name='content_hash'
        """)
        
        result = cursor.fetchone()
        
        if result is None:
            print("添加content_hash字段到answers表...")
            cursor.execute("""
                ALTER TABLE answers 
                ADD COLUMN content_hash VARCHAR(64)
            """)
            conn.commit()
            print("content_hash字段添加成功！")
        else:
            print("content_hash字段已存在，无需添加。")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"更新数据库表失败: {e}")
        return False
    
    return True

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    success = update_answers_table()
    if success:
        print("数据库表更新完成！")
    else:
        print("数据库表更新失败！")