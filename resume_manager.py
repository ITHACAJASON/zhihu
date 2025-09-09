"""断点续传和反爬虫检测管理器"""

import time
import json
import asyncio
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import logging
from enum import Enum
import random
from database_query_manager import DatabaseQueryManager, BatchCrawlTask, QueryFilter


class AntiCrawlType(Enum):
    """反爬虫检测类型"""
    RATE_LIMIT = "rate_limit"          # 请求频率限制
    CAPTCHA = "captcha"                # 验证码
    IP_BLOCK = "ip_block"              # IP封禁
    USER_AGENT_BLOCK = "user_agent_block"  # User-Agent封禁
    SESSION_EXPIRED = "session_expired"    # 会话过期
    NETWORK_ERROR = "network_error"       # 网络错误
    SERVER_ERROR = "server_error"         # 服务器错误
    UNKNOWN = "unknown"                   # 未知错误


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"        # 待处理
    RUNNING = "running"        # 运行中
    PAUSED = "paused"          # 暂停
    COMPLETED = "completed"    # 完成
    FAILED = "failed"          # 失败
    CANCELLED = "cancelled"    # 取消


@dataclass
class AntiCrawlDetection:
    """反爬虫检测记录"""
    detection_type: AntiCrawlType
    detection_time: datetime
    error_details: str
    response_status: Optional[int] = None
    response_headers: Optional[Dict[str, str]] = None
    recovery_action: Optional[str] = None
    recovery_time: Optional[datetime] = None
    batch_task_id: Optional[str] = None


@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3
    base_delay: float = 1.0  # 基础延迟秒数
    max_delay: float = 60.0  # 最大延迟秒数
    exponential_base: float = 2.0  # 指数退避基数
    jitter: bool = True  # 是否添加随机抖动


@dataclass
class CrawlProgress:
    """采集进度"""
    batch_task_id: str
    question_id: str
    question_url: str
    status: str = 'pending'  # pending, processing, completed, failed
    error_message: str = ""
    retry_count: int = 0
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()


class AntiCrawlDetector:
    """反爬虫检测器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.detection_patterns = {
            # HTTP状态码模式
            'status_codes': {
                429: AntiCrawlType.RATE_LIMIT,
                403: AntiCrawlType.IP_BLOCK,
                401: AntiCrawlType.SESSION_EXPIRED,
                500: AntiCrawlType.SERVER_ERROR,
                502: AntiCrawlType.SERVER_ERROR,
                503: AntiCrawlType.SERVER_ERROR,
            },
            # 响应内容关键词
            'content_keywords': {
                'captcha': AntiCrawlType.CAPTCHA,
                '验证码': AntiCrawlType.CAPTCHA,
                'blocked': AntiCrawlType.IP_BLOCK,
                'rate limit': AntiCrawlType.RATE_LIMIT,
                '访问频率': AntiCrawlType.RATE_LIMIT,
                'too many requests': AntiCrawlType.RATE_LIMIT,
            },
            # 响应头模式
            'header_patterns': {
                'retry-after': AntiCrawlType.RATE_LIMIT,
                'x-ratelimit-remaining': AntiCrawlType.RATE_LIMIT,
            }
        }
    
    def detect_anti_crawl(self, response_status: int, response_content: str = "", 
                         response_headers: Dict[str, str] = None) -> Optional[AntiCrawlDetection]:
        """检测反爬虫机制"""
        response_headers = response_headers or {}
        
        # 检查状态码
        if response_status in self.detection_patterns['status_codes']:
            detection_type = self.detection_patterns['status_codes'][response_status]
            return AntiCrawlDetection(
                detection_type=detection_type,
                detection_time=datetime.now(),
                error_details=f"HTTP状态码 {response_status} 触发反爬虫检测",
                response_status=response_status,
                response_headers=response_headers
            )
        
        # 检查响应内容关键词
        content_lower = response_content.lower()
        for keyword, detection_type in self.detection_patterns['content_keywords'].items():
            if keyword in content_lower:
                return AntiCrawlDetection(
                    detection_type=detection_type,
                    detection_time=datetime.now(),
                    error_details=f"响应内容包含关键词 '{keyword}' 触发反爬虫检测",
                    response_status=response_status,
                    response_headers=response_headers
                )
        
        # 检查响应头
        for header_key, detection_type in self.detection_patterns['header_patterns'].items():
            if header_key.lower() in [k.lower() for k in response_headers.keys()]:
                return AntiCrawlDetection(
                    detection_type=detection_type,
                    detection_time=datetime.now(),
                    error_details=f"响应头包含 '{header_key}' 触发反爬虫检测",
                    response_status=response_status,
                    response_headers=response_headers
                )
        
        return None
    
    def get_recovery_strategy(self, detection: AntiCrawlDetection) -> Dict[str, Any]:
        """获取恢复策略"""
        strategies = {
            AntiCrawlType.RATE_LIMIT: {
                'action': 'wait_and_retry',
                'wait_time': self._extract_retry_after(detection.response_headers) or 60,
                'reduce_concurrency': True,
                'increase_delay': True
            },
            AntiCrawlType.CAPTCHA: {
                'action': 'manual_intervention',
                'message': '需要手动处理验证码',
                'pause_task': True
            },
            AntiCrawlType.IP_BLOCK: {
                'action': 'change_ip',
                'wait_time': 300,  # 5分钟
                'message': 'IP被封禁，需要更换IP或等待'
            },
            AntiCrawlType.SESSION_EXPIRED: {
                'action': 'refresh_session',
                'message': '会话过期，需要重新获取参数'
            },
            AntiCrawlType.SERVER_ERROR: {
                'action': 'retry_later',
                'wait_time': 30,
                'max_retries': 5
            },
            AntiCrawlType.NETWORK_ERROR: {
                'action': 'retry_immediately',
                'max_retries': 3
            }
        }
        
        return strategies.get(detection.detection_type, {
            'action': 'pause_and_investigate',
            'message': '未知错误类型，建议暂停任务进行调查'
        })
    
    def _extract_retry_after(self, headers: Dict[str, str]) -> Optional[int]:
        """从响应头提取重试等待时间"""
        if not headers:
            return None
        
        retry_after = headers.get('retry-after') or headers.get('Retry-After')
        if retry_after:
            try:
                return int(retry_after)
            except ValueError:
                pass
        
        return None


class ResumeManager:
    """断点续传管理器"""
    
    def __init__(self, db_manager: DatabaseQueryManager = None):
        self.db_manager = db_manager or DatabaseQueryManager()
        self.anti_crawl_detector = AntiCrawlDetector()
        self.logger = logging.getLogger(__name__)
        self.retry_config = RetryConfig()
        self._running_tasks: Dict[str, bool] = {}  # 跟踪正在运行的任务
    
    def create_batch_task_with_progress(self, name: str, description: str, 
                                      query_filter: QueryFilter) -> str:
        """创建批量任务并初始化进度记录"""
        # 创建批量任务
        task_id = self.db_manager.create_batch_crawl_task(name, description, query_filter)
        
        # 获取所有符合条件的URL
        question_urls = self.db_manager.get_question_urls_by_filter(query_filter)
        
        # 初始化进度记录
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            for question_id, question_url in question_urls:
                cursor.execute('''
                    INSERT INTO batch_crawl_progress 
                    (batch_task_id, question_id, question_url, status)
                    VALUES (%s, %s, %s, 'pending')
                    ON CONFLICT (batch_task_id, question_id) DO NOTHING
                ''', (task_id, question_id, question_url))
            
            conn.commit()
        
        self.logger.info(f"批量任务 {task_id} 创建完成，初始化了 {len(question_urls)} 个进度记录")
        return task_id
    
    def get_next_batch_to_process(self, task_id: str, batch_size: int = 10) -> List[CrawlProgress]:
        """获取下一批待处理的URL"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT batch_task_id, question_id, question_url, status, 
                       error_message, retry_count, created_at, updated_at
                FROM batch_crawl_progress 
                WHERE batch_task_id = %s AND status = 'pending'
                ORDER BY created_at
                LIMIT %s
            ''', (task_id, batch_size))
            
            progress_list = []
            for row in cursor.fetchall():
                progress = CrawlProgress(
                    batch_task_id=row[0], question_id=row[1], question_url=row[2],
                    status=row[3], error_message=row[4] or "", retry_count=row[5],
                    created_at=row[6], updated_at=row[7]
                )
                progress_list.append(progress)
            
            return progress_list
    
    def update_progress_status(self, batch_task_id: str, question_id: str, 
                             status: str, error_message: str = "", increment_retry: bool = False):
        """更新进度状态"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            if increment_retry:
                cursor.execute('''
                    UPDATE batch_crawl_progress 
                    SET status = %s, error_message = %s, retry_count = retry_count + 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE batch_task_id = %s AND question_id = %s
                ''', (status, error_message, batch_task_id, question_id))
            else:
                cursor.execute('''
                    UPDATE batch_crawl_progress 
                    SET status = %s, error_message = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE batch_task_id = %s AND question_id = %s
                ''', (status, error_message, batch_task_id, question_id))
            
            conn.commit()
    
    def log_anti_crawl_detection(self, detection: AntiCrawlDetection):
        """记录反爬虫检测日志"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO anti_crawl_logs 
                (batch_task_id, detection_time, detection_type, error_details,
                 response_status, response_headers, recovery_action)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (
                detection.batch_task_id,
                detection.detection_time,
                detection.detection_type.value,
                detection.error_details,
                detection.response_status,
                json.dumps(detection.response_headers) if detection.response_headers else None,
                detection.recovery_action
            ))
            conn.commit()
    
    def handle_crawl_error(self, batch_task_id: str, question_id: str, 
                          response_status: int, response_content: str = "",
                          response_headers: Dict[str, str] = None) -> Dict[str, Any]:
        """处理采集错误"""
        # 检测反爬虫机制
        detection = self.anti_crawl_detector.detect_anti_crawl(
            response_status, response_content, response_headers
        )
        
        if detection:
            detection.batch_task_id = batch_task_id
            self.log_anti_crawl_detection(detection)
            
            # 获取恢复策略
            recovery_strategy = self.anti_crawl_detector.get_recovery_strategy(detection)
            
            self.logger.warning(
                f"检测到反爬虫机制: {detection.detection_type.value}, "
                f"任务: {batch_task_id}, 问题: {question_id}, "
                f"恢复策略: {recovery_strategy['action']}"
            )
            
            return {
                'is_anti_crawl': True,
                'detection': detection,
                'recovery_strategy': recovery_strategy
            }
        else:
            # 普通错误，记录并准备重试
            error_msg = f"HTTP {response_status}: {response_content[:200]}"
            self.update_progress_status(batch_task_id, question_id, 'failed', error_msg)
            
            return {
                'is_anti_crawl': False,
                'error_message': error_msg,
                'should_retry': response_status >= 500  # 服务器错误可以重试
            }
    
    def calculate_retry_delay(self, retry_count: int) -> float:
        """计算重试延迟时间"""
        delay = min(
            self.retry_config.base_delay * (self.retry_config.exponential_base ** retry_count),
            self.retry_config.max_delay
        )
        
        if self.retry_config.jitter:
            # 添加±25%的随机抖动
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0, delay)
    
    def should_retry(self, retry_count: int, error_type: str = 'normal') -> bool:
        """判断是否应该重试"""
        if error_type == 'anti_crawl':
            return False  # 反爬虫错误不自动重试
        
        return retry_count < self.retry_config.max_retries
    
    def get_task_resume_point(self, task_id: str) -> Dict[str, Any]:
        """获取任务恢复点信息"""
        task = self.db_manager.get_batch_crawl_task(task_id)
        if not task:
            return {'error': '任务不存在'}
        
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # 统计各状态的数量
            cursor.execute('''
                SELECT status, COUNT(*) 
                FROM batch_crawl_progress 
                WHERE batch_task_id = %s 
                GROUP BY status
            ''', (task_id,))
            
            status_counts = dict(cursor.fetchall())
            
            # 获取最后处理的URL
            cursor.execute('''
                SELECT question_id, question_url, updated_at
                FROM batch_crawl_progress 
                WHERE batch_task_id = %s AND status IN ('completed', 'failed')
                ORDER BY updated_at DESC
                LIMIT 1
            ''', (task_id,))
            
            last_processed = cursor.fetchone()
            
            # 获取最近的反爬虫检测记录
            cursor.execute('''
                SELECT detection_type, detection_time, error_details
                FROM anti_crawl_logs 
                WHERE batch_task_id = %s 
                ORDER BY detection_time DESC
                LIMIT 5
            ''', (task_id,))
            
            recent_detections = cursor.fetchall()
        
        return {
            'task': task,
            'status_counts': status_counts,
            'last_processed': {
                'question_id': last_processed[0] if last_processed else None,
                'question_url': last_processed[1] if last_processed else None,
                'updated_at': str(last_processed[2]) if last_processed else None
            } if last_processed else None,
            'recent_detections': [
                {
                    'type': detection[0],
                    'time': str(detection[1]),
                    'details': detection[2]
                }
                for detection in recent_detections
            ],
            'can_resume': status_counts.get('pending', 0) > 0,
            'progress_percentage': (
                (status_counts.get('completed', 0) + status_counts.get('failed', 0)) / 
                max(task.total_urls, 1) * 100
            )
        }
    
    def pause_task(self, task_id: str, reason: str = ""):
        """暂停任务"""
        self.db_manager.update_batch_crawl_task_status(
            task_id, TaskStatus.PAUSED.value, error_message=reason
        )
        self._running_tasks[task_id] = False
        self.logger.info(f"任务 {task_id} 已暂停: {reason}")
    
    def resume_task(self, task_id: str):
        """恢复任务"""
        self.db_manager.update_batch_crawl_task_status(
            task_id, TaskStatus.RUNNING.value
        )
        self._running_tasks[task_id] = True
        self.logger.info(f"任务 {task_id} 已恢复")
    
    def is_task_running(self, task_id: str) -> bool:
        """检查任务是否正在运行"""
        return self._running_tasks.get(task_id, False)
    
    def get_failed_urls_for_retry(self, task_id: str, max_retry_count: int = None) -> List[CrawlProgress]:
        """获取可重试的失败URL"""
        max_retry_count = max_retry_count or self.retry_config.max_retries
        
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT batch_task_id, question_id, question_url, status, 
                       error_message, retry_count, created_at, updated_at
                FROM batch_crawl_progress 
                WHERE batch_task_id = %s AND status = 'failed' AND retry_count < %s
                ORDER BY updated_at
            ''', (task_id, max_retry_count))
            
            progress_list = []
            for row in cursor.fetchall():
                progress = CrawlProgress(
                    batch_task_id=row[0], question_id=row[1], question_url=row[2],
                    status=row[3], error_message=row[4] or "", retry_count=row[5],
                    created_at=row[6], updated_at=row[7]
                )
                progress_list.append(progress)
            
            return progress_list
    
    def reset_failed_to_pending(self, task_id: str, question_ids: List[str] = None):
        """将失败的URL重置为待处理状态"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            if question_ids:
                placeholders = ','.join(['%s'] * len(question_ids))
                cursor.execute(f'''
                    UPDATE batch_crawl_progress 
                    SET status = 'pending', error_message = '', updated_at = CURRENT_TIMESTAMP
                    WHERE batch_task_id = %s AND question_id IN ({placeholders}) AND status = 'failed'
                ''', [task_id] + question_ids)
            else:
                cursor.execute('''
                    UPDATE batch_crawl_progress 
                    SET status = 'pending', error_message = '', updated_at = CURRENT_TIMESTAMP
                    WHERE batch_task_id = %s AND status = 'failed'
                ''', (task_id,))
            
            conn.commit()
            affected_rows = cursor.rowcount
            
        self.logger.info(f"任务 {task_id} 重置了 {affected_rows} 个失败URL为待处理状态")
        return affected_rows