#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库迁移脚本：删除task_info表中的status和current_stage列
"""

import psycopg2
from postgres_models import PostgreSQLManager
from config import ZhihuConfig
import logging

def remove_legacy_columns():
    """删除task_info表中的status和current_stage列"""
    
    # 设置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    
    try:
        # 创建数据库管理器
        config = ZhihuConfig()
        db_config = config.POSTGRES_CONFIG
        db = PostgreSQLManager(db_config)
        
        logger.info("开始删除task_info表中的status和current_stage列...")
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 检查列是否存在
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'task_info' 
                AND column_name IN ('status', 'current_stage')
            """)
            
            existing_columns = [row[0] for row in cursor.fetchall()]
            logger.info(f"找到需要删除的列: {existing_columns}")
            
            # 删除status列
            if 'status' in existing_columns:
                logger.info("删除status列...")
                cursor.execute("ALTER TABLE task_info DROP COLUMN status")
                logger.info("status列删除成功")
            else:
                logger.info("status列不存在，跳过")
            
            # 删除current_stage列
            if 'current_stage' in existing_columns:
                logger.info("删除current_stage列...")
                cursor.execute("ALTER TABLE task_info DROP COLUMN current_stage")
                logger.info("current_stage列删除成功")
            else:
                logger.info("current_stage列不存在，跳过")
            
            conn.commit()
            logger.info("数据库迁移完成！")
            
            # 验证表结构
            cursor.execute("""
                SELECT column_name, data_type, column_default
                FROM information_schema.columns 
                WHERE table_name = 'task_info'
                ORDER BY ordinal_position
            """)
            
            logger.info("当前task_info表结构:")
            for row in cursor.fetchall():
                logger.info(f"  {row[0]} ({row[1]}) - 默认值: {row[2]}")
                
    except Exception as e:
        logger.error(f"数据库迁移失败: {e}")
        raise

if __name__ == "__main__":
    remove_legacy_columns()