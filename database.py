import psycopg2
import logging
from typing import List, Tuple, Optional

class DatabaseManager:
    """PostgreSQL数据库管理类"""
    
    def __init__(self, host: str = 'localhost', port: int = 5432, 
                 database: str = 'zhihu_crawl', user: str = 'postgres', 
                 password: str = 'password'):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.connection = None
        self.cursor = None
        
    def connect(self) -> bool:
        """连接数据库"""
        try:
            self.connection = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            self.cursor = self.connection.cursor()
            logging.info(f"成功连接到数据库 {self.database}")
            return True
        except Exception as e:
            logging.error(f"数据库连接失败: {e}")
            return False
    
    def disconnect(self):
        """断开数据库连接"""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
        logging.info("数据库连接已断开")
    
    def get_questions(self) -> List[Tuple[str, int]]:
        """从questions表获取URL和answer_count"""
        try:
            query = "SELECT url, answer_count FROM questions WHERE url IS NOT NULL AND answer_count > 0"
            self.cursor.execute(query)
            results = self.cursor.fetchall()
            logging.info(f"获取到 {len(results)} 个问题")
            return results
        except Exception as e:
            logging.error(f"获取问题列表失败: {e}")
            self.connection.rollback()  # 回滚事务
            return []
    
    def get_pending_questions(self, limit=None):
        """获取待爬取的问题（包括已完成采集的问题）"""
        try:
            # 修改查询逻辑：读取所有questions表中的数据，不限制crawl_status
            query = "SELECT url, answer_count FROM questions"
            if limit:
                query += f" LIMIT {limit}"
            
            self.cursor.execute(query)
            questions = self.cursor.fetchall()
            logging.info(f"从数据库读取到 {len(questions)} 个问题")
            return questions
        except Exception as e:
            logging.error(f"获取问题列表失败: {e}")
            return []
    
    def update_crawl_status(self, url: str, status: str, crawled_count: int = 0):
        """更新爬取状态"""
        try:
            # 假设questions表有crawl_status和crawled_count字段
            query = "UPDATE questions SET crawl_status = %s, crawled_count = %s WHERE url = %s"
            self.cursor.execute(query, (status, crawled_count, url))
            self.connection.commit()
            logging.info(f"更新URL {url} 状态为 {status}，已爬取 {crawled_count} 个回答")
        except Exception as e:
            logging.error(f"更新爬取状态失败: {e}")
            self.connection.rollback()  # 回滚事务
    
    def save_answer(self, question_url: str, answer_data: dict) -> bool:
        """保存回答数据到answers表"""
        try:
            # 从URL中提取question_id
            import re
            question_id_match = re.search(r'/question/(\d+)', question_url)
            if not question_id_match:
                logging.error(f"无法从URL中提取question_id: {question_url}")
                return False
            
            question_id = question_id_match.group(1)
            
            # 处理时间格式转换
            created_time = self._parse_time_string(answer_data.get('created_time'))
            
            # 插入回答数据到现有的answers表结构
            insert_query = """
            INSERT INTO answers (question_id, answer_id, author, content, vote_count, create_time, task_id, url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (answer_id) DO NOTHING
            """
            
            # 生成一个简单的task_id（可以使用UUID或其他方式）
            import uuid
            task_id = str(uuid.uuid4())
            
            self.cursor.execute(insert_query, (
                question_id,
                answer_data.get('answer_id'),
                answer_data.get('author'),
                answer_data.get('content'),
                answer_data.get('vote_count', 0),
                created_time,
                task_id,
                question_url
            ))
            
            self.connection.commit()
            return True
            
        except Exception as e:
            logging.error(f"保存回答数据失败: {e}")
            self.connection.rollback()
            return False
    
    def save_answers_batch(self, question_url: str, answers_data: List[dict]) -> int:
        """批量保存回答数据到answers表"""
        if not answers_data:
            return 0
            
        try:
            # 从URL中提取question_id
            import re
            question_id_match = re.search(r'/question/(\d+)', question_url)
            if not question_id_match:
                logging.error(f"无法从URL中提取question_id: {question_url}")
                return 0
            
            question_id = question_id_match.group(1)
            
            # 批量插入回答数据
            insert_query = """
            INSERT INTO answers (question_id, answer_id, author, content, vote_count, create_time, task_id, url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (answer_id) DO NOTHING
            """
            
            import uuid
            batch_data = []
            for answer_data in answers_data:
                created_time = self._parse_time_string(answer_data.get('created_time'))
                task_id = str(uuid.uuid4())
                
                batch_data.append((
                    question_id,
                    answer_data.get('answer_id'),
                    answer_data.get('author'),
                    answer_data.get('content'),
                    answer_data.get('vote_count', 0),
                    created_time,
                    task_id,
                    question_url
                ))
            
            # 执行批量插入
            self.cursor.executemany(insert_query, batch_data)
            self.connection.commit()
            
            saved_count = len(batch_data)
            logging.info(f"批量保存 {saved_count} 个回答成功")
            return saved_count
            
        except Exception as e:
            logging.error(f"批量保存回答失败: {e}")
            self.connection.rollback()
            return 0
    
    def _parse_time_string(self, time_str: str) -> Optional[str]:
        """解析中文时间字符串为数据库可接受的格式"""
        if not time_str:
            return None
            
        import re
        from datetime import datetime
        
        try:
            # 移除中文前缀
            time_str = time_str.strip()
            
            # 处理"编辑于"、"发布于"等前缀
            if '编辑于' in time_str:
                time_str = time_str.replace('编辑于', '').strip()
            elif '发布于' in time_str:
                time_str = time_str.replace('发布于', '').strip()
            
            # 移除地点信息（如"・美国"）
            if '・' in time_str:
                time_str = time_str.split('・')[0].strip()
            
            # 尝试解析标准格式 YYYY-MM-DD HH:MM
            date_pattern = r'(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{1,2})'
            match = re.search(date_pattern, time_str)
            
            if match:
                year, month, day, hour, minute = match.groups()
                # 格式化为标准时间戳格式
                formatted_time = f"{year}-{month.zfill(2)}-{day.zfill(2)} {hour.zfill(2)}:{minute.zfill(2)}:00"
                return formatted_time
            else:
                # 如果无法解析，返回None
                logging.warning(f"无法解析时间格式: {time_str}")
                return None
                
        except Exception as e:
            logging.error(f"时间解析失败: {e}, 原始字符串: {time_str}")
            return None
    
    def get_crawled_count(self, question_url: str) -> int:
        """获取已爬取的回答数量"""
        try:
            # 从URL中提取question_id
            import re
            question_id_match = re.search(r'/question/(\d+)', question_url)
            if not question_id_match:
                logging.error(f"无法从URL中提取question_id: {question_url}")
                return 0
            
            question_id = question_id_match.group(1)
            query = "SELECT COUNT(*) FROM answers WHERE question_id = %s"
            self.cursor.execute(query, (question_id,))
            result = self.cursor.fetchone()
            return result[0] if result else 0
        except Exception as e:
            logging.error(f"获取已爬取数量失败: {e}")
            self.connection.rollback()  # 回滚事务
            return 0