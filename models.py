"""
知乎爬虫数据模型
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from config import ZhihuConfig


@dataclass
class Question:
    """问题数据模型"""
    question_id: str
    title: str
    content: str = ""
    author: str = ""
    create_time: str = ""
    follow_count: int = 0
    view_count: int = 0
    answer_count: int = 0
    url: str = ""
    tags: List[str] = None
    crawl_time: str = ""
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if not self.crawl_time:
            self.crawl_time = datetime.now().isoformat()


@dataclass
class Answer:
    """答案数据模型"""
    answer_id: str
    question_id: str
    content: str
    author: str = ""
    author_url: str = ""
    create_time: str = ""
    update_time: str = ""
    vote_count: int = 0
    comment_count: int = 0
    url: str = ""
    is_author: bool = False
    crawl_time: str = ""
    
    def __post_init__(self):
        if not self.crawl_time:
            self.crawl_time = datetime.now().isoformat()


@dataclass
class Comment:
    """评论数据模型"""
    comment_id: str
    answer_id: str
    content: str
    author: str = ""
    author_url: str = ""
    create_time: str = ""
    vote_count: int = 0
    reply_to: str = ""
    crawl_time: str = ""
    
    def __post_init__(self):
        if not self.crawl_time:
            self.crawl_time = datetime.now().isoformat()


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or ZhihuConfig.DATABASE_PATH
        self.init_database()
    
    def init_database(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 创建问题表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS questions (
                    question_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT,
                    author TEXT,
                    create_time TEXT,
                    follow_count INTEGER DEFAULT 0,
                    view_count INTEGER DEFAULT 0,
                    answer_count INTEGER DEFAULT 0,
                    url TEXT,
                    tags TEXT,
                    crawl_time TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建答案表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS answers (
                    answer_id TEXT PRIMARY KEY,
                    question_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    author TEXT,
                    author_url TEXT,
                    create_time TEXT,
                    update_time TEXT,
                    vote_count INTEGER DEFAULT 0,
                    comment_count INTEGER DEFAULT 0,
                    url TEXT,
                    is_author BOOLEAN DEFAULT FALSE,
                    crawl_time TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (question_id) REFERENCES questions (question_id)
                )
            ''')
            
            # 创建评论表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS comments (
                    comment_id TEXT PRIMARY KEY,
                    answer_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    author TEXT,
                    author_url TEXT,
                    create_time TEXT,
                    vote_count INTEGER DEFAULT 0,
                    reply_to TEXT,
                    crawl_time TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (answer_id) REFERENCES answers (answer_id)
                )
            ''')
            
            # 创建搜索记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS search_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT NOT NULL,
                    start_date TEXT,
                    end_date TEXT,
                    total_questions INTEGER DEFAULT 0,
                    total_answers INTEGER DEFAULT 0,
                    total_comments INTEGER DEFAULT 0,
                    search_time TEXT,
                    status TEXT DEFAULT 'running',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建任务状态表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS task_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_type TEXT NOT NULL,
                    keywords TEXT NOT NULL,
                    start_date TEXT,
                    end_date TEXT,
                    current_stage TEXT DEFAULT 'search',
                    processed_questions TEXT DEFAULT '[]',
                    processed_answers TEXT DEFAULT '[]',
                    total_questions INTEGER DEFAULT 0,
                    total_answers INTEGER DEFAULT 0,
                    total_comments INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'running',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建问题URL缓存表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS question_urls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER,
                    question_id TEXT,
                    question_url TEXT,
                    title TEXT,
                    processed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (task_id) REFERENCES task_status (id)
                )
            ''')
            
            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_questions_title ON questions(title)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_answers_question_id ON answers(question_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_comments_answer_id ON comments(answer_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_search_keyword ON search_records(keyword)')
            
            conn.commit()
    
    def save_question(self, question: Question) -> bool:
        """保存问题数据"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 检查是否已存在
                cursor.execute('SELECT question_id FROM questions WHERE question_id = ?', 
                             (question.question_id,))
                exists = cursor.fetchone()
                
                tags_json = json.dumps(question.tags, ensure_ascii=False)
                
                if exists:
                    # 更新现有记录
                    cursor.execute('''
                        UPDATE questions SET 
                        title = ?, content = ?, author = ?, create_time = ?,
                        follow_count = ?, view_count = ?, answer_count = ?,
                        url = ?, tags = ?, crawl_time = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE question_id = ?
                    ''', (question.title, question.content, question.author, 
                         question.create_time, question.follow_count, question.view_count,
                         question.answer_count, question.url, tags_json, 
                         question.crawl_time, question.question_id))
                else:
                    # 插入新记录
                    cursor.execute('''
                        INSERT INTO questions 
                        (question_id, title, content, author, create_time,
                         follow_count, view_count, answer_count, url, tags, crawl_time)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (question.question_id, question.title, question.content,
                         question.author, question.create_time, question.follow_count,
                         question.view_count, question.answer_count, question.url,
                         tags_json, question.crawl_time))
                
                conn.commit()
                return True
        except Exception as e:
            print(f"保存问题数据失败: {e}")
            return False
    
    def save_answer(self, answer: Answer) -> bool:
        """保存答案数据"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 检查是否已存在
                cursor.execute('SELECT answer_id FROM answers WHERE answer_id = ?', 
                             (answer.answer_id,))
                exists = cursor.fetchone()
                
                if exists:
                    # 更新现有记录
                    cursor.execute('''
                        UPDATE answers SET 
                        content = ?, author = ?, author_url = ?, create_time = ?,
                        update_time = ?, vote_count = ?, comment_count = ?,
                        url = ?, is_author = ?, crawl_time = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE answer_id = ?
                    ''', (answer.content, answer.author, answer.author_url,
                         answer.create_time, answer.update_time, answer.vote_count,
                         answer.comment_count, answer.url, answer.is_author,
                         answer.crawl_time, answer.answer_id))
                else:
                    # 插入新记录
                    cursor.execute('''
                        INSERT INTO answers 
                        (answer_id, question_id, content, author, author_url,
                         create_time, update_time, vote_count, comment_count,
                         url, is_author, crawl_time)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (answer.answer_id, answer.question_id, answer.content,
                         answer.author, answer.author_url, answer.create_time,
                         answer.update_time, answer.vote_count, answer.comment_count,
                         answer.url, answer.is_author, answer.crawl_time))
                
                conn.commit()
                return True
        except Exception as e:
            print(f"保存答案数据失败: {e}")
            return False
    
    def save_comment(self, comment: Comment) -> bool:
        """保存评论数据"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 检查是否已存在
                cursor.execute('SELECT comment_id FROM comments WHERE comment_id = ?', 
                             (comment.comment_id,))
                exists = cursor.fetchone()
                
                if exists:
                    # 更新现有记录
                    cursor.execute('''
                        UPDATE comments SET 
                        content = ?, author = ?, author_url = ?, create_time = ?,
                        vote_count = ?, reply_to = ?, crawl_time = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE comment_id = ?
                    ''', (comment.content, comment.author, comment.author_url,
                         comment.create_time, comment.vote_count, comment.reply_to,
                         comment.crawl_time, comment.comment_id))
                else:
                    # 插入新记录
                    cursor.execute('''
                        INSERT INTO comments 
                        (comment_id, answer_id, content, author, author_url,
                         create_time, vote_count, reply_to, crawl_time)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (comment.comment_id, comment.answer_id, comment.content,
                         comment.author, comment.author_url, comment.create_time,
                         comment.vote_count, comment.reply_to, comment.crawl_time))
                
                conn.commit()
                return True
        except Exception as e:
            print(f"保存评论数据失败: {e}")
            return False
    
    def save_search_record(self, keyword: str, start_date: str, end_date: str) -> int:
        """保存搜索记录并返回记录ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO search_records 
                    (keyword, start_date, end_date, search_time)
                    VALUES (?, ?, ?, ?)
                ''', (keyword, start_date, end_date, datetime.now().isoformat()))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            print(f"保存搜索记录失败: {e}")
            return 0
    
    def update_search_stats(self, record_id: int, questions: int, answers: int, comments: int, status: str = 'completed'):
        """更新搜索统计信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE search_records SET 
                    total_questions = ?, total_answers = ?, total_comments = ?, status = ?
                    WHERE id = ?
                ''', (questions, answers, comments, status, record_id))
                conn.commit()
        except Exception as e:
            print(f"更新搜索统计失败: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                stats = {}
                
                # 问题统计
                cursor.execute('SELECT COUNT(*) FROM questions')
                stats['total_questions'] = cursor.fetchone()[0]
                
                # 答案统计
                cursor.execute('SELECT COUNT(*) FROM answers')
                stats['total_answers'] = cursor.fetchone()[0]
                
                # 评论统计
                cursor.execute('SELECT COUNT(*) FROM comments')
                stats['total_comments'] = cursor.fetchone()[0]
                
                # 搜索记录统计
                cursor.execute('SELECT COUNT(*) FROM search_records')
                stats['total_searches'] = cursor.fetchone()[0]
                
                return stats
        except Exception as e:
            print(f"获取统计信息失败: {e}")
            return {}
    
    def create_task(self, task_type: str, keywords: List[str], start_date: str, end_date: str) -> int:
        """创建新任务并返回任务ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                keywords_json = json.dumps(keywords, ensure_ascii=False)
                cursor.execute('''
                    INSERT INTO task_status 
                    (task_type, keywords, start_date, end_date)
                    VALUES (?, ?, ?, ?)
                ''', (task_type, keywords_json, start_date, end_date))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            print(f"创建任务失败: {e}")
            return 0
    
    def update_task_stage(self, task_id: int, stage: str, processed_questions: List[str] = None, processed_answers: List[str] = None):
        """更新任务阶段和处理进度"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                update_fields = ['current_stage = ?', 'updated_at = CURRENT_TIMESTAMP']
                params = [stage]
                
                if processed_questions is not None:
                    update_fields.append('processed_questions = ?')
                    params.append(json.dumps(processed_questions, ensure_ascii=False))
                
                if processed_answers is not None:
                    update_fields.append('processed_answers = ?')
                    params.append(json.dumps(processed_answers, ensure_ascii=False))
                
                params.append(task_id)
                
                cursor.execute(f'''
                    UPDATE task_status SET {', '.join(update_fields)}
                    WHERE id = ?
                ''', params)
                conn.commit()
        except Exception as e:
            print(f"更新任务阶段失败: {e}")
    
    def save_question_urls(self, task_id: int, question_urls: List[Dict[str, str]]) -> bool:
        """批量保存问题URL"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                for url_info in question_urls:
                    cursor.execute('''
                        INSERT OR IGNORE INTO question_urls 
                        (task_id, question_id, question_url, title)
                        VALUES (?, ?, ?, ?)
                    ''', (task_id, url_info.get('question_id', ''), 
                         url_info.get('url', ''), url_info.get('title', '')))
                
                conn.commit()
                return True
        except Exception as e:
            print(f"保存问题URL失败: {e}")
            return False
    
    def get_unprocessed_questions(self, task_id: int) -> List[Dict[str, str]]:
        """获取未处理的问题URL"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT question_id, question_url, title 
                    FROM question_urls 
                    WHERE task_id = ? AND processed = FALSE
                ''', (task_id,))
                
                results = cursor.fetchall()
                return [{
                    'question_id': row[0],
                    'url': row[1],
                    'title': row[2]
                } for row in results]
        except Exception as e:
            print(f"获取未处理问题失败: {e}")
            return []
    
    def get_all_task_questions(self, task_id: int) -> List[Dict[str, str]]:
        """获取任务中的所有问题（包括已处理和未处理的）"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT question_id, question_url, title 
                    FROM question_urls 
                    WHERE task_id = ?
                ''', (task_id,))
                
                results = cursor.fetchall()
                return [{
                    'question_id': row[0],
                    'url': row[1],
                    'title': row[2]
                } for row in results]
        except Exception as e:
            print(f"获取任务所有问题失败: {e}")
            return []
    
    def mark_question_processed(self, task_id: int, question_id: str):
        """标记问题为已处理"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE question_urls SET processed = TRUE 
                    WHERE task_id = ? AND question_id = ?
                ''', (task_id, question_id))
                conn.commit()
        except Exception as e:
            print(f"标记问题已处理失败: {e}")
    
    def get_incomplete_tasks(self) -> List[Dict[str, Any]]:
        """获取未完成的任务"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, task_type, keywords, start_date, end_date, 
                           current_stage, processed_questions, processed_answers,
                           total_questions, total_answers, total_comments
                    FROM task_status 
                    WHERE status = 'running'
                    ORDER BY created_at DESC
                ''', )
                
                results = cursor.fetchall()
                tasks = []
                for row in results:
                    tasks.append({
                        'id': row[0],
                        'task_type': row[1],
                        'keywords': json.loads(row[2]),
                        'start_date': row[3],
                        'end_date': row[4],
                        'current_stage': row[5],
                        'processed_questions': json.loads(row[6]),
                        'processed_answers': json.loads(row[7]),
                        'total_questions': row[8],
                        'total_answers': row[9],
                        'total_comments': row[10]
                    })
                return tasks
        except Exception as e:
            print(f"获取未完成任务失败: {e}")
            return []
    
    def complete_task(self, task_id: int, total_questions: int, total_answers: int, total_comments: int):
        """完成任务"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE task_status SET 
                    status = 'completed',
                    total_questions = ?,
                    total_answers = ?,
                    total_comments = ?,
                    updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (total_questions, total_answers, total_comments, task_id))
                conn.commit()
        except Exception as e:
            print(f"完成任务失败: {e}")