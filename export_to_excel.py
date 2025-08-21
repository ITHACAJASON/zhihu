#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知乎爬虫数据导出脚本
将PostgreSQL数据库中的数据表导出为Excel文件
"""

import os
import sys
import json
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
import psycopg2
from config import ZhihuConfig
import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/export.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

class DataExporter:
    """数据导出器"""
    
    def __init__(self, config: Dict = None):
        """初始化导出器"""
        self.config = config or ZhihuConfig.POSTGRES_CONFIG
        self.output_dir = "exports"
        self.ensure_output_dir()
        
    def ensure_output_dir(self):
        """确保输出目录存在"""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            logger.info(f"创建输出目录: {self.output_dir}")
    
    def get_connection(self):
        """获取数据库连接"""
        try:
            conn = psycopg2.connect(
                host=self.config['host'],
                port=self.config['port'],
                database=self.config['database'],
                user=self.config['user'],
                password=self.config['password']
            )
            return conn
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            raise
    
    def export_table_to_excel(self, table_name: str, query: str = None, filename: str = None) -> str:
        """导出单个表到Excel文件"""
        try:
            # 默认查询语句
            if query is None:
                query = f"SELECT * FROM {table_name}"
            
            # 默认文件名
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{table_name}_{timestamp}.xlsx"
            
            filepath = os.path.join(self.output_dir, filename)
            
            # 连接数据库并查询数据
            with self.get_connection() as conn:
                logger.info(f"开始导出表 {table_name}...")
                
                # 使用pandas读取数据
                df = pd.read_sql_query(query, conn)
                
                if df.empty:
                    logger.warning(f"表 {table_name} 没有数据")
                    return None
                
                # 处理特殊字段
                df = self._process_dataframe(df, table_name)
                
                # 导出到Excel
                with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name=table_name, index=False)
                    
                    # 调整列宽
                    worksheet = writer.sheets[table_name]
                    for column in df.columns:
                        column_length = max(df[column].astype(str).map(len).max(), len(column))
                        col_letter = worksheet.cell(row=1, column=df.columns.get_loc(column) + 1).column_letter
                        worksheet.column_dimensions[col_letter].width = min(column_length + 2, 50)
                
                logger.info(f"✓ 表 {table_name} 导出完成: {filepath} ({len(df)} 行数据)")
                return filepath
                
        except Exception as e:
            logger.error(f"导出表 {table_name} 失败: {e}")
            raise
    
    def _process_dataframe(self, df: pd.DataFrame, table_name: str) -> pd.DataFrame:
        """处理DataFrame中的特殊字段"""
        # 处理JSON字段
        if 'tags' in df.columns:
            df['tags'] = df['tags'].apply(lambda x: ', '.join(x) if isinstance(x, list) else str(x) if x else '')
        
        # 处理时间字段
        time_columns = ['created_at', 'updated_at', 'crawl_time', 'create_time', 'update_time', 'publish_time']
        for col in time_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        # 处理布尔字段
        bool_columns = ['processed', 'is_author']
        for col in bool_columns:
            if col in df.columns:
                df[col] = df[col].map({True: '是', False: '否', None: ''})
        
        # 处理长文本字段（截断显示）
        text_columns = ['content', 'preview_content']
        for col in text_columns:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: str(x)[:500] + '...' if x and len(str(x)) > 500 else str(x) if x else '')
        
        return df
    
    def export_all_tables(self) -> Dict[str, str]:
        """导出所有表到Excel文件"""
        tables = {
            'task_info': '任务信息表',
            'search_results': '搜索结果表', 
            'questions': '问题表',
            'answers': '答案表'
        }
        
        exported_files = {}
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for table_name, description in tables.items():
            try:
                filename = f"{table_name}_{timestamp}.xlsx"
                filepath = self.export_table_to_excel(table_name, filename=filename)
                if filepath:
                    exported_files[table_name] = filepath
            except Exception as e:
                logger.error(f"导出 {description} 失败: {e}")
        
        return exported_files
    
    def export_combined_excel(self, filename: str = None) -> str:
        """导出所有表到一个Excel文件的不同工作表"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"zhihu_data_combined_{timestamp}.xlsx"
        
        filepath = os.path.join(self.output_dir, filename)
        
        tables = {
            'task_info': '任务信息',
            'search_results': '搜索结果', 
            'questions': '问题数据',
            'answers': '答案数据'
        }
        
        try:
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                total_rows = 0
                
                for table_name, sheet_name in tables.items():
                    try:
                        with self.get_connection() as conn:
                            df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
                            
                            if df.empty:
                                logger.warning(f"表 {table_name} 没有数据，跳过")
                                continue
                            
                            # 处理特殊字段
                            df = self._process_dataframe(df, table_name)
                            
                            # 写入工作表
                            df.to_excel(writer, sheet_name=sheet_name, index=False)
                            
                            # 调整列宽
                            worksheet = writer.sheets[sheet_name]
                            for column in df.columns:
                                column_length = max(df[column].astype(str).map(len).max(), len(column))
                                col_letter = worksheet.cell(row=1, column=df.columns.get_loc(column) + 1).column_letter
                                worksheet.column_dimensions[col_letter].width = min(column_length + 2, 50)
                            
                            total_rows += len(df)
                            logger.info(f"✓ {sheet_name}: {len(df)} 行数据")
                            
                    except Exception as e:
                        logger.error(f"处理表 {table_name} 时出错: {e}")
                        continue
                
                logger.info(f"✓ 合并导出完成: {filepath} (总计 {total_rows} 行数据)")
                return filepath
                
        except Exception as e:
            logger.error(f"合并导出失败: {e}")
            raise
    
    def export_by_task(self, task_id: str = None, keywords: str = None) -> str:
        """按任务导出数据"""
        if not task_id and not keywords:
            raise ValueError("必须提供 task_id 或 keywords")
        
        # 构建查询条件
        if task_id:
            condition = f"task_id = '{task_id}'"
            identifier = task_id[:8]
        else:
            condition = f"keywords LIKE '%{keywords}%'"
            identifier = keywords.replace(',', '_').replace(' ', '_')
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"zhihu_task_{identifier}_{timestamp}.xlsx"
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                # 导出任务信息
                with self.get_connection() as conn:
                    task_df = pd.read_sql_query(f"SELECT * FROM task_info WHERE {condition}", conn)
                    if not task_df.empty:
                        task_df = self._process_dataframe(task_df, 'task_info')
                        task_df.to_excel(writer, sheet_name='任务信息', index=False)
                        
                        # 获取实际的task_id列表
                        task_ids = task_df['task_id'].tolist()
                        task_ids_str = "','".join(task_ids)
                        
                        # 导出相关的搜索结果
                        search_df = pd.read_sql_query(f"SELECT * FROM search_results WHERE task_id IN ('{task_ids_str}')", conn)
                        if not search_df.empty:
                            search_df = self._process_dataframe(search_df, 'search_results')
                            search_df.to_excel(writer, sheet_name='搜索结果', index=False)
                        
                        # 导出相关的问题
                        questions_df = pd.read_sql_query(f"SELECT * FROM questions WHERE task_id IN ('{task_ids_str}')", conn)
                        if not questions_df.empty:
                            questions_df = self._process_dataframe(questions_df, 'questions')
                            questions_df.to_excel(writer, sheet_name='问题数据', index=False)
                        
                        # 导出相关的答案
                        answers_df = pd.read_sql_query(f"SELECT * FROM answers WHERE task_id IN ('{task_ids_str}')", conn)
                        if not answers_df.empty:
                            answers_df = self._process_dataframe(answers_df, 'answers')
                            answers_df.to_excel(writer, sheet_name='答案数据', index=False)
                        
                        # 调整所有工作表的列宽
                        for sheet_name in writer.sheets:
                            worksheet = writer.sheets[sheet_name]
                            for column in worksheet.columns:
                                max_length = 0
                                column_letter = column[0].column_letter
                                for cell in column:
                                    try:
                                        if len(str(cell.value)) > max_length:
                                            max_length = len(str(cell.value))
                                    except:
                                        pass
                                adjusted_width = min(max_length + 2, 50)
                                worksheet.column_dimensions[column_letter].width = adjusted_width
                        
                        logger.info(f"✓ 任务数据导出完成: {filepath}")
                        return filepath
                    else:
                        logger.warning(f"未找到匹配的任务: {condition}")
                        return None
                        
        except Exception as e:
            logger.error(f"按任务导出失败: {e}")
            raise
    
    def get_export_summary(self) -> Dict:
        """获取数据库表的统计信息"""
        summary = {}
        tables = ['task_info', 'search_results', 'questions', 'answers']
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                for table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    summary[table] = count
                
                # 获取任务列表
                cursor.execute("SELECT task_id, keywords, created_at FROM task_info ORDER BY created_at DESC")
                tasks = cursor.fetchall()
                summary['tasks'] = [{
                    'task_id': task[0],
                    'keywords': task[1],
                    'created_at': task[2].strftime('%Y-%m-%d %H:%M:%S') if task[2] else ''
                } for task in tasks]
                
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            raise
        
        return summary

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='知乎爬虫数据导出工具')
    parser.add_argument('--mode', choices=['all', 'combined', 'task', 'table', 'summary'], 
                       default='combined', help='导出模式')
    parser.add_argument('--table', help='指定要导出的表名')
    parser.add_argument('--task-id', help='指定任务ID')
    parser.add_argument('--keywords', help='指定关键词')
    parser.add_argument('--output', help='输出文件名')
    
    args = parser.parse_args()
    
    # 确保日志目录存在
    os.makedirs('logs', exist_ok=True)
    
    exporter = DataExporter()
    
    try:
        if args.mode == 'summary':
            # 显示统计信息
            summary = exporter.get_export_summary()
            print("\n=== 数据库统计信息 ===")
            print(f"任务信息表: {summary['task_info']} 条记录")
            print(f"搜索结果表: {summary['search_results']} 条记录")
            print(f"问题表: {summary['questions']} 条记录")
            print(f"答案表: {summary['answers']} 条记录")
            
            if summary['tasks']:
                print("\n=== 任务列表 ===")
                for task in summary['tasks']:
                    print(f"ID: {task['task_id'][:8]}... | 关键词: {task['keywords']} | 创建时间: {task['created_at']}")
            
        elif args.mode == 'all':
            # 导出所有表为单独文件
            files = exporter.export_all_tables()
            print(f"\n✓ 导出完成，共 {len(files)} 个文件:")
            for table, filepath in files.items():
                print(f"  - {table}: {filepath}")
                
        elif args.mode == 'combined':
            # 导出所有表到一个文件
            filepath = exporter.export_combined_excel(args.output)
            print(f"\n✓ 合并导出完成: {filepath}")
            
        elif args.mode == 'task':
            # 按任务导出
            if not args.task_id and not args.keywords:
                print("错误: 任务导出模式需要指定 --task-id 或 --keywords")
                return
            
            filepath = exporter.export_by_task(args.task_id, args.keywords)
            if filepath:
                print(f"\n✓ 任务数据导出完成: {filepath}")
            else:
                print("\n未找到匹配的任务数据")
                
        elif args.mode == 'table':
            # 导出指定表
            if not args.table:
                print("错误: 表导出模式需要指定 --table")
                return
            
            filepath = exporter.export_table_to_excel(args.table, filename=args.output)
            if filepath:
                print(f"\n✓ 表导出完成: {filepath}")
            
    except Exception as e:
        logger.error(f"导出过程中出现错误: {e}")
        print(f"\n❌ 导出失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()