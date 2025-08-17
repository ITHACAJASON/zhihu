#!/usr/bin/env python3
"""数据库迁移脚本：从SQLite迁移到PostgreSQL"""

import sqlite3
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional
import logging
from postgres_models import PostgreSQLManager, TaskInfo, SearchResult, Question, Answer, Comment
from config import ZhihuConfig


class DatabaseMigrator:
    """数据库迁移器"""
    
    def __init__(self, sqlite_path: str = None, postgres_config: Dict = None):
        self.sqlite_path = sqlite_path or ZhihuConfig.DATABASE_PATH
        self.postgres_manager = PostgreSQLManager(postgres_config)
        self.logger = logging.getLogger(__name__)
        
        # 配置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def migrate_all(self) -> bool:
        """执行完整的数据迁移"""
        try:
            self.logger.info("开始数据库迁移...")
            
            # 检查SQLite数据库是否存在
            if not self._check_sqlite_exists():
                self.logger.warning("SQLite数据库不存在，跳过迁移")
                return True
            
            # 迁移任务信息
            task_mapping = self._migrate_tasks()
            
            # 迁移问题数据
            self._migrate_questions(task_mapping)
            
            # 迁移答案数据
            self._migrate_answers(task_mapping)
            
            # 迁移评论数据
            self._migrate_comments(task_mapping)
            
            self.logger.info("数据库迁移完成")
            return True
            
        except Exception as e:
            self.logger.error(f"数据库迁移失败: {e}")
            return False
    
    def _check_sqlite_exists(self) -> bool:
        """检查SQLite数据库是否存在"""
        try:
            with sqlite3.connect(self.sqlite_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()
                return len(tables) > 0
        except Exception:
            return False
    
    def _migrate_tasks(self) -> Dict[str, str]:
        """迁移任务信息，返回旧任务ID到新任务ID的映射"""
        self.logger.info("迁移任务信息...")
        task_mapping = {}
        
        try:
            with sqlite3.connect(self.sqlite_path) as conn:
                cursor = conn.cursor()
                
                # 检查是否存在search_records表
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='search_records'")
                if not cursor.fetchone():
                    # 如果没有search_records表，创建默认任务
                    default_task_id = self.postgres_manager.create_task(
                        keywords="迁移数据",
                        start_date="2015-01-01",
                        end_date="2025-12-31"
                    )
                    task_mapping['default'] = default_task_id
                    self.logger.info(f"创建默认任务: {default_task_id}")
                    return task_mapping
                
                # 迁移search_records表中的任务
                cursor.execute('''
                    SELECT id, keyword, start_date, end_date, total_questions, 
                           total_answers, total_comments, search_time, status
                    FROM search_records
                ''')
                
                for row in cursor.fetchall():
                    old_id, keyword, start_date, end_date, total_q, total_a, total_c, search_time, status = row
                    
                    # 创建新任务
                    new_task_id = self.postgres_manager.create_task(
                        keywords=keyword or "未知关键词",
                        start_date=start_date or "2015-01-01",
                        end_date=end_date or "2025-12-31"
                    )
                    
                    # 更新任务状态
                    pg_status = 'completed' if status == 'completed' else 'running'
                    self.postgres_manager.update_task_status(
                        task_id=new_task_id,
                        status=pg_status,
                        total_questions=total_q or 0,
                        total_answers=total_a or 0,
                        total_comments=total_c or 0
                    )
                    
                    task_mapping[str(old_id)] = new_task_id
                    self.logger.info(f"迁移任务 {old_id} -> {new_task_id}")
                
                # 如果没有任务记录，创建默认任务
                if not task_mapping:
                    default_task_id = self.postgres_manager.create_task(
                        keywords="迁移数据",
                        start_date="2015-01-01",
                        end_date="2025-12-31"
                    )
                    task_mapping['default'] = default_task_id
                    self.logger.info(f"创建默认任务: {default_task_id}")
                
        except Exception as e:
            self.logger.error(f"迁移任务信息失败: {e}")
            # 创建默认任务作为后备
            default_task_id = self.postgres_manager.create_task(
                keywords="迁移数据",
                start_date="2015-01-01",
                end_date="2025-12-31"
            )
            task_mapping['default'] = default_task_id
        
        return task_mapping
    
    def _migrate_questions(self, task_mapping: Dict[str, str]):
        """迁移问题数据"""
        self.logger.info("迁移问题数据...")
        
        try:
            with sqlite3.connect(self.sqlite_path) as conn:
                cursor = conn.cursor()
                
                # 检查questions表是否存在
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='questions'")
                if not cursor.fetchone():
                    self.logger.warning("questions表不存在，跳过问题数据迁移")
                    return
                
                cursor.execute('''
                    SELECT question_id, title, content, author, create_time,
                           follow_count, view_count, answer_count, url, tags, crawl_time
                    FROM questions
                ''')
                
                migrated_count = 0
                default_task_id = task_mapping.get('default', list(task_mapping.values())[0] if task_mapping else None)
                
                if not default_task_id:
                    self.logger.error("没有可用的任务ID，跳过问题数据迁移")
                    return
                
                for row in cursor.fetchall():
                    question_id, title, content, author, create_time, follow_count, view_count, answer_count, url, tags, crawl_time = row
                    
                    # 解析tags
                    try:
                        tags_list = json.loads(tags) if tags else []
                    except:
                        tags_list = []
                    
                    question = Question(
                        question_id=question_id,
                        task_id=default_task_id,
                        title=title or "无标题",
                        content=content or "",
                        author=author or "",
                        create_time=create_time or "",
                        follow_count=follow_count or 0,
                        view_count=view_count or 0,
                        answer_count=answer_count or 0,
                        url=url or "",
                        tags=tags_list,
                        processed=True,  # 迁移的数据标记为已处理
                        crawl_time=crawl_time or datetime.now().isoformat()
                    )
                    
                    if self.postgres_manager.save_question(question):
                        migrated_count += 1
                
                self.logger.info(f"成功迁移 {migrated_count} 个问题")
                
        except Exception as e:
            self.logger.error(f"迁移问题数据失败: {e}")
    
    def _migrate_answers(self, task_mapping: Dict[str, str]):
        """迁移答案数据"""
        self.logger.info("迁移答案数据...")
        
        try:
            with sqlite3.connect(self.sqlite_path) as conn:
                cursor = conn.cursor()
                
                # 检查answers表是否存在
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='answers'")
                if not cursor.fetchone():
                    self.logger.warning("answers表不存在，跳过答案数据迁移")
                    return
                
                cursor.execute('''
                    SELECT answer_id, question_id, content, author, author_url,
                           create_time, update_time, vote_count, comment_count,
                           url, is_author, crawl_time
                    FROM answers
                ''')
                
                migrated_count = 0
                default_task_id = task_mapping.get('default', list(task_mapping.values())[0] if task_mapping else None)
                
                if not default_task_id:
                    self.logger.error("没有可用的任务ID，跳过答案数据迁移")
                    return
                
                for row in cursor.fetchall():
                    answer_id, question_id, content, author, author_url, create_time, update_time, vote_count, comment_count, url, is_author, crawl_time = row
                    
                    answer = Answer(
                        answer_id=answer_id,
                        question_id=question_id,
                        task_id=default_task_id,
                        content=content or "",
                        author=author or "",
                        author_url=author_url or "",
                        create_time=create_time or "",
                        update_time=update_time or "",
                        vote_count=vote_count or 0,
                        comment_count=comment_count or 0,
                        url=url or "",
                        is_author=bool(is_author),
                        processed=True,  # 迁移的数据标记为已处理
                        crawl_time=crawl_time or datetime.now().isoformat()
                    )
                    
                    if self.postgres_manager.save_answer(answer):
                        migrated_count += 1
                
                self.logger.info(f"成功迁移 {migrated_count} 个答案")
                
        except Exception as e:
            self.logger.error(f"迁移答案数据失败: {e}")
    
    def _migrate_comments(self, task_mapping: Dict[str, str]):
        """迁移评论数据"""
        self.logger.info("迁移评论数据...")
        
        try:
            with sqlite3.connect(self.sqlite_path) as conn:
                cursor = conn.cursor()
                
                # 检查comments表是否存在
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='comments'")
                if not cursor.fetchone():
                    self.logger.warning("comments表不存在，跳过评论数据迁移")
                    return
                
                cursor.execute('''
                    SELECT comment_id, answer_id, content, author, author_url,
                           create_time, vote_count, reply_to, crawl_time
                    FROM comments
                ''')
                
                comments_batch = []
                default_task_id = task_mapping.get('default', list(task_mapping.values())[0] if task_mapping else None)
                
                if not default_task_id:
                    self.logger.error("没有可用的任务ID，跳过评论数据迁移")
                    return
                
                for row in cursor.fetchall():
                    comment_id, answer_id, content, author, author_url, create_time, vote_count, reply_to, crawl_time = row
                    
                    comment = Comment(
                        comment_id=comment_id,
                        answer_id=answer_id,
                        task_id=default_task_id,
                        content=content or "",
                        author=author or "",
                        author_url=author_url or "",
                        create_time=create_time or "",
                        vote_count=vote_count or 0,
                        reply_to=reply_to or "",
                        crawl_time=crawl_time or datetime.now().isoformat()
                    )
                    
                    comments_batch.append(comment)
                    
                    # 批量保存评论（每100条）
                    if len(comments_batch) >= 100:
                        self.postgres_manager.save_comments(comments_batch)
                        comments_batch = []
                
                # 保存剩余的评论
                if comments_batch:
                    self.postgres_manager.save_comments(comments_batch)
                
                self.logger.info(f"成功迁移评论数据")
                
        except Exception as e:
            self.logger.error(f"迁移评论数据失败: {e}")
    
    def create_backup(self) -> str:
        """创建SQLite数据库备份"""
        import shutil
        from datetime import datetime
        
        backup_path = f"{self.sqlite_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        try:
            shutil.copy2(self.sqlite_path, backup_path)
            self.logger.info(f"创建备份: {backup_path}")
            return backup_path
        except Exception as e:
            self.logger.error(f"创建备份失败: {e}")
            return ""


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='数据库迁移工具')
    parser.add_argument('--sqlite-path', default=ZhihuConfig.DATABASE_PATH, help='SQLite数据库路径')
    parser.add_argument('--backup', action='store_true', help='迁移前创建备份')
    parser.add_argument('--postgres-host', default='localhost', help='PostgreSQL主机')
    parser.add_argument('--postgres-port', type=int, default=5432, help='PostgreSQL端口')
    parser.add_argument('--postgres-db', default='zhihu_crawler', help='PostgreSQL数据库名')
    parser.add_argument('--postgres-user', default='postgres', help='PostgreSQL用户名')
    parser.add_argument('--postgres-password', default='password', help='PostgreSQL密码')
    
    args = parser.parse_args()
    
    # 构建PostgreSQL配置
    postgres_config = {
        'host': args.postgres_host,
        'port': args.postgres_port,
        'database': args.postgres_db,
        'user': args.postgres_user,
        'password': args.postgres_password
    }
    
    # 创建迁移器
    migrator = DatabaseMigrator(args.sqlite_path, postgres_config)
    
    # 创建备份
    if args.backup:
        migrator.create_backup()
    
    # 执行迁移
    success = migrator.migrate_all()
    
    if success:
        print("数据库迁移成功完成！")
    else:
        print("数据库迁移失败，请检查日志")
        exit(1)


if __name__ == '__main__':
    main()