"""数据库查询管理器 - 支持基于规则的URL筛选和批量采集"""

import psycopg2
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from postgres_models import PostgreSQLManager, Question, SearchResult
from config import ZhihuConfig


@dataclass
class QueryFilter:
    """查询过滤条件"""
    # 回答数筛选
    answer_count_min: Optional[int] = None
    answer_count_max: Optional[int] = None
    
    # 关注数筛选
    follow_count_min: Optional[int] = None
    follow_count_max: Optional[int] = None
    
    # 浏览数筛选
    view_count_min: Optional[int] = None
    view_count_max: Optional[int] = None
    
    # 时间筛选
    create_time_start: Optional[str] = None
    create_time_end: Optional[str] = None
    
    # 关键词筛选
    title_keywords: Optional[List[str]] = None
    content_keywords: Optional[List[str]] = None
    
    # 作者筛选
    author_filter: Optional[str] = None
    
    # 标签筛选
    tags_include: Optional[List[str]] = None
    tags_exclude: Optional[List[str]] = None
    
    # 处理状态筛选
    processed: Optional[bool] = None
    
    # 任务ID筛选
    task_ids: Optional[List[str]] = None
    
    # 排序选项
    order_by: str = 'crawl_time'  # crawl_time, answer_count, follow_count, view_count
    order_desc: bool = True
    
    # 分页选项
    limit: Optional[int] = None
    offset: int = 0


@dataclass
class BatchCrawlTask:
    """批量采集任务"""
    task_id: str
    name: str
    description: str
    query_filter: QueryFilter
    status: str = 'pending'  # pending, running, paused, completed, failed
    created_at: str = ""
    updated_at: str = ""
    total_urls: int = 0
    processed_urls: int = 0
    failed_urls: int = 0
    last_processed_url: str = ""
    error_message: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = datetime.now().isoformat()


class DatabaseQueryManager(PostgreSQLManager):
    """数据库查询管理器 - 扩展PostgreSQL管理器，支持复杂查询和批量采集"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.logger = logging.getLogger(__name__)
        self._init_batch_tables()
    
    def _init_batch_tables(self):
        """初始化批量采集相关表"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 创建批量采集任务表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS batch_crawl_tasks (
                    task_id VARCHAR(36) PRIMARY KEY,
                    name VARCHAR(200) NOT NULL,
                    description TEXT,
                    query_filter JSONB NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_urls INTEGER DEFAULT 0,
                    processed_urls INTEGER DEFAULT 0,
                    failed_urls INTEGER DEFAULT 0,
                    last_processed_url TEXT,
                    error_message TEXT
                )
            ''')
            
            # 创建批量采集进度表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS batch_crawl_progress (
                    id SERIAL PRIMARY KEY,
                    batch_task_id VARCHAR(36) NOT NULL,
                    question_id VARCHAR(100) NOT NULL,
                    question_url TEXT NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',  -- pending, processing, completed, failed
                    error_message TEXT,
                    retry_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (batch_task_id) REFERENCES batch_crawl_tasks (task_id) ON DELETE CASCADE,
                    UNIQUE(batch_task_id, question_id)
                )
            ''')
            
            # 创建反爬虫检测记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS anti_crawl_logs (
                    id SERIAL PRIMARY KEY,
                    batch_task_id VARCHAR(36),
                    detection_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    detection_type VARCHAR(50) NOT NULL,  -- rate_limit, captcha, ip_block, etc.
                    error_details TEXT,
                    response_status INTEGER,
                    response_headers JSONB,
                    recovery_action VARCHAR(100),
                    recovery_time TIMESTAMP,
                    FOREIGN KEY (batch_task_id) REFERENCES batch_crawl_tasks (task_id) ON DELETE SET NULL
                )
            ''')
            
            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_batch_tasks_status ON batch_crawl_tasks(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_batch_progress_task_status ON batch_crawl_progress(batch_task_id, status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_anti_crawl_logs_task_time ON anti_crawl_logs(batch_task_id, detection_time)')
            
            conn.commit()
            self.logger.info("批量采集相关表初始化完成")
    
    def query_questions_by_filter(self, query_filter: QueryFilter) -> List[Question]:
        """根据过滤条件查询问题"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 构建查询条件
            where_conditions = []
            params = []
            
            # 回答数筛选
            if query_filter.answer_count_min is not None:
                where_conditions.append("answer_count >= %s")
                params.append(query_filter.answer_count_min)
            if query_filter.answer_count_max is not None:
                where_conditions.append("answer_count <= %s")
                params.append(query_filter.answer_count_max)
            
            # 关注数筛选
            if query_filter.follow_count_min is not None:
                where_conditions.append("follow_count >= %s")
                params.append(query_filter.follow_count_min)
            if query_filter.follow_count_max is not None:
                where_conditions.append("follow_count <= %s")
                params.append(query_filter.follow_count_max)
            
            # 浏览数筛选
            if query_filter.view_count_min is not None:
                where_conditions.append("view_count >= %s")
                params.append(query_filter.view_count_min)
            if query_filter.view_count_max is not None:
                where_conditions.append("view_count <= %s")
                params.append(query_filter.view_count_max)
            
            # 时间筛选
            if query_filter.create_time_start:
                where_conditions.append("create_time >= %s")
                params.append(query_filter.create_time_start)
            if query_filter.create_time_end:
                where_conditions.append("create_time <= %s")
                params.append(query_filter.create_time_end)
            
            # 关键词筛选
            if query_filter.title_keywords:
                keyword_conditions = []
                for keyword in query_filter.title_keywords:
                    keyword_conditions.append("title ILIKE %s")
                    params.append(f"%{keyword}%")
                where_conditions.append(f"({' OR '.join(keyword_conditions)})")
            
            if query_filter.content_keywords:
                keyword_conditions = []
                for keyword in query_filter.content_keywords:
                    keyword_conditions.append("content ILIKE %s")
                    params.append(f"%{keyword}%")
                where_conditions.append(f"({' OR '.join(keyword_conditions)})")
            
            # 作者筛选
            if query_filter.author_filter:
                where_conditions.append("author ILIKE %s")
                params.append(f"%{query_filter.author_filter}%")
            
            # 标签筛选
            if query_filter.tags_include:
                for tag in query_filter.tags_include:
                    where_conditions.append("tags::text ILIKE %s")
                    params.append(f"%{tag}%")
            
            if query_filter.tags_exclude:
                for tag in query_filter.tags_exclude:
                    where_conditions.append("NOT (tags::text ILIKE %s)")
                    params.append(f"%{tag}%")
            
            # 处理状态筛选
            if query_filter.processed is not None:
                where_conditions.append("processed = %s")
                params.append(query_filter.processed)
            
            # 任务ID筛选
            if query_filter.task_ids:
                placeholders = ','.join(['%s'] * len(query_filter.task_ids))
                where_conditions.append(f"task_id IN ({placeholders})")
                params.extend(query_filter.task_ids)
            
            # 构建完整查询
            base_query = '''
                SELECT question_id, task_id, title, content, author, author_url,
                       create_time, follow_count, view_count, answer_count, url,
                       tags, processed, crawl_time
                FROM questions
            '''
            
            if where_conditions:
                base_query += " WHERE " + " AND ".join(where_conditions)
            
            # 排序
            order_direction = "DESC" if query_filter.order_desc else "ASC"
            base_query += f" ORDER BY {query_filter.order_by} {order_direction}"
            
            # 分页
            if query_filter.limit:
                base_query += f" LIMIT {query_filter.limit}"
            if query_filter.offset > 0:
                base_query += f" OFFSET {query_filter.offset}"
            
            cursor.execute(base_query, params)
            
            questions = []
            for row in cursor.fetchall():
                # 处理tags字段
                tags_data = row[11]
                if isinstance(tags_data, str):
                    import json
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
    
    def get_question_urls_by_filter(self, query_filter: QueryFilter) -> List[Tuple[str, str]]:
        """根据过滤条件获取问题URL列表，返回(question_id, url)元组列表"""
        questions = self.query_questions_by_filter(query_filter)
        return [(q.question_id, q.url) for q in questions if q.url]
    
    def count_questions_by_filter(self, query_filter: QueryFilter) -> int:
        """统计符合条件的问题数量"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 构建查询条件（复用上面的逻辑）
            where_conditions = []
            params = []
            
            # 这里可以复用上面的条件构建逻辑，为了简化，先实现基本的计数
            base_query = "SELECT COUNT(*) FROM questions"
            
            # 添加基本筛选条件
            if query_filter.answer_count_min is not None or query_filter.answer_count_max is not None:
                if query_filter.answer_count_min is not None:
                    where_conditions.append("answer_count >= %s")
                    params.append(query_filter.answer_count_min)
                if query_filter.answer_count_max is not None:
                    where_conditions.append("answer_count <= %s")
                    params.append(query_filter.answer_count_max)
            
            if where_conditions:
                base_query += " WHERE " + " AND ".join(where_conditions)
            
            cursor.execute(base_query, params)
            return cursor.fetchone()[0]
    
    def create_batch_crawl_task(self, name: str, description: str, query_filter: QueryFilter) -> str:
        """创建批量采集任务"""
        import uuid
        import json
        
        task_id = str(uuid.uuid4())
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 统计符合条件的URL数量
            total_urls = self.count_questions_by_filter(query_filter)
            
            cursor.execute('''
                INSERT INTO batch_crawl_tasks 
                (task_id, name, description, query_filter, total_urls)
                VALUES (%s, %s, %s, %s, %s)
            ''', (task_id, name, description, json.dumps(query_filter.__dict__), total_urls))
            
            conn.commit()
            
        self.logger.info(f"创建批量采集任务: {task_id}, 预计处理 {total_urls} 个URL")
        return task_id
    
    def get_batch_crawl_task(self, task_id: str) -> Optional[BatchCrawlTask]:
        """获取批量采集任务信息"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT task_id, name, description, query_filter, status,
                       created_at, updated_at, total_urls, processed_urls, failed_urls,
                       last_processed_url, error_message
                FROM batch_crawl_tasks WHERE task_id = %s
            ''', (task_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            import json
            # row[3]已经是dict类型（JSONB自动解析），不需要json.loads
            query_filter_dict = row[3] if isinstance(row[3], dict) else json.loads(row[3])
            query_filter = QueryFilter(**query_filter_dict)
            
            return BatchCrawlTask(
                task_id=row[0], name=row[1], description=row[2],
                query_filter=query_filter, status=row[4],
                created_at=str(row[5]), updated_at=str(row[6]),
                total_urls=row[7], processed_urls=row[8], failed_urls=row[9],
                last_processed_url=row[10] or "", error_message=row[11] or ""
            )
    
    def update_batch_crawl_task_status(self, task_id: str, status: str, 
                                     processed_urls: int = None, failed_urls: int = None,
                                     last_processed_url: str = None, error_message: str = None):
        """更新批量采集任务状态"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            updates = ["status = %s", "updated_at = CURRENT_TIMESTAMP"]
            params = [status]
            
            if processed_urls is not None:
                updates.append("processed_urls = %s")
                params.append(processed_urls)
            
            if failed_urls is not None:
                updates.append("failed_urls = %s")
                params.append(failed_urls)
            
            if last_processed_url is not None:
                updates.append("last_processed_url = %s")
                params.append(last_processed_url)
            
            if error_message is not None:
                updates.append("error_message = %s")
                params.append(error_message)
            
            params.append(task_id)
            
            cursor.execute(f'''
                UPDATE batch_crawl_tasks SET {', '.join(updates)}
                WHERE task_id = %s
            ''', params)
            
            conn.commit()
    
    def get_pending_batch_tasks(self) -> List[BatchCrawlTask]:
        """获取待处理的批量采集任务"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT task_id, name, description, query_filter, status,
                       created_at, updated_at, total_urls, processed_urls, failed_urls,
                       last_processed_url, error_message
                FROM batch_crawl_tasks 
                WHERE status IN ('pending', 'paused')
                ORDER BY created_at
            ''')
            
            tasks = []
            for row in cursor.fetchall():
                import json
                # row[3]已经是dict类型（JSONB自动解析），不需要json.loads
                query_filter_dict = row[3] if isinstance(row[3], dict) else json.loads(row[3])
                query_filter = QueryFilter(**query_filter_dict)
                
                task = BatchCrawlTask(
                    task_id=row[0], name=row[1], description=row[2],
                    query_filter=query_filter, status=row[4],
                    created_at=str(row[5]), updated_at=str(row[6]),
                    total_urls=row[7], processed_urls=row[8], failed_urls=row[9],
                    last_processed_url=row[10] or "", error_message=row[11] or ""
                )
                tasks.append(task)
            
            return tasks
    
    def list_batch_crawl_tasks(self, status_filter: str = None) -> List[BatchCrawlTask]:
        """列出批量采集任务"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if status_filter:
                cursor.execute('''
                    SELECT task_id, name, description, query_filter, status,
                           created_at, updated_at, total_urls, processed_urls, failed_urls,
                           last_processed_url, error_message
                    FROM batch_crawl_tasks 
                    WHERE status = %s
                    ORDER BY created_at DESC
                ''', (status_filter,))
            else:
                cursor.execute('''
                    SELECT task_id, name, description, query_filter, status,
                           created_at, updated_at, total_urls, processed_urls, failed_urls,
                           last_processed_url, error_message
                    FROM batch_crawl_tasks 
                    ORDER BY created_at DESC
                ''')
            
            tasks = []
            for row in cursor.fetchall():
                import json
                query_filter_dict = json.loads(row[3])
                query_filter = QueryFilter(**query_filter_dict)
                
                task = BatchCrawlTask(
                    task_id=row[0], name=row[1], description=row[2],
                    query_filter=query_filter, status=row[4],
                    created_at=str(row[5]), updated_at=str(row[6]),
                    total_urls=row[7], processed_urls=row[8], failed_urls=row[9],
                    last_processed_url=row[10] or "", error_message=row[11] or ""
                )
                tasks.append(task)
            
            return tasks
    
    def list_batch_crawl_progress(self, task_id: str = None) -> List[Any]:
        """列出批量采集进度"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if task_id:
                cursor.execute('''
                    SELECT task_id, question_id, question_url, status, retry_count,
                           last_error, created_at, updated_at
                    FROM batch_crawl_progress 
                    WHERE task_id = %s
                    ORDER BY created_at
                ''', (task_id,))
            else:
                cursor.execute('''
                    SELECT task_id, question_id, question_url, status, retry_count,
                           last_error, created_at, updated_at
                    FROM batch_crawl_progress 
                    ORDER BY created_at
                ''')
            
            # 返回简单的字典列表，避免复杂的数据类转换
            progress_list = []
            for row in cursor.fetchall():
                progress = {
                    'task_id': row[0],
                    'question_id': row[1],
                    'question_url': row[2],
                    'status': row[3],
                    'retry_count': row[4],
                    'last_error': row[5],
                    'created_at': str(row[6]),
                    'updated_at': str(row[7])
                }
                progress_list.append(progress)
            
            return progress_list
    
    def update_batch_crawl_task_stats(self, task_id: str, completed_urls: int = None, failed_urls: int = None):
        """更新批量采集任务统计信息"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 构建更新语句
            update_fields = []
            params = []
            
            if completed_urls is not None:
                update_fields.append("processed_urls = %s")
                params.append(completed_urls)
            
            if failed_urls is not None:
                update_fields.append("failed_urls = %s")
                params.append(failed_urls)
            
            if update_fields:
                update_fields.append("updated_at = CURRENT_TIMESTAMP")
                params.append(task_id)
                
                sql = f'''
                    UPDATE batch_crawl_tasks 
                    SET {', '.join(update_fields)}
                    WHERE task_id = %s
                '''
                
                cursor.execute(sql, params)
                conn.commit()