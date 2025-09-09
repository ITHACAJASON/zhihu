"""PostgreSQL数据模型和数据库管理器"""

import psycopg2
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from contextlib import contextmanager
from config import ZhihuConfig
import logging


@dataclass
class TaskInfo:
    """任务信息数据模型"""
    task_id: str
    keywords: str
    start_date: str
    end_date: str
    # 两阶段状态管理
    search_stage_status: str = 'not_started'  # not_started, in_progress, completed
    qa_stage_status: str = 'not_started'     # not_started, in_progress, completed
    total_questions: int = 0
    processed_questions: int = 0
    total_answers: int = 0
    processed_answers: int = 0
    created_at: str = ""
    updated_at: str = ""
    
    def __post_init__(self):
        if not self.task_id:
            self.task_id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = datetime.now().isoformat()


@dataclass
class SearchResult:
    """搜索结果数据模型"""
    result_id: str
    task_id: str
    question_id: str
    question_url: str
    title: str
    preview_content: str = ""
    author: str = ""
    answer_count: int = 0
    processed: bool = False
    crawl_time: str = ""
    
    def __post_init__(self):
        if not self.result_id:
            self.result_id = str(uuid.uuid4())
        if not self.crawl_time:
            self.crawl_time = datetime.now().isoformat()


@dataclass
class Question:
    """问题数据模型"""
    question_id: str
    task_id: str
    title: str
    content: str = ""
    author: str = ""
    author_url: str = ""
    create_time: str = ""
    follow_count: int = 0
    view_count: int = 0
    answer_count: int = 0
    url: str = ""
    tags: List[str] = None
    processed: bool = False
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
    task_id: str
    content: str
    content_hash: str = ""
    author: str = ""
    author_url: str = ""
    create_time: str = ""
    update_time: str = ""
    publish_time: str = ""  # 新增：回答发布时间
    vote_count: int = 0
    comment_count: int = 0
    url: str = ""
    is_author: bool = False
    processed: bool = False
    crawl_time: str = ""
    
    def __post_init__(self):
        if not self.crawl_time:
            self.crawl_time = datetime.now().isoformat()





class PostgreSQLManager:
    """PostgreSQL数据库管理器"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or ZhihuConfig.POSTGRES_CONFIG
        self.logger = logging.getLogger(__name__)
        self._init_database()
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接的上下文管理器"""
        conn = None
        try:
            conn = psycopg2.connect(**self.config)
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            self.logger.error(f"数据库连接错误: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def _init_database(self):
        """初始化数据库表"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 创建任务信息表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS task_info (
                    task_id VARCHAR(36) PRIMARY KEY,
                    keywords TEXT NOT NULL,
                    start_date DATE,
                    end_date DATE,
                    search_stage_status VARCHAR(20) DEFAULT 'not_started',
                    qa_stage_status VARCHAR(20) DEFAULT 'not_started',
                    total_questions INTEGER DEFAULT 0,
                    processed_questions INTEGER DEFAULT 0,
                    total_answers INTEGER DEFAULT 0,
                    processed_answers INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建批量采集任务表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS batch_crawl_tasks (
                    task_id VARCHAR(50) PRIMARY KEY,
                    name VARCHAR(200) NOT NULL,
                    description TEXT,
                    query_filter JSONB NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',
                    total_urls INTEGER DEFAULT 0,
                    processed_urls INTEGER DEFAULT 0,
                    completed_urls INTEGER DEFAULT 0,
                    failed_urls INTEGER DEFAULT 0,
                    last_processed_url TEXT,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建批量采集进度表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS batch_crawl_progress (
                    id SERIAL PRIMARY KEY,
                    batch_task_id VARCHAR(50) NOT NULL,
                    question_id VARCHAR(50) NOT NULL,
                    question_url TEXT NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',
                    error_message TEXT,
                    retry_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(batch_task_id, question_id),
                    FOREIGN KEY (batch_task_id) REFERENCES batch_crawl_tasks(task_id) ON DELETE CASCADE
                )
            ''')
            
            # 创建反爬虫检测日志表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS anti_crawl_logs (
                    id SERIAL PRIMARY KEY,
                    batch_task_id VARCHAR(50),
                    detection_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    detection_type VARCHAR(50) NOT NULL,
                    error_details TEXT,
                    response_status INTEGER,
                    response_headers JSONB,
                    recovery_action VARCHAR(100),
                    recovery_time TIMESTAMP,
                    FOREIGN KEY (batch_task_id) REFERENCES batch_crawl_tasks(task_id) ON DELETE SET NULL
                )
            ''')
            
            # 创建搜索结果表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS search_results (
                    result_id VARCHAR(36) PRIMARY KEY,
                    task_id VARCHAR(36) NOT NULL,
                    question_id VARCHAR(100) NOT NULL,
                    question_url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    preview_content TEXT,
                    author VARCHAR(100),
                    answer_count INTEGER DEFAULT 0,
                    processed BOOLEAN DEFAULT FALSE,
                    crawl_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (task_id) REFERENCES task_info (task_id) ON DELETE CASCADE,
                    UNIQUE(task_id, question_id)
                )
            ''')
            
            # 创建问题表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS questions (
                    question_id VARCHAR(100) NOT NULL,
                    task_id VARCHAR(36) NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT,
                    author VARCHAR(100),
                    author_url TEXT,
                    create_time TIMESTAMP,
                    follow_count INTEGER DEFAULT 0,
                    view_count INTEGER DEFAULT 0,
                    answer_count INTEGER DEFAULT 0,
                    url TEXT,
                    tags JSONB,
                    processed BOOLEAN DEFAULT FALSE,
                    crawl_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (question_id, task_id),
                    FOREIGN KEY (task_id) REFERENCES task_info (task_id) ON DELETE CASCADE
                )
            ''')
            
            # 创建答案表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS answers (
                    answer_id VARCHAR(100) NOT NULL,
                    question_id VARCHAR(100) NOT NULL,
                    task_id VARCHAR(36) NOT NULL,
                    content TEXT NOT NULL,
                    content_hash VARCHAR(64),
                    author VARCHAR(100),
                    author_url TEXT,
                    create_time TIMESTAMP,
                    update_time TIMESTAMP,
                    publish_time TIMESTAMP,
                    vote_count INTEGER DEFAULT 0,
                    comment_count INTEGER DEFAULT 0,
                    url TEXT,
                    is_author BOOLEAN DEFAULT FALSE,
                    processed BOOLEAN DEFAULT FALSE,
                    crawl_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (answer_id, task_id),
                    FOREIGN KEY (question_id, task_id) REFERENCES questions (question_id, task_id) ON DELETE CASCADE
                )
            ''')
            

            
            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_search_results_task_id ON search_results(task_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_search_results_processed ON search_results(processed)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_questions_task_id ON questions(task_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_questions_processed ON questions(processed)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_answers_question_task ON answers(question_id, task_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_answers_processed ON answers(processed)')
            
            conn.commit()
            self.logger.info("PostgreSQL数据库表初始化完成")
    
    def create_task(self, keywords: str, start_date: str, end_date: str) -> str:
        """创建新任务"""
        task = TaskInfo(
            task_id="",
            keywords=keywords,
            start_date=start_date,
            end_date=end_date
        )
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO task_info 
                (task_id, keywords, start_date, end_date, search_stage_status, qa_stage_status)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (task.task_id, task.keywords, task.start_date, task.end_date, 
                  task.search_stage_status, task.qa_stage_status))
            conn.commit()
            
        self.logger.info(f"创建新任务: {task.task_id}")
        return task.task_id
    
    def get_unfinished_tasks(self) -> List[TaskInfo]:
        """获取未完成的任务"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT task_id, keywords, start_date, end_date, search_stage_status, qa_stage_status,
                       total_questions, processed_questions, total_answers, processed_answers,
                       created_at, updated_at
                FROM task_info 
                WHERE NOT (search_stage_status = 'completed' AND qa_stage_status = 'completed')
                ORDER BY created_at
            ''')
            
            tasks = []
            for row in cursor.fetchall():
                task = TaskInfo(
                    task_id=row[0], keywords=row[1], start_date=str(row[2]), end_date=str(row[3]),
                    search_stage_status=row[4], qa_stage_status=row[5],
                    total_questions=row[6], processed_questions=row[7], total_answers=row[8], processed_answers=row[9],
                    created_at=str(row[10]), updated_at=str(row[11])
                )
                tasks.append(task)
            
            return tasks
    
    def update_task_status(self, task_id: str, search_stage_status: str = None, 
                          qa_stage_status: str = None, **kwargs):
        """更新任务状态"""
        updates = []
        values = []
            
        if search_stage_status:
            updates.append("search_stage_status = %s")
            values.append(search_stage_status)
            
        if qa_stage_status:
            updates.append("qa_stage_status = %s")
            values.append(qa_stage_status)
        
        for key, value in kwargs.items():
            if key in ['total_questions', 'processed_questions', 'total_answers', 
                      'processed_answers']:
                updates.append(f"{key} = %s")
                values.append(value)
        
        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            values.append(task_id)
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f'''
                    UPDATE task_info SET {', '.join(updates)}
                    WHERE task_id = %s
                ''', values)
                conn.commit()
    
    def save_search_results(self, results: List[SearchResult]) -> bool:
        """批量保存搜索结果"""
        if not results:
            return True
            
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                for result in results:
                    cursor.execute('''
                        INSERT INTO search_results 
                        (result_id, task_id, question_id, question_url, title, 
                         preview_content, author, answer_count, processed, crawl_time)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (task_id, question_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        preview_content = EXCLUDED.preview_content,
                        author = EXCLUDED.author,
                        answer_count = EXCLUDED.answer_count,
                        crawl_time = EXCLUDED.crawl_time
                    ''', (result.result_id, result.task_id, result.question_id,
                          result.question_url, result.title, result.preview_content,
                          result.author, result.answer_count, result.processed,
                          result.crawl_time))
                
                conn.commit()
                self.logger.info(f"保存了 {len(results)} 条搜索结果")
                return True
        except Exception as e:
            self.logger.error(f"保存搜索结果失败: {e}")
            return False
    
    def save_question(self, question: Question) -> bool:
        """保存问题数据"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                tags_json = json.dumps(question.tags, ensure_ascii=False)
                
                cursor.execute('''
                    INSERT INTO questions 
                    (question_id, task_id, title, content, author, author_url,
                     create_time, follow_count, view_count, answer_count, url, tags,
                     processed, crawl_time)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (question_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    content = EXCLUDED.content,
                    author = EXCLUDED.author,
                    author_url = EXCLUDED.author_url,
                    create_time = EXCLUDED.create_time,
                    follow_count = EXCLUDED.follow_count,
                    view_count = EXCLUDED.view_count,
                    answer_count = EXCLUDED.answer_count,
                    url = EXCLUDED.url,
                    tags = EXCLUDED.tags,
                    processed = EXCLUDED.processed,
                    crawl_time = EXCLUDED.crawl_time,
                    updated_at = CURRENT_TIMESTAMP
                ''', (question.question_id, question.task_id, question.title,
                      question.content, question.author, question.author_url,
                      question.create_time, question.follow_count, question.view_count,
                      question.answer_count, question.url, tags_json,
                      question.processed, question.crawl_time))
                
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(f"保存问题数据失败: {e}")
            return False
    
    def save_answer(self, answer: Answer) -> bool:
        """保存答案数据"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO answers 
                    (answer_id, question_id, task_id, content, content_hash, author, author_url,
                     create_time, update_time, publish_time, vote_count, comment_count, url,
                     is_author, processed, crawl_time)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (answer_id) DO UPDATE SET
                    content = EXCLUDED.content,
                    content_hash = EXCLUDED.content_hash,
                    author = EXCLUDED.author,
                    author_url = EXCLUDED.author_url,
                    create_time = EXCLUDED.create_time,
                    update_time = EXCLUDED.update_time,
                    publish_time = EXCLUDED.publish_time,
                    vote_count = EXCLUDED.vote_count,
                    comment_count = EXCLUDED.comment_count,
                    url = EXCLUDED.url,
                    is_author = EXCLUDED.is_author,
                    processed = EXCLUDED.processed,
                    crawl_time = EXCLUDED.crawl_time,
                    updated_at = CURRENT_TIMESTAMP
                ''', (answer.answer_id, answer.question_id, answer.task_id,
                      answer.content, answer.content_hash, answer.author, answer.author_url,
                      answer.create_time, answer.update_time, answer.publish_time, answer.vote_count,
                      answer.comment_count, answer.url, answer.is_author,
                      answer.processed, answer.crawl_time))
                
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(f"保存答案数据失败: {e}")
            return False
    

    
    def get_unprocessed_search_results(self, task_id: str) -> List[SearchResult]:
        """获取未处理的搜索结果"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT result_id, task_id, question_id, question_url, title,
                       preview_content, author, answer_count, processed, crawl_time
                FROM search_results 
                WHERE task_id = %s AND processed = FALSE
                ORDER BY crawl_time
            ''', (task_id,))
            
            results = []
            for row in cursor.fetchall():
                result = SearchResult(
                    result_id=row[0], task_id=row[1], question_id=row[2],
                    question_url=row[3], title=row[4], preview_content=row[5],
                    author=row[6], answer_count=row[7], processed=row[8],
                    crawl_time=str(row[9])
                )
                results.append(result)
            
            return results
    
    def get_unprocessed_questions(self, task_id: str) -> List[Question]:
        """获取未处理的问题"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT question_id, task_id, title, content, author, author_url,
                       create_time, follow_count, view_count, answer_count, url,
                       tags, processed, crawl_time
                FROM questions 
                WHERE task_id = %s AND processed = FALSE
                ORDER BY crawl_time
            ''', (task_id,))
            
            questions = []
            for row in cursor.fetchall():
                # 处理tags字段，可能是JSON字符串或已经是list
                tags_data = row[11]
                if isinstance(tags_data, str):
                    tags = json.loads(tags_data) if tags_data else []
                elif isinstance(tags_data, list):
                    tags = tags_data
                else:
                    tags = []
                    
                question = Question(
                    question_id=row[0], task_id=row[1], title=row[2], content=row[3],
                    author=row[4], author_url=row[5], create_time=str(row[6]),
                    follow_count=row[7], view_count=row[8], answer_count=row[9],
                    url=row[10], tags=tags, processed=row[12], crawl_time=str(row[13])
                )
                questions.append(question)
            
            return questions
    
    def get_unprocessed_answers(self, task_id: str) -> List[Answer]:
        """获取未处理的答案"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT answer_id, question_id, task_id, content, author, author_url,
                       create_time, update_time, vote_count, comment_count, url,
                       is_author, processed, crawl_time
                FROM answers 
                WHERE task_id = %s AND processed = FALSE
                ORDER BY crawl_time
            ''', (task_id,))
            
            answers = []
            for row in cursor.fetchall():
                answer = Answer(
                    answer_id=row[0], question_id=row[1], task_id=row[2], content=row[3],
                    author=row[4], author_url=row[5], create_time=str(row[6]),
                    update_time=str(row[7]), vote_count=row[8], comment_count=row[9],
                    url=row[10], is_author=row[11], processed=row[12], crawl_time=str(row[13])
                )
                answers.append(answer)
            
            return answers
    
    def mark_processed(self, table: str, id_field: str, id_value: str, task_id: str = None):
        """标记数据为已处理"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if table in ['questions', 'answers']:
                # 对于questions和answers表，只使用ID字段
                cursor.execute(f'''
                    UPDATE {table} SET processed = TRUE
                    WHERE {id_field} = %s
                ''', (id_value,))
            else:
                # 对于其他表（如search_results），仍然使用task_id
                cursor.execute(f'''
                    UPDATE {table} SET processed = TRUE
                    WHERE {id_field} = %s AND task_id = %s
                ''', (id_value, task_id))
            conn.commit()
            return cursor.rowcount > 0
    
    def mark_search_result_processed(self, question_id: str, task_id: str):
        """标记搜索结果为已处理"""
        return self.mark_processed('search_results', 'question_id', question_id, task_id)
    
    def mark_question_processed(self, question_id: str, task_id: str):
        """标记问题为已处理"""
        return self.mark_processed('questions', 'question_id', question_id, task_id)
    
    def mark_answer_processed(self, answer_id: str, task_id: str):
        """标记答案为已处理"""
        return self.mark_processed('answers', 'answer_id', answer_id, task_id)
    
    def get_task_progress(self, task_id: str) -> Dict[str, Any]:
        """获取任务进度信息"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 获取任务基本信息
            cursor.execute('''
                SELECT search_stage_status, qa_stage_status,
                       total_questions, processed_questions, total_answers, processed_answers
                FROM task_info WHERE task_id = %s
            ''', (task_id,))
            
            task_info = cursor.fetchone()
            if not task_info:
                return {}
            
            # 获取各阶段的实际数据统计
            cursor.execute('SELECT COUNT(*) FROM search_results WHERE task_id = %s', (task_id,))
            search_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM search_results WHERE task_id = %s AND processed = TRUE', (task_id,))
            search_processed = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM questions WHERE task_id = %s', (task_id,))
            question_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM questions WHERE task_id = %s AND processed = TRUE', (task_id,))
            question_processed = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM answers WHERE task_id = %s', (task_id,))
            answer_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM answers WHERE task_id = %s AND processed = TRUE', (task_id,))
            answer_processed = cursor.fetchone()[0]
            
            return {
                'search_stage_status': task_info[0],
                'qa_stage_status': task_info[1],
                'search_results': {'total': search_count, 'processed': search_processed},
                'questions': {'total': question_count, 'processed': question_processed},
                'answers': {'total': answer_count, 'processed': answer_processed}
            }
    
    def get_unique_answer_count(self, question_id: str, task_id: str) -> int:
        """获取去重后的回答数量（基于content_hash去重）"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT COUNT(DISTINCT content_hash) 
                    FROM answers 
                    WHERE question_id = %s AND task_id = %s AND content_hash IS NOT NULL AND content_hash != ''
                ''', (question_id, task_id))
                result = cursor.fetchone()
                return result[0] if result else 0
        except Exception as e:
            self.logger.error(f"获取去重回答数量失败: {e}")
            return 0
    
    def get_tasks_by_keyword(self, keyword: str) -> List[TaskInfo]:
        """根据关键词获取任务"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT task_id, keywords, start_date, end_date, search_stage_status, qa_stage_status,
                       total_questions, processed_questions, total_answers, processed_answers,
                       created_at, updated_at
                FROM task_info 
                WHERE keywords = %s
                ORDER BY created_at DESC
            ''', (keyword,))
            
            tasks = []
            for row in cursor.fetchall():
                task = TaskInfo(
                    task_id=row[0], keywords=row[1], start_date=str(row[2]), end_date=str(row[3]),
                    search_stage_status=row[4], qa_stage_status=row[5],
                    total_questions=row[6], processed_questions=row[7], total_answers=row[8], processed_answers=row[9],
                    created_at=str(row[10]), updated_at=str(row[11])
                )
                tasks.append(task)
            
            return tasks
    
    def get_task_info(self, task_id: str) -> Optional[TaskInfo]:
        """获取任务信息"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT task_id, keywords, start_date, end_date, search_stage_status, qa_stage_status,
                       total_questions, processed_questions, total_answers, processed_answers,
                       created_at, updated_at
                FROM task_info 
                WHERE task_id = %s
            ''', (task_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
                
            return TaskInfo(
                task_id=row[0], keywords=row[1], start_date=str(row[2]), end_date=str(row[3]),
                search_stage_status=row[4], qa_stage_status=row[5],
                total_questions=row[6], processed_questions=row[7], total_answers=row[8], processed_answers=row[9],
                created_at=str(row[10]), updated_at=str(row[11])
            )
    
    def get_interrupted_tasks(self) -> List[TaskInfo]:
        """获取中断的任务（根据两阶段状态判断）"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT task_id, keywords, start_date, end_date, search_stage_status, qa_stage_status,
                       total_questions, processed_questions, total_answers, processed_answers,
                       created_at, updated_at
                FROM task_info 
                WHERE NOT (search_stage_status = 'completed' AND qa_stage_status = 'completed')
                ORDER BY created_at
            ''')
            
            tasks = []
            for row in cursor.fetchall():
                task = TaskInfo(
                    task_id=row[0], keywords=row[1], start_date=str(row[2]), end_date=str(row[3]),
                    search_stage_status=row[4], qa_stage_status=row[5],
                    total_questions=row[6], processed_questions=row[7], total_answers=row[8], processed_answers=row[9],
                    created_at=str(row[10]), updated_at=str(row[11])
                )
                tasks.append(task)
            
            return tasks
    
    def determine_task_resume_strategy(self, task_id: str) -> Dict[str, Any]:
        """确定任务恢复策略"""
        task_info = self.get_task_info(task_id)
        if not task_info:
            return {'strategy': 'not_found', 'message': '任务不存在'}
        
        search_status = task_info.search_stage_status
        qa_status = task_info.qa_stage_status
        
        if search_status == 'completed' and qa_status == 'completed':
            return {
                'strategy': 'completed',
                'message': '任务已完成',
                'task_info': task_info
            }
        elif search_status == 'in_progress' and qa_status == 'not_started':
            return {
                'strategy': 'resume_search',
                'message': '阶段一进行中，继续搜索任务',
                'task_info': task_info,
                'action': 'continue_search_and_save_results'
            }
        elif search_status == 'completed' and qa_status == 'in_progress':
            # 找到最后处理的问题，从该问题继续
            last_question = self.get_last_processed_question(task_id)
            return {
                'strategy': 'resume_qa',
                'message': '阶段一已完成，阶段二进行中，继续问答详情采集',
                'task_info': task_info,
                'action': 'continue_qa_collection',
                'last_question': last_question
            }
        elif search_status == 'not_started':
            return {
                'strategy': 'start_fresh',
                'message': '任务未开始，从头开始',
                'task_info': task_info,
                'action': 'start_search_task'
            }
        else:
            return {
                'strategy': 'unknown',
                'message': f'未知状态组合: search={search_status}, qa={qa_status}',
                'task_info': task_info
            }
    
    def get_last_processed_question(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取最后一个被处理的问题"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT question_id, title, created_at
                FROM questions 
                WHERE task_id = %s 
                ORDER BY created_at DESC 
                LIMIT 1
            ''', (task_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'question_id': row[0],
                    'title': row[1],
                    'created_at': str(row[2])
                }
            return None
    
    def update_stage_status(self, task_id: str, stage: str, status: str):
        """更新特定阶段的状态"""
        if stage == 'search':
            self.update_task_status(task_id, search_stage_status=status)
        elif stage == 'qa':
            self.update_task_status(task_id, qa_stage_status=status)
        else:
            raise ValueError(f"未知阶段: {stage}")
    
    def close(self):
        """关闭数据库连接（PostgreSQL使用连接池，无需显式关闭）"""
        pass